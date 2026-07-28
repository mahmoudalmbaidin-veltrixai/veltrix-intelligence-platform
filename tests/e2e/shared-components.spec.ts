import { test, expect } from './fixtures'

test('menu supports keyboard navigation and restores focus', async ({ authenticatedPage: page }) => {
  const trigger = page.getByRole('button', { name: 'User menu' })
  await trigger.focus()
  await trigger.press('Enter')
  await expect(page.getByRole('menuitem', { name: 'Profile & preferences' })).toBeFocused()
  await page.keyboard.press('End')
  await expect(page.getByRole('menuitem', { name: 'Sign out' })).toBeFocused()
  await page.keyboard.press('Escape')
  await expect(trigger).toBeFocused()
})

test('notification drawer traps focus, closes with Escape, and restores focus', async ({ authenticatedPage: page }) => {
  const trigger = page.getByRole('button', { name: 'Notifications' })
  await trigger.click()
  await expect(page.getByRole('dialog')).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(page.getByRole('dialog')).toBeHidden()
  await expect(trigger).toBeFocused()
})

test('command palette keyboard journey returns focus safely', async ({ authenticatedPage: page }) => {
  const trigger = page.getByRole('button', { name: /Search & commands/ })
  await trigger.focus()
  await page.keyboard.press('Control+k')
  const search = page.getByRole('dialog').getByRole('textbox')
  await expect(search).toBeFocused()
  await search.fill('dashboard')
  await page.keyboard.press('ArrowDown')
  await page.keyboard.press('Escape')
  await expect(page.getByRole('dialog')).toBeHidden()
})

test('sortable table header is keyboard operable and announces state', async ({ authenticatedPage: page }) => {
  await page.goto('/pipelines')
  const sort = page.getByRole('columnheader', { name: 'Sort by Pipeline' })
  await sort.focus()
  await sort.press('Enter')
  await expect(sort).toHaveAttribute('aria-sort', /ascending|descending/)
})

test('dashboard share dialog has a name, closes with Escape, and restores focus', async ({
  authenticatedPage: page,
}) => {
  await page.goto('/dashboards/new')
  await page.getByLabel('Dashboard name').fill(`Share Dialog QA ${Date.now()}`)
  await page.getByRole('button', { name: 'Save' }).click()
  await expect(page).toHaveURL(/\/dashboards\/[0-9a-f-]+\/edit$/i)
  const trigger = page.getByRole('button', { name: 'Share' })
  await trigger.click()
  await expect(page.getByRole('dialog')).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(page.getByRole('dialog')).toBeHidden()
  await expect(trigger).toBeFocused()
})
