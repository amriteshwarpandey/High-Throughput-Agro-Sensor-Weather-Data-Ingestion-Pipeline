import json
from functools import lru_cache

import redis

from .config import settings


@lru_cache
def get_redis() -> redis.Redis:
    if settings.redis_url:
        return redis.Redis.from_url(settings.redis_url)
    import fakeredis  # dev/test fallback only
    return fakeredis.FakeRedis()


# ---- raw-payload staging: the Celery message carries only the job id ----
def stash_payload(job_id: str, raw: bytes) -> None:
    get_redis().set(f"payload:{job_id}", raw, ex=settings.payload_ttl)


def fetch_payload(job_id: str) -> bytes | None:
    return get_redis().get(f"payload:{job_id}")


def discard_payload(job_id: str) -> None:
    get_redis().delete(f"payload:{job_id}")


# ---- analytics cache with version-based invalidation ----
_VER_KEY = "analytics:version"


def cache_version() -> int:
    return int(get_redis().get(_VER_KEY) or 1)


def invalidate_analytics() -> None:
    r = get_redis()
    if r.get(_VER_KEY) is None:
        r.set(_VER_KEY, 2)
    else:
        r.incr(_VER_KEY)


def cached(name: str, params: tuple, compute):
    """Return (data, hit). Data is JSON-serialisable; TTL is 15 minutes."""
    r = get_redis()
    key = f"analytics:v{cache_version()}:{name}:{':'.join(map(str, params))}"
    hit = r.get(key)
    if hit is not None:
        return json.loads(hit), True
    data = compute()
    r.set(key, json.dumps(data), ex=settings.analytics_cache_ttl)
    return data, False
