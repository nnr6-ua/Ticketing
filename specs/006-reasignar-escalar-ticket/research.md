# Research: Reasignar o escalar ticket (HU-06)

**Feature**: `006-reasignar-escalar-ticket` | **Date**: 2026-11-10

Este documento resuelve las incógnitas técnicas de la especificación y justifica las decisiones del plan. No se introducen tecnologías nuevas: todas las decisiones se apoyan en FastAPI, SQLAlchemy 2, Alembic, PostgreSQL 16, Vue 3, Pinia y Tailwind ya presentes en el repositorio.

La línea de base verificada el 2026-11-10 es:

- `backend/alembic/versions/0003_ticket_timeline.py` es la cabeza de Alembic.
- `ticket_timeline_entries` es append-only y ya tiene `request_id`, `event_order`, autoría y visibilidad por `is_internal`.
- `backend/app/services/ticket_workflow.py` implementa el patrón de bloqueo (`_locked_ticket`), el token `expected_updated_at`, la idempotencia por `request_id` y la autorización `_ensure_writer`.
- La cola de trabajo se deriva en vivo de `tickets.assignee_id` y se refresca cada 60 s (`frontend/src/stores/workQueue.ts`).
- No existe ninguna infraestructura de notificaciones ni de eventos en tiempo real.

---

## R1 — Dónde se registra el cambio de responsable

**Decision**: Ampliar `ticket_timeline_entries` con un nuevo valor `assignee_change` y cinco columnas anulables (`previous_assignee_id`, `new_assignee_id`, `change_kind`, `from_escalation_level`, `to_escalation_level`). Cada reasignación o escalado inserta **una única fila nueva**; nunca se actualiza ni se borra una fila existente.

**Rationale**:

- HU06-RN-07 exige que el cambio de responsable sea una entrada de la línea temporal con autor, responsables, tipo, nivel, motivo y fecha. La tabla ya ofrece autoría, orden, visibilidad pública/interna y la restricción `UNIQUE (ticket_id, request_id, event_type)` que sirve de defensa en profundidad para la idempotencia.
- El motivo se guarda en `body`, por lo que hereda el límite de 5.000 caracteres y la renderización como texto plano ya probada en HU-05.
- La entrada es pública (`is_internal = false`), de modo que el usuario creador la ve sin añadir lógica de visibilidad nueva; el filtrado por `is_internal` ya se aplica en SQL.
- El orden cronológico existente (`created_at`, `event_order`, `id`) sigue siendo válido: `assignee_change` usa `event_order = 0` y no comparte `created_at` con otras entradas del mismo comando.
- No se toca ninguna fila histórica ni se renombra ninguna columna, lo que cumple el principio de migraciones aditivas.

**Alternatives considered**:

- *Tabla paralela `ticket_assignments`*: duplica la trazabilidad, obliga a unir dos históricos para pintar la línea temporal y crea dos fuentes de verdad para la visibilidad.
- *Actualizar solo `tickets.assignee_id` sin registrar el hecho*: incumple HU06-RN-07 y HU06-RF-011; no habría autor ni motivo auditables.
- *Añadir una columna `previous_assignee_id` a `tickets`*: solo conserva el valor inmediatamente anterior y se pierde en el siguiente cambio; no es un histórico.

**Detalle de la restricción**: `ck_timeline_assignee_change` valida que, cuando `event_type = 'assignee_change'`, existan `body`, responsables distintos, tipo y niveles coherentes (reasignación con niveles iguales, escalado con niveles distintos). La dirección estricta del escalado (`to > from`) se valida en el servicio para no depender de la comparación de enums en SQLite.

---

## R2 — Cómo modelar el nivel de escalado

**Decision**: Añadir `users.escalation_level` como enum nativo `escalation_level` (`nivel_1`, `nivel_2`, `especialista`), `NOT NULL DEFAULT 'nivel_1'`, y mantener el orden y las etiquetas en código (`ESCALATION_LEVEL_ORDER`, `ESCALATION_LEVEL_LABELS`).

**Rationale**:

- El catálogo es fijo y de tres valores (HU06-RN-02); una tabla de configuración añadiría una entidad, un CRUD y una consulta extra sin aportar nada en esta versión.
- El valor por defecto cubre a todos los usuarios existentes sin migración de datos manual y encaja con el supuesto 5 de la especificación.
- El orden se define una sola vez en Python y se comparte entre validación, opciones y pruebas; no se depende del orden físico del enum de PostgreSQL.
- La administración de niveles queda fuera de alcance, pero el atributo ya existe para futuras historias.

**Alternatives considered**:

- *Tabla `escalation_levels` con `rank`*: permite editar el catálogo sin desplegar, pero la especificación lo excluye y complica la selección y los tests.
- *Columna entera `escalation_rank`*: pierde semántica y etiquetas; cualquier cambio de orden exige migrar datos.
- *Tabla de perfil de técnico separada*: obliga a un `JOIN` en cada consulta de candidatos y en cada serialización para un dato que pertenece al usuario.

---

## R3 — Selección determinista del responsable al escalar

**Decision**: Resolver la selección en una única consulta SQL, en el momento del comando, aplicando en orden:

1. Técnicos `role = tecnico`, `is_active = true`, `escalation_level = target_level`, excluyendo al usuario creador del ticket.
2. Si el responsable actual tiene `team`, se prefiere ese equipo; si el subconjunto queda vacío, se usa el pool completo del nivel.
3. Menor número de tickets activos (`status IN ('abierto', 'en_progreso', 'pendiente_usuario')`).
4. `lower(name)` ascendente y, como desempate final, `User.id` ascendente.

**Rationale**:

- Reproduce literalmente HU06-RN-04 y hace la operación reproducible ante el mismo estado del sistema.
- El desempate por `id` evita que dos técnicos con el mismo nombre y la misma carga dependan del plan de ejecución o del orden de inserción.
- La consulta usa la columna ya indexada `tickets.assignee_id` y el nuevo índice `ix_users_role_active_level_team`; no requiere materializar cargas ni mantener contadores.
- El pool se recalcula al confirmar, cumpliendo HU06-RN-14: un destino válido al abrir el formulario puede dejar de serlo.

**Alternatives considered**:

- *Reparto round-robin persistido*: exige estado adicional y no está en la especificación.
- *Selección aleatoria*: incumple el requisito de determinismo y dificulta las pruebas.
- *Elegir persona en el cliente*: contradice la clarificación (el técnico solo elige nivel) y permitiría manipular la carga.
- *Cachear el resultado de las opciones*: podría escalar a alguien inactivo o sobrecargado tras cambiar el estado del sistema.

---

## R4 — Mecanismo de notificación inmediata

**Decision**: Persistir una fila en la tabla `notifications` dentro de la misma transacción del cambio y exponerla con una campana Vue que consulta `GET /api/v1/me/notifications` cada **15 segundos**. El sondeo se pausa cuando la pestaña está oculta y se refresca de inmediato al recuperar foco o visibilidad.

**Rationale**:

- HU06-RF-018 exige visibilidad en 30 segundos o menos; un intervalo de 15 s deja margen para la latencia y el renderizado.
- HU06-RF-020 exige conservar la notificación si el destinatario está desconectado: una fila en base de datos lo cumple de forma natural, mientras que un evento efímero no.
- No requiere servidor de mensajería, broker, SSE ni WebSocket; reutiliza el cliente HTTP `apiGet`, el patrón de sondeo ya usado por la cola de trabajo y el ciclo de vida de Pinia.
- La notificación se crea en la misma transacción que el cambio y la entrada de línea temporal, cumpliendo HU06-RN-12/HU06-RF-028.
- El contador de no leídas se calcula en el servidor (`unread_count`), no contando la página recibida, para que sea correcto aunque la campana solo cargue 20 elementos.

**Alternatives considered**:

- *SSE*: mantiene conexiones largas, requiere gestionar reconexión, proxies y el ciclo de vida en FastAPI; para una campana personal es más complejo que un sondeo.
- *WebSocket*: comunicación bidireccional innecesaria y autenticación/heartbeat adicionales; la historia solo necesita lectura periódica.
- *Correo o push*: explícitamente fuera de alcance (HU06-RF-08.2).
- *Aviso solo en el cliente que ejecuta el cambio*: el nuevo responsable puede estar en otra pestaña o equipo, y se perdería al recargar.

---

## R5 — Estilo de los endpoints

**Decision**: Usar recursos de comando `POST` y lecturas `GET`:

- `GET /api/v1/tickets/{id}/assignee-change-options`
- `POST /api/v1/tickets/{id}/reassignments`
- `POST /api/v1/tickets/{id}/escalations`
- `GET /api/v1/me/notifications`
- `POST /api/v1/me/notifications/{id}/read`

**Rationale**:

- El cliente HTTP del frontend solo implementa `apiGet` y `apiPost` (`frontend/src/api/client.ts`); no hay `apiPatch` ni `apiDelete`.
- Cada operación crea un hecho auditable con su propio `id`, autor y fecha; modelarla como sub-recurso encaja con la línea temporal y con el patrón de HU-05 (`/status-transitions`, `/internal-comments`).
- No se modifica ningún endpoint existente de HU-05; la respuesta de `workflow` solo se amplía de forma aditiva.
- El marcado de lectura es un comando idempotente, no un `PATCH` parcial.

**Alternatives considered**:

- *`PATCH /tickets/{id}` con `assignee_id`*: exigiría ampliar el cliente y mezclaría la actualización del ticket con la creación del evento y la notificación.
- *`PUT` idempotente*: no modela de forma natural la creación de una entrada histórica por operación.
- *`DELETE` de notificaciones*: la especificación pide conservarlas hasta su lectura, no borrarlas.

---

## R6 — Idempotencia, concurrencia y atomicidad

**Decision**: Reutilizar el patrón de HU-05:

- `request_id` UUID obligatorio generado por el cliente.
- `expected_updated_at` obligatorio con el valor leído de `workflow`.
- Bloqueo de la fila del ticket con `SELECT id FROM tickets WHERE id = :id FOR UPDATE` (PostgreSQL), recarga con `populate_existing=True` y comparación normalizada a UTC.
- Replay idéntico (mismo actor, mismo tipo, mismo destino y mismo motivo normalizado) ⇒ `200 changed=false`, sin entrada ni notificación y `timeline_entry = null`.
- El replay exacto se resuelve antes de `ensure_assignee_change_actor`: un reintento de red sigue siendo idempotente aunque el actor ya haya perdido la asignación al confirmarse la primera respuesta. Una solicitud con un `request_id` nuevo sigue exigiendo asignación vigente.
- Reutilización con datos distintos, otro actor u otro tipo ⇒ `409 request_id_reused` sin escritura.
- Versión obsoleta ⇒ `409 stale_ticket` sin escritura.
- Cambio, entrada y notificación se confirman con un único `commit()`; cualquier excepción hace `rollback()` y se traduce a `500 internal_error`.

**Rationale**:

- El ticket ya expone `updated_at` y la línea temporal ya tiene `UNIQUE (ticket_id, request_id, event_type)`, por lo que no hace falta una tabla de claves de idempotencia.
- Comparar el **nivel destino** (no la persona seleccionada) en un replay de escalado evita reseleccionar un responsable distinto si la carga cambió entre el envío original y el reintento.
- El bloqueo serializa dos comandos simultáneos y el token detecta lecturas obsoletas anteriores al bloqueo.
- La atomicidad es verificable: un fallo en la inserción de la notificación debe deshacer también el cambio de `assignee_id` y la entrada de línea temporal.

**Alternatives considered**:

- *Solo deshabilitar el botón en el cliente*: no protege ante reintentos de red, doble pestaña ni scripts.
- *Tabla de idempotencia separada*: infraestructura adicional para el mismo resultado.
- *Bloqueo pesimista sin token*: evita escrituras concurrentes, pero no detecta que el cliente leyó datos obsoletos antes de abrir el formulario.

**Nota sobre SQLite**: `FOR UPDATE` no aplica en las pruebas funcionales; la corrección se prueba con `expected_updated_at` y las pruebas de concurrencia real se ejecutan contra PostgreSQL.

---

## R7 — Autorización y capacidades del usuario

**Decision**:

- Añadir `ensure_assignee_change_actor` como función pública de `ticket_workflow.py`, sin renombrar ni alterar `_ensure_writer` de HU-05 (evita regresiones), y reutilizarla en `assignee_change.py`.
- Solo el técnico con `role = tecnico`, `user.id != ticket.creator_id` y `ticket.assignee_id == user.id` puede consultar opciones y ejecutar comandos. Creador, supervisor y admin se comprueban antes que la asignación y reciben `403 forbidden`.
- Ampliar `WorkflowResponse` de forma aditiva con `can_reassign` y `can_escalate`, calculados en servidor.
- El frontend usa esas capacidades solo para montar u ocultar el panel; nunca sustituye la comprobación del servidor.

**Rationale**:

- Evita duplicar la lógica de rol/asignación y mantiene un único mensaje para `403 forbidden` y `403 not_ticket_assignee`, con la precedencia fijada en HU06-RN-11: rol no técnico primero y creador técnico no asignado antes que `not_ticket_assignee`.
- La autorización se evalúa contra el `assignee_id` recargado tras el bloqueo, no contra datos del cliente.
- Al cambiar `assignee_id`, `viewer_capabilities` ya revoca automáticamente `can_view_internal`, `can_change_status` y `can_comment_internally` al técnico anterior; HU-06 solo añade dos capacidades con la misma regla.
- Los roles no técnicos y el creador técnico no asignado reciben `false` y un `403 forbidden` si intentan la operación directamente. El creador que es el técnico asignado vigente puede operar como responsable; como creador sigue excluido como destino y del pool de escalado.

**Alternatives considered**:

- *Usar `require_technician`*: permitiría a cualquier técnico reasignar cualquier ticket.
- *Nueva capa de permisos*: complejidad innecesaria para una regla ya implementada.
- *Confiar en el ocultamiento del cliente*: inseguro; los endpoints quedarían abiertos.

---

## R8 — Validación del destino y del catálogo

**Decision**: Las opciones son una ayuda de experiencia de usuario; el comando revalida siempre:

- Reasignación: destino existente, `is_active`, `role = tecnico`, distinto del responsable actual, distinto del creador, mismo equipo (si el actual tiene equipo) y mismo nivel.
- Escalado: nivel estrictamente superior, existencia de niveles superiores y al menos un técnico activo en el destino.
- Motivo: 1–5.000 caracteres tras `strip()`.
- Estado: solo `abierto`, `en_progreso` o `pendiente_usuario`.

**Rationale**:

- HU06-RN-14 y los casos límite exigen rechazar destinos que dejaron de ser válidos entre la apertura del formulario y la confirmación.
- La validación en el servicio permite devolver códigos estables (`invalid_reassignment_target`, `assignee_unavailable`, `invalid_escalation_level`, `no_higher_level`, `no_technicians_available`) en lugar de un `422` genérico de Pydantic.
- Pydantic solo valida forma y tipos; el handler existente normaliza cualquier payload mal formado a `422 invalid_request`.

**Alternatives considered**:

- *Confiar en la lista de opciones*: una desactivación o un cambio de nivel posterior produciría un destino inválido.
- *Validar solo en Pydantic*: no puede consultar el estado actual de la base de datos ni la identidad del actor.
- *Permitir reasignar al creador si es técnico*: contradice la clarificación y el supuesto 12.

---

## R9 — Migración y reversión del enum

**Decision**: La migración `0004_assignee_changes` (fichero `0004_assignee_changes_notifications.py`) crea los tipos `escalation_level`, `assignee_change_kind` y `notification_type`, añade el valor `assignee_change` a `timeline_event_type` dentro de `op.get_context().autocommit_block()`, añade `users.escalation_level`, las columnas de línea temporal, la tabla `notifications` y los índices.

El `downgrade()` es explícitamente destructivo para los datos de HU-06:

1. Elimina `notifications`.
2. Elimina `ck_timeline_assignee_change` y las columnas/FKs nuevas.
3. Borra las filas `assignee_change` (pérdida deliberada; requiere copia de seguridad).
4. Convierte `event_type` a texto, elimina y recrea `timeline_event_type` sin `assignee_change`, y restaura el tipo.
5. Elimina `users.escalation_level` y su índice.
6. Elimina los tipos nuevos.

**Rationale**:

- PostgreSQL no permite quitar un valor de un enum; la recreación es la única vía reversible y debe documentarse como destructiva.
- `autocommit_block()` permite confirmar el nuevo valor antes de usarlo en la restricción `ck_timeline_assignee_change` dentro de la misma migración.
- La migración es aditiva hacia delante: puede aplicarse antes que el código porque las columnas nuevas son anulables, `users.escalation_level` tiene defecto y el código antiguo ignora el nuevo valor del enum.
- En SQLite (pruebas) no se ejecuta la migración: `Base.metadata.create_all()` genera el esquema equivalente con enums como `VARCHAR + CHECK`.

**Alternatives considered**:

- *Guardar `event_type` como texto y validar en la aplicación*: pierde la garantía de la base de datos y rompe la coherencia con los enums existentes.
- *Recrear la tabla completa en el `upgrade()`*: bloquea y copia datos sin necesidad; las columnas nuevas son anulables.
- *Dejar `assignee_change` en el enum tras el `downgrade()`*: deja esquema residual y hace que la migración no sea realmente reversible.

---

## R10 — Estrategia de pruebas

**Decision**:

- `pytest` unitario para el catálogo de niveles y la función de selección determinista (sin base de datos).
- `pytest` de integración para reasignación, escalado, permisos, notificaciones, atomicidad y contrato HTTP.
- Pruebas de concurrencia marcadas para PostgreSQL.
- `vitest` + `@vue/test-utils` para los componentes nuevos y el store; `axe-core` para accesibilidad.

**Rationale**:

- Coincide con las herramientas ya instaladas y con la estructura de `backend/tests` y `frontend/tests`.
- La selección determinista se prueba con varios técnicos, cargas y nombres repetidos sin depender de la base de datos.
- Las pruebas de integración reutilizan los fixtures existentes (`seeded_workflow`, `auth_headers`) y el `TestClient`.
- La matriz de permisos se prueba por rol y por asignación, incluyendo el técnico anterior tras el traspaso.

**Alternatives considered**:

- *Solo pruebas end-to-end*: lentas y con poca granularidad para la selección y los permisos.
- *Solo pruebas unitarias*: no detectan problemas de transacción, idempotencia ni serialización.

---

## R11 — Impacto en la cola de trabajo

**Decision**: No crear ninguna tabla de colas ni modificar `backend/app/services/work_queue.py`. Actualizar `tickets.assignee_id` y `tickets.updated_at` en la misma transacción; la cola existente, que filtra por `assignee_id` y estado, mueve el ticket en la siguiente actualización de 60 s.

**Rationale**:

- La cola es una proyección en vivo del ticket, no una entidad persistida; duplicarla introduciría desincronización.
- HU06-RN-09 y HU06-RF-021/HU06-RF-022 ya se cumplen con el refresco existente (60 s) y el refresco al recuperar foco/visibilidad.
- La prioridad, el SLA y el orden se recalculan con las reglas de HU-04 porque `priority_id`, `sla_deadline`, `created_at` y `status` no cambian.
- El técnico anterior conserva lectura pública, pero pierde escritura y visibilidad interna en la siguiente lectura del workflow.

**Alternatives considered**:

- *Tabla de colas materializada*: duplica estado y exige tareas de reconciliación.
- *Empujar el cambio a la cola del cliente por eventos*: añade infraestructura en tiempo real sin mejorar el requisito de 60 s.
- *Actualizar la cola solo en el cliente que ejecuta la acción*: no sirve para el nuevo responsable en otro navegador.

---

## R12 — Componentes Vue y accesibilidad

**Decision**: Componer un `TicketAssigneeChangePanel` dentro de `TicketWorkflowPanel` con tres controles especializados (`AssigneeSelector`, `EscalationLevelSelector`, `AssigneeChangeReasonForm`) y una campana `NotificationBell` en una cabecera común. Usar controles nativos (`fieldset`/`legend`, `select`/radios, `textarea`), validación en cliente solo para UX y mensajes `role="alert"`/`role="status"`.

**Rationale**:

- Reutiliza el detalle existente y el store `useTicketDetailStore`; no se crea una vista nueva.
- Los controles nativos son accesibles por teclado y con lectores de pantalla sin implementar un `listbox` propio.
- El panel solo se monta si `canReassign || canEscalate`; el backend sigue siendo la defensa.
- Las etiquetas textuales («No leída», «Reasignación», «Escalado», «Sin técnicos disponibles») evitan depender solo del color, cumpliendo WCAG 2.1 AA.
- La campana usa `aria-expanded`, `aria-controls`, `Escape`, cierre por clic fuera y devolución del foco; el sondeo no bloquea la interacción.

**Alternatives considered**:

- *Modal para el cambio de responsable*: requiere gestión de foco y scroll más compleja; el panel inline encaja mejor con el detalle.
- *Selector de personas con `combobox` personalizado*: más código y más riesgo de accesibilidad; la lista es corta y un `select` nativo es suficiente.
- *Calcular los niveles superiores en el cliente*: duplicaría el catálogo y podría divergir del backend.

---

## R13 — Preservación de la infraestructura base

**Decision**: No modificar `docker-compose.yml`, la imagen de PostgreSQL, la configuración de FastAPI, el servidor de Vite ni las dependencias base. HU-06 solo añade modelos, servicios, esquemas, endpoints, migración, componentes, stores, tipos y pruebas.

**Rationale**:

- La historia se apoya en la infraestructura existente (Docker Compose con `db`, `backend` y `frontend`; PostgreSQL 16; FastAPI; Vue 3).
- No se añaden servicios, brokers, colas ni variables de entorno nuevas.
- La única necesidad operativa nueva es ejecutar `alembic upgrade head` y el seed actualizado, ambos ya previstos.

**Alternatives considered**:

- *Añadir Redis o un broker para notificaciones*: contradice el principio de simplicidad y no es necesario para 30 s.
- *Cambiar el intervalo de la cola a 15 s*: aumentaría la carga sin mejorar el requisito de 60 s; la campana tiene su propio intervalo.

---

## Resumen de artefactos

| Artefacto | Contenido |
|---|---|
| `plan.md` | Arquitectura, decisiones, endpoints, componentes e invariantes |
| `data-model.md` | Entidades, columnas, restricciones, DTOs y migración |
| `contracts/assignee-change.openapi.yaml` | Contrato HTTP completo de HU-06 |
| `contracts/frontend-components.md` | Props, eventos, estados y accesibilidad de los componentes |
| `quickstart.md` | Pasos ejecutables de validación end-to-end |
