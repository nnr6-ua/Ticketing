"""Esquemas del contrato de creación de tickets (HU-01)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_serializer


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    email: str


class CategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str


class PriorityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    level: int
    color: str | None = None
    is_system: bool = False


class AttachmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    original_filename: str
    mime_type: str
    size_bytes: int


class TicketRead(BaseModel):
    id: UUID
    ticket_number: str
    title: str
    description: str
    status: str
    creator: UserRead
    category: CategoryRead
    priority: PriorityRead
    attachments: list[AttachmentRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    duplicate: bool = False
    sla_priority_level: int | None = None
    sla_hours_applied: Decimal | None = None
    sla_version: str | None = None
    sla_config_version_id: UUID | None = None

    @field_serializer("sla_hours_applied", when_used="json")
    def _serialize_sla_hours(self, value: Decimal | None) -> str | None:
        return None if value is None else f"{value:.2f}"


class SuggestionRequest(BaseModel):
    title: str = Field(min_length=0, max_length=120)
    description: str = Field(min_length=0, max_length=5000)


class SuggestionResponse(BaseModel):
    category: CategoryRead
    priority: PriorityRead
    category_is_fallback: bool
    priority_is_fallback: bool
