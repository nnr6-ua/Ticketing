"""Esquemas Pydantic del dashboard de cumplimiento de SLA (HU-07).

Espejo exacto del contrato `specs/007-dashboard-cumplimiento-sla/contracts/
sla-dashboard.openapi.yaml`. Todas las fechas se normalizan a UTC al serializar
y se emiten con sufijo `Z`; los días naturales de filtro se expresan como
`date` (YYYY-MM-DD) en `Europe/Madrid`.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from app.utils.sla import SLA_AMBER_THRESHOLD_PCT, SLA_GREEN_THRESHOLD_PCT

UTC = timezone.utc

SlaSemaphore = Literal["verde", "ambar", "rojo", "sin_datos"]
TotalsScope = Literal["priority", "category", "global"]


def _iso_utc(value: datetime | None) -> str | None:
    if value is None:
        return None
    normalized = value if value.tzinfo else value.replace(tzinfo=UTC)
    return normalized.astimezone(UTC).isoformat().replace("+00:00", "Z")


class SlaSemaphoreModel(BaseModel):
    """Documental: el semáforo se modela como literal en cada métrica."""


class Thresholds(BaseModel):
    green_pct: float = Field(default=SLA_GREEN_THRESHOLD_PCT)
    amber_pct: float = Field(default=SLA_AMBER_THRESHOLD_PCT)


class ComplianceMetrics(BaseModel):
    ticket_count: int = Field(ge=0)
    no_sla_count: int = Field(ge=0)
    attended_with_sla: int = Field(ge=0)
    on_time: int = Field(ge=0)
    compliance_pct: float | None = None
    avg_response_seconds: float | None = None
    overdue_count: int = Field(ge=0)
    semaphore: SlaSemaphore


class MatrixRow(ComplianceMetrics):
    priority_level: int = Field(ge=1, le=4)
    priority_name: str
    priority_is_active: bool
    category_id: UUID | None = None
    category_name: str
    category_is_active: bool | None = None


class TotalsEntry(ComplianceMetrics):
    scope: TotalsScope
    priority_level: int | None = Field(default=None, ge=1, le=4)
    priority_name: str | None = None
    priority_is_active: bool | None = None
    category_id: UUID | None = None
    category_name: str | None = None
    category_is_active: bool | None = None


class RankingEntry(BaseModel):
    technician_id: UUID | None = None
    technician_name: str
    team: str | None = None
    is_active: bool | None = None
    overdue_count: int = Field(ge=0)
    avg_delay_seconds: float


class RankingBlock(BaseModel):
    technicians: list[RankingEntry]
    unassigned: RankingEntry | None = None
    overdue_total: int = Field(ge=0)


class SlaDashboardData(BaseModel):
    summary: ComplianceMetrics
    matrix: list[MatrixRow]
    priority_totals: list[TotalsEntry]
    category_totals: list[TotalsEntry]
    ranking: RankingBlock


class EffectiveFilters(BaseModel):
    desde: date
    hasta: date
    categorias: list[str] = Field(default_factory=list)
    prioridades: list[int] = Field(default_factory=list)


class SlaDashboardMeta(BaseModel):
    generated_at: datetime
    timezone: Literal["Europe/Madrid"] = "Europe/Madrid"
    thresholds: Thresholds = Field(default_factory=Thresholds)
    filters: EffectiveFilters
    has_tickets: bool

    @field_serializer("generated_at", when_used="json")
    def _serialize_generated_at(self, value: datetime) -> str:
        return _iso_utc(value) or ""


class SlaDashboardResponse(BaseModel):
    data: SlaDashboardData
    meta: SlaDashboardMeta


class FilterCategoryOption(BaseModel):
    id: UUID | None = None
    name: str
    is_active: bool | None = None


class FilterPriorityOption(BaseModel):
    level: int = Field(ge=1, le=4)
    name: str
    is_active: bool


class SlaDashboardOptions(BaseModel):
    desde: date
    hasta: date
    categories: list[FilterCategoryOption]
    priorities: list[FilterPriorityOption]


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    detail: ErrorDetail
