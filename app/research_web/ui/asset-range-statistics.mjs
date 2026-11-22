// Pure daily-bar calculation. The caller records diagnostics with the existing
// project logger; only stable codes leave this module, never source payloads.
import { finite, sourceFrequency } from './asset-indicators.mjs';

const DEFINITIONS = {
  changePct: ['percent', '(末收 / 前收 - 1) × 100'],
  changeAmount: ['price', '末收 - 前收'],
  annualizedPct: ['percent', '((末收 / 前收)^(250 / 区间日线条数) - 1) × 100'],
  industryComparisonPct: ['percent', '需已核行业分类及同区间基准日序列；未取得'],
  previousClose: ['price', '同版本同复权已扫描连续日期内的前一有效行情收盘；非交易所日历相邻确认'],
  close: ['price', '区间末日收盘价'], open: ['price', '区间首日开盘价'],
  high: ['price', '区间全部日线最高价的最大值'], low: ['price', '区间全部日线最低价的最小值'],
  meanPrice: ['price', '原始成交均价 = 完整原始成交额 / 完整成交股数；不作为复权均价'],
  amplitudePct: ['percent', '(区间最高 - 区间最低) / 前收 × 100'],
  amount: ['', '区间逐日成交额完整求和（保留原单位）'], volume: ['', '区间逐日成交量完整求和（保留原单位）'],
  turnoverPct: ['percent', '区间逐日已核百分比换手完整求和'], dailyTurnoverPct: ['percent', '区间换手 / 区间全部日线条数'],
  upCount: ['count', '全部有效日线中收盘 > 开盘的条数'], downCount: ['count', '全部有效日线中收盘 < 开盘的条数'], flatCount: ['count', '全部有效日线中收盘 = 开盘的条数'],
  maxVolume: ['', '区间全部日线成交量最大值（保留原单位）'], minVolume: ['', '区间全部日线成交量最小值（保留原单位）'],
  maxDrawdownPct: ['percent', '区间极值口径：(最低 / 最高 - 1) × 100；不按时间顺序'],
  maxRisePct: ['percent', '区间极值口径：(最高 / 最低 - 1) × 100；不按时间顺序'],
};
const object = value => value && typeof value === 'object' && !Array.isArray(value) ? value : {};
function dateOnly(value) {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return null;
  const time = Date.parse(`${value}T00:00:00Z`);
  return Number.isFinite(time) && new Date(time).toISOString().slice(0, 10) === value ? value : null;
}
const positive = value => { const n = finite(value); return n !== null && n > 0 ? n : null; };
const nonnegative = value => { const n = finite(value); return n !== null && n >= 0 ? n : null; };
const observed = row => row && row.gap !== true && row.missing !== true;
const coverageOf = (expectedCount, validCount, scanComplete) => ({ expectedCount, validCount, missingCount: expectedCount - validCount, scanComplete, countBasis: 'loaded_daily_rows' });
function validBar(row) {
  return row && row.gap !== true && row.missing !== true && row.validOHLC !== false
    && [row.open, row.high, row.low, row.close].every(value => positive(value) !== null)
    && Number(row.low) <= Math.min(Number(row.open), Number(row.close))
    && Number(row.high) >= Math.max(Number(row.open), Number(row.close));
}
function unitFor(metadata, key) {
  const fields = metadata.fields;
  const field = object(Array.isArray(fields) ? fields.find(item => item?.name === key || item?.key === key) : fields?.[key]);
  const unit = typeof (field.unit ?? field.units) === 'string' ? (field.unit ?? field.units).trim() : '';
  if (unit === 'currency') return key === 'amount' && ['CNY', 'USD', 'HKD', 'EUR', 'GBP', 'JPY'].includes(field.currency || metadata.currency) ? field.currency || metadata.currency : '';
  const dimension = key === 'amount'
    ? /^(?:CNY|USD|HKD|EUR|GBP|JPY|(?:万|亿|百万|千)?(?:元|美元|港元))$/
    : /^(?:share|shares|(?:万|亿|百万|千)?(?:股|手|份|张|吨|克))$/;
  return dimension.test(unit) ? unit : '';
}
function verifiedRawPriceCurrency(metadata) {
  const keys = ['open', 'high', 'low', 'close', 'vwap'];
  const fields = Array.isArray(metadata.fields)
    ? metadata.fields.filter(field => keys.includes(field?.name) || keys.includes(field?.key))
    : keys.filter(key => Object.hasOwn(object(metadata.fields), key)).map(key => metadata.fields[key]);
  // Amount currency alone does not establish the price basis. Each declared
  // price field must agree, including optional VWAP and duplicate descriptors.
  if (!fields.length || (metadata.currency != null && !['CNY', 'RMB', '元'].includes(metadata.currency))) return false;
  return fields.every(value => {
    const field = object(value); const unit = field.unit ?? field.units;
    return (unit === 'currency_per_share' && field.currency === 'CNY')
      || (unit === '元/股' && (field.currency == null || field.currency === 'CNY'));
  });
}
// Union of scanned calendar intervals proves only provider dataset adjacency.
// A missing scan day is not silently interpreted as an exchange holiday.
function coveredBetween(coverage, start, end) {
  const ranges = Array.isArray(coverage.scanned_ranges) ? coverage.scanned_ranges : [];
  const scans = ranges.map(row => [dateOnly(row?.start_date), dateOnly(row?.end_date)]).filter(([a, b]) => a && b && a <= b).sort((a, b) => a[0].localeCompare(b[0]));
  let cursor = Date.parse(`${start}T00:00:00Z`); const target = Date.parse(`${end}T00:00:00Z`);
  for (const [a, b] of scans) {
    const left = Date.parse(`${a}T00:00:00Z`); const right = Date.parse(`${b}T00:00:00Z`);
    if (left > cursor) return false;
    if (right >= cursor) cursor = right + 86400000;
    if (cursor > target) return true;
  }
  return false;
}
function scale(unit, suffix) {
  if (suffix === '股' && ['share', 'shares'].includes(unit)) return 1;
  if (suffix === '元' && unit === 'CNY') return 1;
  const match = new RegExp(`^(万|亿|百万|千)?${suffix}$`).exec(unit);
  return match ? ({ 万: 1e4, 亿: 1e8, 百万: 1e6, 千: 1e3 }[match[1]] || 1) : null;
}

/**
 * Input is one immutable daily dataset (normalized or enriched bars). Version,
 * factor and adjustment evidence comes from asset_history; optional per-row
 * canonical_version/adjustment must agree. Missing evidence remains unknown.
 * Every error has a stable diagnostics code for the caller's project logger.
 */
export function calculateRangeStatistics(daily, selection = {}, metadata = {}) {
  metadata = object(metadata); selection = object(selection);
  const history = object(metadata.asset_history); const coverage = object(history.coverage);
  const provenance = { canonicalVersion: history.canonical_version || metadata.canonicalVersion || null, factorVersion: history.factor_version || metadata.factorVersion || null, adjustment: history.adjustment || metadata.adjustment || null, source: history.source || metadata.source || metadata.provider || null };
  let requestedStart = dateOnly(selection.startDate); let requestedEnd = dateOnly(selection.endDate);
  if (requestedStart && requestedEnd && requestedStart > requestedEnd) [requestedStart, requestedEnd] = [requestedEnd, requestedStart];
  const range = { requestedStart, requestedEnd, startDate: null, endDate: null, count: 0, coverage: coverageOf(0, 0, false) };
  const metrics = Object.fromEntries(Object.entries(DEFINITIONS).map(([key, [unit, definition]]) => [key, { value: null, unit, status: 'unknown', reason: 'range_unavailable', definition, coverage: coverageOf(0, 0, false) }]));
  const diagnostics = [];
  const fail = code => { diagnostics.push(code); for (const metric of Object.values(metrics)) metric.reason = code; return { range, metrics, provenance, diagnostics }; };
  const set = (key, value, reason = 'required_input_missing', unit = metrics[key].unit, metricCoverage = range.coverage) => {
    const n = finite(value); metrics[key] = { ...metrics[key], value: n, unit, status: n === null ? 'unknown' : 'ok', reason: n === null ? reason : null, coverage: { ...metricCoverage } };
    if (n === null && !diagnostics.includes(reason)) diagnostics.push(reason);
  };
  if (!Array.isArray(daily)) return fail('range_daily_invalid');
  if (!requestedStart || !requestedEnd) return fail('range_dates_invalid');
  if (sourceFrequency(metadata.frequency) !== 'day') return fail('range_daily_required');
  if (daily.some(row => !dateOnly(row?.date))) return fail('range_row_date_invalid');
  const rows = [...daily].sort((a, b) => a.date.localeCompare(b.date));
  if (rows.some((row, i) => i && row.date === rows[i - 1].date)) return fail('range_duplicate_dates');
  if (rows.some(row => (row.canonical_version != null && row.canonical_version !== provenance.canonicalVersion)
    || (row.adjustment != null && row.adjustment !== provenance.adjustment)
    || (row.factor_version != null && row.factor_version !== provenance.factorVersion))) return fail('range_basis_mismatch');
  const selected = rows.filter(row => row.date >= requestedStart && row.date <= requestedEnd);
  if (!selected.length) return fail('range_empty');
  Object.assign(range, { startDate: selected[0].date, endDate: selected.at(-1).date, count: selected.length });
  const scanComplete = coveredBetween(coverage, range.startDate, range.endDate);
  range.coverage = coverageOf(selected.length, selected.filter(validBar).length, scanComplete);
  if (!scanComplete) diagnostics.push('range_scan_incomplete');
  const complete = scanComplete && selected.every(validBar); const first = selected[0]; const last = selected.at(-1);
  const prior = rows[rows.indexOf(first) - 1];
  const priorScanComplete = Boolean(prior && coveredBetween(coverage, prior.date, first.date));
  const priorClose = provenance.canonicalVersion && ['none', 'qfq', 'hfq'].includes(provenance.adjustment) && observed(prior) && observed(first) && priorScanComplete ? positive(prior.close) : null;
  set('previousClose', priorClose, 'previous_close_adjacency_unverified', 'price', coverageOf(1, priorClose === null ? 0 : 1, priorScanComplete));
  const endpoint = (key, row) => {
    const value = observed(row) ? positive(row[key]) : null;
    set(key, value, `range_${key}_missing`, 'price', coverageOf(1, value === null ? 0 : 1, coveredBetween(coverage, row.date, row.date)));
  };
  endpoint('open', first); endpoint('close', last);
  const high = complete ? selected.reduce((n, row) => Math.max(n, Number(row.high)), -Infinity) : null;
  const low = complete ? selected.reduce((n, row) => Math.min(n, Number(row.low)), Infinity) : null;
  set('high', high, 'range_ohlc_incomplete'); set('low', low, 'range_ohlc_incomplete');
  const lastClose = metrics.close.value;
  const ratio = priorClose !== null && lastClose !== null ? lastClose / priorClose : null;
  const closeCoverage = coverageOf(2, Number(priorClose !== null) + Number(lastClose !== null), priorScanComplete && metrics.close.coverage.scanComplete);
  set('changePct', ratio === null ? null : (ratio - 1) * 100, 'previous_or_last_close_missing', 'percent', closeCoverage);
  set('changeAmount', ratio === null ? null : lastClose - priorClose, 'previous_or_last_close_missing', 'price', closeCoverage);
  set('annualizedPct', complete && ratio !== null ? (ratio ** (250 / selected.length) - 1) * 100 : null, 'annualized_input_incomplete');
  set('amplitudePct', high !== null && priorClose !== null ? (high - low) / priorClose * 100 : null, 'amplitude_input_incomplete');
  set('maxDrawdownPct', complete ? (low / high - 1) * 100 : null, 'range_ohlc_incomplete');
  set('maxRisePct', complete ? (high / low - 1) * 100 : null, 'range_ohlc_incomplete');
  for (const [key, predicate] of [['upCount', row => Number(row.close) > Number(row.open)], ['downCount', row => Number(row.close) < Number(row.open)], ['flatCount', row => Number(row.close) === Number(row.open)]]) set(key, complete ? selected.filter(predicate).length : null, 'range_ohlc_incomplete');
  const validQuantity = (row, key) => observed(row) && nonnegative(row[key]) !== null;
  const quantityCoverage = (key, verified = true) => coverageOf(selected.length, verified ? selected.filter(row => validQuantity(row, key)).length : 0, scanComplete);
  const sum = key => scanComplete && selected.every(row => validQuantity(row, key)) ? selected.reduce((n, row) => n + Number(row[key]), 0) : null;
  const amountUnit = unitFor(metadata, 'amount'); const volumeUnit = unitFor(metadata, 'volume');
  const amount = amountUnit ? sum('amount') : null; const volume = volumeUnit ? sum('volume') : null;
  set('amount', amount, amountUnit ? 'range_amount_incomplete' : 'amount_unit_unverified', amountUnit, quantityCoverage('amount', Boolean(amountUnit)));
  set('volume', volume, volumeUnit ? 'range_volume_incomplete' : 'volume_unit_unverified', volumeUnit, quantityCoverage('volume', Boolean(volumeUnit)));
  for (const [key, reducer] of [['maxVolume', Math.max], ['minVolume', Math.min]]) set(key, volume !== null && Number.isFinite(volume) ? selected.reduce((n, row) => reducer(n, Number(row.volume)), key === 'maxVolume' ? -Infinity : Infinity) : null, 'range_volume_incomplete', volumeUnit, quantityCoverage('volume', Boolean(volumeUnit)));
  const fields = metadata.fields; const turnoverField = object(Array.isArray(fields) ? fields.find(row => row?.name === 'turnover_rate_pct' || row?.key === 'turnover_rate_pct') : fields?.turnover_rate_pct);
  const chip = object(history.chip_inputs);
  const verifiedTurnover = ['percent', '%', '百分比'].includes(turnoverField.unit || turnoverField.units) || (chip.status === 'complete' && chip.contract_version === 'chip-turnover-1' && chip.turnover_unit === 'percent');
  const turnover = verifiedTurnover ? sum('turnover_rate_pct') : null;
  set('turnoverPct', turnover, verifiedTurnover ? 'range_turnover_incomplete' : 'turnover_unit_unverified', 'percent', quantityCoverage('turnover_rate_pct', verifiedTurnover));
  set('dailyTurnoverPct', turnover === null ? null : turnover / selected.length, 'range_turnover_incomplete', 'percent', quantityCoverage('turnover_rate_pct', verifiedTurnover));
  const amountScale = scale(amountUnit, '元'); const volumeScale = scale(volumeUnit, '股');
  const priceCurrencyMatches = verifiedRawPriceCurrency(metadata);
  const meanBasis = priceCurrencyMatches && provenance.adjustment === 'none' && amountScale && volumeScale;
  const meanCoverage = coverageOf(selected.length, meanBasis ? selected.filter(row => validQuantity(row, 'amount') && validQuantity(row, 'volume')).length : 0, scanComplete);
  set('meanPrice', meanBasis && amount !== null && volume > 0 ? amount * amountScale / (volume * volumeScale) : null, 'raw_mean_basis_or_input_unverified', 'price', meanCoverage);
  set('industryComparisonPct', null, 'industry_benchmark_unverified', 'percent', coverageOf(selected.length, 0, scanComplete));
  return { range, metrics, provenance, diagnostics };
}
