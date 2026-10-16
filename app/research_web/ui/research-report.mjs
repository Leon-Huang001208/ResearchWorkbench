import { escapeHTML as e, safeURL } from './markdown.mjs';
import { renderResearchPlan } from './views.mjs';

const issueText = issue => typeof issue === 'string' ? issue : issue?.message || issue?.text || issue?.code || '未说明的检查项';
const requirementText = requirement => typeof requirement === 'string' ? requirement : requirement?.text || requirement?.requirement || requirement?.description || requirement?.id || '未说明的用户要求';

export function renderResearchQuality(detail = {}) {
  const quality = detail.research_quality;
  if (!quality) return '';
  const labels = { passed: '质量检查已通过', incomplete: '质量未通过，存在研究缺口', invalid: '完整性检查未通过' };
  const requirements = Array.isArray(quality.requirements) ? quality.requirements : [];
  const issues = Array.isArray(quality.issues) ? quality.issues : [];
  return `<section class="research-quality" data-research-quality="${e(quality.status || 'unknown')}" aria-label="研究质量检查"><p class="notice ${quality.status === 'passed' ? 'success' : 'warning'}" role="status">${e(labels[quality.status] || '质量状态尚未确认')}</p>${quality.verification_scope === 'observed_quotes_and_deterministic_numeric_claims' ? '<p class="small muted">核验范围：实际来源摘录及可复算数字；未核实的改写保留缺口。</p>' : ''}${quality.as_of ? `<p class="small muted">研究截止时点：${e(quality.as_of)}</p>` : ''}${Number.isInteger(quality.repair_count) ? `<p class="small muted">补查许可：${e(quality.repair_count)} 次；活动记录才表示实际执行。</p>` : ''}${requirements.length ? `<details class="research-requirements"><summary>本轮用户要求 · ${requirements.length} 项</summary><ul>${requirements.map(item => `<li>${e(requirementText(item))}</li>`).join('')}</ul></details>` : ''}${issues.length ? `<ul class="research-quality-issues">${issues.map(item => `<li>${e(issueText(item))}</li>`).join('')}</ul>` : ''}${quality.status === 'incomplete' ? '<p class="small">可查看和下载可用成果；未核验项与缺口保留。补充资料后可在本会话继续研究。</p>' : quality.status === 'invalid' ? '<p class="small">报告完整性尚未确认；修复前暂停报告导出。</p>' : '<p class="small muted">执行状态与文件格式检查分别记录；通过项仅限本轮检查范围。</p>'}</section>`;
}

function renderReportVersions(detail) {
  const versions = Array.isArray(detail.research_report_versions) ? detail.research_report_versions : [];
  if (!versions.length) return '';
  return `<section class="research-report-versions" aria-label="历史报告版本"><h3>历史报告版本</h3><p class="small muted">保留原研究回合的报告与检查结果。</p>${versions.map((version, index) => {
    const previous = { research_report: version.report, research_quality: version.quality, historical: true };
    return `<details><summary>${e(version.report?.title || `报告版本 ${index + 1}`)}${version.task_id ? ` · ${e(version.task_id)}` : ''}</summary>${renderResearchPanel(previous, 'report')}${version.report ? renderResearchPanel(previous, 'notes') : ''}</details>`;
  }).join('')}</section>`;
}

export const researchRecipes = {
  onepage: '请围绕以下对象制作一页纸研究摘要，列出关键事实、估值口径、风险和引用来源：',
  selection: '请围绕以下主题筛选标的，说明筛选条件、数据时点、投资逻辑与反例，缺数据时不要补造：',
  chart: '请为以下研究问题制作图表，使用真实数据，标明单位、日期、来源与缺口，并交付实际图表文件：',
  checklist: '请为以下公司或主题准备调研问题清单，按业务、财务、竞争与风险组织，并说明每个问题的验证目的：',
};

export function renderResearchRecipes({ busy = false } = {}) {
  return `<div class="quick-skills research-recipes" aria-label="研究任务快捷入口">${[['onepage', '一页纸'], ['selection', '主题选股'], ['chart', '画图'], ['checklist', '调研清单']].map(([id, label]) => `<button type="button" class="button" data-research-recipe="${id}" ${busy ? 'disabled' : ''}>${label}</button>`).join('')}</div>`;
}

export function renderResearchPanel(detail = {}, tab = 'plan', stageId = null) {
  if (tab === 'plan') {
    return renderResearchPlan(detail) || '<p class="muted">本回合尚无原生研究计划。</p>';
  }
  if (tab === 'evidence') {
    const sources = detail.research_sources || [];
    return `<section aria-label="研究证据索引"><h3>证据来源</h3><p class="small muted">已取得资料与检索摘要；来源身份不代表全文已读或结论已独立核实。</p>${sources.length ? sources.map(source => `<article class="research-evidence-card"><strong>${e(source.title)}</strong><p class="small">${e(source.id)} · ${e(source.state)}</p>${source.excerpt ? `<p>${e(source.excerpt)}</p>` : ''}${safeURL(source.url) ? `<a href="${e(safeURL(source.url))}" target="_blank" rel="noopener noreferrer">查看来源</a>` : ''}</article>`).join('') : '<p class="muted">暂无本会话证据。</p>'}</section>`;
  }
  const report = detail.research_report;
  if (!report) return `${renderResearchQuality(detail)}<p class="muted">本次研究尚未生成结构化报告与笔记。</p>${tab === 'report' ? renderReportVersions(detail) : ''}`;
  const reportQuality = detail.historical ? detail.research_quality?.status : report.quality;
  const readable = detail.research_quality?.status !== 'invalid' && ['checked', 'passed', 'incomplete'].includes(reportQuality);
  if (tab === 'notes') {
    if (!readable) return `<p class="notice warning">${report.quality === 'stale' ? '笔记属于旧任务' : '报告无效，无法确认笔记归属'}。</p>`;
    return `<section aria-label="研究工作笔记"><h3>工作笔记</h3>${(report.notes || []).filter(note => !stageId || note.stage_id === stageId).map(note => `<article><h4>${e(report.sections?.find(section => section.id === note.stage_id)?.heading || '未关联底稿阶段')}</h4><p>${e(note.text)}</p><p class="small muted">引用：${e((note.citations || []).join(', '))}</p></article>`).join('') || '<p class="muted">暂无底稿笔记。</p>'}</section>`;
  }
  const label = { passed: '质量检查已通过', checked: '来源身份与声明章节已检查', incomplete: '存在研究缺口', stale: '报告属于旧任务', invalid: '报告无效' }[reportQuality] || '报告状态未知';
  return `<section aria-label="研究报告"><h3>${e(report.title || '研究报告')}</h3>${detail.research_quality ? renderResearchQuality(detail) : `<p class="notice ${reportQuality === 'passed' ? 'success' : 'warning'}">${e(label)}</p><p class="small muted">仅核对底稿声明的覆盖范围，不替代事实复核。下载文件见“文件”页。</p>`}${(report.issues || []).length ? `<ul>${report.issues.map(issue => `<li>${e(issueText(issue))}</li>`).join('')}</ul>` : ''}${readable ? (report.sections || []).map(section => `<article><h4>${e(section.heading)}</h4>${section.id && !detail.historical ? `<button type="button" class="text-button" data-report-stage="${e(section.id)}">查看章节笔记</button>` : ""}<p>${e(section.text)}</p><p class="small muted">引用：${e((section.citations || []).join(', '))}</p></article>`).join('') : ''}</section>${renderReportVersions(detail)}`;
}
