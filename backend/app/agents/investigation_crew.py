"""
OpsLens Investigation Crew — Deep Investigation Mode

Architecture:
  Step 1 → Python retrieval (no LLM — 0 tokens)
               ↓ ranked evidence chunks
  Agent 1 → Analyst     (Gemini — diagnose root cause)
               ↓ diagnosis + hypotheses
  Agent 2 → Recommender (Gemini — remediation steps)
               ↓ actions + prevention
  Agent 3 → Reporter    (Gemini — format final JSON)

Total: 3 LLM calls (vs 1 for standard mode)
Quality: Each agent has a focused, narrow job → better reasoning
Cost: ~3x standard but justified for complex incidents

The Retriever is intentionally NOT an LLM agent — it's pure Python
that calls your existing VectorStore directly. No tokens wasted on
"please search for X" → just search(X).
"""

import json
import os

from crewai import Agent, Crew, Process, Task

from app.config.settings import settings
from app.core.logging import get_logger
from app.services.embedding_service import EmbeddingService
from app.services.vector_store import VectorStore

logger = get_logger(__name__)

# LiteLLM model string — CrewAI routes through LiteLLM to Gemini
_LLM = f"gemini/{settings.gemini_model}"

# Minimum similarity threshold for crew retrieval (same as standard mode)
_THRESHOLD = 0.40
_SNIPPET = 300


def _ensure_gemini_env() -> None:
    """LiteLLM reads GEMINI_API_KEY from the environment."""
    os.environ["GEMINI_API_KEY"] = settings.gemini_api_key


class OpsLensInvestigationCrew:
    """
    Deep investigation using a 3-LLM-agent crew.

    The retrieval step is pure Python (no LLM) — evidence is fetched
    directly from Qdrant and passed as structured context to the agents.
    """

    def __init__(self, organization_id: int):
        self.organization_id = organization_id
        self._embedder = EmbeddingService()
        self._store = VectorStore()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def run(self, incident: dict) -> str:
        """
        Run the deep investigation.

        Step 1: Python retrieval — no LLM.
        Steps 2-4: CrewAI agents — 3 LLM calls total.

        Returns:
            Raw JSON string (caller parses with _parse_report).
        """
        _ensure_gemini_env()

        title = incident.get("title", "")
        description = incident.get("description", "")
        severity = incident.get("severity", "")
        service = incident.get("service", "")

        # ── Step 1: Pure Python retrieval (0 tokens) ──────────────────
        logger.info(
            "Crew retrieval started (Python, no LLM): org_id=%d incident=%r",
            self.organization_id, title,
        )

        evidence_block, retrieved_chunks = self._retrieve(
            title=title,
            description=description,
            severity=severity,
            service=service,
        )

        logger.info(
            "Crew retrieval complete: %d chunks found for %r",
            len(retrieved_chunks), title,
        )

        # ── Steps 2-4: 3 LLM agents ───────────────────────────────────
        analyst = Agent(
            role="Senior Site Reliability Engineer",
            goal=(
                "Diagnose the root cause of this production incident using "
                "ONLY the provided evidence. Never speculate beyond evidence. "
                "Distinguish confirmed facts from hypotheses from unknowns. "
                "Assign an evidence-based confidence score."
            ),
            backstory=(
                "You are a Senior Staff SRE with 15 years of production systems "
                "experience at Google. You investigate hundreds of incidents per year. "
                "You are known for never claiming certainty you don't have. "
                "When evidence is insufficient you say 'Unable to Determine' — you "
                "never fill knowledge gaps with assumptions."
            ),
            llm=_LLM,
            verbose=False,
            allow_delegation=False,
        )

        recommender = Agent(
            role="Platform Engineer",
            goal=(
                "Produce specific, immediately actionable remediation steps and "
                "long-term architectural improvements based on the SRE's diagnosis. "
                "Every recommendation must include exact commands or configuration changes."
            ),
            backstory=(
                "You are a Platform Engineer with deep expertise in distributed "
                "systems reliability, Kubernetes, databases, and observability. "
                "You turn SRE diagnoses into precise runbooks. "
                "You never give vague advice like 'check the logs' — "
                "you specify exactly which logs, in which system, with which command."
            ),
            llm=_LLM,
            verbose=False,
            allow_delegation=False,
        )

        reporter = Agent(
            role="Technical Report Writer",
            goal=(
                "Synthesise all findings into a single valid JSON report "
                "matching the exact required schema. Output ONLY JSON — "
                "no markdown, no code fences, no explanatory text."
            ),
            backstory=(
                "You are a technical writer who produces machine-parseable incident "
                "reports for engineering leadership. You are obsessively precise about "
                "JSON validity. You never add fields that aren't in the schema."
            ),
            llm=_LLM,
            verbose=False,
            allow_delegation=False,
        )

        # ── Task 1: Analyst diagnoses using the pre-retrieved evidence ──
        analyse_task = Task(
            description=f"""
Diagnose this production incident using the retrieved evidence below.

═══════════════════════════════
INCIDENT
═══════════════════════════════
Title: {title}
Severity: {severity}
Affected Service: {service}
Description:
{description}

═══════════════════════════════
RETRIEVED DOCUMENTATION EVIDENCE
(fetched directly from the knowledge base — no LLM involved)
═══════════════════════════════
{evidence_block}

═══════════════════════════════
RULES — NEVER VIOLATE
═══════════════════════════════
1. NEVER invent facts. Every claim must cite specific retrieved evidence above.
2. If evidence is insufficient, say "Unable to Determine" — do NOT guess.
3. Separate FACTS (from incident description) from INFERENCES (your reasoning).
4. root_cause_status must be: "Confirmed" | "Likely" | "Unable to Determine"
   - "Confirmed" ONLY if documentation explicitly describes this exact failure.
   - "Likely" if evidence strongly suggests but is not definitive.
   - "Unable to Determine" if evidence is insufficient.
5. Confidence score (0-100):
   - Start at 50
   - +10 per chunk with similarity > 0.85
   - +10 if 3+ chunks retrieved
   - -20 if no documentation was retrieved
   - Cap at 95, floor at 5

Provide your analysis covering:
- Executive summary (2-3 factual sentences, past tense)
- Observed evidence (facts ONLY from the incident description — no inference)
- Root cause with status and evidence citations
- Confidence score with reasoning
- 2-3 alternative hypotheses ranked by likelihood with confidence %
- Evidence coverage: what was used, what is missing, what is unknown
""",
            agent=analyst,
            expected_output=(
                "Structured analysis: executive summary, observed evidence list, "
                "root cause with status + confidence score + reasoning, "
                "alternative hypotheses, evidence coverage assessment."
            ),
        )

        # ── Task 2: Recommender produces actions ────────────────────────
        recommend_task = Task(
            description=f"""
Based on the SRE's diagnosis, produce remediation recommendations.

Incident: {title} | {severity} | {service}

RULES:
1. Immediate actions must be executable within minutes or hours.
2. Include exact commands, service names, config file paths — no vague advice.
   BAD: "Check the database"
   GOOD: "Run: SELECT * FROM pg_stat_activity WHERE state = 'idle in transaction';"
3. Long-term prevention must address the systemic root cause.
4. Do not repeat the diagnosis — focus only on what to DO.

Provide:
- 3-5 immediate actions (specific, prioritised, with exact steps)
- 3-5 long-term prevention measures (architectural, process, tooling improvements)
""",
            agent=recommender,
            expected_output=(
                "3-5 specific immediate actions with exact commands or steps, "
                "and 3-5 long-term prevention measures addressing systemic gaps."
            ),
            context=[analyse_task],
        )

        # ── Task 3: Reporter formats final JSON ──────────────────────────
        report_task = Task(
            description=f"""
Combine ALL findings from the analyst and recommender into a single valid JSON report.

Incident: {title} | {severity} | {service}

OUTPUT RULES:
- Return ONLY valid JSON. No markdown. No code fences. No text before or after.
- If a field is unknown, use null or empty array — never omit required fields.
- investigation_mode must be "crew"

REQUIRED JSON STRUCTURE:
{{
  "executive_summary": "2-3 sentence factual summary of what happened",
  "incident_summary": {{
    "title": "{title}",
    "severity": "{severity}",
    "affected_service": "{service}",
    "business_impact": "Describe impact or say 'Unknown — insufficient data'",
    "timeline_note": "Timeline observations from description, or null"
  }},
  "observed_evidence": [
    "FACT: direct observation from incident description only",
    "FACT: another direct observation"
  ],
  "root_cause_status": "Confirmed | Likely | Unable to Determine",
  "root_cause": "Precise root cause statement with evidence citations",
  "confidence": 75,
  "confidence_level": "High | Medium | Low",
  "confidence_reasoning": "1-2 sentences explaining the confidence calculation",
  "alternative_hypotheses": [
    {{"hypothesis": "description", "confidence_pct": 80, "reasoning": "why"}},
    {{"hypothesis": "description", "confidence_pct": 55, "reasoning": "why"}}
  ],
  "immediate_actions": [
    "Specific action with exact command or step",
    "Another specific action"
  ],
  "long_term_prevention": [
    "Architectural or process improvement",
    "Another improvement"
  ],
  "evidence_coverage": {{
    "evidence_used": ["Incident Description", "list document filenames used"],
    "missing_evidence": ["what would improve this analysis"],
    "unknowns": ["what cannot be determined from available evidence"]
  }},
  "ai_reasoning_notes": "2-3 sentences explaining why this root cause was chosen, citing specific evidence",
  "investigation_mode": "crew"
}}
""",
            agent=reporter,
            expected_output=(
                "A single valid JSON object matching the exact schema. "
                "No markdown, no code fences, no surrounding text."
            ),
            context=[analyse_task, recommend_task],
        )

        # ── Assemble and run the crew ────────────────────────────────────
        crew = Crew(
            agents=[analyst, recommender, reporter],
            tasks=[analyse_task, recommend_task, report_task],
            process=Process.sequential,
            verbose=False,
        )

        result = crew.kickoff()
        raw_output = str(result.raw) if result.raw else str(result)

        logger.info(
            "Crew complete: org_id=%d output_len=%d",
            self.organization_id,
            len(raw_output),
        )

        return raw_output

    # ------------------------------------------------------------------
    # Pure Python retrieval — no LLM call
    # ------------------------------------------------------------------

    def _retrieve(
        self,
        title: str,
        description: str,
        severity: str,
        service: str,
    ) -> tuple[str, list[dict]]:
        """
        Retrieve relevant document chunks from Qdrant using pure Python.
        No LLM involved — 0 tokens used here.

        Returns:
            (evidence_block_str, retrieved_chunks_list)
        """
        query = f"Title: {title}\nDescription: {description}\nSeverity: {severity}\nService: {service}"
        query_vector = self._embedder.embed(query)

        results = self._store.search(
            query_vector=query_vector,
            organization_id=self.organization_id,
            limit=settings.rag_retrieval_limit,
        )

        seen: set[str] = set()
        chunks: list[dict] = []
        lines: list[str] = []

        for i, point in enumerate(results, 1):
            score = point.score or 0.0
            if score < _THRESHOLD:
                continue

            payload = point.payload
            text = payload.get("text", "")
            fingerprint = text[:100].strip()
            if fingerprint in seen:
                continue
            seen.add(fingerprint)

            filename = payload.get("filename") or f"doc_{payload.get('document_id')}"
            chunk_idx = payload.get("chunk_index", "?")
            snippet = text[:_SNIPPET].strip()
            if len(text) > _SNIPPET:
                snippet += "…"

            chunks.append({
                "document_id": payload["document_id"],
                "filename": payload.get("filename"),
                "chunk_index": chunk_idx,
                "score": round(score, 4),
                "snippet": snippet,
            })

            lines.append(
                f"[{i}] {filename} | Chunk #{chunk_idx} | Similarity: {score:.3f}\n"
                f'    "{snippet}"'
            )

        if not lines:
            return "No relevant documentation found in the knowledge base.", []

        return "\n\n".join(lines), chunks
