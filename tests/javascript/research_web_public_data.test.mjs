import test from 'node:test';
import assert from 'node:assert/strict';
import { existsSync } from 'node:fs';
import { mkdtemp, mkdir, realpath } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { randomUUID } from 'node:crypto';
import { pathToFileURL } from 'node:url';

const moduleURL = new URL('../../app/research_web/runtime/public-data.mjs', import.meta.url);
const nav = { ErrCode: 0, Data: { FundType: '002', LSJZList: [
  { FSRQ: '2026-09-01', DWJZ: '1.299', LJJZ: '3.872', JZZZL: '-2.40' },
  { FSRQ: '2026-08-31', DWJZ: '1.331', LJJZ: '', JZZZL: '--' },
] } };
const reply = data => new Response(JSON.stringify(data), { headers: { 'content-type': 'application/json' } });

test('registered public data is bounded, typed and preserves missing values', async () => {
  assert.ok(existsSync(moduleURL), 'controlled public-data implementation missing');
  const { fetchPublicData } = await import(moduleURL);
  let request;
  const result = await fetchPublicData({ source: 'fund_nav', code: '000001', limit: 20 }, new AbortController().signal, async (url, options) => { request = { url, options }; return reply(nav); });
  assert.equal(new URL(request.url).hostname, 'api.fund.eastmoney.com');
  assert.equal(request.options.redirect, 'error');
  const rows = JSON.parse(result.rows_json);
  assert.equal(rows[0].date, '2026-08-31');
  assert.equal(rows[0].cumulative_nav, null);
  assert.equal(rows[0].daily_change_pct, null);
  assert.equal(result.as_of, '2026-09-01');
  assert.match(result.limitations, /未复权/);
});

test('public-data rejects arbitrary endpoints, bad schemas and provider failures', async () => {
  const { fetchPublicData } = await import(moduleURL);
  let calls = 0;
  const transport = async () => { calls++; return reply(nav); };
  for (const args of [{ source:'other' }, { source:'fund_nav', code:'../bad' }, { source:'fund_nav', code:'000001', url:'https://evil.test' }, { source:'cls_telegraph', limit:101 }]) {
    await assert.rejects(fetchPublicData(args, new AbortController().signal, transport));
  }
  assert.equal(calls, 0);
  for (const response of [new Response('no', {status:403}), new Response('html'), reply({ErrCode:1}), reply({ErrCode:0,Data:{LSJZList:[]}}), reply({ErrCode:0,Data:{LSJZList:[{FSRQ:'2026-09-01',DWJZ:'bad'}]}})]) {
    await assert.rejects(fetchPublicData({source:'fund_nav',code:'000001'},new AbortController().signal,async()=>response));
  }
  await assert.rejects(fetchPublicData({source:'fund_nav',code:'000001'},new AbortController().signal,async()=>new Response('x'.repeat(1048577), {headers:{'content-type':'application/json'}})), /size/);
});

test('CLS keeps provider timestamps and source links using the registered cache endpoint', async () => {
  const { fetchPublicData } = await import(moduleURL);
  const result = await fetchPublicData({source:'cls_telegraph',limit:2},new AbortController().signal,async url=> {
    assert.equal(new URL(url).pathname, '/api/cache');
    assert.equal(new URL(url).searchParams.get('name'), 'telegraphList');
    return reply({errno:0,data:{roll_data:[{id:123,ctime:1788326831,content:'<em>news</em>',brief:'news'}]}});
  });
  const row=JSON.parse(result.rows_json)[0];
  assert.equal(row.source_url, 'https://www.cls.cn/detail/123');
  assert.equal(row.content,'news');
  assert.match(row.published_at,/Z$/);
});

test('provider whitespace remains missing and malformed numeric/text fields fail explicitly', async () => {
  const {fetchPublicData}=await import(moduleURL);
  const request={source:'fund_nav',code:'000001'};const signal=new AbortController().signal;
  const sample=value=>({ErrCode:0,Data:{LSJZList:[{FSRQ:'2026-09-01',DWJZ:'1.2',LJJZ:value,JZZZL:'\t'}]}});
  const result=await fetchPublicData(request,signal,async()=>reply(sample(' ')));
  const row=JSON.parse(result.rows_json)[0];assert.equal(row.cumulative_nav,null);assert.equal(row.daily_change_pct,null);
  for(const value of ['0x10','Infinity',{},true]) await assert.rejects(fetchPublicData(request,signal,async()=>reply(sample(value))));
  for(const content of [{text:'news'},['news']]) await assert.rejects(fetchPublicData({source:'cls_telegraph'},signal,async()=>reply({errno:0,data:{roll_data:[{id:1,ctime:1788326831,content}]}})));
});

test('native approval denies and cancels before any HTTP request; granted execution remains session-bound', async () => {
  const { apply }=await import(moduleURL);
  const root=await realpath(await mkdtemp(join(tmpdir(),'af-public-data-')));
  const sid=randomUUID();const cwd=join(root,'sessions',sid); await mkdir(cwd,{recursive:true});
  let tool;let grants='rejected';let requested=0;
  const ctx={tools:{register(t){tool=t;}},sessions:{get(){}},get(name){assert.equal(name,'approval');return {async request(req){assert.equal(req.toolName,'af_public_data');return grants;}};},logger:{info(){},warn(){},error(){}}};
  const original=globalThis.fetch;
  globalThis.fetch=async()=>{requested++;return reply(nav);};
  try {
    apply(ctx,{researchRoot:root});
    const exec={agent:{session:{header:{id:sid,cwd}}},signal:new AbortController().signal,callId:'approval-test'};
    for(const outcome of ['rejected','cancelled','unavailable']) {grants=outcome; await assert.rejects(tool.execute({source:'fund_nav',code:'000001'},exec), /HTTP not sent/);}
    assert.equal(requested,0);
    grants='allowed-once'; assert.equal((await tool.execute({source:'fund_nav',code:'000001'},exec)).source,'fund_nav'); assert.equal(requested,1);
    const controller=new AbortController();controller.abort(); await assert.rejects(tool.execute({source:'fund_nav',code:'000001'},{...exec,signal:controller.signal}));
    assert.equal(requested,1);
  } finally {globalThis.fetch=original;}
});

test('public tool schemas conform to the pinned native DSH converter', {skip:!process.env.DSH_SOURCE_ROOT}, async () => {
  const {apply}=await import(moduleURL);
  const {assertSupportedJsonSchema,validateJsonSchemaValue}=await import(pathToFileURL(join(process.env.DSH_SOURCE_ROOT,'packages/core/tools/lib/index.js')));
  let tool;apply({tools:{register(t){tool=t;}}},{researchRoot:'/nonexistent-review-only'});
  assertSupportedJsonSchema(tool.parameters);assertSupportedJsonSchema(tool.output.schema);
  assert.deepEqual(validateJsonSchemaValue(tool.parameters,{source:'fund_nav',code:'000001',limit:30}),[]);
});
