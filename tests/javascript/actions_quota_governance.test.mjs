import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
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

test('Checks installs hashed Web SDK and renderer blocks from the actual generated requirements', t => {
  const root=fs.mkdtempSync(path.join(os.tmpdir(),'rwb-ci-lock-contract-'));
  t.after(()=>fs.rmSync(root,{recursive:true,force:true}));
  for(const name of ['requirements/web.lock','app/research_web/capabilities/pack-runtime-lock.json','pyproject.toml']) {
    const target=path.join(root,name);fs.mkdirSync(path.dirname(target),{recursive:true});
    fs.copyFileSync(new URL('../../'+name,import.meta.url),target);
  }
  const lock=fs.readFileSync(path.join(root,'requirements/web.lock'),'utf8');
  const step=workflows.checks.split('      - name: Install declared test dependencies\n')[1]?.split('\n      - name:')[0];
  assert.ok(step,'dependency installation step must remain');
  const beforeInstall=step.slice(0,step.indexOf('pip install'));
  const heredoc=beforeInstall.match(/          \.venv\/bin\/python[^\n]*<<'([A-Za-z_]+)'\n([^]*?)\n          \1/);
  assert.ok(heredoc,'run the actual requirements generation before dependency installation');
  const code=heredoc[2].split('\n').map(line=>line.slice(10)).join('\n');
  const result=spawnSync(process.env.RWB_TEST_PYTHON || 'python3',['-B','-c',code],{
    cwd:root,env:{...process.env,RUNNER_TEMP:root,PYTHONDONTWRITEBYTECODE:'1'},encoding:'utf8',timeout:10000,
  });
  assert.equal(result.status,0,result.stderr);
  const install=step.split('\n').find(line=>line.includes('pip install')&&line.includes('--require-hashes')&&line.includes('--no-deps'));
  assert.ok(install,'install the generated requirements with pinned hashes and no implicit dependencies');
  const requirement=install.match(/(?:^|\s)-r\s+(?:"([^"]+)"|'([^']+)'|(\S+))/);
  assert.ok(requirement);
  const filename=(requirement[1]||requirement[2]||requirement[3]).replace(/\$(?:\{RUNNER_TEMP\}|RUNNER_TEMP)/g,root);
  const extracted=fs.readFileSync(filename,'utf8');
  const entries=extracted.split(/\n(?=[a-z0-9])/).filter(Boolean);
  for(const packageName of ['reportlab','openpyxl','et-xmlfile','mcp','mcp-types']) {
    const entry=entries.find(value=>value.startsWith(`${packageName}==`));
    assert.ok(entry,packageName);
    const original=lock.split(/\n(?=[a-z0-9])/).find(value=>value.startsWith(`${packageName}==`));
    assert.equal(entry.trimEnd(),original.trimEnd(),`${packageName} block must retain all original hashes`);
    assert.match(entry,/--hash=sha256:[a-f0-9]{64}/);
    if(['mcp','mcp-types'].includes(packageName)) assert.ok(entry.startsWith(`${packageName}==2.2.0`));
  }
});

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

test('retention-only changes select their tool contracts while product changes retain the full scope', t => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'rwb-retention-ci-scope-'));
  t.after(() => fs.rmSync(root, {recursive: true, force: true}));
  const step = workflows.checks.split('      - name: Choose contract test scope\n')[1]?.split('\n      - name:')[0];
  const match = step?.match(/          python - <<'PY'\n([^]*?)\n          PY/);
  assert.ok(match);
  const code = match[1].split('\n').map(line => line.slice(10)).join('\n');
  const toolFiles = ['scripts/test_artifact_retention.py', 'tests/research_web/test_test_artifact_retention.py',
    'AGENTS.md', 'docs/research-web-storage-retention.md', 'docs/generated/py_file_index.md',
    '.ai/reports/fix.md', '.github/workflows/research-web-checks.yml', 'tests/javascript/actions_quota_governance.test.mjs'];
  for (const [files, base, expected] of [[toolFiles, 'a'.repeat(40), true],
    [[...toolFiles, 'app/research_web/api.py'], 'a'.repeat(40), false],
    [['.github/workflows/research-web-checks.yml'], 'a'.repeat(40), false], [toolFiles, '', false]]) {
    const output = path.join(root, `output-${fs.readdirSync(root).length}`);
    const harness = `import json, os, subprocess\nfrom types import SimpleNamespace\nfixture_files=json.loads(os.environ['SCOPE_FILES'])\ndef fake_run(argv, **kwargs):\n    assert argv[-2:]==[os.environ['BASE_SHA'],os.environ['HEAD_SHA']]\n    if 'fetch' in argv: return SimpleNamespace(returncode=0)\n    assert argv[:4]==['git','diff','--name-only','-z']\n    return SimpleNamespace(returncode=0,stdout=bytes([0]).join(name.encode() for name in fixture_files)+bytes([0]))\nsubprocess.run=fake_run\nexec(${JSON.stringify(code)})`;
    const result = spawnSync(process.env.RWB_TEST_PYTHON || 'python3', ['-B', '-c', harness], {
      env: {...process.env, BASE_SHA: base, HEAD_SHA: 'b'.repeat(40), GITHUB_OUTPUT: output, SCOPE_FILES: JSON.stringify(files)}, encoding: 'utf8', timeout: 10000,
    });
    assert.equal(result.status, 0, result.stderr);
    assert.equal(fs.readFileSync(output, 'utf8').trim().split('\n')[0], `retention_only=${expected}`);
  }
  assert.match(workflows.checks, /BASE_SHA: \$\{\{ github\.event\.pull_request\.base\.sha \|\| github\.event\.before \}\}/);
  assert.match(workflows.checks, /HEAD_SHA: \$\{\{ github\.event\.pull_request\.head\.sha \|\| github\.sha \}\}/);
  assert.match(workflows.checks, /-- tests\/research_web\/test_test_artifact_retention\.py --confcutdir=tests\/research_web -q/);
  for (const name of ['Run Research Web JavaScript contracts', 'Verify pinned editorial engine without model or paid requests']) {
    const block = workflows.checks.split(`      - name: ${name}\n`)[1]?.split('\n      - name:')[0];
    assert.match(block, /if: steps\.contract-scope\.outputs\.retention_only != 'true'/);
  }
});

test('research pack changes select Host interfaces while unrelated product changes keep the full scope', t => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'rwb-pack-ci-scope-'));
  t.after(() => fs.rmSync(root, {recursive: true, force: true}));
  const step = workflows.checks.split('      - name: Choose contract test scope\n')[1]?.split('\n      - name:')[0];
  const match = step?.match(/          python - <<'PY'\n([^]*?)\n          PY/);
  assert.ok(match);
  const code = match[1].split('\n').map(line => line.slice(10)).join('\n');
  const packFiles = ['app/research_web/scenario_pack_execution.py', 'app/research_web/main.py',
    'tests/research_web/test_pack_execution_host.py', 'docs/research-web-research-packs.md'];
  for (const [files, expected] of [[packFiles, true], [[...packFiles, 'app/research_web/market_service.py'], false], [['app/research_web/capabilities/pack_execution.py', 'tests/unit/test_ci_pytest_partitions.py'], false], [['app/research_web/main.py'], false], [[], false]]) {
    const output = path.join(root, `output-${fs.readdirSync(root).length}`);
    const harness = `import json, os, subprocess\nfrom types import SimpleNamespace\ndef fake_run(argv, **kwargs):\n    if 'fetch' in argv: return SimpleNamespace(returncode=0)\n    return SimpleNamespace(returncode=0,stdout=bytes([0]).join(name.encode() for name in json.loads(os.environ['SCOPE_FILES']))+bytes([0]))\nsubprocess.run=fake_run\nexec(${JSON.stringify(code)})`;
    const result = spawnSync(process.env.RWB_TEST_PYTHON || 'python3', ['-B', '-c', harness], {
      env: {...process.env, BASE_SHA: 'a'.repeat(40), HEAD_SHA: 'b'.repeat(40), GITHUB_OUTPUT: output, SCOPE_FILES: JSON.stringify(files)}, encoding: 'utf8', timeout: 10000,
    });
    assert.equal(result.status, 0, result.stderr);
    assert.equal(fs.readFileSync(output, 'utf8').trim().split('\n').find(line => line.startsWith('research_packs_only=')), `research_packs_only=${expected}`);
  }
  assert.match(workflows.checks, /test_pack_execution_host\.py/);
  assert.match(workflows.checks, /test_owned_method_execution\.py/);
  assert.match(workflows.checks, /test_weknora_formal_scope\.py/);
});

test('reviewed upgrades select only their maintenance and account UI contracts', t => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'rwb-reviewed-upgrade-scope-'));
  t.after(() => fs.rmSync(root, {recursive: true, force: true}));
  const step = workflows.checks.split('      - name: Choose contract test scope\n')[1]?.split('\n      - name:')[0];
  const match = step?.match(/          python - <<'PY'\n([^]*?)\n          PY/);assert.ok(match);
  const code = match[1].split('\n').map(line => line.slice(10)).join('\n');
  const operator = 'research_workbench_entrypoint/resident/model_provider_upgrade.py';
  const files = [operator, 'research_workbench_entrypoint/resident/gateway_upgrade.py',
    'tests/research_web/test_model_provider_upgrade.py', 'tests/research_web/test_gateway_upgrade.py',
    'app/research_web/ui/server/session.mjs', 'app/research_web/ui/server/profile.css',
    'tests/javascript/research_web_multiuser_session.test.mjs', 'tests/javascript/research_web_mcp_login.test.mjs',
    'app/research_web/ui/progress-data.json', 'docs/CHANGELOG.md', 'docs/architecture/research-web/readme-review.json',
    '.ai/reports/fix.md', '.github/workflows/research-web-checks.yml', '.github/workflows/research-web-bootstrap.yml',
    'tests/javascript/actions_quota_governance.test.mjs'];
  for (const [paths, base, gitFailure, expected] of [[files, 'a'.repeat(40), '', true],
    [[...files, 'app/research_web/workbench.py'], 'a'.repeat(40), '', false],
    [[...files, '.github/workflows/desktop-verify.yml'], 'a'.repeat(40), '', false],
    [[...files, 'tests/research_web/test_protocol.py'], 'a'.repeat(40), '', false],
    [[files[4], 'docs/research-web-ui.md'], 'a'.repeat(40), '', false],
    [files, '', '', false], [files, 'a'.repeat(40), 'fetch', false], [files, 'a'.repeat(40), 'diff', false]]) {
    const output = path.join(root, `output-${fs.readdirSync(root).length}`);
    const harness = `import json, os, subprocess\nfrom types import SimpleNamespace\ndef fake_run(argv, **kwargs):\n    if 'fetch' in argv: return SimpleNamespace(returncode=1 if os.environ['SCOPE_GIT_FAILURE']=='fetch' else 0)\n    return SimpleNamespace(returncode=1 if os.environ['SCOPE_GIT_FAILURE']=='diff' else 0,stdout=bytes([0]).join(name.encode() for name in json.loads(os.environ['SCOPE_FILES']))+bytes([0]))\nsubprocess.run=fake_run\nexec(${JSON.stringify(code)})`;
    const result = spawnSync(process.env.RWB_TEST_PYTHON || 'python3', ['-B', '-c', harness], {
      env: {...process.env, BASE_SHA: base, HEAD_SHA: 'b'.repeat(40), GITHUB_OUTPUT: output,
        SCOPE_FILES: JSON.stringify(paths), SCOPE_GIT_FAILURE: gitFailure}, encoding: 'utf8', timeout: 10000,
    });
    assert.equal(result.status, 0, result.stderr);
    const scope = Object.fromEntries(fs.readFileSync(output, 'utf8').trim().split('\n').map(line => line.split('=')));
    assert.equal(scope.reviewed_upgrade_only, String(expected));
    for (const flag of ['retention_only', 'architecture_only', 'g2b_release_only']) assert.equal(scope[flag], 'false');
  }
});

test('reviewed upgrades run both complete maintenance modules and the bounded account UI group', t => {
  const root = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), 'rwb-reviewed-upgrade-commands-')));
  t.after(() => fs.rmSync(root, {recursive: true, force: true}));
  fs.mkdirSync(path.join(root, '.venv/bin'), {recursive: true});fs.mkdirSync(path.join(root, 'bin'));
  const calls = path.join(root, 'calls.jsonl');
  for (const [file, kind] of [['.venv/bin/python', 'python'], ['bin/git', 'git'], ['bin/node', 'node']]) {
    fs.writeFileSync(path.join(root, file), `#!${process.execPath}\nconst fs=require('node:fs');fs.appendFileSync(process.env.CI_SCOPE_RECORD,JSON.stringify({kind:${JSON.stringify(kind)},args:process.argv.slice(2)})+'\\n');\n`, {mode: 0o700});
  }
  for (const name of ['Run Research Web Python contracts', 'Run Research Web JavaScript contracts']) {
    const step = workflows.checks.split(`      - name: ${name}\n`)[1]?.split('\n      - name:')[0];
    const script = step.split('        run: |\n')[1].split('\n').map(line => line.slice(10)).join('\n');
    const command = script.replaceAll('${{ steps.contract-scope.outputs.retention_only }}', 'false')
      .replaceAll('${{ steps.contract-scope.outputs.architecture_only }}', 'false')
      .replaceAll('${{ steps.contract-scope.outputs.g2b_release_only }}', 'false')
      .replaceAll('${{ steps.contract-scope.outputs.reviewed_upgrade_only }}', 'true');
    const result = spawnSync('/bin/bash', ['-e', '-c', command], {cwd: root,
      env: {...process.env, PATH: path.join(root, 'bin') + path.delimiter + process.env.PATH,
        RUNNER_TEMP: root, GITHUB_RUN_ID: '1', GITHUB_RUN_ATTEMPT: '1', CI_SCOPE_RECORD: calls}, encoding: 'utf8', timeout: 10000});
    assert.equal(result.status, 0, `${name}: ${result.stderr}`);
  }
  const commands = fs.readFileSync(calls, 'utf8').trim().split('\n').map(line => JSON.parse(line));
  const python = commands.filter(item => item.kind === 'python');assert.equal(python.length, 1);
  assert.equal(python[0].args[0], 'scripts/run_ci_pytest_partitions.py');
  assert.deepEqual(python[0].args.slice(python[0].args.indexOf('--') + 1), [
    'tests/research_web/test_model_provider_upgrade.py', 'tests/research_web/test_gateway_upgrade.py', '--confcutdir=tests/research_web', '-q']);
  const git = commands.filter(item => item.kind === 'git');assert.equal(git.length, 1);
  assert.deepEqual(git[0].args.slice(-3), ['b800e50366d1a0868372bbf173822976066c143f',
    'db2ae9a48ceca365852072e622aa6627aa7d0b83', '1529c3189b008b9861a2bee1511f051feefa76eb']);
  const node = commands.filter(item => item.kind === 'node');assert.equal(node.length, 1);
  assert.deepEqual(node[0].args, ['--test', ...['multiuser_session', 'mcp_login', 'account_menu', 'account_workspace',
    'module_navigation', 'progress'].map(name => `tests/javascript/research_web_${name}.test.mjs`),
    'tests/javascript/actions_quota_governance.test.mjs']);
  const editorial = workflows.checks.split('      - name: Verify pinned editorial engine without model or paid requests\n')[1]?.split('\n      - name:')[0];
  assert.match(editorial, /reviewed_upgrade_only != 'true'/);
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
  assert.match(workflows.bootstrap, /macos-15/);
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
    {id: 'clean-install', runsOn: 'macos-15'},
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

test('Mac clean installation verifies the installed Hot runtime without database or model calls', () => {
  assert.match(workflows.bootstrap, /node-version: "24\.19\.0"/);
  assert.match(workflows.bootstrap, /working-directory: services\/hot/);
  assert.match(workflows.bootstrap, /assertNodeRuntime\(\)/);
  assert.match(workflows.bootstrap, /"postgres", "pg-boss", "fast-xml-parser"/);
});

test('automatic workflows cancel stale runs and use bounded jobs', () => {
  for (const source of [workflows.bootstrap, workflows.checks, workflows.constraints, workflows.windows]) {
    assert.match(source, /concurrency:/);
    assert.match(source, /cancel-in-progress: true/);
    assert.match(source, /timeout-minutes:/);
  }
  assert.match(workflows.checks, /runs-on: ubuntu-latest/);
  const checkBudget = workflows.checks.match(/^    timeout-minutes: (\d+)$/m);
  assert.ok(checkBudget && Number(checkBudget[1]) > 0 && Number(checkBudget[1]) <= 45,
    'the original complete Checks job must remain bounded to at most 45 minutes');
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
    'test_multiuser_accounts.py',
    'test_multiuser_gateway.py',
    'test_multiuser_runtime.py',
    'test_multiuser_cli.py',
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

test('pytest evidence staging uses the no-follow allowlist helper and exact artifact directory', () => {
  for (const event of ['pull_request', 'push']) {
    assert.equal(
      triggersForPath(workflows.checks, event, 'scripts/stage_ci_pytest_evidence.py'),
      true,
      `${event}: staging helper must trigger checks`,
    );
    assert.equal(
      triggersForPath(workflows.checks, event, 'tests/unit/test_ci_pytest_evidence_staging.py'),
      true,
      `${event}: staging security contracts must trigger checks`,
    );
  }
  assert.match(workflows.checks, /scripts\/stage_ci_pytest_evidence\.py/);
  assert.match(workflows.checks, /if: always\(\) && steps\.contract-scope\.outputs\.architecture_only != 'true' && steps\.stage-safe-evidence\.outcome == 'success'/);
  assert.match(workflows.checks, /path: artifacts\/research-web-checks\n/);
  assert.doesNotMatch(workflows.checks, /cp "\$root\/\$relative"/);
  assert.doesNotMatch(workflows.checks, /\[ -f "\$root\/\$relative" \]/);
});

test('knowledge authority regressions execute once in each applicable CI branch', t => {
  const root=fs.mkdtempSync(path.join(os.tmpdir(),'rwb-ci-authority-branch-'));
  t.after(()=>fs.rmSync(root,{recursive:true,force:true}));
  const step=workflows.checks.split('      - name: Run Research Web Python contracts\n')[1]?.split('\n      - name:')[0];
  assert.ok(step);
  const script=step.split('        run: |\n')[1].split('\n').map(line=>line.slice(10)).join('\n');
  fs.mkdirSync(path.join(root,'.venv/bin'),{recursive:true});fs.mkdirSync(path.join(root,'bin'));
  fs.writeFileSync(path.join(root,'.venv/bin/python'),`#!${process.execPath}\nconst fs=require('node:fs');fs.appendFileSync(process.env.CI_SCOPE_RECORD,JSON.stringify(process.argv.slice(2))+'\\n');\n`,{mode:0o700});
  fs.writeFileSync(path.join(root,'bin/git'),'#!/bin/sh\nexit 0\n',{mode:0o700});
  for(const [retention,packs] of [[false,false],[false,true],[true,false]]) {
    const record=path.join(root,`${retention}-${packs}.jsonl`);
    const command=script.replaceAll('${{ steps.contract-scope.outputs.retention_only }}',String(retention)).replaceAll('${{ steps.contract-scope.outputs.research_packs_only }}',String(packs)).replaceAll('${{ steps.contract-scope.outputs.architecture_only }}','false').replaceAll('${{ steps.contract-scope.outputs.g2b_release_only }}','false');
    const result=spawnSync('/bin/bash',['-e','-c',command],{cwd:root,env:{...process.env,PATH:path.join(root,'bin')+path.delimiter+process.env.PATH,RUNNER_TEMP:root,GITHUB_RUN_ID:'1',GITHUB_RUN_ATTEMPT:'1',CI_SCOPE_RECORD:record},encoding:'utf8',timeout:10000});
    assert.equal(result.status,0,result.stderr);
    const calls=fs.readFileSync(record,'utf8').trim().split('\n').map(line=>JSON.parse(line));
    const argumentsFound=calls.filter(args=>args[0]==='scripts/run_ci_pytest_partitions.py').flatMap(args=>args.slice(args.indexOf('--')+1));
    for(const file of ['test_weknora_formal_scope.py','test_store.py','test_capabilities_native.py']) {
      assert.equal(argumentsFound.filter(value=>value===`tests/research_web/${file}`).length,retention?0:1,`${file}: retention=${retention},packs=${packs}`);
    }
    if(packs) {
      assert.equal(argumentsFound.filter(value=>value==='tests/research_web/test_service_manager.py').length,0);
      assert.equal(argumentsFound.filter(value=>value==='tests/research_web/test_service_manager.py::test_start_waits_for_runtime_readiness_before_web_spawn_and_browser').length,1);
      assert.equal(argumentsFound.filter(value=>value==='tests/research_web/test_api.py').length,0);
      for(const file of ['test_execution_cancel_native.py','test_owned_news_native_sdk.py']) {
        assert.equal(argumentsFound.includes(`tests/research_web/${file}`),false,`${file} belongs to the macOS built-SDK job`);
        assert.ok(workflows.bootstrap.includes(`tests/research_web/${file}`),`${file} must execute on macOS`);
      }
    }
    if(retention) assert.equal(argumentsFound.filter(value=>value==='tests/research_web/test_test_artifact_retention.py').length,1);
  }
});

test('architecture-only changes select their owner contracts while product or unknown changes retain full scope', t => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'rwb-architecture-ci-scope-'));
  t.after(() => fs.rmSync(root, {recursive: true, force: true}));
  const step = workflows.checks.split('      - name: Choose contract test scope\n')[1]?.split('\n      - name:')[0];
  const match = step?.match(/          python - <<'PY'\n([^]*?)\n          PY/);
  assert.ok(match);
  const code = match[1].split('\n').map(line => line.slice(10)).join('\n');
  const toolFiles = ['scripts/check_research_architecture.mjs', 'tests/javascript/research_web_architecture.test.mjs',
    'docs/AGENT_WORKFLOW.md', 'docs/research-web-documentation.md', '.ai/reports/fix.md',
    '.github/workflows/research-web-checks.yml', 'tests/javascript/actions_quota_governance.test.mjs'];
  for (const [files, base, gitFailure, expected] of [[toolFiles, 'a'.repeat(40), '', true],
    [[...toolFiles, 'app/research_web/api.py'], 'a'.repeat(40), '', false],
    [['.github/workflows/research-web-checks.yml'], 'a'.repeat(40), '', false],
    [toolFiles, '', '', false], [toolFiles, 'a'.repeat(40), 'fetch', false],
    [toolFiles, 'a'.repeat(40), 'diff', false]]) {
    const output = path.join(root, `output-${fs.readdirSync(root).length}`);
    const harness = `import json, os, subprocess\nfrom types import SimpleNamespace\nfixture_files=json.loads(os.environ['SCOPE_FILES'])\ndef fake_run(argv, **kwargs):\n    assert argv[-2:]==[os.environ['BASE_SHA'],os.environ['HEAD_SHA']]\n    if 'fetch' in argv: return SimpleNamespace(returncode=1 if os.environ['SCOPE_GIT_FAILURE']=='fetch' else 0)\n    assert argv[:4]==['git','diff','--name-only','-z']\n    return SimpleNamespace(returncode=1 if os.environ['SCOPE_GIT_FAILURE']=='diff' else 0,stdout=bytes([0]).join(name.encode() for name in fixture_files)+bytes([0]))\nsubprocess.run=fake_run\nexec(${JSON.stringify(code)})`;
    const result = spawnSync(process.env.RWB_TEST_PYTHON || 'python3', ['-B', '-c', harness], {
      env: {...process.env, BASE_SHA: base, HEAD_SHA: 'b'.repeat(40), GITHUB_OUTPUT: output,
        SCOPE_FILES: JSON.stringify(files), SCOPE_GIT_FAILURE: gitFailure}, encoding: 'utf8', timeout: 10000,
    });
    assert.equal(result.status, 0, result.stderr);
    const scope = Object.fromEntries(fs.readFileSync(output, 'utf8').trim().split('\n').map(line => line.split('=')));
    assert.equal(scope.architecture_only, String(expected));
    assert.equal(scope.retention_only, 'false');
  }
});

test('architecture-only CI runs the owner JavaScript contracts without Python or editorial work', t => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'rwb-architecture-ci-branch-'));
  t.after(() => fs.rmSync(root, {recursive: true, force: true}));
  const bin = path.join(root, 'bin'), commands = path.join(root, 'node-commands');fs.mkdirSync(bin);
  fs.writeFileSync(path.join(bin, 'git'), '#!/bin/sh\nexit 91\n', {mode: 0o755});
  fs.writeFileSync(path.join(bin, 'node'), '#!/bin/sh\nprintf "%s\\n" "$*" >> "$SCOPE_NODE_LOG"\n', {mode: 0o755});
  for (const name of ['Run Research Web Python contracts', 'Run Research Web JavaScript contracts']) {
    const block = workflows.checks.split(`      - name: ${name}\n`)[1]?.split('\n      - name:')[0];
    assert.ok(block);
    const multiline = block.match(/        run: \|\n([^]*)/);
    const script = (multiline ? multiline[1].split('\n').map(line => line.slice(10)).join('\n')
      : block.match(/        run: ([^\n]+)/)?.[1])
      .replaceAll('${{ steps.contract-scope.outputs.architecture_only }}', 'true')
      .replaceAll('${{ steps.contract-scope.outputs.retention_only }}', 'false');
    const result = spawnSync('/bin/bash', ['-e', '-c', script], {
      cwd: root, env: {...process.env, PATH: `${bin}:/usr/bin:/bin`, SCOPE_NODE_LOG: commands}, encoding: 'utf8', timeout: 10000,
    });
    assert.equal(result.status, 0, `${name}: ${result.stderr}`);
  }
  assert.equal(fs.readFileSync(commands, 'utf8').trim(), '--test tests/javascript/research_web_architecture.test.mjs');
  for (const name of ['Verify pinned editorial engine without model or paid requests', 'Stage safe pytest evidence', 'Upload safe pytest evidence']) {
    const block = workflows.checks.split(`      - name: ${name}\n`)[1]?.split('\n      - name:')[0];
    assert.match(block, /if: [^\n]*steps\.contract-scope\.outputs\.architecture_only != 'true'/);
  }
});

test('G2B release scope accepts only its explicit interfaces and sends mixed or unknown changes to full checks', t => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'rwb-release-ci-scope-'));
  t.after(() => fs.rmSync(root, {recursive: true, force: true}));
  const step = workflows.checks.split('      - name: Choose contract test scope\n')[1]?.split('\n      - name:')[0];
  const match = step?.match(/          python - <<'PY'\n([^]*?)\n          PY/);
  assert.ok(match);
  const code = match[1].split('\n').map(line => line.slice(10)).join('\n');
  const releaseFiles = ['docker/release.py', 'docker/Dockerfile.release', 'docker/release-schema.json',
    'app/research_web/maintenance.py', 'app/research_web/service.py', 'app/research_web/main.py',
    'tests/research_web/test_docker_release.py', 'tests/research_web/test_release_maintenance.py',
    'tests/research_web/test_api.py', 'tests/fixtures/g2b_fault_controller.py',
    'docs/architecture/research-web/architecture-map.json', '.ai/reports/2026-10-14-g2b-task.json',
    'outputs/research-web-architecture/api-atlas.html', '.github/workflows/research-web-checks.yml'];
  for (const [files, base, expected] of [[releaseFiles, 'a'.repeat(40), true],
    [[...releaseFiles, 'app/research_web/market_service.py'], 'a'.repeat(40), false],
    [[...releaseFiles, 'tests/unit/test_unrelated.py'], 'a'.repeat(40), false],
    [[...releaseFiles, 'scripts/test_artifact_retention.py'], 'a'.repeat(40), false],
    [['app/research_web/service.py'], 'a'.repeat(40), false], [releaseFiles, '', false]]) {
    const output = path.join(root, `output-${fs.readdirSync(root).length}`);
    const harness = `import json, os, subprocess\nfrom types import SimpleNamespace\ndef fake_run(argv, **kwargs):\n    if 'fetch' in argv: return SimpleNamespace(returncode=0)\n    return SimpleNamespace(returncode=0,stdout=bytes([0]).join(name.encode() for name in json.loads(os.environ['SCOPE_FILES']))+bytes([0]))\nsubprocess.run=fake_run\nexec(${JSON.stringify(code)})`;
    const result = spawnSync(process.env.RWB_TEST_PYTHON || 'python3', ['-B', '-c', harness], {
      env: {...process.env, BASE_SHA: base, HEAD_SHA: 'b'.repeat(40), GITHUB_OUTPUT: output, SCOPE_FILES: JSON.stringify(files)}, encoding: 'utf8', timeout: 10000,
    });
    assert.equal(result.status, 0, result.stderr);
    const lines = fs.readFileSync(output, 'utf8').trim().split('\n');
    assert.equal(lines.find(line => line.startsWith('g2b_release_only=')), `g2b_release_only=${expected}`);
  }
});

test('G2B CI executes its release and public Host contracts once without the unrelated Web matrix', t => {
  const root = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), 'rwb-release-ci-commands-')));
  t.after(() => fs.rmSync(root, {recursive: true, force: true}));
  const step = workflows.checks.split('      - name: Run Research Web Python contracts\n')[1]?.split('\n      - name:')[0];
  const script = step.split('        run: |\n')[1].split('\n').map(line => line.slice(10)).join('\n');
  fs.mkdirSync(path.join(root, '.venv/bin'), {recursive: true});
  fs.mkdirSync(path.join(root, 'bin'));
  fs.writeFileSync(path.join(root, '.venv/bin/python'), `#!${process.execPath}\nconst fs=require('node:fs');fs.appendFileSync(process.env.CI_SCOPE_RECORD,JSON.stringify(process.argv.slice(2))+'\\n');\n`, {mode: 0o700});
  fs.writeFileSync(path.join(root, 'bin/git'), '#!/bin/sh\nexit 0\n', {mode: 0o700});
  const record = path.join(root, 'calls.jsonl');
  const command = script.replaceAll('${{ steps.contract-scope.outputs.retention_only }}', 'false')
    .replaceAll('${{ steps.contract-scope.outputs.g2b_release_only }}', 'true')
    .replaceAll('${{ steps.contract-scope.outputs.architecture_only }}', 'false')
    .replaceAll('${{ steps.contract-scope.outputs.research_packs_only }}', 'false');
  const result = spawnSync('/bin/bash', ['-e', '-c', command], {cwd: root,
    env: {...process.env, PATH: path.join(root, 'bin') + path.delimiter + process.env.PATH, RUNNER_TEMP: root, GITHUB_RUN_ID: '1', GITHUB_RUN_ATTEMPT: '1', CI_SCOPE_RECORD: record}, encoding: 'utf8', timeout: 10000});
  assert.equal(result.status, 0, result.stderr);
  const calls = fs.readFileSync(record, 'utf8').trim().split('\n').map(line => JSON.parse(line));
  assert.equal(calls.length, 1);
  assert.equal(calls[0][0], 'scripts/run_ci_pytest_partitions.py');
  const args = calls[0].slice(calls[0].indexOf('--') + 1);
  for (const file of ['test_docker_release.py', 'test_release_maintenance.py', 'test_docker_manager.py', 'test_protocol.py']) {
    assert.equal(args.filter(value => value === `tests/research_web/${file}`).length, 1);
  }
  assert.ok(args.includes('tests/research_web/test_api.py::test_release_idle_includes_current_datahub_and_plugin_work'));
  assert.ok(args.includes('tests/research_web/test_api.py::test_unowned_instance_is_read_only'));
  assert.ok(args.includes('tests/research_web/test_weknora_current_api.py::test_service_only_start_arms_existing_scheduler_without_automation_history'));
  assert.ok(args.includes('tests/research_web/test_report_workflow_integration.py::test_delivery_retry_consumes_late_payload_without_starting_another_claw_session'));
  assert.ok(!args.includes('tests/research_web/test_weknora_current_api.py'));
  assert.ok(!args.some(value => /event_studies|fingpt_cutover|tests\/unit\//.test(value)));
  const js = workflows.checks.split('      - name: Run Research Web JavaScript contracts\n')[1]?.split('\n      - name:')[0];
  assert.match(js, /docker_runtime_contract\.test\.mjs/);
  assert.match(js, /actions_quota_governance\.test\.mjs/);
  const editorial = workflows.checks.split('      - name: Verify pinned editorial engine without model or paid requests\n')[1]?.split('\n      - name:')[0];
  assert.match(editorial, /g2b_release_only != 'true'/);
});
