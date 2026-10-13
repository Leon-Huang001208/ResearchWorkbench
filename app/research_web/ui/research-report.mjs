import { escapeHTML as e, safeURL } from './markdown.mjs';
import { renderResearchPlan } from './views.mjs';

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
  if (!report) return '<p class="muted">本次研究尚未生成结构化报告与笔记。</p>';
  if (tab === 'notes') {
    if (!['checked', 'incomplete'].includes(report.quality)) return `<p class="notice warning">${report.quality === 'stale' ? '笔记属于旧任务' : '报告无效，无法确认笔记归属'}。</p>`;
    return `<section aria-label="研究工作笔记"><h3>工作笔记</h3>${(report.notes || []).filter(note => !stageId || note.stage_id === stageId).map(note => `<article><h4>${e(report.sections?.find(section => section.id === note.stage_id)?.heading || '未关联底稿阶段')}</h4><p>${e(note.text)}</p><p class="small muted">引用：${e((note.citations || []).join(', '))}</p></article>`).join('') || '<p class="muted">暂无底稿笔记。</p>'}</section>`;
  }
  const label = { checked: '来源身份与声明章节已检查', incomplete: '存在研究缺口', stale: '报告属于旧任务', invalid: '报告无效' }[report.quality] || '报告状态未知';
  return `<section aria-label="研究报告"><h3>${e(report.title || '研究报告')}</h3><p class="notice ${report.quality === 'checked' ? '' : 'warning'}">${e(label)}</p><p class="small muted">仅核对底稿声明的覆盖范围，不替代事实复核。下载文件见“文件”页。</p>${(report.issues || []).length ? `<ul>${report.issues.map(issue => `<li>${e(issue)}</li>`).join('')}</ul>` : ''}${['checked', 'incomplete'].includes(report.quality) ? (report.sections || []).map(section => `<article><h4>${e(section.heading)}</h4>${section.id ? `<button type="button" class="text-button" data-report-stage="${e(section.id)}">查看章节笔记</button>` : ""}<p>${e(section.text)}</p><p class="small muted">引用：${e((section.citations || []).join(', '))}</p></article>`).join('') : ''}</section>`;
}
