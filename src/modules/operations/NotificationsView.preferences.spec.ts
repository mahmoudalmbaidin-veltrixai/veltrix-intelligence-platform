import { afterEach, describe, expect, it, vi } from 'vitest'
import { ref } from 'vue'
import { mount, flushPromises } from '@vue/test-utils'

const updatePreferences = vi.hoisted(() => vi.fn())
const hydrateAuthenticatedUser = vi.hoisted(() => vi.fn())
const pushToast = vi.hoisted(() => vi.fn())
const platformUser = vi.hoisted(() => ({
  id: 'user-1',
  preferences: { notifications: { Pipelines: false, System: true } } as Record<string, unknown>,
}))

vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }) }))
vi.mock('@/shared/lib/query', () => ({
  useQuery: () => ({ data: ref([]), isLoading: ref(false) }),
}))
vi.mock('@/shared/stores/ui', () => ({ useUiStore: () => ({ pushToast, unreadNotifications: 0 }) }))
vi.mock('@/shared/stores/platform', () => ({
  usePlatformStore: () => ({ user: platformUser, hydrateAuthenticatedUser }),
}))
vi.mock('@/modules/settings/settings.service', () => ({
  settingsService: { updatePreferences },
}))
vi.mock('./operations.service', () => ({
  operationsService: {
    listNotifications: vi.fn().mockResolvedValue([]),
    markNotificationRead: vi.fn(),
    markNotificationUnread: vi.fn(),
    markAllNotificationsRead: vi.fn(),
  },
}))

import NotificationsView from './NotificationsView.vue'

// Render VipButton/VipSwitch as real interactive elements; stub everything else.
const stubs = {
  VipButton: {
    props: ['loading', 'disabled'],
    emits: ['click'],
    template: '<button :disabled="disabled" @click="$emit(\'click\')"><slot /></button>',
  },
  VipSwitch: {
    props: ['modelValue'],
    emits: ['update:modelValue'],
    template: '<button class="sw" @click="$emit(\'update:modelValue\', !modelValue)">{{ modelValue }}</button>',
  },
  VipPageHeader: true,
  VipCard: { template: '<div><slot /><slot name="actions" /></div>' },
  VipBadge: true,
  VipIcon: true,
  VipTabs: true,
  VipSegmented: true,
  VipEmptyState: true,
  VipSkeleton: true,
}

function saveButton(wrapper: ReturnType<typeof mount>) {
  return wrapper.findAll('button').find((b) => b.text().includes('Save preferences'))!
}

describe('NotificationsView preferences persistence (BUG-NOTIF-002)', () => {
  afterEach(() => {
    vi.clearAllMocks()
    platformUser.preferences = { notifications: { Pipelines: false, System: true } }
  })

  it('saves preferences through the real API and hydrates on success', async () => {
    updatePreferences.mockResolvedValue({ user: { id: 'user-1' } })
    const wrapper = mount(NotificationsView, { global: { stubs } })
    await flushPromises()

    await saveButton(wrapper).trigger('click')
    await flushPromises()

    expect(updatePreferences).toHaveBeenCalledTimes(1)
    const payload = updatePreferences.mock.calls[0][0]
    // The persisted payload namespaces under `notifications` and reflects the
    // user's loaded value (Pipelines was stored false, not the default true).
    expect(payload).toHaveProperty('notifications')
    expect(payload.notifications.Pipelines).toBe(false)
    expect(hydrateAuthenticatedUser).toHaveBeenCalled()
    expect(pushToast).toHaveBeenCalledWith(
      expect.objectContaining({ kind: 'success', title: 'Notification preferences saved' }),
    )
  })

  it('shows an error and does not claim success when the save fails', async () => {
    updatePreferences.mockRejectedValue(new Error('nope'))
    const wrapper = mount(NotificationsView, { global: { stubs } })
    await flushPromises()

    await saveButton(wrapper).trigger('click')
    await flushPromises()

    expect(pushToast).toHaveBeenCalledWith(
      expect.objectContaining({ kind: 'error', title: 'Unable to save notification preferences' }),
    )
    expect(pushToast).not.toHaveBeenCalledWith(expect.objectContaining({ title: 'Notification preferences saved' }))
  })
})
