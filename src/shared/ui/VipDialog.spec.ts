import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import VipDialog from './VipDialog.vue'

describe('VipDialog accessibility', () => {
  it('renders dialog semantics when open', async () => {
    const wrapper = mount(VipDialog, {
      props: { open: true, title: 'Confirm action' },
      slots: { default: '<p>Body</p>' },
      attachTo: document.body,
    })
    await wrapper.vm.$nextTick()
    const dialog = document.querySelector('[role="dialog"]')
    expect(dialog).not.toBeNull()
    expect(dialog?.getAttribute('aria-modal')).toBe('true')
    expect(dialog?.getAttribute('aria-label')).toBe('Confirm action')
    wrapper.unmount()
  })

  it('emits close when the close button is activated', async () => {
    const wrapper = mount(VipDialog, {
      props: { open: true, title: 'T', closable: true },
      attachTo: document.body,
    })
    await wrapper.vm.$nextTick()
    const closeBtn = document.querySelector('.vip-dialog__close') as HTMLButtonElement
    closeBtn?.click()
    expect(wrapper.emitted('close')).toBeTruthy()
    wrapper.unmount()
  })

  it('does not render content when closed', () => {
    mount(VipDialog, { props: { open: false, title: 'T' }, attachTo: document.body })
    expect(document.querySelector('[role="dialog"]')).toBeNull()
  })
})
