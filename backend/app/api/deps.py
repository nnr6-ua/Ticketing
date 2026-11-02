"""Dependencias de autenticación y autorización.

La identidad se resuelve **exclusivamente** del token JWT enviado en
`Authorization: Bearer <token>`. No se aceptan identificadores de técnico por
query string ni cookies de sesión.
"""

from __future__ import annotations

from uuid import UUID

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ApiError
from app.db.session import get_session
from app.models import User, UserRole

bearer_scheme = HTTPBearer(auto_error=False)

UNAUTHENTICATED_MESSAGE = "La sesión no es válida o ha caducado."


def _unauthorized() -> ApiError:
    return ApiError(401, "not_authenticated", UNAUTHENTICATED_MESSAGE)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: Session = Depends(get_session),
) -> User:
    """Valida el Bearer JWT y devuelve el usuario autenticado."""

    if credentials is None or not credentials.credentials:
        raise _unauthorized()

    settings = get_settings()
    if not settings.jwt_secret:
        # Sin secreto configurado no se puede validar ningún token: nunca se
        # aceptan peticiones anónimas ni se usan secretos embebidos.
        raise _unauthorized()

    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            audience=settings.auth_audience or None,
            issuer=settings.auth_issuer or None,
            options={"require": ["exp", "sub"]},
        )
    except jwt.PyJWTError as exc:
        raise _unauthorized() from exc

    subject = payload.get("sub")
    try:
        user_id = UUID(str(subject))
    except (TypeError, ValueError) as exc:
        raise _unauthorized() from exc

    user = session.get(User, user_id)
    if user is None or not user.is_active:
        raise _unauthorized()
    return user


def require_technician(current_user: User = Depends(get_current_user)) -> User:
    """Restringe la vista al rol `tecnico`."""

    if current_user.role != UserRole.tecnico:
        raise ApiError(
            403,
            "forbidden",
            "Esta vista está disponible solo para técnicos.",
        )
    return current_user
