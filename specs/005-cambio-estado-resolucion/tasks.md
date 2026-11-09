# Tasks: Cambio de estado y documentación de resolución (HU-05)

**Input**: Design documents from `/specs/005-cambio-estado-resolucion/`

**Prerequisites**: [plan.md](./plan.md) (required), [spec.md](./spec.md) (required), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Tests**: El plan enumera explícitamente los ficheros de prueba en `backend/tests/**` y `frontend/tests/components/**`, y la puerta «Pruebas verificables» del `Constitution Check` exige cubrir matriz, atomicidad, concurrencia y visibilidad. Por ello las tareas de prueba se incluyen y se escriben antes de la implementación correspondiente.

**Organization**: tareas agrupadas por historia de usuario para que cada una sea implementable y verificable de forma independiente. US1 y US2 son P1; US3 es P2.

**Revisión 2026-11-08**: tareas sincronizadas con `plan.md` tras la fase de clarify: orden de validación, autorización en la capa de servicios, helpers de idempotencia por tipo de comando, bloqueo `FOR UPDATE` con recarga `populate_existing`, estado Pinia y contratos de UI. Las tareas heredadas de la Práctica 2 (`T001A`, `T001B`, `T001`–`T004`) se mantienen intactas.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: puede ejecutarse en paralelo (ficheros distintos, sin dependencias de tareas incompletas)
- **[Story]**: historia a la que pertenece la tarea (US1, US2, US3)
- Todas las descripciones incluyen la ruta exacta del fichero

## Path Conventions

- Backend: `backend/app/`, `backend/alembic/`, `backend/tests/`
- Frontend: `frontend/src/`, `frontend/tests/`
- Documentación de la feature: `specs/005-cambio-estado-resolucion/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: reconstruir las fuentes base desde los artefactos compilados y preparar los paquetes y la configuración mínima que necesitan los módulos nuevos.

- [X] T001A [P] Reconstruir las fuentes backend desde los artefactos compilados antes de modificar módulos existentes: crear `backend/app/main.py`, `backend/app/api/deps.py`, `backend/app/api/v1/router.py`, `backend/app/core/config.py`, `backend/app/core/errors.py`, `backend/app/db/base.py`, `backend/app/db/session.py`, `backend/app/models/enums.py`, `backend/app/models/ticket.py`, `backend/app/models/user.py`, `backend/app/models/priority.py`, `backend/app/models/category.py`, `backend/app/models/__init__.py`, `backend/app/schemas/work_queue.py`, `backend/app/services/work_queue.py`, `backend/app/utils/sla.py`, `backend/app/api/v1/dev_auth.py`, `backend/app/api/v1/work_queue.py`, `backend/tests/conftest.py`, `backend/alembic/env.py`, `backend/alembic/versions/0001_base_schema.py` y `backend/alembic/versions/0002_add_finalized_at_and_work_queue_indexes.py`, restaurando cada módulo desde el historial de control de versiones. Si algún fichero no estuviera versionado, reconstruirlo desde su contrato documentado y registrar la revisión manual en el commit; no se acepta el artefacto compilado como única fuente. Verificar con `python -m pytest tests -q` que las suites existentes pasan.
- [X] T001B [P] Reconstruir el proyecto frontend: crear `frontend/package.json` (scripts `dev`, `build`, `test`), `frontend/vite.config.ts`, `frontend/vitest.config.ts`, `frontend/tsconfig.json` y `frontend/tsconfig.node.json`, `frontend/tailwind.config.js`, `frontend/postcss.config.js`, `frontend/index.html`, `frontend/src/main.ts`, `frontend/src/App.vue`, `frontend/src/router/index.ts`, `frontend/src/services/http.ts`, `frontend/src/views/LoginPage.vue`, `frontend/src/views/WorkQueuePage.vue` y `frontend/src/views/TicketDetailPlaceholder.vue`, restaurando cada fichero desde el historial de control de versiones. Si algún fichero no estuviera versionado, reconstruirlo desde el contrato documentado y registrar la revisión manual; no se acepta `frontend/dist/assets/*.js` como única fuente. Verificar `npm install` (si falta `package-lock.json`) y `npm run test -- --run` con las suites existentes.
- [X] T001 Verificar los inicializadores de paquete del backend creados en T001A en `backend/app/api/v1/__init__.py`, `backend/app/schemas/__init__.py` y `backend/app/services/__init__.py`.
- [X] T002 [P] Crear los inicializadores de paquete de pruebas en `backend/tests/unit/__init__.py`, `backend/tests/integration/__init__.py` y `backend/tests/contract/__init__.py`.
- [X] T003 [P] Crear la estructura de carpetas de la feature en `frontend/src/components/tickets/`, `frontend/src/services/`, `frontend/src/stores/`, `frontend/src/types/`, `frontend/src/views/`, `frontend/tests/components/` y `frontend/tests/stores/`.
- [X] T004 [P] Verificar y completar `frontend/vitest.config.ts` (creado en T001B) para incluir `tests/components/**/*.spec.ts` y `tests/stores/**/*.spec.ts` con entorno `jsdom` y el alias `@` hacia `src`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: modelo de línea temporal, contrato de datos, servicio de lectura y base del cliente frontend. Ninguna historia puede empezar hasta completar esta fase.

**⚠️ CRITICAL**: no iniciar US1, US2 ni US3 hasta que T001A, T001B, T001–T013 y T011A estén completas.

- [X] T005 Añadir (o crear si no existe) el enum `TimelineEventType` en `backend/app/models/enums.py` con los valores exactos `status_change`, `resolution` e `internal_comment`; no modificar `TicketStatus` ni `FINAL_STATUSES`.
- [X] T006 Crear el modelo `TicketTimelineEntry` en `backend/app/models/timeline.py` con las columnas `id` (UUID PK), `ticket_id` (FK `tickets.id` `ON DELETE CASCADE`, NOT NULL), `event_type` (`Enum(TimelineEventType, name="timeline_event_type")` con `values_callable`), `from_status`/`to_status` (`Enum(TicketStatus, name="ticket_status")`, nulos), `body` (Text, nulo), `is_internal` (Boolean NOT NULL default `False`), `author_id` (FK `users.id`, NOT NULL), `created_at` (`DateTime(timezone=True)`, NOT NULL, `utcnow`), `event_order` (SmallInteger NOT NULL default `0`) y `request_id` (UUID, NOT NULL); declarar las restricciones `ck_timeline_status_change`, `ck_timeline_resolution`, `ck_timeline_internal_comment`, `ck_timeline_body_length` (`body IS NULL OR (length(body) >= 1 AND length(body) <= 5000)`, portable a SQLite; la migración PostgreSQL de T008 usa `char_length`), `ck_timeline_event_order` (`event_order IN (0, 1)`), `uq_timeline_request_event` (`ticket_id, request_id, event_type`) y los índices `ix_timeline_ticket_created`, `ix_timeline_ticket_internal`, `ix_timeline_author`.
- [X] T007 Añadir el export de `TicketTimelineEntry` en `backend/app/models/__init__.py` (reconstruido en T001A) sin alterar los exports existentes.
- [X] T008 Crear la migración `backend/alembic/versions/0003_ticket_timeline.py` con `revision = "0003_ticket_timeline"` y `down_revision = "0002_work_queue"`; `upgrade()` crea el tipo `timeline_event_type`, la tabla `ticket_timeline_entries` con FKs, CHECKs, UNIQUE e índices, y `downgrade()` elimina primero los índices, después la tabla y por último el tipo; no ejecutar `ALTER TABLE` sobre tablas existentes.
- [X] T009 [P] Crear todos los DTO Pydantic en `backend/app/schemas/ticket_workflow.py`: `StatusOption`, `AuthorRef`, `TimelineEntry`, `TicketWorkflowSnapshot`, `WorkflowResponse`, `StatusTransitionRequest` (`resolution: str | None`, `expected_updated_at: datetime`, `request_id: UUID` obligatorio), `StatusTransitionResponse`, `InternalCommentRequest` (`body: str`, `request_id: UUID`), `InternalCommentResponse`, `Pagination` y `TimelineResponse`. Pydantic valida solo forma y tipos; las longitudes de negocio (1–5.000) se validan en el servicio para conservar códigos estables.
- [X] T010 [P] Crear los tipos TypeScript compartidos en `frontend/src/types/ticketWorkflow.ts` para `TicketStatus`, `TimelineEventType`, `StatusOption`, `AuthorRef`, `TimelineEntry`, `TicketWorkflowSnapshot`, `WorkflowResponse`, `StatusTransitionRequest`, `StatusTransitionResponse`, `InternalCommentRequest`, `InternalCommentResponse`, `Pagination`, `TimelineResponse` y `ApiErrorBody`, exactamente con los nombres y formas del contrato.
- [X] T011 [P] Implementar la lectura de línea temporal y `viewer_capabilities(user, ticket)` en `backend/app/services/ticket_timeline.py`: la función devuelve `can_view_internal`, `can_change_status` y `can_comment_internally` a partir del rol y de la asignación vigente; la consulta filtra por `ticket_id`, aplica `is_internal = false` cuando `can_view_internal` es falso, ordena por `created_at ASC, event_order ASC, id ASC`, pagina con `page` mínimo 1 y `page_size` por defecto 50/máximo 200, y serializa a `TimelineEntry` con autor (`lazy="joined"`).
- [X] T011A [P] Implementar `can_read_ticket(user, ticket)` en `backend/app/services/ticket_timeline.py`: devuelve verdadero para el usuario creador y para roles `tecnico`, `supervisor` y `admin`; falso para cualquier otro. No revela la existencia del ticket y se recalcula en cada petición.
- [X] T012 [P] Ampliar `backend/tests/conftest.py` (reconstruido en T001A) con fixtures compartidas de HU-05: usuarios `user_creador` (rol `usuario`), `user_tecnico_asignado`, `user_tecnico_no_asignado`, `user_supervisor`, `user_admin` y `user_sin_relacion`; tickets `ticket_abierto`, `ticket_en_progreso`, `ticket_pendiente_usuario`, `ticket_resuelto` y `ticket_cerrado` con `finalized_at`/`closed_at` coherentes; factoría `auth_headers(user)` que devuelve `Authorization: Bearer <token>`; y factoría `timeline_entry_factory(...)` para construir entradas de línea temporal en pruebas.
- [X] T013 [P] Crear `frontend/src/services/ticketWorkflow.ts` con `getWorkflow(ticketId)`, `transitionStatus(ticketId, payload)`, `addInternalComment(ticketId, payload)` y `getTimeline(ticketId, page, pageSize)`, reutilizando el cliente GET/POST existente con `Authorization: Bearer` desde `localStorage.access_token`, `credentials: 'omit'` y parseo de errores `{"detail": {"code", "message"}}`; mapear `409` a `ApiClientError.kind = 'conflict'` conservando `status` y `code`.

**Checkpoint**: modelo, migración, DTOs, tipos, lectura de timeline, autorización de lectura, fixtures y cliente API listos. Las historias pueden comenzar.

---

## Phase 3: User Story 1 — Cambiar el estado según el flujo permitido (Priority: P1) 🎯 MVP

**Goal**: el técnico asignado consulta el estado actual y los destinos permitidos, ejecuta transiciones válidas y ve cada cambio en la línea temporal con autor y fecha.

**Independent Test**: con un ticket `abierto` asignado al técnico, `GET /tickets/{id}/workflow` devuelve solo `en_progreso`; `POST /tickets/{id}/status-transitions` a `en_progreso` devuelve `changed=true`, actualiza `status` y crea una única entrada `status_change`; una transición `abierto → resuelto` devuelve `409 invalid_transition` sin escribir; un ticket `resuelto` puede pasar a `cerrado`; un ticket `cerrado` no admite destinos.

> **Nota RF-005**: la transición automática `pendiente_usuario → en_progreso` al responder el usuario creador pertenece a HU-03. Esta feature implementa la función interna `apply_user_response_transition` (T021A) que HU-03 invocará dentro de su propia transacción, y verifica que la matriz la admite y que queda registrada en la línea temporal. No se implementa aquí la detección de la respuesta ni el contenido de la solicitud de información.

### Tests for User Story 1

- [X] T014 [P] [US1] Escribir las pruebas unitarias de la matriz 5×5 en `backend/tests/unit/test_ticket_state_machine.py`: totalidad de los cinco estados, exactamente las seis transiciones permitidas (`abierto→en_progreso`, `en_progreso→pendiente_usuario`, `en_progreso→resuelto`, `pendiente_usuario→en_progreso`, `resuelto→en_progreso`, `resuelto→cerrado`), `cerrado` sin salidas, ausencia de auto-transiciones, orden estable de opciones y etiquetas es-ES.
- [X] T015 [P] [US1] Escribir las pruebas de integración de transiciones en `backend/tests/integration/test_ticket_status_transitions.py`: casos válidos, incluida `en_progreso→resuelto` con una resolución válida (la cobertura exhaustiva del texto se amplía en US2), rechazos `409 invalid_transition`/`409 ticket_closed`, no-op `200 changed=false` sin entrada, reintento idéntico con el mismo `request_id` ⇒ `200 changed=false` sin escribir, reutilización del mismo `request_id` con otro destino, resolución o autor ⇒ `409 request_id_reused` sin escribir, `409 stale_ticket` con `expected_updated_at` obsoleto, reapertura `resuelto→en_progreso` que limpia `finalized_at`, cierre que conserva `finalized_at` y rellena `closed_at`, ausencia de escrituras parciales y `422 invalid_request` ante un payload mal formado (enum, UUID o fecha inválidos). Añadir pruebas de `apply_user_response_transition`: éxito con autor creador, replay idempotente y `409 request_id_reused`.
- [X] T015A [P] [US1] Escribir las pruebas de concurrencia reales en PostgreSQL en `backend/tests/integration/test_ticket_concurrency.py`, marcadas con `@pytest.mark.postgres` y omitidas cuando el motor no sea PostgreSQL: dos sesiones simultáneas sobre el mismo ticket comprueban que `_locked_ticket` (`SELECT id ... FOR UPDATE` + `session.get(..., populate_existing=True)`) serializa, que solo una escritura gana, que la perdedora recibe `409 stale_ticket`, que un mismo `request_id` no duplica entradas y que `status_change` + `resolution` se confirman o revierten juntos.
- [X] T016 [P] [US1] Escribir las pruebas de contrato de `GET /tickets/{id}/workflow`, `POST /tickets/{id}/status-transitions` y `GET /tickets/{id}/timeline` en `backend/tests/contract/test_ticket_workflow_contract.py`: campos obligatorios de `WorkflowResponse`, `TicketWorkflowSnapshot`, `StatusTransitionResponse` y `TimelineResponse`; valores de `allowed_transitions`; paginación de la línea temporal; y formato de error `{"detail":{"code","message"}}` para `401`, `403`, `404`, `409` (`invalid_transition`, `ticket_closed`, `stale_ticket`, `request_id_reused`), `422` (`invalid_request`) y `500`; un usuario autenticado sin acceso al ticket devuelve `404 ticket_not_found` en `GET /tickets/{id}/workflow` y `GET /tickets/{id}/timeline`.
- [X] T017 [P] [US1] Escribir la prueba de componentes de `TicketStatusSelector` en `frontend/tests/components/TicketStatusSelector.spec.ts`: solo renderiza `options`, no ofrece el estado actual, muestra «No hay cambios de estado disponibles.» con lista vacía, emite `select` y respeta `disabled`.
- [X] T018 [P] [US1] Escribir la prueba de componentes de `TicketTimeline` en `frontend/tests/components/TicketTimeline.spec.ts`: orden recibido, formato de fecha `es-ES`/`Europe/Madrid`, texto de `status_change`, estados vacío y de carga, y ausencia de botones de edición/borrado.
- [X] T019 [P] [US1] Escribir la prueba del flujo de estado de `TicketWorkflowPanel` en `frontend/tests/components/TicketWorkflowPanel.spec.ts`: carga inicial, envío de transición, refresco de timeline, deshabilitado durante `submitting` y aviso de `409 stale_ticket` con recarga; verificar que el payload incluye un UUID en `request_id`, que se reutiliza en un reintento idéntico y se regenera al cambiar destino o resolución.
- [X] T019A [P] [US1] Crear la prueba unitaria del store Pinia en `frontend/tests/stores/ticketDetail.spec.ts`: `loadWorkflow`/`loadTimeline` pueblan `ticket`, `timeline`, `pagination`, `canChangeStatus`, `canComment`, `canSeeInternal`, `timelineLoading` y `notice`; `transitionStatus` envía `expected_updated_at` y `request_id` y refresca timeline tras éxito; `409 stale_ticket` recarga workflow/timeline y conserva el texto de resolución y comentario; los errores se exponen en `error`/`errorCode` sin perder el estado previo.

### Implementation for User Story 1

- [X] T020 [US1] Implementar la máquina de estados pura en `backend/app/services/ticket_state_machine.py` con `ALLOWED_TRANSITIONS: dict[TicketStatus, frozenset[TicketStatus]]` y las funciones `allowed_transitions`, `is_transition_allowed`, `is_final_status`, `status_label` y `allowed_status_options`; sin importar SQLAlchemy ni FastAPI.
- [X] T021 [US1] Implementar `get_workflow` y `change_status` en `backend/app/services/ticket_workflow.py` con el orden de validación: autenticación, ticket existente (`404 ticket_not_found`), rol y asignación mediante `_ensure_writer` (`403 forbidden` / `403 not_ticket_assignee`), replay/reutilización de `request_id` (`_transition_entries` + `_classify_transition_replay`: mismo actor, destino y resolución normalizada ⇒ `200 changed=false` con `timeline_entries=[]`; cualquier diferencia ⇒ `409 request_id_reused`), `resolution_not_allowed` si el destino no es `resuelto` y llega `resolution` (antes del no-op), no-op por mismo estado, `expected_updated_at` (`409 stale_ticket`), ticket cerrado (`409 ticket_closed`), pertenencia a la matriz (`409 invalid_transition`) y resolución obligatoria/longitud (`422 resolution_required`/`resolution_too_long`); `get_workflow` devuelve el snapshot con las capacidades calculadas por `viewer_capabilities` (T011). Aplicar bloqueo `SELECT id ... FOR UPDATE` y recarga con `session.get(..., populate_existing=True)`, actualizar `status`/`updated_at` y `finalized_at`/`closed_at` según la tabla de efectos, e insertar la entrada `status_change` (`event_order=0`, `is_internal=false`, `body=NULL`) en la misma transacción con `flush()` y `rollback()` ante error. Para `target_status == resuelto`, normalizar `resolution` con `strip()`, exigir 1–5000 caracteres e insertar en la misma transacción la entrada `resolution` (`to_status='resuelto'`, `body` normalizado, `is_internal=false`, `from_status=NULL`, `event_order=1`). Persistir el `request_id` obligatorio en las entradas `status_change` y `resolution` y garantizar la unicidad `(ticket_id, request_id, event_type)`. Mantener la búsqueda y comparación de `request_id` en helpers internos de `ticket_workflow.py` (`_transition_entries`/`_classify_transition_replay` para transiciones y `_comment_entries` para comentarios); el router no la duplica. Asignar un único `now` (UTC, microsegundos) por comando y usarlo para `tickets.updated_at` y todas las entradas creadas, para que `status_change` y `resolution` compartan `created_at` y el orden dependa de `event_order`.
- [X] T021A [US1] Implementar `apply_user_response_transition(...)` en `backend/app/services/ticket_workflow.py` como función interna para HU-03: no hace `commit()` ni `rollback()`, exige `ticket.status == pendiente_usuario`, `actor_id == ticket.creator_id`, `request_id` obligatorio y `expected_updated_at`; bloquea con `_locked_ticket` (`SELECT id ... FOR UPDATE` + `session.get(..., populate_existing=True)`), valida la matriz, actualiza `status` a `en_progreso`, limpia `finalized_at`/`closed_at`, inserta `status_change` con `author_id = creator_id`, `event_order=0`, `is_internal=false`, `body=NULL` y aplica idempotencia con `_transition_entries`/`_classify_transition_replay` (`changed=false` o `409 request_id_reused`). No usa `_ensure_writer` porque el actor es el usuario creador, no el técnico asignado. Incluir prueba de que la función no hace `commit()`/`rollback()` (un `rollback` del llamador descarta la transición) y de que no existe ruta pública.
- [X] T022 [US1] Crear el router `backend/app/api/v1/tickets.py` con `GET /tickets/{ticket_id}/workflow`, `POST /tickets/{ticket_id}/status-transitions` y `GET /tickets/{ticket_id}/timeline`. Todos usan `get_current_user`; los `GET` usan el helper `_readable_ticket(session, ticket_id, user)`, que invoca `can_read_ticket(user, ticket)` y devuelve `404 ticket_not_found` si el ticket no existe o no es accesible. Los `POST` **no** aplican `require_technician` en el router: delegan rol y asignación en `_ensure_writer(user, ticket)` de `ticket_workflow.py` (`403 forbidden` para roles distintos de `tecnico`, `403 not_ticket_assignee` para técnico no asignado) y **no** consultan `request_id` ni deciden `changed`/`created`: devuelven el `StatusTransitionResponse` del servicio con `200`; el ajuste `201`/`200` se aplica en el endpoint de comentarios (T045). Toda la lógica de negocio e idempotencia vive en `ticket_workflow.py`/`ticket_timeline.py` y los `ApiError` se traducen al formato de error heredado. Implementar el handler de `RequestValidationError` en `backend/app/core/errors.py` (reconstruido en T001A), registrarlo en `backend/app/main.py` (reconstruido en T001A) y devolver `422 invalid_request` con el mismo formato.
- [X] T023 [US1] Registrar el router de tickets en `backend/app/api/v1/router.py` (reconstruido en T001A) con `include_router(tickets_router)` sin alterar los routers existentes.
- [X] T024 [US1] Añadir logging estructurado al comando de transición en `backend/app/services/ticket_workflow.py`: `INFO` por éxito con `ticket_id`, `actor_id`, `from_status`, `to_status`, `changed`, `request_id` y `duration_ms`; `WARNING` con `code`/`ticket_id` en rechazos; `ERROR` con `logger.exception` en fallos inesperados; nunca registrar cuerpos de resolución o comentario.
- [X] T025 [P] [US1] Crear `frontend/src/components/tickets/TicketStatusSelector.vue` con `props` `currentStatus`, `options` y `disabled`, emit `select`, `fieldset`/`legend` «Nuevo estado», radios nativos, foco visible, estilos Tailwind `slate` y mensaje «No hay cambios de estado disponibles.» cuando `options.length === 0`.
- [X] T026 [P] [US1] Crear `frontend/src/components/tickets/TicketTimeline.vue` con `props` `entries`, `canSeeInternal` y `loading`; renderizar `status_change` como «{autor} cambió el estado de {origen} a {destino}», fechas con `Intl.DateTimeFormat('es-ES', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'Europe/Madrid' })`, estado vacío «Todavía no hay actividad en este ticket.», carga con `role="status"` y texto plano sin `v-html`.
- [X] T026A [P] [US1] Crear el store Pinia `frontend/src/stores/ticketDetail.ts` con estado `ticket`, `timeline`, `pagination`, `canChangeStatus`, `canComment`, `canSeeInternal`, `loading`, `timelineLoading`, `submitting`, `error`, `errorCode`, `notice`, `resolutionText` y `commentText`; acciones `loadWorkflow`, `loadTimeline`, `refresh`, `transitionStatus`, `addComment` y `reset`, reutilizando `frontend/src/services/ticketWorkflow.ts` (T013); conservar los textos de resolución y comentario ante error, exponer `errorCode`/`notice` para no-op, replay y conflictos, recargar workflow/timeline tras `409 stale_ticket`, `409 invalid_transition` o `409 ticket_closed`, y recalcular `canChangeStatus` desde `ticket.allowed_transitions` tras una transición.
- [X] T027 [US1] Crear `frontend/src/components/tickets/TicketWorkflowPanel.vue` consumiendo el store `frontend/src/stores/ticketDetail.ts` (T026A), con `ticketId`, carga de `getWorkflow` + `getTimeline`, selector de estados, envío de `transitionStatus` con `expected_updated_at` tomado siempre de `ticket.updated_at` y `request_id` generado con `crypto.randomUUID()`, bloqueo `submitting`, refresco de timeline, `aria-live="polite"` para éxito y `role="alert"` para errores; copiar `can_change_status`, `can_comment_internally` y `can_view_internal` de `getWorkflow` a `canChangeStatus`, `canComment` y `canSeeInternal`, y pasar `canSeeInternal` a `TicketTimeline`; en `409 stale_ticket` recargar workflow/timeline y conservar el texto introducido. Conservar el `request_id` solo para reintentos idénticos (mismo destino y resolución); regenerarlo al cambiar destino o resolución y tras éxito/no-op. `expected_updated_at` no forma parte de la firma del `request_id`: se relee siempre del ticket actualizado.
- [X] T028 [US1] Crear `frontend/src/views/TicketDetailPage.vue` que obtiene `id` de `useRoute().params.id`, monta `<TicketWorkflowPanel :ticket-id="id" />`, mantiene el enlace «Volver a la cola de trabajo» y sustituye `TicketDetailPlaceholder` en la ruta `/tickets/:id` de `frontend/src/router/index.ts` (reconstruido en T001B) sin cambiar las demás rutas.

**Checkpoint**: US1 completa. El cambio de estado, la matriz, la concurrencia y la visualización de `status_change` funcionan de forma independiente. La resolución ya se valida y persiste en T021, por lo que ningún checkpoint permite resolver sin documentación; US2 añade el formulario, la visualización destacada y la cobertura exhaustiva de validación.

---

## Phase 4: User Story 2 — Documentar obligatoriamente la resolución (Priority: P1)

**Goal**: al pasar a `resuelto`, la descripción de la solución es obligatoria, se guarda como entrada inmutable `resolution` y permanece visible tras cerrar o reabrir el ticket.

**Independent Test**: en un ticket `en_progreso`, resolver con texto vacío, solo espacios o más de 5.000 caracteres devuelve `422` sin cambiar estado ni crear entradas; con texto válido devuelve `changed=true`, `status=resuelto`, `finalized_at` no nulo y dos entradas (`status_change` y `resolution`); tras reabrir y volver a resolver se conservan ambas resoluciones.

> **Nota de alcance**: la API ya valida y persiste la resolución dentro de `change_status` (T021). US2 aporta el formulario, la visualización destacada y la cobertura exhaustiva de validación; T034 es una tarea de endurecimiento, no un segundo camino de escritura.

### Tests for User Story 2

- [X] T029 [P] [US2] Ampliar `backend/tests/integration/test_ticket_status_transitions.py` con resolución: vacío/solo espacios ⇒ `422 resolution_required`; 5.001 caracteres ⇒ `422 resolution_too_long`; payload con tipo, enum, UUID o fecha inválidos ⇒ `422 invalid_request`; texto válido ⇒ `status_change` + `resolution` atómicos y `finalized_at`; `resolution` enviada a un destino distinto de `resuelto` ⇒ `422 resolution_not_allowed`, incluso cuando el destino coincide con el estado actual; resolución visible tras `cerrado`; reapertura y nueva resolución conservan la anterior como histórico.
- [X] T029A [US2] Añadir la prueba ejecutable de inmutabilidad de la resolución en `backend/tests/integration/test_ticket_status_transitions.py` (mismo archivo que T029, ejecutar después): (a) no existe `PATCH`/`PUT`/`DELETE` sobre `/tickets/{id}/status-transitions` (`405`) ni sobre la entrada `resolution` (`404`); (b) un segundo envío con distinto `request_id` y `target_status=resuelto` sobre un ticket ya `resuelto` devuelve `200 changed=false` y deja intacto el `body` y `created_at` originales; (c) tras reabrir y volver a resolver, la resolución anterior conserva su `body` y `created_at` y aparece una segunda entrada; (d) el `body` persistido es exactamente el `strip()` del texto enviado y no cambia tras `cerrado`.
- [X] T030 [P] [US2] Ampliar `backend/tests/contract/test_ticket_workflow_contract.py` con los campos `resolution`, `timeline_entries` y los códigos `resolution_required`, `resolution_too_long`, `resolution_not_allowed` e `invalid_request`, verificando que `StatusTransitionResponse` incluye la entrada `resolution` con `body` normalizado y que el caso «mismo estado + resolución» devuelve `422 resolution_not_allowed` sin escritura.
- [X] T031 [P] [US2] Crear la prueba de `ResolutionForm` en `frontend/tests/components/ResolutionForm.spec.ts`: etiqueta «Descripción de la solución», `maxlength=5000`, contador con `trim()`, `aria-required`, error con `role="alert"` y emisión de `update:modelValue`.
- [X] T032 [P] [US2] Ampliar `frontend/tests/components/TicketWorkflowPanel.spec.ts` con el bloqueo de «Resuelto» sin texto, el límite de 5.000 caracteres, la aparición del formulario solo con destino `resuelto`, la conservación del texto tras `409`/`422` y el foco en el primer campo con error.

### Implementation for User Story 2

- [X] T033 [P] [US2] Crear `frontend/src/components/tickets/ResolutionForm.vue` con `v-model`, `disabled`, `error` y `maxLength=5000`; `<textarea rows="5" :maxlength="maxLength" aria-required="true">`, contador `{{ modelValue.trim().length }} / {{ maxLength }}`, texto de ayuda «Obligatoria para marcar el ticket como Resuelto. No podrás editarla después; si la solución cambia, reabre el ticket y documenta una nueva.», error inline con `role="alert"` y sin `v-html`.
- [X] T034 [US2] Endurecer la validación y persistencia de resolución en `backend/app/services/ticket_workflow.py` (la lógica base ya existe en T021): revisar la normalización con `strip()`, el límite `1–5000` tras la normalización, el rechazo `resolution_not_allowed` para destinos distintos de `resuelto` evaluado **antes** del no-op por mismo estado, la inserción atómica de `resolution` (`to_status='resuelto'`, `body` normalizado, `is_internal=false`, `from_status=NULL`, `event_order=1`) y la conservación de resoluciones anteriores en reaperturas. No introducir un segundo camino de escritura ni duplicar la transacción.
- [X] T035 [US2] Ajustar `POST /tickets/{ticket_id}/status-transitions` en `backend/app/api/v1/tickets.py` para devolver el `StatusTransitionResponse` del servicio: `timeline_entries` con las entradas `status_change` y `resolution` creadas, `200` con `changed=false` y `timeline_entries=[]` (mensaje «El ticket ya se encuentra en ese estado.» para no-op y «Esta transición ya se aplicó con el identificador de solicitud indicado.» para replay idempotente). Los `422` de resolución y los `409` se propagan como `ApiError` desde `ticket_workflow.py`; el router no reconstruye la respuesta, no vuelve a consultar `request_id` ni decide la idempotencia (T021).
- [X] T036 [US2] Integrar `ResolutionForm` en `frontend/src/components/tickets/TicketWorkflowPanel.vue` y aplicar la regla `canSubmit` sobre `resolutionText` del store: destino seleccionado, `resolutionText.trim().length > 0` cuando el destino es `resuelto`, longitud `<= 5000`, `!submitting`; deshabilitar «Guardar cambio» cuando `canSubmit` sea falso, revalidar en el submit, mover el foco al primer error y limpiar `resolutionText` solo tras éxito. Gestionar el ciclo de vida del `request_id` definido en T027: conservarlo en errores de red/409/422 con el mismo payload y regenerarlo si cambia el destino o el texto. Construir el payload omitiendo `resolution` cuando el destino no sea `resuelto`; añadir una prueba de panel que verifique que un texto de resolución presente no se envía al seleccionar `cerrado` o `pendiente_usuario`.
- [X] T037 [US2] Renderizar la entrada `resolution` en `frontend/src/components/tickets/TicketTimeline.vue` como tarjeta destacada «Resolución» (`bg-emerald-50 text-emerald-800`) con el texto completo en plano, autor y fecha; mantenerla visible después de cerrar el ticket y tras una reapertura.

**Checkpoint**: US2 completa. Ningún ticket puede quedar `resuelto` sin resolución y el histórico de resoluciones es visible e inmutable.

---

## Phase 5: User Story 3 — Añadir comentarios internos en cualquier momento (Priority: P2)

**Goal**: el técnico asignado añade notas internas en cualquier estado, incluido `cerrado`, sin cambiar el estado y sin que el creador ni técnicos no asignados puedan verlas.

**Independent Test**: en un ticket `en_progreso` y en uno `cerrado`, el técnico asignado publica un comentario interno y lo ve en la timeline sin que cambie `status`; un comentario vacío o de 5.001 caracteres devuelve `422`; el mismo `request_id` no duplica; el creador y un técnico no asignado no reciben entradas `internal_comment`; el asignado, supervisor y admin sí.

### Tests for User Story 3

- [X] T038 [P] [US3] Crear `backend/tests/integration/test_internal_comments.py` con: alta en todos los estados incluido `cerrado`, validación de vacío/solo espacios ⇒ `422 comment_required`, más de 5.000 caracteres ⇒ `422 comment_too_long`, payload mal formado (UUID o tipo inválido) ⇒ `422 invalid_request`, estado del ticket sin cambios, autor correcto e idempotencia por `request_id` (`created=false` con el mismo `body`; `409 request_id_reused` con `body` o autor distintos, sin escribir). Autorización: `supervisor`, `admin` y creador ⇒ `403 forbidden`; `tecnico` no asignado ⇒ `403 not_ticket_assignee`; en todos los rechazos, ninguna entrada nueva.
- [X] T039 [P] [US3] Crear `backend/tests/integration/test_timeline_visibility.py` con: creador y técnico no asignado solo reciben `status_change` y `resolution`; técnico asignado, supervisor y admin reciben `internal_comment`; la reasignación revoca el acceso al técnico anterior; el orden `created_at, event_order, id` se respeta; un usuario autenticado sin relación con el ticket recibe `404 ticket_not_found` y no recibe ninguna entrada de la timeline.
- [X] T040 [P] [US3] Crear la prueba de `InternalCommentForm` en `frontend/tests/components/InternalCommentForm.spec.ts`: etiqueta y ayuda «Solo visible para el técnico asignado, supervisores y administradores.», contador, botón deshabilitado con texto vacío/solo espacios o más de 5.000 caracteres, y emisión de `submit` solo con texto válido.
- [X] T041 [P] [US3] Ampliar `frontend/tests/components/TicketTimeline.spec.ts` y `frontend/tests/components/TicketWorkflowPanel.spec.ts` para: ocultar `internal_comment` cuando `canSeeInternal=false`, mostrarla con etiqueta «Interno» cuando sea `true`, permitir comentar en ticket `cerrado`, refrescar la timeline y limpiar el textarea solo tras éxito.

### Implementation for User Story 3

- [X] T042 [US3] Crear `frontend/src/components/tickets/InternalCommentForm.vue` con `v-model`, `disabled` y `error`; `<textarea>` «Comentario interno», ayuda de visibilidad, contador `0 / 5000`, validación `trim()` entre 1 y 5.000, botón «Añadir comentario interno» deshabilitado si no es válido o hay envío en curso, y emit `submit`.
- [X] T043 [US3] Implementar `add_internal_comment` en `backend/app/services/ticket_workflow.py`: comprobar rol y asignación mediante `_ensure_writer`, normalizar con `strip()`, exigir `1–5000` caracteres con los códigos estables `comment_required`/`comment_too_long` (no delegar la longitud en Pydantic), insertar `internal_comment` (`body`, `is_internal=true`, `from_status=NULL`, `to_status=NULL`, `event_order=0`) sin tocar `tickets.status`, y deduplicar por `(ticket_id, request_id, event_type)` con `_comment_entries`: si existe la misma entrada con el mismo `author_id` y `body.strip()`, devolver `created=false`; si el `body` o el autor difieren, lanzar `409 request_id_reused` sin insertar. Reutilizar los helpers de idempotencia de `ticket_workflow.py` (T021) y no repetir la comprobación en el router.
- [X] T044 [US3] Aplicar la visibilidad de comentarios internos en `backend/app/services/ticket_timeline.py` reutilizando `viewer_capabilities` de T011: recalcular las capacidades en cada petición a partir de la asignación vigente (una reasignación revoca el acceso al técnico anterior), filtrar `is_internal` en la consulta SQL y exponer `can_view_internal` en la respuesta de workflow. No duplicar la lógica de capacidades ni confiar en el filtrado del cliente.
- [X] T045 [US3] Añadir `POST /tickets/{ticket_id}/internal-comments` en `backend/app/api/v1/tickets.py`, devolviendo el `InternalCommentResponse` de `add_internal_comment` (T043): `201` con `created=true` en alta nueva, `200` con `created=false` en reintento idéntico y `409 request_id_reused` si el servicio rechaza la reutilización. El router usa `get_current_user`; `_ensure_writer` en el servicio valida rol y asignación, y el router no vuelve a consultar `request_id`, no compara `body` ni decide `created`. Actualizar `GET /tickets/{ticket_id}/workflow` para devolver `can_view_internal`, `can_change_status` y `can_comment_internally` calculados por `viewer_capabilities` (T011) y `GET /tickets/{ticket_id}/timeline` para aplicar la visibilidad del usuario.
- [X] T046 [US3] Integrar `InternalCommentForm` en `frontend/src/components/tickets/TicketWorkflowPanel.vue`: mostrarlo según `can_comment_internally` (también con ticket `cerrado`), generar un `request_id` con `crypto.randomUUID()`, reutilizarlo solo en reintentos idénticos y regenerarlo si cambia el texto, llamar a `addInternalComment`, refrescar la timeline, limpiar el texto solo tras éxito y conservarlo ante error.
- [X] T047 [US3] Actualizar `frontend/src/components/tickets/TicketTimeline.vue` para no renderizar entradas `internal_comment` cuando `canSeeInternal=false`, mostrarlas con etiqueta textual «Interno» y estilo `bg-amber-50 text-amber-800` cuando `true`, y pasar `canSeeInternal` desde `TicketWorkflowPanel.vue`.

**Checkpoint**: US3 completa. Los comentarios internos funcionan en cualquier estado y la visibilidad se aplica exclusivamente en servidor.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: coherencia, accesibilidad, invariantes y validación end-to-end de las tres historias.

- [X] T048 [P] Auditar el logging de `backend/app/services/ticket_workflow.py` para garantizar que nunca se registran cuerpos de resolución ni de comentarios, que los rechazos llevan `code` y `ticket_id`, y que los fallos inesperados usan `logger.exception`.
- [X] T049 [P] Auditar accesibilidad y responsive en `frontend/src/components/tickets/TicketStatusSelector.vue`, `ResolutionForm.vue`, `InternalCommentForm.vue`, `TicketTimeline.vue` y `TicketWorkflowPanel.vue`: `fieldset`/`legend`, `aria-*`, foco visible, `role="alert"`/`aria-live`, contraste AA y apilado en una columna por debajo de 640 px.
- [X] T050 [P] Añadir aserciones de invariantes (requiere T050A, cuya auditoría de legado define la exclusión) en `backend/tests/integration/test_ticket_status_transitions.py` y `backend/tests/integration/test_timeline_visibility.py`: el último `status_change` coincide con `tickets.status`, todo `resuelto` cuyo `finalized_at` sea posterior a `0003_ticket_timeline` tiene al menos una `resolution` (los tickets con `finalized_at` anterior se excluyen y se listan en la auditoría), `finalized_at` es no nulo si y solo si el estado es final, y `closed_at` solo existe en `cerrado`.
- [X] T050A Implementar la auditoría de legado (mismo archivo que T050; ejecutar antes) en `backend/tests/integration/test_ticket_status_transitions.py`: listar los tickets `resuelto`/`cerrado` con `finalized_at` anterior a `0003_ticket_timeline` que no tienen entrada `resolution`, verificar que quedan excluidos de la aserción «resuelto ⇒ resolución» y documentar el listado en la salida de la auditoría y en quickstart §7.
- [X] T051 [P] Verificar `upgrade()` y `downgrade()` de `backend/alembic/versions/0003_ticket_timeline.py` sobre PostgreSQL: `alembic current` muestra `0003_ticket_timeline (head)`, la tabla y sus índices existen, el enum contiene los tres valores y `downgrade 0002_work_queue` no deja residuos.
- [X] T052 [P] Ejecutar las suites del backend desde `backend/`: `python -m pytest tests/unit tests/integration tests/contract -q` y corregir cualquier fallo sin relajar las validaciones de negocio.
- [X] T053 [P] Ejecutar las pruebas del frontend desde `frontend/`: `npm run test -- --run` y corregir cualquier fallo de componentes, accesibilidad o tipos.
- [X] T054 Ejecutar los escenarios HTTP y de interfaz de `specs/005-cambio-estado-resolucion/quickstart.md` (secciones 5, 6 y 7) contra los servicios locales y registrar el resultado.
- [X] T055 [P] Auditar los guardarraíles de arquitectura en `backend/app/`, `backend/alembic/versions/0003_ticket_timeline.py` y `frontend/src/`: sin columnas nuevas en `tickets`, sin `PATCH`/`PUT`/`DELETE`, sin `v-html`, sin nuevas dependencias, sin cambios en `TicketStatus`/`FINAL_STATUSES` y sin comprobaciones de `request_id` ni decisiones de `changed`/`created` en `backend/app/api/v1/tickets.py` (la idempotencia vive solo en `ticket_workflow.py`).
- [X] T055A [P] Revisar la seguridad de la visibilidad de datos internos antes del merge: confirmar el filtro `is_internal` en SQL, que creador y técnicos no asignados nunca reciben entradas `internal_comment`, que la reasignación revoca el acceso y que los cuerpos de resolución/comentario no aparecen en logs.
- [X] T055B [P] Ejecutar y registrar las pruebas de concurrencia escritas en T015A sobre PostgreSQL: dos sesiones simultáneas sobre el mismo ticket para verificar `_locked_ticket` (`SELECT id ... FOR UPDATE` + `session.get(..., populate_existing=True)`), la respuesta `409 stale_ticket`, la ausencia de entradas duplicadas y la atomicidad de `status_change` + `resolution`.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: sin dependencias; T001A y T001B pueden ejecutarse en paralelo al inicio, seguidos de T001–T004.
- **Foundational (Phase 2)**: depende de Setup; T005–T013 y T011A **bloquean** todas las historias.
- **User Stories (Phase 3–5)**: dependen de Foundational.
  - **US1 (P1)**: puede empezar tras Foundational. Es el MVP.
  - **US2 (P1)**: depende de US1 para reutilizar `change_status` y el endpoint de transiciones (T021–T023); puede empezar su frontend en paralelo una vez existan tipos y servicio (T010, T013).
  - **US3 (P2)**: depende de Foundational para modelo/lectura y de US1 para el panel y la timeline; su backend (`add_internal_comment`) es independiente de US2.
- **Polish (Phase 6)**: depende de las historias que se quieran entregar; T048–T055 y las variantes T050A, T055A y T055B se ejecutan al final. T050A va antes de T050 porque comparten archivo y T050 consume su auditoría de legado.

### User Story Dependencies

- **US1**: sin dependencias de otras historias.
- **US2**: depende de US1 (servicio y endpoint de transición). No depende de US3.
- **US3**: depende de US1 (panel/timeline) y de Foundational (modelo y lectura). No depende de US2.

### Within Each User Story

- Las pruebas se escriben primero y deben fallar antes de implementar.
- Modelo/servicios antes de endpoints.
- Componentes antes de la integración en el panel.
- La historia se valida en su checkpoint antes de pasar a la siguiente prioridad.

### Parallel Opportunities

- Setup: T001A y T001B en paralelo; T002, T003 y T004 en paralelo tras T001 y T001B.
- Foundational: T009, T010 y T011 en paralelo tras T006; T011A tras T011, en paralelo con T012 y T013.
- US1: T014–T019, T015A y T019A (pruebas, ficheros distintos) en paralelo; T025, T026 y T026A (componentes/store, ficheros distintos) en paralelo.
- US2: T029, T030, T031 y T032 (pruebas) en paralelo; T029A comparte archivo con T029 y se ejecuta después. T033 (componente) puede avanzar en paralelo con T034/T035 (backend).
- US3: T038–T041 (pruebas) en paralelo; T042 (componente) puede avanzar en paralelo con T043/T044 (backend).
- Polish: T048, T049, T051, T052, T053, T055, T055A y T055B son independientes entre sí; T050A va antes de T050 (mismo archivo y dependencia de la auditoría); T054 requiere los servicios levantados.

---

## Parallel Example: User Story 1

```bash
# Pruebas de US1 en paralelo (ficheros distintos):
Task: "T014 [US1] Pruebas de la matriz 5x5 en backend/tests/unit/test_ticket_state_machine.py"
Task: "T015 [US1] Pruebas de integración de transiciones en backend/tests/integration/test_ticket_status_transitions.py"
Task: "T015A [US1] Pruebas de concurrencia PostgreSQL en backend/tests/integration/test_ticket_concurrency.py"
Task: "T016 [US1] Pruebas de contrato en backend/tests/contract/test_ticket_workflow_contract.py"
Task: "T017 [US1] Prueba de TicketStatusSelector en frontend/tests/components/TicketStatusSelector.spec.ts"
Task: "T018 [US1] Prueba de TicketTimeline en frontend/tests/components/TicketTimeline.spec.ts"
Task: "T019 [US1] Prueba del panel en frontend/tests/components/TicketWorkflowPanel.spec.ts"
Task: "T019A [US1] Prueba del store en frontend/tests/stores/ticketDetail.spec.ts"

# Componentes de US1 en paralelo:
Task: "T025 [US1] Crear frontend/src/components/tickets/TicketStatusSelector.vue"
Task: "T026 [US1] Crear frontend/src/components/tickets/TicketTimeline.vue"
```

## Parallel Example: User Story 2

```bash
# Pruebas de US2 en paralelo:
Task: "T029 [US2] Pruebas de resolución en backend/tests/integration/test_ticket_status_transitions.py"
Task: "T030 [US2] Contrato de resolución en backend/tests/contract/test_ticket_workflow_contract.py"
Task: "T031 [US2] Prueba de ResolutionForm en frontend/tests/components/ResolutionForm.spec.ts"
Task: "T032 [US2] Prueba del panel con resolución en frontend/tests/components/TicketWorkflowPanel.spec.ts"

# En serie tras T029 (comparte archivo):
Task: "T029A [US2] Prueba de inmutabilidad de la resolución en backend/tests/integration/test_ticket_status_transitions.py"

# Componente y backend en paralelo (ficheros distintos):
Task: "T033 [US2] Crear frontend/src/components/tickets/ResolutionForm.vue"
Task: "T034 [US2] Validación y persistencia de resolución en backend/app/services/ticket_workflow.py"
```

## Parallel Example: User Story 3

```bash
# Pruebas de US3 en paralelo:
Task: "T038 [US3] Pruebas de comentarios internos en backend/tests/integration/test_internal_comments.py"
Task: "T039 [US3] Pruebas de visibilidad en backend/tests/integration/test_timeline_visibility.py"
Task: "T040 [US3] Prueba de InternalCommentForm en frontend/tests/components/InternalCommentForm.spec.ts"
Task: "T041 [US3] Pruebas de visibilidad en timeline y panel en frontend/tests/components/"

# Componente y backend en paralelo (ficheros distintos):
Task: "T042 [US3] Crear frontend/src/components/tickets/InternalCommentForm.vue"
Task: "T043 [US3] Implementar add_internal_comment en backend/app/services/ticket_workflow.py"
Task: "T044 [US3] Implementar visibilidad en backend/app/services/ticket_timeline.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Completar Phase 1 (Setup).
2. Completar Phase 2 (Foundational) — bloquea todas las historias.
3. Completar Phase 3 (US1).
4. **STOP and VALIDATE**: ejecutar T014–T019, T019A y T015A, y el escenario de quickstart 5.2–5.3/5.11; confirmar que la matriz, la concurrencia, el store y la timeline funcionan.
5. Desplegar/demostrar US1 como incremento técnico.

> Un despliegue funcional de HU-05 debe incluir también US2, porque la resolución obligatoria es el criterio central de la historia. US1 solo es el MVP técnico que habilita el flujo de estados.

### Incremental Delivery

1. Setup + Foundational → base lista.
2. US1 → validar matriz y timeline → demo del flujo de estados.
3. US2 → validar resolución obligatoria e histórico → demo de HU-05 completa.
4. US3 → validar comentarios internos y visibilidad → demo de la trazabilidad interna.
5. Polish → ejecutar quickstart completo y auditorías.

### Parallel Team Strategy

1. El equipo completa Setup + Foundational.
2. Después:
   - Persona A: US1 (backend + panel base).
   - Persona B: US2 (formulario de resolución y validaciones) en cuanto US1 exponga el comando.
   - Persona C: US3 (comentarios internos y visibilidad) en cuanto US1 exponga el panel.
3. Integrar por checkpoints y ejecutar Polish al final.

---

## Notes

- `[P]` indica ficheros distintos y ausencia de dependencias de tareas incompletas.
- `[USn]` traza cada tarea a la historia correspondiente de `spec.md`.
- Las pruebas de US2 y US3 amplían ficheros creados en US1; por eso no se marcan `[P]` frente a esas tareas anteriores, solo frente a las de su propia fase.
- Cada historia termina en un checkpoint verificable de forma independiente.
- **RF-005 pertenece a HU-03**: esta feature expone `apply_user_response_transition` (T021A) como contrato interno para que HU-03 ejecute la transición `pendiente_usuario → en_progreso` dentro de su transacción y garantiza su trazabilidad; no implementa la detección de la respuesta del usuario ni el contenido de la solicitud de información.
- Pydantic valida forma y tipos; las longitudes de negocio (1–5.000) y el resto de reglas se validan en el servicio con códigos estables (`invalid_request`, `resolution_required`, `resolution_too_long`, `resolution_not_allowed`, `comment_required`, `comment_too_long`).
- No se añaden endpoints de edición/borrado: la timeline es append-only.
- Los mensajes de usuario y de error deben estar en español de España.

---

## Phase 7: Convergence — permisos y mensajes

> **Nota de numeración**: los identificadores `T061`, `T065`, `T066` y `T067` no se asignaron porque sus cambios quedaron absorbidos por tareas de convergencia posteriores. Se conserva la numeración original para no romper referencias en commits y revisiones.

- [X] T056 Alinear el rechazo de escritura de HU-05 para que `supervisor`, `admin` y `usuario` reciban `403 forbidden` con «No tienes permiso para modificar este ticket.» desde `_forbidden()` en `backend/app/services/ticket_workflow.py` (invocado por `_ensure_writer`), manteniendo en `backend/app/api/deps.py` el mensaje «Esta vista está disponible solo para técnicos.» de `require_technician` para `GET /work-queue`; añadir pruebas de contrato/integración que verifiquen ambos mensajes. per RF-028/RF-029, plan §1.5 (resolved)
- [X] T057 Recalcular `canChangeStatus` tras una transición exitosa y condicionar `ResolutionForm`, el selector y el botón «Guardar cambio» a esa capacidad en `frontend/src/stores/ticketDetail.ts` y `frontend/src/components/tickets/TicketWorkflowPanel.vue`, de modo que al cerrar un ticket en la misma sesión se muestre el aviso de cierre y no queden controles habilitados; ampliar las pruebas del store y del panel. per plan §3.2, contracts/frontend-components.md §9.2 (resolved)
- [X] T058 Identificar como históricas en `frontend/src/components/tickets/TicketTimeline.vue` las resoluciones anteriores a una reapertura (`status_change` de `resuelto` a `en_progreso`) mediante una etiqueta visual junto a «Resolución», sin alterar el orden ni el texto plano; ampliar `frontend/tests/components/TicketTimeline.spec.ts` con una reapertura y dos resoluciones. per RN-09/RF-014 (resolved)
- [X] T059 Devolver el mensaje 500 del catálogo HU-05 («No se pudo guardar el cambio. El ticket no se ha modificado. Inténtalo de nuevo.») cuando falle inesperadamente una operación de escritura de workflow, ajustando `backend/app/core/errors.py` y/o `backend/app/api/v1/tickets.py` sin cambiar el mensaje de `GET /work-queue`; añadir una prueba de contrato que compruebe el mensaje además del código `internal_error`. per RF-029, plan §1.5 (resolved)

---

## Phase 8: Convergence — resolución y autorización

- [X] T060 Reconciliar el orden de validación de `change_status` con RF-034/RN-03: cuando `resolution` no sea nula y `target_status` sea distinto de `resuelto`, devolver `422 resolution_not_allowed` incluso si `target_status` coincide con el estado actual, manteniendo el no-op `200 changed=false` para peticiones sin resolución; actualizar `plan.md` §1.2 y `data-model.md` §5.1 para que la precedencia no contradiga la spec y añadir pruebas de integración y contrato del caso «mismo estado + resolución» en `backend/tests/integration/test_ticket_status_transitions.py` y `backend/tests/contract/test_ticket_workflow_contract.py`. per RF-034/RN-03, spec.md L123 y L221 vs plan §1.2 #5/#6 (resolved)
- [X] T062 Alinear la autorización de escritura con el orden documentado en plan §1.2/§1.6: `get_current_user` en el router, carga del ticket y `404 ticket_not_found` antes de la comprobación de rol; `_ensure_writer` en `ticket_workflow.py` valida rol y asignación (`403 forbidden`/`403 not_ticket_assignee`). No se usa `require_technician` en HU-05 y se mantiene intacto su mensaje en `GET /work-queue`; añadir pruebas de contrato con ticket inexistente y rol no técnico. per plan §1.2 #2/#3, §1.6 y T022 (resolved)
- [X] T063 Reconciliar `TicketTimelineEntry.ticket` con `data-model.md` §3.4: relación many-to-one `ticket` → `Ticket` declarada en `backend/app/models/timeline.py` sin modificar `Ticket`, con la prueba de carga `test_timeline_entry_ticket_relationship` en `backend/tests/integration/test_timeline_visibility.py`. per data-model §3.4 (resolved)

---

## Phase 9: Convergence — rendimiento

- [X] T064 [CRITICAL] Proporcionar evidencia reproducible del rendimiento de HU-05 y dejarla versionada: medir el p95 de `GET /tickets/{id}/workflow`, `GET /tickets/{id}/timeline` y `POST /tickets/{id}/status-transitions` (< 300 ms) y el tiempo percibido hasta reflejar una transición (< 2 s) con datos de seed, documentar comandos y resultados en `specs/005-cambio-estado-resolucion/quickstart.md` o en un informe de rendimiento, y añadir una comprobación ejecutable que detecte regresiones. per Constitución IV y «Rendimiento», plan Objetivos de rendimiento, SC-004 y SC-010 (resolved)

---

## Phase 10: Convergence — estados de carga

- [X] T068 Hacer visible el estado de carga de la línea temporal mientras se resuelve `GET /tickets/{id}/timeline`: en `frontend/src/stores/ticketDetail.ts` mantener un indicador de carga propio de la timeline (o conservar `loading` activo hasta completar workflow y timeline) y pasarlo desde `frontend/src/components/tickets/TicketWorkflowPanel.vue` a `TicketTimeline`, de modo que no se muestre el estado vacío durante la petición; añadir una prueba en `frontend/tests/stores/ticketDetail.spec.ts` y/o `frontend/tests/components/TicketWorkflowPanel.spec.ts` que verifique que el estado de carga aparece y que el vacío solo se muestra tras completar la carga. per plan §3.2 flujo de carga, §3.6, contracts/frontend-components.md §5, T026/T026A (resolved)
- [X] T069 Mostrar el botón «Reintentar» cuando falle cualquier carga del panel, incluida la de la línea temporal con `ticket` ya cargado: ajustar `frontend/src/components/tickets/TicketWorkflowPanel.vue` para renderizar el aviso de error con reintento también cuando `ticket` exista y el error provenga de `loadTimeline`, y hacer que «Reintentar» recargue workflow y timeline; añadir una prueba del caso «workflow correcto + timeline fallida». per plan §3.2 flujo de carga paso 3, §3.6 (resolved)
- [X] T070 Alinear el estado vacío de `frontend/src/components/tickets/TicketTimeline.vue` con plan §3.6 añadiendo `role="status"` al párrafo «Todavía no hay actividad en este ticket.» (o, si se decide que solo el estado de carga debe anunciarse, corregir plan §3.6 y `contracts/frontend-components.md` §5 para eliminar la contradicción); ampliar `frontend/tests/components/TicketTimeline.spec.ts` para cubrir el rol del estado vacío. per plan §3.6 vs contracts/frontend-components.md §5 y T026 (resolved)

---

## Phase 11: Convergence — bloqueo de fila

- [X] T071 [CRITICAL] Corregir la lectura del ticket bloqueado en `_locked_ticket` de `backend/app/services/ticket_workflow.py` para que `apply_user_response_transition` valide el estado y `expected_updated_at` contra la fila confirmada y no contra la instancia obsoleta del identity map del llamador (por ejemplo, `session.get(Ticket, locked_id, populate_existing=True)` después del `SELECT ... FOR UPDATE`, sin cambiar el contrato de transacción de HU-03); añadir una prueba de regresión portable en `backend/tests/integration/test_ticket_status_transitions.py` (ticket precargado → otra transacción confirma un cambio → el llamador recibe `409` y no se duplica la entrada) y una prueba de concurrencia real en `backend/tests/integration/test_ticket_concurrency.py` con dos sesiones que precargan el ticket como HU-03, donde solo una obtiene `changed=true` y la perdedora recibe `409` con una única entrada `status_change`. per RN-08, RF-005, RF-030, RF-031, plan §1.3/§1.7, Constitución IV y T021A/T055B (resolved)

---

## Phase 12: Convergence — evidencia de rendimiento

- [X] T072 Completar la tabla de resultados de `specs/005-cambio-estado-resolucion/quickstart.md` §8 sustituyendo el marcador `*(rellenar tras ejecutar)*` de `POST /tickets/{id}/status-transitions` (p95) por el valor medido al ejecutar `python -m pytest tests/integration/test_ticket_workflow_performance.py -q -s` (en la ejecución de referencia: 24,09 ms; presupuesto < 300 ms) y anotar la fecha y el entorno de la medición, manteniendo el resto de filas y la comprobación ejecutable ya existente en `backend/tests/integration/test_ticket_workflow_performance.py`; no se requiere cambio de código. per T064, plan Objetivos de rendimiento, SC-004 y SC-010 (partial).
