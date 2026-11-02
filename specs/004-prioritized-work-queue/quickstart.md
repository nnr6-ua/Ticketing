# Guía de Validación: Cola de Trabajo Priorizada (HU-04)

**Funcionalidad**: `specs/004-prioritized-work-queue`
**Fecha**: 2026-10-29
**Objetivo**: demostrar de extremo a extremo que la cola priorizada cumple la [spec.md](./spec.md), sin leer código.

Esta guía describe cómo preparar el entorno, ejecutar las pruebas y validar manualmente cada comportamiento observable. Los detalles de diseño están en [plan.md](./plan.md), [data-model.md](./data-model.md) y [contracts/work-queue.openapi.yaml](./contracts/work-queue.openapi.yaml).

---

## 1. Requisitos previos

**Opción recomendada (Docker)**: Docker Engine 24+ y Docker Compose v2. Con esta opción no hace falta instalar Python, Node ni PostgreSQL en la máquina.

**Opción nativa**: Python 3.12 y `pip`, Node.js 20 LTS y `npm`, PostgreSQL 16 en local o accesible por red.

En ambos casos se necesita:

- Un mecanismo de autenticación del proyecto que permita iniciar sesión como técnico y obtener un JWT. Esta guía asume que todas las peticiones se envían con `Authorization: Bearer <token>`. Para las pruebas locales, el proyecto incluye un stub de login falso que se puede habilitar con `AUTH_DEV_STUB_ENABLED=true` (ver §3.0).
- Navegador Chromium/Firefox actualizado y, opcionalmente, un lector de pantalla (NVDA, Narrator o VoiceOver).

> No se necesitan claves ni secretos en el repositorio. Toda la configuración va por variables de entorno.

---

## 2. Variables de entorno

Backend (ejemplo, ajustar a los nombres reales del proyecto):

```text
DATABASE_URL=postgresql+psycopg://usuario:password@localhost:5432/ticketing
AUTH_ISSUER=<emisor del proveedor de autenticación>
AUTH_AUDIENCE=<audiencia>
APP_ENV=development
```

Frontend:

```text
VITE_API_BASE_URL=http://localhost:8000
```

Nunca commitear estos valores. Usar `.env.local` ignorado por Git o el gestor de secretos del equipo.

### 2.1 Variables con Docker Compose

El arranque contenerizado usa el archivo `.env` de la raíz. Copiar el ejemplo y ajustar los valores:

```bash
cp .env.example .env
# Windows PowerShell: Copy-Item .env.example .env
```

Variables principales: `FRONTEND_PORT`, `BACKEND_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `DATABASE_URL` (opcional), `JWT_SECRET`, `JWT_ALGORITHM`, `AUTH_ISSUER`, `AUTH_AUDIENCE`, `AUTH_DEV_STUB_ENABLED`, `FRONTEND_ORIGINS`, `MIGRATION_MAX_ATTEMPTS`, `MIGRATION_RETRY_SECONDS` y `VITE_API_BASE_URL`. La descripción completa está en el [`README.md`](../../README.md) de la raíz.

## 3. Puesta en marcha

### 3.0 Docker Compose (recomendado)

```bash
docker compose up --build
```

Comprobar que los tres servicios están sanos:

```bash
docker compose ps
```

Abrir `http://localhost:8080/cola-de-trabajo`. La API queda en `http://localhost:8000` y su documentación en `http://localhost:8000/docs`. Las migraciones de Alembic se aplican automáticamente al arrancar el backend.

Aplicar los datos de prueba:

```bash
docker compose exec backend python scripts/seed_dev.py
```

Acceder a la aplicación con el stub de autenticación de desarrollo (habilitado
por defecto en Compose):

1. Abrir `http://localhost:8080/login`.
2. En «Acceso de desarrollo», elegir `Técnico A` y pulsar «Entrar con token de
   prueba». La SPA guarda el JWT y redirige a `/cola-de-trabajo`.

También se puede obtener el token por consola:

```bash
curl -s -X POST http://localhost:8000/api/v1/dev/login \
  -H "Content-Type: application/json" \
  -d '{"email": "tecnico.a@example.com"}'
```

Detener conservando los datos:

```bash
docker compose down
```

Empezar de cero (borra el volumen):

```bash
docker compose down -v
docker compose up --build
```

### 3.1 Backend (opción nativa)

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
# Stub de login local: usa un secreto de desarrollo cualquiera.
AUTH_DEV_STUB_ENABLED=true JWT_SECRET=dev-only-secret uvicorn app.main:app --reload --port 8000
```

Comprobación rápida: `http://localhost:8000/docs` muestra `GET /api/v1/me/work-queue` y el esquema coincide con [work-queue.openapi.yaml](./contracts/work-queue.openapi.yaml).

### 3.2 Frontend (opción nativa)

```bash
cd frontend
npm install
npm run dev
```

Abrir `http://localhost:5173/login` e iniciar sesión con el stub de desarrollo como Técnico A.

### 3.3 Datos de prueba

Ejecutar el seed determinista incluido en el proyecto (T009), con la base ya migrada. En nativo:

```bash
python backend/scripts/seed_dev.py
```

Con Docker Compose:

```bash
docker compose exec backend python scripts/seed_dev.py
```

El seed prepara al menos:

- **Técnico A** (`tecnico.a@example.com`) con:
  - 2 tickets Crítica: uno vencido hace 2 h y otro con 30 min restantes.
  - 2 tickets Alta: uno con 10 min restantes y otro sin SLA.
  - 1 ticket Media dentro de plazo.
  - 1 ticket Resuelto finalizado **antes** de su deadline.
  - 1 ticket Cerrado finalizado **después** de su deadline.
- **Técnico B** con 2 tickets propios (para verificar que no aparecen en la cola de A).
- Un ticket con SLA total de **30 minutos** y 20 minutos restantes (para el umbral corto).
- Un ticket con SLA total de **4 horas** y 30 minutos restantes (debe estar en ámbar).

Los tickets deben tener `sla_deadline` y `created_at` en UTC y `finalized_at` coherente con su estado. Si se usan fixtures, reiniciar la base entre escenarios para evitar contaminación.

---

## 4. Pruebas automatizadas

### 4.1 Backend

```bash
cd backend
pytest tests/unit/test_sla.py -q
pytest tests/integration/test_work_queue_api.py -q
pytest tests/contract/test_work_queue_contract.py -q
```

Resultado esperado: todas en verde. Las pruebas cubren:

- Umbral de SLA corto (< 60 min), exactamente 60 min y largo.
- Límite exacto (0 s → `at_risk`) y −1 s → `overdue`.
- Sin SLA, finalizado cumplido, finalizado incumplido y sin SLA finalizado.
- Solo tickets del técnico autenticado; un `technician_id` inyectado no amplía la visibilidad.
- Filtros Y, estados por defecto, mezcla de activos y finales.
- Orden completo, paginación sin solapes y desempates.
- 401/403/422/500 y `Cache-Control: no-store`.

#### 4.1.1 Ejecución opcional contra PostgreSQL 16

La suite usa SQLite por defecto. Para validar el motor de producción, apunta
`TEST_DATABASE_URL` a una base **desechable** (las pruebas hacen
`drop_all`/`create_all`) y ejecuta también las migraciones:

```bash
cd backend
export TEST_DATABASE_URL="postgresql+psycopg://usuario:clave@localhost:5432/hu04_test"
export DATABASE_URL="$TEST_DATABASE_URL"   # mismo destino para alembic
alembic upgrade head
alembic downgrade base
alembic upgrade head
pytest -q
```

En PowerShell:

```powershell
$env:TEST_DATABASE_URL = "postgresql+psycopg://usuario:clave@localhost:5432/hu04_test"
$env:DATABASE_URL = $env:TEST_DATABASE_URL
```

Con esa variable, `tests/integration/test_work_queue_api.py` comprueba los
índices en `pg_indexes` y el plan con `EXPLAIN` de PostgreSQL; sin ella, usa
`PRAGMA index_list` y `EXPLAIN QUERY PLAN` de SQLite. La suite no crea ni borra
la base de datos, solo su esquema: no la apuntes a un entorno compartido.

### 4.2 Frontend

```bash
cd frontend
npm run test:unit -- --run
npm run test:components -- --run
```

Resultado esperado: todas en verde. Cubren formato de duraciones, paridad de clasificación con backend, sincronización de filtros con la URL, polling, cancelación, estados vacíos/error y accesibilidad básica.

### 4.3 Comprobación manual del contrato

Con un token de técnico A:

```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/me/work-queue?page=1&page_size=25" | jq
```

Verificar:

- `items` solo contiene tickets de A.
- `pagination.total_items` coincide con el número filtrado.
- `counts.active`/`counts.finalized` y `available_filters` son coherentes (sin contadores por opción).
- `meta.server_time` termina en `Z`.
- La cabecera es `Cache-Control: no-store`.

---

## 5. Escenarios de validación manual

Marcar cada uno como ✅ o ❌. Todos deben pasar para considerar la funcionalidad validada.

### V-01. Solo veo mis tickets (FR-001, FR-002, SC-001)

1. Iniciar sesión como Técnico A y abrir `/cola-de-trabajo`.
2. Revisar todos los tickets listados.
3. Comparar con los tickets de B.

**Esperado**: aparecen los 5 tickets activos de A; ninguno de B. Si se añade `?technician_id=<B>` o `?assignee_id=<B>` a la URL, la lista no cambia.

### V-02. Orden por prioridad y tiempo restante (FR-012, FR-013, FR-014, FR-016, SC-002)

1. Observar la columna de prioridad y el SLA.

**Esperado**: primero todas las Críticas, luego Altas, luego Media, luego Bajas. Dentro de cada prioridad, el orden es de menor a mayor tiempo restante: en Crítica, el vencido (tiempo negativo) antes que el de 30 min; en Alta, el de 10 min antes que el ticket sin SLA (que va al final de su prioridad); los empates se resuelven por número de ticket ascendente.

2. Cronometrar desde que la vista termina de cargar hasta identificar el ticket más urgente; repetir 3 veces y anotar la mediana.

**Esperado**: la mediana es inferior a 10 s (SC-002).

### V-03. Vencido en rojo con texto e icono (FR-018, FR-022, SC-003)

**Esperado**: el ticket vencido muestra fondo rojo suave, borde izquierdo rojo, icono de incumplimiento y el texto "Vencido hace 2 h" (o el tiempo real). El rojo no es el único indicador.

### V-04. Próximo a vencer en ámbar (FR-019, SC-004)

**Esperado**: el ticket con 10 min restantes (SLA de 4 h, umbral 60 min) muestra fondo ámbar, borde ámbar, icono de advertencia y "Próximo a vencer · 10 min".

### V-05. Umbral con SLA corto (FR-020, RN-09)

1. Abrir el ticket con SLA total de 30 min y 20 min restantes.

**Esperado**: **no** está en ámbar; muestra "Dentro de plazo · 20 min".

2. Esperar hasta que queden 15 min o menos (o ajustar el fixture).

**Esperado**: pasa a ámbar con "Próximo a vencer".

### V-06. Límite exacto y vencimiento (FR-008, FR-009)

1. Usar un ticket cuyo `remaining_seconds` sea exactamente 0.

**Esperado**: ámbar, "Vence ahora", aún no vencido.

2. Avanzar un segundo (o ajustar el fixture a −1 s).

**Esperado**: rojo, "Vencido hace menos de 1 min" y luego el tiempo correspondiente. El ticket sigue visible y accesible (SC-010).

### V-07. Sin SLA (FR-010, FR-015)

**Esperado**: el ticket sin deadline muestra "Sin SLA definido" en gris, sin alarma, y aparece al final de su grupo de prioridad (Alta), después de los que sí tienen SLA.

### V-08. Filtro por estado (FR-023, FR-025)

1. Seleccionar solo "En progreso".

**Esperado**: solo tickets de A en ese estado; el orden por urgencia se conserva; el contador de resultados coincide.

2. Seleccionar "Resuelto".

**Esperado**: aparece el ticket Resuelto con resultado histórico "Dentro de plazo" (sin cuenta atrás ni rojo/ámbar). El Cerrado no aparece.

### V-09. Filtro por prioridad (FR-024)

1. Seleccionar "Crítica".

**Esperado**: solo las Críticas de A, ordenadas por tiempo restante.

### V-10. Filtros combinados y limpieza (FR-025, FR-026, FR-027, FR-028, SC-006)

1. Seleccionar "Alta" + "En progreso" a la vez.

**Esperado**: solo los tickets que cumplen **ambos** criterios. El número de resultados se muestra junto a los filtros.

2. Recargar la página (F5) o abrir la misma URL en otra pestaña.

**Esperado**: los filtros siguen aplicados porque viajan en la URL.

3. Pulsar "Limpiar filtros".

**Esperado**: vuelve la cola activa completa y la URL queda sin filtros.

4. Cronometrar la búsqueda de un ticket concreto usando los filtros; repetir 3 veces y anotar la mediana.

**Esperado**: la mediana es inferior a 15 s (SC-006).

### V-11. Finalizados al final y ordenados por finalización (FR-034, FR-035, SC-011, SC-012)

1. Seleccionar estados activos + "Resuelto" + "Cerrado".

**Esperado**: primero todos los activos con el orden de urgencia; después los finalizados, sin mezclarse, aunque uno sea Crítico. Entre finalizados, el más recientemente finalizado va primero. El Resuelto muestra "Dentro de plazo"; el Cerrado muestra "Incumplido hace [tiempo]" (tiempo que rebasó el límite al finalizar), sin alerta activa.

### V-12. Estado vacío sin asignaciones (FR-030, SC-009)

1. Iniciar sesión con un técnico sin tickets.

**Esperado**: "No tienes tickets asignados actualmente." No es un error y no hay botón de reintento.

### V-13. Solo tickets finalizados (FR-030, escenario 4.2)

1. Iniciar sesión con un técnico cuyos únicos tickets están Resueltos/Cerrados.

**Esperado**: "No tienes tickets activos. Puedes consultar los finalizados cambiando el filtro de estado." Al filtrar por Resuelto/Cerrado, aparecen.

### V-14. Filtros sin resultados (FR-031)

1. Aplicar una combinación que no exista (por ejemplo, Baja + Pendiente de usuario).

**Esperado**: "No hay resultados para los filtros seleccionados." + botón "Limpiar filtros". Es distinto del estado vacío por falta de asignaciones.

### V-15. Error de carga y reintento (FR-032, SC-009)

1. Detener el backend o simular un 500.
2. Abrir o refrescar la cola.

**Esperado**: mensaje de error diferenciado, "No se pudo cargar tu cola de trabajo." + "Reintentar"; nunca se presenta como cola vacía. Al reactivar el backend y pulsar "Reintentar", carga correctamente.

3. Con datos ya cargados, provocar un fallo en el siguiente poll.

**Esperado**: la tabla se mantiene y aparece un aviso de que no se pudo actualizar, con opción de reintentar.

### V-16. Sesión caducada (FR-033)

1. Invalidar el token JWT (o esperar a que caduque).
2. Provocar una petición (poll o cambio de filtro).

**Esperado**: redirección a login; tras autenticarse, se vuelve a `/cola-de-trabajo` con la cola cargada.

### V-17. Actualización automática (FR-005, RN-14)

1. Con la vista abierta, reasignar uno de los tickets de A a B desde otra sesión.
2. Esperar hasta 60 s.

**Esperado**: el ticket desaparece de la cola de A sin recargar la página (máximo 60 s). Si se cambia el estado de un ticket, se refleja en el siguiente ciclo. Al volver a la pestaña tras estar oculta, la cola se actualiza de inmediato.

### V-18. Cambio de hora oficial (RN-04, caso límite)

1. Usar un ticket con deadline UTC conocido.
2. Consultar la cola antes y después del cambio de hora (o simular con el reloj del entorno de pruebas).

**Esperado**: `remaining_seconds` y el texto de duración cambian solo por el tiempo real transcurrido; no hay saltos de una hora. Las fechas absolutas se muestran en Europe/Madrid con el formato correcto.

### V-19. Paginación (FR-017)

1. Crear más de 25 tickets para A (o reducir `page_size` en la URL a 2 para la prueba).
2. Revisar la primera y la segunda página.

**Esperado**: la primera página contiene los más urgentes del conjunto completo; no hay tickets repetidos ni omitidos entre páginas; el total de páginas y el número de resultados son correctos.

### V-20. Accesibilidad (FR-022, RN-16)

1. Navegar la vista solo con teclado (Tab, Shift+Tab, Enter, Espacio).
2. Activar un lector de pantalla.
3. Revisar contraste con una herramienta o el inspector.

**Esperado**: todos los filtros, enlaces, paginación y botones son accesibles; el foco es visible; la tabla tiene encabezados asociados; el estado de SLA se anuncia con texto e icono, no solo color; el contraste de texto cumple 4.5:1.

### V-21. Título largo y categoría ausente (casos límite)

**Esperado**: un título largo se trunca visualmente sin romper la fila y permite acceder al texto completo (título o detalle). Un ticket sin categoría muestra "Sin categoría" y sigue listándose y ordenándose. El número y el título enlazan a `/tickets/:id`; el contenido de esa vista pertenece a la HU-06 y no se valida en esta historia.

### V-22. Prioridad desactivada (caso límite)

1. Desactivar la prioridad "Alta" en el catálogo (sin borrarla).
2. Abrir la cola de A.

**Esperado**: los tickets Alta siguen mostrando su prioridad almacenada y mantienen su posición; el filtro de prioridad la incluye y la marca como inactiva si el diseño lo indica. No se rompe el listado.

### V-23. Arranque contenerizado y persistencia (FR-037–FR-043, RNF-09–RNF-13, SC-013)

1. En un equipo con Docker y sin Python, Node ni PostgreSQL instalados, clonar el repositorio y ejecutar `docker compose up --build`.
2. Abrir `http://localhost:8080/cola-de-trabajo` y comprobar que la SPA carga y que las peticiones `/api/...` llegan al backend.
3. Aplicar el seed opcional con `docker compose exec backend python scripts/seed_dev.py`, crear o modificar datos y comprobar que persisten.
4. Ejecutar `docker compose down` y después `docker compose up`; verificar que los datos siguen ahí.
5. Ejecutar `docker compose down -v` y comprobar que la base vuelve a empezar vacía tras un nuevo arranque.

**Esperado**: los tres servicios arrancan sanos, las migraciones se aplican solas, la SPA y la API responden, el volumen conserva los datos entre reinicios y solo se borran con `down -v`. No se requiere ningún comando manual de inicialización ni hay secretos reales en el repositorio.

---

## 5.1. Registro de evidencia (2026-10-31, actualizado el 2026-11-01)

Esta sección registra qué parte de cada escenario queda demostrada por la suite automatizada y qué parte exige una comprobación humana en navegador. Se ejecutó la suite completa en el entorno de desarrollo:

- Backend (SQLite): `backend/.venv/Scripts/python.exe -m pytest -q` → **57 passed**.
- Backend (PostgreSQL 16.15, contenedor Docker con base desechable): `pytest -q` → **57 passed**.
- Frontend unitario: `npm run test:unit` → **32 passed**.
- Frontend componentes: `npm run test:components` → **43 passed**.
- Contenedores (2026-11-01): `docker compose build` y `docker compose up -d` → `db`, `backend` y `frontend` sanos; migraciones automáticas hasta `0002_work_queue`; `GET /` → 200; `GET /healthz` → 200; `GET /api/v1/me/work-queue` a través de Nginx → 401 sin JWT; seed con 10 tickets; persistencia confirmada tras `down`/`up`; `down -v` + `up -d` deja 0 tickets. El stub de login `POST /api/v1/dev/login` emite tokens válidos (cola → 200 como técnico, 403 como supervisor) y la página `/login` muestra el formulario de acceso de desarrollo.

> Limitación del entorno: la suite por defecto usa SQLite y también se ejecutó contra PostgreSQL 16.15 (el mismo del stack Docker) con una base desechable. No se dispone de navegador interactivo ni lector de pantalla. Por eso los aspectos marcados como **⚠️ Manual** no se dan por verificados.

| Escenario | Evidencia automatizada | Estado |
|-----------|------------------------|--------|
| V-01 Solo mis tickets | `test_returns_only_authenticated_technician_tickets`, `test_injected_technician_id_is_ignored`; store: «carga la cola y guarda los datos de la respuesta» | ✅ |
| V-02 Orden por prioridad y tiempo | `test_order_priority_then_deadline_then_number`, `test_sla_parity_values_for_active_tickets` | ✅ |
| V-02 Mediana < 10 s (SC-002) | Requiere cronometraje humano sobre la vista real | ⚠️ Manual |
| V-03 Vencido en rojo + icono + texto | `test_one_second_after_deadline_is_overdue`; `SlaIndicator`: «muestra el estado vencido en rojo, con icono y texto» | ✅ |
| V-04 Próximo a vencer en ámbar | `test_long_sla_ten_minutes_remaining_is_at_risk`; `SlaIndicator`: «muestra el estado próximo a vencer en ámbar» | ✅ |
| V-05 Umbral con SLA corto | `test_short_sla_twenty_minutes_remaining_is_on_time`, `test_short_sla_boundary_15_30_is_on_time`, `test_short_sla_exact_threshold_is_at_risk`; `sla.spec`: «aplica el umbral corto de un SLA de 30 min (borde 15:30)» | ✅ |
| V-06 Límite exacto y vencimiento | `test_exact_zero_is_at_risk`, `test_one_second_after_deadline_is_overdue`; `SlaIndicator`: «muestra "Vence ahora" en el límite exacto sin marcarlo como vencido»; `sla.spec`: «clasifica el límite exacto y un segundo después» | ✅ |
| V-07 Sin SLA | `test_no_sla_when_deadline_missing`, `test_order_priority_then_deadline_then_number` (NULLS LAST); `SlaIndicator`: «muestra "Sin SLA definido" sin alarma» | ✅ |
| V-08 Filtro por estado | `test_filter_by_status`, `test_finalized_only_filter_and_historical_outcome`; `WorkQueueFilters`: selección/deselección de estado | ✅ |
| V-09 Filtro por prioridad | `test_filter_by_priority_level`; `WorkQueueFilters`: selección/deselección de prioridad | ✅ |
| V-10 Filtros combinados + URL + limpieza | `test_combined_filters_use_and`; store: «lee los filtros válidos de la URL», «descarta los valores de URL inválidos», «aplica debounce…», «limpia los filtros…»; `WorkQueueFilters`: «emite "clear"…» | ✅ |
| V-10 Mediana < 15 s (SC-006) | Requiere cronometraje humano sobre la vista real | ⚠️ Manual |
| V-11 Finalizados al final y por fecha | `test_finalized_are_last_and_ordered_by_finalized_at_desc`, `test_finalized_only_filter_and_historical_outcome`; `SlaIndicator`: finalizado cumplido/incumplido/sin SLA | ✅ |
| V-12 Sin asignaciones | `test_technician_without_tickets_gets_empty_queue`; store: «distingue cola vacía, solo finalizados y sin resultados»; `WorkQueueFilters`: «no ofrece "Limpiar filtros" en el vacío sin asignaciones» | ✅ |
| V-13 Solo finalizados | `test_only_finalized_technician_gets_empty_default_items`; store: «distingue cola vacía…»; `WorkQueueStates`: «distingue los tres estados vacíos», «muestra el estado solo finalizados…» | ✅ |
| V-14 Filtros sin resultados | `test_empty_page_shape_when_no_match`; `WorkQueueFilters`: «muestra el estado no_results con acción para limpiar filtros» | ✅ |
| V-15 Error de carga y reintento | `test_unexpected_error_returns_500`; store: «mapea 500 a server y conserva los datos previos al refrescar» | ⚠️ Manual (render de `WorkQueueErrorState` y reintento en vivo) |
| V-16 Sesión caducada | `test_expired_token_returns_401`; store: «mapea 401 a unauthorized», «se recupera al volver a la vista tras un 401 y una sesión renovada» | ⚠️ Manual (redirección real a login y retorno) |
| V-17 Actualización automática ≤ 60 s | store: «sondea cada 60 s mientras la pestaña está visible», «recarga al recuperar el foco de la ventana», «cancela la petición anterior con AbortController», «ignora respuestas fuera de orden…» | ⚠️ Manual (reasignación real desde otra sesión) |
| V-18 Cambio de hora oficial | `test_dst_spring_forward_keeps_real_utc_seconds`, `test_dst_fall_back_keeps_real_utc_seconds`; la cola no muestra fechas absolutas y las duraciones usan `remaining_seconds` + `performance.now()` (`sla.spec`, `useSlaClock`) | ✅ (regresión DST; simulación de reloj de navegador no ejecutada) |
| V-19 Paginación | `test_pagination_without_overlaps`, `test_page_out_of_range_returns_last_page` | ✅ |
| V-20 Accesibilidad | `WorkQueueAccessibility`: axe-core sin violaciones críticas en tabla, filtros, vacíos, errores y paginación; `WorkQueueTable`: «renderiza una tabla semántica con caption oculto…»; `WorkQueueFilters`: «asocia cada etiqueta a su checkbox y permite foco por teclado»; `SlaIndicator`: «usa icono decorativo y texto visible, sin aria-live por tick». Contraste calculado sobre los mapas estáticos: mínimo **6,80:1** (todos ≥ 4,5:1) | ⚠️ Manual (lector de pantalla y foco visible real) |
| V-21 Título largo y categoría ausente | `WorkQueueTable`: «trunca el título largo sin perder el texto completo», «muestra "Sin categoría"…», «enlaza el número y el título al detalle del ticket» | ✅ |
| V-22 Prioridad desactivada | `WorkQueueTable`: «marca las prioridades inactivas sin romper el orden ni la alineación»; `WorkQueueFilters`: «marca las prioridades inactivas y las mantiene filtrables» | ✅ |
| V-23 Arranque contenedizado y persistencia | `docker compose build` y `docker compose up -d` reales: servicios sanos, migración automática a `0002_work_queue`, `/` y `/healthz` → 200, proxy `/api/v1/me/work-queue` → 401 sin JWT, seed de 10 tickets persistente tras `down`/`up` y borrado con `down -v` | ✅ |

**Pendiente de validación manual en navegador** (no bloquea la corrección automatizada, sí el cierre formal de la historia):

1. V-02 y V-10: medianas cronometradas de SC-002 y SC-006.
2. V-15 y V-16: representación visual del error, reintento y redirección real a login.
3. V-17: reasignación en vivo desde otra sesión y refresco al recuperar el foco.
4. V-20: recorrido con teclado y lector de pantalla.

---

## 6. Criterios de aceptación de la validación

La funcionalidad se considera validada cuando:

- [x] Todas las pruebas automatizadas de backend y frontend pasan.
- [ ] Los 23 escenarios manuales (V-01 a V-23) pasan. _(Pendiente: ver «Pendiente de validación manual en navegador» en §5.1.)_
- [x] `GET /api/v1/me/work-queue` responde según el contrato OpenAPI.
- [x] No se puede acceder a tickets de otro técnico por ningún parámetro ni enlace.
- [x] La primera página contiene los tickets más urgentes del conjunto completo.
- [x] El estado de SLA se distingue sin depender del color.
- [x] Los estados vacío, sin resultados y error son visualmente distintos.
- [x] La cola se actualiza en ≤ 60 s sin recargar.
- [x] No hay secretos ni datos personales innecesarios en la respuesta ni en los logs.

---

## 7. Solución de problemas

| Síntoma | Comprobación |
|---------|--------------|
| La cola siempre está vacía | Verificar que el usuario autenticado tiene rol `tecnico` y que `tickets.assignee_id` apunta a su `id`. |
| Todos los tickets aparecen vencidos | Revisar que `sla_deadline` se guardó en UTC y que el servidor no está aplicando una conversión local. |
| El orden de prioridad está invertido | Confirmar la convención `level` 1 = Crítica; si el esquema real es la inversa, ajustar `ORDER BY` y fixtures. |
| Un finalizado no aparece al filtrar | Comprobar que `finalized_at` no es nulo y que la restricción de coherencia se aplicó en la migración. |
| Los colores no se aplican en producción | Verificar que las clases están en los mapas estáticos y que Tailwind las incluye en el build (no usar interpolación). |
| El contador se desvía del reloj | Asegurar que el frontend usa `remaining_seconds` + `performance.now()` y no `new Date()` contra el deadline. |
| Error 403 al abrir la cola | El usuario no tiene rol de técnico; esta vista no está disponible para usuario, supervisor ni admin. |

---

## 8. Referencias

- Especificación: [spec.md](./spec.md)
- Plan técnico: [plan.md](./plan.md)
- Decisiones: [research.md](./research.md)
- Modelo de datos: [data-model.md](./data-model.md)
- Contrato: [contracts/work-queue.openapi.yaml](./contracts/work-queue.openapi.yaml)
- Modelo base: [../001-helpdesk-ticketing/spec.md](../001-helpdesk-ticketing/spec.md)
