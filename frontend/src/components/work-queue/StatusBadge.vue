<script setup lang="ts">
import type { TicketStatus } from '@/types/workQueue'

defineProps<{
  status: TicketStatus
  label: string
}>()

const PALETTE: Record<TicketStatus, string> = {
  abierto: 'bg-sky-100 text-sky-800 ring-1 ring-inset ring-sky-300',
  en_progreso: 'bg-indigo-100 text-indigo-800 ring-1 ring-inset ring-indigo-300',
  pendiente_usuario: 'bg-amber-100 text-amber-900 ring-1 ring-inset ring-amber-300',
  resuelto: 'bg-emerald-100 text-emerald-800 ring-1 ring-inset ring-emerald-300',
  cerrado: 'bg-slate-100 text-slate-700 ring-1 ring-inset ring-slate-300',
}
</script>

<template>
  <span
    class="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium"
    :class="PALETTE[status]"
  >
    {{ label }}
  </span>
</template>
