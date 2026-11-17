"""Pruebas de visibilidad y orden de la línea temporal (HU-05, US3)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.models import (
    Ticket,
    TicketStatus,
    TicketTimelineEntry,
    TimelineEventType,
    User,
)
from app.services.ticket_state_machine import allowed_transitions

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


# ---------------------------------------------------------------------------
# HU-06 · Cambio de responsable en la línea temporal (T050, T092)
# ---------------------------------------------------------------------------
def test_assignee_change_entries_interleave_in_chronological_order(
    client, db, seeded_assignee_change, auth_headers, timeline_entry_factory
) -> None:
    seed = seeded_assignee_change
    ticket = seed.tickets["activo"]
    assigned = seed.users["asignado"]
    destination = seed.users["companero"]
    headers = auth_headers(assigned)

    # Hecho previo de HU-05 para comprobar el intercalado.
    timeline_entry_factory(
        ticket=ticket,
        author=assigned,
        event_type=TimelineEventType.status_change,
        from_status=TicketStatus.abierto,
        to_status=TicketStatus.en_progreso,
        created_at=seed.now - timedelta(minutes=10),
    )

    first = client.post(
        _url(ticket, "reassignments"),
        headers=headers,
        json={
            "new_assignee_id": str(destination.id),
            "reason": "Reasignación documentada.",
            "expected_updated_at": client.get(
                _url(ticket, "workflow"), headers=headers
            ).json()["ticket"]["updated_at"],
            "request_id": str(uuid.uuid4()),
        },
    )
    assert first.status_code == 200, first.text

    second = client.post(
        _url(ticket, "escalations"),
        headers=auth_headers(destination),
        json={
            "target_level": "nivel_2",
            "reason": "Escalado documentado.",
            "expected_updated_at": client.get(
                _url(ticket, "workflow"), headers=auth_headers(destination)
            ).json()["ticket"]["updated_at"],
            "request_id": str(uuid.uuid4()),
        },
    )
    assert second.status_code == 200, second.text

    payload = _timeline(client, ticket, headers).json()
    assert _types(payload) == [
        "status_change",
        "assignee_change",
        "assignee_change",
    ]

    reassignment_entry, escalation_entry = payload["items"][-2:]
    assert reassignment_entry["change_kind"] == "reassignment"
    assert reassignment_entry["body"] == "Reasignación documentada."
    assert reassignment_entry["is_internal"] is False
    assert reassignment_entry["previous_assignee"]["id"] == str(assigned.id)
    assert reassignment_entry["new_assignee"]["id"] == str(destination.id)
    assert reassignment_entry["from_escalation_level"] == "nivel_1"
    assert reassignment_entry["to_escalation_level"] == "nivel_1"

    assert escalation_entry["change_kind"] == "escalation"
    assert escalation_entry["body"] == "Escalado documentado."
    assert escalation_entry["from_escalation_level"] == "nivel_1"
    assert escalation_entry["to_escalation_level"] == "nivel_2"
    assert escalation_entry["to_escalation_level_label"] == "Nivel 2"
    assert escalation_entry["author"]["id"] == str(destination.id)

    created = [item["created_at"] for item in payload["items"]]
    assert created == sorted(created)


def test_creator_sees_assignee_change_but_not_internal_notes(
    client, db, seeded_assignee_change, auth_headers, timeline_entry_factory
) -> None:
    seed = seeded_assignee_change
    ticket = seed.tickets["activo"]
    creator = seed.users["creador_tecnico"]
    assigned = seed.users["asignado"]
    destination = seed.users["companero"]

    timeline_entry_factory(
        ticket=ticket,
        author=assigned,
        event_type=TimelineEventType.internal_comment,
        body="Nota interna del equipo.",
        is_internal=True,
        created_at=seed.now - timedelta(minutes=5),
    )

    response = client.post(
        _url(ticket, "reassignments"),
        headers=auth_headers(assigned),
        json={
            "new_assignee_id": str(destination.id),
            "reason": "Motivo público.",
            "expected_updated_at": client.get(
                _url(ticket, "workflow"), headers=auth_headers(assigned)
            ).json()["ticket"]["updated_at"],
            "request_id": str(uuid.uuid4()),
        },
    )
    assert response.status_code == 200, response.text

    payload = _timeline(client, ticket, auth_headers(creator)).json()
    assert _types(payload) == ["assignee_change"]
    item = payload["items"][0]
    assert item["body"] == "Motivo público."
    assert item["is_internal"] is False
    assert item["previous_assignee"]["name"] == assigned.name
    assert item["new_assignee"]["name"] == destination.name

    workflow = _workflow(client, ticket, auth_headers(creator)).json()
    assert workflow["can_view_internal"] is False
    assert workflow["can_reassign"] is False
    assert workflow["can_escalate"] is False


def test_previous_technician_keeps_public_timeline_and_loses_internal_access(
    client, db, seeded_assignee_change, auth_headers, timeline_entry_factory
) -> None:
    seed = seeded_assignee_change
    ticket = seed.tickets["activo"]
    previous = seed.users["asignado"]
    new_assignee = seed.users["companero"]

    timeline_entry_factory(
        ticket=ticket,
        author=previous,
        event_type=TimelineEventType.internal_comment,
        body="Nota interna anterior.",
        is_internal=True,
        created_at=seed.now - timedelta(minutes=5),
    )

    response = client.post(
        _url(ticket, "reassignments"),
        headers=auth_headers(previous),
        json={
            "new_assignee_id": str(new_assignee.id),
            "reason": "Traspaso.",
            "expected_updated_at": client.get(
                _url(ticket, "workflow"), headers=auth_headers(previous)
            ).json()["ticket"]["updated_at"],
            "request_id": str(uuid.uuid4()),
        },
    )
    assert response.status_code == 200, response.text

    previous_timeline = _timeline(client, ticket, auth_headers(previous))
    assert previous_timeline.status_code == 200, previous_timeline.text
    assert _types(previous_timeline.json()) == ["assignee_change"]

    previous_workflow = _workflow(client, ticket, auth_headers(previous)).json()
    assert previous_workflow["can_view_internal"] is False
    assert previous_workflow["can_change_status"] is False
    assert previous_workflow["can_comment_internally"] is False
    assert previous_workflow["can_reassign"] is False
    assert previous_workflow["can_escalate"] is False

    new_timeline = _timeline(client, ticket, auth_headers(new_assignee))
    assert _types(new_timeline.json()) == ["internal_comment", "assignee_change"]

    new_workflow = _workflow(client, ticket, auth_headers(new_assignee)).json()
    assert new_workflow["can_view_internal"] is True
    assert new_workflow["can_comment_internally"] is True
    assert new_workflow["can_reassign"] is True
    assert new_workflow["can_escalate"] is True


def test_rejections_and_replays_do_not_add_timeline_entries(
    client, db, seeded_assignee_change, auth_headers
) -> None:
    seed = seeded_assignee_change
    ticket = seed.tickets["activo"]
    assigned = seed.users["asignado"]
    destination = seed.users["companero"]
    headers = auth_headers(assigned)
    request_id = uuid.uuid4()

    expected = client.get(
        _url(ticket, "workflow"), headers=headers
    ).json()["ticket"]["updated_at"]
    body = {
        "new_assignee_id": str(destination.id),
        "reason": "Motivo.",
        "expected_updated_at": expected,
        "request_id": str(request_id),
    }

    rejected = client.post(
        _url(ticket, "reassignments"),
        headers=headers,
        json={**body, "reason": "   "},
    )
    assert rejected.status_code == 422
    assert _timeline(client, ticket, headers).json()["pagination"]["total_items"] == 0

    first = client.post(_url(ticket, "reassignments"), headers=headers, json=body)
    assert first.status_code == 200, first.text
    assert _timeline(client, ticket, headers).json()["pagination"]["total_items"] == 1

    replay = client.post(_url(ticket, "reassignments"), headers=headers, json=body)
    assert replay.status_code == 200, replay.text
    assert replay.json()["changed"] is False
    assert replay.json()["timeline_entry"] is None
    assert _timeline(client, ticket, headers).json()["pagination"]["total_items"] == 1

    stale = client.post(
        _url(ticket, "reassignments"),
        headers=auth_headers(destination),
        json={
            **body,
            "new_assignee_id": str(assigned.id),
            "expected_updated_at": "2000-01-01T00:00:00+00:00",
            "request_id": str(uuid.uuid4()),
        },
    )
    assert stale.status_code == 409
    assert _timeline(client, ticket, headers).json()["pagination"]["total_items"] == 1


def test_assignee_change_entry_distinguishes_kind_and_serializes_levels(
    client, db, seeded_assignee_change, auth_headers
) -> None:
    seed = seeded_assignee_change
    ticket = seed.tickets["activo"]
    assigned = seed.users["asignado"]
    destination = seed.users["companero"]

    reassignment = client.post(
        _url(ticket, "reassignments"),
        headers=auth_headers(assigned),
        json={
            "new_assignee_id": str(destination.id),
            "reason": "Reasignación.",
            "expected_updated_at": client.get(
                _url(ticket, "workflow"), headers=auth_headers(assigned)
            ).json()["ticket"]["updated_at"],
            "request_id": str(uuid.uuid4()),
        },
    )
    assert reassignment.status_code == 200, reassignment.text
    assert reassignment.json()["timeline_entry"]["change_kind"] == "reassignment"

    escalation = client.post(
        _url(ticket, "escalations"),
        headers=auth_headers(destination),
        json={
            "target_level": "especialista",
            "reason": "Escalado.",
            "expected_updated_at": client.get(
                _url(ticket, "workflow"), headers=auth_headers(destination)
            ).json()["ticket"]["updated_at"],
            "request_id": str(uuid.uuid4()),
        },
    )
    assert escalation.status_code == 200, escalation.text
    entry = escalation.json()["timeline_entry"]
    assert entry["change_kind"] == "escalation"
    assert entry["from_escalation_level"] == "nivel_1"
    assert entry["to_escalation_level"] == "especialista"
    assert entry["from_escalation_level_label"] == "Nivel 1"
    assert entry["to_escalation_level_label"] == "Especialista"

    payload = _timeline(client, ticket, auth_headers(assigned)).json()
    kinds = [
        item["change_kind"]
        for item in payload["items"]
        if item["type"] == "assignee_change"
    ]
    assert kinds == ["reassignment", "escalation"]
