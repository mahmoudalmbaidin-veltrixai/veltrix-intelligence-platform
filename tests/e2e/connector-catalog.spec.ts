import { test, expect } from './fixtures'

// Guards the enterprise connector catalog: a broad, backend-driven set of connectors
// with honest status badges, category/status filters, and a requirements detail view.
test('connector catalog renders the backend registry with filters and statuses', async ({
  authenticatedPage: page,
}) => {
  await page.goto('/connections/catalog')

  const cards = page.locator('.catalog__card')
  await expect(cards.first()).toBeVisible()
  // The catalog is broad (dozens of connectors), served from the backend registry.
  expect(await cards.count()).toBeGreaterThan(40)

  // Honest status badges are present on the cards (scoped to avoid the filter <option>s).
  await expect(cards.getByText('Available', { exact: true }).first()).toBeVisible()
  await expect(cards.getByText('Planned', { exact: true }).first()).toBeVisible()

  // Filter to Available-only; PostgreSQL must remain and a planned connector must drop.
  const selects = page.locator('.catalog__toolbar select')
  await selects.nth(1).selectOption('available')
  await expect(page.getByRole('heading', { name: 'PostgreSQL' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Snowflake' })).toHaveCount(0)

  // Available connectors offer a real "Create connection" action.
  await expect(page.getByRole('button', { name: 'Create connection' }).first()).toBeVisible()

  // Requirements dialog exposes setup/network guidance.
  await page.locator('.catalog__card').first().getByRole('button', { name: 'View requirements' }).click()
  const dialog = page.getByRole('dialog')
  await expect(dialog).toBeVisible()
  await expect(dialog.getByText('Requirements & network')).toBeVisible()
  await expect(dialog.getByText('Authentication methods')).toBeVisible()
})

test('planned connectors are shown but not directly creatable', async ({ authenticatedPage: page }) => {
  await page.goto('/connections/catalog')
  const selects = page.locator('.catalog__toolbar select')
  await selects.nth(1).selectOption('planned')
  const firstCard = page.locator('.catalog__card').first()
  await expect(firstCard).toBeVisible()
  // A planned connector card must NOT offer "Create connection"; only "View requirements".
  await expect(firstCard.getByRole('button', { name: 'Create connection' })).toHaveCount(0)
  await expect(firstCard.getByRole('button', { name: 'View requirements' })).toBeVisible()
})
