/** Independently started Hot control/read service; never starts ResearchService or DSH. */
import postgres from 'postgres';
import { parseConfig,poolOptions,assertNodeRuntime } from './config.ts';
import { SCHEMA_VERSION } from './database.ts';
import { activateRuntime,heartbeatRuntime,pauseRuntime } from './control.ts';
import { openQueue } from './queue.ts';
import { checkDatabase } from './health.ts';
import { startTransport,type RpcHandler } from './transport.ts';
import { logEvent } from './log.ts';
import {runWorker} from './worker.ts';
import {collectionHandlers,scheduleCollection} from './collection.ts';
import {configureSource} from './source-control.ts';
import {scheduleProcessing,processingHandler,type GroupingModel} from './processing.ts';
import {evaluateChannelRules} from './channel-rules.ts';
import {channelsAt,eventsList,eventDetail} from './projections.ts';
import {configureChannelRequest} from './channel-control.ts';
import {createBriefRequest,briefGet,briefList,briefExport} from './brief-control.ts';
import {researchManifestChunk,researchOriginal} from './research-evidence.ts';
import {correctEvent,type Correction} from './events.ts';
import {loadNativeModel,type NativeModelBootstrap,type ModelCapability} from './native-model.ts';

export interface ServiceBootstrap {
  config: unknown; port?: number; instanceId: string; mode: 'native' | 'docker';
  workerPassword: string; controllerUser: string; controllerPassword: string;
  controllerToken: string; readerToken: string;
  nativeModel?:NativeModelBootstrap;
}
export async function startService(input: ServiceBootstrap,capabilities:{groupingModel?:GroupingModel}={}) {
  assertNodeRuntime();
  const config = parseConfig(input.config);
  if (!config.enabled) throw Error('hot_disabled');
  if (!/^[a-zA-Z][a-zA-Z0-9_]{0,62}$/.test(input.controllerUser) || input.controllerUser === config.database.user) throw Error('hot_controller_role_invalid');
  const health = await checkDatabase(config,async()=>input.workerPassword);
  if (health.state !== 'ready') throw Error(health.code ?? 'hot_database_unavailable');
  const db = postgres(poolOptions(config.database,input.workerPassword));
  const reader = postgres({ ...poolOptions(config.database,input.workerPassword),max:2 });
  const controller = postgres({ ...poolOptions({...config.database,user:input.controllerUser},input.controllerPassword),max:2 });
  let boss: Awaited<ReturnType<typeof openQueue>> | undefined;
  let transport: Awaited<ReturnType<typeof startTransport>> | undefined;
  let owner: Awaited<ReturnType<typeof activateRuntime>> | undefined;
  const workerStop=new AbortController();
  const sourceControllers=new Map<string,AbortController>();
  let workerTask:Promise<void>|undefined;
  let workerState='starting';
  let modelCapability:ModelCapability|undefined;
  let groupingModel=capabilities.groupingModel;
  let closed = false;
  const close = async () => {
    if(closed) return;
    closed = true;
    workerStop.abort();
    let failed = false;
    if(transport) { try { await transport.close(); } catch { failed=true; } }
    if(workerTask){try{await workerTask;}catch{failed=true;}}
    if(modelCapability){try{await modelCapability.close();}catch{failed=true;}}
    if(owner) {
      try { await pauseRuntime(controller,config.database.schema,owner,input.controllerToken); }
      catch { logEvent('control_rejected'); }
    }
    if(boss) { try { await boss.stop(); } catch { failed=true; } }
    const endings = await Promise.allSettled([db.end({timeout:5}),reader.end({timeout:5}),controller.end({timeout:5})]);
    if(failed || endings.some(item=>item.status==='rejected')) throw Error('hot_service_close_failed');
  };
  try {
    const [role] = await controller`select rolsuper,rolcreatedb,rolcreaterole from pg_roles where rolname=current_user`;
    if(role.rolsuper || role.rolcreatedb || role.rolcreaterole) throw Error('hot_controller_role_not_scoped');
    const [supervision]=await controller`select has_table_privilege(current_user,${`${config.database.schema}.job_dependency`},'DELETE')
      and has_column_privilege(current_user,${`${config.database.schema}.version`},'monitor_backoff_on','UPDATE') as allowed`;
    if(!supervision.allowed)throw Error('hot_controller_supervision_permission_missing');
    const [sourceAccess]=await controller`select has_column_privilege(current_user,${`${config.database.schema}.sources`},'enabled','UPDATE')
      and has_column_privilege(current_user,${`${config.database.schema}.sources`},'frequency_seconds','UPDATE')
      and has_column_privilege(current_user,${`${config.database.schema}.sources`},'config_revision','UPDATE')
      and has_table_privilege(current_user,${`${config.database.schema}.source_control_requests`},'INSERT') as allowed`;
    if(!sourceAccess.allowed)throw Error('hot_controller_source_permission_missing');
    boss = await openQueue(db,config.database.schema);
    owner = await activateRuntime(controller,config.database.schema,input.instanceId,input.controllerToken,input.mode,300,true);
    const current = owner;
    if(!groupingModel){
      modelCapability=await loadNativeModel(db,config.database.schema,current,config,input.nativeModel);
      groupingModel=modelCapability.groupingModel;
    }
    const noParams = (params: Record<string,postgres.JSONValue>) => { if(Object.keys(params).length) throw Error('hot_rpc_params_invalid'); };
    const handlers = new Map<string,RpcHandler>([
      ['status',{permission:'read',run:async params=>{
        noParams(params);
        const [counts] = await reader`select count(*)::int n from ${reader(config.database.schema)}.sources`;
        const pending=await reader`select state,count(*)::int count from ${reader(config.database.schema)}.processing_items where state<>'applied' group by state`;
        return { state:'initialized',worker:workerState,model:modelCapability?.state??(groupingModel?'ready':'blocked_model'),modelCode:modelCapability?.code??null,processing:JSON.parse(JSON.stringify([...pending])),schemaVersion:SCHEMA_VERSION,
          mode:current.mode,generation:current.generation,sourceCount:counts.n,collectionMode:'latest_snapshot',backfill:'not_supported' };
      }}],
      ['sources',{permission:'read',run:async params=>{
        noParams(params);
        const rows = await reader`select s.id,s.operator,s.enabled,s.frequency_seconds,s.config_revision::text,s.last_success_at,s.last_error_code,s.next_due_at,s.consecutive_failures,
          (select count(*)::int from ${reader(config.database.schema)}.material_inbox i join ${reader(config.database.schema)}.raw_pages p on p.id=i.page_id where p.source_id=s.id and not i.processed) as pending_items,
          (select json_build_object('coverage',p.coverage,'oldestPublishedAt',p.oldest_published_at,'newestPublishedAt',p.newest_published_at,'acquiredAt',p.acquired_at,'gap',p.gap)
            from ${reader(config.database.schema)}.raw_pages p where p.source_id=s.id order by p.acquired_at desc limit 1) as latest_snapshot
          from ${reader(config.database.schema)}.sources s order by s.id limit 100`;
        return JSON.parse(JSON.stringify([...rows])) as postgres.JSONValue;
      }}],
      ['source.configure',{permission:'control',run:async(params,id,signal)=>{
        signal.throwIfAborted();
        const result=await configureSource(controller,config.database.schema,current,id,params,config.collection.frequencySeconds);
        const [source]=await controller`select enabled from ${controller(config.database.schema)}.sources where id=${String(params.sourceId)}`;
        if(source&&!source.enabled)sourceControllers.get(String(params.sourceId))?.abort();
        return result;
      }}],
      ['channels',{permission:'read',run:params=>channelsAt(reader,config.database.schema,params)}],
      ['brief.list',{permission:'read',run:params=>briefList(reader,config.database.schema,params)}],
      ['brief.get',{permission:'read',run:params=>briefGet(reader,config.database.schema,params)}],
      ['brief.export',{permission:'read',run:params=>briefExport(reader,config.database.schema,params)}],
      ['brief.create',{permission:'control',run:(params,id,signal)=>createBriefRequest(controller,config.database.schema,current,id,params,signal)}],
      ['research.evidence',{permission:'read',run:(params,_id,signal)=>researchManifestChunk(reader,config.database.schema,params,signal)}],
      ['research.original',{permission:'read',run:(params,_id,signal)=>researchOriginal(reader,config.database.schema,params,signal)}],
      ['events.list',{permission:'read',run:params=>eventsList(reader,config.database.schema,params)}],
      ['event.detail',{permission:'read',run:(params,_id,signal)=>eventDetail(reader,config.database.schema,params,signal)}],
      ['channel.configure',{permission:'control',run:async(params,id,signal)=>{
        signal.throwIfAborted();return configureChannelRequest(controller,config.database.schema,current,id,params);
      }}],
      ['event.correct',{permission:'control',run:async(params,id,signal)=>{
        if(Object.keys(params).some(k=>!['reason','change'].includes(k))||typeof params.reason!=='string'||!params.change||typeof params.change!=='object'||Array.isArray(params.change))throw Error('hot_event_correction_invalid');
        signal.throwIfAborted();return correctEvent(controller,config.database.schema,current,id,params.reason,params.change as unknown as Correction) as Promise<postgres.JSONValue>;
      }}],
      ['tasks',{permission:'read',run:async params=>{
        noParams(params);
        const rows = await reader`select input_key,job_id,attempt,state,lease_until,generation from ${reader(config.database.schema)}.job_claims order by input_key limit 100`;
        return JSON.parse(JSON.stringify([...rows])) as postgres.JSONValue;
      }}]
    ]);
    transport = await startTransport({ port:input.port,identity:current,
      controllerToken:input.controllerToken,readerToken:input.readerToken,
      secrets:[input.workerPassword,input.controllerPassword],handlers,
      guard:async()=>{
        const live = await reader`select singleton from ${reader(config.database.schema)}.runtime_identity where singleton
          and instance_id=${current.instanceId} and mode=${current.mode} and generation=${current.generation}
          and not paused and owner_until>clock_timestamp()`;
        if(live.length!==1) throw Error('hot_owner_stale');
      } });
    workerState='running';
    const queue=boss;
    workerTask=runWorker({db,controllerDb:controller,boss:queue,schema:config.database.schema,owner:current,config,
      handlers:{...collectionHandlers(db,queue,config.database.schema,current,config,fetch,sourceControllers),
        ...(groupingModel?{'hot.process':processingHandler(db,config.database.schema,current,groupingModel)}:{})},signal:workerStop.signal,
      heartbeat:async()=>{
        await heartbeatRuntime(controller,config.database.schema,current,input.controllerToken);
        await scheduleCollection(db,queue,config.database.schema,current,config);
        await scheduleProcessing(db,queue,config.database.schema,current,Boolean(groupingModel)&&modelCapability?.state!=='blocked_model');
        await evaluateChannelRules(db,config.database.schema,current);
      }}).catch(()=>{
        workerState='failed';logEvent('worker_stopped');
        queueMicrotask(()=>{void close().catch(()=>logEvent('worker_stopped'));});
      });
    return { owner:current,port:transport.port,close };
  } catch {
    await close();
    throw Error('hot_service_start_failed');
  }
}
