"""Esquemas del contrato de creación de tickets (HU-01)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


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


class SuggestionRequest(BaseModel):
    title: str = Field(min_length=0, max_length=120)
    description: str = Field(min_length=0, max_length=5000)


class SuggestionResponse(BaseModel):
    category: CategoryRead
    priority: PriorityRead
    category_is_fallback: bool
    priority_is_fallback: bool
