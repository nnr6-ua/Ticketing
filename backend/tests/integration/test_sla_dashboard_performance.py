"""Rendimiento del snapshot del dashboard con 10.000 tickets (T071).

El objetivo de HU07-SC-002 (< 3 s extremo a extremo) se valida manualmente en
`quickstart.md` §5 E8. Aquí se mide el cálculo del snapshot en servidor con un
percentil 95 inferior a 300 ms (constitución) y una llamada HTTP completa.

La prueba se ejecuta sobre el motor configurado (`TEST_DATABASE_URL` para
PostgreSQL real). No se truncan datos ajenos: el fixture `db` recrea el esquema
de la base de pruebas antes de cada caso.
"""

from __future__ import annotations

import math
import time
import uuid
from datetime import timedelta

from app.models import Ticket, TicketStatus
from app.services.sla_dashboard import DashboardQuery, build_sla_dashboard
from tests.conftest import SessionLocal
from tests.integration._hu07 import API

TOTAL_TICKETS = 10_000
SERVER_P95_BUDGET_S = 0.300
END_TO_END_BUDGET_S = 3.0
# Con 10 muestras el «percentil 95» coincide con el máximo y un único pico del
# sistema operativo (GC, cambio de contexto) invalida la medición. Se toman
# suficientes muestras para que el p95 excluya los valores atípicos, sin relajar
# el presupuesto de 300 ms.
ITERATIONS = 40


def _bulk_tickets(seed) -> list[dict]:
    now = seed.now
    rows: list[dict] = []
    technicians = [
        seed.users["tecnico_a"].id,
        seed.users["tecnico_b"].id,
        seed.users["tecnico_c"].id,
    ]
    category_ids = [
        seed.categories["red"].id,
        seed.categories["hardware"].id,
        seed.categories["software"].id,
        None,
    ]

    for index in range(TOTAL_TICKETS):
        created_at = now - timedelta(days=20, minutes=index % (20 * 24 * 60))
        has_sla = index % 5 != 0
        deadline = created_at + timedelta(hours=4 + (index % 48)) if has_sla else None
        resolved = index % 3 == 0
        if resolved:
            base = deadline if deadline is not None else created_at + timedelta(hours=2)
            finalized_at = base + timedelta(minutes=15 * ((index % 5) - 2))
            if finalized_at < created_at:
                finalized_at = created_at + timedelta(minutes=5)
        else:
            finalized_at = None

        rows.append(
            {
                "id": uuid.uuid5(uuid.NAMESPACE_DNS, f"hu07-perf-{index}"),
                "number": f"TK-9{index:06d}",
                "title": f"Ticket de rendimiento {index}",
                "description": None,
                "status": (
                    TicketStatus.resuelto if resolved else TicketStatus.en_progreso
                ),
                "priority_id": seed.priorities[(index % 4) + 1].id,
                "category_id": category_ids[index % len(category_ids)],
                "creator_id": seed.users["usuario"].id,
                "assignee_id": technicians[index % len(technicians)],
                "created_at": created_at,
                "sla_deadline": deadline,
                "finalized_at": finalized_at,
                "closed_at": finalized_at,
                "updated_at": created_at,
                "sla_version": "v1",
            }
        )
    return rows


def _percentile_95(samples: list[float]) -> float:
    ordered = sorted(samples)
    index = max(0, math.ceil(0.95 * len(ordered)) - 1)
    return ordered[index]


def test_snapshot_meets_server_latency_budget(client, db, dashboard_seed):
    db.execute(Ticket.__table__.insert(), _bulk_tickets(dashboard_seed))
    db.commit()

    samples: list[float] = []
    # Calentamiento no medido: compila y cachea las sentencias SQLAlchemy.
    warmup_session = SessionLocal()
    try:
        build_sla_dashboard(
            warmup_session,
            DashboardQuery(),
            now=dashboard_seed.now,
        )
    finally:
        warmup_session.close()

    for _ in range(ITERATIONS):
        session = SessionLocal()
        try:
            started = time.perf_counter()
            response = build_sla_dashboard(
                session,
                DashboardQuery(),
                now=dashboard_seed.now,
            )
            samples.append(time.perf_counter() - started)
        finally:
            session.close()

    assert response.data.summary.ticket_count >= TOTAL_TICKETS
    assert _percentile_95(samples) < SERVER_P95_BUDGET_S, samples


def test_api_call_completes_within_end_to_end_budget(client, db, dashboard_seed):
    db.execute(Ticket.__table__.insert(), _bulk_tickets(dashboard_seed))
    db.commit()

    started = time.perf_counter()
    response = client.get(API, headers=dashboard_seed.supervisor_headers)
    elapsed = time.perf_counter() - started

    assert response.status_code == 200, response.text
    assert elapsed < END_TO_END_BUDGET_S, elapsed
    assert response.json()["data"]["summary"]["ticket_count"] >= TOTAL_TICKETS
