<script setup lang="ts">
// Placeholder fuera del alcance de la HU-04: solo evita un 404 cuando la cola
// enlaza a `/tickets/:id`. No implementa la vista de detalle de la HU-06.
import { useRoute } from 'vue-router'

const route = useRoute()
</script>

<template>
  <main class="mx-auto max-w-3xl px-4 py-16">
    <h1 class="text-2xl font-semibold text-slate-900">Detalle del ticket</h1>
    <p class="mt-2 text-slate-700">
      La vista de detalle pertenece a la HU-06 y queda fuera del alcance de la
      cola de trabajo.
    </p>
    <p class="mt-4 text-sm text-slate-600">Ticket: {{ route.params.id }}</p>
    <RouterLink
      to="/cola-de-trabajo"
      class="mt-6 inline-block rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700"
    >
      Volver a la cola de trabajo
    </RouterLink>
  </main>
</template>
