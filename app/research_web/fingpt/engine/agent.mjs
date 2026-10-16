import { publicData } from './security.mjs';
// Agent 编排：计划 → 工具循环（function calling）→ 反思 → 成稿；以 AlphaEngine 风格 SSE 事件推送
import { chatStream } from './llm.mjs';
import { TOOL_SCHEMAS, TOOL_META, runTool } from './tools.mjs';
import * as P from './prompts.mjs';

const clip = (s, n) => (s.length > n ? s.slice(0, n) + '…（已截断）' : s);
function parseJSON(text) {
  const t = String(text || '').replace(/```(?:json)?/g, '');
  const a = t.indexOf('{'), b = t.lastIndexOf('}');
  if (a < 0 || b <= a) return null;
  try { return JSON.parse(t.slice(a, b + 1)); } catch { return null; }
}
const argText = (a) => Object.values(a || {}).map(v => Array.isArray(v) ? v.join(',') : v).join(', ');

export async function runAgent({ tier, mode, question, history = [], emit, signal }) {
  const t0 = Date.now();
  const ctx = { sources: [], key: new Map(), warnings: [] };
  const send = emit;
  emit = (event, data) => { signal?.throwIfAborted(); send(event, publicData(data)); };
  const session = `s_${t0.toString(36)}${Math.random().toString(36).slice(2, 6)}`;
  emit('setup', { content: session, mode, tier });
  emit('start_of_agent', { agent_name: 'AlphaDesk-Research', mode });

  const addSources = (list = []) => list.map(s => {
    const k = `${s.title}|${s.url}`;
    if (!ctx.key.has(k)) { const id = `S${ctx.sources.length + 1}`; ctx.key.set(k, id); ctx.sources.push({ ...s, id }); }
    return ctx.key.get(k);
  });

  async function execTool(call, subId) {
    const name = call.function.name; let args = {};
    try { args = JSON.parse(call.function.arguments || '{}'); } catch { /* 空参 */ }
    const meta = TOOL_META[name];
    const display = `${meta?.title || name} (${argText(args)})`;
    emit('tool_call', { tool_call_id: call.id, tool_name: name, title: meta?.title || name, group: meta?.group || '工具', args, display, sub_id: subId });
    emit('step_start', { id: '_tool_financial', content: `正在检索 · ${display}`, sub_id: subId });
    const ts = Date.now();
    try {
      const r = await runTool(name, args, { signal });
      for (const warning of r.data?.validation || []) if (warning.status === '口径存疑') ctx.warnings.push(`${warning.metric}：口径存疑；${warning.reason}`);
      const ids = addSources(r.sources);
      const n = Array.isArray(r.data) ? r.data.length : r.data?.rows?.length;
      emit('tool_call_result', { tool_call_id: call.id, tool_name: name, ok: true, ms: Date.now() - ts, summary: `完成检索${n != null ? ` · ${n} 条` : ''}`, source_ids: ids, sources: ids.map(id => ctx.sources.find(s => s.id === id)), sub_id: subId });
      return { ok: true, text: clip(JSON.stringify({ 来源编号: ids, 数据校验: r.data?.validation, 数据: r.data }), 7000), ids };
    } catch (e) {
      signal?.throwIfAborted();
      emit('tool_call_result', { tool_call_id: call.id, tool_name: name, ok: false, ms: Date.now() - ts, summary: `检索失败，请检查数据源或查询条件`, sub_id: subId });
      return { ok: false, text: JSON.stringify({ error: '数据源未返回可用结果，请尝试其他数据源或明确标注暂无数据' }) };
    }
  }

  // 通用工具循环。answerStream=true 时最终内容以 _qa 增量推送
  async function loop(messages, { maxRounds = 4, answerStream = false, subId, cotId = '_cot' }) {
    const cot = (x) => emit(cotId === '_cot' ? '_cot' : 'update', cotId === '_cot' ? { content: x } : { id: cotId, sub_id: subId, content: x });
    for (let round = 0; round <= maxRounds; round++) {
      signal?.throwIfAborted();
      const useTools = round < maxRounds;
      let shown = '';
      const res = await chatStream(tier, {
        messages, tools: useTools ? TOOL_SCHEMAS : undefined, signal, maxTokens: answerStream ? 6000 : 4000,
        onReasoning: (x) => cot(x),
        onContent: (x) => { if (answerStream) { shown += x; emitQa(x); } else cot(x); },
      });
      if (res.tool_calls.length && useTools) {
        if (shown) { emit('update', { id: '_qa_retract', content: shown }); cot(shown); resetQa(); }
        messages.push({ role: 'assistant', content: res.content || '', reasoning_content: res.reasoning || undefined, tool_calls: res.tool_calls });
        const results = await Promise.all(res.tool_calls.map(c => execTool(c, subId)));
        res.tool_calls.forEach((c, i) => messages.push({ role: 'tool', tool_call_id: c.id, name: c.function.name, content: results[i].text }));
        continue;
      }
      messages.push({ role: 'assistant', content: res.content || '' });
      return res.content || '';
    }
    return '';
  }

  // _qa 推送：遇到 <<追问>> 之后截留，用于追问建议
  let qaBuf = '', qaSent = 0;
  const MARK = '<<追问>>';
  function emitQa(x) {
    qaBuf += x;
    const cut = qaBuf.indexOf(MARK);
    const safe = cut >= 0 ? cut : Math.max(qaSent, qaBuf.length - MARK.length);
    if (safe > qaSent) { emit('_qa', { content: qaBuf.slice(qaSent, safe) }); qaSent = safe; }
  }
  function resetQa() { qaBuf = ''; qaSent = 0; }
  function flushQa() {
    const cut = qaBuf.indexOf(MARK);
    if (cut < 0 && qaBuf.length > qaSent) emit('_qa', { content: qaBuf.slice(qaSent) });
    const sug = cut >= 0 ? qaBuf.slice(cut + MARK.length).split(/[|｜\n]/).map(s => s.replace(/^[\s\d.、\-*]+/, '').trim()).filter(Boolean).slice(0, 3) : [];
    return sug;
  }

  const hist = history.slice(-6).map(m => ({ role: m.role === 'user' ? 'user' : 'assistant', content: String(m.content || '').slice(0, 3000) }));
  const sourceList = () => ctx.sources.map(s => `[${s.id}] ${s.title} · ${s.provider} · ${s.asof || ''}`).join('\n') || '（无）';

  async function plan() {
    emit('step_start', { id: 'thinking', content: '思考分析中...' });
    emit('start_of_agent', { agent_name: 'AlphaDesk-Planner' });
    const res = await chatStream(tier, { messages: [{ role: 'system', content: P.PLAN_SYSTEM() }, ...hist, { role: 'user', content: question }], signal, maxTokens: 2000, onReasoning: (x) => emit('_cot', { content: x }) });
    const j = parseJSON(res.content);
    const candidates = Array.isArray(j?.sub_questions) ? j.sub_questions : [];
    const subs = candidates.slice(0, 7).map((s, i) => ({ id: i + 1, question: String(s.question || '').slice(0, 500), tools: Array.isArray(s.tools) ? s.tools.filter(t => TOOL_META[t]) : [] })).filter(s => s.question);
    const fallback = [
      { question: `收集「${question}」的最新行情与估值证据`, tools: ['get_realtime_quote'] },
      { question: `分析「${question}」的财务、行业与事件数据`, tools: ['get_financial_data', 'search_news_notices'] },
      { question: `核查「${question}」的数据口径、风险与结论失效条件`, tools: ['ifind_stock_query'] },
    ];
    while (subs.length < 3) { const s = fallback[subs.length]; subs.push({ id: subs.length + 1, ...s }); }
    return { title: j?.title || question, subs };
  }

  if (mode === 'deep') {
    const { title, subs } = await plan();
    emit('step_start', { id: 'deepsearch_start', content: `深度研究：${title}` });
    emit('update', { id: 'sub_question_list', content: subs.map(s => ({ ...s, state: 'pending' })) });
    const notes = [];
    for (const s of subs) {
      emit('step_start', { id: 'sub_question_start', sub_id: s.id, content: s.question });
      const before = ctx.sources.length;
      const note = await loop([{ role: 'system', content: P.SUBQ_SYSTEM() }, { role: 'user', content: `总问题：${question}\n当前子问题：${s.question}\n已登记来源（不得虚构编号）：\n${sourceList()}\n建议工具：${s.tools.join(',') || '自行判断'}` }], { maxRounds: 3, subId: s.id, cotId: 'sub_question_cot' });
      emit('update', { id: 'sub_question_source', sub_id: s.id, content: ctx.sources.slice(before) });
      emit('update', { id: 'sub_question_done', sub_id: s.id, content: note });
      notes.push(`### 子问题${s.id}：${s.question}\n${note}`);
    }
    emit('step_start', { id: 'report_writing_pre_check', content: '整理研究笔记，制定写作计划' });
    const ol = await chatStream(tier, { messages: [{ role: 'system', content: P.OUTLINE_SYSTEM() }, { role: 'user', content: `问题：${question}\n\n研究笔记：\n${notes.join('\n\n')}` }], signal, maxTokens: 2000, onReasoning: (x) => emit('_cot', { content: x }) });
    const outline = parseJSON(ol.content) || { title, sections: [{ title: '核心结论' }, { title: '数据与分析' }, { title: '风险提示' }, { title: '来源' }] };
    emit('update', { id: 'report_writing_plan', content: outline });
    emit('step_start', { id: 'report_writing', content: '报告撰写中' });
    await chatStream(tier, { messages: [{ role: 'system', content: P.REPORT_SYSTEM() + P.SUGGEST_HINT }, { role: 'user', content: `问题：${question}\n\n写作计划：${JSON.stringify(outline)}\n\n研究笔记：\n${notes.join('\n\n')}\n\n可引用来源：\n${sourceList()}` }], signal, maxTokens: 8000, onReasoning: (x) => emit('_cot', { content: x }), onContent: emitQa });
  } else if (mode === 'agent') {
    // AlphaEngine Agent 形态：开场复述 → 子任务清单 → 逐个子任务取数并写工作笔记（todo.md / 笔记.md）→ 复核 → 撰写最终报告 → 总结
    emit('update', { id: 'intro', content: `收到您的需求：「${question}」。我会先拆解子任务，逐项检索取数并记录工作笔记，再复核数据口径，最后形成带来源引用的研究报告。` });
    const { title, subs } = await plan();
    const n = subs.length;
    const progress = (p, text) => emit('update', { id: 'progress', content: { pct: Math.min(100, Math.round(p)), text } });
    const fileOp = (op, name, subId) => emit('update', { id: 'file_op', sub_id: subId, content: { op, name } });
    emit('update', { id: 'plans', content: subs.map(s => ({ ...s, state: 'pending' })) });
    emit('update', { id: 'sub_question_list', content: subs.map(s => ({ ...s, state: 'pending' })) });
    emit('step_start', { id: 'main_loop', content: '任务运行中' });
    progress(3, '开始执行');
    const notes = [];
    for (const [i, s] of subs.entries()) {
      emit('step_start', { id: 'sub_question_start', sub_id: s.id, content: s.question });
      fileOp(i === 0 ? 'create' : 'modify', 'todo.md', s.id);
      progress(5 + (i / n) * 75, `执行子任务 ${s.id}/${n}`);
      const before = ctx.sources.length;
      const note = await loop([{ role: 'system', content: P.SUBQ_SYSTEM() }, { role: 'user', content: `总任务：${question}\n全部子任务：\n${subs.map(x => `${x.id}. ${x.question}`).join('\n')}\n当前子任务：${s.id}. ${s.question}\n已登记来源（不得虚构编号）：\n${sourceList()}\n建议工具：${s.tools.join(',') || '自行判断'}${notes.length ? `\n\n已完成子任务笔记摘要：\n${notes.map(x => clip(x, 600)).join('\n')}` : ''}` }], { maxRounds: 3, subId: s.id, cotId: 'sub_question_cot' });
      const fname = `${s.question.split(/[：:，,（(。]/)[0].slice(0, 18)}.md`;
      emit('update', { id: 'sub_question_source', sub_id: s.id, content: ctx.sources.slice(before) });
      emit('update', { id: 'work_note', sub_id: s.id, content: { title: fname, body: note } });
      fileOp('create', fname, s.id);
      fileOp('modify', 'todo.md', s.id);
      emit('update', { id: 'sub_question_done', sub_id: s.id, content: note });
      notes.push(`### 子任务${s.id}：${s.question}\n${note}`);
      progress(5 + ((i + 1) / n) * 75, `子任务 ${s.id} 完成`);
    }
    emit('update', { id: 'plans_done' });
    emit('step_start', { id: 'reflection', content: '复核数据完整性' });
    progress(82, '复核数据完整性');
    const draft = notes.join('\n\n');
    const rf = await chatStream(tier, { messages: [{ role: 'system', content: P.REFLECT_SYSTEM() }, { role: 'user', content: `问题：${question}\n已有来源：\n${sourceList()}\n研究笔记${draft.length > 12000 ? '（系统为节省篇幅仅截取前 12000 字，末尾中断是系统截取所致，不是笔记缺失，请勿据此判定截断）' : ''}：\n${clip(draft, 12000)}` }], signal, maxTokens: 1500, onReasoning: (x) => emit('_cot', { content: x }) });
    const r = parseJSON(rf.content);
    emit('update', { id: 'reflection', content: r || { sufficient: false, gaps: ['复核结果未形成有效结构，按现有证据保留数据缺口'] } });
    const extra = [];
    if (r && !r.sufficient && Array.isArray(r.next)) {
      for (const [i, x] of r.next.slice(0, 3).entries()) if (TOOL_META[x.tool]) {
        const out = await execTool({ id: `reflect_${i}`, function: { name: x.tool, arguments: JSON.stringify(x.args || {}) } }, subs[n - 1].id);
        extra.push(`${x.tool}: ${out.text}`);
      }
    }
    emit('step_start', { id: 'report_writing', content: '正在撰写报告' });
    progress(88, '正在撰写报告');
    await chatStream(tier, { messages: [{ role: 'system', content: P.AGENT_REPORT_SYSTEM() }, { role: 'user', content: `任务：${question}\n\n研究笔记：\n${draft}${extra.length ? `\n\n复核补充数据：\n${extra.join('\n')}` : ''}\n\n可引用来源：\n${sourceList()}` }], signal, maxTokens: 8000, onReasoning: (x) => emit('_cot', { content: x }), onContent: emitQa });
    fileOp('create', '最终报告.md', subs[n - 1].id);
    emit('update', { id: 'summary', content: `已完成「${title}」的研究任务：共执行 ${n} 个子任务、${ctx.sources.length} 条数据与资料检索，生成 ${n} 篇工作笔记和 1 篇最终报告，最终报告见下方。` });
    progress(100, '已完成该任务');
  } else {
    emit('step_start', { id: 'thinking', content: '思考分析中...' });
    const msgs = [{ role: 'system', content: P.QUICK_SYSTEM() + P.SUGGEST_HINT }, ...hist, { role: 'user', content: question }];
    await loop(msgs, { maxRounds: 4, answerStream: true });
  }

  if (ctx.warnings.length && !qaBuf.includes('口径存疑')) emitQa(`\n\n### 数据口径说明\n${[...new Set(ctx.warnings)].map(w => `- ${w}`).join('\n')}\n`);
  const suggestions = flushQa();
  emit('answer_source', { content: ctx.sources });
  if (mode !== 'agent') emit('update', { id: 'suggestions', content: suggestions });
  emit('update', { id: '_final', content: { elapsed_ms: Date.now() - t0, sources: ctx.sources.length } });
}
