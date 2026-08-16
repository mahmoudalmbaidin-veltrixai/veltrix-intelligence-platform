import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import type { Dashboard } from '@/shared/types/dashboard'
import type { QueryFilter, SemanticModel } from '@/shared/types/semantic'
import DashboardFilterBar from './DashboardFilterBar.vue'

const model: SemanticModel = {
  id: 'm',
  name: 'm',
  label: 'M',
  description: '',
  entities: [],
  fields: [
    { id: 'category', name: 'category', label: 'Category', role: 'dimension', dataType: 'string' },
    { id: 'order_date', name: 'order_date', label: 'Order Date', role: 'time', dataType: 'date' },
  ],
  freshness: '2026-08-10T00:00:00Z',
  owner: 'QA',
  certified: true,
}

const stubs = {
  VipMenu: {
    props: ['items'],
    emits: ['select'],
    template:
      '<div><button v-for="i in items" :key="i.key" class="menu-item" type="button" @click="$emit(\'select\', i.key)">{{ i.label }}</button></div>',
  },
  VipButton: {
    props: ['disabled'],
    emits: ['click'],
    template: '<button :disabled="disabled" @click="$emit(\'click\')"><slot /></button>',
  },
  VipIcon: true,
}

function mountBar(filters: QueryFilter[] = []) {
  return mount(DashboardFilterBar, {
    props: {
      dashboard: { name: 'D' } as Dashboard,
      crossFilters: [],
      models: [model],
      modelId: 'm',
      filters,
    },
    global: { stubs },
  })
}
const lastEmitted = (w: ReturnType<typeof mountBar>) => {
  const events = w.emitted('update:filters')
  return (events?.at(-1)?.[0] ?? []) as QueryFilter[]
}
const addField = (w: ReturnType<typeof mountBar>, label: string) =>
  w
    .findAll('.menu-item')
    .find((b) => b.text() === label)!
    .trigger('click')
const clickText = (w: ReturnType<typeof mountBar>, text: string) =>
  w
    .findAll('button')
    .find((b) => b.text() === text)!
    .trigger('click')

describe('DashboardFilterBar operator authoring (DASH-P2-FILTER-OPERATORS)', () => {
  it('offers field-type-aware operators', async () => {
    const w = mountBar()
    await addField(w, 'Category')
    expect(w.findAll('.fbar__op option').map((o) => o.text())).toEqual(['Equals', 'Is one of'])
    await clickText(w, 'Cancel')
    await addField(w, 'Order Date')
    expect(w.findAll('.fbar__op option').map((o) => o.text())).toEqual(['Equals', 'Between'])
  })

  it('authors an eq filter', async () => {
    const w = mountBar()
    await addField(w, 'Category')
    await w.find('.fbar__input').setValue('Electronics')
    await w.find('form.fbar__value').trigger('submit')
    expect(lastEmitted(w)).toEqual([
      expect.objectContaining({ fieldId: 'category', operator: 'eq', value: 'Electronics' }),
    ])
  })

  it('authors an in filter with multiple values', async () => {
    const w = mountBar()
    await addField(w, 'Category')
    await w.find('.fbar__op').setValue('in')
    await w.find('.fbar__input').setValue('Electronics')
    await clickText(w, 'Add')
    await w.find('.fbar__input').setValue('Furniture')
    await clickText(w, 'Add')
    await w.find('form.fbar__value').trigger('submit')
    expect(lastEmitted(w)).toEqual([
      expect.objectContaining({ fieldId: 'category', operator: 'in', value: ['Electronics', 'Furniture'] }),
    ])
  })

  it('authors a between filter for a date field', async () => {
    const w = mountBar()
    await addField(w, 'Order Date')
    await w.find('.fbar__op').setValue('between')
    const inputs = w.findAll('.fbar__input')
    await inputs[0].setValue('2026-01-01')
    await inputs[1].setValue('2026-12-31')
    await w.find('form.fbar__value').trigger('submit')
    expect(lastEmitted(w)).toEqual([
      expect.objectContaining({ operator: 'between', value: ['2026-01-01', '2026-12-31'] }),
    ])
  })

  it('blocks an empty in filter and an inverted between range', async () => {
    const w = mountBar()
    await addField(w, 'Category')
    await w.find('.fbar__op').setValue('in')
    await w.find('form.fbar__value').trigger('submit')
    expect(w.find('.fbar__error').exists()).toBe(true)
    expect(w.emitted('update:filters')).toBeFalsy()

    const w2 = mountBar()
    await addField(w2, 'Order Date')
    await w2.find('.fbar__op').setValue('between')
    const inputs = w2.findAll('.fbar__input')
    await inputs[0].setValue('2026-12-31')
    await inputs[1].setValue('2026-01-01')
    await w2.find('form.fbar__value').trigger('submit')
    expect(w2.find('.fbar__error').text()).toMatch(/after/i)
    expect(w2.emitted('update:filters')).toBeFalsy()
  })

  it('keeps two filters with different operators independent', async () => {
    const w = mountBar()
    await addField(w, 'Category')
    await w.find('.fbar__op').setValue('in')
    await w.find('.fbar__input').setValue('Electronics')
    await clickText(w, 'Add')
    await w.find('form.fbar__value').trigger('submit')

    await addField(w, 'Order Date')
    await w.find('.fbar__op').setValue('between')
    const inputs = w.findAll('.fbar__input')
    await inputs[0].setValue('2026-01-01')
    await inputs[1].setValue('2026-12-31')
    await w.find('form.fbar__value').trigger('submit')

    const filters = lastEmitted(w)
    expect(filters).toHaveLength(2)
    expect(filters.find((f) => f.fieldId === 'category')).toMatchObject({ operator: 'in', value: ['Electronics'] })
    expect(filters.find((f) => f.fieldId === 'order_date')).toMatchObject({
      operator: 'between',
      value: ['2026-01-01', '2026-12-31'],
    })
  })

  it('reloads and edits a persisted in filter without normalizing it to eq', async () => {
    const w = mountBar([{ fieldId: 'category', operator: 'in', value: ['A', 'B'], label: 'Category is one of A, B' }])
    // Chip is present; clicking it loads the editor with the in operator + tokens.
    await w.find('.fbar__chip-edit').trigger('click')
    expect((w.find('.fbar__op').element as HTMLSelectElement).value).toBe('in')
    expect(w.findAll('.fbar__token').map((t) => t.text().replace(/\s+/g, ''))).toEqual(['A', 'B'])
  })
})
