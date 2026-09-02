"""
InvestigationService — main orchestration service.

Flow:
  Load Incident (org-scoped)
  → Build rich query
  → Generate embedding
  → Search Qdrant (org-scoped, threshold filtered, deduplicated)
  → Build structured chunks with snippets
  → Call RagService with full context + chunk metadata
  → Parse structured JSON report
  → Persist
  → Return
"""

import json
import re
import time
from collections.abc import Generator

from sqlalchemy.orm import Session

from app.config.settings import settings
from app.core.logging import get_logger
from app.models.investigation import Investigation
from app.repositories.incident_repository import IncidentRepository
from app.repositories.investigation_repository import InvestigationRepository
from app.services.bm25_service import BM25, reciprocal_rank_fusion
from app.services.embedding_service import EmbeddingService
from app.services.rag_service import RagService
from app.services.reranker import rerank
from app.services.vector_store import VectorStore

logger = get_logger(__name__)

# Minimum similarity score to include a chunk as evidence.
# If NO chunks pass this threshold we automatically retry at a lower threshold
# so that "No documentation retrieved" only occurs when Qdrant truly has nothing.
_SIMILARITY_THRESHOLD = 0.35
_SIMILARITY_THRESHOLD_FALLBACK = 0.20   # used if primary threshold yields 0 results
_SNIPPET_LENGTH = 300


def _normalise_confidence_level(confidence: int) -> str:
    if confidence >= 75:
        return "High"
    if confidence >= 50:
        return "Medium"
    return "Low"


class InvestigationService:

    def __init__(self, db: Session):
        self.db = db
        self.incidents = IncidentRepository(db)
        self.investigations = InvestigationRepository(db)
        self.embedder = EmbeddingService()
        self.store = VectorStore()
        self.rag = RagService()

    # ------------------------------------------------------------------
    # Crew-based investigation (CrewAI multi-agent)
    # ------------------------------------------------------------------

    def investigate_with_crew(
        self,
        incident_id: int,
        organization_id: int,
    ) -> dict | None:
        """
        Run a multi-agent investigation using the OpsLens CrewAI crew.

        The crew consists of 4 agents:
          1. Retriever  — searches the knowledge base
          2. Analyst    — diagnoses root cause
          3. Recommender — produces remediation steps
          4. Reporter   — formats the final JSON report

        Returns the same InvestigationReport shape as investigate().
        """
        from app.agents.investigation_crew import OpsLensInvestigationCrew

        start = time.monotonic()

        incident = self.incidents.get_by_id_scoped(
            incident_id=incident_id,
            organization_id=organization_id,
        )
        if not incident:
            return None

        logger.info(
            "Crew investigation started: incident_id=%d org_id=%d title=%r",
            incident_id, organization_id, incident.title,
        )

        incident_dict = {
            "title": incident.title,
            "description": incident.description,
            "severity": incident.severity,
            "service": incident.service,
        }

        crew = OpsLensInvestigationCrew(organization_id=organization_id)
        raw_output = crew.run(incident_dict)

        # Reuse existing JSON parser — same defensive parsing as single-agent
        report_json = self._parse_report(raw_output)

        # Mark as crew investigation
        report_json["investigation_mode"] = "crew"

        # Retrieve chunks separately for citation display
        # (the crew's retriever already searched, but we pull ground-truth from Qdrant
        #  so the frontend has structured source data to display)
        query_str = self._build_query(incident)
        query_vector = self.embedder.embed(query_str)
        results = self.store.search(
            query_vector=query_vector,
            organization_id=organization_id,
            limit=settings.rag_retrieval_limit,
        )
        retrieved_chunks, _ = self._process_results(results, query=query_str)
        report_json["retrieved_chunks"] = retrieved_chunks
        report_json["sources"] = retrieved_chunks

        investigation = self.investigations.create(
            Investigation(
                incident_id=incident_id,
                organization_id=organization_id,
                report=report_json,
                confidence=report_json.get("confidence"),
            )
        )

        elapsed = round(time.monotonic() - start, 2)
        logger.info(
            "Crew investigation complete: id=%d incident_id=%d confidence=%s elapsed=%.2fs",
            investigation.id, incident_id, report_json.get("confidence"), elapsed,
        )

        report_json["id"] = investigation.id
        report_json["incident_id"] = incident_id
        report_json["created_at"] = investigation.created_at
        return report_json

    # ------------------------------------------------------------------
    # Blocking investigation
    # ------------------------------------------------------------------

    def investigate(
        self,
        incident_id: int,
        organization_id: int,
    ) -> dict | None:
        start = time.monotonic()

        incident = self.incidents.get_by_id_scoped(
            incident_id=incident_id,
            organization_id=organization_id,
        )
        if not incident:
            return None

        logger.info(
            "Investigation started: incident_id=%d org_id=%d title=%r",
            incident_id, organization_id, incident.title,
        )

        query_str = self._build_query(incident)
        query_vector = self.embedder.embed(query_str)

        results = self.store.search(
            query_vector=query_vector,
            organization_id=organization_id,
            limit=settings.rag_retrieval_limit,
        )

        retrieved_chunks, context = self._process_results(results, query=query_str)

        logger.info(
            "Retrieval: %d raw → %d usable chunks for incident_id=%d",
            len(results), len(retrieved_chunks), incident_id,
        )

        raw_report = self.rag.investigate(
            incident=incident,
            context=context,
            retrieved_chunks=retrieved_chunks,
        )

        report_json = self._parse_report(raw_report)

        # Always override sources with ground-truth retrieved chunks
        report_json["retrieved_chunks"] = retrieved_chunks
        report_json["sources"] = retrieved_chunks  # backward compat

        investigation = self.investigations.create(
            Investigation(
                incident_id=incident_id,
                organization_id=organization_id,
                report=report_json,
                confidence=report_json.get("confidence"),
            )
        )

        elapsed = round(time.monotonic() - start, 2)
        logger.info(
            "Investigation complete: id=%d incident_id=%d confidence=%s elapsed=%.2fs",
            investigation.id, incident_id, report_json.get("confidence"), elapsed,
        )

        # Slack notification — fire and forget
        try:
            from app.services.notification_service import NotificationService
            NotificationService().notify_investigation_complete(
                investigation_report=report_json,
                incident_title=incident.title,
            )
        except Exception as exc:
            logger.debug("Slack notification skipped: %s", exc)

        report_json["id"] = investigation.id
        report_json["incident_id"] = incident_id
        report_json["created_at"] = investigation.created_at
        return report_json

    # ------------------------------------------------------------------
    # Streaming investigation
    # ------------------------------------------------------------------

    def investigate_stream(
        self,
        incident_id: int,
        organization_id: int,
    ) -> Generator[dict, None, None]:
        incident = self.incidents.get_by_id_scoped(
            incident_id=incident_id,
            organization_id=organization_id,
        )
        if not incident:
            raise ValueError("Incident not found")

        logger.info(
            "Stream investigation started: incident_id=%d org_id=%d",
            incident_id, organization_id,
        )

        query_str = self._build_query(incident)
        query_vector = self.embedder.embed(query_str)

        results = self.store.search(
            query_vector=query_vector,
            organization_id=organization_id,
            limit=settings.rag_retrieval_limit,
        )

        retrieved_chunks, context = self._process_results(results, query=query_str)
        for token in self.rag.investigate_stream(
            incident=incident,
            context=context,
            retrieved_chunks=retrieved_chunks,
        ):
            full_text += token
            yield {"type": "token", "content": token}

        report_json = self._parse_report(full_text)
        report_json["retrieved_chunks"] = retrieved_chunks
        report_json["sources"] = retrieved_chunks

        investigation = self.investigations.create(
            Investigation(
                incident_id=incident_id,
                organization_id=organization_id,
                report=report_json,
                confidence=report_json.get("confidence"),
            )
        )

        report_json["id"] = investigation.id
        report_json["incident_id"] = incident_id
        report_json["created_at"] = investigation.created_at.isoformat()

        logger.info(
            "Stream investigation complete: id=%d incident_id=%d",
            investigation.id, incident_id,
        )

        yield {"type": "done", "report": report_json}

    # ------------------------------------------------------------------
    # History queries
    # ------------------------------------------------------------------

    def list_history(self, organization_id: int) -> list[dict]:
        investigations = self.investigations.list_by_organization(organization_id)
        result = []
        for inv in investigations:
            report = inv.report or {}
            result.append({
                "id": inv.id,
                "incident_id": inv.incident_id,
                "incident_title": inv.incident.title if inv.incident else None,
                "confidence": inv.confidence or 0,
                "confidence_level": report.get("confidence_level", "Medium"),
                "root_cause_status": report.get("root_cause_status", "Likely"),
                "source_count": len(report.get("retrieved_chunks", report.get("sources", []))),
                "created_at": inv.created_at,
            })
        return result

    def delete(
        self,
        investigation_id: int,
        organization_id: int,
    ) -> bool:
        return self.investigations.delete(
            investigation_id=investigation_id,
            organization_id=organization_id,
        )

    def get_by_id(
        self,
        investigation_id: int,
        organization_id: int,
    ) -> dict | None:
        inv = self.investigations.get_by_id(
            investigation_id=investigation_id,
            organization_id=organization_id,
        )
        if not inv:
            return None
        report = dict(inv.report)
        report["id"] = inv.id
        report["incident_id"] = inv.incident_id
        report["created_at"] = inv.created_at

        # Normalise: ensure both retrieved_chunks and sources are populated
        # Old reports only had 'sources'; new reports have 'retrieved_chunks'
        if not report.get("retrieved_chunks") and report.get("sources"):
            report["retrieved_chunks"] = report["sources"]
        elif report.get("retrieved_chunks") and not report.get("sources"):
            report["sources"] = report["retrieved_chunks"]

        # Ensure required new fields exist for old reports
        report.setdefault("executive_summary", report.get("root_cause", ""))
        report.setdefault("root_cause_status", "Likely")
        report.setdefault("confidence_level", _normalise_confidence_level(report.get("confidence", 50)))
        report.setdefault("confidence_reasoning", "")
        report.setdefault("alternative_hypotheses", [])
        report.setdefault("observed_evidence", [])
        report.setdefault("ai_reasoning_notes", "")
        report.setdefault("evidence_coverage", {
            "evidence_used": ["Incident Description"],
            "missing_evidence": [],
            "unknowns": [],
        })
        report.setdefault("incident_summary", None)

        return report

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_query(self, incident) -> str:
        """Build a rich semantic query from incident fields."""
        return (
            f"Title: {incident.title}\n"
            f"Description: {incident.description}\n"
            f"Severity: {incident.severity}\n"
            f"Service: {incident.service}"
        )

    def _process_results(self, results: list, query: str = "") -> tuple[list[dict], str]:
        """
        Process raw Qdrant results using hybrid search + reranking.

        Pipeline:
          1. Filter by similarity threshold (two-pass: 0.35 → 0.20 fallback)
          2. BM25 keyword scoring on chunk texts
          3. RRF merge of vector + BM25 rankings
          4. Rerank combined results by query term overlap
          5. Return top chunks with context string

        Returns:
            (retrieved_chunks: list[dict], context: str)
        """
        # Step 1: Build initial candidate list from vector results
        raw_chunks, _ = self._filter_results(results, _SIMILARITY_THRESHOLD)

        if not raw_chunks and results:
            best_score = max((p.score or 0.0) for p in results)
            logger.warning(
                "No chunks passed threshold=%.2f (best=%.3f). "
                "Using fallback threshold=%.2f",
                _SIMILARITY_THRESHOLD, best_score, _SIMILARITY_THRESHOLD_FALLBACK,
            )
            raw_chunks, _ = self._filter_results(results, _SIMILARITY_THRESHOLD_FALLBACK)

        if not raw_chunks:
            if results:
                logger.warning(
                    "All %d results below fallback threshold. "
                    "Investigation proceeds without documentation.",
                    len(results),
                )
            else:
                logger.warning(
                    "Qdrant returned 0 results for this org. "
                    "No documents indexed or no semantic overlap."
                )
            return [], ""

        # Step 2: BM25 scoring on the candidate chunks
        if query and len(raw_chunks) > 1:
            chunk_texts = [c.get("snippet", "") or "" for c in raw_chunks]
            bm25 = BM25()
            bm25.index(chunk_texts)
            bm25_scores = bm25.score(query)

            # Sort chunks by BM25 score for RRF
            bm25_ranked = sorted(
                zip(raw_chunks, bm25_scores),
                key=lambda x: x[1],
                reverse=True,
            )
            bm25_chunks = [c for c, _ in bm25_ranked]
            bm25_scores_sorted = [s for _, s in bm25_ranked]

            # Step 3: Merge via Reciprocal Rank Fusion
            vector_scores = [c.get("score", 0.0) for c in raw_chunks]
            merged = reciprocal_rank_fusion(
                vector_results=raw_chunks,
                bm25_results=bm25_chunks,
                vector_scores=vector_scores,
                bm25_scores=bm25_scores_sorted,
            )
            logger.debug(
                "Hybrid search: %d chunks merged (vector + BM25)",
                len(merged),
            )
        else:
            merged = raw_chunks

        # Step 4: Rerank by query term overlap
        if query:
            merged = rerank(query=query, chunks=merged, top_k=len(merged))

        # Step 5: Build context string
        context_parts = []
        for chunk in merged:
            # Use full text from original results if available
            doc_id = chunk.get("document_id")
            chunk_idx = chunk.get("chunk_index")
            # Find full text from original Qdrant results
            full_text = ""
            for point in results:
                if (point.payload.get("document_id") == doc_id and
                        point.payload.get("chunk_index") == chunk_idx):
                    full_text = point.payload.get("text", "")
                    break
            if full_text:
                context_parts.append(full_text)

        context = "\n\n---\n\n".join(context_parts)

        logger.info(
            "Retrieval pipeline: %d raw → %d after threshold → %d after hybrid+rerank",
            len(results),
            len(raw_chunks),
            len(merged),
        )

        return merged, context

    def _filter_results(
        self,
        results: list,
        threshold: float,
    ) -> tuple[list[dict], str]:
        """Apply a similarity threshold + deduplication to raw Qdrant results."""
        seen_texts: set[str] = set()
        retrieved_chunks: list[dict] = []
        context_parts: list[str] = []

        for point in results:
            score = point.score or 0.0

            if score < threshold:
                continue

            payload = point.payload
            text = payload.get("text", "")

            # Deduplicate by text fingerprint
            fingerprint = text[:100].strip()
            if fingerprint in seen_texts:
                logger.debug("Dropping duplicate chunk (fingerprint=%r)", fingerprint[:40])
                continue
            seen_texts.add(fingerprint)

            snippet = text[:_SNIPPET_LENGTH].strip()
            if len(text) > _SNIPPET_LENGTH:
                snippet += "…"

            retrieved_chunks.append({
                "document_id": payload["document_id"],
                "filename": payload.get("filename"),
                "chunk_index": payload["chunk_index"],
                "score": round(score, 4),
                "snippet": snippet,
            })
            context_parts.append(text)

        context = "\n\n---\n\n".join(context_parts)
        return retrieved_chunks, context

    def _parse_report(self, raw: str) -> dict:
        clean = raw.strip()
        clean = re.sub(r"^```json\s*", "", clean, flags=re.MULTILINE)
        clean = re.sub(r"^```\s*", "", clean, flags=re.MULTILINE)
        clean = re.sub(r"\s*```\s*$", "", clean, flags=re.MULTILINE).strip()

        match = re.search(r"\{.*\}", clean, re.DOTALL)
        if not match:
            logger.error("Could not extract JSON from Gemini response: %r", raw[:500])
            raise ValueError("AI returned an unparseable response. Please retry.")

        try:
            parsed = json.loads(match.group())
        except json.JSONDecodeError as exc:
            logger.error("Invalid JSON from Gemini: %s | raw: %r", exc, raw[:500])
            raise ValueError("AI returned malformed JSON. Please retry.") from exc

        # Normalise confidence_level
        confidence = parsed.get("confidence", 50)
        if "confidence_level" not in parsed:
            if confidence >= 75:
                parsed["confidence_level"] = "High"
            elif confidence >= 50:
                parsed["confidence_level"] = "Medium"
            else:
                parsed["confidence_level"] = "Low"

        # Ensure required fields exist with sensible defaults
        parsed.setdefault("executive_summary", parsed.get("root_cause", "Investigation complete."))
        parsed.setdefault("root_cause_status", "Likely")
        parsed.setdefault("confidence_reasoning", "Confidence derived from retrieved evidence quality.")
        parsed.setdefault("alternative_hypotheses", [])
        parsed.setdefault("observed_evidence", [])
        parsed.setdefault("ai_reasoning_notes", "")
        parsed.setdefault("evidence_coverage", {
            "evidence_used": ["Incident Description"],
            "missing_evidence": [],
            "unknowns": [],
        })

        return parsed
