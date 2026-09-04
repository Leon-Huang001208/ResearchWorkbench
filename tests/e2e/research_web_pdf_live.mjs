/** Explicit real-model PDF upload journey. Each invocation creates one isolated session. */
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {mkdir, writeFile} from 'node:fs/promises';
import path from 'node:path';
const origin=new URL(process.env.RESEARCH_WEB_URL || 'http://127.0.0.1:8088');
if(origin.origin!=='http://127.0.0.1:8088') throw new Error('This live acceptance is pinned to the owned local Web');
const output=path.resolve('outputs/research-web-ui-acceptance/pdf-live');
const log=path.resolve('logs/research-web-pdf-live.jsonl');
const sourceSession='28d73296-9908-4095-b89b-f46a4758d852';
const sourceFile='d7a22c597bdc6ade86e3c2b8';
let browser,sid; const messages=[];
try {
  await mkdir(output,{recursive:true}); await mkdir(path.dirname(log),{recursive:true});
  const {chromium}=await import(process.env.RESEARCH_PLAYWRIGHT_MODULE || 'playwright-core');
  browser=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
  const context=await browser.newContext({viewport:{width:1440,height:1000}});
  const original=await context.request.get(`${origin.origin}/api/research/sessions/${sourceSession}/files/${sourceFile}/download`);
  assert.equal(original.status(),200); const bytes=await original.body(); assert.equal(bytes.subarray(0,4).toString(),'%PDF');
  const sha256=createHash('sha256').update(bytes).digest('hex');
  await writeFile(path.join(output,'dsh-report.pdf'),bytes);
  const page=await context.newPage(); const errors=[]; page.on('pageerror',e=>errors.push(e.name));
  page.on('request',request=>{if(request.method()==='POST' && /\/messages$/.test(new URL(request.url()).pathname)) messages.push({path:new URL(request.url()).pathname,key:request.headers()['idempotency-key']});});
  const resume=process.env.RESEARCH_ACCEPTANCE_SESSION;
  if (resume) {
    assert.match(resume,/^[a-f0-9-]{36}$/); sid=resume;
    await page.goto(`${origin.origin}/?acceptance=pdf-readback#/fingpt?session=${sid}`);
  } else {
  await page.goto(`${origin.origin}/?acceptance=pdf-live#/fingpt`);
  await page.getByRole('link',{name:'DSH 已连接',exact:true}).waitFor();
  await page.locator('#file-input').setInputFiles(path.join(output,'dsh-report.pdf'));
  await page.getByRole('button',{name:/^移除附件 [a-f0-9]+-dsh-report\.pdf$/}).waitFor();
  sid=new URLSearchParams(page.url().split('?session=')[1] ? `session=${page.url().split('?session=')[1]}` : '').get('session');
  assert.match(sid,/^[a-f0-9-]{36}$/);
  await writeFile(path.join(output,'receipt.json'),JSON.stringify({status:'running',session:sid,sourceSession,sourceFile,sha256},null,2));
  await page.getByRole('button',{name:'重命名',exact:true}).click();
  await page.getByRole('textbox',{name:'为这个研究会话命名',exact:true}).fill('UI 验收 · PDF 上传与页码引用');
  await page.getByRole('button',{name:'保存名称',exact:true}).click();
  await page.getByRole('combobox',{name:'使用 Skill 或 Workflow',exact:true}).selectOption({label:'资料解读'});
  await page.getByRole('textbox',{name:'研究问题',exact:true}).fill('用所选资料解读 Skill，实际读取刚上传的 dsh-report.pdf（国金证券 DSH 研报）。只用research_run_script与现有PDF库读取PDF物理第14和15页，即0-based索引13和14，不联网不安装不读取其他文件。分别概括两页主要内容，每条标注PDF物理页码；若印刷页码不同同时注明。给出每页一段不超过20字的原文锚点供核对。只答简短中文，不生成报告文件，不复述你没有实际读取的页；若页数不足明确失败。');
  await page.getByRole('button',{name:'发送',exact:true}).click();
  await page.getByRole('button',{name:'停止',exact:true}).waitFor({timeout:60000});
  // Reload while native execution is active; never resubmit the draft.
  await page.reload();
  await page.getByRole('heading',{name:'UI 验收 · PDF 上传与页码引用',exact:true}).waitFor();
  }
  const deadline=Date.now()+240000; let detail;
  do {
    detail=await (await context.request.get(`${origin.origin}/api/research/sessions/${sid}`)).json();
    if(!detail.can_cancel && ['completed','failed','cancelled','incomplete'].includes(detail.status)) break;
    await new Promise(resolve=>setTimeout(resolve,2000));
  } while(Date.now()<deadline);
  assert.equal(detail.status,'completed'); assert.equal(detail.can_cancel,false);
  assert.equal(messages.length,resume ? 0 : 1,'Reload or click must not resubmit');
  if (!resume) assert.ok(messages[0].key);
  assert.equal(detail.capability.id,'document-reading');
  await page.reload(); await page.getByRole('heading',{name:'UI 验收 · PDF 上传与页码引用',exact:true}).waitFor();
  const rendered=await page.getByLabel('会话消息',{exact:true}).innerText();
  assert.match(rendered,/14/); assert.match(rendered,/15/); assert.match(rendered,/页/);
  assert.ok(detail.activities.some(a=>a.title==='research_run_script' && a.status==='completed'));
  const uploaded=detail.files.find(f=>f.name.endsWith('-dsh-report.pdf')); assert.ok(uploaded);
  const stored=await (await context.request.get(`${origin.origin}${uploaded.url}`)).body();
  assert.equal(createHash('sha256').update(stored).digest('hex'),sha256);
  await page.screenshot({path:path.join(output,'pdf-answer.png'),fullPage:true});
  assert.deepEqual(errors,[]);
  await writeFile(path.join(output,'answer.txt'),rendered);
  await writeFile(path.join(output,'receipt.json'),JSON.stringify({status:'passed',session:sid,sourceSession,sourceFile,uploaded:uploaded.id,sha256,mode:resume?'readback':'live',messageRequests:messages.length,capability:detail.capability,checks:['actual_upload_bytes','native_document_skill','model_read_activity','pages_14_15_rendered',...(resume?[]:['reload_while_running_no_resubmit']),'history_restored']},null,2));
  await writeFile(log,JSON.stringify({event:'pdf_live',status:'passed',session:sid})+'\n'); console.log(`Real PDF journey passed: ${sid}`);
} catch(error) {
  await mkdir(output,{recursive:true}); await mkdir(path.dirname(log),{recursive:true});
  await writeFile(path.join(output,'receipt.json'),JSON.stringify({status:'failed',session:sid,error:error.message,messageRequests:messages.length},null,2));
  await writeFile(log,JSON.stringify({event:'pdf_live',status:'failed',session:sid,error_type:error.name})+'\n'); console.error(error.message); process.exitCode=1;
} finally {if(browser) await browser.close();}
