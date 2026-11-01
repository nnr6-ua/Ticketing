<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { ApiClientError, setAccessToken } from '@/api/client'
import { devLogin } from '@/api/devAuth'

const route = useRoute()
const router = useRouter()

const DEV_USERS = [
  { email: 'tecnico.a@example.com', label: 'Técnico A · 5 activos + finalizados' },
  { email: 'tecnico.b@example.com', label: 'Técnico B · 2 activos' },
  { email: 'tecnico.c@example.com', label: 'Técnico C · solo finalizados' },
  { email: 'tecnico.d@example.com', label: 'Técnico D · cola vacía' },
  { email: 'supervisor@example.com', label: 'Supervisor · 403 en la cola' },
  { email: 'usuario@example.com', label: 'Solicitante · 403 en la cola' },
]

const email = ref(DEV_USERS[0].email)
const loading = ref(false)
const errorMessage = ref<string | null>(null)

const redirectTarget = computed(() => {
  const redirect = route.query.redirect
  if (typeof redirect === 'string' && redirect.startsWith('/') && !redirect.startsWith('//')) {
    return redirect
  }
  return '/cola-de-trabajo'
})

async function submit(): Promise<void> {
  if (loading.value) {
    return
  }
  loading.value = true
  errorMessage.value = null
  try {
    const response = await devLogin(email.value)
    setAccessToken(response.access_token)
    await router.replace(redirectTarget.value)
  } catch (caught) {
    errorMessage.value =
      caught instanceof ApiClientError
        ? caught.message
        : 'No se pudo iniciar sesión con el stub de desarrollo.'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <main class="mx-auto max-w-3xl px-4 py-16">
    <h1 class="text-2xl font-semibold text-slate-900">Inicia sesión</h1>
    <p class="mt-2 text-slate-700">
      El mecanismo de autenticación del proyecto es externo a esta historia.
    </p>
    <p class="mt-4 text-sm text-slate-600">
      Tras iniciar sesión se te redirigirá a
      <code class="rounded bg-slate-100 px-1 py-0.5">{{ redirectTarget }}</code>.
    </p>

    <section class="mt-8 rounded-lg border border-amber-300 bg-amber-50 p-6">
      <h2 class="text-lg font-semibold text-slate-900">Acceso de desarrollo</h2>
      <p class="mt-2 text-sm text-slate-700">
        Stub temporal de autenticación: genera un JWT de prueba para un usuario
        del seed y lo guarda en <code class="rounded bg-amber-100 px-1">localStorage</code>.
        No lo uses en entornos compartidos.
      </p>

      <form class="mt-4 flex flex-col gap-3 sm:flex-row sm:items-end" @submit.prevent="submit">
        <div class="flex-1">
          <label for="dev-user" class="block text-sm font-medium text-slate-800">
            Usuario del seed
          </label>
          <select
            id="dev-user"
            v-model="email"
            class="mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-slate-500 focus:outline-none focus:ring-2 focus:ring-slate-400"
            :disabled="loading"
          >
            <option v-for="user in DEV_USERS" :key="user.email" :value="user.email">
              {{ user.label }} · {{ user.email }}
            </option>
          </select>
        </div>
        <button
          type="submit"
          class="rounded-md bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-700 focus:outline-none focus:ring-2 focus:ring-slate-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60"
          :disabled="loading"
        >
          {{ loading ? 'Entrando…' : 'Entrar con token de prueba' }}
        </button>
      </form>

      <p v-if="errorMessage" class="mt-3 text-sm text-red-700" role="alert">
        {{ errorMessage }}
      </p>

      <p class="mt-3 text-xs text-slate-600">
        Si el usuario no existe, ejecuta
        <code class="rounded bg-amber-100 px-1">docker compose exec backend python scripts/seed_dev.py</code>.
      </p>
    </section>
  </main>
</template>
