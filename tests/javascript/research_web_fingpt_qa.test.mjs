import test from 'node:test';
import assert from 'node:assert/strict';
import { renderQAAnswer, answerFromRound, renderMigratedTasks, TASK_PRESETS } from '../../app/research_web/ui/fingpt.mjs';

test('SSE answer projection keeps sources and completes all three modes',()=>{
 for(const mode of ['quick','deep','agent']){
  const round={mode,tier:'lite',status:'completed',events:[{event:'_qa',data:{content:'# 报告\n证据[S1]'}},{event:'answer_source',data:{content:[{id:'S1',title:'来源'}]}},{event:'update',data:{id:'_final',content:{elapsed_ms:1}}}]};
  const m=answerFromRound(round);assert.equal(m.sources.length,1);assert.equal(m.generating,false);
  const html=renderQAAnswer(m,'test');assert.match(html,/data-doc-ref="1"/);assert.match(html,/重试/);assert.match(html,/复制/);
  if(mode==='agent')assert.match(html,/最终报告/);
 }
});
test('rendered research never executes provider text as HTML',()=>{
 const m=answerFromRound({mode:'quick',status:'completed',events:[{event:'_qa',data:{content:'<script>alert(1)</script> [恶意](javascript:alert(1))'}}]});
 const html=renderQAAnswer(m,'test');assert(!html.includes('<script>'));assert(!html.includes('href="javascript:'));
});
test('task presets belong to the Claw task shelf rather than a fourth FinGPT mode',()=>{
 assert.equal(TASK_PRESETS.length,3);const html=renderMigratedTasks();assert.match(html,/Claw/);assert.match(html,/data-fq-task="0"/);assert(!html.includes('data-fq-mode="task"'));
});

test('agent mode shows the same live thinking panel as quick mode',()=>{
 const m=answerFromRound({mode:'agent',tier:'lite',status:'running',events:[
  {event:'update',data:{id:'intro',content:'收到需求'}},
  {event:'update',data:{id:'sub_question_list',content:[{id:1,question:'子任务一'}]}},
  {event:'update',data:{id:'plans',content:[{id:1,question:'子任务一'}]}},
  {event:'step_start',data:{id:'sub_question_start',sub_id:1,content:'检索中'}},
  {event:'update',data:{id:'sub_question_cot',sub_id:1,content:'子任务推理全文'}},
  {event:'_cot',data:{content:'主推理全文'}}]});
 const open=renderQAAnswer(m,'round-1',{thinking:true});
 assert.match(open,/data-fq-think="round-1"/);
 assert.match(open,/主推理全文/);
 assert.match(open,/子任务推理全文/);
 assert.match(open,/任务运行中/);
 assert.equal((open.match(/data-fq-think/g)||[]).length,1);
 const closed=renderQAAnswer(m,'round-1',{thinking:false});
 assert(!closed.includes('主推理全文'));
 assert.match(closed,/思考分析/);
});

test('finished sub-task reasoning stays available instead of disappearing',()=>{
 const events=[{event:'update',data:{id:'sub_question_list',content:[{id:1,question:'子任务一'}]}},{event:'update',data:{id:'plans',content:[{id:1,question:'子任务一'}]}},{event:'step_start',data:{id:'sub_question_start',sub_id:1,content:'检索中'}},{event:'update',data:{id:'sub_question_cot',sub_id:1,content:'子任务推理全文'}},{event:'update',data:{id:'work_note',sub_id:1,content:{title:'笔记',body:'结论'}}},{event:'update',data:{id:'sub_question_done',sub_id:1,content:'结论'}}];
 const html=renderQAAnswer(answerFromRound({mode:'agent',tier:'lite',status:'running',events}),'round-2',{thinking:false});
 assert.match(html,/fq-subcot/);
 assert.match(html,/子任务推理全文/);
});
