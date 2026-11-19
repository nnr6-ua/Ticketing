---

description: "Task list for HU-08: configuración de categorías, prioridades y plazos SLA"
---

# Tasks: Configuración de categorías, prioridades y plazos (HU-08)

**Input**: Design documents from `/specs/008-configuracion-plazos-sla/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`

**Tests**: Incluidos porque `plan.md` §9 define explícitamente las suites de backend, frontend, contrato, concurrencia, rendimiento y accesibilidad. Escribir las pruebas de cada historia antes de su implementación y verificar que fallan primero.

**Organization**: Tareas agrupadas por historia de usuario para permitir implementación y validación independientes. Las historias comparten archivos de router, servicio, store y página; por eso el orden recomendado es US1 → US2 → US3 → US4 → US5.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Puede ejecutarse en paralelo (archivos distintos, sin dependencias de tareas incompletas)
- **[Story]**: Historia de usuario a la que pertenece la tarea (`US1`–`US5`)
- Todas las tareas incluyen la ruta exacta del archivo que deben modificar o crear

## Path Conventions

- Backend: `backend/app/`, `backend/alembic/`, `backend/tests/`
- Frontend: `frontend/src/`, `frontend/tests/`
- Contratos y documentación de la feature: `specs/008-configuracion-plazos-sla/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Preparar enums, errores, tipos compartidos y credenciales de desarrollo.

- [X] T001 Añadir `ConfigEntityType` (`category`, `priority`, `sla_rule`) y `ConfigAction` (`create`, `update`, `deactivate`, `reactivate`, `delete`, `set_default`, `rule_upsert`, `rule_retire`) a `backend/app/models/enums.py`, persistiendo el valor con `values_callable` como en `TicketStatus`.
- [X] T002 [P] Añadir a `backend/app/core/errors.py` los códigos y mensajes estables `stale_configuration`, `duplicate_catalog_name`, `duplicate_priority_level`, `duplicate_sla_rule`, `last_active_catalog_item`, `default_replacement_required`, `catalog_in_use`, `default_catalog_item`, `system_catalog_item`, `inactive_catalog_item`, `empty_batch`, `configuration_not_initialized` y `configuration_not_configured`, además del mensaje de `require_admin`.
- [X] T003 [P] Crear `frontend/src/types/adminConfiguration.ts` con los tipos espejo de `ConfigurationVersionRef`, `CategoryAdmin`, `PriorityAdmin`, peticiones de alta/edición/borrado, `SlaRuleAdmin`, `SlaMatrixResponse`, `SlaBatchRequest`, `SlaBatchResponse`, `ConfigHistoryEntry`, paginación y error `{ detail: { code, message } }`; los decimales se tipan como `string`.
- [X] T004 [P] Añadir el usuario de desarrollo `admin@example.com` con rol `admin` en `backend/scripts/seed_dev.py` y en `DEV_USERS` de `frontend/src/views/LoginPage.vue`, sin introducir credenciales reales.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Modelo, migración, autorización, DTOs, servicio base y resolución de SLA que bloquean todas las historias.

**⚠️ CRITICAL**: Ninguna historia de usuario puede implementarse hasta completar esta fase.

- [X] T005 Crear `backend/app/models/configuration.py` con `ConfigurationVersion`, `SlaRule` y `ConfigurationAuditEntry` según `data-model.md`: `version` único y `> 0`; `hours > 0`; `valid_to_version IS NULL OR valid_to_version > valid_from_version`; `retired_at IS NULL OR valid_to_version IS NOT NULL`; unique `(category_id, priority_id, valid_from_version)`; unique parcial `(category_id, priority_id) WHERE valid_to_version IS NULL`; FKs, enums e índices `ix_sla_rules_category_priority`, `ix_sla_rules_current`, `ix_sla_rules_version`, `ix_sla_rules_created_at`, `ix_config_audit_occurred_at`, `ix_config_audit_entity`, `ix_config_audit_version` e `ix_config_audit_actor`.
- [X] T006 [P] Añadir `revision` a `backend/app/models/category.py` y `backend/app/models/priority.py` como `Integer`, no nulo, `default=1` y `server_default="1"`.
- [X] T007 [P] Añadir a `backend/app/models/ticket.py` las columnas anulables `sla_priority_level` (`SmallInteger`), `sla_hours_applied` (`Numeric(6,2)`) y `sla_config_version_id` (`Uuid` FK a `configuration_versions.id`), con `ck_tickets_sla_priority_level` (`IS NULL OR BETWEEN 1 AND 4`), `ck_tickets_sla_hours_positive` (`IS NULL OR > 0`) e índice `ix_tickets_sla_config_version`.
- [X] T008 Actualizar `backend/app/models/__init__.py` para exportar `ConfigurationVersion`, `SlaRule`, `ConfigurationAuditEntry`, `ConfigEntityType` y `ConfigAction`.
- [X] T009 Crear `backend/alembic/versions/0006_sla_configuration.py` con `down_revision = "0005_ticket_information"` y el `upgrade()`/`downgrade()` de `data-model.md` §9: crear tablas, insertar línea base `version = 1` con `created_by_id = NULL`, añadir `revision` y columnas de snapshot, rellenar `sla_priority_level` desde `priorities.level`, rellenar `sla_hours_applied` desde `sla_deadline - created_at`, crear índices únicos parciales (incluido `uq_priorities_level_active_non_system` sobre `level` con `WHERE is_active AND NOT is_system`) y abortar con mensaje claro si hay duplicados preexistentes de nombre, nivel activo o default.
- [X] T010 [P] Implementar `require_admin` en `backend/app/api/deps.py` para exigir `UserRole.admin`, devolver `403 forbidden` con «Esta configuración está disponible solo para administración.» y reutilizar `get_current_user`.
- [X] T011 [P] Crear `backend/app/schemas/configuration.py` con los DTOs de `data-model.md` §8 y sus validaciones: nombre de categoría 1–100, de prioridad 1–50; descripción ≤ 2.000; `keywords` ≤ 50 elementos de 1–50 sin duplicados normalizados; `sort_order` 0–9.999; `level` 1–4; color `#RRGGBB`; `base_hours` y `hours` positivos ≤ 9.999,99 con 2 decimales; lote no vacío y máximo 20 operaciones.
- [X] T012 Implementar en `backend/app/services/configuration.py` las primitivas de versión y auditoría: bloqueo de la versión vigente con `SELECT ... FOR UPDATE` (no-op en SQLite para pruebas), creación de una única fila `configuration_versions` por transacción, `append_audit` append-only y serialización segura de UUID, fechas ISO 8601 UTC y decimales como cadena.
- [X] T013 Añadir a `backend/app/services/configuration.py` los helpers de catálogo: normalización `lower(trim(name))`, unicidad de nombre, unicidad de nivel entre prioridades no-sistema activas, rechazo de `is_system` editable, reemplazo obligatorio del default, prohibición de desactivar la última entidad activa no-sistema, comprobación de tickets/reglas para borrado y cálculo de `ticket_count`, `rule_count` y `can_delete`.
- [X] T014 [P] Crear `backend/app/services/sla_resolution.py` con una función pura que, para una combinación y una versión, priorice la regla vigente sobre `priority.base_hours`, devuelva horas con precisión de minutos, fuente (`rule`/`base`), versión y nivel congelado, y lance `500 configuration_not_configured` si no hay horas aplicables.
- [X] T015 Actualizar `backend/tests/conftest.py` para insertar la fila base `version = 1` tras `Base.metadata.create_all`, añadir un fixture de usuario admin y cabeceras admin, y mantener los tickets del fixture `seeded` sin snapshot solo para el caso legado explícito; las pruebas de no retroactividad deben crear tickets con snapshot.
- [X] T016 [P] Crear `backend/app/api/v1/admin_configuration.py` con `APIRouter(prefix="/admin", tags=["Configuración administrativa"])` y la dependencia global `require_admin`; registrar el router en `backend/app/api/v1/router.py`.

**Checkpoint**: modelos, migración, autorización, DTOs y resolución de SLA listos; las historias pueden comenzar.

---

## Phase 3: User Story 1 - Gestionar el catálogo de categorías (Priority: P1) 🎯 MVP

**Goal**: El administrador crea, edita, desactiva, reactiva y elimina categorías, con auditoría y bloqueo optimista; los demás roles reciben 403.

**Independent Test**: Crear una categoría, editar su descripción, desactivarla y comprobar que desaparece de las opciones de nuevos tickets sin romper tickets existentes; repetir con usuario, técnico y supervisor para verificar 403.

### Tests for User Story 1

- [X] T017 [P] [US1] Escribir las pruebas de integración de categorías en `backend/tests/integration/test_admin_categories.py`: alta, edición, duplicado `lower(trim(name))`, revisión obsoleta, default, desactivación/reactivación, reemplazo de default, última activa, borrado con tickets/reglas, entidad de sistema, contadores e idempotencia de desactivar/eliminar repetidamente sin duplicar auditoría ni versiones.
- [X] T018 [P] [US1] Escribir las pruebas de autorización en `backend/tests/integration/test_admin_authorization.py`: `401` sin token, `403` para usuario/técnico/supervisor y `200`/`201` para admin en los endpoints de categorías.

### Implementation for User Story 1

- [X] T019 [US1] Implementar en `backend/app/services/configuration.py` las operaciones de categorías `list_categories`, `create_category`, `update_category` y `delete_category`, aplicando nombre obligatorio 1–100, descripción opcional ≤ 2.000, `keywords` ≤ 50 de 1–50 sin duplicados, `sort_order` 0–9.999, `409 system_catalog_item`, `default_replacement_required`, `last_active_catalog_item` y `catalog_in_use`, y registrando auditoría en la misma versión.
- [X] T020 [US1] Implementar en `backend/app/api/v1/admin_configuration.py` los endpoints `GET /categories`, `POST /categories`, `POST /categories/{category_id}/updates` y `POST /categories/{category_id}/deletion` con los DTOs de `backend/app/schemas/configuration.py` y los códigos de error estables.
- [X] T021 [P] [US1] Crear `frontend/src/services/adminConfiguration.ts` con `listCategories`, `createCategory`, `updateCategory` y `deleteCategory` usando `apiGet`/`apiPost` de `frontend/src/api/client.ts`, sin métodos PATCH/DELETE.
- [X] T022 [P] [US1] Crear `frontend/src/stores/adminConfiguration.ts` con el estado de categorías, `loading`, `saving`, `conflict`, mensajes y acciones de carga, alta, edición, desactivación y borrado; el store solo prepara la UX y no duplica reglas de negocio.
- [X] T023 [P] [US1] Crear `frontend/src/components/admin/CategoryTable.vue` con tabla responsive, columnas Nombre, Descripción, Estado, Tickets, Reglas y Acciones, insignias de activa/inactiva/sistema/default y botones deshabilitados con `title` explicativo.
- [X] T024 [P] [US1] Crear `frontend/src/components/admin/CategoryFormDialog.vue` con Headless UI `Dialog`, etiquetas asociadas, validación en cliente, envío de `expected_revision` y conflicto `409 stale_configuration` que mantiene el diálogo abierto con opción de recargar.
- [X] T025 [P] [US1] Crear `frontend/src/components/admin/ConflictBanner.vue` con `role="alert"`, mensaje de conflicto y acción «Recargar».
- [X] T026 [P] [US1] Crear `frontend/src/components/admin/AdminTabs.vue` con `role="tablist"`, `role="tab"`, `aria-selected`, `aria-controls` y navegación con flechas/Home/End.
- [X] T027 [US1] Crear `frontend/src/views/AdminConfigurationPage.vue` con cabecera, estados de carga/error, `role="status"` para éxitos y la pestaña Categorías montando `CategoryTable` y `CategoryFormDialog`.
- [X] T028 [US1] Añadir la ruta `/admin/configuracion` con nombre `admin-configuration` y `meta.requiresAdmin` en `frontend/src/router/index.ts`, implementar el guard por rol almacenado, actualizar `frontend/src/router/landing.ts` para que `landingForRole('admin')` devuelva `/admin/configuracion` y mantener el resto de roles.
- [X] T029 [P] [US1] Escribir `frontend/tests/components/CategoryFormDialog.spec.ts` para validación, envío, error de conflicto y recarga.
- [X] T030 [P] [US1] Escribir `frontend/tests/components/ConflictBanner.spec.ts` para `role="alert"`, mensaje y acción de recarga.

**Checkpoint**: US1 funcional y verificable de forma independiente; incluye el shell de la página administrativa que reutilizarán las demás historias.

---

## Phase 4: User Story 2 - Gestionar el catálogo de prioridades y su plazo base (Priority: P1)

**Goal**: El administrador mantiene prioridades con nivel 1–4, color, plazo base, default y desactivación segura; los tickets históricos no cambian.

**Independent Test**: Crear una prioridad con plazo base, editar el plazo, intentar duplicar el nivel, desactivarla y comprobar que los nuevos tickets ya no pueden seleccionarla mientras los históricos conservan su información.

### Tests for User Story 2

- [X] T031 [P] [US2] Escribir las pruebas de integración de prioridades en `backend/tests/integration/test_admin_priorities.py`: nivel único 1–4 entre prioridades no-sistema activas, creación tras liberar un nivel, conflicto al reactivar si el nivel fue reutilizado, color `#RRGGBB`, `base_hours` positivo ≤ 9.999,99, nombre único normalizado, default, última activa, desactivación/reactivación, sistema, borrado e idempotencia de comandos repetidos.

### Implementation for User Story 2

- [X] T032 [US2] Implementar en `backend/app/services/configuration.py` las operaciones `list_priorities`, `create_priority`, `update_priority` y `delete_priority`, con nombre 1–50, `level` 1–4 único entre prioridades no-sistema activas, `color` opcional `#RRGGBB`, `base_hours` positivo ≤ 9.999,99, reglas de default, última activa, sistema y borrado como las categorías, y auditoría explícita por entidad y versión.
- [X] T033 [US2] Implementar en `backend/app/api/v1/admin_configuration.py` los endpoints `GET /priorities`, `POST /priorities`, `POST /priorities/{priority_id}/updates` y `POST /priorities/{priority_id}/deletion`.
- [X] T034 [US2] Extender `frontend/src/services/adminConfiguration.ts` con `listPriorities`, `createPriority`, `updatePriority` y `deletePriority` usando `apiGet`/`apiPost`.
- [X] T035 [P] [US2] Crear `frontend/src/components/admin/PriorityTable.vue` con columnas Nombre, Nivel, Color, Plazo base, Estado, Tickets, Reglas y Acciones, mostrando el plazo base en horas.
- [X] T036 [P] [US2] Crear `frontend/src/components/admin/PriorityFormDialog.vue` con campos nivel, color, plazo base, default, `expected_revision` y manejo de `409 stale_configuration` y `default_replacement_required`.
- [X] T037 [US2] Extender `frontend/src/stores/adminConfiguration.ts` con el estado y las acciones de prioridades, reutilizando `loading`, `saving` y `conflict`.
- [X] T038 [US2] Añadir la pestaña Prioridades a `frontend/src/views/AdminConfigurationPage.vue`, montando `PriorityTable` y `PriorityFormDialog`.
- [X] T039 [P] [US2] Escribir `frontend/tests/components/PriorityFormDialog.spec.ts` para nivel, plazo base, color, default y conflicto.

**Checkpoint**: US1 y US2 funcionan de forma independiente; las prioridades aportan el plazo base para US3.

---

## Phase 5: User Story 3 - Configurar la matriz de plazos por categoría y prioridad (Priority: P1)

**Goal**: El administrador define, sustituye y retira reglas SLA por combinación; la regla prevalece sobre el plazo base y los lotes son atómicos.

**Independent Test**: Definir una regla para una categoría y prioridad, crear un ticket con esa combinación y comprobar que usa las horas de la regla; retirar la regla y comprobar que un ticket nuevo vuelve al plazo base sin alterar el anterior.

### Tests for User Story 3

- [X] T040 [P] [US3] Escribir las pruebas de integración de la matriz en `backend/tests/integration/test_admin_sla_matrix.py`: regla prevalece sobre base, fallback, nueva versión al cambiar horas, sustitución con `valid_to_version`/`supersedes_id`, retirada con `retired_at`/`retired_by_id`, duplicado vigente, categoría/prioridad inactiva, lote atómico, límite de 20 cambios, `expected_rule_id` e idempotencia de reintentar el mismo lote o la misma retirada sin duplicar efectos.
- [X] T041 [P] [US3] Escribir `backend/tests/unit/test_sla_resolution.py` para regla versus base, decimales, ausencia de horas aplicables, nivel congelado y prioridad con `base_hours = NULL`.

### Implementation for User Story 3

- [X] T042 [US3] Implementar en `backend/app/services/configuration.py` las operaciones `get_sla_matrix`, `apply_sla_batch` y `retire_sla_rule`: leer reglas vigentes y combinaciones activas, validar lote no vacío ≤ 20, sin combinaciones duplicadas, horas positivas, categoría/prioridad activas y `expected_rule_id` coherente; al sustituir o retirar, cerrar la regla anterior con `valid_to_version`, `supersedes_id`, `retired_at`/`retired_by_id` según corresponda; registrar auditoría por regla afectada y usar una única versión por lote con rollback completo.
- [X] T043 [US3] Implementar en `backend/app/api/v1/admin_configuration.py` los endpoints `GET /sla-rules`, `POST /sla-rules/batch` y `POST /sla-rules/{rule_id}/retirement`, devolviendo `SlaMatrixResponse`/`SlaBatchResponse` y los códigos `duplicate_sla_rule`, `inactive_catalog_item`, `stale_configuration` y `empty_batch`.
- [X] T044 [US3] Modificar `backend/app/services/ticket_creation.py` para bloquear la versión vigente con `FOR SHARE` (no-op en SQLite para pruebas), resolver el plazo con `backend/app/services/sla_resolution.py`, fijar `sla_priority_level = priority.level`, `sla_hours_applied`, `sla_deadline = created_at + hours`, `sla_config_version_id` y `sla_version = "v<version>"` en la misma transacción; si falta la versión base, devolver `500 configuration_not_initialized`. Extender `backend/app/schemas/ticket_creation.py` y el mapeo de `backend/app/api/v1/ticket_creation.py` para exponer en `TicketRead` los valores congelados y la versión aplicada.
- [X] T045 [US3] Extender `frontend/src/services/adminConfiguration.ts` con `getSlaMatrix`, `saveSlaBatch` y `retireSlaRule`.
- [X] T046 [P] [US3] Crear `frontend/src/components/admin/SlaCellEditor.vue` con horas, acciones Guardar/Retirar, validación y cierre accesible.
- [X] T047 [P] [US3] Crear `frontend/src/components/admin/SlaMatrix.vue` con categorías en filas, prioridades en columnas, celdas botón con `aria-label="Plazo para <categoría> y <prioridad>"`, borrador local, indicador de cambios sin guardar, descartar y guardado por lote.
- [X] T048 [US3] Extender `frontend/src/stores/adminConfiguration.ts` con el estado de matriz, borrador, `baseline`, `isDirty`, guardado por lote y conflicto `409 stale_configuration` sin aplicar cambios parciales.
- [X] T049 [US3] Añadir la pestaña Matriz SLA a `frontend/src/views/AdminConfigurationPage.vue`, montando `SlaMatrix` y el anuncio de la nueva versión con `role="status"`.
- [X] T050 [P] [US3] Escribir `frontend/tests/components/SlaMatrix.spec.ts` para renderizado, edición de celdas, borrador, guardado por lote y conflicto.

**Checkpoint**: US3 funcional; los tickets nuevos ya reciben el plazo de la regla o el plazo base con snapshot de versión.

---

## Phase 6: User Story 4 - Garantizar la no retroactividad de los plazos (Priority: P1)

**Goal**: Ningún cambio posterior de configuración altera el plazo, el límite, el nivel de urgencia ni la posición en cola de un ticket ya creado.

**Independent Test**: Crear un ticket, cambiar la regla y el nivel de la prioridad, y comprobar que el ticket conserva `sla_deadline`, `sla_hours_applied`, `sla_priority_level` y posición; después crear otro ticket y comprobar que usa la nueva versión.

### Tests for User Story 4

- [X] T051 [P] [US4] Escribir `backend/tests/integration/test_sla_non_retroactivity.py` usando tickets con snapshot (no los legados de T015) para ticket abierto y cerrado con límite/outcome inmutables, ticket nuevo con nueva versión visible en `TicketRead`, categoría/prioridad desactivada visible en el histórico, posición de cola estable al cambiar el nivel y contraste explícito con un ticket legado sin `sla_config_version_id`.
- [X] T052 [P] [US4] Escribir `backend/tests/integration/test_admin_concurrency.py` con PostgreSQL (`TEST_DATABASE_URL`) para `expected_revision`/`expected_rule_id` obsoletos, dos administradores sobre la misma regla, reintento idempotente de un lote ya aplicado y creación de ticket concurrente con cambio de versión, verificando `409 stale_configuration` y ausencia de escrituras parciales o duplicadas.

### Implementation for User Story 4

- [X] T053 [US4] Modificar `backend/app/services/work_queue.py` para usar `COALESCE(tickets.sla_priority_level, priorities.level)` en filtros, orden y `PriorityRef.level`, manteniendo el contrato y el cálculo de SLA existentes y la compatibilidad con tickets legados sin snapshot.

**Checkpoint**: US4 verificable; los tickets históricos no cambian y la cola usa el nivel congelado.

---

## Phase 7: User Story 5 - Consultar el histórico de cambios de configuración (Priority: P2)

**Goal**: El administrador consulta un histórico append-only con autor, fecha, entidad, acción, valores anteriores/nuevos y versión, con filtros y paginación.

**Independent Test**: Realizar altas, ediciones y retiradas; comprobar que el histórico muestra cada cambio con autor y valores, que los filtros y la paginación funcionan y que no existe endpoint de escritura.

### Tests for User Story 5

- [X] T054 [P] [US5] Escribir `backend/tests/integration/test_configuration_history.py` para entradas append-only, autor, valores previos/nuevos, filtros por fecha/entidad/acción/`configuration_version_id`, paginación, orden descendente e imposibilidad de escritura.

### Implementation for User Story 5

- [X] T055 [US5] Implementar en `backend/app/services/configuration.py` `list_config_history` con filtros por rango de fechas, `entity_type`, `entity_id`, `action` y `configuration_version_id`, paginación coherente, joins a versión y actor y orden descendente por `occurred_at`.
- [X] T056 [US5] Implementar en `backend/app/api/v1/admin_configuration.py` el endpoint `GET /config-history` con `ConfigHistoryResponse`, sin rutas de escritura.
- [X] T057 [US5] Extender `frontend/src/services/adminConfiguration.ts` con `getConfigHistory`.
- [X] T058 [P] [US5] Crear `frontend/src/components/admin/ConfigHistoryTable.vue` con filtros de fecha, entidad, acción y `configuration_version_id` (etiqueta «Versión»), tabla con Fecha, Autor, Entidad, Acción, Valores anteriores, Valores nuevos y Versión, formato `Intl.DateTimeFormat('es-ES', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'Europe/Madrid' })` y paginación.
- [X] T059 [US5] Extender `frontend/src/stores/adminConfiguration.ts` con el estado del histórico, filtros, paginación y carga.
- [X] T060 [US5] Añadir la pestaña Histórico a `frontend/src/views/AdminConfigurationPage.vue`, montando `ConfigHistoryTable`.
- [X] T061 [P] [US5] Escribir `frontend/tests/components/ConfigHistoryTable.spec.ts` para filtros, formato es-ES/Europe/Madrid y paginación.
- [X] T062 [P] [US5] Escribir `frontend/tests/stores/adminConfiguration.spec.ts` para estado del store, carga, guardado, borrador de matriz y conflicto.

**Checkpoint**: Las cinco historias funcionan de forma independiente; el histórico es de solo lectura.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Contrato, regresión, migración real, rendimiento, accesibilidad, seguridad y validación end-to-end.

- [X] T063 [P] Escribir `backend/tests/contract/test_admin_configuration_contract.py` para verificar campos, formas, códigos y rutas de `specs/008-configuracion-plazos-sla/contracts/admin-configuration.openapi.yaml`, incluyendo `403` para no-admin.
- [X] T064 Ejecutar `python -m pytest` en `backend/`, corregir fallos y confirmar que la suite pasa con SQLite.
- [X] T065 Ejecutar `npm run test` y `npm run build` en `frontend/`, corregir fallos de Vitest, TypeScript y `vue-tsc`.
- [X] T066 Ejecutar `alembic upgrade head` y `alembic downgrade -1` sobre `backend/alembic/versions/0006_sla_configuration.py` en PostgreSQL 16, verificar baseline, backfill, índices parciales y que `downgrade()` no toca datos históricos de tickets.
- [X] T067 Revisar accesibilidad en `frontend/src/views/AdminConfigurationPage.vue` y `frontend/src/components/admin/`: foco visible, etiquetas, `caption` en tablas, pestañas y diálogos con teclado.
- [X] T068 Revisar seguridad en `backend/app/api/v1/admin_configuration.py` y `backend/app/services/configuration.py`: 403 para no-admin, sin datos de configuración en respuestas no autorizadas, sin secretos ni cuerpos completos en logs.
- [X] T069 Ejecutar la validación de `specs/008-configuracion-plazos-sla/quickstart.md` contra el entorno local y corregir cualquier divergencia de comportamiento o contrato.
- [X] T070 [P] Escribir `backend/tests/integration/test_admin_configuration_performance.py` para medir p95 de `GET /admin/categories`, `GET /admin/sla-rules`, `GET /admin/config-history`, `POST /admin/sla-rules/batch` con 20 celdas y alta de ticket; ejecutarlo en PostgreSQL con `TEST_DATABASE_URL` y marcar el umbral de la constitución.
- [X] T071 [P] Escribir `frontend/tests/views/AdminConfigurationPage.spec.ts` con `axe-core` para la página administrativa y sus pestañas, verificando que no hay violaciones críticas de accesibilidad.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: sin dependencias; T002, T003 y T004 pueden ejecutarse en paralelo con T001.
- **Foundational (Phase 2)**: depende de Setup y bloquea todas las historias. T005 depende de T001; T006–T007 pueden ir en paralelo; T008 depende de T005–T007; T009 depende de T008; T010–T011 y T014 pueden ir en paralelo; T012 depende de T005; T013 depende de T012; T015 depende de T008; T016 depende de T010.
- **US1 (Phase 3)**: depende de Foundational.
- **US2 (Phase 4)**: depende de Foundational y de US1 para los archivos compartidos `admin_configuration.py`, `adminConfiguration.ts`, store y página.
- **US3 (Phase 5)**: depende de US1 y US2; consume categorías, prioridades, versiones y auditoría.
- **US4 (Phase 6)**: depende de US2 y US3 porque necesita cambios de regla, plazo base y snapshot de ticket.
- **US5 (Phase 7)**: depende de US1–US3 para que existan entradas de auditoría y de US1 para el shell de página.
- **Polish (Phase 8)**: depende de todas las historias deseadas.

### Critical Path

```text
T001 → T005 → T008 → T009 → T012 → T013 → T019 → T020
     → T032 → T033 → T042 → T043 → T044 → T053
     → T055 → T056 → T063 → T064 → T065 → T066 → T069 → T070
```

### User Story Dependencies

- **US1 (P1)**: primera historia; no depende de otras historias.
- **US2 (P1)**: comparte router, servicio, store y página con US1; implementar después de US1 o serializar los archivos compartidos.
- **US3 (P1)**: requiere categorías y prioridades existentes; depende de US1 y US2.
- **US4 (P1)**: requiere que US3 cree reglas y snapshots; depende de US3.
- **US5 (P2)**: requiere entradas de auditoría de US1–US3; puede implementarse después de US3.

### Within Each User Story

- Las pruebas se escriben primero y deben fallar antes de la implementación.
- Modelos/DTOs antes de servicios; servicios antes de endpoints; endpoints antes de la integración frontend.
- Las tareas de componentes en archivos distintos pueden ir en paralelo.
- Las tareas que modifican el mismo archivo (`configuration.py`, `admin_configuration.py`, `adminConfiguration.ts`, store y página) no pueden ejecutarse en paralelo.

### Parallel Opportunities

- Setup: T002, T003 y T004 en paralelo tras T001.
- Foundational: T006, T007, T010, T011, T014 y T016 en paralelo cuando sus dependencias estén resueltas.
- US1: T017/T018 en paralelo; T021–T026 en paralelo tras T020; T029/T030 en paralelo.
- US2: T031 y T035/T036/T039 en paralelo; T034–T036 tras T033.
- US3: T040/T041 en paralelo; T046/T047 en paralelo; T050 en paralelo con T049.
- US4: T051/T052 en paralelo; T053 después de T044.
- US5: T054, T058, T061 y T062 en paralelo; T057–T060 tras T056.
- Polish: T063, T067, T068, T070 y T071 en paralelo; T064–T066 y T069 dependen de la implementación completa.

---

## Parallel Example: User Story 1

```bash
# Pruebas de US1 en paralelo
Task: "T017 Escribir test_admin_categories.py"
Task: "T018 Escribir test_admin_authorization.py"

# Componentes de US1 en paralelo tras T020
Task: "T021 Crear servicio frontend de categorías"
Task: "T022 Crear store de categorías"
Task: "T023 Crear CategoryTable.vue"
Task: "T024 Crear CategoryFormDialog.vue"
Task: "T025 Crear ConflictBanner.vue"
Task: "T026 Crear AdminTabs.vue"
```

## Parallel Example: User Story 2

```bash
Task: "T031 Escribir test_admin_priorities.py"
Task: "T035 Crear PriorityTable.vue"
Task: "T036 Crear PriorityFormDialog.vue"
Task: "T039 Escribir PriorityFormDialog.spec.ts"
```

## Parallel Example: User Story 3

```bash
Task: "T040 Escribir test_admin_sla_matrix.py"
Task: "T041 Escribir test_sla_resolution.py"
Task: "T046 Crear SlaCellEditor.vue"
Task: "T047 Crear SlaMatrix.vue"
Task: "T050 Escribir SlaMatrix.spec.ts"
```

## Parallel Example: User Story 4

```bash
Task: "T051 Escribir test_sla_non_retroactivity.py"
Task: "T052 Escribir test_admin_concurrency.py"
```

## Parallel Example: User Story 5

```bash
Task: "T054 Escribir test_configuration_history.py"
Task: "T058 Crear ConfigHistoryTable.vue"
Task: "T061 Escribir ConfigHistoryTable.spec.ts"
Task: "T062 Escribir adminConfiguration.spec.ts"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Completar Setup y Foundational.
2. Implementar US1 (categorías) con pruebas, endpoints y UI administrativa.
3. **STOP and VALIDATE**: ejecutar `test_admin_categories.py`, `test_admin_authorization.py`, `CategoryFormDialog.spec.ts` y `ConflictBanner.spec.ts`.
4. Desplegar/demostrar la gestión de categorías como primera rebanada vertical.

### Incremental Delivery

1. Setup + Foundational → base técnica lista.
2. US1 → catálogo de categorías y shell administrativo.
3. US2 → prioridades y plazo base.
4. US3 → matriz SLA, versión y snapshot de ticket.
5. US4 → no retroactividad y cola con urgencia congelada.
6. US5 → histórico consultable.
7. Polish → contrato, migración real, accesibilidad, seguridad y quickstart.

El MVP funcional de HU-08 requiere US1–US4 porque la matriz y la no retroactividad son P1; US1 sola es la primera rebanada desplegable, no el alcance completo de la historia.

### Parallel Team Strategy

1. Un equipo completa Setup + Foundational.
2. Después, un desarrollador puede tomar US1 y otro US2, pero deben coordinar los archivos compartidos `backend/app/api/v1/admin_configuration.py`, `backend/app/services/configuration.py`, `frontend/src/services/adminConfiguration.ts`, `frontend/src/stores/adminConfiguration.ts` y `AdminConfigurationPage.vue`.
3. US3 y US4 se abordan después de US2; US5 puede empezar cuando US1–US3 estén estables.
4. Las tareas de pruebas y componentes con archivos propios pueden repartirse en paralelo.

---

## Notes

- `[P]` indica archivos distintos y ausencia de dependencias de tareas incompletas.
- `[US1]`–`[US5]` permiten trazar cada tarea a su historia y validar la cobertura.
- No hay tareas de inicialización de proyecto: el repositorio ya existe con FastAPI, Vue 3, Vitest, pytest y Alembic.
- No se añaden dependencias nuevas; reutilizar `apiGet`/`apiPost`, Headless UI, Heroicons, Tailwind y los patrones de `WorkQueuePage`.
- Los decimales viajan como cadena y las fechas como ISO 8601 UTC; la UI muestra `Europe/Madrid`.
- Evitar tareas vagas y conflictos de edición simultánea sobre los archivos compartidos.

---

## Phase 9: Convergence

- [X] T072 CRITICAL: completar `backend/tests/integration/test_admin_concurrency.py` con creación de ticket concurrente frente a un cambio de versión, `expected_rule_id` obsoleto, una segunda identidad de administrador y verificación de ausencia de reglas, versiones y auditorías duplicadas per Constitution IV / T052 / plan §3.3 (partial)
- [X] T073 CRITICAL: ejecutar y registrar `alembic upgrade head` y `alembic downgrade -1` sobre `backend/alembic/versions/0006_sla_configuration.py` en PostgreSQL 16, verificando baseline, backfill, índices parciales y que el downgrade no altera datos históricos de tickets per Constitution II / T066 (missing)
- [X] T074 Ampliar `backend/tests/integration/test_sla_non_retroactivity.py` con ticket cerrado, invariancia de `SlaOutcome`, orden de cola antes/después, visibilidad de categoría/prioridad desactivada en detalle e histórico y contraste con un ticket legado `v1` per US4/AC1 / US4/AC4 / US4/AC5 / US4/AC6 / US4/AC7 / SC-001 / SC-008 / SC-009 / T051 (partial)
- [X] T075 Envolver `_apply_batch` en `try/except Exception: db.rollback(); raise` en `backend/app/services/configuration.py` para garantizar atomicidad explícita sin depender del cierre de sesión per FR-024 / US3/AC7 / plan §3.1 (partial)
- [X] T076 Capturar `previous_values` de la regla sustituida en las entradas de auditoría `rule_upsert` de `backend/app/services/configuration.py` per FR-022 / US5/AC1 / plan §5 (partial)
- [X] T077 Adquirir el bloqueo `SELECT ... FOR UPDATE` de la versión vigente antes de validar y escribir en `create_*`, `update_*` y `delete_*`, respetando el orden obligatorio de la transacción per plan R7 / plan §3.1 / FR-025 (contradicts)
- [X] T078 Añadir índices únicos funcionales sobre `lower(trim(name))` de categorías y prioridades en los modelos y en `0006_sla_configuration.py` para impedir duplicados por concurrencia per FR-004 / plan R6 / data-model §7.1-7.2 (partial)
- [X] T079 Corregir `backend/tests/integration/test_admin_configuration_performance.py` para medir el incremento <10 ms del alta de ticket frente a una línea base, medir el histórico con 25 elementos y aplicar los umbrales del plan per T070 / plan §9.3 (contradicts)
- [X] T080 Añadir pruebas de idempotencia de comandos repetidos —desactivar/eliminar categorías y prioridades, retirar y reintentar un lote— verificando que no duplican auditoría ni versiones per T017 / T031 / T040 / plan §9.1 (missing)
- [X] T081 Completar casos de aceptación de catálogos y matriz: borrado de categoría referenciada por ticket, nombre duplicado normalizado en prioridades y rechazo por API de horas de regla no positivas per US1/AC4 / FR-004 / US3/AC6 / T017 / T031 / T040 (partial)
- [X] T082 Reflejar en `frontend/src/stores/adminConfiguration.ts` el borrador de matriz, `baseline`, `isDirty`, la versión vigente y los mensajes, reconciliando la divergencia con el contrato de componentes per T048 / plan §6.6 (partial)
- [X] T083 Ejecutar y registrar la validación de `specs/008-configuracion-plazos-sla/quickstart.md` contra el entorno local y corregir cualquier divergencia de comportamiento o contrato per T069 / plan §9.3 (missing)
- [X] T084 Deshabilitar y estilizar las celdas inactivas en `frontend/src/components/admin/SlaMatrix.vue` añadiendo `is_active` a los tipos, y pedir confirmación al salir con cambios sin guardar per plan §6.4 / FR-021 / contracts/frontend-components.md (partial)
- [X] T085 Validar `from <= to` en `config_history` y resolver los joins a versión y actor con `joinedload` para evitar N+1 per plan §5 / T055 (partial)
- [X] T086 Añadir los checks `ck_tickets_sla_priority_level` y `ck_tickets_sla_hours_positive` a `backend/app/models/ticket.py` para igualar el esquema migrado en las bases SQLite de prueba per T007 / plan §1.2 (partial)
- [X] T087 Cambiar el `aria-label` de las celdas en `frontend/src/components/admin/SlaMatrix.vue` a «Plazo para <categoría> y <prioridad>» y actualizar `frontend/tests/components/SlaMatrix.spec.ts` per plan §6.4 / contracts/frontend-components.md (contradicts)
- [X] T088 Ampliar `backend/tests/contract/test_admin_configuration_contract.py` para verificar enums, patrones, formatos y códigos de error estables del OpenAPI per T063 / plan §9.1 (partial)
- [X] T089 Alinear `backend/alembic/versions/0006_sla_configuration.py` con `data-model.md`: crear los enums con `create_type=False` y ampliar el backfill de `sla_priority_level` a todos los tickets existentes per data-model §6.4 / data-model §9.2 (partial)
- [X] T090 Añadir `min_length=1` a `changes` en `SlaBatchRequest` para rechazar lotes vacíos también en la capa de esquema per T011 / US3/AC7 (partial)
- [X] T091 Alinear paleta y cabecera con el plan: tarjeta de error `border-red-200 bg-red-50`, título «Configuración», botón primario `bg-sky-600` e insignias emerald/amber/sky en `AdminConfigurationPage.vue` y las tablas per plan §6.2 / plan §6.3 (contradicts)

---

## Phase 10: Convergence

- [X] T092 CRITICAL: crear explícitamente los enums `config_entity_type` y `config_action` en `upgrade()` de `backend/alembic/versions/0006_sla_configuration.py` con `postgresql.ENUM(...).create(bind, checkfirst=True)` antes de `op.create_table("configuration_audit_entries", ...)`, manteniendo `create_type=False` en las columnas y el `drop()` existente en `downgrade()`, para que `alembic upgrade head` no falle en PostgreSQL 16 con `UndefinedObject` per data-model §9.2 / Constitution II / T089 (contradicts)
- [X] T093 CRITICAL: ejecutar y registrar en PostgreSQL 16 `alembic downgrade base && alembic upgrade head`, `alembic downgrade -1` y `alembic upgrade head`, verificando baseline `version = 1`, backfill completo de `sla_priority_level`, índices parciales, creación/desaparición de enums y que los tickets históricos no se alteran per Constitution II / T066 / T073 / plan §9.3 (missing)
- [X] T094 CRITICAL: ejecutar `backend/tests/integration/test_admin_concurrency.py` con `TEST_DATABASE_URL` real y registrar resultados de `expected_revision`/`expected_rule_id` obsoletos, dos administradores, reintento idempotente y creación de ticket concurrente, confirmando `409 stale_configuration` y ausencia de escrituras duplicadas per FR-025 / SC-010 / Constitution IV / T052 / T072 / plan §3.3 (missing)
- [X] T095 CRITICAL: ejecutar `backend/tests/integration/test_admin_configuration_performance.py` con `TEST_DATABASE_URL` real y registrar p95 de catálogos, matriz, histórico, lote y alta de ticket, además del `EXPLAIN ANALYZE` del histórico, verificando los umbrales del plan per Constitution IV / T070 / T079 / plan §9.3 (missing)
- [X] T096 HIGH: ejecutar y registrar la validación completa de `specs/008-configuracion-plazos-sla/quickstart.md` contra el entorno local, corrigiendo cualquier divergencia de comportamiento o contrato detectada per T069 / T083 / plan §9.3 (missing)

---

## Phase 11: Convergence

- [X] T097 CRITICAL: optimizar `backend/app/services/ticket_creation.py` (`_resolve_sla_snapshot`) y/o `backend/tests/integration/test_admin_configuration_performance.py` para que el incremento p95 del alta de ticket sea < 10 ms con `TEST_DATABASE_URL` real, manteniendo la coherencia versión/regla, y ejecutar y registrar además el `EXPLAIN ANALYZE` del histórico; la medición intercalada actual registró 11.88 ms y falla `assert ticket_overhead_ms < TICKET_THRESHOLD_MS` en `backend/tests/integration/test_admin_configuration_performance.py:226` per Constitution IV / plan §9.3 / T070 / T079 / T095 (contradicts)
- [X] T098 CRITICAL: completar y registrar la verificación PostgreSQL 16 de T093 ejecutando también `alembic downgrade base && alembic upgrade head`, además del ciclo `downgrade -1`/`upgrade head` ya probado, y marcar T066/T073/T093 en `tasks.md` per Constitution II / T066 / T073 / plan §9.3 (partial)
- [X] T099 CRITICAL: registrar el resultado de `TEST_DATABASE_URL='postgresql+psycopg://ticketing:ticketing@localhost:5432/ticketing_test' python3 -m pytest tests/integration/test_admin_concurrency.py -q` (`5 passed`) y marcar T052/T072/T094 en `tasks.md`, conservando la corrección de coherencia versión/regla per FR-025 / SC-010 / Constitution IV / T052 / T072 / plan §3.3 (partial)
- [X] T100 HIGH: ejecutar y registrar la validación completa de `specs/008-configuracion-plazos-sla/quickstart.md` contra el entorno local, corrigiendo cualquier divergencia de comportamiento o contrato detectada y marcando T069/T083/T096 per T069 / T083 / plan §9.3 (missing)

---

## Phase 12: Convergence

- [X] T101 CRITICAL: reconciliar el lock advisory global introducido en `backend/app/services/configuration.py` (`CONFIGURATION_LOCK_KEY`, `acquire_configuration_lock`) y en `backend/app/services/ticket_creation.py` (`_resolve_sla_snapshot`) con `research.md R7` y `plan §3.1`, que exigen `FOR UPDATE`/`FOR SHARE` y descartan explícitamente un lock global; sustituirlo por una alternativa conforme o documentar y justificar la decisión revisada en `research.md`/`plan.md`, conservando concurrencia `5 passed` e incremento p95 < 10 ms per research.md R7 / Constitution V (contradicts)

---

## Phase 13: Convergence

- [X] T102 HIGH: alinear `backend/scripts/seed_dev.py` con `specs/008-configuracion-plazos-sla/quickstart.md` §2 y §5.5: dejar solo la versión base `v1`, sin `configuration-version-2`, reglas creadas por el seed ni `sla_config_version_id=v1` en tickets legacy, para que la verificación inicial y el alta de `Red × Alta` con `expected_rule_id: null` devuelvan el resultado esperado per quickstart §2 / quickstart §5.5 (contradicts)
- [X] T103 HIGH: corregir `previous_values` de las entradas `rule_upsert` en `_apply_batch_impl` de `backend/app/services/configuration.py`, usando `previous_rules[rule.supersedes_id]` en lugar de `previous_rules.get(rule.id)`, y añadir una aserción en `backend/tests/integration/test_admin_sla_matrix.py` per FR-022 / US5/AC1 / plan §5 / T076 (partial)
- [X] T104 MEDIUM: emitir una entrada de auditoría para la categoría o prioridad default demovida por `_set_default` en `backend/app/services/configuration.py`, con revision, valores previos/nuevos y la misma versión de configuración que la entidad destino per FR-022 / SC-005 / plan §5 (partial)
- [X] T105 MEDIUM: alinear `backend/app/services/sla_resolution.py` con `plan §2.1`: exponer `ResolvedSla` con `source: Literal["rule", "priority_base"]`, `rule_id`, `config_version_id` y la firma con entidades, actualizando `_resolve_sla_snapshot` y `tests/unit/test_sla_resolution.py` per plan §2.1 / Constitution V (partial)
- [X] T106 MEDIUM: mostrar los plazos con dos decimales es-ES en `frontend/src/components/admin/PriorityTable.vue` y `frontend/src/components/admin/SlaMatrix.vue`, conservando la precisión de minutos de valores como `7.25` o `8.05`, y ampliar las pruebas per spec Casos límite / plan §6.4 / contracts/frontend-components.md §8 (partial)
- [X] T107 MEDIUM: añadir `:aria-invalid` a los controles validados en `CategoryFormDialog.vue`, `PriorityFormDialog.vue` y `SlaCellEditor.vue`, reflejando `localError` y los errores del backend per plan R12 (partial)
- [X] T108 MEDIUM: asociar una etiqueta accesible al campo texto del color en `frontend/src/components/admin/PriorityFormDialog.vue` mediante `id`/`label` o `aria-label`, y cubrirlo en pruebas per plan §6.3 / T024 (partial)

---

## Phase 14: Convergence

- [X] T109 HIGH: corregir la auditoría `rule_retire` en `_apply_batch_impl` de `backend/app/services/configuration.py`, reutilizando el snapshot previo capturado antes de mutar `valid_to_version`/`retired_at`/`retired_by_id` como `previous_values`, emitiendo `new_values` con el cierre, y añadiendo aserciones en `backend/tests/integration/test_admin_sla_matrix.py` o `test_configuration_history.py` per FR-022 / US5/AC1 / SC-005 / plan §5 / Constitution V (partial)
- [X] T110 HIGH: hacer que `frontend/src/components/admin/SlaMatrix.vue` renderice también las reglas vigentes cuyas combinaciones están inactivas, exponiendo una acción «Retirar regla» que llame a `retireSlaRule(rule.id, rule.id)` desde `frontend/src/views/AdminConfigurationPage.vue`/`frontend/src/stores/adminConfiguration.ts`, recargue la matriz y anuncie la nueva versión, sin incluir combinaciones inactivas en la cuadrícula activa per FR-020 / US3/AC4 / plan §4.4 / T043 / T045 (missing)
- [X] T111 HIGH: añadir `sla_deadline: datetime | None` a `TicketRead` en `backend/app/schemas/ticket_creation.py`, poblarlo en `backend/app/api/v1/ticket_creation.py` y verificar en `backend/tests/integration/test_sla_non_retroactivity.py` que el límite congelado es observable e inmutable, reconciliando la lista de campos de `plan.md` §7.1 con FR-017 / US4/AC3 / T044 (missing)
- [X] T112 MEDIUM: añadir una prueba en `backend/tests/integration/test_sla_non_retroactivity.py` que cree tickets abiertos y cerrados sin regla de matriz, actualice `priority.base_hours` con `expected_revision`, verifique que sus `sla_hours_applied`, `sla_deadline`, `sla_version` y resultado SLA no cambian, y que un ticket nuevo usa el nuevo plazo base y la nueva versión per US2/AC2 / caso límite `spec.md:137` / T051 / Constitution IV (missing)
- [X] T113 MEDIUM: añadir al suite `backend/tests/integration/test_admin_configuration_performance.py` una captura PostgreSQL-only de `EXPLAIN (ANALYZE, BUFFERS)` para la consulta exacta de `list_config_history` con `page_size=25`, verificando el uso del índice de `occurred_at` y registrando el plan en los resultados per T095 / T097 / plan §9.3 (missing)
- [X] T114 MEDIUM: auditar también la entidad promovida a default en `_set_default` de `backend/app/services/configuration.py`, capturando su snapshot previo, incrementando su `revision` y emitiendo una entrada `set_default`/`update` en la misma versión, con una prueba que verifique `previous_values.is_default=false` y `new_values.is_default=true` per FR-022 / SC-005 / T104 / plan §5 (missing)
- [X] T115 LOW: añadir un caso en `frontend/tests/components/LoginPage.spec.ts` que seleccione `admin@example.com`, compruebe la opción de administrador y verifique `router.replace('/admin/configuracion')`, además de `landingForRole('admin')` y el guard `requiresAdmin` per plan §6.1 / T004 / T028 / Constitution IV (missing)
- [X] T116 LOW: corregir el mensaje final de `backend/scripts/seed_dev.py` para que describa únicamente la versión base `v1`, cero reglas SLA, sin histórico de configuración y tickets legacy sin `sla_config_version_id`, añadiendo una verificación que evite la regresión del texto per T102 (contradicts)
- [X] T117 LOW: ampliar `backend/tests/integration/test_admin_sla_matrix.py` para volver a leer el primer ticket tras la retirada de la regla y reafirmar sus `sla_hours_applied`, `sla_deadline`, `sla_config_version_id` y resultado SLA, además de la comprobación existente del ticket nuevo per US3/AC4 / caso límite `spec.md:139` / T040 / Constitution IV (partial)

---

## Phase 15: Convergence

- [X] T118 CRITICAL: reordenar `create_ticket` en `backend/app/services/ticket_creation.py` para adquirir el `FOR SHARE` de la versión vigente antes de `suggest()`/`_resolve_priority()` —o releer categoría y prioridad dentro del mismo snapshot bloqueado— de modo que regla, prioridad y versión pertenezcan a una sola versión coherente, conservando la lectura única de versión/regla y añadiendo una prueba PostgreSQL de cambio concurrente de prioridad per research.md R7 / data-model §7 / plan §3.3 / FR-017 / FR-018 / SC-003 / Constitution IV (contradicts)
- [X] T119 MEDIUM: corregir las altas de categoría y prioridad en `backend/app/services/configuration.py` (`create_category`, `create_priority`) para que la auditoría `ConfigAction.create` conserve `previous_values = NULL`, manteniendo la promoción a default en una entrada `set_default` separada con `previous_values.is_default=false` y `new_values.is_default=true`, y añadir aserciones en `backend/tests/integration/test_admin_categories.py` y `test_admin_priorities.py` per FR-022 / SC-005 / data-model §5.1 / T114 (contradicts)
- [X] T120 MEDIUM: propagar el código `inactive_catalog_item` de `saveSlaBatch`/`retireSlaRule` desde `frontend/src/stores/adminConfiguration.ts` y `frontend/src/views/AdminConfigurationPage.vue` hasta `frontend/src/components/admin/SlaMatrix.vue`, poblando `cellError` por combinación, marcando la celda con borde `rose-400` y mensaje, y conservando el borrador per FR-027 / plan §4.4 / contracts/frontend-components.md §8 / T045 (partial)
- [X] T121 MEDIUM: mostrar los errores de campo del backend bajo el control correspondiente en `frontend/src/components/admin/CategoryFormDialog.vue` (`duplicate_catalog_name`) y `frontend/src/components/admin/PriorityFormDialog.vue` (`duplicate_catalog_name`/`duplicate_priority_level`), con `id`, `role="alert"` y `aria-describedby`, limpiándolos al reabrir y ampliando las pruebas per quickstart §6 filas 4 y 9 / contracts/frontend-components.md §§5-6 y 13 / T107 (partial)
- [X] T122 LOW: renderizar el punto de color de la prioridad en las celdas con regla de `frontend/src/components/admin/SlaMatrix.vue` usando `priority.color`, con una aserción en `frontend/tests/components/SlaMatrix.spec.ts` per contracts/frontend-components.md §8 / plan §6.4 (partial)
- [X] T123 LOW: alinear los nombres públicos con `data-model.md` §8 y T011/T055: definir o re-exportar explícitamente los DTOs en `backend/app/schemas/configuration.py` y exponer y usar `list_config_history` en `backend/app/services/configuration.py` y `backend/app/api/v1/admin_configuration.py`, actualizando pruebas si procede (partial)
- [X] T124 LOW: evitar que las cargas `GET` de administración hereden el fallback `No se pudo cargar la cola de trabajo.` de `apiGet` en `frontend/src/api/client.ts`, pasando un mensaje neutro desde `frontend/src/services/adminConfiguration.ts` o envolviendo el error en el store, y cubriéndolo con una prueba per FR-027 / contracts/frontend-components.md §13 / Constitution IV (partial)

---

## Phase 16: Convergence

- [X] T125 HIGH: corregir `backend/tests/integration/test_admin_configuration_performance.py` para contar las entradas `set_default` añadidas por T119 en `_catalog` (27 auditorías, no 25), volver a ejecutar la suite con `TEST_DATABASE_URL` PostgreSQL y verificar p95 de lecturas/lote/alta (<300/<400/<10 ms) y el `EXPLAIN ANALYZE` del histórico per plan §9.3 / Constitution IV / T070 / T079 / T095 / T097 (contradicts)
- [X] T126 MEDIUM: normalizar a UTC los parámetros `from`/`to` de `GET /admin/config-history` antes de compararlos y filtrar, de modo que extremos naive y aware no produzcan `TypeError`/500, y añadir una prueba con formatos mixtos per plan §5 / FR-027 / US5/AC3 / T085 (partial)
- [X] T127 MEDIUM: renderizar la fila de esqueleto `animate-pulse` en `frontend/src/components/admin/PriorityTable.vue` cuando `loading` sea verdadero, siguiendo el patrón de `CategoryTable.vue`, y cubrirlo en `PriorityTable.spec.ts` per contracts/frontend-components.md §6 / plan §6.2 (partial)
- [X] T128 MEDIUM: añadir una prueba ejecutable de la navegación por teclado de `frontend/src/components/admin/AdminTabs.vue` con `ArrowRight`, `ArrowLeft`, `Home` y `End`, verificando foco y `aria-selected` per plan §6.2 / plan §9.3 / T026 / T067 / Constitution IV (partial)
- [X] T129 MEDIUM: actualizar `specs/008-configuracion-plazos-sla/contracts/frontend-components.md` §§1 y 8 para documentar `is_active?` en las refs, la prop `cellErrors`, el evento `retire` y el panel de reglas inactivas, reconciliando tipos, DTOs y pruebas para que el estado inactivo sea observable en respuestas reales per FR-021 / FR-027 / T084 / T110 / T120 / plan §6.4 (partial)
- [X] T130 LOW: alinear los conjuntos `required` de `admin-configuration.openapi.yaml` con los DTOs Python y los tipos TypeScript para `SlaRuleAdmin.created_by`, `DeleteResponse.configuration_version`, `ConfigHistoryEntry.previous_values` y `new_values`, reforzando `test_admin_configuration_contract.py` con comparación de igualdad per data-model §8 / T063 / T088 (partial)
- [X] T131 LOW: documentar en `specs/008-configuracion-plazos-sla/contracts/admin-configuration.openapi.yaml` el catálogo completo de códigos estables de configuración y ampliar la prueba de contrato para verificarlo contra `CONFIGURATION_ERROR_MESSAGES` per FR-027 / T002 / T088 (partial)
- [X] T132 LOW: actualizar `SEED_SUMMARY_LINES` en `backend/scripts/seed_dev.py` para informar de la creación del usuario administrador y añadir una verificación que evite la regresión del mensaje per quickstart §2 / T004 / T116 (contradicts)

---

## Phase 17: Convergence

- [X] T133 MEDIUM: sustituir los cuatro códigos `validation_error` de `backend/app/services/configuration.py` (l. 66, 645, 899 y 1287) por códigos estables incluidos en `CONFIGURATION_ERROR_MESSAGES` y en el enum `ApiError.code` de `specs/008-configuracion-plazos-sla/contracts/admin-configuration.openapi.yaml`, actualizando las pruebas que los esperan per FR-027 / plan §8 / T131 (contradicts)
- [X] T134 MEDIUM: ampliar `backend/tests/integration/test_admin_authorization.py` y `backend/tests/contract/test_admin_configuration_contract.py` para verificar `401`/`403` y la ausencia de datos de configuración en todas las rutas `/api/v1/admin/**` y para cada rol no administrador per FR-001 / FR-002 / plan §9.1 / T018 / Constitution III (partial)
- [X] T135 MEDIUM: añadir en `backend/tests/integration/test_admin_sla_matrix.py` una prueba que cree una regla, desactive su categoría o prioridad, verifique que la regla sigue presente en `GET /admin/sla-rules` y pueda retirarse per FR-020 / plan §4.4 / T110 (missing)
- [X] T136 LOW: envolver `create_category`, `update_category`, `delete_category`, `create_priority`, `update_priority` y `delete_priority` en `backend/app/services/configuration.py` con `try/except Exception: db.rollback(); raise`, igual que `_apply_batch`, para garantizar atomicidad explícita per FR-024 / plan §3.1 / T075 (partial)
- [X] T137 LOW: crear la línea base `v1` en `seed_configuration()` de `backend/scripts/seed_dev.py` con `created_by_id=None`, igual que la migración `0006`, y ajustar la verificación del resumen per data-model §3.1 / data-model §8.1 / T102 (contradicts)
- [X] T138 LOW: derivar `redirectTarget` en `frontend/src/views/LoginPage.vue` desde `landingForRole` del usuario seleccionado para que el texto anuncie `/admin/configuracion` al administrador sin `?redirect` per plan §6.1 / T115 (contradicts)
- [X] T139 LOW: añadir en `frontend/tests/components/PriorityFormDialog.spec.ts` el caso que marca una prioridad como predeterminada, la desactiva y exige/selecciona `replacement_default_id`, verificando el payload enviado per T039 / plan §9.2 (missing)
- [X] T140 LOW: añadir casos de montaje en `frontend/tests/views/AdminConfigurationPage.spec.ts` para los estados de carga, error, conflicto y «Solo administración», comprobando esqueletos, `role="alert"` y textos per T027 / T071 / plan §9.2 (missing)
- [X] T141 LOW: cubrir los filtros `to` y `action` en `frontend/tests/components/ConfigHistoryTable.spec.ts`, verificando los eventos emitidos per T061 / plan §6.5 (partial)

---

## Phase 18: Convergence

- [X] T142 MEDIUM: cargar el histórico al montar `frontend/src/views/AdminConfigurationPage.vue` cuando `activeTab` se inicializa desde `?tab=history`, invocando `store.loadHistory(store.historyFilters)` en `onMounted` o con un watcher `immediate`, y cubrir el enlace directo en `frontend/tests/views/AdminConfigurationPage.spec.ts` per contracts/frontend-components.md §2 / plan §6.5 / US5/AC4 (missing)
- [X] T143 MEDIUM: documentar `is_active?` en `CategoryRef` y `PriorityRef` de `specs/008-configuracion-plazos-sla/contracts/frontend-components.md` §§1 y 8, reconciliando `frontend/src/types/adminConfiguration.ts`, los DTOs y las pruebas para que el estado inactivo sea observable en respuestas reales per tasks.md T129 / FR-021 / FR-027 / plan §6.4 (partial)
- [X] T144 MEDIUM: conservar el banner de conflicto hasta que la recarga termine con éxito modificando `reloadAll()` en `frontend/src/stores/adminConfiguration.ts` para no limpiar `conflict` antes de `loadAll()` o para restaurarlo si falla, con prueba en `frontend/tests/stores/adminConfiguration.spec.ts` per contracts/frontend-components.md §11 / FR-025 / plan §3.2 (contradicts)
- [X] T145 LOW: renderizar las palabras clave introducidas como chips junto al input separado por comas en `frontend/src/components/admin/CategoryFormDialog.vue`, con cobertura en `frontend/tests/components/CategoryFormDialog.spec.ts` per contracts/frontend-components.md §5 / plan §6.3 (partial)

---

## Phase 19: Convergence

- [X] T146 MEDIUM: derivar `inactiveRules` en `frontend/src/components/admin/SlaMatrix.vue` de `rule.category.is_active === false || rule.priority.is_active === false` con fallback por ausencia en `combinations`, y añadir en `frontend/tests/components/SlaMatrix.spec.ts` un caso con refs inactivas presentes en `combinations` y regla vigente que verifique el panel «Reglas de combinaciones inactivas» y el evento `retire` per FR-020 / US3/AC4 / plan §6.4 / contracts/frontend-components.md §8 / T110 (partial)
- [X] T147 LOW: alinear los conjuntos `required` de `CategoryAdmin` y `PriorityAdmin` entre `specs/008-configuracion-plazos-sla/contracts/admin-configuration.openapi.yaml`, `backend/app/schemas/admin_configuration.py` y `frontend/src/types/adminConfiguration.ts`, ampliando `backend/tests/contract/test_admin_configuration_contract.py` con comparación de igualdad también para esos esquemas per T130 / data-model §8 / Constitution IV (partial)
- [X] T148 LOW: añadir `"is_active": true` a los ejemplos de `SlaRuleAdmin` y `SlaMatrixResponse` en `specs/008-configuracion-plazos-sla/data-model.md` §§8.7-8.8 para reflejar las refs reales per T143 / FR-021 / FR-027 (partial)
- [X] T149 LOW: corregir `frontend-components.md` §10 para describir el filtro «Versión» como ID UUID de configuración (`configuration_version_id`, texto) en lugar de `number`, reconciliando §1, `frontend/src/types/adminConfiguration.ts` y `ConfigHistoryTable.vue` per T058 / plan §6.5 (contradicts)
- [X] T150 LOW: actualizar los ejemplos de plazos en `frontend-components.md` §§6 y 8 a dos decimales es-ES (`8,00 h`, `8,50 h`, `6,00 h`, `Base: 8,00 h`) para igualar el formato implementado y probado per T106 / plan §6.4 (contradicts)
