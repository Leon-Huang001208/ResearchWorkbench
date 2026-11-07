/** Real UI against an owned loopback-only empty-data fixture. Never uses a resident. */
import assert from 'node:assert/strict';
import { mkdir, readFile, writeFile, appendFile } from 'node:fs/promises';
import http from 'node:http';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { PRIMARY_NAVIGATION, secondaryEntries } from '../../app/research_web/ui/module-navigation.mjs';
import { parseRoute } from '../../app/research_web/ui/core.mjs';

const output=path.resolve(process.env.RWB_NAV_OUTPUT || 'logs/module-navigation-browser');
const checkFilter=process.env.RWB_NAV_CHECK_FILTER || '';
const ui=path.resolve('app/research_web/ui');
await mkdir(output,{recursive:true});
const errors=[], external=[], writes=[], requests=[], refreshRequests=[], checks=[], consoleErrors=[];
const account={id:'11111111-1111-4111-8111-111111111111',username:'navigation_fixture',role:'admin',primary:true};
const mime={'.html':'text/html','.css':'text/css','.mjs':'text/javascript','.js':'text/javascript','.json':'application/json','.png':'image/png','.svg':'image/svg+xml'};
function payload(p){
 if(p==='/runtime')return {connected:true,credential_configured:true,model:'offline-fixture'};
 if(p==='/models')return {groups:[],failures:[]};
 if(p==='/data/catalog')return {summary:{},capabilities:[],sources:[],bindings:[]};
 if(p==='/connections')return {sources:[],summary:{}};
 if(p.startsWith('/navigation/'))return {mode:p.split('/').at(-1),revision:0,pinned:[],project_order:[]};
 if(p==='/portfolio-decisions/readiness')return {status:'BLOCKED',gaps:['工程夹具：真实策略未验收']};
 if(p.startsWith('/operations'))return {summary:{},runtime:{},providers:[],items:[]};
 if(p.startsWith('/assets/workspace'))return {observations:[],watchlists:[],notes:[],alerts:[],notifications:[]};
 if(p==='/server/api/me')return account;
 return {items:[],sources:[],summary:{},enabled:false,status:'idle',mode:'offline-fixture',capabilities:[],industries:[],events:[],potential:[],challenges:[],trading:[],groups:[],projects:[]};
}
const server=http.createServer(async(req,res)=>{
 try{
  const url=new URL(req.url,'http://127.0.0.1');requests.push({method:req.method,path:url.pathname});
  if(url.pathname.startsWith('/api/')||url.pathname.startsWith('/server/api/')){
   if(req.method==='POST'&&url.pathname==='/api/research/market/refresh'){refreshRequests.push(url.pathname);res.writeHead(200,{'content-type':'application/json'});res.end(JSON.stringify(payload('/market')));return;}
   if(req.method!=='GET'&&req.method!=='HEAD'){writes.push({method:req.method,path:url.pathname});res.writeHead(405,{'content-type':'application/json'});res.end(JSON.stringify({detail:'fixture_read_only'}));return;}
   res.writeHead(200,{'content-type':'application/json','cache-control':'no-store'});res.end(JSON.stringify(payload(url.pathname.replace(/^\/api\/research/,''))));return;
  }
  const relative=url.pathname==='/'?'index.html':url.pathname.replace(/^\/static\//,'');const file=path.resolve(ui,relative);
  if(!file.startsWith(ui+path.sep))throw Error('unsafe_static_path');
  let content=await readFile(file);if(relative==='index.html') content=Buffer.from(content.toString().replace('</head>','<link rel="stylesheet" href="/static/server/account-menu.css"></head>'));res.writeHead(200,{'content-type':mime[path.extname(file)]||'application/octet-stream','cache-control':'no-store'});res.end(content);
 }catch(error){res.writeHead(500);res.end('fixture_failure');errors.push('fixture:'+error.code);}
});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
const origin=`http://127.0.0.1:${server.address().port}`;
let browser;
async function check(label, fn){if(checkFilter&&!label.includes(checkFilter))return;await fn();checks.push(label);await appendFile(path.join(output,'checks.jsonl'),JSON.stringify({label,status:'PASS'})+'\n');}
try{
 const {chromium}=await import(pathToFileURL(process.env.PLAYWRIGHT_CORE_PATH).href);
 browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
 const context=await browser.newContext({viewport:{width:1440,height:900},colorScheme:'dark'});
 await context.addInitScript(user=>{window.__RWB_USER_ID__=user.id;window.__RWB_ACCOUNT__=user;window.__RWB_USER_ROLE__=user.role;},account);
 await context.route('**/*',async route=>{const u=new URL(route.request().url());if(u.origin!==origin){external.push(u.origin);await route.abort();}else await route.continue();});
 const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')consoleErrors.push(m.text())});
 async function go(hash){await page.goto(origin+'/'+hash);await page.locator('.primary-rail').waitFor();await page.locator('.secondary-sidebar').waitFor({state:'attached'});await page.waitForFunction(()=>document.querySelector('.secondary-sidebar [aria-current="page"],.codex-sidebar'));}
 async function visiblePrimary(){
  assert(await page.locator('.primary-rail').isVisible());assert(await page.locator('.primary-rail .rail-brand').isVisible());
  // Theme/account updates can replace the shell; observe connected geometry
  // atomically rather than measuring a detached node from the previous render.
  await page.waitForFunction(()=>{
   const rail=document.querySelector('.primary-rail'),link=rail?.querySelector('.primary-nav .rail-link');
   const expected=innerWidth>1050&&document.querySelector('.app-shell.claw-shell')?72:68;
   return rail?.getBoundingClientRect().width===expected&&link&&getComputedStyle(link).flexDirection==='column';
  },null,{timeout:5000});
 }
 await check('market sidebar retains five visible clickable destinations under the actual full-shell CSS',async()=>{
  const destinations=[['综合总览','#/market'],['行情分析','#/market?view=overview'],['沪深北行情','#/market?view=quotes'],['板块与资金','#/market?view=sectors'],['研究工作台','#/market?view=workbench']];
  await go('#/market');
  const pane=page.getByLabel('全市场概览子页面',{exact:true});
  assert.equal(await pane.getByRole('link').count(),5);
  assert.equal(await page.locator('#main .market-tabs').evaluate(el=>getComputedStyle(el).display),'none','real module-navigation CSS hides the duplicate content tabs');
  for(const [label,href] of destinations){
   const link=pane.getByRole('link',{name:label,exact:true});assert(await link.isVisible(),label);assert.equal(await link.getAttribute('href'),href);
   await link.click();await page.waitForFunction(expected=>location.hash===expected&&document.querySelector('.module-links [aria-current="page"]')?.getAttribute('href')===expected,href);
   assert.equal(await pane.locator('[aria-current="page"]').textContent(),label);assert.equal(await page.locator('#main .market-tabs:visible').count(),0);
  }
  await page.goBack();await page.waitForFunction(()=>location.hash==='#/market?view=sectors');assert.equal(await pane.locator('[aria-current="page"]').textContent(),'板块与资金');
  await page.reload();await pane.waitFor();assert.equal(await pane.locator('[aria-current="page"]').textContent(),'板块与资金');
  await page.screenshot({path:path.join(output,'market-five-destinations-desktop.png')});
  await pane.locator('[data-collapse-sidebar]').click();assert(!(await pane.isVisible()));await visiblePrimary();await page.locator('.sidebar-reopen').click();assert(await pane.isVisible());
  await page.setViewportSize({width:390,height:844});await page.locator('.menu-toggle').click();assert(await pane.isVisible());
  for(const [label] of destinations)assert(await pane.getByRole('link',{name:label,exact:true}).isVisible(),label);
  await page.screenshot({path:path.join(output,'market-five-destinations-mobile.png')});
  await pane.getByRole('link',{name:'沪深北行情',exact:true}).click();await page.waitForFunction(()=>location.hash==='#/market?view=quotes');assert(!(await pane.isVisible()));
  await page.locator('.menu-toggle').click();assert.equal(await pane.locator('[aria-current="page"]').textContent(),'沪深北行情');await page.keyboard.press('Escape');assert(!(await pane.isVisible()));assert(await page.locator('.menu-toggle').evaluate(el=>el===document.activeElement));
  await page.setViewportSize({width:1440,height:900});
 });
 await check('all canonical modules render secondary navigation',async()=>{
  for(const hash of [...PRIMARY_NAVIGATION.map(x=>x.href),'#/progress','#/settings/general','#/account','#/history?mode=claw']){await go(hash);await visiblePrimary();assert(await page.locator('.secondary-sidebar').isVisible(),hash);assert.equal(await page.locator('#main .progress-tabs:visible,#main .intel-tabs:visible,#main .settings-navigation:visible,#main .market-tabs:visible,#main .capability-workspace-nav:visible').count(),0,hash);}
 });
 await check('all module child destinations select the correct row',async()=>{
  for(const hash of ['#/progress','#/assets','#/settings/general','#/market','#/simulation/etf','#/skills','#/aihot/daily','#/intel/overview','#/automations','#/frameworks','#/operations','#/reports','#/account','#/history']){
   for(const item of secondaryEntries(parseRoute(hash),{account})){await go(item.href);const selected=page.locator('.module-links [aria-current="page"]');assert.equal(await selected.count(),1,item.href);assert.equal(await selected.textContent(),item.label,item.href);}
  }
 });
 await check('collapse preserves primary labels, releases only the secondary width, and persists per module',async()=>{
  await go('#/progress');const before=await page.locator('.primary-rail').boundingBox();const contentBefore=await page.locator('#main').boundingBox();
  await page.locator('.secondary-sidebar [data-collapse-sidebar]').click();assert(!(await page.locator('.secondary-sidebar').isVisible()));await visiblePrimary();assert.equal((await page.locator('.primary-rail').boundingBox()).width,before.width);assert(await page.locator('.primary-nav .rail-label').first().isVisible());assert((await page.locator('#main').boundingBox()).width>contentBefore.width+150);
  await go('#/assets');assert(await page.locator('.secondary-sidebar').isVisible());await go('#/progress');assert(!(await page.locator('.secondary-sidebar').isVisible()));await page.reload();assert(!(await page.locator('.secondary-sidebar').isVisible()));await page.locator('.sidebar-reopen').click();assert(await page.locator('.secondary-sidebar').isVisible());
 });
 await check('filters and deep links survive navigation, back and refresh',async()=>{
  await go('#/progress?status=developing&module=产品体验');await page.locator('.module-links a').nth(1).click();await page.waitForFunction(()=>location.hash.startsWith('#/progress/changelog'));assert(new URLSearchParams((await page.evaluate(()=>location.hash)).split('?')[1]).get('module')==='产品体验');await page.goBack();assert((await page.evaluate(()=>location.hash)).includes('status=developing'));await page.reload();assert((await page.evaluate(()=>location.hash)).includes('status=developing'));
 });
 await check('narrow secondary drawer is independent from the always-visible primary',async()=>{
  await page.setViewportSize({width:390,height:844});await go('#/progress');await visiblePrimary();assert(!(await page.locator('.secondary-sidebar').isVisible()));await page.locator('.menu-toggle').click();assert.equal(await page.locator('.menu-toggle').getAttribute('aria-expanded'),'true');assert(await page.locator('.secondary-sidebar').isVisible());await visiblePrimary();
  await page.locator('.module-links [aria-current="page"]').click();assert(!(await page.locator('.secondary-sidebar').isVisible()));assert(await page.locator('.menu-toggle').evaluate(el=>el===document.activeElement));
  await page.locator('.menu-toggle').click();await page.keyboard.press('Shift+Tab');assert(await page.locator('.secondary-sidebar').evaluate(el=>el.contains(document.activeElement)));await page.keyboard.press('Escape');assert(!(await page.locator('.secondary-sidebar').isVisible()));assert.equal(await page.locator('.menu-toggle').getAttribute('aria-expanded'),'false');
  await page.locator('.menu-toggle').click();await page.locator('.module-links a').nth(1).click();await page.waitForFunction(()=>location.hash.startsWith('#/progress/changelog'));assert(!(await page.locator('.secondary-sidebar').isVisible()));
  await page.setViewportSize({width:1440,height:900});assert(await page.locator('.secondary-sidebar').isVisible(),'mobile close must not collapse desktop');
 });
 await check('asset topic navigation closes only the secondary drawer',async()=>{
  await page.setViewportSize({width:390,height:844});await go('#/assets?view=financials');await page.locator('.menu-toggle').click();await page.locator('.module-links a[href="#/assets"]').click();await page.waitForFunction(()=>location.hash==='#/assets');assert(!(await page.locator('.secondary-sidebar').isVisible()));await visiblePrimary();
 });
 await check('single-user mode retains ordinary business navigation',async()=>{
  const single=await browser.newContext({viewport:{width:1280,height:720}});await single.route('**/*',async r=>{if(new URL(r.request().url()).origin!==origin){external.push(r.request().url());await r.abort();}else await r.continue();});const tab=await single.newPage();tab.on('pageerror',e=>errors.push(e.message));await tab.goto(origin+'/#/progress');await tab.locator('.module-links').waitFor();assert(await tab.locator('.primary-rail').isVisible());assert.equal(await tab.locator('.navigation-footer a[href="#/settings/general"]').count(),1);assert.equal(await tab.locator('.module-links a').count(),2);await single.close();
 });
 await check('themes, responsive layout, reduced motion and screenshots',async()=>{
  for(const theme of ['dark','light'])for(const [width,height] of [[1440,900],[1280,720],[768,1024],[390,844]]){
   await page.setViewportSize({width,height});for(const [label,hash] of [...PRIMARY_NAVIGATION.map(x=>[x.page,x.href]),['progress','#/progress'],['settings','#/settings/general'],['account','#/account'],['history','#/history']]){
    await go(hash);await page.evaluate(t=>window.ResearchWebTheme.controller.setPreference(t),theme);await visiblePrimary();
    const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1||document.querySelector('#main').scrollWidth>document.querySelector('#main').clientWidth+1);assert.equal(overflow,false,`${label}/${theme}/${width}`);
    await page.mouse.move(width-8,10);assert((await page.locator('.account-trigger').boundingBox()).width<=44,'authenticated avatar retains its original size');await page.screenshot({path:path.join(output,`${label}-${theme}-${width}.png`)});
   }
  }
  await page.emulateMedia({reducedMotion:'reduce'});await page.locator('.menu-toggle').click();assert(await page.locator('.secondary-sidebar').isVisible());assert.equal(await page.locator('.module-links a').first().evaluate(el=>getComputedStyle(el).transitionDuration),'0s');await page.keyboard.press('Escape');
 });
 await check('ordinary account cannot discover admin settings and preferences do not leak',async()=>{
  await page.setViewportSize({width:1440,height:900});await go('#/settings/general');await page.locator('.secondary-sidebar [data-collapse-sidebar]').click();
  const ordinary=await browser.newContext({storageState:await context.storageState(),viewport:{width:1440,height:900}});
  await ordinary.addInitScript(user=>{window.__RWB_USER_ID__=user.id;window.__RWB_ACCOUNT__=user;window.__RWB_USER_ROLE__=user.role;},{...account,id:'22222222-2222-4222-8222-222222222222',role:'user',primary:false});
  await ordinary.route('**/*',async r=>{if(new URL(r.request().url()).origin!==origin){external.push(r.request().url());await r.abort();}else await r.continue();});
  const other=await ordinary.newPage();other.on('pageerror',e=>errors.push(e.message));await other.goto(origin+'/#/settings/general');await other.locator('.module-links').waitFor();assert(await other.locator('.secondary-sidebar').isVisible());assert.equal(await other.locator('.module-links a[href="#/settings/users"]').count(),0);assert.equal(await other.locator('.primary-nav a[href="#/reports"]').count(),0);await ordinary.close();
 });
 assert(checks.length>0,'at least one selected browser check must run');assert.deepEqual(errors,[],'browser runtime errors');assert.deepEqual(consoleErrors,[],'browser console errors');assert.deepEqual(external,[],'no external requests');assert.deepEqual(writes,[],'no business writes');
 const result={status:'PASS',origin,checks,requests:requests.length,browserErrors:errors,consoleErrors,externalRequests:external,businessWrites:writes,stubbedMarketRefreshes:refreshRequests.length,fixture:'isolated empty API; real checked-out UI; no resident or data collectors'};
 await writeFile(path.join(output,'result.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
}catch(error){await writeFile(path.join(output,'failure.json'),JSON.stringify({status:'FAIL',message:error.message,stack:error.stack,errors,checks,external,writes},null,2));throw error;}
finally{await browser?.close();server.closeAllConnections();await new Promise(resolve=>server.close(resolve));}
