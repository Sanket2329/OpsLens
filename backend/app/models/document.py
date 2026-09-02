from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.db.database import Base


class IndexStatus:
    PENDING = "pending"
    INDEXING = "indexing"
    INDEXED = "indexed"
    FAILED = "failed"
    PARTIAL = "partial"  # some chunks indexed, some failed


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    original_filename = Column(String, nullable=False)
    content_type = Column(String)
    file_size = Column(Integer)
    storage_path = Column(String, nullable=False)

    # Indexing status and progress
    index_status = Column(String, default=IndexStatus.PENDING, nullable=False)
    chunk_count = Column(Integer, nullable=True)       # total chunks indexed
    chunks_total = Column(Integer, nullable=True)      # total chunks extracted

    organization_id = Column(
        Integer,
        ForeignKey("organizations.id"),
        nullable=False,
    )
    uploaded_by = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
    )
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    organization = relationship("Organization")
    user = relationship("User")
