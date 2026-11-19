"""Esquemas del contrato administrativo de configuración (HU-08)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

from app.core.errors import ApiError
from app.models.enums import ConfigAction, ConfigEntityType

HOURS = Annotated[
    Decimal,
    Field(gt=0, le=Decimal("9999.99"), max_digits=6, decimal_places=2),
]


def _hours(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return f"{value:.2f}"


def _iso_utc(value: datetime | None) -> str | None:
    if value is None:
        return None
    from datetime import timezone

    normalized = (
        value.replace(tzinfo=timezone.utc)
        if value.tzinfo is None
        else value.astimezone(timezone.utc)
    )
    return normalized.isoformat().replace("+00:00", "Z")


def _clean_keywords(values: list[str] | None) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values or []:
        clean = value.strip()
        if not clean:
            raise ValueError("Las palabras clave no pueden estar vacías.")
        if len(clean) > 50:
            raise ValueError("Cada palabra clave admite como máximo 50 caracteres.")
        key = clean.casefold()
        if key not in seen:
            result.append(clean)
            seen.add(key)
    return result


def _clean_name(value: str) -> str:
    clean = value.strip()
    if not clean:
        raise ValueError("El nombre es obligatorio.")
    return clean


class UserRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    email: str


class ConfigurationVersionRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    version: int
    created_at: datetime
    created_by: UserRef | None = None

    @field_serializer("created_at", when_used="json")
    def _serialize_created_at(self, value: datetime) -> str:
        return _iso_utc(value) or ""


class CategoryRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    is_active: bool


class PriorityRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    level: int = Field(ge=1, le=4)
    color: str | None = None
    base_hours: Decimal | None = None
    is_active: bool

    @field_serializer("base_hours", when_used="json")
    def _serialize_base_hours(self, value: Decimal | None) -> str | None:
        return _hours(value)


class CategoryAdmin(CategoryRef):
    description: str | None
    keywords: list[str]
    is_default: bool
    is_system: bool
    sort_order: int
    revision: int
    ticket_count: int
    rule_count: int
    can_delete: bool


class PriorityAdmin(PriorityRef):
    keywords: list[str]
    is_default: bool
    is_system: bool
    sort_order: int
    revision: int
    ticket_count: int
    rule_count: int
    can_delete: bool


class CategoryCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    keywords: list[str] = Field(default_factory=list, max_length=50)
    sort_order: int = Field(default=0, ge=0, le=9999)
    is_default: bool = False

    @field_validator("name")
    @classmethod
    def _name(cls, value: str) -> str:
        return _clean_name(value)

    @field_validator("keywords")
    @classmethod
    def _keywords(cls, value: list[str]) -> list[str]:
        return _clean_keywords(value)


class CategoryUpdateRequest(BaseModel):
    expected_revision: int = Field(ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    keywords: list[str] | None = Field(default=None, max_length=50)
    sort_order: int | None = Field(default=None, ge=0, le=9999)
    is_active: bool | None = None
    is_default: bool | None = None
    replacement_default_id: UUID | None = None

    @field_validator("name")
    @classmethod
    def _name(cls, value: str | None) -> str | None:
        return None if value is None else _clean_name(value)

    @field_validator("keywords")
    @classmethod
    def _keywords(cls, value: list[str] | None) -> list[str] | None:
        return None if value is None else _clean_keywords(value)


class PriorityCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    level: int = Field(ge=1, le=4)
    color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    base_hours: HOURS
    keywords: list[str] = Field(default_factory=list, max_length=50)
    sort_order: int = Field(default=0, ge=0, le=9999)
    is_default: bool = False

    @field_validator("name")
    @classmethod
    def _name(cls, value: str) -> str:
        return _clean_name(value)

    @field_validator("keywords")
    @classmethod
    def _keywords(cls, value: list[str]) -> list[str]:
        return _clean_keywords(value)


class PriorityUpdateRequest(BaseModel):
    expected_revision: int = Field(ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=50)
    level: int | None = Field(default=None, ge=1, le=4)
    color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    base_hours: HOURS | None = None
    keywords: list[str] | None = Field(default=None, max_length=50)
    sort_order: int | None = Field(default=None, ge=0, le=9999)
    is_active: bool | None = None
    is_default: bool | None = None
    replacement_default_id: UUID | None = None

    @field_validator("name")
    @classmethod
    def _name(cls, value: str | None) -> str | None:
        return None if value is None else _clean_name(value)

    @field_validator("keywords")
    @classmethod
    def _keywords(cls, value: list[str] | None) -> list[str] | None:
        return None if value is None else _clean_keywords(value)


class DeleteRequest(BaseModel):
    expected_revision: int = Field(ge=1)


class DeleteResponse(BaseModel):
    deleted: bool
    id: UUID
    configuration_version: ConfigurationVersionRef


class SlaRuleAdmin(BaseModel):
    id: UUID
    category: CategoryRef
    priority: PriorityRef
    hours: Decimal
    valid_from_version: int
    configuration_version_id: UUID
    created_at: datetime
    created_by: UserRef

    @field_serializer("hours", when_used="json")
    def _serialize_hours(self, value: Decimal) -> str:
        return _hours(value) or "0.00"

    @field_serializer("created_at", when_used="json")
    def _serialize_created_at(self, value: datetime) -> str:
        return _iso_utc(value) or ""


class SlaCombinations(BaseModel):
    categories: list[CategoryRef]
    priorities: list[PriorityRef]


class SlaMatrixResponse(BaseModel):
    configuration_version: ConfigurationVersionRef
    items: list[SlaRuleAdmin]
    combinations: SlaCombinations


class SlaUpsertChange(BaseModel):
    operation: Literal["upsert"]
    category_id: UUID
    priority_id: UUID
    hours: HOURS
    expected_rule_id: UUID | None = None


class SlaRetireChange(BaseModel):
    operation: Literal["retire"]
    rule_id: UUID
    expected_rule_id: UUID


class SlaBatchRequest(BaseModel):
    changes: list[SlaUpsertChange | SlaRetireChange] = Field(
        min_length=1, max_length=20
    )

    @field_validator("changes", mode="before")
    @classmethod
    def _non_empty_changes(cls, value: Any) -> Any:
        if isinstance(value, list) and not value:
            raise ApiError(422, "empty_batch", "El lote no contiene cambios.")
        return value


class SlaBatchResponse(BaseModel):
    configuration_version: ConfigurationVersionRef
    items: list[SlaRuleAdmin]


class SlaRetireRequest(BaseModel):
    expected_rule_id: UUID


class ConfigHistoryEntry(BaseModel):
    id: UUID
    configuration_version: ConfigurationVersionRef
    entity_type: ConfigEntityType
    entity_id: UUID
    action: ConfigAction
    actor: UserRef
    occurred_at: datetime
    previous_values: dict[str, Any] | None
    new_values: dict[str, Any] | None
    summary: str

    @field_serializer("occurred_at", when_used="json")
    def _serialize_occurred_at(self, value: datetime) -> str:
        return _iso_utc(value) or ""


class Pagination(BaseModel):
    page: int
    page_size: int
    total_items: int
    total_pages: int
    has_next: bool
    has_previous: bool


class ConfigHistoryResponse(BaseModel):
    items: list[ConfigHistoryEntry]
    pagination: Pagination
