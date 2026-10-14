import { escapeHTML as e } from '../markdown.mjs';

export function renderEmbedded({ framework, snapshot }, { bot = {} } = {}) {
  const app = snapshot.external_app || {};
  const embedUrl = app.url || `/frameworks-embed/${framework.slug}/`;
  return `<article class="framework-detail embedded-framework" data-framework="${e(framework.slug)}" data-framework-revision="${e(snapshot.revision)}">
    <nav class="embedded-toolbar" aria-label="框架导航"><a class="framework-back" href="#/frameworks">← 研究框架</a><a class="embedded-open-link" href="${e(embedUrl)}" target="_blank" rel="noreferrer" aria-label="在新标签页打开${e(framework.name)}">↗ 打开</a></nav>
    <div class="embedded-iframe-wrap"><iframe src="${e(embedUrl)}" title="${e(framework.name)}" loading="eager" allow="fullscreen"></iframe></div>
  </article>`;
}

