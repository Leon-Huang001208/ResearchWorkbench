import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';

const MAX_LEDGER_BYTES = 16 * 1024 * 1024;
const MAX_ROOTS = 128;
const EXACT_MODE = fs.constants.O_NOFOLLOW | (fs.constants.O_NONBLOCK ?? 0);
const IDENTITY_FIELDS = ['dev', 'ino', 'uid', 'gid', 'mode', 'nlink', 'size', 'mtimeNs', 'ctimeNs'];
const ORIGINAL_DIGESTS = {
  'original-proof.json': 'proofSha256',
  'original-resource-receipt.json': 'resourceReceiptSha256',
  'original-delivery.json': 'deliverySha256',
};
const sha256 = bytes => crypto.createHash('sha256').update(bytes).digest('hex');

function fail(code) {
  throw Object.assign(new Error(code), {code});
}

function checkedPath(value, code) {
  if (typeof value !== 'string' || !path.isAbsolute(value) || path.resolve(value) !== value) fail(code);
  return value;
}

function checkedDirectory(directory, code, privateOnly = false) {
  const actual = fs.lstatSync(directory, {throwIfNoEntry: false});
  if (!actual?.isDirectory() || fs.realpathSync(directory) !== directory || actual.uid !== process.getuid() ||
      actual.mode & (privateOnly ? 0o077 : 0o022)) fail(code);
  return [actual.dev, actual.ino];
}

function sameFile(first, second) {
  return second?.isFile() && IDENTITY_FIELDS.every(key => first[key] === second[key]);
}

function readPrivateFile(filename) {
  const code = 'WORKTREE_IDENTITY_LEDGER_INVALID';
  const before = fs.lstatSync(filename, {bigint: true, throwIfNoEntry: false});
  if (!before?.isFile() || before.uid !== BigInt(process.getuid()) || before.nlink !== 1n ||
      (before.mode & 0o777n) !== 0o600n || before.size < 1n || before.size > BigInt(MAX_LEDGER_BYTES)) fail(code);
  let fd;
  try {
    fd = fs.openSync(filename, fs.constants.O_RDONLY | EXACT_MODE);
    if (!sameFile(before, fs.fstatSync(fd, {bigint: true}))) fail(code);
    const bytes = Buffer.alloc(Number(before.size));
    for (let offset = 0; offset < bytes.length;) {
      const count = fs.readSync(fd, bytes, offset, bytes.length - offset, null);
      if (count === 0) fail(code);
      offset += count;
    }
    if (fs.readSync(fd, Buffer.alloc(1), 0, 1, null) || !sameFile(before, fs.fstatSync(fd, {bigint: true})) ||
        !sameFile(before, fs.lstatSync(filename, {bigint: true, throwIfNoEntry: false}))) fail(code);
    return {bytes, identity: IDENTITY_FIELDS.map(key => String(before[key]))};
  } finally {
    if (fd !== undefined) fs.closeSync(fd);
  }
}

function sortedEvidence(evidence) {
  if (!evidence || Object.getPrototypeOf(evidence) !== Object.prototype) fail('WORKTREE_IDENTITY_EVIDENCE_INVALID');
  const keys = Object.keys(evidence).sort();
  if (!keys.length || keys.length > 32 || keys.some(key => !/^[a-zA-Z][a-zA-Z0-9_-]{0,79}$/.test(key) ||
      typeof evidence[key] !== 'string' || !/^(?:[a-f0-9]{40}|[a-f0-9]{64})$/.test(evidence[key]))) {
    fail('WORKTREE_IDENTITY_EVIDENCE_INVALID');
  }
  return Object.fromEntries(keys.map(key => [key, evidence[key]]));
}

function snapshot({ledgerPath, taskId, paths, evidence}) {
  const invalid = 'WORKTREE_IDENTITY_LEDGER_INVALID';
  const scope = 'WORKTREE_IDENTITY_SCOPE_INVALID';
  checkedPath(ledgerPath, invalid);
  if (path.basename(ledgerPath) !== 'resources.json' || typeof taskId !== 'string' ||
      !/^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,95}$/.test(taskId)) fail(invalid);
  const ledgerParent = path.dirname(ledgerPath);
  const ledgerParentIdentity = checkedDirectory(ledgerParent, invalid, true);
  const {bytes, identity: ledgerIdentity} = readPrivateFile(ledgerPath);
  let ledger;
  try { ledger = JSON.parse(bytes.toString('utf8')); }
  catch { fail(invalid); }
  if (!ledger || ledger.taskId !== taskId || !ledger.roots || Array.isArray(ledger.roots) ||
      typeof ledger.roots !== 'object' || !Array.isArray(ledger.directories)) fail(invalid);

  if (!Array.isArray(paths) || !paths.length || paths.length > MAX_ROOTS || new Set(paths).size !== paths.length) fail(scope);
  const sorted = paths.map(root => checkedPath(root, scope)).sort();
  const saved = Object.keys(ledger.roots).sort();
  if (sorted.length !== saved.length || sorted.some((root, i) => root !== saved[i])) fail(scope);
  const parent = path.dirname(sorted[0]);
  if (sorted.some(root => path.dirname(root) !== parent)) fail(scope);
  const worktreeParentIdentity = checkedDirectory(parent, scope);
  const validNumber = value => Number.isSafeInteger(value) && value > 0;
  const roots = sorted.map(root => {
    const previous = ledger.roots[root];
    if (!Array.isArray(previous) || previous.length !== 2 || !previous.every(validNumber)) fail(invalid);
    const current = checkedDirectory(root, 'WORKTREE_IDENTITY_PATH_INVALID');
    if (current[1] !== previous[1]) fail('WORKTREE_IDENTITY_INODE_CHANGED');
    return {path: root, previous, current};
  });
  const {previous: [oldDevice], current: [newDevice]} = roots[0];
  if (newDevice === oldDevice) fail('WORKTREE_IDENTITY_DEVICE_UNCHANGED');
  if (newDevice !== worktreeParentIdentity[0] || newDevice !== ledgerParentIdentity[0] ||
      roots.some(row => row.previous[0] !== oldDevice || row.current[0] !== newDevice)) fail('WORKTREE_IDENTITY_DEVICE_MISMATCH');

  const directoryPaths = new Set();
  for (const row of ledger.directories) {
    if (!row || typeof row !== 'object' || !sorted.includes(row.root) || !validNumber(row.inode) ||
        row.device !== oldDevice) fail(invalid);
    const name = checkedPath(row.path, scope);
    if (!name.startsWith(row.root + path.sep) || directoryPaths.has(name)) fail(scope);
    directoryPaths.add(name);
    // Check each component, not just the leaf. A dangling symlink ancestor
    // would look missing if lstat were called on the full path alone.
    let current = row.root;
    const components = path.relative(row.root, name).split(path.sep);
    for (const [index, component] of components.entries()) {
      current = path.join(current, component);
      const present = fs.lstatSync(current, {throwIfNoEntry: false});
      if (!present) break;
      if (index === components.length - 1 || !present.isDirectory()) fail('WORKTREE_IDENTITY_DIRECTORY_PRESENT');
    }
  }

  const plan = {
    schemaVersion: 1, kind: 'worktree-identity-recovery', taskId, ledgerPath,
    ledgerSha256: sha256(bytes), ledgerIdentity, ledgerParentIdentity, worktreeParentIdentity,
    evidence: sortedEvidence(evidence), roots,
  };
  return {plan, previewSha256: sha256(JSON.stringify(plan)), bytes, ledger};
}

export function planWorktreeIdentityRecovery(input) {
  const {plan, previewSha256} = snapshot(input);
  return {plan, previewSha256};
}

function syncDirectory(directory) {
  const fd = fs.openSync(directory, fs.constants.O_RDONLY | fs.constants.O_NOFOLLOW);
  try { fs.fsyncSync(fd); }
  finally { fs.closeSync(fd); }
}

function writeNewFile(filename, bytes) {
  const fd = fs.openSync(filename, fs.constants.O_WRONLY | fs.constants.O_CREAT | fs.constants.O_EXCL | EXACT_MODE, 0o600);
  try {
    fs.writeFileSync(fd, bytes);
    fs.fsyncSync(fd);
  } finally { fs.closeSync(fd); }
}

const json = value => JSON.stringify(value, null, 2) + '\n';

function checkedOriginals(originals, evidence) {
  if (originals === undefined) return [];
  const code = 'WORKTREE_IDENTITY_ORIGINALS_INVALID';
  if (!originals || Object.getPrototypeOf(originals) !== Object.prototype ||
      Object.keys(originals).length !== Object.keys(ORIGINAL_DIGESTS).length) fail(code);
  return Object.entries(ORIGINAL_DIGESTS).map(([name, key]) => {
    if (!Object.hasOwn(originals, name)) fail(code);
    const source = originals[name];
    if (!Buffer.isBuffer(source) || source.length < 1 || source.length > MAX_LEDGER_BYTES) fail(code);
    const bytes = Buffer.from(source);
    if (sha256(bytes) !== evidence[key]) fail(code);
    return [name, bytes];
  });
}

// The Git safety caller holds both original locks and independently verifies
// the backup and live Git evidence before calling this filesystem commit.
export function commitWorktreeIdentityRecovery({previewSha256, recoveryRoot, originals, assertHeld = () => {}, ...input}) {
  assertHeld();
  const first = snapshot(input);
  if (first.previewSha256 !== previewSha256) fail('WORKTREE_IDENTITY_PREVIEW_STALE');
  const historical = checkedOriginals(originals, first.plan.evidence);
  const parent = path.dirname(input.ledgerPath);
  const invalidRoot = 'WORKTREE_IDENTITY_RECOVERY_ROOT_INVALID';
  checkedPath(recoveryRoot, invalidRoot);
  if (path.dirname(recoveryRoot) !== parent) fail(invalidRoot);
  if (!fs.lstatSync(recoveryRoot, {throwIfNoEntry: false})) fs.mkdirSync(recoveryRoot, {mode: 0o700});
  if (checkedDirectory(recoveryRoot, invalidRoot, true)[0] !== first.plan.ledgerParentIdentity[0]) fail(invalidRoot);
  syncDirectory(parent);

  const epoch = fs.mkdtempSync(path.join(recoveryRoot, 'epoch-'));
  const updated = json({...first.ledger, roots: Object.fromEntries(first.plan.roots.map(row => [row.path, row.current]))});
  const ledgerSha256 = sha256(updated);
  const intent = {plan: first.plan, previewSha256, ledgerAfterSha256: ledgerSha256, status: 'pending'};
  writeNewFile(path.join(epoch, 'original-resources.json'), first.bytes);
  for (const [name, bytes] of historical) writeNewFile(path.join(epoch, name), bytes);
  writeNewFile(path.join(epoch, 'intent.json'), json(intent));
  syncDirectory(epoch);
  syncDirectory(recoveryRoot);

  const temporary = path.join(parent, '.worktree-identity-' + crypto.randomUUID() + '.tmp');
  writeNewFile(temporary, updated);
  try {
    const staged = readPrivateFile(temporary);
    if (sha256(staged.bytes) !== ledgerSha256) fail('WORKTREE_IDENTITY_STAGED_LEDGER_CHANGED');
    assertHeld();
    if (snapshot(input).previewSha256 !== previewSha256) fail('WORKTREE_IDENTITY_PREVIEW_STALE');
    assertHeld();
    fs.renameSync(temporary, input.ledgerPath);
    syncDirectory(parent);
  } finally {
    fs.rmSync(temporary, {force: true});
  }
  const result = {plan: first.plan, previewSha256, epoch, ledgerSha256, status: 'rebound'};
  writeNewFile(path.join(epoch, 'result.json'), json(result));
  syncDirectory(epoch);
  return result;
}
