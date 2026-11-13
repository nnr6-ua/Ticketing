<script setup lang="ts">
import { ExclamationTriangleIcon } from "@heroicons/vue/20/solid";

defineProps<{ message: string | null }>();
</script>

<template>
  <div
    v-if="message"
    role="alert"
    class="flex items-start gap-3 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800"
  >
    <ExclamationTriangleIcon class="mt-0.5 h-5 w-5 flex-none" aria-hidden="true" />
    <p>{{ message }}</p>
  </div>
</template>
