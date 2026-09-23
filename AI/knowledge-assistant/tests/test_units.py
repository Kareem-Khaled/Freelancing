"""Offline tests for chunking, retrieval and citation verification.

No model server, no network. The LLM is faked so answering paths are
deterministic, and the embedder is the dependency-free hashing one.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from knowledge.answering import REFUSAL, Answer, Answerer, parse_citations  # noqa: E402
from knowledge.chunking import chunk_text  # noqa: E402
from knowledge.embeddings import HashingEmbedder, cosine_similarity  # noqa: E402
from knowledge.retrieval import _coverage  # noqa: E402
from knowledge.store import BM25, VectorStore, stem, tokenise  # noqa: E402


POLICY = """ACME CLOUD — REFUND POLICY

Standard Plans
Customers on Starter and Pro plans may request a refund within 14 days of the
original purchase date.

Enterprise Plans
Enterprise customers may request a refund within 30 days of the invoice date.
Refunds exceeding $10,000 require written approval from the Finance Director.

Duplicate Charges
Verified duplicate charges are always refunded in full.
"""


class TestChunking(unittest.TestCase):
    def test_splits_on_headings(self):
        chunks = chunk_text(POLICY, size=400, overlap=50)
        headings = [c.heading for c in chunks]
        self.assertIn("Enterprise Plans", headings)
        self.assertIn("Standard Plans", headings)

    def test_single_word_headings_detected(self):
        """Regression: "Receipts" and "Travel" were missed, merging sections.

        A one-word heading is extremely common in real policies. Missing it
        collapsed an entire document into one chunk, which then lost to
        shorter chunks under BM25 length normalisation.
        """
        text = "POLICY\n\nReceipts\nKeep every receipt above $25.\n\nTravel\nEconomy class is standard."
        chunks = chunk_text(text, size=300, overlap=0)
        headings = {c.heading for c in chunks}
        self.assertIn("Receipts", headings)
        self.assertIn("Travel", headings)

    def test_heading_is_prepended_for_embedding(self):
        """A chunk must be findable by words that appear only in its heading."""
        chunks = chunk_text(POLICY, size=400, overlap=50)
        enterprise = next(c for c in chunks if c.heading == "Enterprise Plans")
        self.assertIn("Enterprise Plans", enterprise.embed_text)

    def test_oversized_block_is_split(self):
        text = "HEADING\n\n" + ("This is a sentence about refunds. " * 200)
        chunks = chunk_text(text, size=500, overlap=100)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(c.text) <= 700 for c in chunks))

    def test_overlap_does_not_cut_a_word_in_half(self):
        """Regression: a chunk began "esk customers", having lost "NovaD"."""
        body = " ".join(
            f"NovaDesk policy sentence number {i} explains the refund window."
            for i in range(60)
        )
        chunks = chunk_text("HEADING\n\n" + body, size=400, overlap=100)
        self.assertGreater(len(chunks), 1)
        words = {w.strip(".,") for c in chunks for w in c.text.split()}
        self.assertNotIn("esk", words)
        for chunk in chunks:
            first = chunk.text.split()[0].strip(".,")
            self.assertIn(
                first,
                {"NovaDesk", "policy", "sentence", "number", "explains",
                 "the", "refund", "window", "HEADING"},
                msg=f"chunk starts mid-word: {chunk.text[:40]!r}",
            )

    def test_empty_input(self):
        self.assertEqual(chunk_text(""), [])
        self.assertEqual(chunk_text("   \n\n  "), [])

    def test_overlap_must_be_smaller_than_size(self):
        """Otherwise chunking never advances and loops forever."""
        with self.assertRaises(ValueError):
            chunk_text(POLICY, size=100, overlap=100)


class TestStemming(unittest.TestCase):
    """Variants must collapse, but unrelated words must not."""

    def test_variants_match(self):
        for a, b in [
            ("expenses", "expense"), ("submitted", "submit"), ("submitting", "submit"),
            ("policies", "policy"), ("refunds", "refund"), ("days", "day"),
            ("seats", "seat"), ("requirements", "requirement"), ("classes", "class"),
        ]:
            self.assertEqual(stem(a), stem(b), msg=f"{a} vs {b}")

    def test_does_not_over_stem(self):
        """Regression: an early version turned "expenses" into "expen"."""
        self.assertEqual(stem("expenses"), "expense")
        for word in ("access", "business", "address", "analysis"):
            self.assertEqual(stem(word), word, msg=word)

    def test_short_words_untouched(self):
        for word in ("is", "as", "us", "gas"):
            self.assertEqual(stem(word), word, msg=word)


class TestTokenising(unittest.TestCase):
    def test_stopwords_dropped_on_request(self):
        tokens = tokenise("What is the refund policy", drop_stopwords=True)
        self.assertNotIn("what", tokens)
        self.assertNotIn("the", tokens)
        self.assertIn("refund", tokens)

    def test_stopwords_kept_by_default(self):
        self.assertIn("the", tokenise("the refund"))


class TestBM25(unittest.TestCase):
    def setUp(self):
        self.index = BM25()
        self.index.build([
            (1, "Enterprise customers may request a refund within 30 days"),
            (2, "Expense claims must be submitted within 60 days"),
            (3, "Passwords must be at least 14 characters long"),
        ])

    def test_finds_the_right_chunk(self):
        top = self.index.search("enterprise refund", 3)
        self.assertEqual(top[0][0], 1)

    def test_morphological_variants_match(self):
        """"expenses" in the question must find "expense" in the document."""
        top = self.index.search("when are expenses submitted", 3)
        self.assertTrue(top)
        self.assertEqual(top[0][0], 2)

    def test_stopword_only_query_returns_nothing(self):
        """Regression: "What is the ...?" matched every chunk on function words."""
        self.assertEqual(self.index.search("what is the", 3), [])

    def test_unknown_terms_return_nothing(self):
        self.assertEqual(self.index.search("zebra giraffe", 3), [])


class TestHashingEmbedder(unittest.TestCase):
    def setUp(self):
        self.embedder = HashingEmbedder(dims=1024)
        self.corpus = [
            "Enterprise customers may request a refund within 30 days",
            "Expense claims must be submitted within 60 days",
            "The office is open from 9am to 6pm",
        ]
        self.embedder.fit(self.corpus)
        self.matrix = self.embedder.embed(self.corpus)

    def test_vectors_are_normalised(self):
        import numpy as np

        norms = np.linalg.norm(self.matrix, axis=1)
        for n in norms:
            self.assertAlmostEqual(float(n), 1.0, places=5)

    def test_ranks_the_relevant_chunk_first(self):
        query = self.embedder.embed(["enterprise refund policy"])[0]
        scores = cosine_similarity(query, self.matrix)
        self.assertEqual(int(scores.argmax()), 0)

    def test_deterministic(self):
        """Same text must always give the same vector, or tests are flaky."""
        a = self.embedder.embed(["refund policy"])
        b = self.embedder.embed(["refund policy"])
        self.assertTrue((a == b).all())

    def test_empty_input(self):
        self.assertEqual(self.embedder.embed([]).shape[0], 0)

    def test_reports_that_it_is_not_semantic(self):
        """The UI surfaces this, so callers know synonyms will not match."""
        self.assertFalse(self.embedder.semantic)


class TestCoverage(unittest.TestCase):
    """The absolute relevance gate that RRF alone cannot provide."""

    CHUNK = "Enterprise customers may request a refund within 30 days of the invoice date"

    def test_on_topic_question_scores(self):
        self.assertGreater(_coverage("enterprise refund policy", self.CHUNK), 0.5)

    def test_off_topic_question_scores_zero(self):
        self.assertEqual(_coverage("What is the capital of France?", self.CHUNK), 0.0)

    def test_stopword_only_question_scores_zero(self):
        self.assertEqual(_coverage("what is the", self.CHUNK), 0.0)

    def test_morphology_counts(self):
        self.assertGreater(_coverage("refunds for enterprises", self.CHUNK), 0.5)


class TestCitationParsing(unittest.TestCase):
    def test_single_markers(self):
        self.assertEqual(parse_citations("Refunds take 30 days [1]."), [1])

    def test_adjacent_markers(self):
        self.assertEqual(parse_citations("This is true [1][3]."), [1, 3])

    def test_comma_separated(self):
        self.assertEqual(parse_citations("Both apply [1, 2]."), [1, 2])

    def test_no_markers(self):
        self.assertEqual(parse_citations("No citation here."), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
