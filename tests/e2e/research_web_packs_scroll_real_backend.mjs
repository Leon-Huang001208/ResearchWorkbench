/** Synthetic account; real Host catalog/ownership/snapshots, no paid/model I/O. */
import assert from 'node:assert/strict';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { createWriteStream } from 'node:fs';
import { mkdir, writeFile } from 'node:fs/promises';
import { pathToFileURL } from 'node:url';

const phase=process.env.RWB_SCROLL_PHASE==='red'?'red':'green';
const project=process.cwd(),output=path.join(project,'outputs/research-web-packs-scroll',phase);
await mkdir(output,{recursive:true});
const log=createWriteStream(path.join(project,`logs/pack-scroll-${phase}-backend.log`));
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
  const context=await browser.newContext({viewport:{width:390,height:1000}}),page=await context.newPage();
  page.setDefaultTimeout(20000);page.on('pageerror',error=>errors.push(error.message));
  await page.route('**/*',route=>new URL(route.request().url()).origin===origin?route.continue():route.abort());
  await page.goto(origin+'/__fixture/login');await page.getByRole('button',{name:'进入离线验收'}).click();
  const fixture=await (await context.request.get(origin+'/__fixture/packs')).json();
  await page.goto(origin+'/#/fingpt?session='+fixture.source_session_id);
  await page.getByRole('button',{name:'选择研究场景',exact:true}).click();
  await page.locator('#scenario-scenario').selectOption('pack-event-review');
  const inspect=selector=>page.locator(selector).evaluate(field=>{
    const body=field.closest('.d-drawer-body'),rect=field.getBoundingClientRect(),container=body.getBoundingClientRect();
    return {scrollTop:body.scrollTop,top:rect.top,bottom:rect.bottom,viewportTop:container.top,viewportBottom:container.bottom,value:field.value,focused:document.activeElement===field,selectionStart:field.selectionStart,selectionEnd:field.selectionEnd};
  });
  const focusVisible=async selector=>{
    await page.locator(selector).evaluate(field=>{const body=field.closest('.d-drawer-body');body.scrollTop+=field.getBoundingClientRect().top-body.getBoundingClientRect().top-body.clientHeight/2;field.focus({preventScroll:true});});
  };
  const typeVisible=async(selector,keys,expected)=>{
    await focusVisible(selector);const before=await inspect(selector);const samples=[];
    if(selector.endsWith('-post_sessions'))await page.screenshot({path:path.join(output,'post-focused-before.png'),fullPage:true});
    for(const key of keys){
      await page.keyboard.press(key);const after=await inspect(selector);samples.push({key,...after});
      if(selector.endsWith('-post_sessions')&&samples.length===1)await page.screenshot({path:path.join(output,'post-first-key.png'),fullPage:true});
      await writeFile(path.join(output,'keystrokes.json'),JSON.stringify({synthetic:true,selector,before,samples},null,2));
      assert.equal(after.focused,true,'typing must keep the original field focus');
      assert.ok(Math.abs(after.scrollTop-before.scrollTop)<=2,'drawer scroll moved during key '+key+': '+JSON.stringify({before,after}));
      assert.ok(after.top>=after.viewportTop && after.bottom<=after.viewportBottom,'typed field left visible drawer');
    }
    assert.equal((await inspect(selector)).value,expected);checks.push({selector,before,samples});
  };
  await page.screenshot({path:path.join(output,'before-scroll.png'),fullPage:true});
  await typeVisible('#scenario-align_event_trading_day-post_sessions',['1','2','3','ArrowLeft','4'],'1243');
  await page.keyboard.press('Tab');assert.equal(await page.locator('#scenario-align_event_trading_day-pre_sessions').evaluate(field=>document.activeElement===field),true);
  await typeVisible('#scenario-align_event_trading_day-release_at',['2','0','2','6','ArrowLeft','7'],'20276');
  const text=await inspect('#scenario-align_event_trading_day-release_at');assert.equal(text.selectionStart,4);assert.equal(text.selectionEnd,4);
  await page.locator('#scenario-question').fill('长文本'.repeat(1000));
  await focusVisible('#scenario-question');await page.keyboard.press('End');
  await typeVisible('#scenario-question',['A','B','C'],'长文本'.repeat(1000)+'ABC');
  await page.screenshot({path:path.join(output,'after-scroll.png'),fullPage:true});
  await page.locator('#scenario-scenario').selectOption('pack-ownership-structure');
  assert.equal(await page.locator('.d-drawer-body').evaluate(element=>element.scrollTop),0,'new scenario should start at top');
  await page.locator('#scenario-scenario').selectOption('pack-event-review');
  await focusVisible('#scenario-align_event_trading_day-post_sessions');
  await page.keyboard.press('Escape');assert.equal(await page.locator('.scenario-panel').count(),0);
  await page.getByRole('button',{name:'选择研究场景',exact:true}).click();
  assert.equal(await page.locator('.d-drawer-body').evaluate(element=>element.scrollTop),0,'new drawer opening should start at top');
  const finalState=await (await context.request.get(origin+'/__fixture/state')).json();
  assert.equal(finalState.native_prompt_calls,0);checks.push({viewport:390,tab:true,closeReopen:true,scenarioSwitch:true,synthetic:true,noModel:true});
  await context.close();
  assert.deepEqual(errors,[]);
  await writeFile(path.join(output,'result.json'),JSON.stringify({fixture:true,checks,errors,realModel:'NOT_RUN',production:'NOT_RUN'},null,2));
  console.log(JSON.stringify({status:'PASS',checks:checks.length,output}));
} catch(error) {
  await writeFile(path.join(output,'failure.json'),JSON.stringify({error:error.message,checks,errors},null,2));throw error;
} finally {
  if(browser)await browser.close();child.kill('SIGTERM');await exit;log.end();
}
