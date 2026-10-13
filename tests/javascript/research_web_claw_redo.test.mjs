import test from 'node:test';
import assert from 'node:assert/strict';
import { renderClawSchedules, renderClawRunCards, renderClawCases, renderAutomationDrafts, automationDraftBody, renderClawConnections } from '../../app/research_web/ui/claw-workspace.mjs';
import { createAPI } from '../../app/research_web/ui/core.mjs';
import { renderSidebar, renderPrimaryRail } from '../../app/research_web/ui/shell.mjs';

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
test('Claw examples prepare drafts with no invented replay or success',()=>{
  const html=renderClawCases('all'); assert.match(html,/每日收盘点评/); assert.match(html,/data-claw-case/);
  assert.doesNotMatch(html,/回放|工具成功|已完成/);
});
test('side navigation owns schedule and workspace while rail always offers reopening',()=>{
  assert.match(renderSidebar({page:'claw'}),/view=plans/);
  assert.match(renderSidebar({page:'claw'}),/view=projects/);
  assert.match(renderPrimaryRail({page:'claw',secondaryOpen:false}),/aria-expanded="false"/);
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

test('desktop sidebar focus uses the visible rail and mobile close uses the topbar', async()=>{
  const { focusSidebarControl } = await import('../../app/research_web/ui/shell.mjs');
  const selections=[];
  const document={querySelector:selector=>({focus:()=>selections.push(selector)})};
  focusSidebarControl(document,false); focusSidebarControl(document,true); focusSidebarControl(document,true,true);
  assert.deepEqual(selections,['.primary-rail .rail-toggle','.topbar .menu-toggle','.rail-mobile-close']);
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
  assert.ok(html.indexOf('开始任务')<html.indexOf('已确认参数')); assert.ok(html.indexOf('已确认参数')<html.indexOf('日程草稿已提出'));
  assert.match(html,/来源：DSH 原生提问/); assert.match(html,/执行时间？/); assert.match(html,/15:30/); assert.match(html,/周一到周五/);
  assert.doesNotMatch(html,/<form|<input|<textarea|data-question-form/);
});
test('question replay escapes native labels and cannot invent omitted answers',async()=>{
  const { renderConversation }=await import('../../app/research_web/ui/views.mjs');
  const html=renderConversation({messages:[],question_history:[{id:'q',seq:3,items:[{id:'scope',question:'<img src=x onerror=alert(1)>'},{id:'model',question:'模型？'}],answers:[{id:'scope',selected:['<script>'],custom:'<svg onload=alert(1)>'}]}]});
  assert.match(html,/&lt;img/); assert.match(html,/&lt;script&gt;/); assert.match(html,/&lt;svg/); assert.doesNotMatch(html,/<img|<script|<svg/);
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
