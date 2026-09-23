"""Offline tests: no network, no model server.

Run with:  python3 -m unittest discover -s tests -v
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from doc_intel.parsing import DocFormat, ParseProblem, detect_format, parse_document  # noqa: E402
from doc_intel.schemas import (  # noqa: E402
    Currency,
    DocumentType,
    InvoiceExtraction,
    LineItem,
    parse_amount,
    parse_date,
)


class TestAmountParsing(unittest.TestCase):
    """Invoices write the same number a dozen different ways."""

    def test_plain_numbers(self):
        self.assertEqual(parse_amount(1392), 1392.0)
        self.assertEqual(parse_amount(1392.5), 1392.5)

    def test_currency_symbols_and_separators(self):
        self.assertEqual(parse_amount("$1,392.00"), 1392.0)
        self.assertEqual(parse_amount("USD 99.50"), 99.5)
        self.assertEqual(parse_amount("€1.392,00"), 1392.0)

    def test_european_decimal_comma(self):
        """1.392,00 means 1392.00, not 1.392."""
        self.assertEqual(parse_amount("1.392,00"), 1392.0)
        self.assertEqual(parse_amount("1,50"), 1.5)

    def test_thousands_comma(self):
        self.assertEqual(parse_amount("1,234"), 1234.0)
        self.assertEqual(parse_amount("1,234,567"), 1234567.0)

    def test_accounting_negative(self):
        self.assertEqual(parse_amount("(150.00)"), -150.0)

    def test_space_separator(self):
        self.assertEqual(parse_amount("1 392.00"), 1392.0)

    def test_unparseable_returns_none(self):
        """None means 'absent', which is different from zero."""
        for value in ("", "   ", "abc", None, "n/a"):
            self.assertIsNone(parse_amount(value), msg=repr(value))

    def test_bool_is_not_an_amount(self):
        """bool is an int subclass; True must not become 1.0."""
        self.assertIsNone(parse_amount(True))


class TestDateParsing(unittest.TestCase):
    def test_iso_passthrough(self):
        self.assertEqual(parse_date("2026-09-10"), "2026-09-10")

    def test_common_formats(self):
        for value in ("10/09/2026", "10-09-2026", "10.09.2026", "Sep 10, 2026", "10 September 2026"):
            self.assertEqual(parse_date(value), "2026-09-10", msg=value)

    def test_unparseable_returns_none(self):
        """Never invent a date -- an absent date is recoverable, a wrong one is not."""
        for value in ("garbage", "", None, "13/13/2026"):
            self.assertIsNone(parse_date(value), msg=repr(value))


class TestCurrencyNormalisation(unittest.TestCase):
    def _currency(self, value):
        return InvoiceExtraction(currency=value).currency

    def test_iso_codes(self):
        self.assertIs(self._currency("USD"), Currency.USD)
        self.assertIs(self._currency("usd"), Currency.USD)

    def test_symbols(self):
        self.assertIs(self._currency("$"), Currency.USD)
        self.assertIs(self._currency("€"), Currency.EUR)
        self.assertIs(self._currency("£"), Currency.GBP)

    def test_embedded_code(self):
        self.assertIs(self._currency("1,392.00 USD"), Currency.USD)

    def test_unknown_is_honest(self):
        for value in ("", "none", "n/a", None, "wibble"):
            self.assertIs(self._currency(value), Currency.UNKNOWN, msg=repr(value))


class TestLineItems(unittest.TestCase):
    def test_amount_derived_from_quantity_and_price(self):
        """Arithmetic in code beats asking the model to multiply."""
        item = LineItem(description="Widget", quantity=40, unit_price=12.5)
        self.assertEqual(item.amount, 500.0)

    def test_explicit_amount_is_not_overwritten(self):
        item = LineItem(description="W", quantity=2, unit_price=10, amount=999)
        self.assertEqual(item.amount, 999.0)

    def test_dict_shape_accepted(self):
        inv = InvoiceExtraction(items={"Widget": 100, "Support": 200})
        self.assertEqual(len(inv.items), 2)
        self.assertEqual(inv.items_sum, 300.0)

    def test_list_of_strings_accepted(self):
        inv = InvoiceExtraction(items=["Widget", "Support"])
        self.assertEqual(len(inv.items), 2)

    def test_items_sum_ignores_missing_amounts(self):
        inv = InvoiceExtraction(items=[{"description": "a", "amount": 10}, {"description": "b"}])
        self.assertEqual(inv.items_sum, 10.0)

    def test_items_sum_none_when_no_amounts(self):
        inv = InvoiceExtraction(items=[{"description": "a"}])
        self.assertIsNone(inv.items_sum)


class TestFormatDetection(unittest.TestCase):
    """Detect by content: an uploader can name a PNG 'invoice.pdf'."""

    def test_pdf_magic_bytes(self):
        self.assertIs(detect_format(b"%PDF-1.7 ...", "x.pdf"), DocFormat.PDF)

    def test_png_named_as_pdf(self):
        self.assertIs(
            detect_format(b"\x89PNG\r\n\x1a\n" + b"\x00" * 20, "invoice.pdf"),
            DocFormat.IMAGE,
        )

    def test_jpeg(self):
        self.assertIs(detect_format(b"\xff\xd8\xff\xe0" + b"\x00" * 20, "x.jpg"), DocFormat.IMAGE)

    def test_plain_text(self):
        self.assertIs(detect_format(b"INVOICE\nTotal: 100", "x.txt"), DocFormat.TEXT)

    def test_binary_is_unknown(self):
        self.assertIs(detect_format(b"\x00\x01\x02\xff\xfe", "x.bin"), DocFormat.UNKNOWN)


class TestDocumentParsing(unittest.TestCase):
    def test_empty_file(self):
        self.assertIs(parse_document(b"", "x.pdf").problem, ParseProblem.EMPTY_FILE)

    def test_oversize_file(self):
        from doc_intel.config import settings

        oversized = b"x" * (settings.max_file_bytes + 1)
        self.assertIs(parse_document(oversized, "x.txt").problem, ParseProblem.TOO_LARGE)

    def test_corrupt_pdf(self):
        result = parse_document(b"%PDF-1.4 this is not really a pdf", "x.pdf")
        self.assertFalse(result.ok)
        self.assertIs(result.problem, ParseProblem.CORRUPT)

    def test_unsupported_type(self):
        self.assertIs(
            parse_document(b"\x00\x01\x02\xff", "x.bin").problem,
            ParseProblem.UNSUPPORTED_FORMAT,
        )

    def test_too_little_text(self):
        self.assertIs(parse_document(b"hi", "x.txt").problem, ParseProblem.TOO_LITTLE_TEXT)

    def test_valid_text_document(self):
        data = b"INVOICE INV-1\nVendor: ACME Ltd\nTotal: $100.00\nDate: 2026-01-01"
        result = parse_document(data, "invoice.txt")
        self.assertTrue(result.ok)
        self.assertIn("INV-1", result.text)

    def test_long_document_keeps_head_and_tail(self):
        """Invoice totals live at the END -- truncation must not drop them."""
        from doc_intel.config import settings

        body = "line of text " * 5000
        data = f"INVOICE START\n{body}\nTOTAL: 1392.00".encode()
        result = parse_document(data, "x.txt")
        self.assertTrue(result.ok)
        self.assertTrue(result.truncated)
        self.assertIn("INVOICE START", result.text)
        self.assertIn("TOTAL: 1392.00", result.text)
        self.assertLess(len(result.text), settings.max_text_chars + 200)


class TestDocumentType(unittest.TestCase):
    def test_non_invoice_can_be_reported(self):
        """A CV must come back as 'other', not an invoice with empty fields."""
        inv = InvoiceExtraction(document_type="other", vendor="Jane Doe")
        self.assertIs(inv.document_type, DocumentType.OTHER)


class TestOCRFlag(unittest.TestCase):
    """The ``ocr`` flag is how downstream checks know the text is lossy."""

    def test_text_documents_are_not_ocr(self):
        data = b"INVOICE INV-1\nVendor: ACME Ltd\nTotal: $100.00\nDate: 2026-01-01"
        self.assertFalse(parse_document(data, "invoice.txt").ocr)

    def test_image_without_ocr_reports_clearly(self):
        """Without tesseract, an image must fail loudly rather than return ''.

        Silently returning empty text would let the model invent an entire
        invoice -- the worst possible outcome for a financial document.
        """
        try:
            import pytesseract  # noqa: F401
        except ImportError:
            result = parse_document(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100, "scan.png")
            self.assertFalse(result.ok)
            self.assertIsNotNone(result.problem)


class TestOCRLanguages(unittest.TestCase):
    """Regression: the wrong language pack yields confident gibberish.

    Tesseract ships with English only. Given an Arabic invoice it mapped the
    script onto the Latin alphabet and returned ``'JI6 Jus JJes sole'`` with
    ``ok=True`` -- 217 characters of meaningless text that the extractor would
    happily have turned into an invented invoice.
    """

    SAMPLE = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "samples", "invoice_arabic.png",
    )

    def setUp(self):
        try:
            import pytesseract  # noqa: F401
        except ImportError:
            self.skipTest("pytesseract not installed")
        if not os.path.exists(self.SAMPLE):
            self.skipTest("arabic sample not generated")

    def test_arabic_is_read_when_the_pack_is_configured(self):
        from doc_intel.config import settings

        if "ara" not in settings.ocr_languages:
            self.skipTest("arabic pack not configured")
        result = parse_document(open(self.SAMPLE, "rb").read(), "arabic.png")
        self.assertTrue(result.ok)
        # The invoice number is Latin text inside an Arabic document.
        self.assertIn("INV-99120", result.text)

    def test_confidence_is_reported_for_ocr(self):
        result = parse_document(open(self.SAMPLE, "rb").read(), "arabic.png")
        self.assertGreater(result.ocr_confidence, 0.0)

    def test_wrong_language_pack_is_rejected(self):
        """The whole point: gibberish must not pass as a successful read."""
        import doc_intel.parsing as parsing
        from doc_intel.config import settings

        original = settings.ocr_languages
        object.__setattr__(settings, "ocr_languages", "eng")
        try:
            result = parsing.parse_document(open(self.SAMPLE, "rb").read(), "arabic.png")
            self.assertFalse(result.ok, "Arabic read as English must not succeed")
            self.assertIs(result.problem, ParseProblem.OCR_UNREADABLE)
            self.assertLess(result.ocr_confidence, 0.55)
        finally:
            object.__setattr__(settings, "ocr_languages", original)


if __name__ == "__main__":
    unittest.main(verbosity=2)
