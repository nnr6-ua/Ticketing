<script setup lang="ts">
import { computed } from "vue";
import {
  Listbox,
  ListboxButton,
  ListboxOption,
  ListboxOptions,
} from "@headlessui/vue";
import { CheckIcon, ChevronUpDownIcon } from "@heroicons/vue/20/solid";
import type { Priority } from "../types/api";

const props = withDefaults(
  defineProps<{
    modelValue: string | null;
    priorities: Priority[];
    disabled?: boolean;
    loading?: boolean;
  }>(),
  {
    disabled: false,
    loading: false,
  },
);

const emit = defineEmits<{
  "update:modelValue": [value: string | null];
}>();

const selected = computed(
  () => props.priorities.find((priority) => priority.id === props.modelValue) ?? null,
);

const displayLabel = computed(() => {
  if (selected.value) return selected.value.name;
  if (props.loading) return "Cargando prioridades…";
  return "Selecciona una prioridad";
});
</script>

<template>
  <Listbox
    as="div"
    class="relative"
    :model-value="modelValue"
    :disabled="disabled || loading"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <ListboxButton
      type="button"
      class="relative flex w-full items-center justify-between gap-2 rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-left text-sm shadow-sm transition hover:border-slate-400 disabled:cursor-not-allowed disabled:bg-slate-50 disabled:text-slate-400"
    >
      <span class="flex min-w-0 items-center gap-2">
        <span
          v-if="selected"
          class="h-2.5 w-2.5 flex-none rounded-full"
          :style="{ backgroundColor: selected.color ?? undefined }"
        />
        <span class="truncate font-medium" :class="selected ? 'text-slate-900' : 'text-slate-500'">
          {{ displayLabel }}
        </span>
      </span>
      <ChevronUpDownIcon class="h-5 w-5 flex-none text-slate-400" aria-hidden="true" />
    </ListboxButton>

    <ListboxOptions
      class="absolute z-20 mt-1 max-h-60 w-full overflow-auto rounded-xl border border-slate-200 bg-white py-1 text-sm shadow-lg focus:outline-none"
    >
      <ListboxOption
        v-for="priority in priorities"
        :key="priority.id"
        v-slot="{ active, selected: isSelected }"
        :value="priority.id"
        as="template"
      >
        <li
          class="flex cursor-pointer items-center gap-2 px-3 py-2"
          :class="active ? 'bg-sky-50 text-sky-900' : 'text-slate-700'"
        >
          <span
            class="h-2.5 w-2.5 flex-none rounded-full"
            :style="{ backgroundColor: priority.color ?? undefined }"
          />
          <span class="flex-1">{{ priority.name }}</span>
          <CheckIcon v-if="isSelected" class="h-4 w-4 text-sky-600" aria-hidden="true" />
        </li>
      </ListboxOption>
    </ListboxOptions>
  </Listbox>
</template>
