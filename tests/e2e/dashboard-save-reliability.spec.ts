import { expect, test } from './fixtures'

test.describe('dashboard save reliability', () => {
  // Authentication, tenant bootstrap, the scenario, and Playwright video
  // teardown all share the test budget. Trace evidence showed Firefox can spend
  // ~25 seconds in real authentication alone; this bound covers that measured
  // path without changing any product/network timeout.
  test.setTimeout(45_000)

  test('Firefox first save is single-flight and adopts the stable route', async ({ authenticatedPage: page }) => {
    await page.addInitScript(() => {
      const target = window as typeof window & { __vipDashboardSaveTrace?: unknown[] }
      target.__vipDashboardSaveTrace = []
      window.addEventListener('vip:dashboard-save', (event) => {
        target.__vipDashboardSaveTrace?.push((event as CustomEvent).detail)
      })
    })

    const writes: string[] = []
    page.on('request', (request) => {
      if (
        ['POST', 'PUT'].includes(request.method()) &&
        /\/api\/v1\/dashboards(?:$|\/[0-9a-f-]+\/editor$)/i.test(new URL(request.url()).pathname)
      ) {
        writes.push(`${request.method()} ${new URL(request.url()).pathname}`)
      }
    })

    await page.goto('/dashboards/new')
    const name = `Firefox save reliability ${Date.now()}`
    await page.getByLabel('Dashboard name').fill(name)

    // Deliberately race two user save gestures. The UI must join the existing
    // lifecycle rather than creating a second dashboard/version transaction.
    await page.getByLabel('Dashboard name').evaluate((input) => {
      for (let attempt = 0; attempt < 2; attempt += 1) {
        input.dispatchEvent(new KeyboardEvent('keydown', { key: 's', ctrlKey: true, bubbles: true }))
      }
    })

    await expect(page).toHaveURL(/\/dashboards\/[0-9a-f-]+\/edit$/i, { timeout: 10_000 })
    await expect(page.getByText('Saved just now')).toBeVisible()

    expect(writes.filter((request) => request.startsWith('POST '))).toHaveLength(1)
    expect(writes.filter((request) => request.startsWith('PUT '))).toHaveLength(1)

    const phases = await page.evaluate(() => {
      const target = window as typeof window & { __vipDashboardSaveTrace?: Array<{ phase?: string }> }
      return target.__vipDashboardSaveTrace?.map((event) => event.phase) ?? []
    })
    expect(phases).toContain('started')
    expect(phases).toContain('joined')
    expect(phases).toContain('persisted')
    expect(phases).toContain('navigated')
    expect(phases).not.toContain('failed')
  })
})
