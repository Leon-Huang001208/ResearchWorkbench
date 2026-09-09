#!/usr/bin/env node
import assert from 'node:assert/strict';
import fs from 'node:fs';
import http from 'node:http';
import os from 'node:os';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const projectRoot=process.cwd();
const artifactRoot=path.join(projectRoot,'outputs/merged-platform-product-prototype');
const screenshotRoot=path.join(projectRoot,'output/playwright/merged-platform-product-prototype');
const chromePath=process.env.CHROME_EXECUTABLE_PATH||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const log=(event,details={})=>process.stdout.write(`${JSON.stringify({at:new Date().toISOString(),event,...details})}\n`);

async function loadChromium(){
  try{const module=await import('playwright-core');return module.chromium||module.default?.chromium;}catch(primaryError){
    const npxRoot=path.join(os.homedir(),'.npm/_npx');
    if(fs.existsSync(npxRoot))for(const directory of fs.readdirSync(npxRoot)){
      const entry=path.join(npxRoot,directory,'node_modules/playwright-core/index.js');
      if(fs.existsSync(entry))try{const module=await import(pathToFileURL(entry).href);return module.chromium||module.default?.chromium;}catch(error){log('playwright_candidate_failed',{entry,message:error.message});}
    }
    throw new Error(`playwright-core unavailable: ${primaryError.message}`);
  }
}

function contentType(file){return ({'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.png':'image/png','.md':'text/markdown; charset=utf-8'})[path.extname(file)]||'application/octet-stream';}
function startServer(){return new Promise((resolve,reject)=>{const server=http.createServer((request,response)=>{try{const pathname=decodeURIComponent(new URL(request.url,'http://localhost').pathname);if(pathname==='/favicon.ico'){response.writeHead(204);response.end();return;}const relative=pathname==='/'?'index.html':pathname.replace(/^\//,'');const target=path.resolve(artifactRoot,relative);if(!target.startsWith(`${artifactRoot}${path.sep}`)&&target!==path.join(artifactRoot,'index.html')){response.writeHead(403);response.end('forbidden');return;}if(!fs.existsSync(target)||fs.statSync(target).isDirectory()){response.writeHead(404);response.end('not found');return;}response.writeHead(200,{'Content-Type':contentType(target),'Cache-Control':'no-store'});fs.createReadStream(target).pipe(response);}catch(error){log('static_server_error',{message:error.message});response.writeHead(500);response.end('server error');}});server.on('error',reject);server.listen(0,'127.0.0.1',()=>resolve({server,baseUrl:`http://127.0.0.1:${server.address().port}`}));});}

const requiredRoutes=[
  ['/market-home','/market-home'],['/themes','/themes'],['/assets/AU-DEMO','/assets/:assetId'],['/fingpt','/fingpt'],
  ['/claw','/claw'],['/watchlists','/watchlists'],['/research-library','/research-library'],['/capabilities','/capabilities'],
];
const viewports=[{width:1600,height:1000,name:'wide'},{width:1180,height:820,name:'compact'},{width:820,height:1180,name:'tablet'},{width:390,height:844,name:'mobile'}];

async function main(){
  const chromium=await loadChromium();
  if(!fs.existsSync(chromePath))throw new Error(`Chrome not found: ${chromePath}`);
  fs.mkdirSync(screenshotRoot,{recursive:true});
  const {server,baseUrl}=await startServer(); let browser;
  try{
    browser=await chromium.launch({headless:true,executablePath:chromePath});
    const context=await browser.newContext({viewport:{width:1600,height:1000}});const page=await context.newPage();const errors=[];
    page.on('console',message=>{if(message.type()==='error')errors.push(`console: ${message.text()}`);});page.on('pageerror',error=>errors.push(`pageerror: ${error.message}`));
    for(const [route,pattern] of requiredRoutes){await page.goto(`${baseUrl}/#${route}`,{waitUntil:'domcontentloaded'});await page.locator(`[data-page-route="${pattern}"]`).waitFor();log('route_pass',{route,pattern});}
    for(const viewport of viewports){await page.setViewportSize(viewport);await page.goto(`${baseUrl}/#/market-home`,{waitUntil:'domcontentloaded'});const metrics=await page.evaluate(()=>({scrollWidth:document.documentElement.scrollWidth,innerWidth,scrollHeight:document.documentElement.scrollHeight,innerHeight}));assert.ok(metrics.scrollWidth<=metrics.innerWidth,`${viewport.name} horizontal overflow ${JSON.stringify(metrics)}`);log('viewport_pass',{viewport,metrics});await page.screenshot({path:path.join(screenshotRoot,`market-home-${viewport.name}.png`),fullPage:true});}
    await page.setViewportSize({width:1600,height:1000});
    for(const id of ['J01','J02','J03','J04','J05']){await page.goto(`${baseUrl}/#/market-home`,{waitUntil:'domcontentloaded'});const expected=await page.evaluate((journeyId)=>{AlphaJourneys.start(journeyId);return AlphaJourneys.journeys[journeyId].steps;},id);for(let index=1;index<expected.length;index+=1){await page.locator('[data-journey="next"]').click();await page.waitForTimeout(25);}assert.equal(await page.evaluate(()=>location.hash.slice(1)),expected.at(-1));log('journey_pass',{id,steps:expected.length,finish:expected.at(-1)});}
    for(const state of ['default','loading','empty','partial','stale','unavailable','quarantined','error','permission_denied','blocked_runtime']){await page.evaluate(value=>{AlphaPrototype.setState({demoState:value});AlphaPrototype.router.refresh();},state);await page.locator('[data-page-route]').waitFor();log('demo_state_pass',{state});}
    await page.goto(`${baseUrl}/#/watchlists?tab=inbox`,{waitUntil:'domcontentloaded'});const inbox=await page.locator('[data-page-route="/watchlists"]').innerText();assert.match(inbox,/skipped_data_stale/);assert.doesNotMatch(inbox,/skipped_data_stale[^\n]*triggered/i);log('stale_alert_guard_pass');
    for(const [route,name] of [['/fingpt','fingpt-home'],['/fingpt?view=result','fingpt-result'],['/claw?view=run','claw-run'],['/claw?state=blocked_runtime','claw-blocked'],['/themes?pack=gold','theme-gold'],['/assets/AU-DEMO','asset-detail']]){await page.evaluate(()=>AlphaPrototype.setState({demoState:'default'}));await page.goto(`${baseUrl}/#${route}`,{waitUntil:'domcontentloaded'});await page.screenshot({path:path.join(screenshotRoot,`${name}.png`),fullPage:true});log('screenshot_pass',{route,name});}
    assert.deepEqual(errors,[]);await context.close();log('prototype_e2e_pass',{routes:requiredRoutes.length,viewports:viewports.length,journeys:5,screenshots:10});
  }finally{if(browser)await browser.close();await new Promise(resolve=>server.close(resolve));}
}

main().catch(error=>{log('prototype_e2e_fail',{message:error.message,stack:error.stack});process.exitCode=1;});
