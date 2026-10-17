import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, writeFileSync, chmodSync, readFileSync, rmSync, mkdirSync, realpathSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { secret, loadConfig, environment, verifyOrigin, stageEngine, authenticated } from '../runtime.mjs';
import { assertDestination } from '../network-guard.mjs';
import { assertFreePreview, controlRoute } from '../control.mjs';
function fixture(t) {
  const dir = realpathSync(mkdtempSync(path.join(os.tmpdir(), 'rwb-ai-news-')));
  t.after(() => rmSync(dir, { recursive: true }));
  const writeSecret = name => { const file = path.join(dir, name); writeFileSync(file, 'private-rwb-value-'.repeat(3), {mode:0o600}); return file; };
  const c = {port:3099,dataDir:path.join(dir,'state'),tokenFile:writeSecret('token'),adminPasswordFile:writeSecret('admin'),sessionSecretFile:writeSecret('session'),imageSecretFile:writeSecret('image'),database:{host:'127.0.0.1',port:5432,name:'rwb_ai_news_test',user:'postgres',passwordFile:writeSecret('db')}};
  return { dir, c };
}
test('private secrets fail closed; ambient paid credentials and dev bypass do not enter child', t => {
  const { c } = fixture(t);
  process.env.MODEL_CALLS_ENABLED = 'true'; process.env.DEV_AUTH_ROLE = 'admin'; process.env.OPENAI_API_KEY = 'ambient-key';
  t.after(() => {delete process.env.MODEL_CALLS_ENABLED;delete process.env.DEV_AUTH_ROLE;delete process.env.OPENAI_API_KEY;});
  const env = environment(c);
  assert.equal(env.MODEL_CALLS_ENABLED,'false'); assert.equal(env.COLLECT_ENABLED,'false');
  assert.equal(env.OPENAI_API_KEY,undefined); assert.equal(env.DEV_AUTH_ROLE,undefined);
  assert.equal(new URL(env.DATABASE_URL).password, 'private-rwb-value-'.repeat(3));
  chmodSync(c.tokenFile,0o644); assert.throws(() => secret(c.tokenFile),/secret_file_not_private/);
});
test('bootstrap rejects remote database and missing range', t => {
  const {dir,c}=fixture(t); const file=path.join(dir,'bootstrap.json');
  writeFileSync(file,JSON.stringify(c)); assert.equal(loadConfig(file).port,3099);
  c.database.host='example.com'; writeFileSync(file,JSON.stringify(c));assert.throws(()=>loadConfig(file),/database_config_invalid/);
});
test('original closure verifies and stage retains unknown paid receipts without querying or releasing', async t => {
  const {c}=fixture(t); const origin=verifyOrigin(); assert.equal(origin.files,652);
  const stage=stageEngine(c.dataDir); assert.equal(stageEngine(c.dataDir),stage);
  const text=readFileSync(path.join(stage,'packages/backend/src/operations/recover.ts'),'utf8');
  const start=text.indexOf('export async function autoReleaseUnknownReceipts('), end=text.indexOf('\n/** ops.recover',start);
  const {autoReleaseUnknownReceipts}=await import('data:text/javascript,'+encodeURIComponent(text.slice(start,end)));
  for(const time of [0,Date.now()+31*60000,Date.now()+365*86400000]) assert.deepEqual(await autoReleaseUnknownReceipts(time),{released:0,requeued:0});
  const sources=JSON.parse(readFileSync(path.join(stage,'industry/sources.json'),'utf8')).sources;
  assert.ok(sources.length>=18); assert.ok(sources.every(s=>s.enabled===false));
  writeFileSync(path.join(stage,'industry/selection.ts'),'tampered');
  assert.throws(()=>stageEngine(c.dataDir),/stage_hash_invalid/);
});
test('bridge authentication rejects absent, truncated and incorrect tokens',()=>{
  assert.equal(authenticated('',''),false);assert.equal(authenticated('abc','abc'),true);assert.equal(authenticated('ab','abc'),false);assert.equal(authenticated('abd','abc'),false);
});
test('outbound destination rejects upstream production and subdomains',()=>{
  for(const url of ['https://aihot.news/a','https://AIHOT.NEWS./','https://api.aihot.news/']) assert.throws(()=>assertDestination(url),/forbidden/);
  assert.equal(assertDestination('https://openai.com/news').hostname,'openai.com');
});
test('finite controls preserve source edits, free previews, original visibility semantics and reject paid/unknown actions',()=>{
  const input={id:'rss-example',kind:'rss',config:{feedUrl:'https://openai.com/news/rss.xml'}};
  assert.equal(controlRoute('source.preview',input).payload,input);
  for(const kind of ['x_search','mp_account','external']) assert.throws(()=>assertFreePreview({...input,kind}),/paid_preview_forbidden/);
  assert.throws(()=>assertFreePreview({...input,config:{feedUrl:'https://r.jina.ai/https://openai.com/'}}),/forbidden/);
  assert.throws(()=>controlRoute('model.enable',{}),/not_allowed/);
  assert.throws(()=>controlRoute('source.create',{config:{headers:{Authorization:'secret'}}}),/private_store/);
  assert.throws(()=>controlRoute('source.preview',{kind:'rss',config:{feedUrl:'https://public.invalid/feed?api_key=secret'}}),/private_store/);
  assert.throws(()=>controlRoute('source.create',{config:{url:'https://public.invalid/feed?key=secret'}}),/private_store/);
  assert.throws(()=>controlRoute('source.create',{config:{headers:{'X-Key':'secret'}}}),/private_store/);
  assert.doesNotThrow(()=>controlRoute('source.create',{config:{headers:{Accept:'application/json'},jsonKey:'news'}}));
  assert.throws(()=>controlRoute('content.detail',{id:'../admin'}),/invalid_id/);
  assert.deepEqual(controlRoute('source.update',{id:'a',patch:{enabled:false},version:'v'}),{method:'PATCH',url:'/api/admin/sources/a',payload:{patch:{enabled:false},version:'v'}});
  assert.equal(controlRoute('content.visibility',{id:'a',visibility:'hidden'}).payload.visibility,'hidden');
  assert.throws(()=>controlRoute('receipt.release',{id:1,billed:false,note:''}),/reconciliation_required/);
  assert.equal(controlRoute('receipt.release',{id:1,billed:false,note:'Provider billing independently verified'}).url,'/api/admin/receipts/1/release');
  assert.throws(()=>controlRoute('processing.requeue',{group:null,reason:''}),/reason_required/);
});
test('activation is explicit and requires private credentials, unexpired grant and persisted positive bounded budget', async t=>{
  const {dir,c}=fixture(t), file=path.join(dir,'activation.json');
  const {loadActivation,assertPaidAuthorization}=await import('../activation.mjs');
  assert.equal(loadActivation().modelCallsEnabled,false);
  const now=Date.now(), grant={approvedBy:'test-operator',approvedAt:new Date(now-1000).toISOString(),expiresAt:new Date(now+60000).toISOString(),budget:{perMinute:2,perHour:4,perDay:6},credentialFiles:{LLM_API_KEY:c.tokenFile},publicConfig:{LLM_BASE_URL:'https://provider.invalid/v1',LLM_MODEL:'fake-only'}};
  const record={version:1,collectionEnabled:false,modelCallsEnabled:true,services:{llm:grant}};
  const active={LLM_API_KEY:secret(c.tokenFile),...grant.publicConfig};
  const save=()=>writeFileSync(file,JSON.stringify(record),{mode:0o600});save();
  assert.equal(loadActivation(file,now).environment.LLM_MODEL,'fake-only');
  grant.publicConfig.LLM_BASE_URL='http://127.0.0.1:11434/v1';save();assert.equal(loadActivation(file,now).environment.LLM_BASE_URL,grant.publicConfig.LLM_BASE_URL);
  grant.publicConfig.LLM_BASE_URL='http://provider.invalid/v1';save();assert.throws(()=>loadActivation(file,now),/provider_url_invalid/);
  grant.publicConfig.LLM_BASE_URL='https://provider.invalid/v1';save();
  assert.doesNotThrow(()=>assertPaidAuthorization('llm',{per_minute:1,per_hour:2,per_day:3},file,now,active));
  for(const budget of [undefined,{per_minute:0,per_hour:2,per_day:3},{per_minute:3,per_hour:4,per_day:6}])assert.throws(()=>assertPaidAuthorization('llm',budget,file,now,active),/persisted_budget/);
  assert.throws(()=>assertPaidAuthorization('socialdata',{per_minute:1,per_hour:1,per_day:1},file,now,active),/authorization_required/);
  assert.throws(()=>assertPaidAuthorization('llm',{per_minute:1,per_hour:2,per_day:3},file,now,{...active,LLM_API_KEY:'old-key'}),/changed_restart/);
  record.services.socialdata={...grant,credentialFiles:{SOCIALDATA_API_KEY:c.tokenFile},publicConfig:{SOCIALDATA_BASE_URL:'https://provider.invalid'}};record.collectionEnabled=true;save();
  const collectorActive={SOCIALDATA_API_KEY:secret(c.tokenFile),SOCIALDATA_BASE_URL:'https://provider.invalid'};
  assert.doesNotThrow(()=>assertPaidAuthorization('socialdata',{per_minute:1,per_hour:2,per_day:3},file,now,collectorActive));
  delete record.services.socialdata.publicConfig.SOCIALDATA_BASE_URL;save();
  assert.throws(()=>assertPaidAuthorization('socialdata',{per_minute:1,per_hour:2,per_day:3},file,now,collectorActive),/changed_restart/);
  delete record.services.socialdata;record.collectionEnabled=false;save();
  record.modelCallsEnabled=false;save();assert.throws(()=>assertPaidAuthorization('llm',{per_minute:1,per_hour:1,per_day:1},file,now,active),/authorization_required/);
  record.modelCallsEnabled=true;grant.expiresAt=new Date(now-1).toISOString();save();assert.throws(()=>loadActivation(file,now),/authorization_invalid/);
  record.services={};record.modelCallsEnabled=false;record.collectionEnabled=true;save();assert.equal(loadActivation(file,now).collectionEnabled,true);
});
