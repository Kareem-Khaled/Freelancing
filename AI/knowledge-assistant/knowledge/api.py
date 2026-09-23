"""FastAPI application for the knowledge assistant.

    POST   /documents              upload and index a document
    GET    /documents              list indexed documents
    GET    /documents/{id}         document metadata
    GET    /documents/{id}/chunks  the chunks it produced
    DELETE /documents/{id}         remove it from the index
    POST   /ask                    answer a question with citations
    GET    /queries                recent questions
    GET    /metrics                cost, latency and index size

Uploads are synchronous here, unlike the document-intelligence service.
Indexing is parse + chunk + embed, which is tens of milliseconds with the local
embedder -- there is no model call, so there is nothing to wait for. Asking a
question is the slow path, and that is a single request the caller is already
expecting to block on.
"""

from __future__ import annotations

import threading
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .config import settings
from .parsing import detect_format
from .pipeline import KnowledgePipeline
from .store import VectorStore
from .trace import TraceCollector, use_collector

app = FastAPI(
    title="Enterprise Knowledge Assistant",
    description=(
        "Ask questions and get answers grounded in your own documents, "
        "with verified citations."
    ),
    version="1.0.0",
)

_STATIC_DIR = Path(__file__).parent / "static"
_CORPUS_DIR = Path(__file__).parent.parent / "corpus"

store = VectorStore()
pipeline = KnowledgePipeline(store=store)

# Traces are diagnostics, not records: in memory and bounded.
_traces: dict[str, TraceCollector] = {}
_trace_order: list[str] = []
_trace_lock = threading.Lock()
_MAX_TRACES = 100


def _remember_trace(key: str, collector: TraceCollector) -> None:
    with _trace_lock:
        _traces[key] = collector
        _trace_order.append(key)
        while len(_trace_order) > _MAX_TRACES:
            _traces.pop(_trace_order.pop(0), None)


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    top_k: int | None = Field(default=None, ge=1, le=20)


class ErrorResponse(BaseModel):
    detail: str


@app.post("/documents", status_code=201, summary="Upload and index a document")
async def upload_document(file: UploadFile = File(...)) -> JSONResponse:
    """Parse, chunk, embed and index one document."""
    data = await file.read()

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

    # Format is detected from content, not the filename: an uploader can call
    # anything ".pdf".
    if detect_format(data, file.filename or "").value == "unknown":
        raise HTTPException(
            status_code=400,
            detail=(
                "unsupported file type; accepted: "
                f"{', '.join(settings.allowed_extensions)}"
            ),
        )

    document_id = f"DOC-{uuid.uuid4().hex[:10].upper()}"
    collector = TraceCollector()
    _remember_trace(document_id, collector)

    with use_collector(collector):
        result = pipeline.ingest(
            data, filename=file.filename or "", document_id=document_id
        )

    return JSONResponse(
        status_code=201 if result.ok else 422,
        content=result.as_dict(),
    )


@app.get("/documents", summary="List indexed documents")
async def list_documents(limit: int = Query(default=100, ge=1, le=500)) -> dict[str, Any]:
    return {
        "documents": store.list_documents(limit=limit),
        "total_chunks": store.chunk_count(),
        "embedder": {
            "backend": pipeline.embedder.name,
            "dims": pipeline.embedder.dims,
            "semantic": pipeline.embedder.semantic,
        },
    }


@app.get(
    "/documents/{document_id}",
    responses={404: {"model": ErrorResponse}},
    summary="Document metadata",
)
async def get_document(document_id: str) -> dict[str, Any]:
    document = store.get_document(document_id)
    if not document:
        raise HTTPException(status_code=404, detail=f"no document {document_id!r}")
    return document


@app.get(
    "/documents/{document_id}/chunks",
    responses={404: {"model": ErrorResponse}},
    summary="Chunks produced from a document",
)
async def get_chunks(document_id: str) -> dict[str, Any]:
    """Expose the chunks so retrieval quality can be inspected directly.

    When an answer is wrong the first question is "was the relevant passage
    even indexed, and did chunking keep it intact?" -- this answers it without
    re-uploading anything.
    """
    if not store.get_document(document_id):
        raise HTTPException(status_code=404, detail=f"no document {document_id!r}")
    chunks = store.list_chunks(document_id)
    return {"document_id": document_id, "count": len(chunks), "chunks": chunks}


@app.delete(
    "/documents/{document_id}",
    responses={404: {"model": ErrorResponse}},
    summary="Remove a document from the index",
)
async def delete_document(document_id: str) -> dict[str, Any]:
    if not store.delete_document(document_id):
        raise HTTPException(status_code=404, detail=f"no document {document_id!r}")
    return {"deleted": document_id, "remaining_chunks": store.chunk_count()}


@app.post("/ask", summary="Answer a question from the indexed documents")
async def ask(request: AskRequest) -> dict[str, Any]:
    """Retrieve relevant passages and answer from them, with citations.

    Returns the retrieved passages alongside the answer so a caller can judge
    the evidence rather than trusting the prose.
    """
    key = f"ask-{uuid.uuid4().hex[:10]}"
    collector = TraceCollector()
    _remember_trace(key, collector)

    with use_collector(collector):
        answer = pipeline.ask(request.question, top_k=request.top_k)

    payload = answer.as_dict()
    payload["trace_id"] = key
    return payload


@app.get("/queries", summary="Recent questions")
async def recent_queries(limit: int = Query(default=20, ge=1, le=100)) -> dict[str, Any]:
    return {"queries": store.recent_queries(limit=limit)}


@app.get(
    "/traces/{key}",
    responses={404: {"model": ErrorResponse}},
    summary="Execution trace for an upload or question",
)
async def get_trace(key: str) -> dict[str, Any]:
    with _trace_lock:
        collector = _traces.get(key)
    if collector is None:
        return {"key": key, "trace": [], "note": "trace expired"}
    return {"key": key, "trace": collector.snapshot()}


@app.get("/metrics", summary="Cost, latency and index size")
async def metrics() -> dict[str, Any]:
    return {
        "metrics": store.metrics_summary(),
        "model": settings.model,
        "api_base": settings.api_base,
        "embedder": {
            "backend": pipeline.embedder.name,
            "dims": pipeline.embedder.dims,
            "semantic": pipeline.embedder.semantic,
        },
        "retrieval": {
            "top_k": settings.top_k,
            "dense_weight": settings.dense_weight,
            "min_coverage": settings.min_coverage,
        },
    }


@app.post("/reindex", summary="Re-embed every chunk with the current embedder")
async def reindex() -> dict[str, Any]:
    """Rebuild all vectors.

    Required after switching embedding backends: vectors produced by different
    models are not comparable, and ``search_dense`` deliberately returns nothing
    on a dimension mismatch rather than scoring incompatible vectors against
    each other. Without this, installing sentence-transformers would silently
    disable vector search until every document was re-uploaded.
    """
    key = f"reindex-{uuid.uuid4().hex[:8]}"
    collector = TraceCollector()
    _remember_trace(key, collector)

    with use_collector(collector):
        chunks = pipeline.reindex_all()

    return {
        "reindexed_chunks": chunks,
        "embedder": {
            "backend": pipeline.embedder.name,
            "dims": pipeline.embedder.dims,
            "semantic": pipeline.embedder.semantic,
        },
        "trace_id": key,
    }


@app.get("/health", summary="Liveness probe")
async def health() -> dict[str, str]:
    return {"status": "ok", "model": settings.model}


# ----------------------------------------------------------------------
# Demo UI
# ----------------------------------------------------------------------
@app.get("/api/corpus", include_in_schema=False)
async def list_corpus() -> dict[str, Any]:
    """Sample documents shipped with the project, for the UI's one-click load."""
    if not _CORPUS_DIR.is_dir():
        return {"files": []}
    return {
        "files": sorted(
            p.name for p in _CORPUS_DIR.iterdir() if p.is_file() and not p.name.startswith(".")
        )
    }


@app.get("/api/corpus/{name}", include_in_schema=False)
async def get_corpus_file(name: str) -> Response:
    path = (_CORPUS_DIR / name).resolve()
    if not path.is_file() or not str(path).startswith(str(_CORPUS_DIR.resolve())):
        raise HTTPException(status_code=404, detail="not found")
    return Response(
        content=path.read_bytes(),
        media_type="application/octet-stream",
        headers={"X-Filename": name},
    )


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(_STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")
