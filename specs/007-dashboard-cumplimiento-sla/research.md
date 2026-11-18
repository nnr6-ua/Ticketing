# Research: Dashboard de cumplimiento de SLA (HU-07)

**Feature**: `007-dashboard-cumplimiento-sla` | **Date**: 2026-11-15

Este documento resuelve las decisiones técnicas de la Fase 0. Todas se basan en el código real de `backend/` y `frontend/` y en las aclaraciones de la especificación (sesión 2026-11-14). No queda ninguna incógnita (`NEEDS CLARIFICATION`) abierta: la especificación consolidada ya define la semántica de negocio (primera finalización, umbrales, regla mixta, alcance global, periodo por defecto) y este plan solo decide el **cómo** técnico.

Contexto verificado del código (exploración 2026-11-15):

- `tickets.finalized_at` materializa la primera finalización con la restricción `ck_tickets_finalized_at`; se estampa en el primer paso a «Resuelto», se conserva al cerrar y se anula al reabrir (`backend/app/services/ticket_workflow.py:386-401`).
- La línea temporal `ticket_timeline_entries` es append-only con `event_type ∈ {status_change, resolution, internal_comment, assignee_change}`, índice `ix_timeline_ticket_created (ticket_id, created_at)` y autor en `author_id`.
- `tickets.sla_deadline` es el límite histórico por ticket (`NULL` = sin SLA; `ck_tickets_sla_deadline_after_created` garantiza `> created_at`); el catálogo de plazos vive en `priorities.base_hours` (seed: Crítica 4 h, Alta 8 h, Media 24 h, Baja 72 h).
- No existe guard de rol para supervisor (solo `require_technician` en `app/api/deps.py:71-80`); formato de error `{"detail": {"code", "message"}}` (`app/core/errors.py`).
- Frontend: store `workQueue.ts` con filtros en URL, sondeo 60 s, AbortController y degradación con datos previos; cliente `apiGet`/`apiPost` propio; `formatDuration` en `utils/sla.ts`; no hay librería de gráficos ni i18n (textos es-ES hardcodeados).
- Migraciones en cabeza: `0004_assignee_changes`. Cadena completa `0001 → 0004`.

---

## R1 — Cómo calcular la primera finalización y el tiempo de respuesta sin tocar la línea temporal

**Decision**: usar la **línea temporal** como fuente de la primera finalización para todas las métricas y el semáforo: la primera entrada `event_type = 'status_change'` con `to_status = 'resuelto'` (la más antigua por `(created_at, event_order, id)`), con fallback a `tickets.finalized_at` solo para tickets heredados sin línea temporal. La misma entrada sirve para derivar **quién finalizó** en la atribución de vencidos. `tickets.finalized_at` refleja el estado actual y **se limpia al reabrir**, por lo que no puede usarse como primera finalización. Ninguna escritura, ninguna migración.

**Rationale**:
- La primera finalización se deriva de la línea temporal append-only, que conserva el primer paso a «Resuelto» aunque el ticket se reabra (HU04-RN-13). `finalized_at` solo refleja el estado actual: la constraint `ck_tickets_finalized_at` lo exige para `resuelto`/`cerrado`, pero el flujo de HU-05 lo limpia al reabrir, por lo que no es válido como primera finalización de tickets reabiertos.
- La línea temporal es la fuente inmutable de la primera finalización: el `LEFT JOIN LATERAL` sobre `ix_timeline_ticket_created`, limitado a la población filtrada, es barato y evita la divergencia con la cola de trabajo (que usa `finalized_at` solo para el estado actual).
- El tiempo de respuesta (HU07-RN-05) es `EXTRACT(EPOCH FROM primera_finalizacion - created_at)` para tickets con SLA y primera finalización; nunca negativo (la primera finalización es posterior o igual a `created_at`).

**Alternatives considered**:
- *Usar `tickets.finalized_at` como primera finalización*: descartado — el flujo de HU-05 lo limpia al reabrir, por lo que no conserva la primera finalización (HU04-RN-13).
- *Añadir columna `finalized_by` al ticket*: descartado — requiere migración y duplicaría evidencia que ya existe de forma inmutable en la línea temporal (constitución II: histórico append-only, no se sobrescribe ni se copia).
- *Función de agregación con trigger/materialized view*: descartado — introduce escritura en un módulo de solo lectura y viola YAGNI.

## R2 — Agregación: una sola proyección SQL + agregación en servicio

**Decision**: una única sentencia `SELECT` (CTE `poblacion`) deriva por ticket las métricas del cuadro de `plan.md` §1 (con_sla, atendido, dentro_de_plazo, vencido, retraso_s, atribuido_a). El servicio recibe la proyección (≤ 10.000 filas) y agrega en Python: matriz por (prioridad, categoría), totales por prioridad, por categoría y global, y ranking por técnico. Toda la respuesta proviene de esa misma proyección ⇒ instantánea coherente por construcción (HU07-RN-12).

**Rationale**:
- Una sola sentencia SELECT en una transacción de lectura ve un snapshot consistente; no hay riesgo de secciones con poblaciones distintas.
- La agregación en Python produce **un único camino de código idéntico en PostgreSQL (producción) y SQLite (pruebas funcionales)**. `GROUPING SETS`/`FILTER` de PostgreSQL no existen en SQLite y obligarían a dos implementaciones o a marcar las pruebas como `postgres`-only, debilitando la matriz de pruebas de la constitución IV.
- 10.000 filas × ~10 columnas numéricas es trivial en memoria (< 10 ms de agregación); el objetivo real de rendimiento (< 3 s, HU07-SC-002; p95 < 300 ms de servidor) lo satisface con holgura la propia consulta con filtrado por `created_at`.

**Alternatives considered**:
- *Cuatro consultas GROUP BY separadas en la misma transacción*: descartado — más código, más viajes de red, y la coherencia depende de la disciplina de transacción en vez de estar garantizada por una sola sentencia.
- *`GROUPING SETS` en PostgreSQL con variante SQLite*: descartado — dos caminos de cálculo = riesgo de divergencia de cifras entre pruebas y producción.
- *Cache materializada o tabla de agregados*: descartado — escrituras y invalidación en un módulo de solo lectura; YAGNI.

## R3 — Rango de fechas en días naturales `Europe/Madrid`

**Decision**: los filtros reciben fechas `YYYY-MM-DD`; el servicio convierte el rango a instantes UTC con `zoneinfo`: inicio = `desde 00:00 Europe/Madrid` (incluido), fin **exclusivo** = `(hasta + 1 día) 00:00 Europe/Madrid`. El filtro SQL es `created_at >= :inicio AND created_at < :fin`, lo que incluye ambos días naturales completos con DST correcto y sin duplicar/perder tickets en cambios de hora (HU07-RN-02, caso límite «cambio de hora oficial»). Duraciones siempre sobre instantes absolutos (UTC). El rango por defecto (últimos 30 días naturales incluido hoy) se calcula en servidor, no en el cliente.

**Rationale**: la spec exige días naturales en Madrid con ambos extremos incluidos; trabajar con semirrango `[inicio, fin)` elimina ambigüedades de 23:59:59.999 y es robusto ante DST. El backend ya guarda y devuelve UTC con sufijo `Z` (patrón `_iso_utc` de `schemas/work_queue.py`).

**Alternatives considered**:
- *`BETWEEN hasta 23:59:59.999999`*: descartado — frágil con microsegundos y con DST.
- *Calcular el rango por defecto en el frontend*: descartado — el cliente podría tener reloj desviado; la spec pide «incluido el día de la consulta» en Madrid, que es asunto del servidor.
- *Dependencia `pytz`*: descartada — `zoneinfo` es stdlib en Python 3.12; solo se añade `tzdata` a `requirements.txt` porque Windows (entorno de pruebas locales) no incluye la base de zonas horarias del sistema. Aditivo, sin impacto en la imagen Linux.

## R4 — Dónde viven los umbrales del semáforo

**Decision**: constantes de módulo `SLA_GREEN_THRESHOLD_PCT = 90.0` y `SLA_AMBER_THRESHOLD_PCT = 70.0` en `backend/app/utils/sla.py` (mismo módulo que ya centraliza la semántica SLA de HU-04), junto a la función pura `compliance_band(pct) -> "verde" | "ambar" | "rojo"` que implementa la banda superior (valor exacto del umbral = banda superior). El backend emite los valores en `meta.thresholds` de cada respuesta y el frontend pinta la leyenda con lo recibido.

**Rationale**:
- La spec los fija como decisión de negocio no configurable desde la UI; versionarlos en código es la trazabilidad pedida (un cambio de negocio = un commit en un fichero, y todos los semáforos y la leyenda se recalculan coherentes, HU07-SC-006).
- Centralizarlos en `utils/sla.py` los reutiliza para pruebas unitarias puras y evita que el frontend hardcodee números que luego divergen de la leyenda.
- No son secretos ni configuración por entorno: no pertenecen a `Settings`/variables de entorno.

**Alternatives considered**:
- *Variables de entorno (`Settings`)*: descartada — sugiere configurabilidad por despliegue que la spec excluye («los umbrales son una decisión de negocio», fuera de alcance configurarlos desde la interfaz), y rompería la coherencia garantizada de HU07-RN-11.
- *Hardcodear en el frontend*: descartada — duplicación y desincronización con la leyenda.
- *Tabla de BD para umbrales*: descartada — requiere migración y CRUD que están fuera de alcance.

## R5 — Permisos: guard de servidor para supervisor/admin

**Decision**: nueva dependencia `require_supervisor_or_admin` en `app/api/deps.py`, replicando `require_technician`: tras `get_current_user` (JWT Bearer + `is_active`), si `role not in (supervisor, admin)` ⇒ `ApiError(403, "forbidden", "No tienes permiso para acceder a este dashboard.")`. Aplicada como `Depends` en ambos endpoints nuevos. Respuestas con `Cache-Control: no-store` y `Vary: Authorization` (patrón de `work_queue.py`).

**Rationale**: constitución III (autorización siempre en servidor, identidad solo del JWT); reutiliza el patrón existente, cero impacto en guards vigentes de HU-04/05/06. La aclaración de negocio fija supervisores y administradores como únicos accesos con alcance global sin filtro por equipo, por lo que el servicio no necesita condiciones de `team`.

**Alternatives considered**:
- *Guard solo en el frontend (ocultar ruta)*: insuficiente por constitución (el cliente puede ocultar, no defender).
- *Reutilizar `require_technician` invertido o permisos nuevos en BD*: innecesario — el rol ya existe en el modelo `User` y la historia no pide roles adicionales.
- *Filtrar por equipo del supervisor*: descartado por la aclaración Q4 (alcance global).

## R6 — Atribución de vencidos (regla mixta) y «Sin asignar»

**Decision**: para cada ticket **vencido** de la población, la CTE calcula `atribuido_a` de forma única:
1. Si `atendido` (primera finalización): `author_id` de la primera entrada `status_change` con `to_status = 'resuelto'` (orden `(created_at, event_order, id)`), obtenida por `LEFT JOIN LATERAL ... LIMIT 1`.
2. Si no atendido (activo vencido): `tickets.assignee_id` (responsable vigente en el instante de la consulta).
3. Si el resultado es `NULL` (o no existe entrada de timeline para un ticket legado finalizado): `NULL` ⇒ fila «Sin asignar».

Cada vencido se contabiliza exactamente una vez; el ranking agrupa por `atribuido_a` con «Sin asignar» como fila separada al final, y su suma cuadra con el total de vencidos (HU07-RN-08/09, HU07-RF-024, HU07-SC-014).

**Rationale**: la spec exige la regla mixta usando el histórico de cambios de responsable de HU-06, que vive en `ticket_timeline_entries.assignee_change` (`previous_assignee_id`/`new_assignee_id`). «Quien lo finalizó» no está materializado; derivarlo de la primera entrada a «Resuelto» es trazable y no altera la asignación real del ticket. El fallback determinista para tickets legados sin timeline (los `seeded_workflow` históricos) evita agujeros de conciliación.

**Alternatives considered**:
- *Atribuir siempre al responsable actual*: descartada — contradice la aclaración Q3 y la regla mixta HU07-RN-09 (un ticket reasignado tras incumplir se atribuye a quien lo finalizó, no a quien lo recibió después).
- *Nueva tabla de historial de asignaciones*: descartada — el historial ya existe inmutable en la línea temporal; duplicarlo requiere migración y backfill.
- *Lateral join sin límite de población*: innecesario — se aplica solo a tickets vencidos atendidos de la población filtrada.

## R7 — Rendimiento e índices

**Decision**: sin índices nuevos. La consulta filtra por `created_at` (rango ≤ 10.000 tickets), resuelve `priority_id`/`category_id` por FK `lazy="joined"` ya existente y usa `ix_timeline_ticket_created` para el lateral de atribución. Se añade una prueba de rendimiento (10.000 tickets, cargados por lotes) que mide el objetivo de HU07-SC-002 y el p95 < 300 ms de servidor.

**Rationale**: para el volumen especificado, un sequential scan acotado por rango es más barato que mantener un índice nuevo; la constitución exige justificar cada cambio de esquema y no hay necesidad demostrada (YAGNI). Si una medición real en producción lo contradijera, el índice aditivo `ix_tickets_created_at` sería la remediación documentada, no el diseño por defecto.

**Alternatives considered**:
- *`Index("ix_tickets_created_at", "created_at")` en una migración 0005*: reservada como remediación medida, no como diseño.
- *Paginación de la matriz*: descartada — la spec exige conciliación total de celdas y totales en pantalla.

## R8 — Actualización ≤ 60 s y frescura en el frontend

**Decision**: el store Pinia `slaDashboard.ts` replica el patrón probado de `workQueue.ts`: sondeo cada 60 s con `AbortController`, pausa con pestaña oculta, refresco al recuperar foco/visibilidad, actualización manual, filtros persistidos en la URL (query en español: `desde`, `hasta`, `categorias`, `prioridades`), y degradación: si falla una actualización con datos previos, se conservan con aviso de posible desactualización y acción de reintento (HU07-RN-12, HU07-RF-045/046). La fecha/hora de última actualización sale de `meta.generated_at` (ISO UTC) y se muestra en `Europe/Madrid`.

**Rationale**: mismo patrón, mismo riesgo cero; cumple el plazo máximo sin tiempo real (fuera de alcance). La instantánea única del backend garantiza que todas las secciones se refrescan juntas.

**Alternatives considered**:
- *SSE/WebSocket*: descartados — fuera de alcance y violarían la simplicidad (la spec lo excluye expresamente).
- *Sondeo por sección (una petición por bloque)*: descartado — rompería la instantánea coherente.

## R9 — Estados diferenciados y semáforo «Sin datos»

**Decision**: la respuesta distingue siempre `compliance_pct = null` (denominador cero ⇒ «Sin datos», banda neutra) de un porcentaje real; el semáforo se calcula **sobre el valor redondeado a un decimal** (`Decimal.quantize(0.1, ROUND_HALF_UP)` para evitar el redondeo bancario de `round()` de Python). El frontend diferencia los estados por datos + error kind: `periodo-sin-tickets`, `filtros-sin-resultados`, `sin-sla`, `sin-vencidos` (ranking), error de carga, error de actualización con datos previos, sesión caducada (`unauthorized`) y rango inválido (`invalid_date_range`). El rango inválido se bloquea antes de consultar (cliente) y el servidor responde `422` si se salta la comprobación.

**Rationale**: HU07-RN-04/11/15/16 lo exigen expresamente («nunca un 0 % engañoso», «el semáforo usa el valor redondeado que se muestra»). El redondeo HALF_UP sobre `Decimal` es determinista y verificable en pruebas unitarias.

**Alternatives considered**:
- *Redondeo con `round()` nativo*: descartado — banker's rounding (90,05 ⇒ 90,0) contradice la expectativa de presentación es-ES y los casos de umbral.
- *Calcular el semáforo en el frontend*: descartado — la banda es regla de negocio; el cliente solo pinta lo que el backend decidió (y recibe los umbrales para la leyenda).

## R10 — Paridad de pruebas PostgreSQL/SQLite

**Decision**: las pruebas funcionales del dashboard se ejecutan por defecto sobre SQLite (conftest existente) y, si `TEST_DATABASE_URL` está exportado, sobre PostgreSQL real (marcador `postgres`). El cálculo SQL se limita a expresiones soportadas por ambos motores (`EXTRACT(EPOCH FROM interval)` se traduce con SQLAlchemy; la derivación `vencido` de tickets activos usa un parámetro `:ahora` generado en servidor, nunca `now()` literal embebido).

**Rationale**: la constitución IV admite SQLite para pruebas funcionales vía la abstracción existente; diseñar la CTE con funciones portables evita sorpresas de semántica entre motores (p. ej. comparación de `DateTime(timezone=True)`). Las pruebas de concurrencia real siguen siendo PostgreSQL-only, pero este módulo es de solo lectura y no tiene operaciones de escritura concurrentes.

**Alternatives considered**:
- *Pruebas solo en PostgreSQL*: descartado — rompe el flujo de pruebas local por defecto del repo.
- *Calcular `ahora` en SQL nativo del motor*: descartado — divergencia de sintaxis y dificultad para simular instantes de consulta; el «ahora» se inyecta como parámetro (y permite pruebas deterministas de retraso creciente).
