<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import type {
  SlaDashboardFilters,
  SlaDashboardOptions,
} from '@/types/slaDashboard'

const props = withDefaults(
  defineProps<{
    filters: SlaDashboardFilters
    options: SlaDashboardOptions | null
    applying?: boolean
  }>(),
  { applying: false },
)

const emit = defineEmits<{
  (event: 'apply', value: SlaDashboardFilters): void
  (event: 'reset'): void
  (event: 'change', value: SlaDashboardFilters): void
}>()

function cloneFilters(value: SlaDashboardFilters): SlaDashboardFilters {
  return {
    desde: value.desde,
    hasta: value.hasta,
    categorias: [...value.categorias],
    prioridades: [...value.prioridades],
  }
}

const draft = ref<SlaDashboardFilters>(cloneFilters(props.filters))

watch(
  () => props.filters,
  (next) => {
    draft.value = cloneFilters(next)
  },
  { deep: true },
)

const invalidRange = computed(
  () =>
    Boolean(draft.value.desde) &&
    Boolean(draft.value.hasta) &&
    (draft.value.desde as string) > (draft.value.hasta as string),
)

const categoryOptions = computed(() => props.options?.categories ?? [])
const priorityOptions = computed(() => props.options?.priorities ?? [])

function formatIsoDate(value: string | null): string {
  if (!value) {
    return '—'
  }
  const [year, month, day] = value.split('-')
  return `${day}/${month}/${year}`
}

const activeSummary = computed(() => {
  const parts = [
    `Desde ${formatIsoDate(draft.value.desde)}`,
    `hasta ${formatIsoDate(draft.value.hasta)}`,
  ]
  if (draft.value.categorias.length > 0) {
    parts.push(
      `${draft.value.categorias.length} ${
        draft.value.categorias.length === 1 ? 'categoría' : 'categorías'
      }`,
    )
  }
  if (draft.value.prioridades.length > 0) {
    parts.push(
      `${draft.value.prioridades.length} ${
        draft.value.prioridades.length === 1 ? 'prioridad' : 'prioridades'
      }`,
    )
  }
  return parts.join(' · ')
})

function notifyChange(): void {
  emit('change', cloneFilters(draft.value))
}

function toggleCategory(id: string | null, event: Event): void {
  const key = id ?? 'sin_categoria'
  const checked = (event.target as HTMLInputElement).checked
  draft.value.categorias = checked
    ? [...draft.value.categorias.filter((value) => value !== key), key]
    : draft.value.categorias.filter((value) => value !== key)
  notifyChange()
}

function isCategorySelected(id: string | null): boolean {
  return draft.value.categorias.includes(id ?? 'sin_categoria')
}

function togglePriority(level: number, event: Event): void {
  const checked = (event.target as HTMLInputElement).checked
  draft.value.prioridades = checked
    ? [...draft.value.prioridades.filter((value) => value !== level), level].sort(
        (left, right) => left - right,
      )
    : draft.value.prioridades.filter((value) => value !== level)
  notifyChange()
}

function apply(): void {
  if (invalidRange.value) {
    return
  }
  emit('apply', cloneFilters(draft.value))
}

function reset(): void {
  emit('reset')
}
</script>

<template>
  <section
    class="rounded-lg border border-slate-200 bg-white p-4 shadow-sm"
    aria-labelledby="sla-filters-title"
    data-testid="sla-dashboard-filters"
  >
    <div class="flex flex-wrap items-baseline justify-between gap-2">
      <h2 id="sla-filters-title" class="text-sm font-semibold uppercase tracking-wide text-slate-700">
        Filtros
      </h2>
      <p class="text-sm text-slate-700" aria-live="polite" data-testid="sla-filters-summary">
        {{ activeSummary }}
      </p>
    </div>

    <div class="mt-4 grid gap-4 lg:grid-cols-2">
      <fieldset>
        <legend class="text-sm font-semibold text-slate-900">
          Rango de fechas
        </legend>
        <div class="mt-2 flex flex-wrap items-end gap-4">
          <div>
            <label for="sla-filter-desde" class="block text-sm text-slate-700">
              Desde
            </label>
            <input
              id="sla-filter-desde"
              v-model="draft.desde"
              type="date"
              class="mt-1 rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm text-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-900 focus-visible:ring-offset-2"
              :aria-invalid="invalidRange"
              :aria-describedby="invalidRange ? 'sla-filter-range-error' : undefined"
              @change="notifyChange"
            />
          </div>
          <div>
            <label for="sla-filter-hasta" class="block text-sm text-slate-700">
              Hasta
            </label>
            <input
              id="sla-filter-hasta"
              v-model="draft.hasta"
              type="date"
              class="mt-1 rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm text-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-900 focus-visible:ring-offset-2"
              :aria-invalid="invalidRange"
              :aria-describedby="invalidRange ? 'sla-filter-range-error' : undefined"
              @change="notifyChange"
            />
          </div>
        </div>
        <p
          v-if="invalidRange"
          id="sla-filter-range-error"
          class="mt-2 text-sm font-medium text-red-700"
          role="alert"
        >
          La fecha inicial no puede ser posterior a la fecha final.
        </p>
      </fieldset>

      <fieldset>
        <legend class="text-sm font-semibold text-slate-900">Prioridad</legend>
        <div class="mt-2 flex flex-wrap gap-2">
          <label
            v-for="option in priorityOptions"
            :key="option.level"
            :for="`sla-filter-prioridad-${option.level}`"
            class="cursor-pointer"
          >
            <input
              :id="`sla-filter-prioridad-${option.level}`"
              type="checkbox"
              class="peer sr-only"
              :checked="draft.prioridades.includes(option.level)"
              @change="togglePriority(option.level, $event)"
            />
            <span
              class="inline-flex items-center rounded-full border border-slate-300 bg-white px-3 py-1 text-sm text-slate-800 peer-checked:border-slate-900 peer-checked:bg-slate-900 peer-checked:text-white peer-focus-visible:ring-2 peer-focus-visible:ring-sky-700 peer-focus-visible:ring-offset-2"
            >
              {{ option.name }}
              <span v-if="!option.is_active" class="ml-1 text-xs">(inactiva)</span>
            </span>
          </label>
          <span v-if="priorityOptions.length === 0" class="text-sm text-slate-600">
            No hay prioridades en el periodo.
          </span>
        </div>
      </fieldset>
    </div>

    <fieldset class="mt-4">
      <legend class="text-sm font-semibold text-slate-900">Categoría</legend>
      <div class="mt-2 flex flex-wrap gap-2">
        <label
          v-for="option in categoryOptions"
          :key="option.id ?? 'sin-categoria'"
          :for="`sla-filter-categoria-${option.id ?? 'sin-categoria'}`"
          class="cursor-pointer"
        >
          <input
            :id="`sla-filter-categoria-${option.id ?? 'sin-categoria'}`"
            type="checkbox"
            class="peer sr-only"
            :checked="isCategorySelected(option.id)"
            @change="toggleCategory(option.id, $event)"
          />
          <span
            class="inline-flex items-center rounded-full border border-slate-300 bg-white px-3 py-1 text-sm text-slate-800 peer-checked:border-slate-900 peer-checked:bg-slate-900 peer-checked:text-white peer-focus-visible:ring-2 peer-focus-visible:ring-sky-700 peer-focus-visible:ring-offset-2"
          >
            {{ option.name }}
            <span v-if="option.is_active === false" class="ml-1 text-xs">
              (inactiva)
            </span>
          </span>
        </label>
        <span v-if="categoryOptions.length === 0" class="text-sm text-slate-600">
          No hay categorías en el periodo.
        </span>
      </div>
    </fieldset>

    <div class="mt-4 flex flex-wrap gap-2">
      <button
        type="button"
        class="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-60"
        :disabled="invalidRange || applying"
        :aria-describedby="invalidRange ? 'sla-filter-range-error' : undefined"
        @click="apply"
      >
        Aplicar
      </button>
      <button
        type="button"
        class="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-800 hover:bg-slate-100"
        @click="reset"
      >
        Restablecer
      </button>
    </div>
  </section>
</template>
