import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
import {runDelivery, parseCli} from '../../scripts/git_safety.mjs';

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
      if(server.commitError)return {status:1,stdout:`HTTP/2.0 ${server.commitError}\r\ncontent-type: application/json\r\n\r\n{"message":"Not Found"}`,stderr:''};
      return server.commitKnown?{status:0,stdout:`HTTP/2.0 200 OK\r\ncontent-type: application/json\r\n\r\n${JSON.stringify({sha})}`,stderr:''}:{status:1,stdout:'HTTP/2.0 404 Not Found\r\ncontent-type: application/json\r\n\r\n{"message":"Not Found"}',stderr:''};
    }
    if (endpoint==='repos/fixture/repo/git/ref/heads/master') value={object:{sha:server.base}};
    else if (endpoint.startsWith('repos/fixture/repo/git/matching-refs/heads/')) value=server.published?[{ref:'published'}]:[];
    else if (endpoint.startsWith('repos/fixture/repo/pulls?')) value=server.published?[{number:1}]:[];
    else if (endpoint.includes('/actions/runs?')) value={total_count:server.runs?1:0,workflow_runs:[]};
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
