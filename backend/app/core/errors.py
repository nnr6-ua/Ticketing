"""Errores homogéneos de la API.

Formato de respuesta acordado en el contrato:

    {"detail": {"code": "...", "message": "..."}}

Los mensajes van en español de España y nunca exponen detalles internos.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

WORK_QUEUE_ERROR_MESSAGE = "No se pudo cargar la cola de trabajo."
WORKFLOW_WRITE_ERROR_MESSAGE = (
    "No se pudo guardar el cambio. El ticket no se ha modificado. "
    "Inténtalo de nuevo."
)
ADMIN_FORBIDDEN_MESSAGE = (
    "Esta configuración está disponible solo para administración."
)
CONFIGURATION_ERROR_MESSAGES: dict[str, str] = {
    "stale_configuration": (
        "La configuración ha cambiado. Recarga y vuelve a intentarlo."
    ),
    "duplicate_catalog_name": "Ya existe una entidad con ese nombre.",
    "duplicate_priority_level": "Ya hay una prioridad activa con ese nivel.",
    "duplicate_sla_rule": "Ya existe una regla vigente para esa combinación.",
    "last_active_catalog_item": (
        "No se puede desactivar la última entidad activa."
    ),
    "default_replacement_required": (
        "Designa otra entidad predeterminada antes de desactivar la actual."
    ),
    "catalog_in_use": (
        "La entidad tiene tickets o reglas asociadas. Desactívala en su lugar."
    ),
    "default_catalog_item": (
        "Designa otra entidad predeterminada antes de eliminar esta."
    ),
    "system_catalog_item": "Las entidades de sistema no se pueden modificar.",
    "inactive_catalog_item": "La categoría o la prioridad no está activa.",
    "inactive_default_catalog_item": (
        "Una entidad inactiva no puede ser predeterminada."
    ),
    "invalid_hours": "El plazo debe ser un número positivo de horas.",
    "invalid_date_range": "La fecha inicial no puede ser posterior a la final.",
    "empty_batch": "El lote no contiene cambios.",
    "configuration_not_initialized": (
        "La configuración base no está inicializada."
    ),
    "configuration_not_configured": (
        "No hay un plazo SLA válido para la combinación seleccionada."
    ),
}


class ApiError(Exception):
    """Error de negocio o de autenticación con código y mensaje estables."""

    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def error_response(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"detail": {"code": code, "message": message}},
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Registra los manejadores de error de la aplicación."""

    @app.exception_handler(ApiError)
    async def _handle_api_error(_: Request, exc: ApiError) -> JSONResponse:
        return error_response(exc.status_code, exc.code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def _handle_validation_error(
        _: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # Los payloads y parámetros mal formados se normalizan a un único
        # código estable; el detalle interno nunca se expone al cliente.
        logger.info("Solicitud no válida: %s", exc.errors())
        return error_response(
            422,
            "invalid_request",
            "La solicitud no es válida. Revisa los datos e inténtalo de nuevo.",
        )

    @app.exception_handler(Exception)
    async def _handle_unexpected_error(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Error inesperado al servir la cola de trabajo: %s", exc)
        return error_response(
            500,
            "internal_error",
            WORK_QUEUE_ERROR_MESSAGE,
        )
