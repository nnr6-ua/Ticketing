"""Router de la API v1."""

from fastapi import APIRouter

from app.api.v1 import dev_auth, work_queue
from app.core.config import get_settings

api_router = APIRouter()
api_router.include_router(work_queue.router)

# El stub de autenticación solo existe cuando se habilita explícitamente.
if get_settings().auth_dev_stub_enabled:
    api_router.include_router(dev_auth.router)
