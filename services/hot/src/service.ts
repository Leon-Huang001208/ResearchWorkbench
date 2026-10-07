/** Independently started Hot control/read service; never starts ResearchService or DSH. */
import postgres from 'postgres';
import { parseConfig,poolOptions,assertNodeRuntime } from './config.ts';
import { SCHEMA_VERSION } from './database.ts';
import { activateRuntime,heartbeatRuntime,pauseRuntime } from './control.ts';
import { openQueue } from './queue.ts';
import { checkDatabase } from './health.ts';
import { startTransport,type RpcHandler } from './transport.ts';
import { logEvent } from './log.ts';

export interface ServiceBootstrap {
  config: unknown; port?: number; instanceId: string; mode: 'native' | 'docker';
  workerPassword: string; controllerUser: string; controllerPassword: string;
  controllerToken: string; readerToken: string;
}
export async function startService(input: ServiceBootstrap) {
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
  let timer: ReturnType<typeof setInterval> | undefined;
  let closed = false;
  let heartbeatBusy = false;
  const close = async () => {
    if(closed) return;
    closed = true;
    if(timer) clearInterval(timer);
    let failed = false;
    if(transport) { try { await transport.close(); } catch { failed=true; } }
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
    boss = await openQueue(db,config.database.schema);
    owner = await activateRuntime(controller,config.database.schema,input.instanceId,input.controllerToken,input.mode,300,true);
    const current = owner;
    const noParams = (params: Record<string,postgres.JSONValue>) => { if(Object.keys(params).length) throw Error('hot_rpc_params_invalid'); };
    const handlers = new Map<string,RpcHandler>([
      ['status',{permission:'read',run:async params=>{
        noParams(params);
        const [counts] = await reader`select count(*)::int n from ${reader(config.database.schema)}.sources`;
        return { state:'initialized',worker:'not_configured',model:'not_integrated',schemaVersion:SCHEMA_VERSION,
          mode:current.mode,generation:current.generation,sourceCount:counts.n };
      }}],
      ['sources',{permission:'read',run:async params=>{
        noParams(params);
        const rows = await reader`select id,operator,enabled,last_success_at,last_error_code from ${reader(config.database.schema)}.sources order by id limit 100`;
        return JSON.parse(JSON.stringify([...rows])) as postgres.JSONValue;
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
    timer = setInterval(()=>{
      if(closed || heartbeatBusy) return;
      heartbeatBusy = true;
      void heartbeatRuntime(controller,config.database.schema,current,input.controllerToken)
        .catch(async()=>{ logEvent('worker_stopped'); try { await close(); } catch { logEvent('worker_stopped'); } })
        .finally(()=>{ heartbeatBusy=false; });
    },30_000);
    return { owner:current,port:transport.port,close };
  } catch {
    await close();
    throw Error('hot_service_start_failed');
  }
}
