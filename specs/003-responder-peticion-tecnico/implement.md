# Implementación — HU-03 Petición de información

## Artefactos producidos

- `spec.md`, `plan.md`, `tasks.md`, `research.md`, `data-model.md`, `contracts/`, `checklists/requirements.md`.
- `analyze.md`, `implement.md`, `converge.md`.

## Código de referencia

- API: `backend/app/api/v1/tickets.py`, `backend/app/api/v1/notifications.py`.
- Servicios: `backend/app/services/ticket_workflow.py`, `notifications.py`, `ticket_timeline.py`.
- Frontend: `frontend/src/stores/notifications.ts`, `frontend/src/views/TicketDetailPage.vue`, `NotificationBell.vue`.
- Pruebas: integración de petición/respuesta, recordatorio 48 h y specs de campana.

## Decisiones aplicadas

- El técnico solicita información desde un ticket en curso; el creador responde desde «Mis tickets».
- El aviso es exclusivamente en aplicación (campana).
- La respuesta genera evento público y devuelve el ticket a la cola colectiva (`en_progreso`, sin responsable).
- El recordatorio de 48 h está ligado a `HU03-RF-010`.

## Verificación

- Contrato y pruebas cubren petición, respuesta, recordatorio y visibilidad del evento.
- `quickstart.md` incluye recorrido manual para ambos roles.
