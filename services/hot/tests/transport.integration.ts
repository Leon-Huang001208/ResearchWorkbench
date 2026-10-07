import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile,mkdtemp,realpath,chmod } from 'node:fs/promises';
import { resolve,join } from 'node:path';
import { randomUUID,randomBytes } from 'node:crypto';
import postgres from 'postgres';
import { migrate } from '../src/database.ts';
import { initializeIdentity,activateRuntime,withOwnerTransaction } from '../src/control.ts';
import { startTransport,rpc } from '../src/transport.ts';

test('a real database generation switch invalidates a still-listening old socket', async () => {
  const dir = resolve(import.meta.dirname,'../../../logs/hot-stage-zero');
  const receipt = JSON.parse(await readFile(join(dir,'receipt.json'),'utf8'));
  const password = await readFile(join(dir,'password'),'utf8');
  const db = postgres({ host:'127.0.0.1',port:receipt.port,database:'hot_probe',username:'postgres',password,onnotice:()=>{} });
  const schema = `hot_rpc_${randomBytes(5).toString('hex')}`;
  const instance = randomUUID();
  const token = randomBytes(32).toString('hex');
  const path = await realpath(await mkdtemp('/tmp/rwb-hot-rpc-db-'));
  await chmod(path,0o700);
  let service: Awaited<ReturnType<typeof startTransport>> | undefined;
  try {
    await migrate(db,schema);
    await initializeIdentity(db,schema,instance,token);
    const native = await activateRuntime(db,schema,instance,token,'native');
    service = await startTransport({ identity:native,readerToken:randomBytes(32).toString('hex'),controllerToken:token,
      guard:()=>withOwnerTransaction(db,schema,native,async()=>{}),
      handlers:new Map([['status',{permission:'read',run:async()=>({state:'ready'})}]]) });
    assert.deepEqual(await rpc(service.port,native,token,'status',{}),{state:'ready'});
    await activateRuntime(db,schema,instance,token,'docker');
    await assert.rejects(rpc(service.port,native,token,'status',{}),/hot_owner_stale/);
  } finally {
    if(service) await service.close();
    await db.end({timeout:5});
  }
});
