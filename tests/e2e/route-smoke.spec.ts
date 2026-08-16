import { test, expect } from './fixtures'
import type { Page } from '@playwright/test'

const routes = [
  '/',
  '/home',
  '/platform',
  '/favorites',
  '/activity',
  '/connections',
  '/connections/catalog',
  '/connections/new',
  '/pipelines',
  '/pipelines/new',
  '/datasets',
  '/datasets/quality',
  '/datasets/lineage',
  '/semantic',
  '/semantic/metrics',
  '/semantic/glossary',
  '/dashboards',
  '/dashboards/templates',
  '/dashboards/published',
  '/dashboards/deliveries',
  '/dashboards/new',
  '/notifications',
  '/operations/activity',
  '/audit',
  '/usage',
  '/admin/organization',
  '/admin/workspace',
  '/admin/members',
  '/admin/feature-flags',
  '/admin/governance',
  '/settings/profile',
  '/settings/security',
  '/forbidden',
  '/upgrade',
  '/definitely-not-a-route',
] as const

const featureGatedRoutes = ['/ai/assistant', '/ai/studio', '/ai/knowledge', '/ai/agents', '/ai/agent-runs'] as const

// Placeholder modules with no production backend remain entitlement-gated.
// AI routes use the stricter production-live-mode gate above and cannot be
// enabled by combining a tenant feature flag with an entitlement.
const entitlementGatedRoutes = [
  '/reports',
  '/reports/new',
  '/reports/deliveries',
  '/insights',
  '/marketplace',
  '/marketplace/ext_snowflake',
  '/billing',
  '/developer',
  '/settings/developer',
  '/automation',
  '/automation/new',
  '/automation/runs',
  '/automation/approvals',
  '/automation/00000000-0000-0000-0000-000000000000',
] as const

async function waitForApplicationReady(page: Page, route: string): Promise<void> {
  const expectedPath = route === '/' ? '/home' : route
  await expect(page).toHaveURL(new RegExp(`${expectedPath.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}$`))
  const main = page.locator('#vip-main')
  await expect(main, `${route} should render inside the application layout`).toBeVisible()
  await expect(main, `${route} should render an intentional nonblank surface`).not.toBeEmpty()
  await expect
    .poll(
      () =>
        page.evaluate(() => ({
          route: document.documentElement.dataset.vipRoute,
          active:
            (window as typeof window & { __vipQueryActivity?: { active: number } }).__vipQueryActivity?.active ?? 0,
        })),
      { message: `${route} should settle its route and server-state queries` },
    )
    .toEqual({ route: expectedPath, active: 0 })
}

async function expectFailClosed404(page: Page, route: string): Promise<void> {
  await page.goto(route)
  await expect(page.getByRole('heading', { name: /page not found/i })).toBeVisible()
  await expect(page).toHaveURL(/\/not-found$/)
  await expect(page).not.toHaveURL(/\/upgrade/)
  await expect(page.locator('#vip-main')).toBeVisible()
  await expect(page.locator('#vip-main')).not.toBeEmpty()
}

test('disabled AI preview routes fail closed to 404, never /upgrade', async ({ authenticatedPage: page }) => {
  test.setTimeout(120_000)
  for (const route of featureGatedRoutes) {
    await expectFailClosed404(page, route)
  }
})

test('placeholder modules fail closed to 404 and never render their surface', async ({ authenticatedPage: page }) => {
  test.setTimeout(120_000)
  // Deferred V1 modules are production-gated: hidden from navigation and blocked
  // on direct URL. The fail-closed wall is 404/not-found, not a paywall at /upgrade.
  for (const route of [...entitlementGatedRoutes, '/explore'] as const) {
    await expectFailClosed404(page, route)
  }
})

test('all router destinations render an intentional nonblank surface without runtime or network errors', async ({
  authenticatedPage: page,
}) => {
  test.setTimeout(120_000)
  await waitForApplicationReady(page, '/home')
  const consoleErrors: string[] = []
  const pendingConsoleErrors: Array<Promise<void>> = []
  const networkFailures: string[] = []
  const failedResponses: string[] = []
  page.on('console', (message) => {
    if (message.type() !== 'error') return
    pendingConsoleErrors.push(
      Promise.all(
        message.args().map(async (argument) => {
          try {
            return JSON.stringify(await argument.jsonValue())
          } catch {
            return argument.toString()
          }
        }),
      ).then((values) => {
        const location = message.location()
        consoleErrors.push(`${values.join(' ')} (${location.url}:${location.lineNumber}:${location.columnNumber})`)
      }),
    )
  })
  page.on('requestfailed', (request) => {
    // A route transition can cancel an in-flight read from the surface being left.
    const failure = request.failure()?.errorText ?? 'unknown'
    if (failure !== 'net::ERR_ABORTED' && !request.url().includes('/api/v1/') && !request.url().includes('/auth/')) {
      networkFailures.push(`${failure} ${request.method()} ${request.url()}`)
    }
  })
  page.on('response', (response) => {
    if (response.status() >= 400)
      failedResponses.push(`${response.status()} ${response.request().method()} ${response.url()}`)
  })

  const liveDetails = await page.evaluate(async () => {
    const tenant = JSON.parse(localStorage.getItem('vip.tenancy.preference') ?? '{}') as {
      orgId?: string
      wsId?: string
    }
    const headers = {
      'X-Organization-ID': tenant.orgId ?? '',
      'X-Workspace-ID': tenant.wsId ?? '',
    }
    const read = async (path: string) => {
      const response = await fetch(`http://localhost:8000/api/v1${path}`, { credentials: 'include', headers })
      return response.ok ? response.json() : null
    }
    const [connections, datasets, models, dashboards] = await Promise.all([
      read('/connections?page_size=1'),
      read('/datasets?page_size=1'),
      read('/semantic-models'),
      read('/dashboards?limit=1'),
    ])
    const modelItems = Array.isArray(models) ? models : Array.isArray(models?.items) ? models.items : []
    const dashboardId = dashboards?.items?.[0]?.id ?? dashboards?.[0]?.id
    return [
      connections?.items?.[0]?.id ? `/connections/${connections.items[0].id}` : null,
      datasets?.items?.[0]?.id ? `/datasets/${datasets.items[0].id}` : null,
      modelItems[0]?.id ? `/semantic/${modelItems[0].id}` : null,
      dashboardId ? `/dashboards/${dashboardId}/edit` : null,
    ].filter((value): value is string => Boolean(value))
  })
  const routesToVisit = [...routes, ...liveDetails]
  const blankRoutes: string[] = []
  const badTitles: string[] = []
  let previousRoute = ''
  for (const route of routesToVisit) {
    if (previousRoute === '/pipelines/new') {
      // Pipeline Studio persists its initialized draft while it is unmounting.
      // A document navigation cancels that completed route transition before
      // continuing the SPA-only smoke sequence.
      await page.goto(route)
    } else {
      await page.evaluate((path) => {
        window.history.pushState({}, '', path)
        window.dispatchEvent(new PopStateEvent('popstate'))
      }, route)
    }
    await waitForApplicationReady(page, route)
    const main = page.locator('#vip-main')
    const text = (await main.textContent())?.trim() ?? ''
    if (!text) blankRoutes.push(route)
    const title = await page.title()
    if (!title.includes('VIP') || title.includes('undefined')) badTitles.push(`${route}: ${title}`)
    previousRoute = route
  }

  expect(blankRoutes, 'blank route surfaces').toEqual([])
  expect(badTitles, 'invalid route titles').toEqual([])
  expect(failedResponses, 'unsuccessful route-transition responses').toEqual([])
  await Promise.all(pendingConsoleErrors)
  expect(consoleErrors, 'browser console errors').toEqual([])
  expect(networkFailures, 'failed route-transition requests').toEqual([])
})
