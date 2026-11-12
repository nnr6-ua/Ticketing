<script setup lang="ts">
import { LockClosedIcon, SparklesIcon } from "@heroicons/vue/20/solid";
import type { Priority, SuggestionResponse } from "../types/api";
import PrioritySelect from "./PrioritySelect.vue";

defineProps<{
  suggestion: SuggestionResponse | null;
  loading: boolean;
  error: string | null;
  priorities: Priority[];
  priorityId: string | null;
}>();

const emit = defineEmits<{
  "update:priority-id": [value: string | null];
}>();
</script>

<template>
  <section
    class="rounded-2xl border border-slate-200 bg-slate-50/70 p-5"
    aria-live="polite"
  >
    <div class="flex items-center justify-between gap-3">
      <div class="flex items-center gap-2">
        <SparklesIcon class="h-5 w-5 text-sky-600" aria-hidden="true" />
        <h2 class="text-sm font-semibold text-slate-900">Sugerencia automática</h2>
      </div>
      <span v-if="loading" class="text-xs text-slate-500">Calculando…</span>
    </div>

    <p class="mt-1 text-xs text-slate-500">
      La categoría se asigna automáticamente a partir del título y la descripción.
    </p>

    <div class="mt-4 grid gap-4 sm:grid-cols-2">
      <div>
        <p class="text-xs font-medium uppercase tracking-wide text-slate-500">Categoría</p>
        <div class="mt-1 flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2.5">
          <LockClosedIcon class="h-4 w-4 flex-none text-slate-400" aria-hidden="true" />
          <span class="truncate text-sm font-medium text-slate-900">
            {{ suggestion?.category.name ?? (loading ? "Calculando…" : "Pendiente") }}
          </span>
        </div>
        <p v-if="suggestion?.category_is_fallback" class="mt-1 text-xs text-amber-700">
          Se usará la categoría por defecto.
        </p>
      </div>

      <div>
        <label class="text-xs font-medium uppercase tracking-wide text-slate-500">
          Prioridad
        </label>
        <div class="mt-1">
          <PrioritySelect
            :model-value="priorityId"
            :priorities="priorities"
            :loading="loading && priorities.length === 0"
            @update:model-value="emit('update:priority-id', $event)"
          />
        </div>
        <p v-if="suggestion?.priority_is_fallback" class="mt-1 text-xs text-amber-700">
          Prioridad por defecto; puedes cambiarla.
        </p>
      </div>
    </div>

    <p v-if="error" class="mt-3 text-xs text-amber-700">{{ error }}</p>
  </section>
</template>
