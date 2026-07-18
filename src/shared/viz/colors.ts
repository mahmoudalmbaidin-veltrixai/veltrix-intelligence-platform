/** Categorical + sequential palettes for data viz, theme-independent. */
export const VIZ_CATEGORICAL = [
  '#6d5efc',
  '#22c1a6',
  '#f2a93b',
  '#e2607a',
  '#4aa3ff',
  '#b06cf0',
  '#4fbf67',
  '#f0725a',
  '#5ac8d8',
  '#d4a24e',
]

export function seriesColor(i: number): string {
  return VIZ_CATEGORICAL[i % VIZ_CATEGORICAL.length]
}

export const COLOR_SCHEMES: Record<string, string[]> = {
  default: VIZ_CATEGORICAL,
  cool: ['#6d5efc', '#4aa3ff', '#22c1a6', '#5ac8d8', '#b06cf0'],
  warm: ['#f2a93b', '#f0725a', '#e2607a', '#d4a24e', '#b06cf0'],
  status: ['#3fb96b', '#e0a52e', '#e5544b', '#4aa3ff'],
}

export function schemeColor(scheme: string | undefined, i: number): string {
  const s = COLOR_SCHEMES[scheme ?? 'default'] ?? VIZ_CATEGORICAL
  return s[i % s.length]
}
