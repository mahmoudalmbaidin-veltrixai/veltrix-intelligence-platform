import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import { router } from './app/router'
import { useThemeStore } from './shared/stores/theme'

import './styles/tokens.css'
import './styles/base.css'

const app = createApp(App)
app.use(createPinia())

// Apply persisted theme before first paint.
useThemeStore().apply()

app.use(router)
app.mount('#app')
