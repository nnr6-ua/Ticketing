# Tasks: HU-06 — Reasignar o escalar ticket

**Input**: Design documents from `/specs/006-reasignar-escalar-ticket/`

**Prerequisites**: `plan.md` (required), `spec.md` (required), `research.md`, `data-model.md`, `contracts/`

**Tests**: Incluidas y obligatorias. La constitución del proyecto y el `plan.md` exigen contratos primero y pruebas ejecutables por capa (pytest, TestClient/httpx, Vitest, `@vue/test-utils` y `axe-core`). Las tareas de prueba se escriben antes de la implementación y deben fallar primero.

**Organization**: Tareas agrupadas por historia de usuario para permitir implementación, prueba y entrega independientes. Prioridades: US1 (P1), US2 (P1), US3 (P1), US4 (P1) y US5 (P2).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Puede ejecutarse en paralelo (archivos distintos, sin dependencias pendientes)
- **[Story]**: Historia de usuario a la que pertenece la tarea (`US1`…`US5`); las fases Setup, Foundational y Polish no llevan etiqueta, salvo las pruebas diferidas de Phase 2 (`T070`, `T071`, `T086`), que conservan su etiqueta para mantener la trazabilidad
- Todas las descripciones incluyen la ruta exacta del archivo afectado

## Path Conventions

- **Backend (FastAPI)**: `backend/app/`, `backend/alembic/`, `backend/tests/`, `backend/scripts/`
- **Frontend (Vue 3 + TypeScript)**: `frontend/src/`, `frontend/tests/`
- **Contratos**: `specs/006-reasignar-escalar-ticket/contracts/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirmar la línea base del repositorio y la coherencia de los contratos antes de tocar código.

- [X] T001 [P] Confirmar que la suite base de backend está en verde y que la cabeza de Alembic es `0003_ticket_timeline`, ejecutando `python -m pytest` desde `backend/` y revisando `backend/alembic/versions/0003_ticket_timeline.py`
- [X] T002 [P] Confirmar que la suite y el build base de frontend están en verde con `npm run test` y `npm run build`, según los scripts de `frontend/package.json`
- [X] T003 [P] Revisar el contrato HTTP y verificar que solo define operaciones `GET` y `POST`, sin `PUT`/`PATCH`/`DELETE`, en `specs/006-reasignar-escalar-ticket/contracts/assignee-change.openapi.yaml`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Esquema de datos, catálogo de niveles, DTOs compartidos, helpers de selección determinista y cliente frontend que necesitan todas las historias.

**⚠️ CRITICAL**: Ninguna historia de usuario puede comenzar hasta completar esta fase.

### Tests de la infraestructura compartida (escribir primero)

- [X] T004 [P] Escribir las pruebas unitarias del catálogo de niveles (orden total, etiquetas «Nivel 1»/«Nivel 2»/«Especialista», `higher_escalation_levels(especialista) == ()` y `is_higher_level` estricto) en `backend/tests/unit/test_escalation_levels.py`
- [X] T005 [P] Escribir las pruebas unitarias de selección determinista (exclusión del creador, preferencia de equipo, fallbacks: responsable sin equipo y nivel destino sin compañeros del mismo equipo, menor carga activa, desempate por `lower(name)` e `User.id`, pool vacío e independencia del orden de entrada) en `backend/tests/unit/test_assignee_selection.py`
- [X] T006 [P] Escribir las pruebas de contrato de los DTOs aditivos (enums, campos requeridos, `extra="forbid"`, `request_id: UUID`, `expected_updated_at: datetime`, casos de campo ausente o tipo inválido, ampliación de `WorkflowResponse` y `TimelineEntry`) en `backend/tests/contract/test_assignee_change_contract.py`

### Pruebas transversales (escribir primero)

> **NOTE: Estas pruebas se escriben y se comprueban en rojo en esta fase, antes de la implementación que las satisface.** Las tareas de US1, US2 y US5 se limitan después a ponerlas en verde; ninguna historia puede implementar permisos, concurrencia o inmutabilidad antes de que su prueba exista.

- [X] T070 [P] [US5] Escribir las pruebas de permisos, capacidades y estados (solo el técnico asignado vigente consulta y ejecuta; rol no técnico → `403 forbidden`; creador técnico no asignado → `403 forbidden` con precedencia sobre `not_ticket_assignee`; el creador que es el técnico asignado puede operar; técnico no asignado o anterior no creador → `403 not_ticket_assignee`; el técnico anterior conserva la lectura pública pero pierde `can_change_status`, `can_comment_internally`, `can_view_internal`, `can_reassign` y `can_escalate`, y el nuevo los adquiere; `abierto`, `en_progreso` y `pendiente_usuario` permitidos; `resuelto`/`cerrado` → `409 ticket_finalized`; sin token `401`; inexistente `404`; replay idéntico `200 changed=false` sin escribir) en `backend/tests/integration/test_assignee_change_permissions.py`
- [X] T071 [P] [US5] Escribir las pruebas de concurrencia en PostgreSQL (bloqueo `FOR UPDATE`, dos comandos simultáneos: uno escribe y otro recibe `409 stale_ticket`, sin entradas/notificaciones duplicadas y replay idéntico tras perder la asignación, comprobando `200 changed=false` y cero filas nuevas en timeline y notificaciones) en `backend/tests/integration/test_assignee_change_concurrency.py`
- [X] T079 [P] Añadir las pruebas de rendimiento en servidor (p95 < 300 ms en opciones, reasignación, escalado y listado de la cola con hasta 100 tickets activos por técnico, conforme a los objetivos de rendimiento del `plan.md`) en `backend/tests/integration/test_assignee_change_performance.py`
- [X] T086 [P] [US5] Escribir la prueba automática de inmutabilidad append-only (los routers de tickets y notificaciones no exponen `PUT`/`PATCH`/`DELETE`; un replay idéntico y los rechazos no crean ni modifican entradas de timeline ni notificaciones; la reasignación o el escalado no alteran entradas previas) en `backend/tests/integration/test_assignee_change_immutability.py`
- [X] T090 [P] Escribir las pruebas unitarias de `create_assignee_change_notification` (snapshots de número, título y nombre del responsable anterior; `recipient_id` igual al nuevo responsable; una notificación por `timeline_entry_id`; ausencia del motivo en la fila; la función añade a la sesión sin `commit()` ni escritura autónoma) en `backend/tests/unit/test_assignee_change_notification.py`
- [X] T091 Escribir las pruebas de latencia percibida en cliente (la entrada `assignee_change` aparece en la línea temporal en menos de 2 s percibidos tras confirmar, conforme a HU06-RF-013/HU06-SC-002, y la cola de trabajo refleja el traspaso en la siguiente actualización de 60 s, conforme a HU06-SC-005, con temporizadores falsos y `flushPromises`) en `frontend/tests/stores/ticketDetail.spec.ts` y `frontend/tests/unit/workQueue.store.spec.ts`

### Persistencia y modelos

- [X] T007 [P] Crear la migración `0004_assignee_changes` con `revision = "0004_assignee_changes"` y `down_revision = "0003_ticket_timeline"`: enums `escalation_level`, `assignee_change_kind` y `notification_type`, `users.escalation_level`, valor `assignee_change`, columnas/FKs/`ck_timeline_assignee_change`, tabla `notifications`, índices y `ix_users_role_active_level_team`, con `downgrade()` destructivo documentado en `backend/alembic/versions/0004_assignee_changes_notifications.py`
- [X] T008 Modificar `backend/app/models/enums.py` para añadir `EscalationLevel`, `ESCALATION_LEVEL_ORDER`, `ESCALATION_LEVEL_LABELS`, `AssigneeChangeKind`, `NotificationType` y el valor `TimelineEventType.assignee_change`
- [X] T009 Modificar `backend/app/models/user.py` para añadir `escalation_level` (`NOT NULL`, `server_default="nivel_1"`) y el índice compuesto `ix_users_role_active_level_team` sobre `(role, is_active, escalation_level, team)`
- [X] T010 Modificar `backend/app/models/timeline.py` para añadir las cinco columnas anulables (`previous_assignee_id`, `new_assignee_id`, `change_kind`, `from_escalation_level`, `to_escalation_level`), las relaciones `previous_assignee`/`new_assignee` con `foreign_keys` explícitas, la relación existente `author` con `foreign_keys=[author_id]` para desambiguar las tres FKs a `users`, y `ck_timeline_assignee_change`
- [X] T011 [P] Crear el modelo `Notification` con `ck_notifications_read_at`, `UNIQUE (timeline_entry_id)` e índices `ix_notifications_recipient_read_created` e `ix_notifications_ticket` en `backend/app/models/notification.py`
- [X] T012 Modificar `backend/app/models/__init__.py` para exportar `Notification`, `EscalationLevel`, `AssigneeChangeKind` y `NotificationType`

### Esquemas Pydantic compartidos

- [X] T013 [P] Crear los esquemas `AssigneeRef`, `EscalationTarget`, `AssigneeChangeOptions`, `AssigneeChangeResponse` (solo lectura), y `ReassignmentRequest`/`EscalationRequest` con `request_id: UUID` y `expected_updated_at: datetime` obligatorios; todos con `extra="forbid"` y sin `minLength`/`maxLength` en `reason`, en `backend/app/schemas/assignee_change.py`
- [X] T014 [P] Crear los esquemas `Notification`, `NotificationListResponse`, `NotificationPagination` y `MarkNotificationReadResponse`, con `page_size` propio `1..100` (defecto 20), sin reutilizar el `Pagination` de HU-05 (`le=200`), en `backend/app/schemas/notification.py`
- [X] T015 Modificar `backend/app/schemas/ticket_workflow.py` para ampliar `TimelineEntry` con `change_kind`, `previous_assignee`, `new_assignee`, `from_escalation_level(_label)` y `to_escalation_level(_label)`, y `WorkflowResponse` con `can_reassign` y `can_escalate`

### Servicios compartidos y seed

- [X] T016 Implementar las funciones puras `escalation_level_label`, `higher_escalation_levels` e `is_higher_level` en `backend/app/services/assignee_change.py`
- [X] T017 Implementar `reassignment_candidates` (rol `tecnico`, activo, mismo equipo si el actual tiene equipo, mismo nivel, excluyendo al responsable y al creador, orden `lower(name), id`) en `backend/app/services/assignee_change.py`
- [X] T018 Implementar `escalation_targets` y `select_escalation_assignee` con la regla determinista (pool del nivel sin el usuario creador, preferencia de equipo, menor carga activa, `lower(name)`, `User.id`) en `backend/app/services/assignee_change.py`
- [X] T021 Crear `create_assignee_change_notification(session, ticket, entry, previous_assignee, new_assignee, kind, now)` con snapshots y sin `commit()`, para participar en la transacción de los comandos de US1/US2, en `backend/app/services/notifications.py`
- [X] TXXX [Foundational] Verificar coherencia responsable ↔ última entrada `assignee_change` en la línea temporal: después de cada cambio, consultar la última entrada de tipo `assignee_change` y comparar con `tickets.assignee_id` mostrado; devolverá `409` si difieren, en `backend/app/services/assignee_change.py`
- [X] T023 [P] Actualizar `backend/scripts/seed_dev.py` con niveles de escalado, equipos y un escenario de creador técnico que permita validar candidatos y exclusiones
- [X] TXXX [Foundational] Implementar validador RF-031: en `ensure_assignee_change_actor` y comandos, verificar que `status`, `priority_id`, `category_id`, `sla_deadline` se conservan sin modificaciones ante cualquier error de validación, permisos, destino no válido o concurrencia; fallo suave sin escribir filas

### Base frontend compartida

- [X] T025 [P] Crear `frontend/src/types/assigneeChange.ts` con `EscalationLevel`, `AssigneeChangeKind`, `AssigneeRef`, `ReassignmentCandidate`, `EscalationTarget`, `AssigneeChangeOptions`, `ReassignmentRequest`, `EscalationRequest` y `AssigneeChangeResponse`, alineados con el OpenAPI
- [X] T026 [P] Modificar `frontend/src/types/ticketWorkflow.ts` para añadir `assignee_change` a `TimelineEventType`, los nuevos campos de `TimelineEntry` y `can_reassign`/`can_escalate` en `WorkflowResponse`
- [X] T027 Crear `frontend/src/services/assigneeChange.ts` con `getAssigneeChangeOptions`, `reassignTicket` y `escalateTicket` usando `apiGet`/`apiPost` y `AbortSignal`, en `frontend/src/services/assigneeChange.ts`
- [X] T028 Modificar `frontend/src/stores/ticketDetail.ts` para añadir el estado `canReassign`, `canEscalate`, `assigneeOptions`, `assigneeOptionsLoading`, `assigneeSubmitting`, `assigneeError`, `assigneeErrorCode`, `assigneeNotice` y la acción `loadAssigneeOptions(ticketId)` con descarte de respuestas fuera de orden

**Checkpoint**: Esquema, DTOs, catálogo, helpers de selección y creación de notificaciones listos. Las pruebas transversales de permisos, concurrencia, inmutabilidad, rendimiento en servidor, notificación y latencia percibida están escritas y en rojo. Las opciones de lectura, la serialización de timeline y los comandos se implementan dentro de su historia, después de las pruebas correspondientes. Las historias pueden comenzar.

---

## Phase 3: User Story 1 — Reasignar el ticket a otro técnico del equipo (Priority: P1) 🎯 MVP

**Goal**: El técnico asignado consulta candidatos de su equipo y nivel, elige un compañero, escribe un motivo y transfiere el ticket de forma atómica e idempotente.

**Independent Test**: Partiendo de un ticket activo asignado, `GET /assignee-change-options` devuelve compañeros del mismo equipo y nivel (sin el actual ni el creador); `POST /reassignments` con motivo cambia `assignee_id`, mantiene estado y campos inmutables, crea una entrada `assignee_change` y una notificación, y un replay idéntico devuelve `200 changed=false` sin escribir.

### Tests for User Story 1 ⚠️

> **NOTE: Escribir primero y comprobar que fallan antes de implementar.**

- [X] T029 [P] [US1] Escribir las pruebas de integración de reasignación (éxito, candidatos del mismo equipo/nivel, reasignación desde un responsable sin equipo → candidatos de todo el nivel, exclusiones, motivo de 1/5.000/0/5.001/solo espacios, `request_id` ausente o no UUID y `expected_updated_at` no ISO → `422 invalid_request` sin escritura, replay sin escritura, `request_id_reused`, campos inmutables, rollback si falla la notificación e invariante `último assignee_change.new_assignee_id == tickets.assignee_id` con `previous_assignee_id` igual al responsable anterior) en `backend/tests/integration/test_ticket_reassignment.py`
- [X] T030 [P] [US1] Escribir las pruebas del selector de compañeros (nombre/equipo/nivel, estado vacío, deshabilitado durante envío, `v-model`, accesibilidad `fieldset`/`legend`) en `frontend/tests/components/AssigneeSelector.spec.ts`
- [X] T031 [P] [US1] Escribir las pruebas del formulario de motivo (obligatorio tras `trim()`, contador 0–5.000, `maxlength`, error accesible y aviso de visibilidad pública) en `frontend/tests/components/AssigneeChangeReasonForm.spec.ts`
- [X] T032 [US1] Escribir las pruebas del panel en modo reasignación (carga de opciones, validación previa, `request_id` estable por firma, conflicto `stale_ticket`, replay `changed=false`, error de red, matriz de todos los códigos §14 aplicables a reasignación y emisión de `changed`/`notice`) en `frontend/tests/components/TicketAssigneeChangePanel.spec.ts`
- [X] T033 [US1] Extender las pruebas del store con el comando de reasignación, el refresco encadenado workflow → timeline → opciones, `assigneeSubmitting`, `assigneeErrorCode`, `assigneeNotice`, la conservación del motivo ante error, el descarte de respuestas fuera de orden y el mapeo de códigos de error (`stale_ticket`, `request_id_reused`, validación, `401` y red) en `frontend/tests/stores/ticketDetail.spec.ts`
- [X] T072 [P] [US1] Extender las pruebas de `TicketWorkflowPanel` para verificar que el panel de cambio de responsable no se monta si `canReassign` y `canEscalate` son ambos falsos y que se monta si alguno es verdadero, en `frontend/tests/components/TicketWorkflowPanel.spec.ts`

### Pruebas transversales de accesibilidad (escribir primero)

- [X] T081 [P] Añadir comprobaciones `axe-core` sin violaciones para el panel, los selectores y el motivo en `frontend/tests/components/TicketAssigneeChangePanel.spec.ts`

### Implementation for User Story 1

- [X] T019 [US1] Implementar el modelo de lectura `get_assignee_change_options` con `current_assignee`, `has_reassignment_candidates`, `has_available_escalation_target`, candidatos y niveles superiores en `backend/app/services/assignee_change.py`
- [X] T020 [US1] Modificar `backend/app/services/ticket_workflow.py` para añadir el helper público `ensure_assignee_change_actor` (rol no técnico → `403 forbidden`; creador técnico no asignado → `403 forbidden` con precedencia sobre `not_ticket_assignee`; el creador asignado puede operar; técnico no asignado no creador → `403 not_ticket_assignee`), sin alterar `_ensure_writer` de HU-05, y calcular `can_reassign`/`can_escalate` en `get_workflow` según rol, asignación vigente, estado activo y nivel del asignado
- [X] T022 [US1] Añadir `GET /api/v1/tickets/{ticket_id}/assignee-change-options` en `backend/app/api/v1/tickets.py`, con `ensure_assignee_change_actor`, `404 ticket_not_found`, `403 forbidden`/`not_ticket_assignee`, `409 ticket_finalized` y cabeceras `Cache-Control: no-store`/`Vary: Authorization`
- [X] T034 [US1] Implementar `reassign_ticket` con el orden de validación 1–11 (replay antes de `ensure_assignee_change_actor`, motivo, `expected_updated_at`, estado activo, autoasignación, creador, destino válido y disponible), bloqueo `FOR UPDATE`, escritura atómica de ticket + entrada + notificación y rollback a `500 internal_error`, en `backend/app/services/assignee_change.py`
- [X] T035 [US1] Añadir `POST /api/v1/tickets/{ticket_id}/reassignments` con `ReassignmentRequest`/`AssigneeChangeResponse`, documentación de `401/403/404/409/422/500` y cabeceras no-store, en `backend/app/api/v1/tickets.py`
- [X] T036 [P] [US1] Crear `AssigneeSelector.vue` con `<fieldset>`/`<legend>`, `<select>` nativo, nombre + equipo + nivel, estado vacío «No hay compañeros disponibles de tu equipo y nivel.» y `aria-required`/`aria-describedby`, en `frontend/src/components/tickets/AssigneeSelector.vue`
- [X] T037 [P] [US1] Crear `AssigneeChangeReasonForm.vue` con `<textarea rows="4" maxlength="5000">`, contador `trim().length / 5000`, ayuda de visibilidad pública, `aria-invalid` y error con `role="alert"`, en `frontend/src/components/tickets/AssigneeChangeReasonForm.vue`
- [X] T038 [US1] Crear `TicketAssigneeChangePanel.vue` en modo reasignación: carga de opciones con `AbortController`, validación de destino y motivo, `request_id` estable por firma `mode|destino|reason.trim()`, envío y mapeo exhaustivo de los códigos de `contracts/frontend-components.md` §14 aplicables a reasignación (`reason_required`, `reason_too_long`, `self_reassignment`, `creator_not_assignable`, `invalid_reassignment_target`, `assignee_unavailable`, `stale_ticket`, `request_id_reused`, `ticket_finalized`, `forbidden`, `not_ticket_assignee`, `not_authenticated`, `invalid_request`, red/500) y emisiones `changed`/`notice`, en `frontend/src/components/tickets/TicketAssigneeChangePanel.vue`
- [X] T039 [US1] Integrar el panel en `frontend/src/components/tickets/TicketWorkflowPanel.vue`, montándolo solo si `canReassign || canEscalate`, pasando `ticketId`, `ticket`, capacidades y `disabled`, y recargando workflow/timeline al recibir `changed`
- [X] T040 [US1] Extender `frontend/src/stores/ticketDetail.ts` con la acción `reassign(ticketId, payload)` y `refreshAfterAssigneeChange(ticketId)` (workflow + timeline + opciones si sigue siendo responsable), conservando el motivo, gestionando `assigneeSubmitting`, `assigneeError`/`assigneeErrorCode` y `assigneeNotice`, y recalculando capacidades tras el éxito

**Checkpoint**: US1 funcional y demostrable de extremo a extremo: reasignación real, entrada en línea temporal y notificación creada en la misma transacción.

---

## Phase 4: User Story 2 — Escalar el ticket a un nivel superior (Priority: P1)

**Goal**: El técnico asignado elige un nivel estrictamente superior; el backend selecciona al nuevo responsable de forma determinista y aplica el cambio de forma atómica.

**Independent Test**: Partiendo de un ticket de Nivel 1, las opciones solo ofrecen Nivel 2 y Especialista; `POST /escalations` con `target_level=nivel_2` asigna un técnico activo de Nivel 2, registra `to > from`, mantiene el estado y crea una notificación; en Especialista devuelve `409 no_higher_level` y sin técnicos `409 no_technicians_available`.

### Tests for User Story 2 ⚠️

- [X] T041 [P] [US2] Escribir las pruebas de integración de escalado (selección determinista, preferencia de equipo, escalado sin técnicos del mismo equipo → pool completo del nivel destino, exclusión del usuario creador, nivel máximo, `no_higher_level`, `no_technicians_available`, nivel no superior, payload sin `assignee_id`, replay sin duplicados, `to > from` e invariante `último assignee_change.new_assignee_id == tickets.assignee_id`) en `backend/tests/integration/test_ticket_escalation.py`
- [X] T042 [P] [US2] Escribir las pruebas del selector de nivel (solo niveles superiores, niveles sin técnicos deshabilitados con texto, nunca envía `assignee_id`, estado vacío en nivel máximo) en `frontend/tests/components/EscalationLevelSelector.spec.ts`
- [X] T043 [P] [US2] Extender las pruebas de contrato con la ruta de escalado, `EscalationRequest` (sin `assignee_id`), `EscalationLevel` y los errores `no_higher_level`/`invalid_escalation_level`/`no_technicians_available` en `backend/tests/contract/test_assignee_change_contract.py`
- [X] T044 [US2] Extender las pruebas del panel con el modo escalado (solo niveles del backend, deshabilitado de niveles no disponibles, envío sin persona, replay y matriz de códigos de escalado) en `frontend/tests/components/TicketAssigneeChangePanel.spec.ts`

### Implementation for User Story 2

- [X] T045 [US2] Implementar `escalate_ticket` reutilizando el orden de validación y la idempotencia de US1, con `no_higher_level` antes de `invalid_escalation_level`, `no_technicians_available`, selección determinista, replay comparado por nivel y escritura atómica de ticket + entrada + notificación, en `backend/app/services/assignee_change.py`
- [X] T046 [US2] Añadir `POST /api/v1/tickets/{ticket_id}/escalations` con `EscalationRequest`/`AssigneeChangeResponse` y documentación de `409/422` de catálogo, en `backend/app/api/v1/tickets.py`
- [X] T047 [US2] Crear `EscalationLevelSelector.vue` con `<fieldset>`/`<legend>`, render de `label`, texto «Sin técnicos disponibles» y control deshabilitado si `is_available = false`, y estado vacío «El ticket ya está en el nivel máximo de soporte.», en `frontend/src/components/tickets/EscalationLevelSelector.vue`
- [X] T048 [US2] Extender `TicketAssigneeChangePanel.vue` con el modo escalado: radios de tipo de cambio, `EscalationLevelSelector`, envío a `/escalations`, mapeo de `no_higher_level`, `no_technicians_available`, `invalid_escalation_level`, `invalid_request`, `not_authenticated` y red/500, y refresco tras éxito, en `frontend/src/components/tickets/TicketAssigneeChangePanel.vue`
- [X] T049 [US2] Extender `frontend/src/stores/ticketDetail.ts` con la acción `escalate(ticketId, payload)` y su integración en `refreshAfterAssigneeChange`, reutilizando `assigneeSubmitting`, `assigneeError`/`assigneeErrorCode` y `assigneeNotice`, sin duplicar la lógica de reasignación

**Checkpoint**: US1 y US2 funcionan de forma independiente y comparten catálogo, opciones, idempotencia y patrón transaccional.

---

## Phase 5: User Story 3 — Registrar el cambio de responsable en la línea temporal (Priority: P1)

**Goal**: Cada reasignación o escalado aparece como una entrada append-only con autor, responsables, tipo, niveles, motivo y fecha, visible para el creador y ordenada con el resto de hechos.

**Independent Test**: Tras reasignar y escalar un ticket, la línea temporal muestra las entradas `assignee_change` en orden cronológico con todos sus campos; el creador las ve junto a estados y resoluciones, no ve comentarios internos, y los intentos rechazados o replays no añaden entradas.

### Tests for User Story 3 ⚠️

- [X] T050 [P] [US3] Extender las pruebas de visibilidad y orden de la línea temporal (entradas `assignee_change` intercaladas; visibilidad del creador; el técnico anterior conserva la lectura de la línea temporal pública pero pierde `can_view_internal` y los comentarios internos, y el nuevo responsable los adquiere; rechazos y replays sin entradas nuevas) en `backend/tests/integration/test_timeline_visibility.py`
- [X] T051 [P] [US3] Extender las pruebas de `TicketTimeline` con la rama `assignee_change` (tipo, subtipo reasignación/escalado, responsables, niveles, motivo como texto plano, sin `v-html` y orden cronológico) en `frontend/tests/components/TicketTimeline.spec.ts`

### Implementation for User Story 3

- [X] T024 [US3] Extender `backend/app/services/ticket_timeline.py` para serializar las entradas `assignee_change` (responsables, tipo, niveles y etiquetas) sin romper las entradas existentes de HU-05 y conservando la serialización de `author` con la relación desambiguada
- [X] T052 [US3] Ajustar `get_timeline` en `backend/app/services/ticket_timeline.py` para mantener el orden `created_at, event_order, id`, cargar las relaciones `previous_assignee`/`new_assignee` y `author` sin N+1 y conservar `viewer_capabilities` para creador y responsables
- [X] T053 [US3] Extender `TicketTimeline.vue` con la rama `entry.type === 'assignee_change'`: etiqueta «Cambio de responsable», subtipo «Reasignación»/«Escalado a {nivel}», texto con autor y responsables, bloque «Motivo» en texto plano y estilo público con etiquetas textuales, en `frontend/src/components/tickets/TicketTimeline.vue`

- [X] T092 [P] [US3] Extender pruebas de visibilidad y orden de la línea temporal para diferenciar claramente entradas assignee_change de tipo reasignación vs escalado, incluyendo validación de que el frontend muestra subtipo correcto y el backend serializa change_kind apropiado, conforme a HU06-RF-012 y HU06-SC-002

**Checkpoint**: La trazabilidad es completa, inmutable y visible para el creador sin lógica de visibilidad en cliente.

---

## Phase 6: User Story 4 — Notificar al nuevo responsable y trasladar el ticket a su cola (Priority: P1)

**Goal**: El nuevo responsable recibe una notificación en la misma transacción, la ve en la campana en menos de 30 s, accede al ticket y lo encuentra en su cola de trabajo.

**Independent Test**: Tras un cambio, existe exactamente una notificación con snapshots para el nuevo responsable; `GET /me/notifications` la devuelve ordenada con `unread_count` global y paginación; `POST /me/notifications/{id}/read` es idempotente y devuelve `404` para notificaciones ajenas; el ticket aparece en la cola del nuevo responsable y desaparece de la del anterior.

### Tests for User Story 4 ⚠️

- [X] T054 [P] [US4] Escribir las pruebas de integración de notificaciones (una por cambio por `UNIQUE (timeline_entry_id)`, snapshots, orden, `unread_count` global, `unread_only`, paginación con `page_size` 1/20/100 válidos y 0/101 → `422 invalid_request`, lectura idempotente, notificación ajena `404`, la notificación no aparece en la bandeja de otro usuario, ausencia del motivo y persistencia con destinatario desconectado: la notificación sigue no leída y aparece al reconectar) en `backend/tests/integration/test_notifications.py`
- [X] T055 [P] [US4] Escribir las pruebas de la campana (contador, `aria-live`, apertura/cierre con teclado y `Escape`, foco gestionado, estados de carga/vacío/error y comprobaciones `axe-core` sin violaciones) en `frontend/tests/components/NotificationBell.spec.ts`, y de `AppHeader` (montaje de la campana y ausencia de sondeo sin token) en `frontend/tests/components/AppHeader.spec.ts`
- [X] T056 [P] [US4] Escribir las pruebas de la lista (distinción textual de no leídas, navegación al ticket, marcado de lectura idempotente, actualización del contador y notificación ajena no visible) en `frontend/tests/components/NotificationList.spec.ts`
- [X] T057 [P] [US4] Escribir las pruebas del store de notificaciones (sondeo de 15 s con temporizadores falsos, notificación visible en la campana en ≤ 30 s desde el comando, pausa con pestaña oculta, refresco al recuperar foco/visibilidad, `AbortController`, contador calculado en servidor y `401` que limpia la bandeja y detiene el sondeo) en `frontend/tests/stores/notifications.spec.ts`
- [X] T058 [US4] Extender las pruebas de contrato con `/me/notifications`, `/me/notifications/{id}/read`, `NotificationListResponse`, `MarkNotificationReadResponse` y `404 notification_not_found` en `backend/tests/contract/test_assignee_change_contract.py`
- [X] T059 [P] [US4] Extender las pruebas de la cola de trabajo para verificar que el ticket aparece para el nuevo responsable y desaparece para el anterior tras el cambio, en `backend/tests/integration/test_work_queue_api.py`

### Implementation for User Story 4

- [X] T060 [US4] Implementar `list_notifications` (orden `created_at DESC, id DESC`, `unread_count` global, `unread_only`) y `mark_notification_read` (idempotente, `404 notification_not_found` para ajenas) en `backend/app/services/notifications.py`
- [X] T061 [US4] Crear `GET /api/v1/me/notifications` y `POST /api/v1/me/notifications/{notification_id}/read` con validación de paginación `1..100`, `Cache-Control: no-store` y `Vary: Authorization`, en `backend/app/api/v1/notifications.py`
- [X] T062 [US4] Registrar el router de notificaciones con `include_router` en `backend/app/api/v1/router.py`
- [X] T063 [P] [US4] Crear `frontend/src/types/notifications.ts` con `NotificationType`, `Notification`, `NotificationListResponse` y `MarkNotificationReadResponse`
- [X] T064 [US4] Crear `frontend/src/services/notifications.ts` con `getNotifications` y `markNotificationRead`, soportando `AbortSignal`
- [X] T065 [US4] Crear `frontend/src/stores/notifications.ts` con estado de bandeja/contador, `loadNotifications`, `markRead`, `POLL_INTERVAL_MS = 15_000`, pausa con pestaña oculta, refresco al recuperar foco/visibilidad, `AbortController`, secuencia anti-desorden y limpieza de bandeja/contador con parada del sondeo ante `401`
- [X] T066 [US4] Crear `NotificationList.vue` con `<ul>/<li>`, título por tipo, `ticket_number`, `ticket_title`, «Anterior responsable», fecha en `Europe/Madrid`, etiqueta textual «No leída», estados de carga/error/vacío y navegación al ticket, en `frontend/src/components/notifications/NotificationList.vue`
- [X] T067 [US4] Crear `NotificationBell.vue` con icono de campana, `aria-label` «Notificaciones, N sin leer», `aria-expanded`/`aria-controls`, contador, `aria-live="polite"`, desplegable, cierre con `Escape`/clic fuera y gestión de foco, en `frontend/src/components/notifications/NotificationBell.vue`
- [X] T068 [US4] Crear `AppHeader.vue` que monte `NotificationBell`, arranque el sondeo al montar solo si existe `getAccessToken()` y lo detenga en `onUnmounted`, en `frontend/src/components/layout/AppHeader.vue`
- [X] T069 [US4] Modificar `frontend/src/App.vue` para montar `AppHeader` fuera de `RouterView` y ocultarlo en la ruta `login`

- [X] T094 [P] [US4] Extender pruebas de notificación para verificar atomicidad transaccional: si falla la inserción de la entrada de línea temporal, la notificación tampoco se crea y el rollback es completo (comprobar cero filas nuevas en las tres tablas, conforme a HU06-RF-028 y HU06-SC-001)

**Checkpoint**: Notificación, bandeja, contador y traslado de cola cierran el ciclo del traspaso sin cambios en el sondeo de 60 s de la cola.

---

## Phase 7: User Story 5 — Aclarar quién puede reasignar y en qué estados (Priority: P2)

**Goal**: Solo el técnico asignado vigente puede consultar opciones y ejecutar comandos, solo en estados activos, con rechazos consistentes y sin escrituras parciales ante concurrencia.

**Independent Test**: Con usuarios de cada rol y tickets en cada estado, se comprueba que los roles no técnicos reciben `403 forbidden`, el creador técnico no asignado recibe `403 forbidden` con precedencia, el creador asignado puede operar, el técnico no asignado o anterior recibe `403 not_ticket_assignee` y conserva solo la lectura pública, el nuevo responsable adquiere las capacidades, sin token `401`, ticket inexistente `404`, finalizado `409 ticket_finalized`; dos comandos concurrentes producen un éxito y un `409 stale_ticket` sin duplicados.

### Tests for User Story 5 ⚠️

- [X] T073 [US5] Extender las pruebas del panel con los estados de acceso denegado (`403 forbidden`/`403 not_ticket_assignee`), ticket finalizado (`409 ticket_finalized`), sesión expirada (`401 not_authenticated`), payload inválido (`422 invalid_request`), error de red con reintento y desaparición del panel tras perder la asignación, en `frontend/tests/components/TicketAssigneeChangePanel.spec.ts`
- [X] T074 [US5] Extender las pruebas de contrato con el catálogo completo de códigos y estados HTTP (`401/403/404/409/422/500`) de las cinco rutas, verificando el `code` estable de cada error, la normalización de payloads mal formados a `422 invalid_request` y que ningún rechazo escribe filas, en `backend/tests/contract/test_assignee_change_contract.py`
- [X] T089 [P] [US5] Extender las pruebas de `TicketWorkflowPanel` para verificar que, tras perder la asignación, las capacidades se recalculan, el panel de cambio de responsable desaparece y se muestra «Este ticket ya no está asignado a ti.» sin dejar controles activos, en `frontend/tests/components/TicketWorkflowPanel.spec.ts`

### Implementation for User Story 5

- [X] T075 [US5] Endurecer en `backend/app/services/assignee_change.py` las guardas de rol/asignación/estado mediante `ensure_assignee_change_actor` y el orden `request_id` → autorización (con la precedencia de RN-11: rol no técnico y creador técnico no asignado → `forbidden`) → motivo → versión → estado, garantizando `403 forbidden`/`not_ticket_assignee`, `409 ticket_finalized` y `409 stale_ticket` sin escrituras
- [X] T076 [US5] Extender `TicketAssigneeChangePanel.vue` con los estados `403 forbidden`/`403 not_ticket_assignee`, `409 ticket_finalized`, `401 not_authenticated`, `422 invalid_request` y error de red con «Reintentar», emitiendo una recarga del workflow cuando el actor deja de ser responsable, en `frontend/src/components/tickets/TicketAssigneeChangePanel.vue`
- [X] T077 [US5] Ajustar `TicketWorkflowPanel.vue` para ocultar el panel cuando las capacidades sean falsas y mostrar el aviso «Este ticket ya no está asignado a ti.» sin dejar controles activos, en `frontend/src/components/tickets/TicketWorkflowPanel.vue`
- [X] T078 [US5] Añadir observabilidad estructurada: `INFO` por comando exitoso (`ticket_id`, `actor_id`, responsables, `change_kind`, niveles, `changed`, `request_id`, `duration_ms`), `WARNING` en rechazos y `ERROR` con `logger.exception`, en `backend/app/services/assignee_change.py`

- [X] T093 [P] [US5] Escribir prueba automática de inmutabilidad reforzada (los routers y servicios no exponen `PUT`/`PATCH`/`DELETE` sobre timeline_entries de tipo assignee_change; un replay idéntico y los rechazos no crean ni modifican entradas previas; validar que intentos de edición devuelvan 405 método_no_permitido, conforme a HU06-RN-07 y HU06-RF-014)

- [X] T095 [P] [US5] Extender pruebas del panel TicketWorkflowPanel para verificar que, cuando el responsable mostrado en el ticket difiere de la última entrada assignee_change en la línea temporal, el panel muestra aviso de inconsistencia y bloquea acciones hasta la corrección, conforme a HU06-RF-033 y HU06-SC-001

**Checkpoint**: Las reglas de propiedad y estados finales quedan protegidas en backend y reflejadas en la interfaz.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Rendimiento, migración real, accesibilidad, contrato completo, inmutabilidad append-only, revisión de seguridad de datos internos y validación final del quickstart.

- [X] T080 [P] Verificar la migración en PostgreSQL con `alembic upgrade head`, `alembic downgrade -1` y `alembic upgrade head`, comprobando enum `assignee_change`, columnas, índices y supervivencia de datos de HU-04/HU-05, sobre `backend/alembic/versions/0004_assignee_changes_notifications.py`
- [X] T082 [P] Validar que recursos, DTOs, estados HTTP y códigos de error coinciden con el OpenAPI y que los campos nuevos son aditivos, en `backend/tests/contract/test_assignee_change_contract.py`
- [X] T083 Ejecutar la suite completa de backend (`python -m pytest`) según `backend/pytest.ini` con `TEST_DATABASE_URL` configurada, incluyendo regresiones de HU-04 y HU-05, y fallar el gate si alguna prueba queda omitida por falta de base de datos
- [X] T084 Ejecutar `npm run test` y `npm run build` según `frontend/package.json`, verificando que los DTOs ampliados compilan sin `any`
- [X] T085 Ejecutar de extremo a extremo los escenarios de `specs/006-reasignar-escalar-ticket/quickstart.md` (reasignación, escalado, colas, notificación, replay, conflicto, permisos, snapshot inmutable y coherencia responsable ↔ última entrada `assignee_change`) y registrar el resultado
- [X] T087 [P] Revisar y registrar la evidencia de la revisión de seguridad de la visibilidad de datos internos exigida por la constitución (§Flujo de desarrollo, punto 4): precedencia del rol no técnico y del creador técnico no asignado sobre `not_ticket_assignee`, comentarios internos no serializados para creador ni técnicos no asignados, `can_view_internal` revocado al técnico anterior, motivo ausente del payload de notificación y de los logs, y opciones sin creador ni responsable actual, con prueba en `backend/tests/integration/test_assignee_change_permissions.py` y nota en `quickstart.md`
- [X] T088 Ejecutar la suite de concurrencia real sobre PostgreSQL 16 con `TEST_DATABASE_URL` configurada (`python -m pytest -m postgres` desde `backend/`), comprobando que `test_assignee_change_concurrency.py` se ejecuta y no se omite, registrar el resultado como evidencia de la puerta de calidad del Principio IV y revisar/limpiar duplicaciones antes de cerrar

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Sin dependencias; puede empezar de inmediato.
- **Foundational (Phase 2)**: Depende de Setup y BLOQUEA todas las historias.
- **User Stories (Phases 3–7)**: Dependen de Foundational. US1, US2, US3 y US4 pueden avanzar en paralelo si se respetan los archivos compartidos; US5 requiere US1 y US2 implementados y no puede cerrarse hasta que `T070`, `T071` y `T086` estén en verde.
- **Polish (Phase 8)**: Depende de todas las historias deseadas.

### User Story Dependencies

- **US1 (P1)**: Tras Foundational; no depende de otras historias. Es el MVP.
- **US2 (P1)**: Tras Foundational; reutiliza catálogo, opciones e idempotencia, pero se prueba con su propia suite. Comparte `assignee_change.py` y `tickets.py` con US1, por lo que esas tareas no son paralelas entre sí.
- **US3 (P1)**: Tras Foundational; el backend ya serializa `assignee_change` (T024) y el frontend depende de los tipos de T026. Puede avanzar en paralelo con US1/US2 para la vista, pero su prueba de orden requiere que US1 o US2 generen entradas.
- **US4 (P1)**: Tras Foundational; la creación de la notificación (`T021`) y su prueba unitaria (`T090`) ya están en Foundational, y la bandeja es independiente. Puede avanzar en paralelo con US1/US2/US3.
- **US5 (P2)**: Sus pruebas (`T070`, `T071`, `T086`) se escriben en Foundational; la implementación de guardas requiere US1 y US2 implementados y las pone en verde.

### Within Each User Story

- Las pruebas se escriben y fallan antes de la implementación. Las pruebas transversales de Phase 2 (`T070`, `T071`, `T079`, `T086`, `T090`, `T091`) deben existir y fallar antes de implementar los comandos, las guardas, la notificación y el refresco de cliente que las satisfacen.
- Modelos/esquemas antes que servicios; servicios antes que endpoints; backend antes de la integración frontend.
- Las tareas que tocan el mismo archivo (`assignee_change.py`, `tickets.py`, `TicketAssigneeChangePanel.vue`, `TicketWorkflowPanel.vue`, `ticketDetail.ts`, `ticketDetail.spec.ts`, `test_assignee_change_contract.py`, `test_assignee_change_permissions.py`, `TicketAssigneeChangePanel.spec.ts`) se ejecutan en secuencia, nunca en paralelo.
- Completar y validar una historia antes de pasar a la siguiente prioridad, comprobando que sus pruebas rojas de Phase 2 pasan a verde.

### Parallel Opportunities

- T001–T003 (Setup) en paralelo.
- T004–T006, T070, T071, T079, T086 y T090 (pruebas fundacionales) en paralelo; T091 comparte `ticketDetail.spec.ts` con T033 y se ejecuta antes y en secuencia con él.
- T007–T012 (persistencia/modelos) pueden repartirse; T008–T012 comparten imports, revisar antes de fusionar.
- T013–T015 (esquemas) en paralelo; T025–T026 (tipos frontend) en paralelo.
- T023 (seed) en paralelo con T016–T018; T021 se implementa después de T011/T090 y antes de T034/T045. T019/T022/T034/T035 comparten `assignee_change.py`/`tickets.py` y deben ejecutarse en secuencia; T020 toca `ticket_workflow.py`, y T024/T052 comparten `ticket_timeline.py`, por lo que tampoco son paralelas entre sí.
- Dentro de US1: T029–T031 en paralelo; T036–T037 en paralelo (componentes distintos); T072 se ejecuta antes de T039 y comparte archivo con T089 de US5.
- Dentro de US2: T041–T043 en paralelo; T047 es independiente del backend.
- Dentro de US4: T054–T057 y T059 en paralelo; T063–T064 en paralelo; T066–T068 secuenciales por dependencia de composición.
- US3 y US4 pueden ejecutarse en paralelo con US1/US2 por equipos distintos, salvo archivos compartidos.

---

## Parallel Example: User Story 1

```bash
# Pruebas de US1 en paralelo (archivos distintos)
Task: "Pruebas de integración de reasignación en backend/tests/integration/test_ticket_reassignment.py"
Task: "Pruebas de AssigneeSelector en frontend/tests/components/AssigneeSelector.spec.ts"
Task: "Pruebas de AssigneeChangeReasonForm en frontend/tests/components/AssigneeChangeReasonForm.spec.ts"

# Componentes de US1 en paralelo (archivos distintos)
Task: "Crear AssigneeSelector.vue en frontend/src/components/tickets/AssigneeSelector.vue"
Task: "Crear AssigneeChangeReasonForm.vue en frontend/src/components/tickets/AssigneeChangeReasonForm.vue"
```

## Parallel Example: User Story 2

```bash
# Pruebas de US2 en paralelo (archivos distintos)
Task: "Pruebas de integración de escalado en backend/tests/integration/test_ticket_escalation.py"
Task: "Pruebas de EscalationLevelSelector en frontend/tests/components/EscalationLevelSelector.spec.ts"

# Implementación independiente
Task: "Crear EscalationLevelSelector.vue en frontend/src/components/tickets/EscalationLevelSelector.vue"
```

## Parallel Example: User Story 4

```bash
# Pruebas de US4 en paralelo (archivos distintos)
Task: "Pruebas de integración de notificaciones en backend/tests/integration/test_notifications.py"
Task: "Pruebas de NotificationBell en frontend/tests/components/NotificationBell.spec.ts"
Task: "Pruebas de NotificationList en frontend/tests/components/NotificationList.spec.ts"
Task: "Pruebas del store de notificaciones en frontend/tests/stores/notifications.spec.ts"

# Tipos y servicio en paralelo
Task: "Crear tipos en frontend/src/types/notifications.ts"
Task: "Crear servicio en frontend/src/services/notifications.ts"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Completar Phase 1: Setup.
2. Completar Phase 2: Foundational (CRÍTICO: bloquea todo).
3. Completar Phase 3: US1 (reasignación).
4. **STOP and VALIDATE**: ejecutar `backend/tests/integration/test_ticket_reassignment.py` y las pruebas de componentes/store de US1.
5. Demostrar la reasignación con entrada de línea temporal y notificación creada en la misma transacción.

### Incremental Delivery

1. Setup + Foundational → base lista (migración, modelos, DTOs, catálogo y helpers de selección).
2. US1 → validar y desplegar (MVP de reasignación).
3. US2 → validar escalado y desplegar.
4. US3 → validar trazabilidad y visibilidad y desplegar.
5. US4 → validar notificación, campana y traslado de cola y desplegar.
6. US5 → validar permisos, estados y concurrencia y desplegar.
7. Polish → rendimiento, migración real, accesibilidad y quickstart.

### Parallel Team Strategy

1. Todo el equipo completa Setup + Foundational.
2. Después:
   - Desarrollador A: US1 (reasignación).
   - Desarrollador B: US2 (escalado) tras estabilizar los helpers compartidos.
   - Desarrollador C: US4 (notificaciones y campana).
   - Desarrollador D: US3 (línea temporal) y US5 (guardas) cuando US1/US2 estén disponibles.
3. Integrar respetando los archivos compartidos indicados en las dependencias.

---

## Notes

- `[P]` significa archivos distintos y sin dependencias pendientes; no aplicar a tareas que comparten archivo.
- La etiqueta `[USn]` traza cada tarea a su historia y permite validar el MVP por separado.
- Cada historia debe poder completarse y probarse de forma independiente; las dependencias compartidas están aisladas en Foundational.
- Verificar que las pruebas fallan antes de implementar y que los replays no escriben filas nuevas.
- Las pruebas transversales de Phase 2 (`T070`, `T071`, `T079`, `T086`, `T090`, `T091`) son la evidencia del Principio IV: se escriben y fallan antes de la implementación que las satisface.
- No se añaden `PUT`, `PATCH` ni `DELETE`; el marcado de lectura es un `POST` idempotente.
- Confirmar que `status`, `priority_id`, `category_id`, `sla_deadline`, `sla_version`, `finalized_at` y `closed_at` no cambian en ningún comando.
- Hacer commit tras cada tarea o grupo lógico y detenerse en cada checkpoint para validar la historia.

## Phase 9: Convergence

- [X] T096 Cerrado (FR-001 / RN-01): `backend/app/services/assignee_change.py` implementa opciones, reasignación y escalado; cubierto por `test_ticket_reassignment.py` y `test_ticket_escalation.py`
- [X] T097 Cerrado (RF-005 / plan: decisiones de API): `GET /tickets/{id}/assignee-change-options`, `POST /tickets/{id}/reassignments` y `POST /tickets/{id}/escalations` en `backend/app/api/v1/tickets.py`
- [X] T098 Cerrado (RN-02 / data-model.md): `users.escalation_level` con `EscalationLevel`, `ESCALATION_LEVEL_ORDER` y `ESCALATION_LEVEL_LABELS`
- [X] T099 Cerrado (data-model.md): columnas `previous_assignee_id`, `new_assignee_id`, `change_kind`, `from_escalation_level`, `to_escalation_level` y `ck_timeline_assignee_change` en `ticket_timeline_entries`
- [X] T100 Cerrado (RF-016 / RN-08 / data-model.md): modelo `Notification` y tabla `notifications` con `ix_notifications_recipient_read_created` e `ix_notifications_ticket`
- [X] T101 Cerrado (US1–US4 / plan: componentes frontend): `TicketAssigneeChangePanel`, `AssigneeSelector`, `AssigneeChangeReasonForm`, `EscalationLevelSelector`, `NotificationBell` y `NotificationList`
- [X] T102 Cerrado (plan: esquemas de API): `backend/app/schemas/assignee_change.py` y `backend/app/schemas/notification.py`

## Phase 10: Convergence

- [X] T103 CRITICAL — Crear la migración de Alembic `0004_assignee_changes_notifications` (`revision = "0004_assignee_changes"`, `down_revision = "0003_ticket_timeline"`) con enums, `users.escalation_level`, índice `ix_users_role_active_level_team`, columnas/FK/constraint de `ticket_timeline_entries`, tabla `notifications` con unicidad e índices, y `upgrade()`/`downgrade()` verificables, en `backend/alembic/versions/0004_assignee_changes_notifications.py` per Constitution II / plan: migración
- [X] T104 CRITICAL — Implementar la autorización de servidor y las capacidades del cambio de responsable: `ensure_assignee_change_actor` con la precedencia de RN-11 (rol no técnico → `403 forbidden`; creador técnico no asignado → `403 forbidden`; técnico no asignado → `403 not_ticket_assignee`) y `can_reassign`/`can_escalate` en `get_workflow` y en `WorkflowResponse`, sin alterar `_ensure_writer` de HU-05, en `backend/app/services/ticket_workflow.py` y `backend/app/schemas/ticket_workflow.py` per Constitution III / RN-11 / US5
- [X] T105 CRITICAL — Escribir las pruebas ejecutables de backend de HU-06 (unitarias de catálogo de niveles, selección determinista y notificación; integración de reasignación, escalado, permisos, concurrencia PostgreSQL, inmutabilidad, rendimiento, notificaciones y traspaso de cola; contrato HTTP completo) en `backend/tests/unit/`, `backend/tests/integration/` y `backend/tests/contract/test_assignee_change_contract.py` per Constitution IV / plan: estrategia de pruebas
- [X] T106 CRITICAL — Escribir las pruebas ejecutables de frontend de HU-06 (componentes con `axe-core`, panel y modos, selectores, motivo, campana y lista, `AppHeader`, línea temporal y stores de ticket/notificaciones) en `frontend/tests/components/` y `frontend/tests/stores/` per Constitution IV / plan: estrategia de pruebas
- [X] T107 Implementar `create_assignee_change_notification`, `list_notifications` y `mark_notification_read` con snapshots, `unread_count` global, `unread_only`, paginación `1..100`, lectura idempotente y `404 notification_not_found` para notificaciones ajenas, en `backend/app/services/notifications.py` per FR-016…FR-020 / plan: §2.8
- [X] T108 Crear `GET /api/v1/me/notifications` y `POST /api/v1/me/notifications/{notification_id}/read` con `Cache-Control: no-store` y `Vary: Authorization`, y registrar el router en `backend/app/api/v1/router.py`, en `backend/app/api/v1/notifications.py` per FR-018/FR-019 / plan: §2.9
- [X] T109 Extender `backend/app/services/ticket_timeline.py` para serializar las entradas `assignee_change` con autor, responsables, `change_kind`, niveles y etiquetas, cargar `previous_assignee`/`new_assignee` sin N+1 y conservar el orden `created_at, event_order, id` y la visibilidad del creador, en `backend/app/services/ticket_timeline.py` per FR-011…FR-015 / US3
- [X] T110 Ampliar `TimelineEntry` con `change_kind`, `previous_assignee`, `new_assignee`, `from_escalation_level(_label)` y `to_escalation_level(_label)` en `backend/app/schemas/ticket_workflow.py` per plan: DTO de línea temporal
- [X] T111 Crear `frontend/src/types/assigneeChange.ts`, `frontend/src/types/notifications.ts`, `frontend/src/services/assigneeChange.ts`, `frontend/src/services/notifications.ts` y `frontend/src/stores/notifications.ts`, y extender `frontend/src/types/ticketWorkflow.ts` y `frontend/src/stores/ticketDetail.ts` con opciones, comandos, capacidades, descarte de respuestas fuera de orden y refresco encadenado workflow → timeline → opciones per FR-001/FR-006/FR-018 / plan: §3.8
- [X] T112 Crear `frontend/src/components/layout/AppHeader.vue` y montarlo en `frontend/src/App.vue` (oculto en la ruta `login`), integrar el panel de cambio de responsable en `frontend/src/components/tickets/TicketWorkflowPanel.vue` solo si `canReassign || canEscalate`, y añadir la rama `assignee_change` en `frontend/src/components/tickets/TicketTimeline.vue` per FR-013/FR-018/FR-023 / plan: §3.1/§3.6/§3.7
- [X] T113 Actualizar `backend/scripts/seed_dev.py` con niveles de escalado, equipos y un escenario de creador técnico que permita validar candidatos, exclusiones y selección determinista per plan: seed / tasks: T023
- [X] T114 Implementar y probar el invariante de coherencia entre `tickets.assignee_id` y la última entrada `assignee_change` de la línea temporal, devolviendo `409` sin escrituras cuando difieran, en `backend/app/services/assignee_change.py` per FR-033 / plan: §5.3
- [X] T115 Añadir observabilidad estructurada a los comandos (INFO con `ticket_id`, `actor_id`, responsables, `change_kind`, niveles, `changed`, `request_id` y `duration_ms`; WARNING en rechazos; ERROR con `logger.exception`), sin registrar el motivo, en `backend/app/services/assignee_change.py` per plan: §5.4 / tasks: T078

## Phase 11: Convergence

- [X] T116 CRITICAL — Escribir las pruebas ejecutables de frontend de HU-06 antes de implementar la interfaz (panel y modos, selectores de compañero y nivel, formulario de motivo, campana y lista de notificaciones, `AppHeader`, rama `assignee_change` de la línea temporal y stores de ticket y notificaciones, incluida la accesibilidad con `axe-core`) en `frontend/tests/components/` y `frontend/tests/stores/` per Constitution IV / plan: estrategia de pruebas
- [X] T117 CRITICAL — Crear `frontend/src/types/assigneeChange.ts`, `frontend/src/types/notifications.ts`, `frontend/src/services/assigneeChange.ts`, `frontend/src/services/notifications.ts` y `frontend/src/stores/notifications.ts`, y extender `frontend/src/types/ticketWorkflow.ts` (`assignee_change`, `change_kind`, responsables y niveles; `can_reassign`/`can_escalate`) y `frontend/src/stores/ticketDetail.ts` (opciones, comandos, capacidades, `AbortController`, descarte de respuestas fuera de orden y refresco encadenado workflow → timeline → opciones) per HU06-RF-001/HU06-RF-006/HU06-RF-016/HU06-RF-018 / plan: §3.8
- [X] T118 CRITICAL — Crear `TicketAssigneeChangePanel.vue` (modos reasignar/escalar, carga de opciones, validación del motivo y del destino, `request_id` estable por firma, mapeo de errores `403`/`409`/`422` y avisos con `role="alert"`/`role="status"`), `AssigneeSelector.vue`, `EscalationLevelSelector.vue` y `AssigneeChangeReasonForm.vue` con `fieldset`/`legend`, `aria-required`, `aria-invalid`, `aria-describedby`, foco gestionado y etiquetas textuales, en `frontend/src/components/tickets/` per HU06-RF-001…HU06-RF-010 / plan: §3.2/§3.3/§3.4/§3.5/§3.9
- [X] T119 CRITICAL — Crear `frontend/src/components/layout/AppHeader.vue`, `NotificationBell.vue` y `NotificationList.vue`, montar la cabecera en `frontend/src/App.vue` fuera de `RouterView` y oculta en la ruta `login`, y activar el sondeo de `stores/notifications.ts` cada 15 s con `AbortController`, `focus`/`visibilitychange`, contador `unread_count` y parada ante `401`, en `frontend/src/components/layout/`, `frontend/src/components/notifications/` y `frontend/src/App.vue` per HU06-RF-016…HU06-RF-020 / plan: §3.1/§3.6
- [X] T120 HIGH — Añadir la rama `entry.type === 'assignee_change'` a `frontend/src/components/tickets/TicketTimeline.vue` con etiqueta «Cambio de responsable», subtipo reasignación/escalado, autor, responsables y niveles, motivo como texto plano y estilo público, conservando el renderizado de entradas antiguas per HU06-RF-011…HU06-RF-015 / plan: §3.7
- [X] T121 HIGH — Integrar `TicketAssigneeChangePanel` en `frontend/src/components/tickets/TicketWorkflowPanel.vue` solo si `canReassign || canEscalate`, recargar workflow, línea temporal y opciones tras `changed` y mostrar el aviso «Este ticket ya no está asignado a ti» con recarga del workflow ante `403 not_ticket_assignee` per HU06-RF-023 / US4/AC5 / plan: §3.1/§3.2
- [X] T122 HIGH — Ejecutar las pruebas de concurrencia real sobre PostgreSQL 16 con `TEST_DATABASE_URL` (`python -m pytest -m postgres` desde `backend/`) y verificar la migración con `alembic upgrade head`, `alembic downgrade -1` y `alembic upgrade head`, registrando la evidencia de la puerta de calidad y sin omitir `test_assignee_change_concurrency.py` per Constitution IV / plan: puertas de calidad
- [X] T123 MEDIUM — Actualizar `backend/scripts/seed_dev.py` para asignar `escalation_level` y equipos a los técnicos y añadir un escenario con creador técnico, de modo que candidatos, exclusiones y selección determinista del escalado sean demostrables per plan: seed / tasks: T023
- [X] T124 MEDIUM — Documentar el código de error `409 assignee_inconsistent` que devuelve el invariante de coherencia en `specs/006-reasignar-escalar-ticket/contracts/assignee-change.openapi.yaml` y en la tabla de errores de `plan.md` §2.9, alineando contrato y backend per HU06-RF-033 / plan: §2.9
- [X] T125 MEDIUM — Ejecutar de extremo a extremo los escenarios de `specs/006-reasignar-escalar-ticket/quickstart.md` (reasignación, escalado, colas, notificación, replay, conflicto, permisos, snapshot inmutable y coherencia responsable ↔ última entrada) y registrar el resultado per plan: quickstart / tasks: T085
