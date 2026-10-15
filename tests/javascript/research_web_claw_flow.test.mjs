import test from 'node:test';
import assert from 'node:assert/strict';
import { renderConversation } from '../../app/research_web/ui/views.mjs';

const activity = (id, seq, extra = {}) => ({ id, seq, type: 'tool', tool: 'research_run_script', title: 'research_run_script', status: 'completed', arguments: { code: 'print("ok")\nprint(2)' }, result: { stdout: 'ok\n2', exit_code: 0 }, duration_ms: 173, ...extra });
test('Claw process stays chronological, exposes real code and keeps final answer outside disclosure', () => {
  const html = renderConversation({ id: 's', mode: 'claw', status: 'completed', duration_ms: 99999, messages: [{ id: 'u', seq: 1, role: 'user', text: '输入' }, { id: 'a', seq: 2, role: 'assistant', text: '阶段说明' }, { id: 'f', seq: 5, role: 'assistant', text: '最终回答' }], activities: [activity('t', 3)] });
  assert.match(html, /class="claw-process"/);
  assert.match(html, /class="claw-step"/);
  assert.match(html, /print\(&quot;ok&quot;\)\nprint\(2\)/);
  assert.match(html, /退出码 0/);
  assert.match(html, /173ms/);
  assert.doesNotMatch(html, /99999|思考了/);
  assert.ok(html.indexOf('阶段说明') < html.indexOf('运行 Python 脚本'));
  assert.ok(html.indexOf('</details><article class="message assistant"') > html.indexOf('运行 Python 脚本'));
  assert.match(html, /data-disclosure-key="s:tool:t"/);
});
test('Claw process never hides pending decisions and preserves unknown positions separately', () => {
  const html = renderConversation({ id: 's', mode: 'claw', status: 'waiting_input', messages: [{ role: 'assistant', seq: 1, text: '先解释' }, { role: 'assistant', seq: 7, text: '继续解释' }], questions: [{ id: 'q', seq: 3, items: [{ id: 'x', question: '确认范围' }] }], activities: [activity('a', 2), activity('b', 5), activity('unknown', undefined)] });
  assert.ok(html.indexOf('先解释') < html.indexOf('确认范围'));
  assert.ok(html.indexOf('确认范围') < html.indexOf('继续解释'));
  assert.match(html, /<\/details><form class="decision-card question-form"/);
  assert.match(html, /缺少原生事件位置/);
  assert.doesNotMatch(html, /执行已完成|思考了/);
});
test('Claw disclosures are scoped to session and failed status is visible when closed', () => {
  const detail = { id: 'one', mode: 'claw', status: 'failed', messages: [], activities: [activity('bad', 1, { status: 'failed', error: '<denied>', result: { exit_code: 1 } })] };
  const html = renderConversation(detail);
  assert.match(html, /失败/); assert.match(html, /&lt;denied&gt;/); assert.match(html, /退出码 1/);
  assert.match(html, /one:tool:bad/);
  assert.match(renderConversation({ ...detail, id: 'two' }), /two:tool:bad/);
  assert.doesNotMatch(renderConversation({ ...detail, mode: 'fingpt' }), /claw-step|claw-process/);
});
