"""Comprobación ejecutable de rendimiento de HU-05 (T064).

Mide el p95 de las lecturas del flujo y de la línea temporal, el p95 del
comando de transición y el tiempo servidor observable al aplicar una
transición y refrescar la timeline. Es la comprobación de regresión que
acompaña a los objetivos del plan:

- `GET /tickets/{id}/workflow` y `GET /tickets/{id}/timeline`: p95 < 300 ms.
- `POST /tickets/{id}/status-transitions`: p95 < 300 ms.
- Transición + refresco de timeline: < 2 s (cota superior del tiempo
  percibido en la interfaz, que usa estas mismas peticiones).
"""

from __future__ import annotations

import math
import time
import uuid
from datetime import timedelta

from app.models import (
    TicketStatus,
    TicketTimelineEntry,
    TimelineEventType,
)

API = "/api/v1/tickets"

WARMUP_CALLS = 3
SAMPLES = 30
READ_BUDGET_SECONDS = 0.300
WRITE_BUDGET_SECONDS = 0.300
REFLECTION_BUDGET_SECONDS = 2.0


def _url(ticket_id: uuid.UUID, suffix: str) -> str:
    return f"{API}/{ticket_id}/{suffix}"


def _p95(samples: list[float]) -> float:
    ordered = sorted(samples)
    index = max(0, math.ceil(0.95 * len(ordered)) - 1)
    return ordered[index]


def _timed_get(client, url: str, headers: dict[str, str]) -> tuple[float, int]:
    started = time.perf_counter()
    response = client.get(url, headers=headers)
    elapsed = time.perf_counter() - started
    return elapsed, response.status_code


def _timed_post(client, url: str, headers: dict[str, str], payload: dict):
    started = time.perf_counter()
    response = client.post(url, headers=headers, json=payload)
    elapsed = time.perf_counter() - started
    return elapsed, response


def _seed_timeline(db, seed, ticket, count: int) -> None:
    """Histórico realista para que la timeline no se mida vacía."""

    author = seed.users["tecnico_asignado"]
    base = seed.now - timedelta(days=1)
    for index in range(count):
        if index % 3 == 0:
            event_type = TimelineEventType.status_change
            from_status = TicketStatus.abierto
            to_status = TicketStatus.en_progreso
            body = None
            event_order = 0
            is_internal = False
        elif index % 3 == 1:
            event_type = TimelineEventType.resolution
            from_status = None
            to_status = TicketStatus.resuelto
            body = f"Resolución histórica {index}."
            event_order = 1
            is_internal = False
        else:
            event_type = TimelineEventType.internal_comment
            from_status = None
            to_status = None
            body = f"Nota interna histórica {index}."
            event_order = 0
            is_internal = True

        db.add(
            TicketTimelineEntry(
                id=uuid.uuid5(
                    uuid.NAMESPACE_DNS, f"hu05-perf-{ticket.id}-{index}"
                ),
                ticket_id=ticket.id,
                event_type=event_type,
                from_status=from_status,
                to_status=to_status,
                body=body,
                is_internal=is_internal,
                author_id=author.id,
                created_at=base + timedelta(minutes=index),
                event_order=event_order,
                request_id=uuid.uuid5(
                    uuid.NAMESPACE_DNS, f"hu05-perf-req-{ticket.id}-{index}"
                ),
            )
        )
    db.commit()


def test_workflow_and_timeline_p95_and_transition_reflection(
    client, db, seeded_workflow, auth_headers
) -> None:
    seed = seeded_workflow
    ticket = seed.tickets["en_progreso"]
    headers = auth_headers(seed.users["tecnico_asignado"])
    _seed_timeline(db, seed, ticket, 60)

    workflow_url = _url(ticket.id, "workflow")
    timeline_url = _url(ticket.id, "timeline")

    for _ in range(WARMUP_CALLS):
        assert client.get(workflow_url, headers=headers).status_code == 200
        assert client.get(timeline_url, headers=headers).status_code == 200

    workflow_samples: list[float] = []
    timeline_samples: list[float] = []
    for _ in range(SAMPLES):
        elapsed, status = _timed_get(client, workflow_url, headers)
        assert status == 200
        workflow_samples.append(elapsed)

        elapsed, status = _timed_get(client, timeline_url, headers)
        assert status == 200
        timeline_samples.append(elapsed)

    workflow_p95 = _p95(workflow_samples)
    timeline_p95 = _p95(timeline_samples)

    # p95 del comando de escritura (Constitución, «Rendimiento»).
    # Se alterna entre dos transiciones válidas de RN-02 para no agotar el
    # flujo; con SAMPLES par el ticket vuelve a `en_progreso` para el bloque
    # de reflexión posterior.
    transition_samples: list[float] = []
    current = client.get(workflow_url, headers=headers).json()["ticket"]
    for _ in range(SAMPLES):
        target = (
            "pendiente_usuario"
            if current["status"] == "en_progreso"
            else "en_progreso"
        )
        elapsed, response = _timed_post(
            client,
            _url(ticket.id, "status-transitions"),
            headers,
            {
                "target_status": target,
                "expected_updated_at": current["updated_at"],
                "request_id": str(uuid.uuid4()),
            },
        )
        assert response.status_code == 200, response.text
        current = response.json()["ticket"]
        transition_samples.append(elapsed)

    transition_p95 = _p95(transition_samples)

    # Tiempo observable de la operación completa que dispara la interfaz:
    # POST de la transición y recarga de la timeline ya actualizada.
    workflow = client.get(workflow_url, headers=headers).json()
    transition_request_id = uuid.uuid4()
    started = time.perf_counter()
    transition = client.post(
        _url(ticket.id, "status-transitions"),
        headers=headers,
        json={
            "target_status": "resuelto",
            "resolution": "Solución medida en la prueba de rendimiento.",
            "expected_updated_at": workflow["ticket"]["updated_at"],
            "request_id": str(transition_request_id),
        },
    )
    assert transition.status_code == 200, transition.text
    refreshed = client.get(timeline_url, headers=headers)
    reflection_elapsed = time.perf_counter() - started
    assert refreshed.status_code == 200
    assert any(
        item["type"] == "resolution" for item in refreshed.json()["items"]
    )

    print(
        "HU-05 rendimiento: "
        f"workflow p95={workflow_p95 * 1000:.2f} ms, "
        f"timeline p95={timeline_p95 * 1000:.2f} ms, "
        f"transición p95={transition_p95 * 1000:.2f} ms, "
        f"transición+refresco={reflection_elapsed * 1000:.2f} ms "
        f"({SAMPLES} muestras)"
    )

    assert workflow_p95 < READ_BUDGET_SECONDS, (
        f"p95 de workflow demasiado alto: {workflow_p95:.3f}s"
    )
    assert timeline_p95 < READ_BUDGET_SECONDS, (
        f"p95 de timeline demasiado alto: {timeline_p95:.3f}s"
    )
    assert transition_p95 < WRITE_BUDGET_SECONDS, (
        f"p95 de status-transitions demasiado alto: {transition_p95:.3f}s"
    )
    assert reflection_elapsed < REFLECTION_BUDGET_SECONDS, (
        "la transición y el refresco superan el presupuesto percibido: "
        f"{reflection_elapsed:.3f}s"
    )


def test_p95_helper_is_stable() -> None:
    assert _p95([0.1, 0.2, 0.3, 0.4, 0.5]) == 0.5
    assert _p95([0.1]) == 0.1
