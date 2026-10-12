import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {resolve,join} from 'node:path';
import {randomBytes,randomUUID} from 'node:crypto';
import postgres from 'postgres';
import {migrate} from '../src/database.ts';
import {initializeIdentity,activateRuntime} from '../src/control.ts';
import {sha256} from '../src/material.ts';
import {openQueue} from '../src/queue.ts';
import {grantWorker} from '../src/provision.ts';
import {provisionModelBudget,reserveModel,markModelDispatch,markModelUnknown,cancelUnsentModel,saveModelReceipt,lookupModel} from '../src/model-budget.ts';

test('cumulative reservations serialize, unknown sends remain charged and late receipts reuse safely',{timeout:10000},async()=>{
  const dir=resolve(process.env.RWB_HOT_TEST_FIXTURE_DIR??resolve(import.meta.dirname,'../../../logs/hot-stage-zero'));
  const receipt=JSON.parse(await readFile(join(dir,'receipt.json'),'utf8')),password=await readFile(join(dir,'password'),'utf8');
  receipt.port=Number(process.env.RWB_HOT_TEST_PG_PORT??receipt.port);
  const db=postgres({host:'127.0.0.1',port:receipt.port,database:'hot_probe',username:'postgres',password,onnotice:()=>{}});
  const schema='hot_budget_'+randomBytes(5).toString('hex');
  const role='hot_bw_'+randomBytes(5).toString('hex'),secret=randomBytes(32).toString('hex');
  let schemaCreated=false,roleCreated=false;
  let worker:ReturnType<typeof postgres>|undefined;
  try{
    assert.equal((await db`select to_regnamespace(${schema}) existing`)[0].existing,null);
    await migrate(db,schema);schemaCreated=true;const instance=randomUUID(),key=randomBytes(32).toString('hex');
    await initializeIdentity(db,schema,instance,key);
    const owner=await activateRuntime(db,schema,instance,key,'native');
    const policy={scopeId:'test_scope',authorizationHash:sha256('synthetic authorization'),maxCalls:2,maxTokens:200,maxCostMicros:1000};
    await provisionModelBudget(db,schema,policy);
    const boss=await openQueue(db,schema,true);await boss.stop();
    try{await db.unsafe(`create role "${role}" login nosuperuser nocreatedb nocreaterole password '${secret}'`);roleCreated=true;}catch{throw Error('hot_fixture_role_failed');}
    await grantWorker(db,schema,role);
    worker=postgres({host:'127.0.0.1',port:receipt.port,database:'hot_probe',username:role,password:secret,onnotice:()=>{}});
    await assert.rejects(provisionModelBudget(worker,schema,{...policy,scopeId:'unapproved'}),/authorization_denied/);
    await assert.rejects(worker`update ${worker(schema)}.model_budgets set max_calls=9999`);
    await assert.rejects(provisionModelBudget(db,schema,{...policy,maxCalls:3}),/authorization_conflict/);
    const spec={resultKey:sha256('input A'),specHash:sha256('model A parameters prompt version'),maxTokens:100,maxCostMicros:500};
    const concurrent=await Promise.all([reserveModel(worker,schema,owner,policy.scopeId,spec),reserveModel(worker,schema,owner,policy.scopeId,spec)]);
    assert.equal(concurrent.filter(row=>row.state==='reserved').length,1);
    assert.equal(concurrent.filter(row=>row.state==='busy').length,1);
    const first=concurrent.find(row=>row.state==='reserved')!;
    if(first.state!=='reserved')throw Error('hot_fixture_ticket_failed');
    await markModelDispatch(worker,schema,owner,first.ticket);
    await assert.rejects(markModelDispatch(db,schema,owner,first.ticket),/dispatch_denied/);
    await markModelUnknown(worker,schema,first.ticket);
    await assert.rejects(cancelUnsentModel(db,schema,owner,first.ticket.id),/cancel_denied/);
    const second=await reserveModel(db,schema,owner,policy.scopeId,{...spec,resultKey:sha256('input B')});
    if(second.state!=='reserved')throw Error('hot_fixture_ticket_failed');
    await assert.rejects(reserveModel(db,schema,owner,policy.scopeId,{...spec,resultKey:sha256('input C')}),/budget_exhausted/);
    const next=await activateRuntime(db,schema,instance,key,'native');
    assert.equal((await reserveModel(db,schema,next,policy.scopeId,spec)).state,'busy');
    await cancelUnsentModel(db,schema,next,second.ticket.id);
    await assert.rejects(markModelDispatch(db,schema,owner,second.ticket),/owner_stale/);
    const response={answer:'synthetic output',metadata:{a:1,b:2}};
    const usage={tokens:40,costMicros:200,providerRequestId:'synthetic-request'};
    let readMiss!:()=>void,continueRead!:()=>void;
    const missed=new Promise<void>(resolve=>{readMiss=resolve;}),proceed=new Promise<void>(resolve=>{continueRead=resolve;});
    const instrumented=new Proxy(worker,{get(target,key,receiver){
      if(key!=='begin')return Reflect.get(target,key,receiver);
      return (fn:any)=>target.begin(async tx=>fn(new Proxy(tx,{apply(sql,thisArg,args){
        const query=Reflect.apply(sql,thisArg,args);
        if(Array.isArray(args[0])&&args[0].join('').includes('.model_results'))return Promise.resolve(query).then(async rows=>{
          if(!rows.length){readMiss();await proceed;}return rows;
        });
        return query;
      }})));
    }});
    const heldLookup=lookupModel(instrumented,schema,spec);await missed;
    const settlement=saveModelReceipt(worker,schema,first.ticket,response,usage);
    let waits=false;
    for(let i=0;i<20;i++){
      const [active]=await db`select count(*)::int n from pg_stat_activity where usename=${role} and wait_event='advisory'`;
      if(active.n){waits=true;break;}await new Promise(resolve=>setTimeout(resolve,10));
    }
    continueRead();assert.equal(waits,true,'late receipt waits on cache lookup fence');
    assert.equal((await heldLookup)?.state,'busy');assert.equal((await settlement).overrun,false);
    const normalized={...spec,resultKey:sha256('input-v2 identity'),specHash:sha256('input-v2 identity'),legacySpecs:[{resultKey:spec.resultKey,specHash:spec.specHash}]};
    const racing=await reserveModel(worker,schema,next,policy.scopeId,normalized);
    assert.equal(racing.state,'reused');if(racing.state==='reused')assert.equal(racing.resultKey,spec.resultKey);
    await saveModelReceipt(db,schema,first.ticket,{metadata:{b:2,a:1},answer:'synthetic output'},usage);
    const reused=await reserveModel(db,schema,next,policy.scopeId,spec);
    assert.equal(reused.state,'reused');
    const [charged]=await db`select * from ${db(schema)}.model_budgets where scope_id=${policy.scopeId}`;
    assert.equal(charged.charged_calls,1);assert.equal(Number(charged.charged_tokens),40);assert.equal(Number(charged.charged_cost_micros),200);
    await assert.rejects(db`update ${db(schema)}.model_receipts set provider_request_id='replaced'`);
    await assert.rejects(saveModelReceipt(db,schema,first.ticket,{answer:'different'},usage),/receipt_conflict/);
    await provisionModelBudget(db,schema,{scopeId:'overrun_scope',authorizationHash:sha256('overrun test'),maxCalls:2,maxTokens:200,maxCostMicros:200});
    const third=await reserveModel(db,schema,next,'overrun_scope',{...spec,resultKey:sha256('input overrun'),maxCostMicros:100});
    if(third.state!=='reserved')throw Error('hot_fixture_ticket_failed');
    const fourth=await reserveModel(db,schema,next,'overrun_scope',{...spec,resultKey:sha256('input pending overrun'),maxCostMicros:100});
    if(fourth.state!=='reserved')throw Error('hot_fixture_ticket_failed');
    await markModelDispatch(db,schema,next,third.ticket);
    assert.equal((await saveModelReceipt(db,schema,third.ticket,{}, {tokens:110,costMicros:101,providerRequestId:null})).overrun,true);
    assert.equal((await db`select provider_request_id from ${db(schema)}.model_receipts where attempt_id=${third.ticket.id}`)[0].provider_request_id,null);
    const [paused]=await db`select paused,charged_tokens from ${db(schema)}.model_budgets where scope_id='overrun_scope'`;
    assert.equal(paused.paused,true);assert.equal(Number(paused.charged_tokens),210);
    await assert.rejects(markModelDispatch(db,schema,next,fourth.ticket),/budget_exhausted/);
    await cancelUnsentModel(db,schema,next,fourth.ticket.id);
    await provisionModelBudget(db,schema,{scopeId:'daily_scope',authorizationHash:sha256('daily test'),maxCalls:3,maxTokens:300,maxCostMicros:300,
      daily:{maxCalls:1,maxTokens:100,maxCostMicros:100,timezone:'Asia/Shanghai'}});
    const daySpec={...spec,maxCostMicros:100,resultKey:sha256('daily A')};
    const dayA=await reserveModel(db,schema,next,'daily_scope',daySpec);
    if(dayA.state!=='reserved')throw Error('hot_fixture_ticket_failed');
    await assert.rejects(reserveModel(db,schema,next,'daily_scope',{...daySpec,resultKey:sha256('daily B')}),/daily_budget_exhausted/);
    await db`update ${db(schema)}.model_attempts set day_key=day_key-1 where id=${dayA.ticket.id}`;
    const dayB=await reserveModel(db,schema,next,'daily_scope',{...daySpec,resultKey:sha256('daily B')});
    if(dayB.state!=='reserved')throw Error('hot_fixture_ticket_failed');
    await assert.rejects(markModelDispatch(db,schema,next,dayA.ticket),/daily_budget_exhausted/);
    await cancelUnsentModel(db,schema,next,dayB.ticket.id);
    await markModelDispatch(db,schema,next,dayA.ticket);
    await markModelUnknown(db,schema,dayA.ticket);
    await assert.rejects(reserveModel(db,schema,next,'daily_scope',{...daySpec,resultKey:sha256('daily C')}),/daily_budget_exhausted/);
  }finally{
    try{
      if(worker)await worker.end({timeout:5});
      if(schemaCreated)await db.unsafe(`drop schema "${schema}" cascade`);
      if(roleCreated)await db.unsafe(`drop role "${role}"`);
    }finally{await db.end({timeout:5});}
  }
});
