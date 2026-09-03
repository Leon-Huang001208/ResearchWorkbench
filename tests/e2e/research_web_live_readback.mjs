/** Read-only recheck of the controller's real model acceptance session. */
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {mkdir, readFile, writeFile} from 'node:fs/promises';
import path from 'node:path';

const origin = new URL(process.env.ALPHAFOUNDRY_WEB_URL || 'http://127.0.0.1:8088');
if (!['localhost', '127.0.0.1'].includes(origin.hostname) || origin.protocol !== 'http:') {
  throw new Error('Live readback is limited to a local deployment');
}
const session = '82f9904a-4c4c-4d35-a1cd-93985437f488';
const file = '97000c47047feb45a14f6436';
const output = path.resolve('outputs/research-web-ui-acceptance/live-readback');
const log = path.resolve('logs/research-web-live-readback.jsonl');
let browser;
try {
  await mkdir(output, {recursive: true});
  await mkdir(path.dirname(log), {recursive: true});
  const {chromium} = await import(process.env.ALPHAFOUNDRY_PLAYWRIGHT_MODULE || 'playwright-core');
  browser = await chromium.launch({headless: true,
    executablePath: process.env.CHROME_EXECUTABLE_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
  const context = await browser.newContext({viewport:{width:820,height:1180},acceptDownloads:true});
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', error => errors.push(error.name));
  await page.route('**/*', async route => {
    if (!['GET', 'HEAD'].includes(route.request().method())) {
      errors.push(`blocked_${route.request().method()}`);
      await route.abort('blockedbyclient');
    } else await route.continue();
  });
  await page.goto(`${origin.origin}/?acceptance=readback#/fingpt?session=${session}`);
  await page.getByRole('heading',{name:'UI 验收 · 多轮与 HTML 文件',exact:true}).waitFor();
  assert.equal(await page.locator('[aria-label="会话消息"] article').count(),10);
  await page.reload();
  await page.getByRole('heading',{name:'UI 验收 · 多轮与 HTML 文件',exact:true}).waitFor();
  assert.equal(await page.locator('[aria-label="会话消息"] article').count(),10);
  await page.getByRole('button',{name:'活动与文件',exact:true}).click();
  await page.getByRole('region',{name:'文件交付检查',exact:true}).getByText('本任务未要求文件',{exact:true}).waitFor();
  await page.screenshot({path:path.join(output,'cold-recovery.png'),fullPage:true});
  await page.getByRole('tab',{name:'文件',exact:true}).click();
  const row = page.locator('.file-card').filter({hasText:'ui-delivery-checked.html'});
  await row.getByRole('button',{name:'预览',exact:true}).click();
  const iframe = page.locator(`iframe[src$="/files/${file}/preview"]`);
  assert.equal(await iframe.getAttribute('sandbox'),'');
  await page.frameLocator(`iframe[src$="/files/${file}/preview"]`).getByRole('heading',{name:'交付验收',exact:true}).waitFor();
  await page.screenshot({path:path.join(output,'html-preview.png'),fullPage:true});
  const downloadPromise = page.waitForEvent('download');
  await row.getByRole('link',{name:'下载',exact:true}).click();
  const download = await downloadPromise;
  assert.equal(download.suggestedFilename(),'ui-delivery-checked.html');
  const target = path.join(output,'ui-delivery-checked.html');
  await download.saveAs(target);
  const bytes = await readFile(target);
  const sha256 = createHash('sha256').update(bytes).digest('hex');
  assert.equal(sha256,'c699a5a67f6d45405baa5c64886a519d28285db8989686011f82544d3db89d8b');
  assert.match(bytes.toString('utf8'),/20\.0/);
  assert.deepEqual(errors,[]);
  await writeFile(path.join(output,'receipt.json'),JSON.stringify({status:'passed',session,file,bytes:bytes.length,sha256,checks:['reload_history_10_messages','latest_delivery_not_required','sandbox_preview','browser_download_hash'],modelCalls:0},null,2));
  await writeFile(log,JSON.stringify({event:'live_readback',status:'passed',checks:4})+'\n');
  console.log('Live readback: history, delivery, isolated preview and browser download passed');
} catch(error) {
  await mkdir(output,{recursive:true});
  await mkdir(path.dirname(log),{recursive:true});
  await writeFile(path.join(output,'receipt.json'),JSON.stringify({status:'failed',error:error.message},null,2));
  await writeFile(log,JSON.stringify({event:'live_readback',status:'failed',error_type:error.name})+'\n');
  console.error(error.message);
  process.exitCode=1;
} finally {if(browser) await browser.close();}
