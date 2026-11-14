"""Concurrencia real del cambio de responsable sobre PostgreSQL (HU-06, T071)."""

from __future__ import annotations

import threading
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.models import Notification, Ticket, TicketTimelineEntry, User
from app.schemas.assignee_change import EscalationRequest, ReassignmentRequest
from app.services.assignee_change import escalate_ticket, reassign_ticket
from app.services.ticket_timeline import as_utc
from tests.conftest import IS_SQLITE

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(IS_SQLITE, reason="Requiere PostgreSQL para with_for_update"),
]


def _run_threads(workers):
    results: list[tuple[object, object]] = []
    lock = threading.Lock()

    def wrap(worker):
        def run():
            try:
                outcome = worker()
            except ApiError as exc:  # pragma: no cover - depende del motor
                outcome = (exc.code, None)
            except Exception as exc:  # noqa: BLE001 - se reporta el fallo
                outcome = ("exception", repr(exc))
            with lock:
                results.append(outcome)

        return run

    threads = [threading.Thread(target=wrap(worker)) for worker in workers]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
        assert not thread.is_alive(), "la prueba de concurrencia no terminó"
    return results


def _run_concurrently(workers):
    barrier = threading.Barrier(len(workers))

    def synchronized(worker):
        def run():
            barrier.wait(timeout=10)
            return worker()

        return run

    return _run_threads([synchronized(worker) for worker in workers])


def _reassign_worker(session_cls, user_id: UUID, ticket_id: UUID, payload):
    def run():
        session: Session = session_cls()
        try:
            user = session.get(User, user_id)
            response = reassign_ticket(session, ticket_id, user, payload)
            return ("ok", response.changed)
        finally:
            session.close()

    return run


def _escalate_worker(session_cls, user_id: UUID, ticket_id: UUID, payload):
    def run():
        session: Session = session_cls()
        try:
            user = session.get(User, user_id)
            response = escalate_ticket(session, ticket_id, user, payload)
            return ("ok", response.changed)
        finally:
            session.close()

    return run


def _counts(db: Session, ticket_id: UUID) -> tuple[int, int]:
    db.expire_all()
    timeline_count = int(
        db.scalar(
            select(func.count())
            .select_from(TicketTimelineEntry)
            .where(TicketTimelineEntry.ticket_id == ticket_id)
        )
        or 0
    )
    notification_count = int(
        db.scalar(
            select(func.count())
            .select_from(Notification)
            .where(Notification.ticket_id == ticket_id)
        )
        or 0
    )
    return timeline_count, notification_count


def test_only_one_of_two_concurrent_commands_wins(
    db, seeded_assignee_change
) -> None:
    from app.db.session import SessionLocal

    seed = seeded_assignee_change
    ticket = seed.tickets["activo"]
    expected = as_utc(ticket.updated_at)
    assert expected is not None

    reassignment = ReassignmentRequest(
        new_assignee_id=seed.users["companero"].id,
        reason="Traspaso concurrente.",
        expected_updated_at=expected,
        request_id=uuid4(),
    )
    escalation = EscalationRequest(
        target_level="nivel_2",
        reason="Escalado concurrente.",
        expected_updated_at=expected,
        request_id=uuid4(),
    )

    lock_acquired = threading.Event()

    def reassignment_first():
        session: Session = SessionLocal()
        try:
            user = session.get(User, seed.users["asignado"].id)
            # Bloquea la fila antes de invocar el comando para que el otro
            # hilo espere de forma determinista en `_locked_ticket`.
            session.scalar(
                select(Ticket.id)
                .where(Ticket.id == ticket.id)
                .with_for_update()
            )
            lock_acquired.set()
            response = reassign_ticket(session, ticket.id, user, reassignment)
            return ("ok", response.changed)
        finally:
            session.close()

    def escalation_while_locked():
        session: Session = SessionLocal()
        try:
            assert lock_acquired.wait(timeout=10)
            user = session.get(User, seed.users["companero"].id)
            response = escalate_ticket(session, ticket.id, user, escalation)
            return ("ok", response.changed)
        finally:
            session.close()

    results = _run_threads([reassignment_first, escalation_while_locked])

    assert len(results) == 2
    assert sorted(result[0] for result in results) == ["ok", "stale_ticket"]
    winner = next(result for result in results if result[0] == "ok")
    loser = next(result for result in results if result[0] == "stale_ticket")
    assert winner == ("ok", True)
    assert loser == ("stale_ticket", None)

    # La sesión de la prueba conserva el ticket en su mapa de identidad
    # (`expire_on_commit=False`); hay que descartarlo para leer el estado que
    # dejó el hilo ganador en otra conexión.
    db.expire_all()
    refreshed = db.get(Ticket, ticket.id)
    assert refreshed is not None
    assert refreshed.assignee_id == seed.users["companero"].id
    assert _counts(db, ticket.id) == (1, 1)


def test_identical_request_id_is_not_duplicated_under_concurrency(
    db, seeded_assignee_change
) -> None:
    from app.db.session import SessionLocal

    seed = seeded_assignee_change
    ticket = seed.tickets["activo"]
    expected = as_utc(ticket.updated_at)
    assert expected is not None
    request_id = uuid4()
    payload = ReassignmentRequest(
        new_assignee_id=seed.users["companero"].id,
        reason="Reintento concurrente.",
        expected_updated_at=expected,
        request_id=request_id,
    )

    results = _run_concurrently(
        [
            _reassign_worker(
                SessionLocal, seed.users["asignado"].id, ticket.id, payload
            ),
            _reassign_worker(
                SessionLocal, seed.users["asignado"].id, ticket.id, payload
            ),
        ]
    )

    assert len(results) == 2
    assert all(result[0] == "ok" for result in results)
    assert sorted(result[1] for result in results) == [False, True]
    assert _counts(db, ticket.id) == (1, 1)


def test_replay_after_losing_the_assignment_does_not_write(
    db, seeded_assignee_change
) -> None:
    from app.db.session import SessionLocal

    seed = seeded_assignee_change
    ticket = seed.tickets["activo"]
    expected = as_utc(ticket.updated_at)
    assert expected is not None
    request_id = uuid4()
    payload = ReassignmentRequest(
        new_assignee_id=seed.users["companero"].id,
        reason="Motivo de red.",
        expected_updated_at=expected,
        request_id=request_id,
    )

    first = _reassign_worker(
        SessionLocal, seed.users["asignado"].id, ticket.id, payload
    )()
    assert first == ("ok", True)
    assert _counts(db, ticket.id) == (1, 1)

    replay = _reassign_worker(
        SessionLocal, seed.users["asignado"].id, ticket.id, payload
    )()

    assert replay == ("ok", False)
    assert _counts(db, ticket.id) == (1, 1)
