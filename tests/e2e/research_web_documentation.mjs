/** Real, read-only settings → isolated diagram navigation acceptance. */
import assert from 'node:assert/strict';
import {mkdir, writeFile, appendFile, readFile} from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';

const origin = new URL(process.env.RESEARCH_WEB_URL || 'http://127.0.0.1:8088');
if (origin.protocol !== 'http:' || !['localhost','127.0.0.1'].includes(origin.hostname)) throw new Error('Local Web only');
const output = path.resolve('outputs/research-web-ui-acceptance/documentation');
const receipt = {status:'running', steps:[], requests:[], repositoryNavigation:[]};
const serverMode=process.env.RESEARCH_ACCEPTANCE_SERVER_MODE || 'documentation-only';
if(!['documentation-only','native'].includes(serverMode)) throw new Error('Unknown acceptance server mode');
const inventory=JSON.parse(await readFile('docs/architecture/research-web/architecture-map.json','utf8'));
receipt.inputs={
  scriptSha256:createHash('sha256').update(await readFile(new URL(import.meta.url))).digest('hex'),
  mapSha256:createHash('sha256').update(await readFile('docs/architecture/research-web/architecture-map.json')).digest('hex'),
  describedRevision:inventory.reading.repository.revision,
  serverMode:serverMode==='native' ? 'isolated Native service; Runtime connected probe required; lifecycle evidence recorded separately' : 'isolated documentation and UI HTTP surface; lifespan disabled; Runtime readiness not asserted',
};
const uniqueOperations=new Set(inventory.apis.map(api=>`${api.method} ${api.path}`)).size;
let browser;
try {
  await mkdir(output,{recursive:true}); await mkdir('logs',{recursive:true});
  if(serverMode==='native') {
    const response=await fetch(`${origin.origin}/api/research/runtime`);
    assert.equal(response.status,200);assert.equal((await response.json()).connected,true);
    receipt.steps.push('isolated_native_runtime_connected');
  }
  const {chromium} = await import(process.env.RESEARCH_PLAYWRIGHT_MODULE || 'playwright-core');
  browser = await chromium.launch({headless:true,executablePath:process.env.CHROME_EXECUTABLE_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
  const context = await browser.newContext({viewport:{width:1440,height:900}});
  await context.route('**/*',route => ['GET','HEAD'].includes(route.request().method()) ? route.continue() : route.abort());
  context.on('response',response=>{
    if(response.url().includes('/documentation/')) receipt.requests.push({path:new URL(response.url()).pathname,status:response.status(),site:response.request().headers()['sec-fetch-site']});
  });
  const page = await context.newPage();
  await page.goto(`${origin.origin}/?acceptance=docs#/settings`);
  await page.getByRole('navigation',{name:'设置分类',exact:true}).getByRole('link',{name:'架构文档',exact:true}).click();
  await page.screenshot({path:path.join(output,'settings-documentation.png'),fullPage:true});
  const link = page.getByRole('link',{name:'打开架构文档 ↗',exact:true});
  await link.waitFor();
  assert.equal(await link.getAttribute('rel'),'noopener noreferrer');
  const popupPromise=context.waitForEvent('page'); await link.click();
  const docs=await popupPromise; await docs.waitForLoadState('domcontentloaded');
  await docs.getByRole('heading',{name:'从研究问题，到真实文件交付',exact:true}).waitFor();
  assert.equal(await docs.locator('.card').count(),inventory.diagrams.length); receipt.steps.push('settings_popup_registered_diagrams');
  await docs.screenshot({path:path.join(output,'index.png'),fullPage:true});
  const atlasResponsePromise=docs.waitForResponse(r=>new URL(r.url()).pathname.endsWith('/api-atlas.html'));
  await docs.getByRole('link',{name:/打开当前 API Atlas/}).click();
  const atlasResponse=await atlasResponsePromise;
  assert.equal(atlasResponse.status(),200,'API Atlas must load from the isolated documentation endpoint');
  await docs.getByRole('heading',{name:'Research Web API Atlas',exact:true}).waitFor();
  assert.equal(await docs.locator('.api').count(),inventory.apis.length,'Atlas must retain every source declaration');
  assert.equal(await docs.locator('.metric').filter({hasText:'唯一接口'}).locator('b').innerText(),String(uniqueOperations));
  await docs.getByRole('searchbox',{name:'搜索接口',exact:true}).fill('report-workflows');
  assert.ok(await docs.locator('.api:visible').count()>0,'Atlas search must retain matching report Workflow routes');
  await docs.getByRole('searchbox',{name:'搜索接口',exact:true}).fill('missing-route-for-acceptance');
  await docs.getByText('没有匹配的接口。',{exact:true}).waitFor({state:'visible'});
  receipt.steps.push('api_atlas_counts_and_search');
  await docs.goto(`${origin.origin}/api/research/documentation/index.html`);
  for(const filename of ['00-system-overview.html','01-deployment.html','08-iteration-docs.html']) {
    await docs.goto(`${origin.origin}/api/research/documentation/index.html`);
    const responsePromise=docs.waitForResponse(r=>new URL(r.url()).pathname.endsWith(`/${filename}`));
    await docs.locator(`a.card[href="${filename}"]`).click(); const response=await responsePromise;
    assert.equal(response.status(),200,`Sandbox index navigation must load ${filename}`);
    const csp=response.headers()['content-security-policy'];
    assert.ok(csp.includes('sandbox allow-scripts')&&!csp.includes('allow-same-origin'));
    await docs.waitForLoadState('domcontentloaded');
    const buttons=docs.getByRole('button'); assert.ok(await buttons.count()>0,'Viewer controls rendered');
    const theme=docs.getByRole('button',{name:'Toggle color theme',exact:true});
    const previous=await theme.innerText(); await theme.click();
    assert.notEqual(await theme.innerText(),previous,'Opaque sandbox must retain real theme interaction');
    if(filename==='08-iteration-docs.html') {
      await docs.getByRole('button',{name:'Focus 架构对应清单, 源码 · API · 文档 · 图 · 测试, Architecture component',exact:true}).click();
      await docs.getByRole('region',{name:'架构对应清单',exact:true}).waitFor();
      await docs.getByRole('button',{name:'Close semantic passport',exact:true}).click();
      receipt.steps.push('viewer_theme_and_node_details');
    }
    await docs.screenshot({path:path.join(output,filename.replace('.html','.png')),fullPage:true,animations:'disabled'});
    await docs.getByRole('link',{name:'模块说明',exact:true}).click();
    await docs.getByRole('heading',{name:'模块阅读入口',exact:true}).waitFor();
    receipt.steps.push(`sandbox_navigation_${filename}`);
  }
  for(const [moduleId,category] of [['frameworks','研究框架'],['integrations','集成协调器'],['local-integrations','本机集成']]) {
    await docs.goto(`${origin.origin}/api/research/documentation/index.html#module-${moduleId}`);
    await docs.locator(`#module-${moduleId}`).getByRole('link',{name:category,exact:true}).click();
    await docs.getByRole('heading',{name:'Research Web API Atlas',exact:true}).waitFor();
    assert.equal(await docs.locator('#category').inputValue(),category);
    assert.ok(await docs.locator('.api:visible').count()>0);
    assert.deepEqual(await docs.locator('.api:visible').evaluateAll(cards=>[...new Set(cards.map(card=>card.dataset.category))]),[category]);
    receipt.steps.push(`${moduleId}_filtered_api`);
    await docs.getByRole('link',{name:'架构阅读起点',exact:true}).click();
    await docs.getByRole('heading',{name:'从研究问题，到真实文件交付',exact:true}).waitFor();
  }
  for(const [kind,file] of [['documentation','docs/architecture/research-web/08-research-frameworks.md'],['source','app/research_web/frameworks/routes.py'],['test','tests/research_web/test_frameworks.py']]) {
    await docs.goto(`${origin.origin}/api/research/documentation/index.html#module-frameworks`);
    const module=docs.locator('#module-frameworks');
    await module.locator('summary').click();
    const link=module.getByRole('link',{name:file,exact:true});
    const href=await link.getAttribute('href');
    assert.equal(href,`${inventory.reading.repository.url}/blob/${inventory.reading.repository.revision}/${file}`);
    const evidence={kind,url:href,status:'NOT_RUN'};
    const navigation=docs.waitForNavigation({waitUntil:'domcontentloaded',timeout:15000}).then(response=>({response}),error=>({error}));
    await link.click({timeout:5000,noWaitAfter:true});
    let navigationPending=true;
    try {
      const result=await navigation;
      if(result.error) throw result.error;
      navigationPending=false;
      evidence.httpStatus=result.response?.status();evidence.finalURL=docs.url();evidence.title=await docs.title();
      if([429,502,503,504].includes(evidence.httpStatus)) {
        evidence.status='BLOCKED';evidence.error=`External service HTTP ${evidence.httpStatus}`;
        continue;
      }
      assert.equal(evidence.httpStatus,200);
      assert.ok(evidence.title.includes(path.posix.basename(file)));
      await docs.screenshot({path:path.join(output,`repository-${kind}.png`),fullPage:false});
      evidence.status='PASS';
    } catch(error) {
      evidence.status=navigationPending && (error.name==='TimeoutError' || /net::ERR_(?:CONNECTION|NAME_NOT_RESOLVED|TIMED_OUT|INTERNET_DISCONNECTED|ADDRESS_UNREACHABLE|CERT_)/.test(String(error))) ? 'BLOCKED' : 'FAIL';
      evidence.error=String(error);
    } finally {
      receipt.repositoryNavigation.push(evidence);
    }
  }
  if(receipt.repositoryNavigation.some(item=>item.status==='FAIL')) {
    receipt.status='failed';process.exitCode=1;
  } else if(receipt.repositoryNavigation.some(item=>item.status!=='PASS')) {
    receipt.status='blocked';process.exitCode=1;
  } else {
    receipt.status='passed';
  }
  receipt.steps.push('repository_link_identity');
} catch(error) {
  receipt.status='failed';receipt.error=String(error);process.exitCode=1;
} finally {
  await browser?.close();
  await writeFile(path.join(output,'receipt.json'),JSON.stringify(receipt,null,2));
  await appendFile('logs/research-web-documentation-e2e.jsonl',JSON.stringify({time:new Date().toISOString(),status:receipt.status,steps:receipt.steps,error:receipt.error})+'\n');
  console.log(JSON.stringify(receipt,null,2));
}
