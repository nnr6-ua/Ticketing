# Contrato de componentes — HU-07 (Dashboard de cumplimiento de SLA)

**Feature**: `007-dashboard-cumplimiento-sla` | **Date**: 2026-11-15

Contrato de la interfaz Vue 3 + Tailwind para el dashboard de supervisión de
SLA. Los componentes consumen el contrato HTTP de
[`sla-dashboard.openapi.yaml`](./sla-dashboard.openapi.yaml); no calculan
porcentajes, semáforos ni rankings: todo valor presentado viene del backend
(`compliance_pct`, `semaphore`, `thresholds`, `avg_*_seconds`).

Se reutilizan el cliente HTTP (`apiGet` de `api/client.ts`), la paleta
`slate`, los patrones de accesibilidad de HU-04/HU-05 y el formato de
duraciones de `utils/sla.ts`. No se añaden librerías de gráficos ni de
interfaz. Vista de **solo lectura**: ningún componente emite escrituras.

---

## 1. Navegación y permisos en cliente

### 1.1. Ruta (`frontend/src/router/index.ts`)

```ts
{
  path: '/dashboard-sla',
  name: 'sla-dashboard',
  component: SlaDashboardPage,
  meta: { requiresRoles: ['supervisor', 'admin'] },
}
```

- Guard global `router.beforeEach` (nuevo, único en la app): decodifica el
  payload del token (`localStorage.access_token`) con un helper
  `getStoredUserRole()` en `api/client.ts`; si no hay token ⇒
  `next({ name: 'login', query: { redirect: to.fullPath } })`; si el rol no
  está en `requiresRoles` ⇒ `next({ name: 'sla-dashboard', ... })` se bloquea
  redirigiendo a `/cola-de-trabajo` (o muestra el estado `forbidden`).
- El guard es **cosmético**: la defensa real es el `403 forbidden` del
  servidor (constitución III). La página también reacciona de forma reactiva
  al `error.kind === 'forbidden'` (patrón de `WorkQueuePage.vue`).
- `AppHeader.vue` muestra el enlace «Dashboard SLA» solo si el rol es
  supervisor/administrador.

## 2. Tipos (`frontend/src/types/slaDashboard.ts`)

```ts
export type SlaSemaphore = 'verde' | 'ambar' | 'rojo' | 'sin_datos'

export interface SlaThresholds {
  green_pct: number
  amber_pct: number
}

export interface ComplianceMetrics {
  ticket_count: number
  no_sla_count: number
  attended_with_sla: number
  on_time: number
  compliance_pct: number | null
  avg_response_seconds: number | null
  overdue_count: number
  semaphore: SlaSemaphore
}

export interface MatrixRow extends ComplianceMetrics {
  priority_level: 1 | 2 | 3 | 4
  priority_name: string
  priority_is_active: boolean
  category_id: string | null
  category_name: string // «Sin categoría» si category_id === null
  category_is_active: boolean | null
}

export interface TotalsEntry extends ComplianceMetrics {
  scope: 'priority' | 'category' | 'global'
  priority_level: number | null
  priority_name: string | null
  priority_is_active: boolean | null
  category_id: string | null
  category_name: string | null
  category_is_active: boolean | null
}

export interface RankingEntry {
  technician_id: string | null // null = «Sin asignar»
  technician_name: string
  team: string | null
  is_active: boolean | null
  overdue_count: number
  avg_delay_seconds: number
}

export interface SlaDashboardFilters {
  desde: string | null // YYYY-MM-DD
  hasta: string | null
  categorias: string[] // UUIDs + 'sin_categoria'
  prioridades: number[] // 1..4
}

export interface SlaDashboardData {
  summary: ComplianceMetrics
  matrix: MatrixRow[]
  priority_totals: TotalsEntry[]
  category_totals: TotalsEntry[]
  ranking: {
    technicians: RankingEntry[]
    unassigned: RankingEntry | null
    overdue_total: number
  }
}

export interface SlaDashboardMeta {
  generated_at: string
  timezone: 'Europe/Madrid'
  thresholds: SlaThresholds
  filters: SlaDashboardFilters
  has_tickets: boolean
}

export interface SlaDashboardOptions {
  desde: string
  hasta: string
  categories: { id: string | null; name: string; is_active: boolean | null }[]
  priorities: { level: number; name: string; is_active: boolean }[]
}
```

## 3. Store (`frontend/src/stores/slaDashboard.ts`)

Setup-style `defineStore('slaDashboard', () => {...})`, espejo del patrón de
`workQueue.ts`:

- Estado: `data`, `meta`, `options`, `loading`, `updating`, `error`
  (`ApiClientError | null`), `stale` (bool), `lastFetchedAt`.
- Filtros sincronizados con la URL (query en español): `desde`, `hasta`,
  `categorias` (CSV), `prioridades` (CSV). Por defecto (sin query):
  el servidor aplica los últimos 30 días naturales; el store pinta los
  valores efectivos de `meta.filters`.
- Acciones: `load()` (aborta la petición previa con `AbortController`),
  `refresh()` (manual, mantiene filtros), `setFilters(f)` (valida
  `desde <= hasta` antes de navegar; no emite petición con rango inválido),
  `resetFilters()`, polling interno cada 60 s pausado con
  `document.hidden` y refresco al recuperar foco/visibilidad.
- Degradación: si falla una actualización con datos previos ⇒
  `stale = true`, conserva `data` y muestra el aviso; si falla la carga
  inicial ⇒ `error` sin `data` (nunca métricas a cero).
- `mapError`: mensajes es-ES por `error.kind` y `error.code`
  (`invalid_date_range` ⇒ «La fecha inicial no puede ser posterior a la
  fecha final.»; `forbidden`; `unauthorized` ⇒ redirige a login con
  `redirect`; `network`/`server` ⇒ «No se pudo cargar el dashboard…»).
- Sesión caducada durante el sondeo ⇒ redirigir a `/login?redirect=…`
  conservando la query de filtros.

## 4. Página y componentes (`components/sla-dashboard/`)

| Componente | Props (entrada) | Emits (salida) | Responsabilidad |
|---|---|---|---|
| `SlaDashboardPage.vue` | — | — | Orquesta: store, guard reactivo, layout (filtros arriba; resumen; matriz; leyenda; ranking), estados globales (loading skeleton, error, vacío, stale) |
| `SlaDashboardFilters.vue` | `filters`, `options`, `applying` | `apply`, `reset`, `change` | Rango de fechas (`type="date"`, máx. hoy permitido sin bloquear fechas futuras), multiselección de categorías (chips con checkbox, incl. «Sin categoría») y de prioridades; resumen de filtros activos (HU07-RF-037); botones «Aplicar» (deshabilitado y con mensaje si `desde > hasta`) y «Restablecer» |
| `SlaSummary.vue` | `summary: ComplianceMetrics` | — | Resumen global (HU07-RF-005): tickets considerados, atendidos con SLA, cumplimiento (semáforo + %), tiempo medio, vencidos, sin SLA |
| `ComplianceMatrix.vue` | `matrix`, `priorityTotals`, `categoryTotals`, `summary` | — | Tabla prioridad (filas, orden 1→4) × categorías (columnas, alfabético, «Sin categoría» al final); celdas solo con datos; fila/columna de totales y celda global siempre visibles; etiquetas «(inactiva)» |
| `MatrixCell.vue` | `metrics: ComplianceMetrics` | — | Celda: nº tickets, semáforo + %, tiempo medio, vencidos; «Sin datos» neutro cuando `compliance_pct === null` |
| `SemaphoreBadge.vue` | `semaphore: SlaSemaphore`, `pct: number | null`, `compact?` | — | Semáforo reutilizable: icono lucide + texto + color (clases estáticas de `utils/slaStyles.ts`); nunca solo color; `aria-label` completo |
| `SemaphoreLegend.vue` | `thresholds: SlaThresholds` | — | Leyenda con los umbrales recibidos de `meta.thresholds` (no hardcodea) y significado de cada banda |
| `TechnicianRanking.vue` | `ranking` | — | Tabla: posición, técnico (+«(inactivo)»), equipo, vencidos, retraso medio; fila «Sin asignar» separada al final; estado vacío específico si no hay vencidos |
| `DashboardEmptyState.vue` | `variant: 'periodo' | 'filtros' | 'sin-sla' | 'sin-vencidos'`, `onAction?` | — | Estados vacíos diferenciados (HU07-RN-16) con acción (ampliar fechas / limpiar filtros); «sin resultados para los filtros» ≠ «periodo sin tickets» |
| `DashboardErrorState.vue` | `variant: 'full' | 'warning' | 'forbidden'`, `message`, `onRetry` | — | Error de carga (con reintento), aviso de desactualización conservando datos previos (`role="status"`), y `forbidden` sin revelar métricas |
| `SlaDashboardSkeleton.vue` | — | — | Esqueleto de carga (patrón `WorkQueueSkeleton`) |

### 4.1. Reglas de presentación (es-ES / Europe/Madrid / WCAG)

- **Porcentajes**: `Intl.NumberFormat('es-ES', { minimumFractionDigits: 1,
  maximumFractionDigits: 1 })` ⇒ «87,5 %»; `< 1 %` nunca; el valor y su
  semáforo son los que envía el backend.
- **Duraciones**: reutilizar `formatDuration` de `utils/sla.ts`
  («3 d 4 h», «4 h 12 min», «37 min») con «menos de 1 min» para medias < 1 minuto
  (HU07-RN-15).
- **Fechas/horas**: `generated_at` y filtros se presentan en
  `Europe/Madrid` (`Intl.DateTimeFormat('es-ES', { timeZone: 'Europe/Madrid' })`);
  «Última actualización: 15/11/2026 09:34».
- **Etiquetas históricas**: si `priority_is_active === false` o
  `category_is_active === false` ⇒ añadir «(inactiva)»; técnico inactivo ⇒
  «(inactivo)».
- **Accesibilidad**: tablas con `<caption>`, `th scope="col"/"row"`,
  `aria-sort` cuando proceda; semáforo con `role="img"` y `aria-label`
  («Cumplimiento 87,5 %, fuera de objetivo»); estados y avisos con
  `role="alert"` o `aria-live="polite"`; foco visible y navegación por
  teclado; contraste AA.
- **Prohibido**: `v-html` con datos del backend; mostrar correo, número o
  detalle de tickets individuales, o datos del usuario creador.

## 5. API wrapper (`frontend/src/api/slaDashboard.ts`)

```ts
export function fetchSlaDashboard(filters: SlaDashboardFilters, signal?: AbortSignal): Promise<{ data: SlaDashboardData; meta: SlaDashboardMeta }>
export function fetchSlaDashboardOptions(filters: Pick<SlaDashboardFilters, 'desde' | 'hasta'>, signal?: AbortSignal): Promise<SlaDashboardOptions>
```

- Ambas usan `apiGet` con query params solo si están definidos;
  `Cache-Control: no-store` esperado del servidor.
- Sin métodos de escritura (no existen en el contrato).
