"""LLM extraction with structured output, validation and repair.

Adapted from the support platform's ``llm.py``. The reliability machinery is
identical -- constrained decoding when the backend supports it, client-side
parsing when it does not, and a repair loop driven by the actual validation
error -- because those problems are properties of talking to an LLM, not of
support tickets.

What changes is the prompt. Extraction is a transcription task: the correct
answer is on the page, so the model's job is to read it accurately and admit
when it cannot. Inventing a plausible total is the worst possible outcome for a
financial document, which is why the prompt repeatedly prefers ``null`` over a
guess.
"""

from __future__ import annotations

import time
from typing import Any, Callable

from openai import OpenAI
from pydantic import ValidationError

from . import trace
from .config import settings
from .schemas import InvoiceExtraction, schema_hint
from .telemetry import CallMetrics, MetricsCollector, estimate_tokens, new_request_id
from .textproc import extract_json, strip_think


class LLMError(RuntimeError):
    """Backend unreachable, or all repair attempts exhausted."""

    def __init__(self, message: str, *, attempts: int = 0, last_raw: str = "") -> None:
        super().__init__(message)
        self.attempts = attempts
        self.last_raw = last_raw


SYSTEM_PROMPT = f"""You extract structured data from business documents.

Read the document text and reply with a SINGLE JSON object, nothing else.
Do not wrap it in markdown fences. Do not add commentary before or after.

Schema:
{schema_hint()}

Rules:
- Transcribe, do not infer. Every value must appear in the document.
- If a field is NOT present, use null (or "" for text). NEVER guess a number.
  A missing total is recoverable; an invented one is not.
- Do NOT calculate values that are absent. If the subtotal is not printed,
  return null rather than summing the lines yourself — the checks downstream
  compare printed values against computed ones, and a filled-in gap defeats them.
- Copy amounts exactly as numbers: 1392.00, not "$1,392.00".
- Dates as YYYY-MM-DD. If the format is ambiguous (03/04/2026), prefer
  day/month unless the document clearly uses US formatting.
- "currency": the ISO code (USD, EUR, GBP, AED, ...). Use UNKNOWN if no symbol
  or code appears.
- "items": one entry per billed row. Include the header-described quantity and
  unit price when the table shows them.
- "document_type": if this is not an invoice at all, say so honestly -- a CV or
  a contract must come back as "other", not as an invoice with empty fields.
- "confidence": how well you could read the document. Low confidence on a poor
  scan is far more useful than false certainty.
- "notes": anything unreadable, ambiguous, or contradictory.
"""

REPAIR_PROMPT = """Your previous reply did not satisfy the schema.

Error:
{error}

Your previous reply:
{previous}

Reply again with ONLY the corrected JSON object. Do not explain the fix."""


def _request_extras() -> dict[str, Any]:
    """Backend-specific fields for suppressing the reasoning block."""
    if settings.enable_thinking:
        return {}
    return {
        "extra_body": {
            "chat_template_kwargs": {"enable_thinking": False},
            "reasoning_effort": "none",
        }
    }


def _schema_response_format() -> dict[str, Any]:
    """Constrain generation to the schema, built from the Pydantic model."""
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "invoice_extraction",
            "schema": InvoiceExtraction.model_json_schema(),
            "strict": True,
        },
    }


def _looks_like_schema_rejection(exc: Exception) -> bool:
    text = str(exc).lower()
    markers = (
        "response_format", "json_schema", "unsupported", "unknown field",
        "not supported", "invalid_request_error", "grammar",
    )
    return any(m in text for m in markers)


def _answer_text(message: Any) -> str:
    """Extract the answer, tolerating servers that split off reasoning."""
    content = getattr(message, "content", None) or ""
    if content.strip():
        return content
    return getattr(message, "reasoning_content", None) or ""


_TRACE_CHARS = 6000


def _truncate(text: str, limit: int = _TRACE_CHARS) -> str:
    if len(text) <= limit:
        return text
    return f"{text[:limit]}\n\n[... {len(text) - limit} more characters ...]"


def _format_messages(messages: list[dict[str, Any]]) -> str:
    return _truncate(
        "\n\n".join(
            f"─── {str(m.get('role', '?')).upper()} ───\n{m.get('content') or ''}"
            for m in messages
        )
    )


def _format_validation_error(exc: ValidationError) -> str:
    """Terse, model-friendly feedback naming the offending value."""
    parts = []
    for err in exc.errors()[:6]:
        loc = ".".join(str(p) for p in err["loc"]) or "(root)"
        got = err.get("input")
        got_repr = repr(got)[:60] if got is not None else "null"
        parts.append(f"- field '{loc}': {err['msg']} (you sent {got_repr})")
    return "\n".join(parts)


class DocumentLLM:
    """Wraps chat-completions with extraction-specific validation and repair."""

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
        self._structured_output_ok = settings.use_structured_output

    def _finish(self, record: CallMetrics, messages: list[dict[str, Any]], content: str) -> None:
        if not record.prompt_tokens:
            record.prompt_tokens = estimate_tokens(
                "".join(str(m.get("content", "")) for m in messages)
            )
        if not record.completion_tokens:
            record.completion_tokens = estimate_tokens(content)
        if not record.total_tokens:
            record.total_tokens = record.prompt_tokens + record.completion_tokens

        self.metrics.record(record)
        if self._on_call:
            self._on_call(record)

    def _complete(
        self,
        messages: list[dict[str, Any]],
        *,
        request_id: str,
        operation: str,
        attempt: int,
        document_id: str = "",
    ) -> tuple[str, CallMetrics, str]:
        """One round-trip, always producing a metrics record."""
        record = CallMetrics(
            request_id=request_id,
            operation=operation,
            model=settings.model,
            attempt=attempt,
            ticket_id=document_id,
        )

        kwargs: dict[str, Any] = {
            "model": settings.model,
            "messages": messages,
            "temperature": settings.temperature,
            "max_tokens": settings.max_tokens,
            **_request_extras(),
        }
        if self._structured_output_ok:
            kwargs["response_format"] = _schema_response_format()

        started = time.perf_counter()
        try:
            response = self.client.chat.completions.create(**kwargs)
        except Exception as exc:
            # A backend that rejects response_format should not fail the
            # document: disable the optimisation and retry unconstrained.
            if "response_format" in kwargs and _looks_like_schema_rejection(exc):
                self._structured_output_ok = False
                kwargs.pop("response_format")
                try:
                    response = self.client.chat.completions.create(**kwargs)
                except Exception as retry_exc:
                    record.latency_ms = (time.perf_counter() - started) * 1000
                    record.error = f"{type(retry_exc).__name__}: {retry_exc}"
                    self._finish(record, messages, "")
                    raise LLMError(
                        f"Model call failed against {settings.api_base}: {retry_exc}",
                        attempts=attempt,
                    ) from retry_exc
            else:
                record.latency_ms = (time.perf_counter() - started) * 1000
                record.error = f"{type(exc).__name__}: {exc}"
                self._finish(record, messages, "")
                raise LLMError(
                    f"Model call failed against {settings.api_base}: {exc}",
                    attempts=attempt,
                ) from exc

        record.latency_ms = (time.perf_counter() - started) * 1000
        record.success = True
        content = _answer_text(response.choices[0].message)
        finish_reason = getattr(response.choices[0], "finish_reason", "") or ""

        usage = getattr(response, "usage", None)
        if usage:
            record.prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
            record.completion_tokens = getattr(usage, "completion_tokens", 0) or 0
            record.total_tokens = getattr(usage, "total_tokens", 0) or 0
        self._finish(record, messages, content)

        trace.emit(
            "llm",
            f"{operation} → {record.completion_tokens} tokens in {record.latency_ms / 1000:.1f}s",
            detail=(
                f"model={settings.model} · prompt={record.prompt_tokens} tok · "
                f"completion={record.completion_tokens} tok · finish={finish_reason or 'stop'}"
            ),
            prompt=_format_messages(messages),
            response=_truncate(content),
            operation=operation,
            attempt=attempt,
        )
        return content, record, finish_reason

    def extract(
        self,
        text: str,
        *,
        document_id: str = "",
        request_id: str | None = None,
    ) -> tuple[InvoiceExtraction, str]:
        """Extract structured invoice data, repairing invalid output."""
        request_id = request_id or new_request_id()
        user_content = f"DOCUMENT TEXT:\n\n{text}"

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]

        last_error = ""
        last_raw = ""
        total_attempts = settings.max_repair_attempts + 1

        for attempt in range(1, total_attempts + 1):
            operation = "extract" if attempt == 1 else "extract_repair"
            content, record, finish_reason = self._complete(
                messages,
                request_id=request_id,
                operation=operation,
                attempt=attempt,
                document_id=document_id,
            )
            last_raw = content
            truncated = finish_reason == "length"

            try:
                payload = extract_json(content)
                extraction = InvoiceExtraction.model_validate(payload)
                trace.emit(
                    "extract",
                    "Extracted" if attempt == 1 else f"Extracted after {attempt} attempts",
                    status="ok" if attempt == 1 else "warn",
                    detail=(
                        f"{extraction.document_type.value} · vendor={extraction.vendor or '?'} · "
                        f"{extraction.currency.value} {extraction.total} · "
                        f"{len(extraction.items)} line item(s) · "
                        f"confidence={extraction.confidence:.2f}"
                    ),
                    attempts=attempt,
                )
                return extraction, request_id
            except ValidationError as exc:
                last_error = _format_validation_error(exc)
            except ValueError as exc:
                if truncated:
                    # A long invoice can exhaust the budget mid-array. Saying so
                    # is far more useful than "malformed JSON".
                    last_error = (
                        f"response hit the {settings.max_tokens}-token limit and was "
                        f"cut off before the JSON was complete (raise DI_MAX_TOKENS)"
                    )
                else:
                    last_error = str(exc)

            # HTTP succeeded but the contract was not met.
            record.success = False
            record.error = last_error[:500]
            trace.emit(
                "extract",
                f"Attempt {attempt} failed validation",
                status="fail",
                detail=last_error,
                attempt=attempt,
            )

            if attempt < total_attempts:
                messages = [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_content},
                    {"role": "assistant", "content": strip_think(content)[:2000]},
                    {
                        "role": "user",
                        "content": REPAIR_PROMPT.format(
                            error=last_error, previous=strip_think(content)[:1000]
                        ),
                    },
                ]

        raise LLMError(
            f"Model failed to produce valid output after {total_attempts} attempts. "
            f"Last error: {last_error}",
            attempts=total_attempts,
            last_raw=last_raw,
        )
