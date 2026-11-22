// Original engine contracts exercised in an isolated staged tree, using fake HTTP and no database.
import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, realpathSync, rmSync, existsSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { stageEngine } from '../runtime.mjs';
const deps = path.resolve(import.meta.dirname, '../vendor/aihot/node_modules/undici');
test('staged original free collectors, forbidden origin and pre-handler API authentication', { skip: !existsSync(deps) }, async t => {
  const dir = realpathSync(mkdtempSync(path.join(os.tmpdir(), 'rwb-engine-contract-')));
  t.after(() => rmSync(dir,{recursive:true}));
  process.env.DATABASE_URL='postgres://unreachable@127.0.0.1:1/rwb_engine_test';
  process.env.MODEL_CALLS_ENABLED='false'; process.env.COLLECT_ENABLED='false';
  process.env.RWB_AI_NEWS_TOKEN='rwb-contract-private-token-long';
  const stage=stageEngine(dir), load=file=>import(pathToFileURL(path.join(stage,file)).href);
  const {MockAgent,getGlobalDispatcher,setGlobalDispatcher}=await import(pathToFileURL(path.join(deps,'index.js')).href);
  const previous=getGlobalDispatcher(), mock=new MockAgent();mock.disableNetConnect();setGlobalDispatcher(mock);
  t.after(async()=>{setGlobalDispatcher(previous);await mock.close();});
  const {config}=await load('packages/backend/src/config.ts');config.allowPrivateNetworkFetch=true;config.egressProxyUrl=null;
  const [{fetchRss},{fetchWebList},{fetchJsonList},{assertPublicUrl}]=await Promise.all([load('packages/backend/src/sources/rss.ts'),load('packages/backend/src/sources/web-list.ts'),load('packages/backend/src/sources/json-list.ts'),load('packages/backend/src/lib/url.ts')]);
  const origin='https://publisher.invalid';const source=(kind,config)=>({id:'rwb-fixture',kind,config,cursor:null,participation_mode:'editorial'});
  mock.get(origin).intercept({path:'/rss'}).reply(200,'<rss><channel><item><title>Original engine RSS</title><link>https://publisher.invalid/post</link><pubDate>Fri, 16 Oct 2026 10:00:00 GMT</pubDate></item></channel></rss>');
  const rss=await fetchRss(source('rss',{feedUrl:origin+'/rss'}));assert.equal(rss.candidates[0].title,'Original engine RSS');
  mock.get(origin).intercept({path:'/web'}).reply(200,'<a href="/post"><h3>Original engine HTML</h3><p>October 16, 2026</p></a>');
  const web=await fetchWebList(source('web_list',{url:origin+'/web',parseMode:'html',itemSelector:'a:has(h3)',titleSelector:'h3',publishedAtSelector:'p',publishedAtUtcOffset:'+00:00'}));assert.equal(web[0].title,'Original engine HTML');
  mock.get(origin).intercept({path:'/json'}).reply(200,JSON.stringify([{title:'Original engine JSON',url:origin+'/post'}]));
  const json=await fetchJsonList(source('json_list',{url:origin+'/json',titlePaths:['title'],urlTemplate:'{raw:url}'}));assert.equal(json[0].title,'Original engine JSON');
  await assert.rejects(assertPublicUrl('https://aihot.news/api/site/today',true),/rwb_outbound_origin_forbidden/);
  const {buildApp}=await load('apps/api/src/app.ts');const app=await buildApp();t.after(()=>app.close());
  for(const url of ['/api/site/today','/api/health','/api/admin/me','/feeds/rss.xml','/missing']) {
    const response=await app.inject({method:'GET',url});assert.equal(response.statusCode,401,url);
  }
  const response=await app.inject({method:'GET',url:'/missing',headers:{'x-rwb-ai-news-token':process.env.RWB_AI_NEWS_TOKEN}});assert.equal(response.statusCode,404);
  mock.assertNoPendingInterceptors();
});
