import { escapeHTML as e, renderMarkdown, safeURL } from './markdown.mjs';
import { sessionHash, isRunning } from './core.mjs';

export const statusText = (status) => ({ idle: '待命', running: '运行中', queued: '排队中', completed: '执行已结束', failed: '失败', cancelled: '已取消', waiting_approval: '等待授权', awaiting_approval: '等待授权', waiting_input: '等待回复', cancelling: '取消中' })[status] || status || '未知';
export const badge = (status) => `<span class="badge ${isRunning(status) ? 'live' : ['failed', 'error'].includes(status) ? 'danger' : ''}">${e(statusText(status))}</span>`;
export const empty = (title, description = '') => `<div class="empty"><span class="empty-symbol" aria-hidden="true">◇</span><h3>${e(title)}</h3>${description ? `<p>${e(description)}</p>` : ''}</div>`;

export function renderConversation(detail, questionDrafts = new Map()) {
  if (!detail) return '';
  const messages = (detail.messages || []).map((message) => `<article class="message ${message.role === 'user' ? 'user' : 'assistant'}"><div class="message-byline"><span class="avatar">${message.role === 'user' ? '你' : 'A'}</span><strong>${e(message.role === 'user' ? '你' : message.role === 'assistant' ? 'AlphaFoundry' : message.role)}</strong></div><div class="markdown">${renderMarkdown(message.text)}</div></article>`).join('');
  const approvals = (detail.approvals || []).map((approval) => `<section class="decision-card"><div class="eyebrow">需要你的授权</div><h3>${e(approval.title)}</h3><div class="markdown">${renderMarkdown(approval.detail)}</div><div class="button-row"><button class="button primary" data-approval="${e(approval.id)}" data-decision="approve">允许</button><button class="button danger-outline" data-approval="${e(approval.id)}" data-decision="deny">拒绝</button></div></section>`).join('');
  const questions = (detail.questions || []).map((question) => {
    const draft = questionDrafts.get(question.id) || [];
    return `<form class="decision-card question-form" data-question-form="${e(question.id)}"><div class="eyebrow">DSH 需要补充信息</div>${question.items?.length ? question.items.map((item, index) => `<fieldset><legend>${e(item.question)}</legend>${(item.options || []).map((option) => `<label class="check-label"><input type="${item.multiSelect === true ? 'checkbox' : 'radio'}" name="selection-${index}" value="${e(option.label)}" ${draft[index]?.selected?.includes(option.label) ? 'checked' : ''}>${e(option.label)}${option.description ? `<span class="muted">${e(option.description)}</span>` : ''}</label>`).join('')}<label for="question-${e(encodeURIComponent(question.id))}-${index}">补充回答</label><textarea id="question-${e(encodeURIComponent(question.id))}-${index}" name="custom-${index}" maxlength="10000" rows="2">${e(draft[index]?.custom || '')}</textarea></fieldset>`).join('') : `<div class="markdown">${renderMarkdown(question.text)}</div>`}<button type="submit" class="button primary">提交回答</button></form>`;
  }).join('');
  return `${messages || empty('尚无消息', '输入问题，开始这个会话。所有回答和活动均来自 DSH。')}${approvals}${questions}${detail.error ? `<div class="notice error" role="alert">${e(detail.error)}</div>` : ''}`;
}

export function renderRename(title) {
  return `<form id="rename-form" class="decision-card rename-form"><label for="rename-title">为这个研究会话命名</label><input id="rename-title" name="title" value="${e(title)}" required maxlength="120"><div class="button-row"><button type="submit" class="button primary">保存名称</button><button type="button" class="button" data-cancel-rename>取消</button></div></form>`;
}

export function renderFormatPicker(formats, skillId) {
  const defaults = ['fund-evaluation', 'company-research', 'industry-research'].includes(skillId) ? ['docx', 'html', 'xlsx'] : [];
  const selected = formats === null ? defaults : formats;
  const label = selected.length ? selected.map((value) => value.toUpperCase()).join(' / ') : '无需文件';
  return `<details class="format-picker"><summary>输出格式：${formats === null ? '自动 · ' : ''}${e(label)}</summary><div class="format-options"><label class="check-label"><input id="auto-formats" type="checkbox" data-auto-formats ${formats === null ? 'checked' : ''}>按 Skill 默认格式</label>${['md', 'html', 'docx', 'xlsx', 'png'].map((format) => `<label class="check-label"><input id="format-${format}" type="checkbox" data-format="${format}" ${selected.includes(format) ? 'checked' : ''}>${format.toUpperCase()}</label>`).join('')}<button type="button" class="text-button" data-no-formats>仅聊天，无需文件</button></div></details>`;
}

export function renderDelivery(delivery) {
  if (!delivery) return '';
  const labels = { pending: '等待执行结束后检查', admission_unknown: '受理未知，未重复执行', completed: '文件交付已检查', incomplete: '交付未完成', verification_failed: '交付验证失败', not_required: '本任务未要求文件' };
  return `<section class="context-section delivery-panel" aria-label="文件交付检查"><h3>文件交付检查</h3><p class="badge ${['incomplete', 'verification_failed'].includes(delivery.status) ? 'danger' : ''}">${e(labels[delivery.status] || delivery.status)}</p><p class="small muted">要求：${e((delivery.required_formats || []).map((format) => format.toUpperCase()).join(' / ') || '无需文件')}。执行结束不等于文件交付完成。</p>${(delivery.reasons || []).map((reason) => `<p class="small">${e(reason)}</p>`).join('')}${(delivery.files || []).map((file) => `<div class="delivery-file"><strong>${e(file.name)}</strong><span>${file.valid ? '已通过格式检查' : '未通过检查'}</span>${file.reason ? `<p>${e(file.reason)}</p>` : ''}</div>`).join('')}</section>`;
}

export function renderActivities(detail) {
  const activities = detail?.activities || []; const agents = detail?.subagents || [];
  return `${agents.length ? `<section class="context-section"><div class="section-heading"><h3>Agent 协作</h3><span class="count">${agents.length}</span></div>${agents.map((agent) => `<div class="agent-card"><span class="agent-mark">◇</span><div><strong>${e(agent.name || agent.id)}</strong><div>${badge(agent.status)}</div></div></div>`).join('')}</section>` : ''}<section class="context-section"><div class="section-heading"><h3>运行活动</h3><span class="count">${activities.length}</span></div>${activities.length ? `<ol class="activity-list">${activities.map((activity) => `<li><details><summary><span class="activity-dot ${isRunning(activity.status) ? 'active' : ''}"></span><span><strong>${e(activity.title || activity.type)}</strong><small>${e(statusText(activity.status))}${activity.agent_id ? ` · ${e(activity.agent_id)}` : ''}</small></span></summary>${activity.detail ? `<div class="markdown activity-detail">${renderMarkdown(typeof activity.detail === 'string' ? activity.detail : JSON.stringify(activity.detail, null, 2))}</div>` : ''}</details></li>`).join('')}</ol>` : '<p class="muted small">尚无运行活动。开始研究后，工具调用与任务状态将在这里显示。</p>'}</section>`;
}

export function fileURL(value) {
  const url = safeURL(value);
  if (!url?.startsWith('/api/research/sessions/')) return null;
  const path = url.split('?')[0];
  if (/%(?:2e|2f|5c)/i.test(path) || path.split('/').some((part) => ['.', '..'].includes(part))) return null;
  return /^\/api\/research\/sessions\/[^/]+\/files\/[^/]+(?:\/(?:preview|download))?(?:\?[^#]*)?$/.test(url) ? url : null;
}

export function formatSize(size) {
  if (!Number.isFinite(size)) return '大小未知';
  return size < 1024 ? `${size} B` : size < 1048576 ? `${(size / 1024).toFixed(1)} KB` : `${(size / 1048576).toFixed(1)} MB`;
}

export function renderFiles(files = [], selected = null) {
  const current = files.find((file) => file.id === selected);
  const rows = files.map((file) => {
    const url = fileURL(file.url); const preview = fileURL(file.preview_url);
    return `<div class="file-card"><div class="file-icon" aria-hidden="true">▤</div><div class="file-info"><strong>${e(file.name)}</strong><small>${e(formatSize(file.size))}</small><div class="file-actions">${preview ? `<button data-preview="${e(file.id)}" class="text-button">预览</button>` : ''}${url ? `<a href="${e(url)}" download="${e(file.name)}" class="text-button">下载</a>` : '<span class="muted small">文件链接不可用</span>'}</div></div></div>`;
  }).join('');
  const previewURL = current && fileURL(current.preview_url);
  const preview = previewURL ? `<section class="preview-panel"><div class="section-heading"><strong>${e(current.name)}</strong><button class="icon-button" data-close-preview aria-label="关闭文件预览">×</button></div><iframe title="${e(current.name)} 文件预览" src="${e(previewURL)}" sandbox="" referrerpolicy="no-referrer" loading="lazy"></iframe><p class="muted small">隔离预览：脚本、表单与外部导航已禁用。</p></section>` : '';
  return `${rows || '<p class="muted small">尚无文件。上传附件或让 DSH 生成报告后，真实文件将显示于此。</p>'}${preview}`;
}

export function renderHistory(sessions, filter = '') {
  const visible = sessions.filter((session) => `${session.title} ${session.mode}`.toLowerCase().includes(filter.toLowerCase()));
  if (!visible.length) return empty(filter ? '没有匹配的会话' : '还没有研究会话', filter ? '试试不同的关键词。' : '从 FinGPT 或 Claw 开始，研究历史会自动保留。');
  return `<div class="history-list">${visible.map((session) => `<a class="history-row" href="${sessionHash(session)}"><span class="session-mark ${session.mode === 'claw' ? 'claw' : ''}">${session.mode === 'claw' ? 'C' : 'F'}</span><div><strong>${e(session.title || '未命名会话')}</strong><span class="muted small">${e(session.mode === 'claw' ? 'Claw · 多 Agent' : 'FinGPT · 即时研究')}${session.model ? ` · ${e(session.model)}` : ''}</span></div>${badge(session.status)}<time>${formatTime(session.updated_at)}</time><span aria-hidden="true">↗</span></a>`).join('')}</div>`;
}

function formatTime(value) {
  if (!value) return '时间未知';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '时间未知' : e(date.toLocaleString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }));
}

export function modelOptions(groups = [], current = '') {
  return '<option value="">选择运行模型</option>' + groups.map((group) => `<optgroup label="${e(group.provider)}">${(group.models || []).map((model) => `<option value="${e(JSON.stringify({ provider: group.provider, model: model.id }))}" ${model.id === current ? 'selected' : ''}>${e(model.name || model.id)}</option>`).join('')}</optgroup>`).join('');
}
