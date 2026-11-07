import { test, expect } from './fixtures'
import AxeBuilder from '@axe-core/playwright'

for (const width of [320, 360, 375, 390, 430, 768, 1024, 1280, 1440, 1920]) {
  test(`responsive clinical, patient, exams, detail and catalog at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 900 })
    for (const path of ['/clinical', '/exams', '/exams/demo-exam-01', '/catalog']) {
      await page.goto(path)
      await expect(page.locator('main h1')).toBeVisible()
      if (path === '/exams')
        await expect(
          page.getByRole('link', { name: 'Panel de laboratorio · DEMO', exact: true }),
        ).toBeVisible()
      expect(
        await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
        path,
      ).toBe(true)
    }
    await page.getByLabel('Vista de demostración').selectOption('patient')
    const menu = page.getByRole('button', { name: 'Abrir navegación', exact: true })
    if (await menu.isVisible()) await menu.click()
    await page.getByRole('link', { name: 'Vista principal', exact: true }).click()
    await expect(
      page.getByRole('heading', { name: 'Tu información, en perspectiva' }),
    ).toBeVisible()
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
    ).toBe(true)
    if ([320, 768, 1440].includes(width))
      await page.screenshot({ path: `test-results/continuity-${width}.png`, fullPage: true })
    if (width === 320)
      expect(
        (
          await new AxeBuilder({ page })
            .withTags(['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa'])
            .analyze()
        ).violations,
      ).toEqual([])
  })
}
test('touch landscape, menu focus/Escape and 200 percent equivalent reflow', async ({
  browser,
}) => {
  const context = await browser.newContext({
    viewport: { width: 844, height: 390 },
    hasTouch: true,
    isMobile: true,
    reducedMotion: 'reduce',
  })
  const page = await context.newPage()
  await page.goto('http://127.0.0.1:5173/exams')
  await expect(
    page.getByRole('link', { name: 'Panel de laboratorio · DEMO', exact: true }),
  ).toBeVisible()
  await page.setViewportSize({ width: 390, height: 844 })
  const menu = page.getByRole('button', { name: 'Abrir navegación', exact: true })
  await menu.tap()
  await expect(page.getByRole('link', { name: 'WellQ Portal de salud' })).toBeFocused()
  await page.keyboard.press('Escape')
  await expect(menu).toBeFocused()
  await expect(menu).toHaveAttribute('aria-expanded', 'false')
  const smallTargets = await page
    .locator('button:visible,select:visible,input:visible')
    .evaluateAll(
      (nodes) =>
        nodes.filter((node) => {
          const rect = node.getBoundingClientRect()
          return rect.width < 24 || rect.height < 24
        }).length,
    )
  expect(smallTargets).toBe(0)
  await context.close()
  const zoom = await browser.newContext({
    viewport: { width: 640, height: 450 },
    deviceScaleFactor: 2,
  })
  const zoomPage = await zoom.newPage()
  await zoomPage.goto('http://127.0.0.1:5173/exams')
  await expect(zoomPage.getByRole('heading', { name: 'Exámenes médicos' })).toBeVisible()
  expect(
    await zoomPage.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
  ).toBe(true)
  await zoom.close()
})
