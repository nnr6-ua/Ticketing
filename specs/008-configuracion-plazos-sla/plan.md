# Implementation Plan: Configuración de categorías, prioridades y plazos (HU-08)

**Branch**: `hu-08-configuracion-sla` | **Date**: 2026-11-15 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/008-configuracion-plazos-sla/spec.md`

**Estado**: plan de Fase 0 y Fase 1. Los artefactos `research.md`, `data-model.md`, `contracts/` y `quickstart.md` están sincronizados con este documento.

## Summary

HU-08 incorpora la configuración administrativa de categorías, prioridades y la matriz de plazos por combinación categoría × prioridad, con dos garantías centrales:

1. **No retroactividad**: cada ticket congela en su creación el plazo aplicado, el límite resultante, el nivel de urgencia de la prioridad y la versión de configuración. Ningún cambio posterior altera esos valores.
2. **Trazabilidad y mínimo privilegio**: solo el rol `admin` consulta o modifica la configuración administrativa completa y su histórico; el catálogo operativo de entidades activas sigue disponible para crear tickets. Toda escritura es append-only en el histórico, atómica y protegida con bloqueo optimista.

La solución reutiliza el modelo existente (`categories`, `priorities`, `tickets`) y añade de forma aditiva:

- **Versiones de configuración** (`configuration_versions`) y **reglas SLA versionadas** (`sla_rules`), con una única regla vigente por combinación.
- **Auditoría inmutable** (`configuration_audit_entries`) con autor, fecha, entidad, acción, valores anteriores y nuevos.
- **Columnas de congelación en `tickets`**: `sla_priority_level`, `sla_hours_applied` y `sla_config_version_id`, manteniendo `sla_deadline` y `sla_version`.
- **Revisión optimista** (`revision`) en categorías y prioridades.

**Decisiones clave**:

| Punto solicitado | Decisión |
|---|---|
| Permisos | Nueva dependencia `require_admin`; todos los endpoints `/api/v1/admin/**` devuelven `403 forbidden` para cualquier otro rol |
| Versionado | Una fila `configuration_versions` por transacción de configuración; cada cambio de regla crea una fila nueva en `sla_rules` |
| No retroactividad | Snapshot en `tickets` al crear; la cola usa `sla_priority_level` congelado, no el nivel mutable de `priorities` |
| Concurrencia | Bloqueo optimista por `revision`/`expected_rule_id` y bloqueo de la versión vigente (`FOR UPDATE` escritura, `FOR SHARE` creación de ticket) |
| Matriz atómica | `POST /admin/sla-rules/batch`: valida y escribe todas las celdas en una sola transacción y una sola versión |
| Cliente HTTP | Solo `GET` y `POST`, conforme a la restricción de compatibilidad del cliente existente |
| Frontend | Página `/admin/configuracion` con pestañas Categorías, Prioridades, Matriz SLA e Histórico, usando la paleta `slate`/`sky`, Tailwind, Headless UI y los patrones de `TicketForm` |

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript 5.7 + Vue 3.5 (frontend)

**Primary Dependencies**: FastAPI 0.115, SQLAlchemy 2.0, Pydantic 2, Alembic, psycopg; Vue 3, Pinia, Vue Router, Tailwind CSS 3.4, Headless UI, Heroicons; pytest + `fastapi.testclient`, Vitest + `@vue/test-utils`

**Storage**: PostgreSQL 16 en desarrollo/producción (`postgresql+psycopg://...`); SQLite en pruebas funcionales mediante `app/db/session.py`. Las tablas nuevas usan tipos genéricos de SQLAlchemy (`Uuid`, `JSON`, `Numeric`, `DateTime(timezone=True)`) para mantener portabilidad.

**Testing**:
- Backend: `pytest` con `TestClient`; pruebas de autorización, catálogos, matriz, no retroactividad, histórico, contrato y concurrencia real en PostgreSQL.
- Frontend: `vitest` + `@vue/test-utils` y `axe-core` para comprobaciones básicas de accesibilidad.
- Contrato: validación del OpenAPI de `contracts/admin-configuration.openapi.yaml` y paridad de tipos TypeScript.

**Target Platform**: Servicio web Linux/contenedor + navegadores de escritorio y tablet. Sin aplicación móvil nativa.

**Project Type**: Aplicación web con backend y frontend separados.

**Performance Goals**:
- Lectura de catálogos y matriz vigente: p95 < 300 ms de servidor.
- Guardado de una celda o de un lote de hasta 20 celdas: p95 < 400 ms.
- Creación de ticket: el cálculo de SLA añade < 10 ms al flujo existente.
- Histórico paginado (25 por defecto, 100 máximo) para mantener respuestas acotadas.

**Constraints**:
- Interfaz y mensajes 100 % en español de España (HU08-RF-026).
- Fechas almacenadas en UTC y presentadas en `Europe/Madrid` (HU08-RF-026).
- Accesibilidad WCAG 2.1 AA, navegación por teclado y `role="alert"` para errores.
- Sin nuevas tecnologías ni servicios externos.
- Sin `PATCH`, `PUT` ni `DELETE`: los comandos se modelan como recursos `POST`.
- Identidad exclusivamente desde `Authorization: Bearer`; el rol se comprueba en servidor.
- Migración aditiva `0006_sla_configuration`, con `downgrade()` verificado en PostgreSQL.

**Scale/Scope**: Mesa de ayuda interna; decenas de categorías, cuatro niveles de prioridad, cientos de reglas históricas y miles de tickets. Una página administrativa con cuatro pestañas. No se contemplan importaciones masivas, programación futura ni calendarios laborales.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

La constitución aplicable está ratificada en `.specify/memory/constitution.md` (versión 1.0.0, 2026-11-02).

| Principio / restricción | Resultado | Justificación |
|---|---|---|
| I. Arquitectura por capas y stack fijado | PASS | Se reutilizan FastAPI, SQLAlchemy 2, Alembic, PostgreSQL, Vue 3, Pinia, Tailwind y Vitest. Los endpoints `/admin/**` delegan en `app/services/configuration.py` y `app/services/sla_resolution.py`; no se añaden motores externos. |
| II. Modelo de datos estable y migraciones aditivas | PASS | La migración `0006_sla_configuration` solo añade tablas, columnas anulables, índices y enums. No renombra ni elimina columnas. `tickets` conserva `sla_deadline` y `sla_version`; se añaden columnas de snapshot. El histórico es append-only. |
| III. Seguridad y mínimo privilegio | PASS | `require_admin` se aplica en servidor a toda ruta administrativa. Usuario, técnico y supervisor reciben `403 forbidden` sin datos de configuración administrativa, pero conservan el catálogo operativo activo necesario para crear tickets. El frontend oculta la ruta, pero no es la defensa. Sin `v-html`. |
| IV. Contratos primero y pruebas verificables | PASS | Se documentan OpenAPI y contrato de componentes antes de implementar. El plan enumera pruebas de permisos, validación, versionado, no retroactividad, atomicidad, concurrencia, idempotencia, histórico y contrato; T017/T031/T040/T052 cubren comandos repetidos. |
| V. Simplicidad, trazabilidad y español de España | PASS | Se usa una versión global por transacción y reglas versionadas simples; no se introduce un motor de reglas. El histórico registra autor, fecha y valores anteriores/nuevos. Mensajes es-ES y fechas `Europe/Madrid`. |
| Restricciones adicionales | PASS | Formato de error heredado, comandos POST, paginación del histórico, presupuesto p95 verificado por T070 y accesibilidad AA verificada por T067/T071. |

**Post-design re-check (Phase 1)**: PASS condicionado a ejecutar las pruebas de idempotencia, rendimiento y accesibilidad incluidas en `tasks.md`. No se requiere `Complexity Tracking`.

## Project Structure

### Documentation (this feature)

```text
specs/008-configuracion-plazos-sla/
├── plan.md                  # Este archivo
├── research.md              # Fase 0: decisiones y alternativas
├── data-model.md            # Fase 1: entidades, invariantes y migración
├── quickstart.md            # Fase 1: validación ejecutable
├── contracts/
│   ├── admin-configuration.openapi.yaml   # Contrato HTTP
│   └── frontend-components.md             # Contrato de componentes Vue
├── checklists/
│   └── requirements.md      # Checklist de calidad de la especificación
├── spec.md                  # Especificación funcional
└── tasks.md                 # Fase 2 (/speckit.tasks, no lo crea este comando)
```

### Source Code (repository root)

```text
backend/
├── alembic/
│   └── versions/
│       └── 0006_sla_configuration.py        # NUEVO: tablas, columnas, índices y baseline
├── app/
│   ├── api/
│   │   ├── deps.py                          # MODIFICADO: require_admin
│   │   └── v1/
│   │       ├── admin_configuration.py       # NUEVO: endpoints /admin/**
│   │       ├── router.py                    # MODIFICADO: include_router(admin_configuration)
│   │       └── ticket_creation.py           # MODIFICADO: snapshot visible en TicketRead
│   ├── models/
│   │   ├── configuration.py                 # NUEVO: ConfigurationVersion, SlaRule, ConfigurationAuditEntry
│   │   ├── enums.py                         # MODIFICADO: ConfigEntityType, ConfigAction
│   │   ├── category.py                      # MODIFICADO: revision
│   │   ├── priority.py                      # MODIFICADO: revision
│   │   ├── ticket.py                        # MODIFICADO: sla_priority_level, sla_hours_applied, sla_config_version_id
│   │   └── __init__.py                      # MODIFICADO: exportar modelos nuevos
│   ├── schemas/
│   │   ├── configuration.py                 # NUEVO: DTOs de categorías, prioridades, matriz e histórico
│   │   └── ticket_creation.py               # MODIFICADO: sla_version, sla_config_version_id y valores congelados
│   ├── services/
│   │   ├── configuration.py                 # NUEVO: comandos transaccionales y auditoría
│   │   ├── sla_resolution.py                # NUEVO: resolución pura del plazo aplicable
│   │   ├── ticket_creation.py               # MODIFICADO: snapshot de SLA y versión
│   │   └── work_queue.py                    # MODIFICADO: nivel de urgencia congelado
│   └── core/
│       └── errors.py                        # MODIFICADO si se añaden códigos estables de configuración
├── scripts/
│   └── seed_dev.py                          # MODIFICADO: usuario admin y baseline de configuración
└── tests/
    ├── conftest.py                            # MODIFICADO: versión base y usuario admin de pruebas
    ├── unit/
    │   └── test_sla_resolution.py
    ├── integration/
    │   ├── test_admin_authorization.py
    │   ├── test_admin_categories.py
    │   ├── test_admin_priorities.py
    │   ├── test_admin_sla_matrix.py
    │   ├── test_sla_non_retroactivity.py
    │   ├── test_configuration_history.py
    │   └── test_admin_concurrency.py
    └── contract/
        └── test_admin_configuration_contract.py

frontend/
├── src/
│   ├── api/
│   │   └── client.ts                        # REUTILIZADO sin cambios de contrato
│   ├── components/
│   │   └── admin/
│   │       ├── AdminTabs.vue                # NUEVO: pestañas accesibles
│   │       ├── CategoryTable.vue            # NUEVO: listado y acciones
│   │       ├── CategoryFormDialog.vue       # NUEVO: alta/edición
│   │       ├── PriorityTable.vue            # NUEVO: listado y acciones
│   │       ├── PriorityFormDialog.vue       # NUEVO: alta/edición
│   │       ├── SlaMatrix.vue                # NUEVO: matriz editable por lotes
│   │       ├── SlaCellEditor.vue            # NUEVO: edición accesible de una celda
│   │       ├── ConfigHistoryTable.vue       # NUEVO: histórico paginado y filtros
│   │       └── ConflictBanner.vue           # NUEVO: conflicto de versión con recarga
│   ├── router/
│   │   ├── index.ts                         # MODIFICADO: ruta /admin/configuracion
│   │   └── landing.ts                       # MODIFICADO: destino para rol admin
│   ├── services/
│   │   └── adminConfiguration.ts            # NUEVO: cliente GET/POST de /admin/**
│   ├── stores/
│   │   └── adminConfiguration.ts            # NUEVO: estado de catálogos, matriz e histórico
│   ├── types/
│   │   └── adminConfiguration.ts            # NUEVO: tipos compartidos
│   └── views/
│       └── AdminConfigurationPage.vue       # NUEVO: página administrativa
└── tests/
    ├── components/
    │   ├── CategoryFormDialog.spec.ts
    │   ├── PriorityFormDialog.spec.ts
    │   ├── SlaMatrix.spec.ts
    │   ├── ConfigHistoryTable.spec.ts
    │   └── ConflictBanner.spec.ts
    └── stores/
        └── adminConfiguration.spec.ts
```

**Structure Decision**: se mantiene la arquitectura por capas existente (`api` → `services` → `models`/`db`, con `schemas` para contratos). La resolución del plazo es una función pura en `sla_resolution.py` para probarla sin base de datos; los comandos y la auditoría viven en `configuration.py`. En el frontend se conserva la organización `api`/`services`/`stores`/`types`/`views`/`components` y el uso de `apiGet`/`apiPost` de `src/api/client.ts`. La nueva página sigue la estética de `WorkQueuePage` y `TicketForm`: `max-w-7xl`, tarjetas `rounded-2xl border-slate-200`, botones `bg-sky-600`, bordes `slate` y mensajes de error en `rose`/`red`.

## Phase 0: Outline & Research

**Output**: [research.md](./research.md)

Resumen de decisiones (detalle y alternativas en `research.md`):

- **R1 — Autorización administrativa centralizada**: `require_admin` en `app/api/deps.py`, aplicada a todas las rutas `/api/v1/admin/**`. El rol se lee del usuario cargado desde el JWT, nunca del cuerpo.
- **R2 — Versión de configuración por transacción**: `configuration_versions` con `version` entero monótono, autor, fecha y nota. Cada comando o lote crea exactamente una versión.
- **R3 — Reglas SLA versionadas**: `sla_rules` append-only por versión, con `valid_from_version` y `valid_to_version`; una regla vigente por combinación mediante índice único parcial y validación de servicio.
- **R4 — Snapshot en el ticket**: `sla_priority_level`, `sla_hours_applied` y `sla_config_version_id` se escriben en la creación; `sla_deadline` se calcula con horas naturales continuas. `sla_version` se conserva como etiqueta legible (`v1`, `v2`…).
- **R5 — Urgencia congelada en la cola**: `work_queue.py` ordena y filtra con `COALESCE(tickets.sla_priority_level, priorities.level)`, de modo que cambiar el nivel de una prioridad no reordena tickets históricos.
- **R6 — Bloqueo optimista**: `revision` en categorías/prioridades y `expected_rule_id` en reglas. Una base superada devuelve `409 stale_configuration`; no hay sobrescritura silenciosa.
- **R7 — Serialización de versión**: las escrituras bloquean la versión vigente con `FOR UPDATE`; la creación de tickets la comparte con `FOR SHARE`. Así el ticket usa una única versión coherente, sin mezclar reglas antiguas y nuevas.
- **R8 — Lote atómico**: `POST /admin/sla-rules/batch` valida todas las celdas antes de escribir; cualquier error hace `rollback` completo y no crea versión.
- **R9 — Defaults y desactivación**: siempre hay una categoría y una prioridad por defecto activas entre las no-sistema. Desactivar la vigente exige `replacement_default_id`. No se puede desactivar la última activa no-sistema.
- **R10 — Borrado seguro**: solo se elimina una categoría/prioridad sin tickets ni reglas, no-sistema y no-default. El resto devuelve `409 catalog_in_use` y la UI ofrece desactivar.
- **R11 — Histórico append-only**: `configuration_audit_entries` registra una entrada por entidad afectada y versión, con valores previos/nuevos en JSON. No existen endpoints de edición o borrado del histórico.
- **R12 — Contrato POST y UI accesible**: comandos como recursos `POST`; formularios con etiquetas, `aria-invalid`, `role="alert"` y pestañas `role="tablist"`. Sin nuevas dependencias.

## Phase 1: Design & Contracts

**Output**: [data-model.md](./data-model.md), [contracts/admin-configuration.openapi.yaml](./contracts/admin-configuration.openapi.yaml), [contracts/frontend-components.md](./contracts/frontend-components.md), [quickstart.md](./quickstart.md)

---

## Diseño detallado

### 1. Modelo de configuración y versionado (Backend / SQLAlchemy)

#### 1.1. Entidades nuevas

- **`ConfigurationVersion`**: `id`, `version` (entero único), `created_at`, `created_by_id` (nullable solo para la línea base), `note`.
- **`SlaRule`**: `id`, `category_id`, `priority_id`, `hours` (`Numeric(6,2)`), `configuration_version_id`, `valid_from_version`, `valid_to_version` (nullable), `created_by_id`, `created_at`, `retired_at` (nullable), `retired_by_id` (nullable), `supersedes_id` (nullable).
- **`ConfigurationAuditEntry`**: `id`, `configuration_version_id`, `entity_type`, `entity_id`, `action`, `actor_id`, `occurred_at`, `previous_values` (JSON nullable), `new_values` (JSON nullable), `summary`.

#### 1.2. Columnas aditivas

- `categories.revision` y `priorities.revision`: entero no nulo, `default=1`, `server_default="1"`.
- `tickets.sla_priority_level`: `SmallInteger` nullable; `CHECK (sla_priority_level BETWEEN 1 AND 4 OR sla_priority_level IS NULL)`.
- `tickets.sla_hours_applied`: `Numeric(6,2)` nullable; `CHECK (sla_hours_applied > 0 OR sla_hours_applied IS NULL)`.
- `tickets.sla_config_version_id`: `Uuid` nullable, FK `configuration_versions.id`.

#### 1.3. Invariantes de datos

1. Como máximo una regla vigente por `(category_id, priority_id)`: índice único parcial `WHERE valid_to_version IS NULL`.
2. Una regla retirada o sustituida conserva `valid_to_version` y `retired_at`; nunca se borra.
3. `valid_to_version > valid_from_version` cuando no es nulo.
4. `hours > 0` y precisión de minutos (`Numeric(6,2)`).
5. `configuration_audit_entries` es append-only: la aplicación no ejecuta `UPDATE` ni `DELETE`.
6. Cada ticket nuevo con SLA tiene `sla_priority_level`, `sla_hours_applied`, `sla_config_version_id` y `sla_deadline` coherentes.
7. Los tickets anteriores a `0006` pueden tener las columnas nuevas en `NULL`; las consultas usan `COALESCE` y no se reescribe su historia.

### 2. Resolución del plazo y no retroactividad

#### 2.1. Función pura

`app/services/sla_resolution.py` expone:

```python
@dataclass(frozen=True)
class ResolvedSla:
    hours: Decimal
    priority_level: int
    source: Literal["rule", "priority_base"]
    rule_id: UUID | None
    config_version_id: UUID

def resolve_sla(
    *,
    category_id: UUID,
    priority: Priority,
    current_rule: SlaRule | None,
    config_version: ConfigurationVersion,
) -> ResolvedSla: ...
```

Reglas:

- Si existe regla vigente para la combinación, se usa `rule.hours`.
- Si no existe, se usa `priority.base_hours`.
- Si `priority.base_hours` es nulo o no positivo, se lanza `ApiError(500, "configuration_not_configured", ...)` y no se crea el ticket.
- `priority_level` se toma del valor actual de `Priority.level` en el instante de creación y queda congelado en el ticket.
- `hours` se convierte a `timedelta(hours=float(hours))`; se conservan los minutos. El límite es `created_at + delta` en UTC.

#### 2.2. Secuencia de creación de ticket

1. Fijar `created_at = datetime.now(timezone.utc)` una sola vez.
2. Bloquear la versión vigente con `SELECT ... ORDER BY version DESC LIMIT 1 FOR SHARE`.
3. Leer la regla vigente de la combinación y la prioridad.
4. Resolver `hours` y calcular `sla_deadline`.
5. Escribir en el ticket `sla_priority_level`, `sla_hours_applied`, `sla_config_version_id`, `sla_deadline` y `sla_version = f"v{version}"`.
6. Crear la entrada `created` de la línea temporal con el mismo `created_at`.

Los pasos 2–5 ocurren en la misma transacción que el alta del ticket. La versión base `v1` la crea la migración `0006` y el fixture `tests/conftest.py`; si en tiempo de ejecución no existe ninguna versión, el servicio devuelve `500 configuration_not_initialized` y no crea una versión implícita, para evitar carreras entre creaciones concurrentes.

#### 2.3. No retroactividad

- `sla_deadline`, `sla_hours_applied`, `sla_priority_level` y `sla_config_version_id` no se recalculan nunca.
- Cambiar `priorities.base_hours`, el `level`, la `category`, la regla o desactivar una entidad no toca tickets existentes.
- El resultado de SLA (`SlaOutcome`) se sigue calculando con `finalized_at` y `sla_deadline`, ambos inmutables para el ticket.
- La cola de trabajo usa el nivel congelado para ordenar y filtrar; el nombre y color de la prioridad pueden actualizarse, pero no la posición histórica.

### 3. Concurrencia y atomicidad

#### 3.1. Escrituras de configuración

Orden obligatorio dentro de la transacción:

1. `SELECT ... FROM configuration_versions ORDER BY version DESC LIMIT 1 FOR UPDATE`.
2. Validar `expected_revision` / `expected_rule_id` de cada entidad.
3. Validar reglas de negocio (defaults, última activa, duplicados, horas).
4. Escribir cambios en categorías, prioridades y reglas.
5. Calcular `version = COALESCE(MAX(version), 0) + 1` e insertar la nueva `ConfigurationVersion`.
6. Insertar las entradas de auditoría.
7. `commit()`; ante cualquier error, `rollback()` completo.

#### 3.2. Conflictos

| Situación | Código | HTTP |
|---|---|---|
| `expected_revision` no coincide | `stale_configuration` | 409 |
| `expected_rule_id` ya no es la regla vigente | `stale_configuration` | 409 |
| Dos reglas vigentes para la misma combinación | `duplicate_sla_rule` | 409 |
| Se intenta desactivar la última categoría/prioridad activa no-sistema | `last_active_catalog_item` | 409 |
| Se desactiva el default sin reemplazo | `default_replacement_required` | 422 |
| Se intenta borrar una entidad referenciada | `catalog_in_use` | 409 |
| Se intenta modificar una entidad `is_system` | `system_catalog_item` | 409 |

El frontend muestra un banner con el mensaje del backend y un botón «Recargar configuración» que vuelve a leer catálogos, matriz y versión vigente.

#### 3.3. Pruebas de concurrencia

`test_admin_concurrency.py` se ejecuta contra PostgreSQL real:

- Dos actualizaciones simultáneas de la misma categoría: una confirma y la otra recibe `409 stale_configuration`.
- Dos lotes simultáneos que afectan a la misma celda: solo uno crea versión y regla.
- Creación de ticket concurrente con cambio de regla: el ticket obtiene una versión completa, nunca una mezcla; el límite corresponde a esa versión.

### 4. API administrativa

Prefijo: `/api/v1/admin`. Todas las rutas usan `Depends(require_admin)`.

| Método | Ruta | Uso |
|---|---|---|
| GET | `/categories` | Lista todas las categorías, incluidas inactivas y de sistema, con contadores y `revision` |
| POST | `/categories` | Crea categoría |
| POST | `/categories/{id}/updates` | Edita, activa/desactiva, cambia default y reemplaza default |
| POST | `/categories/{id}/deletion` | Elimina si no está referenciada |
| GET | `/priorities` | Lista todas las prioridades, incluidas inactivas y de sistema |
| POST | `/priorities` | Crea prioridad |
| POST | `/priorities/{id}/updates` | Edita, activa/desactiva, cambia default y reemplaza default |
| POST | `/priorities/{id}/deletion` | Elimina si no está referenciada |
| GET | `/sla-rules` | Matriz vigente + versión de configuración actual |
| POST | `/sla-rules/batch` | Crea, actualiza y retira celdas de forma atómica |
| POST | `/sla-rules/{id}/retirement` | Retira una regla vigente (atajo de una sola celda) |
| GET | `/config-history` | Histórico paginado con filtros por fecha, entidad, acción y versión |

#### 4.1. Validaciones de catálogos

- Nombre obligatorio, 1–100 caracteres para categoría y 1–50 para prioridad; se normaliza con `trim` y se compara sin distinguir mayúsculas/minúsculas ni espacios sobrantes.
- Descripción opcional hasta 2.000 caracteres.
- `keywords`: lista de hasta 50 cadenas, cada una de 1–50 caracteres, normalizadas y sin duplicados.
- `sort_order`: entero entre 0 y 9999.
- Prioridad: `level` entero 1–4, único entre prioridades no-sistema **activas**; `color` hexadecimal `#RRGGBB`; `base_hours` decimal positivo con hasta 2 decimales.
- `is_system` es de solo lectura y no se acepta en creación ni edición. La prioridad de sistema no reserva nivel ni aparece en el catálogo operativo.
- Una prioridad inactiva libera su nivel. Para intercambiar dos niveles se desactiva temporalmente una prioridad, se cambia el nivel de la otra y se reactiva la primera con el nivel liberado. La API nunca acepta un nivel duplicado entre activas; la UI guía esta secuencia y conserva el histórico de cada paso.
- Si los cuatro niveles están ocupados por prioridades no-sistema activas, crear otra prioridad devuelve `409 duplicate_priority_level` hasta que se desactive o elimine una prioridad no referenciada. La UI explica cómo liberar un nivel.

#### 4.2. Defaults y desactivación

- Exactamente una categoría y una prioridad no-sistema activas tienen `is_default = true`.
- Al crear la primera categoría/prioridad no-sistema, se marca como default automáticamente.
- Al marcar otra como default, la anterior deja de serlo en la misma transacción.
- Al desactivar la default, el payload debe incluir `replacement_default_id` activo y no-sistema; si falta, `422 default_replacement_required`.
- No se puede desactivar la última categoría/prioridad activa no-sistema.
- Reactivar una entidad no la convierte automáticamente en default.

#### 4.3. Eliminación

- Se permite solo si `ticket_count == 0`, `rule_count == 0`, `is_system == false` y `is_default == false`.
- Si está referenciada, `409 catalog_in_use` con mensaje que propone desactivarla.
- Si es default, `409 default_catalog_item` y se debe designar otro default antes.
- La UI deshabilita el botón y muestra el motivo cuando `can_delete = false`.

#### 4.4. Matriz SLA

- `GET /sla-rules` devuelve `configuration_version`, `items` (reglas vigentes) y `combinations` con categorías/prioridades activas para construir la matriz.
- Cada celda vigente se identifica por `rule_id`; una celda sin regla no tiene fila y usa el plazo base de la prioridad.
- `POST /sla-rules/batch` acepta `changes: []` con operaciones `upsert` y `retire`.
- `upsert` requiere `category_id`, `priority_id`, `hours` y `expected_rule_id` (nullable). Si la combinación ya tiene regla, `expected_rule_id` debe coincidir; si no, debe ser `null`.
- `retire` requiere `rule_id` y `expected_rule_id` igual al vigente.
- Un lote vacío devuelve `422 empty_batch`.
- Categorías/prioridades inactivas no admiten nuevas reglas (`422 inactive_catalog_item`); las reglas existentes se conservan y pueden retirarse.
- El lote se aplica en una única transacción y una única versión. Si una celda falla, no se escribe ninguna.

### 5. Histórico de configuración

Cada comando genera una entrada por entidad afectada:

```json
{
  "id": "uuid",
  "configuration_version": { "id": "uuid", "version": 7, "created_at": "..." },
  "entity_type": "sla_rule",
  "entity_id": "uuid",
  "action": "rule_update",
  "actor": { "id": "uuid", "name": "Admin", "email": "admin@example.com" },
  "occurred_at": "2026-11-15T10:30:00Z",
  "previous_values": { "hours": "8.00", "valid_to_version": null },
  "new_values": { "hours": "12.00", "valid_from_version": 7 },
  "summary": "Plazo de Red × Alta actualizado de 8 a 12 horas"
}
```

Filtros de `GET /config-history`: `from`, `to`, `entity_type`, `entity_id`, `action`, `configuration_version_id`, `page`, `page_size`. El rango se valida (`from <= to`) y las fechas se interpretan en UTC. El histórico no tiene endpoints de escritura.

### 6. Componentes de interfaz (Frontend / Vue 3 + Tailwind)

#### 6.1. Ruta y navegación

- Nueva ruta `/admin/configuracion`, nombre `admin-configuration`, con `meta: { requiresAdmin: true }`.
- Guard de navegación: si el rol almacenado no es `admin`, redirige a `landingForRole` o a `/login?redirect=/admin/configuracion`.
- `landingForRole('admin')` devuelve `/admin/configuracion`; el resto de roles mantiene el comportamiento actual.
- El login de desarrollo incorpora `admin@example.com` y el seed crea ese usuario con rol `admin`.

#### 6.2. Página y pestañas

`AdminConfigurationPage.vue`:

- Cabecera coherente con `WorkQueuePage`: título «Configuración», subtítulo y botón primario contextual.
- `AdminTabs.vue` con `role="tablist"`, `role="tab"`, `aria-selected`, `aria-controls` y navegación con flechas/Home/End.
- Pestañas: **Categorías**, **Prioridades**, **Matriz SLA**, **Histórico**.
- Estado de carga con esqueletos `animate-pulse`; error con tarjeta `border-red-200 bg-red-50`; conflicto con `ConflictBanner` y acción de recarga.
- Mensajes de éxito con `role="status"` y `aria-live="polite"`.

#### 6.3. Catálogos

- `CategoryTable.vue` / `PriorityTable.vue`: tabla responsive (`overflow-x-auto`), columnas Nombre, Descripción/Color, Plazo base, Estado, Tickets, Reglas, Acciones.
- Insignias: activa (`bg-emerald-50 text-emerald-800`), inactiva (`bg-slate-100 text-slate-600`), sistema (`bg-amber-50 text-amber-800`), default (`bg-sky-50 text-sky-800`).
- Acciones: Editar, Desactivar/Reactivar, Eliminar. Los botones deshabilitados muestran `title` con el motivo.
- `CategoryFormDialog.vue` y `PriorityFormDialog.vue` usan Headless UI `Dialog`, etiquetas asociadas, validación en cliente y errores del backend bajo el campo o en banner.
- El formulario envía `expected_revision`; si el backend responde `409 stale_configuration`, el diálogo permanece abierto y muestra el banner de conflicto con «Recargar».
- Al desactivar una entidad default, el diálogo exige seleccionar `replacement_default_id`.

#### 6.4. Matriz SLA

- `SlaMatrix.vue`: tabla con categorías en filas y prioridades en columnas; cada celda muestra el plazo vigente o «Base: 8 h».
- Las celdas son botones accesibles con `aria-label="Plazo para <categoría> y <prioridad>"`; al activarlas se abre `SlaCellEditor` (popover/diálogo) con horas y acciones Guardar/Retirar.
- Los cambios se acumulan en un borrador local y se guardan con «Guardar cambios» mediante un único `POST /sla-rules/batch`.
- Indicador de cambios sin guardar y botón «Descartar». Si se intenta salir con cambios, se pide confirmación.
- Tras guardar, se recarga la matriz y se anuncia la nueva versión (`role="status"`).
- Si el lote devuelve `409 stale_configuration`, no se aplica nada y se muestra el banner con recarga.

#### 6.5. Histórico

- `ConfigHistoryTable.vue`: filtros de fecha (`input type="date"`), entidad, acción y versión; tabla con Fecha, Autor, Entidad, Acción, Valores anteriores, Valores nuevos y Versión.
- Fechas formateadas con `Intl.DateTimeFormat('es-ES', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'Europe/Madrid' })`.
- Paginación con los mismos patrones de `WorkQueuePagination`.
- Los valores JSON se renderizan como pares clave/valor en texto plano; no se usa `v-html`.

#### 6.6. Servicio y tipos

- `frontend/src/types/adminConfiguration.ts`: tipos de entidades, peticiones, respuestas, errores y paginación.
- `frontend/src/services/adminConfiguration.ts`: funciones `listCategories`, `createCategory`, `updateCategory`, `deleteCategory`, `listPriorities`, `createPriority`, `updatePriority`, `deletePriority`, `getSlaMatrix`, `saveSlaBatch`, `retireSlaRule`, `getConfigHistory`.
- `frontend/src/stores/adminConfiguration.ts`: estado de catálogos, matriz, histórico, versión vigente, `loading`, `saving`, `conflict` y acciones; no duplica reglas de negocio, solo prepara la UX.

### 7. Coherencia con la arquitectura y funcionalidades existentes

#### 7.1. Lo que no cambia

- El contrato de `GET /api/v1/priorities` para creación de tickets se mantiene: solo prioridades activas no-sistema.
- `ticket_creation.py` sigue sugiriendo categoría y prioridad con `keywords`; la configuración administrativa permite mantener esos campos.
- `TicketRead` incorpora de forma aditiva `sla_priority_level`, `sla_hours_applied`, `sla_version` y `sla_config_version_id`, de modo que la configuración aplicada es observable sin recalcular el SLA.
- `work_queue.py` mantiene su contrato y su cálculo de SLA; solo cambia la fuente del nivel de urgencia a la columna congelada con `COALESCE`.
- `TicketDetailPage` (HU-06), `TicketForm`, `PrioritySelect`, la línea temporal y los estilos base no se reescriben; la vista de detalle podrá mostrar los campos ya expuestos por `TicketRead`.
- El formato de error `{"detail": {"code", "message"}}` y el cliente `api/client.ts` se reutilizan.

#### 7.2. Lo que se añade de forma aditiva

- Nuevas tablas y columnas anulables, con `downgrade()` que elimina índices, tablas y columnas nuevas.
- Nuevos códigos de error estables; los existentes no cambian.
- Nuevo rol de acceso administrativo, ya presente en `UserRole.admin`.
- Nueva ruta y página; no se altera la navegación existente salvo el destino inicial del rol admin.

#### 7.3. Invariantes de coherencia

1. Un ticket creado antes de HU-08 conserva su `sla_deadline` y su resultado; las columnas nuevas pueden ser `NULL`.
2. Un ticket creado después siempre tiene snapshot completo y una única versión.
3. Cambiar el nivel de una prioridad no reordena la cola histórica.
4. Desactivar una categoría/prioridad no rompe tickets ni reglas existentes.
5. El catálogo operativo (`/priorities`) sigue excluyendo inactivas y de sistema.
6. La matriz no puede tener dos reglas vigentes para la misma combinación.
7. El histórico no se puede editar ni borrar desde la API.

### 8. Seguridad, permisos y datos

- `require_admin` devuelve `403 forbidden` con mensaje «Esta configuración está disponible solo para administración.».
- Todas las rutas `/api/v1/admin/**` comprueban el rol en servidor; el guard del frontend es solo UX.
- Los endpoints de admin no exponen datos de tickets, solo contadores agregados (`ticket_count`, `rule_count`).
- No se registran secretos ni tokens; los logs no incluyen cuerpos completos de configuración.
- Los valores de auditoría se serializan como JSON seguro (UUID, fechas ISO 8601, decimales como cadena) y se renderizan como texto.
- Los mensajes de validación no filtran detalles internos de SQLAlchemy ni trazas.

### 9. Pruebas y criterios de verificación

#### 9.1. Backend

| Suite | Cobertura |
|---|---|
| `test_admin_authorization.py` | Los cuatro roles; solo admin accede; 401 sin token y 403 con rol distinto |
| `test_admin_categories.py` | Alta, edición, duplicados normalizados, revisión, default, desactivación, reactivación, borrado, sistema e idempotencia de comandos repetidos |
| `test_admin_priorities.py` | Nivel único 1–4 entre prioridades no-sistema activas, liberación de nivel, color, plazo base positivo, default, borrado e idempotencia de comandos repetidos |
| `test_admin_sla_matrix.py` | Regla prevalece sobre base, fallback, versión, retirada confirmada con `valid_to_version`/`supersedes_id`, duplicados, lote atómico, replay de lote y validaciones |
| `test_sla_non_retroactivity.py` | Ticket abierto/cerrado conserva límite y outcome; ticket nuevo usa nueva regla; snapshot visible en `TicketRead`; urgencia congelada; cola estable |
| `test_configuration_history.py` | Entradas append-only, autor, valores previos/nuevos, filtros por `configuration_version_id`, paginación e inmutabilidad |
| `test_admin_concurrency.py` | Conflictos optimistas, reintentos idempotentes y creación de ticket concurrente con cambio de versión (PostgreSQL) |
| `test_sla_resolution.py` | Función pura: regla, base, decimales, sin horas y nivel congelado |
| `test_admin_configuration_contract.py` | Campos, códigos y formas del OpenAPI |
| `test_admin_configuration_performance.py` | p95 de lecturas, guardado de lote de 20 celdas, histórico paginado y alta de ticket |

#### 9.2. Frontend

| Suite | Cobertura |
|---|---|
| `CategoryFormDialog.spec.ts` | Validación, envío, error de conflicto y recarga |
| `PriorityFormDialog.spec.ts` | Nivel, plazo base, color y default |
| `SlaMatrix.spec.ts` | Renderizado, edición de celdas, borrador, lote y conflicto |
| `ConfigHistoryTable.spec.ts` | Filtros, formato es-ES/Europe/Madrid y paginación |
| `ConflictBanner.spec.ts` | `role="alert"`, mensaje y acción de recarga |
| `AdminConfigurationPage.spec.ts` | Renderizado de pestañas, estados y comprobación `axe-core` sin violaciones críticas |
| `adminConfiguration.spec.ts` | Estado del store, carga y guardado |

#### 9.3. Puertas de calidad

- `python -m pytest` en verde con SQLite y, para concurrencia y rendimiento, con `TEST_DATABASE_URL` PostgreSQL.
- `npm run test` y `npm run build` en verde (`vue-tsc` incluido).
- `alembic upgrade head` y `alembic downgrade -1` verificados sobre PostgreSQL.
- Rendimiento: p95 < 300 ms en lecturas e histórico y p95 < 400 ms en guardado de lote de hasta 20 celdas; alta de ticket con incremento < 10 ms.
- Revisión de accesibilidad: foco visible, etiquetas, tablas con `caption`, pestañas y diálogos, más `axe-core` sin violaciones críticas.
- Revisión de seguridad: 403 para no-admin en `/admin/**`, catálogo operativo intacto para autenticados, sin datos de configuración en respuestas no autorizadas, sin secretos en logs.

## Complexity Tracking

No hay violaciones de la constitución. No se requiere justificación adicional.

## Phase 2 Preview (not created by this command)

`/speckit.tasks` generará `tasks.md` con el desglose por historia:

1. Migración `0006` y modelos.
2. Autorización y servicios de catálogos.
3. Reglas SLA, versionado y no retroactividad.
4. API administrativa y contrato.
5. Histórico y auditoría.
6. Página y componentes Vue.
7. Pruebas, accesibilidad y documentación.
