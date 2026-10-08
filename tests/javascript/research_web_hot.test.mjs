import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createAPI,parseRoute} from '../../app/research_web/ui/core.mjs';
import {createHotController,renderHotWorkspace,hotURL,hotTime} from '../../app/research_web/ui/hot-workspace.mjs';

test('Hot routes preserve existing app routes and explicit action API boundaries',async()=>{
  assert.equal(parseRoute('#/workbench/hot?view=sources').hotView,'sources');
  assert.equal(parseRoute('#/settings/hot').settingsSection,'hot');
  const calls=[];
  const api=createAPI({logger:()=>{},fetcher:async(url,options)=>{calls.push({url,options});return {ok:true,status:200,json:async()=>({items:[]})};}});
  await api.hotEvents({channelId:'gold',q:'100%'});
  await api.hotCorrect({requestId:'opaque',reason:'review',change:{}});
  assert.match(calls[0].url,/q=100%25/);assert.equal(calls[0].options.method,'GET');
  assert.equal(calls[1].options.headers['X-Research-User-Action'],'?1');
});

test('rendering escapes news, permits safe external links and preserves unknown time',()=>{
  const controller=createHotController({api:{}}),s=controller.state;
  s.events=[{id:'event',title:'<script>publisher()</script>',materialCount:1,judgment:null}];
  const html=renderHotWorkspace(s);
  assert.ok(!html.includes('<script>publisher()'));assert.match(html,/&lt;script&gt;/);
  assert.equal(hotURL('javascript:alert(1)'), '');assert.equal(hotURL('https://secret@example.com/'), '');
  assert.equal(hotTime(null),'未知');
});

test('unknown source mutation retries exactly the same parameters and UUID',async()=>{
  const bodies=[];let attempts=0;
  const api={hotSourceConfigure:async body=>{bodies.push(JSON.stringify(body));attempts++;return attempts===1?{state:'outcome_unknown',requestId:body.requestId}:{requestId:body.requestId,enabled:false};}};
  const c=createHotController({api,uuid:()=> '11111111-1111-4111-8111-111111111111'});
  c.state.sources=[{id:'fed',config_revision:'1',enabled:true}];
  await c.action({dataset:{hotAction:'source-toggle',source:'fed'}});
  assert.ok(c.state.pending);await c.action({dataset:{hotAction:'retry'}});
  assert.equal(c.state.pending,null);assert.equal(bodies[0],bodies[1]);
});

test('late event detail cannot overwrite a later selection or navigation',async()=>{
  let resolveFirst;
  const c=createHotController({api:{hotEvent:async id=>id==='first'?new Promise(resolve=>{resolveFirst=resolve;}):{canonicalId:'second'}}});
  const first=c.action({dataset:{hotAction:'detail',event:'first'}});
  await c.action({dataset:{hotAction:'detail',event:'second'}});
  resolveFirst({canonicalId:'first'});await first;assert.equal(c.state.detail.canonicalId,'second');
});

test('material selection survives page changes and detail pages retain their own cutoff',async()=>{
  const calls=[];
  const api={hotEvent:async(id,params)=>{calls.push(params);return {requestedId:id,canonicalId:id,revision:1,cutoff:'2026-10-08T00:00:00Z',reportOffset:params.reportOffset,reports:[{materialId:params.reportOffset?'second':'first'}],materialCount:2};}};
  const c=createHotController({api});c.state.cutoff='2026-10-08T00:00:00Z';
  await c.action({dataset:{hotAction:'detail',event:'event'}});c.selectMaterial('first',true);
  c.state.cutoff='2026-10-08T01:00:00Z';
  await c.action({dataset:{hotAction:'more-reports'}});c.selectMaterial('second',true);
  assert.equal(calls[1].cutoff,'2026-10-08T00:00:00Z');assert.deepEqual(c.state.selectedMaterialIds,['first','second']);
  c.state.loading=true;await c.action({dataset:{hotAction:'detail',event:'another'}});assert.equal(calls.length,2);
});
