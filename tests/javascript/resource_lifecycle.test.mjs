import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import crypto from 'node:crypto';
import {spawnSync} from 'node:child_process';
import {finalizeLifecycle} from '../../scripts/resource_lifecycle.mjs';

function cacheDelegationFixture(t) {
  const root=fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(),'rwb-cache-delegation-')));
  t.after(()=>fs.rmSync(root,{recursive:true,force:true}));
  const owner=path.join(root,'owner'),reporter=path.join(root,'reporter'),origin='https://example.invalid/rwb-fixture.git';
  for(const directory of [owner,reporter]) {
    fs.mkdirSync(directory);for(const args of [['init','--quiet'],['remote','add','origin',origin]]) {
      const result=spawnSync('/usr/bin/git',['-c','gc.auto=0','-c','maintenance.auto=false','-C',directory,...args],{encoding:'utf8'});assert.equal(result.status,0,result.stderr);
    }
  }
  const commonDirectory=path.join(reporter,'.git'),state=path.join(commonDirectory,'leon-engineering/resource-closeout/task'),evidence=path.join(state,'evidence');
  fs.mkdirSync(evidence,{recursive:true});fs.writeFileSync(path.join(evidence,'proof.json'),'required');
  const resourceFile=path.join(state,'receipt.json'),resource={taskId:'task',status:'complete',ok:true,blocked:[],cache:{ok:true,afterBytes:375,builders:{'desktop-linux':{bytes:200},'rwb-dev-builder':{bytes:175}}}};
  fs.writeFileSync(resourceFile,JSON.stringify(resource),{mode:0o600});
  fs.writeFileSync(path.join(state,'git-finalization.json'),JSON.stringify({taskId:'task',status:'complete',restoreVerified:true,candidateCommit:'a'.repeat(40)}));
  const hash=file=>crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
  const identity=directory=>{const stat=fs.statSync(directory,{bigint:true});return {path:directory,dev:String(stat.dev),ino:String(stat.ino)};};
  const projectIdentity=directory=>({projectRoot:identity(directory),commonDirectory:identity(path.join(directory,'.git')),originSha256:crypto.createHash('sha256').update(origin).digest('hex')});
  const grant={schemaVersion:1,adapter:'rwb-buildkit',authorization:{source:'explicit-user',date:'2026-11-05',scope:'report-frozen-cache-observation'},owner:projectIdentity(owner),reporter:projectIdentity(reporter),tasks:[{taskId:'task',receiptSha256:hash(resourceFile),afterBytes:375}]};
  const grantFile=path.join(commonDirectory,'leon-engineering/cache-report-delegation.json');
  const writeGrant=()=>{fs.writeFileSync(grantFile,JSON.stringify(grant),{mode:0o600});fs.chmodSync(grantFile,0o600);};writeGrant();
  const calls=[],ledger={projects:{[owner]:{roots:[path.join(owner,'.git')]}},tasks:[],resources:[],externalCaches:{'rwb-buildkit':{project:owner,bytes:375,receiptSha256:grant.tasks[0].receiptSha256,sequence:8}}};
  const api={isEnrolled:project=>Object.hasOwn(ledger.projects,project),status:()=>structuredClone(ledger),
    enroll:spec=>{calls.push(['enroll',spec]);ledger.projects[spec.project]={roots:spec.roots};},register:spec=>{calls.push(['register',spec]);},
    reportCache:spec=>{if(ledger.externalCaches[spec.adapter]?.project!==spec.project)throw Object.assign(new Error('CACHE_ADAPTER_OWNERSHIP_CONFLICT'),{code:'CACHE_ADAPTER_OWNERSHIP_CONFLICT'});calls.push(['cache',spec]);ledger.externalCaches[spec.adapter]={project:spec.project,bytes:spec.bytes,receiptSha256:spec.receiptSha256,sequence:9};},
    event:spec=>{calls.push(['event',spec]);return {status:'cleaned'};}};
  const finalize=(extra={})=>finalizeLifecycle({...extra,projectRoot:reporter,commonDirectory,taskId:'task',receipt:{taskId:'task',status:'cleaned',integrationCommit:'a'.repeat(40),ci:{status:'passed'},verification:{status:'passed'}},runtime:{createLifecycle:()=>api}});
  return {root,owner,reporter,commonDirectory,state,evidence,resource,resourceFile,hash,grant,grantFile,writeGrant,ledger,api,calls,finalize};
}

test('cache delegation reports one frozen observation under its enrolled owner while task APIs keep the reporter',async t=>{
  const f=cacheDelegationFixture(t),receiptBefore=fs.readFileSync(f.resourceFile),result=await f.finalize();
  assert.equal(result.status,'cleaned');
  assert.equal(f.calls.find(([kind])=>kind==='cache')[1].project,f.owner);
  assert.equal(f.calls.find(([kind])=>kind==='cache')[1].bytes,375);
  for(const [kind,spec] of f.calls.filter(([kind])=>kind!=='cache'))assert.equal(spec.project,f.reporter,kind);
  assert.deepEqual(Object.keys(f.ledger.externalCaches),['rwb-buildkit']);
  assert.equal(result.cacheReport.owner,f.owner);assert.equal(result.cacheReport.reporter,f.reporter);
  assert.equal(result.cacheReport.delegationSha256,f.hash(f.grantFile));
  assert.equal(result.cacheReport.receiptSha256,f.hash(f.resourceFile));assert.equal(result.cacheReport.bytes,375);
  assert.equal(result.cacheReport.previousBytes,375);assert.equal(result.cacheReport.previousSequence,8);
  assert.deepEqual(fs.readFileSync(f.resourceFile),receiptBefore);
});

test('cache delegation rejects observations outside the authorized frozen chain or with changed current bytes',async t=>{
  for(const mode of ['outside-chain','different-bytes'])await t.test(mode,async t=>{
    const f=cacheDelegationFixture(t);f.ledger.externalCaches['rwb-buildkit'].receiptSha256='d'.repeat(64);
    if(mode==='different-bytes') {f.ledger.externalCaches['rwb-buildkit'].bytes=374;f.grant.tasks.push({taskId:'other-task',receiptSha256:'d'.repeat(64),afterBytes:374});f.writeGrant();}
    await assert.rejects(f.finalize(),{code:'LIFECYCLE_CACHE_DELEGATION_OBSERVATION'});
    assert.equal(f.calls.some(([kind])=>['cache','event'].includes(kind)),false);
  });
});

test('cache delegation absence preserves the original owner barrier and result shape',async t=>{
  const f=cacheDelegationFixture(t);fs.unlinkSync(f.grantFile);
  await assert.rejects(f.finalize({delegation:f.grant,cacheReportOwner:f.owner}),{code:'CACHE_ADAPTER_OWNERSHIP_CONFLICT'});
  assert.equal(f.calls.some(([kind])=>kind==='event'),false);
  f.ledger.externalCaches['rwb-buildkit'].project=f.reporter;
  const result=await f.finalize();assert.deepEqual(result,{status:'cleaned'});
  assert.equal(f.calls.findLast(([kind])=>kind==='cache')[1].project,f.reporter);
});

test('cache delegation rejects invalid authority, frozen receipt, identities, ledger owner and private records',async t=>{
  const rewriteResource=f=>{fs.writeFileSync(f.resourceFile,JSON.stringify(f.resource));f.grant.tasks[0].receiptSha256=f.hash(f.resourceFile);};
  const cases=[
    ['unknown field',f=>{f.grant.extra=true;},'INVALID'],
    ['unknown nested field',f=>{f.grant.owner.extra=true;},'INVALID'],
    ['non-user source',f=>{f.grant.authorization.source='http';},'INVALID'],
    ['broader scope',f=>{f.grant.authorization.scope='cache-maintenance';},'INVALID'],
    ['invalid calendar date',f=>{f.grant.authorization.date='2026-02-30';},'INVALID'],
    ['unauthorized task',f=>{f.grant.tasks[0].taskId='other-task';},'TASK'],
    ['duplicate task',f=>{f.grant.tasks.push({...f.grant.tasks[0]});},'INVALID'],
    ['receipt digest',f=>{f.grant.tasks[0].receiptSha256='f'.repeat(64);},'RECEIPT'],
    ['receipt bytes',f=>{f.grant.tasks[0].afterBytes=374;},'RECEIPT'],
    ['builder sum',f=>{f.resource.cache.builders['rwb-dev-builder'].bytes=174;rewriteResource(f);},'RECEIPT'],
    ['different builders',f=>{f.resource.cache.builders.other={bytes:0};rewriteResource(f);},'RECEIPT'],
    ['unsafe sum',f=>{f.resource.cache.builders['desktop-linux'].bytes=Number.MAX_SAFE_INTEGER;f.resource.cache.builders['rwb-dev-builder'].bytes=1;rewriteResource(f);},'RECEIPT'],
    ['root identity',f=>{f.grant.owner.projectRoot.ino='0';},'IDENTITY'],
    ['common identity',f=>{f.grant.reporter.commonDirectory={...f.grant.owner.commonDirectory};},'IDENTITY'],
    ['origin changed',f=>{assert.equal(spawnSync('/usr/bin/git',['-C',f.owner,'remote','set-url','origin','https://example.invalid/other.git']).status,0);},'IDENTITY'],
    ['different origin digests',f=>{const url='https://example.invalid/other.git';assert.equal(spawnSync('/usr/bin/git',['-C',f.owner,'remote','set-url','origin',url]).status,0);f.grant.owner.originSha256=crypto.createHash('sha256').update(url).digest('hex');},'IDENTITY'],
    ['missing adapter',f=>{delete f.ledger.externalCaches['rwb-buildkit'];},'OWNER'],
    ['different owner',f=>{f.ledger.externalCaches['rwb-buildkit'].project=f.reporter;},'OWNER'],
    ['owner not enrolled',f=>{delete f.ledger.projects[f.owner];},'OWNER'],
  ];
  for(const [name,mutate,code] of cases)await t.test(name,async t=>{
    const f=cacheDelegationFixture(t);mutate(f);f.writeGrant();
    await assert.rejects(f.finalize(),{code:'LIFECYCLE_CACHE_DELEGATION_'+code});
    assert.equal(f.calls.some(([kind])=>['cache','event'].includes(kind)),false);
  });
  for(const name of ['permissions','hardlink','alias','dangling-alias','oversize','fifo'])await t.test(name,async t=>{
    const f=cacheDelegationFixture(t);
    if(name==='permissions')fs.chmodSync(f.grantFile,0o644);
    if(name==='hardlink')fs.linkSync(f.grantFile,path.join(f.root,'grant-link'));
    if(name==='alias'){const saved=path.join(f.root,'grant-original');fs.renameSync(f.grantFile,saved);fs.symlinkSync(saved,f.grantFile);}
    if(name==='dangling-alias'){fs.unlinkSync(f.grantFile);fs.symlinkSync(path.join(f.root,'missing'),f.grantFile);}
    if(name==='oversize')fs.writeFileSync(f.grantFile,Buffer.alloc(64*1024+1));
    if(name==='fifo'){fs.unlinkSync(f.grantFile);assert.equal(spawnSync('/usr/bin/mkfifo',[f.grantFile]).status,0);fs.chmodSync(f.grantFile,0o600);}
    await assert.rejects(f.finalize(),{code:name.endsWith('alias')?'LIFECYCLE_ALIAS':'LIFECYCLE_CACHE_DELEGATION_RECORD_INVALID'});
    assert.equal(f.calls.some(([kind])=>['cache','event'].includes(kind)),false);
  });
});

test('cache delegation revalidates grant, receipt, root, origin and owner immediately before reporting',async t=>{
  for(const mode of ['grant','grant-removed','same-grant-bytes','receipt','same-receipt-bytes','identity','common','origin','owner','observation','observation-bytes','atomic-owner'])await t.test(mode,async t=>{
    const f=cacheDelegationFixture(t),register=f.api.register,report=f.api.reportCache;
    if(mode==='observation-bytes'){f.grant.tasks.push({taskId:'other-task',receiptSha256:'d'.repeat(64),afterBytes:374});f.writeGrant();}
    f.api.register=spec=>{
      register(spec);
      if(mode==='grant')fs.appendFileSync(f.grantFile,' ');
      if(mode==='grant-removed')fs.unlinkSync(f.grantFile);
      if(mode==='same-grant-bytes'){const bytes=fs.readFileSync(f.grantFile);fs.renameSync(f.grantFile,f.grantFile+'-original');fs.writeFileSync(f.grantFile,bytes,{mode:0o600});}
      if(mode==='receipt')fs.appendFileSync(f.resourceFile,' ');
      if(mode==='same-receipt-bytes'){const bytes=fs.readFileSync(f.resourceFile);fs.renameSync(f.resourceFile,f.resourceFile+'-original');fs.writeFileSync(f.resourceFile,bytes,{mode:0o600});}
      if(mode==='identity'){fs.renameSync(f.owner,f.owner+'-original');fs.mkdirSync(f.owner);}
      if(mode==='common'){const directory=path.join(f.owner,'.git');fs.renameSync(directory,directory+'-original');fs.mkdirSync(directory);}
      if(mode==='origin')assert.equal(spawnSync('/usr/bin/git',['-C',f.reporter,'remote','set-url','origin','https://example.invalid/new.git']).status,0);
      if(mode==='owner')f.ledger.externalCaches['rwb-buildkit'].project=f.reporter;
      if(mode==='observation')f.ledger.externalCaches['rwb-buildkit'].receiptSha256='d'.repeat(64);
      if(mode==='observation-bytes')Object.assign(f.ledger.externalCaches['rwb-buildkit'],{bytes:374,receiptSha256:'d'.repeat(64)});
    };
    if(mode==='atomic-owner')f.api.reportCache=spec=>{f.ledger.externalCaches['rwb-buildkit'].project=f.reporter;return report(spec);};
    const codes={grant:'LIFECYCLE_CACHE_DELEGATION_CHANGED','grant-removed':'LIFECYCLE_CACHE_DELEGATION_CHANGED','same-grant-bytes':'LIFECYCLE_CACHE_DELEGATION_CHANGED',receipt:'LIFECYCLE_CACHE_DELEGATION_RECEIPT','same-receipt-bytes':'LIFECYCLE_CACHE_DELEGATION_CHANGED',identity:'LIFECYCLE_CACHE_DELEGATION_IDENTITY',common:'LIFECYCLE_CACHE_DELEGATION_IDENTITY',origin:'LIFECYCLE_CACHE_DELEGATION_IDENTITY',owner:'LIFECYCLE_CACHE_DELEGATION_OWNER',observation:'LIFECYCLE_CACHE_DELEGATION_OBSERVATION','observation-bytes':'LIFECYCLE_CACHE_DELEGATION_OBSERVATION','atomic-owner':'CACHE_ADAPTER_OWNERSHIP_CONFLICT'};
    await assert.rejects(f.finalize(),{code:codes[mode]});
    assert.equal(f.calls.some(([kind])=>['cache','event'].includes(kind)),false);
  });
});

test('cache delegation ignores inherited Git identity overrides and rejects a changed pinned read',async t=>{
  const f=cacheDelegationFixture(t),saved=new Map(['GIT_DIR','GIT_WORK_TREE','GIT_CONFIG_COUNT','GIT_CONFIG_KEY_0','GIT_CONFIG_VALUE_0'].map(key=>[key,process.env[key]]));
  try {
    Object.assign(process.env,{GIT_DIR:path.join(f.owner,'.git'),GIT_WORK_TREE:f.owner,GIT_CONFIG_COUNT:'1',GIT_CONFIG_KEY_0:'remote.origin.url',GIT_CONFIG_VALUE_0:'https://example.invalid/injected.git'});
    assert.equal((await f.finalize()).cacheReport.owner,f.owner);
  } finally {for(const [key,value] of saved)if(value===undefined)delete process.env[key];else process.env[key]=value;}
  const second=cacheDelegationFixture(t),read=fs.readSync,ino=fs.statSync(second.grantFile).ino;let changed=false;
  fs.readSync=function(file,...args){const count=read.call(this,file,...args);if(!changed&&count>0&&fs.fstatSync(file).ino===ino){changed=true;fs.appendFileSync(second.grantFile,' ');}return count;};
  try {await assert.rejects(second.finalize(),{code:'LIFECYCLE_CACHE_DELEGATION_CHANGED'});}
  finally {fs.readSync=read;}
  assert.equal(changed,true);assert.equal(second.calls.some(([kind])=>['cache','event'].includes(kind)),false);
});

test('RWB protects verified task evidence and reports BuildKit into the host budget', async t => {
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
  assert.equal(calls.find(x=>x[0]==='register')[1].protection,'rwb-required-verification-recovery-originals');
  assert.equal(calls.find(x=>x[0]==='cache')[1].bytes,123);
  assert.equal(calls.at(-1)[1].type,'delivery-accepted');
  assert.equal(calls.some(x=>x[1].type==='deployment-accepted'),false);
  api.status=()=>({tasks:[{project:root,task:'task',phase:'accepted'}],resources:[]});
  await assert.rejects(finalizeLifecycle({projectRoot:root,commonDirectory,taskId:'task',receipt:{taskId:'task',status:'cleaned',integrationCommit:'a'.repeat(40),ci:{status:'passed'},verification:{status:'passed'}},runtime:{createLifecycle:()=>api}}),/LIFECYCLE_LATE_RESOURCE_UNREGISTERED/);
});

test('RWB refuses old unprotected evidence registrations before cache reports or accepting events',async t=>{
  for(const phase of ['active','accepted','other-accepted'])await t.test(phase,async t=>{
    const root=fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(),'rwb-lifecycle-old-')));
    t.after(()=>fs.rmSync(root,{recursive:true,force:true}));
    const commonDirectory=path.join(root,'.git'),state=path.join(commonDirectory,'leon-engineering/resource-closeout/task'),evidence=path.join(state,'evidence');
    fs.mkdirSync(evidence,{recursive:true});fs.writeFileSync(path.join(evidence,'recovery-proof.json'),'keep');
    fs.writeFileSync(path.join(state,'receipt.json'),JSON.stringify({taskId:'task',ok:true,status:'complete',cache:{ok:true,afterBytes:123},blocked:[]}));
    fs.writeFileSync(path.join(state,'git-finalization.json'),JSON.stringify({taskId:'task',status:'complete',restoreVerified:true,candidateCommit:'a'.repeat(40)}));
    const unreachable=()=>{throw new Error('must not mutate old registration or emit events');};
    const owner=phase==='other-accepted'?'other-task':'task';
    const api={isEnrolled:()=>true,status:()=>({projects:{[root]:{roots:[path.dirname(state)]}},tasks:[{project:root,task:owner,phase:phase==='active'?'active':'accepted'}],
      resources:[{path:owner==='task'?evidence:path.join(path.dirname(state),owner,'evidence'),kind:'temporary',state:'registered',owners:[{project:root,task:owner}]}]}),register:unreachable,reportCache:unreachable,event:unreachable};
    await assert.rejects(finalizeLifecycle({projectRoot:root,commonDirectory,taskId:'task',receipt:{taskId:'task',status:'cleaned',integrationCommit:'a'.repeat(40),ci:{status:'passed'},verification:{status:'passed'}},runtime:{createLifecycle:()=>api}}),{code:'LIFECYCLE_REQUIRED_EVIDENCE_UNPROTECTED'});
    assert.equal(fs.readFileSync(path.join(evidence,'recovery-proof.json'),'utf8'),'keep');
  });
});

test('RWB never recreates missing required evidence from an accepted task',async t=>{
  const root=fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(),'rwb-lifecycle-missing-')));
  t.after(()=>fs.rmSync(root,{recursive:true,force:true}));
  const commonDirectory=path.join(root,'.git'),state=path.join(commonDirectory,'leon-engineering/resource-closeout/task');
  fs.mkdirSync(state,{recursive:true});
  fs.writeFileSync(path.join(state,'receipt.json'),JSON.stringify({taskId:'task',ok:true,status:'complete',cache:{ok:true,afterBytes:123},blocked:[],evidence:[{status:'preserved',archive:path.join(state,'evidence/required/logs')}]}));
  fs.writeFileSync(path.join(state,'git-finalization.json'),JSON.stringify({taskId:'task',status:'complete',restoreVerified:true,candidateCommit:'a'.repeat(40)}));
  const unreachable=()=>{throw new Error('must not recreate required evidence or emit events');};
  const api={isEnrolled:()=>true,status:()=>({projects:{[root]:{roots:[path.dirname(state)]}},tasks:[{project:root,task:'task',phase:'accepted'}],resources:[]}),register:unreachable,reportCache:unreachable,event:unreachable};
  await assert.rejects(finalizeLifecycle({projectRoot:root,commonDirectory,taskId:'task',receipt:{taskId:'task',status:'cleaned',integrationCommit:'a'.repeat(40),ci:{status:'passed'},verification:{status:'passed'}},runtime:{createLifecycle:()=>api}}),{code:'LIFECYCLE_REQUIRED_EVIDENCE_MISSING'});
  assert.equal(fs.existsSync(path.join(state,'evidence')),false);
});

test('RWB refuses lifecycle deletion before Git recovery and resource gates finish', async t => {
  const root=fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(),'rwb-lifecycle-gate-')));
  t.after(()=>fs.rmSync(root,{recursive:true,force:true}));
  await assert.rejects(finalizeLifecycle({projectRoot:root,commonDirectory:path.join(root,'.git'),taskId:'task',
    receipt:{taskId:'task',status:'ci_passed'},runtime:{createLifecycle:()=>{throw new Error('must not reach engine');}}}),/LIFECYCLE_DELIVERY_UNVERIFIED/);
});
