"""Configuración de la aplicación por variables de entorno.

No se incluyen secretos ni valores reales: todos los parámetros sensibles
(`DATABASE_URL`, `JWT_SECRET`, emisor y audiencia) se leen del entorno.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Parámetros de configuración del backend."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: str = "development"
    database_url: str = (
        "postgresql+psycopg://ticketing:ticketing@localhost:5432/ticketing"
    )

    # Autenticación JWT (proveedor existente del proyecto).
    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    auth_issuer: str | None = None
    auth_audience: str | None = None

    # Stub temporal de autenticación para desarrollo local. Nunca debe
    # habilitarse en un entorno compartido o de producción.
    auth_dev_stub_enabled: bool = False

    # Orígenes permitidos para el frontend en desarrollo (separados por coma).
    frontend_origins: str = "http://localhost:5173"

    # Directorio raíz donde se guardan los adjuntos de los tickets.
    attachments_dir: Path = Path("./attachments")


@lru_cache
def get_settings() -> Settings:
    """Devuelve la configuración cacheada de la aplicación."""

    return Settings()
