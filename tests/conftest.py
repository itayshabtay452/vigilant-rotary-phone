import os

# Must be set before any app module is imported so database.py picks up the
# in-memory URL when it builds the engine at module level.
os.environ["DATABASE_URL"] = "sqlite://"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402

# A dedicated in-memory engine with StaticPool so every connection shares the
# same database within a test run. This prevents isolation issues that arise
# when SQLite creates a separate in-memory DB per connection.
_TEST_ENGINE = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_TestSession = sessionmaker(autocommit=False, autoflush=False, bind=_TEST_ENGINE)


def _override_get_db():
    db = _TestSession()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def _reset_database():
    """Create all tables before each test and drop them after."""
    Base.metadata.create_all(bind=_TEST_ENGINE)
    app.dependency_overrides[get_db] = _override_get_db
    yield
    Base.metadata.drop_all(bind=_TEST_ENGINE)
    app.dependency_overrides.clear()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)
