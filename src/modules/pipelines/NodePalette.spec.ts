import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import NodePalette from './NodePalette.vue'

describe('NodePalette readonly', () => {
  it('blocks add events when readonly', async () => {
    const wrapper = mount(NodePalette, { props: { readonly: true } })
    const button = wrapper.find('button.palette__node')
    expect(button.exists()).toBe(true)
    expect(button.attributes('disabled')).toBeDefined()
    await button.trigger('dblclick')
    expect(wrapper.emitted('add')).toBeUndefined()
    expect(wrapper.text()).toContain('Developer access')
  })

  it('emits add when editable', async () => {
    const wrapper = mount(NodePalette, { props: { readonly: false } })
    const button = wrapper.find('button.palette__node')
    await button.trigger('dblclick')
    expect(wrapper.emitted('add')?.length).toBe(1)
  })
})
