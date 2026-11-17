"""Endpoints de la bandeja de notificaciones personal (HU-06)."""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.errors import ApiError, WORKFLOW_WRITE_ERROR_MESSAGE
from app.db.session import get_session
from app.models import User
from app.schemas.notification import (
    MarkNotificationReadResponse,
    NotificationListResponse,
)
from app.services.notifications import list_notifications, mark_notification_read

router = APIRouter(tags=["Notificaciones"])

logger = logging.getLogger(__name__)


def _no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"
    response.headers["Vary"] = "Authorization"


@router.get(
    "/me/notifications",
    response_model=NotificationListResponse,
    summary="Obtener las notificaciones del usuario autenticado",
    responses={
        401: {"description": "Token JWT ausente, inválido o caducado."},
        422: {"description": "Parámetros de paginación inválidos."},
        500: {"description": "Error inesperado del servidor."},
    },
)
def get_my_notifications(
    response: Response,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    unread_only: bool = Query(default=False),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> NotificationListResponse:
    result = list_notifications(
        session,
        current_user,
        page=page,
        page_size=page_size,
        unread_only=unread_only,
    )
    _no_store(response)
    return result


@router.post(
    "/me/notifications/{notification_id}/read",
    response_model=MarkNotificationReadResponse,
    summary="Marcar una notificación como leída",
    responses={
        401: {"description": "Token JWT ausente, inválido o caducado."},
        404: {
            "description": (
                "La notificación no existe o no pertenece al usuario."
            )
        },
        500: {"description": "Error inesperado del servidor."},
    },
)
def mark_my_notification_read(
    notification_id: UUID,
    response: Response,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> MarkNotificationReadResponse:
    try:
        result = mark_notification_read(session, current_user, notification_id)
    except ApiError:
        raise
    except Exception as exc:  # noqa: BLE001 - se traduce a error estable
        logger.exception(
            "Error inesperado al marcar la notificación notification_id=%s",
            notification_id,
        )
        raise ApiError(
            500, "internal_error", WORKFLOW_WRITE_ERROR_MESSAGE
        ) from exc
    _no_store(response)
    return result
