import test from 'node:test';
import assert from 'node:assert/strict';
import { ensureQuestionState, questionStateKey, captureQuestionForm, actionQuestion, collectQuestionGroup, renderPendingQuestion, QUESTION_SKIPPED } from '../../app/research_web/ui/questionnaire.mjs';
import { renderConversation } from '../../app/research_web/ui/views.mjs';

const question = () => ({ id: 'call', seq: 3, items: [
  { id: 'scope', question: '选择范围', options: [{ label: '公开资料（推荐）', description: '公开可查' }, { label: '全部资料' }] },
  { id: 'outputs', question: '选择产物', multiSelect: true, options: [{ label: 'Word' }, { label: 'PDF' }] },
] });
function capture(drafts, q, selected = [], custom = '') {
  const index = ensureQuestionState(drafts, 's', q).index;
  const values = new FormData();
  for (const label of selected) values.append(`selection-${index}`, label);
  values.set(`custom-${index}`, custom);
  return captureQuestionForm({ dataset: { questionForm: q.id, qIndex: String(index) } }, drafts, 's', q, { values });
}

test('page switching and refreshed projections preserve all drafts without mutating native questions', () => {
  const drafts = new Map(), q = question(), before = structuredClone(q);
  capture(drafts, q, ['全部资料'], '中文输入中');
  actionQuestion(drafts, 's', q, 'next');
  capture(drafts, q, ['Word', 'PDF']);
  actionQuestion(drafts, 's', structuredClone(q), 'prev');
  assert.deepEqual(collectQuestionGroup(drafts, 's', q), [{ id: 'scope', selected: ['全部资料'], custom: '中文输入中' }, { id: 'outputs', selected: ['Word', 'PDF'], custom: '' }]);
  assert.deepEqual(q, before);
  assert.equal(ensureQuestionState(drafts, 's', q).index, 0);
  assert.deepEqual(ensureQuestionState(drafts, 'different-session', q).items, []);
  assert.notEqual(questionStateKey('s', q.id), questionStateKey('different-session', q.id));
});

test('closing only folds; explicit skip clears only the active item and never implicitly submits', () => {
  const drafts = new Map(), q = question();
  capture(drafts, q, ['全部资料']);
  actionQuestion(drafts, 's', q, 'next');
  capture(drafts, q, ['PDF'], '补充');
  actionQuestion(drafts, 's', q, 'close');
  assert.match(renderPendingQuestion(q, ensureQuestionState(drafts, 's', q)), /继续回答/);
  assert.doesNotMatch(renderPendingQuestion(q, ensureQuestionState(drafts, 's', q)), /<textarea|type="submit"/);
  capture(drafts, q);
  actionQuestion(drafts, 's', q, 'open');
  assert.deepEqual(collectQuestionGroup(drafts, 's', q)[1], { id: 'outputs', selected: ['PDF'], custom: '补充' });
  actionQuestion(drafts, 's', q, 'skip');
  assert.deepEqual(collectQuestionGroup(drafts, 's', q), [{ id: 'scope', selected: ['全部资料'], custom: '' }, { id: 'outputs', selected: [], custom: QUESTION_SKIPPED }]);
  capture(drafts, q, ['PDF'], QUESTION_SKIPPED);
  assert.deepEqual(collectQuestionGroup(drafts, 's', q)[1], { id: 'outputs', selected: ['PDF'], custom: '' });
});

test('no recommended defaults or automatic skip; single choice validation survives submission', () => {
  const drafts = new Map(), q = question();
  const state = ensureQuestionState(drafts, 's', q);
  assert.throws(() => collectQuestionGroup(drafts, 's', q), /尚未回答/);
  assert.doesNotMatch(renderPendingQuestion(q, state), / checked|type="submit"/);
  assert.throws(() => capture(drafts, q, ['全部资料', '公开资料（推荐）']), /单选/);
  assert.throws(() => capture(drafts, q, ['伪造选项']), /选项/);
  capture(drafts, q, [], '自己的回答');
  actionQuestion(drafts, 's', q, 'next');
  assert.match(renderPendingQuestion(q, state), /type="submit"/);
  assert.doesNotMatch(renderPendingQuestion(q, state), /选择范围/);
});

test('both modes render one native question, session-specific drafts and confirmed read-only history', () => {
  for (const mode of ['fingpt', 'claw']) {
    const drafts = new Map(), q = question();
    capture(drafts, q, [], '尚未提交');
    const pending = renderConversation({ id: 's', mode, messages: [], questions: [q] }, drafts);
    assert.match(pending, /正在询问问题/); assert.match(pending, /正在等待你的回答/);
    assert.match(pending, /尚未提交/); assert.doesNotMatch(pending, /选择产物|已询问/);
    const historical = renderConversation({ id: 's', mode, messages: [], question_history: [{ ...q, answers: [{ id: 'scope', selected: [], custom: QUESTION_SKIPPED }] }] }, drafts);
    assert.match(historical, /已询问 2 个问题/); assert.match(historical, /用户跳过，未提供答案/);
    assert.match(historical, /未记录回答/); assert.doesNotMatch(historical, /<form|<textarea|尚未提交/);
  }
});

test('HTML escaping covers native options, custom text, labels and event identities', () => {
  const html = renderPendingQuestion({ id: '"><img>', items: [{ question: '<script>', options: [{ label: '<svg>', description: '<img>' }] }] }, [{ selected: ['<svg>'], custom: '</textarea><script>' }]);
  assert.doesNotMatch(html, /<script>|<img>|<svg>/);
  assert.match(html, /&lt;svg&gt;/); assert.match(html, /&lt;\/textarea&gt;/);
});


test('pending research hides the removed caption while send guards remain active', async () => {
  const { renderComposer } = await import('../../app/research_web/ui/composer.mjs');
  for (const page of ['claw', 'fingpt']) {
    const html = renderComposer({ page, draft: '保留草稿', taskPending: true, detail: { status: 'completed' } });
    assert.doesNotMatch(html, /上一任务及其交付尚未确认结束/);
    assert.doesNotMatch(html, /<p class="composer-caption[^>]*><\/p>/);
    assert.match(html, /type="submit"[^>]*composer-send[^>]*disabled/);
  }
});
