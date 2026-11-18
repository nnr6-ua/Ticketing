# Tasks: Responder a la petición de información del técnico (HU-03)

**Input**: Design documents from `/specs/003-responder-peticion-tecnico/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/ticket-information.openapi.yaml`, `contracts/frontend-components.md`, `quickstart.md`

**Tests**: El plan enumera pruebas de backend y frontend, y el principio IV de `.specify/memory/constitution.md` exige cubrir el flujo completo con pruebas verificables. Por ello se incluyen tareas de prueba y se escriben antes de la implementación.

**Organization**: Tareas agrupadas por historia de usuario para permitir implementación y validación independientes.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Puede ejecutarse en paralelo (ficheros distintos, sin dependencias de tareas incompletas)
- **[Story]**: Historia de usuario a la que pertenece la tarea (`US1`, `US2`, `US3`)
- Todas las tareas incluyen rutas de fichero exactas

## Path Conventions

- Aplicación web: `backend/`, `frontend/`
- Documentación de la feature: `specs/003-responder-peticion-tecnico/`
- Pruebas backend: `backend/tests/`
- Pruebas frontend: `frontend/tests/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Disponer de la base de `master` y de las herramientas existentes antes de tocar código.

- [X] T001 Verificar la integración de `master` ya realizada (fast-forward a `04e47e5`, HU-01, HU-02, HU-04 y HU-05), confirmar que existen `backend/app/`, `frontend/src/` y las migraciones hasta `backend/alembic/versions/0004_ticket_creation.py`, y ejecutar las suites base antes de modificar código.
- [X] T002 [P] Confirmar los comandos de validación existentes en `backend/` y `frontend/` (`python -m pytest`, `npm run test -- --run`) y que no se añaden dependencias nuevas.

**Checkpoint**: Rama sincronizada y línea base verde.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Modelo, migración, contratos y proyecciones compartidas por las tres historias.

**⚠️ CRITICAL**: Ninguna historia puede comenzar hasta completar esta fase.

- [X] T003 [P] Añadir los valores `information_request` y `user_response` al enum `TimelineEventType` en `backend/app/models/enums.py`, conservando `created`, `status_change`, `resolution` e `internal_comment`.
- [X] T004 [P] Añadir en `backend/app/models/timeline.py` la columna `reply_to_id: Uuid | None` (FK autorreferente a `ticket_timeline_entries.id`, `ondelete='SET NULL'`, índice `ix_timeline_reply_to`) y los dos `CHECK` nuevos con expresión literal: `(event_type <> 'information_request') OR (from_status IS NULL AND to_status IS NULL AND body IS NOT NULL AND is_internal = false AND reply_to_id IS NULL)` y `(event_type <> 'user_response') OR (from_status IS NULL AND to_status IS NULL AND body IS NOT NULL AND is_internal = false)`; `reply_to_id` en `user_response` puede ser `NULL` para tickets legados.
- [X] T005 Crear `backend/alembic/versions/0005_ticket_information.py` con `down_revision = '0004_ticket_creation'`; añadir los valores del enum dentro de `with op.get_context().autocommit_block():`, después la columna/FK/índice y los dos `CHECK`; en `downgrade`, eliminar índice, `CHECK` y columna, y conservar los valores del enum documentando la limitación.
- [X] T006 [P] Añadir `reply_to_id: UUID | None` a `TimelineEntry` en `backend/app/schemas/ticket_workflow.py`; las entradas nuevas son públicas y mantienen `is_internal = false`.
- [X] T007 [P] Añadir a `WorkflowResponse` en `backend/app/schemas/ticket_workflow.py` exactamente `can_request_information: bool`, `can_respond_to_information: bool`, `awaiting_user_response: bool`, `active_information_request: InformationRequestRef | None`, `reminder_active: bool` y `reminder_due_at: datetime | None`; crear `InformationRequestRef` (`id`, `body`, `requested_at`, `requested_by`), `InformationRequestRequest`/`InformationResponseRequest` (`body`, `expected_updated_at`, `request_id`) y las respuestas con `changed`, `message`, `ticket`, `timeline_entries` e `information_request`/`information_response`.
- [X] T008 [P] Añadir a `MyTicketSummary` en `backend/app/schemas/my_tickets.py` exactamente `awaiting_user_response: bool`, `response_requested_at: datetime | None`, `reminder_active: bool` y `reminder_due_at: datetime | None`; serializar las fechas nuevas como ISO 8601 UTC con el helper existente y no incluir el cuerpo de la petición en el resumen.
- [X] T009 [P] Extender `frontend/src/types/ticketWorkflow.ts` con los tipos `information_request`/`user_response`, `reply_to_id`, `InformationRequestRef`, los campos nuevos de `WorkflowResponse` y los DTOs de petición/respuesta; extender `frontend/src/types/myTickets.ts` con los cuatro campos nuevos de `MyTicketSummary`.
- [X] T010 [P] Añadir `requestInformation` y `respondToInformation` a `frontend/src/services/ticketWorkflow.ts`, usando `POST /api/v1/tickets/{ticket_id}/information-requests` y `POST /api/v1/tickets/{ticket_id}/information-responses`, sin calcular permisos ni recordatorios en cliente.
- [X] T011 Extender `backend/app/services/ticket_timeline.py`: incluir `reply_to_id` en `serialize_entry` y calcular `can_request_information`, `can_respond_to_information` y `awaiting_user_response` en `viewer_capabilities`; no exponer comentarios internos al creador.
- [X] T012 Extender `backend/app/services/ticket_timeline.py` con helpers de lectura: petición activa (ticket `pendiente_usuario`, `created_at` igual o posterior al último `status_change` con `to_status = pendiente_usuario` desempatando por `event_order`, y sin `user_response` con `reply_to_id` igual a su `id`), `pending_since`, `reminder_due_at = pending_since + 48 horas naturales`, `reminder_active = ticket.status == pendiente_usuario AND now >= reminder_due_at`, y una consulta agregada por lote para `GET /me/tickets` sin N+1; si no existe `status_change` a pendiente, `pending_since` y el recordatorio son `null`/`false`.
- [X] T013 Extender la proyección de `GET /api/v1/tickets/{id}/workflow` en `backend/app/services/ticket_workflow.py` para rellenar `can_request_information`, `can_respond_to_information`, `awaiting_user_response`, `active_information_request`, `reminder_active` y `reminder_due_at` con los helpers de `ticket_timeline.py`. En el mismo módulo, crear `_classify_information_replay` para comparar tipo de comando, actor, cuerpo normalizado y vínculo, consultando todas las entradas del ticket con el `request_id`; no reutilizar `_classify_transition_replay` para peticiones/respuestas.
- [X] T014 [P] Añadir fixtures en `backend/tests/conftest.py` para ticket `en_progreso` con técnico asignado, ticket `pendiente_usuario` con petición activa, ticket `pendiente_usuario` legado sin petición, creador, técnico asignado, técnico distinto y supervisor; incluir factorías de `information_request` y `user_response`.
- [X] T015 [P] Añadir factorías de prueba en `frontend/tests/fixtures/ticketWorkflow.ts` para workflow, entradas de línea temporal, petición activa y resumen de «Mis tickets», reutilizables por las pruebas de componentes, store y vista.
- [X] T016 [P] Extender el estado de `frontend/src/stores/ticketDetail.ts` con los campos nuevos de workflow y mapearlos en `loadWorkflow`/`loadTimeline`; no añadir `MyTicketSummary` al store (la lista vive en `MyTicketsPage.vue`); limpiar los textos, errores e identificadores de idempotencia al cambiar de ticket; no añadir todavía las acciones de petición/respuesta.

**Checkpoint**: Modelo, migración, contratos, proyecciones y fixtures listos; las historias pueden empezar.

---

## Phase 3: User Story 1 - Responder a la petición de información (Priority: P1) 🎯 MVP

**Goal**: El creador responde a la petición activa (o a un ticket pendiente legado), el ticket vuelve a «En progreso» y la respuesta queda registrada en la línea temporal.

**Independent Test**: Partiendo de un ticket `pendiente_usuario` con petición visible, el creador envía una respuesta válida y se comprueba que el ticket pasa a `en_progreso`, que la respuesta aparece en la línea temporal y que un reintento no duplica entradas.

### Tests for User Story 1

> **NOTE: Escribir estas pruebas primero y comprobar que fallan antes de implementar.**

- [X] T017 [P] [US1] Crear pruebas unitarias de respuesta en `backend/tests/unit/test_information_response_rules.py`: `body.strip()` no vacío, máximo 5.000 caracteres, normalización con `strip()`, clasificación de replay y `request_id_reused`, y `reply_to_id = NULL` permitido para ticket legado.
- [X] T018 [P] [US1] Crear pruebas de integración de respuesta en `backend/tests/integration/test_information_responses.py`: éxito del creador, `404 ticket_not_found` para ticket no legible, `403 forbidden` para supervisor u otro usuario legible, `409 invalid_transition` fuera de `pendiente_usuario`, `409 stale_ticket`, replay `200 changed=false`, `409 request_id_reused`, respuesta sin técnico asignado, atomicidad y `reply_to_id` apuntando a la petición activa o `NULL` en legado.
- [X] T019 [P] [US1] Crear pruebas de contrato de respuesta en `backend/tests/contract/test_information_response_contract.py`: `201` en creación, `200` en replay, campos de `InformationResponseResponse`, `TimelineEntry.reply_to_id`, `can_respond_to_information` y códigos de error documentados.
- [X] T020 [P] [US1] Crear pruebas de `InformationResponseForm.vue` en `frontend/tests/components/InformationResponseForm.spec.ts`: petición visible con autor/fecha, aviso genérico cuando `request = null`, límite 5.000, `submit` deshabilitado con texto vacío/espacios y accesibilidad (`label`, `aria-*`, `role="alert"`).
- [X] T021 [P] [US1] Crear pruebas de la acción de respuesta en `frontend/tests/stores/ticketDetail.response.spec.ts`: payload con `body`, `expected_updated_at` y `request_id`, actualización de ticket/línea temporal, replay sin duplicados, `stale_ticket`, `request_id_reused` y regeneración del identificador.
- [X] T022 [P] [US1] Crear pruebas de integración del panel de respuesta en `frontend/tests/components/TicketWorkflowPanel.information-response.spec.ts`: mostrar formulario solo con `can_respond_to_information`, enviar, limpiar y recargar, foco tras error y no mostrar la acción en `resuelto`/`cerrado`.

### Implementation for User Story 1

- [X] T023 [US1] Implementar `respond_to_information` en `backend/app/services/ticket_workflow.py` reutilizando `_locked_ticket`, `apply_user_response_transition` y el helper `_classify_information_replay` de T013: bloquear ticket; si no es legible devolver `404 ticket_not_found`; exigir creador o `403 forbidden`; normalizar `body.strip()` con 1–5.000 caracteres; comprobar idempotencia antes del estado consultando todas las entradas con ese `request_id`; exigir `pendiente_usuario`; validar `expected_updated_at`; localizar la petición activa del ciclo actual; delegar el `status_change` (`event_order=0`) en `apply_user_response_transition` e insertar solo `user_response` (`event_order=1`) con el mismo `created_at`, `reply_to_id` de la petición activa o `NULL` en legado, `is_internal=false`; confirmar en una única transacción y devolver el resultado existente con `changed=false` en replay.
- [X] T024 [US1] Añadir `POST /api/v1/tickets/{ticket_id}/information-responses` en `backend/app/api/v1/tickets.py`: `201` en creación, `200` en replay, sin lógica de idempotencia en el router y con el mapeo de errores de `data-model.md` §7.2.
- [X] T025 [P] [US1] Crear `frontend/src/components/tickets/InformationResponseForm.vue` con props `modelValue`, `request`, `disabled`, `error`, `maxLength = 5000`; eventos `update:modelValue` y `submit`; método `focus()`; bloque «El técnico necesita esta información» con autor/fecha `es-ES`, aviso genérico «Este ticket está pendiente de tu respuesta. Escribe la información que necesite el equipo técnico.» y contador basado en `modelValue.trim()`.
- [X] T026 [US1] Añadir la acción `respondToInformation` a `frontend/src/stores/ticketDetail.ts`: generar `request_id`, enviar `body`, `expected_updated_at` y `request_id`, actualizar ticket/línea temporal, conservar el `request_id` en replay y regenerarlo tras `stale_ticket` o `request_id_reused`.
- [X] T027 [US1] Integrar `InformationResponseForm` en `frontend/src/components/tickets/TicketWorkflowPanel.vue`: mostrarlo con `canRespondToInformation`, enviar mediante el store, mapear errores a mensaje/foco, limpiar texto/error y recargar workflow y primera página de la línea temporal tras éxito.
- [X] T028 [US1] Añadir en `frontend/src/components/tickets/TicketTimeline.vue` la rama `user_response` con etiqueta «Respuesta del usuario», autor y fecha en `es-ES`, texto con `whitespace-pre-wrap break-words`, sin agrupar ni citar entradas y manteniendo el orden del servidor.

**Checkpoint**: US1 funcional y validable de forma independiente; es el MVP.

---

## Phase 4: User Story 2 - Ver que el técnico necesita información (Priority: P1)

**Goal**: El técnico asignado solicita información desde el panel de estado, el ticket pasa a `pendiente_usuario`, el creador ve el aviso contextual y la petición, y a las 48 h aparece un único recordatorio.

**Independent Test**: Partiendo de un ticket `en_progreso` asignado, el técnico envía una petición con mensaje; se comprueba que el ticket pasa a `pendiente_usuario`, que la petición es visible, que «Mis tickets» muestra el aviso y que a las 48 h `reminder_active` es `true` sin cambiar el estado.

### Tests for User Story 2

> **NOTE: Escribir estas pruebas primero y comprobar que fallan antes de implementar.**

- [X] T029 [P] [US2] Crear pruebas unitarias de solicitud en `backend/tests/unit/test_information_request_rules.py`: `body.strip()` no vacío, máximo 5.000, normalización, estado `en_progreso`, una única petición activa y clasificación de replay/reutilización.
- [X] T030 [P] [US2] Crear pruebas de integración de solicitud en `backend/tests/integration/test_information_requests.py`: éxito del técnico asignado, `403 not_ticket_assignee` para técnico distinto, `403 forbidden` para usuario no técnico, `404 ticket_not_found` para ticket no legible, `409 information_request_already_open` con precedencia sobre `invalid_transition`, `409 invalid_transition`, `409 stale_ticket`, replay `200 changed=false`, `409 request_id_reused`, atomicidad y orden `status_change`/`information_request`.
- [X] T031 [P] [US2] Crear pruebas de integración de aviso y recordatorio en `backend/tests/integration/test_information_reminder.py`: `GET /me/tickets` con `awaiting_user_response`, `response_requested_at` y `reminder_*`; recordatorio inactivo antes de 48 h, activo a las 48 h, inactivo al responder o salir de pendiente, sin `status_change` ⇒ inactivo, sin N+1; y comprobar que consultar varias veces no crea entradas, no cambia el estado ni genera recordatorios adicionales.
- [X] T032 [P] [US2] Crear pruebas de contrato de solicitud en `backend/tests/contract/test_information_request_contract.py`: `201`/`200`, `InformationRequestResponse`, `InformationRequestRef`, `WorkflowResponse` ampliado y `MyTicketSummary` ampliado con los códigos de error de `data-model.md` §7.1.
- [X] T033 [P] [US2] Crear pruebas de `InformationRequestForm.vue` en `frontend/tests/components/InformationRequestForm.spec.ts`: etiqueta «Información que necesitas», ayuda, contador `n / 5000`, `submit` deshabilitado con texto vacío/espacios o más de 5.000, `focus()` y accesibilidad.
- [X] T034 [P] [US2] Crear pruebas de la acción de solicitud en `frontend/tests/stores/ticketDetail.request.spec.ts`: payload, actualización de ticket/línea temporal, replay, `information_request_already_open`, `invalid_transition`, `stale_ticket` y regeneración de `request_id`.
- [X] T035 [P] [US2] Crear pruebas de integración del panel de solicitud en `frontend/tests/components/TicketWorkflowPanel.information-request.spec.ts`: al seleccionar `pendiente_usuario` se muestra `InformationRequestForm` en lugar de `ResolutionForm`, no se llama al endpoint genérico, se muestra petición activa/aviso genérico y recordatorio, y se mapean errores.
- [X] T036 [P] [US2] Crear pruebas de «Mis tickets» en `frontend/tests/views/MyTicketsPage.spec.ts`: badge `pendiente_usuario`, aviso de respuesta requerida, recordatorio a las 48 h y ausencia de campana o centro de notificaciones.

### Implementation for User Story 2

- [X] T037 [US2] Implementar `request_information` en `backend/app/services/ticket_workflow.py` reutilizando `_locked_ticket`, `_apply_ticket_effects`, `_insert_status_change` y el helper `_classify_information_replay` de T013: bloquear ticket; `404 ticket_not_found` si no es legible; `403 forbidden` si el actor no es técnico; `403 not_ticket_assignee` si no es el asignado; normalizar `body.strip()` con 1–5.000 caracteres; comprobar idempotencia antes del estado; rechazar petición activa con `409 information_request_already_open`; exigir `en_progreso`; validar `expected_updated_at`; insertar `status_change` (`event_order=0`) e `information_request` (`event_order=1`) con el mismo `created_at`, `reply_to_id=NULL`, `is_internal=false`; confirmar en una única transacción y devolver el resultado existente con `changed=false` en replay.
- [X] T038 [US2] Añadir `POST /api/v1/tickets/{ticket_id}/information-requests` en `backend/app/api/v1/tickets.py`: `201` en creación, `200` en replay y mapeo de errores de `data-model.md` §7.1.
- [X] T039 [US2] Extender `GET /api/v1/me/tickets` en `backend/app/api/v1/my_tickets.py` para rellenar `awaiting_user_response`, `response_requested_at`, `reminder_active` y `reminder_due_at` usando la consulta agregada de `ticket_timeline.py`, sin N+1 y sin incluir el cuerpo de la petición.
- [X] T040 [P] [US2] Crear `frontend/src/components/tickets/InformationRequestForm.vue` con props `modelValue`, `disabled`, `error`, `maxLength = 5000`; eventos `update:modelValue` y `submit`; método `focus()`; etiqueta «Información que necesitas», ayuda «Explica al usuario qué dato concreto necesitas para continuar.» y contador basado en `modelValue.trim()`.
- [X] T041 [US2] Añadir la acción `requestInformation` a `frontend/src/stores/ticketDetail.ts`: generar `request_id`, enviar `body`, `expected_updated_at` y `request_id`, actualizar ticket/línea temporal, conservar el `request_id` en replay y regenerarlo tras `stale_ticket`, `request_id_reused` o `information_request_already_open`.
- [X] T042 [US2] Integrar la solicitud en `frontend/src/components/tickets/TicketWorkflowPanel.vue`: al seleccionar `pendiente_usuario`, mostrar `InformationRequestForm` y no usar el endpoint genérico; exigir texto válido; mostrar `active_information_request` o aviso genérico y, si `reminderActive`, el aviso «Han pasado más de 48 horas desde la petición. El equipo técnico sigue esperando tu respuesta.» con `role="status"` y `aria-live="polite"`.
- [X] T043 [US2] Añadir en `frontend/src/components/tickets/TicketTimeline.vue` la rama `information_request` con etiqueta «Petición de información», autor y fecha en `es-ES`, texto con `whitespace-pre-wrap break-words`, sin agrupar ni citar entradas.
- [X] T044 [US2] Añadir a `frontend/src/views/MyTicketsPage.vue` el badge de `pendiente_usuario`, el aviso de respuesta requerida y el recordatorio de 48 h usando los campos del resumen; sin campana, centro de notificaciones ni nuevos canales.

**Checkpoint**: US1 y US2 funcionan y se validan de forma independiente.

---

## Phase 5: User Story 3 - Devolver el ticket al equipo técnico y dejar constancia (Priority: P2)

**Goal**: Tras la respuesta, el ticket reaparece en la cola del técnico y la petición, la respuesta y el cambio de estado quedan trazados de forma independiente, pública e inmutable.

**Independent Test**: Tras responder, se comprueba que el ticket figura `en_progreso`, que aparece en la cola de trabajo y que la línea temporal contiene petición, respuesta y cambio de estado con autores y fechas, sin agrupar ni permitir edición/borrado.

### Tests for User Story 3

> **NOTE: Escribir estas pruebas primero y comprobar que fallan antes de implementar los ajustes necesarios.**

- [X] T045 [P] [US3] Crear pruebas de integración del ciclo completo y de visibilidad en `backend/tests/integration/test_information_cycle.py` y `backend/tests/integration/test_information_visibility.py`: petición → respuesta → `en_progreso`, reaparición en cola del técnico o cola colectiva sin asignado, orden `created_at ASC, event_order ASC, id ASC`, autores correctos, `reply_to_id` de la respuesta, visibilidad pública para creador y técnico y ausencia de comentarios internos para el creador.
- [X] T046 [P] [US3] Crear pruebas de contrato de trazabilidad en `backend/tests/contract/test_information_traceability_contract.py`: `reply_to_id` en la línea temporal, entradas independientes, inmutabilidad (sin `PATCH`/`PUT`/`DELETE`; `404`/`405` donde corresponda) y rechazo de respuesta en `resuelto`/`cerrado`.
- [X] T047 [P] [US3] Crear pruebas de línea temporal en `frontend/tests/components/TicketTimeline.information.spec.ts`: mostrar petición y respuesta como entradas independientes con autor/fecha, no agrupar ni citar, no renderizar comentarios internos al creador y mantener `white-space: pre-wrap`.
- [X] T048 [US3] Verificar y, solo si es necesario, ajustar la cola de trabajo en `backend/app/services/work_queue.py` y `backend/app/api/v1/work_queue.py` para que un ticket respondido (`en_progreso`) vuelva a aparecer para el técnico asignado o en la cola colectiva si no hay asignado; añadir la aserción correspondiente a T045.
- [X] T049 [US3] Auditar y, solo si es necesario, ajustar en `backend/app/services/ticket_timeline.py` y `frontend/src/components/tickets/TicketTimeline.vue` el orden, la visibilidad pública y la no agrupación de `information_request`/`user_response`, sin crear hilos ni citas.
- [X] T050 [US3] Auditar la inmutabilidad en `backend/app/api/v1/tickets.py` y `backend/app/services/ticket_timeline.py`: no debe existir endpoint ni servicio para editar o borrar entradas de petición/respuesta; documentar en T046 el comportamiento `404`/`405`.

**Checkpoint**: Las tres historias son funcionales e independientes; el ciclo completo queda trazado.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Verificación final, rendimiento, seguridad y no regresión.

- [X] T051 [P] Revisar el logging de `backend/app/services/ticket_workflow.py`: registrar ticket, actor, comando, `request_id` y resultado, sin cuerpos ni datos sensibles.
- [X] T052 [P] Revisar accesibilidad y responsive en `frontend/src/components/tickets/InformationRequestForm.vue`, `InformationResponseForm.vue`, `TicketWorkflowPanel.vue`, `TicketTimeline.vue` y `frontend/src/views/MyTicketsPage.vue`: foco, `aria-*`, contraste, teclado, `prefers-reduced-motion` y textos en español de España.
- [ ] T053 [P] Probar `alembic upgrade head` y `alembic downgrade 0004_ticket_creation` sobre PostgreSQL, verificando el bloque `autocommit_block` y que el `downgrade` conserva los valores del enum.
- [X] T054 [P] Ejecutar la suite completa de backend (`python -m pytest`) y corregir cualquier fallo de HU-03 o regresión.
- [X] T055 [P] Ejecutar la suite completa de frontend (`npm run test -- --run`) y corregir cualquier fallo de HU-03 o regresión.
- [ ] T056 Ejecutar las secciones 5–8 de `specs/003-responder-peticion-tecnico/quickstart.md` con dos usuarios y un ticket, incluida la simulación del recordatorio de 48 h, y registrar el resultado.
- [X] T057 [P] Auditar las guardas de arquitectura: sin tabla nueva, sin columnas nuevas en `tickets`, sin `PATCH`/`PUT`/`DELETE`, sin `v-html`, sin nuevas dependencias, sin adjuntos, sin correo, sin campana/centro de notificaciones y sin recordatorios periódicos.
- [ ] T058 [P] Crear y ejecutar las pruebas de concurrencia en PostgreSQL en `backend/tests/integration/test_information_concurrency.py`: dos respuestas simultáneas, dos peticiones simultáneas y doble envío, comprobando que solo una se aplica, la otra recibe `stale_ticket` y no quedan cambios parciales.
- [X] T059 [P] Auditar seguridad y visibilidad: identidad solo desde JWT, ticket no legible `404`, supervisor no responde, comentarios internos ocultos al creador y cuerpos sin HTML enriquecido.
- [X] T060 [P] Ejecutar las pruebas de regresión de HU-01, HU-02, HU-04 y HU-05 en `backend/tests/` y `frontend/tests/`, incluidos `frontend/tests/components/TicketWorkflowPanel.spec.ts`, `frontend/tests/components/TicketTimeline.spec.ts` y `frontend/tests/stores/ticketDetail.spec.ts`, y confirmar que la transición genérica de `pendiente_usuario` a `en_progreso` sigue funcionando.
- [X] T061 [P] Extender `backend/tests/integration/test_ticket_workflow_performance.py` con la medición p95 de solicitud, respuesta y proyecciones de `workflow`/«Mis tickets»; verificar <300 ms de servidor y <2 s percibidos, y corregir cualquier N+1 detectado.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Sin dependencias; requiere integrar `master` antes de tocar código.
- **Foundational (Phase 2)**: Depende de Setup y bloquea las tres historias.
- **User Stories (Phase 3–5)**: Dependen de Foundational.
- **Polish (Phase 6)**: Depende de las historias que se quieran entregar.

### User Story Dependencies

- **US1 (P1)**: Puede empezar tras Foundational; no depende de US2/US3. Es el MVP.
- **US2 (P1)**: Puede empezar tras Foundational; es independiente a nivel de contrato, pero comparte `ticket_workflow.py`, `tickets.py`, `ticketDetail.ts`, `TicketWorkflowPanel.vue` y `TicketTimeline.vue` con US1. Recomendación: ejecutar US1 y US2 secuencialmente o asignar la propiedad de esos ficheros para evitar conflictos.
- **US3 (P2)**: Depende de US1 y US2 para validar el ciclo completo y la cola; no introduce una tabla ni un flujo paralelo.

### Within Each User Story

- Las pruebas se escriben y fallan antes de la implementación.
- Servicio antes de endpoint.
- Endpoint antes de la integración de UI que consume el resultado real.
- Componente antes de la integración en el panel.
- Store antes de la integración de la acción en el panel.
- Validar el checkpoint antes de pasar a la siguiente prioridad.

### Parallel Opportunities

- T002 puede ejecutarse en paralelo con T001 una vez sincronizada la rama.
- T003, T004, T006, T007, T008, T009, T010, T014, T015 y T016 son paralelizables entre sí cuando sus dependencias estén completas.
- T005 depende de T003/T004; T011–T013 comparten `ticket_timeline.py`/`ticket_workflow.py` y deben ser secuenciales.
- En US1, T017–T022 son paralelizables; T023–T024 son secuenciales; T025 puede ir en paralelo con T023/T024; T026–T027 son secuenciales; T028 comparte `TicketTimeline.vue` con T043 y debe coordinarse.
- En US2, T029–T036 son paralelizables; T037–T039 son secuenciales; T040 puede ir en paralelo; T041–T042 son secuenciales; T043 comparte `TicketTimeline.vue` con T028; T044 depende de T039.
- En US3, T045–T047 son paralelizables; T048–T050 dependen de las historias previas.
- En Polish, T051–T055 y T057–T061 pueden ejecutarse en paralelo; T056 depende de todo.

---

## Parallel Example: User Story 1

```bash
# Pruebas de US1 en paralelo:
Task: "Unit response rules en backend/tests/unit/test_information_response_rules.py"
Task: "Integration responses en backend/tests/integration/test_information_responses.py"
Task: "Contract response en backend/tests/contract/test_information_response_contract.py"
Task: "Component InformationResponseForm en frontend/tests/components/InformationResponseForm.spec.ts"
Task: "Store response en frontend/tests/stores/ticketDetail.response.spec.ts"
Task: "Panel response en frontend/tests/components/TicketWorkflowPanel.information-response.spec.ts"
```

## Parallel Example: User Story 2

```bash
# Pruebas de US2 en paralelo:
Task: "Unit request rules en backend/tests/unit/test_information_request_rules.py"
Task: "Integration requests en backend/tests/integration/test_information_requests.py"
Task: "Integration reminder en backend/tests/integration/test_information_reminder.py"
Task: "Contract request en backend/tests/contract/test_information_request_contract.py"
Task: "Component InformationRequestForm en frontend/tests/components/InformationRequestForm.spec.ts"
Task: "Store request en frontend/tests/stores/ticketDetail.request.spec.ts"
Task: "Panel request en frontend/tests/components/TicketWorkflowPanel.information-request.spec.ts"
Task: "MyTicketsPage en frontend/tests/views/MyTicketsPage.spec.ts"
```

## Parallel Example: User Story 3

```bash
# Pruebas de US3 en paralelo:
Task: "Ciclo completo en backend/tests/integration/test_information_cycle.py"
Task: "Visibilidad en backend/tests/integration/test_information_visibility.py"
Task: "Contrato de trazabilidad en backend/tests/contract/test_information_traceability_contract.py"
Task: "Línea temporal en frontend/tests/components/TicketTimeline.information.spec.ts"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Completar Phase 1: Setup y sincronizar `master`.
2. Completar Phase 2: Foundational (modelo, migración, contratos, helpers y fixtures).
3. Completar Phase 3: US1 (respuesta del creador).
4. **STOP and VALIDATE**: responder a una petición existente, comprobar `en_progreso`, línea temporal y replay sin duplicados.
5. Demostrar si está listo.

### Incremental Delivery

1. Setup + Foundational → base lista.
2. US1 → validar respuesta y MVP.
3. US2 → validar solicitud, aviso, lista y recordatorio.
4. US3 → validar cola, trazabilidad e inmutabilidad.
5. Polish → PostgreSQL, accesibilidad, seguridad y no regresión.

### Parallel Team Strategy

1. El equipo completa Setup + Foundational.
2. Después:
   - Developer A: US1.
   - Developer B: US2, coordinando los ficheros compartidos con A.
   - Developer C: US3 cuando US1/US2 estén integradas.
3. Cada historia se valida de forma independiente antes de integrar la siguiente.

---

## Notes

- `[P]` indica ficheros distintos y sin dependencias de tareas incompletas.
- Las tareas que comparten `ticket_workflow.py`, `tickets.py`, `ticketDetail.ts`, `TicketWorkflowPanel.vue` o `TicketTimeline.vue` no deben ejecutarse en paralelo.
- Cada historia es independientemente completable y testeable; US1 es el MVP.
- Verificar que las pruebas fallan antes de implementar.
- No añadir tablas, columnas en `tickets`, endpoints de edición/borrado, dependencias nuevas, adjuntos, correo, campana ni recordatorios periódicos.
- Mantener textos, fechas y mensajes en español de España y la estética de HU-05.
