<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'

import AssigneeChangeReasonForm from '@/components/tickets/AssigneeChangeReasonForm.vue'
import AssigneeSelector from '@/components/tickets/AssigneeSelector.vue'
import EscalationLevelSelector from '@/components/tickets/EscalationLevelSelector.vue'
import { useTicketDetailStore } from '@/stores/ticketDetail'
import type {
  AssigneeChangeResponse,
  EscalationLevel,
} from '@/types/assigneeChange'
import type { TicketWorkflowSnapshot } from '@/types/ticketWorkflow'

type ChangeMode = 'reassign' | 'escalate'

const props = withDefaults(
  defineProps<{
    ticketId: string
    ticket: TicketWorkflowSnapshot
    canReassign: boolean
    canEscalate: boolean
    disabled?: boolean
  }>(),
  { disabled: false },
)

const emit = defineEmits<{
  changed: [response: AssigneeChangeResponse | null]
  notice: [message: string]
}>()

const store = useTicketDetailStore()
const {
  assigneeOptions,
  assigneeOptionsLoading,
  assigneeSubmitting,
  assigneeError,
  assigneeErrorCode,
  assigneeNotice,
} = storeToRefs(store)

const mode = ref<ChangeMode | null>(null)
const selectedAssigneeId = ref<string | null>(null)
const selectedLevel = ref<EscalationLevel | null>(null)
const reasonText = ref('')
const reasonError = ref<string | null>(null)
const requestId = ref('')
const lastRequestSignature = ref('')
const reasonInput = ref<{ focus: () => void } | null>(null)

const WORKFLOW_RELOAD_CODES = new Set([
  'stale_ticket',
  'ticket_finalized',
  'not_ticket_assignee',
  'assignee_inconsistent',
])

const REASON_REQUIRED_MESSAGE = 'Indica el motivo del cambio de responsable.'
const REASON_TOO_LONG_MESSAGE = 'El motivo no puede superar los 5.000 caracteres.'

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
    !assigneeSubmitting.value &&
    mode.value !== null &&
    destinationSelected.value &&
    reasonIsValid.value,
)

async function loadOptions(): Promise<void> {
  if (!props.canReassign && !props.canEscalate) {
    return
  }
  await store.loadAssigneeOptions(props.ticketId)
  if (
    assigneeErrorCode.value === 'ticket_finalized' ||
    assigneeErrorCode.value === 'not_ticket_assignee' ||
    assigneeErrorCode.value === 'assignee_inconsistent'
  ) {
    emit('changed', null)
  }
}

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

function resetRequest(): void {
  requestId.value = ''
  lastRequestSignature.value = ''
}

async function focusReason(): Promise<void> {
  await nextTick()
  reasonInput.value?.focus()
}

function selectMode(next: ChangeMode): void {
  mode.value = next
  reasonError.value = null
  resetRequest()
}

function clearSelection(): void {
  selectedAssigneeId.value = null
  selectedLevel.value = null
  reasonText.value = ''
  reasonError.value = null
  resetRequest()
}

async function submit(): Promise<void> {
  if (!canSubmit.value || mode.value === null) {
    return
  }

  const reason = reasonText.value.trim()
  if (reason.length === 0) {
    reasonError.value = REASON_REQUIRED_MESSAGE
    await focusReason()
    return
  }
  if (reason.length > 5000) {
    reasonError.value = REASON_TOO_LONG_MESSAGE
    await focusReason()
    return
  }
  reasonError.value = null

  const currentMode = mode.value
  const currentRequestId = ensureRequestId()

  const response =
    currentMode === 'reassign'
      ? await store.reassign(props.ticketId, {
          new_assignee_id: selectedAssigneeId.value as string,
          reason,
          expected_updated_at: props.ticket.updated_at,
          request_id: currentRequestId,
        })
      : await store.escalate(props.ticketId, {
          target_level: selectedLevel.value as EscalationLevel,
          reason,
          expected_updated_at: props.ticket.updated_at,
          request_id: currentRequestId,
        })

  if (response) {
    clearSelection()
    const message =
      assigneeNotice.value ?? 'El cambio de responsable se ha aplicado.'
    emit('notice', message)
    emit('changed', response)
    return
  }

  if (assigneeErrorCode.value === 'request_id_reused') {
    resetRequest()
  }
  if (
    assigneeErrorCode.value === 'reason_required' ||
    assigneeErrorCode.value === 'reason_too_long'
  ) {
    reasonError.value = assigneeError.value ?? REASON_REQUIRED_MESSAGE
    await focusReason()
  }
  if (
    assigneeErrorCode.value &&
    WORKFLOW_RELOAD_CODES.has(assigneeErrorCode.value)
  ) {
    emit('changed', null)
  }
}

watch(reasonText, () => {
  reasonError.value = null
})

watch(
  () => props.ticket.updated_at,
  () => {
    void loadOptions()
  },
)

watch(assigneeOptions, (options) => {
  if (!options) {
    selectedAssigneeId.value = null
    selectedLevel.value = null
    return
  }
  if (
    selectedAssigneeId.value &&
    !options.reassignment_candidates.some(
      (candidate) => candidate.id === selectedAssigneeId.value,
    )
  ) {
    selectedAssigneeId.value = null
  }
  if (
    selectedLevel.value &&
    !options.escalation_targets.some(
      (target) => target.value === selectedLevel.value && target.is_available,
    )
  ) {
    selectedLevel.value = null
  }
})

onMounted(() => {
  void loadOptions()
})
</script>

<template>
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

    <p v-if="assigneeOptionsLoading" role="status" class="mt-3 text-sm text-slate-700">
      Cargando compañeros y niveles…
    </p>

    <div v-else-if="assigneeError && !assigneeOptions" role="alert" class="mt-3 text-sm text-red-700">
      <p>{{ assigneeError }}</p>
      <button
        type="button"
        class="mt-2 underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-900 focus-visible:ring-offset-2"
        @click="loadOptions"
      >
        Reintentar
      </button>
    </div>

    <template v-else-if="assigneeOptions">
      <fieldset class="mt-4">
        <legend class="text-sm font-medium text-slate-800">Tipo de cambio</legend>
        <label v-if="canReassign" class="mt-2 flex items-center gap-2 text-sm text-slate-800">
          <input
            type="radio"
            name="assignee-change-mode"
            value="reassign"
            :checked="mode === 'reassign'"
            :disabled="disabled || assigneeSubmitting"
            class="h-4 w-4 border-slate-300 text-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-900 focus-visible:ring-offset-2"
            @change="selectMode('reassign')"
          />
          Reasignar a un compañero
        </label>
        <label v-if="canEscalate" class="mt-2 flex items-center gap-2 text-sm text-slate-800">
          <input
            type="radio"
            name="assignee-change-mode"
            value="escalate"
            :checked="mode === 'escalate'"
            :disabled="disabled || assigneeSubmitting"
            class="h-4 w-4 border-slate-300 text-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-900 focus-visible:ring-offset-2"
            @change="selectMode('escalate')"
          />
          Escalar a un nivel superior
        </label>
      </fieldset>

      <AssigneeSelector
        v-if="mode === 'reassign'"
        v-model="selectedAssigneeId"
        :candidates="assigneeOptions.reassignment_candidates"
        :disabled="disabled || assigneeSubmitting"
      />
      <EscalationLevelSelector
        v-else-if="mode === 'escalate'"
        v-model="selectedLevel"
        :targets="assigneeOptions.escalation_targets"
        :disabled="disabled || assigneeSubmitting"
      />
      <AssigneeChangeReasonForm
        v-if="mode"
        ref="reasonInput"
        v-model="reasonText"
        :disabled="disabled || assigneeSubmitting"
        :error="reasonError"
      />

      <p v-if="assigneeError" role="alert" class="mt-3 text-sm text-red-700">
        {{ assigneeError }}
      </p>
      <p
        v-if="assigneeNotice"
        role="status"
        aria-live="polite"
        class="mt-3 text-sm text-emerald-700"
      >
        {{ assigneeNotice }}
      </p>

      <div v-if="mode" class="mt-4 flex justify-end">
        <button
          type="button"
          :disabled="!canSubmit"
          class="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-900 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:bg-slate-300 disabled:text-slate-600"
          @click="submit"
        >
          {{ assigneeSubmitting ? 'Guardando…' : 'Confirmar cambio' }}
        </button>
      </div>
    </template>

    <p v-else class="mt-3 text-sm text-slate-700">
      No hay cambios de responsable disponibles para este ticket.
    </p>
  </section>
</template>
