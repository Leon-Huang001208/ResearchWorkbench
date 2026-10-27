import { escapeHTML as e } from './markdown.mjs';
import { icon } from './icons.mjs';
import { renderReportWorkflowDetail, renderRunEvidence } from './report-workflows.mjs';

const rows = value => Array.isArray(value) ? value : [];
const projectLabels = { enabled: '已启用', needs_attention: '待补齐', draft: '未发布', disabled: '已停用' };
const labels = { queued: '排队中', preparing_data: '准备数据', blocked_data: '数据阻断', blocked_approval: '等待审批', running: '生产中', validating: '检查中', completed: '执行已结束', historical_acceptance: '历史验收完成', failed: '未完成', cancelled: '已取消', delivery_incomplete: '交付不完整', quality_incomplete: '内容未通过', needs_attention: '待核对受理', pending: '待检查', passed: '已通过', invalid: '无效', incomplete: '未通过', complete: '已生成', finalized: '正式定稿', invalidated: '定稿已失效', not_eligible_historical: '历史验收，不得正式定稿', blocked: '已阻断', unverified: '尚未核验', not_run: '未执行' };
const label = value => labels[value] || value || '未确认';
const stamp = value => {
  if (!value) return '未记录';
  const date = new Date(typeof value === 'number' ? value * 1000 : value);
  return Number.isFinite(date.getTime()) ? new Intl.DateTimeFormat('zh-CN', { timeZone: 'Asia/Shanghai', dateStyle: 'short', timeStyle: 'short', hour12: false }).format(date) : '日期未确认';
};
const chip = text => `<span class="badge">${e(text)}</span>`;
export const reportHref = (id = '', tab = 'production', runId = '') => `#/reports${id ? '/' + encodeURIComponent(id) + '?tab=' + encodeURIComponent(tab) + (runId ? '&run=' + encodeURIComponent(runId) : '') : ''}`;
export const selectReportRun = (detail, runId) => runId ? rows(detail?.runs).find(run => run.id === runId) || null : rows(detail?.runs)[0] || null;
export const reportRunStatus = run => run?.research_submission_state === 'unknown' || run?.failure_code === 'research_submission_unknown'
  ? `受理未知${run?.monitoring_disposition === 'ended_by_user' ? ' · 监控已结束' : ''}`
  : run?.monitoring_disposition === 'ended_by_user' ? '监控已结束，结果未确认' : label(run?.status);

function directory(items, route, busy) {
  const query = String(route.reportQuery || '').toLocaleLowerCase();
  const filtered = rows(items).filter(item => (!query || `${item.name || ''} ${item.description || ''}`.toLocaleLowerCase().includes(query)) && (!route.reportStatus || route.reportStatus === 'all' || item.status === route.reportStatus));
  return `<header class="page-header"><div><span class="eyebrow">REPORTS</span><h1>报告项目</h1><p class="muted">固定模板、每期生产与交付文件，在这里集中管理。</p></div><button class="button" data-refresh-report-workspace ${busy ? 'disabled' : ''}>${icon('refresh')}刷新状态</button></header><form class="report-directory-filters" data-report-directory-filter><label class="search-box">${icon('search')}<input type="search" name="q" maxlength="120" aria-label="搜索报告项目" placeholder="搜索报告项目" value="${e(route.reportQuery || '')}"></label><label><span class="sr-only">项目状态</span><select name="status" aria-label="项目状态">${[['all', '全部状态'], ...Object.entries(projectLabels)].map(([value, text]) => `<option value="${value}" ${route.reportStatus === value ? 'selected' : ''}>${e(text)}</option>`).join('')}</select></label><button class="button" type="submit">筛选</button><span class="muted small" role="status">${filtered.length} 个报告项目</span></form>${filtered.length ? `<div class="report-directory-scroll"><table class="report-directory-table"><thead><tr><th scope="col">报告项目</th><th scope="col">项目状态</th><th scope="col">当前版本</th><th scope="col">最近生产</th><th scope="col">定稿状态</th><th scope="col">操作</th></tr></thead><tbody>${filtered.map(item => `<tr><td><a class="report-project-name" href="${reportHref(item.id)}">${icon('document')}<span><strong>${e(item.name)}</strong><small>${e(rows(item.delivery_formats).map(value => String(value).toUpperCase()).join(' · ') || '未声明交付格式')}</small></span></a></td><td>${chip(projectLabels[item.status] || '状态未确认')}</td><td>${item.current_version ? `v${e(item.current_version)}` : '—'}</td><td>${item.latest_run ? e(reportRunStatus(item.latest_run)) + `<small>${e(stamp(item.latest_run.updated_at))}</small>` : '尚未运行'}</td><td>${e(label(item.latest_run?.finalization_status))}</td><td><a class="text-button" href="${reportHref(item.id)}">进入 ${icon('chevronRight')}</a></td></tr>`).join('')}</tbody></table></div>` : '<p class="notice" role="status">没有匹配的报告项目。请调整筛选；此处只展示真实项目。</p>'}<p class="muted small report-directory-footnote">项目已启用不代表本期已通过质量检查。历史验收稿与正式稿分别保留。</p>`;
}

function actions(detail, run, busy) {
  if (!run || run.monitoring_disposition === 'ended_by_user') return '';
  if (run.research_submission_state === 'unknown' || run.status === 'needs_attention') return `<button class="button" data-retry-report-run="${e(run.id)}" ${busy ? 'disabled' : ''}>核对受理状态</button>`;
  if (['queued', 'preparing_data', 'blocked_approval', 'running', 'validating'].includes(run.status)) return `<button class="button" data-cancel-report-run="${e(run.id)}" ${busy ? 'disabled' : ''}>取消运行</button>`;
  if (['blocked_data', 'delivery_incomplete', 'failed', 'cancelled', 'quality_incomplete'].includes(run.status)) return `<button class="button" data-retry-report-run="${e(run.id)}" ${busy ? 'disabled' : ''}>${run.status === 'quality_incomplete' ? '继续核验' : '手动重试'}</button>`;
  return '';
}

function production(detail, route, busy) {
  const run = selectReportRun(detail, route.reportRunId);
  if (route.reportRunId && !run) return '<p class="notice warning" role="alert">生产记录不存在或不属于此项目。没有改用其他记录。</p>';
  const contract = run?.weekly_data_contract || {};
  const period = contract.period_start && contract.period_end ? `${contract.period_start} — ${contract.period_end}` : '报告期未记录';
  const historical = run?.execution_purpose === 'historical_acceptance';
  const states = [ ['数据就绪', run?.weekly_data_assessment?.status || run?.data_status], ['内容质量', run?.quality_status], ['文件交付', run?.delivery_status], ['正式定稿', run?.finalization_status] ];
  const invalid = ['invalid', 'invalidated'].includes(run?.quality_status) || ['invalidated', 'invalid'].includes(run?.finalization_status) || run?.delivery_status === 'verification_failed';
  const artifacts = rows(run?.artifacts);
  const files = artifacts.map(file => {
    const safe = typeof file.url === 'string' && file.url.startsWith('/api/research/') && !/[\u0000-\u001f]/.test(file.url);
    const preview = typeof file.preview_url === 'string' && file.preview_url.startsWith('/api/research/') && !/[\u0000-\u001f]/.test(file.preview_url);
    const available = safe && file.valid !== false && !invalid;
    return `<li><span>${e(file.name || file.format || '产物')}</span><div class="button-row">${available && preview ? `<a class="button small" target="_blank" rel="noopener" href="${e(file.preview_url)}">预览报告</a>` : ''}${available ? `<a class="button small" href="${e(file.url)}">${icon('download')}下载文件</a>` : '<span class="muted small">暂不可下载</span>'}</div></li>`;
  }).join('');
  return `<div class="report-period"><div><h2>${e(run ? period : '尚无生产记录')}</h2>${chip(historical ? '历史验收稿 · 不得正式定稿' : run?.execution_purpose === 'production' ? '正式生产' : '用途未记录')}</div>${rows(detail.runs).length ? `<label class="report-record-select">查看记录<select data-report-run-select aria-label="选择生产记录">${rows(detail.runs).map(item => `<option value="${e(item.id)}" ${item.id === run?.id ? 'selected' : ''}>v${e(item.version)} · ${e(stamp(item.created_at))} · ${e(reportRunStatus(item))}</option>`).join('')}</select></label>` : ''}</div>${run && (run.version !== detail.current_version || historical) ? `<p class="notice warning">正在查看${historical ? '历史验收' : '历史版本'}记录 v${e(run.version)}；下列检查仅属于这次生产，不代表当前版本已验收。</p>` : ''}<dl class="report-quality-strip" aria-label="所选记录质量与交付状态">${states.map(([name, value], index) => `<div><dt><span>0${index + 1}</span>${name}</dt><dd>${e(label(value))}</dd></div>`).join('')}</dl><div class="report-production-grid"><section><header><h2>本次交付</h2>${run ? chip(run.finalization_status === 'finalized' && !historical ? '正式稿' : historical ? '历史验收稿' : '未正式定稿') : ''}</header>${files ? `<ul class="report-output-files">${files}</ul>` : '<div class="report-output-empty"><p>尚无本次交付文件</p><small class="muted">文件生成后在此查看；旧文件不计作本次通过。</small><div class="button-row"><button class="button small" disabled>预览报告</button><button class="button small" disabled>下载文件</button></div></div>'}${invalid ? '<p class="notice warning">所选记录的完整性检查未通过或已失效，下载已暂停。</p>' : ''}<a class="text-button" href="${reportHref(detail.id, 'history')}">查看全部历史记录 ${icon('arrowRight')}</a></section><section><header><h2>生产信息</h2>${run ? chip(reportRunStatus(run)) : ''}</header><dl class="report-production-facts"><dt>配置版本</dt><dd>${run?.version ? `v${e(run.version)}` : '未记录'}</dd><dt>数据来源</dt><dd>${e(({ wind_excel: 'Wind Excel', wind_client_api: 'Wind Client API' })[run?.weekly_data_source] || '未记录')}</dd><dt>市场截止</dt><dd>${e(run?.weekly_cutoff || contract.cutoff || '未记录')}</dd><dt>实际冻结</dt><dd>${e(run?.weekly_data_assessment?.frozen_at || '未确认')}</dd><dt>最近更新</dt><dd>${e(stamp(run?.updated_at))}</dd></dl><div class="button-row">${run?.session_id ? `<a class="text-button" href="#/claw?session=${encodeURIComponent(run.session_id)}">查看 Claw 执行过程 ${icon('arrowRight')}</a>` : '<span class="muted small">尚未创建执行会话</span>'}${actions(detail, run, busy)}</div></section></div>${rows(run?.missing).length ? `<section class="notice warning" role="status"><h3>当前缺口</h3><ul>${run.missing.map(gap => `<li>${e(gap)}</li>`).join('')}</ul></section>` : ''}${run ? `<details class="report-original-evidence"><summary>原始检查与失败信息</summary><p class="muted small">${e(run.failure_code || '没有已记录的失败代码')}</p>${renderRunEvidence(run)}</details>` : ''}`;
}

export function renderReportWorkspace({ items = [], detail = null, route = {}, allowed = false, loading = false, error = '', busy = false } = {}) {
  if (!allowed) return '<section class="report-workspace"><h1>报告生产</h1><p class="notice warning" role="alert">当前账户没有报告生产管理权限。</p></section>';
  if (route.reportInvalid) return '<section class="report-workspace"><h1>报告地址无效</h1><a href="#/reports">返回报告项目</a></section>';
  const errorHTML = error ? `<p class="notice error" role="alert">${e(error)} <button class="text-button" data-refresh-report-workspace>重试读取</button></p>` : '';
  if (!route.reportProjectId) return `<section class="report-workspace" aria-label="报告项目目录">${errorHTML}${loading ? '<p role="status">正在读取报告项目…</p>' : ''}${directory(items, route, busy || loading)}</section>`;
  if (!detail || detail.id !== route.reportProjectId) return `<section class="report-workspace">${errorHTML}<p role="status">${loading ? '正在读取报告项目…' : '报告项目不存在或不可访问。'}</p><a href="#/reports">返回报告项目</a></section>`;
  const tab = ['production', 'configuration', 'history'].includes(route.reportTab) ? route.reportTab : 'production';
  const ready = detail.status === 'enabled' && Number.isInteger(detail.current_version);
  const excel = detail.id === 'huaan-etf-weekly' && detail.weekly_production?.enabled && detail.weekly_production?.data_source === 'wind_excel';
  const runAction = excel ? `data-run-historical-report-workflow="${e(detail.id)}"` : `data-run-report-workflow="${e(detail.id)}"`;
  const body = tab === 'production' ? production(detail, route, busy) : renderReportWorkflowDetail(detail, { busy, section: tab });
  return `<section class="report-workspace" aria-label="报告项目详情"><a class="text-button report-back" href="#/reports">${icon('chevronLeft')}报告项目</a>${errorHTML}<header class="page-header"><div><span class="eyebrow">REPORT PROJECT</span><h1>${e(detail.name)}</h1><p class="muted">固定模板与底稿，每期独立生产、核验和交付。 ${chip(detail.current_version ? `v${detail.current_version}` : '未发布')}</p></div><div class="button-row"><button class="button" data-refresh-report-workspace ${busy || loading ? 'disabled' : ''}>${icon('refresh')}刷新状态</button><button class="button primary" ${runAction} ${busy || loading || !ready ? 'disabled' : ''}>${excel ? '生成历史验收稿' : '生产新一期'}</button></div></header><nav class="report-workspace-tabs" aria-label="报告项目栏目">${[['production', '生产与交付'], ['configuration', '模板与配置'], ['history', '历史记录']].map(([key, title]) => `<a href="${reportHref(detail.id, key, route.reportRunId)}" ${key === tab ? 'aria-current="page"' : ''}>${title}</a>`).join('')}</nav>${loading ? '<p class="small muted" role="status">正在刷新状态…</p>' : ''}${body}</section>`;
}
