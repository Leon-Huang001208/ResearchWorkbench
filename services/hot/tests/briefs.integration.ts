import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile,writeFile} from 'node:fs/promises';
import {resolve,join} from 'node:path';
import {randomBytes,randomUUID} from 'node:crypto';
import postgres from 'postgres';
import {migrate,ingestPage} from '../src/database.ts';
import {initializeIdentity,activateRuntime} from '../src/control.ts';
import {saveAutomaticEvent,configureChannel} from '../src/events.ts';
import {evaluateChannelRules} from '../src/channel-rules.ts';
import {freezeBrief,briefMarkdown} from '../src/briefs.ts';

test('PG frozen brief keeps exact old material/config/event evidence after later changes without paid calls',{timeout:15000},async()=>{
  const dir=resolve(import.meta.dirname,'../../../logs/hot-stage-zero');
  const receipt=JSON.parse(await readFile(join(dir,'receipt.json'),'utf8')),password=await readFile(join(dir,'password'),'utf8');
  const db=postgres({host:'127.0.0.1',port:receipt.port,database:'hot_probe',username:'postgres',password,onnotice:()=>{}});
  const schema='hot_brief_'+randomBytes(5).toString('hex');
  try{
    await migrate(db,schema);const instance=randomUUID(),token=randomBytes(32).toString('hex');
    await initializeIdentity(db,schema,instance,token);const owner=await activateRuntime(db,schema,instance,token,'native');
    await db`insert into ${db(schema)}.sources(id,operator,config) values('fed','Federal Reserve','{}'::jsonb)`;
    const now=new Date(),url='https://www.federalreserve.gov/'+randomUUID(),item={url,title:'Interest rate decision',excerpt:'Original policy excerpt',
      upstreamId:null,publishedRaw:now.toISOString(),publishedAt:now,updatedRaw:'',sourceUpdatedAt:null};
    const page=await ingestPage(db,{source:'fed',raw:'synthetic frozen brief fixture',acquiredAt:now,materials:[item],cursor:{}},schema);
    const eventId=randomUUID();
    await saveAutomaticEvent(db,schema,owner,eventId,0,{title:'Original event',materials:[{id:page.materialIds[0],revision:1,relation:'same_occurrence'}],links:[]});
    const config={name:'Macro',topics:['interest rate'],sourceIds:['fed'],importanceRules:[],rules:[{id:'rate',keywords:['interest rate'],relevance:90,importance:80}]};
    await configureChannel(db,schema,owner,'macro',0,config);await evaluateChannelRules(db,schema,owner);
    const [{cutoff}]=await db`select clock_timestamp() cutoff`;
    const selection={eventIds:[eventId],channelId:'macro',cutoff:cutoff.toISOString()};
    const frozen=await freezeBrief(db,schema,selection);const markdown=briefMarkdown(frozen);
    assert.ok(markdown.includes('Original policy excerpt'));assert.ok(markdown.includes('研究重要性 80'));
    assert.ok(markdown.includes('原事件版本 1 · 原频道版本 1'));
    assert.ok(markdown.includes('应用版本：事件 1 · 频道 1 · 当前版本判断'));
    await ingestPage(db,{source:'fed',raw:'synthetic corrected fixture',acquiredAt:new Date(),materials:[{...item,excerpt:'Corrected excerpt'}],cursor:{}},schema);
    await saveAutomaticEvent(db,schema,owner,eventId,1,{title:'Later event',materials:[{id:page.materialIds[0],revision:2,relation:'same_occurrence'}],links:[]});
    await configureChannel(db,schema,owner,'macro',1,{...config,name:'Changed macro'});await evaluateChannelRules(db,schema,owner);
    assert.equal((await freezeBrief(db,schema,selection)).contentHash,frozen.contentHash);
    assert.equal(briefMarkdown(frozen),markdown);assert.ok(!markdown.includes('Corrected excerpt'));assert.ok(!markdown.includes('Later event'));
    await assert.rejects(freezeBrief(db,schema,{...selection,from:'2026-01-01T00:00:00Z',to:'2026-01-02T00:00:00Z'}),/hot_brief_selection_outside_window/);
    await assert.rejects(freezeBrief(db,schema,{...selection,eventIds:[eventId,eventId.toUpperCase()]}),/hot_brief_selection_invalid/);
    const many=await ingestPage(db,{source:'fed',raw:'synthetic multi-page evidence fixture',acquiredAt:new Date(),
      materials:Array.from({length:51},(_,index)=>({...item,url:url+'/'+index,excerpt:'Report '+index})),cursor:{}},schema);
    const largeEvent=randomUUID();await saveAutomaticEvent(db,schema,owner,largeEvent,0,{title:'Multi-page event',
      materials:many.materialIds.map(id=>({id,revision:1,relation:'same_occurrence' as const})),links:[]});
    const paged=await freezeBrief(db,schema,{...selection,eventIds:[largeEvent],cutoff:new Date().toISOString()});
    const event=JSON.parse(JSON.stringify(paged.payload.events[0]));
    assert.equal(event.reports.length,51);assert.equal(new Set(event.reports.map((report:{materialId:string})=>report.materialId)).size,51);
    const cancelled=new AbortController();cancelled.abort();
    await assert.rejects(freezeBrief(db,schema,selection,cancelled.signal),/hot_brief_cancelled/);
    const [{count}]=await db`select count(*)::int count from ${db(schema)}.model_attempts`;assert.equal(count,0);
    await writeFile(join(dir,'brief-synthetic-frozen.md'),markdown,{mode:0o600});
  }finally{await db.end({timeout:5});}
});
