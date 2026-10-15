/** Local user's persistent interests. Only authenticated controller writes; GET has no work. */
import type postgres from 'postgres';
import {withOwnerTransaction,type RuntimeOwner} from './control.ts';
import {schemaName} from './config.ts';
import {canonicalGroupingInput} from './processing.ts';
import {sha256} from './material.ts';
import {logEvent} from './log.ts';
type Sql=ReturnType<typeof postgres>;
type Kind='channel'|'event'|'keyword'|'institution'|'asset';
interface FollowConfig {kind:Kind;target:string;name:string;enabled:boolean}
interface FollowRequest {followId:string;expectedVersion:number;config:FollowConfig;reason:string}
const uuid=/^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/i;
function json(value:unknown):postgres.JSONValue{return JSON.parse(JSON.stringify(value));}
function plain(value:unknown):value is Record<string,unknown>{return value!==null&&typeof value==='object'&&!Array.isArray(value)&&Object.getPrototypeOf(value)===Object.prototype;}
function text(value:unknown,max:number):value is string{return typeof value==='string'&&value.trim().length>0&&value.length<=max&&!/[\u0000-\u001f\u007f]/.test(value);}
export function parseFollowRequest(value:unknown):FollowRequest {
  if(!plain(value)||Object.keys(value).some(key=>!['followId','expectedVersion','config','reason'].includes(key))||
    typeof value.followId!=='string'||!uuid.test(value.followId)||!Number.isSafeInteger(value.expectedVersion)||Number(value.expectedVersion)<0||Number(value.expectedVersion)>=1000000||!text(value.reason,1000)||
    !plain(value.config)||Object.keys(value.config).some(key=>!['kind','target','name','enabled'].includes(key)))throw Error('hot_follow_request_invalid');
  const c=value.config;
  if(typeof c.kind!=='string'||!['channel','event','keyword','institution','asset'].includes(c.kind)||!text(c.target,200)||!text(c.name,120)||typeof c.enabled!=='boolean'||
    c.kind==='channel'&&!/^[a-z][a-z0-9_-]{0,47}$/.test(c.target)||c.kind==='event'&&!uuid.test(c.target))throw Error('hot_follow_request_invalid');
  return {followId:value.followId.toLowerCase(),expectedVersion:Number(value.expectedVersion),reason:value.reason,
    config:{kind:c.kind as Kind,target:c.kind==='event'?c.target.toLowerCase():c.target,name:c.name,enabled:c.enabled}};
}
export async function readFollows(db:Sql,schema:string,params:Record<string,postgres.JSONValue>){
  schemaName(schema);if(Object.keys(params).length)throw Error('hot_follow_request_invalid');
  try{
    const [{cutoff}]=await db`select clock_timestamp() cutoff`;
    const rows=await db`select f.id,v.version,v.config,v.created_at from ${db(schema)}.follows f join ${db(schema)}.follow_versions v
      on v.follow_id=f.id and v.version=f.current_version order by v.created_at desc,f.id limit 100`;
    return JSON.parse(JSON.stringify({cutoff,items:rows.map(row=>({followId:row.id,version:row.version,config:row.config,createdAt:row.created_at}))})) as postgres.JSONValue;
  }catch(error){logEvent('follow_failed');if(error instanceof Error&&/^hot_/.test(error.message))throw error;throw Error('hot_follow_read_failed');}
}
export async function configureFollow(db:Sql,schema:string,owner:RuntimeOwner,requestId:string,params:unknown){
  schemaName(schema);if(!uuid.test(requestId))throw Error('hot_follow_request_invalid');requestId=requestId.toLowerCase();
  const value=parseFollowRequest(params),hash=sha256(canonicalGroupingInput(value));
  try{
    const result=await withOwnerTransaction(db,schema,owner,async tx=>{
      const [permission]=await tx`select has_table_privilege(current_user,${schema+'.follow_requests'},'INSERT') allowed`;
      if(!permission.allowed)throw Error('hot_follow_control_denied');
      const [cached]=await tx`select params_hash,after_state from ${tx(schema)}.follow_requests where request_id=${requestId}`;
      if(cached){if(cached.params_hash!==hash)throw Error('hot_follow_request_conflict');return cached.after_state;}
      const [previous]=await tx`select f.id,v.version,v.config from ${tx(schema)}.follows f join ${tx(schema)}.follow_versions v
        on v.follow_id=f.id and v.version=f.current_version where f.id=${value.followId} for update of f`;
      if((previous?.version??0)!==value.expectedVersion)throw Error('hot_follow_version_conflict');
      if(previous&&(previous.config.kind!==value.config.kind||previous.config.target!==value.config.target))throw Error('hot_follow_target_conflict');
      if(!previous){
        const [size]=await tx`select count(*)::int count from ${tx(schema)}.follows`;if(size.count>=100)throw Error('hot_follow_limit');
        const matches=await tx`select id from ${tx(schema)}.follows where kind=${value.config.kind} and target=${value.config.target}`;
        if(matches.length)throw Error('hot_follow_target_conflict');
        if(value.config.kind==='channel'&&!(await tx`select id from ${tx(schema)}.channels where id=${value.config.target}`).length)throw Error('hot_follow_target_invalid');
        if(value.config.kind==='event'&&!(await tx`select id from ${tx(schema)}.events where id=${value.config.target}`).length)throw Error('hot_follow_target_invalid');
        await tx`insert into ${tx(schema)}.follows(id,kind,target,current_version) values(${value.followId},${value.config.kind},${value.config.target},${value.expectedVersion+1})`;
      }
      const [saved]=await tx`insert into ${tx(schema)}.follow_versions(follow_id,version,config) values(${value.followId},${value.expectedVersion+1},${tx.json(json(value.config))}) returning created_at`;
      await tx`update ${tx(schema)}.follows set current_version=${value.expectedVersion+1} where id=${value.followId}`;
      const after={followId:value.followId,version:value.expectedVersion+1,config:value.config,createdAt:saved.created_at.toISOString(),requestId};
      await tx`insert into ${tx(schema)}.follow_requests(request_id,follow_id,params_hash,actor,reason,before_state,after_state)
        values(${requestId},${value.followId},${hash},'local_host',${value.reason},${tx.json(previous?{version:previous.version,config:previous.config}:{version:0,config:null})},${tx.json(json(after))})`;
      return after;
    });logEvent('follow_saved');return result;
  }catch(error){logEvent('follow_failed');if(error instanceof Error&&/^hot_[a-z_]+$/.test(error.message))throw error;throw Error('hot_follow_save_failed');}
}
