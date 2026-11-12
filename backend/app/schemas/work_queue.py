"""Esquemas Pydantic de la cola de trabajo.

Los nombres de campo coinciden con el contrato OpenAPI
(`specs/004-prioritized-work-queue/contracts/work-queue.openapi.yaml`).
Todas las fechas se normalizan a UTC al serializar y se emiten con sufijo `Z`.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

from app.core.errors import ApiError
from app.models.enums import (
    DEFAULT_ACTIVE_STATUSES,
    STATUS_LABELS,
    SlaOutcome,
    SlaState,
    TicketStatus,
)

UTC = timezone.utc


def to_utc(value: datetime | None) -> datetime | None:
    """Normaliza un instante a UTC; asume UTC si llega sin zona (SQLite)."""

    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _iso_utc(value: datetime | None) -> str | None:
    normalized = to_utc(value)
    if normalized is None:
        return None
    return normalized.isoformat().replace("+00:00", "Z")


class CategoryRef(BaseModel):
    id: UUID
    name: str
    is_active: bool


class PriorityRef(BaseModel):
    id: UUID
    name: str
    level: int = Field(ge=1, le=4)
    color: str | None = None
    is_active: bool


class Links(BaseModel):
    """Enlaces de solo lectura del ticket."""

    model_config = ConfigDict(populate_by_name=True)

    self_link: str = Field(alias="self")


class SlaInfo(BaseModel):
    deadline: datetime | None = None
    started_at: datetime | None = None
    total_seconds: int | None = Field(default=None, ge=0)
    remaining_seconds: int | None = None
    warning_threshold_seconds: int | None = Field(default=None, ge=0)
    state: SlaState
    outcome: SlaOutcome | None = None
    finalized_at: datetime | None = None
    breach_delay_seconds: int | None = Field(default=None, ge=0)

    @field_serializer("deadline", "started_at", "finalized_at", when_used="json")
    def _serialize_datetimes(self, value: datetime | None) -> str | None:
        return _iso_utc(value)


class WorkQueueItem(BaseModel):
    id: UUID
    number: str
    title: str
    category: CategoryRef | None
    priority: PriorityRef
    status: TicketStatus
    status_label: str
    is_final: bool
    sla: SlaInfo
    links: Links

    @field_validator("status_label", mode="before")
    @classmethod
    def _default_label(cls, value: str | None, info) -> str:
        if value:
            return value
        status = info.data.get("status")
        return STATUS_LABELS[status] if status else ""


class Pagination(BaseModel):
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    total_items: int = Field(ge=0)
    total_pages: int = Field(ge=0)
    has_next: bool
    has_previous: bool


class Counts(BaseModel):
    active: int = Field(ge=0)
    finalized: int = Field(ge=0)


class StatusFilterOption(BaseModel):
    value: TicketStatus
    label: str
    is_final: bool


class PriorityFilterOption(BaseModel):
    id: UUID
    name: str
    level: int = Field(ge=1, le=4)
    color: str | None = None
    is_active: bool


class AvailableFilters(BaseModel):
    statuses: list[StatusFilterOption]
    priorities: list[PriorityFilterOption]
    default_statuses: list[TicketStatus]


class AppliedFilters(BaseModel):
    status: list[TicketStatus]
    priority: list[int]
    is_default: bool


class WarningPolicy(BaseModel):
    short_sla_threshold_minutes: int = 60
    short_sla_ratio: float = 0.5
    long_sla_minimum_minutes: int = 60
    long_sla_ratio: float = 0.25


class Meta(BaseModel):
    server_time: datetime
    timezone: str = "Europe/Madrid"
    warning_policy: WarningPolicy = Field(default_factory=WarningPolicy)

    @field_serializer("server_time", when_used="json")
    def _serialize_server_time(self, value: datetime) -> str:
        return _iso_utc(value) or ""


class WorkQueueResponse(BaseModel):
    items: list[WorkQueueItem]
    pagination: Pagination
    counts: Counts
    available_filters: AvailableFilters
    applied_filters: AppliedFilters
    meta: Meta


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    detail: ErrorDetail


class WorkQueueQuery(BaseModel):
    """Parámetros de consulta ya validados por FastAPI."""

    status: str | None = None
    priority: str | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=25, ge=1, le=100)

    def parsed_statuses(self) -> tuple[TicketStatus, ...]:
        """Devuelve los estados solicitados o los activos por defecto."""

        if self.status is None:
            return DEFAULT_ACTIVE_STATUSES

        parts = [part.strip() for part in self.status.split(",")]
        if not parts or any(part == "" for part in parts):
            raise ApiError(
                422,
                "invalid_query_parameter",
                "El filtro de estado no es válido.",
            )

        statuses: list[TicketStatus] = []
        for part in parts:
            try:
                status = TicketStatus(part)
            except ValueError as exc:
                raise ApiError(
                    422,
                    "invalid_query_parameter",
                    f"El estado «{part}» no es válido.",
                ) from exc
            if status not in statuses:
                statuses.append(status)
        return tuple(statuses)

    def parsed_priorities(self) -> tuple[int, ...]:
        """Devuelve los niveles de prioridad solicitados, sin duplicados."""

        if self.priority is None:
            return ()

        parts = [part.strip() for part in self.priority.split(",")]
        if not parts or any(part == "" for part in parts):
            raise ApiError(
                422,
                "invalid_query_parameter",
                "El filtro de prioridad no es válido.",
            )

        levels: list[int] = []
        for part in parts:
            if not part.isdigit() or not 1 <= int(part) <= 4:
                raise ApiError(
                    422,
                    "invalid_query_parameter",
                    f"La prioridad «{part}» no es válida.",
                )
            level = int(part)
            if level not in levels:
                levels.append(level)
        return tuple(sorted(levels))
