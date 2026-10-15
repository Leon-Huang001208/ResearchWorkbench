import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile,mkdtemp,realpath,chmod,writeFile} from 'node:fs/promises';
import {join,resolve} from 'node:path';
import {createHmac,randomBytes,randomUUID} from 'node:crypto';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import postgres from 'postgres';
import {migrate,ingestPage} from '../src/database.ts';
import {initializeIdentity,activateRuntime,pauseRuntime} from '../src/control.ts';
import {openQueue} from '../src/queue.ts';
import {parseFeed} from '../src/feed.ts';
import {backupSchema,verifyArchive,verifyRestoredSchema} from '../src/archive.ts';
import {sha256} from '../src/material.ts';

const execute=promisify(execFile);
test('consistent authenticated archive restores real raw material and remains paused',{timeout:30000},async()=>{
  const evidence=process.env.RWB_HOT_TEST_EVIDENCE??resolve(import.meta.dirname,'../../../logs/hot-stage-zero');
  const receipt=JSON.parse(await readFile(join(evidence,'receipt.json'),'utf8'));
  const password=await readFile(join(evidence,'password'),'utf8');
  const port=process.env.RWB_HOT_TEST_PG_PORT?Number(process.env.RWB_HOT_TEST_PG_PORT):receipt.port;
  const db=postgres({host:'127.0.0.1',port,database:'hot_probe',username:'postgres',password,onnotice:()=>{}});
  const schema='hot_archive_'+randomBytes(5).toString('hex');
  const restored='hot_archive_restore_'+randomBytes(5).toString('hex');
  const container='rwb-hot-probe-6a5d3231';
  const root=await realpath(await mkdtemp('/tmp/rwb-hot-archive-'));await chmod(root,0o700);
  const identity={instanceId:randomUUID(),controllerToken:randomBytes(32).toString('hex')};
  let target:ReturnType<typeof postgres>|undefined;
  try{
    const {stdout}=await execute('docker',['inspect',container],{timeout:5000});
    const owned=JSON.parse(stdout)[0];
    assert.equal(owned.Config.Labels['rwb.hot.probe'],'6a5d3231');
    assert.equal(owned.Config.Image,receipt.image);
    await migrate(db,schema);await initializeIdentity(db,schema,identity.instanceId,identity.controllerToken);
    await db.unsafe(`create table ${schema}.precision_fixture (value bigint, detail jsonb)`);
    await db.unsafe(`insert into ${schema}.precision_fixture values (9007199254740992,'{"nested":9007199254740992}')`);
    const boss=await openQueue(db,schema,true);await boss.stop();
    await db`insert into ${db(schema)}.sources(id,operator,config) values('fed','Federal Reserve',${db.json({})})`;
    const raw=await readFile(join(evidence,'fed.xml'));
    const acquiredAt=new Date();
    const items=parseFeed(raw.toString('utf8'),'https://www.federalreserve.gov',acquiredAt);
    await ingestPage(db,{source:'fed',raw:raw.toString('utf8'),materials:items.slice(0,1),acquiredAt,cursor:{}},schema);
    const owner=await activateRuntime(db,schema,identity.instanceId,identity.controllerToken,'native');
    let called=false;
    await assert.rejects(backupSchema(db,schema,identity,join(root,'live'),async()=>{called=true;return Buffer.from('bad');}),/requires_paused/);
    assert.equal(called,false);
    await pauseRuntime(db,schema,owner,identity.controllerToken);
    let releaseActivation:()=>void=()=>{};
    let signalLocked:()=>void=()=>{};
    const locked=new Promise<void>(resolveLocked=>{signalLocked=resolveLocked;});
    const finish=new Promise<void>(resolveFinish=>{releaseActivation=resolveFinish;});
    const activation=db.begin(async tx=>{
      await tx`select pg_advisory_xact_lock(hashtextextended(${schema},231501))`;
      await tx`update ${tx(schema)}.runtime_identity set paused=false,generation=generation+1,owner_until=clock_timestamp()+interval '60 seconds'`;
      signalLocked();await finish;
    });
    await locked;
    const stale=assert.rejects(backupSchema(db,schema,identity,join(root,'activation-race'),async()=>Buffer.from('bad')),/requires_paused/);
    await new Promise(resolveWait=>setTimeout(resolveWait,50));releaseActivation();
    await activation;await stale;
    await db`update ${db(schema)}.runtime_identity set paused=true,generation=generation+1,owner_until=null`;
    const directory=join(root,'backup');
    const manifest=await backupSchema(db,schema,identity,directory,async snapshot=>{
      const result=await execute('docker',['exec',container,'pg_dump','-U','postgres','-d','hot_probe',
        '--schema='+schema,'--format=custom','--no-owner','--no-privileges','--snapshot='+snapshot],
        {encoding:'buffer',timeout:15000,maxBuffer:256*1024*1024});
      return result.stdout;
    });
    assert.equal(manifest.tables.raw_pages,1);
    assert.equal(manifest.inventoryEncoding,'postgres-jsonb-text-v1');
    await verifyArchive(directory,identity);
    await assert.rejects(verifyArchive(directory,{...identity,controllerToken:'f'.repeat(64)}),/signature_invalid/);
    await db.unsafe(`create database ${restored}`);
    // A real pg_restore against a new isolated database; no existing schema is overwritten.
    await new Promise<void>((resolveRestore,reject)=>{
      const child=execFile('docker',['exec','-i',container,'pg_restore','-U','postgres','-d',restored,
        '--exit-on-error','--single-transaction','--no-owner','--no-privileges'],{timeout:15000},error=>error?reject(Error('hot_restore_fixture_failed')):resolveRestore());
      readFile(join(directory,'hot.dump')).then(bytes=>child.stdin!.end(bytes),reject);
    });
    target=postgres({host:'127.0.0.1',port,database:restored,username:'postgres',password,max:1,onnotice:()=>{}});
    await target.unsafe("set timezone='America/New_York'");
    await verifyRestoredSchema(target,manifest);
    await target.unsafe(`update ${schema}.precision_fixture set value=9007199254740993`);
    await assert.rejects(verifyRestoredSchema(target,manifest),/inventory_mismatch/);
    await target.unsafe(`update ${schema}.precision_fixture set value=9007199254740992,detail='{"nested":9007199254740993}'`);
    await assert.rejects(verifyRestoredSchema(target,manifest),/inventory_mismatch/);
    await target.unsafe(`update ${schema}.precision_fixture set detail='{"nested":9007199254740992}'`);
    const records:Record<string,unknown[]>={};
    for(const {tablename} of await target`select tablename from pg_tables where schemaname=${schema} order by tablename`){
      const rows=await target`select to_jsonb(t) as row from ${target(schema)}.${target(tablename)} t order by to_jsonb(t)::text`;
      records[tablename]=rows.map(item=>item.row);
    }
    const legacy={...manifest,inventoryEncoding:undefined,inventorySha256:sha256(JSON.stringify(records))};
    await assert.rejects(verifyRestoredSchema(target,legacy),/inventory_rebackup_required/);
    // Both collision directions must fail: the old hash cannot prove original bytes.
    await target.unsafe(`update ${schema}.precision_fixture set detail='{"nested":9007199254740993}'`);
    await assert.rejects(verifyRestoredSchema(target,legacy),/inventory_rebackup_required/);
    await target.unsafe(`update ${schema}.precision_fixture set detail='{"nested":9007199254740992}'`);
    const {proof:oldProof,inventoryEncoding:oldEncoding,...legacyBody}=legacy;
    await writeFile(join(directory,'manifest.json'),JSON.stringify({...legacyBody,
      proof:createHmac('sha256',identity.controllerToken).update(JSON.stringify(legacyBody)).digest('hex')}));
    await assert.rejects(verifyArchive(directory,identity),/inventory_rebackup_required/);
    await writeFile(join(directory,'manifest.json'),JSON.stringify(manifest));
    await verifyRestoredSchema(target,manifest);
    await target`update ${target(schema)}.sources set enabled=false`;
    const [row]=await target`select body from ${target(schema)}.raw_pages`;
    assert.equal(Buffer.compare(row.body,raw),0);
    const [state]=await target`select paused from ${target(schema)}.runtime_identity where singleton`;
    assert.equal(state.paused,true);
    await writeFile(join(directory,'hot.dump'),Buffer.from('tampered'));
    await assert.rejects(verifyArchive(directory,identity),/checksum_invalid/);
  }finally{if(target)await target.end({timeout:5});await db.end({timeout:5});}
});
