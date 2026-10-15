/** Read-only frozen originals for a genuine research handoff; no session or model execution. */
import type postgres from 'postgres';
import {briefGet} from './brief-control.ts';
import {canonicalGroupingInput} from './processing.ts';
import {sha256,identityKeyForUrl} from './material.ts';
import {schemaName} from './config.ts';
import {logEvent} from './log.ts';

type Sql=ReturnType<typeof postgres>;
type Params=Record<string,postgres.JSONValue>;
const UUID=/^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/i;
const MAX_TOTAL_BYTES=32*1024*1024;
const json=(value:unknown)=>JSON.parse(JSON.stringify(value)) as postgres.JSONValue;
function record(value:unknown):Record<string,any>{
  if(!value||typeof value!=='object'||Array.isArray(value))throw Error('hot_research_evidence_invalid');
  return value as Record<string,any>;
}
export function parseEvidenceSelection(params:Params){
  if(Object.keys(params).some(k=>!['briefId','version','materialIds'].includes(k))||typeof params.briefId!=='string'||!UUID.test(params.briefId)||
    typeof params.version!=='number'||!Number.isSafeInteger(params.version)||params.version<1||params.version>1000000||
    !Array.isArray(params.materialIds)||params.materialIds.length<1||params.materialIds.length>20||
    params.materialIds.some(id=>typeof id!=='string'||!UUID.test(id)))throw Error('hot_research_selection_invalid');
  const materialIds=(params.materialIds as string[]).map(id=>id.toLowerCase()).sort();
  if(new Set(materialIds).size!==materialIds.length)throw Error('hot_research_selection_invalid');
  return {briefId:params.briefId.toLowerCase(),version:params.version,materialIds};
}
export function evidenceChunk(bytes:Buffer,offset:unknown){
  if(typeof offset!=='number'||!Number.isSafeInteger(offset)||offset<0||offset>bytes.length)throw Error('hot_research_offset_invalid');
  const part=bytes.subarray(offset,offset+32768),end=offset+part.length;
  return {offset,totalBytes:bytes.length,contentHash:sha256(bytes),dataBase64:part.toString('base64'),nextOffset:end<bytes.length?end:null};
}

async function frozenObjects(db:Sql,schema:string,params:Params,signal?:AbortSignal){
  schemaName(schema);const selection=parseEvidenceSelection(params);
  return db.begin('isolation level repeatable read read only',async tx=>{
    signal?.throwIfAborted();const reader=tx as unknown as Sql;
    const [identity]=await reader`select instance_id from ${reader(schema)}.runtime_identity where singleton`;
    if(!identity)throw Error('hot_research_instance_invalid');
    const saved=record(await briefGet(reader,schema,{briefId:selection.briefId,version:selection.version}));
    const context=record(saved.payload),reports=new Map<string,Record<string,any>>();
    if(!Array.isArray(context.events)||typeof context.cutoff!=='string')throw Error('hot_research_evidence_invalid');
    for(const event of context.events){
      if(!Array.isArray(record(event).reports))throw Error('hot_research_evidence_invalid');
      for(const value of event.reports){
        const report=record(value);if(typeof report.materialId!=='string')throw Error('hot_research_evidence_invalid');
        const previous=reports.get(report.materialId);
        if(previous&&(previous.revision!==report.revision||previous.contentHash!==report.contentHash))throw Error('hot_research_evidence_conflict');
        reports.set(report.materialId,report);
      }
    }
    const originals=new Map<string,Buffer>(),objects:Record<string,unknown>[]=[],materials:Record<string,unknown>[]=[];
    let totalBytes=0;
    function add(key:string,filename:string,format:string,bytes:Buffer){
      if(originals.has(key))return;
      totalBytes+=bytes.length;
      if(bytes.length>8*1024*1024||totalBytes>MAX_TOTAL_BYTES)throw Error('hot_research_evidence_limit');
      originals.set(key,bytes);objects.push({key,filename,format,bytes:bytes.length,contentHash:sha256(bytes)});
    }
    for(const id of selection.materialIds){
      signal?.throwIfAborted();const expected=reports.get(id);
      if(!expected||!Number.isSafeInteger(expected.revision)||expected.revision<1)throw Error('hot_research_material_not_selected');
      const [row]=await reader`select m.id,m.identity,m.original_url,m.first_seen_at,
        v.revision,v.content_hash,v.title,v.excerpt,v.acquired_at,v.published_at,v.published_raw,
        v.source_updated_at,v.source_updated_raw,v.state,v.raw_page_id,
        p.source_id,p.body,p.body_hash,p.acquired_at as raw_acquired_at,p.metadata,p.coverage,p.gap,
        p.oldest_published_at,p.newest_published_at,p.parsed_count
        from ${reader(schema)}.materials m join ${reader(schema)}.material_versions v on v.material_id=m.id
        join ${reader(schema)}.raw_pages p on p.id=v.raw_page_id
        where m.id=${id} and v.revision=${expected.revision} and v.acquired_at<=${context.cutoff} and p.acquired_at<=${context.cutoff}`;
      if(!row||row.content_hash!==expected.contentHash||row.original_url!==expected.url||row.state!==expected.state||
        identityKeyForUrl(row.original_url)!==row.identity)throw Error('hot_research_evidence_changed');
      const raw=Buffer.from(row.body);
      if(sha256(raw)!==row.body_hash)throw Error('hot_research_original_integrity_invalid');
      const rawKey='raw:'+row.raw_page_id,materialKey='material:'+id+':'+row.revision;
      const complete=json({schemaVersion:1,materialId:id,identity:row.identity,originalUrl:row.original_url,firstAcquiredAt:row.first_seen_at,
        revision:row.revision,contentHash:row.content_hash,title:row.title,excerpt:row.excerpt,state:row.state,
        acquiredAt:row.acquired_at,publishedAt:row.published_at,publishedRaw:row.published_raw,
        sourceUpdatedAt:row.source_updated_at,sourceUpdatedRaw:row.source_updated_raw,sources:expected.sources,
        raw:{key:rawKey,pageId:row.raw_page_id,sourceId:row.source_id,contentHash:row.body_hash,acquiredAt:row.raw_acquired_at,
          metadata:row.metadata,coverage:row.coverage,gap:row.gap,oldestPublishedAt:row.oldest_published_at,
          newestPublishedAt:row.newest_published_at,parsedCount:row.parsed_count}});
      add(materialKey,`material-${id}-r${row.revision}.json`,'application/json',Buffer.from(canonicalGroupingInput(complete)));
      add(rawKey,`raw-${row.raw_page_id}.bin`,'application/octet-stream',raw);
      materials.push({materialId:id,revision:row.revision,contentHash:row.content_hash,normalizedObject:materialKey,rawObject:rawKey});
    }
    const manifest=json({schemaVersion:1,instanceId:identity.instance_id,...selection,briefContentHash:saved.contentHash,cutoff:context.cutoff,timezone:context.timezone,
      briefContext:context,materials,objects,totalBytes,limitations:[
        '完整保存的是已取得的材料版本和来源响应，RSS响应不等于原链接网页全文。',
        '原始响应可能包含同页其他条目；研究选材仅为清单中的材料，不扩大事件或频道覆盖。',
        '这一步不创建研究会话、调用模型或对外发送。']});
    if(Buffer.byteLength(canonicalGroupingInput(manifest))>700000)throw Error('hot_research_manifest_limit');
    signal?.throwIfAborted();return {manifest,manifestHash:sha256(canonicalGroupingInput(manifest)),originals};
  });
}
export async function researchEvidence(db:Sql,schema:string,params:Params,signal?:AbortSignal){
  try{
    const result=await frozenObjects(db,schema,params,signal);logEvent('research_evidence_frozen',result.originals.size);
    return json({manifest:result.manifest,manifestHash:result.manifestHash});
  }catch(error){logEvent('research_evidence_failed');
    if(error instanceof Error&&/^hot_[a-z_]+$/.test(error.message))throw error;
    if(signal?.aborted)throw Error('hot_research_cancelled');throw Error('hot_research_evidence_failed');}
}
/** Wire form preserves producer-canonical JSON bytes, including floating-point spellings. */
export async function researchManifestChunk(db:Sql,schema:string,params:Params,signal?:AbortSignal){
  try{
    if(Object.keys(params).some(k=>!['briefId','version','materialIds','offset','manifestHash'].includes(k)))throw Error('hot_research_selection_invalid');
    const offset=params.offset??0;
    if(typeof offset!=='number'||!Number.isSafeInteger(offset)||offset<0||offset>700000||
      (offset>0&&(typeof params.manifestHash!=='string'||!/^[a-f0-9]{64}$/.test(params.manifestHash))))throw Error('hot_research_offset_invalid');
    const result=await frozenObjects(db,schema,{briefId:params.briefId,version:params.version,materialIds:params.materialIds},signal);
    if(params.manifestHash!==undefined&&params.manifestHash!==result.manifestHash)throw Error('hot_research_manifest_changed');
    const bytes=Buffer.from(canonicalGroupingInput(result.manifest));signal?.throwIfAborted();
    return json({manifestHash:result.manifestHash,...evidenceChunk(bytes,offset)});
  }catch(error){logEvent('research_evidence_failed');
    if(error instanceof Error&&/^hot_[a-z_]+$/.test(error.message))throw error;
    if(signal?.aborted)throw Error('hot_research_cancelled');throw Error('hot_research_evidence_failed');}
}
export async function researchOriginal(db:Sql,schema:string,params:Params,signal?:AbortSignal){
  try{
    if(Object.keys(params).some(k=>!['briefId','version','materialIds','objectKey','manifestHash','offset'].includes(k))||
      typeof params.objectKey!=='string'||typeof params.manifestHash!=='string'||!/^[a-f0-9]{64}$/.test(params.manifestHash))throw Error('hot_research_object_invalid');
    const result=await frozenObjects(db,schema,{briefId:params.briefId,version:params.version,materialIds:params.materialIds},signal);
    if(result.manifestHash!==params.manifestHash)throw Error('hot_research_manifest_changed');
    const bytes=result.originals.get(params.objectKey);if(!bytes)throw Error('hot_research_object_not_selected');
    const chunk=evidenceChunk(bytes,params.offset);signal?.throwIfAborted();
    return json({manifestHash:result.manifestHash,objectKey:params.objectKey,...chunk});
  }catch(error){logEvent('research_original_failed');
    if(error instanceof Error&&/^hot_[a-z_]+$/.test(error.message))throw error;
    if(signal?.aborted)throw Error('hot_research_cancelled');throw Error('hot_research_original_failed');}
}
