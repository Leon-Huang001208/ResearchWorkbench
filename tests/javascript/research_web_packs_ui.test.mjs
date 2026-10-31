import test from 'node:test';
import assert from 'node:assert/strict';
import { createScenarioController, renderScenarioPanel } from '../../app/research_web/ui/scenarios.mjs';
import { packResults, packInputEdit, packQualification } from '../../app/research_web/ui/pack-ui.mjs';

const row = {id:'pack-event-review',pack_id:'event-review',name:'事件复盘',description:'',coverage:[],steps:[],examples:[{question:'核验'}],expected_artifacts:[],required_inputs:[],subject_kinds:['stock'],capabilities:[{id:'research-pack-event-review',version:1,available:true}],ui_methods:[{id:'align_event_trading_day',label:'交易日对齐',fields:[{name:'pre_sessions',label:'前置交易日',type:'integer',min:0,max:5000}]}]};
const context = {session_id:'source',subject:{kind:'stock',identity:'600600.SH'},as_of:'2026-10-27',question:'核验',datasets:[{dataset_id:'owned'}]};
test('pack preview is read-only, explicit timezone required and every edit invalidates qualification',async()=>{
  const calls=[];
  const c=createScenarioController({storage:null,logger(){},api:{scenarioCatalog:async()=>({items:[row]}),scenarioPrepare:async(id,body)=>{calls.push(body);return {pack_qualification:{status:'blocked',missing:[{code:'required_kind_missing',kind:'exchange-session'}],executable_methods:[]},references:[]};},handoff:async()=>{throw Error('must not create');}}});
  await c.open(context);
  await c.preview();assert.equal(calls.length,0);
  c.edit('cutoff_at','2026-10-27T15:00:00+08:00');
  c.edit('method:align_event_trading_day:pre_sessions','3');
  await c.preview();assert.equal(calls.length,1);
  assert.equal(calls[0].scenario_inputs.research_scope.methods.align_event_trading_day.pre_sessions,3);
  assert.equal(c.state.preview.pack_qualification.status,'blocked');
  assert.match(renderScenarioPanel(c.state),/exchange-session/);
  await c.prepare();assert.equal(c.state.request,null);
  c.edit('question','保留后重验');assert.equal(c.state.preview,null);assert.equal(c.state.inputs.question,'保留后重验');
});
test('late previews cannot restore edited qualification or reopen closed state',async()=>{
  let resolve;
  const c=createScenarioController({storage:null,logger(){},api:{scenarioCatalog:async()=>({items:[row]}),scenarioPrepare:()=>new Promise(r=>resolve=r)}});
  await c.open(context);c.edit('cutoff_at','2026-10-27T15:00:00+08:00');const pending=c.preview();c.edit('as_of','2026-10-26');resolve({pack_qualification:{status:'partial',executable_methods:['x']}});await pending;assert.equal(c.state.preview,null);assert.equal(c.state.previewing,false);
});
test('pack form has typed fields and no authority or arbitrary records editor',async()=>{
  const c=createScenarioController({storage:null,api:{scenarioCatalog:async()=>({items:[row]})}});await c.open(context);
  const html=renderScenarioPanel(c.state);assert.match(html,/前置交易日/);assert.match(html,/type="number"/);assert.match(html,/只读资格预览/);assert.doesNotMatch(html,/scenario-field="(?:records|provider|source_coverage|owner|rights|passed)"/);
});

test('pack preparation retains unknown request id and server-proof corrections require new preview',async()=>{
  for (const proof of [undefined,'not_created']) {
    let creates=0;
    const c=createScenarioController({storage:null,logger(){},makeID:()=> 'pack-original-key',api:{scenarioCatalog:async()=>({items:[row]}),scenarioPrepare:async()=>({pack_qualification:{status:'partial',executable_methods:['align_event_trading_day']}}),handoff:async()=>{creates++;throw Object.assign(Error('private body must stay hidden'),{status:409,handoffOutcome:proof});},handoffRequest:async()=>{throw Object.assign(Error('missing'),{status:404});}}});
    await c.open(context);c.edit('cutoff_at','2026-10-27T15:00:00+08:00');await c.preview();await c.prepare();assert.doesNotMatch(c.state.error,/private body/);await c.lookup();await c.prepare();assert.equal(creates,1);
    if(proof){assert.equal(c.state.request,null);assert.equal(c.state.preview,null);}else assert.equal(c.state.request.key,'pack-original-key');
  }
});
test('timezone mismatch and IME confirmation do not create or preview',async()=>{
  let calls=0;
  const c=createScenarioController({storage:null,api:{scenarioCatalog:async()=>({items:[row]}),scenarioPrepare:async()=>{calls++;}}});await c.open(context);
  c.edit('cutoff_at','2026-10-27T23:00:00Z');await c.preview();assert.equal(calls,0);assert.match(c.state.error,/北京时间/);
  assert.equal(c.key({key:'Enter',isComposing:true,target:{tagName:'INPUT'},preventDefault(){throw Error('IME interrupted');}}),false);
});
test('explicit securities accept scope fields only and raw authority is never consumed',()=>{
  const inputs={};const row={pack_id:'position-risk',ui_methods:[{id:'validate_positions',fields:[{name:'expected_universe',type:'securities'}]}]};
  assert.equal(packInputEdit(inputs,row,'method:validate_positions:expected_universe:0:security_id','600600.SH'),true);
  assert.equal(packInputEdit(inputs,row,'method:validate_positions:expected_universe:0:rights','qualified'),false);
  assert.deepEqual(inputs.research_scope.methods.validate_positions.expected_universe,[{security_id:'600600.SH'}]);
});
test('result view separates verified files, partial calculation and formal quality',()=>{
  const file={id:'a'.repeat(24),url:'/api/research/sessions/s1/files/'+ 'a'.repeat(24)+'/download',name:'full-result.json',sha256:'b'.repeat(64),bytes:100};
  const detail={id:'s1',status:'completed',research_quality:{status:'incomplete'},files:[file],research_pack:{qualification_status:'partial',executions:[{state:'saved',computation_status:'partial',counts:{root:1},files:[file]}]}};
  const html=packResults(detail);assert.match(html,/incomplete/);assert.match(html,/Host 已重新核验完整文件/);assert.ok(html.includes(file.url));
  assert.doesNotMatch(packResults({...detail,files:[]}),/href="\/api\//);
  assert.doesNotMatch(packResults({...detail,research_pack:{executions:[{state:'unknown',files:[file]}]}}),/href="\/api\//);
});
test('provenance view exposes audit hashes and times without private control paths or raw body',()=>{
  const html=packQualification({references:[{sha256:'hash',retrieved_at:'2026-10-27T10:00:00+08:00',body:'private-body',path:'.control/private'}],scenario:{capabilities:[{id:'pack',version:1,resource_path:'.control/private'}]},pack_qualification:{status:'partial',missing:[],transformations:[{mapping:'approved',raw_files:[{path:'.control/private'}]}]}});
  assert.match(html,/2026-10-27T10:00:00/);assert.match(html,/approved/);assert.doesNotMatch(html,/private-body|\.control\/private/);
});
test('explicit owned source session reads existing materials only and rejects late unowned choices',async()=>{
  let resolve,reads=0;
  const c=createScenarioController({storage:null,api:{scenarioCatalog:async()=>({items:[row]}),detail:async()=>{reads++;return new Promise(r=>resolve=r);}}});
  await c.open({...context,material_sessions:[{id:'owned-source',title:'本人原件'}]});
  await c.selectMaterialSession('foreign');assert.equal(reads,0);
  const pending=c.selectMaterialSession('owned-source');c.edit('question','读取期间保留修订');assert.equal(c.state.materialLoading,true);
  resolve({id:'owned-source',datasets:[{dataset_id:'material'}],source_scope:['datahub']});await pending;
  assert.equal(c.state.materialLoading,false);assert.equal(c.state.inputs.question,'读取期间保留修订');assert.deepEqual(c.state.inputs.material_ids,[]);assert.equal(c.state.datasets[0].dataset_id,'material');
  const late=c.selectMaterialSession('owned-source');await c.selectMaterialSession('');resolve({id:'owned-source',datasets:[{dataset_id:'late'}]});await late;
  assert.deepEqual(c.state.datasets,[]);assert.equal(reads,2);
});
test('account switch refuses delayed preview and further pack actions',async()=>{
  let owner='one',resolve,calls=0;
  const c=createScenarioController({storage:null,account:()=>owner,api:{scenarioCatalog:async()=>({items:[row]}),scenarioPrepare:()=>{calls++;return new Promise(r=>resolve=r);}}});
  await c.open(context);c.edit('cutoff_at','2026-10-27T15:00:00+08:00');const pending=c.preview();owner='two';resolve({pack_qualification:{status:'partial',executable_methods:['method']}});await pending;
  assert.equal(c.state.preview,null);await c.preview();await c.prepare();assert.equal(calls,1);assert.equal(c.state.request,null);
});
