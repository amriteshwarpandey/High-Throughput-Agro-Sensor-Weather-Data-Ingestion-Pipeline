"""Seed regions + synthetic readings.  python -m scripts.seed --rows 500000"""
import argparse
import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import insert, select

from app.db import SessionLocal
from app.models import Region, SensorReading

DISTRICTS = ["Pune", "Nashik", "Nagpur", "Satara", "Kolhapur", "Ludhiana", "Karnal", "Guntur"]

p = argparse.ArgumentParser()
p.add_argument("--regions", type=int, default=40)
p.add_argument("--rows", type=int, default=200_000)
p.add_argument("--days", type=int, default=365)
a = p.parse_args()

with SessionLocal() as db:
    if not db.scalar(select(Region.id).limit(1)):
        db.execute(insert(Region), [{"name": f"Block-{i}", "district": DISTRICTS[i % len(DISTRICTS)], "state": "IN"}
                                    for i in range(a.regions)])
        db.commit()
    ids = list(db.scalars(select(Region.id)))
    now, done = datetime.now(timezone.utc), 0
    while done < a.rows:
        n = min(10_000, a.rows - done)
        db.execute(insert(SensorReading), [{
            "region_id": random.choice(ids),
            "recorded_at": now - timedelta(minutes=random.randint(0, a.days * 1440)),
            "soil_organic_carbon": round(random.uniform(0.3, 4.5), 2),
            "soil_moisture": round(random.uniform(5, 60), 1),
            "soil_ph": round(random.uniform(5, 8.5), 2),
            "temperature_c": round(random.uniform(8, 42), 1),
            "rainfall_mm": round(random.uniform(0, 40), 1),
            "source": "seed"} for _ in range(n)])
        db.commit()
        done += n
    print(f"Seeded {done} readings across {len(ids)} regions")
