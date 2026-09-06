import { escapeHTML as e } from './markdown.mjs';
import { isRunning } from './core.mjs';
import { icon } from './icons.mjs';
import { renderFormatPicker, modelOptions } from './views.mjs';

const quickSkillIDs = ['document-reading', 'company-research', 'industry-research', 'fund-evaluation'];

export function researchQuickSkills(skills = []) {
  const byID = new Map((Array.isArray(skills) ? skills : []).map((skill) => [skill?.id, skill]));
  return quickSkillIDs.map((id) => byID.get(id)).filter(Boolean);
}

export function skillMatches(query, skills = []) {
  const normalized = String(query || '').trim().toLocaleLowerCase();
  const enabled = (Array.isArray(skills) ? skills : []).filter((skill) => skill?.enabled !== false);
  if (!normalized) return enabled;
  return enabled.filter((skill) => `${skill?.name || ''} ${skill?.description || ''}`.toLocaleLowerCase().includes(normalized));
}

export function slashKey(key, index, matches) {
  if (key === 'Escape') return { handled: true, close: true };
  if (key === 'Enter') return { handled: true, ...(matches[index] ? { select: matches[index].id } : {}) };
  if (key === 'ArrowDown' || key === 'ArrowUp') return { handled: true, index: matches.length ? (index + (key === 'ArrowDown' ? 1 : -1) + matches.length) % matches.length : 0 };
  return { handled: false };
}

export function renderQuickSkills(skills = [], { page = 'fingpt', category = '' } = {}) {
  const claw = page === 'claw';
  const items = claw ? (Array.isArray(skills) ? skills : []).filter(item => item?.kind === 'workflow' && item.enabled === true) : researchQuickSkills(skills);
  const categories = [...new Set(items.map(item => item.category).filter(Boolean))];
  const selectedCategory = categories.includes(category) ? category : '';
  const visible = items.filter(item => !selectedCategory || item.category === selectedCategory);
  const filters = categories.length ? `<div class="capability-filters"><label for="quick-category">分类<select id="quick-category" data-quick-category><option value="">全部分类</option>${categories.map(value => `<option value="${e(value)}" ${selectedCategory === value ? 'selected' : ''}>${e(value)}</option>`).join('')}</select></label></div>` : '';
  const cards = visible.map((skill) => {
    const report = skill.metadata?.report_workflow || skill.report_workflow;
    const resourceKinds = new Set((report?.resources || []).map(resource => resource.kind));
    const resourceLabel = [resourceKinds.has('template') ? 'Word 模板' : '', resourceKinds.has('workbook') ? 'Excel 底稿' : ''].filter(Boolean).join(' · ');
    const version = report?.package_version || skill.version;
    const actionLabel = report ? `锁定 v${version} 放入草稿` : `将${skill.name}放入草稿`;
    const actionTitle = report ? `锁定 v${version} 放入草稿，不会执行` : '放入草稿，不会发送';
    return `<article class="quick-skill-card ${report ? 'quick-report-workflow' : ''}"><button type="button" class="quick-skill-title" data-skill-detail="${e(skill.id)}">${icon(({ 'document-reading': 'document', 'company-research': 'company', 'industry-research': 'industry', 'fund-evaluation': 'chart' })[skill.id] || 'layers')}<h3>${e(skill.name)}</h3></button>${report ? `<span class="badge">报告 Workflow</span><p class="quick-input">${e(resourceLabel || '报告资源待检查')} · ${e(report.schedule?.enabled ? report.schedule.label || '日程已启用' : '手动运行')}</p>` : `<p class="quick-input">${e(claw ? '步骤式研究模板' : (skill.metadata?.inputs || []).map(input => input.label).join('、') || '研究问题与资料')}</p>`}<span class="sr-only">${e(skill.description || '')} 场景：${e((skill.metadata?.scenarios || []).join('、') || '未提供')} 输入：${e((skill.metadata?.inputs || []).map(input => `${input.label}（${input.type}${input.required ? ' · 必填' : ''}）`).join('、') || '未提供')} 输出：${e((skill.metadata?.default_formats || []).join('、') || '无需文件')}</span><button type="button" class="quick-use icon-button" data-skill-shortcut="${e(skill.id)}" aria-label="${e(actionLabel)}" title="${e(actionTitle)}" ${skill.enabled === false ? 'disabled' : ''}>${icon('arrow')}</button></article>`;
  }).join('');
  return `<section class="quick-skills" aria-label="${claw ? '研究步骤模板快捷入口' : '研究 Skill 快捷入口'}"><details class="quick-directory"><summary>浏览研究入口与分类</summary><div class="section-heading"><h2>${claw ? '研究步骤模板' : '从真实研究 Skill 开始'}</h2><a href="#/skills" class="text-button">查看能力中心</a></div>${claw ? '<p class="small muted">步骤是研究模板，不代表已经执行；也可通过上方能力选择使用真实 Skill。</p>' : ''}${filters}</details>${cards ? `<div class="quick-skill-grid">${cards}</div>` : `<p class="muted small quick-skill-empty">${claw ? '尚无已启用的研究步骤模板' : '尚无可用研究 Skill'}；请在能力中心检查目录后刷新。</p>`}</section>`;
}

export function renderComposer({ models = [], model = '', page, draft, attachments = [], expectedFormats = null, skills = [], skillId = '', capability = null, toolIds = [], tools = [], disabled = false, busy = false, taskPending = false, detail = null, slashOpen = false, slashIndex = 0, runtimeReady = true } = {}) {
  const claw = page === 'claw';
  const enabledSkills = skillMatches('', skills);
  const matches = slashOpen ? skillMatches(String(draft || '').trimStart().replace(/^\//, ''), enabledSkills).slice(0, 6) : [];
  const picked = capability || skills.find(skill => skill.id === skillId);
  const chips = `${capability ? `<span>${e(capability.name)} · v${e(capability.version)}<button type="button" data-clear-capability aria-label="移除所选能力">×</button></span>` : ''}${toolIds.map(id => `<span>工具意图：${e(tools.find(tool => tool.id === id)?.name || id)}<button type="button" data-remove-tool="${e(id)}" aria-label="移除工具意图">×</button></span>`).join('')}`;
  return `<form id="composer" class="composer" data-dropzone data-paste-support><label class="sr-only" for="prompt">${claw ? '任务目标或补充信息' : '研究问题'}</label><textarea id="prompt" name="prompt" rows="3" aria-expanded="${slashOpen}" ${slashOpen ? `aria-controls="slash-options"${matches.length ? ` aria-activedescendant="slash-option-${slashIndex}"` : ''}` : ''} placeholder="${claw ? '描述你的研究目标，以及希望拿到的文件…' : '向 FinGPT 提问，或输入 / 选择能力…'}" ${disabled ? 'disabled' : ''}>${e(draft || '')}</textarea>${slashOpen ? `<div id="slash-options" class="slash-menu" role="listbox" aria-label="匹配的研究能力">${matches.length ? matches.map((skill, index) => `<button id="slash-option-${index}" type="button" role="option" aria-selected="${index === slashIndex}" class="slash-skill" data-skill-shortcut="${e(skill.id)}"><strong>${e(skill.name)}${skill.version ? ` · v${e(skill.version)}` : ''}</strong><span>${e(skill.description || '无描述')}</span></button>`).join('') : '<p class="small muted">没有匹配的已启用能力；Escape 关闭。</p>'}</div>` : ''}${chips ? `<div class="attachment-chips capability-chips">${chips}</div>` : ''}${attachments.length ? `<div class="attachment-chips">${attachments.map((file) => `<span>${e(file.name)}<button type="button" data-remove-attachment="${e(file.id)}" aria-label="移除附件 ${e(file.name)}">×</button></span>`).join('')}</div>` : ''}<div class="composer-tools"><button type="button" class="button attachment-button" data-upload ${disabled ? 'disabled' : ''} aria-label="添加附件" title="PDF、图片、Markdown、CSV、Excel">${icon('plus')}</button><button type="button" class="button attachment-button" data-slash-search ${disabled ? 'disabled' : ''} title="搜索真实能力">${icon('grid')} <span>能力</span></button><details class="capability-picker"><summary aria-label="选择已启用能力">${icon('chevron')}</summary><label class="sr-only" for="skill-select">使用 Skill 或 Workflow</label><select id="skill-select" ${disabled ? 'disabled' : ''}><option value="">按需使用能力</option>${enabledSkills.map((skill) => `<option value="${e(skill.id)}" ${skillId === skill.id ? 'selected' : ''}>${e(skill.name)}</option>`).join('')}</select></details>${renderFormatPicker(expectedFormats, picked)}<span class="spacer"></span><label class="sr-only" for="model-select">运行模型</label><select id="model-select" ${busy ? 'disabled' : ''}>${modelOptions(models, model)}</select>${detail && (isRunning(detail.status) || detail.can_cancel || detail.can_recheck_stop) ? `<button type="button" class="button danger-outline" data-cancel ${busy || !runtimeReady ? 'disabled' : ''}>${detail.can_recheck_stop ? '重新核对停止' : '停止'}</button>` : ''}<button type="submit" class="button primary composer-send" aria-label="${busy ? '正在提交' : '发送研究问题'}" title="${detail ? '发送' : '开始研究'}" ${disabled || taskPending || !runtimeReady ? 'disabled' : ''}>${icon('arrow')}</button></div><input id="file-input" type="file" multiple accept=".pdf,.png,.jpg,.jpeg,.webp,.gif,.md,.csv,.xlsx" hidden></form><p class="composer-caption">${!runtimeReady ? '运行时未就绪或离线：无法核对停止；可准备草稿，连接与授权就绪后才能发送。' : taskPending ? '上一任务及其交付尚未确认结束；可准备草稿，完成后再发送。' : 'Enter 发送 · Shift + Enter 换行 · / 选择能力，不自动发送'}</p>`;
}
