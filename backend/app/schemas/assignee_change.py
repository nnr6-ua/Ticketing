"""Esquemas Pydantic del cambio de responsable (HU-06)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import (
    AssigneeChangeKind,
    EscalationLevel,
    TicketStatus,
)
from app.schemas.ticket_workflow import (
    AssigneeRef,
    TimelineEntry,
    TicketWorkflowSnapshot,
)


class _Schema(BaseModel):
    model_config = ConfigDict(extra="forbid")


__all__ = [
    "AssigneeChangeOptions",
    "AssigneeChangeResponse",
    "AssigneeRef",
    "EscalationRequest",
    "EscalationTarget",
    "ReassignmentRequest",
]


class EscalationTarget(_Schema):
    value: EscalationLevel
    label: str
    technician_count: int = Field(ge=0)
    is_available: bool


class AssigneeChangeOptions(_Schema):
    ticket_id: UUID
    status: TicketStatus
    current_assignee: AssigneeRef
    has_reassignment_candidates: bool
    has_available_escalation_target: bool
    reassignment_candidates: list[AssigneeRef] = Field(default_factory=list)
    escalation_targets: list[EscalationTarget] = Field(default_factory=list)


class ReassignmentRequest(_Schema):
    new_assignee_id: UUID
    reason: str
    expected_updated_at: datetime
    request_id: UUID


class EscalationRequest(_Schema):
    target_level: EscalationLevel
    reason: str
    expected_updated_at: datetime
    request_id: UUID


class AssigneeChangeResponse(_Schema):
    changed: bool
    message: str | None = None
    ticket: TicketWorkflowSnapshot
    previous_assignee: AssigneeRef
    new_assignee: AssigneeRef
    change_kind: AssigneeChangeKind
    from_escalation_level: EscalationLevel
    from_escalation_level_label: str
    to_escalation_level: EscalationLevel
    to_escalation_level_label: str
    timeline_entry: TimelineEntry | None = None
