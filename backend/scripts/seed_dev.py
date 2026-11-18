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
from decimal import Decimal
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import (
    Category,
    ConfigAction,
    ConfigEntityType,
    ConfigurationAuditEntry,
    ConfigurationVersion,
    EscalationLevel,
    Notification,
    Priority,
    SlaRule,
    Ticket,
    TicketStatus,
    TicketTimelineEntry,
    User,
    UserRole,
)
from app.models.enums import NotificationType, TimelineEventType

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
    escalation_level: EscalationLevel = EscalationLevel.nivel_1,
) -> User:
    user = session.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(id=sid(key), email=email)
        session.add(user)
    user.name = name
    user.role = role
    user.team = team
    user.escalation_level = escalation_level
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
    keywords: list[str] | None = None,
    is_default: bool = False,
    is_system: bool = False,
    sort_order: int | None = None,
) -> Priority:
    priority = session.scalar(select(Priority).where(Priority.name == name))
    if priority is None:
        priority = Priority(
            id=sid(f"priority-{name.casefold().replace(' ', '-')}"),
            level=level,
            name=name,
        )
        session.add(priority)
    priority.name = name
    priority.level = level
    priority.color = color
    priority.base_hours = base_hours  # type: ignore[assignment]
    priority.is_active = is_active
    priority.keywords = keywords or []
    priority.is_default = is_default
    priority.is_system = is_system
    priority.sort_order = sort_order if sort_order is not None else level * 10
    return priority


def upsert_category(
    session: Session,
    *,
    key: str,
    name: str,
    description: str,
    keywords: list[str] | None = None,
    is_default: bool = False,
    is_system: bool = False,
) -> Category:
    category = session.scalar(select(Category).where(Category.name == name))
    if category is None:
        category = Category(id=sid(f"category-{key}"), name=name)
        session.add(category)
    category.description = description
    category.is_active = True
    category.keywords = keywords or []
    category.is_default = is_default
    category.is_system = is_system
    category.sort_order = {
        "red": 10,
        "hardware": 20,
        "software": 30,
        "otros": 100,
        "sin_clasificar": 999,
    }.get(key, 50)
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


def upsert_status_timeline_entry(
    session: Session,
    *,
    ticket: Ticket,
    author: User,
    from_status: TicketStatus,
    to_status: TicketStatus,
    created_at: datetime,
) -> TicketTimelineEntry:
    key = f"timeline-status-{ticket.number}"
    entry = session.get(TicketTimelineEntry, sid(key))
    if entry is None:
        entry = TicketTimelineEntry(
            id=sid(key), request_id=sid(f"request-{key}")
        )
        session.add(entry)
    entry.ticket_id = ticket.id
    entry.event_type = TimelineEventType.status_change
    entry.from_status = from_status
    entry.to_status = to_status
    entry.body = None
    entry.is_internal = False
    entry.author_id = author.id
    entry.created_at = created_at
    entry.event_order = 0
    session.flush()
    return entry


def upsert_notification(
    session: Session,
    *,
    ticket: Ticket,
    recipient: User,
    entry: TicketTimelineEntry,
    previous_assignee_name: str,
    created_at: datetime,
) -> Notification:
    key = f"notification-{ticket.number}"
    notification = session.get(Notification, sid(key))
    if notification is None:
        notification = Notification(id=sid(key))
        session.add(notification)
    notification.recipient_id = recipient.id
    notification.ticket_id = ticket.id
    notification.timeline_entry_id = entry.id
    notification.type = NotificationType.ticket_reassigned
    notification.ticket_number = ticket.number
    notification.ticket_title = ticket.title
    notification.previous_assignee_name = previous_assignee_name
    notification.is_read = False
    notification.created_at = created_at
    notification.read_at = None
    return notification


def seed_configuration(
    session: Session,
    actor: User,
    categories: list[Category],
    priorities: list[Priority],
    now: datetime,
) -> None:
    if session.scalar(select(ConfigurationVersion).limit(1)) is not None:
        return

    base = ConfigurationVersion(
        id=sid("configuration-version-1"),
        version=1,
        created_at=now,
        created_by_id=actor.id,
        note="Configuración base de demostración (HU-08).",
    )
    session.add(base)

    factors = {
        "Red": Decimal("1.50"),
        "Hardware": Decimal("1.00"),
        "Software": Decimal("1.25"),
        "Otros": Decimal("1.00"),
    }
    rules: dict[tuple[str, str], SlaRule] = {}
    for category in categories:
        for priority in priorities:
            hours = (
                Decimal(str(priority.base_hours))
                * factors.get(category.name, Decimal("1.00"))
            ).quantize(Decimal("0.01"))
            rule = SlaRule(
                id=sid(f"sla-rule-v1-{category.name}-{priority.name}"),
                category_id=category.id,
                priority_id=priority.id,
                hours=hours,
                configuration_version_id=base.id,
                created_by_id=actor.id,
                created_at=now,
                valid_from_version=1,
            )
            session.add(rule)
            rules[(category.name, priority.name)] = rule
            session.add(
                ConfigurationAuditEntry(
                    id=sid(f"audit-v1-{category.name}-{priority.name}"),
                    configuration_version_id=base.id,
                    entity_type=ConfigEntityType.sla_rule,
                    entity_id=rule.id,
                    action=ConfigAction.rule_upsert,
                    actor_id=actor.id,
                    occurred_at=now,
                    summary=(
                        f"Regla SLA inicial: {category.name} / "
                        f"{priority.name} ({hours:.2f} h)."
                    ),
                    new_values={
                        "category": category.name,
                        "priority": priority.name,
                        "hours": f"{hours:.2f}",
                    },
                )
            )

    changed_at = now + timedelta(minutes=1)
    updated = ConfigurationVersion(
        id=sid("configuration-version-2"),
        version=2,
        created_at=changed_at,
        created_by_id=actor.id,
        note="Ajuste de demostración: plazo de Red / Crítica.",
    )
    session.add(updated)

    previous_rule = rules[("Red", "Crítica")]
    previous_rule.valid_to_version = 2
    new_hours = previous_rule.hours + Decimal("2.00")
    new_rule = SlaRule(
        id=sid("sla-rule-v2-red-critica"),
        category_id=previous_rule.category_id,
        priority_id=previous_rule.priority_id,
        hours=new_hours,
        configuration_version_id=updated.id,
        created_by_id=actor.id,
        created_at=changed_at,
        valid_from_version=2,
        supersedes_id=previous_rule.id,
    )
    session.add(new_rule)
    session.add(
        ConfigurationAuditEntry(
            id=sid("audit-v2-red-critica"),
            configuration_version_id=updated.id,
            entity_type=ConfigEntityType.sla_rule,
            entity_id=new_rule.id,
            action=ConfigAction.rule_upsert,
            actor_id=actor.id,
            occurred_at=changed_at,
            summary=(
                "Ajuste de plazo SLA: Red / Crítica de "
                f"{previous_rule.hours:.2f} h a {new_hours:.2f} h."
            ),
            previous_values={"hours": f"{previous_rule.hours:.2f}"},
            new_values={"hours": f"{new_hours:.2f}"},
        )
    )


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
            escalation_level=EscalationLevel.nivel_2,
        )
        tecnico_d = upsert_user(
            session,
            key="user-tecnico-d",
            name="Técnico D",
            email="tecnico.d@example.com",
            role=UserRole.tecnico,
            team="Soporte",
            escalation_level=EscalationLevel.especialista,
        )
        tecnico_e = upsert_user(
            session,
            key="user-tecnico-e",
            name="Técnico E",
            email="tecnico.e@example.com",
            role=UserRole.tecnico,
            team="Soporte",
        )
        upsert_user(
            session,
            key="user-tecnico-f",
            name="Técnico F",
            email="tecnico.f@example.com",
            role=UserRole.tecnico,
            team="Infraestructura",
        )
        upsert_user(
            session,
            key="user-supervisor",
            name="Supervisor",
            email="supervisor@example.com",
            role=UserRole.supervisor,
            team="Soporte",
        )
        admin = upsert_user(
            session,
            key="user-admin",
            name="Administración",
            email="admin@example.com",
            role=UserRole.admin,
        )
        solicitante = upsert_user(
            session,
            key="user-solicitante",
            name="Solicitante",
            email="usuario@example.com",
            role=UserRole.usuario,
        )

        critica = upsert_priority(
            session,
            level=1,
            name="Crítica",
            color="#dc2626",
            base_hours="4",
            keywords=["urgente", "crítico", "caído", "no puedo trabajar", "toda la oficina"],
        )
        alta = upsert_priority(
            session,
            level=2,
            name="Alta",
            color="#ea580c",
            base_hours="8",
            keywords=["importante", "bloqueado", "error grave", "afecta a varios"],
        )
        media = upsert_priority(
            session,
            level=3,
            name="Media",
            color="#ca8a04",
            base_hours="24",
            is_default=True,
        )
        baja = upsert_priority(
            session,
            level=4,
            name="Baja",
            color="#16a34a",
            base_hours="72",
            keywords=["leve", "consulta", "cuando pueda", "no urgente"],
        )
        # Fallback de sistema: solo se usa si no queda ninguna prioridad
        # personalizada activa. El CHECK de nivel admite 1–4, por eso comparte
        # nivel 4 y se ordena al final para no aparecer en los listados.
        upsert_priority(
            session,
            level=4,
            name="Sin clasificar",
            color="#64748b",
            base_hours="72",
            is_system=True,
            sort_order=999,
        )

        red = upsert_category(
            session,
            key="red",
            name="Red",
            description="Conectividad y acceso remoto.",
            keywords=["wifi", "vpn", "internet", "red", "conexión", "proxy", "dns"],
        )
        hardware = upsert_category(
            session,
            key="hardware",
            name="Hardware",
            description="Equipos y periféricos.",
            keywords=["portátil", "ordenador", "monitor", "teclado", "ratón", "batería"],
        )
        software = upsert_category(
            session,
            key="software",
            name="Software",
            description="Aplicaciones corporativas.",
            keywords=["aplicación", "programa", "instalar", "actualizar", "error", "correo"],
        )
        otros = upsert_category(
            session,
            key="otros",
            name="Otros",
            description="Solicitudes que no encajan en otra categoría.",
            is_default=True,
        )
        upsert_category(
            session,
            key="sin_clasificar",
            name="Sin clasificar",
            description="Categoría de sistema para tickets sin catálogo activo.",
            is_system=True,
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
            creator=tecnico_b,
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

        req_401 = upsert_ticket(
            session,
            number="TK-000401",
            title="El correo corporativo no envía mensajes",
            status=TicketStatus.en_progreso,
            priority=alta,
            category=software,
            creator=solicitante,
            assignee=tecnico_a,
            created_at=now - timedelta(hours=2),
            sla_deadline=now + timedelta(hours=6),
            finalized_at=None,
        )
        req_402 = upsert_ticket(
            session,
            number="TK-000402",
            title="Solicitud de monitor adicional",
            status=TicketStatus.pendiente_usuario,
            priority=media,
            category=hardware,
            creator=solicitante,
            assignee=tecnico_b,
            created_at=now - timedelta(hours=5),
            sla_deadline=None,
            finalized_at=None,
        )
        req_403 = upsert_ticket(
            session,
            number="TK-000403",
            title="Acceso al gestor documental",
            status=TicketStatus.resuelto,
            priority=baja,
            category=otros,
            creator=solicitante,
            assignee=tecnico_a,
            created_at=now - timedelta(days=1),
            sla_deadline=now - timedelta(hours=10),
            finalized_at=now - timedelta(hours=12),
        )

        entry_401 = upsert_status_timeline_entry(
            session,
            ticket=req_401,
            author=tecnico_a,
            from_status=TicketStatus.abierto,
            to_status=TicketStatus.en_progreso,
            created_at=now - timedelta(hours=1, minutes=30),
        )
        entry_402 = upsert_status_timeline_entry(
            session,
            ticket=req_402,
            author=tecnico_b,
            from_status=TicketStatus.en_progreso,
            to_status=TicketStatus.pendiente_usuario,
            created_at=now - timedelta(hours=3),
        )
        entry_403 = upsert_status_timeline_entry(
            session,
            ticket=req_403,
            author=tecnico_a,
            from_status=TicketStatus.en_progreso,
            to_status=TicketStatus.resuelto,
            created_at=now - timedelta(hours=12),
        )

        upsert_notification(
            session,
            ticket=req_401,
            recipient=solicitante,
            entry=entry_401,
            previous_assignee_name="Mesa de ayuda",
            created_at=now - timedelta(hours=1, minutes=30),
        )
        upsert_notification(
            session,
            ticket=req_402,
            recipient=solicitante,
            entry=entry_402,
            previous_assignee_name="Técnico B",
            created_at=now - timedelta(hours=3),
        )
        read_notification = upsert_notification(
            session,
            ticket=req_403,
            recipient=solicitante,
            entry=entry_403,
            previous_assignee_name="Técnico A",
            created_at=now - timedelta(hours=12),
        )
        read_notification.is_read = True
        read_notification.read_at = now - timedelta(hours=11)

        # Técnico D no tiene tickets (cola vacía).

        seed_configuration(
            session,
            admin,
            [red, hardware, software, otros],
            [critica, alta, media, baja],
            now,
        )

        session.commit()

    print("Seed completado:")
    print("  Técnico A: 5 activos + 1 resuelto + 1 cerrado")
    print("  Técnico B: 2 activos")
    print("  Técnico C: 1 resuelto (solo finalizados)")
    print("  Técnico D: sin tickets")
    print("  Solicitante: 3 tickets propios + 3 notificaciones (2 sin leer)")
    print("  Supervisor: rol no autorizado (403)")
    print("  Configuración: versión 2 con 16 reglas SLA vigentes e historial")


if __name__ == "__main__":
    main()
