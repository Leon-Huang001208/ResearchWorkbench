/** Own turnover-decay estimate. Wind observations guide controls, not a claim of vendor equivalence. */
export const CHIP_MODEL_VERSION = 'rwb-chip-turnover-1';
export const CHIP_DEFAULTS = Object.freeze({
  algorithm: 'triangle', decay: 1, peakUpperPct: 10, peakLowerPct: 10, showPeak: true,
  ageShort: 2, ageMiddle: 10, ageLong: 100, visibleAges: Object.freeze(['long', 'middle', 'short', 'ultra']),
  overlayEnabled: false, overlayDays: 100,
});
export const CHIP_AGES = Object.freeze([
  { id: 'long', name: '长线筹码', color: '#c96532' },
  { id: 'middle', name: '中线筹码', color: '#ee913d' },
  { id: 'short', name: '短线筹码', color: '#efc956' },
  { id: 'ultra', name: '超短筹码', color: '#e9ef73' },
]);

export function normalizeChipSettings(value = {}) {
  if (!value || typeof value !== 'object' || Array.isArray(value) || Object.keys(value).some(k => !Object.hasOwn(CHIP_DEFAULTS, k))) throw new Error('chip_settings_invalid');
  const s = { ...CHIP_DEFAULTS, ...value };
  const number = (key, min, max, integer = false) => {
    if (typeof s[key] !== 'number' || !Number.isFinite(s[key]) || s[key] < min || s[key] > max || (integer && !Number.isSafeInteger(s[key]))) throw new Error('chip_settings_invalid');
  };
  number('decay', 0, 10); number('peakUpperPct', 0, 100); number('peakLowerPct', 0, 100);
  for (const key of ['ageShort', 'ageMiddle', 'ageLong', 'overlayDays']) number(key, 1, 10000, true);
  if (!['triangle', 'uniform'].includes(s.algorithm) || !(s.ageShort < s.ageMiddle && s.ageMiddle < s.ageLong)
      || typeof s.showPeak !== 'boolean' || typeof s.overlayEnabled !== 'boolean'
      || !Array.isArray(s.visibleAges) || s.visibleAges.length > 4 || new Set(s.visibleAges).size !== s.visibleAges.length
      || s.visibleAges.some(id => !CHIP_AGES.some(age => age.id === id))) throw new Error('chip_settings_invalid');
  return { ...s, visibleAges: CHIP_AGES.filter(age => s.visibleAges.includes(age.id)).map(age => age.id) };
}

const finite = v => typeof v === 'number' && Number.isFinite(v);
const day = value => {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const parsed = new Date(`${value}T00:00:00Z`);
  return Number.isFinite(parsed.getTime()) && parsed.toISOString().slice(0, 10) === value;
};
const ageGroup = (n, s) => n < s.ageShort ? 3 : n < s.ageMiddle ? 2 : n < s.ageLong ? 1 : 0;

function kernel(bar, algorithm) {
  const l = bar.low, h = bar.high, m = h === l ? l : algorithm === 'uniform' ? (l + h) / 2 : Math.max(l, Math.min(h, bar.vwap));
  const mean = algorithm === 'uniform' ? m : (l + h + m) / 3;
  const atom = l === h;
  return {
    l, h, m, mean, atom,
    cdf(x, strict = false) {
      if (atom) return strict ? Number(x > l) : Number(x >= l);
      if (x <= l) return 0; if (x >= h) return 1;
      if (algorithm === 'uniform') return (x - l) / (h - l);
      return x <= m ? (x - l) ** 2 / ((h - l) * (m - l)) : 1 - (h - x) ** 2 / ((h - l) * (h - m));
    },
    moment(x, strict = false) {
      if (atom) return (strict ? x > l : x >= l) ? mean : 0;
      if (x <= l) return 0; if (x >= h) return mean;
      if (algorithm === 'uniform') return (x - l) * (x + l) / (2 * (h - l));
      if (x <= m) { const u = x - l; return 2 * (l * u * u / 2 + u ** 3 / 3) / ((h - l) * (m - l)); }
      const u = h - x; return mean - 2 * (h * u * u / 2 - u ** 3 / 3) / ((h - l) * (h - m));
    },
  };
}

/** Density maximum from piecewise-linear breakpoints: independent of drawing bucket resolution. */
function peakOf(cohorts, algorithm) {
  const events = new Map();
  const event = (x, slope, intercept) => { const old = events.get(x) || [0, 0]; events.set(x, [old[0] + slope, old[1] + intercept]); };
  for (const { k, weight } of cohorts) {
    if (k.atom) {
      // A price atom has infinite mathematical density. Use a fixed 0.01-price
      // triangular peak resolution, independent of drawing bins, so a tiny
      // surviving IPO limit-up atom cannot override today's cost density.
      const width = Math.min(.01, k.l / 2), a = weight / (width * width);
      event(k.l - width, a, -a * (k.l - width));
      event(k.l, -2 * a, 2 * a * k.l);
      event(k.l + width, a, -a * (k.l + width));
      continue;
    }
    if (algorithm === 'uniform') { const d = weight / (k.h - k.l); event(k.l, 0, d); event(k.h, 0, -d); continue; }
    if (k.m > k.l) { const a = 2 * weight / ((k.h - k.l) * (k.m - k.l)); event(k.l, a, -a * k.l); event(k.m, -a, a * k.l); }
    if (k.h > k.m) { const a = -2 * weight / ((k.h - k.l) * (k.h - k.m)); event(k.m, a, -a * k.h); event(k.h, -a, a * k.h); }
  }
  let slope = 0, intercept = 0, best = -Infinity, price = null;
  const consider = x => { const density = Math.max(0, slope * x + intercept); if (density > best + Math.max(1e-12, Math.abs(best) * 1e-12) || price === null) { best = density; price = x; } };
  for (const [x, [a, b]] of [...events].sort((a, b) => a[0] - b[0])) { consider(x); slope += a; intercept += b; consider(x); }
  return price;
}

export function estimateChips(source, options = {}, buckets = 180) {
  let settings;
  try { settings = normalizeChipSettings(options); } catch { return unavailable('chip_settings_invalid'); }
  if (!Array.isArray(source) || source.length < 5) return unavailable('chip_history_short', source);
  if (!Number.isSafeInteger(buckets) || buckets < 2 || buckets > 2048) return unavailable('chip_buckets_invalid', source);
  const asset = source[0]?.asset;
  for (let i = 0; i < source.length; i++) {
    const b = source[i];
    if (!b || typeof asset !== 'string' || !asset || b.asset !== asset || !day(b.date) || (i && b.date <= source[i - 1].date)
        || !finite(b.volume) || b.volume < 0 || (b.volume === 0 && b.turnover_rate_pct > 0)
        || b.gap || ![b.open, b.high, b.low, b.close].every(v => finite(v) && v > 0)
        || b.high < Math.max(b.open, b.close, b.low) || b.low > Math.min(b.open, b.close)
        || !finite(b.turnover_rate_pct) || b.turnover_rate_pct < 0) return unavailable('chip_input_invalid', source);
    if (settings.algorithm === 'triangle' && b.high !== b.low && (i === 0 || b.turnover_rate_pct > 0)
        && (!finite(b.vwap) || b.vwap < b.low - 1e-6 || b.vwap > b.high + 1e-6)) return unavailable('chip_vwap_unverified', source);
  }
  const cohorts = []; let survival = 1, clampedTurnoverDays = 0;
  for (let i = source.length - 1; i >= 0; i--) {
    const b = source[i], rate = Math.min(1, b.turnover_rate_pct / 100 * settings.decay);
    if (b.turnover_rate_pct / 100 * settings.decay > 1) clampedTurnoverDays++;
    const weight = i === 0 ? survival : survival * rate; survival *= 1 - rate;
    if (weight > 0) cohorts.push({ k: kernel(b, settings.algorithm), weight, age: source.length - 1 - i, initial: i === 0 });
  }
  const total = cohorts.reduce((s, b) => s + b.weight, 0);
  if (!(total > 0)) return unavailable('chip_mass_invalid', source);
  cohorts.forEach(c => { c.weight /= total; });
  const low = Math.min(...cohorts.map(c => c.k.l)), high = Math.max(...cohorts.map(c => c.k.h));
  const cdf = (x, strict = false) => Math.max(0, Math.min(1, cohorts.reduce((s, c) => s + c.weight * c.k.cdf(x, strict), 0)));
  const quantile = q => { let l = low, h = high; for (let i = 0; i < 52; i++) { const m = (l + h) / 2; if (cdf(m) < q) l = m; else h = m; } return (l + h) / 2; };
  const peak = peakOf(cohorts, settings.algorithm), peakLower = peak * (1 - settings.peakLowerPct / 100), peakUpper = peak * (1 + settings.peakUpperPct / 100);
  const ages = [0, 0, 0, 0], peakAges = [0, 0, 0, 0]; let averageCost = 0, meanAge = 0, peakMass = 0, peakCost = 0, peakAge = 0;
  for (const c of cohorts) {
    const group = ageGroup(c.age, settings), mass = Math.max(0, c.k.cdf(peakUpper) - c.k.cdf(peakLower, true));
    ages[group] += c.weight; averageCost += c.weight * c.k.mean; meanAge += c.weight * c.age;
    peakMass += c.weight * mass; peakCost += c.weight * (c.k.moment(peakUpper) - c.k.moment(peakLower, true));
    peakAge += c.weight * mass * c.age; peakAges[group] += c.weight * mass;
  }
  const width = high > low ? (high - low) / buckets : Math.max(.01, high * .00001);
  // Share exact boundaries. Recomputing h=l+width independently can overlap
  // adjacent intervals and double count an atom at a floating-point edge.
  const edges = high > low ? Array.from({ length: buckets + 1 }, (_, i) => i === buckets ? high : low + i * width) : [low - width / 2, low + width / 2];
  const points = Array.from({ length: high > low ? buckets : 1 }, (_, i) => {
    const l = edges[i], h = edges[i + 1], massByAge = [0, 0, 0, 0];
    for (const c of cohorts) massByAge[ageGroup(c.age, settings)] += c.weight * Math.max(0, c.k.cdf(h, i < buckets - 1) - c.k.cdf(l, true));
    const mass = massByAge.reduce((a, b) => a + b, 0);
    return { price: (l + h) / 2, mass, massByAge, concentration_pct: mass * 100, volume: mass };
  });
  const cost90 = [quantile(.05), quantile(.95)], cost70 = [quantile(.15), quantile(.85)], referenceClose = source.at(-1).close;
  const profitable = cdf(referenceClose, true), atOrBelow = cdf(referenceClose);
  return {
    status: 'ready', modelVersion: CHIP_MODEL_VERSION, settings, points, domain: [low, high], bucketWidth: width,
    startDate: source[0].date, endDate: source.at(-1).date, validBars: source.length, referenceClose,
    averageCost, peak, peakLower, peakUpper, lower: peakLower, upper: peakUpper,
    profitFraction: profitable, lockedFraction: 1 - atOrBelow, atCostFraction: Math.max(0, atOrBelow - profitable),
    cost90, cost70, concentration90: (cost90[1] - cost90[0]) / (cost90[1] + cost90[0]), concentration70: (cost70[1] - cost70[0]) / (cost70[1] + cost70[0]),
    ageFractions: ages, meanAge, peakFraction: peakMass, peakAverageCost: peakMass > 0 ? peakCost / peakMass : null,
    peakCapitalFraction: averageCost > 0 ? peakCost / averageCost : null,
    peakMeanAge: peakMass > 0 ? peakAge / peakMass : null, peakAgeFractions: peakMass > 0 ? peakAges.map(v => v / peakMass) : null,
    initialResidual: cohorts.find(c => c.initial)?.weight || 0, clampedTurnoverDays,
  };
}

export function unavailable(reason, source = []) {
  if (!Array.isArray(source)) source = [];
  return { status: 'unavailable', reason, points: [], averageCost: null, peak: null, lower: null, upper: null, peakLower: null, peakUpper: null,
    profitFraction: null, lockedFraction: null, referenceClose: source.at(-1)?.close ?? null, validBars: source.length, startDate: source[0]?.date, endDate: source.at(-1)?.date };
}
