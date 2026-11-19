"""Servicio de configuración administrativa de catálogos y SLA (HU-08)."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from decimal import Decimal
from functools import wraps
from typing import Any, Callable
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, lazyload

from app.core.errors import CONFIGURATION_ERROR_MESSAGES, ApiError
from app.models import (
    Category,
    ConfigAction,
    ConfigEntityType,
    ConfigurationAuditEntry,
    ConfigurationVersion,
    Priority,
    SlaRule,
    Ticket,
    User,
)
from app.schemas.configuration import (
    CategoryAdmin,
    ConfigurationVersionRef,
    ConfigHistoryEntry,
    ConfigHistoryResponse,
    DeleteResponse,
    Pagination,
    PriorityAdmin,
    SlaBatchRequest,
    SlaBatchResponse,
    SlaMatrixResponse,
    SlaRuleAdmin,
    UserRef,
)

HOURS_QUANT = Decimal("0.01")


def _atomic(func: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(func)
    def wrapped(db: Session, *args: Any, **kwargs: Any) -> Any:
        try:
            return func(db, *args, **kwargs)
        except Exception:
            db.rollback()
            raise

    return wrapped


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _normalize_name(value: str) -> str:
    return " ".join(value.strip().split()).casefold()


def _hours(value: Decimal | str) -> Decimal:
    result = Decimal(str(value)).quantize(HOURS_QUANT)
    if result <= 0:
        raise ApiError(
            422,
            "invalid_hours",
            CONFIGURATION_ERROR_MESSAGES["invalid_hours"],
        )
    return result


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, Decimal):
        return f"{value:.2f}"
    if isinstance(value, datetime):
        normalized = (
            value.replace(tzinfo=timezone.utc)
            if value.tzinfo is None
            else value.astimezone(timezone.utc)
        )
        return normalized.isoformat().replace("+00:00", "Z")
    if isinstance(value, UUID):
        return str(value)
    if hasattr(value, "value"):
        return value.value
    return value


def _current_version(
    db: Session, *, for_update: bool = False
) -> ConfigurationVersion | None:
    statement = (
        select(ConfigurationVersion)
        .order_by(ConfigurationVersion.version.desc())
        .limit(1)
    )
    if for_update and db.get_bind().dialect.name == "postgresql":
        statement = statement.options(
            lazyload(ConfigurationVersion.created_by)
        ).with_for_update()
    return db.scalar(statement)


def _require_version(db: Session, *, for_update: bool = False) -> ConfigurationVersion:
    version = _current_version(db, for_update=for_update)
    if version is None:
        raise ApiError(
            500,
            "configuration_not_initialized",
            "La configuración base no está inicializada.",
        )
    return version


def _new_version(
    db: Session,
    actor: User,
    note: str,
    *,
    current: ConfigurationVersion | None = None,
) -> ConfigurationVersion:
    base = current or _require_version(db, for_update=True)
    version = ConfigurationVersion(
        version=base.version + 1,
        created_by_id=actor.id,
        created_by=actor,
        note=note[:500],
        created_at=_now(),
    )
    db.add(version)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise ApiError(
            409,
            "stale_configuration",
            "La configuración ha cambiado. Recarga y vuelve a intentarlo.",
        ) from exc
    return version


def _audit(
    db: Session,
    version: ConfigurationVersion,
    actor: User,
    entity_type: ConfigEntityType,
    entity_id: UUID,
    action: ConfigAction,
    summary: str,
    *,
    previous: dict[str, Any] | None = None,
    new: dict[str, Any] | None = None,
) -> None:
    db.add(
        ConfigurationAuditEntry(
            configuration_version_id=version.id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            actor_id=actor.id,
            occurred_at=_now(),
            previous_values=_jsonable(previous) if previous is not None else None,
            new_values=_jsonable(new) if new is not None else None,
            summary=summary[:500],
        )
    )


def _version_ref(version: ConfigurationVersion) -> ConfigurationVersionRef:
    return ConfigurationVersionRef(
        id=version.id,
        version=version.version,
        created_at=version.created_at,
        created_by=(
            UserRef.model_validate(version.created_by)
            if version.created_by is not None
            else None
        ),
    )


def _category_snapshot(category: Category) -> dict[str, Any]:
    return {
        "name": category.name,
        "description": category.description,
        "keywords": list(category.keywords or []),
        "sort_order": category.sort_order,
        "is_active": category.is_active,
        "is_default": category.is_default,
        "is_system": category.is_system,
        "revision": category.revision,
    }


def _priority_snapshot(priority: Priority) -> dict[str, Any]:
    return {
        "name": priority.name,
        "level": priority.level,
        "color": priority.color,
        "base_hours": priority.base_hours,
        "keywords": list(priority.keywords or []),
        "sort_order": priority.sort_order,
        "is_active": priority.is_active,
        "is_default": priority.is_default,
        "is_system": priority.is_system,
        "revision": priority.revision,
    }


def _rule_snapshot(rule: SlaRule) -> dict[str, Any]:
    return {
        "category_id": rule.category_id,
        "priority_id": rule.priority_id,
        "hours": rule.hours,
        "configuration_version_id": rule.configuration_version_id,
        "valid_from_version": rule.valid_from_version,
        "valid_to_version": rule.valid_to_version,
        "supersedes_id": rule.supersedes_id,
        "retired_at": rule.retired_at,
    }


def _name_exists(
    db: Session,
    model: type[Category] | type[Priority],
    name: str,
    *,
    exclude_id: UUID | None = None,
) -> bool:
    normalized = _normalize_name(name)
    statement = select(model)
    if exclude_id is not None:
        statement = statement.where(model.id != exclude_id)
    for entity in db.scalars(statement):
        if _normalize_name(entity.name) == normalized:
            return True
    return False


def _category_counts(db: Session, category_id: UUID) -> tuple[int, int]:
    tickets = db.scalar(
        select(func.count())
        .select_from(Ticket)
        .where(Ticket.category_id == category_id)
    )
    rules = db.scalar(
        select(func.count())
        .select_from(SlaRule)
        .where(SlaRule.category_id == category_id)
    )
    return int(tickets or 0), int(rules or 0)


def _priority_counts(db: Session, priority_id: UUID) -> tuple[int, int]:
    tickets = db.scalar(
        select(func.count())
        .select_from(Ticket)
        .where(Ticket.priority_id == priority_id)
    )
    rules = db.scalar(
        select(func.count())
        .select_from(SlaRule)
        .where(SlaRule.priority_id == priority_id)
    )
    return int(tickets or 0), int(rules or 0)


def _category_admin(db: Session, category: Category) -> CategoryAdmin:
    ticket_count, rule_count = _category_counts(db, category.id)
    return CategoryAdmin(
        id=category.id,
        name=category.name,
        description=category.description,
        keywords=list(category.keywords or []),
        is_active=category.is_active,
        is_default=category.is_default,
        is_system=category.is_system,
        sort_order=category.sort_order,
        revision=category.revision,
        ticket_count=ticket_count,
        rule_count=rule_count,
        can_delete=(
            not category.is_system
            and not category.is_default
            and ticket_count == 0
            and rule_count == 0
        ),
    )


def _priority_admin(db: Session, priority: Priority) -> PriorityAdmin:
    ticket_count, rule_count = _priority_counts(db, priority.id)
    return PriorityAdmin(
        id=priority.id,
        name=priority.name,
        level=priority.level,
        color=priority.color,
        base_hours=priority.base_hours,
        keywords=list(priority.keywords or []),
        is_active=priority.is_active,
        is_default=priority.is_default,
        is_system=priority.is_system,
        sort_order=priority.sort_order,
        revision=priority.revision,
        ticket_count=ticket_count,
        rule_count=rule_count,
        can_delete=(
            not priority.is_system
            and not priority.is_default
            and ticket_count == 0
            and rule_count == 0
        ),
    )


def _rule_admin(rule: SlaRule) -> SlaRuleAdmin:
    return SlaRuleAdmin(
        id=rule.id,
        category={
            "id": rule.category.id,
            "name": rule.category.name,
            "is_active": rule.category.is_active,
        },
        priority={
            "id": rule.priority.id,
            "name": rule.priority.name,
            "level": rule.priority.level,
            "color": rule.priority.color,
            "base_hours": rule.priority.base_hours,
            "is_active": rule.priority.is_active,
        },
        hours=rule.hours,
        valid_from_version=rule.valid_from_version,
        configuration_version_id=rule.configuration_version_id,
        created_at=rule.created_at,
        created_by=UserRef.model_validate(rule.created_by),
    )


def _get_category(db: Session, category_id: UUID) -> Category:
    category = db.get(Category, category_id, with_for_update=True)
    if category is None:
        raise ApiError(404, "not_found", "La categoría no existe.")
    return category


def _get_priority(db: Session, priority_id: UUID) -> Priority:
    priority = db.get(Priority, priority_id, with_for_update=True)
    if priority is None:
        raise ApiError(404, "not_found", "La prioridad no existe.")
    return priority


def _active_catalog(
    db: Session, model: type[Category] | type[Priority]
) -> list[Category | Priority]:
    return list(
        db.scalars(
            select(model)
            .where(
                model.is_active.is_(True),
                model.is_system.is_(False),
            )
            .order_by(model.sort_order, model.name)
        ).all()
    )


def _default_for(
    db: Session, model: type[Category] | type[Priority], *, exclude_id: UUID | None = None
):
    statement = select(model).where(
        model.is_active.is_(True),
        model.is_default.is_(True),
        model.is_system.is_(False),
    )
    if exclude_id is not None:
        statement = statement.where(model.id != exclude_id)
    return db.scalar(statement.limit(1))


def _set_default(
    db: Session,
    model: type[Category] | type[Priority],
    target: Category | Priority,
    *,
    is_new: bool = False,
) -> tuple[
    list[tuple[Category | Priority, dict[str, Any]]],
    tuple[Category | Priority, dict[str, Any]] | None,
]:
    demoted: list[tuple[Category | Priority, dict[str, Any]]] = []
    for entity in db.scalars(
        select(model).where(
            model.is_default.is_(True),
            model.id != target.id,
        )
    ).all():
        previous = (
            _category_snapshot(entity)
            if isinstance(entity, Category)
            else _priority_snapshot(entity)
        )
        entity.is_default = False
        entity.revision += 1
        demoted.append((entity, previous))
    if demoted:
        db.flush()

    promoted: tuple[Category | Priority, dict[str, Any]] | None = None
    if not target.is_default:
        previous = (
            _category_snapshot(target)
            if isinstance(target, Category)
            else _priority_snapshot(target)
        )
        target.is_default = True
        if not is_new:
            target.revision += 1
        promoted = (target, previous)

    if demoted or promoted is not None:
        db.flush()
    return demoted, promoted


def _audit_demoted_defaults(
    db: Session,
    version: ConfigurationVersion,
    actor: User,
    demoted: list[tuple[Category | Priority, dict[str, Any]]],
) -> None:
    for entity, previous in demoted:
        if isinstance(entity, Category):
            entity_type = ConfigEntityType.category
            label = f"Categoría «{entity.name}»"
            new = _category_snapshot(entity)
        else:
            entity_type = ConfigEntityType.priority
            label = f"Prioridad «{entity.name}»"
            new = _priority_snapshot(entity)
        _audit(
            db,
            version,
            actor,
            entity_type,
            entity.id,
            ConfigAction.update,
            f"{label} dejó de ser predeterminada.",
            previous=previous,
            new=new,
        )


def _audit_promoted_default(
    db: Session,
    version: ConfigurationVersion,
    actor: User,
    promoted: tuple[Category | Priority, dict[str, Any]] | None,
    main_entity_id: UUID,
    *,
    include_main: bool = False,
) -> None:
    if promoted is None or (
        promoted[0].id == main_entity_id and not include_main
    ):
        return
    entity, previous = promoted
    if isinstance(entity, Category):
        entity_type = ConfigEntityType.category
        label = f"Categoría «{entity.name}»"
        new = _category_snapshot(entity)
    else:
        entity_type = ConfigEntityType.priority
        label = f"Prioridad «{entity.name}»"
        new = _priority_snapshot(entity)
    _audit(
        db,
        version,
        actor,
        entity_type,
        entity.id,
        ConfigAction.set_default,
        f"{label} pasó a ser predeterminada.",
        previous=previous,
        new=new,
    )


def _validate_replacement(
    db: Session,
    model: type[Category] | type[Priority],
    current_id: UUID,
    replacement_id: UUID,
) -> Category | Priority:
    if replacement_id == current_id:
        raise ApiError(
            422,
            "default_replacement_required",
            "El reemplazo debe ser otra entidad activa y no de sistema.",
        )
    replacement = db.get(model, replacement_id)
    if (
        replacement is None
        or not replacement.is_active
        or replacement.is_system
    ):
        raise ApiError(
            422,
            "default_replacement_required",
            "El reemplazo debe ser otra entidad activa y no de sistema.",
        )
    return replacement


def list_categories(db: Session) -> list[CategoryAdmin]:
    categories = db.scalars(
        select(Category).order_by(Category.sort_order, Category.name)
    ).all()
    return [_category_admin(db, category) for category in categories]


@_atomic
def create_category(
    db: Session, actor: User, payload
) -> CategoryAdmin:
    _require_version(db, for_update=True)
    name = payload.name.strip()
    if _name_exists(db, Category, name):
        raise ApiError(
            409,
            "duplicate_catalog_name",
            "Ya existe una categoría con ese nombre.",
        )
    has_default = _default_for(db, Category) is not None
    category = Category(
        name=name,
        description=payload.description,
        keywords=list(payload.keywords),
        sort_order=payload.sort_order,
        is_active=True,
        is_default=False,
        is_system=False,
        revision=1,
    )
    db.add(category)
    db.flush()
    created_snapshot = _category_snapshot(category)
    demoted: list[tuple[Category | Priority, dict[str, Any]]] = []
    promoted: tuple[Category | Priority, dict[str, Any]] | None = None
    if payload.is_default or not has_default:
        demoted, promoted = _set_default(db, Category, category, is_new=True)

    version = _new_version(db, actor, f"Alta de categoría {category.name}")
    _audit(
        db,
        version,
        actor,
        ConfigEntityType.category,
        category.id,
        ConfigAction.create,
        f"Categoría «{category.name}» creada.",
        new=created_snapshot,
    )
    _audit_demoted_defaults(db, version, actor, demoted)
    _audit_promoted_default(
        db, version, actor, promoted, category.id, include_main=True
    )
    db.commit()
    db.refresh(category)
    return _category_admin(db, category)


@_atomic
def update_category(
    db: Session, actor: User, category_id: UUID, payload
) -> CategoryAdmin:
    _require_version(db, for_update=True)
    category = _get_category(db, category_id)
    if category.is_system:
        raise ApiError(
            409,
            "system_catalog_item",
            "Las entidades de sistema no se pueden modificar.",
        )
    if payload.expected_revision != category.revision:
        raise ApiError(
            409,
            "stale_configuration",
            "La configuración ha cambiado. Recarga y vuelve a intentarlo.",
        )

    previous = _category_snapshot(category)
    name = category.name
    if payload.name is not None:
        name = payload.name.strip()
        if _name_exists(db, Category, name, exclude_id=category.id):
            raise ApiError(
                409,
                "duplicate_catalog_name",
                "Ya existe una categoría con ese nombre.",
            )

    effective_active = (
        payload.is_active if payload.is_active is not None else category.is_active
    )
    if (
        category.is_active
        and not category.is_system
        and not effective_active
        and len(_active_catalog(db, Category)) <= 1
    ):
        raise ApiError(
            409,
            "last_active_catalog_item",
            "No se puede desactivar la última categoría activa.",
        )

    replacement = None
    if payload.replacement_default_id is not None:
        replacement = _validate_replacement(
            db, Category, category.id, payload.replacement_default_id
        )
    demoted: list[tuple[Category | Priority, dict[str, Any]]] = []
    promoted: tuple[Category | Priority, dict[str, Any]] | None = None
    if category.is_default and (
        payload.is_default is False or payload.is_active is False
    ):
        if replacement is None:
            raise ApiError(
                422,
                "default_replacement_required",
                "Designa otra categoría predeterminada antes de desactivar la actual.",
            )
        category.is_default = False
        db.flush()
        demoted, promoted = _set_default(db, Category, replacement)
    elif payload.is_default is True:
        if not effective_active:
            raise ApiError(
                422,
                "inactive_default_catalog_item",
                CONFIGURATION_ERROR_MESSAGES["inactive_default_catalog_item"],
            )
        demoted, promoted = _set_default(db, Category, category)

    category.name = name
    if "description" in payload.model_fields_set:
        category.description = payload.description
    if payload.keywords is not None:
        category.keywords = list(payload.keywords)
    if payload.sort_order is not None:
        category.sort_order = payload.sort_order
    if payload.is_active is not None:
        category.is_active = payload.is_active
    if promoted is None or promoted[0].id != category.id:
        category.revision += 1

    if previous["is_active"] and not category.is_active:
        action = ConfigAction.deactivate
        summary = f"Categoría «{category.name}» desactivada."
    elif not previous["is_active"] and category.is_active:
        action = ConfigAction.reactivate
        summary = f"Categoría «{category.name}» reactivada."
    elif payload.is_default is True:
        action = ConfigAction.set_default
        summary = f"Categoría «{category.name}» marcada como predeterminada."
    else:
        action = ConfigAction.update
        summary = f"Categoría «{category.name}» actualizada."

    version = _new_version(db, actor, summary)
    _audit(
        db,
        version,
        actor,
        ConfigEntityType.category,
        category.id,
        action,
        summary,
        previous=previous,
        new=_category_snapshot(category),
    )
    _audit_demoted_defaults(db, version, actor, demoted)
    _audit_promoted_default(db, version, actor, promoted, category.id)
    db.commit()
    db.refresh(category)
    return _category_admin(db, category)


@_atomic
def delete_category(
    db: Session, actor: User, category_id: UUID, payload
) -> DeleteResponse:
    _require_version(db, for_update=True)
    category = _get_category(db, category_id)
    if category.is_system:
        raise ApiError(
            409,
            "system_catalog_item",
            "Las entidades de sistema no se pueden eliminar.",
        )
    if payload.expected_revision != category.revision:
        raise ApiError(
            409,
            "stale_configuration",
            "La configuración ha cambiado. Recarga y vuelve a intentarlo.",
        )
    if category.is_default:
        raise ApiError(
            409,
            "default_catalog_item",
            "Designa otra categoría predeterminada antes de eliminar esta.",
        )
    ticket_count, rule_count = _category_counts(db, category.id)
    if ticket_count or rule_count:
        raise ApiError(
            409,
            "catalog_in_use",
            "La categoría tiene tickets o reglas asociadas. Desactívala en su lugar.",
        )

    previous = _category_snapshot(category)
    db.delete(category)
    db.flush()
    version = _new_version(db, actor, f"Eliminación de categoría {previous['name']}")
    _audit(
        db,
        version,
        actor,
        ConfigEntityType.category,
        category_id,
        ConfigAction.delete,
        f"Categoría «{previous['name']}» eliminada.",
        previous=previous,
    )
    db.commit()
    return DeleteResponse(
        deleted=True,
        id=category_id,
        configuration_version=_version_ref(version),
    )


def list_priorities(db: Session) -> list[PriorityAdmin]:
    priorities = db.scalars(
        select(Priority).order_by(Priority.sort_order, Priority.level)
    ).all()
    return [_priority_admin(db, priority) for priority in priorities]


def _validate_priority_level(
    db: Session, level: int, *, exclude_id: UUID | None = None
) -> None:
    statement = select(Priority).where(
        Priority.level == level,
        Priority.is_active.is_(True),
        Priority.is_system.is_(False),
    )
    if exclude_id is not None:
        statement = statement.where(Priority.id != exclude_id)
    if db.scalar(statement.limit(1)) is not None:
        raise ApiError(
            409,
            "duplicate_priority_level",
            "Ya hay una prioridad activa con ese nivel.",
        )


@_atomic
def create_priority(
    db: Session, actor: User, payload
) -> PriorityAdmin:
    _require_version(db, for_update=True)
    name = payload.name.strip()
    if _name_exists(db, Priority, name):
        raise ApiError(
            409,
            "duplicate_catalog_name",
            "Ya existe una prioridad con ese nombre.",
        )
    _validate_priority_level(db, payload.level)
    has_default = _default_for(db, Priority) is not None
    priority = Priority(
        name=name,
        level=payload.level,
        color=payload.color,
        base_hours=_hours(payload.base_hours),
        keywords=list(payload.keywords),
        sort_order=payload.sort_order,
        is_active=True,
        is_default=False,
        is_system=False,
        revision=1,
    )
    db.add(priority)
    db.flush()
    created_snapshot = _priority_snapshot(priority)
    demoted: list[tuple[Category | Priority, dict[str, Any]]] = []
    promoted: tuple[Category | Priority, dict[str, Any]] | None = None
    if payload.is_default or not has_default:
        demoted, promoted = _set_default(db, Priority, priority, is_new=True)

    version = _new_version(db, actor, f"Alta de prioridad {priority.name}")
    _audit(
        db,
        version,
        actor,
        ConfigEntityType.priority,
        priority.id,
        ConfigAction.create,
        f"Prioridad «{priority.name}» creada.",
        new=created_snapshot,
    )
    _audit_demoted_defaults(db, version, actor, demoted)
    _audit_promoted_default(
        db, version, actor, promoted, priority.id, include_main=True
    )
    db.commit()
    db.refresh(priority)
    return _priority_admin(db, priority)


@_atomic
def update_priority(
    db: Session, actor: User, priority_id: UUID, payload
) -> PriorityAdmin:
    _require_version(db, for_update=True)
    priority = _get_priority(db, priority_id)
    if priority.is_system:
        raise ApiError(
            409,
            "system_catalog_item",
            "Las entidades de sistema no se pueden modificar.",
        )
    if payload.expected_revision != priority.revision:
        raise ApiError(
            409,
            "stale_configuration",
            "La configuración ha cambiado. Recarga y vuelve a intentarlo.",
        )

    previous = _priority_snapshot(priority)
    name = priority.name
    if payload.name is not None:
        name = payload.name.strip()
        if _name_exists(db, Priority, name, exclude_id=priority.id):
            raise ApiError(
                409,
                "duplicate_catalog_name",
                "Ya existe una prioridad con ese nombre.",
            )

    effective_active = (
        payload.is_active if payload.is_active is not None else priority.is_active
    )
    effective_level = (
        payload.level if payload.level is not None else priority.level
    )
    if effective_active and not priority.is_system:
        _validate_priority_level(
            db, effective_level, exclude_id=priority.id
        )
    if (
        priority.is_active
        and not priority.is_system
        and not effective_active
        and len(_active_catalog(db, Priority)) <= 1
    ):
        raise ApiError(
            409,
            "last_active_catalog_item",
            "No se puede desactivar la última prioridad activa.",
        )

    replacement = None
    if payload.replacement_default_id is not None:
        replacement = _validate_replacement(
            db, Priority, priority.id, payload.replacement_default_id
        )
    demoted: list[tuple[Category | Priority, dict[str, Any]]] = []
    promoted: tuple[Category | Priority, dict[str, Any]] | None = None
    if priority.is_default and (
        payload.is_default is False or payload.is_active is False
    ):
        if replacement is None:
            raise ApiError(
                422,
                "default_replacement_required",
                "Designa otra prioridad predeterminada antes de desactivar la actual.",
            )
        priority.is_default = False
        db.flush()
        demoted, promoted = _set_default(db, Priority, replacement)
    elif payload.is_default is True:
        if not effective_active:
            raise ApiError(
                422,
                "inactive_default_catalog_item",
                CONFIGURATION_ERROR_MESSAGES["inactive_default_catalog_item"],
            )
        demoted, promoted = _set_default(db, Priority, priority)

    priority.name = name
    if payload.level is not None:
        priority.level = payload.level
    if "color" in payload.model_fields_set:
        priority.color = payload.color
    if payload.base_hours is not None:
        priority.base_hours = _hours(payload.base_hours)
    if payload.keywords is not None:
        priority.keywords = list(payload.keywords)
    if payload.sort_order is not None:
        priority.sort_order = payload.sort_order
    if payload.is_active is not None:
        priority.is_active = payload.is_active
    if promoted is None or promoted[0].id != priority.id:
        priority.revision += 1

    if previous["is_active"] and not priority.is_active:
        action = ConfigAction.deactivate
        summary = f"Prioridad «{priority.name}» desactivada."
    elif not previous["is_active"] and priority.is_active:
        action = ConfigAction.reactivate
        summary = f"Prioridad «{priority.name}» reactivada."
    elif payload.is_default is True:
        action = ConfigAction.set_default
        summary = f"Prioridad «{priority.name}» marcada como predeterminada."
    else:
        action = ConfigAction.update
        summary = f"Prioridad «{priority.name}» actualizada."

    version = _new_version(db, actor, summary)
    _audit(
        db,
        version,
        actor,
        ConfigEntityType.priority,
        priority.id,
        action,
        summary,
        previous=previous,
        new=_priority_snapshot(priority),
    )
    _audit_demoted_defaults(db, version, actor, demoted)
    _audit_promoted_default(db, version, actor, promoted, priority.id)
    db.commit()
    db.refresh(priority)
    return _priority_admin(db, priority)


@_atomic
def delete_priority(
    db: Session, actor: User, priority_id: UUID, payload
) -> DeleteResponse:
    _require_version(db, for_update=True)
    priority = _get_priority(db, priority_id)
    if priority.is_system:
        raise ApiError(
            409,
            "system_catalog_item",
            "Las entidades de sistema no se pueden eliminar.",
        )
    if payload.expected_revision != priority.revision:
        raise ApiError(
            409,
            "stale_configuration",
            "La configuración ha cambiado. Recarga y vuelve a intentarlo.",
        )
    if priority.is_default:
        raise ApiError(
            409,
            "default_catalog_item",
            "Designa otra prioridad predeterminada antes de eliminar esta.",
        )
    ticket_count, rule_count = _priority_counts(db, priority.id)
    if ticket_count or rule_count:
        raise ApiError(
            409,
            "catalog_in_use",
            "La prioridad tiene tickets o reglas asociadas. Desactívala en su lugar.",
        )

    previous = _priority_snapshot(priority)
    db.delete(priority)
    db.flush()
    version = _new_version(db, actor, f"Eliminación de prioridad {previous['name']}")
    _audit(
        db,
        version,
        actor,
        ConfigEntityType.priority,
        priority_id,
        ConfigAction.delete,
        f"Prioridad «{previous['name']}» eliminada.",
        previous=previous,
    )
    db.commit()
    return DeleteResponse(
        deleted=True,
        id=priority_id,
        configuration_version=_version_ref(version),
    )


def _current_rules(db: Session) -> list[SlaRule]:
    return list(
        db.scalars(
            select(SlaRule)
            .where(SlaRule.valid_to_version.is_(None))
            .order_by(SlaRule.category_id, SlaRule.priority_id)
        ).unique().all()
    )


def sla_matrix(db: Session) -> SlaMatrixResponse:
    version = _require_version(db)
    categories = [
        item
        for item in _active_catalog(db, Category)
        if not item.is_system
    ]
    priorities = [
        item
        for item in _active_catalog(db, Priority)
        if not item.is_system
    ]
    return SlaMatrixResponse(
        configuration_version=_version_ref(version),
        items=[_rule_admin(rule) for rule in _current_rules(db)],
        combinations={
            "categories": [
                {"id": item.id, "name": item.name, "is_active": item.is_active}
                for item in categories
            ],
            "priorities": [
                {
                    "id": item.id,
                    "name": item.name,
                    "level": item.level,
                    "color": item.color,
                    "base_hours": item.base_hours,
                    "is_active": item.is_active,
                }
                for item in priorities
            ],
        },
    )


def _apply_batch(
    db: Session,
    actor: User,
    changes: list,
    *,
    note: str,
) -> ConfigurationVersion:
    try:
        return _apply_batch_impl(db, actor, changes, note=note)
    except Exception:
        db.rollback()
        raise


def _apply_batch_impl(
    db: Session,
    actor: User,
    changes: list,
    *,
    note: str,
) -> ConfigurationVersion:
    if not changes:
        raise ApiError(
            422,
            "empty_batch",
            "El lote no contiene cambios.",
        )
    current = _require_version(db, for_update=True)
    next_version = current.version + 1
    seen_combinations: set[tuple[UUID, UUID]] = set()
    previous_rules: dict[UUID, dict[str, Any]] = {}
    retired_rules: dict[UUID, dict[str, Any]] = {}
    now = _now()

    for change in changes:
        if change.operation == "retire":
            rule = db.get(SlaRule, change.rule_id)
            if (
                rule is None
                or rule.valid_to_version is not None
                or change.expected_rule_id != rule.id
            ):
                raise ApiError(
                    409,
                    "stale_configuration",
                    "La configuración ha cambiado. Recarga y vuelve a intentarlo.",
                )
            key = (rule.category_id, rule.priority_id)
            if key in seen_combinations:
                raise ApiError(
                    409,
                    "duplicate_sla_rule",
                    "El lote contiene cambios duplicados para la misma combinación.",
                )
            seen_combinations.add(key)
            retired_rules[rule.id] = _rule_snapshot(rule)
            rule.valid_to_version = next_version
            rule.retired_at = now
            rule.retired_by_id = actor.id
            continue

        category = db.get(Category, change.category_id)
        priority = db.get(Priority, change.priority_id)
        if (
            category is None
            or priority is None
            or not category.is_active
            or not priority.is_active
            or category.is_system
            or priority.is_system
        ):
            raise ApiError(
                422,
                "inactive_catalog_item",
                "La categoría o la prioridad no está activa.",
            )
        key = (category.id, priority.id)
        if key in seen_combinations:
            raise ApiError(
                409,
                "duplicate_sla_rule",
                "El lote contiene cambios duplicados para la misma combinación.",
            )
        seen_combinations.add(key)
        existing = db.scalar(
            select(SlaRule)
            .where(
                SlaRule.category_id == category.id,
                SlaRule.priority_id == priority.id,
                SlaRule.valid_to_version.is_(None),
            )
            .limit(1)
        )
        if existing is not None:
            if change.expected_rule_id != existing.id:
                raise ApiError(
                    409,
                    "stale_configuration",
                    "La configuración ha cambiado. Recarga y vuelve a intentarlo.",
                )
        elif change.expected_rule_id is not None:
            raise ApiError(
                409,
                "stale_configuration",
                "La configuración ha cambiado. Recarga y vuelve a intentarlo.",
            )

        if existing is not None:
            previous_rules[existing.id] = _rule_snapshot(existing)
            existing.valid_to_version = next_version
            db.flush()

        rule = SlaRule(
            category_id=category.id,
            priority_id=priority.id,
            hours=_hours(change.hours),
            configuration_version_id=current.id,
            valid_from_version=next_version,
            valid_to_version=None,
            created_by_id=actor.id,
            created_at=now,
            supersedes_id=existing.id if existing is not None else None,
        )
        # La regla se asocia a la nueva versión una vez creada.
        db.add(rule)
        db.flush()

    version = ConfigurationVersion(
        version=next_version,
        created_by_id=actor.id,
        created_by=actor,
        note=note[:500],
        created_at=now,
    )
    db.add(version)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise ApiError(
            409,
            "duplicate_sla_rule",
            "Ya existe una regla vigente para esa combinación.",
        ) from exc

    for rule in db.scalars(
        select(SlaRule).where(SlaRule.configuration_version_id == current.id)
    ).all():
        # Las filas nuevas se han creado con la versión anterior para poder
        # cerrar la anterior antes de conocer el id; se corrigen aquí.
        if rule.valid_from_version == next_version:
            rule.configuration_version_id = version.id
    for rule in db.scalars(
        select(SlaRule).where(SlaRule.valid_from_version == next_version)
    ).all():
        rule.configuration_version_id = version.id
        _audit(
            db,
            version,
            actor,
            ConfigEntityType.sla_rule,
            rule.id,
            ConfigAction.rule_upsert,
            f"Regla de {rule.category.name} × {rule.priority.name}: {rule.hours} h.",
            previous=previous_rules.get(rule.supersedes_id),
            new=_rule_snapshot(rule),
        )
    for rule in db.scalars(
        select(SlaRule).where(
            SlaRule.valid_to_version == next_version,
            SlaRule.retired_at.is_not(None),
        )
    ).all():
        _audit(
            db,
            version,
            actor,
            ConfigEntityType.sla_rule,
            rule.id,
            ConfigAction.rule_retire,
            f"Regla de {rule.category.name} × {rule.priority.name} retirada.",
            previous=retired_rules[rule.id],
            new=_rule_snapshot(rule),
        )
    return version


def apply_sla_batch(
    db: Session, actor: User, payload: SlaBatchRequest
) -> SlaBatchResponse:
    version = _apply_batch(db, actor, list(payload.changes), note="Cambios de matriz SLA")
    db.commit()
    return SlaBatchResponse(
        configuration_version=_version_ref(version),
        items=[_rule_admin(rule) for rule in _current_rules(db)],
    )


def retire_sla_rule(
    db: Session, actor: User, rule_id: UUID, expected_rule_id: UUID
) -> SlaBatchResponse:
    from app.schemas.configuration import SlaRetireChange

    change = SlaRetireChange(
        operation="retire",
        rule_id=rule_id,
        expected_rule_id=expected_rule_id,
    )
    version = _apply_batch(
        db, actor, [change], note="Retirada de regla SLA"
    )
    db.commit()
    return SlaBatchResponse(
        configuration_version=_version_ref(version),
        items=[_rule_admin(rule) for rule in _current_rules(db)],
    )


def list_config_history(
    db: Session,
    *,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    entity_type: ConfigEntityType | None = None,
    entity_id: UUID | None = None,
    action: ConfigAction | None = None,
    configuration_version_id: UUID | None = None,
    page: int = 1,
    page_size: int = 25,
) -> ConfigHistoryResponse:
    page = max(1, page)
    page_size = max(1, min(page_size, 100))
    from_date = _as_utc(from_date)
    to_date = _as_utc(to_date)
    if from_date is not None and to_date is not None and from_date > to_date:
        raise ApiError(
            422,
            "invalid_date_range",
            CONFIGURATION_ERROR_MESSAGES["invalid_date_range"],
        )
    filters = []
    if from_date is not None:
        filters.append(ConfigurationAuditEntry.occurred_at >= from_date)
    if to_date is not None:
        filters.append(ConfigurationAuditEntry.occurred_at <= to_date)
    if entity_type is not None:
        filters.append(ConfigurationAuditEntry.entity_type == entity_type)
    if entity_id is not None:
        filters.append(ConfigurationAuditEntry.entity_id == entity_id)
    if action is not None:
        filters.append(ConfigurationAuditEntry.action == action)
    if configuration_version_id is not None:
        filters.append(
            ConfigurationAuditEntry.configuration_version_id
            == configuration_version_id
        )

    total_items = int(
        db.scalar(
            select(func.count())
            .select_from(ConfigurationAuditEntry)
            .where(*filters)
        )
        or 0
    )
    total_pages = math.ceil(total_items / page_size) if total_items else 0
    effective_page = min(page, total_pages) if total_pages else 1
    entries = db.scalars(
        select(ConfigurationAuditEntry)
        .options(
            joinedload(ConfigurationAuditEntry.configuration_version).joinedload(
                ConfigurationVersion.created_by
            ),
            joinedload(ConfigurationAuditEntry.actor),
        )
        .where(*filters)
        .order_by(
            ConfigurationAuditEntry.occurred_at.desc(),
            ConfigurationAuditEntry.id.desc(),
        )
        .offset((effective_page - 1) * page_size)
        .limit(page_size)
    ).unique().all()

    return ConfigHistoryResponse(
        items=[
            ConfigHistoryEntry(
                id=entry.id,
                configuration_version=_version_ref(entry.configuration_version),
                entity_type=entry.entity_type,
                entity_id=entry.entity_id,
                action=entry.action,
                actor=UserRef.model_validate(entry.actor),
                occurred_at=entry.occurred_at,
                previous_values=entry.previous_values,
                new_values=entry.new_values,
                summary=entry.summary,
            )
            for entry in entries
        ],
        pagination=Pagination(
            page=effective_page,
            page_size=page_size,
            total_items=total_items,
            total_pages=total_pages,
            has_next=effective_page < total_pages,
            has_previous=effective_page > 1,
        ),
    )


config_history = list_config_history
