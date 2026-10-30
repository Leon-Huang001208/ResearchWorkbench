import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {admitFileStream, fileStreamRequirement, measureAvailable, STREAM_METADATA_ALLOWANCE, STREAM_RESERVE} from '../../scripts/backup_capacity.mjs';
import {snapshotRegularFile, resolveSnapshotPython, toolchainReuseDecision, selectedExecutableReference} from '../../scripts/git_safety.mjs';

const project = fileURLToPath(new URL('../../', import.meta.url));
const logRoot = path.join(project, 'logs/backup-cow-admission/integration');
fs.mkdirSync(logRoot, {recursive: true});
const trustedHostPython = resolveSnapshotPython(project);
const free = () => {const s = fs.statfsSync(logRoot, {bigint: true}); return s.bavail * s.bsize;};
assert.ok(free() >= 3n * 1024n ** 3n, 'start free space below 3 GiB');
const digest = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const enough = () => ({availableBytes: 8n * 1024n ** 3n, blockSize: 4096n, device: 1n});
const footprints = [];
process.on('exit', () => {
  fs.writeFileSync(path.join(logRoot, `synthetic-footprint-${process.pid}.json`), JSON.stringify({samples: footprints.length, maxRetainedLogicalBytes: Math.max(0, ...footprints), totalRetainedLogicalBytes: footprints.reduce((a, b) => a + b, 0), remainingSampleDirectories: fs.readdirSync(logRoot).filter(name => name.startsWith('sample-')).length}) + '\n', {mode: 0o600, flag: 'wx'});
});
function retainedBytes(directory) {
  return fs.readdirSync(directory, {withFileTypes: true}).reduce((total, item) => {
    const target = path.join(directory, item.name);
    return total + (item.isDirectory() ? retainedBytes(target) : fs.lstatSync(target).size);
  }, 0);
}

function fixture(callback) {
  assert.ok(free() >= STREAM_RESERVE, 'continuing free space below 2 GiB');
  const root = fs.mkdtempSync(path.join(logRoot, 'sample-'));
  fs.chmodSync(root, 0o700);
  const sourceRoot = path.join(root, 'source'), directory = path.join(root, 'backup');
  fs.mkdirSync(sourceRoot, {mode: 0o700}); fs.mkdirSync(directory, {mode: 0o700});
  const bytes = Buffer.from('small synthetic snapshot\n'.repeat(32));
  const source = path.join(sourceRoot, 'file.txt');
  fs.writeFileSync(source, bytes, {mode: 0o640});
  const item = {path: 'file.txt', type: 'file', mode: 0o640, sha256: digest(bytes)};
  const manifest = {files: []}, events = [];
  const context = {resolvePython: () => undefined, measure: enough, onEvent: event => events.push(event)};
  try { return callback({root, sourceRoot, directory, source, bytes, item, manifest, events, context}); }
  finally {footprints.push(retainedBytes(root)); fs.rmSync(root, {recursive: true}); assert.ok(free() >= STREAM_RESERVE);}
}
function snapshot(f, context = {}) {
  return snapshotRegularFile(f.sourceRoot, f.item, f.directory, 'payload/file', f.manifest, {...f.context, ...context});
}
function code(expected) {return error => error.code === expected;}

test('single-file arithmetic rounds content and declares metadata plus the 2 GiB reserve', () => {
  assert.equal(fileStreamRequirement({fileBytes: 4097n, blockSize: 4096n}), STREAM_RESERVE + STREAM_METADATA_ALLOWANCE + 8192n);
  assert.throws(() => fileStreamRequirement({fileBytes: undefined, blockSize: 4096n}), code('BACKUP_CAPACITY_UNKNOWN'));
  for (const fileBytes of [-1n, Number.MAX_SAFE_INTEGER + 1, 1n << 63n]) {
    assert.throws(() => fileStreamRequirement({fileBytes, blockSize: 4096n}), code('BACKUP_CAPACITY_INVALID'));
  }
  assert.throws(() => fileStreamRequirement({fileBytes: (1n << 63n) - 1n, blockSize: 4096n}), code('BACKUP_CAPACITY_INVALID'));
});

test('measurement uses actual destination available blocks and does not use bfree', () => fixture(f => {
  const actual = measureAvailable(f.directory);
  const s = fs.statfsSync(f.directory, {bigint: true});
  assert.equal(actual.device, fs.statSync(f.directory, {bigint: true}).dev);
  assert.ok(actual.availableBytes >= 0n); assert.equal(actual.blockSize, s.bsize);
  const statfs = fs.statfsSync;
  try {
    fs.statfsSync = () => ({bsize: 4096n, bavail: 2n, bfree: 100n});
    assert.equal(measureAvailable(f.directory).availableBytes, 8192n);
    fs.statfsSync = () => ({bsize: 4096n, bavail: 1n << 63n});
    assert.throws(() => measureAvailable(f.directory), code('BACKUP_CAPACITY_INVALID'));
    fs.statfsSync = () => {throw Object.assign(new Error('unsupported'), {code: 'ENOSYS'});};
    assert.throws(() => measureAvailable(f.directory), code('BACKUP_CAPACITY_MEASUREMENT_FAILED'));
  } finally {fs.statfsSync = statfs;}
  assert.throws(() => admitFileStream({directory: f.directory, fileBytes: 1n, measure: () => ({availableBytes: undefined, blockSize: 4096n, device: 1n})}), code('BACKUP_CAPACITY_UNKNOWN'));
  assert.throws(() => admitFileStream({directory: f.directory, fileBytes: 1n, measure: () => {throw new Error('synthetic');}}), code('BACKUP_CAPACITY_MEASUREMENT_FAILED'));
}));

test('unsupported optimization streams complete bytes only after target-FS admission', () => fixture(f => {
  snapshot(f);
  const target = path.join(f.directory, 'payload/file'), stat = fs.statSync(target);
  assert.deepEqual(fs.readFileSync(target), f.bytes); assert.equal(stat.mode & 0o777, 0o600); assert.equal(stat.nlink, 1);
  assert.deepEqual(f.manifest.files, [{path: 'payload/file', sha256: digest(f.bytes)}]);
  assert.ok(f.events.some(x => x.phase === 'snapshot-stream' && x.status === 'PASS'));
  fs.writeFileSync(f.source, 'changed source'); assert.deepEqual(fs.readFileSync(target), f.bytes);
}));

test('insufficient or unknown fallback budget refuses before opening payload', () => {
  for (const measure of [() => ({...enough(), availableBytes: STREAM_RESERVE}), () => ({...enough(), availableBytes: undefined})]) fixture(f => {
    assert.throws(() => snapshot(f, {measure}), error => ['BACKUP_CAPACITY_INSUFFICIENT', 'BACKUP_CAPACITY_UNKNOWN'].includes(error.code));
    assert.equal(fs.existsSync(path.join(f.directory, 'payload/file')), false); assert.deepEqual(f.manifest.files, []);
  });
});

test('source hardlinks retain original stream compatibility and skip clone', () => fixture(f => {
  fs.linkSync(f.source, path.join(f.sourceRoot, 'alias'));
  snapshot(f, {resolvePython: () => '/never/executed', clone: () => {assert.fail('ineligible hardlink attempted clone');}});
  assert.equal(fs.statSync(path.join(f.directory, 'payload/file')).nlink, 1);
  assert.deepEqual(fs.readFileSync(path.join(f.directory, 'payload/file')), f.bytes);
}));

test('source special mode retains original stream compatibility and is not cloned', () => fixture(f => {
  fs.chmodSync(f.source, 0o4640);
  snapshot(f, {resolvePython: () => '/never/executed', clone: () => {assert.fail('special mode attempted clone');}});
  assert.equal(fs.statSync(path.join(f.directory, 'payload/file')).mode & 0o7777, 0o600);
}));

test('error or unknown clone effects retain target and forbid stream admission', () => {
  for (const status of ['error', 'unknown', 'unsupported']) fixture(f => {
    assert.throws(() => snapshot(f, {
      resolvePython: () => '/never/executed',
      clone: ({destinationDirectory, destinationName}) => {fs.writeFileSync(path.join(destinationDirectory, destinationName), 'retained', {flag: 'wx', mode: 0o600}); return {status, code: 'CLONE_SYNTHETIC'};},
      measure: () => {assert.fail('ambiguous or existing target reached stream');},
    }), error => status === 'unsupported' ? error.code === 'BACKUP_TARGET_EXISTS' : error.code === 'CLONE_SYNTHETIC');
    assert.equal(fs.readFileSync(path.join(f.directory, 'payload/file'), 'utf8'), 'retained'); assert.deepEqual(f.manifest.files, []);
  });
});

test('unsupported clone with absent target preserves source offset and falls back', () => fixture(f => {
  snapshot(f, {resolvePython: () => '/never/executed', clone: () => ({status: 'unsupported', code: 'CLONE_SYNTHETIC'})});
  assert.deepEqual(fs.readFileSync(path.join(f.directory, 'payload/file')), f.bytes);
}));

test('same-byte source inode replacement after clone outcome is rejected', () => fixture(f => {
  assert.throws(() => snapshot(f, {resolvePython: () => '/never/executed', clone: () => {
    fs.renameSync(f.source, path.join(f.sourceRoot, 'retired'));
    fs.writeFileSync(f.source, f.bytes, {mode: 0o640});
    return {status: 'unsupported', code: 'CLONE_SYNTHETIC'};
  }}), code('BACKUP_RACE'));
  assert.deepEqual(f.manifest.files, []);
}));

test('source mode/nlink and pinned destination directory races reject before stream', () => {
  for (const mutate of [f => fs.chmodSync(f.source, 0o600), f => fs.linkSync(f.source, path.join(f.sourceRoot, 'new-alias')), f => {
    fs.renameSync(path.join(f.directory, 'payload'), path.join(f.directory, 'retired'));
    fs.mkdirSync(path.join(f.directory, 'payload'), {mode: 0o700});
  }]) fixture(f => {
    assert.throws(() => snapshot(f, {resolvePython: () => '/never/executed', clone: () => {
      mutate(f); return {status: 'unsupported', code: 'CLONE_SYNTHETIC'};
    }, measure: () => {assert.fail('race reached stream admission');}}), code('BACKUP_RACE'));
    assert.deepEqual(f.manifest.files, []);
  });
});

test('capacity recheck cannot grant changed source bytes a write', () => fixture(f => {
  assert.throws(() => snapshot(f, {measure: () => {fs.appendFileSync(f.source, 'growth'); return enough();}}), code('BACKUP_RACE'));
  assert.equal(fs.existsSync(path.join(f.directory, 'payload/file')), false);
}));

test('concurrent source growth cannot stream more bytes than the admitted pinned size', () => fixture(f => {
  const read = fs.readSync;
  let grew = false;
  try {
    fs.readSync = (...args) => {
      const count = read(...args);
      if (!grew && count) {grew = true; fs.appendFileSync(f.source, 'growth beyond admitted size');}
      return count;
    };
    assert.throws(() => snapshot(f), code('BACKUP_RACE'));
  } finally {fs.readSync = read;}
  assert.equal(fs.statSync(path.join(f.directory, 'payload/file')).size, f.bytes.length);
  assert.deepEqual(f.manifest.files, []);
}));

test('capacity logging failure refuses a stream and preserves the original capacity failure', () => fixture(f => {
  assert.throws(() => admitFileStream({directory: f.directory, fileBytes: 1n, measure: enough, onEvent: () => {throw new Error('synthetic log failure');}}), code('BACKUP_CAPACITY_LOG_FAILED'));
  assert.throws(() => admitFileStream({directory: f.directory, fileBytes: 1n, measure: () => ({...enough(), availableBytes: 0n}), onEvent: () => {throw new Error('synthetic log failure');}}), error => error.code === 'BACKUP_CAPACITY_INSUFFICIENT' && error.loggingCode === 'BACKUP_CAPACITY_LOG_FAILED');
}));

test('existing payload and symlinked source are refused without changing sentinel', () => fixture(f => {
  fs.mkdirSync(path.join(f.directory, 'payload'), {mode: 0o700});
  const target = path.join(f.directory, 'payload/file'); fs.writeFileSync(target, 'sentinel');
  assert.throws(() => snapshot(f), code('BACKUP_TARGET_EXISTS')); assert.equal(fs.readFileSync(target, 'utf8'), 'sentinel');
  fs.unlinkSync(f.source); fs.symlinkSync(target, f.source);
  assert.throws(() => snapshot(f), code('BACKUP_RACE')); assert.equal(fs.readFileSync(target, 'utf8'), 'sentinel');
}));

test('static optional Python resolution accepts only trusted absolute existing paths', () => fixture(f => {
  assert.equal(resolveSnapshotPython(f.sourceRoot, {searchPath: 'relative/path'}), undefined);
  const bin = path.join(f.root, 'bin'); fs.mkdirSync(bin, {mode: 0o700});
  const candidate = path.join(bin, 'python3.12'); fs.writeFileSync(candidate, 'not executed', {mode: 0o755});
  assert.equal(resolveSnapshotPython(f.sourceRoot, {searchPath: bin}), fs.realpathSync(candidate));
  fs.chmodSync(candidate, 0o777); assert.equal(resolveSnapshotPython(f.sourceRoot, {searchPath: bin}), undefined);
  fs.chmodSync(candidate, 0o755); fs.chmodSync(bin, 0o775);
  assert.equal(resolveSnapshotPython(f.sourceRoot, {searchPath: bin}), undefined);
}));

test('verified clone result is recorded without entering stream admission', () => fixture(f => {
  snapshot(f, {resolvePython: () => '/never/executed', clone: ({destinationDirectory, destinationName, expectedSha256}) => {
    // Branch-only protocol test. The primitive owns real clone verification.
    fs.writeFileSync(path.join(destinationDirectory, destinationName), f.bytes, {mode: 0o600, flag: 'wx'});
    return {status: 'cloned', code: 'CLONE_VERIFIED', sha256: expectedSha256};
  }, measure: () => {assert.fail('verified clone reached stream admission');}});
  assert.deepEqual(f.manifest.files, [{path: 'payload/file', sha256: digest(f.bytes)}]);
}));

test('pure TCB reuse decision distinguishes exact operation/reference binding and before/after drift', () => {
  // Synthetic data only: this function cannot mint the private production map.
  const binding = {repositoryRoot: '/synthetic/repo', commonDirectory: '/synthetic/common', taskId: 'task', operationToken: Symbol('test-operation')};
  const reference = {lexicalPath: '/synthetic/python3.12', canonicalPath: '/synthetic/canonical-python', sha256: '0'.repeat(64), lexicalLink: '', dev: '1', ino: '2', uid: '501', gid: '20', mode: '33261', nlink: '1', size: '10', mtimeNs: '1', ctimeNs: '1', lexicalDev: '1', lexicalIno: '2', lexicalUid: '501', lexicalGid: '20', lexicalMode: '33261', lexicalNlink: '1', lexicalSize: '10', lexicalMtimeNs: '1', lexicalCtimeNs: '1'};
  const input = {expectedBinding: binding, observedBinding: {...binding}, expectedReference: reference, currentReference: {...reference}};
  assert.equal(toolchainReuseDecision(input), 'available');
  for (const observedBinding of [undefined, {...binding, taskId: 'other'}, {...binding, repositoryRoot: '/other'}, {...binding, commonDirectory: '/other'}, {...binding, operationToken: Symbol('other')}, {...binding, operationToken: undefined}]) {
    assert.equal(toolchainReuseDecision({...input, observedBinding}), 'unavailable');
    assert.equal(toolchainReuseDecision({...input, observedBinding, invoked: true}), 'unknown');
  }
  for (const key of Object.keys(reference)) {
    const currentReference = {...reference, [key]: reference[key] + 'changed'};
    assert.equal(toolchainReuseDecision({...input, currentReference}), 'unavailable');
    assert.equal(toolchainReuseDecision({...input, currentReference, invoked: true}), 'unknown');
  }
  assert.equal(toolchainReuseDecision({...input, currentReference: undefined}), 'unavailable');
  assert.equal(toolchainReuseDecision({...input, currentReference: undefined, invoked: true}), 'unknown');
});

test('no-follow lexical link replacement to the same launcher is reference drift', () => fixture(f => {
  const target = path.join(f.root, 'launcher'), link = path.join(f.root, 'selected-python');
  fs.writeFileSync(target, 'synthetic launcher facts only'); fs.symlinkSync('launcher', link);
  const before = selectedExecutableReference(link);
  assert.ok(before); assert.equal(before.lexicalLink, Buffer.from('launcher').toString('hex'));
  fs.renameSync(link, path.join(f.root, 'retired-link')); fs.symlinkSync('launcher', link);
  const after = selectedExecutableReference(link);
  assert.ok(after); assert.equal(after.canonicalPath, before.canonicalPath); assert.equal(after.sha256, before.sha256);
  assert.notEqual(after.lexicalIno, before.lexicalIno);
  const binding = {repositoryRoot: f.sourceRoot, commonDirectory: f.directory, taskId: 'task', operationToken: Symbol('pure-facts')};
  assert.equal(toolchainReuseDecision({expectedBinding: binding, observedBinding: binding, expectedReference: before, currentReference: after}), 'unavailable');
  assert.equal(toolchainReuseDecision({expectedBinding: binding, observedBinding: binding, expectedReference: before, currentReference: after, invoked: true}), 'unknown');
}));

test('standalone snapshot ignores forged caller toolchain records and uses admitted stream', () => fixture(f => {
  snapshot(f, {toolchainRecord: {trusted: true, pythonPath: '/never/executed'}, trusted: true, clone: () => {assert.fail('forged record reached helper');}});
  assert.deepEqual(fs.readFileSync(path.join(f.directory, 'payload/file')), f.bytes);
  assert.ok(f.events.some(event => event.code === 'CLONE_PYTHON_UNAVAILABLE'));
}));

test('actual standalone host with unavailable optional runtime uses measured target-FS stream', {skip: trustedHostPython ? 'host has a generic strict runtime instead' : false}, () => fixture(f => {
  snapshotRegularFile(f.sourceRoot, f.item, f.directory, 'payload/file', f.manifest, {onEvent: event => f.events.push(event)});
  assert.deepEqual(fs.readFileSync(path.join(f.directory, 'payload/file')), f.bytes);
  assert.ok(f.events.some(event => event.code === 'CLONE_PYTHON_UNAVAILABLE'));
  assert.ok(f.events.some(event => event.event === 'backup_capacity' && event.status === 'PASS' && event.device === String(fs.statSync(path.join(f.directory, 'payload'), {bigint: true}).dev)));
}));

test('small real Darwin clone preserves source independence through snapshot integration', {skip: process.platform !== 'darwin' ? 'Darwin evidence only' : !trustedHostPython ? 'NOT_RUN: existing Python parent chain fails optional runtime trust policy' : false}, () => fixture(f => {
  const pythonPath = resolveSnapshotPython(project);
  assert.ok(pythonPath);
  snapshot(f, {resolvePython: () => pythonPath});
  assert.deepEqual(fs.readFileSync(path.join(f.directory, 'payload/file')), f.bytes);
  assert.ok(f.events.some(x => x.event === 'backup_fd_clone' && x.status === 'cloned'), 'actual host clone was not confirmed');
  fs.writeFileSync(f.source, 'independent source write');
  assert.deepEqual(fs.readFileSync(path.join(f.directory, 'payload/file')), f.bytes);
}));
