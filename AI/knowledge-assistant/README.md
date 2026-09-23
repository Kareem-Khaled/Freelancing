# Enterprise Knowledge Assistant (RAG)

Answers questions from *your* documents, with citations you can verify — and a
refusal when the documents do not contain the answer.

```
DOCUMENTS  (PDF / DOCX / TXT / images)
    ↓
extraction        detect by content, OCR when needed
    ↓
chunks            heading-aware, overlapping
    ↓
embeddings        pluggable: server → sentence-transformers → hashing
    ↓
vector database   SQLite + NumPy, alongside a BM25 lexical index
    ↓
retrieval         reciprocal rank fusion + an absolute relevance gate
    ↓
relevant context  numbered passages, so citations can be checked
    ↓
LLM
    ↓
answer + citations   every [n] verified against what was actually retrieved
```

## Quick start

```bash
cd knowledge-assistant
pip install -r requirements.txt
./start.sh
```

- **UI** — <http://127.0.0.1:8950>
- **API docs** — <http://127.0.0.1:8950/docs>

Click **Load samples** to index the four policy documents in `corpus/`, then ask
something. Or use the API:

```bash
curl -X POST http://127.0.0.1:8950/documents -F "file=@corpus/refund_policy.txt"

curl -X POST http://127.0.0.1:8950/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the refund policy for enterprise customers?"}'
```

```bash
./test.sh     # 49 tests, offline, no model server needed
```

## Real output

```
Q: What is the refund policy for enterprise customers?
   grounded=True  2.4s
   A: Enterprise customers may request a refund within 30 days of the invoice
      date [1]. Any refunds exceeding $10,000 require written approval from the
      Finance Director [1].
      [1] refund_policy.txt — 3. Enterprise Plans

Q: What is the capital of France?
   refused=True  0.0s
   A: I could not find this in the available documents.
```

Note the second one took **0.0s** — the model was never called. That is the
point.

## API

| Method | Route | Purpose |
|---|---|---|
| `POST` | `/documents` | upload and index |
| `GET` | `/documents` | list, with embedder info |
| `GET` | `/documents/{id}/chunks` | inspect what retrieval searches |
| `DELETE` | `/documents/{id}` | remove from the index |
| `POST` | `/ask` | answer with citations |
| `GET` | `/queries` | recent questions |
| `GET` | `/traces/{key}` | step-by-step execution trace |
| `GET` | `/metrics` | cost, latency, index size |

Uploads are synchronous, unlike the document-intelligence service: indexing is
parse + chunk + embed with no model call, so a four-page policy indexes in ~10ms.

---

## The core guarantee: grounded or refused

The product promise is *answers from these documents, not from the model's
general knowledge*. Two mechanisms enforce it, and **neither is the prompt**:

### 1. Refusal happens before the model is called

If retrieval finds nothing above the relevance threshold, the model is never
invoked. It cannot answer from memory if it is not asked. A test asserts the
call count is zero.

### 2. Citations are verified after generation

Every `[n]` marker in the answer is resolved against the passages actually
supplied. A marker outside that range is a fabrication:

```
model says:  "Enterprise refunds take 30 days [99]."
we gave it:  6 passages
result:      grounded=False, warning: cited passage 99 that was not retrieved
```

An answer with no citations at all is also flagged — it cannot be traced to a
source, so it is not presented as grounded.

Asking a model to "only use the context" is a request. Checking which sources it
cited is a measurement.

## Retrieval

Two retrievers, because they fail in opposite directions:

| | Good at | Bad at |
|---|---|---|
| **Dense vectors** | meaning, paraphrase | exact tokens ("Section 4.2", "INV-10932") |
| **BM25** | exact terms, rare words | synonyms ("money back" vs "refund") |

Merged with **Reciprocal Rank Fusion** rather than by adding scores: cosine
similarity sits in roughly [0, 1] while BM25 is unbounded, so summing them would
let BM25 silently dominate. RRF uses only the *position* in each ranking.

### The gate RRF cannot provide

RRF is scale-free by design, which is also its blind spot: it ranks but does not
measure. Measured on this corpus, an off-topic question produced fused scores
*indistinguishable* from a good match:

```
"refund policy for enterprise customers"  -> 0.0164
"What is the capital of France?"          -> 0.0163
```

So a second, absolute signal is applied — the share of the question's content
words that appear in the chunk:

| Question | Coverage | Outcome |
|---|---|---|
| "capital of France" | 0% | refused |
| "who won the world cup" | 0% | refused |
| "refund if I was charged twice" | 25% | answered |
| "tell me about MFA" | 33% | answered |

`KA_MIN_COVERAGE` defaults to 0.20, which sits in the gap.

## Embeddings, and an honest limitation

This machine's llama.cpp server returns:

```
501 "This server does not support embeddings. Start it with --embeddings"
```

So the embedder is an interface with a fallback chain — server →
sentence-transformers → **hashing** — and the live backend is reported in the
UI and at startup:

```
! embeddings: hashing (lexical only — synonyms will not match)
!   for semantic search: pip install sentence-transformers
```

The hashing embedder is TF-IDF-weighted character n-grams: robust to typos and
morphology, zero dependencies, deterministic. But it is **lexical**, not
semantic — "how do I get my money back" will not match "refund policy" unless
they share substrings.

Saying so plainly matters. A system that silently degraded to keyword matching
while calling itself semantic search would be lying to its users. For real
semantic retrieval:

```bash
pip install sentence-transformers    # ~2GB with PyTorch
```

Vectors from different embedders are not comparable, so re-index afterwards
(`pipeline.reindex_all()`). `search_dense` refuses to mix dimensions rather than
returning confident nonsense.

## Chunking

Chunking decides what retrieval can possibly find:

- **Too large** → the answer is buried, the embedding averages to something vague
- **Too small** → "Customers may request a refund within 30 days" is separated
  from the heading "Enterprise Plans" that gives it meaning

So it splits on structure first — blank lines and headings — and falls back to
sentence-boundary cuts only for genuinely oversized blocks. Each chunk carries
its heading, which does double duty: more matchable text for the retriever, and
a citation that means something to the reader.

## Bugs found while building

**1. Single-word headings were missed.** `Receipts` and `Travel` are extremely
common section titles, but the heading detector required two or more words.
`expense_policy.txt` collapsed into **one chunk**, which then lost to shorter
chunks under BM25 length normalisation — so the expense question retrieved the
*security* policy.

**2. Stopwords made every question match.** "What is the capital of France?"
scored against any chunk containing "is" or "the". Stopwords are now dropped
from queries (but kept in the index, where they cost nothing).

**3. The stemmer over-stemmed.** A first attempt turned `expenses` into
`expen`, which matches nothing. Now conservative: strip at most one suffix,
never leave a stem under three characters. `expenses`→`expense`,
`submitted`→`submit`, but `access` and `business` are untouched.

**4. Short sections vanished.** `min_chunk_chars=80` silently dropped
`Receipts / Keep every receipt above $25` — a complete, answerable fact. Chunks
below the minimum are now kept when they have a heading.

All four are covered by regression tests.

## Reuse from the earlier projects

| Module | Status |
|---|---|
| `parsing.py`, `textproc.py`, `telemetry.py`, `trace.py`, `style.css` | **copied unchanged** |
| `config.py`, `pipeline.py`, `api.py` | same shape, new domain |
| `chunking.py`, `embeddings.py`, `store.py`, `retrieval.py`, `answering.py` | new |

The parsing layer arrived complete with PDF/DOCX/OCR handling, magic-byte format
detection and the OCR confidence gate — none of which had to be rewritten.

## Configuration

`KA_*` environment variables or a `.env` file:

`KA_API_BASE`, `KA_MODEL`, `KA_TEMPERATURE`, `KA_EMBEDDING_BACKEND`,
`KA_CHUNK_SIZE`, `KA_CHUNK_OVERLAP`, `KA_TOP_K`, `KA_DENSE_WEIGHT`,
`KA_MIN_COVERAGE`, `KA_MAX_CONTEXT_CHARS`, `KA_OCR_LANGUAGES`, `KA_DB_PATH`.

## Known limitations

- **Lexical embeddings by default.** See above. Install
  `sentence-transformers` for semantic retrieval.
- **Brute-force vector search.** Fine to ~100k chunks; beyond that use a real
  ANN index. The store is written so only `store.py` changes.
- **No authentication.** Anyone who can reach the API can read every document.
  A multi-tenant deployment needs per-tenant scoping.
- **No re-ranking.** A cross-encoder over the top ~20 candidates is the usual
  next quality step.
- **Originals are not stored** — only extracted text and chunks, so a document
  cannot be re-processed after a chunking improvement without re-uploading.
- **SQLite and in-memory traces.** Fine for one process; production wants
  Postgres (with `pgvector`) and a durable queue.
