/** Verify the real, user-reviewed Skill research without sending model requests. */
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {mkdir, readFile, writeFile} from 'node:fs/promises';
import path from 'node:path';

const origin = new URL(process.env.ALPHAFOUNDRY_WEB_URL || 'http://127.0.0.1:8088');
if (!['localhost', '127.0.0.1'].includes(origin.hostname) || origin.protocol !== 'http:') throw new Error('Local acceptance only');
const session = '7ee7b736-673a-4aff-8006-73de6c10b600';
const file = '3320abdf473d5e3d84d3df8f';
const capability = '1ba298cc4b754aee9496b7d1c5c78bf7';
const output = path.resolve('outputs/research-web-ui-acceptance/custom-skill');
const log = path.resolve('logs/research-web-custom-skill-readback.jsonl');
let browser;
try {
  await mkdir(output,{recursive:true}); await mkdir(path.dirname(log),{recursive:true});
  const {chromium} = await import(process.env.ALPHAFOUNDRY_PLAYWRIGHT_MODULE || 'playwright-core');
  browser = await chromium.launch({headless:true,executablePath:process.env.CHROME_EXECUTABLE_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
  const context = await browser.newContext({viewport:{width:1440,height:1000},acceptDownloads:true});
  const page = await context.newPage(); const errors=[];
  page.on('pageerror',error=>errors.push(error.name));
  await page.route('**/*',async route=>{
    if (!['GET','HEAD'].includes(route.request().method())) {errors.push('unexpected_write'); await route.abort();}
    else await route.continue();
  });
  await page.goto(`${origin.origin}/?acceptance=custom-skill#/fingpt?session=${session}`);
  await page.getByRole('heading',{name:'能力验收 · 自建 Skill 统计报告',exact:true}).waitFor();
  await page.reload();
  await page.getByRole('heading',{name:'能力验收 · 自建 Skill 统计报告',exact:true}).waitFor();
  await page.getByText(`所选能力版本：${capability} · v1`,{exact:false}).waitFor();
  const panelToggle=page.getByRole('button',{name:'活动与文件',exact:true});
  if (await panelToggle.getAttribute('aria-expanded') !== 'true') await panelToggle.click();
  await page.getByRole('region',{name:'文件交付检查',exact:true}).getByText('文件交付已检查',{exact:true}).waitFor();
  await page.getByRole('tab',{name:'文件',exact:true}).click();
  const row=page.locator('.file-card').filter({hasText:'sample-statistics.html'});
  await row.getByRole('button',{name:'预览',exact:true}).click();
  const selector=`iframe[src$="/files/${file}/preview"]`;
  assert.equal(await page.locator(selector).getAttribute('sandbox'),'');
  await page.frameLocator(selector).getByRole('table',{name:'统计结果',exact:true}).waitFor();
  await page.screenshot({path:path.join(output,'preview.png'),fullPage:true});
  const promise=page.waitForEvent('download');
  await row.getByRole('link',{name:'下载',exact:true}).click();
  const download=await promise;
  assert.equal(download.suggestedFilename(),'sample-statistics.html');
  const target=path.join(output,'sample-statistics.html'); await download.saveAs(target);
  const bytes=await readFile(target); const html=bytes.toString('utf8');
  const sha256=createHash('sha256').update(bytes).digest('hex');
  assert.equal(sha256,'ff0b305c0b1815120654c944f00635094e930f98474ca7517d46d520e91878e0');
  for (const value of ['12','18','30','40','100','25']) assert.ok(html.includes(value),`Missing ${value}`);
  assert.deepEqual(errors,[]);
  await writeFile(path.join(output,'receipt.json'),JSON.stringify({status:'passed',session,capability,version:1,file,sha256,bytes:bytes.length,checks:['refresh_version_record','delivery_complete','isolated_html_preview','browser_download_sha256','sample_values_present'],modelCalls:0},null,2));
  await writeFile(log,JSON.stringify({event:'custom_skill_readback',status:'passed'})+'\n');
  console.log('Custom Skill: version, delivery, preview and actual download passed');
} catch(error) {
  await mkdir(output,{recursive:true}); await mkdir(path.dirname(log),{recursive:true});
  await writeFile(path.join(output,'receipt.json'),JSON.stringify({status:'failed',error:error.message},null,2));
  await writeFile(log,JSON.stringify({event:'custom_skill_readback',status:'failed',error_type:error.name})+'\n');
  console.error(error.message); process.exitCode=1;
} finally {if(browser) await browser.close();}
