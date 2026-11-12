# Mesa de ayuda — Creación de tickets

Primera funcionalidad de una mesa de ayuda interna: un empleado autenticado crea un ticket con título, descripción y adjuntos opcionales, recibe un número de referencia `TK-000001` y puede consultar la confirmación.

## Stack

- **Backend**: FastAPI, SQLAlchemy 2.0 síncrono, PostgreSQL 16, Alembic, Pydantic v2, Uvicorn.
- **Frontend**: Vue 3 + TypeScript, Vite, Tailwind CSS, Headless UI, Heroicons.
- **Pruebas**: pytest + httpx + PostgreSQL embebido (`pgserver`); Vitest + Vue Test Utils + jsdom.

## Requisitos

- Python 3.12+
- Node.js 18+ y npm
- Docker y Docker Compose (opcional si usas una base PostgreSQL propia)

## Arranque rápido

### 1. Base de datos

```bash
docker compose up -d db
```

### 2. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
alembic upgrade head
python -m app.seeds.seed
uvicorn app.main:app --reload --port 8000
```

API: `http://localhost:8000` · Documentación: `http://localhost:8000/docs`

### 3. Frontend

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

Aplicación: `http://localhost:5173`

## Variables de entorno

Backend (`backend/.env`):

| Variable | Ejemplo | Uso |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg://ticketing:ticketing@localhost:5432/ticketing` | Conexión a PostgreSQL |
| `ATTACHMENTS_DIR` | `./attachments` | Carpeta local de adjuntos |
| `CORS_ORIGINS` | `http://localhost:5173` | Orígenes permitidos |

Frontend (`frontend/.env.local`):

| Variable | Ejemplo | Uso |
|---|---|---|
| `VITE_API_BASE_URL` | `http://localhost:8000/api/v1` | Base de la API |
| `VITE_DEV_EMPLOYEE_ID` | `1` | Empleado demo para `X-Employee-Id` |

No hay secretos reales en los archivos de ejemplo.

## Pruebas

```bash
# Backend: inicia un PostgreSQL embebido automáticamente
cd backend
pytest

# Frontend
cd frontend
npm run test
npm run build
```

## Endpoints principales

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/api/v1/priorities` | Prioridades activas |
| `POST` | `/api/v1/suggestions` | Sugerencia de categoría y prioridad |
| `POST` | `/api/v1/tickets` | Crea un ticket (`multipart/form-data`) |

Todas las peticiones requieren la cabecera `X-Employee-Id`.

## Documentación funcional

- [Especificación](specs/002-crear-ticket/spec.md)
- [Plan técnico](specs/002-crear-ticket/plan.md)
- [Modelo de datos](specs/002-crear-ticket/data-model.md)
- [Contrato OpenAPI](specs/002-crear-ticket/contracts/openapi.yaml)
- [Guía de validación](specs/002-crear-ticket/quickstart.md)
