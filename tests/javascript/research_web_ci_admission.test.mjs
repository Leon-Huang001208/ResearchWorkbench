import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import test from 'node:test';

test('standard wheel builds offline without editable extras and owns pack resources', () => {
  const root = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), 'rwb-ci-standard-wheel-')));
  const project = fileURLToPath(new URL('../../', import.meta.url));
  const python = process.env.RWB_TEST_PYTHON || 'python3';
  const env = {...process.env, PIP_NO_INDEX: '1', PIP_DISABLE_PIP_VERSION_CHECK: '1', PIP_NO_CACHE_DIR: '1', PIP_CONFIG_FILE: process.platform === 'win32' ? 'NUL' : '/dev/null', PYTHONDONTWRITEBYTECODE: '1'};
  try {
    const build = spawnSync(python, ['-B', '-m', 'pip', 'wheel', '--no-index', '--no-deps', '--no-build-isolation', '--wheel-dir', root, project], {
      cwd: root, env, encoding: 'utf8', timeout: 60000,
    });
    assert.ifError(build.error);
    assert.equal(build.status, 0, build.stdout + build.stderr);
    const wheels = fs.readdirSync(root).filter(name => name.endsWith('.whl'));
    assert.equal(wheels.length, 1);
    const code = `import importlib.metadata as metadata,json,sys,zipfile
from pathlib import Path
wheel=Path(sys.argv[1]); installed=Path(sys.argv[2])
assert 'app' not in sys.modules
dist=next(metadata.distributions(path=[str(wheel)]))
assert dist.metadata['Name']=='research-workbench'
assert any(e.name=='rwb' and e.value=='research_workbench_entrypoint:main' for e in dist.entry_points)
assert not any(r.startswith('editables') for r in dist.requires)
with zipfile.ZipFile(wheel) as archive:
 assert not any(name.endswith('.pth') or 'editable' in name.lower() for name in archive.namelist())
 archive.extractall(installed)
assert not (installed/'requirements/web.lock').exists()
sys.path.insert(0,str(installed))
from app.research_web.capabilities.pack_dependencies import runtime_identity,LOCK_PROJECTION
from app.research_web.capabilities.pack_resources import pack_packages,verify_pack_manifest
from app.research_web.capabilities.scenario_method_packages import scenario_method_packages
from app.research_web.runtime_contract import DEFAULT_CONTRACT_PATH,load_runtime_contract
runtime=runtime_identity(); packs=list(pack_packages()); methods=list(scenario_method_packages())
assert len(packs)==9 and len(methods)==3 and len(runtime['dependencies'])==7
assert all(verify_pack_manifest(pack['files']) for _,pack in packs)
assert LOCK_PROJECTION.is_relative_to(installed) and DEFAULT_CONTRACT_PATH.is_relative_to(installed)
assert load_runtime_contract().dsh_commit
for name,module in list(sys.modules.items()):
 if name.split('.')[0] in {'app','core','runtimes'}:
  assert Path(module.__file__).is_relative_to(installed), name
print(json.dumps({'wheel_only_resources':True,'packs':len(packs),'methods':len(methods),'installed_by_this_test':False}))
`;
    const inspect = spawnSync(python, ['-I', '-B', '-c', code, path.join(root, wheels[0]), path.join(root, 'wheel-only')], {
      cwd: root, env, encoding: 'utf8', timeout: 30000,
    });
    assert.ifError(inspect.error);
    assert.equal(inspect.status, 0, inspect.stdout + inspect.stderr);
    assert.deepEqual(JSON.parse(inspect.stdout.trim().split('\n').at(-1)), {wheel_only_resources: true, packs: 9, methods: 3, installed_by_this_test: false});
  } finally {
    fs.rmSync(root, {recursive: true});
  }
});

test('Checks real Host and fresh Native admission reject optional environment pollution', () => {
  const workflow = fs.readFileSync(new URL('../../.github/workflows/research-web-checks.yml', import.meta.url), 'utf8');
  const admission = workflow.match(/          \.venv\/bin\/python (-I -B) - <<'PY_ADMISSION'\n([\s\S]*?)          PY_ADMISSION/);
  assert.ok(admission, 'installed-package admission must ignore cwd and PYTHONPATH');
  const flags = admission[1].split(' ');
  const code = admission[2].replace(/^          /gm, '');
  const root = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), 'rwb-ci-admission-')));
  const project = fileURLToPath(new URL('../../', import.meta.url));
  try {
    fs.mkdirSync(path.join(root, 'logs'));
    const shadow = path.join(root, 'synthetic-optional');
    fs.mkdirSync(shadow);
    fs.writeFileSync(path.join(shadow, 'jsonpointer.py'), 'class JsonPointerException(Exception): pass\nclass JsonPointer:\n def __init__(self, value): self.value=value\n');
    for (const variant of ['clean', 'host-polluted', 'native-polluted']) {
      let actual = code;
      if (variant === 'native-polluted') actual = actual.replace('    result = subprocess.run(', `    code = code.replace("helper.install_native(", ${JSON.stringify('sys.path.insert(0,' + JSON.stringify(shadow) + ')\nhelper.install_native(')})\n    result = subprocess.run(`);
      const prefix = `import sys\nsys.path.insert(0,${JSON.stringify(project)})\n` +
        (variant === 'host-polluted' ? `sys.path.insert(0,${JSON.stringify(shadow)})\n` : '');
      const run = spawnSync(process.env.RWB_TEST_PYTHON || 'python3', [...flags, '-c', prefix + actual], {
        cwd: root, env: {...process.env, PYTHONDONTWRITEBYTECODE: '1'}, encoding: 'utf8', timeout: 40000,
      });
      assert.ifError(run.error);
      assert.equal(run.status, variant === 'clean' ? 0 : 1, variant + ': ' + run.stderr);
      if (variant === 'host-polluted') assert.match(run.stderr, /unbound referenced dependency module/);
      if (variant === 'native-polluted') assert.match(run.stderr, /CalledProcessError/);
    }
    const log = fs.readFileSync(path.join(root, 'logs/ci-pack-dependencies.log'), 'utf8');
    assert.match(log, /ci_pack_host_native_admission_passed/);
    assert.match(log, /ci_pack_host_native_admission_failed/);
    assert.match(log, /unbound optional dependency available/);
  } finally {
    fs.rmSync(root, {recursive: true});
  }
});
