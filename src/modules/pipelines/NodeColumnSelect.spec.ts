import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import NodeColumnSelect from './NodeColumnSelect.vue'
import type { SchemaColumn } from '@/shared/types/pipeline'

const available: SchemaColumn[] = [
  { name: 'id', dataType: 'integer' },
  { name: 'name', dataType: 'string' },
  { name: 'email', dataType: 'string' },
]

function mountPicker(modelValue: string[] = []) {
  return mount(NodeColumnSelect, { props: { available, modelValue } })
}

describe('NodeColumnSelect', () => {
  it('renders every upstream column with its type', () => {
    const w = mountPicker(['id'])
    const text = w.text()
    expect(text).toContain('id')
    expect(text).toContain('name')
    expect(text).toContain('email')
    expect(w.findAll('input[type="checkbox"]')).toHaveLength(3)
  })

  it('emits the kept list in upstream order when toggling', async () => {
    const w = mountPicker(['id'])
    const boxes = w.findAll('input[type="checkbox"]')
    await boxes[2].trigger('change') // toggle "email" on
    const emitted = w.emitted('update:modelValue')!.at(-1)![0]
    expect(emitted).toEqual(['id', 'email']) // preserves upstream order
  })

  it('supports select all, clear, and invert', async () => {
    const w = mountPicker(['id'])
    const [selectAll, clear, invert] = w.findAll('.cols__actions button')
    await selectAll.trigger('click')
    expect(w.emitted('update:modelValue')!.at(-1)![0]).toEqual(['id', 'name', 'email'])
    await clear.trigger('click')
    expect(w.emitted('update:modelValue')!.at(-1)![0]).toEqual([])
    // invert of {id} -> {name, email}
    await invert.trigger('click')
    expect(w.emitted('update:modelValue')!.at(-1)![0]).toEqual(['name', 'email'])
  })

  it('warns when zero columns are kept', () => {
    const w = mountPicker([])
    expect(w.find('.cols__warn').exists()).toBe(true)
  })

  it('flags stale selections that no longer exist upstream', () => {
    const w = mountPicker(['id', 'ghost_column'])
    expect(w.text()).toContain('ghost_column')
    expect(w.find('.cols__warn').exists()).toBe(true)
  })

  it('prompts to connect an upstream node when no columns are available', () => {
    const w = mount(NodeColumnSelect, { props: { available: [], modelValue: [] } })
    expect(w.find('.cols__empty').exists()).toBe(true)
  })
})
