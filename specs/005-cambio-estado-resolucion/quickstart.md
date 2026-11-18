# Quickstart — Validación de HU-05

**Feature**: `005-cambio-estado-resolucion` | **Date**: 2026-11-02

Guía ejecutable para demostrar de extremo a extremo que el cambio de estado, la resolución obligatoria, la línea temporal y los comentarios internos funcionan según la especificación. No contiene la implementación; solo pasos de validación.

**Contratos de referencia**: [`contracts/ticket-workflow.openapi.yaml`](./contracts/ticket-workflow.openapi.yaml) para la API HTTP y [`contracts/frontend-components.md`](./contracts/frontend-components.md) para los componentes Vue.

---

## 1. Prerrequisitos

- Python 3.12 con el entorno `backend/.venv` provisionado.
- PostgreSQL accesible en `DATABASE_URL` (por defecto `postgresql+psycopg://ticketing:ticketing@localhost:5432/ticketing`).
- Node.js + dependencias de `frontend/node_modules` (Vue 3, Vite, Tailwind, Vitest).
- Variables de entorno del backend:
  - `DATABASE_URL`
  - `JWT_SECRET`
  - `AUTH_DEV_STUB_ENABLED=true` (solo desarrollo local)
  - `AUTH_ISSUER`, `AUTH_AUDIENCE`
- Datos de seed con al menos:
  - un técnico (`tecnico.a@example.com`, rol `tecnico`),
  - un usuario creador (`usuario.b@example.com`, rol `usuario`),
  - un supervisor (`supervisor@example.com`, rol `supervisor`),
  - un ticket asignado al técnico en estado `abierto`.

---

## 2. Preparar la base de datos

```bash
cd backend

# Windows
.venv\Scripts\activate
# Linux/macOS
# source .venv/bin/activate

python -m alembic upgrade head
python -m alembic current
```

**Esperado**:

- `alembic current` muestra `0003_ticket_timeline (head)`.
- La tabla `ticket_timeline_entries` existe con sus índices.
- `tickets` no ha cambiado de columnas.

Verificación rápida en PostgreSQL:

```sql
\d ticket_timeline_entries
SELECT enum_range(NULL::timeline_event_type);
```

**Esperado**: el enum contiene `status_change`, `resolution`, `internal_comment`.

---

## 3. Pruebas automatizadas

### 3.1. Backend

```bash
cd backend
python -m pytest tests/unit/test_ticket_state_machine.py -q
python -m pytest tests/integration/test_ticket_status_transitions.py -q
python -m pytest tests/integration/test_ticket_concurrency.py -q
python -m pytest tests/integration/test_internal_comments.py -q
python -m pytest tests/integration/test_timeline_visibility.py -q
python -m pytest tests/contract/test_ticket_workflow_contract.py -q
```

**Esperado**:

| Suite | Resultado |
|---|---|
| Matriz de estados | 25 combinaciones cubiertas; solo las 6 permitidas pasan |
| Transiciones | Éxitos, rechazos, atomicidad, reapertura y no-op |
| Comentarios internos | Alta en todos los estados, validación e idempotencia |
| Visibilidad | Creador y técnico no asignado no reciben filas internas |
| Contrato | Campos y códigos de error coinciden con el OpenAPI |

### 3.2. Frontend

```bash
cd frontend
npm run test -- --run
```

**Esperado**: pasan las pruebas de `TicketStatusSelector`, `ResolutionForm`, `InternalCommentForm`, `TicketTimeline` y `TicketWorkflowPanel`.

### 3.3. Concurrencia real (PostgreSQL)

```bash
cd backend
python -m pytest tests/integration/test_ticket_concurrency.py -q -k "postgres"
```

**Esperado**:

- Dos comandos simultáneos sobre el mismo ticket: solo uno escribe.
- El segundo recibe `409 stale_ticket` o `200 changed=false` si el destino ya coincide.
- No hay entradas duplicadas.

---

## 4. Arrancar los servicios

```bash
# Terminal 1
cd backend
.venv\Scripts\activate
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

> `jq` es opcional; puedes copiar el `access_token` manualmente.

### 5.2. Leer el flujo del ticket

```bash
TICKET_ID=<uuid-del-ticket>

curl -s "$BASE/tickets/$TICKET_ID/workflow" \
  -H "Authorization: Bearer $TECNICO" | jq
```

**Esperado**:

```json
{
  "ticket": {
    "status": "abierto",
    "status_label": "Abierto",
    "allowed_transitions": [
      { "value": "en_progreso", "label": "En progreso" }
    ],
    "updated_at": "2026-11-02T10:00:00.000000+00:00"
  },
  "can_change_status": true,
  "can_comment_internally": true,
  "can_view_internal": true
}
```

Guarda `updated_at` como `EXPECTED`:

```bash
EXPECTED=$(curl -s "$BASE/tickets/$TICKET_ID/workflow" \
  -H "Authorization: Bearer $TECNICO" | jq -r .ticket.updated_at)
```

### 5.3. Abierto → En progreso

```bash
curl -s -X POST "$BASE/tickets/$TICKET_ID/status-transitions" \
  -H "Authorization: Bearer $TECNICO" \
  -H 'Content-Type: application/json' \
  -d "{
    \"target_status\": \"en_progreso\",
    \"expected_updated_at\": \"$EXPECTED\",
    \"request_id\": \"$(uuidgen)\"
  }" | jq
```

**Esperado**:

- `changed: true`
- `ticket.status: "en_progreso"`
- `timeline_entries` con una entrada `status_change` (`abierto → en_progreso`)
- `finalized_at: null`

### 5.4. Intentar resolver sin descripción

```bash
EXPECTED=$(curl -s "$BASE/tickets/$TICKET_ID/workflow" \
  -H "Authorization: Bearer $TECNICO" | jq -r .ticket.updated_at)

curl -s -o /tmp/resp.json -w '%{http_code}\n' \
  -X POST "$BASE/tickets/$TICKET_ID/status-transitions" \
  -H "Authorization: Bearer $TECNICO" \
  -H 'Content-Type: application/json' \
  -d "{
    \"target_status\": \"resuelto\",
    \"resolution\": \"   \",
    \"expected_updated_at\": \"$EXPECTED\",
    \"request_id\": \"$(uuidgen)\"
  }"

cat /tmp/resp.json | jq
```

**Esperado**:

- HTTP `422`
- `detail.code = "resolution_required"`
- `detail.message = "Indica la descripción de la solución para marcar el ticket como Resuelto."`
- El ticket sigue en `en_progreso` y la línea temporal no gana entradas.

### 5.5. Resolver con descripción válida

```bash
EXPECTED=$(curl -s "$BASE/tickets/$TICKET_ID/workflow" \
  -H "Authorization: Bearer $TECNICO" | jq -r .ticket.updated_at)

curl -s -X POST "$BASE/tickets/$TICKET_ID/status-transitions" \
  -H "Authorization: Bearer $TECNICO" \
  -H 'Content-Type: application/json' \
  -d "{
    \"target_status\": \"resuelto\",
    \"resolution\": \"Se reinició el servicio y se verificó el acceso.\",
    \"expected_updated_at\": \"$EXPECTED\",
    \"request_id\": \"$(uuidgen)\"
  }" | jq
```

**Esperado**:

- `changed: true`
- `ticket.status: "resuelto"`
- `ticket.finalized_at` no nulo
- `ticket.closed_at: null`
- Dos entradas: `status_change` (`en_progreso → resuelto`) y `resolution` con el texto.

### 5.6. Comprobar la línea temporal

```bash
curl -s "$BASE/tickets/$TICKET_ID/timeline" \
  -H "Authorization: Bearer $TECNICO" | jq '.items[] | {type, from_status, to_status, is_internal, body}'
```

**Esperado**: orden cronológico; la resolución aparece después del cambio de estado.

### 5.7. Cerrar el ticket

```bash
EXPECTED=$(curl -s "$BASE/tickets/$TICKET_ID/workflow" \
  -H "Authorization: Bearer $TECNICO" | jq -r .ticket.updated_at)

curl -s -X POST "$BASE/tickets/$TICKET_ID/status-transitions" \
  -H "Authorization: Bearer $TECNICO" \
  -H 'Content-Type: application/json' \
  -d "{
    \"target_status\": \"cerrado\",
    \"expected_updated_at\": \"$EXPECTED\",
    \"request_id\": \"$(uuidgen)\"
  }" | jq '.ticket | {status, finalized_at, closed_at, allowed_transitions}'
```

**Esperado**:

- `status: "cerrado"`
- `finalized_at` se conserva
- `closed_at` no nulo
- `allowed_transitions: []`

### 5.8. Comentario interno en ticket cerrado

```bash
curl -s -X POST "$BASE/tickets/$TICKET_ID/internal-comments" \
  -H "Authorization: Bearer $TECNICO" \
  -H 'Content-Type: application/json' \
  -d "{
    \"body\": \"Comprobado el registro del servidor; el error era de credenciales.\",
    \"request_id\": \"$(uuidgen)\"
  }" | jq
```

**Esperado**:

- `created: true`
- `entry.type: "internal_comment"`
- `entry.is_internal: true`
- El estado del ticket sigue siendo `cerrado`.

Repite la misma petición con el **mismo** `request_id`:

**Esperado**: `created: false` y una sola entrada en la línea temporal.

Repite ahora con el mismo `request_id` y otro `body`:

**Esperado**: HTTP `409`, `detail.code = "request_id_reused"` y ninguna entrada nueva.

### 5.9. Visibilidad para el usuario creador

```bash
curl -s "$BASE/tickets/$TICKET_ID/timeline" \
  -H "Authorization: Bearer $CREADOR" | jq
```

**Esperado**:

- Incluye `status_change` y `resolution`.
- **No** incluye ninguna entrada `internal_comment`.

### 5.10. Visibilidad para supervisor

```bash
curl -s "$BASE/tickets/$TICKET_ID/timeline" \
  -H "Authorization: Bearer $SUPERVISOR" | jq '.items[] | {type, is_internal}'
```

**Esperado**: incluye la entrada `internal_comment`.

### 5.11. Transición inválida desde cerrado

```bash
EXPECTED=$(curl -s "$BASE/tickets/$TICKET_ID/workflow" \
  -H "Authorization: Bearer $TECNICO" | jq -r .ticket.updated_at)

curl -s -o /tmp/resp.json -w '%{http_code}\n' \
  -X POST "$BASE/tickets/$TICKET_ID/status-transitions" \
  -H "Authorization: Bearer $TECNICO" \
  -H 'Content-Type: application/json' \
  -d "{
    \"target_status\": \"abierto\",
    \"expected_updated_at\": \"$EXPECTED\",
    \"request_id\": \"$(uuidgen)\"
  }"

cat /tmp/resp.json | jq
```

**Esperado**:

- HTTP `409`
- `detail.code = "ticket_closed"`
- El estado sigue `cerrado` y no se crea ninguna entrada.

### 5.12. Token de concurrencia desactualizado

```bash
# Usa un EXPECTED antiguo (de antes de la última transición)
curl -s -o /tmp/resp.json -w '%{http_code}\n' \
  -X POST "$BASE/tickets/$TICKET_ID/status-transitions" \
  -H "Authorization: Bearer $TECNICO" \
  -H 'Content-Type: application/json' \
  -d "{
    \"target_status\": \"en_progreso\",
    \"expected_updated_at\": \"2020-01-01T00:00:00+00:00\",
    \"request_id\": \"$(uuidgen)\"
  }"

cat /tmp/resp.json | jq
```

**Esperado**:

- HTTP `409`
- `detail.code = "stale_ticket"`
- Ninguna escritura ni entrada nueva.

### 5.13. Doble envío e idempotencia por `request_id`

> Ejecuta este escenario sobre un ticket independiente del seed en estado `abierto` (por ejemplo, `TICKET_ID_2`), para no interferir con 5.3–5.12. La transición `abierto → en_progreso` es real, así que el primer envío devuelve `changed=true`. Si reutilizaras un ticket ya en `en_progreso`, el primer envío sería un no-op (`changed=false`) y el escenario no validaría la idempotencia. Un ticket `cerrado` devuelve `409 ticket_closed`.

Envía dos veces seguidas la misma transición con el mismo `EXPECTED` y el mismo `request_id`:

```bash
TICKET_ID_2=<uuid-de-otro-ticket-abierto>

EXPECTED=$(curl -s "$BASE/tickets/$TICKET_ID_2/workflow" \
  -H "Authorization: Bearer $TECNICO" | jq -r .ticket.updated_at)
REQUEST_ID=$(uuidgen)
BODY="{\"target_status\":\"en_progreso\",\"expected_updated_at\":\"$EXPECTED\",\"request_id\":\"$REQUEST_ID\"}"

curl -s -X POST "$BASE/tickets/$TICKET_ID_2/status-transitions" \
  -H "Authorization: Bearer $TECNICO" -H 'Content-Type: application/json' -d "$BODY" | jq '.changed'

curl -s -X POST "$BASE/tickets/$TICKET_ID_2/status-transitions" \
  -H "Authorization: Bearer $TECNICO" -H 'Content-Type: application/json' -d "$BODY" | jq '.changed, .message, .timeline_entries'
```

**Esperado**:

- Primera: `true`.
- Segunda: `false`, `timeline_entries: []` y «Esta transición ya se aplicó con el identificador de solicitud indicado.».
- En ningún caso se duplican entradas.

Reutiliza el mismo `request_id` con otro destino o resolución:

```bash
curl -s -o /tmp/resp.json -w '%{http_code}\n' \
  -X POST "$BASE/tickets/$TICKET_ID_2/status-transitions" \
  -H "Authorization: Bearer $TECNICO" \
  -H 'Content-Type: application/json' \
  -d "{
    \"target_status\": \"resuelto\",
    \"resolution\": \"Se reinició el servicio y se verificó el acceso.\",
    \"expected_updated_at\": \"$EXPECTED\",
    \"request_id\": \"$REQUEST_ID\"
  }"

cat /tmp/resp.json | jq
```

**Esperado**:

- HTTP `409`
- `detail.code = "request_id_reused"`
- Ninguna escritura ni entrada nueva.

---

## 6. Validación manual de la interfaz

Abre `http://localhost:5173/tickets/<TICKET_ID>` con cada rol.

| # | Escenario | Resultado esperado |
|---|---|---|
| 1 | Técnico, ticket `abierto` | Solo aparece «En progreso» como destino |
| 2 | Técnico elige «En progreso» y guarda | Badge y línea temporal se actualizan sin recargar |
| 3 | Técnico elige «Resuelto» | Aparece el textarea de resolución; el botón está deshabilitado |
| 4 | Escribe solo espacios | El botón sigue deshabilitado; el contador muestra `0 / 5000` |
| 5 | Escribe texto válido y guarda | Estado `Resuelto`; tarjeta «Resolución» visible en la línea temporal |
| 6 | Pega 5.001 caracteres | El campo se limita a 5.000; el botón no envía un texto excesivo |
| 7 | Ticket `cerrado` | No hay destinos; se muestra «El ticket está cerrado…» |
| 8 | Ticket `cerrado` + comentario interno | El comentario se guarda y aparece con etiqueta «Interno» |
| 9 | Usuario creador | Ve estados y resoluciones; no ve entradas «Interno» |
| 10 | Técnico no asignado | No ve entradas «Interno» y recibe error si intenta escribir |
| 11 | Simular `409 stale_ticket` (dos pestañas) | Aviso de conflicto, recarga y texto conservado |
| 12 | Solo teclado | Todos los controles son accesibles con foco visible |
| 13 | Ventana estrecha (< 640 px) | El panel se apila en una columna sin desbordamiento |

---

## 7. Comprobaciones SQL

```sql
-- Entradas del ticket en orden
SELECT event_type, from_status, to_status, is_internal, event_order, created_at
FROM ticket_timeline_entries
WHERE ticket_id = '<TICKET_ID>'
ORDER BY created_at, event_order, id;

-- No debe haber tickets resueltos sin resolución (excluye el legado anterior a 0003)
-- Ajusta '2026-11-02' a la fecha real de aplicación de la migración 0003_ticket_timeline.
SELECT t.id, t.number
FROM tickets t
LEFT JOIN ticket_timeline_entries e
  ON e.ticket_id = t.id AND e.event_type = 'resolution'
WHERE t.status = 'resuelto'
  AND t.finalized_at >= '2026-11-02'
  AND e.id IS NULL;

-- Listado de legado: resueltos/cerrados sin resolución anteriores a la migración
SELECT t.id, t.number, t.status, t.created_at
FROM tickets t
LEFT JOIN ticket_timeline_entries e
  ON e.ticket_id = t.id AND e.event_type = 'resolution'
WHERE t.status IN ('resuelto','cerrado')
  AND t.finalized_at < '2026-11-02'
  AND e.id IS NULL
ORDER BY t.created_at;

-- Coherencia estado ↔ finalized_at
SELECT id, number, status, finalized_at, closed_at
FROM tickets
WHERE (status IN ('resuelto','cerrado') AND finalized_at IS NULL)
   OR (status NOT IN ('resuelto','cerrado') AND finalized_at IS NOT NULL);

-- No debe haber comentarios internos públicos
SELECT id FROM ticket_timeline_entries
WHERE event_type = 'internal_comment' AND is_internal = false;
```

**Esperado**: la segunda, la cuarta y la quinta consultas devuelven 0 filas. La tercera (listado de legado) puede devolver filas y debe registrarse en la auditoría; no se corrige automáticamente.

---

## 8. Rendimiento y regresión

La comprobación ejecutable de rendimiento mide el p95 de las lecturas, el p95 del comando de transición y el tiempo observable de una transición con refresco de timeline. Usa el fixture `seeded_workflow` (equivalente al seed de §3.3) y añade 60 entradas de histórico para que la línea temporal no se mida vacía.

```bash
cd backend
python -m pytest tests/integration/test_ticket_workflow_performance.py -q -s
```

**Resultados de referencia** (6 de noviembre de 2026; Windows 11, Python 3.12.14, SQLite de pruebas, `TestClient`; media de tres ejecuciones):

| Medición | Resultado | Presupuesto |
|---|---|---|
| `GET /tickets/{id}/workflow` (p95) | 4,26–7,37 ms | < 300 ms |
| `GET /tickets/{id}/timeline` (p95) | 7,42–13,65 ms | < 300 ms |
| `POST /tickets/{id}/status-transitions` (p95) | 24,09 ms | < 300 ms |
| Transición + refresco de timeline | 19,30–76,61 ms | < 2 s percibidos |

La fila del `POST /tickets/{id}/status-transitions` se midió el 9 de noviembre de 2026 en el mismo entorno de referencia (Windows 11, Python 3.12.14, SQLite de pruebas, `TestClient`); el valor de referencia es 24,09 ms y las repeticiones de verificación quedaron entre 23,84 ms y 61,74 ms, siempre por debajo del presupuesto de 300 ms. La cuarta fila es la cota superior del tiempo percibido en la interfaz: el panel ejecuta el `POST` de la transición y, al recibir la respuesta, recarga la timeline; ambas peticiones son las que mide la prueba. La tercera fila mide el p95 del comando de escritura aislado, conforme a la restricción de Rendimiento de la constitución. Para repetir la medición sobre PostgreSQL, exporta `TEST_DATABASE_URL` antes de lanzar la prueba. La prueba falla si alguna medición supera su presupuesto, por lo que actúa como detección de regresiones.

---

## 9. Limpieza

```bash
# Volver a un estado limpio de pruebas (solo entorno local)
cd backend
python -m alembic downgrade 0002_work_queue
python -m alembic upgrade head
```

O restaurar el dump/seed de desarrollo habitual.

---

## 10. Criterios de éxito de la validación

- [ ] `alembic current` muestra `0003_ticket_timeline`.
- [ ] La matriz 5×5 está cubierta y solo las transiciones permitidas se aplican.
- [ ] Resolver sin texto devuelve `422` y no modifica nada.
- [ ] Resolver con texto crea `status_change` + `resolution`.
- [ ] Cerrar conserva la resolución y `closed_at`.
- [ ] Reabrir `resuelto → en_progreso` limpia `finalized_at` y conserva la resolución anterior.
- [ ] El usuario creador nunca recibe entradas internas.
- [ ] Un ticket cerrado admite comentarios internos.
- [ ] Un doble envío no duplica entradas.
- [ ] Reutilizar un `request_id` con otro destino, resolución o autor devuelve `409 request_id_reused` sin escribir.
- [ ] Un `expected_updated_at` obsoleto devuelve `409` sin escribir.
- [ ] La UI bloquea el envío de «Resuelto» sin texto.
- [ ] Un ticket inexistente devuelve `404 ticket_not_found` antes que `403 forbidden` para roles no técnicos.
- [ ] La prueba de rendimiento mantiene el p95 de workflow, timeline y status-transitions por debajo de 300 ms, y la transición con refresco por debajo de 2 s.
