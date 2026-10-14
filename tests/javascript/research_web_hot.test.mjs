import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createAPI,parseRoute} from '../../app/research_web/ui/core.mjs';
import {createHotController,renderHotWorkspace,renderHotBrief,renderHotResults,hotURL,hotTime} from '../../app/research_web/ui/hot-workspace.mjs';
import {hotResearchSubmission,renderHotPreparation,renderHotExecution} from '../../app/research_web/ui/hot-research-actions.mjs';

const researchRun='11111111-1111-4111-8111-111111111111', researchMaterial='22222222-2222-4222-8222-222222222222';
const researchBrief={briefId:'33333333-3333-4333-8333-333333333333',version:2,payload:{events:[{reports:[{materialId:researchMaterial,title:'<script>publisher</script>',revision:3}]}]}};
test('research preparation admits only selected frozen materials and never calls execution',async()=>{
  const original=globalThis.FormData;const calls=[];
  globalThis.FormData=class{get(){return 'claw';}getAll(){return [researchMaterial];}};
  try{
    const c=createHotController({uuid:()=>researchRun,api:{hotResearchPrepare:async body=>{calls.push(body);return {...body,state:'snapshot_ready',executionStarted:false};},hotResearchExecute:async()=>assert.fail('automatic execution')}});
    c.state.brief=researchBrief;
    await c.submit({dataset:{hotForm:'research-prepare'}});
    assert.equal(c.state.pending,null);assert.equal(c.state.researchDraft.state,'snapshot_ready');assert.equal(calls[0].version,2);assert.deepEqual(calls[0].materialIds,[researchMaterial]);
    assert.match(renderHotPreparation(researchBrief),/&lt;script&gt;/);assert.ok(!renderHotPreparation(researchBrief).includes('<script>'));
  }finally{globalThis.FormData=original;}
});
test('research selection rejects foreign, duplicate, empty materials and invalid mode',()=>{
  for(const [ids,mode] of [[[], 'claw'],[[researchRun],'claw'],[[researchMaterial,researchMaterial],'claw'],[[researchMaterial],'other']]){
    assert.throws(()=>hotResearchSubmission('research-prepare',{get:()=>mode,getAll:()=>ids},{brief:researchBrief},{},()=>researchRun));
  }
});
test('unknown execution retains exact question and run; explicit retry does not create a new run',async()=>{
  const original=globalThis.FormData;let question='研究当前固定资料',count=0;const bodies=[];
  globalThis.FormData=class{get(){return question;}};
  try{
    const c=createHotController({api:{hotResearchExecute:async body=>{bodies.push(JSON.stringify(body));return {runId:body.runId,state:++count===1?'execution_outcome_unknown':'running',executionStarted:count===1?null:true};}}});
    c.state.researchDraft={runId:researchRun,state:'snapshot_ready'};
    await c.submit({dataset:{hotForm:'research-execute',hotRun:researchRun}});
    assert.ok(c.state.pending);question='changed';await c.submit({dataset:{hotForm:'research-execute',hotRun:researchRun}});assert.equal(bodies.length,1);
    await c.action({dataset:{hotAction:'retry'}});assert.equal(bodies[0],bodies[1]);assert.equal(c.state.pending,null);
  }finally{globalThis.FormData=original;}
});
test('execute requires a verified prepared run; reads and unverified rows expose no paid action',()=>{
  const row={runId:researchRun,runState:'snapshot_ready',stateVerified:false,artifacts:[]};
  assert.ok(!renderHotResults([row]).includes('data-hot-form="research-execute"'));
  assert.ok(renderHotResults([{...row,stateVerified:true}]).includes('data-hot-form="research-execute"'));
  assert.throws(()=>hotResearchSubmission('research-execute',{get:()=> 'question'},{researchRows:[{runId:researchRun,runState:'snapshot_ready',stateVerified:false}]},{dataset:{hotRun:researchRun}}));
  assert.equal(renderHotExecution('bad'), '');assert.match(renderHotExecution(researchRun,'disabled'),/disabled/);
});
test('research API writes carry explicit action and execution does not leak client run into body',async()=>{
  const calls=[];const api=createAPI({logger:()=>{},fetcher:async(url,options)=>{calls.push({url,options});return {ok:true,status:200,json:async()=>({})};}});
  await api.hotResearchPrepare({runId:researchRun});await api.hotResearchExecute({runId:researchRun,question:'q',formats:['md']});
  assert.equal(calls[0].options.headers['X-Research-User-Action'],'?1');assert.equal(calls[1].options.headers['X-Research-User-Action'],'?1');assert.match(calls[1].url,/research-runs\//);assert.deepEqual(JSON.parse(calls[1].options.body),{question:'q',formats:['md']});
});
test('incomplete execution response keeps original request and cannot certify acceptance',async()=>{
  const original=globalThis.FormData;
  globalThis.FormData=class{get(){return 'question';}};
  try{
    for(const response of [{runId:researchRun},{runId:researchRun,state:'running'},{runId:researchRun,state:'invented',executionStarted:true}]){
      const c=createHotController({api:{hotResearchExecute:async()=>response}});c.state.researchDraft={runId:researchRun,state:'snapshot_ready'};
      await c.submit({dataset:{hotForm:'research-execute',hotRun:researchRun}});assert.ok(c.state.pending);assert.match(c.state.message,/不确定/);
    }
  }finally{globalThis.FormData=original;}
});
test('late research success or failure does not overwrite next view messages',async()=>{
  const original=globalThis.FormData;globalThis.FormData=class{get(){return 'question';}};
  try{
    for(const fail of [false,true]){
      let finish;
      const c=createHotController({api:{hotResearchExecute:async()=>new Promise((resolve,reject)=>{finish=()=>fail?reject(Error('old error')):resolve({runId:researchRun,state:'running',executionStarted:true});})}});
      c.state.researchDraft={runId:researchRun,state:'snapshot_ready'};
      const promise=c.submit({dataset:{hotForm:'research-execute',hotRun:researchRun}});c.deactivate();c.state.message='new message';c.state.error='new error';finish();await promise;
      assert.equal(c.state.message,'new message');assert.equal(c.state.error,'new error');assert.equal(Boolean(c.state.pending),fail);
    }
  }finally{globalThis.FormData=original;}
});

test('Hot routes preserve existing app routes and explicit action API boundaries',async()=>{
  assert.equal(parseRoute('#/workbench/hot?view=sources').hotView,'sources');
  assert.equal(parseRoute('#/workbench/hot?view=briefs').hotView,'briefs');
  assert.equal(parseRoute('#/settings/hot').settingsSection,'hot');
  const calls=[];
  const api=createAPI({logger:()=>{},fetcher:async(url,options)=>{calls.push({url,options});return {ok:true,status:200,json:async()=>({items:[]})};}});
  await api.hotEvents({channelId:'gold',q:'100%'});
  await api.hotCorrect({requestId:'opaque',reason:'review',change:{}});
  assert.match(calls[0].url,/q=100%25/);assert.equal(calls[0].options.method,'GET');
  assert.equal(calls[1].options.headers['X-Research-User-Action'],'?1');
});
test('brief creation freezes detail cutoff and unknown replay keeps the same brief and request UUID',async()=>{
  const original=globalThis.FormData,bodies=[];let count=0,n=0;
  globalThis.FormData=class {get(){return 'macro';}};
  try{
    const c=createHotController({uuid:()=>`id-${++n}`,api:{hotBriefCreate:async body=>{bodies.push(JSON.stringify(body));return ++count===1?{state:'outcome_unknown',requestId:body.requestId}:{briefId:body.briefId,version:1,requestId:body.requestId};},hotBrief:async()=>({payload:null})}});
    c.state.detail={canonicalId:'event',revision:1,cutoff:'2026-10-08T00:00:00Z'};
    c.state.cutoff='2026-10-09T00:00:00Z';c.state.filters.from='2026-01-01T00:00:00Z';
    await c.submit({dataset:{hotForm:'brief'}});assert.ok(c.state.pending);
    assert.equal(c.state.pending.body.cutoff,'2026-10-08T00:00:00Z');assert.equal(c.state.pending.body.from,'2026-01-01T00:00:00Z');
    await c.action({dataset:{hotAction:'retry'}});assert.equal(c.state.pending,null);assert.equal(bodies[0],bodies[1]);assert.equal(n,2);
  }finally{globalThis.FormData=original;}
});
test('late brief selection cannot replace a newer selection and readonly brief has no correction checkboxes',async()=>{
  let first;
  const c=createHotController({api:{hotBrief:async id=>id==='first'?new Promise(resolve=>{first=resolve;}):{briefId:id}}});
  const pending=c.action({dataset:{hotAction:'open-brief',brief:'first',version:'1'}});
  await c.action({dataset:{hotAction:'open-brief',brief:'second',version:'1'}});first({briefId:'first'});await pending;
  assert.equal(c.state.brief.briefId,'second');
  const html=renderHotBrief({briefId:'id',version:2,contentHash:'a'.repeat(64),payload:{timezone:'Asia/Shanghai',cutoff:null,channel:{channel_id:'macro',version:1},window:{from:null,to:null},limitations:[],events:[{title:'<script>bad</script>',canonicalId:'event',revision:1,judgments:[],reports:[{title:'source',excerpt:'<img src=x>',url:'javascript:bad',materialId:'material',revision:1,sources:[]}]}]}});
  assert.ok(!html.includes('<script>bad'));assert.ok(!html.includes('<img'));assert.ok(!html.includes('javascript:'));assert.ok(!html.includes('data-hot-material'));
  assert.ok(html.includes('markdown?version=2'));assert.ok(html.includes('来源摘录（发布者陈述）'));
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

test('saved research route reads offline and preserves failure beside verified report',async()=>{
  const {renderHotResults}=await import('../../app/research_web/ui/hot-workspace.mjs');
  const sid='ffe77d48-b717-4946-854c-a9ea5810468e', fid='e563eea6489e8b7cf916b731';
  assert.equal(parseRoute('#/intel/hot?view=research').hotView,'research');
  const row={runId:'run',sessionId:sid,targetMode:'fingpt',title:'<script>bad</script>',runState:'failed',deliveryState:'completed',stateVerified:true,errorCode:'hot_model_budget_exhausted',artifacts:[{id:fid,name:'report.md',url:`/api/research/sessions/${sid}/files/${fid}/download`,verified:true}]};
  const html=renderHotResults([row]);assert.match(html,/运行失败/);assert.match(html,/报告已生成并校验/);assert.ok(!html.includes('<script>'));
  assert.ok(html.includes('download'));assert.ok(!renderHotResults([{...row,artifacts:[{...row.artifacts[0],url:'javascript:alert(1)'}]}]).includes('javascript:'));
  const calls=[];
  const c=createHotController({api:{hotResearchResults:async()=>{calls.push('read');return {items:[row],hasMore:false};}}});
  await c.activate({page:'intel',hotView:'research'});assert.deepEqual(calls,['read']);assert.equal(c.state.researchRows[0].runState,'failed');
});

test('late research page and observation failures cannot overwrite another view',async()=>{
  for(const action of ['more-research','refresh-run']){
    let reject;
    const c=createHotController({api:{hotResearchResults:async()=>new Promise((_,r)=>{reject=r;}),hotResearchRefresh:async()=>new Promise((_,r)=>{reject=r;})}});
    c.state.researchHasMore=true;
    const pending=c.action({dataset:{hotAction:action,run:'old'}});
    c.deactivate();c.state.error='new-view-error';reject(Error('old-request-error'));await pending;
    assert.equal(c.state.error,'new-view-error');
  }
});

test('failed current status observation remains visible even when list GET would succeed',async()=>{
  let reads=0;
  const c=createHotController({api:{hotResearchRefresh:async()=>{throw Error('observation failed');},hotResearchResults:async()=>{reads++;return {items:[],hasMore:false};}}});
  await c.action({dataset:{hotAction:'refresh-run',run:'run'}});
  assert.equal(c.state.error,'observation failed');assert.equal(reads,0);assert.equal(c.state.busy,false);
});
