import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';

const workflow = fs.readFileSync(
  new URL('../../.github/workflows/research-web-tabbit.yml', import.meta.url),
  'utf8',
);

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

test('Tabbit verification is manual-only while automatic CI is paused', () => {
  assert.deepEqual(workflowTriggers(workflow), ['workflow_dispatch']);
});
