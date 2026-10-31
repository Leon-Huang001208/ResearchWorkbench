import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import {finalizeLifecycle} from '../../scripts/resource_lifecycle.mjs';

test('RWB retires verified task evidence and reports BuildKit into the host budget', async t => {
  const root=fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(),'rwb-lifecycle-')));
  t.after(()=>fs.rmSync(root,{recursive:true,force:true}));
  const commonDirectory=path.join(root,'.git'),state=path.join(commonDirectory,'leon-engineering/resource-closeout/task');
  fs.mkdirSync(path.join(state,'evidence'),{recursive:true});
  fs.writeFileSync(path.join(state,'evidence','sample.log'),'passed');
  fs.writeFileSync(path.join(state,'receipt.json'),JSON.stringify({taskId:'task',ok:true,status:'complete',cache:{ok:true,afterBytes:123},blocked:[]}));
  fs.writeFileSync(path.join(state,'git-finalization.json'),JSON.stringify({taskId:'task',status:'complete',restoreVerified:true,candidateCommit:'a'.repeat(40)}));
  const calls=[];
  const api={isEnrolled:()=>false,enroll:s=>calls.push(['enroll',s]),register:s=>calls.push(['register',s]),
    reportCache:s=>calls.push(['cache',s]),event:s=>{calls.push(['event',s]);return {status:'cleaned',notify:true};}};
  const result=await finalizeLifecycle({projectRoot:root,commonDirectory,taskId:'task',receipt:{taskId:'task',status:'cleaned',integrationCommit:'a'.repeat(40),ci:{status:'passed'},verification:{status:'passed'}},runtime:{createLifecycle:()=>api}});
  assert.equal(result.status,'cleaned');
  assert.equal(calls.find(x=>x[0]==='register')[1].path,path.join(state,'evidence'));
  assert.equal(calls.find(x=>x[0]==='cache')[1].bytes,123);
  assert.equal(calls.at(-1)[1].type,'delivery-accepted');
  assert.equal(calls.some(x=>x[1].type==='deployment-accepted'),false);
  api.status=()=>({tasks:[{project:root,task:'task',phase:'accepted'}],resources:[]});
  await assert.rejects(finalizeLifecycle({projectRoot:root,commonDirectory,taskId:'task',receipt:{taskId:'task',status:'cleaned',integrationCommit:'a'.repeat(40),ci:{status:'passed'},verification:{status:'passed'}},runtime:{createLifecycle:()=>api}}),/LIFECYCLE_LATE_RESOURCE_UNREGISTERED/);
});

test('RWB refuses lifecycle deletion before Git recovery and resource gates finish', async t => {
  const root=fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(),'rwb-lifecycle-gate-')));
  t.after(()=>fs.rmSync(root,{recursive:true,force:true}));
  await assert.rejects(finalizeLifecycle({projectRoot:root,commonDirectory:path.join(root,'.git'),taskId:'task',
    receipt:{taskId:'task',status:'ci_passed'},runtime:{createLifecycle:()=>{throw new Error('must not reach engine');}}}),/LIFECYCLE_DELIVERY_UNVERIFIED/);
});
