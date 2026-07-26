import { test, expect } from './fixtures'

test('dashboard first save adopts a stable URL and survives refresh', async ({ authenticatedPage: page }) => {
  await page.goto('/dashboards/new')
  await expect(page.getByLabel('Dashboard name')).toBeVisible()
  const name = `Contract QA Dashboard ${Date.now()}`
  await page.getByLabel('Dashboard name').fill(name)
  await expect(page.getByText(/Unsaved/)).toBeVisible()
  await page.getByRole('button', { name: 'Save' }).click()
  await expect(page).toHaveURL(
    /\/dashboards\/[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\/edit$/i,
  )
  await page.reload()
  await expect(page.getByLabel('Dashboard name')).toHaveValue(name)
})

test('dashboard supports a keyboard-only add, move, resize, and delete journey', async ({
  authenticatedPage: page,
}) => {
  await page.goto('/dashboards/new')
  const add = page.getByRole('button', { name: 'KPI Card' })
  await add.focus()
  await add.press('Enter')
  const widget = page.getByRole('button', { name: /KPI Card widget/ })
  await expect(widget).toBeVisible()
  await widget.focus()
  await widget.press('Enter')
  await widget.press('ArrowRight')
  await widget.press('Shift+ArrowRight')
  await widget.press('Delete')
  await expect(page.getByRole('button', { name: /KPI Card widget/ })).toHaveCount(0)
})

test('pipeline keyboard authoring and first save use stable URL', async ({ authenticatedPage: page }) => {
  await page.goto('/pipelines/new')
  const addNode = page.getByRole('button', { name: /Add Dataset node/ })
  await addNode.focus()
  await addNode.press('Enter')
  await expect(page.getByRole('button', { name: /Dataset node:/ })).toBeVisible()
  await page.getByLabel('Pipeline name').fill('Contract QA Pipeline')
  await expect(page.getByText(/Unsaved/)).toBeVisible()
  await page.getByRole('button', { name: 'Save' }).click()
  await expect(page).toHaveURL(/\/pipelines\/[0-9a-f-]{36}$/)
})

test('pipeline supports keyboard node movement and port connection', async ({ authenticatedPage: page }) => {
  await page.goto('/pipelines/new')
  await page.getByRole('button', { name: 'Add Dataset node' }).press('Enter')
  const source = page.getByRole('button', { name: /Dataset node:/ })
  await source.focus()
  await source.press('ArrowRight')
  await page.getByRole('button', { name: /Output output port/ }).press('Enter')
  await page.getByRole('button', { name: 'Add Dataset Output node' }).press('Enter')
  await page.getByRole('button', { name: /Input input port/ }).press('Enter')
  await expect(page.locator('.pcanvas__edge:not(.is-pending)')).toHaveCount(1)
})

test('@mobile dashboard studio remains usable without horizontal overflow', async ({ authenticatedPage: page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/dashboards/new')
  await expect(page.getByLabel('Dashboard name')).toBeVisible()
  await expect(page.locator('#dstudio-fields')).toHaveAttribute('inert')
  await expect(page.locator('#dstudio-inspector')).toHaveAttribute('inert')
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(
    true,
  )
})

test('@mobile pipeline studio remains usable without horizontal overflow', async ({ authenticatedPage: page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/pipelines/new')
  await expect(page.getByLabel('Pipeline name')).toBeVisible()
  await expect(page.locator('#pstudio-palette')).toHaveAttribute('inert')
  await expect(page.locator('#pstudio-inspector')).toHaveAttribute('inert')
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(
    true,
  )
})
