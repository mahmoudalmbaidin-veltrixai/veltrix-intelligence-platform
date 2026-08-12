import { defineStore } from 'pinia'
import { ref, watch } from 'vue'
import { LocalStore } from '@/shared/lib/mock'

export type ThemeMode = 'light' | 'dark' | 'system'
export type Density = 'comfortable' | 'compact'

interface AppearanceState {
  mode: ThemeMode
  density: Density
  reducedMotion: boolean
}

const store = new LocalStore<AppearanceState>('vip.theme')
const DEFAULTS: AppearanceState = { mode: 'dark', density: 'comfortable', reducedMotion: false }

function systemPrefersDark(): boolean {
  return typeof window !== 'undefined' && window.matchMedia?.('(prefers-color-scheme: dark)').matches
}

export const useThemeStore = defineStore('theme', () => {
  const persisted = store.read(DEFAULTS)
  const mode = ref<ThemeMode>(persisted.mode ?? DEFAULTS.mode)
  const density = ref<Density>(persisted.density ?? DEFAULTS.density)
  const reducedMotion = ref<boolean>(persisted.reducedMotion ?? DEFAULTS.reducedMotion)

  function resolved(): 'light' | 'dark' {
    if (mode.value === 'system') return systemPrefersDark() ? 'dark' : 'light'
    return mode.value
  }

  function apply() {
    if (typeof document === 'undefined') return
    const root = document.documentElement
    root.setAttribute('data-theme', resolved())
    root.setAttribute('data-density', density.value)
    root.toggleAttribute('data-reduced-motion', reducedMotion.value)
  }

  function persist() {
    store.write({ mode: mode.value, density: density.value, reducedMotion: reducedMotion.value })
  }

  function setMode(m: ThemeMode) {
    mode.value = m
    persist()
    apply()
  }
  function setDensity(value: Density) {
    density.value = value
    persist()
    apply()
  }
  function setReducedMotion(value: boolean) {
    reducedMotion.value = value
    persist()
    apply()
  }

  /** Apply server-stored personalization on bootstrap without echoing a save. */
  function hydrate(preferences: Record<string, unknown> | undefined): void {
    if (!preferences) return
    if (preferences.theme === 'light' || preferences.theme === 'dark' || preferences.theme === 'system') {
      mode.value = preferences.theme
    }
    if (preferences.density === 'comfortable' || preferences.density === 'compact') {
      density.value = preferences.density
    }
    if (typeof preferences.reducedMotion === 'boolean') reducedMotion.value = preferences.reducedMotion
    persist()
    apply()
  }

  function cycle() {
    setMode(resolved() === 'dark' ? 'light' : 'dark')
  }

  watch([mode, density, reducedMotion], apply, { immediate: true })

  if (typeof window !== 'undefined') {
    window.matchMedia?.('(prefers-color-scheme: dark)').addEventListener?.('change', () => {
      if (mode.value === 'system') apply()
    })
  }

  return { mode, density, reducedMotion, resolved, setMode, setDensity, setReducedMotion, hydrate, cycle, apply }
})
