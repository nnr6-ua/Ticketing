# Plan de Implementación: Cola de Trabajo Priorizada (HU-04)

**Rama**: `hu-04-cola-trabajo` | **Fecha**: 2026-10-29 | **Spec**: [spec.md](./spec.md)

**Entrada**: Especificación de la funcionalidad en `specs/004-prioritized-work-queue/spec.md`

**Documentos de diseño**: [research.md](./research.md) · [data-model.md](./data-model.md) · [contracts/work-queue.openapi.yaml](./contracts/work-queue.openapi.yaml) · [quickstart.md](./quickstart.md)

## Resumen

La funcionalidad entrega una vista personal de solo lectura en la que un técnico autenticado ve exclusivamente sus tickets asignados, ordenados por prioridad descendente y, dentro de cada prioridad, por menor tiempo restante de SLA. Incluye filtros combinables por estado y prioridad, destacado visual accesible de tickets próximos a vencer o vencidos, estados vacíos diferenciados, paginación y actualización automática cada 60 segundos.

El enfoque técnico es deliberadamente simple:

- **Backend FastAPI**: un único endpoint `GET /api/v1/me/work-queue` que resuelve identidad, visibilidad, filtrado, ordenación, cálculo de SLA y paginación en PostgreSQL. El cliente nunca envía el identificador del técnico.
- **Frontend Vue 3 + Pinia + Tailwind**: una página `WorkQueuePage`, un store que sincroniza filtros con la URL y componentes pequeños para filtros, tabla, fila e indicador de SLA. El formato condicional usa mapas estáticos de clases Tailwind, nunca interpolación dinámica.
- **Tiempo y SLA**: todas las fechas se almacenan y transportan en UTC (`TIMESTAMPTZ` / ISO 8601 con `Z`). El backend devuelve segundos restantes calculados contra el reloj del servidor; el frontend los consume como duración relativa y los decrementa con un reloj monotónico, sin depender de la hora local del navegador. Europe/Madrid se usa solo para formatear fechas absolutas.
- **Contenerización**: una imagen multi-etapa con destinos `backend` y `frontend` y un `docker-compose.yml` que levanta PostgreSQL 16, aplica las migraciones al arrancar y sirve la SPA con Nginx, con datos persistentes en un volumen y configuración por variables de entorno.

Esta historia no crea, edita, reasigna ni cambia estados de tickets: consume el modelo de datos base definido en `specs/001-helpdesk-ticketing/spec.md`.

## Contexto Técnico

**Lenguaje/Versión**: Python 3.12 (backend), TypeScript 5.x sobre Vue 3.5 (frontend)

**Dependencias principales**:
- Backend: FastAPI, SQLAlchemy 2.0 (modo síncrono), psycopg 3, Alembic, Pydantic 2, Uvicorn.
- Frontend: Vue 3.5, Vite, Pinia, Vue Router, Tailwind CSS 3.4, `lucide-vue-next` para iconos.
- Autenticación: JWT Bearer. La dependencia existente del proyecto valida el token enviado en `Authorization: Bearer <token>` y resuelve el usuario autenticado y su rol (integración, no se implementa aquí).

**Almacenamiento**: PostgreSQL 16. Tabla `tickets` del modelo base más la columna `finalized_at` y los índices descritos en [data-model.md](./data-model.md). Zona horaria de base de datos en UTC; columnas temporales `TIMESTAMPTZ`.

**Testing**:
- Backend: `pytest`, `pytest-asyncio` solo si la app es async (la propuesta es síncrona), `httpx` para pruebas de API y una base PostgreSQL de test.
- Frontend: `Vitest` + `@vue/test-utils`, `@testing-library/vue` opcional, `axe-core` para una comprobación básica de accesibilidad.
- Contrato: pruebas de contrato contra `contracts/work-queue.openapi.yaml` y vectores compartidos de cálculo de SLA para garantizar paridad backend/frontend.

**Plataforma objetivo**: aplicación web (backend Linux/contenedor + navegadores de escritorio y tablet). No se requiere experiencia móvil específica en esta historia.

**Despliegue**: Docker Compose v2 sobre Docker Engine. Servicios `db` (PostgreSQL 16), `backend` (FastAPI/Uvicorn) y `frontend` (Nginx con la SPA compilada y proxy `/api`). El backend ejecuta `alembic upgrade head` con reintentos en el entrypoint. Los datos viven en el volumen nombrado `ticketing_db_data`; la configuración se inyecta por variables de entorno desde `.env` (documentadas en `.env.example`). El frontend se publica en `http://localhost:8080` y la API en `http://localhost:8000`.

**Objetivos de rendimiento**:
- p95 de la vista completa < 2 s con hasta 100 tickets asignados (SC-005).
- Consulta SQL de la página < 300 ms con 100 tickets y los índices propuestos.
- Actualización automática cada 60 s sin recargar la página (FR-005).
- Primera página con los tickets más urgentes del conjunto completo, no solo de la página (FR-017).

**Restricciones**:
- Solo lectura: ningún endpoint `POST`, `PUT`, `PATCH` o `DELETE` en esta historia.
- La identidad del técnico se deriva del token JWT de `Authorization: Bearer`; no se acepta `technician_id`, `assignee_id` ni equivalente como parámetro.
- Interfaz y mensajes en español de España; fechas absolutas en Europe/Madrid.
- Sin claves ni secretos en código; configuración por variables de entorno.
- Sin caché de respuestas: la cola debe reflejar reasignaciones y cambios de estado en ≤ 60 s.
- Accesibilidad WCAG 2.1 AA: color, icono y texto; navegación por teclado.

**Escala/Alcance**: hasta 100 tickets activos por técnico y una página de 25 elementos por defecto (máximo 100). Una sola vista, un endpoint y un store. Sin colas de equipo, sin notificaciones push, sin edición de tickets.

**Límite de alcance sobre el detalle del ticket**: esta historia garantiza que un ticket reasignado desaparece de la cola en el siguiente refresco (≤ 60 s). El aviso dentro de una vista de detalle ya abierta pertenece a la HU-06 (detalle y reasignación); la cola no implementa esa vista ni un panel lateral propio. Se deja constancia para que la prueba de reasignación se limite a la cola.

## Constitution Check

*GATE: debe pasar antes de la Fase 0 y re-evaluarse tras la Fase 1.*

> La constitución aplicable está ratificada en `.specify/memory/constitution.md` (copia de `CONSTITUTION.md` en la raíz del repositorio). Se aplican sus cinco principios rectores.

| Principio | Cumplimiento | Evidencia en el diseño |
|-----------|--------------|------------------------|
| **1. Simplicidad ante todo** | ✅ Pasa | Un endpoint, una vista, un store, sin caché, sin WebSockets, sin ordenación configurable ni columnas personalizables. La paginación por offset es suficiente para ≤ 100 tickets. El umbral de SLA se deriva de fechas ya almacenadas. |
| **2. Idioma y mercado** | ✅ Pasa | Toda la interfaz, etiquetas, estados vacíos y errores en español de España. Fechas y horas con `Intl` y `Europe/Madrid`. No hay importes monetarios en esta historia. |
| **3. Cero alcance fantasma** | ✅ Pasa | Solo se implementa lo exigido por `spec.md`: consulta, orden, filtros, destacado, estados vacíos, error, paginación y refresco. No se añaden reasignación, cambio de estado, notificaciones ni edición. `finalized_at` e índices son soporte mínimo de requisitos existentes (FR-034, FR-035, SC-005), no funcionalidad nueva. |
| **4. Verificable por persona no técnica** | ✅ Pasa | [quickstart.md](./quickstart.md) describe escenarios manuales observables (cola propia, orden, colores, filtros, vacíos, error) sin leer código. |
| **5. Datos del usuario con respeto** | ✅ Pasa | La consulta se limita al usuario autenticado; no se expone ni se acepta el identificador de otro técnico. La respuesta incluye solo los campos necesarios para la fila. Sin secretos en código; configuración por entorno. |

**Resultado del gate**: sin violaciones. No se requiere sección de complejidad justificada.

## Estructura del Proyecto

### Documentación de la funcionalidad

```text
specs/004-prioritized-work-queue/
├── plan.md                              # Este archivo
├── research.md                          # Fase 0: decisiones y alternativas
├── data-model.md                        # Fase 1: entidades, columnas, derivados e índices
├── quickstart.md                        # Fase 1: guía de validación ejecutable
├── contracts/
│   └── work-queue.openapi.yaml          # Fase 1: contrato HTTP
├── checklists/
│   └── requirements.md                  # Checklist de calidad de la spec
└── tasks.md                             # Fase 2 (/speckit.tasks, no generado aquí)
```

### Código fuente (raíz del repositorio)

El repositorio aún no contiene código de aplicación. Se adopta la estructura web backend + frontend, coherente con la pila compartida del proyecto. La migración `0001_base_schema.py` crea el esquema base de `specs/001-helpdesk-ticketing/spec.md` y el seed determinista permite ejecutar los escenarios de validación.

```text
Dockerfile                               # Imagen multi-etapa: backend y frontend
.dockerignore                            # Exclusiones del contexto de build
docker-compose.yml                       # db + backend + frontend, volumen y healthchecks
.env.example                             # Variables de entorno sin secretos reales
README.md                                # Arranque, comandos y solución de problemas

backend/
├── app/
│   ├── main.py                          # Creación de la app FastAPI
│   ├── api/
│   │   ├── deps.py                      # Dependencias: sesión DB, usuario autenticado, rol
│   │   └── v1/
│   │       ├── router.py                # Inclusión de routers v1
│   │       └── work_queue.py            # GET /api/v1/me/work-queue
│   ├── core/
│   │   ├── config.py                    # Configuración por variables de entorno
│   │   └── errors.py                    # Respuestas de error homogéneas
│   ├── db/
│   │   ├── base.py                      # Declarative Base
│   │   └── session.py                   # Engine y SessionLocal (timezone UTC)
│   ├── models/
│   │   ├── ticket.py                    # Ticket + finalized_at
│   │   ├── priority.py                  # Prioridad (nivel 1-4)
│   │   ├── category.py                  # Categoría
│   │   └── user.py                      # Usuario/técnico
│   ├── schemas/
│   │   └── work_queue.py                # Pydantic: request query y response models
│   ├── services/
│   │   └── work_queue.py                # Consulta, filtros, orden y paginación
│   └── utils/
│       └── sla.py                       # Cálculo canónico de SLA
├── docker/
│   └── entrypoint.sh                    # Migraciones con reintentos + Uvicorn
├── alembic/
│   └── versions/
│       ├── 0001_base_schema.py
│       └── 0002_add_finalized_at_and_work_queue_indexes.py
├── scripts/
│   └── seed_dev.py
└── tests/
    ├── unit/test_sla.py
    ├── integration/test_work_queue_api.py
    └── contract/test_work_queue_contract.py

frontend/
├── nginx.conf                           # SPA + proxy inverso /api → backend:8000
├── src/
│   ├── api/
│   │   ├── client.ts                    # fetch tipado, Bearer JWT, normalización de errores
│   │   └── workQueue.ts                 # GET /api/v1/me/work-queue
│   ├── components/
│   │   └── work-queue/
│   │       ├── WorkQueueFilters.vue
│   │       ├── WorkQueueTable.vue
│   │       ├── WorkQueueRow.vue
│   │       ├── SlaIndicator.vue
│   │       ├── PriorityBadge.vue
│   │       ├── StatusBadge.vue
│   │       ├── WorkQueueEmptyState.vue
│   │       ├── WorkQueueErrorState.vue
│   │       ├── WorkQueuePagination.vue
│   │       └── WorkQueueSkeleton.vue
│   ├── composables/
│   │   └── useSlaClock.ts               # Ticker monotónico y resincronización
│   ├── router/
│   │   └── index.ts                     # Ruta /cola-de-trabajo
│   ├── stores/
│   │   └── workQueue.ts                 # Estado, filtros URL, polling, errores
│   ├── types/
│   │   └── workQueue.ts                 # Tipos del contrato
│   ├── utils/
│   │   ├── sla.ts                       # Clasificación y formato de duraciones
│   │   └── slaStyles.ts                 # Mapas estáticos de clases Tailwind
│   ├── views/
│   │   └── WorkQueuePage.vue
│   └── main.ts
└── tests/
    ├── unit/sla.spec.ts
    ├── unit/workQueue.store.spec.ts
    └── components/WorkQueue*.spec.ts
```

**Decisión de estructura**: aplicación web separada en `backend/` y `frontend/`, sin monorepo adicional ni paquetes compartidos. La paridad del cálculo de SLA se garantiza con vectores de prueba duplicados, no con código compartido entre Python y TypeScript, para no introducir una capa de build innecesaria.

## Diseño Detallado

### 1. Backend FastAPI: endpoint de cola de trabajo

#### 1.1 Contrato HTTP

Un único endpoint de lectura:

```http
GET /api/v1/me/work-queue
```

No existe endpoint `/meta` separado: las opciones de filtro y la marca de tiempo del servidor viajan en la misma respuesta para reducir llamadas y mantener una única fuente de verdad.

**Autenticación**: obligatoria mediante **Bearer JWT**. La dependencia `get_current_user` valida el token de `Authorization: Bearer <token>` y resuelve el usuario. Si falta el token, no es válido o ha caducado → `401`. Si el rol no es `tecnico` → `403`. No se usa cookie de sesión ni `credentials: 'include'` en el cliente. El endpoint no acepta ningún parámetro de técnico; si el cliente envía `technician_id`, `assignee_id` o similar, se ignora y la consulta sigue usando exclusivamente `current_user.id` (además, el contrato no los declara y las pruebas verifican que no amplían la visibilidad).

**Parámetros de consulta**:

| Parámetro | Tipo | Obligatorio | Regla |
|-----------|------|-------------|-------|
| `status` | lista de códigos separados por coma | No | Si se omite, se aplican los estados activos por defecto: `abierto,en_progreso,pendiente_usuario`. Si se envía, puede incluir estados activos y finales (`resuelto,cerrado`). Un código desconocido o una lista vacía → `422`. |
| `priority` | lista de niveles separados por coma | No | Niveles numéricos 1-4 (`1`=Crítica, `4`=Baja). Si se omite, no se filtra por prioridad. Valores fuera de 1-4 o no numéricos → `422`. |
| `page` | entero ≥ 1 | No | Por defecto `1`. |
| `page_size` | entero 1-100 | No | Por defecto `25`. |

Los filtros se combinan con lógica **Y** (FR-025). El orden no es configurable por el cliente: la spec fija un único orden por urgencia.

**Respuesta `200 OK`** (resumen; contrato completo en [work-queue.openapi.yaml](./contracts/work-queue.openapi.yaml)):

```json
{
  "items": [
    {
      "id": "5f0c2f7e-…",
      "number": "TK-000123",
      "title": "No puedo acceder a la VPN desde casa",
      "category": { "id": "…", "name": "Red", "is_active": true },
      "priority": { "id": "…", "name": "Crítica", "level": 1, "color": "#dc2626", "is_active": true },
      "status": "en_progreso",
      "status_label": "En progreso",
      "is_final": false,
      "sla": {
        "deadline": "2026-10-29T12:00:00Z",
        "started_at": "2026-10-29T08:00:00Z",
        "total_seconds": 14400,
        "remaining_seconds": 5400,
        "warning_threshold_seconds": 3600,
        "state": "on_time",
        "outcome": null,
        "finalized_at": null,
        "breach_delay_seconds": null
      },
      "links": { "self": "/api/v1/tickets/5f0c2f7e-…" }
    }
  ],
  "pagination": {
    "page": 1,
    "page_size": 25,
    "total_items": 42,
    "total_pages": 2,
    "has_next": true,
    "has_previous": false
  },
  "counts": {
    "active": 30,
    "finalized": 12
  },
  "available_filters": {
    "statuses": [
      { "value": "abierto", "label": "Abierto", "is_final": false },
      { "value": "en_progreso", "label": "En progreso", "is_final": false },
      { "value": "pendiente_usuario", "label": "Pendiente de usuario", "is_final": false },
      { "value": "resuelto", "label": "Resuelto", "is_final": true },
      { "value": "cerrado", "label": "Cerrado", "is_final": true }
    ],
    "priorities": [
      { "id": "…", "name": "Crítica", "level": 1, "color": "#dc2626", "is_active": true }
    ],
    "default_statuses": ["abierto", "en_progreso", "pendiente_usuario"]
  },
  "applied_filters": {
    "status": ["abierto", "en_progreso", "pendiente_usuario"],
    "priority": [],
    "is_default": true
  },
  "meta": {
    "server_time": "2026-10-29T10:30:00Z",
    "timezone": "Europe/Madrid",
    "warning_policy": {
      "short_sla_threshold_minutes": 60,
      "short_sla_ratio": 0.5,
      "long_sla_minimum_minutes": 60,
      "long_sla_ratio": 0.25
    }
  }
}
```

**Cálculo de `counts`**:
- `counts.active` y `counts.finalized` se calculan sobre **toda** la cola del técnico, sin aplicar los filtros actuales, y solo se usan para distinguir el estado vacío por falta de asignaciones del estado "solo finalizados" (FR-030).
- `pagination.total_items` es el número de tickets que cumplen los filtros (FR-026).

**Errores**: `401` token ausente, inválido o caducado; `403` rol no autorizado; `422` parámetros inválidos; `500` error inesperado con mensaje genérico en español y sin filtrar detalles internos. La respuesta de error sigue el formato `{ "detail": { "code": "...", "message": "..." } }`.

**Cabeceras**: `Cache-Control: no-store`, `Vary: Authorization` (transporte único Bearer JWT). No se usa ETag.

#### 1.2 Resolución de identidad y visibilidad

```text
current_user = get_current_user(request)  # valida Authorization: Bearer <JWT>
if current_user is None: 401
if current_user.role != "tecnico": 403

assignee_filter = Ticket.assignee_id == current_user.id
```

La condición de propiedad se añade **siempre** a la consulta, antes de filtros y paginación. No existe ninguna ruta alternativa que reciba el técnico por parámetro. Los filtros se aplican como predicados adicionales (`AND`), por lo que nunca pueden ampliar el conjunto (FR-002, FR-029).

#### 1.3 Ordenación SQL

El orden se aplica al conjunto completo y antes de paginar (FR-017). La consulta usa una única cláusula `ORDER BY` que separa activos y finalizados:

```sql
SELECT ...
FROM tickets AS t
JOIN priorities AS p ON p.id = t.priority_id
LEFT JOIN categories AS c ON c.id = t.category_id
WHERE t.assignee_id = :current_user_id
  AND t.status = ANY(:status_filter)          -- por defecto estados activos
  AND (:priority_filter_is_empty OR p.level = ANY(:priority_filter))
ORDER BY
  -- 1) Activos (0) antes que finalizados (1)
  CASE WHEN t.status IN ('resuelto', 'cerrado') THEN 1 ELSE 0 END ASC,

  -- 2) Activos: prioridad de mayor a menor (nivel 1 = Crítica)
  CASE WHEN t.status IN ('resuelto', 'cerrado') THEN NULL ELSE p.level END ASC NULLS LAST,

  -- 3) Activos: menor tiempo restante = menor deadline; sin SLA al final
  CASE WHEN t.status IN ('resuelto', 'cerrado') THEN NULL ELSE t.sla_deadline END ASC NULLS LAST,

  -- 4) Finalizados: más recientemente finalizado primero
  CASE WHEN t.status IN ('resuelto', 'cerrado') THEN t.finalized_at ELSE NULL END DESC NULLS LAST,

  -- 5) Desempate estable por número de ticket ascendente
  t.number ASC
LIMIT :page_size OFFSET :offset;
```

Equivalencias y justificación:

- **Prioridad descendente**: `p.level ASC` porque el modelo base define `nivel` 1-4 y se asume 1 = Crítica, 4 = Baja (documentado en [data-model.md](./data-model.md)). Si el proyecto confirma la convención inversa, se cambia únicamente este término y sus pruebas.
- **Tiempo restante ascendente**: con un límite SLA fijo, ordenar por `sla_deadline ASC` equivale a ordenar por `deadline - now ASC`; los vencidos tienen deadlines pasados y quedan primero dentro de su prioridad (FR-014). Los tickets sin SLA (`sla_deadline IS NULL`) quedan al final de su prioridad (`NULLS LAST`, FR-015).
- **Finalizados al final**: la primera clave los agrupa después de todos los activos, con independencia de su prioridad (FR-035, RN-17).
- **Finalizados por fecha de finalización**: `finalized_at DESC NULLS LAST` y desempate por `number ASC`.
- **Desempate global**: `number ASC` garantiza un orden total y estable para la paginación (FR-016).
- **Categoría opcional**: el `LEFT JOIN` con `categories` evita excluir tickets sin categoría, que deben mostrarse como "Sin categoría" (caso límite de la spec).

**Recuentos y paginación**: se ejecutan tres consultas sobre la misma consulta base (tickets del técnico autenticado):
- `COUNT(*)` con los predicados de filtro para `pagination.total_items` (FR-026).
- La consulta paginada para `items`, con el orden total y `LIMIT/OFFSET`.
- Una consulta agregada **sin predicados de filtro** (solo `assignee_id = current_user.id`) que devuelve, en una sola pasada, `counts.finalized = COUNT(*) FILTER (WHERE status IN ('resuelto','cerrado'))` y `counts.active` como el resto. Es imprescindible para distinguir «sin asignaciones» de «solo finalizados» (FR-030) aunque haya filtros activos.

`offset = (page - 1) * page_size`. Si `page` supera el total de páginas, el servidor la ajusta a la última página disponible (`total_pages`) y devuelve esa página efectiva en `pagination.page`; si no hay resultados, devuelve `items: []` con `page: 1`. El frontend sincroniza la URL con la página efectiva, de modo que nunca se muestra una página vacía por un número fuera de rango.

#### 1.4 Servicio y capas

- `api/v1/work_queue.py`: valida parámetros con Pydantic/FastAPI, obtiene `current_user`, llama al servicio y serializa.
- `services/work_queue.py`: construye la consulta base, aplica filtros, ejecuta el conteo filtrado, la consulta agregada sin filtros de `counts` y la página, calcula derivados de SLA y ensambla `counts`/`available_filters`. `counts` y `available_filters` se calculan siempre sobre toda la cola del técnico, sin filtros; el filtrado solo afecta a `items` y `pagination.total_items`.
- `utils/sla.py`: funciones puras y testeables:
  - `classify_sla(*, is_final, deadline, started_at, now) -> SlaState`
  - `warning_threshold_seconds(total_seconds) -> int`
  - `sla_outcome(finalized_at, deadline) -> "met" | "breached" | "no_sla"`
  - `breach_delay_seconds(finalized_at, deadline) -> int | None`
- `schemas/work_queue.py`: modelos Pydantic de respuesta y validación de query params. Se usa `response_model` para que el contrato quede garantizado por tipos.

No se introduce una capa de repositorio genérica: el servicio usa SQLAlchemy directamente. Es la opción más simple para una única consulta de lectura.

#### 1.5 Índices y migración

Migración Alembic mínima:

1. Añadir `tickets.finalized_at TIMESTAMPTZ NULL`.
2. Rellenar `finalized_at` de tickets ya finalizados (ver [data-model.md](./data-model.md)).
3. Añadir restricciones: `ck_tickets_finalized_at` (estado final ⇒ `finalized_at` no nulo; no final ⇒ nulo), `ck_tickets_finalized_after_created` (`finalized_at >= created_at`) y `ck_tickets_sla_deadline_after_created` (`sla_deadline >= created_at`).
4. Crear índices:
   - `ix_tickets_assignee_status_deadline (assignee_id, status, sla_deadline)`.
   - `ix_tickets_assignee_finalized_at (assignee_id, finalized_at DESC)`.
   - `ix_tickets_assignee_priority (assignee_id, priority_id)`.
   - `ix_tickets_number (number)`.

No se modifican `sla_deadline`, prioridad ni categoría: esta historia solo lee los valores congelados del ticket (RN-03).

### 2. Frontend Vue 3: vista, componentes y formato condicional

#### 2.1 Ruta y estado

- Ruta: `/cola-de-trabajo`, nombre `work-queue`, componente `WorkQueuePage.vue`.
- Los filtros viven en la query de la URL (`estado`, `prioridad`, `pagina`) y en el store Pinia. Esto cumple FR-028 (se mantienen durante la navegación) y permite atrás/adelante y recarga sin perder el estado.
- El número y el título de cada fila enlazan a la ruta de detalle `/tickets/:id`, que pertenece a la HU-06. Esta historia no crea ni modifica esa vista: hasta que exista, el enlace puede devolver 404 y no se valida su contenido.
- Al montar, el store lee la URL, valida los valores contra `available_filters` y normaliza los inválidos. Si no hay filtros explícitos, se aplica el conjunto activo por defecto sin enviar `status` al backend.
- Cambios de filtro: actualizan la URL con `router.replace`, reinician `page = 1` y lanzan una petición con debounce de 250 ms.
- Polling: `setInterval` de 60 s mientras la pestaña está visible; `visibilitychange` y `focus` fuerzan una recarga inmediata al volver. Cada petición cancela la anterior con `AbortController` para evitar respuestas fuera de orden.

#### 2.2 Store Pinia (`stores/workQueue.ts`)

Estado:

```ts
interface WorkQueueState {
  items: WorkQueueItem[]
  pagination: Pagination
  counts: WorkQueueCounts
  availableFilters: AvailableFilters
  appliedFilters: { status: TicketStatus[]; priority: number[] }
  isDefaultFilter: boolean
  loading: boolean          // solo primera carga o recarga manual
  refreshing: boolean       // refresco silencioso
  error: WorkQueueError | null
  lastUpdatedAt: number | null
  serverTime: string | null
  requestId: string | null
}
```

Acciones/getters:

- `fetchQueue({ silent })`: construye query params, llama a `api/workQueue.ts`, reemplaza estado y guarda `lastUpdatedAt` calculado con `performance.now()`.
- `setStatusFilter(statuses)`, `setPriorityFilter(levels)`, `clearFilters()`, `setPage(page)`.
- `startPolling()` / `stopPolling()` ligados al ciclo de vida de la página.
- Getters: `isEmptyQueue` (sin asignaciones y sin filtros), `isNoResults` (filtros activos y `total_items === 0`), `hasOnlyFinalized` (sin filtros, `active === 0`, `finalized > 0`), `degraded` (error durante refresco con datos previos).
- Errores: `401` → redirige a login conservando `redirect=/cola-de-trabajo`; `403` → mensaje de acceso no autorizado; red/timeout/`5xx` → estado de error con reintento. Si ya había datos, se mantienen y se muestra un aviso discreto de "no se pudo actualizar", sin sustituir la tabla por un error de pantalla completa.

#### 2.3 Componentes

| Componente | Responsabilidad |
|------------|-----------------|
| `WorkQueuePage.vue` | Orquesta cabecera, filtros, número de resultados, tabla, paginación y estados. Inicia/detiene polling. |
| `WorkQueueFilters.vue` | Dos grupos de filtros accesibles (`fieldset` + `legend`): estados y prioridades. Checkboxes tipo chip y botón "Limpiar filtros". Emite cambios; no llama a la API. |
| `WorkQueueTable.vue` | Tabla semántica con `<caption>` oculto, columnas Ticket, Título, Categoría, Prioridad, Estado y SLA. Renderiza filas o el estado vacío/error que corresponda. |
| `WorkQueueRow.vue` | Fila con los cinco datos exigidos (FR-006) más estado. Aplica el mapa estático de clases de riesgo. El número/título enlaza a `/tickets/:id` (detalle de la HU-06, solo lectura; no se implementa aquí). |
| `SlaIndicator.vue` | Muestra icono + texto + duración. Recibe `state` y `remainingSeconds`; usa `formatRemaining` y `aria-hidden` en el icono, con texto visible suficiente. |
| `PriorityBadge.vue` | Etiqueta de prioridad con color estático por nivel y texto. |
| `StatusBadge.vue` | Etiqueta de estado en español. |
| `WorkQueueEmptyState.vue` | Variantes: `no_assignments`, `only_final`, `no_results` (con "Limpiar filtros"). |
| `WorkQueueErrorState.vue` | Mensaje diferenciado + botón "Reintentar"; nunca se confunde con vacío. |
| `WorkQueuePagination.vue` | Anterior/Siguiente, página actual y total de páginas. Deshabilitado durante carga. |
| `WorkQueueSkeleton.vue` | Esqueleto de filas solo en la primera carga, sin saltos de layout. |
| `useSlaClock.ts` | Tick local cada 30 s para actualizar duraciones entre polls; devuelve un `now` reactivo y se resincroniza al recibir datos del servidor. |

La vista no incluye acciones de cambio de estado, reasignación ni edición: solo enlaces de consulta al detalle.

#### 2.4 Formato condicional con Tailwind

Se usan mapas estáticos de clases completas para que Tailwind las detecte en el build. **Nunca** se construyen clases por interpolación (`bg-${color}-100`), porque el escaneo de Tailwind no las generaría.

`utils/slaStyles.ts`:

```ts
export const SLA_ROW_CLASS: Record<SlaState, string> = {
  overdue:   'bg-red-50 border-l-4 border-red-600',
  at_risk:   'bg-amber-50 border-l-4 border-amber-500',
  on_time:   'bg-white border-l-4 border-transparent',
  no_sla:    'bg-white border-l-4 border-transparent',
  finalized: 'bg-slate-50 border-l-4 border-transparent',
}

export const SLA_BADGE_CLASS: Record<SlaState, string> = {
  overdue:   'bg-red-100 text-red-800 ring-1 ring-inset ring-red-600',
  at_risk:   'bg-amber-100 text-amber-900 ring-1 ring-inset ring-amber-500',
  on_time:   'bg-emerald-50 text-emerald-800 ring-1 ring-inset ring-emerald-200',
  no_sla:    'bg-slate-100 text-slate-700 ring-1 ring-inset ring-slate-300',
  finalized: 'bg-slate-100 text-slate-700 ring-1 ring-inset ring-slate-300',
}

export const SLA_ICON: Record<SlaState, Component> = {
  overdue: AlertOctagon,
  at_risk: AlertTriangle,
  on_time: CheckCircle2,
  no_sla: MinusCircle,
  finalized: CheckCircle2,
}
```

Reglas visuales concretas:

- **Vencido** (`overdue`): fondo rojo suave, borde izquierdo rojo, icono `AlertOctagon`, texto "Vencido hace [tiempo]" y `aria-label` completo. El rojo no es el único indicador.
- **Próximo a vencer** (`at_risk`): fondo ámbar suave, borde izquierdo ámbar, icono `AlertTriangle`, texto "Próximo a vencer · [tiempo]" o "Vence ahora" si quedan 0 segundos.
- **Dentro de plazo** (`on_time`): sin fondo de alarma, icono `CheckCircle2` y texto "Dentro de plazo · [tiempo]".
- **Sin SLA** (`no_sla`): gris neutro, icono `MinusCircle`, texto "Sin SLA definido"; nunca ámbar ni rojo.
- **Finalizado** (`finalized`): gris neutro, sin cuenta atrás ni alerta. Resultado: "Dentro de plazo" si `outcome === 'met'`; "Incumplido hace [tiempo]" si `outcome === 'breached'`; "Sin SLA definido" si `outcome === 'no_sla'`.

La prioridad usa un mapa estático por nivel (`1` Crítica → rojo, `2` Alta → naranja, `3` Media → azul, `4` Baja → gris). El color almacenado en base de datos se conserva en la respuesta para futuras vistas, pero no se usa para generar clases Tailwind. Los badges mantienen contraste ≥ 4.5:1 y combinan texto + color.

La fila completa no se vuelve clicable para evitar ambigüedad con enlaces internos; el número y el título son enlaces al detalle.

#### 2.5 Estados vacíos y errores

| Situación | Condición | Mensaje / acción |
|-----------|-----------|------------------|
| Sin asignaciones | Sin filtros, `counts.active + counts.finalized === 0` | "No tienes tickets asignados actualmente." Sin botón de reintento. |
| Solo finalizados | Sin filtros, `counts.active === 0`, `counts.finalized > 0` | "No tienes tickets activos. Puedes consultar los finalizados cambiando el filtro de estado." |
| Filtros sin resultados | Filtros activos, `pagination.total_items === 0` | "No hay resultados para los filtros seleccionados." + "Limpiar filtros". |
| Error de carga inicial | Sin datos y `error` | "No se pudo cargar tu cola de trabajo." + "Reintentar". |
| Error durante refresco | Con datos y `error` | Se mantiene la tabla y se muestra aviso "No se pudo actualizar; se muestran los últimos datos." + "Reintentar". |
| Sesión caducada (JWT) | `401` | Redirección a login y vuelta a `/cola-de-trabajo`. |

#### 2.6 Formato de duraciones (español de España)

`utils/sla.ts`:

```ts
formatRemaining(seconds: number): string
// > 86400: "3 d 4 h"
// > 3600:  "4 h 12 min"
// > 60:    "37 min"
// 1..59:   "menos de 1 min"
// 0:       "Vence ahora"          (ámbar, aún no incumplido)
// < 0:     "Vencido hace 2 h 5 min"
```

Para finalizados con incumplimiento se usa `breach_delay_seconds = finalized_at - deadline` (cuánto se rebasó el límite al finalizar) y se muestra "Incumplido hace [tiempo]" conforme al texto fijado en la spec. Este valor es estático: no crece con el tiempo transcurrido desde el cierre. En cambio, en un ticket activo vencido, "Vencido hace [tiempo]" es dinámico y sigue creciendo hasta que el ticket se finaliza.

### 3. Gestión de fechas y SLA: prevención de desajustes horarios

#### 3.1 Principios

1. **UTC en almacenamiento y transporte**. `sla_deadline`, `created_at`, `finalized_at` y `server_time` son instantes absolutos en UTC. PostgreSQL usa `TIMESTAMPTZ`; SQLAlchemy `DateTime(timezone=True)`; Pydantic serializa ISO 8601 con offset (`2026-10-29T12:00:00Z`).
2. **Duraciones relativas en el cálculo**. El backend calcula `remaining_seconds = floor((deadline - now_utc).total_seconds())`. El frontend no compara la hora del navegador con una fecha absoluta para la cuenta atrás: consume `remaining_seconds`.
3. **Europe/Madrid solo para presentar**. El cliente formatea fechas absolutas con `Intl.DateTimeFormat('es-ES', { timeZone: 'Europe/Madrid', ... })`. Las duraciones no dependen de zona horaria. El servidor no necesita convertir a hora local para ordenar ni calcular.
4. **Reloj monotónico en el cliente**. Entre polls, la cuenta atrás se decrementa con `performance.now()`, que no retrocede si cambia la hora del sistema. Cada 60 s (o al recuperar foco/visibilidad) se resincroniza con el servidor.
5. **El servidor es la autoridad**. La clasificación (`on_time`, `at_risk`, `overdue`, `no_sla`, `finalized`) se calcula en el backend al responder. El cliente puede reclasificar entre polls con la misma función y los segundos restantes, pero el siguiente poll impone el valor del servidor.

#### 3.2 Cálculo canónico de SLA (backend)

```python
SECONDS_PER_MINUTE = 60
SECONDS_PER_HOUR = 3600

def warning_threshold_seconds(total_seconds: int) -> int:
    if total_seconds < 60 * SECONDS_PER_MINUTE:          # < 60 min
        return total_seconds // 2                          # mitad del total
    return max(60 * SECONDS_PER_MINUTE, total_seconds // 4)  # max(60 min, 25 %)

def classify_sla(*, is_final, deadline, started_at, now):
    if is_final:
        return "finalized"
    if deadline is None:
        return "no_sla"
    if deadline <= started_at:          # dato corrupto: no mostrar alarma imposible
        return "no_sla"
    remaining = floor((deadline - now).total_seconds())
    if remaining < 0:
        return "overdue"
    total = floor((deadline - started_at).total_seconds())
    threshold = warning_threshold_seconds(total)
    if remaining <= threshold:   # incluye exactamente 0 → "Vence ahora"
        return "at_risk"
    return "on_time"
```

Notas:
- Se captura un único `now` UTC por petición y se reutiliza para todos los elementos y para `meta.server_time`; así no hay diferencias de milisegundos entre filas de la misma respuesta.
- `total_seconds` se deriva de `sla_deadline - created_at` (inicio del SLA congelado en la creación). No se introduce una columna adicional.
- Si `deadline <= created_at` por datos corruptos, se trata como `no_sla` y se registra una advertencia; no se muestra una alarma engañosa.
- El umbral se compara con segundos exactos; la visualización redondea a la baja (RN-04). Ejemplo de borde: con un SLA de 30 min (umbral 15:00) y 15:30 restantes, la fila muestra «15 min» y permanece `on_time`; pasa a `at_risk` cuando `remaining_seconds <= 900`. Los ejemplos de la spec se cumplen: SLA 30 min → umbral 15 min; SLA 4 h → 60 min; SLA 24 h → 6 h; SLA exactamente 60 min → 60 min (por la rama `>= 60`).
- Para finalizados: `outcome = "met"` si `finalized_at <= deadline`; `"breached"` si `finalized_at > deadline`; `"no_sla"` si falta deadline. `breach_delay_seconds = max(0, finalized_at - deadline)`.

#### 3.2.1 Duración mostrada: dinámica en activos, estática en finalizados

- **Tickets activos vencidos** (`state = overdue`): `remaining_seconds` se recalcula contra el `now` de cada respuesta y el frontend lo decrementa entre polls; el texto "Vencido hace [tiempo]" crece mientras el ticket siga activo.
- **Tickets finalizados** (`state = finalized`): no hay cuenta atrás. El resultado se obtiene comparando `finalized_at` con `sla_deadline` y el texto "Incumplido hace [tiempo]" usa `breach_delay_seconds = max(0, finalized_at - sla_deadline)`, es decir, el retraso con el que se finalizó. Ese valor es fijo y no crece con el tiempo transcurrido desde el cierre.
- **Sin SLA**: no hay duración ni resultado calculable; se muestra "Sin SLA definido" y `outcome = no_sla` si el ticket está finalizado.

#### 3.3 Cuenta atrás en el frontend

```ts
// useSlaClock.ts (idea)
const anchor = { remainingSeconds: item.sla.remainingSeconds, perfAtFetch: performance.now() }

function tick() {
  const elapsed = (performance.now() - anchor.perfAtFetch) / 1000
  const remaining = anchor.remainingSeconds - elapsed
  // formatRemaining(remaining) y classify con el umbral recibido
}
```

- No se usa `new Date()` para calcular la diferencia con `deadline`; así un reloj de sistema adelantado o atrasado no altera la cuenta atrás.
- Al recibir una nueva respuesta, se reemplaza el ancla con el nuevo `remaining_seconds` y `performance.now()`.
- Si la pestaña estuvo oculta, al volver se fuerza una petición inmediata en lugar de confiar en el tiempo transcurrido.
- El tick local es de 30 s para que los cambios de minuto se reflejen con precisión; el poll de red sigue siendo de 60 s (RN-14, FR-005).

#### 3.4 Cambio de hora oficial (DST)

- El cálculo de duración usa instantes UTC, por lo que un deadline fijado antes del cambio de hora mantiene exactamente el mismo `remaining_seconds` antes y después.
- La interfaz muestra fechas absolutas con `Intl` y `Europe/Madrid`: en el cambio de primavera no existen las 02:00-02:59, y en el de otoño las 02:00-02:59 se repiten. `Intl` resuelve ambos casos sin lógica manual.
- Prueba de regresión: mismo ticket consultado a las 01:30 y a las 03:30 del día del cambio debe mostrar una diferencia de 2 horas reales (o la que corresponda en UTC), no 1 ni 3.

### 4. Flujo de datos de extremo a extremo

```text
Técnico abre /cola-de-trabajo
  → WorkQueuePage monta
  → store lee filtros de la URL (o aplica activos por defecto)
  → GET /api/v1/me/work-queue?status=…&priority=…&page=1&page_size=25
      → auth resuelve current_user (rol tecnico)
      → WHERE assignee_id = current_user.id AND filtros
      → ORDER BY activos primero, prioridad ASC, deadline ASC NULLS LAST,
                 finalizados por finalized_at DESC, number ASC
      → calcula remaining_seconds, threshold, state, outcome
      → devuelve items + pagination + counts + available_filters + server_time
  → store guarda datos y ancla el reloj monotónico
  → WorkQueueTable pinta filas con SLA_ROW_CLASS / SLA_BADGE_CLASS
  → tick local cada 30 s actualiza duraciones; poll cada 60 s resincroniza
```

### 5. Contenerización y despliegue

#### 5.1 Imagen multi-etapa

Un único `Dockerfile` en la raíz contiene cuatro etapas:

| Etapa | Base | Salida |
|-------|------|--------|
| `frontend-build` | `node:20-alpine` | Ejecuta `npm ci` y `npm run build` con `VITE_API_BASE_URL` como argumento; genera `dist/`. |
| `frontend` | `nginx:1.27-alpine` | Copia `dist/` y `frontend/nginx.conf`; sirve la SPA y proxifica `/api/` a `backend:8000`. |
| `backend-builder` | `python:3.12-slim` | Instala `backend/requirements.txt` en `/opt/venv`. |
| `backend` | `python:3.12-slim` | Copia el virtualenv y el código; ejecuta como usuario sin privilegios y usa `backend/docker/entrypoint.sh`. |

El frontend se compila con `VITE_API_BASE_URL` vacío por defecto, de modo que el navegador llama a `/api` en el mismo origen y Nginx resuelve el proxy. Así se evita CORS en el flujo normal y no se necesita publicar el backend para que la SPA funcione.

#### 5.2 Orquestación con Docker Compose

`docker-compose.yml` define tres servicios:

- `db`: PostgreSQL 16, healthcheck `pg_isready`, volumen `ticketing_db_data` y sin puerto publicado al host.
- `backend`: construido desde la etapa `backend`, espera a `db` sano, recibe `DATABASE_URL` y el resto de configuración por entorno, publica `${BACKEND_PORT:-8000}` y declara healthcheck contra `/openapi.json`.
- `frontend`: construido desde la etapa `frontend`, espera a `backend` sano y publica `${FRONTEND_PORT:-8080}`. Su healthcheck consulta `/healthz`.

El entrypoint del backend ejecuta `alembic upgrade head` con hasta `MIGRATION_MAX_ATTEMPTS` reintentos espaciados `MIGRATION_RETRY_SECONDS`. Cuando termina, hace `exec uvicorn ... --proxy-headers`, de modo que el contenedor principal es Uvicorn y recibe correctamente las señales de parada.

#### 5.3 Configuración y persistencia

- `.env.example` documenta puertos, credenciales de PostgreSQL, secreto/validación JWT, orígenes CORS, reintentos de migración y `VITE_API_BASE_URL`. `.env` está ignorado por Git.
- Si `DATABASE_URL` no se define, Compose la construye con `POSTGRES_USER`, `POSTGRES_PASSWORD` y `POSTGRES_DB`, apuntando al servicio `db`.
- `POSTGRES_PASSWORD` debe ir codificada para URL si contiene caracteres reservados (`@`, `:`, `/`, etc.) cuando se use en `DATABASE_URL`.
- El volumen nombrado conserva los datos entre `docker compose down` y `docker compose up`; solo `docker compose down -v` los elimina.
- El seed de demostración es opcional y se ejecuta con `docker compose exec backend python scripts/seed_dev.py`; nunca se ejecuta automáticamente.

#### 5.4 Criterios operativos

1. Un clon limpio arranca con `docker compose up` sin instalar Python, Node ni PostgreSQL.
2. El esquema queda migrado antes de que el backend se declare sano.
3. La SPA queda disponible en `http://localhost:8080` y la API en `http://localhost:8000`.
4. Un reinicio conserva los datos; un borrado explícito del volumen permite empezar de cero.
5. Ningún secreto real viaja en la imagen ni en el repositorio.

## Estrategia de Pruebas

### Backend

- **Unitarias (`test_sla.py`)**: umbral para SLA de 30 min, 59 min, 60 min, 4 h, 24 h; límite exacto (0 → `at_risk`), −1 s → `overdue`; sin deadline → `no_sla`; finalizado `met`, `breached`, `no_sla`; `breach_delay_seconds`; DST con instantes UTC.
- **Integración (`test_work_queue_api.py`)**:
  - 401 sin token o con token inválido/caducado; 403 con rol usuario/supervisor.
  - Solo tickets de `current_user`; un `technician_id` inyectado en la query no cambia el resultado.
  - Estados por defecto = activos; filtro explícito por `resuelto`/`cerrado`; mezcla de activos y finales.
  - Filtros Y; prioridad por nivel; 422 con estado o nivel inválido; 422 con `page_size` fuera de rango.
  - Orden: prioridad ASC, deadline ASC, vencidos antes que no vencidos dentro de la prioridad, sin SLA al final, desempate por número.
  - Finalizados después de activos, `finalized_at DESC`, desempate por número.
  - Paginación: orden global antes de paginar, páginas sin solapes ni huecos, `total_pages`, página fuera de rango.
  - `counts` y `available_filters` correctos y limitados al técnico.
  - `Cache-Control: no-store`.
- **Contrato (`test_work_queue_contract.py`)**: validar la respuesta contra el esquema OpenAPI y los códigos de estado documentados.
- **Rendimiento**: prueba con 100 tickets que mida la consulta y el endpoint; objetivo p95 < 2 s de extremo a extremo y consulta < 300 ms.

### Frontend

- **Unitarias (`sla.spec.ts`)**: `formatRemaining` para días/horas/minutos/menos de un minuto/cero/negativo; `classify` con los mismos vectores que el backend (paridad); umbral corto y largo.
- **Store (`workQueue.store.spec.ts`)**: lectura/escritura de filtros en URL; normalización de valores inválidos; debounce; reinicio de página al filtrar; polling con fake timers; cancelación de peticiones; mapeo de 401/403/500 a estados; conservación de datos en error de refresco.
- **Componentes**: la tabla muestra los cinco datos por fila; badges incluyen texto e icono; fila roja/ámbar/neutra según estado; finalizados sin alerta; filtros accesibles por teclado; los tres estados vacíos son distintos; el error ofrece reintento; paginación deshabilitada correctamente. Comprobación `axe-core` sin violaciones críticas.
- **Manual**: [quickstart.md](./quickstart.md) con escenarios verificables por una persona no técnica.

## Riesgos y Mitigaciones

| Riesgo | Mitigación |
|--------|------------|
| Convención de `priority.level` invertida (1 = Baja) | Documentar la asunción en [data-model.md](./data-model.md) y cubrirla con una prueba de orden; si el esquema real difiere, cambiar solo `ORDER BY` y el fixture. |
| Reloj del cliente desajustado | Cuenta atrás basada en `remaining_seconds` + `performance.now()`; resincronización cada 60 s y al recuperar foco. |
| Cambio de hora oficial | UTC en cálculo; `Intl` con `Europe/Madrid` solo para presentación; prueba de regresión DST. |
| Tickets ya finalizados sin `finalized_at` | Backfill en migración desde `closed_at`/`updated_at`; restricción NOT NULL para estados finales; si no hay dato fiable, se usa `updated_at` y se documenta. |
| Respuestas fuera de orden por polling | `AbortController` y `requestId`; solo se aplica la respuesta de la última petición. |
| Clases Tailwind purgadas | Mapas estáticos de clases completas; prohibido interpolar nombres de clase. |
| Fuga de tickets ajenos | `assignee_id = current_user.id` en la consulta base; pruebas negativas con parámetros inyectados. |
| Cola grande y paginación inestable | Orden total con desempate por `number`; índices compuestos; prueba de páginas sin solapes. |
| PostgreSQL tarda en aceptar conexiones al arrancar | `depends_on: condition: service_healthy` y entrypoint con reintentos acotados de `alembic upgrade head`. |
| Secretos acabaron en la imagen | `.dockerignore` excluye `.env*` salvo `.env.example`; Compose inyecta valores en tiempo de ejecución y el README no contiene secretos. |
| El frontend apunta a un API inalcanzable | Por defecto `VITE_API_BASE_URL` vacío y proxy de Nginx; si se cambia, se documenta que hay que reconstruir la imagen. |

## Seguimiento de Complejidad

No hay violaciones de la constitución ni complejidad que justificar. El diseño evita caché, WebSockets, repositorios genéricos, ordenación configurable y paquetes compartidos entre backend y frontend.

## Re-evaluación de la Constitución tras el Diseño (Fase 1)

| Principio | Resultado |
|-----------|-----------|
| Simplicidad | ✅ Un endpoint, una vista, un store, una migración mínima. |
| Idioma y mercado | ✅ Textos en español de España y formato `Europe/Madrid`. |
| Cero alcance fantasma | ✅ Solo lectura y requisitos de `spec.md`; sin acciones de ticket ni notificaciones. |
| Verificable por no técnico | ✅ `quickstart.md` con escenarios observables. |
| Datos con respeto | ✅ Identidad desde el token JWT, sin parámetros de técnico, sin secretos. |

**Gate final**: aprobado. Se puede pasar a `/speckit.tasks`.
