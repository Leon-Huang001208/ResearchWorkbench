import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';

import {safeDirectory, writePrivate} from './git_backup_store.mjs';

const SHA256 = /^[a-f0-9]{64}$/;
const OID = /^(?:[a-f0-9]{40}|[a-f0-9]{64})$/;
const POINT = /^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/;
const ID = /^[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}$/;
const NO_FOLLOW = fs.constants.O_RDONLY | fs.constants.O_NOFOLLOW | fs.constants.O_NONBLOCK;
const fail = code => { throw Object.assign(new Error(code), {code}); };
const digest = bytes => crypto.createHash('sha256').update(bytes).digest('hex');

function absolute(value) {
  if (typeof value !== 'string' || !path.isAbsolute(value) || path.resolve(value) !== value) {
    fail('BACKUP_LOCK_EVIDENCE_INVALID');
  }
  return value;
}

function stat(filename) {
  return fs.lstatSync(filename, {bigint: true, throwIfNoEntry: false});
}

function privateStat(value, type, mode) {
  return value?.[type]() && !value.isSymbolicLink() && value.uid === BigInt(process.getuid()) &&
    (value.mode & 0o7777n) === mode;
}

function stableIdentity(value) {
  return {device: String(value.dev), inode: String(value.ino), owner: String(value.uid),
    mode: String(value.mode), birthNs: String(value.birthtimeNs)};
}

function identity(value) {
  return {...stableIdentity(value), size: String(value.size), links: String(value.nlink),
    modifiedNs: String(value.mtimeNs), changedNs: String(value.ctimeNs)};
}

function sameInode(a, b) {
  return b?.dev === a.dev && b.ino === a.ino;
}

function privateFile(filename, maxSize) {
  safeDirectory(path.dirname(filename));
  const fd = fs.openSync(filename, NO_FOLLOW);
  try {
    const before = fs.fstatSync(fd, {bigint: true});
    if (!privateStat(before, 'isFile', 0o600n) || before.nlink !== 1n ||
        before.size === 0n || before.size > BigInt(maxSize)) fail('BACKUP_LOCK_EVIDENCE_INVALID');
    const bytes = Buffer.alloc(Number(before.size));
    let offset = 0;
    while (offset < bytes.length) {
      const count = fs.readSync(fd, bytes, offset, bytes.length - offset, null);
      if (count === 0) fail('BACKUP_LOCK_EVIDENCE_CHANGED');
      offset += count;
    }
    const live = stat(filename);
    if (!privateStat(live, 'isFile', 0o600n) ||
        JSON.stringify(identity(before)) !== JSON.stringify(identity(live))) fail('BACKUP_LOCK_EVIDENCE_CHANGED');
    return {bytes, sha256: digest(bytes), state: identity(before), stat: before};
  } finally { fs.closeSync(fd); }
}

function json(bytes) {
  try { return JSON.parse(bytes); } catch { fail('BACKUP_LOCK_EVIDENCE_INVALID'); }
}

function milliseconds(value) {
  if (typeof value !== 'string' || !/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{3})?Z$/.test(value)) {
    fail('BACKUP_LOCK_EVIDENCE_INVALID');
  }
  const result = Date.parse(value);
  if (!Number.isFinite(result) || new Date(result).toISOString() !== value.replace(/(?<!\.\d{3})Z$/, '.000Z')) {
    fail('BACKUP_LOCK_EVIDENCE_INVALID');
  }
  return result;
}

function defaultProcessGroupAlive(pgid) {
  if (process.platform !== 'darwin') fail('BACKUP_LOCK_PROCESS_UNVERIFIED');
  try {
    process.kill(-pgid, 0);
    return true;
  } catch (error) {
    if (error.code === 'ESRCH') return false;
    fail('BACKUP_LOCK_PROCESS_UNVERIFIED');
  }
}

function readInterruption(root, evidencePath, processGroupAlive) {
  const file = privateFile(evidencePath, 64 * 1024);
  const receipt = json(file.bytes);
  const pgid = receipt?.exitedProcessGroup;
  if (receipt?.disposition !== 'STOPPED_BY_SIGINT_DISK_PRESSURE' || receipt.exitCode !== 130 ||
      receipt.locksPreserved !== true || receipt.remoteWrites !== 0 ||
      !OID.test(receipt.retainedExactCandidate ?? '') || !OID.test(receipt.managedCandidateBeforeAmend ?? '') ||
      !Number.isSafeInteger(pgid) || pgid < 2 || pgid > 0x7fffffff) fail('BACKUP_LOCK_EVIDENCE_INVALID');
  const partial = absolute(receipt.partialBackup);
  if (path.dirname(partial) !== root || !POINT.test(path.basename(partial))) fail('BACKUP_LOCK_EVIDENCE_INVALID');
  const ownerPath = absolute(receipt.managedReceipt);
  const deliveries = path.dirname(ownerPath);
  const engine = path.dirname(deliveries);
  const common = path.dirname(engine);
  if (path.basename(deliveries) !== 'deliveries' || path.basename(engine) !== 'leon-engineering' ||
      path.dirname(path.dirname(evidencePath)) !== common) fail('BACKUP_LOCK_EVIDENCE_INVALID');
  const ownerFile = privateFile(ownerPath, 2 * 1024 * 1024);
  const owner = json(ownerFile.bytes);
  if (owner?.schemaVersion !== 1 || !ID.test(owner.taskId ?? '') || path.basename(ownerPath) !== `${owner.taskId}.json` ||
      path.join(absolute(owner.repositoryRoot), '.git') !== common) fail('BACKUP_LOCK_EVIDENCE_INVALID');
  const observedAt = milliseconds(receipt.observedAt);
  if (observedAt > Date.now() || Number(file.stat.mtimeNs / 1000000n) < observedAt) fail('BACKUP_LOCK_EVIDENCE_INVALID');
  if (processGroupAlive(pgid) !== false) fail('BACKUP_LOCK_PROCESS_NOT_ABSENT');
  return {file, receipt, ownerPath, ownerFile, owner, observedAt, partial};
}

function snapshotControl(partial, observedAt, lock) {
  const point = stat(partial);
  if (!privateStat(point, 'isDirectory', 0o700n) || point.dev !== lock.dev ||
      point.birthtimeNs < lock.birthtimeNs ||
      ['manifest.json', 'manifest-draft.json', 'manifest-v2.pending.json', 'seal.json', 'failure-status.json']
        .some(marker => stat(path.join(partial, marker)))) fail('BACKUP_LOCK_EVIDENCE_INVALID');
  const worktrees = stat(path.join(partial, 'worktrees'));
  const pack = stat(path.join(partial, 'objects.pack'));
  if (!privateStat(worktrees, 'isDirectory', 0o700n) || !privateStat(pack, 'isFile', 0o600n) ||
      pack.nlink !== 1n || pack.size === 0n || worktrees.dev !== point.dev || pack.dev !== point.dev) {
    fail('BACKUP_LOCK_EVIDENCE_INVALID');
  }
  const log = privateFile(path.join(partial, 'logs', 'git-safety.jsonl'), 16 * 1024 * 1024);
  if (log.stat.dev !== point.dev) fail('BACKUP_LOCK_EVIDENCE_INVALID');
  const cutoff = BigInt(observedAt);
  for (const evidence of [point, worktrees, pack, log.stat]) {
    if (evidence.birthtimeNs < lock.birthtimeNs || evidence.mtimeNs / 1000000n > cutoff) fail('BACKUP_LOCK_EVIDENCE_INVALID');
  }
  const lines = log.bytes.toString('utf8').split('\n');
  if (lines.pop() !== '' || lines.length === 0) fail('BACKUP_LOCK_EVIDENCE_INVALID');
  let first, last, startedAt, head;
  for (const line of lines) {
    const event = json(line);
    const when = milliseconds(event?.time);
    const recognized = event?.event === 'backup_capacity' && event.phase === 'snapshot-stream' && event.status === 'PASS' ||
      event?.event === 'backup_fd_clone' && event.phase === 'snapshot-clone';
    if (!recognized || event.action !== 'backup-snapshot' || !OID.test(event.head ?? '') ||
        !Number.isSafeInteger(event.durationMs) || event.durationMs < 0) fail('BACKUP_LOCK_EVIDENCE_INVALID');
    if (first === undefined) {
      first = when;
      startedAt = when - event.durationMs;
      head = event.head;
    }
    if (event.head !== head || last !== undefined && when < last ||
        Math.abs(when - event.durationMs - startedAt) > 20) fail('BACKUP_LOCK_EVIDENCE_INVALID');
    last = when;
  }
  if (startedAt > Number(lock.birthtimeNs / 1000000n) || first < Number(point.birthtimeNs / 1000000n) ||
      last > Number(log.stat.mtimeNs / 1000000n) || last > observedAt) fail('BACKUP_LOCK_EVIDENCE_INVALID');
  return {directory: partial, point: identity(point), pack: identity(pack), worktrees: identity(worktrees),
    journal: {sha256: log.sha256, state: log.state, first, last, startedAt, head}};
}

function inspectPlan(root, evidencePath, backupDirectory, inspectBackup, processGroupAlive) {
  safeDirectory(root);
  const rootIdentity = stat(root);
  const lockPath = path.join(root, '.backup.lock');
  const lock = stat(lockPath);
  if (!lock) fail('BACKUP_LOCK_MISSING');
  if (!privateStat(lock, 'isDirectory', 0o700n) || lock.dev !== rootIdentity.dev ||
      lock.birthtimeNs <= 0n || fs.readdirSync(lockPath).length !== 0) fail('BACKUP_LOCK_NOT_EMPTY_LEGACY');
  const {file, receipt, ownerFile, ownerPath, owner, observedAt, partial} = readInterruption(root, evidencePath, processGroupAlive);
  const interrupted = snapshotControl(partial, observedAt, lock);
  if (backupDirectory === partial || path.dirname(backupDirectory) !== root || !POINT.test(path.basename(backupDirectory))) {
    fail('BACKUP_LOCK_VERIFIED_POINT_INVALID');
  }
  safeDirectory(backupDirectory);
  const backup = inspectBackup(backupDirectory);
  if (!SHA256.test(backup?.hash ?? '')) fail('BACKUP_LOCK_VERIFIED_POINT_INVALID');
  if (JSON.stringify(identity(lock)) !== JSON.stringify(identity(stat(lockPath) ?? {})) ||
      JSON.stringify(stableIdentity(rootIdentity)) !== JSON.stringify(stableIdentity(stat(root) ?? {}))) {
    fail('BACKUP_LOCK_EVIDENCE_CHANGED');
  }
  const plan = {schemaVersion: 1, kind: 'legacy-backup-lock-recovery',
    store: {path: root, identity: stableIdentity(rootIdentity)},
    lock: {path: lockPath, identity: identity(lock)},
    provenance: {path: evidencePath, sha256: file.sha256, identity: file.state,
      exitedProcessGroup: receipt.exitedProcessGroup, observedAt: receipt.observedAt,
      managedTaskId: owner.taskId, managedReceipt: ownerPath, managedReceiptSha256: ownerFile.sha256},
    interrupted, backup: {directory: backupDirectory, manifestSha256: backup.hash,
      identity: stableIdentity(stat(backupDirectory))}};
  return {plan, evidenceBytes: file.bytes, managedReceiptBytes: ownerFile.bytes,
    previewSha256: digest(JSON.stringify(plan))};
}

function syncDirectory(directory) {
  const fd = fs.openSync(directory, NO_FOLLOW);
  try {
    if (!fs.fstatSync(fd).isDirectory()) fail('BACKUP_LOCK_EVIDENCE_CHANGED');
    fs.fsyncSync(fd);
  } finally { fs.closeSync(fd); }
}

function withRecoveryMutex(root, callback) {
  const mutex = path.join(root, '.backup.lock-recovery');
  try { fs.mkdirSync(mutex, {mode: 0o700}); } catch (error) {
    if (error.code === 'EEXIST') fail('BACKUP_LOCK_RECOVERY_BUSY');
    throw error;
  }
  const held = stat(mutex);
  function assertHeld() {
    const live = stat(mutex);
    if (!sameInode(held, live) || !privateStat(live, 'isDirectory', 0o700n)) fail('BACKUP_LOCK_RECOVERY_CHANGED');
  }
  try { return callback(assertHeld); }
  finally { assertHeld(); fs.rmdirSync(mutex); }
}

/** Recover an ownerless directory lock only from preserved, matched interruption evidence. */
export function recoverLegacyBackupLock({root, evidencePath, backupDirectory, apply = false, previewSha256},
  {inspectBackup, verifyBackup, processGroupAlive = defaultProcessGroupAlive, assertHeld: assertRepositoryHeld = () => {}} = {}) {
  absolute(root);
  absolute(evidencePath);
  absolute(backupDirectory);
  if (typeof inspectBackup !== 'function' || typeof verifyBackup !== 'function' ||
      typeof processGroupAlive !== 'function' || typeof assertRepositoryHeld !== 'function' || typeof apply !== 'boolean' ||
      (apply ? !SHA256.test(previewSha256 ?? '') : previewSha256 !== undefined)) fail('BACKUP_LOCK_RECOVERY_ARGUMENT_INVALID');
  const inspect = () => inspectPlan(root, evidencePath, backupDirectory, inspectBackup, processGroupAlive);
  if (!apply) {
    const {plan, previewSha256: hash} = inspect();
    return {status: 'preview', previewSha256: hash, plan};
  }
  safeDirectory(root);
  return withRecoveryMutex(root, assertHeld => {
    const checked = () => {
      assertHeld();
      assertRepositoryHeld();
      const current = inspect();
      if (current.previewSha256 !== previewSha256) fail('BACKUP_LOCK_PREVIEW_CHANGED');
      return current;
    };
    checked();
    if (verifyBackup(backupDirectory)?.restoreVerified !== true) fail('BACKUP_LOCK_RESTORE_UNVERIFIED');
    const {plan, evidenceBytes, managedReceiptBytes} = checked();
    const archive = fs.mkdtempSync(path.join(root, '.backup-lock-recovered-'));
    safeDirectory(archive);
    const archiveIdentity = stat(archive);
    if (String(archiveIdentity.dev) !== plan.lock.identity.device) fail('BACKUP_LOCK_ARCHIVE_INVALID');
    const archivedLock = path.join(archive, 'lock');
    const evidenceArchive = path.join(archive, 'interruption.json');
    const managedReceiptArchive = path.join(archive, 'original-managed-receipt.json');
    const intentPath = path.join(archive, 'intent.json');
    writePrivate(evidenceArchive, evidenceBytes);
    writePrivate(managedReceiptArchive, managedReceiptBytes);
    writePrivate(intentPath, JSON.stringify({schemaVersion: 1, previewSha256, plan, restoreVerified: true}) + '\n');
    syncDirectory(archive);
    syncDirectory(root);
    checked();
    const liveArchive = stat(archive);
    if (!sameInode(archiveIdentity, liveArchive) || !privateStat(liveArchive, 'isDirectory', 0o700n) ||
        stat(archivedLock)) fail('BACKUP_LOCK_ARCHIVE_INVALID');
    if (processGroupAlive(plan.provenance.exitedProcessGroup) !== false) fail('BACKUP_LOCK_PROCESS_NOT_ABSENT');
    // Commit point: legacy writers remain excluded until the original inode is archived.
    // Never replace a subsequent writer's lock after this rename, even if a later fsync fails.
    assertHeld();
    assertRepositoryHeld();
    fs.renameSync(plan.lock.path, archivedLock);
    const archived = stat(archivedLock);
    if (!privateStat(archived, 'isDirectory', 0o700n) || String(archived.ino) !== plan.lock.identity.inode ||
        String(archived.dev) !== plan.lock.identity.device) fail('BACKUP_LOCK_ARCHIVE_INVALID');
    syncDirectory(archive);
    syncDirectory(root);
    return {status: 'recovered', previewSha256, archivedLock, evidenceArchive, managedReceiptArchive, intentPath};
  });
}
