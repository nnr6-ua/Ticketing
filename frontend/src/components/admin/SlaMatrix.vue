<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import ConflictBanner from '@/components/admin/ConflictBanner.vue'
import SlaCellEditor from '@/components/admin/SlaCellEditor.vue'
import type {
  CategoryRef,
  PriorityRef,
  SlaChange,
  SlaMatrixResponse,
  SlaRuleAdmin,
} from '@/types/adminConfiguration'

const props = defineProps<{
  matrix: SlaMatrixResponse | null
  saving?: boolean
  conflict?: string | null
}>()

const emit = defineEmits<{
  (event: 'save', changes: SlaChange[]): void
  (event: 'reload'): void
}>()

const draft = ref<Record<string, string | null>>({})
const editing = ref<{
  category: CategoryRef
  priority: PriorityRef
  hasRule: boolean
} | null>(null)

const categories = computed(() => props.matrix?.combinations.categories ?? [])
const priorities = computed(() => props.matrix?.combinations.priorities ?? [])

watch(
  () => props.matrix,
  () => {
    draft.value = {}
    editing.value = null
  },
)

function key(categoryId: string, priorityId: string): string {
  return `${categoryId}:${priorityId}`
}

function ruleFor(
  categoryId: string,
  priorityId: string,
): SlaRuleAdmin | undefined {
  return props.matrix?.items.find(
    (item) =>
      item.category.id === categoryId && item.priority.id === priorityId,
  )
}

function hoursFor(categoryId: string, priorityId: string): string | null {
  const current = draft.value[key(categoryId, priorityId)]
  if (current !== undefined) return current
  return ruleFor(categoryId, priorityId)?.hours ?? null
}

function formatHours(value: string | null): string {
  if (value === null) return ''
  const number = Number(value)
  if (!Number.isFinite(number)) return `${value} h`
  return `${Number.isInteger(number) ? number : number.toFixed(1).replace('.', ',')} h`
}

function openEditor(category: CategoryRef, priority: PriorityRef): void {
  editing.value = {
    category,
    priority,
    hasRule: ruleFor(category.id, priority.id) !== undefined,
  }
}

function editingHours(): string | null {
  if (!editing.value) return null
  return hoursFor(editing.value.category.id, editing.value.priority.id)
}

function applyCell(value: { hours: string | null }): void {
  if (!editing.value) return
  draft.value = {
    ...draft.value,
    [key(editing.value.category.id, editing.value.priority.id)]: value.hours,
  }
  editing.value = null
}

const isDirty = computed(() => Object.keys(draft.value).length > 0)

function discard(): void {
  draft.value = {}
}

function save(): void {
  const changes: SlaChange[] = []
  for (const [cell, value] of Object.entries(draft.value)) {
    const [categoryId, priorityId] = cell.split(':')
    if (!categoryId || !priorityId) continue
    const rule = ruleFor(categoryId, priorityId)
    if (value === null) {
      if (rule) {
        changes.push({
          operation: 'retire',
          rule_id: rule.id,
          expected_rule_id: rule.id,
        })
      }
      continue
    }
    if (rule && Number(rule.hours) === Number(value)) continue
    changes.push({
      operation: 'upsert',
      category_id: categoryId,
      priority_id: priorityId,
      hours: value,
      expected_rule_id: rule?.id ?? null,
    })
  }
  if (changes.length > 0) {
    emit('save', changes)
  }
}
</script>

<template>
  <section class="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <div>
        <h2 class="text-lg font-semibold text-slate-900">Matriz de plazos</h2>
        <p class="text-sm text-slate-600">
          Regla propia por categoría y prioridad. Sin regla se usa el plazo base.
        </p>
      </div>
      <p v-if="matrix" class="text-xs text-slate-500">
        Versión v{{ matrix.configuration_version.version }}
      </p>
    </div>

    <ConflictBanner
      v-if="conflict"
      :message="conflict"
      :reloading="saving"
      class="mt-4"
      @reload="emit('reload')"
    />

    <div class="mt-4 overflow-x-auto">
      <table class="min-w-full border-separate border-spacing-0 text-sm">
        <caption class="sr-only">Matriz de plazos por categoría y prioridad</caption>
        <thead>
          <tr>
            <th scope="col" class="border-b border-slate-200 px-3 py-2 text-left text-slate-600">
              Categoría
            </th>
            <th
              v-for="priority in priorities"
              :key="priority.id"
              scope="col"
              class="border-b border-slate-200 px-3 py-2 text-left text-slate-600"
            >
              <span class="block font-semibold text-slate-900">{{ priority.name }}</span>
              <span class="block text-xs text-slate-500">Nivel {{ priority.level }}</span>
              <span class="block text-xs text-slate-500">
                Base: {{ formatHours(priority.base_hours) || '—' }}
              </span>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="category in categories" :key="category.id">
            <th scope="row" class="border-b border-slate-100 px-3 py-2 text-left font-medium text-slate-900">
              {{ category.name }}
            </th>
            <td
              v-for="priority in priorities"
              :key="priority.id"
              class="border-b border-slate-100 px-3 py-2"
            >
              <button
                type="button"
                class="w-full rounded-lg border border-slate-200 px-3 py-2 text-left hover:border-sky-400 hover:bg-sky-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
                :aria-label="`Plazo para ${category.name} × ${priority.name}`"
                :aria-describedby="`cell-help-${category.id}-${priority.id}`"
                :disabled="saving"
                @click="openEditor(category, priority)"
              >
                <span
                  v-if="hoursFor(category.id, priority.id)"
                  class="font-medium text-slate-900"
                >
                  {{ formatHours(hoursFor(category.id, priority.id)) }}
                </span>
                <span v-else class="text-slate-500">
                  Base: {{ formatHours(priority.base_hours) || '—' }}
                </span>
              </button>
              <span :id="`cell-help-${category.id}-${priority.id}`" class="sr-only">
                Haz clic para editar el plazo de {{ category.name }} con prioridad
                {{ priority.name }}.
              </span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div
      v-if="isDirty"
      class="sticky bottom-0 mt-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-sky-200 bg-sky-50 p-3"
    >
      <p class="text-sm font-medium text-sky-900" role="status" aria-live="polite">
        Cambios sin guardar
      </p>
      <div class="flex gap-2">
        <button
          type="button"
          class="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm font-semibold text-slate-700"
          :disabled="saving"
          @click="discard"
        >
          Descartar
        </button>
        <button
          type="button"
          class="rounded-lg bg-sky-600 px-3 py-1.5 text-sm font-semibold text-white hover:bg-sky-700 disabled:opacity-60"
          :disabled="saving"
          @click="save"
        >
          {{ saving ? 'Guardando…' : 'Guardar cambios' }}
        </button>
      </div>
    </div>

    <SlaCellEditor
      v-if="editing"
      :open="true"
      :category="editing.category"
      :priority="editing.priority"
      :current-hours="editingHours()"
      :has-rule="editing.hasRule"
      @update:open="editing = null"
      @apply="applyCell"
      @cancel="editing = null"
    />
  </section>
</template>
