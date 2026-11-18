# Implementation Plan: Cambio de estado y documentación de resolución (HU-05)

**Branch**: `hu-05-cambiar-estado` | **Date**: 2026-11-08 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/005-cambio-estado-resolucion/spec.md`

**Estado**: plan revisado contra las fuentes implementadas en `backend/` y `frontend/` el 2026-11-08. Los artefactos de Fase 0 y Fase 1 (`research.md`, `data-model.md`, `contracts/` y `quickstart.md`) están sincronizados con este documento.

## Summary

HU-05 añade al técnico asignado la capacidad de hacer avanzar el ticket por la máquina de estados definida en RN-02 y de documentar obligatoriamente la solución al pasar a «Resuelto». La solución se persiste como una **entrada estructurada e inmutable de la línea temporal** (`event_type = resolution`), no como un campo nuevo en `tickets`, para conservar el histórico de reaperturas y no alterar el modelo base. El cambio de estado y sus entradas de línea temporal se escriben en **una única transacción**, con bloqueo de fila y token de concurrencia (`updated_at`). El frontend incorpora un panel de trabajo con selector de estados permitidos, formulario de resolución con bloqueo de envío y formulario de comentarios internos; el backend sigue siendo la fuente de verdad de la máquina de estados y de la visibilidad.

**Decisiones clave**:

| Punto solicitado | Decisión |
|---|---|
| Validación de transiciones | Máquina de estados pura en `app/services/ticket_state_machine.py` + validación transaccional en `app/services/ticket_workflow.py` |
| Persistencia de la resolución | Entrada `resolution` en la nueva tabla `ticket_timeline_entries`; `tickets` no cambia de esquema |
| Componentes de interfaz | `TicketWorkflowPanel` + `TicketStatusSelector` + `ResolutionForm` + `InternalCommentForm` + `TicketTimeline` (Vue 3 + Tailwind) |
| Trazabilidad y coherencia | Migración aditiva `0003_ticket_timeline`, `finalized_at`/`closed_at` existentes, sin nuevas tecnologías |

## Technical Context

**Language/Version**: Python 3.12 (backend, `.venv` actual), TypeScript + Vue 3 (frontend)

**Primary Dependencies**: FastAPI 0.115.6, SQLAlchemy 2.0.36, Pydantic 2.10.4, Alembic 1.14.0, psycopg; Vue 3, Vite, Tailwind CSS, Pinia, Vue Router; Vitest + `@vue/test-utils` (ya presentes en `frontend/node_modules`)

**Storage**: PostgreSQL en desarrollo/producción (`postgresql+psycopg://...`); SQLite en pruebas locales mediante la abstracción existente de `app/db/session.py`. La tabla nueva usa tipos genéricos de SQLAlchemy y un `Enum` compatible con ambos motores.

**Testing**: `pytest` 8.3.4 + `fastapi.testclient`/`httpx`; `vitest` + `@vue/test-utils` para componentes.

**Target Platform**: Servicio web Linux + interfaz web responsive (desktop/tablet).

**Project Type**: Aplicación web con backend y frontend separados.

**Performance Goals**:
- Cambio de estado y creación de entradas: p95 < 300 ms en servidor (sin contar red).
- Línea temporal visible tras el cambio: < 2 s percibidos por el usuario.
- Cuerpo de resolución/comentario: 1–5.000 caracteres.
- Listado de línea temporal paginado (50 por defecto, 200 máximo) para tickets con historial largo.

**Constraints**:
- Interfaz y mensajes 100 % en español de España (RNF-01).
- Accesibilidad WCAG 2.1 AA (RNF-03) y diseño responsive (RNF-04).
- Autenticación JWT existente; identidad solo desde `Authorization: Bearer` (nunca por query string).
- Sin secretos en código (RNF-07).
- No se introducen nuevas tecnologías ni se modifican las columnas base de `tickets`.

**Scale/Scope**: Mesa de ayuda interna; miles de tickets y decenas de entradas por ticket. La tabla de línea temporal crece de forma append-only; se indexa por ticket y fecha.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

La constitución del proyecto está ratificada en `.specify/memory/constitution.md` (versión 1.0.0, 2026-11-02). Se evalúan sus cinco principios y sus restricciones adicionales:

| Principio / restricción | Resultado | Justificación |
|---|---|---|
| I. Arquitectura por capas y stack fijado | PASS | Se reutilizan FastAPI, SQLAlchemy 2, Alembic, PostgreSQL, Vue 3, TypeScript, Pinia, Tailwind y Vitest; los endpoints delegan en `ticket_workflow.py` y `ticket_timeline.py`. |
| II. Modelo de datos estable y migraciones aditivas | PASS | `tickets` no recibe columnas nuevas; la migración `0003_ticket_timeline` solo añade tabla, enum e índices, con `downgrade()` verificable. La resolución es append-only en la línea temporal. |
| III. Seguridad y mínimo privilegio | PASS | Identidad solo desde JWT; escrituras limitadas al técnico asignado; `viewer_capabilities` y el filtro `is_internal` se calculan en servidor; sin `v-html`. |
| IV. Contratos primero y pruebas verificables | PASS | Contratos OpenAPI y de componentes documentados antes de implementar; matriz 5×5, validaciones, atomicidad, concurrencia, idempotencia, visibilidad y códigos estables tienen pruebas explícitas. |
| V. Simplicidad, trazabilidad y español de España | PASS | Máquina de estados pura, sin motores externos; línea temporal inmutable con autor y fecha; mensajes es-ES, fechas `Europe/Madrid` y accesibilidad WCAG 2.1 AA. |
| Restricciones adicionales | PASS | Formato de error heredado, comandos POST compatibles con el cliente, paginación del historial y presupuesto p95 < 300 ms. |

**Post-design re-check (Phase 1)**: PASS. El diseño final no introduce violaciones de la constitución; no se requiere `Complexity Tracking`.

## Project Structure

### Documentation (this feature)

```text
specs/005-cambio-estado-resolucion/
├── plan.md                  # Este archivo
├── research.md              # Fase 0: decisiones y alternativas
├── data-model.md            # Fase 1: entidades, invariantes y migración
├── quickstart.md            # Fase 1: validación ejecutable
├── contracts/
│   ├── ticket-workflow.openapi.yaml   # Contrato HTTP
│   └── frontend-components.md         # Contrato de componentes Vue
├── checklists/
│   └── requirements.md      # Checklist de calidad de la especificación
├── spec.md                  # Especificación funcional
└── tasks.md                 # Fase 2 (/speckit.tasks, no lo crea este comando)
```

### Source Code (repository root)

```text
backend/
├── alembic/
│   └── versions/
│       └── 0003_ticket_timeline.py          # NUEVO: tabla + enum + índices
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── tickets.py                   # NUEVO: endpoints de HU-05
│   │       └── router.py                    # MODIFICADO: include_router(tickets)
│   ├── models/
│   │   ├── enums.py                         # MODIFICADO: TimelineEventType (aditivo)
│   │   ├── timeline.py                      # NUEVO: TicketTimelineEntry
│   │   └── __init__.py                      # MODIFICADO: exportar el modelo
│   ├── schemas/
│   │   └── ticket_workflow.py               # NUEVO: request/response Pydantic
│   ├── services/
│   │   ├── ticket_state_machine.py          # NUEVO: matriz y funciones puras
│   │   ├── ticket_workflow.py               # NUEVO: comandos transaccionales
│   │   └── ticket_timeline.py               # NUEVO: lectura y visibilidad
│   ├── core/
│   │   └── errors.py                        # MODIFICADO: handler RequestValidationError → invalid_request
│   └── main.py                              # MODIFICADO: registrar el handler de validación
└── tests/
    ├── unit/
    │   └── test_ticket_state_machine.py
    ├── integration/
    │   ├── test_ticket_status_transitions.py
    │   ├── test_ticket_concurrency.py
    │   ├── test_internal_comments.py
    │   ├── test_timeline_visibility.py
    │   └── test_ticket_workflow_performance.py
    └── contract/
        └── test_ticket_workflow_contract.py

frontend/
├── src/
│   ├── components/
│   │   └── tickets/
│   │       ├── TicketWorkflowPanel.vue      # NUEVO: orquestador
│   │       ├── TicketStatusSelector.vue     # NUEVO: estados permitidos
│   │       ├── ResolutionForm.vue           # NUEVO: descripción obligatoria
│   │       ├── InternalCommentForm.vue      # NUEVO: comentario interno
│   │       └── TicketTimeline.vue           # NUEVO: línea temporal
│   ├── services/
│   │   └── ticketWorkflow.ts                # NUEVO: cliente de los endpoints
│   ├── stores/
│   │   └── ticketDetail.ts                  # NUEVO: estado del detalle
│   ├── types/
│   │   └── ticketWorkflow.ts                # NUEVO: tipos TypeScript
│   └── views/
│       └── TicketDetailPage.vue             # NUEVO/INTEGRACIÓN: ruta /tickets/:id
└── tests/
    ├── components/
    │   ├── TicketStatusSelector.spec.ts
    │   ├── ResolutionForm.spec.ts
    │   ├── InternalCommentForm.spec.ts
    │   ├── TicketTimeline.spec.ts
    │   └── TicketWorkflowPanel.spec.ts
    └── stores/
        └── ticketDetail.spec.ts
```

**Nota de estado del repositorio**: a fecha 2026-11-08 las fuentes de HU-05 ya existen en el árbol de trabajo (`backend/app/**`, `backend/alembic/versions/0003_ticket_timeline.py`, `frontend/src/**` y las suites de pruebas listadas). Este plan se ha contrastado con esas fuentes; las etiquetas `MODIFICADO` indican ficheros preexistentes que HU-05 amplía y `NUEVO` los que introduce la historia.

**Structure Decision**: se mantiene la arquitectura por capas existente (`api` → `services` → `models`/`db`, con `schemas` para contratos). La máquina de estados pura se separa del servicio transaccional para poder probarla sin base de datos. En el frontend se mantiene la organización por `components`, `services`, `stores`, `types` y `views` ya presente en el repositorio. Las fuentes de HU-05 respetan las convenciones existentes: cliente HTTP con `Authorization: Bearer` desde `localStorage.access_token`, errores `{"detail": {"code", "message"}}`, router con las rutas `/cola-de-trabajo`, `/tickets/:id` y `/login`, y Tailwind con la paleta `slate` ya usada.

## Phase 0: Outline & Research

**Output**: [research.md](./research.md)

Resumen de decisiones (detalle y alternativas en `research.md`):

- **R1 — Máquina de estados explícita y pura**: mapa `dict[TicketStatus, frozenset[TicketStatus]]` en `ticket_state_machine.py`; sin condicionales dispersos.
- **R2 — Resolución como entrada de línea temporal**: append-only, permite múltiples resoluciones tras reapertura y deja `tickets` intacto.
- **R3 — Concurrencia optimista con `updated_at`**: el cliente envía `expected_updated_at`; el servicio bloquea la fila y compara antes de escribir.
- **R4 — Idempotencia**: estado destino igual al actual ⇒ `200` con `changed = false`; `request_id` obligatorio en transiciones y comentarios, con restricción única. En transiciones, un reintento idéntico (mismo actor, destino y resolución normalizada) no escribe y devuelve `changed=false`; si difiere cualquiera, `409 request_id_reused`. En comentarios internos, un reintento idéntico (mismo autor y `body.strip()`) devuelve `created=false`; si difiere el texto o el autor, `409 request_id_reused` sin escribir.
- **R5 — Endpoints de comando POST**: el cliente HTTP existente solo implementa GET/POST; se usan recursos de comando (`/status-transitions`, `/internal-comments`) para no introducir PATCH.
- **R6 — Visibilidad calculada en servidor**: la línea temporal filtra `is_internal` según rol y asignación; el cliente nunca recibe lo que no debe ver.
- **R7 — Validación en dos capas con códigos estables**: Pydantic valida únicamente forma y tipos (UUID, enum, fecha ISO) mediante `StatusTransitionRequest`; **no** aplica longitudes de negocio. Un handler de `RequestValidationError` en `app/core/errors.py` (registrado en `app/main.py`) traduce cualquier payload mal formado a `422 invalid_request` con el formato heredado. El servicio valida transición, resolución y comentario, y devuelve códigos de negocio estables (`resolution_required`, `resolution_too_long`, `resolution_not_allowed`, `comment_required`, `comment_too_long`). El frontend replica solo la UX; nunca sustituye al backend.
- **R8 — Frontend sin duplicar la matriz**: el selector consume `allowed_transitions` del backend; el bloqueo de resolución es una copia de seguridad de UX, no la única defensa.

## Phase 1: Design & Contracts

**Output**: [data-model.md](./data-model.md), [contracts/ticket-workflow.openapi.yaml](./contracts/ticket-workflow.openapi.yaml), [contracts/frontend-components.md](./contracts/frontend-components.md), [quickstart.md](./quickstart.md)

---

## Diseño detallado

### 1. Validación de transiciones (Backend / FastAPI)

#### 1.1. Máquina de estados pura

Fichero: `backend/app/services/ticket_state_machine.py`. No importa SQLAlchemy ni FastAPI; solo `TicketStatus` y utilidades de etiquetas.

```text
ABIERTO             → EN_PROGRESO
EN_PROGRESO         → PENDIENTE_USUARIO, RESUELTO
PENDIENTE_USUARIO   → EN_PROGRESO        (manual por técnico; automático por HU-03)
RESUELTO            → EN_PROGRESO        (reapertura), CERRADO
CERRADO             → (ninguno)
```

```python
# Contrato conceptual; la implementación real vive en el módulo indicado.
ALLOWED_TRANSITIONS: dict[TicketStatus, frozenset[TicketStatus]] = {
    TicketStatus.abierto: frozenset({TicketStatus.en_progreso}),
    TicketStatus.en_progreso: frozenset({
        TicketStatus.pendiente_usuario,
        TicketStatus.resuelto,
    }),
    TicketStatus.pendiente_usuario: frozenset({TicketStatus.en_progreso}),
    TicketStatus.resuelto: frozenset({
        TicketStatus.en_progreso,
        TicketStatus.cerrado,
    }),
    TicketStatus.cerrado: frozenset(),
}
```

Funciones públicas:

```python
def allowed_transitions(current: TicketStatus) -> tuple[TicketStatus, ...]
def is_transition_allowed(current: TicketStatus, target: TicketStatus) -> bool
def is_final_status(status: TicketStatus) -> bool
def status_label(status: TicketStatus) -> str
def allowed_status_options(current: TicketStatus) -> list[StatusOption]
```

Propiedades que las pruebas deben cubrir:

- La matriz es **total**: los cinco estados tienen entrada, incluido `cerrado` con conjunto vacío.
- No hay auto-transiciones en la matriz; el mismo estado se trata como no-op idempotente antes de consultar la matriz.
- `FINAL_STATUSES` existente (`resuelto`, `cerrado`) se reutiliza para etiquetas y coherencia con la cola de trabajo; no se redefine.
- `allowed_transitions` conserva un orden estable y legible para la UI (por ejemplo, el orden de `TicketStatus`).
- **RF-005 no se implementa aquí**: la transición automática `pendiente_usuario → en_progreso` al responder el usuario creador pertenece a HU-03. HU-05 solo declara la transición como válida en la matriz y garantiza que, cuando HU-03 la ejecute, se registre con autor y fecha. La detección de la respuesta y el contenido de la solicitud de información quedan fuera de esta historia.

#### 1.2. Orden de validación en el servicio transaccional

Fichero: `backend/app/services/ticket_workflow.py`, función `change_status(...)`. El endpoint solo orquesta; toda la lógica vive aquí.

| # | Comprobación | Resultado si falla |
|---|---|---|
| 1 | Usuario autenticado (`get_current_user`) | `401 not_authenticated` |
| 2 | Ticket existe | `404 ticket_not_found` |
| 3 | `ticket.assignee_id == current_user.id` y rol `tecnico` | `403 not_ticket_assignee` / `403 forbidden` |
| 4 | `request_id` ya registrado para el ticket: mismo actor, mismo `target_status` y misma resolución normalizada | `200` con `changed = false`, `timeline_entries = []` (replay idempotente: **no** reproduce las entradas originales) y mensaje «Esta transición ya se aplicó con el identificador de solicitud indicado.»; si difiere cualquiera de los tres, `409 request_id_reused` |
| 5 | Si `target_status != resuelto`: `resolution` debe ser `null`/ausente | `422 resolution_not_allowed` |
| 6 | `target_status == ticket.status` | `200` con `changed = false`; no se escribe nada |
| 7 | `expected_updated_at == ticket.updated_at` | `409 stale_ticket` |
| 8 | `ticket.status != cerrado` | `409 ticket_closed` |
| 9 | `target_status ∈ allowed_transitions(ticket.status)` | `409 invalid_transition` (incluye estados disponibles) |
| 10 | Si `target_status == resuelto`: resolución presente, no vacía tras `strip()`, ≤ 5.000 caracteres | `422 resolution_required` / `422 resolution_too_long` |

La comprobación 5 se adelanta al no-op (6): una petición con `resolution` y destino distinto de `resuelto` es inválida aunque coincida con el estado actual (RF-034). Para un destino `resuelto` sobre un ticket ya `resuelto`, se conserva el no-op `200 changed=false` sin escribir. La comprobación 4 (replay idempotente) sigue teniendo prioridad sobre las validaciones de payload.

La comprobación 4 va antes que la 6 para que un reintento con el mismo `request_id` devuelva el mismo resultado lógico (snapshot actual del ticket, `changed=false`, `timeline_entries=[]`) aunque el ticket haya avanzado. La 6 va antes que la 7 para que un doble envío del mismo destino sea idempotente aunque el primer envío ya haya actualizado `updated_at`. La 7 va antes que 8 y 9 para pedir al cliente que refresque antes de diagnosticar una transición sobre datos obsoletos.

**Fuente única de idempotencia**: la búsqueda y comparación de `request_id` vive exclusivamente en `ticket_workflow.py`, con helpers internos por tipo de comando: `_transition_entries` + `_classify_transition_replay` para `change_status`/`apply_user_response_transition`, y `_comment_entries` para `add_internal_comment`. El router (`api/v1/tickets.py`) no consulta `request_id`, no compara cuerpos y no decide `changed`/`created`: solo devuelve el `StatusTransitionResponse`/`InternalCommentResponse` del servicio y ajusta el `201` cuando `created` es verdadero; los conflictos se propagan como `ApiError` desde el servicio. Cualquier regla nueva de idempotencia se añade en el servicio y en sus pruebas, nunca en dos capas.

#### 1.3. Bloqueo y atomicidad

```text
BEGIN
  SELECT id FROM tickets WHERE id = :id FOR UPDATE  -- PostgreSQL; SQLite lo ignora
  SELECT * FROM tickets WHERE id = :id              -- recarga con populate_existing
  validar (tabla anterior)
  tickets.status          = target
  tickets.updated_at      = now
  tickets.finalized_at    = now      si target == resuelto
                          = NULL     si target == en_progreso y origen == resuelto (reapertura)
                          = sin cambios en el resto
  tickets.closed_at       = now      si target == cerrado
                          = NULL     si target == en_progreso (reapertura)
  INSERT ticket_timeline_entries (status_change, from, to, author, created_at, request_id)
  INSERT ticket_timeline_entries (resolution, to=resuelto, body, author, created_at, request_id)
      -- solo si target == resuelto
  COMMIT
```

- El bloqueo se aplica solo a la fila de `tickets` mediante `SELECT id ... FOR UPDATE`; la carga completa se hace después con `session.get(..., populate_existing=True)` para releer el estado confirmado. Así se evita aplicar `FOR UPDATE` sobre el lado nullable de los `OUTER JOIN` de las relaciones eager (PostgreSQL lo rechaza) y se descarta cualquier instancia obsoleta del identity map del llamador.
- Un `flush()` intermedio fuerza las restricciones `CHECK`/`UNIQUE` antes del `commit()`.
- Cualquier excepción ejecuta `rollback()` y se traduce a un `ApiError` con el mensaje de la tabla de errores; nunca se persiste un cambio parcial.
- `expire_on_commit=False` está configurado en `SessionLocal`, por lo que el objeto actualizado puede serializarse sin recargar.
- En SQLite (pruebas) `FOR UPDATE` no aplica; las pruebas de concurrencia real se marcan para PostgreSQL. La corrección funcional se prueba con el token `expected_updated_at`.

#### 1.4. Endpoints

| Método | Ruta | Propósito | Éxito |
|---|---|---|---|
| `GET` | `/api/v1/tickets/{ticket_id}/workflow` | Estado actual, estados permitidos y capacidades del usuario | `200` |
| `POST` | `/api/v1/tickets/{ticket_id}/status-transitions` | Comando de cambio de estado + resolución | `200` |
| `POST` | `/api/v1/tickets/{ticket_id}/internal-comments` | Añadir comentario interno | `201` (nuevo) / `200` (reintento idempotente) |
| `GET` | `/api/v1/tickets/{ticket_id}/timeline` | Línea temporal filtrada por visibilidad (paginada) | `200` |

Se usa `POST` para comandos porque el cliente HTTP compilado (`frontend/dist/assets/client-*.js`) solo expone GET y POST; así no se altera su interfaz. No se exponen `PUT`, `PATCH` ni `DELETE` sobre entradas de línea temporal (inmutabilidad).

**Request de transición** (`StatusTransitionRequest`):

```json
{
  "target_status": "resuelto",
  "resolution": "Se reinició el servicio y se verificó el acceso.",
  "expected_updated_at": "2026-11-02T10:15:30.123456+00:00",
  "request_id": "6f1c2a7e-9b3d-4f4e-8a1b-2c3d4e5f6a7b"
}
```

- `target_status`: obligatorio, enum `TicketStatus`.
- `resolution`: obligatorio solo si `target_status == "resuelto"`; en el resto debe omitirse o ser `null`.
- `expected_updated_at`: obligatorio; valor `updated_at` recibido en la última lectura. Normalizado a UTC.
- `request_id`: obligatorio; UUID generado por el cliente para deduplicar reintentos y correlacionar la operación.

**Response de transición** (`StatusTransitionResponse`):

```json
{
  "changed": true,
  "message": null,
  "ticket": {
    "id": "…",
    "number": "TCK-000123",
    "title": "No puedo acceder al correo",
    "status": "resuelto",
    "status_label": "Resuelto",
    "assignee_id": "…",
    "creator_id": "…",
    "finalized_at": "2026-11-02T10:16:00.000000+00:00",
    "closed_at": null,
    "updated_at": "2026-11-02T10:16:00.000000+00:00",
    "allowed_transitions": [
      { "value": "en_progreso", "label": "En progreso" },
      { "value": "cerrado", "label": "Cerrado" }
    ]
  },
  "timeline_entries": [
    {
      "id": "…",
      "type": "status_change",
      "from_status": "en_progreso",
      "to_status": "resuelto",
      "body": null,
      "is_internal": false,
      "author": { "id": "…", "name": "Técnica A", "role": "tecnico" },
      "created_at": "2026-11-02T10:16:00.000000+00:00"
    },
    {
      "id": "…",
      "type": "resolution",
      "from_status": null,
      "to_status": "resuelto",
      "body": "Se reinició el servicio y se verificó el acceso.",
      "is_internal": false,
      "author": { "id": "…", "name": "Técnica A", "role": "tecnico" },
      "created_at": "2026-11-02T10:16:00.000000+00:00"
    }
  ]
}
```

Si `changed = false`, `timeline_entries` es `[]`. Un no-op por mismo estado usa el mensaje «El ticket ya se encuentra en ese estado.». Si se reproduce un `request_id` ya aplicado con el mismo contenido, `message` contiene «Esta transición ya se aplicó con el identificador de solicitud indicado.». Un replay idempotente devuelve siempre `changed=false`, `timeline_entries=[]` y ese mensaje; no reemite las entradas creadas por el primer envío. Si el `request_id` se reutiliza con otro destino, resolución o autor, se devuelve `409 request_id_reused` sin escribir.

#### 1.5. Catálogo de errores

Formato heredado de `app/core/errors.py`: `{"detail": {"code": "...", "message": "..."}}`.

| HTTP | `code` | Mensaje (es-ES) |
|---|---|---|
| 401 | `not_authenticated` | «La sesión no es válida o ha caducado.» |
| 403 | `forbidden` | «No tienes permiso para modificar este ticket.» |
| 403 | `not_ticket_assignee` | «Este ticket ya no está asignado a ti.» |
| 404 | `ticket_not_found` | «No se ha encontrado el ticket.» |
| 409 | `invalid_transition` | «No puedes pasar de {origen} a {destino}. Estados disponibles: {lista}.» |
| 409 | `ticket_closed` | «El ticket está cerrado y no admite cambios de estado.» |
| 409 | `stale_ticket` | «El ticket ha sido modificado por otra persona. Actualiza la información e inténtalo de nuevo.» |
| 409 | `request_id_reused` | «La solicitud ya se utilizó con otros datos. Genera una nueva solicitud e inténtalo de nuevo.» |
| 422 | `invalid_request` | «La solicitud no es válida. Revisa los datos e inténtalo de nuevo.» |
| 422 | `resolution_required` | «Indica la descripción de la solución para marcar el ticket como Resuelto.» |
| 422 | `resolution_too_long` | «La descripción de la solución no puede superar los 5.000 caracteres.» |
| 422 | `resolution_not_allowed` | «La descripción de la solución solo se indica al marcar el ticket como Resuelto.» |
| 422 | `comment_required` | «El comentario interno no puede estar vacío.» |
| 422 | `comment_too_long` | «El comentario interno no puede superar los 5.000 caracteres.» |
| 500 | `internal_error` | «No se pudo guardar el cambio. El ticket no se ha modificado. Inténtalo de nuevo.» |

#### 1.6. Permisos

La lectura y la escritura usan dependencias distintas:

- **Lectura** (`GET /workflow`, `GET /timeline`): `get_current_user` + `can_read_ticket(user, ticket)`. `can_read_ticket` es verdadero para el usuario creador y para los roles `tecnico`, `supervisor` y `admin`; para cualquier otro usuario se devuelve `404 ticket_not_found` sin revelar la existencia. No se usa `require_technician`, porque el creador y los técnicos no asignados deben poder consultar la proyección pública. `can_read_ticket(user, ticket)` se implementa en `app/services/ticket_timeline.py` y el router la invoca desde el helper `_readable_ticket(session, ticket_id, user)` en `GET /workflow` y `GET /timeline`; ese helper devuelve `404 ticket_not_found` para usuarios sin acceso.
- **Escritura** (`POST /status-transitions`, `POST /internal-comments`): el router usa `get_current_user` y delega rol y asignación en `_ensure_writer(user, ticket)` de `ticket_workflow.py`; así la autorización vive en la capa de servicios y no se duplica. Orden de evaluación: (1) `401 not_authenticated` (dependencia); (2) `404 ticket_not_found` (ticket inexistente, antes de revelar roles); (3) rol distinto de `tecnico` —incluidos `supervisor`, `admin` y `usuario`— ⇒ `403 forbidden`; (4) `tecnico` no asignado ⇒ `403 not_ticket_assignee`; (5) validaciones de payload del servicio. `_ensure_writer` exige rol `tecnico` **y** asignación al ticket: un técnico no asignado recibe `403 not_ticket_assignee`; `supervisor`/`admin`/`usuario` reciben `403 forbidden` y solo pueden leer.
- **Comentarios internos**: solo el técnico asignado puede crear (`can_comment_internally`). Supervisores y administradores reciben `403 forbidden` aunque puedan ver la timeline interna; un técnico no asignado recibe `403 not_ticket_assignee`. Ningún rechazo escribe en `ticket_timeline_entries`.
- **Capacidades**: `viewer_capabilities(user, ticket)` calcula:
  - `can_view_internal = (user.id == ticket.assignee_id) or role in (supervisor, admin)`.
  - `can_change_status = (user.id == ticket.assignee_id) and ticket.status != cerrado and allowed_transitions(ticket.status) no vacío`.
  - `can_comment_internally = (user.id == ticket.assignee_id)` (incluido `cerrado`).
- `allowed_transitions` del snapshot se rellena solo si `can_change_status` es verdadero; en el resto es `[]`. Así el creador, el técnico no asignado y el supervisor no reciben acciones que no pueden ejecutar.
- El usuario creador solo accede a la proyección pública (`status_change` y `resolution`). Supervisores y administradores leen la proyección interna, pero no ejecutan comandos en esta historia (RN-07).

#### 1.7. Contrato de integración con HU-03 (RF-005)

HU-03 no usa el endpoint público. Invoca la función interna `apply_user_response_transition(...)` de `ticket_workflow.py` dentro de la misma transacción en la que registra la respuesta del creador:

- **Precondiciones**: `ticket.status == pendiente_usuario`, `actor_id == ticket.creator_id`, `request_id` obligatorio (identificador estable del evento de respuesta) y `expected_updated_at` de la lectura de HU-03.
- **Efectos**: bloqueo `FOR UPDATE`, validación de la matriz, `tickets.status = en_progreso`, limpieza de `finalized_at`/`closed_at`, inserción de `status_change` con `author_id = creator_id`, `from_status = pendiente_usuario`, `to_status = en_progreso`, `event_order = 0`, `is_internal = false`, `body = NULL`.
- **Transacción**: la función no hace `commit()` ni `rollback()`; participa en la sesión del llamador. HU-03 confirma la respuesta y la transición de forma atómica.
- **Idempotencia**: mismo `request_id` ⇒ sin escritura y resultado `changed=false`; reutilización con otro contenido ⇒ `409 request_id_reused`. Usa los helpers de idempotencia del servicio (§1.2); no duplica la comprobación.
- **Errores**: `409 invalid_transition`, `409 stale_ticket`, `403 forbidden`; HU-03 los traduce a su propio contrato.
- **Sin ruta pública**: el endpoint `POST /status-transitions` sigue exigiendo que el actor sea el técnico asignado.

---

### 2. Persistencia de la resolución

#### 2.1. Decisión: entrada estructurada en la línea temporal

**No se añade `tickets.resolution`.** La resolución se guarda como una fila de `ticket_timeline_entries` con:

- `event_type = "resolution"`
- `to_status = "resuelto"`
- `body = <descripción normalizada>`
- `is_internal = false`
- `author_id`, `created_at`, `request_id`

Ventajas frente a un campo único en `tickets`:

1. **Histórico completo**: al reabrir «Resuelto» → «En progreso» y volver a resolver, se conservan todas las resoluciones como entradas independientes (RN-05, RF-014).
2. **Coherencia con la especificación**: la entidad «Resolución» ya se define como vinculada a una entrada de la línea temporal.
3. **Modelo base intacto**: `tickets` mantiene sus columnas y restricciones; solo se añade una tabla append-only.
4. **Inmutabilidad natural**: no hay ruta de actualización ni borrado; cada resolución es un hecho histórico.
5. **Trazabilidad uniforme**: cambios de estado, resoluciones y comentarios internos comparten el mismo mecanismo de ordenación, autoría y visibilidad.

**Alternativa rechazada**: columna `resolution` en `tickets`. Se descarta porque sobrescribiría la resolución anterior al reabrir, obligaría a añadir lógica de versionado y rompería la separación entre estado actual e histórico.

#### 2.2. Normalización y validación del texto

- `raw = payload.resolution` (puede ser `None`).
- `body = raw.strip()` si `raw is not None`; se eliminan espacios, tabuladores y saltos de línea al inicio y al final.
- Válido si `1 <= len(body) <= 5000`; se rechaza si `body` queda vacío o si el texto original supera 5.000 caracteres tras `strip()`.
- El texto se guarda **ya normalizado** para que la UI y la base de datos coincidan.
- No se permite HTML enriquecido; se renderiza como texto plano (Vue interpola por defecto, sin `v-html`).

#### 2.3. Efectos en `tickets`

| Transición | `status` | `finalized_at` | `closed_at` | `updated_at` |
|---|---|---|---|---|
| → `en_progreso` desde `abierto`/`pendiente_usuario` | `en_progreso` | sin cambios (`NULL`) | sin cambios (`NULL`) | `now` |
| → `pendiente_usuario` | `pendiente_usuario` | `NULL` | `NULL` | `now` |
| → `resuelto` | `resuelto` | `now` | `NULL` | `now` |
| → `cerrado` desde `resuelto` | `cerrado` | se conserva | `now` | `now` |
| `resuelto` → `en_progreso` (reapertura) | `en_progreso` | `NULL` | `NULL` | `now` |

Esto respeta la restricción existente `ck_tickets_finalized_at`: `status IN ('resuelto','cerrado') ⇔ finalized_at IS NOT NULL`. La cola de trabajo (`FINAL_STATUSES`, `classify_sla`) sigue funcionando sin cambios: al resolver/cerrar el ticket sale de activos; al reabrir vuelve a activos.

#### 2.4. Esquema de la tabla nueva

Detalle completo en [data-model.md](./data-model.md). Resumen:

```text
ticket_timeline_entries
├── id                UUID PK
├── ticket_id         UUID FK tickets.id ON DELETE CASCADE, NOT NULL
├── event_type        timeline_event_type NOT NULL  (status_change | resolution | internal_comment)
├── from_status       ticket_status NULL
├── to_status         ticket_status NULL
├── body              TEXT NULL
├── is_internal       BOOLEAN NOT NULL DEFAULT false
├── author_id         UUID FK users.id NOT NULL
├── created_at        TIMESTAMPTZ NOT NULL
├── event_order       SMALLINT NOT NULL DEFAULT 0
└── request_id        UUID NOT NULL
```

Restricciones:

- `status_change`: `from_status` y `to_status` no nulos y distintos; `body IS NULL`; `is_internal = false`.
- `resolution`: `to_status = 'resuelto'`; `body IS NOT NULL`; `is_internal = false`.
- `internal_comment`: `body IS NOT NULL`; `is_internal = true`; `from_status` y `to_status` nulos.
- `body IS NULL OR length(body) BETWEEN 1 AND 5000` (la migración PostgreSQL usa `char_length`; ambas expresiones son equivalentes y SQLAlchemy traduce `length` en SQLite).
- `UNIQUE (ticket_id, request_id, event_type)` (deduplicación; `request_id` es obligatorio).
- Índices: `(ticket_id, created_at)`, `(ticket_id, is_internal)`, `(author_id)`.

`event_order` garantiza orden determinista cuando un cambio de estado y su resolución comparten el mismo `created_at`: `status_change = 0`, `resolution = 1`, `internal_comment = 0`. La lectura ordena por `created_at ASC, event_order ASC, id ASC`. Cada comando asigna un único `now` (UTC, microsegundos) a `tickets.updated_at` y a todas las entradas que crea, de modo que las de un mismo envío comparten `created_at` y se ordenan por `event_order`; una reapertura crea un nuevo `status_change` con un `created_at` posterior y no reescribe las resoluciones anteriores.

#### 2.5. Migración

`backend/alembic/versions/0003_ticket_timeline.py`:

- `revision = "0003_ticket_timeline"`, `down_revision = "0002_work_queue"`.
- Crea el tipo `timeline_event_type` (PostgreSQL) y la tabla con sus restricciones e índices.
- No modifica `tickets`, `users`, `priorities` ni `categories`.
- `downgrade()` elimina tabla, índices y tipo; es seguro porque no hay datos previos que dependan de ella.
- En SQLite (pruebas) `Base.metadata.create_all()` crea la tabla equivalente; la migración no se ejecuta en ese entorno.

---

### 3. Componentes de interfaz (Frontend / Vue 3 + Tailwind)

#### 3.1. Árbol de componentes

```text
TicketDetailPage.vue                     (ruta /tickets/:id; integra el panel)
└── TicketWorkflowPanel.vue              (orquestador; carga, muta y refresca)
    ├── TicketStatusSelector.vue         (solo estados permitidos)
    ├── ResolutionForm.vue               (visible si destino = resuelto)
    ├── InternalCommentForm.vue          (siempre disponible para el asignado)
    └── TicketTimeline.vue               (entradas públicas e internas según rol)
```

#### 3.2. `TicketWorkflowPanel.vue` — orquestador

**Responsabilidad**: cargar `workflow` y `timeline`, mantener el estado de edición, enviar comandos y refrescar tras éxito o conflicto.

**Estado compartido (Pinia)**: `frontend/src/stores/ticketDetail.ts` centraliza los datos del servidor y las mutaciones para que el panel no mezcle estado de servidor con estado de formulario:

```text
ticket, timeline, pagination          // datos del servidor
canChangeStatus, canComment, canSeeInternal
loading, timelineLoading, submitting
error, errorCode, notice
resolutionText, commentText           // textos conservados entre reintentos
loadWorkflow(), loadTimeline(), refresh(), transitionStatus(), addComment(), reset()
```

**Estado local del panel**: `selectedTarget`, `resolutionError`, `commentError`, `requestId`, `lastRequestSignature`, `commentRequestId` y `lastCommentSignature`. El `expected_updated_at` se toma siempre de `ticket.updated_at`; no se duplica en el panel.

- `request_id` se genera con `crypto.randomUUID()` al iniciar cada envío de transición; se conserva solo mientras no cambien destino ni resolución; se descarta tras éxito, no-op, cambio de contenido o cualquier reintento con datos distintos.

**Flujo de carga**:

1. `GET /tickets/{id}/workflow` → `ticket`, `allowed_transitions`, `can_change_status`, `can_comment_internally` y `can_view_internal`; se copian a `canChangeStatus`, `canComment` y `canSeeInternal`.
2. `GET /tickets/{id}/timeline?page=1&page_size=50` → entradas visibles; el panel no decide visibilidad, solo pasa `canSeeInternal` a `TicketTimeline` como defensa de presentación.
3. Si falla, muestra un mensaje en español y un botón «Reintentar».

**Flujo de envío de estado**:

1. Valida en cliente: destino seleccionado y, si es `resuelto`, resolución no vacía tras `trim()` y ≤ 5.000.
2. Deshabilita el botón (`submitting = true`) para bloquear el doble clic.
3. `POST /tickets/{id}/status-transitions` con `target_status`, `expected_updated_at` y `request_id`; incluir `resolution` **solo** si `target_status === 'resuelto'`. Enviarla con cualquier otro destino produce `422 resolution_not_allowed` (RF-034), incluso si el destino coincide con el estado actual.
4. En éxito: `applyTransitionTicket` reemplaza `ticket` (incluidos `status`, `allowed_transitions` y `updated_at`) y recalcula `canChangeStatus`; el panel limpia selección y resolución, recarga la línea temporal y anuncia el cambio con `aria-live="polite"`.
5. En `409 stale_ticket`: muestra el aviso de conflicto, recarga `workflow` y `timeline`, conserva el texto de resolución para que el técnico no lo pierda y permite reintentar.
6. En `409 invalid_transition` / `ticket_closed`: recarga el estado y muestra el mensaje del backend.
7. En `422`: muestra el error asociado al campo (resolución) o al formulario.
8. En error de red/500: muestra «No se pudo guardar el cambio. El ticket no se ha modificado. Inténtalo de nuevo.».

**Plantilla (esquema)**:

```vue
<section class="rounded-lg border border-slate-200 bg-white p-4 shadow-sm sm:p-6">
  <header class="flex flex-wrap items-center justify-between gap-2">
    <h2 class="text-lg font-semibold text-slate-900">Estado del ticket</h2>
    <span class="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-800">
      {{ ticket.status_label }}
    </span>
  </header>

  <p v-if="ticket.status === 'cerrado'" class="mt-3 text-sm text-slate-600" role="status">
    El ticket está cerrado y no admite cambios de estado.
  </p>

  <TicketStatusSelector
    v-else-if="canChangeStatus"
    :current-status="ticket.status"
    :options="ticket.allowed_transitions"
    :disabled="submitting"
    @select="onSelectTarget"
  />

  <p v-else class="mt-3 text-sm text-slate-600" role="status">
    No tienes permisos para cambiar el estado de este ticket.
  </p>

  <ResolutionForm
    v-if="canChangeStatus && selectedTarget === 'resuelto'"
    v-model="resolutionText"
    :disabled="submitting"
    :error="resolutionError"
  />

  <div v-if="canChangeStatus" class="mt-4 flex justify-end gap-2">
    <button
      type="button"
      class="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white
             hover:bg-slate-700 focus:outline-none focus-visible:ring-2
             focus-visible:ring-slate-900 disabled:cursor-not-allowed disabled:opacity-50"
      :disabled="!canSubmit"
      @click="submitTransition"
    >
      {{ submitting ? 'Guardando…' : 'Guardar cambio' }}
    </button>
  </div>

  <p v-if="error" class="mt-3 text-sm text-red-700" role="alert">{{ error }}</p>
  <p v-if="notice" class="mt-3 text-sm text-emerald-700" role="status">{{ notice }}</p>

  <InternalCommentForm
    v-if="canComment"
    v-model="commentText"
    :disabled="submitting"
    :error="commentError"
    @submit="submitInternalComment"
  />

  <TicketTimeline :entries="timeline" :can-see-internal="canSeeInternal" class="mt-6" />
</section>
```

El selector y el botón de guardado se controlan con `canChangeStatus`, no solo con `ticket.status === 'cerrado'`. Un ticket cerrado muestra el aviso de cierre; un usuario sin permiso de escritura muestra el aviso de solo lectura. El formulario de comentario se controla con `canComment`, que puede ser `true` en un ticket cerrado.

#### 3.3. `TicketStatusSelector.vue` — selector de estados

**Props**:

```ts
defineProps<{
  currentStatus: TicketStatus
  options: StatusOption[]        // calculado en servidor
  disabled?: boolean
}>()
```

**Emits**: `select(target: TicketStatus)`.

**Comportamiento**:

- Renderiza un `<fieldset>` con `<legend class="…">Nuevo estado</legend>` y un grupo de radios/segmentos con los `options` recibidos. **Nunca** muestra estados no permitidos.
- Si `options.length === 0` (ticket cerrado), muestra un texto informativo y no renderiza controles.
- El estado actual se muestra como referencia, pero no es seleccionable.
- Navegación completa por teclado (radios nativos), foco visible (`focus-visible:ring-2`), `aria-describedby` con el texto de ayuda.
- Estilos Tailwind coherentes con la cola de trabajo: `rounded-md border border-slate-300 px-3 py-2 text-sm`, estado seleccionado `border-slate-900 bg-slate-900 text-white`, hover `bg-slate-50`.
- No contiene la matriz de transiciones: si el backend devuelve una lista vacía, la UI se adapta.

#### 3.4. `ResolutionForm.vue` — descripción obligatoria

**Props**:

```ts
defineProps<{
  modelValue: string
  disabled?: boolean
  error?: string | null
  maxLength?: number          // 5000 por defecto
}>()
```

**Emits**: `update:modelValue`.

**Comportamiento**:

- `<textarea>` con `:maxlength="maxLength"`, `rows="5"`, `aria-required="true"`, `:aria-invalid="Boolean(error)"` y `aria-describedby` apuntando al contador y al error.
- Etiqueta: «Descripción de la solución».
- Texto de ayuda: «Obligatoria para marcar el ticket como Resuelto. No podrás editarla después; si la solución cambia, reabre el ticket y documenta una nueva.»
- Contador visible: `{{ trimmedLength }} / {{ maxLength }}`; se calcula con `modelValue.trim().length`.
- Error inline en rojo (`text-red-700`) con `role="alert"` cuando `error`.
- Si el usuario escribe solo espacios, el contador muestra `0` y el formulario padre bloquea el envío.
- El texto no se pierde si el envío falla.

**Regla de bloqueo en el padre** (copia de seguridad de UX; el backend siempre revalida):

```ts
const resolutionIsValid = computed(() =>
  selectedTarget.value !== 'resuelto' ||
  resolutionText.value.trim().length > 0
)

const canSubmit = computed(() =>
  !submitting.value &&
  selectedTarget.value !== null &&
  resolutionIsValid.value &&
  resolutionText.value.trim().length <= 5000
)
```

El botón «Guardar cambio» queda `disabled` cuando `canSubmit === false`, por lo que **es imposible enviar «Resuelto» sin texto**. Además, el `submit` del formulario vuelve a comprobar la regla antes de llamar a la API.

#### 3.5. `InternalCommentForm.vue` — comentarios internos

**Props**: `modelValue: string`, `disabled?: boolean`, `error?: string | null`.
**Emits**: `update:modelValue`, `submit`.

**Comportamiento**:

- `<textarea>` con etiqueta «Comentario interno», ayuda «Solo visible para el técnico asignado, supervisores y administradores.»
- Contador `0 / 5000`; valida no vacío tras `trim()` y ≤ 5.000.
- Botón «Añadir comentario interno» deshabilitado si no es válido o si hay un envío en curso.
- Visible también cuando el ticket está «Cerrado» (RN-06/RF-021).
- Genera un `request_id` estable (`crypto.randomUUID()`) al iniciar el envío; lo reutiliza solo para reintentos con el mismo texto y lo regenera si el usuario edita el comentario o tras un alta correcta. Un `request_id` reutilizado con otro `body` devuelve `409 request_id_reused` y no escribe.
- No cambia el estado del ticket; tras éxito, el padre recarga la línea temporal.

#### 3.6. `TicketTimeline.vue` — línea temporal

**Props**:

```ts
defineProps<{
  entries: TimelineEntry[]
  canSeeInternal: boolean
  loading?: boolean
}>()
```

**Comportamiento**:

- Renderiza en orden cronológico recibido (el backend ya ordena).
- Cada entrada muestra tipo, autor, fecha/hora y contenido:
  - `status_change`: «{Autor} cambió el estado de {origen} a {destino}».
  - `resolution`: tarjeta destacada «Resolución» con el texto completo (texto plano, sin `v-html`).
  - `internal_comment`: tarjeta con borde ámbar y etiqueta «Interno»; solo se renderiza si `canSeeInternal`.
- Usa `Intl.DateTimeFormat('es-ES', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'Europe/Madrid' })`.
- Estados vacío y carga con `role="status"`.
- No muestra botones de edición ni borrado (inmutabilidad).
- Colores de tipo: estado `bg-slate-100 text-slate-700`, resolución `bg-emerald-50 text-emerald-800`, interno `bg-amber-50 text-amber-800`.

#### 3.7. Servicio y tipos TypeScript

`frontend/src/services/ticketWorkflow.ts`:

```ts
export async function getWorkflow(ticketId: string): Promise<WorkflowResponse>
export async function transitionStatus(
  ticketId: string,
  payload: StatusTransitionRequest,
): Promise<StatusTransitionResponse>
export async function addInternalComment(
  ticketId: string,
  payload: InternalCommentRequest,
): Promise<InternalCommentResponse>
export async function getTimeline(
  ticketId: string,
  page = 1,
  pageSize = 50,
): Promise<TimelineResponse>
```

Reutiliza el cliente HTTP existente (GET/POST, `Authorization: Bearer`, `credentials: 'omit'`). Se amplía el mapeo de errores del cliente para que `409` se exponga como `ApiClientError.kind === 'conflict'` conservando `status` y `code`; el resto del contrato no cambia.

`frontend/src/types/ticketWorkflow.ts` define `TicketStatus`, `StatusOption`, `TimelineEntryType`, `TimelineEntry`, `TicketWorkflowSnapshot`, `StatusTransitionRequest`, `StatusTransitionResponse`, `InternalCommentRequest`, `InternalCommentResponse`, `TimelineResponse`, `WorkflowResponse` y `ApiErrorBody`.

#### 3.8. Integración con el detalle del ticket

- La ruta `/tickets/:id` apunta a `TicketDetailPage.vue`, que actúa como contenedor de HU-05 y monta `<TicketWorkflowPanel :ticket-id="id" />`; mantiene el enlace «Volver a la cola de trabajo». El detalle completo de HU-06 puede componerse dentro de este contenedor sin cambiar la ruta ni el panel.
- La cola de trabajo (`WorkQueuePage`) no cambia; al volver a ella tras un cambio, el estado y la posición se recalculan con los datos existentes.

#### 3.9. Accesibilidad y responsive

- Grupos de radios con `fieldset`/`legend`; botones con texto visible; estados de error con `role="alert"` y `aria-live`.
- Foco visible en todos los controles (`focus-visible:ring-2`).
- Contraste AA con la paleta `slate`/`emerald`/`amber`/`red` usada en el proyecto.
- Layout de una columna en móvil/tablet y dos columnas (`lg:grid-cols-[minmax(0,1fr)_22rem]`) en desktop si el detalle lo permite; el panel funciona igual en una sola columna.
- Sin dependencia de color exclusivamente: las etiquetas textuales («Resolución», «Interno», «Cerrado») acompañan a los colores.

---

### 4. Trazabilidad y coherencia con la arquitectura existente

#### 4.1. Lo que **no** cambia

- **Stack**: PostgreSQL + FastAPI + SQLAlchemy 2.0 + Alembic + Vue 3 + Tailwind + Pinia + Vue Router.
- **Modelo base**: `tickets`, `users`, `priorities`, `categories` conservan sus columnas y restricciones. No se añade `resolution`, `version` ni `lock_version` a `tickets`.
- **Enums de estado**: `TicketStatus` mantiene exactamente los cinco valores y `FINAL_STATUSES = (resuelto, cerrado)`.
- **Contrato de errores**: `{"detail":{"code","message"}}` y mensajes en español.
- **Autenticación**: JWT Bearer desde `Authorization`. Las escrituras usan `get_current_user` y `_ensure_writer`: el rol `tecnico` supera la puerta de rol y después se exige asignación al ticket, de modo que `supervisor`/`admin`/`usuario` reciben `403 forbidden` y el técnico no asignado `403 not_ticket_assignee`. Las lecturas dependen de `can_read_ticket`. `require_technician` se mantiene para la cola de trabajo y no se reutiliza en HU-05.
- **Cola de trabajo**: sigue leyendo `status`, `finalized_at` y `sla_deadline`; no requiere cambios.

#### 4.2. Lo que se añade de forma aditiva

- Enum `TimelineEventType` en `app/models/enums.py`.
- Modelo `TicketTimelineEntry` en `app/models/timeline.py` y su export en `app/models/__init__.py`.
- Tabla `ticket_timeline_entries` + índices + restricciones (migración `0003`).
- Servicios `ticket_state_machine.py`, `ticket_workflow.py`, `ticket_timeline.py`; este último expone `viewer_capabilities(user, ticket)` desde la fase Foundational y lo reutilizan `get_workflow` y la consulta de línea temporal.
- Handler de `RequestValidationError` en `app/core/errors.py` (registrado en `app/main.py`) para devolver `422 invalid_request`.
- Esquemas `ticket_workflow.py`.
- Router `tickets.py` incluido en `app/api/v1/router.py`.
- Componentes Vue y su servicio/tipos/store.
- Pruebas unitarias, de integración, de contrato y de componentes.

#### 4.3. Invariantes de coherencia

1. **Estado ↔ línea temporal**: el último `status_change` de un ticket coincide siempre con `tickets.status` (RF-033). Se comprueba en pruebas tras cada transición y tras reaperturas.
2. **Resuelto ⇒ resolución (post-migración)**: toda transición `status_change` con `to_status = 'resuelto'` ejecutada por HU-05 debe tener su entrada `resolution` no vacía con el mismo `request_id` (RN-03/RF-008). Los tickets `resuelto`/`cerrado` anteriores a `0003_ticket_timeline` no se modifican retroactivamente: se listan como legado en la auditoría y quedan excluidos de la aserción. La migración no crea resoluciones sintéticas.
3. **`finalized_at` ↔ estado final**: se respeta `ck_tickets_finalized_at`; resolver/cerrar lo rellenan, reabrir lo limpia.
4. **`closed_at`**: solo no nulo cuando `status = cerrado`.
5. **Inmutabilidad**: no hay endpoints de actualización/borrado de entradas; las resoluciones y comentarios son append-only.
6. **Visibilidad**: el filtro `is_internal` se aplica en la consulta SQL, no en el cliente.
7. **Idempotencia**: mismo estado destino ⇒ sin escritura; `request_id` repetido con el mismo contenido ⇒ sin duplicado; `request_id` reutilizado con otro contenido ⇒ `409 request_id_reused`.
8. **Concurrencia**: `expected_updated_at` desactualizado ⇒ `409 stale_ticket` y cero escrituras.

#### 4.4. Observabilidad

- `logging` estándar (ya configurado en `app/main.py`) con un `INFO` por comando exitoso: `ticket_id`, `actor_id`, `from_status`, `to_status`, `changed`, `request_id`, `duration_ms`. **No** se registra el cuerpo de la resolución ni del comentario (privacidad).
- `WARNING` en transiciones rechazadas con `code` y `ticket_id`; `ERROR` con `logger.exception` en fallos inesperados.
- No se añaden métricas ni trazas externas (fuera de alcance).

#### 4.5. Compatibilidad y despliegue

- La migración es aditiva y reversible; puede desplegarse antes del código (la tabla no la usa el código antiguo).
- El frontend antiguo sigue funcionando: no se modifican endpoints existentes.
- El nuevo endpoint requiere `expected_updated_at`; los clientes que no lo envíen reciben `422` explícito, no un cambio silencioso.
- En producción, `AUTH_DEV_STUB_ENABLED` debe permanecer desactivado; el stub de login es solo para desarrollo/pruebas.

## Complexity Tracking

> No hay violaciones de la Constitución ni del stack. No se rellena.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |

## Phase 2 Preview (not created by this command)

`/speckit.tasks` derivará tareas de:

1. Migración y modelo de línea temporal.
2. Máquina de estados pura + pruebas de matriz.
3. Servicio transaccional de cambio de estado + resolución.
4. Servicio de comentarios internos + idempotencia.
5. Endpoints, esquemas y router.
6. Lectura de línea temporal con visibilidad.
7. Pruebas de integración y contrato.
8. Componentes Vue, servicio, tipos y store.
9. Pruebas de componentes y accesibilidad.
10. Quickstart y verificación end-to-end.
