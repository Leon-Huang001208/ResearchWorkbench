// Playwright test to verify the placeholder text "代码/名称/简拼"
const { test, expect } = require('@playwright/test');

test('Verify asset analysis placeholder text is "代码/名称/简拼"', async ({ page }) => {
  // 1. Navigate to homepage
  await page.goto('http://127.0.0.1:8000/');

  // 2. Wait for page to load
  await page.waitForSelector('nav, [data-i18n="nav.asset-analysis"]', { timeout: 10000 });

  // 3. Click on Asset Analysis section
  await page.getByText(/资产分析|Asset Analysis/).click();

  // 4. Wait for the asset analysis panel to load
  await page.waitForSelector('[data-i18n-placeholder="asset.code_placeholder"]', { timeout: 10000 });

  // 5. Find the input element and get its placeholder attribute
  const input = page.locator('[data-i18n-placeholder="asset.code_placeholder"]');
  const placeholder = await input.getAttribute('placeholder');

  // 6. Verify the placeholder text
  expect(placeholder).toBe('代码/名称/简拼');
  console.log(`✓ Placeholder verified: "${placeholder}"`);

  // 7. Take screenshot
  await page.screenshot({
    path: '/Users/leon/Desktop/Projects/AlphaFoundry/tests/e2e/screenshots/asset-placeholder-verification.png',
    fullPage: true
  });
  console.log('✓ Screenshot saved');
});