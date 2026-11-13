// /api/chat/ask SSE 客户端 + 事件归并（事件名对齐 AlphaEngine：setup / step_start / tool_call / tool_call_result / _cot / _qa / update / answer_source / error）
export type AiMode = "quick" | "deep" | "agent";
export type StepState = "pending" | "processing" | "finished" | "failed";

export interface AiSource { id: string; title: string; url?: string; provider?: string; asof?: string }
export interface AiTool { seq?: number; id: string; name: string; title: string; group: string; display: string; args: unknown; state: StepState; summary?: string; ms?: number; sourceIds?: string[]; subId?: number }
export interface AiSubQ { id: number; question: string; state: StepState; cot: string; note?: string; sources: AiSource[] }
export interface AiPlanItem { id: number; question: string; state: StepState }
export interface AiOutline { title?: string; sections?: { title: string; points?: string[] }[] }

export interface AiMsg {
  session?: string;
  skill?: {id:string;name:string};
  taskId?: string;
  taskStatus?: string;
  mode: AiMode;
  tier: string;
  status: string;          // 当前状态行
  statusId?: string;
  cot: string;             // 思维链
  thinkingDone: boolean;
  tools: AiTool[];
  plans: AiPlanItem[];
  subs: AiSubQ[];
  reflection?: { sufficient?: boolean; gaps?: string[] };
  outline?: AiOutline;
  reportWriting: boolean;
  message: string;         // 最终答案 markdown
  sources: AiSource[];
  suggestions: string[];
  generating: boolean;
  error?: string;
  elapsedMs?: number;
  // Agent 工作空间
  intro?: string;
  progress?: { pct: number; text: string };
  notes: AiNote[];
  files: AiFileOp[];
  summary?: string;
  seq: number;
}
export interface AiNote { subId: number; title: string; body: string }
export interface AiFileOp { seq: number; subId?: number; op: "create" | "modify"; name: string }

export const newAiMsg = (mode: AiMode, tier: string): AiMsg => ({
  mode, tier, status: "", cot: "", thinkingDone: false, tools: [], plans: [], subs: [], reportWriting: false,
  message: "", sources: [], suggestions: [], generating: true, notes: [], files: [], seq: 0,
});

type Ev = { event: string; data: any };

export function reduceAi(m: AiMsg, { event, data }: Ev): AiMsg {
  const d = data || {};
  switch (event) {
    case "setup": return { ...m, session: d.content };
    case "step_start": {
      const id: string = d.id;
      if (id === "sub_question_start") {
        const plans = m.plans.map(p => p.id === d.sub_id ? { ...p, state: "processing" as StepState } : p.state === "processing" ? { ...p, state: "finished" as StepState } : p);
        return { ...m, plans, status: d.content, statusId: id, subs: m.subs.map(s => s.id === d.sub_id ? { ...s, state: "processing" } : s.state === "processing" ? { ...s, state: "finished" } : s) };
      }
      if (id === "report_writing") return { ...m, status: d.content, statusId: id, reportWriting: true, thinkingDone: true, plans: m.plans.map(p => ({ ...p, state: "finished" })) };
      if (id === "main_loop") return { ...m, status: d.content, statusId: id, plans: m.plans.map((p, i) => i === 0 ? { ...p, state: "processing" } : p) };
      return { ...m, status: d.content, statusId: id };
    }
    case "_cot": return { ...m, cot: m.cot + (d.content || "") };
    case "_qa": return { ...m, message: m.message + (d.content || ""), thinkingDone: true };
    case "tool_call": {
      const t: AiTool = { seq: m.seq + 1, id: d.tool_call_id, name: d.tool_name, title: d.title, group: d.group, display: d.display, args: d.args, state: "processing", subId: d.sub_id };
      // Agent 模式：按工具调用推进计划进度
      let plans = m.plans;
      if (plans.length) {
        const done = Math.min(plans.length - 1, m.tools.length); // 每次工具调用推进一个计划项
        plans = plans.map((p, i) => ({ ...p, state: i < done ? "finished" : i === done ? "processing" : p.state }));
      }
      return { ...m, seq: m.seq + 1, tools: [...m.tools, t], plans: m.mode === "agent" ? m.plans : plans };
    }
    case "tool_call_result": {
      const add = ((d.sources || []) as AiSource[]).filter(x => x && !m.sources.some(y => y.id === x.id));
      return { ...m, sources: add.length ? [...m.sources, ...add] : m.sources, tools: m.tools.map(t => t.id === d.tool_call_id ? { ...t, state: d.ok ? "finished" : "failed", summary: d.summary, ms: d.ms, sourceIds: d.source_ids } : t) };
    }
    case "answer_source": return { ...m, sources: d.content?.length ? d.content : m.sources };
    case "task_end": {
      const error = m.error || ({ failed: "研究执行失败。", stopped: "已停止研究。", cancelled: "已停止研究。", interrupted: "研究中断，请先核对已有结果。", unknown: "受理状态待核对。" } as Record<string, string>)[d.status];
      return { ...m, taskStatus: d.status, generating: false, thinkingDone: true, reportWriting: false, error };
    }
    case "error": return { ...m, error: d.content || "未知错误", generating: false };
    case "update": {
      switch (d.id) {
        case "skill": return {...m,skill:d.content};
        case "_qa_retract": return { ...m, message: "" };
        case "sub_question_list": return { ...m, subs: (d.content || []).map((s: any) => ({ id: s.id, question: s.question, state: "pending", cot: "", sources: [] })) };
        case "sub_question_cot": return { ...m, subs: m.subs.map(s => s.id === d.sub_id ? { ...s, cot: s.cot + (d.content || "") } : s) };
        case "sub_question_source": return { ...m, subs: m.subs.map(s => s.id === d.sub_id ? { ...s, sources: d.content || [] } : s) };
        case "sub_question_done": return { ...m, plans: m.plans.map(p => p.id === d.sub_id ? { ...p, state: "finished" } : p), subs: m.subs.map(s => s.id === d.sub_id ? { ...s, state: "finished", note: d.content } : s) };
        case "plans": return { ...m, plans: (d.content || []).map((p: any) => ({ id: p.id, question: p.question, state: "pending" })) };
        case "intro": return { ...m, intro: d.content };
        case "progress": return { ...m, progress: d.content };
        case "file_op": return { ...m, seq: m.seq + 1, files: [...m.files, { seq: m.seq + 1, subId: d.sub_id, op: d.content?.op, name: d.content?.name }] };
        case "work_note": return { ...m, notes: [...m.notes, { subId: d.sub_id, title: d.content?.title, body: d.content?.body }] };
        case "summary": return { ...m, summary: d.content };
        case "plans_done": return { ...m, plans: m.plans.map(p => ({ ...p, state: "finished" })) };
        case "reflection": return { ...m, reflection: d.content };
        case "report_writing_plan": return { ...m, outline: d.content };
        case "suggestions": return { ...m, suggestions: d.content || [] };
        case "_final": return { ...m, generating: false, thinkingDone: true, reportWriting: false, elapsedMs: d.content?.elapsed_ms, status: "",
          subs: m.subs.map(s => ({ ...s, state: s.state === "failed" ? s.state : "finished" })) };
      }
      return m;
    }
  }
  return m;
}

export type QaEvent = Ev & { seq: number };
export interface QaTurn { seq: number; question: string; ai: AiMsg }

const modeOf = (value: unknown): AiMode => value === 'deep' || value === 'agent' ? value : 'quick';

export function projectTurns(events: readonly QaEvent[], model: string, sessionStatus = ''): QaTurn[] {
  const turns: QaTurn[] = [];
  let lastSeq = 0;
  let current: QaTurn | undefined;
  for (const item of events) {
    if (!Number.isSafeInteger(item.seq) || item.seq <= lastSeq) continue;
    lastSeq = item.seq;
    if (item.event === 'question' && typeof item.data?.content === 'string') {
      current = { seq: item.seq, question: item.data.content, ai: newAiMsg(modeOf(item.data.mode), model) };
      turns.push(current);
    } else if (current) {
      current.ai = reduceAi(current.ai, item);
    }
  }
  if (current && !current.ai.taskStatus && ['interrupted', 'cancelled', 'failed'].includes(sessionStatus)) {
    current.ai = reduceAi(current.ai, { event: 'task_end', data: { status: sessionStatus } });
  }
  return turns;
}
