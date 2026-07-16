/**
 * Pipeline node type registry. Drives the palette, the dynamic config inspector,
 * port rendering, validation and schema propagation. Adding a node type here is
 * enough to make it draggable, configurable and validatable.
 */
import type { NodeTypeSpec, PipelineNodeKind, SchemaColumn } from '@/shared/types/pipeline'

const IN = [{ id: 'in', label: 'Input' }]
const OUT = [{ id: 'out', label: 'Output' }]

export const NODE_TYPES: Record<PipelineNodeKind, NodeTypeSpec> = {
  'source-database': {
    kind: 'source-database', label: 'Database Source', category: 'source', icon: 'database',
    description: 'Read from a relational database table or query.',
    docs: 'Connects to a registered database connection and reads a table or SQL query into the pipeline.',
    inputs: [], outputs: OUT,
    config: [
      { key: 'connection', label: 'Connection', type: 'select', required: true, options: [
        { value: 'cn_pg_prod', label: 'Production PostgreSQL' },
        { value: 'cn_mysql_billing', label: 'Billing MySQL' },
        { value: 'cn_mssql_erp', label: 'ERP SQL Server' },
      ] },
      { key: 'mode', label: 'Read mode', type: 'select', defaultValue: 'table', options: [
        { value: 'table', label: 'Table' }, { value: 'query', label: 'Custom SQL' },
      ] },
      { key: 'table', label: 'Table', type: 'text', placeholder: 'public.orders', visibleWhen: { key: 'mode', equals: 'table' } },
      { key: 'query', label: 'SQL query', type: 'code', language: 'sql', placeholder: 'SELECT * FROM orders', visibleWhen: { key: 'mode', equals: 'query' } },
      { key: 'incremental', label: 'Incremental load', type: 'boolean', help: 'Only read rows newer than the last watermark.' },
    ],
  },
  'source-file': {
    kind: 'source-file', label: 'File Source', category: 'source', icon: 'folder',
    description: 'Read CSV / Excel / Parquet from storage.',
    docs: 'Reads a delimited or columnar file from an object store or upload.',
    inputs: [], outputs: OUT,
    config: [
      { key: 'connection', label: 'Storage', type: 'select', required: true, options: [
        { value: 'cn_s3_lake', label: 'Data Lake (S3)' }, { value: 'upload', label: 'Direct upload' },
      ] },
      { key: 'path', label: 'File path', type: 'text', required: true, placeholder: 's3://lake/raw/orders/*.csv' },
      { key: 'format', label: 'Format', type: 'select', defaultValue: 'csv', options: [
        { value: 'csv', label: 'CSV' }, { value: 'excel', label: 'Excel' }, { value: 'parquet', label: 'Parquet' },
      ] },
      { key: 'header', label: 'First row is header', type: 'boolean', defaultValue: true },
    ],
  },
  'source-rest': {
    kind: 'source-rest', label: 'REST API Source', category: 'source', icon: 'external',
    description: 'Fetch JSON from an HTTP endpoint.',
    docs: 'Calls a REST endpoint and flattens the JSON response into rows.',
    inputs: [], outputs: OUT,
    config: [
      { key: 'url', label: 'Endpoint URL', type: 'text', required: true, placeholder: 'https://api.example.com/v1/orders' },
      { key: 'method', label: 'Method', type: 'select', defaultValue: 'GET', options: [
        { value: 'GET', label: 'GET' }, { value: 'POST', label: 'POST' },
      ] },
      { key: 'headers', label: 'Headers', type: 'keyvalue', help: 'Authorization is resolved from the connection secret at run time.' },
      { key: 'jsonPath', label: 'Records path', type: 'text', placeholder: '$.data.items' },
    ],
  },
  'select-columns': {
    kind: 'select-columns', label: 'Select Columns', category: 'transform', icon: 'table',
    description: 'Keep or drop specific columns.',
    docs: 'Projects a subset of the input schema.',
    inputs: IN, outputs: OUT,
    config: [
      { key: 'columns', label: 'Columns to keep', type: 'columns', required: true, help: 'Leave empty to keep all.' },
    ],
  },
  'rename-columns': {
    kind: 'rename-columns', label: 'Rename Columns', category: 'transform', icon: 'text',
    description: 'Rename one or more columns.',
    docs: 'Applies a mapping of old → new column names.',
    inputs: IN, outputs: OUT,
    config: [{ key: 'mapping', label: 'Rename mapping', type: 'keyvalue', required: true }],
  },
  filter: {
    kind: 'filter', label: 'Filter', category: 'transform', icon: 'filter',
    description: 'Keep rows matching a condition.',
    docs: 'Filters rows using a boolean expression over columns.',
    inputs: IN, outputs: OUT,
    config: [
      { key: 'expression', label: 'Filter expression', type: 'code', language: 'sql', required: true, placeholder: "status = 'active' AND amount > 0" },
    ],
  },
  sort: {
    kind: 'sort', label: 'Sort', category: 'transform', icon: 'sort',
    description: 'Order rows by columns.',
    docs: 'Sorts the dataset by one or more keys.',
    inputs: IN, outputs: OUT,
    config: [
      { key: 'sortBy', label: 'Sort by column', type: 'text', required: true, placeholder: 'order_date' },
      { key: 'direction', label: 'Direction', type: 'select', defaultValue: 'asc', options: [
        { value: 'asc', label: 'Ascending' }, { value: 'desc', label: 'Descending' },
      ] },
    ],
  },
  join: {
    kind: 'join', label: 'Join', category: 'transform', icon: 'workflow',
    description: 'Combine two inputs on a key.',
    docs: 'Joins the left and right inputs. Requires two upstream connections.',
    inputs: [{ id: 'left', label: 'Left' }, { id: 'right', label: 'Right' }], outputs: OUT,
    config: [
      { key: 'type', label: 'Join type', type: 'select', required: true, defaultValue: 'inner', options: [
        { value: 'inner', label: 'Inner' }, { value: 'left', label: 'Left outer' }, { value: 'right', label: 'Right outer' }, { value: 'full', label: 'Full outer' },
      ] },
      { key: 'leftKey', label: 'Left key', type: 'text', required: true, placeholder: 'customer_id' },
      { key: 'rightKey', label: 'Right key', type: 'text', required: true, placeholder: 'id' },
    ],
  },
  union: {
    kind: 'union', label: 'Union', category: 'transform', icon: 'layers',
    description: 'Stack rows from two inputs.',
    docs: 'Concatenates rows of two inputs with matching schemas.',
    inputs: [{ id: 'a', label: 'A' }, { id: 'b', label: 'B' }], outputs: OUT,
    config: [{ key: 'dedupe', label: 'Remove duplicates', type: 'boolean' }],
  },
  aggregate: {
    kind: 'aggregate', label: 'Aggregate', category: 'transform', icon: 'gauge',
    description: 'Group and summarise.',
    docs: 'Groups rows and computes aggregate measures.',
    inputs: IN, outputs: OUT,
    config: [
      { key: 'groupBy', label: 'Group by', type: 'text', placeholder: 'region, category', help: 'Comma-separated columns.' },
      { key: 'aggregations', label: 'Aggregations', type: 'keyvalue', required: true, help: 'e.g. revenue → sum' },
    ],
  },
  formula: {
    kind: 'formula', label: 'Formula', category: 'transform', icon: 'hash',
    description: 'Add a derived column.',
    docs: 'Creates a new column from an expression.',
    inputs: IN, outputs: OUT,
    config: [
      { key: 'columnName', label: 'New column name', type: 'text', required: true, placeholder: 'margin_pct' },
      { key: 'expression', label: 'Expression', type: 'code', language: 'sql', required: true, placeholder: 'profit / NULLIF(revenue, 0)' },
    ],
  },
  'type-convert': {
    kind: 'type-convert', label: 'Type Conversion', category: 'transform', icon: 'refresh',
    description: 'Change column data types.',
    docs: 'Casts columns to a target data type.',
    inputs: IN, outputs: OUT,
    config: [{ key: 'conversions', label: 'Conversions', type: 'keyvalue', required: true, help: 'column → type (string/number/date/boolean)' }],
  },
  deduplicate: {
    kind: 'deduplicate', label: 'Deduplicate', category: 'transform', icon: 'copy',
    description: 'Remove duplicate rows.',
    docs: 'Drops duplicate rows based on key columns.',
    inputs: IN, outputs: OUT,
    config: [{ key: 'keys', label: 'Key columns', type: 'text', placeholder: 'order_id', help: 'Empty = full-row dedup.' }],
  },
  'null-handling': {
    kind: 'null-handling', label: 'Null Handling', category: 'transform', icon: 'warning',
    description: 'Fill or drop nulls.',
    docs: 'Handles missing values by dropping or imputing.',
    inputs: IN, outputs: OUT,
    config: [
      { key: 'strategy', label: 'Strategy', type: 'select', required: true, defaultValue: 'drop', options: [
        { value: 'drop', label: 'Drop rows with nulls' }, { value: 'fill', label: 'Fill with value' },
      ] },
      { key: 'fillValue', label: 'Fill value', type: 'text', visibleWhen: { key: 'strategy', equals: 'fill' } },
    ],
  },
  'sql-transform': {
    kind: 'sql-transform', label: 'SQL Transform', category: 'transform', icon: 'code',
    description: 'Arbitrary SQL over inputs.',
    docs: 'Runs a SQL statement against the input, referenced as `input`.',
    inputs: IN, outputs: OUT,
    config: [{ key: 'sql', label: 'SQL', type: 'code', language: 'sql', required: true, placeholder: 'SELECT region, SUM(revenue) AS revenue FROM input GROUP BY 1' }],
  },
  'python-transform': {
    kind: 'python-transform', label: 'Python Transform', category: 'transform', icon: 'code',
    description: 'Transform with Python (pandas).',
    docs: 'Executes a Python function receiving a dataframe `df` and returning a dataframe.',
    inputs: IN, outputs: OUT,
    config: [{ key: 'code', label: 'Python', type: 'code', language: 'python', required: true, placeholder: 'def transform(df):\n    return df' }],
  },
  'output-dataset': {
    kind: 'output-dataset', label: 'Output Dataset', category: 'output', icon: 'database',
    description: 'Materialise as a governed dataset.',
    docs: 'Writes the result as a versioned dataset in the catalog.',
    inputs: IN, outputs: [],
    config: [
      { key: 'datasetName', label: 'Dataset name', type: 'text', required: true, placeholder: 'fct_orders' },
      { key: 'writeMode', label: 'Write mode', type: 'select', defaultValue: 'overwrite', options: [
        { value: 'overwrite', label: 'Overwrite' }, { value: 'append', label: 'Append' }, { value: 'merge', label: 'Merge / upsert' },
      ] },
      { key: 'certify', label: 'Request certification', type: 'boolean' },
    ],
  },
  'file-export': {
    kind: 'file-export', label: 'File Export', category: 'output', icon: 'download',
    description: 'Export to a file in storage.',
    docs: 'Writes the result to a file in an object store.',
    inputs: IN, outputs: [],
    config: [
      { key: 'connection', label: 'Storage', type: 'select', required: true, options: [{ value: 'cn_s3_lake', label: 'Data Lake (S3)' }] },
      { key: 'path', label: 'Destination path', type: 'text', required: true, placeholder: 's3://lake/exports/orders.parquet' },
      { key: 'format', label: 'Format', type: 'select', defaultValue: 'parquet', options: [
        { value: 'csv', label: 'CSV' }, { value: 'parquet', label: 'Parquet' }, { value: 'json', label: 'JSON' },
      ] },
    ],
  },
}

export const PALETTE_GROUPS: { label: string; kinds: PipelineNodeKind[] }[] = [
  { label: 'Sources', kinds: ['source-database', 'source-file', 'source-rest'] },
  { label: 'Prepare', kinds: ['select-columns', 'rename-columns', 'filter', 'sort', 'deduplicate', 'null-handling', 'type-convert'] },
  { label: 'Combine', kinds: ['join', 'union'] },
  { label: 'Transform', kinds: ['aggregate', 'formula', 'sql-transform', 'python-transform'] },
  { label: 'Outputs', kinds: ['output-dataset', 'file-export'] },
]

/** Mock output schema per node kind, for the inspector's schema tab. */
export function mockOutputSchema(kind: PipelineNodeKind): SchemaColumn[] {
  const base: SchemaColumn[] = [
    { name: 'order_id', dataType: 'string' },
    { name: 'customer_id', dataType: 'string' },
    { name: 'region', dataType: 'string' },
    { name: 'order_date', dataType: 'date' },
    { name: 'revenue', dataType: 'currency' },
    { name: 'units', dataType: 'integer' },
  ]
  if (kind === 'aggregate') return [{ name: 'region', dataType: 'string' }, { name: 'revenue', dataType: 'currency' }, { name: 'orders', dataType: 'integer' }]
  if (kind === 'formula') return [...base, { name: 'margin_pct', dataType: 'percent' }]
  return base
}
