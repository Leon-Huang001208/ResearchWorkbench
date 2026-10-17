import { e, list, text, readingLink, external, itemLink, image, timeLabel, jump } from './aihot-common.mjs';
import { safeURL } from './markdown.mjs';
import { sparkline } from './aihot-hot.mjs';

const tags = new Set('p br hr h1 h2 h3 h4 h5 h6 strong b em i u s del blockquote pre code ul ol li table thead tbody tfoot tr th td figure figcaption details summary a img span sup sub div'.split(' '));
export function renderReadingTree(nodes, depth = 0) {
  if (depth > 64) return '';
  return list(nodes).map(node => {
    if (typeof node.text === 'string') return e(node.text);
    if (!tags.has(node.tag)) return '';
    const tag = node.tag, attrs = node.attrs || {}, body = renderReadingTree(node.children, depth + 1);
    const id = /^sec-\d{1,5}$/.test(attrs.id || '') ? ` id="aihot-body-${e(attrs.id)}"` : '';
    if (tag === 'img') return image(attrs.src, text(attrs.alt), 'aihot-body-image');
    if (tag === 'a') {
      if (/^#sec-\d{1,5}$/.test(attrs.href || '')) return jump(`aihot-body-${attrs.href.slice(1)}`,body);
      const local = /^#\/aihot\/(item|story|topic)\/[A-Za-z0-9_-]{1,80}(?:\?lang=original)?$/.test(attrs.href || '');
      const href = local ? attrs.href : safeURL(attrs.href);
      return href && (local || /^https?:\/\//.test(href)) ? `<a href="${e(href)}" ${local ? '' : 'target="_blank" rel="noopener noreferrer"'}>${body}</a>` : body;
    }
    return `<${tag}${id}>${body}${['br','hr'].includes(tag) ? '' : `</${tag}>`}`;
  }).join('');
}
const topicLinks = topics => list(topics).map(topic => readingLink(`/topics/${topic.slug}`, topic.name, 'aihot-topic-chip')).join('');
const storyLinks = stories => list(stories).map(story => `<li>${readingLink(`/story/${story.publicId}`,story.title)}</li>`).join('');
const itemMeta = item => `<span>${e(item.source?.name || item.sourceName || '')}${item.source?.firstParty ? ' · 一手' : ''}${item.selected ? ' · 精选' : ''}</span><time>${e(timeLabel(item.publishedAt || item.discoveredAt || item.timelineAt))}${!item.publishedAt ? item.discoveredAt ? ' 收录' : ' 记录' : ''}</time>`;
function reportRow(item) {
  return `<article class="aihot-reading-row"><div class="aihot-detail-meta">${itemMeta(item)}</div><h3>${itemLink(item)}</h3>${item.summary ? `<details><summary>展开摘要</summary><p>${e(item.summary)}</p></details>` : ''}</article>`;
}
export function articleMarkdown(item) {
  function markdown(nodes) {
    return list(nodes).map(node => {
      if (typeof node.text === 'string') return node.text;
      if (!tags.has(node.tag)) return '';
      const body = markdown(node.children), tag = node.tag;
      if (/^h[1-6]$/.test(tag)) return `\n${'#'.repeat(Number(tag[1]))} ${body}\n\n`;
      if (tag === 'a') {
        const local = (node.attrs?.href || '').match(/^#\/aihot\/(item|story|topic)\/([A-Za-z0-9_-]{1,80})(?:\?lang=original)?$/);
        const href = local ? `${globalThis.location?.origin || ''}${globalThis.location?.pathname || '/'}${node.attrs.href}` : safeURL(node.attrs?.href);
        return href ? `[${body}](${href})` : body;
      }
      if (tag === 'img' && /^\/api\/research\/aihot\/media\/[a-f0-9]{64}$/.test(node.attrs?.src || '')) return `\n![${text(node.attrs.alt).replace(/[\[\]]/g,'')}](${globalThis.location?.origin || ''}${node.attrs.src})\n`;
      if (tag === 'strong' || tag === 'b') return `**${body}**`;
      if (tag === 'pre') return `\n\`\`\`\n${body}\n\`\`\`\n`;
      if (tag === 'li') return `- ${body}\n`;
      return `${body}${['p','div','br','blockquote','tr'].includes(tag) ? '\n\n' : ''}`;
    }).join('');
  }
  const quoted = item.x?.quoted;
  const quoteText = quoted && item.bodyLanguage !== 'original' && quoted.translation ? quoted.translation : quoted?.text;
  const media = list(item.x?.media).map(row => row.kind === 'image' ? markdown([{tag:'img',attrs:{src:row.url,alt:row.alt}}]) : '').join('');
  return `# ${item.title || ''}\n\n${item.source?.name || ''}\n\n${item.summary || ''}\n\n${markdown(item.body?.content)}${media}${quoteText ? `\n\n> ${quoted.authorName || ''}\n> ${quoteText.replace(/\n/g,'\n> ')}` : ''}\n\n来源：${item.links?.original || ''}\n`;

}
export function renderArticle(item) {
  const original = item.bodyLanguage === 'original';
  const outline = list(item.outline).filter(row => /^sec-\d{1,5}$/.test(row.id || ''));
  const notice = item.readingMode === 'summary-only' ? '上游仅提供摘要，暂未提供可在站内阅读的完整正文。' : !item.body?.content?.length ? '正文暂未提供；以下保留摘要与关联阅读。' : item.body.complete === false ? '当前正文尚未完整提供，可切换原文查看上游已提供内容。' : '';
  return `<article class="aihot-detail aihot-article"><header><div class="aihot-detail-meta">${itemMeta(item)}${item.author ? `<span>${e(item.author)}</span>` : ''}</div><h1>${e(item.title)}</h1>${item.originalTitle ? `<p class="aihot-original-title">${e(item.originalTitle)}</p>` : ''}<div class="aihot-reading-actions"><button data-aihot-copy="link">复制链接</button><button data-aihot-copy="markdown">复制 Markdown</button><button data-aihot-download>导出 Markdown</button><span role="status">${e(item.actionNotice || '')}</span></div></header>${item.summary ? `<p class="aihot-detail-summary">${e(item.summary)}</p>` : ''}${item.reason ? `<aside class="aihot-panel"><h2>为什么值得读</h2><p>${e(item.reason)}</p>${typeof item.score === 'number' ? `<small>AI 评分 ${e(item.score)}</small>` : ''}</aside>` : ''}${notice ? `<p class="notice">${notice}</p>` : ''}<details class="aihot-mobile-outline"><summary>文章目录</summary>${outline.map(row => jump(`aihot-body-${row.id}`,e(row.text))).join('')}</details><div class="aihot-detail-grid"><div><section class="aihot-panel"><header><h2>${original ? '正文 · 原文' : item.body?.zhKind === 'translation' ? '正文 · AI 翻译' : '正文'}</h2>${item.hasTranslation ? `<nav aria-label="正文语言"><a href="#/aihot/item/${e(item.id)}" ${!original ? 'aria-current="page"' : ''}>中文</a><a href="#/aihot/item/${e(item.id)}?lang=original" ${original ? 'aria-current="page"' : ''}>原文</a></nav>` : ''}</header><div class="aihot-article-body">${renderReadingTree(item.body?.content)}</div>${item.x?.media ? `<div class="aihot-media-gallery">${list(item.x.media).map(media => `${image(media.url || media.poster, media.alt || '', 'aihot-body-image')}${media.fullUrl ? `<details><summary>查看大图</summary>${image(media.fullUrl,media.alt || '', 'aihot-body-image')}</details>` : ''}`).join('')}</div>` : ''}${item.x?.quoted?.text ? `<blockquote><strong>${e(item.x.quoted.authorName || '引用')}</strong><p>${e(!original && item.x.quoted.translation ? item.x.quoted.translation : item.x.quoted.text)}</p></blockquote>` : ''}</section>${item.sameEvent ? `<aside class="aihot-panel">同一事件：${itemLink(item.sameEvent)}</aside>` : ''}${item.story ? `<section class="aihot-panel"><h2>继续了解事件</h2>${readingLink(`/story/${item.story.publicId}`,item.story.title)}${item.group ? `<p>${e(item.group.reportCount)} 篇报道 · ${e(item.group.additionalSourceCount)} 个其他来源</p><button data-aihot-group ${item.groupLoading ? 'disabled' : ''}>${item.groupLoading ? '正在读取…' : '查看同一新闻的全部来源'}</button>${item.groupError ? `<p role="alert">${e(item.groupError)}</p>` : ''}${list(item.groupReports).map(reportRow).join('')}` : ''}</section>` : ''}${list(item.relatedStories).length ? `<section class="aihot-panel"><h2>关联专题</h2><ul>${storyLinks(item.relatedStories)}</ul></section>` : ''}<footer class="aihot-panel">${external(item.links?.original,'访问信息来源 ↗')}</footer></div><aside class="aihot-detail-rail">${outline.length ? `<nav class="aihot-panel" aria-label="文章目录"><h2>文章目录</h2>${outline.map(row => jump(`aihot-body-${row.id}`,e(row.text))).join('')}</nav>` : ''}<section class="aihot-panel"><h2>相关主题</h2>${topicLinks(item.topics)}<div>${(Array.isArray(item.tags) ? item.tags : []).map(tag => `<span class="aihot-badge">${e(tag)}</span>`).join('')}</div></section></aside></div></article>`;
}
export function renderStory(story, view = {}) {
  const filter = view.filter || 'all', order = view.order || 'desc';
  const ordered = rows => [...list(rows)].sort((a,b) => (text(a.publishedAt || a.firstReportAt).localeCompare(text(b.publishedAt || b.firstReportAt))) * (order === 'asc' ? 1 : -1));
  const rows = ordered(list(story.timeline).filter(row => filter === 'official' ? row.source?.firstParty : filter === 'selected' ? row.selected : true));
  const why = story.whyHot || {}, heat = list(story.heat);
  const overview = story.digest || story.summary || story.excerpt?.text;
  return `<article class="aihot-detail aihot-event-detail"><header><div class="aihot-detail-meta"><span>${e(({active:'持续发展',settled:'已归档',emerging:'新兴事件'})[story.status] || story.status || '事件专题')}</span><span>${e(story.reportCount ?? list(story.timeline).length)} 篇报道 · ${e(story.sourceCount ?? '—')} 个来源</span></div><h1>${e(story.title)}</h1><nav class="aihot-reading-actions" aria-label="专题内容导航">${jump('aihot-story-overview','事件概览')}${jump('aihot-story-reports','报道时间线')}${jump('aihot-story-heat','热度走势')}</nav></header><div class="aihot-detail-grid"><div><section class="aihot-panel" id="aihot-story-overview"><h2>先了解这件事</h2><p class="aihot-detail-summary">${e(overview || '还没有综述，先看下面的报道时间线。')}</p>${story.digestUpdatedAt ? `<small>综述更新 ${e(timeLabel(story.digestUpdatedAt))}</small>` : ''}${story.latest ? `<h3>最新进展</h3><p>${story.latestReport?.id ? itemLink({id:story.latestReport.id,title:story.latest}) : e(story.latest)}</p>` : ''}</section>${list(story.developments).length ? `<section class="aihot-panel"><h2>事件进展 · ${story.developments.length} 项</h2>${ordered(story.developments).map(row => `<article class="aihot-reading-row"><small>${e(timeLabel(row.firstReportAt))} · ${e(row.reportCount)} 篇报道</small><h3>${itemLink(row.representative || {},row.title)}</h3><p>${e(row.representative?.source?.name || '')}</p></article>`).join('')}</section>` : ''}<section class="aihot-panel" id="aihot-story-reports"><h2>报道时间线</h2><div class="aihot-reading-actions" aria-label="报道筛选">${[['all','全部报道'],['official','官方一手'],['selected','精选报道']].map(([key,label]) => `<button data-aihot-filter="${key}" aria-pressed="${key === filter}">${label}</button>`).join('')}<button data-aihot-order="${order === 'desc' ? 'asc' : 'desc'}">${order === 'desc' ? '最新在前 ↓' : '最早在前 ↑'}</button></div>${rows.map(reportRow).join('') || '<p>这个筛选下没有报道。</p>'}${story.reportCount > list(story.timeline).length ? `<p>显示最近 ${list(story.timeline).length} 篇，共 ${e(story.reportCount)} 篇；以上为上游当前提供的报道范围。</p>` : ''}</section><section class="aihot-panel" id="aihot-story-heat"><h2>本事件热度走势</h2>${sparkline(heat.map(point => Number.isFinite(point.heat) ? point.heat : null),'story',true)}${heat.length ? `<small>${e(timeLabel(heat[0].hour))} — ${e(timeLabel(heat.at(-1).hour))}</small>` : '<p>暂无可比热度历史。</p>'}</section>${list(story.related).length ? `<section class="aihot-panel"><h2>关联事件</h2><ul>${storyLinks(story.related)}</ul></section>` : ''}</div><aside class="aihot-detail-rail"><section class="aihot-panel"><h2>为什么热</h2><p>48 小时内 ${e(why.participants48h ?? '—')} 个独立参与者；近 6 小时新增 ${e(why.newParticipants6h ?? '—')} 个。</p><p>24 小时内 ${e(why.recentReports24h ?? '—')} 篇报道${why.rank ? ` · 热点榜第 ${e(why.rank)} 名` : ''}</p>${why.observationComplete === false ? '<p>部分信源观测不完整，仅代表已观察范围。</p>' : ''}</section><section class="aihot-panel"><h2>官方一手</h2>${list(story.officialReports).map(reportRow).join('') || '<p>暂无官方报道。</p>'}</section><section class="aihot-panel"><h2>相关主题</h2>${topicLinks(story.topics)}<p>首次报道 ${e(timeLabel(story.firstReportAt))}</p><p>最近进展 ${e(timeLabel(story.latestAt))}</p></section></aside></div></article>`;
}
export function renderTopic(page) {
  const topic = page.topic || {}, chronicle = page.modules?.chronicle || {};
  const milestones = [...list(chronicle.chronicle),...list(chronicle.milestones),...list(chronicle.highlights)];
  return `<article class="aihot-detail aihot-topic"><header><small>${e(topic.groupName || '主题专题')}</small><h1>${e(topic.name)}</h1><p class="aihot-detail-summary">${e(topic.definition)}</p><p>${e(topic.total ?? '—')} 篇精选 · 近期 ${e(topic.recent ?? '—')} 篇</p></header>${milestones.length || chronicle.status==='local_evidence' ? `<details class="aihot-panel" open><summary>主题大事记 · ${milestones.length} 项</summary>${chronicle.scope ? `<p>${e(chronicle.scope)}</p>` : ''}${!milestones.length ? '<p>自主库暂无可追溯报道，尚不形成历史大事记。</p>' : ''}<ol>${milestones.map(row => `<li><time>${e(row.date || timeLabel(row.at))}${row.timeKind ? ` · ${e(({event:'事件发生',publication:'报道发布',collection:'本机收录'})[row.timeKind] || '时间未确认')}` : ''}</time>${row.provenance ? `<p>发布时间 ${e(timeLabel(row.publishedAt))} · 事件发生 ${e(timeLabel(row.occurredAt))} · 本机收录 ${e(timeLabel(row.collectedAt))}</p>` : ''}<h3>${row.href ? readingLink(row.href,row.title || row.label) : e(row.title || row.label)}</h3>${row.summary ? `<p>${e(row.summary)}</p>` : ''}</li>`).join('')}</ol></details>` : ''}<section class="aihot-panel"><h2>主题报道</h2>${list(page.items).map(reportRow).join('') || '<p>暂无报道。</p>'}<nav class="aihot-pagination" aria-label="主题分页">${page.page > 1 ? `<a href="#/aihot/topic/${e(topic.slug)}?page=${page.page - 1}">上一页</a>` : ''}<span>第 ${e(page.page)} / ${e(page.pageCount)} 页</span>${page.page < page.pageCount ? `<a href="#/aihot/topic/${e(topic.slug)}?page=${page.page + 1}">下一页</a>` : ''}</nav></section></article>`;
}
