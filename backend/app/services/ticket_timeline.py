"""Lectura de la línea temporal y capacidades del visor (HU-05)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    ESCALATION_LEVEL_LABELS,
    EscalationLevel,
    Ticket,
    TicketStatus,
    TicketTimelineEntry,
    TimelineEventType,
    User,
    UserRole,
)
from app.schemas.ticket_workflow import (
    AssigneeRef,
    AuthorRef,
    InformationRequestRef,
    Pagination,
    TimelineEntry,
    TimelineResponse,
)
from app.services.ticket_state_machine import allowed_transitions

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200
INFORMATION_REMINDER_HOURS = 48

UTC = timezone.utc


@dataclass(frozen=True)
class ViewerCapabilities:
    can_view_internal: bool
    can_change_status: bool
    can_comment_internally: bool
    can_request_information: bool
    can_respond_to_information: bool
    awaiting_user_response: bool


@dataclass(frozen=True)
class InformationState:
    """Petición activa y recordatorio derivados de la línea temporal."""

    pending_since: datetime | None = None
    active_request: TicketTimelineEntry | None = None
    reminder_due_at: datetime | None = None
    reminder_active: bool = False


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
    is_technician = user.role == UserRole.tecnico
    awaiting_user_response = ticket.status == TicketStatus.pendiente_usuario
    return ViewerCapabilities(
        can_view_internal=can_view_internal,
        can_change_status=can_change_status,
        can_comment_internally=is_assignee,
        can_request_information=(
            is_assignee
            and is_technician
            and ticket.status == TicketStatus.en_progreso
        ),
        can_respond_to_information=(
            user.id == ticket.creator_id and awaiting_user_response
        ),
        awaiting_user_response=awaiting_user_response,
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
        reply_to_id=entry.reply_to_id,
        change_kind=entry.change_kind,
        previous_assignee=(
            assignee_ref(entry.previous_assignee)
            if entry.previous_assignee is not None
            else None
        ),
        new_assignee=(
            assignee_ref(entry.new_assignee)
            if entry.new_assignee is not None
            else None
        ),
        from_escalation_level=entry.from_escalation_level,
        from_escalation_level_label=escalation_level_label(
            entry.from_escalation_level
        ),
        to_escalation_level=entry.to_escalation_level,
        to_escalation_level_label=escalation_level_label(
            entry.to_escalation_level
        ),
    )


def escalation_level_label(level: EscalationLevel | None) -> str | None:
    if level is None:
        return None
    return ESCALATION_LEVEL_LABELS[level]


def assignee_ref(user: User) -> AssigneeRef:
    """DTO público del responsable, sin datos internos ni correo."""

    level = user.escalation_level or EscalationLevel.nivel_1
    return AssigneeRef(
        id=user.id,
        name=user.name,
        role=user.role,
        team=user.team,
        escalation_level=level,
        escalation_level_label=ESCALATION_LEVEL_LABELS[level],
    )


def information_request_ref(
    entry: TicketTimelineEntry,
) -> InformationRequestRef:
    """DTO de la petición activa a partir de su entrada de línea temporal."""

    return InformationRequestRef(
        id=entry.id,
        body=entry.body or "",
        requested_at=as_utc(entry.created_at) or entry.created_at,
        requested_by=AuthorRef(
            id=entry.author.id,
            name=entry.author.name,
            role=entry.author.role,
        ),
    )


def _latest_pending_changes(
    session: Session, ticket_ids: list[UUID]
) -> dict[UUID, TicketTimelineEntry]:
    if not ticket_ids:
        return {}
    statement = (
        select(TicketTimelineEntry)
        .where(
            TicketTimelineEntry.ticket_id.in_(ticket_ids),
            TicketTimelineEntry.event_type == TimelineEventType.status_change,
            TicketTimelineEntry.to_status == TicketStatus.pendiente_usuario,
        )
        .order_by(
            TicketTimelineEntry.created_at.asc(),
            TicketTimelineEntry.event_order.asc(),
            TicketTimelineEntry.id.asc(),
        )
    )
    latest: dict[UUID, TicketTimelineEntry] = {}
    for entry in session.scalars(statement).unique().all():
        latest[entry.ticket_id] = entry
    return latest


def _latest_information_requests(
    session: Session, ticket_ids: list[UUID]
) -> dict[UUID, TicketTimelineEntry]:
    if not ticket_ids:
        return {}
    statement = (
        select(TicketTimelineEntry)
        .where(
            TicketTimelineEntry.ticket_id.in_(ticket_ids),
            TicketTimelineEntry.event_type
            == TimelineEventType.information_request,
        )
        .order_by(
            TicketTimelineEntry.created_at.asc(),
            TicketTimelineEntry.event_order.asc(),
            TicketTimelineEntry.id.asc(),
        )
    )
    latest: dict[UUID, TicketTimelineEntry] = {}
    for entry in session.scalars(statement).unique().all():
        latest[entry.ticket_id] = entry
    return latest


def _responded_request_ids(
    session: Session, ticket_ids: list[UUID]
) -> set[UUID]:
    if not ticket_ids:
        return set()
    statement = select(TicketTimelineEntry.reply_to_id).where(
        TicketTimelineEntry.ticket_id.in_(ticket_ids),
        TicketTimelineEntry.event_type == TimelineEventType.user_response,
        TicketTimelineEntry.reply_to_id.is_not(None),
    )
    return {row[0] for row in session.execute(statement).all() if row[0]}


def information_states(
    session: Session,
    tickets: list[Ticket],
    *,
    now: datetime | None = None,
) -> dict[UUID, InformationState]:
    """Calcula petición activa y recordatorio por lote (sin N+1)."""

    if not tickets:
        return {}

    current = as_utc(now) or as_utc(datetime.now(UTC)) or datetime.now(UTC)
    ticket_ids = [ticket.id for ticket in tickets]
    pending_changes = _latest_pending_changes(session, ticket_ids)
    latest_requests = _latest_information_requests(session, ticket_ids)
    responded = _responded_request_ids(session, ticket_ids)

    states: dict[UUID, InformationState] = {}
    for ticket in tickets:
        pending_change = pending_changes.get(ticket.id)
        pending_since = (
            as_utc(pending_change.created_at) if pending_change else None
        )
        active_request = None
        if (
            ticket.status == TicketStatus.pendiente_usuario
            and pending_change is not None
        ):
            candidate = latest_requests.get(ticket.id)
            if candidate is not None and candidate.id not in responded:
                candidate_created = as_utc(candidate.created_at)
                if (
                    candidate_created is not None
                    and pending_since is not None
                    and candidate_created >= pending_since
                ):
                    active_request = candidate

        reminder_due_at = (
            pending_since + timedelta(hours=INFORMATION_REMINDER_HOURS)
            if pending_since is not None
            else None
        )
        reminder_active = (
            ticket.status == TicketStatus.pendiente_usuario
            and reminder_due_at is not None
            and current >= reminder_due_at
        )
        states[ticket.id] = InformationState(
            pending_since=pending_since,
            active_request=active_request,
            reminder_due_at=reminder_due_at,
            reminder_active=reminder_active,
        )
    return states


def information_state(
    session: Session,
    ticket: Ticket,
    *,
    now: datetime | None = None,
) -> InformationState:
    return information_states(session, [ticket], now=now)[ticket.id]


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
