"""Input guards: reject or repair bad ticket content before it reaches the model.

Every rejection here saves an expensive inference call, so this runs first in
the pipeline. The rules cover the failure modes that actually show up in a
support inbox: empty bodies, pasted log dumps and binary/control-character noise.

Language is NOT handled here. The model detects it during analysis and replies
in the same language, so routing by language is a business decision in
``rules.py`` rather than a gate that blocks tickets before anyone sees them.

Guiding principle: **fail open, not closed.** A ticket we cannot confidently
judge is accepted and flagged, never dropped. Wrongly blocking a paying customer
is worse than spending one inference call on an odd message.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from .config import settings


class InputProblem(str, Enum):
    EMPTY = "empty"
    TOO_SHORT = "too_short"
    TOO_LONG = "too_long"
    MALFORMED = "malformed"
    NOT_TEXT = "not_text"


@dataclass
class ValidationResult:
    ok: bool
    text: str = ""
    problem: InputProblem | None = None
    detail: str = ""
    truncated: bool = False

    @property
    def rejected(self) -> bool:
        return not self.ok


# Control characters except tab/newline/carriage-return.
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_WHITESPACE_RUN = re.compile(r"[ \t\r\f\v]+")
_NEWLINE_RUN = re.compile(r"\n{3,}")

def validate_message(raw: object) -> ValidationResult:
    """Normalise and validate a single inbound customer message."""
    # --- type / malformed ------------------------------------------
    if raw is None:
        return ValidationResult(False, problem=InputProblem.EMPTY, detail="message is None")
    if isinstance(raw, (bytes, bytearray)):
        try:
            raw = raw.decode("utf-8")
        except UnicodeDecodeError:
            return ValidationResult(
                False, problem=InputProblem.NOT_TEXT, detail="message is not valid UTF-8"
            )
    if not isinstance(raw, str):
        return ValidationResult(
            False,
            problem=InputProblem.MALFORMED,
            detail=f"expected a string, got {type(raw).__name__}",
        )

    # --- control-character / binary noise ---------------------------
    control_count = len(_CONTROL.findall(raw))
    text = _CONTROL.sub("", raw)
    if raw and control_count / max(len(raw), 1) > 0.3:
        return ValidationResult(
            False,
            problem=InputProblem.NOT_TEXT,
            detail="message is mostly control characters (binary payload?)",
        )

    # --- whitespace normalisation -----------------------------------
    text = _WHITESPACE_RUN.sub(" ", text)
    text = _NEWLINE_RUN.sub("\n\n", text).strip()

    if not text:
        return ValidationResult(False, problem=InputProblem.EMPTY, detail="message is empty")
    if len(text) < settings.min_message_chars:
        return ValidationResult(
            False,
            text=text,
            problem=InputProblem.TOO_SHORT,
            detail=f"message shorter than {settings.min_message_chars} characters",
        )

    # --- length -----------------------------------------------------
    truncated = False
    if len(text) > settings.max_message_chars:
        limit = settings.max_message_chars
        # Keep the head and the tail: the ask is usually at one end, and a
        # pasted stack trace in the middle is the least useful part.
        head = text[: int(limit * 0.7)].rsplit(" ", 1)[0]
        tail = text[-int(limit * 0.25):].split(" ", 1)[-1]
        text = f"{head}\n\n[... {len(text) - len(head) - len(tail)} characters truncated ...]\n\n{tail}"
        truncated = True

    # Language is deliberately NOT checked here. The model detects it as part of
    # the analysis and writes its draft reply in the same language, so a
    # pre-filter would be duplicated work -- and a wrong guess would block a real
    # customer before anyone saw the ticket. Routing by language is a business
    # decision, applied in rules.py once the language is actually known.
    return ValidationResult(True, text=text, truncated=truncated)
