import { test, expect } from './fixtures'

// SaaS onboarding: a signed-in user can self-serve a brand-new, isolated organization
// from the topbar switcher. The creator becomes owner, a default workspace is created,
// the app switches into the new org, and the dialog closes.
test('create a new organization from the topbar and switch into it', async ({ authenticatedPage: page }) => {
  const suffix = Date.now().toString().slice(-6)
  const name = `E2E Client ${suffix}`

  await page.getByRole('button', { name: /^Organization:/ }).click()
  await page.getByRole('menuitem', { name: 'New organization' }).click()

  const dialog = page.getByRole('dialog', { name: 'New organization' })
  await expect(dialog).toBeVisible()

  await dialog.getByLabel('Organization name').fill(name)
  // Slug is auto-derived from the name.
  await expect(dialog.getByLabel('Slug')).toHaveValue(`e2e-client-${suffix}`)

  await dialog.getByRole('button', { name: 'Create organization' }).click()

  // Dialog closes and the active organization becomes the newly created one.
  await expect(dialog).toBeHidden()
  await expect(page.getByRole('button', { name: `Organization: ${name}` })).toBeVisible()
})
