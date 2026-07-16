/** Locale-aware value formatting used across analytics + tables. */
import type { NumberFormat } from '@/shared/types/semantic'

export function formatNumber(
  value: number | null | undefined,
  fmt: Partial<NumberFormat> = {},
): string {
  if (value == null || Number.isNaN(value)) return '—'
  const decimals = fmt.decimals ?? (Number.isInteger(value) ? 0 : 1)
  switch (fmt.style) {
    case 'currency':
      return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: fmt.currency ?? 'USD',
        maximumFractionDigits: decimals,
        minimumFractionDigits: decimals,
      }).format(value)
    case 'percent':
      return `${(value * (Math.abs(value) <= 1 ? 100 : 1)).toFixed(decimals)}%`
    case 'compact':
      return new Intl.NumberFormat('en-US', {
        notation: 'compact',
        maximumFractionDigits: 1,
      }).format(value)
    default: {
      const s = new Intl.NumberFormat('en-US', {
        maximumFractionDigits: decimals,
        minimumFractionDigits: decimals,
      }).format(value)
      return `${fmt.prefix ?? ''}${s}${fmt.suffix ?? ''}`
    }
  }
}

export function formatCompact(value: number): string {
  return new Intl.NumberFormat('en-US', { notation: 'compact', maximumFractionDigits: 1 }).format(value)
}

export function formatPct(value: number, decimals = 1): string {
  const sign = value > 0 ? '+' : ''
  return `${sign}${value.toFixed(decimals)}%`
}

export function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const abs = Math.abs(diff)
  const future = diff < 0
  const mins = Math.round(abs / 60_000)
  if (mins < 1) return 'just now'
  if (mins < 60) return future ? `in ${mins}m` : `${mins}m ago`
  const hrs = Math.round(mins / 60)
  if (hrs < 24) return future ? `in ${hrs}h` : `${hrs}h ago`
  const days = Math.round(hrs / 24)
  if (days < 30) return future ? `in ${days}d` : `${days}d ago`
  const months = Math.round(days / 30)
  return future ? `in ${months}mo` : `${months}mo ago`
}

export function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function formatDuration(ms: number | undefined): string {
  if (ms == null) return '—'
  if (ms < 1000) return `${ms}ms`
  const s = ms / 1000
  if (s < 60) return `${s.toFixed(1)}s`
  const m = Math.floor(s / 60)
  const rem = Math.round(s % 60)
  return `${m}m ${rem}s`
}
