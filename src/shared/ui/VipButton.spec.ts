import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import VipButton from './VipButton.vue'

describe('VipButton', () => {
  it('renders its label', () => {
    const wrapper = mount(VipButton, { slots: { default: 'Save' } })
    expect(wrapper.text()).toContain('Save')
  })

  it('emits click when enabled', async () => {
    const wrapper = mount(VipButton, { slots: { default: 'Go' } })
    await wrapper.trigger('click')
    expect(wrapper.emitted('click')).toBeTruthy()
  })

  it('does not emit click when disabled', async () => {
    const wrapper = mount(VipButton, { props: { disabled: true }, slots: { default: 'Go' } })
    await wrapper.trigger('click')
    expect(wrapper.emitted('click')).toBeFalsy()
  })

  it('does not emit click while loading', async () => {
    const wrapper = mount(VipButton, { props: { loading: true }, slots: { default: 'Go' } })
    await wrapper.trigger('click')
    expect(wrapper.emitted('click')).toBeFalsy()
  })

  it('applies the variant class', () => {
    const wrapper = mount(VipButton, { props: { variant: 'danger' }, slots: { default: 'Delete' } })
    expect(wrapper.classes()).toContain('vip-btn--danger')
  })
})
