<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'

import InternalCommentForm from '@/components/tickets/InternalCommentForm.vue'
import ResolutionForm from '@/components/tickets/ResolutionForm.vue'
import TicketStatusSelector from '@/components/tickets/TicketStatusSelector.vue'
import TicketTimeline from '@/components/tickets/TicketTimeline.vue'
import { useTicketDetailStore } from '@/stores/ticketDetail'
import type { TicketStatus } from '@/types/ticketWorkflow'

const props = defineProps<{ ticketId: string }>()

const store = useTicketDetailStore()
const {
  ticket,
  timeline,
  canChangeStatus,
  canComment,
  canSeeInternal,
  loading,
  timelineLoading,
  submitting,
  error,
  errorCode,
  resolutionText,
  commentText,
  notice,
} = storeToRefs(store)

const selectedTarget = ref<TicketStatus | null>(null)
const resolutionError = ref<string | null>(null)
const commentError = ref<string | null>(null)
const requestId = ref('')
const lastRequestSignature = ref('')
const commentRequestId = ref('')
const lastCommentSignature = ref('')
const resolutionInput = ref<{ focus: () => void } | null>(null)
const commentInput = ref<{ focus: () => void } | null>(null)

const RESOLUTION_REQUIRED_MESSAGE =
  'Indica la descripción de la solución para marcar el ticket como Resuelto.'
const RESOLUTION_TOO_LONG_MESSAGE =
  'La descripción de la solución no puede superar los 5.000 caracteres.'
const COMMENT_REQUIRED_MESSAGE = 'El comentario interno no puede estar vacío.'
const COMMENT_TOO_LONG_MESSAGE =
  'El comentario interno no puede superar los 5.000 caracteres.'

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

async function load(): Promise<void> {
  await store.loadWorkflow(props.ticketId)
  await store.loadTimeline(props.ticketId)
}

function ensureRequestId(): string {
  const signature = `${selectedTarget.value ?? ''}|${resolutionText.value.trim()}`
  if (!requestId.value || signature !== lastRequestSignature.value) {
    requestId.value = crypto.randomUUID()
    lastRequestSignature.value = signature
  }
  return requestId.value
}

function ensureCommentRequestId(): string {
  const signature = commentText.value.trim()
  if (!commentRequestId.value || signature !== lastCommentSignature.value) {
    commentRequestId.value = crypto.randomUUID()
    lastCommentSignature.value = signature
  }
  return commentRequestId.value
}

function resetTransitionRequest(): void {
  requestId.value = ''
  lastRequestSignature.value = ''
}

function resetCommentRequest(): void {
  commentRequestId.value = ''
  lastCommentSignature.value = ''
}

async function focusResolution(): Promise<void> {
  await nextTick()
  resolutionInput.value?.focus()
}

async function focusComment(): Promise<void> {
  await nextTick()
  commentInput.value?.focus()
}

function onSelectTarget(target: TicketStatus): void {
  selectedTarget.value = target
  resolutionError.value = null
}

async function submitTransition(): Promise<void> {
  if (!ticket.value || !canSubmit.value || selectedTarget.value === null) {
    return
  }

  const target = selectedTarget.value
  if (target === 'resuelto' && resolutionText.value.trim().length === 0) {
    resolutionError.value = RESOLUTION_REQUIRED_MESSAGE
    await focusResolution()
    return
  }
  if (resolutionText.value.trim().length > 5000) {
    resolutionError.value = RESOLUTION_TOO_LONG_MESSAGE
    await focusResolution()
    return
  }

  resolutionError.value = null
  const payload = {
    target_status: target,
    expected_updated_at: ticket.value.updated_at,
    request_id: ensureRequestId(),
    ...(target === 'resuelto'
      ? { resolution: resolutionText.value.trim() }
      : {}),
  }

  const response = await store.transitionStatus(props.ticketId, payload)
  if (response) {
    selectedTarget.value = null
    resolutionError.value = null
    commentError.value = null
    resetTransitionRequest()
  }
}

async function submitInternalComment(): Promise<void> {
  const body = commentText.value.trim()
  if (body.length === 0) {
    commentError.value = COMMENT_REQUIRED_MESSAGE
    await focusComment()
    return
  }
  if (body.length > 5000) {
    commentError.value = COMMENT_TOO_LONG_MESSAGE
    await focusComment()
    return
  }

  commentError.value = null
  const response = await store.addComment(
    props.ticketId,
    ensureCommentRequestId(),
  )
  if (response) {
    commentError.value = null
    resetCommentRequest()
  }
}

watch(resolutionText, () => {
  resolutionError.value = null
})

watch(commentText, () => {
  commentError.value = null
})

watch(errorCode, (code) => {
  if (code === 'request_id_reused') {
    resetTransitionRequest()
    resetCommentRequest()
  }
  if (code === 'resolution_required' || code === 'resolution_too_long') {
    resolutionError.value = error.value
    void focusResolution()
  }
  if (code === 'comment_required' || code === 'comment_too_long') {
    commentError.value = error.value
    void focusComment()
  }
})

watch(canChangeStatus, (allowed) => {
  if (!allowed) {
    selectedTarget.value = null
    resolutionError.value = null
    resetTransitionRequest()
  }
})

watch(
  () => props.ticketId,
  () => {
    store.reset()
    selectedTarget.value = null
    resolutionError.value = null
    commentError.value = null
    resetTransitionRequest()
    resetCommentRequest()
    void load()
  },
)

onMounted(() => {
  void load()
})
</script>

<template>
  <section class="space-y-6" aria-labelledby="ticket-workflow-heading">
    <div
      v-if="loading && !ticket"
      role="status"
      class="rounded-lg border border-slate-200 bg-white p-6 text-sm text-slate-700"
    >
      Cargando el ticket…
    </div>

    <div
      v-else-if="!ticket"
      role="alert"
      class="rounded-lg border border-red-200 bg-red-50 p-6 text-sm text-red-800"
    >
      <p>{{ error ?? 'No se pudo cargar el ticket.' }}</p>
      <button
        type="button"
        class="mt-3 rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-900 focus-visible:ring-offset-2"
        @click="load"
      >
        Reintentar
      </button>
    </div>

    <template v-else>
      <header class="rounded-lg border border-slate-200 bg-white p-6">
        <div class="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p class="text-sm font-medium text-slate-600">{{ ticket.number }}</p>
            <h1 id="ticket-workflow-heading" class="mt-1 text-2xl font-semibold text-slate-900">
              {{ ticket.title }}
            </h1>
          </div>
          <span
            class="inline-flex rounded-full bg-slate-100 px-3 py-1 text-sm font-medium text-slate-800"
          >
            {{ ticket.status_label }}
          </span>
        </div>
      </header>

      <p
        v-if="notice"
        role="status"
        aria-live="polite"
        class="rounded-lg border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800"
      >
        {{ notice }}
      </p>

      <div
        v-if="error"
        role="alert"
        class="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800"
      >
        <p>{{ error }}</p>
        <button
          type="button"
          class="mt-3 rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-900 focus-visible:ring-offset-2"
          @click="load"
        >
          Reintentar
        </button>
      </div>

      <div class="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div class="space-y-6">
          <div class="rounded-lg border border-slate-200 bg-white p-6">
            <TicketStatusSelector
              v-if="canChangeStatus"
              :key="ticket.updated_at"
              :current-status="ticket.status"
              :options="ticket.allowed_transitions"
              :disabled="submitting"
              @select="onSelectTarget"
            />

            <p
              v-else
              class="text-sm text-slate-700"
              role="status"
            >
              <template v-if="ticket.status === 'cerrado'">
                El cierre es definitivo: este ticket ya no admite cambios de estado.
              </template>
              <template v-else>
                No tienes permiso para cambiar el estado de este ticket.
              </template>
            </p>

            <ResolutionForm
              v-if="canChangeStatus && selectedTarget === 'resuelto'"
              ref="resolutionInput"
              v-model="resolutionText"
              class="mt-4"
              :disabled="submitting"
              :error="resolutionError"
            />

            <div v-if="canChangeStatus" class="mt-4">
              <button
                type="button"
                :disabled="!canSubmit"
                class="inline-flex items-center rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-900 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:bg-slate-300 disabled:text-slate-600"
                @click="submitTransition"
              >
                {{ submitting ? 'Guardando…' : 'Guardar cambio' }}
              </button>
            </div>
          </div>

          <div
            v-if="canComment"
            class="rounded-lg border border-slate-200 bg-white p-6"
          >
            <InternalCommentForm
              ref="commentInput"
              v-model="commentText"
              :disabled="submitting"
              :error="commentError"
              @submit="submitInternalComment"
            />
          </div>
        </div>

        <div class="rounded-lg border border-slate-200 bg-white p-6">
          <TicketTimeline
            :entries="timeline"
            :can-see-internal="canSeeInternal"
            :loading="timelineLoading && timeline.length === 0"
          />
        </div>
      </div>
    </template>
  </section>
</template>
