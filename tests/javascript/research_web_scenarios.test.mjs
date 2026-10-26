import test from 'node:test';
import assert from 'node:assert/strict';
import { createScenarioController, renderScenarioPanel, scenarioLaunchContext } from '../../app/research_web/ui/scenarios.mjs';
import { renderComposer } from '../../app/research_web/ui/composer.mjs';
import { createController } from '../../app/research_web/ui/core.mjs';
import { discoveryItems, discoveryEmptyState } from '../../app/research_web/ui/discovery.mjs';

const scenario = options => createScenarioController({storage:null,...options});
const row = { id: 'company-onepager', name: '<公司>', description: '', coverage: ['风险'], steps: ['核对'], examples: [{question:'示例'}], expected_artifacts:['draft'], required_inputs:[], capabilities:[{id:'company-research', version:1, available:true}] };
const frozen = { state:'prepared', session_id:'target', mode:'fingpt', draft:'新研究', scenario_context:{source_scope:['datahub'], scenario:{inputs:{as_of:'2026-01-01'}}} };
test('real delegated input, submit and open events freeze once and never send', async () => {
  const calls = [], opened = [];
  const c = scenario({ api:{scenarioCatalog:async()=>({items:[row]}), handoff:async(body,key)=>{calls.push({body,key});return frozen;}}, onOpen:r=>opened.push(r), makeID:()=> 'same-key' });
  await c.open({subject:{kind:'stock',identity:'600600.SH'},as_of:'2026-01-01',question:'原草稿'});
  await c.handle({type:'input',target:{dataset:{scenarioField:'question'},value:'修订问题'}});
  await c.handle({type:'submit',target:{matches:()=>true},submitter:{dataset:{scenarioFreeze:''}},preventDefault(){}});
  await c.prepare();
  assert.equal(calls.length,1); assert.equal(calls[0].body.scenario_inputs.question,'修订问题'); assert.equal(opened.length,0);
  await c.handle({type:'click',target:{closest:()=>({dataset:{scenarioAction:'open'}})},preventDefault(){}});
  assert.equal(opened.length,1);
});
test('unknown create retains exact request key across closing, reopening and lookup', async()=>{
  const calls=[]; const c=scenario({api:{scenarioCatalog:async()=>({items:[row]}),handoff:async(_,key)=>{calls.push(key);throw new Error('lost')},handoffRequest:async key=>{calls.push(key);return {state:'creation_outcome_unknown'}}},logger(){},onOpen(){},makeID:()=> 'one-key'});
  await c.open({subject:{kind:'stock',identity:'600600.SH'},as_of:'2026-01-01',question:'保留'}); await c.prepare(); c.close(); await c.open({question:'不要覆盖'}); await c.prepare(); await c.lookup();
  assert.deepEqual(calls,['one-key','one-key']); assert.equal(c.state.inputs.question,'保留');
});
test('late catalog cannot reopen a closed drawer and source labels are escaped',async()=>{
  let resolve; const c=scenario({api:{scenarioCatalog:()=>new Promise(r=>resolve=r)},onOpen(){}}); const p=c.open();c.close();resolve({items:[row]});await p;assert.equal(c.state.items.length,0);
  c.state.open=true;c.state.items=[row];c.state.selected=row.id;c.state.inputs={subject:{kind:'stock',identity:'<script>'},material_ids:[]};
  assert.ok(renderScenarioPanel(c.state).includes('&lt;script&gt;'));assert.ok(!renderScenarioPanel(c.state).includes('<script>'));
});
test('opening frozen research preserves original draft and attachment identities',async()=>{
  const navigation=[]; const c=createController({api:{detail:async id=>({id,mode:'fingpt',source_scope:['datahub']})},draftStorage:null,onNavigate:x=>navigation.push(x)});
  await c.open({page:'fingpt',sessionId:null});c.setDraft('旧问题');c.addAttachments([{id:'attachment',name:'原附件'}]);
  c.setFormats(['pdf']);
  c.setDossierDraft('旧问题', {handoff_id:'a'.repeat(32),dossier_id:'b'.repeat(32)});
  c.openScenarioHandoff(frozen);await c.open({page:'fingpt',sessionId:'target'});assert.equal(c.state.draft,'新研究');
  assert.deepEqual(c.state.expectedFormats,['pdf']);assert.equal(c.state.dossierHandoff,null);assert.deepEqual(c.state.attachments,[]);assert.deepEqual(c.state.sourceScope,['datahub']);
  await c.open({page:'fingpt',sessionId:null});assert.equal(c.state.draft,'旧问题');assert.equal(c.state.attachments[0].id,'attachment');assert.equal(navigation.length,1);
  assert.equal(c.state.dossierHandoff.id,'a'.repeat(32));
});
test('date/category/importance/watchlist filters operate only within returned bounded set',()=>{
  const themes=[{id:'known',category:'科技',priority:'high',assets:['600600.SH'],published_at:'2026-01-01T00:00:00Z'}, {id:'unknown',category:'科技',priority:'high',assets:['600600.SH'],published_at:null}];
  const s={feed:{themes},query:'',filters:{from:'2026-01-01',to:'2026-01-02',category:'科技',importance:'high',watchlist:'mine'},watchlists:[{id:'mine',items:[{asset:'600600.SH'}]}]};
  assert.deepEqual(discoveryItems(s).map(x=>x.id),['known']);
});

test('refresh restores the same pending receipt and a missing lookup never rotates its key',async()=>{
  const saved=new Map(), calls=[]; const storage={getItem:key=>saved.get(key),setItem:(key,value)=>saved.set(key,value),removeItem:key=>saved.delete(key)};
  const api={scenarioCatalog:async()=>({items:[row]}),handoff:async(_,key)=>{calls.push(key);throw new Error('lost')},handoffRequest:async()=>{const error=new Error('not observed');error.code='handoff_not_found';throw error}};
  const first=scenario({api,storage,logger(){},makeID:()=> 'same-persisted-key'});
  await first.open({subject:{kind:'stock',identity:'600600.SH'},as_of:'2026-01-01',question:'原问题'});await first.prepare();
  const second=scenario({api,storage,logger(){}});await second.open();await second.lookup();await second.prepare();
  assert.equal(second.state.request.key,'same-persisted-key');assert.deepEqual(calls,['same-persisted-key']);
});

test('definitive input rejection preserves editable text without misclassifying an unknown creation',async()=>{
  const c=scenario({api:{scenarioCatalog:async()=>({items:[row]}),handoff:async()=>{const error=new Error('bad identity');error.code='scenario_inputs_invalid';throw error}},logger(){},makeID:()=> 'input-rejected-key'});
  await c.open({subject:{kind:'stock',identity:'invalid'},as_of:'2026-01-01',question:'保留问题'});await c.prepare();
  assert.equal(c.state.request,null);c.edit('identity','600600.SH');assert.equal(c.state.inputs.question,'保留问题');assert.equal(c.state.inputs.subject.identity,'600600.SH');
});


test('automatic format picker uses the frozen scenario capability defaults',()=>{
  const html=renderComposer({page:'fingpt',draft:'',detail:{scenario_context:{scenario:{contract:{name:'公司一页纸'},status:'incomplete',inputs:{subject:{identity:'600600.SH'},as_of:'2026-10-26'},capabilities:[{id:'company-research',default_formats:['docx','html','xlsx']}]},requirements:[]}}});
  assert.ok(html.includes('DOCX'));assert.ok(html.includes('HTML'));assert.ok(html.includes('XLSX'));assert.ok(!html.includes('自动 · 无需文件'));
});

test('independent industry draft clears the stock observation and its materials',async()=>{
  const industry={...row,id:'industry-onepager',subject_kinds:['industry']};
  const c=scenario({api:{scenarioCatalog:async()=>({items:[industry]})}});
  await c.open({observation_id:'stock-observation',session_id:'stock-session',subject:{kind:'stock',identity:'600600.SH'},datasets:[{dataset_id:'stock-material'}],as_of:'2026-01-01',question:'独立行业问题'});
  await c.handle({type:'click',target:{closest:()=>({dataset:{scenarioAction:'independent'}})},preventDefault(){}});
  assert.equal(c.state.context.observation_id,undefined);assert.equal(c.state.context.session_id,undefined);assert.deepEqual(c.state.inputs.material_ids,[]);assert.equal(c.state.inputs.subject.kind,'industry');assert.equal(c.state.inputs.question,'独立行业问题');
});


test('non-asset legacy handoffs remain with the original controller and stale asset routes cannot open',()=>{
  const observation={asset:'600600.SH',asset_type:'stock',session_id:'old-session',blocks:{}};
  assert.equal(scenarioLaunchContext({assetPage:false,route:{page:'assets',section:'funds'},observation},{workbenchHandoff:'fingpt',sourceSession:'fund-session',datasetIds:'["nav"]'}),null);
  assert.ok(scenarioLaunchContext({assetPage:true,route:{page:'assets',asset:'601318.SH',assetType:'stock'},observation},{}).error);
  assert.equal(scenarioLaunchContext({assetPage:true,route:{page:'assets',asset:'600600.SH',assetType:'stock'},observation},{}).context.session_id,'old-session');
});
test('Enter in scenario search and implicit submit cannot create a handoff',async()=>{
  let created=0;const c=scenario({api:{scenarioCatalog:async()=>({items:[row]}),handoff:async()=>{created++;return frozen}}});
  await c.open({subject:{kind:'stock',identity:'600600.SH'},as_of:'2026-01-01',question:'已填问题'});
  let prevented=0;assert.equal(c.key({key:'Enter',target:{dataset:{scenarioField:'query'},tagName:'INPUT'},preventDefault(){prevented++}}),true);
  await c.handle({type:'submit',target:{matches:()=>true},preventDefault(){}});
  assert.equal(prevented,1);assert.equal(created,0);
});
test('source-empty, date-filter-empty and unknown self-watch association stay distinct',()=>{
  assert.equal(discoveryEmptyState({feed:{themes:[]},filters:{from:'2026-01-01'}}).code,'source_empty');
  const feed={themes:[{id:'one',assets:[]}]};
  assert.equal(discoveryEmptyState({feed,filters:{from:'2026-01-01'}}).code,'filtered_empty');
  assert.equal(discoveryEmptyState({feed,filters:{watchlist:'mine'}}).code,'association_unknown');
});
