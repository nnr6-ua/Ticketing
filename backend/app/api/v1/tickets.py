"""Endpoints del flujo de trabajo del ticket (HU-05).

El router es una capa de traducción HTTP: toda la lógica de negocio, la
idempotencia y las decisiones `changed`/`created` viven en
`app.services.ticket_workflow` y `app.services.ticket_timeline`.
"""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.errors import ApiError, WORKFLOW_WRITE_ERROR_MESSAGE
from app.db.session import get_session
from app.models import Ticket, User
from app.schemas.ticket_workflow import (
    InternalCommentRequest,
    InternalCommentResponse,
    StatusTransitionRequest,
    StatusTransitionResponse,
    TimelineResponse,
    WorkflowResponse,
)
from app.services.ticket_timeline import can_read_ticket, get_timeline
from app.services.ticket_workflow import (
    add_internal_comment,
    change_status,
    get_workflow,
)

router = APIRouter(tags=["Flujo del ticket"])

logger = logging.getLogger(__name__)

NOT_FOUND_MESSAGE = "No se ha encontrado el ticket."


def _not_found() -> ApiError:
    return ApiError(404, "ticket_not_found", NOT_FOUND_MESSAGE)


def _write_error(ticket_id: UUID, action: str) -> ApiError:
    """Traduce un fallo inesperado de escritura al error del catálogo HU-05."""

    logger.exception(
        "Error inesperado al %s ticket_id=%s", action, ticket_id
    )
    return ApiError(500, "internal_error", WORKFLOW_WRITE_ERROR_MESSAGE)


def _readable_ticket(session: Session, ticket_id: UUID, user: User) -> Ticket:
    """Carga el ticket solo si el usuario puede leerlo.

    Nunca revela la existencia de tickets ajenos: ambos casos (inexistente y
    sin permiso) devuelven el mismo `404 ticket_not_found`.
    """

    ticket = session.get(Ticket, ticket_id)
    if ticket is None or not can_read_ticket(user, ticket):
        raise _not_found()
    return ticket


def _no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"
    response.headers["Vary"] = "Authorization"


@router.get(
    "/tickets/{ticket_id}/workflow",
    response_model=WorkflowResponse,
    summary="Obtener el estado actual y los estados permitidos",
    responses={
        401: {"description": "Token JWT ausente, inválido o caducado."},
        404: {"description": "El ticket no existe o no es accesible."},
        500: {"description": "Error inesperado del servidor."},
    },
)
def get_ticket_workflow(
    ticket_id: UUID,
    response: Response,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> WorkflowResponse:
    ticket = _readable_ticket(session, ticket_id, current_user)
    result = get_workflow(session, ticket, current_user)
    _no_store(response)
    return result


@router.post(
    "/tickets/{ticket_id}/status-transitions",
    response_model=StatusTransitionResponse,
    summary="Cambiar el estado del ticket y documentar la resolución",
    responses={
        401: {"description": "Token JWT ausente, inválido o caducado."},
        403: {"description": "Rol o asignación no autorizados."},
        404: {"description": "El ticket no existe."},
        409: {
            "description": (
                "Transición no permitida, ticket cerrado, versión "
                "desactualizada o request_id reutilizado."
            )
        },
        422: {"description": "Resolución o payload no válidos."},
        500: {"description": "Error inesperado del servidor."},
    },
)
def create_status_transition(
    ticket_id: UUID,
    payload: StatusTransitionRequest,
    response: Response,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> StatusTransitionResponse:
    try:
        result = change_status(session, ticket_id, current_user, payload)
    except ApiError:
        raise
    except Exception as exc:  # noqa: BLE001 - se traduce a error estable
        raise _write_error(ticket_id, "cambiar el estado") from exc
    _no_store(response)
    return result


@router.post(
    "/tickets/{ticket_id}/internal-comments",
    response_model=InternalCommentResponse,
    summary="Añadir un comentario interno",
    responses={
        200: {"description": "Reintento idempotente: la entrada ya existía."},
        201: {"description": "Comentario interno creado."},
        401: {"description": "Token JWT ausente, inválido o caducado."},
        403: {"description": "Rol o asignación no autorizados."},
        404: {"description": "El ticket no existe."},
        409: {"description": "request_id reutilizado con otros datos."},
        422: {"description": "Comentario o payload no válidos."},
        500: {"description": "Error inesperado del servidor."},
    },
)
def create_internal_comment(
    ticket_id: UUID,
    payload: InternalCommentRequest,
    response: Response,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> InternalCommentResponse:
    try:
        result = add_internal_comment(session, ticket_id, current_user, payload)
    except ApiError:
        raise
    except Exception as exc:  # noqa: BLE001 - se traduce a error estable
        raise _write_error(ticket_id, "añadir el comentario") from exc
    response.status_code = 201 if result.created else 200
    _no_store(response)
    return result


@router.get(
    "/tickets/{ticket_id}/timeline",
    response_model=TimelineResponse,
    summary="Obtener la línea temporal visible para el usuario",
    responses={
        401: {"description": "Token JWT ausente, inválido o caducado."},
        404: {"description": "El ticket no existe o no es accesible."},
        422: {"description": "Parámetros de paginación inválidos."},
        500: {"description": "Error inesperado del servidor."},
    },
)
def get_ticket_timeline(
    ticket_id: UUID,
    response: Response,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> TimelineResponse:
    ticket = _readable_ticket(session, ticket_id, current_user)
    result = get_timeline(
        session, ticket, current_user, page=page, page_size=page_size
    )
    _no_store(response)
    return result
