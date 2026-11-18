"""Pruebas de integración del cambio de estado, la resolución y la idempotencia."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from sqlalchemy import and_, select, update
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.models import (
    Ticket,
    TicketStatus,
    TicketTimelineEntry,
    TimelineEventType,
    User,
)
from app.services.ticket_workflow import apply_user_response_transition
from app.services.ticket_timeline import as_utc

API = "/api/v1/tickets"
MIGRATION_CUTOFF = datetime(2026, 11, 2, tzinfo=timezone.utc)
_UNSET = object()


def _url(ticket: Ticket, suffix: str) -> str:
    return f"{API}/{ticket.id}/{suffix}"


def _workflow(client, ticket: Ticket, headers: dict[str, str]) -> dict:
    response = client.get(_url(ticket, "workflow"), headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def _expected(client, ticket: Ticket, headers: dict[str, str]) -> str:
    return _workflow(client, ticket, headers)["ticket"]["updated_at"]


def _transition(
    client,
    ticket: Ticket,
    headers: dict[str, str],
    target: str,
    *,
    resolution=_UNSET,
    expected: str | None = None,
    request_id: UUID | None = None,
):
    body: dict = {
        "target_status": target,
        "expected_updated_at": expected or _expected(client, ticket, headers),
        "request_id": str(request_id or uuid4()),
    }
    if resolution is not _UNSET:
        body["resolution"] = resolution
    return client.post(_url(ticket, "status-transitions"), headers=headers, json=body)


def _entries(db: Session, ticket: Ticket) -> list[TicketTimelineEntry]:
    db.expire_all()
    statement = (
        select(TicketTimelineEntry)
        .where(TicketTimelineEntry.ticket_id == ticket.id)
        .order_by(
            TicketTimelineEntry.created_at.asc(),
            TicketTimelineEntry.event_order.asc(),
            TicketTimelineEntry.id.asc(),
        )
    )
    return list(db.scalars(statement).unique().all())


def _reload(db: Session, ticket: Ticket) -> Ticket:
    db.expire(ticket)
    db.refresh(ticket)
    return ticket


def _parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _legacy_without_resolution(db: Session) -> list[tuple[UUID, str]]:
    """Auditoría T050A: tickets finalizados antes de la migración sin resolución."""

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
            Ticket.status.in_([TicketStatus.resuelto, TicketStatus.cerrado]),
            Ticket.finalized_at < MIGRATION_CUTOFF,
            TicketTimelineEntry.id.is_(None),
        )
        .order_by(Ticket.created_at.asc())
    )
    return [(row[0], row[1]) for row in db.execute(statement).all()]


def _resolved_without_resolution_since_migration(
    db: Session,
) -> list[tuple[UUID, str]]:
    """Invariante T050: todo `resuelto` posterior a 0003 tiene resolución."""

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
            Ticket.finalized_at >= MIGRATION_CUTOFF,
            TicketTimelineEntry.id.is_(None),
        )
    )
    return [(row[0], row[1]) for row in db.execute(statement).all()]


# ---------------------------------------------------------------------------
# Transiciones válidas
# ---------------------------------------------------------------------------
def test_open_to_in_progress_creates_one_status_change(
    client, db, seeded_workflow, auth_headers
) -> None:
    ticket = seeded_workflow.tickets["abierto"]
    headers = auth_headers(seeded_workflow.users["tecnico_asignado"])

    response = _transition(client, ticket, headers, "en_progreso")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["changed"] is True
    assert payload["message"] is None
    assert payload["ticket"]["status"] == "en_progreso"
    assert payload["ticket"]["finalized_at"] is None
    assert len(payload["timeline_entries"]) == 1
    entry = payload["timeline_entries"][0]
    assert entry["type"] == "status_change"
    assert entry["from_status"] == "abierto"
    assert entry["to_status"] == "en_progreso"
    assert entry["body"] is None
    assert entry["is_internal"] is False
    assert entry["author"]["id"] == str(seeded_workflow.users["tecnico_asignado"].id)

    _reload(db, ticket)
    assert ticket.status == TicketStatus.en_progreso
    entries = _entries(db, ticket)
    assert len(entries) == 1
    assert entries[0].event_type == TimelineEventType.status_change


def test_in_progress_to_pending_user(
    client, db, seeded_workflow, auth_headers
) -> None:
    ticket = seeded_workflow.tickets["en_progreso"]
    headers = auth_headers(seeded_workflow.users["tecnico_asignado"])

    response = _transition(client, ticket, headers, "pendiente_usuario")

    assert response.status_code == 200, response.text
    assert response.json()["ticket"]["status"] == "pendiente_usuario"
    _reload(db, ticket)
    assert ticket.status == TicketStatus.pendiente_usuario


def test_pending_user_to_in_progress(
    client, db, seeded_workflow, auth_headers
) -> None:
    ticket = seeded_workflow.tickets["pendiente_usuario"]
    headers = auth_headers(seeded_workflow.users["tecnico_asignado"])

    response = _transition(client, ticket, headers, "en_progreso")

    assert response.status_code == 200, response.text
    assert response.json()["ticket"]["status"] == "en_progreso"


def test_in_progress_to_resolved_with_valid_resolution(
    client, db, seeded_workflow, auth_headers
) -> None:
    ticket = seeded_workflow.tickets["en_progreso"]
    headers = auth_headers(seeded_workflow.users["tecnico_asignado"])
    request_id = uuid4()

    response = _transition(
        client,
        ticket,
        headers,
        "resuelto",
        resolution="   Se reinició el servicio y se verificó el acceso.   ",
        request_id=request_id,
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["changed"] is True
    assert payload["ticket"]["status"] == "resuelto"
    assert payload["ticket"]["finalized_at"] is not None
    assert payload["ticket"]["closed_at"] is None
    types = [entry["type"] for entry in payload["timeline_entries"]]
    assert types == ["status_change", "resolution"]
    resolution = payload["timeline_entries"][1]
    assert resolution["body"] == "Se reinició el servicio y se verificó el acceso."
    assert resolution["to_status"] == "resuelto"
    assert resolution["from_status"] is None

    entries = _entries(db, ticket)
    assert len(entries) == 2
    assert entries[0].event_order == 0
    assert entries[1].event_order == 1
    assert entries[0].created_at == entries[1].created_at
    assert all(entry.request_id == request_id for entry in entries)


def test_resolved_to_closed_keeps_finalized_and_sets_closed_at(
    client, db, seeded_workflow, auth_headers
) -> None:
    ticket = seeded_workflow.tickets["resuelto"]
    original_finalized = ticket.finalized_at
    headers = auth_headers(seeded_workflow.users["tecnico_asignado"])

    response = _transition(client, ticket, headers, "cerrado")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["ticket"]["status"] == "cerrado"
    assert payload["ticket"]["closed_at"] is not None
    assert _parse_ts(payload["ticket"]["finalized_at"]) == original_finalized
    assert payload["timeline_entries"][0]["type"] == "status_change"

    _reload(db, ticket)
    assert ticket.status == TicketStatus.cerrado
    assert ticket.closed_at is not None
    assert _as_utc(ticket.finalized_at) == _as_utc(original_finalized)


def test_reopen_clears_finalized_and_closed(
    client, db, seeded_workflow, auth_headers
) -> None:
    ticket = seeded_workflow.tickets["cerrado"]
    headers = auth_headers(seeded_workflow.users["tecnico_asignado"])
    # Un ticket cerrado no se reabre: primero se valida que esa transición no
    # existe y, para la reapertura real, se usa `resuelto -> en_progreso`.
    closed_response = _transition(client, ticket, headers, "en_progreso")
    assert closed_response.status_code == 409
    assert closed_response.json()["detail"]["code"] == "ticket_closed"

    resolved = seeded_workflow.tickets["resuelto"]
    response = _transition(client, resolved, headers, "en_progreso")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["ticket"]["status"] == "en_progreso"
    assert payload["ticket"]["finalized_at"] is None
    assert payload["ticket"]["closed_at"] is None
    _reload(db, resolved)
    assert resolved.finalized_at is None
    assert resolved.closed_at is None


# ---------------------------------------------------------------------------
# Rechazos y ausencia de escrituras
# ---------------------------------------------------------------------------
def test_invalid_transition_returns_409_without_writing(
    client, db, seeded_workflow, auth_headers
) -> None:
    ticket = seeded_workflow.tickets["abierto"]
    headers = auth_headers(seeded_workflow.users["tecnico_asignado"])

    response = _transition(
        client, ticket, headers, "resuelto", resolution="No permitido"
    )

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["code"] == "invalid_transition"
    assert "Abierto" in detail["message"]
    _reload(db, ticket)
    assert ticket.status == TicketStatus.abierto
    assert _entries(db, ticket) == []


def test_closed_ticket_returns_ticket_closed(
    client, db, seeded_workflow, auth_headers
) -> None:
    ticket = seeded_workflow.tickets["cerrado"]
    headers = auth_headers(seeded_workflow.users["tecnico_asignado"])

    response = _transition(client, ticket, headers, "en_progreso")

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "ticket_closed"
    assert _entries(db, ticket) == []


def test_same_status_is_noop_without_entries(
    client, db, seeded_workflow, auth_headers
) -> None:
    ticket = seeded_workflow.tickets["abierto"]
    headers = auth_headers(seeded_workflow.users["tecnico_asignado"])

    response = _transition(client, ticket, headers, "abierto")

    assert response.status_code == 200
    payload = response.json()
    assert payload["changed"] is False
    assert payload["timeline_entries"] == []
    assert payload["message"] == "El ticket ya se encuentra en ese estado."
    assert _entries(db, ticket) == []


def test_resolution_with_same_status_is_rejected(
    client, db, seeded_workflow, auth_headers
) -> None:
    ticket = seeded_workflow.tickets["abierto"]
    headers = auth_headers(seeded_workflow.users["tecnico_asignado"])
    original_updated_at = ticket.updated_at

    response = _transition(
        client, ticket, headers, "abierto", resolution="No procede"
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "resolution_not_allowed"
    _reload(db, ticket)
    assert ticket.status == TicketStatus.abierto
    assert as_utc(ticket.updated_at) == as_utc(original_updated_at)
    assert _entries(db, ticket) == []


def test_identical_replay_returns_changed_false(
    client, db, seeded_workflow, auth_headers
) -> None:
    ticket = seeded_workflow.tickets["abierto"]
    headers = auth_headers(seeded_workflow.users["tecnico_asignado"])
    request_id = uuid4()
    expected = _expected(client, ticket, headers)

    first = _transition(
        client,
        ticket,
        headers,
        "en_progreso",
        expected=expected,
        request_id=request_id,
    )
    assert first.status_code == 200
    assert first.json()["changed"] is True

    second = _transition(
        client,
        ticket,
        headers,
        "en_progreso",
        expected=expected,
        request_id=request_id,
    )

    assert second.status_code == 200
    payload = second.json()
    assert payload["changed"] is False
    assert payload["timeline_entries"] == []
    assert (
        payload["message"]
        == "Esta transición ya se aplicó con el identificador de solicitud indicado."
    )
    assert len(_entries(db, ticket)) == 1


def test_reused_request_id_with_other_target_returns_409(
    client, db, seeded_workflow, auth_headers
) -> None:
    ticket = seeded_workflow.tickets["abierto"]
    headers = auth_headers(seeded_workflow.users["tecnico_asignado"])
    request_id = uuid4()

    first = _transition(
        client, ticket, headers, "en_progreso", request_id=request_id
    )
    assert first.status_code == 200
    entries_after_first = len(_entries(db, ticket))

    second = _transition(
        client,
        ticket,
        headers,
        "resuelto",
        resolution="Otra cosa",
        request_id=request_id,
    )

    assert second.status_code == 409
    assert second.json()["detail"]["code"] == "request_id_reused"
    assert len(_entries(db, ticket)) == entries_after_first


def test_stale_expected_updated_at_returns_409_without_writing(
    client, db, seeded_workflow, auth_headers
) -> None:
    ticket = seeded_workflow.tickets["abierto"]
    headers = auth_headers(seeded_workflow.users["tecnico_asignado"])

    response = _transition(
        client,
        ticket,
        headers,
        "en_progreso",
        expected="2020-01-01T00:00:00+00:00",
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "stale_ticket"
    _reload(db, ticket)
    assert ticket.status == TicketStatus.abierto
    assert _entries(db, ticket) == []


@pytest.mark.parametrize(
    "body",
    [
        {
            "target_status": "invalido",
            "expected_updated_at": "2026-11-02T10:00:00+00:00",
            "request_id": "6f1c2a7e-9b3d-4f4e-8a1b-2c3d4e5f6a7b",
        },
        {
            "target_status": "en_progreso",
            "expected_updated_at": "no-es-una-fecha",
            "request_id": "6f1c2a7e-9b3d-4f4e-8a1b-2c3d4e5f6a7b",
        },
        {
            "target_status": "en_progreso",
            "expected_updated_at": "2026-11-02T10:00:00+00:00",
            "request_id": "no-es-un-uuid",
        },
        {
            "target_status": "en_progreso",
            "expected_updated_at": "2026-11-02T10:00:00+00:00",
        },
        {
            "target_status": "resuelto",
            "resolution": {"texto": "inválido"},
            "expected_updated_at": "2026-11-02T10:00:00+00:00",
            "request_id": "6f1c2a7e-9b3d-4f4e-8a1b-2c3d4e5f6a7b",
        },
    ],
)
def test_malformed_payload_returns_invalid_request(
    client, db, seeded_workflow, auth_headers, body
) -> None:
    ticket = seeded_workflow.tickets["abierto"]
    headers = auth_headers(seeded_workflow.users["tecnico_asignado"])

    response = client.post(
        _url(ticket, "status-transitions"), headers=headers, json=body
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_request"
    assert _entries(db, ticket) == []


# ---------------------------------------------------------------------------
# Resolución: validación, atomicidad e inmutabilidad
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("resolution", ["", "   ", "\n\t "])
def test_resolution_required(
    client, db, seeded_workflow, auth_headers, resolution
) -> None:
    ticket = seeded_workflow.tickets["en_progreso"]
    headers = auth_headers(seeded_workflow.users["tecnico_asignado"])

    response = _transition(
        client, ticket, headers, "resuelto", resolution=resolution
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "resolution_required"
    _reload(db, ticket)
    assert ticket.status == TicketStatus.en_progreso
    assert _entries(db, ticket) == []


def test_resolution_too_long(
    client, db, seeded_workflow, auth_headers
) -> None:
    ticket = seeded_workflow.tickets["en_progreso"]
    headers = auth_headers(seeded_workflow.users["tecnico_asignado"])

    response = _transition(
        client, ticket, headers, "resuelto", resolution="x" * 5001
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "resolution_too_long"
    _reload(db, ticket)
    assert ticket.status == TicketStatus.en_progreso
    assert _entries(db, ticket) == []


def test_resolution_not_allowed_for_other_target(
    client, db, seeded_workflow, auth_headers
) -> None:
    ticket = seeded_workflow.tickets["abierto"]
    headers = auth_headers(seeded_workflow.users["tecnico_asignado"])

    response = _transition(
        client, ticket, headers, "en_progreso", resolution="No procede"
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "resolution_not_allowed"
    assert _entries(db, ticket) == []


def test_resolution_is_visible_after_closing(
    client, seeded_workflow, auth_headers
) -> None:
    ticket = seeded_workflow.tickets["en_progreso"]
    headers = auth_headers(seeded_workflow.users["tecnico_asignado"])

    resolved = _transition(
        client, ticket, headers, "resuelto", resolution="Solución documentada."
    )
    assert resolved.status_code == 200
    closed = _transition(client, ticket, headers, "cerrado")
    assert closed.status_code == 200

    timeline = client.get(_url(ticket, "timeline"), headers=headers)
    assert timeline.status_code == 200
    items = timeline.json()["items"]
    resolutions = [item for item in items if item["type"] == "resolution"]
    assert len(resolutions) == 1
    assert resolutions[0]["body"] == "Solución documentada."


def test_reopen_and_resolve_again_keeps_previous_resolution(
    client, db, seeded_workflow, auth_headers
) -> None:
    ticket = seeded_workflow.tickets["en_progreso"]
    headers = auth_headers(seeded_workflow.users["tecnico_asignado"])

    first = _transition(
        client, ticket, headers, "resuelto", resolution="Primera solución."
    )
    assert first.status_code == 200
    first_resolution = _entries(db, ticket)[1]
    first_body = first_resolution.body
    first_created_at = first_resolution.created_at

    reopened = _transition(client, ticket, headers, "en_progreso")
    assert reopened.status_code == 200
    second = _transition(
        client, ticket, headers, "resuelto", resolution="Segunda solución."
    )
    assert second.status_code == 200

    db.expire_all()
    resolutions = [
        entry
        for entry in _entries(db, ticket)
        if entry.event_type == TimelineEventType.resolution
    ]
    assert [entry.body for entry in resolutions] == [
        "Primera solución.",
        "Segunda solución.",
    ]
    assert resolutions[0].body == first_body
    assert resolutions[0].created_at == first_created_at


# ---------------------------------------------------------------------------
# T029A — Inmutabilidad (sin PATCH/PUT/DELETE y sin reescritura)
# ---------------------------------------------------------------------------
def test_no_mutation_endpoints_exist(
    client, seeded_workflow, auth_headers
) -> None:
    ticket = seeded_workflow.tickets["en_progreso"]
    headers = auth_headers(seeded_workflow.users["tecnico_asignado"])

    for method in ("patch", "put"):
        response = getattr(client, method)(
            _url(ticket, "status-transitions"),
            headers=headers,
            json={},
        )
        assert response.status_code == 405, method

    assert (
        client.delete(_url(ticket, "status-transitions"), headers=headers).status_code
        == 405
    )

    assert (
        client.delete(_url(ticket, "timeline"), headers=headers).status_code
        == 405
    )
    assert (
        client.patch(_url(ticket, "timeline"), headers=headers, json={}).status_code
        == 405
    )
    # No existe una ruta para editar o borrar una entrada concreta.
    entry_id = uuid4()
    assert (
        client.delete(
            _url(ticket, f"timeline/{entry_id}"), headers=headers
        ).status_code
        == 404
    )


def test_resolution_body_is_not_rewritten(
    client, db, seeded_workflow, auth_headers
) -> None:
    ticket = seeded_workflow.tickets["en_progreso"]
    headers = auth_headers(seeded_workflow.users["tecnico_asignado"])

    first = _transition(
        client,
        ticket,
        headers,
        "resuelto",
        resolution="   Texto normalizado con espacios.   ",
    )
    assert first.status_code == 200
    original = _entries(db, ticket)[1]
    assert original.body == "Texto normalizado con espacios."

    # Un nuevo envío a `resuelto` es un no-op aunque cambie la resolución.
    again = _transition(
        client, ticket, headers, "resuelto", resolution="Otro texto distinto."
    )
    assert again.status_code == 200
    assert again.json()["changed"] is False
    db.expire_all()
    stored = [
        entry
        for entry in _entries(db, ticket)
        if entry.event_type == TimelineEventType.resolution
    ]
    assert len(stored) == 1
    assert stored[0].body == original.body
    assert stored[0].created_at == original.created_at

    closed = _transition(client, ticket, headers, "cerrado")
    assert closed.status_code == 200
    db.expire_all()
    stored = [
        entry
        for entry in _entries(db, ticket)
        if entry.event_type == TimelineEventType.resolution
    ]
    assert stored[0].body == original.body
    assert stored[0].created_at == original.created_at


# ---------------------------------------------------------------------------
# Transición automática de HU-03
# ---------------------------------------------------------------------------
def test_apply_user_response_transition_uses_creator_as_author(
    db, seeded_workflow
) -> None:
    ticket = seeded_workflow.tickets["pendiente_usuario"]
    creator = seeded_workflow.users["creador"]
    request_id = uuid4()

    result = apply_user_response_transition(
        db,
        ticket,
        creator,
        request_id=request_id,
        expected_updated_at=ticket.updated_at,
    )
    db.commit()

    assert result.changed is True
    assert result.ticket.status == TicketStatus.en_progreso
    assert result.timeline_entries[0].author.id == creator.id
    db.expire_all()
    entries = _entries(db, ticket)
    assert len(entries) == 1
    assert entries[0].event_type == TimelineEventType.status_change
    assert entries[0].author_id == creator.id
    assert entries[0].is_internal is False
    assert entries[0].body is None


def test_apply_user_response_transition_participates_in_caller_transaction(
    db, seeded_workflow
) -> None:
    """RF-005: la función no confirma por sí sola; HU-03 controla el commit."""

    ticket = seeded_workflow.tickets["pendiente_usuario"]
    creator = seeded_workflow.users["creador"]
    original_status = ticket.status

    result = apply_user_response_transition(
        db,
        ticket,
        creator,
        request_id=uuid4(),
        expected_updated_at=ticket.updated_at,
    )
    assert result.changed is True

    db.rollback()
    db.expire_all()

    reloaded = db.get(Ticket, ticket.id)
    assert reloaded is not None
    assert reloaded.status == original_status
    assert _entries(db, ticket) == []


def test_apply_user_response_transition_is_idempotent(
    db, seeded_workflow
) -> None:
    ticket = seeded_workflow.tickets["pendiente_usuario"]
    creator = seeded_workflow.users["creador"]
    request_id = uuid4()

    first = apply_user_response_transition(
        db,
        ticket,
        creator,
        request_id=request_id,
        expected_updated_at=ticket.updated_at,
    )
    db.commit()

    second = apply_user_response_transition(
        db,
        ticket,
        creator,
        request_id=request_id,
        expected_updated_at=ticket.updated_at,
    )

    assert first.changed is True
    assert second.changed is False
    assert second.timeline_entries == []
    assert len(_entries(db, ticket)) == 1


def test_apply_user_response_transition_rejects_reused_request_id(
    db, seeded_workflow, timeline_entry_factory
) -> None:
    ticket = seeded_workflow.tickets["pendiente_usuario"]
    creator = seeded_workflow.users["creador"]
    assigned = seeded_workflow.users["tecnico_asignado"]
    request_id = uuid4()
    timeline_entry_factory(
        ticket=ticket,
        author=assigned,
        event_type=TimelineEventType.status_change,
        from_status=TicketStatus.abierto,
        to_status=TicketStatus.en_progreso,
        request_id=request_id,
    )

    with pytest.raises(ApiError) as excinfo:
        apply_user_response_transition(
            db,
            ticket,
            creator,
            request_id=request_id,
            expected_updated_at=ticket.updated_at,
        )

    assert excinfo.value.status_code == 409
    assert excinfo.value.code == "request_id_reused"
    assert len(_entries(db, ticket)) == 1


def test_apply_user_response_transition_rejects_stale_preloaded_ticket(
    db, seeded_workflow
) -> None:
    """Regresión T071: la validación usa la fila bloqueada, no el identity map.

    El llamador de HU-03 precarga el ticket, otra transacción confirma un
    cambio y después se invoca la transición. La instancia del llamador sigue
    obsoleta; el servicio debe releer la fila tras `FOR UPDATE` y responder
    `409 stale_ticket` sin escribir una segunda entrada.
    """

    from app.db.session import SessionLocal

    ticket = seeded_workflow.tickets["pendiente_usuario"]
    creator = seeded_workflow.users["creador"]
    expected = as_utc(ticket.updated_at)
    assert expected is not None

    # HU-03 precarga el ticket en su sesión antes de ejecutar la transición.
    assert db.get(Ticket, ticket.id) is ticket

    other: Session = SessionLocal()
    try:
        other.execute(
            update(Ticket)
            .where(Ticket.id == ticket.id)
            .values(updated_at=expected + timedelta(seconds=5))
        )
        other.commit()
    finally:
        other.close()

    # El identity map del llamador conserva la versión anterior.
    assert db.get(Ticket, ticket.id) is ticket
    assert as_utc(ticket.updated_at) == expected

    with pytest.raises(ApiError) as excinfo:
        apply_user_response_transition(
            db,
            ticket,
            creator,
            request_id=uuid4(),
            expected_updated_at=expected,
        )

    assert excinfo.value.status_code == 409
    assert excinfo.value.code == "stale_ticket"
    assert _entries(db, ticket) == []


# ---------------------------------------------------------------------------
# T050 / T050A — Auditoría de legado e invariantes
# ---------------------------------------------------------------------------
def test_legacy_audit_lists_tickets_without_resolution_before_migration(
    db, seeded_workflow
) -> None:
    legacy = _legacy_without_resolution(db)
    numbers = {number for _, number in legacy}

    assert "TK-000504" in numbers
    assert "TK-000505" in numbers
    # Los tickets legado quedan excluidos de la aserción «resuelto ⇒ resolución».
    assert _resolved_without_resolution_since_migration(db) == []


def test_invariants_hold_after_transitions(
    client, db, seeded_workflow, auth_headers
) -> None:
    headers = auth_headers(seeded_workflow.users["tecnico_asignado"])
    ticket = seeded_workflow.tickets["en_progreso"]

    assert (
        _transition(
            client, ticket, headers, "resuelto", resolution="Solución final."
        ).status_code
        == 200
    )

    # Resuelto ⇒ resolución (solo tickets posteriores a la migración).
    assert _resolved_without_resolution_since_migration(db) == []

    # El último `status_change` coincide con `tickets.status`.
    db.expire_all()
    last = db.scalars(
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
    assert last is not None
    assert last.event_type == TimelineEventType.status_change
    assert last.to_status == _reload(db, ticket).status

    # finalized_at ⇔ estado final; closed_at solo en cerrado.
    for row in db.scalars(select(Ticket)).all():
        if row.status in (TicketStatus.resuelto, TicketStatus.cerrado):
            assert row.finalized_at is not None, row.number
        else:
            assert row.finalized_at is None, row.number
        if row.closed_at is not None:
            assert row.status == TicketStatus.cerrado, row.number
