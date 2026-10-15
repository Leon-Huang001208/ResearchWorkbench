import { escapeHTML as e, renderMarkdown } from './markdown.mjs';
import { icon } from './icons.mjs';

const terminal = icon('terminal');
const elapsed = ms => !Number.isFinite(ms) || ms < 0 ? '' : ms < 1000 ? `${Math.round(ms)}ms` : `${(ms / 1000).toFixed(1)} 秒`;
const payload = value => `<pre class="activity-payload">${e(typeof value === 'string' ? value : JSON.stringify(value, null, 2))}</pre>`;

// These are presentation labels, never evidence that the named action succeeded.
const labels = { research_run_script: '运行 Python 脚本', read_file: '读取文件', write_file: '写入文件', web_search: '搜索网页', rwb_list_automations: '查看日程', rwb_prepare_automation: '准备日程草稿', rwb_prepare_automation_update: '准备日程修改', rwb_run_automation: '启动日程试跑' };
export function renderClawStep(activity, { sessionId = '', statusLabel = '', agents = [] } = {}) {
  const name = activity.tool || activity.title || activity.type || '活动';
  const title = labels[name] || activity.title || name;
  const failed = ['failed', 'error'].includes(activity.status);
  const time = elapsed(activity.duration_ms);
  const result = activity.result;
  const script = typeof activity.arguments?.code === 'string' ? activity.arguments.code : null;
  const exit = Number.isInteger(result?.exit_code) ? `退出码 ${result.exit_code}` : '';
  const agent = agents.find(item => item.id === activity.agent_id)?.name || activity.agent_id;
  const separate = Object.hasOwn(activity, 'arguments') || Object.hasOwn(activity, 'result');
  const key = activity.id != null ? ` data-disclosure-key="${e(`${sessionId}:tool:${activity.id}`)}"` : '';
  return `<details class="claw-step"${key}><summary>${terminal}<span class="claw-step-title">${e(title)}</span><small class="${failed ? 'claw-step-failed' : ''}">${e(statusLabel)}${agent ? ` · ${e(agent)}` : ''}</small><span class="claw-step-toggle" aria-hidden="true">${icon('chevron')}</span></summary><div class="claw-step-body"><p class="claw-tool-id">工具：${e(name)}</p>${activity.error ? `<p class="notice error activity-error" role="alert">${e(activity.error)}</p>` : ''}${Object.hasOwn(activity, 'arguments') ? `<section><h4>参数</h4>${payload(script ?? activity.arguments)}${script ? `<details data-disclosure-key="${e(`${sessionId}:tool:${activity.id}:arguments`)}"><summary>全部参数</summary>${payload(activity.arguments)}</details>` : ''}</section>` : ''}${Object.hasOwn(activity, 'result') ? `<details class="claw-step-output" data-disclosure-key="${e(`${sessionId}:tool:${activity.id}:output`)}"><summary>结果与原始输出</summary>${payload(typeof result?.stdout === 'string' ? result.stdout : result)}${typeof result?.stdout === 'string' ? payload(result) : ''}</details>` : ''}${!separate && activity.detail ? `<div class="markdown activity-detail">${renderMarkdown(typeof activity.detail === 'string' ? activity.detail : JSON.stringify(activity.detail, null, 2))}</div>` : ''}${exit || time ? `<div class="claw-step-exit">${e([exit, time].filter(Boolean).join(' · '))}</div>` : ''}</div></details>`;
}

// A process ends at every decision/receipt/unknown-position boundary. Only the
// last assistant before a new user turn (or a terminal session) is kept outside.
// No session-level elapsed time is assigned to an individual round.
export function renderClawFlow(entries, detail) {
  const finalIndexes = new Set();
  let lastAssistant = -1;
  const terminalState = ['completed', 'failed', 'cancelled', 'idle'].includes(detail.status);
  entries.forEach((entry, index) => {
    if (entry.kind === 'user') {
      if (lastAssistant >= 0) finalIndexes.add(lastAssistant);
      lastAssistant = -1;
    } else if (entry.kind === 'assistant') lastAssistant = index;
    else if (entry.kind === 'activity' || entry.kind === 'decision') lastAssistant = -1;
  });
  if (lastAssistant >= 0 && terminalState) finalIndexes.add(lastAssistant);
  const parts = [];
  let segment = [];
  const flush = () => {
    if (!segment.length) return;
    const tools = segment.filter(entry => entry.kind === 'activity');
    if (!tools.length) parts.push(segment.map(entry => entry.html).join(''));
    else {
      const failures = tools.filter(entry => ['failed', 'error'].includes(entry.status)).length;
      const first = segment[0];
      const key = `${detail.id || ''}:process:${first.kind}:${first.seq}`;
      parts.push(`<details class="claw-process" data-disclosure-key="${e(key)}" open><summary><span>执行过程 · ${tools.length} 项活动${failures ? ` · ${failures} 失败` : ''}</span><span aria-hidden="true">${icon('chevron')}</span></summary><div class="claw-process-body">${segment.map(entry => entry.html).join('')}</div></details>`);
    }
    segment = [];
  };
  entries.forEach((entry, index) => {
    if (entry.kind === 'user' || entry.kind === 'decision' || !Number.isFinite(entry.seq) || finalIndexes.has(index)) {
      flush(); parts.push(entry.html);
    } else segment.push(entry);
  });
  flush();
  return parts.join('');
}
