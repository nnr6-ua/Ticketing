# Análisis de consistencia — HU-01 Crear ticket

Fecha: 2026-11-19. Entrada: `spec.md`, `plan.md`, `tasks.md`, `contracts/openapi.yaml` y código implementado.

| ID | Hallazgo | Resolución |
|---|---|---|
| A-001-1 | La spec decía «categoría y prioridad sugeridas» sin indicar si la categoría era editable. | Cerrado: categoría fija por keywords; prioridad editable; valores por defecto documentados. |
| A-001-2 | Aparecía una referencia a correo electrónico en avisos. | Cerrado: notificaciones solo en aplicación; SMTP fuera de alcance en v1. |
| A-001-3 | Los adjuntos podían entenderse como parcialmente aceptados si fallaba el guardado. | Cerrado: contrato y servicio exigen todo-o-nada; error `422` sin ticket creado. |
| A-001-4 | Constitution Check usaba una numeración resumida, no los cinco principios canónicos. | Cerrado: `plan.md` usa los principios I–V de `.specify/memory/constitution.md`. |

Cobertura: RF-01.1..RF-01.7 y SC-01.1..SC-01.5 trazados a contrato, tareas y pruebas. No quedan marcadores `[NEEDS CLARIFICATION]`.

Resultado: **CONSISTENTE**.
