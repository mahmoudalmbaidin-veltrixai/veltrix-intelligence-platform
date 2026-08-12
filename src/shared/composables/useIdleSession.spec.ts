import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h } from 'vue'
import { mount } from '@vue/test-utils'

const replace = vi.hoisted(() => vi.fn())
const recordActivity = vi.hoisted(() => vi.fn())
const authState = vi.hoisted(() => ({
  isAuthenticated: true,
  session: {
    expiresAt: '',
    user: {},
    idleExpiresAt: null as string | null,
    idleTimeoutMinutes: 30,
    warningMinutes: 5,
  },
  logout: vi.fn(),
}))

vi.mock('vue-router', () => ({ useRouter: () => ({ replace }) }))
vi.mock('@/shared/stores/auth', () => ({ useAuthStore: () => authState }))
vi.mock('@/modules/settings/settings.service', () => ({
  settingsService: { recordActivity },
}))

import { useIdleSession } from './useIdleSession'

let captured: ReturnType<typeof useIdleSession>
const Harness = defineComponent({
  setup() {
    captured = useIdleSession()
    return () => h('div')
  },
})

describe('useIdleSession', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-08-12T00:00:00Z'))
    replace.mockClear()
    recordActivity.mockReset()
    authState.isAuthenticated = true
    authState.logout.mockReset()
  })
  afterEach(() => {
    vi.useRealTimers()
  })

  function deadlineIn(seconds: number) {
    authState.session.idleExpiresAt = new Date(Date.now() + seconds * 1000).toISOString()
  }

  it('shows the warning inside the warning window and counts down', async () => {
    deadlineIn(4 * 60) // 4 min left, warning is 5 min → already in the window
    const wrapper = mount(Harness)
    await vi.advanceTimersByTimeAsync(1000)
    expect(captured.showWarning.value).toBe(true)
    expect(captured.secondsRemaining.value).toBeLessThanOrEqual(4 * 60)
    expect(captured.countdownLabel.value).toMatch(/^0[0-4]:\d\d$/)
    wrapper.unmount()
  })

  it('signs out and routes to login with an idle reason at the deadline', async () => {
    deadlineIn(1)
    const wrapper = mount(Harness)
    await vi.advanceTimersByTimeAsync(1500)
    expect(authState.logout).toHaveBeenCalled()
    expect(replace).toHaveBeenCalledWith({ name: 'login', query: { reason: 'idle' } })
    wrapper.unmount()
  })

  it('"Stay signed in" calls the server activity endpoint and clears the warning', async () => {
    deadlineIn(60)
    recordActivity.mockResolvedValue({
      idleExpiresAt: new Date(Date.now() + 30 * 60 * 1000).toISOString(),
    })
    const wrapper = mount(Harness)
    await vi.advanceTimersByTimeAsync(1000)
    expect(captured.showWarning.value).toBe(true)
    await captured.staySignedIn()
    expect(recordActivity).toHaveBeenCalled()
    expect(captured.showWarning.value).toBe(false)
    wrapper.unmount()
  })

  it('does not renew from a plain tick without genuine activity', async () => {
    deadlineIn(30 * 60) // far from warning
    const wrapper = mount(Harness)
    await vi.advanceTimersByTimeAsync(5000)
    // No user input dispatched → the activity endpoint is never called.
    expect(recordActivity).not.toHaveBeenCalled()
    wrapper.unmount()
  })
})
