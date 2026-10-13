/** Bounded private Host bootstrap; read role and explicit offline migration role differ. */
import postgres from 'postgres';
import {parseConfig,poolOptions,assertNodeRuntime} from '../src/config.ts';
import {SCHEMA_VERSION} from '../src/database.ts';
import {modelControl,modelAttempts} from '../src/model-control.ts';
import {sha256} from '../src/material.ts';
let db:ReturnType<typeof postgres>|undefined;
try{
  assertNodeRuntime();const parts:Buffer[]=[];let size=0;
  for await(const chunk of process.stdin){size+=chunk.length;if(size>65536)throw Error('hot_model_control_invalid');parts.push(Buffer.from(chunk));}
  const input=JSON.parse(Buffer.concat(parts).toString('utf8')),config=parseConfig(input.config);
  if(!['attempts','authorize','terminate','amend-tokens'].includes(input.operation)||!/^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/i.test(input.instanceId))throw Error('hot_model_control_invalid');
  const read=input.operation==='attempts',user=read?config.database.user:input.migrationUser;
  if(typeof user!=='string'||!/^[a-zA-Z][a-zA-Z0-9_]{0,62}$/.test(user)||(!read&&[config.database.user,config.database.controllerUser].includes(user)))throw Error('hot_model_control_denied');
  db=postgres({...poolOptions({...config.database,user},input.password),
    ...(read?{connection:{application_name:'rwb-hot-model-read',default_transaction_read_only:true,statement_timeout:15000}}:{})});
  const [identity]=await db`select instance_id,controller_token_hash from ${db(config.database.schema)}.runtime_identity where singleton`;
  if(!identity||identity.instance_id!==input.instanceId||(!read&&identity.controller_token_hash!==sha256(input.controllerToken)))throw Error('hot_model_control_instance_mismatch');
  const [version]=await db`select max(version)::int version from ${db(config.database.schema)}.migrations`;
  if(version.version!==SCHEMA_VERSION)throw Error('hot_model_controls_setup_required');
  const response=read?await modelAttempts(db,config.database.schema,input.parameters):await modelControl(db,config.database.schema,
    {instanceId:input.instanceId,controllerToken:input.controllerToken},
    {requestId:input.requestId,operator:input.operator,reason:input.reason,operation:input.operation,parameters:input.parameters});
  console.log(JSON.stringify({protocol:'rwb-hot-model/v1',ok:true,response}));
}catch(error){
  const known=['hot_model_control_invalid','hot_model_paid_authorization_required','hot_model_control_denied','hot_model_control_requires_stopped',
    'hot_model_control_instance_mismatch','hot_model_control_request_conflict','hot_model_authorization_conflict','hot_model_termination_invalid','hot_model_amendment_invalid','hot_model_controls_setup_required'];
  const code=error instanceof Error&&known.includes(error.message)?error.message:'hot_model_operation_failed';
  console.log(JSON.stringify({protocol:'rwb-hot-model/v1',ok:false,code}));process.exitCode=1;
}finally{if(db)await db.end({timeout:5});}
