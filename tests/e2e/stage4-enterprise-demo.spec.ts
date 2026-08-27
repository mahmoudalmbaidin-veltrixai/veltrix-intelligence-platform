import { expect, type Page, test } from '@playwright/test'

const UI_TIMEOUT = 30_000

const required = (name: string): string => {
  const value = process.env[name]
  if (!value) throw new Error(`${name} is required for Stage 4 demo certification`)
  return value
}

const signInAs = async (page: Page, username: string, password: string): Promise<void> => {
  await page.goto('/login')
  await page.getByRole('textbox', { name: 'Username or email' }).fill(username)
  await page.getByRole('textbox', { name: 'Password' }).fill(password)
  const response = page.waitForResponse(
    (item) => item.request().method() === 'POST' && item.url().endsWith('/auth/login'),
    { timeout: UI_TIMEOUT },
  )
  await page.getByRole('button', { name: 'Sign in' }).click({ timeout: UI_TIMEOUT })
  expect((await response).status()).toBe(200)
  await expect(page).not.toHaveURL(/\/login/, { timeout: UI_TIMEOUT })
}

test.describe('Stage 4 enterprise demo @stage4-demo', () => {
  test.describe.configure({ mode: 'serial' })

  test('organization admin completes the governed flagship journey', async ({ page }) => {
    test.setTimeout(180_000)
    await signInAs(page, required('VIP_STAGE4_ADMIN_USERNAME'), required('VIP_STAGE4_ADMIN_PASSWORD'))

    await expect(
      page.getByRole('button', { name: `Organization: ${required('VIP_STAGE4_ORGANIZATION_NAME')}` }),
    ).toBeVisible({ timeout: UI_TIMEOUT })
    await expect(page.getByRole('button', { name: required('VIP_STAGE4_WORKSPACE_NAME') })).toBeVisible({
      timeout: UI_TIMEOUT,
    })

    await page.goto(`/connections/${required('VIP_STAGE4_CONNECTION_ID')}`)
    await expect(page.getByText(required('VIP_STAGE4_CONNECTION_NAME'), { exact: true }).first()).toBeVisible({
      timeout: UI_TIMEOUT,
    })
    await expect(page.getByText('healthy', { exact: true }).first()).toBeVisible({ timeout: UI_TIMEOUT })
    const connectionTest = page.waitForResponse(
      (item) =>
        item.request().method() === 'POST' &&
        item.url().endsWith(`/connections/${required('VIP_STAGE4_CONNECTION_ID')}/test`),
    )
    await page.getByRole('button', { name: 'Test connection' }).click()
    expect((await connectionTest).status()).toBe(200)

    await page.goto(`/datasets/${required('VIP_STAGE4_RAW_DATASET_ID')}`)
    await expect(page.getByText(required('VIP_STAGE4_RAW_DATASET_NAME'), { exact: true })).toBeVisible({
      timeout: UI_TIMEOUT,
    })
    await expect(page.getByText(/SYNTHETIC DEMO DATA/i).first()).toBeVisible({ timeout: UI_TIMEOUT })
    await page.getByRole('tab', { name: 'Quality' }).click()
    await expect(page.getByText(/Score [0-9]+/).first()).toBeVisible({ timeout: UI_TIMEOUT })

    await page.goto(`/pipelines/${required('VIP_STAGE4_PIPELINE_ID')}`)
    await expect(page.getByRole('textbox', { name: 'Pipeline name' })).toHaveValue(
      required('VIP_STAGE4_PIPELINE_NAME'),
      { timeout: UI_TIMEOUT },
    )
    await expect(page.getByText('Join Regional Targets', { exact: true })).toBeVisible({ timeout: UI_TIMEOUT })
    await expect(page.getByText('Business Quality Gate', { exact: true })).toBeVisible({ timeout: UI_TIMEOUT })

    await page.goto(`/semantic/${required('VIP_STAGE4_SEMANTIC_ID')}`)
    await expect(page.getByText(required('VIP_STAGE4_SEMANTIC_NAME'), { exact: true }).first()).toBeVisible({
      timeout: UI_TIMEOUT,
    })
    await expect(page.getByText('published', { exact: true }).first()).toBeVisible({ timeout: UI_TIMEOUT })

    await page.goto(`/dashboards/${required('VIP_STAGE4_DASHBOARD_ID')}`)
    await expect(page.getByText(required('VIP_STAGE4_DASHBOARD_NAME'), { exact: true }).first()).toBeVisible({
      timeout: UI_TIMEOUT,
    })
    await expect(page.getByText('Region', { exact: true }).first()).toBeVisible({ timeout: UI_TIMEOUT })
    await expect(page.getByText('Date', { exact: true }).first()).toBeVisible({ timeout: UI_TIMEOUT })
    await expect(page.getByText('Regional Performance Detail', { exact: true })).toBeVisible({ timeout: UI_TIMEOUT })
    await page.reload()
    await expect(page.getByText(required('VIP_STAGE4_DASHBOARD_NAME'), { exact: true }).first()).toBeVisible({
      timeout: UI_TIMEOUT,
    })
    await expect(page.getByText(/Unable to load|Something went wrong/i)).toHaveCount(0)

    await page.getByRole('button', { name: 'Share' }).click()
    await page.getByRole('menuitem', { name: 'Export (PDF/PNG/CSV)' }).click()
    const governanceDialog = page.getByRole('dialog', { name: 'Dashboard governance' })
    await expect(governanceDialog.getByText('PDF export', { exact: true }).first()).toBeVisible({
      timeout: UI_TIMEOUT,
    })
    await expect(governanceDialog.getByText('PNG export', { exact: true }).first()).toBeVisible({
      timeout: UI_TIMEOUT,
    })
    await expect
      .poll(() => governanceDialog.getByRole('button', { name: 'Download' }).count(), { timeout: UI_TIMEOUT })
      .toBeGreaterThanOrEqual(2)

    await page.goto('/notifications')
    await expect(page.getByText('Dashboard export (PDF): succeeded', { exact: true }).first()).toBeVisible({
      timeout: UI_TIMEOUT,
    })
    const markAll = page.getByRole('button', { name: 'Mark all read' })
    if (await markAll.isEnabled()) await markAll.click()
    await expect(markAll).toBeDisabled()
    await page.getByRole('button', { name: 'Mark unread' }).first().click()
    await page.getByRole('button', { name: 'Mark read' }).first().click()
    await expect(markAll).toBeDisabled()
    await page.reload()
    await expect(page.getByRole('button', { name: 'Mark all read' })).toBeDisabled()

    await page.getByRole('button', { name: 'User menu' }).click()
    await page.getByText('Sign out', { exact: true }).click()
    await expect(page).toHaveURL(/\/login/, { timeout: UI_TIMEOUT })
    await signInAs(page, required('VIP_STAGE4_ADMIN_USERNAME'), required('VIP_STAGE4_ADMIN_PASSWORD'))
    await page.goto('/notifications')
    await expect(page.getByRole('button', { name: 'Mark all read' })).toBeDisabled()
  })

  test('viewer consumes published content and direct authoring routes fail closed', async ({ page }) => {
    test.setTimeout(90_000)
    await signInAs(page, required('VIP_STAGE4_VIEWER_USERNAME'), required('VIP_STAGE4_VIEWER_PASSWORD'))

    await page.goto(`/dashboards/${required('VIP_STAGE4_DASHBOARD_ID')}`)
    await expect(page.getByText(required('VIP_STAGE4_DASHBOARD_NAME'), { exact: true }).first()).toBeVisible({
      timeout: UI_TIMEOUT,
    })
    await expect(page.getByRole('link', { name: /Edit|Dashboard Studio/i })).toHaveCount(0)

    await page.goto(`/dashboards/${required('VIP_STAGE4_DASHBOARD_ID')}/edit`)
    await expect(page).toHaveURL(/\/(forbidden|not-found)/)

    await page.goto('/pipelines/new')
    await expect(page).toHaveURL(/\/forbidden/)

    const foreignDashboardId = required('VIP_STAGE4_FOREIGN_DASHBOARD_ID')
    const rejectedForeignRequest = page.waitForResponse(
      (item) => item.request().method() === 'GET' && item.url().includes(`/api/v1/dashboards/${foreignDashboardId}`),
    )
    await page.goto(`/dashboards/${foreignDashboardId}`)
    expect((await rejectedForeignRequest).status()).toBe(404)
    await expect(page.getByText('Network Operations Command Dashboard', { exact: true })).toHaveCount(0)
  })
})
