# Research: Cambio de estado y documentación de resolución (HU-05)

**Feature**: `005-cambio-estado-resolucion` | **Date**: 2026-11-02

Este documento resuelve las incógnitas técnicas de la especificación y justifica las decisiones del plan. No se introducen tecnologías nuevas: todas las decisiones se apoyan en FastAPI, SQLAlchemy, Alembic, PostgreSQL, Vue 3 y Tailwind ya presentes.

---

## R1 — Dónde vive la máquina de estados

**Decision**: Implementar la matriz como una estructura de datos explícita en `backend/app/services/ticket_state_machine.py`, con funciones puras (`allowed_transitions`, `is_transition_allowed`, `allowed_status_options`) que no dependen de SQLAlchemy ni de FastAPI.

**Rationale**:
- Una única fuente de verdad evita condicionales dispersos y divergencias entre backend, tests y UI.
- Al ser puro, se prueba sin base de datos con una matriz 5×5 completa.
- El endpoint y el frontend consumen la misma lista calculada; el cliente no duplica reglas.

**Alternatives considered**:
- *Transiciones codificadas en el endpoint*: difícil de testear y propensa a olvidar casos (`pendiente_usuario → en_progreso`, reapertura).
- *Librería de workflow externa*: añade dependencia y complejidad innecesaria para cinco estados.
- *Tabla de configuración en base de datos*: permitiría flujos configurables, pero la especificación excluye flujos personalizados y añade latencia/consultas.

---

## R2 — Cómo persistir la resolución

**Decision**: Guardar la resolución como una entrada append-only de la línea temporal (`ticket_timeline_entries.event_type = 'resolution'`), con `body`, autor y fecha. No añadir una columna `resolution` a `tickets`.

**Rationale**:
- La especificación define «Resolución» como vinculada a una entrada de la línea temporal y exige conservar las resoluciones anteriores tras reabrir.
- Un campo único en `tickets` se sobrescribiría en la segunda resolución o exigiría un historial paralelo.
- Mantiene intacto el modelo base y la restricción `ck_tickets_finalized_at`.
- Permite que la resolución comparta el mismo mecanismo de visibilidad, orden y autoría que el resto de eventos.

**Alternatives considered**:
- *Columna `tickets.resolution` + tabla histórica*: duplica información y crea dos fuentes de verdad.
- *Reutilizar `description` del ticket*: mezcla el problema con la solución y rompe la semántica.
- *Comentario interno marcado como resolución*: impediría mostrarlo al usuario creador, que debe ver la solución.

---

## R3 — Concurrencia y pérdida de actualizaciones

**Decision**: Usar `tickets.updated_at` como token de concurrencia optimista. El cliente envía `expected_updated_at`; el servicio bloquea la fila (`SELECT ... FOR UPDATE` en PostgreSQL) y compara antes de escribir. Si no coincide, devuelve `409 stale_ticket` sin escribir.

**Rationale**:
- No requiere una columna nueva en `tickets` (modelo base intacto).
- `updated_at` ya existe y se actualiza en cada cambio.
- El bloqueo de fila serializa dos comandos simultáneos y evita que ambos validen sobre el mismo estado.
- Es el patrón estándar para formularios de edición y encaja con RN-08.

**Alternatives considered**:
- *Columna `version` incremental*: más explícita, pero obliga a migrar `tickets` y a tocar todos los `UPDATE` existentes.
- *Bloqueo pesimista sin token*: evita escrituras concurrentes, pero no detecta que el cliente leyó datos obsoletos antes de abrir el formulario.
- *ETag/If-Match HTTP*: correcto en REST puro, pero el cliente actual no maneja cabeceras de versión y el contrato de errores ya usa códigos de negocio.

**Note on SQLite**: `FOR UPDATE` no aplica; las pruebas funcionales usan el token y las de concurrencia real se ejecutan contra PostgreSQL. La lógica de comparación es idéntica en ambos motores.

---

## R4 — Idempotencia y doble envío

**Decision**:
- Cambio de estado: `request_id` obligatorio generado por el cliente. Si ya existe una transición con ese `request_id` para el ticket y coinciden actor, destino y resolución normalizada, se devuelve `200` con `changed = false` y `timeline_entries = []` sin escribir. Si difiere cualquiera de los tres, se devuelve `409 request_id_reused`. El no-op por mismo estado se mantiene para solicitudes nuevas.
- Comentarios internos: `request_id` obligatorio generado por el cliente y restricción única `(ticket_id, request_id, event_type)`; un reintento devuelve la entrada existente sin duplicarla.
- Transiciones: la misma restricción única actúa como defensa en profundidad y permite correlacionar el `status_change` y su `resolution`, que comparten `request_id`.
- El campo `request_id` es `NOT NULL` en la tabla: toda entrada de la línea temporal procede de un comando idempotente.

**Rationale**:
- Un reintento tras pérdida de respuesta no debe crear dos entradas ni devolver un error genérico.
- El `request_id` obligatorio elimina la ambigüedad de las transiciones «best effort» y permite distinguir un replay legítimo de una reutilización incorrecta.
- El no-op por mismo estado sigue cubriendo el doble clic cuando el cliente genera una solicitud nueva.
- La UI además deshabilita el botón mientras hay una petición en curso.

**Alternatives considered**:
- *Solo deshabilitar el botón en el cliente*: no protege ante reintentos de red ni múltiples pestañas.
- *Clave de idempotencia en una tabla separada*: más infraestructura para el mismo resultado.
- *`request_id` opcional en transiciones*: deja sin cubrir el reintento tras pérdida de respuesta y obliga a depender solo del no-op por estado.

---

## R5 — Estilo de los endpoints

**Decision**: Usar comandos `POST` sobre sub-recursos:
- `POST /api/v1/tickets/{id}/status-transitions`
- `POST /api/v1/tickets/{id}/internal-comments`
- `GET /api/v1/tickets/{id}/workflow`
- `GET /api/v1/tickets/{id}/timeline`

**Rationale**:
- El cliente HTTP compilado (`frontend/dist/assets/client-*.js`) solo implementa GET y POST; no hay PATCH.
- Los comandos son recursos auditables: cada transición tiene su `id`, autor y fecha.
- Encaja con el contrato de errores existente y con el patrón de la cola de trabajo.

**Alternatives considered**:
- *PATCH `/tickets/{id}` con `{status, resolution}`*: semánticamente válido, pero obliga a ampliar el cliente y mezcla la actualización del ticket con la creación de eventos.
- *PUT idempotente*: no modela la creación de una entrada histórica por operación.

---

## R6 — Visibilidad de la línea temporal

**Decision**: Calcular la visibilidad en el servidor:
- `status_change` y `resolution`: visibles para el usuario creador y para cualquier usuario con acceso al ticket.
- `internal_comment`: visible solo para el técnico actualmente asignado, supervisores y administradores.
- La lectura de `GET /workflow` y `GET /timeline` se autoriza con `can_read_ticket`: creador y roles `tecnico`, `supervisor` o `admin`. Un usuario sin acceso recibe `404 ticket_not_found`; no se usa `require_technician` para leer.
- La consulta aplica `WHERE is_internal = false` cuando el espectador no tiene privilegio interno; el cliente nunca recibe filas internas.

**Rationale**:
- Cumple RF-019 y RF-024 sin confiar en el cliente.
- Evita filtrar datos sensibles en el payload y luego ocultarlos con CSS.
- La regla de «técnico asignado» se reevalúa en cada consulta, por lo que una reasignación revoca el acceso inmediatamente.

**Alternatives considered**:
- *Filtrar en el frontend*: inseguro; los datos viajan al navegador.
- *Un endpoint público y otro interno*: duplica la lógica y aumenta el riesgo de inconsistencias.

---

## R7 — Validación en dos capas

**Decision**:
- Pydantic valida solo forma y tipos (UUID, enum, fecha ISO); no aplica longitudes de negocio.
- Un handler de `RequestValidationError` traduce cualquier payload mal formado a `422 invalid_request` con el formato heredado.
- El servicio valida reglas de negocio (transición permitida, resolución obligatoria/no vacía/no permitida, comentario no vacío) y lanza `ApiError` con códigos estables.
- El frontend replica solo las validaciones necesarias para una buena UX; nunca sustituye al backend.

**Rationale**:
- Mensajes de error estables y en español, independientes del formato de `RequestValidationError`.
- La regla de negocio queda en un único lugar testeable.
- El `422` de Pydantic se normaliza a `invalid_request`; los errores de negocio usan códigos como `resolution_required`, `resolution_too_long`, `resolution_not_allowed`, `comment_required` o `comment_too_long`.

**Alternatives considered**:
- *Todo en validadores Pydantic*: difícil de expresar reglas que dependen del estado actual del ticket y de la identidad del actor.
- *Todo en el endpoint*: mezcla HTTP con dominio y complica las pruebas.

---

## R8 — Estrategia de UI y bloqueo del envío

**Decision**:
- El selector consume `allowed_transitions` del backend; no hardcodea la matriz.
- `canSubmit` es un `computed` que exige destino seleccionado y, si es `resuelto`, `resolution.trim().length > 0` y ≤ 5.000.
- El botón se deshabilita mientras `submitting` es verdadero.
- Si el backend rechaza, se muestra `detail.message` y se conserva el texto.

**Rationale**:
- El usuario solo ve opciones válidas, lo que reduce errores.
- El bloqueo de envío cumple el criterio de aceptación «el sistema impide guardar sin descripción».
- La revalidación en servidor garantiza que no se pueda saltar la regla con una petición manual.

**Alternatives considered**:
- *Mostrar todos los estados y deshabilitar los inválidos*: más ruido visual y requiere duplicar la matriz.
- *Solo validar en el servidor*: el usuario recibiría un error después de enviar, peor experiencia y más riesgo de perder el texto.

---

## R9 — Ordenación determinista de la línea temporal

**Decision**: Añadir `event_order` (`status_change = 0`, `resolution = 1`, `internal_comment = 0`) y ordenar por `created_at ASC, event_order ASC, id ASC`.

**Rationale**:
- Un cambio a «Resuelto» crea dos entradas con el mismo `created_at`; sin desempate, el orden podría variar entre motores o ejecuciones.
- La resolución debe aparecer después del cambio de estado que la provoca.
- Evita depender de la monotonía de UUID.

**Alternatives considered**:
- *Timestamps con microsegundos distintos*: frágil y dependiente del reloj.
- *Secuencia global autoincremental*: funciona, pero añade una columna y no aporta valor sobre `event_order` para este caso.

---

## R10 — Pruebas

**Decision**:
- `pytest` para matriz, servicios, endpoints, contrato y visibilidad.
- `vitest` + `@vue/test-utils` para componentes.
- Pruebas de concurrencia real marcadas para PostgreSQL; el resto corren en SQLite.

**Rationale**:
- Coincide con las herramientas ya instaladas (`pytest`, `vitest`, `@vue/test-utils`).
- La matriz 5×5 se prueba exhaustivamente sin base de datos.
- Las pruebas de integración usan el mismo `TestClient` y el patrón de contrato de la cola de trabajo.

**Alternatives considered**:
- *Solo pruebas end-to-end*: lentas y con poca granularidad para 25 transiciones.
- *Solo pruebas unitarias*: no detectan problemas de transacción, permisos ni serialización.

---

## R11 — Contrato de ejecución con HU-03

**Decision**: HU-03 ejecuta la transición automática mediante una función interna de servicio (`apply_user_response_transition`), no mediante el endpoint público. La función comparte sesión y transacción con HU-03, registra como autor al usuario creador y usa el identificador del evento de respuesta como `request_id`.

**Rationale**:
- El endpoint público exige que el actor sea el técnico asignado; HU-03 actúa por una respuesta del creador.
- La transición debe ser atómica con el registro de la respuesta: si falla una parte, no debe quedar ninguna.
- El autor creador es el hecho histórico correcto y permite trazabilidad.
- El `request_id` evita duplicados si HU-03 reintenta.

**Alternatives considered**:
- *Llamar al endpoint público con el token del creador*: rompe la regla de asignación y mezcla autorización HTTP con integración interna.
- *Permitir al creador cambiar estados por HTTP*: amplía el alcance y debilita RN-07.
- *Usar un usuario «sistema»*: exige un usuario artificial y pierde la autoría real del creador.

---

## Resumen de artefactos

| Artefacto | Contenido |
|---|---|
| `plan.md` | Arquitectura, decisiones, endpoints, componentes e invariantes |
| `data-model.md` | Entidades, columnas, restricciones, estados y migración |
| `contracts/ticket-workflow.openapi.yaml` | Contrato HTTP completo |
| `contracts/frontend-components.md` | Props, eventos, estados y accesibilidad de los componentes |
| `quickstart.md` | Pasos ejecutables de validación end-to-end |
