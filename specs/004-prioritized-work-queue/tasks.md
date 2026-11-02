---
description: "Desglose de tareas para la HU-04: Cola de Trabajo Priorizada"
---

# Tareas: Cola de Trabajo Priorizada (HU-04)

**Entrada**: Documentos de diseño en `specs/004-prioritized-work-queue/`

**Prerrequisitos**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/work-queue.openapi.yaml](./contracts/work-queue.openapi.yaml), [quickstart.md](./quickstart.md)

**Pruebas**: incluidas en la fase de Verificación (T074–T090). No se adopta TDD: las pruebas se ejecutan después de implementar cada capa y antes de cerrar la funcionalidad.

**Organización**: las fases siguen la estructura solicitada (infraestructura, backend, frontend, lógica visual, filtros y verificación). Cada tarea de implementación lleva la etiqueta de la historia de usuario a la que sirve y referencia los requisitos funcionales (FR) y criterios de éxito (SC) que cubre.

## Formato: `[ID] [P?] [Story] Descripción`

- **[P]**: puede ejecutarse en paralelo con otras tareas de la misma fase porque toca archivos distintos y no depende de una tarea incompleta.
- **[Story]**: `[US1]`, `[US2]`, `[US3]` o `[US4]`, según la historia de `spec.md`.
- Todas las descripciones incluyen la ruta exacta del archivo que se crea o modifica.

## Historias y criterios de aceptación

| Historia | Prioridad | Criterio independiente | Requisitos principales |
|----------|-----------|------------------------|------------------------|
| **US1** — Ver mi cola priorizada | P1 | Un técnico con tickets propios y ajenos ve solo los suyos, con número, título, categoría, prioridad y SLA, ordenados por prioridad descendente y tiempo restante ascendente. | FR-001–FR-017, FR-036, SC-001, SC-002, SC-005, SC-006, SC-010 |
| **US2** — Identificar riesgo de SLA | P2 | Los tickets vencidos se ven en rojo con texto e icono; los próximos a vencer en ámbar; el límite exacto muestra "Vence ahora"; un SLA corto conserva una fase sin alarma. | FR-008, FR-009, FR-018–FR-022, SC-003, SC-004 |
| **US3** — Filtrar por estado y prioridad | P2 | Los filtros se combinan con Y, muestran el número de resultados, se conservan en la navegación y los finalizados quedan al final por fecha de finalización. | FR-023–FR-029, FR-034, FR-035, SC-006, SC-011, SC-012 |
| **US4** — Entender vacíos y errores | P3 | Un técnico distingue "sin tickets", "solo finalizados", "sin resultados" y "error de carga", con acción de reintento en el error. | FR-030–FR-033, SC-009 |

---

## Fase 1: Infraestructura Base

**Propósito**: crear la estructura de backend y frontend, la configuración, la base de datos y el esqueleto de rutas. Ninguna tarea de esta fase lleva etiqueta de historia.

- [X] T001 Crear la estructura de directorios y paquetes del backend (`backend/app/api/v1`, `backend/app/core`, `backend/app/db`, `backend/app/models`, `backend/app/schemas`, `backend/app/services`, `backend/app/utils`, `backend/tests/{unit,integration,contract}`) con sus `__init__.py`.
- [X] T002 Crear `backend/requirements.txt` con las dependencias fijadas: FastAPI, SQLAlchemy 2.x, psycopg 3, Alembic, Pydantic 2, pydantic-settings, PyJWT, Uvicorn, pytest y httpx.
- [X] T003 Inicializar el frontend Vue 3 + TypeScript con Vite en `frontend/` y añadir a `frontend/package.json` Pinia, Vue Router, Tailwind CSS 3.4, `lucide-vue-next`, Vitest, `@vue/test-utils` y `axe-core`, además de los scripts `test:unit` (`vitest run tests/unit`) y `test:components` (`vitest run tests/components`).
- [X] T004 [P] Configurar Tailwind en `frontend/tailwind.config.js` (content sobre `./index.html` y `./src/**/*.{vue,ts}`) y los estilos base en `frontend/src/assets/main.css`.
- [X] T005 [P] Crear la configuración por variables de entorno en `backend/app/core/config.py` (`DATABASE_URL`, entorno, parámetros de autenticación); no incluir secretos ni valores reales.
- [X] T006 [P] Configurar el engine y la sesión de SQLAlchemy en `backend/app/db/session.py` y la base declarativa en `backend/app/db/base.py`, forzando UTC en la conexión (`timezone=UTC`) y `pool_pre_ping=True`.
- [X] T007 Inicializar Alembic en `backend/alembic.ini` y `backend/alembic/env.py`, apuntando a la metadata de `backend/app/db/base.py` y a `DATABASE_URL`.
- [X] T008 Crear la revisión base de Alembic `backend/alembic/versions/0001_base_schema.py` (con `upgrade()` y `downgrade()`; usar `op.create_table` o `op.execute` para el DDL) con las tablas `users` (`id`, `name`, `email` único, `role`, `team`, `is_active`), `categories` (`id`, `name`, `description`, `is_active`), `priorities` (`id`, `name`, `level` 1–4 con `ck_priorities_level`, `color`, `base_hours`, `is_active`) y `tickets` (`id`, `number` único, `title`, `description`, `status` como `ticket_status`, `priority_id`, `category_id` nullable, `creator_id`, `assignee_id`, `created_at`, `sla_deadline`, `closed_at`, `updated_at`, `sla_version`), con sus claves foráneas y los índices base de `assignee_id` y `status`. No añade `finalized_at`; lo hace T016 (soporte de todas las historias).
- [X] T009 Crear el script de seed `backend/scripts/seed_dev.py` con datos deterministas para los escenarios de `quickstart.md`: técnicos A y B, tickets propios y ajenos, prioridades Crítica/Alta/Media/Baja, un ticket sin categoría, un SLA de 30 min, uno de 4 h, un vencido, uno en el límite exacto, uno sin SLA, uno pendiente de usuario, uno resuelto en plazo y uno cerrado con incumplimiento; idempotente y ejecutable tras `alembic upgrade head` con `python backend/scripts/seed_dev.py` (soporte de todas las historias).
- [X] T010 Crear la app FastAPI en `backend/app/main.py` y el manejador homogéneo de errores en `backend/app/core/errors.py` con el formato `{"detail": {"code", "message"}}` y mensajes en español.
- [X] T011 Crear el router v1 en `backend/app/api/v1/router.py` e incluirlo desde `backend/app/main.py` bajo el prefijo `/api/v1`.
- [X] T012 [P] Crear el router de Vue en `frontend/src/router/index.ts` con la ruta `/cola-de-trabajo` (nombre `work-queue`) y el componente `frontend/src/views/WorkQueuePage.vue` como esqueleto inicial.
- [X] T013 [P] Crear el cliente HTTP tipado en `frontend/src/api/client.ts` que obtenga el token JWT del mecanismo de autenticación existente y envíe `Authorization: Bearer <token>`, con cancelación mediante `AbortController` y normalización de errores 401/403/5xx.
- [X] T014 [P] Crear la configuración de pruebas del backend en `backend/tests/conftest.py` (cliente httpx con `Authorization: Bearer` y un token de prueba válido para técnico, sesión de base de datos de test y limpieza entre pruebas).
- [X] T015 [P] Crear la configuración de pruebas del frontend en `frontend/vitest.config.ts` y `frontend/tests/setup.ts` (entorno jsdom, alias `@`, matchers de Testing Library si se usa).

**Checkpoint**: el backend arranca en `/docs`, el frontend sirve la ruta `/cola-de-trabajo` y las herramientas de test están disponibles.

---

## Fase 2: Backend (FastAPI)

**Propósito**: implementar el modelo, los cálculos de SLA, la consulta, el orden, los filtros, la paginación y el endpoint `GET /api/v1/me/work-queue`.

- [X] T016 [US1] Crear la migración `backend/alembic/versions/0002_add_finalized_at_and_work_queue_indexes.py` que añade `tickets.finalized_at TIMESTAMPTZ NULL`, rellena los finalizados con `COALESCE(closed_at, updated_at)`, añade las restricciones `ck_tickets_finalized_at` (final ⇒ no nulo; no final ⇒ nulo), `ck_tickets_finalized_after_created` y `ck_tickets_sla_deadline_after_created`, y crea los índices `ix_tickets_assignee_status_deadline`, `ix_tickets_assignee_finalized_at`, `ix_tickets_assignee_priority` e `ix_tickets_number` (FR-034, FR-035; soporte US2/US3).
- [X] T017 [US1] Actualizar `backend/app/models/ticket.py` con el enum `ticket_status` (`abierto`, `en_progreso`, `pendiente_usuario`, `resuelto`, `cerrado`), `sla_deadline` y `finalized_at` como `DateTime(timezone=True)`, `number`, `title`, `assignee_id`, `category_id`, `priority_id`, `created_at` y la relación con `Priority` y `Category` (FR-001, FR-003, FR-006).
- [X] T018 [P] [US1] Crear/ajustar `backend/app/models/priority.py` con `id`, `name`, `level` (`SmallInteger`, obligatorio, entre 1 y 4), `color`, `is_active`; documentar que `level = 1` es Crítica y `4` es Baja (FR-012).
- [X] T019 [P] [US1] Crear/ajustar `backend/app/models/category.py` con `id`, `name`, `description`, `is_active`; `name` no nulo y `is_active` no nulo (FR-006).
- [X] T020 [P] [US1] Crear/ajustar `backend/app/models/user.py` con `id`, `name`, `email`, `role` (`usuario`, `tecnico`, `supervisor`, `admin`), `team`, `is_active`; `email` único (FR-001, FR-033).
- [X] T021 [US2] Implementar `backend/app/utils/sla.py` con funciones puras: `warning_threshold_seconds(total_seconds)` (`< 3600` → mitad; si no `max(3600, total//4)`), `classify_sla(*, is_final, deadline, started_at, now)` y `sla_outcome(finalized_at, deadline)` / `breach_delay_seconds(finalized_at, deadline)`; usar `floor` para el tiempo restante y `<=` para el límite exacto (FR-008, FR-009, FR-018–FR-020, RN-09).
- [X] T022 [US1] Crear los esquemas Pydantic en `backend/app/schemas/work_queue.py`: query params (`status`, `priority`, `page`, `page_size`), `WorkQueueItem`, `SlaInfo`, `Pagination`, `Counts`, `AvailableFilters`, `AppliedFilters`, `Meta` y `ErrorResponse`, coherentes con `contracts/work-queue.openapi.yaml`; `category` es nullable (`CategoryRef | None`, se serializa como `null` cuando el ticket no tiene categoría), `priority` acepta solo 1–4 y `page_size` solo 1–100 (FR-006, FR-023–FR-026).
- [X] T023 [US1] Implementar `get_current_user` y la dependencia de rol en `backend/app/api/deps.py` resolviendo el usuario desde el token JWT de `Authorization: Bearer` (sin cookie de sesión): token ausente, inválido o caducado → 401; rol distinto de `tecnico` → 403; devolver el `User` autenticado sin aceptar identificadores de técnico por query (FR-001, FR-002, FR-033).
- [X] T024 [US1] Implementar en `backend/app/services/work_queue.py` la consulta base con `Ticket.assignee_id == current_user.id`, `LEFT JOIN categories`, `JOIN priorities`, estados activos por defecto (`abierto`, `en_progreso`, `pendiente_usuario`) y una única captura de `now` UTC por petición (FR-001–FR-004, FR-010).
- [X] T025 [US1] Añadir a `backend/app/services/work_queue.py` el orden de activos: `CASE` activo/final, `priority.level ASC`, `sla_deadline ASC NULLS LAST`, `number ASC`, aplicado antes de paginar (FR-012–FR-017).
- [X] T026 [US1] Añadir a `backend/app/services/work_queue.py` la paginación con `COUNT(*)` sobre los mismos predicados, tamaño de página de 25 por defecto admitido entre 1 y 100, `offset = (page-1)*page_size`, ajuste de `page` a la última página disponible y metadatos `total_pages`, `has_next`, `has_previous` (FR-017, FR-026, FR-036).
- [X] T027 [US3] Añadir a `backend/app/services/work_queue.py` los filtros combinados con Y: `status` explícito (incluidos `resuelto` y `cerrado`), `priority` por nivel 1–4, y el bloque de orden de finalizados `finalized_at DESC NULLS LAST`, `number ASC` después de todos los activos (FR-023–FR-025, FR-035).
- [X] T028 [US2] Mapear en `backend/app/services/work_queue.py` los derivados de SLA por elemento: `started_at`, `total_seconds`, `remaining_seconds`, `warning_threshold_seconds`, `state`, `outcome`, `finalized_at` y `breach_delay_seconds`; los finalizados usan `state = finalized`, `remaining_seconds = null` y `warning_threshold_seconds = null`, y no reciben alerta activa; `outcome`, `finalized_at` y `breach_delay_seconds` solo se rellenan según corresponda (FR-006, FR-008–FR-010, FR-034).
- [X] T029 [US3] Calcular en `backend/app/services/work_queue.py` `counts.active` y `counts.finalized` mediante una consulta agregada independiente, sin aplicar los filtros de la petición (solo `assignee_id = current_user.id`), `available_filters` sobre toda la cola del técnico (estados con etiqueta e `is_final`, prioridades presentes con `level`/`color`/`is_active`, sin contadores por opción) y `applied_filters`; no se añaden contadores agregados de riesgo ni `by_status` (FR-024–FR-026, FR-030).
- [X] T030 [US1] Implementar el endpoint `GET /api/v1/me/work-queue` en `backend/app/api/v1/work_queue.py` con `response_model=WorkQueueResponse`, parámetros validados, llamada al servicio y cabeceras `Cache-Control: no-store` y `Vary: Authorization` (FR-001, FR-006, FR-005).
- [X] T031 [US1] Registrar el endpoint en `backend/app/api/v1/router.py` y mapear en `backend/app/core/errors.py` los errores 401/403/422/500 con mensajes en español, sin filtrar detalles internos (FR-002, FR-033).

**Checkpoint**: el endpoint responde según el contrato para US1, US2 y US3; se puede probar con `curl` antes de construir el frontend.

---

## Fase 3: Frontend (Vue 3)

**Propósito**: construir el estado, la vista y los componentes que muestran la cola con los cinco datos exigidos, además de los estados vacíos y de error.

- [X] T032 [US1] Definir en `frontend/src/types/workQueue.ts` los tipos `WorkQueueItem`, `SlaInfo`, `SlaState`, `SlaOutcome`, `Pagination`, `Counts`, `AvailableFilters`, `AppliedFilters`, `Meta` y `WorkQueueResponse`, alineados con el contrato OpenAPI.
- [X] T033 [US1] Implementar `frontend/src/api/workQueue.ts` con `fetchWorkQueue(params, signal)` que construya `status`, `priority`, `page` y `page_size`, use `frontend/src/api/client.ts` y devuelva el tipo `WorkQueueResponse`.
- [X] T034 [US1] Crear el store Pinia en `frontend/src/stores/workQueue.ts` con estado `items`, `pagination`, `counts`, `availableFilters`, `appliedFilters`, `loading`, `refreshing`, `error`, `lastUpdatedAt` y la acción `fetchQueue({ silent })` (FR-001, FR-006, FR-011).
- [X] T035 [US1] Añadir al store `frontend/src/stores/workQueue.ts` el polling cada 60 s, la recarga al recuperar foco/visibilidad, la cancelación con `AbortController` y la protección contra respuestas fuera de orden (FR-005, RN-14).
- [X] T036 [US1] Implementar `frontend/src/utils/sla.ts` con `formatRemaining(seconds)` para días/horas, horas/minutos, minutos, "menos de 1 min", "Vence ahora" y "Vencido hace [tiempo]" (FR-007–FR-009).
- [X] T037 [US1] Implementar `frontend/src/composables/useSlaClock.ts` con un tick local de 30 s basado en `performance.now()` y el ancla `remaining_seconds`; exponer un `now` reactivo y resincronizar al recibir datos nuevos (FR-005, RN-04, RN-14).
- [X] T038 [US1] Implementar la estructura base de `frontend/src/components/work-queue/SlaIndicator.vue` para recibir `state`, `remainingSeconds`, `outcome` y `breachDelaySeconds`, y renderizar icono + texto + duración con `formatRemaining` (FR-006–FR-010).
- [X] T039 [P] [US1] Implementar `frontend/src/components/work-queue/PriorityBadge.vue` con el nombre de la prioridad y un color estático por nivel (1 Crítica, 2 Alta, 3 Media, 4 Baja), incluyendo texto además de color (FR-006, FR-022).
- [X] T040 [P] [US1] Implementar `frontend/src/components/work-queue/StatusBadge.vue` con las etiquetas en español: Abierto, En progreso, Pendiente de usuario, Resuelto y Cerrado (FR-006, FR-023).
- [X] T041 [US1] Implementar `frontend/src/components/work-queue/WorkQueueRow.vue` mostrando número, título, categoría, prioridad, estado y SLA; número y título enlazan a `/tickets/:id` (detalle de la HU-06, fuera de alcance) y el título largo se trunca con acceso al texto completo (FR-006, caso límite de título).
- [X] T042 [US1] Implementar `frontend/src/components/work-queue/WorkQueueTable.vue` como tabla semántica con `<caption>` oculto y columnas Ticket, Título, Categoría, Prioridad, Estado y SLA (FR-006, RN-16).
- [X] T043 [US1] Construir la estructura de `frontend/src/views/WorkQueuePage.vue`: cabecera en español, zona de filtros y puntos de montaje para tabla, paginación, estados vacío/error y skeleton; integra `WorkQueueTable.vue` y deja el resto para T044–T049 y la Fase 5 (FR-006, FR-011).
- [X] T044 [P] [US1] Implementar `frontend/src/components/work-queue/WorkQueueSkeleton.vue` con filas de carga que respeten el layout de la tabla y solo se muestren en la primera carga (FR-011).
- [X] T045 [US1] Implementar `frontend/src/components/work-queue/WorkQueuePagination.vue` con Anterior/Siguiente, página actual y total de páginas; deshabilitar controles durante la carga (FR-017, FR-036).
- [X] T046 [US4] Implementar `frontend/src/components/work-queue/WorkQueueEmptyState.vue` con las variantes `no_assignments` ("No tienes tickets asignados actualmente"), `only_final` ("No tienes tickets activos…") y `no_results` ("No hay resultados para los filtros seleccionados" + "Limpiar filtros") (FR-030, FR-031).
- [X] T047 [US4] Implementar `frontend/src/components/work-queue/WorkQueueErrorState.vue` con mensaje diferenciado "No se pudo cargar tu cola de trabajo", botón "Reintentar" y variante de aviso para fallo durante un refresco con datos previos (FR-032).
- [X] T048 [US4] Añadir al store `frontend/src/stores/workQueue.ts` el mapeo de errores 401 → redirección a login con retorno a `/cola-de-trabajo`, 403 → acceso no autorizado, 5xx/red → error con reintento; conservar los datos previos si falla un refresco (FR-032, FR-033).
- [X] T049 [US1] Integrar en `frontend/src/views/WorkQueuePage.vue` el store, la tabla, la paginación, el skeleton y el polling, sin recargar la página (FR-005, FR-011).
- [X] T050 [US1] Cubrir en `frontend/src/components/work-queue/WorkQueueRow.vue` y `frontend/src/components/work-queue/WorkQueueTable.vue` los casos de título largo, categoría ausente ("Sin categoría") y prioridad desactivada, sin romper la alineación ni el orden (casos límite de la spec).
- [X] T051 [US4] Implementar en `frontend/src/views/WorkQueuePage.vue` la selección del estado vacío correcto: sin asignaciones, solo finalizados, sin resultados o error, usando `counts` y `pagination.total_items` (FR-030–FR-032).

**Checkpoint**: US1 funciona de extremo a extremo (lista propia, cinco datos, orden, SLA, paginación) y US4 muestra estados diferenciados.

---

## Fase 4: Lógica Visual (Tailwind)

**Propósito**: aplicar el formato condicional accesible que distingue tickets vencidos, próximos a vencer y dentro de plazo, sin depender solo del color.

- [X] T052 [US2] Crear `frontend/src/utils/slaStyles.ts` con mapas estáticos `SLA_ROW_CLASS`, `SLA_BADGE_CLASS`, `PRIORITY_BADGE_CLASS` y `SLA_ICON` para los estados `overdue`, `at_risk`, `on_time`, `no_sla` y `finalized`; usar clases Tailwind completas, nunca interpoladas (FR-018–FR-022).
- [X] T053 [US2] Aplicar en `frontend/src/components/work-queue/WorkQueueRow.vue` el mapa `SLA_ROW_CLASS`: rojo suave para vencido, ámbar suave para próximo a vencer, blanco para dentro de plazo y sin SLA, gris neutro para finalizado (FR-018–FR-021).
- [X] T054 [US2] Aplicar en `frontend/src/components/work-queue/PriorityBadge.vue` el mapa estático por nivel y verificar contraste de texto ≥ 4.5:1 (FR-022, RN-16).
- [X] T055 [US2] Implementar en `frontend/src/components/work-queue/SlaIndicator.vue` el estado `overdue`: icono `AlertOctagon`, texto "Vencido hace [tiempo]" y estilo rojo, con etiqueta accesible completa (FR-009, FR-018, FR-022).
- [X] T056 [US2] Implementar en `frontend/src/components/work-queue/SlaIndicator.vue` el estado `at_risk`: icono `AlertTriangle`, texto "Próximo a vencer · [tiempo]" y estilo ámbar (FR-019, FR-022).
- [X] T057 [US2] Implementar en `frontend/src/utils/sla.ts` y `frontend/src/components/work-queue/SlaIndicator.vue` el caso de tiempo restante exactamente cero: "Vence ahora", ámbar y aún no vencido; con tiempo negativo pasa a "Vencido hace [tiempo]" (FR-008, FR-009).
- [X] T058 [US2] Implementar el estado `on_time` en `frontend/src/components/work-queue/SlaIndicator.vue`: icono `CheckCircle2`, texto "Dentro de plazo · [tiempo]" y estilo neutro/verde suave (FR-019, FR-022).
- [X] T059 [US2] Implementar el estado `no_sla` en `frontend/src/components/work-queue/SlaIndicator.vue`: icono `MinusCircle`, texto "Sin SLA definido", estilo gris y ausencia de alarma (FR-010, FR-015).
- [X] T060 [US3] Implementar en `frontend/src/components/work-queue/SlaIndicator.vue` y `WorkQueueRow.vue` el estado `finalized`: "Dentro de plazo", "Incumplido hace [tiempo]" o "Sin SLA definido", sin cuenta atrás ni destacado de riesgo activo (FR-034, RN-13).
- [X] T061 [US2] Ajustar en `frontend/src/components/work-queue/WorkQueueRow.vue` y `frontend/src/components/work-queue/WorkQueueTable.vue` el foco visible, los `aria-label` de las celdas de riesgo y el contraste de todos los estados (RN-16).
- [X] T062 [US2] Añadir en `frontend/src/components/work-queue/SlaIndicator.vue` la información no cromática: texto visible, icono con `aria-hidden="true"` y una etiqueta accesible que incluya estado y tiempo; no anunciar cada tick con `aria-live` (FR-022, RN-16).
- [X] T063 [US2] Reclasificar en `frontend/src/composables/useSlaClock.ts` y `frontend/src/utils/sla.ts` el estado de SLA en cada tick usando los segundos restantes y el umbral recibido, para que un ticket pase de ámbar a rojo entre polls sin esperar 60 s (FR-008, FR-009, FR-019, RN-14).

**Checkpoint**: US2 se valida visualmente con un ticket vencido, uno a 10 minutos de un SLA de 4 h, uno de SLA de 30 min con 20 min restantes, uno en el límite exacto y uno sin SLA.

---

## Fase 5: Filtros por estado y prioridad

**Propósito**: implementar los filtros combinados, su reflejo en URL, el número de resultados y la interacción con los estados finales.

- [X] T064 [US3] Implementar `frontend/src/components/work-queue/WorkQueueFilters.vue` con dos `fieldset` + `legend` (Estado y Prioridad), checkboxes tipo chip, etiquetas en español y botón "Limpiar filtros"; emitir los cambios al padre sin llamar a la API (FR-023–FR-027, RN-16).
- [X] T065 [US3] Añadir al store `frontend/src/stores/workQueue.ts` las acciones `setStatusFilter`, `setPriorityFilter`, `clearFilters` y `setPage`, y los getters `isDefaultFilter`, `hasActiveFilters` y `activeFilterCount` (FR-023–FR-028).
- [X] T066 [US3] Sincronizar en `frontend/src/stores/workQueue.ts` los filtros con la query de la URL (`estado`, `prioridad`, `pagina`) usando `frontend/src/router/index.ts`: leer al montar, validar contra `available_filters`, descartar valores inválidos, escribir con `router.replace` y soportar atrás/adelante (FR-028).
- [X] T067 [US3] Aplicar en `frontend/src/stores/workQueue.ts` un debounce de 250 ms al cambiar filtros, reiniciar `page = 1` y construir los parámetros `status`, `priority` y `page` para `frontend/src/api/workQueue.ts` (FR-023–FR-025, FR-028).
- [X] T068 [US3] Mostrar en `frontend/src/views/WorkQueuePage.vue` y `frontend/src/components/work-queue/WorkQueueFilters.vue` el número de tickets resultantes (`pagination.total_items`) y actualizarlo tras cada filtro (FR-026).
- [X] T069 [US3] Implementar en `frontend/src/components/work-queue/WorkQueueFilters.vue` y `frontend/src/stores/workQueue.ts` la acción "Limpiar filtros", que restablece los estados activos por defecto, la prioridad vacía y la página 1, y recarga la cola (FR-027).
- [X] T070 [US3] Integrar en `frontend/src/views/WorkQueuePage.vue` el estado `no_results` cuando `hasActiveFilters` y `pagination.total_items === 0`, con el botón "Limpiar filtros", distinguiéndolo del vacío por falta de asignaciones (FR-031).
- [X] T071 [US3] Asegurar en `frontend/src/components/work-queue/WorkQueueTable.vue` que un filtro mixto de estados activos y finales muestre primero todos los activos con su orden de urgencia y después los finalizados por `finalized_at DESC`, sin mezclarlos (FR-035, RN-17).
- [X] T072 [US3] Mantener en `frontend/src/stores/workQueue.ts` los filtros aplicados al recargar la página, al cambiar de página y al abrir la misma URL en otra pestaña, sin perderlos (FR-028).
- [X] T073 [US3] Verificar y ajustar en `frontend/src/components/work-queue/WorkQueueFilters.vue` la navegación por teclado, el foco visible, las etiquetas asociadas y el contraste de los chips de filtro (RN-16).

**Checkpoint**: US3 se valida filtrando por estado, por prioridad, por ambos a la vez, limpiando filtros, comprobando el número de resultados y revisando un filtro mixto con finalizados al final.

---

## Fase 6: Verificación

**Propósito**: demostrar que la funcionalidad cumple la spec mediante pruebas automatizadas, comprobaciones manuales de `quickstart.md` y una revisión final de rendimiento y accesibilidad. Sin etiquetas de historia: cada tarea referencia los FR/SC que valida.

- [X] T074 [P] Implementar las pruebas unitarias de SLA en `backend/tests/unit/test_sla.py`: umbrales de 30, 59, 60 minutos, 4 h y 24 h; límite exacto 0 → `at_risk`; −1 s → `overdue`; borde 15:30 con SLA de 30 min → `on_time`; sin SLA; finalizado `met`/`breached`/`no_sla`; `breach_delay_seconds` (US2; FR-008, FR-009, FR-018–FR-020).
- [X] T075 Implementar las pruebas de integración de propiedad, orden y paginación en `backend/tests/integration/test_work_queue_api.py`: solo tickets del técnico autenticado, `technician_id` inyectado sin efecto, prioridad descendente, deadline ascendente, vencidos primero, sin SLA al final, desempate por número, páginas sin solapes y ticket con `category_id = NULL` serializado como `category: null` (US1; FR-001–FR-017, FR-036, SC-001, SC-010).
- [X] T076 Implementar las pruebas de integración de filtros, contadores de cola y orden mixto en `backend/tests/integration/test_work_queue_api.py`: filtros Y, estados finales, prioridad, `total_items`, `counts.active`/`counts.finalized`, `available_filters` sin contadores por opción y finalizados después de activos por `finalized_at DESC` (US3; FR-023–FR-027, FR-035, SC-012).
- [X] T077 Implementar las pruebas de autenticación, errores y cola vacía en `backend/tests/integration/test_work_queue_api.py`: 401 sin token o con token inválido/caducado, 403 con rol no técnico, 422 con estado/prioridad/página inválidos, 500 controlado y `counts.active`/`counts.finalized` a cero (US4; FR-002, FR-030–FR-033, SC-009).
- [X] T078 [P] Implementar la prueba de contrato en `backend/tests/contract/test_work_queue_contract.py` que valide la respuesta real contra `specs/004-prioritized-work-queue/contracts/work-queue.openapi.yaml` y los códigos 200/401/403/422/500 (US1; FR-006). Incluir un caso con ticket finalizado que compruebe `state: finalized`, `remaining_seconds: null` y `warning_threshold_seconds: null`.
- [X] T079 [P] Implementar en `frontend/tests/unit/sla.spec.ts` los vectores de formato y clasificación compartidos con el backend: días/horas/minutos, menos de un minuto, cero, negativo, umbral corto, umbral largo, borde 15:30 → `on_time` y paridad de `classify` (US2; FR-007–FR-009, FR-018–FR-020).
- [X] T080 Implementar en `frontend/tests/unit/workQueue.store.spec.ts` las pruebas de `fetchQueue`, polling con fake timers, recarga al recuperar foco, cancelación de peticiones y protección contra respuestas fuera de orden (US1; FR-005).
- [X] T081 Implementar en `frontend/tests/unit/workQueue.store.spec.ts` las pruebas de mapeo de 401/403/500, conservación de datos en error de refresco, filtros en URL y estados `no_assignments`/`only_final`/`no_results` (US3, US4; FR-028, FR-030–FR-033).
- [X] T082 [P] Implementar en `frontend/tests/components/WorkQueueTable.spec.ts` las pruebas de los cinco datos por fila, `href` de número y título hacia `/tickets/:id`, título truncado, categoría ausente y prioridad inactiva (US1; FR-006, casos límite).
- [X] T083 [P] Implementar en `frontend/tests/components/SlaIndicator.spec.ts` las pruebas de color/texto/icono para `overdue`, `at_risk`, `on_time`, `no_sla` y `finalized`, incluido "Vence ahora" y la ausencia de alerta en finalizados (US2; FR-008–FR-010, FR-018–FR-022, FR-034).
- [X] T084 [P] Implementar en `frontend/tests/components/WorkQueueFilters.spec.ts` las pruebas de selección/deselección, combinación Y, número de resultados (`pagination.total_items`), limpieza, foco por teclado y estado `no_results` (US3; FR-023–FR-028, FR-031).
- [ ] T085 Ejecutar y documentar en `specs/004-prioritized-work-queue/quickstart.md` los escenarios V-01 a V-07: propiedad, orden, vencido, próximo a vencer, SLA corto, límite exacto y sin SLA (US1, US2; SC-001–SC-004, SC-010). Incluir la medición cronometrada de SC-002 descrita en V-02.
- [ ] T086 Ejecutar y documentar en `specs/004-prioritized-work-queue/quickstart.md` los escenarios V-08 a V-11: filtro por estado, por prioridad, combinados/limpieza y finalizados al final con resultado histórico (US2, US3; SC-006, SC-011, SC-012). Incluir la medición cronometrada de SC-006 descrita en V-10.
- [ ] T087 Ejecutar y documentar en `specs/004-prioritized-work-queue/quickstart.md` los escenarios V-12 a V-16: cola sin asignaciones, solo finalizados, sin resultados, error con reintento y sesión caducada (US4; FR-030–FR-033, SC-009).
- [ ] T088 Ejecutar y documentar en `specs/004-prioritized-work-queue/quickstart.md` los escenarios V-17 a V-22: actualización automática, cambio de hora, paginación, accesibilidad, título/categoría y prioridad desactivada (US1–US4; FR-005, FR-017, FR-022, RN-16).
- [X] T089 Medir con 100 tickets en `backend/tests/integration/test_work_queue_api.py` el tiempo de la consulta y del endpoint, comprobar el uso de los índices con `EXPLAIN` y registrar que la vista cumple p95 < 2 s y consulta < 300 ms (US1; SC-005).
- [ ] T090 Ejecutar la suite completa (`pytest`, `npm run test:unit -- --run`, `npm run test:components -- --run`) y cerrar la validación marcando los escenarios de `quickstart.md`; no cerrar la historia si queda algún FR/SC sin evidencia (US1–US4).

**Checkpoint**: todas las pruebas y escenarios manuales pasan; el contrato OpenAPI es válido y no hay tickets ajenos visibles.

---

## Dependencias y orden de ejecución

### Dependencias entre fases

- **Fase 1 (T001–T015)**: no depende de nada; debe completarse antes de cualquier otra fase.
- **Fase 2 (T016–T031)**: depende de T001–T011 y T014. Bloquea la integración frontend.
- **Fase 3 (T032–T051)**: depende de T012, T013 y de que el contrato del backend esté estable (T022, T030, T031).
- **Fase 4 (T052–T063)**: depende de T036, T037, T038 y T041.
- **Fase 5 (T064–T073)**: depende de T034, T035, T042 y de los filtros y el número de resultados del backend (T027, T029).
- **Fase 6 (T074–T090)**: depende de todas las fases anteriores.

### Dependencias por historia

- **US1 (P1, MVP)**: T016–T020, T022–T026, T030–T031, T032–T045, T049–T050. Es la base del resto.
- **US2 (P2)**: T021, T028, T038, T041, T052–T063. Depende de la fila e indicador de US1.
- **US3 (P2)**: T027, T029, T064–T073. Depende de la tabla/estado de US1 y de los filtros del backend.
- **US4 (P3)**: T046–T048, T051. Depende del store y la página de US1.

### Orden dentro de cada fase

1. Modelo/migración antes de servicio y endpoint.
2. Funciones puras de SLA antes de mapear la respuesta.
3. Store y tipos antes de componentes.
4. Componentes base antes del formato condicional.
5. Filtros después de que la lista y el orden funcionen.
6. Pruebas automatizadas antes de la validación manual final.

---

## Oportunidades de paralelización

- **Infraestructura**: T004, T005, T006, T012, T013, T014 y T015 tocan archivos distintos y pueden repartirse; T008 (migración base) debe preceder a T009 (seed) y a T016.
- **Backend**: T018, T019 y T020 son modelos independientes; T021 (SLA) puede hacerse en paralelo con T022 (esquemas) si se acuerda antes la firma.
- **Frontend**: T039, T040 y T044 son componentes independientes; T036 (formato) y T037 (reloj) también pueden hacerse en paralelo.
- **Pruebas**: T074, T078, T079 y T082–T084 son archivos de test distintos y pueden ejecutarse en paralelo una vez implementadas las capas. T075–T077 comparten `test_work_queue_api.py` y T080–T081 comparten `workQueue.store.spec.ts`: deben ejecutarse en orden.
- **No paralelizar**: T052–T063 comparten `slaStyles.ts`, `SlaIndicator.vue` y `WorkQueueRow.vue`; T064–T073 comparten el store y los filtros. Deben ir en orden.

### Ejemplo de paralelización en US1

```text
T018 [P] Modelo Priority
T019 [P] Modelo Category
T020 [P] Modelo User
→ después: T024 consulta base

T039 [P] PriorityBadge
T040 [P] StatusBadge
T044 [P] WorkQueueSkeleton
→ después: T049 integración de la página
```

### Ejemplo de paralelización en verificación

```text
T074 [P] test_sla.py
T078 [P] test_work_queue_contract.py
T079 [P] sla.spec.ts
T082 [P] WorkQueueTable.spec.ts
T084 [P] WorkQueueFilters.spec.ts
```

---

## Estrategia de implementación

### MVP primero (solo US1)

1. Completar Fase 1.
2. Completar las tareas de backend de US1 (T016–T020, T022–T026, T030–T031), incluida la utilidad de SLA necesaria para mostrar el tiempo restante (T021) y la derivación de datos (T028).
3. Completar las tareas de frontend de US1 (T032–T045, T049–T050).
4. **Parar y validar**: un técnico ve solo sus tickets, con los cinco datos, en el orden correcto y con SLA; se puede demostrar sin filtros ni destacados avanzados.

### Entrega incremental

1. Fase 1 + Fase 2 + Fase 3 → US1 desplegable.
2. Fase 4 → US2: destacado de riesgo y resultado histórico.
3. Fase 5 → US3: filtros combinados, número de resultados y finalizados.
4. Tareas US4 de Fase 3 + T087 → US4: vacíos, errores y token caducado.
5. Fase 6 → verificación completa y cierre.

### Estrategia de equipo

- Una persona puede asumir backend (Fase 2) y otra frontend (Fase 3) después de T022/T030.
- La lógica visual (Fase 4) debe esperar a que la fila y el indicador existan; no se paraleliza con T038/T041.
- Los filtros (Fase 5) no deben empezar hasta que el orden y la tabla funcionen.
- La verificación (Fase 6) se reparte por archivos de test, pero T090 es la puerta final única.

---

## Notas

- Marcar `[x]` solo cuando la tarea esté implementada y su criterio verificable se haya comprobado.
- No añadir funcionalidades fuera de `spec.md`: nada de reasignación, cambio de estado, edición, notificaciones ni colas de equipo.
- No usar interpolación de clases Tailwind (`bg-${color}-100`); todas las clases deben existir en `slaStyles.ts`.
- No calcular la cuenta atrás con `new Date()` contra el deadline; usar `remaining_seconds` + `performance.now()`.
- No aceptar identificadores de técnico por query; la identidad sale del token JWT de `Authorization: Bearer`.
- Mantener los mensajes y etiquetas en español de España y las fechas absolutas en `Europe/Madrid`.
- Ejecutar `quickstart.md` con datos de prueba que cubran SLA vencido, SLA corto, límite exacto, sin SLA y cola vacía.

---

## Phase 7: Convergence

- [X] T091 Corregir en `frontend/src/stores/workQueue.ts` y `frontend/src/views/WorkQueuePage.vue` la reentrada tras un 401: al montar de nuevo la vista, limpiar el error `unauthorized`, releer los filtros de la URL y recargar la cola aunque el store ya esté inicializado, de modo que tras autenticarse se vuelva a `/cola-de-trabajo` con datos; añadir la prueba correspondiente en `frontend/tests/unit/workQueue.store.spec.ts` (FR-033, FR-028) (contradicts).
- [X] T092 Mostrar en `frontend/src/components/work-queue/WorkQueueFilters.vue` la indicación «(inactiva)» en los chips de prioridad cuyo `is_active` sea `false`, manteniéndolas disponibles para filtrar, y cubrirlo en `frontend/tests/components/WorkQueueFilters.spec.ts` (spec: prioridad desactivada) (partial).
- [X] T093 Añadir en `frontend/tests/components/` una comprobación con `axe-core` (ya instalado) sobre la tabla, los filtros y los estados vacío/error, fallando ante violaciones críticas de accesibilidad (RN-16, plan: testing frontend) (missing).
- [X] T094 Añadir en `backend/tests/unit/test_sla.py` la prueba de regresión de cambio de hora oficial: el mismo deadline UTC consultado antes y después del salto de verano/invierno mantiene la diferencia real de segundos y no produce saltos de una hora (RN-04, plan: DST) (missing).
- [X] T095 Añadir una configuración de pruebas de backend contra PostgreSQL 16 (variable de entorno opcional, p. ej. `TEST_DATABASE_URL`) y ejecutar `alembic upgrade head`/`downgrade` y la suite completa sobre ella, manteniendo SQLite como fallback local; documentar el comando en `quickstart.md` (plan: PostgreSQL test database) (partial).
- [X] T096 Añadir pruebas de componente para `frontend/src/components/work-queue/WorkQueueErrorState.vue` (variantes `full`, `warning` y `forbidden`, emisión de `retry` y distinción frente al vacío) y para la variante `only_final` de `frontend/src/components/work-queue/WorkQueueEmptyState.vue`, verificando que los tres estados vacíos son distintos (SC-009, plan: testing frontend) (missing).
- [X] T097 Añadir pruebas de componente para `frontend/src/components/work-queue/WorkQueuePagination.vue`: texto «Página X de Y», emisión de `change` y botones Anterior/Siguiente deshabilitados por límites o durante la carga (FR-036) (missing).
- [X] T098 Alinear `PRIORITY_BADGE_CLASS` en `frontend/src/utils/slaStyles.ts` con la decisión de `plan.md` §2.4 (nivel 3 Media → azul, nivel 4 Baja → gris), verificando el contraste ≥ 4,5:1 (plan: priority colors) (contradicts).
- [X] T099 Ajustar en `frontend/src/components/work-queue/WorkQueueErrorState.vue` y `frontend/src/views/WorkQueuePage.vue` el aviso de fallo durante un refresco para que indique que se muestran los últimos datos («No se pudo actualizar; se muestran los últimos datos.»), sin reutilizar el mensaje de error de carga inicial (plan: refresh error message) (partial).
- [X] T100 Revisar y justificar o retirar la vista placeholder `frontend/src/views/TicketDetailPlaceholder.vue` y su ruta `/tickets/:id`, añadidas fuera del alcance de la HU-04; si se mantienen, documentar que solo evitan un 404 y no implementan la HU-06 (plan: ticket detail out of scope) (unrequested).

---

## Phase 8: Contenerización y despliegue

**Propósito**: empaquetar backend y frontend en imágenes reproducibles y levantar la aplicación completa con Docker Compose, sin pasos manuales y con datos persistentes.

- [X] T101 Crear `Dockerfile` multi-etapa en la raíz con las etapas `frontend-build`, `frontend`, `backend-builder` y `backend`; compilar la SPA con Node/Vite, servirla con Nginx y ejecutar FastAPI con Python 3.12 como usuario sin privilegios (FR-037, RNF-12). Incluye `@types/node` y la exclusión de `vitest.config.ts` del `tsconfig.json` de producción para que `vue-tsc --noEmit && vite build` funcione dentro de la imagen.
- [X] T102 Crear `.dockerignore` en la raíz excluyendo `.git`, dependencias locales, entornos virtuales, secretos, artefactos de pruebas, bases de datos locales y documentación (FR-038, RNF-11).
- [X] T103 Crear `frontend/nginx.conf` con fallback de SPA, sonda `/healthz` y proxy inverso de `/api/` hacia `backend:8000` (FR-040).
- [X] T104 Crear `backend/docker/entrypoint.sh` que aplique `alembic upgrade head` con reintentos acotados y lance Uvicorn con `--proxy-headers`; añadir `.gitattributes` para forzar finales de línea LF (FR-040, RNF-13).
- [X] T105 Crear `docker-compose.yml` con los servicios `db` (PostgreSQL 16), `backend` y `frontend`, healthchecks, dependencias de arranque, puertos configurables y volumen nombrado `ticketing_db_data` (FR-039, FR-041, RNF-09, RNF-10).
- [X] T106 Crear `.env.example` con todas las variables de entorno documentadas y sin secretos reales: puertos, `POSTGRES_*`, `DATABASE_URL`, `JWT_SECRET`, emisor/audiencia, CORS, reintentos y `VITE_API_BASE_URL` (FR-042, RNF-11).
- [X] T107 Crear `README.md` en la raíz con arranque rápido, arquitectura, tabla de variables, persistencia, seed opcional, comandos habituales, pruebas, desarrollo sin contenedores y solución de problemas (FR-043).
- [X] T108 Actualizar `specs/001-helpdesk-ticketing/spec.md`, `specs/004-prioritized-work-queue/spec.md`, `plan.md` y `quickstart.md` con los requisitos, el diseño y las instrucciones de despliegue contenerizado (FR-037–FR-043, RNF-09–RNF-13).
- [X] T109 Validar la sintaxis y la interpolación de `docker-compose.yml` con `docker compose config`, comprobando que las variables por defecto, el volumen y los healthchecks quedan resueltos (FR-039, FR-041, FR-042).
- [X] T110 Construir las imágenes (`docker compose build`) y verificar el arranque limpio con `docker compose up`, la migración automática, la persistencia tras `down`/`up` y el proxy `/api` (SC-013). Verificado el 2026-11-01: `db`, `backend` y `frontend` arrancan sanos, Alembic aplica `0002_work_queue` sin pasos manuales, `/` y `/api/v1/me/work-queue` responden a través de Nginx (200 y 401 sin JWT), el seed deja 10 tickets que sobreviven a `down`/`up` y `down -v` deja la base vacía.
