import assert from 'node:assert/strict';
import test from 'node:test';
import { readFile } from 'node:fs/promises';

const root = new URL('../../app/research_web/ui/', import.meta.url);
const modules = await Promise.all(['markdown.mjs', 'core.mjs', 'views.mjs'].map(async (file) => {
  try { return await import(new URL(file, root)); } catch (error) {
    if (error.code === 'ERR_MODULE_NOT_FOUND') return {};
    throw error;
  }
}));
const [markdown, core, views] = modules;
const session = (id = 's1', extra = {}) => ({ id, title: '真实会话', mode: 'fingpt', status: 'idle', messages: [], activities: [], subagents: [], files: [], approvals: [], questions: [], ...extra });

test('Markdown renders real headings, paragraphs, code, lists, tables and source links', () => {
  assert.equal(typeof markdown.renderMarkdown, 'function');
  const result = markdown.renderMarkdown('# 研究\n\n**利润** 与 `cash`\n\n- 第一\n- 第二\n\n```python\nx < 2\n```\n\n[来源](https://example.com/report)\n\n| 项目 | 值 |\n| --- | --- |\n| 收入 | 10 |');
  for (const expected of ['<h1>研究</h1>', '<strong>利润</strong>', '<code>cash</code>', '<ul>', '<li>第二</li>', '<pre>', 'x &lt; 2', 'rel="noopener noreferrer"', '<table>', '<td>收入</td>']) assert.ok(result.includes(expected), expected);
});

test('Markdown treats HTML as text and refuses active or credential URLs', () => {
  assert.equal(typeof markdown.renderMarkdown, 'function');
  const result = markdown.renderMarkdown('<img src=x onerror=alert(1)>\n\n[x](javascript:alert) [x](data:text/html,test) [x](https://u:p@example.com)');
  assert.doesNotMatch(result, /<img|href="(?:javascript|data):|href="https:\/\/u:p/);
  assert.match(result, /&lt;img/);
  assert.equal(markdown.safeURL('//evil.test/x'), null);
  assert.equal(markdown.safeURL('/api/research/sessions/s/files/f'), '/api/research/sessions/s/files/f');
  assert.equal(markdown.safeURL('/\\evil.test'), null);
});

test('routing accepts only product routes and safely round trips session identifiers', () => {
  assert.equal(typeof core.parseRoute, 'function');
  assert.deepEqual(core.parseRoute('#/claw?session=a%2Fb'), { page: 'claw', sessionId: 'a/b' });
  assert.deepEqual(core.parseRoute('#/market'), { page: 'fingpt', sessionId: null });
  assert.equal(core.sessionHash(session('a/b')), '#/fingpt?session=a%2Fb');
});

test('API encodes paths, includes idempotency, and exposes structured errors without logging bodies', async () => {
  assert.equal(typeof core.createAPI, 'function');
  const calls = []; const logs = [];
  const api = core.createAPI({ fetcher: async (...args) => { calls.push(args); return new Response(JSON.stringify({ accepted: true }), { status: 202 }); }, logger: (...args) => logs.push(args) });
  await api.message('a/b', { text: 'private prompt' }, 'unique-key');
  assert.equal(calls[0][0], '/api/research/sessions/a%2Fb/messages');
  assert.equal(calls[0][1].headers['Idempotency-Key'], 'unique-key');
  assert.equal(calls[0][1].credentials, 'same-origin');
  assert.equal(logs.some((line) => JSON.stringify(line).includes('private prompt')), false);
  const bad = core.createAPI({ fetcher: async () => new Response(JSON.stringify({ error: { code: 'runtime_unavailable', message: 'DSH 尚未连接' } }), { status: 503 }), logger() {} });
  await assert.rejects(bad.runtime(), (error) => error.message === 'DSH 尚未连接' && error.code === 'runtime_unavailable');
});

test('API does not assume success for malformed responses or transport failures', async () => {
  assert.equal(typeof core.createAPI, 'function');
  const malformed = core.createAPI({ fetcher: async () => new Response('<html>proxy</html>'), logger() {} });
  await assert.rejects(malformed.sessions(), /响应格式/);
  const offline = core.createAPI({ fetcher: async () => { throw new TypeError('secret internal details'); }, logger() {} });
  await assert.rejects(offline.runtime(), /网络/);
});

test('controller preserves draft on failed sends and retries with the same idempotency key', async () => {
  assert.equal(typeof core.createController, 'function');
  const keys = []; let failures = 1;
  const api = { detail: async () => session(), sessions: async () => ({ items: [] }), message: async (_id, _body, key) => { keys.push(key); if (failures--) throw new Error('DSH 离线'); return { accepted: true }; } };
  const controller = core.createController({ api, makeID: () => 'stable-id' });
  await controller.open({ page: 'fingpt', sessionId: 's1' });
  controller.setDraft('真实问题');
  await controller.send();
  assert.equal(controller.state.draft, '真实问题');
  assert.match(controller.state.error, /DSH 离线/);
  await controller.send();
  assert.deepEqual(keys, ['stable-id', 'stable-id']);
  assert.equal(controller.state.draft, '');
  assert.equal(controller.state.detail.messages.length, 0, 'no fabricated assistant or optimistic message');
});

test('controller ignores stale session loads and SSE events after navigating away', async () => {
  assert.equal(typeof core.createController, 'function');
  let resolveFirst; const streams = [];
  const api = { detail: (id) => id === 'first' ? new Promise((resolve) => { resolveFirst = resolve; }) : Promise.resolve(session(id)), events: (id, handlers) => { streams.push({ id, handlers, closed: false }); const stream = streams.at(-1); return () => { stream.closed = true; }; } };
  const controller = core.createController({ api });
  const first = controller.open({ page: 'fingpt', sessionId: 'first' });
  await controller.open({ page: 'fingpt', sessionId: 'second' });
  resolveFirst(session('first')); await first;
  assert.equal(controller.state.detail.id, 'second');
  await controller.open({ page: 'history', sessionId: null });
  streams[0].handlers.snapshot(session('second', { title: 'stale' }));
  assert.equal(controller.state.detail, null);
  assert.equal(streams[0].closed, true);
});

test('reconnection reloads a snapshot without resubmitting messages', async () => {
  assert.equal(typeof core.createController, 'function');
  let handlers; let reads = 0; let sends = 0;
  const api = { detail: async () => { reads++; return session(); }, events: (_id, callbacks) => { handlers = callbacks; return () => {}; }, message: async () => { sends++; } };
  const controller = core.createController({ api });
  await controller.open({ page: 'fingpt', sessionId: 's1' });
  handlers.error('事件连接已断开');
  assert.match(controller.state.streamError, /断开/);
  await handlers.open();
  assert.equal(reads, 2); assert.equal(sends, 0);
  assert.equal(controller.state.streamError, '');
});

test('file previews only use scoped same-origin file endpoints and sandbox HTML', () => {
  assert.equal(typeof views.renderFiles, 'function');
  const result = views.renderFiles([{ id: '1', name: '<unsafe>.html', mime: 'text/html', size: 12, url: '/api/research/sessions/s/files/1', preview_url: '/api/research/sessions/s/files/1/preview' }], '1');
  assert.match(result, /sandbox=""/);
  assert.match(result, /&lt;unsafe&gt;/);
  assert.match(result, /download/);
  assert.doesNotMatch(views.renderFiles([{ id: 'x', name: 'bad', url: 'https://evil.test/file', preview_url: 'javascript:alert(1)' }], 'x'), /href="https:\/\/evil|<iframe/);
});

test('session view is honest when empty and safely renders activity, approvals and questions', () => {
  assert.equal(typeof views.renderConversation, 'function');
  const result = views.renderConversation(session('s1', { messages: [{ role: 'assistant', text: '**真实答案**' }], activities: [{ id: 'a', type: 'tool', title: '检索', status: 'running', detail: '<script>x</script>' }], approvals: [{ id: 'p', title: '运行命令', detail: '需要授权' }], questions: [{ id: 'q', text: '研究期间？' }] }));
  assert.match(result, /<strong>真实答案<\/strong>/);
  assert.match(result, /data-approval="p"/);
  assert.match(result, /研究期间/);
  assert.doesNotMatch(result, /<script>|Claim|Evidence|Quality Gate|4 \/ 6/);
  assert.match(views.renderConversation(session()), /尚无消息/);
});

test('entrypoint is self hosted and settings do not persist secrets in browser storage', async () => {
  const html = await readFile(new URL('index.html', root), 'utf8');
  const app = await readFile(new URL('app.mjs', root), 'utf8');
  assert.match(html, /type="module" src="\/static\/app.mjs"/);
  assert.doesNotMatch(html, /https:\/\/.*(?:script|stylesheet)/);
  assert.doesNotMatch(app, /localStorage|sessionStorage/);
  assert.match(app, /password/);
});

test('a stale refresh never overwrites a newer SSE snapshot', async () => {
  let handlers; let resolveRefresh; let reads = 0;
  const controller = core.createController({ api: {
    detail: async () => ++reads === 1 ? session() : new Promise((resolve) => { resolveRefresh = resolve; }),
    events: (_id, callbacks) => { handlers = callbacks; return () => {}; },
  } });
  await controller.open({ page: 'fingpt', sessionId: 's1' });
  const refresh = controller.refresh();
  handlers.snapshot(session('s1', { messages: [{ role: 'assistant', text: '最新输出' }] }));
  resolveRefresh(session()); await refresh;
  assert.equal(controller.state.detail.messages[0]?.text, '最新输出');
});

test('creation does not force navigation after the user has left the page', async () => {
  let resolveCreate; const navigations = [];
  const controller = core.createController({ api: { create: () => new Promise((resolve) => { resolveCreate = resolve; }) }, onNavigate: (hash) => navigations.push(hash) });
  controller.setDraft('保留的问题');
  const creation = controller.create('fingpt', 'w1');
  await controller.open({ page: 'settings', sessionId: null });
  resolveCreate(session()); await creation;
  assert.deepEqual(navigations, []);
});

test('upgrading opens a Claw session with the real returned draft without sending it', async () => {
  assert.equal(typeof core.createController({ api: {} }).upgrade, 'function');
  const navigations = []; let sends = 0;
  const controller = core.createController({ api: { detail: async (id) => session(id), upgrade: async () => session('claw1', { mode: 'claw', draft: '基于现有会话扩展研究' }), message: async () => { sends++; } }, onNavigate: (hash) => navigations.push(hash) });
  await controller.open({ page: 'fingpt', sessionId: 's1' });
  await controller.upgrade();
  await controller.open(core.parseRoute(navigations[0]));
  assert.equal(controller.state.draft, '基于现有会话扩展研究');
  assert.equal(sends, 0);
});

test('native file download route is accepted and traversal remains blocked', () => {
  assert.equal(views.fileURL('/api/research/sessions/s/files/f/download'), '/api/research/sessions/s/files/f/download');
  assert.equal(views.fileURL('/api/research/sessions/s/files/f/../../runtime'), null);
});

test('API uploads actual files as multipart and sends secrets only in configuration body', async () => {
  const calls = []; const logs = [];
  const api = core.createAPI({ fetcher: async (url, options) => { calls.push([url, options]); return new Response('{}'); }, logger: (...args) => logs.push(args) });
  const file = new File(['contents'], 'input.md', { type: 'text/markdown' });
  await api.upload('s1', [file]);
  assert.equal(calls[0][1].body.getAll('files')[0].name, 'input.md');
  assert.equal(calls[0][1].headers['Content-Type'], undefined);
  await api.configure({ provider: 'deepseek-official', model: 'deepseek-v4-flash', api_key: 'very-private' });
  assert.equal(JSON.parse(calls[1][1].body).api_key, 'very-private');
  assert.doesNotMatch(JSON.stringify(logs), /very-private|contents|input.md/);
});

test('SSE malformed payload reports errors and closing a stream releases it', () => {
  let source; const errors = []; const snapshots = [];
  class Source {
    constructor(url) { this.url = url; this.handlers = {}; source = this; }
    addEventListener(name, handler) { this.handlers[name] = handler; }
    close() { this.closed = true; }
  }
  const api = core.createAPI({ EventSourceClass: Source, logger() {} });
  const close = api.events('a/b', { error: (error) => errors.push(error), snapshot: (snapshot) => snapshots.push(snapshot), open() {} });
  assert.equal(source.url, '/api/research/sessions/a%2Fb/events');
  source.handlers.snapshot({ data: 'not json' });
  source.handlers.snapshot({ data: JSON.stringify(session()) });
  source.handlers.runtime_error({ data: JSON.stringify({ message: '真实运行失败' }) });
  assert.equal(snapshots.length, 1); assert.equal(errors.length, 2);
  assert.equal(errors[1], '真实运行失败');
  close(); assert.equal(source.closed, true);
});
