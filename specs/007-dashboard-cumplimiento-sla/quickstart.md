# Quickstart: Validación del Dashboard de cumplimiento de SLA (HU-07)

**Feature**: `007-dashboard-cumplimiento-sla` | **Date**: 2026-11-15

Guía de validación ejecutable end-to-end. Las referencias normativas viven en
[`plan.md`](./plan.md) (§ Requisitos técnicos), [`data-model.md`](./data-model.md)
(derivaciones) y [`contracts/`](./contracts/) (contratos). Este documento no
incluye código de implementación.

---

## 1. Prerrequisitos

- Docker + Docker Compose (o backend con PostgreSQL local).
- Python 3.12 y Node 20 para ejecutar las suites de pruebas sin contenedores.
- Roles disponibles: `supervisor`, `admin` (acceso), `tecnico` y `usuario`
  (denegado). En desarrollo, el stub `POST /api/v1/dev/login` emite tokens
  cuando `AUTH_DEV_STUB_ENABLED=true`.

## 2. Arranque

```bash
# Todo el stack (sin cambios respecto a HU-04/05/06)
docker compose up --build

# Backend:  http://localhost:8000  (OpenAPI en /openapi.json)
# Frontend: http://localhost:8080
```

Instalar dependencias de pruebas (la adición de `tzdata` es nueva):

```bash
cd backend && pip install -r requirements.txt
cd frontend && npm install
```

## 3. Suites de pruebas automatizadas

```bash
# Backend (SQLite por defecto; PostgreSQL real si TEST_DATABASE_URL está definido)
cd backend && pytest -q
# Solo los nuevos del dashboard:
cd backend && pytest -q tests/unit/test_sla_dashboard_math.py \
                       tests/integration/test_sla_dashboard.py \
                       tests/contract/test_sla_dashboard_contract.py
# Con PostgreSQL (marca existente):
TEST_DATABASE_URL="postgresql+psycopg://..." pytest -q -m "postgres"

# Frontend
cd frontend && npm run test
```

Resultado esperado: todas en verde, incluidas las nuevas (fórmulas, semáforo,
permisos, conciliación de totales, estados vacíos).

## 4. Datos de control

Usar el seed existente (`backend/scripts/seed_dev.py`) como base y, si hace
falta, ajustar con casos controlados:

| Ticket de control | Propiedad que valida |
|---|---|
| Finalizado con `finalized_at < sla_deadline` | Dentro de plazo (numerador) |
| Finalizado con `finalized_at == sla_deadline` (exacto al límite) | Dentro de plazo, NO vencido (HU07-SC-015) |
| Finalizado con `finalized_at > sla_deadline` | Vencido histórico; atribuido a quien lo finalizó (autor de la 1.ª entrada a «Resuelto») |
| Activo sin finalizar con `sla_deadline < ahora` | Vencido creciente; atribuido al responsable actual |
| Activo sin finalizar con `sla_deadline > ahora` | No vencido; fuera de % y media (pendiente de atención) |
| `sla_deadline = NULL` | «Sin SLA»: excluido de % y media, nunca vencido |
| Reabierto y vuelto a finalizar | Cuenta una vez con la PRIMERA finalización |
| Sin categoría | Fila/columna «Sin categoría» |
| De categoría/prioridad desactivada | Etiqueta histórica + «(inactiva)» |
| Vencido reasignado tras incumplir | Atribuido a quien lo finalizó, una sola vez |

## 5. Escenarios de validación manual (UI)

Ruta: `http://localhost:8080/dashboard-sla` (enlace visible solo para
supervisor/admin).

### E1. Acceso por rol

1. Inicia sesión como `supervisor` (stub `/dev/login` o JWT) → el dashboard
   carga con rango por defecto de los últimos 30 días naturales.
2. Inicia sesión como `tecnico` → enlace no visible; acceso directo a la URL
   devuelve estado «No tienes permiso para acceder a este dashboard.» y el
   backend responde `403 forbidden` sin datos.
3. Igual para `usuario`. Sin token → redirección a `/login` con `redirect`.

### E2. Matriz y totales (HU07-SC-001/003/005/014)

1. Con los datos de control, comprueba cada celda: % de cumplimiento (con
   coma decimal), tiempo medio legible («3 d 4 h», «37 min», «menos de 1 min»),
   vencidos y nº de tickets.
2. Comprueba que la suma de tickets de las celdas = total por prioridad =
   total por categoría = global, y que los totales se calcularon desde los
   tickets (no promediando celdas).
3. Comprueba que `ranking.overdue_total` = vencidos del resumen, incluida la
   fila «Sin asignar».
4. Comprueba que la vista es responsive y utilizable en escritorio y tablet (HU07-RN-14).

### E3. Semáforo y umbrales (HU07-SC-006/007)

1. Prepara combinaciones con cumplimiento ≥ 90 %, entre 70 y 90, y < 70:
   colores, iconos y textos («En objetivo», «En riesgo», «Fuera de objetivo»)
   coherentes con la leyenda, que muestra los umbrales de `meta.thresholds`
   (90 % / 70 %).
2. Un valor exactamente 90,0 % es **verde**; 70,0 % es **ámbar**.
3. Combinación sin atendidos con SLA ⇒ «Sin datos» neutro, sin color de
   alarma.
4. Verifica en un lector de pantalla / sin color que icono + texto portan la
   información (WCAG 2.1 AA).

### E4. Ranking (HU07-SC-004)

1. Orden: mayor nº de vencidos primero; empate ⇒ mayor retraso medio; si
   persiste, nombre ascendente (sin mayúsculas) y equipo.
2. Solo aparecen técnicos con ≥ 1 vencido; sin vencidos ⇒ estado vacío
   específico («No hay tickets vencidos en el periodo seleccionado.»).
3. Técnicos inactivos con vencidos ⇒ «(inactivo)».
4. Solo nombre, equipo y métricas; sin correos ni tickets individuales.

### E5. Filtros combinables (HU07-SC-005 · HU07-BN-005)

1. Aplica rango de fechas + varias categorías + varias prioridades a la vez:
   matriz, totales y ranking usan el mismo conjunto (los totales cuadran).
2. Lógica: «O» dentro de cada dimensión, «Y» entre dimensiones.
3. `desde > hasta` ⇒ la consulta se bloquea, se mantienen los filtros
   anteriores y aparece el mensaje «La fecha inicial no puede ser posterior
   a la fecha final.» (el backend responde `422 invalid_date_range` si se
   fuerza).
4. Filtro sin resultados ⇒ estado «No hay resultados para los filtros
   seleccionados.» con acción de limpiar (≠ periodo vacío).
5. Periodo sin tickets ⇒ estado vacío que sugiere ampliar el rango (nunca
   matriz de ceros).
6. Restablecer ⇒ vuelve a los últimos 30 días naturales con todo seleccionado.

### E6. Frescura y errores (HU07-SC-013/012)

1. Deja la vista abierta > 60 s: se actualiza sola y se refresca la hora
   «Última actualización» (Europe/Madrid).
2. Actualización manual: recalcula y mantiene filtros.
3. Detén el backend y fuerza una actualización con datos previos: se
   conservan con aviso de posible desactualización y botón de reintento.
4. Detén el backend y recarga: error diferenciado con reintento (nunca
   métricas a cero ni estado vacío).
5. Caduca la sesión: te lleva a `/login?redirect=/dashboard-sla` y, tras
   autenticar, vuelve con los filtros de la URL.

### E7. Solo lectura (HU07-RN-01)

1. Desde el dashboard no existe ninguna acción de edición.
2. Tras usar el dashboard, revisa en el detalle de un ticket que la línea
   temporal no tiene entradas nuevas generadas por la consulta.

### E8. Rendimiento (HU07-SC-002)

Protocolo de medición del objetivo «dashboard completo en menos de 3 segundos
para hasta 10.000 tickets, en al menos el 95 % de las cargas»:

1. **Entorno**: docker-compose local con PostgreSQL 16 y la semilla de
   rendimiento de T071 (10.000 tickets en el periodo, con variedad de
   prioridades, categorías, SLA y finalizaciones). Navegador de escritorio
   moderno con caché deshabilitada (DevTools → «Disable cache»).
2. **Qué se mide**: desde el inicio de `GET /api/v1/sla-dashboard` (pestaña
   Network) hasta que la vista pinta resumen, matriz, totales y ranking. No se
   cuentan el login ni la primera visita de calibración de la SPA.
3. **Muestra**: 20 cargas consecutivas del dashboard tras una carga de
   calentamiento (no se cuenta).
4. **Criterio (HU07-SC-002)**: al menos 19 de las 20 cargas (95 %) por debajo
   de 3 s. Registrar las mediciones como evidencia en el PR.
5. **Servidor (constitución)**: el p95 < 300 ms de la API lo automatiza T071;
   este escenario E8 valida el objetivo extremo a extremo.
6. Si no se cumple el criterio, registrar el perfil de tiempos (back end vs
   render) antes de cualquier optimización.

## 6. Contratos y trazabilidad

- HTTP: [`contracts/sla-dashboard.openapi.yaml`](./contracts/sla-dashboard.openapi.yaml)
  — `GET /api/v1/sla-dashboard`, `GET /api/v1/sla-dashboard/options`.
- Componentes: [`contracts/frontend-components.md`](./contracts/frontend-components.md).
- Derivaciones y fórmulas: [`data-model.md`](./data-model.md) §3–§4.
- Cada escenario anterior mapea a los criterios de éxito
  HU07-SC-001…HU07-SC-016 de [`spec.md`](./spec.md).
