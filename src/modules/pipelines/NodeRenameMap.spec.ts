import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import NodeRenameMap from './NodeRenameMap.vue'
import type { SchemaColumn } from '@/shared/types/pipeline'

const available: SchemaColumn[] = [
  { name: 'id', dataType: 'integer' },
  { name: 'name', dataType: 'string' },
  { name: 'email', dataType: 'string' },
]

function mountMap(modelValue: Record<string, string> = {}) {
  return mount(NodeRenameMap, { props: { available, modelValue } })
}

describe('NodeRenameMap', () => {
  it('offers every upstream column as a rename source', () => {
    const w = mountMap()
    const options = w.findAll('.rn__select option').map((o) => o.text())
    expect(options).toEqual(expect.arrayContaining(['id', 'name', 'email']))
  })

  it('hydrates existing rename mappings from the persisted value', () => {
    const w = mountMap({ name: 'full_name' })
    expect((w.find('.rn__select').element as HTMLSelectElement).value).toBe('name')
    expect((w.find('.rn__input').element as HTMLInputElement).value).toBe('full_name')
  })

  it('emits a current->new map on valid input', async () => {
    const w = mountMap()
    await w.find('.rn__select').setValue('name')
    const input = w.find('.rn__input')
    await input.setValue('full_name')
    await input.trigger('input')
    expect(w.emitted('update:modelValue')!.at(-1)![0]).toEqual({ name: 'full_name' })
  })

  it('rejects an invalid name and does not emit it', async () => {
    const w = mountMap()
    await w.find('.rn__select').setValue('name')
    const input = w.find('.rn__input')
    await input.setValue('bad name!') // space + punctuation
    await input.trigger('input')
    expect(w.find('.rn__err').exists()).toBe(true)
  })

  it('renders a live output-schema preview', () => {
    const w = mountMap({ email: 'email_address' })
    const preview = w.find('.rn__preview').text()
    expect(preview).toContain('email')
    expect(preview).toContain('email_address')
  })
})
