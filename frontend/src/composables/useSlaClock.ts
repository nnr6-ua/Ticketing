import {
  computed,
  getCurrentInstance,
  onMounted,
  onUnmounted,
  ref,
} from 'vue'

/**
 * Reloj local monotónico para actualizar las cuentas atrás entre polls.
 *
 * No compara `new Date()` con el deadline: parte de `remaining_seconds` del
 * servidor y avanza con `performance.now()`. Se resincroniza con cada
 * respuesta nueva (`resync`).
 */
export function useSlaClock(intervalMs = 30_000) {
  const baseNow = ref(Date.now())
  const anchor = ref(performance.now())
  const tick = ref(0)
  let timer: ReturnType<typeof setInterval> | null = null

  const now = computed(() => {
    // `tick` es la dependencia reactiva que fuerza el recálculo.
    void tick.value
    return baseNow.value + Math.floor(performance.now() - anchor.value)
  })

  function resync(): void {
    baseNow.value = Date.now()
    anchor.value = performance.now()
    tick.value += 1
  }

  function start(): void {
    if (timer !== null) {
      return
    }
    timer = setInterval(resync, intervalMs)
  }

  function stop(): void {
    if (timer !== null) {
      clearInterval(timer)
      timer = null
    }
  }

  if (getCurrentInstance()) {
    onMounted(start)
    onUnmounted(stop)
  }

  return { now, resync, start, stop }
}
