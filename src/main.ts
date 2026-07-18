import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import { router } from './app/router'
import { useThemeStore } from './shared/stores/theme'
import { usePlatformStore } from './shared/stores/platform'
import { useAuthStore } from './shared/stores/auth'
import { setRequestContextProvider, setUnauthorizedHandler, cancelAllRequests } from './shared/lib/apiClient'

import './styles/tokens.css'
import './styles/base.css'

const app = createApp(App)
app.use(createPinia())

// Apply persisted theme before first paint.
useThemeStore().apply()

// Wire the centralized API client to the app's live context + 401 handling.
const platform = usePlatformStore()
const auth = useAuthStore()
setRequestContextProvider(() => ({
  token: auth.session?.token,
  orgId: platform.organization?.id,
  workspaceId: platform.workspace?.id,
  locale: platform.user?.locale,
  timezone: platform.user?.timezone,
}))
// On a 401: cancel in-flight requests, clear session/context, and route to
// login preserving the destination (QA VIP-FE-H002).
setUnauthorizedHandler(() => {
  cancelAllRequests()
  auth.onUnauthorized()
  const current = router.currentRoute.value
  if (current.meta.requiresAuth && current.name !== 'login') {
    auth.setIntended(current.fullPath)
    router.replace({ name: 'login', query: { expired: '1' } })
  }
})

// Restore the session before mounting so guards see a settled auth state.
auth.bootstrap().finally(() => {
  app.use(router)
  app.mount('#app')
})
