"""Pydantic schemas for ticket analysis.

The model is a local Qwen build that does not honour constrained decoding, so
it happily returns ``"High"`` where we expect ``"high"``, or invents values such
as ``"super-important"``. Rather than failing on every cosmetic mismatch we run
a *normalisation* pass first (``mode="before"`` validators) and only surface a
validation error when the value is genuinely unmappable -- at which point the
LLM layer retries with the error text as feedback.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, ValidationError, field_validator

__all__ = [
    "Category",
    "Priority",
    "Sentiment",
    "Entity",
    "TicketAnalysis",
    "ValidationError",
]


class Category(str, Enum):
    BILLING = "billing"
    TECHNICAL = "technical"
    ACCOUNT = "account"
    SHIPPING = "shipping"
    FEATURE_REQUEST = "feature_request"
    COMPLAINT = "complaint"
    # Nothing to do with the product: homework, recipes, general chat, or an
    # attempt to use the support bot as a free assistant.
    OUT_OF_SCOPE = "out_of_scope"
    OTHER = "other"


class Priority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Sentiment(str, Enum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


class Action(str, Enum):
    """What the agent should do next.

    A CLOSED set, deliberately. This started as a free-form string and the model
    invented 40 distinct values across ~80 tickets -- including three spellings
    of "ask the customer for more detail" and two of "send this to a human".
    That is unusable: you cannot build a queue filter, a dashboard chart or an
    automation on a field whose values are invented per request.

    Keep this list SHORT. Each value is a genuinely different next step, not a
    description of the problem (that is what ``issue`` is for).
    """

    # Safe to send without review -- see _AUTO_SAFE_ACTIONS in rules.py
    ANSWER_QUESTION = "answer_question"
    REQUEST_MORE_INFO = "request_more_info"
    ACKNOWLEDGE = "acknowledge"

    # Needs a human, but routine
    TROUBLESHOOT = "troubleshoot"
    VERIFY_IDENTITY = "verify_identity"
    INVESTIGATE_BILLING = "investigate_billing"

    # High-risk: money, cancellation, or specialist teams
    PROCESS_REFUND = "process_refund"
    CANCEL_SUBSCRIPTION = "cancel_subscription"
    ESCALATE_TECHNICAL = "escalate_technical"
    ESCALATE_BILLING = "escalate_billing"
    ESCALATE_LEGAL = "escalate_legal"
    ESCALATE_SECURITY = "escalate_security"

    # Fallbacks
    ROUTE_TO_HUMAN = "route_to_human"
    CLOSE_TICKET = "close_ticket"
    # Politely decline a request that is not about the product. Deliberately NOT
    # on the auto-send allow-list in rules.py -- see _rule_out_of_scope.
    DECLINE_OUT_OF_SCOPE = "decline_out_of_scope"


# ----------------------------------------------------------------------
# Synonym tables used to repair model output before validation.
# Keys must be lowercase and stripped of non-alphanumerics.
# ----------------------------------------------------------------------
_PRIORITY_SYNONYMS = {
    "superimportant": Priority.HIGH,
    "veryhigh": Priority.HIGH,
    "urgent": Priority.HIGH,
    "critical": Priority.HIGH,
    "severe": Priority.HIGH,
    "blocker": Priority.HIGH,
    "p0": Priority.HIGH,
    "p1": Priority.HIGH,
    "normal": Priority.MEDIUM,
    "moderate": Priority.MEDIUM,
    "standard": Priority.MEDIUM,
    "average": Priority.MEDIUM,
    "p2": Priority.MEDIUM,
    "minor": Priority.LOW,
    "trivial": Priority.LOW,
    "verylow": Priority.LOW,
    "p3": Priority.LOW,
    "p4": Priority.LOW,
}

_CATEGORY_SYNONYMS = {
    "payment": Category.BILLING,
    "payments": Category.BILLING,
    "invoice": Category.BILLING,
    "invoicing": Category.BILLING,
    "charge": Category.BILLING,
    "refund": Category.BILLING,
    "subscription": Category.BILLING,
    "paymentissue": Category.BILLING,
    "bug": Category.TECHNICAL,
    "error": Category.TECHNICAL,
    "outage": Category.TECHNICAL,
    "technicalsupport": Category.TECHNICAL,
    "tech": Category.TECHNICAL,
    "login": Category.ACCOUNT,
    "auth": Category.ACCOUNT,
    "authentication": Category.ACCOUNT,
    "password": Category.ACCOUNT,
    "profile": Category.ACCOUNT,
    "delivery": Category.SHIPPING,
    "order": Category.SHIPPING,
    "fulfilment": Category.SHIPPING,
    "fulfillment": Category.SHIPPING,
    "featurerequest": Category.FEATURE_REQUEST,
    "feature": Category.FEATURE_REQUEST,
    "enhancement": Category.FEATURE_REQUEST,
    "suggestion": Category.FEATURE_REQUEST,
    "complaint": Category.COMPLAINT,
    "unhappy": Category.COMPLAINT,
    "misc": Category.OTHER,
    "general": Category.OTHER,
    "unknown": Category.OTHER,
    "uncategorized": Category.OTHER,
}

_SENTIMENT_SYNONYMS = {
    "angry": Sentiment.NEGATIVE,
    "frustrated": Sentiment.NEGATIVE,
    "upset": Sentiment.NEGATIVE,
    "annoyed": Sentiment.NEGATIVE,
    "verynegative": Sentiment.NEGATIVE,
    "bad": Sentiment.NEGATIVE,
    "mixed": Sentiment.NEUTRAL,
    "unknown": Sentiment.NEUTRAL,
    "none": Sentiment.NEUTRAL,
    "ok": Sentiment.NEUTRAL,
    "happy": Sentiment.POSITIVE,
    "satisfied": Sentiment.POSITIVE,
    "pleased": Sentiment.POSITIVE,
    "grateful": Sentiment.POSITIVE,
    "good": Sentiment.POSITIVE,
}

# Real values the model produced when ``suggested_action`` was a free-form
# string, mapped onto the closed enum. Slugs are lowercase and alphanumeric-only,
# so "request_more_details" is keyed as "requestmoredetails".
_ACTION_SYNONYMS = {
    # ask the customer for something
    "requestmoredetails": Action.REQUEST_MORE_INFO,
    "requestmoreinformation": Action.REQUEST_MORE_INFO,
    "requestaccountdetails": Action.REQUEST_MORE_INFO,
    "requestaccountidentifier": Action.REQUEST_MORE_INFO,
    "requestaccountidentification": Action.REQUEST_MORE_INFO,
    "requestidentification": Action.REQUEST_MORE_INFO,
    "requestplaintext": Action.REQUEST_MORE_INFO,
    "identifyspecificissue": Action.REQUEST_MORE_INFO,
    "greetandaskfordetails": Action.REQUEST_MORE_INFO,
    "waitforclarification": Action.REQUEST_MORE_INFO,
    "askforinformation": Action.REQUEST_MORE_INFO,
    # simple replies
    "greetcustomer": Action.ACKNOWLEDGE,
    "respondtogreeting": Action.ACKNOWLEDGE,
    "respondgreeting": Action.ACKNOWLEDGE,
    "sendfriendlyacknowledgment": Action.ACKNOWLEDGE,
    "acknowledgefeedback": Action.ACKNOWLEDGE,
    "provideinformation": Action.ANSWER_QUESTION,
    "providecompanyinfo": Action.ANSWER_QUESTION,
    "sharedocumentation": Action.ANSWER_QUESTION,
    "generalinquiryresponse": Action.ANSWER_QUESTION,
    # identity / access
    "verifycredentialsandresetpassword": Action.VERIFY_IDENTITY,
    "accountverification": Action.VERIFY_IDENTITY,
    "investigateaccountaccess": Action.VERIFY_IDENTITY,
    # technical
    "troubleshootloginissue": Action.TROUBLESHOOT,
    "logintroubleshooting": Action.TROUBLESHOOT,
    "escalatetotechnicalsupport": Action.ESCALATE_TECHNICAL,
    "escalatetoengineering": Action.ESCALATE_TECHNICAL,
    # billing
    "investigateduplicatecharge": Action.INVESTIGATE_BILLING,
    "investigatepaymentfailure": Action.INVESTIGATE_BILLING,
    "reviewduplicatecharge": Action.INVESTIGATE_BILLING,
    "reviewbillingdispute": Action.INVESTIGATE_BILLING,
    "billingsupportinquiry": Action.INVESTIGATE_BILLING,
    "escalatetobilling": Action.ESCALATE_BILLING,
    # money movement
    "refundonepayment": Action.PROCESS_REFUND,
    "issuerefund": Action.PROCESS_REFUND,
    "verifytransactionandrefund": Action.PROCESS_REFUND,
    "issuecredit": Action.PROCESS_REFUND,
    "processchargeback": Action.PROCESS_REFUND,
    "waivefee": Action.PROCESS_REFUND,
    # escalation
    "escalatetoseniorsupport": Action.ROUTE_TO_HUMAN,
    "escalatetoseniragent": Action.ROUTE_TO_HUMAN,
    "escalatetoseniragent2": Action.ROUTE_TO_HUMAN,
    "escalatetohuman": Action.ROUTE_TO_HUMAN,
    "routetotranslator": Action.ROUTE_TO_HUMAN,
    "escalatetolegalandbilling": Action.ESCALATE_LEGAL,
    "escalatetolegal": Action.ESCALATE_LEGAL,
    # closing
    "closeticketnonactionable": Action.CLOSE_TICKET,
    "noactionneeded": Action.CLOSE_TICKET,
}


def _slug(value: Any) -> str:
    """Lowercase and strip everything that is not a letter or digit."""
    return "".join(ch for ch in str(value).lower() if ch.isalnum())


def _coerce_enum(value: Any, enum_cls: type[Enum], synonyms: dict[str, Any]) -> Any:
    """Best-effort mapping of a loose model value onto a strict enum.

    Returns the original value untouched when no mapping is found so that
    Pydantic raises a descriptive error we can feed back to the model.
    """
    if isinstance(value, enum_cls):
        return value
    if value is None:
        return value
    if isinstance(value, list) and value:  # model sometimes returns ["billing"]
        value = value[0]

    slug = _slug(value)
    if not slug:
        return value

    # Exact match against the canonical values (handles "High" -> "high").
    for member in enum_cls:
        if _slug(member.value) == slug:
            return member

    if slug in synonyms:
        return synonyms[slug]

    # Substring fallback: "billing_issue" -> billing, "high priority" -> high.
    for member in enum_cls:
        if _slug(member.value) and _slug(member.value) in slug:
            return member
    for key, member in synonyms.items():
        if key in slug:
            return member

    return value


_TRUTHY = {"true", "yes", "y", "1", "required", "needed", "human", "escalate"}
_FALSY = {"false", "no", "n", "0", "notrequired", "notneeded", "auto", "none"}

# Models sometimes return a language name instead of an ISO 639-1 code.
_LANGUAGE_NAMES = {
    "english": "en",
    "arabic": "ar",
    "french": "fr",
    "francais": "fr",
    "german": "de",
    "deutsch": "de",
    "spanish": "es",
    "espanol": "es",
    "portuguese": "pt",
    "italian": "it",
    "dutch": "nl",
    "russian": "ru",
    "chinese": "zh",
    "mandarin": "zh",
    "japanese": "ja",
    "korean": "ko",
    "hindi": "hi",
    "turkish": "tr",
    "hebrew": "he",
    "unknown": "en",
}


class Entity(BaseModel):
    """A structured fact extracted from the ticket (amount, date, order id...)."""

    type: str = Field(description="Entity type, e.g. amount, date, order_id")
    value: str = Field(description="Raw value as it appeared in the ticket")

    @field_validator("type", "value", mode="before")
    @classmethod
    def _stringify(cls, v: Any) -> str:
        if v is None:
            return ""
        return str(v).strip()


class TicketAnalysis(BaseModel):
    """The structured analysis the pipeline persists and shows on the dashboard."""

    model_config = {"use_enum_values": False, "extra": "ignore"}

    category: Category
    priority: Priority
    sentiment: Sentiment
    # ISO 639-1 code of the language the CUSTOMER wrote in. Detected by the
    # model rather than a separate library: it is already reading the text, and
    # it needs to know the language anyway in order to reply in it.
    language: str = Field(default="en", description="ISO 639-1 code, e.g. en, ar, fr, de")
    issue: str = Field(description="Short description of the problem, always in English")
    entities: list[Entity] = Field(default_factory=list)
    suggested_action: Action = Field(
        default=Action.ROUTE_TO_HUMAN, description="What the agent should do next"
    )
    requires_human: bool = True
    draft_response: str = Field(description="Reply, written in the customer's own language")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)

    # -- normalisation ------------------------------------------------
    @field_validator("language", mode="before")
    @classmethod
    def _fix_language(cls, v: Any) -> str:
        """Normalise whatever the model returns into a bare ISO 639-1 code.

        Models variously return "en", "EN", "en-US", "English" or a list. Anything
        unrecognisable falls back to English rather than failing validation --
        the language is metadata, not worth a repair round.
        """
        if v is None:
            return "en"
        if isinstance(v, (list, tuple)) and v:
            v = v[0]
        text = str(v).strip().lower()
        if not text:
            return "en"

        # "en-us" / "en_gb" -> "en"
        text = re.split(r"[-_]", text)[0]

        if len(text) == 2 and text.isalpha():
            return text
        return _LANGUAGE_NAMES.get(text, "en")
    @field_validator("category", mode="before")
    @classmethod
    def _fix_category(cls, v: Any) -> Any:
        return _coerce_enum(v, Category, _CATEGORY_SYNONYMS)

    @field_validator("priority", mode="before")
    @classmethod
    def _fix_priority(cls, v: Any) -> Any:
        return _coerce_enum(v, Priority, _PRIORITY_SYNONYMS)

    @field_validator("sentiment", mode="before")
    @classmethod
    def _fix_sentiment(cls, v: Any) -> Any:
        return _coerce_enum(v, Sentiment, _SENTIMENT_SYNONYMS)

    @field_validator("suggested_action", mode="before")
    @classmethod
    def _fix_action(cls, v: Any) -> Any:
        """Map a loose action onto the closed enum.

        Unlike the other enums this falls back to ROUTE_TO_HUMAN instead of
        letting validation fail. An unmappable action is not worth a repair
        round: sending the ticket to a person is always a safe answer, and the
        value is logged so genuinely new actions can be added deliberately.
        """
        if v is None:
            return Action.ROUTE_TO_HUMAN
        coerced = _coerce_enum(v, Action, _ACTION_SYNONYMS)
        if isinstance(coerced, Action):
            return coerced
        return Action.ROUTE_TO_HUMAN

    @field_validator("requires_human", mode="before")
    @classmethod
    def _fix_requires_human(cls, v: Any) -> Any:
        if isinstance(v, bool) or v is None:
            return True if v is None else v
        slug = _slug(v)
        if slug in _TRUTHY:
            return True
        if slug in _FALSY:
            return False
        return v

    @field_validator("confidence", mode="before")
    @classmethod
    def _fix_confidence(cls, v: Any) -> Any:
        if v is None:
            return 0.5
        if isinstance(v, str):
            s = v.strip().rstrip("%")
            try:
                num = float(s)
            except ValueError:
                return {"low": 0.3, "medium": 0.6, "high": 0.9}.get(_slug(v), 0.5)
            return num / 100 if "%" in v else num
        if isinstance(v, (int, float)):
            # Model sometimes reports 85 instead of 0.85.
            return v / 100 if v > 1 else v
        return v

    @field_validator("issue", "draft_response", mode="before")
    @classmethod
    def _clean_text(cls, v: Any) -> str:
        if v is None:
            return ""
        if isinstance(v, (list, tuple)):
            v = " ".join(str(item) for item in v)
        return str(v).strip()

    @field_validator("entities", mode="before")
    @classmethod
    def _fix_entities(cls, v: Any) -> Any:
        """Accept the several shapes the model uses for entities."""
        if v is None:
            return []
        if isinstance(v, dict):
            # {"amount": "$20", "date": "Monday"} -> [{type, value}, ...]
            return [{"type": k, "value": val} for k, val in v.items()]
        if isinstance(v, list):
            out = []
            for item in v:
                if isinstance(item, dict):
                    if "type" in item and "value" in item:
                        out.append(item)
                    else:
                        out.extend({"type": k, "value": val} for k, val in item.items())
                elif item is not None:
                    out.append({"type": "misc", "value": str(item)})
            return out
        return [{"type": "misc", "value": str(v)}]


def schema_hint() -> str:
    """Compact, human-readable schema description embedded in the prompt."""
    return (
        "{\n"
        f'  "language": ISO 639-1 code of the CUSTOMER\'s message ("en", "ar", "fr", "de", ...),\n'
        f'  "category": one of {[c.value for c in Category]},\n'
        f'  "priority": one of {[p.value for p in Priority]},\n'
        f'  "sentiment": one of {[s.value for s in Sentiment]},\n'
        '  "issue": "short description of the problem, ALWAYS IN ENGLISH",\n'
        '  "entities": [{"type": "amount|date|order_id|email|...", "value": "..."}],\n'
        f'  "suggested_action": one of {[a.value for a in Action]},\n'
        '  "requires_human": true or false,\n'
        '  "draft_response": "reply to the customer, IN THE CUSTOMER\'S OWN LANGUAGE",\n'
        '  "confidence": number between 0 and 1\n'
        "}"
    )
