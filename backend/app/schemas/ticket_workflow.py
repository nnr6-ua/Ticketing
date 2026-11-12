"""Esquemas Pydantic del flujo de trabajo del ticket (HU-05).

Pydantic valida únicamente la forma y los tipos (UUID, enum, fecha ISO). Las
reglas de negocio (longitudes de resolución y comentario, transiciones) se
validan en `app.services.ticket_workflow` para conservar códigos de error
estables.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import TicketStatus, TimelineEventType, UserRole


class _Schema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class StatusOption(_Schema):
    value: TicketStatus
    label: str


class AuthorRef(_Schema):
    id: UUID
    name: str
    role: UserRole


class TimelineEntry(_Schema):
    id: UUID
    type: TimelineEventType
    from_status: TicketStatus | None = None
    to_status: TicketStatus | None = None
    body: str | None = None
    is_internal: bool
    author: AuthorRef
    created_at: datetime


class TicketWorkflowSnapshot(_Schema):
    id: UUID
    number: str
    title: str
    status: TicketStatus
    status_label: str
    assignee_id: UUID | None = None
    creator_id: UUID
    finalized_at: datetime | None = None
    closed_at: datetime | None = None
    updated_at: datetime
    allowed_transitions: list[StatusOption] = Field(default_factory=list)


class WorkflowResponse(_Schema):
    ticket: TicketWorkflowSnapshot
    can_change_status: bool
    can_comment_internally: bool
    can_view_internal: bool


class StatusTransitionRequest(_Schema):
    target_status: TicketStatus
    resolution: str | None = None
    expected_updated_at: datetime
    request_id: UUID


class StatusTransitionResponse(_Schema):
    changed: bool
    message: str | None = None
    ticket: TicketWorkflowSnapshot
    timeline_entries: list[TimelineEntry] = Field(default_factory=list)


class InternalCommentRequest(_Schema):
    body: str
    request_id: UUID


class InternalCommentResponse(_Schema):
    entry: TimelineEntry
    created: bool


class Pagination(_Schema):
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=200)
    total_items: int = Field(ge=0)
    total_pages: int = Field(ge=0)
    has_next: bool
    has_previous: bool


class TimelineResponse(_Schema):
    items: list[TimelineEntry]
    pagination: Pagination
