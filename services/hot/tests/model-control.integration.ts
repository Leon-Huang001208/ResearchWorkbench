import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {resolve,join} from 'node:path';
import {randomBytes,randomUUID} from 'node:crypto';
import postgres from 'postgres';
import {execFileSync} from 'node:child_process';
import {migrate} from '../src/database.ts';
import {initializeIdentity,activateRuntime,pauseRuntime} from '../src/control.ts';
import {sha256} from '../src/material.ts';
import {grantWorker} from '../src/provision.ts';
import {openQueue} from '../src/queue.ts';
import {reserveModel,markModelDispatch,markModelUnknown,saveModelReceipt} from '../src/model-budget.ts';
import {modelControl,modelAttempts} from '../src/model-control.ts';

test('explicit offline model controls preserve cumulative charges, audits and late receipts',{timeout:15000},async()=>{
  const dir=resolve(import.meta.dirname,'../../../logs/hot-stage-zero'),baseline=JSON.parse(await readFile(join(dir,'receipt.json'),'utf8'));
  const db=postgres({host:'127.0.0.1',port:baseline.port,database:'hot_probe',username:'postgres',password:await readFile(join(dir,'password'),'utf8'),onnotice:()=>{}});
  const schema='hot_model_control_'+randomBytes(4).toString('hex'),identity={instanceId:randomUUID(),controllerToken:randomBytes(32).toString('hex')};
  const role='hot_model_op_'+randomBytes(4).toString('hex'),password=randomBytes(32).toString('hex');let worker:ReturnType<typeof postgres>|undefined;
  const policy={scopeId:'synthetic_controls',maxCalls:3,maxTokens:300,maxCostMicros:0,daily:{maxCalls:3,maxTokens:300,maxCostMicros:0,timezone:'Asia/Shanghai'}};
  const authorize={requestId:randomUUID(),operator:'synthetic operator',reason:'Explicit zero-cost fixture authorization',operation:'authorize' as const,parameters:{policy,authorizePaid:true}};
  try{
    await migrate(db,schema);await initializeIdentity(db,schema,identity.instanceId,identity.controllerToken);
    const queue=await openQueue(db,schema,true);await queue.stop();
    const first=await modelControl(db,schema,identity,authorize);
    assert.equal(first.state,'authorized');assert.deepEqual(await modelControl(db,schema,identity,authorize),first);
    await assert.rejects(modelControl(db,schema,identity,{...authorize,reason:'different reason'}),/request_conflict/);
    await assert.rejects(modelControl(db,schema,identity,{...authorize,requestId:randomUUID(),parameters:{policy,authorizePaid:false}}),/paid_authorization_required/);
    const owner=await activateRuntime(db,schema,identity.instanceId,identity.controllerToken,'native');
    await assert.rejects(migrate(db,schema),/hot_migration_requires_stopped/);
    const spec={resultKey:sha256('synthetic attempt'),specHash:sha256('synthetic attempt'),maxTokens:100,maxCostMicros:0};
    const attempt=await reserveModel(db,schema,owner,policy.scopeId,spec);if(attempt.state!=='reserved')throw Error('fixture reserve failed');
    await markModelDispatch(db,schema,owner,attempt.ticket);await markModelUnknown(db,schema,attempt.ticket);
    const terminate={requestId:randomUUID(),operator:'synthetic operator',reason:'Stop further work, retain unknown cost',operation:'terminate' as const,parameters:{attemptId:attempt.ticket.id}};
    await assert.rejects(modelControl(db,schema,identity,terminate),/requires_stopped/);
    await pauseRuntime(db,schema,owner,identity.controllerToken);
    const stopped=await modelControl(db,schema,identity,terminate);assert.equal(stopped.state,'abandoned');
    assert.deepEqual(await modelControl(db,schema,identity,terminate),stopped);
    let [quota]=await db`select charged_calls,charged_tokens::text from ${db(schema)}.model_budgets where scope_id=${policy.scopeId}`;
    assert.equal(quota.charged_calls,1);assert.equal(quota.charged_tokens,'100');
    const next=await activateRuntime(db,schema,identity.instanceId,identity.controllerToken,'native');
    assert.equal((await reserveModel(db,schema,next,policy.scopeId,spec)).state,'busy','abandoned unknown cannot be automatically re-sent');
    await pauseRuntime(db,schema,next,identity.controllerToken);
    await db.unsafe(`create role "${role}" login nosuperuser nocreatedb nocreaterole password '${password}'`);await grantWorker(db,schema,role);
    worker=postgres({host:'127.0.0.1',port:baseline.port,database:'hot_probe',username:role,password,onnotice:()=>{}});
    await assert.rejects(modelControl(worker,schema,identity,{...authorize,requestId:randomUUID()}),/control_denied/);
    await assert.rejects(worker`update ${worker(schema)}.model_attempts set state='abandoned' where id=${attempt.ticket.id}`);
    for(const state of ['reserved','cancelled','dispatching','outcome_unknown','received'])
      await assert.rejects(worker`update ${worker(schema)}.model_attempts set state=${state} where id=${attempt.ticket.id}`);
    await saveModelReceipt(worker,schema,attempt.ticket,{text:'late synthetic response'},{tokens:30,costMicros:0,providerRequestId:null,costBasis:'synthetic'});
    [quota]=await db`select charged_calls,charged_tokens::text from ${db(schema)}.model_budgets where scope_id=${policy.scopeId}`;
    assert.equal(quota.charged_calls,1);assert.equal(quota.charged_tokens,'30');
    const listed=await modelAttempts(worker,schema,{scopeId:policy.scopeId});assert.equal(listed.items[0].state,'received');
    assert.equal('dispatch_token_hash' in listed.items[0],false);assert.equal('response' in listed.items[0],false);
    assert.equal((await db`select count(*)::int n from ${db(schema)}.model_control_requests`)[0].n,2);
    const cliOwner=await activateRuntime(db,schema,identity.instanceId,identity.controllerToken,'native');
    const cliAttempt=await reserveModel(db,schema,cliOwner,policy.scopeId,{resultKey:sha256('CLI uncertain'),specHash:sha256('CLI uncertain'),maxTokens:50,maxCostMicros:0});
    if(cliAttempt.state!=='reserved')throw Error('fixture reserve failed');
    await markModelDispatch(db,schema,cliOwner,cliAttempt.ticket);await markModelUnknown(db,schema,cliAttempt.ticket);
    await pauseRuntime(db,schema,cliOwner,identity.controllerToken);
    const project=resolve(import.meta.dirname,'../../..');
    const probe=`import io,json,sys,tempfile\nfrom pathlib import Path\nfrom types import SimpleNamespace\nfrom contextlib import redirect_stdout\nfrom unittest.mock import patch\nfrom research_workbench_entrypoint.hot import dispatch\np=json.load(sys.stdin)\nclass Credentials:\n def get_password(self,service,account): return p['secrets'].get(account)\nwith tempfile.TemporaryDirectory(prefix='rwb-model-cli-') as directory:\n home=Path(directory).resolve(); hot=home/'hot';hot.mkdir(mode=0o700)\n for name,value in [('identity.json',{'projectRoot':p['project'],'instanceId':p['instance']}),('settings.json',{'projectRoot':p['project'],'config':p['config']})]:\n  path=hot/name;path.write_text(json.dumps(value));path.chmod(0o600)\n file=home/'policy.json';file.write_text(json.dumps(p['policy']));file.chmod(0o600)\n def cli(args):\n  output=io.StringIO()\n  with patch('research_workbench_entrypoint.bootstrap.native_python',return_value=Path(sys.executable)),patch.dict('sys.modules',{'app.research_web.credential_backend':SimpleNamespace(SystemKeyringBackend=Credentials)}),redirect_stdout(output):\n   code=dispatch(['--data-home',str(home),*args],Path(p['project']))\n  return code,json.loads(output.getvalue())\n code,first=cli(['model-authorize','--file',str(file),'--authorize-paid','--reason','Explicit zero-cost CLI approval','--request-id',p['requestId'],'--migration-account','migration','--json']);assert code==0\n code,again=cli(['model-authorize','--file',str(file),'--authorize-paid','--reason','Explicit zero-cost CLI approval','--request-id',p['requestId'],'--migration-account','migration','--json']);assert code==0 and first==again\n code,terminated=cli(['model-terminate','--attempt',p['attemptId'],'--reason','Terminate synthetic ambiguous attempt','--request-id',p['terminateId'],'--migration-account','migration','--json']);assert code==0 and terminated['chargesRetained'] is True\n code,again=cli(['model-terminate','--attempt',p['attemptId'],'--reason','Terminate synthetic ambiguous attempt','--request-id',p['terminateId'],'--migration-account','migration','--json']);assert code==0 and again==terminated\n code,listed=cli(['model-attempts','--scope',p['policy']['scopeId'],'--json']);assert code==0 and listed['items'][0]['state']=='abandoned'\n assert first['charged']['calls']==2 and first['charged']['tokens']=='80'\n print(json.dumps({'state':'PASS','calls':first['charged']['calls'],'tokens':first['charged']['tokens'],'items':len(listed['items'])}))\n`;
    const output=JSON.parse(execFileSync('/Users/leon/Desktop/Projects/ResearchWorkbench/.venv/bin/python',['-c',probe],{cwd:project,encoding:'utf8',timeout:15000,
      input:JSON.stringify({project,instance:identity.instanceId,requestId:randomUUID(),terminateId:randomUUID(),attemptId:cliAttempt.ticket.id,policy,config:{enabled:false,database:{mode:'external',host:'127.0.0.1',tls:'disable',port:baseline.port,name:'hot_probe',schema,user:role,controllerUser:'unused_controller',secretRef:'worker',poolMax:1}},
        secrets:{worker:password,migration:await readFile(join(dir,'password'),'utf8'),'rpc-controller':identity.controllerToken}})}));
    assert.equal(output.state,'PASS');assert.equal(output.calls,2);assert.equal(output.tokens,'80');
    assert.equal((await db`select count(*)::int n from ${db(schema)}.model_control_requests`)[0].n,4);
    await assert.rejects(db`delete from ${db(schema)}.model_control_requests`);
  }finally{if(worker)await worker.end({timeout:5});await db.end({timeout:5});}
});
