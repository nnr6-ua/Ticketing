from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pgserver
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

import app.models  # noqa: F401
from app.core.config import settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.seeds.seed import seed


@pytest.fixture(scope="session")
def pg_server(tmp_path_factory: pytest.TempPathFactory):
    data_dir = tmp_path_factory.mktemp("pgdata")
    server = pgserver.get_server(str(data_dir))
    yield server
    server.cleanup()


@pytest.fixture(scope="session")
def engine(pg_server) -> Iterator[Engine]:
    url = pg_server.get_uri().replace("postgresql://", "postgresql+psycopg://", 1)
    engine = create_engine(url, pool_pre_ping=True)
    Base.metadata.create_all(bind=engine)
    with engine.begin() as connection:
        connection.execute(
            text("CREATE SEQUENCE IF NOT EXISTS ticket_number_seq START 1 INCREMENT 1")
        )
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(engine: Engine) -> Iterator[Session]:
    with engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE TABLE attachments, ticket_events, tickets, "
                "priorities, categories, employees RESTART IDENTITY CASCADE"
            )
        )
        connection.execute(text("ALTER SEQUENCE ticket_number_seq RESTART WITH 1"))

    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    session = factory()
    seed(session)
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(
    db_session: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[TestClient]:
    attachments_dir = tmp_path / "attachments"
    monkeypatch.setattr(settings, "attachments_dir", attachments_dir)

    def override_get_db() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
