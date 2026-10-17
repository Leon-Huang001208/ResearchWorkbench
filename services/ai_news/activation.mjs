// Explicit private activation record. Presence of a key never grants permission to spend.
import { readPrivate, secret } from './runtime.mjs';
const MODEL_SERVICES = { llm:'LLM', zhipu:'ZHIPU', deepseek:'DEEPSEEK', dashscope:'DASHSCOPE', mimo:'XIAOMI_MIMO', embedding:'EMBEDDING' };
const COLLECTORS = { socialdata:'SOCIALDATA_API_KEY', dajiala:'DAJIALA_KEY', jina:'JINA_API_KEY' };
export function loadActivation(file, now = Date.now()) {
  if (!file) return { collectionEnabled:false, modelCallsEnabled:false, services:{}, environment:{} };
  const input=JSON.parse(readPrivate(file));
  if (input.version!==1 || typeof input.collectionEnabled!=='boolean' || typeof input.modelCallsEnabled!=='boolean' || !input.services || typeof input.services!=='object' || Array.isArray(input.services)) throw new Error('activation_invalid');
  const environment={};
  for (const [service, grant] of Object.entries(input.services)) {
    const prefix=MODEL_SERVICES[service], collectorKey=COLLECTORS[service];
    if (!prefix && !collectorKey) throw new Error('activation_service_invalid');
    if (!grant || typeof grant.approvedBy!=='string' || !grant.approvedBy.trim() || !Number.isFinite(Date.parse(grant.approvedAt)) || Date.parse(grant.approvedAt)>now || !Number.isFinite(Date.parse(grant.expiresAt)) || Date.parse(grant.expiresAt)<=now || Date.parse(grant.expiresAt)<=Date.parse(grant.approvedAt)) throw new Error('activation_authorization_invalid');
    if (!grant.budget || !['perMinute','perHour','perDay'].every(key=>Number.isSafeInteger(grant.budget[key])&&grant.budget[key]>0)) throw new Error('activation_budget_invalid');
    const key=collectorKey ?? `${prefix}_API_KEY`;
    environment[key]=secret(grant.credentialFiles?.[key],8);
    const allowed=prefix ? [`${prefix}_BASE_URL`,...(service==='llm'?['LLM_MODEL','LLM_JSON_MODE','LLM_VISION','LLM_REASONING_TOKENS']:service==='embedding'?['EMBEDDING_MODEL','EMBEDDING_DIMS']:[])] : [`${service.toUpperCase()}_BASE_URL`];
    for(const [name,value] of Object.entries(grant.publicConfig??{})) {
      if(!allowed.includes(name)||typeof value!=='string'||value.includes('\0')||/[\r\n]/.test(value)) throw new Error('activation_public_config_invalid');
      if(name.endsWith('_BASE_URL')) {const u=new URL(value);const host=u.hostname.toLowerCase().replace(/\.$/,'');const localModel=Boolean(prefix)&&u.protocol==='http:'&&['127.0.0.1','[::1]'].includes(host);if((u.protocol!=='https:'&&!localModel)||u.username||u.password||u.search||u.hash||host==='aihot.news'||host.endsWith('.aihot.news'))throw new Error('activation_provider_url_invalid');}
      environment[name]=value;
    }
    if(service==='llm' && (!environment.LLM_BASE_URL||!environment.LLM_MODEL))throw new Error('activation_model_config_missing');
  }
  if(input.modelCallsEnabled&&!input.services.llm)throw new Error('activation_model_authorization_missing');
  return {...input,environment};
}
export function assertPaidAuthorization(service, persistedBudget, file=process.env.RWB_AI_NEWS_ACTIVATION_FILE, now=Date.now(), activeEnvironment=process.env) {
  const record=loadActivation(file,now), grant=record.services[service];
  if(!grant || !(COLLECTORS[service]?record.collectionEnabled:record.modelCallsEnabled))throw new Error('paid_authorization_required');
  const prefix=MODEL_SERVICES[service], collectorKey=COLLECTORS[service];
  const owns=key=>prefix ? key.startsWith(prefix+'_') : key===collectorKey || key.startsWith(service.toUpperCase()+'_');
  for(const key of new Set([...Object.keys(record.environment),...Object.keys(activeEnvironment)].filter(owns))) {
    if(activeEnvironment[key]!==record.environment[key])throw new Error('paid_activation_changed_restart_required');
  }
  if(!persistedBudget || ![['per_minute','perMinute'],['per_hour','perHour'],['per_day','perDay']].every(([db,key])=>Number.isSafeInteger(persistedBudget[db])&&persistedBudget[db]>0&&persistedBudget[db]<=grant.budget[key]))throw new Error('paid_persisted_budget_not_authorized');
}
