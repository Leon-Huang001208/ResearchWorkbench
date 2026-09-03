import { escapeHTML as e } from './markdown.mjs';
import { isRunning } from './core.mjs';
import { renderFormatPicker } from './views.mjs';

const quickSkillIDs = ['document-reading', 'company-research', 'industry-research', 'fund-evaluation'];

export function researchQuickSkills(skills = []) {
  const byID = new Map((Array.isArray(skills) ? skills : []).map((skill) => [skill?.id, skill]));
  return quickSkillIDs.map((id) => byID.get(id)).filter(Boolean);
}

export function skillMatches(query, skills = []) {
  const normalized = String(query || '').trim().toLocaleLowerCase();
  if (!normalized) return [];
  return (Array.isArray(skills) ? skills : []).filter((skill) => `${skill?.name || ''} ${skill?.description || ''}`.toLocaleLowerCase().includes(normalized));
}

export function renderQuickSkills(skills = []) {
  const visible = researchQuickSkills(skills);
  if (!visible.length) return '<p class="muted small quick-skill-empty">尚无可用研究 Skill；请在 DSH 中配置后刷新。</p>';
  return `<section class="quick-skills" aria-label="研究 Skill 快捷入口"><div class="section-heading"><h2>从真实研究 Skill 开始</h2><a href="#/skills" class="text-button">查看能力中心</a></div><div class="quick-skill-grid">${visible.map((skill) => `<article class="quick-skill-card"><span class="quick-skill-mark" aria-hidden="true">◇</span><div><h3>${e(skill.name)}</h3><p>${e(skill.description || '此 Skill 未提供描述。')}</p></div><div class="quick-skill-actions"><button type="button" class="text-button" data-skill-detail="${e(skill.id)}">查看详情</button><button type="button" class="button small" data-skill-shortcut="${e(skill.id)}">放入草稿</button></div></article>`).join('')}</div></section>`;
}

export function renderComposer({ page, draft, attachments = [], expectedFormats, skills = [], skillId = '', disabled = false, busy = false, taskPending = false, detail = null, slashOpen = false } = {}) {
  const claw = page === 'claw';
  const matches = slashOpen ? skillMatches(String(draft || '').replace(/^\//, ''), skills).slice(0, 6) : [];
  return `<form id="composer" class="composer" data-dropzone data-paste-support><label class="sr-only" for="prompt">${claw ? '任务目标或补充信息' : '研究问题'}</label><textarea id="prompt" name="prompt" rows="3" placeholder="${claw ? '描述研究目标、约束与希望交付的结果…' : '今天想研究什么？输入问题，或添加文件…'}" ${disabled ? 'disabled' : ''}>${e(draft || '')}</textarea>${matches.length ? `<div class="slash-menu" role="listbox" aria-label="匹配的研究 Skill">${matches.map((skill) => `<button type="button" role="option" class="slash-skill" data-skill-shortcut="${e(skill.id)}"><strong>${e(skill.name)}</strong><span>${e(skill.description || '无描述')}</span></button>`).join('')}</div>` : ''}${attachments.length ? `<div class="attachment-chips">${attachments.map((file) => `<span>${e(file.name)}<button type="button" data-remove-attachment="${e(file.id)}" aria-label="移除附件 ${e(file.name)}">×</button></span>`).join('')}</div>` : ''}${renderFormatPicker(expectedFormats, skillId)}<div class="composer-tools"><button type="button" class="button attachment-button" data-upload ${disabled ? 'disabled' : ''} title="PDF、图片、Markdown、CSV、Excel">＋ <span>附件</span></button><button type="button" class="button attachment-button" data-slash-search ${disabled ? 'disabled' : ''} title="搜索真实 Skill">/ <span>Skill</span></button><label class="sr-only" for="skill-select">使用 Skill</label><select id="skill-select" ${disabled ? 'disabled' : ''}><option value="">按需使用 Skill</option>${skills.map((skill) => `<option value="${e(skill.id)}" ${skillId === skill.id ? 'selected' : ''}>${e(skill.name)}</option>`).join('')}</select><span class="spacer"></span>${detail && (isRunning(detail.status) || detail.can_cancel) ? `<button type="button" class="button danger-outline" data-cancel ${busy ? 'disabled' : ''}>停止</button>` : ''}<button type="submit" class="button primary" ${disabled || taskPending ? 'disabled' : ''}>${busy ? '正在提交…' : detail ? '发送' : '开始研究'} <span aria-hidden="true">↑</span></button></div><input id="file-input" type="file" multiple accept=".pdf,.png,.jpg,.jpeg,.webp,.gif,.md,.csv,.xlsx" hidden></form><p class="composer-caption">${taskPending ? '上一任务及其交付尚未确认结束；可准备草稿，完成后再发送。' : 'Enter 发送 · Shift + Enter 换行 · 输入 / 搜索真实 Skill · 拖放或粘贴文件'}</p>`;
}
