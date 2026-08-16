import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ref } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'

// A live-sized catalog (182 datasets) so multi-page behavior is exercised the
// way the CERT-P2-003 environment surfaced it.
const ALL = Array.from({ length: 182 }, (_, i) => ({
  id: `ds_${i}`,
  name: `dataset ${i}`,
  certified: i % 5 === 0,
  status: 'active',
}))

const listPage = vi.hoisted(() =>
  vi.fn(async (opts: { page?: number; pageSize?: number; search?: string; status?: string } = {}) => {
    const pageSize = opts.pageSize ?? 50
    const page = opts.page ?? 1
    let items = ALL
    if (opts.search) items = items.filter((d) => d.name.includes(opts.search!))
    const total = items.length
    const start = (page - 1) * pageSize
    return { items: items.slice(start, start + pageSize), total, page, pageSize }
  }),
)
const push = vi.hoisted(() => vi.fn())

vi.mock('vue-router', () => ({ useRouter: () => ({ push }) }))
vi.mock('@/shared/lib/query', () => ({ useQuery: () => ({ data: ref([]), isLoading: ref(false) }) }))
vi.mock('@/shared/stores/platform', () => ({ usePlatformStore: () => ({ can: () => true }) }))
vi.mock('@/shared/stores/ui', () => ({ useUiStore: () => ({ pushToast: vi.fn() }) }))
vi.mock('@/modules/connections/connections.service', () => ({
  connectionService: { list: vi.fn().mockResolvedValue({ items: [] }) },
}))
vi.mock('@/shared/lib/fileFormats', () => ({
  isLegacyXlsFilename: () => false,
  isXlsxFilename: () => false,
  loadFileFormatCapabilities: vi.fn().mockResolvedValue({}),
  tabularAcceptAttribute: () => '.csv',
}))
vi.mock('@/shared/services/platformInfrastructure', () => ({ platformInfrastructure: { upload: vi.fn() } }))
vi.mock('./datasets.service', () => ({ datasetService: { listPage, archive: vi.fn(), remove: vi.fn() } }))

import DatasetListView from './DatasetListView.vue'

const stubs = {
  VipButton: {
    props: ['disabled'],
    emits: ['click'],
    template: '<button :disabled="disabled" @click="$emit(\'click\')"><slot /></button>',
  },
  VipSelect: {
    props: ['options', 'modelValue', 'ariaLabel'],
    emits: ['update:modelValue'],
    template:
      '<select :aria-label="ariaLabel" :value="modelValue" @change="$emit(\'update:modelValue\', $event.target.value)"><option v-for="o in options" :key="o.value" :value="o.value">{{ o.label }}</option></select>',
  },
  VipTable: { props: ['rows'], template: '<div class="vt" :data-count="rows.length"></div>' },
  VipInput: {
    props: ['modelValue'],
    emits: ['update:modelValue'],
    template: '<input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
  },
  VipCard: { template: '<div><slot /></div>' },
  VipPageHeader: { template: '<div><slot name="actions" /></div>' },
  VipCheckbox: { props: ['modelValue'], emits: ['update:modelValue'], template: '<input type="checkbox" />' },
  VipBadge: true,
  VipIcon: true,
  VipTooltip: true,
  VipDialog: true,
  VipTextarea: true,
  VipMenu: true,
  VipConfirmDialog: true,
}

async function mountView() {
  const w = mount(DatasetListView, { global: { stubs } })
  await flushPromises()
  return w
}
const rowCount = (w: Awaited<ReturnType<typeof mountView>>) => Number(w.find('.vt').attributes('data-count'))
const pagerButtons = (w: Awaited<ReturnType<typeof mountView>>) => w.findAll('.dl__paging-controls button')
const nextBtn = (w: Awaited<ReturnType<typeof mountView>>) => pagerButtons(w).find((b) => b.text() === 'Next')!
const prevBtn = (w: Awaited<ReturnType<typeof mountView>>) => pagerButtons(w).find((b) => b.text() === 'Previous')!

describe('DatasetListView pagination (CERT-P2-003)', () => {
  beforeEach(() => listPage.mockClear())
  afterEach(() => vi.useRealTimers())

  it('Test 1 & 8 — first page: 50 rows, Page 1 of 4, Previous disabled, range readout', async () => {
    const w = await mountView()
    expect(listPage).toHaveBeenLastCalledWith(expect.objectContaining({ page: 1, pageSize: 50 }))
    expect(rowCount(w)).toBe(50)
    expect(w.find('.dl__page-of').text()).toBe('Page 1 of 4')
    expect(prevBtn(w).attributes('disabled')).toBeDefined()
    expect(nextBtn(w).attributes('disabled')).toBeUndefined()
    expect(w.find('.dl__range').text().replace(/\s+/g, ' ')).toContain('Showing 1')
    expect(w.find('.dl__range').text()).toContain('of 182 datasets')
  })

  it('Test 2 — Next requests page 2 and renders it', async () => {
    const w = await mountView()
    await nextBtn(w).trigger('click')
    await flushPromises()
    expect(listPage).toHaveBeenLastCalledWith(expect.objectContaining({ page: 2, pageSize: 50 }))
    expect(w.find('.dl__page-of').text()).toBe('Page 2 of 4')
    expect(w.find('.dl__range').text()).toContain('51')
    expect(w.find('.dl__range').text()).toContain('100')
  })

  it('Test 3 — last page: 32 rows, Next disabled, range 151–182', async () => {
    const w = await mountView()
    await nextBtn(w).trigger('click')
    await flushPromises()
    await nextBtn(w).trigger('click')
    await flushPromises()
    await nextBtn(w).trigger('click')
    await flushPromises()
    expect(w.find('.dl__page-of').text()).toBe('Page 4 of 4')
    expect(rowCount(w)).toBe(32)
    expect(nextBtn(w).attributes('disabled')).toBeDefined()
    expect(w.find('.dl__range').text()).toContain('151')
    expect(w.find('.dl__range').text()).toContain('of 182 datasets')
  })

  it('Test 4 — Previous navigates back a page', async () => {
    const w = await mountView()
    await nextBtn(w).trigger('click')
    await flushPromises()
    expect(w.find('.dl__page-of').text()).toBe('Page 2 of 4')
    await prevBtn(w).trigger('click')
    await flushPromises()
    expect(listPage).toHaveBeenLastCalledWith(expect.objectContaining({ page: 1 }))
    expect(w.find('.dl__page-of').text()).toBe('Page 1 of 4')
  })

  it('Test 5 — changing search resets to page 1 and updates the total', async () => {
    const w = await mountView()
    await nextBtn(w).trigger('click')
    await flushPromises()
    expect(w.find('.dl__page-of').text()).toBe('Page 2 of 4')

    await w.find('input').setValue('dataset 99') // debounced 300ms; matches exactly one
    await new Promise((r) => setTimeout(r, 320))
    await flushPromises()

    expect(listPage).toHaveBeenLastCalledWith(expect.objectContaining({ page: 1, search: 'dataset 99' }))
    expect(w.find('.dl__page-of').text()).toBe('Page 1 of 1')
    expect(w.find('.dl__range').text()).toContain('of 1 datasets')
  })

  it('Test 6 — changing the status filter resets to page 1', async () => {
    const w = await mountView()
    await nextBtn(w).trigger('click')
    await flushPromises()
    await w.find('select[aria-label="Dataset status"]').setValue('building')
    await flushPromises()
    // building maps to the backend "inactive" status and resets to page 1.
    expect(listPage).toHaveBeenLastCalledWith(expect.objectContaining({ page: 1, status: 'inactive' }))
  })

  it('page size selector re-anchors to page 1 and requests the new size', async () => {
    const w = await mountView()
    await nextBtn(w).trigger('click')
    await flushPromises()
    await w.find('select.dl__page-size').setValue('100')
    await flushPromises()
    expect(listPage).toHaveBeenLastCalledWith(expect.objectContaining({ page: 1, pageSize: 100 }))
    expect(w.find('.dl__page-of').text()).toBe('Page 1 of 2') // ceil(182/100)
    expect(rowCount(w)).toBe(100)
  })

  it('Test 7 — empty catalog hides the pager and shows nothing to page through', async () => {
    listPage.mockResolvedValueOnce({ items: [], total: 0, page: 1, pageSize: 50 })
    const w = await mountView()
    expect(rowCount(w)).toBe(0)
    expect(w.find('.dl__paging').exists()).toBe(false)
  })
})
