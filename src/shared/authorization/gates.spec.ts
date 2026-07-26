import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { mount } from '@vue/test-utils'
import PermissionGate from './PermissionGate.vue'
import FeatureGate from './FeatureGate.vue'
import EntitlementGate from './EntitlementGate.vue'
import QuotaGate from './QuotaGate.vue'
import { useAuthorizationStore } from '@/shared/stores/authorization'

describe('governance gates', () => {
  beforeEach(() => setActivePinia(createPinia()))

  function hydrate(): void {
    useAuthorizationStore().$patch({
      context: {
        user_id: 'user',
        organization_id: 'organization',
        workspace_id: 'workspace',
        organization_role: 'organization_member',
        workspace_role: 'editor',
        permissions: ['dashboard.create'],
        features: { dashboard_studio: true },
        entitlements: ['dashboard_studio'],
        quotas: {
          'dashboards.max': { key: 'dashboards.max', limit: 3, used: 2, remaining: 1, hard: true },
        },
      },
      status: 'ready',
    })
  }

  it.each([
    [PermissionGate, { permission: 'dashboard.create' }],
    [FeatureGate, { feature: 'dashboard_studio' }],
    [EntitlementGate, { entitlement: 'dashboard_studio' }],
    [QuotaGate, { quota: 'dashboards.max' }],
  ])('renders authorized content', (component, props) => {
    hydrate()
    const wrapper = mount(component, { props, slots: { default: '<span>allowed</span>' } })
    expect(wrapper.text()).toBe('allowed')
  })

  it('renders fallback content when denied', () => {
    hydrate()
    const wrapper = mount(PermissionGate, {
      props: { permission: 'dashboard.delete' },
      slots: { default: 'allowed', fallback: 'denied' },
    })
    expect(wrapper.text()).toBe('denied')
  })
})
