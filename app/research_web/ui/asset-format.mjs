/** Display scaling only. Raw snapshots, units and calculations remain unchanged. */
export function formatAssetMagnitude(value, unit = '', currency = '') {
  if (value === null || value === undefined || typeof value === 'boolean' || !['number', 'string'].includes(typeof value) || String(value).trim() === '' || !Number.isFinite(Number(value))) return '—';
  const currencies = { CNY: '元', USD: '美元', HKD: '港元' };
  const canonical = { provider_defined: '', unknown: '', currency: currencies[currency] || currency || '原币', share: '股', shares: '股' };
  const text = typeof unit === 'string' ? Object.hasOwn(canonical, unit) ? canonical[unit] : unit : '';
  const match = /^(万|亿|百万|千)?(元|股|手|份|户|美元|港元)$/.exec(text);
  const multiplier = match ? ({ 万: 1e4, 亿: 1e8, 百万: 1e6, 千: 1e3 }[match[1]] || 1) : 1;
  const base = Number(value) * multiplier;
  if (!Number.isFinite(base)) return '—';
  const divisor = Math.abs(base) >= 1e8 ? 1e8 : 1e4;
  const magnitude = Math.abs(base) >= 1e8 ? '亿' : '万';
  const suffix = match ? match[2] : text;
  return `${(Object.is(base, -0) ? 0 : base / divisor).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2, useGrouping: false })}${magnitude}${suffix}`;
}

export const ASSET_MAGNITUDE_FIELDS = new Set(['volume', 'vol', 'amount', 'turnover', 'market_cap', 'total_shares', 'revenue', 'net_profit', 'net_profit_parent', 'total_assets', 'operating_cost', 'gross_profit', 'gross_profit_ttm', 'free_cf', 'equity', 'financing_balance', 'financing_buy', 'financing_repay', 'margin_balance', 'margin_buy', 'margin_repay', 'securities_lending_volume', 'securities_lending_sell', 'securities_lending_repay', 'short_balance', 'short_sell_vol', 'short_repay_vol', 'north_bound_shares', 'main_force_inflow', 'top10_quantity', 'institutional_holding', 'average_holding']);


// A-share display semantics only: positive red, negative green, zero/unknown neutral.
const movementNumber = value => {
  if (typeof value === 'string' && /^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?$/i.test(value.trim())) value = Number(value);
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
};
export function assetChangeClass(value) {
  const n = movementNumber(value);
  return n === null || n === 0 ? '' : n > 0 ? 'asset-price-up' : 'asset-price-down';
}
export function assetPriceClass(value, previousClose) {
  const price = movementNumber(value); const base = movementNumber(previousClose);
  return price === null || base === null || price <= 0 || base <= 0 ? '' : assetChangeClass(price - base);
}
