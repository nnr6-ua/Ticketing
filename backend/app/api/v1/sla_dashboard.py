"""Endpoints GET del dashboard de cumplimiento de SLA (HU-07).

El router solo orquesta: valida los parámetros, delega en el servicio y fija
las cabeceras de no caché. Toda la lógica de negocio vive en
``app/services/sla_dashboard.py``.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps import require_supervisor_or_admin
from app.core.errors import ApiError
from app.db.session import get_session
from app.models import User
from app.schemas.sla_dashboard import (
    SlaDashboardOptions,
    SlaDashboardResponse,
)
from app.services.sla_dashboard import (
    DashboardQuery,
    build_sla_dashboard,
    build_sla_dashboard_options,
)

router = APIRouter(tags=["Dashboard de SLA"])

_NO_STORE_HEADERS = {
    "Cache-Control": "no-store",
    "Vary": "Authorization",
}


def _apply_no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"
    response.headers["Vary"] = "Authorization"


def _error_response(error: ApiError) -> JSONResponse:
    return JSONResponse(
        status_code=error.status_code,
        content={"detail": {"code": error.code, "message": error.message}},
        headers=_NO_STORE_HEADERS,
    )


@router.get(
    "/sla-dashboard",
    response_model=SlaDashboardResponse,
    summary="Snapshot completo del dashboard de cumplimiento de SLA",
    responses={
        401: {"description": "Token JWT ausente, inválido o caducado."},
        403: {"description": "El usuario autenticado no es supervisor ni admin."},
        422: {"description": "Filtros de consulta inválidos."},
    },
)
def get_sla_dashboard(
    response: Response,
    desde: str | None = Query(
        default=None,
        description=(
            "Fecha inicial (día natural Europe/Madrid, incluido), "
            "formato YYYY-MM-DD."
        ),
    ),
    hasta: str | None = Query(
        default=None,
        description=(
            "Fecha final (día natural Europe/Madrid, incluido), "
            "formato YYYY-MM-DD."
        ),
    ),
    categorias: str | None = Query(
        default=None,
        description=(
            "UUIDs de categoría separados por coma; `sin_categoria` incluye "
            "los tickets sin categoría."
        ),
    ),
    prioridades: str | None = Query(
        default=None,
        description="Niveles de prioridad separados por coma (1 a 4).",
    ),
    current_user: User = Depends(require_supervisor_or_admin),
    session: Session = Depends(get_session),
) -> SlaDashboardResponse | JSONResponse:
    query = DashboardQuery(
        desde=desde,
        hasta=hasta,
        categorias=categorias,
        prioridades=prioridades,
    )
    try:
        result = build_sla_dashboard(session, query)
    except ApiError as error:
        return _error_response(error)

    _apply_no_store(response)
    return result


@router.get(
    "/sla-dashboard/options",
    response_model=SlaDashboardOptions,
    summary="Opciones de filtro presentes en el periodo",
    responses={
        401: {"description": "Token JWT ausente, inválido o caducado."},
        403: {"description": "El usuario autenticado no es supervisor ni admin."},
        422: {"description": "Fechas de consulta inválidas."},
    },
)
def get_sla_dashboard_options(
    response: Response,
    desde: str | None = Query(default=None),
    hasta: str | None = Query(default=None),
    current_user: User = Depends(require_supervisor_or_admin),
    session: Session = Depends(get_session),
) -> SlaDashboardOptions | JSONResponse:
    query = DashboardQuery(desde=desde, hasta=hasta)
    try:
        result = build_sla_dashboard_options(session, query)
    except ApiError as error:
        return _error_response(error)

    _apply_no_store(response)
    return result
