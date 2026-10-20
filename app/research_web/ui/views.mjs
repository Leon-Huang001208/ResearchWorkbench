import { escapeHTML as e, renderMarkdown, safeURL } from './markdown.mjs';
import { sessionHash, isRunning, safeLog } from './core.mjs';
import { icon } from './icons.mjs';
import { renderClawFlow, renderClawStep } from './claw-flow.mjs';
import { renderClawAnswerActions } from './answer-actions.mjs';
import { ensureQuestionState, renderPendingQuestion, renderQuestionHistory } from './questionnaire.mjs';
export { renderPendingQuestion } from './questionnaire.mjs';
import localModels from './local-models.json' with { type: 'json' };

export const statusText = (status) => ({ idle: '待命', running: '运行中', queued: '排队中', completed: '执行已结束', failed: '失败', cancelled: '已取消', waiting_approval: '等待授权', awaiting_approval: '等待授权', waiting_input: '等待回复', cancelling: '取消中' })[status] || status || '未知';
export const badge = (status) => `<span class="badge ${isRunning(status) ? 'live' : ['failed', 'error'].includes(status) ? 'danger' : ''}">${e(statusText(status))}</span>`;
export const empty = (title, description = '') => `<div class="empty"><span class="empty-symbol" aria-hidden="true">◇</span><h3>${e(title)}</h3>${description ? `<p>${e(description)}</p>` : ''}</div>`;

export async function copyResearchText(text, { clipboard = globalThis.navigator?.clipboard, logger = safeLog } = {}) {
  if (typeof text !== 'string' || !text.trim()) throw new Error('没有可复制的回复。');
  try {
    if (typeof clipboard?.writeText !== 'function') throw new Error('clipboard_unavailable');
    await clipboard.writeText(text);
    logger('research_text_copied');
  } catch {
    logger('research_text_copy_failed');
    throw new Error('无法复制，请检查浏览器剪贴板权限或手动选择回复。');
  }
}

const stepStatusText = (status) => ({ running: '进行中', queued: '排队中', pending: '排队中', completed: '已完成', failed: '失败', cancelled: '已取消', interrupted: '已中断', blocked: '已阻断', incomplete: '不完整' })[status] || statusText(status);

// Adapter failure codes reach the banner raw; translate the known compatible-route set.
const failureText = (code) => ({
  compatible_stream_incomplete: '模型响应不完整：连接中断，或输出预算在思考阶段耗尽。请重试。',
  compatible_http_failed: '模型服务连接失败，请检查本地代理与网络后重试。',
  compatible_generation_timeout: '模型响应超时，请重试。',
  compatible_generation_cancelled: '生成已取消。',
  compatible_credentials_missing: '模型密钥不可用，请在设置中重新配置。',
  compatible_credentials_unavailable: '模型密钥读取失败，请在设置中重新配置。',
  compatible_connection_missing: '尚未配置模型连接，请在设置中选择模型。',
  compatible_model_unavailable: '当前模型不可用，请重新选择。',
  compatible_request_too_large: '对话上下文超过模型请求上限；请减少一次性取数数量，或切换更大上下文的模型后重试。',
}[code] || code);

function renderThinking(message, { live = false } = {}) {
  const reasoning = typeof message?.reasoning === 'string' ? message.reasoning.trim() : '';
  if (!reasoning) return '';
  const streaming = live && !message.text;
  return '<details class="answer-thinking"' + (live ? ' open' : '') + '><summary><span class="activity-dot' + (streaming ? ' active' : '') + '"></span><span>' + (streaming ? '正在思考…' : '思考过程') + '</span><span class="process-toggle" aria-hidden="true">' + icon('chevron') + '</span></summary><div class="markdown thinking-detail">' + renderMarkdown(message.reasoning) + '</div></details>';
}

// Group messages and tool activities into 问题 -> 研究过程 -> 正文 rounds, the
// AlphaEngine answer structure. Only main-session activities carry the shared
// projection seq; sub-agent rows (id prefix "child:") stay in 执行记录.
function researchRounds(messages = [], activities = []) {
  const rounds = [];
  for (const message of messages) {
    if (message.role === 'user') rounds.push({ user: message, assistants: [], activities: [], start: Number.isFinite(message.seq) ? message.seq : -1 });
    else if (rounds.length) rounds[rounds.length - 1].assistants.push(message);
    else rounds.push({ user: null, assistants: [message], activities: [], start: Number.isFinite(message.seq) ? message.seq : -1 });
  }
  const scoped = (Array.isArray(activities) ? activities : []).filter((activity) => Number.isFinite(activity?.seq) && !String(activity?.id ?? '').includes(':'));
  for (const activity of scoped) {
    let target = null;
    for (const round of rounds) if (round.start >= 0 && round.start <= activity.seq) target = round;
    (target || rounds[0])?.activities.push(activity);
  }
  return rounds;
}

function renderRoundProcess(activities, { running = false, toolNames = {} } = {}) {
  if (!activities.length) {
    return running ? `<div class="answer-process answer-process-live" role="status"><span class="activity-dot active"></span><span>正在研究…</span></div>` : '';
  }
  const done = activities.filter((activity) => !isRunning(activity.status)).length;
  const current = activities.find((a) => isRunning(a.status));
  const currentLabel = current ? (toolNames[current.title] || current.title || '工具调用') : '';
  const duration = activities.reduce((sum, activity) => sum + (Number.isFinite(activity.duration_ms) ? activity.duration_ms : 0), 0);
  const title = running
    ? (currentLabel ? `正在研究 · ${currentLabel}` : `正在研究 · ${done}/${activities.length}`)
    : `研究过程 · ${activities.length} 步${duration >= 100 ? ` · ${(duration / 1000).toFixed(1)}s` : ''}`;
  const steps = activities.map((activity) => {
    const failed = ['failed', 'error'].includes(activity.status);
    const label = toolNames[activity.title] || activity.title || '工具调用';
    return `<li><details${failed ? ' open' : ''}><summary><span class="activity-dot ${isRunning(activity.status) ? 'active' : ''} ${failed ? 'failed' : ''}"></span><span><strong>${e(label)}</strong><small>${e(stepStatusText(activity.status))}${Number.isFinite(activity.duration_ms) ? ` · ${(activity.duration_ms / 1000).toFixed(1)}s` : ''}</small></span></summary>${activity.error ? `<p class="notice error activity-error" role="alert">${e(activity.error)}</p>` : ''}${activity.detail ? `<div class="markdown activity-detail">${renderMarkdown(typeof activity.detail === 'string' ? activity.detail : JSON.stringify(activity.detail, null, 2))}</div>` : ''}</details></li>`;
  }).join('');
  return `<details class="answer-process"${activities.some(activity => ['failed', 'error'].includes(activity.status)) ? ' open' : ''}><summary><span class="activity-dot${running ? ' active' : ''}"></span><span>${e(title)}</span><span class="process-toggle" aria-hidden="true">${icon('chevron')}</span></summary><ol class="activity-list process-steps">${steps}</ol></details>`;
}

function renderAnswerActions(round, message, { feedback = null, copied = '', retryAllowed = true } = {}) {
  const retry = round.user ? `<button type="button" class="answer-action" data-retry-round="${e(round.user.id)}" ${retryAllowed ? '' : 'disabled'} title="以同样的问题重新研究">${icon('restore')}<span>重试</span></button>` : '';
  const isCopied = copied === `answer:${message.id}`;
  const isShared = copied === 'share';
  return `<div class="answer-actions">${retry}<button type="button" class="answer-action" data-copy-answer="${e(message.id)}">${icon('copy')}<span>${isCopied ? '已复制' : '复制'}</span></button><button type="button" class="answer-action" data-share-session>${icon('share')}<span>${isShared ? '已复制链接' : '分享'}</span></button><span class="answer-feedback" role="group" aria-label="回答反馈"><button type="button" class="answer-action ${feedback === 'good' ? 'active' : ''}" data-answer-feedback="good" data-message="${e(message.id)}" aria-pressed="${feedback === 'good'}">${icon('thumbUp')}<span>有用</span></button><button type="button" class="answer-action ${feedback === 'bad' ? 'active' : ''}" data-answer-feedback="bad" data-message="${e(message.id)}" aria-pressed="${feedback === 'bad'}">${icon('thumbDown')}<span>没用</span></button></span></div>`;
}

export function renderConversation(detail, questionDrafts = new Map(), options = {}) {
  options = Array.isArray(options) ? { extraEntries: options } : options;
  const extraEntries = Array.isArray(options.extraEntries) ? options.extraEntries : [];
  if (!detail) return '';
  const resolveLink = artifactLinkResolver(detail);
  const assistantLabel = detail.mode === 'fingpt' ? 'FinGPT 回复' : detail.mode === 'claw' ? 'Claw 回复' : '助手回复';
  let researchMessages = '';
  if (detail.mode !== 'claw') {
    const running = isRunning(detail.status) && !(detail.questions || []).length;
    const rounds = researchRounds(detail.messages || [], detail.activities || []);
    const lastRound = rounds[rounds.length - 1];
    researchMessages = rounds.map((round) => {
      const isLast = round === lastRound;
      const reportScope = detail.mode === 'fingpt' && detail.research_quality;
      const roundResolver = reportScope ? artifactLinkResolver(detail, isLast ? detail.research_report_delivery || {} : {}) : resolveLink;
      const parts = [];
      if (round.user) parts.push(`<article class="message user" aria-label="用户消息"><div class="markdown">${renderMarkdown(round.user.text, { resolveLink })}</div></article>`);
      if (!round.assistants.length && isLast && running) parts.push(renderRoundProcess(round.activities, { running: true, toolNames: options.toolNames }));
      round.assistants.forEach((message, index) => {
        if (index === 0 && (round.activities.length || (isLast && running))) parts.push(renderRoundProcess(round.activities, { running: isLast && running, toolNames: options.toolNames }));
        const label = message.role === 'assistant' ? assistantLabel : `${message.role || '未知角色'}消息`;
        parts.push(renderThinking(message, { live: isLast && running }));
        parts.push(`<article class="message assistant" aria-label="${e(label)}"><div class="markdown">${renderMarkdown(message.text, { resolveLink: roundResolver })}</div></article>`);
        if (isLast && index === round.assistants.length - 1 && !running && reportScope) parts.push(renderCheckedReportLinks(detail));
        if (index === round.assistants.length - 1 && !running) parts.push(renderAnswerActions(round, message, { feedback: options.feedback?.[message.id], copied: options.copied, retryAllowed: options.retryAllowed !== false && !detail.can_cancel && !['pending', 'admission_unknown'].includes(detail.delivery?.status) }));
      });
      return parts.join('');
    }).join('');
  }
  const messageEntries = (detail.messages || []).map((message, index) => {
    const label = message.role === 'user' ? '用户消息' : message.role === 'assistant' ? assistantLabel : `${message.role || '未知角色'}消息`;
    const thinking = message.role === 'assistant' ? renderThinking(message, { live: isRunning(detail.status) && index === detail.messages.length - 1 }) : '';
    return { kind: message.role === 'user' ? 'user' : 'assistant', seq: Number.isFinite(message.seq) ? message.seq : Infinity, index, html: `${thinking}<article class="message ${message.role === 'user' ? 'user' : 'assistant'}" aria-label="${e(label)}"><div class="markdown">${renderMarkdown(message.text, { resolveLink })}</div></article>`, copyHTML: detail.mode === 'claw' && message.role === 'assistant' && message.text ? renderClawAnswerActions(detail, index, options) : '' };
  });
  const questionEntries = (Array.isArray(detail.question_history) ? detail.question_history : []).filter(question => Number.isFinite(question?.seq) && Array.isArray(question.items) && Array.isArray(question.answers)).map((question, index) => ({
    kind: 'decision', seq: question.seq, index: messageEntries.length + index, html: renderQuestionHistory(question, detail.id || ''),
  }));
  const nativeQuestionIDs = new Set([...(detail.question_history || []), ...(detail.questions || [])].map(question => question.id));
  const activities = detail.mode === 'claw' ? (detail.activities || []).filter(activity => !nativeQuestionIDs.has(activity.id)) : [];
  const activityEntries = activities.filter(activity => Number.isFinite(activity.seq)).map((activity,index) => ({kind:'activity',status:activity.status,seq:activity.seq,index:messageEntries.length + questionEntries.length + index,html:renderClawStep(activity,{sessionId:detail.id,statusLabel:statusText(activity.status),agents:detail.subagents || []})}));
  const unpositioned = activities.filter(activity => !Number.isFinite(activity.seq));
  const approvals = (detail.approvals || []).map((approval) => `<section class="decision-card"><div class="eyebrow">需要你的授权</div><h3>${e(approval.title)}</h3><div class="markdown">${renderMarkdown(approval.detail)}</div><div class="button-row"><button class="button primary" data-approval="${e(approval.id)}" data-decision="approve">允许</button><button class="button danger-outline" data-approval="${e(approval.id)}" data-decision="deny">拒绝</button></div></section>`).join('');
  const pendingQuestionEntries = (detail.questions || []).map((question,index) => {
    const draft = ensureQuestionState(questionDrafts, detail.id || '', question);
    const html = renderPendingQuestion(question, draft, { sessionId: detail.id || '' });
    return {kind:'decision',seq:question.seq,index:messageEntries.length + questionEntries.length + activityEntries.length + index,html};
  });
  const positionedQuestions = detail.mode === 'claw' ? pendingQuestionEntries.filter(question=>Number.isFinite(question.seq)) : [];
  const questions = pendingQuestionEntries.filter(question=>!positionedQuestions.includes(question)).map(question=>question.html).join('');
  const anchoredCards = detail.mode === 'claw' ? extraEntries.filter(entry=>Number.isFinite(entry.seq) && typeof entry.html === 'string').map((entry,index)=>({...entry,kind:'decision',index:messageEntries.length + questionEntries.length + activityEntries.length + pendingQuestionEntries.length + index})) : [];
  const messages = detail.mode !== 'claw' ? researchMessages + questionEntries.map(entry => entry.html).join('') : renderClawFlow([...messageEntries, ...questionEntries, ...activityEntries, ...positionedQuestions, ...anchoredCards].sort((a,b) => a.seq - b.seq || a.index - b.index), detail);
  const html = `${activities.length ? `<p class="muted small conversation-tool-summary">${e(activitySummary(activities))}</p>` : ''}${messages || empty('尚无消息', '输入问题，开始这个会话。所有回答和活动均来自 DSH。')}${unpositioned.length ? `<section class="conversation-activity"><p class="muted small">以下活动缺少原生事件位置，未推断其回答顺序。</p>${unpositioned.map(activity=>renderActivityCard(activity,detail.subagents || [],{compact:true})).join('')}</section>` : ''}${approvals}${questions}${detail.error ? `<div class="notice error" role="alert">${e(failureText(detail.error))}</div>` : ''}`;
  return restrictInvalidReportLinks(html, detail);
}

function restrictInvalidReportLinks(html, detail) {
  if (detail.research_quality?.status !== 'invalid' || !detail.id) return html;
  const prefix = `/api/research/sessions/${encodeURIComponent(detail.id)}/files/`;
  const outputs = new Set((detail.files || []).filter(file => file.kind === 'outputs').map(file => file.id));
  return html.replace(/<a\b([^>]*)>([\s\S]*?)<\/a>/g, (link, attributes, text) => {
    const url = attributes.match(/\bhref="([^"]*)"/)?.[1];
    if (!url?.startsWith(prefix) || !outputs.has(url.slice(prefix.length).split(/[/?#]/)[0])) return link;
    return `<span class="report-export-blocked">${text}（报告完整性未通过）</span>`;
  });
}

export function activitySummary(activities = []) {
  const tools = activities.filter(activity => activity.type === 'tool');
  const success = tools.filter(activity => activity.status === 'completed').length;
  const failed = tools.filter(activity => ['failed','error'].includes(activity.status)).length;
  const pending = tools.length - success - failed;
  return `工具 ${tools.length} 项 · 成功 ${success} · 失败 ${failed}${pending ? ` · 其他状态 ${pending}` : ''}`;
}

export function renderActivityCard(activity, agents = [], {compact = false} = {}) {
  const failed = ['failed','error'].includes(activity.status);
  const duration = Number.isFinite(activity.duration_ms) && activity.duration_ms >= 0 ? ` · ${(activity.duration_ms / 1000).toFixed(1)} 秒` : '';
  const payload = value => `<pre class="activity-payload">${e(typeof value === 'string' ? value : JSON.stringify(value,null,2))}</pre>`;
  const separate = Object.hasOwn(activity,'arguments') || Object.hasOwn(activity,'result');
  return `<details ${failed && !compact ? 'open' : ''}><summary><span class="activity-dot ${isRunning(activity.status) ? 'active' : ''}"></span><span><strong>${e(activity.title || activity.tool || activity.type || '活动')}</strong><small>${e(statusText(activity.status))}${activity.agent_id ? ` · ${e(agents.find(agent=>agent.id===activity.agent_id)?.name || activity.agent_id)}` : ''}${duration}</small></span></summary>${activity.error ? `<p class="notice error activity-error" role="alert">${e(activity.error)}</p>` : ''}${Object.hasOwn(activity,'arguments') ? `<section><h4>参数</h4>${payload(activity.arguments)}</section>` : ''}${Object.hasOwn(activity,'result') ? `<section><h4>结果</h4>${payload(activity.result)}</section>` : ''}${!separate && activity.detail ? `<div class="markdown activity-detail">${renderMarkdown(typeof activity.detail === 'string' ? activity.detail : JSON.stringify(activity.detail,null,2))}</div>` : ''}</details>`;
}

export function renderRename(title, error = '', busy = false) {
  return `<div class="dialog-backdrop" data-dialog-backdrop><form id="rename-form" class="session-dialog rename-form" role="dialog" aria-modal="true" aria-labelledby="rename-heading"><div><div class="eyebrow">会话管理</div><h2 id="rename-heading">重命名会话</h2></div><label for="rename-title">会话名称</label><input id="rename-title" name="title" value="${e(title)}" required maxlength="120" autocomplete="off" ${busy ? 'disabled' : ''}>${error ? `<p class="notice error" role="alert">${e(error)}</p>` : ''}<div class="button-row"><button type="button" class="button" data-cancel-rename ${busy ? 'disabled' : ''}>取消</button><button type="submit" class="button primary" ${busy ? 'disabled' : ''}>${busy ? '正在保存…' : '保存名称'}</button></div></form></div>`;
}

export function renderDeleteConfirm(session, error = '', busy = false) {
  if (!session) return '';
  return `<div class="dialog-backdrop" data-dialog-backdrop><form id="delete-session-form" class="session-dialog" role="dialog" aria-modal="true" aria-labelledby="delete-heading"><div><div class="eyebrow">移至已删除</div><h2 id="delete-heading">删除“${e(session.title || '未命名会话')}”？</h2></div><p>会话将移至“已删除”并保留 30 天，期间可以恢复；研究记录和文件不会立即清除。</p>${error ? `<p class="notice error" role="alert">${e(error)}</p>` : ''}<div class="button-row"><button type="button" class="button" data-cancel-delete ${busy ? 'disabled' : ''}>取消</button><button type="submit" class="button danger" ${busy ? 'disabled' : ''}>${busy ? '正在删除…' : '移至已删除'}</button></div></form></div>`;
}

export function renderPurgeConfirm(session, error = '', busy = false) {
  if (!session) return '';
  return `<div class="dialog-backdrop" data-dialog-backdrop><form id="purge-session-form" class="session-dialog" role="dialog" aria-modal="true" aria-labelledby="purge-heading"><div><div class="eyebrow">永久删除</div><h2 id="purge-heading">永久删除“${e(session.title || '未命名会话')}”？</h2></div><p>此操作无法撤销。DSH 原生对话日志，以及 Workbench 保存的本会话附件、数据集、产物和索引记录都会被清除。</p>${error ? `<p class="notice error" role="alert">${e(error)}</p>` : ''}<div class="button-row"><button type="button" class="button" data-cancel-purge ${busy ? 'disabled' : ''}>取消</button><button type="submit" class="button danger" ${busy ? 'disabled' : ''}>${busy ? '正在永久删除…' : '永久删除'}</button></div></form></div>`;
}

export function renderFormatPicker(formats, capability) {
  const defaults = capability?.metadata?.default_formats || capability?.default_formats || [];
  const selected = formats === null ? defaults : formats;
  const label = selected.length ? selected.map((value) => value.toUpperCase()).join(' / ') : '无需文件';
  return `<details class="format-picker"><summary>输出格式：${formats === null ? '自动 · ' : ''}${e(label)}</summary><div class="format-options"><label class="check-label"><input id="auto-formats" type="checkbox" data-auto-formats ${formats === null ? 'checked' : ''}>按 Skill 默认格式</label>${['md', 'html', 'docx', 'pdf', 'xlsx', 'png'].map((format) => `<label class="check-label"><input id="format-${format}" type="checkbox" data-format="${format}" ${selected.includes(format) ? 'checked' : ''}>${format.toUpperCase()}</label>`).join('')}<button type="button" class="text-button" data-no-formats>仅聊天，无需文件</button></div></details>`;
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

export function renderResearchPlan(detail) {
  const canonical = detail?.research_plan;
  const hasCanonical = detail && Object.hasOwn(detail, 'research_plan');
  const plan = hasCanonical ? canonical?.status === 'available' ? {
    turn: canonical.turn, seq: canonical.seq, version: `${canonical.turn}:${canonical.seq}`, todos: canonical.items,
  } : null : detail?.plan;
  const error = hasCanonical ? canonical?.status === 'invalid' ? '原生计划事件无效；当前计划无法确认。' : null : detail?.plan_error;
  const incomplete = hasCanonical ? canonical?.history_complete === false : detail?.plan_history_incomplete === true;
  if (!plan && !error && !incomplete) return '';
  const labels = { pending: '待开始', in_progress: '进行中', completed: '已完成' };
  const items = !error && Array.isArray(plan?.todos) ? plan.todos : [];
  const terminal = ['failed', 'cancelled', 'interrupted', 'blocked', 'incomplete'].includes(detail?.status);
  return `<section class="context-section research-plan" aria-label="原生研究计划"><div class="section-heading"><h3>原生研究计划</h3>${plan && !error ? `<span class="count">回合 ${e(plan.turn)} · 版本 ${e(plan.version)}</span>` : ''}</div>${error ? `<p class="notice error" role="alert">${e(error)}</p>` : ''}${incomplete ? '<p class="notice" role="status">计划历史不完整；仅显示已读取原生日志能确认的快照。</p>' : ''}${terminal ? `<p class="small">研究${e(statusText(detail.status))}；计划项保留最后一次原生状态。</p>` : ''}${items.length ? `<ol class="native-todo-list">${items.map(item => `<li><span class="native-todo-status">${e(labels[item.status] || '状态未知')}</span><span>${e(item.content)}</span></li>`).join('')}</ol>` : plan && !error ? '<p class="muted small">本回合的原生计划为空。</p>' : ''}<p class="muted small">计划状态不证明并行执行；${hasCanonical ? '计划勾选不代表研究或文件交付完成。' : '计划项完成不代表文件交付完成。'}</p></section>`;
}

export function renderActivities(detail) {
  const activities = detail?.activities || []; const agents = detail?.subagents || [];
  const duration = (value) => Number.isFinite(value) && value >= 0 ? ` · ${(value / 1000).toFixed(1)} 秒` : '';
  return `${agents.length ? `<section class="context-section"><div class="section-heading"><h3>Agent 协作</h3><span class="count">${agents.length}</span></div>${agents.map((agent) => `<div class="agent-card"><span class="agent-mark">◇</span><div><strong>${e(agent.name || agent.id)}</strong><div>${badge(agent.status)}</div><small>${Number.isFinite(agent.usage?.tokens) ? `${agent.usage.tokens} tokens` : ''}${duration(agent.duration_ms)}</small>${agent.error ? `<p class="small">${e(agent.error)}</p>` : ''}${agent.history_truncated ? '<p class="small muted">历史已截断；用量与耗时仅覆盖已读取记录。</p>' : ''}</div></div>`).join('')}</section>` : ''}<section class="context-section"><div class="section-heading"><h3>运行活动</h3><span class="count">${activities.length}</span></div>${activities.length ? `<ol class="activity-list">${activities.map(activity => `<li>${renderActivityCard(activity,agents)}</li>`).join('')}</ol>` : '<p class="muted small">尚无运行活动。开始研究后，工具调用与任务状态将在这里显示。</p>'}</section>`;
}

export function fileURL(value) {
  const url = safeURL(value);
  if (!url?.startsWith('/api/research/sessions/')) return null;
  const path = url.split('?')[0];
  if (/%(?:2e|2f|5c)/i.test(path) || path.split('/').some((part) => ['.', '..'].includes(part))) return null;
  return /^\/api\/research\/sessions\/[^/]+\/files\/[^/]+(?:\/(?:preview|download))?(?:\?[^#]*)?$/.test(url) ? url : null;
}

// Resolve model-authored relative links through the verified, current-session catalog only.
function checkedReportFiles(detail) {
  const delivery = detail.research_report_delivery;
  if (detail.research_quality?.status === 'invalid' || delivery?.status !== 'bound' || !delivery.version_id || !/^[a-f0-9]{64}$/.test(delivery.report_content_sha256 || '') || delivery.report_content_sha256 !== detail.research_report?.content_sha256) return [];
  const prefix = `/api/research/sessions/${encodeURIComponent(detail.id)}/files/`;
  return (Array.isArray(delivery.files) ? delivery.files : []).filter(file =>
    /^[0-9a-f]{24}$/.test(file.id || '') && /^[0-9a-f]{64}$/.test(file.sha256 || '') &&
    file.path?.startsWith(`outputs/report-versions/${delivery.version_id}/`) &&
    fileURL(file.url) === `${prefix}${file.id}/download` &&
    (detail.files || []).filter(row => row.id === file.id && row.url === file.url).length === 1);
}

function renderCheckedReportLinks(detail) {
  const files = checkedReportFiles(detail).filter(file => /\.(html|docx|pdf)$/i.test(file.name || ''));
  if (!files.length) return '';
  const state = detail.research_quality?.status === 'passed' ? '质量通过' : '质量未通过';
  return `<section aria-label="Host核对的报告文件"><p>本轮检查归档 · ${e(state)}。文件可用不等于研究验收通过。</p>${files.map(file => `<a href="${e(file.url)}" download="${e(file.name)}">${e(file.name)}</a>`).join(' · ')}</section>`;
}

function artifactLinkResolver(detail, reportDelivery) {
  const registered = Array.isArray(detail.files) ? detail.files : [];
  const delivery = Array.isArray(detail.delivery?.files) ? detail.delivery.files : [];
  const links = new Map();
  const counts = new Map();
  for (const file of delivery) {
    if (typeof file?.path === 'string') counts.set(file.path, (counts.get(file.path) || 0) + 1);
  }
  if (typeof detail.id !== 'string' || !detail.id) return () => null;
  const prefix = `/api/research/sessions/${encodeURIComponent(detail.id)}/files/`;
  for (const file of delivery) {
    const path = file?.path;
    if (file?.valid !== true || typeof path !== 'string' || !path.startsWith('outputs/') || /[%\\\s<>\u0000-\u001f\u007f]/.test(path) || path.split('/').some(part => !part || part === '.' || part === '..') || counts.get(path) !== 1) continue;
    const url = fileURL(file.url);
    if (!/^[0-9a-f]{24}$/.test(file.id || '') || !url?.startsWith(prefix) || url !== `${prefix}${file.id}/download`) continue;
    if (registered.filter(row => row?.id === file.id && row?.url === url).length !== 1) continue;
    links.set(path, url);
  }
  const verified = new Set(checkedReportFiles(detail).map(file => file.url));
  const names = new Map(registered.map(file => [file.url, file.name]));
  return (path) => {
    // Classify browser/ASGI-equivalent paths before allowing ordinary navigation.
    // Only exact Host aliases can resolve; normalized/encoded variants cannot
    // fall back to safeURL and regain a link to a different report version.
    let canonicalPath = path;
    try {
      for (let i=0;i<3;i++) canonicalPath = new URL(decodeURIComponent(new URL(canonicalPath, 'http://rwb.invalid').pathname), 'http://rwb.invalid').pathname;
    } catch { return null; }
    const local = path.startsWith('outputs/') || canonicalPath.startsWith('/outputs/') || canonicalPath.startsWith('/api/research/sessions/');
    if (!local) return undefined;
    if (path.startsWith(prefix) && registered.some(file => file.kind === 'inputs' && [file.url, file.preview_url].includes(path))) return fileURL(path);
    if (detail.research_quality?.status === 'invalid') return null;
    const report = /\.(html|docx|pdf)$/i.test(path) || /\.(html|docx|pdf)$/i.test(names.get(path) || '') || /research-report\.json$/.test(path) || /research-report\.json$/.test(names.get(path) || '');
    if (reportDelivery !== undefined && report) {
      const target = reportDelivery.aliases?.[path];
      return typeof target === 'string' && verified.has(target) ? target : null;
    }
    if (path.startsWith('/api/')) return registered.some(file => file.url === path) ? path : null;
    return links.get(path) || null;
  };
}

export function formatSize(size) {
  if (!Number.isFinite(size)) return '大小未知';
  return size < 1024 ? `${size} B` : size < 1048576 ? `${(size / 1024).toFixed(1)} KB` : `${(size / 1048576).toFixed(1)} MB`;
}

export function renderFiles(files = [], selected = null, { blockReportExports = false } = {}) {
  const blocked = file => blockReportExports && file?.kind === 'outputs';
  const current = files.find((file) => file.id === selected);
  const rows = files.map((file) => {
    const url = !blocked(file) && fileURL(file.url); const preview = !blocked(file) && fileURL(file.preview_url);
    const office = !blocked(file) && /\.(docx|xlsx|pptx)$/i.test(file.name) && /^[0-9a-f]{24}$/.test(file.id || '');
    return `<div class="file-card"><div class="file-icon" aria-hidden="true">▤</div><div class="file-info"><strong>${e(file.name)}</strong><small>${e(formatSize(file.size))}</small><div class="file-actions">${preview ? `<button data-preview="${e(file.id)}" class="text-button">预览</button>` : ''}${office ? `<button data-document-open="${e(file.id)}" class="text-button">读取与修改</button>` : ''}${url ? `<a href="${e(url)}" download="${e(file.name)}" class="text-button">下载</a>` : `<span class="muted small">${blocked(file) ? '报告完整性未通过，暂不可导出' : '文件链接不可用'}</span>`}</div></div></div>`;
  }).join('');
  const previewURL = current && !blocked(current) && fileURL(current.preview_url);
  const preview = previewURL ? `<section class="preview-panel"><div class="section-heading"><strong>${e(current.name)}</strong><button class="icon-button" data-close-preview aria-label="关闭文件预览">×</button></div><iframe title="${e(current.name)} 文件预览" src="${e(previewURL)}" sandbox="" referrerpolicy="no-referrer" loading="lazy"></iframe><p class="muted small">隔离预览：脚本、表单与外部导航已禁用。</p></section>` : '';
  return `<div class="button-row"><button type="button" data-document-create="docx" class="button small">新建 Word 文件</button><button type="button" data-document-create="xlsx" class="button small">新建 Excel 文件</button><button type="button" data-document-create="pptx" class="button small">新建 PowerPoint 文件</button></div>${rows || '<p class="muted small">尚无文件。上传附件或生成文档后，真实文件将显示于此。</p>'}${preview}`;
}

export function documentTargets(result) {
  const doc = result?.document || {}; const targets = [];
  if (result?.format === 'docx') {
    (doc.paragraphs || []).forEach((p, index) => targets.push({ label: `段落 ${index + 1} · ${p.style || ''}`, value: p.text, change: { kind: 'paragraph', index } }));
    (doc.tables || []).forEach((rows, table) => rows.forEach((row, r) => row.forEach((value, column) => targets.push({ label: `表格 ${table + 1} · 行 ${r + 1} 列 ${column + 1}`, value, change: { kind: 'table_cell', table, row: r, column } }))));
  } else if (result?.format === 'xlsx') {
    (doc.sheets || []).forEach(sheet => sheet.rows.forEach((row, r) => row.forEach((value, c) => {
      let number = c + 1, column = ''; while (number) { number--; column = String.fromCharCode(65 + number % 26) + column; number = Math.floor(number / 26); }
      targets.push({ label: `${sheet.name}!${column}${r + 1}`, value: value ?? '', change: { kind: 'cell', sheet: sheet.name, cell: `${column}${r + 1}` } });
    })));
  } else if (result?.format === 'pptx') {
    (doc.slides || []).forEach(slide => slide.objects.forEach(object => targets.push({ label: `第 ${slide.number} 页 · 对象 ${object.id}`, value: object.text, change: { kind: 'shape_text', slide: slide.number, shape_id: object.id } })));
  }
  return targets.slice(0, 200);
}

export function documentEditValue(value, type) {
  if (type === 'number') {
    if (!/^-?(?:\d+\.?\d*|\.\d+)$/.test(value) || !Number.isFinite(Number(value))) throw new Error('请输入有效数字');
    return Number(value);
  }
  if (type === 'boolean') {
    if (!['true', 'false'].includes(value)) throw new Error('布尔值请输入 true 或 false');
    return value === 'true';
  }
  return value;
}

export function documentCreationPayload(fields) {
  const lines = value => String(value || '').split(/\r?\n/).filter(line => line.length);
  if (fields.format === 'docx') {
    if (fields.mode && !['file', 'native'].includes(fields.mode)) throw new Error('执行方式不支持');
    const table = lines(fields.table).map(line => line.split('\t'));
    if (table.length && table.some(row => row.length !== table[0].length)) throw new Error('表格各行的列数必须一致');
    return { format: 'docx', operation: 'generate', mode: fields.mode || 'file', content: {
      title: String(fields.title || ''), paragraphs: lines(fields.paragraphs), tables: table.length ? [table] : [],
    } };
  }
  if (fields.format === 'pptx') return { format: 'pptx', operation: 'generate', mode: 'file', content: { slides: [1, 2].map(i => ({ title: String(fields[`slide${i}_title`] || ''), body: String(fields[`slide${i}_body`] || '') })) } };
  if (fields.format !== 'xlsx') throw new Error('生成格式不支持');
  const sheets = [1, 2].filter(i => String(fields[`sheet${i}_name`] || '').trim()).map(i => ({
    name: String(fields[`sheet${i}_name`]).trim(), rows: lines(fields[`sheet${i}_rows`]).map(line => line.split('\t').map(value =>
      /^-?(?:0|[1-9]\d*)(?:\.\d+)?$/.test(value) && Number.isFinite(Number(value)) ? Number(value) : value)),
  }));
  if (!sheets.length || new Set(sheets.map(sheet => sheet.name)).size !== sheets.length) throw new Error('请填写不同的工作表名称');
  return { format: 'xlsx', operation: 'generate', mode: 'file', content: { sheets } };
}

function renderDocumentCreation(editor) {
  const word = editor.creating === 'docx'; const ppt = editor.creating === 'pptx';
  const draft = editor.draft || (ppt ? { slide1_title: '研究概览', slide1_body: '本页保持不变', slide2_title: '结论版本 A', slide2_body: '样本数为 2' } : word ? { title: 'Word 验收报告', paragraphs: '这段内容保持不变。\n报告版本 A。', table: '项目\t数值\n样本\t2' } : {
    sheet1_name: 'Inputs', sheet1_rows: '数值\n2\n3', sheet2_name: 'Summary', sheet2_rows: '合计\t=SUM(Inputs!A2:A3)',
  });
  const field = (name, label, multiline = false) => `<label>${e(label)}${multiline ? `<textarea name="${name}" rows="4">${e(draft[name] || '')}</textarea>` : `<input name="${name}" value="${e(draft[name] || '')}">`}</label>`;
  const mode = word ? `<label>执行方式<select name="mode"><option value="file" ${draft.mode !== 'native' ? 'selected' : ''}>文件处理</option><option value="native" ${draft.mode === 'native' ? 'selected' : ''}>本机 Word 操作</option></select></label><p>本机操作会创建、保存并重新打开本任务文稿；Office 可能要求单文件访问授权。</p>` : '';
  return `<div class="dialog-backdrop"><section class="session-dialog" role="dialog" aria-modal="true" aria-label="生成 Office 文件"><div class="section-heading"><strong>新建 ${word ? 'Word' : ppt ? 'PowerPoint' : 'Excel'} 文件</strong><button type="button" data-document-close ${editor.busy ? 'disabled' : ''} aria-label="关闭文档操作">×</button></div>${word ? '' : '<p>文件生成；不会启动本机 Office。</p>'}${editor.error ? `<p role="alert">${e(editor.error)}</p>` : ''}<form id="document-create-form"><fieldset ${editor.busy ? 'disabled' : ''}>${ppt ? field('slide1_title', '第 1 页标题') + field('slide1_body', '第 1 页正文', true) + field('slide2_title', '第 2 页标题') + field('slide2_body', '第 2 页正文', true) : word ? field('title', '标题') + field('paragraphs', '段落（每行一段）', true) + field('table', '表格（制表符分列，每行一行）', true) : field('sheet1_name', '工作表 1 名称') + field('sheet1_rows', '工作表 1 内容（制表符分列）', true) + field('sheet2_name', '工作表 2 名称（可留空）') + field('sheet2_rows', '工作表 2 内容（制表符分列）', true)}${mode}${word || ppt ? '' : '<p>公式将保留但未重算；真实计算需另用 Excel。</p>'}<button type="submit" class="button primary">${editor.busy ? '正在生成…' : '生成文件'}</button></fieldset></form></section></div>`;
}

export function renderDocumentEditor(editor) {
  if (!editor) return '';
  if (editor.creating) return renderDocumentCreation(editor);
  const targets = documentTargets(editor.result);
  const facts = editor.lastResult || editor.result;
  const cleanup = facts?.mode === 'native' ? ({confirmed: '已清理', unverified: '未确认', failed: '失败', not_created: '未创建'}[facts?.diagnostics?.cleanup_outcome] || '未确认') : null;
  const output = editor.lastResult?.output || editor.result?.output; const url = output && fileURL(output.url);
  const draft = editor.draft || { target: 0, value: targets[0]?.value ?? '', mode: 'file', value_type: typeof targets[0]?.value === 'number' ? 'number' : typeof targets[0]?.value === 'boolean' ? 'boolean' : 'string' };
  return `<div class="dialog-backdrop" data-document-backdrop><section class="session-dialog" role="dialog" aria-modal="true" aria-label="Office 文档操作"><div class="section-heading"><strong>${e(editor.file.name)}</strong><button type="button" data-document-close ${editor.busy ? "disabled" : ""} class="icon-button" aria-label="关闭文档操作">×</button></div>${editor.busy ? '<p role="status">正在执行文档操作…</p>' : ''}${editor.error ? `<p role="alert">${e(editor.error)}</p>` : ''}${facts ? `<p>${e(facts.status)} · ${e(facts.mode === "native" ? "本机操作" : "文件处理")} · ${e(facts.last_completed_step || facts.diagnostics?.last_completed_step || facts.code || "")}</p>` : ""}${cleanup ? `<p>本任务资源清理：${e(cleanup)}；功能结果与清理分别记录。</p>` : ""}${facts?.calculation_engine ? `<p>已由 ${e(facts.calculation_engine)} 实际计算，并完成保存后重开读回。</p>` : editor.result?.document?.calculation === 'not_recalculated' ? '<p>文件模式：公式未重算，结果须由 Excel 验证。</p>' : ''}${targets.length ? `<form id="document-edit-form" data-document-revision="${e(editor.result?.sha256 || '')}" data-document-busy="${editor.busy ? "true" : "false"}"><fieldset ${editor.busy ? "disabled" : ""}><label>修改位置<select name="target" data-document-target>${targets.map((t, i) => `<option value="${i}" ${Number(draft.target) === i ? "selected" : ""}>${e(t.label)}</option>`).join('')}</select></label><label>新内容<textarea name="value" rows="4">${e(draft.value)}</textarea></label>${editor.result?.format === "xlsx" ? `<label>值类型<select name="value_type">${["string", "number", "boolean"].map(type => `<option value="${type}" ${draft.value_type === type ? "selected" : ""}>${({string:"文本",number:"数字",boolean:"布尔值"})[type]}</option>`).join("")}</select></label>` : ""}<label>执行方式<select name="mode"><option value="file" ${draft.mode === "file" ? "selected" : ""}>文件处理</option><option value="native" ${draft.mode === "native" ? "selected" : ""}>本机 Office 操作</option></select></label><p>原件保持不变；修改会生成新文件。复杂修订和嵌入对象可能无法处理。</p><button type="submit" class="button primary" ${editor.busy ? 'disabled' : ''}>保存新版本</button></fieldset></form>` : ''}${url ? `<a class="button" href="${e(url)}" download="${e(output.name)}">下载新版本</a>` : ''}</section></div>`;
}

export function renderHistory(sessions, filter = '', mode = null, view = 'active') {
  const needle = String(filter || '').trim().toLocaleLowerCase();
  const visible = sessions.filter((session) => (!mode || session.mode === mode) && `${session?.title || ''} ${session?.mode || ''}`.toLocaleLowerCase().includes(needle));
  const modeLabel = mode === 'claw' ? 'Claw' : mode === 'fingpt' ? 'FinGPT' : '';
  if (!visible.length) return empty(filter ? '没有匹配的会话' : view === 'deleted' ? '“已删除”中没有会话' : `还没有${modeLabel ? ` ${modeLabel}` : ''}研究会话`, filter ? '试试不同的关键词。' : view === 'deleted' ? '删除的会话会在这里保留 30 天。' : modeLabel ? `从 ${modeLabel} 开始研究后，会话会自动保留。` : '从 FinGPT 或 Claw 开始，研究历史会自动保留。');
  if (view === 'deleted') {
    return `<div class="history-list deleted-history">${visible.map((session) => `<article class="history-row deleted-row"><span class="session-mark ${session.mode === 'claw' ? 'claw' : ''}">${session.mode === 'claw' ? 'C' : 'F'}</span><div><strong>${e(session.title || '未命名会话')}</strong><span class="muted small">${e(session.mode === 'claw' ? 'Claw · 多 Agent' : 'FinGPT · 即时研究')} · ${e(retentionText(session.purge_at))}</span></div><time>${formatTime(session.deleted_at)}</time><div class="history-actions"><button type="button" class="button small" data-restore-session="${e(session.id)}">恢复</button><button type="button" class="button small danger-outline" data-purge-session="${e(session.id)}">永久删除</button></div></article>`).join('')}</div>`;
  }
  return `<div class="history-list">${visible.map((session) => `<article class="history-row"><a class="history-link" href="${sessionHash(session)}"><span class="session-mark ${session.mode === 'claw' ? 'claw' : ''}">${session.mode === 'claw' ? 'C' : 'F'}</span><div><strong>${e(session.title || '未命名会话')}</strong><span class="muted small">${e(session.mode === 'claw' ? 'Claw · 多 Agent' : 'FinGPT · 即时研究')}${session.model ? ` · ${e(session.model)}` : ''}</span>${session.history_warning ? `<span class="session-history-warning small" role="status">历史受限：${e(session.history_warning)}</span>` : ''}</div>${badge(session.status)}<time>${formatTime(session.updated_at)}</time><span aria-hidden="true">↗</span></a><div class="history-actions"><button type="button" class="button small" data-rename-history="${e(session.id)}" title="重命名">重命名</button><button type="button" class="button small danger-outline" data-delete-history="${e(session.id)}" title="移至已删除">删除</button></div></article>`).join('')}</div>`;
}

function retentionText(value) {
  const deadline = new Date(value).getTime();
  if (!Number.isFinite(deadline)) return '删除期限未知';
  const remaining = Math.max(0, deadline - Date.now());
  const days = Math.ceil(remaining / 86400000);
  return days > 0 ? `${days} 天后永久删除` : '等待永久删除';
}

function formatTime(value) {
  if (!value) return '时间未知';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '时间未知' : e(date.toLocaleString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }));
}

function matchesLocalGateway(endpoint) {
  try {
    const address = new URL(endpoint); const gateway = new URL(localModels.gateway);
    return ['http:', 'https:'].includes(address.protocol) && address.protocol === gateway.protocol &&
      ['127.0.0.1', 'localhost', '[::1]'].includes(address.hostname) && !address.username && !address.password &&
      address.port === gateway.port && address.pathname.replace(/\/$/, '') === gateway.pathname.replace(/\/$/, '') &&
      !address.search && !address.hash;
  } catch { return false; }
}

export function modelGroups(groups = [], endpoint = '') {
  const presets = Array.isArray(localModels.models) ? localModels.models.filter(model =>
    typeof model?.id === 'string' && /^[a-zA-Z0-9._:/-]{1,100}$/.test(model.id) && typeof model.name === 'string') : [];
  const expanded = groups.map(group => {
    if (!matchesLocalGateway(endpoint) || group.provider !== 'openai-compatible' || localModels.provider !== group.provider ||
        !(group.models || []).some(model => presets.some(preset => preset.id === model.id))) return group;
    const models = new Map(presets.map(model => [model.id, model]));
    for (const model of group.models || []) if (!models.has(model.id)) models.set(model.id, model);
    return { ...group, models: [...models.values()] };
  });
  return expanded;
}

export function modelOptions(groups = [], current = '', endpoint = '') {
  return '<option value="">选择运行模型</option>' + modelGroups(groups, endpoint).map((group) => `<optgroup label="${e(group.provider)}">${(group.models || []).map((model) => `<option value="${e(JSON.stringify({ provider: group.provider, model: model.id }))}" ${model.id === current ? 'selected' : ''}>${e(model.name || model.id)}</option>`).join('')}</optgroup>`).join('');
}
