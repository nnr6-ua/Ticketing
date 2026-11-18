<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { Dialog, DialogPanel, DialogTitle } from '@headlessui/vue'

import type {
  CategoryAdmin,
  CategoryCreateRequest,
  CategoryUpdateRequest,
} from '@/types/adminConfiguration'

const props = defineProps<{
  open: boolean
  category?: CategoryAdmin | null
  defaultCandidates?: CategoryAdmin[]
  saving?: boolean
  serverError?: { code: string; message: string } | null
  conflict?: string | null
}>()

const emit = defineEmits<{
  (event: 'update:open', value: boolean): void
  (
    event: 'submit',
    payload: CategoryCreateRequest | CategoryUpdateRequest,
  ): void
  (event: 'reload'): void
}>()

const form = reactive({
  name: '',
  description: '',
  keywords: '',
  sort_order: 0,
  is_active: true,
  is_default: false,
  replacement_default_id: '',
})
const localError = ref<string | null>(null)

const editing = computed(() => props.category !== null && props.category !== undefined)
const candidates = computed(() =>
  (props.defaultCandidates ?? []).filter(
    (item) => item.id !== props.category?.id && item.is_active && !item.is_system,
  ),
)
const needsReplacement = computed(
  () =>
    editing.value &&
    props.category?.is_default === true &&
    (!form.is_active || !form.is_default),
)

watch(
  () => [props.open, props.category] as const,
  ([open]) => {
    if (!open) return
    const category = props.category
    form.name = category?.name ?? ''
    form.description = category?.description ?? ''
    form.keywords = (category?.keywords ?? []).join(', ')
    form.sort_order = category?.sort_order ?? 0
    form.is_active = category?.is_active ?? true
    form.is_default = category?.is_default ?? false
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

function submit(): void {
  localError.value = null
  if (!form.name.trim()) {
    localError.value = 'El nombre es obligatorio.'
    return
  }
  if (needsReplacement.value && !form.replacement_default_id) {
    localError.value =
      'Selecciona otra categoría predeterminada antes de desactivar esta.'
    return
  }

  const common = {
    name: form.name.trim(),
    description: form.description.trim() || null,
    keywords: keywords(),
    sort_order: form.sort_order,
    is_default: form.is_default,
  }
  if (!editing.value) {
    emit('submit', common satisfies CategoryCreateRequest)
    return
  }
  emit('submit', {
    expected_revision: props.category?.revision ?? 1,
    ...common,
    is_active: form.is_active,
    replacement_default_id: form.replacement_default_id || null,
  } satisfies CategoryUpdateRequest)
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
            {{ editing ? 'Editar categoría' : 'Nueva categoría' }}
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
              <label for="category-name" class="block text-sm font-medium text-slate-800">
                Nombre
              </label>
              <input
                id="category-name"
                v-model="form.name"
                type="text"
                maxlength="100"
                required
                :aria-describedby="localError ? 'category-error' : undefined"
                class="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm focus:border-sky-500 focus:ring-2 focus:ring-sky-500/20"
              />
            </div>
            <div>
              <label for="category-description" class="block text-sm font-medium text-slate-800">
                Descripción
              </label>
              <textarea
                id="category-description"
                v-model="form.description"
                rows="3"
                maxlength="2000"
                class="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm focus:border-sky-500 focus:ring-2 focus:ring-sky-500/20"
              />
            </div>
            <div>
              <label for="category-keywords" class="block text-sm font-medium text-slate-800">
                Palabras clave
              </label>
              <input
                id="category-keywords"
                v-model="form.keywords"
                type="text"
                class="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm focus:border-sky-500 focus:ring-2 focus:ring-sky-500/20"
              />
              <p class="mt-1 text-xs text-slate-500">Sepáralas con comas.</p>
            </div>
            <div class="grid gap-4 sm:grid-cols-2">
              <div>
                <label for="category-order" class="block text-sm font-medium text-slate-800">
                  Orden
                </label>
                <input
                  id="category-order"
                  v-model.number="form.sort_order"
                  type="number"
                  min="0"
                  max="9999"
                  class="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm focus:border-sky-500 focus:ring-2 focus:ring-sky-500/20"
                />
              </div>
              <div v-if="editing" class="space-y-2 pt-6">
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
                for="category-replacement"
                class="block text-sm font-medium text-slate-800"
              >
                Nueva categoría predeterminada
              </label>
              <select
                id="category-replacement"
                v-model="form.replacement_default_id"
                class="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"
              >
                <option value="">Selecciona una categoría</option>
                <option v-for="candidate in candidates" :key="candidate.id" :value="candidate.id">
                  {{ candidate.name }}
                </option>
              </select>
            </div>

            <p
              v-if="localError"
              id="category-error"
              class="text-sm text-rose-700"
              role="alert"
            >
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
