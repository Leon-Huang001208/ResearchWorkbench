/** Explicit migration-owner setup on private stdin; normal worker cannot run this. */
import postgres from 'postgres';
import {parseConfig,poolOptions,assertNodeRuntime} from '../src/config.ts';
import {migrate} from '../src/database.ts';
import {initializeIdentity} from '../src/control.ts';
import {openQueue} from '../src/queue.ts';
import {grantWorker,grantController} from '../src/provision.ts';
import {sha256} from '../src/material.ts';

let db:ReturnType<typeof postgres>|undefined;
let phase='input';
try{
  assertNodeRuntime();const chunks:Buffer[]=[];let size=0;
  for await(const chunk of process.stdin){size+=chunk.length;if(size>65536)throw Error('hot_setup_limit');chunks.push(Buffer.from(chunk));}
  const input=JSON.parse(Buffer.concat(chunks).toString('utf8')),config=parseConfig(input.config);
  if(!/^[a-zA-Z][a-zA-Z0-9_]{0,62}$/.test(input.migrationUser))throw Error('hot_setup_role_invalid');
  if([config.database.user,config.database.controllerUser].includes(input.migrationUser))throw Error('hot_database_roles_overlap');
  db=postgres(poolOptions({...config.database,user:input.migrationUser},input.migrationPassword));
  phase='ownership';
  const [record]=await db`select to_regclass(${`${config.database.schema}.runtime_identity`}) as name`;
  if(record.name){
    const rows=await db`select instance_id,controller_token_hash from ${db(config.database.schema)}.runtime_identity where singleton`;
    if(rows.length&&(rows[0].instance_id!==input.instanceId||rows[0].controller_token_hash!==sha256(input.controllerToken)))throw Error('hot_setup_instance_mismatch');
  }
  phase='roles';
  if(input.createRoles===true){
    if(config.database.mode!=='managed')throw Error('hot_external_role_creation_denied');
    for(const [role,password]of [[config.database.user,input.workerPassword],[config.database.controllerUser,input.controllerPassword]]){
      if(!/^[a-f0-9]{64}$/.test(password))throw Error('hot_generated_secret_invalid');
      const found=await db`select oid from pg_roles where rolname=${role}`;
      if(found.length){
        const verifier=postgres(poolOptions({...config.database,user:role},password));
        try{
          const [attributes]=await verifier`select rolsuper,rolcreatedb,rolcreaterole from pg_roles where rolname=current_user`;
          if(attributes.rolsuper||attributes.rolcreatedb||attributes.rolcreaterole)throw Error('hot_role_not_scoped');
        }finally{await verifier.end({timeout:5});}
        continue;
      }
      // Generated hex only, never user SQL; failures are sanitized below.
      await db.unsafe(`create role "${role}" login nosuperuser nocreatedb nocreaterole password '${password}'`);
    }
  }
  phase='migration';await migrate(db,config.database.schema);
  phase='identity';
  await initializeIdentity(db,config.database.schema,input.instanceId,input.controllerToken);
  phase='queue';const boss=await openQueue(db,config.database.schema,true,config.worker);await boss.stop();
  phase='grants';
  await grantWorker(db,config.database.schema,config.database.user);await grantController(db,config.database.schema,config.database.controllerUser);
  console.log(JSON.stringify({state:'configured',schema:config.database.schema}));
}catch{console.log(JSON.stringify({state:'failed',code:'hot_setup_failed',phase}));process.exitCode=1;}
finally{if(db)await db.end({timeout:5});}
