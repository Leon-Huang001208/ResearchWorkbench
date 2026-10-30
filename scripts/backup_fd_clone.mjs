/** Optional FD-pinned Darwin clone. Does not certify capacity or a full backup.
 * Callers retain their source-path/ancestor checks and must never retry an
 * error/unknown result through a stream. Unsupported alone permits a later,
 * separately capacity-admitted stream attempt. No destination is ever removed.
 */
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {spawnSync} from 'node:child_process';

const HELPER = fileURLToPath(new URL('./backup_fd_clone.py', import.meta.url));
const FACT_KEYS = ['dev', 'ino', 'uid', 'gid', 'mode', 'nlink', 'size', 'mtimeNs', 'ctimeNs'];
const HASH = /^[a-f0-9]{64}$/;
const fail = code => { throw Object.assign(new Error(code), {code}); };

/** Use bigint stat so large sizes, inodes and nanosecond times are not rounded. */
export function sourceFacts(fd) {
  const value = fs.fstatSync(fd, {bigint: true});
  return Object.fromEntries(FACT_KEYS.map(key => [key, String(value[key])]));
}

function sameFacts(left, right) {
  return right && Object.keys(right).length === FACT_KEYS.length && FACT_KEYS.every(key => left[key] === right[key]);
}

function hashFd(fd) {
  const hash = crypto.createHash('sha256');
  const buffer = Buffer.allocUnsafe(1024 * 1024);
  let position = 0;
  let count;
  while ((count = fs.readSync(fd, buffer, 0, buffer.length, position))) {
    hash.update(buffer.subarray(0, count));
    position += count;
    if (!Number.isSafeInteger(position)) fail('CLONE_SIZE_UNSUPPORTED');
  }
  return hash.digest('hex');
}

function privateDirectory(directoryPath, directoryFd) {
  if (typeof directoryPath !== 'string' || !path.isAbsolute(directoryPath)) fail('CLONE_DIRECTORY_PATH_UNVERIFIED');
  for (let current = directoryPath;; current = path.dirname(current)) {
    const value = fs.lstatSync(current, {bigint: true});
    if (!value.isDirectory() || value.isSymbolicLink()) fail('CLONE_DIRECTORY_PATH_UNVERIFIED');
    if (current === path.dirname(current)) break;
  }
  const current = fs.lstatSync(directoryPath, {bigint: true});
  const opened = fs.fstatSync(directoryFd, {bigint: true});
  if (current.ino !== opened.ino || current.dev !== opened.dev || current.uid !== BigInt(process.getuid()) || (current.mode & 0o7777n) !== 0o700n) fail('CLONE_DIRECTORY_PATH_UNVERIFIED');
}

/** The Python path is an absolute trusted caller choice, never a PATH lookup.
 * Only a fixed helper file, isolated stdlib Python, FDs 3/4 and JSON are passed.
 * onEvent receives stable non-sensitive results for the caller's logs/ facility.
 * beforeSpawn is rejection-only: after all source hashing, only literal true
 * continues the original checks/attempt. It grants no runtime/record authority.
 */
export function clonePinnedFile({sourceFd, directoryFd, destinationDirectory, destinationName, expectedSource, expectedSha256, pythonPath, beforeSpawn = () => true, onEvent = () => {}} = {}) {
  let attempted = false;
  let targetFd;
  let outcome;
  try {
    if (!Number.isInteger(sourceFd) || sourceFd < 0 || !Number.isInteger(directoryFd) || directoryFd < 0 || sourceFd === directoryFd || typeof onEvent !== 'function' || typeof beforeSpawn !== 'function') fail('CLONE_REQUEST_INVALID');
    if (typeof destinationName !== 'string' || !destinationName || ['.', '..'].includes(destinationName) || /[/\0]/u.test(destinationName) || Buffer.byteLength(destinationName) > 255) fail('CLONE_NAME_INVALID');
    if (typeof pythonPath !== 'string' || !path.isAbsolute(pythonPath) || typeof expectedSha256 !== 'string' || !HASH.test(expectedSha256)) fail('CLONE_REQUEST_INVALID');
    if (process.platform !== 'darwin') fail('CLONE_PLATFORM_UNSUPPORTED');
    const opened = fs.fstatSync(sourceFd, {bigint: true});
    if (!opened.isFile() || opened.nlink !== 1n || opened.uid !== BigInt(process.getuid()) || (opened.mode & 0o7000n) !== 0n || !sameFacts(sourceFacts(sourceFd), expectedSource)) fail('CLONE_SOURCE_INVALID');
    if (opened.size > BigInt(Number.MAX_SAFE_INTEGER)) fail('CLONE_SIZE_UNSUPPORTED');
    const directory = fs.fstatSync(directoryFd, {bigint: true});
    if (!directory.isDirectory() || directory.uid !== BigInt(process.getuid()) || (directory.mode & 0o7777n) !== 0o700n) fail('CLONE_DIRECTORY_NOT_PRIVATE');
    privateDirectory(destinationDirectory, directoryFd);
    if (hashFd(sourceFd) !== expectedSha256 || !sameFacts(sourceFacts(sourceFd), expectedSource)) {
      fail('CLONE_SOURCE_CHANGED');
    } else {
      let maySpawn = false;
      try {maySpawn = beforeSpawn() === true;} catch {maySpawn = false;}
      if (!maySpawn) fail('CLONE_TOOLCHAIN_UNAVAILABLE');
      attempted = true;
      const child = spawnSync(pythonPath, ['-I', '-S', '-B', HELPER], {
        input: JSON.stringify({name: destinationName, expectedSource}),
        stdio: ['pipe', 'pipe', 'pipe', sourceFd, directoryFd],
        encoding: 'utf8', timeout: 30_000, maxBuffer: 16 * 1024,
        // Isolated Python ignores Python environment configuration; no inherited
        // credentials or dynamic-loader configuration are needed by this bridge.
        env: {},
      });
      if (child.error?.code === 'ENOENT') {
        outcome = {status: 'unsupported', code: 'CLONE_PYTHON_UNAVAILABLE'};
      } else if (child.error || child.signal || child.status !== 0) {
        outcome = {status: 'unknown', code: 'CLONE_HELPER_UNVERIFIED'};
      } else {
        let reply;
        try { reply = JSON.parse(child.stdout); } catch { fail('CLONE_HELPER_UNVERIFIED'); }
        if (!reply || !['cloned', 'unsupported', 'error', 'unknown'].includes(reply.status) || !/^CLONE_[A-Z_]+$/u.test(reply.code)) fail('CLONE_HELPER_UNVERIFIED');
        if (reply.status !== 'cloned') {
          outcome = {status: reply.status, code: reply.code};
        } else {
          privateDirectory(destinationDirectory, directoryFd);
          const targetPath = path.join(destinationDirectory, destinationName);
          const before = fs.lstatSync(targetPath, {bigint: true});
          targetFd = fs.openSync(targetPath, fs.constants.O_RDONLY | fs.constants.O_NOFOLLOW);
          const target = fs.fstatSync(targetFd, {bigint: true});
          if (!target.isFile() || before.isSymbolicLink() || target.nlink !== 1n || before.ino !== target.ino || before.dev !== target.dev || target.uid !== BigInt(process.getuid()) || (target.mode & 0o7777n) !== 0o600n || target.ino === opened.ino && target.dev === opened.dev || !sameFacts(sourceFacts(targetFd), reply.target)) fail('CLONE_TARGET_INVALID');
          if (hashFd(targetFd) !== expectedSha256 || hashFd(sourceFd) !== expectedSha256 || !sameFacts(sourceFacts(sourceFd), expectedSource)) fail('CLONE_SOURCE_CHANGED');
          fs.fsyncSync(targetFd);
          fs.fsyncSync(directoryFd);
          privateDirectory(destinationDirectory, directoryFd);
          const afterPath = fs.lstatSync(targetPath, {bigint: true});
          if (!sameFacts(sourceFacts(targetFd), reply.target) || !sameFacts(Object.fromEntries(FACT_KEYS.map(key => [key, String(afterPath[key])])), reply.target)) fail('CLONE_TARGET_CHANGED');
          outcome = {status: 'cloned', code: 'CLONE_VERIFIED', sha256: expectedSha256};
        }
      }
    }
  } catch (error) {
    outcome = {status: attempted ? 'unknown' : ['CLONE_PLATFORM_UNSUPPORTED', 'CLONE_TOOLCHAIN_UNAVAILABLE'].includes(error.code) ? 'unsupported' : 'error', code: /^CLONE_[A-Z_]+$/u.test(error.code ?? '') ? error.code : 'CLONE_IO_FAILED'};
  } finally {
    if (targetFd !== undefined) {
      try { fs.closeSync(targetFd); } catch { outcome = {status: 'unknown', code: 'CLONE_CLOSE_FAILED'}; }
    }
  }
  if (typeof onEvent !== 'function') return outcome;
  try { onEvent({event: 'backup_fd_clone', status: outcome.status, code: outcome.code}); } catch {
    return {status: 'unknown', code: 'CLONE_LOG_FAILED'};
  }
  return outcome;
}
