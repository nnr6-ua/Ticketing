# Data Model: Creación de tickets de incidencia

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Fecha**: 2026-10-29

Motor: PostgreSQL 16. Convenciones: `snake_case`, claves primarias `BIGSERIAL`, fechas `TIMESTAMPTZ` en UTC, texto UTF-8.

## Diagrama de relaciones

```text
employees 1 ──── * tickets * ──── 1 categories
                    │  │
                    │  └──────── 1 priorities
                    │
                    ├──── * attachments
                    └──── * ticket_events ──── 1 employees (author)

categories / priorities: keywords TEXT[] para sugerencia
```

## Tablas

### `employees`

Representa al empleado creador. Solo datos imprescindibles.

| Columna | Tipo | Restricciones |
|---------|------|---------------|
| `id` | `BIGSERIAL` | PK |
| `name` | `VARCHAR(120)` | NOT NULL |
| `email` | `VARCHAR(255)` | NOT NULL, UNIQUE |
| `is_active` | `BOOLEAN` | NOT NULL, DEFAULT TRUE |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT `now()` |

Índices: `UNIQUE (email)`.

> La autenticación no forma parte de esta funcionalidad. El empleado se resuelve desde la identidad provista por el entorno (`X-Employee-Id` en desarrollo, gateway de autenticación en producción).

### `categories`

Catálogo configurable por administración. En esta historia solo se siembra; no hay CRUD.

| Columna | Tipo | Restricciones |
|---------|------|---------------|
| `id` | `BIGSERIAL` | PK |
| `name` | `VARCHAR(80)` | NOT NULL, UNIQUE |
| `description` | `TEXT` | NULL |
| `keywords` | `TEXT[]` | NOT NULL, DEFAULT `'{}'` |
| `is_active` | `BOOLEAN` | NOT NULL, DEFAULT TRUE |
| `is_system` | `BOOLEAN` | NOT NULL, DEFAULT FALSE |
| `is_default` | `BOOLEAN` | NOT NULL, DEFAULT FALSE |
| `sort_order` | `INTEGER` | NOT NULL, DEFAULT 0 |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT `now()` |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT `now()` |

Restricciones:
- `CHECK (char_length(name) BETWEEN 1 AND 80)`.
- Índice único parcial para garantizar como máximo una categoría por defecto activa no sistema:
  `CREATE UNIQUE INDEX ux_categories_single_default ON categories (is_default) WHERE is_default AND is_active AND NOT is_system;`
- La fila de sistema "Sin clasificar" tiene `is_system = TRUE`, `is_active = TRUE`, `is_default = FALSE` y `keywords = '{}'`. No participa en sugerencias ni en la selección normal.

### `priorities`

Catálogo configurable. En esta historia solo se siembra.

| Columna | Tipo | Restricciones |
|---------|------|---------------|
| `id` | `BIGSERIAL` | PK |
| `name` | `VARCHAR(80)` | NOT NULL, UNIQUE |
| `level` | `SMALLINT` | NOT NULL, CHECK entre 1 y 5 (1 = más urgente) |
| `color` | `VARCHAR(7)` | NOT NULL, DEFAULT `'#64748b'`, CHECK formato `#RRGGBB` |
| `keywords` | `TEXT[]` | NOT NULL, DEFAULT `'{}'` |
| `is_active` | `BOOLEAN` | NOT NULL, DEFAULT TRUE |
| `is_system` | `BOOLEAN` | NOT NULL, DEFAULT FALSE |
| `is_default` | `BOOLEAN` | NOT NULL, DEFAULT FALSE |
| `sort_order` | `INTEGER` | NOT NULL, DEFAULT 0 |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT `now()` |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT `now()` |

Restricciones:
- `CHECK (char_length(name) BETWEEN 1 AND 80)`.
- `CHECK (level BETWEEN 1 AND 5)`.
- `CHECK (color ~ '^#[0-9A-Fa-f]{6}$')`.
- Índice único parcial análogo a categorías para una sola prioridad por defecto activa no sistema:
  `CREATE UNIQUE INDEX ux_priorities_single_default ON priorities (is_default) WHERE is_default AND is_active AND NOT is_system;`
- La fila de sistema "Sin clasificar" tiene `is_system = TRUE`, `level = 5`, `is_default = FALSE` y `keywords = '{}'`.

### `tickets`

| Columna | Tipo | Restricciones |
|---------|------|---------------|
| `id` | `BIGSERIAL` | PK |
| `ticket_number` | `VARCHAR(20)` | NOT NULL, UNIQUE |
| `title` | `VARCHAR(120)` | NOT NULL, CHECK longitud 5–120 |
| `description` | `TEXT` | NOT NULL, CHECK longitud 20–5000 |
| `content_hash` | `CHAR(64)` | NOT NULL (SHA-256 hexadecimal) |
| `status` | `VARCHAR(30)` | NOT NULL, DEFAULT `'Abierto'`, CHECK en (`'Abierto'`, `'En progreso'`, `'Pendiente de usuario'`, `'Resuelto'`, `'Cerrado'`) |
| `category_id` | `BIGINT` | NOT NULL, FK → `categories(id)` |
| `priority_id` | `BIGINT` | NOT NULL, FK → `priorities(id)` |
| `creator_id` | `BIGINT` | NOT NULL, FK → `employees(id)` |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT `now()` |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT `now()` |

Restricciones e índices:
- `UNIQUE (creator_id, content_hash)` → clave de deduplicación.
- `UNIQUE (ticket_number)`.
- `CHECK (char_length(title) BETWEEN 5 AND 120)`.
- `CHECK (char_length(description) BETWEEN 20 AND 5000)`.
- Índice `ix_tickets_creator_created` sobre `(creator_id, created_at DESC)`.
- Índice `ix_tickets_status` sobre `(status)`.
- `ticket_number` se genera con la secuencia `ticket_number_seq` y la expresión:
  `'TK-' || lpad(nextval('ticket_number_seq')::text, 6, '0')`.
  La secuencia se crea en la migración inicial con `START 1 INCREMENT 1`. Los huecos son aceptables.

### `ticket_events`

Primer evento de historial. El modelo queda preparado para eventos futuros, pero esta historia solo inserta `created`.

| Columna | Tipo | Restricciones |
|---------|------|---------------|
| `id` | `BIGSERIAL` | PK |
| `ticket_id` | `BIGINT` | NOT NULL, FK → `tickets(id)` ON DELETE CASCADE |
| `event_type` | `VARCHAR(30)` | NOT NULL, CHECK en (`'created'`) para esta versión |
| `author_id` | `BIGINT` | NOT NULL, FK → `employees(id)` |
| `metadata` | `JSONB` | NOT NULL, DEFAULT `'{}'` |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT `now()` |

Índice: `ix_ticket_events_ticket_created` sobre `(ticket_id, created_at ASC)`.

Para la creación, `metadata` guarda `{"ticket_number": "TK-000001", "status": "Abierto"}`.

### `attachments`

| Columna | Tipo | Restricciones |
|---------|------|---------------|
| `id` | `BIGSERIAL` | PK |
| `ticket_id` | `BIGINT` | NOT NULL, FK → `tickets(id)` ON DELETE CASCADE |
| `original_filename` | `VARCHAR(255)` | NOT NULL |
| `stored_filename` | `VARCHAR(255)` | NOT NULL, UNIQUE |
| `mime_type` | `VARCHAR(100)` | NOT NULL, CHECK en (`'image/png'`, `'image/jpeg'`, `'image/gif'`) |
| `size_bytes` | `BIGINT` | NOT NULL, CHECK `> 0` y `<= 5242880` |
| `relative_path` | `TEXT` | NOT NULL, UNIQUE |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT `now()` |

Índice: `ix_attachments_ticket` sobre `(ticket_id)`.

`relative_path` es relativo a `ATTACHMENTS_DIR`, por ejemplo `attachments/TK-000001/8f14e45f-....png`. No se expone el sistema de archivos al cliente en esta historia.

## Reglas de validación

| Regla | Dónde se aplica |
|-------|-----------------|
| Título obligatorio, 5–120 caracteres tras `strip()` | Pydantic + CHECK en BD |
| Descripción obligatoria, 20–5000 caracteres tras `strip()` | Pydantic + CHECK en BD |
| Máximo 5 adjuntos | Servicio de adjuntos |
| Máximo 5 MB por adjunto | Servicio de adjuntos (streaming) + CHECK en BD |
| Tipos permitidos: PNG, JPEG, GIF | Extensión + `Content-Type` + firma binaria en servicio |
| Prioridad elegida debe existir, estar activa y no ser de sistema | Servicio de tickets |
| Categoría no la elige el cliente: la determina el servidor | Servicio de sugerencias/tickets |
| Duplicado: mismo `creator_id` + `content_hash` | Índice único + servicio |
| Adjuntos todo-o-nada | Servicio de tickets (transacción + limpieza) |

## Hash de contenido

```text
content_hash = SHA-256( NFC(title.strip()) + "\n" + NFC(description.strip()) )
```

- Sensible a mayúsculas/minúsculas (el requisito habla del mismo título y descripción).
- No incluye categoría, prioridad ni adjuntos: dos envíos con mismo texto son duplicados aunque cambien esos valores.
- Se calcula tras validar longitudes.

## Estados

Para esta historia el ticket nace en `Abierto`. No se implementan transiciones; las demás transiciones pertenecen a historias posteriores. La columna `status` admite los valores del ciclo completo para no migrar el esquema al añadirlas.

```text
(nuevo) ──> Abierto
```

## Datos de siembra

Empleado:
- `name`: "Empleado Demo"
- `email`: "demo@empresa.local"
- `is_active`: true

Categorías (todas activas, `is_system = false`):

| Nombre | `is_default` | Palabras clave de ejemplo |
|--------|--------------|---------------------------|
| Red y conectividad | false | wifi, vpn, internet, red, conexión, proxy, dns |
| Hardware | false | portátil, ordenador, monitor, teclado, ratón, batería, pantalla |
| Software | false | aplicación, programa, instalar, actualizar, error, crash, lentitud |
| Accesos y contraseñas | false | contraseña, acceso, login, usuario, bloqueado, permisos |
| Correo | false | correo, email, outlook, bandeja, enviar, recibir |
| Impresoras | false | impresora, imprimir, escáner, tóner, papel |
| Otros | true | (sin palabras clave) |
| Sin clasificar | false (`is_system = true`) | (sin palabras clave) |

Prioridades (todas activas, `is_system = false`):

| Nombre | Nivel | Color | `is_default` | Palabras clave de ejemplo |
|--------|-------|-------|--------------|---------------------------|
| Crítica | 1 | `#dc2626` | false | urgente, crítico, caído, no puedo trabajar, toda la oficina |
| Alta | 2 | `#f97316` | false | importante, bloqueado, error grave, afecta a varios |
| Media | 3 | `#eab308` | true | (sin palabras clave) |
| Baja | 4 | `#22c55e` | false | leve, consulta, cuando pueda, no urgente |
| Sin clasificar | 5 | `#64748b` | false (`is_system = true`) | (sin palabras clave) |

El script de siembra es idempotente: usa `INSERT ... ON CONFLICT (name) DO UPDATE` para catálogos y `ON CONFLICT (email) DO NOTHING` para el empleado.
