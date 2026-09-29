import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const root = new URL('../../', import.meta.url);
const read = (name) => readFileSync(new URL(name, root), 'utf8');
const contract = JSON.parse(read('runtimes/research_web.json'));
const documentNames = ['index', 'api-atlas', '01-deployment', '02-module-dependencies', '03-research-sequence', '04-data-file-flow', '05-capability-flow', '06-run-state', '07-delivery-state', '08-iteration-docs', '09-report-workflow-sequence', '10-excel-report-dataflow'];
const instructions = () => read('Dockerfile').replace(/\\\n\s*/g, ' ').split('\n').filter((line) => /^[A-Z]+ /.test(line));

test('image bases and stage boundaries match the shared runtime contract', () => {
  const lines = instructions();
  assert.match(read('Dockerfile'), /^# syntax=docker\/dockerfile:1\n/);
  assert.ok(lines.includes(`ARG NODE_IMAGE=${contract.node.docker_image}`));
  assert.ok(lines.includes(`ARG PYTHON_IMAGE=${contract.python.docker_image}`));
  assert.deepEqual(lines.filter((line) => line.startsWith('FROM ')), [
    'FROM ${NODE_IMAGE} AS node-runtime', 'FROM ${PYTHON_IMAGE} AS python-builder',
    'FROM python-builder AS dsh-builder', 'FROM ${PYTHON_IMAGE} AS runtime',
  ]);
});

test('builders reuse the hashed Web lock, vendored CJPY and pinned DSH verifier', () => {
  const file = read('Dockerfile');
  assert.match(file, /--require-hashes[^\n]*requirements\/web\.lock/);
  assert.match(file, /--no-build-isolation --no-deps \./);
  assert.match(file, /verify_cjpy_bundle\(\)/);
  assert.match(file, /--no-index --no-deps vendor\/cjpy\/0\.5\.2\/cjpy-0\.5\.2-py3-none-any\.whl/);
  assert.match(file, new RegExp(`corepack pnpm@${contract.dsh.pnpm.replaceAll('.', '\\.')} install --frozen-lockfile`));
  assert.match(file, /DSH_REMOTE, DSH_COMMIT/);
  assert.match(file, /RUN python docker\/stage_dsh\.py/);
  assert.match(read('docker/stage_dsh.py'), /verified = installer\.verify_dsh_source\(source\)[\s\S]*stage_assets\(source, Path\("\/opt\/rwb\/dsh-runtime"\), verified\)/);
  assert.doesNotMatch(file, /requirements\/docker|git clone .*main|git clone .*master/);
});

test('runtime copies a bounded application set and uses the non-root PID1 supervisor', () => {
  const lines = instructions();
  const runtime = lines.slice(lines.indexOf('FROM ${PYTHON_IMAGE} AS runtime') + 1);
  assert.ok(runtime.includes('USER rwb'));
  assert.ok(runtime.some((line) => line.includes('useradd --uid 10001')));
  assert.ok(runtime.includes('ENTRYPOINT ["/opt/rwb/docker/entrypoint.sh"]'));
  assert.ok(runtime.includes('EXPOSE 8088'));
  assert.ok(runtime.some((line) => line.startsWith('HEALTHCHECK ') && line.endsWith('["/opt/rwb/venv/bin/python", "/opt/rwb/docker/healthcheck.py"]')));
  const environment = runtime.find((line) => line.startsWith('ENV '));
  assert.deepEqual([...environment.matchAll(/\bRWB_DSH_STAGED=(\S+)/g)].map((match) => match[1]), ['1']);
  for (const field of ['LOG_DIR=/state/logs', 'OBJECT_STORAGE_PATH=/data/research-web/objects', 'PDF_MARKDOWN_DIR=/data/research-web/markdown', 'PDF_RAW_TEXT_DIR=/data/research-web/raw_text', 'RESEARCH_RUN_MODE=web-prod']) {
    assert.ok(environment.includes(field), `import-time settings must stay writable: ${field}`);
  }
  assert.deepEqual(runtime.filter((line) => line.startsWith('COPY ')).map((line) => line.split(/\s+/).slice(-2, -1)[0]), [
    '/usr/local/bin/node', '/usr/local/lib/node_modules/npm', '/usr/local/lib/node_modules/corepack', '/opt/rwb/venv',
    '/opt/rwb/app', '/opt/rwb/core', '/opt/rwb/data_layer', '/opt/rwb/research_workbench_entrypoint',
    '/opt/rwb/runtimes', '/opt/rwb/vendor/dsh-tabbit', '/opt/rwb/docker/entrypoint.sh',
    '/opt/rwb/docker/supervisor.py', '/opt/rwb/docker/healthcheck.py', '/opt/rwb/pyproject.toml',
    'outputs/research-web-architecture', '/opt/rwb/dsh-runtime',
  ]);
  assert.doesNotMatch(read('Dockerfile'), /^COPY \.\s|^(ARG|ENV) .*?(?:KEY|TOKEN|PASSWORD)=/m);
  assert.match(read('docker/entrypoint.sh'), /exec \/opt\/rwb\/venv\/bin\/python \/opt\/rwb\/docker\/supervisor\.py/);
  assert.match(read('docker/supervisor.py'), /web_host="0\.0\.0\.0"/);
  assert.ok(runtime.some((line) => line.includes('npm/bin/npm-cli.js /usr/local/bin/npm') && line.includes('npm/bin/npx-cli.js /usr/local/bin/npx')), 'MCP package resolution retains Node npm/npx');
});

test('Compose has one isolated service with exactly one loopback Web publication', () => {
  // JSON is a strict, unambiguous YAML 1.2 subset: parse the complete committed document.
  const compose = JSON.parse(read('compose.yaml'));
  assert.deepEqual(Object.keys(compose), ['services']);
  assert.deepEqual(Object.keys(compose.services), ['research-web']);
  const service = compose.services['research-web'];
  assert.deepEqual(service.ports, ['127.0.0.1:${RWB_WEB_PORT:-8088}:8088']);
  assert.equal(service.init, false);
  assert.equal(service.read_only, true);
  assert.equal(service.user, '10001:10001');
  assert.deepEqual(service.cap_drop, ['ALL']);
  assert.deepEqual(service.security_opt, ['no-new-privileges:true']);
  assert.equal(service.network_mode, undefined);
  assert.equal(service.privileged, undefined);
  assert.equal(service.command, undefined);
  assert.equal(service.entrypoint, undefined);
  assert.equal(service.healthcheck, undefined);
});

test('Compose requires explicit canonical mounts and includes only non-secret configuration', () => {
  const service = JSON.parse(read('compose.yaml')).services['research-web'];
  assert.deepEqual(service.volumes, [
    { type: 'bind', source: '${RWB_DATA_DIR:?Set RWB_DATA_DIR}', target: '/data/research-web', bind: { create_host_path: false } },
    { type: 'bind', source: '${RWB_STATE_DIR:?Set RWB_STATE_DIR}', target: '/state', bind: { create_host_path: false } },
    { type: 'bind', source: '${RWB_CREDENTIAL_DIR:?Set RWB_CREDENTIAL_DIR}', target: '/run/rwb-secrets', bind: { create_host_path: false } },
  ]);
  assert.deepEqual(service.environment, { RWB_DATA_ROOT: '/data/research-web', RWB_RUNTIME_STATE: '/state', LOG_DIR: '/state/logs' });
  assert.deepEqual(service.labels, {
    'io.research-workbench.runtime': 'docker',
    'io.research-workbench.installation': '${RWB_INSTALLATION_ID:?Set RWB_INSTALLATION_ID}',
  });
  assert.deepEqual(service.tmpfs, ['/tmp:rw,nosuid,nodev,mode=1777', '/home/rwb:rw,nosuid,nodev,uid=10001,gid=10001,mode=700']);
});

test('build context denies local state and allows only runtime packaging inputs', () => {
  const patterns = read('.dockerignore').split('\n').map((line) => line.trim()).filter((line) => line && !line.startsWith('#'));
  assert.equal(patterns[0], '**');
  const allowed = patterns.filter((line) => line.startsWith('!'));
  assert.deepEqual(allowed, [
    '!Dockerfile', '!pyproject.toml', '!app/', '!app/__init__.py', '!app/research_web/', '!app/research_web/**',
    '!app/cli/', '!app/cli/**', '!core/', '!core/__init__.py', '!core/settings/', '!core/settings/**',
    '!core/observability/', '!core/observability/**',
    '!data_layer/', '!data_layer/__init__.py', '!data_layer/adapters/', '!data_layer/adapters/__init__.py',
    '!data_layer/adapters/ifind/', '!data_layer/adapters/ifind/__init__.py', '!data_layer/adapters/ifind/exceptions.py', '!data_layer/adapters/ifind/http_client.py',
    '!research_workbench_entrypoint/', '!research_workbench_entrypoint/**',
    '!runtimes/', '!runtimes/__init__.py', '!runtimes/research_web.json', '!requirements/', '!requirements/web.lock',
    '!vendor/', '!vendor/cjpy/', '!vendor/cjpy/**', '!vendor/dsh-tabbit/', '!vendor/dsh-tabbit/**',
    '!scripts/', '!scripts/setup_web.py', '!docker/', '!docker/**',
    '!outputs/', '!outputs/research-web-architecture/',
    ...documentNames.map((name) => `!outputs/research-web-architecture/${name}.html`),
  ]);
  for (const pattern of ['**/.git', '**/.worktrees', '**/.venv*', '**/logs', '**/.ai', '**/.ai/reports', '**/__pycache__', '**/.cache', '**/.env*', '**/credentials', '**/secrets', '**/.research-workbench', '**/.runtime', '**/data', '**/auth.json', '**/.ssh', '**/.aws', '**/*.pem', '**/*.key', '**/node_modules', '**/*.pyc', '**/.DS_Store']) {
    assert.ok(patterns.lastIndexOf(pattern) > patterns.lastIndexOf(allowed.at(-1)), `deny ${pattern} after allowlist`);
  }
});

test('the final filesystem is import-smoked as non-root and requires staged integrity', () => {
  const runtime = read('Dockerfile').split('FROM ${PYTHON_IMAGE} AS runtime')[1];
  assert.match(runtime, /RWB_DSH_STAGED=1/);
  assert.match(runtime, /USER rwb\nRUN python -I - <<'PY'/);
  assert.match(runtime, /app\.research_web\.main/);
  assert.match(runtime, /data_layer\.adapters\.ifind\.http_client/);
  assert.match(runtime, /docker_final_image_import_smoke_passed/);
  assert.doesNotMatch(runtime, /COPY[^\n]*\/opt\/rwb\/dsh \/opt\/dsh/);
});
