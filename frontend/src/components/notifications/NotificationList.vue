<script setup lang="ts">
import { computed } from 'vue'

import type { Notification } from '@/types/notifications'

const props = withDefaults(
  defineProps<{
    items: Notification[]
    loading?: boolean
    error?: string | null
  }>(),
  { loading: false, error: null },
)

const emit = defineEmits<{
  select: [notification: Notification]
  retry: []
}>()

const dateFormatter = new Intl.DateTimeFormat('es-ES', {
  dateStyle: 'medium',
  timeStyle: 'short',
  timeZone: 'Europe/Madrid',
})

const TITLES: Record<Notification['type'], string> = {
  ticket_reassigned: 'Ticket reasignado',
  ticket_escalated: 'Ticket escalado',
}

const isEmpty = computed(() => props.items.length === 0)

function titleFor(notification: Notification): string {
  return TITLES[notification.type]
}

function formatDate(value: string): string {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : dateFormatter.format(date)
}
</script>

<template>
  <div class="rounded-lg border border-slate-200 bg-white shadow-lg">
    <p
      v-if="loading"
      role="status"
      class="p-4 text-sm text-slate-700"
    >
      Cargando notificaciones…
    </p>

    <div v-else-if="error" role="alert" class="p-4 text-sm text-red-700">
      <p>{{ error }}</p>
      <button
        type="button"
        class="mt-2 underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-900 focus-visible:ring-offset-2"
        @click="emit('retry')"
      >
        Reintentar
      </button>
    </div>

    <p v-else-if="isEmpty" role="status" class="p-4 text-sm text-slate-700">
      No tienes notificaciones.
    </p>

    <ul v-else class="max-h-96 divide-y divide-slate-200 overflow-y-auto">
      <li v-for="notification in items" :key="notification.id">
        <button
          type="button"
          class="w-full px-4 py-3 text-left hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-900 focus-visible:ring-offset-2"
          @click="emit('select', notification)"
        >
          <span class="flex items-start justify-between gap-2">
            <span class="min-w-0">
              <span class="block text-sm font-medium text-slate-900">
                {{ titleFor(notification) }}
              </span>
              <span class="mt-0.5 block text-xs text-slate-600">
                {{ notification.ticket_number }} · {{ notification.ticket_title }}
              </span>
              <span class="mt-1 block text-xs text-slate-600">
                Anterior responsable: {{ notification.previous_assignee_name }}
              </span>
            </span>
            <span
              v-if="!notification.is_read"
              class="inline-flex shrink-0 items-center gap-1 rounded-full bg-sky-100 px-2 py-0.5 text-xs font-medium text-sky-900"
            >
              <span aria-hidden="true">•</span>
              No leída
            </span>
          </span>
          <time
            :datetime="notification.created_at"
            class="mt-1 block text-xs text-slate-600"
          >
            {{ formatDate(notification.created_at) }}
          </time>
        </button>
      </li>
    </ul>
  </div>
</template>
