<script setup lang="ts">
import { ref, watch } from 'vue'
import { Dialog, DialogPanel, DialogTitle } from '@headlessui/vue'

import type { CategoryRef, PriorityRef } from '@/types/adminConfiguration'

const props = defineProps<{
  open: boolean
  category: CategoryRef
  priority: PriorityRef
  currentHours: string | null
  hasRule: boolean
  error?: string | null
}>()

const emit = defineEmits<{
  (event: 'update:open', value: boolean): void
  (event: 'apply', value: { hours: string | null }): void
  (event: 'cancel'): void
}>()

const value = ref('')
const localError = ref<string | null>(null)
const confirmingRetire = ref(false)

watch(
  () => props.open,
  (open) => {
    if (!open) return
    value.value = props.currentHours ?? ''
    localError.value = null
    confirmingRetire.value = false
  },
  { immediate: true },
)

function accept(): void {
  localError.value = null
  const normalized = value.value.trim().replace(',', '.')
  if (!/^\d{1,4}(\.\d{1,2})?$/.test(normalized) || Number(normalized) <= 0) {
    localError.value = 'Introduce un número positivo de horas.'
    return
  }
  emit('apply', { hours: Number(normalized).toFixed(2) })
}

function retire(): void {
  if (!confirmingRetire.value) {
    confirmingRetire.value = true
    return
  }
  emit('apply', { hours: null })
}
</script>

<template>
  <Dialog
    :open="open"
    class="relative z-50"
    @close="emit('update:open', false)"
  >
    <div class="fixed inset-0 bg-slate-900/40" aria-hidden="true" />
    <div class="fixed inset-0 overflow-y-auto p-4">
      <div class="flex min-h-full items-center justify-center">
        <DialogPanel class="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl">
          <DialogTitle class="text-lg font-semibold text-slate-900">
            Plazo para {{ category.name }} × {{ priority.name }}
          </DialogTitle>
          <p id="sla-cell-help" class="mt-2 text-sm text-slate-600">
            Introduce horas naturales continuas. Ejemplo: 8 o 7,5.
          </p>

          <form class="mt-4" @submit.prevent="accept">
            <label for="sla-cell-hours" class="block text-sm font-medium text-slate-800">
              Horas
            </label>
            <input
              id="sla-cell-hours"
              v-model="value"
              type="text"
              inputmode="decimal"
              aria-describedby="sla-cell-help"
              class="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm focus:border-sky-500 focus:ring-2 focus:ring-sky-500/20"
            />
            <p v-if="localError || error" class="mt-2 text-sm text-rose-700" role="alert">
              {{ localError || error }}
            </p>

            <div v-if="hasRule" class="mt-4 rounded-xl border border-rose-200 bg-rose-50 p-3">
              <p class="text-sm text-rose-900">
                Al retirar la regla se aplicará el plazo base de la prioridad.
              </p>
              <button
                type="button"
                class="mt-2 rounded-lg border border-rose-300 bg-white px-3 py-1.5 text-sm font-semibold text-rose-800"
                @click="retire"
              >
                {{ confirmingRetire ? 'Confirmar retirada' : 'Retirar regla' }}
              </button>
            </div>

            <div class="mt-6 flex justify-end gap-3">
              <button
                type="button"
                class="rounded-xl border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700"
                @click="emit('cancel'); emit('update:open', false)"
              >
                Cancelar
              </button>
              <button
                type="submit"
                class="rounded-xl bg-sky-600 px-4 py-2 text-sm font-semibold text-white hover:bg-sky-700"
              >
                Guardar
              </button>
            </div>
          </form>
        </DialogPanel>
      </div>
    </div>
  </Dialog>
</template>
