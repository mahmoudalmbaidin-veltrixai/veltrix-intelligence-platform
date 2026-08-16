import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

// A controllable connections ref so each test can present 0 / 1 / 2+ eligible
// connections and mutate them mid-session (workspace switch / deactivation).
const holder = vi.hoisted(() => ({ dataRef: null as unknown as { value: unknown[] } }))
const ingestCsv = vi.hoisted(() => vi.fn().mockResolvedValue({ discovered: 1, persisted: 1, warnings: [] }))
const ingestFile = vi.hoisted(() => vi.fn().mockResolvedValue({ discovered: 1, persisted: 1, warnings: [] }))
const upload = vi.hoisted(() => vi.fn().mockResolvedValue({ id: 'file-1' }))
const listPage = vi.hoisted(() => vi.fn().mockResolvedValue({ items: [], total: 0, page: 1, pageSize: 50 }))

vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }) }))
vi.mock('@/shared/lib/query', async () => {
  const { ref } = await import('vue')
  holder.dataRef = ref([]) as unknown as { value: unknown[] }
  return { useQuery: () => ({ data: holder.dataRef, isLoading: ref(false) }) }
})
vi.mock('@/shared/stores/platform', () => ({ usePlatformStore: () => ({ can: () => true }) }))
vi.mock('@/shared/stores/ui', () => ({ useUiStore: () => ({ pushToast: vi.fn() }) }))
vi.mock('@/modules/connections/connections.service', () => ({
  connectionService: { list: vi.fn().mockResolvedValue({ items: [] }) },
}))
vi.mock('@/shared/lib/fileFormats', () => ({
  isLegacyXlsFilename: () => false,
  isXlsxFilename: (name: string) => name.toLowerCase().endsWith('.xlsx'),
  loadFileFormatCapabilities: vi.fn().mockResolvedValue({}),
  tabularAcceptAttribute: () => '.csv,.xlsx',
}))
vi.mock('@/shared/services/platformInfrastructure', () => ({ platformInfrastructure: { upload } }))
vi.mock('./datasets.service', () => ({
  datasetService: { listPage, ingestCsv, ingestFile, discover: vi.fn(), archive: vi.fn(), remove: vi.fn() },
}))

import DatasetListView from './DatasetListView.vue'

const conn = (id: string, name: string, status = 'active') => ({ id, name, status, type: { name: 'Postgres' } })

const stubs = {
  VipSelect: {
    props: ['options', 'modelValue', 'label', 'help'],
    emits: ['update:modelValue'],
    template:
      '<select :aria-label="label" :value="modelValue" @change="$emit(\'update:modelValue\', $event.target.value)"><option value="">—</option><option v-for="o in options" :key="o.value" :value="o.value">{{ o.label }}</option></select>',
  },
  VipButton: {
    props: ['disabled', 'loading'],
    emits: ['click'],
    template: '<button :disabled="disabled || loading" @click="$emit(\'click\')"><slot /></button>',
  },
  VipTextarea: {
    props: ['modelValue'],
    emits: ['update:modelValue'],
    template: '<textarea :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
  },
  VipInput: {
    props: ['modelValue'],
    emits: ['update:modelValue'],
    template: '<input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
  },
  VipDialog: { props: ['open'], template: '<div v-if="open"><slot /><slot name="footer" /></div>' },
  VipCard: { template: '<div><slot /></div>' },
  VipPageHeader: { template: '<div><slot name="actions" /></div>' },
  VipTable: { props: ['rows'], template: '<div class="vt"></div>' },
  VipCheckbox: true,
  VipMenu: true,
  VipConfirmDialog: true,
  VipBadge: true,
  VipIcon: true,
  VipTooltip: true,
}

async function mountView(connections: ReturnType<typeof conn>[]) {
  holder.dataRef.value = connections
  const w = mount(DatasetListView, { global: { stubs } })
  await flushPromises()
  return w
}
const openCsv = async (w: Awaited<ReturnType<typeof mountView>>) => {
  await w
    .findAll('button')
    .find((b) => b.text() === 'Import CSV')!
    .trigger('click')
  await flushPromises()
}
const connSelect = (w: Awaited<ReturnType<typeof mountView>>) => w.find('select[aria-label="Connection"]')
const submitBtn = (w: Awaited<ReturnType<typeof mountView>>) =>
  w.findAll('button').find((b) => b.text() === 'Import and catalog')!

describe('Dataset import connection selection (DATASET-P2-IMPORT-CONNECTION)', () => {
  beforeEach(() => vi.clearAllMocks())
  afterEach(() => {
    holder.dataRef.value = []
  })

  it('Test 1 — zero connections: empty-state guidance, no select, submit disabled', async () => {
    const w = await mountView([])
    await openCsv(w)
    expect(w.find('.discovery-empty').exists()).toBe(true)
    expect(connSelect(w).exists()).toBe(false)
    expect(submitBtn(w).attributes('disabled')).toBeDefined()
  })

  it('Test 2 — one connection: preselected, visible, submit enabled', async () => {
    const w = await mountView([conn('c1', 'Finance WH')])
    await openCsv(w)
    expect((connSelect(w).element as HTMLSelectElement).value).toBe('c1')
    expect(submitBtn(w).attributes('disabled')).toBeUndefined()
  })

  it('Test 3 — multiple connections: none preselected, submit disabled', async () => {
    const w = await mountView([conn('a', 'A'), conn('b', 'B')])
    await openCsv(w)
    expect((connSelect(w).element as HTMLSelectElement).value).toBe('')
    expect(submitBtn(w).attributes('disabled')).toBeDefined()
  })

  it('Test 4 & 7 — explicit choice B submits with B (not the first connection)', async () => {
    const w = await mountView([conn('a', 'A'), conn('b', 'B')])
    await openCsv(w)
    await connSelect(w).setValue('b')
    await w.find('textarea').setValue('id,amount\n1,2\n')
    await submitBtn(w).trigger('click')
    await flushPromises()
    expect(ingestCsv).toHaveBeenCalledTimes(1)
    expect(ingestCsv.mock.calls[0][0].connectionId).toBe('b')
  })

  it('Test 5 — switching workspace clears an invalid selection', async () => {
    const w = await mountView([conn('a', 'A'), conn('b', 'B')])
    await openCsv(w)
    await connSelect(w).setValue('b')
    expect((connSelect(w).element as HTMLSelectElement).value).toBe('b')
    // New workspace exposes entirely different connections.
    holder.dataRef.value = [conn('x', 'X'), conn('y', 'Y')]
    await flushPromises()
    expect((connSelect(w).element as HTMLSelectElement).value).toBe('')
  })

  it('Test 6 — deactivating the selected connection clears it (no silent switch)', async () => {
    const w = await mountView([conn('a', 'A'), conn('b', 'B')])
    await openCsv(w)
    await connSelect(w).setValue('b')
    // B is deactivated / removed from the eligible list; A remains.
    holder.dataRef.value = [conn('a', 'A')]
    await flushPromises()
    expect((connSelect(w).element as HTMLSelectElement).value).toBe('')
  })

  it('Test 8 — XLSX import submits with the chosen connection', async () => {
    const w = await mountView([conn('a', 'A'), conn('b', 'B')])
    await openCsv(w)
    await connSelect(w).setValue('b')
    const file = new File(['x'], 'book.xlsx', {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    })
    const input = w.find('input[type="file"]')
    Object.defineProperty(input.element, 'files', { value: [file], configurable: true })
    await input.trigger('change')
    await flushPromises()
    await submitBtn(w).trigger('click')
    await flushPromises()
    expect(upload).toHaveBeenCalledTimes(1)
    expect(ingestFile).toHaveBeenCalledTimes(1)
    expect(ingestFile.mock.calls[0][0].connectionId).toBe('b')
  })
})
