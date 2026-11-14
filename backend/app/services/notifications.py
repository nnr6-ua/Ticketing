"""Servicio de notificaciones personales del cambio de responsable (HU-06)."""

from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import ApiError, WORKFLOW_WRITE_ERROR_MESSAGE
from app.models import (
    AssigneeChangeKind,
    Notification,
    NotificationType,
    Ticket,
    TicketTimelineEntry,
    User,
)
from app.schemas.notification import (
    MarkNotificationReadResponse,
    Notification as NotificationSchema,
    NotificationListResponse,
    NotificationPagination,
)
from app.services.ticket_timeline import as_utc

UTC = timezone.utc
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


def _notification_not_found() -> ApiError:
    return ApiError(
        404,
        "notification_not_found",
        "No se ha encontrado la notificación.",
    )


def create_assignee_change_notification(
    session: Session,
    ticket: Ticket,
    entry: TicketTimelineEntry,
    previous_assignee: User,
    new_assignee: User,
    kind: AssigneeChangeKind,
    now: datetime,
) -> Notification:
    """Construye y añade la notificación sin hacer `commit()`.

    Participa en la transacción del comando de cambio de responsable. Nunca
    guarda el motivo: solo snapshots públicos para la campana.
    """

    if entry.id is None:
        entry.id = uuid.uuid4()

    notification = Notification(
        recipient_id=new_assignee.id,
        ticket_id=ticket.id,
        timeline_entry_id=entry.id,
        type=(
            NotificationType.ticket_reassigned
            if kind == AssigneeChangeKind.reassignment
            else NotificationType.ticket_escalated
        ),
        ticket_number=ticket.number,
        ticket_title=ticket.title,
        previous_assignee_name=previous_assignee.name,
        is_read=False,
        created_at=now,
        read_at=None,
    )
    session.add(notification)
    return notification


def serialize_notification(row: Notification) -> NotificationSchema:
    return NotificationSchema(
        id=row.id,
        type=row.type,
        ticket_id=row.ticket_id,
        ticket_number=row.ticket_number,
        ticket_title=row.ticket_title,
        previous_assignee_name=row.previous_assignee_name,
        is_read=row.is_read,
        created_at=as_utc(row.created_at) or row.created_at,
        read_at=as_utc(row.read_at),
    )


def list_notifications(
    session: Session,
    user: User,
    *,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    unread_only: bool = False,
) -> NotificationListResponse:
    """Página de la bandeja del usuario y contador global de no leídas."""

    page = max(1, page)
    page_size = max(1, min(page_size, MAX_PAGE_SIZE))

    conditions = [Notification.recipient_id == user.id]
    if unread_only:
        conditions.append(Notification.is_read.is_(False))

    total_items = int(
        session.scalar(
            select(func.count()).select_from(Notification).where(*conditions)
        )
        or 0
    )
    total_pages = math.ceil(total_items / page_size) if total_items else 0

    unread_count = int(
        session.scalar(
            select(func.count())
            .select_from(Notification)
            .where(
                Notification.recipient_id == user.id,
                Notification.is_read.is_(False),
            )
        )
        or 0
    )

    rows = session.scalars(
        select(Notification)
        .where(*conditions)
        .order_by(
            Notification.created_at.desc(),
            Notification.id.desc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return NotificationListResponse(
        items=[serialize_notification(row) for row in rows],
        unread_count=unread_count,
        pagination=NotificationPagination(
            page=page,
            page_size=page_size,
            total_items=total_items,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_previous=page > 1,
        ),
    )


def mark_notification_read(
    session: Session, user: User, notification_id: UUID
) -> MarkNotificationReadResponse:
    """Marca como leída una notificación propia; idempotente."""

    notification = session.get(Notification, notification_id)
    if notification is None or notification.recipient_id != user.id:
        raise _notification_not_found()

    if notification.is_read:
        return MarkNotificationReadResponse(
            changed=False,
            message="La notificación ya estaba marcada como leída.",
            notification=serialize_notification(notification),
        )

    notification.is_read = True
    notification.read_at = datetime.now(UTC)
    try:
        session.commit()
    except Exception as exc:  # noqa: BLE001 - error estable de escritura
        session.rollback()
        raise ApiError(
            500, "internal_error", WORKFLOW_WRITE_ERROR_MESSAGE
        ) from exc

    return MarkNotificationReadResponse(
        changed=True,
        message=None,
        notification=serialize_notification(notification),
    )
