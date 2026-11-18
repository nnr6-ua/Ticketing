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

# El contrato del dashboard de SLA (HU-07) exige no-store también en 401/403/422.
# El prefijo evita alterar las respuestas de error del resto de endpoints.
SLA_DASHBOARD_PATH = "/api/v1/sla-dashboard"


class ApiError(Exception):
    """Error de negocio o de autenticación con código y mensaje estables."""

    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def error_response(
    status_code: int,
    code: str,
    message: str,
    *,
    request: Request | None = None,
) -> JSONResponse:
    headers = None
    if request is not None and request.url.path.startswith(SLA_DASHBOARD_PATH):
        headers = {"Cache-Control": "no-store", "Vary": "Authorization"}
    return JSONResponse(
        status_code=status_code,
        content={"detail": {"code": code, "message": message}},
        headers=headers,
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Registra los manejadores de error de la aplicación."""

    @app.exception_handler(ApiError)
    async def _handle_api_error(request: Request, exc: ApiError) -> JSONResponse:
        return error_response(
            exc.status_code, exc.code, exc.message, request=request
        )

    @app.exception_handler(RequestValidationError)
    async def _handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # Los payloads y parámetros mal formados se normalizan a un único
        # código estable; el detalle interno nunca se expone al cliente.
        logger.info("Solicitud no válida: %s", exc.errors())
        return error_response(
            422,
            "invalid_request",
            "La solicitud no es válida. Revisa los datos e inténtalo de nuevo.",
            request=request,
        )

    @app.exception_handler(Exception)
    async def _handle_unexpected_error(
        request: Request, exc: Exception
    ) -> JSONResponse:
        logger.exception("Error inesperado al servir la cola de trabajo: %s", exc)
        return error_response(
            500,
            "internal_error",
            WORK_QUEUE_ERROR_MESSAGE,
            request=request,
        )
