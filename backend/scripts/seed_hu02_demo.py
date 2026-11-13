"""Ticket de ejemplo para la validación manual de la HU-02.

Crea (o actualiza) un ticket assignado al Técnico A con un historial rico de
estados y comentarios internos, usando un identificador determinista para que
el frontend pueda enlazarlo desde el login de desarrollo.

Uso:
    python backend/scripts/seed_hu02_demo.py

Es idempotente: reutiliza el ticket por número y recrea su línea temporal.
"""

from __future__ import annotations

import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import (
    Category,
    Priority,
    Ticket,
    TicketStatus,
    TicketTimelineEntry,
    TimelineEventType,
    User,
    UserRole,
)

NAMESPACE = uuid.UUID("6f1f4c2e-9d5a-4c7b-8a3d-2b1c0d9e8f70")
DEMO_NUMBER = "TK-DEMO-02"
DEMO_TICKET_ID = uuid.uuid5(NAMESPACE, f"ticket-{DEMO_NUMBER}")


def _entry(
    *,
    index: int,
    created_at: datetime,
    event_type: TimelineEventType,
    from_status: TicketStatus | None = None,
    to_status: TicketStatus | None = None,
    body: str | None = None,
    is_internal: bool = False,
    event_order: int = 0,
) -> TicketTimelineEntry:
    return TicketTimelineEntry(
        id=uuid.uuid5(NAMESPACE, f"timeline-{DEMO_NUMBER}-{index}"),
        ticket_id=DEMO_TICKET_ID,
        event_type=event_type,
        from_status=from_status,
        to_status=to_status,
        body=body,
        is_internal=is_internal,
        author_id=uuid.uuid5(NAMESPACE, "user-tecnico-a"),
        created_at=created_at,
        event_order=event_order,
        request_id=uuid.uuid5(NAMESPACE, f"timeline-req-{DEMO_NUMBER}-{index}"),
    )


def _seed_timeline(session: Session, base: datetime) -> None:
    session.execute(
        delete(TicketTimelineEntry).where(
            TicketTimelineEntry.ticket_id == DEMO_TICKET_ID
        )
    )

    entries = [
        _entry(
            index=1,
            created_at=base,
            event_type=TimelineEventType.status_change,
            from_status=TicketStatus.abierto,
            to_status=TicketStatus.en_progreso,
        ),
        _entry(
            index=2,
            created_at=base + timedelta(minutes=20),
            event_type=TimelineEventType.internal_comment,
            body=(
                "Diagnóstico inicial: el equipo no resuelve el nombre del "
                "servidor interno tras el cambio de red."
            ),
            is_internal=True,
        ),
        _entry(
            index=3,
            created_at=base + timedelta(hours=2),
            event_type=TimelineEventType.internal_comment,
            body="Se aplica una política de DNS temporal y se valida el acceso.",
            is_internal=True,
        ),
        _entry(
            index=4,
            created_at=base + timedelta(days=1, hours=1),
            event_type=TimelineEventType.status_change,
            from_status=TicketStatus.en_progreso,
            to_status=TicketStatus.pendiente_usuario,
        ),
        _entry(
            index=5,
            created_at=base + timedelta(days=1, hours=1, minutes=5),
            event_type=TimelineEventType.internal_comment,
            body="Se solicita al usuario una captura del error para confirmar.",
            is_internal=True,
        ),
        _entry(
            index=6,
            created_at=base + timedelta(days=1, hours=4),
            event_type=TimelineEventType.status_change,
            from_status=TicketStatus.pendiente_usuario,
            to_status=TicketStatus.en_progreso,
        ),
        _entry(
            index=7,
            created_at=base + timedelta(days=1, hours=4, minutes=15),
            event_type=TimelineEventType.internal_comment,
            body="El usuario confirma que ya alcanza el recurso compartido.",
            is_internal=True,
        ),
        _entry(
            index=8,
            created_at=base + timedelta(days=2),
            event_type=TimelineEventType.internal_comment,
            body="Validación final pendiente con el equipo de redes.",
            is_internal=True,
        ),
        _entry(
            index=9,
            created_at=base + timedelta(days=2, hours=1),
            event_type=TimelineEventType.status_change,
            from_status=TicketStatus.en_progreso,
            to_status=TicketStatus.pendiente_usuario,
        ),
        _entry(
            index=10,
            created_at=base + timedelta(days=2, hours=3),
            event_type=TimelineEventType.internal_comment,
            body="Se comparte el plan de pruebas con el usuario implicado.",
            is_internal=True,
        ),
    ]
    session.add_all(entries)


def main() -> None:
    now = datetime.now(timezone.utc).replace(microsecond=0)
    base = (now - timedelta(days=2)).replace(hour=9, minute=0, second=0)

    with SessionLocal() as session:
        technician = session.scalar(
            select(User).where(User.email == "tecnico.a@example.com")
        )
        requester = session.scalar(
            select(User).where(User.email == "usuario@example.com")
        )
        priority = session.scalar(select(Priority).where(Priority.level == 2))
        category = session.scalar(select(Category).where(Category.name == "Red"))

        if technician is None or requester is None or priority is None:
            raise SystemExit(
                "Faltan datos base. Ejecuta primero scripts/seed_dev.py."
            )

        if technician.role != UserRole.tecnico:
            raise SystemExit("El usuario técnico del seed no tiene rol técnico.")

        ticket = session.scalar(select(Ticket).where(Ticket.number == DEMO_NUMBER))
        if ticket is None:
            ticket = Ticket(id=DEMO_TICKET_ID, number=DEMO_NUMBER)
            session.add(ticket)

        ticket.title = "El dominio interno no resuelve tras cambiar de red"
        ticket.description = (
            "Ticket de ejemplo de la HU-02: seguimiento de la evolución del "
            "ticket, con cambios de estado y comentarios internos del técnico."
        )
        ticket.status = TicketStatus.pendiente_usuario
        ticket.priority_id = priority.id
        ticket.category_id = category.id if category else None
        ticket.creator_id = requester.id
        ticket.assignee_id = technician.id
        ticket.created_at = base
        ticket.sla_deadline = base + timedelta(hours=48)
        ticket.finalized_at = None
        ticket.closed_at = None
        ticket.updated_at = base + timedelta(days=2, hours=3)
        ticket.sla_version = "v1"

        session.flush()
        _seed_timeline(session, base)
        session.commit()

    print(f"Ticket de ejemplo: {DEMO_NUMBER} ({DEMO_TICKET_ID})")
    print(
        "Abre: http://localhost:5173/tickets/"
        f"{DEMO_TICKET_ID}"
    )


if __name__ == "__main__":
    main()
