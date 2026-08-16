import { afterEach, describe, expect, it, vi } from 'vitest'
import { announce, useAnnouncerState } from './useAnnouncer'

// The global announcer is the single authoritative screen-reader path for
// toasts (CERT-P2-004). These lock in its politeness routing and re-announce
// behavior without depending on a real animation frame.
describe('useAnnouncer (authoritative announcement path)', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('routes polite and assertive messages to their own regions', () => {
    vi.stubGlobal('requestAnimationFrame', (cb: FrameRequestCallback) => {
      cb(0)
      return 0
    })
    const { politeMessage, assertiveMessage } = useAnnouncerState()
    announce('Dataset saved. Your changes were saved.', 'polite')
    expect(politeMessage.value).toBe('Dataset saved. Your changes were saved.')

    announce('Save failed. Try again.', 'assertive')
    expect(assertiveMessage.value).toBe('Save failed. Try again.')
  })

  it('re-announces a repeated identical message by clearing then setting', () => {
    const frames: FrameRequestCallback[] = []
    vi.stubGlobal('requestAnimationFrame', (cb: FrameRequestCallback) => frames.push(cb))
    const { politeMessage } = useAnnouncerState()

    announce('Copied', 'polite')
    expect(politeMessage.value).toBe('') // cleared synchronously so SR re-reads it
    frames.forEach((cb) => cb(0))
    expect(politeMessage.value).toBe('Copied')

    announce('Copied', 'polite') // same text again
    expect(politeMessage.value).toBe('')
    frames.forEach((cb) => cb(0))
    expect(politeMessage.value).toBe('Copied')
  })
})
