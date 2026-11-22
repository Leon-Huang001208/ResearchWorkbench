import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {spawn, spawnSync} from 'node:child_process';

const SHA = /^[a-f0-9]{40}$/;
const HASH = /^[a-f0-9]{64}$/;
const WORKFLOWS = ['project-constraints.yml', 'research-web-checks.yml', 'research-web-bootstrap.yml'];
const fail = code => { throw Object.assign(new Error(code), {code}); };
const hash = bytes => crypto.createHash('sha256').update(bytes).digest('hex');

function exactPath(filename) {
  if (typeof filename !== 'string' || !path.isAbsolute(filename) ||
      fs.realpathSync(filename) !== filename) fail('DEPLOYMENT_EVIDENCE_PATH_INVALID');
}

function privateJson(filename) {
  exactPath(filename);
  const fd = fs.openSync(filename, fs.constants.O_RDONLY | fs.constants.O_NOFOLLOW | fs.constants.O_NONBLOCK);
  try {
    const stat = fs.fstatSync(fd);
    if (!stat.isFile() || stat.uid !== process.getuid() || stat.nlink !== 1 ||
        (stat.mode & 0o7777) !== 0o600 || stat.size > 1024 * 1024) fail('DEPLOYMENT_EVIDENCE_INVALID');
    const bytes = fs.readFileSync(fd);
    const after = fs.lstatSync(filename);
    if (bytes.length !== stat.size || ['dev', 'ino', 'size', 'mtimeMs', 'ctimeMs'].some(key => stat[key] !== after[key]))
      fail('DEPLOYMENT_EVIDENCE_CHANGED');
    return {value: JSON.parse(bytes), digest: hash(bytes)};
  } finally {
    fs.closeSync(fd);
  }
}

function present(filename) {
  return !!fs.lstatSync(filename, {throwIfNoEntry: false});
}

function artifact(root, record, commit) {
  if (!HASH.test(record?.sha256 ?? '') || typeof record?.path !== 'string' ||
      !record.path.startsWith(path.join(root, 'artifacts') + path.sep)) fail('DEPLOYMENT_ROLLBACK_UNVERIFIED');
  const binding = privateJson(path.join(path.dirname(record.path), 'binding.json')).value;
  if (binding.source !== commit || binding.sha256 !== record.sha256) fail('DEPLOYMENT_ROLLBACK_UNVERIFIED');
  exactPath(record.path);
  const fd = fs.openSync(record.path, fs.constants.O_RDONLY | fs.constants.O_NOFOLLOW | fs.constants.O_NONBLOCK);
  try {
    const info = fs.fstatSync(fd);
    if (!info.isFile() || info.uid !== process.getuid() || !info.size || info.size > 1024 ** 3)
      fail('DEPLOYMENT_ROLLBACK_UNVERIFIED');
    const digest = crypto.createHash('sha256');
    const buffer = Buffer.allocUnsafe(1024 * 1024);
    let offset = 0;
    while (offset < info.size) {
      const size = fs.readSync(fd, buffer, 0, Math.min(buffer.length, info.size - offset), offset);
      if (!size) break;
      offset += size;
      digest.update(buffer.subarray(0, size));
    }
    const after = fs.lstatSync(record.path);
    if (offset !== info.size || digest.digest('hex') !== record.sha256 ||
        ['dev', 'ino', 'size', 'mtimeMs', 'ctimeMs'].some(key => after[key] !== info[key]))
      fail('DEPLOYMENT_ROLLBACK_UNVERIFIED');
  } finally {
    fs.closeSync(fd);
  }
}

function observeNative(port) {
  const result = spawnSync('/usr/bin/curl', ['--noproxy', '*', '--max-time', '5', '--fail', '--silent',
    `http://127.0.0.1:${port}/api/research/resident`], {timeout: 6000, maxBuffer: 65536, encoding: 'utf8'});
  if (result.error || result.status !== 0) fail('DEPLOYMENT_LIVE_UNVERIFIED');
  return JSON.parse(result.stdout);
}

function listening(port, pid) {
  const result = spawnSync('/usr/sbin/lsof', ['-nP', '-a', '-p', String(pid), `-iTCP:${port}`, '-sTCP:LISTEN', '-Fp'],
    {timeout: 6000, maxBuffer: 65536, encoding: 'utf8'});
  return !result.error && result.status === 0 && result.stdout.split('\n').includes('p' + pid);
}

// Use the same flock and order as the resident deployment path. An inherited
// pipe keeps the shared lease alive across Node's synchronous Git calls.
export async function withNativeRetirementAdmission(root, run) {
  exactPath(root);
  const lock = path.join(root, 'admission.lock');
  const before = fs.lstatSync(lock, {throwIfNoEntry: false});
  if (!before?.isFile() || before.uid !== process.getuid() || (before.mode & 0o7777) !== 0o600 ||
      before.nlink !== 1) fail('DEPLOYMENT_ADMISSION_UNVERIFIED');
  const code = [
    'import fcntl, os, stat, sys',
    'fd = os.open(sys.argv[1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)',
    's = os.fstat(fd)',
    'if not stat.S_ISREG(s.st_mode) or s.st_uid != os.getuid() or s.st_nlink != 1 or stat.S_IMODE(s.st_mode) != 0o600: sys.exit(2)',
    'if (s.st_dev, s.st_ino) != tuple(map(int, sys.argv[2:])): sys.exit(2)',
    'fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)',
    'print("held", flush=True)',
    'sys.stdin.buffer.read(1)',
  ].join('\n');
  const child = spawn('/opt/homebrew/bin/python3.12',
    ['-I', '-S', '-c', code, lock, String(before.dev), String(before.ino)],
    {stdio: ['pipe', 'pipe', 'ignore']});
  child.stdin.on('error', () => {});
  const closed = new Promise(resolve => child.once('close', resolve));
  try {
    const acquired = await new Promise(resolve => {
      const timer = setTimeout(() => { child.kill(); resolve(false); }, 5000);
      const done = value => { clearTimeout(timer); resolve(value); };
      child.once('error', () => done(false));
      child.once('close', () => done(false));
      let message = '';
      child.stdout.on('data', bytes => {
        message += bytes.toString('utf8');
        if (message.includes('\n')) done(message === 'held\n');
      });
    });
    if (!acquired) fail('DEPLOYMENT_ADMISSION_BUSY');
    const assertHeld = () => {
      const current = fs.lstatSync(lock, {throwIfNoEntry: false});
      if (child.exitCode !== null || child.signalCode !== null ||
          !current?.isFile() || current.dev !== before.dev || current.ino !== before.ino)
        fail('DEPLOYMENT_ADMISSION_CHANGED');
    };
    assertHeld();
    return await run(assertHeld);
  } finally {
    child.stdin.end();
    await closed;
  }
}

export function nativeRetirementAcceptance({root, commonDirectory}, {installedHead, live = observeNative, listener = listening} = {}) {
  try {
    exactPath(root);
    const info = fs.statSync(root);
    if (!info.isDirectory() || info.uid !== process.getuid() || (info.mode & 0o7777) !== 0o700)
      fail('DEPLOYMENT_EVIDENCE_INVALID');
    if (present(path.join(root, 'transaction.json'))) fail('DEPLOYMENT_IN_PROGRESS');
    const config = privateJson(path.join(root, 'config.json'));
    const accepted = privateJson(path.join(root, 'accepted.json'));
    const state = privateJson(path.join(root, 'state.json'));
    const manifest = privateJson(path.join(path.dirname(root), 'install', 'manifest.json'));
    const webFile = path.join(path.dirname(root), 'run', 'web.json');
    const web = privateJson(webFile);
    const {project, project_identity: identity, source_common: source, web_port: port} = config.value;
    if (source !== commonDirectory || config.value.schema_version !== 1 ||
        config.value.repository !== 'Leon-Huang001208/ResearchWorkbench' || port !== 8088)
      fail('DEPLOYMENT_REPOSITORY_MISMATCH');
    exactPath(project);
    const projectStat = fs.statSync(project);
    if (!projectStat.isDirectory() || identity?.[0] !== projectStat.dev || identity?.[1] !== projectStat.ino)
      fail('DEPLOYMENT_REPOSITORY_MISMATCH');
    const {target, previous, proof, old_wheel: oldWheel, new_wheel: newWheel} = accepted.value;
    if (!SHA.test(target ?? '') || !SHA.test(previous ?? '') || target === previous ||
        proof?.sha !== target || !SHA.test(proof?.head ?? '') || !Number.isSafeInteger(proof?.pull_request) ||
        proof.pull_request < 1 || !Array.isArray(proof.ci) || proof.ci.length !== WORKFLOWS.length ||
        WORKFLOWS.some(workflow => proof.ci.filter(row => row?.workflow === workflow &&
          Number.isSafeInteger(row.run) && row.run > 0 && SHA.test(row.checkout ?? '')).length !== 1) ||
        !['ready', 'deployed'].includes(state.value.status) || state.value.deployed !== target ||
        manifest.value.code_commit !== target || manifest.value.status !== 'installed' ||
        installedHead(project) !== target) fail('DEPLOYMENT_NOT_ACCEPTED');
    const quarantine = path.join(root, 'quarantine.json');
    if (present(quarantine) && privateJson(quarantine).value.sha === target) fail('DEPLOYMENT_NOT_ACCEPTED');
    artifact(root, oldWheel, previous);
    artifact(root, newWheel, target);
    const {pid, role, port: webPort, project_root: webProject} = web.value;
    if (!Number.isSafeInteger(pid) || pid < 2 || role !== 'web' || webPort !== port ||
        webProject !== project || !listener(port, pid)) fail('DEPLOYMENT_LIVE_UNVERIFIED');
    const observed = live(port);
    if (observed?.enabled !== true || observed.maintenance !== false || observed.revision !== target)
      fail('DEPLOYMENT_LIVE_UNVERIFIED');
    if (present(path.join(root, 'transaction.json')) || privateJson(path.join(root, 'accepted.json')).digest !== accepted.digest ||
        privateJson(webFile).digest !== web.digest || !listener(port, pid))
      fail('DEPLOYMENT_EVIDENCE_CHANGED');
    return {target, previous, project, receiptSha256: accepted.digest,
      rollback: {path: oldWheel.path, sha256: oldWheel.sha256}};
  } catch (error) {
    if (/^DEPLOYMENT_[A-Z_]+$/.test(error.code ?? '')) throw error;
    fail('DEPLOYMENT_EVIDENCE_UNAVAILABLE');
  }
}
