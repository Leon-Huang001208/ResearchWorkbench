import assert from 'node:assert/strict';
import test from 'node:test';
import { readFile } from 'node:fs/promises';
import * as workspace from '../../app/research_web/ui/asset-workspace.mjs';
import * as navigation from '../../app/research_web/ui/asset-navigation.mjs';
import { createAssetNewsController, renderAssetNews } from '../../app/research_web/ui/asset-news.mjs';

const route = assetView => ({ page: 'assets', section: 'assets', asset: '600519.SH', assetType: 'stock', assetView });
const props = assetView => ({ route: route(assetView), observation: { id: 'o', asset: '600519.SH', asset_type: 'stock', blocks: {} } });
const topic = html => html.slice(html.indexOf('data-asset-topic-slot'));

test('asset tabs expose one labelled panel and only the selected topic content', () => {
  const expected = { overview: ['asset-topic-overview'], financials: ['financial-panel'], capital: ['capital-flow-card', 'data-asset-block="margin"'], holders: ['shareholder-panel', 'data-asset-block="holders"'], news: ['data-asset-news-slot'], announcements: ['data-asset-news-slot'], materials: ['data-asset-block="research"', 'industry-panel', 'events-panel'] };
  for (const assetView of navigation.ASSET_VIEWS) {
    const html = workspace.renderAssetWorkspace(props(assetView));
    assert.match(html, /role="tablist"/);
    assert.equal((html.match(/role="tab"/g) || []).length, 7);
    assert.equal((html.match(/role="tabpanel"/g) || []).length, 1);
    assert.match(html, new RegExp(`id="asset-tab-${assetView}"[^>]*aria-selected="true"[^>]*tabindex="0"`));
    assert.match(html, new RegExp(`aria-labelledby="asset-tab-${assetView}"`));
    for (const marker of expected[assetView]) assert.ok(topic(html).includes(marker), `${assetView}: ${marker}`);
    for (const [other, markers] of Object.entries(expected)) {
      if (other === assetView || ['news', 'announcements'].includes(other) && ['news', 'announcements'].includes(assetView)) continue;
      for (const marker of markers) assert.equal(topic(html).includes(marker), false, `${assetView} excludes ${marker}`);
    }
    assert.equal((html.match(/data-asset-news-slot/g) || []).length, ['news', 'announcements'].includes(assetView) ? 1 : 0);
    assert.ok(html.includes('data-asset-personal'), 'personal research remains globally available');
    assert.equal((html.match(/class="asset-source-summary"/g) || []).length, 1);
    assert.match(html, /<details class="asset-source-summary">/);
    assert.doesNotMatch(html, /macro-panel|宏观/);
  }
});

test('one global source disclosure keeps full limitations out of the topic cards on every tab', () => {
  const limitations = { valuation: '合成CSV估值单位长说明', financials: '合成公式财务口径长说明', margin: '合成两融数据边界长说明', research: '合成研究资料覆盖长说明' };
  const observation = { asset: '600519.SH', asset_type: 'stock', blocks: Object.fromEntries(Object.entries(limitations).map(([name, note]) => [name, { status: 'complete', dataset: { dataset_id: name, provider: 'tinysoft', limitations: [note] } }])) };
  for (const assetView of navigation.ASSET_VIEWS) {
    const html = workspace.renderAssetWorkspace({ observation, route: route(assetView), errors: { financials: '合成当前财务失败提示' } });
    const sourceIndex = html.indexOf('<details class="asset-source-summary">');
    assert.ok(sourceIndex > html.indexOf('data-asset-chart-slot'));
    assert.ok(sourceIndex < html.indexOf('<nav class="asset-topic-tabs"'));
    for (const note of Object.values(limitations)) {
      assert.equal(html.split(note).length - 1, 1, `${assetView}: ${note}`);
      assert.equal(topic(html).includes(note), false, `${assetView} topic stays compact`);
    }
    if (assetView === 'financials') assert.match(topic(html), /合成当前财务失败提示/);
  }
});

test('asset header has one search slot and one more menu without old query forms', () => {
  const html = workspace.renderAssetWorkspace(props('overview'));
  assert.equal((html.match(/data-asset-search-slot/g) || []).length, 1);
  assert.equal((html.match(/class="asset-more-menu"/g) || []).length, 1);
  assert.doesNotMatch(html, /<form[^>]*\bdata-asset-select\b|<form[^>]*\bdata-asset-observation\b|name="asset_type"|name="source"|name="[^"]*start_date"/);
  const menu = html.slice(html.indexOf('<details class="asset-more-menu"'), html.indexOf('data-asset-metrics-toggle'));
  assert.match(menu, /自选与最近观察/);
  assert.match(menu, /data-workbench-handoff="fingpt"/);
  assert.match(menu, /data-workbench-handoff="claw"/);
});

test('updating an asset topic only mutates its slot and tab semantics', () => {
  assert.equal(typeof workspace.updateAssetTopic, 'function');
  const persistentChart = { selectedDate: '2026-10-20', zoom: [25, 90] };
  const tabs = navigation.ASSET_VIEWS.map(view => ({ dataset: { assetTab: view }, attrs: {}, classList: { toggle(name, selected) { this[name] = selected; } }, setAttribute(name, value) { this.attrs[name] = value; } }));
  const slot = { innerHTML: '' };
  const page = { dataset: { assetIdentity: 'stock:600519.SH', assetView: 'overview' }, querySelector(selector) { assert.equal(selector, '[data-asset-topic-slot]'); return slot; }, querySelectorAll(selector) { assert.equal(selector, '[data-asset-tab]'); return tabs; }, chart: persistentChart };
  assert.equal(workspace.updateAssetTopic(page, props('financials')), true);
  assert.equal(page.chart, persistentChart);
  assert.deepEqual(page.chart, { selectedDate: '2026-10-20', zoom: [25, 90] });
  assert.match(slot.innerHTML, /financial-panel/);
  assert.equal(page.dataset.assetView, 'financials');
  assert.equal(tabs[1].attrs['aria-selected'], 'true');
  assert.equal(tabs[0].attrs.tabindex, '-1');
  assert.equal(workspace.updateAssetTopic(page, { ...props('news'), route: { ...route('news'), asset: '603986.SH' } }), false);
});

test('asset tab navigation wraps horizontally and preserves URL asset identity', () => {
  assert.equal(typeof navigation.assetTopicKey, 'function');
  assert.equal(navigation.assetTopicKey('ArrowLeft', 'overview'), 'materials');
  assert.equal(navigation.assetTopicKey('ArrowRight', 'materials'), 'overview');
  assert.equal(navigation.assetTopicKey('Home', 'news'), 'overview');
  assert.equal(navigation.assetTopicKey('End', 'news'), 'materials');
  assert.equal(navigation.assetTopicKey('ArrowDown', 'news'), null);
  assert.equal(navigation.assetHref('600519.SH', 'stock', 'capital'), '#/assets?view=capital&asset=600519.SH&asset_type=stock');
});

test('news states always explain idle loading empty and failure', () => {
  const common = { asset: '600519.SH', assetType: 'stock', view: 'news', items: [] };
  assert.match(renderAssetNews({ ...common, status: 'idle' }), /尚未读取|准备读取/);
  assert.match(renderAssetNews({ ...common, status: 'loading' }), /正在读取/);
  assert.match(renderAssetNews({ ...common, status: 'empty' }), /空列表/);
  assert.match(renderAssetNews({ ...common, status: 'error' }), /读取失败/);
});

test('valuation keeps the declared PBLF basis visible and separate from PB-MRQ', () => {
  const observation = { asset: '600519.SH', asset_type: 'stock', blocks: { valuation: { status: 'complete', dataset: { provider: 'tinysoft', fields: [{ name: 'pb', unit: 'ratio', basis: 'PBLF' }, { name: 'pb_mrq', unit: 'ratio', basis: 'PBMRQ' }] } } } };
  const rows = { valuation: [{ date: '2026-10-21', pb: 2, pb_mrq: 3 }] };
  const html = workspace.renderAssetWorkspace({ observation, rows, route: route('financials') });
  assert.match(html, /PB 来源口径 PBLF/);
  assert.match(html, /PB<\/dt><dd>2 倍<\/dd>/);
  assert.match(html, /PB-MRQ<\/dt><dd id="fin-pb">3 倍<\/dd>/);
});

test('coverage summary classifies all eleven blocks and keeps unknown state pending', () => {
  assert.equal(typeof workspace.summarizeAssetCoverage, 'function');
  const rows = ['ready', 'ready', 'empty', 'not_loaded', 'loading', 'refreshing', 'error', 'stale', 'not_connected', undefined, 'not_loaded'].map(loadState => ({ loadState, hasSnapshot: ['ready', 'refreshing', 'stale'].includes(loadState), retainedSnapshot: loadState === 'stale' }));
  assert.deepEqual(workspace.summarizeAssetCoverage(rows), { acquired: 4, pending: 4, failed: 2, notConnected: 1, updating: 2, retained: 1, empty: 1 });
});

test('new holder industry and event blocks count as acquired while unrequested blocks stay pending', () => {
  const names = ['holder_details', 'industry', 'events'];
  const observation = { asset: '600519.SH', asset_type: 'stock', blocks: Object.fromEntries(names.map(name => [name, { status: 'complete', dataset: { dataset_id: name, provider: 'tinysoft' } }])) };
  const rows = { holder_details: [{ name: '真实股东', share_ratio: 1 }], industry: [{ sw_level_1: '电子' }], events: [{ summary: '真实事件', date: '2026-10-21' }] };
  const html = workspace.renderAssetWorkspace({ observation, rows, route: route('overview') });
  assert.match(html, /已取得 3 · 待加载 8 · 查询失败 0 · 未接入 0/);
  for (const name of names) assert.match(html, new RegExp(`data-asset-source-row="${name}"`));
  assert.equal((html.match(/data-asset-source-row=/g) || []).length, 11);
});

test('empty successes and unsupported providers stay distinct from never loaded blocks', () => {
  const observation = { asset: '600519.SH', asset_type: 'stock', blocks: { industry: { status: 'empty', dataset: { dataset_id: 'empty-industry', provider: 'tinysoft' } }, research: { status: 'unavailable', failure_code: 'tinysoft_capability_unsupported' }, financials: { status: 'error', failure_code: 'query_failed' } } };
  const html = workspace.renderAssetWorkspace({ observation, route: route('overview') });
  assert.match(html, /已取得 1 · 待加载 8 · 查询失败 1 · 未接入 1 · 空结果 1/);
  const cold = workspace.renderAssetWorkspace(props('overview'));
  assert.match(cold, /已取得 0 · 待加载 11 · 查询失败 0 · 未接入 0/);
  assert.doesNotMatch(cold, /不可用|\d+\/11 区块有快照/);
});

test('canonical history has guidance instead of an unsupported ordinary block-load button', () => {
  const html = workspace.renderAssetWorkspace(props('overview'));
  const row = html.match(/<tr data-asset-source-row="history">[^]*?<\/tr>/)?.[0];
  assert.ok(row);
  assert.match(row, /历史行情使用上方图表控件更新/);
  assert.doesNotMatch(html, /data-asset-block-load="history"/);
});

test('holder detail cards show the same actual block provenance and failure state as the projected names', () => {
  const observation = { asset: '600519.SH', asset_type: 'stock', blocks: { holder_details: { status: 'complete', dataset: { dataset_id: 'synthetic-holder-details', provider: 'tinysoft', as_of: '2026-10-21', fields: [{ name: 'share_ratio', unit: 'percent' }], limitations: ['合成股东明细，仅用于渲染测试'] } } } };
  const rows = { holder_details: [{ shareholder_name: '合成股东甲', report_period: '2026-06-30', share_ratio: 0, is_state_owned: false }] };
  const projection = workspace.projectAssetObservation(rows, observation);
  assert.equal(projection.shareholders[0].name.provider, 'tinysoft');
  const card = html => html.match(/<article[^>]*id="shareholder-panel"[^>]*>[^]*?<\/article>/)?.[0] || '';
  const complete = card(workspace.renderAssetWorkspace({ observation, rows, route: route('holders') }));
  assert.match(complete, /合成股东甲/); assert.match(complete, /tinysoft · 已取得 · 2026-10-21/);
  assert.doesNotMatch(complete, /合成股东明细，仅用于渲染测试/);
  assert.match(workspace.renderAssetWorkspace({ observation, rows, route: route('holders') }), /合成股东明细，仅用于渲染测试/);
  assert.doesNotMatch(complete, /来源未取得/);
  const failed = { ...observation, blocks: { holder_details: { ...observation.blocks.holder_details, status: 'error', failure_code: 'provider_timeout' } } };
  const retained = card(workspace.renderAssetWorkspace({ observation: failed, rows, route: route('holders'), errors: { holder_details: '合成明细读取失败' } }));
  assert.match(retained, /合成股东甲/); assert.match(retained, /合成明细读取失败/);
  assert.match(retained, /下方保留上次快照，不表示刷新成功/);
  assert.match(retained, /缓存已过期/);
  const legacy = { ...observation, blocks: { shareholders: observation.blocks.holder_details } };
  const legacyCard = card(workspace.renderAssetWorkspace({ observation: legacy, rows: { shareholders: rows.holder_details }, route: route('holders') }));
  assert.match(legacyCard, /tinysoft · 完整 · 2026-10-21/);
  assert.match(workspace.renderAssetWorkspace({ observation: legacy, rows: { shareholders: rows.holder_details }, route: route('holders') }), /旧版股东明细限制：合成股东明细，仅用于渲染测试/);
});

test('news caches for sixty seconds then shows the snapshot during background refresh and failure', async () => {
  let time = 0; let calls = 0; let rejectRefresh;
  const states = [];
  const controller = createAssetNewsController({ now: () => time, onChange: () => states.push({ status: controller.state.status, title: controller.state.items[0]?.title }), fetcher: async () => {
    calls++;
    if (calls === 1) return { ok: true, json: async () => [{ title: '已保存新闻' }] };
    return new Promise((resolve, reject) => { rejectRefresh = reject; });
  } });
  await controller.activate(route('news'));
  time = 59999; await controller.activate(route('news')); assert.equal(calls, 1);
  time = 60000; const pending = controller.activate(route('news'));
  assert.equal(calls, 2);
  assert.deepEqual(states.at(-2), { status: 'complete', title: '已保存新闻' });
  assert.deepEqual(states.at(-1), { status: 'loading', title: '已保存新闻' });
  assert.match(renderAssetNews(controller.state), /已保存新闻/);
  rejectRefresh(new Error('上游读取失败')); await pending;
  assert.equal(controller.state.status, 'error');
  assert.match(renderAssetNews(controller.state), /上游读取失败.*保留上次读取内容/);
  assert.match(renderAssetNews(controller.state), /已保存新闻/);
});

test('same-asset tab route is handled before full-page reset and never scrolls anchors', async () => {
  const app = await readFile(new URL('../../app/research_web/ui/app.mjs', import.meta.url), 'utf8');
  const handler = app.slice(app.indexOf('async function showRoute()'), app.indexOf('async function loadConnectionConfiguration'));
  assert.ok(handler.indexOf('updateAssetTopic') > 0);
  assert.ok(handler.indexOf('updateAssetTopic') < handler.indexOf('await controller.open'));
  assert.doesNotMatch(app.slice(app.indexOf('function mountAssetIndicators()'), app.indexOf('const assetWorkspace =')), /scrollIntoView/);
});

test('non-history updates never reconfigure the existing chart or its selected date and viewport', async () => {
  const app = await readFile(new URL('../../app/research_web/ui/app.mjs', import.meta.url), 'utf8');
  const source = app.slice(app.indexOf('function configureAssetTerminal()'), app.indexOf('function setAssetMetricsDrawer('));
  const assetState = { observation: { asset: '600519.SH', asset_type: 'stock', blocks: { history: { dataset: { dataset_id: 'h1', asset_history: { canonical_version: 1 } } } } }, rows: { history: [{ date: '2026-10-20', close: 10 }] }, preferences: { panels: ['volume', 'macd'] } };
  const state = { route: route('overview') };
  const chartState = { selectedDate: '2026-10-20', start: 12, end: 80 }; let configurations = 0;
  const chart = { configure() { configurations++; return chartState; } };
  const metadata = observation => ({ frequency: 'daily', adjustment: 'qfq', historyJob: assetState.historyJob });
  const configure = new Function('assetState', 'state', 'assetChart', 'selectAssetObservation', 'assetTerminalMetadata', `const emptyAssetHistory = Object.freeze([]); let configuredAssetHistory = null; let configuredAssetSignature = ''; ${source}; return configureAssetTerminal;`)(assetState, state, chart, navigation.selectAssetObservation, metadata);
  configure(); assert.equal(configurations, 1);
  state.route = route('financials');
  assetState.observation = { ...assetState.observation, blocks: { ...assetState.observation.blocks, financials: { dataset: { dataset_id: 'f1' } } } };
  assetState.rows.financials = [{ revenue: 0 }];
  configure(); assert.equal(configurations, 1);
  assert.deepEqual(chartState, { selectedDate: '2026-10-20', start: 12, end: 80 });
  assetState.preferences = { panels: ['volume'] }; configure(); assert.equal(configurations, 2);
  assetState.rows.history = [...assetState.rows.history, { date: '2026-10-21', close: 11 }]; configure(); assert.equal(configurations, 3);
  assetState.observation.blocks.history.dataset.asset_history.canonical_version = 2; configure(); assert.equal(configurations, 4);
});

test('same-asset route executes only topic loaders and preserves the main scroll position', async () => {
  const app = await readFile(new URL('../../app/research_web/ui/app.mjs', import.meta.url), 'utf8');
  const source = app.slice(app.indexOf('async function showRoute()'), app.indexOf('async function loadConnectionConfiguration'));
  const state = { route: route('overview'), error: '' };
  const scroller = { scrollTop: 670, scrollTo() { throw new Error('tab navigation must not reset the main scroll'); } };
  const page = { dataset: { assetIdentity: 'stock:600519.SH' } };
  const calls = [];
  const bindings = { location: { hash: '#/assets?view=news&asset=600519.SH&asset_type=stock' }, history: {}, legacyRouteTarget: () => null, parseRoute: () => route('news'), root: { querySelector: () => page }, assetState: { observation: null, errors: {} }, isAssetPage: () => true, state, updateAssetTopic: () => calls.push('topic'), assetTopicProps: () => ({}), mountAssetTopicIndicators: () => calls.push('topic-chart'), assetWorkspace: { activateView: async () => calls.push('view-load') }, assetNews: { activate: async () => calls.push('news-load') }, safeLog: () => {}, paintAssetWorkspace: () => calls.push('summary'), document: { querySelector: () => scroller }, controller: { open() { throw new Error('full navigation must not execute'); } } };
  const show = new Function(...Object.keys(bindings), `let pageGeneration=1; let assetTopicNavigation=0; let workbenchBusy=false; ${source}; return showRoute;`)(...Object.values(bindings));
  await show();
  assert.equal(scroller.scrollTop, 670);
  assert.equal(state.route.assetView, 'news');
  assert.deepEqual(calls, ['topic', 'topic-chart', 'view-load', 'news-load', 'summary']);
});

test('actual app metadata preserves history source and reconfigures source-only changes before chart events', async () => {
  const { createAssetChartController } = await import('../../app/research_web/ui/asset-chart.mjs');
  const app = await readFile(new URL('../../app/research_web/ui/app.mjs', import.meta.url), 'utf8');
  const functions = app.slice(app.indexOf('function assetTerminalMetadata('), app.indexOf('function setAssetMetricsDrawer('));
  const requests = []; let configurations = 0;
  const chart = createAssetChartController({ onHistoryRequest: request => { requests.push(request); return false; } });
  const assetState = { observation: { id: 'o', asset: '600519.SH', asset_type: 'stock', source: 'baostock', request_parameters: { source: 'akshare', adjustment: 'none' }, blocks: { history: { dataset: { dataset_id: 'h', asset_history: { canonical_version: 'asset-history-raw-2', source: 'auto', adjustment: 'none' } } } } }, rows: { history: [{ date: '2026-10-20', open: 10, high: 12, low: 9, close: 11 }] }, preferences: { panels: [] } };
  const wrapped = { configure(...args) { configurations++; return chart.configure(...args); } };
  const { metadata, configure } = new Function('assetState', 'state', 'assetChart', 'selectAssetObservation', 'projectAssetObservation', `const emptyAssetHistory = Object.freeze([]); let configuredAssetHistory = null; let configuredAssetSignature = ''; ${functions}; return { metadata: assetTerminalMetadata, configure: configureAssetTerminal };`)(assetState, { route: route('overview') }, wrapped, navigation.selectAssetObservation, () => ({ basic: {} }));
  configure(); assert.equal(metadata().historySource, 'auto'); assert.equal(chart.getState().historySource, 'auto');
  const click = action => ({ type: 'click', target: { closest: selector => selector === '[data-asset-chart-action]' ? { dataset: { assetChartAction: action } } : null } });
  chart.handle(click('all')); assert.deepEqual(requests, []);
  delete assetState.observation.blocks.history.dataset.asset_history.source;
  delete assetState.observation.blocks.history.dataset.asset_history.canonical_version;
  configure(); assert.equal(configurations, 2); assert.equal(metadata().historySource, 'akshare'); assert.equal(chart.getState().historySource, 'akshare');
  chart.handle(click('all')); assert.deepEqual(requests, []);
  delete assetState.observation.request_parameters.source;
  configure(); assert.equal(configurations, 3); assert.equal(metadata().historySource, 'baostock');
  delete assetState.observation.source;
  configure(); assert.equal(configurations, 4); assert.equal(metadata().historySource, 'tinysoft'); assert.equal(chart.getState().historySource, 'tinysoft');
  chart.handle(click('all')); assert.deepEqual(requests.at(-1), { action: 'load', scope: 'all', adjustment: 'none', source: 'tinysoft' });
});

test('actual app and workspace preserve fixed Tinysoft for legacy canonical and reject unbound raw2 source', async () => {
  const { createAssetChartController } = await import('../../app/research_web/ui/asset-chart.mjs');
  const app = await readFile(new URL('../../app/research_web/ui/app.mjs', import.meta.url), 'utf8');
  const functions = app.slice(app.indexOf('function assetTerminalMetadata('), app.indexOf('function setAssetMetricsDrawer('));
  const observation = { id: 'o', asset: '600519.SH', asset_type: 'stock', source: 'auto', request_parameters: { source: 'auto', section_sources: { history: 'tinysoft' }, adjustment: 'qfq' }, blocks: { history: { dataset: { dataset_id: 'old', asset_history: { canonical_version: 'asset-history-1', adjustment: 'qfq' } } } } };
  const assetState = { observation, rows: { history: [{ date: '2026-10-20', open: 10, high: 12, low: 9, close: 11 }] }, preferences: { panels: [] } };
  const requests = []; const chart = createAssetChartController({ onHistoryRequest: request => { requests.push(request); return false; } });
  const { metadata, configure } = new Function('assetState', 'state', 'assetChart', 'selectAssetObservation', 'projectAssetObservation', `const emptyAssetHistory = Object.freeze([]); let configuredAssetHistory = null; let configuredAssetSignature = ''; ${functions}; return { metadata: assetTerminalMetadata, configure: configureAssetTerminal };`)(assetState, { route: route('overview') }, chart, navigation.selectAssetObservation, () => ({ basic: {} }));
  configure(); assert.equal(metadata().historySource, 'tinysoft'); assert.equal(chart.getState().adjustment, 'qfq');
  const html = workspace.renderAssetWorkspace({ ...props('overview'), observation, rows: assetState.rows });
  assert.match(html, /option value="tinysoft" selected/);
  const click = action => ({ type: 'click', target: { closest: selector => selector === '[data-asset-chart-action]' ? { dataset: { assetChartAction: action } } : null } });
  chart.handle(click('all')); assert.deepEqual(requests, [{ action: 'load', scope: 'all', adjustment: 'qfq', source: 'tinysoft' }]);
  observation.blocks.history.dataset = { dataset_id: 'incomplete-raw2', asset_history: { canonical_version: 'asset-history-raw-2', adjustment: 'none' } };
  configure(); assert.equal(metadata().historySource, 'unknown'); assert.equal(metadata().canLoadHistory, false);
  chart.handle(click('all')); assert.equal(requests.length, 1);
  const broken = workspace.renderAssetWorkspace({ ...props('overview'), observation, rows: assetState.rows });
  assert.match(broken, /来源未知/); assert.match(broken, /data-asset-history-source[^>]* disabled/);
});

test('actual app empty-history polling preserves requested source and pending until failure, then auto can be selected', async () => {
  const { createAssetChartController } = await import('../../app/research_web/ui/asset-chart.mjs');
  const app = await readFile(new URL('../../app/research_web/ui/app.mjs', import.meta.url), 'utf8');
  const functions = app.slice(app.indexOf('function assetTerminalMetadata('), app.indexOf('function setAssetMetricsDrawer('));
  const requests = []; let finish;
  const chart = createAssetChartController({ onHistoryRequest: request => { requests.push(request); return requests.length === 1 ? new Promise(resolve => { finish = resolve; }) : false; } });
  const assetState = { observation: { id: 'o', asset: '600519.SH', asset_type: 'stock', source: 'auto', request_parameters: { source: 'auto', adjustment: 'none' }, blocks: { history: { dataset: null } } }, rows: { history: [] }, preferences: { panels: [] } };
  const state = { route: route('overview') };
  const configure = new Function('assetState', 'state', 'assetChart', 'selectAssetObservation', 'projectAssetObservation', `const emptyAssetHistory = Object.freeze([]); let configuredAssetHistory = null; let configuredAssetSignature = ''; ${functions}; return configureAssetTerminal;`)(assetState, state, chart, navigation.selectAssetObservation, () => ({ basic: {} }));
  const choose = value => chart.handle({ type: 'change', target: { value, matches: selector => selector === '[data-asset-history-source]' } });
  configure(); choose('tinysoft'); assert.equal(chart.getState().historySource, 'tinysoft'); assert.equal(chart.getState().historyRequestPending, true);
  assetState.historyJob = { status: 'queued', source: 'tinysoft', scope: 'recent', adjustment: 'none' }; configure();
  assert.equal(chart.getState().historySource, 'tinysoft'); assert.equal(chart.getState().historyRequestPending, true);
  assetState.historyJob = { ...assetState.historyJob, status: 'failed', failure_code: 'provider_error', retryable: true }; configure();
  assert.equal(chart.getState().historySource, 'tinysoft'); assert.equal(chart.getState().historyRequestPending, false);
  finish(false); await Promise.resolve(); choose('auto');
  assert.deepEqual(requests.map(request => request.source), ['tinysoft', 'auto']);
  assetState.rows.history = Array.from({ length: 160 }, (_, index) => ({ date: new Date(Date.UTC(2026, 0, index + 1)).toISOString().slice(0, 10), open: 10, high: 12, low: 9, close: 11 }));
  assetState.observation.blocks.history.dataset = { dataset_id: 'first', asset_history: { canonical_version: 'asset-history-raw-2', source: 'auto', adjustment: 'none' } };
  assetState.historyJob = { status: 'completed', source: 'auto' }; configure();
  assert.equal(chart.getState().start, 40); assert.equal(chart.getState().end, 160); assert.equal(chart.getState().selectedDate, assetState.rows.history.at(-1).date);
  state.route = { ...route('overview'), asset: '000001.SZ' }; assetState.observation = { id: 'new', asset: '000001.SZ', asset_type: 'stock', source: 'tinysoft', request_parameters: { adjustment: 'qfq' }, blocks: {} }; assetState.rows.history = []; configure();
  assert.equal(chart.getState().historySource, 'tinysoft'); assert.equal(chart.getState().adjustment, 'qfq'); assert.equal(chart.getState().historyRequestPending, false);
});
