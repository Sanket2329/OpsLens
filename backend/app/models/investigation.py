from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.db.database import Base


class Investigation(Base):
    """Persisted investigation reports keyed to an incident."""

    __tablename__ = "investigations"

    id = Column(Integer, primary_key=True, index=True)

    incident_id = Column(
        Integer,
        ForeignKey("incidents.id"),
        nullable=False,
        index=True,
    )

    organization_id = Column(
        Integer,
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )

    # Full structured report stored as JSON
    report = Column(JSON, nullable=False)

    # Top-level fields duplicated for fast list queries
    confidence = Column(Integer, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    incident = relationship("Incident")
    organization = relationship("Organization")
