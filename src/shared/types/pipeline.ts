/**
 * Pipeline Studio domain models.
 * A pipeline is a directed graph of typed nodes connected by edges. Each node
 * carries configuration, validation, execution state and I/O schema.
 */

import type { DataType } from './semantic'

export type PipelineNodeKind =
  // Sources
  | 'source-database'
  | 'source-file'
  | 'source-rest'
  // Transforms
  | 'select-columns'
  | 'rename-columns'
  | 'filter'
  | 'sort'
  | 'join'
  | 'union'
  | 'aggregate'
  | 'formula'
  | 'type-convert'
  | 'deduplicate'
  | 'null-handling'
  | 'sql-transform'
  | 'python-transform'
  // Outputs
  | 'output-dataset'
  | 'file-export'

export type NodeCategory = 'source' | 'transform' | 'output'

export interface NodePortSpec {
  id: string
  label: string
}

/** Static metadata describing a node type (drives the palette + inspector). */
export interface NodeTypeSpec {
  kind: PipelineNodeKind
  label: string
  category: NodeCategory
  icon: string // icon key
  description: string
  docs: string
  inputs: NodePortSpec[]
  outputs: NodePortSpec[]
  /** Config field schema rendered dynamically by the inspector. */
  config: NodeConfigField[]
}

export type NodeConfigFieldType =
  | 'text'
  | 'textarea'
  | 'number'
  | 'select'
  | 'multiselect'
  | 'boolean'
  | 'columns'
  | 'code'
  | 'keyvalue'
  | 'secret'
  | 'formula'

export interface NodeConfigField {
  key: string
  label: string
  type: NodeConfigFieldType
  required?: boolean
  placeholder?: string
  help?: string
  options?: { value: string; label: string }[]
  language?: 'sql' | 'python'
  defaultValue?: unknown
  /** Show only when another field has one of these values. */
  visibleWhen?: { key: string; equals: string | boolean }
}

export type NodeValidationLevel = 'error' | 'warning'
export interface NodeValidationMsg {
  level: NodeValidationLevel
  message: string
}

export type NodeExecStatus =
  'idle' | 'queued' | 'running' | 'waiting' | 'succeeded' | 'failed' | 'cancelled' | 'timed-out' | 'skipped'

export interface SchemaColumn {
  name: string
  dataType: DataType
}

export interface PipelineNode {
  id: string
  kind: PipelineNodeKind
  title: string
  x: number
  y: number
  config: Record<string, unknown>
  /** Cached schemas for the inspector. */
  inputSchema?: SchemaColumn[]
  outputSchema?: SchemaColumn[]
}

export interface PipelineEdge {
  id: string
  sourceNode: string
  sourcePort: string
  targetNode: string
  targetPort: string
}

export type PipelineStatus = 'draft' | 'published'

export interface Pipeline {
  id: string
  name: string
  description: string
  status: PipelineStatus
  version: number
  owner: string
  tags: string[]
  nodes: PipelineNode[]
  edges: PipelineEdge[]
  updatedAt: string
  lastRunAt?: string
  lastRunStatus?: NodeExecStatus
  nextSchedule?: string
}

export interface PipelineListItem {
  id: string
  name: string
  status: PipelineStatus
  owner: string
  tags: string[]
  version: number
  updatedAt: string
  lastRunAt?: string
  lastRunStatus?: NodeExecStatus
  nextSchedule?: string
  nodeCount: number
}

/* ---------------- Validation ---------------- */

export interface ValidationIssue {
  id: string
  level: NodeValidationLevel
  scope: 'pipeline' | 'node' | 'edge'
  nodeId?: string
  edgeId?: string
  code: string
  message: string
}

export interface ValidationReport {
  valid: boolean
  issues: ValidationIssue[]
  checkedAt: string
}

/* ---------------- Execution ---------------- */

export type RunStatus = 'queued' | 'running' | 'waiting' | 'succeeded' | 'failed' | 'cancelled' | 'timed-out'

export interface RunNodeState {
  nodeId: string
  status: NodeExecStatus
  rows?: number
  durationMs?: number
  message?: string
}

export interface RunLogEntry {
  ts: string
  level: 'info' | 'warn' | 'error'
  nodeId?: string
  message: string
}

export interface PipelineRun {
  id: string
  pipelineId: string
  status: RunStatus
  startedAt: string
  finishedAt?: string
  durationMs?: number
  correlationId: string
  trigger: 'manual' | 'schedule' | 'api' | 'automation'
  progress: number // 0..100
  currentNodeId?: string
  nodeStates: RunNodeState[]
  logs: RunLogEntry[]
  attempt: number
  rowsProcessed: number
}
