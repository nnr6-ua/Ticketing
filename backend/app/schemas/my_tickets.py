"""Esquemas del listado «Mis tickets» (tickets creados por el usuario)."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from pydantic import BaseModel, field_serializer

from app.models.enums import TicketStatus


def _iso_utc(value: datetime) -> str:
    normalized = (
        value.replace(tzinfo=timezone.utc)
        if value.tzinfo is None
        else value.astimezone(timezone.utc)
    )
    return normalized.isoformat().replace("+00:00", "Z")


class MyTicketCategory(BaseModel):
    id: UUID
    name: str


class MyTicketPriority(BaseModel):
    id: UUID
    name: str
    level: int
    color: str | None = None


class MyTicketSummary(BaseModel):
    id: UUID
    ticket_number: str
    title: str
    status: TicketStatus
    status_label: str
    category: MyTicketCategory | None = None
    priority: MyTicketPriority
    created_at: datetime
    updated_at: datetime

    @field_serializer("created_at", "updated_at")
    def _serialize_datetime(self, value: datetime) -> str:
        return _iso_utc(value)


class MyTicketsResponse(BaseModel):
    items: list[MyTicketSummary]
