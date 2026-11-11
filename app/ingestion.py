"""Parse, validate, clean and bulk-insert a raw payload (runs in the worker)."""
import csv
import io
import json
from datetime import datetime, timezone

from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from .config import settings
from .models import Region, SensorReading

METRIC_RANGES = {
    "soil_organic_carbon": (0, 100),
    "soil_moisture": (0, 100),
    "soil_ph": (0, 14),
    "temperature_c": (-60, 70),
    "rainfall_mm": (0, 2000),
}
MAX_ERRORS_KEPT = 100


def parse_rows(raw: bytes, source_type: str) -> list:
    text = raw.decode("utf-8-sig")
    if source_type == "csv":
        return list(csv.DictReader(io.StringIO(text)))
    data = json.loads(text)
    if isinstance(data, dict):
        data = data.get("readings", [])
    if not isinstance(data, list):
        raise ValueError("JSON payload must be a list or {'readings': [...]}")
    return data


def clean_row(row, valid_regions: set, source: str) -> dict:
    """Return a column dict or raise ValueError with a human-readable reason."""
    if not isinstance(row, dict):
        raise ValueError("row is not an object")
    try:
        region_id = int(str(row.get("region_id", "")).strip())
    except ValueError:
        raise ValueError("region_id missing or not an integer")
    if region_id not in valid_regions:
        raise ValueError(f"unknown region_id {region_id}")

    try:
        ts = datetime.fromisoformat(str(row.get("recorded_at", "")).strip())
    except ValueError:
        raise ValueError("recorded_at missing or not ISO-8601")
    ts = ts.replace(tzinfo=timezone.utc) if ts.tzinfo is None else ts.astimezone(timezone.utc)

    out = {"region_id": region_id, "recorded_at": ts, "source": source}
    for name, (lo, hi) in METRIC_RANGES.items():
        val = row.get(name)
        if val is None or (isinstance(val, str) and not val.strip()):
            out[name] = None
            continue
        try:
            num = float(val)
        except (TypeError, ValueError):
            raise ValueError(f"{name} is not a number")
        if not (lo <= num <= hi):
            raise ValueError(f"{name} {num} out of range [{lo}, {hi}]")
        out[name] = num
    if all(out[m] is None for m in METRIC_RANGES):
        raise ValueError("no metric values present")
    return out


def process_payload(db: Session, raw: bytes, source_type: str, progress=None) -> dict:
    rows = parse_rows(raw, source_type)
    valid_regions = set(db.scalars(select(Region.id)))
    inserted = rejected = 0
    errors: list = []
    batch: list = []

    def flush():
        nonlocal inserted
        if batch:
            db.execute(insert(SensorReading), batch)  # one executemany-style bulk insert
            db.commit()
            inserted += len(batch)
            batch.clear()
            if progress:
                progress(inserted, rejected)

    for i, row in enumerate(rows):
        try:
            batch.append(clean_row(row, valid_regions, source_type))
        except ValueError as exc:
            rejected += 1
            if len(errors) < MAX_ERRORS_KEPT:
                errors.append({"row": i, "error": str(exc)})
        if len(batch) >= settings.bulk_batch_size:
            flush()
    flush()
    return {"total": len(rows), "inserted": inserted, "rejected": rejected, "errors": errors}
