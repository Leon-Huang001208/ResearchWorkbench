import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, mkdir, realpath, writeFile, chmod, symlink, link, unlink } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { randomUUID } from 'node:crypto';
import { pathToFileURL } from 'node:url';

const moduleURL = new URL('../../app/research_web/runtime/public-data.mjs', import.meta.url);
const reply = data => new Response(JSON.stringify(data), { headers: { 'content-type': 'application/json' } });
const BUSINESS_TOOL_IDS = [
  'datahub_search_assets',
  'datahub_get_trading_calendar',
  'datahub_get_market_bars',
  'datahub_get_market_snapshot',
  'datahub_get_index_data',
  'datahub_get_financials',
  'datahub_get_market_activity',
  'datahub_get_factor_macro',
  'datahub_get_fund_data',
  'datahub_search_news',
  'datahub_search_announcements',
  'datahub_search_research',
  'datahub_search_web',
];
const dataset = {dataset_id:randomUUID(),source:'fund_nav',status:'complete',row_count:243,
  retrieved_at:'2026-09-02T00:00:00Z',as_of:'2025-12-31',pagination_complete:true,
  requested_range:{start_date:'2025-01-01',end_date:'2025-12-31'},actual_range:{start_date:'2025-01-02',end_date:'2025-12-31'},
  files:[{name:'rows.json',path:'inputs/datasets/id/rows.json',sha256:'a'.repeat(64)}],sample:[{date:'2025-12-31',unit_nav:1.2}],limitations:[],missing:[],cache_hit:false};

async function fixture(options = {}) {
  const root = await realpath(await mkdtemp(join(tmpdir(), 'rwb-datahub-bridge-')));
  const sid = randomUUID(); const cwd = join(root,'sessions',sid);
  await mkdir(cwd,{recursive:true}); await mkdir(join(root,'.control'),{mode:0o700});
  const control = join(root,'.control','datahub.json');
  await writeFile(control,JSON.stringify({url:'http://127.0.0.1:18088',token:'t'.repeat(43)}),{mode:0o600});
  const tools=new Map(); let approvalReads=0; let approvalRequests=0;
  const ctx={tools:{register(value){tools.set(value.name,value);}},sessions:{get(){}},get(){approvalReads++;return {async request(){approvalRequests++;return 'allowed-once';}};},logger:{info(){},warn(){},error(){}}};
  const {apply}=await import(moduleURL);
  const config=options.omitEnabledTools ? {researchRoot:root} : {researchRoot:root,enabledTools:options.enabledTools ?? BUSINESS_TOOL_IDS};
  apply(ctx,config);
  const exec={agent:{session:{header:{id:sid,cwd}}},signal:new AbortController().signal,callId:'call-1'};
  return {root,sid,cwd,control,tool:tools.get('datahub_get_fund_data'),tools,ctx,exec,
    approvalReads(){return approvalReads;},approvalRequests(){return approvalRequests;}};
}

test('only the thirteen brand-neutral business tools are registered',async()=>{
  const f=await fixture();
  assert.equal(f.tools.size,13);
  assert.ok(f.tools.has('datahub_get_market_bars'));
  assert.ok(!f.tools.has('research_public_data'));
  assert.ok(f.tools.has('datahub_search_news'));
  assert.ok(f.tools.has('datahub_get_fund_data'));
});

test('enabledTools registers only fixed business tools and invalid configuration fails closed',async()=>{
  const f=await fixture({enabledTools:['datahub_search_news','datahub_get_fund_data']});
  assert.deepEqual([...f.tools.keys()],['datahub_get_fund_data','datahub_search_news']);
  for(const invalid of [
    {omitEnabledTools:true},
    {enabledTools:'datahub_get_fund_data'},
    {enabledTools:['datahub_get_fund_data','datahub_get_fund_data']},
    {enabledTools:['datahub_not_registered']},
    {enabledTools:['toString']},
  ]) await assert.rejects(fixture(invalid),/enabledTools/);
  const empty=await fixture({enabledTools:[]});
  assert.equal(empty.tools.size,0);
});

test('automatic business query uses the stable DataHub contract without reading approval or exposing credentials',async()=>{
  const f=await fixture();const requests=[];const original=globalThis.fetch;
  globalThis.fetch=async(url,options)=>{requests.push({url,options});return reply({...dataset,provider:'eastmoney_fund',capability:'fund_data',attempted_sources:[{source:'eastmoney_fund',status:'selected',reason:null}]});};
  try{
    const result=await f.tools.get('datahub_get_fund_data').execute({dataset:'nav',code:'000001',start_date:'2025-01-01',end_date:'2025-12-31'},f.exec);
    assert.ok(requests[0].url.endsWith('/api/research/internal/data/business-query'));
    const body=JSON.parse(requests[0].options.body);
    assert.deepEqual(body.query,{capability:'fund_data',source:'auto',allow_fallback:false,parameters:{dataset:'nav',code:'000001',start_date:'2025-01-01',end_date:'2025-12-31'},refresh:false});
    assert.equal(JSON.parse(result.manifest_json).provider,'eastmoney_fund');
    assert.ok(!JSON.stringify(result).includes('t'.repeat(43)));
    assert.equal(f.approvalReads(),0);
    assert.equal(f.approvalRequests(),0);
  } finally {globalThis.fetch=original;}
});

test('business query ignores inherited schema and common properties',async()=>{
  const f=await fixture();const requests=[];const original=globalThis.fetch;let inheritedReads=0;
  const inherited={
    get source(){inheritedReads++;return 'prototype_source';},
    get allow_fallback(){inheritedReads++;return true;},
    get refresh(){inheritedReads++;return true;},
    get year(){inheritedReads++;return 2025;},
  };
  const args=Object.assign(Object.create(inherited),{dataset:'nav',code:'000001'});
  globalThis.fetch=async(url,options)=>{requests.push({url,options});return reply(dataset);};
  try{
    await f.tool.execute(args,f.exec);
    assert.equal(inheritedReads,0);
    assert.deepEqual(JSON.parse(requests[0].options.body).query,{capability:'fund_data',source:'auto',allow_fallback:false,parameters:{dataset:'nav',code:'000001'},refresh:false});
  }finally{globalThis.fetch=original;}
});

test('invalid schema arguments send zero HTTP',async()=>{
  const f=await fixture();let calls=0;const original=globalThis.fetch;globalThis.fetch=async()=>{calls++;return reply(dataset);};
  try{
    const valid={dataset:'nav',code:'000001'};
    const invalid=[
      null,
      {dataset:'nav'},
      {dataset:'nav',code:undefined},
      {...valid,unexpected:'value'},
      {dataset:'nav',code:1},
      {dataset:'holdings',code:'000001',year:'2025'},
      {dataset:'unknown',code:'000001'},
      {...valid,source:1},
      {...valid,allow_fallback:'false'},
      {...valid,refresh:'false'},
    ];
    const arrayTool=[...f.tools.values()].find(tool=>Object.values(tool.parameters.properties).some(schema=>schema.type==='array'));
    assert.ok(arrayTool,'fixed business registry must retain a string-array schema');
    const arrayProperty=Object.entries(arrayTool.parameters.properties).find(([,schema])=>schema.type==='array')[0];
    const required=Object.fromEntries((arrayTool.parameters.required ?? []).map(key=>{
      const schema=arrayTool.parameters.properties[key];
      if(schema.enum)return [key,schema.enum[0]];
      if(schema.type==='integer')return [key,2025];
      if(schema.type==='array')return [key,['value']];
      return [key,'value'];
    }));
    invalid.push({tool:arrayTool,args:{...required,[arrayProperty]:['value',2]}});
    invalid.push({tool:f.tools.get('datahub_get_market_snapshot'),args:{assets:new Array(1)}});
    for(const entry of invalid){
      const {tool=f.tool,args=entry}=entry && entry.tool ? entry : {args:entry};
      await assert.rejects(tool.execute(args,f.exec));
    }
    assert.equal(calls,0);
  }finally{globalThis.fetch=original;}
});

test('cancellation unsafe parameters and untrusted ancestry send zero HTTP',async()=>{
  const f=await fixture();let calls=0;const original=globalThis.fetch;globalThis.fetch=async()=>{calls++;return reply(dataset);};
  try{
    const valid={dataset:'nav',code:'000001'};
    for(const args of [{...valid,url:'https://evil.test'},{...valid,session_id:f.sid},{...valid,source:'evil/url'}])await assert.rejects(f.tool.execute(args,f.exec));
    const controller=new AbortController();controller.abort();await assert.rejects(f.tool.execute(valid,{...f.exec,signal:controller.signal}));
    await assert.rejects(f.tool.execute(valid,{...f.exec,agent:{session:{header:{id:'child',cwd:f.cwd,parentSession:'missing'}}}}));
    assert.equal(calls,0);
  }finally{globalThis.fetch=original;}
});

test('private control rejects weak permissions hardlinks symlinks and remote origin',async()=>{
  const f=await fixture();let calls=0;const original=globalThis.fetch;globalThis.fetch=async()=>{calls++;return reply(dataset);};
  try{
    const valid={dataset:'nav',code:'000001'};
    await chmod(f.control,0o644);await assert.rejects(f.tool.execute(valid,f.exec));
    await chmod(f.control,0o600);await link(f.control,join(f.root,'hardlink'));await assert.rejects(f.tool.execute(valid,f.exec));
    await unlink(join(f.root,'hardlink'));await unlink(f.control);await symlink(join(f.root,'absent'),f.control);await assert.rejects(f.tool.execute(valid,f.exec));
    await unlink(f.control);await writeFile(f.control,JSON.stringify({url:'https://evil.test',token:'t'.repeat(43)}),{mode:0o600});await assert.rejects(f.tool.execute(valid,f.exec));
    assert.equal(calls,0);
  }finally{globalThis.fetch=original;}
});

test('native abort sends authenticated cancellation using the stable call identity',async()=>{
  const f=await fixture();const requests=[];const original=globalThis.fetch;const controller=new AbortController();
  let started;const ready=new Promise(resolve=>{started=resolve;});
  globalThis.fetch=async(url,options)=>{requests.push({url,options});if(url.endsWith('/cancel'))return reply({cancelled:true});started();return await new Promise((resolve,reject)=>options.signal.addEventListener('abort',()=>reject(Error('aborted')),{once:true}));};
  try{
    const pending=f.tool.execute({dataset:'nav',code:'000001'},{...f.exec,signal:controller.signal});await ready;controller.abort();await assert.rejects(pending);
    assert.equal(requests.length,2);assert.ok(requests[1].url.endsWith('/cancel'));
    assert.equal(JSON.parse(requests[1].options.body).call_id,JSON.parse(requests[0].options.body).call_id);
    assert.equal(requests[1].options.headers['X-Research-Data-Key'],'t'.repeat(43));
  }finally{globalThis.fetch=original;}
});

test('bridge rejects upstream-shaped data failed HTTP and oversized BFF responses',async()=>{
  const f=await fixture();const original=globalThis.fetch;
  try{for(const response of [reply({ErrCode:0,Data:{}}),new Response('no',{status:403}),reply({status:'cancelled'}),new Response('x'.repeat(1048577),{headers:{'content-type':'application/json'}})]){globalThis.fetch=async()=>response;await assert.rejects(f.tool.execute({dataset:'nav',code:'000001'},f.exec));}}
  finally{globalThis.fetch=original;}
});

test('business tool schemas conform to pinned DSH',{skip:!process.env.DSH_SOURCE_ROOT},async()=>{
  const {assertSupportedJsonSchema,validateJsonSchemaValue}=await import(pathToFileURL(join(process.env.DSH_SOURCE_ROOT,'packages/core/tools/lib/index.js')));
  const f=await fixture();assertSupportedJsonSchema(f.tool.parameters);assertSupportedJsonSchema(f.tool.output.schema);
  assert.deepEqual(validateJsonSchemaValue(f.tool.parameters,{dataset:'nav',code:'000001',start_date:'2025-01-01',end_date:'2025-12-31'}),[]);
  assert.deepEqual(validateJsonSchemaValue(f.tool.parameters,{dataset:'holdings',code:'000001',year:2025}),[]);
});
