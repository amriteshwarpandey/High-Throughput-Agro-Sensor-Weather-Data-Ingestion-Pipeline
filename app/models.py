import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Index, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def _now():
    return datetime.now(timezone.utc)


class Region(Base):
    __tablename__ = "regions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    district: Mapped[str] = mapped_column(String(120), index=True)
    state: Mapped[str] = mapped_column(String(120), default="")


class SensorReading(Base):
    __tablename__ = "sensor_readings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    region_id: Mapped[int] = mapped_column(ForeignKey("regions.id", ondelete="CASCADE"))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    soil_organic_carbon: Mapped[float | None] = mapped_column(Float)  # %
    soil_moisture: Mapped[float | None] = mapped_column(Float)        # %
    soil_ph: Mapped[float | None] = mapped_column(Float)
    temperature_c: Mapped[float | None] = mapped_column(Float)
    rainfall_mm: Mapped[float | None] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(20), default="json")

    __table_args__ = (
        # Composite B-Tree: equality on region_id then range on recorded_at.
        Index("ix_reading_region_time", "region_id", "recorded_at"),
    )


class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    status: Mapped[str] = mapped_column(String(12), default="queued")  # queued|processing|completed|failed
    source_type: Mapped[str] = mapped_column(String(10))               # json | csv
    total_rows: Mapped[int] = mapped_column(Integer, default=0)
    inserted_rows: Mapped[int] = mapped_column(Integer, default=0)
    rejected_rows: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[list] = mapped_column(JSON, default=list)           # first N row errors
    error_message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
