# Implementation Plan: Responder a la petición de información del técnico (HU-03)

**Branch**: `hu-03-responder-tecnico` | **Date**: 2026-11-13 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/003-responder-peticion-tecnico/spec.md`

**Estado**: plan de Fase 0 y Fase 1. Los artefactos `research.md`, `data-model.md`, `contracts/` y `quickstart.md` acompañan a este documento.

## Summary

HU-03 completa el intercambio de información entre el usuario creador y el técnico asignado. El técnico solicita información concreta desde el panel de cambio de estado ya existente; el ticket pasa a «Pendiente de usuario» y la petición queda registrada en la línea temporal pública. El usuario ve el aviso contextual en «Mis tickets» y en la vista del ticket, y responde desde esa misma vista. Al responder, el ticket vuelve automáticamente a «En progreso», la respuesta se registra en la línea temporal y el ticket reaparece en la cola de trabajo del técnico.

**Enfoque técnico**: reutilizar la línea temporal append-only de HU-05 como única fuente de trazabilidad. Se añaden dos tipos de entrada (`information_request` y `user_response`) y una relación `reply_to_id` para vincular la respuesta con su petición. No se crea una tabla nueva ni se añaden columnas a `tickets`. El recordatorio de 48 horas se calcula en servidor a partir del último paso a «Pendiente de usuario», sin almacenar estado de notificación. La UI se integra en `TicketWorkflowPanel`, `TicketTimeline` y `MyTicketsPage`, reutilizando los componentes y la paleta existentes.

**Decisiones clave**:

| Punto | Decisión |
|---|---|
| Persistencia de petición y respuesta | Entradas públicas e inmutables en `ticket_timeline_entries`, no una tabla nueva |
| Vínculo petición-respuesta | Columna `reply_to_id` autorreferente en la línea temporal |
| Recordatorio 48 h | Derivado en servidor desde el último cambio a «Pendiente de usuario»; sin persistencia de avisos |
| Solicitud del técnico | Comando `POST /information-requests`, integrado en el selector de estado |
| Respuesta del usuario | Comando `POST /information-responses`, solo para el creador y solo en «Pendiente de usuario» |
| Avisos | Contextuales en la lista y en el ticket; sin campana, correo ni notificaciones adicionales |
| Compatibilidad | La transición genérica de HU-05 sigue vigente; los tickets pendientes sin petición son respondibles |

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript + Vue 3 (frontend)

**Primary Dependencies**: FastAPI 0.115.6, SQLAlchemy 2.0.36, Pydantic 2.10.4, Alembic 1.14.0, psycopg; Vue 3, Vite, Tailwind CSS, Pinia, Vue Router; Vitest + `@vue/test-utils`

**Storage**: PostgreSQL en desarrollo/producción; SQLite en pruebas locales mediante la abstracción existente de `app/db/session.py`. Los tipos nuevos son genéricos de SQLAlchemy y compatibles con ambos motores.

**Testing**: `pytest` + `fastapi.testclient`/`httpx` en backend; `vitest` + `@vue/test-utils` en frontend.

**Target Platform**: servicio web Linux + interfaz web responsive (desktop/tablet)

**Project Type**: aplicación web con backend y frontend separados

**Performance Goals**:
- Solicitud de información y respuesta: p95 < 300 ms en servidor (sin contar red).
- Vista del ticket y lista «Mis tickets»: < 2 s percibidos.
- Cuerpos de petición y respuesta: 1–5.000 caracteres.
- Lista de tickets sin consultas N+1: una consulta de tickets y una consulta agregada de peticiones abiertas.

**Constraints**:
- Interfaz y mensajes 100 % en español de España (RNF-01).
- Accesibilidad WCAG 2.1 AA (RNF-03) y diseño responsive (RNF-04).
- Autenticación JWT existente; identidad solo desde `Authorization: Bearer`.
- Sin secretos en código ni nuevas tecnologías (RNF-07).
- No se modifican las columnas base de `tickets` ni el flujo de estados de HU-05.
- `master` ya está integrado en esta rama mediante fast-forward a `04e47e5` (HU-01, HU-02, HU-04 y HU-05). Si `master` avanza antes de implementar, repetir la integración y la línea base.

**Scale/Scope**: mesa de ayuda interna; miles de tickets, una petición activa por ticket y ciclos sucesivos poco frecuentes. La línea temporal crece de forma append-only y ya está indexada por ticket y fecha.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitución ratificada: `.specify/memory/constitution.md` (v1.0.0). `CONSTITUTION.md` en la raíz se conserva como resumen de producto; ante conflicto prevalece la constitución ratificada.

| Principio | Resultado | Justificación |
|---|---|---|
| I. Arquitectura por capas y stack fijado | PASS | Los comandos viven en `ticket_workflow.py` y la lectura en `ticket_timeline.py`; se reutilizan FastAPI, SQLAlchemy, Alembic, Vue 3, Pinia y los componentes existentes. No hay tecnologías nuevas. |
| II. Modelo de datos estable y migraciones aditivas | PASS | Se amplía el enum y se añade una columna anulable con FK e índice; no se renombra ni elimina nada. `upgrade`/`downgrade` son verificables y el `downgrade` conserva los valores del enum de forma documentada. |
| III. Seguridad y mínimo privilegio | PASS | La identidad sale solo del JWT; la autorización se aplica en servidor (técnico asignado para solicitar, creador para responder) y los comentarios internos se filtran antes de serializar. |
| IV. Contratos primero y pruebas verificables | PASS | OpenAPI y contrato de componentes preceden a la implementación. Las tareas cubren matriz de estados, permisos, visibilidad, atomicidad, concurrencia, idempotencia, códigos de error y rendimiento. `SC-008` se reformula para ser verificable solo con la app y el quickstart. |
| V. Simplicidad, trazabilidad y experiencia en español | PASS | No se crea tabla ni persistencia de avisos; la línea temporal append-only conserva autor, fecha y estados. Textos en es-ES, fechas en `Europe/Madrid`, accesibilidad WCAG 2.1 AA. |
| Restricciones adicionales | PASS | Se mantiene el formato de error, los comandos POST compatibles con el cliente, el p95 < 300 ms con prueba explícita (T061) y la revisión de accesibilidad. |

**Post-design re-check (Phase 1)**: PASS. El diseño no introduce violaciones; no se requiere `Complexity Tracking`.

## Project Structure

### Documentation (this feature)

```text
specs/003-responder-peticion-tecnico/
├── plan.md                  # Este archivo
├── research.md              # Fase 0: decisiones y alternativas
├── data-model.md            # Fase 1: entidades, invariantes y migración
├── quickstart.md            # Fase 1: validación ejecutable
├── contracts/
│   ├── ticket-information.openapi.yaml   # Contrato HTTP
│   └── frontend-components.md            # Contrato de componentes Vue
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
│       └── 0005_ticket_information.py       # NUEVO: enum, reply_to_id, checks, índice
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── tickets.py                   # MODIFICADO: dos comandos POST
│   │       └── my_tickets.py                # MODIFICADO: flags de respuesta y recordatorio
│   ├── models/
│   │   ├── enums.py                         # MODIFICADO: dos valores de TimelineEventType
│   │   └── timeline.py                      # MODIFICADO: reply_to_id y checks
│   ├── schemas/
│   │   ├── ticket_workflow.py               # MODIFICADO: petición activa y capacidad de responder
│   │   └── my_tickets.py                    # MODIFICADO: awaiting_user_response, reminder
│   ├── services/
│   │   ├── ticket_workflow.py               # MODIFICADO: request_information y respond_to_information
│   │   └── ticket_timeline.py               # MODIFICADO: petición activa y visibilidad pública
│   └── main.py                              # Sin cambios
└── tests/
    ├── unit/
    │   ├── test_information_request_rules.py
    │   └── test_information_response_rules.py
    ├── integration/
    │   ├── test_information_requests.py
    │   ├── test_information_responses.py
    │   ├── test_information_reminder.py
    │   ├── test_information_cycle.py
    │   ├── test_information_concurrency.py
    │   └── test_information_visibility.py
    └── contract/
        ├── test_information_request_contract.py
        ├── test_information_response_contract.py
        └── test_information_traceability_contract.py

frontend/
├── src/
│   ├── components/
│   │   └── tickets/
│   │       ├── InformationRequestForm.vue   # NUEVO: mensaje obligatorio
│   │       ├── InformationResponseForm.vue  # NUEVO: respuesta obligatoria
│   │       ├── TicketWorkflowPanel.vue      # MODIFICADO: integra ambos formularios y avisos
│   │       └── TicketTimeline.vue           # MODIFICADO: petición y respuesta
│   ├── services/
│   │   └── ticketWorkflow.ts                # MODIFICADO: request/response
│   ├── stores/
│   │   └── ticketDetail.ts                  # MODIFICADO: estado y acciones nuevas
│   ├── types/
│   │   ├── ticketWorkflow.ts                # MODIFICADO: tipos de intercambio
│   │   └── myTickets.ts                     # MODIFICADO: flags de aviso
│   └── views/
│       └── MyTicketsPage.vue                # MODIFICADO: badge y recordatorio
└── tests/
    ├── components/
    │   ├── InformationRequestForm.spec.ts
    │   ├── InformationResponseForm.spec.ts
    │   ├── TicketWorkflowPanel.information-request.spec.ts
    │   ├── TicketWorkflowPanel.information-response.spec.ts
    │   └── TicketTimeline.information.spec.ts
    ├── stores/
    │   ├── ticketDetail.request.spec.ts
    │   └── ticketDetail.response.spec.ts
    └── views/
        └── MyTicketsPage.spec.ts
```

**Structure Decision**: se mantiene la arquitectura por capas existente (`api` → `services` → `models`/`db`, con `schemas` para contratos). Los comandos de HU-03 se implementan en `ticket_workflow.py` para reutilizar el bloqueo de fila, la idempotencia, los efectos de estado y la inserción de entradas; la lectura agregada y la visibilidad viven en `ticket_timeline.py`. En frontend se conserva la organización por `components`, `services`, `stores`, `types` y `views`, y no se añaden rutas nuevas: todo ocurre en `/tickets/:id` y en `/mis-tickets`.

Las pruebas de HU-03 conviven con las suites existentes de HU-05. Las nuevas pruebas de componentes, store y ciclo se crean en ficheros separados para evitar conflictos entre historias, pero `frontend/tests/components/TicketWorkflowPanel.spec.ts`, `frontend/tests/components/TicketTimeline.spec.ts` y `frontend/tests/stores/ticketDetail.spec.ts` deben seguir verdes como regresión (T060).

## Phase 0: Outline & Research

**Output**: [research.md](./research.md)

Decisiones resumidas (detalle y alternativas en `research.md`):

- **R1 — Línea temporal como fuente única**: petición y respuesta son entradas append-only, no una tabla paralela.
- **R2 — Vínculo explícito**: `reply_to_id` autorreferente une cada respuesta con su petición concreta sin agrupar visualmente entradas.
- **R3 — Recordatorio derivado**: `reminder_active` se calcula en servidor desde el último paso a «Pendiente de usuario» + 48 h; no se persiste un aviso.
- **R4 — Concurrencia e idempotencia**: `expected_updated_at` + `request_id` reutilizan el patrón de HU-05.
- **R5 — Autorización**: solicitar solo el técnico asignado; responder solo el creador; entradas públicas en servidor.
- **R6 — Compatibilidad**: la transición genérica de HU-05 se conserva y los tickets pendientes sin petición son respondibles con aviso genérico.
- **R7 — UI integrada**: formulario de petición dentro de `TicketWorkflowPanel`; formulario de respuesta en el mismo panel cuando el creador está en «Pendiente de usuario».
- **R8 — Orden determinista**: `event_order = 0` para el cambio de estado y `1` para la petición o respuesta del mismo comando.
- **R9 — Migración aditiva**: `ALTER TYPE ... ADD VALUE` dentro de `autocommit_block()` en PostgreSQL para poder usar los valores en los nuevos `CHECK`; las pruebas SQLite reconstruyen el esquema desde modelos.
- **R10 — Pruebas**: unitarias de reglas, integración de comandos/visibilidad/recordatorio/concurrencia, contrato y componentes.

## Phase 1: Design & Contracts

**Output**: [data-model.md](./data-model.md), [contracts/ticket-information.openapi.yaml](./contracts/ticket-information.openapi.yaml), [contracts/frontend-components.md](./contracts/frontend-components.md), [quickstart.md](./quickstart.md)

---

## Diseño detallado

### 1. Modelo de datos y migración

**Fichero de migración**: `backend/alembic/versions/0005_ticket_information.py`, que depende de `0004_ticket_creation`.

Cambios:

1. Añadir al enum `timeline_event_type` los valores `information_request` y `user_response` dentro de `with op.get_context().autocommit_block():`. Así el valor queda confirmado antes de crear los `CHECK` que lo usan; PostgreSQL no permite usar un valor de enum nuevo en la misma transacción en la que se añade.
2. Añadir a `ticket_timeline_entries` la columna `reply_to_id` (`Uuid`, nullable, FK a `ticket_timeline_entries.id` con `ON DELETE SET NULL`).
3. Añadir los `CHECK` de forma:
   - `information_request`: `from_status IS NULL`, `to_status IS NULL`, `body IS NOT NULL`, `is_internal = false`, `reply_to_id IS NULL`.
   - `user_response`: `from_status IS NULL`, `to_status IS NULL`, `body IS NOT NULL`, `is_internal = false`. No se exige `reply_to_id` para no romper tickets legados.
4. Añadir índice `ix_timeline_reply_to` sobre `reply_to_id`.
5. `downgrade()` elimina índice, `CHECK` y columna; conserva los valores del enum para no recrear el tipo ni destruir datos históricos. Nunca toca `tickets`.

Invariantes:

- Una petición y su respuesta comparten el mismo `ticket_id`; se valida en servicio porque un `CHECK` no puede cruzar filas.
- La petición y la respuesta son públicas (`is_internal = false`).
- Un ticket solo puede tener una petición abierta (sin `user_response` que la referencie) mientras esté «Pendiente de usuario».
- Las entradas son inmutables: solo `INSERT`, sin endpoints de edición o borrado.

### 2. Backend: comandos y reglas

**Servicio**: `backend/app/services/ticket_workflow.py`.

#### 2.1. `request_information(session, ticket_id, current_user, payload)`

1. Bloquear el ticket con `_locked_ticket`; si no existe o el usuario no puede leerlo, `404 ticket_not_found` (no se revela la existencia de tickets ajenos).
2. Verificar rol `tecnico` y que sea el asignado (`403 forbidden` o `403 not_ticket_assignee`).
3. Normalizar `body.strip()` y validar: vacío ⇒ `422 information_request_required`; >5.000 ⇒ `422 information_request_too_long`.
4. Comprobar idempotencia por `request_id` **antes** de validar el estado, para que un reintento tras el éxito devuelva `changed = false`:
   - Replay idéntico (mismo actor, mismo cuerpo y mismo destino pendiente) ⇒ `changed = false`.
   - Reutilización con otros datos o con un comando distinto ⇒ `409 request_id_reused`.
5. Comprobar que no existe una petición activa en el ciclo pendiente actual ⇒ `409 information_request_already_open`.
6. Exigir estado `en_progreso`; si no, `409 invalid_transition`.
7. Validar `expected_updated_at` contra `tickets.updated_at`; si difiere ⇒ `409 stale_ticket`.
8. En una transacción: insertar `status_change` (`en_progreso → pendiente_usuario`, `event_order = 0`) e `information_request` (`body`, `author = técnico`, `event_order = 1`), actualizar el ticket y hacer `commit`.
9. Devolver el snapshot actualizado, las entradas creadas y la referencia de la petición. En un replay, devolver la petición existente sin escribir.

#### 2.2. `respond_to_information(session, ticket_id, current_user, payload)`

1. Bloquear el ticket; si no existe o el usuario no puede leerlo, `404 ticket_not_found`.
2. Exigir que `current_user.id == ticket.creator_id`; si el usuario puede leerlo pero no es el creador (por ejemplo, supervisor), `403 forbidden`.
3. Normalizar `body.strip()` y validar: vacío ⇒ `422 information_response_required`; >5.000 ⇒ `422 information_response_too_long`.
4. Comprobar idempotencia por `request_id` **antes** de validar el estado, para que un reintento tras el éxito devuelva `changed = false`:
   - Replay idéntico (mismo actor, mismo cuerpo y respuesta vinculada) ⇒ `changed = false`.
   - Reutilización con otros datos o con un comando distinto ⇒ `409 request_id_reused`.
5. Exigir estado `pendiente_usuario`; si no, `409 invalid_transition`.
6. Validar `expected_updated_at`; si difiere ⇒ `409 stale_ticket`.
7. Buscar la petición activa del ciclo pendiente actual. Si existe, la respuesta se vincula con `reply_to_id`. Si no existe (ticket legado pendiente, o pendiente por transición genérica), se registra sin vínculo y se admite (RF-020).
8. En una transacción: ejecutar `apply_user_response_transition` (cambio a `en_progreso`, entrada `status_change`, autor = creador), insertar `user_response` (`body`, `author = creador`, `event_order = 1`, `reply_to_id`, mismo `created_at` que el `status_change`) y hacer `commit`.
9. Devolver el snapshot, las entradas creadas y la entrada de respuesta. En un replay, devolver la respuesta existente sin escribir.

**Reutilización**: los comandos viven en el mismo módulo que `change_status` para usar `_locked_ticket`, `_apply_ticket_effects`, `_insert_status_change`, `apply_user_response_transition` y los códigos de error existentes, sin duplicar la lógica transaccional. `_classify_transition_replay` no sirve tal cual para HU-03 porque solo compara `status_change`/`resolution`; se añade `_classify_information_replay`, que consulta todas las entradas del ticket con el `request_id` recibido y compara tipo de comando, actor, cuerpo normalizado y `reply_to_id` (o ausencia de vínculo en legado). Así se detecta también la reutilización entre comandos distintos (por ejemplo, un `request_id` ya usado en un comentario interno o en una transición genérica).

### 3. Backend: lectura, recordatorio y visibilidad

**Servicio**: `backend/app/services/ticket_timeline.py`.

- `get_active_information_request(session, ticket)`: última entrada `information_request` del ciclo pendiente actual (posterior al último paso a `pendiente_usuario`) sin `user_response` que la referencie. Devuelve `None` si el ticket no está pendiente o no hay petición. Así una transición manual de HU-05 no deja una petición «activa» colgada.
- `get_pending_since(session, ticket)`: `created_at` del último `status_change` con `to_status = pendiente_usuario`.
- `reminder_active(ticket, pending_since, now)`: verdadero solo si el ticket sigue «Pendiente de usuario» y `now >= pending_since + 48 h`.
- `viewer_capabilities` se amplía con `can_request_information` (técnico asignado, estado `en_progreso` y sin petición activa) y `can_respond_to_information` (creador y estado `pendiente_usuario`).
- La línea temporal sigue filtrando `is_internal` en servidor. Las entradas nuevas son públicas y se muestran al creador y al personal operativo.

**Proyecciones**:

- `GET /tickets/{id}/workflow` añade al snapshot:
  - `awaiting_user_response: bool`
  - `active_information_request: { id, body, requested_at, requested_by } | null`
  - `reminder_active: bool`
  - `reminder_due_at: datetime | null`
  - capacidades `can_request_information` y `can_respond_to_information`
- `GET /me/tickets` añade a cada resumen:
  - `awaiting_user_response: bool`
  - `response_requested_at: datetime | null`
  - `reminder_active: bool`
  - `reminder_due_at: datetime | null`
- Para evitar N+1, `my_tickets.py` carga los tickets del usuario y, en consultas agregadas por lote, las peticiones abiertas y los últimos pasos a pendiente de esos tickets; luego los cruza en memoria.

### 4. Frontend

**Tipos y cliente** (`types/ticketWorkflow.ts`, `types/myTickets.ts`, `services/ticketWorkflow.ts`):

- Extender solo `TimelineEventType` con `information_request` y `user_response`; `TicketStatus` no cambia.
- Extender `TicketWorkflowSnapshot` y `WorkflowResponse` con los campos de petición activa, aviso y capacidades.
- Añadir `InformationRequestPayload`, `InformationResponsePayload` y sus respuestas.
- Añadir `requestInformation` y `respondToInformation` al cliente HTTP.

**Store** (`stores/ticketDetail.ts`):

- Estado nuevo: `informationRequest`, `canRequestInformation`, `canRespondToInformation`, `awaitingUserResponse`, `reminderActive`, `requestText`, `responseText`.
- Acciones `requestInformation` y `respondToInformation` con el mismo patrón de errores, `notice`, recarga de línea temporal e idempotencia que `transitionStatus`.
- `loadWorkflow` aplica los campos nuevos; `reset` los limpia.
- Mensajes de error nuevos mapeados desde los códigos del backend.

**Componentes**:

- `InformationRequestForm.vue`: `textarea` con etiqueta, ayuda, contador 5.000, error accesible y botón deshabilitado durante el envío. Se muestra en `TicketWorkflowPanel` cuando el destino seleccionado es `pendiente_usuario`.
- `InformationResponseForm.vue`: muestra la petición activa (o aviso genérico si no existe) y un `textarea` de respuesta; valida vacío y longitud; se muestra al creador en «Pendiente de usuario».
- `TicketWorkflowPanel.vue`:
  - Al seleccionar `pendiente_usuario`, renderiza `InformationRequestForm` en lugar de `ResolutionForm`.
  - `canSubmit` exige cuerpo válido si el destino es `pendiente_usuario` o `resuelto`.
  - Si `canRespondToInformation`, muestra un aviso destacado con la petición y `InformationResponseForm`.
  - Si `reminderActive`, muestra el recordatorio contextual con el mismo estilo de aviso ya usado.
- `TicketTimeline.vue`: añade dos `template` con etiquetas «Petición de información» y «Respuesta del usuario», usando los colores existentes (`sky` para petición, `indigo`/`blue` para respuesta) y `whitespace-pre-wrap break-words`.
- `MyTicketsPage.vue`: badge «Esperando tu respuesta» y, si `reminder_active`, texto de recordatorio. Mantiene el enlace `RouterLink` a `/tickets/:id`.

**Accesibilidad**: `fieldset`/`legend`, `aria-describedby` para ayudas y errores, `role="status"`/`aria-live` para avisos y recordatorio, foco en el campo tras error, botón deshabilitado con texto visible.

### 5. Compatibilidad y no regresión

- HU-05 conserva `POST /status-transitions` y su validación. HU-03 añade comandos específicos y no altera la matriz de estados.
- Un ticket «Pendiente de usuario» sin petición previa se puede responder; la UI muestra un aviso genérico.
- La transición manual `pendiente_usuario → en_progreso` sigue disponible para el técnico.
- No se modifican las columnas de `tickets`, las rutas existentes ni los contratos actuales; solo se amplían respuestas con campos nuevos compatibles.
- La línea temporal mantiene el orden `created_at ASC, event_order ASC, id ASC`.

### 6. Pruebas

**Backend**:

- `test_information_request_rules.py` y `test_information_response_rules.py`: longitud, vacío, normalización, decisiones de recordatorio y clasificación de replay.
- `test_information_requests.py`: éxito, rol/asignación, estado, petición abierta duplicada con precedencia sobre `invalid_transition`, idempotencia y atomicidad.
- `test_information_responses.py`: éxito, solo creador, solo pendiente, petición legado, idempotencia y transición automática.
- `test_information_reminder.py`: umbral de 48 h en servidor, ticket respondido y ticket cerrado; el recordatorio no se repite, no crea entradas y no cambia el estado.
- `test_information_cycle.py`: ciclo completo petición → respuesta → cola del técnico y trazabilidad.
- `test_information_concurrency.py`: dos respuestas simultáneas, `stale_ticket` y una sola aplicación contra PostgreSQL.
- `test_information_visibility.py`: petición y respuesta visibles para creador y técnico, comentarios internos ocultos.
- `test_information_request_contract.py`, `test_information_response_contract.py` y `test_information_traceability_contract.py`: endpoints, códigos de error, campos extendidos de `workflow`/`me/tickets`, `reply_to_id` e inmutabilidad.
- `test_ticket_workflow_performance.py` (existente): ampliar con p95 de solicitud, respuesta y proyecciones; verificar <300 ms de servidor y <2 s percibidos.

**Frontend**:

- `InformationRequestForm.spec.ts` e `InformationResponseForm.spec.ts`: validación, límite, error accesible y bloqueo de envío.
- `TicketWorkflowPanel.information-request.spec.ts` e `TicketWorkflowPanel.information-response.spec.ts`: integración de ambos formularios, avisos y recordatorio.
- `TicketTimeline.information.spec.ts`: render de los tipos nuevos con autor y fecha.
- `MyTicketsPage.spec.ts`: badge de espera y recordatorio.
- `ticketDetail.request.spec.ts` y `ticketDetail.response.spec.ts`: acciones, recarga y mensajes de error.
- `TicketWorkflowPanel.spec.ts`, `TicketTimeline.spec.ts` y `ticketDetail.spec.ts` existentes: mantener verdes como regresión (T060).

### 7. Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| `master` avanza durante la implementación | La rama ya integró `master` por fast-forward a `04e47e5`; si avanza de nuevo, repetir la integración y la línea base antes de tocar código. |
| Doble envío o dos pestañas | `request_id` + `expected_updated_at` + bloqueo de fila; pruebas de concurrencia. |
| Tickets pendientes antiguos sin petición | Aviso genérico y respuesta admitida; se cubre con prueba de compatibilidad. |
| Fuga de comentarios internos | Filtro `is_internal` en servidor y prueba de visibilidad; el cliente no recibe filas internas. |
| Crecimiento del módulo `ticket_workflow.py` | Reutilizar helpers existentes; si supera el umbral razonable, extraer primitivas compartidas sin cambiar contratos. |
| Cambios de enum en PostgreSQL | `ALTER TYPE ... ADD VALUE` dentro de `autocommit_block()`; downgrade conserva los valores y pruebas SQLite desde modelos. |
