// 右侧面板：快速/研究 =「参考文件」；Agent =「Agent工作空间」（参考文件 按检索分组 / 工作笔记 按子任务）
import { useEffect, useRef, useState } from "react";
import { useStickyBottom } from "../../lib/useStickyBottom";
import Markdown, { safeSourceURL } from "../charts/Markdown";
import type { AiMsg, AiSource } from "../../lib/aiStream";
import { kindOf, queryOf, withCites } from "./AiAnswer";

function Src({ s, i, active }: { s: AiSource; i?: number; active?: boolean }) {
  const url = safeSourceURL(s.url);
  return (
    <div className={`ae-ref ${active ? "ae-ref-active" : ""}`} tabIndex={-1} id={`src-${s.id}`}>
      <div className="ae-ref-meta">
        <span className="ae-ref-n">{i ?? s.id.replace("S", "")}</span>
        <span className="ae-ref-p">{s.provider || "数据源"}</span>
        <span className="flex-1" />
        <span>{(s.asof || "").replace(/^(\d{4})(\d{2})(\d{2})$/, "$1-$2-$3")}</span>
      </div>
      {url ? <a href={url} target="_blank" rel="noopener noreferrer" className="ae-ref-t">{s.title}</a> : <div className="ae-ref-t">{s.title}</div>}
    </div>
  );
}

export default function AiWorkspace({ m, question, onClose, focus, onSource }: { m: AiMsg; question: string; onClose: () => void; focus?: { id: string; nonce: number }; onSource?: (id: string) => void }) {
  const agent = m.mode === "agent";
  const [tab, setTab] = useState<"refs" | "notes">("refs");
  const [openNote, setOpenNote] = useState<string | null>(null);
  useEffect(() => { if (focus) setTab("refs"); }, [focus]);
  useEffect(() => {
    if (!focus || tab !== "refs") return;
    const frame = requestAnimationFrame(() => {
      const el = document.getElementById(`src-${focus.id}`);
      el?.scrollIntoView({ behavior: "smooth", block: "nearest" }); el?.focus({ preventScroll: true });
    });
    return () => cancelAnimationFrame(frame);
  }, [focus, tab]);
  const seen = new Set<string>();
  const byId = new Map(m.sources.map(s => [s.id, s]));
  const bodyRef = useRef<HTMLDivElement>(null);
  const { atBottom, toBottom } = useStickyBottom(bodyRef, `${m.sources.length}|${m.notes.length}|${tab}`);
  const groups = m.tools.filter(t => t.sourceIds?.length).map(t => ({ key: t.id, q: queryOf(t), kind: kindOf(t.group), list: t.sourceIds!.map(id => byId.get(id)).filter((s): s is AiSource => { if (!s || seen.has(s.id)) return false; seen.add(s.id); return true; }) }));
  const missing = m.sources.filter(s => !seen.has(s.id));
  if (missing.length) groups.push({ key: "other", q: "其他参考文件", kind: "数据来源", list: missing });
  return (
    <div className="ae-ws paper-card">
      <div className="ae-ws-head"><b>{agent ? "Agent工作空间" : "参考文件"}</b><span className="flex-1" /><button aria-label="关闭参考资料" onClick={onClose}>✕</button></div>
      {agent && (
        <div className="ae-tabs">
          <button className={tab === "refs" ? "on" : ""} onClick={() => setTab("refs")}>参考文件</button>
          <button className={tab === "notes" ? "on" : ""} onClick={() => setTab("notes")}>工作笔记</button>
        </div>
      )}
      <div className="ae-ws-body" ref={bodyRef}>
        {(!agent || tab === "refs") && (agent ? (
          groups.length ? groups.filter(g => g.list.length).map(g => (
            <div key={g.key} className="ae-group">
              <div className="ae-group-q">⌕ {g.q}<span className="ae-tag">{g.kind}</span></div>
              {g.list.map(s => <Src key={s.id} s={s} active={focus?.id === s.id} />)}
            </div>
          )) : <div className="ae-empty">{m.generating ? "资料搜集中…" : "本轮没有可展示的来源。"}</div>
        ) : (
          <>
            <div className="ae-group-q">⌕ {question}</div>
            {m.sources.length ? m.sources.map(s => <Src key={s.id} s={s} active={focus?.id === s.id} />) : <div className="ae-empty">{m.generating ? "资料搜集中…" : "本轮没有可展示的来源。"}</div>}
          </>
        ))}
        {agent && tab === "notes" && (
          <>
            {m.plans.map(p => {
              const notes = m.notes.filter(n => n.subId === p.id);
              return (
                <div key={p.id} className="ae-group">
                  <div className="ae-group-q">{p.id}. {p.question.slice(0, 40)}</div>
                  {notes.map((note, index) => {
                    const key = `${p.id}:${index}`;
                    return (
                      <div key={key}>
                        <button type="button" className="ae-note" aria-expanded={openNote === key}
                          onClick={() => setOpenNote(openNote === key ? null : key)}>▤ {note.title || '工作笔记'}</button>
                        {openNote === key && <div className="ae-note-body"><Markdown onSource={onSource}>{withCites(note.body || '')}</Markdown></div>}
                      </div>
                    );
                  })}
                </div>
              );
            })}
          </>
        )}
      </div>
      {!atBottom && <button className="ae-tobottom ae-tobottom-ws" onClick={toBottom}>↓ 回到底部</button>}
    </div>
  );
}
