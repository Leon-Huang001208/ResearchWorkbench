/** Synthetic account; real Host catalog/ownership/snapshots, no paid/model I/O. */
import assert from 'node:assert/strict';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { createWriteStream } from 'node:fs';
import { mkdir, writeFile } from 'node:fs/promises';
import { pathToFileURL } from 'node:url';

const project=process.cwd(),output=path.join(project,'outputs/research-web-packs-ui');
await mkdir(output,{recursive:true});
const log=createWriteStream(path.join(project,'logs/pack-ui-browser-backend.log'));
const child=spawn(process.env.RWB_TEST_PYTHON,['-u','tests/e2e/research_web_packs_backend.py','--output',output],{cwd:project,env:{PATH:process.env.PATH,PYTHONPATH:process.env.PYTHONPATH || '',PYTHONIOENCODING:'utf-8',PYTHONDONTWRITEBYTECODE:'1'},stdio:['ignore','pipe','pipe']});
let buffer='',resolveReady,rejectReady,browser;
const ready=new Promise((resolve,reject)=>{resolveReady=resolve;rejectReady=reject;});
child.stdout.on('data',bytes=>{log.write(bytes);buffer=(buffer+bytes).slice(-12000);const found=/RWB_DOSSIER_HTTP_READY (\{[^\n]+\})/.exec(buffer);if(found)resolveReady(JSON.parse(found[1]));});
child.stderr.pipe(log);child.on('error',rejectReady);
const exit=new Promise(resolve=>child.on('exit',(code,signal)=>{rejectReady(Error(`fixture_exit:${code}:${signal}`));resolve();}));
const checks=[],errors=[];
try {
  const timer=setTimeout(()=>rejectReady(Error('fixture_start_timeout')),30000);
  const target=await ready;clearTimeout(timer);
  await writeFile(path.join(output,'owner.json'),JSON.stringify({pid:child.pid,uid:process.getuid(),fixture:true}));
  const origin=`http://127.0.0.1:${target.port}`;
  const {chromium}=await import(pathToFileURL('/Users/leon/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright-core/index.mjs').href);
  browser=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
  for(const width of [1440,390]) {
    const context=await browser.newContext({viewport:{width,height:1000}}),page=await context.newPage();page.setDefaultTimeout(20000);page.on('pageerror',error=>errors.push(error.message));
    await page.route('**/*',route=>new URL(route.request().url()).origin===origin?route.continue():route.abort());
    assert.equal((await context.request.get(`${origin}/api/research/scenarios`)).status(),401);
    await page.goto(`${origin}/__fixture/login`);await page.getByRole('button',{name:'进入离线验收'}).click();
    const fixture=await (await context.request.get(`${origin}/__fixture/packs`)).json();
    await page.goto(`${origin}/#/fingpt?session=${fixture.source_session_id}`);
    await page.getByRole('button',{name:'选择研究场景',exact:true}).click();
    for (const material of await page.locator('[name="scenario-material"]').all()) {
      if (await material.inputValue() !== fixture.dataset_id) await material.uncheck();
    }
    const catalog=await (await context.request.get(`${origin}/api/research/scenarios`)).json();
    const packs=catalog.items.filter(row=>row.pack_id);assert.equal(packs.length,9);
    const before=await (await context.request.get(`${origin}/__fixture/state`)).json();
    for(const pack of packs) {
      await page.locator('#scenario-scenario').selectOption(pack.id);
      if (pack.id === packs[0].id) {
        await page.locator('#scenario-source-session').selectOption(fixture.source_session_id);
        await page.locator(`[name="scenario-material"][value="${fixture.dataset_id}"]`).waitFor();
        assert.equal(await page.locator('[name="scenario-material"]:checked').count(),0);
        await page.locator(`[name="scenario-material"][value="${fixture.dataset_id}"]`).check();
      }
      await page.locator('#scenario-identity').fill('600600.SH');
      await page.locator('#scenario-as_of').fill(fixture.as_of);
      await page.locator('#scenario-question').fill('合成验收：核对原件及缺口');
      await page.locator('#scenario-cutoff_at').fill(fixture.as_of+'T23:59:59+08:00');
      for(const method of pack.ui_methods)for(const field of method.fields) {
        if(field.type==='securities')continue;
        const locator=page.locator(`#scenario-${method.id}-${field.name}`);
        if(field.type==='integer'||field.type==='number')await locator.fill(field.name==='minimum_samples'?'2':'1');
        else if(field.type==='adjustment')await locator.selectOption('none');
        else await locator.fill(field.type==='instant'?fixture.release_at:field.type==='date'?fixture.as_of:field.name==='report_periods'?'2025FY,2026Q1':field.name==='report_period'?'2026Q3':'synthetic-row');
      }
      await page.locator('#scenario-cutoff_at').press('Enter');
      const pending=page.waitForResponse(r=>r.url().endsWith(`/scenarios/${pack.id}/prepare`));
      await page.getByRole('button',{name:'只读资格预览',exact:true}).click();
      const response=await pending,data=await response.json();assert.equal(response.status(),200,JSON.stringify(data));
      const status=data.pack_qualification.status;assert.equal(status,pack.id==='pack-event-review'?'partial':'blocked');
      await page.getByRole('heading',{name:`Host 只读资格预览 · ${status}`,exact:true}).waitFor();
      assert.equal(await page.locator('[data-scenario-freeze]').isDisabled(),pack.id!=='pack-event-review');
      if(pack.id==='pack-event-review') {
        await page.locator('.d-drawer-body').evaluate(element=>{element.scrollTop=element.scrollHeight;});
        await page.screenshot({path:path.join(output,`partial-${width}.png`),fullPage:true});
        await page.emulateMedia({colorScheme:'dark'});
        await page.waitForFunction(()=>document.documentElement.dataset.theme==='dark');
        await page.screenshot({path:path.join(output,`partial-dark-${width}.png`),fullPage:true});
        await page.emulateMedia({colorScheme:'light'});
        await page.waitForFunction(()=>document.documentElement.dataset.theme==='light');
      }
      await page.locator('#scenario-question').fill('编辑后预览失效');
      assert.equal(await page.locator('[data-scenario-freeze]').isDisabled(),true);
      if (pack.id === packs[0].id) {
        await page.locator('#scenario-question').fill('长文本与原件缺口<synthetic>'.repeat(400).slice(0,6000));
        assert.equal((await page.locator('#scenario-question').inputValue()).length,6000);
        assert.equal(await page.locator('.d-drawer').evaluate(element=>element.scrollWidth>element.clientWidth+1),false);
      }
      checks.push({width,pack:pack.id,status,editInvalidates:true});
    }
    const after=await (await context.request.get(`${origin}/__fixture/state`)).json();assert.equal(after.sessions.length,before.sessions.length);assert.equal(after.native_prompt_calls,before.native_prompt_calls);
    await page.locator('#scenario-scenario').selectOption('pack-event-review');
    await page.locator('#scenario-cutoff_at').fill(fixture.as_of+'T23:59:59+08:00');
    await page.locator('#scenario-align_event_trading_day-release_at').fill(fixture.release_at);
    await page.locator('#scenario-align_event_trading_day-pre_sessions').fill('1');
    await page.locator('#scenario-align_event_trading_day-post_sessions').fill('1');
    await page.locator('#scenario-align_event_trading_day-adjustment').selectOption('none');
    await page.getByRole('button',{name:'只读资格预览',exact:true}).click();
    await page.getByRole('heading',{name:'Host 只读资格预览 · partial',exact:true}).waitFor();
    const frozenReply=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/research/handoffs'&&r.request().method()==='POST');
    await page.getByRole('button',{name:'明确准备研究草稿',exact:true}).click();
    const frozenResponse=await frozenReply,frozen=await frozenResponse.json();assert.equal(frozenResponse.status(),201,JSON.stringify(frozen));
    await page.getByRole('button',{name:'确认冻结资料，进入研究草稿'}).click();
    await page.waitForURL(`**session=${frozen.session_id}`);
    await page.getByRole('region',{name:'组合包计算与文件回执'}).waitFor();
    await page.screenshot({path:path.join(output,`draft-${width}.png`),fullPage:true});
    assert.equal((await (await context.request.get(`${origin}/__fixture/state`)).json()).native_prompt_calls,before.native_prompt_calls);
    const sendReply=page.waitForResponse(r=>r.url().endsWith(`/sessions/${frozen.session_id}/messages`)&&r.request().method()==='POST');
    await page.getByRole('button',{name:'发送研究问题',exact:true}).click();
    const sent=await sendReply;assert.equal(sent.status(),202,await sent.text());
    checks.push({width,explicitPrepareAndSend:true,native:'offline fixture only',realModel:'NOT_RUN'});
    assert.equal(await page.locator('body').evaluate(element=>element.scrollWidth>innerWidth+1),false);
    await context.close();
  }
  assert.deepEqual(errors,[]);
  await writeFile(path.join(output,'result.json'),JSON.stringify({fixture:true,checks,errors,realModel:'NOT_RUN',production:'NOT_RUN'},null,2));
  console.log(JSON.stringify({status:'PASS',checks:checks.length,output}));
} catch(error) {
  await writeFile(path.join(output,'failure.json'),JSON.stringify({error:error.message,checks,errors},null,2));throw error;
} finally {
  if(browser)await browser.close();child.kill('SIGTERM');await exit;log.end();
}
