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
const child = spawn(process.env.RWB_TEST_PYTHON, ['-u','tests/e2e/research_web_dossiers_backend.py','--output',output], {cwd:project,env:{PATH:process.env.PATH,PYTHONIOENCODING:'utf-8',PYTHONPATH:process.env.PYTHONPATH || ''},stdio:['ignore','pipe','pipe']});
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
    await page.locator('#scenario-identity').fill('600600.SH');
    await page.locator('#scenario-as_of').fill('2026-10-26');
    await page.locator('#scenario-question').fill('核对盈利质量与原件缺口');
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
