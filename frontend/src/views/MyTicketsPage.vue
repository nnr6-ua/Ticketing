<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'

import { ApiClientError, apiGet } from '@/api/client'
import type { MyTicketSummary, MyTicketsResponse } from '@/types/myTickets'

const router = useRouter()

const items = ref<MyTicketSummary[]>([])
const loading = ref(true)
const errorMessage = ref<string | null>(null)

const dateFormatter = new Intl.DateTimeFormat('es-ES', {
  dateStyle: 'medium',
  timeStyle: 'short',
  timeZone: 'Europe/Madrid',
})

function formatDate(value: string): string {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : dateFormatter.format(date)
}

async function load(): Promise<void> {
  loading.value = true
  errorMessage.value = null
  try {
    const response = await apiGet<MyTicketsResponse>('/api/v1/me/tickets')
    items.value = response.items
  } catch (caught) {
    if (caught instanceof ApiClientError && caught.kind === 'unauthorized') {
      await router.replace({
        name: 'login',
        query: { redirect: '/mis-tickets' },
      })
      return
    }
    errorMessage.value =
      caught instanceof ApiClientError
        ? caught.message
        : 'No se pudieron cargar tus tickets.'
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <main class="mx-auto max-w-5xl px-4 py-8 sm:px-6">
    <header class="mb-6 flex flex-wrap items-start justify-between gap-3">
      <div>
        <h1 class="text-2xl font-semibold tracking-tight text-slate-900">
          Mis tickets
        </h1>
        <p class="mt-1 text-sm text-slate-700">
          Consulta el estado y el historial de las incidencias que has creado.
        </p>
      </div>
      <RouterLink
        to="/tickets/new"
        class="inline-flex items-center rounded-lg bg-sky-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-sky-700 focus:outline-none focus:ring-2 focus:ring-sky-500 focus:ring-offset-2"
      >
        Nuevo ticket
      </RouterLink>
    </header>

    <p
      v-if="loading"
      class="rounded-lg border border-slate-200 bg-white p-6 text-sm text-slate-600"
      role="status"
    >
      Cargando tus tickets…
    </p>

    <div
      v-else-if="errorMessage"
      class="rounded-lg border border-red-200 bg-red-50 p-6"
      role="alert"
    >
      <p class="text-sm font-medium text-red-800">{{ errorMessage }}</p>
      <button
        type="button"
        class="mt-3 rounded-lg border border-red-300 bg-white px-4 py-2 text-sm font-medium text-red-700 hover:bg-red-100 focus:outline-none focus:ring-2 focus:ring-red-400 focus:ring-offset-2"
        @click="load"
      >
        Reintentar
      </button>
    </div>

    <div
      v-else-if="items.length === 0"
      class="rounded-lg border border-slate-200 bg-white p-8 text-center"
    >
      <p class="text-sm text-slate-700">
        Todavía no has creado ningún ticket.
      </p>
      <RouterLink
        to="/tickets/new"
        class="mt-4 inline-flex items-center rounded-lg bg-sky-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-sky-700 focus:outline-none focus:ring-2 focus:ring-sky-500 focus:ring-offset-2"
      >
        Crear mi primer ticket
      </RouterLink>
    </div>

    <ul v-else class="space-y-3">
      <li v-for="ticket in items" :key="ticket.id">
        <RouterLink
          :to="`/tickets/${ticket.id}`"
          class="flex flex-col gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm transition hover:border-sky-300 hover:shadow focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 focus-visible:ring-offset-2 sm:flex-row sm:items-center sm:justify-between"
        >
          <div class="min-w-0">
            <p class="font-mono text-sm font-semibold text-slate-500">
              {{ ticket.ticket_number }}
            </p>
            <p class="mt-1 truncate text-sm font-medium text-slate-900">
              {{ ticket.title }}
            </p>
            <p class="mt-1 text-xs text-slate-500">
              {{ formatDate(ticket.created_at) }}
              <span v-if="ticket.category"> · {{ ticket.category.name }}</span>
            </p>
          </div>
          <div class="flex flex-none items-center gap-3">
            <span class="inline-flex items-center gap-1.5 rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-700">
              <span
                class="h-2 w-2 rounded-full"
                :style="{ backgroundColor: ticket.priority.color ?? undefined }"
              />
              {{ ticket.priority.name }}
            </span>
            <span class="inline-flex rounded-full bg-sky-50 px-2.5 py-1 text-xs font-medium text-sky-800">
              {{ ticket.status_label }}
            </span>
          </div>
        </RouterLink>
      </li>
    </ul>
  </main>
</template>
