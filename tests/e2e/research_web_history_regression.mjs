/** Re-open existing real research: no model calls, approvals or source queries. */
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {mkdir, readFile, writeFile} from 'node:fs/promises';
import path from 'node:path';

const origin = new URL(process.env.RESEARCH_WEB_URL || 'http://127.0.0.1:8088');
if (!['localhost','127.0.0.1'].includes(origin.hostname) || origin.protocol !== 'http:') {
  throw new Error('Historical acceptance is limited to a local deployment');
}
const output = path.resolve('outputs/research-web-ui-acceptance/history-regression');
const log = path.resolve('logs/research-web-history-regression.jsonl');
const results = [];
let browser;
try {
  await mkdir(output,{recursive:true});
  await mkdir(path.dirname(log),{recursive:true});
  const {chromium} = await import(process.env.RESEARCH_PLAYWRIGHT_MODULE || 'playwright-core');
  browser = await chromium.launch({headless:true,
    executablePath:process.env.CHROME_EXECUTABLE_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
  const context = await browser.newContext({viewport:{width:1440,height:900},acceptDownloads:true});
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror',error=>errors.push(error.name));
  await page.route('**/*',async route=>{
    if (!['GET','HEAD'].includes(route.request().method())) {
      errors.push(`blocked_${route.request().method()}`);
      await route.abort('blockedbyclient');
    } else await route.continue();
  });
  async function openSession(sid,mode,title) {
    await page.goto(`${origin.origin}/?acceptance=historical#/${mode}?session=${sid}`);
    await page.getByRole('heading',{name:title,exact:true}).waitFor();
    await page.getByRole('link',{name:'DSH 已连接',exact:true}).waitFor();
    const panel = page.getByRole('complementary',{name:'研究活动、资料与文件',exact:true});
    if (!await panel.isVisible()) await page.getByRole('button',{name:'活动与文件',exact:true}).click();
    return panel;
  }
  const fund = 'd918f34f-02bf-4c85-bc7a-a8b5880195b6';
  const panel = await openSession(fund,'claw','基金000001：共享资料与最终报告');
  await panel.getByRole('tab',{name:'活动',exact:true}).click();
  assert.equal(await panel.locator('.agent-card').count(),2);
  await panel.getByText('净值区间与回撤计算',{exact:true}).waitFor();
  await panel.getByText('资料风险与缺失核对',{exact:true}).waitFor();
  await panel.getByText('文件交付已检查',{exact:true}).waitFor();
  await page.screenshot({path:path.join(output,'real-subagents.png'),fullPage:true});
  await panel.getByRole('tab',{name:'资料',exact:true}).click();
  assert.equal(await panel.locator('.dataset-card').count(),4);
  assert.match(await panel.innerText(),/243 条/);
  assert.match(await panel.innerText(),/13 页/);
  await page.screenshot({path:path.join(output,'real-datasets.png'),fullPage:true});
  await panel.getByRole('tab',{name:'文件',exact:true}).click();
  const row = panel.locator('.file-card').filter({hasText:'fund_eval_000001_final.xlsx'});
  const pending = page.waitForEvent('download');
  await row.getByRole('link',{name:'下载',exact:true}).click();
  const download = await pending;
  assert.equal(download.suggestedFilename(),'fund_eval_000001_final.xlsx');
  const file = path.join(output,download.suggestedFilename());
  await download.saveAs(file);
  const sha256 = createHash('sha256').update(await readFile(file)).digest('hex');
  assert.equal(sha256,'f06cb9c45442ab89e9489369958a5adc41118440b458f50447e5e35ad546c37e');
  results.push({session:fund,checks:['two_native_children','four_datasets','243_rows_13_pages','delivery_checked','xlsx_download_hash'],sha256});

  const pdf = '28d73296-9908-4095-b89b-f46a4758d852';
  const pdfPanel = await openSession(pdf,'fingpt','原生研究工具验收');
  await pdfPanel.getByRole('tab',{name:'文件',exact:true}).click();
  assert.equal(await pdfPanel.locator('.file-card').filter({hasText:'.pdf'}).count(),1);
  assert.match(await page.getByLabel('会话消息',{exact:true}).innerText(),/页/);
  await page.screenshot({path:path.join(output,'pdf-history.png'),fullPage:true});
  results.push({session:pdf,checks:['uploaded_pdf_retained','page_citations_retained']});

  const cancelled = 'c9155f74-5887-4ef2-8768-5da903ad1ddb';
  await openSession(cancelled,'fingpt','真实验收：公开数据审批允许、拒绝与取消');
  assert.equal(await page.getByRole('button',{name:'停止',exact:true}).count(),0);
  assert.equal(await page.getByRole('button',{name:'允许',exact:true}).count(),0);
  assert.equal(await page.getByRole('button',{name:'拒绝',exact:true}).count(),0);
  assert.ok(await page.getByText('已取消',{exact:true}).count()>=1);
  results.push({session:cancelled,checks:['cancelled_retained','no_pending_decision']});
  assert.deepEqual(errors,[]);
  await writeFile(path.join(output,'receipt.json'),JSON.stringify({status:'passed',results,modelCalls:0,sourceQueries:0},null,2));
  await writeFile(log,JSON.stringify({event:'history_regression',status:'passed',sessions:results.length})+'\n');
  console.log('Historical browser regression: 3 real sessions passed; no new model or data requests');
} catch(error) {
  await mkdir(output,{recursive:true});
  await mkdir(path.dirname(log),{recursive:true});
  await writeFile(path.join(output,'receipt.json'),JSON.stringify({status:'failed',error:error.message,results},null,2));
  await writeFile(log,JSON.stringify({event:'history_regression',status:'failed',error_type:error.name})+'\n');
  console.error(error.message);
  process.exitCode=1;
} finally {if(browser) await browser.close();}
