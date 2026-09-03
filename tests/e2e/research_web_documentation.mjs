/** Real, read-only settings → isolated diagram navigation acceptance. */
import assert from 'node:assert/strict';
import {mkdir, writeFile, appendFile} from 'node:fs/promises';
import path from 'node:path';

const origin = new URL(process.env.ALPHAFOUNDRY_WEB_URL || 'http://127.0.0.1:8088');
if (origin.protocol !== 'http:' || !['localhost','127.0.0.1'].includes(origin.hostname)) throw new Error('Local Web only');
const output = path.resolve('outputs/research-web-ui-acceptance/documentation');
const receipt = {status:'running', steps:[], requests:[]};
let browser;
try {
  await mkdir(output,{recursive:true}); await mkdir('logs',{recursive:true});
  const {chromium} = await import(process.env.ALPHAFOUNDRY_PLAYWRIGHT_MODULE || 'playwright-core');
  browser = await chromium.launch({headless:true,executablePath:process.env.CHROME_EXECUTABLE_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
  const context = await browser.newContext({viewport:{width:1440,height:900}});
  await context.route('**/*',route => ['GET','HEAD'].includes(route.request().method()) ? route.continue() : route.abort());
  context.on('response',response=>{
    if(response.url().includes('/documentation/')) receipt.requests.push({path:new URL(response.url()).pathname,status:response.status(),site:response.request().headers()['sec-fetch-site']});
  });
  const page = await context.newPage();
  await page.goto(`${origin.origin}/?acceptance=docs#/settings`);
  const link = page.getByRole('link',{name:'打开架构文档 ↗',exact:true});
  await link.waitFor();
  assert.equal(await link.getAttribute('rel'),'noopener noreferrer');
  const popupPromise=context.waitForEvent('page'); await link.click();
  const docs=await popupPromise; await docs.waitForLoadState('domcontentloaded');
  await docs.getByRole('heading',{name:'从研究问题，到真实文件交付',exact:true}).waitFor();
  assert.equal(await docs.locator('.card').count(),8); receipt.steps.push('settings_popup_eight_diagrams');
  await docs.screenshot({path:path.join(output,'index.png'),fullPage:true});
  for(const filename of ['01-deployment.html','08-iteration-docs.html']) {
    await docs.goto(`${origin.origin}/api/research/documentation/index.html`);
    const responsePromise=docs.waitForResponse(r=>new URL(r.url()).pathname.endsWith(`/${filename}`));
    await docs.locator(`a[href="${filename}"]`).click(); const response=await responsePromise;
    assert.equal(response.status(),200,`Sandbox index navigation must load ${filename}`);
    const csp=response.headers()['content-security-policy'];
    assert.ok(csp.includes('sandbox allow-scripts')&&!csp.includes('allow-same-origin'));
    await docs.waitForLoadState('domcontentloaded');
    const buttons=docs.getByRole('button'); assert.ok(await buttons.count()>0,'Viewer controls rendered');
    const theme=docs.getByRole('button',{name:'Toggle color theme',exact:true});
    const previous=await theme.innerText(); await theme.click();
    assert.notEqual(await theme.innerText(),previous,'Opaque sandbox must retain real theme interaction');
    if(filename==='08-iteration-docs.html') {
      await docs.getByRole('button',{name:'Focus 架构对应清单, 源码 · API · 文档 · 图 · 测试, Architecture component',exact:true}).click();
      await docs.getByRole('region',{name:'架构对应清单',exact:true}).waitFor();
      await docs.getByRole('button',{name:'Close semantic passport',exact:true}).click();
      receipt.steps.push('viewer_theme_and_node_details');
    }
    await docs.screenshot({path:path.join(output,filename.replace('.html','.png')),fullPage:true});
    receipt.steps.push(`sandbox_navigation_${filename}`);
  }
  receipt.status='passed';
} catch(error) {
  receipt.status='failed';receipt.error=String(error);process.exitCode=1;
} finally {
  await browser?.close();
  await writeFile(path.join(output,'receipt.json'),JSON.stringify(receipt,null,2));
  await appendFile('logs/research-web-documentation-e2e.jsonl',JSON.stringify({time:new Date().toISOString(),status:receipt.status,steps:receipt.steps,error:receipt.error})+'\n');
  console.log(JSON.stringify(receipt,null,2));
}
