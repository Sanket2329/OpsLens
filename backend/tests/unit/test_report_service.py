"""
Unit tests for ReportService — pure function, no mocking needed.
Updated for the full SRE report format.
"""

from datetime import datetime, timezone

import pytest

from app.services.report_service import _confidence_label, render_markdown


SAMPLE_REPORT = {
    "id": 42,
    "incident_id": 7,
    "created_at": datetime(2024, 6, 15, 10, 30, 0, tzinfo=timezone.utc),
    "executive_summary": "The payment-api experienced connection pool exhaustion following a deployment.",
    "incident_summary": {
        "title": "Database connection pool exhausted",
        "severity": "High",
        "affected_service": "payment-api",
        "business_impact": "Payment failures for ~15% of users.",
        "timeline_note": "Started immediately after 14:30 deployment.",
    },
    "observed_evidence": [
        "FACT: HTTP 500 errors reported by users",
        "FACT: Error message: 'remaining connection slots are reserved'",
        "OBSERVATION: Issue began after deployment at 14:30",
    ],
    "retrieved_chunks": [
        {
            "document_id": 1,
            "filename": "runbook.pdf",
            "chunk_index": 3,
            "score": 0.92,
            "snippet": "remaining connection slots are reserved indicates max_connections exhaustion.",
        },
        {
            "document_id": 2,
            "filename": "architecture.md",
            "chunk_index": 0,
            "score": 0.78,
            "snippet": "Connection pool size should be tuned based on workload.",
        },
    ],
    "root_cause_status": "Likely",
    "root_cause": "Based on retrieved documentation, the most likely root cause is connection pool exhaustion.",
    "confidence": 85,
    "confidence_level": "High",
    "confidence_reasoning": "Multiple retrieved documents agree on the same diagnosis with high similarity scores.",
    "alternative_hypotheses": [
        {"hypothesis": "Connection leak", "confidence_pct": 71, "reasoning": "Possible if connections not properly closed."},
        {"hypothesis": "Long running transactions", "confidence_pct": 55, "reasoning": "Could hold connections open."},
    ],
    "immediate_actions": [
        "Restart the app server to clear stale connections",
        "Increase pool_size in SQLAlchemy config",
    ],
    "long_term_prevention": [
        "Add eager loading to all list endpoints",
        "Set up connection pool monitoring alerts",
    ],
    "evidence_coverage": {
        "evidence_used": ["Incident Description", "runbook.pdf", "architecture.md"],
        "missing_evidence": ["PostgreSQL logs", "Grafana metrics"],
        "unknowns": ["Exact connection count at time of failure"],
    },
    "ai_reasoning_notes": "The PostgreSQL runbook (similarity 0.92) explicitly describes this error pattern.",
    "sources": [],
}


class TestConfidenceLabel:
    def test_high_confidence(self):
        assert _confidence_label(90) == "High"

    def test_boundary_high(self):
        assert _confidence_label(75) == "High"

    def test_medium_confidence(self):
        assert _confidence_label(65) == "Medium"

    def test_boundary_medium(self):
        assert _confidence_label(50) == "Medium"

    def test_low_confidence(self):
        assert _confidence_label(30) == "Low"

    def test_zero_confidence(self):
        assert _confidence_label(0) == "Low"


class TestRenderMarkdown:
    def test_returns_string(self):
        result = render_markdown(SAMPLE_REPORT)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_contains_investigation_id(self):
        result = render_markdown(SAMPLE_REPORT)
        assert "42" in result

    def test_contains_incident_id(self):
        result = render_markdown(SAMPLE_REPORT)
        assert "7" in result

    def test_contains_root_cause(self):
        result = render_markdown(SAMPLE_REPORT)
        assert "connection pool exhaustion" in result

    def test_contains_all_sections(self):
        result = render_markdown(SAMPLE_REPORT)
        assert "## Executive Summary" in result
        assert "## Observed Evidence" in result
        assert "## Retrieved Evidence" in result
        assert "## Root Cause Analysis" in result
        assert "## Confidence" in result
        assert "## Alternative Hypotheses" in result
        assert "## Immediate Actions" in result
        assert "## Long-term Prevention" in result
        assert "## Evidence Coverage" in result
        assert "## AI Reasoning Notes" in result
        assert "## Sources" in result

    def test_sources_table_rendered(self):
        result = render_markdown(SAMPLE_REPORT)
        assert "runbook.pdf" in result
        assert "architecture.md" in result

    def test_similarity_scores_in_sources(self):
        result = render_markdown(SAMPLE_REPORT)
        assert "92.00%" in result
        assert "78.00%" in result

    def test_numbered_actions(self):
        result = render_markdown(SAMPLE_REPORT)
        assert "1. Restart the app server" in result
        assert "2. Increase pool_size" in result

    def test_confidence_shown(self):
        result = render_markdown(SAMPLE_REPORT)
        assert "85%" in result
        assert "High" in result

    def test_root_cause_status(self):
        result = render_markdown(SAMPLE_REPORT)
        assert "Likely" in result

    def test_alternative_hypotheses_rendered(self):
        result = render_markdown(SAMPLE_REPORT)
        assert "Connection leak" in result
        assert "71%" in result

    def test_evidence_coverage_used(self):
        result = render_markdown(SAMPLE_REPORT)
        assert "runbook.pdf" in result
        assert "PostgreSQL logs" in result

    def test_ai_reasoning_notes_rendered(self):
        result = render_markdown(SAMPLE_REPORT)
        assert "PostgreSQL runbook" in result

    def test_datetime_formatted(self):
        result = render_markdown(SAMPLE_REPORT)
        assert "2024-06-15" in result

    def test_empty_retrieved_chunks(self):
        report = {**SAMPLE_REPORT, "retrieved_chunks": [], "sources": []}
        result = render_markdown(report)
        assert "No documentation was retrieved" in result

    def test_empty_actions(self):
        report = {**SAMPLE_REPORT, "immediate_actions": [], "long_term_prevention": []}
        result = render_markdown(report)
        assert "_None recommended._" in result

    def test_missing_created_at(self):
        report = {**SAMPLE_REPORT, "created_at": None}
        result = render_markdown(report)
        assert "—" in result

    def test_footer_present(self):
        result = render_markdown(SAMPLE_REPORT)
        assert "Generated by OpsLens" in result

    def test_incident_summary_table(self):
        result = render_markdown(SAMPLE_REPORT)
        assert "payment-api" in result
        assert "Business Impact" in result
