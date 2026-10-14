import { escapeHTML as e } from '../markdown.mjs';
import { frameworkBot } from './common.mjs';
import { isNativeFramework } from './embed-bridge.mjs';

export function renderEmbedded({ framework, snapshot }, { bot = {} } = {}) {
  const native = isNativeFramework(framework.slug);
  const embedUrl = framework.display?.url || `/frameworks-embed/${framework.slug}/`;
  return `<article class="framework-detail embedded-framework" data-framework="${e(framework.slug)}" data-framework-revision="${e(snapshot.revision)}">
    <nav class="embedded-toolbar" aria-label="框架导航"><a class="framework-back" href="#/frameworks">← 研究框架</a><span>${native ? `原生数据快照 · ${e(snapshot.as_of || '尚无观测')} · ${e(snapshot.revision.slice(0, 8))}` : `静态导入 · ${e(framework.display?.imported_at || '2026-10-14')}`}</span>${native ? '<button type="button" data-framework-retry>刷新快照</button>' : ''}<a class="embedded-open-link" href="#/frameworks/${e(framework.slug)}" target="_blank" rel="noreferrer" aria-label="在新标签页打开${e(framework.name)}">↗ 打开</a></nav>
    <div class="embedded-native-layout"><div class="embedded-iframe-wrap"><iframe ${native ? 'data-native-framework' : ''} data-slug="${e(framework.slug)}" data-revision="${e(snapshot.revision)}" src="${e(embedUrl)}" title="${e(framework.name)}" loading="eager" allow="fullscreen"></iframe></div>${native ? `<div data-framework-bot-slot>${renderEmbeddedBot(snapshot, bot)}</div>` : ''}</div>
  </article>`;
}

export function renderEmbeddedBot(snapshot, bot = {}) {
  const boundRevision = bot.revision || snapshot.revision;
  const stale = Boolean(bot.sessionId && boundRevision !== snapshot.revision);
  const viewBot = { ...bot, busy: bot.busy || !bot.bridgeReady, ...(stale ? { errorCode: 'framework_snapshot_changed' } : {}) };
  return frameworkBot(viewBot, boundRevision);
}
