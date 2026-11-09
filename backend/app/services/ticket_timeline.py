"""Lectura de la línea temporal y capacidades del visor (HU-05)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Ticket, TicketStatus, TicketTimelineEntry, User, UserRole
from app.schemas.ticket_workflow import (
    AuthorRef,
    Pagination,
    TimelineEntry,
    TimelineResponse,
)
from app.services.ticket_state_machine import allowed_transitions

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200

UTC = timezone.utc


@dataclass(frozen=True)
class ViewerCapabilities:
    can_view_internal: bool
    can_change_status: bool
    can_comment_internally: bool


def as_utc(value: datetime | None) -> datetime | None:
    """Normaliza a UTC; asume UTC si el valor llega sin zona (SQLite)."""

    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def viewer_capabilities(user: User, ticket: Ticket) -> ViewerCapabilities:
    """Capacidades calculadas en servidor a partir del rol y la asignación."""

    is_assignee = ticket.assignee_id is not None and user.id == ticket.assignee_id
    can_view_internal = is_assignee or user.role in (
        UserRole.supervisor,
        UserRole.admin,
    )
    can_change_status = (
        is_assignee
        and ticket.status != TicketStatus.cerrado
        and len(allowed_transitions(ticket.status)) > 0
    )
    return ViewerCapabilities(
        can_view_internal=can_view_internal,
        can_change_status=can_change_status,
        can_comment_internally=is_assignee,
    )


def can_read_ticket(user: User, ticket: Ticket) -> bool:
    """Acceso de lectura al ticket: creador o roles operativos."""

    return user.id == ticket.creator_id or user.role in (
        UserRole.tecnico,
        UserRole.supervisor,
        UserRole.admin,
    )


def serialize_entry(entry: TicketTimelineEntry) -> TimelineEntry:
    """Convierte una fila del modelo al DTO público."""

    return TimelineEntry(
        id=entry.id,
        type=entry.event_type,
        from_status=entry.from_status,
        to_status=entry.to_status,
        body=entry.body,
        is_internal=entry.is_internal,
        author=AuthorRef(
            id=entry.author.id,
            name=entry.author.name,
            role=entry.author.role,
        ),
        created_at=as_utc(entry.created_at) or entry.created_at,
    )


def get_timeline(
    session: Session,
    ticket: Ticket,
    user: User,
    *,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> TimelineResponse:
    """Página visible de la línea temporal, filtrada en SQL."""

    capabilities = viewer_capabilities(user, ticket)
    page = max(1, page)
    page_size = max(1, min(page_size, MAX_PAGE_SIZE))

    conditions = [TicketTimelineEntry.ticket_id == ticket.id]
    if not capabilities.can_view_internal:
        conditions.append(TicketTimelineEntry.is_internal.is_(False))

    total_items = int(
        session.scalar(
            select(func.count())
            .select_from(TicketTimelineEntry)
            .where(*conditions)
        )
        or 0
    )
    total_pages = math.ceil(total_items / page_size) if total_items else 0

    statement = (
        select(TicketTimelineEntry)
        .where(*conditions)
        .order_by(
            TicketTimelineEntry.created_at.asc(),
            TicketTimelineEntry.event_order.asc(),
            TicketTimelineEntry.id.asc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    entries = session.scalars(statement).unique().all()

    return TimelineResponse(
        items=[serialize_entry(entry) for entry in entries],
        pagination=Pagination(
            page=page,
            page_size=page_size,
            total_items=total_items,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_previous=page > 1,
        ),
    )


def ticket_by_id(session: Session, ticket_id: UUID) -> Ticket | None:
    """Carga un ticket por identificador."""

    return session.get(Ticket, ticket_id)
