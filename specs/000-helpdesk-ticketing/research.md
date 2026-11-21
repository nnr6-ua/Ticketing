# Investigación — Decisiones del núcleo

| ID | Decisión | Justificación |
|---|---|---|
| D-01 | FastAPI + SQLAlchemy 2 + Alembic + PostgreSQL; Vue 3 + TS + Vite + Pinia + Tailwind | Stack fijado por la constitución; ya usado por las ocho historias. |
| D-02 | Contratos OpenAPI por historia y validación mediante pruebas de contrato | Permite verificación automática y genera documentación útil para la memoria. |
| D-03 | JWT con identidad y rol leídos siempre en servidor | Simplicidad y mínimo privilegio; el rol del token en cliente es solo cosmético y no autoriza. |
| D-04 | Línea temporal `append-only` | Trazabilidad auditable y agregación estable para HU-07. |
| D-05 | SLA en horas naturales continuas (24/7), sin festivos | Regla cerrada con el usuario; evita calendarios y ambigüedad de zona horaria laboral. |
| D-06 | Versión de configuración congelada en el ticket | Los cambios administrativos no alteran plazos ya asignados. |
| D-07 | Notificación en aplicación (campana) | Sin SMTP en el entorno de entrega; suficiente para las historias HU-03 y HU-06. |
| D-08 | Primera finalización como hito SLA | Coincide con el momento en que el ticket deja de estar abierto para el técnico. |
| D-09 | Umbrales fijos 90 % / 70 % | No configurables desde la interfaz; simplifica el dashboard y las pruebas. |
| D-10 | Cola colectiva acotada a tickets sin responsable en `en_progreso` | Conciliación entre propiedad individual y devolución de HU-03 sin mostrar tickets ajenos asignados. |

Las decisiones D-01 a D-10 son definitivas para v1 y están aplicadas en `spec.md`.
