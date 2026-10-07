/** Consistent schema archive, authenticated manifest and bounded restore verification. */
import type postgres from 'postgres';
import {mkdir,open,lstat,readFile,realpath} from 'node:fs/promises';
import {join,resolve} from 'node:path';
import {createHmac,timingSafeEqual} from 'node:crypto';
import {schemaName} from './config.ts';
import {sha256} from './material.ts';

type Sql=ReturnType<typeof postgres>;
export interface ArchiveIdentity {instanceId:string;controllerToken:string}
export interface ArchiveManifest {
  version:1;schema:string;instanceId:string;createdAt:string;scope:'hot_schema';
  rawObjects:'database_bytea';researchSnapshots:'not_integrated';
  archiveSha256:string;inventorySha256:string;tables:Record<string,number>;proof:string;
}
async function inventory(db:Sql,schema:string){
  const names=await db`select tablename from pg_tables where schemaname=${schema} order by tablename`;
  const records:Record<string,unknown[]>={};
  for(const {tablename}of names){
    const rows=await db`select to_jsonb(t) as row from ${db(schema)}.${db(tablename)} t order by to_jsonb(t)::text`;
    records[tablename]=rows.map(item=>item.row);
  }
  return {inventorySha256:sha256(JSON.stringify(records)),tables:Object.fromEntries(Object.entries(records).map(([name,rows])=>[name,rows.length]))};
}
async function privateFile(path:string){
  const info=await lstat(path);
  if(!info.isFile()||info.nlink!==1||(info.mode&0o777)!==0o600||info.uid!==process.getuid?.())throw Error('hot_archive_unsafe');
}
async function privateDirectory(path:string){
  const info=await lstat(path);
  if(!info.isDirectory()||(info.mode&0o777)!==0o700||info.uid!==process.getuid?.()||await realpath(path)!==resolve(path))throw Error('hot_archive_unsafe');
}
function seal(value:Omit<ArchiveManifest,'proof'>,token:string){
  return createHmac('sha256',token).update(JSON.stringify(value)).digest('hex');
}
export async function backupSchema(db:Sql,schema:string,identity:ArchiveIdentity,directory:string,
  dump:(snapshot:string)=>Promise<Buffer>):Promise<ArchiveManifest>{
  schemaName(schema);
  await mkdir(directory,{mode:0o700}); // Unique destination; never replace an archive.
  await privateDirectory(directory);
  let manifest:ArchiveManifest;
  const connection=await db.reserve();
  let locked=false;
  let transaction=false;
  try{
    // Acquire the session fence BEFORE creating the repeatable-read snapshot.
    await connection`select pg_advisory_lock(hashtextextended(${schema},231501))`;
    locked=true;
    await connection.unsafe('begin isolation level repeatable read');transaction=true;
    const tx=connection;
    manifest=await (async()=>{
      const [owner]=await tx`select instance_id,controller_token_hash,paused from ${tx(schema)}.runtime_identity where singleton`;
      if(!owner||owner.instance_id!==identity.instanceId||owner.controller_token_hash!==sha256(identity.controllerToken))throw Error('hot_archive_identity_denied');
      if(!owner.paused)throw Error('hot_archive_requires_paused');
      const [{snapshot}]=await tx`select pg_export_snapshot() as snapshot`;
      const before=await inventory(tx as unknown as Sql,schema);
      const bytes=await dump(snapshot);
      if(bytes.length===0||bytes.length>256*1024*1024)throw Error('hot_archive_size_limit');
      const file=await open(join(directory,'hot.dump'),'wx',0o600);
      try{await file.writeFile(bytes);await file.sync();}finally{await file.close();}
      const body={version:1 as const,schema,instanceId:identity.instanceId,createdAt:new Date().toISOString(),
        scope:'hot_schema' as const,rawObjects:'database_bytea' as const,researchSnapshots:'not_integrated' as const,
        archiveSha256:sha256(bytes),...before};
      return {...body,proof:seal(body,identity.controllerToken)};
    })();
    await connection.unsafe('commit');transaction=false;
    const file=await open(join(directory,'manifest.json'),'wx',0o600);
    try{await file.writeFile(JSON.stringify(manifest));await file.sync();}finally{await file.close();}
    console.error(JSON.stringify({subsystem:'hot',event:'backup_completed'}));
    return manifest;
  }catch(error){
    // Incomplete directory is retained; lack of authenticated manifest prevents restore.
    console.error(JSON.stringify({subsystem:'hot',event:'backup_failed'}));
    throw error;
  }finally{
    try{
      if(transaction)await connection.unsafe('rollback');
      if(locked)await connection`select pg_advisory_unlock(hashtextextended(${schema},231501))`;
    }finally{connection.release();}
  }
}
export async function verifyArchive(directory:string,identity:ArchiveIdentity):Promise<ArchiveManifest>{
  await privateDirectory(directory);
  await privateFile(join(directory,'manifest.json'));await privateFile(join(directory,'hot.dump'));
  const bytes=await readFile(join(directory,'manifest.json'));
  if(bytes.length>65536)throw Error('hot_archive_manifest_invalid');
  const value=JSON.parse(bytes.toString('utf8')) as ArchiveManifest;
  const {proof,...body}=value;
  if(value.version!==1||value.scope!=='hot_schema'||value.instanceId!==identity.instanceId||
     typeof proof!=='string'||!/^[a-f0-9]{64}$/.test(proof))throw Error('hot_archive_identity_denied');
  const actual=seal(body,identity.controllerToken);
  if(!timingSafeEqual(Buffer.from(proof,'hex'),Buffer.from(actual,'hex')))throw Error('hot_archive_signature_invalid');
  schemaName(value.schema);
  const file=await lstat(join(directory,'hot.dump'));
  if(file.size>256*1024*1024)throw Error('hot_archive_size_limit');
  if(sha256(await readFile(join(directory,'hot.dump')))!==value.archiveSha256)throw Error('hot_archive_checksum_invalid');
  return value;
}
export async function verifyRestoredSchema(db:Sql,manifest:ArchiveManifest):Promise<void>{
  schemaName(manifest.schema);
  await db.begin('isolation level repeatable read',async tx=>{
    const actual=await inventory(tx as unknown as Sql,manifest.schema);
    if(actual.inventorySha256!==manifest.inventorySha256)throw Error('hot_archive_inventory_mismatch');
    const [owner]=await tx`select paused from ${tx(manifest.schema)}.runtime_identity where singleton`;
    if(!owner?.paused)throw Error('hot_archive_restore_not_paused');
  });
}
