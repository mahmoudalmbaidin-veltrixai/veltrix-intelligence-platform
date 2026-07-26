import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import SourceConfigurationPanel from './SourceConfigurationPanel.vue'
import { usePipelineEditor } from './usePipelineEditor'
import { newDraft } from './pipelines.service'

vi.mock('@/shared/stores/platform', () => ({
  usePlatformStore: () => ({
    organization: { name: 'Organization Alpha' },
    workspace: { name: 'Alpha Workspace' },
  }),
}))

vi.mock('@/modules/connections/connections.service', () => ({
  connectionService: {
    list: vi.fn().mockResolvedValue({ items: [], total: 0 }),
  },
}))

vi.mock('@/shared/services/platformInfrastructure', () => ({
  platformInfrastructure: {
    files: vi.fn().mockResolvedValue({ items: [], next_cursor: null }),
    upload: vi.fn(),
  },
}))

vi.mock('@/modules/datasets/datasets.service', () => ({
  datasetService: {
    list: vi.fn().mockResolvedValue([
      {
        id: 'dataset-1',
        name: 'Orders',
        description: 'Governed orders',
        source: 'warehouse.public.orders',
        sourceType: 'table',
        schema: 'public',
        table: 'orders',
        rowCount: 2,
        qualityScore: 100,
        version: 4,
        readOnly: true,
      },
    ]),
    listFields: vi.fn().mockResolvedValue([
      { name: 'order_id', type: 'bigint', nullable: false, description: '' },
      { name: 'revenue', type: 'numeric', nullable: true, description: '' },
    ]),
    preview: vi.fn().mockResolvedValue({
      columns: [
        {
          name: 'order_id',
          displayName: 'order_id',
          physicalType: 'bigint',
          normalizedType: 'integer',
          nullable: false,
          sensitive: false,
        },
      ],
      rows: [{ order_id: 1001 }],
      page: 1,
      pageSize: 10,
      returnedRows: 1,
      maskedFields: [],
      refreshedAt: '2026-07-26T00:00:00Z',
    }),
    discover: vi.fn(),
    ingestFile: vi.fn(),
  },
}))

describe('SourceConfigurationPanel', () => {
  it('binds a real governed dataset schema and preview to the source node', async () => {
    const editor = usePipelineEditor({ ...newDraft(), id: 'pipeline-test' })
    const node = editor.addNode('source-dataset', 0, 0)
    const wrapper = mount(SourceConfigurationPanel, { props: { editor, node } })
    await flushPromises()

    expect(wrapper.text()).toContain('Organization Alpha')
    expect(wrapper.text()).toContain('Orders')
    const datasetSelect = wrapper.findAll('select').find((select) => select.text().includes('Orders'))
    expect(datasetSelect).toBeDefined()
    await datasetSelect!.setValue('dataset-1')
    await flushPromises()

    expect(editor.pipeline.nodes[0].config.dataset_id).toBe('dataset-1')
    expect(editor.pipeline.nodes[0].config.dataset_version).toBe(4)
    expect(editor.pipeline.nodes[0].outputSchema).toEqual([
      { name: 'order_id', dataType: 'integer' },
      { name: 'revenue', dataType: 'number' },
    ])
    const output = editor.addNode('file-export', 300, 0)
    editor.connect(node.id, 'out', output.id, 'in')
    expect(editor.pipeline.nodes[0].config.dataset_id).toBe('dataset-1')
    expect(wrapper.text()).toContain('1001')
  })
})
