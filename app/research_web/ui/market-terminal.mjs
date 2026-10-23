import { escapeHTML as e } from './markdown.mjs';
import { assetHref } from './asset-navigation.mjs';
import { safeLog } from './core.mjs';

export const HORIZONS = { intraday: ['日内／超短', '当日及 1—3 日 · 盘中临时读数'], swing: ['波段', '5—20 个交易日 · 同源历史观察'], allocation: ['中期配置', '20—60 个交易日 · 历史与风险约束'] };
const AXES = { trend: '趋势', breadth: '广度', sentiment: '情绪', funds: '资金', valuation: '估值', risk: '风险' };
const list = value => Array.isArray(value) ? value : [];
const num = value => typeof value === 'number' && Number.isFinite(value) ? value : null;
const show = value => num(value) === null ? '—' : value.toLocaleString('zh-CN', { maximumFractionDigits: 2 });
const day = value => { const date = new Date(value); return value && Number.isFinite(date.getTime()) ? new Intl.DateTimeFormat('sv-SE', { timeZone: 'Asia/Shanghai' }).format(date) : ''; };
const raw = value => e(JSON.stringify(value ?? null, null, 2));
export const terminalIndices = state => state.snapshot?.sections?.['indices:terminal-v2'] || state.snapshot?.sections?.indices || {};
export function terminalCatalogRows(state) {
  const quotes = new Map(list(terminalIndices(state).rows).map(row => [row.asset, row]));
  const items = list(state.catalog?.items);
  return items.length ? items.map(item => ({ ...item, ...quotes.get(item.asset) })) : [...quotes.values()];
}
const STYLE_ROWS = [['大盘', '399373.SZ', '399372.SZ'], ['中盘', '399375.SZ', '399374.SZ'], ['小盘', '399377.SZ', '399376.SZ']];
function periodStyle(state) {
  const profile = state.analysis?.style_profile;
  return profile?.horizon === (state.horizon || 'intraday') ? profile : {};
}
function styleDescription(state) {
  const profile = periodStyle(state);
  const complete = profile.status === 'observed' && STYLE_ROWS.flatMap(([, ...assets]) => assets).every(asset => list(profile.cells).some(cell => cell.asset === asset && cell.status === 'observed' && num(cell.return_pct) !== null));
  const style = complete ? profile.style_dominance : 'unknown', size = complete ? profile.size_dominance : 'unknown';
  const labels = { growth: '成长相对领先', value: '价值相对领先', balanced: '成长／价值差异较小', unknown: '成长／价值待确认' };
  const sizes = { large: '大盘相对领先', mid: '中盘相对领先', small: '小盘相对领先', balanced: '规模差异较小', unknown: '规模待确认' };
  return `${labels[style] || labels.unknown} · ${sizes[size] || sizes.unknown}`;
}
export function decisionStrip(state) {
  const horizon = state.horizon || 'intraday', analysis = state.analysis || {}, quotes = state.snapshot?.sections?.quotes || {}, summary = quotes.summary || {};
  const cache = analysis.cache_state?.quotes || {};
  const stale = quotes.stale || cache.stale || cache.status === 'stale';
  const incomplete = quotes.complete === false || quotes.pagination_complete === false || summary.temporal_complete === false || ['partial', 'failed'].includes(cache.status);
  const status = stale ? '陈旧快照 · 保留上次行情' : incomplete ? '未完整 · 保留数据缺口' : quotes.snapshot_id && quotes.complete === true ? '缓存快照' : '覆盖待确认';
  const source = quotes.provider === 'eastmoney' ? '东方财富' : quotes.provider || '来源待确认';
  const counts = ['up', 'down', 'flat'].map(key => num(summary[key]));
  const covered = counts.every(n => n !== null) ? counts.reduce((a, b) => a + b, 0) : null;
  const participation = covered > 0 ? `${show(summary.up / covered * 100)}% 上涨` : '—';
  return `<section class="market-decision"><div><div class="market-decision-head"><span>市场状态</span><div class="market-horizons">${Object.entries(HORIZONS).map(([key, [label]]) => `<button type="button" data-market-action="horizon" data-horizon="${key}" aria-pressed="${horizon === key}">${label}</button>`).join('')}</div></div><h2>行情快照${state.snapshot ? '已取得' : '待取得'}，择时结论待验证</h2><p>${e(HORIZONS[horizon][1])}${state.analysisLoading ? ' · 证据读取中' : ''}</p><p class="market-style-description">${e(styleDescription(state))}</p></div><div><span>快照市场参与度</span><strong>${e(participation)}</strong><small>有效报价 ${e(show(covered))} 只 · 缺报价 ${e(show(summary.unknown))} 只</small><small class="market-participation-provenance">${e(source)} · 行情 ${e(quotes.as_of || '未提供')} · ${e(status)}</small></div><div><span>综合评分／权益区间</span><strong>待验证</strong><small>${e(analysis.validation?.reason || '六维证据及样本外检验齐备后发布')}</small></div></section>`;
}
export function indexCollection(state, metadataMarkup = '') {
  const all = terminalCatalogRows(state), pins = state.pins ?? state.catalog?.default_pins ?? all.map(row => row.asset);
  const search = String(state.indexSearch || '').trim().toLowerCase(), group = state.indexGroup || 'pins';
  const rows = all.filter(row => (search || group === 'all' || group === 'pins' && pins.includes(row.asset) || row.group === group) && (!search || `${row.asset} ${row.name} ${row.code}`.toLowerCase().includes(search))).sort((a, b) => Number(pins.includes(b.asset)) - Number(pins.includes(a.asset)));
  const groups = [{ id: 'pins', label: '常用' }, { id: 'all', label: '全部' }, ...list(state.catalog?.groups)];
  return `<section class="market-panel market-index-collection"><header><h2>指数行情</h2><div class="market-index-tools">${groups.map(item => `<button type="button" data-market-action="index-group" data-group="${e(item.id)}" aria-pressed="${group === item.id}">${e(item.label)}</button>`).join('')}<form data-market-index-search><input aria-label="搜索指数代码或名称" type="search" id="market-index-search" name="index_search" data-market-index-search-draft value="${e(state.indexSearchDraft ?? state.indexSearch ?? '')}" placeholder="搜索代码或名称"><button type="submit">搜索</button></form><button type="button" data-market-action="pins-reset">恢复默认</button></div></header><div class="market-terminal-indices">${rows.length ? rows.map(row => `<article class="market-terminal-index"><button type="button" data-market-action="pin" data-asset="${e(row.asset)}" aria-pressed="${pins.includes(row.asset)}" aria-label="${e(row.name || row.asset)}置顶">${pins.includes(row.asset) ? '★' : '☆'}</button><a href="${e(assetHref(row.asset, 'index'))}"><span>${e(row.name || row.asset)}</span><strong>${e(show(row.price))}</strong><span class="market-${num(row.change_pct) === null ? 'unknown' : row.change_pct > 0 ? 'up' : row.change_pct < 0 ? 'down' : 'flat'}">${num(row.change_pct) === null ? '行情待取得' : `${row.change_pct > 0 ? '+' : ''}${show(row.change_pct)}%`}</span><small>${e(row.asset)}</small><small>${e(day(row.as_of) || '行情日期未提供')}${day(row.as_of) && day(terminalIndices(state).as_of) && day(row.as_of) !== day(terminalIndices(state).as_of) ? ' · 旧日' : ''}</small></a><details data-disclosure-key="market-index-${e(row.asset)}"><summary>口径</summary><p>${e(row.publisher || '发布方待确认')} · ${e(row.return_basis || '收益口径待确认')}</p><p>行情：${e(row.as_of || '未提供')} · 采集：${e(terminalIndices(state).retrieved_at || '未提供')}</p>${/^https:\/\//.test(row.definition_url || '') ? `<a href="${e(row.definition_url)}" target="_blank" rel="noreferrer">官方定义</a>` : ''}</details></article>`).join('') : '<p class="market-empty">没有匹配的指数；可选择全部或恢复默认。</p>'}</div>${state.catalogError ? `<p class="market-error market-caption" role="alert">${e(state.catalogError)}</p>` : ''}<p class="market-caption">星标按当前账号保存 · 数据缺口保留 · 指数进入资产观察 · ${e(terminalIndices(state).stale ? '陈旧快照' : terminalIndices(state).complete === false ? '部分覆盖' : '覆盖以来源详情为准')}</p>${metadataMarkup}</section>`;
}
export function evidencePanels(state) {
  const analysis = state.analysis || {}, axes = analysis.axes || {}, rows = terminalCatalogRows(state);
  const profile = periodStyle(state), horizon = state.horizon || 'intraday';
  const periodLabel = horizon === 'intraday' ? '当日涨跌幅' : `近${horizon === 'swing' ? 20 : 60}个交易日价格收益`;
  const style = `<section class="market-panel"><header><h2>风格定位</h2><small>${periodLabel} · 描述性观测</small></header><div class="market-style-grid"><span></span><span>价值</span><span>成长</span>${STYLE_ROWS.map(([label, ...assets]) => `<span>${label}</span>${assets.map(asset => { const row = rows.find(item => item.asset === asset), cell = list(profile.cells).find(item => item.asset === asset), value = cell?.status === 'observed' ? num(cell.return_pct) : null; return `<a href="${e(assetHref(asset, 'index'))}" class="market-style-cell" data-style-asset="${e(asset)}"><strong class="market-${value === null ? 'unknown' : value > 0 ? 'up' : value < 0 ? 'down' : 'flat'}">${value === null ? '—' : `${show(value)}%`}</strong><small>${e(row?.name || asset)}</small><small>${e(value === null ? cell?.reason || '数据待取得' : cell?.provenance?.quote_as_of || '行情日期未提供')}</small></a>`; }).join('')}`).join('')}</div><p class="market-caption">${e(styleDescription(state))} · 成长减价值 ${num(profile.growth_minus_value_pp) === null ? '—' : e(show(profile.growth_minus_value_pp))} 个百分点</p><p class="market-caption">同系列价格收益口径 · 历史不足不判定均衡。微盘观察：${e(profile.micro?.reason || '定义及来源待核验')} 中证2000不作为微盘替身。</p><details class="market-metadata" data-disclosure-key="market-style-provenance"><summary>风格规则、原始收益与来源</summary><pre>${raw(profile)}</pre><p class="market-caption">价格指数不含分红；盘中读数临时，历史首次观测未核验PIT；相对领先不等于未来收益或配置建议。</p></details></section>`;
  const evidence = `<section class="market-panel"><header><h2>六维证据</h2><small>综合结论待验证</small></header><div class="market-six-axes">${Object.entries(AXES).map(([key, label]) => { const axis = axes[key] || {}; return `<article><h3>${label}</h3><strong>${e(show(axis.score))}<small>${num(axis.score) === null ? '待验证' : '描述读数'}</small></strong><p>${e(axis.reason || '证据尚未取得，不填中性分。')}</p><details data-disclosure-key="market-axis-${key}" data-market-detail="axis-${key}" ${state.openDetails?.includes(`axis-${key}`) ? 'open' : ''}><summary>原始指标、公式与来源</summary><p>状态：${e(axis.status || 'unavailable')}</p><pre>${raw({ metrics: axis.metrics, formula: axis.formula, provenance: axis.provenance, scoring: axis.scoring })}</pre></details></article>`; }).join('')}</div><p class="market-caption">固定规则 · 缺项不补零、不重分配权重 · 历史 ${e(show(analysis.history?.observation_count ?? analysis.history?.count ?? analysis.history_count))} 日</p>${state.analysisError ? `<p class="market-caption market-error" role="alert">${e(state.analysisError)}</p>` : ''}<details class="market-metadata" data-disclosure-key="market-validation-diagnostics"><summary>验证与缓存诊断</summary><pre>${raw({ validation: analysis.validation, diagnostics: analysis.diagnostics ?? analysis.history?.diagnostics, cache_state: analysis.cache_state })}</pre></details></section>`;
  return `<div class="market-evidence-grid">${style}${evidence}</div>`;
}

export function newPortfolioDraft() { return { source: 'manual', as_of: '', currency: 'CNY', cash: '', holdings: [{ asset: '', quantity: '', cost: '' }], csv_text: '', risk_tolerance: '', equity_min: '', equity_max: '', single_name_max: '', sector_max: '' }; }
export function portfolioPayload(draft) {
  const numeric = (value, label) => { if (String(value).trim() === '' || !Number.isFinite(Number(value))) throw new Error(`${label}须填写有效数值`); return Number(value); };
  if (!/^\d{4}-\d{2}-\d{2}$/.test(draft.as_of)) throw new Error('请明确填写持仓日期');
  const payload = { source: draft.source, as_of: draft.as_of, currency: draft.currency, cash: numeric(draft.cash, '现金') };
  if (payload.cash < 0) throw new Error('现金不得小于零');
  if (draft.source === 'csv') { if (!draft.csv_text.trim()) throw new Error('请填写CSV内容或选择本地CSV文件'); payload.csv_text = draft.csv_text; }
  else payload.holdings = draft.holdings.map(row => ({ asset: row.asset.trim().toUpperCase(), quantity: numeric(row.quantity, '数量'), ...(row.cost === '' ? {} : { cost: numeric(row.cost, '成本') }) }));
  const riskKeys = ['equity_min', 'equity_max', 'single_name_max', 'sector_max'];
  if (draft.risk_tolerance || riskKeys.some(key => draft[key] !== '')) {
    if (!draft.risk_tolerance) throw new Error('请选择风险档');
    payload.risk_profile = { risk_tolerance: draft.risk_tolerance };
    for (const key of riskKeys) { const value = numeric(draft[key], '风险比例'); if (value < 0 || value > 100) throw new Error('风险比例须在0至100之间'); payload.risk_profile[key] = value / 100; }
    if (payload.risk_profile.equity_min > payload.risk_profile.equity_max) throw new Error('权益下限不得超过上限');
  }
  return payload;
}
function savedPortfolio(item) {
  const portfolio = item.portfolio || item, valuation = item.valuation || {}, profile = portfolio.risk_profile || {};
  const key = item.snapshot_id || `${portfolio.as_of}:${portfolio.source}`;
  const positions = Array.isArray(item.positions) ? item.positions : list(portfolio.holdings).map(holding => ({ ...holding, valuation_status: 'unavailable' }));
  const observed = valuation.status === 'observed' && valuation.stale !== true;
  const ratio = value => num(value) === null ? '—' : `${show(value * 100)}%`;
  const sourceLabels = { manual: '手工录入', csv: 'CSV导入' };
  const statusLabels = { observed: '行情估值', suspended_reference: '停牌参考价，不计估值', stale: '行情陈旧，不计估值', unavailable: '行情待核验' };
  const tradeLabels = { trading: '正常交易', suspended: '停牌', unlisted: '未上市', delisted: '已退市', unknown: '交易状态待确认' };
  const price = row => row.valuation_status === 'observed' && num(row.price) !== null ? `${e(show(row.price))}<small>成交报价</small>` : num(row.reference_price) !== null ? `${e(show(row.reference_price))}<small>停牌参考，不计当前估值</small>` : '—';
  const metrics = [['现金（用户声明）', show(portfolio.cash)], ['持仓市值', show(observed ? valuation.holdings_value : null)], ['资产总值', show(observed ? valuation.total_value : null)], ['权益比例', ratio(observed ? valuation.equity_ratio : null)]];
  const checks = [['equity_min', '权益下限'], ['equity_max', '权益上限'], ['single_name_max', '单券上限'], ['sector_max', '行业上限']].map(([constraint, label]) => {
    const check = list(item.risk_checks).find(value => value.constraint === constraint), declared = profile[constraint];
    const status = check?.status === 'within_declared_limit' ? '符合用户约束' : check?.status === 'outside_declared_limit' ? '超出用户约束' : num(declared) === null ? '未设置' : '待核验';
    const reason = check?.reason || (constraint === 'sector_max' ? '缺少同日逐股行业归属，无法核验行业集中度。' : num(declared) !== null && !check ? '缺少完整行情估值，暂不能核验。' : '');
    return `<li><span>${label} ${e(ratio(declared))}</span><span>实际 ${e(ratio(check?.observed))} · ${e(status)}</span>${reason ? `<small>${e(reason)}</small>` : ''}</li>`;
  }).join('');
  const holdings = positions.length ? `<div class="market-table-wrap"><table class="market-table market-saved-positions"><thead><tr>${['证券', '数量', '成本（用户声明）', '报价／参考价', '市值', '状态'].map(label => `<th scope="col">${label}</th>`).join('')}</tr></thead><tbody>${positions.map(row => `<tr><td><a href="${e(assetHref(row.asset))}">${e(row.asset)}</a></td><td>${e(show(row.quantity))}</td><td>${e(show(row.cost))}</td><td>${price(row)}<small>${e(row.quote_as_of || '行情时间未提供')}</small></td><td>${e(show(row.valuation_status === 'observed' && observed ? row.market_value : null))}</td><td>${e(statusLabels[row.valuation_status] || '行情待核验')}<small>${e(tradeLabels[row.trade_status] || tradeLabels.unknown)}</small></td></tr>`).join('')}</tbody></table></div>` : '<p>未录入证券持仓。</p>';
  return `<details class="market-saved-snapshot" data-disclosure-key="market-portfolio-snapshot-${e(key)}"><summary>${e(portfolio.as_of || '持仓日期未提供')} · ${e(portfolio.currency || '币种未提供')} · ${e(sourceLabels[portfolio.source] || portfolio.source || '来源未提供')}</summary><div class="market-saved-body"><div class="market-saved-metrics">${metrics.map(([label, value]) => `<div><span>${label}</span><strong>${e(value)}</strong></div>`).join('')}</div><p>${e(portfolio.currency || '')} · ${valuation.stale || valuation.status === 'stale' ? '行情陈旧 · ' : ''}${e(valuation.reason || '尚未取得完整行情估值；保存的持仓与成本由用户声明。')}</p>${holdings}<p>行情 ${e(valuation.as_of || '未提供')} · 采集 ${e(valuation.retrieved_at || '未提供')} · 快照 ${e(valuation.quote_snapshot_id || '未提供')}</p><div class="market-saved-risk"><h3>用户风险约束核验</h3><p>风险档：${e(({ conservative: '保守', balanced: '均衡', aggressive: '积极' })[profile.risk_tolerance] || '未设置')} · 缺少约束或有效估值时不生成仓位建议。</p><ul>${checks}</ul></div><details data-disclosure-key="market-portfolio-source-${e(key)}"><summary>持仓原件、行情来源与核验详情</summary><pre>${raw(item)}</pre></details></div></details>`;
}
export function portfolioPanel(state) {
  const draft = state.portfolioDraft || newPortfolioDraft(), field = (key, label, type = 'number') => `<label>${label}<input type="${type}" id="market-portfolio-${key}" data-market-portfolio="${key}" value="${e(draft[key])}" ${type === 'number' ? 'min="0" step="any"' : ''}></label>`;
  const items = list(state.portfolios?.items), preview = state.portfolioPreview;
  return `<section class="market-panel market-portfolio"><details data-disclosure-key="market-portfolio" data-market-detail="portfolio" ${state.openDetails?.includes('portfolio') ? 'open' : ''}><summary>个人组合与仓位参考 <span>${items.length ? `已保存 ${items.length} 份持仓快照` : '未载入持仓'}</span></summary><div class="market-portfolio-body"><p>金元证券：官方接口／权限待确认。手工／CSV快照经校验预览后按当前账号保存。</p><div class="market-portfolio-saved">${items.map(savedPortfolio).join('')}</div><form data-market-portfolio-form><div class="market-portfolio-fields"><label>持仓来源<select id="market-portfolio-source" data-market-portfolio="source"><option value="manual" ${draft.source === 'manual' ? 'selected' : ''}>手工录入</option><option value="csv" ${draft.source === 'csv' ? 'selected' : ''}>CSV导入</option></select></label>${field('as_of', '持仓日期', 'date')}<label>币种<select id="market-portfolio-currency" data-market-portfolio="currency">${['CNY', 'USD', 'HKD'].map(value => `<option ${draft.currency === value ? 'selected' : ''}>${value}</option>`).join('')}</select></label>${field('cash', '现金')}</div>${draft.source === 'csv' ? `<label class="market-csv">CSV（asset,quantity,cost；cost可选）<input type="file" accept=".csv,text/csv" data-market-csv-file><textarea id="market-portfolio-csv" data-market-portfolio="csv_text" rows="5" placeholder="asset,quantity,cost">${e(draft.csv_text)}</textarea></label>` : `<div class="market-holdings">${draft.holdings.map((row, index) => `<div><label>证券<input id="market-holding-${index}-asset" data-market-holding="asset" data-row="${index}" value="${e(row.asset)}" placeholder="000001.SZ"></label><label>数量<input type="number" min="0" step="any" id="market-holding-${index}-quantity" data-market-holding="quantity" data-row="${index}" value="${e(row.quantity)}"></label><label>成本（可选）<input type="number" min="0" step="any" id="market-holding-${index}-cost" data-market-holding="cost" data-row="${index}" value="${e(row.cost)}"></label><button type="button" data-market-action="holding-remove" data-row="${index}" ${draft.holdings.length === 1 ? 'disabled' : ''}>移除</button></div>`).join('')}<button type="button" data-market-action="holding-add">添加持仓</button></div>`}<div class="market-portfolio-fields"><label>风险档<select id="market-portfolio-risk" data-market-portfolio="risk_tolerance"><option value="">请选择</option>${[['conservative', '保守'], ['balanced', '均衡'], ['aggressive', '积极']].map(([value, label]) => `<option value="${value}" ${draft.risk_tolerance === value ? 'selected' : ''}>${label}</option>`).join('')}</select></label>${field('equity_min', '权益下限（%）')}${field('equity_max', '权益上限（%）')}${field('single_name_max', '单券上限（%）')}${field('sector_max', '行业上限（%）')}</div><p>缺持仓、风险约束或验证证据时不生成仓位建议。</p><button type="submit" ${state.portfolioBusy ? 'disabled' : ''}>${state.portfolioBusy ? '处理中…' : '校验并预览'}</button></form>${state.portfolioError ? `<p class="market-error" role="alert">${e(state.portfolioError)}</p>` : ''}${preview ? `<div class="market-portfolio-preview"><h3>保存前预览</h3><pre>${raw({ ...preview, confirmation_token: undefined })}</pre><button type="button" data-market-action="portfolio-confirm" ${!preview.confirmation_token || list(preview.errors).length || state.portfolioBusy ? 'disabled' : ''}>确认保存此快照</button></div>` : ''}</div></details></section>`;
}

// Per-activation and per-edit tickets fence late reads, previews and confirmations.
export function createTerminalController({ state, api, changed, storage, visible }) {
  let epoch = 0, analysisEpoch = 0, edits = 0, active = false, readerAbort = new AbortController();
  const currentAccount = () => String(globalThis.__RWB_USER_ID__ || 'local');
  let account = currentAccount();
  const pinKey = () => `rwb:${account}:market-pins-terminal-v2`;
  const canSend = () => active && account === currentAccount() && visible() && !readerAbort.signal.aborted;
  const isCurrent = ticket => ticket === epoch && canSend();
  state.horizon = 'intraday'; state.indexGroup = 'pins'; state.portfolioDraft = newPortfolioDraft(); state.openDetails = [];
  const invalidate = () => { edits++; state.portfolioPreview = null; state.portfolioError = ''; state.portfolioBusy = false; };
  function savePins() { try { storage?.setItem(pinKey(), JSON.stringify(state.pins)); } catch { safeLog('market_pins_save_failed', { status: 'failed' }); state.catalogError = '指数偏好保存失败，本次选择仍有效。'; } }
  async function analysis() {
    if (!canSend()) return;
    const ticket = epoch, current = ++analysisEpoch, horizon = state.horizon;
    state.analysisLoading = true; state.analysisError = ''; changed();
    try { const result = await api.request(`/market/analysis?horizon=${horizon}`, { signal: readerAbort.signal }); if (isCurrent(ticket) && current === analysisEpoch) state.analysis = result; }
    catch (error) { if (isCurrent(ticket) && current === analysisEpoch) { state.analysisError = error.message || '市场证据读取失败'; safeLog('market_analysis_failed', { status: 'failed' }); } }
    finally { if (isCurrent(ticket) && current === analysisEpoch) { state.analysisLoading = false; changed(); } }
  }
  async function activate() {
    readerAbort.abort(); readerAbort = new AbortController(); active = true;
    const ticket = ++epoch;
    if (account !== currentAccount()) { account = currentAccount(); state.pins = undefined; state.portfolioDraft = newPortfolioDraft(); state.portfolioPreview = null; state.portfolioBusy = false; state.portfolios = null; state.analysis = null; state.openDetails = []; edits++; }
    await Promise.allSettled([analysis(), (async () => { try { const result = await api.request('/market/indices/catalog', { signal: readerAbort.signal }); if (!isCurrent(ticket)) return; state.catalog = result; state.catalogError = ''; const allowed = new Set(list(result.items).map(row => row.asset)); if (!state.pins) { try { const saved = JSON.parse(storage?.getItem(pinKey()) || 'null'); state.pins = list(Array.isArray(saved) ? saved : result.default_pins).filter(asset => allowed.has(asset)); } catch { state.pins = list(result.default_pins); safeLog('market_pins_load_failed', { status: 'failed' }); } } changed(); } catch (error) { if (isCurrent(ticket)) { state.catalogError = error.message || '指数目录读取失败'; safeLog('market_catalog_failed', { status: 'failed' }); changed(); } } })(), (async () => { try { const result = await api.request('/market/portfolios', { signal: readerAbort.signal }); if (isCurrent(ticket)) { state.portfolios = result; changed(); } } catch (error) { if (isCurrent(ticket)) { state.portfolioError = error.message || '持仓快照读取失败'; safeLog('market_portfolios_failed', { status: 'failed' }); changed(); } } })()]);
  }
  async function preview() {
    if (!canSend()) return;
    invalidate(); const ticket = epoch, version = edits;
    try { const payload = portfolioPayload(state.portfolioDraft); state.portfolioBusy = true; changed(); if (!isCurrent(ticket) || version !== edits) return; const result = await api.request('/market/portfolios/preview', { method: 'POST', body: payload, signal: readerAbort.signal }); if (isCurrent(ticket) && version === edits) state.portfolioPreview = result; }
    catch (error) { if (isCurrent(ticket) && version === edits) { state.portfolioError = error.message || '持仓预览失败'; safeLog('market_portfolio_preview_failed', { status: 'failed' }); } }
    finally { if (isCurrent(ticket) && version === edits) { state.portfolioBusy = false; changed(); } }
  }
  async function confirm() {
    if (!canSend()) return;
    const token = state.portfolioPreview?.confirmation_token; if (!token || list(state.portfolioPreview.errors).length || state.portfolioBusy) return;
    const ticket = epoch, version = edits; state.portfolioBusy = true; changed();
    try { if (!isCurrent(ticket) || version !== edits) return; const result = await api.request('/market/portfolios', { method: 'POST', body: { confirmation_token: token }, signal: readerAbort.signal }); if (!isCurrent(ticket) || version !== edits) return; state.portfolios = { ...state.portfolios, items: [...list(state.portfolios?.items), result.item || result] }; state.portfolioPreview = null; state.notice = '持仓快照已保存。'; safeLog('market_portfolio_saved', { status: 'completed' }); }
    catch (error) { if (isCurrent(ticket) && version === edits) { state.portfolioError = error.message || '持仓保存失败'; safeLog('market_portfolio_save_failed', { status: 'failed' }); } }
    finally { if (isCurrent(ticket) && version === edits) { state.portfolioBusy = false; changed(); } }
  }
  function click(data) {
    if (data.marketAction === 'horizon' && HORIZONS[data.horizon]) { state.horizon = data.horizon; state.analysis = null; void analysis(); }
    else if (data.marketAction === 'index-group') { state.indexGroup = data.group; changed(); }
    else if (data.marketAction === 'pin' && terminalCatalogRows(state).some(row => row.asset === data.asset)) { const pins = new Set(state.pins ?? state.catalog?.default_pins ?? []); if (pins.has(data.asset)) pins.delete(data.asset); else pins.add(data.asset); state.pins = [...pins]; savePins(); changed(); }
    else if (data.marketAction === 'pins-reset') { state.pins = [...list(state.catalog?.default_pins)]; savePins(); changed(); }
    else if (data.marketAction === 'holding-add') { invalidate(); state.portfolioDraft.holdings.push({ asset: '', quantity: '', cost: '' }); changed(); }
    else if (data.marketAction === 'holding-remove') { const row = Number(data.row); if (Number.isInteger(row) && state.portfolioDraft.holdings.length > 1) { invalidate(); state.portfolioDraft.holdings.splice(row, 1); changed(); } }
    else if (data.marketAction === 'portfolio-confirm') void confirm();
    else return false;
    return true;
  }
  function input(target) {
    const data = target?.dataset || {};
    if ('marketIndexSearchDraft' in data) { state.indexSearchDraft = target.value; return true; }
    if (data.marketPortfolio && Object.hasOwn(state.portfolioDraft, data.marketPortfolio)) { invalidate(); state.portfolioDraft[data.marketPortfolio] = target.value; changed(); return true; }
    if (data.marketHolding && ['asset', 'quantity', 'cost'].includes(data.marketHolding) && state.portfolioDraft.holdings[Number(data.row)]) { invalidate(); state.portfolioDraft.holdings[Number(data.row)][data.marketHolding] = target.value; changed(); return true; }
    return false;
  }
  async function file(target) {
    if (!canSend()) return;
    invalidate(); changed(); const ticket = epoch, version = edits, selected = target.files?.[0];
    if (!selected) return;
    try { if (!isCurrent(ticket) || version !== edits) return; if (selected.size > 256 * 1024) throw new Error('CSV文件不得超过256 KiB'); const value = await selected.text(); if (isCurrent(ticket) && version === edits) { state.portfolioDraft.csv_text = value; changed(); } }
    catch (error) { if (isCurrent(ticket) && version === edits) { state.portfolioError = error.message || 'CSV读取失败'; safeLog('market_portfolio_csv_failed', { status: 'failed' }); changed(); } }
  }
  return { activate, analysis, click, input, file, preview, confirm, cancel(deactivate = true) { if (deactivate) active = false; epoch++; analysisEpoch++; readerAbort.abort(); readerAbort = new AbortController(); invalidate(); state.analysisLoading = false; } };
}
