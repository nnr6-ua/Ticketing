# Implementation Plan: Reasignar o escalar ticket (HU-06)

**Branch**: `hu-06-reasignar-escalar` | **Date**: 2026-11-11 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/006-reasignar-escalar-ticket/spec.md`

**Estado**: plan revisado el 2026-11-11 contra las fuentes implementadas en `backend/` y `frontend/` y contra las aclaraciones de la especificación (sesión 2026-11-10). Los artefactos de Fase 0 y Fase 1 (`research.md`, `data-model.md`, `contracts/` y `quickstart.md`) están sincronizados con este documento.

## Summary

HU-06 permite al técnico **actualmente asignado** transferir la responsabilidad de un ticket de dos formas: **reasignarlo** a otro técnico activo de su mismo equipo y nivel, o **escalarlo** a un nivel superior del catálogo fijo (`Nivel 1 < Nivel 2 < Especialista`). En ambos casos se exige un motivo de 1 a 5.000 caracteres, el cambio se registra como una **entrada append-only de la línea temporal** (`event_type = assignee_change`) y el nuevo responsable recibe una **notificación en la aplicación** creada en la misma transacción.

La reasignación y el escalado **no alteran** el estado, la prioridad, la categoría ni el límite de SLA del ticket. El traslado entre colas es una consecuencia natural de actualizar `tickets.assignee_id`: la cola de trabajo existente ya se calcula en vivo por responsable, por lo que el ticket desaparece de la cola anterior y aparece en la nueva en la siguiente actualización de 60 segundos. No se crea una tabla de colas ni se duplica su lógica.

**Decisiones clave**:

| Punto solicitado | Decisión |
|---|---|
| Trazabilidad append-only | Ampliar `ticket_timeline_entries` con `event_type = assignee_change` y columnas anulables para responsable anterior/nuevo, tipo de cambio y niveles; nunca se actualiza ni borra una entrada |
| Nivel de escalado | Enum `EscalationLevel` (`nivel_1`, `nivel_2`, `especialista`) como `users.escalation_level`, `NOT NULL DEFAULT 'nivel_1'`; catálogo fijo ordenado en código |
| Selección del nuevo responsable al escalar | Función determinista en servidor: mismo equipo si existe, menor carga activa, nombre alfabético sin distinguir mayúsculas y `User.id` como desempate final |
| Notificación inmediata | Tabla `notifications` + campana Vue con sondeo ligero cada 15 s; se pausa con la pestaña oculta y se refresca al recuperar foco. Sin SSE, WebSocket, correo ni push |
| API | `GET /tickets/{id}/assignee-change-options`, `POST /tickets/{id}/reassignments`, `POST /tickets/{id}/escalations`, `GET /me/notifications` y `POST /me/notifications/{id}/read`; solo GET/POST |
| Interfaz | `TicketAssigneeChangePanel` con `AssigneeSelector`, `EscalationLevelSelector` y `AssigneeChangeReasonForm`; campana `NotificationBell` en una cabecera común |
| Atomicidad / concurrencia | Una transacción con bloqueo de fila, `expected_updated_at` y `request_id`; el cambio, la entrada de línea temporal y la notificación se confirman juntos |

## Requisitos técnicos explícitos de la HU-06

Esta sección fija, de forma normativa para la implementación, las cinco decisiones que la historia exige documentar de forma expresa. El detalle de cada una se desarrolla en las secciones indicadas.

### 1. Línea temporal append-only (CRÍTICO)

**Decisión**: cada reasignación o escalado se registra mediante el `INSERT` de **una única fila nueva** en `ticket_timeline_entries` con `event_type = 'assignee_change'`. No existe ningún camino de código, endpoint ni operación ORM que actualice o elimine una entrada existente.

**Contenido obligatorio de la fila**:

| Campo | Valor en la entrada `assignee_change` |
|---|---|
| `ticket_id` | Ticket afectado |
| `event_type` | `assignee_change` |
| `body` | Motivo normalizado con `strip()`; 1–5.000 caracteres; texto plano |
| `is_internal` | `false` (entrada pública, visible para el usuario creador) |
| `author_id` | Técnico que ejecuta la acción (identidad del JWT) |
| `previous_assignee_id` | Responsable vigente antes del cambio |
| `new_assignee_id` | Nuevo responsable (persona en reasignación; seleccionado por el sistema en escalado) |
| `change_kind` | `reassignment` o `escalation` |
| `from_escalation_level` | Nivel del responsable anterior |
| `to_escalation_level` | Nivel destino; igual a `from` en reasignación y estrictamente superior en escalado |
| `created_at` | Instante UTC único del comando |
| `event_order` | `0` (se conserva el orden `created_at`, `event_order`, `id`) |
| `request_id` | UUID de idempotencia enviado por el cliente |

**Garantías de inmutabilidad y trazabilidad**:

- El historial **no se reescribe**: el cambio de responsable actualiza `tickets.assignee_id` y `tickets.updated_at` en la misma transacción, pero la evidencia anterior permanece intacta en las filas ya existentes.
- No se exponen `PUT`, `PATCH` ni `DELETE` sobre `ticket_timeline_entries`; el servicio `assignee_change.py` solo construye y añade filas. La inmutabilidad es una invariante de diseño heredada de HU-05 y se verifica con pruebas que comprueban que no existe ruta de modificación.
- La restricción `ck_timeline_assignee_change` obliga a que la entrada tenga motivo, responsables distintos, tipo y niveles coherentes; `UNIQUE (ticket_id, request_id, event_type)` impide duplicados por doble envío.
- Un intento rechazado (permisos, estado final, destino inválido, motivo vacío, versión obsoleta) **no inserta ninguna fila**.
- Un replay idéntico del mismo `request_id` **no inserta una segunda fila**; devuelve `changed = false` y `timeline_entry = null`.
- No se añade un trigger de PostgreSQL: la defensa es la ausencia de rutas de escritura, las restricciones de integridad y la transacción única. Si una auditoría futura exigiera inmutabilidad a nivel de motor, se incorporaría en una migración separada sin alterar este contrato.

**Referencias**: §1.2 (columnas y restricciones), §2.6 (transacción) y §5.3 (invariantes).

### 2. Impacto en la cola de trabajo (Backend/FastAPI)

**Decisión**: no se crea una tabla de colas ni se duplica la lógica de HU-04. La cola sigue siendo una consulta en vivo sobre `tickets` cuyo único criterio de propiedad es `tickets.assignee_id`.

- El comando actualiza `assignee_id` al nuevo responsable y `updated_at` al instante del cambio, dentro de la misma transacción que la entrada de línea temporal y la notificación.
- La consulta existente de `work_queue.py` filtra por `assignee_id == current_user.id` y estados activos (`abierto`, `en_progreso`, `pendiente_usuario`). En la siguiente actualización, el ticket deja de cumplir el filtro del técnico anterior y pasa a cumplirlo para el nuevo.
- El frontend de la cola ya sondea cada 60 s y refresca al recuperar foco o visibilidad (`frontend/src/stores/workQueue.ts`); cumple RF-021 y RF-022 sin cambios ni invalidación de caché.
- La prioridad, la categoría, el límite de SLA y el orden se conservan; el ticket se reposiciona en la cola del nuevo responsable con las reglas de HU-04 porque `priority_id`, `sla_deadline`, `created_at` y `status` no se tocan.
- El cambio de `updated_at` invalida a los clientes con datos obsoletos: un comando posterior con `expected_updated_at` antiguo recibe `409 stale_ticket`.
- El técnico anterior conserva lectura pública, pero pierde `can_change_status`, `can_comment_internally`, `can_view_internal`, `can_reassign` y `can_escalate` en la siguiente lectura del workflow; el nuevo responsable los adquiere.

**Referencias**: §2.6, §2.7 y §4.

### 3. Mecanismo de notificación

**Decisión**: notificación persistida en la tabla `notifications` y campana Vue con **sondeo ligero cada 15 segundos**. No se usan SSE, WebSocket, correo ni notificaciones push.

- La fila de notificación se inserta en la **misma transacción** que el cambio de responsable y la entrada de línea temporal; si falla cualquier inserción, no persiste ninguna de las tres.
- `notifications.timeline_entry_id` es `UNIQUE`: como máximo una notificación por cambio. El destinatario es siempre el nuevo responsable.
- La notificación guarda snapshots de número y título del ticket y del nombre del responsable anterior, para que la campana no dependa de joins ni de cambios posteriores del ticket. El motivo no se duplica: vive en la línea temporal y se consulta al abrir el ticket.
- `GET /api/v1/me/notifications` devuelve la página ordenada por `created_at DESC` y un `unread_count` calculado en servidor sobre todas las notificaciones del usuario, no solo sobre la página.
- `POST /api/v1/me/notifications/{id}/read` marca la notificación como leída de forma idempotente; solo el destinatario puede hacerlo (`404 notification_not_found` para notificaciones ajenas).
- `NotificationBell.vue` vive en `AppHeader`, se apoya en el store Pinia `notifications`, consulta cada 15 s, pausa el sondeo con la pestaña oculta y refresca de inmediato al recuperar foco o visibilidad. Usa `AbortController` y secuencia para descartar respuestas fuera de orden.
- **Por qué esta solución**: cumple el plazo de 30 s de RF-018 con margen, conserva la notificación si el destinatario está desconectado (RF-020), reutiliza el cliente HTTP y el patrón de sondeo ya existentes y no añade infraestructura, autenticación de conexiones ni gestión de reconexión. SSE y WebSocket se descartan por complejidad y por la regla de simplicidad; el correo y el push están fuera de alcance (RF-08.2).

**Referencias**: §1.3, §2.8, §3.6 y R4 de `research.md`.

### 4. Componentes de interfaz (Frontend/Vue)

**Decisión**: un panel de cambio de responsable integrado en el detalle existente y una campana común en la cabecera, reutilizando Tailwind, Pinia, Vue Router y los patrones de accesibilidad de HU-04/HU-05.

| Componente | Responsabilidad |
|---|---|
| `TicketAssigneeChangePanel.vue` | Orquesta el modo (`reassign` / `escalate`), carga opciones, valida, envía y refresca workflow/timeline |
| `AssigneeSelector.vue` | Selector de compañeros candidatos del mismo equipo y nivel, con nombre, equipo y nivel; estado vacío claro |
| `EscalationLevelSelector.vue` | Selector de niveles **estrictamente superiores**; muestra disponibilidad y deshabilita niveles sin técnicos; nunca elige persona en cliente |
| `AssigneeChangeReasonForm.vue` | Caja de texto obligatoria de 1–5.000 caracteres, contador, ayuda de visibilidad pública y error accesible |
| `NotificationBell.vue` | Campana con contador de no leídas, `aria-live`, apertura/cierre accesible y sondeo |
| `NotificationList.vue` | Lista de notificaciones, distinción textual de no leídas, navegación al ticket y marcado de lectura |
| `AppHeader.vue` | Cabecera común que monta la campana fuera de `RouterView` y la oculta en `/login` |
| `TicketTimeline.vue` | Nueva rama de renderizado para `assignee_change` con tipo, responsables, niveles y motivo en texto plano |

**Reglas de interacción**:

- El motivo es obligatorio, se valida con `trim()` en cliente y se revalida en servidor; el texto de ayuda advierte de que el usuario creador podrá verlo en la línea temporal.
- La reasignación solo ofrece candidatos que devuelve el backend (mismo equipo y nivel, excluyendo al responsable actual y al creador). El escalado solo ofrece niveles superiores y el backend selecciona al responsable de forma determinista.
- El panel solo se monta si `canReassign || canEscalate`; si el usuario deja de ser responsable, desaparece en la recarga y el backend sigue siendo la defensa.
- El `request_id` se mantiene estable por firma `modo|destino|motivo.trim()` y se regenera si cambia la firma o si el backend responde `request_id_reused`.
- Se cubren estados de carga, vacío, error, conflicto de versión, replay y éxito; los errores se asocian al campo correspondiente y los avisos usan `role="alert"` o `role="status"`.
- Accesibilidad WCAG 2.1 AA: `fieldset`/`legend`, etiquetas asociadas, `aria-required`, `aria-invalid`, `aria-describedby`, foco visible, navegación por teclado y cierre de la campana con `Escape`.

**Referencias**: §3 y `contracts/frontend-components.md`.

### 5. Trazabilidad y alcance técnico

**Decisión**: se mantiene intacta la infraestructura base y solo se documentan adiciones técnicas para HU-06.

**No cambia**:

- Docker Compose, PostgreSQL 16, FastAPI, SQLAlchemy 2, Alembic, Vue 3, TypeScript, Vite, Pinia, Tailwind y Vitest.
- El modelo base `tickets`, `priorities`, `categories`, la matriz de estados de HU-05, la cola de trabajo de HU-04, la autenticación JWT, el cliente HTTP y el formato de errores `{"detail": {"code", "message"}}`.
- No se añaden servicios externos, brokers, colas, SSE, WebSocket, correo, push, variables de entorno ni secretos.

**Se añade de forma aditiva**:

- Migración `0004_assignee_changes_notifications`: enums, `users.escalation_level`, columnas anulables y restricciones en `ticket_timeline_entries`, tabla `notifications` e índices.
- Servicios `assignee_change.py` y `notifications.py`; ampliación aditiva de `ticket_workflow.py` y `ticket_timeline.py`.
- Esquemas `assignee_change.py` y `notification.py`; ampliación aditiva de `ticket_workflow.py`.
- Endpoints de opciones, reasignación, escalado y notificaciones; solo `GET` y `POST`.
- Componentes, servicios, tipos, stores y pruebas del frontend; `AppHeader` con la campana.
- Seed de desarrollo con niveles y escenarios de creador técnico.

**Invariantes que la implementación debe conservar**:

1. El último `assignee_change` del ticket tiene `new_assignee_id = tickets.assignee_id` y `previous_assignee_id` igual al responsable anterior.
2. La línea temporal es append-only: no hay actualización ni borrado de entradas.
3. Cambio, entrada y notificación se confirman juntos o no se confirma ninguno.
4. Una notificación por cambio (`UNIQUE (timeline_entry_id)`) y replay idempotente sin duplicados.
5. `status`, `priority_id`, `category_id`, `sla_deadline`, `sla_version`, `finalized_at` y `closed_at` no cambian.
6. La entrada es pública (`is_internal = false`) y el creador la ve con su motivo.
7. Solo el técnico asignado vigente ejecuta y consulta opciones. Rol no técnico (supervisor, admin, usuario) ⇒ `403 forbidden`; creador técnico no asignado ⇒ `403 forbidden` con precedencia sobre la asignación; técnico anterior no creador ⇒ `403 not_ticket_assignee`. Si el creador es el técnico asignado, puede operar.
8. Mismo `request_id` + mismos datos ⇒ sin escritura; datos distintos ⇒ `409 request_id_reused`.
9. `expected_updated_at` obsoleto ⇒ `409 stale_ticket` y cero escrituras.
10. El escalado es determinista: mismo equipo, menor carga, nombre y `User.id` como desempate.

**Referencias**: §1.4, §2.6, §5 y `data-model.md`.

## Technical Context

**Language/Version**: Python 3.12 (backend, `.venv` actual), TypeScript + Vue 3 (frontend)

**Primary Dependencies**: FastAPI 0.115.6, SQLAlchemy 2.0.36, Pydantic 2.10.4, Alembic 1.14.0, psycopg; Vue 3.5, Vite 6, Tailwind CSS 3.4, Pinia 2.3, Vue Router 4.5; Vitest + `@vue/test-utils` y `axe-core` ya presentes

**Storage**: PostgreSQL 16 en desarrollo/producción (`postgresql+psycopg://...`); SQLite en pruebas locales mediante la abstracción de `app/db/session.py`. La tabla nueva y las columnas nuevas usan tipos genéricos de SQLAlchemy y enums compatibles con ambos motores.

**Testing**: `pytest` 8.3.4 + `fastapi.testclient`/`httpx`; `vitest` + `@vue/test-utils` para componentes y stores. Las pruebas de concurrencia real se ejecutan sobre PostgreSQL; las funcionales pueden usar SQLite.

**Target Platform**: Servicio web Linux + interfaz web responsive (desktop/tablet).

**Project Type**: Aplicación web con backend y frontend separados.

**Performance Goals**:
- Comando de reasignación/escalado: p95 < 300 ms en servidor (sin contar red); verificado por `T079`.
- Consulta de opciones de cambio de responsable: p95 < 300 ms; verificado por `T079`.
- Listado de la cola con hasta 100 tickets activos por técnico: p95 < 300 ms; verificado por `T079`.
- **SC-010 alineación**: "Menos de 300 ms p95 en servidor" corresponde al objetivo de rendimiento del plan; ver T079 para pruebas de rendimiento en servidor.
- Entrada de cambio de responsable visible en la línea temporal: < 2 s percibidos tras confirmar; verificado en cliente por `T091` (el backend solo garantiza su p95).
- Notificación visible en la campana: ≤ 30 s (sondeo de 15 s + refresco inmediato al recuperar foco); verificado por `T057` y `T091`.
- Ticket en la cola del nuevo responsable y fuera de la anterior: siguiente actualización de 60 s de HU-04; verificado por `T091`.
- Motivo: 1–5.000 caracteres tras `strip()`.
- Línea temporal paginada (50 por defecto, 200 máximo) sin cambios.

**Constraints**:
- Interfaz y mensajes 100 % en español de España (RNF-01).
- Accesibilidad WCAG 2.1 AA (RNF-03) y diseño responsive (RNF-04).
- Identidad exclusivamente desde el JWT (`Authorization: Bearer`); nunca desde query string, cuerpo o cabeceras manipulables.
- Autorización en servidor contra el responsable vigente; el cliente solo oculta acciones.
- Sin nuevas tecnologías, motores de workflow, colas, SSE ni WebSocket.
- Sin secretos en código (RNF-07).
- No se renombran ni eliminan columnas/tablas existentes; la migración es aditiva y reversible.
- El motivo es público para el usuario creador: se redacta sabiendo que quedará visible en la línea temporal.

**Scale/Scope**: Mesa de ayuda interna; miles de tickets, decenas de técnicos y decenas de entradas por ticket. Las notificaciones crecen de forma append-only por destinatario; se indexan por `(recipient_id, is_read, created_at)` y se conservan hasta su lectura.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

La constitución del proyecto está ratificada en `.specify/memory/constitution.md` (versión 1.0.0, 2026-11-02). Se evalúan sus cinco principios y sus restricciones adicionales.

### Pre-Phase 0

| Principio / restricción | Resultado | Justificación |
|---|---|---|
| I. Arquitectura por capas y stack fijado | PASS | Se reutilizan FastAPI, SQLAlchemy 2, Alembic, PostgreSQL, Vue 3, TypeScript, Pinia, Tailwind y Vitest. Los endpoints delegan en `assignee_change.py` y `notifications.py`; no se añaden motores ni servicios externos. |
| II. Modelo de datos estable y migraciones aditivas | PASS | La migración `0004_assignee_changes` añade valor al enum existente, columnas anulables o con defecto, una tabla nueva e índices. No renombra ni elimina columnas/tablas. La línea temporal sigue siendo append-only. |
| III. Seguridad y mínimo privilegio | PASS | Identidad solo desde JWT; solo el técnico asignado vigente ejecuta comandos y consulta opciones. Los roles no técnicos reciben `403 forbidden`, el creador técnico no asignado también `forbidden` por precedencia y el técnico anterior `not_ticket_assignee`; el creador que es el técnico asignado opera como responsable. La autorización se reevalúa en servidor; el técnico anterior pierde escritura y visibilidad interna al cambiar `assignee_id`. |
| IV. Contratos primero y pruebas verificables | PASS | Se documentan OpenAPI y contrato de componentes antes de implementar. El plan enumera pruebas de estados, permisos, destinos, visibilidad, atomicidad, concurrencia, idempotencia, notificaciones y códigos estables. |
| V. Simplicidad, trazabilidad y español de España | PASS | Catálogo fijo en código, sin tabla de configuración; notificación con tabla + sondeo de 15 s en lugar de infraestructura en tiempo real; línea temporal como fuente de trazabilidad; mensajes es-ES y fechas `Europe/Madrid`. |
| **Cross-reference**: RN-11 precedencia y RN-10/FR-025 | — | **RN-11**: rol no técnico → `403 forbidden`; creador técnico no asignado → `forbidden` con precedencia sobre `not_ticket_assignee`; creador asignado opera como responsable; técnico anterior no creador → `not_ticket_assignee`. **FR-025**: "El sistema DEBE impedir que el técnico se reasigne el ticket a sí mismo" alinea con RN-10. Ver también RN-10 y RN-11 para reglas de autorización. |
| Restricciones adicionales | PASS | Formato de error heredado, comandos POST compatibles con el cliente GET/POST, paginación existente, p95 < 300 ms y accesibilidad AA. |

### Post-design re-check (Phase 1)

| Principio / restricción | Resultado | Justificación |
|---|---|---|
| I. Arquitectura por capas | PASS | `api/v1/tickets.py` y `api/v1/notifications.py` solo orquestan; la selección determinista, la idempotencia y la transacción viven en `services/assignee_change.py`; la lectura de notificaciones en `services/notifications.py`. |
| II. Modelo de datos y migraciones | PASS | `data-model.md` detalla columnas, restricciones e invariantes. El `downgrade()` elimina primero notificaciones, después columnas/constraints y por último recrea el enum `timeline_event_type` sin `assignee_change`; la destrucción de datos de HU-06 se documenta y exige copia de seguridad. |
| III. Seguridad y mínimo privilegio | PASS | `ensure_assignee_change_actor` se añade en `ticket_workflow.py` sin alterar `_ensure_writer` de HU-05; las opciones y comandos exigen rol `tecnico` y asignación vigente. Los roles no técnicos reciben `403 forbidden`; el creador técnico no asignado recibe `forbidden` con precedencia sobre `not_ticket_assignee`; el creador asignado opera como responsable y el técnico anterior recibe `not_ticket_assignee` salvo en el replay idéntico, que no escribe. La visibilidad interna se recalcula por `assignee_id`. |
| IV. Contratos y pruebas | PASS | El contrato OpenAPI incluye los nuevos recursos, DTOs y catálogo de errores; el contrato de componentes fija props, emits, estados y accesibilidad. Las pruebas cubren la matriz de destinos, la selección determinista y la no escritura ante rechazo. |
| V. Simplicidad y trazabilidad | PASS | No se añade un servicio de notificaciones externo ni una tabla de colas. La notificación es una fila más en la misma transacción; la cola sigue derivándose de `tickets.assignee_id`. |

**Resultado**: PASS. No hay violaciones que justificar en `Complexity Tracking`.

**Nota de remediación (tras `/speckit.analyze`)**: se ajustó `tasks.md` sin alterar el diseño ni los contratos. En la primera ronda, las tareas de prueba que estaban en Foundational se movieron a la historia que las consume y se colocaron antes de su implementación (`T019`, `T020` y `T022` a US1; `T081` a US1 antes de implementar componentes; `T024` a US3; `T021` a US4; `T079` como prueba transversal al inicio de Phase 2), de modo que se cumple el Principio IV (pruebas escritas y en rojo antes de implementar). También se añadieron la guarda de token en `AppHeader` (`T068`) y su prueba (`T055`), la limpieza del sondeo ante `401` (`T065`, `T057`), la precisión de qué DTOs llevan `request_id`/`expected_updated_at` (`T013`), el marcado `[P]` de `T036`/`T037`, la separación de la accesibilidad de la campana a US4 y el requisito de `TEST_DATABASE_URL` en el gate `T083`. En la segunda ronda se corrigieron los hallazgos restantes: (a) `T070` (permisos/capacidades), `T071` (concurrencia) y `T086` (inmutabilidad) se movieron a Phase 2 para que se escriban en rojo antes de los comandos que las satisfacen; (b) `T021` (creación de notificación) se movió a Foundational con su prueba unitaria `T090`, porque US1/US2 la necesitan antes de US4; (c) `T072` se dividió en la prueba de montaje de US1 (`T072`) y la prueba de pérdida de capacidades de US5 (`T089`); (d) se añadió `T091` para la latencia percibida en cliente, de modo que `T079` solo cubre el rendimiento en servidor; (e) se ampliaron `T033`, `T050`, `T070`, `T074`, `T079` y `T087`; y (f) se fijó en RN-11 la precedencia del rol no técnico y del creador técnico no asignado, implementada en el helper `ensure_assignee_change_actor`, manteniendo que el creador asignado puede operar como responsable. El total queda en 91 tareas.

## Project Structure

### Documentation (this feature)

```text
specs/006-reasignar-escalar-ticket/
├── plan.md                  # Este archivo
├── research.md              # Fase 0: decisiones y alternativas
├── data-model.md            # Fase 1: entidades, invariantes y migración
├── quickstart.md            # Fase 1: validación ejecutable
├── contracts/
│   ├── assignee-change.openapi.yaml   # Contrato HTTP de HU-06
│   └── frontend-components.md         # Contrato de componentes Vue
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
│       └── 0004_assignee_changes_notifications.py   # NUEVO: enums, columnas, tabla e índices
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── tickets.py                   # MODIFICADO: opciones, reasignación y escalado
│   │       ├── notifications.py             # NUEVO: bandeja y marcado de lectura
│   │       └── router.py                    # MODIFICADO: include_router(notifications)
│   ├── models/
│   │   ├── enums.py                         # MODIFICADO: EscalationLevel, AssigneeChangeKind, NotificationType, assignee_change
│   │   ├── user.py                          # MODIFICADO: escalation_level
│   │   ├── timeline.py                      # MODIFICADO: columnas y relaciones de cambio de responsable
│   │   ├── notification.py                  # NUEVO: Notification
│   │   └── __init__.py                      # MODIFICADO: exportar Notification y enums
│   ├── schemas/
│   │   ├── assignee_change.py               # NUEVO: opciones, requests y response
│   │   ├── notification.py                  # NUEVO: DTOs de notificación
│   │   └── ticket_workflow.py               # MODIFICADO: TimelineEntry y WorkflowResponse ampliados
│   ├── services/
│   │   ├── assignee_change.py               # NUEVO: catálogo, candidatos, selección y comandos
│   │   ├── notifications.py                 # NUEVO: creación compartida, bandeja, contador y marcado de lectura
│   │   ├── ticket_workflow.py               # MODIFICADO: ensure_assignee_change_actor y capacidades
│   │   └── ticket_timeline.py               # MODIFICADO: serialización de assignee_change
│   └── main.py                              # Sin cambios funcionales (handlers existentes)
├── scripts/
│   └── seed_dev.py                          # MODIFICADO: niveles y creador técnico para escenarios
└── tests/
    ├── unit/
    │   ├── test_escalation_levels.py
    │   ├── test_assignee_selection.py
    │   └── test_assignee_change_notification.py
    ├── integration/
    │   ├── test_ticket_reassignment.py
    │   ├── test_ticket_escalation.py
    │   ├── test_assignee_change_permissions.py
    │   ├── test_assignee_change_concurrency.py
    │   ├── test_assignee_change_immutability.py
    │   ├── test_assignee_change_performance.py
    │   ├── test_timeline_visibility.py           # MODIFICADO: visibilidad del cambio
    │   ├── test_work_queue_api.py                # MODIFICADO: traspaso entre colas
    │   └── test_notifications.py
    └── contract/
        └── test_assignee_change_contract.py

frontend/
├── src/
│   ├── App.vue                              # MODIFICADO: cabecera común
│   ├── components/
│   │   ├── layout/
│   │   │   └── AppHeader.vue                # NUEVO: cabecera con campana
│   │   ├── notifications/
│   │   │   ├── NotificationBell.vue         # NUEVO: campana y contador
│   │   │   └── NotificationList.vue         # NUEVO: lista desplegable
│   │   └── tickets/
│   │       ├── TicketAssigneeChangePanel.vue # NUEVO: orquestador
│   │       ├── AssigneeSelector.vue          # NUEVO: compañeros candidatos
│   │       ├── EscalationLevelSelector.vue   # NUEVO: niveles superiores
│   │       ├── AssigneeChangeReasonForm.vue  # NUEVO: motivo obligatorio
│   │       ├── TicketWorkflowPanel.vue       # MODIFICADO: integra el panel de responsable
│   │       └── TicketTimeline.vue            # MODIFICADO: render de assignee_change
│   ├── services/
│   │   ├── assigneeChange.ts                 # NUEVO: cliente de los comandos
│   │   └── notifications.ts                  # NUEVO: cliente de la bandeja
│   ├── stores/
│   │   ├── notifications.ts                  # NUEVO: contador y sondeo de 15 s
│   │   └── ticketDetail.ts                   # MODIFICADO: opciones y comandos de responsable
│   ├── types/
│   │   ├── assigneeChange.ts                 # NUEVO: tipos del cambio de responsable
│   │   ├── notifications.ts                  # NUEVO: tipos de notificación
│   │   └── ticketWorkflow.ts                 # MODIFICADO: TimelineEntry y WorkflowResponse
│   └── views/
│       └── TicketDetailPage.vue               # Sin cambios: compone TicketWorkflowPanel
└── tests/
    ├── components/
    │   ├── AssigneeSelector.spec.ts
    │   ├── EscalationLevelSelector.spec.ts
    │   ├── AssigneeChangeReasonForm.spec.ts
    │   ├── TicketAssigneeChangePanel.spec.ts
    │   ├── TicketWorkflowPanel.spec.ts       # MODIFICADO: montaje y pérdida de capacidades
    │   ├── NotificationBell.spec.ts
    │   ├── NotificationList.spec.ts
    │   ├── AppHeader.spec.ts                  # NUEVO: campana y token
    │   └── TicketTimeline.spec.ts             # MODIFICADO: caso assignee_change
    ├── stores/
    │   ├── ticketDetail.spec.ts               # MODIFICADO: comandos, refresco y latencia
    │   └── notifications.spec.ts
    └── unit/
        └── workQueue.store.spec.ts            # MODIFICADO: traspaso en la siguiente actualización
```

**Structure Decision**: se mantiene la arquitectura por capas existente (`api` → `services` → `models`/`db`, con `schemas` como contrato). La lógica de selección, permisos, idempotencia y transacción vive en `services/assignee_change.py`; el router solo traduce HTTP. La lectura de notificaciones se separa en `services/notifications.py` para no mezclar la bandeja personal con el flujo del ticket. En el frontend se conserva la organización por `components`, `services`, `stores`, `types` y `views`; la campana vive en una cabecera común (`AppHeader`) y el panel de responsable se integra en el detalle existente (`TicketWorkflowPanel`). Se reutilizan el cliente HTTP (`apiGet`/`apiPost`), el formato de errores `{"detail": {"code", "message"}}`, la paleta `slate` y los patrones de accesibilidad de HU-04/HU-05.

**Nota de estado del repositorio**: a fecha 2026-11-10 existen `ticket_timeline_entries` (migración `0003_ticket_timeline`), `viewer_capabilities`, los comandos de HU-05 y la cola de trabajo con sondeo de 60 s. HU-06 se apoya en esas fuentes; no se reimplementan. La cabeza de Alembic es `0003_ticket_timeline`; la nueva revisión es `0004_assignee_changes` con `down_revision = "0003_ticket_timeline"`.

## Phase 0: Outline & Research

**Output**: [research.md](./research.md)

Resumen de decisiones (detalle y alternativas en `research.md`):

- **R1 — Extender la línea temporal, no crear un histórico paralelo**: `assignee_change` es un tipo más de `ticket_timeline_entries`; las columnas nuevas son anulables y solo se rellenan en ese tipo. Se conserva el orden cronológico, la autoría y la inmutabilidad.
- **R2 — Nivel de escalado como enum fijo en `users`**: catálogo `nivel_1 < nivel_2 < especialista`, `NOT NULL DEFAULT 'nivel_1'`; la administración de niveles queda fuera de alcance. Un enum evita una tabla de configuración y mantiene el orden en código y en la migración.
- **R3 — Selección determinista del escalado en SQL + orden estable**: se prefieren técnicos del mismo equipo (si el responsable actual tiene equipo), después menor número de tickets activos, después `lower(name)` y finalmente `User.id`. La consulta se ejecuta en el momento del comando, no sobre opciones cacheadas.
- **R4 — Notificación en base de datos + sondeo de 15 s**: una fila en `notifications` por cambio y destinatario; la campana consulta `GET /me/notifications` cada 15 s (pausa con pestaña oculta, refresco al recuperar foco). SSE y WebSocket se rechazan por infraestructura y complejidad; el correo/push están fuera de alcance.
- **R5 — Comandos POST sobre sub-recursos**: el cliente HTTP existente solo expone GET/POST. Se usan `/reassignments` y `/escalations`, sin PATCH/PUT/DELETE y sin tocar los endpoints de HU-05.
- **R6 — Idempotencia y concurrencia reutilizando el patrón de HU-05**: `request_id` obligatorio + `expected_updated_at` + `SELECT ... FOR UPDATE`; replay idéntico ⇒ `200 changed=false` sin escritura; reutilización con otros datos ⇒ `409 request_id_reused`; versión obsoleta ⇒ `409 stale_ticket`.
- **R7 — Autorización única en servicios**: se añade `ensure_assignee_change_actor` (rol no técnico → `403 forbidden`; técnico no asignado y creador → `forbidden` con precedencia; técnico anterior no creador → `not_ticket_assignee`; el creador asignado opera como responsable) en `ticket_workflow.py`, sin tocar `_ensure_writer` de HU-05, y se reutiliza en opciones y comandos. Las capacidades del visor se calculan en servidor; el cliente solo las usa para ocultar acciones.
- **R8 — Validación de destino en el momento del comando**: las opciones son una ayuda de UX; el comando revalida existencia, actividad, rol, equipo, nivel, creador y autoasignación. Un destino válido al abrir el formulario puede dejar de serlo al confirmar (RN-14).
- **R9 — Migración reversible con recreación explícita del enum**: PostgreSQL no permite eliminar un valor de enum; el `downgrade()` borra las entradas `assignee_change`, convierte la columna a texto, recrea `timeline_event_type` sin el valor y restaura el tipo. Se documenta la pérdida de datos de HU-06.

## Phase 1: Design & Contracts

**Output**: [data-model.md](./data-model.md), [contracts/assignee-change.openapi.yaml](./contracts/assignee-change.openapi.yaml), [contracts/frontend-components.md](./contracts/frontend-components.md), [quickstart.md](./quickstart.md)

---

## Diseño detallado

### 1. Modelo de datos y migración

#### 1.1. Catálogo de niveles de escalado

Se añade en `backend/app/models/enums.py`:

```python
class EscalationLevel(str, Enum):
    nivel_1 = "nivel_1"
    nivel_2 = "nivel_2"
    especialista = "especialista"
```

Con un orden y etiquetas estables:

```python
ESCALATION_LEVEL_ORDER: tuple[EscalationLevel, ...] = (
    EscalationLevel.nivel_1,
    EscalationLevel.nivel_2,
    EscalationLevel.especialista,
)
ESCALATION_LEVEL_LABELS = {
    EscalationLevel.nivel_1: "Nivel 1",
    EscalationLevel.nivel_2: "Nivel 2",
    EscalationLevel.especialista: "Especialista",
}
```

Funciones puras en `backend/app/services/assignee_change.py`:

```python
def escalation_level_label(level: EscalationLevel) -> str
def higher_escalation_levels(level: EscalationLevel) -> tuple[EscalationLevel, ...]
def is_higher_level(current: EscalationLevel, target: EscalationLevel) -> bool
```

Propiedades que las pruebas deben cubrir:

- El orden es total y no depende del orden de declaración del enum de PostgreSQL.
- `higher_escalation_levels(especialista) == ()`.
- `is_higher_level` es estricto: el mismo nivel y los inferiores no son válidos.
- Las etiquetas son las de la especificación: «Nivel 1», «Nivel 2», «Especialista».

`users.escalation_level` se añade como `NOT NULL DEFAULT 'nivel_1'`; los usuarios existentes quedan en Nivel 1 sin migración de datos manual. La columna no se expone en la cola de trabajo ni en la línea temporal existente; solo se usa para candidatos, escalado y DTOs de cambio de responsable.

#### 1.2. Extensión de la línea temporal

`TimelineEventType` pasa a:

```python
class TimelineEventType(str, Enum):
    status_change = "status_change"
    resolution = "resolution"
    internal_comment = "internal_comment"
    assignee_change = "assignee_change"
```

`ticket_timeline_entries` recibe columnas **anulables** (las filas existentes no se tocan):

| Columna | Tipo | Nulo | Uso |
|---|---|---|---|
| `previous_assignee_id` | UUID FK `users.id` | Sí | Responsable anterior en `assignee_change` |
| `new_assignee_id` | UUID FK `users.id` | Sí | Responsable nuevo en `assignee_change` |
| `change_kind` | enum `assignee_change_kind` | Sí | `reassignment` o `escalation` |
| `from_escalation_level` | enum `escalation_level` | Sí | Nivel del responsable anterior |
| `to_escalation_level` | enum `escalation_level` | Sí | Nivel destino (igual en reasignación) |

Se añade `AssigneeChangeKind`:

```python
class AssigneeChangeKind(str, Enum):
    reassignment = "reassignment"
    escalation = "escalation"
```

Restricción nueva `ck_timeline_assignee_change`:

```text
(event_type <> 'assignee_change') OR (
    body IS NOT NULL
    AND is_internal = false
    AND from_status IS NULL
    AND to_status IS NULL
    AND previous_assignee_id IS NOT NULL
    AND new_assignee_id IS NOT NULL
    AND previous_assignee_id <> new_assignee_id
    AND change_kind IS NOT NULL
    AND from_escalation_level IS NOT NULL
    AND to_escalation_level IS NOT NULL
    AND (
        (change_kind = 'reassignment' AND from_escalation_level = to_escalation_level)
        OR
        (change_kind = 'escalation' AND from_escalation_level <> to_escalation_level)
    )
)
```

La dirección estricta del escalado (`to > from`) se valida en el servicio, no en el `CHECK`, para no depender de la comparación de enums en SQLite. Las restricciones existentes (`ck_timeline_status_change`, `ck_timeline_resolution`, `ck_timeline_internal_comment`, `ck_timeline_body_length`, `ck_timeline_event_order`, `uq_timeline_request_event`) se conservan sin cambios y siguen aplicándose solo a su tipo.

`TicketTimelineEntry` añade:

```python
previous_assignee_id: Mapped[uuid.UUID | None] = mapped_column(
    Uuid, ForeignKey("users.id"), nullable=True
)
new_assignee_id: Mapped[uuid.UUID | None] = mapped_column(
    Uuid, ForeignKey("users.id"), nullable=True
)
change_kind: Mapped[AssigneeChangeKind | None] = mapped_column(
    Enum(AssigneeChangeKind, name="assignee_change_kind", ...), nullable=True
)
from_escalation_level: Mapped[EscalationLevel | None] = mapped_column(
    Enum(EscalationLevel, name="escalation_level", ...), nullable=True
)
to_escalation_level: Mapped[EscalationLevel | None] = mapped_column(
    Enum(EscalationLevel, name="escalation_level", ...), nullable=True
)
```

Relaciones: al haber varias FKs a `users`, la relación existente debe desambiguarse:

```python
author: Mapped[User] = relationship(lazy="joined", foreign_keys=[author_id])
previous_assignee: Mapped[User | None] = relationship(
    lazy="joined", foreign_keys=[previous_assignee_id]
)
new_assignee: Mapped[User | None] = relationship(
    lazy="joined", foreign_keys=[new_assignee_id]
)
```

`event_order = 0` para `assignee_change`; el orden de lectura existente (`created_at`, `event_order`, `id`) se mantiene.

#### 1.3. Tabla de notificaciones

Nueva tabla `notifications`, vinculada al cambio que la origina:

| Columna | Tipo | Nulo | Notas |
|---|---|---|---|
| `id` | UUID PK | No | |
| `recipient_id` | UUID FK `users.id` | No | Solo el nuevo responsable |
| `ticket_id` | UUID FK `tickets.id` `ON DELETE CASCADE` | No | |
| `timeline_entry_id` | UUID FK `ticket_timeline_entries.id` `ON DELETE CASCADE` | No | **UNIQUE**: una notificación por cambio |
| `type` | enum `notification_type` | No | `ticket_reassigned` o `ticket_escalated` |
| `ticket_number` | `VARCHAR(20)` | No | Snapshot para la campana |
| `ticket_title` | `VARCHAR(200)` | No | Snapshot para la campana |
| `previous_assignee_name` | `VARCHAR(150)` | No | Snapshot para la campana |
| `is_read` | `BOOLEAN DEFAULT false` | No | Contador de no leídas |
| `created_at` | `TIMESTAMPTZ` | No | UTC |
| `read_at` | `TIMESTAMPTZ` | Sí | Se rellena al marcar leída |

Restricción `ck_notifications_read_at`:

```text
(is_read = false AND read_at IS NULL) OR (is_read = true AND read_at IS NOT NULL)
```

Índices:

- `ix_notifications_recipient_read_created` sobre `(recipient_id, is_read, created_at)`.
- `ix_notifications_ticket` sobre `(ticket_id)`.
- `UNIQUE (timeline_entry_id)`.

`NotificationType`:

```python
class NotificationType(str, Enum):
    ticket_reassigned = "ticket_reassigned"
    ticket_escalated = "ticket_escalated"
```

La tabla guarda **snapshots** de número, título y nombre del responsable anterior para que la campana no dependa de joins ni de que el ticket cambie después. No se guarda el motivo en la notificación; el motivo vive en la línea temporal y se consulta al abrir el ticket.

#### 1.4. Migración `0004_assignee_changes`

Fichero: `backend/alembic/versions/0004_assignee_changes_notifications.py`.

- `revision = "0004_assignee_changes"`, `down_revision = "0003_ticket_timeline"`.
- Crea los tipos `escalation_level`, `assignee_change_kind` y `notification_type`.
- Añade `users.escalation_level` con `server_default='nivel_1'` y `NOT NULL`.
- Añade el valor `assignee_change` a `timeline_event_type`. En PostgreSQL se ejecuta dentro de `op.get_context().autocommit_block()` para que el valor quede confirmado antes de usarlo en la restricción de la misma migración; `IF NOT EXISTS` hace la operación repetible.
- Añade las cinco columnas anulables a `ticket_timeline_entries`, sus FKs y `ck_timeline_assignee_change`.
- Crea `notifications` con sus restricciones e índices.
- Añade `ix_users_role_active_level_team` sobre `(role, is_active, escalation_level, team)` para la consulta de candidatos.
- `downgrade()`:
  1. Elimina `notifications` y sus índices.
  2. Elimina `ck_timeline_assignee_change` y las FKs/columnas nuevas de `ticket_timeline_entries`.
  3. Borra las filas con `event_type = 'assignee_change'` (pérdida deliberada de los datos de HU-06; requiere copia de seguridad).
  4. Convierte `ticket_timeline_entries.event_type` a texto, elimina `timeline_event_type` y lo recrea sin `assignee_change`; vuelve a convertir la columna al enum.
  5. Elimina `users.escalation_level` y el índice `ix_users_role_active_level_team`.
  6. Elimina los tipos `notification_type`, `assignee_change_kind` y `escalation_level`.
- En SQLite (pruebas) no se ejecuta la migración: `Base.metadata.create_all()` crea el esquema equivalente.

**Nota de despliegue**: la migración es aditiva hacia delante y puede aplicarse antes que el código. El `downgrade()` no es un simple `drop` porque PostgreSQL no permite quitar un valor de enum; se documenta como operación destructiva de los datos de HU-06 y se valida en PostgreSQL 16 antes de fusionar.

---

### 2. Backend: servicios y comandos

#### 2.1. Consulta de candidatos de reasignación

Fichero: `backend/app/services/assignee_change.py`.

```python
def reassignment_candidates(
    session: Session, ticket: Ticket, current_assignee: User
) -> list[User]:
    ...
```

Reglas:

- Rol `tecnico`, `is_active = true`.
- Mismo `escalation_level` que el responsable actual.
- Si el responsable actual tiene `team`, mismo `team`; si `team is None`, cualquier equipo.
- Excluye al responsable actual y al usuario creador del ticket (RN-03/RN-14).
- Orden estable para la UI: `lower(User.name).asc(), User.id.asc()`.
- La consulta se ejecuta en el momento de abrir las opciones y se repite en el comando.

La respuesta de opciones incluye `id`, `name`, `team`, `escalation_level` y `escalation_level_label`; no incluye datos internos ni correo.

#### 2.2. Selección determinista del escalado

```python
def escalation_targets(
    session: Session, current_assignee: User
) -> list[EscalationTarget]:
    ...

def select_escalation_assignee(
    session: Session, ticket: Ticket, target_level: EscalationLevel
) -> User | None:
    ...
```

`select_escalation_assignee` aplica, en este orden:

1. **Pool**: usuarios `role = tecnico`, `is_active = true`, `escalation_level = target_level`, excluyendo al usuario creador del ticket (`ticket.creator_id`).
2. **Preferencia de equipo**: si el responsable actual tiene `team`, se queda con los candidatos de ese equipo; si ese subconjunto está vacío, se usa el pool completo. Si el responsable actual no tiene equipo, se usa el pool completo.
3. **Menor carga activa**: `COUNT(tickets.id)` con `assignee_id = candidato.id` y `status IN ('abierto', 'en_progreso', 'pendiente_usuario')`.
4. **Desempate**: `lower(User.name)` ascendente y, si persiste, `User.id` ascendente.

La consulta usa un `LEFT JOIN`/subconsulta correlacionada sobre `tickets` (ya existe `ix_tickets_assignee_status_deadline`) y ordena en SQL. El resultado no depende del orden de inserción ni del plan de consulta. Si el pool queda vacío, devuelve `None` y el comando responde `409 no_technicians_available` sin escribir.

`escalation_targets` devuelve solo niveles estrictamente superiores al nivel del responsable actual, con `technician_count` e `is_available` (calculados con el pool del nivel excluyendo al usuario creador, sin preferencia de equipo, para que la UI sepa si hay alguien que pueda recibir el ticket).

#### 2.3. Endpoint de opciones

`GET /api/v1/tickets/{ticket_id}/assignee-change-options`

- Autorización: `get_current_user` + `ensure_assignee_change_actor(current_user, ticket)`. Los roles no técnicos reciben `403 forbidden`; el creador técnico no asignado recibe `forbidden` con precedencia sobre `not_ticket_assignee`; un técnico no asignado o anterior no creador recibe `403 not_ticket_assignee`. El creador que es el técnico asignado vigente puede consultar las opciones y ejecutar los comandos.
- Ticket inexistente: `404 ticket_not_found` (el lock/load ocurre antes de revelar roles).
- Estado final (`resuelto`, `cerrado`): `409 ticket_finalized`; no se devuelven candidatos porque la operación no es posible.
- Respuesta `200`:

```json
{
  "ticket_id": "…",
  "status": "en_progreso",
  "current_assignee": {
    "id": "…",
    "name": "Técnico A",
    "role": "tecnico",
    "team": "Soporte",
    "escalation_level": "nivel_1",
    "escalation_level_label": "Nivel 1"
  },
  "has_reassignment_candidates": true,
  "has_available_escalation_target": true,
  "reassignment_candidates": [
    {
      "id": "…",
      "name": "Técnico B",
      "role": "tecnico",
      "team": "Soporte",
      "escalation_level": "nivel_1",
      "escalation_level_label": "Nivel 1"
    }
  ],
  "escalation_targets": [
    {
      "value": "nivel_2",
      "label": "Nivel 2",
      "technician_count": 1,
      "is_available": true
    },
    {
      "value": "especialista",
      "label": "Especialista",
      "technician_count": 1,
      "is_available": true
    }
  ]
}
```

`has_reassignment_candidates` es verdadero si hay al menos un candidato; `has_available_escalation_target` es verdadero si hay al menos un nivel superior con `is_available = true`. Estos campos describen disponibilidad, no permiso; el permiso lo expresan `can_reassign`/`can_escalate` de `WorkflowResponse`. La UI muestra estados vacíos claros cuando ambos son falsos, pero el backend sigue siendo la defensa.

#### 2.4. Comando de reasignación

`POST /api/v1/tickets/{ticket_id}/reassignments`

Request:

```json
{
  "new_assignee_id": "…",
  "reason": "Estoy de vacaciones; el compañero conoce el caso.",
  "expected_updated_at": "2026-11-10T09:15:30.123456+00:00",
  "request_id": "6f1c2a7e-9b3d-4f4e-8a1b-2c3d4e5f6a7b"
}
```

Orden de validación (el servicio es la única fuente de verdad):

| # | Comprobación | Resultado si falla |
|---|---|---|
| 1 | Usuario autenticado (`get_current_user`) | `401 not_authenticated` |
| 2 | Ticket existe (`_locked_ticket`) | `404 ticket_not_found` |
| 3 | Ya existe una entrada `assignee_change` con ese `request_id`: si coinciden actor, tipo `reassignment`, `new_assignee_id` y motivo normalizado ⇒ replay; si difiere cualquier dato ⇒ conflicto | `200 changed=false`, `message` de replay, `timeline_entry = null` / `409 request_id_reused` |
| 4 | `ensure_assignee_change_actor(current_user, ticket)` para solicitudes nuevas (rol no técnico → `forbidden`; técnico no asignado y creador → `forbidden`; técnico no asignado no creador → `not_ticket_assignee`; el creador asignado puede operar) | `403 forbidden` / `403 not_ticket_assignee` |
| 5 | `reason.strip()` no vacío y ≤ 5.000 caracteres | `422 reason_required` / `422 reason_too_long` |
| 6 | `expected_updated_at == ticket.updated_at` | `409 stale_ticket` |
| 7 | Estado activo (`abierto`, `en_progreso`, `pendiente_usuario`) | `409 ticket_finalized` |
| 8 | Destino distinto del responsable actual | `422 self_reassignment` |
| 9 | Destino distinto del usuario creador | `422 creator_not_assignable` |
| 10 | Destino existe y está activo; si no, `assignee_unavailable`. Si está activo, tiene rol `tecnico`, mismo equipo (si el actual tiene equipo) y mismo nivel; si no, `invalid_reassignment_target` | `422 assignee_unavailable` / `422 invalid_reassignment_target` |
| 11 | Escritura atómica | `500 internal_error` con rollback |

La comprobación 3 se ejecuta antes que la 4 y que las validaciones de payload para que un reintento idéntico sea idempotente aunque el actor haya dejado de ser responsable. Solo un replay exacto del mismo actor evita `ensure_assignee_change_actor`; una solicitud nueva con otro `request_id` siempre exige asignación vigente. La 5 se adelanta a la 6 para dar un error de formulario claro sin consultar versiones. La 6 se adelanta a la 7 para pedir al cliente que refresque antes de diagnosticar un ticket finalizado sobre datos obsoletos. El destino se revalida siempre aunque venga de la lista de opciones.

#### 2.5. Comando de escalado

`POST /api/v1/tickets/{ticket_id}/escalations`

Request:

```json
{
  "target_level": "nivel_2",
  "reason": "Requiere permisos de administración del servidor.",
  "expected_updated_at": "2026-11-10T09:15:30.123456+00:00",
  "request_id": "0b9e4d6a-1c2f-4a3b-8d7e-5f6a7b8c9d0e"
}
```

El orden es el mismo que en la reasignación, sustituyendo las comprobaciones 8-10 por:

| # | Comprobación | Resultado si falla |
|---|---|---|
| 8 | Existe al menos un nivel superior en el catálogo para el nivel del responsable actual | `409 no_higher_level` |
| 9 | `target_level` estrictamente superior al nivel del responsable actual | `422 invalid_escalation_level` |
| 10 | Hay al menos un técnico activo en el nivel destino, excluyendo al usuario creador | `409 no_technicians_available` |
| 11 | Selección determinista del nuevo responsable (§2.2) | `409 no_technicians_available` si el pool queda vacío |
| 12 | Escritura atómica | `500 internal_error` con rollback |

La comprobación 8 va antes que la 9 para que un responsable en el nivel máximo reciba siempre `409 no_higher_level`, sea cual sea el `target_level` enviado, en lugar de un `422` que sugeriría que existe otro nivel válido. La comprobación 3 sigue ejecutándose antes que `ensure_assignee_change_actor`, de modo que el reintento de un escalado original sigue siendo idempotente aunque el actor ya no sea el responsable.

El técnico **no elige persona** al escalar, solo nivel. El backend selecciona al responsable con la regla determinista y lo devuelve en la respuesta; el frontend no calcula ni preselecciona candidatos.

#### 2.6. Idempotencia, concurrencia y atomicidad

- `request_id` es obligatorio (UUID) y actúa como clave de idempotencia. La restricción existente `UNIQUE (ticket_id, request_id, event_type)` es la defensa en profundidad.
- Replay idéntico: mismo actor, mismo tipo, mismo destino (persona en reasignación; nivel en escalado) y mismo motivo normalizado ⇒ `200 changed=false`, sin entrada nueva, sin notificación nueva y `timeline_entry = null`. No se reselecciona al responsable en un replay de escalado.
- El replay exacto se busca por `(ticket_id, request_id, event_type='assignee_change')` antes de `ensure_assignee_change_actor`. Así, si la respuesta original se perdió y el actor ya dejó de ser responsable, el reintento de red sigue siendo idempotente. Cualquier solicitud con un `request_id` nuevo exige asignación vigente.
- Reutilización con otros datos, otro actor u otro tipo ⇒ `409 request_id_reused` sin escribir.
- `expected_updated_at` es obligatorio. El servicio bloquea la fila con `SELECT id FROM tickets WHERE id = :id FOR UPDATE` (PostgreSQL), recarga con `populate_existing=True` y compara `as_utc(ticket.updated_at)` antes de escribir. Si no coincide ⇒ `409 stale_ticket`.
- La transacción:

```text
BEGIN
  SELECT id FROM tickets WHERE id = :id FOR UPDATE
  SELECT * FROM tickets WHERE id = :id          -- populate_existing
  validar (tablas §2.4/§2.5)
  tickets.assignee_id  = new_assignee.id
  tickets.updated_at   = now                    -- único instante para todo el comando
  -- status, priority_id, category_id, sla_deadline, sla_version,
  -- finalized_at y closed_at NO se tocan
  INSERT ticket_timeline_entries (assignee_change, previous/new, kind, levels, body, author, now, request_id)
  INSERT notifications (recipient=new_assignee, ticket, timeline_entry, type, snapshots, now)
  COMMIT
```

- Cualquier excepción ejecuta `rollback()` y se traduce a `500 internal_error`; nunca queda un cambio parcial. `expire_on_commit=False` permite serializar el ticket actualizado.
- En SQLite `FOR UPDATE` no aplica; la corrección funcional se prueba con `expected_updated_at` y las pruebas de concurrencia real se ejecutan contra PostgreSQL.

#### 2.7. Permisos y capacidades

Se añade en `ticket_workflow.py` un helper específico de HU-06, `ensure_assignee_change_actor(user, ticket)`, sin modificar `_ensure_writer` de HU-05 (que sigue gobernando los comandos de estado y comentarios de esa historia y evita regresiones):

```python
def ensure_assignee_change_actor(user: User, ticket: Ticket) -> None:
    """Solo el técnico asignado vigente puede consultar opciones y cambiar el responsable.

    El creador con rol técnico no asignado recibe `403 forbidden` (RN-11) con
    precedencia sobre `403 not_ticket_assignee`. Si el creador es el técnico
    asignado, actúa en su capacidad de responsable y la operación se permite.
    """

    if user.role != UserRole.tecnico:
        raise _forbidden()
    if ticket.assignee_id is None or ticket.assignee_id != user.id:
        if user.id == ticket.creator_id:
            raise _forbidden()
        raise _not_assignee()
```

Precedencia explícita (HU06-RN-11):

- Rol distinto de `tecnico` (supervisor, admin o usuario) ⇒ `403 forbidden`.
- Técnico no asignado que además es el usuario creador ⇒ `403 forbidden`; la condición de creador tiene precedencia sobre la de asignación, de modo que no recibe `not_ticket_assignee`.
- Técnico no asignado o técnico anterior que no es el creador ⇒ `403 not_ticket_assignee`.
- Si el creador es el técnico asignado vigente, la operación se permite: actúa en su capacidad de responsable, no como creador (escenario `TK-000101` del quickstart). El creador sigue excluido como **destino** de la reasignación y del pool de escalado.
- El replay idéntico de HU06-RN-13 se resuelve antes de este helper y no escribe; cualquier solicitud nueva exige asignación vigente.
- La comprobación se hace contra `ticket.assignee_id` recargado tras el lock, no contra datos del cliente.

`WorkflowResponse` se amplía de forma aditiva:

```json
{
  "ticket": { "...": "..." },
  "can_change_status": true,
  "can_comment_internally": true,
  "can_view_internal": true,
  "can_reassign": true,
  "can_escalate": true
}
```

Cálculo en `get_workflow`:

- `can_reassign = user.role == tecnico and ticket.assignee_id == user.id and ticket.status in DEFAULT_ACTIVE_STATUSES`.
- `can_escalate = can_reassign and assignee.escalation_level != especialista` (permiso; el nivel se lee del usuario asignado en servidor). No depende de que existan técnicos en el nivel superior: esa disponibilidad se expone en `has_available_escalation_target`.
- Los roles no técnicos (supervisor, admin) y el creador técnico no asignado reciben ambos `false`; el creador que es el técnico asignado vigente los recibe según las reglas anteriores (opera como responsable); el técnico anterior los pierde en la siguiente lectura.
- `viewer_capabilities` sigue gobernando `can_view_internal`, `can_change_status` y `can_comment_internally`; al cambiar `assignee_id`, el técnico anterior deja de ver comentarios internos y el nuevo los ve, sin cambios adicionales.

#### 2.8. Servicio de notificaciones

Fichero: `backend/app/services/notifications.py`.

- `create_assignee_change_notification(session, ticket, entry, previous_assignee, new_assignee, kind, now)` construye la fila con snapshots y la añade a la sesión; no hace `commit()` para participar en la transacción del comando.
- `list_notifications(session, user, *, page, page_size, unread_only)` devuelve la página ordenada por `created_at DESC, id DESC` y el `unread_count` de todo el usuario.
- La paginación de notificaciones usa `NotificationPagination` con `page_size` 1..100 y defecto 20; no reutiliza el `Pagination` de HU-05, que permite hasta 200.
- `mark_notification_read(session, user, notification_id)`:
  - Si no existe o `recipient_id != user.id` ⇒ `404 notification_not_found` (no revela notificaciones ajenas).
  - Si ya está leída ⇒ `200 changed=false` sin escribir.
  - Si no ⇒ `is_read=true`, `read_at=now`, `commit()`; `200 changed=true`.
- La bandeja solo devuelve notificaciones del usuario autenticado; no hay endpoint para leer las de otro.

#### 2.9. Endpoints y errores

| Método | Ruta | Propósito | Éxito |
|---|---|---|---|
| `GET` | `/api/v1/tickets/{ticket_id}/assignee-change-options` | Candidatos, niveles y capacidades | `200` |
| `POST` | `/api/v1/tickets/{ticket_id}/reassignments` | Reasignar a un compañero | `200` |
| `POST` | `/api/v1/tickets/{ticket_id}/escalations` | Escalar a un nivel superior | `200` |
| `GET` | `/api/v1/me/notifications?page=&page_size=&unread_only=` | Bandeja y contador | `200` |
| `POST` | `/api/v1/me/notifications/{notification_id}/read` | Marcar como leída | `200` |

No se exponen `PUT`, `PATCH` ni `DELETE` sobre entradas de línea temporal ni notificaciones. El marcado de lectura es un comando POST idempotente.

**Catálogo de errores** (formato `{"detail": {"code": "...", "message": "..."}}`):

| HTTP | `code` | Mensaje (es-ES) |
|---|---|---|
| 401 | `not_authenticated` | «La sesión no es válida o ha caducado.» |
| 403 | `forbidden` | «No tienes permiso para modificar este ticket.» |
| 403 | `not_ticket_assignee` | «Este ticket ya no está asignado a ti.» |
| 404 | `ticket_not_found` | «No se ha encontrado el ticket.» |
| 404 | `notification_not_found` | «No se ha encontrado la notificación.» |
| 409 | `ticket_finalized` | «El ticket está finalizado y no admite cambios de responsable.» |
| 409 | `stale_ticket` | «El ticket ha sido modificado por otra persona. Actualiza la información e inténtalo de nuevo.» |
| 409 | `assignee_inconsistent` | «El responsable del ticket no coincide con el último cambio registrado. Actualiza la información e inténtalo de nuevo.» |
| 409 | `request_id_reused` | «La solicitud ya se utilizó con otros datos. Genera una nueva solicitud e inténtalo de nuevo.» |
| 409 | `no_higher_level` | «El ticket ya está en el nivel máximo de soporte.» |
| 409 | `no_technicians_available` | «No hay técnicos disponibles en ese nivel en este momento.» |
| 422 | `invalid_request` | «La solicitud no es válida. Revisa los datos e inténtalo de nuevo.» |
| 422 | `reason_required` | «Indica el motivo del cambio de responsable.» |
| 422 | `reason_too_long` | «El motivo no puede superar los 5.000 caracteres.» |
| 422 | `self_reassignment` | «No puedes reasignarte el ticket a ti mismo.» |
| 422 | `creator_not_assignable` | «Ese usuario no puede recibir este ticket.» |
| 422 | `invalid_reassignment_target` | «Solo puedes reasignar a técnicos activos de tu equipo y de tu nivel.» |
| 422 | `assignee_unavailable` | «El técnico seleccionado ya no está disponible. Actualiza la lista e inténtalo de nuevo.» |
| 422 | `invalid_escalation_level` | «Debes elegir un nivel superior al del responsable actual.» |
| 500 | `internal_error` | «No se pudo guardar el cambio. El ticket no se ha modificado. Inténtalo de nuevo.» |

Los payloads mal formados (UUID inválido, enum desconocido, fecha no ISO, campo extra) se normalizan a `422 invalid_request` mediante el handler existente de `RequestValidationError`.

---

### 3. Frontend: componentes y experiencia

#### 3.1. Árbol de componentes

```text
App.vue
├── AppHeader.vue                         (visible salvo en /login)
│   └── NotificationBell.vue              (campana, contador y desplegable)
│       └── NotificationList.vue          (lista y marcado de lectura)
└── RouterView
    └── TicketDetailPage.vue
        └── TicketWorkflowPanel.vue        (orquestador existente)
            ├── TicketStatusSelector.vue   (HU-05, sin cambios)
            ├── ResolutionForm.vue         (HU-05, sin cambios)
            ├── InternalCommentForm.vue    (HU-05, sin cambios)
            ├── TicketAssigneeChangePanel.vue   (NUEVO)
            │   ├── AssigneeSelector.vue        (NUEVO)
            │   ├── EscalationLevelSelector.vue (NUEVO)
            │   └── AssigneeChangeReasonForm.vue(NUEVO)
            └── TicketTimeline.vue          (ampliado con assignee_change)
```

`TicketAssigneeChangePanel` se renderiza en la columna izquierda del detalle, debajo del panel de estado y antes del formulario de comentario. Solo se monta si `canReassign || canEscalate`; si no, no se muestra ninguna acción (el backend ya denegaría).

#### 3.2. `TicketAssigneeChangePanel.vue` — orquestador

**Props**: `ticketId: string`, `ticket: TicketWorkflowSnapshot`, `canReassign: boolean`, `canEscalate: boolean`, `disabled?: boolean`.

**Emits**: `changed` (el padre recarga workflow/timeline), `notice` (mensaje para `aria-live`).

**Estado local**:

```text
mode: 'reassign' | 'escalate' | null
options: AssigneeChangeOptions | null
optionsLoading, optionsError
selectedAssigneeId: string | null
selectedLevel: EscalationLevel | null
reasonText: string
reasonError: string | null
requestId: string
lastRequestSignature: string
submitting: boolean
error, errorCode, notice
```

**Flujo de carga**:

1. Al montar (y cuando cambie `ticket.updated_at`), si `canReassign || canEscalate`, `GET /tickets/{id}/assignee-change-options` con `AbortController`.
2. Si `409 ticket_finalized`, muestra el aviso y no renderiza controles.
3. Si `403 not_ticket_assignee`, muestra «Este ticket ya no está asignado a ti.» y emite una recarga del workflow para que el panel de estado también se actualice.
4. Si falla la red, muestra un aviso con botón «Reintentar».

**Flujo de envío**:

1. Valida `mode` y destino: reasignación exige `selectedAssigneeId`; escalado exige `selectedLevel`.
2. Valida `reasonText.trim()` entre 1 y 5.000; si no, marca `reasonError` y enfoca el textarea.
3. Deshabilita el botón (`submitting = true`) y genera/recupera un `request_id` estable por firma `mode|destino|reason.trim()`; si la firma cambia, se genera uno nuevo.
4. Envía `POST /reassignments` o `/escalations` con `expected_updated_at = ticket.updated_at`.
5. En éxito (`changed=true`): limpia selección y motivo, muestra «El cambio de responsable se ha aplicado.», emite `changed` para recargar workflow, timeline y opciones. Como el actor deja de ser responsable, el panel desaparece en la recarga.
6. En replay (`changed=false`): muestra el `message` del backend, limpia selección y emite `changed` (sin duplicar nada).
7. En `409 stale_ticket` / `ticket_finalized` / `invalid_reassignment_target` / `no_technicians_available`: muestra el mensaje, conserva el motivo y recarga opciones y workflow.
8. En `409 request_id_reused`: muestra el mensaje y regenera `request_id` para el siguiente intento.
9. En `422 reason_required` / `reason_too_long`: asocia el error al textarea y enfoca.
10. En error de red/500: muestra «No se pudo guardar el cambio. El ticket no se ha modificado. Inténtalo de nuevo.» y conserva los datos.

**Plantilla (esquema)**:

```vue
<section class="rounded-lg border border-slate-200 bg-white p-6" aria-labelledby="assignee-change-heading">
  <h2 id="assignee-change-heading" class="text-base font-semibold text-slate-900">
    Cambiar responsable
  </h2>

  <fieldset class="mt-4">
    <legend class="text-sm font-medium text-slate-800">Tipo de cambio</legend>
    <label v-if="canReassign">
      <input v-model="mode" type="radio" value="reassign" :disabled="submitting" />
      Reasignar a un compañero
    </label>
    <label v-if="canEscalate">
      <input v-model="mode" type="radio" value="escalate" :disabled="submitting" />
      Escalar a un nivel superior
    </label>
  </fieldset>

  <AssigneeSelector
    v-if="mode === 'reassign'"
    v-model="selectedAssigneeId"
    :candidates="options?.reassignment_candidates ?? []"
    :disabled="submitting"
  />
  <EscalationLevelSelector
    v-else-if="mode === 'escalate'"
    v-model="selectedLevel"
    :targets="options?.escalation_targets ?? []"
    :disabled="submitting"
  />
  <AssigneeChangeReasonForm
    v-if="mode"
    v-model="reasonText"
    :disabled="submitting"
    :error="reasonError"
  />

  <p v-if="error" role="alert" class="mt-3 text-sm text-red-700">{{ error }}</p>
  <p v-if="notice" role="status" aria-live="polite" class="mt-3 text-sm text-emerald-700">{{ notice }}</p>

  <div v-if="mode" class="mt-4 flex justify-end gap-2">
    <button type="button" :disabled="!canSubmit" @click="submit">
      {{ submitting ? 'Guardando…' : 'Confirmar cambio' }}
    </button>
  </div>
</section>
```

#### 3.3. `AssigneeSelector.vue`

- `<fieldset>` + `<legend>` «Compañero destino».
- Renderiza un `<select>` nativo (o radios) con los candidatos; cada opción muestra `name` y `team` («Técnico B · Soporte»), y un texto secundario con el nivel.
- Excluye al responsable actual y al creador porque el backend no los envía; si la lista está vacía, muestra «No hay compañeros disponibles de tu equipo y nivel.» y no renderiza el selector.
- `aria-required="true"`, `aria-describedby` con la ayuda, foco visible, navegación por teclado.
- Emite `update:modelValue` con el `id` seleccionado.

#### 3.4. `EscalationLevelSelector.vue`

- `<fieldset>` + `<legend>` «Nivel destino».
- Solo renderiza los niveles superiores que devuelve el backend; nunca calcula el orden en cliente.
- Cada nivel muestra `label` y, si `is_available = false`, el texto «Sin técnicos disponibles» y el control deshabilitado.
- Si no hay niveles superiores, muestra «El ticket ya está en el nivel máximo de soporte.» y no renderiza controles.
- Emite `update:modelValue` con el `value` seleccionado.

#### 3.5. `AssigneeChangeReasonForm.vue`

- `<textarea>` con etiqueta «Motivo del cambio de responsable», `rows="4"`, `:maxlength="5000"`, `aria-required="true"`, `:aria-invalid="Boolean(error)"`, `aria-describedby` apuntando al contador y al error.
- Ayuda: «Obligatorio. El usuario creador podrá ver este motivo en la línea temporal.»
- Contador visible `{{ trimmedLength }} / 5000`; se calcula con `modelValue.trim().length`.
- Error inline con `role="alert"` y foco en el textarea cuando el padre lo solicita.
- No usa `v-html`; el motivo se renderiza como texto plano en la timeline.

#### 3.6. Campana de notificaciones

`NotificationBell.vue`:

- Botón con icono de campana (`lucide-vue-next` ya instalado), `aria-label` «Notificaciones, N sin leer» y `aria-expanded`/`aria-controls` del desplegable.
- Contador visible si `unreadCount > 0`; `aria-live="polite"` para anunciar cambios sin interrumpir.
- Al abrir, muestra `NotificationList` con las notificaciones más recientes (página 1, 20 elementos).
- Al hacer clic en una notificación: `POST /me/notifications/{id}/read`, actualiza el contador y navega a `/tickets/{ticket_id}`.
- Cierra con `Escape`, clic fuera o al navegar; devuelve el foco al botón.
- Si el usuario no tiene token o la petición devuelve `401`, no muestra datos y detiene el sondeo; la vista de cola ya redirige al login.

`NotificationList.vue`:

- Lista `<ul>` con `<li>` por notificación; cada elemento es un botón accesible.
- Muestra título «Ticket reasignado» / «Ticket escalado», `ticket_number`, `ticket_title`, «Anterior responsable: {previous_assignee_name}» y fecha en `Europe/Madrid`.
- Distingue no leídas con un punto/etiqueta textual «No leída», no solo con color.
- Estado vacío: «No tienes notificaciones.»
- Estado de carga y error con `role="status"`/`role="alert"`.

**Sondeo** (`stores/notifications.ts`):

- `POLL_INTERVAL_MS = 15_000`.
- `startPolling()`: `setInterval` que solo ejecuta si `document.visibilityState !== 'hidden'`.
- `focus` y `visibilitychange` (visible) disparan una recarga inmediata.
- `stopPolling()` limpia el intervalo y los listeners; se llama en `onUnmounted` de `AppHeader`.
- Cada carga usa `AbortController` y una secuencia para descartar respuestas fuera de orden.
- `unreadCount` se actualiza con el campo `unread_count` de la respuesta, no contando localmente la página.
- El sondeo de la cola de trabajo (60 s) no se modifica.

#### 3.7. Línea temporal

`TicketTimeline.vue` añade una rama para `entry.type === 'assignee_change'`:

- Etiqueta «Cambio de responsable».
- Subtipo textual: «Reasignación» o «Escalado a {to_escalation_level_label}».
- Texto: «{author.name} reasignó el ticket de {previous_assignee.name} a {new_assignee.name}.» o «{author.name} escaló el ticket de {previous_assignee.name} ({from label}) a {new_assignee.name} ({to label}).»
- Bloque «Motivo» con `entry.body` como texto plano (`whitespace-pre-wrap break-words`).
- Estilo público (no interno): `border-sky-200 bg-sky-50 text-sky-900`, con etiquetas textuales para no depender del color.
- La entrada es visible para el creador porque el backend la devuelve con `is_internal = false`; no se añade lógica de visibilidad en cliente.
- Las entradas antiguas sin los nuevos campos se siguen renderizando sin cambios.

#### 3.8. Servicios, tipos y store

`frontend/src/services/assigneeChange.ts`:

```ts
export function getAssigneeChangeOptions(ticketId: string, signal?: AbortSignal): Promise<AssigneeChangeOptions>
export function reassignTicket(ticketId: string, payload: ReassignmentRequest, signal?: AbortSignal): Promise<AssigneeChangeResponse>
export function escalateTicket(ticketId: string, payload: EscalationRequest, signal?: AbortSignal): Promise<AssigneeChangeResponse>
```

`frontend/src/services/notifications.ts`:

```ts
export function getNotifications(params: { page?: number; page_size?: number; unread_only?: boolean }, signal?: AbortSignal): Promise<NotificationListResponse>
export function markNotificationRead(notificationId: string, signal?: AbortSignal): Promise<MarkNotificationReadResponse>
```

`frontend/src/types/assigneeChange.ts` define `EscalationLevel`, `AssigneeChangeKind`, `AssigneeRef`, `ReassignmentCandidate`, `EscalationTarget`, `AssigneeChangeOptions`, `ReassignmentRequest`, `EscalationRequest`, `AssigneeChangeResponse`.

`frontend/src/types/notifications.ts` define `NotificationType`, `Notification`, `NotificationListResponse`, `MarkNotificationReadResponse`.

`frontend/src/types/ticketWorkflow.ts` amplía:

```ts
export type TimelineEventType =
  | 'status_change'
  | 'resolution'
  | 'internal_comment'
  | 'assignee_change'

export interface TimelineEntry {
  // campos existentes…
  change_kind: 'reassignment' | 'escalation' | null
  previous_assignee: AssigneeRef | null
  new_assignee: AssigneeRef | null
  from_escalation_level: EscalationLevel | null
  from_escalation_level_label: string | null
  to_escalation_level: EscalationLevel | null
  to_escalation_level_label: string | null
}

export interface WorkflowResponse {
  // campos existentes…
  can_reassign: boolean
  can_escalate: boolean
}
```

`frontend/src/stores/ticketDetail.ts` amplía el estado con `canReassign`, `canEscalate`, `assigneeOptions`, `assigneeOptionsLoading`, `assigneeSubmitting`, `assigneeError`, `assigneeErrorCode`, `assigneeNotice`, y las acciones `loadAssigneeOptions(ticketId)`, `reassign(ticketId, payload)`, `escalate(ticketId, payload)`, `refreshAfterAssigneeChange(ticketId)`. Tras un cambio exitoso, `refreshAfterAssigneeChange` recarga `workflow`, `timeline` y (si el usuario sigue siendo responsable) las opciones; como el actor deja de serlo, las capacidades se recalculan a `false`.

`App.vue` monta `AppHeader` fuera de `RouterView` y lo oculta en la ruta `login`:

```vue
<template>
  <AppHeader v-if="$route.name !== 'login'" />
  <RouterView />
</template>
```

#### 3.9. Accesibilidad y responsive

- Grupos de radios/selects con `fieldset`/`legend` y etiquetas asociadas.
- `aria-required`, `aria-invalid`, `aria-describedby` para motivo y destino.
- Errores con `role="alert"`; avisos de éxito con `role="status"` y `aria-live="polite"`.
- Foco visible en todos los controles (`focus-visible:ring-2`), foco gestionado al abrir/cerrar la campana y al enfocar errores.
- La campana y el panel funcionan solo con teclado; `Escape` cierra el desplegable.
- Layout de una columna en móvil/tablet y dos columnas en desktop, igual que el detalle actual; el panel no depende del ancho.
- Etiquetas textuales junto a los colores («No leída», «Reasignación», «Escalado», «Sin técnicos disponibles»).
- Se añaden pruebas con `axe-core` para los componentes nuevos, siguiendo `WorkQueueAccessibility.spec.ts`.

---

### 4. Impacto en la cola de trabajo

- No se crea ninguna tabla de colas ni se modifica `backend/app/services/work_queue.py`.
- La cola se deriva de `Ticket.assignee_id == current_user.id` y `Ticket.status IN (...)`; al actualizar `assignee_id` y `updated_at` en la misma transacción, el ticket sale de la consulta del técnico anterior y entra en la del nuevo.
- La vista de cola ya sondea cada 60 s y refresca al recuperar foco/visibilidad (`frontend/src/stores/workQueue.ts`); cumple RF-021/RF-022 sin cambios.
- La prioridad, el SLA y el orden se recalculan con las reglas de HU-04 porque el ticket conserva `priority_id`, `sla_deadline`, `created_at` y `status`.
- El técnico anterior conserva acceso de lectura pública (`can_read_ticket` por rol `tecnico`), pero pierde `can_change_status`, `can_comment_internally`, `can_view_internal`, `can_reassign` y `can_escalate` en la siguiente lectura del workflow.

---

### 5. Trazabilidad y coherencia con la arquitectura existente

#### 5.1. Lo que **no** cambia

- **Stack**: PostgreSQL + FastAPI + SQLAlchemy 2.0 + Alembic + Vue 3 + Tailwind + Pinia + Vue Router.
- **Modelo base**: `tickets`, `priorities`, `categories` conservan sus columnas y restricciones. No se añade `resolution` ni `version` a `tickets`.
- **Estados**: `TicketStatus` y la matriz de HU-05 no se modifican; el cambio de responsable no es una transición de estado y no crea `status_change`.
- **Cola de trabajo**: sigue leyendo `status`, `finalized_at`, `sla_deadline` y `assignee_id`; no requiere cambios.
- **Formato de errores**: `{"detail":{"code","message"}}` y mensajes es-ES.
- **Autenticación**: JWT Bearer; `get_current_user` se reutiliza y `ensure_assignee_change_actor` concentra la autorización de HU-06.
- **Endpoints de HU-05**: `/workflow`, `/status-transitions`, `/internal-comments` y `/timeline` mantienen su contrato; solo se amplía la respuesta de `workflow` y los campos opcionales de `TimelineEntry`.

#### 5.2. Lo que se añade de forma aditiva

- Enums `EscalationLevel`, `AssigneeChangeKind` y `NotificationType`; valor `assignee_change` en `TimelineEventType`.
- `users.escalation_level` (NOT NULL DEFAULT `nivel_1`).
- Columnas de cambio de responsable en `ticket_timeline_entries` y relaciones `previous_assignee`/`new_assignee`.
- Tabla `notifications` e índices.
- Servicios `assignee_change.py` y `notifications.py`.
- Esquemas `assignee_change.py` y `notification.py`; ampliación de `ticket_workflow.py`.
- Endpoints de opciones, reasignación, escalado y notificaciones.
- Componentes Vue, servicios, tipos, stores y pruebas.
- `AppHeader` con la campana y su sondeo de 15 s.

#### 5.3. Invariantes de coherencia

1. **Responsable ↔ línea temporal**: tras un cambio confirmado, el último `assignee_change` del ticket tiene `new_assignee_id = tickets.assignee_id` y `previous_assignee_id` igual al responsable anterior. Se comprueba en pruebas y en el quickstart.
2. **Append-only**: no hay endpoints de actualización/borrado de entradas; el motivo y los responsables quedan inmutables.
3. **Atomicidad**: cambio + entrada + notificación se confirman juntos; un rechazo o error no deja rastro.
4. **Una notificación por cambio**: `UNIQUE (timeline_entry_id)` y el replay idempotente evitan duplicados.
5. **Sin efectos colaterales**: `status`, `priority_id`, `category_id`, `sla_deadline`, `sla_version`, `finalized_at` y `closed_at` no cambian.
6. **Visibilidad**: `assignee_change` es público (`is_internal = false`) y se filtra en SQL como el resto; el creador lo ve con motivo.
7. **Permisos**: solo el técnico asignado vigente ejecuta y consulta opciones; el técnico anterior recibe `403 not_ticket_assignee` y pierde acceso interno, salvo en el replay idéntico, que no escribe.
8. **Idempotencia**: mismo `request_id` + mismos datos ⇒ sin escritura; datos distintos ⇒ `409 request_id_reused`.
9. **Concurrencia**: `expected_updated_at` desactualizado ⇒ `409 stale_ticket` y cero escrituras.
10. **Determinismo**: el escalado produce el mismo responsable ante el mismo estado del sistema (mismo equipo, carga, nombre e id).

#### 5.4. Observabilidad

- `logging` estándar con un `INFO` por comando exitoso: `ticket_id`, `actor_id`, `previous_assignee_id`, `new_assignee_id`, `change_kind`, `from_level`, `to_level`, `changed`, `request_id`, `duration_ms`.
- `WARNING` en rechazos con `code`, `ticket_id` y, cuando aplique, `actor_id`.
- `ERROR` con `logger.exception` en fallos inesperados.
- **No** se registra el texto del motivo en logs (puede contener información sensible); solo se registra su longitud si hace falta para diagnóstico.
- No se añaden métricas ni trazas externas.

#### 5.5. Compatibilidad y despliegue

- La migración puede aplicarse antes del código: las columnas nuevas son anulables, `users.escalation_level` tiene defecto y `assignee_change` no lo usa el código antiguo.
- El frontend antiguo sigue funcionando: los campos nuevos de `workflow` y `timeline` son aditivos; los clientes que no los lean los ignoran.
- Los clientes que no envíen `expected_updated_at` o `request_id` reciben `422 invalid_request`, no un cambio silencioso.
- `AUTH_DEV_STUB_ENABLED` debe permanecer desactivado en producción; el stub de login es solo para desarrollo/pruebas.
- El `downgrade()` de `0004` destruye datos de HU-06; se documenta en `data-model.md` y se prueba en PostgreSQL antes de fusionar.

## Estrategia de pruebas

La estrategia aplica el principio IV de la Constitución: contratos antes de implementar, pruebas ejecutables por capa y concurrencia real sobre PostgreSQL. No se añaden frameworks ni dependencias de prueba; se reutilizan `pytest`, `TestClient`/`httpx`, Vitest, `@vue/test-utils` y `axe-core`.

### Criterios transversales

- **Aislamiento**: cada prueba parte de un esquema limpio (el fixture `db` recrea las tablas), crea sus propios usuarios, equipos, niveles y tickets y no depende de `scripts/seed_dev.py` ni del orden de ejecución.
- **Determinismo**: fechas y UUID explícitos. Las pruebas de orden fijan `created_at`, carga activa, `name` e `id` para no depender del orden físico de las filas.
- **Dos motores**: SQLite para pruebas funcionales rápidas; PostgreSQL para concurrencia, `SELECT ... FOR UPDATE`, enums nativos y migraciones.
- **Sin efectos colaterales**: toda prueba de éxito compara `status`, `priority_id`, `category_id`, `sla_deadline`, `sla_version`, `finalized_at` y `closed_at` antes y después del comando.
- **Contratos primero**: las pruebas de contrato validan el OpenAPI y el contrato de componentes; cualquier cambio de DTO obliga a actualizar ambos artefactos y sus pruebas.
- **Idempotencia verificable**: además del resultado HTTP, se cuentan filas de `ticket_timeline_entries` y `notifications` antes y después para demostrar que un replay no escribe.

### Backend

| Área | Archivo | Casos mínimos |
|---|---|---|
| Catálogo de niveles | `tests/unit/test_escalation_levels.py` | Orden total independiente del enum de PostgreSQL; etiquetas «Nivel 1», «Nivel 2», «Especialista»; `higher_escalation_levels(especialista) == ()`; `is_higher_level` estricto (igual e inferior no válidos) |
| Selección de responsable | `tests/unit/test_assignee_selection.py` | Preferencia por el mismo equipo; menor carga activa; desempate por `lower(name)`; desempate final por `User.id`; ausencia de candidatos; independencia del orden de entrada |
| Reasignación | `tests/integration/test_ticket_reassignment.py` | Éxito con entrada `assignee_change` y notificación; candidatos del mismo equipo y nivel; exclusión del responsable actual, del creador técnico y de inactivos; rechazo de otro equipo/nivel; motivo de 1, 5.000, 0, 5.001 caracteres y solo espacios; replay idéntico sin escritura; `request_id_reused` con datos distintos; campos inmutables intactos |
| Escalado | `tests/integration/test_ticket_escalation.py` | Selección determinista; preferencia de equipo; nivel máximo `especialista`; `no_higher_level`; `no_technicians_available`; nivel no superior; el payload no acepta `assignee_id`; replay sin duplicados; `to > from` en la entrada |
| Permisos | `tests/integration/test_assignee_change_permissions.py` | Solo el técnico asignado vigente ejecuta y consulta opciones; roles no técnicos reciben `403 forbidden`; creador técnico no asignado recibe `forbidden` con precedencia sobre `not_ticket_assignee`; el creador asignado puede operar; técnico no asignado o anterior no creador `403 not_ticket_assignee`; el anterior conserva la lectura pública y pierde `can_view_internal`, `can_change_status`, `can_comment_internally`, `can_reassign` y `can_escalate`; `abierto`, `en_progreso` y `pendiente_usuario` permitidos; `resuelto`/`cerrado` `409 ticket_finalized`; sin token `401`; inexistente `404`; replay idéntico `200 changed=false` sin escribir |
| Concurrencia | `tests/integration/test_assignee_change_concurrency.py` | Dos comandos simultáneos: uno escribe y el otro recibe `409 stale_ticket`; bloqueo de fila efectivo; sin entradas ni notificaciones duplicadas; replay idéntico tras perder la asignación devuelve `200 changed=false` |
| Atomicidad | `tests/integration/test_ticket_reassignment.py` y `test_ticket_escalation.py` | Fallo simulado al insertar la notificación ⇒ rollback total: ni cambio de `assignee_id`, ni entrada, ni notificación; respuesta `500 internal_error` |
| Notificaciones | `tests/integration/test_notifications.py` | Una notificación por cambio (`UNIQUE (timeline_entry_id)`); snapshots de número, título y responsable anterior; bandeja ordenada; `unread_count` global y no solo de la página; paginación; lectura idempotente; notificación ajena `404`; el motivo no se duplica en la notificación |
| Notificación (unidad) | `tests/unit/test_assignee_change_notification.py` | Snapshots de número, título y responsable anterior; destinatario = nuevo responsable; `timeline_entry_id` único; sin motivo; la función añade a la sesión sin `commit()` ni escritura autónoma |
| Inmutabilidad | `tests/integration/test_assignee_change_immutability.py` | Los routers no exponen `PUT`/`PATCH`/`DELETE`; replays y rechazos no crean ni modifican timeline ni notificaciones; un cambio posterior no altera entradas previas |
| Contrato | `tests/contract/test_assignee_change_contract.py` | Recursos, DTOs, estados HTTP y códigos de error coinciden con `assignee-change.openapi.yaml`; normalización de payloads mal formados a `422 invalid_request`; campos nuevos de `workflow` y `timeline` son aditivos |
| Rendimiento | `tests/integration/test_assignee_change_performance.py` | p95 < 300 ms en opciones, reasignación, escalado y listado de la cola con el volumen de referencia (hasta 100 tickets activos por técnico) |

**Concurrencia real**: se ejecuta solo con `TEST_DATABASE_URL` apuntando a PostgreSQL (`pytest ... -k postgres`). En SQLite no se simula `FOR UPDATE`; la corrección funcional se cubre con `expected_updated_at` y las pruebas de carrera se reservan para PostgreSQL.

**Migración**: `alembic upgrade head`, `alembic downgrade -1` y `alembic upgrade head` sobre una base PostgreSQL limpia; se verifica el valor `assignee_change` del enum, las cinco columnas, los índices de `notifications`, `ix_users_role_active_level_team` y que los datos existentes de HU-04/HU-05 sobreviven.

### Frontend

| Área | Archivo | Casos mínimos |
|---|---|---|
| Selector de compañeros | `tests/components/AssigneeSelector.spec.ts` | Render de nombre, equipo y nivel; estado vacío; deshabilitado durante el envío; `v-model` y emisión de selección; accesibilidad con `fieldset`/`legend` |
| Selector de nivel | `tests/components/EscalationLevelSelector.spec.ts` | Solo niveles estrictamente superiores; niveles sin técnicos deshabilitados con texto; nunca envía un `assignee_id`; estado vacío cuando no hay nivel superior |
| Motivo | `tests/components/AssigneeChangeReasonForm.spec.ts` | Obligatorio tras `trim()`; contador 0–5.000; límite `maxlength`; error accesible con `aria-invalid`/`aria-describedby`; aviso de visibilidad pública |
| Panel orquestador | `tests/components/TicketAssigneeChangePanel.spec.ts` | Modos reasignar/escalar; carga de opciones; validación previa; envío; `request_id` estable por firma y regenerado al cambiarla o tras `request_id_reused`; conflicto `stale_ticket`; replay con `changed=false`; éxito refresca workflow y timeline; el panel desaparece si el actor deja de ser responsable |
| Panel de flujo | `tests/components/TicketWorkflowPanel.spec.ts` | No monta el panel de cambio de responsable sin `canReassign` ni `canEscalate`; lo monta si alguno es verdadero; tras perder la asignación recalcula capacidades, lo desmonta y muestra «Este ticket ya no está asignado a ti.» |
| Campana | `tests/components/NotificationBell.spec.ts` | Contador de no leídas; `aria-live`; apertura/cierre con teclado y `Escape`; foco gestionado; estados de carga, vacío y error |
| Cabecera | `tests/components/AppHeader.spec.ts` | Monta `NotificationBell` fuera de `RouterView`; no arranca el sondeo sin token y lo detiene al desmontar |
| Lista | `tests/components/NotificationList.spec.ts` | Distinción textual de no leídas; navegación al ticket; marcado de lectura idempotente y actualización del contador; notificación ajena no visible |
| Línea temporal | `tests/components/TicketTimeline.spec.ts` | Rama `assignee_change` con tipo, responsables, niveles y motivo en texto plano; sin interpretar HTML; orden cronológico |
| Stores | `tests/stores/ticketDetail.spec.ts`, `tests/stores/notifications.spec.ts` | Opciones y comandos; refresco encadenado de workflow, timeline y opciones; errores por código; sondeo de 15 s con temporizadores falsos; pausa con pestaña oculta y refresco al recuperar foco; `AbortController` descarta respuestas fuera de orden; `401` limpia la bandeja y detiene el sondeo; contador y marcado de lectura, con error de red visible |
| Latencia percibida | `tests/stores/ticketDetail.spec.ts`, `tests/unit/workQueue.store.spec.ts` | La entrada `assignee_change` aparece en la línea temporal en < 2 s percibidos tras confirmar (`HU06-SC-002`); la cola refleja el traspaso en la siguiente actualización de 60 s (`HU06-SC-005`); temporizadores falsos y `flushPromises` |
| Accesibilidad | `tests/components/WorkQueueAccessibility.spec.ts` como referencia | `axe-core` sin violaciones en panel, selectores, motivo y campana; foco visible; navegación completa por teclado |
| Tipos y build | `npm run build` | Los DTOs ampliados de `workflow` y `timeline` compilan sin `any` ni cambios incompatibles |

### Puertas de calidad

1. `python -m pytest` en verde, incluidas las suites existentes de HU-04 y HU-05 (sin regresiones).
2. `npm run test` y `npm run build` en verde.
3. Migración probada en PostgreSQL en ambos sentidos antes de fusionar.
4. `quickstart.md` completo: reasignación, escalado, cola de origen/destino, notificación, replay, conflicto, permisos y snapshot de campos inmutables.
5. Revisión de contrato: ningún endpoint `PUT`, `PATCH` o `DELETE` nuevo; solo `GET` y `POST`.

**Fuera de alcance de las pruebas**: SSE, WebSocket, correo y push (no existen en el diseño); triggers de inmutabilidad (no se añaden); pruebas de carga más allá del volumen de referencia.

## Riesgos y mitigaciones

| Riesgo | Impacto | Mitigación | Detección |
|---|---|---|---|
| Dos comandos concurrentes pisan el responsable | Pérdida de una acción o historial incoherente | Bloqueo de fila + `expected_updated_at` + transacción única; el segundo recibe `409 stale_ticket` | Prueba de concurrencia PostgreSQL |
| Doble clic o reintento de red duplica entradas/notificaciones | Historial y bandeja contaminados | `request_id` + `UNIQUE (ticket_id, request_id, event_type)` + `UNIQUE (timeline_entry_id)`; replay devuelve `changed=false` | Pruebas de idempotencia y conteo de filas |
| Selección de escalado no determinista | El mismo estado produce responsables distintos | Orden explícito por mismo equipo, carga, `lower(name)` e `id`; sin `ORDER BY` implícito | Pruebas unitarias con orden de entrada barajado |
| Nivel destino sin técnicos activos | Ticket bloqueado o cambio parcial | `409 no_technicians_available` antes de escribir; el selector deshabilita el nivel | Prueba de integración y estado vacío en UI |
| Notificación perdida o duplicada | El nuevo responsable no se entera o recibe ruido | Inserción en la misma transacción + unicidad; el sondeo relee del servidor y el contador se calcula en servidor | Pruebas de atomicidad, bandeja y conteo |
| Latencia percibida de la notificación | Incumplir el plazo de 30 s | Sondeo cada 15 s, pausado con pestaña oculta y refresco inmediato al recuperar foco | Prueba de store con temporizadores falsos y quickstart |
| Futuro código muta o borra la línea temporal | Se rompe la trazabilidad append-only | Sin rutas de mutación, inserción solo en servicio, restricciones y revisión de contrato; trigger de motor valorado en migración separada si una auditoría lo exige | Pruebas de contrato y revisión de código |
| `downgrade()` destructivo de HU-06 | Pérdida de cambios y notificaciones | Copia de seguridad obligatoria; `downgrade()` documentado y probado en PostgreSQL antes de fusionar | Prueba de migración descendente |
| Divergencia SQLite/PostgreSQL | Pruebas verdes que fallan en producción | Funcionales en SQLite; concurrencia, enums y migraciones en PostgreSQL | CI con ambos motores |
| Consulta de candidatos lenta con muchos usuarios | p95 > 300 ms | Índice `ix_users_role_active_level_team`; filtros por rol, actividad, nivel y equipo; límite de resultados | Prueba de rendimiento |
| El motivo se filtra a logs o a la notificación | Exposición de información sensible | El motivo solo vive en la línea temporal; no se registra en logs ni se copia a `notifications`; la UI avisa de su visibilidad pública | Revisión de logs y pruebas de DTOs |
| Regresión en HU-04/HU-05 | Cola, workflow o timeline existentes se rompen | Cambios aditivos, campos opcionales y suites existentes en la puerta de calidad | `pytest` completo y `npm run test` |
| Zona horaria incoherente en fechas | Orden o caducidad incorrectos | Almacenamiento UTC y presentación `Europe/Madrid` con los helpers existentes | Pruebas de serialización y quickstart |

## Complexity Tracking

> No hay violaciones de la Constitución ni del stack. No se rellena.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |

## Phase 2 Preview (not created by this command)

`/speckit.tasks` derivará tareas de:

1. Migración `0004`: enums, `users.escalation_level`, columnas de timeline, `notifications`, índices y `downgrade()`.
2. Modelos y enums: `Notification`, relaciones de timeline y exports.
3. Catálogo de niveles y helpers puros de selección/candidatos.
4. Servicio `assignee_change.py`: opciones, reasignación, escalado, idempotencia y transacción.
5. Servicio `notifications.py`: bandeja, contador y marcado de lectura.
6. Ampliación de `ticket_workflow.py` y `ticket_timeline.py` (helpers públicos, capacidades y serialización).
7. Esquemas Pydantic y endpoints de tickets/notificaciones; router.
8. Seed con niveles y escenarios de creador técnico.
9. Pruebas unitarias, de integración, concurrencia PostgreSQL, rendimiento y contrato.
10. Tipos, servicios y stores del frontend.
11. Componentes `TicketAssigneeChangePanel`, selectores, motivo, campana y timeline.
12. Pruebas de componentes, accesibilidad y quickstart end-to-end.
