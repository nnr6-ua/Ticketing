"""Datos de control y utilidades compartidas por las pruebas de HU-07."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models import (
    Category,
    Priority,
    Ticket,
    TicketStatus,
    TicketTimelineEntry,
    TimelineEventType,
    User,
    UserRole,
)
from tests.conftest import make_token

API = "/api/v1/sla-dashboard"
OPTIONS_API = f"{API}/options"
UTC = timezone.utc


@dataclass
class SeededDashboard:
    now: datetime
    users: dict[str, User]
    priorities: dict[int, Priority]
    categories: dict[str, Category]
    tickets: dict[str, Ticket]

    def headers_for(self, key: str, **kwargs) -> dict[str, str]:
        return {"Authorization": f"Bearer {make_token(self.users[key], **kwargs)}"}

    @property
    def supervisor_headers(self) -> dict[str, str]:
        return self.headers_for("supervisor")


def _user(
    db: Session,
    key: str,
    name: str,
    role: UserRole,
    *,
    team: str | None = None,
    is_active: bool = True,
) -> User:
    user = User(
        id=uuid.uuid5(uuid.NAMESPACE_DNS, f"hu07-user-{key}"),
        name=name,
        email=f"hu07.{key}@example.com",
        role=role,
        team=team,
        is_active=is_active,
    )
    db.add(user)
    return user


def seed_dashboard(db: Session) -> SeededDashboard:
    """Población determinista con todos los casos límite de HU-07."""

    now = datetime.now(UTC).replace(microsecond=0)

    users = {
        "supervisor": _user(db, "supervisor", "Supervisora", UserRole.supervisor),
        "admin": _user(db, "admin", "Administrador", UserRole.admin),
        "usuario": _user(db, "usuario", "Usuario Final", UserRole.usuario),
        "tecnico_a": _user(
            db, "tecnico-a", "Técnico A", UserRole.tecnico, team="Soporte"
        ),
        "tecnico_b": _user(
            db, "tecnico-b", "Técnico B", UserRole.tecnico, team="Redes"
        ),
        "tecnico_c": _user(
            db,
            "tecnico-c",
            "Técnico C",
            UserRole.tecnico,
            team="Soporte",
            is_active=False,
        ),
    }

    priority_specs = {
        1: ("Crítica", True),
        2: ("Alta", True),
        3: ("Media", True),
        4: ("Baja", False),
    }
    priorities: dict[int, Priority] = {}
    for level, (name, is_active) in priority_specs.items():
        priority = Priority(
            id=uuid.uuid5(uuid.NAMESPACE_DNS, f"hu07-priority-{level}"),
            name=name,
            level=level,
            color="#dc2626",
            base_hours="4.00",
            is_active=is_active,
        )
        db.add(priority)
        priorities[level] = priority

    category_specs = {
        "red": ("Red", True),
        "hardware": ("Hardware", True),
        "software": ("Software", False),
    }
    categories: dict[str, Category] = {}
    for key, (name, is_active) in category_specs.items():
        category = Category(
            id=uuid.uuid5(uuid.NAMESPACE_DNS, f"hu07-category-{key}"),
            name=name,
            is_active=is_active,
        )
        db.add(category)
        categories[key] = category

    tickets: dict[str, Ticket] = {}

    def add_ticket(
        key: str,
        number: str,
        status: TicketStatus,
        priority_level: int,
        *,
        category_key: str | None,
        assignee: User | None,
        created_delta: timedelta,
        deadline_delta: timedelta | None,
        finalized_delta: timedelta | None = None,
    ) -> Ticket:
        ticket = Ticket(
            id=uuid.uuid5(uuid.NAMESPACE_DNS, f"hu07-ticket-{key}"),
            number=number,
            title=f"Ticket de control {number}",
            description="Ticket de control para el dashboard de SLA.",
            status=status,
            priority_id=priorities[priority_level].id,
            category_id=categories[category_key].id if category_key else None,
            creator_id=users["usuario"].id,
            assignee_id=assignee.id if assignee else None,
            created_at=now + created_delta,
            sla_deadline=now + deadline_delta if deadline_delta is not None else None,
            finalized_at=now + finalized_delta if finalized_delta else None,
            closed_at=now + finalized_delta if finalized_delta else None,
            updated_at=now,
            sla_version="v1",
        )
        db.add(ticket)
        tickets[key] = ticket
        return ticket

    def resolve(ticket: Ticket, author: User, delta: timedelta) -> None:
        db.add(
            TicketTimelineEntry(
                id=uuid.uuid5(
                    uuid.NAMESPACE_DNS, f"hu07-timeline-{ticket.number}"
                ),
                ticket_id=ticket.id,
                event_type=TimelineEventType.status_change,
                from_status=TicketStatus.en_progreso,
                to_status=TicketStatus.resuelto,
                body=None,
                is_internal=False,
                author_id=author.id,
                created_at=now + delta,
                event_order=0,
                request_id=uuid.uuid5(
                    uuid.NAMESPACE_DNS, f"hu07-request-{ticket.number}"
                ),
            )
        )

    # 1. Vencido activo: se atribuye al responsable vigente (Técnico A).
    add_ticket(
        "critica_vencida_activa",
        "TK-000701",
        TicketStatus.en_progreso,
        1,
        category_key="red",
        assignee=users["tecnico_a"],
        created_delta=timedelta(days=-2),
        deadline_delta=timedelta(days=-1),
    )

    # 2. Atendido exactamente en el límite: cuenta dentro de plazo.
    limite = add_ticket(
        "critica_limite",
        "TK-000702",
        TicketStatus.resuelto,
        1,
        category_key="red",
        assignee=users["tecnico_b"],
        created_delta=timedelta(days=-4),
        deadline_delta=timedelta(days=-3),
        finalized_delta=timedelta(days=-3),
    )
    resolve(limite, users["tecnico_a"], timedelta(days=-3))

    # 3. Finalizado fuera de plazo y reasignado: se atribuye a quien finalizó.
    tardia = add_ticket(
        "alta_tardia",
        "TK-000703",
        TicketStatus.cerrado,
        2,
        category_key="hardware",
        assignee=users["tecnico_a"],
        created_delta=timedelta(days=-5),
        deadline_delta=timedelta(days=-5, hours=8),
        finalized_delta=timedelta(days=-4, hours=-12),
    )
    resolve(tardia, users["tecnico_b"], timedelta(days=-4, hours=-12))

    # 4. Sin SLA y sin categoría: fuera de % y media, nunca vencido.
    add_ticket(
        "alta_sin_sla",
        "TK-000704",
        TicketStatus.abierto,
        2,
        category_key=None,
        assignee=None,
        created_delta=timedelta(days=-1),
        deadline_delta=None,
    )

    # 5. Categoría y prioridad inactivas: etiquetas históricas.
    add_ticket(
        "media_activa",
        "TK-000705",
        TicketStatus.abierto,
        3,
        category_key="software",
        assignee=users["tecnico_a"],
        created_delta=timedelta(days=-6),
        deadline_delta=timedelta(days=1),
    )

    # 6. Reabierto: conserva la primera finalización y su autor (Técnico C).
    reabierto = add_ticket(
        "baja_reabierta",
        "TK-000706",
        TicketStatus.abierto,
        4,
        category_key="red",
        assignee=users["tecnico_a"],
        created_delta=timedelta(days=-8),
        deadline_delta=timedelta(days=-7, hours=-12),
        finalized_delta=None,
    )
    resolve(reabierto, users["tecnico_c"], timedelta(days=-7))

    # 7. Vencido sin responsable: fila «Sin asignar».
    add_ticket(
        "media_vencida_sin_asignar",
        "TK-000707",
        TicketStatus.pendiente_usuario,
        3,
        category_key=None,
        assignee=None,
        created_delta=timedelta(days=-3),
        deadline_delta=timedelta(days=-1),
    )

    # 8. Finalizado sin SLA: cuenta en no_sla_count, no en la media.
    add_ticket(
        "baja_sin_sla",
        "TK-000708",
        TicketStatus.resuelto,
        4,
        category_key="hardware",
        assignee=users["tecnico_a"],
        created_delta=timedelta(days=-9),
        deadline_delta=None,
        finalized_delta=timedelta(days=-8),
    )

    db.commit()
    return SeededDashboard(
        now=now,
        users=users,
        priorities=priorities,
        categories=categories,
        tickets=tickets,
    )


def get_dashboard(client, headers: dict[str, str], **params) -> dict:
    response = client.get(API, headers=headers, params=params or None)
    assert response.status_code == 200, response.text
    return response.json()
