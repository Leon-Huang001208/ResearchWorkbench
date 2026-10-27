import assert from 'node:assert/strict';
import test from 'node:test';
import { createAssetResearchController, renderAssetResearch } from '../../app/research_web/ui/asset-research.mjs';
import { scenarioLaunchContext } from '../../app/research_web/ui/scenarios.mjs';

const obs=(id,asset,dataset)=>({id,asset,asset_type:'stock',session_id:`session-${id}`,request_parameters:{end_date:'2026-10-26'},blocks:{financials:{status:'complete',dataset:{dataset_id:dataset,manifest_sha256:`hash-${dataset}`}}}});
const route={page:'assets',asset:'600600',assetType:'stock',assetView:'financials'};
const canonical={...route,asset:'600600.SH'};
function harness(){let calls=0;const payloads=[],known=new Map();let account='alice';const c=createAssetResearchController({account:()=>account,logger(){},api:{assetResearchCatalog:async()=>({materials:[],observations:[]}),assetResearchPreview:async body=>{calls++;payloads.push(body);return {asset:known.get(body.observation_id).asset,observation_id:body.observation_id,material:body.material,required_source_scope:['datahub'],comparisons:[body.observation_id,...body.comparison_observation_ids].map(id=>({observation_id:id,asset:known.get(id).asset,datasets:[known.get(id).blocks.financials.dataset],records:[]})),summaries:[],relations:[]}}}});return {c,known,payloads,count:()=>calls,account:value=>account=value};}

test('unique six-digit aliases open canonical context; different and ambiguous aliases do not',()=>{
  const one=obs('one','600600.SH','d1'),sameCode=obs('other','600600.SZ','d2');
  const result=scenarioLaunchContext({assetPage:true,route,observation:one,observations:[one]},{});
  assert.equal(result.context.subject.identity,'600600.SH');
  assert.equal(result.context.session_id,'session-one');
  assert.ok(scenarioLaunchContext({assetPage:true,route:{...route,asset:'601318.SH'},observation:one,observations:[one]},{}).error);
  assert.ok(scenarioLaunchContext({assetPage:true,route,observation:one,observations:[one,sameCode]},{}).error);
});

test('current and selected-peer version changes refresh without discarding user choices',async()=>{
  const h=harness(),one=obs('one','600600.SH','d1'),peer=obs('peer','601318.SH','p1');h.known.set(one.id,one);h.known.set(peer.id,peer);
  await h.c.activate(one,canonical,[one,peer]);assert.equal(h.count(),1);
  h.c.state.question='保留我的问题';h.c.state.comparisons=['peer'];h.c.state.scope=['datahub','uploads'];
  await h.c.activate(one,canonical,[one,peer]);
  const before=h.count(),next=obs('one','600600.SH','d2');h.known.set(next.id,next);
  await h.c.activate(next,canonical,[next,peer]);assert.equal(h.count(),before+1);
  assert.equal(h.c.state.preview.comparisons[0].datasets[0].dataset_id,'d2');
  const nextPeer=obs('peer','601318.SH','p2');h.known.set(nextPeer.id,nextPeer);
  await h.c.activate(next,canonical,[next,nextPeer]);assert.equal(h.count(),before+2);
  assert.equal(h.c.state.preview.comparisons[1].datasets[0].dataset_id,'p2');
  assert.equal(h.c.state.question,'保留我的问题');assert.deepEqual(h.c.state.comparisons,['peer']);assert.deepEqual(h.c.state.scope,['datahub','uploads']);
  await h.c.activate(next,canonical,[next,nextPeer]);assert.equal(h.count(),before+2);
});

test('changed version clears stale preview immediately and late response cannot overwrite it',async()=>{
  const pending=[];const one=obs('one','600600.SH','d1');
  const c=createAssetResearchController({logger(){},api:{assetResearchCatalog:async()=>({materials:[],observations:[]}),assetResearchPreview:body=>new Promise(resolve=>pending.push({body,resolve}))}});
  const first=c.activate(one,canonical,[one]);await new Promise(resolve=>setImmediate(resolve));
  const two=obs('one','600600.SH','d2'),second=c.activate(two,canonical,[two]);await new Promise(resolve=>setImmediate(resolve));
  assert.equal(pending.length,2);assert.equal(c.state.preview,null);
  pending[1].resolve({observation_id:'one',asset:'600600.SH',material:null,version:'d2'});await second;
  pending[0].resolve({observation_id:'one',asset:'600600.SH',material:null,version:'d1'});await first;
  assert.equal(c.state.preview.version,'d2');
});


test('owner or subject changes cannot reuse the old evidence and source consent',async()=>{
  const h=harness(),one=obs('one','600600.SH','d1'),two=obs('two','601318.SH','d2');h.known.set(one.id,one);h.known.set(two.id,two);
  await h.c.activate(one,route,[one,two]);assert.equal(h.count(),1);
  h.c.state.question='旧主体问题';h.c.state.scope=['datahub','uploads'];h.c.state.comparisons=['two'];
  await h.c.activate(two,{...canonical,asset:'601318.SH'},[one,two]);
  assert.equal(h.c.state.preview.asset,'601318.SH');assert.deepEqual(h.c.state.scope,['datahub']);assert.deepEqual(h.c.state.comparisons,[]);
  h.account('bob');await h.c.activate(one,route,[one,two]);assert.equal(h.c.state.active,false);assert.equal(h.c.state.preview,null);assert.equal(h.count(),2);
});
test('summary text stays unassessed while each source report grade is separately shown',()=>{
  const proof=status=>({url:'/owned/evidence',title:'来源报告',reference:{id:'outputs/research-report.json'},source:'research_output',sha256:'a'.repeat(64),locator:{kind:'text',start:0,end:2,quote:'原文'},source_quality:status,source_contract:'b'.repeat(64),source_report_sha256:'a'.repeat(64)});
  const html=renderAssetResearch({active:true,observation:obs('one','600600.SH','d1'),catalog:{observations:[],materials:[]},comparisons:[],scope:['datahub'],asOf:'2026-10-26',question:'问题',tab:'summaries',preview:{summaries:[{title:'任意新摘要',text:'没有出处的新增断言',quality:'passed',evidence:[proof('passed'),proof('incomplete')]}],relations:[],comparisons:[],required_source_scope:['datahub']}});
  assert.ok(html.includes('本条摘要未独立评估'));assert.ok(html.includes('来源报告：当前报告质量通过'));assert.ok(html.includes('来源报告：当前报告证据不完整'));
  assert.ok(!html.includes('分析观点／引用摘录 · 当前报告质量通过'));
});
