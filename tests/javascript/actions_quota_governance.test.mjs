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
    'setup-web.cmd',
    'scripts/setup_web.py',
    'requirements/web.lock',
    'vendor/cjpy/0.5.2/manifest.json',
  ]) {
    assert.equal(triggersForPath(workflows.bootstrap, 'push', file), true, file);
    assert.equal(triggersForPath(workflows.bootstrap, 'pull_request', file), true, file);
  }
  assert.match(workflows.bootstrap, /macos-14/);
  assert.doesNotMatch(workflows.bootstrap, /windows-2022/);
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
  assert.equal(triggersForPath(workflows.windows, 'push', platformSpecific), false);
});

test('platform workflows retain explicit routing boundaries', () => {
  assert.deepEqual(workflowTriggers(workflows.tabbit), ['workflow_dispatch']);
  assert.deepEqual(workflowTriggers(workflows.windows), ['workflow_dispatch']);
  assert.equal(triggersForPath(workflows.desktop, 'push', 'src-tauri/src/main.rs'), true);
});

test('automatic workflows cancel stale runs and use bounded jobs', () => {
  for (const source of [workflows.bootstrap, workflows.checks, workflows.constraints]) {
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
