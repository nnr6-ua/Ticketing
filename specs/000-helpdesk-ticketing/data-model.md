# Modelo de datos compartido — Spec `000`

## Entidades

### `users`

- `id` (UUID, PK), `email` (único), `full_name`, `role` (`usuario` | `tecnico` | `supervisor` | `admin`), `team`, `is_active`.
- La identidad del solicitante/técnico se obtiene del JWT; no se acepta `user_id` del cliente.

### `tickets`

- `id` (UUID, PK), `number` (`TK-000001`, único e inmutable), `title`, `description`.
- `creator_id` → `users.id`, `assignee_id` → `users.id` (nullable).
- `category_id`, `priority_id`, `configuration_version_id`.
- `status` (`abierto` | `en_progreso` | `pendiente_usuario` | `resuelto` | `cerrado`).
- `created_at`, `first_finalized_at` (nullable), `finalized_at` (nullable).
- Adjuntos: entidad `attachments` con ruta local, MIME validado y tamaño ≤ 5 MB.

### `ticket_timeline_entries`

- `id` (UUID, PK), `ticket_id`, `author_id`, `kind`, `body` (nullable), `visibility` (`public` | `internal`), `created_at`.
- Inmutable: no hay operaciones de actualización ni borrado.

### Configuración (HU-08)

- `categories`: id, nombre, activa, por defecto, palabras clave, `sort_order`.
- `priorities`: id, nombre, nivel, color, activa, por defecto, `sort_order`.
- `sla_rules`: combinación categoría/prioridad → plazo en horas.
- `configuration_versions`: versión con `effective_from` e histórico consultable.

### Notificaciones (HU-03/HU-06)

- `notifications`: id, `user_id`, `ticket_id`, `kind`, `read_at`, `created_at`.
- Sin canal externo: la campana consulta este almacén.

## Invariantes

1. `number` y `created_at` no cambian tras la creación.
2. `cerrado` es terminal.
3. Un ticket sin responsable en `en_progreso` pertenece a la cola colectiva de HU-04.
4. `first_finalized_at` se escribe una sola vez, en la primera transición a `resuelto`/`cerrado`.
5. Los cambios de configuración no actualizan `configuration_version_id` de tickets existentes.
6. Toda transición, reasignación o respuesta genera exactamente una entrada de línea temporal.

## Migraciones

Aditivas y reversibles con Alembic. Se prohíbe renombrar o eliminar columnas en v1 sin revisar todas las specs dependientes.
