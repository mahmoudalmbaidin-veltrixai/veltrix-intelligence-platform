/** Shapes a QueryResult into series structures the chart SFCs consume. */
import type { QueryResult } from '@/shared/types/semantic'

export interface Series {
  name: string
  key: string
  points: number[]
}
export interface CartesianData {
  categories: string[]
  series: Series[]
  measureFormat?: QueryResult['columns'][number]['format']
}

export function toCartesian(result: QueryResult): CartesianData {
  const dimCols = result.columns.filter((c) => c.role === 'dimension' || c.role === 'time')
  const measCols = result.columns.filter((c) => c.role === 'measure' || c.role === 'metric')
  const catCol = dimCols[0]
  const seriesCol = dimCols[1]

  if (!catCol) {
    // single-row: one category "Total"
    return {
      categories: ['Total'],
      series: measCols.map((m) => ({ name: m.label, key: m.key, points: [Number(result.rows[0]?.[m.key] ?? 0)] })),
      measureFormat: measCols[0]?.format,
    }
  }

  const categories = [...new Set(result.rows.map((r) => String(r[catCol.key])))]

  if (seriesCol && measCols[0]) {
    const seriesNames = [...new Set(result.rows.map((r) => String(r[seriesCol.key])))]
    const m = measCols[0]
    return {
      categories,
      measureFormat: m.format,
      series: seriesNames.map((sn) => ({
        name: sn,
        key: sn,
        points: categories.map((cat) => {
          const row = result.rows.find((r) => String(r[catCol.key]) === cat && String(r[seriesCol.key]) === sn)
          return Number(row?.[m.key] ?? 0)
        }),
      })),
    }
  }

  // one series per measure
  return {
    categories,
    measureFormat: measCols[0]?.format,
    series: measCols.map((m) => ({
      name: m.label,
      key: m.key,
      points: categories.map((cat) => {
        const row = result.rows.find((r) => String(r[catCol.key]) === cat)
        return Number(row?.[m.key] ?? 0)
      }),
    })),
  }
}

export interface Slice {
  label: string
  value: number
}
export function toPie(result: QueryResult): { slices: Slice[]; format: QueryResult['columns'][number]['format'] } {
  const dimCol = result.columns.find((c) => c.role === 'dimension' || c.role === 'time')
  const measCol = result.columns.find((c) => c.role === 'measure' || c.role === 'metric')
  if (!dimCol || !measCol) return { slices: [], format: measCol?.format }
  const map = new Map<string, number>()
  result.rows.forEach((r) => {
    const k = String(r[dimCol.key])
    map.set(k, (map.get(k) ?? 0) + Number(r[measCol.key] ?? 0))
  })
  return { slices: [...map.entries()].map(([label, value]) => ({ label, value })), format: measCol.format }
}
