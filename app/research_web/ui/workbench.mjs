import { escapeHTML as e } from './markdown.mjs';
import { renderAssetWorkspace } from './asset-workspace.mjs';
import { renderEtfPaper } from './etf-paper.mjs';
import { renderIntelligenceNavigation } from './intel.mjs';

export const SECTIONS = [
  ['market', '新闻', '市场新闻与主题资讯检索', 'search_news'],
  ['assets', '行情与基本面', '证券检索、行情、财务和公告', 'market_bars'],
  ['funds', '基金数据', '基本资料、净值、分红和披露持仓', 'fund_data'],
  ['industry', '研报', '行业与主题检索', 'search_research'],
  ['documents', '公告', '证券与主题公告检索', 'search_announcements'],
  ['etf-paper', 'ETF 模拟', '受约束的策略模拟与复盘', null],
];

const assetTabs = [['assets', '行情与基本面', '#/assets'], ['funds', '基金数据', '#/assets/funds'], ['dossiers', '研究档案', '#/assets?view=dossiers']];
const searchTabs = [['market', '新闻', '#/intel/search?kind=news'], ['industry', '研报', '#/intel/search?kind=research'], ['documents', '公告', '#/intel/search?kind=announcements']];
const navigation = (section, tabs, label) => `<nav class="workbench-tabs" aria-label="${label}">${tabs.map(([id, title, href]) => `<a href="${href}" class="${section === id ? 'active' : ''}" ${section === id ? 'aria-current="page"' : ''}>${title}</a>`).join('')}</nav>`;

function latestQuery(queries, section) {
  return [...(queries || [])].filter(item => item.section === section).sort((a, b) => (b.created_at || 0) - (a.created_at || 0))[0] || null;
}

function queryForm(section, capability, catalog, draft = {}) {
  if (!capability) return '';
  const parameters = draft?.parameters || {};
  const callable = capability.callable_source_count > 0;
  const sourceIds = new Set((catalog.bindings || []).filter(binding => binding.capability_id === capability.id).map(binding => binding.source_id));
  const bindings = (catalog.sources || []).filter(source => sourceIds.has(source.id) && source.readiness?.callable);
  const requestedSource = draft?.source || 'auto';
  const selectedSource = requestedSource === 'auto' || bindings.some(source => source.id === requestedSource) ? requestedSource : 'auto';
  const sourceOptions = [`<option value="auto" ${selectedSource === 'auto' ? 'selected' : ''}>自动选择</option>`, ...bindings.map(source => `<option value="${e(source.id)}" ${selectedSource === source.id ? 'selected' : ''}>${e(source.name)}</option>`)].join('');
  const common = `<label>数据来源<select name="source">${sourceOptions}</select></label>`;
  const dates = `<label>开始日期<input type="date" name="start_date" value="${e(parameters.start_date || '')}"></label><label>结束日期<input type="date" name="end_date" value="${e(parameters.end_date || '')}"></label>`;
  let fields = '';
  if (section === 'funds') {
    const datasets = [['nav', '历史净值'], ['profile', '基本资料'], ['distributions', '分红'], ['holdings', '披露持仓']];
    const dataset = datasets.some(([id]) => id === parameters.dataset) ? parameters.dataset : 'nav';
    fields = `<label>基金代码<input name="code" pattern="[0-9]{6}" value="${e(parameters.code ?? '000001')}" required></label><label>数据集<select name="dataset">${datasets.map(([id, label]) => `<option value="${id}" ${dataset === id ? 'selected' : ''}>${label}</option>`).join('')}</select></label>${dates}`;
  }
  else if (section === 'market') fields = `<label>资讯关键词<input name="query" maxlength="120" value="${e(parameters.query || '')}" placeholder="留空读取最新公开电报"></label><label>条数<input name="limit" type="number" min="1" max="100" value="${e(parameters.limit ?? 20)}"></label>`;
  else if (section === 'industry') fields = `<label>行业、主题或公司<input name="query" maxlength="120" value="${e(parameters.query || '')}" required placeholder="例如 光模块产业链"></label><label>资料条数<input name="limit" type="number" min="1" max="100" value="${e(parameters.limit ?? 20)}"></label>`;
  else fields = `<label>证券或关键词<input name="query" maxlength="120" value="${e(parameters.query || '')}" required></label>`;
  return `<form class="workbench-query-form" data-workbench-query data-capability="${e(capability.id)}"><div class="workbench-form-grid">${common}${fields}</div>${selectedSource !== requestedSource ? '<p class="notice warning">此前选择的来源当前不可调用，已回到自动选择；请核对来源后再提交。</p>' : ''}<div class="button-row"><button class="button primary" type="submit" ${callable ? '' : 'disabled'}>${callable ? '查询并生成快照' : '当前没有可调用来源'}</button><span class="muted small">查询只在提交后联网；页面打开不会取数或产生费用。</span></div></form>`;
}

function queryResult(query) {
  if (!query) return '<div class="empty compact"><h3>尚未查询</h3><p>选择参数后生成会话隔离的数据快照，再交给 FinGPT 或 Claw。</p></div>';
  const dataset = query.dataset;
  return `<section class="desk-result"><div class="section-heading"><h2>最近查询</h2><span class="badge ${query.status === 'completed' ? 'live' : query.status === 'failed' ? 'danger' : ''}">${e(query.status)}</span></div>${dataset ? `<dl class="desk-metrics"><div><dt>来源</dt><dd>${e(dataset.provider || dataset.source || '未知')}</dd></div><div><dt>结果</dt><dd>${e(dataset.status || '未知')}</dd></div><div><dt>行数</dt><dd>${e(dataset.row_count ?? '未知')}</dd></div><div><dt>截止时间</dt><dd>${e(dataset.as_of || dataset.actual_range?.end_date || '来源未提供')}</dd></div></dl>${dataset.missing?.length ? `<p class="notice warning">缺失：${dataset.missing.map(e).join('、')}</p>` : ''}${dataset.limitations?.length ? `<p class="notice warning">限制：${dataset.limitations.map(e).join('、')}</p>` : ''}` : `<p class="muted">${query.status === 'failed' ? `查询失败：${e(query.failure_code || '未知错误')}` : '查询执行中，完成后显示实际数据集。'}</p>`}</section>`;
}

export function readWorkbenchQuery(form) {
  const values = new FormData(form);
  const parameters = {};
  for (const [name, value] of values.entries()) {
    if (name === 'source' || value === '') continue;
    parameters[name] = ['limit', 'year'].includes(name) ? Number(value) : String(value);
  }
  return { capability: form.getAttribute('data-capability'), source: String(values.get('source') || 'auto'), parameters };
}

export function renderWorkbench({ section = 'assets', catalog = {}, queries = [], queryDraft = {}, busy = false, assetState = {}, etfState = {} } = {}) {
  if (!SECTIONS.some(item => item[0] === section)) section = 'assets';
  if (section === 'etf-paper') return renderEtfPaper({ ...etfState, busy });
  if (section === 'assets') return `${navigation(section, assetTabs, '资产观察视图')}${renderAssetWorkspace({ ...assetState, busy })}`;
  const definition = SECTIONS.find(item => item[0] === section);
  const capability = (catalog.capabilities || []).find(item => item.id === definition[3]);
  const query = latestQuery(queries, section);
  const sessionId = query?.session_id || '';
  const datasetIds = query?.dataset?.dataset_id ? [query.dataset.dataset_id] : [];
  const funds = section === 'funds';
  const header = `<header class="page-header workbench-header"><div><div class="eyebrow">${funds ? 'ASSET OBSERVATION' : 'RESEARCH INTELLIGENCE'}</div><h1>${funds ? '资产观察' : '研究情报'}</h1><p class="muted">${funds ? '查询基金基本资料、净值、分红与披露持仓，保存快照后继续研究。' : '按新闻、研报和公告检索研究主题，保存来源与截止时间后继续研究。'}</p></div><button class="button" data-refresh>刷新目录与查询状态</button></header>`;
  const tabs = funds ? navigation(section, assetTabs, '资产观察视图') : `${renderIntelligenceNavigation('search')}${navigation(section, searchTabs, '主题检索类型')}`;
  return `${header}${tabs}<section class="desk-hero"><div><span class="eyebrow">${funds ? '基金数据' : '主题检索'}</span><h2>${e(definition[2])}</h2><p>${capability ? `${e(capability.description || '按需查询并保存真实数据快照')} · ${capability.source_count ?? 0} 个登记来源，${capability.callable_source_count ?? 0} 个当前可调用。` : '能力目录尚未提供此查询，刷新后重试；已有查询快照仍保留。'}</p></div><div class="button-row"><button class="button" data-workbench-handoff="fingpt" data-source-session="${e(sessionId)}" data-dataset-ids="${e(JSON.stringify(datasetIds))}" ${sessionId && datasetIds.length && !busy ? '' : 'disabled'}>交给 FinGPT</button><button class="button primary" data-workbench-handoff="claw" data-source-session="${e(sessionId)}" data-dataset-ids="${e(JSON.stringify(datasetIds))}" ${sessionId && datasetIds.length && !busy ? '' : 'disabled'}>交给 Claw</button></div></section>${queryForm(section, capability, catalog, queryDraft)}${queryResult(query)}`;
}
