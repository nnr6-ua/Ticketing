<script setup lang="ts">
withDefaults(defineProps<{ rows?: number }>(), { rows: 4 })
</script>

<template>
  <div
    class="overflow-hidden rounded-lg border border-slate-200 bg-white"
    role="status"
    aria-busy="true"
    aria-label="Cargando dashboard"
    data-testid="sla-dashboard-skeleton"
  >
    <div class="h-10 animate-pulse bg-slate-200" />
    <div class="space-y-3 p-4">
      <p class="text-sm text-slate-600">Cargando dashboard…</p>
      <div
        v-for="row in rows"
        :key="row"
        class="flex gap-4"
      >
        <div class="h-4 w-24 animate-pulse rounded bg-slate-200" />
        <div class="h-4 flex-1 animate-pulse rounded bg-slate-200" />
        <div class="h-4 w-20 animate-pulse rounded bg-slate-200" />
      </div>
    </div>
  </div>
</template>
