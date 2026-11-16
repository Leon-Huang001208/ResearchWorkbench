import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import crypto from 'node:crypto';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import {pathToFileURL} from 'node:url';

function git(cwd, ...args) {
  const result = spawnSync('/usr/bin/git', ['-C', cwd, ...args], {encoding: 'utf8'});
  assert.equal(result.status, 0, result.stderr);
  return result.stdout.trim();
}

async function fixture(t, {attributes} = {}) {
  const {proveDeployedWorktree} = await import('../../scripts/git_deployed_worktree_proof.mjs');
  const root = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), 'git-deployed-worktree-proof-')));
  t.after(() => fs.rmSync(root, {recursive: true, force: true}));
  const projectRoot = path.join(root, 'source');
  const worktree = path.join(root, 'deployed');
  const scratchRoot = path.join(root, 'scratch');
  fs.mkdirSync(projectRoot);
  fs.mkdirSync(scratchRoot, {mode: 0o700});
  git(projectRoot, 'init', '-b', 'master');
  git(projectRoot, 'config', 'user.name', 'Proof Fixture');
  git(projectRoot, 'config', 'user.email', 'fixture@example.invalid');
  fs.mkdirSync(path.join(projectRoot, 'nested'));
  fs.writeFileSync(path.join(projectRoot, 'nested', 'executable'), '#!/bin/sh\nexit 0\n', {mode: 0o755});
  fs.writeFileSync(path.join(projectRoot, 'source.txt'), 'recoverable source\n');
  if (attributes) fs.writeFileSync(path.join(projectRoot, '.gitattributes'), attributes);
  fs.writeFileSync(path.join(projectRoot, '.gitignore'), 'ignored.cache\n');
  fs.symlinkSync('../source.txt', path.join(projectRoot, 'nested', 'symbolic'));
  git(projectRoot, 'add', '.');
  git(projectRoot, 'commit', '-m', 'deployed');
  git(projectRoot, 'worktree', 'add', '-b', 'codex/fixture', worktree, 'master');
  const commit = git(worktree, 'rev-parse', 'HEAD');
  const source = path.join(worktree, 'source.txt');
  return {prove: (input = {}, options = {}) => proveDeployedWorktree({projectRoot, worktree, commit, deployedCommit: commit, ...input}, {scratchRoot, ...options}),
    projectRoot, worktree, scratchRoot, source, commit};
}

test('independent temporary Git restoration proves identical bytes, modes and symlink targets', async t => {
  const f = await fixture(t);
  const index = git(f.worktree, 'rev-parse', '--path-format=absolute', '--git-path', 'index');
  const before = fs.readFileSync(index);
  const first = f.prove();
  assert.equal(first.commit, f.commit);
  assert.equal(first.trackedFiles, 4);
  assert.match(first.indexSha256, /^[a-f0-9]{64}$/);
  assert.match(first.treeSha256, /^[a-f0-9]{64}$/);
  assert.match(first.adminSha256, /^[a-f0-9]{64}$/);
  assert.deepEqual(f.prove(), first);
  assert.deepEqual(fs.readFileSync(index), before);
  assert.deepEqual(fs.readdirSync(f.scratchRoot), []);
  assert.equal(fs.readlinkSync(path.join(f.worktree, 'nested', 'symbolic')), '../source.txt');
});

test('staged source, ignored data and untracked data cannot be treated as deployed Git content', async t => {
  for (const kind of ['staged', 'ignored', 'untracked']) {
    await t.test(kind, async it => {
      const f = await fixture(it);
      if (kind === 'staged') {
        fs.appendFileSync(f.source, 'not deployed\n');
        git(f.worktree, 'add', 'source.txt');
      } else fs.writeFileSync(path.join(f.worktree, kind === 'ignored' ? 'ignored.cache' : 'private.txt'), 'not Git backed\n');
      assert.throws(() => f.prove(), {code: 'DEPLOYED_WORKTREE_NOT_CLEAN'});
      assert.deepEqual(fs.readdirSync(f.scratchRoot), []);
    });
  }
});

test('skip-worktree, assume-unchanged and sparse checkout prevent a proof', async t => {
  for (const flag of ['skip-worktree', 'assume-unchanged', 'sparse']) {
    await t.test(flag, async it => {
      const f = await fixture(it);
      if (flag === 'sparse') git(f.worktree, 'sparse-checkout', 'set', 'nested');
      else git(f.worktree, 'update-index', `--${flag}`, 'source.txt');
      assert.throws(() => f.prove(), {code: 'DEPLOYED_WORKTREE_INDEX_UNVERIFIABLE'});
      assert.deepEqual(fs.readdirSync(f.scratchRoot), []);
    });
  }
});

test('physical metadata that Git cannot reproduce invalidates the proof', async t => {
  for (const kind of ['mode', 'empty directory', 'hardlink']) {
    await t.test(kind, async it => {
      const f = await fixture(it);
      if (kind === 'mode') fs.chmodSync(f.source, 0o600);
      if (kind === 'empty directory') fs.mkdirSync(path.join(f.worktree, 'only-local'));
      if (kind === 'hardlink') fs.linkSync(f.source, path.join(f.projectRoot, 'only-local-hardlink'));
      assert.throws(() => f.prove(), {code: 'DEPLOYED_WORKTREE_METADATA_UNVERIFIABLE'});
      assert.deepEqual(fs.readdirSync(f.scratchRoot), []);
    });
  }
});

test('macOS extended attributes and ACLs cannot be dropped merely because the Git index is clean', {
  skip: process.platform !== 'darwin',
}, async t => {
  for (const kind of ['xattr', 'ACL']) {
    await t.test(kind, async it => {
      const f = await fixture(it);
      const result = kind === 'xattr'
        ? spawnSync('/usr/bin/xattr', ['-w', 'com.example.worktree-proof', 'local metadata', f.source])
        : spawnSync('/bin/chmod', ['+a', 'everyone allow read', f.source]);
      assert.equal(result.status, 0, result.stderr.toString('utf8'));
      assert.equal(git(f.worktree, 'status', '--porcelain'), '');
      assert.throws(() => f.prove(), {code: 'DEPLOYED_WORKTREE_METADATA_UNVERIFIABLE'});
      assert.deepEqual(fs.readdirSync(f.scratchRoot), []);
    });
  }
});

test('a different target or Git object backend cannot silently substitute for the deployed commit', async t => {
  const f = await fixture(t);
  assert.throws(() => f.prove({commit: crypto.randomBytes(20).toString('hex')}), {code: 'DEPLOYED_WORKTREE_IDENTITY_MISMATCH'});
  fs.writeFileSync(path.join(f.projectRoot, '.git/objects/info/alternates'), path.join(f.projectRoot, 'invalid-object-store')+'\n');
  assert.throws(() => f.prove(), {code: 'DEPLOYED_WORKTREE_OBJECT_SOURCE_UNVERIFIABLE'});
  assert.deepEqual(fs.readdirSync(f.scratchRoot), []);
});

test('Git clean normalization does not certify different physical worktree bytes', async t => {
  const f = await fixture(t, {attributes: 'source.txt filter=proof\n'});
  git(f.projectRoot, 'config', 'filter.proof.clean', '/usr/bin/sed s/^LOCAL://');
  fs.writeFileSync(f.source, 'LOCAL:recoverable source\n');
  assert.equal(git(f.worktree, 'hash-object', '--path=source.txt', 'source.txt'),
    git(f.worktree, 'rev-parse', 'HEAD:source.txt'));
  assert.throws(() => f.prove(), {code: 'DEPLOYED_WORKTREE_NOT_CLEAN'});
  assert.deepEqual(fs.readdirSync(f.scratchRoot), []);
});

test('a killed restoration child does not leave its incomplete independent checkout behind', async t => {
  const f = await fixture(t);
  const killer = path.join(path.dirname(f.scratchRoot), 'test-killed-python');
  fs.writeFileSync(killer, '#!/bin/sh\nmkdir -p "$9/abandoned-restore/checkout"\nkill -KILL $$\n', {mode: 0o700});
  assert.throws(() => f.prove({}, {pythonPath: killer}), {code: 'DEPLOYED_WORKTREE_PROOF_FAILED'});
  assert.deepEqual(fs.readdirSync(f.scratchRoot), []);
  assert.equal(fs.readFileSync(f.source, 'utf8'), 'recoverable source\n');
});

test('the proof does not execute an interpreter supplied by the project’s private virtual environment', async t => {
  const f = await fixture(t);
  const venv = path.join(f.projectRoot, '.venv', 'bin');
  const marker = path.join(f.projectRoot, 'untrusted-interpreter-ran');
  fs.mkdirSync(venv, {recursive: true});
  fs.writeFileSync(path.join(venv, 'python'), '#!/bin/sh\n' + 'touch "$6/untrusted-interpreter-ran"\nexit 1\n', {mode: 0o700});
  assert.equal(f.prove().commit, f.commit);
  assert.equal(fs.existsSync(marker), false);
  assert.deepEqual(fs.readdirSync(f.scratchRoot), []);
});

test('Darwin metadata inspection loads the exact helper source instead of a same-name package', {
  skip: process.platform !== 'darwin',
}, async t => {
  const f = await fixture(t);
  const tool = path.join(path.dirname(f.scratchRoot), 'tool');
  const shadow = path.join(tool, 'backup_fd_clone');
  fs.mkdirSync(shadow, {recursive: true});
  for (const name of ['git_deployed_worktree_proof.mjs', 'backup_fd_clone.py']) {
    fs.copyFileSync(new URL(`../../scripts/${name}`, import.meta.url), path.join(tool, name));
  }
  fs.writeFileSync(path.join(shadow, '__init__.py'), 'raise RuntimeError("untrusted package loaded")\n');
  const {proveDeployedWorktree} = await import(pathToFileURL(path.join(tool, 'git_deployed_worktree_proof.mjs')).href);
  assert.equal(proveDeployedWorktree({projectRoot: f.projectRoot, worktree: f.worktree, commit: f.commit,
    deployedCommit: f.commit}, {scratchRoot: f.scratchRoot}).commit, f.commit);
});

test('a clean branch cannot retire the only linked HEAD reflog of an undeployed detached commit', async t => {
  const f = await fixture(t);
  git(f.worktree, 'checkout', '--detach', f.commit);
  git(f.worktree, 'commit', '--allow-empty', '-m', 'undeployed detached change');
  const detached = git(f.worktree, 'rev-parse', 'HEAD');
  assert.notEqual(detached, f.commit);
  git(f.worktree, 'checkout', 'codex/fixture');
  assert.equal(git(f.worktree, 'status', '--porcelain'), '');
  assert.throws(() => f.prove(), {code: 'DEPLOYED_WORKTREE_ADMIN_UNVERIFIABLE'});
  assert.ok(git(f.worktree, 'reflog', 'show', '--format=%H', 'HEAD').split('\n').includes(detached));
  assert.deepEqual(fs.readdirSync(f.scratchRoot), []);
});

test('newer Git empty linked refs scaffolding is safe and its identity is recorded', async t => {
  const f = await fixture(t);
  const admin = git(f.worktree, 'rev-parse', '--absolute-git-dir');
  const refs = path.join(admin, 'refs');
  fs.mkdirSync(refs, {recursive: true});
  const first = f.prove();
  assert.equal(first.commit, f.commit);
  assert.deepEqual(f.prove(), first);
  fs.rmdirSync(refs);
  assert.notEqual(f.prove().adminSha256, first.adminSha256);
  assert.deepEqual(fs.readdirSync(f.scratchRoot), []);
});

test('private refs and unclassified linked Git administrative state prevent worktree removal', async t => {
  for (const kind of ['private ref', 'unknown refs directory', 'symlinked refs', 'rebase state']) {
    await t.test(kind, async it => {
      const f = await fixture(it);
      const admin = git(f.worktree, 'rev-parse', '--absolute-git-dir');
      const refs = path.join(admin, 'refs');
      fs.mkdirSync(refs, {recursive: true});
      assert.equal(f.prove().commit, f.commit);
      if (kind === 'private ref') {
        git(f.worktree, 'update-ref', 'refs/worktree/private', f.commit);
        assert.ok(fs.existsSync(path.join(refs, 'worktree', 'private')));
      } else if (kind === 'unknown refs directory') {
        fs.mkdirSync(path.join(refs, 'unknown'));
      } else if (kind === 'symlinked refs') {
        fs.rmdirSync(refs);
        fs.symlinkSync(f.scratchRoot, refs);
      } else fs.writeFileSync(path.join(admin, 'REBASE_HEAD'), f.commit+'\n');
      assert.throws(() => f.prove(), {code: 'DEPLOYED_WORKTREE_ADMIN_UNVERIFIABLE'});
      assert.deepEqual(fs.readdirSync(f.scratchRoot), []);
    });
  }
});

test('a previous linked HEAD recorded in deployed history remains reproducible from the deployment anchor', async t => {
  const f = await fixture(t);
  git(f.projectRoot, 'commit', '--allow-empty', '-m', 'later live deployment');
  const deployedCommit = git(f.projectRoot, 'rev-parse', 'HEAD');
  git(f.worktree, 'checkout', '--detach', deployedCommit);
  git(f.worktree, 'checkout', 'codex/fixture');
  assert.equal(f.prove({deployedCommit}).commit, f.commit);
  assert.deepEqual(fs.readdirSync(f.scratchRoot), []);
});
