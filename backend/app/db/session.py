"""Engine y fábrica de sesiones de SQLAlchemy.

La conexión fuerza UTC cuando el motor es PostgreSQL. En SQLite (entorno de
pruebas local) se usa el mismo modelo con tipos genéricos de SQLAlchemy.
"""

from __future__ import annotations

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings


def _engine_kwargs(url: str) -> dict:
    if url.startswith("sqlite"):
        return {"connect_args": {"check_same_thread": False}}
    return {
        "pool_pre_ping": True,
        "connect_args": {"options": "-c timezone=UTC"},
    }


settings = get_settings()
engine: Engine = create_engine(settings.database_url, **_engine_kwargs(settings.database_url))

if engine.dialect.name == "sqlite":

    @event.listens_for(engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


def get_session():
    """Generador de sesión para dependencias de FastAPI."""

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
