import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import VipMenu from './VipMenu.vue'

// The panel is teleported to <body>; stub teleport so it stays inline for querying.
const items = [
  { key: 'rename', label: 'Rename', icon: 'edit' },
  { key: 'divider', label: '', divider: true },
  { key: 'delete', label: 'Delete', icon: 'trash', danger: true },
  { key: 'export', label: 'Export', disabled: true },
]

const mountMenu = () =>
  mount(VipMenu, {
    props: { items, label: 'Actions' },
    attachTo: document.body,
    global: { stubs: { teleport: true } },
  })

describe('VipMenu', () => {
  it('is closed initially and opens on trigger click', async () => {
    const w = mountMenu()
    expect(w.find('.vip-menu__panel').exists()).toBe(false)
    await w.find('.vip-menu__trigger').trigger('click')
    expect(w.find('.vip-menu__panel').exists()).toBe(true)
  })

  it('renders items, dividers and the destructive Delete action', async () => {
    const w = mountMenu()
    await w.find('.vip-menu__trigger').trigger('click')
    const labels = w.findAll('.vip-menu__item').map((b) => b.text())
    expect(labels).toContain('Rename')
    expect(labels).toContain('Delete')
    expect(w.find('.vip-menu__item.is-danger').text()).toBe('Delete')
    expect(w.find('.vip-menu__divider').exists()).toBe(true)
  })

  it('emits select with the item key and closes', async () => {
    const w = mountMenu()
    await w.find('.vip-menu__trigger').trigger('click')
    const del = w.findAll('.vip-menu__item').find((b) => b.text() === 'Delete')!
    await del.trigger('click')
    expect(w.emitted('select')?.[0]).toEqual(['delete'])
    expect(w.find('.vip-menu__panel').exists()).toBe(false)
  })

  it('does not emit for a disabled item', async () => {
    const w = mountMenu()
    await w.find('.vip-menu__trigger').trigger('click')
    const disabled = w.findAll('.vip-menu__item').find((b) => b.text() === 'Export')!
    expect(disabled.attributes('disabled')).toBeDefined()
    await disabled.trigger('click')
    expect(w.emitted('select')).toBeFalsy()
  })

  it('closes on Escape', async () => {
    const w = mountMenu()
    await w.find('.vip-menu__trigger').trigger('click')
    expect(w.find('.vip-menu__panel').exists()).toBe(true)
    await w.find('.vip-menu__panel').trigger('keydown', { key: 'Escape' })
    expect(w.find('.vip-menu__panel').exists()).toBe(false)
  })
})
