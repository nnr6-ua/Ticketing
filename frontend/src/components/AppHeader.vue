<script setup lang="ts">
import { LifebuoyIcon } from "@heroicons/vue/24/outline";
</script>

<template>
  <header class="border-b border-slate-200 bg-white">
    <div class="mx-auto flex max-w-3xl items-center justify-between px-4 py-4 sm:px-6">
      <div class="flex items-center gap-3">
        <div class="grid h-10 w-10 place-items-center rounded-xl bg-sky-600 text-white shadow-sm">
          <LifebuoyIcon class="h-6 w-6" aria-hidden="true" />
        </div>
        <div>
          <p class="text-sm font-semibold text-slate-900">Mesa de ayuda</p>
          <p class="text-xs text-slate-500">Soporte interno</p>
        </div>
      </div>

      <div class="flex items-center gap-3">
        <div class="hidden text-right sm:block">
          <p class="text-sm font-medium text-slate-900">Empleado Demo</p>
          <p class="text-xs text-slate-500">Sesión de desarrollo</p>
        </div>
        <div class="grid h-9 w-9 place-items-center rounded-full bg-slate-200 text-sm font-semibold text-slate-700">
          ED
        </div>
      </div>
    </div>
  </header>
</template>
