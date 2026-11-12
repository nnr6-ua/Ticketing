"""Endpoint `GET /api/v1/me/work-queue`."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.api.deps import require_technician
from app.db.session import get_session
from app.models import User
from app.schemas.work_queue import WorkQueueQuery, WorkQueueResponse
from app.services.work_queue import build_work_queue

router = APIRouter(tags=["Cola de trabajo"])


@router.get(
    "/me/work-queue",
    response_model=WorkQueueResponse,
    summary="Obtener la cola de trabajo del técnico autenticado",
    responses={
        401: {"description": "Token JWT ausente, inválido o caducado."},
        403: {"description": "El usuario autenticado no tiene rol de técnico."},
        422: {"description": "Parámetros de consulta inválidos."},
        500: {"description": "Error inesperado del servidor."},
    },
)
def get_my_work_queue(
    response: Response,
    status: str | None = Query(
        default=None,
        description=(
            "Códigos de estado separados por coma. Por defecto: "
            "abierto,en_progreso,pendiente_usuario."
        ),
    ),
    priority: str | None = Query(
        default=None,
        description="Niveles de prioridad separados por coma (1 = Crítica, 4 = Baja).",
    ),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    current_user: User = Depends(require_technician),
    session: Session = Depends(get_session),
) -> WorkQueueResponse:
    query = WorkQueueQuery(
        status=status,
        priority=priority,
        page=page,
        page_size=page_size,
    )
    result = build_work_queue(session, current_user, query)

    response.headers["Cache-Control"] = "no-store"
    response.headers["Vary"] = "Authorization"
    return result
