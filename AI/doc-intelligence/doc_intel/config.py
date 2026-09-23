"""Configuration for the document intelligence service.

Ported from the support platform: the shape is identical, only the field names
differ. Every value is overridable with a ``DI_``-prefixed environment variable
or a ``.env`` file, and pydantic validates types and ranges at startup so a bad
value stops the server rather than silently becoming a default.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings. Override with DI_* env vars or a .env file."""

    model_config = SettingsConfigDict(
        env_prefix="DI_",
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

    # Invoices produce more output than a ticket triage: a 20-line invoice is a
    # long JSON array. Generous ceiling, with finish_reason="length" detected in
    # llm.py so truncation is reported honestly rather than as malformed JSON.
    max_tokens: int = Field(default=8192, ge=512, le=32768)

    # Extraction is a transcription task, not a creative one -- we want the same
    # invoice to yield the same numbers every time.
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)

    # Whether the model may emit a reasoning block. Off is substantially faster
    # on models that honour it; re-verify on every model swap, because the flag
    # is silently ignored by backends that do not support it.
    enable_thinking: bool = Field(default=False)

    # Ask the backend to constrain generation to the JSON schema. Silently
    # ignored by servers that do not support it, which is why the client-side
    # parser in textproc.py is kept as a fallback.
    use_structured_output: bool = Field(default=True)

    # --- Reliability ---------------------------------------------------
    # 1 initial attempt + this many repairs driven by validation errors.
    max_repair_attempts: int = Field(default=2, ge=0, le=5)

    # --- Document limits -----------------------------------------------
    max_file_bytes: int = Field(default=10 * 1024 * 1024, ge=1024)  # 10 MB
    max_pages: int = Field(default=20, ge=1)
    # Characters of extracted text sent to the model. A 20-page contract would
    # otherwise blow the context window; invoices are short, so this is generous.
    max_text_chars: int = Field(default=24_000, ge=500)
    min_text_chars: int = Field(default=20, ge=1)

    allowed_extensions: Annotated[tuple[str, ...], NoDecode] = Field(
        default=(".pdf", ".docx", ".png", ".jpg", ".jpeg", ".txt")
    )

    # --- OCR -----------------------------------------------------------
    # Tesseract language packs, "+"-separated. This MUST list every script the
    # documents may contain: tesseract does not detect language, it applies the
    # models it is told to. Given only "eng", Arabic text is transcribed as
    # Latin gibberish and returned as a successful read -- the worst failure
    # mode, because nothing downstream can tell it went wrong.
    #
    # Installing packs:  brew install tesseract-lang  /  apt install tesseract-ocr-ara
    # Listing installed: tesseract --list-langs
    ocr_languages: str = Field(default="eng+ara")

    # Minimum mean per-word confidence tesseract must report for OCR output to
    # be trusted. Measured on this project:
    #   Arabic image read with 'eng'     -> 40%  (wrong script, gibberish)
    #   Arabic image read with 'ara+eng' -> 75%  (correct)
    #   English image read with 'eng'    -> 87%  (correct)
    # 55% sits in the gap and rejects the wrong-pack case without failing
    # legitimate imperfect scans.
    ocr_min_confidence: float = Field(default=0.55, ge=0.0, le=1.0)

    # --- Validation ----------------------------------------------------
    # Money comparisons need a tolerance: invoices round line items, so
    # subtotal + tax rarely equals total to the cent.
    amount_tolerance: float = Field(default=0.02, ge=0.0)

    # --- Cost tracking -------------------------------------------------
    # Local inference is free, but tracking a rate models what the same traffic
    # would cost on a hosted API. Read by telemetry.CallMetrics.cost_usd.
    cost_per_1k_input: float = Field(default=0.0, ge=0.0)
    cost_per_1k_output: float = Field(default=0.0, ge=0.0)

    # --- Storage -------------------------------------------------------
    db_path: str = Field(default="doc_intel.db")
    upload_dir: str = Field(default="uploads")

    @field_validator("allowed_extensions", mode="before")
    @classmethod
    def _parse_extensions(cls, v: object) -> object:
        """Accept '.pdf,.docx' from the environment as well as a real sequence."""
        if isinstance(v, str):
            return tuple(
                part.strip().lower() for part in v.split(",") if part.strip()
            )
        return v

    @field_validator("api_base")
    @classmethod
    def _strip_trailing_slash(cls, v: str) -> str:
        return v.rstrip("/")


settings = Settings()
