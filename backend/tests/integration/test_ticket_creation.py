from __future__ import annotations

import threading
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
from app.services.ticket_creation import create_ticket
from tests.conftest import IS_SQLITE

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
    assert event.created_at == ticket.created_at
    assert event.event_order == 0


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


def test_rejects_whitespace_only_title_after_trimming(
    client: TestClient,
    db: Session,
    catalogs: SimpleNamespace,
    auth,
    attachments_dir,
) -> None:
    response = client.post(
        "/api/v1/tickets",
        data=payload(title="     "),
        headers=auth(catalogs.user),
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "validation_error"
    assert "título" in response.json()["detail"]["message"].lower()
    assert db.scalar(select(func.count(Ticket.id))) == 0


def test_rejects_whitespace_only_description_after_trimming(
    client: TestClient,
    catalogs: SimpleNamespace,
    auth,
    attachments_dir,
) -> None:
    response = client.post(
        "/api/v1/tickets",
        data=payload(description="                    "),
        headers=auth(catalogs.user),
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "validation_error"
    assert "descripción" in response.json()["detail"]["message"].lower()


@pytest.mark.parametrize(
    "field,value",
    [
        ("title", "abc"),
        ("title", "x" * 121),
        ("description", "x" * 19),
        ("description", "x" * 5001),
    ],
)
def test_rejects_lengths_outside_contract(
    client: TestClient,
    catalogs: SimpleNamespace,
    auth,
    attachments_dir,
    field: str,
    value: str,
) -> None:
    response = client.post(
        "/api/v1/tickets",
        data=payload(**{field: value}),
        headers=auth(catalogs.user),
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_request"


def test_preserves_special_characters_and_formatting(
    client: TestClient,
    db: Session,
    catalogs: SimpleNamespace,
    auth,
    attachments_dir,
) -> None:
    title = "  Error <script> & 'código'  "
    description = (
        "Pega el siguiente fragmento:\n"
        "```js\nconst ok = 1 < 2 && 3 > 2;\n```\n"
        "No funciona en la aplicación."
    )

    response = client.post(
        "/api/v1/tickets",
        data=payload(title=title, description=description),
        headers=auth(catalogs.user),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["title"] == title.strip()
    ticket = db.scalar(select(Ticket).where(Ticket.number == body["ticket_number"]))
    assert ticket is not None
    assert ticket.title == title.strip()
    assert ticket.description == description.strip()


def test_suggests_priority_from_keywords(
    client: TestClient,
    catalogs: SimpleNamespace,
    auth,
    attachments_dir,
) -> None:
    response = client.post(
        "/api/v1/tickets",
        data=payload(
            title="El servicio está caído",
            description="Esto es urgente y afecta a toda la oficina.",
        ),
        headers=auth(catalogs.user),
    )

    assert response.status_code == 201
    assert response.json()["priority"]["name"] == "Crítica"


def test_uses_system_catalog_when_custom_catalogs_are_inactive(
    client: TestClient,
    db: Session,
    catalogs: SimpleNamespace,
    auth,
    attachments_dir,
) -> None:
    for category in db.scalars(select(Category)).all():
        category.is_active = False
    for priority in db.scalars(select(Priority)).all():
        priority.is_active = False
    db.add_all(
        [
            Category(
                name="Sin clasificar",
                is_system=True,
                is_active=True,
                sort_order=999,
            ),
            Priority(
                name="Sin clasificar",
                level=4,
                color="#64748b",
                base_hours="72",
                is_system=True,
                is_active=True,
                sort_order=999,
            ),
        ]
    )
    db.commit()

    response = client.post(
        "/api/v1/tickets",
        data=payload(),
        headers=auth(catalogs.user),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["category"]["name"] == "Sin clasificar"
    assert body["priority"]["name"] == "Sin clasificar"


def test_accepts_jpeg_and_gif_attachments(
    client: TestClient,
    db: Session,
    catalogs: SimpleNamespace,
    auth,
    attachments_dir,
) -> None:
    jpeg = b"\xff\xd8\xff" + b"jpeg"
    gif = b"GIF89a" + b"gif"
    response = client.post(
        "/api/v1/tickets",
        data=payload(),
        files=[
            ("attachments", ("foto.jpg", jpeg, "image/jpeg")),
            ("attachments", ("animacion.gif", gif, "image/gif")),
        ],
        headers=auth(catalogs.user),
    )

    assert response.status_code == 201
    attachments = response.json()["attachments"]
    assert [item["original_filename"] for item in attachments] == [
        "foto.jpg",
        "animacion.gif",
    ]
    assert {item["mime_type"] for item in attachments} == {
        "image/jpeg",
        "image/gif",
    }
    assert db.scalar(select(func.count(Attachment.id))) == 2


def test_rejects_oversized_attachment_atomically(
    client: TestClient,
    db: Session,
    catalogs: SimpleNamespace,
    auth,
    attachments_dir,
) -> None:
    oversized = b"\x89PNG\r\n\x1a\n" + b"0" * (5 * 1024 * 1024)
    response = client.post(
        "/api/v1/tickets",
        data=payload(),
        files={"attachments": ("grande.png", oversized, "image/png")},
        headers=auth(catalogs.user),
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "attachment_too_large"
    assert db.scalar(select(func.count(Ticket.id))) == 0
    assert db.scalar(select(func.count(Attachment.id))) == 0
    assert [path for path in attachments_dir.rglob("*") if path.is_file()] == []


def test_rejects_renamed_file_with_invalid_signature(
    client: TestClient,
    db: Session,
    catalogs: SimpleNamespace,
    auth,
    attachments_dir,
) -> None:
    response = client.post(
        "/api/v1/tickets",
        data=payload(),
        files={"attachments": ("falsa.png", b"no soy una imagen", "image/png")},
        headers=auth(catalogs.user),
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_attachment"
    assert db.scalar(select(func.count(Ticket.id))) == 0


def test_rejects_declared_content_type_mismatch(
    client: TestClient,
    db: Session,
    catalogs: SimpleNamespace,
    auth,
    attachments_dir,
) -> None:
    response = client.post(
        "/api/v1/tickets",
        data=payload(),
        files={"attachments": ("foto.png", PNG, "image/gif")},
        headers=auth(catalogs.user),
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_attachment"
    assert db.scalar(select(func.count(Ticket.id))) == 0


def test_atomicity_when_a_later_attachment_is_invalid(
    client: TestClient,
    db: Session,
    catalogs: SimpleNamespace,
    auth,
    attachments_dir,
) -> None:
    response = client.post(
        "/api/v1/tickets",
        data=payload(),
        files=[
            ("attachments", ("valida.png", PNG, "image/png")),
            ("attachments", ("rota.png", b"contenido invalido", "image/png")),
        ],
        headers=auth(catalogs.user),
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_attachment"
    assert db.scalar(select(func.count(Ticket.id))) == 0
    assert db.scalar(select(func.count(Attachment.id))) == 0
    assert [path for path in attachments_dir.rglob("*") if path.is_file()] == []


def test_duplicate_keeps_only_original_attachments(
    client: TestClient,
    db: Session,
    catalogs: SimpleNamespace,
    auth,
    attachments_dir,
) -> None:
    headers = auth(catalogs.user)
    other_png = b"\x89PNG\r\n\x1a\n" + b"otra-imagen"
    first = client.post(
        "/api/v1/tickets",
        data=payload(),
        files={"attachments": ("original.png", PNG, "image/png")},
        headers=headers,
    )
    second = client.post(
        "/api/v1/tickets",
        data=payload(),
        files={"attachments": ("duplicada.png", other_png, "image/png")},
        headers=headers,
    )

    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json()["duplicate"] is True
    assert second.json()["ticket_number"] == first.json()["ticket_number"]
    assert [item["original_filename"] for item in second.json()["attachments"]] == [
        "original.png"
    ]
    assert db.scalar(select(func.count(Ticket.id))) == 1
    assert db.scalar(select(func.count(Attachment.id))) == 1
    files = [path for path in attachments_dir.rglob("*") if path.is_file()]
    assert len(files) == 1
    assert files[0].read_bytes() == PNG


@pytest.mark.postgres
@pytest.mark.skipif(IS_SQLITE, reason="Requiere PostgreSQL para concurrencia real")
def test_concurrent_identical_requests_create_one_ticket(
    db: Session,
    catalogs: SimpleNamespace,
    attachments_dir,
) -> None:
    from app.db.session import SessionLocal

    barrier = threading.Barrier(2)
    results: list[tuple[str, bool]] = []
    errors: list[str] = []
    lock = threading.Lock()

    def worker() -> None:
        session = SessionLocal()
        try:
            user = session.get(User, catalogs.user.id)
            assert user is not None
            barrier.wait(timeout=10)
            ticket, duplicate = create_ticket(
                session,
                user,
                title="No funciona la VPN",
                description="No puedo conectar desde ayer por la tarde.",
                priority_id=None,
                staged=[],
                attachments_dir=attachments_dir,
            )
            with lock:
                results.append((ticket.number, duplicate))
        except Exception as exc:  # noqa: BLE001 - se reporta el fallo real
            with lock:
                errors.append(repr(exc))
        finally:
            session.close()

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
        assert not thread.is_alive(), "la prueba de concurrencia no terminó"

    assert errors == []
    assert len(results) == 2
    assert {number for number, _ in results} == {results[0][0]}
    assert sorted(duplicate for _, duplicate in results) == [False, True]

    db.expire_all()
    assert db.scalar(select(func.count(Ticket.id))) == 1
    assert db.scalar(select(func.count(Attachment.id))) == 0
