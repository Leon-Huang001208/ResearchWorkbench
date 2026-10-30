import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import crypto from 'node:crypto';
import {spawnSync} from 'node:child_process';
import {fileURLToPath, pathToFileURL} from 'node:url';
import {backupRepository, checkRepository, configureRepository, selectGitPath, withRepositoryLock, validateCleanup, validateResourceCleanup, runDelivery, parseCli, maintainBackups, verifyBackupDirectory} from '../../scripts/git_safety.mjs';

const gitPath = '/usr/bin/git';
function git(root, args) {
  // Fixture commits must not race detached Git maintenance with the lock gate.
  // Keep the production lock checks intact; these options affect this call only.
  const result = spawnSync(gitPath, ['-c', 'gc.auto=0', '-c', 'maintenance.auto=false', '-C', root, ...args], {encoding: 'utf8'});
  assert.equal(result.status, 0, result.stderr);
  return result.stdout.trim();
}
function fixture(t) {
  const root = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), 'git-safety-test-')));
  t.after(() => fs.rmSync(root, {recursive: true, force: true}));
  const projectRoot = path.join(root, 'repo');
  fs.mkdirSync(projectRoot);
  git(projectRoot, ['init', '-b', 'master']);
  git(projectRoot, ['config', 'user.name', 'Fixture']);
  git(projectRoot, ['config', 'user.email', 'fixture@example.invalid']);
  fs.writeFileSync(path.join(projectRoot, 'package.json'), JSON.stringify({type: 'module'}) + '\n');
  fs.writeFileSync(path.join(projectRoot, 'tracked.txt'), 'base\n');
  git(projectRoot, ['add', '.']);
  git(projectRoot, ['commit', '-m', 'base']);
  return {root, projectRoot, options: {gitPath, platform: 'darwin', identityRoot: projectRoot, backupRoot: path.join(root, 'backups'), backupVersion: 1}};
}

async function partialCleanupFixture(t) {
  const f=cleanupFixture(t), {projectRoot,receipt}=f;
  fs.appendFileSync(path.join(projectRoot,'.git/info/exclude'),'\nlogs/\n');
  receipt.schemaVersion=1;receipt.mode='pr';receipt.verification={status:'passed'};
  receipt.pullRequest={number:1,url:'https://github.com/fixture/repo/pull/1'};
  git(projectRoot,['commit','--allow-empty','-m','merged task']);
  const merge=git(projectRoot,['rev-parse','HEAD']);
  git(projectRoot,['push','origin','master']);git(projectRoot,['update-ref','refs/remotes/origin/master',merge]);
  receipt.remoteUrl='https://github.com/fixture/repo.git';git(projectRoot,['remote','set-url','origin',receipt.remoteUrl]);
  const beforeRefs=Object.fromEntries(git(projectRoot,['for-each-ref','--format=%(refname) %(objectname)']).split('\n').map(line=>line.split(' ')));
  const backup=backupRepository({projectRoot},{...f.options,backupVersion:2,worktreePaths:[projectRoot,receipt.featureWorktree,receipt.integrationWorktree],preservationRefs:beforeRefs});
  const state=path.join(projectRoot,'.git/leon-engineering/resource-closeout/task');fs.mkdirSync(state,{recursive:true});
  const managed=[{branch:receipt.featureBranch,worktree:receipt.featureWorktree,commit:receipt.featureCommit},{branch:receipt.integrationBranch,worktree:receipt.integrationWorktree,commit:receipt.integrationCommit}];
  const beforeWorktrees=managed.map(row=>({worktree:row.worktree,HEAD:row.commit,branch:`refs/heads/${row.branch}`}));
  fs.writeFileSync(path.join(state,'git-finalization.json'),JSON.stringify({taskId:'task',candidateCommit:receipt.integrationCommit,status:'pending',resourceContractRequired:true,restoreVerified:true,beforeRefs,beforeWorktrees,managed,verifiedPreservationRefs:beforeRefs}),{mode:0o600});
  fs.writeFileSync(path.join(state,'receipt.json'),JSON.stringify({taskId:'task',ok:true,cache:{ok:true},status:'blocked',blocked:[{phase:'git',code:'DELIVERY_FAILED'}]}),{mode:0o600});
  const delivery=path.join(projectRoot,'.git/leon-engineering/deliveries/task.json');fs.mkdirSync(path.dirname(delivery),{recursive:true});
  fs.writeFileSync(delivery,JSON.stringify(receipt),{mode:0o600});
  for(const item of managed)git(projectRoot,['worktree','remove',item.worktree]);
  git(projectRoot,['branch','-d',receipt.featureBranch]);
  const remoteRefs=new Map(managed.map(row=>[`refs/heads/${row.branch}`,row.commit])), calls=[], server={};
  const controller={readDeliveryReceipt:()=>JSON.parse(fs.readFileSync(delivery)),validateCleanedDelivery:()=>{
    const value=JSON.parse(fs.readFileSync(delivery));assert.equal(value.status,'cleaned');
    for(const row of managed){assert.equal(fs.existsSync(row.worktree),false);assert.equal(remoteRefs.has(`refs/heads/${row.branch}`),false);assert.equal(spawnSync(gitPath,['-C',projectRoot,'show-ref','--verify','--quiet',`refs/heads/${row.branch}`]).status,1);}
    return value;
  }};
  const githubRunner=(_exe,args)=>{
    calls.push(args);
    let value;
    if(args[0]==='pr')value={state:'MERGED',headRefOid:receipt.integrationCommit,baseRefName:'master',reviewDecision:'',statusCheckRollup:[{name:'check',status:'COMPLETED',conclusion:'SUCCESS'}],mergeCommit:{oid:merge}};
    else if(args[1]==='graphql'){
      const body=JSON.parse(fs.readFileSync(args[args.indexOf('--input')+1]));
      const updates=body.variables.input.refUpdates;
      server.beforeMutation?.();
      for(const row of updates){assert.equal(row.force,false);assert.equal(row.afterOid,'0'.repeat(40));}
      if(updates.some(row=>remoteRefs.get(row.name)!==row.beforeOid))value={errors:[{type:'STALE_DATA'}]};
      else{for(const row of updates)remoteRefs.delete(row.name);value={data:{updateRefs:{clientMutationId:body.variables.input.clientMutationId}}};}
    } else {
      const route=args[1];
      if(route.endsWith('/protection'))value={required_status_checks:{strict:true,checks:[{context:'check'}]},required_pull_request_reviews:{required_approving_review_count:0},enforce_admins:{enabled:true},required_conversation_resolution:{enabled:true}};
      else if(route.endsWith('/check-runs'))value=[{check_runs:[{name:'check',head_sha:receipt.integrationCommit,status:'completed',conclusion:'success'}]}];
      else if(route.endsWith('/status'))value={sha:receipt.integrationCommit,statuses:[]};
      else if(route.endsWith('/commits/'+merge))value={sha:merge,parents:[{sha:receipt.integrationCommit}]};
      else if(route.endsWith('/git/ref/heads/master'))value={object:{sha:merge}};
      else if(route.includes('/git/matching-refs/heads/')){const name='refs/heads/'+route.split('/git/matching-refs/heads/')[1];value=remoteRefs.has(name)?[{ref:name,object:{sha:remoteRefs.get(name)}}]:[];server.afterRemoteRead?.(name);}
      else if(route==='repos/fixture/repo')value={node_id:'R_fixture'};
      else throw new Error('unexpected GitHub request '+route);
    }
    return {status:0,stdout:JSON.stringify(value)};
  };
  const resourceRevalidationProbe=()=>({ok:true,taskId:'task',candidateCommit:receipt.integrationCommit,cache:{ok:true},previousReceiptSha256:crypto.createHash('sha256').update(fs.readFileSync(path.join(state,'receipt.json'))).digest('hex')});
  return {...f,state,backup,delivery,managed,remoteRefs,calls,merge,server,options:{...f.options,controller,githubRunner,resourceRevalidationProbe,quotaProbe:()=>({allowed:true})}};
}

test('partial cleanup recovers retired worktrees without forging the original pending proof', async t=>{
  const {recoverCloseoutFinalization}=await import('../../scripts/git_safety.mjs');
  const f=await partialCleanupFixture(t), original=fs.readFileSync(path.join(f.state,'git-finalization.json'));
  const input={projectRoot:f.projectRoot,taskId:'task',backupDirectory:f.backup.directory};
  const preview=await recoverCloseoutFinalization(input,f.options);
  assert.equal(preview.kind,'partial_cleanup');assert.equal(JSON.parse(fs.readFileSync(f.delivery)).status,'ci_passed');
  const result=await recoverCloseoutFinalization({...input,apply:true,previewSha256:preview.previewSha256},f.options);
  assert.equal(result.status,'cleaned');assert.equal(JSON.parse(fs.readFileSync(f.delivery)).status,'cleaned');
  assert.deepEqual(fs.readFileSync(path.join(f.state,'git-finalization.json')),original);
  assert.equal(JSON.parse(fs.readFileSync(path.join(f.state,'receipt.json'))).status,'complete');
});

test('partial cleanup preserves a recreated worktree before any local reference deletion', async t=>{
  const {recoverCloseoutFinalization}=await import('../../scripts/git_safety.mjs');
  const f=await partialCleanupFixture(t), input={projectRoot:f.projectRoot,taskId:'task',backupDirectory:f.backup.directory};
  const preview=await recoverCloseoutFinalization(input,f.options);
  f.options.afterPartialRemoteRetired=()=>{
    git(f.projectRoot,['worktree','add',f.receipt.integrationWorktree,f.receipt.integrationBranch]);
    fs.writeFileSync(path.join(f.receipt.integrationWorktree,'new-user-work.txt'),'keep');
  };
  await assert.rejects(recoverCloseoutFinalization({...input,apply:true,previewSha256:preview.previewSha256},f.options),{code:'PARTIAL_CLEANUP_WORKTREE_PRESENT'});
  assert.equal(git(f.projectRoot,['rev-parse',`refs/heads/${f.receipt.integrationBranch}`]),f.receipt.integrationCommit);
  assert.equal(fs.readFileSync(path.join(f.receipt.integrationWorktree,'new-user-work.txt'),'utf8'),'keep');
});

test('partial cleanup checks worktrees after the last remote observation', async t=>{
  const {recoverCloseoutFinalization}=await import('../../scripts/git_safety.mjs');
  const f=await partialCleanupFixture(t), input={projectRoot:f.projectRoot,taskId:'task',backupDirectory:f.backup.directory};
  const preview=await recoverCloseoutFinalization(input,f.options);let emptyReads=0;
  f.server.afterRemoteRead=()=>{
    if(f.remoteRefs.size===0 && ++emptyReads===4){
      const other=path.join(f.root,'new-user-checkout');git(f.projectRoot,['worktree','add',other,f.receipt.integrationBranch]);
      fs.writeFileSync(path.join(other,'new-user-work.txt'),'keep');
    }
  };
  await assert.rejects(recoverCloseoutFinalization({...input,apply:true,previewSha256:preview.previewSha256},f.options),{code:'PARTIAL_CLEANUP_WORKTREE_PRESENT'});
  assert.equal(git(f.projectRoot,['rev-parse',`refs/heads/${f.receipt.integrationBranch}`]),f.receipt.integrationCommit);
  assert.equal(fs.readFileSync(path.join(f.root,'new-user-checkout/new-user-work.txt'),'utf8'),'keep');
});

test('partial cleanup never certifies a concurrently modified delivery', async t=>{
  const {recoverCloseoutFinalization}=await import('../../scripts/git_safety.mjs');
  const f=await partialCleanupFixture(t), input={projectRoot:f.projectRoot,taskId:'task',backupDirectory:f.backup.directory};
  const preview=await recoverCloseoutFinalization(input,f.options);
  f.options.afterPartialReceiptCommitted=()=>{const v=JSON.parse(fs.readFileSync(f.delivery));v.newUserWork='keep';fs.writeFileSync(f.delivery,JSON.stringify(v));};
  await assert.rejects(recoverCloseoutFinalization({...input,apply:true,previewSha256:preview.previewSha256},f.options),{code:'CLOSEOUT_RECOVERY_STALE'});
  assert.equal(JSON.parse(fs.readFileSync(f.delivery)).newUserWork,'keep');
  assert.equal(fs.existsSync(path.join(f.state,'git-finalization-recovery.json')),false);
});

test('partial cleanup rechecks delivery after final network observations', async t=>{
  const {recoverCloseoutFinalization}=await import('../../scripts/git_safety.mjs');
  const f=await partialCleanupFixture(t), input={projectRoot:f.projectRoot,taskId:'task',backupDirectory:f.backup.directory};
  const preview=await recoverCloseoutFinalization(input,f.options);let emptyReads=0;
  f.server.afterRemoteRead=()=>{
    if(f.remoteRefs.size===0 && ++emptyReads===6){const value=JSON.parse(fs.readFileSync(f.delivery));value.newUserWork='keep';fs.writeFileSync(f.delivery,JSON.stringify(value));}
  };
  await assert.rejects(recoverCloseoutFinalization({...input,apply:true,previewSha256:preview.previewSha256},f.options),{code:'CLOSEOUT_RECOVERY_STALE'});
  assert.equal(JSON.parse(fs.readFileSync(f.delivery)).newUserWork,'keep');
  assert.equal(fs.existsSync(path.join(f.state,'git-finalization-recovery.json')),false);
});

test('partial cleanup completion preview never invokes the fetching validator', async t=>{
  const {recoverCloseoutFinalization}=await import('../../scripts/git_safety.mjs');
  const f=await partialCleanupFixture(t), input={projectRoot:f.projectRoot,taskId:'task',backupDirectory:f.backup.directory};
  const preview=await recoverCloseoutFinalization(input,f.options);
  await recoverCloseoutFinalization({...input,apply:true,previewSha256:preview.previewSha256},f.options);
  f.options.controller.validateCleanedDelivery=()=>{throw new Error('unexpected fetching validator');};
  assert.equal((await recoverCloseoutFinalization(input,f.options)).status,'cleaned');
});

test('partial cleanup rejects stale preview and missing review before mutations', async t=>{
  const {recoverCloseoutFinalization}=await import('../../scripts/git_safety.mjs');
  const f=await partialCleanupFixture(t), input={projectRoot:f.projectRoot,taskId:'task',backupDirectory:f.backup.directory};
  const preview=await recoverCloseoutFinalization(input,f.options);
  await assert.rejects(recoverCloseoutFinalization({...input,apply:true,previewSha256:'0'.repeat(64)},f.options),{code:'CLOSEOUT_RECOVERY_STALE'});
  fs.unlinkSync(path.join(f.projectRoot,'.git/leon-engineering/git-safety/reviews/task.json'));
  await assert.rejects(recoverCloseoutFinalization(input,f.options),{code:'REVIEW_NOT_ATTESTED'});
  assert.equal(f.remoteRefs.size,2);assert.equal(JSON.parse(fs.readFileSync(f.delivery)).status,'ci_passed');
  assert.equal(fs.existsSync(path.join(f.state,'partial-cleanup-intent.json')),false);
});

test('partial cleanup remote compare-and-delete rejects new work atomically', async t=>{
  const {recoverCloseoutFinalization}=await import('../../scripts/git_safety.mjs');
  const f=await partialCleanupFixture(t), input={projectRoot:f.projectRoot,taskId:'task',backupDirectory:f.backup.directory};
  const preview=await recoverCloseoutFinalization(input,f.options);
  f.server.beforeMutation=()=>f.remoteRefs.set(`refs/heads/${f.receipt.integrationBranch}`,f.merge);
  await assert.rejects(recoverCloseoutFinalization({...input,apply:true,previewSha256:preview.previewSha256},f.options),{code:'PARTIAL_CLEANUP_REMOTE_UPDATE_UNCONFIRMED'});
  assert.equal(f.remoteRefs.get(`refs/heads/${f.receipt.featureBranch}`),f.receipt.featureCommit);
  assert.equal(f.remoteRefs.get(`refs/heads/${f.receipt.integrationBranch}`),f.merge);
  assert.equal(git(f.projectRoot,['rev-parse',`refs/heads/${f.receipt.integrationBranch}`]),f.receipt.integrationCommit);
});

test('partial cleanup local compare-and-delete never erases a new commit', async t=>{
  const {recoverCloseoutFinalization}=await import('../../scripts/git_safety.mjs');
  const f=await partialCleanupFixture(t), input={projectRoot:f.projectRoot,taskId:'task',backupDirectory:f.backup.directory};
  const preview=await recoverCloseoutFinalization(input,f.options);
  f.options.afterPartialRemoteRetired=()=>git(f.projectRoot,['update-ref',`refs/heads/${f.receipt.integrationBranch}`,f.merge]);
  await assert.rejects(recoverCloseoutFinalization({...input,apply:true,previewSha256:preview.previewSha256},f.options),{code:'COMMAND_FAILED'});
  assert.equal(git(f.projectRoot,['rev-parse',`refs/heads/${f.receipt.integrationBranch}`]),f.merge);
  assert.equal(JSON.parse(fs.readFileSync(f.delivery)).status,'ci_passed');
});

test('partial cleanup observes accepted remote retirement after interruption without resending', async t=>{
  const {recoverCloseoutFinalization}=await import('../../scripts/git_safety.mjs');
  const f=await partialCleanupFixture(t), input={projectRoot:f.projectRoot,taskId:'task',backupDirectory:f.backup.directory};
  let preview=await recoverCloseoutFinalization(input,f.options);
  f.options.afterPartialRemoteRetired=()=>{throw new Error('interrupted');};
  await assert.rejects(recoverCloseoutFinalization({...input,apply:true,previewSha256:preview.previewSha256},f.options),/interrupted/);
  assert.equal(f.remoteRefs.size,0);delete f.options.afterPartialRemoteRetired;
  preview=await recoverCloseoutFinalization(input,f.options);
  assert.equal((await recoverCloseoutFinalization({...input,apply:true,previewSha256:preview.previewSha256},f.options)).status,'cleaned');
  assert.equal(f.calls.filter(args=>args[1]==='graphql').length,1);
});

test('partial cleanup resumes a receipt commit interrupted before completion certificate', async t=>{
  const {recoverCloseoutFinalization}=await import('../../scripts/git_safety.mjs');
  const f=await partialCleanupFixture(t), input={projectRoot:f.projectRoot,taskId:'task',backupDirectory:f.backup.directory};
  let preview=await recoverCloseoutFinalization(input,f.options);
  f.options.afterPartialReceiptCommitted=()=>{throw new Error('interrupted');};
  await assert.rejects(recoverCloseoutFinalization({...input,apply:true,previewSha256:preview.previewSha256},f.options),/interrupted/);
  assert.equal(JSON.parse(fs.readFileSync(f.delivery)).status,'cleaned');
  assert.equal(fs.existsSync(path.join(f.state,'git-finalization-recovery.json')),false);
  delete f.options.afterPartialReceiptCommitted;preview=await recoverCloseoutFinalization(input,f.options);
  assert.equal((await recoverCloseoutFinalization({...input,apply:true,previewSha256:preview.previewSha256},f.options)).status,'cleaned');
});

test('partial cleanup quota failure preserves references and original receipts', async t=>{
  const {recoverCloseoutFinalization}=await import('../../scripts/git_safety.mjs');
  const f=await partialCleanupFixture(t), input={projectRoot:f.projectRoot,taskId:'task',backupDirectory:f.backup.directory};
  const preview=await recoverCloseoutFinalization(input,f.options), before=fs.readFileSync(f.delivery);
  f.options.quotaProbe=()=>({allowed:false});
  await assert.rejects(recoverCloseoutFinalization({...input,apply:true,previewSha256:preview.previewSha256},f.options),{code:'ACTIONS_BUDGET_BLOCKED'});
  assert.deepEqual(fs.readFileSync(f.delivery),before);assert.equal(f.remoteRefs.size,2);
});

test('partial cleanup framework validation uses private native Git shim and restores PATH', async t=>{
  const {recoverCloseoutFinalization}=await import('../../scripts/git_safety.mjs');
  const f=await partialCleanupFixture(t), input={projectRoot:f.projectRoot,taskId:'task',backupDirectory:f.backup.directory};
  const capture=path.join(f.root,'fetch-args.json'), wrapper=path.join(f.root,'selected-git');
  fs.writeFileSync(wrapper,`#!${process.execPath}\nconst fs=require('node:fs'),{spawnSync}=require('node:child_process');const a=process.argv.slice(2);if(a.includes('fetch')){fs.writeFileSync(${JSON.stringify(capture)},JSON.stringify(a));process.exit(0);}const r=spawnSync('/usr/bin/git',a,{stdio:'inherit'});process.exit(r.status??1);\n`,{mode:0o700});
  f.options.gitPath=wrapper;const validate=f.options.controller.validateCleanedDelivery, oldPath=process.env.PATH;
  f.options.controller.validateCleanedDelivery=()=>{
    assert.equal(process.env.PATH.split(path.delimiter)[0],path.join(f.projectRoot,'.git/leon-engineering/git-safety/bin'));
    const r=spawnSync('git',['-C',f.projectRoot,'fetch','--prune','origin','refs/heads/master:refs/remotes/origin/master'],{encoding:'utf8'});assert.equal(r.status,0,r.stderr);
    return validate();
  };
  const preview=await recoverCloseoutFinalization(input,f.options);
  assert.equal(fs.existsSync(path.join(f.projectRoot,'.git/leon-engineering/git-safety/bin')),false);
  await recoverCloseoutFinalization({...input,apply:true,previewSha256:preview.previewSha256},f.options);
  const args=JSON.parse(fs.readFileSync(capture));assert.equal(args.includes('--prune'),false);assert.ok(args.includes('gc.auto=0'));assert.ok(args.includes('maintenance.auto=false'));
  assert.equal(process.env.PATH,oldPath);
});

test('partial cleanup rejects reference loss during resource revalidation', async t=>{
  const {recoverCloseoutFinalization}=await import('../../scripts/git_safety.mjs');
  const f=await partialCleanupFixture(t), input={projectRoot:f.projectRoot,taskId:'task',backupDirectory:f.backup.directory};
  const preview=await recoverCloseoutFinalization(input,f.options), original=fs.readFileSync(path.join(f.state,'git-finalization.json'));
  const revalidate=f.options.resourceRevalidationProbe;
  f.options.resourceRevalidationProbe=(...args)=>{const result=revalidate(...args);git(f.projectRoot,['update-ref','-d','refs/remotes/origin/master']);return result;};
  await assert.rejects(recoverCloseoutFinalization({...input,apply:true,previewSha256:preview.previewSha256},f.options),{code:'BRANCH_UNMERGED'});
  assert.equal(fs.existsSync(path.join(f.state,'git-finalization-recovery.json')),false);
  assert.deepEqual(fs.readFileSync(path.join(f.state,'git-finalization.json')),original);
});

test('partial cleanup completed preview retains full object integrity checks', async t=>{
  const {recoverCloseoutFinalization}=await import('../../scripts/git_safety.mjs');
  const f=await partialCleanupFixture(t), input={projectRoot:f.projectRoot,taskId:'task',backupDirectory:f.backup.directory};
  const preview=await recoverCloseoutFinalization(input,f.options);
  await recoverCloseoutFinalization({...input,apply:true,previewSha256:preview.previewSha256},f.options);
  const blob=git(f.projectRoot,['rev-parse','HEAD:tracked.txt']);fs.unlinkSync(path.join(f.projectRoot,'.git/objects',blob.slice(0,2),blob.slice(2)));
  await assert.rejects(recoverCloseoutFinalization(input,f.options),{code:'OBJECT_INTEGRITY_FAILED'});
});

test('partial cleanup completed preview retains independent review binding', async t=>{
  const {recoverCloseoutFinalization}=await import('../../scripts/git_safety.mjs');
  const f=await partialCleanupFixture(t), input={projectRoot:f.projectRoot,taskId:'task',backupDirectory:f.backup.directory};
  const preview=await recoverCloseoutFinalization(input,f.options);
  await recoverCloseoutFinalization({...input,apply:true,previewSha256:preview.previewSha256},f.options);
  fs.unlinkSync(path.join(f.projectRoot,'.git/leon-engineering/git-safety/reviews/task.json'));
  await assert.rejects(recoverCloseoutFinalization(input,f.options),{code:'REVIEW_NOT_ATTESTED'});
});

test('partial cleanup rejects FIFO metadata without blocking the child process', async t=>{
  const f=await partialCleanupFixture(t), proof=path.join(f.state,'git-finalization.json');
  fs.unlinkSync(proof);assert.equal(spawnSync('/usr/bin/mkfifo',[proof]).status,0);
  const modulePath=pathToFileURL(path.resolve('scripts/git_safety.mjs')).href;
  const body=`import fs from 'node:fs';import {recoverCloseoutFinalization} from ${JSON.stringify(modulePath)};const input=${JSON.stringify({projectRoot:f.projectRoot,taskId:'task',backupDirectory:f.backup.directory})};const controller={readDeliveryReceipt:()=>JSON.parse(fs.readFileSync(${JSON.stringify(f.delivery)}))};try{await recoverCloseoutFinalization(input,{controller});process.exitCode=9;}catch(error){process.stderr.write(error.code??'unknown');process.exitCode=3;}`;
  const r=spawnSync(process.execPath,['--input-type=module','-e',body],{encoding:'utf8',timeout:3000});
  assert.equal(r.error,undefined);assert.equal(r.status,3);assert.match(r.stderr,/CLOSEOUT_RECOVERY_RECORD_INVALID/);
});

test('partial cleanup refuses invalid or foreign branch namespaces', async t=>{
  const {recoverCloseoutFinalization}=await import('../../scripts/git_safety.mjs');
  const f=await partialCleanupFixture(t), v=JSON.parse(fs.readFileSync(f.delivery));
  v.integrationBranch='master';fs.writeFileSync(f.delivery,JSON.stringify(v));
  const proof=JSON.parse(fs.readFileSync(path.join(f.state,'git-finalization.json')));proof.managed[1].branch='master';
  fs.writeFileSync(path.join(f.state,'git-finalization.json'),JSON.stringify(proof));
  await assert.rejects(recoverCloseoutFinalization({projectRoot:f.projectRoot,taskId:'task',backupDirectory:f.backup.directory},f.options),{code:'TASK_OWNERSHIP_MISMATCH'});
  assert.equal(git(f.projectRoot,['rev-parse','master']),f.merge);assert.equal(f.remoteRefs.size,2);
});

test('macOS always selects native Git; unsupported production mutations fail closed', () => {
  assert.equal(selectGitPath({platform: 'darwin'}), '/usr/bin/git');
  assert.throws(() => selectGitPath({platform: 'linux', mutate: true}), {code: 'HOST_UNSUPPORTED'});
});

test('check is read-only and configure shares common config with rollback evidence', t => {
  const {root, projectRoot, options} = fixture(t);
  const before = fs.readFileSync(path.join(projectRoot, '.git/config'));
  const result = checkRepository({projectRoot}, options);
  assert.equal(result.fsck, 'PASS');
  assert.deepEqual(fs.readFileSync(path.join(projectRoot, '.git/config')), before);
  assert.equal(fs.existsSync(path.join(projectRoot, 'logs/git-safety.jsonl')), false);
  const wt = path.join(root, 'linked');
  git(projectRoot, ['worktree', 'add', '-b', 'codex/linked', wt]);
  const configured = configureRepository({projectRoot: wt}, options);
  assert.equal(git(projectRoot, ['config', '--local', 'gc.auto']), '0');
  assert.equal(git(projectRoot, ['config', '--local', 'maintenance.auto']), 'false');
  assert.equal(JSON.parse(fs.readFileSync(configured.backup)).previous['gc.auto'], null);
  assert.equal(fs.statSync(configured.backup).mode & 0o777, 0o600);
});

test('repository/native locks are never removed, even with stale PID', t => {
  const {projectRoot, options} = fixture(t);
  const common = path.join(projectRoot, '.git');
  fs.mkdirSync(path.join(common, 'leon-engineering/git-safety'), {recursive: true});
  const lock = path.join(common, 'leon-engineering/git-safety/repository.lock');
  fs.writeFileSync(lock, '{"pid":99999999}');
  assert.throws(() => withRepositoryLock({projectRoot}, () => {}, options), {code: 'REPOSITORY_LOCKED'});
  assert.equal(fs.readFileSync(lock, 'utf8'), '{"pid":99999999}');
  fs.rmSync(lock);
  fs.writeFileSync(path.join(common, 'index.lock'), 'untouched');
  assert.throws(() => configureRepository({projectRoot}, options), {code: 'NATIVE_LOCKED'});
  assert.equal(fs.readFileSync(path.join(common, 'index.lock'), 'utf8'), 'untouched');
});

test('missing committed objects fail fsck without repair or log writes', t => {
  const {projectRoot, options} = fixture(t);
  const blob = git(projectRoot, ['rev-parse', 'HEAD:tracked.txt']);
  fs.rmSync(path.join(projectRoot, '.git/objects', blob.slice(0, 2), blob.slice(2)));
  assert.throws(() => checkRepository({projectRoot}, options), error=>{
    assert.equal(error.code,'OBJECT_INTEGRITY_FAILED');
    assert.equal(Number.isInteger(error.integrity.exitCode),true);assert.ok(error.integrity.exitCode>0);assert.equal(error.integrity.signal,null);
    assert.match(error.integrity.stderrSha256,/^[a-f0-9]{64}$/);return true;
  });
  assert.equal(fs.existsSync(path.join(projectRoot, 'logs')), false);
});

test('backup actually restores commits, binary staged/unstaged patches, untracked files and snapshot refs', t => {
  const {projectRoot, options} = fixture(t);
  fs.writeFileSync(path.join(projectRoot, 'tracked.txt'), Buffer.from([0, 1, 2, 3]));
  git(projectRoot, ['add', 'tracked.txt']);
  fs.writeFileSync(path.join(projectRoot, 'tracked.txt'), Buffer.from([0, 1, 4, 5]));
  fs.writeFileSync(path.join(projectRoot, 'new.txt'), 'untracked evidence\n');
  fs.symlinkSync('new.txt', path.join(projectRoot, 'new-link'));
  const tree = git(projectRoot, ['rev-parse', 'HEAD^{tree}']);
  git(projectRoot, ['update-ref', 'refs/codex/snapshot', tree]);
  const result = backupRepository({projectRoot}, options);
  assert.equal(result.restoreVerified, true);
  assert.equal(result.fsck, 'PASS');
  assert.equal(result.snapshotRefs['refs/codex/snapshot'], tree);
  assert.ok(fs.existsSync(path.join(result.directory, 'commits.bundle')));
  assert.equal(fs.statSync(result.directory).mode & 0o777, 0o700);
  const manifest = JSON.parse(fs.readFileSync(path.join(result.directory, 'manifest.json')));
  assert.equal(manifest.worktrees[0].untracked.length, 2);
  assert.ok(manifest.files.every(item => /^[a-f0-9]{64}$/.test(item.sha256)));
  const journal = path.join(result.directory, 'logs/git-safety.jsonl');
  assert.equal(fs.statSync(path.dirname(journal)).mode & 0o777, 0o700);
  assert.equal(fs.statSync(journal).mode & 0o777, 0o600);
  assert.equal(fs.statSync(journal).nlink, 1);
  assert.equal(manifest.files.find(item => item.path === 'logs/git-safety.jsonl')?.sha256, crypto.createHash('sha256').update(fs.readFileSync(journal)).digest('hex'));
  assert.ok(fs.readFileSync(journal, 'utf8').trim().split('\n').every(line => JSON.parse(line).action === 'backup-snapshot'));
  assert.ok(!fs.readFileSync(path.join(projectRoot, 'logs/git-safety.jsonl'), 'utf8').includes('backup-snapshot'));
  assert.ok(!fs.readFileSync(path.join(projectRoot, 'logs/git-safety.jsonl'), 'utf8').includes('untracked evidence'));
});

test('possible secret untracked files are refused before exporting any backup', t => {
  const {projectRoot, options} = fixture(t);
  fs.writeFileSync(path.join(projectRoot, '.env.production'), 'SECRET_SENTINEL');
  assert.throws(() => backupRepository({projectRoot}, options), {code: 'SENSITIVE_UNTRACKED'});
  assert.equal(fs.existsSync(options.backupRoot), false);
});

function cleanupFixture(t) {
  const f = fixture(t);
  const head = git(f.projectRoot, ['rev-parse', 'HEAD']);
  const remote = path.join(f.root, 'remote.git');
  git(f.projectRoot, ['init', '--bare', '-b', 'master', remote]);
  git(f.projectRoot, ['remote', 'add', 'origin', remote]);
  git(f.projectRoot, ['push', 'origin', 'master']);
  git(f.projectRoot, ['update-ref', 'refs/remotes/origin/master', head]);
  const featureWorktree = path.join(f.root, 'feature');
  const integrationWorktree = path.join(f.root, 'integration');
  git(f.projectRoot, ['worktree', 'add', '-b', 'codex/task-feature', featureWorktree]);
  git(f.projectRoot, ['worktree', 'add', '-b', 'codex/task-integration', integrationWorktree]);
  const receipt = {taskId: 'task', repositoryRoot: f.projectRoot, remote: 'origin', remoteUrl: remote, defaultBranch: 'master', featureBranch: 'codex/task-feature', featureWorktree, featureCommit: head, integrationBranch: 'codex/task-integration', integrationWorktree, integrationCommit: head, integrationHistory: [], status: 'ci_passed', ci: {status: 'passed'}};
  const reviews = path.join(f.projectRoot, '.git/leon-engineering/git-safety/reviews');
  fs.mkdirSync(reviews, {recursive: true});
  fs.writeFileSync(path.join(reviews, 'task.json'), JSON.stringify({candidateCommit: head, reviewedCommit: head, status: 'PASS', attestedAt: new Date().toISOString()}), {mode: 0o600});
  return {...f, receipt};
}

test('cleanup refuses dirty, unmerged, occupied and mismatched ownership without changing resources', t => {
  const {projectRoot, options, receipt} = cleanupFixture(t);
  fs.writeFileSync(path.join(receipt.featureWorktree, 'dirty.txt'), 'dirty');
  assert.throws(() => validateCleanup({projectRoot, receipt}, {...options, processProbe: () => false}), {code: 'WORKTREE_DIRTY'});
  fs.rmSync(path.join(receipt.featureWorktree, 'dirty.txt'));
  assert.throws(() => validateCleanup({projectRoot, receipt}, {...options, processProbe: () => true}), {code: 'WORKTREE_OCCUPIED'});
  fs.writeFileSync(path.join(receipt.featureWorktree, 'change.txt'), 'change');
  git(receipt.featureWorktree, ['add', '.']);
  git(receipt.featureWorktree, ['commit', '-m', 'unmerged']);
  receipt.featureCommit = git(receipt.featureWorktree, ['rev-parse', 'HEAD']);
  assert.throws(() => validateCleanup({projectRoot, receipt}, {...options, processProbe: () => false}), {code: 'BRANCH_UNMERGED'});
  assert.ok(fs.existsSync(receipt.featureWorktree));
  assert.ok(git(projectRoot, ['show-ref', '--verify', 'refs/heads/codex/task-feature']));
});

test('cleanup backup failure never calls destructive controller and preserves unrelated resources', async t => {
  const {projectRoot, options, receipt} = cleanupFixture(t);
  git(projectRoot, ['branch', 'codex/unrelated']);
  let cleaned = false;
  const controller = {readDeliveryReceipt: () => receipt, cleanupDelivery: () => {cleaned = true;}};
  const backupRoot = path.join(options.backupRoot, 'file');
  fs.mkdirSync(options.backupRoot);
  fs.writeFileSync(backupRoot, 'cannot be directory');
  await assert.rejects(runDelivery({projectRoot, taskId: 'task', action: 'cleanup'}, {...options, controller, backupRoot, processProbe: () => false, quotaProbe: () => ({allowed: true})}));
  assert.equal(cleaned, false);
  assert.ok(fs.existsSync(receipt.featureWorktree));
  assert.ok(git(projectRoot, ['show-ref', '--verify', 'refs/heads/codex/unrelated']));
});

test('process-scoped native Git shim blocks maintenance and strips fetch pruning', async t => {
  const {projectRoot, options} = cleanupFixture(t);
  const head = git(projectRoot, ['rev-parse', 'HEAD']);
  git(projectRoot, ['update-ref', 'refs/remotes/origin/stale', head]);
  const previousPath = process.env.PATH;
  const controller = {startDelivery: () => {
    for (const maintenance of ['gc', 'prune', 'repack', 'maintenance', 'prune-packed']) {
      assert.equal(spawnSync('git', ['-C', projectRoot, maintenance]).status, 73);
    }
    const fetch = spawnSync('git', ['-C', projectRoot, 'fetch', '--prune', 'origin'], {encoding: 'utf8'});
    assert.equal(fetch.status, 0, fetch.stderr);
    assert.equal(spawnSync('git', ['-C', projectRoot, 'config', '--get', 'gc.auto'], {encoding: 'utf8'}).stdout.trim(), '0');
    assert.equal(git(projectRoot, ['rev-parse', 'refs/remotes/origin/stale']), head);
    return {status: 'started'};
  }};
  assert.equal((await runDelivery({projectRoot, taskId: 'task', action: 'start'}, {...options, controller})).status, 'started');
  assert.equal(process.env.PATH, previousPath);
  const bin = path.join(projectRoot, '.git/leon-engineering/git-safety/bin');
  assert.deepEqual(JSON.parse(fs.readFileSync(path.join(bin, 'package.json'))), {type: 'commonjs'});
  const original = fs.readFileSync(path.join(bin, 'git'));
  await runDelivery({projectRoot, taskId: 'task', action: 'start'}, {...options, controller});
  assert.deepEqual(fs.readFileSync(path.join(bin, 'git')), original);
});

function githubFixture(receipt, captured, {existing = [], protection, pr, checkConclusion = 'success', mergeParent = receipt.integrationCommit} = {}) {
  return (_command, args) => {
    captured.push(args);
    let result;
    if (args[0] === 'api' && args[1].endsWith('/check-runs')) result = [{check_runs: [{name: 'check', head_sha: receipt.integrationCommit, status: 'completed', conclusion: checkConclusion, app: {id: 1}}]}];
    else if (args[0] === 'api' && args[1].endsWith('/status')) result = {sha: receipt.integrationCommit, statuses: []};
    else if (args[0] === 'api' && args[1].endsWith('/protection')) result = protection;
    else if (args[0] === 'api' && /\/commits\//.test(args[1])) result = {sha: pr.mergeCommit.oid, parents: [{sha: mergeParent}]};
    else if (args[0] === 'api') result = {allow_auto_merge: false};
    else if (args[0] === 'pr' && args[1] === 'list') result = existing;
    else if (args[0] === 'pr' && args[1] === 'view') result = pr;
    else if (args[0] === 'pr' && args[1] === 'create') {
      assert.ok(args.includes('--body-file'));
      assert.equal(args.includes('--body'), false);
      assert.ok(fs.existsSync(args[args.indexOf('--body-file') + 1]));
      assert.equal(fs.readFileSync(args[args.indexOf('--body-file') + 1], 'utf8').includes('SECRET_SENTINEL'), false);
      return {status: 0, stdout: Buffer.from('https://github.com/fixture/repo/pull/1\n')};
    } else if (args[0] === 'pr' && args[1] === 'merge') result = {};
    else throw new Error('Unexpected fixture GitHub call');
    return {status: 0, stdout: Buffer.from(JSON.stringify(result)), stderr: Buffer.from('')};
  };
}

test('publication is PR first, body-file only, reuses matching PR and never enables auto-merge', async t => {
  const {projectRoot, options, receipt} = cleanupFixture(t);
  receipt.remoteUrl = 'https://github.com/fixture/repo.git';
  git(projectRoot, ['remote', 'set-url', 'origin', receipt.remoteUrl]);
  const calls = [];
  const controller = {readDeliveryReceipt: () => receipt, publishDelivery: params => {
    assert.deepEqual(params.pushDefault(), {status: 'protected'});
    const created = params.githubRunner('gh', ['pr', 'create', '--body', 'SECRET_SENTINEL'], {cwd: projectRoot});
    params.githubRunner('gh', ['pr', 'merge', '--auto', '--merge'], {cwd: projectRoot});
    return {status: 'awaiting_ci', url: created.stdout.toString().trim()};
  }};
  const common = {...options, controller, quotaProbe: () => ({allowed: true}), githubRunner: githubFixture(receipt, calls)};
  assert.equal((await runDelivery({projectRoot, taskId: 'task', action: 'publish'}, common)).safetyAutoMergeDeferred, true);
  assert.equal(calls.some(args => args.includes('--auto')), false);
  assert.equal(fs.readFileSync(path.join(projectRoot, 'logs/git-safety.jsonl'), 'utf8').includes('SECRET_SENTINEL'), false);
  calls.length = 0;
  common.githubRunner = githubFixture(receipt, calls, {existing: [{url: 'https://github.com/fixture/repo/pull/2', headRefOid: receipt.integrationCommit}]});
  assert.equal((await runDelivery({projectRoot, taskId: 'task', action: 'publish'}, common)).url, 'https://github.com/fixture/repo/pull/2');
  assert.equal(calls.some(args => args[1] === 'create'), false);
});

test('status requires exact reviewed SHA, checks, approval and protection before ordinary merge', async t => {
  const {projectRoot, options, receipt} = cleanupFixture(t);
  receipt.remoteUrl = 'https://github.com/fixture/repo.git'; receipt.mode = 'pr'; receipt.pullRequest = {url: 'https://github.com/fixture/repo/pull/1'};
  git(projectRoot, ['remote', 'set-url', 'origin', receipt.remoteUrl]);
  const calls = [];
  const protection = {required_status_checks: {strict: true, checks: [{context: 'check'}]}, required_pull_request_reviews: {required_approving_review_count: 1}, enforce_admins: {enabled: true}, required_conversation_resolution: {enabled: true}};
  const pr = {state: 'OPEN', headRefOid: receipt.integrationCommit, baseRefName: 'master', mergeStateStatus: 'CLEAN', reviewDecision: 'APPROVED', statusCheckRollup: [{name: 'check', status: 'COMPLETED', conclusion: 'SUCCESS'}]};
  const controller = {readDeliveryReceipt: () => receipt, refreshDeliveryStatus: params => params.resolveCiStatus({}, receipt)};
  const common = {...options, controller, quotaProbe: () => ({allowed: true}), githubRunner: githubFixture(receipt, calls, {protection, pr})};
  fs.unlinkSync(path.join(projectRoot, '.git/leon-engineering/git-safety/reviews/task.json'));
  await runDelivery({projectRoot, taskId: 'task', action: 'status'}, common);
  assert.equal(calls.some(args => args[1] === 'merge'), false);
  await assert.rejects(runDelivery({projectRoot, taskId: 'task', action: 'status', reviewedCommit: '0'.repeat(40)}, common), {code: 'REVIEWED_COMMIT_MISMATCH'});
  pr.reviewDecision = '';
  await assert.rejects(runDelivery({projectRoot, taskId: 'task', action: 'status', reviewedCommit: receipt.integrationCommit}, common), {code: 'REVIEW_NOT_APPROVED'});
  protection.required_pull_request_reviews.required_approving_review_count = 0;
  await runDelivery({projectRoot, taskId: 'task', action: 'status', reviewedCommit: receipt.integrationCommit}, common);
  const merge = calls.find(args => args[1] === 'merge');
  assert.ok(merge.includes('--match-head-commit'));
  assert.equal(merge[merge.indexOf('--match-head-commit') + 1], receipt.integrationCommit);
  assert.equal(merge.includes('--admin'), false);
});

test('cleanup removes only merged task history and leaves unrelated branches/worktrees intact', async t => {
  const {root, projectRoot, options, receipt} = cleanupFixture(t);
  const history = path.join(root, 'history');
  const unrelated = path.join(root, 'unrelated');
  git(projectRoot, ['worktree', 'add', '-b', 'codex/integrate-task-r0', history]);
  git(projectRoot, ['worktree', 'add', '-b', 'codex/unrelated', unrelated]);
  receipt.integrationHistory = [{branch: 'codex/integrate-task-r0', worktree: history, commit: receipt.integrationCommit}];
  const controller = {readDeliveryReceipt: () => receipt, cleanupDelivery: () => {
    for (const target of [receipt.featureWorktree, receipt.integrationWorktree]) git(projectRoot, ['worktree', 'remove', target]);
    for (const branch of [receipt.featureBranch, receipt.integrationBranch, 'codex/integrate-task-r0']) git(projectRoot, ['branch', '-d', branch]);
    return {status: 'cleaned'};
  }};
  const result = await runDelivery({projectRoot, taskId: 'task', action: 'cleanup'}, {...options, controller, processProbe: () => false, quotaProbe: () => ({allowed: true})});
  assert.equal(result.safetyFsck, 'PASS');
  assert.equal(fs.existsSync(history), false);
  assert.ok(fs.existsSync(unrelated));
  assert.ok(git(projectRoot, ['show-ref', '--verify', 'refs/heads/codex/unrelated']));
});

test('backup scopes current checkout and preserves missing/other-task registrations without reading their secrets', t => {
  const {root, projectRoot, options} = fixture(t);
  const other = path.join(root, 'other');
  git(projectRoot, ['worktree', 'add', '-b', 'codex/other', other]);
  fs.writeFileSync(path.join(other, 'credentials.json'), 'OTHER_TASK_SECRET');
  const result = backupRepository({projectRoot}, options);
  const manifest = JSON.parse(fs.readFileSync(path.join(result.directory, 'manifest.json')));
  assert.equal(manifest.worktrees.length, 1);
  assert.equal(manifest.registeredWorktrees.length, 2);
  assert.throws(() => backupRepository({projectRoot}, {...options, worktreePaths: [other]}), {code: 'SENSITIVE_UNTRACKED'});
  fs.rmSync(other, {recursive: true});
  assert.equal(backupRepository({projectRoot}, options).restoreVerified, true);
  assert.ok(git(projectRoot, ['worktree', 'list', '--porcelain']).includes(other));
});

test('legitimate token-efficiency reports are backed up while exact credential files are refused', t => {
  const {projectRoot, options} = fixture(t);
  const reports = path.join(projectRoot, '.ai/reports');
  fs.mkdirSync(reports, {recursive: true});
  fs.writeFileSync(path.join(reports, '2026-09-20-token-efficiency-review.md'), 'legitimate report');
  assert.equal(backupRepository({projectRoot}, options).restoreVerified, true);
  fs.writeFileSync(path.join(projectRoot, 'credentials.json'), 'SECRET_SENTINEL');
  assert.throws(() => backupRepository({projectRoot}, options), {code: 'SENSITIVE_UNTRACKED'});
});

test('lock replacement is preserved and async callbacks retain repository exclusion', async t => {
  const {projectRoot, options} = fixture(t);
  const target = path.join(projectRoot, '.git/leon-engineering/git-safety/repository.lock');
  await withRepositoryLock({projectRoot}, async () => {
    await Promise.resolve();
    assert.throws(() => withRepositoryLock({projectRoot}, () => {}, options), {code: 'REPOSITORY_LOCKED'});
  }, options);
  assert.equal(fs.existsSync(target), false);
  assert.throws(() => withRepositoryLock({projectRoot}, () => {
    fs.unlinkSync(target);
    fs.writeFileSync(target, '{"nonce":"foreign","pid":12}');
  }, options), {code: 'LOCK_OWNERSHIP_CHANGED'});
  assert.equal(fs.readFileSync(target, 'utf8'), '{"nonce":"foreign","pid":12}');
});

function failingGit(root, conflict = false) {
  const filename = path.join(root, 'failing-git');
  fs.writeFileSync(filename, `#!${process.execPath}\nconst {spawnSync}=require('node:child_process');const a=process.argv.slice(2);if(a.includes('--replace-all')&&a.includes('maintenance.auto')){${conflict ? "spawnSync('/usr/bin/git',['-C',a[a.indexOf('-C')+1],'config','--local','gc.auto','7']);" : ''}process.exit(1);}const r=spawnSync('/usr/bin/git',a,{stdio:'inherit'});process.exit(r.status??1);\n`, {mode: 0o700});
  return filename;
}

test('partial configuration failure restores exact previous values outside Git', t => {
  const {root, projectRoot, options} = fixture(t);
  git(projectRoot, ['config', '--local', 'gc.auto', '42']);
  git(projectRoot, ['config', '--local', 'maintenance.auto', 'true']);
  assert.throws(() => configureRepository({projectRoot}, {...options, gitPath: failingGit(root)}), {code: 'COMMAND_FAILED'});
  assert.equal(git(projectRoot, ['config', '--local', 'gc.auto']), '42');
  assert.equal(git(projectRoot, ['config', '--local', 'maintenance.auto']), 'true');
  assert.equal(git(projectRoot, ['config', '--local', 'user.name']), 'Fixture');
  assert.equal(fs.readdirSync(options.backupRoot).filter(name => name.startsWith('config-before-')).length, 1);
});

test('configuration rollback refuses external changes instead of overwriting them', t => {
  const {root, projectRoot, options} = fixture(t);
  assert.throws(() => configureRepository({projectRoot}, {...options, gitPath: failingGit(root, true)}), {code: 'CONFIG_ROLLBACK_CONFLICT'});
  assert.equal(git(projectRoot, ['config', '--local', 'gc.auto']), '7');
});

test('symlink state/backup/log parents and unknown shim files fail closed', async t => {
  const {root, projectRoot, options} = fixture(t);
  const actual = path.join(root, 'actual'); fs.mkdirSync(actual);
  const linked = path.join(root, 'linked'); fs.symlinkSync(actual, linked);
  assert.throws(() => backupRepository({projectRoot}, {...options, backupRoot: path.join(linked, 'backup')}), {code: 'PRIVATE_DIRECTORY_INVALID'});
  const logDir = path.join(projectRoot, 'logs'); fs.symlinkSync(actual, logDir);
  assert.throws(() => configureRepository({projectRoot}, options), {code: 'PRIVATE_DIRECTORY_INVALID'});
  fs.unlinkSync(logDir);
  const shim = path.join(projectRoot, '.git/leon-engineering/git-safety/bin/git');
  fs.mkdirSync(path.dirname(shim), {recursive: true}); fs.writeFileSync(shim, 'unknown preserved');
  await assert.rejects(runDelivery({projectRoot, taskId: 'task', action: 'start'}, {...options, controller: {startDelivery: () => ({})}}), {code: 'SHIM_INVALID'});
  assert.equal(fs.readFileSync(shim, 'utf8'), 'unknown preserved');
});

test('cleanup binds commit and worktree ownership and refuses missing undocumented worktrees', t => {
  const {projectRoot, options, receipt} = cleanupFixture(t);
  const safe = {...options, processProbe: () => false};
  assert.throws(() => validateCleanup({projectRoot, receipt: {...receipt, featureCommit: '0'.repeat(40)}}, safe), {code: 'TASK_COMMIT_MISMATCH'});
  assert.throws(() => validateCleanup({projectRoot, receipt: {...receipt, featureWorktree: receipt.integrationWorktree}}, safe), {code: 'TASK_OWNERSHIP_MISMATCH'});
  git(projectRoot, ['worktree', 'remove', receipt.featureWorktree]);
  assert.throws(() => validateCleanup({projectRoot, receipt}, safe), {code: 'WORKTREE_UNAVAILABLE'});
});

test('merged status refuses skipped required checks and mismatched merge parents', async t => {
  const {projectRoot, options, receipt} = cleanupFixture(t);
  receipt.remoteUrl = 'https://github.com/fixture/repo.git'; receipt.mode = 'pr'; receipt.pullRequest = {url: 'https://github.com/fixture/repo/pull/1'};
  git(projectRoot, ['remote', 'set-url', 'origin', receipt.remoteUrl]);
  const protection = {required_status_checks: {strict: true, checks: [{context: 'check', app_id: 1}]}, required_pull_request_reviews: {required_approving_review_count: 0}, enforce_admins: {enabled: true}, required_conversation_resolution: {enabled: true}};
  const pr = {state: 'MERGED', headRefOid: receipt.integrationCommit, baseRefName: 'master', reviewDecision: '', statusCheckRollup: [{name: 'check', status: 'COMPLETED', conclusion: 'SKIPPED'}], mergeCommit: {oid: '1'.repeat(40)}};
  const controller = {readDeliveryReceipt: () => receipt, refreshDeliveryStatus: params => params.resolveCiStatus({}, receipt)};
  const common = {...options, controller};
  fs.unlinkSync(path.join(projectRoot, '.git/leon-engineering/git-safety/reviews/task.json'));
  assert.equal((await runDelivery({projectRoot, taskId: 'task', action: 'status'}, {...common, githubRunner: githubFixture(receipt, [], {protection, pr})})).status, 'pending');
  await assert.rejects(runDelivery({projectRoot, taskId: 'task', action: 'status', reviewedCommit: receipt.integrationCommit}, {...common, githubRunner: githubFixture(receipt, [], {protection, pr, checkConclusion: 'skipped'})}), {code: 'MERGE_GATES_NOT_PASSED'});
  pr.statusCheckRollup[0].conclusion = 'SUCCESS';
  await assert.rejects(runDelivery({projectRoot, taskId: 'task', action: 'status'}, {...common, githubRunner: githubFixture(receipt, [], {protection, pr, mergeParent: '2'.repeat(40)})}), {code: 'MERGE_IDENTITY_UNPROVEN'});
  assert.equal((await runDelivery({projectRoot, taskId: 'task', action: 'status'}, {...common, githubRunner: githubFixture(receipt, [], {protection, pr})})).status, 'passed');
});

test('prepare cannot remove unmerged history through controller replacement paths', async t => {
  const {projectRoot, options, receipt} = cleanupFixture(t);
  const controller = {readDeliveryReceipt: () => receipt, prepareDelivery: () => assert.fail('must not call destructive prepare')};
  await assert.rejects(runDelivery({projectRoot, taskId: 'task', action: 'prepare', replacePrepared: true}, {...options, controller}), {code: 'PREPARE_REMOVAL_BLOCKED'});
  await assert.rejects(runDelivery({projectRoot, taskId: 'task', action: 'prepare'}, {...options, controller}), {code: 'PREPARE_REMOVAL_BLOCKED'});
  assert.ok(fs.existsSync(receipt.integrationWorktree));
});

test('CLI exposes no rollback, controller path, arbitrary command or malformed review attestation', () => {
  for (const extra of [['--rollback'], ['--controller', '/tmp/evil'], ['--command', 'rm'], ['--status', '--reviewed-commit', 'not-a-sha']]) {
    assert.throws(() => parseCli(['delivery', '--project', '.', '--task-id', 'task', ...extra]));
  }
});

test('cleanup preserves concurrent unrelated fast-forward commits and newly registered worktrees', async t => {
  const {root, projectRoot, options, receipt} = cleanupFixture(t);
  const unrelated = path.join(root, 'concurrent');
  git(projectRoot, ['worktree', 'add', '-b', 'codex/concurrent', unrelated]);
  let newCommit;
  const controller = {readDeliveryReceipt: () => receipt, cleanupDelivery: () => {
    fs.writeFileSync(path.join(unrelated, 'new.txt'), 'another task advances');
    git(unrelated, ['add', '.']); git(unrelated, ['commit', '-m', 'concurrent advance']);
    newCommit = git(unrelated, ['rev-parse', 'HEAD']);
    git(projectRoot, ['worktree', 'add', '-b', 'codex/new-task', path.join(root, 'new-task')]);
    for (const target of [receipt.featureWorktree, receipt.integrationWorktree]) git(projectRoot, ['worktree', 'remove', target]);
    for (const branch of [receipt.featureBranch, receipt.integrationBranch]) git(projectRoot, ['branch', '-d', branch]);
    return {status: 'cleaned'};
  }};
  const result = await runDelivery({projectRoot, taskId: 'task', action: 'cleanup'}, {...options, controller, processProbe: () => false, quotaProbe: () => ({allowed: true})});
  assert.equal(result.status, 'cleaned');
  assert.ok(result.concurrentRefAdvances.some(item => item.newCommit === newCommit));
  assert.equal(git(unrelated, ['rev-parse', 'HEAD']), newCommit);
  assert.ok(fs.existsSync(path.join(root, 'new-task')));
});

test('controller task locks remain independent and are never removed by repository-lock cleanup', async t => {
  const {projectRoot, options, receipt} = cleanupFixture(t);
  const taskLock = path.join(projectRoot, '.git/leon-engineering/locks/task.lock');
  fs.mkdirSync(path.dirname(taskLock), {recursive: true}); fs.writeFileSync(taskLock, '{"pid":99999999}');
  const controller = {readDeliveryReceipt: () => ({...receipt, status: 'started'}), prepareDelivery: () => {throw new Error('delivery task is locked: task');}};
  await assert.rejects(runDelivery({projectRoot, taskId: 'task', action: 'prepare'}, {...options, controller}), {code: 'TASK_LOCKED'});
  assert.equal(fs.readFileSync(taskLock, 'utf8'), '{"pid":99999999}');
  assert.equal(fs.existsSync(path.join(projectRoot, '.git/leon-engineering/git-safety/repository.lock')), false);
  const record = JSON.parse(fs.readFileSync(path.join(projectRoot, 'logs/git-safety.jsonl'), 'utf8').trim());
  assert.equal(record.gitPath, '/usr/bin/git');
  assert.match(record.gitVersion, /^git version/);
  assert.match(record.head, /^[a-f0-9]{40}$/);
  assert.equal(typeof record.durationMs, 'number');
  assert.equal(record.code, 'TASK_LOCKED');
});

test('production mutation entry points reject another repository before config/ref/log changes', async t => {
  const {projectRoot, options} = fixture(t);
  const beforeConfig = fs.readFileSync(path.join(projectRoot, '.git/config'));
  const beforeRefs = git(projectRoot, ['show-ref']);
  const {identityRoot: _identityRoot, ...productionOptions} = options;
  assert.throws(() => configureRepository({projectRoot}, productionOptions), {code: 'REPOSITORY_IDENTITY_MISMATCH'});
  assert.throws(() => backupRepository({projectRoot}, productionOptions), {code: 'REPOSITORY_IDENTITY_MISMATCH'});
  await assert.rejects(runDelivery({projectRoot, taskId: 'task', action: 'start'}, productionOptions), {code: 'REPOSITORY_IDENTITY_MISMATCH'});
  for (const subcommand of ['configure', 'backup', 'delivery']) {
    const args = [path.resolve('scripts/git_safety.mjs'), subcommand, '--project', projectRoot, ...(subcommand === 'delivery' ? ['--task-id', 'task', '--start'] : [])];
    const result = spawnSync(process.execPath, args, {encoding: 'utf8'});
    assert.equal(result.status, 1);
    assert.ok(['REPOSITORY_IDENTITY_MISMATCH', 'HOST_UNSUPPORTED'].includes(JSON.parse(result.stderr).code));
  }
  assert.deepEqual(fs.readFileSync(path.join(projectRoot, '.git/config')), beforeConfig);
  assert.equal(git(projectRoot, ['show-ref']), beforeRefs);
  assert.equal(fs.existsSync(path.join(projectRoot, '.git/leon-engineering')), false);
  assert.equal(fs.existsSync(path.join(projectRoot, 'logs')), false);
  assert.equal(fs.existsSync(options.backupRoot), false);
  assert.equal(checkRepository({projectRoot}, productionOptions).fsck, 'PASS');
});

test('cleanup cannot trust forged ci_passed without matching operator review attestation', async t => {
  const {projectRoot, options, receipt} = cleanupFixture(t);
  const filename = path.join(projectRoot, '.git/leon-engineering/git-safety/reviews/task.json');
  fs.unlinkSync(filename);
  let cleaned = false;
  const controller = {readDeliveryReceipt: () => receipt, cleanupDelivery: () => {cleaned = true;}};
  const safe = {...options, controller, processProbe: () => false, quotaProbe: () => ({allowed: true})};
  await assert.rejects(runDelivery({projectRoot, taskId: 'task', action: 'cleanup'}, safe), {code: 'REVIEW_NOT_ATTESTED'});
  fs.writeFileSync(filename, JSON.stringify({candidateCommit: '0'.repeat(40), reviewedCommit: '0'.repeat(40), status: 'PASS', attestedAt: new Date().toISOString()}));
  await assert.rejects(runDelivery({projectRoot, taskId: 'task', action: 'cleanup'}, safe), {code: 'REVIEW_NOT_ATTESTED'});
  assert.equal(cleaned, false);
  assert.ok(fs.existsSync(receipt.featureWorktree));
  assert.ok(fs.existsSync(receipt.integrationWorktree));
});

test('cleanup refuses ignored files/directories before backup without exporting their contents', async t => {
  const {projectRoot, options, receipt} = cleanupFixture(t);
  fs.appendFileSync(path.join(projectRoot, '.git/info/exclude'), '\nruntime.private\nprivate-data/\n');
  const sentinel = path.join(receipt.featureWorktree, 'runtime.private');
  fs.writeFileSync(sentinel, 'IGNORED_PRIVATE_SENTINEL');
  let cleaned = false;
  const controller = {readDeliveryReceipt: () => receipt, cleanupDelivery: () => {cleaned = true;}};
  const safe = {...options, controller, processProbe: () => false, quotaProbe: () => ({allowed: true})};
  await assert.rejects(runDelivery({projectRoot, taskId: 'task', action: 'cleanup'}, safe), {code: 'WORKTREE_IGNORED_DATA'});
  assert.equal(fs.readFileSync(sentinel, 'utf8'), 'IGNORED_PRIVATE_SENTINEL');
  assert.equal(fs.existsSync(options.backupRoot), false);
  fs.unlinkSync(sentinel);
  const privateDir = path.join(receipt.integrationWorktree, 'private-data');
  fs.mkdirSync(privateDir); fs.writeFileSync(path.join(privateDir, 'record'), 'DIRECTORY_SENTINEL');
  await assert.rejects(runDelivery({projectRoot, taskId: 'task', action: 'cleanup'}, safe), {code: 'WORKTREE_IGNORED_DATA'});
  assert.equal(fs.readFileSync(path.join(privateDir, 'record'), 'utf8'), 'DIRECTORY_SENTINEL');
  assert.equal(cleaned, false);
  assert.equal(fs.readFileSync(path.join(projectRoot, 'logs/git-safety.jsonl'), 'utf8').includes('IGNORED_PRIVATE_SENTINEL'), false);
});

test('cleanup rechecks ignored data created after backup immediately before destructive controller', async t => {
  const {projectRoot, options, receipt} = cleanupFixture(t);
  fs.appendFileSync(path.join(projectRoot, '.git/info/exclude'), '\nruntime.private\n');
  const sentinel = path.join(receipt.featureWorktree, 'runtime.private');
  let probes = 0; let cleaned = false;
  const controller = {readDeliveryReceipt: () => receipt, cleanupDelivery: () => {cleaned = true;}};
  const processProbe = () => { if (++probes === 3) fs.writeFileSync(sentinel, 'LATE_IGNORED_SENTINEL'); return false; };
  await assert.rejects(runDelivery({projectRoot, taskId: 'task', action: 'cleanup'}, {...options, controller, processProbe, quotaProbe: () => ({allowed: true})}), {code: 'WORKTREE_IGNORED_DATA'});
  assert.equal(cleaned, false);
  assert.equal(fs.readFileSync(sentinel, 'utf8'), 'LATE_IGNORED_SENTINEL');
  assert.ok(fs.existsSync(options.backupRoot));
});

test('hardlinked log target is refused without appending to an external victim', t => {
  const {root, projectRoot, options} = fixture(t);
  const victim = path.join(root, 'victim'); fs.writeFileSync(victim, 'ORIGINAL\n');
  fs.mkdirSync(path.join(projectRoot, 'logs'));
  fs.linkSync(victim, path.join(projectRoot, 'logs/git-safety.jsonl'));
  assert.throws(() => configureRepository({projectRoot}, options), {code: 'LOG_FILE_INVALID'});
  assert.equal(fs.readFileSync(victim, 'utf8'), 'ORIGINAL\n');
});

test('log symlink and replacement races never append to the raced target or victim', t => {
  for (const phase of ['symlink-before-open', 'replace-before-open', 'replace-after-open']) {
    const {root, projectRoot, options} = fixture(t);
    const victim = path.join(root, 'victim'); fs.writeFileSync(victim, 'VICTIM_UNCHANGED\n');
    fs.mkdirSync(path.join(projectRoot, 'logs'));
    const target = path.join(projectRoot, 'logs/git-safety.jsonl'); fs.writeFileSync(target, 'LOG_UNCHANGED\n');
    const held = path.join(root, 'held-log');
    const originalOpen = fs.openSync;
    let raced = false;
    fs.openSync = function(filename, flags, mode) {
      if (filename !== target || raced) return originalOpen.call(fs, filename, flags, mode);
      raced = true;
      if (phase === 'replace-after-open') {
        const fd = originalOpen.call(fs, filename, flags, mode);
        fs.renameSync(target, held); fs.linkSync(victim, target); return fd;
      }
      fs.renameSync(target, held);
      if (phase === 'symlink-before-open') fs.symlinkSync(victim, target);
      else fs.linkSync(victim, target);
      return originalOpen.call(fs, filename, flags, mode);
    };
    try { assert.throws(() => configureRepository({projectRoot}, options), {code: 'LOG_FILE_INVALID'}); }
    finally { fs.openSync = originalOpen; }
    assert.equal(raced, true);
    assert.equal(fs.readFileSync(victim, 'utf8'), 'VICTIM_UNCHANGED\n');
    assert.equal(fs.readFileSync(held, 'utf8'), 'LOG_UNCHANGED\n');
  }
});

test('changed origin identity blocks receipt actions before any GitHub or destructive calls', async t => {
  const {root, projectRoot, options, receipt} = cleanupFixture(t);
  git(projectRoot, ['remote', 'set-url', 'origin', path.join(root, 'foreign.git')]);
  let calls = 0;
  const controller = {readDeliveryReceipt: () => receipt, publishDelivery: () => {calls++;}, cleanupDelivery: () => {calls++;}, refreshDeliveryStatus: () => {calls++;}};
  for (const action of ['publish', 'status', 'cleanup']) await assert.rejects(runDelivery({projectRoot, taskId: 'task', action}, {...options, controller, quotaProbe: () => {calls++; return {allowed: true};}}), {code: 'REMOTE_IDENTITY_CHANGED'});
  assert.equal(calls, 0);
  assert.ok(fs.existsSync(receipt.featureWorktree));
  assert.ok(fs.existsSync(receipt.integrationWorktree));
});

test('private CommonJS marker rejects unknown, symlinked and hardlinked files without overwriting them', async t => {
  for (const kind of ['unknown', 'symlink', 'hardlink']) {
    const {root, projectRoot, options} = cleanupFixture(t);
    const marker = path.join(projectRoot, '.git/leon-engineering/git-safety/bin/package.json');
    fs.mkdirSync(path.dirname(marker), {recursive: true});
    const victim = path.join(root, 'victim.json');
    fs.writeFileSync(victim, JSON.stringify({type: 'commonjs'}) + '\n');
    if (kind === 'unknown') fs.writeFileSync(marker, '{"type":"module"}\n');
    else if (kind === 'symlink') fs.symlinkSync(victim, marker);
    else fs.linkSync(victim, marker);
    const before = fs.readFileSync(marker);
    await assert.rejects(runDelivery({projectRoot, taskId: 'task', action: 'start'}, {...options, controller: {startDelivery: () => assert.fail('untrusted package scope must not execute')}}), {code: 'SHIM_INVALID'});
    assert.deepEqual(fs.readFileSync(marker), before);
    assert.equal(fs.readFileSync(victim, 'utf8'), '{"type":"commonjs"}\n');
  }
});

test('actual restore preserves private/read-only/executable tracked modes, patches, missing files and symlinks', t => {
  const {root, projectRoot, options} = fixture(t);
  fs.writeFileSync(path.join(projectRoot, 'private.txt'), 'private fixture');
  fs.writeFileSync(path.join(projectRoot, 'readonly.txt'), 'read-only fixture');
  fs.writeFileSync(path.join(projectRoot, 'run.sh'), '#!/bin/sh\nexit 0\n', {mode: 0o755});
  fs.writeFileSync(path.join(projectRoot, 'missing.txt'), 'will be removed');
  const outside = path.join(root, 'outside.txt'); fs.writeFileSync(outside, 'outside unchanged', {mode: 0o640});
  fs.symlinkSync(outside, path.join(projectRoot, 'tracked-link'));
  git(projectRoot, ['add', '.']); git(projectRoot, ['commit', '-m', 'tracked permissions fixture']);
  fs.chmodSync(path.join(projectRoot, 'private.txt'), 0o600);
  fs.chmodSync(path.join(projectRoot, 'readonly.txt'), 0o400);
  fs.chmodSync(path.join(projectRoot, 'run.sh'), 0o700);
  fs.writeFileSync(path.join(projectRoot, 'tracked.txt'), 'staged\n'); git(projectRoot, ['add', 'tracked.txt']);
  fs.writeFileSync(path.join(projectRoot, 'tracked.txt'), 'unstaged\n'); fs.chmodSync(path.join(projectRoot, 'tracked.txt'), 0o600);
  fs.chmodSync(path.join(projectRoot, 'missing.txt'), 0o400); fs.unlinkSync(path.join(projectRoot, 'missing.txt'));
  const result = backupRepository({projectRoot}, options);
  assert.equal(result.restoreVerified, true);
  const manifest = JSON.parse(fs.readFileSync(path.join(result.directory, 'manifest.json')));
  const tracked = Object.fromEntries(manifest.worktrees[0].tracked.map(item => [item.path, item]));
  assert.equal(tracked['private.txt'].mode, 0o600);
  assert.equal(tracked['readonly.txt'].mode, 0o400);
  assert.equal(tracked['run.sh'].mode, 0o700);
  assert.equal(tracked['missing.txt'].type, 'missing');
  assert.equal(tracked['tracked-link'].type, 'symlink');
  assert.equal(fs.statSync(outside).mode & 0o777, 0o640);
  assert.equal(fs.readFileSync(outside, 'utf8'), 'outside unchanged');
});

test('failed restore retains private uncertified draft and immutable failure status', t => {
  const {root, projectRoot, options} = fixture(t);
  const wrapper = path.join(root, 'tamper-restore-git');
  fs.writeFileSync(wrapper, `#!${process.execPath}\nconst fs=require('node:fs');const path=require('node:path');const {spawnSync}=require('node:child_process');const a=process.argv.slice(2);const r=spawnSync('/usr/bin/git',a,{stdio:'inherit'});if(r.status===0&&a.includes('worktree')&&a.includes('add')&&a.includes('--detach')){const target=a[a.indexOf('--detach')+1];if(!path.resolve(target).startsWith(${JSON.stringify(options.backupRoot + path.sep)}))process.exit(78);const backup=path.dirname(path.dirname(target));const manifest=JSON.parse(fs.readFileSync(path.join(backup,'manifest-draft.json')));const index=manifest.worktrees[0].tracked.findIndex(item=>item.path==='tracked.txt');fs.writeFileSync(path.join(backup,'worktrees/0/tracked',String(index)),'TAMPERED_ARTIFACT');}process.exit(r.status??1);\n`, {mode: 0o700});
  assert.throws(() => backupRepository({projectRoot}, {...options, gitPath: wrapper}), {code: 'BACKUP_HASH_MISMATCH'});
  const directory = path.join(options.backupRoot, fs.readdirSync(options.backupRoot)[0]);
  const draftPath = path.join(directory, 'manifest-draft.json');
  const draft = JSON.parse(fs.readFileSync(draftPath));
  assert.equal(draft.restoreVerified, false);
  assert.ok(draft.files.some(item => item.path === 'objects.pack'));
  assert.ok(draft.files.some(item => item.path === 'worktrees/0/unstaged.patch'));
  const status = JSON.parse(fs.readFileSync(path.join(directory, 'failure-status.json')));
  assert.equal(status.restoreVerified, false);
  assert.equal(status.status, 'FAIL');
  assert.equal(status.code, 'BACKUP_HASH_MISMATCH');
  assert.equal(fs.statSync(draftPath).mode & 0o777, 0o600);
  assert.equal(fs.statSync(path.join(directory, 'failure-status.json')).mode & 0o777, 0o600);
  assert.equal(fs.existsSync(path.join(directory, 'manifest.json')), false);
  assert.equal(fs.readFileSync(path.join(projectRoot, 'tracked.txt'), 'utf8'), 'base\n');
});

test('restored regular-file replacement by symlink/hardlink cannot chmod external data', t => {
  for (const kind of ['symlink', 'hardlink']) {
    const {root, projectRoot, options} = fixture(t);
    fs.chmodSync(path.join(projectRoot, 'tracked.txt'), 0o600);
    const outside = path.join(root, 'outside.txt'); fs.writeFileSync(outside, 'outside untouched', {mode: 0o640});
    const wrapper = path.join(root, 'replace-restore-git');
    fs.writeFileSync(wrapper, `#!${process.execPath}\nconst fs=require('node:fs');const path=require('node:path');const {spawnSync}=require('node:child_process');const a=process.argv.slice(2);const r=spawnSync('/usr/bin/git',a,{stdio:'inherit'});if(r.status===0&&a.includes('worktree')&&a.includes('add')&&a.includes('--detach')){const target=a[a.indexOf('--detach')+1];if(!path.resolve(target).startsWith(${JSON.stringify(options.backupRoot + path.sep)}))process.exit(78);const file=path.join(target,'tracked.txt');fs.unlinkSync(file);fs.${kind === 'symlink' ? 'symlinkSync' : 'linkSync'}(${JSON.stringify(outside)},file);}process.exit(r.status??1);\n`, {mode: 0o700});
    assert.throws(() => backupRepository({projectRoot}, {...options, gitPath: wrapper}), {code: 'RESTORE_FILE_INVALID'});
    assert.equal(fs.statSync(outside).mode & 0o777, 0o640);
    assert.equal(fs.readFileSync(outside, 'utf8'), 'outside untouched');
    assert.equal(fs.statSync(path.join(projectRoot, 'tracked.txt')).mode & 0o777, 0o600);
  }
});

test('tracked raw LF working copy survives Git CRLF checkout normalization with exact bytes and mode', t => {
  const {root, projectRoot, options} = fixture(t);
  const bytes = Buffer.from('@echo off\necho fixture\n');
  fs.writeFileSync(path.join(projectRoot, '.gitattributes'), '*.cmd text eol=crlf\n');
  fs.writeFileSync(path.join(projectRoot, '.gitignore'), 'logs/\n');
  fs.writeFileSync(path.join(projectRoot, 'fixture.cmd'), bytes);
  git(projectRoot, ['add', '.']); git(projectRoot, ['commit', '-m', 'CRLF normalization fixture']);
  fs.chmodSync(path.join(projectRoot, 'fixture.cmd'), 0o600);
  assert.equal(git(projectRoot, ['status', '--porcelain']), '');
  const probe = path.join(root, 'canonical-checkout');
  git(projectRoot, ['clone', '--no-hardlinks', projectRoot, probe]);
  assert.deepEqual(fs.readFileSync(path.join(probe, 'fixture.cmd')), Buffer.from('@echo off\r\necho fixture\r\n'));
  const result = backupRepository({projectRoot}, options);
  assert.equal(result.restoreVerified, true);
  const manifest = JSON.parse(fs.readFileSync(path.join(result.directory, 'manifest.json')));
  const tracked = manifest.worktrees[0].tracked;
  const index = tracked.findIndex(item => item.path === 'fixture.cmd');
  const artifact = path.join(result.directory, `worktrees/0/tracked/${index}`);
  assert.deepEqual(fs.readFileSync(artifact), bytes);
  assert.equal(tracked[index].sha256, crypto.createHash('sha256').update(bytes).digest('hex'));
  assert.equal(tracked[index].mode, 0o600);
  assert.equal(fs.statSync(artifact).mode & 0o777, 0o600);
  assert.equal(fs.statSync(path.dirname(artifact)).mode & 0o777, 0o700);
  assert.deepEqual(fs.readFileSync(path.join(projectRoot, 'fixture.cmd')), bytes);
  assert.equal(git(projectRoot, ['status', '--porcelain']), '');
});

test('tracked raw snapshot refuses source content/identity races and does not follow replaced symlinks', t => {
  for (const kind of ['content', 'symlink']) {
    const {root, projectRoot, options} = fixture(t);
    const source = path.join(projectRoot, 'tracked.txt');
    const outside = path.join(root, 'outside.txt'); fs.writeFileSync(outside, 'OUTSIDE_NOT_EXPORTED', {mode: 0o640});
    const originalOpen = fs.openSync; let raced = false;
    fs.openSync = function(filename, flags, mode) {
      if (filename === source && typeof flags === 'number' && !raced) {
        raced = true;
        if (kind === 'content') fs.writeFileSync(source, 'changed during snapshot');
        else { fs.unlinkSync(source); fs.symlinkSync(outside, source); }
      }
      return originalOpen.call(fs, filename, flags, mode);
    };
    try { assert.throws(() => backupRepository({projectRoot}, options), {code: 'BACKUP_RACE'}); }
    finally { fs.openSync = originalOpen; }
    assert.equal(raced, true);
    assert.equal(fs.statSync(outside).mode & 0o777, 0o640);
    assert.equal(fs.readFileSync(outside, 'utf8'), 'OUTSIDE_NOT_EXPORTED');
    const directory = path.join(options.backupRoot, fs.readdirSync(options.backupRoot)[0]);
    assert.equal(fs.existsSync(path.join(directory, 'manifest.json')), false);
    const draft = JSON.parse(fs.readFileSync(path.join(directory, 'manifest-draft.json')));
    const sentinelHash = crypto.createHash('sha256').update('OUTSIDE_NOT_EXPORTED').digest('hex');
    assert.equal(draft.files.some(file => file.sha256 === sentinelHash), false);
    assert.equal(JSON.parse(fs.readFileSync(path.join(directory, 'failure-status.json'))).code, 'BACKUP_RACE');
  }
});

function snapshotTree(projectRoot, contents) {
  const blob = spawnSync('/usr/bin/git', ['-C', projectRoot, 'hash-object', '-w', '--stdin'], {input: contents, encoding: 'utf8'});
  assert.equal(blob.status, 0);
  const tree = spawnSync('/usr/bin/git', ['-C', projectRoot, 'mktree'], {input: `100644 blob ${blob.stdout.trim()}\tsnapshot.txt\n`, encoding: 'utf8'});
  assert.equal(tree.status, 0);
  return {blob: blob.stdout.trim(), tree: tree.stdout.trim()};
}
function verifyPackedBlob(projectRoot, root, directory, oid, contents) {
  const bare = path.join(root, 'pack-proof.git');
  git(projectRoot, ['init', '--bare', '-b', 'master', bare]);
  const indexed = spawnSync('/usr/bin/git', ['-C', bare, 'index-pack', '--stdin'], {input: fs.readFileSync(path.join(directory, 'objects.pack')), encoding: 'utf8'});
  assert.equal(indexed.status, 0, indexed.stderr);
  assert.equal(git(bare, ['cat-file', '-p', oid]), contents);
}

test('as-of backup allows concurrent Codex tree updates/new unrelated worktrees and restores saved old closure', t => {
  const {root, projectRoot, options} = fixture(t);
  const ref = 'refs/codex/turn-diffs/checkpoints/fixture';
  const old = snapshotTree(projectRoot, 'OLD_SNAPSHOT_ONLY_BLOB');
  const newer = snapshotTree(projectRoot, 'NEW_SNAPSHOT_ONLY_BLOB');
  git(projectRoot, ['update-ref', ref, old.tree]);
  const unrelated = path.join(root, 'new-other');
  const wrapper = path.join(root, 'concurrent-snapshot-git');
  fs.writeFileSync(wrapper, `#!${process.execPath}\nconst {spawnSync}=require('node:child_process');const a=process.argv.slice(2);const r=spawnSync('/usr/bin/git',a,{stdio:'inherit'});if(r.status===0&&a.includes('pack-objects')){const root=${JSON.stringify(projectRoot)};for(const args of [['update-ref',${JSON.stringify(ref)},${JSON.stringify(newer.tree)}],['worktree','add','-b','codex/new-other',${JSON.stringify(unrelated)}]]){if(spawnSync('/usr/bin/git',['--no-optional-locks','-c','gc.auto=0','-c','maintenance.auto=false','-C',root,...args],{stdio:'ignore'}).status!==0)process.exit(79);}}process.exit(r.status??1);\n`, {mode: 0o700});
  const result = backupRepository({projectRoot}, {...options, gitPath: wrapper});
  assert.equal(result.restoreVerified, true);
  const manifest = JSON.parse(fs.readFileSync(path.join(result.directory, 'manifest.json')));
  assert.equal(manifest.metadataSemantics, 'as-of-capture');
  assert.equal(manifest.refs[ref], old.tree);
  assert.equal(git(projectRoot, ['rev-parse', ref]), newer.tree);
  assert.ok(fs.existsSync(unrelated));
  assert.equal(manifest.registeredWorktrees.some(item => item.worktree === unrelated), false);
  verifyPackedBlob(projectRoot, root, result.directory, old.blob, 'OLD_SNAPSHOT_ONLY_BLOB');
});

test('preservation anchors archive snapshot old OIDs changed before backup capture', t => {
  const {root, projectRoot, options} = fixture(t);
  const ref = 'refs/codex/turn-diffs/captures/base';
  const old = snapshotTree(projectRoot, 'PRE_CAPTURE_OLD_BLOB');
  const newer = snapshotTree(projectRoot, 'CAPTURE_CURRENT_BLOB');
  git(projectRoot, ['update-ref', ref, old.tree]);
  const preservationRefs = {[ref]: old.tree};
  git(projectRoot, ['update-ref', ref, newer.tree]);
  const result = backupRepository({projectRoot}, {...options, preservationRefs});
  const manifest = JSON.parse(fs.readFileSync(path.join(result.directory, 'manifest.json')));
  assert.equal(manifest.refs[ref], newer.tree);
  assert.equal(manifest.preservationRefs[ref], old.tree);
  verifyPackedBlob(projectRoot, root, result.directory, old.blob, 'PRE_CAPTURE_OLD_BLOB');
});

test('target HEAD/branch changes still fail backup despite allowing unrelated snapshot updates', t => {
  const {root, projectRoot, options} = fixture(t);
  const wrapper = path.join(root, 'move-target-git');
  fs.writeFileSync(wrapper, `#!${process.execPath}\nconst {spawnSync}=require('node:child_process');const a=process.argv.slice(2);const r=spawnSync('/usr/bin/git',a,{stdio:'inherit'});if(r.status===0&&a.includes('pack-objects')){if(spawnSync('/usr/bin/git',['-c','gc.auto=0','-c','maintenance.auto=false','-C',${JSON.stringify(projectRoot)},'commit','--allow-empty','-m','target moved'],{stdio:'ignore'}).status!==0)process.exit(79);}process.exit(r.status??1);\n`, {mode: 0o700});
  assert.throws(() => backupRepository({projectRoot}, {...options, gitPath: wrapper}), {code: 'BACKUP_RACE'});
});

test('cleanup preserves concurrent Codex tree pointers and verifies old snapshot backup before accepting update', async t => {
  const {root, projectRoot, options, receipt} = cleanupFixture(t);
  const ref = 'refs/codex/turn-diffs/checkpoints/cleanup';
  const old = snapshotTree(projectRoot, 'CLEANUP_OLD_BLOB');
  const newer = snapshotTree(projectRoot, 'CLEANUP_NEW_BLOB');
  git(projectRoot, ['update-ref', ref, old.tree]);
  const controller = {readDeliveryReceipt: () => receipt, cleanupDelivery: () => {
    git(projectRoot, ['update-ref', ref, newer.tree]);
    for (const target of [receipt.featureWorktree, receipt.integrationWorktree]) git(projectRoot, ['worktree', 'remove', target]);
    for (const branch of [receipt.featureBranch, receipt.integrationBranch]) git(projectRoot, ['branch', '-d', branch]);
    return {status: 'cleaned'};
  }};
  const result = await runDelivery({projectRoot, taskId: 'task', action: 'cleanup'}, {...options, controller, processProbe: () => false, quotaProbe: () => ({allowed: true})});
  assert.ok(result.concurrentRefAdvances.some(item => item.event === 'concurrent_snapshot_update' && item.oldCommit === old.tree && item.newCommit === newer.tree));
  assert.equal(git(projectRoot, ['rev-parse', ref]), newer.tree);
  assert.equal(JSON.parse(fs.readFileSync(path.join(result.safetyBackup, 'manifest.json'))).preservationRefs[ref], old.tree);
  verifyPackedBlob(projectRoot, root, result.safetyBackup, old.blob, 'CLEANUP_OLD_BLOB');
});

test('resource preflight rejects switched task branches before any generated data removal', t => {
  const {projectRoot, options, receipt} = cleanupFixture(t);
  const dependencies=path.join(receipt.featureWorktree,'node_modules');
  fs.mkdirSync(dependencies); fs.writeFileSync(path.join(dependencies,'proof'),'keep');
  fs.writeFileSync(path.join(projectRoot,'.git/info/exclude'),'/node_modules/\n');
  const safe={...options,processProbe:()=>false};
  assert.equal(validateResourceCleanup({projectRoot,receipt},safe).valid,true);
  assert.throws(()=>validateCleanup({projectRoot,receipt},safe),{code:'WORKTREE_IGNORED_DATA'});
  git(receipt.featureWorktree,['switch','-c','codex/other-task']);
  assert.throws(()=>validateResourceCleanup({projectRoot,receipt},safe),{code:'TASK_OWNERSHIP_MISMATCH'});
  assert.equal(fs.readFileSync(path.join(dependencies,'proof'),'utf8'),'keep');
});

test('cleaned controller state cannot hide incomplete safety finalization', async t => {
  const {projectRoot,options,receipt}=cleanupFixture(t);
  Object.assign(receipt,{status:'cleaned',mode:'pr',pullRequest:{url:'https://github.com/fixture/repo/pull/1'}});
  const state=path.join(projectRoot,'.git/leon-engineering/resource-closeout/task');fs.mkdirSync(state,{recursive:true});
  fs.writeFileSync(path.join(state,'git-finalization.json'),JSON.stringify({taskId:'task',candidateCommit:receipt.integrationCommit,restoreVerified:false,status:'pending'}));
  const controller={readDeliveryReceipt:()=>receipt,validateCleanedDelivery:()=>receipt};
  await assert.rejects(runDelivery({projectRoot,taskId:'task',action:'status'},{...options,controller}),{code:'CLOSEOUT_FINALIZATION_UNVERIFIED'});
});

test('completed closeout survives a later task removing its own refs and worktrees', async t => {
  const {projectRoot,options,receipt}=cleanupFixture(t);
  Object.assign(receipt,{status:'cleaned',mode:'pr',pullRequest:{url:'https://github.com/fixture/repo/pull/1'}});
  const state=path.join(projectRoot,'.git/leon-engineering/resource-closeout/task');fs.mkdirSync(state,{recursive:true});
  // This older snapshot contained a different task, which has since legitimately retired.
  fs.writeFileSync(path.join(state,'git-finalization.json'),JSON.stringify({taskId:'task',candidateCommit:receipt.integrationCommit,restoreVerified:true,status:'complete',resourceContractRequired:true,beforeRefs:{'refs/heads/other-completed-task':receipt.featureCommit},beforeWorktrees:[],managed:[],verifiedPreservationRefs:{}}));
  fs.writeFileSync(path.join(state,'receipt.json'),JSON.stringify({taskId:'task',ok:true,cache:{ok:true},status:'complete',gitCleanup:true,restoreVerified:true}));
  const controller={readDeliveryReceipt:()=>receipt,validateCleanedDelivery:()=>receipt};
  assert.equal((await runDelivery({projectRoot,taskId:'task',action:'status'},{...options,controller})).status,'cleaned');
  assert.equal((await runDelivery({projectRoot,taskId:'task',action:'cleanup'},{...options,controller,quotaProbe:()=>({allowed:true})})).status,'cleaned');
});

async function pendingSnapshotCloseout(t, {otherRetirement=false}={}) {
  const f=cleanupFixture(t), {projectRoot,receipt}=f;
  fs.appendFileSync(path.join(projectRoot,'.git/info/exclude'),'\nlogs/\n');
  const snapshot='refs/codex/turn-diffs/captures/123/fixture/base';
  const tree=git(projectRoot,['rev-parse','HEAD^{tree}']);
  git(projectRoot,['update-ref',snapshot,tree]);
  const head=receipt.integrationCommit;
  const other={taskId:'other-task',status:'cleaned',mode:'pr',ci:{status:'passed'},verification:{status:'passed'},integrationCommit:head,featureCommit:head,featureBranch:'codex/other-feature',integrationBranch:'codex/other-integration',featureWorktree:path.join(f.root,'other-feature'),integrationWorktree:path.join(f.root,'other-integration'),cleanup:Object.fromEntries(['featureWorktreeRemoved','integrationWorktreeRemoved','localBranchDeleted','remoteBranchDeleted'].map(key=>[key,true]))};
  Object.assign(other,{repositoryRoot:projectRoot,remote:receipt.remote,remoteUrl:receipt.remoteUrl,defaultBranch:receipt.defaultBranch});
  const retiredRefs=otherRetirement?[`refs/heads/${other.featureBranch}`,`refs/heads/${other.integrationBranch}`,`refs/remotes/origin/${other.integrationBranch}`]:[];
  for(const ref of retiredRefs)git(projectRoot,['update-ref',ref,head]);
  const beforeRefs=Object.fromEntries(git(projectRoot,['for-each-ref','--format=%(refname) %(objectname)']).split('\n').map(line=>line.split(' ')));
  const backup=backupRepository({projectRoot},{...f.options,backupVersion:2,worktreePaths:[projectRoot,receipt.featureWorktree,receipt.integrationWorktree],preservationRefs:beforeRefs});
  const state=path.join(projectRoot,'.git/leon-engineering/resource-closeout/task');fs.mkdirSync(state,{recursive:true});
  const managed=[{branch:receipt.featureBranch,worktree:receipt.featureWorktree,commit:receipt.featureCommit},{branch:receipt.integrationBranch,worktree:receipt.integrationWorktree,commit:receipt.integrationCommit}];
  const beforeWorktrees=managed.map(row=>({worktree:row.worktree,HEAD:receipt.featureCommit,branch:`refs/heads/${row.branch}`}));
  if(otherRetirement)beforeWorktrees.push({worktree:other.featureWorktree,HEAD:head,branch:`refs/heads/${other.featureBranch}`},{worktree:other.integrationWorktree,HEAD:head,branch:`refs/heads/${other.integrationBranch}`});
  const proof={taskId:'task',candidateCommit:receipt.integrationCommit,status:'pending',resourceContractRequired:true,restoreVerified:true,beforeRefs,beforeWorktrees,managed,verifiedPreservationRefs:beforeRefs};
  fs.writeFileSync(path.join(state,'git-finalization.json'),JSON.stringify(proof),{mode:0o600});
  fs.writeFileSync(path.join(state,'receipt.json'),JSON.stringify({taskId:'task',ok:true,cache:{ok:true},status:'blocked',blocked:[{phase:'git'}]}),{mode:0o600});
  for(const item of managed){git(projectRoot,['worktree','remove',item.worktree]);git(projectRoot,['branch','-d',item.branch]);}
  git(projectRoot,['update-ref','-d',snapshot]);
  receipt.status='cleaned';receipt.mode='pr';receipt.pullRequest={url:'https://github.com/fixture/repo/pull/1'};
  receipt.verification={status:'passed'};receipt.cleanup=Object.fromEntries(['featureWorktreeRemoved','integrationWorktreeRemoved','localBranchDeleted','remoteBranchDeleted'].map(key=>[key,true]));
  const controller={readDeliveryReceipt:()=>receipt,validateCleanedDelivery:()=>receipt};
  let otherState;
  if(otherRetirement){
    const base=path.join(projectRoot,'.git/leon-engineering');otherState=path.join(base,'resource-closeout',other.taskId);
    fs.mkdirSync(path.join(base,'deliveries'),{recursive:true});fs.mkdirSync(otherState,{recursive:true});
    const put=(file,value)=>fs.writeFileSync(file,JSON.stringify(value),{mode:0o600});
    put(path.join(base,'deliveries',other.taskId+'.json'),other);
    put(path.join(base,'git-safety/reviews',other.taskId+'.json'),{candidateCommit:head,reviewedCommit:head,status:'PASS'});
    put(path.join(otherState,'git-finalization.json'),{taskId:other.taskId,status:'complete',candidateCommit:head,restoreVerified:true,beforeRefs:Object.fromEntries(retiredRefs.map(ref=>[ref,head])),beforeWorktrees:beforeWorktrees.filter(row=>row.worktree===other.featureWorktree || row.worktree===other.integrationWorktree),managed:[{branch:other.featureBranch,worktree:other.featureWorktree,commit:head},{branch:other.integrationBranch,worktree:other.integrationWorktree,commit:head}]});
    put(path.join(otherState,'receipt.json'),{taskId:other.taskId,status:'complete',ok:true,cache:{ok:true},gitCleanup:true,restoreVerified:true,blocked:[]});
    for(const ref of retiredRefs)git(projectRoot,['update-ref','-d',ref]);
  }
  const resourceRevalidationProbe=(_repo,task,phase)=>{
    assert.equal(phase,'revalidate');
    const bytes=fs.readFileSync(path.join(state,'receipt.json'));
    return {ok:true,taskId:task,candidateCommit:receipt.integrationCommit,cache:{ok:true},previousReceiptSha256:crypto.createHash('sha256').update(bytes).digest('hex')};
  };
  return {...f,state,snapshot,tree,backup,other,otherState,retiredRefs,options:{...f.options,controller,resourceRevalidationProbe}};
}

test('explicit recovery keeps the pending proof and accepts only restore-verified retired Codex snapshots', async t => {
  const {recoverCloseoutFinalization}=await import('../../scripts/git_safety.mjs');
  const f=await pendingSnapshotCloseout(t), before=fs.readFileSync(path.join(f.state,'git-finalization.json'));
  const input={projectRoot:f.projectRoot,taskId:'task',backupDirectory:f.backup.directory};
  const preview=await recoverCloseoutFinalization(input,f.options);
  let validations=0;f.options.controller.validateCleanedDelivery=()=>{validations++;return f.receipt;};
  await recoverCloseoutFinalization(input,f.options);assert.equal(validations,0);
  assert.equal(preview.status,'preview');assert.deepEqual(preview.retiredSnapshots,[{ref:f.snapshot,oid:f.tree}]);
  assert.deepEqual(fs.readFileSync(path.join(f.state,'git-finalization.json')),before);
  assert.equal(fs.existsSync(path.join(f.state,'git-finalization-recovery.json')),false);
  const result=await recoverCloseoutFinalization({...input,apply:true,previewSha256:preview.previewSha256},f.options);
  assert.equal(result.status,'cleaned');assert.equal(result.restoreVerified,true);
  assert.deepEqual(fs.readFileSync(path.join(f.state,'git-finalization.json')),before);
  assert.equal(git(f.projectRoot,['for-each-ref','--format=%(refname)',f.snapshot]),'');
  assert.equal(JSON.parse(fs.readFileSync(path.join(f.state,'receipt.json'))).status,'complete');
  assert.equal((await runDelivery({projectRoot:f.projectRoot,taskId:'task',action:'status'},f.options)).status,'cleaned');
  assert.equal((await recoverCloseoutFinalization({...input,apply:true,previewSha256:preview.previewSha256},f.options)).status,'cleaned');
  const oid=git(f.projectRoot,['rev-parse','HEAD:tracked.txt']);
  fs.rmSync(path.join(f.projectRoot,'.git/objects',oid.slice(0,2),oid.slice(2)));
  await assert.rejects(recoverCloseoutFinalization({...input,apply:true,previewSha256:preview.previewSha256},f.options),{code:'OBJECT_INTEGRITY_FAILED'});
});

test('recovery refuses ordinary ref deletion, stale preview, wrong backup and changes during restore', async t => {
  const {recoverCloseoutFinalization}=await import('../../scripts/git_safety.mjs');
  const f=await pendingSnapshotCloseout(t), input={projectRoot:f.projectRoot,taskId:'task',backupDirectory:f.backup.directory};
  const preview=await recoverCloseoutFinalization(input,f.options);
  const other=fixture(t), unrelated=backupRepository({projectRoot:other.projectRoot},{...other.options,backupVersion:1});
  await assert.rejects(recoverCloseoutFinalization({...input,backupDirectory:unrelated.directory},f.options),{code:'CLOSEOUT_RECOVERY_BACKUP_INVALID'});
  await assert.rejects(recoverCloseoutFinalization({...input,apply:true,previewSha256:'0'.repeat(64)},f.options),{code:'CLOSEOUT_RECOVERY_STALE'});
  const proof=JSON.parse(fs.readFileSync(path.join(f.state,'git-finalization.json')));
  proof.beforeRefs['refs/heads/unknown-retired']=f.receipt.featureCommit;
  fs.writeFileSync(path.join(f.state,'git-finalization.json'),JSON.stringify(proof));
  await assert.rejects(recoverCloseoutFinalization(input,f.options),{code:'UNRELATED_REF_CHANGED'});
  delete proof.beforeRefs['refs/heads/unknown-retired'];
  fs.writeFileSync(path.join(f.state,'git-finalization.json'),JSON.stringify(proof));
  const changedPreview=await recoverCloseoutFinalization(input,f.options);
  await assert.rejects(recoverCloseoutFinalization({...input,apply:true,previewSha256:changedPreview.previewSha256},{...f.options,afterRecoveryVerified:()=>git(f.projectRoot,['update-ref','-d','refs/remotes/origin/master'])}),{code:'UNRELATED_REF_CHANGED'});
  assert.equal(JSON.parse(fs.readFileSync(path.join(f.state,'receipt.json'))).status,'blocked');
  assert.equal(fs.existsSync(path.join(f.state,'git-finalization-recovery.json')),false);
});

test('recovery requires an unmodified archive and hash-bound completion', async t => {
  const {recoverCloseoutFinalization}=await import('../../scripts/git_safety.mjs');
  const f=await pendingSnapshotCloseout(t), input={projectRoot:f.projectRoot,taskId:'task',backupDirectory:f.backup.directory};
  const preview=await recoverCloseoutFinalization(input,f.options);
  const manifestPath=path.join(f.backup.directory,'manifest.json'), bytes=fs.readFileSync(manifestPath);
  fs.appendFileSync(manifestPath,' ');
  await assert.rejects(recoverCloseoutFinalization({...input,apply:true,previewSha256:preview.previewSha256},f.options),{code:'BACKUP_METADATA_MISMATCH'});
  fs.writeFileSync(manifestPath,bytes);
  await recoverCloseoutFinalization({...input,apply:true,previewSha256:preview.previewSha256},f.options);
  const cert=JSON.parse(fs.readFileSync(path.join(f.state,'git-finalization-recovery.json')));
  fs.appendFileSync(path.join(f.state,cert.epoch),' ');
  await assert.rejects(runDelivery({projectRoot:f.projectRoot,taskId:'task',action:'status'},f.options),{code:'CLOSEOUT_FINALIZATION_UNVERIFIED'});
});

test('recovery keeps committed-object and backup ownership gates', async t => {
  const {recoverCloseoutFinalization}=await import('../../scripts/git_safety.mjs');
  const f=await pendingSnapshotCloseout(t), input={projectRoot:f.projectRoot,taskId:'task',backupDirectory:f.backup.directory};
  const oid=git(f.projectRoot,['rev-parse','HEAD:tracked.txt']);
  fs.rmSync(path.join(f.projectRoot,'.git/objects',oid.slice(0,2),oid.slice(2)));
  await assert.rejects(recoverCloseoutFinalization(input,f.options),{code:'OBJECT_INTEGRITY_FAILED'});
  assert.equal(JSON.parse(fs.readFileSync(path.join(f.state,'receipt.json'))).status,'blocked');
});

test('closeout recovery CLI defaults to preview and refuses unmatched execute flags', () => {
  const args=['closeout-recover','--project','/fixture','--task-id','task','--recovery-backup','/backup'];
  assert.equal(parseCli(args).options.apply,undefined);
  assert.throws(()=>parseCli([...args,'--apply']),{code:'CLI_ARGUMENT_REQUIRED'});
  assert.throws(()=>parseCli([...args,'--status']),{code:'CLI_ARGUMENT_REQUIRED'});
  assert.equal(parseCli([...args,'--apply','--preview-sha256','a'.repeat(64)]).options.apply,true);
});

test('recovery recognizes another fully finalized delivery without guessing retired ref ownership', async t => {
  const {recoverCloseoutFinalization}=await import('../../scripts/git_safety.mjs');
  const f=await pendingSnapshotCloseout(t,{otherRetirement:true}), input={projectRoot:f.projectRoot,taskId:'task',backupDirectory:f.backup.directory};
  const preview=await recoverCloseoutFinalization(input,f.options);
  assert.deepEqual(preview.retiredDeliveries.map(row=>row.ref).sort(),f.retiredRefs.sort());
  assert.equal(preview.retiredWorktrees.length,2);
  const result=await recoverCloseoutFinalization({...input,apply:true,previewSha256:preview.previewSha256},f.options);
  assert.equal(result.status,'cleaned');
  assert.equal((await runDelivery({projectRoot:f.projectRoot,taskId:'task',action:'status'},f.options)).status,'cleaned');
});

test('a retired delivery cannot authorize a reappeared or unrelated worktree', async t => {
  const {recoverCloseoutFinalization}=await import('../../scripts/git_safety.mjs');
  const f=await pendingSnapshotCloseout(t,{otherRetirement:true});
  fs.mkdirSync(f.other.featureWorktree);
  await assert.rejects(recoverCloseoutFinalization({projectRoot:f.projectRoot,taskId:'task',backupDirectory:f.backup.directory},f.options),{code:'UNRELATED_WORKTREE_CHANGED'});
  assert.equal(fs.existsSync(f.other.featureWorktree),true);
});

test('another pending or tampered retirement is still an unknown ordinary deletion', async t => {
  const {recoverCloseoutFinalization}=await import('../../scripts/git_safety.mjs');
  const f=await pendingSnapshotCloseout(t,{otherRetirement:true}), input={projectRoot:f.projectRoot,taskId:'task',backupDirectory:f.backup.directory};
  const file=path.join(f.otherState,'git-finalization.json'), value=JSON.parse(fs.readFileSync(file));
  value.status='pending';fs.writeFileSync(file,JSON.stringify(value));
  await assert.rejects(recoverCloseoutFinalization(input,f.options),{code:'UNRELATED_REF_CHANGED'});
  value.status='complete';fs.writeFileSync(file,JSON.stringify(value));
  const preview=await recoverCloseoutFinalization(input,f.options);
  const resource=path.join(f.otherState,'receipt.json');fs.appendFileSync(resource,' ');
  await assert.rejects(recoverCloseoutFinalization({...input,apply:true,previewSha256:preview.previewSha256},f.options),{code:'CLOSEOUT_RECOVERY_STALE'});
});

test('retirement rejects cross-repository, ambiguous and unmerged branch claims', async t => {
  const {recoverCloseoutFinalization}=await import('../../scripts/git_safety.mjs');
  const f=await pendingSnapshotCloseout(t,{otherRetirement:true}), input={projectRoot:f.projectRoot,taskId:'task',backupDirectory:f.backup.directory};
  const directory=path.join(f.projectRoot,'.git/leon-engineering/deliveries'), file=path.join(directory,f.other.taskId+'.json');
  const original=fs.readFileSync(file), other=JSON.parse(original);
  other.repositoryRoot=f.root;fs.writeFileSync(file,JSON.stringify(other));
  await assert.rejects(recoverCloseoutFinalization(input,f.options),{code:'UNRELATED_REF_CHANGED'});
  fs.writeFileSync(file,original);
  const duplicate=path.join(directory,'ambiguous-task.json');fs.writeFileSync(duplicate,JSON.stringify({...f.other,taskId:'ambiguous-task'}),{mode:0o600});
  await assert.rejects(recoverCloseoutFinalization(input,f.options),{code:'UNRELATED_REF_CHANGED'});
  fs.unlinkSync(duplicate);
  const tree=git(f.projectRoot,['rev-parse','HEAD^{tree}']);
  const child=git(f.projectRoot,['commit-tree',tree,'-p',f.receipt.integrationCommit,'-m','unmerged branch']);
  const proofFile=path.join(f.otherState,'git-finalization.json'), proof=JSON.parse(fs.readFileSync(proofFile));
  other.repositoryRoot=f.projectRoot;other.featureCommit=child;fs.writeFileSync(file,JSON.stringify(other));
  proof.managed.find(row=>row.branch===other.featureBranch).commit=child;
  proof.beforeRefs[`refs/heads/${other.featureBranch}`]=child;
  fs.writeFileSync(proofFile,JSON.stringify(proof));
  await assert.rejects(recoverCloseoutFinalization(input,f.options),{code:'UNRELATED_REF_CHANGED'});
});

test('resource revalidation accepts only cleaned pending deliveries without replaying deletion', () => {
  const source=fileURLToPath(new URL('../research_web/test_iteration_revalidation.py',import.meta.url));
  const result=spawnSync('python3',[source],{encoding:'utf8',env:{...process.env,PYTHONPATH:path.resolve(path.dirname(source),'../..'),PYTHONDONTWRITEBYTECODE:'1'}});
  assert.equal(result.status,0,result.stderr);
  assert.match(result.stderr,/Ran 4 tests/);
});

test('enabled resource contract receives revalidate through the Python process boundary', async t => {
  const f=await pendingSnapshotCloseout(t), root=f.projectRoot;
  fs.mkdirSync(path.join(root,'scripts'));fs.mkdirSync(path.join(root,'.agents'));
  for(const name of ['git_safety.mjs','git_backup_store.mjs','backup_fd_clone.mjs','backup_fd_clone.py','backup_capacity.mjs'])fs.copyFileSync(new URL(`../../scripts/${name}`,import.meta.url),path.join(root,'scripts',name));
  fs.writeFileSync(path.join(root,'.agents/resource-closeout.json'),'{}');
  const python=spawnSync('python3',['-c','import sys;print(sys.executable)'],{encoding:'utf8'});
  assert.equal(python.status,0,python.stderr);
  fs.mkdirSync(path.join(root,'.venv/bin'),{recursive:true});fs.symlinkSync(python.stdout.trim(),path.join(root,'.venv/bin/python'));
  const pkg=path.join(root,'research_workbench_entrypoint');fs.mkdirSync(pkg);fs.writeFileSync(path.join(pkg,'__init__.py'),'');
  fs.writeFileSync(path.join(pkg,'iteration_resources.py'),[
    'import json,hashlib,sys', 'from pathlib import Path',
    'phase=sys.argv[sys.argv.index("--phase")+1]',
    'Path("observed-phase.txt").write_text(phase)',
    'assert phase=="revalidate", phase',
    'r=Path(".git/leon-engineering/resource-closeout/task/receipt.json").read_bytes()',
    'd=json.loads(Path("bridge-delivery.json").read_text())',
    'print(json.dumps(dict(ok=True,taskId="task",candidateCommit=d["integrationCommit"],cache=dict(ok=True),previousReceiptSha256=hashlib.sha256(r).hexdigest())))',
  ].join('\n'));
  fs.writeFileSync(path.join(root,'bridge-delivery.json'),JSON.stringify(f.receipt));
  const {recoverCloseoutFinalization}=await import(pathToFileURL(path.join(root,'scripts/git_safety.mjs')).href);
  const input={projectRoot:root,taskId:'task',backupDirectory:f.backup.directory};
  const preview=await recoverCloseoutFinalization(input,f.options);
  assert.equal(fs.existsSync(path.join(root,'observed-phase.txt')),false);
  await recoverCloseoutFinalization({...input,apply:true,previewSha256:preview.previewSha256},f.options);
  assert.equal(fs.readFileSync(path.join(root,'observed-phase.txt'),'utf8'),'revalidate');
});

function baseRefreshFixture(t, {includeBase = true, includePrevious = true} = {}) {
  const f = fixture(t);
  const base = git(f.projectRoot, ['rev-parse', 'HEAD']);
  const feature = path.join(f.root, 'refresh-feature');
  git(f.projectRoot, ['remote', 'add', 'origin', 'https://github.com/fixture/repo.git']);
  git(f.projectRoot, ['worktree', 'add', '-b', 'codex/task-feature', feature]);
  fs.writeFileSync(path.join(feature, 'feature.txt'), 'feature\n');
  git(feature, ['add', '.']); git(feature, ['commit', '-m', 'feature']);
  const previous = git(feature, ['rev-parse', 'HEAD']);
  fs.writeFileSync(path.join(f.projectRoot, 'upstream.txt'), 'upstream\n');
  git(f.projectRoot, ['add', '.']); git(f.projectRoot, ['commit', '-m', 'upstream']);
  const latest = git(f.projectRoot, ['rev-parse', 'HEAD']);
  git(f.projectRoot, ['update-ref', 'refs/remotes/origin/master', latest]);
  const integration = path.join(f.root, 'refresh-integration');
  git(f.projectRoot, ['worktree', 'add', '-b', 'codex/integrate-task', integration, includePrevious ? previous : latest]);
  if (includeBase && includePrevious) git(integration, ['merge', '--no-ff', '--no-edit', latest]);
  const candidate = git(integration, ['rev-parse', 'HEAD']);
  const receipt = {schemaVersion: 1, taskId: 'task', repositoryRoot: f.projectRoot, remote: 'origin', remoteUrl: 'https://github.com/fixture/repo.git', defaultBranch: 'master', featureBranch: 'codex/task-feature', featureWorktree: feature, featureCommit: previous, integrationBranch: 'codex/integrate-task', integrationWorktree: integration, integrationCommit: previous, integrationHistory: [], baseCommit: base, remoteCommit: base, mode: 'pr', pullRequest: {url: 'https://github.com/fixture/repo/pull/1', number: 1}, status: 'remote_moved', repairAttempts: 2, verification: {status: 'passed'}, ci: {status: 'passed', runs: [{id: 'old-run'}]}};
  const filename = path.join(f.projectRoot, '.git/leon-engineering/deliveries/task.json');
  fs.mkdirSync(path.dirname(filename), {recursive: true}); fs.writeFileSync(filename, JSON.stringify(receipt), {mode: 0o600});
  const calls = [];
  let onRead = () => {}, remoteBase = latest;
  const pr = {state: 'OPEN', headRefOid: previous, headRefName: receipt.integrationBranch, baseRefName: 'master'};
  const controller = {readDeliveryReceipt: () => JSON.parse(fs.readFileSync(filename)), prepareDelivery: () => assert.fail('must not remove or rebuild the integration worktree')};
  const githubRunner = (_command, args) => {
    calls.push(args); onRead(args);
    const result = args[0] === 'api' && args[1] === 'repos/fixture/repo/git/ref/heads/master' ? {object: {sha: remoteBase}} : args[0] === 'api' && args[1] === 'repos/fixture/repo' ? {allow_auto_merge: false} : args[0] === 'pr' && args[1] === 'view' ? pr : assert.fail('unexpected GitHub operation: ' + args.join(' '));
    return {status: 0, stdout: JSON.stringify(result), stderr: ''};
  };
  return {...f, receipt, filename, candidate, latest, calls, pr, safe: {...f.options, controller, githubRunner}, onRead: fn => {onRead = fn;}, setRemoteBase: value => {remoteBase = value;}};
}

test('remote advance recovery preserves the existing PR, worktrees and old commits, and invalidates stale evidence', async t => {
  const f = baseRefreshFixture(t), before = git(f.projectRoot, ['show-ref']);
  const result = await runDelivery({projectRoot: f.projectRoot, taskId: 'task', action: 'prepare'}, f.safe);
  const saved = JSON.parse(fs.readFileSync(f.filename));
  assert.equal(result.status, 'prepared');
  assert.equal(saved.baseCommit, f.latest); assert.equal(saved.remoteCommit, f.latest);
  assert.equal(saved.integrationCommit, f.candidate); assert.deepEqual(saved.pullRequest, f.receipt.pullRequest);
  assert.equal(saved.integrationWorktree, f.receipt.integrationWorktree); assert.equal(saved.featureWorktree, f.receipt.featureWorktree);
  assert.deepEqual(saved.ci, {status: 'pending', runs: []}); assert.equal(saved.verification, null);
  assert.equal(saved.repairAttempts, 2); assert.deepEqual(saved.integrationHistory, []);
  assert.equal(git(f.projectRoot, ['show-ref']), before);
  assert.equal(git(f.receipt.integrationWorktree, ['rev-parse', 'HEAD']), f.candidate);
  assert.ok(fs.existsSync(f.receipt.featureWorktree)); assert.ok(fs.existsSync(f.receipt.integrationWorktree));
  git(f.projectRoot, ['merge-base', '--is-ancestor', f.receipt.integrationCommit, f.candidate]);
  const snapshots = path.join(f.projectRoot, '.git/leon-engineering/git-safety/base-refresh/task');
  const files = fs.readdirSync(snapshots); assert.equal(files.length, 1);
  assert.deepEqual(JSON.parse(fs.readFileSync(path.join(snapshots, files[0]))), f.receipt);
  assert.equal(fs.statSync(path.join(snapshots, files[0])).mode & 0o777, 0o600);
  assert.ok(f.calls.every(args => args[0] === 'api' || args[0] === 'pr' && args[1] === 'view'));
});

for (const status of ['awaiting_ci', 'ci_failed']) test(`live published ${status} refreshes a moved base without consuming exhausted CI repair budget`, async t => {
  const f = baseRefreshFixture(t);
  f.receipt.status = status; f.receipt.repairAttempts = 3;
  fs.writeFileSync(f.filename, JSON.stringify(f.receipt));
  const before = git(f.projectRoot, ['show-ref']);
  const result = await runDelivery({projectRoot: f.projectRoot, taskId: 'task', action: 'prepare'}, f.safe);
  assert.equal(result.status, 'prepared');
  assert.equal(result.baseCommit, f.latest);
  assert.equal(result.repairAttempts, 3);
  assert.deepEqual(result.pullRequest, f.receipt.pullRequest);
  assert.equal(result.verification, null);
  assert.deepEqual(result.ci, {status: 'pending', runs: []});
  assert.equal(git(f.projectRoot, ['show-ref']), before);
  assert.ok(f.calls.every(args => args[0] === 'api' || args[0] === 'pr' && args[1] === 'view'));
});

test('live published base refresh rejects an unchanged master without mutating the receipt', async t => {
  const f = baseRefreshFixture(t);
  f.receipt.status = 'awaiting_ci'; f.receipt.repairAttempts = 3;
  fs.writeFileSync(f.filename, JSON.stringify(f.receipt)); f.setRemoteBase(f.receipt.baseCommit);
  const before = fs.readFileSync(f.filename);
  await assert.rejects(runDelivery({projectRoot: f.projectRoot, taskId: 'task', action: 'prepare'}, f.safe), {code: 'BASE_REFRESH_NOT_NEEDED'});
  assert.deepEqual(fs.readFileSync(f.filename), before);
});

for (const failure of ['dirty', 'foreign-pr']) test(`live published base refresh preserves guards with ${failure}`, async t => {
  const f = baseRefreshFixture(t);
  f.receipt.status = 'awaiting_ci'; f.receipt.repairAttempts = 3;
  fs.writeFileSync(f.filename, JSON.stringify(f.receipt));
  if (failure === 'dirty') fs.writeFileSync(path.join(f.receipt.integrationWorktree, 'untracked'), 'preserve');
  else f.pr.headRefOid = f.latest;
  const before = fs.readFileSync(f.filename);
  await assert.rejects(runDelivery({projectRoot: f.projectRoot, taskId: 'task', action: 'prepare'}, f.safe), {code: failure === 'dirty' ? 'WORKTREE_DIRTY' : 'PR_HEAD_MISMATCH'});
  assert.deepEqual(fs.readFileSync(f.filename), before);
});

test('remote advance recovery refuses dirty or wrong-branch worktrees without changing the receipt', async t => {
  const f = baseRefreshFixture(t), before = fs.readFileSync(f.filename);
  const dirty = path.join(f.receipt.integrationWorktree, 'untracked'); fs.writeFileSync(dirty, 'preserve');
  await assert.rejects(runDelivery({projectRoot: f.projectRoot, taskId: 'task', action: 'prepare'}, f.safe), {code: 'WORKTREE_DIRTY'});
  assert.deepEqual(fs.readFileSync(f.filename), before); assert.equal(fs.readFileSync(dirty, 'utf8'), 'preserve');
  fs.unlinkSync(dirty); git(f.receipt.integrationWorktree, ['switch', '-c', 'codex/other']);
  await assert.rejects(runDelivery({projectRoot: f.projectRoot, taskId: 'task', action: 'prepare'}, f.safe), {code: 'TASK_OWNERSHIP_MISMATCH'});
  assert.deepEqual(fs.readFileSync(f.filename), before);
});

test('remote advance recovery requires both the new base and the previous published candidate in ancestry', async t => {
  for (const settings of [{includeBase: false}, {includePrevious: false}]) {
    const f = baseRefreshFixture(t, settings), before = fs.readFileSync(f.filename);
    await assert.rejects(runDelivery({projectRoot: f.projectRoot, taskId: 'task', action: 'prepare'}, f.safe), {code: 'BASE_REFRESH_ANCESTRY_INVALID'});
    assert.deepEqual(fs.readFileSync(f.filename), before);
  }
});

test('remote advance recovery rejects a different PR head and concurrent receipt changes', async t => {
  const f = baseRefreshFixture(t), before = fs.readFileSync(f.filename);
  f.pr.headRefOid = '1'.repeat(40);
  await assert.rejects(runDelivery({projectRoot: f.projectRoot, taskId: 'task', action: 'prepare'}, f.safe), {code: 'PR_HEAD_MISMATCH'});
  assert.deepEqual(fs.readFileSync(f.filename), before);
  f.pr.headRefOid = f.receipt.integrationCommit;
  let reads = 0;
  f.onRead(() => { if (++reads === 3) fs.writeFileSync(f.filename, JSON.stringify({...f.receipt, repairAttempts: 3})); });
  await assert.rejects(runDelivery({projectRoot: f.projectRoot, taskId: 'task', action: 'prepare'}, f.safe), {code: 'DELIVERY_RECORD_CHANGED'});
  assert.equal(JSON.parse(fs.readFileSync(f.filename)).repairAttempts, 3);
  assert.ok(fs.existsSync(f.receipt.integrationWorktree));
});

test('remote advance recovery supports another advance before the prepared candidate was published', async t => {
  const f = baseRefreshFixture(t);
  await runDelivery({projectRoot: f.projectRoot, taskId: 'task', action: 'prepare'}, f.safe);
  const first = JSON.parse(fs.readFileSync(f.filename));
  fs.writeFileSync(path.join(f.projectRoot, 'later.txt'), 'later\n');
  git(f.projectRoot, ['add', '.']); git(f.projectRoot, ['commit', '-m', 'later master']);
  const latest = git(f.projectRoot, ['rev-parse', 'HEAD']);
  git(f.projectRoot, ['update-ref', 'refs/remotes/origin/master', latest]);
  git(f.receipt.integrationWorktree, ['merge', '--no-ff', '--no-edit', latest]);
  const candidate = git(f.receipt.integrationWorktree, ['rev-parse', 'HEAD']);
  fs.writeFileSync(f.filename, JSON.stringify({...first, status: 'remote_moved'}));
  f.setRemoteBase(latest);
  const result = await runDelivery({projectRoot: f.projectRoot, taskId: 'task', action: 'prepare'}, f.safe);
  assert.equal(result.status, 'prepared'); assert.equal(result.baseCommit, latest);
  assert.equal(result.integrationCommit, candidate); assert.deepEqual(result.pullRequest, f.receipt.pullRequest);
  git(f.projectRoot, ['merge-base', '--is-ancestor', f.candidate, candidate]);
  assert.equal(fs.readdirSync(path.join(f.projectRoot, '.git/leon-engineering/git-safety/base-refresh/task')).length, 2);
});

test('remote advance recovery rejects a moving remote base and never removes an existing integration lock', async t => {
  const f = baseRefreshFixture(t), before = fs.readFileSync(f.filename);
  let reads = 0;
  f.onRead(() => { if (++reads === 3) f.setRemoteBase('1'.repeat(40)); });
  await assert.rejects(runDelivery({projectRoot: f.projectRoot, taskId: 'task', action: 'prepare'}, f.safe), {code: 'REMOTE_BASE_CHANGED'});
  assert.deepEqual(fs.readFileSync(f.filename), before);
  f.onRead(() => {}); f.setRemoteBase(f.latest);
  const lock = path.join(f.projectRoot, '.git/leon-engineering/locks/integration.lock');
  fs.writeFileSync(lock, '99999999');
  await assert.rejects(runDelivery({projectRoot: f.projectRoot, taskId: 'task', action: 'prepare'}, f.safe), {code: 'TASK_LOCKED'});
  assert.equal(fs.readFileSync(lock, 'utf8'), '99999999');
  assert.deepEqual(fs.readFileSync(f.filename), before);
});

test('remote advance recovery rejects an unregistered PR rewind even when it is an actual ancestor', async t => {
  const f = baseRefreshFixture(t), before = fs.readFileSync(f.filename);
  f.pr.headRefOid = f.receipt.baseCommit;
  git(f.projectRoot, ['merge-base', '--is-ancestor', f.pr.headRefOid, f.receipt.integrationCommit]);
  await assert.rejects(runDelivery({projectRoot: f.projectRoot, taskId: 'task', action: 'prepare'}, f.safe), {code: 'PR_HEAD_MISMATCH'});
  assert.deepEqual(fs.readFileSync(f.filename), before);
});

test('remote advance recovery rejects PR and local candidate changes between its checks', async t => {
  const f = baseRefreshFixture(t), before = fs.readFileSync(f.filename);
  let reads = 0;
  f.onRead(args => { if (args[0] === 'pr' && ++reads === 2) f.pr.headRefOid = f.receipt.baseCommit; });
  await assert.rejects(runDelivery({projectRoot: f.projectRoot, taskId: 'task', action: 'prepare'}, f.safe), {code: 'PR_HEAD_MISMATCH'});
  assert.deepEqual(fs.readFileSync(f.filename), before);
  f.pr.headRefOid = f.receipt.integrationCommit; reads = 0;
  f.onRead(args => {
    if (args[0] === 'pr' && ++reads === 2) {
      fs.writeFileSync(path.join(f.receipt.integrationWorktree, 'newer.txt'), 'concurrent');
      git(f.receipt.integrationWorktree, ['add', '.']); git(f.receipt.integrationWorktree, ['commit', '-m', 'concurrent candidate']);
    }
  });
  await assert.rejects(runDelivery({projectRoot: f.projectRoot, taskId: 'task', action: 'prepare'}, f.safe), {code: 'DELIVERY_RECORD_CHANGED'});
  assert.deepEqual(fs.readFileSync(f.filename), before);
  assert.equal(fs.readFileSync(path.join(f.receipt.integrationWorktree, 'newer.txt'), 'utf8'), 'concurrent');
});

test('successful publication advances the pinned PR head and rejects a later rewind to the older published tip', async t => {
  const f = baseRefreshFixture(t);
  await runDelivery({projectRoot: f.projectRoot, taskId: 'task', action: 'prepare'}, f.safe);
  f.safe.quotaProbe = () => ({allowed: true});
  f.safe.controller.publishDelivery = () => {
    const updated = {...JSON.parse(fs.readFileSync(f.filename)), status: 'awaiting_ci'};
    fs.writeFileSync(f.filename, JSON.stringify(updated)); f.pr.headRefOid = updated.integrationCommit;
    return updated;
  };
  const published = await runDelivery({projectRoot: f.projectRoot, taskId: 'task', action: 'publish'}, f.safe);
  assert.equal(published.baseRefreshPublishedHead, f.candidate);
  assert.equal(JSON.parse(fs.readFileSync(f.filename)).baseRefreshPublishedHead, f.candidate);
  fs.writeFileSync(path.join(f.projectRoot, 'later.txt'), 'later\n');
  git(f.projectRoot, ['add', '.']); git(f.projectRoot, ['commit', '-m', 'later master']);
  const latest = git(f.projectRoot, ['rev-parse', 'HEAD']);
  git(f.projectRoot, ['update-ref', 'refs/remotes/origin/master', latest]);
  git(f.receipt.integrationWorktree, ['merge', '--no-ff', '--no-edit', latest]);
  const record = JSON.parse(fs.readFileSync(f.filename)); record.status = 'remote_moved'; fs.writeFileSync(f.filename, JSON.stringify(record));
  f.setRemoteBase(latest); f.pr.headRefOid = f.receipt.integrationCommit;
  const before = fs.readFileSync(f.filename);
  await assert.rejects(runDelivery({projectRoot: f.projectRoot, taskId: 'task', action: 'prepare'}, f.safe), {code: 'PR_HEAD_MISMATCH'});
  assert.deepEqual(fs.readFileSync(f.filename), before);
});

test('published-head bookkeeping cannot mutate a receipt rejected by the branch identity gate', async t => {
  const f = baseRefreshFixture(t);
  await runDelivery({projectRoot: f.projectRoot, taskId: 'task', action: 'prepare'}, f.safe);
  const record = {...JSON.parse(fs.readFileSync(f.filename)), status: 'awaiting_ci', defaultBranch: 'other'};
  fs.writeFileSync(f.filename, JSON.stringify(record)); const before = fs.readFileSync(f.filename);
  f.safe.quotaProbe = () => ({allowed: true});
  await assert.rejects(runDelivery({projectRoot: f.projectRoot, taskId: 'task', action: 'publish', repair: true}, f.safe), {code: 'DELIVERY_BRANCH_INVALID'});
  assert.deepEqual(fs.readFileSync(f.filename), before);
});

function unpublishedBaseRefreshFixture(t, settings = {}) {
  const f = baseRefreshFixture(t, settings);
  f.receipt = {...f.receipt, mode: null, pullRequest: null, remoteCommit: null};
  fs.writeFileSync(f.filename, JSON.stringify(f.receipt), {mode: 0o600});
  return f;
}

test('unpublished remote advance preserves all refs and null publication identity, snapshots privately and invalidates evidence', async t => {
  const f = unpublishedBaseRefreshFixture(t);
  fs.writeFileSync(path.join(f.receipt.featureWorktree, 'repair.txt'), 'latest feature repair\n');
  git(f.receipt.featureWorktree, ['add', '.']); git(f.receipt.featureWorktree, ['commit', '-m', 'feature repair']);
  const feature = git(f.receipt.featureWorktree, ['rev-parse', 'HEAD']);
  git(f.receipt.integrationWorktree, ['merge', '--no-ff', '--no-edit', feature]);
  const candidate = git(f.receipt.integrationWorktree, ['rev-parse', 'HEAD']);
  const refs = git(f.projectRoot, ['show-ref']);
  const result = await runDelivery({projectRoot: f.projectRoot, taskId: 'task', action: 'prepare'}, f.safe);
  assert.equal(result.status, 'prepared'); assert.equal(result.baseCommit, f.latest);
  assert.equal(result.integrationCommit, candidate); assert.equal(result.featureCommit, feature);
  for (const field of ['mode', 'pullRequest', 'remoteCommit']) assert.equal(result[field], null);
  assert.equal(result.baseRefreshPublishedHead, undefined);
  assert.equal(result.verification, null); assert.deepEqual(result.ci, {status: 'pending', runs: []});
  assert.equal(git(f.projectRoot, ['show-ref']), refs);
  assert.ok(f.calls.length >= 3); assert.ok(f.calls.every(args => args[0] === 'api'));
  const snapshots = path.join(f.projectRoot, '.git/leon-engineering/git-safety/base-refresh/task');
  const file = path.join(snapshots, fs.readdirSync(snapshots)[0]);
  assert.deepEqual(JSON.parse(fs.readFileSync(file)), f.receipt); assert.equal(fs.statSync(file).mode & 0o777, 0o600);
  assert.deepEqual(JSON.parse(fs.readFileSync(f.filename)), result);
});

test('unpublished recovery refuses incomplete or unknown publication identities, while pr mode still requires its PR', async t => {
  const f = unpublishedBaseRefreshFixture(t);
  for (const patch of [{mode: 'direct'}, {mode: undefined}, {pullRequest: {}}, {remoteCommit: f.latest}, {baseRefreshPublishedHead: f.receipt.integrationCommit}, {publishedAt: null}, {pushResult: {}}, {mode: 'pr', pullRequest: null}]) {
    const record = {...f.receipt, ...patch}; fs.writeFileSync(f.filename, JSON.stringify(record)); const before = fs.readFileSync(f.filename);
    await assert.rejects(runDelivery({projectRoot: f.projectRoot, taskId: 'task', action: 'prepare'}, f.safe));
    assert.deepEqual(fs.readFileSync(f.filename), before);
  }
  assert.equal(f.calls.length, 0);
});

test('unpublished recovery requires both recorded candidate and fetched descendant base, clean exact feature ownership', async t => {
  for (const settings of [{includeBase: false}, {includePrevious: false}]) {
    const f = unpublishedBaseRefreshFixture(t, settings), before = fs.readFileSync(f.filename);
    await assert.rejects(runDelivery({projectRoot: f.projectRoot, taskId: 'task', action: 'prepare'}, f.safe), {code: 'BASE_REFRESH_ANCESTRY_INVALID'});
    assert.deepEqual(fs.readFileSync(f.filename), before);
  }
  const f = unpublishedBaseRefreshFixture(t), before = fs.readFileSync(f.filename);
  fs.writeFileSync(path.join(f.receipt.featureWorktree, 'dirty.txt'), 'preserve');
  await assert.rejects(runDelivery({projectRoot: f.projectRoot, taskId: 'task', action: 'prepare'}, f.safe), {code: 'FEATURE_REPAIR_UNVERIFIED'});
  assert.deepEqual(fs.readFileSync(f.filename), before);
  fs.unlinkSync(path.join(f.receipt.featureWorktree, 'dirty.txt'));
  git(f.receipt.featureWorktree, ['switch', '-c', 'codex/other-feature']);
  await assert.rejects(runDelivery({projectRoot: f.projectRoot, taskId: 'task', action: 'prepare'}, f.safe), {code: 'TASK_OWNERSHIP_MISMATCH'});
  assert.deepEqual(fs.readFileSync(f.filename), before);
});

test('unpublished recovery rejects concurrent record, candidate, feature and remote changes without overwriting them', async t => {
  for (const kind of ['record', 'candidate', 'feature', 'remote', 'remote-ref', 'remote-url']) {
    const f = unpublishedBaseRefreshFixture(t), before = fs.readFileSync(f.filename);
    let reads = 0;
    f.onRead(() => {
      if (++reads !== 2) return;
      if (kind === 'record') fs.writeFileSync(f.filename, JSON.stringify({...f.receipt, repairAttempts: 3}));
      if (kind === 'remote') f.setRemoteBase('1'.repeat(40));
      if (kind === 'remote-ref') git(f.projectRoot, ['update-ref', 'refs/remotes/origin/master', f.receipt.baseCommit]);
      if (kind === 'remote-url') git(f.projectRoot, ['remote', 'set-url', 'origin', 'https://github.com/fixture/other.git']);
      if (kind === 'candidate' || kind === 'feature') {
        const directory = kind === 'candidate' ? f.receipt.integrationWorktree : f.receipt.featureWorktree;
        fs.writeFileSync(path.join(directory, 'concurrent.txt'), 'preserve concurrent');
        git(directory, ['add', '.']); git(directory, ['commit', '-m', 'concurrent advance']);
      }
    });
    await assert.rejects(runDelivery({projectRoot: f.projectRoot, taskId: 'task', action: 'prepare'}, f.safe));
    if (kind === 'record') assert.equal(JSON.parse(fs.readFileSync(f.filename)).repairAttempts, 3);
    else assert.deepEqual(fs.readFileSync(f.filename), before);
    assert.ok(fs.existsSync(f.receipt.featureWorktree)); assert.ok(fs.existsSync(f.receipt.integrationWorktree));
  }
});

test('unpublished recovery supports repeated new master advances before any publication and preserves an existing task lock', async t => {
  const f = unpublishedBaseRefreshFixture(t);
  const first = await runDelivery({projectRoot: f.projectRoot, taskId: 'task', action: 'prepare'}, f.safe);
  fs.writeFileSync(path.join(f.projectRoot, 'later-master.txt'), 'later\n');
  git(f.projectRoot, ['add', '.']); git(f.projectRoot, ['commit', '-m', 'master advances again']);
  const latest = git(f.projectRoot, ['rev-parse', 'HEAD']);
  git(f.projectRoot, ['update-ref', 'refs/remotes/origin/master', latest]);
  git(f.receipt.integrationWorktree, ['merge', '--no-ff', '--no-edit', latest]);
  fs.writeFileSync(f.filename, JSON.stringify({...first, status: 'remote_moved'})); f.setRemoteBase(latest);
  const lock = path.join(f.projectRoot, '.git/leon-engineering/locks/integration.lock'); fs.writeFileSync(lock, '99999999');
  const before = fs.readFileSync(f.filename);
  await assert.rejects(runDelivery({projectRoot: f.projectRoot, taskId: 'task', action: 'prepare'}, f.safe), {code: 'TASK_LOCKED'});
  assert.equal(fs.readFileSync(lock, 'utf8'), '99999999'); assert.deepEqual(fs.readFileSync(f.filename), before); fs.unlinkSync(lock);
  const second = await runDelivery({projectRoot: f.projectRoot, taskId: 'task', action: 'prepare'}, f.safe);
  assert.equal(second.baseCommit, latest); assert.equal(second.mode, null); assert.equal(second.remoteCommit, null); assert.equal(second.pullRequest, null);
  assert.equal(fs.readdirSync(path.join(f.projectRoot, '.git/leon-engineering/git-safety/base-refresh/task')).length, 2);
  assert.ok(f.calls.every(args => args[0] === 'api'));
});

test('unpublished recovery rechecks a last-moment remote advance after its private snapshot', async t => {
  const f = unpublishedBaseRefreshFixture(t), before = fs.readFileSync(f.filename);
  let reads = 0; f.onRead(() => { if (++reads === 3) f.setRemoteBase('1'.repeat(40)); });
  await assert.rejects(runDelivery({projectRoot: f.projectRoot, taskId: 'task', action: 'prepare'}, f.safe), {code: 'REMOTE_BASE_CHANGED'});
  assert.deepEqual(fs.readFileSync(f.filename), before);
  const snapshots = path.join(f.projectRoot, '.git/leon-engineering/git-safety/base-refresh/task');
  assert.deepEqual(JSON.parse(fs.readFileSync(path.join(snapshots, fs.readdirSync(snapshots)[0]))), f.receipt);
  assert.ok(fs.existsSync(f.receipt.integrationWorktree));
});

function treeBytes(root) {
  if (!fs.existsSync(root)) return 0;
  return fs.readdirSync(root, {withFileTypes:true}).reduce((n,e) => n + (e.isDirectory() ? treeBytes(path.join(root,e.name)) : fs.lstatSync(path.join(root,e.name)).size),0);
}
function v2Fixture(t) {
  const f=fixture(t);f.options.backupVersion=2;f.options.processProbe=()=>false;
  // Match RWB's ignored operational logs; logging must not alter the captured working copy.
  fs.appendFileSync(path.join(f.projectRoot,'.git/info/exclude'),'\nlogs/\n');
  return f;
}

test('v2 reuses unchanged independent recovery point and stores content only once', t => {
  const {projectRoot,options}=v2Fixture(t);
  fs.writeFileSync(path.join(projectRoot,'untracked.txt'),'private work\n');
  fs.chmodSync(path.join(projectRoot,'tracked.txt'),0o600);
  const first=backupRepository({projectRoot},options);
  const size=treeBytes(options.backupRoot);
  for(let i=0;i<4;i++) {
    const next=backupRepository({projectRoot},options);
    assert.equal(next.directory,first.directory);
    assert.equal(next.reused,true);
  }
  assert.equal(treeBytes(options.backupRoot),size);
  const manifest=JSON.parse(fs.readFileSync(path.join(first.directory,'manifest.json')));
  assert.equal(manifest.schemaVersion,2);
  assert.equal(fs.existsSync(path.join(first.directory,'objects.pack')),false);
  assert.equal(fs.existsSync(path.join(first.directory,'commits.bundle')),false);
  fs.renameSync(projectRoot,projectRoot+'-offline');
  assert.equal(verifyBackupDirectory(first.directory,options).restoreVerified,true);
});

test('v2 preserves binary index/worktree, non-Git permissions, missing and symlink records', t => {
  const {projectRoot,options}=v2Fixture(t);
  fs.writeFileSync(path.join(projectRoot,'tracked.txt'),Buffer.from([0,1,2]));
  git(projectRoot,['add','tracked.txt']);
  fs.writeFileSync(path.join(projectRoot,'tracked.txt'),Buffer.from([0,1,3]));
  fs.chmodSync(path.join(projectRoot,'tracked.txt'),0o400);
  fs.symlinkSync('tracked.txt',path.join(projectRoot,'new-link'));
  fs.unlinkSync(path.join(projectRoot,'package.json'));
  const point=backupRepository({projectRoot},options);
  assert.equal(verifyBackupDirectory(point.directory,options).restoreVerified,true);
});

test('v1 migration previews without writes, preserves point path, verifies v2 and resumes', t => {
  const {projectRoot,options}=fixture(t);
  const old=backupRepository({projectRoot},options);
  const journal=JSON.parse(fs.readFileSync(path.join(old.directory,'manifest.json'))).files.find(item=>item.path==='logs/git-safety.jsonl');
  assert.ok(journal);
  const before=treeBytes(options.backupRoot);
  const preview=maintainBackups({projectRoot,action:'backup-migrate'},options);
  assert.equal(preview.status,'preview');
  assert.equal(treeBytes(options.backupRoot),before);
  const migrated=maintainBackups({projectRoot,action:'backup-migrate',apply:true},options);
  assert.equal(migrated.items.find(x=>x.id===path.basename(old.directory)).status,'migrated');
  assert.equal(JSON.parse(fs.readFileSync(path.join(old.directory,'manifest.json'))).schemaVersion,2);
  assert.equal(JSON.parse(fs.readFileSync(path.join(old.directory,'manifest.json'))).files.find(item=>item.path===journal.path)?.sha256,journal.sha256);
  const sharedJournal=path.join(options.backupRoot,'.v2-store/files',journal.sha256.slice(0,2),journal.sha256.slice(2));
  assert.equal(crypto.createHash('sha256').update(fs.readFileSync(sharedJournal)).digest('hex'),journal.sha256);
  assert.equal(verifyBackupDirectory(old.directory,options).restoreVerified,true);
  assert.equal(fs.existsSync(path.join(old.directory,'objects.pack')),false);
  assert.doesNotThrow(()=>maintainBackups({projectRoot,action:'backup-migrate',apply:true},options));
});

test('rotation retains seven days and latest two points and does not mutate the live Git objects', t => {
  const {projectRoot,options}=v2Fixture(t); const points=[];
  const day=86400000, now=Date.now();
  for(let i=0;i<4;i++) {
    fs.writeFileSync(path.join(projectRoot,'tracked.txt'),'version '+i+'\n');
    git(projectRoot,['add','.']);git(projectRoot,['commit','-m','change '+i]);
    points.push(backupRepository({projectRoot},{...options,now:now-(10-i)*day}));
  }
  const before=fs.readFileSync(path.join(projectRoot,'.git/config'));
  const result=maintainBackups({projectRoot,action:'backup-prune',apply:true},{...options,now});
  assert.equal(result.items.filter(x=>x.status==='expired').length,2);
  assert.equal(fs.existsSync(points[0].directory),false);
  assert.equal(fs.existsSync(points[1].directory),false);
  for(const p of points.slice(2))assert.equal(verifyBackupDirectory(p.directory,options).restoreVerified,true);
  assert.deepEqual(fs.readFileSync(path.join(projectRoot,'.git/config')),before);
  assert.doesNotThrow(()=>git(projectRoot,['fsck','--full']));
});

test('rotation protects dirty, unmerged and explicitly held recovery points', t => {
  const {projectRoot,options}=v2Fixture(t);const now=Date.now();const old=now-20*86400000;
  git(projectRoot,['checkout','-b','codex/unmerged']);
  fs.writeFileSync(path.join(projectRoot,'tracked.txt'),'not on master');git(projectRoot,['add','.']);git(projectRoot,['commit','-m','unmerged']);
  const p=backupRepository({projectRoot},{...options,now:old});
  git(projectRoot,['checkout','master']);
  const held=backupRepository({projectRoot},{...options,now:old,backupProtection:'object-repair'});
  fs.writeFileSync(path.join(projectRoot,'dirty.txt'),'unsaved');
  const dirty=backupRepository({projectRoot},{...options,now:old});
  const result=maintainBackups({projectRoot,action:'backup-prune',apply:true},{...options,now});
  for(const x of [p,held,dirty])assert.equal(fs.existsSync(x.directory),true);
  assert.ok(result.items.some(x=>x.reason==='unmerged'));
  assert.ok(result.items.some(x=>x.reason==='protected'));
});

test('corruption and lock conflicts fail closed without deleting originals', t => {
  const {projectRoot,options}=v2Fixture(t);
  const p=backupRepository({projectRoot},options);
  const root=path.join(options.backupRoot,'.v2-store');
  fs.mkdirSync(path.join(options.backupRoot,'.backup.lock'));
  assert.throws(()=>backupRepository({projectRoot},options),{code:'BACKUP_STORE_LOCKED'});
  fs.rmdirSync(path.join(options.backupRoot,'.backup.lock'));
  const manifest=JSON.parse(fs.readFileSync(path.join(p.directory,'manifest.json')));
  const blob=manifest.files[0].sha256;
  fs.writeFileSync(path.join(root,'files',blob.slice(0,2),blob.slice(2)),'corrupt');
  assert.throws(()=>verifyBackupDirectory(p.directory,options));
  assert.throws(()=>maintainBackups({projectRoot,action:'backup-prune',apply:true},{...options,now:Date.now()+20*86400000}));
  assert.equal(fs.existsSync(p.directory),true);
});

test('backup CLI maintenance defaults to preview and apply is restricted to maintenance', () => {
  assert.equal(parseCli(['backup-prune','--project','/repo']).options.apply,undefined);
  assert.equal(parseCli(['backup-migrate','--project','/repo','--apply']).options.apply,true);
  assert.throws(()=>parseCli(['backup','--project','/repo','--apply']),{code:'CLI_OPTION_INVALID'});
});

test('migration resumes after a persisted pending commit with a different retry clock', t => {
  const {projectRoot,options}=fixture(t);const point=backupRepository({projectRoot},options);
  assert.throws(()=>maintainBackups({projectRoot,action:'backup-migrate',apply:true},{...options,afterMigrationPending:()=>{throw new Error('simulated interruption');}}));
  assert.equal(fs.existsSync(path.join(point.directory,'objects.pack')),true);
  assert.equal(fs.existsSync(path.join(point.directory,'manifest-v2.pending.json')),true);
  assert.doesNotThrow(()=>maintainBackups({projectRoot,action:'backup-migrate',apply:true},{...options,now:Date.now()+1000}));
  assert.equal(verifyBackupDirectory(point.directory,options).restoreVerified,true);
});

test('v2 certificate detects edited retention metadata without deleting any recovery point', t => {
  const {projectRoot,options}=v2Fixture(t);const p=backupRepository({projectRoot},options);
  const file=path.join(p.directory,'manifest.json');const original=fs.readFileSync(file);
  for(const edit of [m=>m.worktrees=[],m=>m.protection='ordinary-other',m=>m.createdAt='2000-01-01T00:00:00Z']) {
    const m=JSON.parse(original);edit(m);fs.writeFileSync(file,JSON.stringify(m));
    assert.throws(()=>verifyBackupDirectory(p.directory,options),{code:'BACKUP_METADATA_MISMATCH'});
    assert.throws(()=>maintainBackups({projectRoot,action:'backup-prune',apply:true},options));
    assert.equal(fs.existsSync(p.directory),true);fs.writeFileSync(file,original);
  }
});

test('v2 returns verified preservation proof on new and reused snapshots', t => {
  const {projectRoot,options}=v2Fixture(t);const tree=git(projectRoot,['rev-parse','HEAD^{tree}']);
  const preservationRefs={'refs/codex/turn-diffs/proof':tree};
  for(let i=0;i<2;i++)assert.deepEqual(backupRepository({projectRoot},{...options,preservationRefs}).verifiedPreservationRefs,preservationRefs);
});

test('rotation protects deleted unmerged refs not belonging to the selected worktree', t => {
  const {projectRoot,options}=v2Fixture(t);const now=Date.now();
  git(projectRoot,['switch','-c','codex/orphan']);fs.writeFileSync(path.join(projectRoot,'orphan.txt'),'only old point');git(projectRoot,['add','.']);git(projectRoot,['commit','-m','orphan']);
  git(projectRoot,['switch','master']);const old=backupRepository({projectRoot},{...options,now:now-20*86400000});
  git(projectRoot,['branch','-D','codex/orphan']);
  for(let i=0;i<2;i++){fs.writeFileSync(path.join(projectRoot,'tracked.txt'),'new '+i);git(projectRoot,['add','.']);git(projectRoot,['commit','-m','new '+i]);backupRepository({projectRoot},options);}
  const result=maintainBackups({projectRoot,action:'backup-prune',apply:true},{...options,now});
  assert.equal(result.items.find(x=>x.id===path.basename(old.directory)).reason,'unmerged_or_unique_anchor');
  assert.equal(fs.existsSync(old.directory),true);
});

test('pending migration prevents rotation from collecting its shared payloads', t => {
  const {projectRoot,options}=fixture(t);const p=backupRepository({projectRoot},options);
  assert.throws(()=>maintainBackups({projectRoot,action:'backup-migrate',apply:true},{...options,afterMigrationPending:()=>{throw new Error('interrupted');}}));
  const bytes=treeBytes(path.join(options.backupRoot,'.v2-store'));
  assert.throws(()=>maintainBackups({projectRoot,action:'backup-prune',apply:true},options),{code:'BACKUP_MIGRATION_PENDING'});
  assert.equal(treeBytes(path.join(options.backupRoot,'.v2-store')),bytes);
  assert.equal(fs.existsSync(path.join(p.directory,'objects.pack')),true);
  assert.doesNotThrow(()=>maintainBackups({projectRoot,action:'backup-migrate',apply:true},options));
});

test('earliest v1 points remain readable and protected when the index proof was never recorded', t => {
  const {projectRoot,options}=fixture(t);const p=backupRepository({projectRoot},options);
  const file=path.join(p.directory,'manifest.json'),m=JSON.parse(fs.readFileSync(file));
  delete m.metadataSemantics;delete m.preservationRefs;for(const w of m.worktrees)delete w.index;
  fs.writeFileSync(file,JSON.stringify(m));
  assert.equal(verifyBackupDirectory(p.directory,options).restoreVerified,true);
  const result=maintainBackups({projectRoot,action:'backup-migrate',apply:true},options);
  assert.equal(result.items[0].reason,'legacy_index_unrecorded');
  assert.equal(fs.existsSync(path.join(p.directory,'objects.pack')),true);
});

test('metadata partial-write failure keeps the original and resumes without a truncated seal', t => {
  const {projectRoot,options}=fixture(t);const p=backupRepository({projectRoot},options);
  const write=fs.writeFileSync;
  fs.writeFileSync=function(target,value,...rest) {
    if(typeof target==='number' && typeof value==='string' && value.startsWith('{"manifestSha256"')) {
      write.call(fs,target,value.slice(0,5),...rest);throw new Error('simulated metadata I/O failure');
    }
    return write.call(fs,target,value,...rest);
  };
  try{assert.throws(()=>maintainBackups({projectRoot,action:'backup-migrate',apply:true},options));}finally{fs.writeFileSync=write;}
  assert.equal(fs.existsSync(path.join(p.directory,'objects.pack')),true);
  assert.equal(fs.existsSync(path.join(p.directory,'seal.json')),false);
  assert.doesNotThrow(()=>maintainBackups({projectRoot,action:'backup-migrate',apply:true},options));
  assert.equal(verifyBackupDirectory(p.directory,options).restoreVerified,true);
});

test('failed v1 diagnostic remains protected while independent expired v2 points can be collected', t => {
  const {projectRoot,options}=v2Fixture(t);const now=Date.now();
  for(let i=0;i<3;i++) {
    fs.writeFileSync(path.join(projectRoot,'tracked.txt'),'version '+i);git(projectRoot,['add','.']);git(projectRoot,['commit','-m','version '+i]);
    backupRepository({projectRoot},{...options,now:now-(20-i)*86400000});
  }
  const failed=path.join(options.backupRoot,crypto.randomUUID());fs.mkdirSync(failed,{mode:0o700});
  fs.writeFileSync(path.join(failed,'manifest-draft.json'),JSON.stringify({schemaVersion:1,restoreVerified:false}),{mode:0o600});
  fs.writeFileSync(path.join(failed,'failure-status.json'),JSON.stringify({status:'FAIL',restoreVerified:false}),{mode:0o600});
  const result=maintainBackups({projectRoot,action:'backup-prune',apply:true},{...options,now});
  assert.equal(result.collection.status,'complete');
  assert.equal(result.items.filter(x=>x.status==='expired').length,1);
  assert.equal(fs.existsSync(failed),true);
});

test('distinct v2 metadata points share identical payloads without growth or borrowing source objects', t => {
  const {projectRoot,options}=v2Fixture(t);const first=backupRepository({projectRoot},options);
  const store=path.join(options.backupRoot,'.v2-store'),bytes=treeBytes(store);
  fs.chmodSync(path.join(projectRoot,'tracked.txt'),0o600);
  const second=backupRepository({projectRoot},options);
  assert.notEqual(second.directory,first.directory);assert.equal(treeBytes(store),bytes);
  fs.renameSync(projectRoot,projectRoot+'-offline');
  for(const p of [first,second])assert.equal(verifyBackupDirectory(p.directory,options).restoreVerified,true);
});

test('v2 preserves an as-of old tree while unrelated Codex refs and worktrees move during export', t => {
  const {root,projectRoot,options}=v2Fixture(t),ref='refs/codex/turn-diffs/checkpoints/v2';
  const old=snapshotTree(projectRoot,'old tree only'),next=snapshotTree(projectRoot,'new tree only');
  git(projectRoot,['update-ref',ref,old.tree]);
  const marker=path.join(root,'mutated'),other=path.join(root,'other'),wrapper=path.join(root,'snapshot-v2-git');
  fs.writeFileSync(wrapper,`#!${process.execPath}\nconst fs=require('node:fs');const {spawnSync}=require('node:child_process');const a=process.argv.slice(2);const r=spawnSync('/usr/bin/git',a,{stdio:'inherit'});if(r.status===0&&a.includes('pack-objects')&&!fs.existsSync(${JSON.stringify(marker)})){fs.writeFileSync(${JSON.stringify(marker)},'done');for(const args of [['update-ref',${JSON.stringify(ref)},${JSON.stringify(next.tree)}],['worktree','add','-b','codex/other',${JSON.stringify(other)}]])if(spawnSync('/usr/bin/git',['-C',${JSON.stringify(projectRoot)},...args],{stdio:'ignore'}).status!==0)process.exit(79);}process.exit(r.status??1);\n`,{mode:0o700});
  const p=backupRepository({projectRoot},{...options,gitPath:wrapper,preservationRefs:{[ref]:old.tree}});
  const m=JSON.parse(fs.readFileSync(path.join(p.directory,'manifest.json')));
  assert.equal(m.refs[ref],old.tree);assert.equal(git(projectRoot,['rev-parse',ref]),next.tree);
  assert.equal(p.verifiedPreservationRefs[ref],old.tree);
  assert.equal(verifyBackupDirectory(p.directory,options).restoreVerified,true);
});

test('v1 migration also preserves objects and refs present only in its concurrent full bundle', t => {
  const {projectRoot,options}=fixture(t);const p=backupRepository({projectRoot},options);
  const tree=git(projectRoot,['rev-parse','HEAD^{tree}']);
  const result=spawnSync(gitPath,['-C',projectRoot,'commit-tree',tree,'-p','HEAD'],{input:'bundle-only recovery commit\n',encoding:'utf8'});
  assert.equal(result.status,0);const oid=result.stdout.trim();
  git(projectRoot,['update-ref','refs/heads/bundle-only',oid]);
  const bundle=path.join(p.directory,'commits.bundle');fs.unlinkSync(bundle);
  git(projectRoot,['bundle','create',bundle,'--all']);fs.chmodSync(bundle,0o600);
  const file=path.join(p.directory,'manifest.json'),m=JSON.parse(fs.readFileSync(file));
  m.files.find(x=>x.path==='commits.bundle').sha256=crypto.createHash('sha256').update(fs.readFileSync(bundle)).digest('hex');fs.writeFileSync(file,JSON.stringify(m));
  git(projectRoot,['update-ref','-d','refs/heads/bundle-only']);
  fs.unlinkSync(path.join(projectRoot,'.git/objects',oid.slice(0,2),oid.slice(2)));
  assert.doesNotThrow(()=>maintainBackups({projectRoot,action:'backup-migrate',apply:true},options));
  const migrated=JSON.parse(fs.readFileSync(file));assert.equal(migrated.additionalBundleRefs['refs/heads/bundle-only'],oid);
  assert.equal(verifyBackupDirectory(p.directory,options).restoreVerified,true);
});
