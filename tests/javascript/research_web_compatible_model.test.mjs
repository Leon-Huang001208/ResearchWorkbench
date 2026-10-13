import test from 'node:test';
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { createRequire } from 'node:module';
import { mkdtemp, readFile, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';
import { streamCompletion } from '../../app/research_web/runtime/compatible-model.mjs';

async function endpoint(t, handle) {
  const server = createServer(handle);
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  t.after(() => { server.closeAllConnections(); server.close(); });
  return `http://127.0.0.1:${server.address().port}/v1`;
}
const frame = value => `data: ${JSON.stringify(value)}\n\n`;
const response = text => frame({ choices: [{ index: 0, delta: { content: text }, finish_reason: null }] }) + frame({ choices: [{ index: 0, delta: {}, finish_reason: 'stop' }] }) + 'data: [DONE]\n\n';
const connection = base_url => ({ provider: 'openai-compatible', protocol: 'openai-completions', model: 'local-test', base_url, credential_mode: 'none' });
const request = { model: 'local-test', messages: [{ role: 'user', content: [{ type: 'text', text: '合成测试' }] }] };
const collect = async iterable => { const chunks = []; for await (const chunk of iterable) chunks.push(chunk); return chunks; };

test('keyless transport emits final native text without consulting credentials', async t => {
  let calls = 0;
  const url = await endpoint(t, async (req, res) => {
    calls++;
    assert.equal(req.url, '/v1/chat/completions');
    assert.equal(req.headers.authorization, undefined);
    assert.equal(req.headers['x-research-data-key'], undefined);
    assert.equal(req.headers['x-native-attribution'], 'fixture');
    let body = ''; for await (const part of req) body += part;
    const value = JSON.parse(body);
    assert.equal(value.model, 'local-test');
    assert.equal(value.stream, true);
    assert.equal(value.tools, undefined);
    res.setHeader('Content-Type', 'text/event-stream'); res.end(response('合成完成'));
  });
  const chunks = await collect(streamCompletion(connection(url), request, { attributionHeaders: () => ({ 'X-Native-Attribution': 'fixture' }), resolveKey: () => { throw Error('credential must not be inherited'); } }));
  assert.equal(calls, 1);
  assert.deepEqual(chunks.at(-1), { type: 'finish', reason: { kind: 'stop' } });
  assert.equal(chunks.find(c => c.type === 'block-end').block.text, '合成完成');
});

test('redirect never forwards the prompt or authentication to another endpoint', async t => {
  let forwarded = 0;
  const target = await endpoint(t, (_req, res) => { forwarded++; res.end(response('不可到达')); });
  const origin = await endpoint(t, (_req, res) => { res.writeHead(307, { Location: target }); res.end(); });
  await assert.rejects(collect(streamCompletion({ ...connection(origin), credential_mode: 'api_key' }, request, { resolveKey: async () => 'synthetic-fixture-value' })), /compatible_http_failed/);
  assert.equal(forwarded, 0);
});

test('HTTP 200 with an unfinished stream is not a successful generation', async t => {
  const url = await endpoint(t, (_req, res) => { res.setHeader('Content-Type', 'text/event-stream'); res.end(frame({ choices: [{ index: 0, delta: { content: '只有部分' }, finish_reason: null }] })); });
  await assert.rejects(collect(streamCompletion(connection(url), request)), /compatible_stream_incomplete/);
});

test('missing authentication fails before a request and cannot use ambient values', async t => {
  let calls = 0;
  const url = await endpoint(t, (_req, res) => { calls++; res.end(response('不可到达')); });
  await assert.rejects(collect(streamCompletion({ ...connection(url), credential_mode: 'api_key' }, request, { resolveKey: async () => undefined })), /compatible_credentials_missing/);
  assert.equal(calls, 0);
});

test('adapter rejects stale keyless prepared generation after settings change', async t => {
  const { createAdapter } = await import('../../app/research_web/runtime/compatible-model.mjs');
  const first = await endpoint(t, (req, res) => {
    assert.equal(req.headers['x-native-attribution'], 'fixture');
    res.setHeader('Content-Type', 'text/event-stream'); res.end(response('原快照'));
  });
  let current = connection(first);
  const adapter = createAdapter(class {}, { readConnection: async () => current, attributionHeaders: () => ({ 'X-Native-Attribution': 'fixture' }) });
  const call = await adapter.prepareCall('openai-compatible', 'local-test');
  current = connection('http://127.0.0.1:9/v1');
  await assert.rejects(collect(call.stream(request)), /compatible_connection_changed/);
  assert.equal(adapter.providerRetryPolicy().maxRetries, 0);
});

test('a prepared authenticated call cannot send a new generation key to its old endpoint', async () => {
  const { createAdapter } = await import('../../app/research_web/runtime/compatible-model.mjs');
  let current = { ...connection('http://127.0.0.1:1234/v1'), credential_mode: 'api_key', revision: 'a'.repeat(32) };
  let key = 'synthetic-generation-a';
  let requests = 0;
  const adapter = createAdapter(class {}, {
    readConnection: async () => current,
    resolveKey: async () => key,
    fetch: async () => { requests++; return new Response(response('不能到达'), { headers: { 'content-type': 'text/event-stream' } }); },
  });
  const prepared = await adapter.prepareCall('openai-compatible', 'local-test');
  current = { ...current, base_url: 'http://127.0.0.1:1235/v1', revision: 'b'.repeat(32) };
  key = 'synthetic-generation-b';
  await assert.rejects(collect(prepared.stream(request)), /compatible_connection_changed/);
  assert.equal(requests, 0);
});

test('cancellation after a buffered text delta cannot emit success finish', async () => {
  const abort = new AbortController();
  const chunks = [];
  await assert.rejects((async () => {
    for await (const chunk of streamCompletion(connection('http://127.0.0.1:1234/v1'), { ...request, signal: abort.signal }, {
      fetch: async () => new Response(response('合成取消'), { headers: { 'content-type': 'text/event-stream' } }),
    })) {
      chunks.push(chunk);
      if (chunk.type === 'text-delta') abort.abort();
    }
  })(), /compatible_generation_cancelled/);
  assert.equal(chunks.some(chunk => chunk.type === 'finish'), false);
});


test('credential resolution that crosses a configuration generation fails before dispatch', async () => {
  const { createAdapter } = await import('../../app/research_web/runtime/compatible-model.mjs');
  let current = { ...connection('http://127.0.0.1:1234/v1'), credential_mode: 'api_key', revision: 'a'.repeat(32) };
  const adapter = createAdapter(class {}, {
    readConnection: async () => current,
    resolveKey: async () => { current = { ...current, revision: 'b'.repeat(32) }; return 'synthetic-new-generation'; },
  });
  await assert.rejects(adapter.prepareCall('openai-compatible', 'local-test'), /compatible_connection_changed/);
});

test('reasoning stream emits a thinking block before the answer text with usage', async t => {
  const url = await endpoint(t, (_req, res) => {
    res.setHeader('Content-Type', 'text/event-stream');
    res.end(
      frame({ choices: [{ index: 0, delta: { reasoning_content: '先想' }, finish_reason: null }] }) +
      frame({ choices: [{ index: 0, delta: { reasoning_content: '再想' }, finish_reason: null }] }) +
      frame({ choices: [{ index: 0, delta: { content: '答' }, finish_reason: null }] }) +
      frame({ choices: [{ index: 0, delta: {}, finish_reason: 'stop' }], usage: { prompt_tokens: 10, completion_tokens: 5, total_tokens: 15 } }) +
      'data: [DONE]\n\n'
    );
  });
  const chunks = await collect(streamCompletion(connection(url), request));
  assert.deepEqual(chunks[0], { type: 'block-start', index: 0, blockType: 'reasoning' });
  assert.deepEqual(chunks[1], { type: 'reasoning-delta', index: 0, text: '先想' });
  assert.equal(chunks.find(c => c.type === 'block-end' && c.block.type === 'reasoning').block.text, '先想再想');
  assert.equal(chunks.find(c => c.type === 'block-start' && c.blockType === 'text').index, 1);
  assert.deepEqual(chunks.find(c => c.type === 'usage'), { type: 'usage', usage: { inputTokens: 10, outputTokens: 5, totalTokens: 15 } });
  assert.deepEqual(chunks.at(-1), { type: 'finish', reason: { kind: 'stop' } });
});

test('output budget exhausted by reasoning without answer text is an incomplete stream', async t => {
  const url = await endpoint(t, (_req, res) => {
    res.setHeader('Content-Type', 'text/event-stream');
    res.end(
      frame({ choices: [{ index: 0, delta: { reasoning_content: '只想不答' }, finish_reason: null }] }) +
      frame({ choices: [{ index: 0, delta: {}, finish_reason: 'length' }] }) +
      'data: [DONE]\n\n'
    );
  });
  await assert.rejects(collect(streamCompletion(connection(url), request)), /compatible_stream_incomplete/);
});

test('default output budget leaves headroom for reasoning models and respects explicit values', async t => {
  const seen = [];
  const url = await endpoint(t, async (req, res) => {
    let body = ''; for await (const part of req) body += part;
    seen.push(JSON.parse(body).max_tokens);
    res.setHeader('Content-Type', 'text/event-stream'); res.end(response('好'));
  });
  await collect(streamCompletion(connection(url), request));
  await collect(streamCompletion(connection(url), { ...request, maxTokens: 2048 }));
  assert.deepEqual(seen, [16384, 2048]);
});

test('tool-call streams become native tool-call blocks with a tool-calls finish', async t => {
  let body;
  const url = await endpoint(t, async (req, res) => {
    let rawBody = ''; for await (const part of req) rawBody += part;
    body = JSON.parse(rawBody);
    res.setHeader('Content-Type', 'text/event-stream');
    res.end(
      frame({ choices: [{ index: 0, delta: { tool_calls: [{ index: 0, id: 'call_1', type: 'function', function: { name: 'web_search', arguments: '' } }] }, finish_reason: null }] }) +
      frame({ choices: [{ index: 0, delta: { tool_calls: [{ index: 0, function: { arguments: '{"query":"' } }] }, finish_reason: null }] }) +
      frame({ choices: [{ index: 0, delta: { tool_calls: [{ index: 0, function: { arguments: '消费"}' } }] }, finish_reason: null }] }) +
      frame({ choices: [{ index: 0, delta: {}, finish_reason: 'tool_calls' }], usage: { prompt_tokens: 8, completion_tokens: 4, total_tokens: 12 } }) +
      'data: [DONE]\n\n'
    );
  });
  const tools = [{ name: 'web_search', description: '检索网页', parameters: { type: 'object', properties: {} } }];
  const chunks = await collect(streamCompletion(connection(url), { ...request, tools }));
  assert.deepEqual(body.tools, [{ type: 'function', function: { name: 'web_search', description: '检索网页', parameters: { type: 'object', properties: {} } } }]);
  assert.deepEqual(chunks[0], { type: 'block-start', index: 0, blockType: 'tool-call' });
  const deltas = chunks.filter(c => c.type === 'tool-call-delta');
  assert.equal(deltas[0].name, 'web_search');
  assert.equal(deltas.map(c => c.argumentsDelta).join(''), '{"query":"消费"}');
  assert.deepEqual(chunks.find(c => c.type === 'block-end').block, { type: 'tool-call', id: 'call_1', name: 'web_search', arguments: '{"query":"消费"}' });
  assert.deepEqual(chunks.at(-1), { type: 'finish', reason: { kind: 'tool-calls' } });
});

test('assistant tool-call history and tool results map to the OpenAI wire shape', async t => {
  let body;
  const url = await endpoint(t, async (req, res) => {
    let rawBody = ''; for await (const part of req) rawBody += part;
    body = JSON.parse(rawBody);
    res.setHeader('Content-Type', 'text/event-stream'); res.end(response('继续'));
  });
  await collect(streamCompletion(connection(url), {
    model: 'local-test',
    messages: [
      { role: 'user', content: [{ type: 'text', text: '查一下' }] },
      { role: 'assistant', content: [{ type: 'reasoning', text: '想' }, { type: 'tool-call', id: 'call_1', name: 'web_search', arguments: '{"query":"消费"}' }] },
      { role: 'tool', toolCallId: 'call_1', content: [{ type: 'text', text: '结果文本' }] },
    ],
  }));
  assert.deepEqual(body.messages, [
    { role: 'user', content: '查一下' },
    { role: 'assistant', content: '', tool_calls: [{ id: 'call_1', type: 'function', function: { name: 'web_search', arguments: '{"query":"消费"}' } }] },
    { role: 'tool', tool_call_id: 'call_1', content: '结果文本' },
  ]);
});

test('requests past the former 256 KiB guard reach the route unchanged', async t => {
  let received = 0;
  const url = await endpoint(t, async (req, res) => {
    let body = ''; for await (const part of req) body += part;
    received = Buffer.byteLength(body);
    res.setHeader('Content-Type', 'text/event-stream'); res.end(response('已送达'));
  });
  const chunks = await collect(streamCompletion(connection(url), {
    model: 'local-test',
    messages: [{ role: 'user', content: [{ type: 'text', text: 'x'.repeat(300000) }] }],
  }));
  assert.ok(received > 262144, `expected the route to receive the larger body, saw ${received}`);
  assert.deepEqual(chunks.at(-1), { type: 'finish', reason: { kind: 'stop' } });
});

test('a body past the pathological guard fails before any dispatch', async t => {
  let calls = 0;
  const url = await endpoint(t, async (_req, res) => {
    calls += 1;
    res.setHeader('Content-Type', 'text/event-stream'); res.end(response('never'));
  });
  const huge = {
    model: 'local-test',
    messages: [{ role: 'user', content: [{ type: 'text', text: 'x'.repeat(4.5 * 1024 * 1024) }] }],
  };
  await assert.rejects(collect(streamCompletion(connection(url), huge)), /compatible_request_too_large/);
  assert.equal(calls, 0);
});

test('reasoning closes before the first tool block even with no answer text', async () => {
  const wire = frame({ choices: [{ index: 0, delta: { reasoning_content: '检查资料' }, finish_reason: null }] }) +
    frame({ choices: [{ index: 0, delta: { tool_calls: [{ index: 0, id: 'call_1', type: 'function', function: { name: 'web_search', arguments: '{}' } }] }, finish_reason: null }] }) +
    frame({ choices: [{ index: 0, delta: {}, finish_reason: 'tool_calls' }] }) + 'data: [DONE]\n\n';
  const stream = streamCompletion(connection('http://127.0.0.1:1234/v1'), request, {
    fetch: async () => new Response(wire, { headers: { 'content-type': 'text/event-stream' } }),
  });
  assert.equal((await stream.next()).value.blockType, 'reasoning');
  assert.equal((await stream.next()).value.type, 'reasoning-delta');
  assert.deepEqual((await stream.next()).value, { type: 'block-end', index: 0, block: { type: 'reasoning', text: '检查资料' } });
  assert.deepEqual((await stream.next()).value, { type: 'block-start', index: 1, blockType: 'tool-call' });
  const tail = await collect(stream);
  assert.equal(tail.filter(chunk => chunk.type === 'block-end' && chunk.block.type === 'reasoning').length, 0);
  assert.deepEqual(tail.at(-1), { type: 'finish', reason: { kind: 'tool-calls' } });
});

test('reasoning after a tool block and cancellation at its boundary fail closed', async () => {
  const thought = frame({ choices: [{ index: 0, delta: { reasoning_content: '想' }, finish_reason: null }] });
  const tool = frame({ choices: [{ index: 0, delta: { tool_calls: [{ index: 0, id: 'call_1', function: { name: 'web_search', arguments: '{}' } }] }, finish_reason: null }] });
  const fetchWire = wire => async () => new Response(wire, { headers: { 'content-type': 'text/event-stream' } });
  await assert.rejects(collect(streamCompletion(connection('http://127.0.0.1:1234/v1'), request, { fetch: fetchWire(thought + tool + thought) })), /compatible_stream_invalid/);
  const abort = new AbortController();
  const chunks = [];
  await assert.rejects((async () => {
    for await (const chunk of streamCompletion(connection('http://127.0.0.1:1234/v1'), { ...request, signal: abort.signal }, { fetch: fetchWire(thought + tool) })) {
      chunks.push(chunk);
      if (chunk.type === 'block-end') abort.abort();
    }
  })(), /compatible_generation_cancelled/);
  assert.equal(chunks.some(chunk => chunk.blockType === 'tool-call' || chunk.type === 'finish'), false);
});

test('resolved metadata exposes the fixed DSH nested context with conservative default and explicit override', async () => {
  const { createAdapter } = await import('../../app/research_web/runtime/compatible-model.mjs');
  for (const [configured, expected] of [[undefined, 32768], [131072, 131072]]) {
    const adapter = createAdapter(class {}, { contextWindow: configured, readConnection: async () => connection('http://127.0.0.1:1234/v1') });
    assert.deepEqual((await adapter.resolveModel('openai-compatible', 'local-test')).context, { contextWindow: expected });
    assert.deepEqual((await adapter.prepareCall('openai-compatible', 'local-test')).model.context, { contextWindow: expected });
  }
  assert.throws(() => createAdapter(class {}, { contextWindow: 0 }), /compatible_context_invalid/);
});

test('fixed DSH Loader exposes isolated compaction and pruning on the research preset realm', { skip: !process.env.DSH_SOURCE_ROOT }, async t => {
  const source = process.env.DSH_SOURCE_ROOT;
  const require = createRequire(join(source, 'packages/compaction/compaction-basic/package.json'));
  const load = async name => import(pathToFileURL(require.resolve(name)).href);
  const { Context } = await load('@deepseek-ai/cordis');
  const { default: Loader, Group } = await load('@deepseek-ai/cordis-plugin-loader');
  const { default: Include } = await load('@deepseek-ai/cordis-plugin-include');
  const modules = new Map();
  for (const name of ['llm', 'session', 'session-projection', 'token-meter', 'compaction-basic', 'compaction-tool-result-pruner']) {
    const module = await load(`@deepseek-ai/dsh-${name}`);
    modules.set(`@deepseek-ai/dsh-${name}`, module.default ?? module);
  }
  modules.set('@deepseek-ai/dsh-command-compact', await import(pathToFileURL(join(source, 'packages/compaction/command-compact/lib/index.js')).href));
  const directory = await mkdtemp(join(tmpdir(), 'rwb-preset-compaction-'));
  const ctx = new Context();
  t.after(async () => { await ctx.fiber.dispose(); await rm(directory, { recursive: true }); });
  ctx.baseUrl = pathToFileURL(directory).href + '/';
  await ctx.plugin(Loader);
  ctx.loader.builtins.include = Include;
  ctx.loader.builtins.group = Group;
  ctx.loader.internal = { version: 'v2', async import(name) {
    if (!modules.has(name)) throw Error('unexpected_fixture_module');
    return modules.get(name);
  } };
  const preset = await readFile(new URL('../../app/research_web/runtime/research.cordis.yml', import.meta.url), 'utf8');
  const compaction = preset.slice(preset.indexOf('- id: compaction\n'));
  const config = join(directory, 'cordis.yml');
  // Dependencies remain in the parent realm, exactly as in the shipped preset.
  await writeFile(config, ['llm', 'session', 'session-projection', 'token-meter'].map(name => `- name: '@deepseek-ai/dsh-${name}'\n`).join('') + compaction);
  await ctx.loader.create({ name: 'cordis:include', config: { path: pathToFileURL(config).href } });
  await ctx.loader.await();
  const group = [...ctx.loader.entries()].find(entry => entry.options.name === 'cordis:group');
  assert.ok(group, 'preset group must load');
  assert.ok(group.ctx.get('compaction'), 'group realm needs the engine');
  assert.ok(group.ctx.get('toolResultPruner'), 'group realm needs the pruner');
  assert.equal(ctx.get('compaction'), undefined, 'engine stays isolated from parent');
  assert.equal(ctx.get('toolResultPruner'), undefined, 'pruner stays isolated from parent');
  const { LlmAdapter } = await load('@deepseek-ai/dsh-llm');
  const { createAdapter } = await import('../../app/research_web/runtime/compatible-model.mjs');
  const adapter = createAdapter(LlmAdapter, { readConnection: async () => connection('http://127.0.0.1:1234/v1') });
  ctx.llm.registerAdapter(['openai-compatible'], adapter);
  assert.deepEqual((await ctx.llm.resolveModelInfo('openai-compatible', 'local-test')).context, { contextWindow: 32768 });
});
