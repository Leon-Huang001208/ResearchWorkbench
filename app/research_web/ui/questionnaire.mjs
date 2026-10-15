import { icon } from './icons.mjs';
import { escapeHTML as e, renderMarkdown } from './markdown.mjs';
import { safeLog } from './core.mjs';

export const QUESTION_SKIPPED = '用户跳过，未提供答案';
export const questionStateKey = (sessionId, questionId) => JSON.stringify([String(sessionId || ''), String(questionId || '')]);

// UI state only: native questions/history remain authoritative and untouched.
export function ensureQuestionState(drafts, sessionId, question) {
  if (!(drafts instanceof Map) || !question?.id) throw new Error('问题草稿身份不可用。');
  const key = questionStateKey(sessionId, question.id);
  let state = drafts.get(key);
  if (!state) {
    const legacy = drafts.get(question.id);
    state = { items: Array.isArray(legacy) ? legacy.map(item => ({ ...item, selected: [...(item.selected || [])] })) : [], index: 0, collapsed: false };
    if (Array.isArray(legacy)) drafts.delete(question.id);
    drafts.set(key, state);
  }
  const count = Array.isArray(question.items) ? question.items.length : 0;
  state.index = Math.max(0, Math.min(Number.isInteger(state.index) ? state.index : 0, Math.max(0, count - 1)));
  return state;
}

export function captureQuestionForm(form, drafts, sessionId, question, { values } = {}) {
  const state = ensureQuestionState(drafts, sessionId, question);
  if (!form || form.dataset?.questionForm !== String(question.id)) throw new Error('问题表单已变化，请重新核对。');
  // Folded cards have no answer controls; reopening must never erase the draft.
  if (state.collapsed) return state;
  const index = Number(form.dataset.qIndex ?? state.index);
  if (index !== state.index || !question.items?.[index]) return state;
  const data = values || new FormData(form);
  const item = question.items[index];
  const selected = data.getAll(`selection-${index}`).filter(value => typeof value === 'string');
  const labels = new Set((item.options || []).map(option => option.label));
  if (selected.some(value => !labels.has(value)) || (item.multiSelect !== true && selected.length > 1)) {
    safeLog('question_draft_invalid');
    throw new Error('问题选项已变化或单选题选择超过一项，请重新核对。');
  }
  let custom = String(data.get(`custom-${index}`) || '').slice(0, 10000);
  const previous = state.items[index];
  if (previous?.skipped && selected.length && custom === QUESTION_SKIPPED) custom = '';
  state.items[index] = { selected: [...new Set(selected)], custom, skipped: !selected.length && custom === QUESTION_SKIPPED && previous?.skipped === true };
  return state;
}

export function actionQuestion(drafts, sessionId, question, action) {
  const state = ensureQuestionState(drafts, sessionId, question);
  const last = Math.max(0, (question.items?.length || 0) - 1);
  if (action === 'close') state.collapsed = true;
  else if (action === 'open') state.collapsed = false;
  else if (action === 'prev') state.index = Math.max(0, state.index - 1);
  else if (action === 'next') state.index = Math.min(last, state.index + 1);
  else if (action === 'skip') {
    state.items[state.index] = { selected: [], custom: QUESTION_SKIPPED, skipped: true };
    state.index = Math.min(last, state.index + 1);
    safeLog('question_explicitly_skipped');
  } else throw new Error('未知问题操作。');
  return state;
}

export function collectQuestionGroup(drafts, sessionId, question) {
  const state = ensureQuestionState(drafts, sessionId, question);
  return (question.items || []).map((item, index) => {
    const draft = state.items[index] || {};
    const selected = Array.isArray(draft.selected) ? [...draft.selected] : [];
    const custom = typeof draft.custom === 'string' ? draft.custom : '';
    if (!selected.length && !custom.trim()) throw new Error(`第 ${index + 1} 个问题尚未回答，请回答或明确跳过。`);
    if (item.multiSelect !== true && selected.length > 1) throw new Error('单选题只能选择一项。');
    const labels = new Set((item.options || []).map(option => option.label));
    if (selected.some(value => !labels.has(value))) throw new Error('问题选项已变化，请重新核对。');
    return { id: item.id, selected, custom };
  });
}

export function renderPendingQuestion(question, draft = [], { sessionId = '' } = {}) {
  const state = Array.isArray(draft) ? { items: draft, index: 0, collapsed: false } : draft;
  const items = Array.isArray(question.items) ? question.items : [];
  const index = Math.max(0, Math.min(state.index || 0, Math.max(0, items.length - 1)));
  const item = items[index]; const answer = state.items?.[index] || {};
  const identity = `data-question-form="${e(question.id)}" data-q-session="${e(sessionId)}" data-q-index="${index}"`;
  const status = `<div class="codex-question-status"><span aria-hidden="true">${icon('question')}</span><span>正在询问问题</span></div><div class="codex-question-waiting"><span aria-hidden="true">${icon('listChecks')}</span><span>正在等待你的回答</span></div>`;
  if (state.collapsed) return `<form class="decision-card question-form" ${identity}>${status}<div class="codex-question-folded"><button type="button" class="text-button" data-q-open="${e(question.id)}">继续回答</button></div></form>`;
  const pager = `<span class="codex-question-pager" role="group" aria-label="切换问题"><button type="button" class="codex-question-arrow" data-q-page="prev" aria-label="上一题" ${index === 0 ? 'disabled' : ''}>${icon('chevronLeft')}</button><span class="codex-question-count">${items.length ? index + 1 : 0} of ${items.length}</span><button type="button" class="codex-question-arrow" data-q-page="next" aria-label="下一题" ${index >= items.length - 1 ? 'disabled' : ''}>${icon('chevronRight')}</button><button type="button" class="codex-question-close" data-q-close="${e(question.id)}" aria-label="收起问题，保留未提交回答" title="收起问题">${icon('close')}</button></span>`;
  const customId = `question-${encodeURIComponent(question.id)}-${index}`;
  const body = item ? `<fieldset><legend class="codex-question-title" tabindex="-1"><span>${e(item.question || '')}${item.multiSelect === true ? '<small class="codex-question-multiple">可多选</small>' : ''}</span>${pager}</legend><div class="codex-question-options">${(item.options || []).map((option, optionIndex) => {
    const recommended = option.recommended === true || /(?:[（(]推荐[）)]|[（(]Recommended[）)])/i.test(option.label || '');
    const label = String(option.label || '').replace(/\s*[（(](?:推荐|Recommended)[）)]\s*/ig, '').trim();
    const checked = answer.selected?.includes(option.label);
    return `<div class="codex-question-option-row"><label class="codex-question-option"><input type="${item.multiSelect === true ? 'checkbox' : 'radio'}" name="selection-${index}" value="${e(option.label)}" ${checked ? 'checked' : ''}><span class="codex-question-number" aria-hidden="true">${optionIndex + 1}</span><span class="question-option-copy"><strong>${e(label)}${recommended ? '<span class="codex-question-recommended">推荐</span>' : ''}</strong>${option.description ? `<span class="muted">${e(option.description)}</span>` : ''}</span></label>${index < items.length - 1 ? '<button type="button" class="codex-option-forward" data-q-page="next" aria-label="选择并继续">'+icon('arrowRight')+'</button>' : ''}</div>`;
  }).join('')}</div>${answer.skipped ? '<p class="muted small codex-question-skipped">本题已明确跳过，可重新作答。</p>' : ''}</fieldset>` : `<div class="markdown">${renderMarkdown(question.text || '')}</div>`;
  return `<form class="decision-card question-form" ${identity}>${status}<section class="codex-question">${body}<footer class="codex-question-footer"><label class="codex-question-custom" for="${e(customId)}"><span aria-hidden="true">${icon('pencil')}</span><span class="sr-only">自己的回答或补充说明</span><textarea id="${e(customId)}" name="custom-${index}" maxlength="10000" rows="1" placeholder="补充你的回答，或说明你希望如何调整…">${e(answer.custom || '')}</textarea></label><div class="codex-question-submit"><button type="button" class="button ghost" data-q-skip="${e(question.id)}" aria-label="跳过此题" ${!item ? 'disabled' : ''}>跳过</button>${index >= items.length - 1 ? '<button type="submit" class="button primary">提交回答</button>' : ''}</div></footer></section></form>`;
}

export function renderQuestionHistory(question, sessionId = '') {
  return `<details class="decision-card question-history" data-disclosure-key="${e(`${sessionId}:question:${question.id}`)}" aria-label="已确认的原生提问参数"><summary><span class="question-history-icon" aria-hidden="true">${icon('question')}</span><span>已询问 ${question.items.length} 个问题</span><span class="question-receipt-toggle" aria-hidden="true">${icon('chevron')}</span></summary><dl>${question.items.map((item, index) => {
    const answer = item.id != null ? question.answers.find(value => value.id === item.id) : question.answers[index];
    const selected = Array.isArray(answer?.selected) ? answer.selected.filter(value => typeof value === 'string') : [];
    const custom = typeof answer?.custom === 'string' ? answer.custom : '';
    return `<div><dt>${e(item.question || '')}</dt><dd>${selected.length ? `<p>${selected.map(value => e(value)).join('、')}</p>` : ''}${custom ? `<p>${e(custom)}</p>` : ''}${!selected.length && !custom ? '<p class="muted">未记录回答</p>' : ''}</dd></div>`;
  }).join('')}</dl></details>`;
}
