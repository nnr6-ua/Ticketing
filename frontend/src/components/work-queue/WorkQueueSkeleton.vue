<script setup lang="ts">
withDefaults(defineProps<{ rows?: number }>(), { rows: 5 })
</script>

<template>
  <div
    class="overflow-hidden rounded-lg border border-slate-200 bg-white"
    role="status"
    aria-label="Cargando cola de trabajo"
    data-testid="work-queue-skeleton"
  >
    <div class="h-10 animate-pulse bg-slate-200" />
    <div
      v-for="row in rows"
      :key="row"
      class="flex gap-4 border-b border-slate-100 px-4 py-4"
    >
      <div class="h-4 w-24 animate-pulse rounded bg-slate-200" />
      <div class="h-4 flex-1 animate-pulse rounded bg-slate-200" />
      <div class="h-4 w-20 animate-pulse rounded bg-slate-200" />
      <div class="h-4 w-28 animate-pulse rounded bg-slate-200" />
    </div>
  </div>
</template>
