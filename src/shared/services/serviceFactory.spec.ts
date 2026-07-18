import { describe, it, expect } from 'vitest'
import { defineService } from './serviceFactory'
import { config } from '@/shared/config/env'

describe('service factory', () => {
  it('selects the mock adapter in mock mode (test env default)', () => {
    const mock = { tag: 'mock' }
    const live = { tag: 'live' }
    const chosen = defineService(mock, () => live)
    // Test env runs in mock mode.
    expect(config.apiMode).toBe('mock')
    expect(chosen).toBe(mock)
  })

  it('does not construct the live adapter in mock mode', () => {
    let constructed = false
    defineService({ tag: 'mock' }, () => {
      constructed = true
      return { tag: 'live' }
    })
    expect(constructed).toBe(false)
  })
})
