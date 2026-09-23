"""Per-request cost and latency telemetry.

Even against a free local model this matters: latency and token counts are how
you spot prompt bloat, runaway ``<think>`` blocks and retry storms. Recording a
notional price per 1k tokens also lets you answer "what would this traffic cost
on a hosted API?" without changing any code.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

from .config import settings


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class CallMetrics:
    """One LLM round-trip (a retry is its own record, sharing ``request_id``)."""

    request_id: str
    operation: str
    model: str
    attempt: int = 1
    latency_ms: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    success: bool = False
    error: str = ""
    ticket_id: str = ""
    created_at: str = field(default_factory=_now_iso)

    @property
    def cost_usd(self) -> float:
        return (
            self.prompt_tokens / 1000 * settings.cost_per_1k_input
            + self.completion_tokens / 1000 * settings.cost_per_1k_output
        )

    def as_dict(self) -> dict:
        d = asdict(self)
        d["cost_usd"] = round(self.cost_usd, 6)
        return d


class Timer:
    """Context manager that records wall-clock milliseconds."""

    def __init__(self) -> None:
        self.ms: float = 0.0
        self._start: float = 0.0

    def __enter__(self) -> "Timer":
        self._start = time.perf_counter()
        return self

    def __exit__(self, *exc) -> None:
        self.ms = (time.perf_counter() - self._start) * 1000
        return None


def new_request_id() -> str:
    return uuid.uuid4().hex[:12]


def estimate_tokens(text: str) -> int:
    """Rough fallback when the server omits a usage block (~4 chars/token)."""
    return max(1, len(text) // 4)


class MetricsCollector:
    """In-memory aggregate view; the durable copy lives in SQLite."""

    def __init__(self) -> None:
        self.calls: list[CallMetrics] = []

    def record(self, metrics: CallMetrics) -> CallMetrics:
        self.calls.append(metrics)
        return metrics

    def summary(self) -> dict:
        if not self.calls:
            return {
                "calls": 0, "successes": 0, "failures": 0, "success_rate": 0.0,
                "retries": 0, "avg_latency_ms": 0.0, "p95_latency_ms": 0.0,
                "total_latency_ms": 0.0, "prompt_tokens": 0, "completion_tokens": 0,
                "total_tokens": 0, "cost_usd": 0.0,
            }

        latencies = sorted(c.latency_ms for c in self.calls)
        successes = sum(1 for c in self.calls if c.success)
        idx = max(0, int(len(latencies) * 0.95) - 1)

        return {
            "calls": len(self.calls),
            "successes": successes,
            "failures": len(self.calls) - successes,
            "success_rate": round(successes / len(self.calls), 3),
            "retries": sum(1 for c in self.calls if c.attempt > 1),
            "avg_latency_ms": round(sum(latencies) / len(latencies), 1),
            "p95_latency_ms": round(latencies[idx], 1),
            "total_latency_ms": round(sum(latencies), 1),
            "prompt_tokens": sum(c.prompt_tokens for c in self.calls),
            "completion_tokens": sum(c.completion_tokens for c in self.calls),
            "total_tokens": sum(c.total_tokens for c in self.calls),
            "cost_usd": round(sum(c.cost_usd for c in self.calls), 6),
        }
