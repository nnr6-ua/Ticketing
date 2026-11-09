"""Pruebas de concurrencia real sobre PostgreSQL (HU-05, T015A/T055B).

Se omiten automáticamente cuando la suite se ejecuta sobre SQLite. Para
ejecutarlas, exporta `TEST_DATABASE_URL` apuntando a un PostgreSQL 16
desechable y lanza:

    python -m pytest tests/integration/test_ticket_concurrency.py -q -m postgres
"""

from __future__ import annotations

import threading
from datetime import datetime
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
from app.schemas.ticket_workflow import StatusTransitionRequest
from app.services.ticket_timeline import as_utc
from app.services.ticket_workflow import (
    apply_user_response_transition,
    change_status,
)
from tests.conftest import IS_SQLITE

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(IS_SQLITE, reason="Requiere PostgreSQL para with_for_update"),
]


def _payload(
    target: TicketStatus,
    expected: datetime,
    request_id: UUID,
    *,
    resolution: str | None = None,
) -> StatusTransitionRequest:
    return StatusTransitionRequest(
        target_status=target,
        resolution=resolution,
        expected_updated_at=expected,
        request_id=request_id,
    )


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


def _session_factory(session_cls, user_id: UUID):
    def _worker(ticket_id: UUID, payload: StatusTransitionRequest):
        session: Session = session_cls()
        try:
            user = session.get(User, user_id)
            response = change_status(session, ticket_id, user, payload)
            return ("ok", response.changed)
        finally:
            session.close()

    return _worker


def test_only_one_of_two_stale_writers_wins(
    db, seeded_workflow
) -> None:
    from app.db.session import SessionLocal

    ticket = seeded_workflow.tickets["en_progreso"]
    expected = as_utc(ticket.updated_at)
    user_id = seeded_workflow.users["tecnico_asignado"].id
    worker = _session_factory(SessionLocal, user_id)

    # Destinos distintos: el perdedor no puede acogerse al no-op por mismo
    # estado (que se evalúa antes que `expected_updated_at`) y debe recibir
    # `409 stale_ticket`.
    results = _run_concurrently(
        [
            lambda: worker(
                ticket.id, _payload(TicketStatus.resuelto, expected, uuid4(), resolution="A")
            ),
            lambda: worker(
                ticket.id, _payload(TicketStatus.pendiente_usuario, expected, uuid4())
            ),
        ]
    )

    assert len(results) == 2
    assert sorted(result[0] for result in results) == ["ok", "stale_ticket"]
    ok = next(result for result in results if result[0] == "ok")
    stale = next(result for result in results if result[0] == "stale_ticket")
    assert ok == ("ok", True)
    assert stale == ("stale_ticket", None)

    db.expire_all()
    refreshed = db.get(Ticket, ticket.id)
    assert refreshed is not None
    assert refreshed.status in (TicketStatus.resuelto, TicketStatus.pendiente_usuario)
    status_changes = db.scalars(
        select(TicketTimelineEntry).where(
            TicketTimelineEntry.ticket_id == ticket.id,
            TicketTimelineEntry.event_type == TimelineEventType.status_change,
        )
    ).unique().all()
    resolutions = db.scalars(
        select(TicketTimelineEntry).where(
            TicketTimelineEntry.ticket_id == ticket.id,
            TicketTimelineEntry.event_type == TimelineEventType.resolution,
        )
    ).unique().all()
    assert len(status_changes) == 1
    expected_resolutions = 1 if refreshed.status == TicketStatus.resuelto else 0
    assert len(resolutions) == expected_resolutions


def test_same_request_id_is_not_duplicated_under_concurrency(
    db, seeded_workflow
) -> None:
    from app.db.session import SessionLocal

    ticket = seeded_workflow.tickets["en_progreso"]
    expected = as_utc(ticket.updated_at)
    request_id = uuid4()
    user_id = seeded_workflow.users["tecnico_asignado"].id
    worker = _session_factory(SessionLocal, user_id)
    payload = _payload(TicketStatus.resuelto, expected, request_id, resolution="Única")

    results = _run_concurrently(
        [
            lambda: worker(ticket.id, payload),
            lambda: worker(ticket.id, payload),
        ]
    )

    assert len(results) == 2
    assert all(result[0] == "ok" for result in results)
    assert sorted(result[1] for result in results) == [False, True]

    db.expire_all()
    rows = db.scalars(
        select(TicketTimelineEntry)
        .where(
            TicketTimelineEntry.ticket_id == ticket.id,
            TicketTimelineEntry.request_id == request_id,
        )
        .order_by(TicketTimelineEntry.event_order.asc())
    ).unique().all()
    assert [row.event_type for row in rows] == [
        TimelineEventType.status_change,
        TimelineEventType.resolution,
    ]


def test_only_one_preloaded_user_response_transition_wins(
    db, seeded_workflow
) -> None:
    """T071: dos sesiones de HU-03 precargan el ticket antes de competir.

    Solo una transición debe confirmarse con `changed=true`; la otra, tras
    esperar el bloqueo, debe releer la fila y recibir `409` sin escribir una
    segunda entrada `status_change`.
    """

    from app.db.session import SessionLocal

    ticket = seeded_workflow.tickets["pendiente_usuario"]
    expected = as_utc(ticket.updated_at)
    user_id = seeded_workflow.users["creador"].id
    barrier = threading.Barrier(2)

    def _worker(request_id: UUID):
        def run():
            session: Session = SessionLocal()
            try:
                user = session.get(User, user_id)
                preloaded = session.get(Ticket, ticket.id)
                assert preloaded is not None
                # HU-03 precarga el ticket en su sesión antes de invocar la
                # transición; ambas sesiones compiten desde el mismo estado.
                barrier.wait(timeout=10)
                try:
                    response = apply_user_response_transition(
                        session,
                        preloaded,
                        user,
                        request_id=request_id,
                        expected_updated_at=expected,
                    )
                    session.commit()
                    return ("ok", response.changed)
                except ApiError as exc:
                    session.rollback()
                    return (exc.status_code, exc.code)
            finally:
                session.close()

        return run

    results = _run_threads([_worker(uuid4()), _worker(uuid4())])

    assert len(results) == 2
    winners = [result for result in results if result[0] == "ok"]
    losers = [result for result in results if result[0] == 409]
    assert winners == [("ok", True)]
    # La perdedora relee la fila ya confirmada y rechaza la transición por
    # estado inválido (`409`), sin duplicar la entrada `status_change`.
    assert losers == [(409, "invalid_transition")]

    db.expire_all()
    refreshed = db.get(Ticket, ticket.id)
    assert refreshed is not None
    assert refreshed.status == TicketStatus.en_progreso
    status_changes = db.scalars(
        select(TicketTimelineEntry).where(
            TicketTimelineEntry.ticket_id == ticket.id,
            TicketTimelineEntry.event_type == TimelineEventType.status_change,
        )
    ).unique().all()
    assert len(status_changes) == 1


def test_status_change_and_resolution_roll_back_together(
    db, seeded_workflow, monkeypatch
) -> None:
    from app.db.session import SessionLocal

    ticket = seeded_workflow.tickets["en_progreso"]
    original_status = ticket.status
    expected = as_utc(ticket.updated_at)

    def _fail(*args, **kwargs):
        raise RuntimeError("fallo simulado al insertar la resolución")

    monkeypatch.setattr(
        "app.services.ticket_workflow._insert_resolution", _fail
    )

    session: Session = SessionLocal()
    try:
        user = session.get(User, seeded_workflow.users["tecnico_asignado"].id)
        with pytest.raises(ApiError) as error:
            change_status(
                session,
                ticket.id,
                user,
                _payload(
                    TicketStatus.resuelto,
                    expected,
                    uuid4(),
                    resolution="No debe persistir.",
                ),
            )
        assert error.value.status_code == 500
        assert error.value.code == "internal_error"
    finally:
        session.close()

    db.expire_all()
    refreshed = db.get(Ticket, ticket.id)
    assert refreshed is not None
    assert refreshed.status == original_status
    assert refreshed.finalized_at is None
    assert (
        db.scalar(
            select(func.count())
            .select_from(TicketTimelineEntry)
            .where(TicketTimelineEntry.ticket_id == ticket.id)
        )
        == 0
    )
