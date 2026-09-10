import test from 'node:test';
import assert from 'node:assert/strict';
import { chmod, mkdir, mkdtemp, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';

import { apply } from '../../app/research_web/runtime/mcp-adapter.mjs';

async function fixture() {
  const root = await mkdtemp(join(tmpdir(), 'rwb-mcp-adapter-'));
  const control = join(root, '.control');
  await mkdir(control, { mode: 0o700 });
  await writeFile(
    join(control, 'mcp-runtime.json'),
    JSON.stringify({ url: 'http://127.0.0.1:8088', token: 'a'.repeat(43) }),
    { mode: 0o600 },
  );
  await chmod(control, 0o700);
  return root;
}

function binding(overrides = {}) {
  return {
    name: 'mcp__mcp-installation-0123456789abcdef0123456789abcdef__read_filing',
    installation_id: 'mcp-installation-0123456789abcdef0123456789abcdef',
    version: '1.2.3',
    tool_name: 'read_filing',
    schema_sha256: 'b'.repeat(64),
    description: 'Read one filing',
    input_schema: { type: 'object', properties: { code: { type: 'string' } }, required: ['code'], additionalProperties: false },
    ...overrides,
  };
}

test('MCP adapter registers only exact verified bindings and proxies without logging arguments', async () => {
  const root = await fixture();
  const registrations = [];
  const logs = [];
  const ctx = {
    tools: { register: item => registrations.push(item) },
    logger: { info: (...args) => logs.push(args), warn: (...args) => logs.push(args) },
  };
  apply(ctx, { researchRoot: root, bindings: [binding()] });
  assert.equal(registrations.length, 1);
  assert.equal(registrations[0].name, binding().name);
  assert.deepEqual(registrations[0].parameters, binding().input_schema);

  const previousFetch = globalThis.fetch;
  let request;
  globalThis.fetch = async (url, options) => {
    request = { url, options };
    return new Response(JSON.stringify({ status: 'complete', result: { content: [{ type: 'text', text: 'ok' }] } }), {
      status: 200,
      headers: { 'content-type': 'application/json', 'content-length': '83' },
    });
  };
  try {
    const result = await registrations[0].execute(
      { code: '600000' },
      {
        signal: new AbortController().signal,
        callId: 'call-1',
        agent: { session: { header: { id: 'native-session-1' } } },
        cwd: root,
      },
    );
    assert.equal(result.result_json, JSON.stringify({ content: [{ type: 'text', text: 'ok' }] }));
  } finally {
    globalThis.fetch = previousFetch;
  }
  assert.equal(request.url, 'http://127.0.0.1:8088/api/research/internal/mcp/tools/call');
  assert.equal(request.options.redirect, 'error');
  assert.equal(request.options.credentials, 'omit');
  assert.equal(request.options.headers['X-Research-MCP-Key'], 'a'.repeat(43));
  const body = JSON.parse(request.options.body);
  assert.deepEqual(body.arguments, { code: '600000' });
  assert.equal(body.schema_sha256, 'b'.repeat(64));
  assert.ok(logs.every(parts => !parts.join(' ').includes('600000')));
});

test('MCP adapter rejects duplicate, malformed and schema-mismatched bindings before registration', () => {
  const ctx = { tools: { register() {} }, logger: { info() {}, warn() {} } };
  assert.throws(() => apply(ctx, { researchRoot: '/tmp', bindings: [binding(), binding()] }), /duplicate/i);
  assert.throws(() => apply(ctx, { researchRoot: '/tmp', bindings: [binding({ name: 'mcp__prefix' })] }), /invalid/i);
  assert.throws(() => apply(ctx, { researchRoot: '/tmp', bindings: [binding({ schema_sha256: 'bad' })] }), /invalid/i);
});

test('MCP adapter is inert without bindings and does not require a control secret', () => {
  let registrations = 0;
  apply(
    { tools: { register() { registrations += 1; } }, logger: { info() {}, warn() {} } },
    { researchRoot: '/path/that/does/not/exist', bindings: [] },
  );
  assert.equal(registrations, 0);
});
