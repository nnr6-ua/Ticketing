# Data Model: Responder a la petición de información del técnico (HU-03)

**Feature**: `003-responder-peticion-tecnico` | **Date**: 2026-11-13

Este documento describe el modelo persistente y las proyecciones de lectura de HU-03. Se apoya en el modelo existente de `master` (HU-01/02/04/05) y no duplica entidades.

## 1. Resumen del modelo

| Concepto | Persistencia | Descripción |
|---|---|---|
| Ticket | `tickets` (sin cambios) | Estado actual, creador y técnico asignado |
| Entrada de línea temporal | `ticket_timeline_entries` (ampliada) | Fuente única de peticiones, respuestas y cambios de estado |
| Petición de información | Fila con `event_type = information_request` | Mensaje concreto del técnico; pública |
| Respuesta del usuario | Fila con `event_type = user_response` | Texto del creador; pública; puede apuntar a una petición |
| Petición activa | Derivada | Petición sin respuesta que la referencie |
| Recordatorio 48 h | Derivado | `pending_since + 48 h` comparado con la hora del servidor |

No se crean tablas nuevas. No se añaden columnas a `tickets`.

## 2. Cambios en `ticket_timeline_entries`

### 2.1. Enum `timeline_event_type`

Valores existentes:

- `created`
- `status_change`
- `resolution`
- `internal_comment`

Valores nuevos:

- `information_request`: petición de información del técnico.
- `user_response`: respuesta del usuario creador.

### 2.2. Nueva columna `reply_to_id`

| Atributo | Valor |
|---|---|
| Tipo | `Uuid` |
| Nulabilidad | Sí |
| FK | `ticket_timeline_entries.id` |
| `ondelete` | `SET NULL` |
| Índice | `ix_timeline_reply_to` |
| Uso | Solo en `user_response`; apunta a la `information_request` respondida |

### 2.3. Modelo resultante (resumen)

```python
class TicketTimelineEntry(Base):
    __tablename__ = "ticket_timeline_entries"

    id: UUID
    ticket_id: UUID              # FK tickets.id, ondelete CASCADE
    event_type: TimelineEventType
    from_status: TicketStatus | None
    to_status: TicketStatus | None
    body: str | None
    is_internal: bool
    author_id: UUID              # FK users.id
    created_at: datetime
    event_order: int             # 0 o 1
    request_id: UUID
    reply_to_id: UUID | None     # NUEVO: FK ticket_timeline_entries.id
```

### 2.4. Restricciones

Existentes que se conservan:

- `ck_timeline_status_change`: `status_change` exige `from_status`, `to_status`, `from_status <> to_status`, `body IS NULL` e `is_internal = false`.
- `ck_timeline_resolution`: `resolution` exige `to_status = 'resuelto'`, `body` e `is_internal = false`.
- `ck_timeline_internal_comment`: comentario interno exige `body`, `is_internal = true` y estados nulos.
- `ck_timeline_body_length`: `body` entre 1 y 5.000 caracteres.
- `ck_timeline_event_order`: `0` o `1`.
- `uq_timeline_request_event`: único `(ticket_id, request_id, event_type)`.

Nuevas:

| Nombre | Expresión | Propósito |
|---|---|---|
| `ck_timeline_information_request` | `(event_type <> 'information_request') OR (from_status IS NULL AND to_status IS NULL AND body IS NOT NULL AND is_internal = false AND reply_to_id IS NULL)` | Forma de una petición |
| `ck_timeline_user_response` | `(event_type <> 'user_response') OR (from_status IS NULL AND to_status IS NULL AND body IS NOT NULL AND is_internal = false)` | Forma de una respuesta |

La obligatoriedad de `reply_to_id` en respuestas nuevas se valida en servicio porque los tickets legados pueden responder sin petición previa (HU03-RF-020). La respuesta legada se registra con `reply_to_id = NULL`; el `CHECK` no la rechaza.

### 2.5. Índices

| Índice | Columnas | Uso |
|---|---|---|
| `ix_timeline_ticket_created` | `(ticket_id, created_at)` | Cronología y paginación existentes |
| `ix_timeline_ticket_internal` | `(ticket_id, is_internal)` | Filtro de visibilidad existente |
| `ix_timeline_author` | `(author_id)` | Historial por autor existente |
| `ix_timeline_reply_to` | `(reply_to_id)` | NUEVO: localizar la respuesta de una petición |

## 3. Forma de cada entrada

### 3.1. `information_request`

| Campo | Valor |
|---|---|
| `event_type` | `information_request` |
| `from_status` | `NULL` |
| `to_status` | `NULL` |
| `body` | Mensaje del técnico, normalizado con `strip()`, 1–5.000 caracteres |
| `is_internal` | `false` |
| `author_id` | Técnico asignado |
| `created_at` | Instante del comando |
| `event_order` | `1` |
| `request_id` | Identificador de idempotencia del comando |
| `reply_to_id` | `NULL` |

La petición va precedida por una entrada `status_change` con el mismo `request_id`, `from_status = en_progreso`, `to_status = pendiente_usuario` y `event_order = 0`.

### 3.2. `user_response`

| Campo | Valor |
|---|---|
| `event_type` | `user_response` |
| `from_status` | `NULL` |
| `to_status` | `NULL` |
| `body` | Respuesta del creador, normalizada con `strip()`, 1–5.000 caracteres |
| `is_internal` | `false` |
| `author_id` | Creador del ticket |
| `created_at` | Instante del comando |
| `event_order` | `1` |
| `request_id` | Identificador de idempotencia del comando |
| `reply_to_id` | `id` de la petición activa, o `NULL` si el ticket legado no tenía petición |

La respuesta va precedida por una entrada `status_change` con el mismo `request_id`, `from_status = pendiente_usuario`, `to_status = en_progreso` y `event_order = 0`.

## 4. Petición activa (derivada)

Una petición está activa si se cumplen las tres condiciones:

1. El ticket está en `pendiente_usuario`.
2. La petición pertenece al ciclo pendiente actual: su `created_at` es igual o posterior al último `status_change` con `to_status = pendiente_usuario` (desempate por `event_order`).
3. No existe ninguna fila `user_response` con `reply_to_id` igual a su `id`.

Reglas:

- Como máximo una petición activa por ticket.
- Solo puede crearse una petición nueva si el ticket está `en_progreso` y no hay otra activa.
- Al responder, la petición deja de estar activa y no se vuelve a mostrar como pendiente.
- Si hay varias peticiones históricas, la activa es la más reciente del ciclo pendiente actual.
- Si el técnico usa la transición genérica de HU-05 para sacar el ticket de «Pendiente de usuario» sin respuesta, la petición deja de estar activa sin crear una respuesta ficticia; queda como petición histórica sin responder.
- Si el ticket vuelve a «Pendiente de usuario» con una transición genérica posterior, las peticiones anteriores no se reactivan.

## 5. Recordatorio de 48 horas (derivado)

```
pending_since   = created_at del último status_change con to_status = pendiente_usuario
reminder_due_at = pending_since + 48 horas naturales
reminder_active = ticket.status == pendiente_usuario AND now >= reminder_due_at
```

Detalles:

- `now` es la hora del servidor en UTC.
- El cálculo no se persiste ni se cachea.
- Si el ticket sale de `pendiente_usuario`, el recordatorio deja de estar activo.
- Si vuelve a entrar, se usa el nuevo `pending_since`.
- El recordatorio también se calcula para tickets legados pendientes sin petición.
- Si no existe ningún `status_change` a «Pendiente de usuario» (ticket legado sin línea temporal), `pending_since` es `null` y el recordatorio no se activa.
- Se devuelve `reminder_due_at` para que la UI pueda mostrar la fecha, pero la decisión `reminder_active` es del servidor.
- Es un estado contextual, no un envío repetido: se activa una sola vez al cruzar las 48 h y permanece visible hasta que el usuario responde o el ticket sale de «Pendiente de usuario». No hay recordatorios posteriores ni escalado.

## 6. Transiciones y efectos

| Comando | Estado origen | Estado destino | Entradas creadas | Efectos en `tickets` |
|---|---|---|---|---|
| Solicitar información | `en_progreso` | `pendiente_usuario` | `status_change` (orden 0) + `information_request` (orden 1) | `status`, `updated_at`; limpia `finalized_at` y `closed_at` |
| Responder | `pendiente_usuario` | `en_progreso` | `status_change` (orden 0) + `user_response` (orden 1) | `status`, `updated_at`; limpia `finalized_at` y `closed_at` |
| Transición genérica HU-05 | `pendiente_usuario` | `en_progreso` | `status_change` | Sin cambios adicionales; sigue permitida |

La matriz de estados no se modifica. `apply_user_response_transition` sigue siendo la referencia para la transición automática.

## 7. Reglas de validación

### 7.1. Solicitud de información

| Regla | Error |
|---|---|
| Ticket existe y el actor puede leerlo | `404 ticket_not_found` |
| Actor sin rol `tecnico` | `403 forbidden` |
| Actor es el asignado | `403 not_ticket_assignee` |
| `body.strip()` no vacío | `422 information_request_required` |
| `len(body.strip()) <= 5000` | `422 information_request_too_long` |
| `request_id` no reutilizado | `409 request_id_reused` |
| No hay petición activa en el ciclo pendiente | `409 information_request_already_open` |
| Estado `en_progreso` | `409 invalid_transition` |
| `expected_updated_at` coincide | `409 stale_ticket` |
| Payload válido | `422 invalid_request` |

La precedencia es: idempotencia → petición activa → estado → `expected_updated_at`. La idempotencia se comprueba antes del estado para que un reintento tras el éxito devuelva `200 changed = false` aunque el ticket ya esté «Pendiente de usuario». La petición activa se comprueba antes que el estado para que `information_request_already_open` sea alcanzable cuando el ticket ya está pendiente.

### 7.2. Respuesta del usuario

| Regla | Error |
|---|---|
| Ticket existe y el actor puede leerlo | `404 ticket_not_found` |
| Actor no es el creador (si puede leerlo) | `403 forbidden` |
| `body.strip()` no vacío | `422 information_response_required` |
| `len(body.strip()) <= 5000` | `422 information_response_too_long` |
| `request_id` no reutilizado | `409 request_id_reused` |
| Estado `pendiente_usuario` | `409 invalid_transition` |
| `expected_updated_at` coincide | `409 stale_ticket` |
| Payload válido | `422 invalid_request` |

Un usuario que no puede leer el ticket recibe `404` y no se le revela su existencia. La idempotencia se comprueba antes del estado para que un reintento tras el éxito devuelva `200 changed = false` aunque el ticket ya esté «En progreso».

### 7.3. Normalización

- Se aplica `strip()` al cuerpo antes de validar y guardar.
- El cuerpo normalizado es el que se devuelve y se compara en la idempotencia.
- Los cuerpos vacíos o compuestos solo por espacios se rechazan.
- No se permiten adjuntos, HTML enriquecido ni formato especial; el texto se muestra con `white-space: pre-wrap`.

## 8. Proyecciones de lectura

### 8.1. `GET /api/v1/tickets/{id}/workflow`

```jsonc
{
  "ticket": { "...": "sin cambios" },
  "can_change_status": true,
  "can_comment_internally": true,
  "can_view_internal": true,
  "can_request_information": true,
  "can_respond_to_information": false,
  "awaiting_user_response": false,
  "active_information_request": {
    "id": "uuid",
    "body": "¿Qué versión del navegador usas?",
    "requested_at": "2026-11-13T10:00:00Z",
    "requested_by": {
      "id": "uuid",
      "name": "Técnico",
      "role": "tecnico"
    }
  },
  "reminder_active": false,
  "reminder_due_at": null
}
```

Definiciones:

| Campo | Tipo | Descripción |
|---|---|---|
| `can_request_information` | bool | Técnico asignado + estado `en_progreso` + sin petición activa |
| `can_respond_to_information` | bool | Creador + estado `pendiente_usuario` |
| `awaiting_user_response` | bool | Ticket en `pendiente_usuario` (estado del ticket) |
| `active_information_request` | objeto o `null` | Petición sin respuesta |
| `reminder_active` | bool | Han pasado 48 h desde el último paso a pendiente |
| `reminder_due_at` | datetime o `null` | `pending_since + 48 h` |

### 8.2. `GET /api/v1/me/tickets`

Cada `MyTicketSummary` añade:

| Campo | Tipo | Descripción |
|---|---|---|
| `awaiting_user_response` | bool | Ticket en `pendiente_usuario` |
| `response_requested_at` | datetime o `null` | `created_at` de la petición activa |
| `reminder_active` | bool | Recordatorio de 48 h activo |
| `reminder_due_at` | datetime o `null` | Fecha límite del recordatorio |

La lista no incluye el cuerpo de la petición para mantener el resumen ligero; el detalle se obtiene al abrir el ticket.

### 8.3. `GET /api/v1/tickets/{id}/timeline`

Cada `TimelineEntry` añade `reply_to_id`. Las entradas nuevas son públicas y aparecen en la cronología normal con su autor y fecha.

## 9. Migración `0005_ticket_information`

**Down revision**: `0004_ticket_creation`

**Upgrade**:

1. Añadir valores al enum `timeline_event_type` (PostgreSQL) dentro de `with op.get_context().autocommit_block():`. El bloque confirma los valores antes de usarlos en los `CHECK`, porque PostgreSQL no permite usar un valor de enum nuevo en la misma transacción en la que se añade.
2. Añadir columna `reply_to_id` con FK autorreferente `ON DELETE SET NULL`.
3. Añadir los dos `CHECK` nuevos.
4. Crear el índice `ix_timeline_reply_to`.

**Downgrade**:

1. Eliminar el índice.
2. Eliminar los `CHECK` nuevos.
3. Eliminar la columna `reply_to_id`.
4. Conservar los valores del enum: PostgreSQL no permite quitar un valor sin recrear el tipo y conservarlos no rompe datos históricos. Se documenta como limitación conocida.

**Compatibilidad**:

- No se modifican `tickets` ni filas existentes.
- Los `CHECK` nuevos solo aplican a los tipos nuevos.
- SQLite reconstruye el esquema desde los modelos en las pruebas; no ejecuta el `ALTER TYPE`.
- La migración debe ejecutarse con el backend actualizado y sin tráfico de escritura, como el resto de migraciones.

## 10. Invariantes

1. Toda petición y toda respuesta pertenecen a un ticket existente.
2. El autor de una petición es el técnico asignado en el momento del comando.
3. El autor de una respuesta es el creador del ticket.
4. Petición y respuesta son públicas (`is_internal = false`).
5. Una respuesta nueva apunta a la petición activa del mismo ticket; una respuesta legada puede no apuntar a ninguna.
6. No puede haber dos peticiones activas en el mismo ticket.
7. El cambio de estado y la entrada de información se escriben en la misma transacción.
8. Las entradas son inmutables: no hay endpoints de edición ni borrado.
9. La línea temporal mantiene el orden `created_at ASC, event_order ASC, id ASC`.
10. El recordatorio no altera el estado del ticket ni crea entradas.
