import assert from 'node:assert/strict';
import test from 'node:test';
import { createMarketController, renderMarketPage, marketQuoteParams, marketNumber, marketSign, marketHref } from '../../app/research_web/ui/market.mjs';

const data = (overrides = {}) => ({ sections: {}, market_state: { state: 'unknown' }, inflight: [], ...overrides });
const section = (rows = [], extra = {}) => ({ rows, provider: 'eastmoney', complete: true, pagination_complete: true, provider_total: rows.length, snapshot_id: 'snap1', as_of: '2026-10-22T03:00:00Z', retrieved_at: '2026-10-22T03:00:01Z', ...extra });
const quote = { asset: '920001.BJ', code: '920001', name: '北交样本', exchange: 'BJ', price: 0, change_pct: null, amount: 0 };

test('overview separates confirmed limits, unknown coverage and previous amount gap', () => {
  const html = renderMarketPage({ snapshot: data({ sections: { quotes: section([], { summary: { limit_up: 0, limit_down: 2, limit_unknown: 3, limit_covered: 10, previous_amount: { amount: null, reason: '缺少合格昨日快照' } } }) } }) });
  assert.match(html, /确认涨停/); assert.match(html, /确认跌停/); assert.match(html, /限价未知/);
  assert.match(html, /昨日同口径成交额/); assert.match(html, /缺少合格昨日快照/);
});

test('fund history shows all five amounts and distinguishes vendor from accumulated rows', () => {
  const flow = { provider: 'eastmoney', row_count: 1, provider_total: 1, history_requested: 30, history_count: 2, history_rows: [{date:'2026-10-21',main_net:0,super_net:-1,large_net:1,medium_net:2,small_net:-2},{date:'2026-10-22',main_net:-3,super_net:-1,large_net:-2,medium_net:2,small_net:1}] };
  const html = renderMarketPage({ snapshot: data({ sections: { 'flows:industry:today': section([], { summary: { market_flow: flow } }) } }) }, {marketView:'sectors'});
  assert.match(html, /本次来源 1 日/); assert.match(html, /已留存 2 日/); assert.match(html, /未补齐/);
  assert.match(html, /2026-10-21/); assert.match(html, /超大单/); assert.match(html, /小单/);
});

test('known suspended and unlisted rows have explicit labels and separate breadth', () => {
  const html = renderMarketPage({ snapshot: data({ sections: { quotes: section([], { summary: { up: 1, down: 2, flat: 3, unknown: 0, suspended: 7, unlisted: 4, amount: 2000, amount_scope_count: 13 } }) } }) });
  assert.match(html, /停牌/); assert.match(html, /未上市/); assert.match(html, /已上市 13 只/);
  const table = renderMarketPage({ quotes: { items: [{ ...quote, price: 3.57, trade_status: 'suspended', price_basis: 'last_traded_reference' }] } }, { marketView: 'quotes' });
  assert.match(table, /3\.57<small>停牌参考价/);
});

test('market flow uses its own date and row coverage rather than sector metadata', () => {
  const market = section([{ date: '2026-10-22', main_net: -10 }], { trade_date: '2026-10-22', retrieved_at: '2026-10-22T09:00:00Z' });
  const html = renderMarketPage({ snapshot: data({ sections: { 'flows:industry:today': section([], { provider_total: 496, summary: { market_flow: market } }) } }) }, { marketView: 'sectors' });
  assert.match(html, /行情日：2026-10-22（日线）/); assert.match(html, /1 \/ 1 条/);
});

test('retained market flow inherits collector staleness and error without sector coverage', () => {
  const market = section([{ date: '2026-10-22', main_net: -10 }], { trade_date: '2026-10-22' });
  const html = renderMarketPage({ snapshot: data({ sections: { 'flows:industry:today': section([], { stale: true, error: { message: '本次获取失败' }, provider_total: 496, summary: { market_flow: market } }) } }) }, { marketView: 'sectors' });
  const panel = html.slice(html.indexOf('<h2>沪深大盘资金流'));
  assert.match(panel, /陈旧 · 保留上次快照/); assert.match(panel, /本次获取失败/);
  assert.match(panel, /1 \/ 1 条/); assert.doesNotMatch(panel, /496/);
});

function harness(initial = data(), extra = {}) {
  const calls = []; let current = initial;
  const api = { request: async (path, options = {}) => {
    calls.push({ path, options });
    if (path === '/market') return current;
    if (path === '/market/refresh') return { request_id: `req${calls.length}`, status: 'completed' };
    if (path.startsWith('/market/quotes?')) return { items: [quote], total: 1, snapshot_id: 'snap1', meta: section() };
    if (options.method === 'DELETE') return { status: 'cancelled' };
    return { status: 'completed' };
  } };
  const timers = new Map(); let nextTimer = 0;
  const doc = { hidden: false, addEventListener() {}, removeEventListener() {} };
  const controller = createMarketController({ api, documentRef: doc, storage: null, setTimer: (fn, ms) => { timers.set(++nextTimer, { fn, ms }); return nextTimer; }, clearTimer: id => timers.delete(id), ...extra });
  return { controller, calls, timers, doc, setData: value => { current = value; } };
}

test('market renders three tabs and explicit absent data without fabricated zeroes', () => {
  const html = renderMarketPage();
  for (const label of ['全市场概览', '总览', '沪深北行情', '板块与资金', '涨跌幅分布', '行业热力图', '概念热力图']) assert.ok(html.includes(label), label);
  assert.match(html, /交易状态待确认/); assert.match(html, /涨跌停.*未提供/);
  assert.doesNotMatch(html, /模拟|强弱评分|0 只上涨/);
});

test('formatting distinguishes zero, null, booleans and negative returns', () => {
  assert.equal(marketNumber(0), '0'); assert.equal(marketNumber(null), '—'); assert.equal(marketNumber(false), '—');
  assert.equal(marketNumber(' '), '—'); assert.equal(marketSign(0), 'flat'); assert.equal(marketSign(null), 'unknown'); assert.equal(marketSign(-2), 'down');
});

test('quotes preserve canonical BJ identities, zero and explicit missing fields', () => {
  const html = renderMarketPage({ view: 'quotes', quotes: { items: [quote], total: 1, snapshot_id: 'snap1' }, snapshot: data({ sections: { quotes: section([], { complete: false, limitations: ['缺失沪市分页'], stale: true }) } }) });
  assert.match(html, /920001\.BJ/); assert.match(html, /asset=920001.BJ/); assert.match(html, /缺失沪市分页/); assert.match(html, /陈旧/);
  assert.match(html, /data-market-column="price"[^>]*>0</); assert.match(html, /data-market-column="change_pct"[^>]*>—</);
});

test('metadata and supplier strings are safely escaped and coverage is visible', () => {
  const html = renderMarketPage({ snapshot: data({ sections: { industry: section([{ board_id: 'BK0001', name: '<script>x</script>', change_pct: 0 }], { complete: false, provider_total: 40, limitations: ['<img onerror=x>'], missing: { rows: 3 } }) } }) });
  assert.ok(html.includes('&lt;script&gt;')); assert.ok(html.includes('&lt;img')); assert.doesNotMatch(html, /<script>|<img onerror/); assert.match(html, /40/); assert.match(html, /未完整/);
});

test('query parameters and route links only carry supported filters', () => {
  const params = marketQuoteParams({ exchange: 'BJ', board: 'beijing', search: '北&证', sort: 'amount', direction: 'asc', offset: 50, limit: 50, board_id: 'BK0011' }, 'snap 2');
  assert.equal(params.get('exchange'), 'BJ'); assert.equal(params.get('search'), '北&证'); assert.equal(params.get('snapshot_id'), 'snap 2');
  assert.equal(marketHref('quotes', 'BK0011'), '#/market?view=quotes&board_id=BK0011');
  assert.equal(marketHref('bad', 'x<script>'), '#/market?view=overview');
});

test('activation initially starts one bounded refresh but unknown calendar has no auto timer', async () => {
  const h = harness(); await h.controller.activate({ marketView: 'overview' });
  assert.equal(h.calls.filter(c => c.path === '/market/refresh').length, 1);
  assert.equal(h.timers.size, 0); assert.equal(h.controller.state.loading, false); h.controller.dispose();
});

test('known trading state schedules 30 second quotes and 60 second sectors', async () => {
  const h = harness(data({ sections: { quotes: section(), indices: section(), industry: section(), concept: section() }, market_state: { state: 'open' } }));
  await h.controller.activate({ marketView: 'overview' });
  assert.deepEqual([...h.timers.values()].map(t => t.ms).sort((a,b) => a-b), [30000, 60000, 60000]);
  h.controller.setPaused(true); assert.equal(h.timers.size, 0);
  h.controller.dispose();
});

test('hidden page stops timers and releases only its reader refresh IDs', async () => {
  let listener;
  const h = harness(data({ market_state: { state: 'open' } }), { documentRef: { hidden: false, addEventListener: (_name, fn) => { listener = fn; }, removeEventListener() {} } });
  await h.controller.activate({ marketView: 'overview' }); h.controller.document.hidden = true; listener();
  assert.equal(h.timers.size, 0); h.controller.dispose();
});

test('late activation cannot overwrite a newer page state', async () => {
  let resolve;
  const h = harness(); let count = 0;
  h.controller.api.request = async path => {
    if (path === '/market') { count++; if (count === 1) return new Promise(r => { resolve = r; }); return data({ market_state: { state: 'closed' } }); }
    if (path.startsWith('/market/quotes?')) return { items: [quote], total: 1 };
    return { status: 'completed', request_id: 'r' };
  };
  const first = h.controller.activate({ marketView: 'overview' });
  await h.controller.activate({ marketView: 'quotes' });
  resolve(data({ market_state: { state: 'open' } })); await first;
  assert.equal(h.controller.state.view, 'quotes'); assert.equal(h.controller.state.snapshot.market_state.state, 'closed'); h.controller.dispose();
});

test('read failures are visible and do not silently trigger another POST', async () => {
  const h = harness(); h.controller.api.request = async () => { throw new Error('来源暂不可用'); };
  await h.controller.activate({ marketView: 'quotes' });
  assert.equal(h.controller.state.error, '来源暂不可用'); assert.equal(h.controller.state.loading, false); h.controller.dispose();
});

test('dense table includes export snapshot and column visibility controls', () => {
  const html = renderMarketPage({ view: 'quotes', quotes: { items: [quote], total: 1, snapshot_id: 'frozen' } });
  assert.match(html, /quotes\/export\?/); assert.match(html, /snapshot_id=frozen/); assert.match(html, /data-market-column-toggle/); assert.match(html, /aria-label="搜索股票代码或名称"/);
});

test('fast refresh does not reset or starve the sixty second sector timer', async () => {
  const h = harness(data({ sections: Object.fromEntries(['quotes','indices','industry','concept','calendar'].map(key => [key,section()])), market_state: { state: 'open' } }));
  await h.controller.activate({ marketView: 'overview' });
  const slow = [...h.timers.entries()].filter(([,timer]) => timer.ms === 60000).at(-1);
  const fast = [...h.timers.entries()].find(([,timer]) => timer.ms === 30000);
  h.timers.delete(fast[0]); fast[1].fn();
  await new Promise(resolve => setImmediate(resolve));
  assert.ok(h.timers.has(slow[0]));
  assert.equal(h.calls.filter(call => call.path === '/market/refresh').length, 1);
  assert.deepEqual(h.calls.find(call => call.path === '/market/refresh').options.body.sections, ['quotes','indices']);
  h.controller.dispose();
});

test('pending reader is released on page cancellation and late refresh cannot publish', async () => {
  let releaseStart;
  const calls = [];
  const h = harness(data({ sections: { quotes: section(), calendar: section() }, market_state: { state: 'unknown' } }));
  h.controller.api.request = async (path, options = {}) => {
    calls.push({path,options});
    if (path === '/market') return data({ sections: { quotes: section(), calendar: section() }, market_state: { state: 'unknown' } });
    if (path === '/market/refresh') return new Promise(resolve => { releaseStart = resolve; });
    if (path.startsWith('/market/quotes?')) return {items: [], total: 0};
    return {status: 'cancelled'};
  };
  await h.controller.activate({marketView: 'quotes'});
  const pending = h.controller.refresh(['quotes']);
  h.controller.cancel();
  releaseStart({request_id:'owned-reader',status:'running'});
  await pending;
  assert.equal(calls.filter(call => call.options.method === 'DELETE').length,1);
  assert.equal(calls.find(call => call.options.method === 'DELETE').path, '/market/refresh/owned-reader');
  assert.equal(h.controller.state.refreshing,false);
  h.controller.dispose();
});

test('failed task retains existing snapshot and exposes safe task failure', async () => {
  const h = harness(data({sections: {quotes:section([], {summary:{total:5925}})}}));
  h.controller.api.request = async path => path === '/market' ? data({sections:{quotes:section([], {summary:{total:5925}})}}) : {request_id:'failed',status:'failed',error:{message:'全量分页未完成'}};
  await h.controller.activate({marketView:'overview'});
  assert.equal(h.controller.state.error,'全量分页未完成');
  assert.equal(h.controller.state.snapshot.sections.quotes.summary.total,5925);
  h.controller.dispose();
});

test('flow period and kind controls request the selected supplier scope', async () => {
  const h = harness(data({sections: {industry:section(),calendar:section(),'flows:industry:today':section()}}));
  await h.controller.activate({marketView:'sectors'});
  const event = {target:{dataset:{marketPeriod:''},value:'5d'}};
  assert.equal(h.controller.handleChange(event),true);
  await new Promise(resolve=>setImmediate(resolve));
  const refresh=h.calls.find(call=>call.path==='/market/refresh');
  assert.deepEqual(refresh.options.body,{sections:['flows'],kind:'industry',period:'5d'});
  h.controller.dispose();
});

test('index comparisons use gaps and never turn absolute prices into returns', () => {
  const indices=section([{asset:'000001.SH',name:'上证',price:3000,series:[{time:'09:30',change_pct:0},{time:'09:32',change_pct:1}]},{asset:'899050.BJ',name:'北证',series:[{time:'09:30',price:1000}]}]);
  const html=renderMarketPage({snapshot:data({sections:{indices}})});
  assert.match(html,/market-intraday/);
  assert.match(html,/<path d="M[^\"]+ M/);
  assert.doesNotMatch(html,/NaN|Infinity/);
  const missing=renderMarketPage({snapshot:data({sections:{indices:section([{asset:'899050.BJ',series:[{time:'09:30',price:1000}]}])}})});
  assert.match(missing,/需要真实分时数据及昨收基准/);
});

test('column preferences are namespaced by account and keep code/name visible', async () => {
  const stored=[];
  const h=harness(data({sections:{quotes:section(),calendar:section()}}),{storage:{getItem:()=>null,setItem:(key,value)=>stored.push({key,value})}});
  const target={dataset:{marketColumnToggle:'volume'},checked:false};
  assert.equal(h.controller.handleChange({target}),true);
  assert.ok(!h.controller.state.columns.includes('volume'));
  assert.ok(h.controller.state.columns.includes('code'));assert.ok(h.controller.state.columns.includes('name'));
  assert.match(stored[0].key,/rwb:local:market-columns-v1/);
  h.controller.dispose();
});

test('calendar-backed lunch resumes automatically using cache-only state checks', async () => {
  const sections=Object.fromEntries(['quotes','indices','industry','concept','calendar'].map(key=>[key,section()]));
  const h=harness(data({sections,market_state:{state:'lunch'}}));
  await h.controller.activate({marketView:'overview'});
  assert.equal(h.timers.size,1);assert.equal(h.calls.filter(call=>call.path==='/market/refresh').length,0);
  h.setData(data({sections,market_state:{state:'open'}}));
  const [id,timer]=[...h.timers.entries()][0];h.timers.delete(id);timer.fn();
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(h.calls.filter(call=>call.path==='/market/refresh').length,1);
  assert.equal(h.timers.size,3);
  h.controller.dispose();
});

test('overview concept buttons retain explicit membership classification', () => {
  const html=renderMarketPage({snapshot:data({sections:{concept:section([{board_id:'BK1234',name:'概念甲',change_pct:1}])}})});
  assert.match(html,/data-board-id="BK1234"[^>]*data-kind="concept"/);
});

test('hiding all index lines keeps controls so the selection can be restored', () => {
  const html=renderMarketPage({selectedIndices:['__none__'],snapshot:data({sections:{indices:section([{asset:'000001.SH',name:'上证',series:[{time:'09:30',change_pct:0}]}])}})});
  assert.match(html,/data-market-index="000001.SH"/);assert.match(html,/可勾选指数查看/);assert.doesNotMatch(html,/market-intraday/);
});

test('partial snapshots show coverage while preventing an unaccepted CSV download', () => {
  const html=renderMarketPage({view:'quotes',snapshot:data({sections:{quotes:section([],{complete:false,provider_total:6000,row_count:5500})}}),quotes:{items:[quote],total:5500,snapshot_id:'partial'}});
  assert.match(html,/5,500 \/ 6,000 条/);assert.match(html,/aria-disabled="true" data-market-disabled title="取得完整快照后可导出"/);
});

test('CSV uses export filters without pagination parameters rejected by the server', () => {
  const html=renderMarketPage({view:'quotes',quotes:{items:[quote],total:1,snapshot_id:'accepted'},filters:{offset:100,limit:50}});
  const query=html.match(/href="\/api\/research\/market\/quotes\/export\?([^"]+)"/)[1].replaceAll('&amp;','&');
  const params=new URLSearchParams(query);assert.equal(params.has('limit'),false);assert.equal(params.has('offset'),false);assert.equal(params.get('snapshot_id'),'accepted');
});

test('market funds render the provider nested daily history rows', () => {
  const html=renderMarketPage({view:'sectors',snapshot:data({sections:{'flows:industry:today':section([],{summary:{market_flow:{scope:'SH+SZ',frequency:'daily',rows:[{date:'2026-10-21',main_net:100000000}]}}})}})});
  assert.match(html,/2026-10-21/);assert.match(html,/1亿/);assert.match(html,/不包含北交所/);
});

test('individual index dates and mixed-day stock statistics remain visibly distinct', () => {
  const html=renderMarketPage({snapshot:data({sections:{indices:section([{asset:'000001.SH',name:'上证',as_of:'2026-10-22T03:00:00Z'},{asset:'899050.BJ',name:'北证',as_of:'2026-10-21T07:00:00Z'}]),quotes:section([],{summary:{temporal_complete:false,quote_trade_date:'2026-10-22'},missing:{quote_date:2}})}})});
  assert.match(html,/2026-10-21 · 旧日/);assert.match(html,/行情日不齐/);assert.match(html,/统计行情日：2026-10-22/);assert.match(html,/quote_date：2/);
});

async function deferredBoardRace(firstFinished) {
  const pending = new Map(), navigations = [], calls = [];
  const snapshot = data({ sections: Object.fromEntries(['quotes','indices','industry','concept','calendar'].map(key => [key, section()])) });
  const h = harness(snapshot, { onNavigate: hash => { navigations.push(hash); h.controller.cancel(); } });
  h.controller.api.request = async (path, options = {}) => {
    calls.push({path,options});
    if (path === '/market') return snapshot;
    if (path === '/market/refresh') return new Promise(resolve => pending.set(options.body.board_id, resolve));
    return {status:'cancelled'};
  };
  await h.controller.activate({marketView:'overview'});
  const click = id => h.controller.handleClick({preventDefault(){},target:{closest: selector => selector === '[data-market-action]' ? {dataset:{marketAction:'members',boardId:id,boardName:id,kind:'industry'}} : null}});
  click('BK0001'); click('BK0002');
  pending.get(firstFinished)({request_id:`reader-${firstFinished}`,status:'completed'});
  await new Promise(resolve => setImmediate(resolve));
  if (firstFinished === 'BK0001') assert.deepEqual(navigations, [], 'older selection must not navigate while latest board is pending');
  pending.get(firstFinished === 'BK0001' ? 'BK0002' : 'BK0001')({request_id:`reader-${firstFinished === 'BK0001' ? 'BK0002' : 'BK0001'}`,status:'completed'});
  await new Promise(resolve => setImmediate(resolve));
  assert.deepEqual(navigations, ['#/market?view=quotes&board_id=BK0002']);
  assert.ok(calls.some(call => call.path === '/market/refresh/reader-BK0001' && call.options.method === 'DELETE'));
  assert.ok(!calls.some(call => call.path === '/market/refresh/reader-BK0002' && call.options.method === 'DELETE'));
  h.controller.dispose();
}

test('two delayed board selections navigate only the latest when the old request finishes first', async () => { await deferredBoardRace('BK0001'); });
test('two delayed board selections keep the latest when completion order is reversed', async () => { await deferredBoardRace('BK0002'); });

test('unsubmitted search draft survives a market state redraw without filtering the table', async () => {
  const h = harness(data({ sections: { quotes: section(), calendar: section() } }));
  await h.controller.activate({marketView:'quotes'});
  const priorReads=h.calls.filter(call=>call.path.startsWith('/market/quotes?')).length;
  assert.equal(h.controller.handleInput({target:{dataset:{marketSearchDraft:''},value:'北交&样本'}}),true);
  assert.equal(h.controller.state.filters.search,'');
  await h.controller.refresh(['quotes']);
  assert.match(renderMarketPage(h.controller.state),/id="market-search"/);
  assert.match(renderMarketPage(h.controller.state),/value="北交&amp;样本"/);
  assert.equal(h.calls.filter(call=>call.path.startsWith('/market/quotes?')).length,priorReads+1);
  assert.ok(h.calls.filter(call=>call.path.startsWith('/market/quotes?')).every(call=>!new URLSearchParams(call.path.split('?')[1]).has('search')));
  h.controller.dispose();
});

test('replacing an in-progress board selection releases its own reader without cancelling the new one', async () => {
  const calls=[], navigations=[];
  const snapshot=data({sections:Object.fromEntries(['quotes','indices','industry','concept','calendar'].map(key=>[key,section()]))});
  const h=harness(snapshot,{onNavigate:hash=>{navigations.push(hash);h.controller.cancel();}});
  h.controller.api.request=async(path,options={})=>{
    calls.push({path,options});
    if(path==='/market')return snapshot;
    if(path==='/market/refresh')return {request_id:`active-${options.body.board_id}`,status:'running'};
    if(options.method==='DELETE')return {status:'cancelled'};
    return {status:'completed'};
  };
  await h.controller.activate({marketView:'overview'});
  const click=id=>h.controller.handleClick({preventDefault(){},target:{closest:selector=>selector==='[data-market-action]'?{dataset:{marketAction:'members',boardId:id,boardName:id}}:null}});
  click('BK0001');await new Promise(resolve=>setImmediate(resolve));
  click('BK0002');await new Promise(resolve=>setImmediate(resolve));
  assert.equal(calls.filter(call=>call.path==='/market/refresh/active-BK0001'&&call.options.method==='DELETE').length,1);
  assert.equal(calls.filter(call=>call.path==='/market/refresh/active-BK0002'&&call.options.method==='DELETE').length,0);
  const [id,timer]=[...h.timers.entries()][0];h.timers.delete(id);timer.fn();
  await new Promise(resolve=>setImmediate(resolve));
  assert.deepEqual(navigations,['#/market?view=quotes&board_id=BK0002']);
  assert.equal(calls.filter(call=>call.path==='/market/refresh/active-BK0002'&&call.options.method==='DELETE').length,0);
  h.controller.dispose();
});

test('an old refresh cannot remove the current generation singleflight registration', async () => {
  const snapshot = data({sections: Object.fromEntries(['quotes','calendar'].map(key => [key, section()]))});
  const h = harness(snapshot), starts = [], calls = [];
  h.controller.api.request = async (path, options = {}) => {
    calls.push({path, options});
    if (path === '/market') return snapshot;
    if (path.startsWith('/market/quotes?')) return {items: [quote], total: 1};
    if (path === '/market/refresh') return new Promise(resolve => starts.push(resolve));
    return {status: 'cancelled'};
  };
  await h.controller.activate({marketView: 'quotes'});
  const old = h.controller.refresh(['quotes']);
  await h.controller.activate({marketView: 'quotes'});
  const current = h.controller.refresh(['quotes']);
  assert.equal(starts.length, 2);
  starts[0]({request_id: 'old', status: 'completed'});
  await old;
  const duplicate = h.controller.refresh(['quotes']);
  assert.equal(starts.length, 2, 'the active refresh must still be shared after an old response');
  assert.equal(h.controller.state.refreshing, true);
  starts[1]({request_id: 'current', status: 'completed'});
  await Promise.all([current, duplicate]);
  assert.equal(h.controller.state.refreshing, false);
  assert.ok(calls.some(call => call.path === '/market/refresh/old' && call.options.method === 'DELETE'));
  assert.ok(!calls.some(call => call.path === '/market/refresh/current' && call.options.method === 'DELETE'));
  h.controller.dispose();
});
