import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import VipLogo from './VipLogo.vue'

describe('VipLogo', () => {
  it('renders the mark as inline SVG (no external image request)', () => {
    const wrapper = mount(VipLogo)
    const svg = wrapper.find('svg.vip-logo__mark')
    expect(svg.exists()).toBe(true)
    // The Veltrix One badge (rounded square + "V" chevron) is inline — nothing to 404.
    expect(wrapper.find('img').exists()).toBe(false)
    expect(svg.find('rect').exists()).toBe(true)
    expect(svg.findAll('path').length).toBeGreaterThanOrEqual(1)
  })

  it('shows the Veltrix One wordmark for full/auto and hides it for icon', () => {
    expect(mount(VipLogo, { props: { variant: 'full' } }).text()).toContain('Veltrix One')
    expect(mount(VipLogo, { props: { variant: 'auto' } }).text()).toContain('Veltrix One')
    expect(
      mount(VipLogo, { props: { variant: 'icon' } })
        .find('.vip-logo__word')
        .exists(),
    ).toBe(false)
  })

  it('is a labeled image by default and decorative when asked', () => {
    const labeled = mount(VipLogo)
    expect(labeled.attributes('role')).toBe('img')
    expect(labeled.attributes('aria-label')).toBe('Veltrix One')

    const decorative = mount(VipLogo, { props: { decorative: true } })
    expect(decorative.attributes('aria-hidden')).toBe('true')
    expect(decorative.attributes('role')).toBeUndefined()
  })

  it('honors a custom accessible label', () => {
    const wrapper = mount(VipLogo, { props: { label: 'VIP home' } })
    expect(wrapper.attributes('aria-label')).toBe('VIP home')
  })

  it('renders a square, non-distorted mark sized by the size token', () => {
    const wrapper = mount(VipLogo, { props: { size: 'lg' } })
    const svg = wrapper.find('svg.vip-logo__mark')
    // lg => 44px, square (no stretching), preserving the 48x48 viewBox aspect.
    expect(svg.attributes('width')).toBe('44')
    expect(svg.attributes('height')).toBe('44')
    expect(svg.attributes('viewBox')).toBe('0 0 48 48')
    expect(svg.attributes('draggable')).toBe('false')
    expect(wrapper.classes()).toContain('vip-logo--lg')
  })

  it('supports an explicit pixel height override', () => {
    const svg = mount(VipLogo, { props: { height: 30 } }).find('svg.vip-logo__mark')
    expect(svg.attributes('height')).toBe('30')
    expect(svg.attributes('width')).toBe('30')
  })

  it('uses a flat, gradient-free mark that is safe to co-locate', () => {
    // The Veltrix One mark is flat (no <defs>/gradient ids), so multiple logos on
    // one page can never cross-reference shared definitions.
    const Host = { components: { VipLogo }, template: '<div><VipLogo /><VipLogo /></div>' }
    const wrapper = mount(Host)
    expect(wrapper.findAll('linearGradient').length).toBe(0)
    expect(wrapper.findAll('svg.vip-logo__mark').length).toBe(2)
  })
})
