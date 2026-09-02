"""
RagService — responsible ONLY for AI generation.

Contract:
- Never access the database.
- For investigation: callers pass pre-retrieved context + structured chunks.
- For chat Q&A: handles its own retrieval to keep callers simple.
- Output: AI-generated text (string or stream of strings).
"""

import time
from collections.abc import Generator

from google import genai

from app.config.settings import settings
from app.core.logging import get_logger
from app.core.token_tracker import track_usage
from app.services.embedding_service import EmbeddingService
from app.services.vector_store import VectorStore

logger = get_logger(__name__)


class RagService:

    def __init__(self):
        self.client = genai.Client(api_key=settings.gemini_api_key)
        self.model = settings.gemini_model
        self._embedder = EmbeddingService()
        self._store = VectorStore()

    # ------------------------------------------------------------------
    # Chat Q&A
    # ------------------------------------------------------------------

    def answer(
        self,
        question: str,
        organization_id: int | None = None,
        conversation_history: list[dict] | None = None,
    ) -> str:
        query_vector = self._embedder.embed(question)
        results = self._store.search(
            query_vector=query_vector,
            organization_id=organization_id,
            limit=settings.rag_chat_retrieval_limit,
        )

        context_parts = [point.payload["text"] for point in results]
        context = (
            "\n\n---\n\n".join(context_parts)
            if context_parts
            else "No relevant documentation found."
        )

        history_block = self._build_history_block(conversation_history)
        prompt = (
            "You are an expert AI assistant for an engineering team.\n\n"
            "Answer the question based ONLY on the documentation provided below.\n"
            "If the documentation does not contain enough information to answer, say:\n"
            '"I couldn\'t find that information in the available documentation."\n\n'
            "Do not fabricate information. Be concise and professional.\n\n"
            + (f"Conversation so far:\n{history_block}\n\n" if history_block else "")
            + f"Documentation:\n{context}\n\nQuestion:\n{question}\n\nAnswer:"
        )
        return self._generate(prompt, operation="chat")

    # ------------------------------------------------------------------
    # Incident Investigation — blocking
    # ------------------------------------------------------------------

    def investigate(
        self,
        incident,
        context: str,
        retrieved_chunks: list[dict] | None = None,
    ) -> str:
        prompt = self._build_investigation_prompt(incident, context, retrieved_chunks)
        return self._generate(prompt, operation="investigation")

    # ------------------------------------------------------------------
    # Incident Investigation — streaming
    # ------------------------------------------------------------------

    def investigate_stream(
        self,
        incident,
        context: str,
        retrieved_chunks: list[dict] | None = None,
    ) -> Generator[str, None, None]:
        prompt = self._build_investigation_prompt(incident, context, retrieved_chunks)
        start = time.monotonic()
        for chunk in self.client.models.generate_content_stream(
            model=self.model,
            contents=prompt,
        ):
            if chunk.text:
                yield chunk.text
        logger.info(
            "Gemini stream complete: operation=investigation model=%s elapsed=%.2fs",
            self.model,
            round(time.monotonic() - start, 2),
        )

    # ------------------------------------------------------------------
    # Private — SRE Investigation Prompt
    # ------------------------------------------------------------------

    def _build_investigation_prompt(
        self,
        incident,
        context: str,
        retrieved_chunks: list[dict] | None = None,
    ) -> str:
        """
        Build the full Senior SRE investigation prompt.

        The prompt enforces strict separation of:
          Facts | Evidence | Observations | Hypotheses | Assumptions | Recommendations

        The AI is explicitly forbidden from hallucinating.
        """
        has_docs = bool(context.strip())
        chunks = retrieved_chunks or []

        # Build the retrieved evidence block with full citations
        retrieved_evidence_block = ""
        if chunks:
            lines = []
            for i, c in enumerate(chunks, 1):
                fname = c.get("filename") or f"doc_{c.get('document_id')}"
                chunk_num = c.get("chunk_index", "?")
                score = c.get("score")
                score_str = f"{score:.3f}" if score is not None else "N/A"
                snippet = c.get("snippet", "")[:400]
                lines.append(
                    f"[CHUNK {i}]\n"
                    f"Document: {fname}\n"
                    f"Chunk: #{chunk_num}\n"
                    f"Similarity: {score_str}\n"
                    f"Snippet: \"{snippet}\""
                )
            retrieved_evidence_block = "\n\n".join(lines)
        else:
            retrieved_evidence_block = "No documentation was retrieved."

        no_doc_warning = (
            "\n⚠️  WARNING: No relevant documentation was found in the knowledge base.\n"
            "You MUST explicitly state in root_cause that you cannot determine the root cause from available evidence.\n"
            "Set root_cause_status to 'Unable to Determine'.\n"
            "Set confidence below 30.\n"
        ) if not has_docs else ""

        return f"""You are a Senior Staff Site Reliability Engineer (SRE) at Google with 15 years of experience in production systems.

You are conducting a formal post-incident investigation. Your report will be reviewed by engineering leadership.

═══════════════════════════════════════════════════════
ABSOLUTE RULES — NEVER VIOLATE THESE
═══════════════════════════════════════════════════════
1. NEVER invent facts. Every claim must be grounded in the incident description or retrieved documentation.
2. NEVER say "The X caused Y" unless the documentation explicitly confirms it. Use "X is a likely contributing factor."
3. NEVER present a hypothesis as a confirmed fact.
4. If documentation is missing, explicitly say so. Do NOT fill gaps with assumptions.
5. Separate FACTS (from incident description) from INFERENCES (your reasoning) from RECOMMENDATIONS (your advice).
6. If you cannot determine the root cause, say: "Unable to determine from available evidence."
7. Confidence score MUST be calculated from: retrieval similarity scores + volume of evidence + document consistency. Do NOT assign arbitrary values.
8. Return ONLY valid JSON. No markdown. No code fences. No explanations outside the JSON.
{no_doc_warning}
═══════════════════════════════════════════════════════
INCIDENT DETAILS
═══════════════════════════════════════════════════════
Title: {incident.title}
Severity: {incident.severity}
Affected Service: {incident.service}
Description:
{incident.description}

═══════════════════════════════════════════════════════
RETRIEVED DOCUMENTATION CHUNKS
═══════════════════════════════════════════════════════
{retrieved_evidence_block}

═══════════════════════════════════════════════════════
FULL CONTEXT (for cross-referencing)
═══════════════════════════════════════════════════════
{context if has_docs else "No documentation available."}

═══════════════════════════════════════════════════════
OUTPUT INSTRUCTIONS
═══════════════════════════════════════════════════════
Return a single JSON object matching this EXACT structure.
Do not add extra fields. Do not omit required fields.

Confidence calculation guide:
- Start at 50 (baseline)
- +10 if average similarity score > 0.85
- +10 if 3+ chunks retrieved
- +10 if multiple documents agree on the same diagnosis
- -20 if no documentation was retrieved
- -10 if only 1 chunk retrieved
- -10 if chunks are from unrelated topics
- Cap at 95 (never claim 100% certainty)
- Floor at 5 (never claim 0%)

root_cause_status rules:
- "Confirmed" ONLY if documentation explicitly describes this exact failure mode
- "Likely" if evidence strongly suggests it but is not definitive
- "Unable to Determine" if evidence is insufficient

{{
  "executive_summary": "A 2-3 sentence paragraph explaining what happened, what was affected, and what is known so far. Write in past tense. Be factual.",

  "incident_summary": {{
    "title": "{incident.title}",
    "severity": "{incident.severity}",
    "affected_service": "{incident.service}",
    "business_impact": "Describe the likely user/business impact based on the severity and service. If unknown, say 'Unknown — logs not available'.",
    "timeline_note": "Any timeline observations from the incident description. If none, say null."
  }},

  "observed_evidence": [
    "FACT: Direct observation from the incident description only. No inference.",
    "FACT: Another direct observation.",
    "OBSERVATION: Something that can be inferred from the description with high confidence."
  ],

  "root_cause_status": "Likely",

  "root_cause": "State the root cause precisely. If Confirmed, cite the documentation. If Likely, say 'Based on [evidence], the most likely root cause is...'. If Unable to Determine, say 'The available evidence is insufficient to determine the root cause. Missing: [list what is needed].'",

  "confidence": 72,

  "confidence_level": "Medium",

  "confidence_reasoning": "Explain in 1-2 sentences how you calculated confidence. Reference the similarity scores and evidence volume.",

  "alternative_hypotheses": [
    {{
      "hypothesis": "Most likely alternative explanation",
      "confidence_pct": 82,
      "reasoning": "Why this hypothesis is supported by the evidence"
    }},
    {{
      "hypothesis": "Second alternative",
      "confidence_pct": 65,
      "reasoning": "Why this is plausible but less certain"
    }},
    {{
      "hypothesis": "Third alternative",
      "confidence_pct": 45,
      "reasoning": "Possible but speculative"
    }}
  ],

  "immediate_actions": [
    "Specific operational action with exact command or step — no vague instructions",
    "Another specific action",
    "Another specific action"
  ],

  "long_term_prevention": [
    "Architectural or process improvement",
    "Another systemic improvement",
    "Another improvement"
  ],

  "evidence_coverage": {{
    "evidence_used": [
      "Incident Description",
      "List each document filename that was actually retrieved and used"
    ],
    "missing_evidence": [
      "List what evidence would improve this analysis (e.g. 'Application logs', 'Database metrics', 'Deployment history')"
    ],
    "unknowns": [
      "List things that cannot be determined from available evidence"
    ]
  }},

  "ai_reasoning_notes": "Explain in 2-3 sentences WHY you selected this root cause. Reference specific evidence. Example: 'The PostgreSQL runbook (similarity 0.91) explicitly describes this error pattern. The incident description matches the documented failure mode. Deployment timing adds further support for a connection leak hypothesis.'"
}}"""

    def _generate(self, prompt: str, operation: str = "generate") -> str:
        start = time.monotonic()
        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
        )
        elapsed = round(time.monotonic() - start, 2)
        text = response.text or ""
        logger.info(
            "Gemini generate_content: operation=%s model=%s elapsed=%.2fs response_len=%d",
            operation,
            self.model,
            elapsed,
            len(text),
        )
        track_usage(response, operation=operation, model=self.model)
        return text

    def _build_history_block(self, history: list[dict] | None) -> str:
        if not history:
            return ""
        turns = history[-settings.rag_conversation_history_turns:]
        lines = []
        for turn in turns:
            label = "User" if turn["role"] == "user" else "Assistant"
            lines.append(f"{label}: {turn['content']}")
        return "\n".join(lines)
