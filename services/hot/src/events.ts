/** Append-only event/graph/channel evidence. No similarity-based automatic merging. */
import type postgres from 'postgres';
import {randomUUID} from 'node:crypto';
import {withOwnerTransaction,type RuntimeOwner,type Tx} from './control.ts';
import {schemaName} from './config.ts';
import {sha256} from './material.ts';
import {logEvent} from './log.ts';
type Sql=ReturnType<typeof postgres>;
export interface MaterialRef {id:string;revision:number;relation:'same_occurrence'|'composite'}
export interface EventLink {id:string;relation:'direct_followup'|'related'|'pending_review'}
export interface EventProposal {title:string;materials:MaterialRef[];links:EventLink[]}
export interface EventSnapshot extends EventProposal {state:'active'|'merged';canonicalId:string|null;occurredAt:null;effectiveAt:null;
  manual:{title:boolean;protected:MaterialRef[];excluded:string[];channels:string[]|null}}
export interface ChannelRule {id:string;keywords:string[];requireOfficial?:boolean;relevance:number;importance:number}
export interface ChannelConfig {name:string;topics:string[];sourceIds:string[];importanceRules:string[];rules?:ChannelRule[]}
function uuid(value:string){if(!/^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i.test(value))throw Error('hot_event_identity_invalid');}
function revision(value:number){if(!Number.isSafeInteger(value)||value<0||value>1000000)throw Error('hot_event_revision_invalid');}
function text(value:string,max=500){if(typeof value!=='string'||!value.trim()||value.length>max)throw Error('hot_event_text_invalid');}
function refKey(value:MaterialRef){return value.id+':'+value.revision;}
function proposal(value:EventProposal){
  if(Object.keys(value).some(key=>!['title','materials','links','state','canonicalId','occurredAt','effectiveAt','manual'].includes(key)))throw Error('hot_event_proposal_invalid');
  text(value.title);if(!Array.isArray(value.materials)||value.materials.length>200||!Array.isArray(value.links)||value.links.length>50)throw Error('hot_event_proposal_invalid');
  const materials=new Set<string>(),links=new Set<string>();
  for(const ref of value.materials){uuid(ref.id);revision(ref.revision);if(Object.keys(ref).some(key=>!['id','revision','relation'].includes(key))||ref.revision===0||!['same_occurrence','composite'].includes(ref.relation)||materials.has(refKey(ref)))throw Error('hot_event_proposal_invalid');materials.add(refKey(ref));}
  for(const link of value.links){uuid(link.id);if(Object.keys(link).some(key=>!['id','relation'].includes(key))||!['direct_followup','related','pending_review'].includes(link.relation)||links.has(link.id))throw Error('hot_event_proposal_invalid');links.add(link.id);}
}
async function current(tx:Tx,schema:string,id:string){
  uuid(id);const [row]=await tx`select e.current_revision,v.snapshot from ${tx(schema)}.events e join ${tx(schema)}.event_versions v
    on v.event_id=e.id and v.revision=e.current_revision where e.id=${id} for update of e`;
  if(!row)throw Error('hot_event_unknown');return {revision:row.current_revision as number,snapshot:row.snapshot as EventSnapshot};
}
async function rejectCycle(tx:Tx,schema:string,origin:string,target:string){
  let frontier=[target];const visited=new Set<string>();
  for(let depth=0;frontier.length;depth++){
    if(depth>=100)throw Error('hot_event_link_depth');
    if(frontier.includes(origin))throw Error('hot_event_link_cycle');
    frontier.forEach(id=>visited.add(id));if(visited.size>1000)throw Error('hot_event_graph_limit');
    const next=await tx`select (v.snapshot->>'canonicalId')::uuid target_id from ${tx(schema)}.events e
      join ${tx(schema)}.event_versions v on v.event_id=e.id and v.revision=e.current_revision
      where e.id=any(${tx.array(frontier)}::uuid[]) and v.snapshot->>'state'='merged'
      union select l.target_id from ${tx(schema)}.events e join ${tx(schema)}.event_versions v on v.event_id=e.id and v.revision=e.current_revision
        join ${tx(schema)}.event_links l on l.event_id=e.id and l.event_revision=e.current_revision
      where e.id=any(${tx.array(frontier)}::uuid[]) and v.snapshot->>'state'='active' and l.relation='direct_followup'`;
    frontier=[...new Set(next.map(row=>row.target_id as string))].filter(id=>!visited.has(id));
  }
}
async function append(tx:Tx,schema:string,id:string,expected:number,snapshot:EventSnapshot,observedAt?:Date){
  uuid(id);revision(expected);proposal(snapshot);
  if(snapshot.canonicalId)uuid(snapshot.canonicalId);
  const [row]=await tx`select current_revision from ${tx(schema)}.events where id=${id} for update`;
  if(!row||row.current_revision!==expected)throw Error('hot_event_revision_conflict');
  // Only versions already acquired may support this observation.
  for(const ref of snapshot.materials){
    const found=await tx`select material_id from ${tx(schema)}.material_versions where material_id=${ref.id} and revision=${ref.revision} and acquired_at<=clock_timestamp()`;
    if(!found.length)throw Error('hot_event_evidence_unknown');
  }
  for(const link of snapshot.links){
    if(link.id===id)throw Error('hot_event_link_cycle');
    if(link.relation==='direct_followup'){
      await rejectCycle(tx,schema,id,link.id);
    }
  }
  const next=expected+1;
  const [{observed}]=observedAt?[{observed:observedAt}]:await tx`select clock_timestamp() observed`;
  await tx`insert into ${tx(schema)}.event_versions(event_id,revision,snapshot,created_at) values(${id},${next},${tx.json(JSON.parse(JSON.stringify(snapshot)))},${observed})`;
  for(const ref of snapshot.materials)await tx`insert into ${tx(schema)}.event_materials(event_id,event_revision,material_id,material_revision,relation) values(${id},${next},${ref.id},${ref.revision},${ref.relation})`;
  for(const link of snapshot.links)await tx`insert into ${tx(schema)}.event_links(event_id,event_revision,target_id,relation) values(${id},${next},${link.id},${link.relation})`;
  await tx`update ${tx(schema)}.events set current_revision=${next} where id=${id}`;
  return {id,revision:next,snapshot};
}
function fresh(value:EventProposal):EventSnapshot{return {title:value.title,materials:value.materials,links:value.links,state:'active',canonicalId:null,occurredAt:null,effectiveAt:null,manual:{title:false,protected:[],excluded:[],channels:null}};}
export async function saveAutomaticEvent(db:Sql,schema:string,owner:RuntimeOwner,id:string,expected:number,value:EventProposal){
  return withOwnerTransaction(db,schema,owner,tx=>saveAutomaticEventTransaction(tx,schema,id,expected,value));
}
/** Internal commit helper; caller must already hold the owner/claim transaction fence. */
export async function saveAutomaticEventTransaction(tx:Tx,schema:string,id:string,expected:number,value:EventProposal){
  schemaName(schema);uuid(id);revision(expected);proposal(value);
  if(Object.keys(value).some(key=>!['title','materials','links'].includes(key)))throw Error('hot_event_proposal_invalid');
  id=id.toLowerCase();value={title:value.title,materials:value.materials.map(ref=>({...ref,id:ref.id.toLowerCase()})),links:value.links.map(link=>({...link,id:link.id.toLowerCase()}))};proposal(value);
    let snapshot=fresh(value);
    if(expected===0)await tx`insert into ${tx(schema)}.events(id) values(${id}) on conflict do nothing`;
    else{
      const previous=await current(tx,schema,id);
      if(previous.snapshot.state!=='active')throw Error('hot_event_alias_requires_canonical');
      const locks=previous.snapshot.manual;
      if(locks.title&&value.title!==previous.snapshot.title)throw Error('hot_event_manual_conflict');
      if(value.materials.some(ref=>locks.excluded.includes(ref.id))||locks.protected.some(ref=>!value.materials.some(item=>refKey(item)===refKey(ref)&&item.relation===ref.relation)))throw Error('hot_event_manual_conflict');
      snapshot={...snapshot,manual:locks};
    }
    const result=await append(tx,schema,id,expected,snapshot);logEvent('event_saved');return result;
}
export async function configureChannel(db:Sql,schema:string,owner:RuntimeOwner,id:string,expected:number,config:ChannelConfig){
  if(!/^[a-z][a-z0-9_-]{0,47}$/.test(id))throw Error('hot_channel_invalid');revision(expected);text(config.name,100);
  if(Object.keys(config).some(key=>!['name','topics','sourceIds','importanceRules','rules'].includes(key)))throw Error('hot_channel_invalid');
  for(const array of [config.topics,config.sourceIds,config.importanceRules]){if(!Array.isArray(array)||array.length>50)throw Error('hot_channel_invalid');array.forEach(value=>text(value,500));}
  if(config.rules!==undefined){
    if(!Array.isArray(config.rules)||config.rules.length>30)throw Error('hot_channel_rule_invalid');
    const seen=new Set<string>();
    for(const rule of config.rules){
      if(!rule||Object.keys(rule).some(key=>!['id','keywords','requireOfficial','relevance','importance'].includes(key))||
        !/^[a-z][a-z0-9_-]{0,47}$/.test(rule.id)||seen.has(rule.id)||!Array.isArray(rule.keywords)||rule.keywords.length<1||rule.keywords.length>20||
        (rule.requireOfficial!==undefined&&typeof rule.requireOfficial!=='boolean'))throw Error('hot_channel_rule_invalid');
      seen.add(rule.id);rule.keywords.forEach(value=>text(value,80));
      for(const score of [rule.relevance,rule.importance])if(!Number.isInteger(score)||score<0||score>100)throw Error('hot_channel_rule_invalid');
    }
  }
  return withOwnerTransaction(db,schema,owner,async tx=>{
    await tx`insert into ${tx(schema)}.channels(id) values(${id}) on conflict do nothing`;
    const [row]=await tx`select current_version from ${tx(schema)}.channels where id=${id} for update`;
    if(row.current_version!==expected)throw Error('hot_channel_revision_conflict');
    for(const source of config.sourceIds){const found=await tx`select id from ${tx(schema)}.sources where id=${source}`;if(!found.length)throw Error('hot_channel_source_unknown');}
    await tx`insert into ${tx(schema)}.channel_versions(channel_id,version,config) values(${id},${expected+1},${tx.json(JSON.parse(JSON.stringify(config)))})`;
    await tx`update ${tx(schema)}.channels set current_version=${expected+1} where id=${id}`;
    logEvent('channel_configured');return {id,version:expected+1};
  });
}
export type Correction={type:'title';id:string;expected:number;title:string}|{type:'merge';id:string;expected:number;target:string;targetExpected:number}|{type:'split';id:string;expected:number;materialIds:string[];title:string}|{type:'reassign';id:string;expected:number;target:string;targetExpected:number;materialIds:string[]}|{type:'channels';id:string;expected:number;channelIds:string[]};
function canonical(value:unknown):string {
  if(Array.isArray(value))return '['+value.map(canonical).join(',')+']';
  if(value!==null&&typeof value==='object')return '{'+Object.keys(value).sort().map(key=>JSON.stringify(key)+':'+canonical((value as Record<string,unknown>)[key])).join(',')+'}';
  return JSON.stringify(value);
}
function correctionInput(change:Correction):Correction {
  const keys:Record<Correction['type'],string[]>={title:['title'],merge:['target','targetExpected'],split:['materialIds','title'],reassign:['target','targetExpected','materialIds'],channels:['channelIds']};
  if(!keys[change.type]||Object.keys(change).some(key=>!['type','id','expected',...keys[change.type]].includes(key)))throw Error('hot_event_correction_invalid');
  uuid(change.id);revision(change.expected);
  const normalized={...change,id:change.id.toLowerCase()};
  if('target' in normalized){uuid(normalized.target);revision(normalized.targetExpected);normalized.target=normalized.target.toLowerCase();}
  if('materialIds' in normalized){
    if(!Array.isArray(normalized.materialIds)||normalized.materialIds.length===0||normalized.materialIds.length>200)throw Error('hot_event_split_invalid');
    normalized.materialIds=normalized.materialIds.map(id=>{uuid(id);return id.toLowerCase();}).sort();
    if(new Set(normalized.materialIds).size!==normalized.materialIds.length)throw Error('hot_event_split_invalid');
  }
  if('channelIds' in normalized&&Array.isArray(normalized.channelIds))normalized.channelIds=[...normalized.channelIds].sort();
  return normalized;
}
export async function correctEvent(db:Sql,schema:string,owner:RuntimeOwner,requestId:string,reason:string,change:Correction){
  uuid(requestId);requestId=requestId.toLowerCase();text(reason,2000);change=correctionInput(change);
  const digest=sha256(canonical({reason,change}));
  return withOwnerTransaction(db,schema,owner,async tx=>{
    const [permission]=await tx`select has_table_privilege(current_user,${schema+'.event_corrections'},'INSERT') allowed`;
    if(!permission.allowed)throw Error('hot_event_control_denied');
    const [cached]=await tx`select params_hash,after_state from ${tx(schema)}.event_corrections where request_id=${requestId}`;
    if(cached){if(cached.params_hash!==digest)throw Error('hot_event_request_conflict');return cached.after_state;}
    const original=await current(tx,schema,change.id);
    if(original.revision!==change.expected||original.snapshot.state!=='active')throw Error('hot_event_revision_conflict');
    const before:any={source:original},after:any={};
    const [{observed}]=await tx`select clock_timestamp() observed`;
    if(change.type==='title'){
      text(change.title);after.source=await append(tx,schema,change.id,change.expected,{...original.snapshot,title:change.title,manual:{...original.snapshot.manual,title:true}},observed);
    }else if(change.type==='merge'){
      uuid(change.target);if(change.target===change.id)throw Error('hot_event_merge_invalid');
      const target=await current(tx,schema,change.target);before.target=target;
      if(target.revision!==change.targetExpected||target.snapshot.state!=='active')throw Error('hot_event_revision_conflict');
      const refs=[...new Map([...target.snapshot.materials,...original.snapshot.materials].map(ref=>[refKey(ref),ref])).values()];
      after.source=await append(tx,schema,change.id,change.expected,{...original.snapshot,state:'merged',canonicalId:change.target},observed);
      const links=[...new Map([...target.snapshot.links,...original.snapshot.links].filter(link=>![change.id,change.target].includes(link.id)).map(link=>[link.id,link])).values()];
      after.target=await append(tx,schema,change.target,change.targetExpected,{...target.snapshot,materials:refs,links,
        manual:{...target.snapshot.manual,protected:refs,excluded:target.snapshot.manual.excluded.filter(id=>!refs.some(ref=>ref.id===id))}},observed);
    }else if(change.type==='channels'){
      if(!Array.isArray(change.channelIds)||change.channelIds.length>50||new Set(change.channelIds).size!==change.channelIds.length)throw Error('hot_channel_invalid');
      for(const channel of change.channelIds){const found=await tx`select id from ${tx(schema)}.channels where id=${channel}`;if(!found.length)throw Error('hot_channel_unknown');}
      after.source=await append(tx,schema,change.id,change.expected,{...original.snapshot,manual:{...original.snapshot.manual,channels:change.channelIds}},observed);
    }else if(change.type==='split'||change.type==='reassign'){
      const moved=original.snapshot.materials.filter(ref=>change.materialIds.includes(ref.id));
      if(!moved.length||moved.length===original.snapshot.materials.length||change.materialIds.some(id=>!moved.some(ref=>ref.id===id)))throw Error('hot_event_split_invalid');
      if(change.type==='split'){
        text(change.title);const id=randomUUID();await tx`insert into ${tx(schema)}.events(id) values(${id})`;
        after.target=await append(tx,schema,id,0,{...fresh({title:change.title,materials:moved,links:[]}),manual:{title:true,protected:moved,excluded:[],channels:null}},observed);
      }else{
        if(change.target===change.id)throw Error('hot_event_reassign_invalid');
        const target=await current(tx,schema,change.target);before.target=target;
        if(target.revision!==change.targetExpected||target.snapshot.state!=='active')throw Error('hot_event_revision_conflict');
        const refs=[...new Map([...target.snapshot.materials,...moved].map(ref=>[refKey(ref),ref])).values()];
        after.target=await append(tx,schema,change.target,change.targetExpected,{...target.snapshot,materials:refs,
          manual:{...target.snapshot.manual,protected:[...new Map([...target.snapshot.manual.protected,...moved].map(ref=>[refKey(ref),ref])).values()],
            excluded:target.snapshot.manual.excluded.filter(id=>!moved.some(ref=>ref.id===id))}},observed);
      }
      after.source=await append(tx,schema,change.id,change.expected,{...original.snapshot,materials:original.snapshot.materials.filter(ref=>!change.materialIds.includes(ref.id)),
        manual:{...original.snapshot.manual,protected:original.snapshot.manual.protected.filter(ref=>!change.materialIds.includes(ref.id)),excluded:[...new Set([...original.snapshot.manual.excluded,...change.materialIds])]}},observed);
    }else throw Error('hot_event_correction_invalid');
    await tx`insert into ${tx(schema)}.event_corrections(request_id,params_hash,actor,reason,before_state,after_state,created_at)
      values(${requestId},${digest},'local_host',${reason},${tx.json(before)},${tx.json(after)},${observed})`;
    logEvent('event_corrected');return after;
  });
}
export async function eventAt(db:Sql,schema:string,id:string,cutoff:Date):Promise<{id:string;revision:number;snapshot:EventSnapshot}|null>{
  schemaName(schema);uuid(id);if(!Number.isFinite(cutoff.getTime()))throw Error('hot_event_cutoff_invalid');
  id=id.toLowerCase();
  const visited=new Set<string>();
  for(let depth=0;depth<100;depth++){
    if(visited.has(id))throw Error('hot_event_alias_cycle');visited.add(id);
    const [row]=await db`select revision,snapshot from ${db(schema)}.event_versions where event_id=${id} and created_at<=${cutoff} order by revision desc limit 1`;
    if(!row)return null;const snapshot=row.snapshot as EventSnapshot;
    if(snapshot.state==='merged'&&snapshot.canonicalId){id=snapshot.canonicalId;continue;}
    return {id,revision:row.revision,snapshot};
  }
  throw Error('hot_event_alias_depth');
}
export interface ChannelJudgment {relevance:number;importance:number;informationIncrement:number;heat:number;
  evidence:'single_official'|'corroborated'|'unverified'|'contradicted';reason:string;limitations:string[]}
export interface ChannelJudgmentInput {eventId:string;eventRevision:number;channelId:string;channelVersion:number;inputHash:string;
  authority:'rule'|'model'|'human';judgment:ChannelJudgment}
export async function saveChannelJudgment(db:Sql,schema:string,owner:RuntimeOwner,input:ChannelJudgmentInput){
  return withOwnerTransaction(db,schema,owner,tx=>saveChannelJudgmentTransaction(tx,schema,input));
}
/** Internal helper; caller holds the authenticated owner/claim transaction fence. */
export async function saveChannelJudgmentTransaction(tx:Tx,schema:string,input:ChannelJudgmentInput){
  uuid(input.eventId);revision(input.eventRevision);revision(input.channelVersion);
  input={...input,eventId:input.eventId.toLowerCase()};
  if(!/^[a-f0-9]{64}$/.test(input.inputHash)||!['rule','model','human'].includes(input.authority))throw Error('hot_channel_judgment_invalid');
  const j=input.judgment;text(j.reason,2000);
  for(const score of [j.relevance,j.importance,j.informationIncrement,j.heat])if(!Number.isFinite(score)||score<0||score>100)throw Error('hot_channel_judgment_invalid');
  if(!['single_official','corroborated','unverified','contradicted'].includes(j.evidence)||!Array.isArray(j.limitations)||j.limitations.length>30)throw Error('hot_channel_judgment_invalid');j.limitations.forEach(value=>text(value,500));
    if(input.authority==='human'){
      const [permission]=await tx`select has_table_privilege(current_user,${schema+'.event_corrections'},'INSERT') allowed`;
      if(!permission.allowed)throw Error('hot_event_control_denied');
    }
    const event=await current(tx,schema,input.eventId);
    if(event.revision!==input.eventRevision||event.snapshot.state!=='active')throw Error('hot_event_revision_conflict');
    if(input.authority!=='human'&&event.snapshot.manual.channels!==null&&!event.snapshot.manual.channels.includes(input.channelId))throw Error('hot_event_manual_conflict');
    const [channel]=await tx`select current_version from ${tx(schema)}.channels where id=${input.channelId}`;
    if(!channel||channel.current_version!==input.channelVersion)throw Error('hot_channel_revision_conflict');
    if(input.authority!=='human'){
      const human=await tx`select id from ${tx(schema)}.channel_judgments where event_id=${input.eventId} and channel_id=${input.channelId} and authority='human' limit 1`;
      if(human.length)throw Error('hot_event_manual_conflict');
    }
    let modelAttemptId:string|null=null;
    if(input.authority==='model'){
      const [receipt]=await tx`select r.attempt_id,r.response from ${tx(schema)}.model_results m
        join ${tx(schema)}.model_receipts r on r.attempt_id=m.attempt_id where m.result_key=${input.inputHash}`;
      if(!receipt||typeof receipt.response?.text!=='string'||receipt.response.rejected)throw Error('hot_channel_model_receipt_required');
      let result:unknown;try{result=JSON.parse(receipt.response.text);}catch{throw Error('hot_channel_model_receipt_invalid');}
      if(canonical(result)!==canonical(j))throw Error('hot_channel_model_receipt_invalid');
      modelAttemptId=receipt.attempt_id;
    }
    const [prior]=await tx`select id,authority,judgment from ${tx(schema)}.channel_judgments where event_id=${input.eventId} and event_revision=${input.eventRevision}
      and channel_id=${input.channelId} and channel_version=${input.channelVersion} and input_hash=${input.inputHash}`;
    if(prior){if(prior.authority!==input.authority||canonical(prior.judgment)!==canonical(j))throw Error('hot_channel_judgment_conflict');return prior.id;}
    const id=randomUUID();await tx`insert into ${tx(schema)}.channel_judgments(id,event_id,event_revision,channel_id,channel_version,input_hash,authority,judgment,model_attempt_id)
      values(${id},${input.eventId},${input.eventRevision},${input.channelId},${input.channelVersion},${input.inputHash},${input.authority},${tx.json(JSON.parse(JSON.stringify(j)))},${modelAttemptId})`;
    return id;
}
export interface JudgmentProjection {id:string;judgment:ChannelJudgment;authority:'rule'|'model'|'human';event_revision:number;channel_version:number;created_at:Date;
  inherited:boolean;applied_event_revision:number;applied_channel_version:number}
export async function judgmentAt(db:Sql,schema:string,eventId:string,channelId:string,cutoff:Date):Promise<JudgmentProjection|null>{
  const event=await eventAt(db,schema,eventId,cutoff);if(!event)return null;
  if(event.snapshot.manual.channels!==null&&!event.snapshot.manual.channels.includes(channelId))return null;
  const [channel]=await db`select version from ${db(schema)}.channel_versions where channel_id=${channelId} and created_at<=${cutoff} order by version desc limit 1`;
  if(!channel)return null;
  const [human]=await db<Omit<JudgmentProjection,'inherited'|'applied_event_revision'|'applied_channel_version'>[]>`select id,judgment,authority,event_revision,channel_version,created_at from ${db(schema)}.channel_judgments
    where event_id=${event.id} and channel_id=${channelId} and authority='human' and created_at<=${cutoff}
    order by created_at desc,id desc limit 1`;
  if(human)return {...human,inherited:human.event_revision!==event.revision||human.channel_version!==channel.version,
    applied_event_revision:event.revision,applied_channel_version:channel.version};
  const [row]=await db<Omit<JudgmentProjection,'inherited'|'applied_event_revision'|'applied_channel_version'>[]>`select id,judgment,authority,event_revision,channel_version,created_at from ${db(schema)}.channel_judgments
    where event_id=${event.id} and channel_id=${channelId} and event_revision=${event.revision} and channel_version=${channel.version}
    and created_at<=${cutoff} order by case when authority='human' then 0 else 1 end,created_at desc limit 1`;
  return row?{...row,inherited:false,applied_event_revision:event.revision,applied_channel_version:channel.version}:null;
}
