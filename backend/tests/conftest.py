"""Configuración común de las pruebas del backend.

Por defecto las pruebas usan SQLite en un archivo temporal para no depender de
un PostgreSQL local. Para validar el motor de producción, exporta
`TEST_DATABASE_URL` apuntando a una base de datos PostgreSQL 16 desechable;
entonces la suite completa (y los planes de consulta) se ejecutan allí.

El código de la aplicación es portable (funciones de ventana no, `COUNT` con
`CASE`, `NULLS LAST`, tipos genéricos de SQLAlchemy); la producción usa
PostgreSQL mediante `DATABASE_URL`.
"""

from __future__ import annotations

import os
import tempfile
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

TEMP_DIR = Path(tempfile.mkdtemp(prefix="hu04-tests-"))
DB_PATH = TEMP_DIR / "work_queue_test.sqlite3"

# Debe fijarse antes de importar cualquier módulo de `app`.
SQLITE_DATABASE_URL = f"sqlite+pysqlite:///{DB_PATH.as_posix()}"
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "").strip()
DATABASE_URL = TEST_DATABASE_URL or SQLITE_DATABASE_URL
IS_SQLITE = DATABASE_URL.startswith("sqlite")

os.environ["DATABASE_URL"] = DATABASE_URL
os.environ["JWT_SECRET"] = "test-secret"
os.environ["APP_ENV"] = "test"
os.environ["AUTH_DEV_STUB_ENABLED"] = "true"
os.environ.pop("AUTH_ISSUER", None)
os.environ.pop("AUTH_AUDIENCE", None)

import jwt  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app import models  # noqa: E402,F401
from app.db.base import Base  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import (  # noqa: E402
    Category,
    Priority,
    Ticket,
    TicketStatus,
    User,
    UserRole,
)

JWT_SECRET = "test-secret"
JWT_ALGORITHM = "HS256"


@pytest.fixture(scope="session", autouse=True)
def _cleanup_temp_dir():
    yield
    if not IS_SQLITE:
        return
    try:
        DB_PATH.unlink(missing_ok=True)
        TEMP_DIR.rmdir()
    except OSError:
        pass


@pytest.fixture()
def db() -> Session:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    # En PostgreSQL, recrear los tipos ENUM cambia su OID. Descartar las
    # conexiones del pool evita que queden planes preparados con el OID viejo.
    engine.dispose()
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client() -> TestClient:
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def make_token(
    user: User,
    *,
    secret: str = JWT_SECRET,
    expires_delta: timedelta = timedelta(hours=1),
    algorithm: str = JWT_ALGORITHM,
) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),
        "role": user.role.value,
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(payload, secret, algorithm=algorithm)


@pytest.fixture()
def auth():
    def _auth(user: User, **kwargs) -> dict[str, str]:
        return {"Authorization": f"Bearer {make_token(user, **kwargs)}"}

    return _auth


@dataclass
class SeededQueue:
    now: datetime
    users: dict[str, User]
    priorities: dict[int, Priority]
    categories: dict[str, Category]
    tickets: dict[str, Ticket]

    def header_for(self, key: str, **kwargs) -> dict[str, str]:
        return {"Authorization": f"Bearer {make_token(self.users[key], **kwargs)}"}


def _user(
    db: Session,
    key: str,
    name: str,
    email: str,
    role: UserRole,
) -> User:
    user = User(
        id=uuid.uuid5(uuid.NAMESPACE_DNS, f"hu04-{key}"),
        name=name,
        email=email,
        role=role,
        team="Soporte" if role == UserRole.tecnico else None,
        is_active=True,
    )
    db.add(user)
    return user


@pytest.fixture()
def seeded(db: Session) -> SeededQueue:
    """Datos equivalentes al seed de `quickstart.md` §3.3."""

    now = datetime.now(timezone.utc).replace(microsecond=0)

    tecnico_a = _user(db, "a", "Técnico A", "tecnico.a@example.com", UserRole.tecnico)
    tecnico_b = _user(db, "b", "Técnico B", "tecnico.b@example.com", UserRole.tecnico)
    tecnico_c = _user(db, "c", "Técnico C", "tecnico.c@example.com", UserRole.tecnico)
    tecnico_d = _user(db, "d", "Técnico D", "tecnico.d@example.com", UserRole.tecnico)
    supervisor = _user(
        db, "supervisor", "Supervisor", "supervisor@example.com", UserRole.supervisor
    )
    usuario = _user(db, "usuario", "Usuario", "usuario@example.com", UserRole.usuario)

    priority_specs = {
        1: ("Crítica", "#dc2626", "4.00"),
        2: ("Alta", "#ea580c", "8.00"),
        3: ("Media", "#ca8a04", "24.00"),
        4: ("Baja", "#16a34a", "72.00"),
    }
    priorities: dict[int, Priority] = {}
    for level, (name, color, base_hours) in priority_specs.items():
        priority = Priority(
            id=uuid.uuid5(uuid.NAMESPACE_DNS, f"hu04-priority-{level}"),
            name=name,
            level=level,
            color=color,
            base_hours=base_hours,
            is_active=True,
        )
        db.add(priority)
        priorities[level] = priority

    categories: dict[str, Category] = {}
    for key, name in (("red", "Red"), ("hardware", "Hardware"), ("software", "Software")):
        category = Category(
            id=uuid.uuid5(uuid.NAMESPACE_DNS, f"hu04-category-{key}"),
            name=name,
            is_active=True,
        )
        db.add(category)
        categories[key] = category

    tickets: dict[str, Ticket] = {}

    def add_ticket(
        key: str,
        number: str,
        title: str,
        status: TicketStatus,
        priority_level: int,
        category_key: str | None,
        assignee: User,
        created_delta: timedelta,
        deadline_delta: timedelta | None,
        finalized_delta: timedelta | None = None,
    ) -> Ticket:
        ticket = Ticket(
            id=uuid.uuid5(uuid.NAMESPACE_DNS, f"hu04-ticket-{number}"),
            number=number,
            title=title,
            status=status,
            priority_id=priorities[priority_level].id,
            category_id=categories[category_key].id if category_key else None,
            creator_id=assignee.id,
            assignee_id=assignee.id,
            created_at=now + created_delta,
            sla_deadline=now + deadline_delta if deadline_delta else None,
            finalized_at=now + finalized_delta if finalized_delta else None,
            closed_at=now + finalized_delta if finalized_delta else None,
            updated_at=now + finalized_delta if finalized_delta else now + created_delta,
            sla_version="v1",
        )
        db.add(ticket)
        tickets[number] = ticket
        return ticket

    add_ticket(
        "critica_vencida",
        "TK-000101",
        "No puedo acceder a la VPN desde casa",
        TicketStatus.en_progreso,
        1,
        "red",
        tecnico_a,
        timedelta(hours=-6),
        timedelta(hours=-2),
    )
    add_ticket(
        "critica_30min",
        "TK-000102",
        "Caída intermitente de la red wifi",
        TicketStatus.abierto,
        1,
        "red",
        tecnico_a,
        timedelta(minutes=-10),
        timedelta(minutes=20),
    )
    add_ticket(
        "alta_10min",
        "TK-000103",
        "El portátil no arranca tras la actualización",
        TicketStatus.en_progreso,
        2,
        "hardware",
        tecnico_a,
        timedelta(hours=-3, minutes=-50),
        timedelta(minutes=10),
    )
    add_ticket(
        "alta_sin_sla",
        "TK-000104",
        "Solicitud de alta en el gestor documental",
        TicketStatus.pendiente_usuario,
        2,
        None,
        tecnico_a,
        timedelta(hours=-1),
        None,
    )
    add_ticket(
        "media_en_plazo",
        "TK-000105",
        "Error al generar el informe mensual",
        TicketStatus.abierto,
        3,
        "software",
        tecnico_a,
        timedelta(hours=-4),
        timedelta(hours=20),
    )
    add_ticket(
        "resuelto_met",
        "TK-000106",
        "Restablecer contraseña del correo corporativo",
        TicketStatus.resuelto,
        3,
        "software",
        tecnico_a,
        timedelta(hours=-3),
        timedelta(hours=-1),
        timedelta(hours=-2),
    )
    add_ticket(
        "cerrado_breached",
        "TK-000107",
        "Sustitución de teclado dañado",
        TicketStatus.cerrado,
        1,
        "hardware",
        tecnico_a,
        timedelta(days=-2),
        timedelta(days=-1),
        timedelta(hours=-1),
    )

    add_ticket(
        "b_vencida",
        "TK-000201",
        "Incidencia del servidor de impresión",
        TicketStatus.en_progreso,
        1,
        "red",
        tecnico_b,
        timedelta(hours=-5),
        timedelta(hours=-1),
    )
    add_ticket(
        "b_media",
        "TK-000202",
        "Instalación de lector de tarjetas",
        TicketStatus.abierto,
        3,
        "hardware",
        tecnico_b,
        timedelta(hours=-2),
        timedelta(hours=10),
    )
    add_ticket(
        "c_resuelto",
        "TK-000301",
        "Migración de buzón completada",
        TicketStatus.resuelto,
        4,
        "software",
        tecnico_c,
        timedelta(hours=-8),
        timedelta(hours=-4),
        timedelta(hours=-6),
    )

    db.commit()

    return SeededQueue(
        now=now,
        users={
            "a": tecnico_a,
            "b": tecnico_b,
            "c": tecnico_c,
            "d": tecnico_d,
            "supervisor": supervisor,
            "usuario": usuario,
        },
        priorities=priorities,
        categories=categories,
        tickets=tickets,
    )


@pytest.fixture()
def seeded_client(client: TestClient, seeded: SeededQueue) -> SimpleNamespace:
    return SimpleNamespace(client=client, seed=seeded)


def refresh(session: Session, instance):
    session.refresh(instance)
    return instance


__all__ = [
    "JWT_ALGORITHM",
    "JWT_SECRET",
    "SeededQueue",
    "client",
    "db",
    "make_token",
    "seeded",
    "select",
]
