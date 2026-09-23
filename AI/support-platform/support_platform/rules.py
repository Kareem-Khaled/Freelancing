"""Deterministic business rules applied AFTER the LLM classification.

    LLM  ->  classification  ->  BUSINESS RULES  ->  final decision

Why this layer exists
---------------------
The LLM's output is a *recommendation*, not a decision. Prompt instructions are
suggestions a model may ignore -- exactly how this project already saw
``enable_thinking`` silently ignored by the server and ``"priority": "High"``
returned against an explicit lowercase enum.

Anything the business actually cares about (money movement, legal exposure,
security, churn risk) must be enforced in code that runs every time and cannot
be talked out of its answer by a persuasive ticket.

Design rules for this module:

* **Rules only escalate, never de-escalate.** A rule may raise priority or force
  human review; none may lower priority or clear ``requires_human``. This makes
  the layer safe by construction -- adding a rule can never make the system more
  permissive than the model alone.
* **Pure and deterministic.** No network, no model, no randomness. Same input,
  same decision, every time.
* **Auditable.** Every rule that fires is recorded by name on the decision, so a
  reviewer can see precisely why a ticket was escalated.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable

from .config import settings
from .schemas import Action as TicketAction
from .schemas import Category, Priority, Sentiment, TicketAnalysis

__all__ = ["Action", "RuleOutcome", "Decision", "Rule", "apply_rules", "RULES"]


class Action(str, Enum):
    """What the platform will actually do with the ticket."""

    AUTO_SEND = "auto_send"          # safe enough to reply without a human
    HUMAN_REVIEW = "human_review"    # draft is ready, a human must approve it
    ESCALATE = "escalate"            # senior/specialist queue
    NEEDS_INFO = "needs_info"        # ask the customer for more detail


# Rules are ordered by severity; the strongest action wins.
_ACTION_RANK = {
    Action.AUTO_SEND: 0,
    Action.NEEDS_INFO: 1,
    Action.HUMAN_REVIEW: 2,
    Action.ESCALATE: 3,
}

_PRIORITY_RANK = {Priority.LOW: 0, Priority.MEDIUM: 1, Priority.HIGH: 2}


@dataclass
class RuleOutcome:
    """What a single rule wants to change."""

    reason: str
    action: Action | None = None
    priority: Priority | None = None
    requires_human: bool | None = None
    tag: str = ""


@dataclass
class Rule:
    name: str
    description: str
    check: Callable[[TicketAnalysis, str], RuleOutcome | None]


@dataclass
class ToolFacts:
    """Verified facts extracted from tool calls, for rules to act on.

    Rules must not re-read raw tool payloads; they get this narrow, typed view so
    a change in tool output shape cannot silently alter policy.
    """

    duplicate_verified: bool = False
    duplicate_checked: bool = False
    customer_found: bool = False
    customer_plan: str = ""
    lookup_failed: bool = False

    @classmethod
    def from_records(cls, records: list | None) -> "ToolFacts":
        facts = cls()
        for r in records or []:
            name = getattr(r, "name", "")
            ok = getattr(r, "ok", False)
            summary = getattr(r, "result_summary", "") or ""
            if name == "check_duplicate_charges":
                facts.duplicate_checked = facts.duplicate_checked or ok
                if ok and "duplicate_found=True" in summary:
                    facts.duplicate_verified = True
            elif name == "get_customer":
                if ok:
                    facts.customer_found = True
                    for part in summary.split(", "):
                        if part.startswith("plan="):
                            facts.customer_plan = part[5:]
                else:
                    facts.lookup_failed = True
            elif not ok:
                facts.lookup_failed = True
        return facts


@dataclass
class Decision:
    """The final, post-rules decision for a ticket."""

    action: Action
    priority: Priority
    requires_human: bool
    sla_hours: int
    fired_rules: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    # Set when rules overrode the model, so the UI can show the disagreement.
    model_priority: Priority | None = None
    model_requires_human: bool | None = None

    @property
    def overrode_model(self) -> bool:
        return (
            self.model_priority is not None and self.model_priority != self.priority
        ) or (
            self.model_requires_human is not None
            and self.model_requires_human != self.requires_human
        )

    def as_dict(self) -> dict:
        return {
            "action": self.action.value,
            "priority": self.priority.value,
            "requires_human": self.requires_human,
            "sla_hours": self.sla_hours,
            "fired_rules": self.fired_rules,
            "reasons": self.reasons,
            "tags": self.tags,
            "overrode_model": self.overrode_model,
            "model_priority": self.model_priority.value if self.model_priority else None,
            "model_requires_human": self.model_requires_human,
        }


# ----------------------------------------------------------------------
# Keyword sets. Kept explicit and readable so a non-engineer can audit them.
# ----------------------------------------------------------------------
_LEGAL = re.compile(
    r"\b(lawyer|attorney|solicitor|legal action|sue|suing|lawsuit|court|"
    r"small claims|regulator|ombudsman|gdpr|ccpa|data protection|"
    r"chargeback|dispute the charge|fraud|fraudulent)\b",
    re.I,
)
_SECURITY = re.compile(
    r"\b(hacked|breach|breached|phishing|password leak|leaked|unauthorized access|"
    r"unauthorised access|someone else logged|account taken over|2fa|mfa|"
    r"security vulnerability|xss|sql injection)\b",
    re.I,
)
_CHURN = re.compile(
    r"\b(cancel my|cancel our|cancelling|canceling|close my account|delete my account|"
    r"switch to a competitor|moving to another|unsubscribe|terminate (my|our) (plan|contract)|"
    r"refund everything|never using)\b",
    re.I,
)
_VIP_TERMS = re.compile(r"\b(enterprise|our team of|per seat|annual contract|sla)\b", re.I)

# Money movement is the single highest-risk action a support bot can take.
_MONEY_ACTIONS = re.compile(r"(refund|chargeback|credit|reimburse|compensat|discount|waive)", re.I)

# The ONLY actions that may ever reach a customer without human review.
# An allow-list, not a block-list: an action missing from here is refused even if
# no other rule objected, so a value nobody anticipated fails closed.
_AUTO_SAFE_ACTIONS = {
    TicketAction.ANSWER_QUESTION,
    TicketAction.REQUEST_MORE_INFO,
    TicketAction.ACKNOWLEDGE,
}


# ----------------------------------------------------------------------
# Individual rules
# ----------------------------------------------------------------------
def _mentions_money(a: TicketAnalysis) -> bool:
    """Whether the analysis involves money movement.

    Checks both the action and the issue text -- the model may describe a refund
    in the issue while choosing a neutral action like ``review_billing_inquiry``.
    Shared by the keyword and tool-grounded rules so both stay consistent.
    """
    return bool(_MONEY_ACTIONS.search(a.suggested_action.value) or _MONEY_ACTIONS.search(a.issue))


def _rule_money_movement(a: TicketAnalysis, text: str) -> RuleOutcome | None:
    """Anything touching money never auto-sends, regardless of model confidence."""
    if _mentions_money(a):
        return RuleOutcome(
            reason="Involves money movement (refund/credit/chargeback) — requires human approval",
            action=Action.HUMAN_REVIEW,
            requires_human=True,
            tag="money",
        )
    return None


def _rule_legal(a: TicketAnalysis, text: str) -> RuleOutcome | None:
    if _LEGAL.search(text):
        return RuleOutcome(
            reason="Legal or regulatory language detected — escalate, do not auto-reply",
            action=Action.ESCALATE,
            priority=Priority.HIGH,
            requires_human=True,
            tag="legal",
        )
    return None


def _rule_security(a: TicketAnalysis, text: str) -> RuleOutcome | None:
    if _SECURITY.search(text):
        return RuleOutcome(
            reason="Possible security incident — escalate to the security queue",
            action=Action.ESCALATE,
            priority=Priority.HIGH,
            requires_human=True,
            tag="security",
        )
    return None


def _rule_churn(a: TicketAnalysis, text: str) -> RuleOutcome | None:
    if _CHURN.search(text):
        return RuleOutcome(
            reason="Cancellation or churn signal — route to retention",
            action=Action.ESCALATE,
            priority=Priority.HIGH,
            requires_human=True,
            tag="churn",
        )
    return None


def _rule_angry_customer(a: TicketAnalysis, text: str) -> RuleOutcome | None:
    """A negative, high-priority ticket should not be answered by a bot."""
    if a.sentiment is Sentiment.NEGATIVE and a.priority is Priority.HIGH:
        return RuleOutcome(
            reason="Angry customer on a high-priority issue — human should reply",
            action=Action.HUMAN_REVIEW,
            requires_human=True,
            tag="at_risk",
        )
    return None


def _rule_low_confidence(a: TicketAnalysis, text: str) -> RuleOutcome | None:
    """Do not act on a classification the model itself is unsure about."""
    if a.confidence < 0.6:
        return RuleOutcome(
            reason=f"Model confidence {a.confidence:.2f} below 0.60 threshold",
            action=Action.HUMAN_REVIEW,
            requires_human=True,
            tag="low_confidence",
        )
    return None


def _rule_failed_analysis(a: TicketAnalysis, text: str) -> RuleOutcome | None:
    """Confidence 0.0 is the pipeline's fallback marker for 'analysis failed'."""
    if a.confidence <= 0.0:
        return RuleOutcome(
            reason="Automatic analysis unavailable — manual triage required",
            action=Action.HUMAN_REVIEW,
            requires_human=True,
            tag="no_analysis",
        )
    return None


def _rule_billing_is_never_low(a: TicketAnalysis, text: str) -> RuleOutcome | None:
    """Billing problems cost customers money; never sit on them as 'low'."""
    if a.category is Category.BILLING and a.priority is Priority.LOW:
        return RuleOutcome(
            reason="Billing tickets are never low priority",
            priority=Priority.MEDIUM,
            tag="billing_floor",
        )
    return None


def _rule_vip(a: TicketAnalysis, text: str) -> RuleOutcome | None:
    if _VIP_TERMS.search(text):
        return RuleOutcome(
            reason="Enterprise/contract language — apply the enterprise SLA",
            priority=Priority.HIGH,
            requires_human=True,
            tag="enterprise",
        )
    return None


def _rule_out_of_scope(a: TicketAnalysis, text: str) -> RuleOutcome | None:
    """Refuse to answer anything that is not about the product.

    A support channel that answers homework is being used as a free LLM, and any
    answer it gives carries the company's name. The prompt already instructs the
    model to decline, but prompts are requests -- this project has watched the
    model ignore an explicit lowercase-enum instruction, so scope is enforced
    here as well.

    Low priority (it is not a customer problem) but never auto-sent: an
    off-topic reply is exactly the kind of thing a human should glance at.
    """
    if a.category is Category.OUT_OF_SCOPE or a.suggested_action is TicketAction.DECLINE_OUT_OF_SCOPE:
        return RuleOutcome(
            reason="Not a product support request — decline rather than answer",
            action=Action.HUMAN_REVIEW,
            requires_human=True,
            tag="out_of_scope",
        )
    return None


def _rule_needs_more_info(a: TicketAnalysis, text: str) -> RuleOutcome | None:
    if a.suggested_action is TicketAction.REQUEST_MORE_INFO:
        return RuleOutcome(
            reason="Ticket lacks the detail needed to act",
            action=Action.NEEDS_INFO,
            tag="needs_info",
        )
    return None


def _rule_unsupported_language(a: TicketAnalysis, text: str) -> RuleOutcome | None:
    """Flag tickets the team cannot review, if such a limit is configured.

    Inert by default: ``supported_languages`` is empty, meaning every language is
    handled. It is NOT a technical limit -- the model reads and replies in any
    language it knows. It exists only for teams whose agents can review a subset,
    because approving a refund reply you cannot read is rubber-stamping.

    Note this runs *after* analysis, so the ticket is fully triaged and the draft
    reply is already written in the customer's language. A translator reviews
    something, rather than starting from scratch.
    """
    allowed = settings.supported_languages
    if not allowed:
        return None
    if a.language and a.language not in allowed:
        return RuleOutcome(
            reason=(
                f"Ticket is in '{a.language}'; the team reviews "
                f"{', '.join(allowed)} -- route to someone who can verify the reply"
            ),
            action=Action.HUMAN_REVIEW,
            requires_human=True,
            tag="needs_translator",
        )
    return None


RULES: list[Rule] = [
    Rule("failed_analysis", "Analysis unavailable -> manual triage", _rule_failed_analysis),
    Rule("legal_exposure", "Legal/regulatory language -> escalate", _rule_legal),
    Rule("security_incident", "Security language -> escalate", _rule_security),
    Rule("churn_risk", "Cancellation intent -> retention", _rule_churn),
    Rule("money_movement", "Refunds/credits -> human approval", _rule_money_movement),
    Rule("angry_customer", "Negative + high priority -> human", _rule_angry_customer),
    Rule("low_confidence", "Confidence < 0.60 -> human", _rule_low_confidence),
    Rule("enterprise_sla", "Enterprise language -> high priority", _rule_vip),
    Rule("billing_priority_floor", "Billing is never low", _rule_billing_is_never_low),
    Rule("needs_more_info", "Insufficient detail -> ask customer", _rule_needs_more_info),
    Rule("out_of_scope", "Not a support request -> decline, never answer", _rule_out_of_scope),
    Rule("unsupported_language", "Language the team cannot review -> translator", _rule_unsupported_language),
]


# SLA targets in hours, keyed by final priority.
SLA_HOURS = {Priority.HIGH: 4, Priority.MEDIUM: 24, Priority.LOW: 72}


def apply_rules(
    analysis: TicketAnalysis,
    conversation_text: str = "",
    rules: list[Rule] | None = None,
    tools: list | None = None,
) -> Decision:
    """Run every rule and combine the outcomes into a final decision.

    ``conversation_text`` is the raw customer text. Rules read it directly rather
    than trusting the model's summary, so a phrase like "I'm calling my lawyer"
    escalates even if the model classified the ticket as a routine question.

    ``tools`` are the tool-call records from the research phase. Rules use them
    to distinguish a *verified* fact from an unverified customer claim.

    Escalation-only: the result is never weaker than what the model proposed.
    """
    rules = rules if rules is not None else RULES
    facts = ToolFacts.from_records(tools)

    # Start from the model's recommendation.
    action = Action.HUMAN_REVIEW if analysis.requires_human else Action.AUTO_SEND
    priority = analysis.priority
    requires_human = analysis.requires_human

    decision = Decision(
        action=action,
        priority=priority,
        requires_human=requires_human,
        sla_hours=SLA_HOURS[priority],
        model_priority=analysis.priority,
        model_requires_human=analysis.requires_human,
    )

    for rule in rules:
        try:
            outcome = rule.check(analysis, conversation_text)
        except Exception:
            # A broken rule must never take down triage; skip it.
            continue
        if outcome is None:
            continue

        decision.fired_rules.append(rule.name)
        decision.reasons.append(outcome.reason)
        if outcome.tag and outcome.tag not in decision.tags:
            decision.tags.append(outcome.tag)

        # Escalate only -- take the strongest action seen so far.
        if outcome.action and _ACTION_RANK[outcome.action] > _ACTION_RANK[decision.action]:
            decision.action = outcome.action
        if outcome.priority and _PRIORITY_RANK[outcome.priority] > _PRIORITY_RANK[decision.priority]:
            decision.priority = outcome.priority
        if outcome.requires_human:
            decision.requires_human = True

    # -- tool-grounded rules ------------------------------------------
    for outcome in _tool_rules(analysis, facts):
        decision.fired_rules.append(outcome.tag or "tool_rule")
        decision.reasons.append(outcome.reason)
        if outcome.tag and outcome.tag not in decision.tags:
            decision.tags.append(outcome.tag)
        if outcome.action and _ACTION_RANK[outcome.action] > _ACTION_RANK[decision.action]:
            decision.action = outcome.action
        if outcome.priority and _PRIORITY_RANK[outcome.priority] > _PRIORITY_RANK[decision.priority]:
            decision.priority = outcome.priority
        if outcome.requires_human:
            decision.requires_human = True

    # A ticket needing a human cannot also be auto-sent.
    if decision.requires_human and decision.action is Action.AUTO_SEND:
        decision.action = Action.HUMAN_REVIEW

    # Conservative default: only a small allow-list may ever auto-send.
    if decision.action is Action.AUTO_SEND and analysis.suggested_action not in _AUTO_SAFE_ACTIONS:
        decision.action = Action.HUMAN_REVIEW
        decision.requires_human = True
        decision.fired_rules.append("auto_send_allowlist")
        decision.reasons.append(
            f"Action '{analysis.suggested_action.value}' is not on the auto-send allow-list"
        )

    # An off-topic ticket is never auto-sent, whatever action the model chose.
    # Checked separately from the allow-list because the model may label a
    # homework question "answer_question" -- which IS allow-listed -- while also
    # marking the category out_of_scope. The category wins.
    if decision.action is Action.AUTO_SEND and analysis.category is Category.OUT_OF_SCOPE:
        decision.action = Action.HUMAN_REVIEW
        decision.requires_human = True
        decision.fired_rules.append("out_of_scope_never_auto_sends")
        decision.reasons.append(
            "Out-of-scope requests are reviewed before any reply is sent"
        )

    decision.sla_hours = SLA_HOURS[decision.priority]
    return decision


def _tool_rules(analysis: TicketAnalysis, facts: ToolFacts) -> list[RuleOutcome]:
    """Policy that depends on verified account data rather than the ticket text."""
    outcomes: list[RuleOutcome] = []

    if facts.duplicate_verified:
        outcomes.append(
            RuleOutcome(
                reason="Duplicate charge CONFIRMED in billing records — fast-track the refund review",
                priority=Priority.HIGH,
                requires_human=True,
                tag="verified_duplicate",
            )
        )
    elif facts.duplicate_checked and _mentions_money(analysis):
        # The customer claimed a duplicate, we checked, and it is not there.
        outcomes.append(
            RuleOutcome(
                reason="Refund/duplicate claimed but NO duplicate charge found in billing records — verify before refunding",
                requires_human=True,
                tag="unverified_claim",
            )
        )

    if facts.customer_plan == "enterprise":
        outcomes.append(
            RuleOutcome(
                reason="Verified enterprise account — apply the enterprise SLA",
                priority=Priority.HIGH,
                requires_human=True,
                tag="enterprise_verified",
            )
        )

    if facts.lookup_failed and not facts.customer_found:
        outcomes.append(
            RuleOutcome(
                reason="Could not identify the customer in our systems — a human must verify identity",
                requires_human=True,
                tag="unidentified",
            )
        )

    return outcomes
