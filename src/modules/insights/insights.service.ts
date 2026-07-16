/**
 * Insights service (mock, clearly simulated in dev).
 *
 * INTEGRATION POINT
 *   GET  /api/v1/insights?modelId=...      -> Insight[]
 *   POST /api/v1/insights/explain          -> Insight (NL query -> generated finding)
 *   POST /api/v1/insights/:id/pin          -> pin to dashboard
 *   permission: insight:read / insight:write
 *
 * All findings are synthesised over the mock semantic engine and MUST be
 * labelled as simulated in development (see `simulated: true`).
 */
import type { Insight, InsightKind, SuggestedQuestion } from '@/shared/types/insight'
import { latency, isoAgo, rng } from '@/shared/lib/mock'

function series(n: number, up = true): { label: string; value: number }[] {
  const out: { label: string; value: number }[] = []
  let v = 100 + rng() * 40
  for (let i = 0; i < n; i++) {
    v += (up ? 1 : -1) * (rng() * 18 - 4)
    out.push({ label: `P${i + 1}`, value: Math.max(10, Math.round(v)) })
  }
  return out
}

const SEED: Insight[] = [
  {
    id: 'in_1', kind: 'trend', title: 'Revenue is trending up', sentiment: 'positive',
    finding: 'Revenue grew steadily over the last 6 months, up 18.4% versus the prior period, driven mainly by the Enterprise segment in EMEA.',
    modelId: 'sm_sales', metricLabel: 'Revenue', metricValue: 4_820_000, metricFormat: 'currency',
    comparisonLabel: 'vs previous 6 months', changePct: 18.4, confidence: 0.92, freshness: isoAgo(35),
    series: series(6, true), breakdownDimension: 'segment', recommendedAction: 'Increase EMEA Enterprise capacity to sustain momentum.',
    relatedVisual: 'line', simulated: true, pinned: false, saved: false,
  },
  {
    id: 'in_2', kind: 'anomaly', title: 'Unusual drop in APAC orders', sentiment: 'negative',
    finding: 'APAC orders fell 27% in the last week — 3.1σ below the expected range. This coincides with the Self-Serve channel outage on the 4th.',
    modelId: 'sm_sales', metricLabel: 'Orders', metricValue: 1_240, metricFormat: 'compact',
    comparisonLabel: 'vs 8-week baseline', changePct: -27, confidence: 0.81, freshness: isoAgo(120),
    series: series(8, false), breakdownDimension: 'channel', recommendedAction: 'Confirm Self-Serve checkout recovery in APAC.',
    relatedVisual: 'column', simulated: true, pinned: false, saved: false,
  },
  {
    id: 'in_3', kind: 'target-variance', title: 'Margin below target', sentiment: 'negative',
    finding: 'Margin is 24.1% against a 27% target — a 2.9pt shortfall. Hardware discounting in Americas is the largest contributor.',
    modelId: 'sm_sales', metricLabel: 'Margin %', metricValue: 0.241, metricFormat: 'percent',
    comparisonLabel: 'vs 27% target', changePct: -10.7, confidence: 0.88, freshness: isoAgo(60),
    breakdownDimension: 'category', recommendedAction: 'Review Americas Hardware discount policy.',
    relatedVisual: 'gauge', simulated: true, pinned: false, saved: false,
  },
  {
    id: 'in_4', kind: 'top-increase', title: 'Software is the top growth category', sentiment: 'positive',
    finding: 'Software contributed 46% of revenue growth this quarter, adding $612K — more than the next two categories combined.',
    modelId: 'sm_sales', metricLabel: 'Revenue growth', metricValue: 612_000, metricFormat: 'currency',
    comparisonLabel: 'quarter over quarter', changePct: 46, confidence: 0.9, freshness: isoAgo(45),
    series: series(4, true), breakdownDimension: 'category', recommendedAction: 'Prioritise Software pipeline in Q4 planning.',
    relatedVisual: 'bar', simulated: true, pinned: false, saved: false,
  },
  {
    id: 'in_5', kind: 'period-comparison', title: 'Partner channel outpacing Direct', sentiment: 'neutral',
    finding: 'Partner revenue grew 22% while Direct grew 6% period-over-period. Partner now accounts for 38% of total revenue, up from 33%.',
    modelId: 'sm_sales', metricLabel: 'Partner revenue', metricValue: 1_830_000, metricFormat: 'currency',
    comparisonLabel: 'vs previous period', changePct: 22, confidence: 0.85, freshness: isoAgo(90),
    series: series(6, true), breakdownDimension: 'channel', recommendedAction: 'Assess partner enablement investment.',
    relatedVisual: 'area', simulated: true, pinned: false, saved: false,
  },
  {
    id: 'in_6', kind: 'contribution', title: 'EMEA drives half of profit', sentiment: 'positive',
    finding: 'EMEA contributes 51% of total profit despite being 43% of revenue, reflecting a higher-margin product mix.',
    modelId: 'sm_sales', metricLabel: 'Profit contribution', metricValue: 0.51, metricFormat: 'percent',
    comparisonLabel: 'share of total profit', changePct: 8, confidence: 0.87, freshness: isoAgo(150),
    breakdownDimension: 'region', recommendedAction: 'Replicate EMEA product mix in other regions.',
    relatedVisual: 'donut', simulated: true, pinned: false, saved: false,
  },
]

export const SUGGESTED_QUESTIONS: SuggestedQuestion[] = [
  { id: 'q1', text: 'Why did revenue change last quarter?' },
  { id: 'q2', text: 'Which region has the highest margin?' },
  { id: 'q3', text: 'What is driving the drop in APAC orders?' },
  { id: 'q4', text: 'Show top 5 categories by profit' },
  { id: 'q5', text: 'Compare Partner vs Direct channel this year' },
]

export const insightsService = {
  async list(modelId?: string): Promise<Insight[]> {
    await latency(200, 500)
    return SEED.filter((i) => !modelId || i.modelId === modelId).map((i) => ({ ...i }))
  },
  /** Simulate a natural-language query → generated insight. */
  async explain(question: string): Promise<Insight> {
    await latency(500, 1100)
    const kinds: InsightKind[] = ['trend', 'variance', 'key-driver', 'period-comparison']
    const kind = kinds[Math.floor(rng() * kinds.length)]
    const change = Math.round((rng() * 30 - 8) * 10) / 10
    return {
      id: `in_gen_${Date.now().toString(36)}`,
      kind,
      title: question.length > 60 ? question.slice(0, 57) + '…' : question,
      sentiment: change >= 0 ? 'positive' : 'negative',
      finding: `Based on the Sales Analytics model, "${question}" resolves to a ${change >= 0 ? 'positive' : 'negative'} movement of ${Math.abs(change)}% versus the comparison period. The largest contributor is the Enterprise segment. This is a generated, simulated answer for development.`,
      modelId: 'sm_sales', metricLabel: 'Revenue', metricValue: Math.round(3_000_000 + rng() * 2_000_000), metricFormat: 'currency',
      comparisonLabel: 'vs previous period', changePct: change, confidence: 0.6 + rng() * 0.3, freshness: new Date().toISOString(),
      series: series(6, change >= 0), breakdownDimension: 'segment', recommendedAction: 'Explore the breakdown to validate the driver.',
      relatedVisual: 'line', simulated: true, pinned: false, saved: false,
    }
  },
}
