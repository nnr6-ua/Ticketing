# Plan de implementación — Spec núcleo `000`

## Contexto técnico

- Backend: Python 3.12, FastAPI, SQLAlchemy 2, Alembic, PostgreSQL 16 (SQLite para desarrollo/pruebas), JWT.
- Frontend: Vue 3, TypeScript, Vite, Pinia, Tailwind, Headless UI, Vitest.
- Repositorio: monorepo con `backend/`, `frontend/`, `specs/`, `docs/` y `.specify/`.
- Sin servicios externos obligatorios: no hay SMTP, colas, caché ni proveedores de identidad en v1.

## Principios constitucionales (canónicos)

| Principio | Aplicación en el núcleo |
|---|---|
| I. Arquitectura por capas y stack fijado | API → servicios → modelos/BD; interfaz desacoplada mediante contratos OpenAPI. |
| II. Modelo de datos estable y migraciones aditivas | Modelos compartidos; migraciones aditivas; línea temporal `append-only`. |
| III. Seguridad y mínimo privilegio | Identidad desde JWT; autorización en servidor; sin secretos en código. |
| IV. Contratos primero y pruebas verificables | OpenAPI por historia, pruebas de contrato/integración/componente y quickstarts ejecutables. |
| V. Simplicidad, trazabilidad y experiencia en español | Un único modelo de ticket, errores y copia en es-ES, trazabilidad RF/SC en cada historia. |

Resultado: **PASA**, sin excepciones.

## Estructura acordada

- `specs/000-helpdesk-ticketing/`: contratos comunes, modelos, decisiones y este plan.
- `specs/001..008`: una historia por carpeta, con `spec.md`, `plan.md`, `tasks.md`, `research.md`, `data-model.md`, `contracts/`, `checklists/requirements.md`, `analyze.md`, `implement.md`, `converge.md` y `quickstart.md`.
- `docs/agrupamiento.md`: reparto entre Nayara y José Miguel.
- `docs/memoria.md`: memoria final con índice de 12 apartados.

## Reglas transversales

1. Ninguna historia redefine estados, roles, formato de error ni línea temporal.
2. El plazo SLA se calcula en horas naturales (24/7) y se congela por versión en cada ticket.
3. Las notificaciones son solo en aplicación (campana).
4. La cola de trabajo incluye tickets propios y la cola colectiva de HU-03.
5. El dashboard usa primera finalización y umbrales fijos 90 % / 70 %.
6. La configuración administrativa nunca es retroactiva.

## Fuera de alcance

Correo electrónico, SMS, calendario laboral/festivos, SLA configurable por interfaz, edición/borrado de eventos de línea temporal y autenticación externa.

## Complejidad

No se requiere justificación adicional: no hay desviaciones de los principios I–V.
