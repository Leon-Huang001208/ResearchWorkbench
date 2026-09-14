import { escapeHTML as e } from '../markdown.mjs';

const statusLabel = {
  complete: '完整', partial: '部分', stale: '过期', proxy: '代理', missing: '缺失', fixture: '固定样例',
};

export function blockSources(block) {
  const names = (block?.sources || []).map((item) => typeof item === 'string' ? item : item.name);
  return `<footer class="framework-source-strip"><span>观测 ${e(block?.as_of || '—')}</span><span>检查 ${e(block?.checked_at || block?.fetched_at || '—')}</span><span>状态 ${e(statusLabel[block?.status] || block?.status || '—')}</span><span>${e(names.join(' · ') || '暂无来源')}</span>${block?.failure_code ? `<span class="framework-gap">${e(block.failure_code)}</span>` : ''}${block?.gaps?.length ? `<span class="framework-gap">缺口 ${block.gaps.length}</span>` : ''}</footer>`;
}

export function frameworkPanel(title, subtitle, content, extra = '') {
  return `<section class="framework-panel ${extra}"><header><div><h3>${e(title)}</h3><p>${e(subtitle)}</p></div></header>${content}</section>`;
}

export function chapterHeading(id, index, label, question) {
  return `<header class="framework-chapter-heading"><span class="mono">${String(index).padStart(2, '0')}</span><div><h2 id="framework-${e(id)}-title">${e(label)}</h2><p>${e(question)}</p></div></header>`;
}

export function evidenceList(items) {
  return `<div class="framework-evidence-list">${items.map((item) => `<article><time class="mono">${e(item.date)}</time><div><strong>${e(item.observation)}</strong><p><a href="${e(item.url || '#')}" target="_blank" rel="noreferrer">${e(item.source)}</a> · ${e(item.use)}</p></div><span>${e(item.quality)}</span></article>`).join('')}</div>`;
}

export function frameworkBot(bot, revision, example = '为什么当前状态仍然是“待核验”？') {
  if (!bot?.open) return '<button class="framework-bot-launch" type="button" data-framework-bot-open><span aria-hidden="true">✦</span><strong>问框架</strong><small>基于当前快照解释</small></button>';
  const messages = (bot.detail?.messages || []).map((item) => `<article class="framework-bot-message ${e(item.role || 'assistant')}"><span>${item.role === 'user' ? '你' : bot.mode === 'verify' ? '验证' : '框架'}</span><p>${e(item.text || '')}</p></article>`).join('');
  const stale = bot.errorCode === 'framework_snapshot_changed';
  return `<aside class="framework-bot" aria-label="框架对话" data-revision="${e(revision)}">
    <header><div><span class="eyebrow">DSH · ${bot.mode === 'verify' ? 'DEEP VERIFY' : 'EXPLAIN'}</span><h2>${bot.mode === 'verify' ? '深度验证' : '问当前框架'}</h2></div><button type="button" data-framework-bot-close aria-label="关闭框架对话">×</button></header>
    <div class="framework-bot-context"><span>绑定快照</span><strong class="mono">${e(revision.slice(0, 8))}</strong><small>${bot.mode === 'verify' ? '只读检索已启用；不会改写框架状态' : '无工具解释；不会自行补造数据'}</small></div>
    <div class="framework-bot-thread" aria-live="polite">${messages || `<div class="framework-bot-empty"><strong>可以从结论、反证或数据缺口开始。</strong><p>例如：${e(example)}</p></div>`}${bot.busy ? '<div class="framework-bot-thinking" role="status">DSH 正在处理…</div>' : ''}</div>
    ${stale ? '<div class="framework-bot-stale" role="alert">数据已更新。为避免证据漂移，请关闭后基于新快照重新开始。</div>' : bot.error ? `<div class="framework-bot-error" role="alert">${e(bot.error)}</div>` : ''}
    <form class="framework-bot-form" data-framework-bot-form><label for="framework-bot-input">问题</label><textarea id="framework-bot-input" name="question" rows="3" placeholder="围绕当前结论、图表或缺口提问…" ${bot.busy || stale ? 'disabled' : ''}>${e(bot.draft || '')}</textarea><div><button class="button" type="button" data-framework-verify ${!bot.sessionId || bot.busy || stale ? 'disabled' : ''}>深度验证</button><button class="button primary" type="submit" ${bot.busy || stale ? 'disabled' : ''}>发送</button></div></form>
  </aside>`;
}

export function anchorRail(framework, slug, anchor, label) {
  const links = framework.sections.map((item, index) => `<a href="#/frameworks/${e(slug)}?tab=${e(item.id)}" data-framework-anchor="${e(item.id)}" class="${item.id === anchor ? 'active' : ''}" ${item.id === anchor ? 'aria-current="location"' : ''}><span class="mono">${String(index + 1).padStart(2, '0')}</span>${e(item.label)}</a>`).join('');
  return `<nav class="framework-anchor-rail" aria-label="${e(label)}">${links}</nav>`;
}

export function sourceNames(block, fallback = '暂无来源') {
  return (block?.sources || []).map((item) => item.name || item).join(' · ') || fallback;
}
