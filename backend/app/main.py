"""Aplicación FastAPI de la mesa de ayuda (HU-04)."""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.errors import register_exception_handlers

logging.basicConfig(level=logging.INFO)

settings = get_settings()

app = FastAPI(
    title="Mesa de ayuda · Cola de trabajo priorizada",
    version="1.0.0",
    description=(
        "Vista personal de solo lectura con los tickets asignados al técnico "
        "autenticado, ordenados por urgencia."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.frontend_origins.split(",") if origin.strip()],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Accept", "Content-Type"],
    expose_headers=["Cache-Control", "Vary"],
)

register_exception_handlers(app)
app.include_router(api_router, prefix="/api/v1")
