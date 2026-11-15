"""Derivación de petición activa y recordatorio de 48 horas."""

from __future__ import annotations

from datetime import timedelta

from app.models import TicketStatus, TimelineEventType
from app.services.ticket_timeline import information_state


def test_without_status_change_there_is_no_active_request_or_reminder(
    db, seeded_workflow, ticket_pendiente_usuario, timeline_entry_factory
):
    author = seeded_workflow.users["tecnico_asignado"]
    timeline_entry_factory(
        ticket=ticket_pendiente_usuario,
        author=author,
        event_type=TimelineEventType.information_request,
        body="¿Datos?",
        created_at=seeded_workflow.now - timedelta(hours=50),
    )

    state = information_state(db, ticket_pendiente_usuario, now=seeded_workflow.now)

    assert state.pending_since is None
    assert state.active_request is None
    assert state.reminder_due_at is None
    assert state.reminder_active is False


def test_active_request_and_reminder_boundary(
    db, seeded_workflow, ticket_pendiente_usuario, timeline_entry_factory
):
    author = seeded_workflow.users["tecnico_asignado"]
    pending_since = seeded_workflow.now - timedelta(hours=48)
    timeline_entry_factory(
        ticket=ticket_pendiente_usuario,
        author=author,
        event_type=TimelineEventType.status_change,
        from_status=TicketStatus.en_progreso,
        to_status=TicketStatus.pendiente_usuario,
        created_at=pending_since,
        event_order=0,
    )
    request = timeline_entry_factory(
        ticket=ticket_pendiente_usuario,
        author=author,
        event_type=TimelineEventType.information_request,
        body="¿Datos?",
        created_at=pending_since,
        event_order=1,
    )

    state = information_state(db, ticket_pendiente_usuario, now=seeded_workflow.now)
    assert state.active_request is not None
    assert state.active_request.id == request.id
    assert state.reminder_due_at == pending_since + timedelta(hours=48)
    assert state.reminder_active is True

    earlier = information_state(
        db,
        ticket_pendiente_usuario,
        now=seeded_workflow.now - timedelta(seconds=1),
    )
    assert earlier.reminder_active is False


def test_request_before_last_pending_cycle_is_not_active(
    db, seeded_workflow, ticket_pendiente_usuario, timeline_entry_factory
):
    author = seeded_workflow.users["tecnico_asignado"]
    timeline_entry_factory(
        ticket=ticket_pendiente_usuario,
        author=author,
        event_type=TimelineEventType.information_request,
        body="Petición antigua.",
        created_at=seeded_workflow.now - timedelta(hours=5),
        event_order=1,
    )
    timeline_entry_factory(
        ticket=ticket_pendiente_usuario,
        author=author,
        event_type=TimelineEventType.status_change,
        from_status=TicketStatus.en_progreso,
        to_status=TicketStatus.pendiente_usuario,
        created_at=seeded_workflow.now - timedelta(hours=1),
        event_order=0,
    )

    state = information_state(db, ticket_pendiente_usuario, now=seeded_workflow.now)

    assert state.pending_since is not None
    assert state.active_request is None


def test_answered_request_is_not_active(
    db, seeded_workflow, ticket_pendiente_usuario, timeline_entry_factory
):
    technician = seeded_workflow.users["tecnico_asignado"]
    creator = seeded_workflow.users["creador"]
    pending_since = seeded_workflow.now - timedelta(hours=2)
    timeline_entry_factory(
        ticket=ticket_pendiente_usuario,
        author=technician,
        event_type=TimelineEventType.status_change,
        from_status=TicketStatus.en_progreso,
        to_status=TicketStatus.pendiente_usuario,
        created_at=pending_since,
        event_order=0,
    )
    request = timeline_entry_factory(
        ticket=ticket_pendiente_usuario,
        author=technician,
        event_type=TimelineEventType.information_request,
        body="¿Datos?",
        created_at=pending_since,
        event_order=1,
    )
    timeline_entry_factory(
        ticket=ticket_pendiente_usuario,
        author=creator,
        event_type=TimelineEventType.user_response,
        body="Datos.",
        created_at=seeded_workflow.now,
        event_order=1,
        reply_to_id=request.id,
    )
    ticket_pendiente_usuario.status = TicketStatus.en_progreso
    db.commit()

    state = information_state(db, ticket_pendiente_usuario, now=seeded_workflow.now)

    assert state.active_request is None
    assert state.reminder_active is False


def test_information_states_uses_a_constant_number_of_queries(
    db, seeded_workflow
):
    from sqlalchemy import event

    from app.services.ticket_timeline import information_states

    tickets = list(seeded_workflow.tickets.values())
    statements: list[str] = []

    def before_cursor_execute(
        conn, cursor, statement, parameters, context, executemany
    ):
        statements.append(statement)

    engine = db.get_bind()
    event.listen(engine, "before_cursor_execute", before_cursor_execute)
    try:
        states = information_states(db, tickets, now=seeded_workflow.now)
    finally:
        event.remove(engine, "before_cursor_execute", before_cursor_execute)

    assert len(states) == len(tickets)
    assert len(statements) == 3
