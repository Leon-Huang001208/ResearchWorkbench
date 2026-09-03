/** Real model + actual UI cancel while a session-local script is running. */
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {mkdir,writeFile,appendFile} from 'node:fs/promises';
const origin='http://127.0.0.1:8088';
const output='outputs/research-web-ui-acceptance/stop-live';
const record={status:'running',samples:[]};
let browser;
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
try {
  await mkdir(output,{recursive:true}); await mkdir('logs',{recursive:true});
  const {chromium}=await import(process.env.ALPHAFOUNDRY_PLAYWRIGHT_MODULE || 'playwright-core');
  browser=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
  const context=await browser.newContext({viewport:{width:1600,height:1000}});
  const page=await context.newPage();
  await page.goto(`${origin}/?acceptance=stop-live#/fingpt`);
  await page.getByRole('link',{name:'DSH 已连接',exact:true}).waitFor();
  await page.getByRole('textbox',{name:'研究问题',exact:true}).fill('独立手动停止测试：只调用一次af_run_script执行Python，创建outputs/cancel-proof.txt，以w打开，每0.5秒追加一行递增数字并flush，最多120次。不要联网、不要读取任何附件、不启子Agent、不要第二脚本或读回。我将在工具实际执行两秒后点击停止。不要把超时当作取消。');
  const accepted=page.waitForResponse(r=>r.request().method()==='POST'&&new URL(r.url()).pathname.endsWith('/messages'));
  await page.getByRole('button',{name:'开始研究',exact:true}).click(); assert.equal((await accepted).status(),202);
  record.session=new URLSearchParams(page.url().split('#')[1].split('?')[1]).get('session');
  assert.match(record.session,/^[a-f0-9-]{36}$/);
  const read=async()=>await(await context.request.get(`${origin}/api/research/sessions/${record.session}`)).json();
  let detail; const deadline=Date.now()+60000;
  do {
    detail=await read();
    if(detail.activities.some(a=>a.title==='af_run_script'&&a.status==='running')) break;
    await pause(200);
  }while(Date.now()<deadline);
  assert.ok(detail.activities.some(a=>a.title==='af_run_script'&&a.status==='running'));
  await pause(1500);
  detail=await read(); record.before={status:detail.status,activities:detail.activities};
  const responsePromise=page.waitForResponse(r=>r.request().method()==='POST'&&new URL(r.url()).pathname.endsWith('/cancel'));
  await page.getByRole('button',{name:'停止',exact:true}).click();
  const cancel=await responsePromise; record.cancelStatus=cancel.status(); assert.equal(cancel.status(),200);
  const end=Date.now()+15000;
  do {detail=await read();if(!detail.can_cancel)break;await pause(250);}while(Date.now()<end);
  record.after={status:detail.status,delivery:detail.delivery,activities:detail.activities,can_cancel:detail.can_cancel};
  const file=detail.files.find(f=>f.name==='cancel-proof.txt'); assert.ok(file);
  for(let i=0;i<3;i++) {
    const response=await context.request.get(`${origin}${file.url}`); assert.equal(response.status(),200);
    const bytes=await response.body(); const text=bytes.toString();
    record.samples.push({time:new Date().toISOString(),bytes:bytes.length,lines:text.trim().split('\n').length,sha256:createHash('sha256').update(bytes).digest('hex')});
    if(i<2)await pause(2000);
  }
  assert.equal(new Set(record.samples.map(s=>s.sha256)).size,1,'Cancelled script must not keep writing');
  assert.ok(record.samples[0].lines<120);
  await page.reload();
  await page.getByRole('button',{name:'活动与文件',exact:true}).waitFor();
  await page.screenshot({path:`${output}/cancelled.png`,fullPage:true});
  assert.equal(detail.can_cancel,false);assert.equal(detail.status,'cancelled');
  assert.notEqual(detail.delivery.status,'pending');
  record.status='passed';
}catch(error){record.status='failed';record.error=String(error);process.exitCode=1;}
finally {
  await browser?.close(); await writeFile(`${output}/receipt.json`,JSON.stringify(record,null,2));
  await appendFile('logs/research-web-stop-live.jsonl',JSON.stringify({time:new Date().toISOString(),status:record.status,session:record.session,error:record.error})+'\n');
  console.log(JSON.stringify(record,null,2));
}
