"""
BM25Service — keyword-based document scoring (pure Python, 0 tokens).

BM25 (Best Match 25) ranks documents by term frequency and inverse document
frequency. It finds exact keyword matches — things that vector search misses:
  - Error codes:  "ORA-00942", "SQLSTATE 23505"
  - Service names: "payment-api", "user-service"
  - Version numbers: "postgres-14.2", "k8s-1.28"
  - Technical terms that embed poorly

Used in hybrid search alongside Qdrant vector search.
No external dependencies — pure Python math.
"""

import math
import re
from collections import Counter


def _tokenize(text: str) -> list[str]:
    """Lowercase, split on non-alphanumeric, remove empty tokens."""
    return [t for t in re.split(r"[^a-z0-9]+", text.lower()) if t]


class BM25:
    """
    BM25 ranking over a corpus of documents.

    Standard parameters:
      k1=1.5  — term frequency saturation (higher = more weight to TF)
      b=0.75  — length normalization (1.0 = full normalization)
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self._docs: list[list[str]] = []
        self._doc_freqs: list[Counter] = []
        self._idf: dict[str, float] = {}
        self._avg_dl: float = 0.0

    def index(self, documents: list[str]) -> None:
        """Build the BM25 index from a list of document strings."""
        self._docs = [_tokenize(d) for d in documents]
        self._doc_freqs = [Counter(d) for d in self._docs]
        n = len(self._docs)

        if n == 0:
            self._avg_dl = 0.0
            self._idf = {}
            return

        self._avg_dl = sum(len(d) for d in self._docs) / n

        # IDF: log((N - df + 0.5) / (df + 0.5) + 1)
        df: Counter = Counter()
        for freq in self._doc_freqs:
            for term in freq:
                df[term] += 1

        self._idf = {
            term: math.log((n - count + 0.5) / (count + 0.5) + 1)
            for term, count in df.items()
        }

    def score(self, query: str) -> list[float]:
        """
        Score all indexed documents for a query.
        Returns a list of BM25 scores in the same order as the indexed documents.
        """
        if not self._docs:
            return []

        query_terms = _tokenize(query)
        scores = []

        for i, doc_tokens in enumerate(self._docs):
            dl = len(doc_tokens)
            freq = self._doc_freqs[i]
            doc_score = 0.0

            for term in query_terms:
                if term not in self._idf:
                    continue
                tf = freq.get(term, 0)
                numerator = tf * (self.k1 + 1)
                denominator = tf + self.k1 * (
                    1 - self.b + self.b * dl / max(self._avg_dl, 1)
                )
                doc_score += self._idf[term] * numerator / denominator

            scores.append(doc_score)

        return scores


def reciprocal_rank_fusion(
    vector_results: list[dict],
    bm25_results: list[dict],
    vector_scores: list[float],
    bm25_scores: list[float],
    k: int = 60,
    vector_weight: float = 0.7,
    bm25_weight: float = 0.3,
) -> list[dict]:
    """
    Merge vector search results and BM25 results using Reciprocal Rank Fusion.

    RRF score = Σ weight / (k + rank)

    Args:
        vector_results: Chunks from Qdrant vector search (already ordered by score).
        bm25_results:   Same chunks, re-ordered by BM25 score.
        vector_scores:  Vector similarity scores for each chunk in vector_results order.
        bm25_scores:    BM25 scores for each chunk in bm25_results order.
        k:              RRF constant (default 60, standard value).
        vector_weight:  Weight for vector rankings (0.7 = 70% weight).
        bm25_weight:    Weight for BM25 rankings (0.3 = 30% weight).

    Returns:
        Re-ranked list of chunks with a combined `hybrid_score` field.
    """
    # Build score maps keyed by (document_id, chunk_index)
    def _key(chunk: dict) -> tuple:
        return (chunk.get("document_id"), chunk.get("chunk_index"))

    rrf: dict[tuple, float] = {}
    chunk_map: dict[tuple, dict] = {}

    # Vector rankings
    for rank, chunk in enumerate(vector_results, 1):
        key = _key(chunk)
        rrf[key] = rrf.get(key, 0.0) + vector_weight / (k + rank)
        chunk_map[key] = chunk

    # BM25 rankings — only include if BM25 score > 0
    for rank, (chunk, score) in enumerate(zip(bm25_results, bm25_scores), 1):
        if score <= 0:
            continue
        key = _key(chunk)
        rrf[key] = rrf.get(key, 0.0) + bm25_weight / (k + rank)
        chunk_map[key] = chunk

    # Sort by combined RRF score descending
    ranked = sorted(rrf.items(), key=lambda x: x[1], reverse=True)

    result = []
    for key, combined_score in ranked:
        chunk = dict(chunk_map[key])
        chunk["hybrid_score"] = round(combined_score, 6)
        result.append(chunk)

    return result
