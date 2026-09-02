"""
Unit tests for Pydantic schemas — validation rules.
"""

import pytest
from pydantic import ValidationError

from app.schemas.incident import IncidentCreate, SeverityEnum
from app.schemas.chat import ChatRequest
from app.schemas.user import UserRegister


class TestIncidentCreate:
    def _valid(self, **overrides):
        base = {
            "title": "API latency spike",
            "description": "P95 latency exceeded 2s for 10 minutes on the payment service.",
            "severity": "Critical",
            "service": "payment-api",
        }
        return {**base, **overrides}

    def test_valid_incident(self):
        inc = IncidentCreate(**self._valid())
        assert inc.severity == SeverityEnum.critical
        assert inc.title == "API latency spike"

    def test_severity_enum_case_sensitive(self):
        # "critical" lowercase should fail — enum values are title-case
        with pytest.raises(ValidationError):
            IncidentCreate(**self._valid(severity="critical"))

    def test_invalid_severity(self):
        with pytest.raises(ValidationError):
            IncidentCreate(**self._valid(severity="potato"))

    def test_all_valid_severities(self):
        for sev in ("Critical", "High", "Medium", "Low"):
            inc = IncidentCreate(**self._valid(severity=sev))
            assert inc.severity.value == sev

    def test_title_too_short(self):
        with pytest.raises(ValidationError):
            IncidentCreate(**self._valid(title="AB"))  # min_length=3

    def test_title_too_long(self):
        with pytest.raises(ValidationError):
            IncidentCreate(**self._valid(title="x" * 256))

    def test_description_too_short(self):
        with pytest.raises(ValidationError):
            IncidentCreate(**self._valid(description="short"))  # min_length=10

    def test_description_too_long(self):
        with pytest.raises(ValidationError):
            IncidentCreate(**self._valid(description="x" * 5001))

    def test_empty_service(self):
        with pytest.raises(ValidationError):
            IncidentCreate(**self._valid(service=""))


class TestChatRequest:
    def test_valid(self):
        req = ChatRequest(question="What is the retry policy?")
        assert req.conversation_id is None

    def test_with_conversation_id(self):
        req = ChatRequest(question="Follow up question", conversation_id=5)
        assert req.conversation_id == 5

    def test_empty_question(self):
        with pytest.raises(ValidationError):
            ChatRequest(question="")

    def test_question_too_long(self):
        with pytest.raises(ValidationError):
            ChatRequest(question="x" * 2001)

    def test_max_length_question(self):
        req = ChatRequest(question="x" * 2000)
        assert len(req.question) == 2000


class TestUserRegister:
    def _valid(self, **overrides):
        base = {
            "organization_name": "Acme Corp",
            "name": "Jane Smith",
            "email": "jane@acme.com",
            "password": "securepassword123",
        }
        return {**base, **overrides}

    def test_valid_registration(self):
        user = UserRegister(**self._valid())
        assert user.email == "jane@acme.com"

    def test_invalid_email(self):
        with pytest.raises(ValidationError):
            UserRegister(**self._valid(email="not-an-email"))

    def test_password_too_short(self):
        with pytest.raises(ValidationError):
            UserRegister(**self._valid(password="short"))

    def test_name_too_short(self):
        with pytest.raises(ValidationError):
            UserRegister(**self._valid(name="A"))

    def test_org_name_too_short(self):
        with pytest.raises(ValidationError):
            UserRegister(**self._valid(organization_name="X"))
