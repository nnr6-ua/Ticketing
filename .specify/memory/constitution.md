# Constitución del proyecto Mesa de Ayuda

<!--
  Documento ratificado. Cualquier cambio requiere el procedimiento de
  gobernanza descrito al final de este fichero.
-->

## Principios fundamentales

### I. Arquitectura por capas y stack fijado

El sistema es una aplicación web con backend y frontend separados. El backend
usa FastAPI, SQLAlchemy 2, Alembic y PostgreSQL; el frontend usa Vue 3,
TypeScript, Vite, Pinia y Tailwind CSS. La dirección permitida es
`api → services → models/db`, con `schemas` como contrato de entrada y salida.
Los endpoints solo orquestan: la lógica de negocio y las reglas de estado viven
en `services`. No se introducen nuevas tecnologías, motores de workflow, colas
ni servicios externos sin una enmienda a esta constitución. Se reutilizan la
autenticación JWT, el cliente HTTP, el formato de errores y los componentes
visuales existentes.

### II. Modelo de datos estable y migraciones aditivas

El modelo base es un contrato compartido. Los cambios de esquema deben ser
aditivos y compatibles hacia atrás: columnas nuevas anulables o con valor por
defecto, tablas nuevas y enums ampliados; nunca se renombran ni se eliminan
columnas o tablas existentes en una misma entrega. Toda modificación de esquema
se realiza mediante una migración de Alembic con `upgrade()` y `downgrade()`
verificables sobre PostgreSQL. El histórico de negocio relevante es
append-only e inmutable; no se sobrescribe evidencia de estados o resoluciones
anteriores. Cada cambio de datos se documenta en `data-model.md`.

### III. Seguridad y mínimo privilegio

La identidad se obtiene exclusivamente del token JWT (`Authorization: Bearer`);
nunca de parámetros de consulta, cuerpos de petición o cabeceras manipulables.
La autorización se aplica siempre en el servidor: el cliente puede ocultar
acciones, pero no es la defensa. Se aplica el mínimo privilegio por rol y por
asignación actual del ticket. Los datos internos (comentarios, notas,
credenciales) nunca se envían a quien no puede verlos, ni siquiera para que el
frontend los oculte. Los secretos se leen de variables de entorno y nunca se
versionan. Las entradas se validan y se renderizan como texto plano; se prohíbe
`v-html` con contenido de usuario.

### IV. Contratos primero y pruebas verificables (NO NEGOCIABLE)

Los contratos HTTP (OpenAPI) y de componentes se documentan antes de
implementar. Cada historia incluye pruebas ejecutables de la matriz de estados,
permisos, visibilidad, atomicidad, concurrencia, idempotencia y códigos de
error; las pruebas se escriben antes de la implementación cuando el plan las
enumera. Una funcionalidad sin verificación ejecutable no se considera
terminada. Las pruebas de concurrencia real se ejecutan sobre PostgreSQL; las
pruebas funcionales pueden usar SQLite a través de la abstracción existente.
Los mensajes de error expuestos usan códigos estables e independientes del
formato interno del framework.

### V. Simplicidad, trazabilidad y experiencia en español

Se aplica YAGNI: la solución más simple que cumpla los requisitos, sin
abstracciones especulativas. Toda decisión compleja se justifica en el plan y
en `research.md`. La línea temporal es la fuente de trazabilidad: cada cambio
relevante registra autor, fecha, estado anterior y estado nuevo. La interfaz y
los mensajes van en español de España (es-ES), con fechas mostradas en
`Europe/Madrid` y almacenadas en UTC. La interfaz cumple WCAG 2.1 AA, es
responsive y funciona con teclado y lectores de pantalla.

## Restricciones adicionales

- **Base de datos**: PostgreSQL en desarrollo y producción; SQLite solo para
  pruebas locales mediante la abstracción de sesión existente.
- **Formato de error**: `{"detail": {"code": "...", "message": "..."}}`, con
  mensajes comprensibles en español y códigos estables en `snake_case`.
- **Compatibilidad de cliente**: cuando el cliente compilado solo expone GET y
  POST, los comandos se modelan como recursos POST; no se añaden PATCH, PUT o
  DELETE sin actualizar y verificar el cliente.
- **Rendimiento**: las operaciones de lectura y comando deben mantenerse en
  p95 inferior a 300 ms de servidor para el volumen previsto de la mesa de
  ayuda; el historial se pagina.
- **Accesibilidad**: contraste AA, foco visible, etiquetas asociadas,
  `role="alert"`/`aria-live` para mensajes dinámicos y navegación por teclado.

## Flujo de desarrollo y puertas de calidad

1. Cada funcionalidad pasa por especificación (`spec.md`), plan (`plan.md`) y
   desglose de tareas (`tasks.md`) antes de implementarse.
2. El `Constitution Check` del plan se evalúa antes de la Fase 0 y se vuelve a
   evaluar tras el diseño de la Fase 1. Una violación bloquea el avance salvo
   que se documente en `Complexity Tracking` con una justificación aprobada.
3. El análisis de consistencia es de solo lectura; cualquier remediación se
   propone y se aprueba antes de aplicarse.
4. Antes de fusionar: pruebas de backend y frontend en verde, migraciones
   `upgrade`/`downgrade` verificadas, revisión de accesibilidad y revisión de
   seguridad de la visibilidad de datos internos.
5. La revisión de código verifica explícitamente el cumplimiento de los cinco
   principios y de las restricciones adicionales.

## Gobernanza

Esta constitución prevalece sobre cualquier otra práctica o convención del
repositorio. Las enmiendas requieren una propuesta documentada con motivación,
impacto, plan de migración y aprobación; se versionan con semver
(MAYOR por cambios incompatibles, MENOR por nuevos principios o restricciones,
PARCHE por aclaraciones) y se actualiza la fecha de última enmienda. Todo
cambio incompatible debe incluir un plan de migración. El cumplimiento se
verifica en cada revisión; una violación no justificada bloquea la fusión.

**Version**: 1.0.0 | **Ratified**: 2026-11-02 | **Last Amended**: 2026-11-02
