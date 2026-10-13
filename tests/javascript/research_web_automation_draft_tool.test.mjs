import test from 'node:test';
import assert from 'node:assert/strict';
import { apply } from '../../app/research_web/runtime/research-tools.mjs';

test('native schedule tool proposes only; no create/enable or caller paths', async () => {
  const tools = new Map(); const calls = [];
  const ctx = { tools: { register: tool => tools.set(tool.name, tool) }, logger: { info() {}, warn() {} } };
  apply(ctx, { python: '/python', runnerPath: '/runner', researchRoot: '/research' }, undefined,
    async () => ({ admitted: true }), async (_ctx, _exec, _config, args) => { calls.push(args); return { id: 'draft-one', status: 'proposed' }; });
  const tool = tools.get('rwb_prepare_automation');
  assert.ok(tool);
  const args = { name: '每日研究', target_kind: 'skill', target_id: 'company-research', target_version: 1, input_template: '研究公司', schedule: { kind: 'daily', timezone: 'Asia/Shanghai', hour: 9, minute: 0 } };
  const result = await tool.execute(args, { signal: new AbortController().signal });
  assert.equal(JSON.parse(result.result_json).status, 'proposed');
  assert.equal(calls.length, 1);
  await assert.rejects(() => tool.execute({ ...args, enabled: true }, { signal: new AbortController().signal }), /draft_arguments_invalid/);
  await assert.rejects(() => tool.execute({ ...args, cwd: '/secret' }, { signal: new AbortController().signal }), /draft_arguments_invalid/);
  assert.equal(calls.length, 1);
});

test('native tools expose direct research, versioned updates and guarded trial control', async () => {
  const tools=new Map();const actions=[];
  const ctx={tools:{register:tool=>tools.set(tool.name,tool)},logger:{info(){},warn(){}}};
  apply(ctx,{python:'/python',runnerPath:'/runner',researchRoot:'/research'},undefined,
    async()=>({admitted:true}),async(_ctx,_exec,_config,args)=>({status:'proposed',body:args}),
    async(_ctx,_exec,_config,args)=>{actions.push(args);return{status:args.operation==='run'?'queued':'proposed'};});
  const exec={signal:new AbortController().signal};
  const create=tools.get('rwb_prepare_automation');
  assert.ok(create.parameters.properties.target_kind.enum.includes('research_task'));
  assert.ok(create.parameters.properties.schedule.properties.weekdays);
  const definition={schema_version:1,description:'每日收盘点评',model_provider:'deepseek-official',model_id:'deepseek-flash',output_requirements:'Markdown',approved_data_sources:['web'],approved_tools:['research_run_script']};
  assert.equal(JSON.parse((await create.execute({name:'每日收盘点评',target_kind:'research_task',research_task:definition,schedule:{kind:'weekly',timezone:'Asia/Shanghai',weekdays:[0,1,2,3,4],hour:15,minute:30}},exec)).result_json).status,'proposed');
  await tools.get('rwb_list_automations').execute({},exec);
  await tools.get('rwb_prepare_automation_update').execute({automation_id:'task',body:{expected_version:1,research_task:definition}},exec);
  const trial=await tools.get('rwb_run_automation').execute({automation_id:'task'},exec);
  assert.equal(JSON.parse(trial.result_json).status,'queued');
  assert.deepEqual(actions.map(a=>a.operation),['list','prepare_update','run']);
  await assert.rejects(()=>tools.get('rwb_run_automation').execute({automation_id:'task',confirmed:true},exec),/automation_arguments_invalid/);
  await assert.rejects(()=>tools.get('rwb_prepare_automation_update').execute({automation_id:'task'},exec),/automation_arguments_invalid/);
});
