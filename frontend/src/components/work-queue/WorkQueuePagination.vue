<script setup lang="ts">
import type { Pagination } from '@/types/workQueue'

const props = defineProps<{
  pagination: Pagination
  disabled: boolean
}>()

const emit = defineEmits<{ (event: 'change', page: number): void }>()

function goTo(page: number): void {
  if (!props.disabled) {
    emit('change', page)
  }
}
</script>

<template>
  <nav
    class="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-slate-200 bg-white px-4 py-3"
    aria-label="Paginación de la cola de trabajo"
    data-testid="work-queue-pagination"
  >
    <button
      type="button"
      class="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-800 hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-50"
      :disabled="disabled || !pagination.has_previous"
      @click="goTo(pagination.page - 1)"
    >
      Anterior
    </button>
    <p class="text-sm text-slate-700">
      Página {{ pagination.page }} de {{ pagination.total_pages }}
    </p>
    <button
      type="button"
      class="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-800 hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-50"
      :disabled="disabled || !pagination.has_next"
      @click="goTo(pagination.page + 1)"
    >
      Siguiente
    </button>
  </nav>
</template>
