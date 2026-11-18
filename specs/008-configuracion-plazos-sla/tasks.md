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
- [ ] T052 [P] [US4] Escribir `backend/tests/integration/test_admin_concurrency.py` con PostgreSQL (`TEST_DATABASE_URL`) para `expected_revision`/`expected_rule_id` obsoletos, dos administradores sobre la misma regla, reintento idempotente de un lote ya aplicado y creación de ticket concurrente con cambio de versión, verificando `409 stale_configuration` y ausencia de escrituras parciales o duplicadas.

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
- [ ] T066 Ejecutar `alembic upgrade head` y `alembic downgrade -1` sobre `backend/alembic/versions/0006_sla_configuration.py` en PostgreSQL 16, verificar baseline, backfill, índices parciales y que `downgrade()` no toca datos históricos de tickets.
- [X] T067 Revisar accesibilidad en `frontend/src/views/AdminConfigurationPage.vue` y `frontend/src/components/admin/`: foco visible, etiquetas, `caption` en tablas, pestañas y diálogos con teclado.
- [X] T068 Revisar seguridad en `backend/app/api/v1/admin_configuration.py` y `backend/app/services/configuration.py`: 403 para no-admin, sin datos de configuración en respuestas no autorizadas, sin secretos ni cuerpos completos en logs.
- [ ] T069 Ejecutar la validación de `specs/008-configuracion-plazos-sla/quickstart.md` contra el entorno local y corregir cualquier divergencia de comportamiento o contrato.
- [ ] T070 [P] Escribir `backend/tests/integration/test_admin_configuration_performance.py` para medir p95 de `GET /admin/categories`, `GET /admin/sla-rules`, `GET /admin/config-history`, `POST /admin/sla-rules/batch` con 20 celdas y alta de ticket; ejecutarlo en PostgreSQL con `TEST_DATABASE_URL` y marcar el umbral de la constitución.
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
