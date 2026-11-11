from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Postgres in Docker; SQLite fallback so tests/dev run with zero services.
    database_url: str = "sqlite:///./agro.db"
    # When unset: in-memory fake Redis + Celery tasks run inline (eager).
    redis_url: str | None = None

    analytics_cache_ttl: int = 15 * 60   # 15-minute TTL for dashboard queries
    payload_ttl: int = 60 * 60           # staged raw payloads expire after 1h
    bulk_batch_size: int = 5000
    max_upload_bytes: int = 100 * 1024 * 1024


settings = Settings()
