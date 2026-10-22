// Asset identity stays separate from the six-digit upstream news identifier.
export const ASSET_VIEWS = ['overview', 'financials', 'capital', 'holders', 'news', 'announcements', 'materials'];
export const ASSET_TYPES = ['stock', 'etf', 'index', 'fund', 'theme'];
export function assetTopicKey(key, view = 'overview') {
  const index = Math.max(0, ASSET_VIEWS.indexOf(view));
  if (key === 'Home') return ASSET_VIEWS[0];
  if (key === 'End') return ASSET_VIEWS.at(-1);
  if (!['ArrowLeft', 'ArrowRight'].includes(key)) return null;
  return ASSET_VIEWS[(index + (key === 'ArrowRight' ? 1 : -1) + ASSET_VIEWS.length) % ASSET_VIEWS.length];
}
export const cleanAsset = value => /^[A-Za-z0-9][A-Za-z0-9._-]{1,31}$/.test(String(value || '')) ? String(value).toUpperCase() : '';
export function assetHref(asset = '', assetType = 'stock', view = 'overview') {
  const params = new URLSearchParams({ view: ASSET_VIEWS.includes(view) ? view : 'overview' });
  const identity = cleanAsset(asset);
  if (identity) { params.set('asset', identity); params.set('asset_type', ASSET_TYPES.includes(assetType) ? assetType : 'stock'); }
  return `#/assets?${params}`;
}
export function selectAssetObservation(items = [], route = {}) {
  const asset = cleanAsset(route.asset);
  if (!asset) return route.assetView && route.assetView !== 'overview' ? null : items[0] || null;
  const candidates = items.filter(item => item.asset_type === (route.assetType || 'stock'));
  const exact = candidates.find(item => cleanAsset(item.asset) === asset);
  if (exact) return exact;
  if (!/^\d{6}$/.test(asset)) return null;
  const matches = candidates.filter(item => cleanAsset(item.asset).split('.')[0] === asset);
  const identities = new Set(matches.map(item => cleanAsset(item.asset)));
  return identities.size === 1 ? matches[0] : null;
}
export function assetNewsCode(asset, assetType = 'stock') {
  if (assetType !== 'stock') return null;
  const match = /^(\d{6})(?:\.(SH|SZ|BJ))?$/.exec(cleanAsset(asset));
  if (!match) return null;
  const [, code, market] = match;
  const valid = market === 'SH' ? /^6\d{5}$/.test(code) : market === 'SZ' ? /^(00|30)\d{4}$/.test(code) : market === 'BJ' ? /^(4|8)\d{5}$|^92\d{4}$/.test(code) : /^(6\d{5}|(?:00|30)\d{4}|[48]\d{5}|92\d{4})$/.test(code);
  return valid ? code : null;
}
