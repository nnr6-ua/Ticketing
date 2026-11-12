from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import (
    Attachment,
    Category,
    Priority,
    Ticket,
    TicketTimelineEntry,
    TimelineEventType,
    User,
    UserRole,
)

PNG = b"\x89PNG\r\n\x1a\n" + b"contenido"


@pytest.fixture()
def catalogs(db: Session) -> SimpleNamespace:
    user = User(
        id=uuid.uuid4(),
        name="Solicitante",
        email="solicitante@example.com",
        role=UserRole.usuario,
        is_active=True,
    )
    red = Category(
        name="Red",
        keywords=["vpn", "wifi", "internet", "red"],
        sort_order=10,
        is_active=True,
    )
    otros = Category(
        name="Otros",
        keywords=[],
        sort_order=100,
        is_default=True,
        is_active=True,
    )
    media = Priority(
        name="Media",
        level=3,
        color="#ca8a04",
        is_default=True,
        is_active=True,
    )
    critica = Priority(
        name="Crítica",
        level=1,
        color="#dc2626",
        keywords=["urgente", "caído"],
        is_active=True,
    )
    db.add_all([user, red, otros, media, critica])
    db.commit()
    return SimpleNamespace(
        user=user,
        red=red,
        otros=otros,
        media=media,
        critica=critica,
    )


@pytest.fixture()
def attachments_dir(tmp_path, monkeypatch):
    directory = tmp_path / "attachments"
    monkeypatch.setattr(get_settings(), "attachments_dir", directory)
    return directory


def payload(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "title": "No funciona la VPN",
        "description": "No puedo conectar desde ayer por la tarde.",
    }
    data.update(overrides)
    return data


def test_creates_ticket_with_suggestion_and_creation_event(
    client: TestClient,
    db: Session,
    catalogs: SimpleNamespace,
    auth,
    attachments_dir,
) -> None:
    response = client.post(
        "/api/v1/tickets", data=payload(), headers=auth(catalogs.user)
    )

    assert response.status_code == 201
    body = response.json()
    assert body["ticket_number"].startswith("TK-")
    assert len(body["ticket_number"]) == 9
    assert body["status"] == "Abierto"
    assert body["category"]["name"] == "Red"
    assert body["priority"]["name"] == "Media"
    assert body["creator"]["email"] == "solicitante@example.com"
    assert body["duplicate"] is False

    ticket = db.scalar(select(Ticket).where(Ticket.number == body["ticket_number"]))
    assert ticket is not None
    event = db.scalar(
        select(TicketTimelineEntry).where(
            TicketTimelineEntry.ticket_id == ticket.id,
            TicketTimelineEntry.event_type == TimelineEventType.created,
        )
    )
    assert event is not None
    assert event.author_id == catalogs.user.id


def test_duplicate_returns_existing_ticket_with_200(
    client: TestClient,
    db: Session,
    catalogs: SimpleNamespace,
    auth,
    attachments_dir,
) -> None:
    headers = auth(catalogs.user)
    first = client.post("/api/v1/tickets", data=payload(), headers=headers)
    second = client.post("/api/v1/tickets", data=payload(), headers=headers)

    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json()["duplicate"] is True
    assert second.json()["ticket_number"] == first.json()["ticket_number"]
    assert db.scalar(select(func.count(Ticket.id))) == 1


def test_uses_selected_priority_instead_of_suggestion(
    client: TestClient,
    catalogs: SimpleNamespace,
    auth,
    attachments_dir,
) -> None:
    response = client.post(
        "/api/v1/tickets",
        data=payload(priority_id=str(catalogs.critica.id)),
        headers=auth(catalogs.user),
    )

    assert response.status_code == 201
    assert response.json()["priority"]["name"] == "Crítica"


def test_rejects_unknown_priority(
    client: TestClient,
    catalogs: SimpleNamespace,
    auth,
    attachments_dir,
) -> None:
    response = client.post(
        "/api/v1/tickets",
        data=payload(priority_id=str(uuid.uuid4())),
        headers=auth(catalogs.user),
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_priority"


def test_requires_authentication(
    client: TestClient,
    catalogs: SimpleNamespace,
    attachments_dir,
) -> None:
    response = client.post("/api/v1/tickets", data=payload())

    assert response.status_code == 403 or response.status_code == 401


def test_creates_ticket_with_attachment(
    client: TestClient,
    db: Session,
    catalogs: SimpleNamespace,
    auth,
    attachments_dir,
) -> None:
    response = client.post(
        "/api/v1/tickets",
        data=payload(),
        files={"attachments": ("foto.png", PNG, "image/png")},
        headers=auth(catalogs.user),
    )

    assert response.status_code == 201
    body = response.json()
    assert len(body["attachments"]) == 1
    assert body["attachments"][0]["original_filename"] == "foto.png"

    attachment = db.scalar(select(Attachment))
    assert attachment is not None
    assert attachment.stored_filename.endswith(".png")
    stored = attachments_dir / attachment.relative_path
    assert stored.exists()
    assert stored.read_bytes() == PNG


def test_invalid_attachment_does_not_create_ticket(
    client: TestClient,
    db: Session,
    catalogs: SimpleNamespace,
    auth,
    attachments_dir,
) -> None:
    response = client.post(
        "/api/v1/tickets",
        data=payload(),
        files={"attachments": ("notas.txt", b"hola", "text/plain")},
        headers=auth(catalogs.user),
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_attachment"
    assert db.scalar(select(func.count(Ticket.id))) == 0


def test_too_many_attachments_does_not_create_ticket(
    client: TestClient,
    db: Session,
    catalogs: SimpleNamespace,
    auth,
    attachments_dir,
) -> None:
    files = [("attachments", (f"foto{i}.png", PNG, "image/png")) for i in range(6)]
    response = client.post(
        "/api/v1/tickets",
        data=payload(),
        files=files,
        headers=auth(catalogs.user),
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "too_many_attachments"
    assert db.scalar(select(func.count(Ticket.id))) == 0


def test_ticket_numbers_increment(
    client: TestClient,
    catalogs: SimpleNamespace,
    auth,
    attachments_dir,
) -> None:
    headers = auth(catalogs.user)
    first = client.post("/api/v1/tickets", data=payload(), headers=headers)
    second = client.post(
        "/api/v1/tickets",
        data=payload(
            title="Solicitud de información",
            description="Necesito información sobre el proceso de vacaciones.",
        ),
        headers=headers,
    )

    assert first.status_code == 201
    assert second.status_code == 201
    first_number = int(first.json()["ticket_number"].split("-")[1])
    second_number = int(second.json()["ticket_number"].split("-")[1])
    assert second_number == first_number + 1


def test_suggestions_endpoint(
    client: TestClient,
    catalogs: SimpleNamespace,
    auth,
) -> None:
    response = client.post(
        "/api/v1/suggestions",
        json={"title": "No funciona la VPN", "description": "Sin conexión."},
        headers=auth(catalogs.user),
    )

    assert response.status_code == 200
    assert response.json()["category"]["name"] == "Red"


def test_priorities_endpoint(
    client: TestClient,
    catalogs: SimpleNamespace,
    auth,
) -> None:
    response = client.get("/api/v1/priorities", headers=auth(catalogs.user))

    assert response.status_code == 200
    names = [priority["name"] for priority in response.json()]
    assert names == ["Crítica", "Media"]
