"""Mock CRM / billing backend.

Stands in for the systems a real support platform would query: customer records,
orders, payments and the refund policy. Seeded with deterministic data so tests
and demos are reproducible.

In production each function here becomes an API client. The important part is
the *shape*: every function is a plain read, returns plain dicts, and raises
``NotFound`` rather than inventing data.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any


class NotFound(LookupError):
    """Raised when a record does not exist."""


def _d(days_ago: int) -> str:
    return (date(2026, 9, 18) - timedelta(days=days_ago)).isoformat()


# ----------------------------------------------------------------------
# Seed data
# ----------------------------------------------------------------------
_CUSTOMERS: dict[str, dict[str, Any]] = {
    "C-1001": {
        "customer_id": "C-1001",
        "name": "Dana Whitfield",
        "email": "dana@acme-corp.com",
        "plan": "enterprise",
        "mrr_usd": 1200.00,
        "since": _d(640),
        "status": "active",
        "open_tickets": 2,
    },
    "C-1002": {
        "customer_id": "C-1002",
        "name": "Sam Ortega",
        "email": "sam@example.net",
        "plan": "pro",
        "mrr_usd": 29.99,
        "since": _d(95),
        "status": "active",
        "open_tickets": 0,
    },
    "C-1003": {
        "customer_id": "C-1003",
        "name": "Lee Zhang",
        "email": "lee@example.org",
        "plan": "free",
        "mrr_usd": 0.0,
        "since": _d(12),
        "status": "active",
        "open_tickets": 1,
    },
    "C-1004": {
        "customer_id": "C-1004",
        "name": "Kemo Khaled",
        "email": "kemo@gmail.com",
        "plan": "pro",
        "mrr_usd": 29.99,
        "since": _d(1200),
        "status": "active",
        "open_tickets": 0,
    },
}

_ORDERS: dict[str, list[dict[str, Any]]] = {
    "C-1001": [
        {"order_id": "A-5521", "total_usd": 1200.00, "status": "fulfilled", "date": _d(18)},
    ],
    "C-1002": [
        {"order_id": "B-8842", "total_usd": 29.99, "status": "fulfilled", "date": _d(31)},
        {"order_id": "B-8901", "total_usd": 29.99, "status": "fulfilled", "date": _d(3)},
    ],
    "C-1003": [],
}

# C-1002 is deliberately charged twice in the same period -- this is the
# scenario the flagship demo ticket describes.
_PAYMENTS: dict[str, list[dict[str, Any]]] = {
    "C-1001": [
        {"payment_id": "P-9001", "amount_usd": 1200.00, "date": _d(18),
         "status": "succeeded", "order_id": "A-5521", "method": "invoice"},
    ],
    "C-1002": [
        {"payment_id": "P-7741", "amount_usd": 29.99, "date": _d(31),
         "status": "succeeded", "order_id": "B-8842", "method": "card"},
        {"payment_id": "P-8120", "amount_usd": 29.99, "date": _d(4),
         "status": "succeeded", "order_id": "B-8901", "method": "card"},
        {"payment_id": "P-8121", "amount_usd": 29.99, "date": _d(3),
         "status": "succeeded", "order_id": "B-8901", "method": "card"},
    ],
    "C-1003": [
        {"payment_id": "P-6600", "amount_usd": 0.0, "date": _d(12),
         "status": "failed", "order_id": "", "method": "card",
         "error_code": "ERR_CARD_DECLINED_51"},
    ],
}

_REFUND_POLICY = {
    "window_days": 30,
    "auto_approve_limit_usd": 50.00,
    "requires_manager_above_usd": 500.00,
    "duplicate_charges": "Always refundable regardless of window.",
    "notes": (
        "Refunds within 30 days of payment may be approved by a support agent up to "
        "$50. Above $50 requires a manager. Above $500 requires finance sign-off. "
        "Verified duplicate charges are always refundable."
    ),
}


# ----------------------------------------------------------------------
# Read-only accessors
# ----------------------------------------------------------------------
def get_customer(customer_id: str) -> dict[str, Any]:
    record = _CUSTOMERS.get(customer_id.strip().upper())
    if not record:
        raise NotFound(f"no customer with id {customer_id!r}")
    return dict(record)


def find_customer_by_email(email: str) -> dict[str, Any]:
    target = email.strip().lower()
    for record in _CUSTOMERS.values():
        if record["email"].lower() == target:
            return dict(record)
    raise NotFound(f"no customer with email {email!r}")


def get_orders(customer_id: str) -> list[dict[str, Any]]:
    cid = customer_id.strip().upper()
    if cid not in _CUSTOMERS:
        raise NotFound(f"no customer with id {customer_id!r}")
    return [dict(o) for o in _ORDERS.get(cid, [])]


def get_order(order_id: str) -> dict[str, Any]:
    target = order_id.strip().upper()
    for cid, orders in _ORDERS.items():
        for order in orders:
            if order["order_id"].upper() == target:
                return {**order, "customer_id": cid}
    raise NotFound(f"no order with id {order_id!r}")


def get_payments(customer_id: str) -> list[dict[str, Any]]:
    cid = customer_id.strip().upper()
    if cid not in _CUSTOMERS:
        raise NotFound(f"no customer with id {customer_id!r}")
    return [dict(p) for p in _PAYMENTS.get(cid, [])]


def find_duplicate_charges(customer_id: str, within_days: int = 7) -> list[dict[str, Any]]:
    """Group successful payments with the same amount close together in time.

    This is the check a human agent would run by eye. Doing it in code rather
    than asking the model to compare dates means the answer is arithmetic, not
    a guess.
    """
    payments = [p for p in get_payments(customer_id) if p.get("status") == "succeeded"]
    groups: list[dict[str, Any]] = []

    by_amount: dict[float, list[dict[str, Any]]] = {}
    for p in payments:
        by_amount.setdefault(float(p["amount_usd"]), []).append(p)

    for amount, items in by_amount.items():
        if len(items) < 2:
            continue
        items.sort(key=lambda p: p["date"])
        for earlier, later in zip(items, items[1:]):
            gap = (date.fromisoformat(later["date"]) - date.fromisoformat(earlier["date"])).days
            if gap <= within_days:
                groups.append({
                    "amount_usd": amount,
                    "days_apart": gap,
                    "payment_ids": [earlier["payment_id"], later["payment_id"]],
                    "dates": [earlier["date"], later["date"]],
                })
    return groups


def get_refund_policy() -> dict[str, Any]:
    return dict(_REFUND_POLICY)


def list_customers() -> list[dict[str, Any]]:
    """Everyone in the CRM, for the demo's identity switcher.

    A real deployment would never expose this: identity comes from an
    authenticated session, not a dropdown. It exists so the dashboard can
    simulate "signed in as X" without building a login.
    """
    return [dict(record) for record in _CUSTOMERS.values()]
