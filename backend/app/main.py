"""Aplicación FastAPI de la mesa de ayuda (HU-01 a HU-08)."""

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
    title="Mesa de ayuda · Sistema de tickets",
    version="1.0.0",
    description=(
        "API del sistema de mesa de ayuda: creación y seguimiento de tickets, "
        "cola priorizada, flujo de estados, reasignación y escalado, dashboard "
        "de cumplimiento SLA y configuración administrativa."
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
