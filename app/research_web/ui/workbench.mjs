import { escapeHTML as e } from './markdown.mjs';

export const SECTIONS = [
  ['market', '市场', '市场概览、板块、事件和资讯', 'search_news'],
  ['assets', '资产', '证券检索、行情、财务和公告', 'market_bars'],
  ['funds', '基金', '基本资料、净值、分红和持仓', 'fund_data'],
  ['industry', '产业链', '上下游结构、公司和产业资料', 'search_research'],
  ['documents', '资料', '上传文件、公告、新闻、研报和数据集', 'search_announcements'],
  ['reports', '报告', 'DSH 实际生成的报告、表格和图表', null],
];

const bytes = (value = 0) => value < 1024 ? `${value} B` : value < 1048576 ? `${(value / 1024).toFixed(1)} KB` : `${(value / 1048576).toFixed(1)} MB`;

function latestQuery(queries, section) {
  return [...(queries || [])].filter(item => item.section === section).sort((a, b) => (b.created_at || 0) - (a.created_at || 0))[0] || null;
}

function queryForm(section, capability, catalog) {
  if (!capability) return '';
  const callable = capability.callable_source_count > 0;
  const sourceIds = new Set((catalog.bindings || []).filter(binding => binding.capability_id === capability.id).map(binding => binding.source_id));
  const bindings = (catalog.sources || []).filter(source => sourceIds.has(source.id) && source.readiness?.callable);
  const sourceOptions = ['<option value="auto">自动选择</option>', ...bindings.map(source => `<option value="${e(source.id)}">${e(source.name)}</option>`)].join('');
  const common = `<label>数据来源<select name="source">${sourceOptions}</select></label>`;
  let fields = '';
  if (section === 'funds') fields = `<label>基金代码<input name="code" pattern="[0-9]{6}" value="000001" required></label><label>数据集<select name="dataset"><option value="nav">历史净值</option><option value="profile">基本资料</option><option value="distributions">分红</option><option value="holdings">披露持仓</option></select></label><label>开始日期<input type="date" name="start_date"></label><label>结束日期<input type="date" name="end_date"></label>`;
  else if (section === 'market') fields = `<label>资讯关键词<input name="query" maxlength="120" placeholder="留空读取最新公开电报"></label><label>条数<input name="limit" type="number" min="1" max="100" value="20"></label>`;
  else if (section === 'assets') fields = `<label>证券代码<input name="asset" maxlength="24" placeholder="例如 600519.SH" required></label><label>开始日期<input type="date" name="start_date" required></label><label>结束日期<input type="date" name="end_date" required></label>`;
  else if (section === 'industry') fields = `<label>产业或公司<input name="query" maxlength="120" required placeholder="例如 光模块产业链"></label><label>资料条数<input name="limit" type="number" min="1" max="100" value="20"></label>`;
  else fields = `<label>证券或关键词<input name="query" maxlength="120" required></label>`;
  return `<form class="workbench-query-form" data-workbench-query data-capability="${e(capability.id)}"><div class="workbench-form-grid">${common}${fields}</div><div class="button-row"><button class="button primary" type="submit" ${callable ? '' : 'disabled'}>${callable ? '查询并生成快照' : '当前没有可调用来源'}</button><span class="muted small">查询只在提交后联网；页面打开不会取数或产生费用。</span></div></form>`;
}

function queryResult(query) {
  if (!query) return '<div class="empty compact"><h3>尚未查询</h3><p>选择参数后生成会话隔离的数据快照，再交给 FinGPT 或 Claw。</p></div>';
  const dataset = query.dataset;
  return `<section class="desk-result"><div class="section-heading"><h2>最近查询</h2><span class="badge ${query.status === 'completed' ? 'live' : query.status === 'failed' ? 'danger' : ''}">${e(query.status)}</span></div>${dataset ? `<dl class="desk-metrics"><div><dt>来源</dt><dd>${e(dataset.provider || dataset.source || '未知')}</dd></div><div><dt>结果</dt><dd>${e(dataset.status || '未知')}</dd></div><div><dt>行数</dt><dd>${e(dataset.row_count ?? '未知')}</dd></div><div><dt>截止时间</dt><dd>${e(dataset.as_of || dataset.actual_range?.end_date || '来源未提供')}</dd></div></dl>${dataset.missing?.length ? `<p class="notice warning">缺失：${dataset.missing.map(e).join('、')}</p>` : ''}` : `<p class="muted">${query.status === 'failed' ? `查询失败：${e(query.failure_code || '未知错误')}` : '查询执行中，完成后显示实际数据集。'}</p>`}</section>`;
}

function artifactGrid(artifacts) {
  return `<div class="artifact-grid">${artifacts?.length ? artifacts.map(item => `<article class="artifact-card"><div><span class="eyebrow">${e((item.name.split('.').pop() || 'FILE').toUpperCase())}</span><h3>${e(item.name)}</h3><p class="muted small">${e(item.session_title || '研究会话')} · ${bytes(item.size)}</p></div><div class="button-row"><a class="button small" href="${e(item.preview_url)}" target="_blank" rel="noopener">预览</a><a class="button small" href="${e(item.url)}">下载</a></div></article>`).join('') : '<div class="empty compact"><h3>暂无真实产物</h3><p>DSH 在会话 outputs 目录生成的文件会显示在这里。</p></div>'}</div>`;
}

export function readWorkbenchQuery(form) {
  const values = new FormData(form);
  const parameters = {};
  for (const [name, value] of values.entries()) {
    if (name === 'source' || value === '') continue;
    parameters[name] = ['limit', 'year'].includes(name) ? Number(value) : String(value);
  }
  return { capability: form.dataset.capability, source: String(values.get('source') || 'auto'), parameters };
}

export function renderWorkbench({ section = 'market', catalog = {}, queries = [], artifacts = [], busy = false } = {}) {
  const definition = SECTIONS.find(item => item[0] === section) || SECTIONS[0];
  const capability = (catalog.capabilities || []).find(item => item.id === definition[3]);
  const query = latestQuery(queries, section);
  const sessionId = query?.session_id || '';
  const datasetIds = query?.dataset?.dataset_id ? [query.dataset.dataset_id] : [];
  return `<header class="page-header workbench-header"><div><div class="eyebrow">RESEARCH DESK</div><h1>研究台</h1><p class="muted">先固化真实数据与页面参数，再交给 DSH 研究；不同 Agent 共用同一份快照。</p></div><button class="button" data-refresh>刷新目录与产物</button></header><nav class="workbench-tabs" aria-label="研究台页面">${SECTIONS.map(([id, label]) => `<a href="#/workbench?section=${id}" class="${section === id ? 'active' : ''}" ${section === id ? 'aria-current="page"' : ''}>${label}</a>`).join('')}</nav><section class="desk-hero"><div><span class="eyebrow">${e(definition[1])}</span><h2>${e(definition[2])}</h2><p>${capability ? `${e(capability.description)} · ${capability.source_count} 个登记来源，${capability.callable_source_count} 个当前可调用。` : '此页只读取当前会话实际产物，空目录保持为空。'}</p></div><div class="button-row"><button class="button" data-workbench-handoff="fingpt" data-source-session="${e(sessionId)}" data-dataset-ids="${e(JSON.stringify(datasetIds))}" ${sessionId && !busy ? '' : 'disabled'}>交给 FinGPT</button><button class="button primary" data-workbench-handoff="claw" data-source-session="${e(sessionId)}" data-dataset-ids="${e(JSON.stringify(datasetIds))}" ${sessionId && !busy ? '' : 'disabled'}>交给 Claw</button></div></section>${section === 'reports' ? artifactGrid(artifacts) : `${queryForm(section, capability, catalog)}${queryResult(query)}${section === 'documents' ? artifactGrid(artifacts) : ''}`}`;
}
