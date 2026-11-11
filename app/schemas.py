import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class RegionIn(BaseModel):
    name: str
    district: str
    state: str = ""


class RegionOut(RegionIn):
    model_config = ConfigDict(from_attributes=True)
    id: int


class JobAccepted(BaseModel):
    job_id: uuid.UUID
    status: str = "queued"
    status_url: str


class RowError(BaseModel):
    row: int
    error: str


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    status: str
    source_type: str
    total_rows: int
    inserted_rows: int
    rejected_rows: int
    errors: list[RowError]
    error_message: str
    created_at: datetime
    finished_at: datetime | None
