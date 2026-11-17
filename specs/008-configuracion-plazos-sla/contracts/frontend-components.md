# Contrato de componentes — HU-08

**Feature**: `008-configuracion-plazos-sla` | **Date**: 2026-11-15

Contrato de la interfaz Vue 3 + Tailwind para la configuración administrativa. Los componentes consumen [admin-configuration.openapi.yaml](./admin-configuration.openapi.yaml); no hardcodean permisos, versiones ni reglas de negocio.

---

## 1. Tipos compartidos

`frontend/src/types/adminConfiguration.ts`:

```ts
export type ConfigEntityType = 'category' | 'priority' | 'sla_rule'

export type ConfigAction =
  | 'create'
  | 'update'
  | 'deactivate'
  | 'reactivate'
  | 'delete'
  | 'set_default'
  | 'rule_upsert'
  | 'rule_retire'

export interface UserRef {
  id: string
  name: string
  email: string
}

export interface ConfigurationVersionRef {
  id: string
  version: number
  created_at: string
  created_by: UserRef | null
}

export interface CategoryRef {
  id: string
  name: string
}

export interface PriorityRef {
  id: string
  name: string
  level: number
  color: string | null
  base_hours: string | null
}

export interface CategoryAdmin extends CategoryRef {
  description: string | null
  keywords: string[]
  is_active: boolean
  is_default: boolean
  is_system: boolean
  sort_order: number
  revision: number
  ticket_count: number
  rule_count: number
  can_delete: boolean
}

export interface PriorityAdmin extends PriorityRef {
  keywords: string[]
  is_active: boolean
  is_default: boolean
  is_system: boolean
  sort_order: number
  revision: number
  ticket_count: number
  rule_count: number
  can_delete: boolean
}

export interface CategoryCreateRequest {
  name: string
  description?: string | null
  keywords?: string[]
  sort_order?: number
  is_default?: boolean
}

export interface CategoryUpdateRequest {
  expected_revision: number
  name?: string
  description?: string | null
  keywords?: string[]
  sort_order?: number
  is_active?: boolean
  is_default?: boolean
  replacement_default_id?: string | null
}

export interface PriorityCreateRequest {
  name: string
  level: number
  color?: string | null
  base_hours: string
  keywords?: string[]
  sort_order?: number
  is_default?: boolean
}

export interface PriorityUpdateRequest {
  expected_revision: number
  name?: string
  level?: number
  color?: string | null
  base_hours?: string
  keywords?: string[]
  sort_order?: number
  is_active?: boolean
  is_default?: boolean
  replacement_default_id?: string | null
}

export interface DeleteRequest {
  expected_revision: number
}

export interface DeleteResponse {
  deleted: boolean
  id: string
  configuration_version: ConfigurationVersionRef
}

export interface SlaRuleAdmin {
  id: string
  category: CategoryRef
  priority: PriorityRef
  hours: string
  valid_from_version: number
  configuration_version_id: string
  created_at: string
  created_by: UserRef
}

export interface SlaMatrixResponse {
  configuration_version: ConfigurationVersionRef
  items: SlaRuleAdmin[]
  combinations: {
    categories: CategoryRef[]
    priorities: PriorityRef[]
  }
}

export type SlaChange =
  | {
      operation: 'upsert'
      category_id: string
      priority_id: string
      hours: string
      expected_rule_id: string | null
    }
  | {
      operation: 'retire'
      rule_id: string
      expected_rule_id: string
    }

export interface SlaBatchRequest {
  changes: SlaChange[]
}

export interface SlaBatchResponse {
  configuration_version: ConfigurationVersionRef
  items: SlaRuleAdmin[]
}

export interface ConfigHistoryEntry {
  id: string
  configuration_version: ConfigurationVersionRef
  entity_type: ConfigEntityType
  entity_id: string
  action: ConfigAction
  actor: UserRef
  occurred_at: string
  previous_values: Record<string, unknown> | null
  new_values: Record<string, unknown> | null
  summary: string
}

export interface Pagination {
  page: number
  page_size: number
  total_items: number
  total_pages: number
  has_next: boolean
  has_previous: boolean
}

export interface ConfigHistoryResponse {
  items: ConfigHistoryEntry[]
  pagination: Pagination
}

export interface ConfigHistoryFilters {
  from?: string
  to?: string
  entity_type?: ConfigEntityType
  entity_id?: string
  action?: ConfigAction
  configuration_version_id?: string
  page?: number
  page_size?: number
}
```

---

## 2. `AdminConfigurationPage.vue`

**Ruta**: `frontend/src/views/AdminConfigurationPage.vue`
**Ruta URL**: `/admin/configuracion`
**Nombre**: `admin-configuration`

### Estado

| Ref | Tipo | Uso |
|---|---|---|
| `activeTab` | `'categories' \| 'priorities' \| 'matrix' \| 'history'` | Pestaña visible; se refleja en `?tab=` |
| `loading` | `boolean` | Carga inicial de catálogos y matriz |
| `error` | `ApiClientError \| null` | Error fatal de carga |
| `conflict` | `string \| null` | Mensaje de conflicto de versión |

### Comportamiento

- Al montar, carga categorías, prioridades y matriz en paralelo.
- Si el error es `unauthorized`, redirige a `/login?redirect=/admin/configuracion`.
- Si el error es `forbidden`, muestra una tarjeta «Solo administración» sin datos.
- La pestaña activa se conserva en la query `tab` para poder enlazar.
- Proporciona `reloadAll()` a las pestañas para resolver conflictos.

### Estructura visual

- `main.mx-auto.max-w-7xl.px-4.py-8`
- Cabecera con `h1.text-2xl.font-semibold.tracking-tight.text-slate-900` y subtítulo `text-sm.text-slate-700`.
- Botón primario `bg-sky-600 hover:bg-sky-700 rounded-lg px-4 py-2 text-sm font-semibold text-white shadow-sm`.
- Tarjetas `rounded-2xl border border-slate-200 bg-white shadow-sm`.
- Esqueletos `animate-pulse` con bloques `bg-slate-100`.

---

## 3. `AdminTabs.vue`

### Props

| Prop | Tipo | Obligatoria | Descripción |
|---|---|---|---|
| `tabs` | `{ id: string; label: string }[]` | Sí | Pestañas disponibles |
| `modelValue` | `string` | Sí | Pestaña activa |

### Eventos

| Evento | Payload | Cuándo |
|---|---|---|
| `update:modelValue` | `string` | El usuario selecciona una pestaña |

### Accesibilidad

- Contenedor `role="tablist"` con `aria-label="Secciones de configuración"`.
- Cada pestaña `role="tab"`, `id="tab-<id>"`, `aria-controls="panel-<id>"`, `aria-selected`.
- Navegación con flechas izquierda/derecha, `Home` y `End`.
- El panel correspondiente usa `role="tabpanel"`, `aria-labelledby="tab-<id>"` y `tabindex="0"`.

### Estados visuales

- Activa: `border-sky-600 text-sky-700`.
- Inactiva: `border-transparent text-slate-600 hover:text-slate-900`.
- Foco: `focus-visible:ring-2 focus-visible:ring-sky-500 focus-visible:ring-offset-2`.

---

## 4. `CategoryTable.vue`

### Props

| Prop | Tipo | Obligatoria | Descripción |
|---|---|---|---|
| `items` | `CategoryAdmin[]` | Sí | Categorías |
| `loading` | `boolean` | No | Muestra esqueletos |
| `disabled` | `boolean` | No | Bloquea acciones durante guardado |

### Eventos

| Evento | Payload | Cuándo |
|---|---|---|
| `create` | — | Botón «Nueva categoría» |
| `edit` | `CategoryAdmin` | Acción Editar |
| `toggle` | `CategoryAdmin` | Acción Desactivar/Reactivar |
| `delete` | `CategoryAdmin` | Acción Eliminar |

### Columnas

Nombre, Descripción, Palabras clave, Orden, Estado, Tickets, Reglas, Acciones.

### Reglas de acciones

- `is_system`: sin acciones; insignia «Sistema».
- `is_default` y `is_active`: el botón Desactivar exige reemplazo (lo gestiona el diálogo).
- `can_delete = false`: botón Eliminar deshabilitado con `title` explicativo.
- En pantallas pequeñas, la tabla se desplaza horizontalmente; no se ocultan columnas críticas.

### Accesibilidad

- `<caption class="sr-only">Categorías configuradas</caption>`.
- Cabeceras con `scope="col"`.
- Botones con `aria-label` que incluye el nombre de la categoría.
- Estado vacío con texto «Todavía no hay categorías configuradas.»

---

## 5. `CategoryFormDialog.vue`

### Props

| Prop | Tipo | Obligatoria | Descripción |
|---|---|---|---|
| `open` | `boolean` | Sí | Visibilidad |
| `category` | `CategoryAdmin \| null` | No | `null` = alta |
| `defaultCandidates` | `CategoryAdmin[]` | No | Categorías activas no-sistema para reemplazo |
| `saving` | `boolean` | No | Bloquea el formulario |
| `serverError` | `{ code: string; message: string } \| null` | No | Error del backend |
| `conflict` | `string \| null` | No | Conflicto de versión |

### Eventos

| Evento | Payload | Cuándo |
|---|---|---|
| `update:open` | `boolean` | Cierre |
| `submit` | `CategoryCreateRequest \| CategoryUpdateRequest` | Guardar |
| `reload` | — | El usuario pulsa «Recargar configuración» |

### Campos

- Nombre (obligatorio, 1–100).
- Descripción (opcional, ≤ 2.000).
- Palabras clave (input separado por comas; se muestran como chips).
- Orden (0–9.999).
- Activa (checkbox).
- Predeterminada (checkbox).
- Reemplazo de predeterminada (select, visible al desactivar la default).

### Validación

- Nombre vacío: «El nombre es obligatorio.»
- Nombre duplicado: mensaje del backend `duplicate_catalog_name`.
- Desactivar default sin reemplazo: mensaje local y `default_replacement_required` del backend.
- Conflicto: banner superior y botón «Recargar configuración»; no se cierra el diálogo.
- Los errores de campo usan `role="alert"` y `aria-describedby`.

### Estilo

- `Dialog` de Headless UI con overlay `bg-slate-900/40`.
- Panel `rounded-2xl bg-white p-6 shadow-xl`.
- Inputs `rounded-xl border-slate-300 focus:border-sky-500 focus:ring-2 focus:ring-sky-500/20`.
- Botón primario `bg-sky-600`; secundario `border-slate-300 bg-white text-slate-700`.

---

## 6. `PriorityTable.vue`

### Props

| Prop | Tipo | Obligatoria | Descripción |
|---|---|---|---|
| `items` | `PriorityAdmin[]` | Sí | Prioridades |
| `loading` | `boolean` | No | Esqueletos |
| `disabled` | `boolean` | No | Bloquea acciones |

### Eventos

`create`, `edit`, `toggle`, `delete` con el mismo contrato que `CategoryTable`.

### Columnas

Nombre, Nivel, Color, Plazo base, Palabras clave, Estado, Tickets, Reglas, Acciones.

### Visual

- El color se muestra como punto `h-2.5 w-2.5 rounded-full` con `style="{ backgroundColor: color }"`.
- Nivel como insignia `bg-slate-100 text-slate-700`.
- Plazo base como `8 h` (sin decimales si es entero) o `8,5 h`.
- Insignias de estado y sistema iguales que en categorías.

---

## 7. `PriorityFormDialog.vue`

### Props y eventos

Mismo contrato que `CategoryFormDialog`, con `priority` y `PriorityCreateRequest | PriorityUpdateRequest`.

### Campos

- Nombre (obligatorio, 1–50).
- Nivel (select 1–4; 1 = Crítica).
- Color (`input type="color"` + texto hexadecimal).
- Plazo base en horas (obligatorio, decimal positivo, hasta 2 decimales).
- Palabras clave.
- Orden.
- Activa.
- Predeterminada y reemplazo.

### Validación

- Nivel fuera de 1–4: «El nivel debe estar entre 1 y 4.»
- Nivel duplicado: `duplicate_priority_level` del backend.
- Plazo base ≤ 0 o no numérico: «El plazo base debe ser un número positivo de horas.»
- Resto igual que categorías.

---

## 8. `SlaMatrix.vue`

### Props

| Prop | Tipo | Obligatoria | Descripción |
|---|---|---|---|
| `matrix` | `SlaMatrixResponse \| null` | Sí | Matriz vigente |
| `saving` | `boolean` | No | Bloquea acciones |
| `conflict` | `string \| null` | No | Conflicto de versión |

### Eventos

| Evento | Payload | Cuándo |
|---|---|---|
| `save` | `SlaChange[]` | «Guardar cambios» |
| `reload` | — | «Recargar configuración» |

### Estado interno

- `draft`: `Map<string, string | null>` con clave `${categoryId}:${priorityId}` y valor de horas o `null` para retirar.
- `baseline`: copia de la matriz recibida para calcular cambios.
- `isDirty`: `draft` difiere de `baseline`.
- `cellError`: error local de una celda.

### Renderizado

- Tabla con categorías en filas y prioridades en columnas.
- Cabecera de prioridad: nombre, nivel y plazo base (`Base: 8 h`).
- Celda con regla: `6 h` y un punto de color de la prioridad.
- Celda sin regla: `Base: 8 h` en `text-slate-500`.
- Celda inactiva: fondo `bg-slate-50` y texto `text-slate-400`; no editable.
- Cada celda es un `<button>` con `aria-label="Plazo para Red y Alta"` y `aria-describedby` con la ayuda.
- Barra inferior sticky con «Cambios sin guardar», «Descartar» y «Guardar cambios».

### Edición

- `SlaCellEditor` se abre al activar una celda.
- Acepta horas positivas con hasta 2 decimales.
- Acciones: Guardar (actualiza `draft`), Retirar (marca `null`), Cancelar.
- `Esc` cierra sin aplicar; `Enter` guarda.
- Al guardar el lote, se emite `save` con todas las diferencias:
  - Celda nueva: `{ operation: 'upsert', ..., hours, expected_rule_id: null }`.
  - Celda modificada: `{ operation: 'upsert', ..., hours, expected_rule_id: rule.id }`.
  - Celda retirada: `{ operation: 'retire', rule_id, expected_rule_id: rule.id }`.

### Conflictos y errores

- `409 stale_configuration`: banner con «La matriz ha cambiado. Recarga antes de guardar.» y botón de recarga.
- `422 inactive_catalog_item`: la celda se marca con borde `rose-400` y mensaje.
- Cualquier error deja el borrador intacto para no perder cambios.

### Accesibilidad

- `<caption class="sr-only">Matriz de plazos por categoría y prioridad</caption>`.
- Cabeceras de fila y columna con `scope`.
- Estados de guardado con `role="status"` y `aria-live="polite"`.
- No se usan solo colores para indicar vigencia; se añade texto.

---

## 9. `SlaCellEditor.vue`

### Props

| Prop | Tipo | Obligatoria | Descripción |
|---|---|---|---|
| `open` | `boolean` | Sí | Visibilidad |
| `category` | `CategoryRef` | Sí | Fila |
| `priority` | `PriorityRef` | Sí | Columna |
| `currentHours` | `string \| null` | Sí | Horas vigentes o `null` |
| `hasRule` | `boolean` | Sí | Indica si existe regla |
| `error` | `string \| null` | No | Error local o del backend |

### Eventos

| Evento | Payload | Cuándo |
|---|---|---|
| `update:open` | `boolean` | Cierre |
| `apply` | `{ hours: string \| null }` | Guardar o retirar |
| `cancel` | — | Cancelar |

### Reglas

- Título: «Plazo para {categoría} × {prioridad}».
- Ayuda: «Introduce horas naturales continuas. Ejemplo: 8 o 7,5.»
- Si `hasRule`, muestra «Retirar regla» con confirmación inline; al retirar, el nuevo plazo será el base de la prioridad.
- No permite guardar si el valor está vacío, no es numérico o es ≤ 0.

---

## 10. `ConfigHistoryTable.vue`

### Props

| Prop | Tipo | Obligatoria | Descripción |
|---|---|---|---|
| `response` | `ConfigHistoryResponse \| null` | Sí | Página de histórico |
| `filters` | `ConfigHistoryFilters` | Sí | Filtros aplicados |
| `loading` | `boolean` | No | Esqueletos |
| `error` | `string \| null` | No | Error de carga |

### Eventos

| Evento | Payload | Cuándo |
|---|---|---|
| `update:filters` | `ConfigHistoryFilters` | Cambian filtros o página |
| `retry` | — | Reintentar carga |

### Filtros

- Desde / hasta (`input type="date"`).
- Entidad (`category`, `priority`, `sla_rule`).
- Acción (`create`, `update`, `deactivate`, `reactivate`, `delete`, `set_default`, `rule_upsert`, `rule_retire`).
- Versión (`number`).
- Botón «Limpiar filtros».

### Tabla

Columnas: Fecha, Autor, Entidad, Acción, Valores anteriores, Valores nuevos, Versión.

- Fecha: `Intl.DateTimeFormat('es-ES', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'Europe/Madrid' })`.
- Entidad: etiqueta legible (`Categoría`, `Prioridad`, `Regla SLA`).
- Acción: etiqueta legible en español.
- Valores: pares `clave: valor` en una lista compacta; `—` si es `null`.
- Versión: `v{version}`.
- Paginación reutiliza el patrón visual de `WorkQueuePagination`.

### Accesibilidad

- `<caption class="sr-only">Histórico de cambios de configuración</caption>`.
- Filtros con etiquetas asociadas.
- Estado vacío: «No hay cambios para los filtros seleccionados.»
- Errores con `role="alert"` y botón «Reintentar».

---

## 11. `ConflictBanner.vue`

### Props

| Prop | Tipo | Obligatoria | Descripción |
|---|---|---|---|
| `message` | `string` | Sí | Mensaje del conflicto |
| `reloading` | `boolean` | No | Estado de recarga |

### Eventos

| Evento | Payload | Cuándo |
|---|---|---|
| `reload` | — | El usuario pulsa «Recargar configuración» |

### Visual y accesibilidad

- `role="alert"` y `aria-live="assertive"`.
- Contenedor `rounded-xl border border-amber-300 bg-amber-50 p-4`.
- Título «La configuración ha cambiado» y texto `text-sm text-amber-900`.
- Botón `border-amber-300 bg-white text-amber-900 hover:bg-amber-100`.
- No se cierra automáticamente; desaparece al recargar con éxito.

---

## 12. Servicio `adminConfiguration.ts`

**Ruta**: `frontend/src/services/adminConfiguration.ts`

```ts
import { apiGet, apiPost } from '@/api/client'
import type {
  CategoryAdmin,
  CategoryCreateRequest,
  CategoryUpdateRequest,
  ConfigHistoryFilters,
  ConfigHistoryResponse,
  DeleteRequest,
  DeleteResponse,
  PriorityAdmin,
  PriorityCreateRequest,
  PriorityUpdateRequest,
  SlaBatchRequest,
  SlaBatchResponse,
  SlaMatrixResponse,
} from '@/types/adminConfiguration'

const BASE = '/api/v1/admin'

export function listCategories(signal?: AbortSignal) {
  return apiGet<CategoryAdmin[]>(`${BASE}/categories`, { signal })
}

export function createCategory(payload: CategoryCreateRequest) {
  return apiPost<CategoryAdmin, CategoryCreateRequest>(`${BASE}/categories`, payload)
}

export function updateCategory(id: string, payload: CategoryUpdateRequest) {
  return apiPost<CategoryAdmin, CategoryUpdateRequest>(
    `${BASE}/categories/${encodeURIComponent(id)}/updates`,
    payload,
  )
}

export function deleteCategory(id: string, payload: DeleteRequest) {
  return apiPost<DeleteResponse, DeleteRequest>(
    `${BASE}/categories/${encodeURIComponent(id)}/deletion`,
    payload,
  )
}

export function listPriorities(signal?: AbortSignal) {
  return apiGet<PriorityAdmin[]>(`${BASE}/priorities`, { signal })
}

export function createPriority(payload: PriorityCreateRequest) {
  return apiPost<PriorityAdmin, PriorityCreateRequest>(`${BASE}/priorities`, payload)
}

export function updatePriority(id: string, payload: PriorityUpdateRequest) {
  return apiPost<PriorityAdmin, PriorityUpdateRequest>(
    `${BASE}/priorities/${encodeURIComponent(id)}/updates`,
    payload,
  )
}

export function deletePriority(id: string, payload: DeleteRequest) {
  return apiPost<DeleteResponse, DeleteRequest>(
    `${BASE}/priorities/${encodeURIComponent(id)}/deletion`,
    payload,
  )
}

export function getSlaMatrix(signal?: AbortSignal) {
  return apiGet<SlaMatrixResponse>(`${BASE}/sla-rules`, { signal })
}

export function saveSlaBatch(payload: SlaBatchRequest) {
  return apiPost<SlaBatchResponse, SlaBatchRequest>(`${BASE}/sla-rules/batch`, payload)
}

export function retireSlaRule(id: string, expectedRuleId: string) {
  return apiPost<SlaBatchResponse, { expected_rule_id: string }>(
    `${BASE}/sla-rules/${encodeURIComponent(id)}/retirement`,
    { expected_rule_id: expectedRuleId },
  )
}

export function getConfigHistory(filters: ConfigHistoryFilters, signal?: AbortSignal) {
  return apiGet<ConfigHistoryResponse>(`${BASE}/config-history`, {
    signal,
    query: {
      from: filters.from,
      to: filters.to,
      entity_type: filters.entity_type,
      entity_id: filters.entity_id,
      action: filters.action,
      configuration_version_id: filters.configuration_version_id,
      page: filters.page,
      page_size: filters.page_size,
    },
  })
}
```

---

## 13. Store `adminConfiguration.ts`

**Ruta**: `frontend/src/stores/adminConfiguration.ts`

### Estado

| Campo | Tipo | Uso |
|---|---|---|
| `categories` | `CategoryAdmin[]` | Catálogo |
| `priorities` | `PriorityAdmin[]` | Catálogo |
| `matrix` | `SlaMatrixResponse \| null` | Matriz vigente |
| `history` | `ConfigHistoryResponse \| null` | Histórico |
| `historyFilters` | `ConfigHistoryFilters` | Filtros |
| `loading` | `boolean` | Carga inicial |
| `saving` | `boolean` | Guardado |
| `error` | `ApiClientError \| null` | Error general |
| `conflict` | `string \| null` | Conflicto de versión |

### Acciones

- `loadAll()`: carga categorías, prioridades y matriz en paralelo.
- `reloadAll()`: limpia `conflict` y recarga todo.
- `createCategory`, `updateCategory`, `deleteCategory`.
- `createPriority`, `updatePriority`, `deletePriority`.
- `saveMatrix(changes)`: guarda el lote y recarga la matriz.
- `loadHistory(filters)`: carga una página del histórico.
- `clearConflict()`.

### Manejo de errores

- `ApiClientError.kind === 'conflict'` o `code === 'stale_configuration'`: guarda el mensaje en `conflict` y no descarta el borrador.
- `kind === 'forbidden'`: redirige a la landing segura.
- `kind === 'unauthorized'`: redirige a login con `redirect`.
- Errores de validación se devuelven al componente para mostrarlos bajo el campo.

---

## 14. Ruta y guard

`frontend/src/router/index.ts`:

```ts
{
  path: '/admin/configuracion',
  name: 'admin-configuration',
  component: () => import('@/views/AdminConfigurationPage.vue'),
  meta: { requiresAdmin: true },
}
```

`frontend/src/router/landing.ts`:

```ts
export const ADMIN_CONFIGURATION_PATH = '/admin/configuracion'

export function landingForRole(role: string | null | undefined): string {
  if (role === 'usuario') return MY_TICKETS_PATH
  if (role === 'admin') return ADMIN_CONFIGURATION_PATH
  return WORK_QUEUE_PATH
}
```

Guard:

```ts
router.beforeEach((to) => {
  if (!to.meta.requiresAdmin) return true
  if (getStoredUserRole() === 'admin') return true
  return { name: 'login', query: { redirect: to.fullPath } }
})
```

El guard es solo UX; el backend devuelve `403` aunque se fuerce la ruta.

---

## 15. Integración con login y seed

- `frontend/src/views/LoginPage.vue` añade `admin@example.com` a `DEV_USERS` con la etiqueta «Administración · configuración».
- `backend/scripts/seed_dev.py` crea `admin@example.com` con `role=UserRole.admin`, `name="Administración"` y `is_active=True`.
- El seed garantiza una categoría default (`Otros`), una prioridad default (`Media`) y una versión base si no existe.

---

## 16. Criterios de aceptación visual

1. La página usa la misma paleta `slate`/`sky`, radios `rounded-xl`/`rounded-2xl` y sombras `shadow-sm` que las vistas existentes.
2. Las tablas no rompen el layout en 360 px: se desplazan horizontalmente y mantienen las acciones accesibles.
3. Los diálogos atrapan el foco, se cierran con `Esc` y devuelven el foco al botón que los abrió.
4. Los errores y conflictos son visibles con lector de pantalla (`role="alert"`).
5. Las fechas se muestran en español de España y `Europe/Madrid`.
6. No hay `v-html` ni interpolación de clases Tailwind dinámicas.
7. El botón Guardar se deshabilita durante el envío y muestra «Guardando…».
8. La matriz indica claramente qué celdas tienen regla propia y cuáles usan el plazo base.
