import { test } from 'node:test';
import assert from 'node:assert/strict';
import { randomBytes, randomUUID } from 'node:crypto';
import { createHmac } from 'node:crypto';
import { createConnection } from 'node:net';
import { once } from 'node:events';
import { setTimeout as delay } from 'node:timers/promises';
import { startTransport, rpc, type RpcIdentity, type RpcHandler } from '../src/transport.ts';

test('large signed research receipts and cached streams fit without widening ordinary operations',async()=>{
  const reader=randomBytes(32).toString('hex'),controller=randomBytes(32).toString('hex');
  const identity:RpcIdentity={instanceId:randomUUID(),mode:'native',generation:'1'};
  const payload={chunks:[{type:'text-delta',text:'x'.repeat(950000)}]};
  let saved:any;
  const service=await startTransport({identity,readerToken:reader,controllerToken:controller,guard:async()=>{},handlers:new Map([
    ['research.model.receipt',{permission:'control',run:async (params:Parameters<RpcHandler['run']>[0])=>{saved=params;return {state:'received'};}}],
    ['research.model.reserve',{permission:'control',run:async()=>({state:'reused',response:saved})}],
    ['ordinary',{permission:'control',run:async()=>({})}],
  ])});
  try{
    await assert.rejects(rpc(service.port,identity,controller,'ordinary',payload),/request_limit/);
    await assert.rejects(rpc(service.port,identity,reader,'research.model.receipt',payload),/denied/);
    assert.deepEqual(await rpc(service.port,identity,controller,'research.model.receipt',payload),{state:'received'});
    assert.deepEqual(await rpc(service.port,identity,controller,'research.model.reserve',{}),{state:'reused',response:payload});
    await assert.rejects(rpc(service.port,identity,controller,'research.model.receipt',{text:'x'.repeat(2097152)}),/request_limit/);
  }finally{await service.close();}
});

test('private protocol enforces instance, mode, generation and control permission', async () => {
  const reader = randomBytes(32).toString('hex');
  const controller = randomBytes(32).toString('hex');
  const identity: RpcIdentity = { instanceId: randomUUID(), mode: 'native', generation: '1' };
  let writes = 0;
  const escapedSecret='p"a\\ss\nsecret';
  const service = await startTransport({ identity, readerToken: reader, controllerToken: controller,secrets:[escapedSecret],
    guard: async () => {}, handlers: new Map([
      ['status', { permission: 'read', run: async () => ({ state: 'ready' }) }],
      ['mutate', { permission: 'control', run: async () => { writes++; return {}; } }],
      ['reflect', { permission: 'read', run: async () => ({ forbidden: controller }) }],
      ['escaped', { permission: 'read', run: async () => ({ forbidden: escapedSecret }) }]
    ]) });
  try {
    assert.deepEqual(await rpc(service.port, identity, reader, 'status', {}), { state: 'ready' });
    await assert.rejects(rpc(service.port, identity, reader, 'mutate', {}), /hot_rpc_denied/);
    await assert.rejects(rpc(service.port, { ...identity, generation: '0' }, controller, 'mutate', {}), /hot_rpc_identity_mismatch/);
    await assert.rejects(rpc(service.port, { ...identity, instanceId: randomUUID() }, controller, 'mutate', {}), /hot_rpc_identity_mismatch/);
    await assert.rejects(rpc(service.port, { ...identity, mode: 'docker' }, controller, 'mutate', {}), /hot_rpc_identity_mismatch/);
    await assert.rejects(rpc(service.port, identity, reader, 'reflect', {}), /hot_rpc_credential_reflection/);
    await assert.rejects(rpc(service.port, identity, reader, 'escaped', {}), /hot_rpc_credential_reflection/);
    assert.equal(writes, 0);
    await rpc(service.port, identity, controller, 'mutate', {});
    assert.equal(writes, 1);
    await assert.rejects(startTransport({ port:service.port, identity, readerToken: reader, controllerToken: controller,
      guard: async () => {}, handlers: new Map() }), /hot_rpc_bind_failed/);
  } finally { await service.close(); }
});

test('preaccepted connections cannot exceed the in-flight bound after peers disconnect', {timeout:8000}, async()=>{
  const token=randomBytes(32).toString('hex');
  const identity:RpcIdentity={instanceId:randomUUID(),mode:'native',generation:'1'};
  const releases:Array<()=>void>=[];
  const service=await startTransport({identity,readerToken:token,controllerToken:randomBytes(32).toString('hex'),guard:async()=>{},
    handlers:new Map([['hold',{permission:'read',run:async()=>new Promise(resolve=>releases.push(()=>resolve({})))}]])});
  const sockets:Array<ReturnType<typeof createConnection>>=[];
  const frame=()=>{
    const data=Buffer.from(JSON.stringify({protocol:'rwb-hot/v1',id:randomUUID(),...identity,op:'hold',params:{},sentAt:Date.now()})).toString('base64url');
    return JSON.stringify({data,proof:createHmac('sha256',token).update(data).digest('hex')})+'\n';
  };
  const wait=async(predicate:()=>boolean)=>{for(let n=0;n<200&&!predicate();n++)await delay(5);assert.ok(predicate());};
  try{
    for(let n=0;n<15;n++){
      const peer=createConnection({host:'127.0.0.1',port:service.port});peer.on('error',()=>{});sockets.push(peer);
      await once(peer,'connect');peer.write(frame());
    }
    await wait(()=>service.metrics().inflight===15);
    for(const peer of sockets)peer.destroy();
    await wait(()=>service.metrics().connections===0);
    const accepted=[];
    for(let n=0;n<16;n++){
      const peer=createConnection({host:'127.0.0.1',port:service.port});peer.on('error',()=>{});sockets.push(peer);accepted.push(peer);
      await once(peer,'connect');
    }
    await wait(()=>service.metrics().connections===16);
    for(const peer of accepted)peer.write(frame());
    await wait(()=>service.metrics().inflight===16&&service.metrics().connections<=1);
    assert.equal(releases.length,16);
  }finally{
    for(const peer of sockets)peer.destroy();
    for(const release of releases)release();
    await service.close();
  }
});
