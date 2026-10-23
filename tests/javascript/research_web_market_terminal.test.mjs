import assert from 'node:assert/strict';
import test from 'node:test';
import { createTerminalController, decisionStrip, evidencePanels, indexCollection, newPortfolioDraft, portfolioPayload, portfolioPanel, terminalIndices } from '../../app/research_web/ui/market-terminal.mjs';

const catalog = { items: [{ asset: '932000.SH', name: '中证2000', group: 'scale' }, { asset: '000824.SH', name: '国企红利', group: 'dividend' }], default_pins: ['932000.SH'], groups: [{ id: 'scale', label: '规模' }, { id: 'dividend', label: '红利' }] };
const tick = () => new Promise(resolve => setImmediate(resolve));
function harness(request, saved = null, options = {}) {
  const state = {}, writes = [], calls = [], renders = [];
  const api = { request: (path, options) => { calls.push({ path, options }); return request(path, options); } };
  const controller = createTerminalController({ state, api, changed() { renders.push(portfolioPanel(state)); options.changed?.(); }, visible: options.visible || (() => true), storage: { getItem: () => saved, setItem: (...args) => writes.push(args) } });
  return { state, controller, calls, writes, renders };
}
function base(path) { return Promise.resolve(path.includes('catalog') ? catalog : path.includes('portfolios') ? { items: [] } : { axes: {}, validation: { status: 'insufficient_evidence' } }); }
function validDraft() { return { ...newPortfolioDraft(), as_of: '2026-10-22', cash: '0', holdings: [{ asset: '000001.sz', quantity: '100', cost: '10' }] }; }

test('catalog uses canonical terminal snapshot and explicit legacy fallback', () => {
  const legacy = { rows: [{ asset: '000001.SH' }] }, terminal = { rows: [{ asset: '932000.SH' }] };
  assert.equal(terminalIndices({ snapshot: { sections: { indices: legacy } } }), legacy);
  assert.equal(terminalIndices({ snapshot: { sections: { indices: legacy, 'indices:terminal-v2': terminal } } }), terminal);
  const html = indexCollection({ catalog, indexGroup: 'all', snapshot: { sections: { 'indices:terminal-v2': terminal } } });
  assert.match(html, /932000.SH/); assert.match(html, /000824.SH/); assert.match(html, /行情待取得/);
  assert.doesNotMatch(html, /932000.CSI|>0%/);
});

test('pins restore only allowlisted assets, persist account key and reset defaults', async () => {
  const h = harness(base, JSON.stringify(['000824.SH', 'bad'])); await h.controller.activate();
  assert.deepEqual(h.state.pins, ['000824.SH']);
  h.controller.click({ marketAction: 'pin', asset: '932000.SH' });
  assert.deepEqual(h.state.pins, ['000824.SH', '932000.SH']);
  assert.match(h.writes[0][0], /rwb:.*:market-pins-terminal-v2/);
  h.controller.click({ marketAction: 'pins-reset' }); assert.deepEqual(h.state.pins, ['932000.SH']);
  h.controller.click({ marketAction: 'pin', asset: 'bad' }); assert.deepEqual(h.state.pins, ['932000.SH']);
});

test('valid descriptive scores render while total and allocation remain pending', () => {
  const state = { horizon: 'swing', analysis: { total_score: 89, allocation: { equity: .8 }, axes: { risk: { score: 12.5, status: 'observed', metrics: { volatility: .3 }, formula: 'inverse_rank', provenance: [{ source: '<supplier>' }] } } } };
  const html = evidencePanels(state); assert.match(html, /12.5/); assert.match(html, /inverse_rank/); assert.match(html, /volatility/); assert.match(html, /&lt;supplier&gt;/);
  assert.match(html, /axis-valuation/); assert.match(html, /数据待取得/); assert.doesNotMatch(html, /<supplier>/);
  const strip = decisionStrip(state); assert.match(strip, /待验证/); assert.doesNotMatch(strip, /89|80%/); assert.match(strip, /5—20/);
});

test('horizon response fencing discards an older analysis after a later selection', async () => {
  const deferred = new Map(), h = harness(path => path.includes('analysis') ? new Promise(resolve => deferred.set(path.split('=')[1], resolve)) : base(path));
  const activation = h.controller.activate();
  h.controller.click({ marketAction: 'horizon', horizon: 'allocation' });
  deferred.get('allocation')({ id: 'new' }); await tick(); deferred.get('intraday')({ id: 'old' }); await activation;
  assert.equal(h.state.horizon, 'allocation'); assert.equal(h.state.analysis.id, 'new');
});

test('risk profile requires explicit bounds and cost is optional with zero preserved', () => {
  const draft = validDraft(), payload = portfolioPayload(draft); assert.equal(payload.cash, 0); assert.equal(payload.holdings[0].asset, '000001.SZ'); assert.equal(payload.holdings[0].cost, 10); assert.equal(payload.risk_profile, undefined);
  draft.risk_tolerance = 'conservative'; assert.throws(() => portfolioPayload(draft), /有效数值/);
  Object.assign(draft, { equity_min: '0', equity_max: '50', single_name_max: '10', sector_max: '25' });
  assert.deepEqual(portfolioPayload(draft).risk_profile, { risk_tolerance: 'conservative', equity_min: 0, equity_max: .5, single_name_max: .1, sector_max: .25 });
  draft.equity_min = '60'; assert.throws(() => portfolioPayload(draft), /下限/);
});

test('late portfolio preview cannot authorize confirmation after the draft changes', async () => {
  let finish;
  const h = harness((path, options) => options?.method === 'POST' ? new Promise(resolve => { finish = resolve; }) : base(path));
  await h.controller.activate(); h.state.portfolioDraft = validDraft();
  const work = h.controller.preview(); await tick();
  h.controller.input({ dataset: { marketHolding: 'quantity', row: '0' }, value: '200' });
  finish({ confirmation_token: 'old', snapshot: { quantity: 100 } }); await work;
  assert.equal(h.state.portfolioPreview, null); await h.controller.confirm();
  assert.equal(h.calls.filter(call => call.options?.method === 'POST').length, 1);
});

test('CSV import previews raw text then requires a separate explicit confirmation', async () => {
  const h = harness((path, options) => options?.method === 'POST' ? Promise.resolve(path.endsWith('preview') ? { confirmation_token: 'token', snapshot: { cash: 0 } } : { snapshot_id: 'saved', as_of: '2026-10-22' }) : base(path));
  await h.controller.activate(); h.state.portfolioDraft = { ...validDraft(), source: 'csv', csv_text: 'asset,quantity\n000001.SZ,100' };
  await h.controller.preview(); assert.equal(h.calls.filter(call => call.options?.method === 'POST').length, 1);
  const previewCall = h.calls.find(call => call.path.endsWith('preview')); assert.equal(previewCall.options.body.csv_text, h.state.portfolioDraft.csv_text); assert.equal(previewCall.options.body.holdings, undefined);
  assert.doesNotMatch(portfolioPanel(h.state), /confirmation_token|>token</);
  await h.controller.confirm(); assert.deepEqual(h.calls.at(-1).options.body, { confirmation_token: 'token' }); assert.equal(h.state.portfolios.items[0].snapshot_id, 'saved');
});

test('cancelling activation suppresses late catalog and portfolio responses', async () => {
  const resolutions = [], h = harness(() => new Promise(resolve => resolutions.push(resolve)));
  const activation = h.controller.activate(); h.controller.cancel(); resolutions.forEach(resolve => resolve(catalog)); await activation;
  assert.equal(h.state.catalog, undefined); assert.equal(h.state.portfolios, undefined); assert.equal(h.state.analysis, undefined);
});

test('raw API errors are visible and file reads cannot replace a later user edit', async () => {
  const h = harness(path => path.includes('analysis') ? Promise.reject(new Error('provider_cache_invalid')) : base(path)); await h.controller.activate();
  assert.match(evidencePanels(h.state), /provider_cache_invalid/);
  let finish; const work = h.controller.file({ files: [{ size: 10, text: () => new Promise(resolve => { finish = resolve; }) }] });
  h.controller.input({ dataset: { marketPortfolio: 'csv_text' }, value: 'new text' }); finish('old text'); await work;
  assert.equal(h.state.portfolioDraft.csv_text, 'new text');
});

test('account changes reset private drafts and fence responses from the previous account', async () => {
  const previous = globalThis.__RWB_USER_ID__;
  try {
    globalThis.__RWB_USER_ID__ = 'account-a';
    const h = harness(base); await h.controller.activate(); h.state.portfolioDraft = validDraft();
    h.controller.click({ marketAction: 'pin', asset: '000824.SH' });
    assert.match(h.writes.at(-1)[0], /account-a/);
    globalThis.__RWB_USER_ID__ = 'account-b'; await h.controller.activate();
    assert.equal(h.state.portfolioDraft.cash, ''); assert.equal(h.state.portfolioDraft.holdings[0].asset, '');
    h.controller.click({ marketAction: 'pins-reset' }); assert.match(h.writes.at(-1)[0], /account-b/);
    let finish;
    // Simulate an in-flight read through the public analysis path, then switch without activating.
    const delayed = harness(path => path.includes('analysis') ? new Promise(resolve => { finish = resolve; }) : base(path));
    const active = delayed.controller.activate(); globalThis.__RWB_USER_ID__ = 'account-c'; finish({ private_marker: 'b' }); await active;
    assert.equal(delayed.state.analysis, undefined);
  } finally { if (previous === undefined) delete globalThis.__RWB_USER_ID__; else globalThis.__RWB_USER_ID__ = previous; }
});

test('editing a pending preview immediately renders an enabled button and preserves the entered value', async () => {
  let finish;
  const h = harness((path, options) => options?.method === 'POST' ? new Promise(resolve => { finish = resolve; }) : base(path));
  await h.controller.activate(); h.state.portfolioDraft = validDraft();
  const work = h.controller.preview(); assert.match(h.renders.at(-1), /<button type="submit" disabled>处理中/);
  h.controller.input({ dataset: { marketHolding: 'quantity', row: '0' }, value: '200' });
  assert.match(h.renders.at(-1), /<button type="submit" >校验并预览/);
  assert.match(h.renders.at(-1), /id="market-holding-0-quantity"[^>]*value="200"/);
  finish({ confirmation_token: 'stale' }); await work;
  assert.match(h.renders.at(-1), /<button type="submit" >校验并预览/);
  assert.equal(h.state.portfolioPreview, null);
});

test('inactive, hidden and changed-account controllers never send private drafts, old tokens or file reads', async () => {
  const previous = globalThis.__RWB_USER_ID__;
  try {
    for (const action of ['deactivate', 'hide', 'account']) {
      globalThis.__RWB_USER_ID__ = 'private-account-a'; let visible = true, fileReads = 0;
      const h = harness(base, null, { visible: () => visible });
      await h.controller.activate(); h.state.portfolioDraft = validDraft();
      h.state.portfolioPreview = { confirmation_token: 'old-account-token' };
      if (action === 'deactivate') h.controller.cancel();
      if (action === 'hide') visible = false;
      if (action === 'account') globalThis.__RWB_USER_ID__ = 'private-account-b';
      await h.controller.confirm(); await h.controller.preview();
      await h.controller.file({ files: [{ size: 1, async text() { fileReads++; return 'private'; } }] });
      assert.equal(h.calls.filter(call => call.options?.method === 'POST').length, 0, action);
      assert.equal(fileReads, 0, action);
    }
  } finally { if (previous === undefined) delete globalThis.__RWB_USER_ID__; else globalThis.__RWB_USER_ID__ = previous; }
});

test('send-time guard rechecks lifecycle after the busy render before a POST or local file read', async () => {
  let block = false, visible = true, fileReads = 0;
  const h = harness(base, null, { visible: () => visible, changed: () => { if (block) visible = false; } });
  await h.controller.activate(); h.state.portfolioDraft = validDraft(); block = true;
  await h.controller.preview(); assert.equal(h.calls.filter(call => call.options?.method === 'POST').length, 0);
  visible = true; h.state.portfolioBusy = false; h.state.portfolioPreview = { confirmation_token: 'old' };
  await h.controller.confirm(); assert.equal(h.calls.filter(call => call.options?.method === 'POST').length, 0);
  visible = true;
  await h.controller.file({ files: [{ size: 1, async text() { fileReads++; return 'private'; } }] });
  assert.equal(fileReads, 0);
});

test('saved snapshots and validation diagnostics expose stable disclosure identities', () => {
  const first = portfolioPanel({ portfolios: { items: [{ snapshot_id: 'snapshot-a', as_of: '2026-10-22' }] } });
  const second = portfolioPanel({ portfolios: { items: [{ snapshot_id: 'snapshot-b', as_of: '2026-10-23' }, { snapshot_id: 'snapshot-a', as_of: '2026-10-22' }] } });
  assert.match(first, /data-disclosure-key="market-portfolio-snapshot-snapshot-a"/);
  assert.match(second, /data-disclosure-key="market-portfolio-snapshot-snapshot-a"/);
  assert.match(evidencePanels({}), /data-disclosure-key="market-validation-diagnostics"/);
});

function styleProfile(horizon, value, complete = true) {
  const cells = ['399372.SZ', '399373.SZ', '399374.SZ', '399375.SZ', '399376.SZ', '399377.SZ'].map(asset => ({ asset, status: 'observed', return_pct: value, provenance: { quote_as_of: '2026-10-23T11:00:00+08:00', base_date: '2026-09-23' } }));
  if (!complete) Object.assign(cells[0], { status: 'unavailable', return_pct: null, reason: '历史不足' });
  return { horizon, cells, status: complete ? 'observed' : 'incomplete', style_dominance: complete ? 'growth' : 'unknown', size_dominance: complete ? 'small' : 'unknown', growth_minus_value_pp: complete ? .2 : null, rule: 'official-six-price-index', micro: { status: 'unavailable', reason: '微盘尚无核验配对' } };
}

test('style cells follow intraday, 20-session and 60-session backend returns rather than current quote changes', () => {
  for (const [horizon, value, label] of [['intraday', 1.23, '当日涨跌幅'], ['swing', 12.34, '近20个交易日价格收益'], ['allocation', 23.45, '近60个交易日价格收益']]) {
    const state = { horizon, analysis: { style_profile: styleProfile(horizon, value) }, snapshot: { sections: { indices: { rows: [{ asset: '399372.SZ', name: '大盘成长', change_pct: 99.99 }] } } } };
    const html = evidencePanels(state);
    assert.match(html, new RegExp(label)); assert.match(html, new RegExp(`>${value}%</strong>`)); assert.doesNotMatch(html, /99.99%/);
    assert.match(html, /official-six-price-index/); assert.match(html, /2026-09-23/); assert.match(html, /微盘尚无核验配对/);
    const strip = decisionStrip(state); assert.match(strip, /成长相对领先/); assert.match(strip, /小盘相对领先/); assert.match(strip, /择时结论待验证/);
  }
});

test('missing history and stale-horizon style cells remain unknown without daily-return fallback', () => {
  for (const profile of [styleProfile('intraday', 7.77), styleProfile('swing', 7.77, false), undefined]) {
    const state = { horizon: 'swing', analysis: { style_profile: profile } }, strip = decisionStrip(state);
    assert.match(strip, /成长／价值待确认/); assert.match(strip, /规模待确认/); assert.doesNotMatch(strip, /相对领先|差异较小/);
    const html = evidencePanels(state);
    assert.match(html, /market-style-cell/); assert.match(html, />—<\/strong>/);
    if (profile?.horizon !== 'swing') assert.doesNotMatch(html, /7.77%/);
  }
});

test('CSV file size limit matches the 256 KiB server contract before reading local contents', async () => {
  let reads = 0;
  const h = harness(base); await h.controller.activate();
  await h.controller.file({ files: [{ size: 256 * 1024 + 1, async text() { reads++; return 'private'; } }] });
  assert.equal(reads, 0); assert.match(h.state.portfolioError, /256 KiB/);
});

test('participation identifies its source, full quote timestamp and stale or incomplete cache', () => {
  const quotes = { snapshot_id: 'quote-old', provider: 'eastmoney', as_of: '2026-10-22T03:00:00Z', complete: true, summary: { up: 1, down: 1, flat: 0, unknown: 0 } };
  const state = { snapshot: { sections: { quotes } }, analysis: { cache_state: { quotes: { status: 'stale', stale: true, snapshot_id: 'quote-old' } } } };
  let html = decisionStrip(state);
  assert.match(html, /快照市场参与度/); assert.doesNotMatch(html, /当前市场参与度/);
  assert.match(html, /50% 上涨/); assert.match(html, /东方财富 · 行情 2026-10-22T03:00:00Z · 陈旧快照/);
  state.analysis = {}; state.snapshot.sections.quotes = { ...quotes, stale: true };
  assert.match(decisionStrip(state), /陈旧快照/);
  state.snapshot.sections.quotes = { ...quotes, complete: false };
  html = decisionStrip(state); assert.match(html, /未完整 · 保留数据缺口/); assert.doesNotMatch(html, /· 缓存快照/);
});
