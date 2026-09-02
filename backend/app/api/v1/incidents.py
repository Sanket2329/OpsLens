from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.dependencies import get_db
from app.schemas.incident import IncidentCreate, IncidentResponse, IncidentUpdate
from app.security.dependencies import get_current_user
from app.services.incident_service import IncidentService
from app.services.severity_detector import detect_severity

router = APIRouter(
    prefix="/incidents",
    tags=["Incidents"],
)


@router.post(
    "",
    response_model=IncidentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_incident(
    data: IncidentCreate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = IncidentService(db)
    return service.create(
        data=data,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
    )


@router.get(
    "",
    response_model=list[IncidentResponse],
)
def list_incidents(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = IncidentService(db)
    return service.list(current_user.organization_id)


@router.get(
    "/{incident_id}",
    response_model=IncidentResponse,
)
def get_incident(
    incident_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = IncidentService(db)
    incident = service.get(
        incident_id=incident_id,
        organization_id=current_user.organization_id,
    )
    if incident is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")
    return incident


@router.patch(
    "/{incident_id}",
    response_model=IncidentResponse,
)
def update_incident(
    incident_id: int,
    data: IncidentUpdate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = IncidentService(db)
    incident = service.update(
        incident_id=incident_id,
        organization_id=current_user.organization_id,
        data=data,
    )
    if incident is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")
    return incident


# ---------------------------------------------------------------------------
# Auto-severity detection (0 tokens — rule-based)
# ---------------------------------------------------------------------------

class SeverityDetectRequest(BaseModel):
    title: str = Field(min_length=3)
    description: str = Field(min_length=10)


class SeverityDetectResponse(BaseModel):
    suggested_severity: str
    confidence: float
    signals: list[str]
    reasoning: str


@router.post(
    "/detect-severity",
    response_model=SeverityDetectResponse,
    summary="Auto-detect incident severity from title + description (0 AI tokens)",
)
def detect_incident_severity(
    data: SeverityDetectRequest,
    current_user=Depends(get_current_user),
):
    """
    Analyse the incident title and description using rule-based keyword matching
    to suggest an appropriate severity level.

    Returns the suggested severity, confidence score (0-1), the signals that
    triggered the detection, and a human-readable reasoning explanation.

    No AI tokens used — pure Python regex.
    """
    result = detect_severity(title=data.title, description=data.description)
    return SeverityDetectResponse(
        suggested_severity=result.suggested_severity,
        confidence=result.confidence,
        signals=result.signals,
        reasoning=result.reasoning,
    )
