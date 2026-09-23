#!/usr/bin/env python3
"""Run the RAG evaluation question set and write a Markdown report.

Deliberately runs the system exactly as a user would -- through the HTTP API,
with no access to the source documents -- so the report reflects what the
assistant can actually retrieve, including where it fails.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8950"

SECTIONS: list[tuple[str, list[str]]] = [
    ("Level A — direct retrieval", [
        "What are NovaDesk's current business hours for non-P1 support?",
        "What is the Enterprise Plus included monthly API volume for Acme Logistics Group?",
        "What is the current P1 initial response target?",
        "What is the production API path for creating a ticket?",
        "What payment data is a support agent prohibited from sending to a general-purpose LLM?",
    ]),
    ("Level B — multi-document retrieval", [
        "Acme has 2,184,600 API calls in June 2026. How many calls are billable overage, and what overage charge should the signed agreement produce?",
        "For Acme, is a confirmed SLA outage compensated with a cash refund or a service credit? Cite the controlling agreement or policy.",
        "A customer asks to reverse a duplicate charge for USD 700. What approvals or human review are required?",
        "A ticket says: I was charged twice, but one of the charges is still pending. What should support do differently from a confirmed duplicate capture?",
        "What information is missing from a ticket.created event if an AI agent needs the customer's billing history?",
    ]),
    ("Level C — conflict and temporal reasoning", [
        "One document says P1 response is 1 hour and another says 30 minutes. Which should apply today, and why?",
        "The 2025 policy says cash refunds above USD 250 need Finance approval, while the 2026 policy says USD 500. Which threshold should a current support workflow use?",
        "Acme's June report shows a USD 480 service credit. Is that consistent with a 5% Enterprise Plus credit on a USD 4,800 platform fee? Explain any discrepancy.",
        "If Acme asks for a cash refund because of an SLA outage, what should the AI agent tell the customer, and what should it avoid promising?",
        "An AI agent wants to automatically send a reply about a possible security breach. What governance constraints apply?",
    ]),
    ("Level D — reasoning and synthesis", [
        "Which documents are needed to answer why Acme was billed an overage in June, what rate applies, and whether the service credit was calculated correctly?",
        "Given incident INC-2026-041, how should an AI support workflow distinguish a duplicate authorization hold from a confirmed duplicate charge?",
        "A support ticket from Acme is low confidence, requests a USD 900 refund, and mentions possible account takeover. Should the AI respond automatically? Explain using the applicable rules.",
        "In the recommended architecture of validate, retrieve context, call LLM, validate response, apply business rules, persist, notify and escalate, which stages should be deterministic application logic rather than delegated to the LLM?",
        "What is the strongest evidence that the AI system should avoid using the historical 2025 support policy for current SLA answers?",
    ]),
    ("Level E — adversarial and citation quality", [
        "Which two sources could cause a naive RAG system to quote the wrong support policy, and how should metadata or reranking prevent that?",
        "Is the USD 480 service credit in the June report necessarily proof that NovaDesk over-credited Acme? What additional reconciliation evidence would you request?",
        "Can a support agent view a customer's full card number to validate a payment? What does the security handbook say?",
        "A user asks the assistant to cancel an order and issue a USD 900 refund. Which parts require tool calls, which require deterministic business rules, and which require human approval?",
        "Is the USD 480 service credit consistent with the 5% Enterprise Plus credit on the USD 4,800 platform fee? Give the answer, documents used, whether a conflict was detected, the calculation, and the recommended next step.",
    ]),
]


def post(path: str, payload: dict, timeout: int = 180) -> dict:
    request = urllib.request.Request(
        f"{BASE}{path}",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def get(path: str) -> dict:
    with urllib.request.urlopen(f"{BASE}{path}", timeout=30) as response:
        return json.load(response)


def render(number: int, question: str, result: dict) -> str:
    lines = [f"### {number}. {question}", ""]

    if result.get("refused"):
        lines.append("> **No answer returned.** Retrieval found nothing above the")
        lines.append("> relevance threshold, so the model was never called.")
        lines.append("")
    else:
        lines.append(result.get("answer", "").strip())
        lines.append("")

    citations = result.get("citations") or []
    if citations:
        lines.append("**Sources**")
        lines.append("")
        for citation in citations:
            where = citation.get("filename") or citation.get("document_id")
            heading = citation.get("heading") or ""
            suffix = f" — *{heading}*" if heading else ""
            lines.append(f"- `[{citation['marker']}]` **{where}**{suffix}")
        lines.append("")

    retrieval = result.get("retrieval") or {}
    chunks = retrieval.get("chunks") or []
    if chunks:
        names = []
        for chunk in chunks:
            name = chunk.get("filename") or chunk.get("document_id")
            if name not in names:
                names.append(name)
        lines.append(f"<sub>Retrieved {len(chunks)} passage(s) from: {', '.join(names)}</sub>")
        lines.append("")

    warnings = result.get("warnings") or []
    grounded = result.get("grounded")
    flags = []
    if grounded:
        flags.append("grounded")
    elif not result.get("refused"):
        flags.append("**unverified**")
    if result.get("refused"):
        flags.append("refused")
    flags.append(f"{result.get('latency_ms', 0) / 1000:.1f}s")
    lines.append(f"<sub>Status: {' · '.join(flags)}</sub>")
    lines.append("")

    for warning in warnings:
        lines.append(f"> ⚠️ {warning}")
        lines.append("")

    return "\n".join(lines)


def main() -> int:
    try:
        docs = get("/documents")
        meta = get("/metrics")
    except urllib.error.URLError as exc:
        print(f"cannot reach {BASE}: {exc}", file=sys.stderr)
        return 1

    embedder = docs["embedder"]
    out: list[str] = [
        "# RAG Evaluation — Results",
        "",
        f"Generated {datetime.now().strftime('%Y-%m-%d %H:%M')} by the Enterprise "
        "Knowledge Assistant.",
        "",
        "Every answer below was produced through the HTTP API with no access to the",
        "source documents beyond what retrieval returned. Answers are unedited.",
        "",
        "## Setup",
        "",
        f"- **Corpus**: {len(docs['documents'])} documents, {docs['total_chunks']} chunks",
        f"- **Model**: `{meta['model']}`",
        f"- **Embeddings**: `{embedder['backend']}` ({embedder['dims']}d, "
        f"{'semantic' if embedder['semantic'] else '**lexical only**'})",
        f"- **Retrieval**: hybrid BM25 + vector, RRF fusion, top-k "
        f"{meta['retrieval']['top_k']}, coverage gate "
        f"{meta['retrieval']['min_coverage']}",
        "",
    ]

    if not embedder["semantic"]:
        out += [
            "> **Caveat that affects these results.** The model backend does not expose",
            "> an embeddings endpoint, so the assistant fell back to a lexical embedder.",
            "> Retrieval matches wording, not meaning — a question phrased without the",
            "> document's vocabulary may retrieve nothing even when the answer exists.",
            "> Where that happens below, it is a retrieval limitation, not a corpus gap.",
            "",
        ]

    out += ["---", ""]

    stats = {"total": 0, "grounded": 0, "refused": 0, "unverified": 0}
    number = 0

    for title, questions in SECTIONS:
        out += [f"## {title}", ""]
        for question in questions:
            number += 1
            stats["total"] += 1
            print(f"  {number:2d}. {question[:70]}...", flush=True)
            started = time.time()
            try:
                result = post("/ask", {"question": question})
            except Exception as exc:  # noqa: BLE001
                result = {
                    "answer": f"_Request failed: {type(exc).__name__}: {exc}_",
                    "refused": False,
                    "grounded": False,
                    "latency_ms": (time.time() - started) * 1000,
                }
            if result.get("refused"):
                stats["refused"] += 1
            elif result.get("grounded"):
                stats["grounded"] += 1
            else:
                stats["unverified"] += 1
            out.append(render(number, question, result))
        out.append("---")
        out.append("")

    out += [
        "## Summary",
        "",
        "| Outcome | Count |",
        "|---|---|",
        f"| Grounded (all citations verified) | {stats['grounded']} |",
        f"| Answered but unverified | {stats['unverified']} |",
        f"| Refused (nothing retrieved) | {stats['refused']} |",
        f"| **Total** | **{stats['total']}** |",
        "",
        "A refusal is not necessarily a failure: for questions whose answer is not in",
        "the corpus, refusing is the correct behaviour. Refusals on questions that",
        "*are* answerable indicate a retrieval gap — with a lexical embedder, usually",
        "a vocabulary mismatch between the question and the document.",
        "",
    ]

    report = "\n".join(out)
    with open("RAG_EVALUATION_RESULTS.md", "w") as handle:
        handle.write(report)

    print()
    print(f"grounded={stats['grounded']} unverified={stats['unverified']} "
          f"refused={stats['refused']} of {stats['total']}")
    print("written: RAG_EVALUATION_RESULTS.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
