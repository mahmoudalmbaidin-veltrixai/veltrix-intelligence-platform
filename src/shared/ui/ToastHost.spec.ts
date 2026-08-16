import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

// Spy the authoritative announcer so we can assert it is the SINGLE path.
const announce = vi.hoisted(() => vi.fn())
vi.mock('@/shared/composables/useAnnouncer', () => ({
  announce,
  useAnnouncerState: () => ({ politeMessage: { value: '' }, assertiveMessage: { value: '' } }),
}))

import { useUiStore } from '@/shared/stores/ui'
import ToastHost from './ToastHost.vue'

const stubs = { teleport: true, VipIcon: true }

describe('Toast accessibility (CERT-P2-004)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    announce.mockClear()
    vi.useFakeTimers()
  })
  afterEach(() => vi.useRealTimers())

  it('Test 1 — success toast: one visible toast and exactly one announcement', () => {
    const ui = useUiStore()
    ui.pushToast({ kind: 'success', title: 'Dataset saved', message: 'Your changes were saved successfully.' })
    expect(ui.toasts).toHaveLength(1)
    expect(announce).toHaveBeenCalledTimes(1)
    expect(announce).toHaveBeenCalledWith('Dataset saved. Your changes were saved successfully.', 'polite')
  })

  it('Test 2 — error toast is announced assertively; warning assertive, info polite', () => {
    const ui = useUiStore()
    ui.pushToast({ kind: 'error', title: 'Save failed', message: 'Try again.' })
    expect(announce).toHaveBeenNthCalledWith(1, 'Save failed. Try again.', 'assertive')
    ui.pushToast({ kind: 'warning', title: 'Heads up' })
    ui.pushToast({ kind: 'info', title: 'FYI' })
    expect(announce).toHaveBeenNthCalledWith(2, 'Heads up', 'assertive')
    expect(announce).toHaveBeenNthCalledWith(3, 'FYI', 'polite')
  })

  it('Test 3 — title + description composed once, title not repeated', () => {
    const ui = useUiStore()
    ui.pushToast({ kind: 'success', title: 'Dataset saved', message: 'Saved.' })
    const msg = announce.mock.calls[0][0] as string
    expect(msg).toBe('Dataset saved. Saved.')
    expect(msg.match(/Dataset saved/g)).toHaveLength(1)
  })

  it('Test 4 — two distinct toasts are each represented and announced once', () => {
    const ui = useUiStore()
    ui.pushToast({ kind: 'success', title: 'Dataset saved' })
    ui.pushToast({ kind: 'success', title: 'Dashboard published' })
    expect(ui.toasts).toHaveLength(2)
    expect(announce).toHaveBeenCalledTimes(2)
    expect(announce).toHaveBeenNthCalledWith(1, 'Dataset saved', 'polite')
    expect(announce).toHaveBeenNthCalledWith(2, 'Dashboard published', 'polite')
  })

  it('Test 5 — manual dismiss and timeout dismissal do not re-announce', () => {
    const ui = useUiStore()
    const id = ui.pushToast({ kind: 'success', title: 'Dataset saved' })
    expect(announce).toHaveBeenCalledTimes(1)
    ui.dismissToast(id)
    expect(ui.toasts).toHaveLength(0)
    expect(announce).toHaveBeenCalledTimes(1)

    ui.pushToast({ kind: 'success', title: 'Dashboard published' })
    expect(announce).toHaveBeenCalledTimes(2)
    vi.advanceTimersByTime(6000) // auto-dismiss timeout fires
    expect(ui.toasts).toHaveLength(0)
    expect(announce).toHaveBeenCalledTimes(2)
  })

  it('ToastHost is a landmark region, NOT a second aria-live region', () => {
    const ui = useUiStore()
    ui.pushToast({ kind: 'success', title: 'Dataset saved', message: 'ok' })
    const w = mount(ToastHost, { global: { stubs } })
    const region = w.find('.vip-toasts')
    expect(region.attributes('role')).toBe('region')
    expect(region.attributes('aria-label')).toBe('Notifications')
    expect(region.attributes('aria-live')).toBeUndefined() // the fix — no duplicate live region
    expect(w.findAll('.vip-toast')).toHaveLength(1) // shown exactly once
  })

  it('Test 6 — showing a toast does not steal keyboard focus', () => {
    const btn = document.createElement('button')
    document.body.appendChild(btn)
    btn.focus()
    expect(document.activeElement).toBe(btn)

    const ui = useUiStore()
    ui.pushToast({ kind: 'success', title: 'Dataset saved' })
    const w = mount(ToastHost, { attachTo: document.body, global: { stubs } })
    expect(document.activeElement).toBe(btn)

    w.unmount()
    btn.remove()
  })
})
