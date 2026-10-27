/** Real temporary Host + owned Chrome. Frozen synthetic captures; no public fetch or LLM. */
import assert from 'node:assert/strict';
import path from 'node:path';
import os from 'node:os';
import { spawn } from 'node:child_process';
import { createWriteStream } from 'node:fs';
import { mkdir, mkdtemp, writeFile, readFile, readdir, stat, rm, chmod } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { pathToFileURL } from 'node:url';

const task='seek-packs-20261027-7bda5752', project=process.cwd();
const output=process.env.RWB_SOURCE_E2E_OUTPUT;
if(!output || !path.isAbsolute(output))throw Error('absolute_RWB_SOURCE_E2E_OUTPUT_required');
await mkdir(output,{recursive:true});
const scratch=await mkdtemp(path.join(os.tmpdir(),'rwb-source-picker-')),identity=await stat(scratch);
const owner={task,uid:process.getuid(),pid:process.pid,root:scratch,dev:identity.dev,inode:identity.ino,fixture:true};
await writeFile(path.join(output,'runner-owner.json'),JSON.stringify(owner));
process.env.TMPDIR=scratch;
const log=createWriteStream(path.join(output,'backend.log'));
const child=spawn(process.env.RWB_TEST_PYTHON,['-u','tests/e2e/research_web_source_picker_backend.py','--output',output],{cwd:project,env:{PATH:process.env.PATH,PYTHONPATH:process.env.PYTHONPATH || '',PYTHONIOENCODING:'utf-8',PYTHONDONTWRITEBYTECODE:'1',TMPDIR:scratch},stdio:['ignore','pipe','pipe']});
await writeFile(path.join(output,'server-owner.json'),JSON.stringify({...owner,pid:child.pid}));
let buffer='',resolveReady,rejectReady,browser;
const ready=new Promise((resolve,reject)=>{resolveReady=resolve;rejectReady=reject;});
child.stdout.on('data',bytes=>{log.write(bytes);buffer=(buffer+bytes).slice(-12000);const match=/RWB_DOSSIER_HTTP_READY (\{[^\n]+\})/.exec(buffer);if(match)resolveReady(JSON.parse(match[1]));});
child.stderr.pipe(log);child.on('error',rejectReady);
const exit=new Promise(resolve=>child.on('exit',(code,signal)=>{rejectReady(Error(`fixture_exit:${code}:${signal}`));resolve();}));
const checks=[],errors=[];
try {
  const timer=setTimeout(()=>rejectReady(Error('fixture_start_timeout')),30000);
  let target;
  try { target=await ready; } finally {clearTimeout(timer);}
  const origin=`http://127.0.0.1:${target.port}`;
  const {chromium}=await import(pathToFileURL('/Users/leon/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright-core/index.mjs').href);
  browser=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
  // Playwright owns Chrome's child process; the debug connection exposes its exact PID.
  const debug=await browser.newBrowserCDPSession();
  const processes=await debug.send('SystemInfo.getProcessInfo');
  await writeFile(path.join(output,'chrome-owner.json'),JSON.stringify({...owner,processes:processes.processInfo.map(({id,type})=>({pid:id,type}))}));
  for(const width of [1440,390]) {
    const context=await browser.newContext({viewport:{width,height:1000}}),page=await context.newPage();
    page.setDefaultTimeout(15000);page.on('pageerror',error=>errors.push(error.message));
    await page.route('**/*',route=>new URL(route.request().url()).origin===origin?route.continue():route.abort());
    assert.equal((await context.request.get(origin+'/api/research/source-selections/sessions/foreign')).status(),401);
    await page.goto(origin+'/__fixture/login');await page.getByRole('button',{name:'进入离线验收'}).click();
    const fixture=await (await context.request.get(origin+'/__fixture/source-picker')).json();
    const getState=async()=> (await context.request.get(origin+'/__fixture/state')).json();
    let sourceRequests=0,freezeRequests=0;
    page.on('request',request=>{if(request.url().endsWith('/source-selections/preview'))sourceRequests++;if(request.url().endsWith('/source-selections/freeze'))freezeRequests++;});
    const open=async(kind,identity,pack='pack-research-prep')=>{
      await page.goto(origin+'/#/fingpt');
      await page.getByRole('button',{name:'选择研究场景',exact:true}).click();
      await page.locator('#scenario-scenario').selectOption(pack);
      await page.locator('#scenario-kind').selectOption(kind);
      await page.locator('#scenario-identity').fill(identity);
      await page.locator('#scenario-as_of').fill(fixture.as_of);
      await page.locator('#scenario-cutoff_at').fill(fixture.as_of+'T23:59:59+08:00');
      await page.locator('#scenario-question').fill('Synthetic 核对已保存原文与真实来源缺口');
      await page.locator('#scenario-material-mode').selectOption('sources');
      await page.locator('#scenario-source-browse').selectOption(fixture.sessions[0]);
      await page.locator('[name="scenario-source"]').first().waitFor();
      await page.locator(`[name="scenario-source"][value="${fixture.sessions[0]}:${fixture.source_id}"]`).check();
    };
    const preview=async()=>{
      const response=page.waitForResponse(r=>r.url().endsWith('/source-selections/preview'));
      await page.getByRole('button',{name:'只读资格预览',exact:true}).click();
      const actual=await response,result=await actual.json();assert.equal(actual.status(),200,JSON.stringify(result));
      await page.getByRole('heading',{name:'Host 只读资格预览 · partial',exact:true}).waitFor();
      assert.ok(result.preview_sha256);assert.deepEqual(result.qualification.executable_methods,['deduplicate_source_versions']);
      assert.equal(result.frozen,false);assert.equal(result.send_authorized,false);return result;
    };
    const before=await getState();
    for(const [kind,id] of [['stock','600600.SH'],['industry','sw:801890'],['topic','中国制造业景气']]) {
      await open(kind,id,kind==='industry'?'pack-global-opinion':'pack-research-prep');
      if(kind==='stock') {
        await page.locator('#scenario-source-browse').selectOption(fixture.sessions[1]);
        await page.locator(`[name="scenario-source"][value="${fixture.sessions[1]}:${fixture.source_id}"]`).check();
        assert.equal(await page.locator('[name="scenario-source"]:checked').count(),2);
        assert.equal(await page.locator('.pack-source-picker').getByText(/上游完整性未知/).count(),2);
        assert.equal(await page.locator('.pack-source-picker script').count(),0);
        await page.locator('#scenario-question').fill('Synthetic 长问题与中文粘贴<安全>'.repeat(400).slice(0,6000));
        assert.equal((await page.locator('#scenario-question').inputValue()).length,6000);
        await page.locator('#scenario-question').focus();await page.keyboard.press('Home');await page.keyboard.type('IME');
        const scroll=await page.locator('.d-drawer-body').evaluate(el=>el.scrollTop);
        await page.locator('#scenario-question').press('ArrowLeft');await page.keyboard.type('X');
        assert.ok(Math.abs(await page.locator('.d-drawer-body').evaluate(el=>el.scrollTop)-scroll)<2);
        assert.equal(await page.locator('#scenario-question').evaluate(el=>el===document.activeElement),true);
        // Switch modes explicitly: source selections survive, no datasets masquerade as sources.
        await page.locator('#scenario-material-mode').selectOption('datasets');
        await page.locator('#scenario-material-mode').selectOption('sources');
        assert.equal(await page.locator('[name="scenario-source"]:checked').count(),2);
      }
      const result=await preview();assert.equal(result.subject.kind,kind);assert.equal(result.subject.identity,id);
      assert.equal(result.sources.length,kind==='stock'?2:1);
      await page.getByText('来源去重',{exact:false}).count();
      assert.match(await page.locator('.pack-scope').innerText(),/1\.1\.0/);
      assert.equal(await page.locator('.d-drawer').evaluate(el=>el.scrollWidth>el.clientWidth+1),false);
      for(const theme of ['light','dark']) {
        await page.emulateMedia({colorScheme:theme});await page.waitForFunction(expected=>document.documentElement.dataset.theme===expected,theme);
        await page.locator('.pack-source-picker').scrollIntoViewIfNeeded();
        await page.screenshot({path:path.join(output,`${kind}-${width}-${theme}.png`),fullPage:true});
      }
      await page.locator('#scenario-question').fill('Synthetic 编辑使旧预览失效');
      assert.equal(await page.locator('[data-scenario-freeze]').isDisabled(),true);
      await page.locator('#scenario-question').press('Escape');
      checks.push({width,kind,crossSession:kind==='stock',previewOnly:true});
    }
    const afterPreview=await getState();assert.equal(afterPreview.sessions.length,before.sessions.length);assert.equal(afterPreview.native_prompt_calls,before.native_prompt_calls);
    // Real permission withdrawal is distinct from an empty source list; inputs survive.
    await open('topic',`来源权限验收-${width}`);
    await page.locator('#scenario-source-browse').selectOption(fixture.empty);
    await page.getByText('此会话没有已保存原文；当前为空，未抓取新来源。',{exact:true}).waitFor();
    await context.request.post(origin+'/__fixture/source-picker/revoke');
    await page.locator('#scenario-source-browse').selectOption(fixture.sessions[0]);
    await page.locator('.pack-source-picker [role=alert]').filter({hasText:'权限已撤回'}).waitFor();
    assert.equal(await page.locator('[name="scenario-source"]:checked').count(),1);
    assert.equal(await page.locator('#scenario-identity').inputValue(),`来源权限验收-${width}`);
    await context.request.post(origin+'/__fixture/source-picker/restore');
    await page.locator('#scenario-source-browse').selectOption(fixture.sessions[1]);
    await page.locator('#scenario-source-browse').selectOption(fixture.sessions[0]);await preview();
    await context.request.post(origin+'/__fixture/source-picker/revoke');
    const revokedResponse=page.waitForResponse(r=>r.url().endsWith('/source-selections/freeze'));
    await page.getByRole('button',{name:'明确准备研究草稿',exact:true}).click();
    const revoked=await revokedResponse;assert.equal(revoked.status(),403);assert.equal((await revoked.json()).error.handoff_outcome,'not_created');
    await page.waitForFunction(()=>!document.querySelector('#scenario-question').disabled);
    assert.equal(await page.locator('#scenario-identity').inputValue(),`来源权限验收-${width}`);
    assert.equal(await page.getByRole('button',{name:'查询原请求',exact:true}).count(),0);
    await context.request.post(origin+'/__fixture/source-picker/restore');await preview();
    const rejectedFreezeCount=freezeRequests;
    // Lost freeze response after the real server created a draft: only original lookup may proceed.
    await page.route('**/source-selections/freeze',async route=>{await route.fetch();await route.abort('failed');},{times:1});
    await page.getByRole('button',{name:'明确准备研究草稿',exact:true}).click();
    await page.getByRole('button',{name:'查询原请求',exact:true}).waitFor();
    assert.equal(await page.getByRole('button',{name:'确认冻结资料，进入研究草稿'}).count(),0);
    assert.equal(freezeRequests,rejectedFreezeCount+1);
    await page.getByRole('button',{name:'查询原请求',exact:true}).click();
    await page.getByRole('button',{name:'确认冻结资料，进入研究草稿'}).waitFor();
    assert.equal(freezeRequests,rejectedFreezeCount+1);const created=await getState();assert.equal(created.sessions.length,before.sessions.length+1);assert.equal(created.native_prompt_calls,before.native_prompt_calls);
    await page.getByRole('button',{name:'确认冻结资料，进入研究草稿'}).click();
    await page.getByRole('region',{name:'组合包计算与文件回执'}).waitFor();
    const send=page.waitForResponse(r=>r.url().endsWith('/messages')&&r.request().method()==='POST');
    await page.getByRole('button',{name:'发送研究问题',exact:true}).click();assert.equal((await send).status(),202);
    checks.push({width,freezeOnce:true,lostReplyLookup:true,explicitSend:'offline native fixture only',sourceRequests});
    await context.close();
  }
  // A genuine server Native RPC outcome unknown stays unknown under original lookup.
  const unknownContext=await browser.newContext(),unknownPage=await unknownContext.newPage();
  await unknownPage.route('**/*',route=>new URL(route.request().url()).origin===origin?route.continue():route.abort());
  await unknownPage.goto(origin+'/__fixture/login');await unknownPage.getByRole('button',{name:'进入离线验收'}).click();
  const unknownFixture=await (await unknownContext.request.get(origin+'/__fixture/source-picker')).json();
  await unknownPage.goto(origin+'/#/fingpt');await unknownPage.getByRole('button',{name:'选择研究场景',exact:true}).click();
  await unknownPage.locator('#scenario-scenario').selectOption('pack-research-prep');await unknownPage.locator('#scenario-kind').selectOption('topic');await unknownPage.locator('#scenario-identity').fill('Synthetic 真正未知创建');
  await unknownPage.locator('#scenario-as_of').fill(unknownFixture.as_of);await unknownPage.locator('#scenario-cutoff_at').fill(unknownFixture.as_of+'T23:59:59+08:00');await unknownPage.locator('#scenario-question').fill('Synthetic 原请求只查询，不重发');
  await unknownPage.locator('#scenario-material-mode').selectOption('sources');await unknownPage.locator('#scenario-source-browse').selectOption(unknownFixture.sessions[0]);await unknownPage.locator('[name="scenario-source"]').check();
  await unknownPage.getByRole('button',{name:'只读资格预览',exact:true}).click();await unknownPage.getByRole('heading',{name:'Host 只读资格预览 · partial',exact:true}).waitFor();
  const creationBefore=await (await unknownContext.request.get(origin+'/__fixture/source-picker/creation-state')).json();
  await unknownContext.request.post(origin+'/__fixture/source-picker/unknown-next');
  const unknownReply=unknownPage.waitForResponse(r=>r.url().endsWith('/source-selections/freeze'));
  await unknownPage.getByRole('button',{name:'明确准备研究草稿',exact:true}).click();const unknownResponse=await unknownReply,unknownError=await unknownResponse.json();
  assert.ok(unknownResponse.status()>=400,JSON.stringify(unknownError));assert.equal(unknownError.error.handoff_outcome,undefined);
  const unknownLookup=unknownPage.waitForResponse(r=>r.url().includes('/handoff-requests/'));
  await unknownPage.getByRole('button',{name:'查询原请求',exact:true}).click();assert.equal((await (await unknownLookup).json()).state,'creation_outcome_unknown');
  await unknownPage.getByText('创建结果尚未确认；不自动重复创建',{exact:true}).waitFor();
  await unknownPage.reload();await unknownPage.getByRole('button',{name:'选择研究场景',exact:true}).click();await unknownPage.getByRole('button',{name:'查询原请求',exact:true}).click();
  assert.equal(await unknownPage.getByRole('button',{name:'明确准备研究草稿',exact:true}).count(),0);
  assert.equal(await unknownPage.getByRole('button',{name:'确认冻结资料，进入研究草稿'}).count(),0);
  const creationAfter=await (await unknownContext.request.get(origin+'/__fixture/source-picker/creation-state')).json();assert.equal(creationAfter.attempts,creationBefore.attempts+1);
  checks.push({serverCreationUnknown:true,reloadLookup:true,nativeCreationAttempts:1,automaticRetries:0});await unknownContext.close();
  // Post-preview proof corruption returns an actual 409 + not_created, preserving editable inputs.
  const context=await browser.newContext({viewport:{width:390,height:1000}}),page=await context.newPage();
  await page.route('**/*',route=>new URL(route.request().url()).origin===origin?route.continue():route.abort());
  await page.goto(origin+'/__fixture/login');await page.getByRole('button',{name:'进入离线验收'}).click();
  const fixture=await (await context.request.get(origin+'/__fixture/source-picker')).json();
  await page.goto(origin+'/#/fingpt');await page.getByRole('button',{name:'选择研究场景',exact:true}).click();
  await page.locator('#scenario-scenario').selectOption('pack-research-prep');await page.locator('#scenario-kind').selectOption('topic');await page.locator('#scenario-identity').fill('Synthetic 409输入保留');
  await page.locator('#scenario-as_of').fill(fixture.as_of);await page.locator('#scenario-cutoff_at').fill(fixture.as_of+'T23:59:59+08:00');await page.locator('#scenario-question').fill('Synthetic 来源变化后保留此问题');
  await page.locator('#scenario-material-mode').selectOption('sources');await page.locator('#scenario-source-browse').selectOption(fixture.sessions[0]);await page.locator('[name="scenario-source"]').check();
  await page.getByRole('button',{name:'只读资格预览',exact:true}).click();await page.getByRole('heading',{name:'Host 只读资格预览 · partial',exact:true}).waitFor();
  await context.request.post(origin+'/__fixture/source-picker/change');
  const freeze=page.waitForResponse(r=>r.url().endsWith('/source-selections/freeze'));
  await page.getByRole('button',{name:'明确准备研究草稿',exact:true}).click();const rejected=await freeze;assert.equal(rejected.status(),409);assert.equal((await rejected.json()).error.handoff_outcome,'not_created');
  await page.waitForFunction(()=>!document.querySelector('#scenario-question').disabled);
  assert.equal(await page.locator('#scenario-question').inputValue(),'Synthetic 来源变化后保留此问题');assert.equal(await page.locator('[name="scenario-source"]:checked').count(),1);
  assert.equal(await page.getByRole('button',{name:'查询原请求',exact:true}).count(),0);assert.equal(await page.locator('[data-scenario-freeze]').isDisabled(),true);
  await context.request.post(origin+'/__fixture/source-picker/delete-empty');await page.locator('#scenario-source-browse').selectOption(fixture.empty);
  await page.locator('.pack-source-picker [role=alert]').filter({hasText:'已删除或永久清理'}).waitFor();
  checks.push({status409:true,notCreatedProof:true,inputsPreserved:true,status410:true});await context.close();
  assert.deepEqual(errors,[]);
  await writeFile(path.join(output,'result.json'),JSON.stringify({fixture:true,checks,errors,model:'NOT_RUN',production:'NOT_RUN'},null,2));
  console.log(JSON.stringify({status:'PASS',checks:checks.length,output}));
} catch(error) {
  await writeFile(path.join(output,'failure.json'),JSON.stringify({error:error.message,checks,errors},null,2));throw error;
} finally {
  if(browser)await browser.close();
  if(child.exitCode===null)child.kill('SIGTERM');await exit;await new Promise(resolve=>log.end(resolve));
  const current=await stat(scratch);assert.equal(current.dev,owner.dev);assert.equal(current.ino,owner.inode);
  // Frozen test skill directories are deliberately read-only. Restore owner write
  // only inside this registered ephemeral root after its Host/Chrome have exited.
  async function writable(dir){await chmod(dir,0o700);for(const item of await readdir(dir,{withFileTypes:true}))if(item.isDirectory())await writable(path.join(dir,item.name));}
  await writable(scratch);
  await rm(scratch,{recursive:true});
  const hashes={};
  async function archive(dir){for(const item of await readdir(dir,{withFileTypes:true})){const file=path.join(dir,item.name);if(item.isDirectory())await archive(file);else if(item.name!=='sha256.json'){const bytes=await readFile(file);hashes[path.relative(output,file)]=createHash('sha256').update(bytes).digest('hex');}}}
  await archive(output);await writeFile(path.join(output,'sha256.json'),JSON.stringify(hashes,null,2));
  for(const [file,hash] of Object.entries(hashes))assert.equal(createHash('sha256').update(await readFile(path.join(output,file))).digest('hex'),hash);
  await writeFile(path.join(output,'cleanup.json'),JSON.stringify({task,tempRemoved:true,hashReadback:true}));
}
