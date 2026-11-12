# Data Model: Creación de tickets de incidencia

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Fecha**: 2026-11-12

Motor de producción: PostgreSQL 16. Convenciones: tablas y columnas en
`snake_case`, claves primarias `UUID`, fechas `TIMESTAMPTZ` en UTC y texto
UTF-8. SQLite se usa en las pruebas unitarias e integrales; la lógica de
numeración y concurrencia se valida además contra PostgreSQL.

## Diagrama de relaciones

```text
users 1 ──── * tickets * ──── 1 categories
                │  │
                │  └──────── 1 priorities
                │
                ├──── * attachments
                └──── * ticket_timeline_entries ──── 1 users (author)

categories / priorities: keywords JSON para la sugerencia
```

La autenticación vive fuera de esta funcionalidad. La identidad se resuelve
del JWT `Authorization: Bearer <token>` (`sub` = UUID del usuario) y se valida
que el usuario exista y esté activo.

## Tablas

### `users`

Usuario del sistema (solicitante, técnico, supervisor o administrador).

| Columna | Tipo | Restricciones |
|---------|------|---------------|
| `id` | `UUID` | PK |
| `name` | `VARCHAR(150)` | NOT NULL |
| `email` | `VARCHAR(255)` | NOT NULL, UNIQUE |
| `role` | `user_role` | NOT NULL (`usuario`, `tecnico`, `supervisor`, `admin`) |
| `team` | `VARCHAR(100)` | NULL |
| `is_active` | `BOOLEAN` | NOT NULL, DEFAULT TRUE |

### `categories`

Catálogo configurable. En esta historia solo se siembra; no hay CRUD.

| Columna | Tipo | Restricciones |
|---------|------|---------------|
| `id` | `UUID` | PK |
| `name` | `VARCHAR(100)` | NOT NULL |
| `description` | `TEXT` | NULL |
| `keywords` | `JSON` | NOT NULL, DEFAULT `[]` |
| `is_active` | `BOOLEAN` | NOT NULL, DEFAULT TRUE |
| `is_default` | `BOOLEAN` | NOT NULL, DEFAULT FALSE |
| `is_system` | `BOOLEAN` | NOT NULL, DEFAULT FALSE |
| `sort_order` | `INTEGER` | NOT NULL, DEFAULT 0 |

La fila de sistema **"Sin clasificar"** tiene `is_system = true`,
`is_active = true`, `is_default = false` y `keywords = []`. No participa en las
sugerencias ni en el listado normal; solo se usa como último fallback cuando no
queda ninguna categoría personalizada activa.

### `priorities`

| Columna | Tipo | Restricciones |
|---------|------|---------------|
| `id` | `UUID` | PK |
| `name` | `VARCHAR(50)` | NOT NULL |
| `level` | `SMALLINT` | NOT NULL, CHECK `level BETWEEN 1 AND 4` |
| `color` | `VARCHAR(7)` | NULL |
| `base_hours` | `NUMERIC(6,2)` | NULL |
| `keywords` | `JSON` | NOT NULL, DEFAULT `[]` |
| `is_active` | `BOOLEAN` | NOT NULL, DEFAULT TRUE |
| `is_default` | `BOOLEAN` | NOT NULL, DEFAULT FALSE |
| `is_system` | `BOOLEAN` | NOT NULL, DEFAULT FALSE |
| `sort_order` | `INTEGER` | NOT NULL, DEFAULT 0 |

La fila de sistema **"Sin clasificar"** comparte `level = 4` porque el CHECK
vigente solo admite 1–4, usa `color = '#64748b'` y `sort_order = 999` para
quedar al final. Al igual que la categoría de sistema, solo actúa como
fallback.

### `tickets`

| Columna | Tipo | Restricciones |
|---------|------|---------------|
| `id` | `UUID` | PK |
| `number` | `VARCHAR(20)` | NOT NULL, UNIQUE, formato `TK-%06d` |
| `title` | `VARCHAR(200)` | NOT NULL (la API valida 5–120 tras `strip()`) |
| `description` | `TEXT` | NULL (la API exige 20–5000 tras `strip()`) |
| `status` | `ticket_status` | NOT NULL (`abierto`, `en_progreso`, `pendiente_usuario`, `resuelto`, `cerrado`) |
| `priority_id` | `UUID` | NOT NULL, FK → `priorities(id)` |
| `category_id` | `UUID` | NULL, FK → `categories(id)` (la creación asigna siempre una) |
| `creator_id` | `UUID` | NOT NULL, FK → `users(id)` |
| `assignee_id` | `UUID` | NULL, FK → `users(id)` |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT `now()` |
| `sla_deadline` | `TIMESTAMPTZ` | NULL |
| `finalized_at` | `TIMESTAMPTZ` | NULL |
| `closed_at` | `TIMESTAMPTZ` | NULL |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT `now()` |
| `sla_version` | `VARCHAR(50)` | NULL |
| `content_hash` | `VARCHAR(64)` | NULL, SHA-256 hexadecimal |

Restricciones e índices relevantes:

- `UNIQUE (creator_id, content_hash)` → deduplicación por creador y contenido.
- `UNIQUE (number)`.
- `CHECK` que obliga a `finalized_at` no nulo solo en estados finales.
- `CHECK (finalized_at >= created_at)` y `CHECK (sla_deadline > created_at)`.
- Índices de la cola: `(assignee_id, status, sla_deadline)`,
  `(assignee_id, finalized_at)`, `(assignee_id, priority_id)`, `(number)`.

#### Numeración

En PostgreSQL el número se obtiene con
`nextval('ticket_number_seq')` y se formatea como `TK-%06d`. La secuencia se
crea en la migración `0004_ticket_creation` (`START 1 INCREMENT 1`); los huecos
son aceptables. En SQLite (pruebas) se usa `max(number) + 1`. La restricción
única de `number` y la de `(creator_id, content_hash)` protegen los envíos
concurrentes; el servicio recupera el ticket existente si otra transacción ganó
la carrera.

### `ticket_timeline_entries`

Historial append-only. La creación inserta una entrada `created`; las demás
transiciones pertenecen a historias posteriores.

| Columna | Tipo | Restricciones |
|---------|------|---------------|
| `id` | `UUID` | PK |
| `ticket_id` | `UUID` | NOT NULL, FK → `tickets(id)` ON DELETE CASCADE |
| `event_type` | `timeline_event_type` | NOT NULL (`created`, `status_change`, `resolution`, `internal_comment`) |
| `from_status` | `ticket_status` | NULL |
| `to_status` | `ticket_status` | NULL |
| `body` | `TEXT` | NULL (1–5000 si existe) |
| `is_internal` | `BOOLEAN` | NOT NULL, DEFAULT FALSE |
| `author_id` | `UUID` | NOT NULL, FK → `users(id)` |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT `now()` |
| `event_order` | `SMALLINT` | NOT NULL, DEFAULT 0, CHECK `IN (0, 1)` |
| `request_id` | `UUID` | NOT NULL |

Restricciones: `UNIQUE (ticket_id, request_id, event_type)` e índices
`(ticket_id, created_at)`, `(ticket_id, is_internal)` y `(author_id)`.

En la creación: `event_type = 'created'`, `from_status = NULL`,
`to_status = NULL`, `body = NULL`, `is_internal = false`, `event_order = 0`,
`author_id` = creador y `created_at` = `tickets.created_at`.

### `attachments`

| Columna | Tipo | Restricciones |
|---------|------|---------------|
| `id` | `UUID` | PK |
| `ticket_id` | `UUID` | NOT NULL, FK → `tickets(id)` ON DELETE CASCADE |
| `original_filename` | `VARCHAR(255)` | NOT NULL |
| `stored_filename` | `VARCHAR(255)` | NOT NULL, UNIQUE |
| `mime_type` | `VARCHAR(100)` | NOT NULL, CHECK en (`image/png`, `image/jpeg`, `image/gif`) |
| `size_bytes` | `BIGINT` | NOT NULL, CHECK `> 0` y `<= 5242880` |
| `relative_path` | `TEXT` | NOT NULL, UNIQUE |
| `sha256` | `CHAR(64)` | NOT NULL |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT `now()` |

Índice: `ix_attachments_ticket` sobre `(ticket_id)`.

`relative_path` es relativo a `ATTACHMENTS_DIR`, por ejemplo
`TK-000001/8f14e45f-....png`. Los archivos se escriben primero en
`ATTACHMENTS_DIR/tmp` y se mueven al directorio del ticket solo cuando la
transacción va a confirmarse.

## Reglas de validación

| Regla | Dónde se aplica |
|-------|-----------------|
| Título obligatorio, 5–120 caracteres tras `strip()` | FastAPI `Form` + servicio |
| Descripción obligatoria, 20–5000 caracteres tras `strip()` | FastAPI `Form` + servicio |
| Máximo 5 adjuntos | Servicio de adjuntos |
| Máximo 5 MB por adjunto | Servicio de adjuntos + CHECK en BD |
| Tipos permitidos: PNG, JPEG, GIF | Extensión + `Content-Type` declarado + firma binaria |
| Prioridad elegida existente, activa y no de sistema | Servicio de tickets |
| Categoría no la elige el cliente | Servicio de sugerencias/tickets |
| Duplicado: mismo `creator_id` + `content_hash` | Índice único + servicio |
| Adjuntos todo-o-nada | Transacción + limpieza de temporales |

## Hash de contenido

```text
content_hash = SHA-256( NFC(title.strip()) + "\n" + NFC(description.strip()) )
```

- Sensible a mayúsculas/minúsculas (el requisito habla del mismo título y
  descripción).
- No incluye categoría, prioridad ni adjuntos: dos envíos con el mismo texto
  son duplicados aunque cambien esos valores.
- Se calcula tras validar longitudes.

## Estados

Para esta historia el ticket nace en `abierto` (etiqueta «Abierto»). La columna
admite el ciclo completo para no migrar el esquema al añadir las transiciones
de historias posteriores.

```text
(nuevo) ──> abierto
```

## Datos de siembra

Script idempotente: `backend/scripts/seed_dev.py` (se ejecuta con
`python scripts/seed_dev.py` desde `backend` o dentro del contenedor).

Usuarios:

| Nombre | Email | Rol |
|--------|-------|-----|
| Técnico A | `tecnico.a@example.com` | `tecnico` |
| Técnico B | `tecnico.b@example.com` | `tecnico` |
| Técnico C | `tecnico.c@example.com` | `tecnico` |
| Técnico D | `tecnico.d@example.com` | `tecnico` |
| Supervisor | `supervisor@example.com` | `supervisor` |
| Solicitante | `usuario@example.com` | `usuario` |

Categorías activas (`is_system = false`):

| Nombre | `is_default` | Palabras clave |
|--------|--------------|----------------|
| Red | false | wifi, vpn, internet, red, conexión, proxy, dns |
| Hardware | false | portátil, ordenador, monitor, teclado, ratón, batería |
| Software | false | aplicación, programa, instalar, actualizar, error, correo |
| Otros | true | (sin palabras clave) |
| Sin clasificar | false (`is_system = true`) | (sin palabras clave) |

Prioridades activas (`is_system = false`):

| Nombre | Nivel | Color | `is_default` | Palabras clave |
|--------|-------|-------|--------------|----------------|
| Crítica | 1 | `#dc2626` | false | urgente, crítico, caído, no puedo trabajar, toda la oficina |
| Alta | 2 | `#ea580c` | false | importante, bloqueado, error grave, afecta a varios |
| Media | 3 | `#ca8a04` | true | (sin palabras clave) |
| Baja | 4 | `#16a34a` | false | leve, consulta, cuando pueda, no urgente |
| Sin clasificar | 4 | `#64748b` | false (`is_system = true`) | (sin palabras clave) |
