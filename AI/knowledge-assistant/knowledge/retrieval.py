"""Hybrid retrieval: dense vectors fused with BM25.

Why fuse two retrievers
-----------------------
They fail in opposite directions, which is what makes combining them worth the
complexity:

* **Dense vectors** match meaning but are weak on exact tokens. A query for
  "Section 4.2" or "INV-10932" embeds to something generic.
* **BM25** matches words but has no notion of synonymy. "How do I get my money
  back?" scores zero against a document that only says "refund".

An enterprise question usually contains both kinds of term -- "what is the
refund policy for *enterprise* customers" needs the concept *and* the literal
word -- so both rankings are produced and merged.

How the fusion works
--------------------
Reciprocal Rank Fusion, rather than adding the raw scores. Cosine similarity
lives in roughly [0, 1] while BM25 is unbounded and corpus-dependent, so summing
them would let BM25 silently dominate. RRF uses only the *position* in each
ranking::

    score(chunk) = Σ  weight_r / (k + rank_r(chunk))

which is scale-free: a chunk ranked first by either retriever gets a strong
contribution regardless of what the underlying numbers happened to be.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from . import trace
from .config import settings
from .embeddings import Embedder
from .store import StoredChunk, VectorStore, tokenise

# Rank-fusion damping. The standard value from the RRF paper; it stops the top
# hit from overwhelming everything below it.
RRF_K = 60


def _coverage(query: str, chunk_text: str) -> float:
    """Share of the query's content words that appear in a chunk.

    Reciprocal Rank Fusion is scale-free by design, which is its strength and
    its blind spot: it reports *relative* ordering, so the best of four
    irrelevant chunks still scores about the same as a genuinely good match.
    Measured on this corpus, "What is the capital of France?" produced fused
    scores of 0.0163 while "refund policy for enterprise customers" produced
    0.0164 -- indistinguishable.

    Lexical overlap restores an absolute signal: a question whose content words
    appear nowhere in the corpus is one nothing can answer.
    """
    from .store import tokenise

    terms = set(tokenise(query, drop_stopwords=True, apply_stem=True))
    if not terms:
        return 0.0
    body = set(tokenise(chunk_text, apply_stem=True))
    return sum(1 for t in terms if t in body) / len(terms)


@dataclass
class RetrievedChunk:
    """A chunk plus why it was retrieved."""

    chunk: StoredChunk
    score: float
    dense_rank: int | None = None
    lexical_rank: int | None = None
    dense_score: float | None = None
    semantic_override: bool = False

    @property
    def sources(self) -> list[str]:
        found_by = []
        if self.dense_rank is not None:
            found_by.append("vector")
        if self.lexical_rank is not None:
            found_by.append("keyword")
        return found_by

    def as_dict(self) -> dict[str, Any]:
        return {
            **self.chunk.as_dict(),
            "score": round(self.score, 4),
            "dense_rank": self.dense_rank,
            "lexical_rank": self.lexical_rank,
            "dense_score": (
                round(self.dense_score, 4) if self.dense_score is not None else None
            ),
            "semantic_override": self.semantic_override,
            "found_by": self.sources,
        }


@dataclass
class RetrievalResult:
    """Everything retrieval produced, including what it rejected."""

    query: str
    chunks: list[RetrievedChunk] = field(default_factory=list)
    dense_hits: int = 0
    lexical_hits: int = 0
    filtered_out: int = 0
    # Best query-term coverage seen, for explaining a refusal.
    best_coverage: float = 0.0

    @property
    def is_empty(self) -> bool:
        return not self.chunks

    def context(self, max_chars: int | None = None) -> str:
        """Render the chunks as numbered context for the prompt.

        Numbering matters: the model is asked to cite ``[1]``, ``[2]`` and so
        on, and those markers are later resolved back to real chunks. Without
        stable numbering there is no way to verify a citation.
        """
        limit = max_chars or settings.max_context_chars
        parts: list[str] = []
        used = 0

        for position, item in enumerate(self.chunks, 1):
            chunk = item.chunk
            where = chunk.filename or chunk.document_id
            header = f"[{position}] {where}"
            if chunk.heading:
                header += f" — {chunk.heading}"
            block = f"{header}\n{chunk.text}"

            if used + len(block) > limit:
                break
            parts.append(block)
            used += len(block)

        return "\n\n---\n\n".join(parts)

    def as_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "chunks": [c.as_dict() for c in self.chunks],
            "dense_hits": self.dense_hits,
            "lexical_hits": self.lexical_hits,
            "filtered_out": self.filtered_out,
            "best_coverage": round(self.best_coverage, 3),
        }


def _rrf(ranked_ids: list[int], weight: float) -> dict[int, float]:
    """Reciprocal-rank contribution of one ranking."""
    return {
        chunk_id: weight / (RRF_K + rank)
        for rank, chunk_id in enumerate(ranked_ids, start=1)
    }


class Retriever:
    """Finds the passages most likely to answer a question."""

    def __init__(self, store: VectorStore, embedder: Embedder) -> None:
        self.store = store
        self.embedder = embedder

    def retrieve(
        self,
        query: str,
        *,
        top_k: int | None = None,
        dense_weight: float | None = None,
    ) -> RetrievalResult:
        top_k = top_k or settings.top_k
        dense_weight = (
            settings.dense_weight if dense_weight is None else dense_weight
        )
        result = RetrievalResult(query=query)

        if not query.strip() or self.store.chunk_count() == 0:
            trace.emit(
                "retrieve",
                "Nothing to search",
                status="warn",
                detail="the knowledge base is empty",
            )
            return result

        candidates = settings.candidate_k

        # --- dense ---------------------------------------------------
        dense: list[tuple[int, float]] = []
        if dense_weight > 0:
            try:
                vector = self.embedder.embed([query])[0]
                dense = self.store.search_dense(vector, candidates)
            except Exception as exc:  # noqa: BLE001
                # Retrieval must degrade, not fail: BM25 alone still answers
                # most keyword-shaped questions.
                trace.emit(
                    "retrieve",
                    "Vector search unavailable",
                    status="warn",
                    detail=f"{type(exc).__name__}: {exc}",
                )

        # --- lexical -------------------------------------------------
        lexical = self.store.search_lexical(query, candidates)

        result.dense_hits = len(dense)
        result.lexical_hits = len(lexical)

        # --- fuse ----------------------------------------------------
        dense_ids = [cid for cid, _ in dense]
        lexical_ids = [cid for cid, _ in lexical]

        fused: dict[int, float] = {}
        for chunk_id, contribution in _rrf(dense_ids, dense_weight).items():
            fused[chunk_id] = fused.get(chunk_id, 0.0) + contribution
        for chunk_id, contribution in _rrf(lexical_ids, 1.0 - dense_weight).items():
            fused[chunk_id] = fused.get(chunk_id, 0.0) + contribution

        if not fused:
            trace.emit("retrieve", "No matching passages", status="warn")
            return result

        dense_rank = {cid: i for i, cid in enumerate(dense_ids, 1)}
        lexical_rank = {cid: i for i, cid in enumerate(lexical_ids, 1)}
        dense_score = {cid: score for cid, score in dense}

        def _strong_semantic(chunk_id: int) -> bool:
            """A dense hit good enough to trust on meaning alone.

            Both gates below -- the fused ``min_score`` cutoff and the lexical
            coverage gate -- are lexical in spirit: a paraphrase sharing no
            words with its source scores near zero on each. With a semantic
            embedder that is precisely the case worth keeping, so a top-ranked,
            strongly similar vector hit is allowed past both. Measured on this
            corpus, on-topic paraphrases score 0.20-0.44 while off-topic
            questions peak at 0.11, so the threshold sits in the gap.
            """
            if not self.embedder.semantic:
                return False
            rank = dense_rank.get(chunk_id)
            score = dense_score.get(chunk_id)
            return (
                rank is not None
                and rank <= settings.semantic_override_max_rank
                and score is not None
                and score >= settings.min_semantic_score
            )

        ordered = sorted(fused.items(), key=lambda kv: kv[1], reverse=True)
        kept = [
            (cid, score)
            for cid, score in ordered
            if score >= settings.min_score or _strong_semantic(cid)
        ]
        result.filtered_out = len(ordered) - len(kept)
        kept = kept[: top_k * 2]  # over-fetch; the coverage gate prunes below

        chunks = self.store.get_chunks([cid for cid, _ in kept])
        by_id = {c.id: c for c in chunks}

        # Absolute relevance gate. RRF only ranks, so without this an
        # off-topic question still returns its best-of-a-bad-lot chunks and the
        # model is invited to answer from general knowledge.
        #
        # The threshold scales down for long questions. A 20-word question
        # cannot expect any single chunk to contain most of its vocabulary --
        # the answer is usually spread across several passages, each covering a
        # slice. Measured: a 30-term question about pipeline architecture left
        # exactly one chunk above a flat 20% gate, and the model then refused
        # for lack of surrounding context even though retrieval had found the
        # right section.
        term_count = len(set(tokenise(query, drop_stopwords=True, apply_stem=True)))
        threshold = settings.min_coverage
        if term_count > 8:
            threshold = max(settings.min_coverage_floor, settings.min_coverage * 8 / term_count)

        best_coverage = 0.0
        semantic_overrides = 0
        surviving: list[RetrievedChunk] = []
        for chunk_id, score in kept:
            stored = by_id.get(chunk_id)
            if stored is None:
                continue
            coverage = _coverage(query, f"{stored.heading} {stored.text}")
            best_coverage = max(best_coverage, coverage)

            item_dense_rank = dense_rank.get(chunk_id)
            item_dense_score = dense_score.get(chunk_id)
            allow_semantic_override = _strong_semantic(chunk_id)

            if coverage < threshold:
                if allow_semantic_override:
                    semantic_overrides += 1
                else:
                    result.filtered_out += 1
                    continue
            surviving.append(
                RetrievedChunk(
                    chunk=stored,
                    score=score,
                    dense_rank=item_dense_rank,
                    lexical_rank=lexical_rank.get(chunk_id),
                    dense_score=item_dense_score,
                    semantic_override=coverage < threshold,
                )
            )

        result.chunks = surviving[:top_k]
        result.best_coverage = best_coverage

        if not result.chunks:
            trace.emit(
                "retrieve",
                "No sufficiently relevant passage",
                status="warn",
                detail=(
                    f"best term coverage was {best_coverage:.0%}, below the "
                    f"{threshold:.0%} threshold ({term_count} query terms) — the "
                    f"question does not appear to be about these documents"
                ),
            )
            return result

        both = sum(1 for c in result.chunks if len(c.sources) == 2)
        trace.emit(
            "retrieve",
            f"Retrieved {len(result.chunks)} passage(s)",
            detail=(
                f"vector={result.dense_hits} candidates, "
                f"keyword={result.lexical_hits} candidates, "
                f"{both} found by both · coverage={best_coverage:.0%} · "
                f"semantic-overrides={semantic_overrides}"
            ),
            response="\n\n".join(
                f"[{i}] score={c.score:.4f} via {'+'.join(c.sources)} — "
                f"{c.chunk.filename} {c.chunk.heading}\n{c.chunk.text[:300]}"
                for i, c in enumerate(result.chunks, 1)
            ),
        )
        return result
