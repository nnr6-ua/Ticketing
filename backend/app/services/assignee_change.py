"""Cambio de responsable: opciones, reasignación y escalado (HU-06)."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import ApiError, WORKFLOW_WRITE_ERROR_MESSAGE
from app.models import (
    DEFAULT_ACTIVE_STATUSES,
    ESCALATION_LEVEL_LABELS,
    ESCALATION_LEVEL_ORDER,
    AssigneeChangeKind,
    EscalationLevel,
    Ticket,
    TicketStatus,
    TicketTimelineEntry,
    TimelineEventType,
    User,
    UserRole,
)
from app.schemas.assignee_change import (
    AssigneeChangeOptions,
    AssigneeChangeResponse,
    AssigneeRef,
    EscalationRequest,
    EscalationTarget,
    ReassignmentRequest,
)
from app.services.notifications import create_assignee_change_notification
from app.services.ticket_timeline import as_utc, assignee_ref, serialize_entry
from app.services.ticket_workflow import (
    _locked_ticket,
    build_snapshot,
    ensure_assignee_change_actor,
)

logger = logging.getLogger(__name__)

UTC = timezone.utc
MAX_REASON_LENGTH = 5000

REPLAY_REASSIGNMENT = (
    "Esta reasignación ya se aplicó con el identificador de solicitud indicado."
)
REPLAY_ESCALATION = (
    "Este escalado ya se aplicó con el identificador de solicitud indicado."
)
REQUEST_ID_REUSED = (
    "La solicitud ya se utilizó con otros datos. Genera una nueva solicitud e "
    "inténtalo de nuevo."
)
TICKET_FINALIZED = (
    "El ticket está finalizado y no admite cambios de responsable."
)
STALE_TICKET = (
    "El ticket ha sido modificado por otra persona. Actualiza la información e "
    "inténtalo de nuevo."
)
REASON_REQUIRED = "Indica el motivo del cambio de responsable."
REASON_TOO_LONG = "El motivo no puede superar los 5.000 caracteres."
SELF_REASSIGNMENT = "No puedes reasignarte el ticket a ti mismo."
CREATOR_NOT_ASSIGNABLE = "Ese usuario no puede recibir este ticket."
INVALID_REASSIGNMENT_TARGET = (
    "Solo puedes reasignar a técnicos activos de tu equipo y de tu nivel."
)
ASSIGNEE_UNAVAILABLE = (
    "El técnico seleccionado ya no está disponible. Actualiza la lista e "
    "inténtalo de nuevo."
)
INVALID_ESCALATION_LEVEL = (
    "Debes elegir un nivel superior al del responsable actual."
)
NO_HIGHER_LEVEL = "El ticket ya está en el nivel máximo de soporte."
NO_TECHNICIANS_AVAILABLE = (
    "No hay técnicos disponibles en ese nivel en este momento."
)
ASSIGNEE_INCONSISTENT = (
    "El responsable del ticket no coincide con el último cambio registrado. "
    "Actualiza la información e inténtalo de nuevo."
)


# ---------------------------------------------------------------------------
# Catálogo de niveles y selección determinista
# ---------------------------------------------------------------------------
def escalation_level_label(level: EscalationLevel) -> str:
    return ESCALATION_LEVEL_LABELS[level]


def higher_escalation_levels(
    level: EscalationLevel,
) -> tuple[EscalationLevel, ...]:
    index = ESCALATION_LEVEL_ORDER.index(level)
    return ESCALATION_LEVEL_ORDER[index + 1 :]


def is_higher_level(
    current: EscalationLevel, target: EscalationLevel
) -> bool:
    return (
        ESCALATION_LEVEL_ORDER.index(target)
        > ESCALATION_LEVEL_ORDER.index(current)
    )


def _level_of(user: User) -> EscalationLevel:
    return user.escalation_level or EscalationLevel.nivel_1


def _active_ticket_counts():
    return (
        select(
            Ticket.assignee_id.label("user_id"),
            func.count(Ticket.id).label("active_count"),
        )
        .where(
            Ticket.assignee_id.is_not(None),
            Ticket.status.in_(DEFAULT_ACTIVE_STATUSES),
        )
        .group_by(Ticket.assignee_id)
        .subquery()
    )


def reassignment_candidates(
    session: Session, ticket: Ticket, current_assignee: User
) -> list[User]:
    """Compañeros del mismo equipo y nivel, sin el actual ni el creador."""

    current_level = _level_of(current_assignee)
    conditions = [
        User.role == UserRole.tecnico,
        User.is_active.is_(True),
        User.escalation_level == current_level,
        User.id != current_assignee.id,
        User.id != ticket.creator_id,
    ]
    if current_assignee.team:
        conditions.append(User.team == current_assignee.team)

    statement = (
        select(User)
        .where(*conditions)
        .order_by(func.lower(User.name).asc(), User.id.asc())
    )
    return list(session.scalars(statement).all())


def escalation_targets(
    session: Session, current_assignee: User, creator_id: UUID
) -> list[EscalationTarget]:
    """Niveles estrictamente superiores con disponibilidad calculada."""

    targets: list[EscalationTarget] = []
    for level in higher_escalation_levels(_level_of(current_assignee)):
        technician_count = int(
            session.scalar(
                select(func.count())
                .select_from(User)
                .where(
                    User.role == UserRole.tecnico,
                    User.is_active.is_(True),
                    User.escalation_level == level,
                    User.id != creator_id,
                )
            )
            or 0
        )
        targets.append(
            EscalationTarget(
                value=level,
                label=escalation_level_label(level),
                technician_count=technician_count,
                is_available=technician_count > 0,
            )
        )
    return targets


def select_escalation_assignee(
    session: Session, ticket: Ticket, target_level: EscalationLevel
) -> User | None:
    """Selección determinista: equipo, menor carga, nombre e id."""

    counts = _active_ticket_counts()
    active_count = func.coalesce(counts.c.active_count, 0)
    statement = (
        select(User)
        .outerjoin(counts, counts.c.user_id == User.id)
        .where(
            User.role == UserRole.tecnico,
            User.is_active.is_(True),
            User.escalation_level == target_level,
            User.id != ticket.creator_id,
        )
        .order_by(
            active_count.asc(),
            func.lower(User.name).asc(),
            User.id.asc(),
        )
    )
    candidates = list(session.scalars(statement).all())
    if not candidates:
        return None

    current = (
        session.get(User, ticket.assignee_id)
        if ticket.assignee_id is not None
        else None
    )
    if current is not None and current.team:
        same_team = [user for user in candidates if user.team == current.team]
        if same_team:
            candidates = same_team
    return candidates[0]


# ---------------------------------------------------------------------------
# Errores
# ---------------------------------------------------------------------------
def _ticket_finalized() -> ApiError:
    return ApiError(409, "ticket_finalized", TICKET_FINALIZED)


def _stale() -> ApiError:
    return ApiError(409, "stale_ticket", STALE_TICKET)


def _request_id_reused() -> ApiError:
    return ApiError(409, "request_id_reused", REQUEST_ID_REUSED)


def _assignee_inconsistent() -> ApiError:
    return ApiError(409, "assignee_inconsistent", ASSIGNEE_INCONSISTENT)


def _reason_required() -> ApiError:
    return ApiError(422, "reason_required", REASON_REQUIRED)


def _reason_too_long() -> ApiError:
    return ApiError(422, "reason_too_long", REASON_TOO_LONG)


def _self_reassignment() -> ApiError:
    return ApiError(422, "self_reassignment", SELF_REASSIGNMENT)


def _creator_not_assignable() -> ApiError:
    return ApiError(422, "creator_not_assignable", CREATOR_NOT_ASSIGNABLE)


def _invalid_reassignment_target() -> ApiError:
    return ApiError(
        422, "invalid_reassignment_target", INVALID_REASSIGNMENT_TARGET
    )


def _assignee_unavailable() -> ApiError:
    return ApiError(422, "assignee_unavailable", ASSIGNEE_UNAVAILABLE)


def _invalid_escalation_level() -> ApiError:
    return ApiError(
        422, "invalid_escalation_level", INVALID_ESCALATION_LEVEL
    )


def _no_higher_level() -> ApiError:
    return ApiError(409, "no_higher_level", NO_HIGHER_LEVEL)


def _no_technicians_available() -> ApiError:
    return ApiError(
        409, "no_technicians_available", NO_TECHNICIANS_AVAILABLE
    )


# ---------------------------------------------------------------------------
# Validaciones compartidas
# ---------------------------------------------------------------------------
def _validate_reason(reason: str) -> str:
    if not reason:
        logger.warning("Motivo no válido code=reason_required")
        raise _reason_required()
    if len(reason) > MAX_REASON_LENGTH:
        logger.warning("Motivo no válido code=reason_too_long")
        raise _reason_too_long()
    return reason


def _ensure_active(ticket: Ticket) -> None:
    if ticket.status in (TicketStatus.resuelto, TicketStatus.cerrado):
        logger.warning(
            "Ticket finalizado code=ticket_finalized ticket_id=%s", ticket.id
        )
        raise _ticket_finalized()


def _ensure_version(ticket: Ticket, expected_updated_at: datetime) -> None:
    expected = as_utc(expected_updated_at)
    current = as_utc(ticket.updated_at)
    if expected is None or current is None or expected != current:
        logger.warning(
            "Conflicto de versión code=stale_ticket ticket_id=%s", ticket.id
        )
        raise _stale()


def ensure_assignee_consistency(session: Session, ticket: Ticket) -> None:
    """RF-033: el ticket y la última entrada `assignee_change` deben coincidir."""

    latest = session.scalar(
        select(TicketTimelineEntry)
        .where(
            TicketTimelineEntry.ticket_id == ticket.id,
            TicketTimelineEntry.event_type == TimelineEventType.assignee_change,
        )
        .order_by(
            TicketTimelineEntry.created_at.desc(),
            TicketTimelineEntry.event_order.desc(),
            TicketTimelineEntry.id.desc(),
        )
        .limit(1)
    )
    if latest is not None and latest.new_assignee_id != ticket.assignee_id:
        logger.warning(
            "Inconsistencia de responsable code=assignee_inconsistent "
            "ticket_id=%s",
            ticket.id,
        )
        raise _assignee_inconsistent()


# ---------------------------------------------------------------------------
# Idempotencia
# ---------------------------------------------------------------------------
def _assignee_change_entry(
    session: Session, ticket_id: UUID, request_id: UUID
) -> TicketTimelineEntry | None:
    return session.scalar(
        select(TicketTimelineEntry)
        .where(
            TicketTimelineEntry.ticket_id == ticket_id,
            TicketTimelineEntry.request_id == request_id,
            TicketTimelineEntry.event_type == TimelineEventType.assignee_change,
        )
        .limit(1)
    )


def _classify_replay(
    entry: TicketTimelineEntry | None,
    actor: User,
    kind: AssigneeChangeKind,
    reason: str,
    *,
    new_assignee_id: UUID | None = None,
    target_level: EscalationLevel | None = None,
) -> str:
    if entry is None:
        return "none"
    if (
        entry.author_id != actor.id
        or entry.change_kind != kind
        or entry.body != reason
    ):
        return "reused"
    if kind == AssigneeChangeKind.reassignment:
        return (
            "replay"
            if entry.new_assignee_id == new_assignee_id
            else "reused"
        )
    return (
        "replay"
        if entry.to_escalation_level == target_level
        else "reused"
    )


# ---------------------------------------------------------------------------
# Lectura de opciones
# ---------------------------------------------------------------------------
def get_assignee_change_options(
    session: Session, ticket: Ticket, current_user: User
) -> AssigneeChangeOptions:
    ensure_assignee_change_actor(current_user, ticket)
    _ensure_active(ticket)
    ensure_assignee_consistency(session, ticket)

    current_assignee = session.get(User, ticket.assignee_id)
    if current_assignee is None:
        logger.warning(
            "Responsable no disponible code=assignee_unavailable ticket_id=%s",
            ticket.id,
        )
        raise _assignee_unavailable()

    candidates = reassignment_candidates(session, ticket, current_assignee)
    targets = escalation_targets(session, current_assignee, ticket.creator_id)

    return AssigneeChangeOptions(
        ticket_id=ticket.id,
        status=ticket.status,
        current_assignee=assignee_ref(current_assignee),
        has_reassignment_candidates=bool(candidates),
        has_available_escalation_target=any(
            target.is_available for target in targets
        ),
        reassignment_candidates=[assignee_ref(user) for user in candidates],
        escalation_targets=targets,
    )


# ---------------------------------------------------------------------------
# Escritura atómica
# ---------------------------------------------------------------------------
def _insert_assignee_change(
    session: Session,
    ticket: Ticket,
    actor: User,
    previous_assignee: User,
    new_assignee: User,
    kind: AssigneeChangeKind,
    reason: str,
    from_level: EscalationLevel,
    to_level: EscalationLevel,
    now: datetime,
    request_id: UUID,
) -> TicketTimelineEntry:
    entry = TicketTimelineEntry(
        ticket_id=ticket.id,
        event_type=TimelineEventType.assignee_change,
        from_status=None,
        to_status=None,
        body=reason,
        is_internal=False,
        author_id=actor.id,
        author=actor,
        created_at=now,
        event_order=0,
        request_id=request_id,
        previous_assignee_id=previous_assignee.id,
        new_assignee_id=new_assignee.id,
        change_kind=kind,
        from_escalation_level=from_level,
        to_escalation_level=to_level,
    )
    session.add(entry)
    session.flush()
    return entry


def _commit_change(
    session: Session,
    ticket: Ticket,
    actor: User,
    new_assignee: User,
    kind: AssigneeChangeKind,
    reason: str,
    from_level: EscalationLevel,
    to_level: EscalationLevel,
    now: datetime,
    request_id: UUID,
) -> TicketTimelineEntry:
    ticket.assignee_id = new_assignee.id
    ticket.updated_at = now
    try:
        entry = _insert_assignee_change(
            session,
            ticket,
            actor,
            actor,
            new_assignee,
            kind,
            reason,
            from_level,
            to_level,
            now,
            request_id,
        )
        create_assignee_change_notification(
            session,
            ticket,
            entry,
            actor,
            new_assignee,
            kind,
            now,
        )
        session.commit()
    except Exception as exc:  # noqa: BLE001 - error estable de escritura
        session.rollback()
        logger.exception(
            "Error inesperado al cambiar el responsable ticket_id=%s", ticket.id
        )
        raise ApiError(500, "internal_error", WORKFLOW_WRITE_ERROR_MESSAGE) from exc
    return entry


def _response_from_entry(
    ticket: Ticket,
    actor: User,
    entry: TicketTimelineEntry,
    *,
    changed: bool,
    message: str | None,
) -> AssigneeChangeResponse:
    previous = entry.previous_assignee or actor
    new = entry.new_assignee
    from_level = entry.from_escalation_level or _level_of(previous)
    to_level = entry.to_escalation_level or (
        _level_of(new) if new is not None else from_level
    )
    if new is None:  # defensa: la FK garantiza que existe
        raise ApiError(500, "internal_error", WORKFLOW_WRITE_ERROR_MESSAGE)

    return AssigneeChangeResponse(
        changed=changed,
        message=message,
        ticket=build_snapshot(ticket, actor),
        previous_assignee=assignee_ref(previous),
        new_assignee=assignee_ref(new),
        change_kind=entry.change_kind or AssigneeChangeKind.reassignment,
        from_escalation_level=from_level,
        from_escalation_level_label=escalation_level_label(from_level),
        to_escalation_level=to_level,
        to_escalation_level_label=escalation_level_label(to_level),
        timeline_entry=serialize_entry(entry) if changed else None,
    )


def _log_success(
    started: float,
    ticket: Ticket,
    actor: User,
    previous: User,
    new: User,
    kind: AssigneeChangeKind,
    from_level: EscalationLevel,
    to_level: EscalationLevel,
    changed: bool,
    request_id: UUID,
) -> None:
    duration_ms = round((time.perf_counter() - started) * 1000, 2)
    # El motivo nunca se registra en logs.
    logger.info(
        "Cambio de responsable ticket_id=%s actor_id=%s previous_assignee_id=%s "
        "new_assignee_id=%s change_kind=%s from_level=%s to_level=%s "
        "changed=%s request_id=%s duration_ms=%s",
        ticket.id,
        actor.id,
        previous.id,
        new.id,
        kind.value,
        from_level.value,
        to_level.value,
        changed,
        request_id,
        duration_ms,
    )


# ---------------------------------------------------------------------------
# Comando: reasignación
# ---------------------------------------------------------------------------
def reassign_ticket(
    session: Session,
    ticket_id: UUID,
    current_user: User,
    payload: ReassignmentRequest,
) -> AssigneeChangeResponse:
    started = time.perf_counter()
    ticket = _locked_ticket(session, ticket_id)
    reason = payload.reason.strip()

    entry = _assignee_change_entry(session, ticket.id, payload.request_id)
    replay = _classify_replay(
        entry,
        current_user,
        AssigneeChangeKind.reassignment,
        reason,
        new_assignee_id=payload.new_assignee_id,
    )
    if replay == "replay" and entry is not None:
        _log_success(
            started,
            ticket,
            current_user,
            entry.previous_assignee or current_user,
            entry.new_assignee or current_user,
            AssigneeChangeKind.reassignment,
            entry.from_escalation_level or _level_of(current_user),
            entry.to_escalation_level or _level_of(current_user),
            False,
            payload.request_id,
        )
        return _response_from_entry(
            ticket, current_user, entry, changed=False, message=REPLAY_REASSIGNMENT
        )
    if replay == "reused":
        logger.warning(
            "request_id reutilizado code=request_id_reused ticket_id=%s",
            ticket.id,
        )
        raise _request_id_reused()

    ensure_assignee_change_actor(current_user, ticket)
    _validate_reason(reason)
    _ensure_version(ticket, payload.expected_updated_at)
    _ensure_active(ticket)
    ensure_assignee_consistency(session, ticket)

    previous_assignee = session.get(User, ticket.assignee_id)
    if previous_assignee is None:
        raise _assignee_unavailable()

    if payload.new_assignee_id == previous_assignee.id:
        raise _self_reassignment()
    if payload.new_assignee_id == ticket.creator_id:
        raise _creator_not_assignable()

    destination = session.get(User, payload.new_assignee_id)
    if destination is None or not destination.is_active:
        raise _assignee_unavailable()

    same_level = _level_of(destination) == _level_of(previous_assignee)
    same_team = (
        previous_assignee.team is None
        or destination.team == previous_assignee.team
    )
    if destination.role != UserRole.tecnico or not same_level or not same_team:
        raise _invalid_reassignment_target()

    now = datetime.now(UTC)
    entry = _commit_change(
        session,
        ticket,
        current_user,
        destination,
        AssigneeChangeKind.reassignment,
        reason,
        _level_of(previous_assignee),
        _level_of(destination),
        now,
        payload.request_id,
    )
    _log_success(
        started,
        ticket,
        current_user,
        previous_assignee,
        destination,
        AssigneeChangeKind.reassignment,
        _level_of(previous_assignee),
        _level_of(destination),
        True,
        payload.request_id,
    )
    return _response_from_entry(
        ticket, current_user, entry, changed=True, message=None
    )


# ---------------------------------------------------------------------------
# Comando: escalado
# ---------------------------------------------------------------------------
def escalate_ticket(
    session: Session,
    ticket_id: UUID,
    current_user: User,
    payload: EscalationRequest,
) -> AssigneeChangeResponse:
    started = time.perf_counter()
    ticket = _locked_ticket(session, ticket_id)
    reason = payload.reason.strip()

    entry = _assignee_change_entry(session, ticket.id, payload.request_id)
    replay = _classify_replay(
        entry,
        current_user,
        AssigneeChangeKind.escalation,
        reason,
        target_level=payload.target_level,
    )
    if replay == "replay" and entry is not None:
        _log_success(
            started,
            ticket,
            current_user,
            entry.previous_assignee or current_user,
            entry.new_assignee or current_user,
            AssigneeChangeKind.escalation,
            entry.from_escalation_level or _level_of(current_user),
            entry.to_escalation_level or payload.target_level,
            False,
            payload.request_id,
        )
        return _response_from_entry(
            ticket, current_user, entry, changed=False, message=REPLAY_ESCALATION
        )
    if replay == "reused":
        logger.warning(
            "request_id reutilizado code=request_id_reused ticket_id=%s",
            ticket.id,
        )
        raise _request_id_reused()

    ensure_assignee_change_actor(current_user, ticket)
    _validate_reason(reason)
    _ensure_version(ticket, payload.expected_updated_at)
    _ensure_active(ticket)
    ensure_assignee_consistency(session, ticket)

    previous_assignee = session.get(User, ticket.assignee_id)
    if previous_assignee is None:
        raise _assignee_unavailable()

    from_level = _level_of(previous_assignee)
    if not higher_escalation_levels(from_level):
        logger.warning(
            "Nivel máximo code=no_higher_level ticket_id=%s", ticket.id
        )
        raise _no_higher_level()
    if not is_higher_level(from_level, payload.target_level):
        logger.warning(
            "Nivel no superior code=invalid_escalation_level ticket_id=%s",
            ticket.id,
        )
        raise _invalid_escalation_level()

    destination = select_escalation_assignee(
        session, ticket, payload.target_level
    )
    if destination is None:
        logger.warning(
            "Sin técnicos code=no_technicians_available ticket_id=%s",
            ticket.id,
        )
        raise _no_technicians_available()

    now = datetime.now(UTC)
    to_level = _level_of(destination)
    entry = _commit_change(
        session,
        ticket,
        current_user,
        destination,
        AssigneeChangeKind.escalation,
        reason,
        from_level,
        to_level,
        now,
        payload.request_id,
    )
    _log_success(
        started,
        ticket,
        current_user,
        previous_assignee,
        destination,
        AssigneeChangeKind.escalation,
        from_level,
        to_level,
        True,
        payload.request_id,
    )
    return _response_from_entry(
        ticket, current_user, entry, changed=True, message=None
    )
