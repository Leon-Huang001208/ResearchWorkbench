import fs from 'node:fs';
import { execFileSync, spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { performance } from 'node:perf_hooks';

const report = '.ai/reports/fingpt-native-plan-v1/';
const python = '/private/tmp/rwb-claw-test-env.Z0DP8D/bin/python';
const node = '/Users/leon/.research-workbench/node-runtime/node_modules/node/bin/node';
const original = new Set([
  'app/research_web/runtime/research.cordis.yml', 'app/research_web/runtime/guard.mjs',
  'app/research_web/projection.py', 'app/research_web/service.py', 'app/research_web/ui/views.mjs',
  'app/research_web/ui/shell.mjs', 'app/research_web/ui/styles.css',
  'tests/research_web/test_protocol.py', 'tests/research_web/test_event_recovery.py',
  'tests/research_web/test_runtime_launch.py', 'tests/javascript/research_web_guard.test.mjs',
  'tests/javascript/research_web_ui.test.mjs', 'docs/research-web-ui.md',
  'docs/architecture/research-web/02-research-runtime.md', 'docs/architecture/research-web/04-api.md',
  'docs/DEVELOPMENT_MAP.md', 'docs/architecture/research-web/architecture-map.json',
  // Explicit user extension for documentation and generated artifacts.
  'docs/architecture/research-web/readme-review.json', 'docs/research-web-appearance.md',
  'docs/architecture/research-web/08-research-frameworks.md', 'docs/architecture/research-web/01-system.md',
  'docs/architecture/research-web/05-security-validation.md', 'docs/research-web-tabbit.md',
  'docs/generated/py_file_index.md', 'outputs/research-web-architecture/index.html',
  'outputs/research-web-architecture/api-atlas.html', 'logs/research-api-atlas.jsonl',
]);
const write = (file, value) => fs.writeFileSync(report + file, JSON.stringify(value, null, 2) + '\n', { mode: 0o600 });
try {
  const manifestRoot = '.agents/runtime/leon-engineering/';
  const manifest = JSON.parse(fs.readFileSync(manifestRoot + 'manifest.json'));
  for (const [file, hash] of Object.entries(manifest.files)) {
    if (createHash('sha256').update(fs.readFileSync(manifestRoot + file)).digest('hex') !== hash) throw Error('manifest drift');
  }
  for (const file of ['validation-results.json', 'verification-receipt.json', 'boundary-receipt.json']) {
    if (!fs.existsSync(report + file)) write(file, {});
  }
  const gitFiles = args => execFileSync('git', args, { encoding: 'utf8' }).trim().split('\n').filter(Boolean);
  const changed = [...new Set([...gitFiles(['diff', '--name-only', 'f8adae050900e2209bf3f10025b901dea692cdee']), ...gitFiles(['ls-files', '--others', '--exclude-standard'])])].sort();
  for (const file of changed) if (!original.has(file) && !file.startsWith(report)) throw Error('out of scope: ' + file);
  write('changed-files.json', changed);
  const plan = JSON.parse(execFileSync(node, ['scripts/plan_verification.mjs', '--project', '.',
    ...changed.flatMap(file => ['--changed-file', file]), '--signal', 'validation_failure'], { encoding: 'utf8' }));
  write('verification-plan.json', plan);
  const unchanged = ['runtimes/research_web.json', 'requirements/web.in', 'requirements/web.lock',
    'scripts/setup_web.py', 'docs/research-web-installation.md', '.github/workflows/research-web-bootstrap.yml',
    '.agents/verification-policy.json', 'app/research_web/service.py'];
  const hashes = {};
  for (const file of unchanged) {
    const bytes = fs.readFileSync(file);
    if (!bytes.equals(execFileSync('git', ['show', 'HEAD:' + file]))) throw Error('forbidden drift: ' + file);
    hashes[file] = createHash('sha256').update(bytes).digest('hex');
  }
  write('boundary-receipt.json', { status: 'PASS', changedFiles: changed.length, manifestFiles: Object.keys(manifest.files).length, unchangedSHA256: hashes });
  const executed = [];
  for (const gate of [...plan.local].sort((a, b) => a.level.localeCompare(b.level))) {
    let argv = gate.value.split(' ');
    if (gate.id === 'project-constraints-local') argv = ['node', '.agents/project-constraints.mjs', '--project', '.', ...changed.flatMap(file => ['--changed-file', file])];
    const binary = argv.shift() === 'python' ? python : node;
    const start = performance.now();
    const result = spawnSync(binary, argv, { encoding: 'utf8', maxBuffer: 64 * 1024 * 1024,
      timeout: 180000, env: { ...process.env, PATH: node.slice(0, node.lastIndexOf('/')) + ':' + process.env.PATH } });
    const durationSeconds = (performance.now() - start) / 1000;
    const log = report + 'logs/final-' + gate.id + '.log';
    fs.writeFileSync(log, (result.stdout || '') + (result.stderr || '') + (result.error ? '\n' + result.error.message : ''), { mode: 0o600 });
    const status = result.status === 0 && !result.error ? 'PASS' : 'FAIL';
    executed.push({ id: gate.id, level: gate.level, status, durationSeconds, evidence: log });
    write('validation-results.json', executed);
    console.log(gate.id, status, 'exit=' + result.status, durationSeconds.toFixed(2) + 's');
  }
  const receipt = { schemaVersion: 2, changeSummary: plan.changeSummary, changedFiles: plan.changedFiles,
    plannedLevel: plan.requiredLevel, actualLevel: plan.requiredLevel, components: plan.components,
    platforms: plan.platforms, impact: plan.impact, executed,
    external: plan.ci.map(gate => ({ id: gate.id, status: 'NOT_RUN', evidence: report + 'BLOCKED.md' })),
    realMachine: plan.realMachine.map(gate => ({ id: gate.id, status: 'NOT_RUN', evidence: report + 'BLOCKED.md' })),
    result: executed.some(gate => gate.status === 'FAIL') ? 'FAIL' : 'BLOCKED', mergeReady: false, releaseReady: false,
    uncoveredRisks: [...new Set([...plan.uncoveredRisks, ...plan.ci.map(gate => 'external_gate_not_run:' + gate.id), 'browser_live_not_run', 'clean_install_not_run', 'model_live_not_run'])],
    escalation: executed.some(gate => gate.status === 'FAIL')
      ? { required: true, targetLevel: plan.requiredLevel, reasons: ['validation_failure'] }
      : { required: false, targetLevel: null, reasons: [] } };
  write('verification-receipt.json', receipt);
  console.log('receipt:', receipt.result, 'mergeReady=false releaseReady=false');
} catch (error) {
  console.error('final verification failed:', error.message);
  process.exitCode = 1;
}
