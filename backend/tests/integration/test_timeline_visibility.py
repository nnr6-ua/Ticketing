"""Pruebas de visibilidad y orden de la línea temporal (HU-05, US3)."""

from __future__ import annotations

import importlib.util
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import and_, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import engine

from app.models import (
    Ticket,
    TicketStatus,
    TicketTimelineEntry,
    TimelineEventType,
    User,
    UserRole,
)
from app.services.ticket_state_machine import allowed_transitions
from app.services.ticket_timeline import serialize_entry

API = "/api/v1/tickets"
MIGRATION_CUTOFF = datetime(2026, 11, 2, tzinfo=timezone.utc)
UTC = timezone.utc


def _url(ticket: Ticket, suffix: str) -> str:
    return f"{API}/{ticket.id}/{suffix}"


def _timeline(client, ticket: Ticket, headers: dict[str, str], **params):
    return client.get(_url(ticket, "timeline"), headers=headers, params=params)


def _workflow(client, ticket: Ticket, headers: dict[str, str]):
    return client.get(_url(ticket, "workflow"), headers=headers)


def _types(payload: dict) -> list[str]:
    return [item["type"] for item in payload["items"]]


def _entities(
    ticket: Ticket, author_key: str, seeded_workflow
) -> list[TicketTimelineEntry]:
    """Entradas públicas e internas con orden cronológico conocido."""

    author = seeded_workflow.users[author_key]
    base = seeded_workflow.now - timedelta(hours=3)
    return [
        TicketTimelineEntry(
            id=uuid.uuid5(uuid.NAMESPACE_DNS, f"hu05-visible-status-{ticket.id}"),
            ticket_id=ticket.id,
            event_type=TimelineEventType.status_change,
            from_status=TicketStatus.abierto,
            to_status=TicketStatus.en_progreso,
            body=None,
            is_internal=False,
            author_id=author.id,
            created_at=base,
            event_order=0,
            request_id=uuid.uuid5(
                uuid.NAMESPACE_DNS, f"hu05-visible-status-req-{ticket.id}"
            ),
        ),
        TicketTimelineEntry(
            id=uuid.uuid5(uuid.NAMESPACE_DNS, f"hu05-visible-resolution-{ticket.id}"),
            ticket_id=ticket.id,
            event_type=TimelineEventType.resolution,
            from_status=None,
            to_status=TicketStatus.resuelto,
            body="Resolución documentada.",
            is_internal=False,
            author_id=author.id,
            created_at=base + timedelta(minutes=1),
            event_order=1,
            request_id=uuid.uuid5(
                uuid.NAMESPACE_DNS, f"hu05-visible-resolution-req-{ticket.id}"
            ),
        ),
        TicketTimelineEntry(
            id=uuid.uuid5(uuid.NAMESPACE_DNS, f"hu05-visible-internal-{ticket.id}"),
            ticket_id=ticket.id,
            event_type=TimelineEventType.internal_comment,
            from_status=None,
            to_status=None,
            body="Nota solo para el equipo.",
            is_internal=True,
            author_id=author.id,
            created_at=base + timedelta(minutes=2),
            event_order=0,
            request_id=uuid.uuid5(
                uuid.NAMESPACE_DNS, f"hu05-visible-internal-req-{ticket.id}"
            ),
        ),
    ]


def _seed_entities(db: Session, ticket: Ticket, seeded_workflow) -> None:
    for entry in _entities(ticket, "tecnico_asignado", seeded_workflow):
        db.add(entry)
    db.commit()


# ---------------------------------------------------------------------------
# Visibilidad por rol y relación
# ---------------------------------------------------------------------------
def test_creator_only_sees_public_entries(
    client, db, seeded_workflow, auth_headers
) -> None:
    ticket = seeded_workflow.tickets["en_progreso"]
    _seed_entities(db, ticket, seeded_workflow)
    headers = auth_headers(seeded_workflow.users["creador"])

    timeline = _timeline(client, ticket, headers)
    workflow = _workflow(client, ticket, headers)

    assert timeline.status_code == 200, timeline.text
    payload = timeline.json()
    assert _types(payload) == ["status_change", "resolution"]
    assert all(item["is_internal"] is False for item in payload["items"])
    assert all(item["body"] != "Nota solo para el equipo." for item in payload["items"])
    assert payload["pagination"]["total_items"] == 2

    assert workflow.status_code == 200, workflow.text
    capabilities = workflow.json()
    assert capabilities["can_view_internal"] is False
    assert capabilities["can_comment_internally"] is False
    assert capabilities["can_change_status"] is False


def test_unassigned_technician_only_sees_public_entries(
    client, db, seeded_workflow, auth_headers
) -> None:
    ticket = seeded_workflow.tickets["en_progreso"]
    _seed_entities(db, ticket, seeded_workflow)
    headers = auth_headers(seeded_workflow.users["tecnico_no_asignado"])

    timeline = _timeline(client, ticket, headers)
    workflow = _workflow(client, ticket, headers)

    assert timeline.status_code == 200, timeline.text
    assert _types(timeline.json()) == ["status_change", "resolution"]
    assert timeline.json()["pagination"]["total_items"] == 2

    capabilities = workflow.json()
    assert capabilities["can_view_internal"] is False
    assert capabilities["can_comment_internally"] is False


@pytest.mark.parametrize(
    "key, can_change", [("tecnico_asignado", True), ("supervisor", False), ("admin", False)]
)
def test_creator_with_operative_role_only_sees_public_entries(
    client, db, seeded_workflow, auth_headers, key, can_change
) -> None:
    """US2/AC3: ser creador limita la visibilidad aunque tenga rol operativo."""

    ticket = seeded_workflow.tickets["en_progreso"]
    _seed_entities(db, ticket, seeded_workflow)
    creator = seeded_workflow.users[key]
    ticket.creator_id = creator.id
    db.commit()
    headers = auth_headers(creator)

    timeline = _timeline(client, ticket, headers)
    workflow = _workflow(client, ticket, headers)

    assert timeline.status_code == 200, timeline.text
    assert _types(timeline.json()) == ["status_change", "resolution"]
    assert all(item["is_internal"] is False for item in timeline.json()["items"])
    assert all(item["body"] != "Nota solo para el equipo." for item in timeline.json()["items"])
    assert timeline.json()["pagination"]["total_items"] == 2

    assert workflow.status_code == 200, workflow.text
    capabilities = workflow.json()
    assert capabilities["can_view_internal"] is False
    assert capabilities["can_change_status"] is can_change


@pytest.mark.parametrize(
    "key, can_comment", [("tecnico_asignado", True), ("supervisor", False), ("admin", False)]
)
def test_internal_entries_visible_to_authorised_viewers(
    client, db, seeded_workflow, auth_headers, key, can_comment
) -> None:
    ticket = seeded_workflow.tickets["en_progreso"]
    _seed_entities(db, ticket, seeded_workflow)
    headers = auth_headers(seeded_workflow.users[key])

    timeline = _timeline(client, ticket, headers)
    workflow = _workflow(client, ticket, headers)

    assert timeline.status_code == 200, timeline.text
    payload = timeline.json()
    assert _types(payload) == ["status_change", "resolution", "internal_comment"]
    internal = payload["items"][-1]
    assert internal["is_internal"] is True
    assert internal["body"] == "Nota solo para el equipo."
    assert payload["pagination"]["total_items"] == 3

    capabilities = workflow.json()
    assert capabilities["can_view_internal"] is True
    assert capabilities["can_comment_internally"] is can_comment


def test_reassignment_revokes_previous_assignee_internal_access(
    client, db, seeded_workflow, auth_headers
) -> None:
    ticket = seeded_workflow.tickets["en_progreso"]
    _seed_entities(db, ticket, seeded_workflow)
    previous = seeded_workflow.users["tecnico_asignado"]
    new_assignee = seeded_workflow.users["tecnico_no_asignado"]
    previous_headers = auth_headers(previous)
    new_headers = auth_headers(new_assignee)

    before = _timeline(client, ticket, previous_headers)
    assert _types(before.json()) == [
        "status_change",
        "resolution",
        "internal_comment",
    ]

    ticket.assignee_id = new_assignee.id
    db.commit()

    after = _timeline(client, ticket, previous_headers)
    assert after.status_code == 200, after.text
    assert _types(after.json()) == ["status_change", "resolution"]
    assert after.json()["pagination"]["total_items"] == 2

    assert _workflow(client, ticket, previous_headers).json()["can_view_internal"] is False
    assert _workflow(client, ticket, new_headers).json()["can_view_internal"] is True
    assert _types(_timeline(client, ticket, new_headers).json()) == [
        "status_change",
        "resolution",
        "internal_comment",
    ]


def test_unrelated_user_gets_not_found_without_timeline_data(
    client, db, seeded_workflow, auth_headers
) -> None:
    ticket = seeded_workflow.tickets["en_progreso"]
    _seed_entities(db, ticket, seeded_workflow)
    headers = auth_headers(seeded_workflow.users["sin_relacion"])

    workflow = _workflow(client, ticket, headers)
    timeline = _timeline(client, ticket, headers)

    assert workflow.status_code == 404, workflow.text
    assert workflow.json()["detail"]["code"] == "ticket_not_found"
    assert timeline.status_code == 404, timeline.text
    payload = timeline.json()
    assert payload["detail"]["code"] == "ticket_not_found"
    assert "items" not in payload


# ---------------------------------------------------------------------------
# Orden y paginación
# ---------------------------------------------------------------------------
def test_timeline_orders_by_created_at_event_order_and_id(
    client, db, seeded_workflow, auth_headers
) -> None:
    ticket = seeded_workflow.tickets["en_progreso"]
    author = seeded_workflow.users["tecnico_asignado"]
    base = seeded_workflow.now - timedelta(hours=1)

    first_id = uuid.uuid5(uuid.NAMESPACE_DNS, "hu05-order-oldest")
    same_time_ids = sorted(
        [
            uuid.uuid5(uuid.NAMESPACE_DNS, "hu05-order-tie-a"),
            uuid.uuid5(uuid.NAMESPACE_DNS, "hu05-order-tie-b"),
        ]
    )

    def status_entry(entry_id, created_at, order, suffix):
        return TicketTimelineEntry(
            id=entry_id,
            ticket_id=ticket.id,
            event_type=TimelineEventType.status_change,
            from_status=TicketStatus.abierto,
            to_status=TicketStatus.en_progreso,
            body=None,
            is_internal=False,
            author_id=author.id,
            created_at=created_at,
            event_order=order,
            request_id=uuid.uuid5(uuid.NAMESPACE_DNS, f"hu05-order-req-{suffix}"),
        )

    db.add(status_entry(first_id, base, 0, "oldest"))
    db.add(status_entry(same_time_ids[0], base + timedelta(minutes=5), 1, "tie-a"))
    db.add(status_entry(same_time_ids[1], base + timedelta(minutes=5), 1, "tie-b"))
    db.commit()

    response = _timeline(client, ticket, auth_headers(author))

    assert response.status_code == 200, response.text
    payload = response.json()
    assert [item["id"] for item in payload["items"]] == [
        str(first_id),
        str(same_time_ids[0]),
        str(same_time_ids[1]),
    ]
    assert payload["pagination"] == {
        "page": 1,
        "page_size": 50,
        "total_items": 3,
        "total_pages": 1,
        "has_next": False,
        "has_previous": False,
    }


def test_timeline_pagination_slices_visible_entries(
    client, db, seeded_workflow, auth_headers
) -> None:
    ticket = seeded_workflow.tickets["en_progreso"]
    _seed_entities(db, ticket, seeded_workflow)
    headers = auth_headers(seeded_workflow.users["creador"])

    first_page = _timeline(client, ticket, headers, page=1, page_size=1)
    second_page = _timeline(client, ticket, headers, page=2, page_size=1)

    assert first_page.status_code == 200, first_page.text
    assert second_page.status_code == 200, second_page.text
    assert _types(first_page.json()) == ["status_change"]
    assert _types(second_page.json()) == ["resolution"]
    assert first_page.json()["pagination"] == {
        "page": 1,
        "page_size": 1,
        "total_items": 2,
        "total_pages": 2,
        "has_next": True,
        "has_previous": False,
    }
    assert second_page.json()["pagination"]["has_previous"] is True
    assert second_page.json()["pagination"]["has_next"] is False


# ---------------------------------------------------------------------------
# Invariantes (T050)
# ---------------------------------------------------------------------------
def _resolved_without_resolution_since_migration(
    db: Session,
) -> list[tuple[uuid.UUID, str]]:
    statement = (
        select(Ticket.id, Ticket.number)
        .outerjoin(
            TicketTimelineEntry,
            and_(
                TicketTimelineEntry.ticket_id == Ticket.id,
                TicketTimelineEntry.event_type == TimelineEventType.resolution,
            ),
        )
        .where(
            Ticket.status == TicketStatus.resuelto,
            Ticket.finalized_at.is_not(None),
            Ticket.finalized_at >= MIGRATION_CUTOFF,
            TicketTimelineEntry.id.is_(None),
        )
    )
    return [(row[0], row[1]) for row in db.execute(statement).all()]


def test_timeline_invariants_hold(
    client, db, seeded_workflow, auth_headers
) -> None:
    ticket = seeded_workflow.tickets["en_progreso"]
    headers = auth_headers(seeded_workflow.users["tecnico_asignado"])
    workflow = _workflow(client, ticket, headers).json()

    response = client.post(
        _url(ticket, "status-transitions"),
        headers=headers,
        json={
            "target_status": "resuelto",
            "resolution": "  Solución verificada.  ",
            "expected_updated_at": workflow["ticket"]["updated_at"],
            "request_id": str(uuid.uuid4()),
        },
    )
    assert response.status_code == 200, response.text

    db.expire_all()
    assert _resolved_without_resolution_since_migration(db) == []

    last_status_change = db.scalars(
        select(TicketTimelineEntry)
        .where(
            TicketTimelineEntry.ticket_id == ticket.id,
            TicketTimelineEntry.event_type == TimelineEventType.status_change,
        )
        .order_by(
            TicketTimelineEntry.created_at.desc(),
            TicketTimelineEntry.event_order.desc(),
            TicketTimelineEntry.id.desc(),
        )
    ).unique().first()
    refreshed = db.get(Ticket, ticket.id)
    assert last_status_change is not None
    assert last_status_change.to_status == refreshed.status

    for row in db.scalars(select(Ticket)).all():
        if row.status in (TicketStatus.resuelto, TicketStatus.cerrado):
            assert row.finalized_at is not None, row.number
        else:
            assert row.finalized_at is None, row.number
        if row.closed_at is not None:
            assert row.status == TicketStatus.cerrado, row.number


def test_timeline_entry_ticket_relationship(
    db, seeded_workflow, timeline_entry_factory
) -> None:
    """`TicketTimelineEntry.ticket` carga el ticket relacionado (data-model §3.4)."""

    ticket = seeded_workflow.tickets["en_progreso"]
    author = seeded_workflow.users["tecnico_asignado"]
    entry = timeline_entry_factory(
        ticket=ticket,
        author=author,
        event_type=TimelineEventType.status_change,
        from_status=TicketStatus.abierto,
        to_status=TicketStatus.en_progreso,
    )

    db.expire_all()
    loaded = db.get(TicketTimelineEntry, entry.id)
    assert loaded is not None
    assert loaded.ticket.id == ticket.id
    assert loaded.ticket.number == ticket.number


def test_creator_sees_public_comment_with_author_and_date(
    client, db, seeded_workflow, auth_headers
) -> None:
    """US2/AC3: el creador ve comentarios públicos con autor y fecha, nunca internos."""

    ticket = seeded_workflow.tickets["en_progreso"]
    author = seeded_workflow.users["tecnico_asignado"]
    created_at = seeded_workflow.now - timedelta(minutes=30)
    public_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"hu02-public-comment-{ticket.id}")
    internal_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"hu02-internal-comment-{ticket.id}")
    db.add_all(
        [
            TicketTimelineEntry(
                id=public_id,
                ticket_id=ticket.id,
                event_type=TimelineEventType.internal_comment,
                from_status=None,
                to_status=None,
                body="Comentario público del técnico.",
                is_internal=False,
                author_id=author.id,
                created_at=created_at,
                event_order=0,
                request_id=uuid.uuid5(uuid.NAMESPACE_DNS, f"hu02-public-req-{ticket.id}"),
            ),
            TicketTimelineEntry(
                id=internal_id,
                ticket_id=ticket.id,
                event_type=TimelineEventType.internal_comment,
                from_status=None,
                to_status=None,
                body="Nota solo para el equipo.",
                is_internal=True,
                author_id=author.id,
                created_at=created_at + timedelta(minutes=1),
                event_order=0,
                request_id=uuid.uuid5(
                    uuid.NAMESPACE_DNS, f"hu02-internal-req-{ticket.id}"
                ),
            ),
        ]
    )
    db.commit()

    response = _timeline(client, ticket, auth_headers(seeded_workflow.users["creador"]))

    assert response.status_code == 200, response.text
    items = response.json()["items"]
    public = next(
        item for item in items if item["body"] == "Comentario público del técnico."
    )
    assert public["type"] == "internal_comment"
    assert public["is_internal"] is False
    assert public["author"]["id"] == str(author.id)
    assert public["author"]["name"] == author.name
    assert public["author"]["role"] == author.role.value
    assert (
        datetime.fromisoformat(public["created_at"].replace("Z", "+00:00"))
        == created_at
    )
    assert all(item["is_internal"] is False for item in items)
    assert all(item["body"] != "Nota solo para el equipo." for item in items)


def test_technician_creates_public_comment_visible_to_creator(
    client, seeded_workflow, auth_headers
) -> None:
    """US2/AC3: la vía de escritura existente permite comentarios públicos."""

    ticket = seeded_workflow.tickets["en_progreso"]
    technician = seeded_workflow.users["tecnico_asignado"]
    technician_headers = auth_headers(technician)

    public_response = client.post(
        _url(ticket, "internal-comments"),
        headers=technician_headers,
        json={
            "body": "Comentario público creado desde la API.",
            "request_id": str(uuid.uuid4()),
            "is_internal": False,
        },
    )
    internal_response = client.post(
        _url(ticket, "internal-comments"),
        headers=technician_headers,
        json={
            "body": "Nota solo para el equipo.",
            "request_id": str(uuid.uuid4()),
            "is_internal": True,
        },
    )

    assert public_response.status_code == 201, public_response.text
    assert internal_response.status_code == 201, internal_response.text
    public = public_response.json()["entry"]
    assert public["type"] == "internal_comment"
    assert public["is_internal"] is False
    assert public["body"] == "Comentario público creado desde la API."
    assert public["author"]["id"] == str(technician.id)
    assert public["author"]["name"] == technician.name
    assert public["author"]["role"] == technician.role.value
    assert datetime.fromisoformat(public["created_at"].replace("Z", "+00:00"))

    timeline = _timeline(client, ticket, auth_headers(seeded_workflow.users["creador"]))

    assert timeline.status_code == 200, timeline.text
    items = timeline.json()["items"]
    assert [item["id"] for item in items].count(public["id"]) == 1
    assert all(item["is_internal"] is False for item in items)
    assert all(item["body"] != "Nota solo para el equipo." for item in items)


def test_creator_gets_empty_timeline_payload(client, seeded_workflow, auth_headers) -> None:
    """US2/AC4: un ticket sin entradas devuelve historial vacío y paginación coherente."""

    ticket = seeded_workflow.tickets["abierto"]

    response = _timeline(client, ticket, auth_headers(seeded_workflow.users["creador"]))

    assert response.status_code == 200, response.text
    assert response.json() == {
        "items": [],
        "pagination": {
            "page": 1,
            "page_size": 50,
            "total_items": 0,
            "total_pages": 0,
            "has_next": False,
            "has_previous": False,
        },
    }


def test_entry_without_author_is_serialized_as_sistema() -> None:
    """Caso límite: una entrada sin autor muestra «Sistema» sin exponer datos internos."""

    entry = TicketTimelineEntry(
        id=uuid.uuid4(),
        ticket_id=uuid.uuid4(),
        event_type=TimelineEventType.internal_comment,
        from_status=None,
        to_status=None,
        body="Entrada sin autor.",
        is_internal=False,
        author_id=uuid.uuid4(),
        created_at=datetime.now(timezone.utc),
        event_order=0,
        request_id=uuid.uuid4(),
    )

    serialized = serialize_entry(entry)

    assert serialized.author.name == "Sistema"
    assert serialized.author.role is UserRole.usuario


@pytest.mark.postgres
def test_public_timeline_comments_migration_is_reversible_on_postgres() -> None:
    """0005 admite comentarios públicos y conserva las filas válidas (PostgreSQL)."""

    database_url = os.environ.get("TEST_DATABASE_URL", "").strip()
    if not database_url or database_url.startswith("sqlite"):
        pytest.skip("requiere TEST_DATABASE_URL apuntando a PostgreSQL")

    migration_path = (
        Path(__file__).resolve().parents[2]
        / "alembic"
        / "versions"
        / "0005_public_timeline_comments.py"
    )
    spec = importlib.util.spec_from_file_location("migration_0005", migration_path)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    schema = f"hu02_migration_{uuid.uuid4().hex[:12]}"
    table = "ticket_timeline_entries"
    legacy_id = str(uuid.uuid4())
    public_id = str(uuid.uuid4())
    second_public_id = str(uuid.uuid4())

    def insert(connection, entry_id: str, is_internal: bool) -> None:
        with connection.begin_nested():
            connection.execute(
                text(
                    f'INSERT INTO "{schema}".{table} '
                    "(id, event_type, from_status, to_status, body, is_internal) "
                    "VALUES (:id, 'internal_comment', NULL, NULL, :body, :is_internal)"
                ),
                {
                    "id": entry_id,
                    "body": "Comentario de prueba.",
                    "is_internal": is_internal,
                },
            )

    try:
        with engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            connection.execute(
                text(
                    f'CREATE TABLE "{schema}".{table} ('
                    "id uuid PRIMARY KEY, event_type text NOT NULL, "
                    "from_status text, to_status text, body text, "
                    "is_internal boolean NOT NULL, "
                    f"CONSTRAINT ck_timeline_internal_comment CHECK ("
                    "(event_type <> 'internal_comment') OR "
                    "(from_status IS NULL AND to_status IS NULL "
                    "AND body IS NOT NULL AND is_internal = true)))"
                )
            )
            insert(connection, legacy_id, True)
            with pytest.raises(IntegrityError):
                insert(connection, public_id, False)

        def apply(operation) -> None:
            with engine.begin() as connection:
                connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
                context = MigrationContext.configure(connection)
                with Operations.context(context):
                    operation()

        apply(migration.upgrade)
        with engine.begin() as connection:
            insert(connection, public_id, False)
            visible_ids = {
                str(row[0])
                for row in connection.execute(
                    text(f'SELECT id FROM "{schema}".{table}')
                )
            }
        assert visible_ids == {legacy_id, public_id}

        apply(migration.downgrade)
        with engine.begin() as connection:
            with pytest.raises(IntegrityError):
                insert(connection, second_public_id, False)
            remaining_ids = {
                str(row[0])
                for row in connection.execute(
                    text(f'SELECT id FROM "{schema}".{table}')
                )
            }
        assert remaining_ids == {legacy_id, public_id}
    finally:
        with engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
