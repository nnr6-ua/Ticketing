# Contrato de componentes — HU-03

**Feature**: `003-responder-peticion-tecnico` | **Date**: 2026-11-13

Contrato de la interfaz Vue 3 + Tailwind para solicitar y responder información. Los componentes consumen el contrato HTTP de [ticket-information.openapi.yaml](./ticket-information.openapi.yaml); no calculan permisos, transiciones ni recordatorios por su cuenta.

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
  | 'created'
  | 'status_change'
  | 'resolution'
  | 'internal_comment'
  | 'information_request'
  | 'user_response'

export interface TimelineEntry {
  id: string
  type: TimelineEventType
  from_status: TicketStatus | null
  to_status: TicketStatus | null
  body: string | null
  is_internal: boolean
  author: AuthorRef
  created_at: string
  reply_to_id: string | null
}

export interface InformationRequestRef {
  id: string
  body: string
  requested_at: string
  requested_by: AuthorRef
}

export interface WorkflowResponse {
  ticket: TicketWorkflowSnapshot
  can_change_status: boolean
  can_comment_internally: boolean
  can_view_internal: boolean
  can_request_information: boolean
  can_respond_to_information: boolean
  awaiting_user_response: boolean
  active_information_request: InformationRequestRef | null
  reminder_active: boolean
  reminder_due_at: string | null
}

export interface InformationRequestRequest {
  body: string
  expected_updated_at: string
  request_id: string
}

export interface InformationRequestResponse {
  changed: boolean
  message: string | null
  ticket: TicketWorkflowSnapshot
  timeline_entries: TimelineEntry[]
  information_request: InformationRequestRef
}

export interface InformationResponseRequest {
  body: string
  expected_updated_at: string
  request_id: string
}

export interface InformationResponseResponse {
  changed: boolean
  message: string | null
  ticket: TicketWorkflowSnapshot
  timeline_entries: TimelineEntry[]
  information_response: TimelineEntry
}
```

`frontend/src/types/myTickets.ts` añade a `MyTicketSummary`:

```ts
export interface MyTicketSummary {
  // campos existentes...
  awaiting_user_response: boolean
  response_requested_at: string | null
  reminder_active: boolean
  reminder_due_at: string | null
}
```

---

## 2. `InformationRequestForm.vue`

**Ruta**: `frontend/src/components/tickets/InformationRequestForm.vue`

Formulario controlado para que el técnico escriba la información que necesita. Sigue el patrón de `ResolutionForm.vue`.

### Props

| Prop | Tipo | Obligatoria | Por defecto | Descripción |
|---|---|---|---|---|
| `modelValue` | `string` | Sí | — | Texto de la petición |
| `disabled` | `boolean` | No | `false` | Bloquea el campo durante el envío |
| `error` | `string \| null` | No | `null` | Error de validación o del servidor |
| `maxLength` | `number` | No | `5000` | Límite visible y `maxlength` |

### Eventos

| Evento | Payload | Cuándo |
|---|---|---|
| `update:modelValue` | `string` | Cambia el texto |
| `submit` | — | El formulario válido se envía |

### Expone

| Método | Uso |
|---|---|
| `focus()` | Enfocar el `textarea` tras un error |

### Comportamiento

- Etiqueta: «Información que necesitas».
- Ayuda: «Explica al usuario qué dato concreto necesitas para continuar.»
- Contador `n / 5000` basado en `modelValue.trim()`.
- `submit` deshabilitado si el texto recortado está vacío, supera 5.000 o `disabled`.
- No envía por sí solo: el padre llama al store y pasa el `request_id`.

### Accesibilidad

- `label` asociada con `for`/`id`.
- `aria-required="true"`, `aria-invalid` cuando hay error y `aria-describedby` con ayuda, contador y error.
- `role="alert"` para el error.
- Foco visible con `focus-visible:ring-2 focus-visible:ring-slate-900`.

---

## 3. `InformationResponseForm.vue`

**Ruta**: `frontend/src/components/tickets/InformationResponseForm.vue`

Formulario controlado para que el creador responda. Muestra la petición activa o un aviso genérico si el ticket legado no tiene petición.

### Props

| Prop | Tipo | Obligatoria | Por defecto | Descripción |
|---|---|---|---|---|
| `modelValue` | `string` | Sí | — | Texto de la respuesta |
| `request` | `InformationRequestRef \| null` | Sí | — | Petición activa o `null` |
| `disabled` | `boolean` | No | `false` | Bloquea el campo durante el envío |
| `error` | `string \| null` | No | `null` | Error de validación o del servidor |
| `maxLength` | `number` | No | `5000` | Límite visible y `maxlength` |

### Eventos

| Evento | Payload | Cuándo |
|---|---|---|
| `update:modelValue` | `string` | Cambia el texto |
| `submit` | — | El formulario válido se envía |

### Expone

| Método | Uso |
|---|---|
| `focus()` | Enfocar el `textarea` tras un error |

### Comportamiento

- Si `request` existe, muestra un bloque destacado:
  - Etiqueta «El técnico necesita esta información».
  - Cuerpo de la petición con `whitespace-pre-wrap break-words`.
  - Autor y fecha formateada en `es-ES`.
- Si `request` es `null`, muestra un aviso neutro: «Este ticket está pendiente de tu respuesta. Escribe la información que necesite el equipo técnico.»
- Etiqueta del campo: «Tu respuesta».
- Contador y validación equivalentes a `InformationRequestForm`.
- `submit` deshabilitado si el texto recortado está vacío, supera 5.000 o `disabled`.

### Accesibilidad

- El bloque de la petición usa `role="note"` y `aria-labelledby`.
- Mismas reglas de `label`, `aria-describedby`, `aria-invalid` y `role="alert"`.
- El aviso genérico usa `role="status"`.

---

## 4. `TicketWorkflowPanel.vue` (modificado)

### Nuevo estado local

| Ref | Tipo | Uso |
|---|---|---|
| `informationRequestError` | `string \| null` | Error del formulario de petición |
| `informationResponseError` | `string \| null` | Error del formulario de respuesta |
| `informationRequestInput` | `{ focus: () => void } \| null` | Foco del formulario de petición |
| `informationResponseInput` | `{ focus: () => void } \| null` | Foco del formulario de respuesta |
| `informationRequestId` | `string` | Idempotencia de la petición |
| `informationResponseId` | `string` | Idempotencia de la respuesta |

### Cambios de comportamiento

1. Al seleccionar `pendiente_usuario` en `TicketStatusSelector`:
   - Se renderiza `InformationRequestForm` en lugar de `ResolutionForm`.
   - `canSubmit` exige texto válido además de `selectedTarget`.
   - `submitTransition` envía `store.requestInformation` con `body`, `expected_updated_at` y `request_id`.
   - No se usa el endpoint genérico de cambio de estado para este destino.
2. Si `canRespondToInformation`:
   - Se muestra un aviso destacado con la petición activa (o aviso genérico).
   - Se renderiza `InformationResponseForm` y un botón «Enviar respuesta».
   - `submitInformationResponse` envía `store.respondToInformation` con `body`, `expected_updated_at` y `request_id`.
3. Si `reminderActive`:
   - Se muestra un aviso contextual con `role="status"` y `aria-live="polite"`.
   - Texto: «Han pasado más de 48 horas desde la petición. El equipo técnico sigue esperando tu respuesta.»
4. Tras un envío correcto:
   - Se limpia el texto, el error y el `request_id`.
   - Se recarga el workflow y la primera página de la línea temporal.
   - Se muestra el `notice` existente o el mensaje de replay.
5. Al cambiar de ticket o perder la capacidad:
   - Se limpian textos, errores e identificadores de idempotencia.

### Mapeo de errores

| Código | Campo | Acción |
|---|---|---|
| `information_request_required` | petición | Mensaje y foco |
| `information_request_too_long` | petición | Mensaje y foco |
| `information_response_required` | respuesta | Mensaje y foco |
| `information_response_too_long` | respuesta | Mensaje y foco |
| `information_request_already_open` | global | `notice`/`error` |
| `invalid_transition` | global | `error` |
| `stale_ticket` | global | `error` y recarga |
| `request_id_reused` | global | `error` y regenerar identificadores |
| `forbidden` / `not_ticket_assignee` | global | `error` |
| `ticket_not_found` | global | `error` sin revelar datos del ticket |

---

## 5. `TicketTimeline.vue` (modificado)

Añade dos ramas de render:

| Tipo | Etiqueta | Estilo |
|---|---|---|
| `information_request` | «Petición de información» | Borde/fondo `sky` |
| `user_response` | «Respuesta del usuario» | Borde/fondo `indigo` o `blue` |

Reglas:

- Mantiene el orden recibido del servidor; no agrupa ni cita.
- Muestra autor y fecha con el mismo formato existente (`es-ES`).
- El cuerpo usa `whitespace-pre-wrap break-words`.
- `reply_to_id` no se muestra como texto; solo se usa en pruebas o depuración.
- Las entradas nuevas son públicas y no dependen de `canSeeInternal`.

---

## 6. `MyTicketsPage.vue` (modificado)

Cada fila muestra:

- Badge «Esperando tu respuesta» cuando `awaiting_user_response` es `true`.
- Recordatorio «Pendiente desde hace más de 48 horas» cuando `reminder_active` es `true`.
- El badge reutiliza los estilos de estado existentes; el recordatorio usa el mismo tono de aviso que el detalle.
- El enlace `RouterLink` a `/tickets/:id` se mantiene.
- No se muestra el cuerpo de la petición en la lista.

---

## 7. `stores/ticketDetail.ts` (modificado)

### Estado nuevo

```ts
informationRequest: InformationRequestRef | null
canRequestInformation: boolean
canRespondToInformation: boolean
awaitingUserResponse: boolean
reminderActive: boolean
reminderDueAt: string | null
informationRequestText: string
informationResponseText: string
```

### Acciones

```ts
requestInformation(ticketId: string, body: string): Promise<InformationRequestResponse | null>
respondToInformation(ticketId: string, body: string): Promise<InformationResponseResponse | null>
```

Responsabilidades:

- Validar el texto recortado y construir el payload con `expected_updated_at` del ticket y un `request_id` estable.
- Llamar al servicio HTTP.
- En éxito: actualizar `ticket`, añadir o recargar la línea temporal, limpiar textos y fijar `notice`.
- En replay (`changed = false`): no duplicar entradas y mostrar el mensaje del servidor.
- En error: fijar `error`/`errorCode` con el mensaje del backend.
- `loadWorkflow` aplica los campos nuevos del contrato.
- `reset` limpia todos los campos nuevos.

---

## 8. `services/ticketWorkflow.ts` (modificado)

```ts
export async function requestInformation(
  ticketId: string,
  payload: InformationRequestRequest,
): Promise<InformationRequestResponse>

export async function respondToInformation(
  ticketId: string,
  payload: InformationResponseRequest,
): Promise<InformationResponseResponse>
```

- `POST /api/v1/tickets/{ticketId}/information-requests`
- `POST /api/v1/tickets/{ticketId}/information-responses`
- Reutilizan el cliente HTTP, el manejo de `ApiErrorBody` y las cabeceras existentes.
- No envían `Content-Type` distinto de `application/json`.

---

## 9. Ejemplo de integración en el panel

```vue
<InformationRequestForm
  v-if="canChangeStatus && selectedTarget === 'pendiente_usuario'"
  ref="informationRequestInput"
  v-model="informationRequestText"
  :disabled="submitting"
  :error="informationRequestError"
/>

<InformationResponseForm
  v-if="canRespondToInformation"
  ref="informationResponseInput"
  v-model="informationResponseText"
  :request="informationRequest"
  :disabled="submitting"
  :error="informationResponseError"
  @submit="submitInformationResponse"
/>
```

---

## 10. Criterios de aceptación visuales

- La petición y la respuesta usan la misma tipografía, radios, bordes y espaciado que las tarjetas actuales.
- Los avisos y recordatorios son visibles sin desplazamiento en escritorio y se apilan correctamente en móvil.
- Los estados de foco son visibles con teclado.
- No aparece ninguna campana, bandeja de notificaciones, correo ni pantalla nueva.
- Los textos están en español de España y no exponen códigos internos.
