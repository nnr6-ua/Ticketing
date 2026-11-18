# Constitución de Ticketing (resumen)

> **Fuente de verdad**: [`.specify/memory/constitution.md`](../.specify/memory/constitution.md) (v1.0.0, ratificada el 2026-11-02). Este fichero y `CONSTITUTION.md` (raíz) son resúmenes informativos; ante cualquier discrepancia prevalece el documento ratificado.

## Principios rectores

1. **Arquitectura por capas y stack fijado**: FastAPI, SQLAlchemy 2, Alembic y PostgreSQL en backend; Vue 3, TypeScript, Vite, Pinia y Tailwind en frontend. Los endpoints solo orquestan; las reglas viven en `services`.

2. **Modelo de datos estable y migraciones aditivas**: cambios compatibles hacia atrás mediante Alembic, con historial de negocio append-only e inmutable.

3. **Seguridad y mínimo privilegio**: identidad exclusivamente desde JWT Bearer, autorización real en servidor, secretos por variables de entorno y datos internos visibles solo para quien puede verlos.

4. **Contratos primero y pruebas verificables**: contratos HTTP y de componentes antes de implementar; pruebas ejecutables de estados, permisos, atomicidad, concurrencia y errores, con formato de error estable.

5. **Simplicidad, trazabilidad y experiencia en español**: YAGNI, decisiones justificadas en `plan.md`/`research.md`, fechas UTC mostradas en `Europe/Madrid` y accesibilidad WCAG 2.1 AA.

Las restricciones adicionales (base de datos, formato de error, compatibilidad de cliente, rendimiento y accesibilidad) y el procedimiento de enmienda están en el documento ratificado.
