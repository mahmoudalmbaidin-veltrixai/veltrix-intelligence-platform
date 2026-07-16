import { defineStore } from 'pinia'
import { ref, watch } from 'vue'
import { LocalStore } from '@/shared/lib/mock'

export type ThemeMode = 'light' | 'dark' | 'system'

const store = new LocalStore<{ mode: ThemeMode }>('vip.theme')

function systemPrefersDark(): boolean {
  return typeof window !== 'undefined' && window.matchMedia?.('(prefers-color-scheme: dark)').matches
}

export const useThemeStore = defineStore('theme', () => {
  const mode = ref<ThemeMode>(store.read({ mode: 'dark' }).mode)

  function resolved(): 'light' | 'dark' {
    if (mode.value === 'system') return systemPrefersDark() ? 'dark' : 'light'
    return mode.value
  }

  function apply() {
    if (typeof document !== 'undefined') {
      document.documentElement.setAttribute('data-theme', resolved())
    }
  }

  function setMode(m: ThemeMode) {
    mode.value = m
    store.write({ mode: m })
    apply()
  }

  function cycle() {
    setMode(resolved() === 'dark' ? 'light' : 'dark')
  }

  watch(mode, apply, { immediate: true })

  if (typeof window !== 'undefined') {
    window.matchMedia?.('(prefers-color-scheme: dark)').addEventListener?.('change', () => {
      if (mode.value === 'system') apply()
    })
  }

  return { mode, resolved, setMode, cycle, apply }
})
