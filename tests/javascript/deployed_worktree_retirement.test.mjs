import assert from 'node:assert/strict';
import crypto from 'node:crypto';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
import test from 'node:test';
import {parseCli, retireDeployedWorktrees} from '../../scripts/git_safety.mjs';
import {nativeRetirementAcceptance, withNativeRetirementAdmission} from '../../scripts/native_retirement_acceptance.mjs';

function temp(t) {
  const directory = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), 'rwb-retirement-')));
  t.after(() => fs.rmSync(directory, {recursive: true, force: true}));
  return directory;
}

function json(filename, value) {
  fs.mkdirSync(path.dirname(filename), {recursive: true, mode: 0o700});
  fs.writeFileSync(filename, JSON.stringify(value), {mode: 0o600});
}

function git(directory, ...args) {
  const result = spawnSync('/usr/bin/git', ['-C', directory, ...args], {encoding: 'utf8'});
  assert.equal(result.status, 0, result.stderr);
  return result.stdout.trim();
}

test('Native retirement requires matching persisted acceptance, live revision and intact rollback', t => {
  const directory = temp(t);
  const root = path.join(directory, 'resident');
  const project = path.join(directory, 'project');
  fs.mkdirSync(project);
  const commonDirectory = path.join(project, '.git');
  const target = 'a'.repeat(40);
  const previous = 'b'.repeat(40);
  const {dev, ino} = fs.statSync(project);
  json(path.join(root, 'config.json'), {schema_version: 1, repository: 'Leon-Huang001208/ResearchWorkbench',
    source_common: commonDirectory, project, project_identity: [dev, ino], web_port: 8088});
  json(path.join(root, 'state.json'), {status: 'ready', deployed: target});
  json(path.join(directory, 'install/manifest.json'), {code_commit: target, status: 'installed'});
  json(path.join(directory, 'run/web.json'), {pid: 123, project_root: project, role: 'web', port: 8088});
  const wheel = (name, source) => {
    const filename = path.join(root, 'artifacts', name, 'payload');
    json(filename, {name});
    const sha256 = crypto.createHash('sha256').update(fs.readFileSync(filename)).digest('hex');
    json(path.join(path.dirname(filename), 'binding.json'), {source, sha256});
    return {path: filename, sha256};
  };
  const oldWheel = wheel('old', previous);
  json(path.join(root, 'accepted.json'), {target, previous, old_wheel: oldWheel, new_wheel: wheel('new', target),
    proof: {sha: target, head: target, pull_request: 10,
      ci: ['project-constraints.yml', 'research-web-checks.yml', 'research-web-bootstrap.yml'].map(
        (workflow, index) => ({workflow, run: index + 1, checkout: target}))}});
  const check = (revision = target) => nativeRetirementAcceptance({root, commonDirectory},
    {installedHead: () => target, live: () => ({enabled: true, maintenance: false, revision}), listener: () => true});
  assert.equal(check().target, target);
  assert.throws(() => check(previous), {code: 'DEPLOYMENT_LIVE_UNVERIFIED'});
  const journal = path.join(root, 'transaction.json');
  json(journal, {});
  assert.throws(() => check(), {code: 'DEPLOYMENT_IN_PROGRESS'});
  fs.unlinkSync(journal);
  fs.appendFileSync(oldWheel.path, 'drift');
  assert.throws(() => check(), {code: 'DEPLOYMENT_ROLLBACK_UNVERIFIED'});
});

test('retirement shares Native admission with research and excludes a deployment writer', {
  skip: process.platform !== 'darwin' || !fs.existsSync('/opt/homebrew/bin/python3.12'),
}, async t => {
  const root = temp(t);
  const lock = path.join(root, 'admission.lock');
  fs.writeFileSync(lock, '', {mode: 0o600});
  const probe = mode => spawnSync('/opt/homebrew/bin/python3.12', ['-I', '-S', '-c',
    'import fcntl, os, sys; fd=os.open(sys.argv[1], os.O_RDWR); fcntl.flock(fd, int(sys.argv[2]) | fcntl.LOCK_NB)',
    lock, String(mode)]).status;
  await withNativeRetirementAdmission(root, assertHeld => {
    assertHeld();
    assert.equal(probe(1), 0);
    assert.notEqual(probe(2), 0);
  });
  assert.equal(probe(2), 0);
});

function fixture(t) {
  const root = temp(t);
  const projectRoot = path.join(root, 'source');
  fs.mkdirSync(projectRoot);
  git(projectRoot, 'init', '-b', 'master');
  git(projectRoot, 'config', 'user.name', 'fixture');
  git(projectRoot, 'config', 'user.email', 'fixture@example.invalid');
  fs.writeFileSync(path.join(projectRoot, 'source.txt'), 'source\n');
  fs.writeFileSync(path.join(projectRoot, '.gitignore'), 'local.cache\n');
  git(projectRoot, 'add', '.');
  git(projectRoot, 'commit', '-m', 'source');
  const oid = git(projectRoot, 'rev-parse', 'HEAD');
  const remoteUrl = 'https://github.com/fixture/repo.git';
  git(projectRoot, 'remote', 'add', 'origin', remoteUrl);
  git(projectRoot, 'update-ref', 'refs/remotes/origin/master', oid);
  const taskId = 'sample';
  const featureBranch = 'codex/sample-feature';
  const integrationBranch = 'codex/integrate-sample';
  const featureWorktree = path.join(root, 'feature');
  const integrationWorktree = path.join(root, 'integration');
  git(projectRoot, 'worktree', 'add', '-b', featureBranch, featureWorktree);
  git(projectRoot, 'worktree', 'add', '-b', integrationBranch, integrationWorktree);
  json(path.join(projectRoot, '.agents/resource-closeout.json'), {});
  json(path.join(projectRoot, '.agents/deployed-worktree-retirement.json'), {schemaVersion: 1});
  const state = path.join(projectRoot, '.git/leon-engineering');
  const release = {target: oid, previous: 'b'.repeat(40), project: projectRoot,
    receiptSha256: 'c'.repeat(64), rollback: {sha256: 'd'.repeat(64)}};
  const deliveryFile = path.join(state, 'deliveries/sample.json');
  json(deliveryFile, {taskId, projectRoot, repositoryRoot: projectRoot, remoteUrl,
    status: 'ci_passed', mode: 'pr', ci: {status: 'passed'}, verification: {status: 'passed'},
    integrationBranch, integrationWorktree, integrationCommit: oid, featureBranch, featureWorktree,
    featureCommit: oid, pullRequest: {url: 'https://github.com/fixture/repo/pull/1'}});
  json(path.join(state, 'git-safety/reviews/sample.json'), {status: 'PASS', candidateCommit: oid,
    reviewedCommit: oid, attestedAt: new Date().toISOString()});
  const receiptDir = path.join(state, 'resource-closeout/sample');
  json(path.join(receiptDir, 'resources.json'), {taskId,
    roots: Object.fromEntries([featureWorktree, integrationWorktree].map(root => {
      const {dev, ino} = fs.statSync(root);
      return [root, [dev, ino]];
    }))});
  const options = {identityRoot: projectRoot, gitPath: '/usr/bin/git', processProbe: () => false,
    retirementUseProbe: () => false, retirementAcceptance: () => release,
    retirementAdmission: (_root, run) => run(() => {}),
    githubRunner: () => ({status: 0, stdout: Buffer.from(JSON.stringify({
      state: 'MERGED', baseRefName: 'master', headRefOid: oid, mergeCommit: {oid}}))})};
  return {run: (apply, overrides = {}) => retireDeployedWorktrees({projectRoot, taskId, residentRoot: root, apply},
    {...options, ...overrides}), oid, featureWorktree, integrationWorktree, featureBranch, integrationBranch,
    projectRoot, release, deliveryFile, proof: path.join(receiptDir, 'deployed-worktree-retirement.json')};
}

test('preview cannot authorize an ignored file or occupied tree', async t => {
  const f = fixture(t);
  assert.equal((await f.run(false)).items[0].status, 'candidate');
  assert.equal(fs.existsSync(f.proof), false);
  const state = await f.run(true, {retirementUseProbe: () => true});
  assert.equal(state.items[0].code, 'WORKTREE_OCCUPIED');
  fs.writeFileSync(path.join(f.featureWorktree, 'local.cache'), 'unique\n');
  assert.equal((await f.run(false)).items[0].code, 'WORKTREE_IGNORED_DATA');
  assert.equal(fs.existsSync(f.integrationWorktree), true);
  assert.equal(fs.existsSync(f.proof), false);
});

test('real Git proof permits both registered worktrees to retire and keeps branch objects', async t => {
  const f = fixture(t);
  assert.equal((await f.run(true)).items[0].status, 'retired');
  assert.equal(fs.existsSync(f.featureWorktree), false);
  assert.equal(fs.existsSync(f.integrationWorktree), false);
  const proof = JSON.parse(fs.readFileSync(f.proof));
  assert.equal(proof.status, 'complete');
  assert.equal(proof.targets.length, 2);
  assert.ok(proof.targets.every(row => row.proof.trackedFiles === 2));
  assert.equal(git(f.projectRoot, 'rev-parse', f.featureBranch), f.oid);
  assert.equal(git(f.projectRoot, 'rev-parse', f.integrationBranch), f.oid);
  assert.deepEqual((await f.run(true)).items, []);
});

test('a partial worktree retirement can finish after a newer accepted descendant', async t => {
  const f = fixture(t);
  const first = await f.run(true, {retirementUseProbe: root =>
    root === f.integrationWorktree && !fs.existsSync(f.featureWorktree)});
  assert.equal(first.items[0].code, 'WORKTREE_OCCUPIED');
  assert.equal(fs.existsSync(f.featureWorktree), false);
  assert.equal(fs.existsSync(f.integrationWorktree), true);
  const pending = JSON.parse(fs.readFileSync(f.proof));
  assert.equal(pending.status, 'pending');
  const refreshed = JSON.parse(fs.readFileSync(f.deliveryFile));
  refreshed.updatedAt = new Date().toISOString();
  refreshed.ci.checkedAt = refreshed.updatedAt;
  json(f.deliveryFile, refreshed);
  git(f.projectRoot, 'commit', '--allow-empty', '-m', 'successor deployment');
  const target = git(f.projectRoot, 'rev-parse', 'HEAD');
  git(f.projectRoot, 'update-ref', 'refs/remotes/origin/master', target);
  const later = await f.run(true, {retirementAcceptance: () => ({...f.release, target, receiptSha256: 'e'.repeat(64)})});
  assert.equal(later.items[0].status, 'retired');
  assert.equal(fs.existsSync(f.integrationWorktree), false);
  const final = JSON.parse(fs.readFileSync(f.proof));
  assert.deepEqual(final.deployment, pending.deployment);
  assert.equal(final.completedAtDeployment, target);
});

test('retirement CLI does not take self-certified acceptance or Git SHA flags', () => {
  assert.throws(() => parseCli(['worktree-retirement', '--project', '/source', '--task-id', 'sample',
    '--resident-root', '/resident', '--reviewed-commit', 'a'.repeat(40), '--apply']), {code: 'CLI_ARGUMENT_REQUIRED'});
});
