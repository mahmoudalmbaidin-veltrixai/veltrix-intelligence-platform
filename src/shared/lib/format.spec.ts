import { describe, it, expect } from 'vitest'
import { formatNumber, formatPct, formatDuration } from './format'

describe('format helpers', () => {
  it('formats currency', () => {
    expect(formatNumber(1500, { style: 'currency', currency: 'USD', decimals: 0 })).toBe('$1,500')
  })
  it('formats compact numbers', () => {
    expect(formatNumber(1_200_000, { style: 'compact' })).toBe('1.2M')
  })
  it('returns an em dash for nullish', () => {
    expect(formatNumber(null)).toBe('—')
    expect(formatNumber(undefined)).toBe('—')
  })
  it('adds a sign to percentages', () => {
    expect(formatPct(12.4)).toBe('+12.4%')
    expect(formatPct(-3)).toBe('-3.0%')
  })
  it('formats durations', () => {
    expect(formatDuration(500)).toBe('500ms')
    expect(formatDuration(2500)).toBe('2.5s')
    expect(formatDuration(90_000)).toBe('1m 30s')
    expect(formatDuration(undefined)).toBe('—')
  })
})
