#!/usr/bin/env python3
"""Compare lexical and semantic retrieval on paraphrased questions.

The 25-question benchmark scored 25/25 with a lexical embedder -- but those
questions used the corpus's own vocabulary. This asks the SAME questions in the
words an employee would actually use, which is where lexical matching is
expected to fail.

Run once before switching embedders and once after; the script writes its
results to a JSON file so the two runs can be compared.
"""

from __future__ import annotations

import json
import sys
import urllib.request

BASE = "http://127.0.0.1:8950"

# (corpus wording, natural wording) -- both ask the same thing.
PAIRS: list[tuple[str, str]] = [
    ("What is the current P1 initial response target?",
     "How fast do you reply to emergencies?"),
    ("What payment data is prohibited from being sent to a general-purpose LLM?",
     "Can I paste a customer's credit card into ChatGPT?"),
    ("What are NovaDesk's current business hours for non-P1 support?",
     "When can I reach someone on the phone?"),
    ("Is an SLA outage compensated with a cash refund or a service credit?",
     "If you go down, do I get my money back?"),
    ("What is the Enterprise Plus included monthly API volume?",
     "How many requests can we make before extra charges kick in?"),
    ("What approvals are required to reverse a duplicate charge?",
     "Who has to sign off before we give someone their money back?"),
    ("How should an AI agent handle a possible security breach reply?",
     "Can the bot answer on its own if someone got hacked?"),
    ("What is the production API path for creating a ticket?",
     "How do I file a new issue programmatically?"),
]

OFF_TOPIC = [
    "What is the capital of France?",
    "How do I bake sourdough bread?",
]


def ask(question: str) -> dict:
    request = urllib.request.Request(
        f"{BASE}/ask",
        data=json.dumps({"question": question}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=180) as response:
        return json.load(response)


def main() -> int:
    label = sys.argv[1] if len(sys.argv) > 1 else "run"

    meta = json.load(urllib.request.urlopen(f"{BASE}/metrics", timeout=30))
    backend = meta["embedder"]["backend"]
    semantic = meta["embedder"]["semantic"]

    print(f"embedder: {backend} (semantic={semantic})")
    print()
    print(f"{'':4}{'corpus wording':<14}{'natural wording':<16}question")
    print("-" * 78)

    results = {"backend": backend, "semantic": semantic, "pairs": [], "off_topic": []}
    natural_ok = 0

    for index, (corpus_q, natural_q) in enumerate(PAIRS, 1):
        a = ask(corpus_q)
        b = ask(natural_q)
        a_ok = not a["refused"]
        b_ok = not b["refused"]
        if b_ok:
            natural_ok += 1
        print("%-4d%-14s%-16s%s" % (
            index,
            "answered" if a_ok else "REFUSED",
            "answered" if b_ok else "REFUSED",
            natural_q[:42],
        ))
        results["pairs"].append({
            "corpus": corpus_q, "natural": natural_q,
            "corpus_answered": a_ok, "natural_answered": b_ok,
        })

    print()
    refused_off_topic = 0
    for question in OFF_TOPIC:
        result = ask(question)
        if result["refused"]:
            refused_off_topic += 1
        print("off-topic  %-9s %s" % (
            "refused" if result["refused"] else "ANSWERED", question[:44]))
        results["off_topic"].append(
            {"question": question, "refused": result["refused"]}
        )

    corpus_ok = sum(1 for p in results["pairs"] if p["corpus_answered"])
    results["corpus_answered"] = corpus_ok
    results["natural_answered"] = natural_ok
    results["off_topic_refused"] = refused_off_topic

    print()
    print(f"corpus wording  : {corpus_ok}/{len(PAIRS)} answered")
    print(f"natural wording : {natural_ok}/{len(PAIRS)} answered")
    print(f"off-topic       : {refused_off_topic}/{len(OFF_TOPIC)} correctly refused")

    path = f"paraphrase_{label}.json"
    with open(path, "w") as handle:
        json.dump(results, handle, indent=2)
    print(f"\nwritten: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
