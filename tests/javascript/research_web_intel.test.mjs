import assert from 'node:assert/strict';
import test from 'node:test';
import { parseRoute } from '../../app/research_web/ui/core.mjs';
import { renderPrimaryRail } from '../../app/research_web/ui/shell.mjs';
import { createIntelController, renderIntel, intelTabs, validStockCode, intelURL, filterIntelEvents, filterIntelPosts } from '../../app/research_web/ui/intel.mjs';
const response = data => ({ ok: true, json: async () => data });
const overview = { reading: Array.from({ length: 45 }, (_, i) => ({ id: `e${i}`, title: `资讯${i}`, groups: ['ai'], revision: i % 3 })), logics: [{ id: 'ai', name: 'AI' }], trading: [], potential: [], challenges: [{ id: 'e0' }] };

test('eight native routes and active navigation', () => {
  for (const [tab] of intelTabs) assert.equal(parseRoute(`#/intel/${tab}`).intelTab, tab);
  for (const hash of ['#/intel', '#/intel/unknown', '#/intel/news/extra']) assert.equal(parseRoute(hash).intelTab, 'overview');
  assert.match(renderPrimaryRail({ page: 'intel' }), /href="#\/intel\/overview" class="rail-link active"/);
  assert.equal(parseRoute('#/fingpt').page, 'fingpt');
});

test('lazy tab loads, read-only refresh, pagination and cursor deduplication', async () => {
  const calls = [];
  const c = createIntelController({ fetcher: async path => {
    calls.push(path);
    if (path.includes('overview')) return response(overview);
    if (path.includes('reports')) return response({ items: [{ id: 'r1', title: '报告' }], total: 100 });
    if (path.includes('wsc')) return response({ items: [{ id: 'w1', title: '快讯' }], next_cursor: 'abc+123', has_more: true });
    return response({ stories: [] });
  } });
  assert.equal(calls.length, 0);
  await c.activate('overview');
  assert.equal(calls.length, 3);
  assert.equal((renderIntel(c.state).match(/data-intel-action="event"/g) || []).length, 21);
  c.state.limit += 20;
  assert.equal((renderIntel(c.state).match(/data-intel-action="event"/g) || []).length, 41);
  c.state.query = 'previous-filter';
  await c.activate('events'); assert.equal(calls.length, 3); assert.equal(c.state.query, '');
  await c.activate('overview'); assert.equal(calls.length, 3);
  await c.activate('research-reports');
  c.state.entries['research-reports'].offset = 20; await c.load();
  assert.ok(calls.some(path => path.endsWith('reports?limit=20&offset=20')));
  await c.activate('wsc'); await c.load({ more: true });
  assert.equal(c.state.entries.wsc.data.items.length, 1);
  assert.ok(calls.some(path => path.includes('wsc?cursor=abc%2B123')));
  assert.ok(calls.every(path => !/refresh|explain|feedback/.test(path)));
});

test('event and social filters match declared fields', () => {
  assert.equal(filterIntelEvents([{ title: 'AI 需求', groups: ['ai'], _counter: true }, { title: '矿业', groups: ['mining'] }], { query: 'ai', group: 'ai', category: 'counter' }).length, 1);
  assert.equal(filterIntelPosts([{ platform: 'x', account_id: 1, text: 'AI', author: '研究员' }, { platform: 'wechat', account_id: 2, text: '行业' }], { platform: 'x', account: '1', query: '研究' }).length, 1);
  assert.ok(validStockCode('600519')); assert.ok(!validStockCode('60051')); assert.ok(!validStockCode('abcdef'));
});

test('cancellation prevents late response and details from replacing a new tab', async () => {
  let resolveMain; let resolveDetail; let signal;
  const c = createIntelController({ fetcher: async (path, options) => {
    if (path.endsWith('/radar')) { signal = options.signal; return new Promise(resolve => { resolveMain = resolve; }); }
    if (path.includes('/events/')) return new Promise(resolve => { resolveDetail = resolve; });
    return response({ accounts: [], posts: [] });
  } });
  const pending = c.activate('investment-news');
  await c.activate('social'); assert.ok(signal.aborted);
  resolveMain(response({ industries: [{ key: 'late' }] })); await pending;
  assert.equal(c.state.tab, 'social'); assert.equal(c.state.entries['investment-news'].data, null);
  const detail = c.openDetail('event', 'e1');
  await c.activate('events'); resolveDetail(response({ event: { title: 'late' } })); await detail;
  assert.equal(c.state.detail, null); assert.equal(c.state.detailLoading, false);
});

test('errors are independent, retry succeeds, and external content never becomes HTML', async () => {
  let broken = true;
  const c = createIntelController({ fetcher: async () => broken ? { ok: false, json: async () => ({ detail: { message: '读取超时' } }) } : response({ items: [], has_more: false }) });
  await c.activate('wsc'); assert.match(renderIntel(c.state), /读取超时/);
  broken = false; await c.load(); assert.equal(c.state.entries.wsc.error, ''); assert.match(renderIntel(c.state), /暂无见闻快讯/);
  c.state.entries.wsc.data.items = [{ title: '<img src=x onerror=alert(1)>', content: '<script>bad</script>', url: 'javascript:alert(1)' }];
  const html = renderIntel(c.state);
  assert.match(html, /&lt;script&gt;/); assert.doesNotMatch(html, /<img src=x|href="javascript:/);
  assert.equal(intelURL('//evil.com'), null); assert.equal(intelURL('/api/private'), null);
  assert.equal(intelURL('https://example.com/article'), 'https://example.com/article');
});


test('detail repeat requests cannot clear the newer loading state, and report links stay remote', async () => {
  const pending = [];
  const c = createIntelController({ fetcher: async () => new Promise(resolve => pending.push(resolve)) });
  c.state.tab = 'research-reports';
  const first = c.openDetail('report', 'r1');
  const second = c.openDetail('report', 'r1');
  pending[0](response({ title: 'older' })); await first;
  assert.equal(c.state.detailLoading, true);
  pending[1](response({ title: 'newer', content: '[unsafe](/api/private) [source](https://example.com/article)' })); await second;
  assert.equal(c.state.detail.title, 'newer');
  const html = renderIntel(c.state);
  assert.doesNotMatch(html, /href="\/api\/private"/);
  assert.match(html, /href="https:\/\/example.com\/article"/);
});


test('report reader preserves structured existing analysis and original evidence', () => {
  const c = createIntelController();
  c.state.tab = 'research-reports'; c.state.detailKind = 'report'; c.state.detailId = 'r1';
  c.state.detail = { title: '研究报告', content: '完整原文', processing: { status: 'complete', sections: [{ title: '章节', status: 'complete', original: '章节原文', analysis: { summary: '已完成摘要', topics: ['产业'], points: [{ text: '观点', quote: '<原文证据>' }], risks: [{ text: '不确定性' }] } }] } };
  const html = renderIntel(c.state);
  for (const label of ['已完成摘要','产业','观点','&lt;原文证据&gt;','不确定性','完整原文','章节原文']) assert.ok(html.includes(label));
  assert.ok(!html.includes('[object Object]'));
});
