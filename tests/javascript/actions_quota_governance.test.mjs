import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';

const readWorkflow = (name) => fs.readFileSync(
  new URL(`../../.github/workflows/${name}`, import.meta.url),
  'utf8',
);

const workflows = {
  bootstrap: readWorkflow('research-web-bootstrap.yml'),
  checks: readWorkflow('research-web-checks.yml'),
  constraints: readWorkflow('project-constraints.yml'),
  desktop: readWorkflow('desktop-verify.yml'),
  tabbit: readWorkflow('research-web-tabbit.yml'),
  windows: readWorkflow('research-web-windows-verify.yml'),
};
const verificationPolicy = JSON.parse(fs.readFileSync(
  new URL('../../.agents/verification-policy.json', import.meta.url),
  'utf8',
));

function workflowTriggers(source) {
  const lines = source.split(/\r?\n/);
  const start = lines.findIndex((line) => line === 'on:');
  assert.notEqual(start, -1, 'workflow must declare an on block');
  const triggers = [];
  for (const line of lines.slice(start + 1)) {
    if (/^\S/.test(line)) break;
    const match = line.match(/^  ([a-z_]+):\s*$/);
    if (match) triggers.push(match[1]);
  }
  return triggers;
}

function workflowJobs(source) {
  const lines = source.split(/\r?\n/);
  const start = lines.findIndex((line) => line === 'jobs:');
  assert.notEqual(start, -1, 'workflow must declare jobs');
  const jobs = [];
  for (let index = start + 1; index < lines.length;) {
    if (/^\S/.test(lines[index])) break;
    const line = lines[index];
    if (!/^  \S/.test(line)) {
      index += 1;
      continue;
    }
    const value = line.slice(2);
    if (value.startsWith('#') || value.startsWith('- ')) {
      index += 1;
      continue;
    }
    const quoted = value.match(/^(?:"((?:[^"\\]|\\.)*)"|'((?:[^']|'')*)')\s*:/);
    const separator = value.indexOf(':');
    if (!quoted && separator <= 0) {
      index += 1;
      continue;
    }
    const id = quoted
      ? (quoted[1] ?? quoted[2].replaceAll("''", "'"))
      : value.slice(0, separator).trim();
    let runsOn = null;
    index += 1;
    while (index < lines.length && !/^\S/.test(lines[index]) && !/^  \S/.test(lines[index])) {
      const runner = lines[index].match(/^    runs-on: (.+)$/);
      if (runner) runsOn = runner[1];
      index += 1;
    }
    jobs.push({id, runsOn});
  }
  return jobs;
}

function triggerPaths(source, event) {
  const lines = source.split(/\r?\n/);
  const onIndex = lines.findIndex((line) => line === 'on:');
  const eventIndex = lines.findIndex(
    (line, index) => index > onIndex && line === `  ${event}:`,
  );
  if (eventIndex === -1) return null;
  const paths = [];
  let readingPaths = false;
  for (const line of lines.slice(eventIndex + 1)) {
    if (/^\S/.test(line) || /^  [a-z_]+:\s*$/.test(line)) break;
    if (line === '    paths:') {
      readingPaths = true;
      continue;
    }
    if (readingPaths) {
      const match = line.match(/^      - "([^"]+)"$/);
      if (match) paths.push(match[1]);
      else if (/^    \S/.test(line)) break;
    }
  }
  return paths.length ? paths : null;
}

function matchesPath(pattern, file) {
  const escaped = pattern
    .replace(/[.+?^${}()|[\]\\]/g, '\\$&')
    .replaceAll('**', '::DOUBLE_STAR::')
    .replaceAll('*', '[^/]*')
    .replaceAll('::DOUBLE_STAR::', '.*');
  return new RegExp(`^${escaped}$`).test(file);
}

function triggersForPath(source, event, file) {
  if (!workflowTriggers(source).includes(event)) return false;
  const paths = triggerPaths(source, event);
  return paths === null || paths.some((pattern) => matchesPath(pattern, file));
}

function representativeRulePaths(rule) {
  return [
    ...rule.match.files,
    ...rule.match.prefixes.map(prefix => `${prefix}__routing_probe__.txt`),
    ...rule.match.segments.map(segment => `__routing_probe__/${segment}/file.txt`),
    ...rule.match.suffixes.map(suffix => `__routing_probe__/file${suffix}`),
  ];
}

for (const [gate, workflowName] of [
  ['research-web-bootstrap', 'bootstrap'],
]) {
  test(`${gate} workflow covers every deterministic policy matcher`, () => {
    const routedRules = verificationPolicy.rules.filter(rule => rule.ci.includes(gate));
    assert.ok(routedRules.length > 0);
    for (const rule of routedRules) {
      for (const file of representativeRulePaths(rule)) {
        for (const event of ['pull_request', 'push']) {
          assert.equal(
            triggersForPath(workflows[workflowName], event, file),
            true,
            `${gate}: ${rule.id}: ${event}: ${file}`,
          );
        }
      }
    }
  });
}

function policyRuleMatches(rule, file) {
  const segments = file.split('/');
  return rule.match.files.includes(file)
    || rule.match.prefixes.some(prefix => file.startsWith(prefix))
    || rule.match.segments.some(segment => segments.includes(segment))
    || rule.match.suffixes.some(suffix => file.endsWith(suffix));
}

function policyRequiresGate(file, gate) {
  return verificationPolicy.rules.some(rule => rule.ci.includes(gate) && policyRuleMatches(rule, file));
}

test('Docker runtime test paths retain required Native bootstrap coverage', () => {
  const policy = JSON.parse(fs.readFileSync(
    new URL('../../.agents/verification-policy.json', import.meta.url), 'utf8',
  ));
  for (const file of [
    'tests/research_web/test_runtime_contract.py',
    'tests/research_web/test_runtime_mode.py',
    'tests/research_web/test_docker_runtime.py',
  ]) {
    assert.ok(policy.rules.some(rule => rule.match.files.includes(file)
      && rule.ci.includes('research-web-bootstrap')), `policy must require bootstrap: ${file}`);
    for (const event of ['pull_request', 'push']) {
      assert.equal(triggersForPath(workflows.bootstrap, event, file), true, `${event}: ${file}`);
    }
  }
});

test('documentation-only changes use only the lightweight constraints workflow', () => {
  const file = 'docs/README.md';
  assert.equal(triggersForPath(workflows.constraints, 'push', file), true);
  assert.equal(triggersForPath(workflows.bootstrap, 'push', file), false);
  assert.equal(triggersForPath(workflows.checks, 'push', file), false);
  assert.equal(triggersForPath(workflows.windows, 'push', file), false);
  assert.equal(triggersForPath(workflows.desktop, 'push', file), false);
});

test('installation changes trigger the GitHub macOS bootstrap gate', () => {
  for (const file of [
    'setup-web.sh',
    'rwb',
    'scripts/setup_web.py',
    'requirements/web.lock',
    'requirements/desktop.in',
    'package-lock.json',
    'yarn.lock',
    'uv.lock',
    'nested/dependency.lock',
    'vendor/cjpy/0.5.2/manifest.json',
  ]) {
    assert.equal(triggersForPath(workflows.bootstrap, 'push', file), true, file);
    assert.equal(triggersForPath(workflows.bootstrap, 'pull_request', file), true, file);
  }
  assert.match(workflows.bootstrap, /macos-14/);
  assert.doesNotMatch(workflows.bootstrap, /windows-2022/);
  for (const file of ['setup-web.cmd', 'rwb.cmd']) {
    assert.equal(triggersForPath(workflows.bootstrap, 'push', file), false, file);
    assert.equal(triggersForPath(workflows.bootstrap, 'pull_request', file), false, file);
  }
});

test('reopened platform scope selects Windows verification without automatic dispatch', () => {
  for (const file of [
    'setup-web.cmd',
    'rwb.cmd',
    'scripts/setup_web.py',
    'requirements/web.lock',
    'app/research_web/service_manager.py',
    'app/research_web/runtime_auth.py',
    'app/research_web/runtime/launcher.py',
    'app/research_web/local_integrations/manager.py',
    'tests/research_web/test_local_integrations.py',
    'vendor/cjpy/0.5.2/manifest.json',
    '.gitattributes',
  ]) {
    assert.equal(policyRequiresGate(file, 'research-web-windows-verify'), true, file);
    assert.equal(triggersForPath(workflows.windows, 'push', file), false, `push: ${file}`);
    assert.equal(triggersForPath(workflows.windows, 'pull_request', file), false, `pull_request: ${file}`);
  }

  for (const file of [
    'docs/README.md',
    'setup-web.sh',
    'rwb',
    'app/research_web/ui/app.mjs',
    'app/research_web/frameworks/service.py',
    'app/research_web/datahub/providers_akshare.py',
  ]) {
    assert.equal(policyRequiresGate(file, 'research-web-windows-verify'), false, file);
    assert.equal(triggersForPath(workflows.windows, 'push', file), false, file);
    assert.equal(triggersForPath(workflows.windows, 'pull_request', file), false, file);
  }
});

for (const file of [
  '.github/workflows/research-web-bootstrap.yml',
  '.github/workflows/research-web-windows-verify.yml',
  'tests/javascript/actions_quota_governance.test.mjs',
]) {
  test(`focused CI path automatically triggers both required Web workflows: ${file}`, () => {
    for (const event of ['pull_request', 'push']) {
      for (const name of ['bootstrap', 'checks']) {
        assert.equal(triggersForPath(workflows[name], event, file), true, `${name}: ${event}: ${file}`);
      }
    }
    assert.equal(triggersForPath(workflows.windows, 'pull_request', file), false, file);
    assert.equal(triggersForPath(workflows.windows, 'push', file), false, file);
  });
}

test('Bootstrap has exactly one macOS clean-install job and its intended triggers', () => {
  assert.deepEqual(
    workflowTriggers(workflows.bootstrap),
    ['pull_request', 'push', 'workflow_dispatch'],
  );
  assert.deepEqual(workflowJobs(workflows.bootstrap), [
    {id: 'clean-install', runsOn: 'macos-14'},
  ]);
});

test('macOS bootstrap proves product readiness and browser assets', () => {
  assert.match(workflows.bootstrap, /report\['installation_ok'\] is True/);
  assert.match(workflows.bootstrap, /report\['product_ready'\] is True/);
  assert.match(workflows.bootstrap, /http:\/\/127\.0\.0\.1:8088\/\s*>\s*root\.html/);
  assert.match(workflows.bootstrap, /http:\/\/127\.0\.0\.1:8088\/static\/app\.mjs\s*>\s*app\.mjs/);
});

test('workflow job parser detects unquoted and quoted extra job keys', () => {
  const source = [
    'jobs:',
    '  clean-install:',
    '    runs-on: macos-14',
    '    strategy:',
    '      matrix:',
    '        os: [macos-14]',
    '  extra_job:',
    '    runs-on: ubuntu-latest',
    '  ExtraJob:',
    '    runs-on: windows-2022',
    '  "quoted-extra":',
    '    runs-on: macos-14',
    "  'single-quoted-extra':",
    '    runs-on: ubuntu-latest',
    '  inline-extra: { runs-on: ubuntu-latest, steps: [] }',
    '  commented-extra: # manual verification only',
  ].join('\n');

  const jobs = workflowJobs(source);
  assert.deepEqual(jobs, [
    {id: 'clean-install', runsOn: 'macos-14'},
    {id: 'extra_job', runsOn: 'ubuntu-latest'},
    {id: 'ExtraJob', runsOn: 'windows-2022'},
    {id: 'quoted-extra', runsOn: 'macos-14'},
    {id: 'single-quoted-extra', runsOn: 'ubuntu-latest'},
    {id: 'inline-extra', runsOn: null},
    {id: 'commented-extra', runsOn: null},
  ]);
  assert.equal(jobs.some(({id}) => id === 'strategy'), false);
  assert.equal(jobs.some(({id}) => id === 'matrix'), false);
});

test('ordinary Research Web code uses Linux checks without unnecessary native jobs', () => {
  const ordinary = 'app/research_web/frameworks/service.py';
  assert.equal(triggersForPath(workflows.checks, 'push', ordinary), true);
  assert.equal(triggersForPath(workflows.bootstrap, 'push', ordinary), false);
  assert.equal(triggersForPath(workflows.windows, 'push', ordinary), false);

  const platformSpecific = 'app/research_web/service_manager.py';
  assert.equal(triggersForPath(workflows.checks, 'push', platformSpecific), true);
  assert.equal(triggersForPath(workflows.bootstrap, 'push', platformSpecific), true);
  assert.equal(policyRequiresGate(platformSpecific, 'research-web-windows-verify'), true);
  assert.equal(triggersForPath(workflows.windows, 'push', platformSpecific), false);
});

test('platform workflows retain explicit routing boundaries', () => {
  assert.deepEqual(workflowTriggers(workflows.tabbit), ['workflow_dispatch']);
  assert.deepEqual(workflowTriggers(workflows.windows), ['workflow_dispatch']);
  assert.deepEqual(workflowJobs(workflows.windows), [
    {id: 'windows-local-integrations', runsOn: 'windows-2022'},
  ]);
  assert.equal(triggersForPath(workflows.desktop, 'push', 'src-tauri/src/main.rs'), true);
});

test('Windows verification executes the public installer and launcher contract', () => {
  assert.match(workflows.windows, /expected_sha:[\s\S]*required: true/);
  assert.match(workflows.windows, /GITHUB_SHA[\s\S]*EXPECTED_SHA/);
  assert.match(workflows.windows, /python-version: "3\.12"/);
  assert.match(workflows.windows, /node-version: "22\.19\.0"/);
  assert.match(workflows.windows, /shell: cmd[\s\S]*setup-web\.cmd --no-start/);
  assert.match(workflows.windows, /rwb\.cmd web start --no-open/);
  assert.match(workflows.windows, /rwb\.cmd web doctor --json > doctor\.json/);
  assert.match(workflows.windows, /rwb\.cmd web stop/);
  assert.match(workflows.windows, /tests\/research_web\/test_setup_web\.py/);
});

test('automatic workflows cancel stale runs and use bounded jobs', () => {
  for (const source of [workflows.bootstrap, workflows.checks, workflows.constraints, workflows.windows]) {
    assert.match(source, /concurrency:/);
    assert.match(source, /cancel-in-progress: true/);
    assert.match(source, /timeout-minutes:/);
  }
  assert.match(workflows.checks, /runs-on: ubuntu-latest/);
  assert.doesNotMatch(workflows.checks, /runs-on: (?:macos|windows)/);
  assert.match(workflows.checks, /python -m venv \.venv/);
  assert.doesNotMatch(
    workflows.checks,
    /pytest tests\/research_web --confcutdir/,
    'daily checks must not silently expand to the full Research Web suite',
  );
  for (const contract of [
    'test_protocol.py',
    'test_integration_coordinator.py',
    'test_documentation.py',
    'test_doc_sync.py',
    'test_cli_lazy.py',
  ]) {
    assert.match(workflows.checks, new RegExp(contract.replace('.', '\\.')));
  }
  assert.match(workflows.checks, /RWB_TEST_PYTHON="\$PWD\/\.venv\/bin\/python"/);
});

test('Web evidence retention is short and full logs upload only on failure', () => {
  assert.match(workflows.bootstrap, /if: success\(\)[\s\S]*retention-days: 3/);
  assert.match(
    workflows.bootstrap,
    /if: failure\(\)[\s\S]*logs\/setup-web\.log[\s\S]*retention-days: 3/,
  );
  assert.match(workflows.windows, /retention-days: 3/);
});

test('Docker CI is dispatched by the Linux device for an exact commit', () => {
  const docker = readWorkflow('research-web-docker.yml');
  assert.deepEqual(workflowTriggers(docker), ['workflow_dispatch']);
  assert.match(docker, /expected_sha:[\s\S]*required: true[\s\S]*type: string/);
  assert.match(docker, /EXPECTED_SHA: \$\{\{ inputs\.expected_sha \}\}/);
  assert.match(docker, /git rev-parse HEAD/);
  assert.match(docker, /actual.*EXPECTED_SHA/);
  assert.deepEqual(workflowJobs(docker), [{id: 'stage-scope', runsOn: 'ubuntu-latest'}, {id: 'docker-runtime', runsOn: 'ubuntu-24.04'}]);
  for (const event of ['pull_request', 'push']) {
    for (const file of [
      'Dockerfile', '.dockerignore', 'compose.yaml', 'docker/supervisor.py',
      'docker/healthcheck.py', 'docker/stage_dsh.py', 'runtimes/research_web.json',
      'app/research_web/runtime_contract.py', 'app/research_web/runtime_state.py',
      'app/research_web/process_spec.py', 'app/research_web/__init__.py',
      'app/research_web/staged_runtime.py', 'app/research_web/runtime_auth.py',
      'app/research_web/launch_runtime.py', 'app/research_web/service_manager.py',
      'research_workbench_entrypoint/docker_runtime.py', 'research_workbench_entrypoint/runtime_mode.py',
      'core/settings/base.py', 'core/observability/logger.py',
      'scripts/setup_web.py', 'setup-web.sh', 'setup-web.cmd', 'rwb', 'rwb.cmd',
      'requirements/web.lock', 'requirements/web.in', 'pyproject.toml',
      'vendor/cjpy/0.5.2/manifest.json', 'vendor/dsh-tabbit/runtime.mjs',
      '.agents/verification-policy.json', 'tests/javascript/verification_policy.test.mjs',
      'tests/javascript/actions_quota_governance.test.mjs', 'tests/javascript/docker_runtime_contract.test.mjs',
      '.github/workflows/research-web-docker.yml',
    ]) assert.equal(triggersForPath(docker, event, file), false, `${event}: ${file}`);
    for (const file of ['docs/README.md', 'docs/actions-budget.md', 'app/research_web/ui/app.mjs', 'app/research_web/frameworks/service.py']) {
      assert.equal(triggersForPath(docker, event, file), false, `${event}: ${file}`);
    }
    for (const file of ['runtimes/research_web.json', 'app/research_web/runtime_contract.py', 'app/research_web/runtime_state.py', 'app/research_web/staged_runtime.py', 'app/research_web/process_spec.py', 'app/research_web/__init__.py']) {
      assert.equal(triggersForPath(workflows.bootstrap, event, file), true, `native ${event}: ${file}`);
    }
    assert.equal(triggersForPath(workflows.bootstrap, event, 'Dockerfile'), false);
  }
});
