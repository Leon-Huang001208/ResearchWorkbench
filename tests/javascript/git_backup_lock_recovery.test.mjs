import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import {spawnSync} from 'node:child_process';

import {readManifest, withBackupLock} from '../../scripts/git_backup_store.mjs';

const point = 'de487ec8-e8c1-4548-bf32-021aa62de844';
const verified = '00bcee59-9e45-442e-9d42-56766a70c6be';
const head = 'a'.repeat(40);

async function fixture(t, {createBackup} = {}) {
  const {recoverLegacyBackupLock} = await import('../../scripts/git_backup_lock_recovery.mjs');
  const base = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), 'backup-lock-recovery-')));
  t.after(() => fs.rmSync(base, {recursive: true, force: true}));
  const root = path.join(base, 'store');
  const lock = path.join(root, '.backup.lock');
  const partial = path.join(root, point);
  const source = path.join(base, 'repo');
  fs.mkdirSync(root, {mode: 0o700});
  fs.mkdirSync(source, {mode: 0o700});
  const backupDirectory = createBackup ? createBackup(source, root) : path.join(root, verified);
  const common = path.join(source, '.git');
  const receiptRoot = path.join(common, 'leon-engineering', 'deliveries');
  const evidenceRoot = path.join(common, 'amend-evidence');
  for (const dir of [root, lock, partial, backupDirectory, source, common, receiptRoot, evidenceRoot,
    path.join(partial, 'logs'), path.join(partial, 'worktrees')]) fs.mkdirSync(dir, {mode: 0o700, recursive: true});
  const lockBirth = Number(fs.statSync(lock, {bigint: true}).birthtimeNs / 1000000n);
  const pointBirth = Number(fs.statSync(partial, {bigint: true}).birthtimeNs / 1000000n);
  const eventTime = new Date(Math.max(Date.now(), pointBirth));
  const log = path.join(partial, 'logs', 'git-safety.jsonl');
  const pack = path.join(partial, 'objects.pack');
  const event = {time: eventTime.toISOString(), action: 'backup-snapshot', event: 'backup_capacity',
    status: 'PASS', phase: 'snapshot-stream', head, durationMs: eventTime.getTime() - lockBirth};
  fs.writeFileSync(pack, 'retain unverified bytes\n', {mode: 0o600});
  fs.writeFileSync(log, JSON.stringify(event)+'\n', {mode: 0o600});
  const logTime = new Date(eventTime.getTime() + 10);
  fs.utimesSync(log, logTime, logTime);
  const managedReceipt = path.join(receiptRoot, 'role-tags.json');
  fs.writeFileSync(managedReceipt, JSON.stringify({schemaVersion: 1, taskId: 'role-tags', repositoryRoot: source}), {mode: 0o600});
  const evidencePath = path.join(evidenceRoot, 'amend-interruption.json');
  const observed = Math.max(Date.now(), ...[partial, pack, log, path.join(partial, 'worktrees')].map(
    file => Number(fs.statSync(file, {bigint: true}).mtimeNs / 1000000n)));
  const evidence = {observedAt: new Date(observed).toISOString(), disposition: 'STOPPED_BY_SIGINT_DISK_PRESSURE',
    exitedProcessGroup: 38775, exitCode: 130, retainedExactCandidate: 'b'.repeat(40),
    managedCandidateBeforeAmend: 'c'.repeat(40), managedReceipt, partialBackup: partial,
    locksPreserved: true, cliExternalBackupOverrideSupported: false, remoteWrites: 0};
  fs.writeFileSync(evidencePath, JSON.stringify(evidence)+'\n', {mode: 0o600});
  // A Linux filesystem tick can be older than Date.now() for a just-written file.
  // Establish the fixture's causal ordering explicitly without weakening the production guard.
  const evidenceTime = new Date(observed + 10);
  fs.utimesSync(evidencePath, evidenceTime, evidenceTime);
  while (Date.now() < observed) await new Promise(resolve => setTimeout(resolve, 2));
  const inputs = {root, evidencePath, backupDirectory};
  const probes = {inspectBackup: () => ({hash: 'd'.repeat(64)}),
    verifyBackup: () => ({restoreVerified: true, fsck: 'PASS'}),
    processGroupAlive: () => false};
  return {root, lock, partial, backupDirectory, evidencePath, evidence, log, pack, inputs, probes, recoverLegacyBackupLock};
}

test('legacy lock preview is read-only; apply archives the exact inode after a successful restore', async t => {
  const f = await fixture(t);
  const original = fs.lstatSync(f.lock, {bigint: true});
  const initialNames = fs.readdirSync(f.root);
  let restores = 0;
  const probes = {...f.probes, verifyBackup: directory => {
    assert.equal(directory, f.backupDirectory);
    assert.equal(fs.lstatSync(f.lock, {bigint: true}).ino, original.ino);
    assert.throws(() => withBackupLock(f.root, () => {}), {code: 'BACKUP_STORE_LOCKED'});
    restores++;
    return {restoreVerified: true, fsck: 'PASS'};
  }};
  const preview = f.recoverLegacyBackupLock(f.inputs, probes);
  assert.equal(preview.status, 'preview');
  assert.match(preview.previewSha256, /^[a-f0-9]{64}$/);
  assert.equal(restores, 0);
  assert.deepEqual(fs.readdirSync(f.root), initialNames);
  const applied = f.recoverLegacyBackupLock({...f.inputs, apply: true, previewSha256: preview.previewSha256}, probes);
  assert.equal(applied.status, 'recovered');
  assert.equal(restores, 1);
  assert.equal(fs.existsSync(f.lock), false);
  const archived = fs.lstatSync(applied.archivedLock, {bigint: true});
  assert.deepEqual([archived.dev, archived.ino], [original.dev, original.ino]);
  assert.equal(fs.readFileSync(f.pack, 'utf8'), 'retain unverified bytes\n');
  assert.deepEqual(JSON.parse(fs.readFileSync(applied.evidenceArchive)), f.evidence);
  assert.deepEqual(fs.readFileSync(applied.managedReceiptArchive), fs.readFileSync(f.evidence.managedReceipt));
  assert.equal(JSON.parse(fs.readFileSync(applied.intentPath)).previewSha256, preview.previewSha256);
  assert.equal(withBackupLock(f.root, () => 'subsequent writer'), 'subsequent writer');
});

test('a live, reused or unverifiable process group and an unrelated interrupted point are refused', async t => {
  const f = await fixture(t);
  assert.throws(() => f.recoverLegacyBackupLock(f.inputs, {...f.probes, processGroupAlive: pgid => {
    assert.equal(pgid, 38775);
    return true;
  }}), {code: 'BACKUP_LOCK_PROCESS_NOT_ABSENT'});
  assert.throws(() => f.recoverLegacyBackupLock(f.inputs, {...f.probes, processGroupAlive: () => undefined}),
    {code: 'BACKUP_LOCK_PROCESS_NOT_ABSENT'});
  fs.writeFileSync(f.evidencePath, JSON.stringify({...f.evidence, partialBackup: path.join(f.root, 'different-point')}));
  assert.throws(() => f.recoverLegacyBackupLock(f.inputs, f.probes), {code: 'BACKUP_LOCK_EVIDENCE_INVALID'});
  assert.deepEqual(fs.readdirSync(f.root), ['.backup.lock', verified, point].sort());
});

test('restore failure or changed snapshot evidence never moves the legacy lock', async t => {
  const f = await fixture(t);
  const {previewSha256} = f.recoverLegacyBackupLock(f.inputs, f.probes);
  const apply = {...f.inputs, apply: true, previewSha256};
  assert.throws(() => f.recoverLegacyBackupLock(apply, {...f.probes, verifyBackup: () => {
    throw Object.assign(new Error('damaged backup'), {code: 'BACKUP_HASH_MISMATCH'});
  }}), {code: 'BACKUP_HASH_MISMATCH'});
  assert.throws(() => f.recoverLegacyBackupLock(apply, {...f.probes, verifyBackup: () => ({restoreVerified: false})}),
    {code: 'BACKUP_LOCK_RESTORE_UNVERIFIED'});
  let changed = false;
  assert.throws(() => f.recoverLegacyBackupLock(apply, {...f.probes,
    inspectBackup: () => ({hash: (changed ? 'e' : 'd').repeat(64)}),
    verifyBackup: () => { changed = true; return {restoreVerified: true}; },
  }), {code: 'BACKUP_LOCK_PREVIEW_CHANGED'});
  assert.throws(() => f.recoverLegacyBackupLock(apply, {...f.probes, verifyBackup: () => {
    fs.appendFileSync(f.pack, 'changed during restore');
    fs.utimesSync(f.pack, new Date(), new Date(Date.parse(f.evidence.observedAt) + 1000));
    return {restoreVerified: true};
  }}), {code: 'BACKUP_LOCK_EVIDENCE_INVALID'});
  assert.equal(fs.existsSync(f.lock), true);
  assert.deepEqual(fs.readdirSync(f.root), ['.backup.lock', verified, point].sort());
});

test('a replaced lock or sealed point cannot be recovered using an earlier preview', async t => {
  const f = await fixture(t);
  const {previewSha256} = f.recoverLegacyBackupLock(f.inputs, f.probes);
  const original = fs.lstatSync(f.lock, {bigint: true});
  fs.renameSync(f.lock, path.join(f.root, '.original-test-lock'));
  fs.mkdirSync(f.lock, {mode: 0o700});
  const replacement = fs.lstatSync(f.lock, {bigint: true});
  assert.notEqual(replacement.ino, original.ino);
  assert.throws(() => f.recoverLegacyBackupLock({...f.inputs, apply: true, previewSha256}, f.probes));
  assert.equal(fs.lstatSync(f.lock, {bigint: true}).ino, replacement.ino);
  fs.rmdirSync(f.lock);
  fs.renameSync(path.join(f.root, '.original-test-lock'), f.lock);
  fs.writeFileSync(path.join(f.partial, 'seal.json'), '{}', {mode: 0o600});
  assert.throws(() => f.recoverLegacyBackupLock(f.inputs, f.probes), {code: 'BACKUP_LOCK_EVIDENCE_INVALID'});
  assert.equal(fs.lstatSync(f.lock, {bigint: true}).ino, original.ino);
});

test('two recoveries cannot both move the lock or capture a subsequent writer', async t => {
  const f = await fixture(t);
  const preview = f.recoverLegacyBackupLock(f.inputs, f.probes);
  const apply = {...f.inputs, apply: true, previewSha256: preview.previewSha256};
  const first = f.recoverLegacyBackupLock(apply, {...f.probes, verifyBackup: () => {
    assert.throws(() => f.recoverLegacyBackupLock(apply, f.probes), {code: 'BACKUP_LOCK_RECOVERY_BUSY'});
    return {restoreVerified: true};
  }});
  assert.equal(first.status, 'recovered');
  withBackupLock(f.root, () => {
    const active = fs.lstatSync(f.lock, {bigint: true});
    assert.throws(() => f.recoverLegacyBackupLock(apply, f.probes));
    assert.equal(fs.lstatSync(f.lock, {bigint: true}).ino, active.ino);
  });
});

test('loss of the caller’s repository lock during restore prevents archival', async t => {
  const f = await fixture(t);
  const {previewSha256} = f.recoverLegacyBackupLock(f.inputs, f.probes);
  const original = fs.lstatSync(f.lock, {bigint: true});
  let held = true;
  assert.throws(() => f.recoverLegacyBackupLock({...f.inputs, apply: true, previewSha256}, {...f.probes,
    verifyBackup: () => { held = false; return {restoreVerified: true, fsck: 'PASS'}; },
    assertHeld: () => {
      if (!held) throw Object.assign(new Error('repository lock lost'), {code: 'LOCK_OWNERSHIP_CHANGED'});
    },
  }), {code: 'LOCK_OWNERSHIP_CHANGED'});
  assert.equal(fs.lstatSync(f.lock, {bigint: true}).ino, original.ino);
  assert.deepEqual(fs.readdirSync(f.root), ['.backup.lock', verified, point].sort());
});

test('a sealed backup is restored before lock archival, and a corrupted shared payload blocks recovery', async t => {
  const {backupRepository, verifyBackupDirectory} = await import('../../scripts/git_safety.mjs');
  const gitPath = '/usr/bin/git';
  const git = (repo, ...args) => {
    const result = spawnSync(gitPath, ['-C', repo, '-c', 'gc.auto=0', '-c', 'maintenance.auto=false', ...args], {encoding: 'utf8'});
    assert.equal(result.status, 0, result.stderr);
  };
  const f = await fixture(t, {createBackup: (source, root) => {
    git(source, 'init', '-b', 'master');
    fs.appendFileSync(path.join(source, '.git/info/exclude'), '\nlogs/\n');
    git(source, 'config', 'user.name', 'Fixture');
    git(source, 'config', 'user.email', 'fixture@example.invalid');
    fs.writeFileSync(path.join(source, 'fixture.txt'), 'independent restore\n');
    git(source, 'add', 'fixture.txt');
    git(source, 'commit', '-m', 'fixture');
    return backupRepository({projectRoot: source}, {
      gitPath, platform: 'darwin', identityRoot: source, backupRoot: root, backupVersion: 2,
    }).directory;
  }});
  const probes = {...f.probes, inspectBackup: readManifest,
    verifyBackup: directory => verifyBackupDirectory(directory, {gitPath})};
  const {previewSha256} = f.recoverLegacyBackupLock(f.inputs, probes);
  const apply = {...f.inputs, apply: true, previewSha256};
  const manifest = readManifest(f.backupDirectory);
  const hash = manifest.manifest.files[0].sha256;
  const payload = path.join(f.root, '.v2-store', 'files', hash.slice(0, 2), hash.slice(2));
  const original = fs.readFileSync(payload);
  fs.writeFileSync(payload, 'changed payload');
  assert.throws(() => f.recoverLegacyBackupLock(apply, probes), {code: 'BACKUP_HASH_MISMATCH'});
  assert.equal(fs.existsSync(f.lock), true);
  fs.writeFileSync(payload, original);
  const result = f.recoverLegacyBackupLock(apply, probes);
  assert.equal(result.status, 'recovered');
  assert.equal(readManifest(f.backupDirectory).hash, manifest.hash);
  assert.equal(fs.readFileSync(f.pack, 'utf8'), 'retain unverified bytes\n');
});
