from sqlalchemy.orm import Session

from app.models.incident import Incident


class IncidentRepository:

    def __init__(self, db: Session):
        self.db = db

    def create(self, incident: Incident) -> Incident:
        self.db.add(incident)
        self.db.commit()
        self.db.refresh(incident)
        return incident

    def save(self, incident: Incident) -> Incident:
        self.db.commit()
        self.db.refresh(incident)
        return incident

    def get_all(self, organization_id: int) -> list[Incident]:
        return (
            self.db.query(Incident)
            .filter(Incident.organization_id == organization_id)
            .order_by(Incident.created_at.desc())
            .all()
        )

    def get_by_id_scoped(
        self,
        incident_id: int,
        organization_id: int,
    ) -> Incident | None:
        """Fetch an incident only if it belongs to the given organization."""
        return (
            self.db.query(Incident)
            .filter(
                Incident.id == incident_id,
                Incident.organization_id == organization_id,
            )
            .first()
        )
