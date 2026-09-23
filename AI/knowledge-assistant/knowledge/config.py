"""Configuration for the enterprise knowledge assistant.

Same shape as the other two projects: ``KA_``-prefixed environment variables or
a ``.env`` file, validated by pydantic at startup so a bad value stops the
server rather than silently becoming a default.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings. Override with KA_* env vars or a .env file."""

    model_config = SettingsConfigDict(
        env_prefix="KA_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        protected_namespaces=(),
    )

    # --- Model backend -------------------------------------------------
    api_base: str = Field(default="http://localhost:18790/v1")
    api_key: str = Field(default="not-needed")
    model: str = Field(default="gemma-4-26b-a4b")

    request_timeout: float = Field(default=300.0, gt=0)
    max_tokens: int = Field(default=4096, ge=256, le=32768)

    # Answering from retrieved context is closer to transcription than
    # creation: we want the same question over the same documents to give the
    # same answer.
    temperature: float = Field(default=0.1, ge=0.0, le=2.0)

    enable_thinking: bool = Field(default=False)
    use_structured_output: bool = Field(default=True)
    max_repair_attempts: int = Field(default=2, ge=0, le=5)

    # --- Embeddings ----------------------------------------------------
    # Which backend to use. "auto" prefers, in order: the model server (if it
    # supports /v1/embeddings), sentence-transformers (if installed), then the
    # dependency-free hashing embedder.
    #
    # Measured on this machine: the llama.cpp server returns
    #   501 "This server does not support embeddings. Start it with --embeddings"
    # so the fallback chain is not theoretical -- it is the normal path here.
    embedding_backend: str = Field(default="auto")  # auto|server|sentence|hashing
    embedding_model: str = Field(default="sentence-transformers/all-MiniLM-L6-v2")
    # Dimensions for the hashing embedder. Higher reduces collisions at the
    # cost of memory; 2048 is ample for a few thousand chunks.
    hashing_dims: int = Field(default=2048, ge=256, le=16384)

    # --- Chunking ------------------------------------------------------
    # Characters, not tokens: we have no tokeniser dependency, and for English
    # prose ~4 chars/token makes 1200 chars roughly 300 tokens.
    chunk_size: int = Field(default=1200, ge=200, le=8000)
    # Overlap keeps a sentence that straddles a boundary retrievable from both
    # sides. Without it, the one paragraph that answers a question can be split
    # in half and lose to worse-but-whole chunks.
    chunk_overlap: int = Field(default=200, ge=0, le=2000)
    min_chunk_chars: int = Field(default=80, ge=1)

    # --- Retrieval -----------------------------------------------------
    top_k: int = Field(default=6, ge=1, le=50)
    # Candidates pulled from each retriever before fusion. Larger than top_k so
    # the two rankings have something to disagree about.
    candidate_k: int = Field(default=20, ge=1, le=200)
    # Weight of dense (vector) vs lexical (BM25) results in the fusion.
    # 0.0 = pure BM25, 1.0 = pure vectors.
    dense_weight: float = Field(default=0.5, ge=0.0, le=1.0)
    # Below this fused score a chunk is not worth showing the model.
    min_score: float = Field(default=0.01, ge=0.0)
    # Minimum share of the question's content words that must appear in a chunk.
    # RRF ranks but does not measure relevance, so without an absolute gate an
    # off-topic question still returns its best-of-a-bad-lot passages.
    #
    # Calibrated on this corpus:
    #   "capital of France"            ->  0%   (refuse)
    #   "who won the world cup"        ->  0%   (refuse)
    #   "refund if I was charged twice" -> 25%  (answer)
    #   "tell me about MFA"            -> 33%   (answer)
    # 0.20 sits in the gap. Set it higher to refuse more readily.
    min_coverage: float = Field(default=0.20, ge=0.0, le=1.0)
    # Long questions are scored against a relaxed threshold, scaled by term
    # count: no single passage can contain most of a 30-word question's
    # vocabulary, because the answer is spread across several. This floor stops
    # the relaxation reaching zero, which would readmit off-topic questions.
    min_coverage_floor: float = Field(default=0.10, ge=0.0, le=1.0)
    # Semantic embedders can retrieve paraphrases with little or no term
    # overlap ("money back" vs "refund"). Allow a dense hit to bypass the
    # lexical coverage gate only when its cosine score is clearly strong.
    #
    # Calibrated on the benchmark corpus with all-MiniLM-L6-v2:
    #   on-topic paraphrases   -> 0.14 - 0.44
    #   off-topic questions    -> 0.06 - 0.11  (capital of France, sourdough)
    # 0.14 sits in the gap, and the rank cap keeps one lucky tail hit out.
    min_semantic_score: float = Field(default=0.14, ge=0.0, le=1.0)
    # Limit bypasses to top dense ranks. Set to 10 rather than 3 because the
    # genuinely correct passage often sits below near-duplicate or superseded
    # documents that share the question's topic.
    semantic_override_max_rank: int = Field(default=10, ge=1, le=50)
    # Total characters of context sent to the model.
    max_context_chars: int = Field(default=8000, ge=500)

    # --- Answering -----------------------------------------------------
    # Refuse rather than answer from general knowledge when retrieval finds
    # nothing. The entire point of the product is answers FROM THE DOCUMENTS.
    refuse_without_context: bool = Field(default=True)

    # --- Storage -------------------------------------------------------
    db_path: str = Field(default="knowledge.db")

    # --- Documents -----------------------------------------------------
    max_file_bytes: int = Field(default=20 * 1024 * 1024, ge=1024)
    max_pages: int = Field(default=200, ge=1)
    max_text_chars: int = Field(default=400_000, ge=500)
    min_text_chars: int = Field(default=20, ge=1)

    allowed_extensions: Annotated[tuple[str, ...], NoDecode] = Field(
        default=(".pdf", ".docx", ".txt", ".md", ".png", ".jpg", ".jpeg")
    )

    # --- OCR -----------------------------------------------------------
    ocr_languages: str = Field(default="eng+ara")
    ocr_min_confidence: float = Field(default=0.55, ge=0.0, le=1.0)

    # --- Cost tracking -------------------------------------------------
    cost_per_1k_input: float = Field(default=0.0, ge=0.0)
    cost_per_1k_output: float = Field(default=0.0, ge=0.0)

    @field_validator("allowed_extensions", mode="before")
    @classmethod
    def _parse_extensions(cls, v: object) -> object:
        if isinstance(v, str):
            return tuple(p.strip().lower() for p in v.split(",") if p.strip())
        return v

    @field_validator("api_base")
    @classmethod
    def _strip_trailing_slash(cls, v: str) -> str:
        return v.rstrip("/")

    @field_validator("chunk_overlap")
    @classmethod
    def _overlap_smaller_than_chunk(cls, v: int, info) -> int:
        size = info.data.get("chunk_size", 1200)
        if v >= size:
            raise ValueError(
                f"chunk_overlap ({v}) must be smaller than chunk_size ({size}); "
                "otherwise chunking never advances"
            )
        return v


settings = Settings()
