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
const dataCatalog = await import(new URL('data-catalog.mjs', root));
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
  assert.deepEqual(core.parseRoute('#/history?mode=fingpt'), { page: 'history', sessionId: null, historyMode: 'fingpt', historyView: 'active' });
  assert.deepEqual(core.parseRoute('#/history?mode=claw&view=deleted'), { page: 'history', sessionId: null, historyMode: 'claw', historyView: 'deleted' });
  assert.deepEqual(core.parseRoute('#/history?mode=unknown&view=unknown'), { page: 'history', sessionId: null, historyMode: null, historyView: 'active' });
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

test('conversation distinguishes user and FinGPT messages without visible avatars or bylines', () => {
  const result = views.renderConversation(session('s1', { messages: [
    { role: 'user', text: '请分析现金流' },
    { role: 'assistant', text: '先看经营现金流。' },
  ] }));
  assert.match(result, /<article class="message user" aria-label="用户消息"><div class="markdown">/);
  assert.match(result, /<article class="message assistant" aria-label="FinGPT 回复"><div class="markdown">/);
  assert.doesNotMatch(result, /message-byline|class="avatar"|<strong>你<\/strong>|Research Workbench/);
});

test('conversation attributes assistant replies to the active research mode', () => {
  const assistant = [{ role: 'assistant', text: '真实回复' }];
  assert.match(views.renderConversation(session('fin', { mode: 'fingpt', messages: assistant })), /aria-label="FinGPT 回复"/);
  assert.match(views.renderConversation(session('claw', { mode: 'claw', messages: assistant })), /aria-label="Claw 回复"/);
  assert.match(views.renderConversation(session('other', { mode: 'other', messages: assistant })), /aria-label="助手回复"/);
});

test('entrypoint is self hosted and settings do not persist secrets in browser storage', async () => {
  const html = await readFile(new URL('index.html', root), 'utf8');
  const app = await readFile(new URL('app.mjs', root), 'utf8');
  assert.match(html, /type="module" src="\/static\/app.mjs"/);
  assert.doesNotMatch(html, /https:\/\/.*(?:script|stylesheet)/);
  assert.doesNotMatch(app, /localStorage|sessionStorage/);
  assert.match(app, /password/);
});

test('MySQL password references are cleared immediately after request serialization', async () => {
  const app = await readFile(new URL('app.mjs', root), 'utf8');
  const request = app.indexOf('api.saveMysqlConfiguration(payload)');
  const clearPayload = app.indexOf('delete payload.password', request);
  const awaitResult = app.indexOf('await controller.action', request);
  assert.ok(request >= 0 && clearPayload > request);
  assert.ok(clearPayload < awaitResult, 'payload must be cleared before waiting for the response');
  assert.match(app.slice(request, awaitResult), /values\.delete\('password'\)/);
  assert.match(app.slice(request, awaitResult), /password = ''/);
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

test('API exposes local MySQL configuration without a password read path', async () => {
  const calls=[];const api=core.createAPI({fetcher:async(url,options)=>{calls.push([url,options]);return new Response(JSON.stringify({configured:true,secret_configured:true}));},logger(){}});
  await api.mysqlConfiguration();
  await api.saveMysqlConfiguration({label:'因子库',host:'db.test',port:3306,user:'reader',charset:'gbk',tls_mode:'required_no_verify',password:'one-shot'});
  await api.deleteMysqlConfiguration();
  assert.deepEqual(calls.map(([url,options])=>[url,options.method]),[
    ['/api/research/data/sources/mysql/configuration','GET'],
    ['/api/research/data/sources/mysql/configuration','PUT'],
    ['/api/research/data/sources/mysql/configuration','DELETE'],
  ]);
  assert.equal(Object.hasOwn(JSON.parse(calls[0][1].body || '{}'),'password'),false);
});

test('MySQL source detail shows the four-stage local connection state and settings link', () => {
  const html=dataCatalog.renderDataSourceDetail({id:'mysql',name:'用户 MySQL 数据库',family:'datahub',source_type:'database',description:'本机配置',auth_type:'account',dependencies:['PyMySQL','keyring'],markets:['用户数据库'],bindings:[],readiness:{code_exists:true,integration_completed:true,configured:true,dependency_ready:true,allowed:true,callable:false,integration_state:'ready',health:'untested'}},false);
  for(const label of ['未配置','已保存','已检测','可调用']) assert.match(html,new RegExp(label));
  assert.match(html,/href="#\/settings"/);
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

test('native agent usage, duration and errors are visible without fake measurements', () => {
  const result = views.renderActivities({subagents: [{id:'child', name:'资料Agent', status:'failed', usage:{tokens:123}, duration_ms:2345, error:'<denied>', history_truncated:true}], activities:[{id:'t', title:'research_run_script', status:'completed', duration_ms:1200}]});
  assert.match(result, /123 tokens/);
  assert.match(result, /2\.3 秒/);
  assert.match(result, /1\.2 秒/);
  assert.match(result, /&lt;denied&gt;/);
  assert.match(result, /历史已截断/);
  assert.doesNotMatch(views.renderActivities({subagents:[{id:'unknown',status:'running'}]}), /0 tokens|0\.0 秒/);
});

test('dataset cards show real provenance, range and partial warning without claiming a snapshot is complete', () => {
  assert.equal(typeof views.renderDatasets, 'function');
  const result = views.renderDatasets('session-1', [{
    id: 'dataset-1', name: '<基金净值>', source: 'Eastmoney', source_url: 'https://fund.eastmoney.com/', status: 'partial',
    row_count: 20, requested_range: { start: '2024-01-01', end: '2024-12-31' }, actual_range: { start: '2024-01-02', end: '2024-12-30' },
    pagination_complete: true, pages_fetched: 2, provider_total: 21, retrieved_at: '2026-09-02T09:00:00+08:00', as_of: '2024-12-30',
    missing: ['2024-06-03'], limitations: ['供应商总量与唯一日期数不一致'], files: [{ name: 'rows.csv', sha256: 'a'.repeat(64) }],
  }, {
    id: 'dataset-2', name: '最新资讯', source: 'CLS', status: 'snapshot', row_count: 20, pagination_complete: true,
  }]);
  for (const expected of ['研究资料', '&lt;基金净值&gt;', 'Eastmoney', '请求范围', '实际范围', '20 条', '2 页', '供应商总量 21', '取数时间', '缺失：2024-06-03', '供应商总量与唯一日期数不一致', '资料不完整', '分页已结束，但资料仍不完整', '公开快照，不代表完整历史', '下载 CSV', '下载 JSON', '下载 manifest', 'a'.repeat(64)]) assert.match(result, new RegExp(expected));
  assert.match(result, /截至<\/dt><dd>2024-12-30/);
  assert.match(result, /href="https:\/\/fund\.eastmoney\.com\//);
  assert.doesNotMatch(result, /全量数据完整/);
});

test('dataset downloads only use the current session, safe dataset id and three fixed files', () => {
  assert.equal(typeof views.datasetFileURL, 'function');
  assert.equal(views.datasetFileURL('session-1', 'dataset-1', 'rows.csv'), '/api/research/sessions/session-1/datasets/dataset-1/files/rows.csv');
  for (const value of [
    views.datasetFileURL('session-1', 'dataset-1', 'rows.csv?download=1'),
    views.datasetFileURL('session-1', 'dataset-1', 'manifest.json#fragment'),
    views.datasetFileURL('session-1', 'dataset-1', 'other.txt'),
    views.datasetFileURL('session-1', 'dataset%2Fother', 'rows.json'),
    views.datasetFileURL('session/other', 'dataset-1', 'rows.json'),
  ]) assert.equal(value, null);
  const unsafe = views.renderDatasets('session-1', [{ id: '../dataset', name: '坏资料', source_url: 'javascript:alert(1)', files: [{ name: 'rows.csv', url: 'https://evil.test/download' }] }]);
  assert.doesNotMatch(unsafe, /evil\.test|javascript:|href="\/api\/research\/sessions/);
});
