# Tasks: Seguimiento de la evolución del ticket (estado y línea temporal)

**Input**: Design documents from `/specs/002-ticket-timeline-history/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/
**Tests**: Not explicitly requested in the feature specification; implementation tasks only.
**Organization**: Tasks grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Maps task to user story (US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Web application**: `backend/src/` → `backend/app/`, `frontend/src/` (as per plan.md structure)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [x] T001 Confirm project structure per implementation plan (backend/ and frontend/ already present)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T002 [P] Align contract path in `contracts/ticket-timeline.query.openapi.yaml`: change `GET /tickets/{ticket_id}` to `GET /tickets/{ticket_id}/workflow` to match the existing backend router (`backend/app/api/v1/tickets.py`) and frontend service (`frontend/src/services/ticketWorkflow.ts`)

**Checkpoint**: Foundation ready — contract aligned with existing implementation; user story work can now begin.

---

## Phase 3: User Story 1 — Consultar el estado actual del ticket (Prioridad: P1) [US1]

**Goal**: El usuario creador ve el estado actual de su ticket sin tener que preguntar al técnico.

**Independent Test**: Abrir el detalle de un ticket propio y confirmar que se muestra el número, título y etiqueta de estado actual (ej. «En progreso») obtenida del backend.

### Implementation for User Story 1

- [x] T003 [P] [US1] Verify `GET /tickets/{ticket_id}/workflow` returns `WorkflowResponse` with `ticket.status`, `ticket.status_label`, `ticket.allowed_transitions` in `backend/app/api/v1/tickets.py`
- [x] T004 [P] [US1] Verify `TicketDetailPage.vue` mounts `TicketWorkflowPanel` and renders ticket number, title, and status label in `frontend/src/views/TicketDetailPage.vue`
- [x] T005 [P] [US1] Verify frontend service `getWorkflow` calls `/tickets/{id}/workflow` and maps to `WorkflowResponse` in `frontend/src/services/ticketWorkflow.ts`

**Checkpoint**: User Story 1 fully functional and testable independently — ticket creator sees current status.

---

## Phase 4: User Story 2 — Revisar la línea temporal completa del ticket (Prioridad: P1) [US2]

**Goal**: El usuario creador revisa el historial cronológico con cambios de estado, resoluciones y comentarios públicos del técnico.

**Independent Test**: Abrir el detalle de un ticket con varias entradas y confirmar que la línea temporal muestra cada evento en orden cronológico con autor, fecha y hora, y que los comentarios internos no aparecen para el creador.

### Implementation for User Story 2

- [x] T006 [P] [US2] Verify `GET /tickets/{ticket_id}/timeline` accepts `page`/`page_size` query params and returns paginated `TimelineResponse` in `backend/app/api/v1/tickets.py`
- [x] T007 [P] [US2] Verify `TicketTimeline` renders entries chronologically (status_change, resolution, internal_comment) with author and date in `frontend/src/components/tickets/TicketTimeline.vue`
- [x] T008 [P] [US2] Add pagination controls (page, page_size, has_next/has_previous) to `TicketTimeline`, wired to `ticketDetail.store` `pagination` ref, in `frontend/src/components/tickets/TicketTimeline.vue`
- [x] T009 [P] [US2] Verify `get_timeline` filters `is_internal = false` for users who cannot view internal comments (ticket creator) in `backend/app/services/ticket_timeline.py`

**Checkpoint**: User Stories 1 AND 2 both functional independently — timeline paginated, internal comments hidden from creator.

---

## Phase 5: User Story 3 — Identificar autor y fecha de cada entrada (Prioridad: P2) [US3]

**Goal**: El usuario creador sabe quién realizó cada cambio/comentario y cuándo.

**Independent Test**: Consultar la línea temporal y confirmar que cada entrada muestra el nombre del autor y la fecha/hora en zona horaria de España.

### Implementation for User Story 3

- [x] T010 [P] [US3] Verify each timeline entry renders `entry.author.name` and formatted `entry.created_at` in `frontend/src/components/tickets/TicketTimeline.vue`
- [x] T011 [P] [US3] Verify dates stored in UTC and displayed in `Europe/Madrid` via `Intl.DateTimeFormat` in `frontend/src/components/tickets/TicketTimeline.vue`

**Checkpoint**: All user stories independently functional — author and date visible per timeline entry.

---

## Phase 6: Polish & Cross-Cutting Concerns (Calidad profesional 2026)

**Purpose**: Mejoras que afectan a varias historias de usuario (frontend actual a interfaces de 2026, calidad profesional)

- [x] T012 [P] Revisión WCAG 2.1 AA: anillos de foco visible (`focus-visible:ring-2`), `aria-live` para mensajes dinámicos, navegación por teclado en panel de estado y línea temporal
- [x] T013 [P] Revisión responsive: línea temporal legible en móvil (grid apilado, objetivos táctiles adecuados) en `frontend/src/components/tickets/TicketTimeline.vue` y `frontend/src/views/TicketDetailPage.vue`
- [x] T014 [P] Localización es-ES: todos los mensajes de usuario en español de España y fechas mostradas en `Europe/Madrid`, almacenadas en UTC
- [x] T015 Ejecutar escenarios de validación de `quickstart.md` de extremo a extremo (estado, timeline, comentarios internos ocultos, acceso denegado a ticket ajeno)
- [x] T016 [P] Lint y typecheck: backend (`ruff`/`mypy` según configuración del proyecto) y frontend (`vue-tsc`, ESLint)
- [x] T017 [US1] Verificar que `TicketDetailPage.vue` y `TicketWorkflowPanel.vue` ocultan los controles de escritura (cambio de estado, resolución, comentario interno) cuando el usuario es creador pero no técnico asignado, cumpliendo HU02-RF-008 en `frontend/src/views/TicketDetailPage.vue` y `frontend/src/components/tickets/TicketWorkflowPanel.vue`
- [x] T018 [P] Medir p95 < 2 segundos de `GET /tickets/{ticket_id}/workflow` y `GET /tickets/{ticket_id}/timeline` (HU02-SC-003) en `backend/app/api/v1/tickets.py` y `backend/app/services/ticket_timeline.py`

---

## Dependencies & Execution Order

### Phase dependencies

- **Setup (Phase 1)**: No dependencies — puede iniciarse inmediatamente.
- **Foundational (Phase 2)**: Depende de Setup. Alinea el contrato con la implementación existente. Bloquea todas las historias de usuario.
- **User Stories (Phase 3-5)**: Dependen de Foundational. US1, US2 y US3 pueden ejecutarse en paralelo si hay capacidad del equipo (reusan infraestructura existente de HU-05).
- **Polish (Phase 6)**: Depende de las historias de usuario deseadas completadas.

### User story dependencies

- **US1 (P1)**: Tras Foundational. Sin dependencias de otras historias.
- **US2 (P1)**: Tras Foundational. Independiente; puede ejecutarse en paralelo con US1.
- **US3 (P2)**: Tras Foundational. Independiente; puede ejecutarse en paralelo con US1/US2.

### Within each user story

- Verificación de backend y frontend pueden hacerse en paralelo (archivos distintos).
- Tareas [P] de una misma historia pueden ejecutarse en paralelo.

### Parallel opportunities

- T003, T004, T005 (US1): verificaciones independientes en archivos distintos → ejecutar en paralelo.
- T006, T007, T008, T009 (US2): independientes en archivos distintos → ejecutar en paralelo.
- T010, T011 (US3): independientes → ejecutar en paralelo.
- T012, T013, T014, T016, T018 (Polish/performance): independientes en archivos distintos → ejecutar en paralelo.
- T017 (US1): depende de que T004 y T005 estén verificados; se ejecuta tras US1.

### Parallel example: User Story 2

```bash
# Verificaciones de US2 en paralelo (archivos distintos):
Task: "Verify GET /tickets/{ticket_id}/timeline ... backend/app/api/v1/tickets.py"
Task: "Verify TicketTimeline renders entries ... frontend/src/components/tickets/TicketTimeline.vue"
Task: "Add pagination controls to TicketTimeline ... frontend/src/components/tickets/TicketTimeline.vue"
Task: "Verify get_timeline filters is_internal=false ... backend/app/services/ticket_timeline.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL — contract alignment blocks all stories)
3. Complete Phase 3: User Story 1 (estado actual)
4. **STOP and VALIDATE**: Test User Story 1 independently
5. Deploy/demo if ready

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. Add User Story 1 → Test independently → Deploy/Demo (MVP!)
3. Add User Story 2 → Test independently → Deploy/Demo
4. Add User Story 3 → Test independently → Deploy/Demo
5. Cada historia añade valor sin romper las anteriores

### Parallel Team Strategy

Con múltiples desarrolladores:

1. Equipo completa Setup + Foundational juntos
2. Tras Foundational:
   - Desarrollador A: US1 (estado actual)
   - Desarrollador B: US2 (línea temporal + paginación)
   - Desarrollador C: US3 (autor y fecha) + Polish
3. Las historias se completan e integran de forma independiente

---

## Notes

- [P] tasks = archivos diferentes, sin dependencias de tareas incompletas
- [Story] label mapea la tarea a la historia de usuario para trazabilidad
- Cada historia de usuario debe ser completable y comprobable de forma independiente
- Esta historia reusa fuertemente la infraestructura de HU-05 (`TicketWorkflowPanel`, `TicketTimeline`, store `ticketDetail`, servicio `ticketWorkflow`, endpoints `/workflow` y `/timeline`); las tareas se centran en verificar, alinear el contrato y añadir paginación UI + pulido de calidad profesional 2026
- Frontend: Vue 3 Composition API `<script setup>`, TypeScript estricto, Tailwind CSS, Pinia, reutilizando componentes visuales existentes (opción A elegida: sin nueva librería de componentes, acorde a la constitución)
- Tests no incluidos: la especificación no solicita tests y el usuario no pidió enfoque TDD.
- T002: verificar que el contrato `contracts/ticket-timeline.query.openapi.yaml` apunta a `GET /tickets/{ticket_id}/workflow` (no a `/tickets/{ticket_id}`) antes de empezar la implementación.
- Duplicados D1-D3 y redacción de "historial completo" (A1): pendientes en `spec.md` (no son tareas de implementación, se resuelven al refinar la especificación).

---

## Phase 7: Convergence

- [X] T019 CRITICAL — Añadir pruebas ejecutables de US2 para comentarios públicos del técnico: el creador ve `autor`, texto y fecha, los internos siguen ocultos, y la UI los identifica como «Comentario» (Constitution IV, US2/AC3, RF-006; missing)
- [X] T020 CRITICAL — Añadir pruebas de componente en `frontend/tests/components/TicketTimeline.spec.ts` para los controles de paginación de T008: emisión de `page-change`, estados `has_next`/`has_previous` y navegación sin recarga (Constitution IV, T008, US2/AC1; missing)
- [X] T021 CRITICAL — Añadir pruebas de contrato de `GET /tickets/{ticket_id}/timeline` para 401, 404 `ticket_not_found` y 422 con parámetros `page`/`page_size` inválidos, verificando el formato `{"detail": {"code", "message"}}` (Constitution IV, US2/AC5; missing)
- [X] T022 [US2] Habilitar entradas de comentario público del técnico (`is_internal=false`) y corregir `frontend/src/components/tickets/TicketTimeline.vue` para etiquetarlas como «Comentario» en lugar de «Interno», manteniendo ocultos los comentarios internos para el creador (US2/AC3, RF-006, RN-03; missing)
- [X] T023 [US2] Alinear `contracts/ticket-timeline.query.openapi.yaml` con la implementación: documentar 404 en lugar de 403 para ticket ajeno, añadir 422, incluir `created` en el enum de `TimelineEntry` y reflejar `is_internal=false` para comentarios públicos (plan: contracts decision, US2/AC5, Constitution IV; contradicts)
- [X] T024 [US2] Revisar y justificar o retirar la insignia «Histórica» y su lógica `historicalResolutionIds` en `frontend/src/components/tickets/TicketTimeline.vue`, por no estar solicitada en la spec, el plan ni las tareas de US2 (spec US2/RN-02, Constitution V; unrequested)

---

## Phase 8: Convergence

- [X] T025 [US2] Habilitar la creación de comentarios públicos del técnico (`is_internal=false`) en la vía de escritura existente de `backend/app/services/ticket_workflow.py` y `backend/app/api/v1/tickets.py`, reutilizando la migración `backend/alembic/versions/0005_public_timeline_comments.py`, y añadir una prueba extremo a extremo en `backend/tests/integration/test_timeline_visibility.py` donde el creador ve el comentario con autor, texto y fecha, el interno sigue oculto y la UI lo etiqueta como «Comentario» en `frontend/src/components/tickets/TicketTimeline.vue` (US2/AC3, RF-006, RN-03, T022; partial)
- [X] T026 [US2] Añadir una prueba backend en `backend/tests/integration/test_timeline_visibility.py` para un ticket sin entradas visibles: `GET /tickets/{ticket_id}/timeline` devuelve 200 con `items=[]`, `total_items=0`, `total_pages=0`, `has_next=false` y `has_previous=false`, y el frontend muestra el mensaje de estado vacío de `frontend/src/components/tickets/TicketTimeline.vue` (US2/AC4, RF-010, caso límite “ticket sin cambios de estado ni comentarios”; missing)
- [X] T027 [US2] Añadir una prueba ejecutable de la migración `backend/alembic/versions/0005_public_timeline_comments.py` que verifique `upgrade()` y `downgrade()`: la restricción `ck_timeline_internal_comment` admite `is_internal=false` tras `upgrade()` y vuelve a excluirlo tras `downgrade()`, sin perder filas válidas (plan: decisión de modelo de datos, `specs/002-ticket-timeline-history/data-model.md:98`; missing)

---

## Phase 9: Convergence

- [X] T028 CRITICAL — Sustituir la prueba simulada de `backend/tests/integration/test_timeline_visibility.py` (`FakeOp`) por una prueba ejecutable de `upgrade()`/`downgrade()` de `backend/alembic/versions/0005_public_timeline_comments.py` sobre PostgreSQL: insertar fila con `is_internal=false` tras `upgrade()`, verificar que `downgrade()` la rechaza y que no se pierden filas válidas (per T027, Constitution II, Constitution IV, `specs/002-ticket-timeline-history/data-model.md:98`; partial)
- [X] T029 [US2] Garantizar que el usuario creador nunca reciba comentarios internos en `GET /tickets/{ticket_id}/timeline` aunque tenga rol `tecnico`/`supervisor`/`admin` o sea el asignado, reforzando el filtro en `backend/app/services/ticket_timeline.py` y añadiendo una prueba en `backend/tests/integration/test_timeline_visibility.py` con creador operativo (per US2/AC3, RN-03, SC-006, plan: Constitution III; contradicts)
- [X] T030 [US2] Exponer un control de `page_size` (1-200) en `frontend/src/components/tickets/TicketTimeline.vue`, emitir el cambio hacia `frontend/src/components/tickets/TicketWorkflowPanel.vue` y usar el valor en `store.loadTimeline` en lugar del `50` fijo, con su prueba de componente (per T008, plan: decisión de paginación; partial)
- [X] T031 [US2] Añadir una prueba de integración en `frontend/tests/components/TicketWorkflowPanel.spec.ts` que verifique que `page-change` de `TicketTimeline` actualiza `pagination`, vuelve a llamar a `getTimeline` con la página solicitada y no recarga la página (per T020, Constitution IV; partial)
- [X] T032 [US2] Habilitar la selección de visibilidad pública en el formulario de comentario del técnico (`frontend/src/components/tickets/InternalCommentForm.vue`, `frontend/src/stores/ticketDetail.ts`, `frontend/src/types/ticketWorkflow.ts`), enviando `is_internal=false` a la vía de escritura existente, para que el creador vea el comentario etiquetado como «Comentario» con autor, texto y fecha; añadir prueba de componente (per US2/AC3, RF-006, T022, T025; partial)
- [X] T033 [US2] Implementar y probar el indicador «sistema» para entradas sin autor registrado en `serialize_entry` de `backend/app/services/ticket_timeline.py` y en `frontend/src/components/tickets/TicketTimeline.vue`, sin exponer datos internos (per caso límite «Entrada de línea temporal sin autor registrado», RF-009; missing)
