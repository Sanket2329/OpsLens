"""
SimilarityService — finds similar past incidents (0 tokens).

Uses the existing investigation report vectors stored in the DB to find
incidents with similar root causes, without any new embeddings or API calls.

Approach:
  1. Get the current investigation's query embedding (already computed)
  2. Compare against previous investigation queries using cosine similarity
  3. Return the top matches above a threshold

Since we don't store query vectors in the DB, we use text similarity on
the root_cause + executive_summary fields instead — pure string comparison
using TF-IDF cosine similarity implemented in pure Python.
"""

import math
import re
from collections import Counter

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.repositories.investigation_repository import InvestigationRepository

logger = get_logger(__name__)

_SIMILARITY_THRESHOLD = 0.30
_MAX_SIMILAR = 3


def _tokenize(text: str) -> list[str]:
    return [t for t in re.split(r"[^a-z0-9]+", text.lower()) if len(t) > 2]


def _tfidf_vector(doc_tokens: list[str], idf: dict[str, float]) -> dict[str, float]:
    tf = Counter(doc_tokens)
    total = max(len(doc_tokens), 1)
    return {
        term: (count / total) * idf.get(term, 1.0)
        for term, count in tf.items()
    }


def _cosine_sparse(a: dict[str, float], b: dict[str, float]) -> float:
    shared = set(a) & set(b)
    if not shared:
        return 0.0
    dot = sum(a[t] * b[t] for t in shared)
    norm_a = math.sqrt(sum(v * v for v in a.values()))
    norm_b = math.sqrt(sum(v * v for v in b.values()))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _build_idf(corpus: list[list[str]]) -> dict[str, float]:
    n = len(corpus)
    df: Counter = Counter()
    for doc in corpus:
        for term in set(doc):
            df[term] += 1
    return {
        term: math.log((n + 1) / (count + 1)) + 1
        for term, count in df.items()
    }


def find_similar_investigations(
    investigation_id: int,
    organization_id: int,
    db: Session,
) -> list[dict]:
    """
    Find past investigations similar to the given one.

    Compares root_cause + executive_summary text using TF-IDF cosine similarity.
    Returns up to _MAX_SIMILAR results above _SIMILARITY_THRESHOLD.
    No API calls — pure math on existing DB data.

    Returns:
        List of dicts with: id, incident_id, incident_title, similarity,
        root_cause_snippet, confidence, created_at
    """
    repo = InvestigationRepository(db)

    # Get all investigations for this org
    all_investigations = repo.list_by_organization(organization_id, limit=200)

    if len(all_investigations) < 2:
        return []

    # Find the target
    target = next((inv for inv in all_investigations if inv.id == investigation_id), None)
    if not target:
        return []

    def _text(inv) -> str:
        report = inv.report or {}
        return " ".join(filter(None, [
            report.get("root_cause", ""),
            report.get("executive_summary", ""),
            inv.incident.title if inv.incident else "",
        ]))

    target_text = _text(target)
    target_tokens = _tokenize(target_text)

    if not target_tokens:
        return []

    # Build corpus (excluding target)
    others = [inv for inv in all_investigations if inv.id != investigation_id]
    if not others:
        return []

    corpus_texts = [_text(inv) for inv in others]
    corpus_tokens = [_tokenize(t) for t in corpus_texts]

    # Build IDF over all docs including target
    all_tokens = corpus_tokens + [target_tokens]
    idf = _build_idf(all_tokens)

    target_vec = _tfidf_vector(target_tokens, idf)

    results = []
    for inv, tokens in zip(others, corpus_tokens):
        if not tokens:
            continue
        vec = _tfidf_vector(tokens, idf)
        sim = _cosine_sparse(target_vec, vec)

        if sim >= _SIMILARITY_THRESHOLD:
            report = inv.report or {}
            root_cause = report.get("root_cause", "")
            results.append({
                "id": inv.id,
                "incident_id": inv.incident_id,
                "incident_title": inv.incident.title if inv.incident else f"Incident #{inv.incident_id}",
                "similarity": round(sim, 3),
                "root_cause_snippet": root_cause[:200] + ("…" if len(root_cause) > 200 else ""),
                "confidence": inv.confidence or 0,
                "created_at": inv.created_at.isoformat() if inv.created_at else None,
            })

    results.sort(key=lambda x: x["similarity"], reverse=True)
    top = results[:_MAX_SIMILAR]

    logger.info(
        "Similarity search: investigation_id=%d found %d similar (threshold=%.2f)",
        investigation_id,
        len(top),
        _SIMILARITY_THRESHOLD,
    )

    return top
