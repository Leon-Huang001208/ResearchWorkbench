import assert from 'node:assert/strict';
import test from 'node:test';
import { createAPI, isDataWorkspaceRoute, parseRoute } from '../../app/research_web/ui/core.mjs';
import { secondaryEntries } from '../../app/research_web/ui/module-navigation.mjs';
import { createEventResearchWorkspace, createStrategyValidation } from '../../app/research_web/ui/strategy-validation.mjs';

const dataset = { id: 'd1', name: '<img onerror=alert(1)>', sha256: 'a'.repeat(64) };
const run = { id: 'r1', dataset_id: 'd1', horizon: 5, created_at: '2026-11-16T03:00:00Z' };
const detail = {
  ...run,
  rules: [
    { id: 'volume_stall', signal_count: 1063, downside: { n: 1050, events: 496, rate: 496 / 1050, ci95: [.45, .50] },
      sale: { n: 1059, events: 551, rate: 551 / 1059, mean: -.00602, ci_effect: [-.016, .0013] },
      matched: { n: 899, trigger_mean: .0061, control_mean: .0058, mean: .000367 } },
    { id: 'sma5_close', signal_count: 23111, downside: { n: 0, events: 0, rate: null } },
  ],
  coverage: { first_market_session: '2022-01-04', last_market_session: '2026-11-13', ticker_count: 160, raw_rows: 200820 },
  configuration: {
    dataset_id: 'd1', rules: ['volume_stall', 'sma5_close'], horizon: 5, high_window: 60,
    volume_ratio: 1.75, near_high_pct: 2, ma_previous_gap_pct: 3, ma_close_gap_pct: 2.5, sell_cost_bps: 9,
  },
};
const deferred = () => {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
};

const pageRoot = selector => selector === '.strategy-validation' ? {} : null;
function submit(kind) {
  return { type: 'submit', target: { closest: pageRoot, matches: selector => selector === `[data-strategy-${kind}]` }, preventDefault() {} };
}
function change(name, value, extras = {}) {
  return { type: 'change', target: { closest: pageRoot, name, value, ...extras } };
}
function click(data) {
  return { type: 'click', target: { closest: selector => selector === '.strategy-validation' ? {} : { dataset: data } } };
}

test('strategy route selects its navigation and leaves simulation siblings independent', () => {
  const route = parseRoute('#/simulation/strategies');
  assert.equal(route.simulationView, 'strategies');
  assert.equal(isDataWorkspaceRoute(route), false);
  assert.deepEqual(secondaryEntries(route).filter(row => row.active).map(row => row.href), ['#/simulation/strategies']);
  assert.equal(parseRoute('#/simulation/events').simulationView, 'events');
  assert.equal(isDataWorkspaceRoute(parseRoute('#/simulation/etf')), true);
});

test('research workspace visits the correct controller and leaves ETF requests to its page', async () => {
  let route = parseRoute('#/simulation/etf');
  const reads = [];
  const workspace = createEventResearchWorkspace({
    getRoute: () => route,
    onChange: () => {},
    api: {
      request: async path => { reads.push(path); return { items: [] }; },
      strategyValidation: async () => { reads.push('/strategy-validation'); return { datasets: [], runs: [] }; },
    },
  });
  assert.equal(workspace.isActiveRoute(), false);
  assert.equal(workspace.showsEtfErrors(), true);
  assert.equal(workspace.activate(), undefined);
  assert.equal(workspace.render(), '');
  assert.equal(workspace.owns({ target: { closest: () => null } }), false);
  assert.deepEqual(reads, []);
  for (const [href, endpoint, title] of [
    ['#/intel/timeline', '/events?', '事件时间线'],
    ['#/simulation/events', '/event-studies', '事件与日历研究'],
    ['#/simulation/scores', '/market-scores/runs', '六维评分'],
    ['#/simulation/strategies', '/strategy-validation', '策略验证'],
  ]) {
    workspace.deactivate();
    route = parseRoute(href);
    reads.length = 0;
    assert.equal(workspace.isActiveRoute(), true);
    await workspace.activate();
    assert.ok(reads[0].startsWith(endpoint), href);
    assert.match(workspace.render(), new RegExp(`<h1>${title}</h1>`));
  }
  assert.equal(workspace.showsEtfErrors(), false);
  assert.equal(workspace.owns(click({ strategyAction: 'reload' })), true);
  assert.equal(await workspace.handle(click({ strategyAction: 'reload' })), true);
  assert.deepEqual(reads, ['/strategy-validation', '/strategy-validation']);
});

test('archive is sent as raw ZIP with intent and run uses an explicit idempotency key', async () => {
  const calls = [];
  const api = createAPI({
    fetcher: async (url, options) => { calls.push({ url, ...options }); return new Response('{}'); },
    logger: () => {},
  });
  const bytes = new Uint8Array([0x50, 0x4B, 0x03, 0x04, 0xFF]);
  await api.strategyValidationImport(new Blob([bytes], { type: 'application/x-zip-compressed' }));
  await api.strategyValidationRun({ dataset_id: 'd1', rules: ['volume_stall'], horizon: 5 }, 'research-button-one');
  await api.strategyValidationEvents('r /1', 'sma5_close', 50, 50);
  assert.equal(calls[0].url, '/api/research/strategy-validation/datasets');
  assert.equal(calls[0].headers['Content-Type'], 'application/zip');
  assert.equal(calls[0].headers['X-Research-User-Action'], '?1');
  assert.deepEqual(new Uint8Array(await calls[0].body.arrayBuffer()), bytes);
  assert.equal(calls[1].headers['Idempotency-Key'], 'research-button-one');
  assert.equal(calls[1].headers['X-Research-User-Action'], '?1');
  assert.equal(calls[1].headers['Content-Type'], 'application/json');
  assert.equal(calls[2].url, '/api/research/strategy-validation/runs/r%20%2F1/events?rule=sma5_close&offset=50&limit=50');
  assert.equal(calls[2].headers['X-Research-User-Action'], undefined);
});

test('configured run shows actual rate denominators, effect, comparison, and bounded event pages', async () => {
  const calls = [];
  const view = createStrategyValidation({
    api: {
      strategyValidation: async () => ({ datasets: [dataset], runs: [] }),
      strategyValidationRun: async (body, key) => { calls.push({ body, key }); return run; },
      strategyValidationDetail: async () => detail,
      strategyValidationEvents: async (id, rule, offset, limit) => {
        calls.push({ id, rule, offset, limit });
        return { offset, limit, total: 51, items: Array.from({ length: offset === 0 ? 50 : 1 }, (_, index) => ({
          date: '2022-01-04', ticker: `<code>${offset + index}</code>`, hold_return: .0123,
          sell_advantage: -.0121, open_executable: false, control_ticker: '000002.SZ', control_return: .002,
        })) };
      },
    },
    makeKey: () => 'research-key',
  });
  await view.activate();
  await view.handle(change('horizon', '10'));
  await view.handle(change('rules', 'sma20_close', { checked: false }));
  await view.handle(change('volume_ratio', '1.31'));
  assert.equal(calls.length, 0);
  await view.handle(submit('config'));
  assert.deepEqual(calls[0], { key: 'research-key', body: {
    dataset_id: 'd1', rules: ['volume_stall', 'sma5_close', 'sma10_close'], horizon: 10, volume_ratio: 1.31,
    high_window: 20, near_high_pct: 2, ma_previous_gap_pct: 3, ma_close_gap_pct: 2.5, sell_cost_bps: 10,
  } });
  assert.deepEqual(calls[1], { id: 'r1', rule: 'volume_stall', offset: 0, limit: 50 });
  const output = view.render();
  assert.match(output, /52\.03%（551 \/ 1,059）/);
  assert.match(output, /-0\.602/);
  assert.match(output, /95% 区间 45\.00% 至 50\.00%/);
  assert.match(output, /0 笔可计算/);
  assert.match(output, /不可按假设成交/);
  assert.match(output, /000002\.SZ/);
  const historical = output.match(/<details data-strategy-run-configuration>[\s\S]*?<\/details>/)?.[0] || '';
  assert.match(historical, /本次运行参数/);
  assert.match(historical, /放量倍数<\/dt><dd>1\.75<\/dd>/);
  assert.match(historical, /观察期限（交易日）<\/dt><dd>5<\/dd>/);
  assert.match(output, /id="strategy-volume_ratio"[^>]*value="1\.31"/);
  assert.match(output, /&lt;code&gt;0&lt;\/code&gt;/);
  assert.doesNotMatch(output, /<img onerror|<code>0<\/code>/);
  await view.handle(click({ strategyOffset: '50' }));
  assert.match(view.render(), /第 51–51 笔，共 51 笔/);
  assert.match(view.render(), /id="strategy-events-next"[^>]* disabled/);
  await view.handle(change('', 'sma5_close', { matches: s => s === '[data-strategy-event-rule]' }));
  assert.deepEqual(calls.at(-1), { id: 'r1', rule: 'sma5_close', offset: 0, limit: 50 });
});

test('only an explicit retry of the same run reuses its idempotency key', async () => {
  const submitted = [], pending = deferred();
  let serial = 0;
  const view = createStrategyValidation({
    makeKey: () => `run-key-${++serial}`,
    api: {
      strategyValidation: async () => ({ datasets: [dataset], runs: [] }),
      strategyValidationRun: (body, key) => {
        submitted.push({ body, key });
        if (submitted.length === 1) return pending.promise;
        throw Error('尚未确认');
      },
    },
  });
  await view.activate();
  const first = view.handle(submit('config'));
  await view.handle(submit('config'));
  assert.equal(submitted.length, 1);
  pending.reject(Error('请求结果未知'));
  await first;
  assert.match(view.render(), /手动重试/);
  assert.equal(submitted.length, 1);
  await view.handle(submit('config'));
  assert.equal(submitted[1].key, submitted[0].key);
  await view.handle(change('horizon', '1'));
  await view.handle(submit('config'));
  assert.notEqual(submitted[2].key, submitted[0].key);
});

test('explicit ZIP import selects the returned frozen dataset without running research', async () => {
  const imported = [];
  const file = Object.assign(new Blob(['PK']), { name: '<archive>.zip' });
  const view = createStrategyValidation({
    api: {
      strategyValidation: async () => ({ datasets: [], runs: [] }),
      strategyValidationImport: async value => { imported.push(value); return dataset; },
      strategyValidationRun: () => assert.fail('import must not trigger a run'),
    },
  });
  await view.activate();
  await view.handle(change('archive', '', { files: [file] }));
  assert.equal(imported.length, 0);
  await view.handle(submit('import'));
  assert.deepEqual(imported, [file]);
  assert.equal(view.state.draft.dataset_id, 'd1');
  assert.equal(view.state.file, null);
  assert.match(view.render(), /冻结行情已导入/);
});

test('route and account changes fence late results and prevent private re-render', async () => {
  let owner = 'user-a';
  const oldHistory = deferred(), running = deferred();
  let loads = 0;
  const view = createStrategyValidation({
    getIdentity: () => owner,
    makeKey: () => 'same-account-request-key',
    api: {
      strategyValidation: () => ++loads === 1 ? oldHistory.promise : Promise.resolve({ datasets: [dataset], runs: [] }),
      strategyValidationRun: () => running.promise,
      strategyValidationDetail: () => assert.fail('a late write cannot open a result in another view'),
    },
  });
  const first = view.activate();
  view.deactivate();
  await view.activate();
  oldHistory.resolve({ datasets: [{ id: 'expired' }], runs: [] });
  await first;
  assert.equal(view.state.draft.dataset_id, 'd1');
  const oldWrite = view.handle(submit('config'));
  view.deactivate();
  running.resolve(run);
  await oldWrite;
  assert.equal(view.state.detail, null);
  assert.equal(view.state.runs.length, 0);
  assert.equal(view.state.busy, '');
  owner = 'user-b';
  assert.doesNotMatch(view.render(), /&lt;img/);
  await view.activate();
  assert.equal(view.state.detail, null);
});

test('same-account return during a run rereads history as soon as the run settles', async () => {
  const running = deferred();
  const keys = [];
  let saved = [], reads = 0;
  const view = createStrategyValidation({
    makeKey: () => `research-${keys.length + 1}`,
    api: {
      strategyValidation: async () => { reads += 1; return { datasets: [dataset], runs: saved }; },
      strategyValidationRun: (_body, key) => { keys.push(key); return running.promise; },
      strategyValidationDetail: async () => detail,
      strategyValidationEvents: async () => ({ items: [], offset: 0, limit: 50, total: 0 }),
    },
  });
  await view.activate();
  const submitted = view.handle(submit('config'));
  view.deactivate();
  await view.activate();
  assert.match(view.render(), /正在计算/);
  assert.equal(reads, 1);
  saved = [run];
  running.resolve(run);
  await submitted;
  assert.equal(reads, 2);
  assert.equal(keys.length, 1);
  assert.match(view.render(), /data-strategy-run="r1"/);
  await view.handle(click({ strategyRun: 'r1' }));
  assert.equal(view.state.detail?.id, 'r1');
});

test('a returned run keeps its request key when the refreshed history does not show its result', async () => {
  const running = deferred();
  const keys = [];
  let reads = 0;
  const view = createStrategyValidation({
    makeKey: () => `research-${keys.length + 1}`,
    api: {
      strategyValidation: async () => {
        reads += 1;
        if (reads === 2) throw Error('历史暂不可读');
        return { datasets: [dataset], runs: [] };
      },
      strategyValidationRun: (_body, key) => {
        keys.push(key);
        if (keys.length === 1) return running.promise;
        throw Error('响应暂不可读');
      },
    },
  });
  await view.activate();
  const submitted = view.handle(submit('config'));
  view.deactivate();
  await view.activate();
  running.resolve(run);
  await submitted;
  assert.match(view.render(), /历史暂不可读/);
  await view.handle(submit('config'));
  assert.equal(keys[1], keys[0]);
});

test('a failed write after returning shows the unknown result and requires an explicit retry', async () => {
  const running = deferred();
  const keys = [];
  let reads = 0;
  const view = createStrategyValidation({
    makeKey: () => `research-${keys.length + 1}`,
    api: {
      strategyValidation: async () => { reads += 1; return { datasets: [dataset], runs: [] }; },
      strategyValidationRun: (_body, key) => {
        keys.push(key);
        return keys.length === 1 ? running.promise : Promise.reject(Error('仍未确认'));
      },
    },
  });
  await view.activate();
  const submitted = view.handle(submit('config'));
  view.deactivate();
  await view.activate();
  running.reject(Error('运行结果未确认'));
  await submitted;
  assert.equal(reads, 2);
  assert.equal(keys.length, 1);
  assert.match(view.render(), /运行结果未确认.*手动重试/);
  await view.handle(submit('config'));
  assert.equal(keys[1], keys[0]);
});

test('an old account acknowledgement does not refresh or populate another account history', async () => {
  const running = deferred();
  let owner = 'account-a', reads = 0;
  const view = createStrategyValidation({
    getIdentity: () => owner,
    makeKey: () => 'old-account-run',
    api: {
      strategyValidation: async () => {
        reads += 1;
        return { datasets: owner === 'account-a' ? [dataset] : [], runs: [] };
      },
      strategyValidationRun: () => running.promise,
    },
  });
  await view.activate();
  const submitted = view.handle(submit('config'));
  owner = 'account-b';
  view.deactivate();
  await view.activate();
  running.resolve(run);
  await submitted;
  assert.equal(reads, 2);
  assert.deepEqual(view.state.runs, []);
  assert.deepEqual(view.state.datasets, []);
});
