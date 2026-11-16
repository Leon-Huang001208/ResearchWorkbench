// AI 回答渲染，复刻 AlphaEngine 呈现：
//  快速/研究：可折叠「思考分析」面板（正在检索「库」query → 完成检索 + 灰色流式推理）→ 正文（角标）→ 页脚 N篇文档 · 重试/复制/分享/赞/踩
//  Agent：开场复述 → 子任务清单（检索/研读/文件操作 步骤行）→ 底部「任务运行中 X%」→ 总结 + 最终报告卡片（全屏/下载）→ 参考N篇文档·生成N篇笔记
import { useState, type ReactNode } from "react";
import Markdown from "../charts/Markdown";
import { AI_LABELS as T } from "../../lib/aiLabels";
import type { AiMsg, AiTool, StepState } from "../../lib/aiStream";

export const kindOf = (g: string) => T.sourceKinds[g] || g;
export const queryOf = (t: AiTool) => {
  const a = (t.args || {}) as Record<string, unknown>;
  const q = a.query ?? a.keyword ?? a.code ?? a.codes ?? a.symbol ?? a.series ?? a.index;
  return q != null ? (Array.isArray(q) ? q.join("、") : String(q)) : t.display;
};
// 把 [S1] / [S1][S2] 渲染为角标链接（点击联动右侧参考文件）
export const withCites = (md: string) => md.replace(/\[S(\d+)\](?!\()/g, "[$1](#src-S$1)");

const Check = ({ s }: { s: StepState }) => (
  <span className={`ae-check ae-check-${s}`}>{s === "finished" ? "✓" : s === "failed" ? "!" : s === "processing" ? <span className="ai-spin" /> : ""}</span>
);

function StepLine({ t }: { t: AiTool }) {
  const verb = t.state === "processing" ? T.searching : t.state === "failed" ? T.toolFailed : T.searched;
  return (
    <div className={`ae-step ae-step-${t.state}`} title={t.display}>
      <span className="ae-step-ico">⌕</span>
      <span>{verb}「<b>{kindOf(t.group)}</b>」</span>
      <span className="ae-step-q">{queryOf(t)}</span>
    </div>
  );
}

function ThinkPanel({ m }: { m: AiMsg }) {
  const done = m.thinkingDone || !m.generating;
  const [open, setOpen] = useState<boolean | null>(null);
  const isOpen = open ?? !done;
  const tools = m.tools.filter(t => m.mode !== "deep" || t.subId == null);
  return (
    <div className="ae-think">
      <button className="ae-think-head" onClick={() => setOpen(!isOpen)} aria-expanded={isOpen}>
        {!done && <span className="ai-spin" />}<span>{done ? T.thinkingDone : T.thinkingPrefix}</span>
        <span className="ai-caret">{isOpen ? "▴" : "▾"}</span>
      </button>
      {isOpen && (
        <div className="ae-think-body">
          {tools.map(t => <StepLine key={t.id} t={t} />)}
          {m.mode === "deep" && m.subs.map(s => (
            <div key={s.id} className="ae-sub">
              <div className="ae-sub-q"><Check s={s.state} />{s.id}. {s.question}</div>
              {m.tools.filter(t => t.subId === s.id).map(t => <StepLine key={t.id} t={t} />)}
              {s.cot && <div className="ae-cot">{s.cot.slice(-1200)}</div>}
            </div>
          ))}
          {m.outline?.sections?.length ? <div className="ae-cot">写作计划：{m.outline.sections.map(s => s.title).join(" / ")}</div> : null}
          {m.cot && <div className="ae-cot">{m.cot}</div>}
          {m.generating && !m.cot && !tools.length && <div className="ae-cot">{T.collecting}</div>}
        </div>
      )}
    </div>
  );
}

function Footer({ m, onStop, extra }: { m: AiMsg; onStop: () => void; extra?: ReactNode }) {
  const [notice, setNotice] = useState("");
  if (m.generating) return m.mode === "agent" ? null : <div className="ae-foot"><button className="ae-stop" onClick={onStop}>■ {T.stop}</button></div>;
  const copy = async () => { try { await navigator.clipboard.writeText(m.message); setNotice("已复制全文"); } catch { setNotice("复制失败，请手动选择正文"); } };
  return (
    <div className="ae-foot">
      <span className="ae-docs">{m.mode === "agent" ? `参考${m.sources.length}篇文档 · 生成${m.notes.length}篇笔记` : `${m.sources.length}篇文档`}</span>
      <span className="flex-1" />
      {m.message && <button type="button" onClick={copy} title={T.copy}>⧉ {T.copy}</button>}
      {extra}
      {notice && <span role="status">{notice}</span>}
    </div>
  );
}

function ReportCard({ m, onSource }: { m: AiMsg; onSource?: (id: string) => void }) {
  const [full, setFull] = useState(false);
  const title = (m.message.match(/^#\s+(.+)$/m)?.[1] || "最终报告").trim();
  const body = <div className="ai-body"><Markdown onSource={onSource}>{withCites(m.message)}</Markdown>{m.generating && <span className="typing-caret" />}</div>;
  return (
    <>
      <div className="ae-report">
        <div className="ae-report-head">
          <span className="ae-report-ico">▤</span><b>{title}</b><span className="ae-tag">最终报告</span>
          <span className="flex-1" />
          <button onClick={() => setFull(true)}>⤢ 全屏</button>
        </div>
        {body}
      </div>
      {full && (
        <div className="ae-modal" onClick={() => setFull(false)}>
          <div className="ae-modal-in" onClick={e => e.stopPropagation()}>
            <div className="ae-report-head"><b>{title}</b><span className="flex-1" /><button onClick={() => setFull(false)}>✕</button></div>
            {body}
          </div>
        </div>
      )}
    </>
  );
}

function AgentView({ m, onStop, onSource }: { m: AiMsg; onStop: () => void; onSource?: (id: string) => void }) {
  const pct = m.progress?.pct;
  const lines = (subId: number) => [
    ...m.tools.filter(t => t.subId === subId).map(t => ({ seq: t.seq || 0, el: <StepLine key={t.id} t={t} /> })),
    ...m.files.filter(f => f.subId === subId).map(f => ({ seq: f.seq, el: <div key={`f${f.seq}`} className="ae-step ae-file"><span className="ae-step-ico">▤</span>{f.op === "create" ? "完成创建文件" : "完成修改文件"} <span className="ae-file-name">{f.name}</span></div> })),
  ].sort((a, b) => a.seq - b.seq).map(x => x.el);
  return (
    <div className="ae-agent">
      {!m.intro && m.generating && <div className="ae-placeholder">正在理解您的需求并规划任务<span className="typing-caret" /></div>}
      {m.intro && <div className="ae-intro">{m.intro}</div>}
      {m.plans.map(p => {
        const sub = m.subs.find(s => s.id === p.id);
        const note = m.notes.find(n => n.subId === p.id);
        return (
          <div key={p.id} className={`ae-task ae-task-${p.state}`}>
            <div className="ae-task-q"><Check s={p.state} /><span>{p.question}</span></div>
            {p.state !== "pending" && <div className="ae-task-steps">
              {lines(p.id)}
              {note && <div className="ae-task-note">{note.body.replace(/\[S\d+\]|[*#|>`]/g, "").replace(/\s+/g, " ").slice(0, 90)}…</div>}
              {!note && sub?.cot && p.state === "processing" && <div className="ae-cot">{sub.cot.slice(-240)}</div>}
            </div>}
          </div>
        );
      })}
      {m.reportWriting && m.generating && <div className="ae-step"><span className="ai-spin" /> {T.reportWriting === "报告撰写中" ? "正在撰写报告" : T.reportWriting}</div>}
      {m.summary && <div className="ae-intro">{m.summary}</div>}
      {m.message && <ReportCard m={m} onSource={onSource} />}
      {m.generating && (
        <div className="ae-runbar">
          <span className="ai-spin" />
          <div className="flex-1">
            <div className="ae-runbar-t">任务运行中 {pct !== undefined && `${pct}%`}</div>
            <div className="ae-runbar-s">{m.progress?.text || m.status}</div>
            {m.taskId && <div className="ae-runbar-bg">任务已在后台执行，安心退出进行其他操作</div>}
            {pct !== undefined && <progress max={100} value={pct} aria-label="执行进度" />}
          </div>
          <button className="ae-stop-ico" onClick={onStop} title={T.stop}>■</button>
        </div>
      )}
    </div>
  );
}

export default function AiAnswer({ m, onSuggest, onStop, actions, onSource }: { m: AiMsg; onSuggest: (q: string) => void; onStop: () => void; actions?: ReactNode; onSource?: (id: string) => void }) {
  return (
    <div className="ai-answer">
      {m.mode === "agent" ? <AgentView m={m} onStop={onStop} onSource={onSource} /> : (
        <>
          <ThinkPanel m={m} />
          {m.message && <div className="ai-body"><Markdown onSource={onSource}>{withCites(m.message)}</Markdown>{m.generating && <span className="typing-caret" />}</div>}
        </>
      )}
      {m.error && <div className="ai-error">⚠ {m.error}</div>}
      <Footer m={m} onStop={onStop} extra={actions} />
      {m.mode !== "agent" && !m.generating && m.suggestions.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {m.suggestions.map(s => <button key={s} onClick={() => onSuggest(s)} className="ai-suggest">{s} →</button>)}
        </div>
      )}
    </div>
  );
}
