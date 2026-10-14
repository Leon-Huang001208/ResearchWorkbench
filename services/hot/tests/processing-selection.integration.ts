import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {resolve,join} from 'node:path';
import {randomBytes,randomUUID} from 'node:crypto';
import postgres from 'postgres';
import type {PgBoss} from 'pg-boss';
import {migrate,ingestPage} from '../src/database.ts';
import {initializeIdentity,activateRuntime,pauseRuntime} from '../src/control.ts';
import {openQueue,processOne} from '../src/queue.ts';
import {registerProcessing,scheduleProcessing,processingPriority} from '../src/processing.ts';
import {sha256} from '../src/material.ts';

test('same queue explicit selection leaves unrelated backlog queued across restart and makes no model calls',{timeout:15000},async()=>{
  const dir=process.env.RWB_HOT_PROOF_DIR?resolve(process.env.RWB_HOT_PROOF_DIR):resolve(import.meta.dirname,'../../../logs/hot-stage-zero');
  const receipt=JSON.parse(await readFile(join(dir,'receipt.json'),'utf8')),password=await readFile(join(dir,'password'),'utf8');
  const port=process.env.RWB_HOT_PROOF_PORT?Number(process.env.RWB_HOT_PROOF_PORT):receipt.port;
  assert.ok(Number.isSafeInteger(port)&&port>0&&port<65536);
  const db=postgres({host:'127.0.0.1',port,database:'hot_probe',username:'postgres',password,onnotice:()=>{}});
  const schema='hot_selected_'+randomBytes(5).toString('hex'),instance=randomUUID(),token=randomBytes(32).toString('hex');let boss:PgBoss|undefined,provisioned=false;
  try{
    await migrate(db,schema);await initializeIdentity(db,schema,instance,token);provisioned=true;boss=await openQueue(db,schema,true);
    let owner=await activateRuntime(db,schema,instance,token,'native');
    await db`insert into ${db(schema)}.sources(id,operator,config) values('source','Synthetic operator','{}'::jsonb)`;
    const now=new Date(),material=(name:string)=>({url:'https://example.test/'+randomUUID(),title:name,excerpt:name,upstreamId:null,publishedRaw:now.toISOString(),publishedAt:now,updatedRaw:'',sourceUpdatedAt:null});
    const page=await ingestPage(db,{source:'source',raw:'synthetic selection fixture',acquiredAt:now,materials:[material('older backlog'),material('selected current article')],cursor:{}},schema);
    await db.begin(tx=>registerProcessing(tx,schema,page.materialIds));
    const [other,selected]=page.materialIds;
    assert.equal(await scheduleProcessing(db,boss,schema,owner,true),2);
    const [originalOther]=await db`select id,state from ${db(schema)}.job where name='hot.process' and data->'payload'->>'materialId'=${other}`;
    assert.equal(await scheduleProcessing(db,boss,schema,owner,true,[selected]),1);
    await pauseRuntime(db,schema,owner,token);const oldOwner=owner;owner=await activateRuntime(db,schema,instance,token,'native');
    assert.equal(await scheduleProcessing(db,boss,schema,owner,true,[selected]),1);
    let runs=0;
    assert.equal(await processOne(boss,db,schema,owner,'hot.process',async payload=>{
      assert.equal(JSON.parse(JSON.stringify(payload)).materialId,selected);runs++;
      return {result:{state:'fixture_selected_no_model_execution'}};
    },randomUUID(),120,undefined,processingPriority(owner,[selected])),'completed');
    assert.equal(runs,1);
    const [preservedOther]=await db`select id,state,priority from ${db(schema)}.job where id=${originalOther.id}`;
    assert.equal(preservedOther.id,originalOther.id);assert.equal(preservedOther.state,'created');assert.equal(preservedOther.priority,0);
    const [item]=await db`select state from ${db(schema)}.processing_items where material_id=${other}`;assert.equal(item.state,'pending');
    await assert.rejects(scheduleProcessing(db,boss,schema,oldOwner,true,[selected]),/hot_owner_stale/);
    assert.throws(()=>processingPriority({...owner,generation:'2147483648'},[selected]),/hot_processing_selection_invalid/);
    assert.equal(processingPriority(owner,[]),undefined);
    const [{count}]=await db`select count(*)::int count from ${db(schema)}.model_attempts`;assert.equal(count,0);
    await pauseRuntime(db,schema,owner,token);
  }finally{
    await boss?.stop();
    try{if(provisioned){const [identity]=await db`select instance_id,controller_token_hash from ${db(schema)}.runtime_identity where singleton`;assert.equal(identity.instance_id,instance);assert.equal(identity.controller_token_hash,sha256(token));await db.unsafe(`drop schema "${schema}" cascade`);}}
    finally{await db.end({timeout:5});}
  }
});
