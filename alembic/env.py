from alembic import context

from app import models  # noqa: F401  (registers tables)
from app.db import Base, engine

target_metadata = Base.metadata

with engine.connect() as connection:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()
