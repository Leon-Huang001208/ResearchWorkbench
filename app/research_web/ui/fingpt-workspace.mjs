/** Preserve WeKnora's complete workspace and native event stream across shell renders. */
import { safeLog } from './core.mjs';

export const nativeFinGPT = () => globalThis.__RWB_FINGPT_WORKSPACE__ === true;
export const renderFinGPT = () => '<section class="fingpt-native" aria-label="FinGPT"><div data-fingpt-workspace role="status">正在打开 FinGPT 工作台…</div></section>';
let frame, loading;

export function paintFinGPTShell(root, markup, active) {
  const shell = root.querySelector('.app-shell');
  if (!active || !root.querySelector('.fingpt-native-frame') || !shell) {
    root.innerHTML = markup;
    return;
  }
  // An iframe loses its browsing context when detached, even if the same DOM
  // node is inserted again. Patch the surrounding shell, keeping main attached.
  const template = document.createElement('template');
  template.innerHTML = markup;
  const next = template.content.querySelector('.app-shell');
  if (!next) throw Error('fingpt_shell_missing');
  shell.className = next.className;
  for (const selector of ['.topbar', '.navigation-column']) {
    const old = shell.querySelector(selector), replacement = next.querySelector(selector);
    if (old && replacement) old.replaceWith(replacement);
  }
  for (const child of [...root.children]) if (child !== shell) child.remove();
  next.remove();
  root.append(...template.content.childNodes);
}

export async function mountFinGPT(root, fetcher = fetch) {
  const slot = root.querySelector('[data-fingpt-workspace]');
  if (!slot) return;
  if (frame) { slot.replaceWith(frame); return; }
  if (loading) return;
  loading = true;
  try {
    const response = await fetcher('/api/server/fingpt/workspace', { credentials: 'same-origin' });
    if (!response.ok) throw Error(response.status === 409 ? '请先在设置中绑定你的 WeKnora 账号。' : 'FinGPT 工作台暂时无法打开，请重试。');
    const data = await response.json();
    const entry = new URL(data.entry);
    if (!['https:', 'http:'].includes(entry.protocol) || entry.pathname !== '/rwb-fingpt.html') throw Error('FinGPT 工作台地址无效。');
    frame = document.createElement('iframe');
    frame.title = 'FinGPT 工作台'; frame.className = 'fingpt-native-frame';
    frame.referrerPolicy = 'no-referrer'; frame.src = entry.href;
    root.querySelector('[data-fingpt-workspace]')?.replaceWith(frame);
  } catch (error) {
    safeLog('fingpt_workspace_open_failed');
    const current = root.querySelector('[data-fingpt-workspace]');
    if (current) { current.textContent = error.message; const link = document.createElement('a'); link.href = '#/settings/data'; link.textContent = ' 打开知识库设置'; current.append(link); }
  } finally { loading = false; }
}
