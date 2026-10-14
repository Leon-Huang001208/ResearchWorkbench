import {test} from 'node:test';
import assert from 'node:assert/strict';
import {loadNativeModel} from '../src/native-model.ts';
import {parseConfig} from '../src/config.ts';

const owner={instanceId:'00000000-0000-0000-0000-000000000001',mode:'native' as const,generation:'1'};
const settings=parseConfig({model:{enabled:true,scopeId:'authorized'},budget:{maxCallsPerDay:20,maxTokensPerDay:20000,maxCostPerDay:1}});
const bootstrap={source:'/trusted',credentials:{python:'/python',bridge:'/bridge',dataHome:'/home'}};
const policy={authorization_hash:'a'.repeat(64),paused:false,max_calls:20,max_tokens:'20000',max_cost_micros:'1000000',
  daily_max_calls:20,daily_max_tokens:'20000',daily_max_cost_micros:'1000000',quota_timezone:'Asia/Shanghai'};
function database(value:unknown){
  let reads=0;const db:any=(query:unknown,..._args:unknown[])=>{if(Array.isArray(query)){reads++;return Promise.resolve(value?[value]:[]);}return 'schema';};
  return {db,reads:()=>reads};
}

test('disabled and unsupported mode do not query policy or initialize DSH',async()=>{
  const {db,reads}=database(null);let contexts=0;
  const factory=async()=>{contexts++;throw Error('must not initialize');};
  assert.equal((await loadNativeModel(db,'hot',owner,parseConfig({}),bootstrap,factory)).code,'hot_model_disabled');
  assert.equal((await loadNativeModel(db,'hot',{...owner,mode:'docker'},settings,bootstrap,factory)).code,'hot_dsh_native_platform_required');
  assert.equal(reads(),0);assert.equal(contexts,0);
});

test('settings cannot create authorization or silently exceed its daily cap',async()=>{
  if(process.platform!=='darwin')return;
  let contexts=0;const factory=async()=>{contexts++;throw Error('must not initialize');};
  const missing=database(null);
  assert.equal((await loadNativeModel(missing.db,'hot',owner,settings,bootstrap,factory)).code,'hot_model_authorization_missing');
  assert.equal(missing.reads(),1);
  const existing=database(policy);
  const smaller=parseConfig({model:{enabled:true},budget:{maxCallsPerDay:1}});
  assert.equal((await loadNativeModel(existing.db,'hot',owner,smaller,bootstrap,factory)).code,'hot_model_budget_settings_conflict');
  assert.equal(contexts,0);
});

test('stale tariff is blocked before model context and does not reset policy',async()=>{
  if(process.platform!=='darwin')return;
  const {db,reads}=database(policy);let contexts=0;
  const result=await loadNativeModel(db,'hot',owner,settings,bootstrap,async()=>{contexts++;throw Error('must not initialize');},'2026-10-10');
  assert.equal(result.code,'hot_model_pricing_refresh_required');assert.equal(reads(),1);assert.equal(contexts,0);
});

test('unconfigured credential error disables the paid handler without ledger writes',async()=>{
  if(process.platform!=='darwin')return;
  const {db,reads}=database(policy);
  const result=await loadNativeModel(db,'hot',owner,settings,bootstrap,async()=>{throw Error('hot_dsh_model_unconfigured');},'2026-10-08');
  assert.equal(result.state,'blocked_model');assert.equal(result.code,'hot_dsh_model_unconfigured');
  assert.equal(result.groupingModel,undefined);assert.equal(reads(),1);
});

test('ready context is closed by owner and catalog rejection closes partial initialization',async()=>{
  if(process.platform!=='darwin')return;
  const {db,reads}=database(policy);let closed=0,calls=0;
  const context:any={runtime:{listModels:async()=>[{id:'deepseek-v4-flash'}],prepareCall:()=>{calls++;throw Error('not expected');}},safeOutput:()=>true,close:async()=>{closed++;}};
  const active=await loadNativeModel(db,'hot',owner,settings,bootstrap,async()=>context,'2026-10-08');
  assert.equal(active.state,'ready');assert.ok(active.groupingModel);assert.equal(calls,0);assert.equal(reads(),1);
  await active.close();assert.equal(closed,1);
  context.runtime.listModels=async()=>[];
  const rejected=await loadNativeModel(db,'hot',owner,settings,bootstrap,async()=>context,'2026-10-08');
  assert.equal(rejected.code,'hot_model_catalog_missing');assert.equal(closed,2);assert.equal(calls,0);
});

test('running worker becomes blocked across midnight before preparation or reservation',async()=>{
  if(process.platform!=='darwin')return;
  const {db,reads}=database(policy);let day='2026-10-08',prepared=0;
  const context:any={runtime:{listModels:async()=>[{id:'deepseek-v4-flash'}],prepareCall:()=>{prepared++;throw Error('must not prepare');}},safeOutput:()=>true,close:async()=>{}};
  const active=await loadNativeModel(db,'hot',owner,settings,bootstrap,async()=>context,()=>day);
  assert.equal(active.state,'ready');day='2026-10-09';
  assert.equal(active.state,'blocked_model');assert.equal(active.code,'hot_model_pricing_refresh_required');
  assert.throws(()=>active.groupingModel!.run({} as any,new AbortController().signal),/hot_dsh_pricing_refresh_required/);
  assert.equal(prepared,0);assert.equal(reads(),1);await active.close();
});
