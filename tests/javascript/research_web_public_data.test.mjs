import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, mkdir, realpath, writeFile, chmod, symlink, link, unlink } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { randomUUID } from 'node:crypto';
import { pathToFileURL } from 'node:url';

const moduleURL = new URL('../../app/research_web/runtime/public-data.mjs', import.meta.url);
const reply = data => new Response(JSON.stringify(data), { headers: { 'content-type': 'application/json' } });
const dataset = {dataset_id:randomUUID(),source:'fund_nav',status:'complete',row_count:243,
  retrieved_at:'2026-09-02T00:00:00Z',as_of:'2025-12-31',pagination_complete:true,
  requested_range:{start_date:'2025-01-01',end_date:'2025-12-31'},actual_range:{start_date:'2025-01-02',end_date:'2025-12-31'},
  files:[{name:'rows.json',path:'inputs/datasets/id/rows.json',sha256:'a'.repeat(64)}],sample:[{date:'2025-12-31',unit_nav:1.2}],limitations:[],missing:[],cache_hit:false};

async function fixture() {
  const root = await realpath(await mkdtemp(join(tmpdir(), 'af-datahub-bridge-')));
  const sid = randomUUID(); const cwd = join(root,'sessions',sid);
  await mkdir(cwd,{recursive:true}); await mkdir(join(root,'.control'),{mode:0o700});
  const control = join(root,'.control','datahub.json');
  await writeFile(control,JSON.stringify({url:'http://127.0.0.1:18088',token:'t'.repeat(43)}),{mode:0o600});
  let tool; let outcome='allowed-once';
  const ctx={tools:{register(value){tool=value;}},sessions:{get(){}},get(){return {async request(){return outcome;}};},logger:{info(){},warn(){},error(){}}};
  const {apply}=await import(moduleURL); apply(ctx,{researchRoot:root});
  const exec={agent:{session:{header:{id:sid,cwd}}},signal:new AbortController().signal,callId:'call-1'};
  return {root,sid,cwd,control,tool,ctx,exec,setOutcome(value){outcome=value;}};
}

test('approved native query uses authenticated loopback DataHub and small manifest',async()=>{
  const f=await fixture();const requests=[];const original=globalThis.fetch;
  globalThis.fetch=async(url,options)=>{requests.push({url,options});return reply(dataset);};
  try{
    const result=await f.tool.execute({source:'fund_nav',code:'000001',start_date:'2025-01-01',end_date:'2025-12-31'},f.exec);
    assert.equal(requests.length,1);assert.equal(requests[0].url,'http://127.0.0.1:18088/api/research/internal/data/query');
    assert.equal(requests[0].options.redirect,'error');assert.equal(requests[0].options.headers['X-Research-Data-Key'],'t'.repeat(43));
    const body=JSON.parse(requests[0].options.body);assert.equal(body.session_id,f.sid);assert.equal(body.call_id,`${f.sid}:call-1`);
    assert.equal(result.dataset_id,dataset.dataset_id);assert.equal(result.rows_json,undefined);
    assert.equal(JSON.parse(result.manifest_json).row_count,243);assert.equal(JSON.parse(result.sample_json).length,1);
    assert.ok(!JSON.stringify(result).includes('t'.repeat(43)));
  }finally{globalThis.fetch=original;}
});

test('denial cancellation unsafe parameters and untrusted ancestry send zero HTTP',async()=>{
  const f=await fixture();let calls=0;const original=globalThis.fetch;globalThis.fetch=async()=>{calls++;return reply(dataset);};
  try{
    for(const outcome of ['rejected','cancelled','unavailable']){f.setOutcome(outcome);await assert.rejects(f.tool.execute({source:'fund_nav',code:'000001'},f.exec),/HTTP not sent/);}
    f.setOutcome('allowed-once');
    for(const args of [{source:'other'},{source:'fund_nav',code:'000001',url:'https://evil.test'},{source:'fund_nav',code:'000001',session_id:f.sid},{source:'cls_telegraph',limit:101},{source:'fund_nav',code:'000001',start_date:'2025-01-01'},{source:'fund_nav',code:'000001',start_date:'2025-01-01',end_date:'2099-01-01'}])await assert.rejects(f.tool.execute(args,f.exec));
    const controller=new AbortController();controller.abort();await assert.rejects(f.tool.execute({source:'fund_nav',code:'000001'},{...f.exec,signal:controller.signal}));
    await assert.rejects(f.tool.execute({source:'fund_nav',code:'000001'},{...f.exec,agent:{session:{header:{id:'child',cwd:f.cwd,parentSession:'missing'}}}}));
    assert.equal(calls,0);
  }finally{globalThis.fetch=original;}
});

test('private control rejects weak permissions hardlinks symlinks and remote origin',async()=>{
  const f=await fixture();let calls=0;const original=globalThis.fetch;globalThis.fetch=async()=>{calls++;return reply(dataset);};
  try{
    await chmod(f.control,0o644);await assert.rejects(f.tool.execute({source:'fund_nav',code:'000001'},f.exec));
    await chmod(f.control,0o600);await link(f.control,join(f.root,'hardlink'));await assert.rejects(f.tool.execute({source:'fund_nav',code:'000001'},f.exec));
    await unlink(join(f.root,'hardlink'));await unlink(f.control);await symlink(join(f.root,'absent'),f.control);await assert.rejects(f.tool.execute({source:'fund_nav',code:'000001'},f.exec));
    await unlink(f.control);await writeFile(f.control,JSON.stringify({url:'https://evil.test',token:'t'.repeat(43)}),{mode:0o600});await assert.rejects(f.tool.execute({source:'fund_nav',code:'000001'},f.exec));
    assert.equal(calls,0);
  }finally{globalThis.fetch=original;}
});

test('native abort sends authenticated cancellation using the stable call identity',async()=>{
  const f=await fixture();const requests=[];const original=globalThis.fetch;const controller=new AbortController();
  let started;const ready=new Promise(resolve=>{started=resolve;});
  globalThis.fetch=async(url,options)=>{requests.push({url,options});if(url.endsWith('/cancel'))return reply({cancelled:true});started();return await new Promise((resolve,reject)=>options.signal.addEventListener('abort',()=>reject(Error('aborted')),{once:true}));};
  try{
    const pending=f.tool.execute({source:'fund_nav',code:'000001'},{...f.exec,signal:controller.signal});await ready;controller.abort();await assert.rejects(pending);
    assert.equal(requests.length,2);assert.ok(requests[1].url.endsWith('/cancel'));
    assert.equal(JSON.parse(requests[1].options.body).call_id,JSON.parse(requests[0].options.body).call_id);
    assert.equal(requests[1].options.headers['X-Research-Data-Key'],'t'.repeat(43));
  }finally{globalThis.fetch=original;}
});

test('bridge rejects upstream-shaped data failed HTTP and oversized BFF responses',async()=>{
  const f=await fixture();const original=globalThis.fetch;
  try{for(const response of [reply({ErrCode:0,Data:{}}),new Response('no',{status:403}),reply({status:'cancelled'}),new Response('x'.repeat(1048577),{headers:{'content-type':'application/json'}})]){globalThis.fetch=async()=>response;await assert.rejects(f.tool.execute({source:'fund_nav',code:'000001'},f.exec));}}
  finally{globalThis.fetch=original;}
});

test('public tool schemas conform to pinned DSH with dates and holdings year',{skip:!process.env.DSH_SOURCE_ROOT},async()=>{
  const {assertSupportedJsonSchema,validateJsonSchemaValue}=await import(pathToFileURL(join(process.env.DSH_SOURCE_ROOT,'packages/core/tools/lib/index.js')));
  const f=await fixture();assertSupportedJsonSchema(f.tool.parameters);assertSupportedJsonSchema(f.tool.output.schema);
  assert.deepEqual(validateJsonSchemaValue(f.tool.parameters,{source:'fund_nav',code:'000001',start_date:'2025-01-01',end_date:'2025-12-31'}),[]);
  assert.deepEqual(validateJsonSchemaValue(f.tool.parameters,{source:'fund_holdings',code:'000001',year:2025}),[]);
});
