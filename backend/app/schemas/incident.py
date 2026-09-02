from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class SeverityEnum(str, Enum):
    critical = "Critical"
    high = "High"
    medium = "Medium"
    low = "Low"


class StatusEnum(str, Enum):
    open = "Open"
    investigating = "Investigating"
    resolved = "Resolved"


class IncidentCreate(BaseModel):
    title: str = Field(min_length=3, max_length=255)
    description: str = Field(min_length=10, max_length=5000)
    severity: SeverityEnum
    service: str = Field(min_length=1, max_length=255)


class IncidentUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=255)
    description: str | None = Field(default=None, min_length=10, max_length=5000)
    severity: SeverityEnum | None = None
    service: str | None = Field(default=None, min_length=1, max_length=255)
    status: StatusEnum | None = None


class IncidentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str
    severity: str
    service: str
    status: str
    created_at: datetime
