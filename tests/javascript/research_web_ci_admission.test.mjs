import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import test from 'node:test';

test('Checks real Host and fresh Native admission reject optional environment pollution', () => {
  const workflow = fs.readFileSync(new URL('../../.github/workflows/research-web-checks.yml', import.meta.url), 'utf8');
  const code = workflow.match(/          \.venv\/bin\/python -B - <<'PY_ADMISSION'\n([\s\S]*?)          PY_ADMISSION/)[1].replace(/^          /gm, '');
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'rwb-ci-admission-'));
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
      const run = spawnSync(process.env.RWB_TEST_PYTHON || 'python3', ['-I', '-B', '-c', prefix + actual], {
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
