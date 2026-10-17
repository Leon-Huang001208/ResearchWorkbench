#!/usr/bin/env node
/** RWB macOS Git safety boundary. No maintenance, arbitrary shell, or controller CLI forwarding. */
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import crypto from 'node:crypto';
import {spawnSync} from 'node:child_process';
import {fileURLToPath, pathToFileURL} from 'node:url';

const CONTROLLER = path.join(os.homedir(), '.agents/leon-engineering/runtime/iteration-delivery.mjs');
const FORBIDDEN = new Set(['gc', 'prune', 'repack', 'maintenance', 'prune-packed']);
const ID = /^[a-z0-9][a-z0-9-]{0,79}$/;
const sha256 = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
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
  return command(selectGitPath(options), ['--no-optional-locks', '-c', 'gc.auto=0', '-c', 'maintenance.auto=false', '-C', project, ...args], extra);
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
function log(repository, action, status, code, details = {}, options = {}) {
  if (options.logFailureCode) fail(options.logFailureCode);
  let descriptor;
  try {
  const dir = path.join(repository.repositoryRoot, 'logs');
  assertNoSymlinkAncestors(dir);
  if (fs.existsSync(dir) && (!fs.lstatSync(dir).isDirectory() || fs.lstatSync(dir).isSymbolicLink())) fail('LOG_DIRECTORY_INVALID');
  fs.mkdirSync(dir, {recursive: true});
  const parentBefore = fs.lstatSync(dir);
  const target = path.join(dir, 'git-safety.jsonl');
  const before = fs.lstatSync(target, {throwIfNoEntry: false});
  if (before && (!before.isFile() || before.isSymbolicLink() || before.nlink !== 1)) fail('LOG_FILE_INVALID');
  const version = output(command(selectGitPath(options), ['--version']));
  const head = output(git(repository.repositoryRoot, ['rev-parse', 'HEAD'], options, {allowFailure: true}));
  const flags = fs.constants.O_WRONLY | fs.constants.O_APPEND | fs.constants.O_NOFOLLOW | (before ? 0 : fs.constants.O_CREAT | fs.constants.O_EXCL);
  try { descriptor = fs.openSync(target, flags, 0o600); } catch { fail('LOG_FILE_INVALID'); }
  const opened = fs.fstatSync(descriptor);
  assertNoSymlinkAncestors(dir);
  const parentAfter = fs.lstatSync(dir);
  const current = fs.lstatSync(target, {throwIfNoEntry: false});
  if (!opened.isFile() || opened.nlink !== 1 || (typeof process.getuid === 'function' && (opened.uid !== process.getuid() || parentAfter.uid !== process.getuid())) || !current || current.isSymbolicLink() || current.nlink !== 1 || current.ino !== opened.ino || current.dev !== opened.dev || before && (opened.ino !== before.ino || opened.dev !== before.dev) || parentBefore.ino !== parentAfter.ino || parentBefore.dev !== parentAfter.dev || parentAfter.isSymbolicLink()) fail('LOG_FILE_INVALID');
  fs.writeSync(descriptor, JSON.stringify({time: new Date().toISOString(), action, status, gitPath: selectGitPath(options), gitVersion: /^git version [\w .()+-]+$/.test(version) ? version : 'UNKNOWN', head: /^[a-f0-9]{40,64}$/.test(head) ? head : null, durationMs: Math.max(0, Date.now() - (options.startedAt ?? Date.now())), ...details, ...(code ? {code} : {})}) + '\n');
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
  if (git(repository.repositoryRoot, ['fsck', '--full', '--no-reflogs'], options, {allowFailure: true}).status !== 0) fail('OBJECT_INTEGRITY_FAILED');
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
  const release = () => {
    fs.closeSync(fd);
    const current = fs.lstatSync(target, {throwIfNoEntry: false});
    if (!current || current.isSymbolicLink() || current.ino !== owned.ino || current.dev !== owned.dev) fail('LOCK_OWNERSHIP_CHANGED');
    let record;
    try { record = JSON.parse(fs.readFileSync(target, 'utf8')); } catch { fail('LOCK_OWNERSHIP_CHANGED'); }
    if (record.nonce !== nonce || record.pid !== process.pid) fail('LOCK_OWNERSHIP_CHANGED');
    fs.unlinkSync(target);
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
function copyDescriptors(sourceFd, targetFd) {
  const digest = crypto.createHash('sha256');
  const buffer = Buffer.allocUnsafe(1024 * 1024);
  let count;
  while ((count = fs.readSync(sourceFd, buffer, 0, buffer.length, null))) {
    digest.update(buffer.subarray(0, count));
    let written = 0;
    while (written < count) {
      const size = fs.writeSync(targetFd, buffer, written, count - written, null);
      if (size <= 0) fail('BACKUP_WRITE_FAILED');
      written += size;
    }
  }
  return digest.digest('hex');
}
function snapshotRegularFile(sourceRoot, item, directory, relative, manifest) {
  const source = path.resolve(sourceRoot, item.path);
  if (!source.startsWith(path.resolve(sourceRoot) + path.sep) || item.type !== 'file') fail('BACKUP_RACE');
  assertNoSymlinkAncestors(path.dirname(source));
  const before = fs.lstatSync(source, {throwIfNoEntry: false});
  if (!before?.isFile() || before.isSymbolicLink() || (before.mode & 0o777) !== item.mode) fail('BACKUP_RACE');
  let sourceFd, targetFd;
  try {
    try { sourceFd = fs.openSync(source, fs.constants.O_RDONLY | fs.constants.O_NOFOLLOW); } catch { fail('BACKUP_RACE'); }
    const opened = fs.fstatSync(sourceFd);
    if (!opened.isFile() || opened.ino !== before.ino || opened.dev !== before.dev || opened.uid !== before.uid) fail('BACKUP_RACE');
    const target = path.join(directory, relative);
    privateDirectory(path.dirname(target));
    assertNoSymlinkAncestors(path.dirname(target));
    targetFd = fs.openSync(target, fs.constants.O_WRONLY | fs.constants.O_CREAT | fs.constants.O_EXCL | fs.constants.O_NOFOLLOW, 0o600);
    const hash = copyDescriptors(sourceFd, targetFd);
    const after = fs.fstatSync(sourceFd);
    const current = fs.lstatSync(source, {throwIfNoEntry: false});
    assertNoSymlinkAncestors(path.dirname(source));
    if (hash !== item.sha256 || !current?.isFile() || current.isSymbolicLink() || current.ino !== opened.ino || current.dev !== opened.dev || current.uid !== opened.uid || after.size !== before.size || after.mtimeMs !== before.mtimeMs || after.ctimeMs !== before.ctimeMs || after.nlink !== before.nlink || (after.mode & 0o777) !== item.mode) fail('BACKUP_RACE');
    manifest.files.push({path: relative, sha256: hash});
  } finally { if (sourceFd !== undefined) fs.closeSync(sourceFd); if (targetFd !== undefined) fs.closeSync(targetFd); }
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
function restoreBackup(directory, manifest, options) {
  const scratch = fs.mkdtempSync(path.join(directory, '.restore-'));
  const bare = path.join(scratch, 'restored.git');
  try {
    command(selectGitPath(options), ['-c', 'gc.auto=0', '-c', 'maintenance.auto=false', 'init', '--bare', bare]);
    git(bare, ['bundle', 'verify', path.join(directory, 'commits.bundle')], options);
    git(bare, ['bundle', 'unbundle', path.join(directory, 'commits.bundle')], options);
    const packFd = fs.openSync(path.join(directory, 'objects.pack'), 'r');
    try { git(bare, ['index-pack', '--stdin'], options, {inputFd: packFd}); }
    finally { fs.closeSync(packFd); }
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
        fs.mkdirSync(path.dirname(target), {recursive: true, mode: 0o700});
        if (item.type === 'symlink') fs.symlinkSync(item.link, target);
        else { fs.copyFileSync(path.join(directory, `worktrees/${index}/untracked/${itemIndex}`), target); restoreFileMode(scratch, restored, item); }
      }
      saved.tracked.forEach((item, itemIndex) => { if (item.type === 'file') restoreFileMode(scratch, restored, item, path.join(directory, `worktrees/${index}/tracked/${itemIndex}`)); });
      const actualTracked = saved.tracked.map(item => fileRecord(restored, item.path));
      const actualUntracked = saved.untracked.map(item => fileRecord(restored, item.path));
      if (JSON.stringify(actualTracked) !== JSON.stringify(saved.tracked) || JSON.stringify(actualUntracked) !== JSON.stringify(saved.untracked)) fail('RESTORE_HASH_MISMATCH');
      if (sha256(git(restored, ['ls-files', '--stage', '-z'], options).stdout) !== saved.index) fail('RESTORE_INDEX_MISMATCH');
      if (sha256(git(restored, ['diff', '--cached', '--binary', '--full-index', 'HEAD', '--'], options).stdout) !== saved.staged || sha256(git(restored, ['diff', '--binary', '--full-index', '--'], options).stdout) !== saved.unstaged) fail('RESTORE_PATCH_MISMATCH');
    }
    if (git(bare, ['fsck', '--full', '--no-reflogs'], options, {allowFailure: true}).status !== 0) fail('RESTORE_FSCK_FAILED');
    for (const [ref, oid] of Object.entries(manifest.refs)) if (output(git(bare, ['rev-parse', ref], options)) !== oid) fail('RESTORE_REF_MISMATCH');
    const anchors = [...new Set(Object.values(manifest.preservationRefs))];
    for (const oid of anchors) if (git(bare, ['cat-file', '-e', oid], options, {allowFailure: true}).status !== 0) fail('RESTORE_REF_MISMATCH');
    if (anchors.length && git(bare, ['fsck', '--connectivity-only', '--no-reflogs', ...anchors], options, {allowFailure: true}).status !== 0) fail('RESTORE_FSCK_FAILED');
    for (const item of manifest.files) if (hashFile(path.join(directory, item.path)) !== item.sha256) fail('BACKUP_HASH_MISMATCH');
  } finally { fs.rmSync(scratch, {recursive: true, force: true}); }
}
function backupUnlocked(repository, options) {
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
  const preservationRefs = {...(options.preservationRefs ?? {})};
  if (Object.entries(preservationRefs).some(([ref, oid]) => !ref.startsWith('refs/') || !/^[a-f0-9]{40,64}$/.test(oid))) fail('PRESERVATION_REFS_INVALID');
  const manifest = {schemaVersion: 1, metadataSemantics: 'as-of-capture', restoreVerified: false, preservationRefs, refs: before.refs, registeredWorktrees: before.registeredWorktrees, worktrees: before.worktrees, files: []};
  try {
    git(repository.repositoryRoot, ['bundle', 'create', path.join(directory, 'commits.bundle'), '--all', ...before.worktrees.map(item => item.head)], options);
    fs.chmodSync(path.join(directory, 'commits.bundle'), 0o600);
    manifest.files.push({path: 'commits.bundle', sha256: hashFile(path.join(directory, 'commits.bundle'))});
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
      item.tracked.forEach((file, itemIndex) => { if (file.type === 'file') snapshotRegularFile(item.path, file, directory, `worktrees/${index}/tracked/${itemIndex}`, manifest); });
      item.untracked.forEach((file, itemIndex) => { if (file.type === 'file') snapshotRegularFile(item.path, file, directory, `worktrees/${index}/untracked/${itemIndex}`, manifest); });
    }
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

function resourcePhase(repository, taskId, phase, options) {
  if (!closeoutEnabled(repository)) return;
  const source = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
  const installedPython = path.join(repository.repositoryRoot, '.venv/bin/python');
  const python = fs.existsSync(installedPython) ? installedPython : 'python3.12';
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
function refreshPublishedBase(repository, receipt, taskId, options) {
  // The shared controller rebuilds worktrees for remote_moved. RWB instead admits
  // an already committed descendant, preserving every ref and any existing PR.
  // A never-published candidate must retain explicit null publication identities.
  const unpublished = receipt.mode === null && receipt.pullRequest === null && receipt.remoteCommit === null;
  if ((!unpublished && receipt.mode !== 'pr') || receipt.status !== 'remote_moved' || !receipt.integrationCommit) fail('PREPARE_REMOVAL_BLOCKED');
  if (unpublished && (receipt.baseRefreshPublishedHead != null || Object.keys(receipt).some(key => /publish|publication|push|pull.?request|remote.?commit/i.test(key) && !['pullRequest', 'remoteCommit', 'baseRefreshPublishedHead'].includes(key)) || receipt.cleanup?.remoteBranchDeleted === true || receipt.rollback && receipt.rollback.status !== 'not_run')) fail('UNPUBLISHED_STATE_INVALID');
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
      const allowed = [receipt.integrationCommit, receipt.baseRefreshPublishedHead].filter(Boolean);
      if (allowed.some(value => !/^[a-f0-9]{40}$/.test(value)) || pr.state !== 'OPEN' || !allowed.includes(pr.headRefOid) || pr.headRefName !== receipt.integrationBranch || pr.baseRefName !== 'master' || git(repository.repositoryRoot, ['merge-base', '--is-ancestor', pr.headRefOid, receipt.integrationCommit], options, {allowFailure: true}).status !== 0) fail('PR_HEAD_MISMATCH');
      return pr.headRefOid;
    };
    const base = readBase();
    if (base === receipt.baseCommit) fail('BASE_REFRESH_NOT_NEEDED');
    if (output(git(repository.repositoryRoot, ['rev-parse', 'refs/remotes/origin/master'], options)) !== base) fail('REMOTE_BASE_NOT_FETCHED');
    let latestFeature;
    const checkCandidate = () => {
      if (unpublished) {
        if (output(git(repository.repositoryRoot, ['remote', 'get-url', 'origin'], options)) !== receipt.remoteUrl) fail('REMOTE_IDENTITY_CHANGED');
        if (output(git(repository.repositoryRoot, ['rev-parse', 'refs/remotes/origin/master'], options)) !== base) fail('REMOTE_BASE_NOT_FETCHED');
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
    const updated = {...receipt, baseCommit: base, remoteCommit: unpublished ? null : base, integrationCommit: candidate, ...(unpublished ? {featureCommit: latestFeature} : {baseRefreshPublishedHead: publishedHead}), verification: null, ci: {status: 'pending', runs: []}, status: 'prepared', updatedAt: new Date().toISOString()};
    temporary = destination + '.' + crypto.randomUUID() + '.tmp';
    privateWrite(temporary, JSON.stringify(updated, null, 2) + '\n');
    if (unpublished) {
      if (readBase() !== base) fail('REMOTE_BASE_CHANGED');
      if (checkCandidate() !== candidate) fail('DELIVERY_RECORD_CHANGED');
    }
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
function finishResourceReceipt(repository, taskId, required=closeoutEnabled(repository)) {
  const filename=path.join(repository.commonDirectory,'leon-engineering/resource-closeout',taskId,'receipt.json');
  if (!fs.existsSync(filename)) { if (required) fail('RESOURCE_CLOSEOUT_MISSING'); return; }
  if (fs.lstatSync(filename).isSymbolicLink()) fail('CLOSEOUT_RECEIPT_INVALID');
  const value=JSON.parse(fs.readFileSync(filename,'utf8'));
  if (value.taskId!==taskId || !value.ok || !value.cache?.ok) fail('RESOURCE_CLOSEOUT_BLOCKED');
  writePrivateJson(filename,{...value,status:'complete',gitCleanup:true,restoreVerified:true,blocked:(value.blocked??[]).filter(row=>row.phase!=='git')});
}
function validateCompletedCloseout(repository,taskId,receipt,options) {
  const pending=closeoutFinalization(repository,taskId);
  if (!fs.existsSync(pending)) { if(closeoutEnabled(repository)) fail('CLOSEOUT_FINALIZATION_MISSING'); return; }
  if (fs.lstatSync(pending).isSymbolicLink()) fail('CLOSEOUT_RECEIPT_INVALID');
  const proof=JSON.parse(fs.readFileSync(pending,'utf8'));
  if (proof.taskId!==taskId || proof.candidateCommit!==receipt.integrationCommit || !proof.restoreVerified) fail('CLOSEOUT_FINALIZATION_UNVERIFIED');
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
  options = {...options, startedAt: Date.now()};
  selectGitPath({...options, mutate: true});
  if (!ID.test(taskId ?? '') || !['start', 'prepare', 'publish', 'status', 'cleanup'].includes(action)) fail('DELIVERY_ARGUMENT_INVALID');
  const result = await withRepositoryLock({projectRoot}, async repository => {
    fsck(repository, options);
    const directory = installShim(repository, options);
    const previousPath = process.env.PATH;
    process.env.PATH = directory + path.delimiter + (previousPath ?? '');
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
        result = receipt.status === 'remote_moved'
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
        result = controller.cleanupDelivery(common);
        fsck(repository, options);
        const concurrentRefAdvances = preservationAudit(repository, beforeRefs, beforeWorktrees, validated.managed, options, backup.verifiedPreservationRefs);
        result = {...result, safetyBackup: backup.directory, safetyFsck: 'PASS', concurrentRefAdvances};
        finishResourceReceipt(repository,taskId,resourceContractRequired);
        const finalization=closeoutFinalization(repository,taskId);
        if (fs.existsSync(finalization)) writePrivateJson(finalization,{...JSON.parse(fs.readFileSync(finalization,'utf8')),status:'complete'});
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
    finally { if (previousPath === undefined) delete process.env.PATH; else process.env.PATH = previousPath; }
  }, options);
  // Finish resource/Git cleanup only after releasing the repository lock; recursive
  // cleanup must not deadlock or run while CI/merge is still pending.
  if (action === 'status' && result.status === 'ci_passed' && closeoutEnabled(discover(projectRoot, options))) {
    return runDelivery({projectRoot, taskId, action:'cleanup'}, options);
  }
  return result;
}
export function parseCli(args) {
  const [subcommand, ...rest] = args;
  if (!['check', 'configure', 'backup', 'delivery'].includes(subcommand)) fail('CLI_SUBCOMMAND_INVALID');
  const options = {};
  const values = new Map([['--project', 'projectRoot'], ['--task-id', 'taskId'], ['--slug', 'slug'], ['--worktree-root', 'worktreeRoot'], ['--reviewed-commit', 'reviewedCommit'], ['--verification-command', 'verificationCommand'], ['--verification-status', 'verificationStatus'], ['--verification-duration-seconds', 'verificationDuration']]);
  for (let index = 0; index < rest.length; index++) {
    const item = rest[index];
    if (['--start', '--prepare', '--publish', '--status', '--cleanup'].includes(item)) { if (options.action) fail('CLI_ACTION_INVALID'); options.action = item.slice(2); }
    else if (item === '--repair') options.repair = true;
    else if (item === '--replace-prepared') options.replacePrepared = true;
    else if (values.has(item) && rest[index + 1] && !rest[index + 1].startsWith('--')) options[values.get(item)] = rest[++index];
    else fail('CLI_OPTION_INVALID');
  }
  if (!options.projectRoot || (subcommand === 'delivery' && (!options.taskId || !options.action))) fail('CLI_ARGUMENT_REQUIRED');
  if (subcommand !== 'delivery' && Object.keys(options).some(key => key !== 'projectRoot')) fail('CLI_OPTION_INVALID');
  if (options.reviewedCommit && (options.action !== 'status' || !/^[a-f0-9]{40}$/.test(options.reviewedCommit))) fail('CLI_REVIEW_INVALID');
  if (options.replacePrepared && options.action !== 'prepare' || options.repair && options.action !== 'publish') fail('CLI_OPTION_INVALID');
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
    const result = subcommand === 'check' ? checkRepository(options) : subcommand === 'configure' ? configureRepository(options) : subcommand === 'backup' ? backupRepository(options) : await runDelivery(options);
    const rendered = subcommand === 'delivery' ? Object.fromEntries([
      'taskId', 'status', 'mode', 'defaultBranch', 'baseCommit', 'featureBranch', 'featureWorktree', 'featureCommit',
      'integrationBranch', 'integrationWorktree', 'integrationCommit', 'remoteCommit', 'pullRequest', 'cleanup',
      'safetyAutoMergeDeferred', 'safetyBackup', 'safetyFsck', 'concurrentRefAdvances'
    ].filter(key => result[key] !== undefined).map(key => [key, result[key]])) : result;
    if (subcommand === 'delivery' && result.ci) rendered.ci = {status: result.ci.status, runCount: result.ci.runs?.length ?? 0};
    process.stdout.write(JSON.stringify(rendered, null, 2) + '\n');
  } catch (error) { process.stderr.write(JSON.stringify({status: 'BLOCKED', code: error.code ?? 'GIT_SAFETY_FAILED'}) + '\n'); process.exitCode = 1; }
}
