import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import crypto from 'node:crypto';
import {spawnSync} from 'node:child_process';
import {backupRepository, checkRepository, configureRepository, selectGitPath, withRepositoryLock, validateCleanup, validateResourceCleanup, runDelivery, parseCli} from '../../scripts/git_safety.mjs';

const gitPath = '/usr/bin/git';
function git(root, args) {
  const result = spawnSync(gitPath, ['-C', root, ...args], {encoding: 'utf8'});
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
  return {root, projectRoot, options: {gitPath, platform: 'darwin', identityRoot: projectRoot, backupRoot: path.join(root, 'backups')}};
}

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
  assert.throws(() => checkRepository({projectRoot}, options), {code: 'OBJECT_INTEGRITY_FAILED'});
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
