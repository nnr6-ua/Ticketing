# Implementation Plan: Seguimiento de la evolución del ticket (estado y línea temporal)

**Branch**: `002-ticket-timeline-history` | **Date**: 2026-11-13 | **Spec**: `specs/002-ticket-timeline-history/spec.md`

**Input**: Feature specification from `specs/002-ticket-timeline-history/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command; its definition describes the execution workflow.

## Summary

El usuario creador de un ticket puede consultar en cualquier momento el estado actual y revisar la línea temporal cronológica del ticket (cambios de estado, resoluciones y comentarios públicos del técnico), sin tener que contactar al técnico. El backend expone endpoints de sólo lectura para obtener el resumen del ticket y su línea temporal paginada; el frontend renderiza el estado actual y la línea temporal en la vista de detalle del ticket. La escritura (cambios de estado, resoluciones, comentarios internos) pertenece a HU-05; esta historia solo consulta.

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript (frontend)

**Primary Dependencies**: Backend: FastAPI 0.115.6, SQLAlchemy 2.0.36, Alembic 1.14.0, psycopg 3.2.3, Pydantic 2.10.4, PyJWT 2.10.1, pytest 8.3.4. Frontend: Vue 3, Pinia, Tailwind CSS, Vite, Vitest.

**Storage**: PostgreSQL (desarrollo y producción); SQLite solo para pruebas locales mediante la abstracción de sesión existente.

**Testing**: pytest (backend), vitest (frontend).

**Target Platform**: Linux server.

**Project Type**: Web application (backend + frontend).

**Performance Goals**: Lecturas y comandos en p95 inferior a 300 ms de servidor; el historial de línea temporal se paga.

**Constraints**: p95 < 300 ms; paginación del historial; interfaz y mensajes en español de España (es-ES); fechas mostradas en Europe/Madrid y almacenadas en UTC; WCAG 2.1 AA; responsive; teclado y lectores de pantalla; formato de error `{"detail": {"code": "...", "message": "..."}}` con códigos en snake_case.

**Scale/Scope**: Volumen previsto de la mesa de ayuda (varios miles de tickets; decenas de entradas de línea temporal por ticket).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Constitution principle / restriction | Assessment | Status |
|---|---|---|---|
| I | Arquitectura por capas y stack fijado: api → services → models/db; endpoints solo orquestan; lógica en services; no nuevas tecnologías | La consulta de estado y timeline se implementa como endpoints GET que orquestan servicios existentes (`ticket_timeline.get_timeline`, `ticket_by_id`); se reusa el stack actual (FastAPI, SQLAlchemy, Pydantic, Vue 3). No se introduce nueva tecnología. | PASS |
| II | Modelo de datos estable y migraciones aditivas; histórico append-only e inmutable | No se modifica el esquema: se reusan `tickets` y `ticket_timeline_entries` de HU-05. La línea temporal es append-only y se consulta sin editar ni eliminar entradas. | PASS |
| III | Seguridad y mínimo privilegio: identidad por JWT; autorización en servidor; datos internos nunca al usuario creador | `can_read_ticket` permite lectura al creador o roles operativos. `viewer_capabilities` oculta `is_internal=true` a quien no sea asignado/supervisor/admin. El usuario creador ve solo comentarios públicos (per RN-03 de la especificación). | PASS |
| IV | Contratos primero y pruebas verificables; matriz de estados, permisos, visibilidad, atomicidad, idempotencia, códigos de error | Se documentan contratos de endpoint (GET ticket, GET timeline) en `contracts/`; se cubren pruebas de permisos y visibilidad de comentarios internos. | PASS |
| V | Simplicidad, trazabilidad y experiencia en español; línea temporal con autor, fecha, estado anterior/nuevo; interfaz en es-ES, fechas Europe/Madrid, UTC almacenado | La línea temporal ya registra autor, fecha y hora (HU-05); esta historia la muestra ordenada cronológicamente. Interfaz en español; fechas en Europe/Madrid. | PASS |

Gates evaluated: all 5 principles pass. No violations; no Complexity Tracking entries required.

## Project Structure

### Documentation (this feature)

```text
specs/002-ticket-timeline-history/
├── spec.md              # Feature specification (/speckit.specify output)
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
│   └── ticket-timeline.query.openapi.yaml
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
backend/
├── src/            # (app/)
│   ├── api/        # Endpoints de consulta (GET ticket, GET timeline)
│   ├── services/   # ticket_timeline.get_timeline (ya existente, reutilizado)
│   ├── models/     # Ticket, TicketTimelineEntry (ya existentes, reutilizados)
│   └── schemas/    # TimelineResponse, TicketWorkflowSnapshot (ya existentes, reutilizados)
├── tests/
│   ├── contract/   # Pruebas de contrato de endpoints de consulta
│   └── integration/# Pruebas de visibilidad y permisos de timeline
frontend/
├── src/
│   ├── components/ # TicketTimeline, TicketStatus (vista de detalle)
│   ├── pages/      # Página de detalle del ticket
│   ├── services/   # Cliente HTTP para consultar ticket y timeline
│   └── stores/     # ticketDetail store (ya existente, reutilizado)
└── tests/
    └── components/ # TicketTimeline, ResolutionForm, etc.
```

**Structure Decision**: Web application (Option 2): `backend/` y `frontend/` separados, siguiendo la estructura existente del repositorio. No se crea un tercer proyecto; se reusan `app/` y `src/` actuales.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No entries: all Constitution Check gates pass without violations.

---

## Phase 0: Outline & Research

No `[NEEDS CLARIFICATION]` markers remain in the specification; all Technical Context fields are resolved from the constitution and existing codebase. Research decisions are consolidated below.

### research.md

See `specs/002-ticket-timeline-history/research.md`.

**Decisions**:
- **Reutilizar modelo y servicio existentes**: `Ticket`, `TicketTimelineEntry`, `ticket_timeline.get_timeline` y `ticket_by_id` de HU-05 se reutilizan sin modificar. Rationale: evita duplicación y respeta el modelo de datos estable (constitución II).
- **Visibilidad de comentarios internos**: el usuario creador ve solo comentarios no internos (`is_internal = false`), aplicando el filtro ya existente en `get_timeline` cuando `can_view_internal` es falso. Rationale: cumple la constitución III y RN-03 de la especificación.
- **Endpoints de solo lectura**: `GET /tickets/{ticket_id}` (resumen del ticket con estado actual) y `GET /tickets/{ticket_id}/timeline` (línea temporal paginada). Rationale: la historia es de consulta; no se añaden comandos de escritura.
- **Paginación**: página y page_size con límites (máx. 200), orden cronológico por `created_at` y `event_order`. Rationale: cumple el requisito de paginación del historial y el objetivo de p95 < 300 ms.
- **Zona horaria**: fechas almacenadas en UTC, mostradas en Europe/Madrid. Rationale: constitución V.

**Alternatives considered**:
- Crear un nuevo modelo de "historial público" separado: rechazado, duplica datos y viola la inmutabilidad append-only (constitución II).
- Exponer todos los comentarios internos al usuario creador: rechazado, viola el mínimo privilegio (constitución III).
- Sin paginación (cargar todo el historial): rechazado, afecta el rendimiento p95 con historiales largos.

## Phase 1: Design & Contracts

### data-model.md

See `specs/002-ticket-timeline-history/data-model.md`.

### contracts/

See `specs/002-ticket-timeline-history/contracts/ticket-timeline.query.openapi.yaml`.

### quickstart.md

See `specs/002-ticket-timeline-history/quickstart.md`.

### Re-evaluated Constitution Check (post-design)

| # | Constitution principle / restriction | Post-design assessment | Status |
|---|---|---|---|
| I | Capas y stack fijado | Endpoints GET orquestan servicios existentes; sin nuevas tecnologías. | PASS |
| II | Datos estables, histórico append-only | Sin cambios de esquema; timeline solo se lee. | PASS |
| III | Seguridad y mínimo privilegio | Comentarios internos filtrados por rol/asignación en servidor. | PASS |
| IV | Contratos y pruebas | Contratos OpenAPI documentados; pruebas de permisos y visibilidad. | PASS |
| V | Simplicidad, trazabilidad, español | Línea temporal con autor/fecha; interfaz en es-ES. | PASS |

All gates pass post-design. No violations.
