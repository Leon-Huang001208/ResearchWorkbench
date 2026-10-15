/** Host-owned backup/restore bootstrap. Raw credentials are private stdin only. */
import postgres from 'postgres';
import {readFile,mkdtemp,writeFile,rm,realpath} from 'node:fs/promises';
import {join} from 'node:path';
import {tmpdir} from 'node:os';
import {spawn,execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {randomUUID} from 'node:crypto';
import {sha256} from '../src/material.ts';
import {parseConfig,poolOptions,assertNodeRuntime} from '../src/config.ts';
import {backupSchema,verifyArchive,verifyRestoredSchema} from '../src/archive.ts';
import {grantWorker,grantController} from '../src/provision.ts';

const execute=promisify(execFile);
let db:ReturnType<typeof postgres>|undefined,cancellationDb:ReturnType<typeof postgres>|undefined,temp:string|undefined;
let phase='input';
let cancelling=false;
process.on('SIGTERM',()=>{cancelling=true;});process.on('SIGINT',()=>{cancelling=true;});
try{
  assertNodeRuntime();const chunks:Buffer[]=[];let length=0;
  for await(const chunk of process.stdin){length+=chunk.length;if(length>65536)throw Error('hot_archive_input_limit');chunks.push(Buffer.from(chunk));}
  const input=JSON.parse(Buffer.concat(chunks).toString('utf8')),config=parseConfig(input.config),schema=config.database.schema;
  if(!['backup','restore'].includes(input.operation)||typeof input.directory!=='string')throw Error('hot_archive_input_invalid');
  if(!/^[a-zA-Z][a-zA-Z0-9_]{0,62}$/.test(input.migrationUser))throw Error('hot_archive_input_invalid');
  const identity={instanceId:input.instanceId,controllerToken:input.controllerToken};
  const environment:NodeJS.ProcessEnv={PATH:process.env.PATH,HOME:process.env.HOME,LANG:'C.UTF-8'};
  let prefix:string[]=[];
  if(config.database.mode==='managed'){
    const container='rwb-hot-db-'+identity.instanceId.replaceAll('-','').slice(0,16);
    const {stdout}=await execute('docker',['inspect',container],{timeout:5000,env:environment});
    const state=JSON.parse(stdout)[0];
    if(state.Config.Labels?.['rwb.hot.instance']!==identity.instanceId||
       state.Config.Image!=='postgres@sha256:3645570cccdfa447589da9f57dd740faa29b30938e861289a5574b6ca6b03826')throw Error('hot_archive_container_foreign');
    prefix=['docker','exec','-i',container];
  }else{
    temp=await realpath(await mkdtemp(join(tmpdir(),'rwb-hot-pgpass-')));
    const escape=(value:string)=>value.replaceAll('\\','\\\\').replaceAll(':','\\:');
    const pass=[config.database.host,String(config.database.port),'*',input.migrationUser,input.migrationPassword].map(escape).join(':');
    if(pass.includes('\n')||pass.includes('\r'))throw Error('hot_archive_password_invalid');
    await writeFile(join(temp,'pgpass'),pass+'\n',{mode:0o600,flag:'wx'});
    environment.PGPASSFILE=join(temp,'pgpass');environment.PGSSLMODE=config.database.tls==='verify-full'?'verify-full':'disable';
  }
  async function command(tool:string,args:string[],bytes?:Buffer):Promise<Buffer>{
    if(cancelling)throw Error('hot_archive_cancelled');
    const binary=prefix[0]??tool;
    const application='rwb-hot-archive-'+randomUUID();
    const options='-c statement_timeout=60000 -c lock_timeout=5000';
    const parameters=prefix.length?['exec','-i','-e','PGAPPNAME='+application,'-e','PGOPTIONS='+options,
      prefix[3]!,'timeout','--signal=TERM','--kill-after=5s','60s',tool,...args]:args;
    return await new Promise((resolveOutput,reject)=>{
      const child=spawn(binary,parameters,{env:{...environment,PGAPPNAME:application,PGOPTIONS:options},stdio:['pipe','pipe','pipe']});
      const output:Buffer[]=[];let size=0,failed=false;
      // In Docker the timeout lives INSIDE the container and kills the tool group.
      const timer=setTimeout(()=>{failed=true;if(!prefix.length)child.kill('SIGKILL');},60000);
      child.stderr.resume(); // Never echo libpq diagnostics or credential-bearing server errors.
      child.stdout.on('data',chunk=>{size+=chunk.length;if(size>256*1024*1024){failed=true;if(!prefix.length)child.kill('SIGKILL');}else output.push(chunk);});
      child.on('error',()=>{clearTimeout(timer);reject(Error('hot_archive_tool_unavailable'));});
      child.on('close',async code=>{
        clearTimeout(timer);
        if(code!==0||failed||cancelling){
          try{
            if(cancellationDb){
              await cancellationDb`select pg_terminate_backend(pid) from pg_stat_activity where application_name=${application} and usename=${user} and pid<>pg_backend_pid()`;
              let ended=false;
              for(let retry=0;retry<20;retry++){
                const [active]=await cancellationDb`select count(*)::int as n from pg_stat_activity where application_name=${application} and usename=${user}`;
                if(!active.n){ended=true;break;}
                await new Promise(resolveWait=>setTimeout(resolveWait,100));
              }
              if(!ended)throw Error('hot_archive_outcome_unknown');
            }
            reject(Error('hot_archive_tool_failed'));
          }catch{reject(Error('hot_archive_outcome_unknown'));}
        }else resolveOutput(Buffer.concat(output));
      });
      child.stdin.on('error',()=>{});child.stdin.end(bytes);
    });
  }
  phase='tools';
  for(const tool of ['pg_dump','pg_restore']){
    const version=(await command(tool,['--version'])).toString('utf8');
    if(!/\(PostgreSQL\) 17\./.test(version))throw Error('hot_archive_tools_version_unsupported');
  }
  const user=config.database.mode==='managed'?'postgres':input.migrationUser;
  const connection=prefix.length?['-U',user]:['-h',config.database.host,'-p',String(config.database.port),'-U',user];
  db=postgres(poolOptions({...config.database,user},input.migrationPassword));
  // Never depend on the pool whose sole connection may hold the exported snapshot.
  cancellationDb=postgres(poolOptions({...config.database,user,poolMax:1},input.migrationPassword));
  if(input.operation==='backup'){
    phase='backup';
    const manifest=await backupSchema(db,schema,identity,input.directory,snapshot=>command('pg_dump',[
      ...connection,'-d',config.database.name,'--schema='+schema,'--format=custom','--no-owner','--no-privileges','--snapshot='+snapshot]));
    console.log(JSON.stringify({state:'backed_up',directory:input.directory,archiveSha256:manifest.archiveSha256,
      tables:manifest.tables,scope:manifest.scope,researchSnapshots:manifest.researchSnapshots}));
  }else{
    phase='verify';const manifest=await verifyArchive(input.directory,identity);
    const authenticatedBytes=await readFile(join(input.directory,'hot.dump'));
    if(sha256(authenticatedBytes)!==manifest.archiveSha256)throw Error('hot_archive_checksum_invalid');
    if(manifest.schema!==schema||!/^[a-zA-Z][a-zA-Z0-9_]{0,62}$/.test(input.targetDatabase)||input.targetDatabase===config.database.name)throw Error('hot_archive_target_invalid');
    phase='target';
    const existing=await db`select datname from pg_database where datname=${input.targetDatabase}`;
    if(!existing.length)await db.unsafe(`create database "${input.targetDatabase}"`);
    const target=postgres(poolOptions({...config.database,user,name:input.targetDatabase},input.migrationPassword));
    try{
      const names=await target`select oid from pg_namespace where nspname=${schema}`;
      if(names.length)throw Error('hot_archive_target_not_empty');
      phase='restore';await command('pg_restore',[...connection,'-d',input.targetDatabase,'--exit-on-error','--single-transaction','--no-owner','--no-privileges'],authenticatedBytes);
      phase='inventory';await verifyRestoredSchema(target,manifest);
      await target`update ${target(schema)}.sources set enabled=false`;
      await grantWorker(target,schema,config.database.user);await grantController(target,schema,config.database.controllerUser);
      console.log(JSON.stringify({state:'restored_paused',targetDatabase:input.targetDatabase,schema,
        archiveSha256:manifest.archiveSha256,sourceCollectionPaused:true,researchSnapshots:'not_integrated'}));
    }finally{await target.end({timeout:5});}
  }
}catch(error){console.log(JSON.stringify({state:'failed',code:error instanceof Error&&error.message==='hot_archive_outcome_unknown'?'hot_archive_outcome_unknown':'hot_archive_failed',phase}));process.exitCode=1;}
finally{if(db)await db.end({timeout:5});if(cancellationDb)await cancellationDb.end({timeout:5});if(temp)await rm(temp,{recursive:true});}
