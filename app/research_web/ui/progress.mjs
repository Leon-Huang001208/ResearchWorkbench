// Bundled product information only: no tasks, credentials, or live execution state.
import { escapeHTML as e } from './markdown.mjs';

export const PROGRESS_STATUSES = { planned: '计划中', developing: '开发中', validating: '待验收', delivered: '已交付', paused: '已暂停', cancelled: '已取消' };
export const PROGRESS_KINDS = { new: '新增', improvement: '优化', fix: '修复', removal: '下线', announcement: '公告' };
const REPO = 'https://github.com/Leon-Huang001208/ResearchWorkbench';
const ID = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
const own = (object, key) => Object.hasOwn(object, key);
const invalid = code => { throw new Error(`progress_invalid_${code}`); };
function fields(value, allowed) {
  if (!value || typeof value !== 'object' || Array.isArray(value) || Object.keys(value).some(key => !allowed.includes(key))) invalid('fields');
}
function text(value, name, max = 1200) {
  if (typeof value !== 'string' || !value.trim() || value.length > max || /[\x00-\x08\x0b\x0c\x0e-\x1f]/.test(value)) invalid(name);
  if (/\/(?:Users|home|private|tmp|var|opt|Volumes|etc|root)\/|[A-Za-z]:\\|\\\\[a-zA-Z0-9]|(?:sk-|ghp_)[a-zA-Z0-9]{12,}|-----BEGIN .*PRIVATE KEY-----/.test(value)) invalid('private_text');
  return value;
}
function date(value, ceiling) {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value) || Number.isNaN(Date.parse(`${value}T00:00:00Z`)) || new Date(`${value}T00:00:00Z`).toISOString().slice(0, 10) !== value || (ceiling && value > ceiling)) invalid('date');
}
function link(value) {
  if (typeof value !== 'string' || value.length > 500 || !value.startsWith(`${REPO}/`) || !new RegExp(`^${REPO}/(?:pull/[1-9][0-9]*|actions/runs/[1-9][0-9]*(?:/job/[1-9][0-9]*)?|blob/(?:[a-f0-9]{40}|master)/(?:docs|\\.ai/reports)/[a-zA-Z0-9_./-]+\\.md)(?:#[a-zA-Z0-9_%\\u3400-\\u9fff-]+)?$`).test(value) || value.includes('..')) invalid('link');
  return value;
}
function accepted(feature) {
  return feature.evidence.some(item => item.kind === 'merge' && /\/pull\//.test(item.url)) && ['constraints', 'web', 'macos'].every(gate => feature.evidence.some(item => item.kind === 'validation' && item.gate === gate && item.result === 'passed' && /\/actions\/runs\//.test(item.url)));
}

export function validateProgress(input) {
  fields(input, ['schemaVersion', 'asOf', 'features', 'releases']);
  if (!input || input.schemaVersion !== 1 || !Array.isArray(input.features) || !Array.isArray(input.releases) || input.features.length > 200 || input.releases.length > 1000) invalid('schema');
  date(input.asOf);
  const ids = new Set(); const features = new Map();
  for (const feature of input.features) {
    fields(feature, ['id', 'module', 'title', 'summary', 'scope', 'next', 'owner', 'source', 'updated', 'status', 'platforms', 'included', 'activation', 'limitations', 'evidence', 'blocked']);
    if (typeof feature.id !== 'string' || !ID.test(feature.id) || feature.id.length > 80) invalid('id');
    if (ids.has(feature.id)) invalid('duplicate_id'); ids.add(feature.id);
    for (const field of ['module', 'title', 'summary', 'scope', 'next', 'owner', 'limitations']) text(feature[field], field);
    date(feature.updated, input.asOf); link(feature.source);
    if (!own(PROGRESS_STATUSES, feature.status) || !Array.isArray(feature.platforms) || !feature.platforms.length || feature.platforms.some(p => !['macos', 'windows', 'linux', 'docker-desktop'].includes(p)) || typeof feature.included !== 'boolean' || !['unknown', 'configuration_required', 'disabled'].includes(feature.activation)) invalid('status');
    if (feature.blocked !== undefined) { fields(feature.blocked, ['reason', 'next']); text(feature.blocked.reason, 'blocked_reason'); text(feature.blocked.next, 'blocked_next'); }
    if (!Array.isArray(feature.evidence) || feature.evidence.length > 20) invalid('evidence');
    for (const item of feature.evidence) {
      fields(item, ['kind', 'label', 'url', 'gate', 'result']);
      if (!item || !['merge', 'validation', 'reference'].includes(item.kind)) invalid('evidence');
      text(item.label, 'evidence_label', 160); link(item.url);
      if (item.kind === 'validation' && (!['constraints', 'web', 'macos'].includes(item.gate) || item.result !== 'passed')) invalid('evidence');
    }
    if (feature.status === 'delivered' && !accepted(feature)) invalid('evidence');
    features.set(feature.id, feature);
  }
  for (const release of input.releases) {
    fields(release, ['id', 'featureId', 'date', 'kind', 'title', 'summary']);
    if (typeof release.id !== 'string' || !ID.test(release.id) || release.id.length > 80) invalid('id');
    if (ids.has(release.id)) invalid('duplicate_id'); ids.add(release.id);
    if (typeof release.featureId !== 'string' || !features.has(release.featureId)) invalid('association');
    date(release.date, input.asOf);
    if (!own(PROGRESS_KINDS, release.kind)) invalid('kind');
    text(release.title, 'title'); text(release.summary, 'summary');
    // A release is a confirmed delivery event even if the feature later pauses.
    if (!accepted(features.get(release.featureId))) invalid('evidence');
  }
  return input;
}

export function progressHref(route = {}, patch = {}) {
  const values = { tab: route.progressTab || 'overview', status: route.progressStatus || 'all', kind: route.progressKind || 'all', module: route.progressModule || '', item: route.progressItem || '', month: route.progressMonth || '', ...patch };
  const params = new URLSearchParams();
  for (const key of ['status', 'kind', 'module', 'item', 'month']) if (values[key] && values[key] !== 'all' && (key !== 'status' || values.tab === 'overview') && (key !== 'kind' || values.tab === 'changelog')) params.set(key, values[key]);
  return `#/progress${values.tab === 'changelog' ? '/changelog' : ''}${params.size ? `?${params}` : ''}`;
}
const dateLabel = value => `${Number(value.slice(5, 7))} 月 ${Number(value.slice(8))} 日`;
const option = (value, label, selected) => `<option value="${e(value)}" ${value === selected ? 'selected' : ''}>${e(label)}</option>`;
function details(feature, id, route) {
  const activation = { unknown: '未确认', configuration_required: '需配置并另行启用', disabled: '默认关闭' }[feature.activation];
  const platforms = feature.platforms.map(p => ({ macos: 'macOS', windows: 'Windows', linux: 'Linux', 'docker-desktop': 'Mac Docker Desktop' })[p]).join('、');
  return `<details data-disclosure-key="progress:${e(id)}" ${route.progressItem === id ? 'open' : ''}><summary>查看详情与依据</summary><div class="progress-detail"><dl><dt>功能范围</dt><dd>${e(feature.scope)}</dd><dt>下一步</dt><dd>${e(feature.next)}</dd><dt>负责人</dt><dd>${e(feature.owner)}</dd><dt>本版本包含实现</dt><dd>${feature.included ? '是' : '否'}</dd><dt>适用平台</dt><dd>${e(platforms)}</dd><dt>启用情况</dt><dd>${e(activation)}</dd><dt>验证与限制</dt><dd>${e(feature.limitations)}</dd></dl>${feature.blocked ? `<p class="progress-blocked">阻塞原因：${e(feature.blocked.reason)}<br>下一步：${e(feature.blocked.next)}</p>` : ''}<ul class="progress-evidence"><li><a href="${e(feature.source)}" target="_blank" rel="noopener noreferrer">功能来源与目标 ↗</a></li>${feature.evidence.map(item => `<li><a href="${e(item.url)}" target="_blank" rel="noopener noreferrer">${e(item.label)} ↗</a></li>`).join('')}</ul></div></details>`;
}
export function renderProgress(state = {}, route = {}) {
  const tab = route.progressTab || 'overview'; const changes = tab === 'changelog';
  const header = `<header class="progress-heading"><div><h1>研发进展</h1><p class="muted">看见每一步改进，了解接下来会发生什么。</p></div>${state.data ? `<p class="progress-snapshot">进展截至 <time datetime="${e(state.data.asOf)}">${e(state.data.asOf)}</time><small>随本版本提供的进展快照</small></p>` : ''}</header><nav class="progress-tabs" aria-label="研发进展视图">${[['overview', '进展概览'], ['changelog', '更新日志']].map(([key, label]) => `<a href="${e(progressHref(route, { tab: key, item: '', month: '' }))}" ${tab === key ? 'aria-current="page"' : ''}>${label}</a>`).join('')}</nav>`;
  let body;
  if (route.progressInvalid) body = '<p role="alert">进展地址无效，请从进展概览重新打开。</p>';
  else if (state.loading) body = '<p role="status" class="progress-empty">正在读取版本内的进展记录…</p>';
  else if (state.error) body = `<div class="progress-empty" role="alert"><p>${state.error === 'invalid_content' ? '进展内容未通过完整性检查，暂不能展示。' : '暂时无法读取进展记录，请重试。'}</p><button type="button" class="button" data-progress-retry>重新读取</button></div>`;
  else if (!state.data) body = '<p role="status" class="progress-empty">正在读取版本内的进展记录…</p>';
  else {
    const data = state.data; const features = new Map(data.features.map(f => [f.id, f]));
    const module = route.progressModule || ''; const filter = changes ? route.progressKind || 'all' : route.progressStatus || 'all';
    const entries = (changes ? data.releases.map(r => ({ ...r, feature: features.get(r.featureId) })) : data.features.map(f => ({ ...f, date: f.updated, feature: f }))).filter(row => (!module || row.feature.module === module) && (filter === 'all' || (changes ? row.kind : row.status) === filter)).sort((a, b) => b.date.localeCompare(a.date) || a.id.localeCompare(b.id));
    const dates = [...new Set(entries.map(row => row.date))]; const months = [...new Set(dates.map(d => d.slice(0, 7)))];
    const filterName = changes ? 'kind' : 'status'; const filterOptions = changes ? PROGRESS_KINDS : PROGRESS_STATUSES;
    const controls = `<form class="progress-filters" data-progress-filters><label>${changes ? '类型' : '状态'}<select name="${filterName}" aria-label="筛选${changes ? '类型' : '状态'}">${option('all', changes ? '全部类型' : '全部状态', filter)}${Object.entries(filterOptions).map(([v, l]) => option(v, l, filter)).join('')}</select></label><label>模块<select name="module">${option('', '全部模块', module)}${[...new Set(data.features.map(f => f.module))].sort().map(m => option(m, m, module)).join('')}${module && !data.features.some(f => f.module === module) ? option(module, module, module) : ''}</select></label></form>`;
    const missing = route.progressItem && !entries.some(row => row.id === route.progressItem) ? '<p role="status" class="notice">该条目不存在或不符合当前筛选。</p>' : '';
    const days = dates.map(day => `<section class="progress-day" id="progress-day-${day}"><h2><time datetime="${day}">${dateLabel(day)}</time><span>${day.slice(0, 4)}</span></h2>${entries.filter(row => row.date === day).map(row => `<article class="progress-entry" id="progress-item-${e(row.id)}"><div class="progress-meta progress-${changes ? row.kind : row.status}"><span class="progress-status"><i aria-hidden="true"></i>${e(changes ? PROGRESS_KINDS[row.kind] : PROGRESS_STATUSES[row.status])}</span></div><div class="progress-copy"><h3><a data-progress-target href="${e(progressHref(route, { item: row.id, month: '' }))}">${e(row.title)}</a></h3><p>${e(row.summary)}</p><div class="progress-tags"><span>${e(row.feature.module)}</span>${row.feature.blocked ? '<span class="progress-blocked">存在阻塞</span>' : ''}</div>${details(row.feature, row.id, route)}</div></article>`).join('')}</section>`).join('');
    const monthsOpen = !globalThis.matchMedia?.('(max-width: 780px)').matches;
    const aside = `<aside class="progress-months"><details ${monthsOpen ? 'open' : ''}><summary>按月份</summary><nav aria-label="按月份">${months.map(m => `<a data-progress-target href="${e(progressHref(route, { month: m, item: '' }))}" ${route.progressMonth === m ? 'aria-current="date"' : ''}>${m.slice(0, 4)} 年 ${Number(m.slice(5))} 月<span>${entries.filter(row => row.date.startsWith(m)).length} 条</span></a>`).join('')}</nav></details><p>先看功能变化，<br>再按需展开细节。</p></aside>`;
    body = `<div class="progress-body"><div>${controls}${missing}${days || '<p class="progress-empty" role="status">没有符合筛选条件的进展记录。</p>'}</div>${aside}</div>`;
  }
  return `<section class="progress-page" aria-label="研发进展">${header}${body}<footer class="progress-footnote"><p>“已交付”表示已合并并通过必需验收。本版本包含实现、适用平台与启用情况分别说明；其他环境的可用情况未确认。</p><p>这是一份版本内快照，不实时追踪开发状态。<a href="${REPO}/blob/master/docs/CHANGELOG.md" target="_blank" rel="noopener noreferrer">历史文档 ↗</a></p></footer></section>`;
}

export function createProgressController({ fetcher = globalThis.fetch?.bind(globalThis), notify = () => {}, logger = () => {}, timeoutMs = 15000 } = {}) {
  const state = { data: null, loading: false, error: '' }; let inFlight = null;
  return { state, async load({ retry = false } = {}) {
    if (inFlight) return inFlight;
    if (state.data && !retry) return;
    state.loading = true; state.error = ''; notify();
    inFlight = (async () => {
      const abort = new AbortController(); let timer;
      try {
        const timeout = new Promise((_, reject) => { timer = setTimeout(() => { abort.abort(); reject(new Error('timeout')); }, timeoutMs); });
        const read = async () => {
          const response = await fetcher('/static/progress-data.json', { signal: abort.signal, cache: 'no-cache', credentials: 'same-origin' });
          if (!response.ok) throw new Error('http');
          const data = await response.json();
          return validateProgress(data);
        };
        state.data = await Promise.race([read(), timeout]); logger('progress_loaded', { status: 'ready' });
      } catch (error) { state.data = null; state.error = error instanceof SyntaxError || String(error?.message).startsWith('progress_invalid_') ? 'invalid_content' : 'load_failed'; logger('progress_load_failed', { status: state.error }); }
      finally { clearTimeout(timer); state.loading = false; inFlight = null; notify(); }
    })();
    return inFlight;
  } };
}

export function focusProgressTarget(root, route) {
  const monthIndex = root.querySelector('.progress-months details');
  if (monthIndex) monthIndex.open = !(globalThis.matchMedia?.('(max-width: 780px)').matches);
  const target = route.progressItem ? root.querySelector(`#progress-item-${route.progressItem}`) : route.progressMonth ? root.querySelector(`[id^="progress-day-${route.progressMonth}-"]`) : null;
  const main = root.querySelector('#main');
  if (target && main) { const detail = route.progressItem && target.querySelector('details'); if (detail) detail.open = true; main.scrollTop += target.getBoundingClientRect().top - main.getBoundingClientRect().top - 16; target.tabIndex = -1; target.focus({ preventScroll: true }); }
  else if (main) main.scrollTop = 0;
}

export function createProgressWorkspace({ root, route, notify, logger }) {
  const controller = createProgressController({ logger, notify: () => { if (route().page === 'progress') notify(); } });
  root.addEventListener('change', event => {
    const form = event.target.closest?.('[data-progress-filters]');
    if (route().page !== 'progress' || !form) return;
    window.location.hash = progressHref(route(), { ...Object.fromEntries(new FormData(form)), item: '', month: '' });
  });
  root.addEventListener('click', event => {
    const link = event.target.closest?.('[data-progress-target]');
    if (route().page === 'progress' && link?.hash === window.location.hash) { event.preventDefault(); focusProgressTarget(root, route()); }
    if (route().page === 'progress' && event.target.closest?.('[data-progress-retry]')) void controller.load({ retry: true });
  });
  globalThis.addEventListener?.('resize', () => {
    const index = root.querySelector('.progress-months details');
    if (route().page === 'progress' && index) index.open = !globalThis.matchMedia('(max-width: 780px)').matches;
  });
  return {
    render: () => renderProgress(controller.state, route()),
    async open() {
      const requested = route(); await controller.load();
      if (route() === requested) { document.title = '研发进展 · Research Workbench'; focusProgressTarget(root, requested); }
    },
  };
}

export function changelogSection(data) {
  validateProgress(data);
  const featureMap = new Map(data.features.map(f => [f.id, f]));
  const escapeMarkdown = value => value.replace(/[\\`*_{}\[\]<>#!|]/g, '\\$&').replace(/\r?\n/g, ' ');
  return ['<!-- product-progress:generated:start -->', '## 产品交付快照（自动生成）', '', `进展截至 ${data.asOf}。以下记录来自版本内结构化内容；源码交付不等于当前环境已启用。`, '', ...[...data.releases].sort((a, b) => b.date.localeCompare(a.date) || a.id.localeCompare(b.id)).map(r => `- ${r.date} **${PROGRESS_KINDS[r.kind]} · ${escapeMarkdown(r.title)}**：${escapeMarkdown(r.summary)}（[交付依据](${featureMap.get(r.featureId).source})）`), '', '<!-- product-progress:generated:end -->'].join('\n');
}
