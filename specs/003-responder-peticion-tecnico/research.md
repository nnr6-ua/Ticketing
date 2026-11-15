# Research: Responder a la petición de información del técnico (HU-03)

**Feature**: `003-responder-peticion-tecnico` | **Date**: 2026-11-13

Este documento resuelve las decisiones técnicas de HU-03. Todas ellas respetan la especificación [spec.md](./spec.md) y la constitución del proyecto. Las decisiones marcadas como «decidida» son las que se trasladan a [plan.md](./plan.md), [data-model.md](./data-model.md) y [contracts/](./contracts/).

## Contexto de partida

La implementación existente en `master` ya ofrece:

- Línea temporal append-only (`ticket_timeline_entries`) con `event_type`, `body`, `author_id`, `is_internal`, `created_at`, `event_order` y `request_id`.
- Máquina de estados con `en_progreso → pendiente_usuario` y `pendiente_usuario → en_progreso`.
- `apply_user_response_transition`, que aplica la vuelta a «En progreso» de forma idempotente y con bloqueo, pero sin endpoint público ni texto de respuesta.
- Visibilidad de la línea temporal filtrada en servidor (`is_internal`).
- Vista del ticket (`TicketWorkflowPanel`, `TicketTimeline`) y lista «Mis tickets».

La rama actual (`hu-03-responder-tecnico`) parte del commit inicial y no contiene esas fuentes. Antes de implementar hay que integrar `master`; este plan asume la base de HU-01/02/04/05.

## R1 — ¿Tabla nueva o línea temporal existente?

**Decidida**: usar `ticket_timeline_entries` con dos tipos nuevos, `information_request` y `user_response`.

**Razonamiento**:

- La spec exige que petición y respuesta aparezcan como entradas cronológicas independientes (Q3), con autor, fecha y tipo.
- La línea temporal ya es la fuente única de trazabilidad, ya tiene visibilidad pública/interna y ya está indexada por ticket y fecha.
- Una tabla nueva obligaría a duplicar autoría, orden, visibilidad, paginación y borrado en cascada.

**Alternativas descartadas**:

- Tabla `ticket_information_requests` con estados propios: más piezas, más migraciones y dos fuentes de verdad para la misma cronología.
- Columnas en `tickets` (`pending_question`, `pending_response`): rompe el histórico de ciclos sucesivos y mezcla estado actual con auditoría.

## R2 — ¿Cómo se vincula una respuesta con su petición?

**Decidida**: columna autorreferente `reply_to_id` en `ticket_timeline_entries`, nullable, con FK a `id` y `ondelete="SET NULL"`.

**Razonamiento**:

- Permite saber qué petición concreta responde una entrada, incluso si hay varios ciclos.
- La respuesta sigue siendo una entrada independiente en la línea temporal (no se agrupa ni se cita visualmente).
- `SET NULL` evita problemas de orden cuando se elimina un ticket y su línea temporal en cascada.

**Alternativas descartadas**:

- Emparejar por proximidad temporal: frágil ante comentarios internos o reintentos.
- Guardar el `request_id` de la petición en la respuesta: mezcla idempotencia con relación funcional y no impide respuestas huérfanas.
- Subdocumento JSON con petición y respuesta: rompe el modelo append-only y complica la paginación.

**Invariante**: una `user_response` solo puede apuntar a una `information_request` del mismo `ticket_id`. Se valida en servicio porque un `CHECK` no puede comparar filas.

## R3 — ¿Cómo se calcula el recordatorio de 48 horas?

**Decidida**: cálculo derivado en servidor, sin persistencia.

- `pending_since` = `created_at` del último `status_change` con `to_status = pendiente_usuario`.
- `reminder_due_at` = `pending_since + 48 h`.
- `reminder_active` = ticket en `pendiente_usuario` y `now >= reminder_due_at`.

**Razonamiento**:

- La spec pide un único recordatorio contextual, sin envíos periódicos ni escalado (Q4). Se interpreta como un estado que se activa al cruzar las 48 h y permanece visible hasta la respuesta; no hay una secuencia de avisos ni historial de lectura (fuera de alcance).
- Al no persistir «recordatorio enviado» no hay migración de estado de aviso ni trabajos programados.
- El cálculo es determinista, se puede probar y no depende del reloj del navegador.

**Alternativas descartadas**:

- Columna `reminder_sent_at` en `tickets`: añade estado que nadie más usa y obliga a decidir cuándo «se envía».
- Tarea programada/correo: fuera de alcance y añade infraestructura.
- Cálculo en frontend: expuesto a relojes incorrectos y duplicado en lista y detalle.

## R4 — ¿Cómo se garantiza idempotencia y concurrencia?

**Decidida**: reutilizar el patrón de HU-05: `request_id` + `expected_updated_at` + `SELECT ... FOR UPDATE` sobre la fila del ticket.

**Razonamiento**:

- `request_id` ya forma parte de la línea temporal y tiene una restricción única por `(ticket_id, request_id, event_type)`.
- Un doble clic o dos pestañas no deben crear dos peticiones ni dos respuestas.
- `expected_updated_at` detecta ediciones concurrentes y devuelve un `409 stale_ticket` comprensible.

**Reglas de clasificación**:

- Replay idéntico (mismo actor, mismo tipo, mismo cuerpo y mismo destino) ⇒ `changed = false`, sin escrituras.
- `request_id` ya usado con otros datos o para otro comando ⇒ `409 request_id_reused`.
- Estado inesperado o versión desactualizada ⇒ `409 invalid_transition` o `409 stale_ticket`.

**Alternativas descartadas**:

- Solo `request_id`: no detecta dos pestañas con identificadores distintos.
- Solo `updated_at`: un doble envío secuencial pasaría como nueva respuesta.
- Bloqueo optimista del cliente sin bloqueo de fila: dos respuestas simultáneas podrían insertar dos entradas.

## R5 — ¿Quién puede solicitar y quién puede responder?

**Decidida**:

- Solicitar: solo el técnico asignado, con rol `tecnico`, sobre un ticket `en_progreso`.
- Responder: solo el creador del ticket, sobre un ticket `pendiente_usuario`.

**Razonamiento**:

- Coherente con HU-05: el técnico asignado es el único escritor operativo.
- La respuesta es del usuario que pidió ayuda; ni supervisores ni administradores deben suplantarlo.
- El servidor decide; la UI solo muestra u oculta acciones.

**Alternativas descartadas**:

- Cualquier técnico puede solicitar: rompe la asignación y la cola de trabajo.
- Supervisor/admin pueden responder: no representan la información solicitada al usuario.
- Confiar solo en la UI: inseguro.

**Privacidad**: las entradas nuevas son públicas (`is_internal = false`). La petición se muestra al creador y al personal operativo; los comentarios internos siguen filtrándose en SQL.

## R6 — ¿Qué pasa con tickets «Pendiente de usuario» antiguos sin petición?

**Decidida**: se pueden responder; la UI muestra un aviso genérico y la respuesta se registra sin `reply_to_id`.

**Razonamiento**:

- La transición genérica de HU-05 sigue siendo válida (Q1 de la spec).
- Impedir la respuesta dejaría tickets bloqueados en un estado sin salida para el usuario.
- La ausencia de petición no debe romper la línea temporal ni el contrato.

**Alternativas descartadas**:

- Exigir siempre una petición previa: rompe tickets existentes.
- Crear una petición ficticia retroactiva: inventa datos y autores.

## R7 — ¿Dónde vive la UI de solicitud y respuesta?

**Decidida**:

- La solicitud se escribe en el panel de cambio de estado existente; al elegir «Pendiente de usuario» se despliega el campo.
- La respuesta se muestra en el mismo panel cuando el visitante es el creador y el ticket está pendiente.
- La lista «Mis tickets» solo añade un badge y el recordatorio contextual.

**Razonamiento**:

- La spec pide coherencia estética y funcional y evitar pantallas nuevas (Q5).
- El panel ya concentra el cambio de estado, la resolución y los comentarios internos.
- No se añaden rutas ni un centro de notificaciones (Q1/Q2).

**Alternativas descartadas**:

- Modal o pantalla independiente: más fricción y divergencia visual.
- Campana global: fuera de alcance.
- Formulario en la línea temporal: mezcla lectura y escritura y rompe el patrón actual.

## R8 — ¿Cómo se ordenan las entradas del mismo comando?

**Decidida**: `event_order = 0` para el `status_change` y `event_order = 1` para la petición o la respuesta creadas en el mismo instante.

**Razonamiento**:

- El orden existente es `created_at ASC, event_order ASC, id ASC`.
- Así el usuario ve primero el cambio de estado y después la información asociada.
- No se necesita una precisión de reloj mayor ni un contador global.

**Alternativas descartadas**:

- Todo con `event_order = 0` y confiar en `id`: UUID aleatorios, orden no determinista.
- `created_at` con microsegundos distintos: depende del reloj y de la base.

## R9 — Estrategia de migración y compatibilidad de motores

**Decidida**: migración `0005_ticket_information`, aditiva:

1. `ALTER TYPE timeline_event_type ADD VALUE` para `information_request` y `user_response` en PostgreSQL, dentro de `with op.get_context().autocommit_block():`. El bloque confirma los valores antes de crear los `CHECK` que los usan, porque PostgreSQL no permite usar un valor de enum nuevo en la misma transacción en la que se añade.
2. `reply_to_id` nullable con FK autorreferente.
3. Nuevos `CHECK` para petición y respuesta.
4. Índice `ix_timeline_reply_to`.

Las pruebas usan SQLite y construyen el esquema desde los modelos (`Base.metadata.create_all`), por lo que no ejecutan el `ALTER TYPE` de PostgreSQL.

**Razonamiento**:

- No se toca `tickets` ni los datos existentes.
- Los `CHECK` nuevos no afectan a filas previas porque solo se aplican a los tipos nuevos.
- El `downgrade` elimina índice, restricciones y columna. Los valores añadidos al enum se conservan: PostgreSQL no permite eliminar un valor de un enum sin recrear el tipo, y conservarlos es inocuo para los datos históricos.

**Alternativas descartadas**:

- Recrear la tabla: costoso y arriesgado.
- Recrear el enum en `upgrade`: bloquea y complica la migración.
- Guardar petición/respuesta en JSON: pierde validación e indexación.

## R10 — Estrategia de pruebas

**Decidida**:

- Unitarias: validación de cuerpo y cálculo de recordatorio, sin base de datos.
- Integración: comandos completos, autorización, compatibilidad, visibilidad, recordatorio y concurrencia (PostgreSQL cuando esté disponible; SQLite para el resto).
- Contrato: forma de las respuestas y catálogo de errores.
- Frontend: formularios, panel, línea temporal, lista y store con Vitest.

**Razonamiento**:

- La lógica sensible (transacción, idempotencia, autorización) debe probarse contra la base real.
- Los componentes se prueban por comportamiento visible y accesibilidad, no por detalles internos.
- El flujo manual de `quickstart.md` cubre la validación por una persona no técnica.

## Referencias internas

- `.specify/memory/constitution.md` (constitución ratificada)
- `CONSTITUTION.md` (resumen de producto)
- `specs/003-responder-peticion-tecnico/spec.md`
- `specs/005-cambio-estado-resolucion/{plan.md,data-model.md,contracts/ticket-workflow.openapi.yaml}`
- `specs/002-ticket-timeline-history/{spec.md,data-model.md}`
- `backend/app/models/timeline.py`, `backend/app/models/enums.py`
- `backend/app/services/ticket_workflow.py`, `backend/app/services/ticket_timeline.py`
- `backend/app/api/v1/tickets.py`, `backend/app/api/v1/my_tickets.py`
- `frontend/src/components/tickets/TicketWorkflowPanel.vue`, `TicketTimeline.vue`
- `frontend/src/views/MyTicketsPage.vue`
