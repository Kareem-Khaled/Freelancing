"""Support platform: LLM-driven customer ticket triage."""

from .config import settings
from .llm import LLMError, SupportLLM
from .pipeline import SupportPipeline, TicketResult
from .schemas import Category, Entity, Priority, Sentiment, TicketAnalysis
from .storage import Database
from .telemetry import CallMetrics, MetricsCollector
from .validation import InputProblem, validate_message

__all__ = [
    "settings",
    "SupportPipeline",
    "TicketResult",
    "SupportLLM",
    "LLMError",
    "TicketAnalysis",
    "Category",
    "Priority",
    "Sentiment",
    "Entity",
    "Database",
    "CallMetrics",
    "MetricsCollector",
    "InputProblem",
    "validate_message",
]
