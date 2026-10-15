import test from 'node:test';
import assert from 'node:assert/strict';
import { renderClawAnswerActions, downloadAnswer, speakAnswer } from '../../app/research_web/ui/answer-actions.mjs';
import { renderConversation } from '../../app/research_web/ui/views.mjs';
const detail = { id:'s', mode:'claw', status:'completed', messages:[{ role:'user', text:'研究', seq:1 }, { role:'assistant', text:'中间说明', seq:2 }, { role:'assistant', text:'最终回答', seq:3 }] };
test('final-only toolbar has eight quiet entries and safe disabled retry', () => {
  const html = renderConversation(detail, new Map(), { retryAllowed:false });
  assert.equal((html.match(/aria-label="最终回答操作"/g) || []).length, 1);
  assert.match(html, /data-copy-message="2"/); assert.doesNotMatch(html, /data-copy-message="1"/);
  for (const action of ['share','download','speak','retry','sources','good','bad','process','files']) assert.match(html, new RegExp(`data-claw-answer-action="${action}"`));
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
test('speech requires a local voice, supports stop, and surfaces asynchronous failure', () => {
  let utterance; let stopped=false; let error='';
  class Utterance { constructor(text){this.text=text;} }
  const synthesis={ getVoices:()=>[{localService:false,lang:'zh-CN'},{localService:true,lang:'zh-CN'}],speak(value){utterance=value;},cancel(){stopped=true;} };
  speakAnswer('正文',{synthesis,Utterance,logger(){},onError(value){error=value;}});
  assert.equal(utterance.voice.localService,true); assert.equal(utterance.text,'正文'); utterance.onerror(); assert.match(error,/朗读失败/);
  error=''; synthesis.cancel=()=>{stopped=true;utterance.onerror({error:'canceled'});};
  synthesis.speaking=true; speakAnswer('正文',{synthesis,Utterance,logger(){}}); assert.equal(stopped,true); assert.equal(error,'');
  utterance.onerror({error:'interrupted'}); assert.equal(error,'');
  assert.throws(()=>speakAnswer('正文',{synthesis:{getVoices:()=>[]},Utterance,logger(){}}),/本机语音/);
});
