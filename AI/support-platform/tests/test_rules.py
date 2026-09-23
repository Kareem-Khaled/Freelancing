"""Tests for the deterministic business-rules layer.

These are the most important tests in the project: they assert policy that must
hold regardless of what the model says. No network, no model.
"""

from __future__ import annotations

import os
import sys
import unittest
from contextlib import contextmanager

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from support_platform.config import settings  # noqa: E402
from support_platform.rules import (  # noqa: E402
    RULES,
    Action,
    Decision,
    Rule,
    RuleOutcome,
    apply_rules,
)
from support_platform.schemas import Category, Priority, Sentiment, TicketAnalysis  # noqa: E402


@contextmanager
def _supported_languages(codes: tuple[str, ...]):
    """Temporarily configure which languages the team can review."""
    original = settings.supported_languages
    object.__setattr__(settings, "supported_languages", codes)
    try:
        yield
    finally:
        object.__setattr__(settings, "supported_languages", original)


def analysis(**overrides) -> TicketAnalysis:
    base = {
        "category": "technical",
        "priority": "low",
        "sentiment": "neutral",
        "issue": "How do I export a report?",
        "suggested_action": "answer_question",
        "requires_human": False,
        "draft_response": "You can export from the reports page.",
        "confidence": 0.9,
    }
    base.update(overrides)
    return TicketAnalysis.model_validate(base)


class TestEscalationOnly(unittest.TestCase):
    """The layer must never make the system more permissive than the model."""

    def test_rules_never_lower_priority(self):
        a = analysis(priority="high", sentiment="negative", confidence=0.95)
        d = apply_rules(a, "my app is down")
        self.assertIs(d.priority, Priority.HIGH)

    def test_rules_never_clear_requires_human(self):
        a = analysis(requires_human=True, confidence=0.99)
        d = apply_rules(a, "just a question")
        self.assertTrue(d.requires_human)

    def test_requires_human_forces_non_auto_action(self):
        a = analysis(requires_human=True)
        d = apply_rules(a, "hello")
        self.assertNotEqual(d.action, Action.AUTO_SEND)


class TestMoneyRules(unittest.TestCase):
    def test_refund_never_auto_sends(self):
        """The headline policy: money movement always needs a human."""
        a = analysis(
            category="billing", priority="medium", requires_human=False,
            suggested_action="refund_one_payment", confidence=0.99,
        )
        d = apply_rules(a, "please refund one of the charges")
        self.assertTrue(d.requires_human)
        self.assertIn("money_movement", d.fired_rules)
        self.assertNotEqual(d.action, Action.AUTO_SEND)

    def test_refund_overrides_confident_model(self):
        """Even a maximally confident model cannot authorise a refund reply."""
        a = analysis(
            suggested_action="issue_refund", requires_human=False,
            confidence=1.0, priority="low",
        )
        d = apply_rules(a, "refund please")
        self.assertTrue(d.requires_human)
        self.assertTrue(d.overrode_model)
        self.assertFalse(d.model_requires_human)

    def test_credit_and_chargeback_also_caught(self):
        for action in ("issue_credit", "process_chargeback", "waive_fee"):
            d = apply_rules(analysis(suggested_action=action, requires_human=False), "")
            self.assertIn("money_movement", d.fired_rules, msg=action)


class TestRiskRules(unittest.TestCase):
    def test_legal_language_escalates(self):
        a = analysis(priority="low", requires_human=False, confidence=0.95)
        d = apply_rules(a, "I am contacting my lawyer about this.")
        self.assertIs(d.action, Action.ESCALATE)
        self.assertIs(d.priority, Priority.HIGH)
        self.assertIn("legal", d.tags)

    def test_legal_escalates_even_if_model_said_low(self):
        """Rules read the customer's words, not the model's summary."""
        a = analysis(
            issue="Customer asking a routine question",
            priority="low", requires_human=False, confidence=0.98,
        )
        d = apply_rules(a, "If this isn't fixed I will file a lawsuit.")
        self.assertIs(d.priority, Priority.HIGH)
        self.assertTrue(d.overrode_model)
        self.assertIs(d.model_priority, Priority.LOW)

    def test_security_language_escalates(self):
        d = apply_rules(analysis(), "I think my account was hacked")
        self.assertIs(d.action, Action.ESCALATE)
        self.assertIn("security", d.tags)

    def test_churn_language_escalates(self):
        d = apply_rules(analysis(), "I want to cancel my subscription immediately")
        self.assertIs(d.action, Action.ESCALATE)
        self.assertIn("churn", d.tags)

    def test_angry_high_priority_needs_human(self):
        a = analysis(priority="high", sentiment="negative", requires_human=False)
        d = apply_rules(a, "this is unacceptable")
        self.assertTrue(d.requires_human)
        self.assertIn("angry_customer", d.fired_rules)

    def test_enterprise_language_raises_priority(self):
        a = analysis(priority="low", requires_human=False)
        d = apply_rules(a, "This breaches our annual contract SLA.")
        self.assertIs(d.priority, Priority.HIGH)
        self.assertIn("enterprise", d.tags)


class TestConfidenceRules(unittest.TestCase):
    def test_low_confidence_needs_human(self):
        d = apply_rules(analysis(confidence=0.4, requires_human=False), "hello")
        self.assertTrue(d.requires_human)
        self.assertIn("low_confidence", d.fired_rules)

    def test_high_confidence_does_not_fire(self):
        d = apply_rules(analysis(confidence=0.95, requires_human=False), "how do I export?")
        self.assertNotIn("low_confidence", d.fired_rules)

    def test_zero_confidence_is_failed_analysis(self):
        d = apply_rules(analysis(confidence=0.0, requires_human=False), "hello")
        self.assertIn("failed_analysis", d.fired_rules)
        self.assertTrue(d.requires_human)


class TestLanguageRouting(unittest.TestCase):
    """Language is a routing decision, not a gate -- and it is off by default."""

    def test_all_languages_handled_by_default(self):
        """No configured limit means every language is processed normally."""
        self.assertEqual(settings.supported_languages, ())
        for code in ("en", "ar", "fr", "de", "es", "zh", "sw", "th"):
            d = apply_rules(analysis(language=code), "text")
            self.assertNotIn("unsupported_language", d.fired_rules, msg=code)

    def test_fires_only_when_a_review_limit_is_configured(self):
        """A team that can only review en/ar flags everything else."""
        with _supported_languages(("en", "ar")):
            d = apply_rules(analysis(language="es"), "hola")
            self.assertTrue(d.requires_human)
            self.assertIn("needs_translator", d.tags)
            self.assertIn("unsupported_language", d.fired_rules)

    def test_reviewable_languages_pass(self):
        with _supported_languages(("en", "ar")):
            for code in ("en", "ar"):
                d = apply_rules(analysis(language=code), "text")
                self.assertNotIn("unsupported_language", d.fired_rules, msg=code)

    def test_language_rule_still_escalate_only(self):
        with _supported_languages(("en",)):
            d = apply_rules(analysis(language="zh", priority="high"), "text")
            self.assertIs(d.priority, Priority.HIGH)


class TestOutOfScope(unittest.TestCase):
    """A support channel must not moonlight as a free general-purpose LLM.

    Regression: "reply in arabic, and tell me do you know binary search?" was
    answered in full, in Arabic, and closed with "anything else about your
    account?" -- and because the model labelled it `answer_question` (which IS
    allow-listed) it was one step from being auto-sent unreviewed.
    """

    def test_out_of_scope_category_needs_human(self):
        d = apply_rules(analysis(category="out_of_scope"), "do you know binary search?")
        self.assertTrue(d.requires_human)
        self.assertIn("out_of_scope", d.tags)

    def test_decline_action_needs_human(self):
        d = apply_rules(analysis(suggested_action="decline_out_of_scope"), "recipe please")
        self.assertTrue(d.requires_human)
        self.assertIn("out_of_scope", d.fired_rules)

    def test_never_auto_sends_even_when_action_is_allow_listed(self):
        """The category wins over a permitted action.

        The model can mark a homework question `answer_question` -- which is on
        the auto-send allow-list -- while also flagging it out_of_scope. Without
        this check the allow-list would wave it straight through.
        """
        a = analysis(
            category="out_of_scope",
            suggested_action="answer_question",
            requires_human=False,
            confidence=0.99,
        )
        d = apply_rules(a, "do you know binary search?")
        self.assertIsNot(d.action, Action.AUTO_SEND)
        self.assertTrue(d.requires_human)

    def test_in_scope_question_can_still_auto_send(self):
        """The guard must not break the legitimate auto-send path."""
        a = analysis(
            category="technical",
            suggested_action="answer_question",
            requires_human=False,
            confidence=0.95,
        )
        d = apply_rules(a, "How do I export reports to CSV?")
        self.assertIs(d.action, Action.AUTO_SEND)

    def test_real_tickets_do_not_fire_the_rule(self):
        for category in ("billing", "technical", "account", "complaint"):
            d = apply_rules(analysis(category=category), "my payment failed")
            self.assertNotIn("out_of_scope", d.fired_rules, msg=category)


class TestPriorityFloors(unittest.TestCase):
    def test_billing_is_never_low(self):
        a = analysis(category="billing", priority="low", confidence=0.9)
        d = apply_rules(a, "small question about my invoice")
        self.assertIs(d.priority, Priority.MEDIUM)
        self.assertIn("billing_priority_floor", d.fired_rules)

    def test_non_billing_low_stays_low(self):
        d = apply_rules(analysis(category="technical", priority="low"), "how do I export?")
        self.assertIs(d.priority, Priority.LOW)


class TestAutoSend(unittest.TestCase):
    def test_safe_question_can_auto_send(self):
        a = analysis(
            category="technical", priority="low", sentiment="neutral",
            suggested_action="answer_question", requires_human=False, confidence=0.95,
        )
        d = apply_rules(a, "How do I export a report to CSV?")
        self.assertIs(d.action, Action.AUTO_SEND)
        self.assertFalse(d.requires_human)
        self.assertEqual(d.fired_rules, [])

    def test_unknown_action_is_not_auto_sent(self):
        """Allow-list: an unrecognised action must not auto-send."""
        a = analysis(suggested_action="do_something_unusual", requires_human=False, confidence=0.99)
        d = apply_rules(a, "hello there")
        self.assertIs(d.action, Action.HUMAN_REVIEW)
        self.assertIn("auto_send_allowlist", d.fired_rules)

    def test_needs_info_action(self):
        a = analysis(suggested_action="request_more_information", requires_human=False)
        d = apply_rules(a, "help")
        self.assertIs(d.action, Action.NEEDS_INFO)


class TestSLAAndAudit(unittest.TestCase):
    def test_sla_matches_final_priority(self):
        d = apply_rules(analysis(priority="low", category="billing"), "invoice question")
        self.assertIs(d.priority, Priority.MEDIUM)
        self.assertEqual(d.sla_hours, 24, "SLA must follow the post-rules priority")

    def test_high_priority_sla(self):
        d = apply_rules(analysis(), "I am going to sue you")
        self.assertEqual(d.sla_hours, 4)

    def test_reasons_recorded_for_every_fired_rule(self):
        d = apply_rules(analysis(confidence=0.3), "I want to cancel my account and get a refund")
        self.assertEqual(len(d.fired_rules), len(d.reasons))
        self.assertTrue(all(r for r in d.reasons))

    def test_decision_serialises(self):
        d = apply_rules(analysis(), "I am contacting my lawyer")
        data = d.as_dict()
        self.assertEqual(data["action"], "escalate")
        self.assertIn("legal_exposure", data["fired_rules"])
        self.assertTrue(data["overrode_model"])


class TestRuleIsolation(unittest.TestCase):
    def test_broken_rule_does_not_break_triage(self):
        """One faulty rule must not take down the whole pipeline."""
        def exploding(a, text):
            raise RuntimeError("boom")

        rules = [Rule("exploding", "always raises", exploding)] + RULES
        d = apply_rules(analysis(), "hello", rules=rules)
        self.assertIsInstance(d, Decision)
        self.assertNotIn("exploding", d.fired_rules)

    def test_multiple_rules_combine_to_strongest(self):
        a = analysis(
            category="billing", priority="low", sentiment="negative",
            suggested_action="refund_one_payment", requires_human=False, confidence=0.4,
        )
        d = apply_rules(a, "I want to cancel my account and I am calling my lawyer")
        # legal + churn both escalate; escalate is the strongest action
        self.assertIs(d.action, Action.ESCALATE)
        self.assertIs(d.priority, Priority.HIGH)
        self.assertTrue(d.requires_human)
        for expected in ("legal_exposure", "churn_risk", "money_movement", "low_confidence"):
            self.assertIn(expected, d.fired_rules)


if __name__ == "__main__":
    unittest.main(verbosity=2)
