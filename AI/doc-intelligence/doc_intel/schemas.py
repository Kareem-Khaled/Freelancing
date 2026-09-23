"""Extraction contract for invoices.

The support platform's lesson applies directly: normalise what is unambiguous,
fail on what is genuinely uncertain, and make the failure message good enough
that the retry can succeed.

Invoices add a wrinkle tickets did not have -- **numbers**. A model reading
"$1,392.00" may return ``"$1,392.00"``, ``"1392.00"``, ``1392`` or ``"1.392,00"``
(European format). All four mean the same thing, so all four are repaired here
rather than costing a retry. What is NOT repaired is arithmetic: if the line
items do not sum to the subtotal, that is a finding for ``validation.py``, not
something to quietly "fix".
"""

from __future__ import annotations

import re
from datetime import date
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

__all__ = [
    "Currency",
    "DocumentType",
    "LineItem",
    "InvoiceExtraction",
    "schema_hint",
]


class DocumentType(str, Enum):
    """What kind of document this turned out to be.

    ``OTHER`` matters: a service that only knows how to say "invoice" will
    confidently extract invoice fields from a CV. Naming the alternative gives
    the model somewhere honest to put a non-invoice.
    """

    INVOICE = "invoice"
    RECEIPT = "receipt"
    PURCHASE_ORDER = "purchase_order"
    CREDIT_NOTE = "credit_note"
    OTHER = "other"


class Currency(str, Enum):
    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"
    AED = "AED"
    SAR = "SAR"
    EGP = "EGP"
    JPY = "JPY"
    CAD = "CAD"
    AUD = "AUD"
    CHF = "CHF"
    INR = "INR"
    UNKNOWN = "UNKNOWN"


# Symbols and loose spellings a model returns instead of an ISO code.
_CURRENCY_SYNONYMS = {
    "$": Currency.USD, "us$": Currency.USD, "usd$": Currency.USD,
    "dollar": Currency.USD, "dollars": Currency.USD, "usdollar": Currency.USD,
    "€": Currency.EUR, "euro": Currency.EUR, "euros": Currency.EUR,
    "£": Currency.GBP, "pound": Currency.GBP, "pounds": Currency.GBP,
    "sterling": Currency.GBP, "gbp£": Currency.GBP,
    "aed": Currency.AED, "dirham": Currency.AED, "dhs": Currency.AED,
    "sar": Currency.SAR, "riyal": Currency.SAR, "sr": Currency.SAR,
    "egp": Currency.EGP, "le": Currency.EGP,
    "¥": Currency.JPY, "yen": Currency.JPY,
    "₹": Currency.INR, "rupee": Currency.INR, "rs": Currency.INR,
    "c$": Currency.CAD, "cad$": Currency.CAD,
    "a$": Currency.AUD, "aud$": Currency.AUD,
    "": Currency.UNKNOWN, "none": Currency.UNKNOWN, "n/a": Currency.UNKNOWN,
}

_CURRENCY_IN_TEXT = re.compile(
    r"\b(USD|EUR|GBP|AED|SAR|EGP|JPY|CAD|AUD|CHF|INR)\b", re.I
)


def parse_amount(value: Any) -> float | None:
    """Turn whatever the model returned into a float, or ``None``.

    Handles the formats that actually appear on invoices::

        "$1,392.00"   -> 1392.0     currency symbols and thousands separators
        "1.392,00"    -> 1392.0     European decimal comma
        "(150.00)"    -> -150.0     accounting negative
        "1 392.00"    -> 1392.0     space as separator
        1392          -> 1392.0     already a number

    Returns ``None`` rather than guessing when the text has no digits, so the
    caller can decide whether the field was genuinely absent.
    """
    if value is None:
        return None
    if isinstance(value, bool):  # bool is an int subclass; never an amount
        return None
    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip()
    if not text:
        return None

    negative = text.startswith("(") and text.endswith(")")
    # Keep digits, separators and a leading minus; drop symbols and letters.
    cleaned = re.sub(r"[^\d,.\-]", "", text)
    if not re.search(r"\d", cleaned):
        return None

    if "," in cleaned and "." in cleaned:
        # Whichever separator comes last is the decimal point.
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif "," in cleaned:
        parts = cleaned.split(",")
        # "1,50" is a decimal comma; "1,234" and "1,234,567" are separators.
        if len(parts) == 2 and len(parts[-1]) in (1, 2):
            cleaned = cleaned.replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")

    try:
        amount = float(cleaned)
    except ValueError:
        return None
    return -abs(amount) if negative else amount


# Date formats seen on invoices, most specific first. ISO is tried first so an
# unambiguous value is never reinterpreted.
_DATE_FORMATS = [
    "%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%m-%d-%Y",
    "%d.%m.%Y", "%d %B %Y", "%d %b %Y", "%B %d, %Y", "%b %d, %Y",
    "%d/%m/%y", "%m/%d/%y", "%Y%m%d",
]


def parse_date(value: Any) -> str | None:
    """Normalise a date to ISO ``YYYY-MM-DD``, or ``None`` if unparseable.

    Ambiguity is real here: ``03/04/2026`` is 3 April in most of the world and
    4 March in the US. We try day-first before month-first, and record nothing
    when neither works rather than inventing a date.
    """
    if value is None:
        return None
    if isinstance(value, date):
        return value.isoformat()

    text = str(value).strip()
    if not text:
        return None

    from datetime import datetime

    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return None


class LineItem(BaseModel):
    """One row from the invoice table."""

    description: str = Field(default="", description="What was billed")
    quantity: float | None = Field(default=None)
    unit_price: float | None = Field(default=None)
    amount: float | None = Field(default=None, description="Line total")

    @field_validator("quantity", "unit_price", "amount", mode="before")
    @classmethod
    def _parse_numbers(cls, v: Any) -> float | None:
        return parse_amount(v)

    @field_validator("description", mode="before")
    @classmethod
    def _clean_description(cls, v: Any) -> str:
        if v is None:
            return ""
        if isinstance(v, (list, tuple)):
            v = " ".join(str(item) for item in v)
        return " ".join(str(v).split())

    @model_validator(mode="after")
    def _fill_missing_amount(self) -> "LineItem":
        """Derive the line total when only quantity and unit price are given.

        This is arithmetic, not a guess -- the model often reads the columns but
        omits the computed total. Deriving it in code is more reliable than
        asking the model to multiply.
        """
        if self.amount is None and self.quantity is not None and self.unit_price is not None:
            object.__setattr__(self, "amount", round(self.quantity * self.unit_price, 2))
        return self


class InvoiceExtraction(BaseModel):
    """Structured invoice data. The contract the API returns."""

    model_config = {"extra": "ignore"}

    document_type: DocumentType = Field(default=DocumentType.INVOICE)
    vendor: str = Field(default="", description="Who issued the invoice")
    vendor_address: str = Field(default="")
    bill_to: str = Field(default="", description="Who is being billed")
    invoice_number: str = Field(default="")
    purchase_order: str = Field(default="")
    date: str | None = Field(default=None, description="ISO YYYY-MM-DD")
    due_date: str | None = Field(default=None)
    currency: Currency = Field(default=Currency.UNKNOWN)
    subtotal: float | None = Field(default=None)
    tax: float | None = Field(default=None)
    shipping: float | None = Field(default=None)
    discount: float | None = Field(default=None)
    total: float | None = Field(default=None)
    items: list[LineItem] = Field(default_factory=list)
    # The model's own view of how well it read the document. Low confidence is a
    # useful routing signal even when every field happens to be populated.
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    notes: str = Field(default="", description="Anything unclear or unreadable")

    # -- normalisation ------------------------------------------------
    @field_validator(
        "subtotal", "tax", "shipping", "discount", "total", mode="before"
    )
    @classmethod
    def _parse_amounts(cls, v: Any) -> float | None:
        return parse_amount(v)

    @field_validator("date", "due_date", mode="before")
    @classmethod
    def _parse_dates(cls, v: Any) -> str | None:
        return parse_date(v)

    @field_validator("currency", mode="before")
    @classmethod
    def _parse_currency(cls, v: Any) -> Any:
        """Map a symbol or loose spelling onto an ISO code."""
        if isinstance(v, Currency) or v is None:
            return Currency.UNKNOWN if v is None else v
        text = str(v).strip()
        if not text:
            return Currency.UNKNOWN

        upper = text.upper()
        for member in Currency:
            if member.value == upper:
                return member

        slug = "".join(ch for ch in text.lower() if not ch.isspace())
        if slug in _CURRENCY_SYNONYMS:
            return _CURRENCY_SYNONYMS[slug]

        # "1,392.00 USD" -- the code is embedded in a longer string.
        match = _CURRENCY_IN_TEXT.search(text)
        if match:
            return Currency(match.group(1).upper())

        # Symbols may be adjacent to the amount ("$1,392.00"), so a substring
        # check is needed -- but ONLY for symbols. Matching alphabetic synonyms
        # this way turned "wibble" into EGP via the "le" abbreviation, which is
        # exactly the kind of confident-but-wrong answer the service must avoid.
        for symbol, member in _CURRENCY_SYNONYMS.items():
            if symbol and not symbol.isalnum() and symbol in text:
                return member
        return Currency.UNKNOWN

    @field_validator(
        "vendor", "vendor_address", "bill_to", "invoice_number",
        "purchase_order", "notes",
        mode="before",
    )
    @classmethod
    def _clean_text(cls, v: Any) -> str:
        if v is None:
            return ""
        if isinstance(v, (list, tuple)):
            v = " ".join(str(item) for item in v)
        return " ".join(str(v).split())

    @field_validator("confidence", mode="before")
    @classmethod
    def _parse_confidence(cls, v: Any) -> Any:
        if v is None:
            return 0.5
        if isinstance(v, str):
            stripped = v.strip().rstrip("%")
            try:
                number = float(stripped)
            except ValueError:
                return {"low": 0.3, "medium": 0.6, "high": 0.9}.get(
                    v.strip().lower(), 0.5
                )
            return number / 100 if "%" in v else number
        if isinstance(v, (int, float)):
            return v / 100 if v > 1 else v
        return v

    @field_validator("items", mode="before")
    @classmethod
    def _normalise_items(cls, v: Any) -> Any:
        """Accept the shapes models use for a table of line items."""
        if v is None:
            return []
        if isinstance(v, dict):
            # {"Widget": 100, "Support": 200} -> rows
            return [{"description": k, "amount": val} for k, val in v.items()]
        if isinstance(v, list):
            rows = []
            for item in v:
                if isinstance(item, dict):
                    rows.append(item)
                elif item is not None:
                    rows.append({"description": str(item)})
            return rows
        return []

    # -- convenience --------------------------------------------------
    @property
    def items_sum(self) -> float | None:
        """Sum of line amounts, or ``None`` when no line has an amount."""
        amounts = [i.amount for i in self.items if i.amount is not None]
        return round(sum(amounts), 2) if amounts else None


def schema_hint() -> str:
    """Compact schema description embedded in the prompt.

    Generated from the enums so the prompt cannot drift from the contract.
    """
    return (
        "{\n"
        f'  "document_type": one of {[d.value for d in DocumentType]},\n'
        '  "vendor": "company that issued the invoice",\n'
        '  "vendor_address": "their address, or \\"\\"",\n'
        '  "bill_to": "who is being billed",\n'
        '  "invoice_number": "e.g. INV-10932",\n'
        '  "purchase_order": "PO number if present, else \\"\\"",\n'
        '  "date": "YYYY-MM-DD",\n'
        '  "due_date": "YYYY-MM-DD or null",\n'
        f'  "currency": one of {[c.value for c in Currency]},\n'
        '  "subtotal": number,\n'
        '  "tax": number,\n'
        '  "shipping": number or null,\n'
        '  "discount": number or null,\n'
        '  "total": number,\n'
        '  "items": [\n'
        '    {"description": "...", "quantity": number, "unit_price": number, "amount": number}\n'
        "  ],\n"
        '  "confidence": number between 0 and 1,\n'
        '  "notes": "anything unclear or unreadable"\n'
        "}"
    )
