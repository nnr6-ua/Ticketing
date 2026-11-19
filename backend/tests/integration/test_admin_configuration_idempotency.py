from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    ConfigAction,
    ConfigurationAuditEntry,
    ConfigurationVersion,
)


def _versions(db: Session) -> list[int]:
    db.expire_all()
    return sorted(db.scalars(select(ConfigurationVersion.version)).all())


def _audits(
    db: Session, entity_id: uuid.UUID, action: ConfigAction | None = None
) -> int:
    db.expire_all()
    statement = (
        select(func.count())
        .select_from(ConfigurationAuditEntry)
        .where(ConfigurationAuditEntry.entity_id == entity_id)
    )
    if action is not None:
        statement = statement.where(ConfigurationAuditEntry.action == action)
    return int(db.scalar(statement) or 0)


def _create_category(client: TestClient, headers, name: str) -> dict:
    response = client.post(
        "/api/v1/admin/categories", json={"name": name}, headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()


def _create_priority(client: TestClient, headers, name: str, level: int) -> dict:
    response = client.post(
        "/api/v1/admin/priorities",
        json={"name": name, "level": level, "base_hours": "8.00"},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_repeated_category_deactivation_and_deletion_do_not_duplicate_history(
    client: TestClient, db: Session, admin_headers
) -> None:
    current = _create_category(client, admin_headers, "Principal")
    replacement = _create_category(client, admin_headers, "Secundaria")
    current_id = uuid.UUID(current["id"])

    versions_before = _versions(db)
    audits_before = _audits(db, current_id)
    payload = {
        "expected_revision": current["revision"],
        "is_active": False,
        "replacement_default_id": replacement["id"],
    }
    url = f"/api/v1/admin/categories/{current['id']}/updates"
    first = client.post(url, json=payload, headers=admin_headers)
    assert first.status_code == 200, first.text
    versions_after_deactivate = _versions(db)
    assert len(versions_after_deactivate) == len(versions_before) + 1

    retry = client.post(url, json=payload, headers=admin_headers)
    assert retry.status_code == 409
    assert retry.json()["detail"]["code"] == "stale_configuration"
    assert _versions(db) == versions_after_deactivate
    assert _audits(db, current_id) == audits_before + 1
    assert _audits(db, current_id, ConfigAction.deactivate) == 1

    disposable = _create_category(client, admin_headers, "Temporal")
    disposable_id = uuid.UUID(disposable["id"])
    versions_before_delete = _versions(db)
    audits_before_delete = _audits(db, disposable_id)
    delete_url = f"/api/v1/admin/categories/{disposable['id']}/deletion"
    delete_payload = {"expected_revision": disposable["revision"]}

    deleted = client.post(delete_url, json=delete_payload, headers=admin_headers)
    assert deleted.status_code == 200, deleted.text
    versions_after_delete = _versions(db)
    assert len(versions_after_delete) == len(versions_before_delete) + 1

    retried_delete = client.post(
        delete_url, json=delete_payload, headers=admin_headers
    )
    assert retried_delete.status_code == 404
    assert retried_delete.json()["detail"]["code"] == "not_found"
    assert _versions(db) == versions_after_delete
    assert _audits(db, disposable_id) == audits_before_delete + 1
    assert _audits(db, disposable_id, ConfigAction.delete) == 1


def test_repeated_priority_deactivation_and_deletion_do_not_duplicate_history(
    client: TestClient, db: Session, admin_headers
) -> None:
    current = _create_priority(client, admin_headers, "Crítica", 1)
    replacement = _create_priority(client, admin_headers, "Alta", 2)
    current_id = uuid.UUID(current["id"])

    versions_before = _versions(db)
    audits_before = _audits(db, current_id)
    payload = {
        "expected_revision": current["revision"],
        "is_active": False,
        "replacement_default_id": replacement["id"],
    }
    url = f"/api/v1/admin/priorities/{current['id']}/updates"
    first = client.post(url, json=payload, headers=admin_headers)
    assert first.status_code == 200, first.text
    versions_after_deactivate = _versions(db)
    assert len(versions_after_deactivate) == len(versions_before) + 1

    retry = client.post(url, json=payload, headers=admin_headers)
    assert retry.status_code == 409
    assert retry.json()["detail"]["code"] == "stale_configuration"
    assert _versions(db) == versions_after_deactivate
    assert _audits(db, current_id) == audits_before + 1
    assert _audits(db, current_id, ConfigAction.deactivate) == 1

    disposable = _create_priority(client, admin_headers, "Media", 3)
    disposable_id = uuid.UUID(disposable["id"])
    versions_before_delete = _versions(db)
    audits_before_delete = _audits(db, disposable_id)
    delete_url = f"/api/v1/admin/priorities/{disposable['id']}/deletion"
    delete_payload = {"expected_revision": disposable["revision"]}

    deleted = client.post(delete_url, json=delete_payload, headers=admin_headers)
    assert deleted.status_code == 200, deleted.text
    versions_after_delete = _versions(db)
    assert len(versions_after_delete) == len(versions_before_delete) + 1

    retried_delete = client.post(
        delete_url, json=delete_payload, headers=admin_headers
    )
    assert retried_delete.status_code == 404
    assert retried_delete.json()["detail"]["code"] == "not_found"
    assert _versions(db) == versions_after_delete
    assert _audits(db, disposable_id) == audits_before_delete + 1
    assert _audits(db, disposable_id, ConfigAction.delete) == 1


def test_retrying_batch_and_retirement_do_not_duplicate_history(
    client: TestClient, db: Session, admin_headers
) -> None:
    category = _create_category(client, admin_headers, "Red")
    priority = _create_priority(client, admin_headers, "Alta", 2)
    upsert = {
        "operation": "upsert",
        "category_id": category["id"],
        "priority_id": priority["id"],
        "hours": "5.00",
        "expected_rule_id": None,
    }

    created = client.post(
        "/api/v1/admin/sla-rules/batch",
        json={"changes": [upsert]},
        headers=admin_headers,
    )
    assert created.status_code == 200, created.text
    rule_id = uuid.UUID(created.json()["items"][0]["id"])
    versions_after_upsert = _versions(db)
    assert _audits(db, rule_id, ConfigAction.rule_upsert) == 1

    retried_batch = client.post(
        "/api/v1/admin/sla-rules/batch",
        json={"changes": [upsert]},
        headers=admin_headers,
    )
    assert retried_batch.status_code == 409
    assert retried_batch.json()["detail"]["code"] == "stale_configuration"
    assert _versions(db) == versions_after_upsert
    assert _audits(db, rule_id, ConfigAction.rule_upsert) == 1

    retire_url = f"/api/v1/admin/sla-rules/{rule_id}/retirement"
    retire_payload = {"expected_rule_id": str(rule_id)}
    retired = client.post(retire_url, json=retire_payload, headers=admin_headers)
    assert retired.status_code == 200, retired.text
    versions_after_retire = _versions(db)
    assert _audits(db, rule_id, ConfigAction.rule_retire) == 1

    retried_retirement = client.post(
        retire_url, json=retire_payload, headers=admin_headers
    )
    assert retried_retirement.status_code == 409
    assert retried_retirement.json()["detail"]["code"] == "stale_configuration"
    assert _versions(db) == versions_after_retire
    assert _audits(db, rule_id, ConfigAction.rule_retire) == 1

    retried_retire_batch = client.post(
        "/api/v1/admin/sla-rules/batch",
        json={
            "changes": [
                {
                    "operation": "retire",
                    "rule_id": str(rule_id),
                    "expected_rule_id": str(rule_id),
                }
            ]
        },
        headers=admin_headers,
    )
    assert retried_retire_batch.status_code == 409
    assert retried_retire_batch.json()["detail"]["code"] == "stale_configuration"
    assert _versions(db) == versions_after_retire
    assert _audits(db, rule_id, ConfigAction.rule_retire) == 1
