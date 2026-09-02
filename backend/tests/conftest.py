"""
Shared test fixtures.

Integration tests use a real SQLite in-memory database so they don't
need a running PostgreSQL instance.  External services (Qdrant, Gemini)
are mocked at the service layer.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base  # ensures all models are registered
from app.db.dependencies import get_db
from app.main import app

# ---------------------------------------------------------------------------
# In-memory SQLite engine (one shared connection so all queries see same data)
# ---------------------------------------------------------------------------
SQLITE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLITE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

# SQLite doesn't enforce foreign keys by default
@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_conn, _):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function", autouse=False)
def db_session():
    """Create all tables, yield a session, then drop everything."""
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    """
    FastAPI TestClient wired to the in-memory DB.
    External service calls (Qdrant, Gemini) must be mocked per-test.
    """

    def override_get_db():
        try:
            yield db_session
        finally:
            pass  # session lifecycle managed by db_session fixture

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def register_and_login(client: TestClient, email: str = "test@example.com") -> dict:
    """Register a user and return auth headers + user data."""
    resp = client.post(
        "/api/v1/auth/register",
        json={
            "organization_name": "Test Org",
            "name": "Test User",
            "email": email,
            "password": "testpassword123",
        },
    )
    assert resp.status_code == 201, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
