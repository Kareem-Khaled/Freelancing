"""End-to-end document pipeline: parse -> extract -> validate -> persist.

The orchestration layer, mirroring the support platform's ``pipeline.py``. It is
the only module that knows about storage, the LLM and parsing together, which
keeps the others independently testable.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from . import trace
from .llm import DocumentLLM, LLMError
from .parsing import ParseProblem, ParseResult, parse_document
from .schemas import InvoiceExtraction
from .storage import Database
from .telemetry import CallMetrics, MetricsCollector, new_request_id
from .validation import ReviewStatus, ValidationReport, validate


class DocumentStatus(str, Enum):
    """Lifecycle of an uploaded document."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ProcessResult:
    """Outcome of processing one document."""

    document_id: str
    ok: bool
    extraction: InvoiceExtraction | None = None
    report: ValidationReport | None = None
    request_id: str = ""
    error: str = ""
    problem: ParseProblem | None = None
    doc_format: str = ""
    pages: int = 0
    truncated: bool = False
    calls: list[CallMetrics] = field(default_factory=list)

    @property
    def attempts(self) -> int:
        return len(self.calls)

    @property
    def latency_ms(self) -> float:
        return round(sum(c.latency_ms for c in self.calls), 1)

    def as_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "document_id": self.document_id,
            "ok": self.ok,
            "request_id": self.request_id,
            "attempts": self.attempts,
            "latency_ms": self.latency_ms,
            "doc_format": self.doc_format,
            "pages": self.pages,
        }
        if self.extraction:
            data["extraction"] = self.extraction.model_dump(mode="json")
        if self.report:
            data["validation"] = self.report.as_dict()
        if self.error:
            data["error"] = self.error
        if self.problem:
            data["problem"] = self.problem.value
        if self.truncated:
            data["truncated"] = True
        return data


class DocumentPipeline:
    """Processes documents and records everything about the run.

    Safe to share across threads: the per-request metrics buffer is
    thread-local, so concurrent uploads cannot interleave each other's
    telemetry.
    """

    def __init__(self, db: Database | None = None, llm: DocumentLLM | None = None) -> None:
        self.db = db or Database()
        self.metrics = MetricsCollector()
        self._local = threading.local()
        self.llm = llm or DocumentLLM(metrics=self.metrics, on_call=self._on_call)

    @property
    def _call_buffer(self) -> list[CallMetrics]:
        if not hasattr(self._local, "calls"):
            self._local.calls = []
        return self._local.calls

    def _reset_calls(self) -> None:
        self._local.calls = []

    def _on_call(self, record: CallMetrics) -> None:
        """Buffer the attempt; persisted once its outcome is final.

        A call can succeed at the HTTP layer and fail validation a moment later,
        so writing here would record a misleading success.
        """
        self._call_buffer.append(record)

    def _flush_calls(self) -> None:
        """Persist buffered metrics once their outcome is final.

        Telemetry must never break processing, but it must also never fail
        *silently*: a bare ``except: pass`` here hid a missing settings field and
        produced a metrics dashboard that confidently reported zero calls. The
        error is swallowed for the caller and surfaced in the trace.
        """
        for record in self._call_buffer:
            try:
                self.db.save_call(record)
            except Exception as exc:  # noqa: BLE001
                trace.emit(
                    "store",
                    "Failed to persist call metrics",
                    status="fail",
                    detail=f"{type(exc).__name__}: {exc}",
                )

    # -- public API ----------------------------------------------------
    def process(
        self,
        data: bytes,
        *,
        filename: str = "",
        content_type: str = "",
        document_id: str | None = None,
    ) -> ProcessResult:
        """Parse, extract and validate one uploaded document."""
        document_id = document_id or f"DOC-{uuid.uuid4().hex[:10].upper()}"
        self._reset_calls()

        if not self.db.get_document(document_id):
            self.db.create_document(document_id, filename, content_type, len(data))
        self.db.update_document(document_id, status=DocumentStatus.PROCESSING.value)

        # 1. Parse. Cheap guards before any inference call.
        parsed: ParseResult = parse_document(data, filename)
        if parsed.failed:
            trace.emit(
                "parse",
                f"Cannot read document: {parsed.problem.value if parsed.problem else 'unknown'}",
                status="fail",
                detail=parsed.detail,
            )
            self.db.update_document(
                document_id,
                status=DocumentStatus.FAILED.value,
                doc_format=parsed.doc_format.value,
                error=parsed.detail,
                pages=parsed.pages,
            )
            return ProcessResult(
                document_id=document_id,
                ok=False,
                error=parsed.detail,
                problem=parsed.problem,
                doc_format=parsed.doc_format.value,
                pages=parsed.pages,
            )

        trace.emit(
            "parse",
            f"Read {parsed.doc_format.value.upper()}"
            + (" via OCR" if parsed.ocr else "")
            + (f", {parsed.pages} page(s)" if parsed.pages else ""),
            status="warn" if parsed.ocr else "ok",
            detail=f"{len(parsed.text)} characters"
            + (" (truncated)" if parsed.truncated else "")
            + (" — OCR output is lossy" if parsed.ocr else ""),
            # The extracted text is what the model actually sees. When an
            # extraction looks wrong the first question is always "did we read
            # the document correctly?", and this answers it without re-running.
            response=parsed.text,
        )
        self.db.update_document(
            document_id,
            doc_format=parsed.doc_format.value,
            pages=parsed.pages,
            text_chars=len(parsed.text),
            truncated=int(parsed.truncated),
        )

        # 2. Extract.
        try:
            extraction, request_id = self.llm.extract(
                parsed.text, document_id=document_id
            )
        except LLMError as exc:
            trace.emit("extract", "Extraction failed", status="fail", detail=str(exc))
            self._flush_calls()
            self.db.update_document(
                document_id, status=DocumentStatus.FAILED.value, error=str(exc)
            )
            return ProcessResult(
                document_id=document_id,
                ok=False,
                error=str(exc),
                doc_format=parsed.doc_format.value,
                pages=parsed.pages,
                truncated=parsed.truncated,
                calls=list(self._call_buffer),
            )

        # 3. Validate. Deterministic arithmetic, not model judgement.
        report = validate(extraction, from_ocr=parsed.ocr)
        for finding in report.findings:
            trace.emit(
                "validate",
                finding.check,
                status="fail" if finding.severity.value == "error" else "warn",
                detail=finding.message,
            )
        trace.emit(
            "validate",
            f"Review status: {report.status.value}",
            status="ok" if report.status is ReviewStatus.AUTO_APPROVED else "warn",
            detail=f"{len(report.findings)} finding(s)",
        )

        # 4. Persist.
        self.db.save_extraction(document_id, request_id, extraction, report)
        self.db.update_document(document_id, status=DocumentStatus.COMPLETED.value)
        self._flush_calls()
        trace.emit("store", f"Saved as {document_id}", detail=f"status={report.status.value}")

        return ProcessResult(
            document_id=document_id,
            ok=True,
            extraction=extraction,
            report=report,
            request_id=request_id,
            doc_format=parsed.doc_format.value,
            pages=parsed.pages,
            truncated=parsed.truncated,
            calls=list(self._call_buffer),
        )
