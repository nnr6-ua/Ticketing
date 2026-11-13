# Data Model: Seguimiento de la evolución del ticket (estado y línea temporal)

**Feature**: `002-ticket-timeline-history`
**Date**: 2026-11-13
**Spec**: `specs/002-ticket-timeline-history/spec.md`

## Overview

Esta historia es de solo lectura y no introduce nuevos modelos de datos. Reusa las entidades ya definidas en HU-05:

- `Ticket` (`app/models/ticket.py`, tabla `tickets`)
- `TicketTimelineEntry` (`app/models/timeline.py`, tabla `ticket_timeline_entries`)
- `User` (`app/models/user.py`, tabla `users`)

No se añaden columnas, tablas ni enums. No se requiere migración de Alembic.

## Entities

### Ticket

Representa un ticket de la mesa de ayuda. Campos relevantes para esta historia (lectura):

| Campo | Tipo | Descripción |
|-------|------|-------------|
| id | UUID | Identificador único del ticket |
| number | String(20) | Número de referencia mostrado al usuario |
| title | String(200) | Título del ticket |
| status | TicketStatus (enum) | Estado actual: abierto, en_progreso, pendiente_usuario, resuelto, cerrado |
| creator_id | UUID | Usuario creador del ticket (quién puede consultar) |
| assignee_id | UUID | Técnico asignado actualmente |
| updated_at | DateTime (UTC) | Fecha y hora de última modificación |
| finalized_at | DateTime (UTC) | Fecha de resolución/cierre (puede ser nula) |

Relaciones: `creator` (User), `assignee` (User).

### TicketTimelineEntry

Entrada inmutable y append-only de la línea temporal. Campos relevantes:

| Campo | Tipo | Descripción |
|-------|------|-------------|
| id | UUID | Identificador único de la entrada |
| ticket_id | UUID | Ticket al que pertenece la entrada |
| event_type | TimelineEventType (enum) | `status_change`, `resolution`, `internal_comment` |
| from_status | TicketStatus | Estado anterior (solo `status_change`) |
| to_status | TicketStatus | Estado nuevo (solo `status_change`) |
| body | Text | Texto de resolución o comentario (nulo para `status_change`) |
| is_internal | Boolean | Si la entrada es interna (oculta al usuario creador) |
| author_id | UUID | Autor de la entrada |
| created_at | DateTime (UTC) | Fecha y hora de creación |
| event_order | SmallInteger | Orden de desempate dentro del mismo instante |
| request_id | UUID | Clave de idempotencia |

Relaciones: `author` (User), `ticket` (Ticket).

### User

Identidad del autor/consultante:

| Campo | Tipo | Descripción |
|-------|------|-------------|
| id | UUID | Identificador único |
| name | String | Nombre del autor |
| role | UserRole (enum) | usuario, tecnico, supervisor, admin |

## Relationships

- `Ticket` 1:N `TicketTimelineEntry` (un ticket tiene muchas entradas de línea temporal).
- `TicketTimelineEntry` N:1 `Ticket` y N:1 `User` (autor).
- `Ticket` N:1 `User` (creador) y N:1 `User` (técnico asignado).

## Validation Rules

Heredadas de HU-05, aplicadas en servidor:

- `TicketTimelineEntry.body`: si no es nulo, entre 1 y 5.000 caracteres (`ck_timeline_body_length`).
- `status_change`: `from_status` y `to_status` presentes, distintos, `body` nulo, `is_internal = false`.
- `resolution`: `to_status = resuelto`, `body` presente, `is_internal = false`.
- `internal_comment`: `from_status`/`to_status` nulos, `body` presente, `is_internal = true`.
- Unicidad de `(ticket_id, request_id, event_type)` (`uq_timeline_request_event`) para idempotencia.
- Índices: `ix_timeline_ticket_created` (ticket_id, created_at), `ix_timeline_ticket_internal` (ticket_id, is_internal), `ix_timeline_author` (author_id).

## State Transitions (read context)

Los estados válidos y sus transiciones son propiedad de HU-05 (`TicketStatus` enum y `allowed_transitions`). Esta historia solo los muestra:

- `abierto` → `en_progreso`
- `en_progreso` → `pendiente_usuario`, `resuelto`
- `pendiente_usuario` → `en_progreso` (manual o automático al responder el usuario, HU-03)
- `resuelto` → `en_progreso` (reapertura), `cerrado`
- `cerrado`: definitivo, sin transiciones salientes

## No Changes Required

- No nuevas tablas.
- No nuevas columnas.
- No nuevos enums.
- No migración de Alembic.
- No cambios a `data-model.md` de HU-05 (esta historia es de consulta sobre el modelo existente).
