// ../../../../AlphaDesk/src/lib/aiStream.ts
var newAiMsg = (mode, tier) => ({
  mode,
  tier,
  status: "",
  cot: "",
  thinkingDone: false,
  tools: [],
  plans: [],
  subs: [],
  reportWriting: false,
  message: "",
  sources: [],
  suggestions: [],
  generating: true,
  notes: [],
  files: [],
  seq: 0
});
function reduceAi(m, { event, data }) {
  const d = data || {};
  switch (event) {
    case "setup":
      return { ...m, session: d.content };
    case "step_start": {
      const id = d.id;
      if (id === "sub_question_start") {
        const plans = m.plans.map((p) => p.id === d.sub_id ? { ...p, state: "processing" } : p.state === "processing" ? { ...p, state: "finished" } : p);
        return { ...m, plans, status: d.content, statusId: id, subs: m.subs.map((s) => s.id === d.sub_id ? { ...s, state: "processing" } : s.state === "processing" ? { ...s, state: "finished" } : s) };
      }
      if (id === "report_writing") return { ...m, status: d.content, statusId: id, reportWriting: true, thinkingDone: true, plans: m.plans.map((p) => ({ ...p, state: "finished" })) };
      if (id === "main_loop") return { ...m, status: d.content, statusId: id, plans: m.plans.map((p, i) => i === 0 ? { ...p, state: "processing" } : p) };
      return { ...m, status: d.content, statusId: id };
    }
    case "_cot":
      return { ...m, cot: m.cot + (d.content || "") };
    case "_qa":
      return { ...m, message: m.message + (d.content || ""), thinkingDone: true };
    case "tool_call": {
      const t = { seq: m.seq + 1, id: d.tool_call_id, name: d.tool_name, title: d.title, group: d.group, display: d.display, args: d.args, state: "processing", subId: d.sub_id };
      let plans = m.plans;
      if (plans.length) {
        const done = Math.min(plans.length - 1, m.tools.length);
        plans = plans.map((p, i) => ({ ...p, state: i < done ? "finished" : i === done ? "processing" : p.state }));
      }
      return { ...m, seq: m.seq + 1, tools: [...m.tools, t], plans: m.mode === "agent" ? m.plans : plans };
    }
    case "tool_call_result": {
      const add = (d.sources || []).filter((x) => x && !m.sources.some((y) => y.id === x.id));
      return { ...m, sources: add.length ? [...m.sources, ...add] : m.sources, tools: m.tools.map((t) => t.id === d.tool_call_id ? { ...t, state: d.ok ? "finished" : "failed", summary: d.summary, ms: d.ms, sourceIds: d.source_ids } : t) };
    }
    case "answer_source":
      return { ...m, sources: d.content?.length ? d.content : m.sources };
    case "error":
      return { ...m, error: d.content || "\u672A\u77E5\u9519\u8BEF", generating: false };
    case "update": {
      switch (d.id) {
        case "_qa_retract":
          return { ...m, message: "" };
        case "sub_question_list":
          return { ...m, subs: (d.content || []).map((s) => ({ id: s.id, question: s.question, state: "pending", cot: "", sources: [] })) };
        case "sub_question_cot":
          return { ...m, subs: m.subs.map((s) => s.id === d.sub_id ? { ...s, cot: s.cot + (d.content || "") } : s) };
        case "sub_question_source":
          return { ...m, subs: m.subs.map((s) => s.id === d.sub_id ? { ...s, sources: d.content || [] } : s) };
        case "sub_question_done":
          return { ...m, plans: m.plans.map((p) => p.id === d.sub_id ? { ...p, state: "finished" } : p), subs: m.subs.map((s) => s.id === d.sub_id ? { ...s, state: "finished", note: d.content } : s) };
        case "plans":
          return { ...m, plans: (d.content || []).map((p) => ({ id: p.id, question: p.question, state: "pending" })) };
        case "intro":
          return { ...m, intro: d.content };
        case "progress":
          return { ...m, progress: d.content };
        case "file_op":
          return { ...m, seq: m.seq + 1, files: [...m.files, { seq: m.seq + 1, subId: d.sub_id, op: d.content?.op, name: d.content?.name }] };
        case "work_note":
          return { ...m, notes: [...m.notes, { subId: d.sub_id, title: d.content?.title, body: d.content?.body }] };
        case "summary":
          return { ...m, summary: d.content };
        case "plans_done":
          return { ...m, plans: m.plans.map((p) => ({ ...p, state: "finished" })) };
        case "reflection":
          return { ...m, reflection: d.content };
        case "report_writing_plan":
          return { ...m, outline: d.content };
        case "suggestions":
          return { ...m, suggestions: d.content || [] };
        case "_final":
          return {
            ...m,
            generating: false,
            thinkingDone: true,
            reportWriting: false,
            elapsedMs: d.content?.elapsed_ms,
            status: "",
            subs: m.subs.map((s) => ({ ...s, state: s.state === "failed" ? s.state : "finished" }))
          };
      }
      return m;
    }
  }
  return m;
}
async function readSSE(res, cb) {
  const reader = res.body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  for (; ; ) {
    const { done, value } = await reader.read();
    buf += done ? dec.decode() : dec.decode(value, { stream: true });
    buf = buf.replace(/\r\n/g, "\n");
    if (done && buf.trim()) buf += "\n\n";
    let i;
    while ((i = buf.indexOf("\n\n")) >= 0) {
      const block = buf.slice(0, i);
      buf = buf.slice(i + 2);
      let event = "message";
      let id;
      const data = [];
      for (const line of block.split("\n")) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) data.push(line.slice(5).trimStart());
        else if (line.startsWith("id:")) id = Number(line.slice(3).trim());
      }
      if (!data.length) continue;
      let parsed;
      try {
        parsed = JSON.parse(data.join("\n"));
      } catch {
        throw new Error("\u56DE\u7B54\u4E8B\u4EF6\u683C\u5F0F\u9519\u8BEF\uFF0C\u8BF7\u91CD\u8BD5");
      }
      cb(event, parsed, id);
    }
    if (done) break;
  }
}
export {
  newAiMsg,
  readSSE,
  reduceAi
};
