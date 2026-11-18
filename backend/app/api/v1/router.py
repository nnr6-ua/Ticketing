"""Router de la API v1."""

from fastapi import APIRouter

from app.api.v1 import (
    admin_configuration,
    dev_auth,
    my_tickets,
    notifications,
    sla_dashboard,
    ticket_creation,
    tickets,
    work_queue,
)
from app.core.config import get_settings

api_router = APIRouter()
api_router.include_router(work_queue.router)
api_router.include_router(my_tickets.router)
api_router.include_router(ticket_creation.router)
api_router.include_router(tickets.router)
api_router.include_router(admin_configuration.router)
api_router.include_router(notifications.router)
api_router.include_router(sla_dashboard.router)

# El stub de autenticación solo existe cuando se habilita explícitamente.
if get_settings().auth_dev_stub_enabled:
    api_router.include_router(dev_auth.router)
