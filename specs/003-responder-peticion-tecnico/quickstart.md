# Quickstart — Validación de HU-03

**Feature**: `003-responder-peticion-tecnico` | **Date**: 2026-11-13

Guía ejecutable para demostrar de extremo a extremo que el técnico puede pedir información, el usuario creador puede responder y el ticket vuelve a «En progreso» sin romper el flujo existente. No contiene implementación; solo pasos de validación.

**Contratos de referencia**: [`contracts/ticket-information.openapi.yaml`](./contracts/ticket-information.openapi.yaml) y [`contracts/frontend-components.md`](./contracts/frontend-components.md).

---

## 1. Prerrequisitos

- `master` integrado en la rama de trabajo (HU-01, HU-02, HU-04 y HU-05).
- Python 3.12 con `backend/.venv` provisionado.
- PostgreSQL accesible en `DATABASE_URL` (por defecto `postgresql+psycopg://ticketing:ticketing@localhost:5432/ticketing`).
- Node.js y `frontend/node_modules` instalados.
- Variables del backend:
  - `DATABASE_URL`
  - `JWT_SECRET`
  - `AUTH_DEV_STUB_ENABLED=true` (solo desarrollo local)
  - `AUTH_ISSUER`, `AUTH_AUDIENCE`
- Seed con:
  - técnico `tecnico.a@example.com` (rol `tecnico`);
  - creador `usuario.b@example.com` (rol `usuario`);
  - supervisor `supervisor@example.com` (rol `supervisor`);
  - un ticket asignado al técnico, creado por el usuario, en estado `abierto`.

---

## 2. Preparar la base de datos

```bash
cd backend
python -m alembic upgrade head
python -m alembic current
```

**Esperado**:

- `alembic current` muestra `0005_ticket_information (head)`.
- `tickets` conserva sus columnas.
- `ticket_timeline_entries` incluye `reply_to_id` y el índice `ix_timeline_reply_to`.

Verificación en PostgreSQL:

```sql
\d ticket_timeline_entries
SELECT enum_range(NULL::timeline_event_type);
```

**Esperado**: el enum contiene `information_request` y `user_response`, además de los valores anteriores.

---

## 3. Pruebas automatizadas

### 3.1. Backend

```bash
cd backend
python -m pytest tests/unit/test_information_request_rules.py tests/unit/test_information_response_rules.py -q
python -m pytest tests/integration/test_information_requests.py -q
python -m pytest tests/integration/test_information_responses.py -q
python -m pytest tests/integration/test_information_reminder.py -q
python -m pytest tests/integration/test_information_cycle.py -q
python -m pytest tests/integration/test_information_visibility.py -q
python -m pytest tests/integration/test_information_concurrency.py -q
python -m pytest tests/contract/test_information_request_contract.py tests/contract/test_information_response_contract.py tests/contract/test_information_traceability_contract.py -q
```

**Esperado**:

| Suite | Resultado |
|---|---|
| Reglas | Cuerpos vacíos, límites, umbral de 48 h y replay |
| Peticiones | Éxito, autorización, estado, petición abierta con precedencia, idempotencia y atomicidad |
| Respuestas | Éxito, solo creador, ticket legado, idempotencia y vuelta a «En progreso» |
| Recordatorio | Activo a las 48 h, inactivo al responder o cerrar, sin repetición ni efectos laterales |
| Ciclo | Petición → respuesta → cola del técnico y trazabilidad completa |
| Visibilidad | Petición y respuesta públicas; comentarios internos ocultos |
| Concurrencia | Una sola respuesta gana; la otra recibe `stale_ticket` |
| Contrato | Campos, `reply_to_id`, inmutabilidad y códigos coinciden con el OpenAPI |

### 3.2. Frontend

```bash
cd frontend
npm run test -- --run
```

**Esperado**: pasan `InformationRequestForm`, `InformationResponseForm`, `TicketWorkflowPanel.information-*`, `TicketTimeline.information`, `MyTicketsPage`, `ticketDetail.request` y `ticketDetail.response`, además de las suites existentes.

### 3.3. Concurrencia real (PostgreSQL)

```bash
cd backend
python -m pytest tests/integration/test_information_concurrency.py -q -k "postgres"
```

**Esperado**:

- Dos respuestas simultáneas: solo una escribe.
- La otra recibe `409 stale_ticket`.
- No hay entradas duplicadas ni dos `status_change` a «En progreso».

### 3.4. Rendimiento

```bash
cd backend
python -m pytest tests/integration/test_ticket_workflow_performance.py -q
```

**Esperado**:

- p95 de solicitud y respuesta < 300 ms de servidor.
- `GET /workflow` y `GET /me/tickets` sin N+1 y con < 2 s percibidos en la vista.

---

## 4. Arrancar los servicios

```bash
# Terminal 1
cd backend
source .venv/bin/activate
python -m uvicorn app.main:app --reload --port 8000

# Terminal 2
cd frontend
npm run dev
```

- API: `http://localhost:8000`
- UI: `http://localhost:5173`
- OpenAPI interactivo: `http://localhost:8000/docs`

---

## 5. Validación HTTP (curl)

### 5.1. Obtener tokens

```bash
BASE=http://localhost:8000/api/v1

TECNICO=$(curl -s -X POST "$BASE/dev/login" \
  -H 'Content-Type: application/json' \
  -d '{"email":"tecnico.a@example.com"}' | jq -r .access_token)

CREADOR=$(curl -s -X POST "$BASE/dev/login" \
  -H 'Content-Type: application/json' \
  -d '{"email":"usuario.b@example.com"}' | jq -r .access_token)

SUPERVISOR=$(curl -s -X POST "$BASE/dev/login" \
  -H 'Content-Type: application/json' \
  -d '{"email":"supervisor@example.com"}' | jq -r .access_token)
```

> `jq` y `uuidgen` son opcionales; puedes copiar los valores manualmente.

### 5.2. Preparar el ticket en «En progreso»

```bash
TICKET_ID=<uuid-del-ticket>

EXPECTED=$(curl -s "$BASE/tickets/$TICKET_ID/workflow" \
  -H "Authorization: Bearer $TECNICO" | jq -r .ticket.updated_at)

curl -s -X POST "$BASE/tickets/$TICKET_ID/status-transitions" \
  -H "Authorization: Bearer $TECNICO" \
  -H 'Content-Type: application/json' \
  -d "{
    \"target_status\": \"en_progreso\",
    \"expected_updated_at\": \"$EXPECTED\",
    \"request_id\": \"$(uuidgen)\"
  }" | jq
```

**Esperado**: `ticket.status = "en_progreso"` y una entrada `status_change`.

### 5.3. El técnico solicita información

```bash
EXPECTED=$(curl -s "$BASE/tickets/$TICKET_ID/workflow" \
  -H "Authorization: Bearer $TECNICO" | jq -r .ticket.updated_at)

REQUEST_ID=$(uuidgen)

curl -s -X POST "$BASE/tickets/$TICKET_ID/information-requests" \
  -H "Authorization: Bearer $TECNICO" \
  -H 'Content-Type: application/json' \
  -d "{
    \"body\": \"¿Qué versión del navegador y sistema operativo usas?\",
    \"expected_updated_at\": \"$EXPECTED\",
    \"request_id\": \"$REQUEST_ID\"
  }" | jq
```

**Esperado**:

- `changed: true`
- `ticket.status: "pendiente_usuario"`
- Dos entradas en `timeline_entries`, en este orden:
  1. `status_change` de `en_progreso` a `pendiente_usuario`, `event_order = 0`.
  2. `information_request` con el texto, autor técnico y `event_order = 1`.
- `information_request.reply_to_id` no se expone; la respuesta lo usará internamente.

### 5.4. El usuario ve el aviso

```bash
curl -s "$BASE/me/tickets" \
  -H "Authorization: Bearer $CREADOR" | jq \
  '.items[] | select(.id == "'$TICKET_ID'") | {
    status,
    awaiting_user_response,
    response_requested_at,
    reminder_active,
    reminder_due_at
  }'
```

**Esperado**:

```json
{
  "status": "pendiente_usuario",
  "awaiting_user_response": true,
  "response_requested_at": "2026-11-13T10:00:00Z",
  "reminder_active": false,
  "reminder_due_at": "2026-11-15T10:00:00Z"
}
```

Abrir `http://localhost:5173/mis-tickets` y comprobar el badge «Esperando tu respuesta».

### 5.5. El usuario abre el ticket y responde

```bash
curl -s "$BASE/tickets/$TICKET_ID/workflow" \
  -H "Authorization: Bearer $CREADOR" | jq

EXPECTED=$(curl -s "$BASE/tickets/$TICKET_ID/workflow" \
  -H "Authorization: Bearer $CREADOR" | jq -r .ticket.updated_at)

RESPONSE_ID=$(uuidgen)

curl -s -X POST "$BASE/tickets/$TICKET_ID/information-responses" \
  -H "Authorization: Bearer $CREADOR" \
  -H 'Content-Type: application/json' \
  -d "{
    \"body\": \"Uso Chrome 131 en Windows 11.\",
    \"expected_updated_at\": \"$EXPECTED\",
    \"request_id\": \"$RESPONSE_ID\"
  }" | jq
```

**Esperado antes de responder**:

- `can_respond_to_information: true`
- `active_information_request.body` con la pregunta
- `awaiting_user_response: true`

**Esperado después de responder**:

- `changed: true`
- `ticket.status: "en_progreso"`
- Dos entradas nuevas:
  1. `status_change` de `pendiente_usuario` a `en_progreso`.
  2. `user_response` con el texto, autor creador y `reply_to_id` igual al `id` de la petición.
- `active_information_request: null`
- `can_respond_to_information: false`

### 5.6. Comprobar la cronología

```bash
curl -s "$BASE/tickets/$TICKET_ID/timeline" \
  -H "Authorization: Bearer $CREADOR" | jq \
  '.items[] | {type, from_status, to_status, author: .author.name, body, reply_to_id}'
```

**Esperado**:

- La petición y la respuesta aparecen como entradas independientes.
- La respuesta tiene `reply_to_id` apuntando a la petición.
- No aparece ningún comentario interno si el visor es el creador.

### 5.7. El ticket reaparece en la cola del técnico

```bash
curl -s "$BASE/tickets/$TICKET_ID/workflow" \
  -H "Authorization: Bearer $TECNICO" | jq \
  '{status: .ticket.status, can_request_information, active_information_request}'
```

**Esperado**: `status = "en_progreso"` y `can_request_information = true`.

---

## 6. Validación manual en la interfaz

1. Entrar como técnico y abrir el ticket.
2. Cambiar a «Pendiente de usuario»; comprobar que aparece el campo «Información que necesitas» y que «Guardar cambio» está deshabilitado hasta escribir.
3. Enviar la petición; comprobar el cambio de estado y las dos entradas en la línea temporal.
4. Entrar como creador en «Mis tickets»; comprobar el badge «Esperando tu respuesta».
5. Abrir el ticket; comprobar el aviso con la pregunta y el campo «Tu respuesta».
6. Enviar la respuesta; comprobar la vuelta a «En progreso» y las dos entradas nuevas.
7. Volver como técnico; comprobar que el ticket está en su cola y que la línea temporal muestra la respuesta.
8. Repetir con un ticket legado en «Pendiente de usuario» sin petición: debe mostrarse el aviso genérico y permitir responder.

**Comprobaciones visuales**:

- Sin campana, bandeja de notificaciones, correo ni pantalla nueva.
- La petición y la respuesta se ven con la misma estética que el resto de la línea temporal.
- Los avisos y el recordatorio son legibles en móvil y con teclado.
- Los textos están en español de España.

---

## 7. Simular el recordatorio de 48 horas

No hay que esperar dos días. Sobre un ticket recién puesto en «Pendiente de usuario»:

```sql
-- Localiza el último cambio a pendiente de usuario del ticket
SELECT id, created_at, to_status
FROM ticket_timeline_entries
WHERE ticket_id = '<TICKET_ID>'
  AND event_type = 'status_change'
  AND to_status = 'pendiente_usuario'
ORDER BY created_at DESC
LIMIT 1;

-- Retrasa 49 horas ese cambio para activar el recordatorio
UPDATE ticket_timeline_entries
SET created_at = now() - interval '49 hours'
WHERE id = '<STATUS_CHANGE_ENTRY_ID>';
```

Después:

```bash
curl -s "$BASE/tickets/$TICKET_ID/workflow" \
  -H "Authorization: Bearer $CREADOR" | jq \
  '{reminder_active, reminder_due_at, awaiting_user_response}'

curl -s "$BASE/me/tickets" \
  -H "Authorization: Bearer $CREADOR" | jq \
  '.items[] | select(.id == "'$TICKET_ID'") | {reminder_active, reminder_due_at}'
```

**Esperado**: `reminder_active: true` en ambos endpoints y el aviso visible en la UI. Repetir las consultas varias veces no crea entradas nuevas, no cambia el estado ni genera recordatorios adicionales. Al responder, el recordatorio desaparece porque el ticket deja de estar pendiente.

---

## 8. Casos de error que se deben comprobar

| Caso | Petición | Esperado |
|---|---|---|
| Petición vacía | `body: "   "` | `422 information_request_required` |
| Petición demasiado larga | 5.001 caracteres | `422 information_request_too_long` |
| Respuesta vacía | `body: ""` | `422 information_response_required` |
| Respuesta demasiado larga | 5.001 caracteres | `422 information_response_too_long` |
| Otro técnico solicita | Token de otro técnico | `403 not_ticket_assignee` |
| Usuario ajeno responde | Token de otro usuario | `404 ticket_not_found` (no revela el ticket) |
| Supervisor responde | Token de supervisor | `403 forbidden` |
| Ticket en estado incorrecto | Solicitar en `pendiente_usuario` | `409 invalid_transition` |
| Doble envío idéntico | Mismo `request_id` y cuerpo | `200 changed: false`, sin entradas nuevas |
| `request_id` reutilizado con otro cuerpo | Mismo `request_id`, otro texto | `409 request_id_reused` |
| Versión desactualizada | `expected_updated_at` antiguo | `409 stale_ticket` |
| Petición duplicada abierta | Dos peticiones sin responder | La segunda recibe `409 information_request_already_open` (antes que `invalid_transition`) |

---

## 9. Criterio de aceptación global

HU-03 se considera validada cuando:

1. El técnico asignado puede pedir información y el ticket pasa a «Pendiente de usuario».
2. El creador ve el aviso y responde desde el propio ticket.
3. El ticket vuelve a «En progreso» de forma atómica.
4. Petición y respuesta quedan en la línea temporal con autor, fecha y vínculo.
5. El recordatorio de 48 h aparece una sola vez, no crea entradas ni cambia el estado, y desaparece al responder.
6. Los tickets legados pendientes siguen siendo respondibles.
7. No se ha roto ninguna prueba de HU-01/02/04/05.
8. HU03-SC-008: un usuario no técnico completa petición y respuesta solo con la app, sin crear tickets ni comentarios externos.
