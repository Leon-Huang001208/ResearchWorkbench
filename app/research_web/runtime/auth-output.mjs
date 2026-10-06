/** Startup-only authentication transport; no auth links enter ordinary logs. */
import { closeSync, existsSync, fsyncSync, lstatSync, openSync, realpathSync, renameSync, unlinkSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { randomUUID } from 'node:crypto';

export function createAuthOutputSink(port, capture, emit) {
  let pending = '';
  let dropping = false;
  return chunk => {
    pending += chunk;
    let end;
    while ((end = pending.indexOf('\n')) >= 0) {
      const line = pending.slice(0, end + 1);
      pending = pending.slice(end + 1);
      if (dropping) { dropping = false; continue; }
      if (/[?&]token=/.test(line)) {
        const match = line.match(/dsh web: http:\/\/127\.0\.0\.1:(\d+)\/\?token=([A-Za-z0-9_-]{43})(?=\s|$)/);
        if (match && Number(match[1]) === port) capture(match[2]);
        emit('runtime_auth_startup_output_redacted\n');
      } else { emit(line); }
    }
    if (pending.length > 65536) {
      pending = '';
      dropping = true;
      emit('runtime_startup_output_truncated\n');
    }
  };
}

export function writeBootstrapAuth(path, metadata, token) {
  const parent = dirname(path);
  const directory = lstatSync(parent);
  if (realpathSync(parent) !== parent || !directory.isDirectory() || directory.isSymbolicLink() ||
      (process.platform !== 'win32' && directory.uid !== process.getuid())) throw Error('runtime_auth_handoff_failed');
  if (existsSync(path)) {
    const item = lstatSync(path);
    if (!item.isFile() || item.isSymbolicLink() || item.nlink !== 1 ||
        (process.platform !== 'win32' && ((item.mode & 0o077) || item.uid !== process.getuid()))) {
      throw Error('runtime_auth_handoff_failed');
    }
  }
  const temporary = join(parent, `.auth-bootstrap-${randomUUID()}`);
  let fd;
  let created = false;
  try {
    fd = openSync(temporary, 'wx', 0o600);
    created = true;
    writeFileSync(fd, JSON.stringify({ ...metadata, bootstrap_token: token }));
    fsyncSync(fd);
    closeSync(fd);
    fd = undefined;
    renameSync(temporary, path);
    created = false;
  } catch { throw Error('runtime_auth_handoff_failed'); }
  finally {
    if (fd !== undefined) closeSync(fd);
    if (created) unlinkSync(temporary);
  }
}
