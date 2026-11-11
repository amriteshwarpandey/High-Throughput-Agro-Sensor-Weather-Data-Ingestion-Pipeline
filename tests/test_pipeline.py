import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from app.db import SessionLocal
from app.models import SensorReading


def _row(region, **kw):
    base = {"region_id": region["id"], "recorded_at": (datetime.now(timezone.utc) - timedelta(days=5)).isoformat(),
            "soil_organic_carbon": 2.0, "soil_moisture": 30}
    base.update(kw)
    return base


def _post(client, payload):
    return client.post("/ingest/readings", content=json.dumps(payload),
                       headers={"Content-Type": "application/json"})


def _count():
    with SessionLocal() as db:
        return db.scalar(select(func.count(SensorReading.id)))


def test_json_ingest_returns_202_and_bulk_inserts(client, region):
    r = _post(client, {"readings": [_row(region) for _ in range(250)]})
    assert r.status_code == 202
    job = client.get(r.json()["status_url"]).json()  # eager Celery in tests
    assert job["status"] == "completed"
    assert (job["inserted_rows"], job["rejected_rows"]) == (250, 0)
    assert _count() == 250


def test_invalid_rows_are_rejected_and_reported(client, region):
    rows = [_row(region), _row(region, soil_ph=99), _row(region, region_id=9999), {"region_id": region["id"]}]
    job = client.get(_post(client, rows).json()["status_url"]).json()
    assert (job["inserted_rows"], job["rejected_rows"]) == (1, 3)
    assert len(job["errors"]) == 3


def test_csv_ingest(client, region):
    ts = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    csv_data = f"region_id,recorded_at,soil_organic_carbon,soil_ph\n{region['id']},{ts},1.5,6.5\n{region['id']},{ts},,\n"
    r = client.post("/ingest/csv", files={"file": ("s.csv", csv_data.encode(), "text/csv")})
    assert r.status_code == 202
    job = client.get(r.json()["status_url"]).json()
    assert (job["inserted_rows"], job["rejected_rows"]) == (1, 1)


def test_malformed_json_marks_job_failed(client, region):
    r = client.post("/ingest/readings", content=b"not json", headers={"Content-Type": "application/json"})
    assert r.status_code == 202
    assert client.get(r.json()["status_url"]).json()["status"] == "failed"


def test_analytics_cached_then_invalidated_by_new_ingest(client, region):
    _post(client, [_row(region, soil_organic_carbon=2.0)])
    url = "/analytics/districts/soil-carbon?months=6"
    first = client.get(url)
    assert first.headers["X-Cache"] == "MISS" and first.json()[0]["avg_soil_organic_carbon"] == 2.0
    assert client.get(url).headers["X-Cache"] == "HIT"

    _post(client, [_row(region, soil_organic_carbon=4.0)])
    after = client.get(url)
    assert after.headers["X-Cache"] == "MISS"  # version bump invalidated stale entry
    assert after.json()[0]["avg_soil_organic_carbon"] == 3.0


def test_region_endpoints(client, region):
    _post(client, [_row(region)])
    assert client.get(f"/analytics/regions/{region['id']}/summary").json()["readings"] == 1
    assert len(client.get(f"/analytics/regions/{region['id']}/monthly").json()) == 1
    assert client.get("/analytics/regions/424242/summary").status_code == 404


def test_composite_index_declared():
    idx = {i.name: [c.name for c in i.columns] for i in SensorReading.__table__.indexes}
    assert idx["ix_reading_region_time"] == ["region_id", "recorded_at"]
