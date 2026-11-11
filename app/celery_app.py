from celery import Celery

from .config import settings

celery_app = Celery(
    "agro",
    broker=settings.redis_url or "memory://",
    include=["app.tasks"],
)
celery_app.conf.task_always_eager = settings.redis_url is None  # inline when no Redis (dev/tests)
celery_app.conf.task_acks_late = True
