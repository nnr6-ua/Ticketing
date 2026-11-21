# Guía rápida de verificación — Spec `000`

## Puesta en marcha

```bash
cd backend
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

```bash
cd frontend
npm install
npm run dev -- --port 5173
```

## Comprobaciones de aceptación del núcleo

1. Con un token de `usuario`, crear un ticket y comprobar `TK-000001`, creador, fecha, estado `abierto` y primer evento de línea temporal.
2. Con `tecnico`, ver el ticket en `/cola-de-trabajo` tras asignarlo y comprobar el orden por urgencia/SLA.
3. Solicitar información, responder como creador y verificar que el ticket vuelve a la cola colectiva sin responsable.
4. Cambiar a `resuelto` y después a `cerrado`; verificar que `first_finalized_at` se escribe solo en la primera finalización y que `cerrado` es terminal.
5. Con `supervisor`, abrir `/dashboard-sla` y comprobar semáforo 90 %/70 %, matriz, totales, ranking y filtros.
6. Con `admin`, cambiar una regla SLA y verificar que el ticket creado antes conserva su versión original.

## Pruebas automatizadas

```bash
cd backend && python3 -m pytest
cd frontend && npm test
```

Para ejecutar las pruebas marcadas `postgres`, exportar `TEST_DATABASE_URL` apuntando a PostgreSQL 16. Sin esa variable se omiten y SQLite actúa como fallback.

## Demo

`http://localhost:8080/demo/` muestra el vídeo y la reproducción de las 31 historias/escenarios de entrega.
