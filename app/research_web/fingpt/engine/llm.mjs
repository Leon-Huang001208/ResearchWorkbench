import { safeText, textFilter } from './security.mjs';
// OpenAI 兼容 Chat Completions 流式客户端 + 档位注册表
const E = (k, d = '') => process.env[k] || d;

export function getTiers() {
  return {
    lite: { label: 'Lite · 小米 MiMo', base: E('MIMO_BASE_URL', 'https://api.xiaomimimo.com/v1'), key: E('MIMO_API_KEY'), model: E('MIMO_MODEL'), auth: E('MIMO_AUTH', 'api-key') },
    ultra: { label: 'Ultra · MiniMax', base: E('MINIMAX_BASE_URL', 'https://api.minimaxi.com/v1'), key: E('MINIMAX_API_KEY'), model: E('MINIMAX_MODEL'), auth: 'bearer', extra: { reasoning_split: true } },
    frontier: { label: 'Frontier · 通义千问', base: E('DASHSCOPE_BASE_URL', 'https://dashscope.aliyuncs.com/compatible-mode/v1'), key: E('DASHSCOPE_API_KEY'), model: E('QWEN_MODEL'), auth: 'bearer' },
    kimi: { label: 'Kimi（可选）', base: E('KIMI_BASE_URL', 'https://api.moonshot.cn/v1'), key: E('KIMI_API_KEY'), model: E('KIMI_MODEL'), auth: 'bearer' },
  };
}

export function publicTiers() {
  const t = getTiers();
  return Object.fromEntries(Object.entries(t).map(([id, v]) => [id, { label: v.label, configured: !!(v.key && v.model) }]));
}

/**
 * 流式调用。回调：onReasoning(text) / onContent(text)
 * 返回 { content, reasoning, tool_calls, finish_reason }
 */
export async function chatStream(tier, { messages, tools, signal, maxTokens = 4096, onReasoning, onContent }) {
  const p = getTiers()[tier];
  if (!p) throw new Error(`未知档位 ${tier}`);
  if (!p.key || !p.model) throw Object.assign(new Error(`${p.label} 未配置 API Key`), { code: 'NO_KEY' });
  const headers = { 'Content-Type': 'application/json', Accept: 'text/event-stream' };
  if (p.auth === 'api-key') headers['api-key'] = p.key; else headers.Authorization = `Bearer ${p.key}`;
  const body = { model: p.model, messages, stream: true, max_tokens: maxTokens, ...(p.extra || {}) };
  if (tools?.length) { body.tools = tools; body.tool_choice = 'auto'; }
  const requestSignal = signal ? AbortSignal.any([signal, AbortSignal.timeout(240000)]) : AbortSignal.timeout(240000);
  const res = await fetch(`${p.base.replace(/\/$/, '')}/chat/completions`, { method: 'POST', headers, body: JSON.stringify(body), signal: requestSignal });
  if (!res.ok) {
    await res.body?.cancel();
    throw Object.assign(new Error(`${p.label} 服务返回 HTTP ${res.status}`), { code: 'LLM_HTTP_ERROR' });
  }
  const reader = res.body.getReader();
  const dec = new TextDecoder();
  let buf = '', content = '', reasoning = '', finish = null;
  const calls = [];
  const contentOut = textFilter(x => onContent?.(x));
  const reasoningOut = textFilter(x => onReasoning?.(x));
  let inThink = false, tagBuf = '';
  const write = (txt, thinking) => {
    if (thinking) { reasoning += txt; reasoningOut.push(txt); }
    else { content += txt; contentOut.push(txt); }
  };
  const emitContent = txt => {
    tagBuf += txt;
    for (;;) {
      const tag = inThink ? '</think>' : '<think>';
      const i = tagBuf.indexOf(tag);
      if (i >= 0) {
        write(tagBuf.slice(0, i), inThink);
        tagBuf = tagBuf.slice(i + tag.length); inThink = !inThink;
        continue;
      }
      let keep = 0;
      for (let n = 1; n < tag.length; n++) if (tagBuf.endsWith(tag.slice(0, n))) keep = n;
      write(tagBuf.slice(0, tagBuf.length - keep), inThink);
      tagBuf = keep ? tagBuf.slice(-keep) : '';
      break;
    }
  };
  for (;;) {
    const { done, value } = await reader.read();
    if (done) { buf += dec.decode(); if (buf.trim()) buf += '\n'; else break; }
    buf += dec.decode(value, { stream: true });
    let idx;
    while ((idx = buf.indexOf('\n')) >= 0) {
      const line = buf.slice(0, idx).trim(); buf = buf.slice(idx + 1);
      if (!line.startsWith('data:')) continue;
      const data = line.slice(5).trim();
      if (data === '[DONE]') continue;
      let j; try { j = JSON.parse(data); } catch { continue; }
      if (j.error) throw Object.assign(new Error('模型流返回错误'), { code: 'LLM_STREAM_ERROR' });
      const ch = j.choices?.[0]; if (!ch) continue;
      const d = ch.delta || {};
      if (d.reasoning_content) { write(d.reasoning_content, true); }
      if (Array.isArray(d.reasoning_details)) for (const r of d.reasoning_details) if (r.text) { write(r.text, true); }
      if (d.content) emitContent(d.content);
      if (d.tool_calls) for (const tc of d.tool_calls) {
        const i = tc.index ?? calls.length;
        calls[i] ||= { id: '', type: 'function', function: { name: '', arguments: '' } };
        if (tc.id) calls[i].id = tc.id;
        if (tc.function?.name) calls[i].function.name += tc.function.name;
        if (tc.function?.arguments) calls[i].function.arguments += tc.function.arguments;
      }
      if (ch.finish_reason) finish = ch.finish_reason;
    }
    if (done) break;
  }
  write(tagBuf, inThink);
  contentOut.flush(); reasoningOut.flush();
  if (!finish) throw Object.assign(new Error('模型流提前结束，请重试'), { code: 'LLM_INCOMPLETE' });
  if (finish === 'length') throw Object.assign(new Error('模型输出达到长度上限，请缩小问题范围后重试'), { code: 'LLM_TRUNCATED' });
  const tool_calls = calls.filter(Boolean).map((c, i) => ({ ...c, id: c.id || `call_${Date.now()}_${i}` }));
  return { content: safeText(content), reasoning: safeText(reasoning), tool_calls, finish_reason: finish };
}
