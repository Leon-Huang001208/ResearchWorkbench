import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, mkdir, readFile, realpath, rename, symlink, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { spawnSync } from 'node:child_process';

import { apply } from '../../app/research_web/runtime/research-tools.mjs';

test('report plans become fixed code with Host-only binding and inert JSON', async () => {
  const mod = await import('../../app/research_web/runtime/research-tools.mjs');
  assert.equal(typeof mod.reportPlanCode, 'function');
  const context = {task_id:'a'.repeat(24),contract_sha256:'b'.repeat(64),as_of:'2026-10-19',requirement_ids:['r1']};
  const plan = {title:"');__import__('os').system('unexpected')#中文",sections:[],summary:[],missing:[]};
  const code = mod.reportPlanCode(plan, context);
  assert.ok(code.split('\n').length >= 5);
  assert.ok(Buffer.byteLength(code) <= 65536);
  assert.doesNotMatch(code,/__import__|unexpected|eval\(/);
  const values = [...code.matchAll(/b64decode\('([A-Za-z0-9+/=]+)'\)/g)].map(m=>JSON.parse(Buffer.from(m[1],'base64').toString('utf8')));
  assert.deepEqual(values,[context,plan]);
  assert.throws(()=>mod.reportPlanCode(plan,undefined),/contract/);
  assert.throws(()=>mod.reportPlanCode(plan,{...context,task_id:'other-session'}),/contract/);
  assert.throws(()=>mod.reportPlanCode({...plan,title:'x'.repeat(33000)},context),/limit/);
  const fixedFormats = {...context,formats:['html','docx']};
  const systemPlan = {title:'GDP',sections:[{id:'calc',heading:'Calculation',evidence_ids:['$nominal'],requirement_ids:['r1']}],calculations:[{id:'nominal',operation:'percent_change',operands:['gdp_current_price_preliminary@2025','gdp_current_price_final@2024'],decimal_places:2}],missing:[]};
  const generated = mod.reportPlanCode(systemPlan,fixedFormats);
  const bound = [...generated.matchAll(/b64decode\('([A-Za-z0-9+/=]+)'\)/g)].map(m=>JSON.parse(Buffer.from(m[1],'base64').toString('utf8')));
  assert.deepEqual(bound,[fixedFormats,systemPlan]);
  assert.match(generated,/available_evidence/);
  for(const formats of [[],['html','html'],['exe'],'html']) assert.throws(()=>mod.reportPlanCode(plan,{...context,formats}),/contract/);
});

test('report plan keeps admission, bounded code transport and slot release',async t=>{
  const {EventEmitter}=await import('node:events');const {rm}=await import('node:fs/promises');
  const root=await realpath(await mkdtemp(join(tmpdir(),'rwb-plan-mode-')));t.after(()=>rm(root,{recursive:true}));
  const sid='01234567-89ab-4cde-8fab-0123456789ab';const cwd=join(root,'sessions',sid);await mkdir(cwd,{recursive:true});
  const context={task_id:'a'.repeat(24),contract_sha256:'b'.repeat(64),as_of:'2026-10-19',requirement_ids:['r1']};
  let scope={admitted:true,read_paths:[],report_context:context};const sent=[];let spawned=0;
  const spawn=()=>{spawned++;const child=new EventEmitter();child.stdout=new EventEmitter();child.stderr=new EventEmitter();child.stdin=new EventEmitter();child.kill=()=>{};child.stdin.end=raw=>{sent.push(JSON.parse(raw));child.stdout.emit('data',Buffer.from(JSON.stringify({status:'completed',stdout:'files only',stderr:'',exit_code:0,error:null})));child.emit('close',0);};return child;};
  const tools=new Map();const ctx={tools:{register:x=>tools.set(x.name,x)},sessions:{get(){}},logger:{info(){},warn(){},error(){}}};
  apply(ctx,{python:'/usr/bin/python3',runnerPath:'/tmp/runner.py',researchRoot:root},spawn,async()=>scope);
  const exec={signal:new AbortController().signal,agent:{session:{header:{id:sid,cwd}}}};const tool=tools.get('research_run_script');
  const plan={title:'Test',sections:[],summary:[],missing:[]};
  await assert.rejects(()=>tool.execute({code:'print(1)',report_plan:plan},exec));
  await assert.rejects(()=>tool.execute({report_plan:plan,report_context:context},exec));
  scope={admitted:false,read_paths:[],report_context:context};await assert.rejects(()=>tool.execute({report_plan:plan},exec),/scope/);
  scope={admitted:true,read_paths:[]};await assert.rejects(()=>tool.execute({report_plan:plan},exec),/contract/);
  scope={admitted:true,read_paths:[],report_context:{...context,extra:'caller override'}};await assert.rejects(()=>tool.execute({report_plan:plan},exec),/contract/);
  scope={admitted:true,read_paths:[],report_context:context};await assert.rejects(()=>tool.execute({report_plan:{...plan,title:'中'.repeat(11000)}},exec),/limit/);
  assert.equal(spawned,0);
  assert.equal((await tool.execute({report_plan:plan},exec)).status,'completed');
  assert.match(sent[0].code,/write_business_report_plan/);assert.deepEqual(sent[0].read_paths,[]);
  assert.equal((await tool.execute({code:'print(1)'},exec)).status,'completed');assert.equal(sent[1].code,'print(1)');
});

test('executed plan rejection supplies unique IDs and corrected selection succeeds', async t => {
  const {reportPlanCode} = await import('../../app/research_web/runtime/research-tools.mjs');
  const {rm} = await import('node:fs/promises');
  const root = await mkdtemp(join(tmpdir(),'rwb-plan-feedback-'));
  t.after(()=>rm(root,{recursive:true}));
  const inventory = [{id:'business_unique_a',metric:'gdp_current_price_final',period:'2024',unit:'亿元'},{id:'business_unique_b',metric:'gdp_current_price_final',period:'2024',unit:'亿元'}];
  await writeFile(join(root,'research_report.py'),'def load_business_evidence(task, digest):\n return '+JSON.stringify({observations:inventory})+'\n');
  await writeFile(join(root,'research_report_plan.py'),"def write_business_report_plan(context, plan):\n if plan['sections'][0]['evidence_ids'] != ['business_unique_a']: raise ValueError('research_report_plan_missing_or_ambiguous_observation')\n return {'quality_not_evaluated':True,'next':'research_check_quality'}\n");
  const context={task_id:'a'.repeat(24),contract_sha256:'b'.repeat(64),as_of:'2026-10-16',requirement_ids:['r1'],formats:['html','docx']};
  const plan={title:'Actual',sections:[{id:'facts',heading:'Facts',evidence_ids:['gdp_current_price_final@2024'],requirement_ids:['r1']}],missing:[]};
  const execute = value => spawnSync('python3',['-c',reportPlanCode(value,context)],{cwd:root,encoding:'utf8',env:{...process.env,PYTHONPATH:root,PYTHONDONTWRITEBYTECODE:'1'}});
  const failed=execute(plan);
  assert.equal(failed.status,1,failed.stderr);
  const feedback=JSON.parse(failed.stdout);
  assert.equal(feedback.error,'research_report_plan_missing_or_ambiguous_observation');
  assert.deepEqual(feedback.available_evidence,inventory);
  const corrected={...plan,sections:[{...plan.sections[0],evidence_ids:[feedback.available_evidence[0].id]}]};
  const success=execute(corrected);
  assert.equal(success.status,0,success.stderr);
  assert.equal(JSON.parse(success.stdout).quality_not_evaluated,true);
});

test('document business tool rejects host paths and unadmitted execution', async () => {
  const tools = new Map();
  const ctx = { tools: { register: tool => tools.set(tool.name, tool) }, logger: { info() {}, warn() {}, error() {} } };
  apply(ctx, { python: '/usr/bin/python3', runnerPath: '/tmp/runner.py', researchRoot: '/tmp/research' }, undefined, async () => ({ admitted: false }));
  const tool = tools.get('research_document_operation');
  assert.ok(tool);
  const exec = { signal: new AbortController().signal };
  await assert.rejects(() => tool.execute({ format: 'docx', mode: 'file', operation: 'read', path: '/etc/passwd' }, exec), /document_arguments_invalid/);
  await assert.rejects(() => tool.execute({ format: 'docx', mode: 'file', operation: 'read', file_id: 'a'.repeat(24) }, exec), /document_scope_unverified/);
});

test('Cordis undeclared service getter is never read during research tool registration', () => {
  const tools = new Map();
  let undeclaredReads = 0;
  const target = { tools: { register: tool => tools.set(tool.name, tool) },
    sessions: { get() {} }, logger: { info() {}, warn() {}, error() {} } };
  const ctx = new Proxy(target, { get(object, key, receiver) {
    if (key === 'spawnProcess') {
      undeclaredReads += 1;
      throw new Error('cannot get property spawnProcess without inject');
    }
    return Reflect.get(object, key, receiver);
  } });
  assert.doesNotThrow(() => apply(ctx, { python: '/usr/bin/python3', runnerPath: '/tmp/runner.py', researchRoot: '/tmp/research' }));
  assert.equal(undeclaredReads, 0);
  assert.ok(tools.has('research_run_script'));
});

test('accessor test hooks are not invoked as spawn overrides', () => {
  const tools = new Map();
  const ctx = { tools: { register: tool => tools.set(tool.name, tool) }, logger: {} };
  Object.defineProperty(ctx, 'spawnProcess', { get() { throw new Error('accessor must not execute'); } });
  assert.doesNotThrow(() => apply(ctx, { python: '/usr/bin/python3', runnerPath: '/tmp/runner.py', researchRoot: '/tmp/research' }));
  assert.ok(tools.has('research_run_script'));
});

test('rwb_record_method_use writes only bounded method identity in the current session', async () => {
  const root = await realpath(await mkdtemp(join(tmpdir(), 'rwb-method-')));
  const sid = '01234567-89ab-4cde-8fab-0123456789ab';
  const cwd = join(root, 'sessions', sid);
  await mkdir(cwd, { recursive: true });
  const tools = new Map();
  const ctx = { tools: { register: tool => tools.set(tool.name, tool) }, sessions: { get() {} }, logger: { info() {}, warn() {}, error() {} } };
  apply(ctx, { python: '/usr/bin/python3', runnerPath: '/tmp/runner.py', researchRoot: root });
  const controller = new AbortController();
  const exec = { signal: controller.signal, agent: { session: { header: { id: sid, cwd } } } };
  const result = await tools.get('rwb_record_method_use').execute({ method_id: 'fact-checking', version: '1.0.0', source: 'required' }, exec);
  assert.deepEqual(result, { recorded: true, method_id: 'fact-checking', version: '1.0.0', source: 'required' });
  const rows = (await readFile(join(cwd, '.rwb', 'method-trace.jsonl'), 'utf8')).trim().split('\n').map(JSON.parse);
  assert.deepEqual(rows, [{ method_id: 'fact-checking', version: '1.0.0', source: 'required' }]);
  await assert.rejects(() => tools.get('rwb_record_method_use').execute({ method_id: 'fact-checking', version: '1.0.0', source: 'required', prompt: 'secret' }, exec), /bounded method identity/);
  await rename(join(cwd, '.rwb', 'method-trace.jsonl'), join(cwd, '.rwb', 'retained.jsonl'));
  await symlink(join(cwd, '.rwb', 'retained.jsonl'), join(cwd, '.rwb', 'method-trace.jsonl'));
  await assert.rejects(() => tools.get('rwb_record_method_use').execute({ method_id: 'fact-checking', version: '1.0.0', source: 'required' }, exec));
});

test('script permission failure retains evidence and supplies relative-path recovery only for real PermissionError',async t=>{
  const {EventEmitter}=await import('node:events');
  const {rm}=await import('node:fs/promises');
  const root=await realpath(await mkdtemp(join(tmpdir(),'rwb-permission-hint-')));
  t.after(()=>rm(root,{recursive:true}));
  const sid='01234567-89ab-4cde-8fab-0123456789ab'; const cwd=join(root,'sessions',sid);await mkdir(cwd,{recursive:true});
  const tools=new Map(); let response;
  const spawn=()=>{
    const child=new EventEmitter();child.stdout=new EventEmitter();child.stderr=new EventEmitter();child.stdin=new EventEmitter();child.kill=()=>{};
    child.stdin.end=()=>{child.stdout.emit('data',Buffer.from(JSON.stringify(response)));child.emit('close',0);};return child;
  };
  const ctx={tools:{register:tool=>tools.set(tool.name,tool)},sessions:{get(){}},logger:{info(){},warn(){},error(){}}};
  apply(ctx,{python:'/usr/bin/python3',runnerPath:'/tmp/runner.py',researchRoot:root},spawn,async()=>({admitted:true,read_paths:[]}));
  const tool=tools.get('research_run_script');
  assert.match(tool.description,/os\.getcwd\(\)/);
  assert.match(tool.description,/Path\.resolve\(\)/);
  const exec={agent:{session:{header:{id:sid,cwd}}},signal:new AbortController().signal};
  response={status:'failed',stdout:'',stderr:'Traceback (most recent call last):\nPermissionError: forbidden cwd',exit_code:1,error:null};
  const denied=await tool.execute({code:'print(1)'},exec);
  assert.equal(denied.status,'failed');assert.equal(denied.stderr,response.stderr);assert.equal(denied.exit_code,1);
  assert.match(denied.error,/sandbox_permission_denied/);assert.match(denied.error,/相对路径/);assert.match(denied.error,/不要重试/);
  assert.deepEqual(Object.keys(denied).sort(),['error','exit_code','status','stderr','stdout']);
  response={...response,error:'original_diagnostic'};
  const retained=await tool.execute({code:'print(1)'},exec);
  assert.ok(retained.error.startsWith('original_diagnostic\n'));
  assert.equal(retained.stderr,response.stderr);
  response={status:'failed',stdout:'',stderr:'SyntaxError: bad code',exit_code:1,error:null};
  assert.deepEqual(await tool.execute({code:'print(1)'},exec),response);
  response={status:'completed',stdout:'PermissionError: quoted example',stderr:'',exit_code:0,error:null};
  assert.deepEqual(await tool.execute({code:'print(1)'},exec),response);
});

test('Chinese body target is Host-only bounded context and numeric templates are explicit', async () => {
  const {reportPlanCode}=await import('../../app/research_web/runtime/research-tools.mjs');
  const context={task_id:'a'.repeat(24),contract_sha256:'b'.repeat(64),as_of:'2026-10-16',requirement_ids:['r1'],body_target:1200};
  const plan={title:'研究',sections:[],missing:[]};
  assert.match(reportPlanCode(plan,context),/write_business_report_plan/);
  for(const body_target of [true,299,5001,'1200']) assert.throws(()=>reportPlanCode(plan,{...context,body_target}),/contract/);
  const registered=new Map();apply({tools:{register:t=>registered.set(t.name,t)},logger:{}},{python:'/usr/bin/python3',runnerPath:'/tmp/runner.py',researchRoot:'/tmp/research'});
  const tool=registered.get('research_run_script');
  assert.match(tool.parameters.properties.report_plan.properties.sections.items.properties.analysis.description,/\{\{fact:/);
  assert.equal(tool.parameters.properties.report_plan.properties.body_target,undefined);
  assert.ok(tool.parameters.properties.report_plan.properties.calculations.items.properties.operation.enum.includes('gdp_implicit_deflator'));
});
