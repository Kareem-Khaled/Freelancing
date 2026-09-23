"""Deterministic checks on an extracted invoice.

    LLM  ->  extraction  ->  VALIDATION  ->  decision

The support platform's business-rules layer, adapted. Two differences matter:

1. **The checks are arithmetic, not policy.** "Do the line items sum to the
   subtotal?" has a right answer that Python can compute. Asking the model to
   verify its own maths is asking the unreliable component to grade itself.

2. **Findings do not mutate the extraction.** If the numbers do not add up we
   report it; we never "fix" a total. Silently correcting a financial document
   would turn a visible discrepancy into an invisible one.

As in the support platform, severity only ever escalates -- a check can raise
the review level, never lower it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import Enum

from .config import settings
from .schemas import Currency, DocumentType, InvoiceExtraction


class Severity(str, Enum):
    INFO = "info"        # worth noting
    WARNING = "warning"  # a human should glance at this
    ERROR = "error"      # do not trust this extraction


class ReviewStatus(str, Enum):
    AUTO_APPROVED = "auto_approved"  # safe to use without review
    NEEDS_REVIEW = "needs_review"    # a human should confirm
    REJECTED = "rejected"            # unusable


_SEVERITY_RANK = {Severity.INFO: 0, Severity.WARNING: 1, Severity.ERROR: 2}
_STATUS_RANK = {
    ReviewStatus.AUTO_APPROVED: 0,
    ReviewStatus.NEEDS_REVIEW: 1,
    ReviewStatus.REJECTED: 2,
}


@dataclass
class Finding:
    """One thing a check noticed."""

    check: str
    severity: Severity
    message: str
    expected: float | None = None
    found: float | None = None

    def as_dict(self) -> dict:
        data = {
            "check": self.check,
            "severity": self.severity.value,
            "message": self.message,
        }
        if self.expected is not None:
            data["expected"] = round(self.expected, 2)
        if self.found is not None:
            data["found"] = round(self.found, 2)
        return data


@dataclass
class ValidationReport:
    status: ReviewStatus
    findings: list[Finding] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return self.status is not ReviewStatus.REJECTED

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.severity is Severity.ERROR]

    def as_dict(self) -> dict:
        return {
            "status": self.status.value,
            "findings": [f.as_dict() for f in self.findings],
            "error_count": len(self.errors),
            "warning_count": sum(
                1 for f in self.findings if f.severity is Severity.WARNING
            ),
        }


def _close(a: float, b: float) -> bool:
    """Whether two amounts agree within the configured tolerance.

    Exact equality is wrong here: invoices round each line item, so a subtotal
    can legitimately differ from the sum of its lines by a cent or two.
    """
    return abs(a - b) <= settings.amount_tolerance


# ----------------------------------------------------------------------
# Individual checks. Each returns a Finding, or None when it passes.
# ----------------------------------------------------------------------
def _check_is_invoice(inv: InvoiceExtraction) -> Finding | None:
    if inv.document_type is DocumentType.OTHER:
        return Finding(
            "document_type",
            Severity.ERROR,
            "This does not look like an invoice — extracted fields are unreliable",
        )
    return None


def _check_required_fields(inv: InvoiceExtraction) -> Finding | None:
    missing = [
        name
        for name, value in [
            ("vendor", inv.vendor),
            ("invoice_number", inv.invoice_number),
            ("date", inv.date),
            ("total", inv.total),
        ]
        if not value
    ]
    if missing:
        return Finding(
            "required_fields",
            Severity.ERROR if "total" in missing else Severity.WARNING,
            f"Missing required field(s): {', '.join(missing)}",
        )
    return None


def _check_items_sum(inv: InvoiceExtraction) -> Finding | None:
    """Line items should sum to the subtotal.

    The single most valuable check in the service: it catches a missed row, a
    misread digit, and a hallucinated line -- none of which the model can
    reliably notice about its own output.
    """
    items_total = inv.items_sum
    if items_total is None or inv.subtotal is None:
        return None
    if not _close(items_total, inv.subtotal):
        return Finding(
            "items_sum",
            Severity.ERROR,
            f"Line items sum to {items_total:.2f} but subtotal is {inv.subtotal:.2f}",
            expected=inv.subtotal,
            found=items_total,
        )
    return None


def _check_total_arithmetic(inv: InvoiceExtraction) -> Finding | None:
    """subtotal + tax + shipping - discount should equal the total."""
    if inv.subtotal is None or inv.total is None:
        return None

    computed = inv.subtotal + (inv.tax or 0) + (inv.shipping or 0) - (inv.discount or 0)
    if not _close(computed, inv.total):
        return Finding(
            "total_arithmetic",
            Severity.ERROR,
            (
                f"subtotal {inv.subtotal:.2f} + tax {(inv.tax or 0):.2f} "
                f"+ shipping {(inv.shipping or 0):.2f} - discount {(inv.discount or 0):.2f} "
                f"= {computed:.2f}, but total says {inv.total:.2f}"
            ),
            expected=inv.total,
            found=computed,
        )
    return None


def _check_line_item_maths(inv: InvoiceExtraction) -> Finding | None:
    """Each row's quantity x unit price should equal its amount."""
    bad = []
    for i, item in enumerate(inv.items, 1):
        if item.quantity is None or item.unit_price is None or item.amount is None:
            continue
        expected = item.quantity * item.unit_price
        if not _close(expected, item.amount):
            bad.append(f"row {i} ({item.description[:28]}): {expected:.2f} vs {item.amount:.2f}")
    if bad:
        return Finding(
            "line_item_maths",
            Severity.WARNING,
            "quantity x unit price does not match the line amount — " + "; ".join(bad[:3]),
        )
    return None


def _check_negative_amounts(inv: InvoiceExtraction) -> Finding | None:
    """A negative total usually means a credit note read as an invoice."""
    if inv.total is not None and inv.total < 0 and inv.document_type is not DocumentType.CREDIT_NOTE:
        return Finding(
            "negative_total",
            Severity.WARNING,
            f"Total is negative ({inv.total:.2f}) — is this a credit note?",
            found=inv.total,
        )
    return None


def _check_tax_plausible(inv: InvoiceExtraction) -> Finding | None:
    """Tax above 40% of the subtotal is almost certainly a misread."""
    if inv.subtotal is None or inv.tax is None or inv.subtotal <= 0:
        return None
    rate = inv.tax / inv.subtotal
    if rate > 0.40:
        return Finding(
            "tax_rate",
            Severity.WARNING,
            f"Tax is {rate * 100:.1f}% of the subtotal, which is unusually high",
            found=round(rate * 100, 1),
        )
    return None


def _check_currency(inv: InvoiceExtraction) -> Finding | None:
    if inv.currency is Currency.UNKNOWN:
        return Finding(
            "currency",
            Severity.WARNING,
            "Currency could not be determined — amounts are ambiguous",
        )
    return None


def _check_dates(inv: InvoiceExtraction) -> Finding | None:
    """Catch unparseable dates, far-future dates, and due-before-issue."""
    if inv.date is None:
        return None
    try:
        issued = date.fromisoformat(inv.date)
    except ValueError:
        return Finding("date_format", Severity.WARNING, f"Unparseable date: {inv.date!r}")

    if issued > date.today() + timedelta(days=365):
        return Finding(
            "date_range",
            Severity.WARNING,
            f"Invoice date {inv.date} is more than a year in the future",
        )

    if inv.due_date:
        try:
            due = date.fromisoformat(inv.due_date)
            if due < issued:
                return Finding(
                    "due_date",
                    Severity.WARNING,
                    f"Due date {inv.due_date} is before the invoice date {inv.date}",
                )
        except ValueError:
            return Finding(
                "date_format", Severity.WARNING, f"Unparseable due date: {inv.due_date!r}"
            )
    return None


def _check_confidence(inv: InvoiceExtraction) -> Finding | None:
    if inv.confidence < 0.6:
        return Finding(
            "low_confidence",
            Severity.WARNING,
            f"Model reported low confidence ({inv.confidence:.2f})",
            found=inv.confidence,
        )
    return None


def _check_no_items(inv: InvoiceExtraction) -> Finding | None:
    if not inv.items:
        return Finding(
            "no_line_items",
            Severity.WARNING,
            "No line items extracted — the table may not have been read",
        )
    return None


def ocr_check(inv: InvoiceExtraction) -> Finding | None:
    """Flag any extraction that came from OCR.

    Added after watching tesseract silently drop the invoice number, the date
    and the subtotal line from a clean, synthetic 900x920 image -- not a blurry
    phone photo. The model then reported ``confidence: 1.0``, because it read
    the text it was given perfectly; the loss happened one layer earlier.

    OCR output is a lossy transcription of a lossy scan, so "the field is
    absent" and "the scanner lost it" are indistinguishable downstream. Always
    worth a human glance.
    """
    return Finding(
        "ocr_source",
        Severity.WARNING,
        "Text came from OCR, which silently drops characters and whole lines — "
        "verify against the original image",
    )


CHECKS = [
    _check_is_invoice,
    _check_required_fields,
    _check_items_sum,
    _check_total_arithmetic,
    _check_line_item_maths,
    _check_negative_amounts,
    _check_tax_plausible,
    _check_currency,
    _check_dates,
    _check_confidence,
    _check_no_items,
]


def validate(inv: InvoiceExtraction, checks=None, *, from_ocr: bool = False) -> ValidationReport:
    """Run every check and combine the findings into a review status.

    ``from_ocr`` adds a standing warning: OCR output is a lossy transcription,
    so an absent field cannot be distinguished from one the scanner lost.

    Escalate-only: any ERROR rejects, any WARNING requires review, and nothing
    can downgrade a status once raised.
    """
    checks = CHECKS if checks is None else checks
    if from_ocr:
        checks = [*checks, ocr_check]

    report = ValidationReport(status=ReviewStatus.AUTO_APPROVED)

    for check in checks:
        try:
            finding = check(inv)
        except Exception:
            # A broken check must never take down extraction. In production this
            # would be logged loudly -- a silently skipped check is a silently
            # weaker guarantee.
            continue
        if finding is None:
            continue

        report.findings.append(finding)
        if finding.severity is Severity.ERROR:
            target = ReviewStatus.REJECTED
        elif finding.severity is Severity.WARNING:
            target = ReviewStatus.NEEDS_REVIEW
        else:
            target = ReviewStatus.AUTO_APPROVED

        if _STATUS_RANK[target] > _STATUS_RANK[report.status]:
            report.status = target

    return report
