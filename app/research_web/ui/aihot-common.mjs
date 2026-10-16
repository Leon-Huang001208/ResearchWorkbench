import { escapeHTML, safeURL } from './markdown.mjs';
export const e = escapeHTML;
export const list = value => Array.isArray(value) ? value.filter(item => item && typeof item === 'object') : [];
export const text = value => typeof value === 'string' || typeof value === 'number' ? String(value) : '';
export const kinds = { daily: '日报', weekly: '周报', monthly: '月报' };
export const reportHash = (kind, key = '') => `#/aihot/${kind}${key ? `?date=${encodeURIComponent(key)}` : ''}`;
export function external(value, label, className = '') {
  const url = safeURL(value);
  return url && /^https?:\/\//.test(url) ? `<a class="${e(className)}" href="${e(url)}" target="_blank" rel="noopener noreferrer">${e(label)}</a>` : e(label);
}
export function readingLink(value, label, className = '') {
  if (typeof value === 'string') {
    try {
      const url = new URL(value, 'https://aihot.news');
      const match = url.origin === 'https://aihot.news' && url.pathname.match(/^\/(items|story|topics)\/([A-Za-z0-9_-]{1,80})(\/original)?\/?$/);
      if (match) return `<a class="${e(className)}" href="#/aihot/${({items:'item',story:'story',topics:'topic'})[match[1]]}/${e(match[2])}${match[3] ? '?lang=original' : ''}">${e(label)}</a>`;
    } catch { /* Invalid publisher destinations remain inert. */ }
  }
  return external(value, label, className);
}
export const itemLink = (item, label = item.title) => item.available === false ? `<span class="aihot-withdrawn">${e(label)}</span>` : readingLink((item.itemId || item.id) ? `https://aihot.news/items/${encodeURIComponent(item.itemId || item.id)}` : item.sourceUrl, label);
export const imageURL = value => typeof value === 'string' && /^\/api\/research\/aihot\/media\/[a-f0-9]{64}$/.test(value) ? value : null;
export function image(value, alt = '', className = '', eager = false) {
  const url = imageURL(value?.url || value);
  if (!url) return '';
  const srcSet = text(value?.srcSet);
  const safeSet = srcSet && srcSet.split(',').every(part => /^\/api\/research\/aihot\/media\/[a-f0-9]{64} \d+w$/.test(part.trim()));
  return `<img class="${e(className)}" src="${e(url)}" ${safeSet ? `srcset="${e(srcSet)}" sizes="(min-width:1100px) 740px, 100vw"` : ''} alt="${e(alt)}" loading="${eager ? 'eager' : 'lazy'}" decoding="async" referrerpolicy="no-referrer">`;
}
export function timeLabel(value) {
  if (!value) return '时间未提供';
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? '时间未提供' : date.toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false });
}
export function weekday(key, short = false) {
  const date = new Date(`${key}T00:00:00+08:00`);
  return Number.isNaN(date.valueOf()) ? '' : date.toLocaleDateString('zh-CN', { timeZone: 'Asia/Shanghai', weekday: short ? 'short' : 'long' });
}
export const source = item => `<span class="aihot-source"><span class="aihot-source-icon"><b>${e(text(item.sourceName).slice(0,1) || '·')}</b>${image(item.sourceIconUrl, '', 'aihot-avatar')}</span><span>${e(text(item.sourceName))}</span>${item.firstParty ? '<span class="aihot-badge accent">一手</span>' : ''}</span>`;
export const coverage = item => `${item.otherSources > 0 ? `<span class="muted">另外 ${e(item.otherSources)} 家也报道了</span>` : ''}${item.followUp ? `<span class="aihot-badge" title="${e(item.followUp)} 的日报报道过，这里是新进展">跟进</span>` : ''}`;
export function related(items) {
  return list(items).length ? `<ul class="aihot-related">${list(items).slice(0, 4).map(item => `<li>${itemLink(item)}<span>${e(text(item.sourceName))}</span>${item.available === false ? '<small>内容已撤回或调整</small>' : ''}</li>`).join('')}</ul>` : '';
}
export function jump(id, label, className = '') {
  return `<button type="button" class="aihot-jump ${e(className)}" data-aihot-jump="${e(id)}">${label}</button>`;
}
