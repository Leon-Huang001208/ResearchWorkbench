import assert from 'node:assert/strict';
import crypto from 'node:crypto';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import {
  commitWorktreeIdentityRecovery,
  planWorktreeIdentityRecovery,
} from '../../scripts/git_worktree_identity_recovery.mjs';

function fixture(t) {
  const root = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), 'rwb-worktree-identity-')));
  t.after(() => fs.rmSync(root, {recursive: true, force: true}));
  const worktrees = path.join(root, 'worktrees');
  const state = path.join(root, 'closeout');
  fs.mkdirSync(worktrees, {mode: 0o700});
  fs.mkdirSync(state, {mode: 0o700});
  const paths = ['feature', 'integration'].map(name => path.join(worktrees, name));
  for (const directory of paths) fs.mkdirSync(directory, {mode: 0o700});
  const device = fs.statSync(paths[0]).dev;
  const oldDevice = device + 1;
  const taskId = 'fixture-task';
  const ledgerPath = path.join(state, 'resources.json');
  const recoveryRoot = path.join(state, 'identity-epochs');
  const evidence = {backupManifestSha256: 'a'.repeat(64), currentWorktreesSha256: 'b'.repeat(64)};
  const ledger = {
    taskId,
    roots: Object.fromEntries(paths.map(directory => [directory, [oldDevice, fs.statSync(directory).ino]])),
    directories: [
      {root: paths[0], path: path.join(paths[0], 'logs'), kind: 'evidence', device: oldDevice, inode: 42},
      {root: paths[1], path: path.join(paths[1], '.venv'), kind: 'dependency', device: oldDevice, inode: 43},
    ],
    evidencePolicy: 'selective-v1',
  };
  const write = () => fs.writeFileSync(ledgerPath, JSON.stringify(ledger) + '\n', {mode: 0o600});
  write();
  return {input: {ledgerPath, taskId, paths, evidence}, recoveryRoot, ledger, device, write};
}

test('worktree recovery previews read-only and commits only the admitted device change with original evidence', t => {
  const {input, recoveryRoot, ledger, device} = fixture(t);
  const original = fs.readFileSync(input.ledgerPath);
  const preview = planWorktreeIdentityRecovery(input);
  assert.deepEqual(planWorktreeIdentityRecovery({...input, paths: [...input.paths].reverse()}), preview);
  assert.deepEqual(fs.readFileSync(input.ledgerPath), original);
  assert.equal(fs.existsSync(recoveryRoot), false);
  const result = commitWorktreeIdentityRecovery({...input, recoveryRoot, previewSha256: preview.previewSha256});
  assert.equal(result.previewSha256, preview.previewSha256);
  const expected = {...ledger, roots: Object.fromEntries(input.paths.map(directory => [directory, [device, fs.statSync(directory).ino]]))};
  assert.deepEqual(JSON.parse(fs.readFileSync(input.ledgerPath)), expected);
  assert.equal(fs.statSync(input.ledgerPath).mode & 0o777, 0o600);
  assert.deepEqual(fs.readFileSync(path.join(result.epoch, 'original-resources.json')), original);
  const intent = JSON.parse(fs.readFileSync(path.join(result.epoch, 'intent.json')));
  assert.equal(intent.previewSha256, preview.previewSha256);
  assert.deepEqual(intent.plan, preview.plan);
  assert.equal(JSON.parse(fs.readFileSync(path.join(result.epoch, 'result.json'))).ledgerSha256, result.ledgerSha256);
  assert.throws(() => planWorktreeIdentityRecovery(input), /WORKTREE_IDENTITY_DEVICE_UNCHANGED/);
});

test('worktree recovery refuses an incomplete path set and an inode replacement', t => {
  const {input} = fixture(t);
  assert.throws(() => planWorktreeIdentityRecovery({...input, paths: input.paths.slice(1)}), /WORKTREE_IDENTITY_SCOPE_INVALID/);
  fs.renameSync(input.paths[0], input.paths[0] + '-old');
  fs.mkdirSync(input.paths[0], {mode: 0o700});
  assert.throws(() => planWorktreeIdentityRecovery(input), /WORKTREE_IDENTITY_INODE_CHANGED/);
});

test('worktree recovery refuses restoration artifacts reappearing, a dangling alias and paths outside a managed root', t => {
  const {input, ledger, write} = fixture(t);
  const row = ledger.directories[0];
  fs.mkdirSync(row.path, {mode: 0o700});
  assert.throws(() => planWorktreeIdentityRecovery(input), /WORKTREE_IDENTITY_DIRECTORY_PRESENT/);
  fs.rmdirSync(row.path);
  fs.symlinkSync(path.join(input.paths[0], 'nonexistent'), row.path);
  assert.throws(() => planWorktreeIdentityRecovery(input), /WORKTREE_IDENTITY_DIRECTORY_PRESENT/);
  fs.unlinkSync(row.path);
  row.path = path.join(path.dirname(input.paths[0]), 'unrelated');
  write();
  assert.throws(() => planWorktreeIdentityRecovery(input), /WORKTREE_IDENTITY_SCOPE_INVALID/);
});

test('worktree recovery refuses preview drift and leaves no partial recovery when the stale preview is submitted', t => {
  const {input, recoveryRoot, ledger, write} = fixture(t);
  const {previewSha256} = planWorktreeIdentityRecovery(input);
  ledger.evidencePolicy = 'changed-after-preview';
  write();
  const current = fs.readFileSync(input.ledgerPath);
  assert.throws(() => commitWorktreeIdentityRecovery({...input, recoveryRoot, previewSha256}), /WORKTREE_IDENTITY_PREVIEW_STALE/);
  assert.deepEqual(fs.readFileSync(input.ledgerPath), current);
  assert.equal(fs.existsSync(recoveryRoot), false);
});

test('worktree recovery refuses a ledger symlink and a recovery destination outside the ledger state', t => {
  const {input, recoveryRoot} = fixture(t);
  const {previewSha256} = planWorktreeIdentityRecovery(input);
  assert.throws(() => commitWorktreeIdentityRecovery({...input, recoveryRoot: path.dirname(recoveryRoot), previewSha256}), /WORKTREE_IDENTITY_RECOVERY_ROOT_INVALID/);
  fs.renameSync(input.ledgerPath, input.ledgerPath + '.original');
  fs.symlinkSync(input.ledgerPath + '.original', input.ledgerPath);
  assert.throws(() => planWorktreeIdentityRecovery(input), /WORKTREE_IDENTITY_LEDGER_INVALID/);
});

test('worktree recovery binds and preserves originals that the ordinary closeout can overwrite', t => {
  const {input, recoveryRoot} = fixture(t);
  const originals = {
    'original-proof.json': Buffer.from('{"status":"pending"}\n'),
    'original-resource-receipt.json': Buffer.from('{"status":"blocked"}\n'),
    'original-delivery.json': Buffer.from('{"status":"ci_passed"}\n'),
  };
  const names = {
    'original-proof.json': 'proofSha256',
    'original-resource-receipt.json': 'resourceReceiptSha256',
    'original-delivery.json': 'deliverySha256',
  };
  for (const [name, bytes] of Object.entries(originals)) {
    input.evidence[names[name]] = crypto.createHash('sha256').update(bytes).digest('hex');
  }
  const {previewSha256} = planWorktreeIdentityRecovery(input);
  const originalLedger = fs.readFileSync(input.ledgerPath);
  const changed = {...originals, 'original-proof.json': Buffer.from('{"status":"changed"}\n')};
  assert.throws(() => commitWorktreeIdentityRecovery({...input, recoveryRoot, previewSha256, originals: changed}),
    /WORKTREE_IDENTITY_ORIGINALS_INVALID/);
  assert.deepEqual(fs.readFileSync(input.ledgerPath), originalLedger);
  assert.equal(fs.existsSync(recoveryRoot), false);
  const result = commitWorktreeIdentityRecovery({...input, recoveryRoot, previewSha256, originals});
  for (const [name, bytes] of Object.entries(originals)) {
    assert.deepEqual(fs.readFileSync(path.join(result.epoch, name)), bytes);
  }
});
