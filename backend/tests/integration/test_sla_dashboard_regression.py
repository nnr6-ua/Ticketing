"""No regresión de HU-04/HU-05/HU-06 y solo lectura del dashboard (T072)."""

from __future__ import annotations

from datetime import timezone
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import func, select

from app.models import Ticket, TicketTimelineEntry
from app.services.assignee_change import ensure_assignee_consistency
from tests.conftest import make_token
from tests.integration._hu07 import API, OPTIONS_API, assert_vary_authorization

BACKEND_ROOT = Path(__file__).resolve().parents[2]
EXPECTED_HEAD = "0008_sync_ticket_number_sequence"
WORK_QUEUE_API = "/api/v1/me/work-queue"


def _count(session, model) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0


def _naive_utc(value):
    if value is not None and value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def test_work_queue_contract_is_unchanged(client, seeded):
    headers = {"Authorization": f"Bearer {make_token(seeded.users['a'])}"}

    response = client.get(WORK_QUEUE_API, headers=headers)

    assert response.status_code == 200, response.text
    assert response.headers["Cache-Control"] == "no-store"
    assert_vary_authorization(response)

    body = response.json()
    assert set(body) == {
        "items",
        "pagination",
        "counts",
        "available_filters",
        "applied_filters",
        "meta",
    }
    assert body["meta"]["timezone"] == "Europe/Madrid"
    assert len(body["items"]) > 0


def test_work_queue_forbidden_for_supervisor_is_unchanged(client, seeded):
    headers = {
        "Authorization": f"Bearer {make_token(seeded.users['supervisor'])}"
    }

    response = client.get(WORK_QUEUE_API, headers=headers)

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "forbidden"


def test_dashboard_is_read_only(client, db, dashboard_seed):
    tickets_before = _count(db, Ticket)
    entries_before = _count(db, TicketTimelineEntry)
    updated_before = {
        row.id: _naive_utc(row.updated_at)
        for row in db.scalars(select(Ticket)).all()
    }
    sample = dashboard_seed.tickets["critica_vencida_activa"]
    sample_updated_before = _naive_utc(sample.updated_at)

    assert client.get(API, headers=dashboard_seed.supervisor_headers).status_code == 200
    assert (
        client.get(OPTIONS_API, headers=dashboard_seed.supervisor_headers).status_code
        == 200
    )

    db.expire_all()
    assert _count(db, Ticket) == tickets_before
    assert _count(db, TicketTimelineEntry) == entries_before

    updated_after = {
        row.id: _naive_utc(row.updated_at)
        for row in db.scalars(select(Ticket)).all()
    }
    assert updated_after == updated_before

    refreshed = db.get(Ticket, sample.id)
    assert refreshed is not None
    assert _naive_utc(refreshed.updated_at) == sample_updated_before

    # El dashboard no crea entradas de cambio de responsable ni de estado.
    assert (
        db.scalar(
            select(func.count())
            .select_from(TicketTimelineEntry)
            .where(TicketTimelineEntry.event_type.in_(["assignee_change"]))
        )
        or 0
    ) == 0


def test_assignee_consistency_helper_still_works(db, dashboard_seed):
    ticket = dashboard_seed.tickets["critica_vencida_activa"]
    before = _count(db, TicketTimelineEntry)

    ensure_assignee_consistency(db, ticket)

    db.expire_all()
    assert _count(db, TicketTimelineEntry) == before


def test_dashboard_router_only_exposes_get():
    from app.api.v1 import sla_dashboard as module

    routes = {route.path: route.methods for route in module.router.routes}

    assert set(routes) == {"/sla-dashboard", "/sla-dashboard/options"}
    for methods in routes.values():
        assert methods == {"GET"}


def test_alembic_head_is_unchanged():
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    script = ScriptDirectory.from_config(config)

    assert script.get_current_head() == EXPECTED_HEAD

    versions = sorted(
        path.name
        for path in (BACKEND_ROOT / "alembic" / "versions").glob("*.py")
    )
    assert versions == [
        "0001_base_schema.py",
        "0002_add_finalized_at_and_work_queue_indexes.py",
        "0003_ticket_timeline.py",
        "0004_assignee_changes_notifications.py",
        "0004_ticket_creation.py",
        "0005_ticket_information.py",
        "0006_sla_configuration.py",
        "0007_merge_hu06_hu08.py",
        "0008_sync_ticket_number_sequence.py",
    ]


def test_docker_compose_has_no_new_services():
    compose = (BACKEND_ROOT.parent / "docker-compose.yml").read_text(
        encoding="utf-8"
    )
    service_lines: list[str] = []
    in_services = False
    for line in compose.splitlines():
        if line.rstrip() == "services:":
            in_services = True
            continue
        if in_services and line and not line.startswith(" "):
            break
        if (
            in_services
            and line.startswith("  ")
            and not line.startswith("    ")
            and line.rstrip().endswith(":")
        ):
            service_lines.append(line.strip().rstrip(":"))

    assert service_lines == ["db", "backend", "frontend"]


def test_dashboard_timestamps_do_not_mutate_rows(client, db, dashboard_seed):
    sample = dashboard_seed.tickets["alta_tardia"]
    before_updated = sample.updated_at
    before_finalized = sample.finalized_at

    body = client.get(
        API, headers=dashboard_seed.supervisor_headers
    ).json()

    assert body["meta"]["generated_at"].endswith("Z")
    db.expire_all()
    after = db.get(Ticket, sample.id)
    assert after is not None
    assert _naive_utc(after.updated_at) == _naive_utc(before_updated)
    assert _naive_utc(after.finalized_at) == _naive_utc(before_finalized)
