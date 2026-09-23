"""Tests for the retry/repair loop, conversation context and telemetry.

Uses a fake OpenAI client so the whole suite runs offline and deterministically.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from dataclasses import dataclass
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from support_platform.llm import LLMError, SupportLLM, _render_transcript  # noqa: E402
from support_platform.pipeline import SupportPipeline  # noqa: E402
from support_platform.schemas import Priority  # noqa: E402
from support_platform.storage import Database  # noqa: E402
from support_platform.validation import InputProblem  # noqa: E402

GOOD_JSON = """<think>reasoning here</think>

{"category": "billing", "priority": "high", "sentiment": "negative",
 "issue": "duplicate charge", "entities": [{"type": "amount", "value": "$20"}],
 "suggested_action": "refund_one_payment", "requires_human": true,
 "draft_response": "We are sorry, we'll review the duplicate charge.",
 "confidence": 0.9}"""

BAD_ENUM_JSON = """<think>reasoning</think>

{"category": "billing", "priority": "banana", "sentiment": "negative",
 "issue": "duplicate charge", "suggested_action": "refund",
 "requires_human": true, "draft_response": "Sorry.", "confidence": 0.8}"""

NOT_JSON = "I'm sorry, I can't produce structured output for that request."


# ----------------------------------------------------------------------
# Fake OpenAI client
# ----------------------------------------------------------------------
@dataclass
class _Usage:
    prompt_tokens: int = 120
    completion_tokens: int = 60
    total_tokens: int = 180


class _Msg:
    def __init__(self, content: str) -> None:
        self.content = content
        self.tool_calls = None


class _Choice:
    def __init__(self, content: str, finish_reason: str = "stop") -> None:
        self.message = _Msg(content)
        self.finish_reason = finish_reason


class _Response:
    def __init__(self, content: str, finish_reason: str = "stop") -> None:
        self.choices = [_Choice(content, finish_reason)]
        self.usage = _Usage()


class FakeCompletions:
    def __init__(self, script: list[Any]) -> None:
        self.script = list(script)
        self.calls: list[list[dict]] = []
        self.kwargs: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs["messages"])
        self.kwargs.append(kwargs)
        item = self.script.pop(0) if self.script else GOOD_JSON
        if isinstance(item, Exception):
            raise item
        if isinstance(item, tuple):  # (content, finish_reason)
            return _Response(*item)
        return _Response(item)


class FakeClient:
    def __init__(self, script: list[Any]) -> None:
        self.chat = type("chat", (), {})()
        self.chat.completions = FakeCompletions(script)


def make_llm(script: list[Any]) -> SupportLLM:
    """LLM with a scripted backend and tools disabled.

    These tests exercise the validate/repair loop; a research phase would consume
    scripted responses. Tool behaviour has its own suite in ``test_tools.py``.
    """
    llm = SupportLLM()
    llm.client = FakeClient(script)

    original = llm.analyse

    def analyse(conversation, **kwargs):
        kwargs.setdefault("use_tools", False)
        return original(conversation, **kwargs)

    llm.analyse = analyse  # type: ignore[method-assign]
    return llm


class TestRetryRepair(unittest.TestCase):
    def test_first_attempt_success(self):
        llm = make_llm([GOOD_JSON])
        analysis, _, _ = llm.analyse([{"role": "customer", "content": "charged twice"}])
        self.assertIs(analysis.priority, Priority.HIGH)
        self.assertEqual(len(llm.client.chat.completions.calls), 1)

    def test_repairs_after_invalid_enum(self):
        llm = make_llm([BAD_ENUM_JSON, GOOD_JSON])
        analysis, _, _ = llm.analyse([{"role": "customer", "content": "charged twice"}])
        self.assertIs(analysis.priority, Priority.HIGH)
        calls = llm.client.chat.completions.calls
        self.assertEqual(len(calls), 2, "should have retried once")

        # The repair prompt must contain the actual validation error.
        repair_text = calls[1][-1]["content"]
        self.assertIn("priority", repair_text)
        self.assertIn("banana", repair_text)

    def test_repairs_after_non_json(self):
        llm = make_llm([NOT_JSON, GOOD_JSON])
        analysis, _, _ = llm.analyse([{"role": "customer", "content": "hello there"}])
        self.assertIs(analysis.priority, Priority.HIGH)

    def test_gives_up_after_max_attempts(self):
        llm = make_llm([BAD_ENUM_JSON, BAD_ENUM_JSON, BAD_ENUM_JSON])
        with self.assertRaises(LLMError):
            llm.analyse([{"role": "customer", "content": "charged twice"}])
        self.assertEqual(len(llm.client.chat.completions.calls), 3)

    def test_connection_error_raises(self):
        llm = make_llm([ConnectionError("server down")])
        with self.assertRaises(LLMError):
            llm.analyse([{"role": "customer", "content": "charged twice"}])

    def test_metrics_recorded_per_attempt(self):
        llm = make_llm([BAD_ENUM_JSON, GOOD_JSON])
        llm.analyse([{"role": "customer", "content": "charged twice"}])
        summary = llm.metrics.summary()
        self.assertEqual(summary["calls"], 2)
        self.assertEqual(summary["retries"], 1)
        self.assertEqual(summary["successes"], 1, "failed-contract attempt counts as failure")
        self.assertGreater(summary["total_tokens"], 0)

    def test_transcript_includes_all_turns(self):
        llm = make_llm([GOOD_JSON])
        llm.analyse([
            {"role": "customer", "content": "My payment failed."},
            {"role": "customer", "content": "It happened three times."},
        ])
        prompt = llm.client.chat.completions.calls[0][1]["content"]
        self.assertIn("My payment failed.", prompt)
        self.assertIn("It happened three times.", prompt)


class TestTranscriptPurpose(unittest.TestCase):
    """Regression: research and analysis need OPPOSITE closing instructions.

    Sending the analyse instruction ("return the JSON object") to the research
    phase contradicted its system prompt. The model responded by calling zero
    tools and instead copying details out of earlier AGENT_DRAFT turns, then
    reporting them as "verified facts" -- laundering an unverified guess into
    the analysis prompt.
    """

    conversation = [
        {"role": "customer", "content": "What was my last order?"},
        {"role": "agent_draft", "content": "Your last order was A-5521 for $1,200.00."},
        {"role": "customer", "content": "my email is dana@acme-corp.com"},
    ]

    def test_research_transcript_does_not_ask_for_json(self):
        text = _render_transcript(self.conversation, purpose="research")
        self.assertNotIn("JSON", text)
        self.assertIn("tools", text.lower())

    def test_research_transcript_names_email_as_an_identifier(self):
        """The model previously claimed "no id provided" while an email was present."""
        text = _render_transcript(self.conversation, purpose="research")
        self.assertIn("EMAIL", text.upper())

    def test_analyse_transcript_still_asks_for_json(self):
        text = _render_transcript(self.conversation, purpose="analyse")
        self.assertIn("JSON", text)

    def test_analyse_is_the_default(self):
        self.assertEqual(
            _render_transcript(self.conversation),
            _render_transcript(self.conversation, purpose="analyse"),
        )

    def test_research_prompt_rejects_agent_drafts_as_evidence(self):
        from support_platform.llm import RESEARCH_PROMPT

        self.assertIn("AGENT_DRAFT", RESEARCH_PROMPT)
        self.assertIn("not evidence", RESEARCH_PROMPT.lower())

    def test_research_transcript_points_at_the_latest_message(self):
        """Regression: research must be driven by what the LATEST message needs.

        A blanket "look up every identifier in this conversation" made the model
        re-run lookups on closing messages like "okay, thank you so much",
        costing a tool round trip to confirm something already settled.
        """
        text = _render_transcript(self.conversation, purpose="research")
        self.assertIn("LATEST", text)
        self.assertIn("NO RESEARCH NEEDED", text)

    def test_research_prompt_allows_declining(self):
        from support_platform.llm import RESEARCH_PROMPT

        self.assertIn("NO RESEARCH NEEDED", RESEARCH_PROMPT)

    def test_system_prompt_defines_scope(self):
        """Scope is stated in the prompt AND enforced in rules.py."""
        from support_platform.llm import SYSTEM_PROMPT

        self.assertIn("out_of_scope", SYSTEM_PROMPT)
        self.assertIn("binary search", SYSTEM_PROMPT.lower())

    def test_system_prompt_treats_instructions_as_data(self):
        """Prompt-injection guidance: a command in a ticket is a fact, not an order."""
        from support_platform.llm import SYSTEM_PROMPT

        self.assertIn("DATA, not commands", SYSTEM_PROMPT)


class TestNoResearchSentinel(unittest.TestCase):
    """The decline sentinel must not reach the analysis prompt as 'facts'."""

    def test_recognises_the_sentinel(self):
        from support_platform.llm import _is_no_research

        for text in [
            "NO RESEARCH NEEDED",
            "no research needed",
            "**NO RESEARCH NEEDED.**",
            "NO RESEARCH NEEDED - the customer is just saying thanks.",
            "",
        ]:
            self.assertTrue(_is_no_research(text), msg=repr(text))

    def test_real_facts_are_not_mistaken_for_it(self):
        from support_platform.llm import _is_no_research

        self.assertFalse(_is_no_research("Customer C-1001 is on the enterprise plan."))

    def test_declined_research_yields_empty_facts(self):
        """Empty facts means the analysis prompt gets no VERIFIED DATA block."""
        llm = make_llm(["NO RESEARCH NEEDED", GOOD_JSON])
        llm.client.chat.completions.script = ["NO RESEARCH NEEDED", GOOD_JSON]
        facts, records = llm.research("transcript", request_id="t")
        self.assertEqual(facts, "")
        self.assertEqual(records, [])

    def test_sends_json_schema_when_enabled(self):
        """Structured output is requested so the backend can constrain generation."""
        llm = make_llm([GOOD_JSON])
        llm.analyse([{"role": "customer", "content": "charged twice"}])
        kwargs = llm.client.chat.completions.kwargs[0]
        rf = kwargs.get("response_format")
        self.assertIsNotNone(rf, "response_format should be sent")
        self.assertEqual(rf["type"], "json_schema")
        # Built from the Pydantic model, so grammar and contract cannot drift.
        self.assertIn("category", rf["json_schema"]["schema"]["properties"])

    def test_falls_back_when_backend_rejects_schema(self):
        """A server that refuses response_format must not kill the ticket.

        We disable the optimisation for this instance and retry unconstrained --
        the client-side parse/repair path still enforces the contract.
        """
        class RejectsSchemaOnce:
            def __init__(self):
                self.calls, self.kwargs = [], []

            def create(self, **kw):
                self.calls.append(kw["messages"])
                self.kwargs.append(kw)
                if "response_format" in kw:
                    raise ValueError("400: unknown field 'response_format'")
                return _Response(GOOD_JSON)

        llm = make_llm([GOOD_JSON])
        llm.client.chat.completions = RejectsSchemaOnce()

        analysis, _, _ = llm.analyse([{"role": "customer", "content": "charged twice"}])
        self.assertIs(analysis.priority, Priority.HIGH)
        self.assertFalse(llm._structured_output_ok, "should stop retrying the unsupported field")

    def test_truncated_response_reported_as_truncation(self):
        """A reply cut off at max_tokens must not be reported as malformed JSON.

        Observed live: the <think> block consumed the token budget and the JSON
        was cut mid-object, producing a misleading 'no JSON object found' error.
        """
        cut_off = '<think>long reasoning...</think>\n\n{"category": "billing", "priority": "hi'
        llm = make_llm([(cut_off, "length"), GOOD_JSON])
        analysis, _, _ = llm.analyse([{"role": "customer", "content": "charged twice"}])
        self.assertIs(analysis.priority, Priority.HIGH)

        first = llm.metrics.calls[0]
        self.assertFalse(first.success)
        self.assertIn("token limit", first.error)

        # The repair prompt should tell the model to be brief.
        repair_text = llm.client.chat.completions.calls[1][-1]["content"]
        self.assertIn("cut off", repair_text)


class TestPipeline(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.db = Database(self.tmp.name)

    def tearDown(self):
        os.unlink(self.tmp.name)

    def _pipeline(self, script):
        llm = make_llm(script)
        p = SupportPipeline(db=self.db, llm=llm)
        llm._on_call = p._on_call
        llm.metrics = p.metrics
        return p

    def test_happy_path_persists(self):
        p = self._pipeline([GOOD_JSON])
        result = p.process("I was charged twice for my subscription.")
        self.assertTrue(result.ok)
        self.assertIs(result.analysis.priority, Priority.HIGH)

        stored = self.db.latest_analysis(result.ticket_id)
        self.assertEqual(stored["priority"], "high")
        self.assertEqual(stored["category"], "billing")

    def test_bad_input_short_circuits_without_calling_model(self):
        p = self._pipeline([GOOD_JSON])
        result = p.process("")
        self.assertFalse(result.ok)
        self.assertIs(result.problem, InputProblem.EMPTY)
        self.assertEqual(result.attempts, 0, "must not spend an inference call")
        self.assertTrue(result.analysis.requires_human)

    def test_foreign_language_analysed_normally(self):
        """Language is handled by the model, not by a pre-filter.

        By default every language is processed: the ticket is analysed and the
        draft reply is written in the customer's own language.
        """
        spanish_json = GOOD_JSON.replace('"category": "billing"', '"language": "es", "category": "billing"')
        p = self._pipeline([spanish_json])
        result = p.process("Hola, me cobraron dos veces la suscripcion, gracias por favor.")

        self.assertTrue(result.ok, "a foreign-language ticket is analysed like any other")
        self.assertEqual(result.analysis.language, "es")
        self.assertNotIn("unsupported_language", result.decision.fired_rules)

    def test_language_routing_when_review_limit_configured(self):
        """A team that can only review English flags other languages for a translator."""
        from support_platform.config import settings

        original = settings.supported_languages
        object.__setattr__(settings, "supported_languages", ("en",))
        try:
            spanish_json = GOOD_JSON.replace(
                '"category": "billing"', '"language": "es", "category": "billing"'
            )
            p = self._pipeline([spanish_json])
            result = p.process("Hola, me cobraron dos veces la suscripcion, gracias.")

            self.assertTrue(result.ok, "still analysed, just flagged")
            self.assertIn("unsupported_language", result.decision.fired_rules)
            self.assertIn("needs_translator", result.decision.tags)
            self.assertTrue(result.decision.requires_human)
        finally:
            object.__setattr__(settings, "supported_languages", original)

    def test_supported_language_does_not_fire_translator_rule(self):
        p = self._pipeline([GOOD_JSON])
        result = p.process("I was charged twice for my subscription.")
        self.assertNotIn("unsupported_language", result.decision.fired_rules)

    def test_model_failure_produces_fallback_not_crash(self):
        p = self._pipeline([ConnectionError("down")])
        result = p.process("I was charged twice for my subscription.")
        self.assertFalse(result.ok)
        self.assertIsNotNone(result.analysis)
        self.assertTrue(result.analysis.requires_human)
        # Ticket is still recorded so nothing is silently dropped.
        self.assertIsNotNone(self.db.latest_analysis(result.ticket_id))

    def test_conversation_context_accumulates(self):
        p = self._pipeline([GOOD_JSON, GOOD_JSON, GOOD_JSON])
        r1 = p.process("My payment failed.")
        r2 = p.process("It happened three times.", ticket_id=r1.ticket_id)
        r3 = p.process("Here's the error code: ERR_51", ticket_id=r1.ticket_id)

        self.assertEqual(r1.ticket_id, r3.ticket_id)
        customer_msgs = [m for m in p.conversation(r1.ticket_id) if m["role"] == "customer"]
        self.assertEqual(len(customer_msgs), 3)

        # The third call must have seen all three customer turns.
        third_prompt = p.llm.client.chat.completions.calls[-1][1]["content"]
        self.assertIn("My payment failed.", third_prompt)
        self.assertIn("It happened three times.", third_prompt)
        self.assertIn("ERR_51", third_prompt)

    def test_metrics_persisted_to_db(self):
        p = self._pipeline([BAD_ENUM_JSON, GOOD_JSON])
        p.process("I was charged twice for my subscription.")
        m = self.db.metrics_summary()
        self.assertEqual(m["calls"], 2)
        self.assertEqual(m["retries"], 1)
        self.assertGreater(m["total_tokens"], 0)

    def test_failed_attempt_recorded_as_failure_in_db(self):
        """Regression: an attempt that passes HTTP but fails schema validation
        must be persisted as success=0, not success=1."""
        p = self._pipeline([BAD_ENUM_JSON, GOOD_JSON])
        p.process("I was charged twice for my subscription.")
        m = self.db.metrics_summary()
        self.assertEqual(m["calls"], 2)
        self.assertEqual(m["successes"], 1, "the repaired attempt must count as a failure")
        self.assertEqual(m["success_rate"], 0.5)

        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT attempt, success, error FROM llm_calls ORDER BY attempt"
            ).fetchall()
        self.assertEqual(rows[0]["success"], 0)
        self.assertIn("priority", rows[0]["error"])
        self.assertEqual(rows[1]["success"], 1)

    def test_dashboard_rows(self):
        p = self._pipeline([GOOD_JSON])
        p.process("I was charged twice for my subscription.")
        rows = self.db.dashboard_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["priority"], "high")


if __name__ == "__main__":
    unittest.main(verbosity=2)
