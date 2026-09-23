"""Central configuration, backed by pydantic-settings.

Every value can be overridden with an ``SP_``-prefixed environment variable or
an entry in a local ``.env`` file, so the same code runs unchanged on a laptop,
in CI and in production.

Unlike a hand-rolled ``os.environ`` reader, pydantic validates types and ranges
at startup and raises a descriptive error. That is deliberate: a server that
refuses to boot on bad config is far better than one that silently falls back to
a default you did not intend and behaves oddly hours later.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings. Override with SP_* env vars or a .env file."""

    model_config = SettingsConfigDict(
        env_prefix="SP_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        # Without this, pydantic warns about the field named ``model``.
        protected_namespaces=(),
    )

    # --- Model backend -------------------------------------------------
    api_base: str = Field(
        default="http://localhost:18790/v1",
        description="OpenAI-compatible endpoint.",
    )
    api_key: str = Field(default="not-needed", description="Ignored by local servers.")
    model: str = Field(default="gemma-4-26b-a4b", description="Model name to request.")

    request_timeout: float = Field(default=300.0, gt=0, description="Seconds per HTTP call.")

    # Token ceiling for one generation. History of this number: 2048 truncated
    # the JSON mid-object; 4096 was fine until tool grounding pushed reasoning to
    # ~3855 tokens; 6144 restored headroom. With thinking disabled real usage is
    # ~200-600 tokens, so this is now only a safety net.
    max_tokens: int = Field(default=6144, ge=256, le=32768)

    temperature: float = Field(default=0.2, ge=0.0, le=2.0)

    # Reasoning ("thinking") models spend most of their output budget on a block
    # that is discarded before validation. Whether it can be disabled is
    # MODEL-SPECIFIC and must be re-verified on every model swap:
    #
    #   qwen-3.5-35b     -> ignores every documented switch; thinking forced
    #   gemma-4-26b-a4b  -> honours it; 1137 -> 210 output tokens, 30s -> 6s,
    #                       with no measurable loss in classification quality
    #
    # Sending the flag to a model that ignores it is harmless, so it defaults to
    # False (thinking suppressed) for speed.
    enable_thinking: bool = Field(
        default=False,
        description="Let the model emit its reasoning block. Off is ~2.5x faster.",
    )

    # Ask the backend to constrain generation to the JSON schema
    # ("structured outputs" / grammar-constrained decoding). When supported this
    # guarantees well-formed JSON with correct enum values at generation time,
    # which removes most repair rounds.
    #
    # Measured on gemma-4-26b-a4b via llama.cpp:
    #   no constraint          -> wrapped output in ```json fences (invalid)
    #   response_format=json_object -> valid JSON, but invented its own shape
    #   response_format=json_schema -> valid JSON in exactly our shape
    #
    # Support is MODEL- AND SERVER-SPECIFIC. A backend that does not understand
    # the field ignores it silently, so the client-side parse/repair path in
    # llm.py is kept as a fallback and must never be removed on the assumption
    # that this flag is doing its job.
    use_structured_output: bool = Field(
        default=True,
        description="Send response_format=json_schema to constrain generation.",
    )

    # --- Reliability ---------------------------------------------------
    # 1 initial attempt + this many repair attempts driven by validation errors.
    max_repair_attempts: int = Field(default=2, ge=0, le=5)

    # --- Tools ---------------------------------------------------------
    # Tool calling grounds the analysis in real account data. Each tool round
    # trip is another generation (~4-5s on the current model), so it is opt-out.
    enable_tools: bool = Field(default=True)
    # Hard stop: a model that keeps calling tools would otherwise loop forever.
    max_tool_iterations: int = Field(default=4, ge=1, le=10)

    # --- Input guards --------------------------------------------------
    max_message_chars: int = Field(default=8000, ge=100)
    min_message_chars: int = Field(default=3, ge=1)
    max_history_messages: int = Field(default=20, ge=1)

    # --- Language ------------------------------------------------------
    # The model reads and replies in any language it knows, so there is no
    # technical restriction and this is EMPTY by default: every language is
    # handled.
    #
    # This exists only for a staffing reality. Most tickets are routed to a human
    # for approval, and an agent cannot meaningfully approve a refund reply they
    # cannot read. A team that can only review English and Arabic can set:
    #
    #   SP_SUPPORTED_LANGUAGES=en,ar
    #
    # Tickets in other languages are then still analysed and still get a draft
    # reply in the customer's language -- they are just tagged for someone who
    # can verify it. Leave it empty unless you have that constraint.
    #
    # ``NoDecode`` is required: without it pydantic-settings tries to JSON-parse
    # any non-scalar field straight from the env var, *before* validators run, so
    # "en,ar" fails with a JSONDecodeError.
    supported_languages: Annotated[tuple[str, ...], NoDecode] = Field(default=())

    # --- Cost tracking -------------------------------------------------
    # Local inference is free, but tracking a rate models what the same traffic
    # would cost on a hosted API.
    cost_per_1k_input: float = Field(default=0.0, ge=0.0)
    cost_per_1k_output: float = Field(default=0.0, ge=0.0)

    # --- Storage -------------------------------------------------------
    db_path: str = Field(default="support_platform.db")

    @field_validator("supported_languages", mode="before")
    @classmethod
    def _parse_languages(cls, v: object) -> object:
        """Accept 'en,ar' from the environment as well as a real sequence."""
        if isinstance(v, str):
            return tuple(part.strip().lower() for part in v.split(",") if part.strip())
        return v

    @field_validator("api_base")
    @classmethod
    def _strip_trailing_slash(cls, v: str) -> str:
        return v.rstrip("/")


settings = Settings()
