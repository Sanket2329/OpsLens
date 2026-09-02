"""
Investigation schemas.

The new report format separates Facts, Evidence, Inferences, and Recommendations
so the AI never presents assumptions as facts.
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------

class RootCauseStatus(str, Enum):
    confirmed = "Confirmed"
    likely = "Likely"
    unable_to_determine = "Unable to Determine"


class ConfidenceLevel(str, Enum):
    high = "High"
    medium = "Medium"
    low = "Low"


class RetrievedChunk(BaseModel):
    """A single retrieved document chunk with full citation metadata."""
    document_id: int
    filename: str | None = None
    chunk_index: int
    score: float | None = None
    snippet: str | None = None          # First 300 chars of the chunk text


class AlternativeHypothesis(BaseModel):
    """A ranked alternative root cause hypothesis."""
    hypothesis: str
    confidence_pct: int = Field(ge=0, le=100)
    reasoning: str


class EvidenceCoverage(BaseModel):
    """Tracks what evidence was used and what is missing."""
    evidence_used: list[str] = []       # e.g. ["Incident Description", "runbook.pdf"]
    missing_evidence: list[str] = []    # e.g. ["PostgreSQL logs", "Grafana metrics"]
    unknowns: list[str] = []            # Things that cannot be determined


class IncidentSummary(BaseModel):
    """Structured incident metadata for the report header."""
    title: str
    severity: str
    affected_service: str
    business_impact: str
    timeline_note: str | None = None


# ---------------------------------------------------------------------------
# Full investigation report
# ---------------------------------------------------------------------------

class InvestigationReport(BaseModel):
    """
    Full structured investigation report.
    This is the canonical shape stored in the DB and returned by the API.
    """
    model_config = ConfigDict(from_attributes=True)

    # --- Incident context ---
    incident_summary: IncidentSummary | None = None

    # --- Executive summary ---
    executive_summary: str

    # --- Evidence ---
    observed_evidence: list[str] = []
    retrieved_chunks: list[RetrievedChunk] = []

    # --- Root cause ---
    root_cause_status: RootCauseStatus = RootCauseStatus.likely
    root_cause: str

    # --- Confidence ---
    confidence: int = Field(ge=0, le=100)
    confidence_level: ConfidenceLevel = ConfidenceLevel.medium
    confidence_reasoning: str

    # --- Hypotheses ---
    alternative_hypotheses: list[AlternativeHypothesis] = []

    # --- Actions ---
    immediate_actions: list[str] = []
    long_term_prevention: list[str] = []

    # --- Coverage & transparency ---
    evidence_coverage: EvidenceCoverage | None = None
    ai_reasoning_notes: str

    # --- Investigation mode: "single" (default) | "crew" ---
    investigation_mode: str = "single"

    # --- Sources (backward compat) ---
    sources: list[RetrievedChunk] = []

    # --- DB metadata ---
    id: int | None = None
    incident_id: int | None = None
    created_at: datetime | None = None


# ---------------------------------------------------------------------------
# API response models
# ---------------------------------------------------------------------------

class InvestigationResponse(InvestigationReport):
    """API response — same as the full report."""
    pass


class InvestigationHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    incident_id: int
    incident_title: str | None = None
    confidence: int
    confidence_level: str = "Medium"
    root_cause_status: str = "Likely"
    source_count: int
    created_at: datetime
