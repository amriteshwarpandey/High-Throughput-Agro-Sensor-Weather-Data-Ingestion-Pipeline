import uuid

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, UploadFile
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import analytics, redis_client
from .config import settings
from .db import get_db
from .models import IngestionJob, Region
from .schemas import JobAccepted, JobOut, RegionIn, RegionOut
from .tasks import process_ingestion_job

app = FastAPI(title="Agro Sensor Ingestion API", version="1.0.0")


def _enqueue(db: Session, raw: bytes, source_type: str) -> JobAccepted:
    """Stage raw bytes in Redis, queue the job, return immediately (no per-row work here)."""
    if len(raw) > settings.max_upload_bytes:
        raise HTTPException(413, "payload too large")
    job = IngestionJob(source_type=source_type)
    db.add(job)
    db.commit()
    jid = str(job.id)
    redis_client.stash_payload(jid, raw)
    process_ingestion_job.delay(jid)
    return JobAccepted(job_id=job.id, status="queued", status_url=f"/jobs/{jid}")


@app.post("/ingest/readings", response_model=JobAccepted, status_code=202)
async def ingest_json(request: Request, db: Session = Depends(get_db)):
    """JSON batch: a list of readings or {"readings": [...]}. Body is staged unparsed."""
    raw = await request.body()
    return await run_in_threadpool(_enqueue, db, raw, "json")


@app.post("/ingest/csv", response_model=JobAccepted, status_code=202)
async def ingest_csv(file: UploadFile, db: Session = Depends(get_db)):
    """CSV upload (multipart field `file`) of field-survey readings."""
    raw = await file.read()
    return await run_in_threadpool(_enqueue, db, raw, "csv")


@app.get("/jobs/{job_id}", response_model=JobOut)
def job_status(job_id: uuid.UUID, db: Session = Depends(get_db)):
    job = db.get(IngestionJob, job_id)
    if job is None:
        raise HTTPException(404, "job not found")
    return job


@app.post("/regions", response_model=RegionOut, status_code=201)
def create_region(body: RegionIn, db: Session = Depends(get_db)):
    region = Region(**body.model_dump())
    db.add(region)
    db.commit()
    return region


@app.get("/regions", response_model=list[RegionOut])
def list_regions(db: Session = Depends(get_db)):
    return db.scalars(select(Region).order_by(Region.id)).all()


def _respond(result, response: Response):
    data, hit = result
    response.headers["X-Cache"] = "HIT" if hit else "MISS"
    return data


Months = Query(6, ge=1, le=36, description="Look-back window in months")


@app.get("/analytics/districts/soil-carbon")
def district_soil_carbon(response: Response, months: int = Months, db: Session = Depends(get_db)):
    return _respond(analytics.district_soil_carbon(db, months), response)


def _require_region(db: Session, region_id: int):
    if db.get(Region, region_id) is None:
        raise HTTPException(404, "region not found")


@app.get("/analytics/regions/{region_id}/summary")
def region_summary(region_id: int, response: Response, months: int = Months, db: Session = Depends(get_db)):
    _require_region(db, region_id)
    return _respond(analytics.region_summary(db, region_id, months), response)


@app.get("/analytics/regions/{region_id}/monthly")
def region_monthly(region_id: int, response: Response, months: int = Months, db: Session = Depends(get_db)):
    _require_region(db, region_id)
    return _respond(analytics.region_monthly(db, region_id, months), response)


@app.get("/healthz")
def healthz():
    return {"ok": True}
