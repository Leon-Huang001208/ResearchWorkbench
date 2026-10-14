/** Durable grouping inputs and receipt-bound business publication on the sole PG queue. */
import type postgres from 'postgres';
import type {PgBoss} from 'pg-boss';
import {withOwnerTransaction,type RuntimeOwner,type Claim,type Tx} from './control.ts';
import {enqueueTransaction,transactionAdapter,type JobOutput} from './queue.ts';
import {saveAutomaticEventTransaction,type EventSnapshot} from './events.ts';
import {sha256,identityKeyForUrl} from './material.ts';
import {schemaName} from './config.ts';
import {logEvent} from './log.ts';
type Sql=ReturnType<typeof postgres>;
export const GROUP_PROMPT_VERSION='hot-group-v1';
export interface GroupingPacket {
  promptVersion:string;material:{id:string;revision:number;title:string;excerpt:string;url:string;publishedAt:string|null;acquiredAt:string;contentHash:string;partial:boolean};
  candidates:{id:string;revision:number;snapshot:EventSnapshot;reports:{title:string;url:string;publishedAt:string|null}[]}[];candidateLimit:number;candidateSearch:'bounded_all_history';
}
export interface GroupingPart {relation:'same_occurrence'|'direct_followup'|'different_event'|'pending_review';candidateId:string|null;title:string;reason:string}
export interface GroupingDecision {parts:GroupingPart[]}
export interface GroupingModel {run(packet:GroupingPacket,signal:AbortSignal):Promise<{resultKey:string;decision:GroupingDecision}>}
export function groupingSourceReferences(text:string):string[]{
  return [...new Set((text.match(/https?:\/\/[^\s<>"']+/g)??[]).map(url=>identityKeyForUrl(url.replace(/[\])},.;!?。；，]+$/u,''))).filter((key):key is string=>key!==null))].slice(0,20);
}
/** Fail closed for newly introduced camel-case brands; candidate titles are not source evidence. */
export function assertMaterialAnchoredDecision(value:GroupingDecision,packet:GroupingPacket){
  const source=(packet.material.title+' '+packet.material.excerpt).toLowerCase().replace(/[^\p{L}\p{N}]/gu,'');
  for(const part of value.parts){
    const brands=part.title.match(/\b[A-Z][a-z]+(?:[A-Z][A-Za-z]*)+\b/g)??[];
    if(brands.some(brand=>!source.includes(brand.toLowerCase()))){
      throw Error('hot_grouping_output_unreported_entity');
    }
  }
}
export function canonicalGroupingInput(value:unknown):string {
  return stable(value);
}
function stable(value:unknown):string {
  if(Array.isArray(value))return '['+value.map(stable).join(',')+']';
  if(value!==null&&typeof value==='object')return '{'+Object.keys(value).sort().map(key=>JSON.stringify(key)+':'+stable((value as Record<string,unknown>)[key])).join(',')+'}';
  return JSON.stringify(value);
}
function key(id:string,rev:number){return id+':'+rev+':'+GROUP_PROMPT_VERSION;}
function eventId(id:string,part:number){const hash=sha256(id+':'+part);return hash.slice(0,8)+'-'+hash.slice(8,12)+'-5'+hash.slice(13,16)+'-a'+hash.slice(17,20)+'-'+hash.slice(20,32);}
function validateDecision(value:GroupingDecision,packet:GroupingPacket){
  if(!value||Object.keys(value).some(k=>k!=='parts')||!Array.isArray(value.parts)||value.parts.length<1||value.parts.length>5)throw Error('hot_grouping_output_invalid');
  const seen=new Set<string>();
  for(const part of value.parts){
    if(!part||Object.keys(part).some(k=>!['relation','candidateId','title','reason'].includes(k))||!['same_occurrence','direct_followup','different_event','pending_review'].includes(part.relation)||
      typeof part.title!=='string'||!part.title.trim()||part.title.length>500||typeof part.reason!=='string'||!part.reason.trim()||part.reason.length>2000)throw Error('hot_grouping_output_invalid');
    if(part.candidateId!==null&&!packet.candidates.some(c=>c.id===part.candidateId))throw Error('hot_grouping_candidate_invalid');
    if((['same_occurrence','direct_followup'].includes(part.relation)&&part.candidateId===null)||(part.relation==='different_event'&&part.candidateId!==null))throw Error('hot_grouping_candidate_invalid');
    if(part.candidateId){if(seen.has(part.candidateId))throw Error('hot_grouping_output_invalid');seen.add(part.candidateId);}
  }
}
export async function registerProcessing(tx:Tx,schema:string,materialIds:string[]){
  schemaName(schema);
  for(const id of materialIds)await tx`insert into ${tx(schema)}.processing_items(material_id,material_revision,prompt_version)
    select id,current_revision,${GROUP_PROMPT_VERSION} from ${tx(schema)}.materials where id=${id} on conflict do nothing`;
}
export async function appliedGroupingResult(db:Sql,schema:string,id:string,revision:number){
  schemaName(schema);if(!/^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/.test(id)||!Number.isSafeInteger(revision)||revision<1)throw Error('hot_processing_payload_invalid');
  const [result]=await db`select r.result_key,r.decision,r.event_ids,r.material_revision,r.applied_at from ${db(schema)}.processing_results r
    join ${db(schema)}.processing_items i using(material_id,material_revision,prompt_version)
    where r.material_id=${id} and r.material_revision=${revision} and r.prompt_version=${GROUP_PROMPT_VERSION} and i.state='applied'`;
  return result??null;
}
export function processingPriority(owner:RuntimeOwner,materialIds:string[]=[]):number|undefined{
  if(!Array.isArray(materialIds)||materialIds.length>20||materialIds.some(id=>typeof id!=='string'||!/^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/.test(id))||new Set(materialIds).size!==materialIds.length)throw Error('hot_processing_selection_invalid');
  if(!materialIds.length)return undefined;
  const priority=Number(owner.generation);if(!Number.isSafeInteger(priority)||priority<1||priority>2147483647)throw Error('hot_processing_selection_invalid');return priority;
}
export async function scheduleProcessing(db:Sql,boss:PgBoss,schema:string,owner:RuntimeOwner,modelReady:boolean,materialIds:string[]=[]){
  const priority=processingPriority(owner,materialIds);
  if(!modelReady)return 0;
  return withOwnerTransaction(db,schema,owner,async tx=>{
    await tx`update ${tx(schema)}.processing_items i set state='stale',error_code='hot_processing_stale',finished_at=clock_timestamp()
      from ${tx(schema)}.materials m where m.id=i.material_id and m.current_revision<>i.material_revision and i.state in ('pending','ready')
      and (${!materialIds.length} or i.material_id=any(${tx.array(materialIds)}::uuid[]))`;
    if(priority!==undefined){
      // Only reclassify queued selected work after a mode/restart fence. Active attempts remain owned.
      const old=await tx`select j.id from ${tx(schema)}.job j where j.name='hot.process' and j.state in ('created','retry') and j.priority<>${priority}
        and j.data->'payload'->>'materialId'=any(${tx.array(materialIds)}::text[])`;
      if(old.length)await boss.cancel('hot.process',old.map(row=>row.id),{db:transactionAdapter(tx)});
    }
    const rows=await tx`select material_id,material_revision from ${tx(schema)}.processing_items i
      where state in ('pending','ready') and prompt_version=${GROUP_PROMPT_VERSION}
      and (${!materialIds.length} or material_id=any(${tx.array(materialIds)}::uuid[]))
      and not exists(select 1 from ${tx(schema)}.job j where j.name='hot.process' and j.state in ('created','retry','active')
        and j.data->'payload'->>'materialId'=i.material_id::text and (j.data->'payload'->>'revision')::integer=i.material_revision)
      order by created_at,material_id limit 20`;
    for(const row of rows)await enqueueTransaction(boss,tx,'hot.process',key(row.material_id,row.material_revision),{materialId:row.material_id,revision:row.material_revision},priority??0);
    if(priority!==undefined)logEvent('processing_selected',rows.length);
    return rows.length;
  });
}
async function assertClaim(tx:Tx,schema:string,claim:Claim){
  const rows=await tx`select input_key from ${tx(schema)}.job_claims where input_key=${claim.inputKey} and job_id=${claim.jobId}
    and worker_id=${claim.workerId} and lease_token=${claim.leaseToken} and generation=${claim.owner.generation} and state='running' and lease_until>clock_timestamp()`;
  if(!rows.length)throw Error('hot_claim_stale');
}
/** Caller must hold the instance owner transaction; freezes inputs before any paid dispatch. */
export async function prepareGroupingPacket(tx:Tx,schema:string,id:string,rev:number):Promise<GroupingPacket>{
  const [item]=await tx`select packet,packet_hash from ${tx(schema)}.processing_items where material_id=${id} and material_revision=${rev} and prompt_version=${GROUP_PROMPT_VERSION} for update`;
  if(!item)throw Error('hot_processing_unknown');
  const [material]=await tx`select m.current_revision,m.original_url,v.* from ${tx(schema)}.materials m join ${tx(schema)}.material_versions v
    on v.material_id=m.id and v.revision=${rev} where m.id=${id} and v.acquired_at<=clock_timestamp()`;
  if(!material||material.current_revision!==rev)throw Error('hot_processing_stale');
  if(item.packet){if(sha256(stable(item.packet))!==item.packet_hash)throw Error('hot_processing_packet_invalid');return item.packet as GroupingPacket;}
  const terms=[...new Set((material.title as string).toLowerCase().match(/[\p{L}\p{N}]{3,}/gu)??[])].slice(0,20);
  const patterns=terms.map(term=>'%'+term+'%');
  const references=groupingSourceReferences(material.excerpt.slice(0,1500));
  // No recency window: matching old chains and previous associations remain eligible.
  const candidates=await tx`select e.id,e.current_revision revision,v.snapshot,
    (select coalesce(jsonb_agg(report),'[]'::jsonb) from (select mv.title,m.original_url url,mv.published_at as "publishedAt"
      from ${tx(schema)}.event_materials r join ${tx(schema)}.material_versions mv on mv.material_id=r.material_id and mv.revision=r.material_revision
      join ${tx(schema)}.materials m on m.id=r.material_id where r.event_id=e.id and r.event_revision=e.current_revision order by r.material_id limit 3) report) reports
    from ${tx(schema)}.events e
    join ${tx(schema)}.event_versions v on v.event_id=e.id and v.revision=e.current_revision
    where v.snapshot->>'state'='active' and ((v.snapshot->>'title') ilike any(${tx.array(patterns)}::text[])
      or exists(select 1 from ${tx(schema)}.event_materials r join ${tx(schema)}.materials m on m.id=r.material_id
        where r.event_id=e.id and r.event_revision=e.current_revision and m.identity=any(${tx.array(references)}::text[]))
      or exists(select 1 from ${tx(schema)}.event_materials r where r.event_id=e.id and r.event_revision=e.current_revision and r.material_id=${id})
      or exists(select 1 from ${tx(schema)}.event_materials r join ${tx(schema)}.material_versions mv on mv.material_id=r.material_id and mv.revision=r.material_revision
        where r.event_id=e.id and r.event_revision=e.current_revision and (mv.title ilike any(${tx.array(patterns)}::text[]) or mv.excerpt ilike any(${tx.array(patterns)}::text[]))))
    order by case when exists(select 1 from ${tx(schema)}.event_materials r where r.event_id=e.id and r.event_revision=e.current_revision and r.material_id=${id}) then 0
      when exists(select 1 from ${tx(schema)}.event_materials r join ${tx(schema)}.materials m on m.id=r.material_id
        where r.event_id=e.id and r.event_revision=e.current_revision and m.identity=any(${tx.array(references)}::text[])) then 1 else 2 end,e.id limit 20`;
  const packet:GroupingPacket={promptVersion:GROUP_PROMPT_VERSION,material:{id,revision:rev,title:material.title,excerpt:material.excerpt.slice(0,1500),url:material.original_url,
    publishedAt:material.published_at?.toISOString()??null,acquiredAt:material.acquired_at.toISOString(),contentHash:material.content_hash,partial:material.excerpt.length>1500},
    candidates:candidates.map(row=>({id:row.id,revision:row.revision,snapshot:row.snapshot,reports:row.reports})),candidateLimit:20,candidateSearch:'bounded_all_history'};
  await tx`update ${tx(schema)}.processing_items set packet=${tx.json(JSON.parse(JSON.stringify(packet)))},packet_hash=${sha256(stable(packet))},state='ready'
    where material_id=${id} and material_revision=${rev} and prompt_version=${GROUP_PROMPT_VERSION}`;
  return packet;
}
export function processingHandler(db:Sql,schema:string,owner:RuntimeOwner,model:GroupingModel){
  return async(value:postgres.JSONValue,signal:AbortSignal,claim:Claim):Promise<JobOutput>=>{
    const input=value as {materialId:string;revision:number};
    if(!input||Array.isArray(input)||Object.keys(input).some(k=>!['materialId','revision'].includes(k))||
      !/^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/.test(input.materialId)||!Number.isSafeInteger(input.revision)||input.revision<1||
      claim.inputKey!=='hot.process:'+key(input.materialId,input.revision))throw Error('hot_processing_payload_invalid');
    const packet=await withOwnerTransaction(db,schema,owner,async tx=>{await assertClaim(tx,schema,claim);signal.throwIfAborted();return prepareGroupingPacket(tx,schema,input.materialId,input.revision);});
    let output:Awaited<ReturnType<GroupingModel['run']>>;
    try{
      output=await model.run(packet,signal);validateDecision(output.decision,packet);assertMaterialAnchoredDecision(output.decision,packet);if(!/^[a-f0-9]{64}$/.test(output.resultKey))throw Error('hot_grouping_output_invalid');
      const [receipt]=await db`select r.response from ${db(schema)}.model_results m join ${db(schema)}.model_receipts r on r.attempt_id=m.attempt_id where m.result_key=${output.resultKey}`;
      let decision:unknown;try{decision=JSON.parse(receipt?.response?.text);}catch{throw Error('hot_grouping_receipt_invalid');}
      if(receipt.response.rejected||stable(decision)!==stable(output.decision))throw Error('hot_grouping_receipt_invalid');
      for(const part of output.decision.parts){
        const candidate=packet.candidates.find(c=>c.id===part.candidateId);
        if(part.relation==='same_occurrence'&&(candidate!.snapshot.manual.excluded.includes(input.materialId)||
          candidate!.snapshot.manual.protected.some(ref=>ref.id===input.materialId&&ref.revision!==input.revision)))throw Error('hot_event_manual_conflict');
      }
    }
    catch(error){
      const code=error instanceof Error&&/^hot_[a-z_]+$/.test(error.message)?error.message:'hot_grouping_outcome_unknown';
      const state=code==='hot_dsh_pricing_refresh_required'?'ready':code.includes('budget')?'blocked_budget':['output','candidate','receipt','manual'].some(s=>code.includes(s))?'rejected':'outcome_unknown';
      await withOwnerTransaction(db,schema,owner,async tx=>{await assertClaim(tx,schema,claim);
        await tx`update ${tx(schema)}.processing_items set state=${state},error_code=${code} where material_id=${input.materialId} and material_revision=${input.revision} and prompt_version=${GROUP_PROMPT_VERSION}`;});
      logEvent('processing_failed');throw Error(code);
    }
    const result={materialId:input.materialId,revision:input.revision,state:'applied'};
    return {result,commit:async tx=>{
      const [head]=await tx`select current_revision from ${tx(schema)}.materials where id=${input.materialId}`;
      let stale=head?.current_revision!==input.revision;
      for(const part of output.decision.parts){const candidate=packet.candidates.find(c=>c.id===part.candidateId);
        if(candidate){const [live]=await tx`select current_revision from ${tx(schema)}.events where id=${candidate.id}`;stale ||= live?.current_revision!==candidate.revision;}}
      if(stale){
        result.state='stale';
        await tx`update ${tx(schema)}.processing_items set state='stale',result_key=${output.resultKey},finished_at=clock_timestamp(),error_code='hot_processing_stale'
          where material_id=${input.materialId} and material_revision=${input.revision} and prompt_version=${GROUP_PROMPT_VERSION}`;
        return;
      }
      try{await tx.savepoint(async tx=>{
      const ids:string[]=[];
      for(const [index,part] of output.decision.parts.entries()){
        const ref={id:input.materialId,revision:input.revision,relation:output.decision.parts.length>1?'composite' as const:'same_occurrence' as const};
        const candidate=packet.candidates.find(c=>c.id===part.candidateId);
        if(part.relation==='same_occurrence'){
          const refs=candidate!.snapshot.materials.filter(ref=>ref.id!==input.materialId);
          await saveAutomaticEventTransaction(tx,schema,candidate!.id,candidate!.revision,{title:candidate!.snapshot.title,materials:[...refs,ref],links:candidate!.snapshot.links});ids.push(candidate!.id);
        }else{
          const id=eventId(key(input.materialId,input.revision),index);
          await saveAutomaticEventTransaction(tx,schema,id,0,{title:part.title,materials:[ref],links:candidate?[{id:candidate.id,relation:part.relation==='direct_followup'?'direct_followup':'pending_review'}]:[]});ids.push(id);
        }
      }
      await tx`insert into ${tx(schema)}.processing_results(material_id,material_revision,prompt_version,result_key,decision,event_ids)
        values(${input.materialId},${input.revision},${GROUP_PROMPT_VERSION},${output.resultKey},${tx.json(JSON.parse(JSON.stringify(output.decision)))},${tx.array(ids)}::uuid[])`;
      await tx`update ${tx(schema)}.processing_items set state='applied',result_key=${output.resultKey},finished_at=clock_timestamp(),error_code=null
        where material_id=${input.materialId} and material_revision=${input.revision} and prompt_version=${GROUP_PROMPT_VERSION}`;
      logEvent('processing_applied',ids.length);
      });}catch(error){
        if(!(error instanceof Error)||!/^hot_(event|grouping)_[a-z_]+$/.test(error.message))throw error;
        result.state='rejected';
        await tx`update ${tx(schema)}.processing_items set state='rejected',result_key=${output.resultKey},finished_at=clock_timestamp(),error_code=${error.message}
          where material_id=${input.materialId} and material_revision=${input.revision} and prompt_version=${GROUP_PROMPT_VERSION}`;
        logEvent('processing_failed');
      }
    }};
  };
}
