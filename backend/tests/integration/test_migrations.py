from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine

from app.core.config import settings


def test_migration_creates_and_drops_schema(
    engine: Engine,
    monkeypatch,
) -> None:
    base_url = str(engine.url)
    database_name = "ticketing_migration_test"

    admin = create_engine(base_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        connection.execute(text(f"DROP DATABASE IF EXISTS {database_name}"))
        connection.execute(text(f"CREATE DATABASE {database_name}"))

    test_url = base_url.replace("/postgres?", f"/{database_name}?")
    monkeypatch.setattr(settings, "database_url", test_url)

    config = Config("alembic.ini")
    migration_engine = create_engine(test_url)

    try:
        command.upgrade(config, "head")
        tables = set(inspect(migration_engine).get_table_names())
        assert {
            "employees",
            "categories",
            "priorities",
            "tickets",
            "ticket_events",
            "attachments",
        } <= tables

        with migration_engine.connect() as connection:
            assert connection.execute(text("SELECT nextval('ticket_number_seq')")).scalar_one() == 1
    finally:
        migration_engine.dispose()
        command.downgrade(config, "base")
        with admin.connect() as connection:
            connection.execute(text(f"DROP DATABASE IF EXISTS {database_name}"))
        admin.dispose()
