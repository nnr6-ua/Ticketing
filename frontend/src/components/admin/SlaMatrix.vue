<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import * as vueRouter from 'vue-router'

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
  cellErrors?: Record<string, string>
}>()

const emit = defineEmits<{
  (event: 'save', changes: SlaChange[]): void
  (event: 'retire', ruleId: string): void
  (event: 'reload'): void
}>()

const draft = ref<Record<string, string | null>>({})
const baseline = ref<Record<string, string | null>>({})
const editing = ref<{
  category: CategoryRef
  priority: PriorityRef
  hasRule: boolean
} | null>(null)

const categories = computed(() => props.matrix?.combinations.categories ?? [])
const priorities = computed(() => props.matrix?.combinations.priorities ?? [])

const inactiveRules = computed(() => {
  const activeCategories = new Set(categories.value.map((category) => category.id))
  const activePriorities = new Set(priorities.value.map((priority) => priority.id))
  return (props.matrix?.items ?? []).filter(
    (rule) =>
      rule.category.is_active === false ||
      rule.priority.is_active === false ||
      !activeCategories.has(rule.category.id) ||
      !activePriorities.has(rule.priority.id),
  )
})

watch(
  () => props.matrix,
  (matrix) => {
    const nextBaseline: Record<string, string | null> = {}
    for (const item of matrix?.items ?? []) {
      nextBaseline[key(item.category.id, item.priority.id)] = item.hours
    }
    baseline.value = nextBaseline
    draft.value = {}
    editing.value = null
  },
  { immediate: true },
)

const hoursFormatter = new Intl.NumberFormat('es-ES', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})

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

function errorFor(categoryId: string, priorityId: string): string | null {
  return props.cellErrors?.[key(categoryId, priorityId)] ?? null
}

function isInactive(category: CategoryRef, priority: PriorityRef): boolean {
  return category.is_active === false || priority.is_active === false
}

function inactiveLabel(category: CategoryRef, priority: PriorityRef): string {
  if (category.is_active === false && priority.is_active === false) {
    return 'Categoría y prioridad inactivas'
  }
  return category.is_active === false ? 'Categoría inactiva' : 'Prioridad inactiva'
}

function formatHours(value: string | null): string {
  if (value === null) return ''
  const number = Number(value)
  if (!Number.isFinite(number)) return `${value} h`
  return `${hoursFormatter.format(number)} h`
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

const isDirty = computed(() => {
  const cells = new Set([...Object.keys(baseline.value), ...Object.keys(draft.value)])
  return [...cells].some((cell) => {
    const current = Object.prototype.hasOwnProperty.call(draft.value, cell)
      ? draft.value[cell]
      : (baseline.value[cell] ?? null)
    return current !== (baseline.value[cell] ?? null)
  })
})

const UNSAVED_CHANGES_MESSAGE =
  'Tienes cambios sin guardar en la matriz SLA. ¿Salir de todos modos?'

function confirmLeave(): boolean {
  return !isDirty.value || window.confirm(UNSAVED_CHANGES_MESSAGE)
}

function warnBeforeUnload(event: BeforeUnloadEvent): void {
  if (!isDirty.value) return
  event.preventDefault()
  event.returnValue = ''
}

vueRouter.onBeforeRouteLeave?.(() => confirmLeave())
onMounted(() => window.addEventListener('beforeunload', warnBeforeUnload))
onUnmounted(() => window.removeEventListener('beforeunload', warnBeforeUnload))

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
                class="w-full rounded-lg border px-3 py-2 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 disabled:cursor-not-allowed"
                :class="
                  errorFor(category.id, priority.id)
                    ? 'border-rose-400 bg-rose-50 text-slate-900'
                    : isInactive(category, priority)
                      ? 'border-slate-200 bg-slate-50 text-slate-400'
                      : 'border-slate-200 text-slate-900 hover:border-sky-400 hover:bg-sky-50'
                "
                :aria-label="`Plazo para ${category.name} y ${priority.name}`"
                :aria-describedby="
                  errorFor(category.id, priority.id)
                    ? `cell-help-${category.id}-${priority.id} cell-error-${category.id}-${priority.id}`
                    : `cell-help-${category.id}-${priority.id}`
                "
                :disabled="saving || isInactive(category, priority)"
                @click="openEditor(category, priority)"
              >
                <span
                  v-if="hoursFor(category.id, priority.id)"
                  class="inline-flex items-center gap-2"
                  :class="isInactive(category, priority) ? 'text-slate-400' : 'font-medium text-slate-900'"
                >
                  <span
                    v-if="priority.color"
                    class="h-2.5 w-2.5 rounded-full"
                    :style="{ backgroundColor: priority.color }"
                    aria-hidden="true"
                  />
                  {{ formatHours(hoursFor(category.id, priority.id)) }}
                </span>
                <span
                  v-else
                  :class="isInactive(category, priority) ? 'text-slate-400' : 'text-slate-500'"
                >
                  Base: {{ formatHours(priority.base_hours) || '—' }}
                </span>
                <span
                  v-if="isInactive(category, priority)"
                  class="mt-1 block text-xs text-slate-400"
                >
                  {{ inactiveLabel(category, priority) }}
                </span>
              </button>
              <span :id="`cell-help-${category.id}-${priority.id}`" class="sr-only">
                <template v-if="isInactive(category, priority)">
                  Esta combinación usa el plazo base y no es editable.
                </template>
                <template v-else>
                  Haz clic para editar el plazo de {{ category.name }} con prioridad
                  {{ priority.name }}.
                </template>
              </span>
              <span
                v-if="errorFor(category.id, priority.id)"
                :id="`cell-error-${category.id}-${priority.id}`"
                class="mt-1 block text-xs text-rose-700"
                role="alert"
              >
                {{ errorFor(category.id, priority.id) }}
              </span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div
      v-if="inactiveRules.length > 0"
      class="mt-4 rounded-xl border border-slate-200 bg-slate-50 p-3"
    >
      <h3 class="text-sm font-semibold text-slate-900">
        Reglas de combinaciones inactivas
      </h3>
      <p class="mt-1 text-xs text-slate-600">
        Estas reglas siguen vigentes, pero no se pueden editar desde la matriz.
      </p>
      <ul class="mt-3 space-y-2">
        <li
          v-for="rule in inactiveRules"
          :key="rule.id"
          class="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm"
        >
          <span class="text-slate-700">
            {{ rule.category.name }} × {{ rule.priority.name }}:
            <strong class="font-semibold text-slate-900">{{ formatHours(rule.hours) }}</strong>
          </span>
          <button
            type="button"
            class="rounded-lg border border-red-300 bg-white px-3 py-1.5 text-sm font-semibold text-red-700 hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-60"
            :aria-label="`Retirar regla de ${rule.category.name} y ${rule.priority.name}`"
            :disabled="saving"
            @click="emit('retire', rule.id)"
          >
            Retirar regla
          </button>
        </li>
      </ul>
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
