# Implementación — HU-02 Estado e historial

## Artefactos producidos

- `spec.md`, `plan.md`, `tasks.md`, `research.md`, `data-model.md`, `contracts/`, `checklists/requirements.md`.
- `analyze.md`, `implement.md`, `converge.md`.

## Código de referencia

- API: `backend/app/api/v1/my_tickets.py`, `backend/app/api/v1/tickets.py`.
- Servicios: `backend/app/services/ticket_timeline.py`.
- Frontend: `frontend/src/stores/ticketDetail.ts`, `frontend/src/views/MyTicketsPage.vue`, `frontend/src/views/TicketDetailPage.vue`.
- Pruebas: `backend/tests/integration/test_timeline_visibility.py` y specs de componentes de detalle.

## Decisiones aplicadas

- La línea temporal es inmutable; cada cambio de estado, asignación o comentario genera una entrada nueva.
- Los comentarios públicos son visibles para el creador; los internos solo para roles técnicos.
- Los eventos se ordenan por fecha con desempate estable y se muestran en español de España.

## Verificación

- Contrato y pruebas de integración cubren visibilidad por rol.
- `quickstart.md` describe los escenarios manuales de seguimiento.
