import {spawnSync} from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const helperRoot = path.dirname(fileURLToPath(import.meta.url));
const objectId = /^(?:[a-f0-9]{40}|[a-f0-9]{64})$/;
const fail = code => { throw Object.assign(new Error(code), {code}); };

// The scanner and its Git descendants share Darwin's no-materialization policy.
// The helper uses the existing backup FD checks rather than guessing ACLs from
// Git modes, and reports no filenames, file bytes or Git subprocess output.
const PROOF = String.raw`
import ctypes
import hashlib
import json
import os
import pathlib
import re
import stat
import subprocess
import sys
import tempfile
import time

project, target, commit, scratch_root, git, helpers, deployed = sys.argv[1:]
limit = time.monotonic() + 180
gib = 1024 ** 3
no_follow = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
env.update(GIT_NO_LAZY_FETCH='1', GIT_NO_REPLACE_OBJECTS='1', GIT_CONFIG_NOSYSTEM='1',
           GIT_CONFIG_GLOBAL=os.devnull, GIT_TERMINAL_PROMPT='0', GIT_PROTOCOL_FROM_USER='0')


class Refusal(Exception):
    pass


def require(condition, suffix):
    if not condition:
        raise Refusal('DEPLOYED_WORKTREE_' + suffix)


def command(root, *args, allowed=(0,), payload=None):
    supplied = {'input': payload} if payload is not None else {'stdin': subprocess.DEVNULL}
    result = subprocess.run([
        git, '--no-optional-locks', '-c', 'gc.auto=0', '-c', 'maintenance.auto=false',
        '-c', 'core.hooksPath=/dev/null', '-c', 'core.fsmonitor=false',
        '-c', 'core.untrackedCache=false', '-c', 'core.symlinks=true',
        '-c', 'protocol.file.allow=always', '-c', 'protocol.ext.allow=never',
        '-C', root, *args,
    ], env=env, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, **supplied,
        timeout=max(0.01, limit - time.monotonic()), check=False)
    require(result.returncode in allowed and len(result.stdout) <= 16 * 1024 ** 2, 'GIT_PROOF_FAILED')
    return result


def out(root, *args):
    return command(root, *args).stdout


def text(root, *args):
    return out(root, *args).decode('utf-8').rstrip('\n')


def real(path):
    require(os.path.isabs(path) and os.path.realpath(path) == path and os.path.isdir(path), 'IDENTITY_MISMATCH')
    return path


def git_common(root):
    require(text(root, 'rev-parse', '--show-toplevel') == root, 'IDENTITY_MISMATCH')
    return real(text(root, 'rev-parse', '--path-format=absolute', '--git-common-dir'))


def assert_object_source(root, common):
    objects = os.path.join(common, 'objects')
    require(real(objects) == objects, 'OBJECT_SOURCE_UNVERIFIABLE')
    for name in ('shallow', 'info/grafts', 'objects/info/alternates', 'objects/info/http-alternates'):
        require(not os.path.lexists(os.path.join(common, name)), 'OBJECT_SOURCE_UNVERIFIABLE')
    require(text(root, 'rev-parse', '--is-shallow-repository') == 'false', 'OBJECT_SOURCE_UNVERIFIABLE')
    require(command(root, 'config', '--get-regexp', r'^(extensions\.partialclone|remote\..*\.promisor)$',
                    allowed=(0, 1)).returncode == 1, 'OBJECT_SOURCE_UNVERIFIABLE')
    pack = os.path.join(objects, 'pack')
    if os.path.lexists(pack):
        require(real(pack) == pack and not any(name.endswith('.promisor') for name in os.listdir(pack)),
                'OBJECT_SOURCE_UNVERIFIABLE')


def read_index(root):
    sparse = command(root, 'config', '--bool', '--get-all', 'core.sparseCheckout', allowed=(0, 1)).stdout
    require(sparse in (b'', b'false\n'), 'INDEX_UNVERIFIABLE')
    raw = out(root, 'ls-files', '-v', '--stage', '--cached', '-z')
    tracked = {}
    for rec in raw.split(b'\x00')[:-1]:
        parts = rec.split(b'\t', 1)
        require(len(parts) == 2 and re.fullmatch(rb'H (100644|100755|120000) [a-f0-9]{40,64} 0', parts[0]),
                'INDEX_UNVERIFIABLE')
        name = parts[1].decode('utf-8')
        segments = name.split('/')
        require(name and all(x and x.lower() not in ('.', '..', '.git') for x in segments) and
                all(ord(x) >= 32 and ord(x) != 127 for x in name) and name not in tracked,
                'INDEX_UNVERIFIABLE')
        tracked[name] = parts[0].split()[1]
    require(len(tracked) <= 50000, 'INDEX_UNVERIFIABLE')
    require(command(root, 'diff', '--cached', '--quiet', '--no-ext-diff', '--no-textconv', 'HEAD', '--',
                    allowed=(0, 1)).returncode == 0, 'NOT_CLEAN')
    require(not out(root, 'ls-files', '--others', '-z'), 'NOT_CLEAN')
    return raw, tracked


def facts(s):
    return (s.st_dev, s.st_ino, s.st_mode, s.st_uid, s.st_gid, s.st_nlink, s.st_size,
            s.st_mtime_ns, s.st_ctime_ns, getattr(s, 'st_flags', 0))


def administrative_file(filename, maximum, check_metadata):
    fd = os.open(filename, no_follow)
    try:
        opened = os.fstat(fd)
        require(stat.S_ISREG(opened.st_mode) and opened.st_uid == os.getuid() and
                opened.st_nlink == 1 and opened.st_size <= maximum, 'ADMIN_UNVERIFIABLE')
        check_metadata(fd)
        with os.fdopen(os.dup(fd), 'rb') as stream:
            data = stream.read(maximum + 1)
        require(len(data) == opened.st_size and facts(opened) == facts(os.lstat(filename)), 'ADMIN_UNVERIFIABLE')
        return data
    finally:
        os.close(fd)


def git_line(value):
    require(value.endswith(b'\n') and value.count(b'\n') == 1 and b'\x00' not in value, 'ADMIN_UNVERIFIABLE')
    return value[:-1].decode('utf-8')


def assert_admin(root, common, check_metadata):
    admin = real(text(root, 'rev-parse', '--absolute-git-dir'))
    require(os.path.dirname(admin) == os.path.join(common, 'worktrees'), 'ADMIN_UNVERIFIABLE')
    before = os.lstat(admin)
    fd = os.open(admin, no_follow | os.O_DIRECTORY)
    try:
        require(facts(os.fstat(fd)) == facts(before) and before.st_uid == os.getuid(), 'ADMIN_UNVERIFIABLE')
        check_metadata(fd)
    finally:
        os.close(fd)
    sizes = {'HEAD': 4096, 'commondir': 4096, 'gitdir': 16384, 'index': 16 * 1024 ** 2, 'ORIG_HEAD': 1024}
    names = set(os.listdir(admin))
    require({'HEAD', 'commondir', 'gitdir', 'index'} <= names <= set(sizes) | {'logs', 'refs'}, 'ADMIN_UNVERIFIABLE')
    directory_facts = {}
    if 'refs' in names:
        # Newer Git's files backend initializes an empty worktree refs directory.
        # Any entry under it may be linked-worktree state and must be retained.
        refs = os.path.join(admin, 'refs')
        before_refs = os.lstat(refs)
        require(stat.S_ISDIR(before_refs.st_mode) and before_refs.st_uid == os.getuid() and
                before_refs.st_dev == before.st_dev, 'ADMIN_UNVERIFIABLE')
        f = os.open(refs, no_follow | os.O_DIRECTORY)
        try:
            require(facts(os.fstat(f)) == facts(before_refs), 'FILESYSTEM_CHANGED')
            check_metadata(f)
            require(not os.listdir(f), 'ADMIN_UNVERIFIABLE')
            directory_facts['refs'] = facts(before_refs)
        finally:
            os.close(f)
    data = {name: administrative_file(os.path.join(admin, name), sizes[name], check_metadata)
            for name in names if name in sizes}
    pointer = administrative_file(os.path.join(root, '.git'), 16384, check_metadata)
    require(git_line(pointer) == 'gitdir: ' + admin and git_line(data['gitdir']) == os.path.join(root, '.git') and
            os.path.realpath(os.path.join(admin, git_line(data['commondir']))) == common, 'ADMIN_UNVERIFIABLE')
    head = git_line(data['HEAD'])
    require(head == commit or head.startswith('ref: refs/heads/') and head == 'ref: ' +
            text(root, 'symbolic-ref', 'HEAD'), 'ADMIN_UNVERIFIABLE')
    all_commits = {commit}
    oid = rb'[a-f0-9]{' + str(len(commit)).encode() + rb'}'
    if 'ORIG_HEAD' in data:
        orig = git_line(data['ORIG_HEAD']).encode('ascii')
        require(re.fullmatch(oid, orig), 'ADMIN_UNVERIFIABLE')
        all_commits.add(orig.decode('ascii'))
    if 'logs' in names:
        logs = os.path.join(admin, 'logs')
        f = os.open(logs, no_follow | os.O_DIRECTORY)
        try:
            before_logs = os.fstat(f)
            require(before_logs.st_uid == os.getuid(), 'ADMIN_UNVERIFIABLE')
            check_metadata(f)
            require(os.listdir(f) == ['HEAD'], 'ADMIN_UNVERIFIABLE')
            journal = administrative_file(os.path.join(logs, 'HEAD'), 2 * 1024 ** 2, check_metadata)
            require(facts(os.lstat(logs)) == facts(before_logs), 'FILESYSTEM_CHANGED')
        finally:
            os.close(f)
        lines = journal.split(b'\n')
        require(lines.pop() == b'' and len(lines) <= 5000, 'ADMIN_UNVERIFIABLE')
        row = re.compile(rb'^(' + oid + rb') (' + oid + rb') [^\x00\t]+(?:\t[^\x00]*)?$')
        for line in lines:
            match = row.fullmatch(line)
            require(match, 'ADMIN_UNVERIFIABLE')
            all_commits.update(part.decode('ascii') for part in match.groups() if part != b'0' * len(commit))
        data['logs/HEAD'] = journal
    data['.git'] = pointer
    require(facts(os.lstat(admin)) == facts(before), 'FILESYSTEM_CHANGED')
    # An exact one-pass rev walk refuses even a detached HEAD that a later
    # checkout hid from git status. No replacement or shallow boundary is allowed.
    commits = sorted(all_commits)
    refs_payload = ('\n'.join(commits) + '\n').encode('ascii')
    types = command(root, 'cat-file', '--batch-check=%(objectname) %(objecttype)', payload=refs_payload).stdout
    require(types == (''.join(oid + ' commit\n' for oid in commits)).encode('ascii'), 'ADMIN_UNVERIFIABLE')
    walk = command(root, 'rev-list', '--max-count=1', '--stdin',
                   payload=refs_payload + ('^' + deployed + '\n').encode('ascii')).stdout
    require(not walk, 'ADMIN_UNVERIFIABLE')
    if 'refs' in directory_facts:
        require(facts(os.lstat(refs)) == directory_facts['refs'], 'FILESYSTEM_CHANGED')
    return [facts(before), {**directory_facts,
                            **{name: hashlib.sha256(data[name]).hexdigest() for name in sorted(data)}}]


def metadata_checker():
    if sys.platform == 'darwin':
        guard = ctypes.CDLL('/usr/lib/libSystem.B.dylib', use_errno=True)
        guard.setiopolicy_np.argtypes = [ctypes.c_int] * 3
        guard.getiopolicy_np.argtypes = [ctypes.c_int] * 2
        require(guard.setiopolicy_np(3, 0, 1) == 0 and guard.getiopolicy_np(3, 0) == 1,
                'METADATA_UNVERIFIABLE')
        # The controller binds this exact source file to the deployed Git blob.
        # Compile its pinned regular-file bytes without extending sys.path or
        # reading a cached .pyc, native module, or same-name package.
        filename = os.path.join(real(helpers), 'backup_fd_clone.py')
        fd = os.open(filename, no_follow)
        try:
            opened = os.fstat(fd)
            require(stat.S_ISREG(opened.st_mode) and opened.st_uid == os.getuid() and
                    opened.st_nlink == 1 and not opened.st_mode & 0o022 and
                    0 < opened.st_size <= 128 * 1024, 'METADATA_UNVERIFIABLE')
            with os.fdopen(os.dup(fd), 'rb') as stream:
                source = stream.read(opened.st_size + 1)
            require(len(source) == opened.st_size and facts(os.lstat(filename)) == facts(opened),
                    'METADATA_UNVERIFIABLE')
        finally:
            os.close(fd)
        helper = {'__name__': 'rwb_proof_backup_fd_clone', '__file__': filename}
        exec(compile(source, filename, 'exec'), helper)
        library = helper['system_library']()
        require_plain_metadata = helper['require_plain_metadata']
        CloneRefusal = helper['Refusal']

        def check(fd):
            try:
                require_plain_metadata(library, fd)
            except CloneRefusal as error:
                raise Refusal('DEPLOYED_WORKTREE_METADATA_UNVERIFIABLE') from error

        return check
    require(sys.platform == 'linux' and hasattr(os, 'listxattr'), 'METADATA_UNVERIFIABLE')
    return lambda fd: require(not os.listxattr(fd), 'METADATA_UNVERIFIABLE')


def scan(root, tracked, check_metadata):
    allowed_dirs = {''}
    for name in tracked:
        allowed_dirs.update(str(p) for p in pathlib.PurePosixPath(name).parents if str(p) != '.')
    rows, seen, identities = {}, set(), {}
    byte_count = 0

    def directory(fd, prefix, device):
        nonlocal byte_count
        before = os.fstat(fd)
        require(before.st_dev == device and before.st_uid == os.getuid(), 'METADATA_UNVERIFIABLE')
        check_metadata(fd)
        rows[prefix] = ('d', stat.S_IMODE(before.st_mode), before.st_uid, before.st_gid)
        for name in os.listdir(fd):
            item = name if not prefix else prefix + '/' + name
            source = os.stat(name, dir_fd=fd, follow_symlinks=False)
            require(source.st_dev == device and source.st_uid == os.getuid() and not getattr(source, 'st_flags', 0),
                    'METADATA_UNVERIFIABLE')
            if item == '.git':
                require(stat.S_ISREG(source.st_mode) and source.st_nlink == 1, 'IDENTITY_MISMATCH')
                identities[item] = facts(source)
                continue
            if item in allowed_dirs:
                require(stat.S_ISDIR(source.st_mode), 'METADATA_UNVERIFIABLE')
                opened = os.open(name, no_follow | os.O_DIRECTORY, dir_fd=fd)
                try:
                    require(facts(os.fstat(opened)) == facts(source), 'FILESYSTEM_CHANGED')
                    directory(opened, item, device)
                finally:
                    os.close(opened)
            else:
                require(item in tracked and source.st_nlink == 1, 'METADATA_UNVERIFIABLE')
                seen.add(item)
                link = tracked[item] == b'120000'
                require(stat.S_ISLNK(source.st_mode) if link else stat.S_ISREG(source.st_mode), 'METADATA_UNVERIFIABLE')
                if link and sys.platform == 'linux':
                    require(not os.listxattr('/proc/self/fd/' + str(fd) + '/' + name, follow_symlinks=False),
                            'METADATA_UNVERIFIABLE')
                    content = hashlib.sha256(os.fsencode(os.readlink(name, dir_fd=fd))).hexdigest()
                else:
                    flags = os.O_RDONLY | os.O_SYMLINK if link else no_follow
                    opened = os.open(name, flags, dir_fd=fd)
                    try:
                        require(facts(os.fstat(opened)) == facts(source), 'FILESYSTEM_CHANGED')
                        check_metadata(opened)
                        if link:
                            content = hashlib.sha256(os.fsencode(os.readlink(name, dir_fd=fd))).hexdigest()
                        else:
                            current = hashlib.sha256()
                            count = 0
                            while True:
                                step = os.read(opened, 1024 * 1024)
                                if not step:
                                    break
                                count += len(step)
                                require(count <= source.st_size and time.monotonic() < limit, 'FILESYSTEM_CHANGED')
                                current.update(step)
                            require(count == source.st_size, 'FILESYSTEM_CHANGED')
                            content = current.hexdigest()
                        require(facts(os.fstat(opened)) == facts(source), 'FILESYSTEM_CHANGED')
                    finally:
                        os.close(opened)
                rows[item] = ('l' if link else 'f', stat.S_IMODE(source.st_mode), source.st_uid, source.st_gid, content)
                byte_count += source.st_size
            require(facts(os.stat(name, dir_fd=fd, follow_symlinks=False)) == facts(source), 'FILESYSTEM_CHANGED')
            identities[item] = facts(source)
        require(facts(os.fstat(fd)) == facts(before), 'FILESYSTEM_CHANGED')

    fd = os.open(root, no_follow | os.O_DIRECTORY)
    try:
        root_stat = os.fstat(fd)
        directory(fd, '', root_stat.st_dev)
        require(facts(os.lstat(root)) == facts(root_stat), 'FILESYSTEM_CHANGED')
        identities[''] = facts(root_stat)
    finally:
        os.close(fd)
    require(seen == set(tracked) and '.git' in identities, 'METADATA_UNVERIFIABLE')
    return rows, identities, byte_count


def admit(common, tracked_bytes):
    values = dict(line.split(': ', 1) for line in text(common, 'count-objects', '-v').splitlines() if ': ' in line)
    estimate = (int(values['size']) + int(values['size-pack'])) * 1024 + tracked_bytes + 128 * 1024 ** 2
    disk = os.statvfs(scratch_root)
    require(disk.f_bavail * disk.f_frsize >= estimate + 3 * gib and estimate <= 4 * gib, 'PROOF_CAPACITY_INSUFFICIENT')


def proof():
    check_metadata = metadata_checker()
    for p in (project, target, scratch_root):
        real(p)
    require(project != target and all(os.path.commonpath((s, scratch_root)) != s for s in (project, target)),
            'IDENTITY_MISMATCH')
    common = git_common(project)
    require(git_common(target) == common and text(target, 'rev-parse', 'HEAD') == commit, 'IDENTITY_MISMATCH')
    assert_object_source(project, common)
    index, tracked = read_index(target)
    admin = assert_admin(target, common, check_metadata)
    live = scan(target, tracked, check_metadata)
    admit(project, live[2])
    with tempfile.TemporaryDirectory(dir=scratch_root, prefix='rwb-git-proof-') as scratch:
        bare = os.path.join(scratch, 'repo.git')
        restored = os.path.join(scratch, 'checkout')
        algorithm = 'sha1' if len(commit) == 40 else 'sha256'
        out(scratch, 'init', '--bare', '--template=', '--object-format=' + algorithm, bare)
        out(bare, 'fetch', '--no-tags', '--no-write-fetch-head', '--no-recurse-submodules', '--no-auto-gc',
            pathlib.Path(project).as_uri(), deployed + ':refs/heads/proof')
        assert_object_source(bare, bare)
        require(text(bare, 'rev-parse', 'refs/heads/proof') == deployed, 'GIT_PROOF_FAILED')
        out(bare, 'fsck', '--full', '--no-reflogs', deployed)
        out(bare, 'worktree', 'add', '--detach', restored, commit)
        rebuilt_index, rebuilt_paths = read_index(restored)
        require(rebuilt_index == index and rebuilt_paths == tracked, 'INDEX_UNVERIFIABLE')
        rebuilt = scan(restored, tracked, check_metadata)[0]
        require(rebuilt.keys() == live[0].keys(), 'METADATA_UNVERIFIABLE')
        for name, value in live[0].items():
            require(value[:4] == rebuilt[name][:4], 'METADATA_UNVERIFIABLE')
            require(value == rebuilt[name], 'NOT_CLEAN')
        require(scan(target, tracked, check_metadata) == live and read_index(target)[0] == index and
                assert_admin(target, common, check_metadata) == admin and
                git_common(target) == common and text(target, 'rev-parse', 'HEAD') == commit, 'FILESYSTEM_CHANGED')
    return {'commit': commit, 'indexSha256': hashlib.sha256(index).hexdigest(), 'trackedFiles': len(tracked),
            'adminSha256': hashlib.sha256(json.dumps(admin, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
            'treeSha256': hashlib.sha256(json.dumps(live[0], sort_keys=True, separators=(',', ':')).encode()).hexdigest()}


try:
    print(json.dumps(proof()))
except Refusal as exc:
    print(json.dumps({'code': str(exc)}))
    sys.exit(1)
except subprocess.TimeoutExpired:
    print(json.dumps({'code': 'DEPLOYED_WORKTREE_PROOF_TIMEOUT'}))
    sys.exit(1)
except (OSError, ValueError, UnicodeError, KeyError, ImportError):
    print(json.dumps({'code': 'DEPLOYED_WORKTREE_METADATA_UNVERIFIABLE'}))
    sys.exit(1)
`;

/** Prove that the exact live checkout is fully reconstructible by independent Git objects. */
export function proveDeployedWorktree({projectRoot, worktree, commit, deployedCommit}, options = {}) {
  const {gitPath = '/usr/bin/git', scratchRoot = fs.realpathSync(os.tmpdir())} = options;
  const defaultPython = process.platform === 'darwin' ? '/opt/homebrew/bin/python3.12' : '/usr/bin/python3';
  const pythonPath = options.pythonPath ?? defaultPython;
  if (![projectRoot, worktree, gitPath, scratchRoot, pythonPath].every(v => typeof v === 'string' && path.isAbsolute(v)) ||
      typeof commit !== 'string' || !objectId.test(commit) || typeof deployedCommit !== 'string' ||
      !objectId.test(deployedCommit) || deployedCommit.length !== commit.length) fail('DEPLOYED_WORKTREE_IDENTITY_MISMATCH');
  let scratch;
  try {
    if (fs.realpathSync(scratchRoot) !== scratchRoot || [projectRoot, worktree].some(root =>
      scratchRoot === root || scratchRoot.startsWith(root + path.sep))) fail('DEPLOYED_WORKTREE_SCRATCH_UNAVAILABLE');
    scratch = fs.mkdtempSync(path.join(scratchRoot, 'rwb-git-proof-'));
  } catch { fail('DEPLOYED_WORKTREE_SCRATCH_UNAVAILABLE'); }
  const pin = fs.lstatSync(scratch, {bigint: true});
  let result;
  try {
    result = spawnSync(pythonPath, ['-I', '-S', '-B', '-c', PROOF, projectRoot, worktree,
      commit, scratch, gitPath, helperRoot, deployedCommit], {encoding: 'utf8', timeout: 190_000, maxBuffer: 4096});
  } finally {
    const live = fs.lstatSync(scratch, {bigint: true, throwIfNoEntry: false});
    if (!live?.isDirectory() || live.dev !== pin.dev || live.ino !== pin.ino || live.uid !== pin.uid ||
        fs.realpathSync(scratch) !== scratch) fail('DEPLOYED_WORKTREE_SCRATCH_IDENTITY_CHANGED');
    fs.rmSync(scratch, {recursive: true});
  }
  let parsed;
  try { parsed = JSON.parse(result.stdout ?? ''); } catch { /* refuse incomplete proof */ }
  if (result.status !== 0) fail(/^DEPLOYED_WORKTREE_[A-Z_]+$/.test(parsed?.code ?? '')
    ? parsed.code : 'DEPLOYED_WORKTREE_PROOF_FAILED');
  const hash = /^[a-f0-9]{64}$/;
  if (parsed?.commit !== commit || !hash.test(parsed.indexSha256 ?? '') || !hash.test(parsed.treeSha256 ?? '') ||
      !hash.test(parsed.adminSha256 ?? '') ||
      !Number.isSafeInteger(parsed.trackedFiles) || parsed.trackedFiles < 0) fail('DEPLOYED_WORKTREE_PROOF_FAILED');
  return parsed;
}
