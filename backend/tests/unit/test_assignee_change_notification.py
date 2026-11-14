"""Pruebas unitarias de `create_assignee_change_notification` (HU-06, T090)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    AssigneeChangeKind,
    EscalationLevel,
    Notification,
    NotificationType,
    TicketTimelineEntry,
    TimelineEventType,
)
from app.services.notifications import create_assignee_change_notification
from tests.conftest import SeededAssigneeChange

UTC = timezone.utc


def _entry(
    seed: SeededAssigneeChange,
    *,
    key: str = "entry",
    kind: AssigneeChangeKind = AssigneeChangeKind.reassignment,
    new_user=None,
    to_level=None,
) -> TicketTimelineEntry:
    ticket = seed.tickets["activo"]
    actor = seed.users["asignado"]
    new = new_user or seed.users["companero"]
    return TicketTimelineEntry(
        id=uuid.uuid5(uuid.NAMESPACE_DNS, f"hu06-notification-{key}"),
        ticket_id=ticket.id,
        event_type=TimelineEventType.assignee_change,
        from_status=None,
        to_status=None,
        body="Motivo que nunca debe copiarse a la notificación.",
        is_internal=False,
        author_id=actor.id,
        created_at=seed.now,
        event_order=0,
        request_id=uuid.uuid5(
            uuid.NAMESPACE_DNS, f"hu06-notification-request-{key}"
        ),
        previous_assignee_id=actor.id,
        new_assignee_id=new.id,
        change_kind=kind,
        from_escalation_level=actor.escalation_level,
        to_escalation_level=to_level or new.escalation_level,
    )


def test_notification_uses_public_snapshots(
    db: Session, seeded_assignee_change: SeededAssigneeChange
) -> None:
    seed = seeded_assignee_change
    ticket = seed.tickets["activo"]
    entry = _entry(seed)
    db.add(entry)
    db.flush()

    notification = create_assignee_change_notification(
        db,
        ticket,
        entry,
        seed.users["asignado"],
        seed.users["companero"],
        AssigneeChangeKind.reassignment,
        seed.now,
    )

    assert notification.recipient_id == seed.users["companero"].id
    assert notification.ticket_id == ticket.id
    assert notification.timeline_entry_id == entry.id
    assert notification.type == NotificationType.ticket_reassigned
    assert notification.ticket_number == ticket.number
    assert notification.ticket_title == ticket.title
    assert notification.previous_assignee_name == seed.users["asignado"].name
    assert notification.is_read is False
    assert notification.read_at is None
    assert notification.created_at == seed.now


def test_escalation_uses_escalated_type(
    db: Session, seeded_assignee_change: SeededAssigneeChange
) -> None:
    seed = seeded_assignee_change
    entry = _entry(
        seed,
        key="escalation",
        kind=AssigneeChangeKind.escalation,
        new_user=seed.users["nivel_2"],
        to_level=EscalationLevel.nivel_2,
    )
    db.add(entry)
    db.flush()

    notification = create_assignee_change_notification(
        db,
        seed.tickets["activo"],
        entry,
        seed.users["asignado"],
        seed.users["nivel_2"],
        AssigneeChangeKind.escalation,
        seed.now,
    )

    assert notification.type == NotificationType.ticket_escalated


def test_reason_is_not_stored_in_notification_row(
    db: Session, seeded_assignee_change: SeededAssigneeChange
) -> None:
    seed = seeded_assignee_change
    entry = _entry(seed)
    db.add(entry)
    db.flush()

    notification = create_assignee_change_notification(
        db,
        seed.tickets["activo"],
        entry,
        seed.users["asignado"],
        seed.users["companero"],
        AssigneeChangeKind.reassignment,
        seed.now,
    )
    db.commit()

    columns = {column.name for column in Notification.__table__.columns}
    assert "reason" not in columns
    assert "body" not in columns
    values = " ".join(
        str(getattr(notification, column.name)) for column in Notification.__table__.columns
    )
    assert entry.body not in values


def test_function_adds_without_committing(
    db: Session, seeded_assignee_change: SeededAssigneeChange
) -> None:
    seed = seeded_assignee_change
    entry = _entry(seed, key="no-commit")
    db.add(entry)
    db.flush()

    notification = create_assignee_change_notification(
        db,
        seed.tickets["activo"],
        entry,
        seed.users["asignado"],
        seed.users["companero"],
        AssigneeChangeKind.reassignment,
        seed.now,
    )

    assert notification in db.new
    db.rollback()
    assert db.scalar(select(func.count()).select_from(Notification)) == 0
    assert db.scalar(select(func.count()).select_from(TicketTimelineEntry)) == 0


def test_one_notification_per_timeline_entry(
    db: Session, seeded_assignee_change: SeededAssigneeChange
) -> None:
    seed = seeded_assignee_change
    entry = _entry(seed, key="unique")
    db.add(entry)
    db.flush()

    create_assignee_change_notification(
        db,
        seed.tickets["activo"],
        entry,
        seed.users["asignado"],
        seed.users["companero"],
        AssigneeChangeKind.reassignment,
        seed.now,
    )
    create_assignee_change_notification(
        db,
        seed.tickets["activo"],
        entry,
        seed.users["asignado"],
        seed.users["companero"],
        AssigneeChangeKind.reassignment,
        seed.now,
    )

    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    assert db.scalar(select(func.count()).select_from(Notification)) == 0


def test_created_at_is_normalized_to_utc(
    db: Session, seeded_assignee_change: SeededAssigneeChange
) -> None:
    seed = seeded_assignee_change
    entry = _entry(seed, key="utc")
    db.add(entry)
    db.flush()
    now = datetime.now(UTC)

    notification = create_assignee_change_notification(
        db,
        seed.tickets["activo"],
        entry,
        seed.users["asignado"],
        seed.users["companero"],
        AssigneeChangeKind.reassignment,
        now,
    )
    db.commit()

    assert notification.created_at.replace(tzinfo=UTC) == now
