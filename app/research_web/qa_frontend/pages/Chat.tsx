// Adapted from AlphaDesk's Chat page. RWB owns the composer and Host snapshots.
import { useMemo, useRef, useState } from 'react';
import AiAnswer from '../components/chat/AiAnswer';
import AiWorkspace from '../components/chat/AiWorkspace';
import { AI_LABELS } from '../lib/aiLabels';
import { projectTurns, type AiMode, type QaEvent } from '../lib/aiStream';
import { useStickyBottom } from '../lib/useStickyBottom';

export interface ChatProps {
  sessionId: string | null;
  events: readonly QaEvent[];
  mode: AiMode;
  model: string;
  status: string;
  disabled: boolean;
  loading: boolean;
  streamError: string;
  onMode: (mode: AiMode) => void;
  onSuggest: (question: string) => void;
  onStop: () => void;
}

const modes = Object.keys(AI_LABELS.modes) as AiMode[];

export default function Chat({ events, mode, model, status, disabled, loading, streamError, onMode, onSuggest, onStop }: ChatProps) {
  const turns = useMemo(() => projectTurns(events, model, status), [events, model, status]);
  const [panel, setPanel] = useState<{ turn: number; id?: string; nonce?: number } | null>(null);
  const transcript = useRef<HTMLDivElement>(null);
  const { atBottom, toBottom } = useStickyBottom(transcript, events);
  const panelMsg = turns.find(turn => turn.seq === panel?.turn);

  const openSource = (turn: number, id: string) => setPanel({ turn, id, nonce: Date.now() });

  return (
    <section className="qa-page" aria-label="FinGPT">
      <header className="qa-modes">
        <div className="qa-mode-buttons" role="group" aria-label="研究模式">
          {modes.map(item => <button key={item} type="button" className="button" aria-pressed={mode === item}
            disabled={disabled} onClick={() => onMode(item)}>{AI_LABELS.modes[item].name}</button>)}
        </div>
        {model && <span className="qa-model">{model}</span>}
      </header>
      <div className={`qa-chat-layout${panelMsg ? ' qa-with-workspace' : ''}`}>
        <div className="qa-transcript" ref={transcript} role="region" aria-label="问答记录" tabIndex={0}>
          {streamError && <p className="qa-stream-error" role="status">{streamError}</p>}
          {loading && <p className="qa-welcome" role="status">正在读取会话…</p>}
          {!loading && !turns.length && <div className="qa-welcome"><h1>从一个问题，开始研究</h1><p>{AI_LABELS.modes[mode].desc}</p></div>}
          {turns.map(({ seq, question, ai }) => (
            <article key={seq} className="qa-turn" aria-label="研究问答">
              <p className="qa-question">{question}</p>
              <AiAnswer m={ai} onSuggest={onSuggest} onStop={onStop} onSource={id => openSource(seq, id)}
                actions={(ai.sources.length > 0 || ai.notes.length > 0) && <button type="button"
                  onClick={() => setPanel({ turn: seq })}>查看参考资料与笔记</button>} />
            </article>
          ))}
        </div>
        {!atBottom && <button type="button" className="qa-bottom button" onClick={toBottom}>回到底部</button>}
        {panelMsg && <AiWorkspace key={panelMsg.seq} m={panelMsg.ai} question={panelMsg.question} onClose={() => setPanel(null)}
          focus={panel?.id ? { id: panel.id, nonce: panel.nonce || 0 } : undefined} onSource={id => openSource(panelMsg.seq, id)} />}
      </div>
    </section>
  );
}
