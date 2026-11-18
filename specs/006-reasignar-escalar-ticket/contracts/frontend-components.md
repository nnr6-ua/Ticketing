# Contrato de componentes — HU-06

**Feature**: `006-reasignar-escalar-ticket` | **Date**: 2026-11-10

Contrato de la interfaz Vue 3 + Tailwind para reasignar o escalar un ticket y
para mostrar las notificaciones del nuevo responsable. Los componentes
consumen el contrato HTTP de
[`assignee-change.openapi.yaml`](./assignee-change.openapi.yaml); no calculan
permisos, candidatos, niveles superiores ni el orden del catálogo.

Se reutilizan los tipos, el cliente HTTP (`apiGet`/`apiPost`), la paleta
`slate`, los patrones de accesibilidad y el store `useTicketDetailStore` de
HU-04/HU-05. No se añaden librerías de interfaz ni métodos HTTP nuevos.

---

## 1. Tipos compartidos

### 1.1. `frontend/src/types/assigneeChange.ts`

```ts
export type EscalationLevel = 'nivel_1' | 'nivel_2' | 'especialista'
export type AssigneeChangeKind = 'reassignment' | 'escalation'

export interface AssigneeRef {
  id: string
  name: string
  role: 'usuario' | 'tecnico' | 'supervisor' | 'admin'
  team: string | null
  escalation_level: EscalationLevel
  escalation_level_label: string
}

export interface EscalationTarget {
  value: EscalationLevel
  label: string
  technician_count: number
  is_available: boolean
}

export interface AssigneeChangeOptions {
  ticket_id: string
  status: TicketStatus
  current_assignee: AssigneeRef
  has_reassignment_candidates: boolean
  has_available_escalation_target: boolean
  reassignment_candidates: AssigneeRef[]
  escalation_targets: EscalationTarget[]
}

export interface ReassignmentRequest {
  new_assignee_id: string
  reason: string
  expected_updated_at: string
  request_id: string
}

export interface EscalationRequest {
  target_level: EscalationLevel
  reason: string
  expected_updated_at: string
  request_id: string
}

export interface AssigneeChangeResponse {
  changed: boolean
  message: string | null
  ticket: TicketWorkflowSnapshot
  previous_assignee: AssigneeRef
  new_assignee: AssigneeRef
  change_kind: AssigneeChangeKind
  from_escalation_level: EscalationLevel
  from_escalation_level_label: string
  to_escalation_level: EscalationLevel
  to_escalation_level_label: string
  timeline_entry: TimelineEntry | null
}
```

### 1.2. `frontend/src/types/notifications.ts`

```ts
export type NotificationType = 'ticket_reassigned' | 'ticket_escalated'

export interface Notification {
  id: string
  type: NotificationType
  ticket_id: string
  ticket_number: string
  ticket_title: string
  previous_assignee_name: string
  is_read: boolean
  created_at: string
  read_at: string | null
}

export interface NotificationListResponse {
  items: Notification[]
  unread_count: number
  pagination: Pagination
}

export interface MarkNotificationReadResponse {
  changed: boolean
  message: string | null
  notification: Notification
}
```

### 1.3. Ampliación de `frontend/src/types/ticketWorkflow.ts`

```ts
import type {
  AssigneeChangeKind,
  AssigneeRef,
  EscalationLevel,
} from '@/types/assigneeChange'

export type TimelineEventType =
  | 'status_change'
  | 'resolution'
  | 'internal_comment'
  | 'assignee_change'

export interface TimelineEntry {
  // Campos existentes de HU-05…
  type: TimelineEventType
  change_kind: AssigneeChangeKind | null
  previous_assignee: AssigneeRef | null
  new_assignee: AssigneeRef | null
  from_escalation_level: EscalationLevel | null
  from_escalation_level_label: string | null
  to_escalation_level: EscalationLevel | null
  to_escalation_level_label: string | null
}

export interface WorkflowResponse {
  // Campos existentes de HU-05…
  can_reassign: boolean
  can_escalate: boolean
}
```

Los campos nuevos son aditivos y siempre están presentes (`null` fuera de
`assignee_change`). Un cliente antiguo puede ignorarlos.

---

## 2. Árbol de componentes

```text
App.vue
├── AppHeader.vue                         (visible salvo en /login)
│   └── NotificationBell.vue
│       └── NotificationList.vue
└── RouterView
    └── TicketDetailPage.vue
        └── TicketWorkflowPanel.vue
            ├── TicketStatusSelector.vue      (HU-05, sin cambios)
            ├── ResolutionForm.vue            (HU-05, sin cambios)
            ├── InternalCommentForm.vue       (HU-05, sin cambios)
            ├── TicketAssigneeChangePanel.vue (NUEVO)
            │   ├── AssigneeSelector.vue
            │   ├── EscalationLevelSelector.vue
            │   └── AssigneeChangeReasonForm.vue
            └── TicketTimeline.vue            (ampliado)
```

`TicketAssigneeChangePanel` se monta en la columna izquierda del detalle,
después del panel de estado y antes del formulario de comentario interno. Solo
se monta si `canReassign || canEscalate`; el backend sigue siendo la defensa.

---

## 3. `TicketAssigneeChangePanel.vue`

**Ruta**: `frontend/src/components/tickets/TicketAssigneeChangePanel.vue`

### Props

| Prop | Tipo | Obligatoria | Por defecto | Descripción |
|---|---|---|---|---|
| `ticketId` | `string` | Sí | — | UUID del ticket |
| `ticket` | `TicketWorkflowSnapshot` | Sí | — | Snapshot con `updated_at` para el token de concurrencia |
| `canReassign` | `boolean` | Sí | — | Capacidad calculada por el backend |
| `canEscalate` | `boolean` | Sí | — | Capacidad calculada por el backend |
| `disabled` | `boolean` | No | `false` | Bloquea la interacción durante otra escritura |

### Eventos

| Evento | Payload | Cuándo |
|---|---|---|
| `changed` | `AssigneeChangeResponse` | Cambio aplicado o replay idempotente; el padre recarga workflow y timeline |
| `notice` | `string` | Mensaje para el `aria-live` del padre |

### Estado local

```ts
type ChangeMode = 'reassign' | 'escalate'

const mode = ref<ChangeMode | null>(null)
const options = ref<AssigneeChangeOptions | null>(null)
const optionsLoading = ref(false)
const optionsError = ref<string | null>(null)
const selectedAssigneeId = ref<string | null>(null)
const selectedLevel = ref<EscalationLevel | null>(null)
const reasonText = ref('')
const reasonError = ref<string | null>(null)
const requestId = ref('')
const lastRequestSignature = ref('')
const submitting = ref(false)
const error = ref<string | null>(null)
const errorCode = ref<string | null>(null)
const notice = ref<string | null>(null)
```

`expected_updated_at` no se duplica: se toma siempre de `props.ticket.updated_at`.

### Carga de opciones

1. Al montar y cuando cambie `props.ticket.updated_at`, si
   `canReassign || canEscalate`, llama a
   `GET /tickets/{id}/assignee-change-options` con `AbortController`.
2. Usa una secuencia creciente para descartar respuestas fuera de orden.
3. `409 ticket_finalized`: muestra el aviso, limpia `options` y no renderiza
   controles.
4. `403 not_ticket_assignee`: muestra «Este ticket ya no está asignado a ti.»
   y emite `changed` no aplica; el padre recarga el workflow para que el panel
   desaparezca.
5. Error de red o `500`: muestra un aviso con botón «Reintentar».

### Flujo de envío

1. Valida el modo y el destino: reasignación exige `selectedAssigneeId`;
   escalado exige `selectedLevel`.
2. `reasonText.trim()` debe tener entre 1 y 5.000 caracteres. Si no, asigna
   `reasonError`, enfoca el textarea y no llama a la API.
3. `submitting = true` y `ensureRequestId()` antes del POST.
4. Envía `POST /tickets/{id}/reassignments` o
   `POST /tickets/{id}/escalations` con `expected_updated_at`.
5. Éxito (`changed = true`): limpia selección y motivo, muestra «El cambio de
   responsable se ha aplicado.», emite `changed` y `notice`. Como el actor deja
   de ser responsable, el panel desaparece en la recarga.
6. Replay (`changed = false`): muestra el `message` del backend, limpia
   selección y emite `changed` sin duplicar nada.
7. `409 stale_ticket`, `ticket_finalized`, `invalid_reassignment_target`,
   `assignee_unavailable`, `invalid_escalation_level`, `no_higher_level` o
   `no_technicians_available`: muestra el mensaje, conserva el motivo, recarga
   opciones y emite `changed` para recargar workflow y timeline.
8. `409 request_id_reused`: muestra el mensaje y regenera `request_id` para el
   siguiente intento.
9. `422 reason_required` / `reason_too_long`: asocia el error al textarea y
   enfoca.
10. Error de red o `500`: «No se pudo guardar el cambio. El ticket no se ha
    modificado. Inténtalo de nuevo.» y conserva los datos.

### Ciclo de vida de `request_id`

```ts
function ensureRequestId(): string {
  const destination =
    mode.value === 'reassign'
      ? (selectedAssigneeId.value ?? '')
      : (selectedLevel.value ?? '')
  const signature = `${mode.value ?? ''}|${destination}|${reasonText.value.trim()}`

  if (!requestId.value || signature !== lastRequestSignature.value) {
    requestId.value = crypto.randomUUID()
    lastRequestSignature.value = signature
  }
  return requestId.value
}
```

- Se conserva si falla la red, `409 stale_ticket` o un `422` con el mismo
  payload.
- Se limpia tras éxito o replay.
- Se regenera si cambia el modo, el destino o el motivo.
- Nunca se comparte entre reasignación y escalado.

### Regla de bloqueo

```ts
const destinationSelected = computed(() =>
  mode.value === 'reassign'
    ? Boolean(selectedAssigneeId.value)
    : Boolean(selectedLevel.value),
)

const reasonIsValid = computed(() => {
  const length = reasonText.value.trim().length
  return length >= 1 && length <= 5000
})

const canSubmit = computed(
  () =>
    !props.disabled &&
    !submitting.value &&
    mode.value !== null &&
    destinationSelected.value &&
    reasonIsValid.value,
)
```

El botón «Confirmar cambio» tiene `:disabled="!canSubmit"` y muestra
«Guardando…» mientras `submitting` es `true` (anti doble clic).

### Plantilla (esquema)

```vue
<section
  class="rounded-lg border border-slate-200 bg-white p-6"
  aria-labelledby="assignee-change-heading"
>
  <h2 id="assignee-change-heading" class="text-base font-semibold text-slate-900">
    Cambiar responsable
  </h2>
  <p class="mt-1 text-sm text-slate-600">
    Registra el motivo; el usuario creador podrá verlo en la línea temporal.
  </p>

  <p v-if="optionsLoading" role="status" class="mt-3 text-sm text-slate-700">
    Cargando compañeros y niveles…
  </p>

  <div v-else-if="optionsError" role="alert" class="mt-3 text-sm text-red-700">
    <p>{{ optionsError }}</p>
    <button type="button" class="mt-2 underline" @click="loadOptions">Reintentar</button>
  </div>

  <template v-else-if="options">
    <fieldset class="mt-4">
      <legend class="text-sm font-medium text-slate-800">Tipo de cambio</legend>
      <label v-if="canReassign" class="mt-2 flex items-center gap-2 text-sm">
        <input v-model="mode" type="radio" value="reassign" :disabled="submitting" />
        Reasignar a un compañero
      </label>
      <label v-if="canEscalate" class="mt-2 flex items-center gap-2 text-sm">
        <input v-model="mode" type="radio" value="escalate" :disabled="submitting" />
        Escalar a un nivel superior
      </label>
    </fieldset>

    <AssigneeSelector
      v-if="mode === 'reassign'"
      v-model="selectedAssigneeId"
      :candidates="options.reassignment_candidates"
      :disabled="submitting"
    />
    <EscalationLevelSelector
      v-else-if="mode === 'escalate'"
      v-model="selectedLevel"
      :targets="options.escalation_targets"
      :disabled="submitting"
    />
    <AssigneeChangeReasonForm
      v-if="mode"
      ref="reasonInput"
      v-model="reasonText"
      :disabled="submitting"
      :error="reasonError"
    />

    <p v-if="error" role="alert" class="mt-3 text-sm text-red-700">{{ error }}</p>
    <p v-if="notice" role="status" aria-live="polite" class="mt-3 text-sm text-emerald-700">
      {{ notice }}
    </p>

    <div v-if="mode" class="mt-4 flex justify-end">
      <button
        type="button"
        :disabled="!canSubmit"
        class="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:bg-slate-300 disabled:text-slate-600"
        @click="submit"
      >
        {{ submitting ? 'Guardando…' : 'Confirmar cambio' }}
      </button>
    </div>
  </template>

  <p v-else class="mt-3 text-sm text-slate-700">
    No hay cambios de responsable disponibles para este ticket.
  </p>
</section>
```

---

## 4. `AssigneeSelector.vue`

**Ruta**: `frontend/src/components/tickets/AssigneeSelector.vue`

### Props

| Prop | Tipo | Obligatoria | Por defecto | Descripción |
|---|---|---|---|---|
| `modelValue` | `string \| null` | Sí | — | `id` del técnico seleccionado |
| `candidates` | `AssigneeRef[]` | Sí | — | Candidatos ya filtrados por el backend |
| `disabled` | `boolean` | No | `false` | Deshabilita el control |

### Eventos

| Evento | Payload | Cuándo |
|---|---|---|
| `update:modelValue` | `string \| null` | El usuario selecciona o limpia el destino |

### Reglas

- `<fieldset>` + `<legend>` «Compañero destino».
- `<select>` nativo con una opción inicial «Selecciona un compañero» y valor
  vacío; cada opción muestra `name` y `team` («Técnico B · Soporte»).
- Texto secundario por opción con `escalation_level_label`; no se muestran
  correo ni datos internos.
- Si `candidates.length === 0`, muestra «No hay compañeros disponibles de tu
  equipo y nivel.» y no renderiza el selector.
- No incluye al responsable actual ni al creador: el backend no los envía.
- `aria-required="true"` y `aria-describedby` con la ayuda.
- Emite `update:modelValue` con `id` o `null`.

### Ejemplo

```vue
<AssigneeSelector
  v-model="selectedAssigneeId"
  :candidates="options.reassignment_candidates"
  :disabled="submitting"
/>
```

---

## 5. `EscalationLevelSelector.vue`

**Ruta**: `frontend/src/components/tickets/EscalationLevelSelector.vue`

### Props

| Prop | Tipo | Obligatoria | Por defecto | Descripción |
|---|---|---|---|---|
| `modelValue` | `EscalationLevel \| null` | Sí | — | Nivel destino seleccionado |
| `targets` | `EscalationTarget[]` | Sí | — | Niveles superiores calculados por el backend |
| `disabled` | `boolean` | No | `false` | Deshabilita el control |

### Eventos

| Evento | Payload | Cuándo |
|---|---|---|
| `update:modelValue` | `EscalationLevel \| null` | El usuario selecciona un nivel disponible |

### Reglas

- `<fieldset>` + `<legend>` «Nivel destino».
- Solo renderiza los niveles devueltos por el backend; nunca calcula el orden
  en cliente.
- Cada nivel muestra `label` y, si `is_available = false`, el texto «Sin
  técnicos disponibles» y el control deshabilitado.
- Si `targets.length === 0`, muestra «El ticket ya está en el nivel máximo de
  soporte.» y no renderiza controles.
- El nivel seleccionado se limpia si deja de estar disponible tras una recarga.
- Emite `update:modelValue` con `value` o `null`.

### Ejemplo

```vue
<EscalationLevelSelector
  v-model="selectedLevel"
  :targets="options.escalation_targets"
  :disabled="submitting"
/>
```

---

## 6. `AssigneeChangeReasonForm.vue`

**Ruta**: `frontend/src/components/tickets/AssigneeChangeReasonForm.vue`

### Props

| Prop | Tipo | Obligatoria | Por defecto | Descripción |
|---|---|---|---|---|
| `modelValue` | `string` | Sí | — | Motivo del cambio |
| `disabled` | `boolean` | No | `false` | Deshabilita el textarea |
| `error` | `string \| null` | No | `null` | Error de validación |
| `maxLength` | `number` | No | `5000` | Límite de caracteres |

### Eventos

| Evento | Payload | Cuándo |
|---|---|---|
| `update:modelValue` | `string` | Cambia el texto |

### API expuesta

```ts
defineExpose({ focus: () => textareaRef.value?.focus() })
```

El panel usa esta función para enfocar el campo tras `reason_required` o
`reason_too_long`.

### Reglas

- `<label for="assignee-change-reason">Motivo del cambio de responsable</label>`.
- `<textarea rows="4" :maxlength="maxLength" aria-required="true">`.
- Ayuda: «Obligatorio. El usuario creador podrá ver este motivo en la línea
  temporal.»
- Contador visible `{{ modelValue.trim().length }} / {{ maxLength }}`.
- `:aria-invalid="Boolean(error)"` y `aria-describedby` apuntando al contador,
  la ayuda y el error.
- Error inline con `role="alert"`.
- Texto plano; nunca `v-html`.

### Ejemplo

```vue
<AssigneeChangeReasonForm
  ref="reasonInput"
  v-model="reasonText"
  :disabled="submitting"
  :error="reasonError"
/>
```

---

## 7. `NotificationBell.vue`

**Ruta**: `frontend/src/components/notifications/NotificationBell.vue`

### Props

Ninguna. Consume `useNotificationsStore` y `useRouter`.

### Estado del store utilizado

```ts
items, unreadCount, loading, error, open, hasMore
refresh(), markRead(id), toggle(), close()
```

### Comportamiento

- Botón con icono de campana (`lucide-vue-next`), `aria-label`
  «Notificaciones, N sin leer» y `aria-expanded`/`aria-controls` del
  desplegable.
- Contador visible si `unreadCount > 0`; `aria-live="polite"` para anunciar
  cambios sin interrumpir.
- Al abrir, carga la página 1 (20 elementos) si no hay datos o si han pasado
  más de 15 s desde la última carga.
- Al seleccionar una notificación:
  1. `POST /me/notifications/{id}/read`.
  2. Actualiza `unreadCount` con la respuesta del store.
  3. Navega a `/tickets/{ticket_id}`.
  4. Cierra el desplegable.
- Cierra con `Escape`, clic fuera o al navegar; devuelve el foco al botón.
- Si no hay token o la petición devuelve `401`, limpia los datos y detiene el
  sondeo; la vista de cola ya redirige al login.
- Los errores de red se muestran en el desplegable con botón «Reintentar» y no
  bloquean la navegación.

### Estructura

```vue
<div ref="root" class="relative">
  <button
    type="button"
    :aria-expanded="open"
    aria-controls="notification-panel"
    :aria-label="`Notificaciones, ${unreadCount} sin leer`"
    @click="toggle"
  >
    <Bell aria-hidden="true" />
    <span v-if="unreadCount > 0" aria-live="polite">{{ unreadCount }}</span>
  </button>

  <div v-if="open" id="notification-panel" class="absolute right-0 z-20 mt-2 w-80">
    <NotificationList
      :items="items"
      :loading="loading"
      :error="error"
      @select="onSelect"
      @retry="refresh"
    />
  </div>
</div>
```

---

## 8. `NotificationList.vue`

**Ruta**: `frontend/src/components/notifications/NotificationList.vue`

### Props

| Prop | Tipo | Obligatoria | Por defecto | Descripción |
|---|---|---|---|---|
| `items` | `Notification[]` | Sí | — | Notificaciones de la página actual |
| `loading` | `boolean` | No | `false` | Muestra el estado de carga |
| `error` | `string \| null` | No | `null` | Error de carga |

### Eventos

| Evento | Payload | Cuándo |
|---|---|---|
| `select` | `Notification` | El usuario pulsa una notificación |
| `retry` | — | El usuario pulsa «Reintentar» |

### Reglas

- Lista `<ul>` con `<li>` por notificación; cada elemento es un `<button>`
  accesible de ancho completo.
- Título «Ticket reasignado» / «Ticket escalado», `ticket_number`,
  `ticket_title` y «Anterior responsable: {previous_assignee_name}».
- Fecha con `Intl.DateTimeFormat('es-ES', { dateStyle: 'medium', timeStyle:
  'short', timeZone: 'Europe/Madrid' })`.
- Las no leídas se distinguen con el texto «No leída» y un punto, no solo con
  color.
- Estado vacío: «No tienes notificaciones.»
- Carga: `role="status"` con «Cargando notificaciones…».
- Error: `role="alert"` con el mensaje y un botón «Reintentar».
- El texto se renderiza como texto plano; nunca `v-html`.

---

## 9. `AppHeader.vue`

**Ruta**: `frontend/src/components/layout/AppHeader.vue`

- Cabecera común con enlace «Mesa de ayuda» a `/cola-de-trabajo`.
- Monta `NotificationBell` a la derecha.
- En `onMounted`, si existe `getAccessToken()`, llama a
  `notificationsStore.startPolling()`.
- En `onUnmounted`, llama a `notificationsStore.stopPolling()`.
- No se muestra en la ruta `login`.

`App.vue`:

```vue
<script setup lang="ts">
import { useRoute } from 'vue-router'

import AppHeader from '@/components/layout/AppHeader.vue'

const route = useRoute()
</script>

<template>
  <AppHeader v-if="route.name !== 'login'" />
  <RouterView />
</template>
```

---

## 10. `TicketWorkflowPanel.vue` (integración)

**Ruta**: `frontend/src/components/tickets/TicketWorkflowPanel.vue`

### Props

Sin cambios: `ticketId: string`.

### Ampliación del store

`useTicketDetailStore` añade:

```ts
canReassign, canEscalate
assigneeOptions, assigneeOptionsLoading
assigneeSubmitting, assigneeError, assigneeErrorCode, assigneeNotice
loadAssigneeOptions(ticketId)
reassign(ticketId, payload)
escalate(ticketId, payload)
refreshAfterAssigneeChange(ticketId)
```

`applyWorkflow` incorpora `can_reassign` y `can_escalate`. `reset()` los vuelve
a `false`.

### Composición

```vue
<TicketAssigneeChangePanel
  v-if="canReassign || canEscalate"
  :ticket-id="ticketId"
  :ticket="ticket"
  :can-reassign="canReassign"
  :can-escalate="canEscalate"
  :disabled="submitting"
  @changed="onAssigneeChanged"
  @notice="notice = $event"
/>
```

Se coloca en la columna izquierda, después del bloque de estado/resolución y
antes del comentario interno.

```ts
async function onAssigneeChanged(): Promise<void> {
  await store.refreshAfterAssigneeChange(props.ticketId)
}
```

Tras el cambio, el backend devuelve `can_reassign = false` y
`can_escalate = false` para el actor, por lo que el panel se desmonta y el
técnico anterior deja de ver acciones de escritura y comentarios internos.

---

## 11. `TicketTimeline.vue` (ampliación)

**Ruta**: `frontend/src/components/tickets/TicketTimeline.vue`

### Props

Sin cambios: `entries`, `canSeeInternal`, `loading`.

### Renderizado de `assignee_change`

| Campo | Presentación |
|---|---|
| Etiqueta | «Cambio de responsable» |
| Subtipo | «Reasignación» si `change_kind = 'reassignment'`; «Escalado a {to_escalation_level_label}» si `change_kind = 'escalation'` |
| Texto de reasignación | «{author.name} reasignó el ticket de {previous_assignee.name} a {new_assignee.name}.» |
| Texto de escalado | «{author.name} escaló el ticket de {previous_assignee.name} ({from_escalation_level_label}) a {new_assignee.name} ({to_escalation_level_label}).» |
| Motivo | Bloque «Motivo» con `entry.body` en texto plano (`whitespace-pre-wrap break-words`) |
| Estilo | Público, `border-sky-200 bg-sky-50 text-sky-900`; no usa el estilo interno ámbar |

Reglas:

- La entrada es visible para el creador porque el backend la envía con
  `is_internal = false`; no se añade lógica de visibilidad en cliente.
- Si `previous_assignee`, `new_assignee` o las etiquetas son `null` (datos
  antiguos o incompletos), se muestra un texto genérico «Se cambió el
  responsable del ticket.» sin romper el render.
- Las entradas de HU-05 se siguen renderizando sin cambios.
- Sin botones de edición ni borrado.
- Fechas en `Europe/Madrid` con el formato existente.

---

## 12. Servicios

### 12.1. `frontend/src/services/assigneeChange.ts`

| Función | Método y ruta | Respuesta |
|---|---|---|
| `getAssigneeChangeOptions(ticketId, signal?)` | `GET /api/v1/tickets/{id}/assignee-change-options` | `AssigneeChangeOptions` |
| `reassignTicket(ticketId, payload, signal?)` | `POST /api/v1/tickets/{id}/reassignments` | `AssigneeChangeResponse` |
| `escalateTicket(ticketId, payload, signal?)` | `POST /api/v1/tickets/{id}/escalations` | `AssigneeChangeResponse` |

### 12.2. `frontend/src/services/notifications.ts`

| Función | Método y ruta | Respuesta |
|---|---|---|
| `getNotifications({ page, page_size, unread_only }, signal?)` | `GET /api/v1/me/notifications` | `NotificationListResponse` |
| `markNotificationRead(notificationId, signal?)` | `POST /api/v1/me/notifications/{id}/read` | `MarkNotificationReadResponse` |

Reutilizan `apiGet`/`apiPost`:

- `Authorization: Bearer <access_token>` desde `localStorage`.
- `credentials: 'omit'`.
- `Accept: application/json` y `Content-Type: application/json` en POST.
- Parseo de `{"detail": {"code", "message"}}` como `ApiClientError` con
  `status`, `code` y `kind`.

---

## 13. Store `notifications.ts`

**Ruta**: `frontend/src/stores/notifications.ts`

```ts
export const POLL_INTERVAL_MS = 15_000
export const PAGE_SIZE = 20

export const useNotificationsStore = defineStore('notifications', () => {
  const items = ref<Notification[]>([])
  const unreadCount = ref(0)
  const loading = ref(false)
  const error = ref<string | null>(null)
  const open = ref(false)

  let timer: ReturnType<typeof setInterval> | null = null
  let sequence = 0
  let inFlight: AbortController | null = null

  async function refresh(): Promise<void>
  async function markRead(id: string): Promise<void>
  function toggle(): void
  function close(): void
  function startPolling(): void
  function stopPolling(): void
})
```

### Reglas del sondeo

- `POLL_INTERVAL_MS = 15_000`.
- `startPolling()` es idempotente: si ya hay temporizador, no crea otro.
- Cada tick ejecuta `refresh()` solo si
  `document.visibilityState !== 'hidden'`.
- `focus` y `visibilitychange` (visible) disparan `refresh()` inmediato.
- `stopPolling()` limpia el intervalo y los listeners; se llama en
  `onUnmounted` de `AppHeader`.
- Cada `refresh()` cancela la petición anterior con `AbortController` y usa una
  secuencia para descartar respuestas fuera de orden.
- `unreadCount` se toma de `response.unread_count`, no se cuenta localmente.
- Tras `markRead`, se actualiza el elemento y se usa el `unread_count` devuelto
  por el backend; si la respuesta no lo incluye, se decrementa solo si la
  notificación no estaba leída.
- Un `401` limpia `items`, `unreadCount` y detiene el sondeo.

El sondeo de la cola de trabajo (60 s) no se modifica.

---

## 14. Mensajes y mapeo de errores

| `code` | UI |
|---|---|
| `reason_required` | Error bajo el textarea: «Indica el motivo del cambio de responsable.»; foco al textarea |
| `reason_too_long` | «El motivo no puede superar los 5.000 caracteres.»; foco al textarea |
| `self_reassignment` | Banner: «No puedes reasignarte el ticket a ti mismo.» |
| `creator_not_assignable` | Banner: «Ese usuario no puede recibir este ticket.»; recarga opciones |
| `invalid_reassignment_target` | Banner: «Solo puedes reasignar a técnicos activos de tu equipo y de tu nivel.»; recarga opciones |
| `assignee_unavailable` | Banner: «El técnico seleccionado ya no está disponible. Actualiza la lista e inténtalo de nuevo.»; recarga opciones |
| `invalid_escalation_level` | Banner: «Debes elegir un nivel superior al del responsable actual.»; recarga opciones |
| `no_higher_level` | Banner: «El ticket ya está en el nivel máximo de soporte.»; recarga opciones |
| `no_technicians_available` | Banner: «No hay técnicos disponibles en ese nivel en este momento.»; recarga opciones |
| `stale_ticket` | Banner: «El ticket ha sido modificado por otra persona. Actualiza la información e inténtalo de nuevo.»; recarga workflow, timeline y opciones; conserva motivo |
| `ticket_finalized` | Banner: «El ticket está finalizado y no admite cambios de responsable.»; recarga workflow; el panel desaparece |
| `not_ticket_assignee` | Banner: «Este ticket ya no está asignado a ti.»; recarga workflow; el panel desaparece |
| `forbidden` | Banner: «No tienes permiso para modificar este ticket.» |
| `request_id_reused` | Banner: «La solicitud ya se utilizó con otros datos. Genera una nueva solicitud e inténtalo de nuevo.»; regenera `request_id` |
| `notification_not_found` | En la campana: «No se ha encontrado la notificación.»; recarga la bandeja |
| `not_authenticated` | Limpia la sesión y redirige a `/login`; detiene el sondeo |
| Red / `500` | «No se pudo guardar el cambio. El ticket no se ha modificado. Inténtalo de nuevo.»; conserva los datos |

---

## 15. Accesibilidad y responsive

- Grupos de radios y selects con `<fieldset>` + `<legend>` y etiquetas
  asociadas.
- `aria-required`, `aria-invalid` y `aria-describedby` en destino y motivo.
- Errores con `role="alert"`; éxitos con `role="status"` y `aria-live="polite"`.
- Foco visible en todos los controles:
  `focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-900
  focus-visible:ring-offset-2`.
- La campana funciona solo con teclado: `Enter`/`Espacio` abren, `Escape`
  cierra, el foco vuelve al botón y el desplegable no atrapa el foco.
- Las etiquetas textuales («No leída», «Reasignación», «Escalado», «Sin
  técnicos disponibles») evitan depender solo del color.
- Layout de una columna en móvil/tablet y dos columnas en desktop, igual que el
  detalle actual; el panel no depende del ancho.
- Se añaden pruebas con `axe-core` para `AssigneeSelector`,
  `EscalationLevelSelector`, `AssigneeChangeReasonForm`,
  `TicketAssigneeChangePanel` y `NotificationBell`, siguiendo
  `WorkQueueAccessibility.spec.ts`.

---

## 16. Criterios de aceptación visual

1. Un ticket activo asignado al técnico muestra «Cambiar responsable» con las
   opciones de reasignar y escalar según `can_reassign`/`can_escalate`.
2. Un ticket `resuelto` o `cerrado` no muestra controles y explica que está
   finalizado.
3. El creador, un supervisor, un administrador y un técnico no asignado no ven
   el panel; si llaman a la API reciben `403`.
4. La lista de compañeros no incluye al responsable actual ni al creador, y se
   limita al mismo equipo y nivel.
5. El selector de escalado solo muestra niveles superiores; un nivel sin
   técnicos aparece deshabilitado con «Sin técnicos disponibles».
6. El botón «Confirmar cambio» permanece deshabilitado sin destino o con un
   motivo vacío o de más de 5.000 caracteres.
7. Al confirmar, la línea temporal muestra «Cambio de responsable», el autor,
   el responsable anterior y nuevo, el motivo y la fecha, sin recargar la
   página.
8. El usuario creador ve la entrada con su motivo y sigue sin ver comentarios
   internos.
9. Tras el cambio, el panel desaparece para el técnico anterior y el ticket
   aparece en la cola del nuevo responsable en la siguiente actualización.
10. El nuevo responsable ve la campana con el contador incrementado en menos de
    30 segundos y puede marcar la notificación como leída.
11. Un `409 stale_ticket` muestra el aviso, recarga los datos y conserva el
    motivo escrito.
12. Todos los controles son usables solo con teclado y tienen foco visible; los
    mensajes están en español de España.
