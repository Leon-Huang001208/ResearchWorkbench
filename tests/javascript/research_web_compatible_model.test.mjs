import test from 'node:test';
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
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
