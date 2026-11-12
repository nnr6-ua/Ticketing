# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# Frontend build: compila la SPA de Vue con Vite.
# ---------------------------------------------------------------------------
FROM node:20-alpine AS frontend-build

WORKDIR /app

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./

# Vacío por defecto: el navegador llama a /api en el mismo origen y Nginx
# resuelve el proxy hacia el servicio `backend`.
ARG VITE_API_BASE_URL=""
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}

RUN npm run build

# ---------------------------------------------------------------------------
# Frontend runtime: Nginx sirve la SPA y proxifica /api/ al backend.
# ---------------------------------------------------------------------------
FROM nginx:1.27-alpine AS frontend

COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
# Normaliza posibles finales de línea CRLF (checkout en Windows).
RUN sed -i 's/\r$//' /etc/nginx/conf.d/default.conf

COPY --from=frontend-build /app/dist /usr/share/nginx/html

EXPOSE 80

# ---------------------------------------------------------------------------
# Backend builder: instala las dependencias en un virtualenv aislado.
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS backend-builder

ENV PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"

COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install --upgrade pip && pip install -r /tmp/requirements.txt

# ---------------------------------------------------------------------------
# Backend runtime: ejecuta como usuario sin privilegios y aplica migraciones.
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS backend

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:${PATH}"

RUN groupadd --system app \
    && useradd --system --gid app --home-dir /app --shell /sbin/nologin app

WORKDIR /app

COPY --from=backend-builder /opt/venv /opt/venv
COPY backend/ /app

# Normaliza posibles finales de línea CRLF (checkout en Windows).
RUN sed -i 's/\r$//' /app/docker/entrypoint.sh \
    && chmod +x /app/docker/entrypoint.sh \
    && chown -R app:app /app

USER app

EXPOSE 8000

ENTRYPOINT ["/app/docker/entrypoint.sh"]
