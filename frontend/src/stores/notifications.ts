import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { ApiClientError, isAbortError, setAccessToken } from '@/api/client'
import {
  getNotifications,
  markNotificationRead,
} from '@/services/notifications'
import type { Notification } from '@/types/notifications'

export const POLL_INTERVAL_MS = 15_000
export const PAGE_SIZE = 20

const POLL_ERROR_MESSAGE =
  'No se pudieron cargar las notificaciones. Inténtalo de nuevo.'
const NOT_FOUND_MESSAGE = 'No se ha encontrado la notificación.'
const UNAUTHORIZED_MESSAGE = 'La sesión no es válida o ha caducado.'

function isHidden(): boolean {
  return (
    typeof document !== 'undefined' && document.visibilityState === 'hidden'
  )
}

export const useNotificationsStore = defineStore('notifications', () => {
  const items = ref<Notification[]>([])
  const unreadCount = ref(0)
  const loading = ref(false)
  const error = ref<string | null>(null)
  const open = ref(false)
  const hasMore = ref(false)

  let timer: ReturnType<typeof setInterval> | null = null
  let sequence = 0
  let inFlight: AbortController | null = null
  let lastLoadedAt = 0
  let listenersAttached = false

  function clearData(): void {
    items.value = []
    unreadCount.value = 0
    hasMore.value = false
    error.value = null
  }

  function handleUnauthorized(): void {
    clearData()
    setAccessToken(null)
    error.value = UNAUTHORIZED_MESSAGE
    stopPolling()
  }

  async function refresh(): Promise<void> {
    const current = ++sequence
    inFlight?.abort()
    const controller = new AbortController()
    inFlight = controller
    loading.value = true
    error.value = null

    try {
      const response = await getNotifications(
        { page: 1, page_size: PAGE_SIZE },
        controller.signal,
      )
      if (current !== sequence) {
        return
      }
      items.value = response.items
      unreadCount.value = response.unread_count
      hasMore.value = response.pagination.has_next
      lastLoadedAt = Date.now()
    } catch (caught) {
      if (current !== sequence || isAbortError(caught)) {
        return
      }
      if (caught instanceof ApiClientError && caught.kind === 'unauthorized') {
        handleUnauthorized()
        return
      }
      error.value =
        caught instanceof ApiClientError && caught.kind !== 'server'
          ? caught.message
          : POLL_ERROR_MESSAGE
    } finally {
      if (current === sequence) {
        loading.value = false
      }
    }
  }

  async function markRead(id: string): Promise<void> {
    const target = items.value.find((item) => item.id === id)
    const wasUnread = target ? !target.is_read : false
    try {
      const response = await markNotificationRead(id)
      const index = items.value.findIndex((item) => item.id === id)
      if (index >= 0) {
        items.value[index] = response.notification
      }
      if (response.notification.is_read && wasUnread) {
        unreadCount.value = Math.max(0, unreadCount.value - 1)
      }
    } catch (caught) {
      if (caught instanceof ApiClientError && caught.kind === 'unauthorized') {
        handleUnauthorized()
        return
      }
      if (
        caught instanceof ApiClientError &&
        caught.code === 'notification_not_found'
      ) {
        await refresh()
        error.value = NOT_FOUND_MESSAGE
        return
      }
      error.value =
        caught instanceof ApiClientError && caught.kind !== 'server'
          ? caught.message
          : POLL_ERROR_MESSAGE
    }
  }

  function toggle(): void {
    open.value = !open.value
    if (
      open.value &&
      (items.value.length === 0 || Date.now() - lastLoadedAt > POLL_INTERVAL_MS)
    ) {
      void refresh()
    }
  }

  function close(): void {
    open.value = false
  }

  function onFocus(): void {
    if (!isHidden()) {
      void refresh()
    }
  }

  function onVisibilityChange(): void {
    if (!isHidden()) {
      void refresh()
    }
  }

  function startPolling(): void {
    if (timer !== null) {
      return
    }
    timer = setInterval(() => {
      if (!isHidden()) {
        void refresh()
      }
    }, POLL_INTERVAL_MS)

    if (typeof window !== 'undefined' && !listenersAttached) {
      window.addEventListener('focus', onFocus)
      document.addEventListener('visibilitychange', onVisibilityChange)
      listenersAttached = true
    }

    void refresh()
  }

  function stopPolling(): void {
    if (timer !== null) {
      clearInterval(timer)
      timer = null
    }
    inFlight?.abort()
    inFlight = null
    if (typeof window !== 'undefined' && listenersAttached) {
      window.removeEventListener('focus', onFocus)
      document.removeEventListener('visibilitychange', onVisibilityChange)
      listenersAttached = false
    }
  }

  function reset(): void {
    stopPolling()
    open.value = false
    loading.value = false
    clearData()
  }

  const hasUnread = computed(() => unreadCount.value > 0)

  return {
    items,
    unreadCount,
    hasUnread,
    loading,
    error,
    open,
    hasMore,
    refresh,
    markRead,
    toggle,
    close,
    startPolling,
    stopPolling,
    reset,
  }
})
