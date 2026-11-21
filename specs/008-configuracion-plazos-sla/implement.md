# Implementación — HU-08 Configuración administrativa

## Artefactos producidos

- `spec.md`, `plan.md`, `tasks.md`, `research.md`, `data-model.md`, `contracts/admin-configuration.openapi.yaml`, `checklists/requirements.md`.
- `analyze.md`, `implement.md`, `converge.md`.

## Código de referencia

- API: `backend/app/api/v1/admin_configuration.py`.
- Servicio: `backend/app/services/configuration.py`.
- Frontend: `frontend/src/stores/adminConfiguration.ts`, `frontend/src/views/AdminConfigurationPage.vue`, componentes `SlaMatrix.vue`, `CategoryFormDialog.vue`, `PriorityFormDialog.vue`.
- Pruebas: integración de administración, concurrencia, rendimiento y specs de componentes.

## Decisiones aplicadas

- Categorías, prioridades y matriz SLA editables solo por administrador.
- Cambios versionados con `effective_from`; no retroactivos.
- Regla de exclusión por categoría/prioridad validada antes de persistir.
- Sin SMTP, sin festivos y sin horario laboral: horas naturales continuas.

## Verificación

- Contrato y pruebas cubren alta, baja, activación, matriz, histórico y errores.
- `quickstart.md` describe los escenarios manuales de administración.
