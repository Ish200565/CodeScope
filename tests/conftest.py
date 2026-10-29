import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app import models  # noqa: F401
from app.config import settings
from app.db import Base, get_db
from app.main import app

TEST_DB_URL = settings.database_url.rsplit("/", 1)[0] + "/codescope_test"
engine = create_engine(TEST_DB_URL)
TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@pytest.fixture(scope="session", autouse=True)
def create_tables():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


@pytest.fixture(autouse=True)
def clean_tables():
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE runs, step_runs RESTART IDENTITY CASCADE"))
    yield


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(settings, "github_webhook_secret", "testsecret")

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()

@pytest.fixture(autouse=True)
def no_real_enqueue(monkeypatch):
    from app.worker import tasks
    monkeypatch.setattr(tasks.process_run, "delay", lambda *a, **k: None)