"""Fallback text utilities: reasoning-tag stripping and tolerant JSON extraction.

This is the **safety net**, not the primary mechanism. When the backend supports
``response_format=json_schema`` (see ``settings.use_structured_output``) the
model is grammar-constrained and its output parses with a plain
``json.loads``. Measured on gemma-4-26b-a4b: clean JSON on 5/5 happy-path
samples, on prompt-injection attempts, on tickets containing literal braces and
quotes, and at temperature 0.9.

It is still here because every one of those guarantees is model- and
server-specific, and this project has already been burned three times by flags
that were accepted and silently ignored. The cases it still covers:

* a backend that ignores ``response_format`` (qwen-3.5-35b ignored every such
  flag) and wraps its answer in ```` ```json ```` fences or prose
* ``SP_ENABLE_THINKING=1``, or a model that inlines ``<think>`` in ``content``
  rather than splitting it into ``reasoning_content``
* a reply cut off at ``max_tokens`` mid-object
* small-model syntax slips such as a trailing comma

Everything here is pure string handling with no network calls, which makes it
cheap to unit-test.
"""

from __future__ import annotations

import json
import re
from typing import Any

THINK_OPEN = "<think>"
THINK_CLOSE = "</think>"

_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL)
_STRAY_THINK = re.compile(r"</?think>")
_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)
# Trailing commas before a closing brace/bracket -- the single most common
# JSON syntax error produced by small models.
_TRAILING_COMMA = re.compile(r",(\s*[}\]])")


def strip_think(text: str) -> str:
    """Remove ``<think>...</think>`` spans and stray tags from a full response."""
    if not text:
        return ""
    text = _THINK_BLOCK.sub("", text)
    text = _STRAY_THINK.sub("", text)
    return text.strip()


def _balanced_objects(text: str) -> list[str]:
    """Return every balanced ``{...}`` span, ignoring braces inside strings."""
    spans: list[str] = []
    depth = 0
    start = -1
    in_string = False
    escape = False

    for i, ch in enumerate(text):
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            if depth:
                depth -= 1
                if depth == 0 and start >= 0:
                    spans.append(text[start : i + 1])
    return spans


def extract_json(text: str) -> dict[str, Any]:
    """Pull a JSON object out of a noisy completion.

    Tries, in order: fenced code blocks, the whole string, then each balanced
    ``{...}`` span (last first, since the model tends to restate its final
    answer at the end). Raises ``ValueError`` when nothing parses.
    """
    if not text or not text.strip():
        raise ValueError("model returned an empty response")

    cleaned = strip_think(text)
    candidates: list[str] = []

    for match in _FENCE.findall(cleaned):
        candidates.append(match.strip())

    candidates.append(cleaned.strip())
    # Last span first: the model often "drafts" then repeats the final JSON.
    candidates.extend(reversed(_balanced_objects(cleaned)))

    for candidate in candidates:
        if not candidate:
            continue
        for attempt in (candidate, _TRAILING_COMMA.sub(r"\1", candidate)):
            try:
                parsed = json.loads(attempt)
            except (json.JSONDecodeError, ValueError):
                continue
            if isinstance(parsed, dict):
                return parsed
            if isinstance(parsed, list) and parsed and isinstance(parsed[0], dict):
                return parsed[0]

    preview = cleaned[:200].replace("\n", " ")
    raise ValueError(f"no JSON object found in model output (starts with: {preview!r})")
