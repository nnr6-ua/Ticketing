# Implementación — HU-01 Crear ticket

## Artefactos producidos

- `spec.md`, `plan.md`, `tasks.md`, `research.md`, `data-model.md`, `contracts/`, `checklists/requirements.md`.
- `analyze.md`, `implement.md`, `converge.md` (este ciclo).

## Código de referencia

- API: `backend/app/api/v1/ticket_creation.py`.
- Servicios: `backend/app/services/ticket_creation.py`, `suggestions.py`, `duplicates.py`, `attachments.py`, `ticket_numbers.py`, `catalogs.py`.
- Frontend: `frontend/src/views/TicketCreatePage.vue`, `frontend/src/api/client.ts`.
- Pruebas: `backend/tests/` (contrato, integración y unidad) y `frontend/tests/components/TicketAccessibility.spec.ts`.

## Decisiones aplicadas

- Categoría fija y prioridad editable, con valores por defecto deterministas.
- Número `TK-000001` secuencial e inmutable.
- Duplicados detectados antes de persistir; adjuntos validados por MIME y tamaño con semántica todo-o-nada.
- Primer evento de línea temporal creado en la misma transacción.

## Verificación

- Contrato OpenAPI validado por pruebas de contrato.
- Escenarios manuales en `quickstart.md` ejecutables por una persona no técnica.
- Sin secretos versionados; configuración por entorno.
