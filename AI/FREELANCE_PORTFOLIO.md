# Freelance Portfolio — Copy-Paste Assets

Everything below is drawn from the three projects in this workspace. Every number
is measured, not estimated. Sources are noted so you can defend any claim in a
client call.

**Verified inventory:**

| Project | Tests | What it is |
| --- | --- | --- |
| `knowledge-assistant` | 51 | RAG Q&A over documents, with verified citations |
| `doc-intelligence` | 67 | Invoice → structured JSON, with arithmetic validation |
| `support-platform` | 165 | Ticket triage with tool lookups + business rules |
| **Total** | **283** | all offline, no network, no API keys |

---

# 1. Upwork profile title

Pick one. Avoid the word "RAG" in the title — per market research, clients don't
search for it.

- `AI Engineer — Chatbots That Answer From YOUR Documents (With Citations)`
- `RAG & Document AI Engineer | Python, FastAPI, LLM | Cited, Verifiable Answers`
- `AI Document Automation — PDF/OCR Extraction, Knowledge Assistants, Ticket Triage`

---

# 2. Upwork overview

> **Most AI chatbots will confidently make things up. Mine refuse.**
>
> I build document AI systems where every answer is traceable to a specific
> passage in a specific file — and where the honest answer "I could not find this
> in the available documents" is a feature, not a failure.
>
> **Recent build — Enterprise Knowledge Assistant (RAG)**
> A grounded Q&A service over a 10-document corporate corpus (policies, SLAs,
> contracts, incident reports, an API manual).
>
> - **25/25** benchmark questions answered with verified citations
> - **0** fabricated citations — every `[1]` marker is resolved against the
>   passages actually retrieved; an invented reference is flagged, not rendered
> - Off-topic questions are **refused before the model is ever called**
> - Correctly resolved planted traps: conflicting SLA targets across a current
>   and a *superseded* policy, and a deliberate arithmetic discrepancy in a
>   billing report
>
> **How I work**
> - Hybrid retrieval — semantic vectors *and* BM25 keyword search, rank-fused.
>   Vectors catch "how do I get my money back" → refund policy; BM25 catches
>   exact IDs like `INC-2026-041` that embeddings blur away.
> - I benchmark before and after. Switching to semantic embeddings took
>   real-world paraphrase accuracy from **1/8 to 6/8** with off-topic refusals
>   still at 100%. I have the before/after JSON to prove it.
> - **283 automated tests** across my projects, including adversarial cases: a
>   model citing a passage it was never given, a model answering with no
>   citations at all.
>
> **Also built:** invoice extraction with deterministic arithmetic validation
> (does the maths actually add up?) and a support-ticket triage platform with
> read-only tool lookups and escalate-only business rules.
>
> **Stack:** Python, FastAPI, SQLite, OpenAI-compatible APIs, sentence-
> transformers, BM25, Tesseract OCR (English + Arabic), pydantic.
>
> Runs against OpenAI/Anthropic **or fully on-premise** with a local model — my
> benchmark corpus was processed at **$0 API cost**, entirely offline. If your
> documents cannot leave your network, that is a solved problem.
>
> Tell me what your documents are and what questions people ask of them, and
> I'll tell you honestly whether AI is the right tool.

---

# 3. Portfolio piece — Knowledge Assistant

**Title:** `Enterprise Knowledge Assistant — Cited Answers From Your Documents`

**Description:**

> **The problem.** Staff can't find answers buried in policies, contracts and
> manuals. A generic chatbot makes things up, and nobody can tell when.
>
> **What I built.** A RAG service that ingests PDF/DOCX/TXT/images (OCR when
> needed), indexes them, and answers questions using only what it retrieves —
> with a numbered citation behind every claim.
>
> **Measured results on a 10-document, 55-chunk corpus:**
>
> | | Result |
> | --- | --- |
> | Benchmark questions answered & grounded | 25 / 25 |
> | Fabricated citations | 0 |
> | Off-topic questions correctly refused | 100% |
> | Real-world paraphrase accuracy | 1/8 → 6/8 after retrieval rework |
>
> **Three things that make it trustworthy:**
>
> 1. **Citations are verified, not trusted.** The model is told to cite `[1]`,
>    `[2]`. After generation, every marker is resolved against the passages
>    actually supplied. `[99]` when six were given is a fabrication — caught and
>    reported. *Asking a model to "only use the context" is a request. Checking
>    which sources it cited is a measurement.*
> 2. **Refusal happens before the model runs.** If retrieval finds nothing
>    relevant, the LLM is never invoked. It cannot answer from memory if it is
>    never asked.
> 3. **It handled the hard cases.** The corpus contained a superseded 2025
>    policy contradicting the 2026 one. The system chose correctly and explained
>    why — quoting the "do not apply its thresholds" clause.
>
> **Honest limitation I document publicly:** one question still returns a wrong
> API path, because that PDF's table extracts misaligned — headings pair with
> the next row's values. It's a table-parsing problem, not a retrieval one, and
> I chose to document it rather than tune thresholds until the metric looked
> good.
>
> **Stack:** Python · FastAPI · SQLite · sentence-transformers (MiniLM) · BM25 ·
> Reciprocal Rank Fusion · Tesseract OCR (eng+ara) · 51 automated tests

**Screenshots to attach:** the web UI mid-answer with citations expanded; the
live trace timeline; the `RETRIEVAL_COMPARISON.md` before/after table.

---

# 4. Portfolio piece — Invoice Extraction

**Title:** `Invoice Data Extraction With Arithmetic Validation`

> Turns PDF, DOCX, image or text invoices into validated structured data —
> vendor, invoice number, date, currency, totals, line items.
>
> **The part most extractors skip:** after the LLM returns JSON, deterministic
> code checks whether the numbers *actually add up*. Line items vs subtotal,
> tax, total. A mismatch routes the document to `needs_review` instead of
> silently entering your accounts.
>
> - Format detected by **magic bytes, not filename** — `invoice.pdf` may be a
>   renamed PNG
> - Scanned PDFs detected and OCR'd, with a confidence gate that rejects
>   gibberish rather than passing it downstream
> - Failed extractions retry with the **exact validation error** fed back
> - Outcome: `auto_approved` / `needs_review` / `rejected`, with findings
>
> **67 automated tests.** Stack: Python · FastAPI · pydantic · Tesseract OCR

---

# 5. Portfolio piece — Support Ticket Triage

**Title:** `AI Support Triage With Business Rules That Can't Be Overridden`

> Converts free-text tickets into structured triage: category, priority,
> sentiment, entities, suggested action, draft response.
>
> **Why it's safe to deploy:** the LLM proposes, deterministic business rules
> dispose. Rules are **escalate-only** — they can raise a priority or force
> human review, never lower it. An over-confident model cannot downgrade a P1.
>
> - Read-only tool lookups: customer records, orders, payments, refund policy
> - Verifies duplicate-charge claims against actual billing records before any
>   refund is suggested
> - Input guards for empty, oversized, malformed and unsupported-language input
>
> **165 automated tests.** Stack: Python · pydantic · OpenAI-compatible LLM

---

# 6. Fiverr gigs

### Gig 1 — the main one

**Title:** `I will build an AI chatbot that answers from your PDFs with real citations`

| Tier | Name | Delivery | Scope |
| --- | --- | --- | --- |
| Basic | Proof of Concept | 3 days | Up to 20 documents, web UI, cited answers, runs locally |
| Standard | Production Assistant | 7 days | Up to 200 docs, OCR for scans, hybrid search, REST API, accuracy report |
| Premium | Deployed + Benchmarked | 14 days | Unlimited docs, deployed to your infra or on-premise, custom benchmark on YOUR questions, test suite, handover docs |

**Description:**

> Your team wastes hours hunting through policies, contracts and manuals. A
> normal chatbot invents answers, which is worse than none.
>
> I build assistants that cite their sources — every claim links to the exact
> passage in the exact file — and that **say "I don't know" when your documents
> don't cover it.**
>
> On my benchmark corpus: 25/25 questions answered with verified citations, zero
> fabricated references, and 100% of off-topic questions correctly refused.
>
> Works with PDF, Word, text and scanned images (OCR, English + Arabic). Can run
> **fully on your own servers** — no document ever leaves your network, no
> per-question API bill.
>
> Message me with your document types and 3 example questions. I'll tell you
> straight whether this will work for your case.

### Gig 2

`I will extract invoice and document data to structured JSON or Excel` — lead
with the arithmetic validation; it's the differentiator.

### Gig 3

`I will audit and fix your existing RAG chatbot that gives wrong answers`

> Great for buyers burned by a previous developer. Deliverable: a benchmark of
> the current system, a diagnosis, and a fix. This is literally what I did on my
> own build — took paraphrase accuracy from 1/8 to 6/8 by finding that two
> relevance filters were silently discarding correct semantic matches.

---

# 7. Proposal template

> Hi [Name],
>
> You mentioned [their exact problem]. The part I'd focus on first is making
> sure it never invents an answer — that's usually what sinks these projects.
>
> I recently built a knowledge assistant over corporate policy documents. Two
> results that are relevant to you:
>
> - Every answer carries a citation that is **verified after generation** — if
>   the model references a passage it wasn't given, that's caught and flagged
>   rather than shown to the user. Zero fabricated citations across the
>   benchmark.
> - The corpus deliberately contained a superseded policy contradicting the
>   current one. The system picked the right one and explained why.
>
> For [their project] I'd suggest:
> 1. You send 10–20 representative documents and 10 real questions
> 2. I build a working prototype and **run your questions against it**
> 3. You see the actual accuracy before committing to the full build
>
> That way you're judging measured results, not promises.
>
> One question: are your documents mostly text-based PDFs, or scans? It changes
> the approach — scans need OCR and the accuracy ceiling is lower.
>
> [Your name]

**Why this works, given the research:** Signal 1 says clients have been burned
by devs who over-promise — so lead with evidence and offer a checkpoint. Signal 2
says they distrust ungrounded AI — so lead with verification. The closing
question proves you understand a real technical constraint.

---

# 8. Before you publish

1. **Record a 60–90s screen capture** of the app: upload a PDF → ask a question →
   expand the citation → ask something off-topic → show it refuse. That refusal
   moment is your strongest selling point. Fiverr gigs with video convert
   noticeably better.
2. **Sanitise the corpus.** The benchmark documents are synthetic (NovaDesk /
   Acme) — confirm nothing real leaks into screenshots.
3. **Push to GitHub** with the README, `RAG_EVALUATION_RESULTS.md` and
   `RETRIEVAL_COMPARISON.md`. That comparison doc — documenting a failure and
   the fix — is more persuasive to a technical buyer than any polished claim.
4. **Start below your target rate** for the first 3–5 jobs to buy reviews, then
   raise. Unavoidable on both platforms.

---

## Two claims to state carefully

- **"25/25"** means *correctly cited*, not *100% factually correct* — one answer
  is wrong because of a PDF table extraction issue. Say "25/25 grounded with
  verified citations", and mention the table limitation if pressed. It builds
  more trust than it costs.
- **"1/8 → 6/8"** varies 5–6 between runs because the answering model is
  generative. Say "from 1/8 to 5–6 out of 8". Retrieval is deterministic; the
  LLM is not.
