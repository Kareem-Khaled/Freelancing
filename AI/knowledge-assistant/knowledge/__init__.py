"""Enterprise knowledge assistant: grounded answers with citations."""

from .answering import Answer, Answerer, AnswerError, Citation, parse_citations
from .chunking import Chunk, chunk_text
from .config import settings
from .embeddings import Embedder, HashingEmbedder, get_embedder
from .parsing import DocFormat, ParseProblem, parse_document
from .pipeline import DocumentStatus, IngestResult, KnowledgePipeline
from .retrieval import RetrievalResult, Retriever
from .store import BM25, StoredChunk, VectorStore, stem, tokenise

__all__ = [
    "settings",
    "KnowledgePipeline",
    "IngestResult",
    "DocumentStatus",
    "chunk_text",
    "Chunk",
    "get_embedder",
    "Embedder",
    "HashingEmbedder",
    "VectorStore",
    "StoredChunk",
    "BM25",
    "tokenise",
    "stem",
    "Retriever",
    "RetrievalResult",
    "Answerer",
    "Answer",
    "AnswerError",
    "Citation",
    "parse_citations",
    "parse_document",
    "DocFormat",
    "ParseProblem",
]
