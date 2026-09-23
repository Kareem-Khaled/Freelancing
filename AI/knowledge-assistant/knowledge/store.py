"""Vector store and lexical index, both backed by SQLite.

Why not Chroma, FAISS or pgvector
---------------------------------
For an enterprise knowledge base of the size described -- 50 PDFs, 20 DOCX, 10
policies, 5 manuals, call it a few thousand chunks -- a brute-force NumPy dot
product over the whole matrix takes single-digit milliseconds. Approximate
nearest-neighbour indexes exist to avoid scanning millions of vectors; below
roughly 100k they add a dependency, a build step and an index-staleness problem
in exchange for nothing measurable.

The store is written so that swapping in a real vector database later touches
this file only.

Why BM25 as well
----------------
Dense vectors are bad at exact tokens: part numbers, policy codes, "Section
4.2", "INV-10932". BM25 is bad at synonyms. Enterprise questions contain both
kinds of term, so both indexes are maintained and fused at query time.
"""

from __future__ import annotations

import json
import math
import re
import sqlite3
from collections import Counter
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterator

import numpy as np

from .config import settings

_SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id           TEXT PRIMARY KEY,
    filename     TEXT NOT NULL DEFAULT '',
    title        TEXT NOT NULL DEFAULT '',
    doc_format   TEXT NOT NULL DEFAULT '',
    size_bytes   INTEGER NOT NULL DEFAULT 0,
    pages        INTEGER NOT NULL DEFAULT 0,
    chunk_count  INTEGER NOT NULL DEFAULT 0,
    status       TEXT NOT NULL DEFAULT 'pending',
    error        TEXT NOT NULL DEFAULT '',
    ocr          INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chunks (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id  TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index  INTEGER NOT NULL,
    heading      TEXT NOT NULL DEFAULT '',
    text         TEXT NOT NULL,
    -- float32 vector, stored raw. SQLite has no array type and JSON would
    -- triple the size for no benefit; np.frombuffer reads it back directly.
    vector       BLOB,
    token_count  INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS queries (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    question     TEXT NOT NULL,
    answer       TEXT NOT NULL DEFAULT '',
    citations    TEXT NOT NULL DEFAULT '[]',
    chunk_ids    TEXT NOT NULL DEFAULT '[]',
    grounded     INTEGER NOT NULL DEFAULT 0,
    latency_ms   REAL NOT NULL DEFAULT 0,
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS llm_calls (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id        TEXT NOT NULL,
    document_id       TEXT NOT NULL DEFAULT '',
    operation         TEXT NOT NULL,
    model             TEXT NOT NULL,
    attempt           INTEGER NOT NULL,
    latency_ms        REAL NOT NULL,
    prompt_tokens     INTEGER NOT NULL,
    completion_tokens INTEGER NOT NULL,
    total_tokens      INTEGER NOT NULL,
    cost_usd          REAL NOT NULL DEFAULT 0,
    success           INTEGER NOT NULL,
    error             TEXT NOT NULL DEFAULT '',
    created_at        TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(document_id);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class StoredChunk:
    """A chunk as it comes back from the database."""

    id: int
    document_id: str
    chunk_index: int
    heading: str
    text: str
    filename: str = ""

    @property
    def citation(self) -> str:
        where = self.filename or self.document_id
        return f"{where}#{self.chunk_index}" + (f" ({self.heading})" if self.heading else "")

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "document_id": self.document_id,
            "chunk_index": self.chunk_index,
            "heading": self.heading,
            "text": self.text,
            "filename": self.filename,
        }


_WORD = re.compile(r"[a-z0-9]+")

# Words carrying no retrieval signal. Without this, a question like "What is
# the capital of France?" scores against every chunk containing "is" or "the",
# which made an entirely off-topic query look like a confident hit -- exactly
# the failure the relevance threshold is supposed to catch.
_STOPWORDS = frozenset("""
a an and are as at be been but by can could did do does for from had has have
how i if in into is it its may me might must my of on or our shall should so
such than that the their them then there these they this those to us was we
were what when where which while who whom why will with would you your
""".split())


def stem(word: str) -> str:
    """Crude suffix stripping so morphological variants match.

    Not linguistics -- just enough that "expenses" matches "expense" and
    "submitted" matches "submit". Without it a question in the present tense
    misses a policy written in the past tense, which is most policies.

    Deliberately conservative: strip at most one suffix and never leave a stem
    shorter than three characters. Over-stemming is worse than under-stemming,
    because it silently merges unrelated words ("expenses" must not become
    "expen", which matches nothing).
    """
    if len(word) < 4:
        return word

    # Plural "s" first: "days" -> "day", "expenses" -> "expense". Checking
    # this before "es" avoids turning "expenses" into "expens", which then
    # fails to match the singular.
    if word.endswith("ies") and len(word) > 4:
        return word[:-3] + "y"
    if word.endswith("sses"):          # "classes" -> "class"
        return word[:-2]
    if word.endswith("s") and not word.endswith(("ss", "us", "is")):
        return word[:-1]

    for suffix in ("ing", "ed"):
        if word.endswith(suffix):
            trimmed = word[: -len(suffix)]
            if len(trimmed) < 3:
                continue
            # "submitting" -> "submit", not "submitt"
            if len(trimmed) > 3 and trimmed[-1] == trimmed[-2] and trimmed[-1] not in "sl":
                trimmed = trimmed[:-1]
            return trimmed
    return word


def tokenise(
    text: str, *, drop_stopwords: bool = False, apply_stem: bool = False
) -> list[str]:
    tokens = _WORD.findall(text.lower())
    if drop_stopwords:
        tokens = [t for t in tokens if t not in _STOPWORDS]
    if apply_stem:
        tokens = [stem(t) for t in tokens]
    return tokens


class BM25:
    """Okapi BM25 over the chunk corpus.

    Rebuilt in memory from SQLite on demand. At a few thousand chunks this
    takes milliseconds, and it removes an entire class of bug where the index
    and the database disagree about what exists.
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self.chunk_ids: list[int] = []
        self._freqs: list[Counter] = []
        self._lengths: list[int] = []
        self._doc_freq: Counter = Counter()
        self._avg_len = 0.0

    def build(self, chunks: list[tuple[int, str]]) -> None:
        self.chunk_ids = []
        self._freqs = []
        self._lengths = []
        self._doc_freq = Counter()

        for chunk_id, text in chunks:
            tokens = tokenise(text, apply_stem=True)
            counts = Counter(tokens)
            self.chunk_ids.append(chunk_id)
            self._freqs.append(counts)
            self._lengths.append(len(tokens))
            self._doc_freq.update(counts.keys())

        self._avg_len = (sum(self._lengths) / len(self._lengths)) if self._lengths else 0.0

    def search(self, query: str, limit: int) -> list[tuple[int, float]]:
        if not self.chunk_ids:
            return []

        # Stopwords are dropped from the QUERY only. Keeping them in the index
        # costs nothing, but scoring them turns every question into a match.
        terms = tokenise(query, drop_stopwords=True, apply_stem=True)
        if not terms:
            return []

        total = len(self.chunk_ids)
        scores = np.zeros(total, dtype=np.float32)

        for term in terms:
            df = self._doc_freq.get(term, 0)
            if df == 0:
                continue
            # BM25 IDF, which goes slightly negative for terms in most
            # documents -- clamped, because a term appearing everywhere should
            # contribute nothing rather than penalise.
            idf = max(0.0, math.log((total - df + 0.5) / (df + 0.5) + 1.0))

            for i, counts in enumerate(self._freqs):
                tf = counts.get(term, 0)
                if not tf:
                    continue
                length_norm = 1 - self.b + self.b * (self._lengths[i] / (self._avg_len or 1))
                scores[i] += idf * (tf * (self.k1 + 1)) / (tf + self.k1 * length_norm)

        ranked = scores.argsort()[::-1][:limit]
        return [(self.chunk_ids[i], float(scores[i])) for i in ranked if scores[i] > 0]


class VectorStore:
    """SQLite-backed storage for documents, chunks, vectors and query history."""

    def __init__(self, path: str | None = None) -> None:
        self.path = path or settings.db_path
        self._init_schema()
        self._matrix: np.ndarray | None = None
        self._matrix_ids: list[int] = []
        self._bm25: BM25 | None = None

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 30000")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self.connect() as conn:
            conn.executescript(_SCHEMA)

    def invalidate_cache(self) -> None:
        """Drop the in-memory indexes after a write."""
        self._matrix = None
        self._matrix_ids = []
        self._bm25 = None

    # -- documents ----------------------------------------------------
    def create_document(
        self, document_id: str, filename: str, title: str, size_bytes: int
    ) -> None:
        now = _now()
        with self.connect() as conn:
            conn.execute(
                """INSERT INTO documents (id, filename, title, size_bytes, status,
                                          created_at, updated_at)
                   VALUES (?, ?, ?, ?, 'pending', ?, ?)""",
                (document_id, filename, title, size_bytes, now, now),
            )

    def update_document(self, document_id: str, **fields: Any) -> None:
        if not fields:
            return
        fields["updated_at"] = _now()
        assignments = ", ".join(f"{k} = ?" for k in fields)
        with self.connect() as conn:
            conn.execute(
                f"UPDATE documents SET {assignments} WHERE id = ?",
                (*fields.values(), document_id),
            )

    def get_document(self, document_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM documents WHERE id = ?", (document_id,)
            ).fetchone()
        return dict(row) if row else None

    def list_documents(self, limit: int = 100) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM documents ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    def delete_document(self, document_id: str) -> bool:
        with self.connect() as conn:
            conn.execute("DELETE FROM chunks WHERE document_id = ?", (document_id,))
            cursor = conn.execute("DELETE FROM documents WHERE id = ?", (document_id,))
            deleted = cursor.rowcount > 0
        self.invalidate_cache()
        return deleted

    # -- chunks -------------------------------------------------------
    def add_chunks(
        self, document_id: str, chunks: list[Any], vectors: np.ndarray
    ) -> None:
        """Store chunks and their vectors together, in one transaction."""
        now = _now()
        with self.connect() as conn:
            conn.execute("DELETE FROM chunks WHERE document_id = ?", (document_id,))
            for chunk, vector in zip(chunks, vectors):
                conn.execute(
                    """INSERT INTO chunks (document_id, chunk_index, heading, text,
                                           vector, token_count, created_at)
                       VALUES (?,?,?,?,?,?,?)""",
                    (
                        document_id,
                        chunk.index,
                        chunk.heading,
                        chunk.text,
                        np.asarray(vector, dtype=np.float32).tobytes(),
                        len(tokenise(chunk.text)),
                        now,
                    ),
                )
            conn.execute(
                "UPDATE documents SET chunk_count = ?, updated_at = ? WHERE id = ?",
                (len(chunks), now, document_id),
            )
        self.invalidate_cache()

    def chunk_count(self) -> int:
        with self.connect() as conn:
            return conn.execute("SELECT COUNT(*) AS n FROM chunks").fetchone()["n"]

    def get_chunks(self, chunk_ids: list[int]) -> list[StoredChunk]:
        if not chunk_ids:
            return []
        placeholders = ",".join("?" * len(chunk_ids))
        with self.connect() as conn:
            rows = conn.execute(
                f"""SELECT c.id, c.document_id, c.chunk_index, c.heading, c.text,
                           d.filename
                    FROM chunks c JOIN documents d ON d.id = c.document_id
                    WHERE c.id IN ({placeholders})""",
                chunk_ids,
            ).fetchall()
        by_id = {
            r["id"]: StoredChunk(
                id=r["id"],
                document_id=r["document_id"],
                chunk_index=r["chunk_index"],
                heading=r["heading"],
                text=r["text"],
                filename=r["filename"],
            )
            for r in rows
        }
        # Preserve the caller's ordering, which is the ranking.
        return [by_id[cid] for cid in chunk_ids if cid in by_id]

    def list_chunks(self, document_id: str) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                """SELECT id, chunk_index, heading, text, token_count
                   FROM chunks WHERE document_id = ? ORDER BY chunk_index""",
                (document_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    # -- search -------------------------------------------------------
    def _load_matrix(self) -> tuple[np.ndarray, list[int]]:
        """Load every vector into one contiguous matrix, cached until a write."""
        if self._matrix is not None:
            return self._matrix, self._matrix_ids

        with self.connect() as conn:
            rows = conn.execute(
                "SELECT id, vector FROM chunks WHERE vector IS NOT NULL ORDER BY id"
            ).fetchall()

        if not rows:
            self._matrix = np.zeros((0, 1), dtype=np.float32)
            self._matrix_ids = []
            return self._matrix, self._matrix_ids

        vectors = [np.frombuffer(r["vector"], dtype=np.float32) for r in rows]
        self._matrix = np.vstack(vectors)
        self._matrix_ids = [r["id"] for r in rows]
        return self._matrix, self._matrix_ids

    def search_dense(self, query_vector: np.ndarray, limit: int) -> list[tuple[int, float]]:
        matrix, ids = self._load_matrix()
        if not ids:
            return []
        if matrix.shape[1] != query_vector.shape[0]:
            # Dimension mismatch means the embedder changed since indexing.
            # Returning nothing is correct: comparing incompatible vectors
            # would produce confident nonsense.
            return []
        scores = matrix @ query_vector
        ranked = scores.argsort()[::-1][:limit]
        return [(ids[i], float(scores[i])) for i in ranked]

    def search_lexical(self, query: str, limit: int) -> list[tuple[int, float]]:
        if self._bm25 is None:
            with self.connect() as conn:
                rows = conn.execute(
                    "SELECT id, heading || ' ' || text AS body FROM chunks ORDER BY id"
                ).fetchall()
            self._bm25 = BM25()
            self._bm25.build([(r["id"], r["body"]) for r in rows])
        return self._bm25.search(query, limit)

    # -- query history ------------------------------------------------
    def save_query(
        self,
        question: str,
        answer: str,
        citations: list[dict],
        chunk_ids: list[int],
        grounded: bool,
        latency_ms: float,
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """INSERT INTO queries (question, answer, citations, chunk_ids,
                                        grounded, latency_ms, created_at)
                   VALUES (?,?,?,?,?,?,?)""",
                (
                    question,
                    answer,
                    json.dumps(citations),
                    json.dumps(chunk_ids),
                    int(grounded),
                    latency_ms,
                    _now(),
                ),
            )

    def recent_queries(self, limit: int = 20) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM queries ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        out = []
        for row in rows:
            data = dict(row)
            for key in ("citations", "chunk_ids"):
                try:
                    data[key] = json.loads(data.get(key) or "[]")
                except (ValueError, TypeError):
                    data[key] = []
            data["grounded"] = bool(data["grounded"])
            out.append(data)
        return out

    # -- metrics ------------------------------------------------------
    def save_call(self, metrics: Any) -> None:
        with self.connect() as conn:
            conn.execute(
                """INSERT INTO llm_calls
                   (request_id, document_id, operation, model, attempt, latency_ms,
                    prompt_tokens, completion_tokens, total_tokens, cost_usd,
                    success, error, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    metrics.request_id,
                    metrics.ticket_id,
                    metrics.operation,
                    metrics.model,
                    metrics.attempt,
                    metrics.latency_ms,
                    metrics.prompt_tokens,
                    metrics.completion_tokens,
                    metrics.total_tokens,
                    metrics.cost_usd,
                    int(metrics.success),
                    metrics.error,
                    metrics.created_at,
                ),
            )

    def metrics_summary(self) -> dict[str, Any]:
        with self.connect() as conn:
            row = conn.execute(
                """SELECT COUNT(*) AS calls,
                          SUM(success) AS successes,
                          SUM(CASE WHEN attempt > 1 THEN 1 ELSE 0 END) AS retries,
                          AVG(latency_ms) AS avg_latency_ms,
                          SUM(prompt_tokens) AS prompt_tokens,
                          SUM(completion_tokens) AS completion_tokens,
                          SUM(total_tokens) AS total_tokens,
                          SUM(cost_usd) AS cost_usd
                   FROM llm_calls"""
            ).fetchone()
            docs = conn.execute("SELECT COUNT(*) AS n FROM documents").fetchone()["n"]
            chunks = conn.execute("SELECT COUNT(*) AS n FROM chunks").fetchone()["n"]

        data = {k: (row[k] or 0) for k in row.keys()}
        data["success_rate"] = (
            round(data["successes"] / data["calls"], 3) if data["calls"] else 0.0
        )
        data["avg_latency_ms"] = round(data["avg_latency_ms"], 1)
        data["documents"] = docs
        data["chunks"] = chunks
        return data
