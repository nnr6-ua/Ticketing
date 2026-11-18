<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { Dialog, DialogPanel, DialogTitle } from '@headlessui/vue'

import type {
  PriorityAdmin,
  PriorityCreateRequest,
  PriorityUpdateRequest,
} from '@/types/adminConfiguration'

const props = defineProps<{
  open: boolean
  priority?: PriorityAdmin | null
  defaultCandidates?: PriorityAdmin[]
  saving?: boolean
  serverError?: { code: string; message: string } | null
  conflict?: string | null
}>()

const emit = defineEmits<{
  (event: 'update:open', value: boolean): void
  (
    event: 'submit',
    payload: PriorityCreateRequest | PriorityUpdateRequest,
  ): void
  (event: 'reload'): void
}>()

const form = reactive({
  name: '',
  level: 3,
  color: '#64748b',
  base_hours: '24.00',
  keywords: '',
  sort_order: 0,
  is_active: true,
  is_default: false,
  replacement_default_id: '',
})
const localError = ref<string | null>(null)

const editing = computed(() => props.priority !== null && props.priority !== undefined)
const candidates = computed(() =>
  (props.defaultCandidates ?? []).filter(
    (item) => item.id !== props.priority?.id && item.is_active && !item.is_system,
  ),
)
const needsReplacement = computed(
  () =>
    editing.value &&
    props.priority?.is_default === true &&
    (!form.is_active || !form.is_default),
)

watch(
  () => [props.open, props.priority] as const,
  ([open]) => {
    if (!open) return
    const priority = props.priority
    form.name = priority?.name ?? ''
    form.level = priority?.level ?? 3
    form.color = priority?.color ?? '#64748b'
    form.base_hours = priority?.base_hours ?? '24.00'
    form.keywords = (priority?.keywords ?? []).join(', ')
    form.sort_order = priority?.sort_order ?? 0
    form.is_active = priority?.is_active ?? true
    form.is_default = priority?.is_default ?? false
    form.replacement_default_id = ''
    localError.value = null
  },
  { immediate: true },
)

function keywords(): string[] {
  const seen = new Set<string>()
  return form.keywords
    .split(',')
    .map((item) => item.trim())
    .filter((item) => {
      const key = item.toLocaleLowerCase('es')
      if (!item || seen.has(key)) return false
      seen.add(key)
      return true
    })
}

function validHours(value: string): string | null {
  const normalized = value.trim().replace(',', '.')
  if (!/^\d{1,4}(\.\d{1,2})?$/.test(normalized) || Number(normalized) <= 0) {
    return null
  }
  return Number(normalized).toFixed(2)
}

function submit(): void {
  localError.value = null
  if (!form.name.trim()) {
    localError.value = 'El nombre es obligatorio.'
    return
  }
  if (form.level < 1 || form.level > 4) {
    localError.value = 'El nivel debe estar entre 1 y 4.'
    return
  }
  const baseHours = validHours(form.base_hours)
  if (!baseHours) {
    localError.value = 'El plazo base debe ser un número positivo de horas.'
    return
  }
  if (needsReplacement.value && !form.replacement_default_id) {
    localError.value =
      'Selecciona otra prioridad predeterminada antes de desactivar esta.'
    return
  }

  const common = {
    name: form.name.trim(),
    level: form.level,
    color: form.color || null,
    base_hours: baseHours,
    keywords: keywords(),
    sort_order: form.sort_order,
    is_default: form.is_default,
  }
  if (!editing.value) {
    emit('submit', common satisfies PriorityCreateRequest)
    return
  }
  emit('submit', {
    expected_revision: props.priority?.revision ?? 1,
    ...common,
    is_active: form.is_active,
    replacement_default_id: form.replacement_default_id || null,
  } satisfies PriorityUpdateRequest)
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
        <DialogPanel class="w-full max-w-lg rounded-2xl bg-white p-6 shadow-xl">
          <DialogTitle class="text-lg font-semibold text-slate-900">
            {{ editing ? 'Editar prioridad' : 'Nueva prioridad' }}
          </DialogTitle>

          <div v-if="conflict" class="mt-4 rounded-xl border border-amber-300 bg-amber-50 p-3" role="alert">
            <p class="text-sm text-amber-900">{{ conflict }}</p>
            <button
              type="button"
              class="mt-2 rounded-lg border border-amber-300 bg-white px-3 py-1.5 text-sm text-amber-900"
              @click="emit('reload')"
            >
              Recargar configuración
            </button>
          </div>
          <p
            v-if="serverError"
            class="mt-4 rounded-xl border border-rose-300 bg-rose-50 p-3 text-sm text-rose-800"
            role="alert"
          >
            {{ serverError.message }}
          </p>

          <form class="mt-4 space-y-4" @submit.prevent="submit">
            <div>
              <label for="priority-name" class="block text-sm font-medium text-slate-800">
                Nombre
              </label>
              <input
                id="priority-name"
                v-model="form.name"
                type="text"
                maxlength="50"
                required
                class="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm focus:border-sky-500 focus:ring-2 focus:ring-sky-500/20"
              />
            </div>
            <div class="grid gap-4 sm:grid-cols-2">
              <div>
                <label for="priority-level" class="block text-sm font-medium text-slate-800">
                  Nivel
                </label>
                <select
                  id="priority-level"
                  v-model.number="form.level"
                  class="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"
                >
                  <option :value="1">1 · Crítica</option>
                  <option :value="2">2 · Alta</option>
                  <option :value="3">3 · Media</option>
                  <option :value="4">4 · Baja</option>
                </select>
              </div>
              <div>
                <label for="priority-hours" class="block text-sm font-medium text-slate-800">
                  Plazo base (horas)
                </label>
                <input
                  id="priority-hours"
                  v-model="form.base_hours"
                  type="text"
                  inputmode="decimal"
                  required
                  class="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm focus:border-sky-500 focus:ring-2 focus:ring-sky-500/20"
                />
              </div>
            </div>
            <div>
              <label for="priority-color" class="block text-sm font-medium text-slate-800">
                Color
              </label>
              <div class="mt-1 flex items-center gap-3">
                <input
                  id="priority-color"
                  v-model="form.color"
                  type="color"
                  class="h-10 w-14 rounded border border-slate-300"
                />
                <input
                  v-model="form.color"
                  type="text"
                  pattern="^#[0-9A-Fa-f]{6}$"
                  class="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"
                />
              </div>
            </div>
            <div>
              <label for="priority-keywords" class="block text-sm font-medium text-slate-800">
                Palabras clave
              </label>
              <input
                id="priority-keywords"
                v-model="form.keywords"
                type="text"
                class="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm focus:border-sky-500 focus:ring-2 focus:ring-sky-500/20"
              />
              <p class="mt-1 text-xs text-slate-500">Sepáralas con comas.</p>
            </div>
            <div class="grid gap-4 sm:grid-cols-2">
              <div>
                <label for="priority-order" class="block text-sm font-medium text-slate-800">
                  Orden
                </label>
                <input
                  id="priority-order"
                  v-model.number="form.sort_order"
                  type="number"
                  min="0"
                  max="9999"
                  class="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"
                />
              </div>
              <div v-if="editing" class="pt-6">
                <label class="flex items-center gap-2 text-sm text-slate-800">
                  <input v-model="form.is_active" type="checkbox" />
                  Activa
                </label>
              </div>
            </div>
            <label class="flex items-center gap-2 text-sm text-slate-800">
              <input v-model="form.is_default" type="checkbox" />
              Predeterminada
            </label>
            <div v-if="needsReplacement">
              <label
                for="priority-replacement"
                class="block text-sm font-medium text-slate-800"
              >
                Nueva prioridad predeterminada
              </label>
              <select
                id="priority-replacement"
                v-model="form.replacement_default_id"
                class="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"
              >
                <option value="">Selecciona una prioridad</option>
                <option v-for="candidate in candidates" :key="candidate.id" :value="candidate.id">
                  {{ candidate.name }}
                </option>
              </select>
            </div>

            <p v-if="localError" class="text-sm text-rose-700" role="alert">
              {{ localError }}
            </p>

            <div class="flex justify-end gap-3 pt-2">
              <button
                type="button"
                class="rounded-xl border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700"
                :disabled="saving"
                @click="emit('update:open', false)"
              >
                Cancelar
              </button>
              <button
                type="submit"
                class="rounded-xl bg-sky-600 px-4 py-2 text-sm font-semibold text-white hover:bg-sky-700 disabled:opacity-60"
                :disabled="saving"
              >
                {{ saving ? 'Guardando…' : 'Guardar' }}
              </button>
            </div>
          </form>
        </DialogPanel>
      </div>
    </div>
  </Dialog>
</template>
