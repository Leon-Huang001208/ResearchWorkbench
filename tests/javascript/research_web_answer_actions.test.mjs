import test from 'node:test';
import assert from 'node:assert/strict';
import { renderClawAnswerActions, downloadAnswer } from '../../app/research_web/ui/answer-actions.mjs';
import { renderConversation } from '../../app/research_web/ui/views.mjs';
const detail = { id:'s', mode:'claw', status:'completed', messages:[{ role:'user', text:'研究', seq:1 }, { role:'assistant', text:'中间说明', seq:2 }, { role:'assistant', text:'最终回答', seq:3 }] };
test('final-only toolbar has six quiet entries and safe disabled retry', () => {
  const html = renderConversation(detail, new Map(), { retryAllowed:false });
  assert.equal((html.match(/aria-label="最终回答操作"/g) || []).length, 1);
  assert.match(html, /data-copy-message="2"/); assert.doesNotMatch(html, /data-copy-message="1"/);
  for (const action of ['share','download','retry','sources','process','files']) assert.match(html, new RegExp(`data-claw-answer-action="${action}"`));
  assert.match(html, /以同样问题重新研究[^>]+disabled/);
  assert.doesNotMatch(renderConversation({...detail,status:'running'}), /最终回答操作/);
  assert.match(renderClawAnswerActions({...detail,id:'<img>'},2), /&lt;img&gt;/);
});
test('download emits exact Markdown and handles unavailable browser operations', () => {
  let clicked = false; let removed = false; let blob;
  downloadAnswer('# 原始回复', {document:{createElement:()=>({click(){clicked=true;},remove(){removed=true;}}),body:{append(){}}},urls:{createObjectURL(value){blob=value;return 'blob:test';},revokeObjectURL(){}},logger(){} });
  assert.equal(clicked,true); assert.equal(removed,true); assert.equal(blob.type,'text/markdown;charset=utf-8');
  assert.throws(()=>downloadAnswer('',{logger(){}}),/下载失败/);
});
test('answer toolbar has no speech action', () => { assert.doesNotMatch(renderClawAnswerActions(detail,2), /speak|朗读|speaker|回答反馈|thumbUp|thumbDown|data-claw-answer-action="(?:good|bad)"/); });
