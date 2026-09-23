"""Tests for answering, citation verification and the full pipeline.

A fake OpenAI client makes every path deterministic, including the ones that
matter most: a model that cites a passage it was never given, and a model that
answers with no citations at all.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from dataclasses import dataclass
from typing import Any

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from knowledge.answering import REFUSAL, Answerer  # noqa: E402
from knowledge.embeddings import HashingEmbedder  # noqa: E402
from knowledge.pipeline import KnowledgePipeline  # noqa: E402
from knowledge.store import VectorStore  # noqa: E402


CORPUS = {
    "refund_policy.txt": b"""ACME CLOUD REFUND POLICY

Standard Plans
Customers on Starter and Pro plans may request a refund within 14 days of the
original purchase date. Refunds go to the original payment method.

Enterprise Plans
Enterprise customers may request a refund within 30 days of the invoice date.
Refunds exceeding $10,000 require written approval from the Finance Director.
""",
    "security_policy.txt": b"""ACME SECURITY POLICY

Password Requirements
Passwords must be at least 14 characters and include mixed case, a number and
a symbol. Passwords expire every 180 days.

Incident Reporting
Report suspected incidents to security@acme.example within one hour.
""",
}


# ----------------------------------------------------------------------
# Fake OpenAI client
# ----------------------------------------------------------------------
@dataclass
class _Usage:
    prompt_tokens: int = 500
    completion_tokens: int = 60
    total_tokens: int = 560


class _Msg:
    def __init__(self, content: str) -> None:
        self.content = content
        self.reasoning_content = None


class _Choice:
    def __init__(self, content: str) -> None:
        self.message = _Msg(content)
        self.finish_reason = "stop"


class _Response:
    def __init__(self, content: str) -> None:
        self.choices = [_Choice(content)]
        self.usage = _Usage()


class FakeCompletions:
    def __init__(self, script: list[Any]) -> None:
        self.script = list(script)
        self.calls: list[list[dict]] = []

    def create(self, **kwargs):
        self.calls.append(kwargs["messages"])
        item = self.script.pop(0) if self.script else "No answer."
        if isinstance(item, Exception):
            raise item
        return _Response(item)


class FakeClient:
    def __init__(self, script: list[Any]) -> None:
        self.chat = type("chat", (), {})()
        self.chat.completions = FakeCompletions(script)


class TinySemanticEmbedder:
    """Deterministic semantic-ish embedder for retrieval gate tests."""

    name = "tiny-semantic"
    dims = 4
    semantic = True

    def fit(self, texts: list[str]) -> None:  # noqa: D401 - interface parity
        """No-op."""

    def embed(self, texts: list[str]) -> np.ndarray:
        matrix = np.zeros((len(texts), self.dims), dtype=np.float32)
        for i, text in enumerate(texts):
            lowered = text.lower()
            if any(k in lowered for k in ("refund", "reimburs", "money back", "claw back")):
                matrix[i, 0] = 1.0
            if any(k in lowered for k in ("password", "security")):
                matrix[i, 1] = 1.0
            if any(k in lowered for k in ("invoice", "billing", "price")):
                matrix[i, 2] = 1.0
            if matrix[i].sum() == 0:
                matrix[i, 3] = 1.0
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return matrix / norms


def make_pipeline(script: list[Any], db_path: str) -> KnowledgePipeline:
    store = VectorStore(db_path)
    answerer = Answerer()
    answerer.client = FakeClient(script)
    pipeline = KnowledgePipeline(
        store=store, embedder=HashingEmbedder(dims=1024), answerer=answerer
    )
    answerer._on_call = pipeline._on_call
    answerer.metrics = pipeline.metrics
    for name, data in CORPUS.items():
        pipeline.ingest(data, filename=name)
    return pipeline


class _PipelineTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()

    def tearDown(self):
        os.unlink(self.tmp.name)


class TestIngestion(_PipelineTest):
    def test_documents_are_indexed(self):
        p = make_pipeline([], self.tmp.name)
        self.assertEqual(len(p.store.list_documents()), 2)
        self.assertGreater(p.store.chunk_count(), 2)

    def test_unreadable_document_fails_cleanly(self):
        p = make_pipeline([], self.tmp.name)
        result = p.ingest(b"%PDF-1.4 not really a pdf", filename="broken.pdf")
        self.assertFalse(result.ok)
        self.assertTrue(result.error)

    def test_empty_document_is_rejected(self):
        p = make_pipeline([], self.tmp.name)
        self.assertFalse(p.ingest(b"", filename="empty.txt").ok)

    def test_deleting_removes_its_chunks(self):
        p = make_pipeline([], self.tmp.name)
        before = p.store.chunk_count()
        doc = p.store.list_documents()[0]
        p.store.delete_document(doc["id"])
        self.assertLess(p.store.chunk_count(), before)


class TestGroundedAnswering(_PipelineTest):
    def test_answer_with_valid_citation(self):
        p = make_pipeline(
            ["Enterprise customers may request a refund within 30 days [1]."],
            self.tmp.name,
        )
        answer = p.ask("What is the refund policy for enterprise customers?")
        self.assertTrue(answer.grounded)
        self.assertFalse(answer.refused)
        self.assertEqual(len(answer.citations), 1)
        self.assertEqual(answer.warnings, [])

    def test_citations_resolve_to_real_passages(self):
        p = make_pipeline(["Refunds take 30 days [1]."], self.tmp.name)
        answer = p.ask("enterprise refund policy")
        citation = answer.citations[0]
        self.assertTrue(citation.filename)
        self.assertIn("refund", citation.text.lower())

    def test_the_model_only_sees_retrieved_passages(self):
        """The prompt must contain the context, and the question."""
        p = make_pipeline(["Answer [1]."], self.tmp.name)
        p.ask("enterprise refund policy")
        prompt = p.answerer.client.chat.completions.calls[0][1]["content"]
        self.assertIn("CONTEXT PASSAGES", prompt)
        self.assertIn("refund", prompt.lower())


class TestCitationVerification(_PipelineTest):
    """The guarantee that separates this from "the model said so"."""

    def test_invented_citation_is_caught(self):
        """A marker beyond the supplied passages refers to nothing.

        The model is given N passages; citing [99] is a fabrication, and the
        answer must not be presented as grounded.
        """
        p = make_pipeline(
            ["Enterprise refunds take 30 days [99]."], self.tmp.name
        )
        answer = p.ask("enterprise refund policy")
        self.assertIn(99, answer.invalid_citations)
        self.assertFalse(answer.grounded)
        self.assertTrue(answer.warnings)

    def test_uncited_answer_is_flagged(self):
        """An answer with no citations cannot be traced to a source."""
        p = make_pipeline(["Refunds take 30 days."], self.tmp.name)
        answer = p.ask("enterprise refund policy")
        self.assertTrue(answer.uncited_answer)
        self.assertFalse(answer.grounded)
        self.assertTrue(answer.warnings)

    def test_mixed_valid_and_invalid_citations(self):
        p = make_pipeline(["Refunds take 30 days [1] and [42]."], self.tmp.name)
        answer = p.ask("enterprise refund policy")
        self.assertEqual(len(answer.citations), 1)
        self.assertEqual(answer.invalid_citations, [42])
        self.assertFalse(answer.grounded)


class TestRefusal(_PipelineTest):
    """Answering from general knowledge is the failure this product exists to prevent."""

    def test_off_topic_question_never_reaches_the_model(self):
        p = make_pipeline(["Paris is the capital of France."], self.tmp.name)
        answer = p.ask("What is the capital of France?")
        self.assertTrue(answer.refused)
        self.assertEqual(answer.text, REFUSAL)
        self.assertEqual(
            len(p.answerer.client.chat.completions.calls), 0,
            "the model must not be called when nothing relevant was retrieved",
        )

    def test_empty_question(self):
        p = make_pipeline([], self.tmp.name)
        self.assertTrue(p.ask("").refused)

    def test_empty_knowledge_base_refuses(self):
        store = VectorStore(self.tmp.name)
        answerer = Answerer()
        answerer.client = FakeClient(["Some answer [1]."])
        pipeline = KnowledgePipeline(
            store=store, embedder=HashingEmbedder(dims=512), answerer=answerer
        )
        answer = pipeline.ask("anything at all")
        self.assertTrue(answer.refused)
        self.assertEqual(len(answerer.client.chat.completions.calls), 0)

    def test_model_refusal_is_recognised(self):
        p = make_pipeline([REFUSAL], self.tmp.name)
        answer = p.ask("enterprise refund policy")
        self.assertTrue(answer.refused)
        self.assertFalse(answer.uncited_answer, "a refusal needs no citations")


class TestRetrievalQuality(_PipelineTest):
    def test_retrieves_from_the_right_document(self):
        p = make_pipeline([], self.tmp.name)
        result = p.retriever.retrieve("password requirements")
        self.assertTrue(result.chunks)
        self.assertEqual(result.chunks[0].chunk.filename, "security_policy.txt")

    def test_hybrid_reports_which_retriever_found_it(self):
        p = make_pipeline([], self.tmp.name)
        result = p.retriever.retrieve("enterprise refund")
        self.assertTrue(result.chunks)
        self.assertTrue(result.chunks[0].sources)

    def test_off_topic_retrieval_is_empty(self):
        p = make_pipeline([], self.tmp.name)
        self.assertTrue(p.retriever.retrieve("who won the world cup").is_empty)

    def test_context_is_numbered_for_citation(self):
        """Passage numbering is what makes citations verifiable."""
        p = make_pipeline([], self.tmp.name)
        context = p.retriever.retrieve("enterprise refund").context()
        self.assertIn("[1]", context)

    def test_semantic_hit_can_bypass_lexical_gap(self):
        """Paraphrases should survive when semantic similarity is strong."""
        store = VectorStore(self.tmp.name)
        answerer = Answerer()
        answerer.client = FakeClient([])
        pipeline = KnowledgePipeline(
            store=store,
            embedder=TinySemanticEmbedder(),
            answerer=answerer,
        )
        answerer._on_call = pipeline._on_call
        answerer.metrics = pipeline.metrics
        for name, data in CORPUS.items():
            pipeline.ingest(data, filename=name)

        result = pipeline.retriever.retrieve("Can I claw back payment?")

        self.assertTrue(result.chunks)
        self.assertTrue(any(c.semantic_override for c in result.chunks))


class TestResilience(_PipelineTest):
    def test_model_failure_still_returns_passages(self):
        """If the model is down, the retrieved evidence is still useful."""
        p = make_pipeline([ConnectionError("backend down")], self.tmp.name)
        answer = p.ask("enterprise refund policy")
        self.assertTrue(answer.refused)
        self.assertIsNotNone(answer.retrieval)
        self.assertTrue(answer.retrieval.chunks)

    def test_query_history_is_recorded(self):
        p = make_pipeline(["Refunds take 30 days [1]."], self.tmp.name)
        p.ask("enterprise refund policy")
        history = p.store.recent_queries()
        self.assertEqual(len(history), 1)
        self.assertTrue(history[0]["grounded"])

    def test_metrics_are_persisted(self):
        """Regression: a swallowed exception once left this table empty."""
        p = make_pipeline(["Refunds take 30 days [1]."], self.tmp.name)
        p.ask("enterprise refund policy")
        self.assertEqual(p.store.metrics_summary()["calls"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
