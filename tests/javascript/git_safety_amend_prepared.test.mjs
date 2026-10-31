import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import crypto from 'node:crypto';
import {spawnSync} from 'node:child_process';
import {runDelivery, parseCli, backupRepository} from '../../scripts/git_safety.mjs';
import {withBackupLock, fingerprint, readManifest} from '../../scripts/git_backup_store.mjs';

function git(root, args) {
  const result = spawnSync('/usr/bin/git', ['-c', 'gc.auto=0', '-c', 'maintenance.auto=false', '-C', root, ...args], {encoding:'utf8'});
  assert.equal(result.status, 0, result.stderr);
  return result.stdout.trim();
}
function fixture(t) {
  const root = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), 'unpublished-prepare-amend-20261029-f66ce16a-')));
  t.after(() => fs.rmSync(root, {recursive:true, force:true}));
  const projectRoot = path.join(root, 'repo'); fs.mkdirSync(projectRoot);
  git(projectRoot, ['init', '-b', 'master']);
  git(projectRoot, ['config', 'user.name', 'Fixture']); git(projectRoot, ['config', 'user.email', 'fixture@example.invalid']);
  fs.writeFileSync(path.join(projectRoot, 'base.txt'), 'base\n'); git(projectRoot, ['add', '.']); git(projectRoot, ['commit', '-m', 'base']);
  fs.appendFileSync(path.join(projectRoot, '.git/info/exclude'), '\nlogs/\n');
  const base = git(projectRoot, ['rev-parse', 'HEAD']);
  git(projectRoot, ['remote', 'add', 'origin', 'https://github.com/fixture/repo.git']); git(projectRoot, ['update-ref', 'refs/remotes/origin/master', base]);
  const feature = path.join(root, 'feature'), integration = path.join(root, 'integration');
  git(projectRoot, ['worktree', 'add', '-b', 'codex/task-feature', feature]);
  fs.writeFileSync(path.join(feature, 'feature.txt'), 'feature\n'); git(feature, ['add', '.']); git(feature, ['commit', '-m', 'feature']);
  const oldFeature = git(feature, ['rev-parse', 'HEAD']);
  git(projectRoot, ['worktree', 'add', '-b', 'codex/integrate-task', integration, base]);
  git(integration, ['merge', '--no-ff', '--no-edit', oldFeature]);
  const previous = git(integration, ['rev-parse', 'HEAD']);
  fs.writeFileSync(path.join(feature, 'index.txt'), 'generated repair\n'); git(feature, ['add', '.']); git(feature, ['commit', '-m', 'repair']);
  const newFeature = git(feature, ['rev-parse', 'HEAD']);
  git(integration, ['merge', '--no-ff', '--no-edit', newFeature]);
  const candidate = git(integration, ['rev-parse', 'HEAD']);
  const receipt = {schemaVersion:1, taskId:'task', repositoryRoot:projectRoot, remote:'origin', remoteUrl:'https://github.com/fixture/repo.git', defaultBranch:'master', baseCommit:base, featureBranch:'codex/task-feature', featureWorktree:feature, featureCommit:oldFeature, integrationBranch:'codex/integrate-task', integrationWorktree:integration, integrationCommit:previous, integrationHistory:[], remoteCommit:null, mode:null, pullRequest:null, status:'prepared', repairAttempts:0, verification:{status:'passed'}, ci:{status:'pending', runs:[]}, rollback:{status:'not_run'}, cleanup:{featureWorktreeRemoved:false,integrationWorktreeRemoved:false,localBranchDeleted:false,remoteBranchDeleted:false}};
  const filename = path.join(projectRoot, '.git/leon-engineering/deliveries/task.json'); fs.mkdirSync(path.dirname(filename), {recursive:true}); fs.writeFileSync(filename, JSON.stringify(receipt), {mode:0o600});
  const ledger = path.join(projectRoot, '.git/leon-engineering/resource-closeout/task/resources.json'); fs.mkdirSync(path.dirname(ledger), {recursive:true});
  fs.writeFileSync(ledger, JSON.stringify({taskId:'task', roots:Object.fromEntries([feature,integration].map(p=>{const s=fs.statSync(p);return [p,[s.dev,s.ino]];})), directories:[]}), {mode:0o600});
  const calls=[], server={base, beforeRead:()=>{}, published:false, runs:false};
  const githubRunner=(_exe,args)=>{
    calls.push(args); server.beforeRead(args);
    const endpoint=args[1]; let value;
    if(args.includes('--include')) {
      const sha=endpoint.split('/').at(-1);
      if(sha===base)return server.baseCommitResponse??{status:0,stdout:`HTTP/2.0 200 OK\r\ncontent-type: application/json\r\n\r\n${JSON.stringify({sha})}`,stderr:''};
      if(server.commitResponse)return server.commitResponse(sha);
      if(server.commitError)return {status:1,stdout:`HTTP/2.0 ${server.commitError}\r\ncontent-type: application/json\r\n\r\n{"message":"Not Found"}`,stderr:''};
      return server.commitKnown?{status:0,stdout:`HTTP/2.0 200 OK\r\ncontent-type: application/json\r\n\r\n${JSON.stringify({sha})}`,stderr:''}:{status:1,stdout:'HTTP/2.0 404 Not Found\r\ncontent-type: application/json\r\n\r\n{"message":"Not Found"}',stderr:''};
    }
    if (endpoint==='repos/fixture/repo/git/ref/heads/master') value={object:{sha:server.base}};
    else if (endpoint.startsWith('repos/fixture/repo/git/matching-refs/heads/')) value=server.published?[{ref:'published'}]:[];
    else if (endpoint.startsWith('repos/fixture/repo/pulls?')) value=server.published?[{number:1}]:[];
    else if (endpoint.includes('/actions/runs?')) value={total_count:server.runs||[...(server.runCommits??[])].some(sha=>endpoint.includes(sha))?1:0,workflow_runs:[]};
    else if (endpoint.endsWith('/check-runs')) value={total_count:server.runs?1:0,check_runs:[]};
    else if (endpoint.endsWith('/status')) value={total_count:server.runs?1:0,statuses:[]};
    else assert.fail('unexpected remote operation '+args.join(' '));
    return {status:0,stdout:JSON.stringify(value),stderr:''};
  };
  const options={gitPath:'/usr/bin/git',platform:'darwin',identityRoot:projectRoot,backupRoot:path.join(root,'backups'),processProbe:()=>false,githubRunner,controller:{readDeliveryReceipt:()=>JSON.parse(fs.readFileSync(filename)),prepareDelivery:()=>assert.fail('destructive shared prepare called')}};
  return {root,projectRoot,feature,integration,base,previous,oldFeature,newFeature,candidate,receipt,filename,ledger,options,calls,server};
}
const amend=f=>runDelivery({projectRoot:f.projectRoot,taskId:'task',action:'prepare',amendPrepared:true},f.options);

test('explicit prepared amendment adopts a same-base descendant with real restore and immutable history', async t=>{
  const f=fixture(t), before=fs.readFileSync(f.filename), refs=git(f.projectRoot,['show-ref']);
  const result=await amend(f);
  assert.equal(result.integrationCommit,f.candidate);assert.equal(result.featureCommit,f.newFeature);assert.equal(result.baseCommit,f.base);
  assert.equal(result.status,'prepared');assert.equal(result.mode,null);assert.equal(result.pullRequest,null);assert.equal(result.remoteCommit,null);
  assert.equal(result.verification,null);assert.deepEqual(result.ci,{status:'pending',runs:[]});assert.equal(result.repairAttempts,0);assert.deepEqual(result.integrationHistory,[]);
  assert.deepEqual(fs.readFileSync(result.preparedAmendment.receiptSnapshot),before);
  assert.equal(result.preparedAmendment.restoreVerified,true);assert.ok(fs.existsSync(path.join(result.preparedAmendment.backupDirectory,'manifest.json')));
  for(const line of refs.split('\n')) assert.ok(git(f.projectRoot,['show-ref']).includes(line));
  assert.equal(git(f.integration,['rev-parse','HEAD']),f.candidate);
});

test('prepared amendment accepts controller mergeSourceCommit only when bound to the old feature', async t=>{
  const f=fixture(t),withSource={...f.receipt,mergeSourceCommit:f.oldFeature};
  fs.writeFileSync(f.filename,JSON.stringify(withSource));
  const result=await amend(f);
  assert.equal(result.status,'prepared');
  assert.equal(result.featureCommit,f.newFeature);
  assert.equal(result.mergeSourceCommit,f.newFeature);
  assert.equal(result.integrationCommit,f.candidate);
});

test('prepared amendment rejects controller mergeSourceCommit inconsistent with old feature', async t=>{
  const f=fixture(t),withSource={...f.receipt,mergeSourceCommit:'f'.repeat(40)};
  fs.writeFileSync(f.filename,JSON.stringify(withSource));
  const before=fs.readFileSync(f.filename);
  await assert.rejects(amend(f),{code:'UNPUBLISHED_STATE_INVALID'});
  assert.deepEqual(fs.readFileSync(f.filename),before);
});

test('CLI accepts only the explicit prepare amendment combination and leaves replacement blocked', async t=>{
  assert.equal(parseCli(['delivery','--project','/repo','--task-id','task','--prepare','--amend-prepared']).options.amendPrepared,true);
  for(const args of [['--publish','--amend-prepared'],['--prepare','--amend-prepared','--replace-prepared']]) assert.throws(()=>parseCli(['delivery','--project','/repo','--task-id','task',...args]));
  const f=fixture(t);await assert.rejects(runDelivery({projectRoot:f.projectRoot,taskId:'task',action:'prepare',replacePrepared:true},f.options),{code:'PREPARE_REMOVAL_BLOCKED'});
});

for(const patch of [{status:'remote_moved'},{status:'ci_passed'},{mode:undefined},{mode:'pr'},{pullRequest:{}},{remoteCommit:'1'.repeat(40)},{publishedAt:null},{pushResult:{}},{mergeCommit:null},{ci:{status:'passed',runs:[]}},{ci:{status:'pending',runs:[{id:1}]}},{rollback:{status:'complete'}},{cleanup:{remoteBranchDeleted:true}}]) test('rejects publication ambiguity '+JSON.stringify(patch), async t=>{
  const f=fixture(t);fs.writeFileSync(f.filename,JSON.stringify({...f.receipt,...patch}));const before=fs.readFileSync(f.filename);
  await assert.rejects(amend(f));assert.deepEqual(fs.readFileSync(f.filename),before);assert.equal(f.calls.length,0);
});

for(const kind of ['dirty-feature','dirty-integration','foreign-branch','replaced-worktree','missing-ledger','occupied','unknown-process','missing-feature','missing-previous','missing-base','no-merge','remote','published','ci']) test('prepared amendment rejects '+kind+' without replacing resources', async t=>{
  const f=fixture(t), before=fs.readFileSync(f.filename);
  if(kind.startsWith('dirty-'))fs.writeFileSync(path.join(kind==='dirty-feature'?f.feature:f.integration,'keep.txt'),'keep');
  if(kind==='foreign-branch')git(f.feature,['switch','-c','codex/foreign-feature']);
  if(kind==='replaced-worktree') {
    const value=JSON.parse(fs.readFileSync(f.ledger));value.roots[f.integration][1]++;fs.writeFileSync(f.ledger,JSON.stringify(value));
  }
  if(kind==='missing-ledger')fs.renameSync(f.ledger,f.ledger+'.saved');
  if(kind==='occupied')f.options.processProbe=()=>true;
  if(kind==='unknown-process')f.options.processProbe=()=>{throw Object.assign(new Error('unknown'),{code:'PROCESS_PROBE_FAILED'});};
  if(kind==='missing-feature') {git(f.integration,['checkout','-B',f.receipt.integrationBranch,f.previous]);git(f.integration,['commit','--allow-empty','-m','unrelated repair']);}
  if(kind==='missing-previous') {git(f.integration,['checkout','-B',f.receipt.integrationBranch,f.newFeature]);git(f.integration,['commit','--allow-empty','-m','omits previous']);}
  if(kind==='missing-base') {f.receipt.baseCommit=f.newFeature;fs.writeFileSync(f.filename,JSON.stringify(f.receipt));git(f.projectRoot,['update-ref','refs/remotes/origin/master',f.newFeature]);f.server.base=f.newFeature;}
  if(kind==='no-merge')git(f.integration,['commit','--allow-empty','-m','not the normal merge']);
  if(kind==='remote')f.server.base='1'.repeat(40);
  if(kind==='published')f.server.published=true;
  if(kind==='ci')f.server.runs=true;
  const current=fs.readFileSync(f.filename);await assert.rejects(amend(f));assert.deepEqual(fs.readFileSync(f.filename),current);
  assert.ok(fs.existsSync(f.feature));assert.ok(fs.existsSync(f.integration));if(kind!=='missing-base')assert.deepEqual(current,before);
});

for(const kind of ['receipt','feature','candidate','remote','remote-ref','url','inode','ledger','native-lock']) test('prepared amendment CAS rejects network-time '+kind+' drift', async t=>{
  const f=fixture(t), before=fs.readFileSync(f.filename);let reads=0;
  f.server.beforeRead=()=>{
    if(++reads!==12)return;
    if(kind==='receipt')fs.writeFileSync(f.filename,JSON.stringify({...f.receipt,repairAttempts:2}));
    if(kind==='feature'||kind==='candidate')git(kind==='feature'?f.feature:f.integration,['commit','--allow-empty','-m','concurrent work']);
    if(kind==='remote')f.server.base='1'.repeat(40);
    if(kind==='remote-ref')git(f.projectRoot,['update-ref','refs/remotes/origin/master',f.oldFeature]);
    if(kind==='url')git(f.projectRoot,['remote','set-url','origin','https://github.com/fixture/other.git']);
    if(kind==='inode'){fs.renameSync(f.integration,f.integration+'.saved');fs.mkdirSync(f.integration);}
    if(kind==='ledger')fs.appendFileSync(f.ledger,' ');
    if(kind==='native-lock')fs.writeFileSync(path.join(f.projectRoot,'.git/index.lock'),'keep');
  };
  await assert.rejects(amend(f));
  if(kind==='receipt')assert.equal(JSON.parse(fs.readFileSync(f.filename)).repairAttempts,2);else assert.deepEqual(fs.readFileSync(f.filename),before);
});

test('real backup failure and interruption before adoption preserve the old receipt and all branches', async t=>{
  for(const kind of ['backup','interrupted']){
    const f=fixture(t),before=fs.readFileSync(f.filename),refs=git(f.projectRoot,['show-ref']);
    if(kind==='backup')f.options.backupRoot=path.join(f.projectRoot,'.git/forbidden-backup');
    else f.options.beforePreparedAmendAdopt=()=>{throw Object.assign(new Error('interrupted'),{code:'INTERRUPTED'});};
    await assert.rejects(amend(f));assert.deepEqual(fs.readFileSync(f.filename),before);assert.equal(git(f.projectRoot,['show-ref']),refs);
    assert.ok(fs.existsSync(f.integration));assert.ok(fs.existsSync(f.feature));
  }
});

test('replay validates restore evidence, preserves counters and another task, and supports a later descendant', async t=>{
  const f=fixture(t);f.receipt.repairAttempts=3;fs.writeFileSync(f.filename,JSON.stringify(f.receipt));
  const other=path.join(path.dirname(f.filename),'pr245.json');fs.writeFileSync(other,'{"repairAttempts":2}');
  const first=await amend(f), bytes=fs.readFileSync(f.filename);
  const replay=await amend(f);assert.deepEqual(replay,first);assert.deepEqual(fs.readFileSync(f.filename),bytes);
  assert.equal(fs.readFileSync(other,'utf8'),'{"repairAttempts":2}');assert.equal(replay.repairAttempts,3);
  fs.writeFileSync(path.join(f.feature,'next.txt'),'next');git(f.feature,['add','.']);git(f.feature,['commit','-m','next repair']);
  git(f.integration,['merge','--no-ff','--no-edit',git(f.feature,['rev-parse','HEAD'])]);
  const second=await amend(f);assert.equal(second.preparedAmendmentHistory.length,2);assert.equal(second.repairAttempts,3);
  assert.equal(second.preparedAmendment.previousCandidate,first.integrationCommit);
  fs.renameSync(path.join(second.preparedAmendment.backupDirectory,'manifest.json'),path.join(second.preparedAmendment.backupDirectory,'manifest.saved'));
  const before=fs.readFileSync(f.filename);await assert.rejects(amend(f));assert.deepEqual(fs.readFileSync(f.filename),before);
});

test('native, integration and task locks are never removed by a rejected caller', async t=>{
  for(const name of ['integration','task']){
    const f=fixture(t), lock=path.join(f.projectRoot,'.git/leon-engineering/locks',name+'.lock');fs.mkdirSync(path.dirname(lock),{recursive:true});fs.writeFileSync(lock,'owned elsewhere');
    const before=fs.readFileSync(f.filename);await assert.rejects(amend(f),{code:'TASK_LOCKED'});assert.equal(fs.readFileSync(lock,'utf8'),'owned elsewhere');assert.deepEqual(fs.readFileSync(f.filename),before);
  }
});

test('an accessible GitHub commit also requires empty check and status evidence; 403 and transport ambiguity fail closed', async t=>{
  const f=fixture(t);f.server.commitKnown=true;await amend(f);assert.ok(f.calls.some(args=>args[1].endsWith('/check-runs')));
  for(const status of ['403 Forbidden','500 Internal Server Error','000 Network failure']){
    const other=fixture(t);other.server.commitError=status;const before=fs.readFileSync(other.filename);await assert.rejects(amend(other),{code:'UNPUBLISHED_REMOTE_UNPROVEN'});assert.deepEqual(fs.readFileSync(other.filename),before);
  }
});

for(const patch of [{checkRuns:[{id:123}]},{ciResult:{status:'passed',runs:[123]}},{rollback:{status:'not_run',workflowRun:123}}]) test('review regression: refuses unknown side metadata '+JSON.stringify(patch), async t=>{
  const f=fixture(t);fs.writeFileSync(f.filename,JSON.stringify({...f.receipt,...patch}));const before=fs.readFileSync(f.filename);
  await assert.rejects(amend(f),{code:'UNPUBLISHED_STATE_INVALID'});assert.deepEqual(fs.readFileSync(f.filename),before);assert.equal(f.calls.length,0);
});

for(const name of ['repository','backup']) for(const action of ['remove','replace']) test(`review regression: ${name} lock ${action} during final network wait preserves original receipt`, async t=>{
  const f=fixture(t),before=fs.readFileSync(f.filename);let changed=false;
  f.options.beforePreparedAmendAdopt=()=>{
    f.server.beforeRead=()=>{
      if(changed)return;changed=true;
      const target=name==='repository'?path.join(f.projectRoot,'.git/leon-engineering/git-safety/repository.lock'):path.join(f.options.backupRoot,'.backup.lock');
      if(action==='replace') {fs.renameSync(target,target+'.saved');if(name==='repository')fs.writeFileSync(target,'foreign');else fs.mkdirSync(target,{mode:0o700});}
      else if(name==='repository')fs.unlinkSync(target);else fs.rmdirSync(target);
    };
  };
  await assert.rejects(amend(f));assert.equal(changed,true);assert.deepEqual(fs.readFileSync(f.filename),before);
});

for(const kind of ['snapshot','proof','backup','chain']) test('review regression: prior '+kind+' corruption refuses a new descendant', async t=>{
  const f=fixture(t),first=await amend(f),proof=first.preparedAmendment;
  if(kind==='snapshot')fs.appendFileSync(proof.receiptSnapshot,' ');
  if(kind==='proof')fs.writeFileSync(path.join(path.dirname(proof.receiptSnapshot),'proof.json'),'{}');
  if(kind==='backup')fs.renameSync(path.join(proof.backupDirectory,'manifest.json'),path.join(proof.backupDirectory,'manifest.saved'));
  if(kind==='chain') {first.preparedAmendmentHistory[0]={...proof,previousCandidate:f.base};fs.writeFileSync(f.filename,JSON.stringify(first));}
  fs.writeFileSync(path.join(f.feature,'next.txt'),'next');git(f.feature,['add','.']);git(f.feature,['commit','-m','later repair']);
  git(f.integration,['merge','--no-ff','--no-edit',git(f.feature,['rev-parse','HEAD'])]);
  const before=fs.readFileSync(f.filename);await assert.rejects(amend(f));assert.deepEqual(fs.readFileSync(f.filename),before);
});

test('backup lock optional witness keeps existing callbacks compatible and expires on release', t=>{
  const f=fixture(t),root=f.options.backupRoot;let witness;
  assert.equal(withBackupLock(root,()=>42),42);
  assert.equal(withBackupLock(root,assertHeld=>{witness=assertHeld;assert.equal(typeof witness,'function');witness();return 'held';}),'held');
  assert.throws(()=>witness(),{code:'BACKUP_LOCK_CHANGED'});assert.equal(fs.existsSync(path.join(root,'.backup.lock')),false);
});

for(const action of ['remove','replace']) test('backup lock acquired witness detects '+action+' before callback effects', t=>{
  const f=fixture(t),root=f.options.backupRoot;let effect=false;
  assert.throws(()=>withBackupLock(root,assertHeld=>{
    const lock=path.join(root,'.backup.lock');
    if(action==='replace'){fs.renameSync(lock,lock+'.saved');fs.mkdirSync(lock,{mode:0o700});}else fs.rmdirSync(lock);
    assertHeld();effect=true;
  }),{code:'BACKUP_LOCK_CHANGED'});
  assert.equal(effect,false);
});

test('history verification covers the oldest epoch before a third descendant', async t=>{
  const f=fixture(t),first=await amend(f);
  const advance=label=>{fs.writeFileSync(path.join(f.feature,label+'.txt'),label);git(f.feature,['add','.']);git(f.feature,['commit','-m',label]);git(f.integration,['merge','--no-ff','--no-edit',git(f.feature,['rev-parse','HEAD'])]);};
  advance('second');const second=await amend(f);assert.equal(second.preparedAmendmentHistory.length,2);
  fs.appendFileSync(path.join(path.dirname(first.preparedAmendment.receiptSnapshot),'proof.json'),' ');
  advance('third');const before=fs.readFileSync(f.filename);await assert.rejects(amend(f),{code:'PREPARED_AMEND_HISTORY_INVALID'});assert.deepEqual(fs.readFileSync(f.filename),before);
});

for(const name of ['snapshot','proof','temporary']) for(const action of ['delete','corrupt','replace']) test(`quality regression: new ${name} ${action} during final network wait preserves original receipt`, async t=>{
  const f=fixture(t),before=fs.readFileSync(f.filename);let changed=false,changedTarget;
  f.options.beforePreparedAmendAdopt=()=>{
    const epochs=path.join(f.projectRoot,'.git/leon-engineering/git-safety/prepared-amend/task');
    const epoch=path.join(epochs,fs.readdirSync(epochs)[0]);
    const temporary=fs.readdirSync(path.dirname(f.filename)).find(value=>value.startsWith('task.json.')&&value.endsWith('.tmp'));
    const target=name==='snapshot'?path.join(epoch,'receipt.json'):name==='proof'?path.join(epoch,'proof.json'):path.join(path.dirname(f.filename),temporary);
    changedTarget=target;
    f.server.beforeRead=()=>{
      if(changed)return;changed=true;
      if(action==='delete')fs.unlinkSync(target);
      if(action==='corrupt')fs.writeFileSync(target,'{}\n');
      if(action==='replace'){const bytes=fs.readFileSync(target);fs.renameSync(target,target+'.saved');fs.writeFileSync(target,bytes,{mode:0o600});}
    };
  };
  await assert.rejects(amend(f));assert.equal(changed,true);assert.deepEqual(fs.readFileSync(f.filename),before);
  if(name==='temporary' && action!=='delete')assert.equal(fs.existsSync(changedTarget),true,'changed temporary must be retained, not deleted as owned');
});

for(const mechanism of ['replace','graft','shallow']) test('quality regression: raw graph rejects real '+mechanism+' ambiguity without deleting metadata', async t=>{
  const f=fixture(t);let metadata;
  if(mechanism==='shallow'){
    metadata=path.join(f.projectRoot,'.git/shallow');fs.writeFileSync(metadata,f.base+'\n');
    assert.equal(git(f.projectRoot,['rev-parse','--is-shallow-repository']),'true');
  } else {
    const tree=git(f.integration,['rev-parse','HEAD^{tree}']);
    const single=git(f.integration,['commit-tree',tree,'-p',f.previous,'-m','single parent repair']);
    git(f.integration,['checkout','-B',f.receipt.integrationBranch,single]);
    if(mechanism==='replace'){
      const fake=git(f.integration,['commit-tree',tree,'-p',f.previous,'-p',f.newFeature,'-m','synthetic merge']);
      git(f.projectRoot,['replace',single,fake]);metadata=path.join(f.projectRoot,'.git/refs/replace',single);
    } else {
      metadata=path.join(f.projectRoot,'.git/info/grafts');fs.writeFileSync(metadata,`${single} ${f.previous} ${f.newFeature}\n`);
    }
    const projected=git(f.projectRoot,['rev-list','--parents','-n','1',single]).split(' ').slice(1);
    assert.deepEqual(projected,[f.previous,f.newFeature]);
    const raw=spawnSync('/usr/bin/git',['--no-replace-objects','-C',f.projectRoot,'cat-file','commit',single],{encoding:'utf8',env:{...process.env,GIT_GRAFT_FILE:'/dev/null'}});
    assert.equal(raw.status,0,raw.stderr);assert.equal(raw.stdout.split('\n').filter(line=>line.startsWith('parent ')).length,1);
  }
  const bytes=fs.readFileSync(metadata),before=fs.readFileSync(f.filename),refs=git(f.projectRoot,['show-ref']);
  await assert.rejects(amend(f),error=>['PREPARED_AMEND_ANCESTRY_INVALID','PREPARED_AMEND_GRAPH_UNPROVEN'].includes(error.code));
  assert.deepEqual(fs.readFileSync(f.filename),before);assert.deepEqual(fs.readFileSync(metadata),bytes);assert.equal(git(f.projectRoot,['show-ref']),refs);
});

test('quality regression: a newly resealed backup must correspond to the new proof and its actual restored anchors', async t=>{
  const f=fixture(t),before=fs.readFileSync(f.filename);
  f.options.afterPreparedAmendBackup=backup=>{
    const filename=path.join(backup.directory,'manifest.json'),manifest=JSON.parse(fs.readFileSync(filename));
    manifest.preservationRefs['refs/rwb-amend/old-feature']=f.base;manifest.stateHash=fingerprint(manifest,manifest.protection);
    const bytes=JSON.stringify(manifest,null,2)+'\n';fs.writeFileSync(filename,bytes);
    fs.writeFileSync(path.join(backup.directory,'seal.json'),JSON.stringify({manifestSha256:crypto.createHash('sha256').update(bytes).digest('hex')})+'\n');
  };
  await assert.rejects(amend(f));assert.deepEqual(fs.readFileSync(f.filename),before);
});

test('raw graph checks preserve legitimate unrelated refs and ignore an unrelated replacement mapping', async t=>{
  const f=fixture(t),tree=git(f.projectRoot,['rev-parse','HEAD^{tree}']);
  const other=git(f.projectRoot,['commit-tree',tree,'-p',f.base,'-m','other source']);
  const replacement=git(f.projectRoot,['commit-tree',tree,'-m','other replacement']);
  git(f.projectRoot,['branch','unrelated-keep',other]);git(f.projectRoot,['replace',other,replacement]);
  const before=git(f.projectRoot,['show-ref']),result=await amend(f);
  assert.equal(result.integrationCommit,f.candidate);assert.equal(git(f.projectRoot,['show-ref']),before);
  assert.equal(git(f.projectRoot,['rev-parse',`refs/replace/${other}`]),replacement);
});

for(const name of ['info/grafts','shallow']) test('raw graph guard rejects network-time '+name+' metadata without deleting it', async t=>{
  const f=fixture(t),before=fs.readFileSync(f.filename),target=path.join(f.projectRoot,'.git',name);let changed=false;
  f.options.beforePreparedAmendAdopt=()=>{f.server.beforeRead=()=>{if(!changed){changed=true;fs.writeFileSync(target,f.base+'\n');}};};
  await assert.rejects(amend(f),{code:'PREPARED_AMEND_GRAPH_UNPROVEN'});assert.deepEqual(fs.readFileSync(f.filename),before);assert.equal(fs.readFileSync(target,'utf8'),f.base+'\n');
});

function missingCommit422(sha, patch={}) {
  const body={message:`No commit found for SHA: ${sha}`,documentation_url:'https://docs.github.com/rest/commits/commits#get-a-commit',status:'422',...patch};
  return {status:1,stdout:`HTTP/2.0 422 Unprocessable Entity\r\ncontent-type: application/json\r\n\r\n${JSON.stringify(body)}`,stderr:`gh: No commit found for SHA: ${sha} (HTTP 422)\n`};
}

test('canary regression: exact live-format 422 is absent only after readable base from the same commit endpoint', async t=>{
  const f=fixture(t);f.server.commitResponse=sha=>missingCommit422(sha);
  const result=await amend(f);assert.equal(result.integrationCommit,f.candidate);
  const includes=f.calls.filter(args=>args.includes('--include')).map(args=>args[1]);
  assert.equal(includes[0],`repos/fixture/repo/commits/${f.base}`);
});

for(const response of [{status:1,stdout:'HTTP/2.0 404 Not Found\r\n\r\n{"message":"Not Found"}'},{status:0,stdout:'HTTP/2.0 200 OK\r\n\r\n{"sha":"1111111111111111111111111111111111111111"}'}]) test('canary regression: commit-endpoint base proof cannot be replaced by a readable ref '+response.status, async t=>{
  const f=fixture(t);f.server.baseCommitResponse=response;const before=fs.readFileSync(f.filename);
  await assert.rejects(amend(f),{code:'UNPUBLISHED_REMOTE_UNPROVEN'});assert.deepEqual(fs.readFileSync(f.filename),before);
});

function advanceFeatureAndMerge(f, label='later-repair') {
  fs.writeFileSync(path.join(f.feature,label+'.txt'),label);git(f.feature,['add','.']);git(f.feature,['commit','-m',label]);
  const feature=git(f.feature,['rev-parse','HEAD']);git(f.integration,['merge','--no-ff','--no-edit',feature]);return {feature,candidate:git(f.integration,['rev-parse','HEAD'])};
}

test('canary regression: interrupted unadopted merge is retained as a raw first-parent intermediate', async t=>{
  const f=fixture(t),before=fs.readFileSync(f.filename);
  f.options.beforePreparedAmendAdopt=()=>{throw Object.assign(new Error('interrupted'),{code:'INTERRUPTED'});};
  await assert.rejects(amend(f),{code:'INTERRUPTED'});assert.deepEqual(fs.readFileSync(f.filename),before);
  delete f.options.beforePreparedAmendAdopt;const next=advanceFeatureAndMerge(f);
  const result=await amend(f);assert.equal(result.integrationCommit,next.candidate);assert.equal(result.featureCommit,next.feature);
  assert.equal(result.preparedAmendment.schemaVersion,2);
  assert.deepEqual(result.preparedAmendment.mergeChain,[{commit:f.candidate,firstParent:f.previous,featureCommit:f.newFeature},{commit:next.candidate,firstParent:f.candidate,featureCommit:next.feature}]);
  const manifest=JSON.parse(fs.readFileSync(path.join(result.preparedAmendment.backupDirectory,'manifest.json')));
  for(const [index,step] of result.preparedAmendment.mergeChain.entries()){
    assert.equal(manifest.preservationRefs[`refs/rwb-amend/merge-chain/${index}/candidate`],step.commit);
    assert.equal(manifest.preservationRefs[`refs/rwb-amend/merge-chain/${index}/feature`],step.featureCommit);
  }
  assert.deepEqual(await amend(f),result);
});

for(const [name,build] of [
  ['wrong-sha',sha=>missingCommit422(sha,{message:'No commit found for SHA: '+'1'.repeat(40)})],
  ['generic-422',sha=>missingCommit422(sha,{message:'Validation Failed'})],
  ['wrong-doc',sha=>missingCommit422(sha,{documentation_url:'https://example.invalid'})],
  ['numeric-status',sha=>missingCommit422(sha,{status:422})],
  ['missing-status',sha=>missingCommit422(sha,{status:undefined})],
  ['extra-side-field',sha=>missingCommit422(sha,{publication:'unknown'})],
  ['wrong-exit',sha=>({...missingCommit422(sha),status:0})],
  ['403',sha=>{const r=missingCommit422(sha);r.stdout=r.stdout.replace('422 Unprocessable Entity','403 Forbidden');return r;}],
  ['timeout',()=>({status:null,stdout:'',stderr:'timeout'})],
  ['null-body',()=>({status:1,stdout:'HTTP/2.0 422 Unprocessable Entity\r\n\r\nnull',stderr:''})],
]) test('strict 422 absence refuses '+name, async t=>{
  const f=fixture(t);f.server.commitResponse=build;const before=fs.readFileSync(f.filename);
  await assert.rejects(amend(f),{code:'UNPUBLISHED_REMOTE_UNPROVEN'});assert.deepEqual(fs.readFileSync(f.filename),before);
});

for(const kind of ['single-parent-gap','foreign-second-parent','repeated-feature','wrong-first-parent']) test('raw merge chain rejects '+kind, async t=>{
  const f=fixture(t),before=fs.readFileSync(f.filename);
  if(kind==='single-parent-gap')git(f.integration,['commit','--allow-empty','-m','gap']);
  if(kind==='foreign-second-parent'){
    const foreign=git(f.projectRoot,['commit-tree',git(f.projectRoot,['rev-parse','HEAD^{tree}']),'-p',f.base,'-m','foreign']);
    git(f.integration,['merge','--no-ff','--no-edit',foreign]);
  }
  if(kind==='repeated-feature'){
    const duplicate=git(f.integration,['commit-tree',git(f.integration,['rev-parse','HEAD^{tree}']),'-p',f.candidate,'-p',f.newFeature,'-m','same feature again']);
    git(f.integration,['checkout','-B',f.receipt.integrationBranch,duplicate]);
  }
  if(kind==='wrong-first-parent'){
    git(f.feature,['merge','--no-ff','--no-edit',f.previous]);
    git(f.integration,['checkout','-B',f.receipt.integrationBranch,f.base]);
  }
  advanceFeatureAndMerge(f,kind);
  await assert.rejects(amend(f),{code:'PREPARED_AMEND_ANCESTRY_INVALID'});assert.deepEqual(fs.readFileSync(f.filename),before);
});

test('raw merge chain rejects more than 32 actual committed steps', async t=>{
  const f=fixture(t),before=fs.readFileSync(f.filename);
  for(let index=0;index<32;index++)advanceFeatureAndMerge(f,'step-'+index);
  await assert.rejects(amend(f),{code:'PREPARED_AMEND_CHAIN_LIMIT'});assert.deepEqual(fs.readFileSync(f.filename),before);
});

for(const total of [false,true]) test('raw merge chain enforces '+(total?'256KiB cumulative':'64KiB individual')+' raw commit byte limit', async t=>{
  const f=fixture(t),before=fs.readFileSync(f.filename),message=path.join(f.root,'message.txt');fs.writeFileSync(message,'x'.repeat(total?60*1024:65*1024));
  if(total)for(let index=0;index<5;index++){advanceFeatureAndMerge(f,'large-'+index);git(f.integration,['commit','--amend','-F',message]);}
  else git(f.integration,['commit','--amend','-F',message]);
  await assert.rejects(amend(f),{code:'PREPARED_AMEND_CHAIN_LIMIT'});assert.deepEqual(fs.readFileSync(f.filename),before);
});

for(const kind of ['duplicate','cycle']) test('v2 immutable history refuses a declared '+kind+' chain', async t=>{
  const f=fixture(t),first=await amend(f),proof=structuredClone(first.preparedAmendment);
  if(kind==='duplicate')proof.mergeChain.push({...proof.mergeChain[0]});else proof.mergeChain[0].firstParent=proof.mergeChain[0].commit;
  const record={...first,preparedAmendment:proof,preparedAmendmentHistory:[proof]};fs.writeFileSync(f.filename,JSON.stringify(record));const before=fs.readFileSync(f.filename);
  await assert.rejects(amend(f),{code:'PREPARED_AMEND_HISTORY_INVALID'});assert.deepEqual(fs.readFileSync(f.filename),before);
});

for(const kind of ['visible','ci']) test('unadopted intermediate with '+kind+' evidence cannot be admitted', async t=>{
  const f=fixture(t),before=fs.readFileSync(f.filename);advanceFeatureAndMerge(f);
  if(kind==='visible')f.server.commitResponse=sha=>sha===f.candidate?{status:0,stdout:`HTTP/2.0 200 OK\r\n\r\n${JSON.stringify({sha})}`,stderr:''}:missingCommit422(sha);
  else f.server.runCommits=new Set([f.candidate]);
  await assert.rejects(amend(f),{code:kind==='visible'?'UNPUBLISHED_STATE_INVALID':'UNPUBLISHED_CI_PRESENT'});assert.deepEqual(fs.readFileSync(f.filename),before);
});

for(const kind of ['visible','ci']) test('unadopted intermediate feature with '+kind+' evidence cannot be admitted', async t=>{
  const f=fixture(t),before=fs.readFileSync(f.filename);advanceFeatureAndMerge(f);
  if(kind==='visible')f.server.commitResponse=sha=>sha===f.newFeature?{status:0,stdout:`HTTP/2.0 200 OK\r\n\r\n${JSON.stringify({sha})}`,stderr:''}:missingCommit422(sha);
  else f.server.runCommits=new Set([f.newFeature]);
  await assert.rejects(amend(f),{code:kind==='visible'?'UNPUBLISHED_STATE_INVALID':'UNPUBLISHED_CI_PRESENT'});assert.deepEqual(fs.readFileSync(f.filename),before);
});

test('every intermediate merge anchor must match the actually restored sealed backup', async t=>{
  const f=fixture(t),before=fs.readFileSync(f.filename);advanceFeatureAndMerge(f);
  f.options.afterPreparedAmendBackup=backup=>{
    const file=path.join(backup.directory,'manifest.json'),manifest=JSON.parse(fs.readFileSync(file));delete manifest.preservationRefs['refs/rwb-amend/merge-chain/0/candidate'];
    manifest.stateHash=fingerprint(manifest,manifest.protection);const bytes=JSON.stringify(manifest,null,2)+'\n';fs.writeFileSync(file,bytes);
    fs.writeFileSync(path.join(backup.directory,'seal.json'),JSON.stringify({manifestSha256:crypto.createHash('sha256').update(bytes).digest('hex')})+'\n');
  };
  await assert.rejects(amend(f));assert.deepEqual(fs.readFileSync(f.filename),before);
});

test('network-time normal merge chain advance is preserved but cannot be adopted by a stale observation', async t=>{
  const f=fixture(t),before=fs.readFileSync(f.filename);advanceFeatureAndMerge(f);let changed=false;
  f.options.beforePreparedAmendAdopt=()=>{f.server.beforeRead=()=>{if(!changed){changed=true;advanceFeatureAndMerge(f,'concurrent-normal-merge');}};};
  await assert.rejects(amend(f),{code:'DELIVERY_RECORD_CHANGED'});assert.equal(changed,true);assert.deepEqual(fs.readFileSync(f.filename),before);
});

test('legacy v1 single-step history remains restorable without a v2 chain field', async t=>{
  const f=fixture(t),first=await amend(f),proof={...first.preparedAmendment,schemaVersion:1};delete proof.mergeChain;
  fs.writeFileSync(path.join(path.dirname(proof.receiptSnapshot),'proof.json'),JSON.stringify(proof,null,2)+'\n');
  const legacy={...first,preparedAmendment:proof,preparedAmendmentHistory:[proof]};fs.writeFileSync(f.filename,JSON.stringify(legacy));
  assert.deepEqual(await amend(f),legacy);
});

test('legacy v1 keeps its original single-step command byte budget rather than the new v2 bound', async t=>{
  const f=fixture(t),before=fs.readFileSync(f.filename),message=path.join(f.root,'legacy-message.txt');fs.writeFileSync(message,'x'.repeat(65*1024));git(f.integration,['commit','--amend','-F',message]);
  const candidate=git(f.integration,['rev-parse','HEAD']),preservationRefs={'refs/rwb-amend/old-feature':f.oldFeature,'refs/rwb-amend/old-candidate':f.previous};
  const backup=backupRepository({projectRoot:f.projectRoot},{...f.options,backupVersion:2,worktreePaths:[f.feature,f.integration],preservationRefs});
  const epoch=crypto.randomUUID(),directory=path.join(f.projectRoot,'.git/leon-engineering/git-safety/prepared-amend/task',epoch);fs.mkdirSync(directory,{recursive:true,mode:0o700});
  const snapshot=path.join(directory,'receipt.json');fs.writeFileSync(snapshot,before,{mode:0o600});
  const proof={schemaVersion:1,epoch,previousCandidate:f.previous,previousFeature:f.oldFeature,candidateCommit:candidate,featureCommit:f.newFeature,baseCommit:f.base,receiptSnapshot:snapshot,receiptSha256:crypto.createHash('sha256').update(before).digest('hex'),backupDirectory:backup.directory,backupManifestSha256:readManifest(backup.directory).hash,restoreVerified:true};
  fs.writeFileSync(path.join(directory,'proof.json'),JSON.stringify(proof,null,2)+'\n',{mode:0o600});
  const legacy={...f.receipt,integrationCommit:candidate,featureCommit:f.newFeature,verification:null,review:null,preparedAmendment:proof,preparedAmendmentHistory:[proof]};fs.writeFileSync(f.filename,JSON.stringify(legacy));
  assert.deepEqual(await amend(f),legacy);
});
