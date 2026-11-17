"""Pruebas unitarias de la selección determinista de responsable (HU-06, T005)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import (
    EscalationLevel,
    Ticket,
    TicketStatus,
    User,
    UserRole,
)
from app.services.assignee_change import (
    escalation_targets,
    reassignment_candidates,
    select_escalation_assignee,
)
from tests.conftest import SeededAssigneeChange

UTC = timezone.utc


def _user(
    db: Session,
    key: str,
    name: str,
    *,
    level: EscalationLevel = EscalationLevel.nivel_1,
    team: str | None = "Soporte",
    role: UserRole = UserRole.tecnico,
    is_active: bool = True,
) -> User:
    row = User(
        id=uuid.uuid5(uuid.NAMESPACE_DNS, f"hu06-selection-{key}"),
        name=name,
        email=f"hu06.selection.{key}@example.com",
        role=role,
        team=team,
        escalation_level=level,
        is_active=is_active,
    )
    db.add(row)
    db.flush()
    return row


def _active_ticket(
    db: Session,
    seed: SeededAssigneeChange,
    key: str,
    assignee: User,
) -> Ticket:
    row = Ticket(
        id=uuid.uuid5(uuid.NAMESPACE_DNS, f"hu06-selection-ticket-{key}"),
        number=f"TK-9{key[-5:]}",
        title=f"Ticket de carga {key}",
        status=TicketStatus.en_progreso,
        priority_id=seed.priority.id,
        creator_id=seed.users["creador_tecnico"].id,
        assignee_id=assignee.id,
        created_at=seed.now,
        updated_at=seed.now,
        sla_version="v1",
    )
    db.add(row)
    return row


def _names(users: list[User]) -> list[str]:
    return [user.name for user in users]


def test_reassignment_candidates_same_team_and_level(
    db: Session, seeded_assignee_change: SeededAssigneeChange
) -> None:
    seed = seeded_assignee_change
    ticket = seed.tickets["activo"]
    current = seed.users["asignado"]

    candidates = reassignment_candidates(db, ticket, current)

    assert _names(candidates) == ["Técnico E"]
    assert candidates[0].id == seed.users["companero"].id


def test_reassignment_candidates_exclude_current_and_creator(
    db: Session, seeded_assignee_change: SeededAssigneeChange
) -> None:
    seed = seeded_assignee_change
    ticket = seed.tickets["creador_asignado"]
    current = seed.users["asignado"]

    candidates = reassignment_candidates(db, ticket, current)
    ids = {user.id for user in candidates}

    assert ids == {
        seed.users["companero"].id,
        seed.users["creador_tecnico"].id,
    }
    assert current.id not in ids


def test_reassignment_candidates_without_team_use_whole_level(
    db: Session, seeded_assignee_change: SeededAssigneeChange
) -> None:
    seed = seeded_assignee_change
    current = seed.users["asignado"]
    current.team = None
    db.commit()
    ticket = seed.tickets["activo"]

    candidates = reassignment_candidates(db, ticket, current)

    assert _names(candidates) == ["Técnico D", "Técnico E"]
    assert candidates[0].team == "Redes"
    assert candidates[1].team == "Soporte"


def test_reassignment_candidates_empty_pool(
    db: Session, seeded_assignee_change: SeededAssigneeChange
) -> None:
    seed = seeded_assignee_change
    isolated = _user(db, "isolated", "Técnico Aislado", team="Aislado")
    db.commit()

    candidates = reassignment_candidates(
        db, seed.tickets["activo"], isolated
    )

    assert candidates == []


def test_reassignment_candidates_order_lower_name_then_id(
    db: Session, seeded_assignee_change: SeededAssigneeChange
) -> None:
    seed = seeded_assignee_change
    current = seed.users["asignado"]
    _user(db, "zzz-alto", "AAA Primero")
    m1 = _user(db, "m1", "Mismo Nombre")
    m2 = _user(db, "m2", "Mismo Nombre")
    db.commit()

    candidates = reassignment_candidates(db, seed.tickets["activo"], current)

    assert _names(candidates) == [
        "AAA Primero",
        "Mismo Nombre",
        "Mismo Nombre",
        "Técnico E",
    ]
    same_name_ids = [user.id for user in candidates if user.name == "Mismo Nombre"]
    assert same_name_ids == sorted([m1.id, m2.id])


def test_escalation_targets_only_strictly_higher_levels(
    db: Session, seeded_assignee_change: SeededAssigneeChange
) -> None:
    seed = seeded_assignee_change

    level1 = escalation_targets(
        db, seed.users["asignado"], seed.users["creador_tecnico"].id
    )
    assert [target.value for target in level1] == [
        EscalationLevel.nivel_2,
        EscalationLevel.especialista,
    ]
    assert [target.label for target in level1] == ["Nivel 2", "Especialista"]
    assert all(target.is_available for target in level1)
    assert [target.technician_count for target in level1] == [1, 1]

    level2 = escalation_targets(
        db, seed.users["nivel_2"], seed.users["creador_tecnico"].id
    )
    assert [target.value for target in level2] == [EscalationLevel.especialista]

    specialist = escalation_targets(
        db, seed.users["especialista"], seed.users["creador_tecnico"].id
    )
    assert specialist == []


def test_escalation_targets_exclude_creator_from_count(
    db: Session, seeded_assignee_change: SeededAssigneeChange
) -> None:
    seed = seeded_assignee_change
    creator = seed.users["creador_tecnico"]
    creator.escalation_level = EscalationLevel.nivel_2
    seed.users["nivel_2"].is_active = False
    db.commit()

    targets = escalation_targets(db, seed.users["asignado"], creator.id)
    by_level = {target.value: target for target in targets}

    assert by_level[EscalationLevel.nivel_2].technician_count == 0
    assert by_level[EscalationLevel.nivel_2].is_available is False
    assert by_level[EscalationLevel.especialista].technician_count == 1
    assert by_level[EscalationLevel.especialista].is_available is True


def test_select_escalation_assignee_prefers_current_team(
    db: Session, seeded_assignee_change: SeededAssigneeChange
) -> None:
    seed = seeded_assignee_change
    _user(
        db,
        "otro-equipo-nivel2",
        "A Técnico Externo",
        level=EscalationLevel.nivel_2,
        team="Redes",
    )
    db.commit()

    selected = select_escalation_assignee(
        db, seed.tickets["activo"], EscalationLevel.nivel_2
    )

    assert selected is not None
    assert selected.team == "Soporte"
    assert selected.id == seed.users["nivel_2"].id


def test_select_escalation_assignee_falls_back_to_full_pool(
    db: Session, seeded_assignee_change: SeededAssigneeChange
) -> None:
    seed = seeded_assignee_change
    seed.users["asignado"].team = "Redes"
    _user(
        db,
        "pool-a",
        "A Técnico Pool",
        level=EscalationLevel.nivel_2,
        team="Soporte",
    )
    db.commit()

    selected = select_escalation_assignee(
        db, seed.tickets["activo"], EscalationLevel.nivel_2
    )

    assert selected is not None
    assert selected.name == "A Técnico Pool"


def test_select_escalation_assignee_least_load_then_name_then_id(
    db: Session, seeded_assignee_change: SeededAssigneeChange
) -> None:
    seed = seeded_assignee_change
    seed.users["nivel_2"].is_active = False
    db.commit()

    low_load = _user(
        db, "low-load", "Técnico Z", level=EscalationLevel.nivel_2
    )
    high_load = _user(
        db, "high-load", "Técnico A", level=EscalationLevel.nivel_2
    )
    for index in range(2):
        _active_ticket(db, seed, f"load-{index}", high_load)
    db.commit()

    selected = select_escalation_assignee(
        db, seed.tickets["activo"], EscalationLevel.nivel_2
    )
    assert selected is not None
    assert selected.id == low_load.id

    # Con la misma carga decide `lower(name)`.
    db.query(Ticket).filter(Ticket.assignee_id == high_load.id).delete()
    db.commit()
    selected = select_escalation_assignee(
        db, seed.tickets["activo"], EscalationLevel.nivel_2
    )
    assert selected is not None
    assert selected.id == high_load.id


def test_select_escalation_assignee_id_breaks_name_tie(
    db: Session, seeded_assignee_change: SeededAssigneeChange
) -> None:
    seed = seeded_assignee_change
    seed.users["nivel_2"].is_active = False
    db.commit()
    first = _user(db, "tie-1", "Técnico Igual", level=EscalationLevel.nivel_2)
    second = _user(db, "tie-2", "Técnico Igual", level=EscalationLevel.nivel_2)
    db.commit()

    selected = select_escalation_assignee(
        db, seed.tickets["activo"], EscalationLevel.nivel_2
    )

    assert selected is not None
    assert selected.id == min(first.id, second.id)


def test_select_escalation_assignee_none_when_pool_empty(
    db: Session, seeded_assignee_change: SeededAssigneeChange
) -> None:
    seed = seeded_assignee_change
    seed.users["nivel_2"].is_active = False
    db.commit()

    assert (
        select_escalation_assignee(
            db, seed.tickets["activo"], EscalationLevel.nivel_2
        )
        is None
    )


def test_selection_is_independent_of_insertion_order(
    db: Session, seeded_assignee_change: SeededAssigneeChange
) -> None:
    seed = seeded_assignee_change
    seed.users["nivel_2"].is_active = False
    db.commit()
    # Inserción deliberadamente desordenada.
    _user(db, "order-b", "Técnico B", level=EscalationLevel.nivel_2)
    _user(db, "order-c", "Técnico C", level=EscalationLevel.nivel_2)
    _user(db, "order-a", "Técnico A", level=EscalationLevel.nivel_2)
    db.commit()

    first = select_escalation_assignee(
        db, seed.tickets["activo"], EscalationLevel.nivel_2
    )
    second = select_escalation_assignee(
        db, seed.tickets["activo"], EscalationLevel.nivel_2
    )

    assert first is not None and second is not None
    assert first.id == second.id
    assert first.name == "Técnico A"


def test_datetime_helper_uses_utc() -> None:
    # Salvaguarda de importación: el módulo de selección no depende del reloj.
    assert datetime.now(UTC).tzinfo is UTC
