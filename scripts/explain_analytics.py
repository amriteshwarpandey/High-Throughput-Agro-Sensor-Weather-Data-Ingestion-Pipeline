"""EXPLAIN ANALYZE the hot region/time query: forced seq scan vs composite index (Postgres).
python -m scripts.explain_analytics
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, text

from app.db import SessionLocal, engine
from app.models import Region

with SessionLocal() as db:
    rid = db.scalar(select(Region.id).limit(1))
    if rid is None:
        raise SystemExit("No data. Run: python -m scripts.seed")
    since = (datetime.now(timezone.utc) - timedelta(days=180)).isoformat()
    sql = (f"SELECT avg(soil_organic_carbon) FROM sensor_readings "
           f"WHERE region_id = {rid} AND recorded_at >= '{since}'")
    if engine.dialect.name == "postgresql":
        db.execute(text("SET enable_indexscan=off; SET enable_bitmapscan=off; SET enable_indexonlyscan=off"))
        print("\n=== WITHOUT index (forced sequential scan) ===")
        print("\n".join(r[0] for r in db.execute(text("EXPLAIN ANALYZE " + sql))))
        db.execute(text("RESET enable_indexscan; RESET enable_bitmapscan; RESET enable_indexonlyscan"))
        print("\n=== WITH composite index (region_id, recorded_at) ===")
        print("\n".join(r[0] for r in db.execute(text("EXPLAIN ANALYZE " + sql))))
    else:
        print("\n".join(str(r) for r in db.execute(text("EXPLAIN QUERY PLAN " + sql))))
