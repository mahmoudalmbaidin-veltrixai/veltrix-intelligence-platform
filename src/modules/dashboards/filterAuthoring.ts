/**
 * Dashboard filter-bar authoring helpers. The persistence/publish/viewer layers
 * already round-trip `eq`, `in` and `between` (see dashboards.service operator
 * maps); this module lets the editor author those operators with field-type-
 * aware options, adaptive value shapes, and validation — instead of silently
 * committing every filter as `eq`.
 */
import type { FilterOperator, QueryFilter, SemanticField } from '@/shared/types/semantic'

export interface FilterOperatorOption {
  value: FilterOperator
  label: string
}

type FieldShape = Pick<SemanticField, 'id' | 'label' | 'role' | 'dataType'>

export function isDateField(field: Pick<SemanticField, 'role' | 'dataType'>): boolean {
  return field.role === 'time' || field.dataType === 'date' || field.dataType === 'datetime'
}

export function isNumericField(field: Pick<SemanticField, 'dataType'>): boolean {
  return (
    field.dataType === 'number' ||
    field.dataType === 'integer' ||
    field.dataType === 'currency' ||
    field.dataType === 'percent'
  )
}

/**
 * Operators offered for a field, constrained to combinations the query engine
 * supports: date/numeric fields get Equals + Between; categorical/other fields
 * get Equals + Is one of. `eq` is always first (the default).
 */
export function operatorsForField(field: Pick<SemanticField, 'role' | 'dataType'>): FilterOperatorOption[] {
  if (isDateField(field) || isNumericField(field)) {
    return [
      { value: 'eq', label: 'Equals' },
      { value: 'between', label: 'Between' },
    ]
  }
  return [
    { value: 'eq', label: 'Equals' },
    { value: 'in', label: 'Is one of' },
  ]
}

export function defaultOperatorForField(field: Pick<SemanticField, 'role' | 'dataType'>): FilterOperator {
  return operatorsForField(field)[0].value
}

/** The HTML input type appropriate for a field's scalar/range value editors. */
export function valueInputType(field: Pick<SemanticField, 'role' | 'dataType'>): 'date' | 'number' | 'text' {
  if (isDateField(field)) return 'date'
  if (isNumericField(field)) return 'number'
  return 'text'
}

export interface FilterDraft {
  value?: string
  values?: string[]
  from?: string
  to?: string
}

export interface BuildResult {
  filter?: QueryFilter
  error?: string
}

function compareValues(a: string, b: string, field: FieldShape): number {
  if (isNumericField(field)) {
    const na = Number(a)
    const nb = Number(b)
    if (!Number.isNaN(na) && !Number.isNaN(nb)) return na === nb ? 0 : na < nb ? -1 : 1
  }
  // ISO dates and plain strings both order correctly lexicographically.
  return a === b ? 0 : a < b ? -1 : 1
}

/**
 * Build a canonical QueryFilter from the pending draft, or return a validation
 * error. Never produces malformed payloads (`in: []`, `between` with a missing
 * bound, or an inverted range).
 */
export function buildDashboardFilter(field: FieldShape, operator: FilterOperator, draft: FilterDraft): BuildResult {
  if (operator === 'in') {
    const values = (draft.values ?? []).map((entry) => entry.trim()).filter(Boolean)
    if (values.length === 0) return { error: 'Add at least one value.' }
    return {
      filter: {
        fieldId: field.id,
        operator: 'in',
        value: values,
        label: `${field.label} is one of ${values.join(', ')}`,
      },
    }
  }
  if (operator === 'between') {
    const from = (draft.from ?? '').trim()
    const to = (draft.to ?? '').trim()
    if (!from || !to) return { error: 'Enter both a From and To value.' }
    if (compareValues(from, to, field) > 0) return { error: 'From must not be after To.' }
    return {
      filter: {
        fieldId: field.id,
        operator: 'between',
        value: [from, to],
        label: `${field.label} between ${from} and ${to}`,
      },
    }
  }
  const value = (draft.value ?? '').trim()
  if (!value) return { error: 'Enter a value.' }
  return { filter: { fieldId: field.id, operator: 'eq', value, label: `${field.label} = ${value}` } }
}

/**
 * When the operator changes, carry over what makes sense so users do not retype:
 * the first available scalar seeds the new shape (eq/from → the `in` list, etc.).
 */
export function migrateDraft(next: FilterOperator, draft: FilterDraft): FilterDraft {
  const firstScalar = draft.value || draft.values?.[0] || draft.from || ''
  if (next === 'in') {
    const values = draft.values && draft.values.length ? draft.values : firstScalar ? [firstScalar] : []
    return { values }
  }
  if (next === 'between') {
    return { from: draft.from || firstScalar, to: draft.to ?? '' }
  }
  return { value: firstScalar }
}

/** Reconstruct the editable draft from an existing persisted filter (chip edit). */
export function draftFromFilter(filter: QueryFilter): { operator: FilterOperator; draft: FilterDraft } {
  const toStr = (v: unknown) => (v == null ? '' : String(v))
  if (filter.operator === 'in') {
    const values = Array.isArray(filter.value)
      ? filter.value.map(toStr)
      : filter.value != null
        ? [toStr(filter.value)]
        : []
    return { operator: 'in', draft: { values } }
  }
  if (filter.operator === 'between') {
    const [from, to] = Array.isArray(filter.value) ? filter.value : [filter.value, null]
    return { operator: 'between', draft: { from: toStr(from), to: toStr(to) } }
  }
  return {
    operator: 'eq',
    draft: { value: Array.isArray(filter.value) ? toStr(filter.value[0]) : toStr(filter.value) },
  }
}
