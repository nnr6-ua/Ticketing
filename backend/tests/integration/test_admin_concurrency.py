from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from threading import Barrier, Event
from time import sleep
from uuid import UUID, uuid5, NAMESPACE_DNS

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.main import app
from app.models import (
    ConfigurationAuditEntry,
    ConfigurationVersion,
    ConfigEntityType,
    Priority,
    SlaRule,
    Ticket,
    User,
    UserRole,
)
from app.services.ticket_creation import create_ticket
from tests.conftest import IS_SQLITE, make_token

pytestmark = pytest.mark.skipif(
    IS_SQLITE, reason="La concurrencia real requiere TEST_DATABASE_URL de PostgreSQL"
)


def _catalog(client: TestClient, admin_headers: dict[str, str]):
    category = client.post(
        "/api/v1/admin/categories",
        json={"name": "Concurrencia", "keywords": ["concurrente", "red"]},
        headers=admin_headers,
    )
    assert category.status_code == 201
    priority = client.post(
        "/api/v1/admin/priorities",
        json={
            "name": "Urgente concurrente",
            "level": 1,
            "base_hours": "8.00",
        },
        headers=admin_headers,
    )
    assert priority.status_code == 201
    return category.json(), priority.json()


def _version_numbers(db: Session) -> list[int]:
    db.expire_all()
    return list(
        db.scalars(
            select(ConfigurationVersion.version).order_by(ConfigurationVersion.version)
        ).all()
    )


def _batch(category_id: str, priority_id: str, hours: str, expected_rule_id=None):
    return {
        "changes": [
            {
                "operation": "upsert",
                "category_id": category_id,
                "priority_id": priority_id,
                "hours": hours,
                "expected_rule_id": expected_rule_id,
            }
        ]
    }


def _concurrent(method: str, url, *, payloads, headers_list, use_data=False):
    barrier = Barrier(len(payloads))
    paths = url if isinstance(url, list) else [url] * len(payloads)
    flags = use_data if isinstance(use_data, list) else [use_data] * len(payloads)

    def request(path, payload, headers, as_data):
        with TestClient(app, raise_server_exceptions=False) as client:
            barrier.wait()
            kwargs = {"data" if as_data else "json": payload}
            return client.request(method, path, headers=headers, **kwargs)

    with ThreadPoolExecutor(max_workers=len(payloads)) as executor:
        return list(executor.map(request, paths, payloads, headers_list, flags))


def _second_admin(db: Session) -> dict[str, str]:
    other = User(
        id=uuid5(NAMESPACE_DNS, "hu08-concurrency-admin-b"),
        name="Administración B",
        email="admin-b@example.com",
        role=UserRole.admin,
        is_active=True,
    )
    db.add(other)
    db.commit()
    return {"Authorization": f"Bearer {make_token(other)}"}


def _ticket_creator(db: Session) -> tuple[User, dict[str, str]]:
    creator = User(
        id=uuid5(NAMESPACE_DNS, "hu08-concurrency-creator"),
        name="Solicitante concurrente",
        email="solicitante.concurrencia@example.com",
        role=UserRole.usuario,
        is_active=True,
    )
    db.add(creator)
    db.commit()
    return creator, {"Authorization": f"Bearer {make_token(creator)}"}


def test_two_admins_updating_same_category_get_stale_response(
    client: TestClient, db: Session, admin_headers
) -> None:
    category, _ = _catalog(client, admin_headers)
    url = f"/api/v1/admin/categories/{category['id']}/updates"

    responses = _concurrent(
        "POST",
        url,
        payloads=[
            {"expected_revision": 1, "name": "Concurrencia A"},
            {"expected_revision": 1, "name": "Concurrencia B"},
        ],
        headers_list=[admin_headers, _second_admin(db)],
    )

    assert sorted(response.status_code for response in responses) == [200, 409]
    assert any(
        response.json()["detail"]["code"] == "stale_configuration"
        for response in responses
        if response.status_code == 409
    )


def test_two_admins_updating_same_rule_create_single_version(
    client: TestClient, db: Session, admin_headers
) -> None:
    category, priority = _catalog(client, admin_headers)
    versions_before = len(_version_numbers(db))
    url = "/api/v1/admin/sla-rules/batch"
    payloads = [
        _batch(category["id"], priority["id"], "2.00"),
        _batch(category["id"], priority["id"], "3.00"),
    ]

    responses = _concurrent(
        "POST",
        url,
        payloads=payloads,
        headers_list=[admin_headers, _second_admin(db)],
    )

    assert sorted(response.status_code for response in responses) == [200, 409]
    db.expire_all()
    versions = db.scalar(select(func.count()).select_from(ConfigurationVersion))
    rules = db.scalar(
        select(func.count()).select_from(SlaRule).where(SlaRule.valid_to_version.is_(None))
    )
    assert versions - versions_before == 1
    assert rules == 1


def test_updating_rule_with_stale_expected_rule_id_is_rejected(
    client: TestClient, db: Session, admin_headers
) -> None:
    category, priority = _catalog(client, admin_headers)
    created = client.post(
        "/api/v1/admin/sla-rules/batch",
        json=_batch(category["id"], priority["id"], "2.00"),
        headers=admin_headers,
    )
    assert created.status_code == 200
    stale_rule_id = created.json()["items"][0]["id"]

    responses = _concurrent(
        "POST",
        "/api/v1/admin/sla-rules/batch",
        payloads=[
            _batch(category["id"], priority["id"], "3.00", stale_rule_id),
            _batch(category["id"], priority["id"], "4.00", stale_rule_id),
        ],
        headers_list=[admin_headers, _second_admin(db)],
    )

    assert sorted(response.status_code for response in responses) == [200, 409]
    stale = next(response for response in responses if response.status_code == 409)
    assert stale.json()["detail"]["code"] == "stale_configuration"
    db.expire_all()
    current = db.scalar(
        select(SlaRule).where(
            SlaRule.category_id == UUID(category["id"]),
            SlaRule.priority_id == UUID(priority["id"]),
            SlaRule.valid_to_version.is_(None),
        )
    )
    assert current is not None
    assert str(current.id) != stale_rule_id


def test_retrying_applied_batch_does_not_duplicate_rules_versions_or_audit(
    client: TestClient, db: Session, admin_headers
) -> None:
    category, priority = _catalog(client, admin_headers)
    versions_before = _version_numbers(db)
    url = "/api/v1/admin/sla-rules/batch"

    first = client.post(
        url,
        json=_batch(category["id"], priority["id"], "2.00"),
        headers=admin_headers,
    )
    assert first.status_code == 200
    rule_id = UUID(first.json()["items"][0]["id"])

    retry = client.post(
        url,
        json=_batch(category["id"], priority["id"], "2.00"),
        headers=admin_headers,
    )
    assert retry.status_code == 409
    assert retry.json()["detail"]["code"] == "stale_configuration"

    db.expire_all()
    rules = db.scalars(
        select(SlaRule).where(
            SlaRule.category_id == UUID(category["id"]),
            SlaRule.priority_id == UUID(priority["id"]),
        )
    ).all()
    versions = _version_numbers(db)
    audits = db.scalars(
        select(ConfigurationAuditEntry).where(
            ConfigurationAuditEntry.entity_type == ConfigEntityType.sla_rule,
            ConfigurationAuditEntry.entity_id == rule_id,
        )
    ).all()
    assert len(rules) == 1
    assert rules[0].id == rule_id
    assert len(versions) == len(versions_before) + 1
    assert versions[-1] == versions_before[-1] + 1
    assert len(audits) == 1


def test_ticket_created_concurrently_with_rule_change_uses_one_coherent_version(
    client: TestClient, db: Session, admin_headers
) -> None:
    category, priority = _catalog(client, admin_headers)
    _, ticket_headers = _ticket_creator(db)

    initial = client.post(
        "/api/v1/admin/sla-rules/batch",
        json=_batch(category["id"], priority["id"], "2.00"),
        headers=admin_headers,
    )
    assert initial.status_code == 200
    initial_rule_id = initial.json()["items"][0]["id"]
    initial_version = _version_numbers(db)[-1]

    ticket_payload = {
        "title": "Incidencia concurrente de red",
        "description": "La conexión de red falla de forma intermitente desde esta mañana.",
        "priority_id": priority["id"],
    }
    responses = _concurrent(
        "POST",
        ["/api/v1/admin/sla-rules/batch", "/api/v1/tickets"],
        payloads=[
            _batch(category["id"], priority["id"], "3.00", initial_rule_id),
            ticket_payload,
        ],
        headers_list=[admin_headers, ticket_headers],
        use_data=[False, True],
    )

    batch_response = next(
        response for response in responses if response.request.url.path.endswith("/sla-rules/batch")
    )
    ticket_response = next(
        response for response in responses if response.request.url.path.endswith("/tickets")
    )
    assert batch_response.status_code == 200
    assert ticket_response.status_code == 201, ticket_response.text

    body = ticket_response.json()
    hours = float(body["sla_hours_applied"])
    version_label = body["sla_version"]
    allowed = {(f"v{initial_version}", 2.0), (f"v{initial_version + 1}", 3.0)}
    assert (version_label, hours) in allowed
    assert body["sla_config_version_id"] is not None

    db.expire_all()
    ticket = db.scalar(select(Ticket).where(Ticket.id == UUID(body["id"])))
    version = db.scalar(
        select(ConfigurationVersion).where(
            ConfigurationVersion.id == UUID(body["sla_config_version_id"])
        )
    )
    assert ticket is not None
    assert version is not None
    assert ticket.sla_deadline == ticket.created_at + timedelta(hours=hours)
    assert version.version == int(version_label[1:])
    assert ticket.sla_config_version_id == version.id


def test_ticket_after_concurrent_priority_change_uses_coherent_snapshot(
    client: TestClient, db: Session, admin_headers, tmp_path
) -> None:
    category, priority = _catalog(client, admin_headers)
    _ticket_creator(db)
    creator = db.scalar(
        select(User).where(User.email == "solicitante.concurrencia@example.com")
    )
    assert creator is not None
    creator_id = creator.id

    writer_locked = Event()
    release_writer = Event()

    def writer():
        session = SessionLocal()
        try:
            current_version = session.execute(
                select(ConfigurationVersion.version)
                .order_by(ConfigurationVersion.version.desc())
                .limit(1)
                .with_for_update(of=ConfigurationVersion)
            ).scalar_one()
            writer_locked.set()
            assert release_writer.wait(timeout=20)
            row = session.get(Priority, UUID(priority["id"]))
            assert row is not None
            row.level = 3
            row.base_hours = Decimal("12.00")
            row.revision += 1
            version = ConfigurationVersion(
                version=current_version + 1,
                created_by_id=None,
                note="Cambio concurrente de prioridad",
            )
            session.add(version)
            session.flush()
            result = version.version, version.id
            session.commit()
            return result
        finally:
            session.close()

    def create():
        session = SessionLocal()
        try:
            user = session.get(User, creator_id)
            assert user is not None
            ticket, duplicate = create_ticket(
                session,
                user,
                title="Incidencia concurrente de red",
                description=(
                    "La conexión de red falla de forma intermitente "
                    "desde esta mañana."
                ),
                priority_id=priority["id"],
                staged=[],
                attachments_dir=tmp_path,
            )
            assert duplicate is False
            return ticket.id
        finally:
            session.close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        writer_future = executor.submit(writer)
        assert writer_locked.wait(timeout=20)
        ticket_future = executor.submit(create)
        sleep(0.5)
        release_writer.set()
        expected_version, expected_version_id = writer_future.result(timeout=30)
        ticket_id = ticket_future.result(timeout=30)

    db.expire_all()
    ticket = db.scalar(select(Ticket).where(Ticket.id == ticket_id))
    version = db.scalar(
        select(ConfigurationVersion).where(
            ConfigurationVersion.id == expected_version_id
        )
    )
    assert ticket is not None
    assert version is not None
    assert version.version == expected_version
    assert ticket.sla_priority_level == 3
    assert Decimal(str(ticket.sla_hours_applied)) == Decimal("12.00")
    assert ticket.sla_version == f"v{expected_version}"
    assert ticket.sla_config_version_id == expected_version_id
    assert ticket.sla_deadline == ticket.created_at + timedelta(hours=12)
