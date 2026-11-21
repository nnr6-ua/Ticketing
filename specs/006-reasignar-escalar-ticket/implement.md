# Implementación — HU-06 Reasignar y escalar

## Artefactos producidos

- `spec.md`, `plan.md`, `tasks.md`, `research.md`, `data-model.md`, `contracts/`, `checklists/requirements.md`.
- `analyze.md`, `implement.md`, `converge.md`.

## Código de referencia

- API: `backend/app/api/v1/tickets.py`, `backend/app/api/v1/notifications.py`.
- Servicio: `backend/app/services/assignee_change.py`.
- Frontend: `TicketAssigneeChangePanel.vue`, `AssigneeSelector.vue`, `EscalationLevelSelector.vue`, `AssigneeChangeReasonForm.vue`.
- Pruebas: integración de reasignación/escalado y specs de componentes con axe-core.

## Decisiones aplicadas

- Solo roles técnicos pueden reasignar o escalar; la identidad del autor se toma del JWT.
- Todo cambio genera evento en la línea temporal y aviso en aplicación al nuevo responsable.
- La reasignación no altera el número de ticket ni la versión SLA congelada.

## Verificación

- Contrato, integración y pruebas de accesibilidad cubren motivo, destino y visualización.
- `quickstart.md` describe el recorrido manual para técnico y supervisor.
