/** Bridge to the verified project runtime. No business service or arbitrary command execution. */
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import crypto from 'node:crypto';
import {spawnSync} from 'node:child_process';
import {validateCloseoutRecovery} from './git_safety.mjs';
import {loadProjectResourceRuntime} from './project_delivery_runtime.mjs';

const fail=code=>{throw Object.assign(new Error(code),{code});};
const evidenceProtection='rwb-required-verification-recovery-originals';
function noAliases(filename) {
  let current=path.parse(filename).root;
  for(const part of filename.slice(current.length).split(path.sep)) {
    current=path.join(current,part);
    if(fs.lstatSync(current).isSymbolicLink())fail('LIFECYCLE_ALIAS');
  }
}
function privateJson(filename) {
  noAliases(filename);
  return JSON.parse(fs.readFileSync(filename,'utf8'));
}
const delegationInvalid=()=>fail('LIFECYCLE_CACHE_DELEGATION_INVALID');
const sha256=bytes=>crypto.createHash('sha256').update(bytes).digest('hex');
function exactFields(value,fields) {
  if(!value || typeof value!=='object' || Array.isArray(value) || Object.keys(value).length!==fields.length || Object.keys(value).some(key=>!fields.includes(key)))delegationInvalid();
}
function privateSnapshot(filename,limit) {
  if(typeof process.getuid!=='function')fail('LIFECYCLE_CACHE_DELEGATION_UNSUPPORTED');
  noAliases(filename);
  const fd=fs.openSync(filename,fs.constants.O_RDONLY|fs.constants.O_NOFOLLOW|fs.constants.O_NONBLOCK);
  try {
    const before=fs.fstatSync(fd,{bigint:true});
    if(!before.isFile() || before.nlink!==1n || before.uid!==BigInt(process.getuid()) || (before.mode&0o7777n)!==0o600n || before.size>BigInt(limit))fail('LIFECYCLE_CACHE_DELEGATION_RECORD_INVALID');
    const bytes=Buffer.alloc(Number(before.size));let offset=0;
    while(offset<bytes.length) {const count=fs.readSync(fd,bytes,offset,bytes.length-offset,null);if(!count)fail('LIFECYCLE_CACHE_DELEGATION_CHANGED');offset+=count;}
    const after=fs.fstatSync(fd,{bigint:true});noAliases(filename);
    const current=fs.lstatSync(filename,{bigint:true}),fields=['dev','ino','uid','gid','mode','nlink','size','mtimeNs','ctimeNs'];
    if(BigInt(bytes.length)!==before.size || fields.some(key=>before[key]!==after[key] || before[key]!==current[key]))fail('LIFECYCLE_CACHE_DELEGATION_CHANGED');
    let value;try {value=JSON.parse(bytes);}catch {delegationInvalid();}
    return {value,sha256:sha256(bytes),identity:fields.map(key=>String(before[key])).join(':')};
  } finally {fs.closeSync(fd);}
}
function directoryIdentity(identity) {
  exactFields(identity,['path','dev','ino']);
  if(typeof identity.path!=='string' || !path.isAbsolute(identity.path) || !['dev','ino'].every(key=>typeof identity[key]==='string' && /^(0|[1-9][0-9]*)$/.test(identity[key])))delegationInvalid();
  noAliases(identity.path);const stat=fs.lstatSync(identity.path,{bigint:true});
  if(!stat.isDirectory() || fs.realpathSync(identity.path)!==identity.path || String(stat.dev)!==identity.dev || String(stat.ino)!==identity.ino)fail('LIFECYCLE_CACHE_DELEGATION_IDENTITY');
}
function identityGit(project,args) {
  // Read only repository configuration; inherited Git overrides must not select
  // another repository or inject an origin. Never return origin text to logs.
  const env=Object.fromEntries(Object.entries(process.env).filter(([key])=>!key.startsWith('GIT_')));
  Object.assign(env,{GIT_CONFIG_NOSYSTEM:'1',GIT_CONFIG_GLOBAL:os.devNull,GIT_OPTIONAL_LOCKS:'0',GIT_NO_LAZY_FETCH:'1',GIT_NO_REPLACE_OBJECTS:'1'});
  const result=spawnSync('/usr/bin/git',['--no-optional-locks','-c','gc.auto=0','-c','maintenance.auto=false','-C',project,...args],{encoding:'utf8',env,timeout:8000,maxBuffer:64*1024});
  if(result.error || result.status!==0 || !result.stdout.trim())fail('LIFECYCLE_CACHE_DELEGATION_GIT_IDENTITY');
  return result.stdout.trim();
}
function verifyProjectIdentity(identity) {
  exactFields(identity,['projectRoot','commonDirectory','originSha256']);
  if(typeof identity.originSha256!=='string' || !/^[a-f0-9]{64}$/.test(identity.originSha256))delegationInvalid();
  directoryIdentity(identity.projectRoot);directoryIdentity(identity.commonDirectory);
  const root=identity.projectRoot.path;
  if(identityGit(root,['rev-parse','--show-toplevel'])!==root || path.resolve(root,identityGit(root,['rev-parse','--git-common-dir']))!==identity.commonDirectory.path || sha256(identityGit(root,['remote','get-url','origin']))!==identity.originSha256)fail('LIFECYCLE_CACHE_DELEGATION_IDENTITY');
  directoryIdentity(identity.projectRoot);directoryIdentity(identity.commonDirectory);
}
function cacheDelegation({project,commonDirectory,taskId,resource,resourceFile}) {
  const filename=path.join(commonDirectory,'leon-engineering/cache-report-delegation.json');
  if(!fs.lstatSync(filename,{throwIfNoEntry:false}))return null;
  const record=privateSnapshot(filename,64*1024),grant=record.value;
  exactFields(grant,['schemaVersion','adapter','authorization','owner','reporter','tasks']);
  exactFields(grant.authorization,['source','date','scope']);
  const date=grant.authorization.date,dateValue=typeof date==='string' && /^\d{4}-\d{2}-\d{2}$/.test(date)?Date.parse(date+'T00:00:00.000Z'):NaN;
  if(grant.schemaVersion!==1 || grant.adapter!=='rwb-buildkit' || grant.authorization.source!=='explicit-user' || grant.authorization.scope!=='report-frozen-cache-observation' || !Number.isFinite(dateValue) || new Date(dateValue).toISOString().slice(0,10)!==date || !Array.isArray(grant.tasks) || !grant.tasks.length || grant.tasks.length>32)delegationInvalid();
  const tasks=new Set();
  for(const row of grant.tasks) {
    exactFields(row,['taskId','receiptSha256','afterBytes']);
    if(typeof row.taskId!=='string' || !/^[a-z0-9][a-z0-9-]{0,79}$/.test(row.taskId) || tasks.has(row.taskId) || typeof row.receiptSha256!=='string' || !/^[a-f0-9]{64}$/.test(row.receiptSha256) || !Number.isSafeInteger(row.afterBytes) || row.afterBytes<0)delegationInvalid();
    tasks.add(row.taskId);
  }
  const task=grant.tasks.find(row=>row.taskId===taskId);
  if(!task)fail('LIFECYCLE_CACHE_DELEGATION_TASK');
  verifyProjectIdentity(grant.owner);verifyProjectIdentity(grant.reporter);
  if(grant.reporter.projectRoot.path!==project || grant.reporter.commonDirectory.path!==commonDirectory || grant.owner.originSha256!==grant.reporter.originSha256)fail('LIFECYCLE_CACHE_DELEGATION_IDENTITY');
  const frozen=privateSnapshot(resourceFile,16*1024*1024),builders=resource.cache?.builders;
  if(!builders || typeof builders!=='object' || Array.isArray(builders) || JSON.stringify(Object.keys(builders).sort())!==JSON.stringify(['desktop-linux','rwb-dev-builder']))fail('LIFECYCLE_CACHE_DELEGATION_RECEIPT');
  let total=0;for(const row of Object.values(builders)) {
    if(!Number.isSafeInteger(row?.bytes) || row.bytes<0 || !Number.isSafeInteger(total+row.bytes))fail('LIFECYCLE_CACHE_DELEGATION_RECEIPT');total+=row.bytes;
  }
  if(frozen.sha256!==task.receiptSha256 || JSON.stringify(frozen.value)!==JSON.stringify(resource) || task.afterBytes!==resource.cache.afterBytes || total!==task.afterBytes)fail('LIFECYCLE_CACHE_DELEGATION_RECEIPT');
  return {record,frozen,owner:grant.owner.projectRoot.path,bytes:task.afterBytes};
}
function delegatedOwner(api,delegation) {
  const status=api.status(),previous=status.externalCaches?.['rwb-buildkit'];
  if(!status.projects?.[delegation.owner] || previous?.project!==delegation.owner)fail('LIFECYCLE_CACHE_DELEGATION_OWNER');
  if(previous.bytes!==delegation.bytes || !delegation.record.value.tasks.some(row=>row.afterBytes===previous.bytes && row.receiptSha256===previous.receiptSha256))fail('LIFECYCLE_CACHE_DELEGATION_OBSERVATION');
  return previous;
}
// The shared API exposes its identity schema but no read-only fingerprint or
// protection update. Recheck existing protected archives without registering an
// accepted task again. Keep this schema cross-checked against the real kernel.
function evidenceIdentity(directory) {
  noAliases(directory);
  const entries=[];let bytes=0,count=0;
  const walk=(filename,relative)=>{
    if(++count>100000)fail('LIFECYCLE_EVIDENCE_SCAN_LIMIT');
    const before=fs.lstatSync(filename);
    if(before.isSymbolicLink() || !before.isFile() && !before.isDirectory() || path.basename(filename)==='.git' || before.isFile() && before.nlink!==1)fail('LIFECYCLE_EVIDENCE_INVALID');
    const item=[relative,String(before.dev),String(before.ino),before.mode];
    if(before.isFile()) {
      const fd=fs.openSync(filename,fs.constants.O_RDONLY|fs.constants.O_NOFOLLOW|fs.constants.O_NONBLOCK);
      try {
        const opened=fs.fstatSync(fd),hash=crypto.createHash('sha256'),buffer=Buffer.alloc(1024*1024);
        if(!opened.isFile() || ['dev','ino','mode','size','mtimeMs','nlink'].some(key=>opened[key]!==before[key]))fail('LIFECYCLE_EVIDENCE_CHANGED');
        let length;while((length=fs.readSync(fd,buffer,0,buffer.length,null)))hash.update(buffer.subarray(0,length));
        const after=fs.fstatSync(fd),current=fs.lstatSync(filename);
        if(['dev','ino','mode','size','mtimeMs','nlink'].some(key=>after[key]!==before[key] || current[key]!==before[key]))fail('LIFECYCLE_EVIDENCE_CHANGED');
        bytes+=before.size;item.push(before.size,before.mtimeMs,hash.digest('hex'));
      } finally {fs.closeSync(fd);}
    }
    entries.push(item);
    if(before.isDirectory())for(const name of fs.readdirSync(filename).sort())walk(path.join(filename,name),`${relative}/${name}`);
  };
  walk(directory,'.');
  return {sha256:crypto.createHash('sha256').update(JSON.stringify(entries)).digest('hex'),bytes,entries:count};
}
async function loadRuntime() {
  return loadProjectResourceRuntime();
}

export async function finalizeLifecycle({projectRoot,commonDirectory,taskId,receipt,runtime}) {
  if(!/^[a-z0-9][a-z0-9-]{0,79}$/.test(taskId??'') || receipt.taskId!==taskId || receipt.status!=='cleaned'
    || receipt.ci?.status!=='passed' || receipt.verification?.status!=='passed')fail('LIFECYCLE_DELIVERY_UNVERIFIED');
  const parent=path.join(commonDirectory,'leon-engineering/resource-closeout'),state=path.join(parent,taskId);
  const resourceFile=path.join(state,'receipt.json'),resource=privateJson(resourceFile);
  const finalization=privateJson(path.join(state,'git-finalization.json'));
  if(resource.taskId!==taskId || resource.status!=='complete' || resource.ok!==true || resource.cache?.ok!==true
    || resource.blocked?.length || finalization.taskId!==taskId
    || finalization.restoreVerified!==true || finalization.candidateCommit!==receipt.integrationCommit)fail('LIFECYCLE_RECOVERY_UNVERIFIED');
  if(finalization.status!=='complete') {
    if(finalization.status!=='pending')fail('LIFECYCLE_RECOVERY_UNVERIFIED');
    try {
      validateCloseoutRecovery({projectRoot,commonDirectory,taskId,receipt});
    } catch(error) {
      throw Object.assign(new Error('LIFECYCLE_RECOVERY_UNVERIFIED',{cause:error}),{code:'LIFECYCLE_RECOVERY_UNVERIFIED'});
    }
  }
  const project=fs.realpathSync(projectRoot);
  const delegationInput={project,commonDirectory,taskId,resource,resourceFile},delegation=cacheDelegation(delegationInput);
  const engine=runtime??await loadRuntime(),api=engine.createLifecycle();
  if(delegation)delegatedOwner(api,delegation);
  const roots=api.isEnrolled(project)?api.status().projects[project].roots:[];
  if(!roots.includes(parent))api.enroll({project,roots:[...roots,parent]});
  const evidence=path.join(state,'evidence');
  const status=api.status?.(),registered=status?.resources.filter(row=>row.path===evidence)??[];
  const accepted=status?.tasks.some(t=>t.project===project && t.task===taskId && t.phase!=='active');
  // An event sweeps the whole store. Recognize only the fixed RWB closeout
  // shape, including independent clones/projects, without changing their records.
  for(const row of status?.resources??[]) {
    if(typeof row.path!=='string' || !path.isAbsolute(row.path))continue;
    const closeout=path.dirname(path.dirname(row.path)),ownerTask=path.basename(path.dirname(row.path));
    if(path.basename(row.path)!=='evidence' || path.basename(closeout)!=='resource-closeout' || path.basename(path.dirname(closeout))!=='leon-engineering' || !/^[a-z0-9][a-z0-9-]{0,79}$/.test(ownerTask))continue;
    if(row.protection!==evidenceProtection)fail('LIFECYCLE_REQUIRED_EVIDENCE_UNPROTECTED');
    const owner=row.owners?.[0];
    if(row.state!=='registered' || row.kind!=='temporary' || row.owners?.length!==1 || owner.task!==ownerTask || !status.projects?.[owner.project]?.roots?.some(root=>row.path.startsWith(root+path.sep)))fail('LIFECYCLE_EVIDENCE_REGISTRATION_INVALID');
  }
  if(registered.length>1)fail('LIFECYCLE_EVIDENCE_REGISTRATION_INVALID');
  const existing=registered[0],present=fs.lstatSync(evidence,{throwIfNoEntry:false});
  // Check the ledger even if a previous sweep quarantined the original path.
  // The shared API cannot upgrade protection: never emit a deleting event for
  // old unprotected registrations or silently rewrite their ledger records.
  if(existing) {
    if(existing.protection!==evidenceProtection)fail('LIFECYCLE_REQUIRED_EVIDENCE_UNPROTECTED');
    if(existing.state!=='registered' || existing.kind!=='temporary' || !existing.owners?.some(owner=>owner.project===project && owner.task===taskId))fail('LIFECYCLE_EVIDENCE_REGISTRATION_INVALID');
    if(!present)fail('LIFECYCLE_REQUIRED_EVIDENCE_MISSING');
    const identity=evidenceIdentity(evidence);
    if(['sha256','bytes','entries'].some(key=>identity[key]!==existing.identity?.[key]))fail('LIFECYCLE_EVIDENCE_CHANGED');
  } else if(present) {
    if(accepted)fail('LIFECYCLE_LATE_RESOURCE_UNREGISTERED');
    api.register({project,task:taskId,path:evidence,kind:'temporary',protection:evidenceProtection});
  } else if(resource.evidence?.length) {
    fail('LIFECYCLE_REQUIRED_EVIDENCE_MISSING');
  }
  let cacheReport;
  if(delegation) {
    const current=cacheDelegation(delegationInput);
    if(!current || current.record.sha256!==delegation.record.sha256 || current.record.identity!==delegation.record.identity || current.frozen.identity!==delegation.frozen.identity)fail('LIFECYCLE_CACHE_DELEGATION_CHANGED');
    const previous=delegatedOwner(api,current);
    cacheReport={adapter:'rwb-buildkit',owner:current.owner,reporter:project,receiptSha256:current.frozen.sha256,delegationSha256:current.record.sha256,bytes:current.bytes,observation:'frozen-authorized',previousBytes:previous.bytes,previousSequence:previous.sequence};
  }
  // This remains the shared API's last-observation write, not a CAS or a fresh
  // measurement. Its transaction still rejects a changed adapter owner.
  api.reportCache({project:cacheReport?.owner??project,adapter:'rwb-buildkit',bytes:resource.cache.afterBytes,
    receiptSha256:cacheReport?.receiptSha256??sha256(fs.readFileSync(resourceFile))});
  const result=api.event({project,task:taskId,type:'delivery-accepted',proof:{schemaVersion:1,task:taskId,
    revision:receipt.integrationCommit,verification:'passed',source:'rwb-git-safety'}});
  return cacheReport?{...result,cacheReport}:result;
}
