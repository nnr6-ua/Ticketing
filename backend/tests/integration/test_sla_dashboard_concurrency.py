"""Concurrencia real sobre PostgreSQL del dashboard de SLA (T075).

Lecturas del dashboard mientras se escriben tickets y cambios de estado. La
prueba se omite sobre SQLite; para ejecutarla:

    python -m pytest tests/integration/test_sla_dashboard_concurrency.py -q -m postgres
"""

from __future__ import annotations

import threading
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from app.models import (
    Ticket,
    TicketStatus,
    TicketTimelineEntry,
    TimelineEventType,
)
from app.services.sla_dashboard import DashboardQuery, build_sla_dashboard
from tests.conftest import IS_SQLITE, SessionLocal

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(IS_SQLITE, reason="Requiere PostgreSQL real"),
]

READERS = 4
READS_PER_THREAD = 5
WRITERS = 3


def _run_concurrently(workers):
    """Ejecuta workers etiquetados como ``(kind, callable)``.

    Devuelve una tupla ``(results, errors)`` donde ``results`` agrupa los
    resultados por etiqueta. Los lectores devuelven listas de conteos y los
    escritores devuelven ``None``; solo los resultados de los lectores se
    validan en la prueba.
    """
    barrier = threading.Barrier(len(workers))
    results: dict[str, list[object]] = {}
    errors: list[BaseException] = []
    lock = threading.Lock()

    def wrap(kind, worker):
        def run():
            try:
                barrier.wait(timeout=10)
                outcome = worker()
            except BaseException as exc:  # noqa: BLE001 - se reporta el fallo
                with lock:
                    errors.append(exc)
            else:
                with lock:
                    results.setdefault(kind, []).append(outcome)

        return run

    threads = [
        threading.Thread(target=wrap(kind, worker)) for kind, worker in workers
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)
        assert not thread.is_alive(), "la prueba de concurrencia no terminó"
    return results, errors


def _reader():
    def work():
        values = []
        for _ in range(READS_PER_THREAD):
            session = SessionLocal()
            try:
                snapshot = build_sla_dashboard(
                    session, DashboardQuery(prioridades=None)
                )
            finally:
                session.close()

            summary = snapshot.data.summary
            assert summary.overdue_count == snapshot.data.ranking.overdue_total
            if summary.compliance_pct is not None:
                assert 0.0 <= summary.compliance_pct <= 100.0
            values.append(summary.ticket_count)
        return values

    return work


def _writer(seed, index: int):
    def work():
        session = SessionLocal()
        try:
            created_at = datetime.now(timezone.utc) - timedelta(days=3)
            deadline = created_at + timedelta(hours=4)
            ticket = Ticket(
                id=uuid.uuid5(uuid.NAMESPACE_DNS, f"hu07-concurrent-{index}"),
                number=f"TK-8{index:05d}",
                title="Ticket concurrente",
                description=None,
                status=TicketStatus.resuelto,
                priority_id=seed.priorities[1].id,
                category_id=seed.categories["red"].id,
                creator_id=seed.users["usuario"].id,
                assignee_id=seed.users["tecnico_a"].id,
                created_at=created_at,
                sla_deadline=deadline,
                finalized_at=deadline + timedelta(minutes=30),
                closed_at=None,
                updated_at=created_at,
                sla_version="v1",
            )
            session.add(ticket)
            session.flush()
            session.add(
                TicketTimelineEntry(
                    id=uuid.uuid5(
                        uuid.NAMESPACE_DNS,
                        f"hu07-concurrent-entry-{index}",
                    ),
                    ticket_id=ticket.id,
                    event_type=TimelineEventType.status_change,
                    from_status=TicketStatus.en_progreso,
                    to_status=TicketStatus.resuelto,
                    body=None,
                    is_internal=False,
                    author_id=seed.users["tecnico_b"].id,
                    created_at=deadline + timedelta(minutes=30),
                    event_order=0,
                    request_id=uuid.uuid5(
                        uuid.NAMESPACE_DNS,
                        f"hu07-concurrent-request-{index}",
                    ),
                )
            )
            session.commit()
        finally:
            session.close()

    return work


def test_concurrent_reads_and_writes_are_consistent(db, dashboard_seed):
    entries_before = db.scalar(
        select(func.count()).select_from(TicketTimelineEntry)
    )

    results, errors = _run_concurrently(
        [("reader", _reader()) for _ in range(READERS)]
        + [
            ("writer", _writer(dashboard_seed, index))
            for index in range(WRITERS)
        ]
    )

    assert errors == []
    reader_results = results["reader"]
    assert len(reader_results) == READERS
    for counts in reader_results:
        assert counts and all(count >= 0 for count in counts)
    assert len(results["writer"]) == WRITERS

    db.expire_all()
    entries_after = db.scalar(
        select(func.count()).select_from(TicketTimelineEntry)
    )
    assert entries_after == (entries_before or 0) + WRITERS

    # El dashboard no ha escrito nada: solo los escritores añadieron filas.
    concurrent_tickets = db.scalar(
        select(func.count())
        .select_from(Ticket)
        .where(Ticket.number.like("TK-8%"))
    )
    assert concurrent_tickets == WRITERS
