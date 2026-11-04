/** Bridge to the verified shared runtime. No business service or arbitrary command execution. */
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import crypto from 'node:crypto';
import {pathToFileURL} from 'node:url';

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
  const root=path.join(os.homedir(),'.agents/leon-engineering/runtime');
  const manifest=privateJson(path.join(root,'.leon-engineering-harness-runtime.json'));
  if(!manifest.files?.['resource-lifecycle.mjs'] || !manifest.files?.['lib/resources/lifecycle.mjs'])fail('LIFECYCLE_RUNTIME_REQUIRED');
  const verifier=await import(pathToFileURL(path.join(root,'harness-runtime.mjs')).href);
  if(verifier.verifyHarnessRuntime({runtimeRoot:root}).valid!==true)fail('LIFECYCLE_RUNTIME_UNVERIFIED');
  return import(pathToFileURL(path.join(root,'resource-lifecycle.mjs')).href);
}

export async function finalizeLifecycle({projectRoot,commonDirectory,taskId,receipt,runtime}) {
  if(!/^[a-z0-9][a-z0-9-]{0,79}$/.test(taskId??'') || receipt.taskId!==taskId || receipt.status!=='cleaned'
    || receipt.ci?.status!=='passed' || receipt.verification?.status!=='passed')fail('LIFECYCLE_DELIVERY_UNVERIFIED');
  const parent=path.join(commonDirectory,'leon-engineering/resource-closeout'),state=path.join(parent,taskId);
  const resource=privateJson(path.join(state,'receipt.json'));
  const finalization=privateJson(path.join(state,'git-finalization.json'));
  if(resource.taskId!==taskId || resource.status!=='complete' || resource.ok!==true || resource.cache?.ok!==true
    || resource.blocked?.length || finalization.taskId!==taskId
    || finalization.restoreVerified!==true || finalization.candidateCommit!==receipt.integrationCommit)fail('LIFECYCLE_RECOVERY_UNVERIFIED');
  if(finalization.status!=='complete') {
    if(finalization.status!=='pending')fail('LIFECYCLE_RECOVERY_UNVERIFIED');
    try {
      const {validateCloseoutRecovery}=await import('./git_safety.mjs');
      validateCloseoutRecovery({projectRoot,commonDirectory,taskId,receipt});
    } catch(error) {
      throw Object.assign(new Error('LIFECYCLE_RECOVERY_UNVERIFIED',{cause:error}),{code:'LIFECYCLE_RECOVERY_UNVERIFIED'});
    }
  }
  const engine=runtime??await loadRuntime(),api=engine.createLifecycle();
  const project=fs.realpathSync(projectRoot);
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
  api.reportCache({project,adapter:'rwb-buildkit',bytes:resource.cache.afterBytes,
    receiptSha256:crypto.createHash('sha256').update(fs.readFileSync(path.join(state,'receipt.json'))).digest('hex')});
  return api.event({project,task:taskId,type:'delivery-accepted',proof:{schemaVersion:1,task:taskId,
    revision:receipt.integrationCommit,verification:'passed',source:'rwb-git-safety'}});
}
