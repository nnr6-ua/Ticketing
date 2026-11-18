# Implementation Plan: Dashboard de cumplimiento de SLA (HU-07)

**Branch**: `hu-07-dashboard-sla` | **Date**: 2026-11-15 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/007-dashboard-cumplimiento-sla/spec.md`

**Estado**: plan generado el 2026-11-15 contra las fuentes implementadas en `backend/` y `frontend/` y contra las aclaraciones de la especificación (sesión 2026-11-14). Los artefactos de Fase 0 y Fase 1 (`research.md`, `data-model.md`, `contracts/` y `quickstart.md`) están sincronizados con este documento.

## Summary

HU-07 ofrece a **supervisores y administradores** un dashboard de **solo lectura** que agrega el cumplimiento de SLA por **prioridad y categoría**, con **semáforo verde/ámbar/rojo** (verde ≥ 90 %, ámbar 70 %–<90 %, rojo < 70 %) y un **ranking de técnicos con tickets vencidos** ordenado por volumen. La población son los tickets creados en el rango de fechas filtrado (por defecto, los últimos 30 días naturales en `Europe/Madrid`), y todas las secciones se calculan sobre la **misma instantánea** con los mismos filtros.

La funcionalidad es un consumidor puro de los datos existentes: usa la **primera finalización** derivada de la línea temporal append-only de HU-05 (primera entrada `status_change → 'resuelto'`; `tickets.finalized_at` solo refleja el estado actual y se limpia al reabrir), el **límite de SLA histórico** `tickets.sla_deadline` (HU04-RN-03 / HU08-RN-04), el responsable vigente `tickets.assignee_id` y el **`author_id` de la primera entrada `status_change → 'resuelto'`** de la línea temporal para aplicar la regla mixta de atribución (HU07-RN-09). **No hay migración, no hay tablas nuevas y no se toca ningún endpoint, servicio ni comportamiento de HU-04, HU-05 y HU-06.**

**Decisiones clave**:

| Punto solicitado | Decisión |
|---|---|
| Cálculo de SLA en BD | Una única consulta SQL (CTE `poblacion`) deriva por ticket: `atendido con SLA`, `dentro de plazo` (`primera_finalizacion <= sla_deadline`), `vencido` (finalizado fuera de plazo, o activo con `now() > sla_deadline`), `retraso` y `atribución`; agregación por prioridad/categoría/total y ranking en la capa de servicio sobre esa proyección |
| Instantánea coherente | Una sola sentencia SELECT en una transacción de lectura produce la proyección por ticket; todas las secciones (matriz, totales, ranking) se agregan de ella en memoria (≤ 10.000 filas) |
| Endpoints | `GET /api/v1/sla-dashboard` (snapshot completo con meta y umbrales) y `GET /api/v1/sla-dashboard/options` (opciones de filtro del periodo); solo GET, `Cache-Control: no-store` |
| Umbrales | Constantes de módulo en `backend/app/utils/sla.py` (`SLA_GREEN_THRESHOLD_PCT = 90.0`, `SLA_AMBER_THRESHOLD_PCT = 70.0`) + función pura `compliance_band()`; el backend las emite en `meta.thresholds` y el frontend renderiza lo recibido, sin duplicarlas |
| Permisos | Nueva dependencia `require_supervisor_or_admin` en `app/api/deps.py` (patrón `require_technician`); 403 `forbidden` para técnicos y usuarios; sin cambios en permisos existentes |
| Interfaz | Ruta `/dashboard-sla` con `SlaDashboardPage.vue`, store Pinia `slaDashboard` (patrón de `workQueue`: filtros en URL, sondeo ≤ 60 s, AbortController, degradación con datos previos) y componentes en `components/sla-dashboard/` |
| Esquema | **Cero migraciones**: solo lectura sobre el modelo vigente; `tzdata` se añade a `requirements.txt` para `zoneinfo` en Windows |

## Requisitos técnicos explícitos de la HU-07

Esta sección fija, de forma normativa para la implementación, las seis decisiones que la historia exige documentar de forma expresa. El detalle completo vive en `research.md` (justificación y alternativas), `data-model.md` (entidades y reglas) y `contracts/` (contratos HTTP y de componentes).

### 1. Cálculo de SLA y agregaciones (Backend / FastAPI + PostgreSQL) — CRÍTICO

**Decisión**: el cálculo es **una única consulta SQL de solo lectura** cuyo CTE `poblacion` proyecta cada ticket con sus métricas derivadas; el servicio `sla_dashboard.py` agrega esa proyección en Python (matriz, totales y ranking) sin volver a la base de datos.

**Fuentes de datos (sin modificar su estructura)**:

| Dato | Fuente | Por qué es válido |
|---|---|---|
| Fecha de creación | `tickets.created_at` (UTC, tz-aware) | Base del filtro de población (HU07-RN-02) |
| Límite de SLA histórico | `tickets.sla_deadline` (UTC, `NULL` = sin SLA) | Estampado en creación; `ck_tickets_sla_deadline_after_created` garantiza `> created_at`; nunca se reescribe (HU04-RN-03, HU08-RN-04) |
| Primera finalización | `ticket_timeline_entries` (append-only, **solo lectura**): primera entrada `status_change` con `to_status = 'resuelto'` ordenada por `(created_at, event_order, id)`; fallback `tickets.finalized_at` solo para tickets heredados sin línea temporal | Primer paso a «Resuelto» («Cerrado» siempre va precedido de «Resuelto»). La línea temporal conserva la primera finalización al reabrir (HU04-RN-13). `finalized_at` refleja el estado actual y se limpia al reabrir, por lo que **no** sirve como primera finalización |
| Estado actual | `tickets.status` | Determina activo (`abierto|en_progreso|pendiente_usuario`) vs finalizado |
| Responsable vigente | `tickets.assignee_id` | Atribución de vencidos en tickets activos (regla mixta) |
| Quién lo finalizó | `ticket_timeline_entries` (append-only, **solo lectura**): primera entrada con `event_type = 'status_change'` y `to_status = 'resuelto'`, ordenada por `(created_at, event_order, id)`, `author_id` | Historial inmutable de HU-05/HU-06; no se reescribe ni se altera. Fallback determinista si no existe entrada (tickets legados sin timeline): `tickets.assignee_id`; si tampoco hay, «Sin asignar» |
| Etiquetas históricas | `priorities.name/level/is_active`, `categories.name/is_active` vía FK inmutables del ticket | No hay endpoint que reasigne prioridad/categoría de un ticket, por lo que la FK conserva el valor de creación (HU07-RN-02); el flag `is_active` vigente solo alimenta el sufijo «(inactiva)» |

**Derivación por ticket (expresiones de la CTE, definidas por la especificación)**:

| Métrica derivada | Definición SQL (semántica) |
|---|---|
| `con_sla` | `sla_deadline IS NOT NULL` |
| `primera_finalizacion` | `finalized_at_timeline` si existe la primera entrada `status_change → 'resuelto'`; si no, `tickets.finalized_at` (ticket heredado); `NULL` si ninguna |
| `atendido` (primera finalización) | `primera_finalizacion IS NOT NULL` |
| `atendido_con_sla` (denominador de HU07-RN-04) | `atendido AND con_sla` |
| `dentro_de_plazo` (numerador) | `atendido_con_sla AND primera_finalizacion <= sla_deadline` (igualdad = dentro de plazo, HU07-RN-04) |
| `tiempo_respuesta_s` | `EXTRACT(EPOCH FROM (primera_finalizacion - created_at))` si `atendido_con_sla`; nunca negativo |
| `vencido` (HU07-RN-06) | `con_sla AND ((atendido AND primera_finalizacion > sla_deadline) OR (NOT atendido AND now() > sla_deadline))` |
| `retraso_s` | `EXTRACT(EPOCH FROM (now() - sla_deadline))` si vencido y activo; `EXTRACT(EPOCH FROM (primera_finalizacion - sla_deadline))` si vencido y atendido |
| `atribuido_a` (regla mixta HU07-RN-09) | Solo si `vencido`: `author_id` de la primera finalización si `atendido`; si no, `assignee_id`; si no, `NULL` («Sin asignar») |

La unión `LEFT JOIN LATERAL` con la primera entrada de finalización se limita a la página de población (≤ 10.000 tickets) y aprovecha `ix_timeline_ticket_created (ticket_id, created_at)`.

**Agregaciones (capa de servicio, desde la misma proyección)**:

- **Matriz** (`GROUP BY (priority_id, category_id)` con `category_id = NULL` ⇒ «Sin categoría»): `ticket_count`, `sin_sla_count`, `atendido_con_sla`, `dentro_de_plazo`, `vencido_count`, `cumplimiento_pct = Decimal(100 × dentro_de_plazo ÷ atendido_con_sla).quantize(0.1, ROUND_HALF_UP)`, `tiempo_medio_s = media de tiempo_respuesta_s`.
- **Totales por prioridad, por categoría y global**: mismas fórmulas recalculadas **desde los tickets subyacentes**, nunca promediando celdas (HU07-RF-015). Combinaciones sin tickets no aparecen; los totales siempre se muestran.
- **Ranking** (HU07-RN-08/09): sobre tickets `vencido = true`, atribución única por técnico; orden por `vencidos DESC`, desempate por `retraso_medio DESC` (valor exacto), luego `lower(name) ASC` y `team ASC`; fila separada «Sin asignar» al final; solo técnicos con ≥ 1 vencido, con `is_active` para el sufijo «(inactivo)».
- **Redondeo**: porcentajes con `Decimal.quantize(0.1, ROUND_HALF_UP)` (no `round()` de Python, que es bancario); el semáforo se evalúa sobre el valor redondeado (HU07-RN-15). Medias conservan precisión interna y se redondean al minuto solo en presentación.
- **Sin SLA**: se cuentan aparte (`sin_sla_count`), quedan fuera del porcentaje, la media y los vencidos (HU07-RF-014).
- **Instantánea coherente**: una sola sentencia SELECT en una transacción de lectura produce la proyección; el servicio la agrega de forma pura y determinista (HU07-RN-12). Se elige la agregación en Python sobre `GROUPING SETS` porque produce **un único camino de código idéntico en PostgreSQL y SQLite** (las pruebas funcionales usan SQLite), evita cuatro consultas separadas y es trivial para ≤ 10.000 filas.

**Referencias**: `research.md` (R1, R2, R6, R7), `data-model.md` §3–§4.

### 2. Endpoints de consulta y filtros

**Decisión**: dos endpoints `GET` bajo el nuevo router `app/api/v1/sla_dashboard.py`, montados en `api/v1/router.py`; el router solo orquesta (construye el objeto de filtros, llama al servicio, aplica `_no_store`).

| Endpoint | Devuelve | Filtros (query, combinables, lógica «O» dentro de dimensión y «Y» entre dimensiones) |
|---|---|---|
| `GET /api/v1/sla-dashboard` | Snapshot completo: `summary` (resumen global), `matrix` (combinaciones prioridad×categoría), `priority_totals`, `category_totals`, `ranking` (técnicos + «Sin asignar»), `meta` (instantánea, zona horaria, umbrales, filtros aplicados) | `desde`/`hasta` (fechas `YYYY-MM-DD` días naturales `Europe/Madrid`, ambos extremos incluidos; por defecto, últimos 30 días naturales calculados en servidor), `categorias` (CSV de UUID + valor especial `sin_categoria`), `prioridades` (CSV de niveles 1–4) |
| `GET /api/v1/sla-dashboard/options` | Opciones de filtro presentes en el periodo: categorías (con `is_active`, incluida la opción `sin_categoria` si existe) y prioridades presentes | `desde`/`hasta` |

**Validación y errores**: `desde > hasta` ⇒ `422 invalid_date_range` («La fecha inicial no puede ser posterior a la fecha final.») sin datos parciales; fechas mal formadas o niveles fuera de 1–4 ⇒ `422 invalid_request`; sin sesión ⇒ `401 not_authenticated`; rol no autorizado ⇒ `403 forbidden`. Códigos estables con el formato `{"detail": {"code", "message"}}` existente. Ambos endpoints devuelven `Cache-Control: no-store` y `Vary: Authorization` como la cola de trabajo.

**Contrato completo**: [`contracts/sla-dashboard.openapi.yaml`](./contracts/sla-dashboard.openapi.yaml).

### 3. Reglas de umbrales y configuración

**Decisión**: los límites de SLA por prioridad **ya existen** y no se duplican: el valor que rige es el **histórico estampado en el ticket** (`tickets.sla_deadline`, creado a partir de `priorities.base_hours` de HU-08 en el momento de la creación del ticket, HU04-RN-03). El catálogo `priorities.base_hours` se usa solo como referencia, nunca para recalcular métricas de periodos pasados.

Los **umbrales del semáforo** se definen como **constantes de módulo en `backend/app/utils/sla.py`**, junto a la función pura `compliance_band(pct)` que implementa la regla de banda superior:

```python
SLA_GREEN_THRESHOLD_PCT = 90.0   # verde: cumplimiento >= 90 %
SLA_AMBER_THRESHOLD_PCT = 70.0   # ámbar: 70 % <= cumplimiento < 90 %
                                  # rojo: cumplimiento < 70 %
```

- Son las mismas para todo el dashboard (celdas, totales y global) y nunca se configuran desde la interfaz (fuera de alcance).
- El backend las **emite en `meta.thresholds` de cada respuesta**; el frontend pinta la leyenda con los valores recibidos y no hardcodea números, de modo que un cambio de negocio en un único fichero recalcula todos los semáforos de forma coherente (HU07-RN-11, HU07-SC-006).
- «Sin datos» (denominador cero) es una banda neutra sin color de alarma (HU07-RF-039).
- Los umbrales no son secretos ni parámetros de despliegue: son decisión de negocio versionada en código; por eso van en `utils/sla.py` y no en `Settings` del entorno.

### 4. Permisos y visibilidad

**Decisión**: nueva dependencia `require_supervisor_or_admin` en `app/api/deps.py`, replicando el patrón existente de `require_technician`:

- Identidad **exclusivamente del token JWT** (`get_current_user`, constitución III); nunca de parámetros de consulta ni cabeceras manipulables.
- Tras autenticar y comprobar `is_active`, si `current_user.role not in (supervisor, admin)` ⇒ `403 forbidden` («No tienes permiso para acceder a este dashboard.») **sin revelar datos agregados ni la existencia de métricas**.
- Alcance global sin filtro por equipo (aclaración Q4): el servicio no filtra por `team` ni por usuario.
- **Sin cambios en permisos existentes**: `require_technician`, la cola de HU-04, el flujo de HU-05 y la reasignación de HU-06 conservan sus guards intactos; el nuevo guard se aplica solo a los dos endpoints nuevos.
- Minimización de datos (HU07-RN-13): el ranking expone solo `technician_name`, `team`, `is_active` y métricas agregadas; nunca correos, datos del usuario creador, descripciones ni identificadores de tickets individuales.
- El frontend solo oculta la navegación y redirige; **la autorización real es siempre el guard del servidor**.
- Respuestas con `Cache-Control: no-store` para no dejar métricas en cachés compartidas.

### 5. Interfaz de dashboard (Frontend / Vue 3)

**Decisión**: una página nueva con store Pinia y componentes propios, reutilizando el cliente HTTP (`apiGet`), Tailwind, los patrones de accesibilidad y el modelo de estados de HU-04. No se añaden librerías de gráficos ni de interfaz.

| Pieza | Responsabilidad |
|---|---|
| Ruta `/dashboard-sla` (`SlaDashboardPage.vue`) | Vista de solo lectura; guard de cliente por rol (supervisor/admin) que redirige a `/login?redirect=…` o muestra el estado `forbidden`; el servidor es la defensa real |
| `stores/slaDashboard.ts` | Filtros sincronizados con la URL (query params en español: `desde`, `hasta`, `categorias`, `prioridades`), carga con `AbortController`, sondeo ≤ 60 s pausado con pestaña oculta y refresco al recuperar foco, actualización manual, aviso de desactualización conservando los últimos datos válidos, `mapError` con mensajes es-ES (patrón de `workQueue.ts`) |
| `SlaDashboardFilters.vue` | Barra de filtros: rango de fechas (`type="date"`), multiselección de categorías y prioridades con opciones de `/options`, resumen de filtros activos (RF-037), acción de restablecer; bloquea aplicar si `desde > hasta` |
| `SlaSummary.vue` | Resumen global (RF-005): tickets considerados, atendidos con SLA, cumplimiento, tiempo medio, vencidos, sin SLA |
| `ComplianceMatrix.vue` | Matriz prioridad (Crítica, Alta, Media, Baja) × categorías alfabéticas; celdas solo para combinaciones con datos; totales por fila/columna y global siempre visibles |
| `SemaphoreBadge.vue` | Semáforo reutilizable (verde/ámbar/rojo/sin datos) con **color + icono lucide + texto** (nunca solo color, HU07-RF-040); clases Tailwind estáticas en `utils/slaStyles.ts` |
| `SemaphoreLegend.vue` | Leyenda con los umbrales vigentes leídos de `meta.thresholds` |
| `TechnicianRanking.vue` | Tabla ordenada por volumen: nombre, equipo, vencidos, retraso medio; «(inactivo)» y fila «Sin asignar» separada al final |
| `DashboardEmptyState.vue` / `DashboardErrorState.vue` | Variantes diferenciadas: periodo sin tickets, filtros sin resultados, periodo sin SLA, periodo sin vencidos, error de carga, error de actualización con datos previos, `forbidden` (HU07-RN-16) |
| `utils/format.ts` | Formato es-ES: porcentaje con un decimal y coma (`Intl.NumberFormat('es-ES')`), fechas/horas en `Europe/Madrid`, duraciones reutilizando `formatDuration` de `utils/sla.ts` (con «menos de 1 min») |
| `api/slaDashboard.ts` + `types/slaDashboard.ts` | Wrappers de `apiGet` y tipos espejo del contrato OpenAPI |

**Accesibilidad WCAG 2.1 AA**: tablas con `scope`, `caption` y cabeceras asociadas; `role="alert"`/`aria-live` para estados dinámicos; foco visible; navegación completa por teclado; contraste AA. Español de España en todos los textos.

**Contrato de componentes**: [`contracts/frontend-components.md`](./contracts/frontend-components.md).

### 6. Conservación de arquitectura

**Decisión**: HU-07 es **aditiva y de solo lectura**; nada de lo existente cambia de comportamiento.

- **Docker Compose**: sin cambios (`db` postgres:16, `backend`, `frontend` y sus healthchecks quedan intactos); la nueva funcionalidad se despliega con la misma imagen de backend.
- **Base de datos PostgreSQL**: **cero migraciones** — no hay tablas, columnas, enums ni índices nuevos; la línea temporal append-only no se escribe desde el dashboard (HU07-RN-01) y su estructura no se toca. Única adición de dependencia: `tzdata` en `requirements.txt` (necesario para `zoneinfo("Europe/Madrid")` en Windows; no altera el esquema ni el despliegue).
- **HU-04 (cola)**: `work_queue.py`, `utils/sla.py` (se **amplía** con constantes y `compliance_band()`, sin modificar funciones existentes), indicador de SLA y su reloj siguen intactos.
- **HU-05 (flujo y timeline)**: `ticket_workflow`, máquina de estados, `ck_tickets_finalized_at` y la inmutabilidad de `ticket_timeline_entries` se respetan; el dashboard solo hace `SELECT`.
- **HU-06 (reasignación)**: `assignee_change`, notificaciones y la consistencia `ensure_assignee_consistency` no se modifican; el dashboard lee `assignee_change` del timeline para la atribución.
- **Backend**: solo adiciones — `app/services/sla_dashboard.py`, `app/schemas/sla_dashboard.py`, `app/api/v1/sla_dashboard.py`, `require_supervisor_or_admin` en `deps.py` y registro del router.
- **Frontend**: solo adiciones — ruta, página, store, componentes `sla-dashboard/`, tipos y wrapper de API; no se tocan stores ni vistas de HU-04/05/06.
- **Cliente compilado**: solo se añaden llamadas `GET`; no se introducen PATCH/PUT/DELETE (constitución, compatibilidad de cliente).

## Technical Context

**Language/Version**: Python 3.12 (backend, imagen `python:3.12-slim`), TypeScript ~5.7 + Vue 3.5 (frontend, Node 20)

**Primary Dependencies**: FastAPI 0.115, SQLAlchemy 2.0, Pydantic 2.10, Alembic 1.14 (backend); Vue Router 4.5, Pinia 2.3, Vite 6, Tailwind CSS 3.4, lucide-vue-next (frontend). Se añade `tzdata` (backend)

**Storage**: PostgreSQL 16 (desarrollo y producción); SQLite solo para pruebas funcionales mediante la abstracción de sesión existente

**Testing**: pytest 8.3 (backend: unit + integration + contract, `pytest.ini` existente); Vitest 2 + @vue/test-utils + axe-core (frontend: unit, components, stores)

**Target Platform**: Web (escritorio y tablet), navegadores modernos; despliegue con `docker-compose.yml` vigente

**Project Type**: Web application (backend API + SPA)

**Performance Goals**: dashboard completo < 3 s para 10.000 tickets en el periodo en ≥ 95 % de cargas (HU07-SC-002; protocolo de medición en `quickstart.md` §5 E8); p95 de servidor < 300 ms por la constitución; refresco automático ≤ 60 s

**Constraints**: solo lectura (ninguna escritura a BD); instantánea coherente entre secciones; datos históricos inmutables (sin recálculo por cambios de configuración); WCAG 2.1 AA; es-ES con `Europe/Madrid`; sin datos personales más allá de nombre y equipo del técnico

**Scale/Scope**: hasta 10.000 tickets por periodo consultado; 2 endpoints GET nuevos, 1 servicio, 1 store, ~9 componentes Vue

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio | Evaluación | Evidencia |
|---|---|---|
| I. Arquitectura por capas y stack fijado | ✓ PASS | `api/v1/sla_dashboard.py` (orquestación) → `services/sla_dashboard.py` (reglas y agregación) → modelos/db en solo lectura; `schemas/sla_dashboard.py` como contrato E/S. Sin tecnologías nuevas: FastAPI, SQLAlchemy, Vue 3, Tailwind, Pinia |
| II. Modelo de datos estable y migraciones aditivas | ✓ PASS | **Sin migración**: no se añaden ni alteran tablas, columnas, enums ni índices. La línea temporal append-only se consulta, nunca se escribe. El único cambio de datos documentado es la adición de `tzdata` a `requirements.txt` (dependencia, no esquema) |
| III. Seguridad y mínimo privilegio | ✓ PASS | Identidad solo del JWT; `require_supervisor_or_admin` en servidor para ambos endpoints; 403 sin revelar datos; sin correos, creadores ni tickets individuales en la respuesta; `Cache-Control: no-store`; sin `v-html` |
| IV. Contratos primero y pruebas verificables | ✓ PASS | `contracts/sla-dashboard.openapi.yaml` y `contracts/frontend-components.md` antes de implementar; `quickstart.md` con escenarios ejecutables (matriz de permisos, límites exactos de SLA, semáforo en umbral, conciliación de totales, estados vacíos); pruebas de backend y frontend listadas |
| V. Simplicidad, trazabilidad y experiencia en español | ✓ PASS | YAGNI: sin gráficos, sin exportación, sin tablas nuevas, sin caché materializada; cada cifra trazable a tickets y reglas (HU07-RN-17); es-ES, fechas `Europe/Madrid` mostradas / UTC almacenadas; WCAG 2.1 AA |
| Restricción: formato de error `{"detail": {"code", "message"}}` | ✓ PASS | Reutiliza `ApiError` y handlers registrados; códigos nuevos estables: `invalid_date_range` |
| Restricción: cliente GET/POST | ✓ PASS | Solo endpoints GET nuevos |
| Restricción: p95 < 300 ms servidor | ✓ PASS | Una consulta con `LIMIT` implícito de población (rango de fechas) y agregación O(n) en memoria; medición incluida en pruebas (HU07-SC-002 más holgada) |
| Concurrencia / atomicidad / idempotencia (constitución IV) | ✓ N/A | Módulo de solo lectura: no escribe en `tickets` ni en `ticket_timeline_entries`; la lectura es una única `SELECT` en transacción de lectura (HU07-RN-12). Se añade T075 como prueba de concurrencia real sobre PostgreSQL |

**Veredicto**: sin violaciones. No se requiere `Complexity Tracking`.

**Re-evaluación tras Fase 1** (post-diseño de `research.md`, `data-model.md`, `contracts/`, `quickstart.md`): los contratos no introducen escrituras, esquema ni permisos nuevos; la agregación en Python sobre una única proyección SQL mantiene el stack y la paridad PG/SQLite de pruebas; los umbrales viven en un único módulo de utilidades. Todos los principios siguen en PASS.

## Project Structure

### Documentation (this feature)

```text
specs/007-dashboard-cumplimiento-sla/
├── plan.md              # Este documento (/speckit.plan)
├── research.md          # Fase 0: decisiones y alternativas
├── data-model.md        # Fase 1: entidades, derivaciones y reglas
├── contracts/
│   ├── sla-dashboard.openapi.yaml   # Contrato HTTP de los 2 endpoints
│   └── frontend-components.md       # Contrato de componentes Vue
├── quickstart.md        # Fase 1: guía de validación ejecutable
└── tasks.md             # Fase 2 (/speckit.tasks — no lo genera /speckit.plan)
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── api/
│   │   ├── deps.py                  # + require_supervisor_or_admin (aditivo)
│   │   └── v1/
│   │       ├── router.py            # + registro de sla_dashboard
│   │       └── sla_dashboard.py     # NUEVO: 2 endpoints GET (orquestación)
│   ├── schemas/
│   │   └── sla_dashboard.py         # NUEVO: filtros, métricas, ranking, meta
│   ├── services/
│   │   └── sla_dashboard.py         # NUEVO: CTE de población + agregaciones
│   └── utils/
│       └── sla.py                   # + SLA_GREEN/AMBER_THRESHOLD_PCT, compliance_band()
├── requirements.txt                 # + tzdata
└── tests/
    ├── unit/test_sla_dashboard_math.py        # NUEVO: fórmulas, redondeo, semáforo
    ├── integration/test_sla_dashboard.py      # NUEVO: API + permisos + conciliación
    └── contract/test_sla_dashboard_contract.py # NUEVO: contrato OpenAPI
frontend/
├── src/
│   ├── api/
│   │   └── slaDashboard.ts          # NUEVO: wrapper apiGet
│   ├── types/
│   │   └── slaDashboard.ts          # NUEVO: tipos espejo del contrato
│   ├── stores/
│   │   └── slaDashboard.ts          # NUEVO: filtros URL + sondeo 60 s
│   ├── router/index.ts              # + ruta /dashboard-sla con guard de rol
│   ├── views/
│   │   └── SlaDashboardPage.vue     # NUEVO
│   ├── components/sla-dashboard/    # NUEVO: Filters, Summary, ComplianceMatrix,
│   │                                #   SemaphoreBadge, SemaphoreLegend,
│   │                                #   TechnicianRanking, Empty/Error states
│   └── utils/
│       └── format.ts                # NUEVO: porcentajes y fechas es-ES/Madrid
└── tests/
    ├── components/ (sla-dashboard)  # NUEVO: matriz, semáforo, ranking, estados
    └── stores/slaDashboard.spec.ts        # NUEVO
```

**Structure Decision**: estructura web existente (`backend/` + `frontend/`) sin proyectos nuevos. Todos los cambios son ficheros nuevos o adiciones puntuales (`deps.py`, `router.py`, `utils/sla.py`, `requirements.txt`) identificadas arriba.

## Complexity Tracking

> Sin violaciones de constitución: la tabla queda vacía.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |
