import test from 'node:test';
import assert from 'node:assert/strict';
import { createSessionSearch } from '../../app/research_web/ui/session-search.mjs';
import { renderGlobalResults, renderGlobalSearch } from '../../app/research_web/ui/shell.mjs';
import { createAPI } from '../../app/research_web/ui/core.mjs';

const deferred = () => { let resolve; const promise = new Promise(r => { resolve = r; }); return { promise, resolve }; };
const result = id => ({ source: 'native_dsh', items: [{ id, mode: 'claw', title: id, snippet: '原生正文片段' }], has_more: false });
const tick = () => new Promise(resolve => setImmediate(resolve));
test('native search serializes explicit queries and drops superseded or closed results', async () => {
  const first = deferred(), second = deferred(), calls = []; const timers = [];
  const c = createSessionSearch({ search: (q, mode) => { calls.push([q, mode]); return calls.length === 1 ? first.promise : second.promise; }, schedule: fn => { timers.push(fn); return fn; }, cancel() {} });
  c.update('甲', 'claw'); timers.shift()(); c.update('乙', 'claw'); timers.shift()();
  assert.equal(calls.length, 1); first.resolve(result('old')); await tick();
  assert.deepEqual(calls, [['甲', 'claw'], ['乙', 'claw']]); assert.deepEqual(c.state.items, []);
  c.close(); second.resolve(result('late')); await tick(); assert.deepEqual(c.state.items, []); assert.equal(c.state.pending, false);
});
test('invalid keywords and other modules never send a native read', () => {
  let calls = 0; const c = createSessionSearch({ search: async () => { calls++; }, schedule: fn => { fn(); return null; } });
  c.update('', 'claw'); c.update('a'.repeat(501), 'claw'); assert.match(c.state.error, /500/);
  c.update('含\0空字符', 'claw'); assert.match(c.state.error, /空字符/);
  c.update('关键词', 'fingpt'); assert.equal(calls, 0);
});
test('native failures and malformed or wrong-mode snippets fail visibly without automatic retry', async () => {
  for (const data of [null, { ...result('x'), source: 'fake' }, { ...result('x'), has_more: null }, { ...result('x'), items: [{ ...result('x').items[0], mode: 'fingpt' }] }]) {
    let calls = 0; const c = createSessionSearch({ search: async () => { calls++; return data; }, schedule: fn => { fn(); return null; } });
    c.update('正文', 'claw'); await tick(); assert.equal(calls, 1); assert.match(c.state.error, /暂不可用/); assert.deepEqual(c.state.items, []);
  }
});
test('verified native snippets remain ephemeral and has-more does not invent pagination', async () => {
  const c = createSessionSearch({ search: async () => ({ ...result('s'), has_more: true }), schedule: fn => { fn(); return null; } });
  c.update('正文', 'claw'); await tick(); assert.equal(c.state.items[0].id, 's'); assert.equal(c.state.has_more, true);
  c.close(); assert.deepEqual(c.state.items, []);
});
test('native search merges title hits without duplicates and renders snippets as text', () => {
  const sessions = [{ id: 's', mode: 'claw', title: '正文研究' }, { id: 'f', mode: 'fingpt', title: '正文FinGPT' }];
  const native = { query: '正文', mode: 'claw', items: [{ id: 's', mode: 'claw', title: '正文研究', snippet: '<img src=x onerror=alert(1)>' }], has_more: true };
  const html = renderGlobalResults('正文', sessions, [], { native });
  assert.equal((html.match(/data-session-id="s"/g) || []).length, 1); assert.match(html, /&lt;img/); assert.doesNotMatch(html, /<img|正文FinGPT/); assert.match(html, /缩小关键词/);
  assert.match(renderGlobalSearch('', sessions, [], { native: { ...native, query: '' } }), /搜索Claw会话标题、正文和能力/);
  assert.match(renderGlobalResults('', sessions, [], { native: { ...native, query: '', items: [] } }), /最近 Claw 会话/);
  assert.equal(renderGlobalResults('', sessions, []), '');
});
test('native failure exposes explicit retry while local capability results remain usable', () => {
  const html = renderGlobalResults('研究', [], [{ id: 'skill', name: '研究', enabled: true }], { native: { query: '研究', mode: 'claw', items: [], error: '暂不可用' } });
  assert.match(html, /data-retry-native-search/); assert.match(html, /data-skill-shortcut="skill"/);
});
test('native query API keeps text in a JSON body outside access-log URLs without widening mode', async () => {
  const calls = []; const api = createAPI({ logger() {}, fetcher: async (url, options) => { calls.push([url, options]); return new Response(JSON.stringify(result('s')), { headers: { 'content-type': 'application/json' } }); } });
  await api.searchSessions('正文&mode=fingpt', 'claw'); assert.equal(calls.length, 1); assert.match(calls[0][0], /\/sessions\/search$/); assert.doesNotMatch(calls[0][0], /正文|query|mode=/); assert.equal(calls[0][1].method, 'POST'); assert.deepEqual(JSON.parse(calls[0][1].body), { query: '正文&mode=fingpt', mode: 'claw' });
});
test('a native-search POST timeout remains a read failure and never retries', async () => {
  let calls = 0; const api = createAPI({ logger() {}, requestTimeoutMs: 2, fetcher: async () => { calls++; return new Promise(() => {}); } });
  await assert.rejects(api.searchSessions('正文'), /读取超时/); assert.equal(calls, 1);
});
