// Explicit host integration contract: run with node --test on a host with the
// verified shared runtime installed. Generic repository CI uses the bridge unit contract.
import assert from 'node:assert/strict';
import crypto from 'node:crypto';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import {pathToFileURL} from 'node:url';
import {spawnSync} from 'node:child_process';
import {finalizeLifecycle} from '../../../scripts/resource_lifecycle.mjs';

const kernel=path.join(os.homedir(),'.agents/leon-engineering/runtime/lib/resources/lifecycle.mjs');
const {createLifecycle}=await import(pathToFileURL(kernel).href);
const hash=file=>crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
const protection='rwb-required-verification-recovery-originals';
const proof={schemaVersion:1,task:'task',revision:'a'.repeat(40),verification:'passed',source:'rwb-git-safety'};

function fixture(t,options={}) {
  const root=fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(),'rwb-lifecycle-kernel-')));
  t.after(()=>fs.rmSync(root,{recursive:true,force:true}));
  const projectRoot=path.join(root,'project'),commonDirectory=path.join(projectRoot,'.git');
  const state=path.join(commonDirectory,'leon-engineering/resource-closeout/task'), evidence=path.join(state,'evidence');
  fs.mkdirSync(evidence,{recursive:true});
  fs.writeFileSync(path.join(evidence,'final-receipt.json'),'{"final":true}\n');
  fs.writeFileSync(path.join(evidence,'recovery-proof.json'),'{"restoreVerified":true}\n');
  fs.writeFileSync(path.join(state,'receipt.json'),JSON.stringify({taskId:'task',ok:true,status:'complete',cache:{ok:true,afterBytes:123},blocked:[]}));
  fs.writeFileSync(path.join(state,'git-finalization.json'),JSON.stringify({taskId:'task',status:'complete',restoreVerified:true,candidateCommit:'a'.repeat(40)}));
  const receipt={taskId:'task',status:'cleaned',integrationCommit:'a'.repeat(40),ci:{status:'passed'},verification:{status:'passed'}};
  const api=createLifecycle({storeRoot:path.join(root,'store'),occupancy:()=> 'idle',...options});
  const finalize=()=>finalizeLifecycle({projectRoot,commonDirectory,taskId:'task',receipt,runtime:{createLifecycle:()=>api}});
  return {root,projectRoot,commonDirectory,state,evidence,api,finalize};
}

test('real kernel retains required verification and recovery originals after accepted delivery',async t=>{
  const kernelBefore=hash(kernel);let quarantined=0;
  const f=fixture(t,{afterQuarantine:()=>{quarantined++;}});
  const original=Object.fromEntries(fs.readdirSync(f.evidence).map(name=>[name,hash(path.join(f.evidence,name))]));
  const result=await f.finalize();
  assert.equal(fs.existsSync(f.evidence),true,'required archive must remain at its original path');
  for(const [name,digest] of Object.entries(original))assert.equal(hash(path.join(f.evidence,name)),digest);
  assert.equal(result.status,'cleaned');
  assert.equal(result.items.find(row=>row.path===f.evidence)?.reason,'protected');
  assert.equal(result.reclaimed.length,0);assert.equal(quarantined,0);
  const status=f.api.status();
  assert.equal(status.tasks.find(row=>row.task==='task').phase,'accepted');
  assert.equal(status.externalCaches['rwb-buildkit'].bytes,123);
  const registered=status.resources.find(row=>row.path===f.evidence);
  assert.equal(registered.protection,protection);
  assert.equal((await f.finalize()).status,'cleaned');
  assert.equal(f.api.status().resources.find(row=>row.path===f.evidence).id,registered.id);
  assert.equal(quarantined,0);
  assert.equal(hash(kernel),kernelBefore,'shared kernel source must remain unchanged');
});

function register(f,protectedArchive=false) {
  f.api.enroll({project:f.projectRoot,roots:[path.dirname(f.state)]});
  return f.api.register({project:f.projectRoot,task:'task',path:f.evidence,kind:'temporary',...(protectedArchive?{protection}:{})});
}

test('real kernel preserves pre-registered protected active and accepted archives without re-registration',async t=>{
  for(const accepted of [false,true])await t.test(accepted?'accepted':'active',async t=>{
    const f=fixture(t),resource=register(f,true);
    if(accepted)f.api.event({project:f.projectRoot,task:'task',type:'delivery-accepted',proof});
    assert.equal((await f.finalize()).status,'cleaned');
    assert.equal(f.api.status().resources.find(row=>row.path===f.evidence).id,resource.id);
  });
});

test('real kernel old unprotected active, accepted and quarantined archives fail before another event',async t=>{
  for(const mode of ['active','accepted','quarantined'])await t.test(mode,async t=>{
    const f=fixture(t,mode==='accepted'?{occupancy:()=> 'busy'}:mode==='quarantined'?{afterQuarantine:()=>{throw Object.assign(new Error('INTERRUPTED'),{code:'INTERRUPTED'});}}:{});
    register(f);
    if(mode!=='active')f.api.event({project:f.projectRoot,task:'task',type:'delivery-accepted',proof});
    const before=f.api.status(),resource=before.resources.find(row=>row.path===f.evidence);
    const directory=resource.quarantine??f.evidence,digest=hash(path.join(directory,'recovery-proof.json'));
    await assert.rejects(f.finalize(),{code:'LIFECYCLE_REQUIRED_EVIDENCE_UNPROTECTED'});
    assert.deepEqual(f.api.status(),before);
    assert.equal(hash(path.join(directory,'recovery-proof.json')),digest);
  });
});

test('real kernel protected archive identity, aliases and missing originals stay fail closed',async t=>{
  for(const mode of ['changed','symlink','missing'])await t.test(mode,async t=>{
    const f=fixture(t);register(f,true);
    f.api.event({project:f.projectRoot,task:'task',type:'delivery-accepted',proof});
    if(mode==='changed')fs.appendFileSync(path.join(f.evidence,'final-receipt.json'),'changed');
    if(mode==='symlink') {const moved=f.evidence+'-original';fs.renameSync(f.evidence,moved);fs.symlinkSync(moved,f.evidence);}
    if(mode==='missing')fs.renameSync(f.evidence,f.evidence+'-original');
    const before=f.api.status();
    await assert.rejects(f.finalize(),{code:mode==='changed'?'LIFECYCLE_EVIDENCE_CHANGED':mode==='symlink'?'LIFECYCLE_ALIAS':'LIFECYCLE_REQUIRED_EVIDENCE_MISSING'});
    assert.deepEqual(f.api.status(),before);
    assert.equal(fs.lstatSync(f.evidence,{throwIfNoEntry:false})?.isSymbolicLink()??false,mode==='symlink');
  });
});

test('real kernel unrelated occupied resource still blocks cleanup while required archive is protected',async t=>{
  const f=fixture(t,{occupancy:()=> 'busy'});register(f,true);
  const other=path.join(f.state,'other');fs.mkdirSync(other);fs.writeFileSync(path.join(other,'keep'),'busy');
  f.api.register({project:f.projectRoot,task:'other',path:other,kind:'temporary'});
  f.api.event({project:f.projectRoot,task:'other',type:'delivery-accepted',proof:{...proof,task:'other'}});
  const result=await f.finalize();
  assert.equal(result.status,'blocked');
  assert.equal(result.items.find(row=>row.path===other).reason,'RESOURCE_BUSY');
  assert.equal(result.items.find(row=>row.path===f.evidence).reason,'protected');
  assert.equal(fs.readFileSync(path.join(other,'keep'),'utf8'),'busy');
  assert.equal(fs.existsSync(f.evidence),true);
});

test('real kernel another accepted RWB task cannot lose required originals to this delivery sweep',async t=>{
  let busy=true;
  const f=fixture(t,{occupancy:()=>busy?'busy':'idle'});register(f,true);
  const other=path.join(path.dirname(f.state),'old-task','evidence');fs.mkdirSync(other,{recursive:true});
  const original=path.join(other,'recovery-proof.json');fs.writeFileSync(original,'required old-task proof');
  f.api.register({project:f.projectRoot,task:'old-task',path:other,kind:'temporary'});
  f.api.event({project:f.projectRoot,task:'old-task',type:'delivery-accepted',proof:{...proof,task:'old-task'}});
  busy=false;
  await assert.rejects(f.finalize(),{code:'LIFECYCLE_REQUIRED_EVIDENCE_UNPROTECTED'});
  assert.equal(fs.readFileSync(original,'utf8'),'required old-task proof');
  assert.equal(f.api.status().tasks.find(row=>row.task==='task').phase,'active');
});

test('real kernel another RWB project cannot lose required originals to this delivery sweep',async t=>{
  let busy=true;
  const f=fixture(t,{occupancy:()=>busy?'busy':'idle'});register(f,true);
  const project=path.join(f.root,'other-project'),parent=path.join(project,'.git/leon-engineering/resource-closeout');
  const other=path.join(parent,'old-task','evidence');fs.mkdirSync(other,{recursive:true});
  const original=path.join(other,'recovery-proof.json');fs.writeFileSync(original,'required other-project proof');
  f.api.enroll({project,roots:[parent]});f.api.register({project,task:'old-task',path:other,kind:'temporary'});
  f.api.event({project,task:'old-task',type:'delivery-accepted',proof:{...proof,task:'old-task'}});
  busy=false;
  await assert.rejects(f.finalize(),{code:'LIFECYCLE_REQUIRED_EVIDENCE_UNPROTECTED'});
  assert.equal(fs.readFileSync(original,'utf8'),'required other-project proof');
  assert.equal(f.api.status().tasks.find(row=>row.project===f.projectRoot && row.task==='task').phase,'active');
});

test('real kernel cache delegation preserves its single owner and keeps accepted evidence with the reporter',async t=>{
  const kernelBefore=hash(kernel),f=fixture(t),owner=path.join(f.root,'cache-owner'),origin='https://example.invalid/kernel-fixture.git';
  fs.mkdirSync(owner);
  for(const directory of [owner,f.projectRoot])for(const args of [['init','--quiet'],['remote','add','origin',origin]]) {
    const result=spawnSync('/usr/bin/git',['-c','gc.auto=0','-c','maintenance.auto=false','-C',directory,...args],{encoding:'utf8'});assert.equal(result.status,0,result.stderr);
  }
  const ownerRoot=path.join(owner,'cache-root');fs.mkdirSync(ownerRoot);f.api.enroll({project:owner,roots:[ownerRoot]});
  f.api.reportCache({project:owner,adapter:'rwb-buildkit',bytes:532,receiptSha256:'b'.repeat(64)});
  const resourceFile=path.join(f.state,'receipt.json'),resource=JSON.parse(fs.readFileSync(resourceFile));
  resource.cache.afterBytes=375;resource.cache.builders={'desktop-linux':{bytes:200},'rwb-dev-builder':{bytes:175}};
  fs.writeFileSync(resourceFile,JSON.stringify(resource));fs.chmodSync(resourceFile,0o600);
  const frozen=fs.readFileSync(resourceFile),evidence=hash(path.join(f.evidence,'recovery-proof.json'));
  await assert.rejects(f.finalize(),{code:'CACHE_ADAPTER_OWNERSHIP_CONFLICT'});
  assert.equal(f.api.status().externalCaches['rwb-buildkit'].bytes,532);
  // An independently authorized owner-side report has already established the
  // frozen observation. The bridge may only reuse that authorized chain.
  f.api.reportCache({project:owner,adapter:'rwb-buildkit',bytes:375,receiptSha256:hash(resourceFile)});
  const identity=directory=>{const stat=fs.statSync(directory,{bigint:true});return {path:directory,dev:String(stat.dev),ino:String(stat.ino)};};
  const project=directory=>({projectRoot:identity(directory),commonDirectory:identity(path.join(directory,'.git')),originSha256:crypto.createHash('sha256').update(origin).digest('hex')});
  const grant={schemaVersion:1,adapter:'rwb-buildkit',authorization:{source:'explicit-user',date:'2026-11-05',scope:'report-frozen-cache-observation'},owner:project(owner),reporter:project(f.projectRoot),tasks:[{taskId:'task',receiptSha256:hash(resourceFile),afterBytes:375}]};
  const filename=path.join(f.commonDirectory,'leon-engineering/cache-report-delegation.json');fs.writeFileSync(filename,JSON.stringify(grant),{mode:0o600});
  const result=await f.finalize(),status=f.api.status();
  assert.equal(result.status,'cleaned');assert.equal(result.cacheReport.owner,owner);assert.equal(result.cacheReport.reporter,f.projectRoot);
  assert.deepEqual(Object.keys(status.externalCaches),['rwb-buildkit']);assert.equal(status.externalCaches['rwb-buildkit'].project,owner);assert.equal(status.externalCaches['rwb-buildkit'].bytes,375);
  assert.equal(status.tasks.find(row=>row.task==='task').project,f.projectRoot);
  assert.equal(status.resources.find(row=>row.path===f.evidence).owners[0].project,f.projectRoot);
  assert.equal(hash(path.join(f.evidence,'recovery-proof.json')),evidence);assert.deepEqual(fs.readFileSync(resourceFile),frozen);
  assert.equal((await f.finalize()).cacheReport.previousBytes,375);
  assert.deepEqual(Object.keys(f.api.status().externalCaches),['rwb-buildkit']);
  f.api.reportCache({project:owner,adapter:'rwb-buildkit',bytes:375,receiptSha256:'f'.repeat(64)});
  await assert.rejects(f.finalize(),{code:'LIFECYCLE_CACHE_DELEGATION_OBSERVATION'});
  assert.equal(f.api.status().externalCaches['rwb-buildkit'].receiptSha256,'f'.repeat(64));assert.equal(hash(kernel),kernelBefore);
});
