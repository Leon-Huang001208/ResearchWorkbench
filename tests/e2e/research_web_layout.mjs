/** Read-only live Web layout acceptance. No model submission or permission changes. */
import assert from 'node:assert/strict';
import {mkdir, writeFile} from 'node:fs/promises';
import path from 'node:path';

const origin = new URL(process.env.RESEARCH_WEB_URL || 'http://127.0.0.1:8088');
if (!['127.0.0.1', 'localhost'].includes(origin.hostname) || origin.protocol !== 'http:') {
  throw new Error('Layout acceptance is limited to a local HTTP deployment');
}
const output = path.resolve('outputs/research-web-ui-acceptance');
const logs = path.resolve('logs/research-web-layout.jsonl');
const viewports = [[1440, 900], [1600, 1000], [1920, 1080], [820, 1180], [390, 844]];
const results = [];
let browser;

async function assertContained(page) {
  const metrics = await page.evaluate(() => ({
    width: innerWidth, scrollWidth: document.documentElement.scrollWidth,
    overflowing: [...document.querySelectorAll('button,input,select,textarea')]
      .filter(el => el.getClientRects().length && getComputedStyle(el).visibility !== 'hidden')
      .filter(el => {const r = el.getBoundingClientRect(); return r.left < -1 || r.right > innerWidth + 1;})
      .map(el => el.getAttribute('aria-label') || el.textContent.trim().slice(0, 40))
  }));
  assert.ok(metrics.scrollWidth <= metrics.width, `Horizontal page overflow: ${JSON.stringify(metrics)}`);
  assert.deepEqual(metrics.overflowing, [], 'Interactive controls must remain within viewport');
  return metrics;
}

async function run() {
  await mkdir(output, {recursive: true});
  await mkdir(path.dirname(logs), {recursive: true});
  const {chromium} = await import(process.env.RESEARCH_PLAYWRIGHT_MODULE || 'playwright-core');
  browser = await chromium.launch({headless: true,
    executablePath: process.env.CHROME_EXECUTABLE_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
  for (const [width,height] of viewports) {
    const context = await browser.newContext({viewport: {width,height}});
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.name));
    await page.route('**/*', async route => {
      const request = route.request();
      if (!['GET', 'HEAD'].includes(request.method())) {
        errors.push(`blocked_mutation_${request.method()}`);
        await route.abort('blockedbyclient');
        return;
      }
      await route.continue();
    });
    page.on('request', request => {
      if (!['GET','HEAD'].includes(request.method())) errors.push(`unexpected_mutation_${request.method()}`);
    });
    try {
      for (const mode of ['fingpt','claw','skills']) {
        await page.goto(`${origin.origin}/?acceptance=layout&mode=${mode}#/${mode}`, {waitUntil:'domcontentloaded'});
        await page.locator('#app > .app-shell').waitFor({timeout:15000});
        if (width > 1050) {
          assert.equal(await page.getByRole('navigation',{name:'产品主导航',exact:true}).count(), 1, `Primary navigation must render (${width}×${height}, ${mode})`);
        } else {
          await page.getByRole('button',{name:'打开导航',exact:true}).waitFor();
          assert.equal(await page.getByRole('navigation',{name:'产品主导航',exact:true}).count(), 0, `Narrow layouts must keep navigation in its drawer until requested (${width}×${height}, ${mode})`);
        }
        if (width >= 1440) {
          const labelVisible = await page.getByRole('link',{name:'FinGPT',exact:true}).evaluate(el =>
            [...el.querySelectorAll('span')].some(span => {
              const r = span.getBoundingClientRect();
              return span.textContent.trim() === 'FinGPT' && r.width > 20 && r.height > 8;
            }));
          assert.equal(labelVisible, true, `Desktop rail must have a visible FinGPT label (${width}×${height}, ${mode})`);
        }
        const metrics = await assertContained(page);
        if (mode !== 'skills') {
          const shortcut=page.getByRole('region',{name:mode==='claw'?'研究步骤模板快捷入口':'研究 Skill 快捷入口',exact:true});
          await shortcut.waitFor();
          const expected=mode==='claw'?['基金资料准备与受限评价','公司资料研究与报告交付']:['资料解读','公司研究','行业研究','基金评价'];
          for (const name of expected) await shortcut.getByRole('heading',{name,exact:true}).waitFor();
          const directory=shortcut.locator('details.quick-directory');
          if (!await directory.evaluate(element => element.open)) {
            await directory.locator('summary').click();
          }
          const filter=page.locator('#quick-category');
          await filter.waitFor({state:'visible'});
          const categories=await filter.locator('option').evaluateAll(items=>items.map(item=>item.value));
          if(categories.length>1) {
            await filter.selectOption(categories[1]);
            assert.ok(await shortcut.locator('[data-skill-shortcut]').count()>0);
            await filter.selectOption(categories[0]);
          }
          assert.equal(await page.getByRole('complementary',{name:'研究活动、资料与文件',exact:true}).isVisible(),false,
            'Landing must not display an empty research panel');
          await page.getByRole('button',{name:'选择 Skill 或 Workflow',exact:true}).click();
          await page.getByRole('listbox',{name:'匹配的研究能力',exact:true}).waitFor();
          assert.ok(await page.getByRole('option').count() >= 4);
          await page.getByRole('textbox',{name:mode==='claw'?'任务目标或补充信息':'研究问题',exact:true}).press('Escape');
          await page.getByRole('listbox',{name:'匹配的研究能力',exact:true}).waitFor({state:'hidden',timeout:1500});
          const prompt=page.getByRole('textbox',{name:mode==='claw'?'任务目标或补充信息':'研究问题',exact:true});
          await page.getByRole('button',{name:'选择 Skill 或 Workflow',exact:true}).click();
          await prompt.press('ArrowDown'); await prompt.press('Enter');
          await page.getByRole('listbox',{name:'匹配的研究能力',exact:true}).waitFor({state:'hidden',timeout:1500});
          await page.getByRole('button',{name:'移除所选能力',exact:true}).waitFor();
          // All builtins can enter both research-mode drafts without execution.
          for (const name of ['资料解读','公司研究','行业研究','基金评价']) {
            await page.locator('details.capability-picker > summary').click();
            await page.getByRole('combobox',{name:'使用 Skill 或 Workflow',exact:true}).selectOption({label:name});
            await page.locator('.capability-chips > span').filter({hasText:`${name} · v`}).waitFor();
          }
          await page.getByRole('button',{name:'移除所选能力',exact:true}).click();
          if (width <= 1050) {
            await page.getByRole('button',{name:'打开导航',exact:true}).click();
            const sidebarName = mode === 'claw' ? 'Claw 会话与工作空间侧栏' : 'FinGPT 会话侧栏';
            const sidebar = page.getByRole('complementary',{name:sidebarName,exact:true});
            await sidebar.waitFor();
            assert.notEqual(await sidebar.getAttribute('aria-hidden'), 'true');
            await page.getByRole('button',{name:'打开导航',exact:true}).click();
          }
        } else {
          await page.getByRole('searchbox',{name:'搜索能力名称和简介',exact:true}).fill('基金');
          await page.locator('.skill-card').getByRole('heading',{name:'基金评价',exact:true}).waitFor();
          await page.getByRole('searchbox',{name:'搜索能力名称和简介',exact:true}).fill('不存在的验收能力-xyz');
          await page.getByRole('heading',{name:'没有匹配的能力',exact:true}).waitFor();
          await page.getByRole('searchbox',{name:'搜索能力名称和简介',exact:true}).fill('');
          await page.locator('#cap-source').selectOption('builtin');
          for (const name of ['资料解读','公司研究','行业研究','基金评价']) {
            await page.locator('.skill-card').filter({has:page.getByRole('heading',{name,exact:true})}).getByRole('button',{name:'查看详情',exact:true}).click();
            await page.getByRole('region',{name:'能力详情',exact:true}).getByRole('heading',{name,exact:true}).waitFor();
            await page.getByRole('button',{name:'关闭详情',exact:true}).click();
          }
          await page.getByRole('tab',{name:'Workflow',exact:true}).click();
          await page.getByRole('heading',{name:'基金资料准备与受限评价',exact:true}).waitFor();
          await page.getByRole('tab',{name:'Tool',exact:true}).click();
          await page.getByText('只读目录声明，不代表实例在线、凭据齐备或已获审批。工具选择不改变任何原生权限。',{exact:true}).waitFor();
          assert.equal(await page.getByRole('button',{name:'手动新建',exact:true}).count(),0, `Capability catalog must not expose a fake create button (${width}×${height})`);
          await page.getByRole('tab',{name:'Skill',exact:true}).click();
        }
        const mobileSearch=page.getByRole('button',{name:'打开全局搜索',exact:true});
        if (await mobileSearch.isVisible()) await mobileSearch.click();
        const search=page.getByRole('searchbox',{name:'搜索会话标题和能力名称或简介',exact:true});
        await search.fill('公司研究');
        await page.locator('.global-results').getByRole('option').filter({hasText:'公司研究'}).first().waitFor();
        await assertContained(page);
        await search.fill('');
        const closeSearch=page.getByRole('button',{name:'关闭全局搜索',exact:true});
        if (await closeSearch.isVisible()) await closeSearch.click();
        await page.screenshot({path:path.join(output, `${mode}-${width}x${height}.png`),fullPage:true});
        results.push({mode,width,height,status:'passed',metrics});
      }
      assert.deepEqual(errors, [], 'No script errors or unexpected writes');
    } finally { await context.close(); }
  }
}

try {
  await run();
  await writeFile(path.join(output,'receipt.json'), JSON.stringify({status:'passed',results},null,2));
  await writeFile(logs, JSON.stringify({event:'research_layout_acceptance',status:'passed',checks:results.length})+'\n');
  console.log(`research layout: ${results.length} page/viewport checks passed; no model calls`);
} catch(error) {
  await mkdir(output,{recursive:true});
  await mkdir(path.dirname(logs),{recursive:true});
  await writeFile(path.join(output,'receipt.json'),JSON.stringify({status:'failed',error:error.message,results},null,2));
  await writeFile(logs,JSON.stringify({event:'research_layout_acceptance',status:'failed',error_type:error.name})+'\n');
  console.error(error.message);
  process.exitCode=1;
} finally { if(browser) await browser.close(); }
