"""Seed determinista para la validación manual de la HU-04.

Uso (con la base migrada):

    python backend/scripts/seed_dev.py

Es idempotente: vuelve a escribir los mismos registros (identificados por
`email`, `level` y `number`) sin duplicarlos. Las fechas se calculan tomando
el instante de ejecución como referencia para que los escenarios de SLA
vencido / próximo a vencer / dentro de plazo sean siempre reproducibles.
"""

from __future__ import annotations

import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import Category, Priority, Ticket, TicketStatus, User, UserRole

NAMESPACE = uuid.UUID("6f1f4c2e-9d5a-4c7b-8a3d-2b1c0d9e8f70")


def sid(key: str) -> uuid.UUID:
    return uuid.uuid5(NAMESPACE, key)


def upsert_user(
    session: Session,
    *,
    key: str,
    name: str,
    email: str,
    role: UserRole,
    team: str | None = None,
) -> User:
    user = session.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(id=sid(key), email=email)
        session.add(user)
    user.name = name
    user.role = role
    user.team = team
    user.is_active = True
    return user


def upsert_priority(
    session: Session,
    *,
    level: int,
    name: str,
    color: str,
    base_hours: str,
    is_active: bool = True,
) -> Priority:
    priority = session.scalar(select(Priority).where(Priority.level == level))
    if priority is None:
        priority = Priority(id=sid(f"priority-{level}"), level=level, name=name)
        session.add(priority)
    priority.name = name
    priority.color = color
    priority.base_hours = base_hours  # type: ignore[assignment]
    priority.is_active = is_active
    return priority


def upsert_category(
    session: Session, *, key: str, name: str, description: str
) -> Category:
    category = session.scalar(select(Category).where(Category.name == name))
    if category is None:
        category = Category(id=sid(f"category-{key}"), name=name)
        session.add(category)
    category.description = description
    category.is_active = True
    return category


def upsert_ticket(
    session: Session,
    *,
    number: str,
    title: str,
    status: TicketStatus,
    priority: Priority,
    category: Category | None,
    creator: User,
    assignee: User,
    created_at: datetime,
    sla_deadline: datetime | None,
    finalized_at: datetime | None,
) -> Ticket:
    ticket = session.scalar(select(Ticket).where(Ticket.number == number))
    if ticket is None:
        ticket = Ticket(id=sid(f"ticket-{number}"), number=number)
        session.add(ticket)
    ticket.title = title
    ticket.description = f"Ticket de demostración {number}."
    ticket.status = status
    ticket.priority_id = priority.id
    ticket.category_id = category.id if category else None
    ticket.creator_id = creator.id
    ticket.assignee_id = assignee.id
    ticket.created_at = created_at
    ticket.sla_deadline = sla_deadline
    ticket.finalized_at = finalized_at
    ticket.closed_at = finalized_at
    ticket.updated_at = finalized_at or created_at
    ticket.sla_version = "v1"
    return ticket


def main() -> None:
    now = datetime.now(timezone.utc).replace(microsecond=0)

    with SessionLocal() as session:
        tecnico_a = upsert_user(
            session,
            key="user-tecnico-a",
            name="Técnico A",
            email="tecnico.a@example.com",
            role=UserRole.tecnico,
            team="Soporte",
        )
        tecnico_b = upsert_user(
            session,
            key="user-tecnico-b",
            name="Técnico B",
            email="tecnico.b@example.com",
            role=UserRole.tecnico,
            team="Soporte",
        )
        tecnico_c = upsert_user(
            session,
            key="user-tecnico-c",
            name="Técnico C",
            email="tecnico.c@example.com",
            role=UserRole.tecnico,
            team="Soporte",
        )
        upsert_user(
            session,
            key="user-tecnico-d",
            name="Técnico D",
            email="tecnico.d@example.com",
            role=UserRole.tecnico,
            team="Soporte",
        )
        upsert_user(
            session,
            key="user-supervisor",
            name="Supervisor",
            email="supervisor@example.com",
            role=UserRole.supervisor,
            team="Soporte",
        )
        upsert_user(
            session,
            key="user-solicitante",
            name="Solicitante",
            email="usuario@example.com",
            role=UserRole.usuario,
        )

        critica = upsert_priority(
            session, level=1, name="Crítica", color="#dc2626", base_hours="4"
        )
        alta = upsert_priority(
            session, level=2, name="Alta", color="#ea580c", base_hours="8"
        )
        media = upsert_priority(
            session, level=3, name="Media", color="#ca8a04", base_hours="24"
        )
        baja = upsert_priority(
            session, level=4, name="Baja", color="#16a34a", base_hours="72"
        )

        red = upsert_category(
            session,
            key="red",
            name="Red",
            description="Conectividad y acceso remoto.",
        )
        hardware = upsert_category(
            session,
            key="hardware",
            name="Hardware",
            description="Equipos y periféricos.",
        )
        software = upsert_category(
            session,
            key="software",
            name="Software",
            description="Aplicaciones corporativas.",
        )

        # Técnico A: 5 activos + 1 resuelto en plazo + 1 cerrado incumplido.
        upsert_ticket(
            session,
            number="TK-000101",
            title="No puedo acceder a la VPN desde casa",
            status=TicketStatus.en_progreso,
            priority=critica,
            category=red,
            creator=tecnico_a,
            assignee=tecnico_a,
            created_at=now - timedelta(hours=6),
            sla_deadline=now - timedelta(hours=2),
            finalized_at=None,
        )
        upsert_ticket(
            session,
            number="TK-000102",
            title="Caída intermitente de la red wifi",
            status=TicketStatus.abierto,
            priority=critica,
            category=red,
            creator=tecnico_a,
            assignee=tecnico_a,
            created_at=now - timedelta(minutes=10),
            sla_deadline=now + timedelta(minutes=20),
            finalized_at=None,
        )
        upsert_ticket(
            session,
            number="TK-000103",
            title="El portátil no arranca tras la actualización",
            status=TicketStatus.en_progreso,
            priority=alta,
            category=hardware,
            creator=tecnico_a,
            assignee=tecnico_a,
            created_at=now - timedelta(hours=3, minutes=50),
            sla_deadline=now + timedelta(minutes=10),
            finalized_at=None,
        )
        upsert_ticket(
            session,
            number="TK-000104",
            title="Solicitud de alta en el gestor documental",
            status=TicketStatus.pendiente_usuario,
            priority=alta,
            category=None,
            creator=tecnico_a,
            assignee=tecnico_a,
            created_at=now - timedelta(hours=1),
            sla_deadline=None,
            finalized_at=None,
        )
        upsert_ticket(
            session,
            number="TK-000105",
            title="Error al generar el informe mensual",
            status=TicketStatus.abierto,
            priority=media,
            category=software,
            creator=tecnico_a,
            assignee=tecnico_a,
            created_at=now - timedelta(hours=4),
            sla_deadline=now + timedelta(hours=20),
            finalized_at=None,
        )
        upsert_ticket(
            session,
            number="TK-000106",
            title="Restablecer contraseña del correo corporativo",
            status=TicketStatus.resuelto,
            priority=media,
            category=software,
            creator=tecnico_a,
            assignee=tecnico_a,
            created_at=now - timedelta(hours=3),
            sla_deadline=now - timedelta(hours=1),
            finalized_at=now - timedelta(hours=2),
        )
        upsert_ticket(
            session,
            number="TK-000107",
            title="Sustitución de teclado dañado",
            status=TicketStatus.cerrado,
            priority=critica,
            category=hardware,
            creator=tecnico_a,
            assignee=tecnico_a,
            created_at=now - timedelta(days=2),
            sla_deadline=now - timedelta(days=1),
            finalized_at=now - timedelta(hours=1),
        )

        # Técnico B: tickets ajenos que nunca deben aparecer en la cola de A.
        upsert_ticket(
            session,
            number="TK-000201",
            title="Incidencia del servidor de impresión",
            status=TicketStatus.en_progreso,
            priority=critica,
            category=red,
            creator=tecnico_b,
            assignee=tecnico_b,
            created_at=now - timedelta(hours=5),
            sla_deadline=now - timedelta(hours=1),
            finalized_at=None,
        )
        upsert_ticket(
            session,
            number="TK-000202",
            title="Instalación de lector de tarjetas",
            status=TicketStatus.abierto,
            priority=media,
            category=hardware,
            creator=tecnico_b,
            assignee=tecnico_b,
            created_at=now - timedelta(hours=2),
            sla_deadline=now + timedelta(hours=10),
            finalized_at=None,
        )

        # Técnico C: solo finalizados (escenario «solo finalizados»).
        upsert_ticket(
            session,
            number="TK-000301",
            title="Migración de buzón completada",
            status=TicketStatus.resuelto,
            priority=baja,
            category=software,
            creator=tecnico_c,
            assignee=tecnico_c,
            created_at=now - timedelta(hours=8),
            sla_deadline=now - timedelta(hours=4),
            finalized_at=now - timedelta(hours=6),
        )

        # Técnico D no tiene tickets (cola vacía).

        session.commit()

    print("Seed completado:")
    print("  Técnico A: 5 activos + 1 resuelto + 1 cerrado")
    print("  Técnico B: 2 activos")
    print("  Técnico C: 1 resuelto (solo finalizados)")
    print("  Técnico D: sin tickets")
    print("  Supervisor: rol no autorizado (403)")


if __name__ == "__main__":
    main()
