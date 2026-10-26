/** Real browser events over a temporary real Host; no production/paid/model I/O. */
import assert from 'node:assert/strict';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { createWriteStream } from 'node:fs';
import { mkdir, writeFile } from 'node:fs/promises';
import { pathToFileURL } from 'node:url';

const project = process.cwd(), output = path.join(project, 'outputs/research-web-scenarios');
await mkdir(output, {recursive:true});
const log = createWriteStream(path.join(project,'logs/t2-browser-backend.log'));
const child = spawn(process.env.RWB_TEST_PYTHON, ['-u','tests/e2e/research_web_scenarios_backend.py','--output',output], {cwd:project,env:{PATH:process.env.PATH,PYTHONIOENCODING:'utf-8',PYTHONPATH:process.env.PYTHONPATH || ''},stdio:['ignore','pipe','pipe']});
let buffer='',resolveReady,rejectReady,browser;
const ready = new Promise((resolve,reject)=>{resolveReady=resolve;rejectReady=reject});
child.stdout.on('data', bytes=>{log.write(bytes);buffer=(buffer+bytes).slice(-12000);const found=/RWB_DOSSIER_HTTP_READY (\{[^\n]+\})/.exec(buffer);if(found)resolveReady(JSON.parse(found[1]));});
child.stderr.pipe(log);
child.on('error',rejectReady);
const exit = new Promise(resolve=>child.on('exit',(code,signal)=>{rejectReady(new Error(`fixture_exit:${code}:${signal}`));resolve()}));
const checks=[], errors=[];
try {
  const timer = setTimeout(()=>rejectReady(new Error('fixture_start_timeout')),20000);
  const target=await ready;clearTimeout(timer);
  const origin=`http://127.0.0.1:${target.port}`;
  for(let i=0;i<40;i++){try{if((await fetch(`${origin}/__fixture/ready`)).ok)break;}catch(error){if(i===39)throw error;}await new Promise(resolve=>setTimeout(resolve,100));}
  const {chromium}=await import(pathToFileURL('/Users/leon/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright-core/index.mjs').href);
  browser=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
  for(const width of [1440,390]) {
    const context=await browser.newContext({viewport:{width,height:1000}});
    const page=await context.newPage();page.setDefaultTimeout(15000);page.on('pageerror',error=>errors.push(error.message));
    await page.route('**/*',route=>new URL(route.request().url()).origin===origin?route.continue():route.abort());
    assert.equal((await context.request.get(`${origin}/api/research/scenarios`)).status(),401);
    await page.goto(`${origin}/__fixture/login`);await page.getByRole('button',{name:'进入离线验收'}).click();
    await page.goto(`${origin}/#/fingpt`);
    await page.locator('#prompt').fill('保留原草稿 <tag>');
    const before=await (await context.request.get(`${origin}/__fixture/state`)).json();
    await page.getByRole('button',{name:'选择研究场景',exact:true}).click();
    await page.locator('#scenario-scenario').selectOption('company-onepager');
    await page.getByRole('dialog',{name:'研究场景',exact:true}).getByRole('button',{name:'关闭',exact:true}).focus();
    await page.keyboard.press('Shift+Tab');
    assert.equal(await page.locator('[data-scenario-freeze]').evaluate(element=>element===document.activeElement),true);
    await page.keyboard.press('Escape');assert.equal(await page.locator('.scenario-panel').count(),0);
    assert.equal(await page.locator('#prompt').inputValue(),'保留原草稿 <tag>');
    await page.getByRole('button',{name:'选择研究场景',exact:true}).click();
    await page.locator('#scenario-scenario').selectOption('company-onepager');
    await page.locator('#scenario-identity').fill('600600.SH');
    await page.locator('#scenario-as_of').fill('2026-10-26');
    await page.locator('#scenario-question').fill('核对盈利质量与原件缺口');
    const beforeSearch=await (await context.request.get(`${origin}/__fixture/state`)).json();
    await page.locator('#scenario-query').focus(); await page.keyboard.press('Enter');
    await page.waitForTimeout(150);
    const afterSearch=await (await context.request.get(`${origin}/__fixture/state`)).json();
    assert.equal(afterSearch.sessions.length,beforeSearch.sessions.length,'search Enter must not create');
    await page.locator('#scenario-question').focus();await page.keyboard.press('End');await page.keyboard.type('，逐字输入验证');
    await page.screenshot({path:path.join(output,`scenario-${width}-before.png`),fullPage:true});
    const response=page.waitForResponse(r=>r.request().method()==='POST'&&new URL(r.url()).pathname==='/api/research/handoffs');
    await page.getByRole('button',{name:'冻结资料并准备草稿',exact:true}).click();
    const receipt=await response;const frozen=await receipt.json();assert.equal(receipt.status(),201,JSON.stringify(frozen));
    assert.equal(frozen.scenario_context.scenario.status,'incomplete');
    assert.equal(frozen.scenario_context.scenario.inputs.as_of,'2026-10-26');
    await page.getByRole('button',{name:'确认冻结资料，进入研究草稿'}).click();
    await page.waitForURL(`**session=${frozen.session_id}`);
    await page.waitForFunction(()=>document.querySelector('#prompt')?.value.includes('核对盈利质量'));
    const after=await (await context.request.get(`${origin}/__fixture/state`)).json();
    assert.equal(after.native_prompt_calls,before.native_prompt_calls);
    await page.screenshot({path:path.join(output,`scenario-${width}-prepared.png`),fullPage:true});
    await page.goto(`${origin}/#/fingpt`);
    assert.equal(await page.locator('#prompt').inputValue(),'保留原草稿 <tag>');
    checks.push({width,prepared:true,originalDraftRetained:true,noModelPrepare:true,session:frozen.session_id});
    const fixture=await (await context.request.get(`${origin}/__fixture/asset-workspace`)).json();
    await page.goto(`${origin}/#/assets?asset=600600.SH&asset_type=stock&view=financials`);
    await page.locator('[data-asset-research]').waitFor();
    const raceBefore=await (await context.request.get(`${origin}/__fixture/state`)).json();
    await page.evaluate(()=>{
      globalThis.__scenarioRaceClick=false;
      const observer=new MutationObserver(()=>{
        if(document.querySelector('#asset-code-display')?.textContent.includes('601318.SH')){
          observer.disconnect();globalThis.__scenarioRaceClick=true;
          document.querySelector('[data-scenario-open]')?.click();
        }
      });
      observer.observe(document.getElementById('app'),{childList:true,subtree:true});
      location.hash='#/assets?asset=601318.SH&asset_type=stock&view=financials';
    });
    await page.waitForFunction(()=>globalThis.__scenarioRaceClick===true);
    await page.getByText('当前证券观察尚未就绪，请等待切换完成；没有带入上一证券资料。',{exact:true}).first().waitFor();
    assert.equal(await page.locator('.scenario-panel').count(),0);
    const raceAfter=await (await context.request.get(`${origin}/__fixture/state`)).json();
    assert.equal(raceAfter.sessions.length,raceBefore.sessions.length);
    await page.goto(`${origin}/#/assets?asset=600600.SH&asset_type=stock&view=financials`);
    await page.locator('[data-asset-research]').waitFor();

    await page.waitForFunction(()=>{const field=document.querySelector('#asset-research-import');return field && !field.disabled;});
    await page.locator('#asset-research-import').setInputFiles({name:'workspace.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(fixture.bundle))});
    await page.getByRole('heading',{name:'经营资料摘录',exact:true}).waitFor();
    const savedMaterial=await page.locator('#asset-research-material').inputValue();
    await page.locator('#asset-research-material').selectOption('');
    await page.getByText('尚未选择带来源的研究摘要。可选择已保存资料，或下载模板后导入；不自动生成观点。',{exact:true}).waitFor();
    await page.locator('#asset-research-material').selectOption(savedMaterial);
    await page.getByRole('heading',{name:'经营资料摘录',exact:true}).waitFor();
    await page.locator(`[data-asset-research-peer][value="${fixture.peer_observation_id}"]`).check();
    await page.locator('#ar-tab-comparisons').click();
    await page.getByText('2026-03-31 · akshare · 原始行 1',{exact:true}).waitFor({state:'attached'});
    assert.match(await page.locator('.ar-table-wrap').innerText(),/万元/);
    assert.match(await page.locator('.ar-table-wrap').innerText(),/CNY/);
    await page.locator('#ar-tab-relations').click();
    await page.getByRole('heading',{name:'600600.SH → 601318.SH',exact:true}).waitFor();
    await page.locator('[data-asset-research-scope="uploads"]').check();
    await page.locator('#asset-research-cutoff').fill('2026-10-26');
    await page.locator('[data-asset-research]').scrollIntoViewIfNeeded();
    await page.screenshot({path:path.join(output,`asset-workspace-${width}.png`),fullPage:true});
    await page.getByRole('button',{name:'用已确认资料准备研究',exact:true}).click();
    const assetReply=page.waitForResponse(r=>r.request().method()==='POST'&&new URL(r.url()).pathname==='/api/research/handoffs');
    await page.getByRole('button',{name:'冻结资料并准备草稿',exact:true}).click();
    const assetResponse=await assetReply, assetResult=await assetResponse.json();assert.equal(assetResponse.status(),201,JSON.stringify(assetResult));
    assert.deepEqual(assetResult.scenario_context.comparisons.map(x=>x.subject.identity),['601318.SH']);
    assert.ok(assetResult.scenario_context.frozen_files.length>=1);
    await page.getByRole('button',{name:'确认冻结资料，进入研究草稿'}).click();
    await page.waitForURL(`**session=${assetResult.session_id}`);
    await page.goto(`${origin}/#/assets/funds`);
    const oldReply=page.waitForResponse(r=>r.request().method()==='POST'&&new URL(r.url()).pathname==='/api/research/handoffs');
    await page.locator(`[data-workbench-handoff="fingpt"][data-source-session="${fixture.source_session_id}"]`).click();
    const legacyResponse=await oldReply, legacy=await legacyResponse.json();assert.equal(legacyResponse.status(),201,JSON.stringify(legacy));
    assert.equal(legacy.section,'funds');assert.equal(legacy.dataset_count,1);assert.equal(legacy.scenario_context,undefined);
    checks.push({width,assetWorkspace:true,summary:true,comparisons:true,sourceLinkedRelation:true,realImport:true,legacyHandoff:true,searchEnterNoCreate:true,routeRaceNoCreate:true,desktopKeyboardEscapeAndTab:true});

    await context.close();
  }
  assert.deepEqual(errors,[]);
  await writeFile(path.join(output,'result.json'),JSON.stringify({fixture:true,checks,errors,realModel:'NOT_RUN',production:'NOT_RUN'},null,2));
  console.log(JSON.stringify({status:'PASS',checks:checks.length,output}));
} catch(error) {
  await writeFile(path.join(output,'failure.json'),JSON.stringify({error:error.message,checks,errors},null,2));
  throw error;
} finally {
  if(browser)await browser.close();child.kill('SIGTERM');await exit;log.end();
}
