import type { Pipeline } from '@/shared/types/pipeline'
import { isoAgo, isoAhead } from '@/shared/lib/mock'

export const SEED_PIPELINES: Pipeline[] = [
  {
    id: 'pl_revenue',
    name: 'Revenue Nightly ETL',
    description: 'Builds the certified fct_orders dataset from ERP + billing sources.',
    status: 'published',
    version: 7,
    owner: 'Revenue Ops',
    tags: ['finance', 'certified', 'nightly'],
    updatedAt: isoAgo(180),
    lastRunAt: isoAgo(60),
    lastRunStatus: 'failed',
    nextSchedule: isoAhead(360),
    nodes: [
      { id: 'n1', kind: 'source-database', title: 'ERP Orders', x: 80, y: 120, config: { connection: 'cn_mssql_erp', mode: 'table', table: 'dbo.orders' } },
      { id: 'n2', kind: 'source-database', title: 'Billing', x: 80, y: 300, config: { connection: 'cn_mysql_billing', mode: 'table', table: 'invoices' } },
      { id: 'n3', kind: 'filter', title: 'Active only', x: 360, y: 120, config: { expression: "status = 'active'" } },
      { id: 'n4', kind: 'join', title: 'Join billing', x: 620, y: 200, config: { type: 'left', leftKey: 'order_id', rightKey: 'order_id' } },
      { id: 'n5', kind: 'aggregate', title: 'Rollup by region', x: 880, y: 200, config: { groupBy: 'region', aggregations: { revenue: 'sum' } } },
      { id: 'n6', kind: 'output-dataset', title: 'fct_orders', x: 1140, y: 200, config: { datasetName: 'fct_orders', writeMode: 'overwrite', certify: true } },
    ],
    edges: [
      { id: 'e1', sourceNode: 'n1', sourcePort: 'out', targetNode: 'n3', targetPort: 'in' },
      { id: 'e2', sourceNode: 'n3', sourcePort: 'out', targetNode: 'n4', targetPort: 'left' },
      { id: 'e3', sourceNode: 'n2', sourcePort: 'out', targetNode: 'n4', targetPort: 'right' },
      { id: 'e4', sourceNode: 'n4', sourcePort: 'out', targetNode: 'n5', targetPort: 'in' },
      { id: 'e5', sourceNode: 'n5', sourcePort: 'out', targetNode: 'n6', targetPort: 'in' },
    ],
  },
  {
    id: 'pl_customer',
    name: 'Customer 360 Build',
    description: 'Unifies CRM, product and support data into dim_customers.',
    status: 'published',
    version: 4,
    owner: 'Data Engineering',
    tags: ['customer', 'certified'],
    updatedAt: isoAgo(1440),
    lastRunAt: isoAgo(200),
    lastRunStatus: 'succeeded',
    nextSchedule: isoAhead(720),
    nodes: [
      { id: 'm1', kind: 'source-rest', title: 'Salesforce CRM', x: 80, y: 160, config: { url: 'https://api.crm/v1/accounts', method: 'GET', jsonPath: '$.records' } },
      { id: 'm2', kind: 'select-columns', title: 'Select fields', x: 360, y: 160, config: { columns: ['id', 'name', 'segment'] } },
      { id: 'm3', kind: 'output-dataset', title: 'dim_customers', x: 640, y: 160, config: { datasetName: 'dim_customers', writeMode: 'merge' } },
    ],
    edges: [
      { id: 'me1', sourceNode: 'm1', sourcePort: 'out', targetNode: 'm2', targetPort: 'in' },
      { id: 'me2', sourceNode: 'm2', sourcePort: 'out', targetNode: 'm3', targetPort: 'in' },
    ],
  },
  {
    id: 'pl_events',
    name: 'Event Stream Rollup',
    description: 'Aggregates raw product events into hourly metrics.',
    status: 'draft',
    version: 1,
    owner: 'You',
    tags: ['events', 'draft'],
    updatedAt: isoAgo(30),
    nodes: [
      { id: 'v1', kind: 'source-file', title: 'Raw events', x: 120, y: 180, config: { connection: 'cn_s3_lake', path: 's3://lake/events/*.parquet', format: 'parquet' } },
    ],
    edges: [],
  },
]
