import { escapeHTML as e } from './markdown.mjs';

const LABELS = {
  overview: '资产概览', history: '历史行情', financials: '财务指标', activity: '资金与交易事件',
  announcements: '公告', news: '新闻', research: '研究资料',
};

const STATE_LABELS = {
  loading: '加载中', complete: '完整', partial: '部分', empty: '暂无数据', unavailable: '不可用', error: '失败',
};

const number = (value, digits = 2) => typeof value === 'number' && Number.isFinite(value) ? value.toLocaleString('zh-CN', { maximumFractionDigits: digits }) : '—';
const finite = (value) => {
  if (value === null || value === undefined || value === '' || typeof value === 'boolean') return null;
  return Number.isFinite(Number(value)) ? Number(value) : null;
};
const firstValue = (source, keys) => keys.map(key => source?.[key]).find(value => finite(value) !== null);
const metric = (label, value, suffix = '') => `<div><dt>${e(label)}</dt><dd>${finite(value) === null ? '—' : `${e(number(finite(value)))}${e(suffix)}`}</dd></div>`;

function sparkline(rows = []) {
  const points = rows.map(row => Number(row.close)).filter(Number.isFinite);
  if (points.length < 2) return '<div class="chart-empty">历史数据不足，无法绘制走势。</div>';
  const width = 760; const height = 220; const padding = 18;
  const min = Math.min(...points); const max = Math.max(...points); const span = max - min || 1;
  const coords = points.map((value, index) => {
    const x = padding + index * ((width - padding * 2) / (points.length - 1));
    const y = height - padding - ((value - min) / span) * (height - padding * 2);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(' ');
  return `<svg class="asset-chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="历史收盘价走势" preserveAspectRatio="none"><line x1="${padding}" y1="${padding}" x2="${padding}" y2="${height - padding}"/><line x1="${padding}" y1="${height - padding}" x2="${width - padding}" y2="${height - padding}"/><polyline points="${coords}"/><text x="${padding + 4}" y="${padding + 12}">${e(number(max))}</text><text x="${padding + 4}" y="${height - padding - 6}">${e(number(min))}</text></svg>`;
}

function previewTable(rows = [], limit = 8) {
  const values = rows.slice(0, limit);
  if (!values.length) return '<p class="muted small">这个区块没有可显示的真实记录。</p>';
  const columns = [...new Set(values.flatMap(row => Object.keys(row)))].slice(0, 6);
  return `<div class="asset-table-wrap"><table class="asset-table"><thead><tr>${columns.map(column => `<th>${e(column)}</th>`).join('')}</tr></thead><tbody>${values.map(row => `<tr>${columns.map(column => `<td>${e(row[column] ?? '—')}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
}

function blockCard(name, block = { status: 'loading' }, rows = []) {
  const status = block.status || 'loading';
  const meta = block.dataset;
  const chart = name === 'history' && status === 'complete' ? sparkline(rows) : '';
  return `<article class="asset-block ${e(status)}"><header><div><span class="eyebrow">${e(name.toUpperCase())}</span><h2>${e(LABELS[name] || name)}</h2></div><span class="badge ${status === 'complete' ? 'live' : ['error', 'unavailable'].includes(status) ? 'danger' : ''}">${e(STATE_LABELS[status] || status)}</span></header>${meta ? `<p class="muted small">${e(meta.provider || meta.source || '未知来源')} · 截止 ${e(meta.as_of || meta.actual_range?.end_date || '来源未提供')}</p>` : ''}${block.failure_code ? `<p class="notice warning">${e(block.failure_code)}</p>` : ''}${chart}${['complete', 'partial'].includes(status) ? previewTable(rows) : status === 'loading' ? '<div class="asset-skeleton" role="status">正在查询这个区块…</div>' : status === 'empty' ? '<p class="muted small">来源成功响应，但没有匹配记录。</p>' : ''}</article>`;
}

function assetHeader(observation, rows) {
  const history = rows?.history || [];
  const latest = history.at(-1) || {};
  const snapshot = { ...latest, ...(rows?.overview?.[0] || {}) };
  const datasets = observation?.dataset_ids || [];
  const price = firstValue(snapshot, ['price', 'last', 'close', 'nav', '收盘']);
  const changePct = firstValue(snapshot, ['change_pct', 'pct_chg', '涨跌幅']);
  return `<section class="asset-identity"><div><span class="eyebrow">ASSET WORKSPACE</span><h1>${e(snapshot.name || observation?.asset || '资产观察')}</h1><p>${e(observation?.asset || '输入证券代码开始')} · ${e(observation?.asset_type || '股票 / ETF / 指数 / 基金 / 主题')}</p></div><div class="asset-price"><strong>${e(number(price))}</strong><span class="${changePct === null || changePct >= 0 ? 'positive' : 'negative'}">${changePct !== null ? `${changePct >= 0 ? '+' : ''}${number(changePct)}%` : '涨跌未知'}</span></div><div class="button-row"><button class="button" data-workbench-handoff="fingpt" data-source-session="${e(observation?.session_id || '')}" data-dataset-ids="${e(JSON.stringify(datasets))}" ${observation?.session_id && datasets.length ? '' : 'disabled'}>交给 FinGPT</button><button class="button primary" data-workbench-handoff="claw" data-source-session="${e(observation?.session_id || '')}" data-dataset-ids="${e(JSON.stringify(datasets))}" ${observation?.session_id && datasets.length ? '' : 'disabled'}>交给 Claw</button></div></section>`;
}

function marketMetrics(rows = {}) {
  const history = rows.history || [];
  const latest = history.at(-1) || {};
  const overview = rows.overview?.[0] || {};
  const source = { ...latest, ...overview };
  const closes = history.map(row => finite(firstValue(row, ['close', '收盘']))).filter(value => value !== null);
  const high52 = closes.length ? Math.max(...closes.slice(-252)) : null;
  const low52 = closes.length ? Math.min(...closes.slice(-252)) : null;
  return `<dl class="asset-market-metrics" aria-label="资产核心指标">${metric('开盘', firstValue(source, ['open', '开盘']))}${metric('最高', firstValue(source, ['high', '最高']))}${metric('最低', firstValue(source, ['low', '最低']))}${metric('成交量', firstValue(source, ['volume', '成交量']), '')}${metric('成交额', firstValue(source, ['amount', '成交额']), '')}${metric('换手率', firstValue(source, ['turnover', 'turnover_rate', '换手率']), '%')}${metric('52周高', high52)}${metric('52周低', low52)}</dl>`;
}

function personalPanel({ observation, watchlists = [], notes = [], alerts = [], notifications = [] }) {
  const asset = observation?.asset || '';
  const selectedNotes = notes.filter(item => item.asset === asset);
  const selectedAlerts = alerts.filter(item => item.asset === asset);
  return `<aside class="asset-personal"><section><div class="section-heading"><h2>自选与观察</h2><span class="muted small">本地保存</span></div>${watchlists.length ? `<form data-watchlist-item><input type="hidden" name="asset" value="${e(asset)}"><label>加入列表<select name="watchlist_id">${watchlists.map(item => `<option value="${e(item.id)}">${e(item.name)}</option>`).join('')}</select></label><button class="button small" ${asset ? '' : 'disabled'}>加入自选</button></form>` : '<p class="muted small">尚无自选列表。</p>'}<form data-asset-note><label>观察笔记<textarea name="text" maxlength="10000" required placeholder="记录判断、待验证事项和后续动作"></textarea></label><input type="hidden" name="asset" value="${e(asset)}"><button class="button small" ${asset ? '' : 'disabled'}>保存笔记</button></form>${selectedNotes.map(item => `<p class="personal-entry">${e(item.text)}</p>`).join('')}</section><section><div class="section-heading"><h2>提醒规则</h2><span class="muted small">快照到达时评估</span></div><form data-asset-alert><input type="hidden" name="asset" value="${e(asset)}"><div class="mini-form"><select name="field"><option value="price">价格</option><option value="change_pct">涨跌幅</option><option value="volume">成交量</option></select><select name="operator"><option value="gte">≥</option><option value="lte">≤</option><option value="gt">＞</option><option value="lt">＜</option></select><input name="threshold" type="number" step="any" required placeholder="阈值"></div><button class="button small" ${asset ? '' : 'disabled'}>添加提醒</button></form>${selectedAlerts.map(item => `<p class="personal-entry"><span class="tiny-dot ${item.enabled ? 'active' : ''}"></span>${e(item.field)} ${e(item.operator)} ${e(item.threshold)} · ${item.condition_active ? '已触发' : '监控中'}</p>`).join('') || '<p class="muted small">当前资产没有提醒。</p>'}${notifications.filter(item => item.asset === asset).slice(0, 3).map(item => `<p class="notice warning">已触发：${e(item.field)} = ${e(item.value)}</p>`).join('')}</section></aside>`;
}

function researchContext(observation) {
  const blocks = observation?.blocks || {};
  const sources = Object.entries(blocks).map(([name, block]) => ({
    name: LABELS[name] || name,
    status: block?.status || 'unavailable',
    provider: block?.dataset?.provider || block?.dataset?.source || '未取得',
    asOf: block?.dataset?.as_of || block?.dataset?.actual_range?.end_date || '未提供',
  }));
  return `<section class="asset-research-context" aria-label="资产研究上下文"><article><span class="eyebrow">PEERS</span><h2>同类比较</h2><p class="muted small">当前 DataHub 尚未返回可核对的同类集合；不使用静态排名或虚构估值填充。</p></article><article><span class="eyebrow">THEME EXPOSURE</span><h2>主题暴露</h2><p class="muted small">当前资产尚无来自真实数据源的主题暴露结果；待产业链/持仓 Provider 接入后显示。</p></article><article class="asset-source-matrix"><span class="eyebrow">SOURCES & COVERAGE</span><h2>来源与口径</h2>${sources.length ? `<ul>${sources.map(item => `<li><strong>${e(item.name)}</strong><span>${e(item.provider)}</span><span>${e(STATE_LABELS[item.status] || item.status)} · ${e(item.asOf)}</span></li>`).join('')}</ul>` : '<p class="muted small">查询资产后，这里会按区块列出实际数据源、截止时间和覆盖状态。</p>'}</article></section>`;
}

export function readAssetObservation(form) {
  const data = new FormData(form);
  return {
    asset: String(data.get('asset') || '').trim().toUpperCase(),
    asset_type: String(data.get('asset_type') || 'stock'),
    source: String(data.get('source') || 'auto'),
    start_date: String(data.get('start_date') || '') || null,
    end_date: String(data.get('end_date') || '') || null,
    adjustment: String(data.get('adjustment') || 'qfq'),
    sections: ['overview', 'history', 'financials', 'activity', 'announcements', 'news', 'research'],
  };
}

export function renderAssetWorkspace({ observation = null, rows = {}, watchlists = [], notes = [], alerts = [], notifications = [], busy = false } = {}) {
  const blocks = observation?.blocks || Object.fromEntries(Object.keys(LABELS).map(key => [key, { status: 'empty' }]));
  const today = new Date().toISOString().slice(0, 10);
  const start = new Date(); start.setFullYear(start.getFullYear() - 1);
  return `<header class="page-header"><div><div class="eyebrow">ASSET OBSERVATION</div><h1>资产观察</h1><p class="muted">行情、财务、事件、公告与资料分别取数；每个区块独立显示真实状态。</p></div><button class="button" data-refresh>刷新本地状态</button></header><form class="asset-search" data-asset-observation><label>证券代码<input name="asset" value="${e(observation?.asset || '')}" placeholder="例如 600519.SH" pattern="[A-Za-z0-9._-]+" required></label><label>类型<select name="asset_type">${[['stock', '股票'], ['etf', 'ETF'], ['index', '指数'], ['fund', '基金'], ['theme', '主题']].map(([id, label]) => `<option value="${id}" ${observation?.asset_type === id ? 'selected' : ''}>${label}</option>`).join('')}</select></label><label>起始日<input type="date" name="start_date" value="${start.toISOString().slice(0, 10)}" required></label><label>结束日<input type="date" name="end_date" value="${today}" required></label><label>复权<select name="adjustment"><option value="qfq">前复权</option><option value="none">不复权</option><option value="hfq">后复权</option></select></label><button class="button primary" ${busy ? 'disabled' : ''}>${busy ? '正在更新…' : '更新全部区块'}</button></form>${assetHeader(observation, rows)}${marketMetrics(rows)}${researchContext(observation)}<div class="asset-workspace-grid"><div class="asset-blocks">${Object.entries(blocks).map(([name, block]) => blockCard(name, block, rows[name] || [])).join('')}</div>${personalPanel({ observation, watchlists, notes, alerts, notifications })}</div>`;
}
