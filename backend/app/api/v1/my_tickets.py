"""Endpoint `GET /api/v1/me/tickets` (tickets creados por el usuario)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import STATUS_LABELS, Ticket, User
from app.schemas.my_tickets import (
    MyTicketCategory,
    MyTicketPriority,
    MyTicketsResponse,
    MyTicketSummary,
)

router = APIRouter(tags=["Mis tickets"])


@router.get(
    "/me/tickets",
    response_model=MyTicketsResponse,
    summary="Listar los tickets creados por el usuario autenticado",
    responses={
        401: {"description": "Token JWT ausente, inválido o caducado."},
        500: {"description": "Error inesperado del servidor."},
    },
)
def get_my_tickets(
    response: Response,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> MyTicketsResponse:
    tickets = session.scalars(
        select(Ticket)
        .where(Ticket.creator_id == current_user.id)
        .order_by(Ticket.created_at.desc(), Ticket.number.desc())
    ).all()

    response.headers["Cache-Control"] = "no-store"
    response.headers["Vary"] = "Authorization"

    return MyTicketsResponse(
        items=[
            MyTicketSummary(
                id=ticket.id,
                ticket_number=ticket.number,
                title=ticket.title,
                status=ticket.status,
                status_label=STATUS_LABELS[ticket.status],
                category=(
                    MyTicketCategory(
                        id=ticket.category.id, name=ticket.category.name
                    )
                    if ticket.category is not None
                    else None
                ),
                priority=MyTicketPriority(
                    id=ticket.priority.id,
                    name=ticket.priority.name,
                    level=ticket.priority.level,
                    color=ticket.priority.color,
                ),
                created_at=ticket.created_at,
                updated_at=ticket.updated_at,
            )
            for ticket in tickets
        ]
    )
