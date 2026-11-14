"""Esquemas Pydantic de la bandeja de notificaciones (HU-06)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import NotificationType


class _Schema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Notification(_Schema):
    id: UUID
    type: NotificationType
    ticket_id: UUID
    ticket_number: str
    ticket_title: str
    previous_assignee_name: str
    is_read: bool
    created_at: datetime
    read_at: datetime | None = None


class NotificationPagination(_Schema):
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    total_items: int = Field(ge=0)
    total_pages: int = Field(ge=0)
    has_next: bool
    has_previous: bool


class NotificationListResponse(_Schema):
    items: list[Notification] = Field(default_factory=list)
    unread_count: int = Field(ge=0)
    pagination: NotificationPagination


class MarkNotificationReadResponse(_Schema):
    changed: bool
    message: str | None = None
    notification: Notification
