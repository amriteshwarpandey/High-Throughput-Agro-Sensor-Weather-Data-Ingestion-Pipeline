# High-Throughput Agro-Sensor & Weather Data Ingestion Pipeline

FastAPI service that accepts large batches of soil/climate readings, stages them in Redis, bulk-inserts them
into PostgreSQL via a Celery worker, and serves cached, indexed analytics.

## Stack
Python 3.12 · FastAPI + Pydantic v2 · SQLAlchemy 2.0 + Alembic · PostgreSQL 16 (psycopg 3) · Redis 7 · Celery 5 ·
Gunicorn + Uvicorn workers · Docker Compose · pytest · Locust

## Architecture
```
client ──POST batch──> FastAPI ──stash raw bytes──> Redis ──job_id──> Celery worker
          <── 202 + job_id (ms)                                        │ validate / clean
                                                                       │ bulk insert (5k chunks)
client ──GET /jobs/{id}── progress, counts, row errors <───────────────┘ bump cache version
client ──GET analytics──> Redis cache (15 min TTL) ──miss──> Postgres (index on region_id, recorded_at)
```

## Run
```bash
docker compose up --build                                    # api, worker, postgres, redis
docker compose exec api python -m scripts.seed --rows 500000 # synthetic data
docker compose exec api python -m scripts.explain_analytics  # EXPLAIN ANALYZE: seq scan vs index
python scripts/bench_ingest.py 50000                         # 202 latency + worker time
locust -f scripts/locustfile.py --host http://localhost:8000 # read load test
```
Swagger UI: http://localhost:8000/docs

With no `DATABASE_URL` / `REDIS_URL`, it falls back to SQLite, an in-memory fake Redis and inline Celery, so
`pip install -r requirements.txt && pytest` needs no services. Local dev: `alembic upgrade head && uvicorn app.main:app --reload`.

## Endpoints
| Method | Path | Purpose |
|---|---|---|
| POST | `/ingest/readings` | JSON batch (`[...]` or `{"readings": [...]}`) → `202 {job_id}` |
| POST | `/ingest/csv` | multipart `file` CSV upload → `202 {job_id}` |
| GET | `/jobs/{id}` | status, inserted/rejected counts, first 100 row errors |
| POST/GET | `/regions` | create / list regions |
| GET | `/analytics/districts/soil-carbon?months=6` | avg soil organic carbon per district |
| GET | `/analytics/regions/{id}/summary?months=6` | avg metrics for a region |
| GET | `/analytics/regions/{id}/monthly?months=6` | monthly trend |

Row fields: `region_id`, `recorded_at` (ISO-8601), and any of `soil_organic_carbon`, `soil_moisture`,
`soil_ph`, `temperature_c`, `rainfall_mm` (range-checked; empty values become NULL).

## Design decisions
- **The request does no per-row work.** The raw body is staged in Redis; only the job id goes to Celery.
- **Bulk inserts** in 5,000-row batches via SQLAlchemy 2.0 `insert()` with a list of dicts.
- **Composite B-tree index `(region_id, recorded_at)`** matches equality-then-range filters.
- **Version-counter cache invalidation:** a completed ingest bumps a version in every cache key, so stale
  dashboards are impossible and no key scanning is needed. Responses carry `X-Cache: HIT|MISS`.
- **Sync SQLAlchemy in threadpool** keeps the worker and API sharing one data layer; ingestion endpoints are `async`
  only for reading the body.

## Getting your own numbers
Compare against a naive version that inserts rows inside the request, and capture `explain_analytics` output
before/after. Quote your measured figures in interviews.
