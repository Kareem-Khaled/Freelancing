# Lexical vs Semantic Retrieval — Measured Comparison

Both runs use the identical corpus (10 documents, 55 chunks), the identical
questions and the identical answering model. Only the embedder and the
retrieval gate changed.

## Why this benchmark exists

The 25-question benchmark scored 25/25 — but those questions borrowed the
corpus's own vocabulary. That flatters a lexical retriever, because matching
words is exactly what it does. This benchmark asks **the same eight questions
twice**: once in corpus wording, once in the words an employee would actually
use. The gap between the two columns is the honest measure of retrieval quality.

Two off-topic questions act as a control. A system that improves recall by
simply lowering its standards will start answering these, so they must keep
being refused.

## Results

| Metric | Lexical (hashing) | Semantic (MiniLM) |
| --- | --- | --- |
| Corpus wording answered | 8/8 | 8/8 |
| **Natural wording answered** | **1/8** | **5–6/8** |
| Off-topic refused | 2/2 | 2/2 |
| Full 25-question benchmark | 25/25 grounded | 25/25 grounded |

The lexical embedder answered only one paraphrase out of eight. It was not
"95% accurate" — it was accurate on questions phrased like the documents, which
is not how anybody asks.

Natural wording varies between 5 and 6 across runs because the answering model
is generative; the retrieval stage is deterministic.

## What had to change beyond installing a better embedder

Swapping the embedder alone changed nothing: the score stayed at 1/8. Two gates
downstream were silently lexical, and both discarded the semantic hits before
they reached the model.

1. **The fused `min_score` cutoff.** A passage found by vectors alone ranks
   third at best, contributing `0.5 / (60 + 3) ≈ 0.0079` under reciprocal rank
   fusion — below the `0.01` cutoff. Every vector-only match was dropped before
   anything looked at it.
2. **The lexical coverage gate.** It requires a share of the question's words to
   appear in the passage. A paraphrase sharing no words scores zero by
   definition, which is precisely the case semantic search exists to handle.

Both gates now admit a dense hit that is *clearly* strong, defined as top-10 by
rank and cosine ≥ 0.14. That threshold is not a guess:

| | cosine range |
| --- | --- |
| On-topic paraphrases | 0.14 – 0.44 |
| Off-topic questions | 0.06 – 0.11 |

The threshold sits in the gap, which is why off-topic refusals survived the
change. The rank cap stops one lucky tail match from leaking through.

## Chunking defects found while investigating

Reading the retrieved passages — rather than only the scores — exposed two bugs
that no score would have revealed:

- **Currency lines became headings.** `USD 650` is all-uppercase, so the
  ALL CAPS heading rule promoted a price to a section title, producing chunks
  headed `USD 650` whose body was `500,000 USD 0.007/call`. Heading detection
  now rejects lines that are mostly digits.
- **Overlap cut words in half.** Carrying the tail by raw character count
  produced a chunk beginning `esk customers…`, having lost `NovaD` from
  `NovaDesk`. The overlap now advances to a word boundary.

Both are covered by regression tests.

## Known remaining limitation

`05_novadesk_pro_product_manual_v4_2.pdf` contains an API reference table whose
rows are misaligned by text extraction: the heading `POST` is paired with the
*next* row's path, so `POST /v2/tickets → Create ticket` is scrambled across
chunks. This is why "How do I file a new issue programmatically?" still fails.

This is a PDF table-extraction problem, not a retrieval one, and the honest fix
is layout-aware table parsing rather than tuning thresholds until the number
looks better.

## Reproducing

```bash
./start.sh                      # serves on http://127.0.0.1:8950
python3 paraphrase_test.py semantic
python3 run_evaluation.py
```

Tuning knobs (`KA_`-prefixed env vars or `.env`):

```bash
KA_EMBEDDING_BACKEND=sentence     # auto | server | sentence | hashing
KA_MIN_SEMANTIC_SCORE=0.14        # cosine required to bypass the lexical gate
KA_SEMANTIC_OVERRIDE_MAX_RANK=10  # how deep in the dense ranking to allow it
```

Set `KA_EMBEDDING_BACKEND=hashing` and re-ingest to reproduce the lexical
baseline.
