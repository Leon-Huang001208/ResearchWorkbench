#!/usr/bin/env node
/** RWB macOS Git safety boundary. No maintenance, arbitrary shell, or controller CLI forwarding. */
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import crypto from 'node:crypto';
import {spawnSync} from 'node:child_process';
import {fileURLToPath, pathToFileURL} from 'node:url';
import {withBackupLock, repositoryKey, fingerprint, findReusable, convertToV2, finishMigration, readManifest, materializeV2, hydrateV2, listPoints, sweepPayloads, fileHash} from './git_backup_store.mjs';
import {finalizeLifecycle} from './resource_lifecycle.mjs';
import {clonePinnedFile, sourceFacts} from './backup_fd_clone.mjs';
import {admitFileStream} from './backup_capacity.mjs';

const CONTROLLER = path.join(os.homedir(), '.agents/leon-engineering/runtime/iteration-delivery.mjs');
const FORBIDDEN = new Set(['gc', 'prune', 'repack', 'maintenance', 'prune-packed']);
const ID = /^[a-z0-9][a-z0-9-]{0,79}$/;
const sha256 = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
// Only runDelivery/resourcePhase can populate this process-private scope. It
// reuses the existing CLI toolchain TCB; it does not certify Python's kernel
// loaded image, standard library, ACLs, or all effective host writers.
const deliveryToolchains = new WeakMap();
const snapshotToolchainKey = Symbol('delivery-selected-executable-reference');
const EXECUTABLE_FACTS = ['dev', 'ino', 'uid', 'gid', 'mode', 'nlink', 'size', 'mtimeNs', 'ctimeNs'];
const lexicalFactKey = key => 'lexical' + key[0].toUpperCase() + key.slice(1);
const EXECUTABLE_FIELDS = ['lexicalPath', 'canonicalPath', 'sha256', 'lexicalLink', ...EXECUTABLE_FACTS, ...EXECUTABLE_FACTS.map(lexicalFactKey)];
const BINDING_FIELDS = ['repositoryRoot', 'commonDirectory', 'taskId', 'operationToken'];
/** Read-only launcher facts for the internal direct-test seam. No record or
 * runtime authority is created by observing a file, executable or otherwise.
 */
export function selectedExecutableReference(lexicalPath) {
  let fd, reference;
  try {
    if (!path.isAbsolute(lexicalPath)) return undefined;
    const lexicalBefore = fs.lstatSync(lexicalPath, {bigint: true});
    if (!lexicalBefore.isFile() && !lexicalBefore.isSymbolicLink()) return undefined;
    // Preserve the original link text losslessly as hex bytes; do not follow
    // the final lexical entry when recording its own metadata/link identity.
    const linkText = () => fs.lstatSync(lexicalPath).isSymbolicLink() ? fs.readlinkSync(lexicalPath, {encoding: 'buffer'}).toString('hex') : '';
    const lexicalLink = linkText();
    const canonicalPath = fs.realpathSync(lexicalPath);
    const prior = fs.lstatSync(canonicalPath, {bigint: true});
    if (!prior.isFile() || prior.isSymbolicLink() || prior.size > BigInt(Number.MAX_SAFE_INTEGER)) return undefined;
    fd = fs.openSync(canonicalPath, fs.constants.O_RDONLY | fs.constants.O_NOFOLLOW | fs.constants.O_NONBLOCK);
    const before = fs.fstatSync(fd, {bigint: true});
    if (!before.isFile() || before.dev !== prior.dev || before.ino !== prior.ino) return undefined;
    const hash = crypto.createHash('sha256'), buffer = Buffer.allocUnsafe(1024 * 1024);
    let count, total = 0n;
    while ((count = fs.readSync(fd, buffer, 0, buffer.length, null))) {
      total += BigInt(count);
      if (total > before.size) return undefined;
      hash.update(buffer.subarray(0, count));
    }
    const after = fs.fstatSync(fd, {bigint: true}), current = fs.lstatSync(canonicalPath, {bigint: true});
    if (total !== before.size || !current.isFile() || current.isSymbolicLink() || fs.realpathSync(lexicalPath) !== canonicalPath || EXECUTABLE_FACTS.some(key => before[key] !== after[key] || before[key] !== current[key])) return undefined;
    const lexicalAfter = fs.lstatSync(lexicalPath, {bigint: true});
    if (EXECUTABLE_FACTS.some(key => lexicalBefore[key] !== lexicalAfter[key]) || linkText() !== lexicalLink) return undefined;
    const lexicalFinal = fs.lstatSync(lexicalPath, {bigint: true});
    if (EXECUTABLE_FACTS.some(key => lexicalBefore[key] !== lexicalFinal[key])) return undefined;
    reference = {lexicalPath, canonicalPath, sha256: hash.digest('hex'), lexicalLink, ...Object.fromEntries(EXECUTABLE_FACTS.map(key => [key, String(before[key])])), ...Object.fromEntries(EXECUTABLE_FACTS.map(key => [lexicalFactKey(key), String(lexicalBefore[key])]))};
  } catch {return undefined;}
  finally {if (fd !== undefined) {try {fs.closeSync(fd);} catch {reference = undefined;}}}
  return reference;
}
function executableReferencesEqual(left, right) {
  return !!left && !!right && Object.keys(left).length === EXECUTABLE_FIELDS.length && Object.keys(right).length === EXECUTABLE_FIELDS.length && EXECUTABLE_FIELDS.every(key => typeof left[key] === 'string' && left[key] === right[key]);
}
/** Pure decision/test seam only: no record creation, mutation or execution.
 * Production inputs come exclusively from the private WeakMap and fresh file
 * observations, never from caller dictionaries or child stdout.
 */
export function toolchainReuseDecision({expectedBinding, observedBinding, expectedReference, currentReference, invoked = false} = {}) {
  const validBinding = value => value && typeof value.repositoryRoot === 'string' && path.isAbsolute(value.repositoryRoot) && typeof value.commonDirectory === 'string' && path.isAbsolute(value.commonDirectory) && ID.test(value.taskId ?? '') && typeof value.operationToken === 'symbol';
  const matched = validBinding(expectedBinding) && validBinding(observedBinding) && BINDING_FIELDS.every(key => expectedBinding[key] === observedBinding[key]) && executableReferencesEqual(expectedReference, currentReference);
  return matched ? 'available' : invoked ? 'unknown' : 'unavailable';
}
function toolchainBinding(scope) {
  return Object.fromEntries(BINDING_FIELDS.map(key => [key, scope[key]]));
}
function inheritedSnapshotToolchain(repository) {
  const scope = deliveryToolchains.get(repository), record = scope?.record;
  if (!record) return undefined;
  const check = invoked => {
    const current = deliveryToolchains.get(repository);
    return toolchainReuseDecision({expectedBinding: record.binding, observedBinding: current === scope && current.active && current.record === record ? toolchainBinding(current) : undefined, expectedReference: record.reference, currentReference: selectedExecutableReference(record.reference.lexicalPath), invoked});
  };
  return {lexicalPath: record.reference.lexicalPath, check};
}
function hashFile(filename) {
  const hash = crypto.createHash('sha256');
  const fd = fs.openSync(filename, 'r');
  const buffer = Buffer.allocUnsafe(1024 * 1024);
  try { let count; while ((count = fs.readSync(fd, buffer, 0, buffer.length, null))) hash.update(buffer.subarray(0, count)); }
  finally { fs.closeSync(fd); }
  return hash.digest('hex');
}
function fail(code) { throw Object.assign(new Error(code), {code}); }
function command(executable, args, {cwd, input, inputFd, allowFailure = false, env} = {}) {
  const result = spawnSync(executable, args, {cwd, input, ...(inputFd === undefined ? {} : {stdio: [inputFd, 'pipe', 'pipe']}), env: env ?? process.env, maxBuffer: 64 * 1024 * 1024});
  if (result.error || (!allowFailure && result.status !== 0)) fail('COMMAND_FAILED');
  return result;
}
export function selectGitPath({platform = process.platform, gitPath, mutate = false} = {}) {
  if (mutate && platform !== 'darwin' && !gitPath) fail('HOST_UNSUPPORTED');
  return gitPath ?? (platform === 'darwin' ? '/usr/bin/git' : '/usr/bin/git');
}
function git(project, args, options = {}, extra = {}) {
  if (FORBIDDEN.has(args[0])) fail('MAINTENANCE_FORBIDDEN');
  return command(selectGitPath(options), ['--no-optional-locks', '-c', 'gc.auto=0', '-c', 'maintenance.auto=false', '-C', project, ...args], {...extra,...(options.readOnlyGit?{env:{...process.env,...extra.env,GIT_NO_LAZY_FETCH:'1',GIT_NO_REPLACE_OBJECTS:'1'}}:{})});
}
function output(result) { return result.stdout.toString('utf8').trim(); }
function discover(projectRoot, options = {}) {
  const candidate = path.resolve(projectRoot);
  if (fs.lstatSync(candidate).isSymbolicLink()) fail('PROJECT_DIRECTORY_INVALID');
  const root = fs.realpathSync(candidate);
  const repositoryRoot = fs.realpathSync(output(git(root, ['rev-parse', '--show-toplevel'], options)));
  const commonPath = path.resolve(repositoryRoot, output(git(root, ['rev-parse', '--git-common-dir'], options)));
  if (fs.lstatSync(commonPath).isSymbolicLink()) fail('PRIVATE_DIRECTORY_INVALID');
  const commonDirectory = fs.realpathSync(commonPath);
  return {repositoryRoot, commonDirectory};
}
function privateDirectory(directory) {
  if (fs.existsSync(directory)) {
    const stat = fs.lstatSync(directory);
    if (!stat.isDirectory() || stat.isSymbolicLink()) fail('PRIVATE_DIRECTORY_INVALID');
    fs.chmodSync(directory, 0o700);
    return;
  }
  const parent = path.dirname(directory);
  if (!fs.existsSync(parent)) privateDirectory(parent);
  if (fs.lstatSync(parent).isSymbolicLink()) fail('PRIVATE_DIRECTORY_INVALID');
  fs.mkdirSync(directory, {mode: 0o700});
}
function assertNoSymlinkAncestors(directory) {
  let current = path.resolve(directory);
  while (current !== path.dirname(current)) {
    const stat = fs.lstatSync(current, {throwIfNoEntry: false});
    if (stat?.isSymbolicLink()) fail('PRIVATE_DIRECTORY_INVALID');
    current = path.dirname(current);
  }
}
function privateWrite(destination, value) {
  assertNoSymlinkAncestors(path.dirname(destination));
  privateDirectory(path.dirname(destination));
  fs.writeFileSync(destination, value, {mode: 0o600, flag: 'wx'});
}
function state(repository) { return path.join(repository.commonDirectory, 'leon-engineering/git-safety'); }
function assertRepositoryIdentity(repository, options) {
  const identityRoot = options.identityRoot ?? path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
  if (discover(identityRoot, options).commonDirectory !== repository.commonDirectory) fail('REPOSITORY_IDENTITY_MISMATCH');
}
// This scope is created only for the current owned backup point. It is never
// selected by options/CLI input and never substitutes for the source repository.
function snapshotLogDirectory(journal, create = false) {
  if (journal.sealed) fail('LOG_FILE_INVALID');
  assertNoSymlinkAncestors(journal.root);
  const valid = (value, expected) => value?.isDirectory() && !value.isSymbolicLink() && value.dev === expected.dev && value.ino === expected.ino && value.uid === expected.uid && value.uid === process.getuid() && (value.mode & 0o7777) === 0o700;
  if (!valid(fs.lstatSync(journal.root, {throwIfNoEntry: false}), journal.rootIdentity)) fail('LOG_DIRECTORY_INVALID');
  const directory = path.join(journal.root, 'logs');
  if (!journal.directoryIdentity) {
    if (!create) fail('LOG_DIRECTORY_INVALID');
    try {fs.mkdirSync(directory, {mode: 0o700});} catch {fail('LOG_DIRECTORY_INVALID');}
    journal.directoryIdentity = fs.lstatSync(directory);
  }
  if (!valid(fs.lstatSync(directory, {throwIfNoEntry: false}), journal.directoryIdentity)) fail('LOG_DIRECTORY_INVALID');
  return directory;
}
function sealSnapshotLog(journal, manifest) {
  if (!journal.fileIdentity) return;
  const directory = snapshotLogDirectory(journal), filename = path.join(directory, 'git-safety.jsonl');
  const checkFile = () => {
    const value = fs.lstatSync(filename, {throwIfNoEntry: false});
    if (!value?.isFile() || value.isSymbolicLink() || value.dev !== journal.fileIdentity.dev || value.ino !== journal.fileIdentity.ino || value.uid !== process.getuid() || value.nlink !== 1 || (value.mode & 0o7777) !== 0o600) fail('LOG_FILE_INVALID');
  };
  checkFile();
  const hash = fileHash(filename);
  checkFile();
  for (const [target, expected] of [[journal.root, journal.rootIdentity], [directory, journal.directoryIdentity]]) {
    const fd = fs.openSync(target, fs.constants.O_RDONLY | fs.constants.O_NOFOLLOW);
    try {const actual = fs.fstatSync(fd); if (!actual.isDirectory() || actual.dev !== expected.dev || actual.ino !== expected.ino) fail('LOG_DIRECTORY_INVALID'); fs.fsyncSync(fd);}
    finally {fs.closeSync(fd);}
  }
  snapshotLogDirectory(journal);
  journal.sealed = true;
  // Per-point audit metadata is authenticated by the manifest/seal but is not a
  // deduplicated business restore payload or an execution authority.
  manifest.snapshotJournal = {path: 'logs/git-safety.jsonl', sha256: hash};
}
function verifySnapshotJournal(originalPoint, manifest) {
  const journal = manifest.snapshotJournal;
  if (journal === undefined) return; // Earlier manifests have no audit contract.
  if (!journal || Array.isArray(journal) || Object.keys(journal).length !== 2 || journal.path !== 'logs/git-safety.jsonl' || typeof journal.sha256 !== 'string' || !/^[a-f0-9]{64}$/.test(journal.sha256)) fail('BACKUP_JOURNAL_INVALID');
  const directories = [originalPoint, path.join(originalPoint, 'logs')], filename = path.join(originalPoint, journal.path), descriptors = [];
  let failure;
  try {
    assertNoSymlinkAncestors(originalPoint);
    const uid = BigInt(process.getuid()), same = (left, right) => EXECUTABLE_FACTS.every(key => left[key] === right[key]);
    const beforeDirectories = directories.map(directory => fs.lstatSync(directory, {bigint: true}));
    for (let index = 0; index < directories.length; index++) {
      const before = beforeDirectories[index];
      if (!before.isDirectory() || before.isSymbolicLink() || before.uid !== uid || (before.mode & 0o7777n) !== 0o700n) fail('BACKUP_JOURNAL_INVALID');
      const fd = fs.openSync(directories[index], fs.constants.O_RDONLY | fs.constants.O_NOFOLLOW);
      descriptors.push(fd);
      if (!same(before, fs.fstatSync(fd, {bigint: true}))) fail('BACKUP_JOURNAL_INVALID');
    }
    const before = fs.lstatSync(filename, {bigint: true});
    if (!before.isFile() || before.isSymbolicLink() || before.uid !== uid || before.nlink !== 1n || (before.mode & 0o7777n) !== 0o600n) fail('BACKUP_JOURNAL_INVALID');
    const fd = fs.openSync(filename, fs.constants.O_RDONLY | fs.constants.O_NOFOLLOW | fs.constants.O_NONBLOCK);
    descriptors.push(fd);
    if (!same(before, fs.fstatSync(fd, {bigint: true}))) fail('BACKUP_JOURNAL_INVALID');
    const hash = crypto.createHash('sha256'), buffer = Buffer.allocUnsafe(1024 * 1024);
    let remaining = before.size;
    while (remaining > 0n) {
      const length = remaining > BigInt(buffer.length) ? buffer.length : Number(remaining), count = fs.readSync(fd, buffer, 0, length, null);
      if (!count) fail('BACKUP_JOURNAL_INVALID');
      remaining -= BigInt(count); hash.update(buffer.subarray(0, count));
    }
    if (fs.readSync(fd, buffer, 0, 1, null) || !same(before, fs.fstatSync(fd, {bigint: true})) || !same(before, fs.lstatSync(filename, {bigint: true}))) fail('BACKUP_JOURNAL_INVALID');
    assertNoSymlinkAncestors(originalPoint);
    for (let index = 0; index < directories.length; index++) {
      if (!same(beforeDirectories[index], fs.fstatSync(descriptors[index], {bigint: true})) || !same(beforeDirectories[index], fs.lstatSync(directories[index], {bigint: true}))) fail('BACKUP_JOURNAL_INVALID');
    }
    if (hash.digest('hex') !== journal.sha256) fail('BACKUP_JOURNAL_HASH_MISMATCH');
  } catch (error) {failure = Object.assign(new Error(error.code === 'BACKUP_JOURNAL_HASH_MISMATCH' ? error.code : 'BACKUP_JOURNAL_INVALID'), {code: error.code === 'BACKUP_JOURNAL_HASH_MISMATCH' ? error.code : 'BACKUP_JOURNAL_INVALID'});}
  finally {for (const fd of descriptors.reverse()) {try {fs.closeSync(fd);} catch {failure ??= Object.assign(new Error('BACKUP_JOURNAL_INVALID'), {code: 'BACKUP_JOURNAL_INVALID'});}}}
  if (failure) throw failure;
}
function log(repository, action, status, code, details = {}, options = {}, snapshotJournal) {
  if (options.logFailureCode) fail(options.logFailureCode);
  let descriptor;
  try {
  const dir = snapshotJournal ? snapshotLogDirectory(snapshotJournal, true) : path.join(repository.repositoryRoot, 'logs');
  assertNoSymlinkAncestors(dir);
  if (fs.existsSync(dir) && (!fs.lstatSync(dir).isDirectory() || fs.lstatSync(dir).isSymbolicLink())) fail('LOG_DIRECTORY_INVALID');
  fs.mkdirSync(dir, {recursive: true});
  const parentBefore = fs.lstatSync(dir);
  const target = path.join(dir, 'git-safety.jsonl');
  const before = fs.lstatSync(target, {throwIfNoEntry: false});
  if (before && (!before.isFile() || before.isSymbolicLink() || before.nlink !== 1)) fail('LOG_FILE_INVALID');
  if (snapshotJournal && (before && ((before.mode & 0o7777) !== 0o600 || !snapshotJournal.fileIdentity || before.dev !== snapshotJournal.fileIdentity.dev || before.ino !== snapshotJournal.fileIdentity.ino))) fail('LOG_FILE_INVALID');
  const version = output(command(selectGitPath(options), ['--version']));
  const head = output(git(repository.repositoryRoot, ['rev-parse', 'HEAD'], options, {allowFailure: true}));
  const flags = fs.constants.O_WRONLY | fs.constants.O_APPEND | fs.constants.O_NOFOLLOW | (before ? 0 : fs.constants.O_CREAT | fs.constants.O_EXCL);
  try { descriptor = fs.openSync(target, flags, 0o600); } catch { fail('LOG_FILE_INVALID'); }
  const opened = fs.fstatSync(descriptor);
  assertNoSymlinkAncestors(dir);
  const parentAfter = fs.lstatSync(dir);
  const current = fs.lstatSync(target, {throwIfNoEntry: false});
  if (!opened.isFile() || opened.nlink !== 1 || (typeof process.getuid === 'function' && (opened.uid !== process.getuid() || parentAfter.uid !== process.getuid())) || !current || current.isSymbolicLink() || current.nlink !== 1 || current.ino !== opened.ino || current.dev !== opened.dev || before && (opened.ino !== before.ino || opened.dev !== before.dev) || parentBefore.ino !== parentAfter.ino || parentBefore.dev !== parentAfter.dev || parentAfter.isSymbolicLink()) fail('LOG_FILE_INVALID');
  if (snapshotJournal) {snapshotLogDirectory(snapshotJournal); if ((opened.mode & 0o7777) !== 0o600) fail('LOG_FILE_INVALID');}
  fs.writeSync(descriptor, JSON.stringify({time: new Date().toISOString(), action, status, gitPath: selectGitPath(options), gitVersion: /^git version [\w .()+-]+$/.test(version) ? version : 'UNKNOWN', head: /^[a-f0-9]{40,64}$/.test(head) ? head : null, durationMs: Math.max(0, Date.now() - (options.startedAt ?? Date.now())), ...details, ...(code ? {code} : {})}) + '\n');
  if (snapshotJournal) {fs.fsyncSync(descriptor); snapshotJournal.fileIdentity = opened;}
  } catch (error) { options.logFailureCode = error.code ?? 'LOG_FILE_INVALID'; throw error; }
  finally { if (descriptor !== undefined) fs.closeSync(descriptor); }
}
function nativeLocks(repository) {
  const found = [];
  function walk(directory) {
    if (!fs.existsSync(directory)) return;
    for (const item of fs.readdirSync(directory, {withFileTypes: true})) {
      if (item.isSymbolicLink()) continue;
      const name = path.join(directory, item.name);
      if (item.isDirectory()) walk(name);
      else if (item.name.endsWith('.lock')) found.push(path.relative(repository.commonDirectory, name));
    }
  }
  for (const name of ['index.lock', 'HEAD.lock', 'ORIG_HEAD.lock', 'FETCH_HEAD.lock', 'MERGE_HEAD.lock', 'AUTO_MERGE.lock', 'config.lock', 'config.worktree.lock', 'packed-refs.lock', 'shallow.lock', 'gc.pid']) {
    if (fs.existsSync(path.join(repository.commonDirectory, name))) found.push(name);
  }
  for (const name of ['refs', 'worktrees', 'objects']) walk(path.join(repository.commonDirectory, name));
  return [...new Set(found)].sort();
}
function assertNativeUnlocked(repository) { if (nativeLocks(repository).length) fail('NATIVE_LOCKED'); }
function fsck(repository, options) {
  const result=git(repository.repositoryRoot, ['fsck', '--full', '--no-reflogs'], options, {allowFailure: true});
  if(result.status!==0)throw Object.assign(new Error('OBJECT_INTEGRITY_FAILED'),{code:'OBJECT_INTEGRITY_FAILED',integrity:{exitCode:result.status,signal:result.signal??null,stdoutBytes:result.stdout.length,stderrBytes:result.stderr.length,stdoutSha256:sha256(result.stdout),stderrSha256:sha256(result.stderr)}});
}
export function checkRepository({projectRoot}, options = {}) {
  const repository = discover(projectRoot, options);
  fsck(repository, options);
  return {...repository, gitPath: selectGitPath(options), fsck: 'PASS', nativeLocks: nativeLocks(repository), repositoryLocked: fs.existsSync(path.join(state(repository), 'repository.lock')),
    config: Object.fromEntries(['gc.auto', 'maintenance.auto'].map(key => [key, configValues(repository, key, options)]))};
}
function configValues(repository, key, options) {
  const result = git(repository.repositoryRoot, ['config', '--local', '--get-all', key], options, {allowFailure: true});
  if (result.status === 1) return null;
  if (result.status !== 0) fail('CONFIG_READ_FAILED');
  return result.stdout.toString('utf8').replace(/\n$/, '').split('\n');
}
export function withRepositoryLock({projectRoot}, callback, options = {}) {
  const repository = discover(projectRoot, options);
  assertRepositoryIdentity(repository, options);
  assertNativeUnlocked(repository);
  assertNoSymlinkAncestors(state(repository));
  privateDirectory(state(repository));
  const target = path.join(state(repository), 'repository.lock');
  let fd;
  try { fd = fs.openSync(target, 'wx', 0o600); }
  catch (error) { if (error.code === 'EEXIST') fail('REPOSITORY_LOCKED'); throw error; }
  const nonce = crypto.randomUUID();
  fs.writeFileSync(fd, JSON.stringify({pid: process.pid, nonce}));
  const owned = fs.fstatSync(fd);
  let held=true;
  const assertHeld = () => {
    const current = fs.lstatSync(target, {throwIfNoEntry: false});
    if (!held || !current?.isFile() || current.isSymbolicLink() || current.nlink!==1 || current.ino !== owned.ino || current.dev !== owned.dev) fail('LOCK_OWNERSHIP_CHANGED');
    let record;
    try { record = JSON.parse(fs.readFileSync(target, 'utf8')); } catch { fail('LOCK_OWNERSHIP_CHANGED'); }
    if (record.nonce !== nonce || record.pid !== process.pid) fail('LOCK_OWNERSHIP_CHANGED');
  };
  Object.defineProperty(repository,'assertLockOwned',{value:assertHeld});
  const release = () => {
    try {assertHeld();fs.unlinkSync(target);} finally {held=false;fs.closeSync(fd);}
  };
  let result;
  try { result = callback(repository); }
  catch (error) { release(); throw error; }
  if (result && typeof result.then === 'function') return Promise.resolve(result).finally(release);
  release();
  return result;
}
export function configureRepository({projectRoot}, options = {}) {
  options = {...options, startedAt: Date.now()};
  selectGitPath({...options, mutate: true});
  return withRepositoryLock({projectRoot}, repository => {
    const previous = Object.fromEntries(['gc.auto', 'maintenance.auto'].map(key => [key, configValues(repository, key, options)]));
    const backupRoot = options.backupRoot ?? path.join(os.homedir(), '.codex/backups/rwb-git-safety');
    assertNoSymlinkAncestors(backupRoot);
    const backup = path.join(backupRoot, `config-before-${crypto.randomUUID()}.json`);
    privateWrite(backup, JSON.stringify({schemaVersion: 1, previous}) + '\n');
    const changed = [];
    try {
      changed.push(['gc.auto', '0']);
      git(projectRoot, ['config', '--local', '--replace-all', 'gc.auto', '0'], options);
      changed.push(['maintenance.auto', 'false']);
      git(projectRoot, ['config', '--local', '--replace-all', 'maintenance.auto', 'false'], options);
      log(repository, 'configure', 'PASS', undefined, {backup}, options);
      return {configured: true, backup, previous};
    } catch (error) {
      try {
        for (const [key, value] of changed.reverse()) {
          const current = configValues(repository, key, options);
          if (JSON.stringify(current) === JSON.stringify(previous[key])) continue;
          if (JSON.stringify(current) !== JSON.stringify([value])) fail('CONFIG_ROLLBACK_CONFLICT');
          const removed = git(projectRoot, ['config', '--local', '--unset-all', key], options, {allowFailure: true});
          if (removed.status !== 0) fail('CONFIG_ROLLBACK_FAILED');
          for (const prior of previous[key] ?? []) git(projectRoot, ['config', '--local', '--add', key, prior], options);
        }
      } catch (rollbackError) {
        log(repository, 'configure', 'FAIL', rollbackError.code ?? 'CONFIG_ROLLBACK_FAILED', {backup, rolledBack: false}, options);
        throw rollbackError;
      }
      log(repository, 'configure', 'FAIL', error.code ?? 'CONFIGURE_FAILED', {backup, rolledBack: true}, options);
      throw error;
    }
  }, options);
}
function worktrees(repository, options) {
  const raw = git(repository.repositoryRoot, ['worktree', 'list', '--porcelain', '-z'], options).stdout.toString('utf8');
  return raw.split('\0\0').filter(Boolean).map(block => Object.fromEntries(block.split('\0').filter(Boolean).map(line => {
    const offset = line.indexOf(' ');
    return offset < 0 ? [line, true] : [line.slice(0, offset), line.slice(offset + 1)];
  })));
}
function refs(repository, options) {
  return Object.fromEntries(output(git(repository.repositoryRoot, ['for-each-ref', '--format=%(refname) %(objectname)'], options)).split('\n').filter(Boolean).map(line => line.split(' ')));
}
function paths(project, args, options) { return git(project, args, options).stdout.toString('utf8').split('\0').filter(Boolean); }
function sensitive(name) {
  return name.split('/').some(part => /^\.env/i.test(part) || /^(?:\.netrc|\.npmrc|\.pypirc|\.ssh|\.aws|id_rsa|id_ed25519)$/i.test(part) || /^(?:credentials?|secrets?|passwords?|tokens?|private[-_]?keys?|api[-_]?keys?)(?:\.(?:json|ya?ml|toml|ini|conf|txt))?$/i.test(part) || /\.(?:pem|key|p12|pfx|keystore)$/i.test(part));
}
function fileRecord(project, name) {
  const target = path.join(project, name);
  if (!fs.existsSync(target) && !fs.lstatSync(target, {throwIfNoEntry: false})) return {path: name, type: 'missing'};
  const stat = fs.lstatSync(target);
  if (stat.isSymbolicLink()) return {path: name, type: 'symlink', link: fs.readlinkSync(target), sha256: sha256(fs.readlinkSync(target))};
  if (!stat.isFile()) fail('UNSUPPORTED_FILE_TYPE');
  return {path: name, type: 'file', mode: stat.mode & 0o777, sha256: hashFile(target)};
}
function capture(repository, options) {
  const registeredWorktrees = worktrees(repository, options);
  const requested = [...new Set(options.worktreePaths ?? [repository.repositoryRoot])].map(value => fs.realpathSync(value));
  const entries = requested.map(value => {
    const entry = registeredWorktrees.find(item => item.worktree === value);
    if (!entry || entry.bare || discover(value, options).commonDirectory !== repository.commonDirectory) fail('BACKUP_WORKTREE_MISMATCH');
    return entry;
  });
  // Detect secret-shaped paths for every worktree before reading or exporting file contents.
  const lists = entries.map(entry => {
    if (!fs.existsSync(entry.worktree) || entry.prunable) fail('WORKTREE_UNAVAILABLE');
    const untracked = paths(entry.worktree, ['ls-files', '--others', '--exclude-standard', '-z'], options);
    if (untracked.some(sensitive)) fail('SENSITIVE_UNTRACKED');
    return {entry, untracked};
  });
  return {refs: refs(repository, options), registeredWorktrees, worktrees: lists.map(({entry, untracked}) => ({
    path: entry.worktree, head: entry.HEAD, branch: entry.branch ?? null,
    index: sha256(git(entry.worktree, ['ls-files', '--stage', '-z'], options).stdout),
    staged: sha256(git(entry.worktree, ['diff', '--cached', '--binary', '--full-index', 'HEAD', '--'], options).stdout),
    unstaged: sha256(git(entry.worktree, ['diff', '--binary', '--full-index', '--'], options).stdout),
    tracked: [...new Set(paths(entry.worktree, ['ls-files', '--cached', '-z'], options))].sort().map(name => fileRecord(entry.worktree, name)),
    untracked: untracked.sort().map(name => fileRecord(entry.worktree, name))
  }))};
}
function targetFootprint(captured) {
  return {worktrees: captured.worktrees, branchRefs: Object.fromEntries(captured.worktrees.filter(item => item.branch).map(item => [item.branch, captured.refs[item.branch] ?? null]))};
}
function saveArtifact(directory, relative, bytes, manifest) {
  privateWrite(path.join(directory, relative), bytes);
  manifest.files.push({path: relative, sha256: sha256(bytes)});
}
function copyDescriptors(sourceFd, targetFd, maximumBytes) {
  const digest = crypto.createHash('sha256');
  const buffer = Buffer.allocUnsafe(1024 * 1024);
  let count, copied = 0n;
  while (true) {
    // Snapshot stream writes cannot exceed their admitted pinned size, even if
    // a concurrent writer grows the source before the final race check.
    const remaining = maximumBytes === undefined ? undefined : maximumBytes - copied;
    const length = remaining === undefined || remaining >= BigInt(buffer.length) ? buffer.length : Number(remaining);
    if (length === 0) {
      if (fs.readSync(sourceFd, buffer, 0, 1, null)) fail('BACKUP_RACE');
      break;
    }
    count = fs.readSync(sourceFd, buffer, 0, length, null);
    if (!count) break;
    digest.update(buffer.subarray(0, count));
    let written = 0;
    while (written < count) {
      const size = fs.writeSync(targetFd, buffer, written, count - written, null);
      if (size <= 0) fail('BACKUP_WRITE_FAILED');
      written += size;
    }
    copied += BigInt(count);
  }
  if (maximumBytes !== undefined && copied !== maximumBytes) fail('BACKUP_RACE');
  return digest.digest('hex');
}
function trustedRuntimePath(candidate, executable = false) {
  try {
    if (!path.isAbsolute(candidate) || typeof process.getuid !== 'function') return undefined;
    const resolved = fs.realpathSync(candidate), owner = process.getuid();
    const trusted = value => (value.uid === 0 || value.uid === owner) && !(value.mode & 0o022);
    const file = fs.statSync(resolved);
    if (!file.isFile() || !trusted(file) || executable && !(file.mode & 0o111)) return undefined;
    // Check both the selected path and its resolved target: symlinks may only
    // lead through directories that another user cannot replace or modify.
    for (const start of [path.dirname(candidate), path.dirname(resolved)]) {
      for (let current = start;; current = path.dirname(current)) {
        const value = fs.statSync(current);
        if (!value.isDirectory() || !trusted(value)) return undefined;
        if (current === path.dirname(current)) break;
      }
    }
    if (executable) fs.accessSync(resolved, fs.constants.X_OK);
    return resolved;
  } catch {return undefined;}
}
/** Static reuse of the existing resource-phase Python selection policy. No
 * interpreter probe/which, new setting, CLI override, or PATH execution occurs.
 * Missing/untrusted optional optimization leaves the original stream eligible.
 */
export function resolveSnapshotPython(sourceRoot, {searchPath = process.env.PATH ?? ''} = {}) {
  const venv = path.join(sourceRoot, '.venv');
  if (trustedRuntimePath(path.join(venv, 'pyvenv.cfg'))) {
    const python = trustedRuntimePath(path.join(venv, 'bin/python'), true);
    if (python) return python;
  }
  for (const entry of searchPath.split(path.delimiter)) {
    if (!entry || !path.isAbsolute(entry)) continue;
    const python = trustedRuntimePath(path.join(entry, 'python3.12'), true);
    if (python) return python;
  }
  return undefined;
}
/** Internal direct-test seam; production callers provide only the event sink.
 * This admits one known stream file, never the complete backup/restore peak.
 */
export function snapshotRegularFile(sourceRoot, item, directory, relative, manifest, context = {}) {
  const source = path.resolve(sourceRoot, item.path);
  if (!source.startsWith(path.resolve(sourceRoot) + path.sep) || item.type !== 'file') fail('BACKUP_RACE');
  assertNoSymlinkAncestors(path.dirname(source));
  const before = fs.lstatSync(source, {throwIfNoEntry: false});
  if (!before?.isFile() || before.isSymbolicLink() || (before.mode & 0o777) !== item.mode) fail('BACKUP_RACE');
  let sourceFd, targetFd, directoryFd;
  try {
    try { sourceFd = fs.openSync(source, fs.constants.O_RDONLY | fs.constants.O_NOFOLLOW); } catch { fail('BACKUP_RACE'); }
    const opened = fs.fstatSync(sourceFd);
    if (!opened.isFile() || opened.ino !== before.ino || opened.dev !== before.dev || opened.uid !== before.uid) fail('BACKUP_RACE');
    const expectedSource = sourceFacts(sourceFd);
    const target = path.resolve(directory, relative), targetDirectory = path.dirname(target);
    if (!target.startsWith(path.resolve(directory) + path.sep)) fail('BACKUP_RACE');
    privateDirectory(targetDirectory);
    assertNoSymlinkAncestors(targetDirectory);
    directoryFd = fs.openSync(targetDirectory, fs.constants.O_RDONLY | fs.constants.O_NOFOLLOW);
    const pinnedDirectory = fs.fstatSync(directoryFd);
    const checkDirectory = () => {
      assertNoSymlinkAncestors(targetDirectory);
      const current = fs.lstatSync(targetDirectory), actual = fs.fstatSync(directoryFd);
      if (!actual.isDirectory() || current.isSymbolicLink() || actual.dev !== pinnedDirectory.dev || actual.ino !== pinnedDirectory.ino || current.dev !== actual.dev || current.ino !== actual.ino || (actual.mode & 0o7777) !== 0o700 || actual.uid !== process.getuid()) fail('BACKUP_RACE');
    };
    const checkSource = () => {
      const current = fs.lstatSync(source, {throwIfNoEntry: false});
      assertNoSymlinkAncestors(path.dirname(source));
      if (!current?.isFile() || current.isSymbolicLink() || current.ino !== opened.ino || current.dev !== opened.dev || current.uid !== opened.uid || JSON.stringify(sourceFacts(sourceFd)) !== JSON.stringify(expectedSource)) fail('BACKUP_RACE');
    };
    checkDirectory();
    if (fs.lstatSync(target, {throwIfNoEntry: false})) fail('BACKUP_TARGET_EXISTS');
    let runtimeProfile = 'generic-strict';
    const onEvent = event => (context.onEvent ?? (() => {}))({phase: 'snapshot-clone', ...(event.event === 'backup_fd_clone' ? {runtimeProfile, executableScope: 'selected-executable-reference'} : {}), ...event});
    const eligible = process.platform === 'darwin' && opened.nlink === 1 && opened.uid === process.getuid() && !(opened.mode & 0o7000) && BigInt(expectedSource.size) <= BigInt(Number.MAX_SAFE_INTEGER);
    let pythonPath = eligible ? (context.resolvePython ?? resolveSnapshotPython)(sourceRoot) : undefined;
    const inherited = eligible && !pythonPath ? context[snapshotToolchainKey]?.() : undefined;
    if (inherited) {
      runtimeProfile = 'existing-resource-phase-tcb';
      if (inherited.check(false) === 'available') pythonPath = inherited.lexicalPath;
    }
    let outcome;
    if (pythonPath) {
      let spawnVetoed = false;
      const beforeSpawn = inherited ? () => {
        // The primitive calls this only after its full source hash, immediately
        // before spawn. A refused/unavailable check means no helper ran.
        spawnVetoed = true;
        if (inherited.check(false) !== 'available') return false;
        spawnVetoed = false;
        return true;
      } : undefined;
      try {outcome = (context.clone ?? clonePinnedFile)({sourceFd, directoryFd, destinationDirectory: targetDirectory, destinationName: path.basename(target), expectedSource, expectedSha256: item.sha256, pythonPath, beforeSpawn, onEvent});}
      catch {outcome = {status: 'unknown', code: 'CLONE_HELPER_UNVERIFIED'}; onEvent({event: 'backup_fd_clone', ...outcome});}
      finally {
        if (inherited && !spawnVetoed && inherited.check(true) !== 'available') {
          outcome = {status: 'unknown', code: 'CLONE_TOOLCHAIN_CHANGED'};
          onEvent({event: 'backup_fd_clone', ...outcome});
        }
      }
    }
    else {
      outcome = {status: 'unsupported', code: inherited ? 'CLONE_TOOLCHAIN_UNAVAILABLE' : eligible ? 'CLONE_PYTHON_UNAVAILABLE' : 'CLONE_SOURCE_INELIGIBLE'};
      onEvent({event: 'backup_fd_clone', ...outcome});
    }
    if (!outcome || !['cloned', 'unsupported', 'error', 'unknown'].includes(outcome.status)) fail('CLONE_HELPER_UNVERIFIED');
    if (outcome.status === 'error' || outcome.status === 'unknown') fail(/^CLONE_[A-Z_]+$/.test(outcome.code ?? '') ? outcome.code : 'CLONE_HELPER_UNVERIFIED');
    checkDirectory(); checkSource();
    let hash;
    if (outcome.status === 'cloned') {
      if (outcome.sha256 !== item.sha256) fail('CLONE_HELPER_UNVERIFIED');
      hash = outcome.sha256;
    } else {
      // Unsupported is not permission to overwrite an uncertain helper effect.
      if (fs.lstatSync(target, {throwIfNoEntry: false})) fail('BACKUP_TARGET_EXISTS');
      admitFileStream({directory: targetDirectory, fileBytes: BigInt(expectedSource.size), measure: context.measure, onEvent});
      checkDirectory(); checkSource();
      targetFd = fs.openSync(target, fs.constants.O_WRONLY | fs.constants.O_CREAT | fs.constants.O_EXCL | fs.constants.O_NOFOLLOW, 0o600);
      const pinnedTarget = fs.fstatSync(targetFd);
      checkDirectory(); checkSource();
      hash = copyDescriptors(sourceFd, targetFd, BigInt(expectedSource.size));
      fs.fsyncSync(targetFd); fs.fsyncSync(directoryFd);
      const actual = fs.fstatSync(targetFd), current = fs.lstatSync(target, {throwIfNoEntry: false});
      if (!actual.isFile() || actual.nlink !== 1 || actual.uid !== process.getuid() || (actual.mode & 0o7777) !== 0o600 || actual.dev !== pinnedTarget.dev || actual.ino !== pinnedTarget.ino || !current?.isFile() || current.isSymbolicLink() || current.dev !== actual.dev || current.ino !== actual.ino || current.nlink !== 1) fail('BACKUP_RACE');
    }
    const after = fs.fstatSync(sourceFd);
    const current = fs.lstatSync(source, {throwIfNoEntry: false});
    assertNoSymlinkAncestors(path.dirname(source));
    if (hash !== item.sha256 || !current?.isFile() || current.isSymbolicLink() || current.ino !== opened.ino || current.dev !== opened.dev || current.uid !== opened.uid || after.size !== before.size || after.mtimeMs !== before.mtimeMs || after.ctimeMs !== before.ctimeMs || after.nlink !== before.nlink || (after.mode & 0o777) !== item.mode) fail('BACKUP_RACE');
    checkDirectory(); checkSource();
    manifest.files.push({path: relative, sha256: hash});
  } finally { if (sourceFd !== undefined) fs.closeSync(sourceFd); if (targetFd !== undefined) fs.closeSync(targetFd); if (directoryFd !== undefined) fs.closeSync(directoryFd); }
}
function restoreFileMode(scratch, restored, item, rawArtifact) {
  const target = path.resolve(restored, item.path);
  const scope = path.resolve(scratch) + path.sep;
  if (item.type !== 'file' || !target.startsWith(scope) || !target.startsWith(path.resolve(restored) + path.sep) || !Number.isInteger(item.mode) || item.mode < 0 || item.mode > 0o777) fail('RESTORE_FILE_INVALID');
  assertNoSymlinkAncestors(path.dirname(target));
  const before = fs.lstatSync(target, {throwIfNoEntry: false});
  if (!before?.isFile() || before.isSymbolicLink() || before.nlink !== 1 || (typeof process.getuid === 'function' && before.uid !== process.getuid())) fail('RESTORE_FILE_INVALID');
  let fd;
  try {
    try { fd = fs.openSync(target, (rawArtifact ? fs.constants.O_RDWR : fs.constants.O_RDONLY) | fs.constants.O_NOFOLLOW); } catch { fail('RESTORE_FILE_INVALID'); }
    const opened = fs.fstatSync(fd);
    const current = fs.lstatSync(target, {throwIfNoEntry: false});
    assertNoSymlinkAncestors(path.dirname(target));
    if (!opened.isFile() || opened.nlink !== 1 || opened.ino !== before.ino || opened.dev !== before.dev || opened.uid !== before.uid || !current || current.isSymbolicLink() || current.nlink !== 1 || current.ino !== opened.ino || current.dev !== opened.dev) fail('RESTORE_FILE_INVALID');
    if (rawArtifact) {
      assertNoSymlinkAncestors(path.dirname(rawArtifact));
      const artifact = fs.lstatSync(rawArtifact, {throwIfNoEntry: false});
      if (!artifact?.isFile() || artifact.isSymbolicLink() || artifact.nlink !== 1 || (typeof process.getuid === 'function' && artifact.uid !== process.getuid())) fail('BACKUP_HASH_MISMATCH');
      let sourceFd;
      try {
        sourceFd = fs.openSync(rawArtifact, fs.constants.O_RDONLY | fs.constants.O_NOFOLLOW);
        const actual = fs.fstatSync(sourceFd);
        if (actual.ino !== artifact.ino || actual.dev !== artifact.dev || actual.nlink !== 1) fail('BACKUP_HASH_MISMATCH');
        fs.ftruncateSync(fd, 0);
        if (copyDescriptors(sourceFd, fd) !== item.sha256) fail('BACKUP_HASH_MISMATCH');
      } finally { if (sourceFd !== undefined) fs.closeSync(sourceFd); }
    }
    fs.fchmodSync(fd, item.mode);
    const after = fs.fstatSync(fd);
    const afterPath = fs.lstatSync(target, {throwIfNoEntry: false});
    assertNoSymlinkAncestors(path.dirname(target));
    if (after.nlink !== 1 || (after.mode & 0o777) !== item.mode || !afterPath || afterPath.isSymbolicLink() || afterPath.nlink !== 1 || afterPath.ino !== after.ino || afterPath.dev !== after.dev) fail('RESTORE_FILE_INVALID');
  } finally { if (fd !== undefined) fs.closeSync(fd); }
}
function restoreBackup(directory, manifest, options, storedDirectory = directory) {
  verifySnapshotJournal(storedDirectory, manifest);
  const scratch = fs.mkdtempSync(path.join(directory, '.restore-'));
  const bare = path.join(scratch, 'restored.git');
  try {
    command(selectGitPath(options), ['-c', 'gc.auto=0', '-c', 'maintenance.auto=false', 'init', '--bare', bare]);
    if(manifest.schemaVersion===2) hydrateV2(storedDirectory,manifest,bare);
    else {
      if(!manifest.objectOnly) {
        git(bare, ['bundle', 'verify', path.join(directory, 'commits.bundle')], options);
        git(bare, ['bundle', 'unbundle', path.join(directory, 'commits.bundle')], options);
      }
      const packFd = fs.openSync(path.join(directory, 'objects.pack'), 'r');
      try { git(bare, ['index-pack', '--stdin'], options, {inputFd: packFd}); }
      finally { fs.closeSync(packFd); }
    }
    for (const [ref, oid] of Object.entries(manifest.refs)) git(bare, ['update-ref', ref, oid], options);
    for (let index = 0; index < manifest.worktrees.length; index++) {
      const saved = manifest.worktrees[index];
      const restored = path.join(scratch, `worktree-${index}`);
      git(bare, ['worktree', 'add', '--detach', restored, saved.head], options);
      for (const [kind, args] of [['staged', ['--index']], ['unstaged', []]]) {
        const patch = fs.readFileSync(path.join(directory, `worktrees/${index}/${kind}.patch`));
        if (patch.length) git(restored, ['apply', ...args, '--binary', '-'], options, {input: patch});
      }
      for (let itemIndex = 0; itemIndex < saved.untracked.length; itemIndex++) {
        const item = saved.untracked[itemIndex];
        const target = path.join(restored, item.path);
        if(!target.startsWith(restored+path.sep))fail('RESTORE_FILE_INVALID');
        assertNoSymlinkAncestors(path.dirname(target));
        fs.mkdirSync(path.dirname(target), {recursive: true, mode: 0o700});
        if (item.type === 'symlink') fs.symlinkSync(item.link, target);
        else { fs.copyFileSync(path.join(directory, `worktrees/${index}/untracked/${itemIndex}`), target); restoreFileMode(scratch, restored, item); }
      }
      saved.tracked.forEach((item, itemIndex) => { if (item.type === 'file') restoreFileMode(scratch, restored, item, path.join(directory, `worktrees/${index}/tracked/${itemIndex}`)); });
      const actualTracked = saved.tracked.map(item => fileRecord(restored, item.path));
      const actualUntracked = saved.untracked.map(item => fileRecord(restored, item.path));
      if (JSON.stringify(actualTracked) !== JSON.stringify(saved.tracked) || JSON.stringify(actualUntracked) !== JSON.stringify(saved.untracked)) fail('RESTORE_HASH_MISMATCH');
      if (saved.index!==undefined && sha256(git(restored, ['ls-files', '--stage', '-z'], options).stdout) !== saved.index) fail('RESTORE_INDEX_MISMATCH');
      if (sha256(git(restored, ['diff', '--cached', '--binary', '--full-index', 'HEAD', '--'], options).stdout) !== saved.staged || sha256(git(restored, ['diff', '--binary', '--full-index', '--'], options).stdout) !== saved.unstaged) fail('RESTORE_PATCH_MISMATCH');
    }
    if (git(bare, ['fsck', '--full', '--no-reflogs'], options, {allowFailure: true}).status !== 0) fail('RESTORE_FSCK_FAILED');
    for (const [ref, oid] of Object.entries(manifest.refs)) if (output(git(bare, ['rev-parse', ref], options)) !== oid) fail('RESTORE_REF_MISMATCH');
    const anchors = [...new Set([...Object.values(manifest.preservationRefs),...Object.values(manifest.additionalBundleRefs??{})])];
    for (const oid of anchors) if (git(bare, ['cat-file', '-e', oid], options, {allowFailure: true}).status !== 0) fail('RESTORE_REF_MISMATCH');
    if (anchors.length && git(bare, ['fsck', '--connectivity-only', '--no-reflogs', ...anchors], options, {allowFailure: true}).status !== 0) fail('RESTORE_FSCK_FAILED');
    for (const item of manifest.files) if (hashFile(path.join(directory, item.path)) !== item.sha256) fail('BACKUP_HASH_MISMATCH');
    verifySnapshotJournal(storedDirectory, manifest);
  } finally { fs.rmSync(scratch, {recursive: true, force: true}); }
}
function backupLegacyUnlocked(repository, options) {
  assertNativeUnlocked(repository);
  fsck(repository, options);
  const before = capture(repository, options);
  const backupRoot = options.backupRoot ?? path.join(os.homedir(), '.codex/backups/rwb-git-safety');
  const root = path.resolve(backupRoot);
  assertNoSymlinkAncestors(root);
  if (root === repository.commonDirectory || root.startsWith(repository.commonDirectory + path.sep)) fail('BACKUP_ROOT_INVALID');
  privateDirectory(root);
  const directory = path.join(root, crypto.randomUUID());
  privateDirectory(directory);
  const snapshotJournal = {root: directory, rootIdentity: fs.lstatSync(directory), sealed: false};
  const preservationRefs = {...(options.preservationRefs ?? {})};
  if (Object.entries(preservationRefs).some(([ref, oid]) => !ref.startsWith('refs/') || !/^[a-f0-9]{40,64}$/.test(oid))) fail('PRESERVATION_REFS_INVALID');
  const manifest = {schemaVersion: 1, metadataSemantics: 'as-of-capture', restoreVerified: false, ...(options.stageV2 ? {objectOnly:true,createdAt:new Date(options.now??Date.now()).toISOString()} : {}), preservationRefs, refs: before.refs, registeredWorktrees: before.registeredWorktrees, worktrees: before.worktrees, files: []};
  try {
    if(!options.stageV2) {
      git(repository.repositoryRoot, ['bundle', 'create', path.join(directory, 'commits.bundle'), '--all', ...before.worktrees.map(item => item.head)], options);
      fs.chmodSync(path.join(directory, 'commits.bundle'), 0o600);
      manifest.files.push({path: 'commits.bundle', sha256: hashFile(path.join(directory, 'commits.bundle'))});
    }
    const oids = [...new Set([...Object.values(before.refs), ...Object.values(preservationRefs), ...before.registeredWorktrees.map(item => item.HEAD).filter(Boolean)])];
    const packFile = path.join(directory, 'objects.pack');
    const packFd = fs.openSync(packFile, 'wx', 0o600);
    try {
      const result = spawnSync(selectGitPath(options), ['-c', 'gc.auto=0', '-c', 'maintenance.auto=false', '-C', repository.repositoryRoot, 'pack-objects', '--stdout', '--revs'], {input: oids.join('\n') + '\n', stdio: ['pipe', packFd, 'pipe']});
      if (result.error || result.status !== 0) fail('PACK_EXPORT_FAILED');
    } finally { fs.closeSync(packFd); }
    manifest.files.push({path: 'objects.pack', sha256: hashFile(packFile)});
    for (let index = 0; index < before.worktrees.length; index++) {
      const item = before.worktrees[index];
      saveArtifact(directory, `worktrees/${index}/staged.patch`, git(item.path, ['diff', '--cached', '--binary', '--full-index', 'HEAD', '--'], options).stdout, manifest);
      saveArtifact(directory, `worktrees/${index}/unstaged.patch`, git(item.path, ['diff', '--binary', '--full-index', '--'], options).stdout, manifest);
      const snapshotContext = {onEvent: event => log(repository, 'backup-snapshot', event.status, event.code, event, options, snapshotJournal), [snapshotToolchainKey]: () => inheritedSnapshotToolchain(repository)};
      item.tracked.forEach((file, itemIndex) => { if (file.type === 'file') snapshotRegularFile(item.path, file, directory, `worktrees/${index}/tracked/${itemIndex}`, manifest, snapshotContext); });
      item.untracked.forEach((file, itemIndex) => { if (file.type === 'file') snapshotRegularFile(item.path, file, directory, `worktrees/${index}/untracked/${itemIndex}`, manifest, snapshotContext); });
    }
    sealSnapshotLog(snapshotJournal, manifest);
    saveArtifact(directory, 'manifest-draft.json', JSON.stringify(manifest, null, 2) + '\n', {files: []});
    if (JSON.stringify(targetFootprint(capture(repository, options))) !== JSON.stringify(targetFootprint(before))) fail('BACKUP_RACE');
    restoreBackup(directory, manifest, options);
    if (JSON.stringify(targetFootprint(capture(repository, options))) !== JSON.stringify(targetFootprint(before))) fail('BACKUP_RACE');
    manifest.restoreVerified = true;
    saveArtifact(directory, 'manifest.json', JSON.stringify(manifest, null, 2) + '\n', {files: []});
    log(repository, 'backup', 'PASS', undefined, {backup: directory}, options);
    const result = {directory, restoreVerified: true, fsck: 'PASS', snapshotRefs: Object.fromEntries(Object.entries(before.refs).filter(([ref]) => ref.startsWith('refs/codex/')))};
    Object.defineProperty(result, 'verifiedPreservationRefs', {value: preservationRefs});
    return result;
  } catch (error) {
    // Failed evidence is retained privately; it is never certified or used for cleanup.
    if (!fs.existsSync(path.join(directory, 'manifest-draft.json'))) saveArtifact(directory, 'manifest-draft.json', JSON.stringify({...manifest, restoreVerified: false}, null, 2) + '\n', {files: []});
    saveArtifact(directory, 'failure-status.json', JSON.stringify({schemaVersion: 1, status: 'FAIL', restoreVerified: false, code: error.code ?? 'BACKUP_FAILED', failedAt: new Date().toISOString()}) + '\n', {files: []});
    log(repository, 'backup', 'FAIL', error.code ?? 'BACKUP_FAILED', {backup: directory}, options);
    throw error;
  }
}
export function verifyBackupDirectory(directory, options = {}) {
  const {manifest}=readManifest(directory);
  verifySnapshotJournal(directory, manifest);
  for(const row of manifest.files) {
    if(typeof row.path!=='string' || path.isAbsolute(row.path) || row.path.split('/').some(x=>!x || x==='.' || x==='..'))fail('BACKUP_PATH_INVALID');
    if(manifest.schemaVersion===1 && fileHash(path.join(directory,row.path))!==row.sha256)fail('BACKUP_HASH_MISMATCH');
  }
  if(manifest.schemaVersion===2)materializeV2(directory,manifest,temporary=>restoreBackup(temporary,manifest,options,directory));
  else restoreBackup(directory,manifest,options);
  return {restoreVerified:true,fsck:'PASS'};
}
function backupUnlocked(repository,options) {
  if(options.backupVersion===1)return backupLegacyUnlocked(repository,options);
  assertNativeUnlocked(repository);fsck(repository,options);
  const captured=capture(repository,options),preservationRefs={...(options.preservationRefs??{})};
  const key=repositoryKey(repository.commonDirectory),protection=options.backupProtection??'ordinary';
  const stateHash=fingerprint({...captured,preservationRefs},protection);
  const root=options.backupRoot??path.join(os.homedir(),'.codex/backups/rwb-git-safety');
  return withBackupLock(root,()=>{
    const existing=findReusable(root,key,stateHash);
    if(existing) {
      verifyBackupDirectory(existing.directory,options);
      if(JSON.stringify(targetFootprint(capture(repository,options)))!==JSON.stringify(targetFootprint(captured)))fail('BACKUP_RACE');
      log(repository,'backup-reuse','PASS',undefined,{backup:existing.directory},options);
      const reused={directory:existing.directory,reused:true,restoreVerified:true,fsck:'PASS',snapshotRefs:Object.fromEntries(Object.entries(captured.refs).filter(([ref])=>ref.startsWith('refs/codex/')))};
      Object.defineProperty(reused,'verifiedPreservationRefs',{value:{...existing.manifest.preservationRefs}});
      return reused;
    }
    const legacy=backupLegacyUnlocked(repository,{...options,stageV2:true});
    const saved=readManifest(legacy.directory).manifest;
    const savedHash=fingerprint(saved,protection);
    const checkTarget=()=>{if(JSON.stringify(targetFootprint(capture(repository,options)))!==JSON.stringify(targetFootprint(saved)))fail('BACKUP_RACE');};
    checkTarget();
    const result=convertToV2(legacy.directory,key,{gitPath:selectGitPath(options),now:options.now,protection,stateHash:savedHash,verify:(dir,m)=>{verifySnapshotJournal(dir,m);return materializeV2(dir,m,tmp=>restoreBackup(tmp,m,options,dir));},afterVerified:checkTarget});
    log(repository,'backup-v2','PASS',undefined,{backup:result.directory},options);
    const completed={...legacy,...result};
    Object.defineProperty(completed,'verifiedPreservationRefs',{value:legacy.verifiedPreservationRefs});
    return completed;
  });
}

function registeredLifecycleBackups(repository,root) {
  const directory=path.join(repository.commonDirectory,'leon-engineering/resource-closeout'),ids=new Set();
  if(!fs.existsSync(directory))return ids;
  if(fs.lstatSync(directory).isSymbolicLink())fail('LIFECYCLE_BACKUP_INVALID');
  for(const entry of fs.readdirSync(directory,{withFileTypes:true})) {
    if(!entry.isDirectory() || !ID.test(entry.name))continue;
    const filename=path.join(directory,entry.name,'lifecycle-backup.json');
    if(!fs.existsSync(filename))continue;
    if(fs.lstatSync(filename).isSymbolicLink())fail('LIFECYCLE_BACKUP_INVALID');
    const saved=JSON.parse(fs.readFileSync(filename,'utf8'));
    if(saved.taskId!==entry.name || !/^[a-f0-9-]{36}$/.test(saved.id))fail('LIFECYCLE_BACKUP_INVALID');
    const point=path.join(root,saved.id);
    if(fs.existsSync(point) && readManifest(point).hash===saved.manifestHash)ids.add(saved.id);
  }
  return ids;
}

/** Preview is read-only; apply serializes archive changes without maintaining the live Git database. */
export function maintainBackups({projectRoot,action='backup-audit',apply=false},options={}) {
  const repository=discover(projectRoot,options);assertRepositoryIdentity(repository,options);
  if(!['backup-audit','backup-migrate','backup-prune'].includes(action) || action==='backup-audit'&&apply)fail('CLI_OPTION_INVALID');
  const root=options.backupRoot??path.join(os.homedir(),'.codex/backups/rwb-git-safety'),key=repositoryKey(repository.commonDirectory),now=options.now??Date.now();
  const retirementIds=options.retirementIds??registeredLifecycleBackups(repository,root);
  const run=()=>{
    const points=listPoints(root),items=[];
    const sameRepo=m=>m.schemaVersion===2 ? m.repositoryKey===key : m.registeredWorktrees?.some(x=>path.resolve(x.worktree)===repository.repositoryRoot);
    const eligible=points.filter(x=>!x.error && sameRepo(x.manifest));
    const newest=new Set(eligible.filter(x=>x.manifest.schemaVersion===2 && x.manifest.protection==='ordinary').sort((a,b)=>Date.parse(b.manifest.createdAt)-Date.parse(a.manifest.createdAt)).slice(0,2).map(x=>x.id));
    // Validate all certified points before a deletion. No corrupted retained snapshot can be certified away.
    if(apply && action==='backup-prune') {
      if(points.some(p=>p.error && !p.protectedLegacyFailure))fail('BACKUP_UNCERTIFIED_POINT');
      if(points.some(p=>fs.existsSync(path.join(p.directory,'manifest-v2.pending.json'))))fail('BACKUP_MIGRATION_PENDING');
      for(const p of eligible)verifyBackupDirectory(p.directory,options);
    }
    for(const p of points) {
      const item={id:p.id,status:'retained'};items.push(item);
      if(p.error){item.reason=p.protectedLegacyFailure?'failed_v1_evidence':p.error;continue;}
      const m=p.manifest;
      if(!sameRepo(m)){item.reason='foreign_or_unknown_repository';continue;}
      if(m.protection && m.protection!=='ordinary'){item.reason='protected';continue;}
      if(fs.existsSync(path.join(p.directory,'failure-status.json'))){item.reason='failed_or_isolated';continue;}
      if(action==='backup-migrate') {
        if(m.schemaVersion===2) {
          if(apply){verifyBackupDirectory(p.directory,options);finishMigration(p.directory,m);}
          item.reason='already_v2';continue;
        }
        if(m.worktrees.some(saved=>saved.index===undefined)){item.reason='legacy_index_unrecorded';continue;}
        item.status=apply?'migrated':'would_migrate';
        if(apply) {
          const converted=convertToV2(p.directory,key,{gitPath:selectGitPath(options),now,verify:(dir,manifest)=>{verifySnapshotJournal(dir,manifest);return materializeV2(dir,manifest,tmp=>restoreBackup(tmp,manifest,options,dir));},afterVerified:options.afterMigrationVerified,afterPendingWritten:options.afterMigrationPending});
          item.restoreVerified=converted.restoreVerified;
          log(repository,'backup-migrate','PASS',undefined,{backup:p.directory},options);
        }
        continue;
      }
      if(m.schemaVersion!==2){item.reason='migration_required';continue;}
      let reason;
      const roots=[...Object.values(m.refs),...Object.values(m.preservationRefs??{}),...Object.values(m.additionalBundleRefs??{}),...(m.registeredWorktrees??[]).map(x=>x.HEAD).filter(Boolean)];
      const otherCertified=eligible.filter(x=>x.id!==p.id && newest.has(x.id));
      for(const oid of new Set(roots)) {
        const covered=otherCertified.some(x=>[...Object.values(x.manifest.refs),...Object.values(x.manifest.preservationRefs??{}),...Object.values(x.manifest.additionalBundleRefs??{}),...(x.manifest.registeredWorktrees??[]).map(w=>w.HEAD)].includes(oid));
        if(covered)continue;
        const type=output(git(repository.repositoryRoot,['cat-file','-t',oid],options,{allowFailure:true}));
        if(type!=='commit' || git(repository.repositoryRoot,['merge-base','--is-ancestor',oid,'master'],options,{allowFailure:true}).status!==0){reason='unmerged_or_unique_anchor';break;}
      }
      for(const saved of m.worktrees) {
        if(reason)break;
        if(git(repository.repositoryRoot,['merge-base','--is-ancestor',saved.head,'master'],options,{allowFailure:true}).status!==0){reason='unmerged';break;}
        if(saved.untracked?.length || saved.staged!==sha256(Buffer.alloc(0)) || saved.unstaged!==sha256(Buffer.alloc(0))){reason='uncommitted';break;}
        if(fs.existsSync(saved.path)) {
          const state=git(saved.path,['status','--porcelain'],options,{allowFailure:true});
          if(state.status!==0 || state.stdout.length){reason='active_or_dirty';break;}
          if((options.processProbe??occupied)(saved.path)){reason='active';break;}
        }
      }
      if(reason){item.reason=reason;continue;}
      if(newest.has(p.id)){item.reason='latest_two';continue;}
      if(!retirementIds.has(p.id)){item.reason='legacy_policy_review_required';continue;}
      const created=Date.parse(m.createdAt);
      if(!Number.isFinite(created) || created>now){item.reason='unknown_age';continue;}
      item.status=action==='backup-prune'?(apply?'expired':'would_expire'):'retained';
      if(item.status==='expired') {
        if(readManifest(p.directory).hash!==p.hash)fail('BACKUP_MANIFEST_CHANGED');
        fs.rmSync(p.directory,{recursive:true});
        log(repository,'backup-expire','PASS',undefined,{backup:p.directory},options);
      }
    }
    const result={status:apply?'complete':'preview',retentionDays:0,minimumRecoveryPoints:2,trigger:'lifecycle-event',items};
    if(apply && action==='backup-prune') {
      result.collection=sweepPayloads(root,listPoints(root));
      if(result.collection.status==='blocked')result.status='blocked';
    }
    return result;
  };
  if(!apply)return run();
  assertNativeUnlocked(repository);fsck(repository,options);
  try{return withBackupLock(root,run);}catch(error){log(repository,action,'FAIL',error.code??'BACKUP_MAINTENANCE_FAILED',{},options);throw error;}
}
export function backupRepository({projectRoot}, options = {}) {
  options = {...options, startedAt: Date.now()};
  return withRepositoryLock({projectRoot}, repository => backupUnlocked(repository, options), options);
}
function occupied(directory) {
  const result = command('/usr/sbin/lsof', ['-nP', '+D', directory], {allowFailure: true});
  if (result.status === 0) return true;
  if (result.status === 1 && !result.stderr.toString().trim()) return false;
  fail('PROCESS_PROBE_FAILED');
}
function managed(receipt) {
  return [{branch: receipt.featureBranch, worktree: receipt.featureWorktree, commit: receipt.featureCommit}, ...(receipt.integrationHistory ?? []).map(item => ({branch: item.branch, worktree: item.worktree, commit: item.commit, worktreeRemoved: item.worktreeRemoved})), {branch: receipt.integrationBranch, worktree: receipt.integrationWorktree, commit: receipt.integrationCommit}].filter((item, index, all) => all.findIndex(other => other.worktree === item.worktree) === index);
}

/** A repair may advance its feature tip, but only commits in the actual candidate qualify. */
export function verifiedFeatureRepair({projectRoot, receipt}, options = {}) {
  const repository = discover(projectRoot, options);
  if (!ID.test(receipt.taskId ?? '') || !receipt.featureBranch?.startsWith(`codex/${receipt.taskId}-`)) fail('FEATURE_REPAIR_UNVERIFIED');
  for (const directory of [receipt.featureWorktree, receipt.integrationWorktree]) {
    if (!directory || discover(directory, options).commonDirectory !== repository.commonDirectory || output(git(directory, ['status', '--porcelain', '--untracked-files=all'], options))) fail('FEATURE_REPAIR_UNVERIFIED');
  }
  const head = output(git(receipt.featureWorktree, ['rev-parse', 'HEAD'], options));
  if (output(git(receipt.featureWorktree, ['symbolic-ref', '--short', 'HEAD'], options)) !== receipt.featureBranch ||
      git(projectRoot, ['merge-base', '--is-ancestor', receipt.featureCommit, head], options, {allowFailure:true}).status !== 0 ||
      git(receipt.integrationWorktree, ['merge-base', '--is-ancestor', head, 'HEAD'], options, {allowFailure:true}).status !== 0) fail('FEATURE_REPAIR_UNVERIFIED');
  return head;
}

function closeoutEnabled(repository) {
  const source = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
  return fs.existsSync(path.join(source, '.agents/resource-closeout.json')) && discover(source).commonDirectory === repository.commonDirectory;
}

function selectResourcePython(repository) {
  const installed = path.join(repository.repositoryRoot, '.venv/bin/python');
  if (fs.existsSync(installed)) return installed;
  // Match the existing fixed-name PATH choice before execution, including PATH
  // entries relative to the command's existing repository cwd. This is not a
  // trust certificate; the original resource command already uses this TCB.
  if (process.env.PATH === undefined) return 'python3.12';
  for (const entry of process.env.PATH.split(path.delimiter)) {
    // Keep lexical '..' components: collapsing one across a symlink can change
    // which executable the existing PATH entry actually names in the kernel.
    const prefix = path.isAbsolute(entry) ? entry : repository.repositoryRoot + path.sep + (entry || '.');
    const candidate = prefix + path.sep + 'python3.12';
    try {if (fs.statSync(candidate).isFile()) {fs.accessSync(candidate, fs.constants.X_OK); return candidate;}} catch { /* continue the existing PATH search */ }
  }
  return 'python3.12'; // Preserve the existing command failure if none is found.
}

function resourcePhase(repository, taskId, phase, options) {
  const scope = deliveryToolchains.get(repository);
  if (scope) scope.record = undefined;
  if (!closeoutEnabled(repository)) return options.resourceRevalidationProbe?.(repository,taskId,phase);
  const source = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
  const python = selectResourcePython(repository);
  const canRecord = scope?.active && scope.taskId === taskId && !options.controller && !options.resourceRevalidationProbe;
  const beforeReference = canRecord ? selectedExecutableReference(python) : undefined;
  const result = command(python, ['-P', '-m', 'research_workbench_entrypoint.iteration_resources', '--project', repository.repositoryRoot, '--task-id', taskId, '--phase', phase], {
    cwd: repository.repositoryRoot,
    env: {...process.env, PYTHONPATH:source, PYTHONDONTWRITEBYTECODE:'1'}, allowFailure:true,
  });
  if (result.status !== 0) {
    let code = 'RESOURCE_CLOSEOUT_BLOCKED';
    try { const detail=JSON.parse(result.stdout.toString('utf8')); if (/^[a-z_]{1,80}$/.test(detail.code ?? '')) code=detail.code; } catch { /* bounded stable fallback; never echo subprocess output */ }
    fail(code);
  }
  log(repository, 'resource-' + phase, 'PASS', undefined, {}, options);
  let revalidation;
  if(phase==='revalidate') {
    try{revalidation = JSON.parse(result.stdout.toString('utf8'));}catch{fail('RESOURCE_CLOSEOUT_BLOCKED');}
  }
  const afterReference = canRecord && beforeReference ? selectedExecutableReference(python) : undefined;
  if (canRecord && deliveryToolchains.get(repository) === scope && executableReferencesEqual(beforeReference, afterReference)) scope.record = {binding: toolchainBinding(scope), reference: beforeReference};
  return revalidation;
}

function refreshFeatureRecord(repository, receipt, options) {
  const head = verifiedFeatureRepair({projectRoot:repository.repositoryRoot, receipt}, options);
  if (head === receipt.featureCommit) return;
  const lock=path.join(repository.commonDirectory,'leon-engineering/locks/integration.lock');
  try { privateWrite(lock,String(process.pid)+'\n'); } catch(error) { if(error.code==='EEXIST') fail('TASK_LOCKED'); throw error; }
  const lockIdentity=fs.lstatSync(lock);
  try {
  if (verifiedFeatureRepair({projectRoot:repository.repositoryRoot,receipt},options)!==head) fail('FEATURE_REPAIR_UNVERIFIED');
  const destination = path.join(repository.commonDirectory, 'leon-engineering/deliveries', receipt.taskId + '.json');
  assertNoSymlinkAncestors(path.dirname(destination));
  if (fs.lstatSync(destination).isSymbolicLink()) fail('DELIVERY_RECORD_INVALID');
  const before = fs.readFileSync(destination, 'utf8');
  const current = JSON.parse(before);
  if (current.featureCommit !== receipt.featureCommit || current.integrationCommit !== receipt.integrationCommit) fail('DELIVERY_RECORD_CHANGED');
  const updated = {...current, featureCommit:head};
  const temporary = destination + '.' + crypto.randomUUID() + '.tmp';
  privateWrite(temporary, JSON.stringify(updated, null, 2) + '\n');
  if (fs.readFileSync(destination, 'utf8') !== before) fail('DELIVERY_RECORD_CHANGED');
  fs.renameSync(temporary, destination);
  log(repository, 'feature-repair-identity', 'PASS', undefined, {head}, options);
  } finally {
    const current=fs.lstatSync(lock);
    if (current.isSymbolicLink() || current.dev!==lockIdentity.dev || current.ino!==lockIdentity.ino) fail('LOCK_OWNERSHIP_CHANGED');
    fs.unlinkSync(lock);
  }
}
// This admission contract is deliberately closed and versioned independently of
// published refresh: new shared-controller metadata requires explicit review.
const AMEND_RECEIPT_FIELDS_V1 = ['schemaVersion','taskId','repositoryRoot','remote','remoteUrl','defaultBranch','baseCommit','featureBranch','featureWorktree','featureCommit','integrationBranch','integrationWorktree','integrationCommit','integrationHistory','mergeSourceCommit','remoteCommit','mode','pullRequest','verification','ci','repairAttempts','rollback','cleanup','status','createdAt','updatedAt','baseRefreshPublishedHead','review','preparedAmendment','preparedAmendmentHistory'];
const AMEND_PROOF_FIELDS_V1 = ['schemaVersion','epoch','previousCandidate','previousFeature','candidateCommit','featureCommit','baseCommit','receiptSnapshot','receiptSha256','backupDirectory','backupManifestSha256','restoreVerified'];
const AMEND_PROOF_FIELDS_V2 = [...AMEND_PROOF_FIELDS_V1,'mergeChain'];
const AMEND_CHAIN_LIMIT = 32, AMEND_COMMIT_BYTES = 64*1024, AMEND_CHAIN_BYTES = 256*1024;
function exactFields(value, fields, required = fields) {
  return value && typeof value==='object' && !Array.isArray(value) && Object.keys(value).every(key=>fields.includes(key)) && required.every(key=>Object.hasOwn(value,key));
}
function validateAmendReceipt(receipt) {
  const verification=receipt.verification;
  if(receipt.schemaVersion!==1 || !exactFields(receipt,AMEND_RECEIPT_FIELDS_V1,[]) ||
      receipt.status!=='prepared' || receipt.mode!==null || receipt.pullRequest!==null || receipt.remoteCommit!==null ||
      Object.hasOwn(receipt,'mergeSourceCommit') && receipt.mergeSourceCommit!==receipt.featureCommit ||
      Object.hasOwn(receipt,'baseRefreshPublishedHead') && receipt.baseRefreshPublishedHead!==null ||
      Object.hasOwn(receipt,'review') && receipt.review!==null ||
      !exactFields(receipt.ci,['status','runs']) || !['pending','not_configured'].includes(receipt.ci.status) || !Array.isArray(receipt.ci.runs) || receipt.ci.runs.length ||
      !exactFields(receipt.rollback,['status']) || receipt.rollback.status!=='not_run' ||
      !exactFields(receipt.cleanup,['featureWorktreeRemoved','integrationWorktreeRemoved','localBranchDeleted','remoteBranchDeleted']) || Object.values(receipt.cleanup).some(value=>value!==false) ||
      verification!==null && (!exactFields(verification,['status','command','durationSeconds','recordedAt'],['status']) || !['not_run','passed','failed'].includes(verification.status) ||
        Object.hasOwn(verification,'command') && (typeof verification.command!=='string' || !verification.command.trim()) ||
        Object.hasOwn(verification,'durationSeconds') && (!Number.isSafeInteger(verification.durationSeconds) || verification.durationSeconds<0) ||
        Object.hasOwn(verification,'recordedAt') && !Number.isFinite(Date.parse(verification.recordedAt))) ||
      ['createdAt','updatedAt'].some(key=>Object.hasOwn(receipt,key) && !Number.isFinite(Date.parse(receipt[key]))) ||
      !Number.isSafeInteger(receipt.repairAttempts) || receipt.repairAttempts<0 || !Array.isArray(receipt.integrationHistory) || receipt.integrationHistory.length) fail('UNPUBLISHED_STATE_INVALID');
  const history=receipt.preparedAmendmentHistory;
  if(history===undefined && receipt.preparedAmendment===undefined) return;
  if(!Array.isArray(history) || !history.length || JSON.stringify(history.at(-1))!==JSON.stringify(receipt.preparedAmendment)) fail('PREPARED_AMEND_HISTORY_INVALID');
  for(const proof of history) {
    if(![1,2].includes(proof?.schemaVersion) || !exactFields(proof,proof.schemaVersion===2?AMEND_PROOF_FIELDS_V2:AMEND_PROOF_FIELDS_V1) || proof.restoreVerified!==true ||
      !/^[a-f0-9-]{36}$/.test(proof.epoch??'') || !/^[a-f0-9]{64}$/.test(proof.receiptSha256??'') || !/^[a-f0-9]{64}$/.test(proof.backupManifestSha256??'') ||
      ['previousCandidate','previousFeature','candidateCommit','featureCommit','baseCommit'].some(key=>!/^[a-f0-9]{40}$/.test(proof[key]??''))) fail('PREPARED_AMEND_HISTORY_INVALID');
    if(proof.schemaVersion===2) {
      if(!Array.isArray(proof.mergeChain) || !proof.mergeChain.length || proof.mergeChain.length>AMEND_CHAIN_LIMIT || Buffer.byteLength(JSON.stringify(proof.mergeChain))>16*1024) fail('PREPARED_AMEND_HISTORY_INVALID');
      const commits=new Set([proof.previousCandidate]),features=new Set([proof.previousFeature]);let previous=proof.previousCandidate;
      for(const step of proof.mergeChain) {
        if(!exactFields(step,['commit','firstParent','featureCommit']) || Object.values(step).some(value=>!/^[a-f0-9]{40}$/.test(value??'')) || step.firstParent!==previous || commits.has(step.commit) || features.has(step.featureCommit)) fail('PREPARED_AMEND_HISTORY_INVALID');
        commits.add(step.commit);features.add(step.featureCommit);previous=step.commit;
      }
      if(previous!==proof.candidateCommit || proof.mergeChain.at(-1).featureCommit!==proof.featureCommit) fail('PREPARED_AMEND_HISTORY_INVALID');
    }
  }
}
function rawAmendMergeChain(repository,{previousCandidate,previousFeature,candidateCommit,featureCommit},options,legacy=false) {
  const reversed=[],seen=new Set();let current=candidateCommit,bytes=0;
  while(current!==previousCandidate) {
    if(reversed.length>=(legacy?1:AMEND_CHAIN_LIMIT)) fail('PREPARED_AMEND_CHAIN_LIMIT');
    if(!/^[a-f0-9]{40}$/.test(current??'') || seen.has(current)) fail('PREPARED_AMEND_ANCESTRY_INVALID');seen.add(current);
    const size=Number(output(git(repository.repositoryRoot,['cat-file','-s',current],options)));
    if(!Number.isSafeInteger(size) || size<1 || size>(legacy?64*1024*1024:AMEND_COMMIT_BYTES) || (bytes+=size)>(legacy?64*1024*1024:AMEND_CHAIN_BYTES)) fail('PREPARED_AMEND_CHAIN_LIMIT');
    const parents=git(repository.repositoryRoot,['cat-file','commit',current],options).stdout.toString('utf8').split('\n\n',1)[0].split('\n').filter(line=>line.startsWith('parent ')).map(line=>line.slice(7));
    if(parents.length!==2 || parents.some(parent=>!/^[a-f0-9]{40}$/.test(parent))) fail('PREPARED_AMEND_ANCESTRY_INVALID');
    reversed.push({commit:current,firstParent:parents[0],featureCommit:parents[1]});current=parents[0];
  }
  const chain=reversed.reverse();let prior=previousFeature;
  for(const step of chain) {
    if(step.featureCommit===prior || git(repository.repositoryRoot,['merge-base','--is-ancestor',prior,step.featureCommit],options,{allowFailure:true}).status!==0 ||
        git(repository.repositoryRoot,['merge-base','--is-ancestor',step.featureCommit,featureCommit],options,{allowFailure:true}).status!==0) fail('PREPARED_AMEND_ANCESTRY_INVALID');
    prior=step.featureCommit;
  }
  if(!chain.length || prior!==featureCommit) fail('PREPARED_AMEND_ANCESTRY_INVALID');
  return chain;
}
function amendChainAnchors(chain) {
  return Object.fromEntries(chain.flatMap((step,index)=>[[`refs/rwb-amend/merge-chain/${index}/candidate`,step.commit],[`refs/rwb-amend/merge-chain/${index}/feature`,step.featureCommit]]));
}
/** Adopt only an already committed, never-published merge in the original worktree. */
function amendPrepared(repository, receipt, taskId, options) {
  options={...options,readOnlyGit:true};
  validateAmendReceipt(receipt);
  if (receipt.schemaVersion !== 1 || receipt.taskId !== taskId || receipt.repositoryRoot !== repository.repositoryRoot || receipt.remote !== 'origin' || receipt.defaultBranch !== 'master' ||
      !receipt.featureBranch?.startsWith(`codex/${taskId}-`) || !new RegExp(`^codex/integrate-${taskId}(?:-r[0-9]+)?$`).test(receipt.integrationBranch ?? '') ||
      [receipt.baseCommit,receipt.featureCommit,receipt.integrationCommit].some(value => !/^[a-f0-9]{40}$/.test(value ?? ''))) fail('TASK_OWNERSHIP_MISMATCH');
  const repo = githubRepo(receipt), locks = [];
  const identity = filename => {
    assertNoSymlinkAncestors(path.dirname(filename));
    const stat = fs.lstatSync(filename);
    if (!stat.isFile() || stat.isSymbolicLink() || stat.nlink !== 1 || stat.uid !== process.getuid()) fail('DELIVERY_RECORD_INVALID');
    const fd=fs.openSync(filename,fs.constants.O_RDONLY|fs.constants.O_NOFOLLOW);
    try {
      const opened=fs.fstatSync(fd),bytes=fs.readFileSync(fd),after=fs.fstatSync(fd),current=fs.lstatSync(filename);
      if(!opened.isFile() || opened.nlink!==1 || opened.dev!==stat.dev || opened.ino!==stat.ino || opened.uid!==stat.uid ||
          after.size!==opened.size || after.mtimeMs!==opened.mtimeMs || after.ctimeMs!==opened.ctimeMs || current.isSymbolicLink() || current.nlink!==1 || current.dev!==opened.dev || current.ino!==opened.ino) fail('DELIVERY_RECORD_CHANGED');
      return {dev:opened.dev,ino:opened.ino,bytes};
    } finally {fs.closeSync(fd);}
  };
  const destination = path.join(repository.commonDirectory,'leon-engineering/deliveries',taskId+'.json');
  const ledgerPath = path.join(repository.commonDirectory,'leon-engineering/resource-closeout',taskId,'resources.json');
  let temporary,temporaryIdentity;
  try {
    for (const name of ['integration',taskId]) {
      const filename=path.join(repository.commonDirectory,'leon-engineering/locks',name+'.lock');
      try { privateWrite(filename,String(process.pid)+'\n'); } catch(error) { if(error.code==='EEXIST') fail('TASK_LOCKED'); throw error; }
      locks.push({filename,...identity(filename)});
    }
    const original=identity(destination), ledger=identity(ledgerPath), ownership=JSON.parse(ledger.bytes);
    if (JSON.stringify(JSON.parse(original.bytes)) !== JSON.stringify(receipt)) fail('DELIVERY_RECORD_CHANGED');
    if (ownership.taskId !== taskId) fail('TASK_OWNERSHIP_MISMATCH');
    const unchanged = (filename, expected) => {
      const actual=identity(filename);
      if(actual.dev!==expected.dev || actual.ino!==expected.ino || !actual.bytes.equals(expected.bytes)) fail('DELIVERY_RECORD_CHANGED');
    };
    const history=receipt.preparedAmendmentHistory??[], historicalFiles=[], backupRoot=path.resolve(options.backupRoot??path.join(os.homedir(),'.codex/backups/rwb-git-safety'));
    let assertBackupHeld;
    const validateHistory = (restore=false) => {
      for(const [index,proof] of history.entries()) {
        const directory=path.join(state(repository),'prepared-amend',taskId,proof.epoch);
        if(proof.receiptSnapshot!==path.join(directory,'receipt.json') || typeof proof.backupDirectory!=='string' || path.dirname(proof.backupDirectory)!==backupRoot || !/^[a-f0-9-]{36}$/.test(path.basename(proof.backupDirectory))) fail('PREPARED_AMEND_HISTORY_INVALID');
        const saved=identity(proof.receiptSnapshot), storedProof=identity(path.join(directory,'proof.json'));
        const previous=JSON.parse(saved.bytes); validateAmendReceipt(previous);
        const manifest=readManifest(proof.backupDirectory);
        const chain=rawAmendMergeChain(repository,proof,options,proof.schemaVersion===1);
        if(proof.schemaVersion===1?chain.length!==1:JSON.stringify(chain)!==JSON.stringify(proof.mergeChain) || Object.entries(amendChainAnchors(chain)).some(([ref,oid])=>manifest.manifest.preservationRefs?.[ref]!==oid)) fail('PREPARED_AMEND_HISTORY_INVALID');
        if(sha256(saved.bytes)!==proof.receiptSha256 || !storedProof.bytes.equals(Buffer.from(JSON.stringify(proof,null,2)+'\n')) || manifest.hash!==proof.backupManifestSha256 ||
            manifest.manifest.preservationRefs?.['refs/rwb-amend/old-feature']!==proof.previousFeature || manifest.manifest.preservationRefs?.['refs/rwb-amend/old-candidate']!==proof.previousCandidate ||
            previous.integrationCommit!==proof.previousCandidate || previous.featureCommit!==proof.previousFeature || previous.baseCommit!==proof.baseCommit ||
            ['taskId','repositoryRoot','remote','remoteUrl','defaultBranch','featureWorktree','integrationWorktree','featureBranch','integrationBranch','baseCommit','repairAttempts'].some(key=>previous[key]!==receipt[key]) ||
            JSON.stringify(previous.preparedAmendmentHistory??[])!==JSON.stringify(history.slice(0,index)) ||
            index>0 && (proof.previousCandidate!==history[index-1].candidateCommit || proof.previousFeature!==history[index-1].featureCommit) ||
            index===history.length-1 && (proof.candidateCommit!==receipt.integrationCommit || proof.featureCommit!==receipt.featureCommit)) fail('PREPARED_AMEND_HISTORY_INVALID');
        if(!historicalFiles[index]) historicalFiles[index]=[saved,storedProof];
        else {unchanged(proof.receiptSnapshot,historicalFiles[index][0]);unchanged(path.join(directory,'proof.json'),historicalFiles[index][1]);}
        if(restore) {assertBackupHeld();verifyBackupDirectory(proof.backupDirectory,options);assertBackupHeld();}
      }
    };
    validateHistory();
    const prior=receipt.preparedAmendment;
    const replay=prior?.candidateCommit===receipt.integrationCommit && prior?.featureCommit===receipt.featureCommit &&
      output(git(receipt.integrationWorktree,['rev-parse','HEAD'],options))===receipt.integrationCommit && output(git(receipt.featureWorktree,['rev-parse','HEAD'],options))===receipt.featureCommit;
    const oldCandidate=replay ? prior.previousCandidate : receipt.integrationCommit;
    const oldFeature=replay ? prior.previousFeature : receipt.featureCommit;
    let captured, assertCurrentBackup, pendingEpoch;
    const assertRawGraph = () => {
      if(process.env.GIT_GRAFT_FILE || process.env.GIT_SHALLOW_FILE) fail('PREPARED_AMEND_GRAPH_UNPROVEN');
      for(const directory of [repository.repositoryRoot,receipt.featureWorktree,receipt.integrationWorktree]) {
        if(output(git(directory,['rev-parse','--is-shallow-repository'],options))!=='false') fail('PREPARED_AMEND_GRAPH_UNPROVEN');
        for(const name of ['info/grafts','shallow']) {
          const filename=path.resolve(directory,output(git(directory,['rev-parse','--git-path',name],options)));
          if(fs.lstatSync(filename,{throwIfNoEntry:false})) fail('PREPARED_AMEND_GRAPH_UNPROVEN');
        }
      }
    };
    const candidateState = () => {
      repository.assertLockOwned(); if(assertBackupHeld) assertBackupHeld(); validateHistory();
      assertRawGraph(); if(assertCurrentBackup) assertCurrentBackup();
      if(pendingEpoch) for(const [filename,saved] of pendingEpoch) unchanged(filename,saved);
      assertNativeUnlocked(repository); unchanged(destination,original); unchanged(ledgerPath,ledger);
      for(const lock of locks) unchanged(lock.filename,lock);
      if(output(git(repository.repositoryRoot,['remote','get-url','origin'],options))!==receipt.remoteUrl || output(git(repository.repositoryRoot,['rev-parse','refs/remotes/origin/master'],options))!==receipt.baseCommit) fail('REMOTE_IDENTITY_CHANGED');
      const entries=worktrees(repository,options), result=[];
      for(const [directory,branch] of [[receipt.featureWorktree,receipt.featureBranch],[receipt.integrationWorktree,receipt.integrationBranch]]) {
        assertNoSymlinkAncestors(directory);
        const stat=fs.lstatSync(directory), registered=entries.find(row=>row.worktree===directory);
        if(!stat.isDirectory() || stat.isSymbolicLink() || stat.uid!==process.getuid() || fs.realpathSync(directory)!==directory || directory===repository.repositoryRoot ||
            JSON.stringify(ownership.roots?.[directory])!==JSON.stringify([stat.dev,stat.ino]) || !registered || registered.branch!==`refs/heads/${branch}` || registered.locked || registered.prunable ||
            discover(directory,options).commonDirectory!==repository.commonDirectory || output(git(directory,['symbolic-ref','--short','HEAD'],options))!==branch) fail('TASK_OWNERSHIP_MISMATCH');
        if((options.processProbe??occupied)(directory)) fail('WORKTREE_IN_USE');
        if(output(git(directory,['status','--porcelain','--untracked-files=all'],options))) fail('WORKTREE_DIRTY');
        for(const operation of ['MERGE_HEAD','CHERRY_PICK_HEAD','REVERT_HEAD','rebase-merge','rebase-apply']) {
          const operationPath=output(git(directory,['rev-parse','--git-path',operation],options));
          if(fs.existsSync(path.resolve(directory,operationPath))) fail('INTEGRATION_NOT_COMMITTED');
        }
        const dotgit=identity(path.join(directory,'.git'));
        const admin=path.resolve(directory,output(git(directory,['rev-parse','--git-dir'],options))), adminStat=fs.lstatSync(admin);
        if(!adminStat.isDirectory() || adminStat.isSymbolicLink()) fail('TASK_OWNERSHIP_MISMATCH');
        result.push({head:registered.HEAD,branch,directory,dev:stat.dev,ino:stat.ino,gitFile:sha256(dotgit.bytes),gitInode:dotgit.ino,admin,adminDev:adminStat.dev,adminIno:adminStat.ino});
      }
      if(result[0].directory===result[1].directory) fail('TASK_OWNERSHIP_MISMATCH');
      const feature=result[0].head, candidate=result[1].head;
      const ancestor=(a,b)=>/^[a-f0-9]{40}$/.test(a??'') && git(repository.repositoryRoot,['merge-base','--is-ancestor',a,b],options,{allowFailure:true}).status===0;
      if(feature===oldFeature || candidate===oldCandidate || !ancestor(oldFeature,feature) || !ancestor(oldCandidate,candidate) || !ancestor(feature,candidate) || !ancestor(receipt.baseCommit,candidate) ||
          !ancestor(receipt.baseCommit,oldCandidate) || !ancestor(oldFeature,oldCandidate) || ancestor(oldCandidate,receipt.baseCommit) || ancestor(candidate,receipt.baseCommit)) fail('PREPARED_AMEND_ANCESTRY_INVALID');
      const mergeChain=rawAmendMergeChain(repository,{previousCandidate:oldCandidate,previousFeature:oldFeature,candidateCommit:candidate,featureCommit:feature},options,replay && prior.schemaVersion===1);
      const value=JSON.stringify({result,mergeChain,refs:refs(repository,options)});
      if(captured && value!==captured) fail('DELIVERY_RECORD_CHANGED');
      captured=value;
      return {feature,candidate,mergeChain};
    };
    const {feature,candidate,mergeChain}=candidateState();
    const readCommit = commit => {
      const response=(options.githubRunner??((exe,args,extra)=>command(exe,args,extra)))('gh',['api',`repos/${repo}/commits/${commit}`,'--include'],{cwd:repository.repositoryRoot,allowFailure:true});
      const match=response.stdout.toString().match(/^HTTP\/[\d.]+ (\d{3})[^\r\n]*\r?\n(?:[^\r\n]+\r?\n)*\r?\n([\s\S]*)$/);
      let body;try {body=JSON.parse(match?.[2]??'');} catch {fail('UNPUBLISHED_REMOTE_UNPROVEN');}
      if(!body || typeof body!=='object' || Array.isArray(body)) fail('UNPUBLISHED_REMOTE_UNPROVEN');
      return {http:match[1],exit:response.status,body};
    };
    const remoteState = () => {
      const base=githubJson(['api',`repos/${repo}/git/ref/heads/master`],repository,options)?.object?.sha;
      if(base!==receipt.baseCommit) fail('REMOTE_BASE_CHANGED');
      for(const branch of [receipt.featureBranch,receipt.integrationBranch]) {
        const remote=githubJson(['api',`repos/${repo}/git/matching-refs/heads/${branch}`],repository,options);
        const prs=githubJson(['api',`repos/${repo}/pulls?state=all&head=${repo.split('/')[0]}:${branch}&per_page=1`],repository,options);
        if(!Array.isArray(remote) || remote.length || !Array.isArray(prs) || prs.length) fail('UNPUBLISHED_STATE_INVALID');
      }
      const baseCommit=readCommit(receipt.baseCommit);
      if(baseCommit.http!=='200' || baseCommit.exit!==0 || baseCommit.body.sha!==receipt.baseCommit) fail('UNPUBLISHED_REMOTE_UNPROVEN');
      const intermediates=new Set(mergeChain.slice(0,-1).flatMap(step=>[step.commit,step.featureCommit]));
      for(const commit of new Set([oldCandidate,...mergeChain.flatMap(step=>[step.commit,step.featureCommit])])) {
        // GitHub uses exact 422 missing-SHA responses for unpublished commits.
        // Accept only after proving this same commit endpoint can read the base.
        const {http,exit,body}=readCommit(commit);
        const absent=exit===1 && (http==='404' && body.message==='Not Found' || http==='422' && exactFields(body,['message','documentation_url','status']) && body.message===`No commit found for SHA: ${commit}` && body.documentation_url==='https://docs.github.com/rest/commits/commits#get-a-commit' && body.status==='422');
        if(!absent && (http!=='200' || exit!==0 || body.sha!==commit)) fail('UNPUBLISHED_REMOTE_UNPROVEN');
        if(!absent && intermediates.has(commit)) fail('UNPUBLISHED_STATE_INVALID');
        const endpoints=[`actions/runs?head_sha=${commit}&per_page=1`,...(absent?[]:[`commits/${commit}/check-runs`,`commits/${commit}/status`])];
        for(const endpoint of endpoints) {
          const value=githubJson(['api',`repos/${repo}/${endpoint}`],repository,options);
          const rows=endpoint.startsWith('actions/')?value.workflow_runs:endpoint.endsWith('check-runs')?value.check_runs:value.statuses;
          if(value.total_count!==0 || !Array.isArray(rows) || rows.length) fail('UNPUBLISHED_CI_PRESENT');
        }
      }
      // Last network observation precedes the synchronous local CAS revalidation.
      if(githubJson(['api',`repos/${repo}/git/ref/heads/master`],repository,options)?.object?.sha!==receipt.baseCommit) fail('REMOTE_BASE_CHANGED');
      candidateState();
    };
    remoteState();
    if(replay) {
      if(receipt.verification!==null || receipt.review!==null) fail('PREPARED_AMEND_HISTORY_INVALID');
      return withBackupLock(backupRoot,assertHeld=>{
        assertBackupHeld=assertHeld; validateHistory(true); remoteState();
        log(repository,'delivery-prepared-amend-replay','PASS',undefined,{candidate},options);
        return receipt;
      });
    }
    if(feature===receipt.featureCommit || candidate===receipt.integrationCommit) fail('PREPARED_AMEND_NOT_NEEDED');
    const disk=fs.statfsSync(repository.repositoryRoot);
    if(disk.bavail*disk.bsize<3*1024**3) fail('PREPARED_AMEND_DISK_BUDGET');
    const preserved=refs(repository,options);
    const chainAnchors=amendChainAnchors(mergeChain);
    const backup=backupUnlocked(repository,{...options,backupVersion:2,preservationRefs:{...preserved,'refs/rwb-amend/old-feature':receipt.featureCommit,'refs/rwb-amend/old-candidate':receipt.integrationCommit,...chainAnchors},worktreePaths:[receipt.featureWorktree,receipt.integrationWorktree]});
    if(backup.restoreVerified!==true) fail('RESTORE_UNVERIFIED');
    return withBackupLock(path.dirname(backup.directory),assertHeld=>{
    assertBackupHeld=assertHeld; validateHistory(true);
    verifyBackupDirectory(backup.directory,options);
    const restored=readManifest(backup.directory), manifestFile=path.join(backup.directory,'manifest.json'), sealFile=path.join(backup.directory,'seal.json');
    const restoredManifest=identity(manifestFile), restoredSeal=identity(sealFile);
    assertCurrentBackup=()=>{
      unchanged(manifestFile,restoredManifest);unchanged(sealFile,restoredSeal);
      const current=readManifest(backup.directory), value=current.manifest;
      if(current.hash!==restored.hash || value.preservationRefs?.['refs/rwb-amend/old-feature']!==receipt.featureCommit || value.preservationRefs?.['refs/rwb-amend/old-candidate']!==receipt.integrationCommit ||
          Object.entries(chainAnchors).some(([ref,oid])=>value.preservationRefs?.[ref]!==oid) ||
          value.refs?.[`refs/heads/${receipt.featureBranch}`]!==feature || value.refs?.[`refs/heads/${receipt.integrationBranch}`]!==candidate || value.refs?.['refs/remotes/origin/master']!==receipt.baseCommit ||
          value.worktrees.length!==2 || value.worktrees.find(row=>row.path===receipt.featureWorktree)?.head!==feature || value.worktrees.find(row=>row.path===receipt.integrationWorktree)?.head!==candidate) fail('PREPARED_AMEND_HISTORY_INVALID');
    };
    assertCurrentBackup();
    options.afterPreparedAmendBackup?.(backup);
    candidateState(); remoteState();
    const epoch=crypto.randomUUID(), directory=path.join(state(repository),'prepared-amend',taskId,epoch);
    const snapshot=path.join(directory,'receipt.json'); privateWrite(snapshot,original.bytes);
    const proof={schemaVersion:2,epoch,previousCandidate:receipt.integrationCommit,previousFeature:receipt.featureCommit,candidateCommit:candidate,featureCommit:feature,baseCommit:receipt.baseCommit,receiptSnapshot:snapshot,receiptSha256:sha256(original.bytes),backupDirectory:backup.directory,backupManifestSha256:restored.hash,restoreVerified:true,mergeChain};
    // The sealed external backup anchors both old commits without moving any ref.
    privateWrite(path.join(directory,'proof.json'),JSON.stringify(proof,null,2)+'\n');
    const updated={...receipt,featureCommit:feature,integrationCommit:candidate,...(Object.hasOwn(receipt,'mergeSourceCommit')?{mergeSourceCommit:feature}:{}),verification:null,ci:{status:'pending',runs:[]},review:null,preparedAmendment:proof,preparedAmendmentHistory:[...(receipt.preparedAmendmentHistory??[]),proof],updatedAt:new Date().toISOString()};
    temporary=destination+'.'+epoch+'.tmp';privateWrite(temporary,JSON.stringify(updated,null,2)+'\n');
    pendingEpoch=[[snapshot,original.bytes],[path.join(directory,'proof.json'),Buffer.from(JSON.stringify(proof,null,2)+'\n')],[temporary,Buffer.from(JSON.stringify(updated,null,2)+'\n')]].map(([filename,bytes])=>{
      const saved=identity(filename);if(!saved.bytes.equals(bytes)) fail('DELIVERY_RECORD_CHANGED');return [filename,saved];
    });
    temporaryIdentity=pendingEpoch.at(-1)[1];
    options.beforePreparedAmendAdopt?.();
    remoteState(); candidateState();
    const remaining=fs.statfsSync(repository.repositoryRoot);
    if(remaining.bavail*remaining.bsize<2*1024**3) fail('PREPARED_AMEND_DISK_BUDGET');
    repository.assertLockOwned(); assertBackupHeld();
    fs.renameSync(temporary,destination);
    log(repository,'delivery-prepared-amend','PASS',undefined,{candidate,previousCandidate:receipt.integrationCommit,receiptSnapshot:snapshot,backup:backup.directory},options);
    return updated;
    });
  } finally {
    if(temporary && temporaryIdentity && fs.lstatSync(temporary,{throwIfNoEntry:false})) {
      const current=fs.lstatSync(temporary);
      if(current.isFile() && !current.isSymbolicLink() && current.nlink===1 && current.dev===temporaryIdentity.dev && current.ino===temporaryIdentity.ino && identity(temporary).bytes.equals(temporaryIdentity.bytes)) fs.unlinkSync(temporary);
      else log(repository,'delivery-prepared-amend-temporary','RETAINED','TEMPORARY_IDENTITY_CHANGED',{},options);
    }
    for(const lock of locks.reverse()) {
      const current=identity(lock.filename);
      if(current.dev!==lock.dev || current.ino!==lock.ino || !current.bytes.equals(lock.bytes)) fail('LOCK_OWNERSHIP_CHANGED');
      fs.unlinkSync(lock.filename);
    }
  }
}
function refreshPublishedBase(repository, receipt, taskId, options) {
  // The shared controller rebuilds worktrees for remote_moved. RWB instead admits
  // an already committed descendant, preserving every ref and any existing PR.
  // A never-published candidate must retain explicit null publication identities.
  const unpublished = receipt.mode === null && receipt.pullRequest === null && receipt.remoteCommit === null;
  const publishedPrepared = receipt.mode === 'pr' && receipt.status === 'prepared' &&
    /^[a-f0-9]{40}$/.test(receipt.baseRefreshPublishedHead ?? '') && receipt.baseRefreshPublishedHead !== receipt.integrationCommit;
  const refreshable = unpublished ? ['remote_moved', 'prepared'] : ['remote_moved', 'awaiting_ci', 'ci_failed', ...(publishedPrepared ? ['prepared'] : [])];
  if ((!unpublished && receipt.mode !== 'pr') || !refreshable.includes(receipt.status) || !receipt.integrationCommit) fail('PREPARE_REMOVAL_BLOCKED');
  if (unpublished && (receipt.baseRefreshPublishedHead != null || Object.keys(receipt).some(key => /publish|publication|push|pull.?request|remote.?commit/i.test(key) && !['pullRequest', 'remoteCommit', 'baseRefreshPublishedHead'].includes(key)) || receipt.cleanup?.remoteBranchDeleted === true || receipt.rollback && receipt.rollback.status !== 'not_run')) fail('UNPUBLISHED_STATE_INVALID');
  if (unpublished && Object.hasOwn(receipt, 'mergeSourceCommit') && receipt.mergeSourceCommit !== receipt.featureCommit) fail('UNPUBLISHED_STATE_INVALID');
  if (receipt.taskId !== taskId || receipt.repositoryRoot !== repository.repositoryRoot || receipt.remote !== 'origin' || receipt.defaultBranch !== 'master' || !new RegExp(`^codex/integrate-${taskId}(?:-r[0-9]+)?$`).test(receipt.integrationBranch ?? '')) fail('TASK_OWNERSHIP_MISMATCH');
  const repo = githubRepo(receipt);
  if (!unpublished && (!Number.isSafeInteger(receipt.pullRequest?.number) || receipt.pullRequest.number < 1 || receipt.pullRequest.url !== `https://github.com/${repo}/pull/${receipt.pullRequest.number}`)) fail('TASK_OWNERSHIP_MISMATCH');
  if ([receipt.baseCommit, receipt.integrationCommit, receipt.featureCommit].some(value => !/^[a-f0-9]{40}$/.test(value ?? ''))) fail('BASE_REFRESH_ANCESTRY_INVALID');
  const destination = path.join(repository.commonDirectory, 'leon-engineering/deliveries', taskId + '.json');
  const lock = path.join(repository.commonDirectory, 'leon-engineering/locks/integration.lock');
  try { privateWrite(lock, String(process.pid) + '\n'); } catch (error) { if (error.code === 'EEXIST') fail('TASK_LOCKED'); throw error; }
  const lockIdentity = fs.lstatSync(lock);
  let temporary;
  try {
    assertNoSymlinkAncestors(path.dirname(destination));
    const recordIdentity = fs.lstatSync(destination);
    if (!recordIdentity.isFile() || recordIdentity.isSymbolicLink() || recordIdentity.nlink !== 1) fail('DELIVERY_RECORD_INVALID');
    const before = fs.readFileSync(destination, 'utf8');
    if (JSON.stringify(JSON.parse(before)) !== JSON.stringify(receipt)) fail('DELIVERY_RECORD_CHANGED');
    const readBase = () => {
      const base = githubJson(['api', `repos/${repo}/git/ref/heads/master`], repository, options)?.object?.sha;
      if (!/^[a-f0-9]{40}$/.test(base ?? '')) fail('REMOTE_BASE_UNPROVEN');
      return base;
    };
    const checkPR = () => {
      const pr = githubJson(['pr', 'view', receipt.pullRequest.url, '--repo', repo, '--json', 'state,headRefOid,headRefName,baseRefName'], repository, options);
      // A second advance may happen before the newly prepared tip is pushed.
      // Admit only that explicitly recorded published tip, never an arbitrary ancestor.
      const allowed = publishedPrepared ? [receipt.baseRefreshPublishedHead] : [receipt.integrationCommit, receipt.baseRefreshPublishedHead].filter(Boolean);
      if (allowed.some(value => !/^[a-f0-9]{40}$/.test(value)) || pr.state !== 'OPEN' || !allowed.includes(pr.headRefOid) || pr.headRefName !== receipt.integrationBranch || pr.baseRefName !== 'master' || git(repository.repositoryRoot, ['merge-base', '--is-ancestor', pr.headRefOid, receipt.integrationCommit], options, {allowFailure: true}).status !== 0) fail('PR_HEAD_MISMATCH');
      return pr.headRefOid;
    };
    const base = readBase();
    if (base === receipt.baseCommit) fail('BASE_REFRESH_NOT_NEEDED');
    if (output(git(repository.repositoryRoot, ['rev-parse', 'refs/remotes/origin/master'], options)) !== base) fail('REMOTE_BASE_NOT_FETCHED');
    let latestFeature;
    const checkCandidate = () => {
      if (output(git(repository.repositoryRoot, ['remote', 'get-url', 'origin'], options)) !== receipt.remoteUrl) fail('REMOTE_IDENTITY_CHANGED');
      if (output(git(repository.repositoryRoot, ['rev-parse', 'refs/remotes/origin/master'], options)) !== base) fail('REMOTE_BASE_NOT_FETCHED');
      if (unpublished) {
        assertNoSymlinkAncestors(receipt.featureWorktree);
        const featureDirectory = fs.realpathSync(receipt.featureWorktree);
        const feature = worktrees(repository, options).find(item => item.worktree === featureDirectory);
        if (featureDirectory !== receipt.featureWorktree || featureDirectory === repository.repositoryRoot || !feature || feature.branch !== `refs/heads/${receipt.featureBranch}`) fail('TASK_OWNERSHIP_MISMATCH');
        for (const operation of ['MERGE_HEAD', 'CHERRY_PICK_HEAD', 'REVERT_HEAD']) {
          if (git(featureDirectory, ['rev-parse', '-q', '--verify', operation], options, {allowFailure: true}).status === 0) fail('FEATURE_REPAIR_UNVERIFIED');
        }
        if (git(repository.repositoryRoot, ['merge-base', '--is-ancestor', receipt.baseCommit, receipt.integrationCommit], options, {allowFailure: true}).status !== 0) fail('BASE_REFRESH_ANCESTRY_INVALID');
      }
      assertNoSymlinkAncestors(receipt.integrationWorktree);
      const directory = fs.realpathSync(receipt.integrationWorktree);
      const registered = worktrees(repository, options).find(item => item.worktree === directory);
      if ((unpublished && directory !== receipt.integrationWorktree) || directory === repository.repositoryRoot || !registered || registered.branch !== `refs/heads/${receipt.integrationBranch}` || discover(directory, options).commonDirectory !== repository.commonDirectory) fail('TASK_OWNERSHIP_MISMATCH');
      if (output(git(directory, ['status', '--porcelain', '--untracked-files=all'], options))) fail('WORKTREE_DIRTY');
      for (const operation of ['MERGE_HEAD', 'CHERRY_PICK_HEAD', 'REVERT_HEAD']) {
        if (git(directory, ['rev-parse', '-q', '--verify', operation], options, {allowFailure: true}).status === 0) fail('INTEGRATION_NOT_COMMITTED');
      }
      const head = output(git(directory, ['rev-parse', 'HEAD'], options));
      if (head === receipt.integrationCommit || [receipt.integrationCommit, base].some(commit => git(directory, ['merge-base', '--is-ancestor', commit, head], options, {allowFailure: true}).status !== 0) || git(directory, ['merge-base', '--is-ancestor', receipt.baseCommit, base], options, {allowFailure: true}).status !== 0) fail('BASE_REFRESH_ANCESTRY_INVALID');
      const feature = verifiedFeatureRepair({projectRoot: repository.repositoryRoot, receipt}, options);
      if (unpublished && latestFeature && feature !== latestFeature) fail('DELIVERY_RECORD_CHANGED');
      latestFeature = feature;
      return head;
    };
    const candidate = checkCandidate();
    const publishedHead = unpublished ? null : checkPR();
    if (readBase() !== base) fail('REMOTE_BASE_CHANGED');
    if (!unpublished && checkPR() !== publishedHead) fail('PR_HEAD_MISMATCH');
    if (checkCandidate() !== candidate) fail('DELIVERY_RECORD_CHANGED');
    const unchanged = () => {
      const stat = fs.lstatSync(destination);
      if (stat.isSymbolicLink() || !stat.isFile() || stat.nlink !== 1 || stat.dev !== recordIdentity.dev || stat.ino !== recordIdentity.ino || fs.readFileSync(destination, 'utf8') !== before) fail('DELIVERY_RECORD_CHANGED');
    };
    unchanged();
    const snapshot = path.join(state(repository), 'base-refresh', taskId, crypto.randomUUID() + '.json');
    privateWrite(snapshot, before);
    const updated = {...receipt, baseCommit: base, remoteCommit: unpublished ? null : base, integrationCommit: candidate, ...(unpublished ? {featureCommit: latestFeature, ...(Object.hasOwn(receipt, 'mergeSourceCommit') ? {mergeSourceCommit: latestFeature} : {})} : {baseRefreshPublishedHead: publishedHead}), verification: null, ci: {status: 'pending', runs: []}, status: 'prepared', updatedAt: new Date().toISOString()};
    temporary = destination + '.' + crypto.randomUUID() + '.tmp';
    privateWrite(temporary, JSON.stringify(updated, null, 2) + '\n');
    if (readBase() !== base) fail('REMOTE_BASE_CHANGED');
    if (!unpublished && checkPR() !== publishedHead) fail('PR_HEAD_MISMATCH');
    if (checkCandidate() !== candidate) fail('DELIVERY_RECORD_CHANGED');
    unchanged();
    fs.renameSync(temporary, destination);
    log(repository, 'delivery-base-refresh', 'PASS', undefined, {previousBase: receipt.baseCommit, base, previousCandidate: receipt.integrationCommit, publishedHead, candidate, receiptSnapshot: snapshot}, options);
    return updated;
  } finally {
    if (temporary && fs.existsSync(temporary)) fs.unlinkSync(temporary);
    const current = fs.lstatSync(lock);
    if (current.isSymbolicLink() || current.dev !== lockIdentity.dev || current.ino !== lockIdentity.ino) fail('LOCK_OWNERSHIP_CHANGED');
    fs.unlinkSync(lock);
  }
}
function advancePublishedHead(repository, receipt, options) {
  if (!receipt.baseRefreshPublishedHead || receipt.baseRefreshPublishedHead === receipt.integrationCommit || receipt.mode !== 'pr' || !['awaiting_ci', 'pushed', 'ci_failed'].includes(receipt.status)) return receipt;
  const lock = path.join(repository.commonDirectory, 'leon-engineering/locks/integration.lock');
  try { privateWrite(lock, String(process.pid) + '\n'); } catch (error) { if (error.code === 'EEXIST') fail('TASK_LOCKED'); throw error; }
  const lockIdentity = fs.lstatSync(lock);
  const destination = path.join(repository.commonDirectory, 'leon-engineering/deliveries', receipt.taskId + '.json');
  let temporary;
  try {
    assertNoSymlinkAncestors(path.dirname(destination));
    const stat = fs.lstatSync(destination);
    if (stat.isSymbolicLink() || !stat.isFile() || stat.nlink !== 1) fail('DELIVERY_RECORD_INVALID');
    const before = fs.readFileSync(destination, 'utf8');
    if (JSON.stringify(JSON.parse(before)) !== JSON.stringify(receipt)) fail('DELIVERY_RECORD_CHANGED');
    const updated = {...receipt, baseRefreshPublishedHead: receipt.integrationCommit};
    temporary = destination + '.' + crypto.randomUUID() + '.tmp';
    privateWrite(temporary, JSON.stringify(updated, null, 2) + '\n');
    const current = fs.lstatSync(destination);
    if (current.isSymbolicLink() || current.dev !== stat.dev || current.ino !== stat.ino || current.nlink !== 1 || fs.readFileSync(destination, 'utf8') !== before) fail('DELIVERY_RECORD_CHANGED');
    fs.renameSync(temporary, destination);
    log(repository, 'published-head-confirmed', 'PASS', undefined, {candidate: receipt.integrationCommit}, options);
    return updated;
  } finally {
    if (temporary && fs.existsSync(temporary)) fs.unlinkSync(temporary);
    const current = fs.lstatSync(lock);
    if (current.isSymbolicLink() || current.dev !== lockIdentity.dev || current.ino !== lockIdentity.ino) fail('LOCK_OWNERSHIP_CHANGED');
    fs.unlinkSync(lock);
  }
}
function closeoutFinalization(repository, taskId) {
  return path.join(repository.commonDirectory,'leon-engineering/resource-closeout',taskId,'git-finalization.json');
}
function writePrivateJson(destination, value) {
  const temporary=destination+'.'+crypto.randomUUID()+'.tmp';
  privateWrite(temporary,JSON.stringify(value,null,2)+'\n');
  if (fs.existsSync(destination) && fs.lstatSync(destination).isSymbolicLink()) fail('CLOSEOUT_RECEIPT_INVALID');
  fs.renameSync(temporary,destination);
}
function finishResourceReceipt(repository, taskId, required=closeoutEnabled(repository), revalidation) {
  const filename=path.join(repository.commonDirectory,'leon-engineering/resource-closeout',taskId,'receipt.json');
  if (!fs.existsSync(filename)) { if (required) fail('RESOURCE_CLOSEOUT_MISSING'); return; }
  if (fs.lstatSync(filename).isSymbolicLink()) fail('CLOSEOUT_RECEIPT_INVALID');
  const value=JSON.parse(fs.readFileSync(filename,'utf8'));
  if (value.taskId!==taskId || !value.ok || !value.cache?.ok) fail('RESOURCE_CLOSEOUT_BLOCKED');
  if(revalidation && (revalidation.taskId!==taskId || !revalidation.ok || !revalidation.cache?.ok || revalidation.previousReceiptSha256!==hashFile(filename)))fail('RESOURCE_CLOSEOUT_BLOCKED');
  writePrivateJson(filename,{...value,...(revalidation?{cache:revalidation.cache,revalidation}:{}),status:'complete',gitCleanup:true,restoreVerified:true,blocked:(value.blocked??[]).filter(row=>row.phase!=='git')});
}
function validateCompletedCloseout(repository,taskId,receipt,options) {
  const pending=closeoutFinalization(repository,taskId);
  if (!fs.existsSync(pending)) { if(closeoutEnabled(repository)) fail('CLOSEOUT_FINALIZATION_MISSING'); return; }
  if (fs.lstatSync(pending).isSymbolicLink()) fail('CLOSEOUT_RECEIPT_INVALID');
  const proof=JSON.parse(fs.readFileSync(pending,'utf8'));
  if (proof.taskId!==taskId || proof.candidateCommit!==receipt.integrationCommit || !proof.restoreVerified) fail('CLOSEOUT_FINALIZATION_UNVERIFIED');
  const partialIntent=path.join(path.dirname(pending),'partial-cleanup-intent.json');
  if(fs.existsSync(partialIntent) && !fs.existsSync(path.join(path.dirname(pending),'git-finalization-recovery.json')))fail('CLOSEOUT_FINALIZATION_UNVERIFIED');
  if (fs.existsSync(path.join(path.dirname(pending),'git-finalization-recovery.json'))) {
    validateRecoveryCompletion(repository,taskId,receipt);
    return;
  }
  if (proof.status === 'complete') {
    const filename=path.join(path.dirname(pending),'receipt.json');
    if (!fs.existsSync(filename) || fs.lstatSync(filename).isSymbolicLink()) fail('CLOSEOUT_FINALIZATION_UNVERIFIED');
    const completed=JSON.parse(fs.readFileSync(filename,'utf8'));
    if (completed.taskId!==taskId || completed.status!=='complete' || !completed.ok || !completed.cache?.ok || !completed.gitCleanup || !completed.restoreVerified) fail('CLOSEOUT_FINALIZATION_UNVERIFIED');
  } else {
    preservationAudit(repository,proof.beforeRefs,proof.beforeWorktrees,proof.managed,options,proof.verifiedPreservationRefs);
    finishResourceReceipt(repository,taskId,proof.resourceContractRequired);
    writePrivateJson(pending,{...proof,status:'complete'});
  }
}

// A recovery certificate is an additional audit epoch; never rewrite the original
// pending proof or recreate another application's ephemeral snapshot pointers.
const retiredSnapshotRef = ref => /^refs\/codex\/turn-diffs\/(?:captures\/[^/]+\/[^/]+\/base|checkpoints\/[^/]+\/[^/]+\/[^/]+\/[^/]+)$/.test(ref);
function retirementIdentity(ref,oid,currentTask,records) {
  const owner=records.delivery.value, proof=records.proof.value, resource=records.resource.value, review=records.review.value;
  const branch=ref.startsWith('refs/heads/')?ref.slice(11):ref.startsWith('refs/remotes/origin/')?ref.slice(20):null;
  if(!branch?.startsWith('codex/') || !ID.test(owner.taskId??'') || owner.taskId===currentTask || owner.mode!=='pr' || owner.status!=='cleaned' || owner.ci?.status!=='passed' || owner.verification?.status!=='passed' || !['featureWorktreeRemoved','integrationWorktreeRemoved','localBranchDeleted','remoteBranchDeleted'].every(key=>owner.cleanup?.[key]===true))return null;
  const targets=managed(owner), matches=targets.filter(row=>row.branch===branch);
  if(matches.length!==1 || !/^[a-f0-9]{40,64}$/.test(oid) || !/^[a-f0-9]{40,64}$/.test(matches[0].commit??'') || !/^[a-f0-9]{40,64}$/.test(owner.integrationCommit??''))return null;
  if(proof.taskId!==owner.taskId || proof.status!=='complete' || proof.candidateCommit!==owner.integrationCommit || proof.restoreVerified!==true || !Array.isArray(proof.managed) || proof.managed.length!==targets.length || proof.managed.some(row=>!targets.some(target=>row.branch===target.branch && row.worktree===target.worktree && row.commit===target.commit)) || proof.beforeRefs?.[ref]!==matches[0].commit)return null;
  if(resource.taskId!==owner.taskId || resource.status!=='complete' || resource.ok!==true || resource.cache?.ok!==true || resource.gitCleanup!==true || resource.restoreVerified!==true || !Array.isArray(resource.blocked) || resource.blocked.length || review.status!=='PASS' || review.candidateCommit!==owner.integrationCommit || review.reviewedCommit!==owner.integrationCommit)return null;
  return {ref,oid,ownerTaskId:owner.taskId,branchCommit:matches[0].commit,candidateCommit:owner.integrationCommit,deliverySha256:records.delivery.sha256,proofSha256:records.proof.sha256,resourceSha256:records.resource.sha256,reviewSha256:records.review.sha256};
}
function retiredDelivery(repository,taskId,receipt,ref,oid,options) {
  const directory=path.join(repository.commonDirectory,'leon-engineering/deliveries');
  assertNoSymlinkAncestors(directory);
  if(!fs.lstatSync(directory,{throwIfNoEntry:false})?.isDirectory())fail('UNRELATED_REF_CHANGED');
  const files=fs.readdirSync(directory).filter(name=>name.endsWith('.json'));
  if(files.length>2000)fail('CLOSEOUT_RECOVERY_SCAN_LIMIT');
  const candidates=[];
  for(const name of files) {
    const delivery=recoveryJson(path.join(directory,name));
    const owner=delivery.value;
    if(owner.taskId===taskId || !ID.test(owner.taskId??'') || name!==owner.taskId+'.json')continue;
    if(!managed(owner).some(row=>ref===`refs/heads/${row.branch}` || ref===`refs/remotes/origin/${row.branch}`))continue;
    candidates.push({delivery,owner});
  }
  if(candidates.length!==1)fail('UNRELATED_REF_CHANGED');
  const {delivery,owner}=candidates[0], base=path.join(repository.commonDirectory,'leon-engineering');
  if(owner.repositoryRoot!==repository.repositoryRoot || owner.remote!==receipt.remote || owner.remoteUrl!==receipt.remoteUrl || owner.defaultBranch!==receipt.defaultBranch)fail('UNRELATED_REF_CHANGED');
  const records={delivery,proof:recoveryJson(path.join(base,'resource-closeout',owner.taskId,'git-finalization.json')),resource:recoveryJson(path.join(base,'resource-closeout',owner.taskId,'receipt.json')),review:recoveryJson(path.join(base,'git-safety/reviews',owner.taskId+'.json'))};
  const witness=retirementIdentity(ref,oid,taskId,records);
  if(!witness || output(git(repository.repositoryRoot,['cat-file','-t',oid],options))!=='commit' || git(repository.repositoryRoot,['merge-base','--is-ancestor',oid,witness.branchCommit],options,{allowFailure:true}).status!==0 || git(repository.repositoryRoot,['merge-base','--is-ancestor',witness.branchCommit,owner.integrationCommit],options,{allowFailure:true}).status!==0 || git(repository.repositoryRoot,['merge-base','--is-ancestor',owner.integrationCommit,`refs/remotes/${receipt.remote}/${receipt.defaultBranch}`],options,{allowFailure:true}).status!==0)fail('UNRELATED_REF_CHANGED');
  return {witness:{...witness,ancestorVerified:true},records};
}
function retirementWorktreeMatches(worktree,ref,records) {
  const targets=managed(records.delivery.value), target=targets.find(row=>`refs/heads/${row.branch}`===ref && row.worktree===worktree);
  return Boolean(target && records.proof.value.beforeWorktrees?.some(row=>row.worktree===worktree && row.branch===ref && row.HEAD===target.commit && !row.bare));
}
function recoveryJson(filename) {
  assertNoSymlinkAncestors(filename);
  const fd=fs.openSync(filename,fs.constants.O_RDONLY|fs.constants.O_NOFOLLOW|(fs.constants.O_NONBLOCK??0));
  try {
    const info=fs.fstatSync(fd);
    if(!info.isFile() || info.nlink!==1 || info.mode&0o077 || info.size>16*1024*1024 || typeof process.getuid==='function' && info.uid!==process.getuid())fail('CLOSEOUT_RECOVERY_RECORD_INVALID');
    const bytes=fs.readFileSync(fd), after=fs.lstatSync(filename);
    if(after.isSymbolicLink() || after.ino!==info.ino || after.dev!==info.dev || after.size!==info.size || after.mtimeMs!==info.mtimeMs || bytes.length!==info.size)fail('CLOSEOUT_RECOVERY_STALE');
    return {value:JSON.parse(bytes),bytes,sha256:sha256(bytes)};
  } finally {fs.closeSync(fd);}
}
function validateRecoveryCompletion(repository,taskId,receipt) {
  const original=closeoutFinalization(repository,taskId), directory=path.dirname(original);
  const proof=recoveryJson(original), certificate=recoveryJson(path.join(directory,'git-finalization-recovery.json')).value;
  if(proof.value.taskId!==taskId || proof.value.candidateCommit!==receipt.integrationCommit || proof.value.restoreVerified!==true || proof.value.status!=='pending')fail('CLOSEOUT_FINALIZATION_UNVERIFIED');
  if(certificate.schemaVersion!==1 || certificate.taskId!==taskId || certificate.candidateCommit!==receipt.integrationCommit || certificate.originalProofSha256!==proof.sha256 || !/^recovery-epochs\/[a-f0-9-]{36}\/epoch.json$/.test(certificate.epoch??''))fail('CLOSEOUT_FINALIZATION_UNVERIFIED');
  const record=recoveryJson(path.join(directory,certificate.epoch));
  const saved=recoveryJson(path.join(path.dirname(path.join(directory,certificate.epoch)),'original-proof.json'));
  const epoch=record.value;
  if(record.sha256!==certificate.epochSha256 || saved.sha256!==proof.sha256 || epoch.originalProofSha256!==proof.sha256 || epoch.taskId!==taskId || epoch.candidateCommit!==receipt.integrationCommit || epoch.status!=='complete' || epoch.restoreVerified!==true || !/^[a-f0-9]{64}$/.test(epoch.backupManifestSha256??'') || !Array.isArray(epoch.retiredSnapshots) || !Array.isArray(epoch.retiredDeliveries) || !Array.isArray(epoch.retiredWorktrees) || (!epoch.retiredSnapshots.length && !epoch.retiredDeliveries.length && !epoch.retiredWorktrees.length && epoch.kind!=='partial_cleanup') || epoch.retiredSnapshots.some(row=>!retiredSnapshotRef(row.ref) || proof.value.verifiedPreservationRefs?.[row.ref]!==row.oid || proof.value.beforeRefs?.[row.ref]!==row.oid))fail('CLOSEOUT_FINALIZATION_UNVERIFIED');
  if(epoch.kind==='partial_cleanup') {
    const intentRecord=recoveryJson(path.join(directory,'partial-cleanup-intent.json')), intent=intentRecord.value;
    const originalDelivery=recoveryJson(path.join(directory,'partial-cleanup-original-delivery.json'));
    const actual=recoveryJson(path.join(repository.commonDirectory,'leon-engineering/deliveries',taskId+'.json'));
    if(intent.taskId!==taskId || intent.candidateCommit!==receipt.integrationCommit || intent.originalProofSha256!==proof.sha256 || intent.originalDeliverySha256!==originalDelivery.sha256 || epoch.originalDeliverySha256!==originalDelivery.sha256 || intentRecord.sha256!==epoch.originalIntentSha256 || !sameCleanupDelivery(actual.value,originalDelivery.value) || actual.sha256!==epoch.finalDeliverySha256 || JSON.stringify(actual.value)!==JSON.stringify(receipt))fail('CLOSEOUT_FINALIZATION_UNVERIFIED');
    const manifest=readManifest(epoch.backupDirectory);
    if(manifest.hash!==epoch.backupManifestSha256 || manifest.manifest.repositoryKey!==repositoryKey(repository.commonDirectory))fail('CLOSEOUT_FINALIZATION_UNVERIFIED');
    assertPartialPathsAbsent(repository,receipt,{});
  }
  for(const [row,isWorktree] of [...epoch.retiredDeliveries.map(row=>[row,false]),...epoch.retiredWorktrees.map(row=>[row,true])]) {
    if(!ID.test(row.ownerTaskId??'') || row.ancestorVerified!==true || proof.value.verifiedPreservationRefs?.[row.ref]!==row.oid || proof.value.beforeRefs?.[row.ref]!==row.oid)fail('CLOSEOUT_FINALIZATION_UNVERIFIED');
    const retirementDirectory=path.join(path.dirname(path.join(directory,certificate.epoch)),'retired-deliveries',row.ownerTaskId);
    const records=Object.fromEntries(['delivery','proof','resource','review'].map(kind=>[kind,recoveryJson(path.join(retirementDirectory,kind+'.json'))]));
    const identity=retirementIdentity(row.ref,row.oid,taskId,records);
    if(isWorktree && (!proof.value.beforeWorktrees?.some(saved=>saved.worktree===row.worktree && saved.branch===row.ref && saved.HEAD===row.oid && !saved.bare) || !retirementWorktreeMatches(row.worktree,row.ref,records)))fail('CLOSEOUT_FINALIZATION_UNVERIFIED');
    if(!identity || records.delivery.value.repositoryRoot!==repository.repositoryRoot || records.delivery.value.remoteUrl!==receipt.remoteUrl || records.delivery.value.remote!==receipt.remote || records.delivery.value.defaultBranch!==receipt.defaultBranch || JSON.stringify({...identity,ancestorVerified:true,...(isWorktree?{worktree:row.worktree}:{})})!==JSON.stringify(row))fail('CLOSEOUT_FINALIZATION_UNVERIFIED');
  }
  const resource=recoveryJson(path.join(directory,'receipt.json')).value;
  if(resource.taskId!==taskId || resource.status!=='complete' || !resource.ok || !resource.cache?.ok || !resource.gitCleanup || !resource.restoreVerified)fail('CLOSEOUT_FINALIZATION_UNVERIFIED');
  const originalResource=recoveryJson(path.join(path.dirname(path.join(directory,certificate.epoch)),'original-resource-receipt.json'));
  const revalidation=epoch.resourceRevalidation;
  if(!revalidation?.ok || revalidation.taskId!==taskId || revalidation.candidateCommit!==receipt.integrationCommit || !revalidation.cache?.ok || revalidation.previousReceiptSha256!==originalResource.sha256 || JSON.stringify(resource.revalidation)!==JSON.stringify(revalidation) || JSON.stringify(resource.cache)!==JSON.stringify(revalidation.cache))fail('CLOSEOUT_FINALIZATION_UNVERIFIED');
}

function sameCleanupDelivery(current,original) {
  if(current.status!=='cleaned' || !['featureWorktreeRemoved','integrationWorktreeRemoved','localBranchDeleted','remoteBranchDeleted'].every(key=>current.cleanup?.[key]===true) || !Number.isFinite(Date.parse(current.updatedAt)))return false;
  const normalized={...current,status:original.status};
  for(const key of ['cleanup','updatedAt']) {
    if(Object.hasOwn(original,key))normalized[key]=original[key];else delete normalized[key];
  }
  return JSON.stringify(normalized)===JSON.stringify(original);
}
function syncRecoveryPath(filename, directory=false) {
  const fd=fs.openSync(filename,fs.constants.O_RDONLY|fs.constants.O_NOFOLLOW|(directory?fs.constants.O_DIRECTORY:0));
  try {fs.fsyncSync(fd);} finally {fs.closeSync(fd);}
}
function writeRecoveryJson(filename,value) {
  writePrivateJson(filename,value);syncRecoveryPath(filename);syncRecoveryPath(path.dirname(filename),true);
}
function assertPartialWorktreesRetired(repository,receipt,options) {
  const registered=worktrees(repository,options);
  for(const row of managed(receipt)) {
    if(row.worktree===repository.repositoryRoot || fs.lstatSync(row.worktree,{throwIfNoEntry:false}) || registered.some(item=>item.worktree===row.worktree || item.branch===`refs/heads/${row.branch}`))fail('PARTIAL_CLEANUP_WORKTREE_PRESENT');
  }
}
function assertPartialPathsAbsent(repository,receipt,options) {
  assertPartialWorktreesRetired(repository,receipt,options);
  const current=refs(repository,options);
  for(const row of managed(receipt)) {
    if(current[`refs/heads/${row.branch}`])fail('PARTIAL_CLEANUP_REF_PRESENT');
  }
}
function partialRemoteRefs(repository,receipt,options) {
  const repo=githubRepo(receipt), result={};
  for(const row of managed(receipt)) {
    const ref=`refs/heads/${row.branch}`;
    const matches=githubJson(['api',`repos/${repo}/git/matching-refs/heads/${row.branch}`],repository,options);
    if(!Array.isArray(matches))fail('PARTIAL_CLEANUP_REMOTE_UNPROVEN');
    const exact=matches.filter(item=>item.ref===ref);
    if(exact.length>1 || exact.length && exact[0].object?.sha!==row.commit)fail('REMOTE_TASK_COMMIT_MISMATCH');
    if(exact.length)result[ref]=row.commit;
  }
  return result;
}
function partialCleanupPlan(repository,taskId,backupDirectory,current,options) {
  const directory=path.dirname(closeoutFinalization(repository,taskId));
  const deliveryFile=path.join(repository.commonDirectory,'leon-engineering/deliveries',taskId+'.json');
  const delivery=recoveryJson(deliveryFile), proof=recoveryJson(closeoutFinalization(repository,taskId));
  if(JSON.stringify(delivery.value)!==JSON.stringify(current))fail('DELIVERY_RECORD_CHANGED');
  const intentFile=path.join(directory,'partial-cleanup-intent.json');
  const intent=fs.existsSync(intentFile)?recoveryJson(intentFile).value:null;
  const original=intent?recoveryJson(path.join(directory,'partial-cleanup-original-delivery.json')):delivery;
  const receipt=original.value;
  if(receipt.schemaVersion!==1 || receipt.status!=='ci_passed' || receipt.ci?.status!=='passed' || receipt.verification?.status!=='passed' || receipt.mode!=='pr' || receipt.taskId!==taskId || receipt.repositoryRoot!==repository.repositoryRoot)fail('CLOSEOUT_RECOVERY_NOT_PENDING');
  if(intent && (intent.taskId!==taskId || intent.candidateCommit!==receipt.integrationCommit || intent.originalDeliverySha256!==original.sha256 || intent.originalProofSha256!==proof.sha256 || delivery.sha256!==original.sha256 && !sameCleanupDelivery(current,receipt)))fail('CLOSEOUT_RECOVERY_STALE');
  assertReviewed(repository,receipt);
  const owned=managed(receipt), local=refs(repository,options), registered=worktrees(repository,options);
  if(proof.value.taskId!==taskId || proof.value.status!=='pending' || !proof.value.restoreVerified || proof.value.candidateCommit!==receipt.integrationCommit || !proof.value.beforeRefs || !Array.isArray(proof.value.beforeWorktrees) || !Array.isArray(proof.value.managed) || owned.length>128 || new Set(owned.map(row=>row.branch)).size!==owned.length || new Set(owned.map(row=>row.worktree)).size!==owned.length || proof.value.managed.length!==owned.length || proof.value.managed.some(row=>!owned.some(target=>row.branch===target.branch && row.worktree===target.worktree && row.commit===target.commit)))fail('CLOSEOUT_FINALIZATION_UNVERIFIED');
  for(const row of owned) {
    if(!row.branch?.startsWith(`codex/${taskId}-`) && !new RegExp(`^codex/integrate-${taskId}(?:-r[0-9]+)?$`).test(row.branch??''))fail('TASK_OWNERSHIP_MISMATCH');
    if(!path.isAbsolute(row.worktree??'') || !/^[a-f0-9]{40}$/.test(row.commit??'') || git(repository.repositoryRoot,['check-ref-format',`refs/heads/${row.branch}`],options,{allowFailure:true}).status!==0)fail('TASK_OWNERSHIP_MISMATCH');
    if(row.worktree===repository.repositoryRoot || fs.lstatSync(row.worktree,{throwIfNoEntry:false}) || registered.some(item=>item.worktree===row.worktree || item.branch===`refs/heads/${row.branch}`))fail('PARTIAL_CLEANUP_WORKTREE_PRESENT');
    const ref=`refs/heads/${row.branch}`;
    if(proof.value.beforeRefs?.[ref]!==row.commit || local[ref] && local[ref]!==row.commit)fail('TASK_COMMIT_MISMATCH');
    if(output(git(repository.repositoryRoot,['cat-file','-t',row.commit],options))!=='commit' || git(repository.repositoryRoot,['merge-base','--is-ancestor',row.commit,'refs/remotes/origin/master'],options,{allowFailure:true}).status!==0)fail('BRANCH_UNMERGED');
  }
  preservationAudit(repository,proof.value.beforeRefs,proof.value.beforeWorktrees,owned,options,proof.value.verifiedPreservationRefs);
  const backup=path.resolve(backupDirectory??''), root=path.resolve(options.backupRoot??path.join(os.homedir(),'.codex/backups/rwb-git-safety'));
  assertNoSymlinkAncestors(backup);
  if(path.dirname(backup)!==root || !/^[a-f0-9-]{36}$/.test(path.basename(backup)))fail('CLOSEOUT_RECOVERY_BACKUP_INVALID');
  const manifest=readManifest(backup);
  if(manifest.manifest.schemaVersion!==2 || manifest.manifest.repositoryKey!==repositoryKey(repository.commonDirectory) || !manifest.manifest.restoreVerified || Object.entries(proof.value.beforeRefs).some(([ref,oid])=>manifest.manifest.preservationRefs?.[ref]!==oid) || !manifest.manifest.worktrees.some(row=>row.path===repository.repositoryRoot) || owned.some(row=>!proof.value.beforeWorktrees.some(saved=>saved.worktree===row.worktree && saved.HEAD===row.commit && saved.branch===`refs/heads/${row.branch}`) || !manifest.manifest.worktrees.some(saved=>saved.path===row.worktree && saved.head===row.commit && saved.branch===`refs/heads/${row.branch}`)))fail('CLOSEOUT_RECOVERY_BACKUP_INVALID');
  const resource=recoveryJson(path.join(directory,'receipt.json'));
  if(resource.value.taskId!==taskId || !resource.value.ok || !resource.value.cache?.ok || !Array.isArray(resource.value.blocked) || resource.value.blocked.some(row=>row.phase!=='git'))fail('RESOURCE_CLOSEOUT_BLOCKED');
  const summary=githubJson(['pr','view',receipt.pullRequest.url,'--repo',githubRepo(receipt),'--json','state,headRefOid,baseRefName,mergeCommit'],repository,options);
  if(summary.state!=='MERGED' || summary.headRefOid!==receipt.integrationCommit || summary.baseRefName!=='master' || !/^[a-f0-9]{40}$/.test(summary.mergeCommit?.oid??''))fail('MERGE_IDENTITY_UNPROVEN');
  if(git(repository.repositoryRoot,['merge-base','--is-ancestor',summary.mergeCommit.oid,'refs/remotes/origin/master'],options,{allowFailure:true}).status!==0)fail('MERGE_IDENTITY_UNPROVEN');
  const remote=partialRemoteRefs(repository,receipt,options);
  if(current.status==='cleaned' && (Object.keys(remote).length || owned.some(row=>local[`refs/heads/${row.branch}`])))fail('CLOSEOUT_RECOVERY_STALE');
  const plan={schemaVersion:1,kind:'partial_cleanup',taskId,candidateCommit:receipt.integrationCommit,originalProofSha256:proof.sha256,originalDeliverySha256:original.sha256,currentDeliverySha256:delivery.sha256,backupDirectory:backup,backupManifestSha256:manifest.hash,resourceSha256:resource.sha256,localRefs:Object.fromEntries(owned.filter(row=>local[`refs/heads/${row.branch}`]).map(row=>[`refs/heads/${row.branch}`,row.commit])),remoteRefs:remote};
  return {plan,previewSha256:sha256(JSON.stringify(plan)),proof,original,deliveryFile,directory,receipt};
}
async function recoverPartialCleanup(repository,input,controller,options) {
  const {taskId,backupDirectory,apply,previewSha256}=input;
  const read=()=>partialCleanupPlan(repository,taskId,backupDirectory,controller.readDeliveryReceipt({projectRoot:repository.repositoryRoot,taskId}),options);
  const first=read();
  if(!apply)return {...first.plan,status:'preview',previewSha256:first.previewSha256};
  if(previewSha256!==first.previewSha256)fail('CLOSEOUT_RECOVERY_STALE');
  return withBackupLock(path.dirname(first.plan.backupDirectory),()=>{
    verifyBackupDirectory(first.plan.backupDirectory,options);
    options.afterPartialBackupVerified?.();
    if(read().previewSha256!==previewSha256)fail('CLOSEOUT_RECOVERY_STALE');
    const ci=reviewedStatus(repository,first.receipt,undefined,options);
    if(ci.status!=='passed')fail('MERGE_GATES_NOT_PASSED');
    quota(repository,options);
    const intentPath=path.join(first.directory,'partial-cleanup-intent.json');
    const originalPath=path.join(first.directory,'partial-cleanup-original-delivery.json');
    if(!fs.existsSync(originalPath))fs.writeFileSync(originalPath,first.original.bytes,{flag:'wx',mode:0o600});
    if(recoveryJson(originalPath).sha256!==first.original.sha256)fail('CLOSEOUT_RECOVERY_STALE');
    syncRecoveryPath(originalPath);syncRecoveryPath(first.directory,true);
    if(!fs.existsSync(intentPath))writeRecoveryJson(intentPath,{schemaVersion:1,taskId,candidateCommit:first.receipt.integrationCommit,originalProofSha256:first.proof.sha256,originalDeliverySha256:first.original.sha256});
    const acceptedIntent=recoveryJson(intentPath);
    const updates=Object.entries(first.plan.remoteRefs).map(([name,beforeOid])=>({name,beforeOid,afterOid:'0'.repeat(40),force:false}));
    if(updates.length) {
      const repo=githubRepo(first.receipt), identity=githubJson(['api',`repos/${repo}`],repository,options);
      if(typeof identity.node_id!=='string' || !identity.node_id)fail('REMOTE_IDENTITY_CHANGED');
      const request=path.join(first.directory,'partial-remote-update-'+crypto.randomUUID()+'.json');
      writeRecoveryJson(request,{query:'mutation($input: UpdateRefsInput!) { updateRefs(input: $input) { clientMutationId } }',variables:{input:{repositoryId:identity.node_id,clientMutationId:crypto.randomUUID(),refUpdates:updates}}});
      const result=githubJson(['api','graphql','--input',request],repository,options);
      if(result.errors?.length || !result.data?.updateRefs)fail('PARTIAL_CLEANUP_REMOTE_UPDATE_UNCONFIRMED');
    }
    if(Object.keys(partialRemoteRefs(repository,first.receipt,options)).length)fail('PARTIAL_CLEANUP_REMOTE_UPDATE_UNCONFIRMED');
    options.afterPartialRemoteRetired?.();
    if(recoveryJson(first.deliveryFile).sha256!==first.plan.currentDeliverySha256 || recoveryJson(closeoutFinalization(repository,taskId)).sha256!==first.proof.sha256)fail('CLOSEOUT_RECOVERY_STALE');
    if(Object.keys(partialRemoteRefs(repository,first.receipt,options)).length)fail('PARTIAL_CLEANUP_REMOTE_UPDATE_UNCONFIRMED');
    assertPartialWorktreesRetired(repository,first.receipt,options);
    const local=Object.entries(first.plan.localRefs);
    if(local.length)git(repository.repositoryRoot,['update-ref','--no-deref','--stdin'],options,{input:'start\n'+local.map(([ref,oid])=>`delete ${ref} ${oid}\n`).join('')+'prepare\ncommit\n'});
    assertPartialPathsAbsent(repository,first.receipt,options);
    preservationAudit(repository,first.proof.value.beforeRefs,first.proof.value.beforeWorktrees,managed(first.receipt),options,first.proof.value.verifiedPreservationRefs);
    const epochs=path.join(first.directory,'recovery-epochs');privateDirectory(epochs);syncRecoveryPath(first.directory,true);
    const id=crypto.randomUUID(), directory=path.join(epochs,id);fs.mkdirSync(directory,{mode:0o700});
    syncRecoveryPath(epochs,true);
    fs.writeFileSync(path.join(directory,'original-proof.json'),first.proof.bytes,{flag:'wx',mode:0o600});
    syncRecoveryPath(path.join(directory,'original-proof.json'));
    const beforeResource=recoveryJson(path.join(first.directory,'receipt.json'));
    fs.writeFileSync(path.join(directory,'original-resource-receipt.json'),beforeResource.bytes,{flag:'wx',mode:0o600});
    syncRecoveryPath(path.join(directory,'original-resource-receipt.json'));syncRecoveryPath(directory,true);
    const cleaned={...first.receipt,status:'cleaned',cleanup:{...first.receipt.cleanup,...Object.fromEntries(['featureWorktreeRemoved','integrationWorktreeRemoved','localBranchDeleted','remoteBranchDeleted'].map(key=>[key,true]))},updatedAt:new Date().toISOString()};
    if(recoveryJson(first.deliveryFile).sha256!==first.plan.currentDeliverySha256)fail('CLOSEOUT_RECOVERY_STALE');
    writeRecoveryJson(first.deliveryFile,cleaned);
    const committed=recoveryJson(first.deliveryFile);
    options.afterPartialReceiptCommitted?.();
    const actual=controller.validateCleanedDelivery({projectRoot:repository.repositoryRoot,taskId});
    if(recoveryJson(first.deliveryFile).sha256!==committed.sha256 || JSON.stringify(actual)!==JSON.stringify(cleaned))fail('CLOSEOUT_RECOVERY_STALE');
    const resources=resourcePhase(repository,taskId,'revalidate',options);
    if(!resources?.ok || resources.taskId!==taskId || resources.candidateCommit!==cleaned.integrationCommit || !resources.cache?.ok || resources.previousReceiptSha256!==beforeResource.sha256)fail('RESOURCE_CLOSEOUT_BLOCKED');
    fsck(repository,options);
    const validateFinal=()=>{
      const observed=read();
      if(observed.proof.sha256!==first.proof.sha256 || observed.original.sha256!==first.original.sha256 || observed.plan.backupManifestSha256!==first.plan.backupManifestSha256 || observed.plan.currentDeliverySha256!==committed.sha256 || recoveryJson(intentPath).sha256!==acceptedIntent.sha256)fail('CLOSEOUT_RECOVERY_STALE');
      // read() finishes with network observations. Recheck local paths and refs
      // afterwards; fsck alone does not prove preservation of reference names.
      assertPartialPathsAbsent(repository,first.receipt,options);
      preservationAudit(repository,first.proof.value.beforeRefs,first.proof.value.beforeWorktrees,managed(first.receipt),options,first.proof.value.verifiedPreservationRefs);
      if(recoveryJson(first.deliveryFile).sha256!==committed.sha256 || recoveryJson(closeoutFinalization(repository,taskId)).sha256!==first.proof.sha256 || recoveryJson(intentPath).sha256!==acceptedIntent.sha256 || readManifest(first.plan.backupDirectory).hash!==first.plan.backupManifestSha256)fail('CLOSEOUT_RECOVERY_STALE');
    };
    validateFinal();
    const epoch={...first.plan,status:'complete',restoreVerified:true,originalDeliverySha256:first.original.sha256,originalIntentSha256:acceptedIntent.sha256,finalDeliverySha256:committed.sha256,retiredSnapshots:[],retiredDeliveries:[],retiredWorktrees:[],resourceRevalidation:resources,verifiedAt:new Date().toISOString()};
    const payload=JSON.stringify(epoch,null,2)+'\n';fs.writeFileSync(path.join(directory,'epoch.json'),payload,{flag:'wx',mode:0o600});
    syncRecoveryPath(path.join(directory,'epoch.json'));syncRecoveryPath(directory,true);
    finishResourceReceipt(repository,taskId,true,resources);
    syncRecoveryPath(path.join(first.directory,'receipt.json'));syncRecoveryPath(first.directory,true);
    validateFinal();
    const certificate=path.join(first.directory,'git-finalization-recovery.json');
    if(fs.lstatSync(certificate,{throwIfNoEntry:false}))fail('CLOSEOUT_RECOVERY_STALE');
    writeRecoveryJson(certificate,{schemaVersion:1,taskId,candidateCommit:cleaned.integrationCommit,originalProofSha256:first.proof.sha256,epoch:`recovery-epochs/${id}/epoch.json`,epochSha256:sha256(payload)});
    validateRecoveryCompletion(repository,taskId,recoveryJson(first.deliveryFile).value);
    log(repository,'closeout-partial-recover','PASS',undefined,{backup:first.plan.backupDirectory},options);
    return {taskId,status:'cleaned',restoreVerified:true,kind:'partial_cleanup'};
  });
}
function recoveryPlan(repository,taskId,backupDirectory,receipt,options) {
  if(receipt.status!=='cleaned' || receipt.ci?.status!=='passed' || receipt.verification?.status!=='passed' || !['featureWorktreeRemoved','integrationWorktreeRemoved','localBranchDeleted','remoteBranchDeleted'].every(key=>receipt.cleanup?.[key]===true))fail('CLOSEOUT_RECOVERY_NOT_PENDING');
  assertReviewed(repository,receipt);
  const original=closeoutFinalization(repository,taskId), saved=recoveryJson(original), proof=saved.value;
  if(proof.taskId!==taskId || proof.candidateCommit!==receipt.integrationCommit || proof.status!=='pending' || proof.restoreVerified!==true || !proof.beforeRefs || !Array.isArray(proof.beforeWorktrees) || !Array.isArray(proof.managed))fail('CLOSEOUT_FINALIZATION_UNVERIFIED');
  const owned=managed(receipt);
  if(proof.managed.length!==owned.length || proof.managed.some(row=>!owned.some(target=>row.branch===target.branch && row.worktree===target.worktree && row.commit===target.commit)))fail('CLOSEOUT_FINALIZATION_UNVERIFIED');
  const current=refs(repository,options), managedRefs=new Set(proof.managed.flatMap(row=>[`refs/heads/${row.branch}`,`refs/remotes/origin/${row.branch}`]));
  const retiredSnapshots=[], retiredDeliveries=[], retiredWorktrees=[], retirementRecords={};
  const remember=retired=>{
    const prior=retirementRecords[retired.witness.ownerTaskId];
    if(prior && Object.keys(prior).some(kind=>prior[kind].sha256!==retired.records[kind].sha256))fail('CLOSEOUT_RECOVERY_STALE');
    retirementRecords[retired.witness.ownerTaskId]=retired.records;
  };
  for(const [ref,oid] of Object.entries(proof.beforeRefs)) {
    if(current[ref] || managedRefs.has(ref))continue;
    if(proof.verifiedPreservationRefs?.[ref]!==oid)fail('UNRELATED_REF_CHANGED');
    if(retiredSnapshotRef(ref)) {
      if(output(git(repository.repositoryRoot,['cat-file','-t',oid],options))!=='tree')fail('UNRELATED_REF_CHANGED');
      retiredSnapshots.push({ref,oid});
    } else {
      const retired=retiredDelivery(repository,taskId,receipt,ref,oid,options);
      remember(retired);retiredDeliveries.push(retired.witness);
    }
  }
  const currentWorktrees=worktrees(repository,options);
  for(const row of proof.beforeWorktrees) {
    if(proof.managed.some(own=>own.worktree===row.worktree) || currentWorktrees.some(current=>current.worktree===row.worktree))continue;
    if(row.bare || proof.beforeRefs[row.branch]!==row.HEAD || fs.lstatSync(row.worktree,{throwIfNoEntry:false}))fail('UNRELATED_WORKTREE_CHANGED');
    let retired;
    try {retired=retiredDelivery(repository,taskId,receipt,row.branch,row.HEAD,options);}catch(error){if(error.code==='UNRELATED_REF_CHANGED')fail('UNRELATED_WORKTREE_CHANGED');throw error;}
    if(!retirementWorktreeMatches(row.worktree,row.branch,retired.records))fail('UNRELATED_WORKTREE_CHANGED');
    remember(retired);retiredWorktrees.push({...retired.witness,worktree:row.worktree});
  }
  if(!retiredSnapshots.length && !retiredDeliveries.length && !retiredWorktrees.length || retiredSnapshots.length+retiredDeliveries.length+retiredWorktrees.length>128)fail('CLOSEOUT_RECOVERY_NOT_PENDING');
  const remaining=Object.fromEntries(Object.entries(proof.beforeRefs).filter(([ref])=>![...retiredSnapshots,...retiredDeliveries].some(row=>row.ref===ref)));
  // Every ordinary deletion, divergence and unrelated worktree change retains
  // the existing audit. Only the named archived tree pointers get a new witness.
  preservationAudit(repository,remaining,proof.beforeWorktrees.filter(row=>!retiredWorktrees.some(retired=>retired.worktree===row.worktree)),proof.managed,options,proof.verifiedPreservationRefs);
  const root=path.resolve(options.backupRoot??path.join(os.homedir(),'.codex/backups/rwb-git-safety'));
  const backup=path.resolve(backupDirectory??'');assertNoSymlinkAncestors(backup);
  if(path.dirname(backup)!==root || !/^[a-f0-9-]{36}$/.test(path.basename(backup)))fail('CLOSEOUT_RECOVERY_BACKUP_INVALID');
  const {manifest,hash}=readManifest(backup);
  const savedManaged=proof.beforeWorktrees.filter(row=>proof.managed.some(target=>target.worktree===row.worktree));
  if(manifest.schemaVersion!==2 || manifest.repositoryKey!==repositoryKey(repository.commonDirectory) || !manifest.worktrees.some(row=>row.path===repository.repositoryRoot) || savedManaged.some(row=>!manifest.worktrees.some(saved=>saved.path===row.worktree && saved.head===row.HEAD && saved.branch===(row.branch??null))) || Object.entries(proof.verifiedPreservationRefs??{}).some(([ref,oid])=>manifest.preservationRefs[ref]!==oid) || Object.entries(proof.beforeRefs).some(([ref,oid])=>manifest.preservationRefs[ref]!==oid))fail('CLOSEOUT_RECOVERY_BACKUP_INVALID');
  const resource=recoveryJson(path.join(path.dirname(original),'receipt.json')).value;
  if(resource.taskId!==taskId || !resource.ok || !resource.cache?.ok || !Array.isArray(resource.blocked) || resource.blocked.some(row=>row.phase!=='git'))fail('RESOURCE_CLOSEOUT_BLOCKED');
  const plan={schemaVersion:1,taskId,candidateCommit:receipt.integrationCommit,originalProofSha256:saved.sha256,backupDirectory:backup,backupManifestSha256:hash,retiredSnapshots:retiredSnapshots.sort((a,b)=>a.ref.localeCompare(b.ref)),retiredDeliveries:retiredDeliveries.sort((a,b)=>a.ref.localeCompare(b.ref)),retiredWorktrees:retiredWorktrees.sort((a,b)=>a.worktree.localeCompare(b.worktree))};
  return {plan,proof,saved,original,retirementRecords,previewSha256:sha256(JSON.stringify(plan))};
}
export async function recoverCloseoutFinalization({projectRoot,taskId,backupDirectory,apply=false,previewSha256},options={}) {
  options={...options,readOnlyGit:true};
  if(!ID.test(taskId??''))fail('DELIVERY_ARGUMENT_INVALID');
  selectGitPath({...options,mutate:apply});
  const perform=async repository=>{
    const controller=options.controller??await import(pathToFileURL(CONTROLLER).href);
    const common={projectRoot:repository.repositoryRoot,taskId};
    const local=controller.readDeliveryReceipt(common);
    if(local.repositoryRoot!==repository.repositoryRoot || local.remote!=='origin' || local.defaultBranch!=='master' || output(git(repository.repositoryRoot,['remote','get-url',local.remote],options))!==local.remoteUrl)fail('REMOTE_IDENTITY_CHANGED');
    assertReviewed(repository,local);
    fsck(repository,options);
    const partialIntent=path.join(path.dirname(closeoutFinalization(repository,taskId)),'partial-cleanup-intent.json');
    if(local.status==='ci_passed' || fs.existsSync(partialIntent)) {
      const certificate=path.join(path.dirname(closeoutFinalization(repository,taskId)),'git-finalization-recovery.json');
      if(local.status==='cleaned' && fs.existsSync(certificate)) {
        const actual=apply?controller.validateCleanedDelivery(common):local;
        validateRecoveryCompletion(repository,taskId,actual);
        if(!apply && Object.keys(partialRemoteRefs(repository,actual,options)).length)fail('PARTIAL_CLEANUP_REMOTE_UPDATE_UNCONFIRMED');
        return {taskId,status:'cleaned',restoreVerified:true};
      }
      return recoverPartialCleanup(repository,{taskId,backupDirectory,apply,previewSha256},controller,options);
    }
    // The shared validateCleanedDelivery performs fetch: only the locked apply
    // lane may use it. Preview reads local records and audits local Git only.
    const receipt=apply?controller.validateCleanedDelivery(common):local;
    assertReviewed(repository,receipt);
    const certificate=path.join(path.dirname(closeoutFinalization(repository,taskId)),'git-finalization-recovery.json');
    if(fs.existsSync(certificate)){validateRecoveryCompletion(repository,taskId,receipt);return {taskId,status:'cleaned',restoreVerified:true};}
    const first=recoveryPlan(repository,taskId,backupDirectory,receipt,options);
    if(!apply)return {...first.plan,status:'preview',previewSha256:first.previewSha256};
    if(previewSha256!==first.previewSha256)fail('CLOSEOUT_RECOVERY_STALE');
    return withBackupLock(path.dirname(first.plan.backupDirectory),()=>{
      verifyBackupDirectory(first.plan.backupDirectory,options);
      options.afterRecoveryVerified?.();
      const after=recoveryPlan(repository,taskId,backupDirectory,receipt,options);
      if(after.previewSha256!==previewSha256)fail('CLOSEOUT_RECOVERY_STALE');
      const resources=resourcePhase(repository,taskId,'revalidate',options);
      const beforeResource=recoveryJson(path.join(path.dirname(first.original),'receipt.json'));
      if(!resources?.ok || resources.taskId!==taskId || resources.candidateCommit!==receipt.integrationCommit || resources.previousReceiptSha256!==beforeResource.sha256 || !resources.cache?.ok)fail('RESOURCE_CLOSEOUT_BLOCKED');
      fsck(repository,options);
      const final=recoveryPlan(repository,taskId,backupDirectory,receipt,options);
      if(final.previewSha256!==previewSha256)fail('CLOSEOUT_RECOVERY_STALE');
      const directory=path.dirname(first.original), id=crypto.randomUUID();
      const epochs=path.join(directory,'recovery-epochs');privateDirectory(epochs);
      const epochDirectory=path.join(epochs,id);fs.mkdirSync(epochDirectory,{mode:0o700});
      fs.writeFileSync(path.join(epochDirectory,'original-proof.json'),first.saved.bytes,{flag:'wx',mode:0o600});
      fs.writeFileSync(path.join(epochDirectory,'original-resource-receipt.json'),beforeResource.bytes,{flag:'wx',mode:0o600});
      if(Object.keys(final.retirementRecords).length) {
        const directory=path.join(epochDirectory,'retired-deliveries');fs.mkdirSync(directory,{mode:0o700});
        for(const [owner,records] of Object.entries(final.retirementRecords)) {
          const saved=path.join(directory,owner);fs.mkdirSync(saved,{mode:0o700});
          for(const [kind,record] of Object.entries(records))fs.writeFileSync(path.join(saved,kind+'.json'),record.bytes,{flag:'wx',mode:0o600});
        }
      }
      const epoch={...final.plan,status:'complete',restoreVerified:true,resourceRevalidation:resources,verifiedAt:new Date().toISOString()};
      const payload=JSON.stringify(epoch,null,2)+'\n';
      fs.writeFileSync(path.join(epochDirectory,'epoch.json'),payload,{flag:'wx',mode:0o600});
      // The certificate is committed only after resource completion and another
      // full audit. A crash leaves an uncommitted epoch and the old pending gate.
      fsck(repository,options);
      if(recoveryPlan(repository,taskId,backupDirectory,receipt,options).previewSha256!==previewSha256)fail('CLOSEOUT_RECOVERY_STALE');
      finishResourceReceipt(repository,taskId,first.proof.resourceContractRequired,resources);
      if(fs.existsSync(certificate))fail('CLOSEOUT_RECOVERY_STALE');
      writePrivateJson(certificate,{schemaVersion:1,taskId,candidateCommit:receipt.integrationCommit,originalProofSha256:first.saved.sha256,epoch:`recovery-epochs/${id}/epoch.json`,epochSha256:sha256(payload)});
      validateRecoveryCompletion(repository,taskId,receipt);
      log(repository,'closeout-recover','PASS',undefined,{backup:first.plan.backupDirectory},options);
      return {taskId,status:'cleaned',restoreVerified:true,retiredSnapshots:first.plan.retiredSnapshots,retiredDeliveries:first.plan.retiredDeliveries,retiredWorktrees:first.plan.retiredWorktrees,epoch:certificate};
    });
  };
  if(!apply)return perform(discover(projectRoot,options));
  return withRepositoryLock({projectRoot},async repository=>{
    const directory=installShim(repository,options), previousPath=process.env.PATH;
    process.env.PATH=directory+path.delimiter+(previousPath??'');
    try{return await perform(repository);}catch(error){log(repository,'closeout-recover','FAIL',error.code??'CLOSEOUT_RECOVERY_FAILED',{},options);throw error;}
    finally {if(previousPath===undefined)delete process.env.PATH;else process.env.PATH=previousPath;}
  },options);
}
function assertNoIgnoredData(directory, options) {
  if (paths(directory, ['ls-files', '--others', '--ignored', '--exclude-standard', '--directory', '-z'], options).length) fail('WORKTREE_IGNORED_DATA');
}
export function validateCleanup({projectRoot, receipt}, options = {}) {
  return cleanupPreflight({projectRoot, receipt}, options, false);
}
export function validateResourceCleanup({projectRoot, receipt}, options = {}) {
  return cleanupPreflight({projectRoot, receipt}, options, true);
}
function cleanupPreflight({projectRoot, receipt}, options, beforeResources) {
  const repository = discover(projectRoot, options);
  if (receipt.repositoryRoot !== repository.repositoryRoot || !ID.test(receipt.taskId ?? '') || receipt.defaultBranch !== 'master' || receipt.remote !== 'origin') fail('TASK_OWNERSHIP_MISMATCH');
  if (receipt.status !== 'ci_passed' || receipt.ci?.status !== 'passed') fail('CI_NOT_PASSED');
  const registered = worktrees(repository, options);
  for (const item of managed(receipt)) {
    const integrationPattern = new RegExp(`^codex/integrate-${receipt.taskId}(?:-r[0-9]+)?$`);
    if (typeof item.branch !== 'string' || !(item.branch.startsWith(`codex/${receipt.taskId}-`) || integrationPattern.test(item.branch)) || typeof item.worktree !== 'string') fail('TASK_OWNERSHIP_MISMATCH');
    const branch = `refs/heads/${item.branch}`;
    const existing = git(projectRoot, ['show-ref', '--verify', '--quiet', branch], options, {allowFailure: true}).status === 0;
    if (!existing || !/^[a-f0-9]{40,64}$/.test(item.commit ?? '') || output(git(projectRoot, ['rev-parse', branch], options)) !== item.commit) fail('TASK_COMMIT_MISMATCH');
    if (existing && git(projectRoot, ['merge-base', '--is-ancestor', branch, 'refs/remotes/origin/master'], options, {allowFailure: true}).status !== 0) fail('BRANCH_UNMERGED');
    if (!fs.existsSync(item.worktree)) { if (!item.worktreeRemoved || registered.some(entry => entry.worktree === item.worktree)) fail('WORKTREE_UNAVAILABLE'); continue; }
    if (fs.realpathSync(item.worktree) === repository.repositoryRoot) fail('TASK_OWNERSHIP_MISMATCH');
    const entry = registered.find(entry => entry.worktree === fs.realpathSync(item.worktree));
    if (!entry || entry.branch !== branch || discover(item.worktree, options).commonDirectory !== repository.commonDirectory) fail('TASK_OWNERSHIP_MISMATCH');
    if (output(git(item.worktree, ['status', '--porcelain', '--untracked-files=all'], options))) fail('WORKTREE_DIRTY');
    if (!beforeResources) assertNoIgnoredData(item.worktree, options);
    if ((options.processProbe ?? occupied)(item.worktree)) fail('WORKTREE_OCCUPIED');
  }
  if (git(projectRoot, ['merge-base', '--is-ancestor', receipt.integrationCommit, 'refs/remotes/origin/master'], options, {allowFailure: true}).status !== 0) fail('BRANCH_UNMERGED');
  return {valid: true, managed: managed(receipt)};
}

/** Private process PATH shim. execFile-style argv forwarding; no user args become shell source. */
function immutableShimFile(destination, expected) {
  assertNoSymlinkAncestors(path.dirname(destination));
  const before = fs.lstatSync(destination, {throwIfNoEntry: false});
  if (!before) { privateWrite(destination, expected); return; }
  if (!before.isFile() || before.isSymbolicLink() || before.nlink !== 1 || (typeof process.getuid === 'function' && before.uid !== process.getuid())) fail('SHIM_INVALID');
  let fd;
  try {
    try { fd = fs.openSync(destination, fs.constants.O_RDONLY | fs.constants.O_NOFOLLOW); } catch { fail('SHIM_INVALID'); }
    const opened = fs.fstatSync(fd);
    if (!opened.isFile() || opened.nlink !== 1 || opened.ino !== before.ino || opened.dev !== before.dev || opened.uid !== before.uid) fail('SHIM_INVALID');
    if (fs.readFileSync(fd, 'utf8') !== expected) fail('SHIM_INVALID');
    const current = fs.lstatSync(destination, {throwIfNoEntry: false});
    if (!current || current.isSymbolicLink() || current.nlink !== 1 || current.ino !== opened.ino || current.dev !== opened.dev || current.uid !== opened.uid) fail('SHIM_INVALID');
    assertNoSymlinkAncestors(path.dirname(destination));
  } finally { if (fd !== undefined) fs.closeSync(fd); }
}
function installShim(repository, options) {
  const directory = path.join(state(repository), 'bin');
  privateDirectory(directory);
  const destination = path.join(directory, 'git');
  const source = `#!${process.execPath}\nimport {spawnSync} from 'node:child_process';\nconst a=process.argv.slice(2);\nlet i=0;while(i<a.length){if(['-C','-c','--git-dir','--work-tree'].includes(a[i])){i+=2;continue;}if(a[i].startsWith('--git-dir=')||a[i].startsWith('--work-tree=')||a[i]==='--no-optional-locks'){i++;continue;}break;}\nconst cmd=a[i];if(${JSON.stringify([...FORBIDDEN])}.includes(cmd))process.exit(73);\nconst forwarded=cmd==='fetch'?a.filter((x,n)=>n<=i||x!=='--prune'):a;\nconst r=spawnSync(${JSON.stringify(selectGitPath(options))},['--no-optional-locks','-c','gc.auto=0','-c','maintenance.auto=false',...forwarded],{stdio:'inherit'});process.exit(r.status??74);\n`;
  // Node treats an extensionless entry as CommonJS; dynamic import is unnecessary with require.
  const executableSource = source.replace("import {spawnSync} from 'node:child_process';", "const {spawnSync}=require('node:child_process');");
  assertNoSymlinkAncestors(directory);
  immutableShimFile(destination, executableSource);
  // The repository's type:module scope also reaches .git. Pin this owned bin to CJS.
  immutableShimFile(path.join(directory, 'package.json'), JSON.stringify({type: 'commonjs'}) + '\n');
  fs.chmodSync(destination, 0o700);
  return directory;
}
function githubRepo(receipt) {
  const match = receipt.remoteUrl?.match(/github\.com[/:]([\w.-]+\/[\w.-]+?)(?:\.git)?$/);
  if (!match) fail('GITHUB_REMOTE_REQUIRED');
  return match[1];
}
function gh(args, cwd, options) { return (options.githubRunner ?? ((commandName, argv, extra) => command(commandName, argv, extra)))('gh', args, {cwd}); }
function githubJson(args, repository, options) { return JSON.parse(output(gh(args, repository.repositoryRoot, options))); }
function quota(repository, options) {
  if (options.quotaProbe) { if (!options.quotaProbe(repository).allowed) fail('ACTIONS_BUDGET_BLOCKED'); return; }
  // Read the repository-owned gate on every remote mutation. No cached visibility inference.
  fs.readFileSync(path.join(repository.repositoryRoot, 'docs/actions-budget.md'), 'utf8');
  const result = githubJson(['repo', 'view', '--json', 'visibility,nameWithOwner'], repository, options);
  if (result.visibility !== 'PUBLIC') fail('ACTIONS_BUDGET_UNPROVEN');
  const workflows = path.join(repository.repositoryRoot, '.github/workflows');
  for (const name of fs.readdirSync(workflows).filter(name => /\.ya?ml$/.test(name))) {
    const source = fs.readFileSync(path.join(workflows, name), 'utf8');
    const labels = [...source.matchAll(/runs-on:\s*([^\n]+)/g)].map(item => item[1].trim());
    const standard = label => /^(?:ubuntu-(?:latest|(?:20|22|24|26)\.04)|macos-(?:latest|13|14|15|26)(?:-intel)?|windows-(?:latest|2019|2022|2025))\s*(?:#.*)?$/.test(label);
    const matrix = source.match(/\bos:\s*\[([^\]]+)\]/)?.[1]?.split(',').map(item => item.trim().replace(/^["']|["']$/g, '')) ?? [...source.matchAll(/^\s+os:\s*([^\n]+)$/gm)].map(item => item[1].trim());
    if (!labels.length || labels.some(label => !(standard(label) || label === '${{ matrix.os }}' && matrix?.length && matrix.every(standard)))) fail('STANDARD_RUNNER_UNPROVEN');
  }
  const runs = githubJson(['run', 'list', '--repo', result.nameWithOwner, '--limit', '20', '--json', 'status,conclusion'], repository, options);
  if (!runs.some(item => item.status === 'in_progress' || item.status === 'completed' && item.conclusion === 'success')) fail('ACTIONS_RUN_UNPROVEN');
}
function publicationRunner(repository, receipt, options, verification) {
  const repo = githubRepo(receipt);
  const controllerResult = result => ({...result, stdout: result.stdout?.toString() ?? '', stderr: result.stderr?.toString() ?? ''});
  return (_executable, args, extra) => {
    if (args[0] === 'pr' && args[1] === 'merge' && args.includes('--auto')) return {status: 0, stdout: '', stderr: ''};
    if (args[0] !== 'pr' || args[1] !== 'create') return controllerResult(gh(args, extra.cwd, options));
    const existing = githubJson(['pr', 'list', '--repo', repo, '--head', receipt.integrationBranch, '--base', 'master', '--state', 'open', '--json', 'url,headRefOid'], repository, options);
    if (existing.length > 1) fail('PR_IDENTITY_AMBIGUOUS');
    if (existing.length) {
      if (existing[0].headRefOid !== receipt.integrationCommit) fail('PR_HEAD_MISMATCH');
      return {status: 0, stdout: existing[0].url + '\n', stderr: ''};
    }
    const bodyOffset = args.indexOf('--body');
    if (bodyOffset < 0) fail('PR_BODY_REQUIRED');
    const bodyPath = path.join(state(repository), `pr-body-${crypto.randomUUID()}.md`);
    const duration = verification?.durationSeconds;
    const body = `Managed ResearchWorkbench delivery ${receipt.taskId}.\n\nCandidate: ${receipt.integrationCommit}\nVerification: ${verification?.status === 'passed' ? 'passed' : 'not certified'}${Number.isInteger(duration) && duration >= 0 ? ` (${duration} seconds)` : ''}.\nTask-local command declarations and evidence remain in the local delivery receipt.\n`;
    privateWrite(bodyPath, body);
    try { return controllerResult(gh([...args.slice(0, bodyOffset), '--body-file', bodyPath, ...args.slice(bodyOffset + 2)], extra.cwd, options)); }
    finally { fs.unlinkSync(bodyPath); }
  };
}
function reviewFile(repository, taskId) { return path.join(state(repository), 'reviews', `${taskId}.json`); }
function readReview(repository, taskId) {
  const filename = reviewFile(repository, taskId);
  assertNoSymlinkAncestors(path.dirname(filename));
  const stat = fs.lstatSync(filename, {throwIfNoEntry: false});
  if (!stat) return null;
  if (!stat.isFile() || stat.isSymbolicLink() || stat.nlink !== 1) fail('REVIEW_STATE_INVALID');
  let record;
  try { record = JSON.parse(fs.readFileSync(filename, 'utf8')); } catch { fail('REVIEW_STATE_INVALID'); }
  if (record.status !== 'PASS' || !/^[a-f0-9]{40,64}$/.test(record.candidateCommit ?? '') || record.reviewedCommit !== record.candidateCommit || !Number.isFinite(Date.parse(record.attestedAt))) fail('REVIEW_STATE_INVALID');
  return record;
}
function assertReviewed(repository, receipt) {
  const review = readReview(repository, receipt.taskId);
  if (!review || review.candidateCommit !== receipt.integrationCommit || review.reviewedCommit !== receipt.integrationCommit) fail('REVIEW_NOT_ATTESTED');
  return review;
}
function attestReview(repository, receipt, reviewedCommit) {
  if (reviewedCommit !== receipt.integrationCommit) fail('REVIEWED_COMMIT_MISMATCH');
  readReview(repository, receipt.taskId); // Refuse corrupt or foreign existing state.
  const target = reviewFile(repository, receipt.taskId);
  const temporary = `${target}.${crypto.randomUUID()}.tmp`;
  privateWrite(temporary, JSON.stringify({candidateCommit: receipt.integrationCommit, reviewedCommit, status: 'PASS', attestedAt: new Date().toISOString()}) + '\n');
  try { fs.renameSync(temporary, target); } finally { if (fs.existsSync(temporary)) fs.unlinkSync(temporary); }
}
function reviewedStatus(repository, receipt, reviewedCommit, options) {
  const repo = githubRepo(receipt);
  const pr = githubJson(['pr', 'view', receipt.pullRequest.url, '--repo', repo, '--json', 'state,headRefOid,baseRefName,mergeStateStatus,reviewDecision,statusCheckRollup,mergeCommit'], repository, options);
  if (pr.headRefOid !== receipt.integrationCommit || pr.baseRefName !== 'master') fail('PR_HEAD_MISMATCH');
  if (reviewedCommit) attestReview(repository, receipt, reviewedCommit);
  const review = readReview(repository, receipt.taskId);
  if (!review || review.candidateCommit !== receipt.integrationCommit || review.reviewedCommit !== receipt.integrationCommit) return {status: 'pending', runs: pr.statusCheckRollup ?? []};
  const runs = pr.statusCheckRollup ?? [];
  const bad = runs.some(item => item.status !== 'COMPLETED' && item.state !== 'SUCCESS' || item.conclusion && !['SUCCESS', 'NEUTRAL', 'SKIPPED'].includes(item.conclusion));
  const protection = githubJson(['api', `repos/${repo}/branches/master/protection`], repository, options);
  const required = protection.required_status_checks?.checks ?? protection.required_status_checks?.contexts?.map(context => ({context}));
  const approvalCount = protection.required_pull_request_reviews?.required_approving_review_count;
  if (!Array.isArray(required) || !required.length || typeof approvalCount !== 'number' || !protection.required_status_checks?.strict || !protection.enforce_admins?.enabled || !protection.required_conversation_resolution?.enabled || protection.allow_force_pushes?.enabled || protection.allow_deletions?.enabled) fail('BRANCH_PROTECTION_UNPROVEN');
  if (pr.reviewDecision !== 'APPROVED' && !(approvalCount === 0 && !pr.reviewDecision)) fail('REVIEW_NOT_APPROVED');
  const checkRuns = githubJson(['api', `repos/${repo}/commits/${receipt.integrationCommit}/check-runs`, '--paginate', '--slurp'], repository, options).flatMap(page => page.check_runs ?? []);
  const commitStatuses = githubJson(['api', `repos/${repo}/commits/${receipt.integrationCommit}/status`], repository, options);
  if (commitStatuses.sha !== receipt.integrationCommit) fail('CHECK_COMMIT_MISMATCH');
  const requiredPassed = required.every(check => checkRuns.some(run => run.name === check.context && run.head_sha === receipt.integrationCommit && run.status === 'completed' && run.conclusion === 'success' && (!(check.app_id > 0) || run.app?.id === check.app_id)) || (!(check.app_id > 0) && (commitStatuses.statuses ?? []).some(run => run.context === check.context && run.state === 'success')));
  if (!requiredPassed || bad) fail('MERGE_GATES_NOT_PASSED');
  if (pr.state === 'MERGED') {
    const merge = pr.mergeCommit?.oid;
    if (!/^[a-f0-9]{40,64}$/.test(merge ?? '')) fail('MERGE_IDENTITY_UNPROVEN');
    const commit = githubJson(['api', `repos/${repo}/commits/${merge}`], repository, options);
    if (commit.sha !== merge || !(commit.parents ?? []).some(parent => parent.sha === receipt.integrationCommit)) fail('MERGE_IDENTITY_UNPROVEN');
    return {status: 'passed', runs, mergeCommit: merge};
  }
  if (pr.state !== 'OPEN' || pr.mergeStateStatus !== 'CLEAN') fail('MERGE_GATES_NOT_PASSED');
  quota(repository, options);
  gh(['pr', 'merge', receipt.pullRequest.url, '--repo', repo, '--merge', '--match-head-commit', review.reviewedCommit], repository.repositoryRoot, options);
  return {status: 'pending', runs}; // Refresh must observe the merge and CI before cleanup.
}
function preservationAudit(repository, beforeRefs, beforeWorktrees, targets, options, verifiedPreservationRefs) {
  const afterRefs = refs(repository, options);
  const managedRefs = new Set(targets.flatMap(item => [`refs/heads/${item.branch}`, `refs/remotes/origin/${item.branch}`]));
  const advances = [];
  const ancestor = (oldCommit, newCommit) => git(repository.repositoryRoot, ['merge-base', '--is-ancestor', oldCommit, newCommit], options, {allowFailure: true}).status === 0;
  for (const [ref, oid] of Object.entries(beforeRefs)) {
    if (managedRefs.has(ref) || afterRefs[ref] === oid) continue;
    if (!afterRefs[ref]) fail('UNRELATED_REF_CHANGED');
    if (ref.startsWith('refs/codex/turn-diffs/') && verifiedPreservationRefs?.[ref] === oid && output(git(repository.repositoryRoot, ['cat-file', '-t', oid], options)) === 'tree' && output(git(repository.repositoryRoot, ['cat-file', '-t', afterRefs[ref]], options)) === 'tree') {
      if (git(repository.repositoryRoot, ['fsck', '--connectivity-only', '--no-reflogs', afterRefs[ref]], options, {allowFailure: true}).status !== 0) fail('OBJECT_INTEGRITY_FAILED');
      advances.push({event: 'concurrent_snapshot_update', oldCommit: oid, newCommit: afterRefs[ref]});
    } else {
      if (!ancestor(oid, afterRefs[ref])) fail('UNRELATED_REF_CHANGED');
      advances.push({event: 'concurrent_ref_advance', oldCommit: oid, newCommit: afterRefs[ref]});
    }
  }
  const afterWorktrees = worktrees(repository, options);
  for (const item of beforeWorktrees) {
    if (targets.some(target => target.worktree === item.worktree)) continue;
    const current = afterWorktrees.find(other => other.worktree === item.worktree);
    if (!current || current.branch !== item.branch || current.bare !== item.bare) fail('UNRELATED_WORKTREE_CHANGED');
    if (current.HEAD !== item.HEAD && (!current.HEAD || !item.HEAD || !ancestor(item.HEAD, current.HEAD))) fail('UNRELATED_WORKTREE_CHANGED');
    if (fs.existsSync(item.worktree) && !item.bare && discover(item.worktree, options).commonDirectory !== repository.commonDirectory) fail('UNRELATED_WORKTREE_CHANGED');
  }
  return advances;
}
export async function runDelivery({projectRoot, taskId, action, reviewedCommit, ...params}, options = {}) {
  if (Object.hasOwn(params, 'deferCleanup') && (params.deferCleanup !== true || action !== 'status')) fail('DELIVERY_ARGUMENT_INVALID');
  options = {...options, startedAt: Date.now()};
  selectGitPath({...options, mutate: true});
  if (!ID.test(taskId ?? '') || !['start', 'prepare', 'publish', 'status', 'cleanup'].includes(action)) fail('DELIVERY_ARGUMENT_INVALID');
  let safetyCleanupDeferred = false;
  const result = await withRepositoryLock({projectRoot}, async repository => {
    fsck(repository, options);
    const directory = installShim(repository, options);
    const previousPath = process.env.PATH;
    process.env.PATH = directory + path.delimiter + (previousPath ?? '');
    const toolchainScope = {repositoryRoot: repository.repositoryRoot, commonDirectory: repository.commonDirectory, taskId, operationToken: Symbol('delivery-operation'), active: true, record: undefined};
    deliveryToolchains.set(repository, toolchainScope);
    try {
      const controller = options.controller ?? await import(pathToFileURL(CONTROLLER).href);
      const common = {projectRoot: repository.repositoryRoot, taskId};
      if (action !== 'start') {
        const receipt = controller.readDeliveryReceipt(common);
        const currentRemote = output(git(projectRoot, ['remote', 'get-url', 'origin'], options));
        if (typeof receipt.remoteUrl !== 'string' || currentRemote !== receipt.remoteUrl) fail('REMOTE_IDENTITY_CHANGED');
      }
      let result;
      if (action === 'start') {
        const remoteHead = output(git(projectRoot, ['ls-remote', '--symref', 'origin', 'HEAD'], options));
        if (!/^ref:\s+refs\/heads\/master\s+HEAD$/m.test(remoteHead)) fail('DELIVERY_BRANCH_INVALID');
        result = controller.startDelivery({...common, slug: params.slug ?? taskId, remote: 'origin', worktreeRoot: params.worktreeRoot});
        resourcePhase(repository, taskId, 'record', options);
      }
      if (action === 'prepare') {
        if (params.replacePrepared) fail('PREPARE_REMOVAL_BLOCKED');
        const receipt = controller.readDeliveryReceipt(common);
        if (receipt.status === 'ci_passed') fail('PREPARE_REMOVAL_BLOCKED');
        const refreshBase = receipt.status === 'remote_moved' || receipt.mode === null && receipt.status === 'prepared' || receipt.mode === 'pr' && (['awaiting_ci', 'ci_failed'].includes(receipt.status) || receipt.status === 'prepared' && receipt.baseRefreshPublishedHead != null);
        result = params.amendPrepared ? amendPrepared(repository, receipt, taskId, options) : refreshBase
          ? refreshPublishedBase(repository, receipt, taskId, options)
          : controller.prepareDelivery({...common, integrationWorktreeRoot: params.worktreeRoot, replacePrepared: false});
        resourcePhase(repository, taskId, 'record', options);
      }
      if (action === 'publish') {
        quota(repository, options);
        let receipt = controller.readDeliveryReceipt(common);
        if (receipt.defaultBranch !== 'master' || receipt.remote !== 'origin') fail('DELIVERY_BRANCH_INVALID');
        const repo = githubRepo(receipt);
        const settings = githubJson(['api', `repos/${repo}`], repository, options);
        if (settings.allow_auto_merge !== false) fail('REPO_AUTO_MERGE_ENABLED');
        if (closeoutEnabled(repository)) refreshFeatureRecord(repository, receipt, options);
        resourcePhase(repository, taskId, 'record', options);
        receipt = advancePublishedHead(repository, controller.readDeliveryReceipt(common), options);
        result = advancePublishedHead(repository, controller.publishDelivery({...common, verification: params.verification, repair: params.repair ?? false, pushDefault: () => ({status: 'protected'}), githubRunner: publicationRunner(repository, receipt, options, params.verification)}), options);
        result = {...result, safetyAutoMergeDeferred: true};
      }
      if (action === 'status') {
        const receipt = controller.readDeliveryReceipt(common);
        if (receipt.mode !== 'pr' || !receipt.pullRequest?.url) fail('PR_DELIVERY_REQUIRED');
        if (receipt.status === 'cleaned') {
          assertReviewed(repository, receipt); result=controller.validateCleanedDelivery(common);
          validateCompletedCloseout(repository,taskId,receipt,options);
        }
        else result = controller.refreshDeliveryStatus({...common, resolveCiStatus: (_repository, record) => reviewedStatus(repository, record, reviewedCommit, options)});
      }
      if (action === 'cleanup') {
        const resourceContractRequired=closeoutEnabled(repository);
        quota(repository, options);
        const receipt = controller.readDeliveryReceipt(common);
        assertReviewed(repository, receipt);
        if(receipt.status==='cleaned') {
          result=controller.validateCleanedDelivery(common);
          validateCompletedCloseout(repository,taskId,receipt,options);
          log(repository,'delivery-cleanup','PASS',undefined,{},options);
          return result;
        }
        git(projectRoot, ['fetch', 'origin', 'refs/heads/master:refs/remotes/origin/master'], options);
        validateResourceCleanup({projectRoot, receipt}, options);
        // Record late test outputs before preserving them, then retain every Git
        // cleanup guard (merged tip, restore-verified backup, ignored data, occupancy).
        resourcePhase(repository, taskId, 'record', options);
        resourcePhase(repository, taskId, 'cleanup', options);
        const validated = validateCleanup({projectRoot, receipt}, options);
        for (const item of validated.managed) {
          const advertised = output(git(projectRoot, ['ls-remote', 'origin', `refs/heads/${item.branch}`], options));
          if (!advertised) continue;
          const oid = advertised.split(/\s+/)[0];
          if (oid !== item.commit) fail('REMOTE_TASK_COMMIT_MISMATCH');
          if (git(projectRoot, ['merge-base', '--is-ancestor', oid, 'refs/remotes/origin/master'], options, {allowFailure: true}).status !== 0) fail('BRANCH_UNMERGED');
        }
        const beforeRefs = refs(repository, options);
        const beforeWorktrees = worktrees(repository, options);
        const backup = backupUnlocked(repository, {...options, preservationRefs: beforeRefs, worktreePaths: [...new Set([repository.repositoryRoot, ...validated.managed.map(item => item.worktree).filter(item => fs.existsSync(item))])]});
        if (!backup.restoreVerified) fail('BACKUP_NOT_VERIFIED');
        validateCleanup({projectRoot, receipt}, options);
        preservationAudit(repository, beforeRefs, beforeWorktrees, validated.managed, options, backup.verifiedPreservationRefs);
        for (const item of validated.managed) if (fs.existsSync(item.worktree)) assertNoIgnoredData(item.worktree, options);
        // The controller omits superseded worktree removal. Remove only the validated task history.
        for (const item of validated.managed.filter(item => item.worktree !== receipt.featureWorktree && item.worktree !== receipt.integrationWorktree)) {
          if (fs.existsSync(item.worktree)) { assertNoIgnoredData(item.worktree, options); git(projectRoot, ['worktree', 'remove', item.worktree], options); }
        }
        for (const item of validated.managed) if (fs.existsSync(item.worktree)) assertNoIgnoredData(item.worktree, options);
        if (resourceContractRequired) writePrivateJson(closeoutFinalization(repository,taskId),{taskId,candidateCommit:receipt.integrationCommit,status:'pending',resourceContractRequired,restoreVerified:backup.restoreVerified,beforeRefs,beforeWorktrees,managed:validated.managed,verifiedPreservationRefs:backup.verifiedPreservationRefs});
        result = controller.cleanupDelivery({...common,deferResourceCleanup:true});
        if(result.status!=='cleaned') {
          log(repository,'delivery-cleanup','FAIL','RESOURCE_CLEANUP_PENDING',{},options);
          return {...result,safetyBackup:backup.directory};
        }
        fsck(repository, options);
        const concurrentRefAdvances = preservationAudit(repository, beforeRefs, beforeWorktrees, validated.managed, options, backup.verifiedPreservationRefs);
        result = {...result, safetyBackup: backup.directory, safetyFsck: 'PASS', concurrentRefAdvances};
        if(fs.existsSync(path.join(repository.repositoryRoot,'.agents/resource-lifecycle.json'))) {
          writePrivateJson(path.join(repository.commonDirectory,'leon-engineering/resource-closeout',taskId,'lifecycle-backup.json'),
            {taskId,id:path.basename(backup.directory),manifestHash:readManifest(backup.directory).hash});
        }
        finishResourceReceipt(repository,taskId,resourceContractRequired);
        const finalization=closeoutFinalization(repository,taskId);
        if (fs.existsSync(finalization)) writePrivateJson(finalization,{...JSON.parse(fs.readFileSync(finalization,'utf8')),status:'complete'});
      }
      if (action === 'status' && result.status === 'ci_passed' && params.deferCleanup === true && closeoutEnabled(repository)) {
        log(repository, 'delivery-cleanup-deferred', 'DEFERRED', undefined, {safetyCleanupDeferred: true, readOnly: false}, options);
        safetyCleanupDeferred = true;
        result = {...result, safetyCleanupDeferred: true};
      }
      log(repository, 'delivery-' + action, 'PASS', undefined, result?.safetyBackup ? {backup: result.safetyBackup, concurrentRefAdvances: result.concurrentRefAdvances} : {}, options);
      return result;
    } catch (error) {
      const code = error.code ?? (/delivery task is locked:/.test(error.message ?? '') ? 'TASK_LOCKED' : 'DELIVERY_FAILED');
      if (action==='cleanup' || action==='status') {
        const directory=path.join(repository.commonDirectory,'leon-engineering/resource-closeout',taskId);
        if (fs.existsSync(directory)) {
          const filename=path.join(directory,'receipt.json');
          if (fs.existsSync(filename) && fs.lstatSync(filename).isSymbolicLink()) fail('CLOSEOUT_RECEIPT_INVALID');
          const record=fs.existsSync(filename)?JSON.parse(fs.readFileSync(filename,'utf8')):{taskId,ok:false};
          if(record.taskId!==taskId) fail('CLOSEOUT_RECEIPT_INVALID');
          if (record.status!=='complete') writePrivateJson(filename,{...record,status:'blocked',blocked:[...(record.blocked??[]),{phase:'git',code}]});
        }
      }
      log(repository, 'delivery-' + action, 'FAIL', code, {}, options);
      if (!error.code) fail(code);
      throw error;
    }
    finally {
      toolchainScope.active = false;
      toolchainScope.record = undefined;
      deliveryToolchains.delete(repository);
      if (previousPath === undefined) delete process.env.PATH; else process.env.PATH = previousPath;
    }
  }, options);
  // Finish resource/Git cleanup only after releasing the repository lock; recursive
  // cleanup must not deadlock or run while CI/merge is still pending.
  if (safetyCleanupDeferred) return result;
  if (action === 'status' && result.status === 'ci_passed' && closeoutEnabled(discover(projectRoot, options))) {
    return runDelivery({projectRoot, taskId, action:'cleanup'}, options);
  }
  if (['status','cleanup'].includes(action) && result.status==='cleaned') {
    const repository=discover(projectRoot,options),policy=path.join(repository.repositoryRoot,'.agents/resource-lifecycle.json');
    if(fs.existsSync(policy)) {
      let lifecycle;
      try {
        if(fs.lstatSync(policy).isSymbolicLink())fail('LIFECYCLE_POLICY_INVALID');
        const value=JSON.parse(fs.readFileSync(policy,'utf8'));
        if(value.schemaVersion!==1 || value.enabled!==true)fail('LIFECYCLE_POLICY_INVALID');
        lifecycle=await finalizeLifecycle({projectRoot:repository.repositoryRoot,commonDirectory:repository.commonDirectory,taskId,receipt:result});
        const retirementIds=registeredLifecycleBackups(repository,options.backupRoot??path.join(os.homedir(),'.codex/backups/rwb-git-safety'));
        const preview=maintainBackups({projectRoot:repository.repositoryRoot,action:'backup-prune'}, {...options,retirementIds});
        lifecycle.backups=preview.items.some(item=>item.status==='would_expire')
          ?maintainBackups({projectRoot:repository.repositoryRoot,action:'backup-prune',apply:true},{...options,retirementIds}):preview;
        if(lifecycle.backups.status==='blocked')lifecycle.status='blocked';
      } catch(error) {lifecycle={status:'blocked',code:error.code??'LIFECYCLE_CLOSEOUT_FAILED'};}
      writePrivateJson(path.join(repository.commonDirectory,'leon-engineering/resource-closeout',taskId,'lifecycle.json'),lifecycle);
      log(repository,'resource-lifecycle',lifecycle.status==='cleaned'?'PASS':'FAIL',lifecycle.code,{},options);
      return {...result,gitStatus:result.status,status:lifecycle.status==='cleaned'?'cleaned':'cleanup_pending',
        lifecycleCloseout:{status:lifecycle.status,code:lifecycle.code,notify:lifecycle.notify,
          reclaimed:lifecycle.reclaimed?.length??0,retained:lifecycle.items?.filter(i=>i.action==='retain').length??0,
          backups:lifecycle.backups?.items?.length??0,detail:path.join(repository.commonDirectory,'leon-engineering/resource-closeout',taskId,'lifecycle.json')}};
    }
  }
  return result;
}
export function parseCli(args) {
  const [subcommand, ...rest] = args;
  if (!['check', 'configure', 'backup', 'delivery', 'backup-audit', 'backup-migrate', 'backup-prune', 'closeout-recover'].includes(subcommand)) fail('CLI_SUBCOMMAND_INVALID');
  const options = {};
  const values = new Map([['--project', 'projectRoot'], ['--task-id', 'taskId'], ['--recovery-backup', 'backupDirectory'], ['--preview-sha256', 'previewSha256'], ['--slug', 'slug'], ['--worktree-root', 'worktreeRoot'], ['--reviewed-commit', 'reviewedCommit'], ['--verification-command', 'verificationCommand'], ['--verification-status', 'verificationStatus'], ['--verification-duration-seconds', 'verificationDuration']]);
  for (let index = 0; index < rest.length; index++) {
    const item = rest[index];
    if (['--start', '--prepare', '--publish', '--status', '--cleanup'].includes(item)) { if (options.action) fail('CLI_ACTION_INVALID'); options.action = item.slice(2); }
    else if (item === '--apply') options.apply = true;
    else if (item === '--repair') options.repair = true;
    else if (item === '--replace-prepared') options.replacePrepared = true;
    else if (item === '--amend-prepared') options.amendPrepared = true;
    else if (item === '--defer-cleanup') options.deferCleanup = true;
    else if (values.has(item) && rest[index + 1] && !rest[index + 1].startsWith('--')) options[values.get(item)] = rest[++index];
    else fail('CLI_OPTION_INVALID');
  }
  if (!options.projectRoot || (subcommand === 'delivery' && (!options.taskId || !options.action))) fail('CLI_ARGUMENT_REQUIRED');
  if (options.deferCleanup !== undefined && (subcommand !== 'delivery' || options.action !== 'status')) fail('CLI_OPTION_INVALID');
  if(subcommand==='closeout-recover') {
    if(!options.taskId || !options.backupDirectory || Object.keys(options).some(key=>!['projectRoot','taskId','backupDirectory','previewSha256','apply'].includes(key)) || options.apply && !/^[a-f0-9]{64}$/.test(options.previewSha256??'') || !options.apply && options.previewSha256)fail('CLI_ARGUMENT_REQUIRED');
    return {subcommand,options};
  }
  if(options.backupDirectory || options.previewSha256)fail('CLI_OPTION_INVALID');
  const maintenance=['backup-audit','backup-migrate','backup-prune'].includes(subcommand);
  if (subcommand !== 'delivery' && Object.keys(options).some(key => key !== 'projectRoot' && !(maintenance && key==='apply'))) fail('CLI_OPTION_INVALID');
  if(options.apply && !['backup-migrate','backup-prune'].includes(subcommand))fail('CLI_OPTION_INVALID');
  if(maintenance)options.action=subcommand;
  if (options.reviewedCommit && (options.action !== 'status' || !/^[a-f0-9]{40}$/.test(options.reviewedCommit))) fail('CLI_REVIEW_INVALID');
  if (options.replacePrepared && options.action !== 'prepare' || options.repair && options.action !== 'publish') fail('CLI_OPTION_INVALID');
  if (options.amendPrepared && (options.action !== 'prepare' || options.replacePrepared || options.worktreeRoot)) fail('CLI_OPTION_INVALID');
  if (options.action === 'publish') {
    const durationSeconds = Number(options.verificationDuration);
    if (!options.verificationCommand || options.verificationStatus !== 'passed' || !Number.isInteger(durationSeconds) || durationSeconds < 0) fail('VERIFICATION_REQUIRED');
    options.verification = {command: options.verificationCommand, status: 'passed', durationSeconds};
  }
  delete options.verificationCommand; delete options.verificationStatus; delete options.verificationDuration;
  return {subcommand, options};
}
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    const {subcommand, options} = parseCli(process.argv.slice(2));
    const result = subcommand === 'check' ? checkRepository(options) : subcommand === 'configure' ? configureRepository(options) : subcommand === 'backup' ? backupRepository(options) : subcommand.startsWith('backup-') ? maintainBackups(options) : subcommand==='closeout-recover' ? await recoverCloseoutFinalization(options) : await runDelivery(options);
    const rendered = subcommand === 'delivery' ? Object.fromEntries([
      'taskId', 'status', 'mode', 'defaultBranch', 'baseCommit', 'featureBranch', 'featureWorktree', 'featureCommit',
      'integrationBranch', 'integrationWorktree', 'integrationCommit', 'remoteCommit', 'pullRequest', 'cleanup',
      'safetyAutoMergeDeferred', 'safetyCleanupDeferred', 'safetyBackup', 'safetyFsck', 'concurrentRefAdvances', 'preparedAmendment', 'gitStatus', 'lifecycleCloseout'
    ].filter(key => result[key] !== undefined).map(key => [key, result[key]])) : result;
    if (subcommand === 'delivery' && result.ci) rendered.ci = {status: result.ci.status, runCount: result.ci.runs?.length ?? 0};
    process.stdout.write(JSON.stringify(rendered, null, 2) + '\n');
    if(result.status==='cleanup_pending')process.exitCode=2;
  } catch (error) { process.stderr.write(JSON.stringify({status: 'BLOCKED', code: error.code ?? 'GIT_SAFETY_FAILED',...(error.integrity?{integrity:error.integrity}:{})}) + '\n'); process.exitCode = 1; }
}
