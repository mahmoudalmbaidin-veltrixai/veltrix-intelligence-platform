/** Global UI state: sidebar, command palette, notification count, toasts. */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { LocalStore } from '@/shared/lib/mock'

export interface Toast {
  id: string
  kind: 'success' | 'error' | 'warning' | 'info'
  title: string
  message?: string
  correlationId?: string
}

const sidebarStore = new LocalStore<{ collapsed: boolean }>('vip.ui.sidebar')

export const useUiStore = defineStore('ui', () => {
  const sidebarCollapsed = ref(sidebarStore.read({ collapsed: false }).collapsed)
  const mobileNavOpen = ref(false)
  const commandOpen = ref(false)
  const notificationDrawerOpen = ref(false)
  const unreadNotifications = ref(4)
  const toasts = ref<Toast[]>([])

  function toggleSidebar() {
    sidebarCollapsed.value = !sidebarCollapsed.value
    sidebarStore.write({ collapsed: sidebarCollapsed.value })
  }

  function openCommand() {
    commandOpen.value = true
  }
  function closeCommand() {
    commandOpen.value = false
  }

  function pushToast(t: Omit<Toast, 'id'>) {
    const id = crypto.randomUUID()
    toasts.value.push({ ...t, id })
    setTimeout(() => dismissToast(id), 5200)
    return id
  }
  function dismissToast(id: string) {
    toasts.value = toasts.value.filter((t) => t.id !== id)
  }

  return {
    sidebarCollapsed, mobileNavOpen, commandOpen, notificationDrawerOpen,
    unreadNotifications, toasts,
    toggleSidebar, openCommand, closeCommand, pushToast, dismissToast,
  }
})
