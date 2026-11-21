# Implementation Plan: Creación de tickets de incidencia

**Branch**: `001-crear-ticket` | **Date**: 2026-10-29 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-crear-ticket/spec.md`

## Summary

Implementar la primera funcionalidad de la mesa de ayuda: un empleado autenticado crea un ticket con título, descripción y hasta cinco capturas de pantalla, recibe un número de referencia secuencial con prefijo (`TK-000001`) y el sistema le propone una categoría fija y una prioridad editable mediante coincidencia sencilla de palabras clave. El ticket nace en estado "Abierto", registra creador, fecha y primer evento de historial, evita duplicados por mismo creador y contenido, y valida tipo/tamaño de adjuntos con comportamiento todo-o-nada.

La solución es una aplicación web con frontend Vue 3 + Tailwind CSS + Headless UI, API REST FastAPI y PostgreSQL. Los adjuntos se guardan en una carpeta local del servidor. No se implementa autenticación, seguimiento, administración de catálogos ni notificaciones: quedan fuera del alcance de esta historia.

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript 5.x + Node.js 20 LTS (frontend)

**Primary Dependencies**:
- Backend: FastAPI, SQLAlchemy 2.0 (modo síncrono), Alembic, Pydantic v2, `python-multipart`, `psycopg[binary]`, Uvicorn.
- Frontend: Vue 3, Vite, Tailwind CSS, `@headlessui/vue`, `@heroicons/vue` (iconos), Vitest + Vue Test Utils.
- Sin ORM asíncrono, sin gestor de estado externo, sin axios: `fetch` nativo.

**Storage**: PostgreSQL 16 para datos; carpeta local del servidor para adjuntos (`ATTACHMENTS_DIR`, por defecto `backend/attachments/`).

**Testing**: `pytest` + `httpx`/`TestClient` contra PostgreSQL de pruebas para backend; Vitest + Vue Test Utils + jsdom para frontend. Validación manual end-to-end en `quickstart.md`.

**Target Platform**: Servidor Linux; navegadores modernos (Chrome, Edge, Firefox, Safari últimas 2 versiones); diseño responsive para escritorio y tablet.

**Project Type**: Aplicación web (frontend + backend) en monorepo.

**Performance Goals**:
- Creación de ticket (sin contar transferencia de adjuntos): p95 < 500 ms.
- Sugerencia de categoría/prioridad: p95 < 200 ms.
- Carga inicial de la pantalla de creación: < 2 s en red de oficina.
- Hasta 5 adjuntos de 5 MB por ticket (25 MB por envío como máximo).

**Constraints**:
- Título 5–120 caracteres; descripción 20–5000 caracteres (contados tras recortar espacios).
- Adjuntos: PNG, JPG/JPEG o GIF; máximo 5 MB por archivo; máximo 5 archivos.
- Todo el texto de interfaz y errores en español de España.
- Sin claves ni secretos en código; configuración por variables de entorno.
- Sin autenticación propia: se consume una identidad de empleado provista por el entorno (ver research.md).
- Los adjuntos deben ser todo-o-nada: si falla uno, no se crea el ticket.

**Scale/Scope**: Uso interno de una organización; cientos de empleados y miles de tickets al mes. Una única pantalla de creación más confirmación. Sin portal externo, sin app móvil nativa, sin multi-tenant.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitución aplicable: [`.specify/memory/constitution.md`](../../.specify/memory/constitution.md) (v1.0.0, ratificada). [`CONSTITUTION.md`](../../CONSTITUTION.md) en la raíz es solo un resumen informativo.

| Principio canónico | Cumplimiento | Evidencia |
|-----------|--------------|-----------|
| I. Arquitectura por capas y stack fijado | PASA | FastAPI + SQLAlchemy 2 + Alembic + PostgreSQL y Vue 3 + TypeScript + Vite + Pinia + Tailwind; `api → services → models/db`; no se introduce ninguna tecnología nueva. |
| II. Modelo de datos estable y migraciones aditivas | PASA | La creación reutiliza el modelo `Ticket` y añade columnas/índices de forma aditiva con Alembic; la línea temporal es `append-only` y el número de ticket es secuencial e inmutable. |
| III. Seguridad y mínimo privilegio | PASA | El creador se toma del JWT; no se acepta `creator_id` manipulable; los adjuntos se validan por tipo y tamaño; sin secretos en código. |
| IV. Contratos primero y pruebas verificables | PASA | `contracts/openapi.yaml` precede a la implementación; `quickstart.md` y las pruebas de contrato/integración cubren duplicados, adjuntos todo-o-nada, límites y códigos de error. |
| V. Simplicidad, trazabilidad y experiencia en español | PASA | Un único flujo de creación, sin abstracciones especulativas; copia y errores en es-ES; la creación queda registrada como primer evento de la línea temporal. |

**Resultado**: sin violaciones. No se requiere justificación en Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/001-crear-ticket/
├── plan.md              # Este archivo
├── research.md          # Fase 0
├── data-model.md        # Fase 1
├── quickstart.md        # Fase 1
├── contracts/
│   └── openapi.yaml     # Fase 1
├── checklists/
│   └── requirements.md
└── tasks.md             # Fase 2 (/speckit.tasks, no creado aquí)
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── main.py
│   ├── core/
│   │   ├── config.py          # Variables de entorno (DATABASE_URL, ATTACHMENTS_DIR, CORS)
│   │   └── errors.py          # Errores de aplicación y handler en español
│   ├── db/
│   │   ├── base.py            # Declarative Base
│   │   └── session.py         # Engine y SessionLocal
│   ├── models/
│   │   ├── employee.py
│   │   ├── category.py
│   │   ├── priority.py
│   │   ├── ticket.py
│   │   ├── ticket_event.py
│   │   └── attachment.py
│   ├── schemas/
│   │   ├── catalog.py
│   │   ├── errors.py
│   │   ├── suggestion.py
│   │   └── ticket.py
│   ├── api/
│   │   ├── deps.py            # Empleado actual y sesión de BD
│   │   └── routes/
│   │       ├── priorities.py
│   │       ├── suggestions.py
│   │       └── tickets.py
│   ├── services/
│   │   ├── attachments.py     # Validación, guardado temporal y movimiento final
│   │   ├── duplicates.py      # Hash normalizado de contenido
│   │   ├── suggestions.py     # Coincidencia de palabras clave y fallback
│   │   └── tickets.py         # Transacción de creación y número de ticket
│   └── seeds/
│       └── seed.py            # Empleado demo, categorías, prioridades y palabras clave
├── alembic/
│   ├── env.py
│   └── versions/
├── tests/
│   ├── conftest.py
│   ├── unit/
│   ├── contract/
│   └── integration/
├── alembic.ini
├── pyproject.toml
├── .env.example
└── attachments/               # Ignorada en git; configurable

frontend/
├── src/
│   ├── main.ts
│   ├── App.vue
│   ├── style.css
│   ├── components/
│   │   ├── AppHeader.vue
│   │   ├── TicketForm.vue
│   │   ├── AttachmentField.vue
│   │   ├── SuggestionPanel.vue
│   │   ├── PrioritySelect.vue
│   │   ├── TicketConfirmation.vue
│   │   ├── ErrorBanner.vue
│   │   └── icons/
│   ├── composables/
│   │   └── useTicketForm.ts
│   ├── services/
│   │   └── api.ts
│   ├── types/
│   │   └── api.ts
│   └── tests/
│       ├── TicketForm.spec.ts
│       └── SuggestionPanel.spec.ts
├── index.html
├── package.json
├── tsconfig.json
├── vite.config.ts
├── tailwind.config.js
├── postcss.config.js
└── .env.example

docker-compose.yml             # PostgreSQL 16 para desarrollo local
.gitignore
```

**Structure Decision**: Aplicación web en monorepo con `backend/` y `frontend/`. Backend por capas (rutas → servicios → modelos) para que la lógica de creación, duplicados, sugerencias y adjuntos sea testeable sin HTTP. Frontend con una única vista y componentes enfocados en el formulario, la sugerencia y la confirmación; sin router ni store global porque solo hay un flujo.

## Post-Design Constitution Check

*Re-evaluación tras completar `research.md`, `data-model.md`, `contracts/openapi.yaml` y `quickstart.md`.*

| Principio canónico | Resultado | Nota |
|-----------|-----------|------|
| I. Arquitectura por capas y stack fijado | PASA | El diseño final mantiene el stack fijado, dos aplicaciones, una base de datos y almacenamiento local de adjuntos; sin colas, caché ni servicios externos. |
| II. Modelo de datos estable y migraciones aditivas | PASA | El contrato y `data-model.md` solo introducen campos aditivos y una migración reversible; no se renombra ni elimina nada. |
| III. Seguridad y mínimo privilegio | PASA | Identidad del JWT, validación estricta de MIME/tamaño y rutas de adjuntos derivadas del número de ticket; sin secretos versionados. |
| IV. Contratos primero y pruebas verificables | PASA | `contracts/openapi.yaml`, `quickstart.md` y las pruebas ejecutables cubren los diez escenarios manuales y los códigos de error. |
| V. Simplicidad, trazabilidad y experiencia en español | PASA | Contrato, datos de siembra, mensajes y quickstart en es-ES; la creación genera su entrada inicial en la línea temporal. |

**Resultado post-diseño**: sin violaciones.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

Sin violaciones de la constitución. No se añade complejidad no justificada.

## Phase 0 y Phase 1 — Artefactos generados

| Artefacto | Estado | Contenido |
|-----------|--------|-----------|
| `research.md` | Completo | 12 decisiones técnicas con rationale y alternativas; sin `NEEDS CLARIFICATION`. |
| `data-model.md` | Completo | 6 tablas, restricciones, índices, reglas de validación, hash, estados y datos de siembra. |
| `contracts/openapi.yaml` | Completo | Contrato OpenAPI 3.0.3 de prioridades, sugerencias y creación de tickets. |
| `quickstart.md` | Completo | Puesta en marcha, pruebas y 10 escenarios de validación manual. |
