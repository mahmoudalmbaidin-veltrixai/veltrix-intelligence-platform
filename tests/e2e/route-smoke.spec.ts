import { test, expect } from './fixtures'

const routes = [
  '/',
  '/home',
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
  '/insights',
  '/explore',
  '/reports',
  '/reports/new',
  '/reports/deliveries',
  '/automation',
  '/automation/new',
  '/automation/runs',
  '/automation/approvals',
  '/automation/au_1',
  '/notifications',
  '/operations/activity',
  '/audit',
  '/usage',
  '/marketplace',
  '/marketplace/ext_snowflake',
  '/developer',
  '/admin/platform',
  '/admin/organization',
  '/admin/workspace',
  '/admin/members',
  '/admin/feature-flags',
  '/admin/governance',
  '/billing',
  '/settings/personal',
  '/settings/workspace',
  '/settings/organization',
  '/settings/developer',
  '/settings/security',
  '/forbidden',
  '/upgrade',
  '/definitely-not-a-route',
] as const

const featureGatedRoutes = ['/ai/assistant', '/ai/studio', '/ai/knowledge', '/ai/agents', '/ai/agent-runs'] as const

test('disabled AI preview routes remain inaccessible in production navigation', async ({ authenticatedPage: page }) => {
  for (const route of featureGatedRoutes) {
    await page.goto(route)
    await expect.poll(() => new URL(page.url()).pathname).not.toBe(route)
    await expect(page).toHaveURL(/\/(?:upgrade\?.*|)$/)
  }
})

test('all router destinations render an intentional nonblank surface without runtime or network errors', async ({
  authenticatedPage: page,
}) => {
  test.setTimeout(120_000)
  await page.waitForTimeout(250)
  const consoleErrors: string[] = []
  const networkFailures: string[] = []
  const failedResponses: string[] = []
  page.on('console', (message) => {
    if (message.type() === 'error') consoleErrors.push(message.text())
  })
  page.on('requestfailed', (request) => {
    // A route transition can cancel an in-flight read from the surface being left.
    const failure = request.failure()?.errorText ?? 'unknown'
    if (
      failure !== 'net::ERR_ABORTED' &&
      !request.url().includes('/api/v1/') &&
      !request.url().includes('/auth/')
    ) {
      networkFailures.push(`${failure} ${request.method()} ${request.url()}`)
    }
  })
  page.on('response', (response) => {
    if (response.status() >= 400) failedResponses.push(`${response.status()} ${response.request().method()} ${response.url()}`)
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
    return [
      connections?.items?.[0]?.id ? `/connections/${connections.items[0].id}` : null,
      datasets?.items?.[0]?.id ? `/datasets/${datasets.items[0].id}` : null,
      models?.[0]?.id ? `/semantic/${models[0].id}` : null,
      dashboards?.[0]?.id ? `/dashboards/${dashboards[0].id}/edit` : null,
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
    await expect(page).toHaveURL(route === '/' ? /\/home$/ : new RegExp(`${route.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}$`))
    await page.waitForTimeout(100)
    const main = page.locator('#vip-main')
    await expect(main, `${route} should render inside the application layout`).toBeVisible()
    await expect(main, `${route} should render an intentional nonblank surface`).not.toBeEmpty()
    const text = (await main.textContent())?.trim() ?? ''
    if (!text) blankRoutes.push(route)
    const title = await page.title()
    if (!title.includes('VIP') || title.includes('undefined')) badTitles.push(`${route}: ${title}`)
    previousRoute = route
  }

  expect(blankRoutes, 'blank route surfaces').toEqual([])
  expect(badTitles, 'invalid route titles').toEqual([])
  expect(failedResponses, 'unsuccessful route-transition responses').toEqual([])
  expect(consoleErrors, 'browser console errors').toEqual([])
  expect(networkFailures, 'failed route-transition requests').toEqual([])
})
