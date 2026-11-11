import uuid
from datetime import datetime, timezone

from sqlalchemy import update

from . import redis_client
from .celery_app import celery_app
from .db import SessionLocal
from .ingestion import process_payload
from .models import IngestionJob


@celery_app.task(name="process_ingestion_job")
def process_ingestion_job(job_id: str) -> None:
    jid = uuid.UUID(job_id)
    with SessionLocal() as db:
        job = db.get(IngestionJob, jid)
        job.status = "processing"
        db.commit()

        raw = redis_client.fetch_payload(job_id)
        if raw is None:
            job.status, job.error_message = "failed", "Staged payload expired or missing"
            job.finished_at = datetime.now(timezone.utc)
            db.commit()
            return

        def progress(inserted, rejected):
            db.execute(update(IngestionJob).where(IngestionJob.id == jid)
                       .values(inserted_rows=inserted, rejected_rows=rejected))
            db.commit()

        try:
            result = process_payload(db, raw, job.source_type, progress)
        except Exception as exc:  # malformed payload etc.
            db.rollback()
            job = db.get(IngestionJob, jid)
            job.status, job.error_message = "failed", str(exc)[:1000]
        else:
            job.status = "completed"
            job.total_rows, job.inserted_rows = result["total"], result["inserted"]
            job.rejected_rows, job.errors = result["rejected"], result["errors"]
            redis_client.invalidate_analytics()  # new data -> never serve stale dashboards
        finally:
            redis_client.discard_payload(job_id)
        job.finished_at = datetime.now(timezone.utc)
        db.commit()
