# Implementación — Spec núcleo `000`

## Artefactos producidos

- `spec.md`, `checklists/requirements.md` (preexistentes, revisados).
- `plan.md`, `tasks.md`, `research.md`, `data-model.md`, `contracts/api-conventions.md`, `quickstart.md`.
- `analyze.md`, `implement.md`, `converge.md`.

## Código alineado con el núcleo

- `backend/app/main.py`: título y descripción globales de la mesa de ayuda, no solo HU-04.
- `backend/app/api/deps.py`: identidad desde JWT y roles.
- `backend/app/services/ticket_state_machine.py`: estados y transiciones canónicos.
- `backend/app/services/ticket_timeline.py`: línea temporal inmutable.
- `backend/app/services/sla_dashboard.py`: métrica de primera finalización y umbrales fijos.
- `backend/app/services/work_queue.py`: cola propia + colectiva.
- `frontend/src/router/index.ts`: navegación por rol; la autorización definitiva permanece en backend.

## Verificación

- `workflow.yml` validado como YAML y con el ciclo completo.
- `docs/agrupamiento.md` y `docs/memoria.md` enlazan el núcleo con las ocho historias.
- Todas las specs `001`–`008` tienen analyze/implement/converge explícitos.

Nota: el rol leído en cliente se usa para ocultar navegación, nunca como autorización; la defensa es el `403` del backend.
