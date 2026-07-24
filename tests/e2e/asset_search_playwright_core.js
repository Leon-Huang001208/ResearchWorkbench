#!/usr/bin/env node
/*
 * 资产分析候选搜索浏览器回归测试。
 *
 * 依赖本机已有 playwright-core 和 Chrome，不依赖 @playwright/test。
 * 运行前请先启动 Web 服务，例如：
 *   python -m uvicorn app.api.main:app --host 127.0.0.1 --port 8002
 */
import fs from 'node:fs';
import path from 'node:path';

async function loadChromium() {
  try {
    return (await import('playwright-core')).chromium;
  } catch (error) {
    console.error(
      [
        '缺少 playwright-core，无法运行资产搜索浏览器回归。',
        '本脚本不依赖 @playwright/test，但需要 Node 能 resolve playwright-core。',
        `原始错误: ${error.message}`,
      ].join('\n')
    );
    process.exit(1);
  }
}

const BASE_URL = process.env.ALPHAFOUNDRY_WEB_URL || 'http://127.0.0.1:8002';
const CHROME_PATH =
  process.env.CHROME_EXECUTABLE_PATH ||
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';

function analysisCardResponse(canonicalId, name) {
  return {
    canonical_id: canonicalId,
    basic_info: { symbol: canonicalId, name, market_cap: null },
    current_price: null,
    price_change: null,
    price_change_pct: null,
    volume: null,
    amount: null,
    turnover: null,
    high_52w: null,
    low_52w: null,
    financial: {},
    price_bars: [],
    capital_flow: null,
    top_10_shareholders: [],
    industry: null,
    recent_events: [],
    macro_sensitivity: null,
  };
}

async function openAssetPage(page) {
  await page.goto(BASE_URL, { waitUntil: 'domcontentloaded' });
  await page.click('.activity-btn[data-section="asset-analysis"]');
  await page.waitForSelector('#section-asset-analysis.active #asset-code', { timeout: 10000 });
}

async function assertDropdownContains(page, expectedParts) {
  await page.waitForSelector('#asset-search-dropdown:not(.hidden) .asset-result-item', {
    timeout: 10000,
  });
  const text = await page.locator('#asset-search-dropdown').innerText();
  for (const part of expectedParts) {
    if (!text.includes(part)) {
      throw new Error(`候选框缺少 ${part}: ${text}`);
    }
  }
  if (text.includes('没有匹配')) {
    throw new Error(`候选框错误显示没有匹配: ${text}`);
  }
  return text;
}

async function runNormalSearchFlow(page) {
  await page.route('**/api/assets/analysis-card', async route => {
    const request = route.request();
    let canonicalId = '600519.SH';
    try {
      canonicalId = JSON.parse(request.postData() || '{}').canonical_id || canonicalId;
    } catch (error) {
      console.warn(`analysis-card post body parse failed: ${error.message}`);
    }
    const name = canonicalId === '399436.SZ' ? '绿色煤炭' : '贵州茅台';
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(analysisCardResponse(canonicalId, name)),
    });
  });

  await openAssetPage(page);

  const input = page.locator('#asset-code');
  await input.fill('gzmt');
  await assertDropdownContains(page, ['600519.SH', '贵州茅台']);

  await input.press('Enter');
  await page.waitForSelector('#asset-result:not(.hidden)', { timeout: 10000 });
  const selectedValue = await input.inputValue();
  if (!selectedValue.includes('600519.SH') || !selectedValue.includes('贵州茅台')) {
    throw new Error(`Enter 未选中当前候选: ${selectedValue}`);
  }

  await input.fill('lsmt');
  await assertDropdownContains(page, ['399436.SZ', '绿色煤炭']);
}

async function runSearchOutageFallback(browser) {
  const context = await browser.newContext({ viewport: { width: 1000, height: 720 } });
  const page = await context.newPage();
  await page.route('**/api/search**', route =>
    route.fulfill({
      status: 503,
      contentType: 'application/json',
      body: JSON.stringify({ detail: 'forced search outage' }),
    })
  );
  await page.route('**/api/assets/analysis-card', route =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(analysisCardResponse('600519.SH', '贵州茅台')),
    })
  );

  await openAssetPage(page);
  await page.fill('#asset-code', 'gzmt');
  const text = await assertDropdownContains(page, ['600519.SH', '贵州茅台']);
  if (!text.includes('搜索服务异常')) {
    throw new Error(`搜索异常兜底状态未提示: ${text}`);
  }
  await context.close();
}

async function main() {
  const chromium = await loadChromium();
  if (!fs.existsSync(CHROME_PATH)) {
    throw new Error(
      [
        `找不到 Chrome 可执行文件: ${CHROME_PATH}`,
        '请安装 Google Chrome，或设置 CHROME_EXECUTABLE_PATH 指向可用的 Chromium/Chrome。',
      ].join('\n')
    );
  }
  const screenshotDir = path.resolve('output/playwright');
  fs.mkdirSync(screenshotDir, { recursive: true });

  const browser = await chromium.launch({
    headless: true,
    executablePath: CHROME_PATH,
  });
  const context = await browser.newContext({ viewport: { width: 1280, height: 860 } });
  const page = await context.newPage();
  const browserErrors = [];
  page.on('console', msg => {
    if (msg.type() === 'error' && !msg.text().includes('favicon')) {
      browserErrors.push(msg.text());
    }
  });
  page.on('pageerror', err => browserErrors.push(String(err)));

  try {
    await runNormalSearchFlow(page);
    await page.screenshot({
      path: path.join(screenshotDir, 'asset-search-candidates.png'),
      fullPage: true,
    });
    await context.close();
    await runSearchOutageFallback(browser);
    if (browserErrors.length) {
      throw new Error(`浏览器控制台错误:\n${browserErrors.join('\n')}`);
    }
    console.log('asset search browser regression passed');
  } finally {
    await browser.close();
  }
}

main().catch(error => {
  console.error(error);
  process.exit(1);
});
