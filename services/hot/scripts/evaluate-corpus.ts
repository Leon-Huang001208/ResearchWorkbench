/** Offline source/receipt review. No credentials, PG connection or model sender. */
import {readFile} from 'node:fs/promises';
import {pathToFileURL} from 'node:url';
import {scoreChannel} from '../src/channel-rules.ts';
import {canonicalGroupingInput,type GroupingPacket,type GroupingDecision} from '../src/processing.ts';
import {sha256,identityKeyForUrl} from '../src/material.ts';
import type {ChannelConfig} from '../src/events.ts';
type Score={relevance:number;importance:number;heat:number};
interface Material {material_id:string;revision:number;content_hash:string;title:string;excerpt:string;original_url:string;
  published_at:string|null;acquired_at:string;state:string;source_id:string;operator:string;body_hash:string}
interface Receipt {packet:GroupingPacket;packetHash:string;response:{text:string};responseHash:string;decision:GroupingDecision;expectedRelations:string[];eventIds:string[]}
interface Sample {id:string;split:'development'|'holdout';eventGroups:string[];material:Material;materialSnapshotHash:string;expectedScores:Record<string,Score>;tags:string[];receipt?:Receipt}
interface Reference {id:string;split:'development'|'holdout';eventGroups:string[];expected:string;sourceUrls:string[];modelStatus:'NOT_RUN'}
interface Corpus {version:1;cutoff:string;reviewAuthority:'engineering_source_review';independentLabels:false;blindedHoldout:false;retrospective:true;
  sourceCatalog:{version:1;sources:{id:string;operator:string;official:boolean;url:string}[]};
  channelConfigs:{id:string;version:number;config:ChannelConfig}[];samples:Sample[];referenceCases:Reference[];limitations:string[]}
function reject(code:string):never{throw Error('hot_evaluation_'+code);}
const uuid=(value:unknown)=>typeof value==='string'&&/^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/.test(value);
const hash=(value:unknown)=>typeof value==='string'&&/^[a-f0-9]{64}$/.test(value);
function instant(value:string){const date=new Date(value);if(!Number.isFinite(date.getTime())||!value.endsWith('Z'))reject('time_invalid');return date;}
export function evaluateCorpus(input:unknown){
  const c=input as Corpus;
  if(!c||c.version!==1||c.reviewAuthority!=='engineering_source_review'||c.independentLabels!==false||c.blindedHoldout!==false||c.retrospective!==true
    ||!Array.isArray(c.samples)||c.samples.length<4||c.samples.length>100||!Array.isArray(c.referenceCases)||c.referenceCases.length>100
    ||!Array.isArray(c.channelConfigs)||!c.channelConfigs.length||!Array.isArray(c.limitations)||c.sourceCatalog?.version!==1||!Array.isArray(c.sourceCatalog.sources))reject('input_invalid');
  const catalog=new Map(c.sourceCatalog.sources.map(source=>[source.id,source]));if(catalog.size!==c.sourceCatalog.sources.length)reject('source_invalid');
  const cutoff=instant(c.cutoff),groups=new Map<string,string>(),materials=new Map<string,string>(),urls=new Map<string,string>(),ids=new Set<string>();
  function partition(item:{id:string;split:string;eventGroups:string[]}){
    if(!item||typeof item.id!=='string'||ids.has(item.id)||!['development','holdout'].includes(item.split)||!Array.isArray(item.eventGroups)||!item.eventGroups.length)reject('input_invalid');
    ids.add(item.id);
    for(const group of item.eventGroups){if(typeof group!=='string'||!group)reject('input_invalid');if(groups.has(group)&&groups.get(group)!==item.split)reject('split_overlap');groups.set(group,item.split);}
  }
  for(const sample of c.samples){
    partition(sample);const m=sample.material;
    if(!m||!uuid(m.material_id)||!Number.isSafeInteger(m.revision)||m.revision<1||!hash(m.content_hash)||!hash(m.body_hash)||typeof m.title!=='string'||typeof m.excerpt!=='string'||!Array.isArray(sample.tags))reject('material_invalid');
    if(!hash(sample.materialSnapshotHash)||sha256(canonicalGroupingInput(m))!==sample.materialSnapshotHash)reject('material_integrity_invalid');
    const key=identityKeyForUrl(m.original_url);if(!key||new URL(m.original_url).protocol!=='https:')reject('material_invalid');
    const source=catalog.get(m.source_id);if(!source||source.operator!==m.operator||typeof source.official!=='boolean'||new URL(source.url).origin!==new URL(m.original_url).origin)reject('source_invalid');
    if(materials.has(m.material_id)||urls.has(key))reject('material_overlap');materials.set(m.material_id,sample.split);urls.set(key,sample.split);
    if(instant(m.acquired_at)>cutoff)reject('future_material');if(m.published_at)instant(m.published_at);
  }
  for(const ref of c.referenceCases){
    partition(ref);if(ref.modelStatus!=='NOT_RUN'||!Array.isArray(ref.sourceUrls)||!ref.sourceUrls.length)reject('reference_invalid');
    for(const url of ref.sourceUrls){const key=identityKeyForUrl(url);if(!key||new URL(url).protocol!=='https:')reject('reference_invalid');
      if(urls.has(key)&&urls.get(key)!==ref.split)reject('split_overlap');urls.set(key,ref.split);}
  }
  const channelIds=new Set(c.channelConfigs.map(row=>row.id));if(channelIds.size!==c.channelConfigs.length)reject('channel_invalid');
  const rules:{id:string;split:string;scores:Record<string,Score>;insufficientContext:boolean}[]=[],mismatches:string[]=[],receiptCases:string[]=[];
  const candidateContextOverlap:{sampleId:string;candidateEventId:string;sourceSampleIds:string[]}[]=[];
  for(const sample of c.samples){
    const m=sample.material,scores:Record<string,Score>={};
    for(const channel of c.channelConfigs){
      const report={id:m.material_id,revision:m.revision,contentHash:m.content_hash,title:m.title,excerpt:m.excerpt,url:m.original_url,
        publishedAt:m.published_at?instant(m.published_at):null,acquiredAt:instant(m.acquired_at),state:m.state,official:catalog.get(m.source_id)!.official,sources:[{id:m.source_id,operator:m.operator}]};
      const j=scoreChannel(channel.config,[report],[],cutoff).judgment;scores[channel.id]={relevance:j.relevance,importance:j.importance,heat:j.heat};
      const expected=sample.expectedScores?.[channel.id];if(!expected||canonicalGroupingInput(expected)!==canonicalGroupingInput(scores[channel.id]))mismatches.push(sample.id+':'+channel.id);
    }
    rules.push({id:sample.id,split:sample.split,scores,insufficientContext:sample.tags.includes('insufficient_title_context')});
    if(sample.receipt){
      const r=sample.receipt;
      if(sha256(canonicalGroupingInput(r.packet))!==r.packetHash||sha256(canonicalGroupingInput(r.response))!==r.responseHash
        ||r.packet.material.id!==m.material_id||r.packet.material.revision!==m.revision||r.packet.material.contentHash!==m.content_hash
        ||r.packet.material.title!==m.title||r.packet.material.excerpt!==m.excerpt.slice(0,12000)||r.packet.material.url!==m.original_url
        ||r.packet.material.publishedAt!==m.published_at||r.packet.material.acquiredAt!==m.acquired_at||!Array.isArray(r.eventIds)||r.eventIds.some(id=>!uuid(id)))reject('receipt_invalid');
      let decision:GroupingDecision;try{decision=JSON.parse(r.response.text);}catch{reject('receipt_invalid');}
      if(canonicalGroupingInput(decision)!==canonicalGroupingInput(r.decision)||!Array.isArray(decision.parts))reject('receipt_invalid');
      if(canonicalGroupingInput(decision.parts.map(part=>part.relation))!==canonicalGroupingInput(r.expectedRelations))mismatches.push(sample.id+':relation');
      receiptCases.push(sample.id);
      for(const candidate of r.packet.candidates){
        const overlap=c.samples.filter(other=>other.split!==sample.split&&(other.receipt?.eventIds.includes(candidate.id)
          ||candidate.snapshot.materials.some(ref=>ref.id===other.material.material_id)
          ||candidate.reports.some(report=>identityKeyForUrl(report.url)===identityKeyForUrl(other.material.original_url))));
        if(overlap.length)candidateContextOverlap.push({sampleId:sample.id,candidateEventId:candidate.id,sourceSampleIds:overlap.map(other=>other.id)});
      }
    }
  }
  return {state:mismatches.length?'FAIL':'PASS_RETROSPECTIVE_REPLAY_WITH_EXPLICIT_GAPS',newModelCalls:0,independentAccuracy:null,blindedHoldout:false,
    partitionScope:'primary_occurrences_only',storedReceiptContextDisjoint:candidateContextOverlap.length===0,candidateContextOverlap,
    partitionCounts:{development:c.samples.filter(row=>row.split==='development').length,holdout:c.samples.filter(row=>row.split==='holdout').length},
    rules,modelReceiptCases:receiptCases.length,receiptCases,mismatches,
    unrunRelationships:c.referenceCases.map(row=>({id:row.id,expected:row.expected,status:row.modelStatus})),limitations:c.limitations};
}
if(process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href){
  try{const result=evaluateCorpus(JSON.parse(await readFile(new URL('../evaluation/real-corpus-v1.json',import.meta.url),'utf8')));
    console.log(JSON.stringify(result,null,2));if(result.state==='FAIL')process.exitCode=1;
  }catch(error){console.error(JSON.stringify({subsystem:'hot-evaluation',event:'evaluation_failed',code:error instanceof Error&&/^hot_evaluation_[a-z_]+$/.test(error.message)?error.message:'hot_evaluation_failed'}));process.exitCode=1;}
}
