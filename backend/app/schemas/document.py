from datetime import datetime

from pydantic import BaseModel, ConfigDict


class IndexStatus:
    PENDING = "pending"
    INDEXING = "indexing"
    INDEXED = "indexed"
    FAILED = "failed"
    PARTIAL = "partial"


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    original_filename: str
    file_size: int
    content_type: str
    created_at: datetime
    index_status: str = "pending"
    chunk_count: int | None = None
    chunks_total: int | None = None
