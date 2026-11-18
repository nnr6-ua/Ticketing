# Research: Configuración de categorías, prioridades y plazos (HU-08)

**Feature**: `008-configuracion-plazos-sla` | **Date**: 2026-11-15 | **Spec**: [spec.md](./spec.md)

Este documento registra las decisiones técnicas de Fase 0 y las alternativas descartadas. El diseño completo se desarrolla en [plan.md](./plan.md) y [data-model.md](./data-model.md).

---

## R1 — Autorización administrativa centralizada

**Decisión**: añadir `require_admin` en `backend/app/api/deps.py`, construida sobre `get_current_user`, y aplicarla mediante `Depends` a todas las rutas del router `/api/v1/admin`. El catálogo operativo `GET /api/v1/priorities` y las sugerencias usadas al crear tickets quedan fuera de `/admin` y siguen disponibles para los perfiles autenticados.

```python
def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.admin:
        raise ApiError(403, "forbidden", ADMIN_FORBIDDEN_MESSAGE)
    return current_user
```

**Motivo**: el rol viaja en el JWT, pero la autorización se resuelve contra el usuario cargado desde la base de datos, igual que `require_technician`. Así una cuenta desactivada o con rol cambiado no conserva privilegios por un token antiguo.

**Alternativas descartadas**:

- Comprobar el rol solo en el frontend: viola el principio III de la constitución.
- Un router separado con middleware global: añade complejidad y no encaja con el patrón de dependencias existente.
- Confiar en el claim `role` del JWT sin recargar el usuario: impediría revocar privilegios de inmediato.

---

## R2 — Versión de configuración por transacción

**Decisión**: crear `configuration_versions` con `id`, `version` entero único, `created_at`, `created_by_id` (nullable en la línea base) y `note`. Cada comando administrativo o lote crea exactamente una fila.

`version` se calcula como `COALESCE(MAX(version), 0) + 1` después de bloquear la versión vigente con `FOR UPDATE`. No se usa una secuencia de PostgreSQL porque el valor debe ser estrictamente consecutivo dentro del orden de commits y SQLite no tiene secuencias portables; el bloqueo ya serializa a los escritores.

**Motivo**: permite que un ticket identifique con precisión la configuración vigente en su creación y que el histórico agrupe todos los cambios de una misma operación, incluido un lote de matriz.

**Alternativas descartadas**:

- Guardar solo un `updated_at` o un hash: no permite reconstruir el histórico ni agrupar cambios.
- Una versión por entidad: fragmenta un lote atómico en varias versiones y rompe la garantía de «una única versión» para el ticket.
- Una secuencia global: produce huecos en rollbacks y complica las pruebas SQLite.

---

## R3 — Reglas SLA versionadas y no sobrescritas

**Decisión**: `sla_rules` es append-only por versión. Cada fila representa una versión de la regla para una combinación:

- `valid_from_version`: versión en la que nace.
- `valid_to_version`: versión en la que se sustituye o retira; `NULL` mientras está vigente.
- `supersedes_id`: enlace a la versión anterior.
- `retired_at` / `retired_by_id`: retirada explícita sin sustituto.

Un índice único parcial `(category_id, priority_id) WHERE valid_to_version IS NULL` garantiza como máximo una regla vigente por combinación; el servicio valida además antes de escribir para devolver un error de negocio claro.

**Motivo**: cumple «la anterior se conserva para el histórico» sin sobrescribir filas y permite reconstruir las reglas vigentes en cualquier versión pasada:

```sql
SELECT *
FROM sla_rules
WHERE valid_from_version <= :version
  AND (valid_to_version IS NULL OR valid_to_version > :version);
```

**Alternativas descartadas**:

- Una tabla `sla_rules` mutable con auditoría: el histórico dependería de reconstruir valores desde JSON y se perdería la integridad referencial de la versión anterior.
- Una fila por combinación con columnas `previous_hours`: solo conserva un nivel de historia y no soporta múltiples cambios.
- Reglas dentro de un JSON de versión: impide índices, claves foráneas y validaciones declarativas.

---

## R4 — Snapshot de SLA en el ticket

**Decisión**: añadir a `tickets`:

- `sla_priority_level` (`SmallInteger`, nullable por compatibilidad).
- `sla_hours_applied` (`Numeric(6,2)`, nullable).
- `sla_config_version_id` (`Uuid` FK a `configuration_versions`, nullable).
- Se conservan `sla_deadline` y `sla_version`; `sla_version` se rellena con la etiqueta `v<version>`.

En la creación se calcula `created_at` una vez, se resuelve el plazo y se escribe `sla_deadline = created_at + hours`. `TicketRead` expone de forma aditiva `sla_priority_level`, `sla_hours_applied`, `sla_version` y `sla_config_version_id` para que la configuración aplicada sea observable sin recalcular el SLA.

**Motivo**: la no retroactividad exige que el límite y la regla aplicada no dependan del estado actual de `priorities` ni de `sla_rules`. Guardar solo la FK a la regla no bastaría si la regla se retira; el snapshot de horas y nivel es inmutable y barato de leer.

**Alternativas descartadas**:

- Recalcular el SLA al leer: viola HU08-RF-017 y HU08-RF-018.
- Guardar solo `sla_version` como cadena: no permite mostrar las horas aplicadas ni auditar la regla exacta.
- Duplicar el nombre de la categoría/prioridad: el requisito pide conservar la referencia; el nombre actual puede cambiar y no afecta al plazo.

---

## R5 — Urgencia congelada en la cola de trabajo

**Decisión**: `work_queue.py` usa `COALESCE(Ticket.sla_priority_level, Priority.level)` para ordenar, filtrar por nivel y construir las opciones de filtro. El `PriorityRef.level` devuelto usa también el valor congelado. Para tickets legados sin snapshot, el `COALESCE` cae al nivel actual de la prioridad.

**Motivo**: HU08-RF-018 y HU08-SC-009 exigen que cambiar el nivel de una prioridad no altere la posición de tickets existentes. Mantener el join a `Priority` para nombre y color conserva la UI actual.

**Alternativas descartadas**:

- Copiar el nivel en la línea temporal: complica las consultas de la cola y no cubre tickets anteriores a HU-05.
- Bloquear el cambio de nivel de prioridad: impide una operación administrativa permitida por la especificación.

---

## R6 — Bloqueo optimista

**Decisión**:

- Categorías y prioridades: columna `revision` entera, incrementada en cada actualización. El payload incluye `expected_revision`; si no coincide, `409 stale_configuration`.
- Reglas: el cliente envía `expected_rule_id` con la regla vigente que leyó. Si la regla ya fue sustituida o retirada, `409 stale_configuration`.
- Lote: cada cambio lleva su propia expectativa; cualquier discrepancia cancela todo el lote.

**Motivo**: cumple HU08-RF-025 y HU08-SC-010 sin bloqueos pesimistas de larga duración. El bloqueo de la versión vigente protege la coherencia global, pero no se mantiene durante la edición en el navegador.

**Alternativas descartadas**:

- `updated_at` como token: las categorías/prioridades no tienen esa columna y su resolución puede ser menor que la de un reloj de aplicación.
- Bloqueo pesimista al abrir el formulario: mala UX y riesgo de bloqueos huérfanos.
- Última escritura gana: viola la especificación y provoca pérdida silenciosa.

---

## R7 — Serialización de la versión vigente

**Decisión**: las mutaciones de configuración bloquean la última fila de `configuration_versions` con `SELECT ... FOR UPDATE`; la creación de tickets la bloquea con `FOR SHARE` antes de leer reglas y prioridad.

**Motivo**: impide que un ticket lea una regla de la versión N y una prioridad modificada por la versión N+1. El ticket obtiene una única versión coherente. En PostgreSQL el bloqueo compartido permite muchas creaciones simultáneas; las escrituras esperan. En SQLite las pruebas funcionales son secuenciales y el bloqueo se ignora.

**Alternativas descartadas**:

- Leer sin bloqueo: puede mezclar versiones en el instante de un cambio.
- Bloquear toda la tabla de tickets o usar un lock global: reduce el paralelismo innecesariamente.
- Reintentos con validación posterior: más complejo y con ventanas de inconsistencia.

---

## R8 — Lote atómico de la matriz

**Decisión**: `POST /admin/sla-rules/batch` recibe todas las operaciones de la matriz, las valida completas y las escribe en una transacción con una única `ConfigurationVersion`. Si una celda falla, se hace `rollback` y no se crea versión ni auditoría.

**Motivo**: cumple el escenario 3.7 y HU08-RF-024. También reduce el número de versiones cuando el administrador guarda varias celdas de una vez.

**Alternativas descartadas**:

- Una llamada por celda: produce versiones intermedias y deja la matriz parcialmente aplicada si falla una celda.
- Guardado optimista en el cliente sin lote: no garantiza atomicidad en servidor.

---

## R9 — Defaults, desactivación y última entidad activa

**Decisión**:

- Siempre hay una categoría y una prioridad no-sistema activas con `is_default = true`.
- Crear la primera entidad no-sistema la marca como default.
- Cambiar el default limpia el anterior en la misma transacción.
- Desactivar la default exige `replacement_default_id` activo y no-sistema.
- No se puede desactivar la última entidad activa no-sistema.
- Las entidades `is_system` son de solo lectura y no cuentan para estas reglas.

**Motivo**: evita que la creación de tickets quede sin catálogo aplicable y mantiene la coherencia con `resolve_default_category`/`resolve_default_priority`.

**Alternativas descartadas**:

- Permitir cero defaults y usar «la primera activa»: oculta una configuración ambigua y complica la UI.
- Desactivar sin reemplazo y fallar al crear tickets: traslada el error al usuario final.

---

## R10 — Borrado seguro

**Decisión**: permitir eliminación solo si no hay tickets ni reglas asociadas, no es `is_system` y no es `is_default`. En caso contrario, `409 catalog_in_use` o `409 default_catalog_item` con un mensaje que propone desactivar.

**Motivo**: cumple HU08-RF-006 y HU08-SC-004. Las claves foráneas existentes ya protegen la integridad; la comprobación previa permite un error de negocio claro en lugar de un `IntegrityError` genérico.

**Alternativas descartadas**:

- Borrado en cascada: destruye historia de tickets y reglas.
- Borrado lógico con `deleted_at`: la especificación ya ofrece `is_active`; añadir otro estado complica el modelo.

---

## R11 — Histórico append-only

**Decisión**: `configuration_audit_entries` registra una entrada por entidad afectada y versión, con `previous_values` y `new_values` en JSON. La API solo expone lectura; no hay endpoints de actualización ni borrado.

**Motivo**: cumple HU08-RF-022 y HU08-RF-023, y permite explicar cada cambio con autor, fecha y valores. El JSON es portable entre PostgreSQL y SQLite; los valores se serializan como texto/ISO 8601 para conservar precisión.

**Alternativas descartadas**:

- Usar la línea temporal del ticket: mezcla auditoría de configuración con eventos de ticket y no cubre entidades sin ticket.
- Tablas de auditoría por entidad: multiplica esquemas y consultas.
- Solo logs de aplicación: no son consultables por el administrador ni inmutables.

---

## R12 — Contrato POST y cliente HTTP existente

**Decisión**: modelar comandos como recursos `POST`:

- `/categories/{id}/updates`
- `/categories/{id}/deletion`
- `/priorities/{id}/updates`
- `/priorities/{id}/deletion`
- `/sla-rules/batch`
- `/sla-rules/{id}/retirement`

**Motivo**: la restricción adicional de la constitución y el cliente `frontend/src/api/client.ts` solo implementan `GET` y `POST`. Introducir `PATCH`/`DELETE` obligaría a modificar y verificar el cliente, fuera del alcance de HU-08.

**Alternativas descartadas**:

- `PATCH`/`DELETE` REST clásicos: incompatibles con el cliente actual.
- Un único endpoint `/config` con una acción en el cuerpo: menos explícito y más difícil de validar y auditar.

---

## R13 — Validación en dos capas y códigos estables

**Decisión**: Pydantic valida forma y tipos en `app/schemas/configuration.py`; el servicio valida reglas de negocio y lanza `ApiError` con códigos estables. El manejador existente de `RequestValidationError` sigue traduciendo payloads mal formados a `422 invalid_request`.

Códigos nuevos:

| Código | HTTP | Uso |
|---|---|---|
| `stale_configuration` | 409 | Revisión o regla desactualizada |
| `duplicate_catalog_name` | 409 | Nombre duplicado normalizado |
| `duplicate_priority_level` | 409 | Nivel ya usado por otra prioridad no-sistema activa |
| `duplicate_sla_rule` | 409 | Dos reglas vigentes para la misma combinación |
| `last_active_catalog_item` | 409 | Se intenta desactivar la última activa |
| `default_replacement_required` | 422 | Falta reemplazo del default |
| `catalog_in_use` | 409 | Entidad referenciada por tickets o reglas |
| `default_catalog_item` | 409 | Se intenta borrar el default |
| `system_catalog_item` | 409 | Se intenta modificar una entidad de sistema |
| `inactive_catalog_item` | 422 | Regla sobre categoría/prioridad inactiva |
| `empty_batch` | 422 | Lote sin cambios |
| `configuration_not_initialized` | 500 | No existe ninguna versión de configuración al crear un ticket |
| `configuration_not_configured` | 500 | No hay horas aplicables para la combinación ni plazo base válido |

**Motivo**: mantiene el formato `{"detail": {"code", "message"}}`, permite al frontend distinguir conflicto de validación y evita exponer detalles internos. `configuration_not_initialized` y `configuration_not_configured` son fallos de infraestructura, no errores de formulario.

**Alternativas descartadas**:

- Devolver mensajes de SQLAlchemy: filtra detalles internos y no es estable.
- Usar solo `422` para todo: impide que la UI distinga conflictos recuperables de errores de formulario.

---

## R14 — Estrategia de interfaz

**Decisión**: una página `/admin/configuracion` con cuatro pestañas y componentes pequeños. Se reutilizan Tailwind, Headless UI, Heroicons, los patrones de `WorkQueuePage` (cabecera, carga, error, paginación) y `TicketForm` (campos, validación, botones). El store de Pinia mantiene catálogos, matriz, histórico y conflicto.

**Motivo**: coherencia estética y funcional con HU-01/HU-04/HU-05 sin introducir una librería de administración. La matriz se edita como borrador local para poder guardar en lote.

**Alternativas descartadas**:

- Una tabla genérica de configuración clave/valor: no representa la matriz ni los defaults.
- Edición celda a celda contra el servidor: muchas versiones y más conflictos.
- Una nueva librería de componentes: viola la simplicidad y el stack fijado.

---

## R15 — Pruebas

**Decisión**:

- Unitarias: función pura `resolve_sla`, normalización de nombres, serialización de auditoría.
- Integración: autorización, catálogos, matriz, no retroactividad, histórico, contrato e idempotencia de comandos repetidos.
- Concurrencia real: PostgreSQL con `TEST_DATABASE_URL`; SQLite para el resto.
- Rendimiento: PostgreSQL con `TEST_DATABASE_URL` para p95 de lecturas, guardado de lote de 20 celdas, histórico y alta de ticket.
- Frontend: Vitest + Vue Test Utils para diálogos, matriz, histórico, banner de conflicto y `axe-core` en la página administrativa.

**Motivo**: cada requisito no negociable de la constitución tiene una prueba ejecutable. La no retroactividad se prueba creando un ticket, cambiando la regla y comparando columnas y resultados antes/después; los comandos repetidos comprueban que no generan duplicados ni escrituras parciales.

**Alternativas descartadas**:

- Solo pruebas manuales: incumple el principio IV.
- Simular concurrencia en SQLite: no reproduce el comportamiento de bloqueo de PostgreSQL.

---

## Resumen de artefactos

| Artefacto | Contenido |
|---|---|
| [plan.md](./plan.md) | Contexto técnico, constitución, estructura, diseño detallado y pruebas |
| [data-model.md](./data-model.md) | Entidades, columnas, restricciones, DTOs, migración `0006` e invariantes |
| [contracts/admin-configuration.openapi.yaml](./contracts/admin-configuration.openapi.yaml) | Contrato HTTP de `/api/v1/admin/**` |
| [contracts/frontend-components.md](./contracts/frontend-components.md) | Tipos, props, eventos y estados de los componentes Vue |
| [quickstart.md](./quickstart.md) | Validación ejecutable end-to-end |
