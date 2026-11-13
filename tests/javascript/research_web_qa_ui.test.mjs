import assert from 'node:assert/strict';
import test from 'node:test';
import { parseRoute, sessionHash, createController } from '../../app/research_web/ui/core.mjs';
import { fingptReplacement, isQASession, isSpecialistSession, qaEnabled, visibleResearchSessions } from '../../app/research_web/ui/qa-navigation.mjs';
import { renderComposer } from '../../app/research_web/ui/composer.mjs';
import { renderPrimaryRail } from '../../app/research_web/ui/shell.mjs';
import { projectTurns } from '../../app/research_web/qa_frontend/lib/aiStream.ts';

const legacy = { id: 'legacy', mode: 'fingpt', research_mode: 'deep' };
const qa = { id: 'qa', mode: 'fingpt', research_mode: 'deep', execution_engine: 'alphadesk' };
const specialist = { id: 'specialist', mode: 'fingpt', research_mode: 'specialist', execution_engine: 'dsh' };
const claw = { id: 'claw', mode: 'claw' };

test('activation replaces the rail and hides retired FinGPT history while retaining professional collaboration', () => {
  assert.equal(qaEnabled(undefined), false);
  assert.match(renderPrimaryRail(), /href="#\/fingpt"/);
  assert.equal(qaEnabled({ execution_engine: 'alphadesk' }), true);
  const rail = renderPrimaryRail({ route: { page: 'qa' }, qaEnabled: true });
  assert.match(rail, /href="#\/qa".*?aria-current="page"/);
  assert.match(rail, /FinGPT/);
  assert.match(rail, /href="#\/specialist"/);
  assert.doesNotMatch(rail, /href="#\/fingpt"/);
  assert.deepEqual(visibleResearchSessions([legacy, qa, specialist, claw], true), [qa, specialist, claw]);
});

test('legacy links resolve to the new chat or the correct accessible session', () => {
  assert.equal(fingptReplacement(legacy, 'legacy'), '#/qa');
  assert.equal(fingptReplacement(qa, 'qa'), '#/qa?session=qa');
  assert.equal(fingptReplacement(specialist, 'specialist'), '#/specialist?session=specialist');
  assert.deepEqual(parseRoute(sessionHash(qa)), { page: 'qa', sessionId: 'qa' });
  assert.deepEqual(parseRoute(sessionHash(specialist)), { page: 'specialist', sessionId: 'specialist' });
  assert.equal(isQASession(specialist), false);
  assert.equal(isSpecialistSession(qa), false);
});

test('QA uses the existing composer and specialist creation retains budget confirmation', async () => {
  const markup = renderComposer({ page: 'qa', draft: '问题', researchMode: 'deep' });
  assert.match(markup, /id="composer"/);
  assert.match(markup, /添加附件/);
  assert.doesNotMatch(markup, /id="research-depth"/);
  assert.doesNotMatch(markup, /FinGPT/);
  const requests = [];
  const controller = createController({ api: { create: payload => { requests.push(payload); return specialist; } } });
  await controller.open(parseRoute('#/specialist'));
  assert.equal(controller.state.researchMode, 'specialist');
  assert.match(renderComposer({ page: 'specialist', researchMode: controller.state.researchMode, draft: '' }), /预算/);
  assert.equal(await controller.create('fingpt'), null);
  assert.deepEqual(requests, []);
});

test('duplicate stream sequences do not duplicate answer text and a new turn clears the old status', () => {
  const events = [
    { seq: 1, event: 'question', data: { content: '第一轮', mode: 'deep' } },
    { seq: 2, event: '_qa', data: { content: '部分答案' } },
    { seq: 2, event: '_qa', data: { content: '部分答案' } },
    { seq: 3, event: 'task_end', data: { status: 'interrupted' } },
    { seq: 4, event: 'question', data: { content: '下一轮', mode: 'agent' } },
    { seq: 5, event: 'update', data: { id: 'work_note', content: { title: '真实笔记', body: '笔记正文' } } },
    { seq: 6, event: '_qa', data: { content: '下一轮答案 [S1]' } },
    { seq: 7, event: 'answer_source', data: { content: [{ id: 'S1', title: '原件', asof: '2026-11-13' }] } },
    { seq: 8, event: 'task_end', data: { status: 'completed' } },
  ];
  const [first, second] = projectTurns(events, '测试模型');
  assert.equal(first.ai.message, '部分答案');
  assert.equal(first.ai.generating, false);
  assert.match(first.ai.error, /中断/);
  assert.equal(second.ai.message, '下一轮答案 [S1]');
  assert.equal(second.ai.notes[0].title, '真实笔记');
  assert.equal(second.ai.sources[0].title, '原件');
  assert.equal(second.ai.error, undefined);
});

test('a restored interrupted snapshot settles a running turn even when there is no terminal event', () => {
  const events = [{ seq: 1, event: 'question', data: { content: '部分研究', mode: 'agent' } }];
  const [turn] = projectTurns(events, '模型', 'interrupted');
  assert.equal(turn.ai.generating, false);
  assert.match(turn.ai.error, /中断/);
});
