"""Grounded answering with verified citations.

The product promise is "answers from these documents, not from the model's
general knowledge". Two mechanisms enforce it, and neither is the prompt alone:

1. **Refusal when retrieval is empty.** If nothing relevant was found, the model
   is never asked the question. It cannot answer from memory if it is not
   invoked.

2. **Citation verification after generation.** Every ``[n]`` marker is resolved
   against the passages actually supplied. A marker pointing at a passage that
   was not retrieved is a fabrication, and it is reported rather than rendered.

The second point is the important one. Asking a model to "only use the context"
is a request; checking which sources it cited is a measurement. This project has
repeatedly found that instructions are followed *usually*, which is not the same
as *always* -- and for an internal policy assistant, a confidently wrong answer
about refund eligibility is worse than no answer.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from openai import OpenAI

from . import trace
from .config import settings
from .retrieval import RetrievalResult
from .telemetry import CallMetrics, MetricsCollector, estimate_tokens, new_request_id
from .textproc import strip_think


class AnswerError(RuntimeError):
    """The backend was unreachable."""


SYSTEM_PROMPT = """You answer questions using ONLY the provided context passages.

Rules:
- Every factual claim must come from the passages. Never use outside knowledge.
- Cite the passage number in square brackets after each claim, like [1] or [2][3].
- If the passages do not contain the answer, say exactly:
  "I could not find this in the available documents."
  Do not guess, and do not fill the gap from general knowledge.
- If the passages partially answer the question, answer that part and say
  plainly what is missing.
- Quote exact figures, dates and conditions rather than paraphrasing them.
- Be concise. Two or three sentences is usually enough.
- Never invent a passage number. Only cite numbers that appear in the context."""

REFUSAL = "I could not find this in the available documents."

# Matches [1], [2][3], [1, 2] -- models are inconsistent about the format.
_CITATION = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]")


@dataclass
class Citation:
    """A resolved reference from the answer back to a source passage."""

    marker: int
    document_id: str
    filename: str
    chunk_index: int
    heading: str
    text: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "marker": self.marker,
            "document_id": self.document_id,
            "filename": self.filename,
            "chunk_index": self.chunk_index,
            "heading": self.heading,
            "snippet": self.text[:320],
        }


@dataclass
class Answer:
    """An answer plus the evidence for it."""

    question: str
    text: str
    citations: list[Citation] = field(default_factory=list)
    grounded: bool = False
    refused: bool = False
    invalid_citations: list[int] = field(default_factory=list)
    uncited_answer: bool = False
    retrieval: RetrievalResult | None = None
    request_id: str = ""
    latency_ms: float = 0.0

    @property
    def warnings(self) -> list[str]:
        """Problems a reader should know about before trusting this."""
        issues = []
        if self.invalid_citations:
            issues.append(
                f"Answer cited passage(s) {self.invalid_citations} that were not "
                f"retrieved — those claims are unverified."
            )
        if self.uncited_answer and not self.refused:
            issues.append(
                "Answer contains no citations, so it cannot be traced to a source."
            )
        return issues

    def as_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "answer": self.text,
            "citations": [c.as_dict() for c in self.citations],
            "grounded": self.grounded,
            "refused": self.refused,
            "warnings": self.warnings,
            "request_id": self.request_id,
            "latency_ms": round(self.latency_ms, 1),
            "retrieval": self.retrieval.as_dict() if self.retrieval else None,
        }


def _request_extras() -> dict[str, Any]:
    if settings.enable_thinking:
        return {}
    return {
        "extra_body": {
            "chat_template_kwargs": {"enable_thinking": False},
            "reasoning_effort": "none",
        }
    }


def parse_citations(text: str) -> list[int]:
    """Extract every passage number referenced in an answer."""
    markers: list[int] = []
    for group in _CITATION.findall(text):
        for part in group.split(","):
            try:
                markers.append(int(part.strip()))
            except ValueError:
                continue
    return markers


class Answerer:
    """Generates answers that are grounded in retrieved passages."""

    def __init__(
        self,
        metrics: MetricsCollector | None = None,
        on_call: Callable[[CallMetrics], None] | None = None,
    ) -> None:
        self.client = OpenAI(
            base_url=settings.api_base,
            api_key=settings.api_key,
            timeout=settings.request_timeout,
        )
        self.metrics = metrics or MetricsCollector()
        self._on_call = on_call

    def _complete(
        self, messages: list[dict[str, str]], *, request_id: str
    ) -> tuple[str, CallMetrics]:
        record = CallMetrics(
            request_id=request_id,
            operation="answer",
            model=settings.model,
            attempt=1,
        )

        started = time.perf_counter()
        try:
            response = self.client.chat.completions.create(
                model=settings.model,
                messages=messages,
                temperature=settings.temperature,
                max_tokens=settings.max_tokens,
                **_request_extras(),
            )
        except Exception as exc:
            record.latency_ms = (time.perf_counter() - started) * 1000
            record.error = f"{type(exc).__name__}: {exc}"
            self._finish(record, messages, "")
            raise AnswerError(
                f"Model call failed against {settings.api_base}: {exc}"
            ) from exc

        record.latency_ms = (time.perf_counter() - started) * 1000
        record.success = True

        message = response.choices[0].message
        content = getattr(message, "content", None) or ""
        if not content.strip():
            content = getattr(message, "reasoning_content", None) or ""

        usage = getattr(response, "usage", None)
        if usage:
            record.prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
            record.completion_tokens = getattr(usage, "completion_tokens", 0) or 0
            record.total_tokens = getattr(usage, "total_tokens", 0) or 0
        self._finish(record, messages, content)

        trace.emit(
            "llm",
            f"answer → {record.completion_tokens} tokens in {record.latency_ms / 1000:.1f}s",
            detail=(
                f"model={settings.model} · prompt={record.prompt_tokens} tok · "
                f"completion={record.completion_tokens} tok"
            ),
            prompt="\n\n".join(
                f"─── {m['role'].upper()} ───\n{m['content']}" for m in messages
            )[:6000],
            response=content[:6000],
        )
        return content, record

    def _finish(
        self, record: CallMetrics, messages: list[dict[str, str]], content: str
    ) -> None:
        if not record.prompt_tokens:
            record.prompt_tokens = estimate_tokens(
                "".join(m.get("content", "") for m in messages)
            )
        if not record.completion_tokens:
            record.completion_tokens = estimate_tokens(content)
        if not record.total_tokens:
            record.total_tokens = record.prompt_tokens + record.completion_tokens
        self.metrics.record(record)
        if self._on_call:
            self._on_call(record)

    def answer(self, question: str, retrieval: RetrievalResult) -> Answer:
        """Answer a question from retrieved passages, or refuse."""
        started = time.perf_counter()
        request_id = new_request_id()

        # No context: refuse without calling the model at all. This is the
        # strongest possible grounding guarantee -- a model that is never asked
        # cannot answer from memory.
        if retrieval.is_empty:
            trace.emit(
                "answer",
                "Refused — nothing relevant retrieved",
                status="warn",
                detail="No passage scored above the relevance threshold.",
            )
            return Answer(
                question=question,
                text=REFUSAL,
                refused=True,
                grounded=False,
                retrieval=retrieval,
                request_id=request_id,
                latency_ms=(time.perf_counter() - started) * 1000,
            )

        context = retrieval.context()
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"CONTEXT PASSAGES:\n\n{context}\n\n"
                    f"QUESTION: {question}\n\n"
                    f"Answer using only the passages above, citing each claim."
                ),
            },
        ]

        raw, _ = self._complete(messages, request_id=request_id)
        text = strip_think(raw).strip()

        answer = Answer(
            question=question,
            text=text,
            retrieval=retrieval,
            request_id=request_id,
        )

        # --- verify the citations ------------------------------------
        markers = parse_citations(text)
        available = len(retrieval.chunks)

        for marker in sorted(set(markers)):
            if 1 <= marker <= available:
                source = retrieval.chunks[marker - 1].chunk
                answer.citations.append(
                    Citation(
                        marker=marker,
                        document_id=source.document_id,
                        filename=source.filename,
                        chunk_index=source.chunk_index,
                        heading=source.heading,
                        text=source.text,
                    )
                )
            else:
                # A marker outside the supplied range is invented. The model
                # was given N passages; [N+1] refers to nothing.
                answer.invalid_citations.append(marker)

        answer.refused = REFUSAL.lower()[:30] in text.lower()
        answer.uncited_answer = not markers and not answer.refused
        answer.grounded = bool(answer.citations) and not answer.invalid_citations
        answer.latency_ms = (time.perf_counter() - started) * 1000

        status = "ok" if answer.grounded else "warn"
        detail = f"{len(answer.citations)} citation(s) verified"
        if answer.invalid_citations:
            detail += f" · INVALID markers {answer.invalid_citations}"
        if answer.uncited_answer:
            detail += " · no citations given"
        trace.emit(
            "answer",
            "Refused" if answer.refused else ("Answered" if answer.grounded else "Answered, unverified"),
            status="warn" if answer.refused else status,
            detail=detail,
        )
        return answer
