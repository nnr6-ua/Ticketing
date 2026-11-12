"""Comandos transaccionales del flujo de trabajo del ticket (HU-05).

Fuente única de la idempotencia: la búsqueda y comparación de `request_id`
viven en este módulo. El router solo traduce los resultados a HTTP.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ApiError, WORKFLOW_WRITE_ERROR_MESSAGE
from app.models import (
    Ticket,
    TicketStatus,
    TicketTimelineEntry,
    TimelineEventType,
    User,
    UserRole,
)
from app.schemas.ticket_workflow import (
    InternalCommentRequest,
    InternalCommentResponse,
    StatusTransitionRequest,
    StatusTransitionResponse,
    TicketWorkflowSnapshot,
    WorkflowResponse,
)
from app.services.ticket_state_machine import (
    allowed_status_options,
    allowed_transitions,
    is_transition_allowed,
    status_label,
)
from app.services.ticket_timeline import (
    as_utc,
    serialize_entry,
    viewer_capabilities,
)

logger = logging.getLogger(__name__)

UTC = timezone.utc

NOOP_MESSAGE = "El ticket ya se encuentra en ese estado."
REPLAY_MESSAGE = (
    "Esta transición ya se aplicó con el identificador de solicitud indicado."
)
INTERNAL_ERROR_MESSAGE = WORKFLOW_WRITE_ERROR_MESSAGE

RESOLUTION_REQUIRED = (
    "Indica la descripción de la solución para marcar el ticket como Resuelto."
)
RESOLUTION_TOO_LONG = (
    "La descripción de la solución no puede superar los 5.000 caracteres."
)
RESOLUTION_NOT_ALLOWED = (
    "La descripción de la solución solo se indica al marcar el ticket como Resuelto."
)
COMMENT_REQUIRED = "El comentario interno no puede estar vacío."
COMMENT_TOO_LONG = (
    "El comentario interno no puede superar los 5.000 caracteres."
)
REQUEST_ID_REUSED = (
    "La solicitud ya se utilizó con otros datos. Genera una nueva solicitud e "
    "inténtalo de nuevo."
)

MAX_BODY_LENGTH = 5000

_TRANSITION_EVENTS = (
    TimelineEventType.status_change,
    TimelineEventType.resolution,
)


# ---------------------------------------------------------------------------
# Helpers compartidos
# ---------------------------------------------------------------------------
def _not_found() -> ApiError:
    return ApiError(404, "ticket_not_found", "No se ha encontrado el ticket.")


def _forbidden() -> ApiError:
    return ApiError(
        403,
        "forbidden",
        "No tienes permiso para modificar este ticket.",
    )


def _not_assignee() -> ApiError:
    return ApiError(
        403,
        "not_ticket_assignee",
        "Este ticket ya no está asignado a ti.",
    )


def _stale() -> ApiError:
    return ApiError(
        409,
        "stale_ticket",
        "El ticket ha sido modificado por otra persona. Actualiza la "
        "información e inténtalo de nuevo.",
    )


def _request_id_reused() -> ApiError:
    return ApiError(409, "request_id_reused", REQUEST_ID_REUSED)


def _now() -> datetime:
    return datetime.now(UTC)


def load_ticket(session: Session, ticket_id: UUID) -> Ticket:
    """Carga un ticket o lanza `404 ticket_not_found`."""

    ticket = session.get(Ticket, ticket_id)
    if ticket is None:
        raise _not_found()
    return ticket


def _locked_ticket(session: Session, ticket_id: UUID) -> Ticket:
    """Carga el ticket con bloqueo de fila en PostgreSQL.

    El bloqueo se aplica solo a la fila de `tickets` (no al `SELECT` con las
    relaciones eager): PostgreSQL rechaza `FOR UPDATE` sobre el lado nullable
    de un `OUTER JOIN`. Una vez adquirido el bloqueo, la carga del modelo con
    sus relaciones se hace sin bloquear y dentro de la misma transacción.
    """

    locked_id = session.scalar(
        select(Ticket.id).where(Ticket.id == ticket_id).with_for_update()
    )
    if locked_id is None:
        raise _not_found()
    # `populate_existing=True` fuerza releer la fila confirmada tras adquirir
    # el bloqueo. Sin ello, `session.get` devolvería la instancia obsoleta del
    # identity map del llamador (precargada antes de que otra transacción
    # confirmara un cambio) y la validación de estado/`updated_at` se haría
    # contra datos viejos (T071).
    ticket = session.get(Ticket, locked_id, populate_existing=True)
    if ticket is None:
        raise _not_found()
    return ticket


def _ensure_writer(user: User, ticket: Ticket) -> None:
    """Solo el técnico asignado puede escribir en este ticket."""

    if user.role != UserRole.tecnico:
        logger.warning(
            "Acceso denegado code=forbidden ticket_id=%s", ticket.id
        )
        raise _forbidden()
    if ticket.assignee_id is None or ticket.assignee_id != user.id:
        logger.warning(
            "Acceso denegado code=not_ticket_assignee ticket_id=%s", ticket.id
        )
        raise _not_assignee()


def build_snapshot(ticket: Ticket, user: User) -> TicketWorkflowSnapshot:
    """Snapshot del ticket con las capacidades del usuario."""

    capabilities = viewer_capabilities(user, ticket)
    options = (
        allowed_status_options(ticket.status)
        if capabilities.can_change_status
        else []
    )
    return TicketWorkflowSnapshot(
        id=ticket.id,
        number=ticket.number,
        title=ticket.title,
        status=ticket.status,
        status_label=status_label(ticket.status),
        assignee_id=ticket.assignee_id,
        creator_id=ticket.creator_id,
        finalized_at=as_utc(ticket.finalized_at),
        closed_at=as_utc(ticket.closed_at),
        updated_at=as_utc(ticket.updated_at) or ticket.updated_at,
        allowed_transitions=options,
    )


def get_workflow(session: Session, ticket: Ticket, user: User) -> WorkflowResponse:
    """Proyección de lectura del flujo del ticket."""

    capabilities = viewer_capabilities(user, ticket)
    return WorkflowResponse(
        ticket=build_snapshot(ticket, user),
        can_change_status=capabilities.can_change_status,
        can_comment_internally=capabilities.can_comment_internally,
        can_view_internal=capabilities.can_view_internal,
    )


# ---------------------------------------------------------------------------
# Idempotencia
# ---------------------------------------------------------------------------
def _transition_entries(
    session: Session, ticket_id: UUID, request_id: UUID
) -> list[TicketTimelineEntry]:
    statement = (
        select(TicketTimelineEntry)
        .where(
            TicketTimelineEntry.ticket_id == ticket_id,
            TicketTimelineEntry.request_id == request_id,
            TicketTimelineEntry.event_type.in_(_TRANSITION_EVENTS),
        )
        .order_by(
            TicketTimelineEntry.event_order.asc(),
            TicketTimelineEntry.id.asc(),
        )
    )
    return list(session.scalars(statement).unique().all())


def _classify_transition_replay(
    entries: list[TicketTimelineEntry],
    actor_id: UUID,
    target: TicketStatus,
    normalized_resolution: str | None,
) -> str:
    """Devuelve `none`, `replay` o `reused` para un `request_id`."""

    if not entries:
        return "none"

    status_change = next(
        (entry for entry in entries if entry.event_type == TimelineEventType.status_change),
        None,
    )
    resolution = next(
        (entry for entry in entries if entry.event_type == TimelineEventType.resolution),
        None,
    )

    same_actor = status_change is not None and status_change.author_id == actor_id
    same_target = status_change is not None and status_change.to_status == target
    if not (same_actor and same_target):
        return "reused"

    if target == TicketStatus.resuelto:
        if (
            resolution is not None
            and normalized_resolution is not None
            and resolution.body == normalized_resolution
        ):
            return "replay"
        return "reused"

    if resolution is not None or normalized_resolution is not None:
        return "reused"
    return "replay"


def _comment_entries(
    session: Session, ticket_id: UUID, request_id: UUID
) -> list[TicketTimelineEntry]:
    statement = select(TicketTimelineEntry).where(
        TicketTimelineEntry.ticket_id == ticket_id,
        TicketTimelineEntry.request_id == request_id,
        TicketTimelineEntry.event_type == TimelineEventType.internal_comment,
    )
    return list(session.scalars(statement).unique().all())


# ---------------------------------------------------------------------------
# Comando: cambio de estado (+ resolución)
# ---------------------------------------------------------------------------
def _ensure_resolution_allowed(
    ticket_id: UUID, target: TicketStatus, raw_resolution: str | None
) -> None:
    """`resolution` solo acompaña a un destino `resuelto` (RF-034).

    Se evalúa antes del no-op por mismo estado para que un envío con
    resolución y destino distinto de `resuelto` nunca se acepte como no-op.
    """

    if target != TicketStatus.resuelto and raw_resolution is not None:
        logger.warning(
            "Resolución no válida code=resolution_not_allowed ticket_id=%s",
            ticket_id,
        )
        raise ApiError(422, "resolution_not_allowed", RESOLUTION_NOT_ALLOWED)


def _validate_resolution(
    ticket_id: UUID, target: TicketStatus, raw_resolution: str | None
) -> str | None:
    if target == TicketStatus.resuelto:
        body = raw_resolution.strip() if raw_resolution is not None else ""
        if not body:
            logger.warning(
                "Resolución no válida code=resolution_required ticket_id=%s",
                ticket_id,
            )
            raise ApiError(422, "resolution_required", RESOLUTION_REQUIRED)
        if len(body) > MAX_BODY_LENGTH:
            logger.warning(
                "Resolución no válida code=resolution_too_long ticket_id=%s",
                ticket_id,
            )
            raise ApiError(422, "resolution_too_long", RESOLUTION_TOO_LONG)
        return body
    return None


def _invalid_transition(current: TicketStatus, target: TicketStatus) -> ApiError:
    available = ", ".join(
        status_label(status) for status in allowed_transitions(current)
    )
    return ApiError(
        409,
        "invalid_transition",
        f"No puedes pasar de {status_label(current)} a {status_label(target)}. "
        f"Estados disponibles: {available or 'ninguno'}.",
    )


def _apply_ticket_effects(
    ticket: Ticket, target: TicketStatus, now: datetime
) -> None:
    ticket.status = target
    ticket.updated_at = now

    if target == TicketStatus.resuelto:
        ticket.finalized_at = now
        ticket.closed_at = None
    elif target == TicketStatus.cerrado:
        # `finalized_at` se conserva desde el paso a resuelto.
        ticket.closed_at = now
    else:
        # Cualquier estado activo limpia la finalización (reapertura incluida).
        ticket.finalized_at = None
        ticket.closed_at = None


def _insert_status_change(
    session: Session,
    ticket: Ticket,
    actor: User,
    from_status: TicketStatus,
    to_status: TicketStatus,
    now: datetime,
    request_id: UUID,
) -> TicketTimelineEntry:
    entry = TicketTimelineEntry(
        ticket_id=ticket.id,
        event_type=TimelineEventType.status_change,
        from_status=from_status,
        to_status=to_status,
        body=None,
        is_internal=False,
        author_id=actor.id,
        author=actor,
        created_at=now,
        event_order=0,
        request_id=request_id,
    )
    session.add(entry)
    return entry


def _insert_resolution(
    session: Session,
    ticket: Ticket,
    actor: User,
    body: str,
    now: datetime,
    request_id: UUID,
) -> TicketTimelineEntry:
    entry = TicketTimelineEntry(
        ticket_id=ticket.id,
        event_type=TimelineEventType.resolution,
        from_status=None,
        to_status=TicketStatus.resuelto,
        body=body,
        is_internal=False,
        author_id=actor.id,
        author=actor,
        created_at=now,
        event_order=1,
        request_id=request_id,
    )
    session.add(entry)
    return entry


def change_status(
    session: Session,
    ticket_id: UUID,
    current_user: User,
    payload: StatusTransitionRequest,
) -> StatusTransitionResponse:
    """Ejecuta un cambio de estado de forma atómica e idempotente."""

    started = time.perf_counter()
    ticket = _locked_ticket(session, ticket_id)
    _ensure_writer(current_user, ticket)

    normalized_resolution = (
        payload.resolution.strip() if payload.resolution is not None else None
    )
    target = payload.target_status

    entries = _transition_entries(session, ticket.id, payload.request_id)
    replay = _classify_transition_replay(
        entries, current_user.id, target, normalized_resolution
    )
    if replay == "replay":
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        source = entries[0].from_status if entries else None
        logger.info(
            "Transición idempotente ticket_id=%s actor_id=%s from_status=%s "
            "to_status=%s changed=false request_id=%s duration_ms=%s",
            ticket.id,
            current_user.id,
            source.value if source else None,
            target.value,
            payload.request_id,
            duration_ms,
        )
        return StatusTransitionResponse(
            changed=False,
            message=REPLAY_MESSAGE,
            ticket=build_snapshot(ticket, current_user),
            timeline_entries=[],
        )
    if replay == "reused":
        logger.warning(
            "request_id reutilizado code=request_id_reused ticket_id=%s",
            ticket.id,
        )
        raise _request_id_reused()

    _ensure_resolution_allowed(ticket.id, target, payload.resolution)

    if target == ticket.status:
        return StatusTransitionResponse(
            changed=False,
            message=NOOP_MESSAGE,
            ticket=build_snapshot(ticket, current_user),
            timeline_entries=[],
        )

    expected = as_utc(payload.expected_updated_at)
    current = as_utc(ticket.updated_at)
    if expected is None or current is None or expected != current:
        logger.warning(
            "Conflicto de versión code=stale_ticket ticket_id=%s", ticket.id
        )
        raise _stale()

    if ticket.status == TicketStatus.cerrado:
        logger.warning("Ticket cerrado code=ticket_closed ticket_id=%s", ticket.id)
        raise ApiError(
            409,
            "ticket_closed",
            "El ticket está cerrado y no admite cambios de estado.",
        )

    if not is_transition_allowed(ticket.status, target):
        logger.warning(
            "Transición inválida code=invalid_transition ticket_id=%s",
            ticket.id,
        )
        raise _invalid_transition(ticket.status, target)

    body = _validate_resolution(ticket.id, target, payload.resolution)
    from_status = ticket.status
    now = _now()

    try:
        _apply_ticket_effects(ticket, target, now)
        status_entry = _insert_status_change(
            session,
            ticket,
            current_user,
            from_status,
            target,
            now,
            payload.request_id,
        )
        created = [status_entry]
        if target == TicketStatus.resuelto and body is not None:
            resolution_entry = _insert_resolution(
                session,
                ticket,
                current_user,
                body,
                now,
                payload.request_id,
            )
            created.append(resolution_entry)

        session.flush()
        session.commit()
    except Exception as exc:  # noqa: BLE001 - se traduce a error estable
        session.rollback()
        logger.exception(
            "Error inesperado al cambiar el estado ticket_id=%s", ticket.id
        )
        raise ApiError(500, "internal_error", INTERNAL_ERROR_MESSAGE) from exc

    duration_ms = round((time.perf_counter() - started) * 1000, 2)
    logger.info(
        "Cambio de estado ticket_id=%s actor_id=%s from_status=%s "
        "to_status=%s changed=true request_id=%s duration_ms=%s",
        ticket.id,
        current_user.id,
        from_status.value,
        target.value,
        payload.request_id,
        duration_ms,
    )

    return StatusTransitionResponse(
        changed=True,
        message=None,
        ticket=build_snapshot(ticket, current_user),
        timeline_entries=[serialize_entry(entry) for entry in created],
    )


def apply_user_response_transition(
    session: Session,
    ticket: Ticket,
    actor: User,
    *,
    request_id: UUID,
    expected_updated_at: datetime,
) -> StatusTransitionResponse:
    """Transición automática `pendiente_usuario -> en_progreso` para HU-03.

    No hace `commit()` ni `rollback()`: participa en la transacción del
    llamador y deja el trabajo preparado con `flush()`.
    """

    locked = _locked_ticket(session, ticket.id)
    if actor.id != locked.creator_id:
        logger.warning(
            "Acceso denegado code=forbidden ticket_id=%s", locked.id
        )
        raise _forbidden()

    target = TicketStatus.en_progreso
    entries = _transition_entries(session, locked.id, request_id)
    replay = _classify_transition_replay(entries, actor.id, target, None)
    if replay == "replay":
        return StatusTransitionResponse(
            changed=False,
            message=REPLAY_MESSAGE,
            ticket=build_snapshot(locked, actor),
            timeline_entries=[],
        )
    if replay == "reused":
        logger.warning(
            "request_id reutilizado code=request_id_reused ticket_id=%s",
            locked.id,
        )
        raise _request_id_reused()

    if locked.status != TicketStatus.pendiente_usuario:
        logger.warning(
            "Transición inválida code=invalid_transition ticket_id=%s",
            locked.id,
        )
        raise _invalid_transition(locked.status, target)

    expected = as_utc(expected_updated_at)
    current = as_utc(locked.updated_at)
    if expected is None or current is None or expected != current:
        logger.warning(
            "Conflicto de versión code=stale_ticket ticket_id=%s", locked.id
        )
        raise _stale()

    if not is_transition_allowed(locked.status, target):
        logger.warning(
            "Transición inválida code=invalid_transition ticket_id=%s",
            locked.id,
        )
        raise _invalid_transition(locked.status, target)

    from_status = locked.status
    now = _now()
    _apply_ticket_effects(locked, target, now)
    status_entry = _insert_status_change(
        session,
        locked,
        actor,
        from_status,
        target,
        now,
        request_id,
    )
    session.flush()

    return StatusTransitionResponse(
        changed=True,
        message=None,
        ticket=build_snapshot(locked, actor),
        timeline_entries=[serialize_entry(status_entry)],
    )


# ---------------------------------------------------------------------------
# Comando: comentario interno
# ---------------------------------------------------------------------------
def add_internal_comment(
    session: Session,
    ticket_id: UUID,
    current_user: User,
    payload: InternalCommentRequest,
) -> InternalCommentResponse:
    """Añade una nota interna sin cambiar el estado del ticket."""

    started = time.perf_counter()
    ticket = _locked_ticket(session, ticket_id)
    _ensure_writer(current_user, ticket)

    body = payload.body.strip()
    if not body:
        logger.warning(
            "Comentario no válido code=comment_required ticket_id=%s", ticket.id
        )
        raise ApiError(422, "comment_required", COMMENT_REQUIRED)
    if len(body) > MAX_BODY_LENGTH:
        logger.warning(
            "Comentario no válido code=comment_too_long ticket_id=%s", ticket.id
        )
        raise ApiError(422, "comment_too_long", COMMENT_TOO_LONG)

    existing = _comment_entries(session, ticket.id, payload.request_id)
    if existing:
        entry = existing[0]
        if entry.author_id == current_user.id and entry.body == body:
            logger.info(
                "Comentario idempotente ticket_id=%s actor_id=%s created=false "
                "request_id=%s",
                ticket.id,
                current_user.id,
                payload.request_id,
            )
            return InternalCommentResponse(
                entry=serialize_entry(entry), created=False
            )
        logger.warning(
            "request_id reutilizado code=request_id_reused ticket_id=%s",
            ticket.id,
        )
        raise _request_id_reused()

    now = _now()
    try:
        entry = TicketTimelineEntry(
            ticket_id=ticket.id,
            event_type=TimelineEventType.internal_comment,
            from_status=None,
            to_status=None,
            body=body,
            is_internal=True,
            author_id=current_user.id,
            author=current_user,
            created_at=now,
            event_order=0,
            request_id=payload.request_id,
        )
        session.add(entry)
        session.flush()
        session.commit()
    except Exception as exc:  # noqa: BLE001 - se traduce a error estable
        session.rollback()
        logger.exception(
            "Error inesperado al añadir comentario ticket_id=%s", ticket.id
        )
        raise ApiError(500, "internal_error", INTERNAL_ERROR_MESSAGE) from exc

    duration_ms = round((time.perf_counter() - started) * 1000, 2)
    logger.info(
        "Comentario interno ticket_id=%s actor_id=%s created=true "
        "request_id=%s duration_ms=%s",
        ticket.id,
        current_user.id,
        payload.request_id,
        duration_ms,
    )
    return InternalCommentResponse(entry=serialize_entry(entry), created=True)
