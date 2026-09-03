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

const datasetID = (value) => typeof value === 'string' && /^[A-Za-z0-9][A-Za-z0-9_-]*$/.test(value) ? value : null;
const fixedDatasetFiles = new Map([['rows.csv', 'CSV'], ['rows.json', 'JSON'], ['manifest.json', 'manifest']]);

export function datasetFileURL(sessionID, datasetIDValue, fileName) {
  const sid = datasetID(sessionID); const did = datasetID(datasetIDValue);
  if (!sid || !did || !fixedDatasetFiles.has(fileName)) return null;
  return `/api/research/sessions/${sid}/datasets/${did}/files/${fileName}`;
}

function datasetRange(range) {
  if (!range || typeof range !== 'object') return '未提供';
  const start = range.start ?? range.start_date; const end = range.end ?? range.end_date;
  return start || end ? `${start || '未知'} 至 ${end || '未知'}` : '未提供';
}

function datasetStatus(status) {
  return ({ complete: '请求范围已完整取得', snapshot: '公开快照', empty: '来源返回零条', partial: '资料不完整', failed: '取数失败' })[status] || '状态未知';
}

function datasetPagination(dataset) {
  if (dataset.pagination_complete === true) return dataset.status === 'partial' ? '分页已结束，但资料仍不完整' : '分页已结束';
  if (dataset.pagination_complete === false) return '分页尚未结束';
  return '分页状态未知';
}

export function renderDatasets(sessionID, datasets = []) {
  if (!Array.isArray(datasets) || !datasets.length) return '';
  const sid = datasetID(sessionID);
  const cards = datasets.map((dataset) => {
    const did = datasetID(dataset?.dataset_id || dataset?.id);
    const sourceURL = safeURL(dataset?.source_url);
    const source = dataset?.source || '来源未知';
    const status = dataset?.status;
    const warning = status === 'partial' || status === 'failed' || !['complete', 'snapshot', 'empty'].includes(status);
    const filesByName = new Map((Array.isArray(dataset?.files) ? dataset.files : []).filter((file) => fixedDatasetFiles.has(file?.name)).map((file) => [file.name, file]));
    const downloads = did && sid ? [...fixedDatasetFiles].map(([fileName, label]) => {
      const url = datasetFileURL(sid, did, fileName); const hash = filesByName.get(fileName)?.sha256;
      return `<div class="dataset-download"><a class="text-button" href="${e(url)}" download aria-label="下载资料 ${e(dataset?.name || did)} 的 ${label}">下载 ${label}</a>${typeof hash === 'string' ? `<small class="dataset-hash">SHA256：${e(hash)}</small>` : ''}</div>`;
    }).join('') : '<p class="muted small">资料标识不合规，下载不可用。</p>';
    return `<article class="dataset-card"><div class="section-heading"><div><strong>${e(dataset?.name || '未命名资料')}</strong><p class="dataset-source">来源：${sourceURL ? `<a href="${e(sourceURL)}" target="_blank" rel="noopener noreferrer">${e(source)}</a>` : e(source)}</p></div><span class="badge ${warning ? 'danger' : ''}">${e(datasetStatus(status))}</span></div>${status === 'snapshot' ? '<p class="dataset-note">公开快照，不代表完整历史。</p>' : ''}${warning ? `<p class="dataset-warning" role="alert">${e(datasetPagination(dataset))}${status === 'partial' ? '；请结合缺失和限制谨慎使用。' : status ? '；请检查资料说明。' : '；不能据此判断取数结果。'}</p>` : ''}<dl class="dataset-meta"><div><dt>请求范围</dt><dd>${e(datasetRange(dataset?.requested_range))}</dd></div><div><dt>实际范围</dt><dd>${e(datasetRange(dataset?.actual_range))}</dd></div><div><dt>记录数</dt><dd>${Number.isFinite(dataset?.row_count) ? `${e(dataset.row_count)} 条` : '未知'}</dd></div><div><dt>分页</dt><dd>${e(datasetPagination(dataset))}${Number.isFinite(dataset?.pages_fetched) ? ` · ${e(dataset.pages_fetched)} 页` : ''}${Number.isFinite(dataset?.provider_total) ? ` · 供应商总量 ${e(dataset.provider_total)}` : ''}</dd></div><div><dt>取数时间</dt><dd>${e(dataset?.retrieved_at || '未知')}</dd></div><div><dt>截至</dt><dd>${e(dataset?.as_of || '未知')}</dd></div></dl>${dataset?.cache_hit === true ? '<p class="dataset-note">复用已验证快照；取数时间保留原始值。</p>' : ''}${Array.isArray(dataset?.missing) && dataset.missing.length ? `<p class="dataset-note">缺失：${e(dataset.missing.join('；'))}</p>` : ''}${Array.isArray(dataset?.limitations) && dataset.limitations.length ? `<p class="dataset-note">限制：${e(dataset.limitations.join('；'))}</p>` : ''}<div class="dataset-downloads">${downloads}</div></article>`;
  }).join('');
  return `<section class="context-section datasets-panel" aria-label="研究资料"><div class="section-heading"><h3>研究资料</h3><span class="count">${datasets.length}</span></div><p class="muted small">资料输入独立于生成文件和交付状态。</p>${cards}</section>`;
}

export function renderActivities(detail) {
  const activities = detail?.activities || []; const agents = detail?.subagents || [];
  const duration = (value) => Number.isFinite(value) && value >= 0 ? ` · ${(value / 1000).toFixed(1)} 秒` : '';
  return `${agents.length ? `<section class="context-section"><div class="section-heading"><h3>Agent 协作</h3><span class="count">${agents.length}</span></div>${agents.map((agent) => `<div class="agent-card"><span class="agent-mark">◇</span><div><strong>${e(agent.name || agent.id)}</strong><div>${badge(agent.status)}</div><small>${Number.isFinite(agent.usage?.tokens) ? `${agent.usage.tokens} tokens` : ''}${duration(agent.duration_ms)}</small>${agent.error ? `<p class="small">${e(agent.error)}</p>` : ''}${agent.history_truncated ? '<p class="small muted">历史已截断；用量与耗时仅覆盖已读取记录。</p>' : ''}</div></div>`).join('')}</section>` : ''}<section class="context-section"><div class="section-heading"><h3>运行活动</h3><span class="count">${activities.length}</span></div>${activities.length ? `<ol class="activity-list">${activities.map((activity) => { const failed = ['failed', 'error'].includes(activity.status); return `<li><details ${failed ? 'open' : ''}><summary><span class="activity-dot ${isRunning(activity.status) ? 'active' : ''}"></span><span><strong>${e(activity.title || activity.type)}</strong><small>${e(statusText(activity.status))}${activity.agent_id ? ` · ${e(agents.find((agent) => agent.id === activity.agent_id)?.name || activity.agent_id)}` : ''}${duration(activity.duration_ms)}</small></span></summary>${activity.error ? `<p class="notice error activity-error" role="alert">${e(activity.error)}</p>` : ''}${activity.detail ? `<div class="markdown activity-detail">${renderMarkdown(typeof activity.detail === 'string' ? activity.detail : JSON.stringify(activity.detail, null, 2))}</div>` : ''}</details></li>`; }).join('')}</ol>` : '<p class="muted small">尚无运行活动。开始研究后，工具调用与任务状态将在这里显示。</p>'}</section>`;
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
