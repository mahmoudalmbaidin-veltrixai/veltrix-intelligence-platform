import fs from 'node:fs'
import path from 'node:path'
import { expect, resetClientState, signInAs, test } from './fixtures'
import { browserFixtures } from './personas'

test.setTimeout(120_000)

const csvPath = path.resolve('tests', 'e2e', 'data', 'b8_5_certification.csv')
const xlsxPath = path.resolve('tests', 'e2e', 'data', 'sales_certification.xlsx')

async function tenantHeaders(page: Parameters<typeof signInAs>[0]) {
  return page.evaluate(() => {
    const tenancy = JSON.parse(localStorage.getItem('vip.tenancy.preference') ?? '{}') as {
      orgId?: string
      wsId?: string
    }
    const csrf =
      document.cookie
        .split('; ')
        .find((item) => item.startsWith('vip_csrf_token='))
        ?.split('=')[1] ?? ''
    return {
      'Content-Type': 'application/json',
      'X-Organization-ID': tenancy.orgId ?? '',
      'X-Workspace-ID': tenancy.wsId ?? '',
      'X-CSRF-Token': decodeURIComponent(csrf),
    }
  })
}

async function api(
  page: Parameters<typeof signInAs>[0],
  method: string,
  url: string,
  body?: unknown,
): Promise<{ status: number; json: unknown }> {
  const headers = await tenantHeaders(page)
  return page.evaluate(
    async ({ method, url, headers, body }) => {
      const response = await fetch(url, {
        method,
        credentials: 'include',
        headers,
        body: body == null ? undefined : JSON.stringify(body),
      })
      const text = await response.text()
      let json: unknown = text
      try {
        json = text ? JSON.parse(text) : null
      } catch {
        json = text
      }
      return { status: response.status, json }
    },
    { method, url, headers, body },
  )
}

/** IANA labels are the zone id with underscores turned into spaces. "UTC" is not
 * guaranteed to appear in `Intl.supportedValuesOf('timeZone')`. */
async function chooseTimezone(page: Parameters<typeof signInAs>[0], query: string, option: RegExp): Promise<void> {
  const timezone = page.getByRole('combobox', { name: 'Time zone' })
  await expect(timezone).toBeVisible()
  await timezone.click()
  await timezone.fill(query)
  const match = page.getByRole('option', { name: option })
  await expect(match).toBeVisible({ timeout: 8_000 })
  await match.click()
  await page.keyboard.press('Escape')
}

test('CERT-P2-001 timezone combobox persists Asia/Riyadh across reload', async ({ authenticatedPage: page }) => {
  await page.goto('/settings/language')
  const timezone = page.getByRole('combobox', { name: 'Time zone' })
  await expect(timezone).toBeVisible()
  const current = await timezone.inputValue()
  if (/Asia\/Riyadh/.test(current)) {
    await chooseTimezone(page, 'London', /Europe\/London/)
    await page.getByRole('button', { name: 'Save changes' }).click()
    await expect(page.getByText('Your language and region settings were saved.', { exact: true })).toBeVisible()
  }
  await chooseTimezone(page, 'Riyadh', /Asia\/Riyadh/)
  await expect(timezone).toHaveValue(/Asia\/Riyadh/)
  await page.getByRole('button', { name: 'Save changes' }).click()
  await expect(page.getByText('Your language and region settings were saved.', { exact: true })).toBeVisible()
  await page.reload()
  await expect(page.getByRole('combobox', { name: 'Time zone' })).toHaveValue(/Asia\/Riyadh/)
})

test('CERT-P2-004 success toast has one visual region and one live announcement path', async ({
  authenticatedPage: page,
}) => {
  await page.goto('/notifications')
  await expect(page.getByText('Notification preferences')).toBeVisible()
  const billing = page.locator('.ntf__pref-row', { hasText: 'Billing' }).getByRole('switch')
  await billing.click()
  await page.getByRole('button', { name: 'Save preferences' }).click()
  const visual = page.getByRole('region', { name: 'Notifications' }).locator('.vip-toast')
  await expect(visual.filter({ hasText: 'Notification preferences saved' })).toHaveCount(1)
  await expect(page.getByRole('region', { name: 'Notifications' })).not.toHaveAttribute('aria-live', /./)
  await expect(page.locator('[aria-live="polite"]').filter({ hasText: 'Notification preferences saved' })).toHaveCount(
    1,
  )
})

test('CERT-P2-003 dataset catalog pager walks pages, page-size, and filter reset', async ({
  authenticatedPage: page,
}) => {
  await page.goto('/datasets')
  const count = page.locator('.dl__count')
  await expect(count).toBeVisible()
  await expect.poll(async () => ((await count.textContent()) ?? '').trim(), { timeout: 20_000 }).not.toBe('0 of 0')
  const summary = ((await count.textContent()) ?? '').trim()
  const total = Number(/of\s+(\d+)\s*$/.exec(summary)?.[1] ?? '0')
  expect(total, `catalog total from "${summary}"`).toBeGreaterThan(0)

  await page.getByLabel('Datasets per page').selectOption('25')
  const pageOf = page.locator('.dl__page-of')
  await expect(pageOf).toContainText('Page 1 of')
  const totalPages = Number(/Page 1 of (\d+)/.exec((await pageOf.textContent()) ?? '')?.[1] ?? '1')
  const next = page.getByRole('button', { name: 'Next page' })
  const previous = page.getByRole('button', { name: 'Previous page' })
  if (totalPages > 1) {
    await next.click()
    await expect(pageOf).toContainText('Page 2 of')
    await previous.click()
    await expect(pageOf).toContainText('Page 1 of')
    const walk = Math.min(totalPages, 8)
    for (let pageNumber = 1; pageNumber < walk; pageNumber += 1) {
      await expect(next).toBeEnabled()
      await next.click()
      await expect(pageOf).toContainText(`Page ${pageNumber + 1} of`)
    }
    if (walk === totalPages) {
      await expect(next).toBeDisabled()
      await expect(previous).toBeEnabled()
      await previous.click()
    }
  }

  await page.getByPlaceholder('Search dataset name or source').fill('__no_such_dataset__')
  await expect.poll(async () => (await count.textContent())?.trim(), { timeout: 15_000 }).toMatch(/^0 of 0$/)
  await page.getByPlaceholder('Search dataset name or source').fill('')
  await expect
    .poll(async () => (await count.textContent())?.trim(), { timeout: 15_000 })
    .toMatch(new RegExp(`of ${total}$`))
  await page.getByLabel('Dataset status').selectOption('active')
  await page.getByLabel('Dataset status').selectOption('all')
  await expect
    .poll(async () => (await count.textContent())?.trim(), { timeout: 15_000 })
    .toMatch(new RegExp(`of ${total}$`))
})

test('DATASET-P2-IMPORT-CONNECTION does not auto-pick the first of many connections', async ({
  authenticatedPage: page,
}) => {
  await page.goto('/datasets')
  await page.getByRole('button', { name: 'Import CSV' }).click()
  const dialog = page.getByRole('dialog', { name: 'Import CSV dataset' })
  await expect(dialog).toBeVisible()
  if (
    await dialog
      .getByText('No eligible connections available')
      .isVisible()
      .catch(() => false)
  ) {
    await expect(dialog.getByRole('button', { name: 'Import and catalog' })).toBeDisabled()
    return
  }
  const connection = dialog.getByLabel('Connection')
  await expect(connection).toBeVisible()
  const optionCount = await connection.locator('option:not([disabled])').count()
  const selected = await connection.inputValue()
  if (optionCount <= 1) {
    expect(selected.length).toBeGreaterThan(0)
  } else {
    expect(selected).toBe('')
    await expect(dialog.getByRole('button', { name: 'Import and catalog' })).toBeDisabled()
    const connectionB = connection.locator('option:not([disabled])').nth(1)
    const valueB = await connectionB.getAttribute('value')
    expect(valueB).toBeTruthy()
    await connection.selectOption(valueB!)
  }
  await dialog.getByLabel('Upload CSV or XLSX file from your device').setInputFiles(csvPath)
  await expect(dialog.getByText('b8_5_certification.csv')).toBeVisible()
  await dialog.getByLabel('Target table').fill(`qa_csv_${Date.now()}`)
  if (optionCount > 1) {
    const selectedId = await connection.inputValue()
    expect(selectedId).toBeTruthy()
    const ingest = page.waitForRequest(
      (request) => request.url().includes('/datasets/ingest-csv') && request.method() === 'POST',
    )
    await dialog.getByRole('button', { name: 'Import and catalog' }).click()
    const sent = await ingest
    expect((sent.postDataJSON() as { connection_id?: string }).connection_id).toBe(selectedId)
  }
})

test('DATASET-P2-IMPORT-CONNECTION XLSX uses the explicitly chosen connection', async ({ authenticatedPage: page }) => {
  test.skip(!fs.existsSync(xlsxPath), 'Committed XLSX fixture is required')
  await page.goto('/datasets')
  await page.getByRole('button', { name: 'Import CSV' }).click()
  const dialog = page.getByRole('dialog', { name: 'Import CSV dataset' })
  await expect(dialog).toBeVisible()
  const connection = dialog.getByLabel('Connection')
  await expect(connection).toBeVisible()
  const wanted = connection.locator('option').filter({ hasText: browserFixtures.destinationConnection })
  const value = await wanted.first().getAttribute('value')
  expect(value).toBeTruthy()
  await connection.selectOption(value!)
  await dialog.getByLabel('Upload CSV or XLSX file from your device').setInputFiles(xlsxPath)
  await expect(dialog.getByText('sales_certification.xlsx')).toBeVisible()
  await dialog.getByLabel('Target table').fill(`qa_xlsx_${Date.now()}`)
  await expect(dialog.getByRole('button', { name: 'Import and catalog' })).toBeEnabled()
  const ingest = page.waitForRequest(
    (request) => request.url().includes('/datasets/ingest-file') && request.method() === 'POST',
    { timeout: 30_000 },
  )
  await dialog.getByRole('button', { name: 'Import and catalog' }).click()
  const sent = await ingest
  const payload = sent.postDataJSON() as { connection_id?: string }
  expect(payload.connection_id).toBe(value)
})

test('CERT-P2-002 incomplete widget save shows guidance and empty publish stays blocked', async ({
  authenticatedPage: page,
}) => {
  await page.goto('/dashboards/new')
  await expect(page.getByLabel('Dashboard name')).toBeVisible()
  const publish = page.getByRole('button', { name: 'Publish' })
  await expect(publish).toBeDisabled()
  // Map is a data widget whose wells stay empty, so it remains incomplete even
  // when a semantic model is bound (KPI auto-fills a measure).
  await page.getByRole('button', { name: 'Map' }).click()
  await expect(page.getByText('Needs configuration')).toBeVisible()
  const save = page
    .waitForResponse(
      (response) =>
        response.url().includes('/api/v1/dashboards') && ['POST', 'PUT'].includes(response.request().method()),
      { timeout: 3_000 },
    )
    .catch(() => null)
  await page.getByRole('button', { name: 'Save', exact: true }).click()
  await expect(page.getByText('Complete this widget before saving', { exact: true })).toBeVisible()
  expect(await save).toBeNull()
  await expect(publish).toBeDisabled()
  await page.getByRole('button', { name: 'Widget menu' }).click()
  await page.getByRole('menuitem', { name: 'Delete' }).click()
  await page.getByRole('button', { name: 'KPI Card' }).click()
  await page.getByLabel('Dashboard name').fill(`qa-incomplete-${Date.now()}`)
  const inspector = page.getByRole('region', { name: 'Visual inspector' })
  if (
    await page
      .getByText('Needs configuration')
      .isVisible()
      .catch(() => false)
  ) {
    await inspector.locator('.winsp__add').first().click()
    const measure = page.getByRole('menuitem').first()
    if (await measure.isVisible().catch(() => false)) {
      await measure.click()
    } else {
      await page.keyboard.press('Escape')
      await page.getByRole('button', { name: 'Widget menu' }).click()
      await page.getByRole('menuitem', { name: 'Delete' }).click()
      await page.getByRole('button', { name: 'Text', exact: true }).click()
    }
    await expect(page.getByText('Needs configuration')).toHaveCount(0)
  }
  await page.getByRole('button', { name: 'Save', exact: true }).click()
  await expect(page).toHaveURL(/\/dashboards\/[0-9a-f-]+\/edit$/i, { timeout: 20_000 })
})

test('DASH-P2-FILTER-OPERATORS persist Is one of and Between across save/reload', async ({ page }) => {
  const email = process.env.VIP_E2E_GOVERNANCE_DEMO_EMAIL
  const password = process.env.VIP_E2E_GOVERNANCE_DEMO_PASSWORD
  if (!email || !password) throw new Error('Governance Demo browser credentials are required')
  await resetClientState(page)
  await signInAs(page, email, password)
  await page.goto('/dashboards/new')
  await page.getByLabel('Dashboard name').fill(`qa-filter-ops-${Date.now()}`)
  const panel = page.getByRole('region', { name: 'Fields and visuals' })
  await panel.getByRole('tab', { name: 'Data', exact: true }).click()
  const model = panel.getByRole('combobox')
  await expect(model).toBeVisible()
  const labels = await model.locator('option').allTextContents()
  const preferred =
    labels.find((label) => /LIVE-UAT-Sales-Model/i.test(label)) ??
    labels.find((label) => /QA Browser Certification Semantic Model/i.test(label)) ??
    labels.find((label) => label.trim() && !/^select/i.test(label))
  expect(preferred, `semantic model options: ${labels.join(' | ')}`).toBeTruthy()
  await model.selectOption({ label: preferred!.trim() })
  await panel.getByRole('tab', { name: 'Visuals', exact: true }).click()
  await page.getByRole('button', { name: 'Table', exact: true }).click()
  await page.getByRole('button', { name: 'Filter', exact: true }).click()
  const category = page
    .getByRole('menuitem')
    .filter({ hasText: /categor/i })
    .first()
  await expect(category).toBeVisible()
  await category.click()
  await page.getByLabel(/operator/i).selectOption('in')
  const addValue = page.getByLabel(/Add a .* value/i)
  await addValue.fill('Electronics')
  await page.getByRole('button', { name: 'Add', exact: true }).click()
  await addValue.fill('Furniture')
  await page.getByRole('button', { name: 'Add', exact: true }).click()
  await page.getByRole('button', { name: 'Apply' }).click()
  await page.getByRole('button', { name: 'Filter', exact: true }).click()
  const dateField = page.getByRole('menuitem').filter({ hasText: /date/i }).first()
  await expect(dateField).toBeVisible()
  await dateField.click()
  await page.getByLabel(/operator/i).selectOption('between')
  await page.getByLabel(/from$/i).fill('2026-01-01')
  await page.getByLabel(/to$/i).fill('2026-12-31')
  await page.getByRole('button', { name: 'Apply' }).click()
  const authored = (await page.locator('.fbar__chip').allTextContents()).join(' | ')
  expect(authored).toMatch(/is one of/i)
  expect(authored).toMatch(/between/i)
  await page.getByRole('button', { name: 'Save', exact: true }).click()
  await expect(page).toHaveURL(/\/dashboards\/[0-9a-f-]+\/edit$/i, { timeout: 20_000 })
  await page.reload()
  await expect(page.getByLabel('Dashboard name')).toBeVisible({ timeout: 20_000 })
  await expect
    .poll(async () => (await page.locator('.fbar__chip').allTextContents()).join(' | '), { timeout: 20_000 })
    .toMatch(/is one of/i)
  const chips = (await page.locator('.fbar__chip').allTextContents()).join(' | ')
  expect(chips).toMatch(/is one of/i)
  expect(chips).toMatch(/Electronics/)
  expect(chips).toMatch(/Furniture/)
  expect(chips).toMatch(/between/i)
  expect(chips).toMatch(/2026-01-01/)
  expect(chips).toMatch(/2026-12-31/)
})

test('PIPE-P2-STALE-SCHEDULES archive disables the schedule and clears next run', async ({
  authenticatedPage: page,
}) => {
  await page.goto('/pipelines/new')
  await page.getByLabel('Pipeline name').fill(`qa-stale-sched-${Date.now()}`)
  await page.getByRole('button', { name: 'Save' }).click()
  await expect(page).toHaveURL(/\/pipelines\/[0-9a-f-]{36}/i, { timeout: 20_000 })
  const pipelineId = /\/pipelines\/([0-9a-f-]{36})/i.exec(page.url())?.[1]
  expect(pipelineId).toBeTruthy()
  const created = await api(page, 'POST', `http://localhost:8000/api/v1/pipelines/${pipelineId}/schedules`, {
    name: 'stale-schedule-cert',
    schedule_type: 'daily',
    timezone: 'UTC',
    enabled: false,
  })
  expect(created.status, JSON.stringify(created.json)).toBe(201)
  const detail = await api(page, 'GET', `http://localhost:8000/api/v1/pipelines/${pipelineId}`)
  expect(detail.status).toBe(200)
  const version =
    (detail.json as { pipeline?: { row_version?: number }; row_version?: number }).pipeline?.row_version ??
    (detail.json as { row_version?: number }).row_version
  expect(version).toBeGreaterThan(0)
  const archived = await api(
    page,
    'DELETE',
    `http://localhost:8000/api/v1/pipelines/${pipelineId}?expected_version=${version}`,
  )
  expect(archived.status, JSON.stringify(archived.json)).toBe(204)
  const leftover = await api(page, 'GET', `http://localhost:8000/api/v1/pipelines/${pipelineId}/schedules`)
  if (leftover.status === 200 && Array.isArray(leftover.json)) {
    const rows = leftover.json as Array<{ enabled?: boolean; next_run_at?: string | null; status?: string }>
    expect(rows.every((item) => item.enabled === false)).toBe(true)
    expect(rows.every((item) => item.next_run_at == null || item.status === 'archived')).toBe(true)
  } else {
    expect([403, 404]).toContain(leftover.status)
  }
})

test('deferred modules are absent from sidebar, palette, and quick create', async ({ authenticatedPage: page }) => {
  await page.goto('/home')
  for (const name of ['Reports', 'Insights', 'Explore', 'AI Studio', 'Automation', 'Billing', 'Marketplace']) {
    await expect(
      page.getByRole('navigation', { name: 'Primary navigation' }).getByRole('link', { name, exact: true }),
    ).toHaveCount(0)
  }
  await page.getByRole('button', { name: /Search & commands/ }).click()
  const search = page.getByRole('dialog').getByRole('textbox')
  await expect(search).toBeVisible()
  await search.fill('Reports')
  await expect(page.getByRole('option', { name: /^Reports$/ })).toHaveCount(0)
  await page.keyboard.press('Escape')
  await page.goto('/reports')
  await expect(page.getByRole('heading', { name: /page not found/i })).toBeVisible()
  await expect(page).toHaveURL(/\/not-found$/)
  await expect(page).not.toHaveURL(/\/upgrade/)
})
