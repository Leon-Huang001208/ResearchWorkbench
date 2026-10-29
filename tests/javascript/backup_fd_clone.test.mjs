import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';

const project = fileURLToPath(new URL('../../', import.meta.url));
const logRoot = path.join(project, 'logs/backup-cow-admission/fd-primitive');
const pythonPath = '/opt/homebrew/bin/python3.12';
fs.mkdirSync(logRoot, {recursive: true});
function freeFloor(gib) {
  const space = fs.statfsSync(logRoot, {bigint: true});
  assert.ok(space.bavail * space.bsize >= BigInt(gib) * 1024n ** 3n, `free space below ${gib} GiB`);
}
freeFloor(3);

function fixture(callback) {
  freeFloor(2);
  const root = fs.mkdtempSync(path.join(logRoot, 'sample-'));
  fs.chmodSync(root, 0o700);
  const source = path.join(root, 'source.data');
  const directory = path.join(root, 'private');
  fs.mkdirSync(directory, {mode: 0o700});
  const bytes = Buffer.from('ordinary synthetic data\n'.repeat(64));
  fs.writeFileSync(source, bytes, {mode: 0o640});
  const sourceFd = fs.openSync(source, fs.constants.O_RDONLY | fs.constants.O_NOFOLLOW);
  const directoryFd = fs.openSync(directory, fs.constants.O_RDONLY | fs.constants.O_NOFOLLOW);
  try { return callback({root, source, directory, bytes, sourceFd, directoryFd}); }
  finally {
    fs.closeSync(directoryFd);
    fs.closeSync(sourceFd);
    fs.rmSync(root, {recursive: true});
    freeFloor(2);
  }
}

function args(api, f, extra = {}) {
  return {
    sourceFd: f.sourceFd, directoryFd: f.directoryFd, destinationDirectory: f.directory,
    destinationName: 'copy.data', expectedSource: api.sourceFacts(f.sourceFd),
    expectedSha256: crypto.createHash('sha256').update(f.bytes).digest('hex'),
    pythonPath, ...extra,
  };
}

test('pinned descriptor clone API is available', async () => {
  let api;
  try { api = await import('../../scripts/backup_fd_clone.mjs'); } catch (error) {
    if (error.code !== 'ERR_MODULE_NOT_FOUND') throw error;
  }
  assert.equal(typeof api?.clonePinnedFile, 'function');
});

test('Darwin clone inherits the pinned FD and has independent bytes, mode and inode', {skip: process.platform !== 'darwin'}, async () => {
  const api = await import('../../scripts/backup_fd_clone.mjs');
  fixture(f => {
    fs.renameSync(f.source, path.join(f.root, 'old.data'));
    fs.writeFileSync(f.source, 'other ordinary data', {mode: 0o600});
    const events = [];
    const result = api.clonePinnedFile(args(api, f, {onEvent: event => events.push(event)}));
    assert.deepEqual(result, {status: 'cloned', code: 'CLONE_VERIFIED', sha256: args(api, f).expectedSha256});
    const target = path.join(f.directory, 'copy.data');
    assert.deepEqual(fs.readFileSync(target), f.bytes);
    assert.equal(fs.statSync(target).mode & 0o777, 0o600);
    assert.equal(fs.statSync(target).nlink, 1);
    assert.notEqual(fs.statSync(target).ino, fs.fstatSync(f.sourceFd).ino);
    // Both mutation directions are private synthetic data, never source code.
    fs.writeFileSync(path.join(f.root, 'old.data'), 'changed source');
    assert.deepEqual(fs.readFileSync(target), f.bytes);
    fs.writeFileSync(target, 'changed clone');
    assert.equal(fs.readFileSync(path.join(f.root, 'old.data'), 'utf8'), 'changed source');
    assert.equal(events[0].code, 'CLONE_VERIFIED');
    assert.equal(Object.keys(events[0]).length, 3);
  });
});

test('destination regular, symbolic and hardlink entries remain untouched', {skip: process.platform !== 'darwin'}, async () => {
  const api = await import('../../scripts/backup_fd_clone.mjs');
  for (const kind of ['file', 'symlink', 'hardlink']) fixture(f => {
    const target = path.join(f.directory, 'copy.data');
    const other = path.join(f.root, 'other.data');
    fs.writeFileSync(other, 'existing ordinary data');
    if (kind === 'file') fs.writeFileSync(target, 'existing ordinary data');
    else if (kind === 'symlink') fs.symlinkSync(other, target);
    else fs.linkSync(other, target);
    const before = fs.lstatSync(target);
    assert.deepEqual(api.clonePinnedFile(args(api, f)), {status: 'error', code: 'CLONE_TARGET_EXISTS'});
    assert.equal(fs.lstatSync(target).ino, before.ino);
    assert.equal(fs.readFileSync(target, 'utf8'), 'existing ordinary data');
  });
});

test('unsafe basenames, mismatched source facts and hash fail before creating data', async () => {
  const api = await import('../../scripts/backup_fd_clone.mjs');
  fixture(f => {
    for (const destinationName of ['', '.', '..', '../copy.data', 'a/b', 'a\0b']) {
      assert.equal(api.clonePinnedFile(args(api, f, {destinationName})).code, 'CLONE_NAME_INVALID');
    }
    if (process.platform === 'darwin') assert.equal(api.clonePinnedFile(args(api, f, {expectedSource: {...api.sourceFacts(f.sourceFd), ino: '0'}})).code, 'CLONE_SOURCE_INVALID');
    if (process.platform === 'darwin') assert.equal(api.clonePinnedFile(args(api, f, {expectedSha256: '0'.repeat(64)})).code, 'CLONE_SOURCE_CHANGED');
    assert.deepEqual(fs.readdirSync(f.directory), []);
  });
});

test('source directories/hardlinks and nonprivate or mismatched directory path are refused', {skip: process.platform !== 'darwin'}, async () => {
  const api = await import('../../scripts/backup_fd_clone.mjs');
  fixture(f => {
    assert.equal(api.clonePinnedFile(args(api, f, {sourceFd: f.directoryFd, directoryFd: f.sourceFd, expectedSource: api.sourceFacts(f.directoryFd)})).code, 'CLONE_SOURCE_INVALID');
    fs.linkSync(f.source, path.join(f.root, 'source-alias.data'));
    assert.equal(api.clonePinnedFile(args(api, f)).code, 'CLONE_SOURCE_INVALID');
    fs.unlinkSync(path.join(f.root, 'source-alias.data'));
    fs.chmodSync(f.directory, 0o755);
    assert.equal(api.clonePinnedFile(args(api, f)).code, 'CLONE_DIRECTORY_NOT_PRIVATE');
    fs.chmodSync(f.directory, 0o700);
    assert.equal(api.clonePinnedFile(args(api, f, {destinationDirectory: f.root})).code, 'CLONE_DIRECTORY_PATH_UNVERIFIED');
    const directoryAlias = path.join(f.root, 'directory-alias');
    fs.symlinkSync(f.directory, directoryAlias);
    assert.equal(api.clonePinnedFile(args(api, f, {destinationDirectory: directoryAlias})).code, 'CLONE_DIRECTORY_PATH_UNVERIFIED');
    assert.deepEqual(fs.readdirSync(f.directory), []);
  });
});

test('missing interpreter is explicitly unsupported with no fallback side effects', async () => {
  const api = await import('../../scripts/backup_fd_clone.mjs');
  fixture(f => {
    const prefix = Buffer.alloc(5);
    fs.readSync(f.sourceFd, prefix, 0, prefix.length, null);
    const result = api.clonePinnedFile(args(api, f, {pythonPath: path.join(f.root, 'missing-python')}));
    assert.equal(result.status, 'unsupported');
    assert.equal(result.code, process.platform === 'darwin' ? 'CLONE_PYTHON_UNAVAILABLE' : 'CLONE_PLATFORM_UNSUPPORTED');
    assert.deepEqual(fs.readdirSync(f.directory), []);
    const next = Buffer.alloc(5);
    fs.readSync(f.sourceFd, next, 0, next.length, null);
    assert.deepEqual(next, f.bytes.subarray(5, 10));
  });
});

test('uncertain logging after a clone retains its target and never retries', {skip: process.platform !== 'darwin'}, async () => {
  const api = await import('../../scripts/backup_fd_clone.mjs');
  fixture(f => {
    const result = api.clonePinnedFile(args(api, f, {onEvent: () => { throw new Error('synthetic log failure'); }}));
    assert.deepEqual(result, {status: 'unknown', code: 'CLONE_LOG_FAILED'});
    assert.deepEqual(fs.readFileSync(path.join(f.directory, 'copy.data')), f.bytes);
    assert.deepEqual(fs.readdirSync(f.directory), ['copy.data']);
  });
});
