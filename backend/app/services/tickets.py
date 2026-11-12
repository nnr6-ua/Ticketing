from __future__ import annotations

from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models import Attachment, Employee, Priority, Ticket, TicketEvent
from app.services.attachments import (
    StagedFile,
    cleanup_staged,
    move_staged,
    remove_files,
)
from app.services.duplicates import compute_content_hash, normalize_text
from app.services.suggestions import suggest


def _validate_fields(title: str, description: str) -> tuple[str, str]:
    clean_title = normalize_text(title)
    clean_description = normalize_text(description)

    if not (5 <= len(clean_title) <= 120):
        raise AppError(
            422,
            "validation_error",
            "El título debe tener entre 5 y 120 caracteres.",
            field="title",
        )
    if not (20 <= len(clean_description) <= 5000):
        raise AppError(
            422,
            "validation_error",
            "La descripción debe tener entre 20 y 5000 caracteres.",
            field="description",
        )
    return clean_title, clean_description


def _find_duplicate(db: Session, employee_id: int, content_hash: str) -> Ticket | None:
    return db.scalar(
        select(Ticket).where(
            Ticket.creator_id == employee_id,
            Ticket.content_hash == content_hash,
        )
    )


def create_ticket(
    db: Session,
    employee: Employee,
    *,
    title: str,
    description: str,
    priority_id: int | None,
    staged: list[StagedFile],
    attachments_dir: Path,
) -> tuple[Ticket, bool]:
    try:
        clean_title, clean_description = _validate_fields(title, description)
        content_hash = compute_content_hash(clean_title, clean_description)

        existing = _find_duplicate(db, employee.id, content_hash)
        if existing is not None:
            cleanup_staged(staged)
            return existing, True

        suggestion = suggest(db, clean_title, clean_description)

        if priority_id is None:
            priority = suggestion.priority
        else:
            priority = db.scalar(
                select(Priority).where(
                    Priority.id == priority_id,
                    Priority.is_active.is_(True),
                    Priority.is_system.is_(False),
                )
            )
            if priority is None:
                raise AppError(
                    422,
                    "invalid_priority",
                    "La prioridad seleccionada no existe, no está activa o es de sistema.",
                    field="priority_id",
                )

        number = db.scalar(select(func.nextval("ticket_number_seq")))
        ticket_number = f"TK-{int(number):06d}"

        ticket = Ticket(
            ticket_number=ticket_number,
            title=clean_title,
            description=clean_description,
            status="Abierto",
            creator_id=employee.id,
            category_id=suggestion.category.id,
            priority_id=priority.id,
            content_hash=content_hash,
        )
    except Exception:
        cleanup_staged(staged)
        raise

    moved: list[tuple[StagedFile, str]] = []

    try:
        db.add(ticket)
        db.flush()

        db.add(
            TicketEvent(
                ticket_id=ticket.id,
                event_type="created",
                author_id=employee.id,
                event_metadata={
                    "ticket_number": ticket_number,
                    "status": "Abierto",
                },
            )
        )

        moved = move_staged(staged, attachments_dir, ticket.ticket_number)
        for item, relative_path in moved:
            db.add(
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

        db.commit()
    except IntegrityError:
        db.rollback()
        cleanup_staged(staged)
        remove_files([str(attachments_dir / relative) for _, relative in moved])
        existing = _find_duplicate(db, employee.id, content_hash)
        if existing is not None:
            return existing, True
        raise AppError(
            409,
            "ticket_conflict",
            "No se pudo crear el ticket por un conflicto de datos.",
        )
    except Exception:
        db.rollback()
        cleanup_staged(staged)
        remove_files([str(attachments_dir / relative) for _, relative in moved])
        raise

    db.refresh(ticket)
    return ticket, False
