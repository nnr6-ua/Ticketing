"""Pruebas de integración del ranking de técnicos (US2)."""

from __future__ import annotations

import pytest

from tests.integration._hu07 import API, get_dashboard


def test_ranking_order_and_attribution(client, dashboard_seed):
    body = get_dashboard(client, dashboard_seed.supervisor_headers)
    ranking = body["data"]["ranking"]

    names = [entry["technician_name"] for entry in ranking["technicians"]]
    assert names == ["Técnico A", "Técnico C", "Técnico B"]

    delays = [entry["avg_delay_seconds"] for entry in ranking["technicians"]]
    assert delays == sorted(delays, reverse=True)

    counts = [entry["overdue_count"] for entry in ranking["technicians"]]
    assert counts == [1, 1, 1]


def test_unassigned_row_is_separate_and_last(client, dashboard_seed):
    body = get_dashboard(client, dashboard_seed.supervisor_headers)
    ranking = body["data"]["ranking"]

    unassigned = ranking["unassigned"]
    assert unassigned is not None
    assert unassigned["technician_id"] is None
    assert unassigned["technician_name"] == "Sin asignar"
    assert unassigned["overdue_count"] == 1
    assert unassigned["avg_delay_seconds"] == pytest.approx(86400.0, rel=0.01)


def test_inactive_technician_keeps_row_with_flag(client, dashboard_seed):
    body = get_dashboard(client, dashboard_seed.supervisor_headers)
    entry = next(
        row
        for row in body["data"]["ranking"]["technicians"]
        if row["technician_name"] == "Técnico C"
    )

    assert entry["is_active"] is False
    assert entry["team"] == "Soporte"


def test_overdue_total_matches_summary(client, dashboard_seed):
    body = get_dashboard(client, dashboard_seed.supervisor_headers)

    ranking_total = sum(
        entry["overdue_count"] for entry in body["data"]["ranking"]["technicians"]
    )
    if body["data"]["ranking"]["unassigned"] is not None:
        ranking_total += body["data"]["ranking"]["unassigned"]["overdue_count"]

    assert ranking_total == body["data"]["ranking"]["overdue_total"]
    assert ranking_total == body["data"]["summary"]["overdue_count"] == 4


def test_reassigned_overdue_is_attributed_to_who_finalized(db, client, dashboard_seed):
    body = get_dashboard(client, dashboard_seed.supervisor_headers)
    names = {
        entry["technician_name"] for entry in body["data"]["ranking"]["technicians"]
    }
    # Técnico B finalizó el ticket tardío aunque el responsable vigente es A.
    assert "Técnico B" in names


def test_legacy_finalized_without_timeline_falls_back_to_assignee(
    db, client, dashboard_seed
):
    """Un vencido heredado sin línea temporal se atribuye al responsable."""

    import uuid
    from datetime import timedelta

    from app.models import Ticket, TicketStatus

    seed = dashboard_seed
    now = seed.now
    before = get_dashboard(client, seed.supervisor_headers)["data"]["ranking"]

    def overdue_legacy(number: str, assignee) -> Ticket:
        return Ticket(
            id=uuid.uuid5(uuid.NAMESPACE_DNS, f"hu07-legacy-{number}"),
            number=number,
            title=f"Ticket legado {number}",
            description="Ticket heredado sin entradas de línea temporal.",
            status=TicketStatus.cerrado,
            priority_id=seed.priorities[2].id,
            category_id=seed.categories["red"].id,
            creator_id=seed.users["usuario"].id,
            assignee_id=assignee.id if assignee is not None else None,
            created_at=now - timedelta(days=3),
            sla_deadline=now - timedelta(days=2),
            finalized_at=now - timedelta(days=1),
            closed_at=now - timedelta(days=1),
            updated_at=now,
            sla_version="v1",
        )

    db.add(overdue_legacy("TK-000921", seed.users["tecnico_a"]))
    db.add(overdue_legacy("TK-000922", None))
    db.commit()

    after = get_dashboard(client, seed.supervisor_headers)["data"]["ranking"]

    def count(ranking: dict, name: str) -> int:
        return next(
            (
                entry["overdue_count"]
                for entry in ranking["technicians"]
                if entry["technician_name"] == name
            ),
            0,
        )

    assert count(after, "Técnico A") == count(before, "Técnico A") + 1
    before_unassigned = (
        before["unassigned"]["overdue_count"] if before["unassigned"] else 0
    )
    assert after["unassigned"]["overdue_count"] == before_unassigned + 1
    assert after["overdue_total"] == before["overdue_total"] + 2


def test_period_without_overdue_returns_empty_ranking(client, dashboard_seed):
    from datetime import timedelta

    madrid_day = dashboard_seed.now.date()
    params = {
        "desde": (madrid_day - timedelta(days=1)).isoformat(),
        "hasta": madrid_day.isoformat(),
    }
    body = get_dashboard(client, dashboard_seed.supervisor_headers, **params)

    assert body["data"]["ranking"]["technicians"] == []
    assert body["data"]["ranking"]["unassigned"] is None
    assert body["data"]["ranking"]["overdue_total"] == 0
    assert body["data"]["summary"]["overdue_count"] == 0


def test_equal_named_technicians_have_stable_order(db, client, dashboard_seed):
    """Dos técnicos distintos con métricas idénticas mantienen un orden estable."""

    import uuid
    from datetime import timedelta

    from app.models import Ticket, TicketStatus, User, UserRole

    seed = dashboard_seed
    now = seed.now

    # El orden de inserción (zzz, aaa) es el inverso del orden por identificador,
    # de modo que sin desempate final el resultado dependería del orden de filas.
    twins = []
    for suffix in ("zzz", "aaa"):
        user = User(
            id=uuid.uuid5(uuid.NAMESPACE_DNS, f"hu07-twin-{suffix}"),
            name="Técnico Gemelo",
            email=f"hu07.twin.{suffix}@example.com",
            role=UserRole.tecnico,
            team="Soporte",
            is_active=True,
        )
        db.add(user)
        twins.append(user)
    db.flush()

    for index, user in enumerate(twins, start=1):
        db.add(
            Ticket(
                id=uuid.uuid5(
                    uuid.NAMESPACE_DNS, f"hu07-twin-ticket-{index}"
                ),
                number=f"TK-00081{index}",
                title=f"Ticket gemelo {index}",
                description="Ticket de control para el desempate del ranking.",
                status=TicketStatus.en_progreso,
                priority_id=seed.priorities[2].id,
                category_id=seed.categories["red"].id,
                creator_id=seed.users["usuario"].id,
                assignee_id=user.id,
                created_at=now - timedelta(days=2),
                sla_deadline=now - timedelta(days=1),
                finalized_at=None,
                closed_at=None,
                updated_at=now,
                sla_version="v1",
            )
        )
    db.commit()

    expected = sorted(str(user.id) for user in twins)
    orders = []
    for _ in range(2):
        body = get_dashboard(client, seed.supervisor_headers)
        entries = [
            entry
            for entry in body["data"]["ranking"]["technicians"]
            if entry["technician_name"] == "Técnico Gemelo"
        ]
        assert len(entries) == 2
        assert {entry["technician_id"] for entry in entries} == set(expected)
        assert all(entry["overdue_count"] == 1 for entry in entries)
        assert all(entry["team"] == "Soporte" for entry in entries)
        orders.append([entry["technician_id"] for entry in entries])

    assert orders[0] == orders[1] == expected


def test_ranking_has_no_personal_or_ticket_identifiers(client, dashboard_seed):
    response = client.get(API, headers=dashboard_seed.supervisor_headers)
    assert response.status_code == 200

    text = response.text
    assert "@example.com" not in text
    assert "TK-000" not in text
