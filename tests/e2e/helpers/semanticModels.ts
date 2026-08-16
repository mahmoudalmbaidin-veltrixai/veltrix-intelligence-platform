/**
 * Current semantic-model list contract is a JSON array of models.
 * Older harness code assumed a paginated `{ items }` envelope. Accept both so
 * fixture-preflight and browser tests bind to the live API without changing it.
 */
export interface SemanticModelListItem {
  id: string
  name: string
  key?: string
  primary_dataset_id?: string
  primary_dataset?: { id?: string }
}

export function parseSemanticModelList(body: unknown): SemanticModelListItem[] {
  if (Array.isArray(body)) return body as SemanticModelListItem[]
  if (body && typeof body === 'object') {
    const envelope = body as { items?: unknown }
    if (Array.isArray(envelope.items)) return envelope.items as SemanticModelListItem[]
    const item = body as SemanticModelListItem
    if (typeof item.id === 'string' && typeof item.name === 'string') return [item]
  }
  return []
}

export function primaryDatasetId(model: SemanticModelListItem | undefined): string {
  if (!model) return ''
  if (typeof model.primary_dataset_id === 'string' && model.primary_dataset_id) return model.primary_dataset_id
  if (typeof model.primary_dataset?.id === 'string') return model.primary_dataset.id
  return ''
}
