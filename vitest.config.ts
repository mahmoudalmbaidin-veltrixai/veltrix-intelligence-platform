import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    include: ['src/**/*.{test,spec}.ts'],
    css: false,
    // Unit tests must be hermetic even when a developer has copied the
    // production-oriented .env.example to .env.
    env: {
      VITE_APP_ENV: 'development',
      VITE_API_MODE: 'mock',
      VITE_API_BASE_URL: '',
      VITE_ENABLE_MOCK_LATENCY: 'false',
    },
    // Keep process pressure predictable on Windows workstations and small CI
    // runners while retaining file-level parallelism.
    minWorkers: 1,
    maxWorkers: 4,
  },
})
