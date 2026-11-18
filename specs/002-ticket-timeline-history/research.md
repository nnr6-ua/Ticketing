# Research: Seguimiento de la evolución del ticket (estado y línea temporal)

**Feature**: `002-ticket-timeline-history`
**Date**: 2026-11-13
**Spec**: `specs/002-ticket-timeline-history/spec.md`

## Context

Esta historia (HU-02 del sistema base) es de solo lectura: el usuario creador consulta el estado actual y la línea temporal de sus propios tickets. La escritura (cambios de estado, resoluciones, comentarios internos) ya está implementada en HU-05 (`005-cambio-estado-resolucion`) sobre los modelos `Ticket` y `TicketTimelineEntry` y el servicio `ticket_timeline.get_timeline`.

No hay `[NEEDS CLARIFICATION]` pendientes en la especificación; todos los campos del Technical Context se resuelven a partir de la constitución y el código existente.

## Decisions

### Decision 1: Reutilizar modelo y servicio existentes (HU-05)

**Decision**: No se crea ningún modelo ni servicio nuevo. Se reutilizan `Ticket`, `TicketTimelineEntry`, `ticket_timeline.get_timeline`, `ticket_by_id`, `viewer_capabilities` y `can_read_ticket`.

**Rationale**: La constitución (principio II) exige un modelo de datos estable y cambios aditivos; duplicar el modelo de línea temporal violaría ese principio y el principio de simplicidad (principio V). HU-05 ya provee las entradas de línea temporal que esta historia consulta.

**Alternatives considered**:
- Modelo separado `TicketHistoryPublic`: rechazado (duplica datos, rompe inmutabilidad append-only).

### Decision 2: Visibilidad de comentarios internos

**Decision**: El usuario creador ve solo las entradas de línea temporal con `is_internal = false` (cambios de estado, resoluciones y comentarios públicos del técnico). Los comentarios internos (`is_internal = true`) se filtran en SQL cuando `can_view_internal` es falso, reutilizando la lógica ya existente de `ticket_timeline.get_timeline`.

**Rationale**: Cumple la constitución (principio III, mínimo privilegio) y RN-03 de la especificación (acordado en clarificación: solo comentarios públicos visibles al usuario creador).

**Alternatives considered**:
- Exponer comentarios internos al creador: rechazado (violaría privacidad de notas internas).
- Ocultar todos los comentarios al creador: rechazado (no cumple "cada comentario que el técnico haya ido dejando" de la descripción de usuario, limitada por privacidad).

### Decision 3: Endpoints de solo lectura

**Decision**: Dos endpoints GET:
- `GET /tickets/{ticket_id}` → resumen del ticket con estado actual (`TicketWorkflowSnapshot`).
- `GET /tickets/{ticket_id}/timeline` → línea temporal paginada (`TimelineResponse`).

**Rationale**: La historia es de consulta; no se añaden comandos de escritura ni se modifican estados. Reusa los esquemas Pydantic existentes de HU-05.

**Alternatives considered**:
- Un único endpoint combinado: rechazado (menos claro, acopla resumen y timeline).
- Endpoints POST para consultas: rechazado (el cliente compilado expone GET; constitution restricción de compatibilidad de cliente).

### Decision 4: Paginación y ordenamiento

**Decision**: Página y page_size (máx. 200), orden cronológico por `created_at` asc, `event_order` asc, `id` asc. Total items, total_pages, has_next, has_previous.

**Rationale**: El historial se paga (supuesto 6 de la especificación y restricción de rendimiento de la constitución: p95 < 300 ms). El orden cronológico cumple RF-003/RF-009.

**Alternatives considered**:
- Cargar todo el historial sin paginar: rechazado (riesgo de rendimiento en historiales largos).

### Decision 5: Zona horaria

**Decision**: Fechas almacenadas en UTC; mostradas en Europe/Madrid. `as_utc` normaliza a UTC en la serialización.

**Rationale**: Constitución V (fechas en Europe/Madrid mostradas, UTC almacenado).

## Alternatives Considered (summary)

| Option | Evaluated | Decision | Why rejected / accepted |
|--------|-----------|----------|-------------------------|
| Nuevo modelo de historial público separado | Sí | Rechazado | Duplica datos; viola modelo estable e inmutabilidad |
| Exponer comentarios internos al creador | Sí | Rechazado | Viola mínimo privilegio (constitución III) |
| Ocultar todos los comentarios al creador | Sí | Rechazado | No cumple necesidad de usuario de ver comentarios públicos |
| Endpoint único combinado resumen+timeline | Sí | Rechazado | Menos claro; acopla dos consultas |
| Consultas vía POST | Sí | Rechazado | Cliente soporta GET; restricción de compatibilidad |
| Sin paginación | Sí | Rechazado | Riesgo de rendimiento (p95 < 300 ms) |

## Open questions

None. All technical decisions are resolved.
