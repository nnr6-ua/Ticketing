"""Servicio de lectura de la cola de trabajo priorizada.

Tres consultas sobre la misma base (tickets del técnico autenticado):

1. `items` de la página solicitada, con el orden de urgencia completo.
2. `COUNT(*)` con los filtros de la petición (`pagination.total_items`).
3. Agregado sin filtros para `counts.active` / `counts.finalized`.

`available_filters` también se calcula sobre toda la cola del técnico.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import Select, case, func, select
from sqlalchemy.orm import Session

from app.models import (
    DEFAULT_ACTIVE_STATUSES,
    FINAL_STATUSES,
    STATUS_LABELS,
    Category,
    Priority,
    SlaOutcome,
    SlaState,
    Ticket,
    TicketStatus,
    User,
)
from app.schemas.work_queue import (
    AppliedFilters,
    AvailableFilters,
    CategoryRef,
    Counts,
    Links,
    Meta,
    Pagination,
    PriorityFilterOption,
    PriorityRef,
    SlaInfo,
    StatusFilterOption,
    WarningPolicy,
    WorkQueueItem,
    WorkQueueQuery,
    WorkQueueResponse,
)
from app.utils.sla import (
    as_utc,
    breach_delay_seconds,
    classify_sla,
    sla_outcome,
    warning_threshold_seconds,
)

DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 100


def _finals_condition():
    return Ticket.status.in_(FINAL_STATUSES)


def _sla_info(ticket: Ticket, now: datetime) -> SlaInfo:
    """Calcula los derivados de SLA de un ticket sin persistirlos."""

    is_final = ticket.status.is_final
    deadline = as_utc(ticket.sla_deadline) if ticket.sla_deadline else None
    started_at = as_utc(ticket.created_at) if ticket.created_at else None
    has_sla = (
        deadline is not None
        and started_at is not None
        and deadline > started_at
    )

    if is_final:
        outcome = (
            sla_outcome(ticket.finalized_at, deadline) if has_sla else SlaOutcome.no_sla
        )
        return SlaInfo(
            deadline=deadline if has_sla else None,
            started_at=started_at if has_sla else None,
            total_seconds=(
                math.floor((deadline - started_at).total_seconds()) if has_sla else None
            ),
            remaining_seconds=None,
            warning_threshold_seconds=None,
            state=SlaState.finalized,
            outcome=outcome,
            finalized_at=as_utc(ticket.finalized_at) if ticket.finalized_at else None,
            breach_delay_seconds=(
                breach_delay_seconds(ticket.finalized_at, deadline) if has_sla else None
            ),
        )

    if not has_sla:
        return SlaInfo(
            deadline=None,
            started_at=None,
            total_seconds=None,
            remaining_seconds=None,
            warning_threshold_seconds=None,
            state=SlaState.no_sla,
            outcome=None,
            finalized_at=None,
            breach_delay_seconds=None,
        )

    total_seconds = math.floor((deadline - started_at).total_seconds())
    remaining_seconds = math.floor((deadline - as_utc(now)).total_seconds())
    return SlaInfo(
        deadline=deadline,
        started_at=started_at,
        total_seconds=total_seconds,
        remaining_seconds=remaining_seconds,
        warning_threshold_seconds=warning_threshold_seconds(total_seconds),
        state=classify_sla(
            is_final=False,
            deadline=deadline,
            started_at=started_at,
            now=now,
        ),
        outcome=None,
        finalized_at=None,
        breach_delay_seconds=None,
    )


def _to_item(ticket: Ticket, now: datetime) -> WorkQueueItem:
    category = (
        CategoryRef(
            id=ticket.category.id,
            name=ticket.category.name,
            is_active=ticket.category.is_active,
        )
        if ticket.category is not None
        else None
    )
    priority = PriorityRef(
        id=ticket.priority.id,
        name=ticket.priority.name,
        level=ticket.priority.level,
        color=ticket.priority.color,
        is_active=ticket.priority.is_active,
    )
    return WorkQueueItem(
        id=ticket.id,
        number=ticket.number,
        title=ticket.title,
        category=category,
        priority=priority,
        status=ticket.status,
        status_label=STATUS_LABELS[ticket.status],
        is_final=ticket.status.is_final,
        sla=_sla_info(ticket, now),
        links=Links(self_link=f"/api/v1/tickets/{ticket.id}"),
    )


def _ordered_statement(
    user_id: UUID,
    statuses: tuple[TicketStatus, ...],
    priorities: tuple[int, ...],
) -> Select:
    """Consulta base con propiedad, filtros y el orden de urgencia fijado."""

    is_final = case((_finals_condition(), 1), else_=0)

    statement = (
        select(Ticket)
        .join(Priority, Priority.id == Ticket.priority_id)
        .where(Ticket.assignee_id == user_id)
        .where(Ticket.status.in_(statuses))
    )
    if priorities:
        statement = statement.where(Priority.level.in_(priorities))

    return statement.order_by(
        is_final.asc(),
        case(
            (_finals_condition(), None),
            else_=Priority.level,
        ).asc().nulls_last(),
        case(
            (_finals_condition(), None),
            else_=Ticket.sla_deadline,
        ).asc().nulls_last(),
        case(
            (_finals_condition(), Ticket.finalized_at),
            else_=None,
        ).desc().nulls_last(),
        Ticket.number.asc(),
    )


def _counts(session: Session, user_id: UUID) -> Counts:
    """Activos y finalizados de toda la cola, sin aplicar filtros."""

    statement = select(
        func.coalesce(
            func.sum(case((_finals_condition(), 0), else_=1)),
            0,
        ).label("active"),
        func.coalesce(
            func.sum(case((_finals_condition(), 1), else_=0)),
            0,
        ).label("finalized"),
    ).where(Ticket.assignee_id == user_id)

    active, finalized = session.execute(statement).one()
    return Counts(active=int(active or 0), finalized=int(finalized or 0))


def _available_priorities(session: Session, user_id: UUID) -> list[PriorityFilterOption]:
    """Prioridades presentes en la cola del técnico, sin contadores."""

    statement = (
        select(Priority)
        .join(Ticket, Ticket.priority_id == Priority.id)
        .where(Ticket.assignee_id == user_id)
        .distinct()
        .order_by(Priority.level.asc(), Priority.name.asc())
    )
    rows = session.scalars(statement).unique().all()
    return [
        PriorityFilterOption(
            id=priority.id,
            name=priority.name,
            level=priority.level,
            color=priority.color,
            is_active=priority.is_active,
        )
        for priority in rows
    ]


def build_work_queue(
    session: Session,
    current_user: User,
    query: WorkQueueQuery,
    *,
    now: datetime | None = None,
) -> WorkQueueResponse:
    """Ensambla la respuesta completa de `GET /api/v1/me/work-queue`."""

    request_now = as_utc(now) if now is not None else datetime.now(timezone.utc)
    statuses = query.parsed_statuses()
    priorities = query.parsed_priorities()

    page_size = max(1, min(query.page_size, MAX_PAGE_SIZE))

    filtered_count = session.scalar(
        select(func.count())
        .select_from(Ticket)
        .join(Priority, Priority.id == Ticket.priority_id)
        .where(Ticket.assignee_id == current_user.id)
        .where(Ticket.status.in_(statuses))
        .where(
            Priority.level.in_(priorities) if priorities else True
        )
    ) or 0
    total_items = int(filtered_count)

    total_pages = math.ceil(total_items / page_size) if total_items else 0
    effective_page = min(query.page, total_pages) if total_pages else 1
    offset = (effective_page - 1) * page_size

    statement = _ordered_statement(current_user.id, statuses, priorities)
    tickets = (
        session.scalars(statement.offset(offset).limit(page_size)).unique().all()
    )
    items = [_to_item(ticket, request_now) for ticket in tickets]

    has_previous = total_pages > 0 and effective_page > 1
    has_next = total_pages > 0 and effective_page < total_pages

    status_options = [
        StatusFilterOption(
            value=status,
            label=STATUS_LABELS[status],
            is_final=status.is_final,
        )
        for status in TicketStatus
    ]

    return WorkQueueResponse(
        items=items,
        pagination=Pagination(
            page=effective_page,
            page_size=page_size,
            total_items=total_items,
            total_pages=total_pages,
            has_next=has_next,
            has_previous=has_previous,
        ),
        counts=_counts(session, current_user.id),
        available_filters=AvailableFilters(
            statuses=status_options,
            priorities=_available_priorities(session, current_user.id),
            default_statuses=list(DEFAULT_ACTIVE_STATUSES),
        ),
        applied_filters=AppliedFilters(
            status=list(statuses),
            priority=list(priorities),
            is_default=query.status is None and query.priority is None,
        ),
        meta=Meta(
            server_time=request_now,
            timezone="Europe/Madrid",
            warning_policy=WarningPolicy(),
        ),
    )
