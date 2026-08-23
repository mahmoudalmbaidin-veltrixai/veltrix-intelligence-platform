# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: release-p2-certification.spec.ts >> CERT-P2-001 timezone combobox persists Asia/Riyadh across reload
- Location: tests\e2e\release-p2-certification.spec.ts:72:1

# Error details

```
Error: expect(locator).toBeVisible() failed

Locator: getByText('Your language and region settings were saved.', { exact: true })
Expected: visible
Error: strict mode violation: getByText('Your language and region settings were saved.', { exact: true }) resolved to 2 elements:
    1) <div data-v-e6c2a848="" class="vip-toast__msg">Your language and region settings were saved.</div> aka getByText('Your language and region').first()
    2) <div data-v-e6c2a848="" class="vip-toast__msg">Your language and region settings were saved.</div> aka getByText('Your language and region').nth(1)

Call log:
  - Expect "toBeVisible" with timeout 7000ms
  - waiting for getByText('Your language and region settings were saved.', { exact: true })

```

# Page snapshot

```yaml
- generic [active] [ref=e1]:
  - generic [ref=e2]:
    - link "Skip to main content" [ref=e3]:
      - /url: "#vip-main"
    - generic [ref=e4]:
      - navigation "Primary navigation" [ref=e6]:
        - generic [ref=e7]:
          - link "VIP home" [ref=e8]:
            - /url: /home
            - generic [ref=e9]:
              - img [ref=e10]
              - generic [ref=e19]: VIP
          - button "Unpin and collapse navigation to icons" [pressed] [ref=e20] [cursor=pointer]:
            - img [ref=e21]
        - generic [ref=e24]:
          - generic [ref=e25]:
            - generic [ref=e26]: Core
            - link "Home" [ref=e28]:
              - /url: /home
              - img [ref=e29]
              - generic [ref=e32]: Home
            - link "Favorites" [ref=e34]:
              - /url: /favorites
              - img [ref=e35]
              - generic [ref=e37]: Favorites
            - link "Recent activity" [ref=e39]:
              - /url: /activity
              - img [ref=e40]
              - generic [ref=e43]: Recent activity
          - generic [ref=e44]:
            - generic [ref=e45]: Data
            - link "Connections" [ref=e47]:
              - /url: /connections
              - img [ref=e48]
              - generic [ref=e50]: Connections
            - link "Pipelines" [ref=e52]:
              - /url: /pipelines
              - img [ref=e53]
              - generic [ref=e57]: Pipelines
            - link "Datasets" [ref=e59]:
              - /url: /datasets
              - img [ref=e60]
              - generic [ref=e64]: Datasets
            - link "Semantic Models" [ref=e66]:
              - /url: /semantic
              - img [ref=e67]
              - generic [ref=e70]: Semantic Models
            - link "Metrics & KPIs" [ref=e72]:
              - /url: /semantic/metrics
              - img [ref=e73]
              - generic [ref=e77]: Metrics & KPIs
            - link "Data Quality" [ref=e79]:
              - /url: /datasets/quality
              - img [ref=e80]
              - generic [ref=e83]: Data Quality
            - link "Data Lineage" [ref=e85]:
              - /url: /datasets/lineage
              - img [ref=e86]
              - generic [ref=e91]: Data Lineage
          - generic [ref=e92]:
            - generic [ref=e93]: Analytics
            - link "Dashboards" [ref=e95]:
              - /url: /dashboards
              - img [ref=e96]
              - generic [ref=e100]: Dashboards
            - link "Dashboard Studio" [ref=e102]:
              - /url: /dashboards/new
              - img [ref=e103]
              - generic [ref=e105]: Dashboard Studio
            - link "Dashboard Templates" [ref=e107]:
              - /url: /dashboards/templates
              - img [ref=e108]
              - generic [ref=e111]: Dashboard Templates
            - link "Published Dashboards" [ref=e113]:
              - /url: /dashboards/published
              - img [ref=e114]
              - generic [ref=e117]: Published Dashboards
            - link "Scheduled Deliveries" [ref=e119]:
              - /url: /dashboards/deliveries
              - img [ref=e120]
              - generic [ref=e123]: Scheduled Deliveries
          - generic [ref=e124]:
            - generic [ref=e125]: Operations
            - link "Activity" [ref=e127]:
              - /url: /operations/activity
              - img [ref=e128]
              - generic [ref=e130]: Activity
            - link "Audit Center" [ref=e132]:
              - /url: /audit
              - img [ref=e133]
              - generic [ref=e136]: Audit Center
            - link "Usage" [ref=e138]:
              - /url: /usage
              - img [ref=e139]
              - generic [ref=e141]: Usage
          - generic [ref=e142]:
            - generic [ref=e143]: Administration
            - link "Platform Admin" [ref=e145]:
              - /url: /platform
              - img [ref=e146]
              - generic [ref=e149]: Platform Admin
            - link "Organization Admin" [ref=e151]:
              - /url: /admin/organization
              - img [ref=e152]
              - generic [ref=e155]: Organization Admin
            - link "Workspace Admin" [ref=e157]:
              - /url: /admin/workspace
              - img [ref=e158]
              - generic [ref=e161]: Workspace Admin
            - link "Members & Roles" [ref=e163]:
              - /url: /admin/members
              - img [ref=e164]
              - generic [ref=e168]: Members & Roles
            - link "Roles" [ref=e170]:
              - /url: /admin/roles
              - img [ref=e171]
              - generic [ref=e173]: Roles
            - link "Groups & Teams" [ref=e175]:
              - /url: /admin/groups
              - img [ref=e176]
              - generic [ref=e180]: Groups & Teams
            - link "Access Control" [ref=e182]:
              - /url: /admin/access
              - img [ref=e183]
              - generic [ref=e185]: Access Control
            - link "Feature Flags" [ref=e187]:
              - /url: /admin/feature-flags
              - img [ref=e188]
              - generic [ref=e190]: Feature Flags
            - link "Governance" [ref=e192]:
              - /url: /admin/governance
              - img [ref=e193]
              - generic [ref=e195]: Governance
          - generic [ref=e196]:
            - generic [ref=e197]: Settings
            - link "Settings" [ref=e199]:
              - /url: /settings/profile
              - img [ref=e200]
              - generic [ref=e203]: Settings
        - generic [ref=e204]:
          - link "Help & docs" [ref=e206]:
            - /url: /help
            - img [ref=e207]
            - generic [ref=e210]: Help & docs
          - generic [ref=e211]: VIP · v0.1.0 · hybrid local
      - generic [ref=e212]:
        - banner [ref=e213]:
          - generic [ref=e214]:
            - 'button "Organization: QA_Enterprise_A_20260804" [ref=e217] [cursor=pointer]':
              - generic [ref=e218]: Q
              - generic [ref=e219]: QA_Enterprise_A_20260804
              - img [ref=e220]
            - generic [ref=e222]: /
            - button "Default" [ref=e225] [cursor=pointer]:
              - img [ref=e226]
              - generic [ref=e229]: Default
              - img [ref=e230]
            - generic [ref=e232]: /
            - generic [ref=e233]: Settings
          - generic [ref=e234]:
            - button "Search & commands ⌘K" [ref=e235] [cursor=pointer]:
              - img [ref=e236]
              - generic [ref=e239]: Search & commands
              - generic [ref=e240]: ⌘K
            - button "Create" [ref=e243] [cursor=pointer]:
              - img [ref=e244]
            - button "Toggle theme" [ref=e246] [cursor=pointer]:
              - img [ref=e247]
            - button "Notifications" [ref=e250] [cursor=pointer]:
              - img [ref=e251]
              - generic [ref=e254]: "22"
            - generic "Active organization and workspace roles" [ref=e255]:
              - img [ref=e256]
              - generic [ref=e260]: Organization Owner · Workspace Admin
            - button "User menu" [ref=e263] [cursor=pointer]:
              - generic "QA Platform Super Admin" [ref=e264]: QP
        - main [ref=e265]:
          - generic [ref=e266]:
            - generic [ref=e269]:
              - heading "Settings" [level=1] [ref=e271]
              - paragraph [ref=e272]: Manage your account, personal preferences, security, and notification settings.
            - generic [ref=e273]:
              - navigation "Settings sections" [ref=e274]:
                - generic [ref=e275]:
                  - paragraph [ref=e276]: Account
                  - button "Profile" [ref=e277] [cursor=pointer]:
                    - img [ref=e278]
                    - generic [ref=e282]: Profile
                  - button "Security" [ref=e283] [cursor=pointer]:
                    - img [ref=e284]
                    - generic [ref=e286]: Security
                  - button "Sessions" [ref=e287] [cursor=pointer]:
                    - img [ref=e288]
                    - generic [ref=e291]: Sessions
                - generic [ref=e292]:
                  - paragraph [ref=e293]: Preferences
                  - button "Appearance" [ref=e294] [cursor=pointer]:
                    - img [ref=e295]
                    - generic [ref=e298]: Appearance
                  - button "Language & region" [ref=e299] [cursor=pointer]:
                    - img [ref=e300]
                    - generic [ref=e302]: Language & region
                - generic [ref=e303]:
                  - paragraph [ref=e304]: Advanced
                  - button "Account information" [ref=e305] [cursor=pointer]:
                    - img [ref=e306]
                    - generic [ref=e309]: Account information
              - region "Language & region" [ref=e310]:
                - generic "Language & region" [ref=e311]:
                  - generic [ref=e312]:
                    - generic [ref=e313]:
                      - generic [ref=e314]: Interface language
                      - generic [ref=e315]:
                        - combobox "Interface language" [ref=e316] [cursor=pointer]:
                          - option "English (United States)" [selected]
                          - option "English (United Kingdom)"
                          - option "العربية (السعودية)"
                          - option "Français (France)"
                          - option "Deutsch (Deutschland)"
                          - option "Español (España)"
                        - img
                    - paragraph [ref=e317]: English is fully localized. Other languages set formatting and locale preferences; full interface translation may be partial.
                    - generic [ref=e318]:
                      - generic [ref=e319]: Time zone
                      - generic [ref=e321]:
                        - img [ref=e322]
                        - combobox "Time zone" [ref=e325]: Asia/Riyadh
                        - img [ref=e326]
                      - paragraph [ref=e328]: "Current offset: GMT+3"
                    - generic [ref=e329]:
                      - generic [ref=e330]:
                        - generic [ref=e331]: Date format
                        - generic [ref=e332]:
                          - combobox "Date format" [ref=e333] [cursor=pointer]:
                            - option "2026-08-12 (ISO)" [selected]
                            - option "12/08/2026 (Day first)"
                            - option "08/12/2026 (Month first)"
                            - option "12 Aug 2026"
                          - img
                      - generic [ref=e334]:
                        - generic [ref=e335]: Time format
                        - generic [ref=e336]:
                          - combobox "Time format" [ref=e337] [cursor=pointer]:
                            - option "24-hour (14:30)" [selected]
                            - option "12-hour (2:30 PM)"
                          - img
                    - generic [ref=e338]:
                      - generic [ref=e339]: First day of week
                      - generic [ref=e340]:
                        - combobox "First day of week" [ref=e341] [cursor=pointer]:
                          - option "Monday" [selected]
                          - option "Sunday"
                          - option "Saturday"
                        - img
                  - button "Save changes" [disabled] [ref=e344]:
                    - img [ref=e345]
                    - generic [ref=e347]: Save changes
    - generic [ref=e348]:
      - status [ref=e349]: Preferences saved. Your language and region settings were saved.
      - alert
  - region "Notifications" [ref=e350]:
    - generic [ref=e351]:
      - img [ref=e352]
      - generic [ref=e355]:
        - generic [ref=e356]: Preferences saved
        - generic [ref=e357]: Your language and region settings were saved.
      - button "Dismiss" [ref=e358] [cursor=pointer]:
        - img [ref=e359]
    - generic [ref=e361]:
      - img [ref=e362]
      - generic [ref=e365]:
        - generic [ref=e366]: Preferences saved
        - generic [ref=e367]: Your language and region settings were saved.
      - button "Dismiss" [ref=e368] [cursor=pointer]:
        - img [ref=e369]
```

# Test source

```ts
  1   | import fs from 'node:fs'
  2   | import path from 'node:path'
  3   | import { expect, resetClientState, signInAs, test } from './fixtures'
  4   | import { browserFixtures } from './personas'
  5   | 
  6   | test.setTimeout(120_000)
  7   | 
  8   | const csvPath = path.resolve('tests', 'e2e', 'data', 'b8_5_certification.csv')
  9   | const xlsxPath = path.resolve('tests', 'e2e', 'data', 'sales_certification.xlsx')
  10  | 
  11  | async function tenantHeaders(page: Parameters<typeof signInAs>[0]) {
  12  |   return page.evaluate(() => {
  13  |     const tenancy = JSON.parse(localStorage.getItem('vip.tenancy.preference') ?? '{}') as {
  14  |       orgId?: string
  15  |       wsId?: string
  16  |     }
  17  |     const csrf =
  18  |       document.cookie
  19  |         .split('; ')
  20  |         .find((item) => item.startsWith('vip_csrf_token='))
  21  |         ?.split('=')[1] ?? ''
  22  |     return {
  23  |       'Content-Type': 'application/json',
  24  |       'X-Organization-ID': tenancy.orgId ?? '',
  25  |       'X-Workspace-ID': tenancy.wsId ?? '',
  26  |       'X-CSRF-Token': decodeURIComponent(csrf),
  27  |     }
  28  |   })
  29  | }
  30  | 
  31  | async function api(
  32  |   page: Parameters<typeof signInAs>[0],
  33  |   method: string,
  34  |   url: string,
  35  |   body?: unknown,
  36  | ): Promise<{ status: number; json: unknown }> {
  37  |   const headers = await tenantHeaders(page)
  38  |   return page.evaluate(
  39  |     async ({ method, url, headers, body }) => {
  40  |       const response = await fetch(url, {
  41  |         method,
  42  |         credentials: 'include',
  43  |         headers,
  44  |         body: body == null ? undefined : JSON.stringify(body),
  45  |       })
  46  |       const text = await response.text()
  47  |       let json: unknown = text
  48  |       try {
  49  |         json = text ? JSON.parse(text) : null
  50  |       } catch {
  51  |         json = text
  52  |       }
  53  |       return { status: response.status, json }
  54  |     },
  55  |     { method, url, headers, body },
  56  |   )
  57  | }
  58  | 
  59  | /** IANA labels are the zone id with underscores turned into spaces. "UTC" is not
  60  |  * guaranteed to appear in `Intl.supportedValuesOf('timeZone')`. */
  61  | async function chooseTimezone(page: Parameters<typeof signInAs>[0], query: string, option: RegExp): Promise<void> {
  62  |   const timezone = page.getByRole('combobox', { name: 'Time zone' })
  63  |   await expect(timezone).toBeVisible()
  64  |   await timezone.click()
  65  |   await timezone.fill(query)
  66  |   const match = page.getByRole('option', { name: option })
  67  |   await expect(match).toBeVisible({ timeout: 8_000 })
  68  |   await match.click()
  69  |   await page.keyboard.press('Escape')
  70  | }
  71  | 
  72  | test('CERT-P2-001 timezone combobox persists Asia/Riyadh across reload', async ({ authenticatedPage: page }) => {
  73  |   await page.goto('/settings/language')
  74  |   const timezone = page.getByRole('combobox', { name: 'Time zone' })
  75  |   await expect(timezone).toBeVisible()
  76  |   const current = await timezone.inputValue()
  77  |   if (/Asia\/Riyadh/.test(current)) {
  78  |     await chooseTimezone(page, 'London', /Europe\/London/)
  79  |     await page.getByRole('button', { name: 'Save changes' }).click()
  80  |     await expect(page.getByText('Your language and region settings were saved.', { exact: true })).toBeVisible()
  81  |   }
  82  |   await chooseTimezone(page, 'Riyadh', /Asia\/Riyadh/)
  83  |   await expect(timezone).toHaveValue(/Asia\/Riyadh/)
  84  |   await page.getByRole('button', { name: 'Save changes' }).click()
> 85  |   await expect(page.getByText('Your language and region settings were saved.', { exact: true })).toBeVisible()
      |                                                                                                  ^ Error: expect(locator).toBeVisible() failed
  86  |   await page.reload()
  87  |   await expect(page.getByRole('combobox', { name: 'Time zone' })).toHaveValue(/Asia\/Riyadh/)
  88  | })
  89  | 
  90  | test('CERT-P2-004 success toast has one visual region and one live announcement path', async ({
  91  |   authenticatedPage: page,
  92  | }) => {
  93  |   await page.goto('/notifications')
  94  |   await expect(page.getByText('Notification preferences')).toBeVisible()
  95  |   const billing = page.locator('.ntf__pref-row', { hasText: 'Billing' }).getByRole('switch')
  96  |   await billing.click()
  97  |   await page.getByRole('button', { name: 'Save preferences' }).click()
  98  |   const visual = page.getByRole('region', { name: 'Notifications' }).locator('.vip-toast')
  99  |   await expect(visual.filter({ hasText: 'Notification preferences saved' })).toHaveCount(1)
  100 |   await expect(page.getByRole('region', { name: 'Notifications' })).not.toHaveAttribute('aria-live', /./)
  101 |   await expect(page.locator('[aria-live="polite"]').filter({ hasText: 'Notification preferences saved' })).toHaveCount(
  102 |     1,
  103 |   )
  104 | })
  105 | 
  106 | test('CERT-P2-003 dataset catalog pager walks pages, page-size, and filter reset', async ({
  107 |   authenticatedPage: page,
  108 | }) => {
  109 |   await page.goto('/datasets')
  110 |   const count = page.locator('.dl__count')
  111 |   await expect(count).toBeVisible()
  112 |   await expect.poll(async () => ((await count.textContent()) ?? '').trim(), { timeout: 20_000 }).not.toBe('0 of 0')
  113 |   const summary = ((await count.textContent()) ?? '').trim()
  114 |   const total = Number(/of\s+(\d+)\s*$/.exec(summary)?.[1] ?? '0')
  115 |   expect(total, `catalog total from "${summary}"`).toBeGreaterThan(0)
  116 | 
  117 |   await page.getByLabel('Datasets per page').selectOption('25')
  118 |   const pageOf = page.locator('.dl__page-of')
  119 |   await expect(pageOf).toContainText('Page 1 of')
  120 |   const totalPages = Number(/Page 1 of (\d+)/.exec((await pageOf.textContent()) ?? '')?.[1] ?? '1')
  121 |   const next = page.getByRole('button', { name: 'Next page' })
  122 |   const previous = page.getByRole('button', { name: 'Previous page' })
  123 |   if (totalPages > 1) {
  124 |     await next.click()
  125 |     await expect(pageOf).toContainText('Page 2 of')
  126 |     await previous.click()
  127 |     await expect(pageOf).toContainText('Page 1 of')
  128 |     const walk = Math.min(totalPages, 8)
  129 |     for (let pageNumber = 1; pageNumber < walk; pageNumber += 1) {
  130 |       await expect(next).toBeEnabled()
  131 |       await next.click()
  132 |       await expect(pageOf).toContainText(`Page ${pageNumber + 1} of`)
  133 |     }
  134 |     if (walk === totalPages) {
  135 |       await expect(next).toBeDisabled()
  136 |       await expect(previous).toBeEnabled()
  137 |       await previous.click()
  138 |     }
  139 |   }
  140 | 
  141 |   await page.getByPlaceholder('Search dataset name or source').fill('__no_such_dataset__')
  142 |   await expect.poll(async () => (await count.textContent())?.trim(), { timeout: 15_000 }).toMatch(/^0 of 0$/)
  143 |   await page.getByPlaceholder('Search dataset name or source').fill('')
  144 |   await expect
  145 |     .poll(async () => (await count.textContent())?.trim(), { timeout: 15_000 })
  146 |     .toMatch(new RegExp(`of ${total}$`))
  147 |   await page.getByLabel('Dataset status').selectOption('active')
  148 |   await page.getByLabel('Dataset status').selectOption('all')
  149 |   await expect
  150 |     .poll(async () => (await count.textContent())?.trim(), { timeout: 15_000 })
  151 |     .toMatch(new RegExp(`of ${total}$`))
  152 | })
  153 | 
  154 | test('DATASET-P2-IMPORT-CONNECTION does not auto-pick the first of many connections', async ({
  155 |   authenticatedPage: page,
  156 | }) => {
  157 |   await page.goto('/datasets')
  158 |   await page.getByRole('button', { name: 'Import CSV' }).click()
  159 |   const dialog = page.getByRole('dialog', { name: 'Import CSV dataset' })
  160 |   await expect(dialog).toBeVisible()
  161 |   if (
  162 |     await dialog
  163 |       .getByText('No eligible connections available')
  164 |       .isVisible()
  165 |       .catch(() => false)
  166 |   ) {
  167 |     await expect(dialog.getByRole('button', { name: 'Import and catalog' })).toBeDisabled()
  168 |     return
  169 |   }
  170 |   const connection = dialog.getByLabel('Connection')
  171 |   await expect(connection).toBeVisible()
  172 |   const optionCount = await connection.locator('option:not([disabled])').count()
  173 |   const selected = await connection.inputValue()
  174 |   if (optionCount <= 1) {
  175 |     expect(selected.length).toBeGreaterThan(0)
  176 |   } else {
  177 |     expect(selected).toBe('')
  178 |     await expect(dialog.getByRole('button', { name: 'Import and catalog' })).toBeDisabled()
  179 |     const connectionB = connection.locator('option:not([disabled])').nth(1)
  180 |     const valueB = await connectionB.getAttribute('value')
  181 |     expect(valueB).toBeTruthy()
  182 |     await connection.selectOption(valueB!)
  183 |   }
  184 |   await dialog.getByLabel('Upload CSV or XLSX file from your device').setInputFiles(csvPath)
  185 |   await expect(dialog.getByText('b8_5_certification.csv')).toBeVisible()
```