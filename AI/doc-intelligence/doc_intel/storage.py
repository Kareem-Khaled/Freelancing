"""SQLite persistence for documents, extractions and LLM call metrics."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Iterator

from .config import settings
from .schemas import InvoiceExtraction
from .telemetry import CallMetrics

if TYPE_CHECKING:  # avoid a circular import at runtime
    from .validation import ValidationReport

_SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id            TEXT PRIMARY KEY,
    filename      TEXT NOT NULL DEFAULT '',
    content_type  TEXT NOT NULL DEFAULT '',
    doc_format    TEXT NOT NULL DEFAULT '',
    size_bytes    INTEGER NOT NULL DEFAULT 0,
    pages         INTEGER NOT NULL DEFAULT 0,
    status        TEXT NOT NULL DEFAULT 'pending',
    error         TEXT NOT NULL DEFAULT '',
    text_chars    INTEGER NOT NULL DEFAULT 0,
    truncated     INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS extractions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id     TEXT NOT NULL REFERENCES documents(id),
    request_id      TEXT NOT NULL DEFAULT '',
    -- The full extraction as JSON. Stored whole because the schema will evolve
    -- and re-parsing one blob is cheaper than migrating twenty columns.
    payload         TEXT NOT NULL,
    -- Denormalised for querying and dashboards.
    document_type   TEXT NOT NULL DEFAULT '',
    vendor          TEXT NOT NULL DEFAULT '',
    invoice_number  TEXT NOT NULL DEFAULT '',
    invoice_date    TEXT NOT NULL DEFAULT '',
    currency        TEXT NOT NULL DEFAULT '',
    total           REAL,
    confidence      REAL NOT NULL DEFAULT 0,
    review_status   TEXT NOT NULL DEFAULT '',
    findings        TEXT NOT NULL DEFAULT '[]',
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS llm_calls (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id        TEXT NOT NULL,
    document_id       TEXT NOT NULL DEFAULT '',
    operation         TEXT NOT NULL,
    model             TEXT NOT NULL,
    attempt           INTEGER NOT NULL,
    latency_ms        REAL NOT NULL,
    prompt_tokens     INTEGER NOT NULL,
    completion_tokens INTEGER NOT NULL,
    total_tokens      INTEGER NOT NULL,
    cost_usd          REAL NOT NULL DEFAULT 0,
    success           INTEGER NOT NULL,
    error             TEXT NOT NULL DEFAULT '',
    created_at        TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_extractions_doc ON extractions(document_id);
CREATE INDEX IF NOT EXISTS idx_calls_doc       ON llm_calls(document_id);
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Database:
    """Thin SQLite wrapper."""

    def __init__(self, path: str | None = None) -> None:
        self.path = path or settings.db_path
        self._init_schema()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        # A generous busy timeout matters once the API serves concurrent
        # uploads: writers queue rather than failing with "database is locked".
        conn = sqlite3.connect(self.path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 30000")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self.connect() as conn:
            conn.executescript(_SCHEMA)

    # -- documents ----------------------------------------------------
    def create_document(
        self,
        document_id: str,
        filename: str,
        content_type: str,
        size_bytes: int,
    ) -> None:
        now = _now()
        with self.connect() as conn:
            conn.execute(
                """INSERT INTO documents
                   (id, filename, content_type, size_bytes, status, created_at, updated_at)
                   VALUES (?, ?, ?, ?, 'pending', ?, ?)""",
                (document_id, filename, content_type, size_bytes, now, now),
            )

    def update_document(self, document_id: str, **fields: Any) -> None:
        if not fields:
            return
        fields["updated_at"] = _now()
        assignments = ", ".join(f"{k} = ?" for k in fields)
        with self.connect() as conn:
            conn.execute(
                f"UPDATE documents SET {assignments} WHERE id = ?",
                (*fields.values(), document_id),
            )

    def get_document(self, document_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM documents WHERE id = ?", (document_id,)
            ).fetchone()
        if not row:
            return None
        data = dict(row)
        data["truncated"] = bool(data.get("truncated"))
        return data

    def list_documents(self, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                """SELECT d.*, e.vendor, e.total, e.currency, e.review_status
                   FROM documents d
                   LEFT JOIN extractions e ON e.id = (
                       SELECT id FROM extractions WHERE document_id = d.id
                       ORDER BY id DESC LIMIT 1
                   )
                   ORDER BY d.created_at DESC
                   LIMIT ? OFFSET ?""",
                (limit, offset),
            ).fetchall()
        return [dict(r) for r in rows]

    def count_documents(self) -> int:
        with self.connect() as conn:
            return conn.execute("SELECT COUNT(*) AS n FROM documents").fetchone()["n"]

    # -- extractions --------------------------------------------------
    def save_extraction(
        self,
        document_id: str,
        request_id: str,
        extraction: InvoiceExtraction,
        report: "ValidationReport | None" = None,
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """INSERT INTO extractions
                   (document_id, request_id, payload, document_type, vendor,
                    invoice_number, invoice_date, currency, total, confidence,
                    review_status, findings, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    document_id,
                    request_id,
                    extraction.model_dump_json(),
                    extraction.document_type.value,
                    extraction.vendor,
                    extraction.invoice_number,
                    extraction.date or "",
                    extraction.currency.value,
                    extraction.total,
                    extraction.confidence,
                    report.status.value if report else "",
                    json.dumps([f.as_dict() for f in report.findings]) if report else "[]",
                    _now(),
                ),
            )

    def get_extraction(self, document_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                """SELECT * FROM extractions WHERE document_id = ?
                   ORDER BY id DESC LIMIT 1""",
                (document_id,),
            ).fetchone()
        if not row:
            return None
        data = dict(row)
        try:
            data["payload"] = json.loads(data["payload"])
        except (ValueError, TypeError):
            data["payload"] = {}
        try:
            data["findings"] = json.loads(data.get("findings") or "[]")
        except (ValueError, TypeError):
            data["findings"] = []
        return data

    # -- metrics ------------------------------------------------------
    def save_call(self, metrics: CallMetrics) -> None:
        with self.connect() as conn:
            conn.execute(
                """INSERT INTO llm_calls
                   (request_id, document_id, operation, model, attempt, latency_ms,
                    prompt_tokens, completion_tokens, total_tokens, cost_usd,
                    success, error, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    metrics.request_id,
                    metrics.ticket_id,  # CallMetrics is shared; this holds the document id
                    metrics.operation,
                    metrics.model,
                    metrics.attempt,
                    metrics.latency_ms,
                    metrics.prompt_tokens,
                    metrics.completion_tokens,
                    metrics.total_tokens,
                    metrics.cost_usd,
                    int(metrics.success),
                    metrics.error,
                    metrics.created_at,
                ),
            )

    def metrics_summary(self) -> dict[str, Any]:
        with self.connect() as conn:
            row = conn.execute(
                """SELECT COUNT(*) AS calls,
                          SUM(success) AS successes,
                          SUM(CASE WHEN attempt > 1 THEN 1 ELSE 0 END) AS retries,
                          AVG(latency_ms) AS avg_latency_ms,
                          MAX(latency_ms) AS max_latency_ms,
                          SUM(prompt_tokens) AS prompt_tokens,
                          SUM(completion_tokens) AS completion_tokens,
                          SUM(total_tokens) AS total_tokens,
                          SUM(cost_usd) AS cost_usd
                   FROM llm_calls"""
            ).fetchone()
        data = {k: (row[k] or 0) for k in row.keys()}
        data["success_rate"] = (
            round(data["successes"] / data["calls"], 3) if data["calls"] else 0.0
        )
        data["avg_latency_ms"] = round(data["avg_latency_ms"], 1)
        return data

    def review_counts(self) -> dict[str, int]:
        with self.connect() as conn:
            rows = conn.execute(
                """SELECT e.review_status, COUNT(*) AS n
                   FROM extractions e
                   JOIN (SELECT document_id, MAX(id) AS mid FROM extractions
                         GROUP BY document_id) last ON e.id = last.mid
                   WHERE e.review_status != ''
                   GROUP BY e.review_status"""
            ).fetchall()
        return {r["review_status"]: r["n"] for r in rows}
