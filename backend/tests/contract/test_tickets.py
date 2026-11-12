from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Attachment, Priority, Ticket, TicketEvent

HEADERS = {"X-Employee-Id": "1"}
PNG = b"\x89PNG\r\n\x1a\n" + b"contenido"


def create_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "title": "No funciona la VPN",
        "description": "No puedo conectar desde ayer por la tarde.",
    }
    payload.update(overrides)
    return payload


def test_creates_ticket_with_number_status_and_suggestion(
    client: TestClient, db_session: Session
) -> None:
    response = client.post("/api/v1/tickets", data=create_payload(), headers=HEADERS)

    assert response.status_code == 201
    body = response.json()
    assert body["ticket_number"] == "TK-000001"
    assert body["status"] == "Abierto"
    assert body["category"]["name"] == "Red y conectividad"
    assert body["priority"]["name"] == "Media"
    assert body["creator"]["email"] == "demo@empresa.local"
    assert body["duplicate"] is False

    ticket = db_session.scalar(select(Ticket).where(Ticket.ticket_number == "TK-000001"))
    assert ticket is not None
    event = db_session.scalar(
        select(TicketEvent).where(
            TicketEvent.ticket_id == ticket.id,
            TicketEvent.event_type == "created",
        )
    )
    assert event is not None
    assert event.event_metadata == {"ticket_number": "TK-000001", "status": "Abierto"}


def test_duplicate_returns_existing_ticket_with_200(
    client: TestClient, db_session: Session
) -> None:
    first = client.post("/api/v1/tickets", data=create_payload(), headers=HEADERS)
    second = client.post("/api/v1/tickets", data=create_payload(), headers=HEADERS)

    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json()["duplicate"] is True
    assert second.json()["ticket_number"] == first.json()["ticket_number"]
    assert db_session.scalar(select(func.count(Ticket.id))) == 1


def test_uses_selected_priority_instead_of_suggestion(
    client: TestClient, db_session: Session
) -> None:
    alta = db_session.scalar(select(Priority).where(Priority.name == "Alta"))
    assert alta is not None

    response = client.post(
        "/api/v1/tickets",
        data=create_payload(
            title="Solicitud de información",
            description="Necesito información sobre el proceso de vacaciones.",
            priority_id=alta.id,
        ),
        headers=HEADERS,
    )

    assert response.status_code == 201
    assert response.json()["priority"]["name"] == "Alta"


def test_rejects_inactive_or_unknown_priority(client: TestClient) -> None:
    response = client.post(
        "/api/v1/tickets",
        data=create_payload(priority_id=9999),
        headers=HEADERS,
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_priority"


def test_rejects_system_priority(client: TestClient, db_session: Session) -> None:
    system = db_session.scalar(
        select(Priority).where(Priority.name == "Sin clasificar")
    )
    assert system is not None

    response = client.post(
        "/api/v1/tickets",
        data=create_payload(priority_id=system.id),
        headers=HEADERS,
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_priority"


def test_requires_employee_header(client: TestClient) -> None:
    response = client.post("/api/v1/tickets", data=create_payload())

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "auth_required"


def test_rejects_unknown_employee(client: TestClient) -> None:
    response = client.post(
        "/api/v1/tickets",
        data=create_payload(),
        headers={"X-Employee-Id": "9999"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "auth_invalid"


def test_creates_ticket_with_attachment(
    client: TestClient, db_session: Session
) -> None:
    response = client.post(
        "/api/v1/tickets",
        data=create_payload(),
        files={"attachments": ("foto.png", PNG, "image/png")},
        headers=HEADERS,
    )

    assert response.status_code == 201
    body = response.json()
    assert len(body["attachments"]) == 1
    assert body["attachments"][0]["original_filename"] == "foto.png"

    attachment = db_session.scalar(select(Attachment))
    assert attachment is not None
    assert attachment.stored_filename.endswith(".png")
    assert attachment.relative_path.startswith("attachments/TK-000001/")
    stored = settings.attachments_dir / attachment.relative_path
    assert stored.exists()
    assert stored.read_bytes() == PNG


def test_invalid_attachment_does_not_create_ticket(
    client: TestClient, db_session: Session
) -> None:
    response = client.post(
        "/api/v1/tickets",
        data=create_payload(),
        files={"attachments": ("notas.txt", b"hola", "text/plain")},
        headers=HEADERS,
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_attachment"
    assert db_session.scalar(select(func.count(Ticket.id))) == 0


def test_too_many_attachments_does_not_create_ticket(
    client: TestClient, db_session: Session
) -> None:
    files = [("attachments", (f"foto{i}.png", PNG, "image/png")) for i in range(6)]
    response = client.post(
        "/api/v1/tickets",
        data=create_payload(),
        files=files,
        headers=HEADERS,
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "too_many_attachments"
    assert db_session.scalar(select(func.count(Ticket.id))) == 0


def test_duplicate_with_attachment_does_not_duplicate_files(
    client: TestClient, db_session: Session
) -> None:
    first = client.post(
        "/api/v1/tickets",
        data=create_payload(),
        files={"attachments": ("foto.png", PNG, "image/png")},
        headers=HEADERS,
    )
    second = client.post(
        "/api/v1/tickets",
        data=create_payload(),
        files={"attachments": ("foto.png", PNG, "image/png")},
        headers=HEADERS,
    )

    assert first.status_code == 201
    assert second.status_code == 200
    assert db_session.scalar(select(func.count(Attachment.id))) == 1
    temp_dir = settings.attachments_dir / "tmp"
    assert list(temp_dir.glob("*")) == []


def test_validates_title_and_description(client: TestClient) -> None:
    short_title = client.post(
        "/api/v1/tickets",
        data=create_payload(title="abc"),
        headers=HEADERS,
    )
    short_description = client.post(
        "/api/v1/tickets",
        data=create_payload(description="corta"),
        headers=HEADERS,
    )

    assert short_title.status_code == 422
    assert short_title.json()["error"]["code"] == "validation_error"
    assert short_description.status_code == 422


def test_ticket_numbers_increment(client: TestClient) -> None:
    first = client.post("/api/v1/tickets", data=create_payload(), headers=HEADERS)
    second = client.post(
        "/api/v1/tickets",
        data=create_payload(
            title="Solicitud de información",
            description="Necesito información sobre el proceso de vacaciones.",
        ),
        headers=HEADERS,
    )

    assert first.json()["ticket_number"] == "TK-000001"
    assert second.json()["ticket_number"] == "TK-000002"
