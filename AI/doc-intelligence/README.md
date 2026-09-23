# AI Document Intelligence — Invoice Extraction API

Turns PDF, DOCX, image or text invoices into validated structured data.

```
Upload (PDF / DOCX / image / text)
      ↓
Parsing            detect by content, extract text, reject what cannot be read
      ↓
LLM                local model via an OpenAI-compatible endpoint
      ↓
Parse + repair     constrained JSON, normalise amounts/dates/currency, validate
      ↓            ↑ on failure: retry with the exact validation error
Extraction         vendor, invoice_number, date, currency, totals, line items
      ↓
VALIDATION         deterministic arithmetic — do the numbers actually add up?
      ↓
Review status      auto_approved / needs_review / rejected + findings
      ↓
SQLite             documents, extractions, llm_calls
```

## Quick start

```bash
cd doc-intelligence
pip install -r requirements.txt

uvicorn doc_intel.api:app --reload --port 8900
```

- **Web UI** — <http://127.0.0.1:8900>
- **Interactive API docs** — <http://127.0.0.1:8900/docs>

```bash
# Upload -> 202 Accepted
curl -X POST http://127.0.0.1:8900/documents -F "file=@samples/invoice_clean.txt"

# Poll
curl http://127.0.0.1:8900/documents/DOC-XXXX

# Result
curl http://127.0.0.1:8900/documents/DOC-XXXX/extraction

# Tests (offline, no model server needed)
python3 -m unittest discover -s tests
```

## Web UI

Drag-and-drop upload with sample buttons for the interesting cases (clean
invoice, bad arithmetic, not-an-invoice). Dark theme with a fixed palette, so it
does not depend on the OS light/dark setting.

The **execution trace** is the point of the UI. It streams live while the
document is processed and shows, for every step:

```
  0.0s [parse   ] Read TEXT, 1 page(s)          → view extracted text
 12.4s [llm     ] extract → 386 tokens in 12.4s → view prompt & response
 12.4s [extract ] Extracted
 12.4s [validate] items_sum                     ✗ Line items sum to 1150.00
                                                  but subtotal is 1200.00
 12.4s [validate] Review status: rejected
 12.4s [store   ] Saved as DOC-950CBE3106
```

Two disclosures matter when an extraction looks wrong:

- **`view extracted text`** on the parse step — the text the model actually
  received. The first question is always "did we read the document correctly?",
  and this answers it without re-running anything.
- **`view prompt & response`** on the model step — the exact request and raw
  reply, including a repair round's failed attempt alongside the corrected one.

## API

| Method | Route | Purpose |
|---|---|---|
| `POST` | `/documents` | Upload → **202** with `document_id` |
| `GET` | `/documents` | List, with review counts |
| `GET` | `/documents/{id}` | Status and metadata |
| `GET` | `/documents/{id}/extraction` | Structured result + findings |
| `GET` | `/documents/{id}/trace` | Per-step execution trace |
| `GET` | `/metrics` | Cost and latency |
| `GET` | `/health` | Liveness probe |

Status codes are deliberate: **404** means no such document, **409** means "not
ready yet" or "failed" — so a polling client knows whether to retry or stop.
**413** is returned for oversize uploads rather than a generic 400.

### Why uploads are asynchronous

Extraction takes several seconds. Holding an HTTP connection open that long is
fragile — proxies and client timeouts interfere. `POST /documents` returns
**202 Accepted** immediately and the client polls, which is the conventional
shape for long-running work and usable from a browser, a script or a queue.

## Real output

```json
{
  "vendor": "ACME SUPPLIES LTD",
  "invoice_number": "INV-10932",
  "date": "2026-09-10",
  "currency": "USD",
  "subtotal": 1200.0,
  "tax": 192.0,
  "total": 1392.0,
  "items": [
    {"description": "Steel brackets (type A)", "quantity": 40, "unit_price": 12.5, "amount": 500.0},
    {"description": "Mounting plates",         "quantity": 25, "unit_price": 18.0, "amount": 450.0},
    {"description": "Delivery handling",       "quantity": 1,  "unit_price": 250.0, "amount": 250.0}
  ]
}
```

---

## The core idea: the model reads, the code checks

An LLM reading an invoice is doing transcription, and it is good at it. What it
**cannot** reliably do is notice that its own output does not add up — a missed
row, a misread digit and a hallucinated line all look equally plausible to the
model that produced them.

So every extraction is checked with arithmetic:

| Check | Severity | Catches |
|---|---|---|
| `items_sum` | error | line items ≠ subtotal |
| `total_arithmetic` | error | subtotal + tax + shipping − discount ≠ total |
| `document_type` | error | a CV extracted as an invoice |
| `required_fields` | error/warning | missing total, vendor, number or date |
| `line_item_maths` | warning | quantity × unit price ≠ line amount |
| `tax_rate` | warning | tax > 40% of subtotal |
| `negative_total` | warning | negative total that is not a credit note |
| `currency` | warning | currency could not be determined |
| `dates` | warning | unparseable, far-future, or due-before-issue |
| `low_confidence` | warning | model reported < 0.6 |
| `no_line_items` | warning | table was probably not read |

Escalate-only, as in the support platform: any error rejects, any warning
requires review, and nothing can downgrade a status once raised.

**Findings never mutate the extraction.** A wrong total is reported, never
silently corrected — turning a visible discrepancy into an invisible one is the
worst thing a financial tool can do.

### It works — verified live

An invoice with a deliberately altered line (rows sum to 1150, subtotal printed
as 1200):

```
type=invoice vendor=ACME SUPPLIES LTD total=1392.0 items_sum=1150.0
REVIEW: rejected
  [error]   Line items sum to 1150.00 but subtotal is 1200.00
  [warning] quantity x unit price does not match the line amount — row 2
```

The model extracted it confidently and without complaint. **Arithmetic caught
what the model could not.**

And a CV uploaded as an invoice:

```
type=other vendor=Jane Doe total=None
REVIEW: rejected
  [error] This does not look like an invoice — extracted fields are unreliable
  [error] Missing required field(s): invoice_number, date, total
```

## Parsing

Format is detected from **magic bytes, not the filename** — an uploader can call
a PNG `invoice.pdf`, and a test covers exactly that.

| Input | Handling |
|---|---|
| PDF (text layer) | `pypdf`, page-capped |
| PDF (scanned) | **rejected** with `no_text_layer` unless OCR is installed |
| DOCX | paragraphs **and tables** — invoice totals live in tables |
| Image | OCR via tesseract, flagged as lossy |
| Text | decoded with encoding fallbacks |
| Password-protected PDF | empty-password unlock attempted, then reported |

A scanned PDF produces almost no text. Reporting that plainly is far better than
handing the model an empty string and letting it invent an invoice.

Long documents are truncated **head + tail**, keeping the first 60% and last
35%. Invoice totals sit at the *end*, so dropping the tail would defeat the
purpose. There is a test for this.

### OCR

Free and open source — [tesseract](https://github.com/tesseract-ocr/tesseract),
no API key. It needs the **binary** as well as the Python package:

```bash
brew install tesseract tesseract-lang    # macOS (lang = 162 language packs)
apt install tesseract-ocr tesseract-ocr-ara
pip install pytesseract
```

Without the binary the code degrades gracefully: images are rejected with an
explanatory message rather than returning empty text.

#### Languages must be declared

`DI_OCR_LANGUAGES` defaults to `eng+ara`. This matters more than it sounds:
**tesseract does not detect script — it applies the models it is told to.**

Given only `eng`, an Arabic invoice came back like this:

```
'JI6 Jus JJes sole\nlug 76\nade |Sle9 96: INV-99120...'
```

217 characters, `ok=True`, and complete nonsense. Tesseract mapped Arabic script
onto the Latin alphabet and reported success. The extractor would have built an
invoice out of it.

With `ara+eng` the same image reads correctly, including the Latin invoice
number embedded in Arabic text:

```
vendor: تاديروتلل رونل | number: INV-99120 | date: 2026-09-15 | currency: EGP
```

Check what you have with `tesseract --list-langs`.

#### Confidence gating

Output below `DI_OCR_MIN_CONFIDENCE` (default 55%) is rejected outright.
Tesseract reports a per-word confidence, and it separates the cases cleanly:

| Case | Mean confidence |
|---|---|
| Arabic image, `eng` pack | **40%** → rejected |
| Arabic image, `ara+eng` pack | 75% → accepted |
| English image, `eng` pack | 87% → accepted |

> An earlier attempt guessed at quality by counting vowels and odd
> capitalisation. It scored the gibberish **100%** — tesseract's garbage is
> built from real letters, so "does this look like words?" is a bad question.
> The confidence tesseract already computes is a measurement rather than a
> guess.

**OCR output is always flagged for review**, and this is not caution for its own
sake. On a clean, synthetic 900×920 invoice image — not a blurry phone photo —
tesseract silently dropped the invoice number, the date and the subtotal line:

```
review: needs_review
vendor: NORTHGATE SUPPLIES INC | total: 1296.0 | items: 3
  [warning] Missing required field(s): invoice_number, date
  [warning] Text came from OCR, which silently drops characters and whole lines
```

The model reported `confidence: 1.0`, because it read the text it was given
perfectly. The loss happened one layer earlier — which is exactly why the flag
lives in `parsing.py` rather than in the prompt. After OCR, "the field is
absent" and "the scanner lost it" are indistinguishable downstream, so a human
should always glance at the original.

## Normalisation

Invoices write the same number many ways. All of these are repaired before
validation rather than costing a retry:

| Input | Becomes |
|---|---|
| `"$1,392.00"` | `1392.0` |
| `"1.392,00"` (European) | `1392.0` |
| `"(150.00)"` (accounting) | `-150.0` |
| `"10/09/2026"`, `"Sep 10, 2026"` | `"2026-09-10"` |
| `"$"`, `"1,392.00 USD"` | `Currency.USD` |
| `{"Widget": 100}` | `[{description, amount}]` |

What is **not** repaired is arithmetic. A total that does not match is a
finding, not something to quietly fix.

## Reuse from the support platform

Roughly 70% of the architecture transferred:

| Module | Status |
|---|---|
| `textproc.py`, `telemetry.py`, `trace.py` | **copied unchanged** |
| `config.py`, `storage.py`, `llm.py` | same shape, renamed fields |
| `parsing.py` | new — documents arrive as bytes, not text |
| `schemas.py`, `validation.py` | new domain |

The reliability machinery — constrained decoding with a client-side fallback,
repair driven by the actual validation error, per-attempt metrics, thread-local
buffering — is a property of talking to an LLM, not of support tickets. That is
why it ported without modification.

## Testing

55 tests, all offline — no model server, no network.

```
Ran 55 tests in 0.052s
OK
```

The validation suite is the important one: it asserts arithmetic that must hold
regardless of model confidence, including that a broken check cannot break
validation and that findings never mutate the extraction.

### A bug the tests caught

`"wibble"` was classified as **EGP**. The currency matcher fell back to
substring search over its synonym table, and `"le"` (an Egyptian pound
abbreviation) appears inside `"wibble"`. Substring matching is now restricted to
non-alphanumeric symbols, where it is actually needed (`"$1,392.00"`).

Worth noting the failure mode: not a crash, just a confidently wrong currency on
a financial document. Exactly what this project exists to prevent.

## Configuration

Environment-driven via `DI_*` variables or a `.env` file:

`DI_API_BASE`, `DI_MODEL`, `DI_MAX_TOKENS`, `DI_TEMPERATURE`,
`DI_ENABLE_THINKING`, `DI_USE_STRUCTURED_OUTPUT`, `DI_MAX_REPAIR_ATTEMPTS`,
`DI_MAX_FILE_BYTES`, `DI_MAX_PAGES`, `DI_MAX_TEXT_CHARS`,
`DI_AMOUNT_TOLERANCE`, `DI_DB_PATH`.

`DI_TEMPERATURE` defaults to `0.0` — extraction is transcription, and the same
invoice should yield the same numbers every time.

## Known limitations

- **OCR is lossy.** Working, but every OCR'd document is flagged
  `needs_review` — tesseract drops fields even on clean images.
- **Single worker.** The local model is the bottleneck; concurrent generations
  make all of them slower. Raise `max_workers` for a hosted API.
- **Originals are not stored.** Only metadata and the extraction are persisted,
  so a document cannot be re-processed after a prompt or parser improvement,
  and a disputed result cannot be audited against the source. Production would
  put the file in object storage and keep a key.
- **SQLite and in-memory traces.** Fine for one process; a real deployment wants
  Postgres and a durable queue.
- **No authentication.** Anyone who can reach the API can upload and read any
  document. A multi-tenant deployment needs per-tenant scoping — the same
  lesson the support platform learned about tool authorisation.
- **Invoice-specific.** The pipeline is generic; `schemas.py` and
  `validation.py` are not. Swapping those two gives receipts, contracts or
  purchase orders.
