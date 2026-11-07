import { test as base, expect } from '@playwright/test'
export const test = base.extend({
  page: async ({ page }, use) => {
    await page.route('**/health', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: '{"status":"ok"}' }),
    )
    await use(page)
  },
})
export { expect }
