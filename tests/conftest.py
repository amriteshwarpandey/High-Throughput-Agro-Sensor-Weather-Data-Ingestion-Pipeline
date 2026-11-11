import os
import tempfile

# Must be set before app modules import settings.
_db = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_db}"
os.environ.pop("REDIS_URL", None)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db import Base, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.redis_client import get_redis  # noqa: E402


@pytest.fixture(autouse=True)
def _fresh_state():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    get_redis().flushall()
    yield


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def region(client):
    return client.post("/regions", json={"name": "Block-1", "district": "Pune", "state": "MH"}).json()
