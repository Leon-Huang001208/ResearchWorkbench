/** Controller-only conditional configuration and request replay; no public SQL. */
import type postgres from 'postgres';
import {withOwnerTransaction,type RuntimeOwner} from './control.ts';
import {configureChannelTransaction,type ChannelConfig} from './events.ts';
import {canonicalGroupingInput} from './processing.ts';
import {sha256} from './material.ts';
type Sql=ReturnType<typeof postgres>;
export async function configureChannelRequest(db:Sql,schema:string,owner:RuntimeOwner,requestId:string,params:Record<string,postgres.JSONValue>){
  if(!/^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/i.test(requestId)||Object.keys(params).some(k=>!['channelId','expectedVersion','config'].includes(k))||
    typeof params.channelId!=='string'||!/^[a-z][a-z0-9_-]{0,47}$/.test(params.channelId)||!Number.isSafeInteger(params.expectedVersion)||Number(params.expectedVersion)<0||
    !params.config||typeof params.config!=='object'||Array.isArray(params.config))throw Error('hot_channel_request_invalid');
  requestId=requestId.toLowerCase();const hash=sha256(canonicalGroupingInput(params));
  const channelId=params.channelId;
  return withOwnerTransaction(db,schema,owner,async tx=>{
    const [permission]=await tx`select has_table_privilege(current_user,${schema+'.channel_control_requests'},'INSERT') allowed`;
    if(!permission.allowed)throw Error('hot_channel_control_denied');
    const [cached]=await tx`select params_hash,after_state from ${tx(schema)}.channel_control_requests where request_id=${requestId}`;
    if(cached){if(cached.params_hash!==hash)throw Error('hot_channel_request_conflict');return cached.after_state;}
    const [previous]=await tx`select c.current_version,cv.config from ${tx(schema)}.channels c left join ${tx(schema)}.channel_versions cv
      on cv.channel_id=c.id and cv.version=c.current_version where c.id=${channelId}`;
    const result=await configureChannelTransaction(tx,schema,channelId,Number(params.expectedVersion),params.config as unknown as ChannelConfig);
    const after={channelId:result.id,version:result.version,config:params.config,requestId};
    await tx`insert into ${tx(schema)}.channel_control_requests(request_id,channel_id,params_hash,actor,before_state,after_state)
      values(${requestId},${channelId},${hash},'local_host',${tx.json(previous?{version:previous.current_version,config:previous.config}:{version:0,config:null})},${tx.json(after)})`;
    return after;
  });
}
