from app.core.logging import get_logger
from app.models.incident import Incident
from app.repositories.incident_repository import IncidentRepository
from app.schemas.incident import IncidentCreate, IncidentUpdate
from app.services.notification_service import NotificationService
from app.services.severity_detector import detect_severity

logger = get_logger(__name__)


class IncidentService:

    def __init__(self, db):
        self.repo = IncidentRepository(db)

    def create(
        self,
        data: IncidentCreate,
        organization_id: int,
        user_id: int,
    ) -> Incident:
        incident = Incident(
            title=data.title,
            description=data.description,
            severity=data.severity.value,
            service=data.service,
            organization_id=organization_id,
            created_by=user_id,
        )

        result = self.repo.create(incident)

        logger.info(
            "Incident created: id=%d title=%r severity=%s org_id=%d",
            result.id, result.title, result.severity, organization_id,
        )

        # Fire-and-forget Slack notification for Critical/High incidents
        NotificationService().notify_incident_created(result)

        return result

    def list(self, organization_id: int) -> list[Incident]:
        return self.repo.get_all(organization_id)

    def get(self, incident_id: int, organization_id: int) -> Incident | None:
        return self.repo.get_by_id_scoped(
            incident_id=incident_id,
            organization_id=organization_id,
        )

    def update(
        self,
        incident_id: int,
        organization_id: int,
        data: IncidentUpdate,
    ) -> Incident | None:
        incident = self.repo.get_by_id_scoped(
            incident_id=incident_id,
            organization_id=organization_id,
        )

        if incident is None:
            return None

        if data.title is not None:
            incident.title = data.title
        if data.description is not None:
            incident.description = data.description
        if data.severity is not None:
            incident.severity = data.severity.value
        if data.service is not None:
            incident.service = data.service
        if data.status is not None:
            incident.status = data.status.value

        updated = self.repo.save(incident)

        logger.info(
            "Incident updated: id=%d org_id=%d",
            updated.id,
            organization_id,
        )

        return updated
