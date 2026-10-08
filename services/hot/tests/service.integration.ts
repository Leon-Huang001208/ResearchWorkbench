import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile,mkdtemp,realpath,chmod,mkdir,writeFile } from 'node:fs/promises';
import { join,resolve } from 'node:path';
import { randomUUID,randomBytes } from 'node:crypto';
import { spawn,execFileSync } from 'node:child_process';
import { once } from 'node:events';
import postgres from 'postgres';
import { migrate,ingestPage } from '../src/database.ts';
import { parseFeed } from '../src/feed.ts';
import { initializeIdentity } from '../src/control.ts';
import { openQueue } from '../src/queue.ts';
import { grantWorker,grantController } from '../src/provision.ts';
import { rpc } from '../src/transport.ts';

test('real owned service process stops and restarts without deleting material or database', {timeout:20000}, async()=>{
  const dir=resolve(import.meta.dirname,'../../../logs/hot-stage-zero');
  const receipt=JSON.parse(await readFile(join(dir,'receipt.json'),'utf8'));
  const password=await readFile(join(dir,'password'),'utf8');
  const db=postgres({host:'127.0.0.1',port:receipt.port,database:'hot_probe',username:'postgres',password,onnotice:()=>{}});
  const schema=`hot_service_${randomBytes(5).toString('hex')}`;
  const worker=`hot_worker_${randomBytes(5).toString('hex')}`;
  const controller=`hot_control_${randomBytes(5).toString('hex')}`;
  const workerPassword=randomBytes(32).toString('hex');
  const controllerPassword=randomBytes(32).toString('hex');
  const instance=randomUUID(),controllerToken=randomBytes(32).toString('hex'),readerToken=randomBytes(32).toString('hex');
  const path=await realpath(await mkdtemp('/tmp/rwb-hot-service-'));
  await chmod(path,0o700);
  const socketPath=join(path,'rpc.sock');
  let child: ReturnType<typeof spawn> | undefined;
  try {
    await migrate(db,schema);
    await initializeIdentity(db,schema,instance,controllerToken);
    const boss=await openQueue(db,schema,true); await boss.stop();
    try {
      await db.unsafe(`create role "${worker}" login nosuperuser nocreatedb nocreaterole password '${workerPassword}'`);
      await db.unsafe(`create role "${controller}" login nosuperuser nocreatedb nocreaterole password '${controllerPassword}'`);
    } catch { throw Error('hot_fixture_role_failed'); }
    await grantWorker(db,schema,worker); await grantController(db,schema,controller);
    await db`insert into ${db(schema)}.sources(id,operator,config) values('fed','Federal Reserve','{}'::jsonb)`;
    const raw=await readFile(join(dir,'fed.xml'),'utf8'),acquiredAt=new Date();
    const stored=await ingestPage(db,{source:'fed',raw,acquiredAt,materials:parseFeed(raw,'https://www.federalreserve.gov/feeds/press_all.xml',acquiredAt).slice(0,1),cursor:{}},schema);
    let previousGeneration='0';
    for(let restart=0;restart<2;restart++) {
      child=spawn(process.execPath,[resolve(import.meta.dirname,'../scripts/serve.ts')],{stdio:['pipe','pipe','pipe']});
      child.stderr!.resume();
      const ready=new Promise<any>((resolveReady,reject)=>{
        let buffer='';
        child!.stdout!.on('data',chunk=>{ buffer+=chunk; if(buffer.includes('\n')) { try {resolveReady(JSON.parse(buffer.split('\n')[0]));} catch {reject(Error('hot_fixture_ready_invalid'));} } });
        child!.on('error',()=>reject(Error('hot_fixture_process_failed')));
        child!.on('exit',()=>{if(!buffer.includes('\n')) reject(Error('hot_fixture_process_exited'));});
      });
      child.stdin!.end(JSON.stringify({config:{enabled:true,database:{mode:'external',tls:'disable',port:receipt.port,name:'hot_probe',schema,user:worker}},
        instanceId:instance,mode:'native',workerPassword,controllerUser:controller,controllerPassword,controllerToken,readerToken}));
      const result=await ready;
      assert.equal(result.state,'initialized');
      assert.ok(Number(result.owner.generation)>Number(previousGeneration));
      previousGeneration=result.owner.generation;
      const status=await rpc(result.port,result.owner,readerToken,'status',{}) as any;
      assert.equal(status.sourceCount,1);
      assert.equal(status.worker,'running');
      const change={sourceId:'fed',expectedRevision:String(restart*2),enabled:false,frequencySeconds:120};
      const requestId=randomUUID();
      await assert.rejects(rpc(result.port,result.owner,readerToken,'source.configure',change,requestId),/denied/);
      const changed=await rpc(result.port,result.owner,controllerToken,'source.configure',change,requestId) as any;
      assert.equal(changed.enabled,false);assert.equal(changed.revision,String(restart*2+1));
      assert.deepEqual(await rpc(result.port,result.owner,controllerToken,'source.configure',change,requestId),changed);
      await assert.rejects(rpc(result.port,result.owner,controllerToken,'source.configure',{...change,enabled:true},requestId),/request_conflict/);
      await rpc(result.port,result.owner,controllerToken,'source.configure',{sourceId:'fed',expectedRevision:changed.revision,enabled:true,frequencySeconds:null});
      const exited=once(child,'exit'); child.kill('SIGTERM');
      const [code]=await exited; assert.equal(code,0); child=undefined;
      assert.equal((await db`select paused from ${db(schema)}.runtime_identity where singleton`)[0].paused,true);
      assert.equal((await db`select count(*)::int n from ${db(schema)}.materials where id=${stored.materialIds[0]}`)[0].n,1);
    }
    // The public manager uses the same production module; only the credential backend is isolated.
    const home=join(path,'manager-home');await mkdir(join(home,'hot'),{recursive:true,mode:0o700});
    const project=resolve(import.meta.dirname,'../../..');
    const config={enabled:true,database:{mode:'external',tls:'disable',port:receipt.port,name:'hot_probe',schema,user:worker,controllerUser:controller}};
    await writeFile(join(home,'hot','settings.json'),JSON.stringify({schemaVersion:1,projectRoot:project,config}),{mode:0o600});
    await writeFile(join(home,'hot','identity.json'),JSON.stringify({projectRoot:project,instanceId:instance}),{mode:0o600});
    const probe=`import json,sys\nfrom pathlib import Path\nfrom research_workbench_entrypoint.hot_manager import HotManager\np=json.load(sys.stdin)\nclass Credentials:\n def get_password(self,service,account): return p['secrets'].get(account)\nm=HotManager(Path(p['project']),Path(p['home']),Credentials())\ntry:\n a=m.start()\n b=m.status()\n e=m.configure_source('fed','4',False,120)\n f=m.sources()\n c=m.restart()\n g=m.sources()\n d=m.stop()\n print(json.dumps({'first':a['state'],'status':b['state'],'restart':c['state'],'stopped':d['state'],'sourceRevision':e['revision'],'sourceEnabled':f[0]['enabled'],'persistedEnabled':g[0]['enabled']}))\nfinally:\n m.stop()\n`;
    const result=execFileSync('/opt/homebrew/bin/python3.12',['-c',probe],{cwd:project,
      env:{...process.env,RESEARCH_NODE_BINARY:process.execPath},timeout:20000,encoding:'utf8',
      input:JSON.stringify({project,home,secrets:{'hot-database':workerPassword,'hot-controller-database':controllerPassword,'rpc-controller':controllerToken,'rpc-reader':readerToken}})});
    assert.deepEqual(JSON.parse(result),{first:'initialized',status:'initialized',restart:'initialized',stopped:'stopped',sourceRevision:'5',sourceEnabled:false,persistedEnabled:false});
    assert.equal((await db`select count(*)::int n from ${db(schema)}.materials where id=${stored.materialIds[0]}`)[0].n,1);
  } finally {
    if(child) {child.kill('SIGKILL');await once(child,'exit');}
    await db.end({timeout:5});
  }
});
