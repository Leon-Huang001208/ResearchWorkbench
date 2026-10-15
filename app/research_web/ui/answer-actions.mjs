import { escapeHTML as e } from './markdown.mjs';
import { icon } from './icons.mjs';
import { safeLog } from './core.mjs';

export function renderClawAnswerActions(detail, index, options = {}) {
  const message = detail.messages[index];
  const key = message.id || `${detail.id}:${index}`;
  const feedback = options.feedback?.[key];
  const button = (action, label, glyph, extra = '') => `<button type="button" class="claw-answer-action" data-claw-answer-action="${action}" data-answer-index="${index}" data-answer-session="${e(detail.id || '')}" aria-label="${e(label)}" title="${e(label)}" ${extra}>${icon(glyph)}</button>`;
  const copy = `<button type="button" class="claw-answer-action" data-copy-message="${index}" data-copy-session="${e(detail.id || '')}" aria-label="复制回复" title="复制回复">${icon('copy')}</button>`;
  const previousUser = detail.messages.slice(0, index).findLast(item => item.role === 'user');
  return `<div class="claw-answer-actions" role="group" aria-label="最终回答操作">${copy}<details class="claw-answer-menu" data-disclosure-key="${e(`${detail.id}:feedback:${index}`)}"><summary aria-label="回答反馈" title="回答反馈">${icon(feedback === 'bad' ? 'thumbDown' : 'thumbUp')}</summary><div class="claw-answer-menu-items">${button('good', '有用（仅本页记录）', 'thumbUp', `aria-pressed="${feedback === 'good'}"`)}${button('bad', '没用（仅本页记录）', 'thumbDown', `aria-pressed="${feedback === 'bad'}"`)}</div></details>${button('share', '复制本机会话链接', 'share')}${button('download', '下载本条回复为 Markdown', 'document')}${button('speak', '朗读或停止朗读（本机语音）', 'speaker')}${button('retry', '以同样问题重新研究', 'restore', options.retryAllowed === false || detail.execution_restricted || !previousUser ? 'disabled' : '')}<details class="claw-answer-menu" data-disclosure-key="${e(`${detail.id}:more:${index}`)}"><summary aria-label="更多回答操作" title="更多">${icon('more')}</summary><div class="claw-answer-menu-items">${button('process', '查看执行过程', 'terminal')}${button('files', '查看会话文件', 'folder')}</div></details>${button('sources', '查看资料与来源', 'book')}</div>`;
}

export function downloadAnswer(text, { document: doc = globalThis.document, urls = globalThis.URL, logger = safeLog } = {}) {
  let url;
  let link;
  try {
    if (typeof text !== 'string' || !text.trim()) throw new Error('empty_answer');
    url = urls.createObjectURL(new Blob([text], { type: 'text/markdown;charset=utf-8' }));
    link = doc.createElement('a'); link.href = url; link.download = 'research-answer.md';
    doc.body.append(link); link.click(); logger('claw_answer_downloaded');
  } catch {
    logger('claw_answer_download_failed'); throw new Error('下载失败，请使用复制回复保存正文。');
  } finally {
    link?.remove(); if (url) setTimeout(() => urls.revokeObjectURL(url), 1000);
  }
}

export function speakAnswer(text, { synthesis = globalThis.speechSynthesis, Utterance = globalThis.SpeechSynthesisUtterance, logger = safeLog, onError = () => {} } = {}) {
  try {
    if (!synthesis || !Utterance) throw new Error('speech_unavailable');
    if (synthesis.speaking || synthesis.pending) { synthesis.cancel(); logger('claw_answer_speech_stopped'); return; }
    const voices = synthesis.getVoices().filter(voice => voice.localService === true);
    const voice = voices.find(item => /^zh/i.test(item.lang)) || voices[0];
    if (!voice) throw new Error('local_voice_unavailable');
    const utterance = new Utterance(text); utterance.voice = voice; utterance.lang = voice.lang;
    utterance.onerror = event => {
      if (['canceled', 'interrupted'].includes(event?.error)) { logger('claw_answer_speech_stopped'); return; }
      logger('claw_answer_speech_failed'); onError('本机朗读失败，请检查系统语音设置。');
    };
    synthesis.speak(utterance); logger('claw_answer_speech_started');
  } catch {
    logger('claw_answer_speech_unavailable'); throw new Error('浏览器尚无可用的本机语音，暂时无法朗读。');
  }
}
