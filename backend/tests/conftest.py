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
from sqlalchemy import select, text  # noqa: E402
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
    TicketTimelineEntry,
    TimelineEventType,
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
    if not IS_SQLITE:
        # La secuencia de numeración la crea la migración 0004; en las pruebas
        # el esquema se construye desde los modelos, así que se replica aquí.
        with engine.begin() as connection:
            connection.execute(
                text("CREATE SEQUENCE IF NOT EXISTS ticket_number_seq START 1 INCREMENT 1")
            )
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


# ---------------------------------------------------------------------------
# Fixtures de HU-05: cambio de estado, resolución y comentarios internos
# ---------------------------------------------------------------------------
@dataclass
class SeededWorkflow:
    """Usuarios y tickets deterministas para las pruebas de HU-05."""

    now: datetime
    users: dict[str, User]
    tickets: dict[str, Ticket]
    priority: Priority

    def headers_for(self, key: str, **kwargs) -> dict[str, str]:
        return {"Authorization": f"Bearer {make_token(self.users[key], **kwargs)}"}


@pytest.fixture()
def seeded_workflow(db: Session) -> SeededWorkflow:
    now = datetime.now(timezone.utc).replace(microsecond=0)

    def user(key: str, name: str, role: UserRole) -> User:
        row = User(
            id=uuid.uuid5(uuid.NAMESPACE_DNS, f"hu05-user-{key}"),
            name=name,
            email=f"hu05.{key}@example.com",
            role=role,
            team="Soporte" if role == UserRole.tecnico else None,
            is_active=True,
        )
        db.add(row)
        return row

    creator = user("creador", "Usuario Creador", UserRole.usuario)
    assigned = user("tecnico-asignado", "Técnica Asignada", UserRole.tecnico)
    unassigned = user(
        "tecnico-no-asignado", "Técnico No Asignado", UserRole.tecnico
    )
    supervisor = user("supervisor", "Supervisora", UserRole.supervisor)
    admin = user("admin", "Administrador", UserRole.admin)
    unrelated = user("sin-relacion", "Usuario Sin Relación", UserRole.usuario)

    priority = Priority(
        id=uuid.uuid5(uuid.NAMESPACE_DNS, "hu05-priority-3"),
        name="Media",
        level=3,
        color="#ca8a04",
        base_hours="24.00",
        is_active=True,
    )
    db.add(priority)

    # Los tickets finalizados del seed son legado anterior a la migración
    # 0003_ticket_timeline: no tienen resolución y deben quedar excluidos de
    # la aserción «resuelto ⇒ resolución» (se listan en la auditoría T050A).
    legacy_finalized_at = datetime(2026, 10, 15, 10, 0, tzinfo=timezone.utc)
    legacy_closed_at = datetime(2026, 10, 20, 10, 0, tzinfo=timezone.utc)
    created_at = datetime(2026, 9, 1, 9, 0, tzinfo=timezone.utc)
    tickets: dict[str, Ticket] = {}

    def add_ticket(
        key: str,
        number: str,
        status: TicketStatus,
        *,
        finalized_at: datetime | None = None,
        closed_at: datetime | None = None,
    ) -> Ticket:
        ticket = Ticket(
            id=uuid.uuid5(uuid.NAMESPACE_DNS, f"hu05-ticket-{key}"),
            number=number,
            title=f"Ticket de prueba {number}",
            description="Descripción de prueba.",
            status=status,
            priority_id=priority.id,
            creator_id=creator.id,
            assignee_id=assigned.id,
            created_at=created_at,
            sla_deadline=now + timedelta(hours=8),
            finalized_at=finalized_at,
            closed_at=closed_at,
            updated_at=now,
            sla_version="v1",
        )
        db.add(ticket)
        tickets[key] = ticket
        return ticket

    add_ticket("abierto", "TK-000501", TicketStatus.abierto)
    add_ticket("en_progreso", "TK-000502", TicketStatus.en_progreso)
    add_ticket(
        "pendiente_usuario", "TK-000503", TicketStatus.pendiente_usuario
    )
    add_ticket(
        "resuelto",
        "TK-000504",
        TicketStatus.resuelto,
        finalized_at=legacy_finalized_at,
    )
    add_ticket(
        "cerrado",
        "TK-000505",
        TicketStatus.cerrado,
        finalized_at=legacy_finalized_at,
        closed_at=legacy_closed_at,
    )

    db.commit()

    return SeededWorkflow(
        now=now,
        users={
            "creador": creator,
            "tecnico_asignado": assigned,
            "tecnico_no_asignado": unassigned,
            "supervisor": supervisor,
            "admin": admin,
            "sin_relacion": unrelated,
        },
        tickets=tickets,
        priority=priority,
    )


@pytest.fixture()
def workflow_seed(seeded_workflow: SeededWorkflow) -> SeededWorkflow:
    """Alias corto y explícito para las pruebas de HU-05."""

    return seeded_workflow


@pytest.fixture()
def user_creador(seeded_workflow: SeededWorkflow) -> User:
    return seeded_workflow.users["creador"]


@pytest.fixture()
def user_tecnico_asignado(seeded_workflow: SeededWorkflow) -> User:
    return seeded_workflow.users["tecnico_asignado"]


@pytest.fixture()
def user_tecnico_no_asignado(seeded_workflow: SeededWorkflow) -> User:
    return seeded_workflow.users["tecnico_no_asignado"]


@pytest.fixture()
def user_supervisor(seeded_workflow: SeededWorkflow) -> User:
    return seeded_workflow.users["supervisor"]


@pytest.fixture()
def user_admin(seeded_workflow: SeededWorkflow) -> User:
    return seeded_workflow.users["admin"]


@pytest.fixture()
def user_sin_relacion(seeded_workflow: SeededWorkflow) -> User:
    return seeded_workflow.users["sin_relacion"]


@pytest.fixture()
def ticket_abierto(seeded_workflow: SeededWorkflow) -> Ticket:
    return seeded_workflow.tickets["abierto"]


@pytest.fixture()
def ticket_en_progreso(seeded_workflow: SeededWorkflow) -> Ticket:
    return seeded_workflow.tickets["en_progreso"]


@pytest.fixture()
def ticket_pendiente_usuario(seeded_workflow: SeededWorkflow) -> Ticket:
    return seeded_workflow.tickets["pendiente_usuario"]


@pytest.fixture()
def ticket_resuelto(seeded_workflow: SeededWorkflow) -> Ticket:
    return seeded_workflow.tickets["resuelto"]


@pytest.fixture()
def ticket_cerrado(seeded_workflow: SeededWorkflow) -> Ticket:
    return seeded_workflow.tickets["cerrado"]


@pytest.fixture()
def auth_headers():
    """Devuelve las cabeceras Bearer de un usuario."""

    def _headers(user: User, **kwargs) -> dict[str, str]:
        return {"Authorization": f"Bearer {make_token(user, **kwargs)}"}

    return _headers


@pytest.fixture()
def timeline_entry_factory(db: Session):
    """Construye entradas válidas de la línea temporal para las pruebas."""

    def _factory(
        *,
        ticket: Ticket,
        author: User,
        event_type: TimelineEventType,
        body: str | None = None,
        from_status: TicketStatus | None = None,
        to_status: TicketStatus | None = None,
        is_internal: bool | None = None,
        created_at: datetime | None = None,
        event_order: int = 0,
        request_id: uuid.UUID | None = None,
        commit: bool = True,
    ) -> TicketTimelineEntry:
        if is_internal is None:
            is_internal = event_type == TimelineEventType.internal_comment
        entry = TicketTimelineEntry(
            ticket_id=ticket.id,
            event_type=event_type,
            from_status=from_status,
            to_status=to_status,
            body=body,
            is_internal=is_internal,
            author_id=author.id,
            author=author,
            created_at=created_at or datetime.now(timezone.utc),
            event_order=event_order,
            request_id=request_id or uuid.uuid4(),
        )
        db.add(entry)
        if commit:
            db.commit()
        return entry

    return _factory


__all__ = [
    "JWT_ALGORITHM",
    "JWT_SECRET",
    "SeededQueue",
    "SeededWorkflow",
    "auth_headers",
    "client",
    "db",
    "make_token",
    "seeded",
    "seeded_workflow",
    "select",
    "timeline_entry_factory",
]
