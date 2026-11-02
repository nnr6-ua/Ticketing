"""Stub temporal de autenticación para desarrollo local.

Permite obtener un JWT válido para los usuarios creados por
`scripts/seed_dev.py` sin depender de un proveedor de autenticación externo.
Solo se registra si `AUTH_DEV_STUB_ENABLED=true`; nunca debe habilitarse en
producción ni en entornos compartidos.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ApiError
from app.db.session import get_session
from app.models import User

router = APIRouter(prefix="/dev", tags=["dev"])

DEFAULT_EMAIL = "tecnico.a@example.com"
TOKEN_TTL_SECONDS = 8 * 60 * 60


class DevLoginRequest(BaseModel):
    """Usuario del seed para el que se emite el token."""

    email: str = DEFAULT_EMAIL


class DevUser(BaseModel):
    id: str
    email: str
    name: str
    role: str


class DevLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: DevUser


@router.post("/login", response_model=DevLoginResponse)
def dev_login(
    payload: DevLoginRequest | None = None,
    session: Session = Depends(get_session),
) -> DevLoginResponse:
    """Emite un JWT de prueba para un usuario activo del seed."""

    settings = get_settings()
    if not settings.auth_dev_stub_enabled:
        raise ApiError(
            404,
            "not_found",
            "El stub de autenticación de desarrollo no está habilitado.",
        )

    if not settings.jwt_secret:
        raise ApiError(
            503,
            "dev_stub_unavailable",
            "El stub de desarrollo requiere JWT_SECRET configurado.",
        )

    email = (payload.email if payload else DEFAULT_EMAIL).strip().lower()
    user = session.scalar(select(User).where(User.email == email))
    if user is None or not user.is_active:
        raise ApiError(
            404,
            "dev_user_not_found",
            (
                "No existe un usuario activo con ese correo. Ejecuta el seed de "
                "desarrollo y vuelve a intentarlo."
            ),
        )

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=TOKEN_TTL_SECONDS)
    claims: dict[str, object] = {
        "sub": str(user.id),
        "role": user.role.value,
        "iat": now,
        "exp": expires_at,
    }
    if settings.auth_issuer:
        claims["iss"] = settings.auth_issuer
    if settings.auth_audience:
        claims["aud"] = settings.auth_audience

    token = jwt.encode(claims, settings.jwt_secret, algorithm=settings.jwt_algorithm)

    return DevLoginResponse(
        access_token=token,
        expires_in=TOKEN_TTL_SECONDS,
        user=DevUser(
            id=str(user.id),
            email=user.email,
            name=user.name,
            role=user.role.value,
        ),
    )
