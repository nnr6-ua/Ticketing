# Tareas del núcleo — Spec `000`

Estado: todas completadas y verificadas en el código vigente.

| ID | Tarea | Evidencia |
|---|---|---|
| T000-01 | Ratificar constitución canónica | `.specify/memory/constitution.md` v1.0.0 |
| T000-02 | Fijar roles y estados | `spec.md`, `data-model.md` |
| T000-03 | Fijar formato de error `detail.code/message` | `contracts/api-conventions.md` |
| T000-04 | Fijar línea temporal `append-only` | `data-model.md`, HU-02 |
| T000-05 | Fijar SLA 24/7 y congelación por versión | `research.md`, HU-08 |
| T000-06 | Fijar notificaciones solo en aplicación | `spec.md`, HU-03/HU-06 |
| T000-07 | Fijar cola propia + colectiva | `spec.md`, HU-04 |
| T000-08 | Fijar métrica y umbrales del dashboard | `spec.md`, HU-07 |
| T000-09 | Fijar reparto por historia | `docs/agrupamiento.md` |
| T000-10 | Fijar ciclo Spec Kit completo | `.specify/workflows/speckit/workflow.yml` |
| T000-11 | Crear artefactos analyze/implement/converge | Este directorio y HU-01..HU-08 |
| T000-12 | Verificar coherencia final | `analyze.md` y `converge.md` |

## Dependencias

- HU-08 debe existir antes de HU-01/HU-07.
- HU-03 debe existir antes de cerrar la coherencia de HU-04.
- HU-05/HU-06 alimentan HU-02 y HU-07.
- Ninguna historia puede cambiar este núcleo sin revisar `converge.md` de todas las demás.
