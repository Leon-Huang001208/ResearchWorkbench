import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile,mkdtemp,realpath,mkdir,writeFile} from 'node:fs/promises';
import {resolve,join} from 'node:path';
import {randomBytes,randomUUID} from 'node:crypto';
import postgres from 'postgres';
import {migrate,ingestPage} from '../src/database.ts';
import {initializeIdentity,activateRuntime,pauseRuntime} from '../src/control.ts';
import {openQueue} from '../src/queue.ts';
import {grantWorker,grantController} from '../src/provision.ts';
import {saveAutomaticEvent,configureChannel,saveChannelJudgment} from '../src/events.ts';
import {parseFeed} from '../src/feed.ts';
import {startService} from '../src/service.ts';
import {rpc} from '../src/transport.ts';
import {sha256} from '../src/material.ts';
import {execFileSync} from 'node:child_process';

test('signed event/channel projections are bounded, historical and read-only; controller mutations replay once',{timeout:105000},async()=>{
  const dir=resolve(import.meta.dirname,'../../../logs/hot-stage-zero'),baseline=JSON.parse(await readFile(join(dir,'receipt.json'),'utf8'));
  const password=await readFile(join(dir,'password'),'utf8');
  const db=postgres({host:'127.0.0.1',port:baseline.port,database:'hot_probe',username:'postgres',password,onnotice:()=>{}});
  const schema='hot_event_rpc_'+randomBytes(5).toString('hex'),worker='hot_erw_'+randomBytes(5).toString('hex'),controller='hot_erc_'+randomBytes(5).toString('hex');
  const workerPassword=randomBytes(32).toString('hex'),controllerPassword=randomBytes(32).toString('hex');
  const instanceId=randomUUID(),controllerToken=randomBytes(32).toString('hex'),readerToken=randomBytes(32).toString('hex');
  let service:Awaited<ReturnType<typeof startService>>|undefined;
  let managerCleanup:(()=>void)|undefined;
  try{
    await migrate(db,schema);await initializeIdentity(db,schema,instanceId,controllerToken);
    const boss=await openQueue(db,schema,true);await boss.stop();
    await db.unsafe(`create role "${worker}" login nosuperuser nocreatedb nocreaterole password '${workerPassword}'`);
    await db.unsafe(`create role "${controller}" login nosuperuser nocreatedb nocreaterole password '${controllerPassword}'`);
    await grantWorker(db,schema,worker);await grantController(db,schema,controller);
    await db`insert into ${db(schema)}.sources(id,operator,config) values('fed','Federal Reserve','{}'::jsonb)`;
    const raw=await readFile(join(dir,'fed.xml'),'utf8'),now=new Date();
    const items=parseFeed(raw,'https://www.federalreserve.gov/feeds/press_all.xml',now).slice(0,2).map((item,index)=>({...item,title:index?'Policy 100 percent known':'Policy 100% known',excerpt:'Synthetic read projection fixture'}));
    const stored=await ingestPage(db,{source:'fed',raw,acquiredAt:now,materials:items,cursor:{}},schema);
    const initial=await activateRuntime(db,schema,instanceId,controllerToken,'native');
    const a=randomUUID(),b=randomUUID();
    for(const [i,id] of [a,b].entries())await saveAutomaticEvent(db,schema,initial,id,0,{title:i?'Beta event':'Alpha event',materials:[{id:stored.materialIds[i],revision:1,relation:'same_occurrence'}],links:[]});
    await configureChannel(db,schema,initial,'macro',0,{name:'Macro',topics:['policy'],sourceIds:['fed'],importanceRules:[]});
    await saveChannelJudgment(db,schema,initial,{eventId:a,eventRevision:1,channelId:'macro',channelVersion:1,inputHash:sha256('human'),authority:'human',
      judgment:{relevance:99,importance:99,heat:1,informationIncrement:1,evidence:'single_official',reason:'Synthetic review',limitations:[]}});
    await saveChannelJudgment(db,schema,initial,{eventId:b,eventRevision:1,channelId:'macro',channelVersion:1,inputHash:sha256('human second'),authority:'human',
      judgment:{relevance:50,importance:50,heat:1,informationIncrement:1,evidence:'unverified',reason:'Synthetic second review',limitations:[]}});
    await pauseRuntime(db,schema,initial,controllerToken);
    service=await startService({config:{enabled:true,database:{mode:'external',tls:'disable',port:baseline.port,name:'hot_probe',schema,user:worker}},
      instanceId,mode:'native',workerPassword,controllerUser:controller,controllerPassword,controllerToken,readerToken});
    const read=(op:string,params:any={})=>rpc(service!.port,service!.owner,readerToken,op,params) as Promise<any>;
    const control=(op:string,params:any,id=randomUUID())=>rpc(service!.port,service!.owner,controllerToken,op,params,id) as Promise<any>;
    const list=await read('events.list',{channelId:'macro',sort:'importance',limit:1});
    assert.equal(list.items[0].id,a);assert.equal(list.hasMore,true);
    const next=await read('events.list',{channelId:'macro',sort:'importance',limit:1,offset:1,cutoff:list.cutoff});assert.equal(next.items[0].id,b);
    const special=await read('events.list',{q:'100%'});assert.equal(special.items.length,1);
    const briefRequest=randomUUID(),briefId=randomUUID(),briefArgs={briefId,expectedVersion:0,eventIds:[a,b],channelId:'macro',cutoff:list.cutoff};
    await assert.rejects(read('brief.create',briefArgs),/denied/);
    const brief=await control('brief.create',briefArgs,briefRequest);
    assert.equal(brief.version,1);assert.deepEqual(await control('brief.create',briefArgs,briefRequest),brief);
    await assert.rejects(control('brief.create',{...briefArgs,eventIds:[a]},briefRequest),/request_conflict/);
    const savedBrief=await read('brief.get',{briefId,version:1});assert.equal(savedBrief.contentHash,brief.contentHash);
    assert.equal(savedBrief.payload.events.length,2);const listedBriefs=await read('brief.list');assert.equal(listedBriefs.items[0].briefId,briefId);
    await assert.rejects(db`update ${db(schema)}.brief_versions set content_hash=${'0'.repeat(64)} where brief_id=${briefId}`);
    const channelRequest=randomUUID(),config={name:'Gold',topics:['gold'],sourceIds:['fed'],importanceRules:[]};
    const args={channelId:'gold',expectedVersion:0,config};
    await assert.rejects(read('channel.configure',args),/denied/);
    const created=await control('channel.configure',args,channelRequest);
    assert.deepEqual(await control('channel.configure',{config,expectedVersion:0,channelId:'gold'},channelRequest),created);
    await assert.rejects(control('channel.configure',{...args,config:{...config,name:'Changed'}},channelRequest),/request_conflict/);
    assert.equal((await read('channels',{cutoff:list.cutoff})).items.length,1);
    // PostgreSQL versions retain microseconds; a JS millisecond cutoff in the same
    // tick legitimately precedes the just-committed version. Advance this test clock.
    await new Promise(resolve=>setTimeout(resolve,5));
    assert.equal((await read('channels')).items.length,2);
    const correctionRequest=randomUUID(),change={type:'title',id:a,expected:1,title:'Human Alpha'};
    await assert.rejects(read('event.correct',{reason:'Operator title fix',change}),/denied/);
    const corrected=await control('event.correct',{reason:'Operator title fix',change},correctionRequest);
    assert.deepEqual(await control('event.correct',{reason:'Operator title fix',change},correctionRequest),corrected);
    assert.equal((await read('event.detail',{eventId:a,cutoff:list.cutoff})).title,'Alpha event');
    const current=await read('event.detail',{eventId:a,reportLimit:1});assert.equal(current.title,'Human Alpha');
    assert.equal(current.judgments.find((j:any)=>j.channelId==='macro').inherited,true);
    const secondBriefRequest=randomUUID(),secondBriefArgs={...briefArgs,expectedVersion:1,cutoff:current.cutoff};
    const secondBrief=await control('brief.create',secondBriefArgs,secondBriefRequest);assert.equal(secondBrief.version,2);
    assert.deepEqual(await read('brief.get',{briefId,version:1}),savedBrief);
    assert.equal((await read('brief.list',{cutoff:listedBriefs.cutoff})).items[0].version,1);
    await assert.rejects(read('brief.list',{offset:1}),/cutoff_required/);
    assert.equal((await read('brief.get',{briefId})).payload.events[0].title,'Human Alpha');
    await assert.rejects(control('brief.create',briefArgs),/version_conflict/);
    const [briefPrivileges]=await db`select has_table_privilege(${worker},${schema+'.brief_versions'},'INSERT') can_insert,
      has_column_privilege(${worker},${schema+'.briefs'},'current_version','UPDATE') can_update`;
    assert.equal(briefPrivileges.can_insert,false);assert.equal(briefPrivileges.can_update,false);
    assert.equal(current.reports.length,1);assert.equal(current.reports[0].contentHash.length,64);
    await assert.rejects(read('events.list',{limit:51}),/params_invalid/);
    await assert.rejects(read('events.list',{cutoff:'2026-02-31T00:00:00Z'}),/cutoff_invalid/);
    await assert.rejects(read('events.list',{cutoff:new Date(Date.now()+3600000).toISOString()}),/cutoff_invalid/);
    await assert.rejects(read('events.list',{sql:'select *'}),/params_invalid/);
    await assert.rejects(read('events.list',{offset:1}),/cutoff_required/);
    assert.equal((await read('events.list',{channelId:'gold'})).items.length,0);
    assert.equal((await read('events.list',{channelId:'gold',minRelevance:0})).items.length,2);
    assert.equal((await db`select count(*)::int n from ${db(schema)}.channel_control_requests`)[0].n,1);
    assert.equal((await db`select count(*)::int n from ${db(schema)}.event_corrections`)[0].n,1);
    assert.equal((await db`select count(*)::int n from ${db(schema)}.model_attempts`)[0].n,0);
    assert.equal((await db`select count(*)::int n from ${db(schema)}.raw_pages`)[0].n,1);
    await control('event.correct',{reason:'Explicit channel membership fixture',change:{type:'channels',id:b,expected:1,channelIds:['macro']}});
    assert.equal((await read('events.list',{channelId:'macro'})).items.length,2);
    assert.equal((await read('events.list',{channelId:'macro',minRelevance:80})).items.length,1,'manual membership cannot bypass an explicit score filter');
    await service.close();service=undefined;
    service=await startService({config:{enabled:true,database:{mode:'external',tls:'disable',port:baseline.port,name:'hot_probe',schema,user:worker}},
      instanceId,mode:'native',workerPassword,controllerUser:controller,controllerPassword,controllerToken,readerToken});
    assert.deepEqual(await read('brief.get',{briefId,version:1}),savedBrief);
    assert.deepEqual(await control('brief.create',secondBriefArgs,secondBriefRequest),secondBrief,'restart and lost response replay cannot produce version3');
    assert.equal((await db`select count(*)::int n from ${db(schema)}.brief_versions`)[0].n,2);
    await service.close();service=undefined;
    const home=await realpath(await mkdtemp('/tmp/rwb-hot-projection-cli-'));await mkdir(join(home,'hot'),{mode:0o700});
    const project=resolve(import.meta.dirname,'../../..');
    const nativeConfig={enabled:true,database:{mode:'external',tls:'disable',port:baseline.port,name:'hot_probe',schema,user:worker,controllerUser:controller}};
    await writeFile(join(home,'hot','settings.json'),JSON.stringify({schemaVersion:1,projectRoot:project,config:nativeConfig}),{mode:0o600});
    await writeFile(join(home,'hot','identity.json'),JSON.stringify({projectRoot:project,instanceId}),{mode:0o600});
    const probe=`import io,json,sys\nfrom pathlib import Path\nfrom contextlib import redirect_stdout\nfrom types import SimpleNamespace\nfrom unittest.mock import patch\nfrom research_workbench_entrypoint.hot_manager import HotManager\nfrom research_workbench_entrypoint.hot import dispatch\np=json.load(sys.stdin)\nclass Credentials:\n def get_password(self,service,account): return p['secrets'].get(account)\nm=HotManager(Path(p['project']),Path(p['home']),Credentials())\ndef cli(args):\n stream=io.StringIO()\n with patch('research_workbench_entrypoint.bootstrap.native_python',return_value=Path(sys.executable)),patch.dict('sys.modules',{'app.research_web.credential_backend':SimpleNamespace(SystemKeyringBackend=Credentials)}),patch('research_workbench_entrypoint.hot_manager.HotManager',return_value=m),redirect_stdout(stream):\n  code=dispatch(['--data-home',p['home'],*args],Path(p['project']))\n if code: raise RuntimeError('cli fixture failed')\n return json.loads(stream.getvalue())\ntry:\n m.start()\n channels=cli(['channels','--json'])\n events=cli(['events','--query','100%','--json'])\n detail=cli(['event',p['event'],'--json'])\n cfg=Path(p['home'])/'channel.json';cfg.write_text(json.dumps({'name':'Gold CLI','topics':['gold'],'sourceIds':['fed'],'importanceRules':[]}))\n configured=cli(['channel-configure','gold','--expected-version','1','--file',str(cfg),'--request-id','44444444-4444-4444-8444-444444444444','--json'])\n change_file=Path(p['home'])/'change.json';change_file.write_text(json.dumps({'type':'title','id':p['event'],'expected':2,'title':'CLI title'}));corrected=cli(['event-correct','--file',str(change_file),'--reason','CLI integration','--request-id','55555555-5555-4555-8555-555555555555','--json'])\n correctedAgain=cli(['event-correct','--file',str(change_file),'--reason','CLI integration','--request-id','55555555-5555-4555-8555-555555555555','--json'])\n print(json.dumps({'channels':len(channels['items']),'literalRows':len(events['items']),'title':detail['title'],'version':configured['version'],'revision':corrected['source']['revision'],'sameCorrection':corrected==correctedAgain}))\nfinally:\n m.stop()\n`;
    const bootstrap=JSON.stringify({project,home,event:a,secrets:{'hot-database':workerPassword,'hot-controller-database':controllerPassword,'rpc-controller':controllerToken,'rpc-reader':readerToken}});
    const cleanupProbe=`import json,sys\nfrom pathlib import Path\nfrom research_workbench_entrypoint.hot_manager import HotManager\np=json.load(sys.stdin)\nclass Credentials:\n def get_password(self,service,account): return p['secrets'].get(account)\nm=HotManager(Path(p['project']),Path(p['home']),Credentials())\nprint(json.dumps(m.stop()))\n`;
    managerCleanup=()=>{
      const cleaned=execFileSync('/opt/homebrew/bin/python3.12',['-c',cleanupProbe],{cwd:project,env:{...process.env,RESEARCH_NODE_BINARY:process.execPath},timeout:15000,encoding:'utf8',input:bootstrap});
      assert.equal(JSON.parse(cleaned).state,'stopped');
    };
    const proof=execFileSync('/opt/homebrew/bin/python3.12',['-c',probe],{cwd:project,env:{...process.env,RESEARCH_NODE_BINARY:process.execPath},timeout:60000,encoding:'utf8',input:bootstrap});
    assert.deepEqual(JSON.parse(proof),{channels:2,literalRows:1,title:'Human Alpha',version:2,revision:3,sameCorrection:true});
    // A disappeared Python parent does not run its finally; the independent cleanup must still stop its owned Node.
    const orphanProbe=`import json,sys\nfrom pathlib import Path\nfrom research_workbench_entrypoint.hot_manager import HotManager\np=json.load(sys.stdin)\nclass Credentials:\n def get_password(self,service,account): return p['secrets'].get(account)\nm=HotManager(Path(p['project']),Path(p['home']),Credentials())\nm.start()\nsys.exit(98)\n`;
    assert.throws(()=>execFileSync('/opt/homebrew/bin/python3.12',['-c',orphanProbe],{cwd:project,env:{...process.env,RESEARCH_NODE_BINARY:process.execPath},timeout:20000,encoding:'utf8',input:bootstrap}),
      (error:any)=>error.status===98);
    managerCleanup();
  }finally{
    const cleanup=await Promise.allSettled([(async()=>{if(service)await service.close();})(),(async()=>{if(managerCleanup)managerCleanup();})(),db.end({timeout:5})]);
    if(cleanup.some(result=>result.status==='rejected'))throw Error('hot_event_rpc_fixture_cleanup_failed');
  }
});
