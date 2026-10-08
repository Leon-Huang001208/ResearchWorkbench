/** Authenticated Host-only source changes. Audits and conditional revisions commit together. */
import type postgres from 'postgres';
import {withOwnerTransaction,type RuntimeOwner} from './control.ts';
import {schemaName} from './config.ts';
import {sha256} from './material.ts';
import {logEvent} from './log.ts';
type Sql=ReturnType<typeof postgres>;
export interface SourceChange {sourceId:string;expectedRevision:string;enabled?:boolean;frequencySeconds?:number|null}
export function sourceChange(input:Record<string,postgres.JSONValue>):SourceChange{
  if(Object.keys(input).some(key=>!['sourceId','expectedRevision','enabled','frequencySeconds'].includes(key))||
    typeof input.sourceId!=='string'||!/^[a-z][a-z0-9_-]{0,47}$/.test(input.sourceId)||
    typeof input.expectedRevision!=='string'||!/^\d{1,18}$/.test(input.expectedRevision))throw Error('hot_source_config_invalid');
  const value:SourceChange={sourceId:input.sourceId,expectedRevision:input.expectedRevision};
  if('enabled'in input){if(typeof input.enabled!=='boolean')throw Error('hot_source_config_invalid');value.enabled=input.enabled;}
  if('frequencySeconds'in input){
    if(input.frequencySeconds!==null&&(typeof input.frequencySeconds!=='number'||!Number.isInteger(input.frequencySeconds)||input.frequencySeconds<60||input.frequencySeconds>86400))throw Error('hot_source_config_invalid');
    value.frequencySeconds=input.frequencySeconds as number|null;
  }
  if(!('enabled'in value)&&!('frequencySeconds'in value))throw Error('hot_source_config_invalid');
  return value;
}
export async function configureSource(db:Sql,schema:string,owner:RuntimeOwner,requestId:string,input:Record<string,postgres.JSONValue>,defaultFrequency=600):Promise<postgres.JSONValue>{
  schemaName(schema);const value=sourceChange(input);
  if(!Number.isInteger(defaultFrequency)||defaultFrequency<60||defaultFrequency>86400)throw Error('hot_source_config_invalid');
  if(!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(requestId))throw Error('hot_source_request_invalid');
  requestId=requestId.toLowerCase();
  const hash=sha256(JSON.stringify(value));
  const result=await withOwnerTransaction(db,schema,owner,async tx=>{
    const [previous]=await tx`select params_hash,after_state from ${tx(schema)}.source_control_requests where request_id=${requestId}`;
    if(previous){if(previous.params_hash!==hash)throw Error('hot_source_request_conflict');return previous.after_state;}
    const [row]=await tx`select id,enabled,frequency_seconds,config_revision from ${tx(schema)}.sources where id=${value.sourceId} for update`;
    if(!row)throw Error('hot_source_unknown');
    if(String(row.config_revision)!==value.expectedRevision)throw Error('hot_source_revision_conflict');
    const before={sourceId:row.id,enabled:row.enabled,frequencySeconds:row.frequency_seconds,revision:String(row.config_revision)};
    const [updated]=await tx`update ${tx(schema)}.sources set enabled=${value.enabled??row.enabled},
      frequency_seconds=${'frequencySeconds'in value?value.frequencySeconds!:row.frequency_seconds},config_revision=config_revision+1,
      next_due_at=case when ${value.enabled===true&&row.enabled===false} then clock_timestamp()
        when ${'frequencySeconds'in value} then greatest(clock_timestamp(),coalesce(last_success_at,clock_timestamp())+
          ${value.frequencySeconds??defaultFrequency}*interval '1 second') else next_due_at end
      where id=${value.sourceId} returning enabled,frequency_seconds,config_revision`;
    const after={sourceId:row.id,enabled:updated.enabled,frequencySeconds:updated.frequency_seconds,
      revision:String(updated.config_revision),requestId};
    await tx`insert into ${tx(schema)}.source_control_requests(request_id,source_id,params_hash,generation,actor,before_state,after_state)
      values(${requestId},${row.id},${hash},${owner.generation},'local_host',${tx.json(before)},${tx.json(after)})`;
    return after;
  });
  logEvent('source_configured');return result;
}
