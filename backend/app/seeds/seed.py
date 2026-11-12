from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models import Category, Employee, Priority

CATEGORIES = [
    {
        "name": "Red y conectividad",
        "description": "VPN, wifi, internet, proxy y problemas de red.",
        "keywords": ["wifi", "vpn", "internet", "red", "conexión", "proxy", "dns"],
        "sort_order": 10,
    },
    {
        "name": "Hardware",
        "description": "Equipos, periféricos y componentes.",
        "keywords": [
            "portátil",
            "ordenador",
            "monitor",
            "teclado",
            "ratón",
            "batería",
            "pantalla",
        ],
        "sort_order": 20,
    },
    {
        "name": "Software",
        "description": "Aplicaciones, instalaciones y actualizaciones.",
        "keywords": [
            "aplicación",
            "programa",
            "instalar",
            "actualizar",
            "error",
            "crash",
            "lentitud",
        ],
        "sort_order": 30,
    },
    {
        "name": "Accesos y contraseñas",
        "description": "Credenciales, permisos y cuentas de usuario.",
        "keywords": [
            "contraseña",
            "acceso",
            "login",
            "usuario",
            "bloqueado",
            "permisos",
        ],
        "sort_order": 40,
    },
    {
        "name": "Correo",
        "description": "Buzones, envío y recepción de correo.",
        "keywords": ["correo", "email", "outlook", "bandeja", "enviar", "recibir"],
        "sort_order": 50,
    },
    {
        "name": "Impresoras",
        "description": "Impresión, escaneo y consumibles.",
        "keywords": ["impresora", "imprimir", "escáner", "tóner", "papel"],
        "sort_order": 60,
    },
    {
        "name": "Otros",
        "description": "Solicitudes que no encajan en otra categoría.",
        "keywords": [],
        "sort_order": 100,
        "is_default": True,
    },
    {
        "name": "Sin clasificar",
        "description": "Categoría de sistema usada como último recurso.",
        "keywords": [],
        "sort_order": 999,
        "is_system": True,
    },
]

PRIORITIES = [
    {
        "name": "Crítica",
        "level": 1,
        "color": "#dc2626",
        "keywords": ["urgente", "crítico", "caído", "no puedo trabajar", "toda la oficina"],
        "sort_order": 10,
    },
    {
        "name": "Alta",
        "level": 2,
        "color": "#f97316",
        "keywords": ["importante", "bloqueado", "error grave", "afecta a varios"],
        "sort_order": 20,
    },
    {
        "name": "Media",
        "level": 3,
        "color": "#eab308",
        "keywords": [],
        "sort_order": 30,
        "is_default": True,
    },
    {
        "name": "Baja",
        "level": 4,
        "color": "#22c55e",
        "keywords": ["leve", "consulta", "cuando pueda", "no urgente"],
        "sort_order": 40,
    },
    {
        "name": "Sin clasificar",
        "level": 5,
        "color": "#64748b",
        "keywords": [],
        "sort_order": 999,
        "is_system": True,
    },
]


def _upsert(db: Session, model: type[Category] | type[Priority], data: dict) -> None:
    entity = db.scalar(select(model).where(model.name == data["name"]))
    if entity is None:
        entity = model(**data)
        db.add(entity)
        return
    for key, value in data.items():
        setattr(entity, key, value)


def seed(db: Session) -> None:
    db.execute(update(Category).values(is_default=False))
    db.execute(update(Priority).values(is_default=False))

    for data in CATEGORIES:
        _upsert(db, Category, data)
    for data in PRIORITIES:
        _upsert(db, Priority, data)

    employee = db.scalar(select(Employee).where(Employee.email == "demo@empresa.local"))
    if employee is None:
        db.add(
            Employee(
                name="Empleado Demo",
                email="demo@empresa.local",
                is_active=True,
            )
        )

    db.commit()


if __name__ == "__main__":
    from app.db.session import SessionLocal

    with SessionLocal() as session:
        seed(session)
    print("Catálogos iniciales y empleado demo creados.")
