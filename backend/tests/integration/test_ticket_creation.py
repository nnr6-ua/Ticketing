from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Employee, TicketEvent
from app.services.tickets import create_ticket


def test_persists_ticket_and_creation_event(
    db_session: Session, tmp_path: Path
) -> None:
    employee = db_session.scalar(select(Employee))
    assert employee is not None

    ticket, duplicate = create_ticket(
        db_session,
        employee,
        title="No funciona la VPN",
        description="No puedo conectar desde ayer por la tarde.",
        priority_id=None,
        staged=[],
        attachments_dir=tmp_path,
    )

    assert duplicate is False
    assert ticket.ticket_number == "TK-000001"
    assert ticket.status == "Abierto"

    event = db_session.scalar(
        select(TicketEvent).where(TicketEvent.ticket_id == ticket.id)
    )
    assert event is not None
    assert event.event_type == "created"
    assert event.author_id == employee.id
    assert event.event_metadata == {
        "ticket_number": "TK-000001",
        "status": "Abierto",
    }
