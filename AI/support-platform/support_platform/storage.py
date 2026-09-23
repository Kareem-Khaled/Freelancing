"""SQLite persistence for tickets, messages, analyses and LLM call metrics."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Iterator

from .config import settings
from .schemas import TicketAnalysis
from .telemetry import CallMetrics

if TYPE_CHECKING:  # avoid a circular import at runtime
    from .rules import Decision

_SCHEMA = """
CREATE TABLE IF NOT EXISTS tickets (
    id            TEXT PRIMARY KEY,
    customer      TEXT NOT NULL DEFAULT 'unknown',
    subject       TEXT NOT NULL DEFAULT '',
    status        TEXT NOT NULL DEFAULT 'open',
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id  TEXT NOT NULL REFERENCES tickets(id),
    role       TEXT NOT NULL,
    content    TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS analyses (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id        TEXT NOT NULL REFERENCES tickets(id),
    request_id       TEXT NOT NULL,
    category         TEXT NOT NULL,
    priority         TEXT NOT NULL,
    sentiment        TEXT NOT NULL,
    issue            TEXT NOT NULL,
    entities         TEXT NOT NULL DEFAULT '[]',
    suggested_action TEXT NOT NULL,
    requires_human   INTEGER NOT NULL,
    draft_response   TEXT NOT NULL,
    confidence       REAL NOT NULL,
    -- post-rules decision (the value the platform actually acted on)
    action           TEXT NOT NULL DEFAULT '',
    sla_hours        INTEGER NOT NULL DEFAULT 0,
    fired_rules      TEXT NOT NULL DEFAULT '[]',
    rule_reasons     TEXT NOT NULL DEFAULT '[]',
    tags             TEXT NOT NULL DEFAULT '[]',
    -- what the model proposed before rules, for audit
    model_priority       TEXT NOT NULL DEFAULT '',
    model_requires_human INTEGER NOT NULL DEFAULT 0,
    overrode_model       INTEGER NOT NULL DEFAULT 0,
    tool_calls       TEXT NOT NULL DEFAULT '[]',
    created_at       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS llm_calls (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id        TEXT NOT NULL,
    ticket_id         TEXT NOT NULL DEFAULT '',
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

CREATE INDEX IF NOT EXISTS idx_messages_ticket ON messages(ticket_id);
CREATE INDEX IF NOT EXISTS idx_analyses_ticket ON analyses(ticket_id);
CREATE INDEX IF NOT EXISTS idx_calls_ticket    ON llm_calls(ticket_id);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Database:
    """Thin SQLite wrapper. Safe for the single-process CLI/dashboard usage."""

    def __init__(self, path: str | None = None) -> None:
        self.path = path or settings.db_path
        self._init_schema()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        # A generous timeout matters once the web UI processes tickets
        # concurrently: writers queue rather than failing with "database is locked".
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
            self._migrate(conn)

    @staticmethod
    def _migrate(conn: sqlite3.Connection) -> None:
        """Add columns introduced after a database was first created.

        ``CREATE TABLE IF NOT EXISTS`` does not alter an existing table, so a
        database created before the business-rules layer would be missing those
        columns. Adding them here keeps existing data usable.
        """
        existing = {row["name"] for row in conn.execute("PRAGMA table_info(analyses)")}
        additions = {
            "action": "TEXT NOT NULL DEFAULT ''",
            "sla_hours": "INTEGER NOT NULL DEFAULT 0",
            "fired_rules": "TEXT NOT NULL DEFAULT '[]'",
            "rule_reasons": "TEXT NOT NULL DEFAULT '[]'",
            "tags": "TEXT NOT NULL DEFAULT '[]'",
            "model_priority": "TEXT NOT NULL DEFAULT ''",
            "model_requires_human": "INTEGER NOT NULL DEFAULT 0",
            "overrode_model": "INTEGER NOT NULL DEFAULT 0",
            "tool_calls": "TEXT NOT NULL DEFAULT '[]'",
        }
        for column, spec in additions.items():
            if column not in existing:
                conn.execute(f"ALTER TABLE analyses ADD COLUMN {column} {spec}")

    # -- tickets ------------------------------------------------------
    def upsert_ticket(self, ticket_id: str, customer: str = "unknown", subject: str = "") -> None:
        now = _now()
        with self.connect() as conn:
            conn.execute(
                """INSERT INTO tickets (id, customer, subject, status, created_at, updated_at)
                   VALUES (?, ?, ?, 'open', ?, ?)
                   ON CONFLICT(id) DO UPDATE SET updated_at = excluded.updated_at""",
                (ticket_id, customer, subject, now, now),
            )

    def set_status(self, ticket_id: str, status: str) -> None:
        with self.connect() as conn:
            conn.execute(
                "UPDATE tickets SET status = ?, updated_at = ? WHERE id = ?",
                (status, _now(), ticket_id),
            )

    # -- messages -----------------------------------------------------
    def add_message(self, ticket_id: str, role: str, content: str) -> None:
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO messages (ticket_id, role, content, created_at) VALUES (?, ?, ?, ?)",
                (ticket_id, role, content, _now()),
            )

    def get_messages(self, ticket_id: str) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT role, content, created_at FROM messages WHERE ticket_id = ? ORDER BY id",
                (ticket_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    # -- analyses -----------------------------------------------------
    def save_analysis(
        self,
        ticket_id: str,
        request_id: str,
        analysis: TicketAnalysis,
        decision: "Decision | None" = None,
        tool_calls: list | None = None,
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """INSERT INTO analyses
                   (ticket_id, request_id, category, priority, sentiment, issue, entities,
                    suggested_action, requires_human, draft_response, confidence,
                    action, sla_hours, fired_rules, rule_reasons, tags,
                    model_priority, model_requires_human, overrode_model, tool_calls, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    ticket_id,
                    request_id,
                    analysis.category.value,
                    analysis.priority.value,
                    analysis.sentiment.value,
                    analysis.issue,
                    json.dumps([e.model_dump() for e in analysis.entities]),
                    analysis.suggested_action.value,
                    int(analysis.requires_human),
                    analysis.draft_response,
                    analysis.confidence,
                    decision.action.value if decision else "",
                    decision.sla_hours if decision else 0,
                    json.dumps(decision.fired_rules) if decision else "[]",
                    json.dumps(decision.reasons) if decision else "[]",
                    json.dumps(decision.tags) if decision else "[]",
                    decision.model_priority.value if decision and decision.model_priority else "",
                    int(bool(decision.model_requires_human)) if decision else 0,
                    int(decision.overrode_model) if decision else 0,
                    json.dumps([t.as_dict() for t in (tool_calls or [])]),
                    _now(),
                ),
            )

    def latest_analysis(self, ticket_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM analyses WHERE ticket_id = ? ORDER BY id DESC LIMIT 1",
                (ticket_id,),
            ).fetchone()
        return dict(row) if row else None

    # -- metrics ------------------------------------------------------
    def save_call(self, metrics: CallMetrics) -> None:
        with self.connect() as conn:
            conn.execute(
                """INSERT INTO llm_calls
                   (request_id, ticket_id, operation, model, attempt, latency_ms,
                    prompt_tokens, completion_tokens, total_tokens, cost_usd,
                    success, error, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    metrics.request_id,
                    metrics.ticket_id,
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

    # -- dashboard queries --------------------------------------------
    def dashboard_rows(self, limit: int = 50) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                """SELECT t.id, t.customer, t.status, t.updated_at,
                          a.category, a.priority, a.sentiment, a.issue,
                          a.suggested_action, a.requires_human, a.confidence,
                          a.action, a.sla_hours, a.tags, a.fired_rules, a.overrode_model
                   FROM tickets t
                   LEFT JOIN analyses a ON a.id = (
                       SELECT id FROM analyses WHERE ticket_id = t.id ORDER BY id DESC LIMIT 1
                   )
                   ORDER BY t.updated_at DESC
                   LIMIT ?""",
                (limit,),
            ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            for key in ("tags", "fired_rules"):
                try:
                    d[key] = json.loads(d.get(key) or "[]")
                except (ValueError, TypeError):
                    d[key] = []
            out.append(d)
        return out

    def action_counts(self) -> dict[str, int]:
        """How many tickets landed on each post-rules action."""
        with self.connect() as conn:
            rows = conn.execute(
                """SELECT a.action, COUNT(*) AS n
                   FROM analyses a
                   JOIN (SELECT ticket_id, MAX(id) AS mid FROM analyses GROUP BY ticket_id) last
                     ON a.id = last.mid
                   WHERE a.action != ''
                   GROUP BY a.action"""
            ).fetchall()
        return {r["action"]: r["n"] for r in rows}

    def rule_counts(self) -> dict[str, int]:
        """How often each business rule fired -- useful for tuning."""
        counts: dict[str, int] = {}
        with self.connect() as conn:
            rows = conn.execute(
                """SELECT a.fired_rules
                   FROM analyses a
                   JOIN (SELECT ticket_id, MAX(id) AS mid FROM analyses GROUP BY ticket_id) last
                     ON a.id = last.mid"""
            ).fetchall()
        for r in rows:
            try:
                for name in json.loads(r["fired_rules"] or "[]"):
                    counts[name] = counts.get(name, 0) + 1
            except (ValueError, TypeError):
                continue
        return dict(sorted(counts.items(), key=lambda kv: -kv[1]))

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
        data["success_rate"] = round(data["successes"] / data["calls"], 3) if data["calls"] else 0.0
        data["avg_latency_ms"] = round(data["avg_latency_ms"], 1)
        return data

    def queue_counts(self) -> dict[str, int]:
        with self.connect() as conn:
            rows = conn.execute(
                """SELECT a.priority, COUNT(*) AS n
                   FROM analyses a
                   JOIN (SELECT ticket_id, MAX(id) AS mid FROM analyses GROUP BY ticket_id) last
                     ON a.id = last.mid
                   GROUP BY a.priority"""
            ).fetchall()
        return {r["priority"]: r["n"] for r in rows}

    def get_ticket(self, ticket_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        return dict(row) if row else None

    def ticket_calls(self, ticket_id: str) -> list[dict[str, Any]]:
        """Every LLM attempt made for a ticket, newest last."""
        with self.connect() as conn:
            rows = conn.execute(
                """SELECT request_id, operation, attempt, latency_ms, prompt_tokens,
                          completion_tokens, total_tokens, success, error, created_at
                   FROM llm_calls WHERE ticket_id = ? ORDER BY id""",
                (ticket_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def analyses_for(self, ticket_id: str) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM analyses WHERE ticket_id = ? ORDER BY id", (ticket_id,)
            ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            try:
                d["entities"] = json.loads(d.get("entities") or "[]")
            except (ValueError, TypeError):
                d["entities"] = []
            for key in ("fired_rules", "rule_reasons", "tags", "tool_calls"):
                try:
                    d[key] = json.loads(d.get(key) or "[]")
                except (ValueError, TypeError):
                    d[key] = []
            d["requires_human"] = bool(d.get("requires_human"))
            d["overrode_model"] = bool(d.get("overrode_model"))
            out.append(d)
        return out
