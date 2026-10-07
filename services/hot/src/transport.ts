/** Signed single-frame loopback protocol; keys never travel over the connection. */
import {createServer,createConnection,type Socket} from 'node:net';
import {createHmac,timingSafeEqual,randomUUID} from 'node:crypto';
import type postgres from 'postgres';
import {logEvent} from './log.ts';

export interface RpcIdentity {instanceId:string;mode:'native'|'docker';generation:string}
export interface RpcHandler {permission:'read'|'control';run:(params:Record<string,postgres.JSONValue>,id:string,signal:AbortSignal)=>Promise<postgres.JSONValue>}
export interface TransportOptions {port?:number;identity:RpcIdentity;readerToken:string;controllerToken:string;
  guard:(signal:AbortSignal)=>Promise<void>;handlers:Map<string,RpcHandler>;secrets?:string[]}
const PROTOCOL='rwb-hot/v1',MAX_INPUT=65536,MAX_OUTPUT=1048576;
const UUID=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
function tokenValid(token:string){if(!/^[A-Za-z0-9_\-]{32,128}$/.test(token))throw Error('hot_rpc_token_invalid');}
function identityValid(identity:RpcIdentity){if(!UUID.test(identity.instanceId)||!['native','docker'].includes(identity.mode)||!/^\d{1,18}$/.test(identity.generation))throw Error('hot_rpc_identity_invalid');}
function sign(data:string,key:string){return createHmac('sha256',key).update(data).digest('hex');}
function verify(data:string,proof:unknown,key:string){return typeof proof==='string'&&/^[a-f0-9]{64}$/.test(proof)&&timingSafeEqual(Buffer.from(proof,'hex'),Buffer.from(sign(data,key),'hex'));}
function encode(value:unknown,key:string){const data=Buffer.from(JSON.stringify(value)).toString('base64url');return JSON.stringify({data,proof:key?sign(data,key):''})+'\n';}
function decode(frame:any){if(!frame||typeof frame.data!=='string'||!/^[A-Za-z0-9_\-]+$/.test(frame.data))throw Error('hot_rpc_frame_invalid');return JSON.parse(Buffer.from(frame.data,'base64url').toString('utf8'));}
function safeCode(error:unknown){return error instanceof Error&&/^hot_[a-z_]+$/.test(error.message)?error.message:'hot_rpc_unavailable';}
function reflects(value:unknown,secrets:string[],depth=0):boolean{
  if(depth>64)throw Error('hot_rpc_response_invalid');
  if(typeof value==='string')return secrets.some(secret=>value===secret||(secret.length>=8&&value.includes(secret)));
  if(Array.isArray(value))return value.some(item=>reflects(item,secrets,depth+1));
  if(value&&typeof value==='object')return Object.entries(value).some(([key,item])=>reflects(key,secrets,depth+1)||reflects(item,secrets,depth+1));
  return false;
}
export async function startTransport(options:TransportOptions):Promise<{port:number;metrics:()=>{connections:number;inflight:number};close:()=>Promise<void>}>{
  identityValid(options.identity);tokenValid(options.readerToken);tokenValid(options.controllerToken);
  if(options.readerToken===options.controllerToken)throw Error('hot_rpc_token_roles_invalid');
  const port=options.port??0;
  if(!Number.isInteger(port)||port<0||port>65535)throw Error('hot_rpc_port_invalid');
  const identity=Object.freeze({...options.identity}),secrets=[options.readerToken,options.controllerToken,...(options.secrets??[])].filter(Boolean);
  const connections=new Set<Socket>(),controllers=new Set<AbortController>();
  let closed=false,inflight=0;
  const server=createServer(socket=>{
    if(closed||connections.size>=16||inflight>=16){socket.destroy();return;}
    connections.add(socket);
    const cancellation=new AbortController();controllers.add(cancellation);
    const deadline=setTimeout(()=>{cancellation.abort();socket.destroy();},5000);
    deadline.unref();
    socket.on('close',()=>{connections.delete(socket);controllers.delete(cancellation);clearTimeout(deadline);cancellation.abort();});
    socket.on('error',()=>logEvent('rpc_failed'));
    let buffer=Buffer.alloc(0),processing=false;
    socket.on('data',chunk=>{
      if(processing){socket.destroy();return;}
      buffer=Buffer.concat([buffer,chunk]);
      if(buffer.length>MAX_INPUT){socket.destroy();return;}
      const end=buffer.indexOf(10);if(end<0)return;
      processing=true;
      if(buffer.subarray(end+1).length){socket.destroy();return;}
      if(inflight>=16){socket.destroy();return;}
      inflight++;
      void(async()=>{
        let id:string|null=null,key='';
        try{
          const frame=JSON.parse(buffer.subarray(0,end).toString('utf8'));
          if(typeof frame?.data!=='string')throw Error('hot_rpc_frame_invalid');
          if(verify(frame.data,frame.proof,options.controllerToken))key=options.controllerToken;
          else if(verify(frame.data,frame.proof,options.readerToken))key=options.readerToken;
          else throw Error('hot_rpc_denied');
          const request=decode(frame);
          if(!request||typeof request!=='object'||Array.isArray(request)||Object.keys(request).some(field=>!['protocol','id','instanceId','mode','generation','op','params','sentAt'].includes(field))||
            request.protocol!==PROTOCOL||!UUID.test(request.id)||!Number.isFinite(request.sentAt)||Math.abs(Date.now()-request.sentAt)>10000||
            !request.params||typeof request.params!=='object'||Array.isArray(request.params))throw Error('hot_rpc_request_invalid');
          id=request.id;
          if(request.instanceId!==identity.instanceId||request.mode!==identity.mode||request.generation!==identity.generation)throw Error('hot_rpc_identity_mismatch');
          const handler=options.handlers.get(request.op);
          if(!handler||(handler.permission==='control'&&key!==options.controllerToken))throw Error('hot_rpc_denied');
          await options.guard(cancellation.signal);cancellation.signal.throwIfAborted();
          const result=await handler.run(request.params,request.id,cancellation.signal);cancellation.signal.throwIfAborted();
          await options.guard(cancellation.signal);
          if(reflects(result,secrets)||reflects(id,secrets))throw Error('hot_rpc_credential_reflection');
          const response=encode({protocol:PROTOCOL,id,ok:true,result},key);
          if(Buffer.byteLength(response)>MAX_OUTPUT)throw Error('hot_rpc_response_limit');
          socket.end(response);
        }catch(error){
          logEvent('rpc_failed');let code=safeCode(error);
          if(reflects(id,secrets))id=null;if(reflects(code,secrets))code='hot_rpc_credential_reflection';
          if(!socket.destroyed)socket.end(encode({protocol:PROTOCOL,id,ok:false,code},key));
        }finally{inflight--;}
      })();
    });
  });
  await new Promise<void>((resolve,reject)=>{
    const failed=()=>reject(Error('hot_rpc_bind_failed'));server.once('error',failed);
    server.listen({host:'127.0.0.1',port,exclusive:true},()=>{server.removeListener('error',failed);resolve();});
  });
  server.on('error',()=>logEvent('rpc_failed'));
  const address=server.address();
  if(!address||typeof address==='string'){await new Promise<void>(resolve=>server.close(()=>resolve()));throw Error('hot_rpc_bind_failed');}
  return {port:address.port,metrics:()=>({connections:connections.size,inflight}),async close(){
    if(closed)return;closed=true;
    for(const controller of controllers)controller.abort();for(const socket of connections)socket.destroy();
    await new Promise<void>((resolve,reject)=>server.close(error=>error?reject(Error('hot_rpc_close_failed')):resolve()));
  }};
}
export async function rpc(port:number,identity:RpcIdentity,token:string,op:string,params:Record<string,postgres.JSONValue>,id=randomUUID()):Promise<postgres.JSONValue>{
  identityValid(identity);tokenValid(token);
  if(!Number.isInteger(port)||port<1||port>65535)throw Error('hot_rpc_port_invalid');
  const payload=encode({protocol:PROTOCOL,id,...identity,op,params,sentAt:Date.now()},token);
  if(Buffer.byteLength(payload)>MAX_INPUT)throw Error('hot_rpc_request_limit');
  return new Promise((resolve,reject)=>{
    const socket=createConnection({host:'127.0.0.1',port});let buffer=Buffer.alloc(0),settled=false;
    const deadline=setTimeout(()=>finish(Error('hot_rpc_timeout')),5000);deadline.unref();
    const finish=(error?:Error,value?:postgres.JSONValue)=>{if(settled)return;settled=true;clearTimeout(deadline);socket.destroy();if(error)reject(error);else resolve(value!);};
    socket.on('connect',()=>socket.write(payload));socket.on('error',()=>finish(Error('hot_rpc_unavailable')));
    socket.on('end',()=>{if(!settled)finish(Error('hot_rpc_incomplete'));});
    socket.on('data',chunk=>{
      buffer=Buffer.concat([buffer,chunk]);if(buffer.length>MAX_OUTPUT)return finish(Error('hot_rpc_response_limit'));
      const end=buffer.indexOf(10);if(end<0)return;
      try{
        const frame=JSON.parse(buffer.subarray(0,end).toString('utf8'));
        if(!verify(frame.data,frame.proof,token))return finish(Error('hot_rpc_denied'));
        const response=decode(frame);
        if(response.protocol!==PROTOCOL||response.id!==id||typeof response.ok!=='boolean')throw Error('hot_rpc_response_invalid');
        if(!response.ok)return finish(Error(safeCode(Error(response.code))));finish(undefined,response.result);
      }catch{finish(Error('hot_rpc_response_invalid'));}
    });
  });
}
