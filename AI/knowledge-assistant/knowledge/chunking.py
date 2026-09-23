"""Split document text into retrievable chunks.

Chunking decides what retrieval can possibly find. Two failure modes matter:

* **Chunks too large** -- the answer is buried among unrelated paragraphs, the
  embedding averages out to something vague, and the model is handed noise.
* **Chunks too small** -- the sentence that answers the question is separated
  from the heading that gives it meaning. "Customers may request a refund
  within 30 days" is useless if it is split away from "Enterprise Plans".

So this splits on *structure* first (blank lines, headings) and only falls back
to hard character cuts when a single block is genuinely oversized. Each chunk
carries the heading it lives under, which does double duty: it gives the
retriever more matchable text, and it gives the reader a citation that means
something.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .config import settings


@dataclass
class Chunk:
    """One retrievable passage."""

    text: str
    index: int
    heading: str = ""
    start_char: int = 0
    end_char: int = 0

    @property
    def embed_text(self) -> str:
        """Text used for embedding and indexing.

        The heading is prepended so a chunk about refund windows still matches
        a query mentioning "enterprise" when that word only appears in the
        section title.
        """
        return f"{self.heading}\n\n{self.text}".strip() if self.heading else self.text

    def as_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "text": self.text,
            "heading": self.heading,
            "start_char": self.start_char,
            "end_char": self.end_char,
        }


# A heading is a short line that is not a sentence: markdown hashes, numbered
# sections, ALL CAPS, or Title Case without terminal punctuation.
_MARKDOWN_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$")
_NUMBERED_HEADING = re.compile(r"^\s{0,3}((?:\d+\.){1,4}\d*|\([a-z]\)|[A-Z]\.)\s+(.{3,80})$")
_UNDERLINE = re.compile(r"^\s*[=\-_]{3,}\s*$")


def _is_heading(line: str) -> bool:
    """Whether a line looks like a section heading."""
    stripped = line.strip()
    if not stripped or len(stripped) > 90:
        return False
    if _MARKDOWN_HEADING.match(stripped) or _NUMBERED_HEADING.match(stripped):
        return True
    if stripped.endswith((".", ",", ";", ":")) and not stripped.endswith("..."):
        return False

    words = stripped.split()
    if len(words) > 12:
        return False

    letters = [c for c in stripped if c.isalpha()]
    if not letters:
        return False

    # Reject table cells that merely look like headings. Extracted PDF tables
    # produce lines such as "USD 650" or "USD 12,558.40": the letters are all
    # uppercase, so the ALL CAPS rule below would promote a price to a section
    # title. Measured on the benchmark corpus, this created chunks headed
    # "USD 650" whose body was "500,000 USD 0.007/call" -- semantically
    # meaningless fragments that then outranked real policy text.
    if any(c.isdigit() for c in stripped) and len(letters) / len(stripped) < 0.5:
        return False

    # ALL CAPS, e.g. "REFUND POLICY"
    if sum(1 for c in letters if c.isupper()) / len(letters) > 0.8:
        return True

    # Title Case, e.g. "Enterprise Refund Terms". Single words count too:
    # real policies are full of one-word section headings ("Receipts",
    # "Travel"), and missing them merges unrelated sections into one chunk.
    capitalised = sum(1 for w in words if w[:1].isupper())
    if len(words) == 1:
        return stripped[:1].isupper() and len(stripped) > 3 and stripped.isalpha()
    return capitalised / len(words) > 0.7


def _clean_heading(line: str) -> str:
    stripped = line.strip()
    md = _MARKDOWN_HEADING.match(stripped)
    if md:
        return md.group(1).strip()
    num = _NUMBERED_HEADING.match(stripped)
    if num:
        return f"{num.group(1)} {num.group(2)}".strip()
    return stripped


@dataclass
class _Block:
    """A paragraph plus the heading in force when it appeared."""

    text: str
    heading: str
    start: int
    blocks: list[str] = field(default_factory=list)


def _normalise_layout(text: str) -> str:
    """Insert paragraph breaks around headings when a PDF has none.

    PDF text extraction returns one newline per rendered line and no blank
    lines, so a document that looks well-structured on screen arrives as an
    undifferentiated wall of text. Splitting on ``\\n\\s*\\n`` then finds a
    single block, every heading is missed, and each chunk is cited as
    "somefile.pdf" with no section -- which is useless to a reader checking an
    answer.

    Measured on the benchmark corpus: 0 of 21 PDF chunks had a heading before
    this, because the blank lines the splitter relies on simply were not there.

    This re-inserts a blank line before and after any line that looks like a
    heading, restoring the structure the splitter expects. Documents that
    already have blank lines are unaffected.
    """
    if "\n\n" in text:
        # Already paragraph-separated; trust the original layout.
        return text

    out: list[str] = []
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped and _is_heading(stripped):
            if out and out[-1].strip():
                out.append("")
            out.append(stripped)
            out.append("")
        else:
            out.append(line)
    return "\n".join(out)


def _split_into_blocks(text: str) -> list[_Block]:
    """Group the document into paragraphs, tracking the current heading."""
    blocks: list[_Block] = []
    heading = ""
    cursor = 0

    text = _normalise_layout(text)

    for raw in re.split(r"\n\s*\n", text):
        paragraph = raw.strip()
        start = text.find(raw, cursor)
        if start >= 0:
            cursor = start + len(raw)

        if not paragraph:
            continue

        lines = paragraph.split("\n")

        # A paragraph that is only a heading updates context and adds no text.
        if len(lines) == 1 and _is_heading(lines[0]):
            heading = _clean_heading(lines[0])
            continue

        # "HEADING\nbody text..." -- common in PDFs where the blank line is lost.
        if len(lines) > 1 and _is_heading(lines[0]) and not _UNDERLINE.match(lines[1]):
            heading = _clean_heading(lines[0])
            paragraph = "\n".join(lines[1:]).strip()
            if not paragraph:
                continue

        blocks.append(_Block(text=paragraph, heading=heading, start=max(start, 0)))

    return blocks


def _tail_on_word_boundary(text: str, overlap: int) -> str:
    """The last ``overlap`` characters, trimmed forward to a word boundary.

    Slicing by raw character count cuts words in half: the benchmark corpus
    produced a chunk starting "esk customers. It applies to all paid plans",
    which had lost "NovaD" from "NovaDesk". A truncated word helps neither the
    embedder nor a human reading the cited passage, so the tail is advanced to
    the next whitespace when the cut lands inside a word.
    """
    if overlap <= 0 or not text:
        return ""
    tail = text[-overlap:]
    # A cut inside a word means the character before the tail is not a space.
    if len(text) > overlap and not text[-overlap - 1].isspace():
        _, separator, remainder = tail.partition(" ")
        if separator:
            tail = remainder
    return tail.lstrip()


def _split_oversized(text: str, size: int, overlap: int) -> list[str]:
    """Hard-split a block that is larger than one chunk.

    Cuts at sentence boundaries where possible so a chunk does not begin
    mid-clause.
    """
    sentences = re.split(r"(?<=[.!?])\s+", text)
    pieces: list[str] = []
    current = ""

    for sentence in sentences:
        # A single sentence longer than the chunk size (a table row, a URL
        # dump): cut it by characters, there is nothing better to do.
        if len(sentence) > size:
            if current:
                pieces.append(current.strip())
                current = ""
            for i in range(0, len(sentence), size - overlap):
                pieces.append(sentence[i : i + size].strip())
            continue

        if len(current) + len(sentence) + 1 > size:
            pieces.append(current.strip())
            # Carry the tail of the previous chunk so a boundary-straddling
            # sentence remains retrievable from both sides.
            carry = _tail_on_word_boundary(current, overlap)
            current = f"{carry} {sentence}".strip() if carry else sentence
        else:
            current = f"{current} {sentence}".strip()

    if current.strip():
        pieces.append(current.strip())
    return [p for p in pieces if p]


def chunk_text(
    text: str,
    *,
    size: int | None = None,
    overlap: int | None = None,
) -> list[Chunk]:
    """Split document text into overlapping, heading-aware chunks."""
    size = size or settings.chunk_size
    overlap = overlap if overlap is not None else settings.chunk_overlap
    if overlap >= size:
        raise ValueError("overlap must be smaller than size")

    if not text or not text.strip():
        return []

    chunks: list[Chunk] = []
    buffer = ""
    buffer_heading = ""
    buffer_start = 0

    def flush() -> None:
        nonlocal buffer, buffer_heading, buffer_start
        body = buffer.strip()
        # A chunk under the minimum is kept when it has a heading: a short
        # section such as "Receipts / Keep every receipt above $25" is a
        # complete, answerable fact. Dropping it would make the document
        # silently unsearchable for exactly the question it answers.
        if body and (len(body) >= settings.min_chunk_chars or buffer_heading):
            chunks.append(
                Chunk(
                    text=body,
                    index=len(chunks),
                    heading=buffer_heading,
                    start_char=buffer_start,
                    end_char=buffer_start + len(body),
                )
            )
        buffer = ""

    for block in _split_into_blocks(text):
        # A new heading starts a new chunk: mixing sections dilutes both.
        if block.heading != buffer_heading and buffer:
            flush()

        if not buffer:
            buffer_heading = block.heading
            buffer_start = block.start

        if len(block.text) > size:
            flush()
            buffer_heading = block.heading
            for piece in _split_oversized(block.text, size, overlap):
                if len(piece) >= settings.min_chunk_chars or block.heading:
                    chunks.append(
                        Chunk(
                            text=piece,
                            index=len(chunks),
                            heading=block.heading,
                            start_char=block.start,
                            end_char=block.start + len(piece),
                        )
                    )
            continue

        if len(buffer) + len(block.text) + 2 > size:
            tail = buffer[-overlap:] if overlap else ""
            flush()
            buffer_heading = block.heading
            buffer_start = block.start
            buffer = f"{tail}\n\n{block.text}".strip() if tail else block.text
        else:
            buffer = f"{buffer}\n\n{block.text}".strip() if buffer else block.text

    flush()

    # Re-number after the oversized path may have appended out of order.
    for position, chunk in enumerate(chunks):
        chunk.index = position
    return chunks
