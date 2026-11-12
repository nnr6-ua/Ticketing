from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Employee
from app.services.tickets import create_ticket


def test_ticket_numbers_increment_without_reuse(
    db_session: Session, tmp_path: Path
) -> None:
    employee = db_session.scalar(select(Employee))
    assert employee is not None

    first, _ = create_ticket(
        db_session,
        employee,
        title="No funciona la VPN",
        description="No puedo conectar desde ayer por la tarde.",
        priority_id=None,
        staged=[],
        attachments_dir=tmp_path,
    )
    second, _ = create_ticket(
        db_session,
        employee,
        title="Solicitud de información",
        description="Necesito información sobre el proceso de vacaciones.",
        priority_id=None,
        staged=[],
        attachments_dir=tmp_path,
    )

    assert first.ticket_number == "TK-000001"
    assert second.ticket_number == "TK-000002"
    assert first.ticket_number != second.ticket_number
