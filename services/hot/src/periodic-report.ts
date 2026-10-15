/** Existing Python report mechanism, invoked once per frozen input; no research/model process. */
import {execFile} from 'node:child_process';
import {isAbsolute,resolve} from 'node:path';
import type postgres from 'postgres';
import {sha256} from './material.ts';
import {logEvent} from './log.ts';
import {schemaName} from './config.ts';

type Sql=ReturnType<typeof postgres>;
export type PeriodicReportRenderer=(saved:postgres.JSONValue,signal:AbortSignal)=>Promise<Buffer>;
const protocol='rwb-hot-report/v1';
export function decodeReport(value:unknown,inputHash:string):Buffer {
  if(!value||typeof value!=='object'||Array.isArray(value))throw Error('hot_periodic_report_invalid');
  const row=value as Record<string,unknown>;
  if(row.protocol!==protocol||row.state!=='completed'||row.inputHash!==inputHash||row.format!=='docx'||
     !Number.isSafeInteger(row.bytes)||Number(row.bytes)<1||Number(row.bytes)>5242880||typeof row.sha256!=='string'||
     !/^[a-f0-9]{64}$/.test(row.sha256)||typeof row.data!=='string'||row.data.length>6990508)throw Error('hot_periodic_report_invalid');
  const data=Buffer.from(row.data,'base64');
  if(data.toString('base64')!==row.data||data.length!==row.bytes||sha256(data)!==row.sha256)throw Error('hot_periodic_report_invalid');
  return data;
}
export function periodicReportRenderer(python:string):PeriodicReportRenderer {
  if(typeof python!=='string'||!isAbsolute(python)||python.length>1024)throw Error('hot_periodic_report_unavailable');
  const project=resolve(import.meta.dirname,'../../..');
  const environment=Object.fromEntries(Object.entries(process.env).filter(([key])=>['PATH','HOME','TMPDIR','TEMP','TMP'].includes(key)));
  return async(saved,signal)=>{
    signal.throwIfAborted();
    const packet=JSON.stringify({protocol,saved});
    if(Buffer.byteLength(packet)>1048576)throw Error('hot_periodic_report_limit');
    try{
      const raw=await new Promise<string>((accept,reject)=>{
        const child=execFile(python,['-m','app.research_web.hot_periodic_report'],
          {cwd:project,env:environment,timeout:25000,maxBuffer:8*1024*1024,killSignal:'SIGKILL',signal},
          (error,stdout)=>error?reject(Error('hot_periodic_report_failed')):accept(stdout));
        child.stdin!.on('error',()=>{}); // Exit/abort callback owns the stable failure.
        child.stdin!.end(packet);
      });
      signal.throwIfAborted();
      const inputHash=(saved as Record<string,postgres.JSONValue>).contentHash;
      const data=decodeReport(JSON.parse(raw),String(inputHash));
      logEvent('periodic_report_completed');return data;
    }catch{logEvent('periodic_report_failed');throw Error('hot_periodic_report_failed');}
  };
}
export async function periodicReportChunk(db:Sql,schema:string,params:Record<string,postgres.JSONValue>){
  schemaName(schema);
  if(Object.keys(params).some(key=>!['runId','offset'].includes(key))||typeof params.runId!=='string'||
     !/^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/i.test(params.runId)||
     (params.offset!==undefined&&(!Number.isSafeInteger(params.offset)||Number(params.offset)<0)))throw Error('hot_periodic_report_invalid');
  const [row]=await db`select execution_id,brief_id,brief_version,input_hash,docx_hash,octet_length(docx)::int bytes,
    substring(docx from ${Number(params.offset??0)+1} for 32768) chunk from ${db(schema)}.periodic_report_executions where run_id=${params.runId}`;
  if(!row)throw Error('hot_periodic_report_unknown');
  const offset=Number(params.offset??0),next=offset+row.chunk.length;
  if(offset>=row.bytes)throw Error('hot_periodic_report_invalid');
  return {runId:params.runId,executionId:row.execution_id,briefId:row.brief_id,briefVersion:row.brief_version,
    inputHash:row.input_hash,artifactHash:row.docx_hash,format:'docx',totalBytes:row.bytes,offset,
    data:row.chunk.toString('base64'),nextOffset:next<row.bytes?next:null};
}
