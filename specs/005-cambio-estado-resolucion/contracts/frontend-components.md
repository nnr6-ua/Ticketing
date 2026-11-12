# Contrato de componentes — HU-05

**Feature**: `005-cambio-estado-resolucion` | **Date**: 2026-11-02

Contrato de la interfaz Vue 3 + Tailwind para el cambio de estado, la resolución y los comentarios internos. Los componentes consumen el contrato HTTP de [ticket-workflow.openapi.yaml](./ticket-workflow.openapi.yaml); no hardcodean la matriz de transiciones ni la visibilidad.

---

## 1. Tipos compartidos

`frontend/src/types/ticketWorkflow.ts`:

```ts
export type TicketStatus =
  | 'abierto'
  | 'en_progreso'
  | 'pendiente_usuario'
  | 'resuelto'
  | 'cerrado'

export type TimelineEventType =
  | 'status_change'
  | 'resolution'
  | 'internal_comment'

export interface StatusOption {
  value: TicketStatus
  label: string
}

export interface AuthorRef {
  id: string
  name: string
  role: 'usuario' | 'tecnico' | 'supervisor' | 'admin'
}

export interface TimelineEntry {
  id: string
  type: TimelineEventType
  from_status: TicketStatus | null
  to_status: TicketStatus | null
  body: string | null
  is_internal: boolean
  author: AuthorRef
  created_at: string
}

export interface TicketWorkflowSnapshot {
  id: string
  number: string
  title: string
  status: TicketStatus
  status_label: string
  assignee_id: string | null
  creator_id: string
  finalized_at: string | null
  closed_at: string | null
  updated_at: string
  allowed_transitions: StatusOption[]
}

export interface WorkflowResponse {
  ticket: TicketWorkflowSnapshot
  can_change_status: boolean
  can_comment_internally: boolean
  can_view_internal: boolean
}

export interface StatusTransitionRequest {
  target_status: TicketStatus
  resolution?: string | null
  expected_updated_at: string
  request_id: string
}

export interface StatusTransitionResponse {
  changed: boolean
  message: string | null
  ticket: TicketWorkflowSnapshot
  timeline_entries: TimelineEntry[]
}

export interface InternalCommentRequest {
  body: string
  request_id: string
}

export interface InternalCommentResponse {
  entry: TimelineEntry
  created: boolean
}

export interface Pagination {
  page: number
  page_size: number
  total_items: number
  total_pages: number
  has_next: boolean
  has_previous: boolean
}

export interface TimelineResponse {
  items: TimelineEntry[]
  pagination: Pagination
}

export interface ApiErrorBody {
  detail: {
    code: string
    message: string
  }
}
```

---

## 2. `TicketStatusSelector.vue`

**Ruta**: `frontend/src/components/tickets/TicketStatusSelector.vue`

### Props

| Prop | Tipo | Obligatoria | Por defecto | Descripción |
|---|---|---|---|---|
| `currentStatus` | `TicketStatus` | Sí | — | Estado actual, mostrado como referencia |
| `options` | `StatusOption[]` | Sí | — | Estados permitidos calculados por el backend |
| `disabled` | `boolean` | No | `false` | Deshabilita la interacción durante el envío |

### Eventos

| Evento | Payload | Cuándo |
|---|---|---|
| `select` | `TicketStatus` | El usuario elige un destino permitido |

### Estados visuales

| Estado | Comportamiento |
|---|---|
| `options.length > 0` | `fieldset` con radios; el estado actual se muestra como texto, no como opción |
| `options.length === 0` | Mensaje «No hay cambios de estado disponibles.» y ningún control |
| `disabled` | Controles con `disabled` y `opacity-50` |

### Accesibilidad

- `<fieldset>` + `<legend>` «Nuevo estado».
- Radios nativos (navegación con flechas y espacio).
- `aria-describedby` con el texto de ayuda.
- Foco visible: `focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-900 focus-visible:ring-offset-2`.

### Ejemplo de uso

```vue
<TicketStatusSelector
  :current-status="ticket.status"
  :options="ticket.allowed_transitions"
  :disabled="submitting"
  @select="selectedTarget = $event"
/>
```

---

## 3. `ResolutionForm.vue`

**Ruta**: `frontend/src/components/tickets/ResolutionForm.vue`

### Props

| Prop | Tipo | Obligatoria | Por defecto | Descripción |
|---|---|---|---|---|
| `modelValue` | `string` | Sí | — | Texto de la solución |
| `disabled` | `boolean` | No | `false` | Deshabilita el textarea |
| `error` | `string \| null` | No | `null` | Error de validación del servidor o del cliente |
| `maxLength` | `number` | No | `5000` | Límite de caracteres |

### Eventos

| Evento | Payload | Cuándo |
|---|---|---|
| `update:modelValue` | `string` | Cambia el texto |

### Reglas

- Visible solo cuando el destino seleccionado es `resuelto`.
- `required` lógico: no se puede enviar vacío ni solo con espacios.
- Contador calculado con `trim()`.
- Obligatorio: `aria-required="true"`.
- Error: `aria-invalid="true"` + `role="alert"`.
- Texto de ayuda: «Obligatoria para marcar el ticket como Resuelto. No podrás editarla después; si la solución cambia, reabre el ticket y documenta una nueva.»
- No usa `v-html`.

### Ejemplo

```vue
<ResolutionForm
  v-if="selectedTarget === 'resuelto'"
  v-model="resolutionText"
  :disabled="submitting"
  :error="resolutionError"
/>
```

---

## 4. `InternalCommentForm.vue`

**Ruta**: `frontend/src/components/tickets/InternalCommentForm.vue`

### Props

| Prop | Tipo | Obligatoria | Por defecto | Descripción |
|---|---|---|---|---|
| `modelValue` | `string` | Sí | — | Texto del comentario |
| `disabled` | `boolean` | No | `false` | Deshabilita el formulario |
| `error` | `string \| null` | No | `null` | Error mostrado bajo el textarea |

### Eventos

| Evento | Payload | Cuándo |
|---|---|---|
| `update:modelValue` | `string` | Cambia el texto |
| `submit` | — | El usuario pulsa «Añadir comentario interno» con texto válido |

### Reglas

- Disponible en cualquier estado, incluido `cerrado`.
- Válido si `trim().length` está entre 1 y 5.000.
- Botón deshabilitado si no es válido o si `disabled`.
- El padre genera `crypto.randomUUID()` al iniciar el envío; lo reutiliza solo para reintentos con el mismo texto y lo regenera si el usuario edita el comentario o tras un alta correcta.
- Texto de ayuda: «Solo visible para el técnico asignado, supervisores y administradores.»

### Ejemplo

```vue
<InternalCommentForm
  v-if="canComment"
  v-model="commentText"
  :disabled="submitting"
  :error="commentError"
  @submit="submitInternalComment"
/>
```

---

## 5. `TicketTimeline.vue`

**Ruta**: `frontend/src/components/tickets/TicketTimeline.vue`

### Props

| Prop | Tipo | Obligatoria | Por defecto | Descripción |
|---|---|---|---|---|
| `entries` | `TimelineEntry[]` | Sí | — | Entradas ya filtradas y ordenadas por el backend |
| `canSeeInternal` | `boolean` | Sí | — | Si es `false`, no se renderizan entradas `internal_comment` aunque lleguen |
| `loading` | `boolean` | No | `false` | Muestra el estado de carga |

### Renderizado por tipo

| Tipo | Presentación |
|---|---|
| `status_change` | «{autor} cambió el estado de {origen} a {destino}»; badge `bg-slate-100 text-slate-700` |
| `resolution` | Tarjeta «Resolución» con el texto; badge `bg-emerald-50 text-emerald-800` |
| `internal_comment` | Tarjeta «Interno» con el texto; badge `bg-amber-50 text-amber-800`; oculta si `!canSeeInternal` |

### Reglas

- Orden: el recibido del backend (`created_at`, `event_order`, `id`).
- Fechas: `Intl.DateTimeFormat('es-ES', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'Europe/Madrid' })`.
- Sin botones de edición ni borrado.
- Estado vacío: «Todavía no hay actividad en este ticket.»
- Estado de carga: `role="status"` con «Cargando la línea temporal…».
- Texto plano; nunca `v-html`.

---

## 6. `TicketWorkflowPanel.vue`

**Ruta**: `frontend/src/components/tickets/TicketWorkflowPanel.vue`

### Props

| Prop | Tipo | Obligatoria | Descripción |
|---|---|---|---|
| `ticketId` | `string` | Sí | UUID del ticket |

### Estado

El estado de servidor y las mutaciones viven en el store Pinia `useTicketDetailStore` (`frontend/src/stores/ticketDetail.ts`):

```ts
// storeToRefs(useTicketDetailStore())
ticket, timeline, pagination
canChangeStatus, canComment, canSeeInternal
loading, timelineLoading, submitting
error, errorCode, notice
resolutionText, commentText
```

El panel conserva solo estado de formulario y de petición:

```ts
const selectedTarget = ref<TicketStatus | null>(null)
const resolutionError = ref<string | null>(null)
const commentError = ref<string | null>(null)
const requestId = ref('')
const lastRequestSignature = ref('')
const commentRequestId = ref('')
const lastCommentSignature = ref('')
const resolutionInput = ref<{ focus: () => void } | null>(null)
const commentInput = ref<{ focus: () => void } | null>(null)
```

`expected_updated_at` no se duplica: se toma siempre de `ticket.updated_at`.

### Métodos

| Método | Descripción |
|---|---|
| `load()` | `store.loadWorkflow(ticketId)` + `store.loadTimeline(ticketId)`; el store inicializa `canChangeStatus`, `canSeeInternal` y `canComment` |
| `submitTransition()` | Valida, envía `store.transitionStatus`, actualiza estado y recarga timeline |
| `submitInternalComment()` | Valida, envía `store.addComment`, recarga timeline y limpia el texto |
| `store.refresh(ticketId)` | Recarga workflow y timeline; conserva textos |
| `store.transitionStatus` / `store.addComment` | Extraen `e.code`/`e.message` y aplican mensajes es-ES |

### Ciclo de vida de `request_id`

```ts
function ensureRequestId(): string {
  const signature = `${selectedTarget.value ?? ''}|${resolutionText.value.trim()}`
  if (!requestId.value || signature !== lastRequestSignature.value) {
    requestId.value = crypto.randomUUID()
    lastRequestSignature.value = signature
  }
  return requestId.value
}
```

- Se llama justo antes de `store.transitionStatus`.
- Se conserva si el envío falla por red, `409 stale_ticket` o `422` con el mismo payload.
- Se limpia tras éxito o no-op.
- Se regenera si cambia `target_status` o `resolution`.

### Regla de bloqueo

```ts
const resolutionIsValid = computed(
  () =>
    selectedTarget.value !== 'resuelto' ||
    resolutionText.value.trim().length > 0,
)

const canSubmit = computed(
  () =>
    !submitting.value &&
    selectedTarget.value !== null &&
    resolutionIsValid.value &&
    resolutionText.value.trim().length <= 5000,
)
```

- El botón «Guardar cambio» tiene `:disabled="!canSubmit"`.
- El `submit` vuelve a validar antes de llamar a la API.
- Mientras `submitting` es `true`, el botón muestra «Guardando…» y queda deshabilitado (anti doble clic).

### Payload de transición

- `resolution` solo se incluye cuando `selectedTarget === 'resuelto'`; en el resto se omite (no se envía `null`) para no disparar `422 resolution_not_allowed` (RF-034).
- El texto escrito se conserva localmente aunque se cambie de destino, pero no se envía.

### Manejo de errores

| `code` | UI |
|---|---|
| `resolution_required` | Error bajo el textarea: «Indica la descripción de la solución para marcar el ticket como Resuelto.» |
| `resolution_too_long` | Error bajo el textarea: «La descripción de la solución no puede superar los 5.000 caracteres.» |
| `invalid_transition` | Banner con el mensaje del backend; recarga `workflow` |
| `ticket_closed` | Banner; recarga `workflow` |
| `stale_ticket` | Banner: «El ticket ha sido modificado por otra persona. Actualiza la información e inténtalo de nuevo.»; recarga y conserva textos |
| `not_ticket_assignee` | Banner: «Este ticket ya no está asignado a ti.» |
| `comment_required` / `comment_too_long` | Error bajo el textarea de comentario |
| `request_id_reused` | Banner: «La solicitud ya se utilizó con otros datos. Genera una nueva solicitud e inténtalo de nuevo.»; no recarga la timeline; permite reintentar con un `request_id` nuevo. |
| Red / 500 | «No se pudo guardar el cambio. El ticket no se ha modificado. Inténtalo de nuevo.» |

### Anuncios accesibles

- `<p role="status" aria-live="polite">` para el éxito.
- `<p role="alert">` para errores.
- El foco se mueve al primer campo con error tras un `422`.

---

## 7. `TicketDetailPage.vue`

**Ruta**: `frontend/src/views/TicketDetailPage.vue` (ruta `/tickets/:id`)

- Obtiene `ticketId` de `useRoute().params.id`.
- Renderiza la cabecera del ticket (si HU-06 ya la aporta, se compone con ella).
- Monta `<TicketWorkflowPanel :ticket-id="ticketId" />`.
- Mantiene el enlace «Volver a la cola de trabajo» (`/cola-de-trabajo`) con el estilo existente.
- `TicketDetailPage.vue` ya sustituye al placeholder en la ruta; el detalle completo de HU-06 puede componerse dentro de este contenedor sin cambiar la ruta ni el panel.

---

## 8. Servicio `ticketWorkflow.ts`

**Ruta**: `frontend/src/services/ticketWorkflow.ts`

| Función | Método y ruta | Respuesta |
|---|---|---|
| `getWorkflow(ticketId)` | `GET /api/v1/tickets/{id}/workflow` | `WorkflowResponse` |
| `transitionStatus(ticketId, payload)` | `POST /api/v1/tickets/{id}/status-transitions` | `StatusTransitionResponse` |
| `addInternalComment(ticketId, payload)` | `POST /api/v1/tickets/{id}/internal-comments` | `InternalCommentResponse` |
| `getTimeline(ticketId, page, pageSize)` | `GET /api/v1/tickets/{id}/timeline?page=&page_size=` | `TimelineResponse` |

Reutiliza el cliente existente:

- `Authorization: Bearer <access_token>` desde `localStorage`.
- `credentials: 'omit'`.
- `Accept: application/json` y `Content-Type: application/json` en POST.
- Parseo de error: `{"detail": {"code", "message"}}`.
- Extensión: mapear `409` a `ApiClientError.kind = 'conflict'` conservando `status` y `code`. No se añaden métodos HTTP nuevos.

---

## 9. Criterios de aceptación visual

1. Un ticket `abierto` solo muestra «En progreso» como destino.
2. Un ticket `cerrado` no muestra ningún destino y explica que el cierre es definitivo.
3. Al elegir «Resuelto», aparece el textarea de resolución y el botón permanece deshabilitado hasta que el texto tenga contenido no blanco.
4. Con 5.001 caracteres, el contador se muestra en rojo y el botón se deshabilita (además del `maxlength`).
5. Al guardar con éxito, el badge de estado, el selector y la línea temporal se actualizan sin recargar la página.
6. El usuario creador no ve la tarjeta «Interno» en la línea temporal.
7. Un ticket cerrado permite añadir un comentario interno.
8. Un `409 stale_ticket` muestra el aviso, recarga los datos y conserva el texto escrito.
9. Todos los controles son usables solo con teclado y tienen foco visible.
10. Los mensajes están en español de España.
