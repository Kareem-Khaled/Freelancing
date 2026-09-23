"""Tests for the deterministic validation layer.

The most important tests in the project: they assert arithmetic that must hold
regardless of how confident the model was.
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from doc_intel.schemas import InvoiceExtraction  # noqa: E402
from doc_intel.validation import ReviewStatus, Severity, validate  # noqa: E402


def invoice(**overrides) -> InvoiceExtraction:
    base = {
        "document_type": "invoice",
        "vendor": "ACME Supplies Ltd",
        "invoice_number": "INV-10932",
        "date": "2026-09-10",
        "currency": "USD",
        "subtotal": 1200.0,
        "tax": 192.0,
        "total": 1392.0,
        "items": [
            {"description": "Steel brackets", "quantity": 40, "unit_price": 12.5, "amount": 500.0},
            {"description": "Mounting plates", "quantity": 25, "unit_price": 18.0, "amount": 450.0},
            {"description": "Delivery", "quantity": 1, "unit_price": 250.0, "amount": 250.0},
        ],
        "confidence": 0.95,
    }
    base.update(overrides)
    return InvoiceExtraction.model_validate(base)


class TestCleanInvoice(unittest.TestCase):
    def test_correct_invoice_is_auto_approved(self):
        report = validate(invoice())
        self.assertIs(report.status, ReviewStatus.AUTO_APPROVED)
        self.assertEqual(report.findings, [])


class TestArithmetic(unittest.TestCase):
    """The core value of the service: catching maths the model cannot check."""

    def test_line_items_must_sum_to_subtotal(self):
        bad = invoice(items=[{"description": "One", "amount": 100.0}])
        report = validate(bad)
        self.assertIs(report.status, ReviewStatus.REJECTED)
        self.assertTrue(any(f.check == "items_sum" for f in report.findings))

    def test_subtotal_plus_tax_must_equal_total(self):
        report = validate(invoice(total=9999.0))
        self.assertIs(report.status, ReviewStatus.REJECTED)
        finding = next(f for f in report.findings if f.check == "total_arithmetic")
        self.assertIs(finding.severity, Severity.ERROR)

    def test_shipping_and_discount_are_included(self):
        ok = invoice(subtotal=1000.0, tax=100.0, shipping=50.0, discount=25.0, total=1125.0,
                     items=[{"description": "x", "amount": 1000.0}])
        self.assertIs(validate(ok).status, ReviewStatus.AUTO_APPROVED)

    def test_rounding_tolerance(self):
        """Invoices round line items; a one-cent gap is not an error."""
        near = invoice(subtotal=1200.01, total=1392.01)
        self.assertIs(validate(near).status, ReviewStatus.AUTO_APPROVED)

    def test_line_item_multiplication_checked(self):
        bad = invoice(items=[
            {"description": "Widget", "quantity": 10, "unit_price": 5.0, "amount": 999.0},
        ], subtotal=999.0, tax=0.0, total=999.0)
        report = validate(bad)
        self.assertTrue(any(f.check == "line_item_maths" for f in report.findings))

    def test_missing_numbers_do_not_crash_the_checks(self):
        """A half-read invoice must produce findings, not an exception."""
        report = validate(invoice(subtotal=None, tax=None, total=None, items=[]))
        self.assertIsNotNone(report.status)


class TestRequiredFields(unittest.TestCase):
    def test_missing_total_is_an_error(self):
        report = validate(invoice(total=None))
        self.assertIs(report.status, ReviewStatus.REJECTED)

    def test_missing_vendor_is_a_warning(self):
        report = validate(invoice(vendor=""))
        self.assertIs(report.status, ReviewStatus.NEEDS_REVIEW)

    def test_non_invoice_is_rejected(self):
        """A CV extracted as an invoice must never be auto-approved."""
        report = validate(invoice(document_type="other"))
        self.assertIs(report.status, ReviewStatus.REJECTED)
        self.assertTrue(any(f.check == "document_type" for f in report.findings))


class TestPlausibility(unittest.TestCase):
    def test_implausible_tax_rate_flagged(self):
        report = validate(invoice(subtotal=100.0, tax=90.0, total=190.0,
                                  items=[{"description": "x", "amount": 100.0}]))
        self.assertTrue(any(f.check == "tax_rate" for f in report.findings))

    def test_negative_total_flagged(self):
        report = validate(invoice(subtotal=-1200.0, total=-1392.0,
                                  items=[{"description": "x", "amount": -1200.0}]))
        self.assertTrue(any(f.check == "negative_total" for f in report.findings))

    def test_credit_note_may_be_negative(self):
        report = validate(invoice(document_type="credit_note", subtotal=-1200.0,
                                  total=-1392.0, items=[{"description": "x", "amount": -1200.0}]))
        self.assertFalse(any(f.check == "negative_total" for f in report.findings))

    def test_unknown_currency_flagged(self):
        report = validate(invoice(currency="wibble"))
        self.assertTrue(any(f.check == "currency" for f in report.findings))

    def test_due_before_issue_flagged(self):
        report = validate(invoice(date="2026-09-10", due_date="2026-08-01"))
        self.assertTrue(any(f.check == "due_date" for f in report.findings))

    def test_low_confidence_flagged(self):
        report = validate(invoice(confidence=0.3))
        self.assertTrue(any(f.check == "low_confidence" for f in report.findings))

    def test_no_line_items_flagged(self):
        report = validate(invoice(items=[], subtotal=None))
        self.assertTrue(any(f.check == "no_line_items" for f in report.findings))


class TestEscalationOnly(unittest.TestCase):
    """Severity may rise but never fall, as in the support platform's rules."""

    def test_error_rejects_even_alongside_warnings(self):
        report = validate(invoice(total=9999.0, currency="wibble", confidence=0.2))
        self.assertIs(report.status, ReviewStatus.REJECTED)

    def test_warning_alone_needs_review(self):
        self.assertIs(validate(invoice(confidence=0.3)).status, ReviewStatus.NEEDS_REVIEW)

    def test_broken_check_does_not_break_validation(self):
        def exploding(_inv):
            raise RuntimeError("boom")

        from doc_intel.validation import CHECKS

        report = validate(invoice(), checks=[exploding, *CHECKS])
        self.assertIs(report.status, ReviewStatus.AUTO_APPROVED)

    def test_validation_never_mutates_the_extraction(self):
        """Findings are reported; a wrong total is never silently 'fixed'."""
        inv = invoice(total=9999.0)
        validate(inv)
        self.assertEqual(inv.total, 9999.0)


class TestOCRAwareness(unittest.TestCase):
    """OCR output is a lossy transcription and must never be auto-approved.

    Observed with tesseract on a clean, synthetic 900x920 invoice image -- not a
    blurry phone photo: the invoice number, the date and the subtotal line were
    silently dropped. The model then reported confidence 1.0, because it read
    the text it was given perfectly. The loss happened one layer earlier, which
    is exactly why the flag lives in parsing and not in the prompt.
    """

    def test_ocr_source_is_flagged(self):
        report = validate(invoice(), from_ocr=True)
        self.assertTrue(any(f.check == "ocr_source" for f in report.findings))

    def test_perfect_ocr_invoice_still_needs_review(self):
        """Even an arithmetically flawless OCR extraction gets a human glance."""
        report = validate(invoice(), from_ocr=True)
        self.assertIs(report.status, ReviewStatus.NEEDS_REVIEW)

    def test_non_ocr_invoice_is_unaffected(self):
        report = validate(invoice(), from_ocr=False)
        self.assertIs(report.status, ReviewStatus.AUTO_APPROVED)
        self.assertFalse(any(f.check == "ocr_source" for f in report.findings))

    def test_ocr_does_not_mask_real_errors(self):
        """A warning must not downgrade an error."""
        report = validate(invoice(total=9999.0), from_ocr=True)
        self.assertIs(report.status, ReviewStatus.REJECTED)


class TestSettingsCompleteness(unittest.TestCase):
    """Regression: a missing settings field silently emptied the metrics table.

    ``CallMetrics.cost_usd`` reads two settings that were not ported from the
    support platform. ``_flush_calls`` caught the AttributeError with a bare
    ``except: pass``, so every save failed and the dashboard reported zero calls
    while extraction appeared to work perfectly.
    """

    def test_cost_fields_exist(self):
        from doc_intel.config import settings

        self.assertIsInstance(settings.cost_per_1k_input, float)
        self.assertIsInstance(settings.cost_per_1k_output, float)

    def test_call_metrics_cost_is_computable(self):
        from doc_intel.telemetry import CallMetrics

        record = CallMetrics(
            request_id="r", operation="extract", model="m", attempt=1,
            prompt_tokens=1000, completion_tokens=500,
        )
        self.assertIsInstance(record.cost_usd, float)

    def test_metrics_persist_to_the_database(self):
        import os
        import tempfile

        from doc_intel.storage import Database
        from doc_intel.telemetry import CallMetrics

        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        try:
            db = Database(tmp.name)
            db.save_call(
                CallMetrics(
                    request_id="r1", operation="extract", model="m",
                    attempt=1, success=True, ticket_id="DOC-1",
                )
            )
            self.assertEqual(db.metrics_summary()["calls"], 1)
        finally:
            os.unlink(tmp.name)


if __name__ == "__main__":
    unittest.main(verbosity=2)
