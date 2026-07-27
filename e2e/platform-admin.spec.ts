import { test, expect, signInAs, E2E_PASSWORD } from './fixtures'

// The platform super-admin console is a cross-tenant operator surface. tenant-a is
// granted the platform-admin flag during seeding; tenant-b is a normal tenant user.

test('platform admin can open the cross-tenant console', async ({ authenticatedPage: page }) => {
  // The Platform Admin nav entry is visible only to platform admins.
  await expect(page.getByRole('link', { name: 'Platform Admin' })).toBeVisible()

  await page.goto('/platform')
  await expect(page.getByRole('heading', { name: 'Platform administration' })).toBeVisible()

  // Overview stat tiles render live counts.
  await expect(page.locator('.pa__stat-label', { hasText: 'Platform admins' })).toBeVisible()
  await expect(page.locator('.pa__stat').filter({ hasText: 'Organizations' })).toBeVisible()

  // Organizations tab lists tenants with actions.
  await page.getByRole('tab', { name: 'Organizations' }).click()
  await expect(page.locator('.pa__table')).toBeVisible()
  await expect(page.getByRole('button', { name: /^Suspend$|^Activate$/ }).first()).toBeVisible()

  // Users tab lists users across tenants.
  await page.getByRole('tab', { name: 'Users' }).click()
  await expect(page.locator('.pa__table')).toBeVisible()
})

test('a normal tenant user cannot see or reach the platform console', async ({ page }) => {
  await signInAs(page, 'tenant-b@vip.demo', E2E_PASSWORD)

  // No Platform Admin nav entry.
  await expect(page.getByRole('link', { name: 'Platform Admin' })).toHaveCount(0)

  // Direct navigation is non-disclosing: routed to not-found, not the console.
  await page.goto('/platform')
  await expect(page.getByRole('heading', { name: 'Platform administration' })).toHaveCount(0)
})
