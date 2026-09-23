"""Text embeddings, with a fallback chain that works on any backend.

The local llama.cpp server here returns::

    501 "This server does not support embeddings. Start it with --embeddings"

so a service that assumed a working ``/v1/embeddings`` endpoint would simply not
run. Rather than make the whole product depend on a flag we do not control, the
embedder is an interface with three implementations, chosen at startup:

1. ``ServerEmbedder``        -- uses the model backend, if it supports embeddings
2. ``SentenceEmbedder``      -- local transformer, if sentence-transformers is installed
3. ``HashingEmbedder``       -- pure NumPy, always available

The hashing embedder is the honest part of this design. It is a *lexical*
representation dressed as a vector: character n-grams hashed into a fixed space,
TF-IDF weighted, L2-normalised. It captures word overlap and morphology but NOT
meaning -- "how do I get my money back" will not match "refund policy" unless
they share substrings.

That limitation is why retrieval fuses these scores with BM25 rather than
trusting them alone, and why the UI reports which backend is live. A system that
silently degraded to keyword matching while calling itself semantic search would
be lying to its users.
"""

from __future__ import annotations

import hashlib
import math
import re
from typing import Protocol

import numpy as np

from .config import settings

__all__ = [
    "Embedder",
    "HashingEmbedder",
    "SentenceEmbedder",
    "ServerEmbedder",
    "get_embedder",
    "cosine_similarity",
]


class Embedder(Protocol):
    """Anything that can turn text into vectors."""

    name: str
    dims: int
    semantic: bool  # True when the vectors capture meaning, not just wording

    def embed(self, texts: list[str]) -> np.ndarray:
        """Return an (n, dims) float32 array of L2-normalised vectors."""
        ...


def cosine_similarity(query: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    """Cosine similarity of one vector against many.

    Vectors are already L2-normalised by every embedder here, so this is a
    plain dot product -- which is also why it stays fast on a few thousand
    chunks without a vector database.
    """
    if matrix.size == 0:
        return np.zeros(0, dtype=np.float32)
    return matrix @ query


_TOKEN = re.compile(r"[a-z0-9]+")

# Words that carry no retrieval signal. Hashing every "the" and "is" into the
# vector made unrelated texts look similar: "What is the capital of France?"
# scored 0.17 against a document about removing users, purely on function words.
_STOPWORDS = frozenset("""
a an and are as at be been but by can could did do does for from had has have
how i if in into is it its may me might must my of on or our shall should so
such than that the their them then there these they this those to us was we
were what when where which while who whom why will with would you your
""".split())


def _tokenise(text: str) -> list[str]:
    from .store import stem

    return [stem(t) for t in _TOKEN.findall(text.lower()) if t not in _STOPWORDS]


class HashingEmbedder:
    """Dependency-free embedder: hashed character n-grams with TF-IDF weighting.

    Known limits, stated plainly because they shape retrieval quality:

    * **No synonymy.** "car" and "automobile" are unrelated.
    * **No word order.** "policy refund" equals "refund policy".
    * **Hash collisions.** Unrelated features can share a dimension; more
      ``dims`` reduces this.

    What it does give: robustness to typos and morphology (via character
    n-grams, so "refunds" matches "refund"), zero install cost, and
    deterministic output -- the same text always yields the same vector, which
    makes tests reliable.
    """

    name = "hashing"
    semantic = False

    def __init__(self, dims: int | None = None) -> None:
        self.dims = dims or settings.hashing_dims
        # Document frequency, learned from whatever has been embedded so far,
        # so common words across the corpus are down-weighted.
        self._doc_freq: dict[int, int] = {}
        self._docs_seen = 0

    def _features(self, text: str) -> dict[int, float]:
        """Map text to {dimension: count} using words plus character 3-grams."""
        counts: dict[int, float] = {}
        tokens = _tokenise(text)

        for token in tokens:
            counts[self._bucket(token)] = counts.get(self._bucket(token), 0.0) + 1.0
            # Character n-grams give partial credit for shared morphology:
            # "refund" and "refunds" overlap on "ref", "efu", "fun", "und".
            padded = f"#{token}#"
            for i in range(len(padded) - 2):
                gram = padded[i : i + 3]
                bucket = self._bucket(f"~{gram}")
                counts[bucket] = counts.get(bucket, 0.0) + 0.5

        return counts

    def _bucket(self, feature: str) -> int:
        digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
        return int.from_bytes(digest, "big") % self.dims

    def fit(self, texts: list[str]) -> None:
        """Learn document frequencies so IDF weighting is meaningful."""
        for text in texts:
            self._docs_seen += 1
            for bucket in self._features(text):
                self._doc_freq[bucket] = self._doc_freq.get(bucket, 0) + 1

    def embed(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dims), dtype=np.float32)

        matrix = np.zeros((len(texts), self.dims), dtype=np.float32)
        total_docs = max(self._docs_seen, 1)

        for row, text in enumerate(texts):
            for bucket, count in self._features(text).items():
                # Sub-linear term frequency: a word appearing 20 times is not
                # 20x more important than one appearing once.
                tf = 1.0 + math.log(count) if count > 0 else 0.0
                df = self._doc_freq.get(bucket, 0)
                idf = math.log((total_docs + 1) / (df + 1)) + 1.0
                matrix[row, bucket] = tf * idf

        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return matrix / norms


class SentenceEmbedder:
    """Local transformer embeddings via sentence-transformers.

    The quality option: these vectors capture meaning, so "how do I get my
    money back" retrieves the refund policy even with no shared words. Costs a
    ~90 MB model download on first use (plus PyTorch, ~2 GB).
    """

    name = "sentence-transformers"
    semantic = True

    def __init__(self, model_name: str | None = None) -> None:
        from sentence_transformers import SentenceTransformer

        self.model_name = model_name or settings.embedding_model
        self._model = SentenceTransformer(self.model_name)
        # The accessor was renamed in sentence-transformers 6.x; support both so
        # the service runs on whichever version is installed.
        for attribute in ("get_embedding_dimension", "get_sentence_embedding_dimension"):
            getter = getattr(self._model, attribute, None)
            if callable(getter):
                self.dims = int(getter())
                break
        else:  # pragma: no cover - defensive
            self.dims = int(self._model.encode(["probe"]).shape[1])

    def fit(self, texts: list[str]) -> None:  # noqa: D401 - interface parity
        """No-op: the model is pre-trained."""

    def embed(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dims), dtype=np.float32)
        vectors = self._model.encode(
            texts, normalize_embeddings=True, show_progress_bar=False
        )
        return np.asarray(vectors, dtype=np.float32)


class ServerEmbedder:
    """Embeddings from the OpenAI-compatible backend, when it supports them."""

    name = "server"
    semantic = True

    def __init__(self, model: str | None = None) -> None:
        from openai import OpenAI

        self.model = model or settings.model
        self._client = OpenAI(
            base_url=settings.api_base,
            api_key=settings.api_key,
            timeout=settings.request_timeout,
        )
        # Probe once at construction: a backend that refuses embeddings should
        # fail here, where we can fall back, rather than on the first upload.
        probe = self.embed(["probe"])
        self.dims = int(probe.shape[1])

    def fit(self, texts: list[str]) -> None:  # noqa: D401 - interface parity
        """No-op: the model is pre-trained."""

    def embed(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, getattr(self, "dims", 1)), dtype=np.float32)
        response = self._client.embeddings.create(model=self.model, input=texts)
        matrix = np.asarray(
            [item.embedding for item in response.data], dtype=np.float32
        )
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return matrix / norms


def get_embedder(backend: str | None = None) -> Embedder:
    """Pick an embedder, preferring quality but never failing to start.

    ``auto`` tries server, then sentence-transformers, then hashing. An explicit
    backend name raises if unavailable, because silently substituting a weaker
    embedder would make retrieval quality mysterious.
    """
    choice = (backend or settings.embedding_backend).lower()

    if choice == "hashing":
        return HashingEmbedder()
    if choice == "sentence":
        return SentenceEmbedder()
    if choice == "server":
        return ServerEmbedder()
    if choice != "auto":
        raise ValueError(f"unknown embedding backend: {choice!r}")

    try:
        return ServerEmbedder()
    except Exception:
        pass
    try:
        return SentenceEmbedder()
    except Exception:
        pass
    return HashingEmbedder()
