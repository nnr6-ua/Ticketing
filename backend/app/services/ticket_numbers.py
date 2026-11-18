from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models import Ticket


def max_ticket_number_value(numbers: Iterable[str]) -> int:
    """Devuelve el mayor sufijo numérico de una lista de números de ticket."""

    highest = 0
    for number in numbers:
        suffix = number.rsplit("-", 1)[-1]
        if suffix.isdigit():
            highest = max(highest, int(suffix))
    return highest or 1


def sync_ticket_number_sequence(session: Session) -> None:
    """Ajusta la secuencia PostgreSQL al mayor número ya persistido."""

    if session.get_bind().dialect.name != "postgresql":
        return
    highest = max_ticket_number_value(session.scalars(select(Ticket.number)).all())
    session.execute(
        text("SELECT setval('ticket_number_seq', :value, :called)"),
        {"value": highest, "called": highest > 1},
    )
