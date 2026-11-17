# Quickstart — Validación de HU-08

**Feature**: `008-configuracion-plazos-sla` | **Date**: 2026-11-15

Guía ejecutable para demostrar de extremo a extremo que la configuración de categorías, prioridades y plazos SLA funciona, que solo el rol `admin` accede y que los cambios no son retroactivos. No contiene la implementación; solo pasos de validación.

**Contratos de referencia**: [`contracts/admin-configuration.openapi.yaml`](./contracts/admin-configuration.openapi.yaml) para la API HTTP y [`contracts/frontend-components.md`](./contracts/frontend-components.md) para los componentes Vue.

---

## 1. Prerrequisitos

- Python 3.12 con el entorno `backend/.venv` provisionado.
- PostgreSQL 16 accesible en `DATABASE_URL` (por defecto `postgresql+psycopg://ticketing:ticketing@localhost:5432/ticketing`).
- Node.js + dependencias de `frontend/node_modules`.
- Variables de entorno del backend:
  - `DATABASE_URL`
  - `JWT_SECRET`
  - `AUTH_DEV_STUB_ENABLED=true` (solo desarrollo local)
  - `AUTH_ISSUER`, `AUTH_AUDIENCE`
- Datos de seed con:
  - `admin@example.com` (rol `admin`),
  - `tecnico.a@example.com` (rol `tecnico`),
  - `supervisor@example.com` (rol `supervisor`),
  - `usuario@example.com` (rol `usuario`),
  - categorías `Red`, `Hardware`, `Software`, `Otros` (default) y `Sin clasificar` (sistema),
  - prioridades `Crítica` (4 h), `Alta` (8 h), `Media` (24 h, default), `Baja` (72 h) y `Sin clasificar` (sistema).

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
python scripts/seed_dev.py
```

**Esperado**:

- `alembic current` muestra `0006_sla_configuration (head)`.
- Existen `configuration_versions`, `sla_rules` y `configuration_audit_entries`.
- `tickets` tiene `sla_priority_level`, `sla_hours_applied` y `sla_config_version_id`.
- La migración insertó la versión base `v1`.
- El seed informa de la creación del usuario de administración.

Verificación rápida en PostgreSQL:

```bash
docker compose exec db psql -U ticketing -d ticketing
```

```sql
\d configuration_versions
\d sla_rules
\d configuration_audit_entries
\d tickets

SELECT version, created_at, note FROM configuration_versions ORDER BY version;
SELECT id, name, is_default FROM categories ORDER BY sort_order;
SELECT id, name, level, base_hours, is_default FROM priorities ORDER BY level;
```

**Esperado**:

- Una fila en `configuration_versions` con `version = 1`.
- Una categoría default (`Otros`) y una prioridad default (`Media`).
- Los tickets existentes tienen `sla_priority_level` relleno y `sla_config_version_id = NULL` (legado). El escenario de «conservar la versión anterior» aplica a tickets creados desde `v1`; los legados conservan plazo y nivel, pero no una versión fiable.

---

## 3. Pruebas automatizadas

### 3.1. Backend funcional (SQLite)

```bash
cd backend
python -m pytest tests/unit/test_sla_resolution.py -q
python -m pytest tests/integration/test_admin_authorization.py -q
python -m pytest tests/integration/test_admin_categories.py -q
python -m pytest tests/integration/test_admin_priorities.py -q
python -m pytest tests/integration/test_admin_sla_matrix.py -q
python -m pytest tests/integration/test_sla_non_retroactivity.py -q
python -m pytest tests/integration/test_configuration_history.py -q
python -m pytest tests/contract/test_admin_configuration_contract.py -q
```

**Esperado**:

| Suite | Resultado |
|---|---|
| Resolución de SLA | Regla prevalece sobre base; fallback correcto; decimales y errores |
| Autorización | Solo `admin`; `401` sin token; `403` para usuario, técnico y supervisor |
| Categorías | Alta, edición, duplicados normalizados, default, desactivación, borrado e idempotencia |
| Prioridades | Nivel 1–4 único entre activas, color, plazo base, default e idempotencia |
| Matriz | Alta, cambio versionado, sustitución/retirada, duplicados, lote atómico e idempotencia |
| No retroactividad | Tickets abiertos/cerrados conservan límite, outcome, nivel y snapshot visible |
| Histórico | Append-only, autor, valores previos/nuevos y filtros por `configuration_version_id` |
| Contrato | Campos y códigos coinciden con el OpenAPI |

### 3.2. Concurrencia real (PostgreSQL)

```bash
cd backend
export TEST_DATABASE_URL='postgresql+psycopg://ticketing:ticketing@localhost:5432/ticketing_test'
python -m pytest tests/integration/test_admin_concurrency.py -q
```

**Esperado**:

- Dos actualizaciones simultáneas de la misma categoría: una confirma y la otra recibe `409 stale_configuration`.
- Dos lotes simultáneos sobre la misma celda: solo uno crea versión.
- Reintentar un lote ya aplicado no duplica versión, reglas ni auditoría.
- Creación de ticket concurrente con cambio de regla: el ticket obtiene una versión coherente.

### 3.3. Rendimiento (PostgreSQL)

```bash
cd backend
export TEST_DATABASE_URL='postgresql+psycopg://ticketing:ticketing@localhost:5432/ticketing_test'
python -m pytest tests/integration/test_admin_configuration_performance.py -q
```

**Esperado**: p95 < 300 ms en lecturas e histórico, p95 < 400 ms en lote de 20 celdas e incremento < 10 ms en el alta de ticket.

### 3.4. Frontend

```bash
cd frontend
npm run test -- --run
npm run build
```

**Esperado**: pasan las pruebas de diálogos, matriz, histórico, banner de conflicto y `axe-core` de la página; `vue-tsc` no reporta errores.

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

ADMIN=$(curl -s -X POST "$BASE/dev/login" \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@example.com"}' | jq -r .access_token)

TECNICO=$(curl -s -X POST "$BASE/dev/login" \
  -H 'Content-Type: application/json' \
  -d '{"email":"tecnico.a@example.com"}' | jq -r .access_token)

SUPERVISOR=$(curl -s -X POST "$BASE/dev/login" \
  -H 'Content-Type: application/json' \
  -d '{"email":"supervisor@example.com"}' | jq -r .access_token)
```

> `jq` es opcional; puedes copiar el `access_token` manualmente.

### 5.2. Solo administración

```bash
curl -s -o /tmp/admin_tecnico.json -w '%{http_code}\n' \
  "$BASE/admin/categories" -H "Authorization: Bearer $TECNICO"

curl -s -o /tmp/admin_supervisor.json -w '%{http_code}\n' \
  "$BASE/admin/priorities" -H "Authorization: Bearer $SUPERVISOR"

cat /tmp/admin_tecnico.json | jq
cat /tmp/admin_supervisor.json | jq
```

**Esperado**:

- HTTP `403` en ambos casos.
- `detail.code = "forbidden"`.
- Ninguna respuesta contiene categorías, prioridades, reglas ni histórico.

```bash
curl -s "$BASE/admin/categories" \
  -H "Authorization: Bearer $ADMIN" | jq
```

**Esperado**: HTTP `200`, incluidas inactivas y `Sin clasificar` con `is_system: true`.

### 5.3. Crear y editar una categoría

```bash
CATEGORY=$(curl -s -X POST "$BASE/admin/categories" \
  -H "Authorization: Bearer $ADMIN" \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "Telefonía",
    "description": "Averías de telefonía fija y móvil.",
    "keywords": ["teléfono", "móvil", "extensión"],
    "sort_order": 40
  }')

echo "$CATEGORY" | jq
CATEGORY_ID=$(echo "$CATEGORY" | jq -r .id)
REVISION=$(echo "$CATEGORY" | jq -r .revision)
```

**Esperado**:

- HTTP `201`.
- `is_active: true`, `is_default: false`, `is_system: false`.
- `ticket_count: 0`, `rule_count: 0`, `can_delete: true`.

Duplicado normalizado:

```bash
curl -s -o /tmp/dup.json -w '%{http_code}\n' \
  -X POST "$BASE/admin/categories" \
  -H "Authorization: Bearer $ADMIN" \
  -H 'Content-Type: application/json' \
  -d '{"name":"  telefonía  "}'

cat /tmp/dup.json | jq
```

**Esperado**: HTTP `409`, `detail.code = "duplicate_catalog_name"`.

Edición con revisión:

```bash
curl -s -X POST "$BASE/admin/categories/$CATEGORY_ID/updates" \
  -H "Authorization: Bearer $ADMIN" \
  -H 'Content-Type: application/json' \
  -d "{
    \"expected_revision\": $REVISION,
    \"name\": \"Telefonía y voz\",
    \"description\": \"Averías de telefonía fija, móvil y centralita.\"
  }" | jq
```

**Esperado**: `revision` incrementada y cambio registrado en el histórico.

Repetir la misma petición con `expected_revision` antiguo:

```bash
curl -s -o /tmp/stale.json -w '%{http_code}\n' \
  -X POST "$BASE/admin/categories/$CATEGORY_ID/updates" \
  -H "Authorization: Bearer $ADMIN" \
  -H 'Content-Type: application/json' \
  -d "{
    \"expected_revision\": $REVISION,
    \"name\": \"Otro nombre\"
  }"

cat /tmp/stale.json | jq
```

**Esperado**: HTTP `409`, `detail.code = "stale_configuration"`, sin cambios.

### 5.4. Crear una prioridad y validar el nivel único

Los cuatro niveles están ocupados por prioridades no-sistema activas. Para crear `Planificada` se libera temporalmente el nivel 4 desactivando `Baja`:

```bash
BAJA_ID=$(curl -s "$BASE/admin/priorities" \
  -H "Authorization: Bearer $ADMIN" | jq -r '.[] | select(.name=="Baja") | .id')

BAJA_REV=$(curl -s "$BASE/admin/priorities" \
  -H "Authorization: Bearer $ADMIN" \
  | jq -r --arg id "$BAJA_ID" '.[] | select(.id==$id) | .revision')

curl -s -X POST "$BASE/admin/priorities/$BAJA_ID/updates" \
  -H "Authorization: Bearer $ADMIN" \
  -H 'Content-Type: application/json' \
  -d "{\"expected_revision\":$BAJA_REV,\"is_active\":false}" | jq
```

**Esperado**: `Baja` queda inactiva y su nivel 4 deja de estar reservado.

```bash
PRIORITY=$(curl -s -X POST "$BASE/admin/priorities" \
  -H "Authorization: Bearer $ADMIN" \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "Planificada",
    "level": 4,
    "color": "#0ea5e9",
    "base_hours": "48.00",
    "keywords": ["planificado", "mantenimiento"],
    "sort_order": 40
  }')

echo "$PRIORITY" | jq
```

**Esperado**: HTTP `201`, `base_hours: "48.00"`, `is_default: false`.

Nivel duplicado:

```bash
curl -s -o /tmp/level.json -w '%{http_code}\n' \
  -X POST "$BASE/admin/priorities" \
  -H "Authorization: Bearer $ADMIN" \
  -H 'Content-Type: application/json' \
  -d '{"name":"Otra crítica","level":4,"base_hours":"10.00"}'

cat /tmp/level.json | jq
```

**Esperado**: HTTP `409`, `detail.code = "duplicate_priority_level"`.

Plazo base inválido:

```bash
curl -s -o /tmp/hours.json -w '%{http_code}\n' \
  -X POST "$BASE/admin/priorities" \
  -H "Authorization: Bearer $ADMIN" \
  -H 'Content-Type: application/json' \
  -d '{"name":"Inválida","level":4,"base_hours":"0"}'

cat /tmp/hours.json | jq
```

**Esperado**: HTTP `422`, mensaje de validación; no se crea la prioridad.

Limpieza de la prueba: se elimina `Planificada` y se reactiva `Baja` en el nivel 4 para continuar con el catálogo inicial.

```bash
PRIORITY_ID=$(echo "$PRIORITY" | jq -r .id)
PRIORITY_REV=$(curl -s "$BASE/admin/priorities" \
  -H "Authorization: Bearer $ADMIN" \
  | jq -r --arg id "$PRIORITY_ID" '.[] | select(.id==$id) | .revision')

curl -s -X POST "$BASE/admin/priorities/$PRIORITY_ID/deletion" \
  -H "Authorization: Bearer $ADMIN" \
  -H 'Content-Type: application/json' \
  -d "{\"expected_revision\":$PRIORITY_REV}" | jq

BAJA_REV=$(curl -s "$BASE/admin/priorities" \
  -H "Authorization: Bearer $ADMIN" \
  | jq -r --arg id "$BAJA_ID" '.[] | select(.id==$id) | .revision')

curl -s -X POST "$BASE/admin/priorities/$BAJA_ID/updates" \
  -H "Authorization: Bearer $ADMIN" \
  -H 'Content-Type: application/json' \
  -d "{\"expected_revision\":$BAJA_REV,\"is_active\":true,\"level\":4}" | jq
```

### 5.5. Configurar la matriz SLA

Obtén los identificadores de `Red` y `Alta`:

```bash
RED_ID=$(curl -s "$BASE/admin/categories" \
  -H "Authorization: Bearer $ADMIN" | jq -r '.[] | select(.name=="Red") | .id')
ALTA_ID=$(curl -s "$BASE/admin/priorities" \
  -H "Authorization: Bearer $ADMIN" | jq -r '.[] | select(.name=="Alta") | .id')

MATRIX=$(curl -s "$BASE/admin/sla-rules" \
  -H "Authorization: Bearer $ADMIN")
echo "$MATRIX" | jq
```

**Esperado**:

- `configuration_version.version` igual a la versión vigente.
- `items` vacío o con reglas existentes.
- `combinations.categories` y `combinations.priorities` con las entidades activas.

Crear la regla `Red × Alta = 6 h`:

```bash
curl -s -X POST "$BASE/admin/sla-rules/batch" \
  -H "Authorization: Bearer $ADMIN" \
  -H 'Content-Type: application/json' \
  -d "{
    \"changes\": [{
      \"operation\": \"upsert\",
      \"category_id\": \"$RED_ID\",
      \"priority_id\": \"$ALTA_ID\",
      \"hours\": \"6.00\",
      \"expected_rule_id\": null
    }]
  }" | jq
```

**Esperado**:

- HTTP `200`.
- `configuration_version.version` incrementada.
- Un `item` con `hours: "6.00"` y `valid_from_version` igual a la nueva versión.

Duplicar la regla vigente sin retirar la anterior:

```bash
curl -s -o /tmp/rule_dup.json -w '%{http_code}\n' \
  -X POST "$BASE/admin/sla-rules/batch" \
  -H "Authorization: Bearer $ADMIN" \
  -H 'Content-Type: application/json' \
  -d "{
    \"changes\": [{
      \"operation\": \"upsert\",
      \"category_id\": \"$RED_ID\",
      \"priority_id\": \"$ALTA_ID\",
      \"hours\": \"7.00\",
      \"expected_rule_id\": null
    }]
  }"

cat /tmp/rule_dup.json | jq
```

**Esperado**: HTTP `409`, `detail.code = "duplicate_sla_rule"` o `stale_configuration`, sin crear regla.

### 5.6. Crear un ticket y comprobar el plazo aplicado

```bash
curl -s -X POST "$BASE/tickets" \
  -H "Authorization: Bearer $TECNICO" \
  -F 'title=No funciona la VPN en la oficina' \
  -F 'description=Desde esta mañana no puedo conectar por VPN ni por wifi. Afecta a toda la oficina.' \
  -F "priority_id=$ALTA_ID" | jq
```

**Esperado**:

- Ticket creado con categoría `Red` (sugerida por palabras clave) y prioridad `Alta`.
- `TicketRead` incluye `sla_priority_level`, `sla_hours_applied`, `sla_version` y `sla_config_version_id`.
- `sla_deadline` se comprueba en SQL.

```sql
SELECT number, category_id, priority_id, created_at, sla_deadline,
       sla_priority_level, sla_hours_applied, sla_version, sla_config_version_id
FROM tickets
WHERE number = 'TK-000XXX';
```

**Esperado**:

- `sla_priority_level = 2` (Alta).
- `sla_hours_applied = 6.00`.
- `sla_deadline = created_at + interval '6 hours'`.
- `sla_version` con la etiqueta de la versión usada.
- `sla_config_version_id` no nulo.

### 5.7. Verificar la no retroactividad

Guarda el ticket anterior como `OLD_TICKET` y su `sla_deadline`.

Cambia la regla a 12 h usando el `rule_id` vigente:

```bash
RULE_ID=$(curl -s "$BASE/admin/sla-rules" \
  -H "Authorization: Bearer $ADMIN" \
  | jq -r --arg c "$RED_ID" --arg p "$ALTA_ID" \
    '.items[] | select(.category.id==$c and .priority.id==$p) | .id')

curl -s -X POST "$BASE/admin/sla-rules/batch" \
  -H "Authorization: Bearer $ADMIN" \
  -H 'Content-Type: application/json' \
  -d "{
    \"changes\": [{
      \"operation\": \"upsert\",
      \"category_id\": \"$RED_ID\",
      \"priority_id\": \"$ALTA_ID\",
      \"hours\": \"12.00\",
      \"expected_rule_id\": \"$RULE_ID\"
    }]
  }" | jq
```

Comprueba que el ticket antiguo no cambió:

```sql
SELECT number, sla_deadline, sla_hours_applied, sla_version
FROM tickets
WHERE number = 'TK-000XXX';
```

**Esperado**: mismos valores que antes del cambio.

Crea un ticket nuevo con texto distinto pero palabras clave de Red:

```bash
curl -s -X POST "$BASE/tickets" \
  -H "Authorization: Bearer $TECNICO" \
  -F 'title=Incidencia de red en el aula 3' \
  -F 'description=La conexión wifi y el acceso por VPN fallan de forma intermitente desde primera hora.' \
  -F "priority_id=$ALTA_ID" | jq
```

**Esperado**: el ticket nuevo tiene `sla_hours_applied = 12.00` y `sla_deadline = created_at + 12 hours`; el antiguo sigue con 6 h.

### 5.8. Verificar la urgencia congelada

Anota el orden de la cola del técnico:

```bash
curl -s "$BASE/me/work-queue" \
  -H "Authorization: Bearer $TECNICO" | jq '.items[] | {number, priority}'
```

Los cuatro niveles 1–4 están ocupados. Para intercambiar `Alta` (2) y `Baja` (4), se desactiva temporalmente `Baja`, se mueve `Alta` al nivel 4 y se reactiva `Baja` con el nivel 2 liberado:

```bash
BAJA_ID=$(curl -s "$BASE/admin/priorities" \
  -H "Authorization: Bearer $ADMIN" | jq -r '.[] | select(.name=="Baja") | .id')

BAJA_REV=$(curl -s "$BASE/admin/priorities" \
  -H "Authorization: Bearer $ADMIN" \
  | jq -r --arg id "$BAJA_ID" '.[] | select(.id==$id) | .revision')

# 1. Desactivar Baja (libera el nivel 4)
curl -s -X POST "$BASE/admin/priorities/$BAJA_ID/updates" \
  -H "Authorization: Bearer $ADMIN" \
  -H 'Content-Type: application/json' \
  -d "{\"expected_revision\":$BAJA_REV,\"is_active\":false}" | jq

# 2. Mover Alta del nivel 2 al 4
ALTA_REV=$(curl -s "$BASE/admin/priorities" \
  -H "Authorization: Bearer $ADMIN" \
  | jq -r --arg id "$ALTA_ID" '.[] | select(.id==$id) | .revision')

curl -s -X POST "$BASE/admin/priorities/$ALTA_ID/updates" \
  -H "Authorization: Bearer $ADMIN" \
  -H 'Content-Type: application/json' \
  -d "{\"expected_revision\":$ALTA_REV,\"level\":4}" | jq

# 3. Reactivar Baja con el nivel 2 liberado
BAJA_REV=$(curl -s "$BASE/admin/priorities" \
  -H "Authorization: Bearer $ADMIN" \
  | jq -r --arg id "$BAJA_ID" '.[] | select(.id==$id) | .revision')

curl -s -X POST "$BASE/admin/priorities/$BAJA_ID/updates" \
  -H "Authorization: Bearer $ADMIN" \
  -H 'Content-Type: application/json' \
  -d "{\"expected_revision\":$BAJA_REV,\"is_active\":true,\"level\":2}" | jq
```

Vuelve a leer la cola:

```bash
curl -s "$BASE/me/work-queue" \
  -H "Authorization: Bearer $TECNICO" | jq '.items[] | {number, priority}'
```

**Esperado**:

- Los tickets existentes de `Alta` conservan `priority.level: 2` congelado en la cola, aunque la prioridad `Alta` ahora tenga nivel 4.
- Los tickets existentes de `Baja` conservan el nivel 4 congelado.
- Los tickets nuevos creados después del intercambio usan el nivel actual (Alta = 4, Baja = 2).
- La posición relativa de los tickets históricos no cambia.

Para dejar el catálogo como estaba, repite la secuencia invertida (desactivar `Baja`, devolver `Alta` al nivel 2, reactivar `Baja` con nivel 4) o ejecuta la limpieza del apartado 9.

### 5.9. Conflicto de versión y recarga

En dos pestañas del navegador o con dos peticiones:

```bash
REV=$(curl -s "$BASE/admin/categories" \
  -H "Authorization: Bearer $ADMIN" \
  | jq -r --arg id "$CATEGORY_ID" '.[] | select(.id==$id) | .revision')

# Petición A
curl -s -X POST "$BASE/admin/categories/$CATEGORY_ID/updates" \
  -H "Authorization: Bearer $ADMIN" \
  -H 'Content-Type: application/json' \
  -d "{\"expected_revision\":$REV,\"description\":\"Cambio A\"}" | jq

# Petición B, con la misma revisión
curl -s -o /tmp/conflict.json -w '%{http_code}\n' \
  -X POST "$BASE/admin/categories/$CATEGORY_ID/updates" \
  -H "Authorization: Bearer $ADMIN" \
  -H 'Content-Type: application/json' \
  -d "{\"expected_revision\":$REV,\"description\":\"Cambio B\"}"

cat /tmp/conflict.json | jq
```

**Esperado**: A guarda; B recibe `409 stale_configuration`; el valor final es el de A.

En la UI, el diálogo de B muestra el banner de conflicto y «Recargar configuración» conserva los datos escritos hasta que el usuario decide.

### 5.10. Lote atómico

Obtén la regla vigente actual de `Red × Alta` y el identificador de `Media`:

```bash
CURRENT_RULE_ID=$(curl -s "$BASE/admin/sla-rules" \
  -H "Authorization: Bearer $ADMIN" \
  | jq -r --arg c "$RED_ID" --arg p "$ALTA_ID" \
    '.items[] | select(.category.id==$c and .priority.id==$p) | .id')

MEDIA_ID=$(curl -s "$BASE/admin/priorities" \
  -H "Authorization: Bearer $ADMIN" | jq -r '.[] | select(.name=="Media") | .id')
```

Intenta un lote con una celda válida y otra con plazo cero:

```bash
curl -s -o /tmp/batch.json -w '%{http_code}\n' \
  -X POST "$BASE/admin/sla-rules/batch" \
  -H "Authorization: Bearer $ADMIN" \
  -H 'Content-Type: application/json' \
  -d "{
    \"changes\": [
      {
        \"operation\": \"upsert\",
        \"category_id\": \"$RED_ID\",
        \"priority_id\": \"$ALTA_ID\",
        \"hours\": \"10.00\",
        \"expected_rule_id\": \"$CURRENT_RULE_ID\"
      },
      {
        \"operation\": \"upsert\",
        \"category_id\": \"$RED_ID\",
        \"priority_id\": \"$MEDIA_ID\",
        \"hours\": \"0.00\",
        \"expected_rule_id\": null
      }
    ]
  }"

cat /tmp/batch.json | jq
```

**Esperado**: HTTP `422`; no se crea versión ni se modifica la regla de `Red × Alta`. El lote es todo o nada.

### 5.11. Histórico

```bash
curl -s "$BASE/admin/config-history?page=1&page_size=10" \
  -H "Authorization: Bearer $ADMIN" | jq
```

**Esperado**:

- Entradas con autor, fecha, entidad, acción, valores anteriores/nuevos y versión.
- Orden descendente por fecha.
- Paginación coherente.

Filtro por entidad:

```bash
curl -s "$BASE/admin/config-history?entity_type=category&entity_id=$CATEGORY_ID" \
  -H "Authorization: Bearer $ADMIN" | jq
```

**Esperado**: solo cambios de la categoría creada.

Filtro por versión de configuración:

```bash
VERSION_ID=$(curl -s "$BASE/admin/config-history?page=1&page_size=1" \
  -H "Authorization: Bearer $ADMIN" | jq -r '.items[0].configuration_version.id')

curl -s "$BASE/admin/config-history?configuration_version_id=$VERSION_ID" \
  -H "Authorization: Bearer $ADMIN" | jq
```

**Esperado**: solo entradas de esa versión.

Intento de modificar el histórico (no existe endpoint de escritura):

```bash
curl -s -o /tmp/history_write.json -w '%{http_code}\n' \
  -X POST "$BASE/admin/config-history" \
  -H "Authorization: Bearer $ADMIN" \
  -H 'Content-Type: application/json' \
  -d '{}'
```

**Esperado**: HTTP `405` o `404`; el histórico es de solo lectura.

### 5.12. Retirar una regla y volver al plazo base

```bash
CURRENT_RULE_ID=$(curl -s "$BASE/admin/sla-rules" \
  -H "Authorization: Bearer $ADMIN" \
  | jq -r --arg c "$RED_ID" --arg p "$ALTA_ID" \
    '.items[] | select(.category.id==$c and .priority.id==$p) | .id')

curl -s -X POST "$BASE/admin/sla-rules/$CURRENT_RULE_ID/retirement" \
  -H "Authorization: Bearer $ADMIN" \
  -H 'Content-Type: application/json' \
  -d "{\"expected_rule_id\":\"$CURRENT_RULE_ID\"}" | jq
```

**Esperado**:

- La regla deja de estar en `items`.
- La versión incrementa.
- Un ticket nuevo de `Red × Alta` usa `base_hours` de Alta.
- Los tickets anteriores conservan su plazo.

---

## 6. Validación manual de la interfaz

Abre `http://localhost:5173/login` y entra como `admin@example.com`.

| # | Escenario | Resultado esperado |
|---|---|---|
| 1 | Login como admin | Redirige a `/admin/configuracion` |
| 2 | Login como técnico y visita `/admin/configuracion` | Redirige a login o a la cola; no se muestran datos de configuración |
| 3 | Pestaña Categorías | Tabla con activas, inactivas y sistema; badge «Sistema» en `Sin clasificar` |
| 4 | Crear categoría con nombre duplicado | Mensaje de conflicto bajo el campo; no se crea |
| 5 | Editar categoría | Se actualiza la tabla y el número de revisión |
| 6 | Desactivar la categoría default | El diálogo exige seleccionar reemplazo |
| 7 | Intentar borrar una categoría con tickets | Botón deshabilitado con motivo; si se fuerza, banner `catalog_in_use` |
| 8 | Pestaña Prioridades | Nivel, color, plazo base, default y contadores |
| 9 | Crear prioridad con nivel duplicado | Error `duplicate_priority_level` |
| 10 | Pestaña Matriz SLA | Filas categorías, columnas prioridades, celdas con regla o «Base: X h» |
| 11 | Editar dos celdas y guardar | Una sola versión nueva; tabla actualizada |
| 12 | Lote con un error | No se guarda ninguna celda; banner de error |
| 13 | Dos pestañas editan la misma celda | La segunda recibe banner de conflicto y opción de recarga |
| 14 | Pestaña Histórico | Filtros, fechas es-ES/Europe/Madrid, autor y valores |
| 15 | Solo teclado | Pestañas, diálogos y matriz navegables con foco visible |
| 16 | Ventana < 640 px | Tablas con scroll horizontal; acciones accesibles |

---

## 7. Comprobaciones SQL

```sql
-- Versiones de configuración en orden
SELECT version, created_at, created_by_id, note
FROM configuration_versions
ORDER BY version;

-- Reglas vigentes: debe haber como máximo una por combinación
SELECT category_id, priority_id, COUNT(*) AS current_rules
FROM sla_rules
WHERE valid_to_version IS NULL
GROUP BY category_id, priority_id
HAVING COUNT(*) > 1;

-- Reglas históricas coherentes
SELECT id, category_id, priority_id, hours, valid_from_version, valid_to_version
FROM sla_rules
WHERE valid_to_version IS NOT NULL
  AND valid_to_version <= valid_from_version;

-- Tickets con snapshot completo creados después de la migración
SELECT id, number, sla_deadline, sla_priority_level, sla_hours_applied,
       sla_config_version_id, sla_version
FROM tickets
WHERE created_at >= (SELECT MIN(created_at) FROM configuration_versions)
  AND (sla_deadline IS NOT NULL)
  AND (sla_priority_level IS NULL
       OR sla_hours_applied IS NULL
       OR sla_config_version_id IS NULL);

-- Tickets con plazo incoherente
SELECT id, number, created_at, sla_deadline, sla_hours_applied
FROM tickets
WHERE sla_deadline IS NOT NULL
  AND sla_deadline <= created_at;

-- Niveles de urgencia fuera de rango
SELECT id, number, sla_priority_level
FROM tickets
WHERE sla_priority_level IS NOT NULL
  AND sla_priority_level NOT BETWEEN 1 AND 4;

-- No debe haber más de un default por catálogo
SELECT 'category' AS kind, COUNT(*) FROM categories WHERE is_default = true
UNION ALL
SELECT 'priority', COUNT(*) FROM priorities WHERE is_default = true;
```

**Esperado**:

- La segunda consulta devuelve 0 filas.
- La tercera devuelve 0 filas.
- La cuarta devuelve 0 filas.
- La quinta devuelve 0 filas.
- La sexta devuelve 0 filas.
- La séptima devuelve exactamente 1 categoría y 1 prioridad.

---

## 8. Rendimiento y regresión

```bash
cd backend
python -m pytest tests/integration/test_sla_non_retroactivity.py -q -s
python -m pytest tests/integration/test_admin_configuration_performance.py -q -s
```

**Presupuestos**:

| Medición | Presupuesto |
|---|---|
| `GET /admin/categories` | p95 < 300 ms |
| `GET /admin/sla-rules` | p95 < 300 ms |
| `POST /admin/sla-rules/batch` (20 celdas) | p95 < 400 ms |
| Creación de ticket con resolución de SLA | incremento < 10 ms sobre el flujo actual |
| `GET /admin/config-history` (25 elementos) | p95 < 300 ms |

La prueba debe fallar si se supera un presupuesto, para detectar regresiones.

---

## 9. Limpieza

```bash
# Volver a un estado limpio de pruebas (solo entorno local)
cd backend
python -m alembic downgrade 0005_ticket_information
python -m alembic upgrade head
python scripts/seed_dev.py
```

O restaurar el dump/seed de desarrollo habitual.

---

## 10. Criterios de éxito de la validación

1. Solo `admin` puede consultar o modificar la configuración y el histórico.
2. Un cambio de regla no altera ningún ticket existente, abierto o cerrado.
3. Un ticket nuevo usa la versión vigente en el instante de su creación.
4. Cambiar el nivel de una prioridad no reordena tickets históricos.
5. La matriz no admite dos reglas vigentes para la misma combinación.
6. Un lote inválido no deja cambios parciales ni crea versión.
7. Dos administradores concurrentes no pierden cambios silenciosamente.
8. Cada cambio aparece en el histórico con autor, fecha, valores anteriores y nuevos.
9. Desactivar una categoría o prioridad no rompe tickets existentes.
10. La interfaz es usable con teclado, lector de pantalla y ventana estrecha.
