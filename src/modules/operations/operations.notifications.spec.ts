import { describe, expect, it } from 'vitest'
import { operationsService } from './operations.service'

// Test env runs in mock mode (VITE_API_MODE=mock), so operationsService is the
// stateful mock adapter. These assert the read/unread/count semantics the UI
// relies on; the live adapter is validated by the backend integration tests.
describe('operations notification read state', () => {
  it('reports an unread count and mutates it on mark/unmark', async () => {
    const items = await operationsService.listNotifications()
    const unread = items.filter((n) => !n.read)
    const start = await operationsService.unreadNotificationCount()
    expect(start).toBe(unread.length)
    expect(start).toBeGreaterThan(0)

    const target = unread[0]
    const afterRead = await operationsService.markNotificationRead(target.id)
    expect(afterRead).toBe(start - 1)

    const afterUnread = await operationsService.markNotificationUnread(target.id)
    expect(afterUnread).toBe(start)
  })

  it('mark all as read drives the count to zero', async () => {
    const zero = await operationsService.markAllNotificationsRead()
    expect(zero).toBe(0)
    expect(await operationsService.unreadNotificationCount()).toBe(0)
  })
})
