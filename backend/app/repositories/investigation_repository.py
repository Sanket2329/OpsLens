from sqlalchemy.orm import Session

from app.models.investigation import Investigation


class InvestigationRepository:

    def __init__(self, db: Session):
        self.db = db

    def create(self, investigation: Investigation) -> Investigation:
        self.db.add(investigation)
        self.db.commit()
        self.db.refresh(investigation)
        return investigation

    def delete(
        self,
        investigation_id: int,
        organization_id: int,
    ) -> bool:
        """Delete an investigation. Returns True if deleted, False if not found."""
        inv = self.get_by_id(investigation_id, organization_id)
        if inv is None:
            return False
        self.db.delete(inv)
        self.db.commit()
        return True

    def get_by_id(
        self,
        investigation_id: int,
        organization_id: int,
    ) -> Investigation | None:
        return (
            self.db.query(Investigation)
            .filter(
                Investigation.id == investigation_id,
                Investigation.organization_id == organization_id,
            )
            .first()
        )

    def list_by_organization(
        self,
        organization_id: int,
        limit: int = 50,
    ) -> list[Investigation]:
        return (
            self.db.query(Investigation)
            .filter(Investigation.organization_id == organization_id)
            .order_by(Investigation.created_at.desc())
            .limit(limit)
            .all()
        )

    def get_by_incident(
        self,
        incident_id: int,
        organization_id: int,
    ) -> list[Investigation]:
        return (
            self.db.query(Investigation)
            .filter(
                Investigation.incident_id == incident_id,
                Investigation.organization_id == organization_id,
            )
            .order_by(Investigation.created_at.desc())
            .all()
        )
