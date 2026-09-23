"""FastAPI application exposing the document intelligence API.

    POST   /documents                     upload, returns 202 + document id
    GET    /documents                     list
    GET    /documents/{id}                status and metadata
    GET    /documents/{id}/extraction     the structured result
    GET    /documents/{id}/trace          per-step execution trace
    GET    /metrics                       cost and latency

Why uploads are asynchronous
----------------------------
Extraction takes several seconds on a local model. Holding an HTTP connection
open that long is fragile -- proxies and client timeouts interfere, and the
caller has no way to poll. ``POST /documents`` therefore returns **202 Accepted**
with an id, and the client polls ``GET /documents/{id}`` until the status is
``completed``. That is the conventional shape for long-running work and it makes
the service usable from a browser, a script or a queue consumer alike.
"""

from __future__ import annotations

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .config import settings
from .parsing import detect_format
from .pipeline import DocumentPipeline, DocumentStatus
from .storage import Database
from .trace import TraceCollector, use_collector

app = FastAPI(
    title="Document Intelligence API",
    description="Extract structured data from invoices (PDF, DOCX, image, text).",
    version="1.0.0",
)

_STATIC_DIR = Path(__file__).parent / "static"
_SAMPLES_DIR = Path(__file__).parent.parent / "samples"

db = Database()
pipeline = DocumentPipeline(db=db)

# One worker: the local model is the bottleneck, and several concurrent
# generations make all of them slower. Raise this for a hosted API.
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="extract")

# Traces are diagnostics, not records -- kept in memory and bounded.
_traces: dict[str, TraceCollector] = {}
_traces_order: list[str] = []
_traces_lock = threading.Lock()
_MAX_TRACES = 200


def _remember_trace(document_id: str, collector: TraceCollector) -> None:
    with _traces_lock:
        _traces[document_id] = collector
        _traces_order.append(document_id)
        while len(_traces_order) > _MAX_TRACES:
            _traces.pop(_traces_order.pop(0), None)


# ----------------------------------------------------------------------
# Response models -- these document the API and validate what we return.
# ----------------------------------------------------------------------
class UploadAccepted(BaseModel):
    document_id: str
    status: str
    message: str = Field(
        default="Processing started. Poll GET /documents/{id} for status."
    )


class DocumentInfo(BaseModel):
    id: str
    filename: str
    doc_format: str
    size_bytes: int
    pages: int
    status: str
    error: str = ""
    truncated: bool = False
    created_at: str
    updated_at: str


class ErrorResponse(BaseModel):
    detail: str


# ----------------------------------------------------------------------
# Processing
# ----------------------------------------------------------------------
def _process(document_id: str, data: bytes, filename: str, content_type: str) -> None:
    """Run the pipeline on a worker thread, capturing a trace."""
    collector = TraceCollector()
    _remember_trace(document_id, collector)
    try:
        with use_collector(collector):
            pipeline.process(
                data,
                filename=filename,
                content_type=content_type,
                document_id=document_id,
            )
    except Exception as exc:  # noqa: BLE001 - a worker must never die silently
        db.update_document(
            document_id,
            status=DocumentStatus.FAILED.value,
            error=f"{type(exc).__name__}: {exc}",
        )


@app.post(
    "/documents",
    response_model=UploadAccepted,
    status_code=202,
    responses={400: {"model": ErrorResponse}, 413: {"model": ErrorResponse}},
    summary="Upload a document for extraction",
)
async def upload_document(file: UploadFile = File(...)) -> JSONResponse:
    """Accept a document and start extraction in the background.

    Returns **202 Accepted** rather than the result: extraction takes seconds,
    and the caller should poll rather than hold a connection open.
    """
    data = await file.read()

    # Cheap rejections first -- no worker slot, no inference call.
    if not data:
        raise HTTPException(status_code=400, detail="file is empty")

    if len(data) > settings.max_file_bytes:
        raise HTTPException(
            status_code=413,
            detail=(
                f"file is {len(data) / 1_048_576:.1f} MB, limit is "
                f"{settings.max_file_bytes / 1_048_576:.0f} MB"
            ),
        )

    # Format is detected from content, not the filename -- an uploader can
    # call anything ".pdf".
    doc_format = detect_format(data, file.filename or "")
    if doc_format.value == "unknown":
        raise HTTPException(
            status_code=400,
            detail=(
                "unsupported file type; accepted: "
                f"{', '.join(settings.allowed_extensions)}"
            ),
        )

    document_id = f"DOC-{uuid.uuid4().hex[:10].upper()}"
    db.create_document(
        document_id,
        filename=file.filename or "",
        content_type=file.content_type or "",
        size_bytes=len(data),
    )

    _executor.submit(_process, document_id, data, file.filename or "", file.content_type or "")

    return JSONResponse(
        status_code=202,
        content={
            "document_id": document_id,
            "status": DocumentStatus.PENDING.value,
            "message": f"Processing started. Poll GET /documents/{document_id} for status.",
        },
    )


@app.get("/documents", summary="List uploaded documents")
async def list_documents(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    return {
        "total": db.count_documents(),
        "limit": limit,
        "offset": offset,
        "documents": db.list_documents(limit=limit, offset=offset),
        "review_counts": db.review_counts(),
    }


@app.get(
    "/documents/{document_id}",
    responses={404: {"model": ErrorResponse}},
    summary="Get document status and metadata",
)
async def get_document(document_id: str) -> dict[str, Any]:
    document = db.get_document(document_id)
    if not document:
        raise HTTPException(status_code=404, detail=f"no document with id {document_id!r}")
    return document


@app.get(
    "/documents/{document_id}/extraction",
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
    summary="Get the structured extraction",
)
async def get_extraction(document_id: str) -> dict[str, Any]:
    """Return the extracted invoice data plus its validation report.

    Status codes are deliberate: **409** distinguishes "still processing" and
    "failed" from **404** "no such document", so a polling client knows whether
    to retry or give up.
    """
    document = db.get_document(document_id)
    if not document:
        raise HTTPException(status_code=404, detail=f"no document with id {document_id!r}")

    if document["status"] == DocumentStatus.FAILED.value:
        raise HTTPException(
            status_code=409,
            detail=document["error"] or "extraction failed",
        )

    extraction = db.get_extraction(document_id)
    if not extraction:
        raise HTTPException(
            status_code=409,
            detail=f"extraction not ready; document status is {document['status']!r}",
        )

    return {
        "document_id": document_id,
        "status": document["status"],
        "review_status": extraction["review_status"],
        "confidence": extraction["confidence"],
        "extraction": extraction["payload"],
        "findings": extraction["findings"],
        "extracted_at": extraction["created_at"],
    }


@app.get(
    "/documents/{document_id}/trace",
    responses={404: {"model": ErrorResponse}},
    summary="Per-step execution trace",
)
async def get_trace(document_id: str) -> dict[str, Any]:
    """Show what happened, step by step, including the raw model exchange."""
    with _traces_lock:
        collector = _traces.get(document_id)
    if collector is None:
        if not db.get_document(document_id):
            raise HTTPException(status_code=404, detail=f"no document with id {document_id!r}")
        return {"document_id": document_id, "trace": [], "note": "trace expired"}
    return {"document_id": document_id, "trace": collector.snapshot()}


@app.get("/metrics", summary="Cost and latency metrics")
async def get_metrics() -> dict[str, Any]:
    return {
        "metrics": db.metrics_summary(),
        "model": settings.model,
        "api_base": settings.api_base,
    }


@app.get("/health", summary="Liveness probe")
async def health() -> dict[str, str]:
    return {"status": "ok", "model": settings.model}


# ----------------------------------------------------------------------
# Demo UI
# ----------------------------------------------------------------------
_SAMPLE_FILES = {
    "clean": "invoice_clean.txt",
    "bad_maths": "invoice_bad_maths.txt",
    "not_invoice": "not_an_invoice.txt",
    "docx": "invoice.docx",
    "scan": "invoice_scan.png",
    "arabic": "invoice_arabic.png",
}


@app.get("/api/sample/{name}", include_in_schema=False)
async def get_sample(name: str) -> Response:
    """Serve a fixture so the UI's sample buttons exercise the real upload path.

    Excluded from the OpenAPI schema: this exists for the demo page, not for
    API consumers.
    """
    filename = _SAMPLE_FILES.get(name)
    if not filename:
        raise HTTPException(status_code=404, detail=f"no sample named {name!r}")

    path = (_SAMPLES_DIR / filename).resolve()
    if not path.is_file() or not str(path).startswith(str(_SAMPLES_DIR.resolve())):
        raise HTTPException(status_code=404, detail="sample file is missing")

    return Response(
        content=path.read_bytes(),
        media_type="application/octet-stream",
        headers={"X-Filename": filename},
    )


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(_STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")
