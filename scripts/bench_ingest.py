"""Measure 202 latency + worker time against a running stack.
python scripts/bench_ingest.py [rows=50000] [base_url=http://localhost:8000]
Needs at least one region (python -m scripts.seed).
"""
import json
import random
import sys
import time
from datetime import datetime, timedelta, timezone

import requests

rows = int(sys.argv[1]) if len(sys.argv) > 1 else 50_000
base = sys.argv[2] if len(sys.argv) > 2 else "http://localhost:8000"

regions = [r["id"] for r in requests.get(f"{base}/regions").json()]
now = datetime.now(timezone.utc)
body = json.dumps({"readings": [
    {"region_id": random.choice(regions),
     "recorded_at": (now - timedelta(minutes=random.randint(0, 200000))).isoformat(),
     "soil_organic_carbon": round(random.uniform(0.3, 4.5), 2),
     "soil_moisture": round(random.uniform(5, 60), 1)} for _ in range(rows)]})

t0 = time.perf_counter()
r = requests.post(f"{base}/ingest/readings", data=body, headers={"Content-Type": "application/json"})
print(f"{rows} rows -> HTTP {r.status_code} in {(time.perf_counter() - t0) * 1000:.0f} ms")
job = r.json()

t1 = time.perf_counter()
while (j := requests.get(f"{base}/jobs/{job['job_id']}").json())["status"] not in ("completed", "failed"):
    time.sleep(0.25)
print(f"worker finished in {time.perf_counter() - t1:.1f}s: {j['status']} "
      f"inserted={j['inserted_rows']} rejected={j['rejected_rows']}")
