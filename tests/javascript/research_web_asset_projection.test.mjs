import assert from 'node:assert/strict';
import test from 'node:test';
import { projectAssetObservation } from '../../app/research_web/ui/asset-projection.mjs';

const project = (rows = {}, blocks = {}, extra = {}) => projectAssetObservation(rows, { ...extra, blocks });
const snapshot = (provider, extra = {}) => ({ status: 'complete', dataset: { provider, ...extra } });

test('uncollected sections do not claim a global source or date range was requested', () => {
  const p = project({ overview: [{ price: 2 }] }, { overview: snapshot('tinysoft', { dataset_id: 'quote' }) }, { source: 'tinysoft', request_parameters: { start_date: '2026-09-01', end_date: '2026-10-21', frequency: 'daily', adjustment: 'qfq' } });
  for (const row of p.coverageRows.filter(item => item.id !== 'overview')) {
    assert.equal(row.requestedSource, null, row.id);
    assert.equal(row.requestedRange, null, row.id);
    assert.equal(row.requestedFrequency, null, row.id);
    assert.equal(row.hasSnapshot, false, row.id);
  }
  assert.equal(p.coverageRows[0].requestedSource, 'tinysoft');
});

test('valuation keeps plain PB separate from PB-MRQ and preserves zero with provenance', () => {
  const p = project({ valuation: [{ date: '2026-10-20', pe_ttm: 0, pb: 0, ps_ttm: 0, total_shares: 0, market_cap: 0 }], financials: [{ report_period: '2026-06-30', pb_mrq: 7 }] }, {
    valuation: snapshot('vendor', { fields: [{ name: 'pb', unit: 'ratio', basis: 'source PB' }, { name: 'total_shares', unit: 'share' }], currency: 'CNY' }),
    financials: snapshot('financial-vendor'),
  });
  for (const id of ['peTTM', 'pb', 'psTTM', 'totalShares', 'marketCap']) assert.equal(p.valuation[id].value, 0, id);
  assert.equal(p.valuation.pb.provider, 'vendor'); assert.equal(p.valuation.pb.date, '2026-10-20'); assert.equal(p.valuation.pb.unit, 'ratio');
  assert.equal(p.valuation.pb.currency, null, 'PB is dimensionless despite a dataset-level currency'); assert.equal(p.valuation.pb.state, 'complete'); assert.equal(p.financial.pbMRQ.value, 7);
  assert.equal(project({ valuation: [{ pb_mrq: 4 }] }).valuation.pb.value, null);
  assert.equal(project({ valuation: [{ pb: 4 }] }).financial.pbMRQ.value, null);
});

test('missing field metadata cannot inherit price units and derived returns keep their dimensions', () => {
  const meta = { currency: 'CNY', fields: [{ name: 'price', unit: 'currency_per_share', currency: 'CNY' }, { name: 'pb', unit: 'ratio', currency: 'CNY', basis: 'source PB' }, { name: 'ps_ttm', unit: 'ratio' }, { name: 'total_shares', unit: 'share', currency: 'CNY' }] };
  const p = project({ overview: [{ price: 10.11, yclose: 10, date: '2026-10-20' }], valuation: [{ pe_ttm: 9, pb: 2, ps_ttm: 3, total_shares: 0 }], financials: [{ roe: 0.2, gross_profit_margin: 30 }] }, { overview: snapshot('tinysoft', meta), valuation: snapshot('wind', meta), financials: snapshot('wind', { currency: 'CNY' }) });
  assert.equal(p.basic.open.value, null); assert.equal(p.basic.open.unit, null); assert.equal(p.basic.open.currency, null);
  assert.equal(p.basic.changePct.derived, true); assert.equal(p.basic.changePct.unit, 'percent'); assert.equal(p.basic.changePct.currency, null);
  assert.ok(Math.abs(p.basic.changePct.value - 1.1) < 1e-10);
  assert.equal(p.basic.change.unit, 'currency_per_share'); assert.equal(p.basic.change.currency, 'CNY'); assert.equal(p.basic.change.provider, 'tinysoft'); assert.equal(p.basic.change.date, '2026-10-20');
  for (const id of ['peTTM', 'pb', 'psTTM', 'totalShares']) assert.equal(p.valuation[id].currency, null, id);
  assert.equal(p.financial.roe.unit, null, 'an unqualified ROE does not imply a percent scale'); assert.equal(p.financial.roe.currency, null);
  assert.equal(p.financial.grossMargin.currency, null);
  assert.equal(p.coverageRows.find(row => row.id === 'valuation').fields.find(field => field.name === 'pb').basis, 'source PB');
  const unknown = project({ overview: [{ price: 2, yclose: 1 }] });
  assert.equal(unknown.basic.change.unit, null); assert.equal(unknown.basic.change.currency, null);
});

test('a partially read first snapshot is not a retained snapshot after a page read failure', () => {
  for (const rowCount of [201, 320]) {
    const p = project({ history: Array.from({ length: 200 }, (_, index) => ({ date: `2026-10-${String(index % 20 + 1).padStart(2, '0')}`, close: index })) }, { history: { status: 'partial', failure_code: 'snapshot_read_failed', dataset: { dataset_id: 'new-history', provider: 'tinysoft', row_count: rowCount } } });
    const row = p.coverageRows.find(item => item.id === 'history');
    assert.equal(row.loadedRowCount, 200); assert.equal(row.hasSnapshot, true); assert.equal(row.retainedSnapshot, false); assert.equal(row.failureCode, 'snapshot_read_failed');
  }
  const empty = project({}, { history: { status: 'error', failure_code: 'snapshot_read_failed', dataset: { dataset_id: 'new-history', row_count: 320 } } }).coverageRows[1];
  assert.equal(empty.hasSnapshot, false); assert.equal(empty.retainedSnapshot, false);
});

test('PS-TTM only reads its exact source field and never derives from capitalization and revenue', () => {
  const rows = { overview: [{ market_cap: 800 }], valuation: [{ ps: 5, price_sales: 6 }], financials: [{ revenue: 100 }] };
  assert.equal(project(rows).valuation.psTTM.value, null);
  assert.equal(project({ valuation: [{ ps_ttm: false }] }).valuation.psTTM.value, null);
  assert.equal(project({ valuation: [{ ps_ttm: 0 }] }).valuation.psTTM.value, 0);
});

test('Wind shares retain raw values and declared units while never deriving market capitalization', () => {
  const blocks = { valuation: snapshot('wind', { fields: [{ name: 'close', unit: 'currency_per_share', currency: 'CNY' }, { name: 'total_shares', unit: 'share' }] }) };
  const p = project({ valuation: [{ close: 10, total_shares: 123.45, date: '2026-10-20' }] }, blocks);
  assert.equal(p.valuation.totalShares.value, 123.45); assert.equal(p.valuation.totalShares.unit, 'share');
  assert.equal(p.valuation.totalShares.unitVerified, false); assert.match(p.valuation.totalShares.unitNote, /来源声明|未核验/);
  assert.equal(p.basic.marketCap.value, null); assert.equal(p.valuation.marketCap.value, null);
  assert.equal(project({ valuation: [{ total_shares: 0 }] }, blocks).valuation.totalShares.value, 0);
  const direct = project({ valuation: [{ close: 10, total_shares: 123.45, market_cap: 999, date: '2026-10-20' }] }, blocks);
  assert.equal(direct.valuation.marketCap.value, 999); assert.equal(direct.basic.marketCap.derived, undefined);
});

test('non-Wind market capitalization keeps the existing same-source same-day unit guards', () => {
  const blocks = { valuation: snapshot('vendor', { fields: [{ name: 'close', unit: '元/股', currency: 'CNY' }, { name: 'total_shares', unit: '股' }] }) };
  const p = project({ valuation: [{ close: 10, total_shares: 20, date: '2026-10-20' }] }, blocks);
  assert.equal(p.basic.marketCap.value, 200); assert.equal(p.basic.marketCap.derived, true);
  assert.equal(p.valuation.totalShares.unitVerified, true);
  assert.equal(project({ overview: [{ price: 10, date: '2026-10-21' }], valuation: [{ total_shares: 20, date: '2026-10-20' }] }, blocks).basic.marketCap.value, null);
});

test('coverage separates providers, row dates, report periods and metadata read times', () => {
  const p = project({ overview: [{ 时间: '2026-10-20T15:00:00', price: 0 }], history: [{ date: '2026-10-18', close: 1 }, { 时间: '2026-10-20', close: 2 }], financials: [{ 报告期: '2026-06-30', revenue: 1 }, { 截止日期: '2026-03-31', revenue: 2 }, { 报告日期: '2025-12-31', revenue: 3 }] }, {
    overview: snapshot('tinysoft', { dataset_id: 'overview-id', as_of: '2026-10-21', retrieved_at: '2026-10-22T01:00:00Z' }),
    history: { ...snapshot('wind', { dataset_id: 'history-id', actual_range: { start_date: '2026-10-17', end_date: '2026-10-20' } }), requested_source: 'wind', requested_range: { start_date: '2026-10-01', end_date: '2026-10-21' } },
    financials: snapshot('financial-vendor', { dataset_id: 'financial-id' }),
  }, { source: 'auto', request_parameters: { frequency: 'daily', adjustment: 'none' } });
  assert.deepEqual(p.coverageRows.map(row => row.id), ['overview', 'history', 'valuation', 'financials', 'activity', 'margin', 'holders', 'research']);
  const byId = Object.fromEntries(p.coverageRows.map(row => [row.id, row]));
  assert.equal(byId.overview.provider, 'tinysoft'); assert.equal(byId.overview.dataDate, '2026-10-20T15:00:00');
  assert.equal(byId.overview.asOf, '2026-10-21'); assert.equal(byId.overview.retrievedAt, '2026-10-22T01:00:00Z');
  assert.equal(byId.history.provider, 'wind'); assert.equal(byId.history.requestedSource, 'wind');
  assert.deepEqual(byId.history.loadedRange, { start_date: '2026-10-18', end_date: '2026-10-20' });
  assert.deepEqual(byId.history.requestedRange, { start_date: '2026-10-01', end_date: '2026-10-21' });
  assert.equal(byId.history.actualRange.start_date, '2026-10-17');
  assert.equal(byId.history.requestedFrequency, 'daily'); assert.equal(byId.history.requestedAdjustment, 'none');
  assert.equal(byId.financials.dataDate, null); assert.deepEqual(byId.financials.reportPeriods, ['2025-12-31', '2026-03-31', '2026-06-30']);
  assert.equal(byId.financials.requestedFrequency, null); assert.equal(byId.financials.requestedAdjustment, null);
  assert.equal(byId.valuation.dataDate, null); assert.equal(byId.valuation.asOf, null);
});

test('coverage counts only loaded rows with dataset identity, not advertised counts or complete status', () => {
  const p = project({ overview: [{ price: 0 }], valuation: [{ pb: 0 }] }, {
    overview: snapshot('tinysoft', { dataset_id: 'actual', row_count: 0 }),
    history: snapshot('wind', { dataset_id: 'not-loaded', row_count: 999 }),
    valuation: snapshot('wind', { row_count: 1 }),
  });
  assert.equal(p.coverageRows.filter(row => row.hasSnapshot).length, 1);
  assert.equal(p.coverageRows[0].loadedRowCount, 1); assert.equal(p.coverageRows[1].loadedRowCount, 0);
  assert.equal(p.coverageRows[2].hasSnapshot, false); assert.equal(p.coverageRows[2].loadedRowCount, 1);
});

test('failed refresh keeps old snapshot identity, actual loaded rows and failure visible', () => {
  const p = project({ history: [{ date: '2026-10-10', close: 8 }] }, { history: {
    status: 'error', failure_code: 'provider_timeout', requested_source: 'tinysoft', requested_range: { start_date: '2026-10-01', end_date: '2026-10-21' },
    dataset: { dataset_id: 'retained-id', provider: 'wind', as_of: '2026-10-10', retrieved_at: '2026-10-11T00:00:00Z', limitations: ['snapshot_only'], fields: [{ name: 'close', unit: '元/股', basis: 'unadjusted' }] },
  } });
  const row = p.coverageRows.find(item => item.id === 'history');
  assert.equal(row.status, 'error'); assert.equal(row.hasSnapshot, true); assert.equal(row.retainedSnapshot, true);
  assert.equal(row.failureCode, 'provider_timeout'); assert.equal(row.requestedSource, 'tinysoft'); assert.equal(row.provider, 'wind');
  assert.equal(row.datasetId, 'retained-id'); assert.equal(row.dataDate, '2026-10-10'); assert.equal(row.retrievedAt, '2026-10-11T00:00:00Z');
  assert.deepEqual(row.limitations, ['snapshot_only']); assert.deepEqual(row.fields, [{ name: 'close', unit: '元/股', basis: 'unadjusted' }]);
  const unloaded = project({}, { history: { status: 'error', failure_code: 'provider_timeout', dataset: { dataset_id: 'retained-id', row_count: 1 } } }).coverageRows[1];
  assert.equal(unloaded.hasSnapshot, false); assert.equal(unloaded.retainedSnapshot, false);
});

test('projection leaves frozen rows and metadata unchanged and preserves original field declarations', () => {
  const rows = { history: [{ date: '2026-10-20', close: 1 }, { date: '2026-10-18', close: 2 }], valuation: [{ pb: 0, total_shares: 0 }] };
  const observation = { source: 'wind', blocks: { valuation: snapshot('wind', { dataset_id: 'valuation-id', fields: { pb: { unit: 'ratio', basis: 'source PB' } }, units: { total_shares: '万股' } }) } };
  const original = JSON.stringify({ rows, observation });
  const freeze = value => { if (value && typeof value === 'object') { Object.values(value).forEach(freeze); Object.freeze(value); } return value; };
  freeze(rows); freeze(observation);
  const p = projectAssetObservation(rows, observation);
  assert.equal(JSON.stringify({ rows, observation }), original);
  assert.equal(p.valuation.totalShares.unit, '万股');
  const fields = p.coverageRows.find(row => row.id === 'valuation').fields;
  assert.deepEqual(fields, [{ name: 'pb', unit: 'ratio', basis: 'source PB' }, { name: 'total_shares', unit: '万股' }]);
});
