from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class EmployeeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str


class CategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class PriorityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    level: int
    color: str
    is_system: bool


class AttachmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    original_filename: str
    mime_type: str
    size_bytes: int


class TicketRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticket_number: str
    title: str
    description: str
    status: str
    creator: EmployeeRead
    category: CategoryRead
    priority: PriorityRead
    attachments: list[AttachmentRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    duplicate: bool = False


class TicketCreateResponse(TicketRead):
    duplicate: bool = False


class SuggestionResponse(BaseModel):
    category: CategoryRead
    priority: PriorityRead
    category_is_fallback: bool
    priority_is_fallback: bool
