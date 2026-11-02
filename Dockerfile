# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# Aplicación Ticketing · imagen multi-etapa
#
# Etapas:
#   frontend-build  Compila la SPA de Vue/Vite con Node.
#   frontend        Sirve la SPA con Nginx y hace de proxy inverso de /api.
#   backend-builder Instala las dependencias de Python en un virtualenv.
#   backend         Ejecuta FastAPI/Alembic con un usuario sin privilegios.
#
# Docker Compose construye las etapas `backend` y `frontend` por separado.
# ---------------------------------------------------------------------------

# ------------------------------- Frontend ---------------------------------
FROM node:20-alpine AS frontend-build

WORKDIR /app

# Las dependencias se copian antes que el código para aprovechar la caché.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./

# Vacío por defecto: el navegador llama a /api y Nginx lo redirige al backend.
# Se puede sobrescribir al construir si el API vive en otro origen.
ARG VITE_API_BASE_URL=""
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}

RUN npm run build

FROM nginx:1.27-alpine AS frontend

COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=frontend-build /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -qO- http://127.0.0.1/healthz >/dev/null 2>&1 || exit 1

# ------------------------------- Backend ----------------------------------
FROM python:3.12-slim AS backend-builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"

COPY backend/requirements.txt ./
RUN pip install -r requirements.txt

FROM python:3.12-slim AS backend

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:${PATH}"

RUN groupadd --system app \
    && useradd --system --gid app --home-dir /app --no-create-home app

WORKDIR /app

COPY --from=backend-builder /opt/venv /opt/venv
COPY backend/ ./
RUN chmod +x /app/docker/entrypoint.sh \
    && chown -R app:app /app

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/openapi.json')" >/dev/null 2>&1 || exit 1

ENTRYPOINT ["/app/docker/entrypoint.sh"]
