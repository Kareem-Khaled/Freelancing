"""Offline tests: no network, no model server required.

Run with:  python -m unittest discover -s tests -v
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from support_platform.schemas import Category, Priority, Sentiment, TicketAnalysis  # noqa: E402
from support_platform.textproc import extract_json, strip_think  # noqa: E402
from support_platform.validation import (  # noqa: E402
    InputProblem,
    validate_message,
)


class TestThinkStripping(unittest.TestCase):
    def test_strips_block(self):
        self.assertEqual(strip_think("<think>\n\n</think>\n\n391"), "391")

    def test_strips_populated_block(self):
        raw = "<think>Thinking Process: 1. analyse...</think>\n\n{\"a\": 1}"
        self.assertEqual(strip_think(raw), '{"a": 1}')


class TestJSONExtraction(unittest.TestCase):
    def test_plain(self):
        self.assertEqual(extract_json('{"category": "billing"}'), {"category": "billing"})

    def test_after_think_block(self):
        raw = '<think>reasoning</think>\n\n{"category": "Billing", "priority": "High"}'
        self.assertEqual(extract_json(raw), {"category": "Billing", "priority": "High"})

    def test_fenced(self):
        raw = 'Here you go:\n```json\n{"a": 1}\n```\nhope that helps'
        self.assertEqual(extract_json(raw), {"a": 1})

    def test_prefers_final_object(self):
        # The model drafts one object then restates the final answer.
        raw = '<think>draft {"a": 1}</think>\n\n{"a": 2}'
        self.assertEqual(extract_json(raw), {"a": 2})

    def test_trailing_comma_repaired(self):
        self.assertEqual(extract_json('{"a": 1,}'), {"a": 1})

    def test_nested_braces_and_strings(self):
        raw = '{"issue": "he said {weird}", "entities": [{"type": "amount", "value": "$20"}]}'
        self.assertEqual(extract_json(raw)["entities"][0]["value"], "$20")

    def test_empty_raises(self):
        with self.assertRaises(ValueError):
            extract_json("")

    def test_prose_only_raises(self):
        with self.assertRaises(ValueError):
            extract_json("I cannot help with that request.")


class TestSchemaRepair(unittest.TestCase):
    """The headline case from the brief: 'super-important' is not a valid priority."""

    base = {
        "category": "billing",
        "priority": "high",
        "sentiment": "negative",
        "issue": "duplicate charge",
        "suggested_action": "refund_one_payment",
        "requires_human": True,
        "draft_response": "We'll look into it.",
    }

    def _build(self, **overrides):
        return TicketAnalysis.model_validate({**self.base, **overrides})

    def test_super_important_maps_to_high(self):
        self.assertIs(self._build(priority="super-important").priority, Priority.HIGH)

    def test_capitalised_values(self):
        a = self._build(priority="High", category="Billing", sentiment="Negative")
        self.assertIs(a.priority, Priority.HIGH)
        self.assertIs(a.category, Category.BILLING)
        self.assertIs(a.sentiment, Sentiment.NEGATIVE)

    def test_priority_synonyms(self):
        for value, expected in [
            ("urgent", Priority.HIGH), ("P1", Priority.HIGH), ("critical", Priority.HIGH),
            ("normal", Priority.MEDIUM), ("moderate", Priority.MEDIUM),
            ("minor", Priority.LOW), ("trivial", Priority.LOW),
        ]:
            self.assertIs(self._build(priority=value).priority, expected, msg=value)

    def test_category_synonyms(self):
        self.assertIs(self._build(category="payment").category, Category.BILLING)
        self.assertIs(self._build(category="bug").category, Category.TECHNICAL)
        self.assertIs(self._build(category="login").category, Category.ACCOUNT)

    def test_sentiment_angry_is_negative(self):
        self.assertIs(self._build(sentiment="angry").sentiment, Sentiment.NEGATIVE)

    def test_requires_human_strings(self):
        self.assertTrue(self._build(requires_human="yes").requires_human)
        self.assertFalse(self._build(requires_human="no").requires_human)

    def test_confidence_percentage(self):
        self.assertAlmostEqual(self._build(confidence=85).confidence, 0.85)
        self.assertAlmostEqual(self._build(confidence="90%").confidence, 0.9)

    def test_entities_dict_shape(self):
        a = self._build(entities={"amount": "$20", "date": "Monday"})
        self.assertEqual({e.type for e in a.entities}, {"amount", "date"})

    def test_entities_list_of_scalars(self):
        a = self._build(entities=["$20", "Monday"])
        self.assertEqual(len(a.entities), 2)

    def test_action_maps_to_enum(self):
        """suggested_action is a closed set; loose values map onto it."""
        from support_platform.schemas import Action

        self.assertIs(self._build(suggested_action="Refund One Payment!").suggested_action,
                      Action.PROCESS_REFUND)

    def test_action_synonyms(self):
        """Real values the model produced when this field was free-form."""
        from support_platform.schemas import Action

        for given, expected in [
            ("request_more_details", Action.REQUEST_MORE_INFO),
            ("request_account_identifier", Action.REQUEST_MORE_INFO),
            ("respond_to_greeting", Action.ACKNOWLEDGE),
            ("greet_customer", Action.ACKNOWLEDGE),
            ("investigate_duplicate_charge", Action.INVESTIGATE_BILLING),
            ("escalate_to_engineering", Action.ESCALATE_TECHNICAL),
            ("escalate_to_human", Action.ROUTE_TO_HUMAN),
            ("close_ticket", Action.CLOSE_TICKET),
        ]:
            self.assertIs(self._build(suggested_action=given).suggested_action, expected, msg=given)

    def test_unknown_action_falls_back_to_human(self):
        """An action nobody anticipated is safe by default, not a repair round."""
        from support_platform.schemas import Action

        self.assertIs(
            self._build(suggested_action="do_something_nobody_expected").suggested_action,
            Action.ROUTE_TO_HUMAN,
        )

    def test_unmappable_priority_still_fails(self):
        """Genuinely nonsensical values must raise so the LLM layer can retry."""
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            self._build(priority="banana")

    def test_extra_fields_ignored(self):
        a = self._build(unexpected_field="whatever")
        self.assertIs(a.category, Category.BILLING)

    def test_language_defaults_to_english(self):
        self.assertEqual(self._build().language, "en")

    def test_language_normalisation(self):
        """Models return the language in whatever shape they feel like."""
        for given, expected in [
            ("ar", "ar"), ("AR", "ar"), ("en-US", "en"), ("fr_FR", "fr"),
            ("English", "en"), ("Arabic", "ar"), ("deutsch", "de"),
            (["es"], "es"), (None, "en"), ("", "en"), ("gibberish", "en"),
        ]:
            self.assertEqual(self._build(language=given).language, expected, msg=given)


class TestInputValidation(unittest.TestCase):
    def test_empty(self):
        self.assertIs(validate_message("").problem, InputProblem.EMPTY)

    def test_whitespace_only(self):
        self.assertIs(validate_message("   \n\t ").problem, InputProblem.EMPTY)

    def test_none(self):
        self.assertIs(validate_message(None).problem, InputProblem.EMPTY)

    def test_too_short(self):
        self.assertIs(validate_message("hi").problem, InputProblem.TOO_SHORT)

    def test_wrong_type(self):
        self.assertIs(validate_message({"body": "x"}).problem, InputProblem.MALFORMED)
        self.assertIs(validate_message(12345).problem, InputProblem.MALFORMED)

    def test_binary(self):
        self.assertIs(validate_message(b"\x00\x01\x02\xff\xfe").problem, InputProblem.NOT_TEXT)

    def test_valid_utf8_bytes_accepted(self):
        self.assertTrue(validate_message("I was charged twice".encode()).ok)

    def test_long_message_truncated_not_rejected(self):
        result = validate_message("My app crashes. " + ("log line. " * 5000))
        self.assertTrue(result.ok)
        self.assertTrue(result.truncated)
        self.assertLess(len(result.text), 10000)

    def test_foreign_language_is_accepted(self):
        """Language is no longer a gate: the model detects it and replies in it.

        Routing to a translator is a business decision in rules.py, applied once
        the language is actually known.
        """
        spanish = "Hola, me cobraron dos veces la suscripcion, por favor reembolso gracias."
        self.assertTrue(validate_message(spanish).ok)

    def test_english_passes(self):
        self.assertTrue(validate_message("I was charged twice for my subscription").ok)

    def test_control_chars_stripped(self):
        result = validate_message("I was charged\x00 twice for my subscription")
        self.assertTrue(result.ok)
        self.assertNotIn("\x00", result.text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
