"""Tests for the live execution trace.

Tracing is diagnostics: it must never change behaviour and must never raise.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from support_platform import trace  # noqa: E402
from support_platform.storage import Database  # noqa: E402
from support_platform.trace import TraceCollector, use_collector  # noqa: E402
from test_pipeline import BAD_ENUM_JSON, GOOD_JSON, make_llm  # noqa: E402
from support_platform.pipeline import SupportPipeline  # noqa: E402


class TestCollector(unittest.TestCase):
    def test_emit_without_collector_is_a_no_op(self):
        """The CLI and tests run untraced; emit must be silently inert."""
        self.assertIsNone(trace.current())
        trace.emit("validate", "nothing is listening")  # must not raise

    def test_events_recorded_in_order(self):
        collector = TraceCollector()
        with use_collector(collector):
            trace.emit("validate", "first")
            trace.emit("analyse", "second")
        labels = [e["label"] for e in collector.snapshot()]
        self.assertEqual(labels, ["first", "second"])

    def test_collector_detached_after_block(self):
        collector = TraceCollector()
        with use_collector(collector):
            pass
        trace.emit("validate", "after")
        self.assertEqual(collector.snapshot(), [])

    def test_snapshot_is_json_safe(self):
        import json

        collector = TraceCollector()
        with use_collector(collector):
            trace.emit("tool", "get_customer(id=C-1)", detail="found", tool="get_customer")
        json.dumps(collector.snapshot())  # must not raise

    def test_elapsed_is_recorded(self):
        collector = TraceCollector()
        with use_collector(collector):
            trace.emit("validate", "x")
        self.assertGreaterEqual(collector.snapshot()[0]["elapsed_ms"], 0.0)

    def test_emit_never_raises(self):
        """A bug in tracing must not take down ticket processing."""
        class Exploding(TraceCollector):
            def add(self, event):
                raise RuntimeError("boom")

        with use_collector(Exploding()):
            trace.emit("validate", "should be swallowed")  # must not raise


class TestPipelineTracing(unittest.TestCase):
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

    def test_happy_path_emits_each_phase(self):
        collector = TraceCollector()
        p = self._pipeline([GOOD_JSON])
        with use_collector(collector):
            p.process("I was charged twice for my subscription.")

        phases = [e["phase"] for e in collector.snapshot()]
        for expected in ("validate", "analyse", "rules", "store"):
            self.assertIn(expected, phases, msg=f"missing {expected}")

    def test_rejected_input_is_traced(self):
        collector = TraceCollector()
        p = self._pipeline([GOOD_JSON])
        with use_collector(collector):
            p.process("")

        events = collector.snapshot()
        self.assertTrue(any(e["status"] == "fail" for e in events))
        self.assertEqual(events[0]["phase"], "validate")

    def test_rule_overrides_are_visible(self):
        collector = TraceCollector()
        p = self._pipeline([GOOD_JSON])
        with use_collector(collector):
            p.process("I was charged twice, please refund me.")

        rule_events = [e for e in collector.snapshot() if e["phase"] == "rules"]
        self.assertTrue(rule_events, "business rules should appear in the trace")
        self.assertTrue(any("money_movement" in e["label"] for e in rule_events))

    def test_untraced_run_produces_same_result(self):
        """Tracing must not alter the outcome."""
        p1 = self._pipeline([GOOD_JSON])
        untraced = p1.process("I was charged twice for my subscription.")

        p2 = self._pipeline([GOOD_JSON])
        with use_collector(TraceCollector()):
            traced = p2.process("I was charged twice for my subscription.")

        self.assertEqual(untraced.analysis.category, traced.analysis.category)
        self.assertEqual(untraced.decision.action, traced.decision.action)


class TestRawExchangeCapture(unittest.TestCase):
    """Every model call should expose exactly what was sent and received."""

    def test_llm_event_carries_prompt_and_response(self):
        collector = TraceCollector()
        llm = make_llm([GOOD_JSON])
        with use_collector(collector):
            llm.analyse([{"role": "customer", "content": "I was charged twice"}])

        llm_events = [e for e in collector.snapshot() if e["phase"] == "llm"]
        self.assertTrue(llm_events, "a model call should emit an llm event")

        event = llm_events[0]
        self.assertIn("prompt", event)
        self.assertIn("response", event)
        # The prompt shows the real transcript sent to the model.
        self.assertIn("SYSTEM", event["prompt"])
        self.assertIn("I was charged twice", event["prompt"])
        # The response is the raw text, before parsing.
        self.assertIn("billing", event["response"])

    def test_repair_round_shows_both_exchanges(self):
        """When a retry fires you can compare the bad reply with the fixed one."""
        collector = TraceCollector()
        llm = make_llm([BAD_ENUM_JSON, GOOD_JSON])
        with use_collector(collector):
            llm.analyse([{"role": "customer", "content": "charged twice"}])

        llm_events = [e for e in collector.snapshot() if e["phase"] == "llm"]
        self.assertEqual(len(llm_events), 2, "both attempts should be visible")
        self.assertIn("banana", llm_events[0]["response"], "the invalid value should be inspectable")
        # The repair prompt must contain the validation error fed back.
        self.assertIn("banana", llm_events[1]["prompt"])

    def test_long_exchange_is_truncated(self):
        """A pasted log dump must not bloat every poll response."""
        collector = TraceCollector()
        llm = make_llm([GOOD_JSON])
        with use_collector(collector):
            llm.analyse([{"role": "customer", "content": "x " * 20000}])

        event = [e for e in collector.snapshot() if e["phase"] == "llm"][0]
        self.assertLess(len(event["prompt"]), 8000)
        self.assertIn("more characters", event["prompt"])

    def test_non_llm_events_have_no_exchange(self):
        """Only model calls carry raw payloads."""
        collector = TraceCollector()
        with use_collector(collector):
            trace.emit("validate", "Input accepted")
        self.assertNotIn("prompt", collector.snapshot()[0])


if __name__ == "__main__":
    unittest.main(verbosity=2)
