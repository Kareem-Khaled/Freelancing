"""End-to-end ticket pipeline: validate -> analyse -> persist -> route.

This is the orchestration layer the dashboard and CLI both sit on top of.
It is deliberately the only place that knows about *all* of storage, the LLM
and the input guards, so the other modules stay independently testable.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from typing import Any

from . import crm, trace
from .config import settings
from .llm import LLMError, SupportLLM
from .rules import Action, Decision, apply_rules
from .schemas import Action as TicketAction
from .schemas import Category, Priority, Sentiment, TicketAnalysis
from .storage import Database
from .telemetry import CallMetrics, MetricsCollector, new_request_id
from .tools import ToolCallRecord
from .validation import InputProblem, ValidationResult, validate_message


@dataclass
class TicketResult:
    """Outcome of processing one inbound message."""

    ticket_id: str
    ok: bool
    analysis: TicketAnalysis | None = None
    decision: Decision | None = None
    tools: list[ToolCallRecord] = field(default_factory=list)
    request_id: str = ""
    error: str = ""
    problem: InputProblem | None = None
    truncated: bool = False
    calls: list[CallMetrics] = field(default_factory=list)

    @property
    def attempts(self) -> int:
        return len(self.calls)

    @property
    def language(self) -> str:
        """Language the customer wrote in, as detected by the model."""
        return self.analysis.language if self.analysis else "en"

    @property
    def latency_ms(self) -> float:
        return round(sum(c.latency_ms for c in self.calls), 1)

    def as_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "ticket_id": self.ticket_id,
            "ok": self.ok,
            "request_id": self.request_id,
            "attempts": self.attempts,
            "latency_ms": self.latency_ms,
        }
        if self.analysis:
            data["analysis"] = self.analysis.model_dump(mode="json")
        if self.decision:
            data["decision"] = self.decision.as_dict()
        if self.tools:
            data["tools"] = [t.as_dict() for t in self.tools]
        if self.error:
            data["error"] = self.error
        if self.problem:
            data["problem"] = self.problem.value
        if self.truncated:
            data["truncated"] = True
        return data


def _fallback_analysis(
    issue: str,
    draft: str,
    *,
    category: Category = Category.OTHER,
    priority: Priority = Priority.MEDIUM,
    action: TicketAction = TicketAction.ROUTE_TO_HUMAN,
) -> TicketAnalysis:
    """A safe, human-routed analysis used when the model cannot be trusted.

    The platform must never silently drop a ticket: if anything goes wrong we
    still produce a record, flagged for a human.
    """
    return TicketAnalysis(
        category=category,
        priority=priority,
        sentiment=Sentiment.NEUTRAL,
        issue=issue,
        entities=[],
        suggested_action=action,
        requires_human=True,
        draft_response=draft,
        confidence=0.0,
    )


def _apply_decision(analysis: TicketAnalysis, decision: Decision) -> TicketAnalysis:
    """Return a copy of the analysis reconciled with the rules decision.

    The stored record must reflect what the platform actually decided, not the
    model's unchecked suggestion -- otherwise the dashboard would show a
    'medium / no human needed' ticket that the rules had already escalated.
    The original model values are preserved on the ``Decision`` for audit.
    """
    if analysis.priority == decision.priority and analysis.requires_human == decision.requires_human:
        return analysis
    return analysis.model_copy(
        update={"priority": decision.priority, "requires_human": decision.requires_human}
    )


def _resolve_identity(customer: str) -> str | None:
    """Resolve the channel-supplied customer label to a CRM customer id.

    Accepts a customer id or an email address, because that is what an
    authenticated session or a verified email sender would give us. Placeholder
    labels such as "web" or "unknown" resolve to ``None``, meaning anonymous --
    and an anonymous ticket may not read anyone's account data.
    """
    value = (customer or "").strip()
    if not value or value.lower() in {"web", "unknown", "anonymous", "demo", "test"}:
        return None
    try:
        if "@" in value:
            return crm.find_customer_by_email(value)["customer_id"]
        return crm.get_customer(value)["customer_id"]
    except crm.NotFound:
        return None


class SupportPipeline:
    """Processes tickets and keeps conversation state in the database.

    Safe to share across threads: the per-request metrics buffer is thread-local,
    so concurrent ``process`` calls cannot interleave each other's telemetry.
    """

    def __init__(self, db: Database | None = None, llm: SupportLLM | None = None) -> None:
        self.db = db or Database()
        self.metrics = MetricsCollector()
        self._local = threading.local()
        self.llm = llm or SupportLLM(metrics=self.metrics, on_call=self._on_call)

    @property
    def _call_buffer(self) -> list[CallMetrics]:
        if not hasattr(self._local, "calls"):
            self._local.calls = []
        return self._local.calls

    def _reset_calls(self) -> None:
        self._local.calls = []

    def _on_call(self, record: CallMetrics) -> None:
        """Buffer the attempt; it is persisted once its outcome is final.

        A call can look successful at the HTTP layer and still fail the schema
        contract a moment later, so writing to the database here would record a
        misleading ``success=1``. We flush the buffer at the end of ``process``.
        """
        self._call_buffer.append(record)

    def _flush_calls(self) -> None:
        """Persist buffered metrics. Telemetry must never break processing."""
        for record in self._call_buffer:
            try:
                self.db.save_call(record)
            except Exception:
                pass

    # -- public API ----------------------------------------------------
    def process(
        self,
        message: object,
        *,
        ticket_id: str | None = None,
        customer: str = "unknown",
        subject: str = "",
    ) -> TicketResult:
        """Process one inbound message.

        Pass an existing ``ticket_id`` to append to a conversation; omit it to
        open a new ticket.
        """
        ticket_id = ticket_id or f"TKT-{uuid.uuid4().hex[:8].upper()}"
        self._reset_calls()

        # 1. Guard the input before spending an inference call.
        check: ValidationResult = validate_message(message)
        if check.rejected:
            trace.emit(
                "validate",
                f"Rejected: {check.problem.value if check.problem else 'invalid'}",
                status="fail",
                detail=check.detail,
            )
            return self._handle_rejection(ticket_id, check, customer, subject)

        trace.emit(
            "validate",
            "Input accepted",
            detail=(
                f"{len(check.text)} characters"
                + (" (truncated)" if check.truncated else "")
            ),
            chars=len(check.text),
            truncated=check.truncated,
        )

        # 2. Record the customer turn so context survives across calls.
        self.db.upsert_ticket(ticket_id, customer=customer, subject=subject or check.text[:80])
        self.db.add_message(ticket_id, "customer", check.text)
        conversation = self.db.get_messages(ticket_id)

        customer_turns = sum(1 for m in conversation if m.get("role") == "customer")
        if customer_turns > 1:
            trace.emit(
                "validate",
                f"Conversation has {customer_turns} customer messages",
                detail="The whole thread is re-sent so references like 'it happened again' resolve.",
            )

        # 3. Analyse the whole thread (with tool-grounded research).
        #
        # Tools are scoped to the customer this ticket belongs to. ``customer``
        # comes from the channel (an authenticated session, or the verified
        # sender), never from the message body -- otherwise anyone could read
        # another account by typing its email.
        identity = _resolve_identity(customer)
        trace.emit(
            "validate",
            f"Identity: {identity}" if identity else "Identity: anonymous",
            status="ok" if identity else "warn",
            detail=(
                f"Account lookups are restricted to {identity}."
                if identity
                else "No verified identity — personal account lookups are refused."
            ),
        )

        try:
            analysis, request_id, tool_records = self.llm.analyse(
                conversation, ticket_id=ticket_id, customer_scope=identity
            )
        except LLMError as exc:
            analysis = _fallback_analysis(
                issue="Automatic analysis unavailable",
                draft=(
                    "Thanks for reaching out. Your message has been received and a member "
                    "of our team will follow up shortly."
                ),
                action=TicketAction.ROUTE_TO_HUMAN,
            )
            request_id = new_request_id()
            decision = apply_rules(analysis, self._customer_text(conversation))
            analysis = _apply_decision(analysis, decision)
            self.db.save_analysis(ticket_id, request_id, analysis, decision)
            self.db.set_status(ticket_id, decision.action.value)
            self._flush_calls()
            return TicketResult(
                ticket_id=ticket_id,
                ok=False,
                analysis=analysis,
                decision=decision,
                request_id=request_id,
                error=str(exc),
                truncated=check.truncated,
                calls=list(self._call_buffer),
            )

        # 4. BUSINESS RULES: the model proposed, deterministic policy decides.
        decision = apply_rules(analysis, self._customer_text(conversation), tools=tool_records)
        analysis = _apply_decision(analysis, decision)

        if decision.fired_rules:
            for name, reason in zip(decision.fired_rules, decision.reasons):
                trace.emit("rules", name, status="warn", detail=reason)
        else:
            trace.emit("rules", "No rules fired", detail="The model's recommendation stands.")

        trace.emit(
            "rules",
            f"Decision: {decision.action.value}",
            status="warn" if decision.overrode_model else "ok",
            detail=(
                f"priority {decision.priority.value}, SLA {decision.sla_hours}h"
                + (
                    f" — OVERRODE the model "
                    f"(it said priority={decision.model_priority.value if decision.model_priority else '?'}, "
                    f"requires_human={decision.model_requires_human})"
                    if decision.overrode_model
                    else ""
                )
            ),
            action=decision.action.value,
            priority=decision.priority.value,
            overrode_model=decision.overrode_model,
        )

        # 5. Persist and route on the post-rules decision.
        self.db.save_analysis(ticket_id, request_id, analysis, decision, tool_records)
        self.db.add_message(ticket_id, "agent_draft", analysis.draft_response)
        self.db.set_status(ticket_id, decision.action.value)
        self._flush_calls()

        trace.emit(
            "store",
            f"Saved as {ticket_id}",
            detail=f"status={decision.action.value}",
        )

        return TicketResult(
            ticket_id=ticket_id,
            ok=True,
            analysis=analysis,
            decision=decision,
            tools=tool_records,
            request_id=request_id,
            truncated=check.truncated,
            calls=list(self._call_buffer),
        )

    @staticmethod
    def _customer_text(conversation: list[dict[str, Any]]) -> str:
        """Raw customer text for the rules to scan.

        Rules read the customer's own words rather than the model's summary, so
        a phrase like "I'm calling my lawyer" still escalates even if the model
        summarised the ticket as a routine question.
        """
        return "\n".join(m["content"] for m in conversation if m.get("role") == "customer")

    def _handle_rejection(
        self, ticket_id: str, check: ValidationResult, customer: str, subject: str
    ) -> TicketResult:
        """Bad input still becomes a ticket -- flagged, never silently dropped."""
        messages = {
            InputProblem.EMPTY: (
                "Empty message",
                "We received your message but it appears to be empty. "
                "Could you reply with a few details about the problem?",
                TicketAction.REQUEST_MORE_INFO,
            ),
            InputProblem.TOO_SHORT: (
                "Message too short to analyse",
                "Thanks for getting in touch. Could you share a little more detail "
                "so we can help you properly?",
                TicketAction.REQUEST_MORE_INFO,
            ),
            InputProblem.NOT_TEXT: (
                "Attachment or binary content with no readable text",
                "We received your message but couldn't read its contents. "
                "Could you resend it as plain text?",
                TicketAction.REQUEST_MORE_INFO,
            ),
            InputProblem.MALFORMED: (
                "Malformed ticket payload",
                "We hit a problem reading your message. A member of our team will "
                "follow up shortly.",
                TicketAction.ROUTE_TO_HUMAN,
            ),
        }
        issue, draft, action = messages.get(
            check.problem,
            ("Unprocessable ticket", "A member of our team will follow up shortly.", TicketAction.ROUTE_TO_HUMAN),
        )

        analysis = _fallback_analysis(
            issue=issue,
            draft=draft,
            priority=Priority.LOW
            if check.problem in (InputProblem.EMPTY, InputProblem.TOO_SHORT)
            else Priority.MEDIUM,
            action=action,
        )

        request_id = new_request_id()
        decision = apply_rules(analysis, check.text or "")
        analysis = _apply_decision(analysis, decision)
        self.db.upsert_ticket(ticket_id, customer=customer, subject=subject or issue)
        if check.text:
            self.db.add_message(ticket_id, "customer", check.text)
        self.db.save_analysis(ticket_id, request_id, analysis, decision)
        self.db.set_status(ticket_id, decision.action.value)

        return TicketResult(
            ticket_id=ticket_id,
            ok=False,
            analysis=analysis,
            decision=decision,
            request_id=request_id,
            error=check.detail,
            problem=check.problem,
            truncated=check.truncated,
            calls=[],
        )

    # -- conversation helpers -----------------------------------------
    def conversation(self, ticket_id: str) -> list[dict[str, Any]]:
        return self.db.get_messages(ticket_id)

    def summary(self) -> dict[str, Any]:
        return self.metrics.summary()
