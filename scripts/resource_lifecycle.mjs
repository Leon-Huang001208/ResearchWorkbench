/** Bridge to the verified shared runtime. No business service or arbitrary command execution. */
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import crypto from 'node:crypto';
import {pathToFileURL} from 'node:url';

const fail=code=>{throw Object.assign(new Error(code),{code});};
function privateJson(filename) {
  let current=path.parse(filename).root;
  for(const part of filename.slice(current.length).split(path.sep)) {
    current=path.join(current,part);
    if(fs.lstatSync(current).isSymbolicLink())fail('LIFECYCLE_ALIAS');
  }
  return JSON.parse(fs.readFileSync(filename,'utf8'));
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
    || resource.blocked?.length || finalization.taskId!==taskId || finalization.status!=='complete'
    || finalization.restoreVerified!==true || finalization.candidateCommit!==receipt.integrationCommit)fail('LIFECYCLE_RECOVERY_UNVERIFIED');
  const engine=runtime??await loadRuntime(),api=engine.createLifecycle();
  const project=fs.realpathSync(projectRoot);
  const roots=api.isEnrolled(project)?api.status().projects[project].roots:[];
  if(!roots.includes(parent))api.enroll({project,roots:[...roots,parent]});
  const evidence=path.join(state,'evidence');
  // Idempotent status must not re-register accepted resources or recreate deleted archives.
  if(fs.existsSync(evidence)) {
    const status=api.status?.();
    const accepted=status?.tasks.some(t=>t.project===project && t.task===taskId && t.phase!=='active');
    if(accepted && !status.resources.some(r=>r.path===evidence))fail('LIFECYCLE_LATE_RESOURCE_UNREGISTERED');
    if(!accepted)api.register({project,task:taskId,path:evidence,kind:'temporary'});
  }
  api.reportCache({project,adapter:'rwb-buildkit',bytes:resource.cache.afterBytes,
    receiptSha256:crypto.createHash('sha256').update(fs.readFileSync(path.join(state,'receipt.json'))).digest('hex')});
  return api.event({project,task:taskId,type:'delivery-accepted',proof:{schemaVersion:1,task:taskId,
    revision:receipt.integrationCommit,verification:'passed',source:'rwb-git-safety'}});
}
