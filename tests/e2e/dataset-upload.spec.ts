import path from 'node:path'
import { test, expect } from './fixtures'

// Regression guard for device-file dataset import: users must be able to upload a
// CSV file from their device (not only paste text). The picker reads the file,
// fills the CSV textarea, and auto-derives the target table and display name.
test('Datasets: Import CSV accepts a device file and fills the form', async ({ authenticatedPage: page }) => {
  await page.goto('/datasets')
  await page.getByRole('button', { name: 'Import CSV' }).click()

  const dialog = page.getByRole('dialog', { name: 'Import CSV dataset' })
  await expect(dialog).toBeVisible()

  // The file input is hidden behind the "Upload CSV file…" button; set files directly.
  await dialog.locator('input[type="file"]').setInputFiles(path.resolve('e2e', 'data', 'b8_5_certification.csv'))

  // Selected filename is surfaced.
  await expect(dialog.getByText('b8_5_certification.csv')).toBeVisible()

  // CSV contents are loaded into the editable textarea.
  await expect(dialog.locator('textarea')).toHaveValue(/transaction_id/)

  // Target table and display name are auto-derived from the filename.
  await expect(dialog.getByLabel('Target table')).toHaveValue('b8_5_certification')
  await expect(dialog.getByLabel(/Display name/)).toHaveValue('b8_5_certification')
})
