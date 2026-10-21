import test from 'node:test';
import assert from 'node:assert/strict';
import { renderClawSchedules, renderClawRunCards, clawCases, renderAutomationDrafts, automationDraftBody, renderClawConnections } from '../../app/research_web/ui/claw-workspace.mjs';
import { createAPI } from '../../app/research_web/ui/core.mjs';
import { renderSidebar, renderPrimaryRail, renderTopbar } from '../../app/research_web/ui/shell.mjs';
import { renderConversation } from '../../app/research_web/ui/views.mjs';
import { renderComposer } from '../../app/research_web/ui/composer.mjs';

test('homepage explicit unsent drafts persist synchronously across reload and remain mode isolated',async()=>{
  const { createController }=await import('../../app/research_web/ui/core.mjs');
  const data=new Map();const storage={getItem:key=>data.get(key) || null,setItem:(key,value)=>data.set(key,value)};
  const api={detail:async id=>({id,mode:'claw',messages:[]})};
  const first=createController({api,draftStorage:storage});await first.open({page:'fingpt',sessionId:null});first.setDraft('FinGPT 未发送草稿');await first.open({page:'claw',sessionId:null});first.setDraft('草稿保留验收：尚未发送');first.setTools(['不应跨刷新恢复的权限']);
  assert.match(data.get('research-web:explicit-draft:v1:new:claw') || '',/草稿保留验收/);
  const reload=createController({api,draftStorage:storage});await reload.open({page:'claw',sessionId:null});assert.equal(reload.state.draft,'草稿保留验收：尚未发送');assert.deepEqual(reload.state.toolIds,[]);
  await reload.open({page:'fingpt',sessionId:null});assert.equal(reload.state.draft,'FinGPT 未发送草稿');
  const direct=createController({api,draftStorage:storage});await direct.open({page:'fingpt',sessionId:null});assert.equal(direct.state.draft,'FinGPT 未发送草稿');
});

test('run and draft cards anchor only exact native result IDs and immutable task identity',async()=>{
  const { positionClawAutomationCards }=await import('../../app/research_web/ui/claw-workspace.mjs');
  const detail={mode:'claw',messages:[{seq:1,role:'user',text:'试跑一'},{seq:5,role:'user',text:'试跑二'},{seq:9,role:'assistant',text:'准备变更'}],activities:[{id:'c1',type:'tool',tool:'rwb_run_automation',seq:3,status:'completed',arguments:{automation_id:'a'},result:{id:'r1'}},{id:'c2',type:'tool',tool:'rwb_run_automation',seq:7,status:'completed',arguments:{automation_id:'a'},result:{id:'r2'}},{id:'c3',type:'tool',tool:'rwb_prepare_automation_update',seq:10,status:'completed',arguments:{automation_id:'a'},result:{id:'d'}}],automation_runs:[{id:'r1',automation_id:'a',result_text:'第一版报告'},{id:'r2',automation_id:'a',result_text:'第二版报告'}],automation_drafts:[{id:'d',status:'proposed',operation:'update',automation_id:'a',body:{expected_version:2,research_task:{description:'修改内容'}}}]};
  const positioned=positionClawAutomationCards(detail);
  assert.deepEqual(positioned.entries.map(entry=>entry.seq),[10,3,7]);assert.deepEqual(positioned.unpositionedRuns,[]);assert.deepEqual(positioned.unpositionedDrafts,[]);
  const html=renderConversation(detail,new Map(),positioned.entries);
  assert.ok(html.indexOf('试跑一')<html.indexOf('第一版报告'));assert.ok(html.indexOf('第一版报告')<html.indexOf('试跑二'));assert.ok(html.indexOf('试跑二')<html.indexOf('第二版报告'));assert.ok(html.indexOf('准备变更')<html.indexOf('确认更新同一任务'));
  assert.equal((html.match(/data-claw-draft-form="d"/g)||[]).length,1);assert.equal((html.match(/第一版报告/g)||[]).length,1);
  assert.doesNotMatch(renderConversation({...detail,mode:'fingpt'},new Map(),positioned.entries),/第一版报告|确认更新同一任务/);
  for (const result of ['{"id":"r1"',null,{id:'other'}]) {
    const unknown=positionClawAutomationCards({...detail,activities:[{...detail.activities[0],result}],automation_drafts:[],automation_runs:[detail.automation_runs[0]]});
    assert.equal(unknown.entries.length,0);assert.equal(unknown.unpositionedRuns.length,1);
  }
  const wrongTask=positionClawAutomationCards({...detail,activities:[{...detail.activities[0],arguments:{automation_id:'wrong'}}],automation_drafts:[],automation_runs:[detail.automation_runs[0]]});assert.equal(wrongTask.entries.length,0);
  for (const activities of [[{...detail.activities[0],seq:undefined}],[detail.activities[0],{...detail.activities[0],id:'replayed',seq:4}],[{...detail.activities[0],status:'failed'}]]) {
    const ambiguous=positionClawAutomationCards({...detail,activities,automation_drafts:[],automation_runs:[detail.automation_runs[0]]});assert.equal(ambiguous.entries.length,0);assert.equal(ambiguous.unpositionedRuns.length,1);
  }
});
test('conversation failures stay compact while their real status remains visible',()=>{
  const html=renderConversation({mode:'claw',messages:[],activities:[{id:'x',seq:1,type:'tool',status:'failed',title:'research_run_script',arguments:{script:'很长脚本'},result:'很长返回',error:'实际错误'}]});
  assert.match(html,/失败/);assert.match(html,/实际错误/);assert.doesNotMatch(html,/<details open>/);
});

test('accepted first message clears only its unchanged pre-create homepage draft',async()=>{
  const { createController }=await import('../../app/research_web/ui/core.mjs');
  let release;const hold=new Promise(resolve=>{release=resolve;});let accepted=true;
  const data=new Map();const storage={getItem:key=>data.get(key) || null,setItem:(key,value)=>data.set(key,value)};
  const api={create:async()=>({id:'created',mode:'claw'}),detail:async id=>({id,mode:'claw',messages:[]}),message:async()=>{await hold;return {accepted};}};
  const control=createController({api,draftStorage:storage,logger(){}});
  await control.open({page:'claw',sessionId:null});control.setDraft('首次问题');await control.create('claw');await control.open({page:'claw',sessionId:'created'});
  const pending=control.send();await control.open({page:'claw',sessionId:null});assert.equal(control.state.draft,'首次问题');release();await pending;
  assert.equal(control.state.draft,'');await control.open({page:'claw',sessionId:'created'});assert.equal(control.state.draft,'');
  await control.open({page:'claw',sessionId:null});assert.equal(control.state.draft,'');
  const reloaded=createController({api,draftStorage:storage});await reloaded.open({page:'claw',sessionId:null});assert.equal(reloaded.state.draft,'');
});
test('late first-message acceptance preserves a newer homepage draft and rejected sends keep original',async()=>{
  const { createController }=await import('../../app/research_web/ui/core.mjs');
  let release;let hold=new Promise(resolve=>{release=resolve;});let accepted=true;let sequence=0;
  const control=createController({api:{create:async()=>({id:`created-${++sequence}`,mode:'claw'}),detail:async id=>({id,mode:'claw',messages:[]}),message:async()=>{await hold;return {accepted};}},logger(){}});
  await control.open({page:'claw',sessionId:null});control.setDraft('首次问题');await control.create('claw');await control.open({page:'claw',sessionId:'created-1'});
  const pending=control.send();await control.open({page:'claw',sessionId:null});control.setDraft('后来准备的新问题');release();await pending;
  assert.equal(control.state.draft,'后来准备的新问题');await control.open({page:'claw',sessionId:'created-1'});await control.open({page:'claw',sessionId:null});assert.equal(control.state.draft,'后来准备的新问题');
  accepted=false;hold=Promise.resolve();await control.create('claw');await control.open({page:'claw',sessionId:'created-2'});await control.send();await control.open({page:'claw',sessionId:null});assert.equal(control.state.draft,'后来准备的新问题');
});

test('copying a rendered reply writes only its actual Markdown and reports clipboard errors',async()=>{
  const { copyResearchText }=await import('../../app/research_web/ui/views.mjs');
  const writes=[],events=[];
  await copyResearchText('## 真正回复',{clipboard:{writeText:async value=>writes.push(value)},logger:event=>events.push(event)});
  assert.deepEqual(writes,['## 真正回复']);assert.deepEqual(events,['research_text_copied']);
  await assert.rejects(copyResearchText('回复',{clipboard:{writeText:async()=>{throw new Error('denied');}},logger:event=>events.push(event)}),/无法复制/);
  await assert.rejects(copyResearchText('',{clipboard:{writeText:async()=>writes.push('bad')}}),/没有可复制/);
  assert.equal(writes.length,1);
  assert.match(renderConversation({id:'s',mode:'claw',messages:[{role:'assistant',text:'内容'}]}),/data-copy-message="0"/);
});

test('Claw interleaves actual tools by call sequence and excludes native question duplication',()=>{
  const detail={mode:'claw',messages:[{seq:1,role:'user',text:'问题'},{seq:2,role:'assistant',text:'先查询资料'},{seq:6,role:'assistant',text:'结论'}],activities:[{id:'a',seq:3,type:'tool',title:'web_search',tool:'web_search',status:'completed',arguments:{query:'真实查询'},result:'检索结果',duration_ms:1200},{id:'q',seq:4,type:'tool',title:'ask_user_question',status:'completed'},{id:'bad',seq:5,type:'tool',title:'datahub',status:'failed',error:'<denied>'}],question_history:[{id:'q',seq:4,items:[{id:'x',question:'需要哪类资料？'}],answers:[{id:'x',selected:['公开资料']}]}]};
  const html=renderConversation(detail);
  assert.ok(html.indexOf('先查询资料')<html.indexOf('web_search'));
  assert.ok(html.indexOf('web_search')<html.indexOf('需要哪类资料？'));
  assert.ok(html.indexOf('需要哪类资料？')<html.indexOf('datahub'));
  assert.ok(html.indexOf('datahub')<html.indexOf('结论'));
  assert.match(html,/参数/);assert.match(html,/真实查询/);assert.match(html,/检索结果/);assert.match(html,/1\.2 秒/);
  assert.match(html,/工具 2 项 · 成功 1 · 失败 1/);assert.match(html,/&lt;denied&gt;/);
  assert.doesNotMatch(html,/ask_user_question|<denied>/);
  assert.equal(renderConversation(detail),html);
  assert.doesNotMatch(renderConversation({...detail,mode:'fingpt'}),/真实查询|工具 2 项/);
});
test('pending native questions occupy their actual call position and never duplicate the tool',()=>{
  const html=renderConversation({mode:'claw',messages:[{seq:1,role:'assistant',text:'执行说明'},{seq:8,role:'assistant',text:'后来解释'}],activities:[{id:'q',seq:3,type:'tool',title:'ask_user_question',status:'running'}],questions:[{id:'q',seq:3,items:[{id:'scope',question:'待确认范围'}]},{id:'old',items:[{id:'old',question:'旧提问'}]}]});
  assert.ok(html.indexOf('执行说明')<html.indexOf('待确认范围'));
  assert.ok(html.indexOf('待确认范围')<html.indexOf('后来解释'));
  assert.ok(html.indexOf('后来解释')<html.indexOf('旧提问'));
  assert.doesNotMatch(html,/ask_user_question/);assert.equal((html.match(/data-question-form="q"/g)||[]).length,1);
});
test('execution followup payload ignores restored selections and binds exact immutable scope',async()=>{
  const { createController }=await import('../../app/research_web/ui/core.mjs');
  const writes=[];let confirmations=0;
  const detail={id:'exec',mode:'claw',messages:[],status:'idle',execution_context:{definition_snapshot:{output_formats:['md'],research_task:{approved_tools:['web_search'],approved_data_sources:['web']}}}};
  const control=createController({api:{detail:async()=>detail,message:async(id,body)=>{writes.push(body);return {accepted:true};}},confirmTabbit:async()=>{confirmations++;return true;}});
  await control.open({page:'claw',sessionId:'exec'});
  control.setCapability({id:'extra',enabled:true,version:1});control.setTools(['unapproved']);control.setMethods(['extra-method']);control.setFormats([]);
  control.state.tabbitTabs=[{tab_id:'tab',instance_id:'browser'}];control.addAttachments([{id:'unapproved-file'}]);control.setDraft('补充说明');await control.send();
  assert.deepEqual(writes,[{text:'补充说明',tool_ids:['web_search'],expected_formats:['md']}]);assert.equal(confirmations,0);
  assert.equal('attachment_ids' in writes[0],false);assert.deepEqual(control.state.attachments,[{id:'unapproved-file'}]);
  // A separately changed approval snapshot permits uploads; previously excluded selections remain in the next draft.
  detail.execution_context.definition_snapshot.research_task.approved_data_sources=['uploads'];
  control.addAttachments([{id:'approved-file'}]);control.setDraft('参考附件');await control.send();
  assert.deepEqual(writes[1],{text:'参考附件',tool_ids:['web_search'],expected_formats:['md'],attachment_ids:['unapproved-file','approved-file']});
  delete detail.execution_context.definition_snapshot.output_formats;
  control.setDraft('缺失快照不能发送');await control.send();
  assert.equal(writes.length,2);assert.equal(control.state.draft,'缺失快照不能发送');assert.match(control.state.error,/缺少批准范围/);
});
test('run reports use safe Markdown and shared actual tool details with provenance',()=>{
  const html=renderClawRunCards([{id:'r',automation_id:'a',definition_version:2,session_id:'exec',trigger:'manual',result_text:'## 实际报告\n\n|项目|结果|\n|---|---|\n|A|B|\n\n<script>alert(1)</script>',activities:[{id:'t',type:'tool',title:'search',status:'failed',arguments:{q:'参数值'},result:'返回值',error:'失败原因',duration_ms:34}],files:[{id:'f',name:'报告.md',url:'/api/research/sessions/exec/files/f/download'}]}]);
  assert.match(html,/<h2>实际报告<\/h2>/);assert.match(html,/<table>/);assert.doesNotMatch(html,/<script>/);
  assert.match(html,/参数值/);assert.match(html,/返回值/);assert.match(html,/失败原因/);assert.match(html,/执行会话 exec/);
});
test('source run previews complete Markdown delivery safely without copying report into source inputs',()=>{
  const preview='/api/research/sessions/exec/files/f/preview';
  const html=renderClawRunCards([{id:'r',session_id:'exec',definition_version:2,result_text:'简短回复',files:[{name:'完整.md',preview_url:preview,url:'/api/research/sessions/exec/files/f/download'},{name:'report.html',preview_url:preview},{name:'unsafe.md',preview_url:'javascript:alert(1)'},{name:'outside.md',preview_url:'/api/research/sessions/exec/files/%2e%2e/preview'},{name:'foreign.md',preview_url:'/api/research/sessions/other/files/f/preview'},{name:'download.md',preview_url:'/api/research/sessions/exec/files/f/download'}]}]);
  assert.match(html,/完整报告 · 完整.md/);assert.match(html,/来源：执行会话 exec · 定义 v2/);
  assert.match(html,/src="\/api\/research\/sessions\/exec\/files\/f\/preview" sandbox="" referrerpolicy="no-referrer" loading="lazy"/);
  assert.equal((html.match(/<iframe/g)||[]).length,1);assert.doesNotMatch(html,/src="javascript:|src="[^\"]*%2e|完整报告 · report.html|data-reference/);
});
test('confirmed draft receipts replay actual saved versions read-only without claiming current enable state',async()=>{
  const { positionClawAutomationCards }=await import('../../app/research_web/ui/claw-workspace.mjs');
  const saved={id:'a',name:'已保存任务',definition_version:2,schedule:{kind:'weekly',weekdays:[0,1,2,3,4],hour:15,minute:30,timezone:'Asia/Shanghai'},research_task:{description:'已保存研究',model_id:'actual-model'},output_formats:['md']};
  const draft={id:'d',operation:'update',automation_id:'a',status:'confirmed',confirmed_at:'2026-10-14T01:00:00Z',confirmed_enabled:true,confirmed_definition:saved,body:{name:'旧草稿名称',research_task:{description:'旧草稿内容'}}};
  const html=renderAutomationDrafts([draft],new Map([['d',{name:'未提交编辑'}]]));
  assert.match(html,/日程确认回执/);assert.match(html,/已保存任务/);assert.match(html,/定义 v2/);assert.match(html,/当时保存\/启用状态：已保存 · 已启用/);assert.match(html,/当前状态请查看 Agent 日程/);assert.match(html,/actual-model/);assert.match(html,/确认时间/);assert.match(html,/先跑一次已保存任务/);
  assert.doesNotMatch(html,/<form|<input|<textarea|data-run-automation|旧草稿名称|未提交编辑/);
  const positions=positionClawAutomationCards({activities:[{seq:4,status:'completed',tool:'rwb_prepare_automation_update',arguments:{automation_id:'a'},result:{id:'d'}}],automation_drafts:[draft]});assert.equal(positions.entries.length,1);assert.equal(positions.entries[0].seq,4);
  const legacy=renderAutomationDrafts([{...draft,confirmed_definition:undefined,confirmed_enabled:undefined}]);assert.match(legacy,/版本未知/);assert.match(legacy,/状态未记录/);assert.doesNotMatch(legacy,/定义 v2|已启用/);
  const escaped=renderAutomationDrafts([{...draft,confirmed_definition:{...saved,name:'<script>',research_task:{description:'<svg>',model_id:'<img>'}}}]);assert.doesNotMatch(escaped,/<script>|<svg>|<img>/);
  const retry=renderAutomationDrafts([{...draft,enable_error:'unavailable'}]);assert.match(retry,/重试启用/);assert.doesNotMatch(retry,/日程确认回执/);
});
test('execution composer displays immutable snapshot and keeps followup separate from grants',()=>{
  const detail={mode:'claw',execution_context:{automation_id:'a',definition_version:2,definition_snapshot:{name:'点评',output_formats:['md'],research_task:{model_id:'locked-model',model_provider:'official',approved_data_sources:['datahub'],approved_tools:['web_search'],output_requirements:'Markdown 报告'}}}};
  const html=renderComposer({page:'claw',detail,draft:'补充问题',expectedFormats:null,models:[],model:'unrelated'});
  assert.match(html,/locked-model/);assert.match(html,/定义 v2/);assert.match(html,/datahub/);assert.match(html,/web_search/);assert.match(html,/MD/);
  assert.doesNotMatch(html,/自动 · 无需文件|id="model-select"|data-format=|data-method-id|data-slash-search/);
  assert.match(html,/data-upload disabled/);assert.doesNotMatch(html,/placeholder="[^\"]*@|@ 实时标签页/);
  assert.match(html,/补充问题/);assert.match(html,/追问不会修改日程定义/);
  const missing=renderComposer({page:'claw',detail:{execution_context:{definition_snapshot:{}}}});
  assert.match(missing,/未提供范围快照/);assert.match(missing,/未提供工具快照/);assert.match(missing,/未提供格式快照/);
  assert.doesNotMatch(missing,/无额外数据|无额外工具|自动 · 无需文件/);
});

test('schedule table distinguishes real manual and scheduled runs and all weekdays', () => {
  const html = renderClawSchedules([{ id:'a', name:'点评', enabled:true, schedule:{kind:'weekly',weekdays:[0,1,2,3,4],hour:15,minute:30,timezone:'Asia/Shanghai'}, target:{kind:'research_task',version:2}, next_run_at:null }], [{id:'r',automation_id:'a',trigger:'manual',research_status:'completed',session_id:'s',created_at:1}]);
  assert.match(html, /<table/); assert.match(html,/周一、周二、周三、周四、周五/);
  assert.match(html,/手动试跑/); assert.match(html,/不是交易日历/);
  assert.doesNotMatch(html,/交付渠道|MCP 市场/);
});
test('research confirmation preserves version and scope and presents explicit enable', () => {
  const body={name:'点评',target_kind:'research_task',research_task:{description:'研究',model:'m',approved_data_sources:['datahub'],approved_tools:[],output_requirements:'html'},input_template:'研究',schedule:{kind:'weekly',weekdays:[0,1,2,3,4],hour:15,minute:30,timezone:'Asia/Shanghai'}};
  const html=renderAutomationDrafts([{id:'d',status:'proposed',body,action:'update',automation_id:'a',expected_version:2}]);
  assert.match(html,/确认更新/); assert.match(html,/v2/); assert.match(html,/权限/);
  const values=new Map([['name','点评'],['input_template','增加技术面'],['kind','weekly'],['timezone','Asia/Shanghai'],['time','15:30'],['weekdays','0,1,2,3,4']]);
  const result=automationDraftBody(body,values);
  assert.deepEqual(result.schedule.weekdays,[0,1,2,3,4]); assert.deepEqual(result.research_task.approved_data_sources,body.research_task.approved_data_sources);
  assert.equal(result.research_task.description,'增加技术面');
  assert.match(renderAutomationDrafts([{id:'d',status:'proposed',body}]),/确认创建并启用/);
});
test('Claw capability chooser only selects and links to centralized management',()=>{
  const html=renderClawConnections([{id:'s',kind:'skill',name:'真实能力',enabled:true}],[]);
  assert.match(html,/data-skill-shortcut="s"/); assert.match(html,/能力中心/);
  assert.doesNotMatch(html,/连接状态|数据源配置|MCP 市场与安装/);
});
test('Claw schedule creation keeps its draft after homepage examples are removed',()=>{
  const html=renderClawSchedules([]); assert.match(html,/新建任务/); assert.match(html,/data-claw-case="schedule"/);
  assert.deepEqual(clawCases.map(item=>item.id),['schedule']);
  assert.match(clawCases[0].text,/先澄清/);
  assert.doesNotMatch(html,/回放|工具成功|已完成/);
});
test('side navigation owns schedule and workspace while topbar offers reopening',()=>{
  assert.match(renderSidebar({page:'claw'}),/view=plans/);
  assert.match(renderSidebar({page:'claw'}),/view=projects/);
  assert.match(renderTopbar({page:'claw'}),/sidebar-reopen[^>]*aria-expanded="false"/);
});

test('explicit create-enable changes only the confirmation endpoint and keeps the draft body', async()=>{
  const requests=[];
  const api=createAPI({fetcher:async(url, options)=>{ requests.push([url,options]); return new Response(JSON.stringify({id:'a',enabled:true})); }});
  const body={target_kind:'research_task',research_task:{description:'内容'}};
  await api.confirmAutomationDraft('s','d',body,true);
  await api.confirmAutomationDraft('s','legacy',body);
  assert.match(requests[0][0], /confirm\?enable=true$/); assert.doesNotMatch(requests[1][0], /enable=true/);
  assert.deepEqual(JSON.parse(requests[0][1].body),body);
});
test('failed enable retains an explicit same-draft retry while update shows definition differences',()=>{
  const body={target_kind:'research_task',research_task:{description:'新研究',model_id:'m'},schedule:{kind:'weekly',weekdays:[0,1,2,3,4],hour:15,minute:30,timezone:'Asia/Shanghai'}};
  const retry=renderAutomationDrafts([{id:'d',status:'confirmed',enable_error:'unavailable',body}]);
  assert.match(retry,/重试启用/); assert.match(retry,/data-claw-draft-form="d"/);
  const update=renderAutomationDrafts([{id:'u',operation:'update',status:'proposed',automation_id:'a',body:{expected_version:2,research_task:body.research_task},previous_definition:{research_task:{description:'旧研究'},schedule:body.schedule}}]);
  assert.match(update,/变更前/); assert.match(update,/旧研究/); assert.match(update,/新研究/);
  assert.doesNotMatch(update,/name="timezone"/); assert.match(update,/保持原定义/);
});

test('run source labels respect the actual schedule trigger and unknown stays visible',()=>{
  const html=renderClawRunCards([{id:'r',trigger:'schedule',research_status:'completed'},{id:'x'}]);
  assert.match(html,/定时运行/); assert.match(html,/运行来源未知/);
  assert.doesNotMatch(html,/手动试跑/);
});

test('desktop sidebar focus uses the content reopen control and mobile keeps drawer controls', async()=>{
  const { focusSidebarControl } = await import('../../app/research_web/ui/shell.mjs');
  const selections=[];
  const document={querySelector:selector=>({focus:()=>selections.push(selector)})};
  focusSidebarControl(document,false); focusSidebarControl(document,false,true); focusSidebarControl(document,true); focusSidebarControl(document,true,true);
  assert.deepEqual(selections,['.topbar .sidebar-reopen','.secondary-sidebar .sidebar-collapse','.topbar .menu-toggle','.rail-mobile-close']);
});
test('readable parent and individual session rows retain escaped history restrictions', async()=>{
  const { renderResearchAttention, renderSessionRow } = await import('../../app/research_web/ui/shell.mjs');
  const { renderHistory } = await import('../../app/research_web/ui/views.mjs');
  const session={id:'s',mode:'claw',title:'父会话',history_warning:'<历史受限>',status:'idle',updated_at:1};
  for (const html of [renderResearchAttention(session),renderSessionRow(session),renderHistory([session])]) {
    assert.match(html,/&lt;历史受限&gt;/); assert.doesNotMatch(html,/<历史受限>/);
  }
});
test('enable retry card exposes the exact saved definition without editable controls',()=>{
  const body={name:'已保存名称',target_kind:'research_task',research_task:{description:'已保存内容',model_id:'m'},schedule:{kind:'daily',hour:15,minute:30,timezone:'Asia/Shanghai'}};
  const html=renderAutomationDrafts([{id:'d',automation_id:'a',status:'confirmed',enable_error:'unavailable',body}],new Map([['d',{name:'忽略的编辑',input_template:'忽略的内容'}]]));
  assert.match(html,/已保存名称/); assert.match(html,/已保存内容/);
  assert.doesNotMatch(html,/<input|<textarea|<select|忽略的编辑|忽略的内容|data-claw-draft-dismiss/);
  assert.match(html,/查看已保存任务/);
});

test('weekly confirmation uses named execution-day checkboxes and hides other frequencies',()=>{
  const body={name:'点评',target_kind:'research_task',research_task:{description:'研究',model_provider:'deepseek-official',model_id:'deepseek-flash'},schedule:{kind:'weekly',weekday:2,hour:15,minute:30,timezone:'Asia/Shanghai'}};
  const html=renderAutomationDrafts([{id:'d',status:'proposed',body}]);
  assert.match(html,/type="checkbox" name="weekdays" value="2" checked/);
  assert.match(html,/周一/); assert.match(html,/周日/); assert.match(html,/deepseek-official \/ deepseek-flash/);
  assert.doesNotMatch(html,/旧单星期日|0=周一|以逗号分隔|name="weekday"|name="day"|name="once_at"/);
  const monthly=renderAutomationDrafts([{id:'d',status:'proposed',body}],new Map([['d',{kind:'monthly',day:'12'}]]));
  assert.match(monthly,/name="day"/); assert.doesNotMatch(monthly,/name="weekdays"|name="once_at"/);
});
test('multiple execution days survive draft edits and empty selection is rejected',async()=>{
  const { captureAutomationDraftEdits }=await import('../../app/research_web/ui/claw-workspace.mjs');
  const form=new FormData(); form.set('kind','weekly'); form.set('weekdays_present','1'); form.append('weekdays','0'); form.append('weekdays','4');
  const edits=captureAutomationDraftEdits(form,{time:'15:30',input_template:'保留文本'});
  assert.deepEqual(edits.weekdays,['0','4']); assert.equal(edits.time,'15:30'); assert.equal(edits.input_template,'保留文本');
  form.set('name','点评');form.set('input_template','研究');form.set('timezone','Asia/Shanghai');form.set('time','15:30');
  assert.deepEqual(automationDraftBody({schedule:{}},form).schedule.weekdays,[0,4]);
  form.delete('weekdays');assert.throws(()=>automationDraftBody({schedule:{weekday:2}},form),/至少选择一个/);
});

test('run cards use real definition names, safe delivered files and restricted result errors',()=>{
  const html=renderClawRunCards([{id:'r',session_id:'s',definition_snapshot:{name:'每日收盘点评'},result_error:'<执行会话已删除>',files:[{name:'report.html',url:'/api/research/sessions/s/files/f/download'},{name:'missing.md'},{name:'unsafe',url:'javascript:alert(1)'}]}]);
  assert.match(html,/<strong>每日收盘点评<\/strong>/); assert.match(html,/结果受限：&lt;执行会话已删除&gt;/);
  assert.match(html,/href="\/api\/research\/sessions\/s\/files\/f\/download"/);
  assert.doesNotMatch(html,/href="javascript:|href="undefined"|href="null"/);
  assert.match(html,/<p>missing.md<\/p>/);
});

test('confirmed native answers replay between messages by event sequence and stay read-only',async()=>{
  const { renderConversation }=await import('../../app/research_web/ui/views.mjs');
  const html=renderConversation({mode:'claw',messages:[{role:'user',text:'开始任务',seq:1},{role:'assistant',text:'日程草稿已提出',seq:9}],question_history:[{id:'call-1',seq:5,items:[{id:'time',question:'执行时间？'}],answers:[{id:'time',selected:['15:30'],custom:'周一到周五'}]}]});
  assert.ok(html.indexOf('开始任务')<html.indexOf('已询问 1 个问题')); assert.ok(html.indexOf('已询问 1 个问题')<html.indexOf('日程草稿已提出'));
  assert.match(html,/aria-label="已确认的原生提问参数"/); assert.match(html,/执行时间？/); assert.match(html,/15:30/); assert.match(html,/周一到周五/);
  assert.doesNotMatch(html,/<form|<input|<textarea|data-question-form/);
});
test('question replay escapes native labels and cannot invent omitted answers',async()=>{
  const { renderConversation }=await import('../../app/research_web/ui/views.mjs');
  const html=renderConversation({messages:[],question_history:[{id:'q',seq:3,items:[{id:'scope',question:'<img src=x onerror=alert(1)>'},{id:'model',question:'模型？'}],answers:[{id:'scope',selected:['<script>'],custom:'<svg onload=alert(1)>'}]}]});
  assert.match(html,/&lt;img/); assert.match(html,/&lt;script&gt;/); assert.match(html,/&lt;svg/); assert.doesNotMatch(html,/<(?:img|script)\b|<svg[^>]*\bonload\s*=/i);
  assert.match(html,/未记录回答/); assert.doesNotMatch(html,/尚无消息/);
  assert.doesNotMatch(renderConversation({messages:[{role:'user',text:'旧会话'}]}),/已确认参数/);
});

test('update confirmation promises only a same-task update, preserving enable state',()=>{
  const html=renderAutomationDrafts([{id:'d',operation:'update',status:'proposed',automation_id:'a',body:{expected_version:1,research_task:{description:'修改'}},previous_definition:{schedule:{kind:'daily',hour:15,minute:30,timezone:'Asia/Shanghai'}}}]);
  assert.match(html,/确认后更新同一任务，保留启用状态，不立即运行/);
  assert.doesNotMatch(html,/确认创建并启用后|创建成功不会立即运行/);
});
test('schedule timestamps are displayed in each definition timezone with explicit labels',()=>{
  const date='2026-01-01T00:00:00Z';
  const html=renderClawSchedules([{id:'a',schedule:{kind:'daily',hour:8,minute:0,timezone:'Asia/Shanghai'},next_run_at:date},{id:'b',schedule:{kind:'daily',hour:19,minute:0,timezone:'America/New_York'},next_run_at:date}],[]);
  assert.match(html,/8:00:00.*Asia\/Shanghai/); assert.match(html,/19:00:00.*America\/New_York/);
  const run=renderClawRunCards([{id:'r',created_at:date,definition_snapshot:{schedule:{timezone:'America/New_York'}}}]);
  assert.match(run,/19:00:00.*America\/New_York/);
});
test('late example navigation cannot overwrite a different actual controller session draft',async()=>{
  const { prepareClawExampleDraft, createController }=await import('../../app/research_web/ui/core.mjs');
  const controller=createController({api:{detail:async id=>({id,mode:'claw',messages:[],files:[],status:'idle'})}});
  let generation=1,release;
  const hold=new Promise(resolve=>{release=resolve;});
  const prepared=prepareClawExampleDraft(controller,'案例草稿',{currentGeneration:()=>generation,navigate:async()=>{generation++; await controller.open({page:'claw',sessionId:null});await hold;}});
  generation++;await controller.open({page:'claw',sessionId:'other'});controller.setDraft('当前会话原草稿');release();
  assert.equal(await prepared,false);assert.equal(controller.state.draft,'当前会话原草稿');
  assert.equal(controller.state.route.sessionId,'other');
  await controller.open({page:'claw',sessionId:null});controller.setDraft('保留已有首页草稿');
  const ok=await prepareClawExampleDraft(controller,'案例草稿',{currentGeneration:()=>generation,navigate:()=>{}});
  assert.equal(ok,true);assert.equal(controller.state.draft,'保留已有首页草稿\n\n案例草稿');
});

test('restricted historical conversation remains readable but composer cannot execute',async()=>{
  const { renderComposer }=await import('../../app/research_web/ui/composer.mjs');
  const html=renderComposer({page:'claw',draft:'保留草稿',detail:{id:'old',execution_restricted:true},runtimeReady:true});
  assert.match(html,/执行受限，仍可查看原记录与文件/);assert.match(html,/data-new>新建研究/);
  assert.match(html,/<textarea[^>]*disabled/);assert.match(html,/composer-send[^>]*disabled/);
  assert.match(html,/保留草稿/);
});

test('dedicated schedule table exposes a read-only refresh control and disables it while pending',()=>{
  assert.match(renderClawSchedules([],[]),/data-claw-schedule-refresh>刷新日程与运行/);
  assert.match(renderClawSchedules([],[],true),/data-claw-schedule-refresh disabled/);
});

test('explicit reference attachments show original names and provenance without changing file identity',async()=>{
  const { renderComposer }=await import('../../app/research_web/ui/composer.mjs');
  const reference={id:'copy-1',name:'reference-uuid.md',source_name:'每日收盘点评-v2.md',source_session_id:'source-session',source_file_id:'source-file',sha256:'a'.repeat(64)};
  const html=renderComposer({page:'claw',draft:'继续研究',attachments:[reference,{id:'upload-1',name:'普通上传.md'}]});
  assert.match(html,/每日收盘点评-v2.md/);assert.doesNotMatch(html,/reference-uuid.md/);
  assert.match(html,/href="#\/claw\?session=source-session"/);assert.match(html,/来源会话/);assert.match(html,/source-file/);
  assert.match(html,/data-remove-attachment="copy-1"/);assert.match(html,/普通上传.md/);
  assert.equal(reference.id,'copy-1');assert.equal(reference.name,'reference-uuid.md');
});
test('reference name and provenance are escaped and source routes cannot become executable URLs',async()=>{
  const { renderComposer }=await import('../../app/research_web/ui/composer.mjs');
  const html=renderComposer({page:'claw',attachments:[{id:'copy',name:'copy.md',source_name:'<img src=x onerror=alert(1)>',source_session_id:'javascript:alert(1)',source_file_id:'" onclick="alert(1)'}]});
  assert.match(html,/&lt;img/);assert.match(html,/&quot; onclick=&quot;/);assert.match(html,/#\/claw\?session=javascript%3Aalert/);
  assert.doesNotMatch(html,/<img|href="javascript:|title="[^"]*" onclick=/);
});

test('Claw preserves reasoning and opens only the current streaming assistant without reordering activities',()=>{
  const detail={mode:'claw',status:'running',messages:[{role:'user',seq:1,text:'开始'},{role:'assistant',seq:2,reasoning:'旧回合推理',text:'已有正文'},{role:'assistant',seq:4,reasoning:'当前推理',text:''}],activities:[{id:'tool',seq:3,type:'tool',title:'中间工具',status:'completed'}]};
  const html=renderConversation(detail);
  assert.match(html,/旧回合推理/);assert.match(html,/当前推理/);assert.match(html,/正在思考…/);
  assert.equal((html.match(/class="answer-thinking" open/g)||[]).length,1);
  assert.ok(html.indexOf('旧回合推理')<html.indexOf('中间工具'));assert.ok(html.indexOf('中间工具')<html.indexOf('当前推理'));
  const finished=renderConversation({...detail,status:'completed'});
  assert.match(finished,/当前推理/);assert.doesNotMatch(finished,/class="answer-thinking" open|正在思考…/);
});
