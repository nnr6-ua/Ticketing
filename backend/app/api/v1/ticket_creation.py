"""Endpoints de creación de tickets y catálogos auxiliares (HU-01)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.db.session import get_session
from app.models import Attachment, Priority, Ticket, User
from app.schemas.ticket_creation import (
    AttachmentRead,
    CategoryRead,
    PriorityRead,
    SuggestionRequest,
    SuggestionResponse,
    TicketRead,
    UserRead,
)
from app.services.attachments import cleanup_staged, stage_files
from app.services.suggestions import suggest
from app.services.ticket_creation import create_ticket

router = APIRouter(tags=["Creación de tickets"])


def _ticket_read(
    session: Session, ticket: Ticket, *, duplicate: bool
) -> TicketRead:
    creator = session.get(User, ticket.creator_id)
    attachments = session.scalars(
        select(Attachment)
        .where(Attachment.ticket_id == ticket.id)
        .order_by(Attachment.created_at.asc())
    ).all()

    if creator is None or ticket.category is None:
        raise RuntimeError("Ticket sin creador o categoría asociados.")

    return TicketRead(
        id=ticket.id,
        ticket_number=ticket.number,
        title=ticket.title,
        description=ticket.description or "",
        status=ticket.status.label,
        creator=UserRead.model_validate(creator),
        category=CategoryRead.model_validate(ticket.category),
        priority=PriorityRead.model_validate(ticket.priority),
        attachments=[
            AttachmentRead.model_validate(attachment)
            for attachment in attachments
        ],
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
        duplicate=duplicate,
    )


@router.get(
    "/priorities",
    response_model=list[PriorityRead],
    summary="Lista las prioridades activas seleccionables",
)
def list_priorities(
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
) -> list[Priority]:
    return list(
        session.scalars(
            select(Priority)
            .where(
                Priority.is_active.is_(True),
                Priority.is_system.is_(False),
            )
            .order_by(Priority.sort_order, Priority.level)
        ).all()
    )


@router.post(
    "/suggestions",
    response_model=SuggestionResponse,
    summary="Sugiere categoría y prioridad a partir del texto del ticket",
)
def get_suggestion(
    payload: SuggestionRequest,
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
) -> SuggestionResponse:
    result = suggest(session, payload.title, payload.description)
    return SuggestionResponse(
        category=CategoryRead.model_validate(result.category),
        priority=PriorityRead.model_validate(result.priority),
        category_is_fallback=result.category_is_fallback,
        priority_is_fallback=result.priority_is_fallback,
    )


@router.post(
    "/tickets",
    response_model=TicketRead,
    status_code=201,
    summary="Crea un ticket con adjuntos opcionales",
)
async def create_ticket_endpoint(
    response: Response,
    title: Annotated[str, Form(min_length=5, max_length=120)],
    description: Annotated[str, Form(min_length=20, max_length=5000)],
    priority_id: Annotated[str | None, Form()] = None,
    attachments: Annotated[list[UploadFile] | None, File()] = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> TicketRead:
    settings = get_settings()
    temp_dir = settings.attachments_dir / "tmp"
    staged = await stage_files(attachments or [], temp_dir)

    try:
        ticket, duplicate = create_ticket(
            session,
            current_user,
            title=title,
            description=description,
            priority_id=priority_id,
            staged=staged,
            attachments_dir=settings.attachments_dir,
        )
    except Exception:
        cleanup_staged(staged)
        raise

    if duplicate:
        response.status_code = 200

    return _ticket_read(session, ticket, duplicate=duplicate)
