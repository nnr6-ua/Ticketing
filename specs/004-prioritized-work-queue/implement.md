# Implementación — HU-04 Cola priorizada

## Artefactos producidos

- `spec.md`, `plan.md`, `tasks.md`, `research.md`, `data-model.md`, `contracts/work-queue.openapi.yaml`, `checklists/requirements.md`.
- `analyze.md`, `implement.md`, `converge.md`.

## Código de referencia

- API: `backend/app/api/v1/work_queue.py`.
- Servicio: `backend/app/services/work_queue.py` (filtro `assignee_id == user_id OR (assignee_id IS NULL AND status == en_progreso)`).
- Frontend: `frontend/src/stores/workQueue.ts`, `frontend/src/views/WorkQueuePage.vue`, componentes `work-queue/*`.
- Pruebas: contrato, integración, `WorkQueueAccessibility.spec.ts`, `WorkQueueStates.spec.ts`, `WorkQueuePagination.spec.ts`.

## Decisiones aplicadas

- Orden por urgencia, SLA y criterios estables; paginación por offset suficiente para ≤ 100 tickets.
- La cola colectiva contiene solo tickets sin responsable en `en_progreso`; nunca tickets asignados a otro técnico.
- Indicadores con color + icono + texto, prioridades inactivas marcadas como «(inactiva)» y errores diferenciados de estados vacíos.
- `PRIORITY_BADGE_CLASS` alineado con Media=azul y Baja=gris.

## Verificación

- Contrato y pruebas de componente cubren filtros, paginación, accesibilidad y errores.
- Quedan abiertas T085–T088, T090, T094 y T095 según `Estado final de convergencia`.
