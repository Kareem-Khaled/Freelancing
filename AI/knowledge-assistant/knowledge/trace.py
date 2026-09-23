"""Live execution trace for the pipeline.

The dashboard shows a spinner for the ~19 seconds a grounded ticket takes, which
hides everything interesting: which tools ran, what they returned, whether a
repair round fired, which business rules decided the outcome.

This module lets each stage publish an event as it happens. The web layer
attaches a collector per job and polls it, so the UI can render the phases live
instead of only showing the final result.

Design notes:

* **Opt-in and inert by default.** ``emit`` does nothing unless a collector is
  attached to the current thread, so the CLI and tests are unaffected and pay
  no cost.
* **Thread-local.** The web server runs one worker thread; a thread-local
  collector means two concurrent jobs can never interleave each other's trace.
* **Never raises.** Tracing is diagnostics. A bug here must not break ticket
  processing, so ``emit`` swallows its own errors.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any

__all__ = ["TraceEvent", "TraceCollector", "emit", "use_collector", "current"]


@dataclass
class TraceEvent:
    """One thing that happened, in order."""

    phase: str          # validate | research | tool | analyse | rules | store | llm
    label: str          # short human-readable summary
    status: str = "ok"  # ok | fail | warn | start
    detail: str = ""    # longer text, shown on expand
    data: dict[str, Any] = field(default_factory=dict)
    elapsed_ms: float = 0.0
    at: float = field(default_factory=time.time)
    # Raw model exchange, attached to "llm" events only. Kept separate from
    # ``detail`` so the UI can render it in a collapsed <pre> block rather than
    # flooding the timeline.
    prompt: str = ""
    response: str = ""

    def as_dict(self) -> dict[str, Any]:
        payload = {
            "phase": self.phase,
            "label": self.label,
            "status": self.status,
            "detail": self.detail,
            "data": self.data,
            "elapsed_ms": round(self.elapsed_ms, 1),
        }
        if self.prompt:
            payload["prompt"] = self.prompt
        if self.response:
            payload["response"] = self.response
        return payload


class TraceCollector:
    """Thread-safe, ordered list of events for a single ticket."""

    def __init__(self) -> None:
        self._events: list[TraceEvent] = []
        self._lock = threading.Lock()
        self._started = time.perf_counter()

    def add(self, event: TraceEvent) -> None:
        with self._lock:
            if not event.elapsed_ms:
                event.elapsed_ms = (time.perf_counter() - self._started) * 1000
            self._events.append(event)

    def snapshot(self) -> list[dict[str, Any]]:
        """Everything recorded so far. Safe to call while the job is running."""
        with self._lock:
            return [e.as_dict() for e in self._events]


_local = threading.local()


def current() -> TraceCollector | None:
    return getattr(_local, "collector", None)


class use_collector:
    """Context manager attaching a collector for the duration of a block."""

    def __init__(self, collector: TraceCollector | None) -> None:
        self.collector = collector
        self._previous: TraceCollector | None = None

    def __enter__(self) -> TraceCollector | None:
        self._previous = current()
        _local.collector = self.collector
        return self.collector

    def __exit__(self, *exc: Any) -> None:
        _local.collector = self._previous


def emit(
    phase: str,
    label: str,
    *,
    status: str = "ok",
    detail: str = "",
    prompt: str = "",
    response: str = "",
    **data: Any,
) -> None:
    """Record an event, if anything is listening. Never raises."""
    collector = current()
    if collector is None:
        return
    try:
        collector.add(
            TraceEvent(
                phase=phase,
                label=label,
                status=status,
                detail=detail,
                prompt=prompt,
                response=response,
                data=data,
            )
        )
    except Exception:  # pragma: no cover - diagnostics must never break triage
        pass
