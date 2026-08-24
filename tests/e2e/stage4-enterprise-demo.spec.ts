import { expect, type Page, test } from '@playwright/test'

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
  )
  await page.getByRole('button', { name: 'Sign in' }).click()
  expect((await response).status()).toBe(200)
  await expect(page).not.toHaveURL(/\/login/)
}

test.describe('Stage 4 enterprise demo @stage4-demo', () => {
  test.describe.configure({ mode: 'serial' })

  test('organization admin completes the governed flagship journey', async ({ page }) => {
    await signInAs(page, required('VIP_STAGE4_ADMIN_USERNAME'), required('VIP_STAGE4_ADMIN_PASSWORD'))

    await page.goto(`/datasets/${required('VIP_STAGE4_RAW_DATASET_ID')}`)
    await expect(page.getByText(required('VIP_STAGE4_RAW_DATASET_NAME'), { exact: true })).toBeVisible()
    await expect(page.getByText(/SYNTHETIC DEMO DATA/i).first()).toBeVisible()

    await page.goto(`/pipelines/${required('VIP_STAGE4_PIPELINE_ID')}`)
    await expect(page.getByRole('textbox', { name: 'Pipeline name' })).toHaveValue(
      required('VIP_STAGE4_PIPELINE_NAME'),
    )
    await expect(page.getByText('Join Regional Targets', { exact: true })).toBeVisible()
    await expect(page.getByText('Business Quality Gate', { exact: true })).toBeVisible()

    await page.goto(`/dashboards/${required('VIP_STAGE4_DASHBOARD_ID')}`)
    await expect(page.getByText(required('VIP_STAGE4_DASHBOARD_NAME'), { exact: true }).first()).toBeVisible()
    await expect(page.getByText('Region', { exact: true }).first()).toBeVisible()
    await expect(page.getByText('Date', { exact: true }).first()).toBeVisible()
    await expect(page.getByText('Regional Performance Detail', { exact: true })).toBeVisible()
    await page.reload()
    await expect(page.getByText(required('VIP_STAGE4_DASHBOARD_NAME'), { exact: true }).first()).toBeVisible()
    await expect(page.getByText(/Unable to load|Something went wrong/i)).toHaveCount(0)
  })

  test('viewer consumes published content and direct authoring routes fail closed', async ({ page }) => {
    await signInAs(page, required('VIP_STAGE4_VIEWER_USERNAME'), required('VIP_STAGE4_VIEWER_PASSWORD'))

    await page.goto(`/dashboards/${required('VIP_STAGE4_DASHBOARD_ID')}`)
    await expect(page.getByText(required('VIP_STAGE4_DASHBOARD_NAME'), { exact: true }).first()).toBeVisible()
    await expect(page.getByRole('link', { name: /Edit|Dashboard Studio/i })).toHaveCount(0)

    await page.goto(`/dashboards/${required('VIP_STAGE4_DASHBOARD_ID')}/edit`)
    await expect(page).toHaveURL(/\/(forbidden|not-found)/)

    await page.goto('/pipelines/new')
    await expect(page).toHaveURL(/\/forbidden/)

    const foreignDashboardId = required('VIP_STAGE4_FOREIGN_DASHBOARD_ID')
    const rejectedForeignRequest = page.waitForResponse(
      (item) =>
        item.request().method() === 'GET' &&
        item.url().includes(`/api/v1/dashboards/${foreignDashboardId}`),
    )
    await page.goto(`/dashboards/${foreignDashboardId}`)
    expect((await rejectedForeignRequest).status()).toBe(404)
    await expect(page.getByText('Network Operations Command Dashboard', { exact: true })).toHaveCount(0)
  })
})
