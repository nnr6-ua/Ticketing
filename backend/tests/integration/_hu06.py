"""Utilidades compartidas por las pruebas de integración de HU-06."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    Notification,
    Ticket,
    TicketTimelineEntry,
    TimelineEventType,
    User,
    UserRole,
)
from tests.conftest import SeededAssigneeChange

API = "/api/v1/tickets"
NOTIFICATIONS_API = "/api/v1/me/notifications"
UTC = timezone.utc


def url(ticket: Ticket, suffix: str) -> str:
    return f"{API}/{ticket.id}/{suffix}"


def workflow(client, ticket: Ticket, headers: dict[str, str]) -> dict:
    response = client.get(url(ticket, "workflow"), headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def expected_updated_at(client, ticket: Ticket, headers: dict[str, str]) -> str:
    return workflow(client, ticket, headers)["ticket"]["updated_at"]


def options(client, ticket: Ticket, headers: dict[str, str]):
    return client.get(url(ticket, "assignee-change-options"), headers=headers)


def reassign(
    client,
    ticket: Ticket,
    headers: dict[str, str],
    destination: User | UUID | str,
    *,
    reason: str = "Motivo de reasignación.",
    expected: str | None = None,
    request_id: UUID | str | None = None,
    body: dict | None = None,
):
    payload = body
    if payload is None:
        payload = {
            "new_assignee_id": str(
                destination.id if isinstance(destination, User) else destination
            ),
            "reason": reason,
            "expected_updated_at": expected
            or expected_updated_at(client, ticket, headers),
            "request_id": str(request_id or uuid.uuid4()),
        }
    return client.post(url(ticket, "reassignments"), headers=headers, json=payload)


def escalate(
    client,
    ticket: Ticket,
    headers: dict[str, str],
    target_level: str,
    *,
    reason: str = "Motivo de escalado.",
    expected: str | None = None,
    request_id: UUID | str | None = None,
    body: dict | None = None,
):
    payload = body
    if payload is None:
        payload = {
            "target_level": target_level,
            "reason": reason,
            "expected_updated_at": expected
            or expected_updated_at(client, ticket, headers),
            "request_id": str(request_id or uuid.uuid4()),
        }
    return client.post(url(ticket, "escalations"), headers=headers, json=payload)


def entries(
    db: Session,
    ticket: Ticket,
    event_type: TimelineEventType | None = None,
) -> list[TicketTimelineEntry]:
    db.expire_all()
    statement = select(TicketTimelineEntry).where(
        TicketTimelineEntry.ticket_id == ticket.id
    )
    if event_type is not None:
        statement = statement.where(
            TicketTimelineEntry.event_type == event_type
        )
    statement = statement.order_by(
        TicketTimelineEntry.created_at.asc(),
        TicketTimelineEntry.event_order.asc(),
        TicketTimelineEntry.id.asc(),
    )
    return list(db.scalars(statement).unique().all())


def notification_rows(db: Session, ticket: Ticket | None = None) -> list[Notification]:
    db.expire_all()
    statement = select(Notification)
    if ticket is not None:
        statement = statement.where(Notification.ticket_id == ticket.id)
    statement = statement.order_by(
        Notification.created_at.asc(), Notification.id.asc()
    )
    return list(db.scalars(statement).all())


def count_notifications(db: Session, ticket: Ticket | None = None) -> int:
    db.expire_all()
    statement = select(func.count()).select_from(Notification)
    if ticket is not None:
        statement = statement.where(Notification.ticket_id == ticket.id)
    return int(db.scalar(statement) or 0)


def reload_ticket(db: Session, ticket: Ticket) -> Ticket:
    db.expire_all()
    refreshed = db.get(Ticket, ticket.id)
    assert refreshed is not None
    return refreshed


def error_code(response) -> str:
    assert response.status_code >= 400, response.text
    return response.json()["detail"]["code"]


def make_user(
    db: Session,
    key: str,
    name: str,
    *,
    level: str = "nivel_1",
    team: str | None = "Soporte",
    role: UserRole = UserRole.tecnico,
    is_active: bool = True,
) -> User:
    from app.models import EscalationLevel

    row = User(
        id=uuid.uuid5(uuid.NAMESPACE_DNS, f"hu06-integration-{key}"),
        name=name,
        email=f"hu06.integration.{key}@example.com",
        role=role,
        team=team,
        escalation_level=EscalationLevel(level),
        is_active=is_active,
    )
    db.add(row)
    return row


def set_assignee(db: Session, ticket: Ticket, user: User) -> None:
    ticket.assignee_id = user.id
    db.commit()


def set_status(db: Session, ticket: Ticket, status) -> None:
    ticket.status = status
    db.commit()


def add_timeline_entry(
    db: Session,
    ticket: Ticket,
    *,
    seed: SeededAssigneeChange,
    previous,
    new,
    kind,
    key: str,
    body: str = "Entrada histórica de cambio de responsable.",
    created_at: datetime | None = None,
) -> TicketTimelineEntry:
    entry = TicketTimelineEntry(
        id=uuid.uuid5(uuid.NAMESPACE_DNS, f"hu06-history-{key}"),
        ticket_id=ticket.id,
        event_type=TimelineEventType.assignee_change,
        from_status=None,
        to_status=None,
        body=body,
        is_internal=False,
        author_id=previous.id,
        created_at=created_at or seed.now,
        event_order=0,
        request_id=uuid.uuid5(uuid.NAMESPACE_DNS, f"hu06-history-req-{key}"),
        previous_assignee_id=previous.id,
        new_assignee_id=new.id,
        change_kind=kind,
        from_escalation_level=previous.escalation_level,
        to_escalation_level=new.escalation_level,
    )
    db.add(entry)
    db.commit()
    return entry


def as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
