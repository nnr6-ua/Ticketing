#!/bin/sh
# Arranque del backend: aplica migraciones y lanza Uvicorn.
#
# El contenedor de PostgreSQL puede tardar unos segundos en aceptar conexiones
# aunque su healthcheck ya esté disponible. Por eso las migraciones se
# reintentan con un límite antes de fallar y dejar que Docker reinicie.

set -eu

: "${DATABASE_URL:?La variable DATABASE_URL es obligatoria}"

# El stub de autenticación de desarrollo necesita una clave para firmar los
# tokens. Si no se ha configurado JWT_SECRET, se genera una efímera por arranque
# (los tokens dejan de ser válidos al reiniciar el contenedor).
if [ "${AUTH_DEV_STUB_ENABLED:-false}" = "true" ] && [ -z "${JWT_SECRET:-}" ]; then
    JWT_SECRET="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
    export JWT_SECRET
    echo "[entrypoint] Stub de desarrollo habilitado: JWT_SECRET efímero generado."
fi

MAX_ATTEMPTS="${MIGRATION_MAX_ATTEMPTS:-30}"
SLEEP_SECONDS="${MIGRATION_RETRY_SECONDS:-2}"
attempt=1

echo "[entrypoint] Aplicando migraciones de Alembic..."
until alembic upgrade head; do
    if [ "${attempt}" -ge "${MAX_ATTEMPTS}" ]; then
        echo "[entrypoint] No se pudieron aplicar las migraciones tras ${MAX_ATTEMPTS} intentos." >&2
        exit 1
    fi
    echo "[entrypoint] Base de datos no disponible (intento ${attempt}/${MAX_ATTEMPTS}); reintentando en ${SLEEP_SECONDS}s..." >&2
    attempt=$((attempt + 1))
    sleep "${SLEEP_SECONDS}"
done

echo "[entrypoint] Migraciones aplicadas. Iniciando la API..."

if [ "$#" -gt 0 ]; then
    echo "[entrypoint] Ejecutando comando alternativo: $*"
    exec "$@"
fi

exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port "${PORT:-8000}" \
    --proxy-headers \
    --forwarded-allow-ips="*"
