import { escapeHTML as e } from './markdown.mjs';
import { icon } from './icons.mjs';
import { empty } from './views.mjs';

const list = (value) => Array.isArray(value) ? value : [];
const labels = {
  ready: '已接入', blocked_config: '待配置', blocked_dependency: '缺少依赖', disabled: '未接入', error: '接入异常',
  untested: '未检测', checking: '检测中', healthy: '健康', degraded: '降级', unavailable: '不可用',
  none: '无需鉴权', api_key: 'API Key', account: '账号授权', terminal: '本机终端', local: '本地数据',
  formal: '正式来源', datahub: '当前 DataHub', legacy: '旧适配器',
};
const badge = (text, tone = '') => `<span class="badge ${tone}">${e(text)}</span>`;
const truth = (label, value) => `<span class="truth-item ${value ? 'yes' : 'no'}"><span aria-hidden="true">${value ? '●' : '○'}</span>${e(label)}</span>`;

export function filterDataCatalog(catalog = {}, { view = 'capabilities', query = '', category = '', market = '', status = '', auth = '' } = {}) {
  const q = String(query).trim().toLocaleLowerCase();
  if (view === 'sources') return list(catalog.sources).filter(source => {
    const ready = source.readiness || {};
    return (!q || `${source.name} ${source.id} ${source.description} ${source.markets?.join(' ')}`.toLocaleLowerCase().includes(q))
      && (!market || list(source.markets).includes(market))
      && (!status || ready.integration_state === status || ready.health === status)
      && (!auth || source.auth_type === auth);
  });
  return list(catalog.capabilities).filter(capability => (!q || `${capability.name} ${capability.id} ${capability.description} ${capability.tool_id}`.toLocaleLowerCase().includes(q))
    && (!category || capability.category === category)
    && (!market || list(capability.markets).includes(market))
    && (!status || (status === 'ready' ? capability.callable_source_count > 0 : capability.callable_source_count === 0)));
}

function summaryCards(summary = {}) {
  return `<section class="data-summary" aria-label="数据目录汇总">
    <div><strong>${e(summary.capabilities ?? 0)}</strong><span>数据能力</span></div>
    <div><strong>${e(summary.sources ?? 0)}</strong><span>数据来源</span></div>
    <div><strong>${e(summary.callable_sources ?? 0)}</strong><span>当前可调用</span></div>
    <div><strong>${e(summary.needs_configuration ?? 0)}</strong><span>需要配置</span></div>
    <div><strong>${e(summary.unavailable ?? 0)}</strong><span>检测不可用</span></div>
  </section>`;
}

function capabilityCard(item, busy) {
  const ready = item.callable_source_count > 0;
  return `<article class="data-card capability-data-card">
    <div class="card-top"><span class="skill-icon">${icon('database')}</span><div><p class="eyebrow">${e(item.category)}</p><h2>${e(item.name)}</h2></div></div>
    <p class="card-description">${e(item.description)}</p>
    <div class="data-card-meta"><span>${e(item.source_count)} 个候选来源</span><span>${e(item.callable_source_count)} 个可调用</span></div>
    <div class="data-card-fields">${list(item.fields).slice(0, 4).map(field => `<code>${e(field)}</code>`).join('')}</div>
    <div class="card-state">${badge(ready ? '可通过 DataHub 调用' : '暂无已适配来源', ready ? 'live' : 'danger')}<div class="button-row"><button class="button small" data-data-capability-detail="${e(item.id)}">查看来源矩阵</button><button class="button small primary" data-use-data-tool="${e(item.tool_id)}" ${busy || !ready ? 'disabled' : ''}>放入研究草稿</button></div></div>
  </article>`;
}

function sourceCard(item, busy) {
  const ready = item.readiness || {};
  const feeWarning = ['possibly_metered', 'account'].includes(item.fee);
  return `<article class="data-card source-data-card">
    <div class="card-top"><span class="skill-icon">${icon('database')}</span><div><p class="eyebrow">${e(labels[item.family] || item.family)} · ${e(item.source_type)}</p><h2>${e(item.name)}</h2><code>${e(item.id)}</code></div></div>
    <p class="card-description">${e(item.description)}</p>
    <div class="truth-strip" aria-label="来源就绪状态">${truth('有代码', ready.code_exists)}${truth('已适配', ready.integration_completed)}${truth('已配置', ready.configured)}${truth('允许', ready.allowed)}</div>
    <div class="data-card-meta"><span>${e(labels[item.auth_type] || item.auth_type)}</span><span>${e(list(item.markets).join('、') || '覆盖未声明')}</span></div>
    <div class="card-state">${badge(`${labels[ready.integration_state] || ready.integration_state} · ${labels[ready.health] || ready.health}`, ready.callable ? 'live' : ready.health === 'unavailable' ? 'danger' : '')}<div class="button-row"><button class="button small" data-data-source-detail="${e(item.id)}">查看详情</button><button class="button small" data-probe-source="${e(item.id)}" ${busy || ready.health === 'checking' ? 'disabled' : ''}>${ready.health === 'checking' ? '检测中…' : feeWarning ? '检测连接 · 可能计费' : '检测连接'}</button></div></div>
  </article>`;
}

export function renderDataCatalog({ catalog = {}, view = 'capabilities', query = '', category = '', market = '', status = '', auth = '', busy = false, error = '', probe = null } = {}) {
  const categories = [...new Set(list(catalog.capabilities).map(item => item.category))];
  const markets = [...new Set((view === 'sources' ? list(catalog.sources) : list(catalog.capabilities)).flatMap(item => list(item.markets)))];
  const results = filterDataCatalog(catalog, { view, query, category, market, status, auth });
  const filters = `<div class="capability-filters data-filters"><label class="search-box"><span aria-hidden="true">⌕</span><input id="cap-search" data-cap-query type="search" aria-label="搜索数据能力和来源" value="${e(query)}" placeholder="搜索名称、数据集或技术 ID"></label>${view === 'capabilities' ? `<label>数据类型<select data-data-category><option value="">全部类型</option>${categories.map(value => `<option value="${e(value)}" ${category === value ? 'selected' : ''}>${e(value)}</option>`).join('')}</select></label>` : `<label>鉴权<select data-data-auth><option value="">全部</option>${[['none','无需鉴权'],['api_key','API Key'],['account','账号授权'],['terminal','本机终端'],['local','本地数据']].map(([value,label]) => `<option value="${value}" ${auth === value ? 'selected' : ''}>${label}</option>`).join('')}</select></label>`}<label>市场<select data-data-market><option value="">全部市场</option>${markets.map(value => `<option value="${e(value)}" ${market === value ? 'selected' : ''}>${e(value)}</option>`).join('')}</select></label><label>状态<select data-data-status><option value="">全部状态</option>${[['ready','可调用 / 已接入'],['disabled','未接入'],['blocked_config','待配置'],['healthy','健康'],['unavailable','不可用']].map(([value,label]) => `<option value="${value}" ${status === value ? 'selected' : ''}>${label}</option>`).join('')}</select></label></div>`;
  return `${summaryCards(catalog.summary)}<div class="data-view-switch" role="tablist" aria-label="数据目录视图"><button class="button small ${view === 'capabilities' ? 'primary' : ''}" role="tab" aria-selected="${view === 'capabilities'}" data-data-view="capabilities">按数据能力</button><button class="button small ${view === 'sources' ? 'primary' : ''}" role="tab" aria-selected="${view === 'sources'}" data-data-view="sources">按数据来源</button></div><p class="notice warning">目录读取不会联网或启动专业终端。“有代码”不等于“已适配”，只有“当前可调用”的来源才能被 DSH 选中。</p>${probe ? `<p class="notice ${probe.health === 'healthy' ? 'success' : probe.health === 'checking' ? 'warning' : 'error'}" role="status">${e(probe.source_id)}：${e(labels[probe.health] || probe.health)}${probe.duration_ms !== null ? ` · ${e(probe.duration_ms)}ms` : ''}${probe.failure_code ? ` · ${e(probe.failure_code)}` : ''}</p>` : ''}${error ? `<p class="notice error" role="alert">${e(error)}</p>` : ''}${filters}${results.length ? `<div class="data-grid">${results.map(item => view === 'sources' ? sourceCard(item, busy) : capabilityCard(item, busy)).join('')}</div>` : empty('没有匹配的数据能力', '调整视图或筛选；目录不会把未接入来源伪装成可用。')}`;
}

export function renderDataCapabilityDetail(item) {
  if (!item) return '';
  return `<section class="capability-detail data-detail"><div class="section-heading"><div><span class="eyebrow">数据能力</span><h2>${e(item.name)}</h2><code>${e(item.tool_id)}</code></div><button class="button small" data-cap-close>关闭详情</button></div><p>${e(item.description)}</p><dl class="runtime-details"><div><dt>市场 / 资产</dt><dd>${e(list(item.markets).join('、'))} / ${e(list(item.assets).join('、'))}</dd></div><div><dt>参数</dt><dd>${e(list(item.parameters).map(value => value.name).join('、'))}</dd></div><div><dt>返回字段</dt><dd>${e(list(item.fields).join('、'))}</dd></div><div><dt>候选 / 可调用来源</dt><dd>${e(item.source_count)} / ${e(item.callable_source_count)}</dd></div></dl><h3>来源矩阵</h3><div class="source-matrix">${list(item.bindings).map(binding => `<div><strong>${e(binding.source.name)}</strong><span>优先级 ${e(binding.priority)} · ${e(binding.datasets.join('、'))}</span><span>${binding.implemented ? '能力已适配' : '能力仅登记'} · ${e(labels[binding.source.readiness.health] || binding.source.readiness.health)}</span></div>`).join('')}</div>${item.callable_source_count ? `<button class="button primary" data-use-data-tool="${e(item.tool_id)}">放入研究草稿</button>` : '<p class="notice warning">目前没有完成适配且满足配置的来源，不能运行。</p>'}</section>`;
}

export function renderDataSourceDetail(item, busy = false) {
  if (!item) return '';
  const readiness = item.readiness || {};
  return `<section class="capability-detail data-detail"><div class="section-heading"><div><span class="eyebrow">${e(labels[item.family] || item.family)} · ${e(item.source_type)}</span><h2>${e(item.name)}</h2><code>${e(item.id)}</code></div><button class="button small" data-cap-close>关闭详情</button></div><p>${e(item.description)}</p><div class="truth-strip detail">${truth('代码存在', readiness.code_exists)}${truth('DataHub 已适配', readiness.integration_completed)}${truth('配置齐备', readiness.configured)}${truth('依赖齐备', readiness.dependency_ready)}${truth('允许调用', readiness.allowed)}${truth('当前可调用', readiness.callable)}</div><dl class="runtime-details"><div><dt>鉴权</dt><dd>${e(labels[item.auth_type] || item.auth_type)}；仅显示配置项名称：${e(list(item.config_keys).join('、') || '无')}</dd></div><div><dt>依赖</dt><dd>${e(list(item.dependencies).join('、') || '无额外依赖')}</dd></div><div><dt>市场</dt><dd>${e(list(item.markets).join('、'))}</dd></div><div><dt>接入 / 健康</dt><dd>${e(labels[readiness.integration_state] || readiness.integration_state)} / ${e(labels[readiness.health] || readiness.health)}</dd></div></dl><h3>已登记数据集</h3><div class="source-matrix">${list(item.bindings).map(binding => `<div><strong>${e(binding.capability.name)}</strong><span>${e(binding.datasets.join('、'))}</span><span>优先级 ${e(binding.priority)} · ${binding.implemented ? '已适配' : '仅登记'}</span></div>`).join('')}</div><p class="small muted">连接检测只针对本来源；不会检测其他来源。专业或可能计费来源应先确认账号与费用。</p><button class="button" data-probe-source="${e(item.id)}" ${busy ? 'disabled' : ''}>检测这个来源</button></section>`;
}
