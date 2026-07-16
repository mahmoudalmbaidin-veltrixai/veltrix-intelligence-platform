/**
 * Insights domain models. Insights are generated findings over semantic models.
 * In development they are simulated and clearly labelled as such.
 */

export type InsightKind =
  | 'trend'
  | 'variance'
  | 'anomaly'
  | 'top-increase'
  | 'top-decrease'
  | 'target-variance'
  | 'period-comparison'
  | 'contribution'
  | 'key-driver'

export type InsightSentiment = 'positive' | 'negative' | 'neutral'

export interface InsightMetricPoint {
  label: string
  value: number
}

export interface Insight {
  id: string
  kind: InsightKind
  title: string
  finding: string
  sentiment: InsightSentiment
  modelId: string
  metricLabel: string
  metricValue: number
  metricFormat: 'plain' | 'currency' | 'percent' | 'compact'
  comparisonLabel: string
  changePct: number
  confidence: number // 0..1
  freshness: string
  series?: InsightMetricPoint[]
  breakdownDimension?: string
  recommendedAction?: string
  relatedVisual?: string
  simulated: boolean
  pinned: boolean
  saved: boolean
}

export interface SuggestedQuestion {
  id: string
  text: string
}
