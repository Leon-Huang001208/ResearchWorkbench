import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {resolve,join} from 'node:path';
import {randomBytes,randomUUID} from 'node:crypto';
import postgres from 'postgres';
import {migrate,ingestPage} from '../src/database.ts';
import {initializeIdentity,activateRuntime} from '../src/control.ts';
import {openQueue} from '../src/queue.ts';
import {grantWorker} from '../src/provision.ts';
import {saveAutomaticEvent,configureChannel,saveChannelJudgment,judgmentAt} from '../src/events.ts';
import {evaluateChannelRules,ruleEvidenceAt} from '../src/channel-rules.ts';
import {configureSource} from '../src/source-control.ts';
import {sha256} from '../src/material.ts';

test('worker channel rules preserve immutable basis, coverage comparability, configuration history and human overrides',{timeout:15000},async()=>{
  const dir=resolve(import.meta.dirname,'../../../logs/hot-stage-zero');
  const receipt=JSON.parse(await readFile(join(dir,'receipt.json'),'utf8')),password=await readFile(join(dir,'password'),'utf8');
  const options={host:'127.0.0.1',port:receipt.port,database:'hot_probe',onnotice:()=>{}};
  const db=postgres({...options,username:'postgres',password});
  const schema='hot_rules_'+randomBytes(5).toString('hex');let ordinary:ReturnType<typeof postgres>|undefined;
  try{
    await migrate(db,schema);const instance=randomUUID(),token=randomBytes(32).toString('hex');
    await initializeIdentity(db,schema,instance,token);const owner=await activateRuntime(db,schema,instance,token,'native');
    const boss=await openQueue(db,schema,true);await boss.stop();
    const role='hot_rw_'+randomBytes(5).toString('hex'),workerPassword=randomBytes(32).toString('hex');
    await db.unsafe(`create role "${role}" login nosuperuser nocreatedb nocreaterole password '${workerPassword}'`);
    await grantWorker(db,schema,role);ordinary=postgres({...options,username:role,password:workerPassword});
    await db`insert into ${db(schema)}.sources(id,operator,config) values('fed','Federal Reserve','{}'::jsonb)`;
    const now=new Date(),item={url:'https://www.federalreserve.gov/newsevents/pressreleases/'+randomUUID()+'.htm',title:'Interest rate decision',excerpt:'Rate policy fixture',
      upstreamId:null,publishedRaw:now.toISOString(),publishedAt:now,updatedRaw:'',sourceUpdatedAt:null};
    const material=await ingestPage(db,{source:'fed',raw:'synthetic rule fixture',acquiredAt:now,materials:[item],cursor:{}},schema);
    const eventId=randomUUID();await saveAutomaticEvent(ordinary,schema,owner,eventId,0,{title:'中文利率决定',materials:[{id:material.materialIds[0],revision:1,relation:'same_occurrence'}],links:[]});
    await configureChannel(db,schema,owner,'macro',0,{name:'Macro',topics:['interest rate'],sourceIds:['fed'],importanceRules:['Official rate policy'],
      rules:[{id:'rate-policy',keywords:['interest rate'],requireOfficial:true,relevance:95,importance:90}]});
    await configureChannel(db,schema,owner,'gold',0,{name:'Gold',topics:['gold'],sourceIds:['fed'],importanceRules:['Rates affect gold research'],
      rules:[{id:'rate-channel',keywords:['interest rate'],requireOfficial:true,relevance:85,importance:80}]});
    await configureChannel(db,schema,owner,'ai',0,{name:'AI',topics:['AI technology'],sourceIds:['fed'],importanceRules:[]});
    const [{before}]=await db`select clock_timestamp() before`;
    assert.equal(await evaluateChannelRules(ordinary,schema,owner),3);
    assert.equal(await evaluateChannelRules(ordinary,schema,owner),0);
    assert.equal(await judgmentAt(db,schema,eventId,'gold',before),null);
    const read=()=>new Date(Date.now()+1000);
    const initial=await ruleEvidenceAt(db,schema,eventId,'macro',read());
    assert.equal(initial!.judgment.judgment.importance,90);assert.ok(initial!.judgment.judgment.heat<90);
    assert.equal(initial!.evidence!.details.reportCount,1);assert.equal(initial!.evidence!.details.independentOperators,1);
    assert.equal(initial!.evidence!.details.comparability,'no_baseline');
    assert.equal((await judgmentAt(db,schema,eventId,'ai',read()))!.judgment.relevance,0);
    assert.equal((await judgmentAt(db,schema,eventId,'gold',read()))!.judgment.relevance,85);
    const [{priorPause}]=await db`select clock_timestamp() as "priorPause"`;
    await configureSource(db,schema,owner,randomUUID(),{sourceId:'fed',expectedRevision:'0',enabled:false});
    assert.equal(await evaluateChannelRules(ordinary,schema,owner),3);
    const paused=await ruleEvidenceAt(db,schema,eventId,'macro',read());
    assert.equal(paused!.evidence!.details.comparability,'changed');
    assert.equal(paused!.judgment.judgment.informationIncrement,0,'source config changes cannot repeatedly create new information');
    assert.equal((await ruleEvidenceAt(db,schema,eventId,'macro',priorPause))!.judgment.id,initial!.judgment.id);
    await assert.rejects(db`update ${db(schema)}.channel_rule_evidence set details='{}'::jsonb`);
    const human={relevance:100,importance:99,informationIncrement:50,heat:1,evidence:'single_official' as const,reason:'Operator review fixture',limitations:[]};
    await saveChannelJudgment(db,schema,owner,{eventId,eventRevision:1,channelId:'gold',channelVersion:1,inputHash:sha256('human'),authority:'human',judgment:human});
    await configureChannel(db,schema,owner,'gold',1,{name:'Gold revised',topics:['gold'],sourceIds:['fed'],importanceRules:[]});
    await evaluateChannelRules(ordinary,schema,owner);
    assert.equal((await judgmentAt(db,schema,eventId,'gold',read()))!.judgment.importance,99);
    assert.equal((await judgmentAt(db,schema,eventId,'gold',read()))!.inherited,true);
  }finally{if(ordinary)await ordinary.end({timeout:5});await db.end({timeout:5});}
});
