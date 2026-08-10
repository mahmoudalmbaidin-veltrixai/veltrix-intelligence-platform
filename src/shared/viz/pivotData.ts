import type { DashboardWidget } from '@/shared/types/dashboard'
import type { CellValue, QueryColumn, QueryResult } from '@/shared/types/semantic'

/** Build the same stable Pivot matrix used by PDF/PNG rendering. */
export function toPivotTable(widget: DashboardWidget, result: QueryResult): QueryResult {
  const dimensionKeys = Array.from(
    new Set([
      ...(widget.wells.xAxis ?? []),
      ...(widget.wells.category ?? []),
      ...(widget.wells.legend ?? []),
      ...(widget.wells.series ?? []),
    ]),
  )
  const metricKeys = (widget.wells.values ?? []).map((value) => value.fieldId)
  if (dimensionKeys.length < 2 || !metricKeys.length) return result

  const rowKeys = dimensionKeys.slice(0, -1)
  const columnKey = dimensionKeys[dimensionKeys.length - 1]!
  const byKey = new Map(result.columns.map((column) => [column.key, column]))
  const rowTuples = stableTuples(result.rows, rowKeys)
  const columnValues = stableTuples(result.rows, [columnKey]).map(([value]) => value)
  const source = new Map(
    result.rows.map((row) => [JSON.stringify([...rowKeys.map((key) => row[key]), row[columnKey]]), row]),
  )

  const columns: QueryColumn[] = rowKeys.map(
    (key) => byKey.get(key) ?? { key, label: key, role: 'dimension', dataType: 'string' },
  )
  columnValues.forEach((columnValue, columnIndex) => {
    metricKeys.forEach((metricKey, metricIndex) => {
      const metric = byKey.get(metricKey)
      const label =
        metricKeys.length === 1
          ? String(columnValue ?? '—')
          : `${String(columnValue ?? '—')} · ${metric?.label ?? metricKey}`
      columns.push({
        key: `__pivot_value_${columnIndex * metricKeys.length + metricIndex}`,
        label,
        role: 'metric',
        dataType: metric?.dataType ?? 'number',
        format: metric?.format,
      })
    })
  })

  const rows = rowTuples.map((rowTuple) => {
    const row: Record<string, CellValue> = Object.fromEntries(rowKeys.map((key, index) => [key, rowTuple[index]]))
    columnValues.forEach((columnValue, columnIndex) => {
      const item = source.get(JSON.stringify([...rowTuple, columnValue]))
      metricKeys.forEach((metricKey, metricIndex) => {
        row[`__pivot_value_${columnIndex * metricKeys.length + metricIndex}`] = item?.[metricKey] ?? null
      })
    })
    return row
  })

  return { ...result, columns, rows, totalRows: rows.length }
}

function stableTuples(rows: QueryResult['rows'], fields: string[]): CellValue[][] {
  const seen = new Set<string>()
  const tuples: CellValue[][] = []
  rows.forEach((row) => {
    const tuple = fields.map((field) => row[field] ?? null)
    const key = JSON.stringify(tuple)
    if (!seen.has(key)) {
      seen.add(key)
      tuples.push(tuple)
    }
  })
  return tuples
}
