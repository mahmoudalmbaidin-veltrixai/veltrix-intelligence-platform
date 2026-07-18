/// <reference types="vite/client" />

declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<Record<string, unknown>, Record<string, unknown>, unknown>
  export default component
}

interface ImportMetaEnv {
  readonly VITE_API_MODE?: 'mock' | 'live'
  readonly VITE_API_BASE_URL?: string
  readonly VITE_API_TIMEOUT_MS?: string
  readonly VITE_APP_ENV?: 'development' | 'staging' | 'production'
  readonly VITE_ENABLE_DEVTOOLS?: string
  readonly VITE_ENABLE_MOCK_LATENCY?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
