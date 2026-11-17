"""Rendimiento servidor del cambio de responsable (HU-06, T079)."""

from __future__ import annotations

import itertools
import math
import time
import uuid
from datetime import timedelta

from sqlalchemy.orm import Session

from app.models import Ticket, TicketStatus, User
from tests.conftest import SeededAssigneeChange
from tests.integration._hu06 import (
    escalate,
    expected_updated_at,
    options,
    reassign,
    url,
)

WORK_QUEUE_API = "/api/v1/me/work-queue"

WARMUP_CALLS = 2
SAMPLES = 8
QUEUE_SAMPLES = 15
BUDGET_SECONDS = 0.300

# Secuencia monótona para que los números de ticket de carga sean únicos en la
# ejecución; `hash()` está aleatorizado por proceso y podía colisionar en
# PostgreSQL con la restricción UNIQUE de `tickets.number`.
_NUMBER_SEQUENCE = itertools.count(900_000)


def _p95(samples: list[float]) -> float:
    ordered = sorted(samples)
    index = max(0, math.ceil(0.95 * len(ordered)) - 1)
    return ordered[index]


def _timed_get(client, path: str, headers: dict[str, str]):
    started = time.perf_counter()
    response = client.get(path, headers=headers)
    return time.perf_counter() - started, response


def _timed_command(command, *args, **kwargs):
    started = time.perf_counter()
    response = command(*args, **kwargs)
    return time.perf_counter() - started, response


def _create_ticket(
    db: Session,
    seed: SeededAssigneeChange,
    key: str,
    assignee: User,
    status: TicketStatus = TicketStatus.en_progreso,
) -> Ticket:
    ticket = Ticket(
        id=uuid.uuid5(uuid.NAMESPACE_DNS, f"hu06-perf-ticket-{key}"),
        number=f"TK-{next(_NUMBER_SEQUENCE)}",
        title=f"Ticket de rendimiento {key}",
        description="Ticket para medir el rendimiento del cambio de responsable.",
        status=status,
        priority_id=seed.priority.id,
        category_id=seed.category.id,
        creator_id=seed.users["creador_tecnico"].id,
        assignee_id=assignee.id,
        created_at=seed.now,
        sla_deadline=seed.now + timedelta(days=1),
        updated_at=seed.now,
        sla_version="v1",
    )
    db.add(ticket)
    return ticket


def test_assignee_change_endpoints_p95_with_hundred_active_tickets(
    client, db, seeded_assignee_change: SeededAssigneeChange, auth_headers
) -> None:
    seed = seeded_assignee_change
    assigned = seed.users["asignado"]
    headers = auth_headers(assigned)

    # Carga realista: 100 tickets activos en la cola del técnico.
    for index in range(100):
        _create_ticket(db, seed, f"queue-{index}", assigned)
    db.commit()

    stable_ticket = seed.tickets["activo"]

    for _ in range(WARMUP_CALLS):
        assert options(client, stable_ticket, headers).status_code == 200

    option_samples: list[float] = []
    for _ in range(SAMPLES):
        elapsed, response = _timed_get(
            client, url(stable_ticket, "assignee-change-options"), headers
        )
        assert response.status_code == 200, response.text
        option_samples.append(elapsed)

    reassign_tickets = [
        _create_ticket(db, seed, f"reassign-{index}", assigned)
        for index in range(SAMPLES)
    ]
    db.commit()
    reassign_samples: list[float] = []
    for ticket in reassign_tickets:
        expected = expected_updated_at(client, ticket, headers)
        elapsed, response = _timed_command(
            reassign,
            client,
            ticket,
            headers,
            seed.users["companero"],
            reason="Motivo de rendimiento.",
            expected=expected,
        )
        assert response.status_code == 200, response.text
        reassign_samples.append(elapsed)

    escalate_tickets = [
        _create_ticket(db, seed, f"escalate-{index}", assigned)
        for index in range(SAMPLES)
    ]
    db.commit()
    escalate_samples: list[float] = []
    for ticket in escalate_tickets:
        expected = expected_updated_at(client, ticket, headers)
        elapsed, response = _timed_command(
            escalate,
            client,
            ticket,
            headers,
            "nivel_2",
            reason="Motivo de rendimiento.",
            expected=expected,
        )
        assert response.status_code == 200, response.text
        escalate_samples.append(elapsed)

    queue_url = f"{WORK_QUEUE_API}?page=1&page_size=100"
    for _ in range(WARMUP_CALLS):
        assert client.get(queue_url, headers=headers).status_code == 200
    queue_samples: list[float] = []
    for _ in range(QUEUE_SAMPLES):
        elapsed, response = _timed_get(client, queue_url, headers)
        assert response.status_code == 200, response.text
        queue_samples.append(elapsed)

    option_p95 = _p95(option_samples)
    reassign_p95 = _p95(reassign_samples)
    escalate_p95 = _p95(escalate_samples)
    queue_p95 = _p95(queue_samples)

    print(
        "HU-06 rendimiento: "
        f"options p95={option_p95 * 1000:.2f} ms, "
        f"reassign p95={reassign_p95 * 1000:.2f} ms, "
        f"escalate p95={escalate_p95 * 1000:.2f} ms, "
        f"queue p95={queue_p95 * 1000:.2f} ms"
    )

    assert option_p95 < BUDGET_SECONDS, f"options p95={option_p95:.3f}s"
    assert reassign_p95 < BUDGET_SECONDS, f"reassign p95={reassign_p95:.3f}s"
    assert escalate_p95 < BUDGET_SECONDS, f"escalate p95={escalate_p95:.3f}s"
    assert queue_p95 < BUDGET_SECONDS, f"queue p95={queue_p95:.3f}s"


def test_p95_helper_is_stable() -> None:
    assert _p95([0.1, 0.2, 0.3]) == 0.3
    assert _p95([0.1]) == 0.1
