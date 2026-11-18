# Quickstart — Validación de HU-06

**Feature**: `006-reasignar-escalar-ticket` | **Date**: 2026-11-10

Guía ejecutable para demostrar de extremo a extremo que la reasignación, el escalado, la línea temporal append-only, la notificación en la aplicación y el traslado entre colas funcionan según la especificación. No contiene la implementación; solo pasos de validación.

**Contratos de referencia**: [`contracts/assignee-change.openapi.yaml`](./contracts/assignee-change.openapi.yaml) para la API HTTP y [`contracts/frontend-components.md`](./contracts/frontend-components.md) para los componentes Vue.

> Los bloques de shell están pensados para bash (WSL o Git Bash). En PowerShell, adapta las variables y usa `$env:NOMBRE="valor"` para el entorno.

---

## 1. Prerrequisitos

- Python 3.12 con el entorno `backend/.venv` provisionado.
- PostgreSQL 16 accesible en `DATABASE_URL`. Con `docker compose`:
  `postgresql+psycopg://ticketing:ticketing@localhost:5432/ticketing`.
- Node.js + dependencias de `frontend/node_modules` (Vue 3, Vite, Tailwind, Vitest).
- `curl`, `jq` y `uuidgen` o Python para generar UUID.
- Variables de entorno del backend:
  - `DATABASE_URL`
  - `JWT_SECRET`
  - `AUTH_DEV_STUB_ENABLED=true` (solo desarrollo local)
  - `AUTH_ISSUER`, `AUTH_AUDIENCE` (si el proveedor los exige)

**Datos de seed** (ver `data-model.md` §9.4). El seed de HU-04 se amplía para HU-06:

| Usuario | Correo | Rol | Equipo | Nivel |
|---|---|---|---|---|
| Técnico A | `tecnico.a@example.com` | `tecnico` | Soporte | `nivel_1` |
| Técnico B | `tecnico.b@example.com` | `tecnico` | Soporte | `nivel_1` |
| Técnico E | `tecnico.e@example.com` | `tecnico` | Soporte | `nivel_1` |
| Técnico F | `tecnico.f@example.com` | `tecnico` | Infraestructura | `nivel_1` |
| Técnico C | `tecnico.c@example.com` | `tecnico` | Soporte | `nivel_2` |
| Técnico D | `tecnico.d@example.com` | `tecnico` | Soporte | `especialista` |
| Supervisor | `supervisor@example.com` | `supervisor` | Soporte | `nivel_1` |
| Solicitante | `usuario@example.com` | `usuario` | — | `nivel_1` |

**Tickets relevantes**:

| Ticket | Estado | Creador | Responsable | Uso |
|---|---|---|---|---|
| `TK-000101` | `en_progreso` | Técnico A | Técnico A | Reasignación, escalado y notificaciones |
| `TK-000102` | `abierto` | Técnico B | Técnico A | Exclusión del creador técnico y visibilidad del motivo |
| `TK-000104` | `pendiente_usuario` | Técnico A | Técnico A | Destino no disponible y nivel sin técnicos |
| `TK-000105` | `abierto` | Técnico A | Técnico A | Token `expected_updated_at` obsoleto |
| `TK-000106` | `resuelto` | Técnico A | Técnico A | Ticket finalizado |
| `TK-000107` | `cerrado` | Técnico A | Técnico A | Ticket finalizado |

No se añaden servicios, brokers ni variables de entorno nuevas. Se reutilizan Docker Compose, PostgreSQL, FastAPI y Vue 3.

---

## 2. Preparar la base de datos

```bash
# Base de datos con Docker Compose (opcional si ya tienes PostgreSQL local)
docker compose up -d db

cd backend

# Windows (Git Bash / WSL)
source .venv/Scripts/activate
# Linux/macOS
# source .venv/bin/activate

export DATABASE_URL="postgresql+psycopg://ticketing:ticketing@localhost:5432/ticketing"
export JWT_SECRET="dev-only-secret"
export AUTH_DEV_STUB_ENABLED="true"

python -m alembic upgrade head
python -m alembic current
python scripts/seed_dev.py
```

**Esperado**:

- `alembic current` muestra `0004_assignee_changes (head)`.
- `users.escalation_level` existe y vale `nivel_1` para los usuarios existentes.
- `ticket_timeline_entries` tiene las cinco columnas nuevas y el valor `assignee_change` en su enum.
- `notifications` existe con sus índices y restricciones.
- El seed asigna los niveles y crea `TK-000102` con creador Técnico B y responsable Técnico A.

Verificación rápida en PostgreSQL:

```bash
docker compose exec -T db psql -U ticketing -d ticketing <<'SQL'
\d ticket_timeline_entries
\d notifications
SELECT enum_range(NULL::timeline_event_type);
SELECT enum_range(NULL::escalation_level);
SELECT email, role, team, escalation_level, is_active
FROM users
ORDER BY email;
SQL
```

**Esperado**:

- `timeline_event_type` contiene `status_change`, `resolution`, `internal_comment`, `assignee_change`.
- `escalation_level` contiene `nivel_1`, `nivel_2`, `especialista`.
- Los técnicos A, B y E están en Soporte/Nivel 1; F en Infraestructura/Nivel 1; C en Soporte/Nivel 2; D en Soporte/Especialista.

Guarda una instantánea de los campos que HU-06 **no debe modificar**:

```bash
docker compose exec -T db psql -U ticketing -d ticketing -A -F '|' -t <<'SQL' > /tmp/hu06_immutable_before.txt
SELECT number, status, priority_id, category_id, created_at, sla_deadline, sla_version
FROM tickets
WHERE number IN ('TK-000101', 'TK-000102', 'TK-000104')
ORDER BY number;
SQL

cat /tmp/hu06_immutable_before.txt
```

---

## 3. Pruebas automatizadas

### 3.1. Backend

```bash
cd backend
python -m pytest tests/unit/test_escalation_levels.py -q
python -m pytest tests/unit/test_assignee_selection.py -q
python -m pytest tests/integration/test_ticket_reassignment.py -q
python -m pytest tests/integration/test_ticket_escalation.py -q
python -m pytest tests/integration/test_assignee_change_permissions.py -q
python -m pytest tests/integration/test_notifications.py -q
python -m pytest tests/integration/test_assignee_change_performance.py -q -s
python -m pytest tests/contract/test_assignee_change_contract.py -q
```

**Esperado**:

| Suite | Resultado |
|---|---|
| Niveles | Orden total, etiquetas y `higher_escalation_levels(especialista) == ()` |
| Selección | Preferencia de equipo, menor carga, desempate por `lower(name)` e `id` |
| Reasignación | Éxitos, candidatos, autoasignación, creador y destinos inválidos |
| Escalado | Selección determinista, nivel máximo, nivel sin técnicos y replay |
| Permisos | Solo el técnico asignado; creador, supervisor, admin y técnico anterior rechazados |
| Notificaciones | Creación atómica, bandeja, contador, lectura idempotente y aislamiento |
| Rendimiento | p95 de opciones y comando < 300 ms; refresco percibido < 2 s |
| Contrato | Campos, códigos y estados HTTP coinciden con el OpenAPI |

### 3.2. Concurrencia real (PostgreSQL)

```bash
cd backend
export TEST_DATABASE_URL="postgresql+psycopg://ticketing:ticketing@localhost:5432/ticketing"
python -m pytest tests/integration/test_assignee_change_concurrency.py -q -k postgres
```

**Esperado**:

- Dos comandos simultáneos sobre el mismo ticket: solo uno escribe.
- El segundo recibe `409 stale_ticket`.
- No hay entradas `assignee_change` ni notificaciones duplicadas.
- Un replay idéntico del mismo actor devuelve `200 changed=false` aunque ya no sea el responsable.

### 3.3. Frontend

```bash
cd frontend
npm run test
npm run build
```

**Esperado**:

- Pasan `AssigneeSelector`, `EscalationLevelSelector`, `AssigneeChangeReasonForm`, `TicketAssigneeChangePanel`, `NotificationBell`, `NotificationList`, `TicketTimeline` y los stores.
- `npm run build` valida los tipos de los DTOs ampliados.
- Las pruebas con `axe-core` no detectan violaciones en los componentes nuevos.

---

## 4. Arrancar los servicios

**Opción A — local**:

```bash
# Terminal 1
cd backend
source .venv/Scripts/activate
export DATABASE_URL="postgresql+psycopg://ticketing:ticketing@localhost:5432/ticketing"
export JWT_SECRET="dev-only-secret"
export AUTH_DEV_STUB_ENABLED="true"
python -m uvicorn app.main:app --reload --port 8000

# Terminal 2
cd frontend
npm run dev
```

- API: `http://localhost:8000`
- UI: `http://localhost:5173`
- OpenAPI interactivo: `http://localhost:8000/docs`

**Opción B — Docker Compose**:

```bash
docker compose up --build
```

- API: `http://localhost:8000`
- UI: `http://localhost:8080`
- El backend aplica `alembic upgrade head` al arrancar; ejecuta el seed con
  `docker compose exec -T backend python scripts/seed_dev.py`.

---

## 5. Helpers de validación HTTP

```bash
BASE="http://localhost:8000/api/v1"

login_json() {
  curl -s -X POST "$BASE/dev/login" \
    -H 'Content-Type: application/json' \
    -d "{\"email\":\"$1\"}"
}

new_uuid() {
  python -c 'import uuid; print(uuid.uuid4())'
}

expected_for() {
  curl -s "$BASE/tickets/$1/workflow" \
    -H "Authorization: Bearer $2" | jq -r .ticket.updated_at
}

api_get() {
  curl -s "$1" -H "Authorization: Bearer $2"
}

api_post() {
  curl -s -X POST "$1" \
    -H "Authorization: Bearer $2" \
    -H 'Content-Type: application/json' \
    -d "$3"
}

api_post_code() {
  curl -s -o "${4:-/tmp/hu06.json}" -w '%{http_code}' \
    -X POST "$1" \
    -H "Authorization: Bearer $2" \
    -H 'Content-Type: application/json' \
    -d "$3"
}

dbq() {
  docker compose exec -T db psql -U "${POSTGRES_USER:-ticketing}" \
    -d "${POSTGRES_DB:-ticketing}" -tAc "$1" | tr -d '[:space:]'
}
```

> Si usas un PostgreSQL local, sustituye `dbq` por
> `psql "postgresql://ticketing:ticketing@localhost:5432/ticketing" -tAc "$1"`.

### 5.1. Obtener tokens e identificadores

```bash
A_JSON=$(login_json tecnico.a@example.com)
TOKEN_A=$(echo "$A_JSON" | jq -r .access_token)
ID_A=$(echo "$A_JSON" | jq -r .user.id)

B_JSON=$(login_json tecnico.b@example.com)
TOKEN_B=$(echo "$B_JSON" | jq -r .access_token)
ID_B=$(echo "$B_JSON" | jq -r .user.id)

C_JSON=$(login_json tecnico.c@example.com)
TOKEN_C=$(echo "$C_JSON" | jq -r .access_token)
ID_C=$(echo "$C_JSON" | jq -r .user.id)

D_JSON=$(login_json tecnico.d@example.com)
TOKEN_D=$(echo "$D_JSON" | jq -r .access_token)
ID_D=$(echo "$D_JSON" | jq -r .user.id)

E_JSON=$(login_json tecnico.e@example.com)
TOKEN_E=$(echo "$E_JSON" | jq -r .access_token)
ID_E=$(echo "$E_JSON" | jq -r .user.id)

F_JSON=$(login_json tecnico.f@example.com)
TOKEN_F=$(echo "$F_JSON" | jq -r .access_token)
ID_F=$(echo "$F_JSON" | jq -r .user.id)

SUP_JSON=$(login_json supervisor@example.com)
TOKEN_SUP=$(echo "$SUP_JSON" | jq -r .access_token)

USER_JSON=$(login_json usuario@example.com)
TOKEN_USER=$(echo "$USER_JSON" | jq -r .access_token)
```

### 5.2. Resolver los tickets del seed

```bash
T101=$(dbq "SELECT id FROM tickets WHERE number = 'TK-000101'")
T102=$(dbq "SELECT id FROM tickets WHERE number = 'TK-000102'")
T104=$(dbq "SELECT id FROM tickets WHERE number = 'TK-000104'")
T105=$(dbq "SELECT id FROM tickets WHERE number = 'TK-000105'")
T106=$(dbq "SELECT id FROM tickets WHERE number = 'TK-000106'")
T107=$(dbq "SELECT id FROM tickets WHERE number = 'TK-000107'")

printf 'T101=%s\nT102=%s\nT104=%s\nT105=%s\nT106=%s\nT107=%s\n' \
  "$T101" "$T102" "$T104" "$T105" "$T106" "$T107"
```

---

## 6. Validación HTTP

### 6.1. Opciones de cambio para el responsable actual

```bash
EXPECTED_101=$(expected_for "$T101" "$TOKEN_A")

api_get "$BASE/tickets/$T101/assignee-change-options" "$TOKEN_A" | jq
```

**Esperado**:

- `current_assignee.id == ID_A` y `escalation_level == "nivel_1"`.
- `has_reassignment_candidates == true` y `has_available_escalation_target == true`.
- `reassignment_candidates` contiene **Técnico B** y **Técnico E** (mismo equipo y nivel).
- No contiene Técnico C (Nivel 2), Técnico D (Especialista) ni Técnico F (Infraestructura).
- `escalation_targets` contiene `nivel_2` y `especialista`, ambos con `is_available == true`.
- La respuesta es de solo lectura: `updated_at` del ticket no cambia.

### 6.2. El creador técnico no es candidato

`TK-000102` tiene creador Técnico B y responsable Técnico A:

```bash
api_get "$BASE/tickets/$T102/assignee-change-options" "$TOKEN_A" \
  | jq '{has_reassignment_candidates, has_available_escalation_target, candidates: [.reassignment_candidates[].name]}'
```

**Esperado**:

- `candidates == ["Técnico E"]`.
- **No** aparece Técnico B, aunque sea técnico activo del mismo equipo y nivel, porque es el creador.

### 6.3. Matriz de permisos

```bash
# Técnico no creador y no asignado (E sobre TK-000101): 403 not_ticket_assignee
curl -s -o /tmp/hu06.json -w '%{http_code}\n' \
  "$BASE/tickets/$T101/assignee-change-options" \
  -H "Authorization: Bearer $TOKEN_E"
jq . /tmp/hu06.json

# Supervisor: 403 forbidden
curl -s -o /tmp/hu06.json -w '%{http_code}\n' \
  "$BASE/tickets/$T101/assignee-change-options" \
  -H "Authorization: Bearer $TOKEN_SUP"
jq . /tmp/hu06.json

# Creador técnico no asignado (B creó TK-000102): 403 forbidden
curl -s -o /tmp/hu06.json -w '%{http_code}\n' \
  "$BASE/tickets/$T102/assignee-change-options" \
  -H "Authorization: Bearer $TOKEN_B"
jq . /tmp/hu06.json

# Rol no técnico (solicitante): 403 forbidden
curl -s -o /tmp/hu06.json -w '%{http_code}\n' \
  "$BASE/tickets/$T101/assignee-change-options" \
  -H "Authorization: Bearer $TOKEN_USER"
jq . /tmp/hu06.json

# Sin token: 401 not_authenticated
curl -s -o /tmp/hu06.json -w '%{http_code}\n' \
  "$BASE/me/notifications"
jq . /tmp/hu06.json

# Ticket inexistente: 404 ticket_not_found
curl -s -o /tmp/hu06.json -w '%{http_code}\n' \
  "$BASE/tickets/00000000-0000-4000-8000-000000000000/assignee-change-options" \
  -H "Authorization: Bearer $TOKEN_A"
jq . /tmp/hu06.json
```

**Esperado**:

| Caso | HTTP | `detail.code` |
|---|---|---|
| Técnico E (no creador, no asignado) sobre `TK-000101` | `403` | `not_ticket_assignee` |
| Técnico B (creador, técnico, no asignado) sobre `TK-000102` | `403` | `forbidden` |
| Supervisor sobre `TK-000101` | `403` | `forbidden` |
| Solicitante (rol `usuario`) sobre `TK-000101` | `403` | `forbidden` |
| Sin token | `401` | `not_authenticated` |
| Ticket inexistente | `404` | `ticket_not_found` |

La fila de B verifica la precedencia de HU06-RN-11: es técnico activo y creador de `TK-000102`, pero no su responsable; recibe `forbidden` y no `not_ticket_assignee`. A es creador y responsable de `TK-000101`, y por eso sí puede consultar las opciones en 6.1 (opera como responsable, no como creador).

### 6.4. Rechazos de reasignación sin escritura

Todas estas peticiones usan el `EXPECTED_101` vigente y un `request_id` nuevo. Ninguna debe modificar el ticket ni la línea temporal.

```bash
# Autoasignación (A es también el creador de TK-000101)
BODY_SELF=$(jq -n --arg target "$ID_A" \
  --arg reason "Intento de autoasignación." \
  --arg expected "$EXPECTED_101" --arg rid "$(new_uuid)" \
  '{new_assignee_id:$target,reason:$reason,expected_updated_at:$expected,request_id:$rid}')
api_post_code "$BASE/tickets/$T101/reassignments" "$TOKEN_A" "$BODY_SELF" /tmp/hu06.json
jq . /tmp/hu06.json

# Destino creador: Técnico B es creador de TK-000102
EXPECTED_102=$(expected_for "$T102" "$TOKEN_A")
BODY_CREATOR=$(jq -n --arg target "$ID_B" \
  --arg reason "El creador no debe recibir el ticket." \
  --arg expected "$EXPECTED_102" --arg rid "$(new_uuid)" \
  '{new_assignee_id:$target,reason:$reason,expected_updated_at:$expected,request_id:$rid}')
api_post_code "$BASE/tickets/$T102/reassignments" "$TOKEN_A" "$BODY_CREATOR" /tmp/hu06.json
jq . /tmp/hu06.json

# Destino de otro equipo: Técnico F (Infraestructura)
BODY_TEAM=$(jq -n --arg target "$ID_F" \
  --arg reason "Destino de otro equipo." \
  --arg expected "$EXPECTED_101" --arg rid "$(new_uuid)" \
  '{new_assignee_id:$target,reason:$reason,expected_updated_at:$expected,request_id:$rid}')
api_post_code "$BASE/tickets/$T101/reassignments" "$TOKEN_A" "$BODY_TEAM" /tmp/hu06.json
jq . /tmp/hu06.json

# Destino de otro nivel: Técnico C (Nivel 2)
BODY_LEVEL=$(jq -n --arg target "$ID_C" \
  --arg reason "Destino de otro nivel." \
  --arg expected "$EXPECTED_101" --arg rid "$(new_uuid)" \
  '{new_assignee_id:$target,reason:$reason,expected_updated_at:$expected,request_id:$rid}')
api_post_code "$BASE/tickets/$T101/reassignments" "$TOKEN_A" "$BODY_LEVEL" /tmp/hu06.json
jq . /tmp/hu06.json

# Motivo vacío
BODY_NO_REASON=$(jq -n --arg target "$ID_E" \
  --arg reason "   " \
  --arg expected "$EXPECTED_101" --arg rid "$(new_uuid)" \
  '{new_assignee_id:$target,reason:$reason,expected_updated_at:$expected,request_id:$rid}')
api_post_code "$BASE/tickets/$T101/reassignments" "$TOKEN_A" "$BODY_NO_REASON" /tmp/hu06.json
jq . /tmp/hu06.json

# Motivo de 5.001 caracteres
LONG_REASON=$(python -c 'print("a" * 5001)')
BODY_LONG=$(jq -n --arg target "$ID_E" --arg reason "$LONG_REASON" \
  --arg expected "$EXPECTED_101" --arg rid "$(new_uuid)" \
  '{new_assignee_id:$target,reason:$reason,expected_updated_at:$expected,request_id:$rid}')
api_post_code "$BASE/tickets/$T101/reassignments" "$TOKEN_A" "$BODY_LONG" /tmp/hu06.json
jq . /tmp/hu06.json

# Payload incompleto: falta request_id
BODY_MISSING=$(jq -n --arg target "$ID_E" --arg reason "Motivo válido." \
  --arg expected "$EXPECTED_101" \
  '{new_assignee_id:$target,reason:$reason,expected_updated_at:$expected}')
api_post_code "$BASE/tickets/$T101/reassignments" "$TOKEN_A" "$BODY_MISSING" /tmp/hu06.json
jq . /tmp/hu06.json
```

**Esperado**:

| Caso | HTTP | `detail.code` |
|---|---|---|
| Destino igual al actual | `422` | `self_reassignment` |
| Destino es el creador | `422` | `creator_not_assignable` |
| Destino de otro equipo | `422` | `invalid_reassignment_target` |
| Destino de otro nivel | `422` | `invalid_reassignment_target` |
| Motivo vacío o solo espacios | `422` | `reason_required` |
| Motivo de 5.001 caracteres | `422` | `reason_too_long` |
| Falta `request_id` | `422` | `invalid_request` |

Comprueba que no hay escritura:

```bash
api_get "$BASE/tickets/$T101/workflow" "$TOKEN_A" \
  | jq '{assignee_id: .ticket.assignee_id, can_reassign, can_escalate}'

api_get "$BASE/tickets/$T101/timeline" "$TOKEN_A" \
  | jq '[.items[] | select(.type == "assignee_change")] | length'
```

**Esperado**: `assignee_id == ID_A`, capacidades `true` y longitud `0`.

### 6.5. Token de concurrencia obsoleto

```bash
EXPECTED_105_OLD=$(expected_for "$T105" "$TOKEN_A")

# Provoca un cambio real de versión con una transición de HU-05
BODY_STATUS=$(jq -n --arg expected "$EXPECTED_105_OLD" --arg rid "$(new_uuid)" \
  '{target_status:"en_progreso",expected_updated_at:$expected,request_id:$rid}')
api_post "$BASE/tickets/$T105/status-transitions" "$TOKEN_A" "$BODY_STATUS" | jq '.changed, .ticket.status'

# Reintenta la reasignación con el token antiguo
BODY_STALE=$(jq -n --arg target "$ID_E" \
  --arg reason "Este token ya está obsoleto." \
  --arg expected "$EXPECTED_105_OLD" --arg rid "$(new_uuid)" \
  '{new_assignee_id:$target,reason:$reason,expected_updated_at:$expected,request_id:$rid}')
api_post_code "$BASE/tickets/$T105/reassignments" "$TOKEN_A" "$BODY_STALE" /tmp/hu06.json
jq . /tmp/hu06.json
```

**Esperado**:

- La transición devuelve `changed == true` y `status == "en_progreso"`.
- La reasignación devuelve `409 stale_ticket`.
- `TK-000105` sigue asignado a Técnico A y no gana entradas `assignee_change`.

### 6.6. Reasignación correcta y append-only

```bash
EXPECTED_101=$(expected_for "$T101" "$TOKEN_A")
RID_101_REASSIGN=$(new_uuid)

BODY_REASSIGN_101=$(jq -n --arg target "$ID_E" \
  --arg reason "Estoy de vacaciones; el compañero conoce el caso." \
  --arg expected "$EXPECTED_101" --arg rid "$RID_101_REASSIGN" \
  '{new_assignee_id:$target,reason:$reason,expected_updated_at:$expected,request_id:$rid}')

api_post "$BASE/tickets/$T101/reassignments" "$TOKEN_A" "$BODY_REASSIGN_101" | jq
```

**Esperado**:

- `changed == true`.
- `ticket.assignee_id == ID_E`.
- `change_kind == "reassignment"`.
- `previous_assignee.name == "Técnico A"` y `new_assignee.name == "Técnico E"`.
- `from_escalation_level == to_escalation_level == "nivel_1"`.
- `timeline_entry.type == "assignee_change"` y `timeline_entry.body` contiene el motivo.
- El estado, la prioridad y el SLA no cambian.

Comprueba la línea temporal:

```bash
api_get "$BASE/tickets/$T101/timeline" "$TOKEN_A" \
  | jq '[.items[] | select(.type == "assignee_change")
         | {body, change_kind, previous: .previous_assignee.name,
            new: .new_assignee.name, from: .from_escalation_level,
            to: .to_escalation_level}]'
```

**Esperado**: exactamente una entrada `assignee_change`, con el motivo y los responsables A → E.

### 6.7. Idempotencia, replay y reutilización

Envía **exactamente** el mismo cuerpo anterior, incluido el `expected_updated_at` antiguo:

```bash
api_post "$BASE/tickets/$T101/reassignments" "$TOKEN_A" "$BODY_REASSIGN_101" \
  | jq '{changed, message, timeline_entry}'
```

**Esperado**:

- `changed == false`.
- `timeline_entry == null`.
- `message` indica que la reasignación ya se aplicó.
- La línea temporal sigue teniendo una sola entrada `assignee_change`.

Este caso demuestra que el replay exacto se resuelve antes de `ensure_assignee_change_actor`: Técnico A ya no es el responsable, pero el reintento de red sigue siendo idempotente.

Reutiliza el mismo `request_id` como responsable actual con otro destino:

```bash
EXPECTED_101_E=$(expected_for "$T101" "$TOKEN_E")
BODY_REUSE=$(jq -n --arg target "$ID_B" \
  --arg reason "Reutilización con otros datos." \
  --arg expected "$EXPECTED_101_E" --arg rid "$RID_101_REASSIGN" \
  '{new_assignee_id:$target,reason:$reason,expected_updated_at:$expected,request_id:$rid}')

api_post_code "$BASE/tickets/$T101/reassignments" "$TOKEN_E" "$BODY_REUSE" /tmp/hu06.json
jq . /tmp/hu06.json
```

**Esperado**:

- `409 request_id_reused`.
- Técnico E sigue siendo el responsable.
- No hay entrada nueva ni notificación nueva.

Comprueba que el técnico anterior pierde la escritura:

```bash
api_get "$BASE/tickets/$T101/workflow" "$TOKEN_A" \
  | jq '{can_reassign, can_escalate}'

curl -s -o /tmp/hu06.json -w '%{http_code}\n' \
  "$BASE/tickets/$T101/assignee-change-options" \
  -H "Authorization: Bearer $TOKEN_A"
jq . /tmp/hu06.json
```

**Esperado**: `can_reassign == false`, `can_escalate == false` y `403 forbidden`.

Técnico A es el creador de `TK-000101`; al no ser el responsable vigente, HU06-RN-11
(creador técnico no asignado) tiene precedencia sobre `not_ticket_assignee`, por
lo que el código es `forbidden`. Un técnico no creador y no asignado sí recibe
`403 not_ticket_assignee` (ver §6.3).

### 6.8. Visibilidad interna antes y después del escalado

Con Técnico E como responsable actual, añade un comentario interno:

```bash
BODY_INTERNAL=$(jq -n --arg body "Comentario interno de HU-06." --arg rid "$(new_uuid)" \
  '{body:$body,request_id:$rid}')
api_post "$BASE/tickets/$T101/internal-comments" "$TOKEN_E" "$BODY_INTERNAL" \
  | jq '{created, type: .entry.type, is_internal: .entry.is_internal}'
```

**Esperado**: `created == true`, `type == "internal_comment"`, `is_internal == true`.

Comprueba la visibilidad:

```bash
# Técnico A (creador y responsable anterior): no ve el comentario interno
api_get "$BASE/tickets/$T101/timeline" "$TOKEN_A" \
  | jq '[.items[] | select(.type == "internal_comment")] | length'

# Técnico E (responsable actual): sí lo ve
api_get "$BASE/tickets/$T101/timeline" "$TOKEN_E" \
  | jq '[.items[] | select(.type == "internal_comment")] | length'
```

**Esperado**: `0` para A y `1` para E.

### 6.9. Reasignación de `TK-000102` y visibilidad del motivo para el creador

```bash
EXPECTED_102=$(expected_for "$T102" "$TOKEN_A")
RID_102_REASSIGN=$(new_uuid)
BODY_REASSIGN_102=$(jq -n --arg target "$ID_E" \
  --arg reason "El creador conoce el caso y puede seguir el motivo." \
  --arg expected "$EXPECTED_102" --arg rid "$RID_102_REASSIGN" \
  '{new_assignee_id:$target,reason:$reason,expected_updated_at:$expected,request_id:$rid}')

api_post "$BASE/tickets/$T102/reassignments" "$TOKEN_A" "$BODY_REASSIGN_102" \
  | jq '{changed, new_assignee: .new_assignee.name, kind: .change_kind}'
```

**Esperado**: `changed == true`, nuevo responsable Técnico E, tipo `reassignment`.

El creador Técnico B puede leer la entrada pública y su motivo:

```bash
api_get "$BASE/tickets/$T102/timeline" "$TOKEN_B" \
  | jq '.items[] | select(.type == "assignee_change")
        | {body, previous: .previous_assignee.name, new: .new_assignee.name}'
```

**Esperado**: la entrada aparece con el motivo completo y A → E. B no ve comentarios internos.

### 6.10. Bandeja de notificaciones, contador y lectura

```bash
E_NOTIFS=$(api_get "$BASE/me/notifications?page_size=50" "$TOKEN_E")
echo "$E_NOTIFS" | jq '{unread_count, items: [.items[] | {id, ticket_number, type, previous_assignee_name, is_read}]}'
```

**Esperado**:

- `unread_count >= 2`.
- Hay una notificación `ticket_reassigned` para `TK-000101` y otra para `TK-000102`.
- `previous_assignee_name == "Técnico A"` en ambas.

Comprueba las cabeceras de caché:

```bash
curl -s -D - -o /dev/null "$BASE/me/notifications" \
  -H "Authorization: Bearer $TOKEN_E" \
  | grep -iE 'cache-control|vary'
```

**Esperado**: `Cache-Control: no-store` y `Vary: Authorization`.

Aislamiento entre usuarios:

```bash
NOTIF_101=$(echo "$E_NOTIFS" \
  | jq -r '.items[] | select(.ticket_number == "TK-000101") | .id' | head -n1)

# Otro usuario no puede leerla
curl -s -o /tmp/hu06.json -w '%{http_code}\n' \
  -X POST "$BASE/me/notifications/$NOTIF_101/read" \
  -H "Authorization: Bearer $TOKEN_B"
jq . /tmp/hu06.json

# El destinatario sí puede
api_post "$BASE/me/notifications/$NOTIF_101/read" "$TOKEN_E" "" \
  | jq '{changed, is_read: .notification.is_read, read_at: .notification.read_at}'
```

> `api_post` con cuerpo vacío no es válido para este endpoint sin cuerpo; usa directamente:
>
> ```bash
> curl -s -X POST "$BASE/me/notifications/$NOTIF_101/read" \
>   -H "Authorization: Bearer $TOKEN_E" | jq
> ```

**Esperado**:

- Técnico B recibe `404 notification_not_found`.
- Técnico E recibe `changed == true`, `is_read == true` y `read_at` no nulo.

Repite la lectura:

```bash
curl -s -X POST "$BASE/me/notifications/$NOTIF_101/read" \
  -H "Authorization: Bearer $TOKEN_E" | jq '{changed, message}'
```

**Esperado**: `changed == false` y un mensaje que indica que ya estaba leída.

Comprueba que el contador baja y que las notificaciones no se borran:

```bash
api_get "$BASE/me/notifications?page_size=50" "$TOKEN_E" \
  | jq '{unread_count, total: .pagination.total_items}'
```

**Esperado**: `unread_count` es una unidad menor que antes y la notificación leída sigue apareciendo.

### 6.11. Impacto en la cola de trabajo

```bash
# Técnico A ya no tiene TK-000101 ni TK-000102
api_get "$BASE/me/work-queue?page_size=100" "$TOKEN_A" \
  | jq '[.items[].number]'

# Técnico E los tiene
api_get "$BASE/me/work-queue?page_size=100" "$TOKEN_E" \
  | jq '[.items[].number]'
```

**Esperado**:

- La cola de A no contiene `TK-000101` ni `TK-000102`.
- La cola de E contiene ambos.
- La prioridad, el SLA y el orden se recalculan con las reglas de HU-04.

La API refleja el cambio de inmediato. En la interfaz, la cola se actualiza en el siguiente sondeo de 60 s o al recuperar foco/visibilidad.

### 6.12. Escalado de Nivel 1 a Nivel 2

Primero comprueba que no se puede escalar al mismo nivel:

```bash
BODY_BAD_LEVEL=$(jq -n --arg level "nivel_1" \
  --arg reason "Nivel no superior." \
  --arg expected "$EXPECTED_101_E" --arg rid "$(new_uuid)" \
  '{target_level:$level,reason:$reason,expected_updated_at:$expected,request_id:$rid}')
api_post_code "$BASE/tickets/$T101/escalations" "$TOKEN_E" "$BODY_BAD_LEVEL" /tmp/hu06.json
jq . /tmp/hu06.json
```

**Esperado**: `422 invalid_escalation_level` y ninguna escritura.

Ahora escala correctamente:

```bash
EXPECTED_101_E=$(expected_for "$T101" "$TOKEN_E")
RID_101_ESC1=$(new_uuid)
BODY_ESC_101=$(jq -n --arg level "nivel_2" \
  --arg reason "Requiere permisos de administración del servidor." \
  --arg expected "$EXPECTED_101_E" --arg rid "$RID_101_ESC1" \
  '{target_level:$level,reason:$reason,expected_updated_at:$expected,request_id:$rid}')

api_post "$BASE/tickets/$T101/escalations" "$TOKEN_E" "$BODY_ESC_101" | jq
```

**Esperado**:

- `changed == true`.
- `new_assignee.name == "Técnico C"` (único técnico activo de Nivel 2 en Soporte).
- `change_kind == "escalation"`.
- `from_escalation_level == "nivel_1"` y `to_escalation_level == "nivel_2"`.
- `timeline_entry.body` contiene el motivo.
- El estado, la prioridad y el SLA de `TK-000101` no cambian.

Repite exactamente el mismo cuerpo para validar el replay del escalado:

```bash
api_post "$BASE/tickets/$T101/escalations" "$TOKEN_E" "$BODY_ESC_101" \
  | jq '{changed, message, timeline_entry}'
```

**Esperado**: `changed == false`, `timeline_entry == null` y una sola entrada de escalado nueva.

Comprueba la notificación de Técnico C:

```bash
api_get "$BASE/me/notifications?page_size=50" "$TOKEN_C" \
  | jq '{unread_count, items: [.items[] | {ticket_number, type, previous_assignee_name, is_read}]}'
```

**Esperado**: al menos una notificación `ticket_escalated` para `TK-000101`, con `previous_assignee_name == "Técnico E"`.

### 6.13. Escalado a Especialista y nivel máximo

```bash
EXPECTED_101_C=$(expected_for "$T101" "$TOKEN_C")

# C no tiene compañeros de su nivel: no puede reasignar, pero sí escalar
api_get "$BASE/tickets/$T101/assignee-change-options" "$TOKEN_C" \
  | jq '{has_reassignment_candidates, has_available_escalation_target, candidates: .reassignment_candidates, targets: .escalation_targets}'
```

**Esperado**: `has_reassignment_candidates == false`, `has_available_escalation_target == true`, candidatos vacíos y `especialista` disponible.

```bash
RID_101_ESC2=$(new_uuid)
BODY_ESC_101_2=$(jq -n --arg level "especialista" \
  --arg reason "El caso necesita al especialista de base de datos." \
  --arg expected "$EXPECTED_101_C" --arg rid "$RID_101_ESC2" \
  '{target_level:$level,reason:$reason,expected_updated_at:$expected,request_id:$rid}')

api_post "$BASE/tickets/$T101/escalations" "$TOKEN_C" "$BODY_ESC_101_2" \
  | jq '{changed, new_assignee: .new_assignee.name, from: .from_escalation_level, to: .to_escalation_level}'
```

**Esperado**: `changed == true`, nuevo responsable Técnico D, `nivel_2 → especialista`.

Comprueba el nivel máximo y el orden de validación:

```bash
EXPECTED_101_D=$(expected_for "$T101" "$TOKEN_D")

api_get "$BASE/tickets/$T101/assignee-change-options" "$TOKEN_D" \
  | jq '{has_reassignment_candidates, has_available_escalation_target, targets: .escalation_targets}'

BODY_NO_HIGHER=$(jq -n --arg level "nivel_2" \
  --arg reason "Ya no hay nivel superior." \
  --arg expected "$EXPECTED_101_D" --arg rid "$(new_uuid)" \
  '{target_level:$level,reason:$reason,expected_updated_at:$expected,request_id:$rid}')
api_post_code "$BASE/tickets/$T101/escalations" "$TOKEN_D" "$BODY_NO_HIGHER" /tmp/hu06.json
jq . /tmp/hu06.json
```

**Esperado**:

- Opciones de D: `has_reassignment_candidates == false`, `has_available_escalation_target == false`, `escalation_targets == []`.
- Aunque el destino `nivel_2` sea un nivel existente, la respuesta es `409 no_higher_level` porque D ya está en el máximo.
- No se crea ninguna entrada ni notificación.

Comprueba la cadena completa de la línea temporal:

```bash
api_get "$BASE/tickets/$T101/timeline?page_size=200" "$TOKEN_A" \
  | jq '[.items[] | select(.type == "assignee_change")
         | {kind: .change_kind, previous: .previous_assignee.name,
            new: .new_assignee.name, from: .from_escalation_level,
            to: .to_escalation_level, body}]'
```

**Esperado**: tres entradas en orden A → E (`reassignment`), E → C (`escalation`) y C → D (`escalation`), con los motivos intactos.

### 6.14. Destino inactivo y nivel sin técnicos

**Destino inactivo**:

```bash
docker compose exec -T db psql -U ticketing -d ticketing \
  -c "UPDATE users SET is_active = false WHERE email = 'tecnico.e@example.com';"

EXPECTED_104=$(expected_for "$T104" "$TOKEN_A")
BODY_UNAVAILABLE=$(jq -n --arg target "$ID_E" \
  --arg reason "El técnico ya no está disponible." \
  --arg expected "$EXPECTED_104" --arg rid "$(new_uuid)" \
  '{new_assignee_id:$target,reason:$reason,expected_updated_at:$expected,request_id:$rid}')
api_post_code "$BASE/tickets/$T104/reassignments" "$TOKEN_A" "$BODY_UNAVAILABLE" /tmp/hu06.json
jq . /tmp/hu06.json

docker compose exec -T db psql -U ticketing -d ticketing \
  -c "UPDATE users SET is_active = true WHERE email = 'tecnico.e@example.com';"
```

**Esperado**: `422 assignee_unavailable`, sin cambios en `TK-000104`.

**Nivel sin técnicos**:

```bash
docker compose exec -T db psql -U ticketing -d ticketing \
  -c "UPDATE users SET is_active = false WHERE email = 'tecnico.c@example.com';"

api_get "$BASE/tickets/$T104/assignee-change-options" "$TOKEN_A" \
  | jq '.escalation_targets'

EXPECTED_104=$(expected_for "$T104" "$TOKEN_A")
BODY_NO_TECHS=$(jq -n --arg level "nivel_2" \
  --arg reason "No hay técnicos en el nivel destino." \
  --arg expected "$EXPECTED_104" --arg rid "$(new_uuid)" \
  '{target_level:$level,reason:$reason,expected_updated_at:$expected,request_id:$rid}')
api_post_code "$BASE/tickets/$T104/escalations" "$TOKEN_A" "$BODY_NO_TECHS" /tmp/hu06.json
jq . /tmp/hu06.json

docker compose exec -T db psql -U ticketing -d ticketing \
  -c "UPDATE users SET is_active = true WHERE email = 'tecnico.c@example.com';"
```

**Esperado**:

- `nivel_2` aparece con `technician_count == 0` e `is_available == false`.
- El comando devuelve `409 no_technicians_available`.
- `TK-000104` sigue asignado a Técnico A y sin entradas nuevas.

Restaura siempre los usuarios aunque un escenario falle. Al final del quickstart se incluye la comprobación.

### 6.15. Ticket finalizado

```bash
EXPECTED_106=$(expected_for "$T106" "$TOKEN_A")

# Opciones sobre un ticket resuelto
curl -s -o /tmp/hu06.json -w '%{http_code}\n' \
  "$BASE/tickets/$T106/assignee-change-options" \
  -H "Authorization: Bearer $TOKEN_A"
jq . /tmp/hu06.json

# Comando sobre un ticket cerrado
EXPECTED_107=$(expected_for "$T107" "$TOKEN_A")
BODY_FINAL=$(jq -n --arg target "$ID_E" \
  --arg reason "Intento sobre un ticket cerrado." \
  --arg expected "$EXPECTED_107" --arg rid "$(new_uuid)" \
  '{new_assignee_id:$target,reason:$reason,expected_updated_at:$expected,request_id:$rid}')
api_post_code "$BASE/tickets/$T107/reassignments" "$TOKEN_A" "$BODY_FINAL" /tmp/hu06.json
jq . /tmp/hu06.json
```

**Esperado**:

- Opciones de `TK-000106`: `409 ticket_finalized`.
- Reasignación de `TK-000107`: `409 ticket_finalized`.
- `TK-000106` y `TK-000107` no cambian de responsable ni ganan entradas.

### 6.16. Payload mal formado

```bash
# UUID inválido
BODY_BAD_UUID=$(jq -n --arg reason "UUID inválido." \
  --arg expected "$EXPECTED_104" --arg rid "$(new_uuid)" \
  '{new_assignee_id:"no-es-un-uuid",reason:$reason,expected_updated_at:$expected,request_id:$rid}')
api_post_code "$BASE/tickets/$T104/reassignments" "$TOKEN_A" "$BODY_BAD_UUID" /tmp/hu06.json
jq . /tmp/hu06.json

# Nivel desconocido
BODY_BAD_ENUM=$(jq -n --arg level "nivel_9" \
  --arg reason "Nivel desconocido." \
  --arg expected "$EXPECTED_104" --arg rid "$(new_uuid)" \
  '{target_level:$level,reason:$reason,expected_updated_at:$expected,request_id:$rid}')
api_post_code "$BASE/tickets/$T104/escalations" "$TOKEN_A" "$BODY_BAD_ENUM" /tmp/hu06.json
jq . /tmp/hu06.json
```

**Esperado**: `422 invalid_request` en ambos casos, sin escritura.

### 6.17. Verificación final de no escritura

```bash
# El responsable de TK-000101 es D y solo hay tres entradas assignee_change
api_get "$BASE/tickets/$T101/workflow" "$TOKEN_D" \
  | jq '{assignee_id: .ticket.assignee_id, can_reassign, can_escalate}'

api_get "$BASE/tickets/$T101/timeline?page_size=200" "$TOKEN_D" \
  | jq '[.items[] | select(.type == "assignee_change")] | length'

# TK-000104 sigue con A y sin entradas
api_get "$BASE/tickets/$T104/workflow" "$TOKEN_A" \
  | jq '{assignee_id: .ticket.assignee_id, can_reassign}'

api_get "$BASE/tickets/$T104/timeline" "$TOKEN_A" \
  | jq '[.items[] | select(.type == "assignee_change")] | length'
```

**Esperado**: `TK-000101` con D, `can_reassign == true`, `can_escalate == false` y 3 entradas; `TK-000104` con A y 0 entradas.

`can_reassign` expresa permiso (rol técnico + responsable vigente + estado activo),
no disponibilidad: D no tiene candidatos ni niveles superiores, pero conserva el
permiso de reasignación (`can_reassign == true`, ver §2.3 del `plan.md`). Lo que D
no puede es escalar (`can_escalate == false`, `409 no_higher_level` en §6.13).

---

## 7. Validación manual de la interfaz

Abre `http://localhost:5173` (o `http://localhost:8080` con Docker) e inicia sesión con cada rol.

| # | Escenario | Resultado esperado |
|---|---|---|
| 1 | Técnico A abre `TK-000101` | Ve «Cambiar responsable» con «Reasignar» y «Escalar» |
| 2 | A elige reasignar | El selector muestra solo compañeros de Soporte/Nivel 1 y excluye al creador |
| 3 | A intenta confirmar sin motivo | El botón está deshabilitado o aparece `reason_required`; el foco va al textarea |
| 4 | A reasigna a Técnico E | Aviso de éxito; la línea temporal muestra «Cambio de responsable» con motivo público |
| 5 | Técnico A consulta de nuevo el ticket | El panel de cambio de responsable ya no aparece; sigue viendo la línea temporal pública |
| 6 | Técnico E abre la campana | Contador de no leídas > 0; la notificación de `TK-000101` aparece en ≤ 30 s |
| 7 | E pulsa la notificación | Se marca como leída, el contador baja y navega al detalle del ticket |
| 8 | E abre la cola de trabajo | `TK-000101` aparece en su cola; en la de A desaparece tras ≤ 60 s o al recuperar foco |
| 9 | E elige escalar | Solo aparecen niveles superiores; nunca se calcula el orden en cliente |
| 10 | E escala a Nivel 2 | El nuevo responsable es Técnico C; la etiqueta muestra «Escalado a Nivel 2» |
| 11 | C abre `TK-000101` | No hay compañeros de su nivel para reasignar; sí puede escalar a Especialista |
| 12 | C escala a Especialista | Nuevo responsable Técnico D; notificación para D |
| 13 | D abre `TK-000101` | El panel aparece solo con «Reasignar a un compañero» (sin candidatos) y sin opción de escalar; `can_escalate == false` |
| 14 | Creador B abre `TK-000102` | No ve el panel de cambio de responsable; sí ve la entrada pública y el motivo |
| 15 | Supervisor abre `TK-000101` | No ve el panel; recibe error si intenta la operación por API |
| 16 | Técnico anterior A abre un comentario interno | No lo ve; el responsable actual sí |
| 17 | Dos pestañas con `TK-000105` | La segunda recibe aviso de conflicto, conserva el motivo y recarga opciones |
| 18 | Pestaña oculta durante > 15 s | El sondeo de la campana se pausa; al recuperar foco se refresca de inmediato |
| 19 | Ruta `/login` | La cabecera con la campana no se muestra |
| 20 | Solo teclado | Selectores, textarea, botones y campana son operables con foco visible; `Escape` cierra la campana |
| 21 | Ventana < 640 px | Panel y campana se apilan sin desbordamiento horizontal |
| 22 | Lector de pantalla | Se anuncian errores (`role="alert"`), éxitos (`role="status"`) y el contador de no leídas |

---

## 8. Comprobaciones SQL

Sustituye `<T101>` y `<T104>` por los UUID obtenidos en §5.2.

```sql
-- 1. La última entrada assignee_change coincide con el responsable actual
WITH latest AS (
  SELECT DISTINCT ON (ticket_id)
         ticket_id, new_assignee_id, created_at, id
  FROM ticket_timeline_entries
  WHERE event_type = 'assignee_change'
  ORDER BY ticket_id, created_at DESC, id DESC
)
SELECT t.id, t.number, t.assignee_id, l.new_assignee_id
FROM tickets t
JOIN latest l ON l.ticket_id = t.id
WHERE t.assignee_id <> l.new_assignee_id;

-- 2. Cadena de responsables: cada previous es el new anterior
WITH ordered AS (
  SELECT ticket_id, previous_assignee_id, new_assignee_id,
         LAG(new_assignee_id) OVER (
           PARTITION BY ticket_id ORDER BY created_at, id
         ) AS prior_new
  FROM ticket_timeline_entries
  WHERE event_type = 'assignee_change'
)
SELECT * FROM ordered
WHERE prior_new IS NOT NULL AND previous_assignee_id <> prior_new;

-- 3. Cada cambio tiene exactamente una notificación
SELECT e.id, e.ticket_id, e.request_id
FROM ticket_timeline_entries e
LEFT JOIN notifications n ON n.timeline_entry_id = e.id
WHERE e.event_type = 'assignee_change' AND n.id IS NULL;

-- 4. La notificación pertenece al nuevo responsable y al tipo correcto
SELECT n.id, n.type, e.change_kind, n.recipient_id, e.new_assignee_id
FROM notifications n
JOIN ticket_timeline_entries e ON e.id = n.timeline_entry_id
WHERE e.event_type <> 'assignee_change'
   OR n.recipient_id <> e.new_assignee_id
   OR (e.change_kind = 'reassignment' AND n.type <> 'ticket_reassigned')
   OR (e.change_kind = 'escalation' AND n.type <> 'ticket_escalated');

-- 5. Autoría y forma de la entrada
SELECT id, ticket_id, request_id
FROM ticket_timeline_entries
WHERE event_type = 'assignee_change'
  AND (
    author_id <> previous_assignee_id
    OR is_internal = true
    OR from_status IS NOT NULL
    OR to_status IS NOT NULL
    OR body IS NULL
    OR change_kind IS NULL
    OR from_escalation_level IS NULL
    OR to_escalation_level IS NULL
  );

-- 6. Monotonía de niveles
SELECT id, change_kind, from_escalation_level, to_escalation_level
FROM ticket_timeline_entries
WHERE event_type = 'assignee_change'
  AND (
    (change_kind = 'reassignment' AND from_escalation_level <> to_escalation_level)
    OR (
      change_kind = 'escalation'
      AND (CASE to_escalation_level
             WHEN 'nivel_1' THEN 1 WHEN 'nivel_2' THEN 2 WHEN 'especialista' THEN 3
           END)
        <= (CASE from_escalation_level
              WHEN 'nivel_1' THEN 1 WHEN 'nivel_2' THEN 2 WHEN 'especialista' THEN 3
            END)
    )
  );

-- 7. Sin duplicados de idempotencia
SELECT ticket_id, request_id, COUNT(*)
FROM ticket_timeline_entries
WHERE event_type = 'assignee_change'
GROUP BY ticket_id, request_id
HAVING COUNT(*) > 1;

-- 8. Coherencia de lectura de notificaciones
SELECT id FROM notifications
WHERE (is_read = true AND read_at IS NULL)
   OR (is_read = false AND read_at IS NOT NULL);

-- 9. Sin notificaciones huérfanas
SELECT n.id
FROM notifications n
LEFT JOIN tickets t ON t.id = n.ticket_id
LEFT JOIN ticket_timeline_entries e ON e.id = n.timeline_entry_id
WHERE t.id IS NULL OR e.id IS NULL;

-- 10. Entradas y notificaciones de TK-000101 / TK-000104
SELECT ticket_id, event_type, change_kind, previous_assignee_id,
       new_assignee_id, from_escalation_level, to_escalation_level,
       is_internal, created_at
FROM ticket_timeline_entries
WHERE ticket_id IN ('<T101>', '<T104>')
ORDER BY created_at, event_order, id;

SELECT ticket_id, type, recipient_id, previous_assignee_name, is_read, created_at
FROM notifications
WHERE ticket_id IN ('<T101>', '<T104>')
ORDER BY created_at, id;
```

**Esperado**: las consultas 1–9 devuelven 0 filas. La consulta 10 muestra tres entradas `assignee_change` para `TK-000101`, ninguna para `TK-000104`, y una notificación por cambio.

Compara la instantánea de campos inmutables:

```bash
docker compose exec -T db psql -U ticketing -d ticketing -A -F '|' -t <<'SQL' > /tmp/hu06_immutable_after.txt
SELECT number, status, priority_id, category_id, created_at, sla_deadline, sla_version
FROM tickets
WHERE number IN ('TK-000101', 'TK-000102', 'TK-000104')
ORDER BY number;
SQL

diff -u /tmp/hu06_immutable_before.txt /tmp/hu06_immutable_after.txt
```

**Esperado**: `diff` sin salida. HU-06 no altera estado, prioridad, categoría, fecha de creación, SLA ni versión de SLA.

---

## 9. Rendimiento y regresión

```bash
cd backend
python -m pytest tests/integration/test_assignee_change_performance.py -q -s
```

**Presupuestos**:

| Medición | Presupuesto |
|---|---|
| `GET /tickets/{id}/assignee-change-options` (p95) | < 300 ms |
| `POST /tickets/{id}/reassignments` (p95) | < 300 ms |
| `POST /tickets/{id}/escalations` (p95) | < 300 ms |
| Reasignación + refresco de timeline | < 2 s percibidos |
| `GET /me/notifications` (p95) | < 300 ms |

La prueba falla si una medición supera su presupuesto. Para medir sobre PostgreSQL, exporta `TEST_DATABASE_URL` antes de lanzarla. El sondeo de la campana cada 15 s y el de la cola cada 60 s no se bloquean entre sí.

---

## 10. Limpieza

Restaura los usuarios que se desactivan temporalmente en §6.14:

```bash
docker compose exec -T db psql -U ticketing -d ticketing <<'SQL'
UPDATE users SET is_active = true
WHERE email IN ('tecnico.c@example.com', 'tecnico.e@example.com');
SQL
```

Vuelve a un estado limpio de pruebas (solo entorno local). El `downgrade()` de `0004` es **destructivo** para los datos de HU-06:

```bash
cd backend
python -m alembic downgrade 0003_ticket_timeline
python -m alembic upgrade head
python scripts/seed_dev.py
```

También puedes restaurar el dump/seed de desarrollo habitual. Para detener los servicios:

```bash
docker compose down
```

No ejecutes `docker compose down -v` salvo que quieras borrar el volumen de PostgreSQL.

---

## 11. Criterios de éxito de la validación

- [X] `alembic current` muestra `0004_assignee_changes (head)`.
- [X] El seed asigna niveles y crea `TK-000102` con creador Técnico B y responsable Técnico A.
- [X] Solo el técnico asignado vigente consulta opciones y ejecuta comandos; los roles no técnicos y el creador técnico no asignado reciben `403 forbidden` con precedencia, y el técnico anterior no creador `403 not_ticket_assignee`, salvo el replay idéntico que devuelve `200 changed=false` sin escribir.
- [X] Un creador con rol técnico que no está asignado recibe `forbidden`, no `not_ticket_assignee`; si es el técnico asignado, opera como responsable; un técnico no asignado no creador recibe `not_ticket_assignee`; un rol no técnico recibe `forbidden`.
- [X] El creador técnico nunca aparece como candidato de reasignación ni entra en el pool de escalado, y recibe `creator_not_assignable` si se intenta reasignar a él.
- [X] El motivo vacío devuelve `reason_required`; 5.001 caracteres devuelven `reason_too_long`.
- [X] `expected_updated_at` obsoleto devuelve `409 stale_ticket` sin escribir.
- [X] Un ticket finalizado devuelve `409 ticket_finalized` en opciones y comandos.
- [X] La reasignación actualiza `assignee_id` y crea una entrada `assignee_change` pública con motivo.
- [X] El replay idéntico devuelve `200 changed=false` sin duplicar entrada ni notificación, incluso si el actor ya no es responsable.
- [X] Reutilizar `request_id` con otros datos devuelve `409 request_id_reused` sin escribir.
- [X] El escalado elige el nivel destino y el backend selecciona al técnico de forma determinista.
- [X] Un responsable en `especialista` recibe `409 no_higher_level` antes que `invalid_escalation_level`.
- [X] Un nivel sin técnicos activos disponibles (excluido el creador) devuelve `409 no_technicians_available`.
- [X] Un destino inactivo devuelve `422 assignee_unavailable`.
- [X] La entrada `assignee_change` es visible para el creador con su motivo y nunca es interna.
- [X] El técnico anterior pierde escritura y visibilidad interna; el nuevo responsable las gana.
- [X] Se crea exactamente una notificación por cambio y solo para el nuevo responsable.
- [X] La campana muestra la notificación en ≤ 30 s; el contador se calcula en servidor.
- [X] Marcar como leída es idempotente y no borra la notificación.
- [X] Un usuario no puede leer ni marcar notificaciones ajenas (`404 notification_not_found`).
- [X] El ticket sale de la cola anterior y entra en la nueva; la API lo refleja de inmediato y la UI en ≤ 60 s.
- [X] Estado, prioridad, categoría, SLA, `finalized_at` y `closed_at` no cambian.
- [X] La línea temporal es append-only: no hay endpoints de edición ni borrado y las entradas previas permanecen.
- [X] Las consultas SQL 1–9 de §8 devuelven 0 filas y el `diff` de campos inmutables está vacío.
- [X] Las pruebas de backend, frontend, contrato, concurrencia y rendimiento pasan.
- [X] La interfaz es operable solo con teclado, anuncia errores/éxitos y no depende solo del color.

---

## 12. Evidencia de validación (2026-11-14)

Registro de la ejecución completa de este quickstart sobre Docker Compose
(`db` PostgreSQL 16, `backend`, `frontend`) y sobre las suites locales.

| Comprobación | Comando | Resultado |
|---|---|---|
| Backend (SQLite, puerta por defecto) | `python -m pytest -q -rs` en `backend/` | `314 passed, 7 skipped` (los 7 son las pruebas `with_for_update` marcadas `postgres`) |
| Backend (PostgreSQL 16) | `python -m pytest -q -rs` con `TEST_DATABASE_URL=postgresql+psycopg://…/ticketing_test` | `321 passed` — 0 omitidas, incluye `test_assignee_change_concurrency.py` (T071/T088/T122) |
| Migración real | `alembic upgrade head` → `downgrade -1` → `upgrade head` | OK; cabeza final `0004_assignee_changes (head)` |
| Frontend | `npm run test` | 22 archivos / 185 pruebas en verde |
| Frontend build | `npm run build` (`vue-tsc --noEmit && vite build`) | OK, sin `any` en los DTOs ampliados |
| Escenarios HTTP §6 | script de extremo a extremo sobre el stack | **82 comprobaciones, 0 fallos** (§6.1–§6.17) |
| Consultas SQL §8 (1–9) | `psql` sobre `ticketing` tras §6 | 0 filas en las nueve |
| Snapshot de campos inmutables §8 | `diff` antes/después de §6 para `TK-000101/102/104` | `diff` vacío: estado, prioridad, categoría, `created_at`, SLA y `sla_version` intactos |

Cadena verificada para `TK-000101` tras el recorrido completo:
`A → E (reassignment, nivel_1→nivel_1)`, `E → C (escalation, nivel_1→nivel_2)`,
`C → D (escalation, nivel_2→especialista)`; `TK-000104` sigue con A y sin entradas.
Se creó exactamente una notificación por cambio (4 entradas → 4 notificaciones).

### Correcciones de documentación detectadas al ejecutar §6

- §6.7: Técnico A es el **creador** de `TK-000101`; al perder la asignación recibe
  `403 forbidden` (HU06-RN-11, precedencia del creador técnico no asignado) y no
  `not_ticket_assignee`. El caso `not_ticket_assignee` queda cubierto por §6.3 con
  un técnico no creador y no asignado.
- §6.17 y §7 (escenario 13): `can_reassign` expresa **permiso**, no disponibilidad
  (`plan.md` §2.3). El Especialista D conserva `can_reassign == true` aunque no
  tenga candidatos ni nivel superior; lo que pierde es `can_escalate`.

### Revisión de seguridad de datos internos (constitución, §Flujo de desarrollo, punto 4)

Evidencia en `backend/tests/integration/test_assignee_change_permissions.py`,
`test_timeline_visibility.py`, `test_notifications.py` y `test_assignee_change_contract.py`:

- Precedencia aplicada: rol no técnico y creador técnico no asignado → `403 forbidden`
  antes que `not_ticket_assignee`; el creador asignado opera como responsable.
- Los comentarios internos no se serializan para el creador ni para técnicos no
  asignados; `can_view_internal` se revoca al técnico anterior y se concede al nuevo.
- El motivo del cambio solo vive en `ticket_timeline_entries.body` (entrada pública);
  no se copia a `notifications` ni aparece en los logs estructurados.
- Las opciones de reasignación nunca incluyen al responsable actual ni al creador, y
  el pool de escalado excluye al creador.
- Las respuestas de opciones y bandeja usan `Cache-Control: no-store` y
  `Vary: Authorization` para evitar fugas entre usuarios.
