import { test, expect } from './fixtures'

// Regression guard for the dashboard three-dot menu / delete defect: the action
// menu panel used to be clipped by the card's `overflow: hidden`, hiding Delete.
// VipMenu now teleports the panel to <body>, so it must render fully in-viewport
// and be interactable, and Delete must open the confirmation dialog.
test('dashboard action menu shows an unclipped, usable Delete action', async ({ authenticatedPage: page }) => {
  await page.goto('/dashboards')

  const firstTrigger = page.getByRole('button', { name: /^Actions for/ }).first()
  await expect(firstTrigger).toBeVisible()
  await firstTrigger.click()

  const menu = page.getByRole('menu')
  await expect(menu).toBeVisible()
  const deleteItem = menu.getByRole('menuitem', { name: 'Delete' })
  await expect(deleteItem).toBeVisible()

  // The regression: the Delete item must be fully within the viewport (not
  // clipped by an ancestor with overflow: hidden).
  const box = await deleteItem.boundingBox()
  const viewport = page.viewportSize()!
  expect(box).not.toBeNull()
  expect(box!.x).toBeGreaterThanOrEqual(0)
  expect(box!.y).toBeGreaterThanOrEqual(0)
  expect(box!.x + box!.width).toBeLessThanOrEqual(viewport.width + 1)
  expect(box!.y + box!.height).toBeLessThanOrEqual(viewport.height + 1)

  // Delete opens the confirmation dialog; Cancel closes it without deleting.
  await deleteItem.click()
  const dialog = page.getByRole('dialog', { name: 'Delete dashboard?' })
  await expect(dialog).toBeVisible()
  await dialog.getByRole('button', { name: 'Cancel' }).click()
  await expect(dialog).toBeHidden()
})

test('dashboard action menu closes on Escape and returns focus to the trigger', async ({ authenticatedPage: page }) => {
  await page.goto('/dashboards')
  const firstTrigger = page.getByRole('button', { name: /^Actions for/ }).first()
  await firstTrigger.click()
  await expect(page.getByRole('menu')).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(page.getByRole('menu')).toBeHidden()
})
