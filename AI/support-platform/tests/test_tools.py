"""Tests for the tool layer: dispatch safety, grounding and tool-aware rules.

All offline -- the CRM is seeded mock data and no model is called.
"""

from __future__ import annotations

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from support_platform import crm  # noqa: E402
from support_platform.rules import Action, ToolFacts, apply_rules  # noqa: E402
from support_platform.schemas import Priority, TicketAnalysis  # noqa: E402
from support_platform.tools import REGISTRY, ToolCallRecord, ToolRegistry  # noqa: E402

# Most dispatch tests look up C-1002; scope to them so authorisation is not the
# subject under test. Cross-customer access has its own suite below.
SCOPED = REGISTRY.scoped("C-1002")


def analysis(**overrides) -> TicketAnalysis:
    base = {
        "category": "billing", "priority": "medium", "sentiment": "neutral",
        "issue": "Customer reports a duplicate charge",
        "suggested_action": "refund_one_payment", "requires_human": False,
        "draft_response": "We'll look into it.", "confidence": 0.9,
    }
    base.update(overrides)
    return TicketAnalysis.model_validate(base)


class TestCRM(unittest.TestCase):
    def test_get_customer(self):
        self.assertEqual(crm.get_customer("C-1002")["plan"], "pro")

    def test_customer_id_is_case_insensitive(self):
        self.assertEqual(crm.get_customer("c-1002")["customer_id"], "C-1002")

    def test_unknown_customer_raises(self):
        with self.assertRaises(crm.NotFound):
            crm.get_customer("C-9999")

    def test_find_by_email(self):
        self.assertEqual(crm.find_customer_by_email("sam@example.net")["customer_id"], "C-1002")

    def test_duplicate_detection_finds_real_duplicate(self):
        """C-1002 is seeded with two identical charges one day apart."""
        dupes = crm.find_duplicate_charges("C-1002")
        self.assertTrue(dupes)
        self.assertEqual(dupes[0]["amount_usd"], 29.99)
        self.assertLessEqual(dupes[0]["days_apart"], 7)

    def test_no_false_positive_duplicate(self):
        self.assertEqual(crm.find_duplicate_charges("C-1001"), [])

    def test_failed_payment_has_error_code(self):
        payments = crm.get_payments("C-1003")
        self.assertEqual(payments[0]["error_code"], "ERR_CARD_DECLINED_51")


class TestToolDispatch(unittest.TestCase):
    def test_successful_call(self):
        payload, rec = SCOPED.call("get_customer", '{"customer_id": "C-1002"}')
        self.assertTrue(rec.ok)
        self.assertEqual(json.loads(payload)["plan"], "pro")

    def test_accepts_dict_arguments(self):
        _, rec = SCOPED.call("get_customer", {"customer_id": "C-1002"})
        self.assertTrue(rec.ok)

    def test_unknown_tool_returns_error_not_raise(self):
        payload, rec = REGISTRY.call("delete_everything", "{}")
        self.assertFalse(rec.ok)
        self.assertIn("unknown tool", rec.error)
        self.assertIn("error", json.loads(payload))

    def test_malformed_json_arguments(self):
        payload, rec = REGISTRY.call("get_customer", "{not json")
        self.assertFalse(rec.ok)
        self.assertIn("not valid JSON", rec.error)

    def test_not_found_is_reported_to_model(self):
        """A missing record for YOUR OWN account is reported plainly."""
        payload, rec = SCOPED.call("get_customer", '{"email": "nobody@example.com"}')
        self.assertFalse(rec.ok)
        self.assertIn("no customer", json.loads(payload)["error"])

    def test_denial_precedes_not_found(self):
        """Refusing before the lookup prevents customer-id enumeration.

        If unknown ids returned "no such customer" while real ones returned
        "access denied", an attacker could map which ids exist. Both return the
        same denial instead.
        """
        unknown, _ = SCOPED.call("get_customer", '{"customer_id": "C-9999"}')
        other, _ = SCOPED.call("get_customer", '{"customer_id": "C-1001"}')
        self.assertIn("Access denied", json.loads(unknown)["error"])
        self.assertIn("Access denied", json.loads(other)["error"])

    def test_stray_arguments_are_dropped(self):
        """Small models routinely add keys the schema never declared."""
        _, rec = SCOPED.call(
            "get_customer", '{"customer_id": "C-1002", "reason": "because", "x": 1}'
        )
        self.assertTrue(rec.ok)
        self.assertEqual(rec.arguments, {"customer_id": "C-1002"})

    def test_missing_required_argument(self):
        _, rec = SCOPED.call("get_orders", "{}")
        self.assertFalse(rec.ok)
        self.assertIn("invalid arguments", rec.error)

    def test_empty_arguments_for_no_arg_tool(self):
        payload, rec = REGISTRY.call("get_refund_policy", "")
        self.assertTrue(rec.ok)
        self.assertEqual(json.loads(payload)["window_days"], 30)

    def test_duplicate_check_tool(self):
        payload, rec = SCOPED.call("check_duplicate_charges", '{"customer_id": "C-1002"}')
        self.assertTrue(rec.ok)
        self.assertTrue(json.loads(payload)["duplicate_found"])
        self.assertIn("duplicate_found=True", rec.result_summary)

    def test_exploding_tool_is_contained(self):
        """A tool that raises must not propagate into the research loop."""
        from support_platform.tools import Tool

        def boom(**kwargs):
            raise RuntimeError("backend on fire")

        registry = ToolRegistry([
            Tool("boom", "always fails", {"type": "object", "properties": {}}, boom)
        ])
        payload, rec = registry.call("boom", "{}")
        self.assertFalse(rec.ok)
        self.assertIn("backend on fire", rec.error)

    def test_all_tools_are_read_only(self):
        """Guard against someone adding a write tool the model could call."""
        forbidden = ("create", "update", "delete", "issue", "refund", "charge", "send")
        for name in REGISTRY.names:
            self.assertFalse(
                name.startswith(forbidden),
                msg=f"tool {name!r} looks like a write operation; the model must not have one",
            )

    def test_specs_are_valid_openai_format(self):
        for spec in REGISTRY.specs():
            self.assertEqual(spec["type"], "function")
            self.assertIn("name", spec["function"])
            self.assertIn("parameters", spec["function"])
            self.assertEqual(spec["function"]["parameters"]["type"], "object")


class TestCrossCustomerAccess(unittest.TestCase):
    """Authorisation. The most important tests in this file.

    Regression: a ticket opened by Dana (C-1001) could read Sam's (C-1002)
    customer record, orders and full payment history simply by naming his email.
    The model *happened* to decline to repeat it in the draft reply, but the data
    had already been fetched into the prompt, the trace panel and the database --
    and model discretion is exactly what the rules layer exists because we cannot
    rely on.
    """

    def setUp(self):
        self.dana = REGISTRY.scoped("C-1001")   # Sam is C-1002 / sam@example.net

    def test_cannot_read_another_customer_by_id(self):
        _, rec = self.dana.call("get_customer", '{"customer_id": "C-1002"}')
        self.assertFalse(rec.ok)
        self.assertIn("Access denied", rec.error)

    def test_cannot_read_another_customer_by_email(self):
        """The exact attack: name someone else's email and ask for their data."""
        _, rec = self.dana.call("get_customer", '{"email": "sam@example.net"}')
        self.assertFalse(rec.ok)
        self.assertIn("Access denied", rec.error)

    def test_cannot_read_another_customers_payments(self):
        _, rec = self.dana.call("get_payments", '{"customer_id": "C-1002"}')
        self.assertFalse(rec.ok)

    def test_cannot_read_another_customers_orders(self):
        _, rec = self.dana.call("get_orders", '{"customer_id": "C-1002"}')
        self.assertFalse(rec.ok)

    def test_cannot_read_another_customers_order_by_order_id(self):
        """B-8842 belongs to Sam; the order id alone must not expose it."""
        _, rec = self.dana.call("get_order", '{"order_id": "B-8842"}')
        self.assertFalse(rec.ok)
        self.assertIn("Access denied", rec.error)

    def test_cannot_probe_another_customer_for_duplicates(self):
        _, rec = self.dana.call("check_duplicate_charges", '{"customer_id": "C-1002"}')
        self.assertFalse(rec.ok)

    def test_own_data_still_accessible(self):
        """Scoping must not break the legitimate case."""
        payload, rec = self.dana.call("get_customer", '{"email": "dana@acme-corp.com"}')
        self.assertTrue(rec.ok)
        self.assertEqual(json.loads(payload)["customer_id"], "C-1001")

    def test_own_order_accessible(self):
        _, rec = self.dana.call("get_order", '{"order_id": "A-5521"}')
        self.assertTrue(rec.ok)

    def test_impersonal_tools_need_no_scope(self):
        """The refund policy is not anyone's personal data."""
        _, rec = REGISTRY.scoped(None).call("get_refund_policy", "{}")
        self.assertTrue(rec.ok)

    def test_anonymous_ticket_cannot_read_anyone(self):
        """No verified identity means no personal lookups at all."""
        anon = REGISTRY.scoped(None)
        for tool, args in [
            ("get_customer", '{"customer_id": "C-1002"}'),
            ("get_customer", '{"email": "sam@example.net"}'),
            ("get_payments", '{"customer_id": "C-1001"}'),
        ]:
            _, rec = anon.call(tool, args)
            self.assertFalse(rec.ok, msg=f"{tool} leaked for an anonymous ticket")
            self.assertIn("no verified customer identity", rec.error)

    def test_denial_message_guides_the_model(self):
        """Errors are instructions, not just refusals."""
        _, rec = self.dana.call("get_customer", '{"email": "sam@example.net"}')
        self.assertIn("C-1001", rec.error)
        self.assertIn("account holder", rec.error)


class TestIdentityResolution(unittest.TestCase):
    """Identity comes from the CHANNEL, never from the message body."""

    def test_customer_id_resolves(self):
        from support_platform.pipeline import _resolve_identity

        self.assertEqual(_resolve_identity("C-1002"), "C-1002")

    def test_email_resolves(self):
        from support_platform.pipeline import _resolve_identity

        self.assertEqual(_resolve_identity("dana@acme-corp.com"), "C-1001")

    def test_placeholders_are_anonymous(self):
        from support_platform.pipeline import _resolve_identity

        for label in ("web", "unknown", "", "demo", "test", "anonymous"):
            self.assertIsNone(_resolve_identity(label), msg=label)

    def test_unknown_identifier_is_anonymous(self):
        """An unrecognised label must fail closed, not open."""
        from support_platform.pipeline import _resolve_identity

        self.assertIsNone(_resolve_identity("C-9999"))
        self.assertIsNone(_resolve_identity("nobody@example.com"))


class TestToolFacts(unittest.TestCase):
    def test_verified_duplicate(self):
        records = [ToolCallRecord("check_duplicate_charges", {}, True, "duplicate_found=True (1 pair(s))")]
        facts = ToolFacts.from_records(records)
        self.assertTrue(facts.duplicate_verified)
        self.assertTrue(facts.duplicate_checked)

    def test_checked_but_no_duplicate(self):
        records = [ToolCallRecord("check_duplicate_charges", {}, True, "duplicate_found=False (0 pair(s))")]
        facts = ToolFacts.from_records(records)
        self.assertTrue(facts.duplicate_checked)
        self.assertFalse(facts.duplicate_verified)

    def test_customer_plan_parsed(self):
        records = [ToolCallRecord("get_customer", {}, True, "customer_id=C-1001, name=Dana, plan=enterprise")]
        self.assertEqual(ToolFacts.from_records(records).customer_plan, "enterprise")

    def test_empty_records(self):
        facts = ToolFacts.from_records([])
        self.assertFalse(facts.duplicate_checked)
        self.assertFalse(facts.lookup_failed)


class TestToolGroundedRules(unittest.TestCase):
    def test_verified_duplicate_raises_priority(self):
        records = [ToolCallRecord("check_duplicate_charges", {}, True, "duplicate_found=True (1 pair(s))")]
        d = apply_rules(analysis(priority="low"), "charged twice", tools=records)
        self.assertIs(d.priority, Priority.HIGH)
        self.assertIn("verified_duplicate", d.tags)

    def test_unverified_refund_claim_is_flagged(self):
        """The customer claims a duplicate; billing says otherwise."""
        records = [ToolCallRecord("check_duplicate_charges", {}, True, "duplicate_found=False (0 pair(s))")]
        d = apply_rules(analysis(), "I was charged twice", tools=records)
        self.assertIn("unverified_claim", d.tags)
        self.assertTrue(d.requires_human)

    def test_unverified_claim_detected_via_issue_text(self):
        """Regression: the model may pick a neutral action but describe a refund
        in the issue. Seen live with action='review_billing_inquiry'."""
        a = analysis(
            suggested_action="review_billing_inquiry",
            issue="Customer requests a refund for a duplicate charge",
        )
        records = [ToolCallRecord("check_duplicate_charges", {}, True, "duplicate_found=False (0 pair(s))")]
        d = apply_rules(a, "charged twice", tools=records)
        self.assertIn("unverified_claim", d.tags)

    def test_no_money_mention_does_not_flag(self):
        a = analysis(suggested_action="answer_question", issue="How do I export data?")
        records = [ToolCallRecord("check_duplicate_charges", {}, True, "duplicate_found=False (0 pair(s))")]
        d = apply_rules(a, "question", tools=records)
        self.assertNotIn("unverified_claim", d.tags)

    def test_verified_enterprise_escalates(self):
        records = [ToolCallRecord("get_customer", {}, True, "customer_id=C-1001, plan=enterprise")]
        d = apply_rules(analysis(priority="low"), "help", tools=records)
        self.assertIs(d.priority, Priority.HIGH)
        self.assertIn("enterprise_verified", d.tags)

    def test_unidentified_customer_needs_human(self):
        records = [ToolCallRecord("get_customer", {}, False, error="no customer with id 'C-9999'")]
        d = apply_rules(analysis(requires_human=False), "help me", tools=records)
        self.assertTrue(d.requires_human)
        self.assertIn("unidentified", d.tags)

    def test_no_tools_behaves_as_before(self):
        """Tool rules must be inert when research did not run."""
        d = apply_rules(analysis(), "charged twice", tools=None)
        for tag in ("verified_duplicate", "unverified_claim", "unidentified"):
            self.assertNotIn(tag, d.tags)

    def test_tool_rules_still_escalate_only(self):
        records = [ToolCallRecord("check_duplicate_charges", {}, True, "duplicate_found=True (1 pair(s))")]
        d = apply_rules(analysis(priority="high", requires_human=True), "x", tools=records)
        self.assertIs(d.priority, Priority.HIGH)
        self.assertTrue(d.requires_human)


if __name__ == "__main__":
    unittest.main(verbosity=2)
