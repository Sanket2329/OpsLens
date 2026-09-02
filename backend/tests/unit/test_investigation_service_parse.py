"""
Unit tests for InvestigationService._parse_report

Isolated from all external dependencies — tests only the JSON parsing logic.
"""

import json

import pytest

from app.services.investigation_service import InvestigationService


# Build a minimal InvestigationService without touching the DB or external APIs
def _make_service():
    """Return an InvestigationService with all dependencies mocked out."""
    svc = object.__new__(InvestigationService)
    return svc


VALID_REPORT = {
    "root_cause": "Memory leak in worker process",
    "possible_reasons": ["Unclosed DB connections", "Missing GC tuning"],
    "immediate_actions": ["Restart workers", "Scale horizontally"],
    "long_term_prevention": ["Add memory profiling", "Set resource limits"],
    "confidence": 72,
}


class TestParseReport:
    def setup_method(self):
        self.svc = _make_service()

    def test_parses_clean_json(self):
        raw = json.dumps(VALID_REPORT)
        result = self.svc._parse_report(raw)
        assert result["root_cause"] == "Memory leak in worker process"
        assert result["confidence"] == 72

    def test_strips_json_fence(self):
        raw = f"```json\n{json.dumps(VALID_REPORT)}\n```"
        result = self.svc._parse_report(raw)
        assert result["confidence"] == 72

    def test_strips_plain_fence(self):
        raw = f"```\n{json.dumps(VALID_REPORT)}\n```"
        result = self.svc._parse_report(raw)
        assert result["root_cause"] == "Memory leak in worker process"

    def test_strips_whitespace(self):
        raw = f"   \n  {json.dumps(VALID_REPORT)}  \n  "
        result = self.svc._parse_report(raw)
        assert result["confidence"] == 72

    def test_extracts_json_from_surrounding_text(self):
        raw = f"Here is the report:\n{json.dumps(VALID_REPORT)}\nEnd of report."
        result = self.svc._parse_report(raw)
        assert result["confidence"] == 72

    def test_raises_on_no_json(self):
        with pytest.raises(ValueError, match="unparseable"):
            self.svc._parse_report("This is not JSON at all.")

    def test_raises_on_invalid_json(self):
        with pytest.raises(ValueError, match="malformed"):
            self.svc._parse_report('{"key": "value", broken}')

    def test_raises_on_empty_string(self):
        with pytest.raises(ValueError):
            self.svc._parse_report("")

    def test_handles_nested_json_in_fence(self):
        nested = {**VALID_REPORT, "metadata": {"env": "prod", "region": "us-east-1"}}
        raw = f"```json\n{json.dumps(nested)}\n```"
        result = self.svc._parse_report(raw)
        assert result["metadata"]["env"] == "prod"

    def test_preserves_list_fields(self):
        raw = json.dumps(VALID_REPORT)
        result = self.svc._parse_report(raw)
        assert isinstance(result["possible_reasons"], list)
        assert len(result["possible_reasons"]) == 2
