from sqlalchemy.orm import Session

from app.models.organization import Organization


class OrganizationRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_slug(self, slug: str):
        return (
            self.db.query(Organization)
            .filter(Organization.slug == slug)
            .first()
        )

    def create(self, organization: Organization):
        self.db.add(organization)
        self.db.commit()
        self.db.refresh(organization)
        return organization