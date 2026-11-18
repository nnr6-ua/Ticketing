"""Concurrencia real de peticiones y respuestas de información (T058).

Se omite sobre SQLite; requiere `TEST_DATABASE_URL` apuntando a PostgreSQL.
"""

from __future__ import annotations

import threading
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.models import (
    Ticket,
    TicketStatus,
    TicketTimelineEntry,
    TimelineEventType,
    User,
)
from app.schemas.ticket_workflow import (
    InformationRequestRequest,
    InformationResponseRequest,
)
from app.services.ticket_timeline import as_utc
from app.services.ticket_workflow import (
    request_information,
    respond_to_information,
)
from tests.conftest import IS_SQLITE

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(IS_SQLITE, reason="Requiere PostgreSQL para concurrencia real"),
]


def _run_concurrently(workers):
    barrier = threading.Barrier(len(workers))
    results: list[tuple[object, object]] = []
    lock = threading.Lock()

    def run(worker):
        def wrapped():
            barrier.wait(timeout=10)
            try:
                outcome = worker()
            except ApiError as exc:
                outcome = (exc.status_code, exc.code)
            except Exception as exc:  # noqa: BLE001 - se reporta el fallo
                outcome = ("exception", repr(exc))
            with lock:
                results.append(outcome)

        return wrapped

    threads = [threading.Thread(target=run(worker)) for worker in workers]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
        assert not thread.is_alive(), "la prueba de concurrencia no terminó"
    return results


def _worker(session: Session, action, user: User, ticket_id: UUID, payload):
    def run():
        try:
            response = action(session, ticket_id, user, payload)
            return ("ok", response.changed)
        except ApiError as exc:
            session.rollback()
            return (exc.status_code, exc.code)
        finally:
            session.close()

    return run


def _count_entries(db: Session, ticket_id: UUID, event_type, to_status=None) -> int:
    statement = select(func.count()).select_from(TicketTimelineEntry).where(
        TicketTimelineEntry.ticket_id == ticket_id,
        TicketTimelineEntry.event_type == event_type,
    )
    if to_status is not None:
        statement = statement.where(TicketTimelineEntry.to_status == to_status)
    return int(db.scalar(statement) or 0)


def test_only_one_of_two_simultaneous_responses_writes(
    db: Session, seeded_workflow
) -> None:
    from app.db.session import SessionLocal

    ticket = seeded_workflow.tickets["pendiente_usuario"]
    expected = as_utc(ticket.updated_at)
    creator_id = seeded_workflow.users["creador"].id

    def make_worker():
        session = SessionLocal()
        user = session.get(User, creator_id)
        payload = InformationResponseRequest(
            body="Chrome 131 en Windows 11.",
            expected_updated_at=expected,
            request_id=uuid4(),
        )
        return _worker(session, respond_to_information, user, ticket.id, payload)

    results = _run_concurrently([make_worker(), make_worker()])

    assert len(results) == 2
    winners = [result for result in results if result == ("ok", True)]
    conflicts = [result for result in results if result[0] == 409]
    assert winners == [("ok", True)]
    assert len(conflicts) == 1
    assert conflicts[0] == (409, "stale_ticket")

    db.expire_all()
    refreshed = db.get(Ticket, ticket.id)
    assert refreshed is not None
    assert refreshed.status == TicketStatus.en_progreso
    assert (
        _count_entries(
            db, ticket.id, TimelineEventType.status_change, TicketStatus.en_progreso
        )
        == 1
    )
    assert _count_entries(db, ticket.id, TimelineEventType.user_response) == 1


def test_only_one_of_two_simultaneous_requests_writes(
    db: Session, seeded_workflow
) -> None:
    from app.db.session import SessionLocal

    ticket = seeded_workflow.tickets["en_progreso"]
    expected = as_utc(ticket.updated_at)
    technician_id = seeded_workflow.users["tecnico_asignado"].id

    def make_worker():
        session = SessionLocal()
        user = session.get(User, technician_id)
        payload = InformationRequestRequest(
            body="¿Qué versión del navegador usas?",
            expected_updated_at=expected,
            request_id=uuid4(),
        )
        return _worker(session, request_information, user, ticket.id, payload)

    results = _run_concurrently([make_worker(), make_worker()])

    assert len(results) == 2
    assert [result for result in results if result == ("ok", True)] == [("ok", True)]
    assert [result for result in results if result[0] == 409] == [
        (409, "stale_ticket")
    ]

    db.expire_all()
    refreshed = db.get(Ticket, ticket.id)
    assert refreshed is not None
    assert refreshed.status == TicketStatus.pendiente_usuario
    assert (
        _count_entries(
            db, ticket.id, TimelineEventType.status_change, TicketStatus.pendiente_usuario
        )
        == 1
    )
    assert _count_entries(db, ticket.id, TimelineEventType.information_request) == 1


def test_double_submission_of_response_request_id_is_idempotent(
    db: Session, seeded_workflow
) -> None:
    from app.db.session import SessionLocal

    ticket = seeded_workflow.tickets["pendiente_usuario"]
    expected = as_utc(ticket.updated_at)
    request_id = uuid4()
    creator_id = seeded_workflow.users["creador"].id

    def make_worker():
        session = SessionLocal()
        user = session.get(User, creator_id)
        payload = InformationResponseRequest(
            body="Windows 11 y Chrome 131.",
            expected_updated_at=expected,
            request_id=request_id,
        )
        return _worker(session, respond_to_information, user, ticket.id, payload)

    results = _run_concurrently([make_worker(), make_worker()])

    assert len(results) == 2
    assert all(result[0] == "ok" for result in results)
    assert sorted(result[1] for result in results) == [False, True]
    assert _count_entries(db, ticket.id, TimelineEventType.user_response) == 1
    assert (
        _count_entries(
            db, ticket.id, TimelineEventType.status_change, TicketStatus.en_progreso
        )
        == 1
    )


def test_double_submission_of_request_request_id_is_idempotent(
    db: Session, seeded_workflow
) -> None:
    from app.db.session import SessionLocal

    ticket = seeded_workflow.tickets["en_progreso"]
    expected = as_utc(ticket.updated_at)
    request_id = uuid4()
    technician_id = seeded_workflow.users["tecnico_asignado"].id

    def make_worker():
        session = SessionLocal()
        user = session.get(User, technician_id)
        payload = InformationRequestRequest(
            body="¿Qué sistema operativo usas?",
            expected_updated_at=expected,
            request_id=request_id,
        )
        return _worker(session, request_information, user, ticket.id, payload)

    results = _run_concurrently([make_worker(), make_worker()])

    assert len(results) == 2
    assert all(result[0] == "ok" for result in results)
    assert sorted(result[1] for result in results) == [False, True]
    assert _count_entries(db, ticket.id, TimelineEventType.information_request) == 1
    assert (
        _count_entries(
            db, ticket.id, TimelineEventType.status_change, TicketStatus.pendiente_usuario
        )
        == 1
    )
