"""Creación de tickets (HU-01) sobre el modelo de dominio de master."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.models import (
    Attachment,
    Priority,
    Ticket,
    TicketStatus,
    TicketTimelineEntry,
    TimelineEventType,
    User,
)
from app.services.attachments import (
    StagedFile,
    cleanup_staged,
    move_staged,
    remove_files,
)
from app.services.duplicates import compute_content_hash, normalize_text
from app.services.suggestions import Suggestion, suggest

MAX_TITLE_LENGTH = 120
MAX_DESCRIPTION_LENGTH = 5000


def _validate_fields(title: str, description: str) -> tuple[str, str]:
    clean_title = normalize_text(title)
    clean_description = normalize_text(description)

    if not (5 <= len(clean_title) <= MAX_TITLE_LENGTH):
        raise ApiError(
            422,
            "validation_error",
            f"El título debe tener entre 5 y {MAX_TITLE_LENGTH} caracteres.",
        )
    if not (20 <= len(clean_description) <= MAX_DESCRIPTION_LENGTH):
        raise ApiError(
            422,
            "validation_error",
            f"La descripción debe tener entre 20 y {MAX_DESCRIPTION_LENGTH} caracteres.",
        )
    return clean_title, clean_description


def _find_duplicate(
    session: Session, creator_id: UUID, content_hash: str
) -> Ticket | None:
    return session.scalar(
        select(Ticket).where(
            Ticket.creator_id == creator_id,
            Ticket.content_hash == content_hash,
        )
    )


def _next_ticket_number(session: Session) -> str:
    bind = session.get_bind()
    if bind is not None and bind.dialect.name == "postgresql":
        value = session.scalar(select(func.nextval("ticket_number_seq")))
    else:
        last_number = session.scalar(select(func.max(Ticket.number)))
        value = 1
        if last_number:
            try:
                value = int(last_number.split("-")[-1]) + 1
            except (ValueError, IndexError):
                value = 1
    return f"TK-{int(value):06d}"


def _resolve_priority(
    session: Session,
    priority_id: int | str | None,
    suggestion: Suggestion,
) -> Priority:
    if priority_id is None:
        return suggestion.priority

    priority = session.get(Priority, UUID(str(priority_id)))
    if (
        priority is None
        or not priority.is_active
        or priority.is_system
    ):
        raise ApiError(
            422,
            "invalid_priority",
            "La prioridad seleccionada no existe, no está activa o es de sistema.",
        )
    return priority


def create_ticket(
    session: Session,
    creator: User,
    *,
    title: str,
    description: str,
    priority_id: int | str | None,
    staged: list[StagedFile],
    attachments_dir: Path,
) -> tuple[Ticket, bool]:
    """Crea un ticket o devuelve el duplicado existente del mismo creador."""

    try:
        clean_title, clean_description = _validate_fields(title, description)
        content_hash = compute_content_hash(clean_title, clean_description)

        existing = _find_duplicate(session, creator.id, content_hash)
        if existing is not None:
            cleanup_staged(staged)
            return existing, True

        suggestion = suggest(session, clean_title, clean_description)
        priority = _resolve_priority(session, priority_id, suggestion)
        ticket_number = _next_ticket_number(session)

        ticket = Ticket(
            number=ticket_number,
            title=clean_title,
            description=clean_description,
            status=TicketStatus.abierto,
            creator_id=creator.id,
            category_id=suggestion.category.id,
            priority_id=priority.id,
            content_hash=content_hash,
        )
    except Exception:
        cleanup_staged(staged)
        raise

    moved: list[tuple[StagedFile, str]] = []

    try:
        session.add(ticket)
        session.flush()

        session.add(
            TicketTimelineEntry(
                ticket_id=ticket.id,
                event_type=TimelineEventType.created,
                from_status=None,
                to_status=None,
                body=None,
                is_internal=False,
                author_id=creator.id,
                author=creator,
                created_at=ticket.created_at,
                event_order=0,
                request_id=uuid4(),
            )
        )

        moved = move_staged(staged, attachments_dir, ticket.number)
        for item, relative_path in moved:
            session.add(
                Attachment(
                    ticket_id=ticket.id,
                    original_filename=item.original_filename,
                    stored_filename=item.stored_filename,
                    mime_type=item.mime_type,
                    size_bytes=item.size_bytes,
                    relative_path=relative_path,
                    sha256=item.sha256,
                )
            )

        session.commit()
    except IntegrityError:
        session.rollback()
        cleanup_staged(staged)
        remove_files([str(attachments_dir / relative) for _, relative in moved])
        existing = _find_duplicate(session, creator.id, content_hash)
        if existing is not None:
            return existing, True
        raise ApiError(
            409,
            "ticket_conflict",
            "No se pudo crear el ticket por un conflicto de datos.",
        )
    except Exception:
        session.rollback()
        cleanup_staged(staged)
        remove_files([str(attachments_dir / relative) for _, relative in moved])
        raise

    session.refresh(ticket)
    return ticket, False
