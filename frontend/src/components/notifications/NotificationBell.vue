<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useRouter } from 'vue-router'
import { Bell } from 'lucide-vue-next'

import NotificationList from '@/components/notifications/NotificationList.vue'
import { useNotificationsStore } from '@/stores/notifications'
import type { Notification } from '@/types/notifications'

const store = useNotificationsStore()
const router = useRouter()
const { items, unreadCount, loading, error, open } = storeToRefs(store)

const root = ref<HTMLElement | null>(null)
const button = ref<HTMLButtonElement | null>(null)

function onDocumentClick(event: MouseEvent): void {
  if (!open.value) {
    return
  }
  const target = event.target as Node | null
  if (target && root.value && !root.value.contains(target)) {
    close()
  }
}

function onKeydown(event: KeyboardEvent): void {
  if (event.key === 'Escape' && open.value) {
    event.stopPropagation()
    close()
  }
}

function close(): void {
  store.close()
  button.value?.focus()
}

function toggle(): void {
  store.toggle()
}

async function onSelect(notification: Notification): Promise<void> {
  await store.markRead(notification.id)
  store.close()
  await router.push(`/tickets/${encodeURIComponent(notification.ticket_id)}`)
}

watch(open, (isOpen) => {
  if (isOpen) {
    document.addEventListener('click', onDocumentClick)
    document.addEventListener('keydown', onKeydown)
  } else {
    document.removeEventListener('click', onDocumentClick)
    document.removeEventListener('keydown', onKeydown)
  }
})

onBeforeUnmount(() => {
  document.removeEventListener('click', onDocumentClick)
  document.removeEventListener('keydown', onKeydown)
})
</script>

<template>
  <div ref="root" class="relative">
    <button
      ref="button"
      type="button"
      class="relative inline-flex items-center gap-2 rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-800 hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-900 focus-visible:ring-offset-2"
      :aria-expanded="open"
      aria-controls="notification-panel"
      :aria-label="`Notificaciones, ${unreadCount} sin leer`"
      @click="toggle"
    >
      <Bell aria-hidden="true" class="h-5 w-5" />
      <span class="hidden sm:inline">Notificaciones</span>
      <span
        v-if="unreadCount > 0"
        aria-live="polite"
        class="inline-flex min-w-5 items-center justify-center rounded-full bg-red-600 px-1.5 py-0.5 text-xs font-semibold text-white"
      >
        {{ unreadCount }}
      </span>
    </button>

    <div
      v-if="open"
      id="notification-panel"
      class="absolute right-0 z-20 mt-2 w-80"
    >
      <NotificationList
        :items="items"
        :loading="loading"
        :error="error"
        @select="onSelect"
        @retry="store.refresh()"
      />
    </div>
  </div>
</template>
