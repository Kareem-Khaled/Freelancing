"""Turn an uploaded file into plain text.

This is the layer with no equivalent in the support platform: tickets arrive as
text, documents arrive as bytes in one of several formats.

Design notes
------------
* **Detect by content, not by filename.** A file called ``invoice.pdf`` may be a
  PNG someone renamed. Magic bytes are checked first, and the extension is only
  a fallback.
* **Every failure is a typed result, not an exception.** A corrupt PDF is a
  normal outcome for an upload endpoint, not an error condition -- the API
  should return a clear reason, not a 500.
* **Scanned PDFs are detected, not silently mis-handled.** A PDF containing only
  images yields almost no text. Reporting that plainly is far more useful than
  handing the model an empty string and letting it hallucinate an invoice.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from .config import settings


class DocFormat(str, Enum):
    PDF = "pdf"
    DOCX = "docx"
    IMAGE = "image"
    TEXT = "text"
    UNKNOWN = "unknown"


class ParseProblem(str, Enum):
    EMPTY_FILE = "empty_file"
    TOO_LARGE = "too_large"
    UNSUPPORTED_FORMAT = "unsupported_format"
    CORRUPT = "corrupt"
    NO_TEXT_LAYER = "no_text_layer"
    TOO_LITTLE_TEXT = "too_little_text"
    PASSWORD_PROTECTED = "password_protected"
    # OCR returned text, but it looks like the wrong script read through the
    # wrong language model. Rejecting is safer than passing gibberish to the
    # extractor, which would happily invent an invoice from it.
    OCR_UNREADABLE = "ocr_unreadable"


@dataclass
class ParseResult:
    ok: bool
    text: str = ""
    doc_format: DocFormat = DocFormat.UNKNOWN
    pages: int = 0
    problem: ParseProblem | None = None
    detail: str = ""
    truncated: bool = False
    # Tesseract's own mean per-word confidence, 0..1. Only meaningful when
    # ``ocr`` is True.
    ocr_confidence: float = 0.0
    # True when the text came from OCR rather than an embedded text layer.
    # OCR silently drops characters, words and whole lines, so downstream
    # checks should treat the result as less trustworthy -- a missing invoice
    # number may mean "not on the document" or "the scanner lost it".
    ocr: bool = False

    @property
    def failed(self) -> bool:
        return not self.ok


# Magic bytes. Checked before the extension, because filenames lie.
_SIGNATURES: list[tuple[bytes, DocFormat]] = [
    (b"%PDF-", DocFormat.PDF),
    (b"\x89PNG\r\n\x1a\n", DocFormat.IMAGE),
    (b"\xff\xd8\xff", DocFormat.IMAGE),          # JPEG
    (b"GIF87a", DocFormat.IMAGE),
    (b"GIF89a", DocFormat.IMAGE),
    (b"BM", DocFormat.IMAGE),                    # BMP
]

_EXTENSION_FORMATS = {
    ".pdf": DocFormat.PDF,
    ".docx": DocFormat.DOCX,
    ".png": DocFormat.IMAGE,
    ".jpg": DocFormat.IMAGE,
    ".jpeg": DocFormat.IMAGE,
    ".gif": DocFormat.IMAGE,
    ".bmp": DocFormat.IMAGE,
    ".webp": DocFormat.IMAGE,
    ".txt": DocFormat.TEXT,
    ".md": DocFormat.TEXT,
}

_WHITESPACE_RUN = re.compile(r"[ \t\r\f\v]+")
_NEWLINE_RUN = re.compile(r"\n{3,}")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def detect_format(data: bytes, filename: str = "") -> DocFormat:
    """Identify the format from magic bytes, falling back to the extension."""
    for signature, fmt in _SIGNATURES:
        if data.startswith(signature):
            return fmt

    # DOCX (and every Office format) is a ZIP; look inside for the marker.
    if data.startswith(b"PK\x03\x04"):
        return DocFormat.DOCX if b"word/" in data[:4000] else DocFormat.UNKNOWN

    suffix = Path(filename).suffix.lower()
    if suffix in _EXTENSION_FORMATS:
        return _EXTENSION_FORMATS[suffix]

    # Plain text has no signature: if it decodes cleanly, treat it as text.
    try:
        data[:2000].decode("utf-8")
        return DocFormat.TEXT
    except UnicodeDecodeError:
        return DocFormat.UNKNOWN


def _normalise(text: str) -> str:
    text = _CONTROL.sub("", text)
    text = _WHITESPACE_RUN.sub(" ", text)
    return _NEWLINE_RUN.sub("\n\n", text).strip()


def _parse_pdf(data: bytes) -> ParseResult:
    try:
        import io

        from pypdf import PdfReader
    except ImportError:  # pragma: no cover
        return ParseResult(
            False, problem=ParseProblem.UNSUPPORTED_FORMAT,
            detail="pypdf is not installed", doc_format=DocFormat.PDF,
        )

    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            # An empty password unlocks many "protected" invoices.
            try:
                reader.decrypt("")
            except Exception:
                return ParseResult(
                    False, problem=ParseProblem.PASSWORD_PROTECTED,
                    detail="PDF is password protected", doc_format=DocFormat.PDF,
                )

        total_pages = len(reader.pages)
        pages = []
        for page in reader.pages[: settings.max_pages]:
            try:
                pages.append(page.extract_text() or "")
            except Exception:
                pages.append("")  # one bad page should not lose the document

        text = _normalise("\n\n".join(pages))
    except Exception as exc:
        return ParseResult(
            False, problem=ParseProblem.CORRUPT,
            detail=f"could not read PDF: {exc}", doc_format=DocFormat.PDF,
        )

    if len(text) < settings.min_text_chars:
        # Almost certainly a scan. Saying so is more useful than passing an
        # empty string to the model and letting it invent an invoice.
        return ParseResult(
            False, text=text, doc_format=DocFormat.PDF, pages=total_pages,
            problem=ParseProblem.NO_TEXT_LAYER,
            detail=(
                "PDF has no extractable text layer — it is probably a scan. "
                "OCR is required."
            ),
        )

    return ParseResult(
        True, text=text, doc_format=DocFormat.PDF, pages=total_pages,
        truncated=total_pages > settings.max_pages,
    )


def _parse_docx(data: bytes) -> ParseResult:
    try:
        import io

        import docx
    except ImportError:  # pragma: no cover
        return ParseResult(
            False, problem=ParseProblem.UNSUPPORTED_FORMAT,
            detail="python-docx is not installed", doc_format=DocFormat.DOCX,
        )

    try:
        document = docx.Document(io.BytesIO(data))
        parts = [p.text for p in document.paragraphs if p.text.strip()]

        # Invoice totals almost always live in a table, so tables are flattened
        # into pipe-separated rows rather than skipped.
        for table in document.tables:
            for row in table.rows:
                cells = [c.text.strip() for c in row.cells]
                if any(cells):
                    parts.append(" | ".join(cells))

        text = _normalise("\n".join(parts))
    except Exception as exc:
        return ParseResult(
            False, problem=ParseProblem.CORRUPT,
            detail=f"could not read DOCX: {exc}", doc_format=DocFormat.DOCX,
        )

    if len(text) < settings.min_text_chars:
        return ParseResult(
            False, text=text, doc_format=DocFormat.DOCX,
            problem=ParseProblem.TOO_LITTLE_TEXT,
            detail="DOCX contains almost no text",
        )

    return ParseResult(True, text=text, doc_format=DocFormat.DOCX, pages=1)


def _parse_image(data: bytes) -> ParseResult:
    """Images need OCR, which is not wired up yet.

    Reporting this honestly is deliberate. The alternative -- returning empty
    text and letting the model produce a confident, entirely invented invoice --
    is the worst possible failure mode for a financial document.
    """
    try:
        import io

        from PIL import Image
    except ImportError:  # pragma: no cover
        return ParseResult(
            False, problem=ParseProblem.UNSUPPORTED_FORMAT,
            detail="Pillow is not installed", doc_format=DocFormat.IMAGE,
        )

    try:
        image = Image.open(io.BytesIO(data))
        image.verify()
        size = f"{image.width}x{image.height}"
    except Exception as exc:
        return ParseResult(
            False, problem=ParseProblem.CORRUPT,
            detail=f"could not read image: {exc}", doc_format=DocFormat.IMAGE,
        )

    try:
        import pytesseract  # noqa: F401
        from PIL import Image as PILImage

        # Languages must be declared: tesseract applies the models it is given,
        # it does not detect script. See settings.ocr_languages.
        text, confidence = _ocr_confidence(
            PILImage.open(io.BytesIO(data)), settings.ocr_languages
        )

        if len(text) < settings.min_text_chars:
            return ParseResult(
                False, text=text, doc_format=DocFormat.IMAGE, ocr=True,
                problem=ParseProblem.TOO_LITTLE_TEXT,
                detail=f"OCR found almost no text in this {size} image",
            )

        if confidence < settings.ocr_min_confidence:
            return ParseResult(
                False, text=text, doc_format=DocFormat.IMAGE, ocr=True,
                ocr_confidence=confidence,
                problem=ParseProblem.OCR_UNREADABLE,
                detail=(
                    f"OCR confidence was only {confidence:.0%}. The document is "
                    f"probably in a script that '{settings.ocr_languages}' does "
                    f"not cover, or the scan is too poor. Check "
                    f"`tesseract --list-langs` and set DI_OCR_LANGUAGES."
                ),
            )

        return ParseResult(
            True, text=text, doc_format=DocFormat.IMAGE, pages=1, ocr=True,
            ocr_confidence=confidence,
        )
    except ImportError:
        return ParseResult(
            False, doc_format=DocFormat.IMAGE,
            problem=ParseProblem.NO_TEXT_LAYER,
            detail=(
                f"Image received ({size}) but OCR is not available. Install "
                "pytesseract and the tesseract binary, or send a text-based PDF."
            ),
        )
    except Exception as exc:
        return ParseResult(
            False, doc_format=DocFormat.IMAGE, problem=ParseProblem.CORRUPT,
            detail=f"OCR failed: {exc}",
        )


def _ocr_confidence(image, lang: str) -> tuple[str, float]:
    """Run OCR and return the text alongside tesseract's own mean confidence.

    Tesseract never raises on a wrong language pack: it maps the unfamiliar
    script onto the alphabet it knows and returns confident-looking nonsense.
    Arabic read with ``eng`` produced ``'JI6 Jus JJes sole'`` -- 217 characters,
    ``ok=True``, completely meaningless.

    An earlier attempt guessed at quality by looking for vowels and odd
    capitalisation. It scored that gibberish 100%, because tesseract's garbage
    is built from real letters. The per-word confidence it already computes is a
    direct measurement rather than a guess, and separates the cases cleanly:

        Arabic image, eng pack      -> 40%   (wrong script)
        Arabic image, ara+eng pack  -> 75%   (correct)
        English image, eng pack     -> 87%   (correct)
    """
    import pytesseract

    data = pytesseract.image_to_data(
        image, lang=lang, output_type=pytesseract.Output.DICT
    )
    scores = [int(c) for c in data["conf"] if int(c) >= 0]
    words = [w for w in data["text"] if w.strip()]
    text = _normalise(" ".join(data["text"]))
    confidence = (sum(scores) / len(scores) / 100) if scores else 0.0
    return text, (confidence if words else 0.0)


def _parse_text(data: bytes) -> ParseResult:
    for encoding in ("utf-8", "utf-16", "latin-1"):
        try:
            text = _normalise(data.decode(encoding))
            break
        except UnicodeDecodeError:
            continue
    else:  # pragma: no cover - latin-1 decodes anything
        return ParseResult(
            False, problem=ParseProblem.CORRUPT,
            detail="could not decode text", doc_format=DocFormat.TEXT,
        )

    if len(text) < settings.min_text_chars:
        return ParseResult(
            False, text=text, doc_format=DocFormat.TEXT,
            problem=ParseProblem.TOO_LITTLE_TEXT,
            detail="file contains almost no text",
        )
    return ParseResult(True, text=text, doc_format=DocFormat.TEXT, pages=1)


_PARSERS = {
    DocFormat.PDF: _parse_pdf,
    DocFormat.DOCX: _parse_docx,
    DocFormat.IMAGE: _parse_image,
    DocFormat.TEXT: _parse_text,
}


def parse_document(data: bytes, filename: str = "") -> ParseResult:
    """Extract text from an uploaded file.

    Guards run cheapest-first, exactly as in the support platform's input layer:
    rejecting a 50 MB upload costs nothing, while an inference call is expensive.
    """
    if not data:
        return ParseResult(False, problem=ParseProblem.EMPTY_FILE, detail="file is empty")

    if len(data) > settings.max_file_bytes:
        return ParseResult(
            False, problem=ParseProblem.TOO_LARGE,
            detail=(
                f"file is {len(data) / 1_048_576:.1f} MB, limit is "
                f"{settings.max_file_bytes / 1_048_576:.0f} MB"
            ),
        )

    doc_format = detect_format(data, filename)
    parser = _PARSERS.get(doc_format)
    if parser is None:
        return ParseResult(
            False, doc_format=doc_format, problem=ParseProblem.UNSUPPORTED_FORMAT,
            detail=(
                f"unsupported file type; accepted: "
                f"{', '.join(settings.allowed_extensions)}"
            ),
        )

    result = parser(data)

    # Cap what reaches the model. Invoice totals sit at the END of a document,
    # so when truncating we keep the head and the tail and drop the middle --
    # losing the totals would defeat the purpose.
    if result.ok and len(result.text) > settings.max_text_chars:
        limit = settings.max_text_chars
        head = result.text[: int(limit * 0.6)]
        tail = result.text[-int(limit * 0.35):]
        result.text = f"{head}\n\n[... middle of document omitted ...]\n\n{tail}"
        result.truncated = True

    return result
