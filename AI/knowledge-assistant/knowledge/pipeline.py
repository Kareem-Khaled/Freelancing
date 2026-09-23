"""Orchestration: ingest documents, answer questions.

Two flows, deliberately separate:

    ingest:  bytes -> parse -> chunk -> embed -> store
    ask:     question -> retrieve -> answer -> verify citations

Ingestion is slow and happens rarely; asking is fast and happens constantly.
Keeping them apart is what makes the second one fast -- all the expensive work
(parsing, chunking, embedding) is done once at upload time.
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from . import trace
from .answering import Answer, Answerer, AnswerError
from .chunking import chunk_text
from .config import settings
from .embeddings import Embedder, get_embedder
from .parsing import ParseProblem, parse_document
from .retrieval import Retriever
from .store import VectorStore
from .telemetry import CallMetrics, MetricsCollector


class DocumentStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    INDEXED = "indexed"
    FAILED = "failed"


@dataclass
class IngestResult:
    """Outcome of indexing one document."""

    document_id: str
    ok: bool
    filename: str = ""
    chunks: int = 0
    doc_format: str = ""
    pages: int = 0
    ocr: bool = False
    error: str = ""
    problem: ParseProblem | None = None
    latency_ms: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "document_id": self.document_id,
            "ok": self.ok,
            "filename": self.filename,
            "chunks": self.chunks,
            "doc_format": self.doc_format,
            "pages": self.pages,
            "latency_ms": round(self.latency_ms, 1),
        }
        if self.ocr:
            data["ocr"] = True
        if self.error:
            data["error"] = self.error
        if self.problem:
            data["problem"] = self.problem.value
        return data


class KnowledgePipeline:
    """Indexes documents and answers questions from them.

    Safe to share across threads: the per-request metrics buffer is
    thread-local, so concurrent uploads cannot interleave each other's
    telemetry.
    """

    def __init__(
        self,
        store: VectorStore | None = None,
        embedder: Embedder | None = None,
        answerer: Answerer | None = None,
    ) -> None:
        self.store = store or VectorStore()
        self.embedder = embedder or get_embedder()
        self.metrics = MetricsCollector()
        self._local = threading.local()
        self.answerer = answerer or Answerer(
            metrics=self.metrics, on_call=self._on_call
        )
        self.retriever = Retriever(self.store, self.embedder)

    @property
    def _call_buffer(self) -> list[CallMetrics]:
        if not hasattr(self._local, "calls"):
            self._local.calls = []
        return self._local.calls

    def _on_call(self, record: CallMetrics) -> None:
        self._call_buffer.append(record)

    def _flush_calls(self) -> None:
        """Persist buffered metrics. Never silently: a swallowed exception here
        once produced a dashboard that confidently reported zero calls."""
        for record in self._call_buffer:
            try:
                self.store.save_call(record)
            except Exception as exc:  # noqa: BLE001
                trace.emit(
                    "store",
                    "Failed to persist call metrics",
                    status="fail",
                    detail=f"{type(exc).__name__}: {exc}",
                )
        self._local.calls = []

    # -- ingestion ----------------------------------------------------
    def ingest(
        self,
        data: bytes,
        *,
        filename: str = "",
        title: str = "",
        document_id: str | None = None,
    ) -> IngestResult:
        """Parse, chunk, embed and index one document."""
        started = time.perf_counter()
        document_id = document_id or f"DOC-{uuid.uuid4().hex[:10].upper()}"

        if not self.store.get_document(document_id):
            self.store.create_document(
                document_id, filename, title or filename, len(data)
            )
        self.store.update_document(
            document_id, status=DocumentStatus.PROCESSING.value
        )

        # 1. Parse.
        parsed = parse_document(data, filename)
        if parsed.failed:
            detail = parsed.detail
            trace.emit(
                "parse",
                f"Cannot read: {parsed.problem.value if parsed.problem else 'unknown'}",
                status="fail",
                detail=detail,
            )
            self.store.update_document(
                document_id,
                status=DocumentStatus.FAILED.value,
                error=detail,
                doc_format=parsed.doc_format.value,
            )
            return IngestResult(
                document_id=document_id,
                ok=False,
                filename=filename,
                doc_format=parsed.doc_format.value,
                error=detail,
                problem=parsed.problem,
                latency_ms=(time.perf_counter() - started) * 1000,
            )

        trace.emit(
            "parse",
            f"Read {parsed.doc_format.value.upper()}"
            + (" via OCR" if parsed.ocr else "")
            + (f", {parsed.pages} page(s)" if parsed.pages else ""),
            status="warn" if parsed.ocr else "ok",
            detail=f"{len(parsed.text)} characters"
            + (" — OCR output is lossy" if parsed.ocr else ""),
            response=parsed.text[:4000],
        )

        # 2. Chunk.
        chunks = chunk_text(parsed.text)
        if not chunks:
            message = "document produced no usable chunks"
            trace.emit("chunk", "No chunks", status="fail", detail=message)
            self.store.update_document(
                document_id, status=DocumentStatus.FAILED.value, error=message
            )
            return IngestResult(
                document_id=document_id,
                ok=False,
                filename=filename,
                doc_format=parsed.doc_format.value,
                error=message,
                latency_ms=(time.perf_counter() - started) * 1000,
            )

        headings = len({c.heading for c in chunks if c.heading})
        trace.emit(
            "chunk",
            f"Split into {len(chunks)} chunk(s)",
            detail=(
                f"size={settings.chunk_size} overlap={settings.chunk_overlap} · "
                f"{headings} distinct heading(s)"
            ),
            response="\n\n".join(
                f"[{c.index}] {c.heading or '(no heading)'}\n{c.text[:200]}"
                for c in chunks[:8]
            ),
        )

        # 3. Embed. The hashing embedder learns document frequencies as it
        #    goes, so feeding it the corpus improves its IDF weighting.
        texts = [c.embed_text for c in chunks]
        fit = getattr(self.embedder, "fit", None)
        if callable(fit):
            fit(texts)
        vectors = self.embedder.embed(texts)

        trace.emit(
            "embed",
            f"Embedded {len(chunks)} chunk(s)",
            detail=(
                f"backend={self.embedder.name} dims={self.embedder.dims} "
                f"semantic={self.embedder.semantic}"
            ),
        )

        # 4. Store.
        self.store.add_chunks(document_id, chunks, vectors)
        self.store.update_document(
            document_id,
            status=DocumentStatus.INDEXED.value,
            doc_format=parsed.doc_format.value,
            pages=parsed.pages,
            ocr=int(parsed.ocr),
        )
        trace.emit("store", f"Indexed as {document_id}", detail=f"{len(chunks)} chunks")

        return IngestResult(
            document_id=document_id,
            ok=True,
            filename=filename,
            chunks=len(chunks),
            doc_format=parsed.doc_format.value,
            pages=parsed.pages,
            ocr=parsed.ocr,
            latency_ms=(time.perf_counter() - started) * 1000,
        )

    def reindex_all(self) -> int:
        """Re-embed every chunk with the current embedder.

        Needed after switching backends: vectors from different embedders are
        not comparable, and ``search_dense`` refuses to mix dimensions.
        """
        documents = self.store.list_documents(limit=10_000)
        total = 0
        for document in documents:
            rows = self.store.list_chunks(document["id"])
            if not rows:
                continue

            class _Row:
                def __init__(self, row):
                    self.index = row["chunk_index"]
                    self.heading = row["heading"]
                    self.text = row["text"]

                @property
                def embed_text(self):
                    return (
                        f"{self.heading}\n\n{self.text}".strip()
                        if self.heading
                        else self.text
                    )

            items = [_Row(r) for r in rows]
            texts = [i.embed_text for i in items]
            fit = getattr(self.embedder, "fit", None)
            if callable(fit):
                fit(texts)
            self.store.add_chunks(document["id"], items, self.embedder.embed(texts))
            total += len(items)
        return total

    # -- question answering -------------------------------------------
    def ask(self, question: str, *, top_k: int | None = None) -> Answer:
        """Retrieve relevant passages and answer from them."""
        started = time.perf_counter()

        if not question or not question.strip():
            return Answer(
                question=question,
                text="Please ask a question.",
                refused=True,
            )

        retrieval = self.retriever.retrieve(question, top_k=top_k)

        try:
            answer = self.answerer.answer(question, retrieval)
        except AnswerError as exc:
            trace.emit("answer", "Model unavailable", status="fail", detail=str(exc))
            answer = Answer(
                question=question,
                text=(
                    "The answering model is unavailable, so I cannot summarise "
                    "the documents. The most relevant passages are shown below."
                ),
                retrieval=retrieval,
                refused=True,
            )

        answer.latency_ms = (time.perf_counter() - started) * 1000
        self._flush_calls()

        try:
            self.store.save_query(
                question=question,
                answer=answer.text,
                citations=[c.as_dict() for c in answer.citations],
                chunk_ids=[c.chunk.id for c in retrieval.chunks],
                grounded=answer.grounded,
                latency_ms=answer.latency_ms,
            )
        except Exception:
            pass  # history is a convenience, not part of the answer

        return answer
