# Tasks: HU-07 — Dashboard de cumplimiento de SLA

**Input**: Design documents from `/specs/007-dashboard-cumplimiento-sla/`

**Prerequisites**: `plan.md` (required), `spec.md` (required), `research.md`, `data-model.md`, `contracts/sla-dashboard.openapi.yaml`, `contracts/frontend-components.md`, `quickstart.md`

**Tests**: Incluidas y obligatorias. La constitución del proyecto (principio IV) y el `plan.md` exigen contratos primero y pruebas ejecutables por capa (pytest, FastAPI `TestClient`, Vitest, `@vue/test-utils` y `axe-core`). Las tareas de prueba se escriben antes de la implementación correspondiente y deben fallar primero.

**Organization**: Tareas agrupadas por historia de usuario para permitir implementación, prueba y entrega independientes. Prioridades de `spec.md`: US1 (P1, matriz de cumplimiento), US2 (P1, ranking de técnicos), US3 (P2, filtros), US4 (P2, semáforo), US5 (P3, estados, errores y frescura).

**Feature Name**: `007-dashboard-cumplimiento-sla` — Dashboard de cumplimiento de SLA (HU-07).

## Correspondencia con las fases solicitadas

| Fase solicitada | Fases de este documento |
|---|---|
| 1. Reglas y configuración SLA (backend) | Phase 1 (T001–T004) y Phase 2 (T005–T011): verificación del catálogo `priorities.base_hours` y `tickets.sla_deadline`, umbrales 90/70 y `compliance_band()` |
| 2. Cálculo de métricas y endpoints REST | Phase 2 (contratos y guard) + Phase 3 (US1: proyección y matriz) + Phase 4 (US2: ranking) + Phase 5 (US3: filtros y `/options`) |
| 3. Vista y componentes del dashboard | Phase 2 (T012–T017: base compartida del frontend) + Phase 3 (US1: resumen y matriz) + Phase 4 (US2: ranking) + Phase 5 (US3: barra de filtros) + Phase 6 (US4: semáforo) + Phase 7 (US5: estados y accesibilidad) |
| 4. Pruebas y regresión | Pruebas dentro de cada fase + Phase 8 (T071–T076): rendimiento, concurrencia, no regresión HU-04/05/06, accesibilidad y validación end-to-end |

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Puede ejecutarse en paralelo (archivo distinto, sin dependencias pendientes)
- **[Story]**: Historia de usuario a la que pertenece la tarea (`US1`…`US5`); Setup, Foundational y Polish no llevan etiqueta
- Todas las descripciones incluyen la ruta exacta del archivo afectado y la trazabilidad a `HU07-RF-*` / `HU07-SC-*`

## Path Conventions

- **Backend (FastAPI + SQLAlchemy)**: `backend/app/`, `backend/tests/`, `backend/requirements.txt`
- **Frontend (Vue 3 + TypeScript)**: `frontend/src/`, `frontend/tests/`
- **Contratos y documentación**: `specs/007-dashboard-cumplimiento-sla/contracts/`
- **Raíz**: `docker-compose.yml` (no se modifica)

## Reglas de conservación (no negociables)

1. **Cero migraciones y cero cambios de esquema**: no crear archivos en `backend/alembic/versions/`; la cabeza sigue siendo `0004_assignee_changes_notifications`. `tickets`, `ticket_timeline_entries`, `users`, `priorities` y `categories` se consultan en solo lectura.
2. **Línea temporal append-only intacta**: el dashboard solo ejecuta `SELECT`; nunca inserta, actualiza ni elimina en `backend/app/models/timeline.py` ni en `ticket_timeline_entries`.
3. **HU-04/HU-05/HU-06 sin cambios de comportamiento**: no modificar `backend/app/services/work_queue.py`, `backend/app/api/v1/work_queue.py`, `backend/app/services/ticket_workflow.py`, `backend/app/services/ticket_timeline.py`, `backend/app/services/assignee_change.py`, `backend/app/services/notifications.py`, `backend/app/models/ticket.py` ni `backend/app/models/timeline.py`.
4. **Adiciones puntuales permitidas**: `backend/app/utils/sla.py` (solo añadir constantes y función, sin tocar las existentes), `backend/app/api/deps.py` (solo añadir el guard), `backend/app/api/v1/router.py` (solo registrar el router), `frontend/src/router/index.ts` (solo añadir ruta y guard), `frontend/src/components/layout/AppHeader.vue` (solo añadir el enlace) y `frontend/src/utils/slaStyles.ts` (solo añadir mapas).
5. **Docker Compose intacto**: `docker-compose.yml` no se toca; no se añaden servicios, imágenes ni variables obligatorias.
6. **Solo endpoints `GET` nuevos**: ningún `POST`, `PUT`, `PATCH` o `DELETE`; no existe ninguna acción de edición en la vista.
7. **Frontend**: no modificar `frontend/src/stores/workQueue.ts`, `frontend/src/views/WorkQueuePage.vue`, `frontend/src/stores/ticketDetail.ts` ni `frontend/src/components/work-queue/*`.
8. **Idioma y zona horaria**: textos es-ES, instantes UTC en la API y presentación en `Europe/Madrid`; sin `v-html` con datos del backend.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirmar la línea base, las reglas de SLA ya existentes y la dependencia de zonas horarias antes de escribir código.

- [x] T001 [P] Ejecutar `python -m pytest -q` desde `backend/` y confirmar que la suite base de HU-04/HU-05/HU-06 está en verde y que la cabeza de Alembic es `0004_assignee_changes_notifications` revisando `backend/alembic/versions/0004_assignee_changes_notifications.py`; no crear migraciones. Cubre HU07-RF-052.
- [x] T002 [P] Ejecutar `npm run test` y `npm run build` desde `frontend/` según los scripts de `frontend/package.json` y confirmar que la suite y el build base están en verde antes de añadir código. Cubre HU07-RF-052.
- [x] T003 [P] Verificar en solo lectura que los tiempos límite por prioridad ya existen y no se duplican: Crítica 4 h, Alta 8 h, Media 24 h y Baja 72 h en `backend/scripts/seed_dev.py`, `priority.base_hours` en `backend/app/models/priority.py` y el límite histórico `ticket.sla_deadline` en `backend/app/models/ticket.py`; documentar en la descripción del PR que el dashboard usa el valor estampado en el ticket y no recalcula con el catálogo. No crear tablas, columnas ni configuración alternativa de SLA. Cubre HU07-RF-004, HU07-RF-052.
- [x] T004 Añadir `tzdata` como última línea de `backend/requirements.txt` (sin alterar las versiones existentes) para que `zoneinfo.ZoneInfo("Europe/Madrid")` funcione en Windows durante las pruebas y el desarrollo local; no modificar `docker-compose.yml` ni el `Dockerfile`. Cubre HU07-RF-027, HU07-RF-050.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Umbrales del semáforo, contratos Pydantic, guard de rol, tipos/cliente/formato del frontend y store base que necesitan todas las historias.

**⚠️ CRITICAL**: Ninguna historia de usuario puede comenzar hasta completar esta fase.

### Tests de la infraestructura compartida (escribir primero)

- [x] T005 [P] Escribir en `backend/tests/unit/test_sla_dashboard_semaphore.py` las pruebas de `SLA_GREEN_THRESHOLD_PCT == 90.0`, `SLA_AMBER_THRESHOLD_PCT == 70.0` y `compliance_band()`: `100.0` y `90.0` → `"verde"`; `89.9` y `70.0` → `"ambar"`; `69.9` y `0.0` → `"rojo"`; `None` → `"sin_datos"`; el valor exacto de cada umbral pertenece a la banda superior. Deben fallar antes de T009. Cubre HU07-RF-038, HU07-RF-041, HU07-SC-006.
- [x] T006 [P] Escribir en `backend/tests/contract/test_sla_dashboard_contract.py` las pruebas de contrato de `ComplianceMetrics`, `MatrixRow`, `TotalsEntry`, `RankingEntry`, `SlaDashboardResponse`, `SlaDashboardOptions` y `SlaSemaphore`: campos requeridos, `compliance_pct`/`avg_response_seconds`/`technician_id`/`team`/`is_active` anulables, `priority_level` entre 1 y 4, `thresholds.green_pct`/`amber_pct` presentes y `scope` limitado a `priority|category|global`. Deben fallar antes de T010. Cubre HU07-RF-005 a HU07-RF-010, HU07-RF-019 a HU07-RF-024, HU07-RF-038 a HU07-RF-042.
- [x] T007 [P] Escribir en `backend/tests/integration/test_sla_dashboard_permissions.py` la matriz de acceso de los dos endpoints: sin token → `401`; `tecnico` y `usuario` → `403 forbidden` con el mensaje «No tienes permiso para acceder a este dashboard.» y sin claves de datos agregados; `supervisor` y `admin` → `200`; `Cache-Control: no-store` y `Vary: Authorization`; el JSON no contiene `email`, `creator`, `number` ni identificadores de tickets. Debe fallar antes de T025/T046. Cubre HU07-RF-043, HU07-SC-008.
- [x] T008 [P] Escribir en `frontend/tests/unit/slaDashboardFormat.spec.ts` las pruebas de `formatPercent` («87,5 %» con coma decimal y un decimal), `formatDurationEs` («3 d 4 h», «4 h 12 min», «37 min», «menos de 1 min» para `0 < seconds < 60` y «0 min» para `seconds = 0`) y `formatMadridDateTime` («15/11/2026 09:34» en `Europe/Madrid`, incluido un instante UTC que cambia de día). Deben fallar antes de T014. Cubre HU07-RF-050, HU07-RN-15.
- [x] T009 Añadir al final de `backend/app/utils/sla.py`, sin modificar `as_utc`, `warning_threshold_seconds`, `classify_sla`, `sla_outcome` ni `breach_delay_seconds`, las constantes `SLA_GREEN_THRESHOLD_PCT = 90.0` y `SLA_AMBER_THRESHOLD_PCT = 70.0` y la función pura `compliance_band(pct: Decimal | float | None) -> str` que devuelve `"verde"`, `"ambar"`, `"rojo"` o `"sin_datos"` aplicando banda superior en los umbrales exactos. Cubre HU07-RF-038, HU07-RF-041, HU07-RF-042.
- [x] T010 [P] Crear `backend/app/schemas/sla_dashboard.py` con `SlaSemaphore` (`verde|ambar|rojo|sin_datos`), `Thresholds` (`green_pct`, `amber_pct`), `ComplianceMetrics` (`ticket_count`, `no_sla_count`, `attended_with_sla`, `on_time`, `compliance_pct: float | None`, `avg_response_seconds: float | None`, `overdue_count`, `semaphore`), `MatrixRow` (`priority_level` 1–4, `priority_name`, `priority_is_active`, `category_id: UUID | None`, `category_name` con «Sin categoría» cuando `category_id` es nulo, `category_is_active: bool | None`), `TotalsEntry` (`scope`), `RankingEntry` (`technician_id: UUID | None`, `technician_name`, `team: str | None`, `is_active: bool | None`, `overdue_count`, `avg_delay_seconds`), `RankingBlock` (`technicians`, `unassigned`, `overdue_total`), `SlaDashboardData`, `EffectiveFilters`, `SlaDashboardMeta` (`generated_at`, `timezone="Europe/Madrid"`, `thresholds`, `filters`, `has_tickets`) y los esquemas de opciones `FilterCategoryOption`/`FilterPriorityOption`/`SlaDashboardOptions`, todos espejo de `specs/007-dashboard-cumplimiento-sla/contracts/sla-dashboard.openapi.yaml`. Cubre HU07-RF-005 a HU07-RF-024, HU07-RF-038 a HU07-RF-042.
- [x] T011 Añadir a `backend/app/api/deps.py` la constante `SLA_DASHBOARD_FORBIDDEN_MESSAGE = "No tienes permiso para acceder a este dashboard."` y la dependencia `require_supervisor_or_admin(current_user=Depends(get_current_user))` que permite solo `UserRole.supervisor` y `UserRole.admin` y lanza `ApiError(403, "forbidden", SLA_DASHBOARD_FORBIDDEN_MESSAGE)` en el resto; no modificar `get_current_user` ni `require_technician`. Cubre HU07-RF-043, HU07-SC-008.

### Base frontend compartida

- [x] T012 [P] Crear `frontend/src/types/slaDashboard.ts` con `SlaSemaphore`, `SlaThresholds`, `ComplianceMetrics`, `MatrixRow`, `TotalsEntry`, `RankingEntry`, `SlaDashboardFilters`, `SlaDashboardData`, `SlaDashboardMeta`, `SlaDashboardOptions`, `SlaDashboardResponse`, exactamente como el bloque TypeScript de `specs/007-dashboard-cumplimiento-sla/contracts/frontend-components.md` §2. Cubre HU07-RF-005 a HU07-RF-024.
- [x] T013 Crear `frontend/src/api/slaDashboard.ts` con `fetchSlaDashboard(filters, signal)` y `fetchSlaDashboardOptions({desde, hasta}, signal)` usando `apiGet` de `frontend/src/api/client.ts`, enviando solo los query params definidos (`desde`, `hasta`, `categorias` como CSV, `prioridades` como CSV) y tipando la respuesta con `SlaDashboardResponse`/`SlaDashboardOptions`; sin métodos de escritura. Cubre HU07-RF-001, HU07-RF-027 a HU07-RF-037.
- [x] T014 [P] Crear `frontend/src/utils/format.ts` con `formatPercent(value: number | null)` (`Intl.NumberFormat('es-ES', { minimumFractionDigits: 1, maximumFractionDigits: 1 })` + « %»), `formatDurationEs(seconds: number)` que delega en `formatDuration` de `frontend/src/utils/sla.ts` — que devuelve «menos de 1 min» para `0 < seconds < 60` — y `formatMadridDateTime(iso: string)` con `Intl.DateTimeFormat('es-ES', { timeZone: 'Europe/Madrid' })` en formato «dd/mm/aaaa hh:mm». Cubre HU07-RF-050, HU07-RN-15.
- [x] T015 [P] Añadir a `frontend/src/api/client.ts` el helper `getStoredUserRole(): string | null` que decodifica el payload del JWT almacenado en `localStorage.access_token` (base64url, sin verificar la firma) y devuelve `role`, o `null` si no hay token o el payload no es válido; no modificar `getAccessToken`, `setAccessToken`, `apiGet` ni `apiPost`. Cubre HU07-RF-043.
- [x] T016 [P] Escribir en `frontend/tests/stores/slaDashboard.spec.ts` las pruebas base del store: `load()` puebla `data`, `meta`, `options`, `lastFetchedAt`; `refresh()` reutiliza los filtros vigentes; una respuesta abortada no cambia el estado; un error inicial deja `error` sin `data` ni métricas a cero; `mapError` traduce `invalid_date_range`, `forbidden`, `unauthorized`, `network` y `server` a mensajes es-ES. Deben fallar antes de T017. Cubre HU07-RF-044 a HU07-RF-048.
- [x] T017 Crear `frontend/src/stores/slaDashboard.ts` como store setup de Pinia (`defineStore('slaDashboard', () => {...})`) con estado `data`, `meta`, `options`, `loading`, `updating`, `error: ApiClientError | null`, `stale`, `lastFetchedAt`, acciones `load()` y `refresh()` con `AbortController` y descarte de respuestas fuera de orden, y `mapError` con mensajes es-ES (`invalid_date_range` → «La fecha inicial no puede ser posterior a la fecha final.»; `forbidden` → «No tienes permiso para acceder a este dashboard.»; `unauthorized` → «Tu sesión ha caducado. Inicia sesión de nuevo.»; red/servidor → «No se pudo cargar el dashboard. Inténtalo de nuevo.»). Cubre HU07-RF-044 a HU07-RF-048.

**Checkpoint**: Umbrales, contratos, guard, tipos, cliente, formato y store base listos; las pruebas transversales están escritas y en rojo. Las historias pueden comenzar.

---

## Phase 3: User Story 1 — Ver el cumplimiento agregado por prioridad y categoría (Priority: P1) 🎯 MVP

**Goal**: El supervisor abre el dashboard y ve un resumen global y una matriz prioridad × categoría con, por cada combinación con datos, número de tickets, porcentaje de cumplimiento, tiempo medio de respuesta y tickets vencidos, calculados sobre la primera finalización y el SLA histórico.

**Independent Test**: Con tickets de control que cubran varias prioridades y categorías (incluido uno atendido exactamente en el límite y uno sin SLA), `GET /api/v1/sla-dashboard` devuelve un `summary` y una `matrix` coherentes, sin filas para combinaciones vacías, con totales siempre presentes y sin escrituras en la línea temporal.

### Tests for User Story 1 ⚠️

> **NOTE: Escribir primero y comprobar que fallan antes de implementar.**

- [x] T018 [P] [US1] Escribir en `backend/tests/unit/test_sla_dashboard_math.py` las pruebas de las fórmulas puras de agregación: `cumplimiento = 100 × dentro_de_plazo ÷ atendido_con_sla` con `Decimal.quantize(0.1, ROUND_HALF_UP)`; `primera_finalizacion == sla_deadline` cuenta dentro de plazo; `primera_finalizacion > sla_deadline` y activo con `sla_deadline < ahora` cuentan vencidos; activo sin vencer queda fuera de `%` y media; `sla_deadline = NULL` incrementa `no_sla_count` y nunca vence; reabierto cuenta una vez con la primera finalización; `avg_response_seconds` es la media exacta de los atendidos con SLA y `NULL` si el denominador es cero; totales recalculados desde tickets y nunca como media de celdas; orden Crítica→Baja y categorías alfabéticas con «Sin categoría» al final. Cubre HU07-RF-006 a HU07-RF-018, HU07-SC-001, HU07-SC-003, HU07-SC-009, HU07-SC-015.
- [x] T019 [P] [US1] Escribir en `backend/tests/integration/test_sla_dashboard.py` las pruebas de integración de `GET /api/v1/sla-dashboard`: `200` con `summary`, `matrix`, `priority_totals`, `category_totals` y `meta`; cabeceras `Cache-Control: no-store` y `Vary: Authorization`; combinaciones con tickets presentes y combinaciones vacías ausentes; totales por prioridad, por categoría y global siempre emitidos; conciliación `suma de celdas = totales`; etiqueta «Sin categoría»; categoría/prioridad desactivada con su etiqueta histórica y sufijo «(inactiva)»; tickets sin SLA fuera del porcentaje y de la media; un ticket en el límite exacto dentro de plazo; un ticket reabierto contado una vez. Cubre HU07-RF-003 a HU07-RF-018, HU07-RF-051, HU07-SC-001, HU07-SC-003, HU07-SC-014, HU07-SC-015, HU07-SC-016.
- [x] T020 [P] [US1] Escribir en `frontend/tests/components/SlaSummary.spec.ts` las pruebas del resumen global: tickets considerados, atendidos con SLA, cumplimiento, tiempo medio, vencidos y sin SLA; «Sin datos» cuando `compliance_pct` y `avg_response_seconds` son `null`; formato es-ES de porcentaje y duración; sin acciones de edición. Cubre HU07-RF-005, HU07-RF-011, HU07-RF-050.
- [x] T021 [P] [US1] Escribir en `frontend/tests/components/ComplianceMatrix.spec.ts` las pruebas de `ComplianceMatrix.vue` y `MatrixCell.vue`: filas en orden Crítica, Alta, Media y Baja; columnas alfabéticas con «Sin categoría» al final; solo celdas con datos; columnas/filas de totales y total global siempre visibles; cada celda muestra tickets, porcentaje, tiempo medio y vencidos; sufijo «(inactiva)»; `<caption>` y `th scope="col"`/`scope="row"`; ausencia de filas de ceros. Cubre HU07-RF-006 a HU07-RF-018, HU07-RF-050.
- [x] T022 [P] [US1] Escribir en `frontend/tests/components/SlaDashboardPage.spec.ts` las pruebas base de la página: monta con Pinia y `fetch` simulado, dispara una única carga inicial, renderiza resumen, matriz y esqueleto de carga, y no expone botones, formularios ni llamadas de escritura (solo `GET`). Cubre HU07-RF-001, HU07-RF-002, HU07-RF-005.

### Implementation for User Story 1

- [x] T023 [US1] Implementar en `backend/app/services/sla_dashboard.py` la proyección de población con **una única sentencia `SELECT` de solo lectura** y CTE `poblacion`, parametrizada por `:desde_utc`, `:hasta_utc`, `:categorias`, `:prioridades` y `:ahora`: deriva `con_sla = sla_deadline IS NOT NULL`, `primera_finalizacion` (primera entrada `status_change` con `to_status = 'resuelto'` por `(created_at, event_order, id)`; fallback `finalized_at` solo si no hay entrada, ticket heredado), `atendido = primera_finalizacion IS NOT NULL`, `atendido_con_sla = atendido AND con_sla`, `dentro_de_plazo = atendido_con_sla AND primera_finalizacion <= sla_deadline`, `tiempo_respuesta_s = EXTRACT(EPOCH FROM primera_finalizacion - created_at)` (nunca negativo), `vencido = con_sla AND ((atendido AND primera_finalizacion > sla_deadline) OR (NOT atendido AND :ahora > sla_deadline))`, `retraso_s` (ahora − límite si activo; primera finalización − límite si atendido) y `atribuido_a` (autor de la primera entrada `status_change` con `to_status = 'resuelto'` ordenada por `(created_at, event_order, id)` si `atendido`; `assignee_id` si no; `NULL` si ninguno). El lateral de timeline se limita a la población y usa `ix_timeline_ticket_created`; no escribir nada en `tickets` ni en `ticket_timeline_entries`. Cubre HU07-RF-003, HU07-RF-004, HU07-RF-013, HU07-RF-014, HU07-RF-052, HU07-RN-02, HU07-RN-03, HU07-RN-06, HU07-RN-09.
- [x] T024 [US1] Implementar en `backend/app/services/sla_dashboard.py` las funciones puras de agregación sobre la proyección de T023: resumen global, matriz agrupada por `(priority_id, category_id)` con `category_id = NULL` ⇒ «Sin categoría», y totales por prioridad, por categoría y global **recalculados desde los tickets subyacentes** (nunca promediando celdas). Cada métrica debe exponer `ticket_count`, `no_sla_count`, `attended_with_sla`, `on_time`, `compliance_pct` (`Decimal(100 × on_time / attended_with_sla).quantize(0.1, ROUND_HALF_UP)`, `None` si el denominador es 0), `avg_response_seconds` (media exacta, `None` si no hay atendidos con SLA), `overdue_count` y `semaphore = compliance_band(compliance_pct)`. Ordenar prioridades 1→4 y categorías alfabéticamente con «Sin categoría» al final; omitir combinaciones con `ticket_count = 0`; propagar «(inactiva)» desde `priority_is_active`/`category_is_active`. Cubre HU07-RF-005 a HU07-RF-018, HU07-RF-051, HU07-RN-04, HU07-RN-05, HU07-RN-07, HU07-RN-15.
- [x] T025 [US1] Implementar en `backend/app/services/sla_dashboard.py` la resolución del rango de fechas y el ensamblado del snapshot: convertir `desde`/`hasta` (`YYYY-MM-DD`) a un semirrango UTC `[00:00 Europe/Madrid del día inicial, 00:00 Europe/Madrid del día siguiente al final)` con `zoneinfo.ZoneInfo("Europe/Madrid")`; si faltan, aplicar por defecto los últimos 30 días naturales incluido el día de la consulta; generar `generated_at` en UTC, `timezone = "Europe/Madrid"`, `thresholds = {green_pct: 90.0, amber_pct: 70.0}` y `has_tickets` según si la población tiene tickets. Cubre HU07-RF-003, HU07-RF-028, HU07-RF-044, HU07-RN-02, HU07-RN-12.
- [x] T026 [US1] Crear `backend/app/api/v1/sla_dashboard.py` con `router = APIRouter(tags=["Dashboard de SLA"])` y el endpoint `GET /sla-dashboard` que inyecta `current_user=Depends(require_supervisor_or_admin)` y `session=Depends(get_session)`, delega en el servicio (endpoint solo orquesta), declara `response_model=SlaDashboardResponse`, fija `Cache-Control: no-store` y `Vary: Authorization` y documenta `401`, `403` y `422`. Debe responder con `data` (summary, matrix, priority_totals, category_totals, ranking) y `meta`. Cubre HU07-RF-001, HU07-RF-005, HU07-RF-010, HU07-RF-044.
- [x] T027 [US1] Modificar `backend/app/api/v1/router.py` para importar `sla_dashboard` y registrar `api_router.include_router(sla_dashboard.router)` sin alterar el orden ni el comportamiento de `work_queue`, `tickets`, `notifications` y `dev_auth`. Cubre HU07-RF-001.
- [x] T028 [P] [US1] Crear `frontend/src/components/sla-dashboard/SlaSummary.vue` con las seis cifras del resumen global (tickets considerados, atendidos con SLA, cumplimiento, tiempo medio, vencidos, sin SLA), estados «Sin datos» cuando el valor es nulo, formato es-ES y estructura accesible (`<dl>` o tabla con etiquetas asociadas). Cubre HU07-RF-005, HU07-RF-011, HU07-RF-050.
- [x] T029 [P] [US1] Crear `frontend/src/components/sla-dashboard/SlaDashboardSkeleton.vue` como esqueleto de carga con `aria-busy="true"` y texto «Cargando dashboard…», siguiendo el patrón de `frontend/src/components/work-queue/WorkQueueSkeleton.vue`, sin reutilizar ni modificar ese componente. Cubre HU07-RF-048.
- [x] T030 [US1] Crear `frontend/src/components/sla-dashboard/MatrixCell.vue` que reciba `metrics: ComplianceMetrics` y muestre número de tickets, porcentaje de cumplimiento (o «Sin datos» neutro si es `null`), tiempo medio con `formatDurationEs` y número de vencidos; sin semáforo todavía (se integra en US4). Cubre HU07-RF-006 a HU07-RF-011.
- [x] T031 [US1] Crear `frontend/src/components/sla-dashboard/ComplianceMatrix.vue` que reciba `matrix`, `priorityTotals`, `categoryTotals` y `summary` y renderice la tabla prioridad (Crítica→Baja) × categorías alfabéticas («Sin categoría» al final), celdas solo para combinaciones con datos, fila/columna de totales y celda global siempre visibles, sufijo «(inactiva)», `<caption>`, `th scope` y navegación por teclado. Cubre HU07-RF-006 a HU07-RF-018, HU07-RF-050.
- [x] T032 [US1] Crear `frontend/src/views/SlaDashboardPage.vue` en modo solo lectura: al montar llama a `useSlaDashboardStore().load()`, muestra `SlaDashboardSkeleton` mientras `loading` sin datos, y compone resumen y matriz; no incluye botones, formularios ni acciones de escritura. Cubre HU07-RF-001, HU07-RF-002, HU07-RF-005.
- [x] T033 [US1] Añadir a `frontend/src/router/index.ts` la ruta `{ path: '/dashboard-sla', name: 'sla-dashboard', component: () => import('@/views/SlaDashboardPage.vue'), meta: { requiresRoles: ['supervisor', 'admin'] } }` sin modificar las rutas existentes ni el comportamiento de `/cola-de-trabajo`, `/tickets/:id` y `/login`. Cubre HU07-RF-001.

**Checkpoint**: US1 funcional y verificable de forma independiente: la API devuelve matriz y totales coherentes y la vista muestra el dashboard de solo lectura. Es el MVP.

---

## Phase 4: User Story 2 — Identificar a los técnicos con más tickets vencidos (Priority: P1)

**Goal**: El supervisor ve un ranking de técnicos con tickets vencidos acumulados, ordenado de mayor a menor volumen, con desempates deterministas y una fila separada «Sin asignar».

**Independent Test**: Con tickets vencidos distribuidos entre varios técnicos (incluido un reasignado tras incumplir y uno sin responsable), `ranking.technicians` solo contiene técnicos con al menos un vencido, está ordenado por volumen y desempates, «Sin asignar» aparece al final y `ranking.overdue_total` coincide con `summary.overdue_count`.

### Tests for User Story 2 ⚠️

- [x] T034 [P] [US2] Escribir en `backend/tests/unit/test_sla_dashboard_ranking.py` las pruebas de la agregación de ranking: atribución mixta (activo vencido → responsable actual; finalizado vencido → autor de la primera finalización; sin responsable → fila «Sin asignar»); cada vencido cuenta una sola vez; solo técnicos con ≥ 1 vencido; orden `overdue_count DESC` → `avg_delay_seconds DESC` con valor exacto → `lower(name) ASC` → `team ASC` estable; «Sin asignar» al final; técnico inactivo conserva su fila con `is_active = false`; `overdue_total` = suma de técnicos + «Sin asignar». Cubre HU07-RF-019 a HU07-RF-025, HU07-SC-004, HU07-SC-014.
- [x] T035 [P] [US2] Escribir en `backend/tests/integration/test_sla_dashboard_ranking.py` las pruebas de integración del bloque `ranking`: orden por volumen y desempates; técnico inactivo con vencidos; ticket vencido reasignado después del incumplimiento atribuido una vez a quien lo finalizó; vencido activo y pendiente de atención atribuido al `assignee_id` vigente; vencido reabierto tras finalización tardía atribuido a quien lo finalizó y no al responsable actual; vencido sin responsable en `unassigned`; `overdue_total == summary.overdue_count`; ausencia de correos, creadores, números y detalle de tickets; periodo sin vencidos → listas vacías y `unassigned = null`. Cubre HU07-RF-019 a HU07-RF-026, HU07-RF-051, HU07-SC-014.
- [x] T036 [P] [US2] Escribir en `frontend/tests/components/TechnicianRanking.spec.ts` las pruebas de `TechnicianRanking.vue`: columnas posición, técnico, equipo, vencidos y retraso medio; orden recibido sin recálculo; sufijo «(inactivo)»; fila «Sin asignar» separada al final; estado vacío específico «No hay tickets vencidos en el periodo seleccionado.»; sin correos ni tickets individuales; `<caption>` y `th scope`. Cubre HU07-RF-019 a HU07-RF-026, HU07-RF-050.

### Implementation for User Story 2

- [x] T037 [US2] Implementar en `backend/app/services/sla_dashboard.py` el constructor del ranking sobre los tickets con `vencido = true` de la proyección de T023: agrupar por `atribuido_a`, calcular `overdue_count` y `avg_delay_seconds` exacto, ordenar con `overdue_count DESC`, `avg_delay_seconds DESC` (valor exacto), `lower(technician_name) ASC` y `team ASC` con orden estable, emitir solo técnicos con ≥ 1 vencido y añadir `unassigned` al final (con `technician_id = null`, `technician_name = "Sin asignar"`, `team = null`, `is_active = null`) solo si hay vencidos sin responsable. Cubre HU07-RF-019 a HU07-RF-025, HU07-RN-08, HU07-RN-09.
- [x] T038 [US2] Integrar el ranking en el ensamblado del snapshot de `backend/app/services/sla_dashboard.py`: incluir `data.ranking = {technicians, unassigned, overdue_total}` donde `overdue_total` sea la suma de vencidos de técnicos más «Sin asignar» y validar internamente que coincide con `summary.overdue_count`; la misma población y filtros que la matriz y los totales. Cubre HU07-RF-022, HU07-RF-024, HU07-RF-051, HU07-SC-014.
- [x] T039 [US2] Crear `frontend/src/components/sla-dashboard/TechnicianRanking.vue` con tabla ordenada (posición, técnico con «(inactivo)» si procede, equipo, vencidos y retraso medio con `formatDurationEs`), fila «Sin asignar» separada al final, estado vacío específico y accesibilidad (`<caption>`, `scope`, `aria-live` si cambia la lista). Cubre HU07-RF-019 a HU07-RF-026, HU07-RF-050.
- [x] T040 [US2] Integrar `TechnicianRanking` en `frontend/src/views/SlaDashboardPage.vue` con los datos de `store.data?.ranking` y su estado vacío, sin recalcular el orden en cliente ni mostrar datos personales adicionales. Cubre HU07-RF-019, HU07-RF-022, HU07-RF-026.

**Checkpoint**: US1 y US2 funcionan de forma independiente; el ranking concilia con el total de vencidos del dashboard.

---

## Phase 5: User Story 3 — Acotar el dashboard por fechas, categoría y prioridad (Priority: P2)

**Goal**: El supervisor filtra por rango de fechas, categorías y prioridades, con lógica «O» dentro de cada dimensión y «Y» entre dimensiones; todas las secciones usan el mismo conjunto y los filtros se conservan en la URL y al actualizar.

**Independent Test**: Se aplican filtros por separado y en combinación y se comprueba que matriz, totales y ranking se recalculan con el mismo conjunto, que `desde > hasta` bloquea la consulta con `422 invalid_date_range`, que las opciones de filtro incluyen las categorías/prioridades presentes (incluidas inactivas y «Sin categoría») y que restablecer vuelve a los últimos 30 días naturales.

### Tests for User Story 3 ⚠️

- [x] T041 [P] [US3] Escribir en `backend/tests/integration/test_sla_dashboard_filters.py` las pruebas de filtros y opciones: rango por defecto de los últimos 30 días naturales calculado en servidor; ambos extremos incluidos y días naturales `Europe/Madrid` (incluido un rango que cruza el cambio de hora); `categorias` con «O» e inclusión de `sin_categoria`; `prioridades` con «O»; dimensiones combinadas con «Y»; todas las secciones usan el mismo conjunto; `desde > hasta` → `422` con código `invalid_date_range` y mensaje «La fecha inicial no puede ser posterior a la fecha final.»; UUID o nivel fuera de 1–4 → `422 invalid_request`; `GET /sla-dashboard/options` devuelve solo categorías y prioridades con tickets en el periodo, con `is_active`, y `{id: null, name: "Sin categoría"}` si existen tickets sin categoría; un filtro sin resultados no inventa datos ni filas. Cubre HU07-RF-027 a HU07-RF-037, HU07-SC-005, HU07-SC-012, HU07-SC-016.
- [x] T042 [P] [US3] Escribir en `frontend/tests/components/SlaDashboardFilters.spec.ts` las pruebas de `SlaDashboardFilters.vue`: inputs `type="date"` para `desde`/`hasta`; chips con checkbox para categorías (incluida «Sin categoría») y prioridades; resumen de filtros activos; botón «Aplicar» deshabilitado y con mensaje cuando `desde > hasta`; emisión de `apply` solo con rango válido; botón «Restablecer» que emite `reset`; etiquetas asociadas y navegación por teclado. Cubre HU07-RF-027 a HU07-RF-037, HU07-RF-050.
- [x] T043 [US3] Extender `frontend/tests/stores/slaDashboard.spec.ts` con las pruebas de filtros: lectura/escritura de `desde`, `hasta`, `categorias` y `prioridades` en la query de la URL; `setFilters` con rango inválido no emite petición y conserva los filtros anteriores; `resetFilters` vuelve a la configuración por defecto; los filtros se conservan al llamar a `refresh()`; los valores efectivos se toman de `meta.filters`. Cubre HU07-RF-028, HU07-RF-033, HU07-RF-035, HU07-RF-036.

### Implementation for User Story 3

- [x] T044 [US3] Implementar en `backend/app/services/sla_dashboard.py` el parseo y la validación de filtros: fechas `YYYY-MM-DD` válidas, `desde <= hasta` (si no, `ApiError(422, "invalid_date_range", "La fecha inicial no puede ser posterior a la fecha final.")`), CSV de categorías con UUIDs válidos más el literal `sin_categoria`, y CSV de prioridades con enteros 1–4 sin duplicados; cualquier valor mal formado → `ApiError(422, "invalid_request", "Revisa los filtros e inténtalo de nuevo.")`. Aplicar los filtros a la proyección con «O» dentro de cada dimensión y «Y» entre dimensiones, usando `category_id IS NULL` para `sin_categoria`. Cubre HU07-RF-027 a HU07-RF-034.
- [x] T045 [US3] Implementar en `backend/app/services/sla_dashboard.py` la consulta de opciones del periodo: categorías con al menos un ticket creado en el rango, con `is_active` vigente y la opción `{id: null, name: "Sin categoría", is_active: null}` si existen tickets sin categoría; prioridades con al menos un ticket, orden 1–4, `name` e `is_active`; devolver además `desde`/`hasta` efectivas. Cubre HU07-RF-029, HU07-RF-030, HU07-RF-037.
- [x] T046 [US3] Añadir a `backend/app/api/v1/sla_dashboard.py` los parámetros de consulta `desde`, `hasta`, `categorias` y `prioridades` al endpoint `GET /sla-dashboard`, mapeando las validaciones del servicio a `422` con el formato `{"detail": {"code", "message"}}` existente y manteniendo `no-store`/`Vary: Authorization` también en las respuestas de error. Cubre HU07-RF-027, HU07-RF-031, HU07-RF-033.
- [x] T047 [US3] Añadir a `backend/app/api/v1/sla_dashboard.py` el endpoint `GET /sla-dashboard/options` con `Depends(require_supervisor_or_admin)`, parámetros `desde`/`hasta`, `response_model=SlaDashboardOptions`, las mismas validaciones de rango y cabeceras `Cache-Control: no-store` y `Vary: Authorization`. Cubre HU07-RF-029, HU07-RF-030, HU07-RF-043.
- [x] T048 [US3] Extender `frontend/src/stores/slaDashboard.ts` con los filtros `SlaDashboardFilters` sincronizados con la URL (`desde`, `hasta`, `categorias` CSV, `prioridades` CSV), `setFilters(f)` que valida `desde <= hasta` antes de navegar y no emite petición inválida, `resetFilters()` a la configuración por defecto, conservación de filtros en `refresh()` y uso de `meta.filters` para pintar los valores efectivos. Cubre HU07-RF-028, HU07-RF-033, HU07-RF-035, HU07-RF-036, HU07-RF-037.
- [x] T049 [US3] Crear `frontend/src/components/sla-dashboard/SlaDashboardFilters.vue` con barra reactiva: rango de fechas (`type="date"`), multiselección de categorías y prioridades desde `options` (incluida «Sin categoría» y marcas de inactiva), resumen de filtros activos, botones «Aplicar» y «Restablecer», bloqueo con mensaje accesible si `desde > hasta` y eventos `apply`, `reset` y `change`. Cubre HU07-RF-027 a HU07-RF-037, HU07-RF-050.
- [x] T050 [US3] Crear `frontend/src/components/sla-dashboard/DashboardEmptyState.vue` con las variantes `variant: 'periodo' | 'filtros'`: «No hay tickets en el periodo seleccionado. Prueba con un rango de fechas más amplio.» con acción para ampliar fechas, y «No hay resultados para los filtros seleccionados.» con acción para limpiar filtros; mensajes diferenciados y accesibles (`role="status"`), sin mostrar una matriz de ceros. Cubre HU07-RF-034, HU07-RF-048, HU07-SC-012.
- [x] T051 [US3] Integrar `SlaDashboardFilters` y `DashboardEmptyState` en `frontend/src/views/SlaDashboardPage.vue`: cargar opciones con `fetchSlaDashboardOptions` al entrar y al cambiar el rango, aplicar filtros mediante el store, mostrar el resumen de filtros activos y distinguir el estado «sin resultados para los filtros» del periodo sin datos. Cubre HU07-RF-032, HU07-RF-034, HU07-RF-037.

**Checkpoint**: Los filtros recalculan de forma homogénea matriz, totales y ranking; la invalidación de rango se bloquea en cliente y servidor; las opciones reflejan el periodo.

---

## Phase 6: User Story 4 — Interpretar el cumplimiento con un semáforo (Priority: P2)

**Goal**: Cada porcentaje de cumplimiento (celdas, totales y global) se acompaña de un semáforo verde/ámbar/rojo o «Sin datos» neutro, con color, icono y texto, y de una leyenda con los umbrales vigentes recibidos del backend.

**Independent Test**: Con porcentajes ≥ 90, entre 70 y < 90, < 70 y sin atendidos con SLA, cada combinación recibe la banda correcta (incluido 90,0 → verde y 70,0 → ámbar), la leyenda muestra 90 %/70 % desde `meta.thresholds` y ningún estado depende solo del color.

### Tests for User Story 4 ⚠️

- [x] T052 [P] [US4] Escribir en `backend/tests/integration/test_sla_dashboard_semaphore_api.py` las pruebas de coherencia del semáforo en la API: cada `summary`, celda de `matrix`, total por prioridad, total por categoría y total global devuelve `semaphore` calculado sobre el `compliance_pct` redondeado; `compliance_pct = 90.0` → `verde`; `70.0` → `ambar`; `< 70.0` → `rojo`; `null` → `sin_datos`; `meta.thresholds` contiene exactamente `green_pct = 90.0` y `amber_pct = 70.0`; ningún porcentaje supera 100 ni es negativo. Cubre HU07-RF-038 a HU07-RF-042, HU07-SC-006.
- [x] T053 [P] [US4] Escribir en `frontend/tests/components/SemaphoreBadge.spec.ts` las pruebas de `SemaphoreBadge.vue`: para `verde`, `ambar`, `rojo` y `sin_datos` renderiza texto («En objetivo», «En riesgo», «Fuera de objetivo», «Sin datos»), icono de `lucide-vue-next` y clase de color estática; `aria-label` completo con el porcentaje; «Sin datos» en color neutro y sin color de alarma; variante `compact`; el estado nunca se transmite solo por color. Cubre HU07-RF-039, HU07-RF-040, HU07-RF-050, HU07-SC-007.
- [x] T054 [P] [US4] Escribir en `frontend/tests/components/SemaphoreLegend.spec.ts` las pruebas de `SemaphoreLegend.vue`: muestra los umbrales recibidos por props (montar con `{green_pct: 95, amber_pct: 75}` y comprobar que la leyenda cambia, demostrando que no hardcodea 90/70), explica las cuatro bandas y usa texto + icono además del color. Cubre HU07-RF-042, HU07-SC-006.

### Implementation for User Story 4

- [x] T055 [US4] Ampliar `frontend/src/utils/slaStyles.ts` (solo añadir, sin tocar `SLA_ROW_CLASS`, `SLA_BADGE_CLASS`, `PRIORITY_BADGE_CLASS`, `PRIORITY_BADGE_INACTIVE_CLASS` ni `SLA_ICON`) con `SEMAPHORE_BADGE_CLASS: Record<SlaSemaphore, string>`, `SEMAPHORE_ICON: Record<SlaSemaphore, Component>` y `SEMAPHORE_LABEL: Record<SlaSemaphore, string>` usando clases Tailwind completas y estáticas (`verde` → `CheckCircle2`/«En objetivo»; `ambar` → `AlertTriangle`/«En riesgo»; `rojo` → `AlertOctagon`/«Fuera de objetivo»; `sin_datos` → `MinusCircle`/«Sin datos» en `slate`). Cubre HU07-RF-040, HU07-RF-042.
- [x] T056 [US4] Crear `frontend/src/components/sla-dashboard/SemaphoreBadge.vue` con props `semaphore: SlaSemaphore`, `pct: number | null` y `compact?: boolean`; renderiza icono + etiqueta + color estático + `aria-label` («Cumplimiento 87,5 %, fuera de objetivo») y usa formato es-ES con `formatPercent`. Cubre HU07-RF-038 a HU07-RF-041, HU07-RF-050.
- [x] T057 [US4] Crear `frontend/src/components/sla-dashboard/SemaphoreLegend.vue` que reciba `thresholds: SlaThresholds` y muestre la leyenda de bandas con los valores vigentes recibidos del backend, sin números hardcodeados. Cubre HU07-RF-042, HU07-RF-050.
- [x] T058 [US4] Modificar `frontend/src/components/sla-dashboard/MatrixCell.vue` para sustituir el porcentaje en texto plano por `SemaphoreBadge` (manteniendo «Sin datos» neutro cuando `compliance_pct === null`) y conservar tickets, tiempo medio y vencidos. Cubre HU07-RF-038 a HU07-RF-041.
- [x] T059 [US4] Modificar `frontend/src/components/sla-dashboard/SlaSummary.vue` para mostrar `SemaphoreBadge` junto al cumplimiento global, manteniendo el resto de cifras y el estado «Sin datos». Cubre HU07-RF-038, HU07-RF-039.
- [x] T060 [US4] Integrar `SemaphoreLegend` en `frontend/src/views/SlaDashboardPage.vue` usando `store.meta?.thresholds`, de modo que toda la vista comparta los mismos umbrales y la leyenda refleje los valores vigentes. Cubre HU07-RF-042, HU07-SC-006.

**Checkpoint**: El semáforo es coherente en celdas, totales y global; la leyenda usa `meta.thresholds`; la información no depende solo del color.

---

## Phase 7: User Story 5 — Entender estados vacíos, errores y frescura de los datos (Priority: P3)

**Goal**: El supervisor distingue periodo sin tickets, filtros sin resultados, periodo sin SLA, periodo sin vencidos, error de carga, fallo de actualización con datos previos, sesión caducada y rango inválido; además, los datos se refrescan en ≤ 60 s, se pueden actualizar manualmente y se muestra la hora de última actualización en `Europe/Madrid`.

**Independent Test**: Se fuerzan un periodo vacío, un filtro sin resultados, un fallo inicial, un fallo de actualización con datos previos, una sesión caducada y un acceso con rol no autorizado, comprobando mensajes, acciones y ausencia de métricas a cero o datos filtrados.

### Tests for User Story 5 ⚠️

- [x] T061 [P] [US5] Escribir en `backend/tests/integration/test_sla_dashboard_states.py` las pruebas de estados del backend: periodo sin tickets → `has_tickets = false`, `summary` a cero y `matrix` vacía; todos los tickets sin SLA → `compliance_pct = null`, `semaphore = sin_datos`, `overdue_count = 0` y `no_sla_count > 0`; periodo sin vencidos → `ranking.technicians = []`, `unassigned = null` y `overdue_total = 0`; rango inválido → `422 invalid_date_range` sin datos parciales; sin sesión → `401`; rol no autorizado → `403` sin claves de datos. Cubre HU07-RF-039, HU07-RF-046, HU07-RF-047, HU07-RF-048, HU07-SC-012, HU07-SC-013.
- [x] T062 [P] [US5] Escribir en `frontend/tests/components/SlaDashboardStates.spec.ts` las pruebas de `DashboardEmptyState.vue` y `DashboardErrorState.vue`: variantes «periodo sin tickets», «filtros sin resultados», «sin SLA», «sin vencidos», error de carga con reintento, aviso de desactualización con datos previos y `forbidden`; mensajes es-ES diferenciados; `role="alert"`/`aria-live`; nunca métricas a cero en un error; emisión de `retry`/acción. Cubre HU07-RF-046 a HU07-RF-048, HU07-SC-012.
- [x] T063 [US5] Extender `frontend/tests/stores/slaDashboard.spec.ts` con las pruebas de frescura y degradación: sondeo cada 60 s con temporizadores falsos; pausa con `document.hidden` y refresco al recuperar foco/visibilidad; actualización manual conservando filtros; fallo de actualización con datos previos → `stale = true` y `data` intacta; fallo inicial → `error` sin `data`; `401` durante el sondeo → redirección a `/login?redirect=…` conservando la query de filtros. Cubre HU07-RF-044 a HU07-RF-048, HU07-SC-013.
- [x] T064 [P] [US5] Escribir en `frontend/tests/components/SlaDashboardAccess.spec.ts` las pruebas de acceso en cliente: sin token el guard redirige a `login` con `redirect` al dashboard; `tecnico` y `usuario` no ven el enlace «Dashboard SLA» y el acceso directo muestra `forbidden` sin métricas; `supervisor` y `admin` ven el enlace y acceden; el guard es cosmético y un `403` del backend prevalece. Cubre HU07-RF-043, HU07-SC-008.

### Implementation for User Story 5

- [x] T065 [US5] Crear `frontend/src/components/sla-dashboard/DashboardErrorState.vue` con `variant: 'full' | 'warning' | 'forbidden'`, `message` y `onRetry`: error de carga («No se pudo cargar el dashboard. Inténtalo de nuevo.», `role="alert"`, botón de reintento), aviso de desactualización («No se pudieron actualizar los datos. Se muestran los últimos datos disponibles.», `role="status"`, reintento) y `forbidden` («No tienes permiso para acceder a este dashboard.», sin métricas). Cubre HU07-RF-046, HU07-RF-047, HU07-RF-048.
- [x] T066 [US5] Ampliar `frontend/src/components/sla-dashboard/DashboardEmptyState.vue` con las variantes `sin-sla` («No hay tickets con SLA en el periodo seleccionado.») y `sin-vencidos` («No hay tickets vencidos en el periodo seleccionado.»), manteniendo `periodo` y `filtros` y sus acciones; cada variante con mensaje propio y accesible. Cubre HU07-RF-039, HU07-RF-048.
- [x] T067 [US5] Extender `frontend/src/stores/slaDashboard.ts` con el ciclo de frescura: `startPolling()` cada 60 s sin solapar peticiones, pausa con `document.hidden`, refresco al recuperar foco/visibilidad, `refresh()` manual que conserva filtros, `stale = true` cuando falla una actualización con datos previos (sin borrar `data`), error sin datos en la carga inicial, `lastFetchedAt` y redirección a `/login?redirect=…` con la query de filtros ante `401`, siguiendo el patrón de `frontend/src/stores/workQueue.ts` sin modificarlo. Cubre HU07-RF-044 a HU07-RF-048.
- [x] T068 [US5] Integrar en `frontend/src/views/SlaDashboardPage.vue` los estados de `DashboardErrorState` y las variantes de `DashboardEmptyState`, con prioridad visual: error inicial > forbidden > periodo sin tickets > filtros sin resultados > sin SLA/sin vencidos; mostrar «Última actualización: dd/mm/aaaa hh:mm» desde `meta.generated_at` con `formatMadridDateTime`, botón de actualización manual y contenedores `role="alert"`/`aria-live` sin duplicar anuncios. Cubre HU07-RF-044 a HU07-RF-048, HU07-RF-050.
- [x] T069 [US5] Añadir a `frontend/src/router/index.ts` el guard global `router.beforeEach` que lea `getStoredUserRole()` y `getAccessToken()`: sin token → `{ name: 'login', query: { redirect: to.fullPath } }`; rol fuera de `meta.requiresRoles` → mostrar el estado `forbidden` (sin revelar datos) o redirigir a una ruta neutra, nunca a `/cola-de-trabajo` si el rol no puede usarla; el guard no altera la navegación de `/cola-de-trabajo`, `/tickets/:id` ni `/login`. Cubre HU07-RF-043, HU07-SC-008.
- [x] T070 [US5] Modificar `frontend/src/components/layout/AppHeader.vue` para mostrar el enlace «Dashboard SLA» solo si `getStoredUserRole()` es `supervisor` o `admin`, sin cambiar el enlace existente «Mesa de ayuda» ni el comportamiento de `NotificationBell`. Cubre HU07-RF-043, HU07-RF-050.

**Checkpoint**: Todos los estados y la frescura están diferenciados; el acceso por rol se bloquea en servidor y se refleja en cliente; ninguna situación de error se presenta como dashboard vacío.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Rendimiento, accesibilidad y no regresión de HU-04, HU-05 y HU-06.

- [x] T071 [P] Escribir en `backend/tests/integration/test_sla_dashboard_performance.py` la prueba de rendimiento: cargar por lotes 10.000 tickets en el periodo (con variedad de prioridades, categorías, SLA y finalizaciones), medir el snapshot completo y verificar p95 < 300 ms de servidor (constitución) y el tiempo de respuesta de la API; el objetivo de < 3 s extremo a extremo (HU07-SC-002) se valida manualmente en `quickstart.md` §5 E8, conforme al protocolo de medición definido allí; repetir con PostgreSQL real cuando `TEST_DATABASE_URL` esté definido, sin truncar datos. Cubre HU07-RF-049, HU07-SC-002.
- [x] T072 [P] Escribir en `backend/tests/integration/test_sla_dashboard_regression.py` las pruebas de no regresión de HU-04/HU-05/HU-06: `GET /api/v1/me/work-queue` conserva contrato, estados y cabeceras; el dashboard no crea entradas en `ticket_timeline_entries` ni modifica `tickets` (comparar conteos y `updated_at` antes/después); `ensure_assignee_consistency` y las entradas `assignee_change` siguen intactas; el router del dashboard solo expone métodos `GET`; la cabeza de Alembic sigue en `0004_assignee_changes_notifications`; `docker-compose.yml` no contiene servicios nuevos. Cubre HU07-RF-002, HU07-RF-052, HU07-SC-008, HU07-SC-014.
- [x] T073 [P] Escribir en `frontend/tests/unit/slaDashboardRegression.spec.ts` las pruebas de no regresión de frontend: las rutas `/cola-de-trabajo`, `/tickets/:id` y `/login` siguen resolviendo y no requieren rol de supervisor; `useWorkQueueStore` conserva su estado y acciones; `api/slaDashboard.ts` no expone métodos de escritura; `AppHeader` mantiene «Mesa de ayuda» y `NotificationBell` para un técnico. Cubre HU07-RF-002, HU07-RF-043.
- [x] T074 [P] Escribir en `frontend/tests/components/SlaDashboardAccessibility.spec.ts` las pruebas `axe-core` sin violaciones para `SlaDashboardPage`, `SlaDashboardFilters`, `ComplianceMatrix`, `SemaphoreBadge`, `SemaphoreLegend`, `TechnicianRanking`, `DashboardEmptyState` y `DashboardErrorState`; comprobar foco visible, etiquetas asociadas, `<caption>`/`scope`, `aria-live` y que el semáforo se entiende sin color. Cubre HU07-RF-050, HU07-SC-007.
- [x] T075 [P] Escribir en `backend/tests/integration/test_sla_dashboard_concurrency.py` una prueba de concurrencia real sobre PostgreSQL (marcador `postgres`) que ejecute lecturas del dashboard mientras se escriben tickets y cambios de estado, comprobando que no hay lecturas sucias, ni errores, ni escrituras en `ticket_timeline_entries`; cubre la constitución IV (concurrencia) y HU07-RF-052.
- [x] T076 Ejecutar la validación final: `python -m pytest -q` desde `backend/`, `npm run test` y `npm run build` desde `frontend/`, confirmar `alembic heads` = `0004_assignee_changes_notifications`, `docker compose config` sin cambios y recorrer `specs/007-dashboard-cumplimiento-sla/quickstart.md` §5 (E1–E8), registrando evidencias de acceso por rol, conciliación de totales, semáforo, ranking, filtros, frescura, rendimiento y solo lectura. Cubre HU07-SC-001, HU07-SC-002, HU07-SC-005, HU07-SC-008, HU07-SC-012, HU07-SC-013.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: sin dependencias; puede empezar de inmediato.
- **Foundational (Phase 2)**: depende de Setup y **bloquea todas las historias**.
- **US1 (Phase 3)**: depende de Foundational. Es el MVP y aporta la proyección SQL compartida, la agregación y el endpoint base.
- **US2 (Phase 4)**: depende de US1 (reutiliza la proyección `poblacion` de T023, la agregación de T024 y el endpoint de T026), pero su verificación es independiente (bloque `ranking`).
- **US3 (Phase 5)**: depende de US1/T026 (endpoint) y US2/T038 (snapshot completo); añade filtros y `/options`.
- **US4 (Phase 6)**: depende de US1 (resumen y matriz) y de Foundational/T009 (umbrales); es una capa de presentación sobre métricas ya calculadas.
- **US5 (Phase 7)**: depende de US1–US4 para mostrar estados sobre secciones reales.
- **Polish (Phase 8)**: depende de todas las historias deseadas.

### User Story Dependencies

| Historia | Prioridad | Depende de | Independientemente verificable |
|---|---|---|---|
| US1 — Matriz por prioridad y categoría | P1 | Foundational | Sí: `GET /sla-dashboard` + resumen/matriz |
| US2 — Ranking de técnicos | P1 | US1 (proyección y endpoint) | Sí: bloque `ranking` y conciliación con `summary.overdue_count` |
| US3 — Filtros | P2 | US1/T026, US2/T038 | Sí: matriz, totales y ranking con el mismo subconjunto |
| US4 — Semáforo | P2 | US1, Foundational/T009 | Sí: bandas, leyenda e independencia del color |
| US5 — Estados, errores y frescura | P3 | US1–US4 | Sí: estados diferenciados, sondeo y permisos de acceso |

### Within Each User Story

1. Tests primero y en rojo.
2. Servicio/proyección antes que endpoint.
3. Esquemas antes de serializar respuestas.
4. Componentes hoja (`MatrixCell`, `SemaphoreBadge`) antes que contenedores (`ComplianceMatrix`, `SlaDashboardPage`).
5. Integración en la página al final de cada historia.
6. No avanzar a la siguiente prioridad hasta que la historia actual pase su prueba independiente.

### Parallel Opportunities

- **Setup**: T001, T002 y T003 son paralelizables (T004 depende de revisar `backend/requirements.txt`).
- **Foundational**: T005, T006, T007, T008 (tests en archivos distintos) y T012, T014, T015 (archivos frontend distintos) pueden ir en paralelo; T013 depende de los tipos de T012 y T009–T011/T017 son secuenciales por dependencia de contratos.
- **US1**: T018, T019, T020, T021 y T022 en paralelo; tras T023–T026, los componentes T028, T029, T030 pueden ir en paralelo y T031–T033 en secuencia.
- **US2**: T034, T035 y T036 en paralelo; T037–T040 en secuencia.
- **US3**: T041, T042 en paralelo; T043 es secuencial sobre el store; T044–T047 backend y T048–T051 frontend pueden solaparse por archivos distintos.
- **US4**: T052, T053 y T054 en paralelo; T055–T060 en secuencia de dependencias visuales.
- **US5**: T061, T062 y T064 en paralelo; T063 es secuencial sobre el store; T065–T070 en secuencia.
- **Polish**: T071, T072, T073, T074 y T075 en paralelo; T076 al final.

### Parallel Example: User Story 1

```bash
# Lanzar en paralelo las pruebas de US1 (archivos distintos)
Task: "T018 [US1] Pruebas unitarias de fórmulas en backend/tests/unit/test_sla_dashboard_math.py"
Task: "T019 [US1] Pruebas de integración del endpoint en backend/tests/integration/test_sla_dashboard.py"
Task: "T020 [US1] Pruebas de SlaSummary en frontend/tests/components/SlaSummary.spec.ts"
Task: "T021 [US1] Pruebas de ComplianceMatrix en frontend/tests/components/ComplianceMatrix.spec.ts"
Task: "T022 [US1] Pruebas base de SlaDashboardPage en frontend/tests/components/SlaDashboardPage.spec.ts"
```

---

## Implementation Strategy

### MVP First (US1 Only)

1. Completar Phase 1 (Setup) y Phase 2 (Foundational).
2. Implementar US1 (Phase 3): proyección SQL, agregación, endpoint `GET /api/v1/sla-dashboard`, resumen y matriz.
3. **PARAR y VALIDAR**: ejecutar la prueba independiente de US1 con los tickets de control de `quickstart.md` §4; comprobar conciliación de celdas y totales y ausencia de escrituras.
4. Desplegar/demostrar si el MVP es suficiente.

### Incremental Delivery

1. Setup + Foundational → base lista.
2. US1 → matriz y resumen (MVP).
3. US2 → ranking y conciliación de vencidos.
4. US3 → filtros combinables y opciones.
5. US4 → semáforo, leyenda y accesibilidad no dependiente del color.
6. US5 → estados, errores, frescura y guard de cliente.
7. Polish → rendimiento, regresión y validación end-to-end.
8. Cada incremento se prueba de forma independiente y no altera los anteriores.

### Parallel Team Strategy

1. El equipo completa Setup + Foundational.
2. Después: Developer A → US1 (backend de cálculo); Developer B → componentes de presentación de US1 y US4 (archivos distintos); Developer C → pruebas de contrato y permisos.
3. US2 y US3 se abordan al cerrar US1; US4 y US5 al cerrar las anteriores. Las tareas `[P]` de test y de componentes permiten solapar sin conflictos de archivo.

---

## Trazabilidad RF / CA / SC

### Requisitos funcionales → tareas

| Requisitos funcionales | Fase / tareas |
|---|---|
| HU07-RF-001 a HU07-RF-005 (vista, solo lectura, población, SLA histórico, resumen) | T003, T010, T023, T025, T026, T028, T032, T033 |
| HU07-RF-006 a HU07-RF-018 (métricas, totales, etiquetas, primera finalización, sin SLA, orden) | T018–T021, T024, T031, T044 |
| HU07-RF-019 a HU07-RF-026 (ranking y privacidad) | T034–T040 |
| HU07-RF-027 a HU07-RF-037 (filtros, opciones, sesión, resumen de filtros) | T041–T051 |
| HU07-RF-038 a HU07-RF-042 (semáforo y leyenda) | T005, T009, T052–T060 |
| HU07-RF-043 (permisos supervisor/admin) | T007, T011, T064, T069, T070 |
| HU07-RF-044 a HU07-RF-048 (instantánea, frescura, errores y estados) | T016, T017, T061–T068 |
| HU07-RF-049 (rendimiento) | T071 |
| HU07-RF-050 (es-ES, Madrid, WCAG 2.1 AA) | T008, T014, T028, T031, T039, T049, T053, T056, T057, T068, T074 |
| HU07-RF-051 (conciliación de totales y ranking) | T019, T024, T035, T038, T072 |
| HU07-RF-052 (solo lectura y fuentes históricas) | T001–T004, T023, T072 |

### Criterios de aceptación de la HU-07 → tareas

| Criterio de aceptación | Tareas |
|---|---|
| Vista con métricas por prioridad (Crítica, Alta, Media, Baja) y por categoría | T019, T021, T024, T031, T032 |
| Cada combinación muestra % dentro de plazo, tiempo medio y vencidos | T018, T019, T020, T021, T030, T031 |
| Ranking de técnicos por volumen y desempates | T034–T040 |
| Filtros por rango de fechas, categoría y prioridad | T041–T051 |
| Semáforo verde/ámbar/rojo por umbrales | T005, T009, T052–T060 |
| Solo supervisores y administradores acceden | T007, T011, T064, T069, T070 |
| Distinción entre sin datos, sin resultados y error | T050, T061–T068 |
| No regresión de HU-04, HU-05 y HU-06 | T072, T073, T076 |

### Criterios de éxito → tareas

| Criterio de éxito | Tareas |
|---|---|
| HU07-SC-001, HU07-SC-003, HU07-SC-009, HU07-SC-015, HU07-SC-016 | T018, T019, T024 |
| HU07-SC-002 | T071, T076 |
| HU07-SC-004, HU07-SC-014 | T034, T035, T037, T038, T072 |
| HU07-SC-005 | T041, T043, T048, T051 |
| HU07-SC-006, HU07-SC-007 | T005, T009, T052, T053, T054, T074 |
| HU07-SC-008 | T007, T011, T064, T069, T072 |
| HU07-SC-012 | T050, T061, T062, T076 |
| HU07-SC-013 | T063, T067, T068, T076 |

> HU07-BN-004 y HU07-BN-005 (en el origen de la historia figuraban como criterios de usabilidad provisionales) son métricas de usabilidad post-lanzamiento (spec.md «Resultados de Negocio»); no se verifican de forma automatizada.

---

## Notes

- `[P]` implica archivos distintos y ninguna dependencia pendiente; no marcar dos tareas `[P]` sobre el mismo archivo.
- Las pruebas se escriben y se comprueban en rojo antes de la implementación de su historia.
- No se crean migraciones ni se modifican `tickets`, `ticket_timeline_entries`, `users`, `priorities` o `categories`.
- No se modifican `docker-compose.yml`, `backend/app/services/work_queue.py`, `backend/app/services/ticket_workflow.py`, `backend/app/services/assignee_change.py` ni los componentes de `frontend/src/components/work-queue/`.
- Cada cifra del dashboard debe poder explicarse a partir de los tickets de la población y de `HU07-RN-*`; cualquier cálculo manual o ajuste queda prohibido.
- Confirmar en cada checkpoint que `GET /api/v1/me/work-queue` y las rutas de HU-05/HU-06 siguen respondiendo igual.

---

## Phase 9: Convergence

**Purpose**: Cerrar las diferencias detectadas entre la especificación/plan y el código vigente. No modifica ni renumera ninguna tarea previa.

- [ ] T077 Mostrar la matriz de cumplimiento siempre que la población filtrada tenga tickets, incluido el caso en que todos carezcan de SLA: conservar las filas y celdas con «Sin datos» neutro en porcentaje y tiempo medio junto al conteo «Sin SLA», y mantener el aviso informativo de periodo sin SLA como complemento en lugar de sustituir la matriz, en `frontend/src/views/SlaDashboardPage.vue` per HU07-RF-016 / HU07-RF-011 / HU07-RN-07 (partial)
- [ ] T078 Derivar la instantánea completa, incluidos `technician_name`, `team` e `is_active` del ranking, de la única proyección `poblacion`: ampliar la consulta de población con los joins de `users` necesarios y eliminar la segunda consulta a `users` en `build_ranking` de `backend/app/services/sla_dashboard.py` per plan: Cálculo de SLA y agregaciones (plan.md §1) / research.md R6 (contradicts)

## Phase 10: Convergence

**Purpose**: Segunda pasada de convergencia. Los hallazgos de la primera (T077–T078, Phase 9) siguen pendientes de `/speckit.implement`; esta pasada añade únicamente el hallazgo nuevo detectado (presupuesto de rendimiento de la constitución).

- [ ] T079 CRITICAL Reducir la latencia del snapshot de 10.000 tickets para que el p95 de servidor quede por debajo de 300 ms y `backend/tests/integration/test_sla_dashboard_performance.py::test_snapshot_meets_server_latency_budget` pase en verde (medición actual: p95 ≈ 322 ms): abaratar la consulta de población y la agregación en Python en `backend/app/services/sla_dashboard.py` — por ejemplo eliminando la segunda consulta a `users` de `build_ranking` (ver T078) y minimizando la materialización intermedia en `load_population`/`_derive_ticket`/`build_ranking` — sin alterar resultados, contratos ni el comportamiento de solo lectura per Constitution (restricción Rendimiento: p95 < 300 ms) / plan: Performance Goals / HU07-RF-049 (partial)

## Phase 11: Convergence

**Purpose**: Tercera pasada de convergencia, ejecutada tras la implementación de T077–T079 y la validación con la suite completa en verde (backend 416 pruebas sobre SQLite, frontend 268 pruebas, rendimiento sobre PostgreSQL real). T077, T078 y T079 están resueltos y verificados en el código vigente; esta pasada añade únicamente el defecto detectado al ejecutar las pruebas marcadas `postgres` contra el PostgreSQL real del entorno (`docker compose up`), que quedaban omitidas en la ejecución local sobre SQLite.

- [ ] T080 Corregir la prueba de concurrencia de T075 para que pueda pasar sobre PostgreSQL real: en `backend/tests/integration/test_sla_dashboard_concurrency.py::test_concurrent_reads_and_writes_are_consistent` la aserción `len(results) == READERS` es imposible de satisfacer porque los `WRITERS` también añaden su resultado (`None`) a la lista `results` de `_run_concurrently`, de modo que `len(results)` es siempre `READERS + WRITERS` (7 ≠ 4); separar los resultados por tipo de worker (los lectores devuelven listas de conteos y los escritores `None`) y asertar sobre los resultados de los lectores exclusivamente, manteniendo `errors == []`, la reconciliación de `overdue_count` y las comprobaciones de no escritura; verificar su ejecución con `TEST_DATABASE_URL` apuntando a PostgreSQL 16 real, ya que quedó marcada como completada sin haber corrido nunca en verde (se omite sobre SQLite) per Constitution IV (concurrencia) / T075 / HU07-RF-052 (contradicts)

## Phase 12: Convergence

**Purpose**: Cuarta pasada de convergencia. El código vigente supera la suite backend (416 pruebas en verde sobre SQLite; 8 omitidas por requerir PostgreSQL real), la suite frontend (268 en verde) y el build; la cabeza de Alembic sigue en `0004_assignee_changes`, no hay migraciones nuevas y no se detectan cambios de comportamiento en HU-04/HU-05/HU-06. T077, T078 y T079 están resueltos y verificados; esta pasada añade únicamente el trabajo que sigue pendiente: T080 no está completado y la prueba de concurrencia no puede pasar sobre PostgreSQL real.

- [ ] T081 CRITICAL Completar el trabajo pendiente de T080: corregir y verificar la prueba de concurrencia de T075 para que pueda pasar sobre PostgreSQL real. En `backend/tests/integration/test_sla_dashboard_concurrency.py::test_concurrent_reads_and_writes_are_consistent`, `_run_concurrently` añade el resultado de los `WRITERS` (`None`) a `results`, de modo que `len(results) == READERS` es imposible (7 ≠ 4); separar los resultados por tipo de worker y asertar solo sobre los lectores, manteniendo `errors == []`, la reconciliación `summary.overdue_count == ranking.overdue_total` y la comprobación de que el dashboard no escribe en `ticket_timeline_entries`; ejecutar la prueba con `TEST_DATABASE_URL` apuntando a PostgreSQL 16 real y confirmar que pasa en verde, ya que sigue omitida sobre SQLite per Constitution IV (concurrencia real sobre PostgreSQL) / T075 / T080 / HU07-RF-052 (contradicts)

## Phase 13: Convergence

**Purpose**: Quinta pasada de convergencia, ejecutada tras verificar T077–T081 en el código vigente con la suite backend sobre SQLite (416 pruebas) y PostgreSQL 16 real (424 pruebas), la suite frontend (268 pruebas), el presupuesto de latencia p95 < 300 ms y la ausencia de migraciones o cambios en HU-04/HU-05/HU-06. Esta pasada no renumera tareas previas y añade únicamente dos contradicciones front-end detectadas entre la especificación/plan/tareas y el código: el guard de cliente no comprueba el rol y la leyenda del semáforo no incluye iconos. Uno y otro tienen la defensa o la información equivalente en otra capa (backend `403`, texto de la leyenda), pero incumplen requisitos explícitos y trazados.

- [ ] T082 MEDIUM Completar el guard de cliente por rol en `frontend/src/router/index.ts`: además de `getAccessToken()`, leer `getStoredUserRole()` (de `@/api/client`) y, cuando el rol no esté en `meta.requiresRoles` (`supervisor`, `admin`), bloquear la navegación a `/dashboard-sla` sin revelar datos, mostrando el estado `forbidden` de `SlaDashboardPage.vue` o redirigiendo a una ruta neutra que ese rol sí pueda usar; nunca redirigir a `/cola-de-trabajo` si el rol no puede usarla. Conservar la redirección a `/login?redirect=…` cuando falte token y dejar intactas las rutas `/cola-de-trabajo`, `/tickets/:id` y `/login`. Actualizar `frontend/tests/components/SlaDashboardAccess.spec.ts`, que hoy fija el comportamiento incorrecto («con token el guard permite entrar al dashboard»), con casos para un `tecnico`/`usuario` con token válido: no se alcanza la vista con métricas y se presenta `forbidden` o una ruta permitida; mantener la prueba de que un `403` del backend prevalece sobre el rol cosmético del token per plan: interfaz de dashboard (plan.md §5, l.122) / contracts/frontend-components.md §1.1 (l.31–41) / T069 / HU07-RF-043 / HU07-SC-008 (contradicts)
- [ ] T083 MEDIUM Añadir los iconos de lucide a la leyenda del semáforo en `frontend/src/components/sla-dashboard/SemaphoreLegend.vue`: reutilizar `SEMAPHORE_ICON` (y, si procede, `SEMAPHORE_LABEL`) de `frontend/src/utils/slaStyles.ts` para que cada una de las cuatro bandas (`verde`, `ambar`, `rojo`, `sin_datos`) muestre color + icono + texto, con el icono `aria-hidden="true"` y sin hardcodear umbrales (siguen viniendo de `props.thresholds`). Actualizar `frontend/tests/components/SemaphoreLegend.spec.ts` para comprobar de verdad los iconos renderizados por banda, no solo el texto de las etiquetas, de modo que la prueba escrita en T054 deje de ser una comprobación parcial per T054 (l.182) / HU07-RF-040 / HU07-RF-042 / HU07-SC-007 / HU07-RN-11 (contradicts)

## Phase 14: Convergence

**Purpose**: Sexta pasada de convergencia, ejecutada tras verificar T077–T083 en el código vigente con la suite backend (416 pruebas sobre SQLite, 8 omitidas por PostgreSQL real) y la suite frontend (35 + 270 pruebas) en verde, sin migraciones nuevas ni cambios en HU-04/HU-05/HU-06. No renumera tareas previas y añade únicamente el trabajo que sigue pendiente: una denegación `403` durante la actualización aún deja ver agregados, el reintento de un error inicial no recarga con skeleton, el contrato no refleja la nulabilidad de `ranking.unassigned`, la acción «Ampliar fechas» restablece el rango por defecto en lugar de ampliarlo y el orden del ranking no tiene desempate final por identidad.

- [ ] T084 HIGH Impedir que un `403 forbidden` durante una actualización siga mostrando agregados: en `frontend/src/stores/slaDashboard.ts` (catch de `fetchDashboard`, l.281–294) tratar `mapped.kind === 'forbidden'` como denegación de acceso y no como degradación `stale` — conservar el error, vaciar `data`/`meta`/`stale` — y en `frontend/src/views/SlaDashboardPage.vue` (l.33–41, 119–162) hacer que `fatalError` y `fatalVariant` rendericen el estado `forbidden` sin filtros, resumen, matriz ni ranking; el backend sigue siendo la defensa real y el `401` mantiene su redirección a login. Añadir casos en `frontend/tests/stores/slaDashboard.spec.ts` y `frontend/tests/components/SlaDashboardAccess.spec.ts` con datos previos y `ApiClientError('forbidden', …, 403)` durante `refresh()`/sondeo: no queda `data`, no se renderiza ninguna cifra y aparece «No tienes permiso para acceder a este dashboard.» per plan: autorización en servidor (plan.md:109, l.122) / HU07-RN-13 «El acceso se deniega sin revelar datos agregados ni la existencia de métricas» / HU07-RF-043 / caso límite «Un técnico o un usuario intenta acceder al dashboard» (spec.md:463) / T082 (contradicts)
- [ ] T085 MEDIUM Hacer que «Reintentar» desde un error de carga inicial vuelva a cargar de verdad: `retry()` de `frontend/src/views/SlaDashboardPage.vue` (l.48–50) llama a `store.refresh()`, que usa `fetchDashboard({ silent: true })` y deja `loading === false` con `data === null` (`frontend/src/stores/slaDashboard.ts`: l.262–267, 328–330), por lo que durante el reintento no aparece ni el skeleton ni el error ni un estado vacío coherente; cambiar el reintento fatal para ejecutar una carga no silenciosa (`store.load()` / `fetchDashboard()`) que mantenga el skeleton hasta la respuesta y restaure el error diferenciado si vuelve a fallar, sin tocar el reintento con datos previos (que sí debe conservarlos con aviso `stale`). Añadir una prueba de estados que haga clic en reintento con `data === null` y verifique que no se muestra un dashboard vacío ni un área en blanco mientras la petición está pendiente per HU07-RN-12 «Si la carga inicial falla… se muestra un error diferenciado» / HU07-RN-16 «Un error nunca se presenta como un dashboard vacío» / caso límite «Se produce un fallo al cargar el dashboard» (spec.md:460) / US5 #2 (missing)
- [ ] T086 MEDIUM Corregir la nulabilidad de `ranking.unassigned` en `specs/007-dashboard-cumplimiento-sla/contracts/sla-dashboard.openapi.yaml` (l.394–396): hoy es un `$ref` sin `nullable: true` en un documento `openapi: 3.0.3`, por lo que el esquema no admite `null` aunque su propia descripción, `data-model.md` (l.121: «`technician_id` (UUID o `NULL`), … `NULL` = fila «Sin asignar»») y la implementación (`backend/app/services/sla_dashboard.py`: l.904–911 devuelve `None`, verificado en `backend/tests/integration/test_sla_dashboard_ranking.py`:81) sí lo permiten. Expresar la nulabilidad de forma válida en OAS 3.0 (p. ej. `allOf` con `$ref` y `nullable: true` a nivel de propiedad) y añadir/ajustar una validación ejecutable del contrato frente a una respuesta sin vencidos sin responsable per Constitution IV (contratos primero y verificables) / HU07-RN-08 / HU07-SC-014 (contradicts)
- [ ] T087 LOW Hacer que la acción «Ampliar fechas» amplíe realmente el rango: `frontend/src/components/sla-dashboard/DashboardEmptyState.vue` (l.40–45) ofrece esa acción para el estado «periodo», pero `frontend/src/views/SlaDashboardPage.vue:60–62` la enlaza con `store.resetFilters()`, que vuelve a los últimos 30 días por defecto (`frontend/src/stores/slaDashboard.ts`: l.18, 353–360); si el periodo consultado ya era de 30 días o más, la acción no amplía o incluso estrecha el rango. Implementar un manejador dedicado que ensanche el rango vigente (p. ej. duplicarlo o extenderlo respecto al inicio actual) manteniendo filtros y URL sincronizados, preservar `resetFilters()` para la acción «Limpiar filtros» y actualizar `frontend/tests/components/SlaDashboardStates.spec.ts` y la prueba del store para comprobar que `desde`/`hasta` crecen tras la acción per caso límite «No hay tickets en el periodo seleccionado… acción para ampliar el rango de fechas» (spec.md:441) / HU07-RN-16 (l.340) / HU07-RF-048 / T050 (partial)
- [ ] T088 LOW Garantizar el desempate final y estable del ranking cuando coinciden nombre, equipo, volumen y retraso: `backend/app/services/sla_dashboard.py:925–932` ordena por `-overdue_count`, `-avg_delay_seconds`, `technician_name` y `team`, y se detiene ahí, sin `technician_id` como último criterio; la consulta de población no impone `ORDER BY`, de modo que dos usuarios distintos con el mismo nombre y equipo pueden cambiar de posición según el orden de filas de la BD. Añadir `entry.technician_id` como último criterio de ordenación (con manejo de `None`) y una prueba de integración que cree dos técnicos con nombre, equipo, cuenta y retraso idénticos y compruebe un orden reproducible entre peticiones sin que se fusionen sus métricas per HU07-RN-08 «El orden debe ser estable» / caso límite «Dos técnicos comparten nombre… se distinguen por equipo y por su identidad como usuario» (spec.md:457) / data-model.md:125 / contract:391 (partial)

---

## Phase 15: Convergence

**Purpose**: Séptima pasada de convergencia, ejecutada tras verificar T077–T088 en el código vigente con la suite backend (420 pruebas en verde, 8 omitidas por PostgreSQL real) y la suite frontend (278 pruebas en verde), con el presupuesto p95 < 300 ms en verde, sin migraciones nuevas ni cambios en HU-04/HU-05/HU-06. No renumera tareas previas y añade el trabajo pendiente detectado: un rango de fechas sin resultados elige el estado vacío equivocado, el contrato OpenAPI no declara `Vary: Authorization`, la verificación de accesibilidad ignora violaciones no críticas y contraste, y varias pruebas no ejercitan realmente los requisitos que nombran.

- [ ] T089 HIGH Corregir `emptyVariant` en `frontend/src/stores/slaDashboard.ts` (l.188-206): hoy decide entre `'periodo'` y `'filtros'` usando solo `hasDimensionFilters`, mientras `hasActiveFilters` (que sí incluye `desde`/`hasta`) queda sin uso, de modo que un rango de fechas personalizado sin resultados muestra «No hay tickets en el periodo seleccionado… Ampliar fechas» en lugar de «No hay resultados para los filtros seleccionados… Limpiar filtros». Incluir las fechas personalizadas en la decisión, manteniendo `'periodo'` solo para la configuración por defecto, y actualizar `frontend/tests/components/SlaDashboardStates.spec.ts` y `frontend/tests/stores/slaDashboard.spec.ts` con un caso de rango `desde`/`hasta` sin tickets per US3/AC8 / HU07-RF-034 / HU07-RN-16 (partial)
- [ ] T090 MEDIUM Declarar `Vary: Authorization` en `specs/007-dashboard-cumplimiento-sla/contracts/sla-dashboard.openapi.yaml` para las respuestas 200/401/403/422 de `GET /sla-dashboard` y `GET /sla-dashboard/options` (o en las respuestas reutilizables `$ref`), reflejando el comportamiento real de `backend/app/api/v1/sla_dashboard.py:30-38` y `backend/app/core/errors.py:48-50`, y añadir una validación ejecutable del encabezado en `backend/tests/contract/test_sla_dashboard_contract.py`, hoy inexistente per plan: validación y errores (plan.md:83) / Constitution IV (contratos primero y verificables) / T007 / T019 / T026 / T046 / T047 (partial)
- [ ] T091 MEDIUM Endurecer la verificación de accesibilidad en `frontend/tests/components/SlaDashboardAccessibility.spec.ts` (l.37-46): dejar de filtrar solo `impact === 'critical'` y exigir ausencia de violaciones `serious`/`moderate`/`critical` para los componentes de T074; sustituir la desactivación de `color-contrast` (justificada sin prueba) por una comprobación ejecutable de los pares texto/fondo de `SEMAPHORE_BADGE_CLASS` en `frontend/src/utils/slaStyles.ts:49-54` frente a WCAG 2.1 AA, o documentar y verificar la equivalencia per T074 / HU07-RF-050 / Constitution IV y V (partial)
- [ ] T092 LOW Completar `frontend/tests/components/SemaphoreBadge.spec.ts` (l.23-56) para que las bandas `ambar`, `rojo` y `sin_datos` comprueben también la presencia del icono `svg` y el `aria-label` completo con el porcentaje formateado, como ya hace la prueba de `verde` (l.7-21), de modo que «color + icono + texto» quede verificado para las cuatro bandas per T053 / HU07-RF-040 / HU07-SC-007 (partial)
- [ ] T093 LOW Aplicar formato numérico es-ES a los recuentos enteros de `frontend/src/components/sla-dashboard/SlaSummary.vue`, `MatrixCell.vue` y `TechnicianRanking.vue` mediante una función reutilizable en `frontend/src/utils/format.ts` (p. ej. `Intl.NumberFormat('es-ES')`), de modo que un total de 10000 se presente como «10.000», y añadir pruebas en `frontend/tests/unit/slaDashboardFormat.spec.ts` y en los specs de componentes per HU07-RN-14 / HU07-RF-050 / plan: interfaz de dashboard (plan.md:131) (partial)
- [ ] T094 LOW Reescribir `backend/tests/integration/test_sla_dashboard_filters.py::test_both_period_bounds_are_inclusive` (l.26-37) para crear tickets de control exactamente en las fechas `desde` y `hasta` (días naturales `Europe/Madrid`) y asertar que ambos aparecen en la población y en el total, en lugar de comprobar únicamente que un día sin tickets no inventa datos per T041 / US3/AC2 / HU07-RN-02 (partial)
- [ ] T095 LOW Reescribir `backend/tests/integration/test_sla_dashboard_filters.py::test_dst_boundary_is_a_valid_period` (l.156-166) para sembrar tickets a ambos lados del cambio de hora de `2026-03-29` en `Europe/Madrid` y verificar que ninguno se duplica ni se pierde en la población, conservando la comprobación de los filtros efectivos per caso límite «El rango cruza un cambio de hora oficial» (spec.md:456) / HU07-RN-02 / T041 (partial)
- [ ] T096 LOW Añadir cobertura ejecutable en `backend/tests/unit/test_sla_dashboard_math.py` o `backend/tests/integration/test_sla_dashboard_ranking.py` para la rama de ticket heredado sin entradas de línea temporal: un vencido finalizado sin `first_author_id` se atribuye al `assignee_id` vigente y, si tampoco hay responsable, a «Sin asignar», ejercitando los `coalesce` de `backend/app/services/sla_dashboard.py:300-305,480-482` que hoy no cubre ninguna prueba per HU07-RN-09 / T023 / T034 (missing)

