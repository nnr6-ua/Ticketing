# Mesa de ayuda

Mesa de ayuda interna con autenticación JWT. Reúne dos funcionalidades:

- **Creación de tickets** (HU-01): título, descripción y adjuntos opcionales, con
  sugerencia automática de categoría/prioridad, detección de duplicados y
  número de referencia `TK-000001`.
- **Cola de trabajo priorizada y flujo del ticket** (HU-04/HU-05): vista de los
  tickets asignados al técnico ordenados por urgencia y SLA, cambio de estado,
  resolución y comentarios internos con línea temporal.

## Stack

- **Backend**: FastAPI, SQLAlchemy 2.0 síncrono, PostgreSQL 16, Alembic,
  Pydantic v2, PyJWT, Uvicorn.
- **Frontend**: Vue 3 + TypeScript, Vite, Pinia, Vue Router, Tailwind CSS.
- **Pruebas**: pytest + httpx; Vitest + Vue Test Utils + jsdom.

## Arranque con Docker

```bash
cp .env.example .env
docker compose up --build
```

- Frontend: `http://localhost:8080`
- Backend / OpenAPI: `http://localhost:8000/docs`

El backend aplica las migraciones al arrancar. Para cargar datos de ejemplo:

```bash
docker compose exec backend python scripts/seed_dev.py
```

En desarrollo, el stub de autenticación permite entrar desde `/login` con los
usuarios del seed (por ejemplo `tecnico.a@example.com`).

## Arranque local

### Base de datos

```bash
docker compose up -d db
```

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
python scripts/seed_dev.py
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

La SPA queda en `http://localhost:5173` y Vite redirige `/api` al backend.

## Variables de entorno

Configuración principal (ver `.env.example`):

| Variable | Ejemplo | Uso |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg://ticketing:ticketing@db:5432/ticketing` | Conexión a PostgreSQL |
| `JWT_SECRET` | `dev-only-secret` | Firma/validación de JWT |
| `AUTH_DEV_STUB_ENABLED` | `true` | Habilita el login de desarrollo |
| `FRONTEND_ORIGINS` | `http://localhost:8080` | Orígenes CORS |
| `ATTACHMENTS_DIR` | `./attachments` | Carpeta de adjuntos |
| `VITE_API_BASE_URL` | *(vacío)* | URL del API; vacío = mismo origen |

## Pruebas

```bash
cd backend && python -m pytest
cd frontend && npm test
```

Las pruebas del backend usan SQLite por defecto; exporta `TEST_DATABASE_URL`
para ejecutarlas contra un PostgreSQL 16 desechable.
