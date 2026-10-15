import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {resolve,join} from 'node:path';
import {randomBytes,randomUUID} from 'node:crypto';
import postgres from 'postgres';
import {migrate,ingestPage} from '../src/database.ts';
import {initializeIdentity,activateRuntime} from '../src/control.ts';
import {parseFeed} from '../src/feed.ts';
import {saveAutomaticEvent,configureChannel,correctEvent,eventAt,saveChannelJudgment,judgmentAt,type MaterialRef} from '../src/events.ts';
import {sha256} from '../src/material.ts';
import {openQueue} from '../src/queue.ts';
import {grantWorker,grantController} from '../src/provision.ts';
import {provisionModelBudget,reserveModel,markModelDispatch,saveModelReceipt} from '../src/model-budget.ts';

test('shared event evidence, as-of aliases, corrections and third channel survive automatic rerun',{timeout:10000},async()=>{
  const dir=resolve(import.meta.dirname,'../../../logs/hot-stage-zero');
  const receipt=JSON.parse(await readFile(join(dir,'receipt.json'),'utf8')),password=await readFile(join(dir,'password'),'utf8');
  const db=postgres({host:'127.0.0.1',port:receipt.port,database:'hot_probe',username:'postgres',password,onnotice:()=>{}});
  const schema='hot_events_'+randomBytes(5).toString('hex');
  let ordinary:ReturnType<typeof postgres>|undefined,controller:ReturnType<typeof postgres>|undefined;
  try{
    await migrate(db,schema);const instance=randomUUID(),token=randomBytes(32).toString('hex');
    await initializeIdentity(db,schema,instance,token);const owner=await activateRuntime(db,schema,instance,token,'native');
    await db`insert into ${db(schema)}.sources(id,operator,config) values('fed','Federal Reserve',${db.json({})})`;
    const raw=await readFile(join(dir,'fed.xml'),'utf8'),acquiredAt=new Date();
    const stored=await ingestPage(db,{source:'fed',raw,acquiredAt,materials:parseFeed(raw,'https://www.federalreserve.gov/feeds/press_all.xml',acquiredAt).slice(0,2),cursor:{}},schema);
    const refs=stored.materialIds.map(id=>({id,revision:1,relation:'same_occurrence' as const}));
    const a=randomUUID(),b=randomUUID();
    await saveAutomaticEvent(db,schema,owner,a,0,{title:'First occurrence',materials:[refs[0]],links:[]});
    await saveAutomaticEvent(db,schema,owner,b,0,{title:'Other occurrence',materials:[refs[1]],links:[]});
    const [{cutoff}]=await db`select clock_timestamp() cutoff`;
    const requestId=randomUUID(),change={type:'merge' as const,id:b,expected:1,target:a,targetExpected:1};
    const merged=await correctEvent(db,schema,owner,requestId,'Duplicate reports confirmed',change);
    assert.deepEqual(await correctEvent(db,schema,owner,requestId,'Duplicate reports confirmed',change),merged);
    assert.equal((await eventAt(db,schema,b,cutoff))!.id,b);
    assert.equal((await eventAt(db,schema,b,new Date(Date.now()+1000)))!.id,a);
    assert.equal((await db`select count(*)::int n from ${db(schema)}.event_corrections`)[0].n,1);
    await assert.rejects(saveAutomaticEvent(db,schema,owner,a,2,{title:'First occurrence',materials:[refs[0]],links:[]}),/manual_conflict/);
    await assert.rejects(saveAutomaticEvent(db,schema,owner,b,2,{title:'Old alias',materials:refs,links:[]}),/alias_requires_canonical/);
    const split=await correctEvent(db,schema,owner,randomUUID(),'One material belongs to a different occurrence',
      {type:'split',id:a,expected:2,materialIds:[refs[1].id],title:'Separate progress'}) as any;
    assert.equal(split.source.snapshot.materials.length,1);assert.equal(split.target.snapshot.materials.length,1);
    await assert.rejects(saveAutomaticEvent(db,schema,owner,a,3,{title:'First occurrence',materials:refs,links:[]}),/manual_conflict/);
    await correctEvent(db,schema,owner,randomUUID(),'Operator corrected title',{type:'title',id:a,expected:3,title:'Human title'});
    await assert.rejects(saveAutomaticEvent(db,schema,owner,a,4,{title:'Machine title',materials:[refs[0]],links:[]}),/manual_conflict/);
    const update=await saveAutomaticEvent(db,schema,owner,a,4,{title:'Human title',materials:[refs[0]],links:[{id:split.target.id,relation:'direct_followup'}]});
    assert.equal(update.revision,5);
    await assert.rejects(saveAutomaticEvent(db,schema,owner,split.target.id,1,{title:'Separate progress',materials:[refs[1]],links:[{id:a,relation:'direct_followup'}]}),/link_cycle/);
    for(const id of ['ai','macro','gold'])await configureChannel(db,schema,owner,id,0,{name:id,topics:[id],sourceIds:['fed'],importanceRules:['Official policy may be important despite low report count']});
    assert.equal((await db`select count(*)::int n from ${db(schema)}.channels`)[0].n,3);
    const judgment={relevance:90,importance:95,informationIncrement:80,heat:10,evidence:'single_official' as const,
      reason:'Official policy matters independently of repost count',limitations:['latest snapshot only']};
    const [{beforeJudgment}]=await db`select clock_timestamp() as "beforeJudgment"`;
    for(const channelId of ['ai','macro','gold'])await saveChannelJudgment(db,schema,owner,{eventId:a,eventRevision:5,channelId,channelVersion:1,inputHash:sha256(channelId),authority:'rule',judgment});
    assert.equal(await judgmentAt(db,schema,a,'gold',beforeJudgment),null);
    assert.equal((await judgmentAt(db,schema,a,'gold',new Date(Date.now()+1000)))!.judgment.heat,10);
    assert.equal((await db`select count(*)::int n from ${db(schema)}.channel_judgments where event_id=${a}`)[0].n,3);
    await saveChannelJudgment(db,schema,owner,{eventId:a,eventRevision:5,channelId:'gold',channelVersion:1,inputHash:sha256('human override'),authority:'human',judgment});
    await assert.rejects(saveChannelJudgment(db,schema,owner,{eventId:a,eventRevision:5,channelId:'gold',channelVersion:1,inputHash:sha256('automatic rerun'),authority:'model',judgment}),/manual_conflict/);
    const [{beforeAdvance}]=await db`select clock_timestamp() as "beforeAdvance"`;
    await saveAutomaticEvent(db,schema,owner,a,5,{title:'Human title',materials:[refs[0]],links:[{id:split.target.id,relation:'direct_followup'}]});
    await configureChannel(db,schema,owner,'gold',1,{name:'Gold revised',topics:['rates'],sourceIds:['fed'],importanceRules:['Official policy']});
    const inherited=await judgmentAt(db,schema,a,'gold',new Date(Date.now()+1000));
    assert.equal(inherited!.authority,'human');assert.equal(inherited!.inherited,true);
    assert.equal(inherited!.event_revision,5);assert.equal(inherited!.channel_version,1);
    assert.equal(inherited!.applied_event_revision,6);assert.equal(inherited!.applied_channel_version,2);
    assert.equal((await judgmentAt(db,schema,a,'gold',beforeAdvance))!.inherited,false);
    await assert.rejects(configureChannel(db,schema,owner,'gold',0,{name:'Gold',topics:['rates'],sourceIds:['fed'],importanceRules:[]}),/revision_conflict/);
    await assert.rejects(db`update ${db(schema)}.event_versions set snapshot='{}'::jsonb`);
    const composite:MaterialRef={...refs[0],relation:'composite'};
    await saveAutomaticEvent(db,schema,owner,randomUUID(),0,{title:'Composite linkage 1',materials:[composite],links:[]});
    await saveAutomaticEvent(db,schema,owner,randomUUID(),0,{title:'Composite linkage 2',materials:[composite],links:[]});
    assert.equal((await db`select count(*)::int n from ${db(schema)}.materials`)[0].n,2);
    const c=randomUUID(),d=randomUUID();
    await saveAutomaticEvent(db,schema,owner,c,0,{title:'Wrong group',materials:refs,links:[]});
    await saveAutomaticEvent(db,schema,owner,d,0,{title:'Existing destination',materials:[refs[0]],links:[]});
    const moveId=randomUUID(),move={type:'reassign' as const,id:c,expected:1,target:d,targetExpected:1,materialIds:[refs[1].id]};
    const moved=await correctEvent(db,schema,owner,moveId,'Attach to the existing occurrence',move) as any;
    assert.equal(moved.source.snapshot.materials.length,1);assert.equal(moved.target.snapshot.materials.length,2);
    assert.deepEqual(await correctEvent(db,schema,owner,moveId,'Attach to the existing occurrence',
      {materialIds:[refs[1].id.toUpperCase()],targetExpected:1,target:d.toUpperCase(),expected:1,id:c.toUpperCase(),type:'reassign'}),moved);
    await assert.rejects(saveAutomaticEvent(db,schema,owner,c,2,{title:'Wrong group',materials:refs,links:[]}),/manual_conflict/);
    await assert.rejects(saveAutomaticEvent(db,schema,owner,d,2,{title:'Existing destination',materials:[refs[0]],links:[]}),/manual_conflict/);
    const boss=await openQueue(db,schema,true);await boss.stop();
    const role='hot_ew_'+randomBytes(5).toString('hex'),control='hot_ec_'+randomBytes(5).toString('hex');
    const workerPassword=randomBytes(32).toString('hex'),controllerPassword=randomBytes(32).toString('hex');
    await db.unsafe(`create role "${role}" login nosuperuser nocreatedb nocreaterole password '${workerPassword}'`);
    await db.unsafe(`create role "${control}" login nosuperuser nocreatedb nocreaterole password '${controllerPassword}'`);
    await grantWorker(db,schema,role);await grantController(db,schema,control);
    const options={host:'127.0.0.1',port:receipt.port,database:'hot_probe',onnotice:()=>{}};
    ordinary=postgres({...options,username:role,password:workerPassword});controller=postgres({...options,username:control,password:controllerPassword});
    await assert.rejects(correctEvent(ordinary,schema,owner,moveId,'Attach to the existing occurrence',move),/control_denied/);
    await assert.rejects(configureChannel(ordinary,schema,owner,'unauthorized',0,{name:'No',topics:[],sourceIds:[],importanceRules:[]}));
    await assert.rejects(saveChannelJudgment(ordinary,schema,owner,{eventId:a,eventRevision:6,channelId:'macro',channelVersion:1,inputHash:sha256('worker impersonation'),authority:'human',judgment}),/control_denied/);
    await assert.rejects(saveChannelJudgment(ordinary,schema,owner,{eventId:a,eventRevision:6,channelId:'macro',channelVersion:1,inputHash:sha256('absent receipt'),authority:'model',judgment}),/model_receipt_required/);
    const key=sha256('synthetic judgment receipt');
    await provisionModelBudget(db,schema,{scopeId:'synthetic',authorizationHash:sha256('test-only'),maxCalls:1,maxTokens:10,maxCostMicros:0,
      daily:{maxCalls:1,maxTokens:10,maxCostMicros:0,timezone:'Asia/Shanghai'}});
    const reserved=await reserveModel(ordinary,schema,owner,'synthetic',{resultKey:key,specHash:key,maxTokens:10,maxCostMicros:0});
    assert.equal(reserved.state,'reserved');if(reserved.state!=='reserved')throw Error('fixture reservation');
    await markModelDispatch(ordinary,schema,owner,reserved.ticket);
    await saveModelReceipt(ordinary,schema,reserved.ticket,{text:JSON.stringify(judgment)},{tokens:1,costMicros:0,providerRequestId:null,costBasis:'synthetic'});
    await saveChannelJudgment(ordinary,schema,owner,{eventId:a,eventRevision:6,channelId:'macro',channelVersion:1,inputHash:key,authority:'model',judgment});
    await assert.rejects(ordinary`insert into ${ordinary(schema)}.channel_judgments(id,event_id,event_revision,channel_id,channel_version,input_hash,authority,judgment,model_attempt_id)
      values(${randomUUID()},${a},6,'ai',1,${key},'model',${ordinary.json({...judgment,heat:99})},${reserved.ticket.id})`,/model_receipt_invalid/);
    await assert.rejects(ordinary`insert into ${ordinary(schema)}.channel_judgments(id,event_id,event_revision,channel_id,channel_version,input_hash,authority,judgment)
      values(${randomUUID()},${a},6,'macro',1,${sha256('SQL impersonation')},'human',${ordinary.json(judgment)})`,/control_denied/);
    await configureChannel(controller,schema,owner,'controller',0,{name:'Controller',topics:[],sourceIds:['fed'],importanceRules:[]});
    await saveAutomaticEvent(ordinary,schema,owner,randomUUID(),0,{title:'Ordinary processing',materials:[refs[0]],links:[]});
    assert.equal((await db`select count(*)::int n from ${db(schema)}.channels`)[0].n,4);
    let frontier:string[]=[];
    // 24-node layered diamond: many paths, few distinct reachable vertices.
    for(let layer=0;layer<12;layer++){
      const next=[randomUUID(),randomUUID()];
      for(const id of next)await saveAutomaticEvent(ordinary,schema,owner,id,0,{title:'Layer '+layer,materials:[refs[0]],
        links:frontier.map(id=>({id,relation:'direct_followup' as const}))});
      frontier=next;
    }
    const origin=randomUUID();await saveAutomaticEvent(ordinary,schema,owner,origin,0,{title:'Diamond origin',materials:[refs[0]],links:[{id:frontier[0],relation:'direct_followup'}]});
    await assert.rejects(saveAutomaticEvent(ordinary,schema,owner,frontier[0].toUpperCase(),1,{title:'Layer 11',materials:[refs[0]],links:[{id:origin.toUpperCase(),relation:'direct_followup'}]}),/link_cycle/);
  }finally{if(ordinary)await ordinary.end({timeout:5});if(controller)await controller.end({timeout:5});await db.end({timeout:5});}
});
