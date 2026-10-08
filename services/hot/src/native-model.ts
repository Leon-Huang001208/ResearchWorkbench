/** Normal worker activation binds an existing authorization; never creates/reset quotas. */
import {readFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import type postgres from 'postgres';
import type {HotConfig} from './config.ts';
import type {RuntimeOwner} from './control.ts';
import {reserveModel,markModelDispatch,markModelUnknown,saveModelReceipt,cancelUnsentModel,lookupModel} from './model-budget.ts';
import {createDshGrouping} from './dsh-grouping.ts';
import type {TextLedger,TextTariff} from './dsh-text.ts';
import type {GroupingModel} from './processing.ts';
import type {createNativeDsh} from './native-dsh.mjs';
import {sha256} from './material.ts';
import {logEvent} from './log.ts';

export type NativeModelBootstrap=Parameters<typeof createNativeDsh>[0];
type Context=Awaited<ReturnType<typeof createNativeDsh>>;
export interface ModelCapability {state:'ready'|'blocked_model';code:string|null;groupingModel?:GroupingModel;close:()=>Promise<void>}
const empty=(code:string):ModelCapability=>({state:'blocked_model',code,close:async()=>{}});
export async function loadNativeModel(db:postgres.Sql,schema:string,owner:RuntimeOwner,config:HotConfig,
  bootstrap:NativeModelBootstrap|undefined,
  createContext:(input:NativeModelBootstrap)=>Promise<Context>=async input=>(await import('./native-dsh.mjs')).createNativeDsh(input),
  today:string|(()=>string)=()=>new Intl.DateTimeFormat('en-CA',{timeZone:config.timezone,year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date())):Promise<ModelCapability>{
  const day=typeof today==='function'?today:()=>today;
  if(!config.model.enabled)return empty('hot_model_disabled');
  if(owner.mode!=='native'||process.platform!=='darwin')return empty('hot_dsh_native_platform_required');
  if(!bootstrap)return empty('hot_model_bootstrap_missing');
  let context:Context|undefined;
  try{
    // Existing DB policy is the authorization. Settings alone cannot authorize or refund calls.
    const [policy]=await db`select * from ${db(schema)}.model_budgets where scope_id=${config.model.scopeId}`;
    if(!policy||!/^[a-f0-9]{64}$/.test(policy.authorization_hash)||policy.paused||policy.max_calls<=0||
      Number(policy.max_tokens)<=0||Number(policy.max_cost_micros)<=0||
      !Number.isInteger(policy.daily_max_calls)||policy.daily_max_calls<=0||
      !Number.isSafeInteger(Number(policy.daily_max_tokens))||Number(policy.daily_max_tokens)<=0||
      !Number.isSafeInteger(Number(policy.daily_max_cost_micros))||Number(policy.daily_max_cost_micros)<=0)
      throw Error('hot_model_authorization_missing');
    if(policy.daily_max_calls>config.budget.maxCallsPerDay||Number(policy.daily_max_tokens)>config.budget.maxTokensPerDay||
      Number(policy.daily_max_cost_micros)>Math.round(config.budget.maxCostPerDay*1000000)||policy.quota_timezone!==config.timezone)
      throw Error('hot_model_budget_settings_conflict');
    const verifiedDay=day();
    if(!/^\d{4}-\d{2}-\d{2}$/.test(verifiedDay))throw Error('hot_model_pricing_refresh_required');
    let bytes:Buffer;
    try{bytes=await readFile(resolve(import.meta.dirname,`../pricing.deepseek.${verifiedDay}.json`));}
    catch{throw Error('hot_model_pricing_refresh_required');}
    const pricing=JSON.parse(bytes.toString('utf8'));
    if(pricing.verifiedOn!==day()||pricing.provider!=='deepseek-official'||pricing.requestedModel!=='deepseek-v4-flash'||
      pricing.currency!=='USD')throw Error('hot_model_pricing_refresh_required');
    context=await createContext(bootstrap);
    const models=await context.runtime.listModels(pricing.provider);
    if(!models.some(model=>model.id===pricing.requestedModel))throw Error('hot_model_catalog_missing');
    const pricingGuard=()=>{if(day()!==pricing.verifiedOn)throw Error('hot_dsh_pricing_refresh_required');};
    const legacyTariffHashes=await Promise.all(['2026-10-08','2026-10-09'].map(async date=>sha256(await readFile(resolve(import.meta.dirname,`../pricing.deepseek.${date}.json`)))));
    const ledger:TextLedger={lookup:spec=>lookupModel(db,schema,spec),reserve:spec=>{pricingGuard();return reserveModel(db,schema,owner,config.model.scopeId,spec);},
      dispatch:t=>{pricingGuard();return markModelDispatch(db,schema,owner,t);},unknown:t=>markModelUnknown(db,schema,t),
      save:(t,r,u)=>saveModelReceipt(db,schema,t,r,u),cancelUnsent:t=>cancelUnsentModel(db,schema,owner,t.id)};
    const tariff:TextTariff={...pricing,versionHash:sha256(bytes)};
    const active=context;
    const grouping=createDshGrouping(active.runtime,ledger,tariff,active.safeOutput,
      {provider:pricing.provider,model:pricing.requestedModel,cacheIdentity:'input-v2',legacyTariffHashes});
    logEvent('model_ready');
    return {get state(){return day()===pricing.verifiedOn?'ready':'blocked_model';},
      get code(){return day()===pricing.verifiedOn?null:'hot_model_pricing_refresh_required';},
      groupingModel:{run(packet,signal){pricingGuard();return grouping.run(packet,signal);}},close:()=>active.close()};
  }catch(error){
    if(context){try{await context.close();}catch{logEvent('model_blocked');}}
    logEvent('model_blocked');
    return empty(error instanceof Error&&/^hot_[a-z_]+$/.test(error.message)?error.message:'hot_model_unavailable');
  }
}
