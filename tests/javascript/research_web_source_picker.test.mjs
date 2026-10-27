import test from 'node:test';
import assert from 'node:assert/strict';
import { createScenarioController, renderScenarioPanel } from '../../app/research_web/ui/scenarios.mjs';
import { createAPI } from '../../app/research_web/ui/core.mjs';

const row = {id:'pack-research-prep',pack_id:'research-prep',name:'调研前置',description:'',coverage:[],steps:[],examples:[{question:'核验'}],expected_artifacts:[],required_inputs:[],subject_kinds:['stock','industry','topic'],capabilities:[],ui_methods:[{id:'deduplicate_source_versions',label:'来源去重',version:'1.1.0',fields:[]}]};
const source = sid => ({source_session_id:sid,id:'same-id',sha256:'a'.repeat(64),title:'synthetic <正文不是标题>',source_host:'fixture.example',acquired_at:null,publication_date:'2026-10-27',capture_status:'host_verified',selectable:true,state:'available'});
const context = {session_id:'first',material_sessions:[{id:'first'},{id:'second'}],subject:{kind:'topic',identity:'制造业'},as_of:'2026-10-28',question:'保留问题',datasets:[{dataset_id:'dataset'}]};
function fixture(overrides={}) {
  const calls=[];
  const api={scenarioCatalog:async()=>({items:[row]}),detail:async id=>({id,source_scope:['datahub','uploads','web']}),sourceSelectionList:async sid=>({items:[source(sid)]}),sourceSelectionPreview:async body=>{calls.push(['preview',body]);return {preview_sha256:'b'.repeat(64),qualification:{status:'partial',executable_methods:['deduplicate_source_versions'],missing:[]},sources:body.sources};},sourceSelectionFreeze:async(body,key)=>{calls.push(['freeze',body,key]);return {state:'creation_outcome_unknown'};},handoffRequest:async key=>{calls.push(['lookup',key]);return {state:'creation_outcome_unknown'};},...overrides};
  const c=createScenarioController({api,storage:null,logger(){},makeID:()=> 'original-source-key'});return {c,calls};
}
test('source picker keeps composite identities, explicit modes and original question/dataset inputs',async()=>{
  const {c,calls}=fixture();await c.open(context);c.edit('cutoff_at','2026-10-28T23:59:59+08:00');
  c.edit('material_mode','sources');await c.selectSourceSession('first');c.edit('source_ids',['first:same-id']);
  await c.selectSourceSession('second');c.edit('source_ids',['first:same-id','second:same-id']);
  assert.equal(c.state.inputs.question,'保留问题');assert.deepEqual(c.state.inputs.material_ids,['dataset']);
  await c.preview();assert.equal(calls.length,1);assert.equal(calls[0][1].sources.length,2);
  assert.deepEqual(calls[0][1].handoff.dataset_ids,[]);assert.deepEqual(calls[0][1].handoff.scenario_inputs.material_ids,[]);
  assert.match(renderScenarioPanel(c.state),/日级发表/);assert.match(renderScenarioPanel(c.state),/取得时刻未知/);
  assert.match(renderScenarioPanel(c.state),/上游完整性未知/);assert.match(renderScenarioPanel(c.state),/1.1.0/);
  c.edit('material_mode','datasets');assert.equal(c.state.preview,null);assert.deepEqual(c.state.inputs.material_ids,['dataset']);
});
test('source freeze binds preview and key, unknown never recreates and changes invalidate',async()=>{
  const {c,calls}=fixture();await c.open(context);c.edit('cutoff_at','2026-10-28T23:59:59+08:00');c.edit('material_mode','sources');await c.selectSourceSession('first');c.edit('source_ids',['first:same-id']);
  await c.preview();await c.prepare();await c.prepare();await c.lookup();
  assert.equal(calls.filter(x=>x[0]==='freeze').length,1);assert.equal(calls[1][1].preview_sha256,'b'.repeat(64));assert.equal(calls[1][2],'original-source-key');assert.equal(c.state.request.key,'original-source-key');
  assert.doesNotMatch(renderScenarioPanel(c.state),/已冻结/);
});
test('source list permissions, missing and empty are distinct; cached selection and inputs survive',async()=>{
  let fail=false;
  const {c}=fixture({sourceSelectionList:async sid=>{if(fail)throw Object.assign(Error('private path'),{status:410});return {items:[source(sid)]};}});
  await c.open(context);c.edit('material_mode','sources');await c.selectSourceSession('first');c.edit('source_ids',['first:same-id']);fail=true;await c.selectSourceSession('first');
  assert.deepEqual(c.state.source_ids,['first:same-id']);assert.equal(c.state.inputs.question,'保留问题');assert.match(c.state.sourceError,/永久清理/);assert.doesNotMatch(renderScenarioPanel(c.state),/private path/);
});
test('source-freeze API consumes only explicit before-create proof and preserves exact key/body otherwise',async()=>{
  for (const proof of [undefined,'not_created']) {
    const calls=[];
    const api=createAPI({logger(){},fetcher:async(url,options)=>{
      calls.push({url,options});return {ok:false,status:409,json:async()=>({error:{code:'source_selection_preview_changed',handoff_outcome:proof}})};
    }});
    const body={handoff:{scenario_id:row.id},sources:[source('first')],preview_sha256:'b'.repeat(64)};
    await assert.rejects(api.sourceSelectionFreeze(body,'exact-original-key'),error=>error.status===409 && error.handoffOutcome===proof);
    assert.ok(calls[0].url.endsWith('/source-selections/freeze'));assert.equal(calls[0].options.headers['Idempotency-Key'],'exact-original-key');assert.deepEqual(JSON.parse(calls[0].options.body),body);
    const {c}=fixture({sourceSelectionFreeze:async()=>{throw Object.assign(Error('private'),{status:409,handoffOutcome:proof});}});
    c.state.context={...context};await c.open(context);c.edit('cutoff_at','2026-10-28T23:59:59+08:00');c.edit('material_mode','sources');await c.selectSourceSession('first');c.edit('source_ids',['first:same-id']);await c.preview();await c.prepare();
    assert.equal(c.state.inputs.question,'保留问题');assert.deepEqual(c.state.source_ids,['first:same-id']);assert.equal(!!c.state.request,!proof);assert.doesNotMatch(c.state.error,/private/);
    if(proof){assert.equal(c.state.preview,null);c.edit('question','重新预览前修订');await c.prepare();assert.equal(c.state.request,null);}
  }
});
test('source preview never silently opens missing scope and rejects stale response across account/edits',async()=>{
  const {c,calls}=fixture({detail:async id=>({id,source_scope:['web']})});await c.open(context);c.edit('material_mode','sources');await c.selectSourceSession('first');c.edit('source_ids',['first:same-id']);c.edit('cutoff_at','2026-10-28T23:59:59+08:00');await c.preview();
  assert.equal(calls.length,0);assert.match(c.state.error,/不会自动开启/);
  let resolve;
  const f=fixture({sourceSelectionPreview:()=>new Promise(r=>resolve=r)});
  await f.c.open(context);f.c.edit('material_mode','sources');await f.c.selectSourceSession('first');f.c.edit('source_ids',['first:same-id']);f.c.edit('cutoff_at','2026-10-28T23:59:59+08:00');const pending=f.c.preview();f.c.edit('question','迟到前编辑');resolve({qualification:{status:'partial',executable_methods:['x']}});await pending;assert.equal(f.c.state.preview,null);
});
test('removed selected source remains visible as unavailable and may be explicitly deselected',async()=>{
  let items=[source('first')];const {c}=fixture({sourceSelectionList:async()=>({items})});
  await c.open(context);c.edit('material_mode','sources');await c.selectSourceSession('first');c.edit('source_ids',['first:same-id']);items=[];await c.selectSourceSession('first');
  assert.deepEqual(c.state.source_ids,['first:same-id']);assert.equal(c.state.sourceItems[0].selectable,false);
  const html=renderScenarioPanel(c.state);assert.match(html,/source_missing/);assert.doesNotMatch(html,/value="first:same-id" checked disabled/);
  c.edit('source_ids',[]);assert.deepEqual(c.state.source_ids,[]);
});
