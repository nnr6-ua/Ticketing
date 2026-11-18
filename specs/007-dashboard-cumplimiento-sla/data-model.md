# Data Model: Dashboard de cumplimiento de SLA (HU-07)

**Feature**: `007-dashboard-cumplimiento-sla` | **Date**: 2026-11-15

## 1. Impacto en el esquema: NINGUNO

HU-07 es de **solo lectura**. No se crean, alteran ni eliminan tablas, columnas, enums, índices ni restricciones. **No hay migración de Alembic** (la cadena se mantiene con cabeza en `0004_assignee_changes`). La única adición del backend es la dependencia `tzdata` en `requirements.txt` (soporte de `zoneinfo` en Windows para las pruebas locales; no afecta al esquema ni a la imagen Linux).

El histórico de negocio permanece append-only e inmutable: el dashboard emite `SELECT` sobre fuentes existentes y **jamás** escribe en `tickets` ni en `ticket_timeline_entries` (HU07-RN-01, HU07-RN-17).

## 2. Tablas fuente consultadas (sin cambios)

### 2.1. `tickets` (`backend/app/models/ticket.py`)

| Columna | Tipo | Uso en HU-07 |
|---|---|---|
| `id` | Uuid PK | Identidad del ticket (solo interno, nunca expuesto) |
| `number` | String(20) | No se expone (privacidad HU07-RN-13) |
| `status` | Enum `ticket_status` | Activo (`abierto|en_progreso|pendiente_usuario`) vs finalizado |
| `priority_id` | Uuid FK → `priorities.id` | Dimensión de la matriz (valor de creación, FK inmutable) |
| `category_id` | Uuid FK → `categories.id`, `NULL` | Dimensión de la matriz; `NULL` ⇒ «Sin categoría» |
| `assignee_id` | Uuid FK → `users.id`, `NULL` | Atribución de vencidos activos (regla mixta) |
| `created_at` | DateTime(tz) UTC | Filtro de población (días naturales `Europe/Madrid`) |
| `sla_deadline` | DateTime(tz) UTC, `NULL` | Límite de SLA histórico; `NULL` ⇒ «Sin SLA», nunca vencido |
| `finalized_at` | DateTime(tz) UTC, `NULL` | Estado actual (finalizado ⇔ no nulo); se limpia al reabrir, por lo que **no** sirve como primera finalización (HU04-RN-13) |
| `closed_at` | DateTime(tz) UTC, `NULL` | No se usa directamente (la métrica es la primera finalización) |
| `sla_version` | String(50), `NULL` | Informativo; no altera el cálculo |

Restricciones relevantes (vigentes, no se modifican): `ck_tickets_finalized_at` (finalizado ⇔ `finalized_at NOT NULL`), `ck_tickets_finalized_after_created` (`finalized_at >= created_at`), `ck_tickets_sla_deadline_after_created` (`sla_deadline > created_at`).

### 2.2. `ticket_timeline_entries` (`backend/app/models/timeline.py`) — solo lectura

| Columna | Uso en HU-07 |
|---|---|
| `ticket_id` | Unión con el ticket |
| `event_type` | Filtro `= 'status_change'` |
| `to_status` | Filtro `= 'resuelto'` (primera finalización) |
| `author_id` | **Quien finalizó** para la regla mixta (HU07-RN-09) |
| `created_at`, `event_order`, `id` | Orden determinista de la primera entrada |

La inmutabilidad append-only no se altera; el dashboard nunca inserta, actualiza ni elimina entradas.

### 2.3. `users` (`backend/app/models/user.py`)

| Columna | Uso en HU-07 |
|---|---|
| `id`, `name`, `team`, `is_active` | Ranking: identidad mínima del técnico («(inactivo)» si `is_active = false`) |
| `role` | Guard `require_supervisor_or_admin` (`supervisor`/`admin`) |
| `email` | **Nunca se expone** (HU07-RN-13, RF-026) |

### 2.4. `priorities` y `categories`

| Tabla | Columnas usadas | Uso |
|---|---|---|
| `priorities` | `id`, `name`, `level` (1=Crítica … 4=Baja), `is_active` | Dimensión y orden Crítica→Baja; sufijo «(inactiva)» |
| `priorities` | `base_hours` | Solo referencia del catálogo HU-08; **no** recalcula métricas |
| `categories` | `id`, `name`, `is_active` | Dimensión alfabética; sufijo «(inactiva)»; `NULL` ⇒ «Sin categoría» |

## 3. Proyección derivada `poblacion` (entidad de cálculo, no persistida)

Derivada en una única sentencia SQL (CTE; ver `plan.md` §1 y `research.md` R1/R2/R6). Cada fila representa un ticket de la población filtrada:

| Campo derivado | Regla de derivación | Referencia |
|---|---|---|
| `priority_id`, `priority_level`, `priority_name`, `priority_is_active` | FK del ticket | HU07-RN-02, RF-012 |
| `category_id` (nullable), `category_name` (`NULL` ⇒ «Sin categoría»), `category_is_active` | FK del ticket | RF-012, HU07-RN-07 |
| `con_sla` | `sla_deadline IS NOT NULL` | HU07-RN-02 |
| `primera_finalizacion` | Primera entrada `status_change → 'resuelto'` por `(created_at, event_order, id)`; fallback `tickets.finalized_at` solo si no hay entrada (ticket heredado); `NULL` si ninguna | HU07-RN-03 (Q1), HU04-RN-13 |
| `atendido` | `primera_finalizacion IS NOT NULL` | HU07-RN-03 (Q1) |
| `atendido_con_sla` | `atendido AND con_sla` | Denominador HU07-RN-04 |
| `dentro_de_plazo` | `atendido_con_sla AND primera_finalizacion <= sla_deadline` (igualdad incluida) | HU07-RN-04, HU07-SC-015 |
| `tiempo_respuesta_s` | `EXTRACT(EPOCH FROM primera_finalizacion - created_at)` si `atendido_con_sla`; `NULL` en otro caso; ≥ 0 | HU07-RN-05 |
| `vencido` | `con_sla AND ((atendido AND primera_finalizacion > sla_deadline) OR (NOT atendido AND :ahora > sla_deadline))` | HU07-RN-06 |
| `retraso_s` | Si vencido y no atendido: `:ahora - sla_deadline`; si vencido y atendido: `primera_finalizacion - sla_deadline`; `NULL` si no vencido | HU07-RN-06, Q5 |
| `atendido_por` | Si `atendido`: `author_id` de la primera entrada `status_change → 'resuelto'` por `(created_at, event_order, id)`; fallback `assignee_id` si no hay entrada (ticket legado) | HU07-RN-09 (regla mixta) |
| `atribuido_a` | Si `vencido`: `atendido_por` si `atendido`, si no `assignee_id`; `NULL` ⇒ «Sin asignar». Si no vencido: `NULL` | HU07-RN-09, RF-023 |
| `status_actual`, `assignee_id` | Estado y responsable vigentes | Regla mixta |

Parámetros de la consulta: `:desde_utc`, `:hasta_utc` (semirrango `[desde 00:00 Madrid, (hasta+1d) 00:00 Madrid)` en UTC), `:categorias` (lista de UUID + marcador `sin_categoria`), `:prioridades` (niveles 1–4), `:ahora` (instante de la instantánea, generado en servidor).

**Invariantes de la proyección**:

- Cada ticket de la población aparece exactamente una vez (HU07-RF-013; reabiertos conservan la primera finalización).
- `dentro_de_plazo ≤ atendido_con_sla ≤ ticket_count` por cualquier agrupación.
- `vencido = false` si `con_sla = false` (los sin SLA nunca están vencidos, HU07-RF-014).
- `retraso_s > 0` para todo vencido (nunca negativo).
- Si `atendido` ⇒ exactamente un `atendido_por` (o fallback a `assignee_id`/`NULL` determinista).

> Tickets heredados sin línea temporal: la primera finalización es `tickets.finalized_at` y la atribución se hace al responsable vigente («Sin asignar» si no lo hay), conforme a la regla mixta de HU07-RN-09.

## 4. Entidades de salida (contrato, no persistidas)

### 4.1. Consulta del dashboard (snapshot)

| Campo | Descripción |
|---|---|
| `filters` | `desde`/`hasta` efectivas (fechas Madrid), `categorias` (UUIDs + `sin_categoria`), `prioridades` (niveles), o «por defecto» |
| `generated_at` | Instante UTC de la instantánea (se muestra en `Europe/Madrid`) |
| `timezone` | Siempre `Europe/Madrid` |
| `thresholds` | `{green_pct: 90.0, amber_pct: 70.0}` leídos de `utils/sla.py` |

### 4.2. Métrica de cumplimiento (celda de matriz y totales)

| Campo | Regla | Referencia |
|---|---|---|
| `ticket_count` | Tickets de la combinación | RF-006 |
| `no_sla_count` | Tickets sin SLA (excluidos de % y media) | RF-014 |
| `attended_with_sla` | Denominador | RN-04 |
| `on_time` | Numerador | RN-04 |
| `compliance_pct` | `Decimal(100 × on_time / attended_with_sla).quantize(0.1, HALF_UP)`; `NULL` si denominador 0 («Sin datos») | RN-04, RN-15 |
| `avg_response_seconds` | Media exacta de `tiempo_respuesta_s` (segundos, float); `NULL` si no hay atendidos con SLA | RN-05 |
| `overdue_count` | Recuento de vencidos | RN-06 |
| `semaphore` | `compliance_band(compliance_pct)` ⇒ `verde | ambar | rojo`; `sin_datos` si `compliance_pct = NULL` | RN-11 |

Las mismas fórmulas recalculadas sobre tickets subyacentes producen los totales por prioridad, por categoría y el global (nunca promedios de celdas, RF-015). Las combinaciones sin tickets no generan fila; los totales siempre se emiten.

### 4.3. Ranking de técnicos (vencidos)

| Campo | Regla | Referencia |
|---|---|---|
| `technician_id` (UUID o `NULL`), `technician_name`, `team`, `is_active` | Identidad mínima; `NULL` = fila «Sin asignar» | RN-08, RF-021/024 |
| `overdue_count` | Vencidos atribuidos | RF-019 |
| `avg_delay_seconds` | Media exacta de `retraso_s` de sus vencidos; desempate usa el valor exacto | RN-08, Q5 |

Orden: `overdue_count DESC` → `avg_delay_seconds DESC` (exacto) → `lower(name) ASC` → `team ASC`; orden estable. Solo técnicos con ≥ 1 vencido; «Sin asignar» al final, sin contar como técnico. La suma de `overdue_count` del ranking + «Sin asignar» = total de vencidos del dashboard (RF-024, HU07-SC-014).

### 4.4. Semáforo (valor embebido en cada métrica)

| Banda | Regla sobre `compliance_pct` redondeado | Etiqueta es-ES |
|---|---|---|
| `verde` | `>= 90.0` | «En objetivo» |
| `ambar` | `>= 70.0 y < 90.0` | «En riesgo» |
| `rojo` | `< 70.0` | «Fuera de objetivo» |
| `sin_datos` | `compliance_pct = NULL` | «Sin datos» (color neutro) |

Umbral exacto ⇒ banda superior (Q2, RF-041). Umbrales emitidos en `meta.thresholds`; única fuente `backend/app/utils/sla.py`.

### 4.5. Opciones de filtro (`/options`)

| Campo | Regla |
|---|---|
| `categories` | Categorías con ≥ 1 ticket en el periodo, con `is_active` vigente; opción `{id: null, name: "Sin categoría"}` si existen tickets sin categoría |
| `priorities` | Niveles 1–4 con ≥ 1 ticket en el periodo, con `is_active` vigente |
| `desde` / `hasta` | Fechas de las opciones calculadas |

## 5. Reglas de validación (entrada)

| Entrada | Validación | Error |
|---|---|---|
| `desde`, `hasta` | `YYYY-MM-DD` válidas; `desde <= hasta` | `422 invalid_request` / `422 invalid_date_range` |
| `categorias` | CSV de UUID válidos + valor literal `sin_categoria` | `422 invalid_request` |
| `prioridades` | CSV de enteros 1–4 | `422 invalid_request` |
| Sesión | JWT Bearer válido y activo | `401 not_authenticated` |
| Rol | `supervisor` o `admin` | `403 forbidden` |

El rango por defecto (últimos 30 días naturales incluido hoy, en Madrid) lo calcula el servidor cuando los parámetros no están presentes; el frontend muestra siempre los valores efectivos de `meta.filters`.

## 6. Transiciones de estado

No aplica: el módulo es de solo lectura y no define ni consume transiciones. La condición «vencido» es un estado **derivado** de consulta (crece para activos, es estático para finalizados) y la evidencia de cumplimiento reside inalterada en la línea temporal (HU07-RN-17, HU04-RN-07); `tickets.finalized_at` solo refleja el estado actual.
