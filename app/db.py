from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings

_kwargs = {"connect_args": {"check_same_thread": False}} if settings.database_url.startswith("sqlite") else {
    "pool_size": 10, "max_overflow": 20, "pool_pre_ping": True}
engine = create_engine(settings.database_url, **_kwargs)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    with SessionLocal() as session:
        yield session
