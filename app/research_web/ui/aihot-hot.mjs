// AIHOT hot cards and monotone heat geometry adapted under MIT; see third-party notice.
import { e, list, text, external, image, timeLabel, jump } from './aihot-common.mjs';

export function observedRuns(values) {
  const runs = []; let run = [];
  values.forEach((v, i) => { if (Number.isFinite(v) && v >= 0) run.push(i); else if (run.length) { runs.push(run); run = []; } });
  if (run.length) runs.push(run);
  return runs;
}
const f = n => +n.toFixed(2);
export function curvePath(points) {
  if (!points.length) return '';
  if (points.length === 1) return `M${f(points[0][0])} ${f(points[0][1])}h0`;
  const slopes = points.slice(1).map(([x, y], i) => (y - points[i][1]) / (x - points[i][0] || 1));
  const tangents = points.map((_, i) => i === 0 ? slopes[0] : i === points.length - 1 ? slopes.at(-1) : slopes[i - 1] * slopes[i] <= 0 ? 0 : 2 * slopes[i - 1] * slopes[i] / (slopes[i - 1] + slopes[i]));
  let path = `M${f(points[0][0])} ${f(points[0][1])}`;
  for (let i = 0; i < points.length - 1; i++) {
    const [x0, y0] = points[i], [x1, y1] = points[i + 1], h = (x1 - x0) / 3;
    path += `C${f(x0 + h)} ${f(y0 + tangents[i] * h)} ${f(x1 - h)} ${f(y1 - tangents[i + 1] * h)} ${f(x1)} ${f(y1)}`;
  }
  return path;
}
export function sparkline(values, id, large = false) {
  const safe = Array.isArray(values) ? values.slice(0, 49) : [];
  const seen = safe.filter(v => Number.isFinite(v) && v >= 0);
  if (seen.length < 3) return `<span class="aihot-spark-empty" title="缺少可比历史，不展示趋势线"></span>`;
  const max = Math.max(...seen) || 1;
  const runs = observedRuns(safe).map(run => run.map(i => [i / Math.max(1, safe.length - 1) * 100, (1 - safe[i] / max) * 100]));
  const end = runs.at(-1).at(-1);
  return `<svg class="aihot-spark ${large ? 'large' : ''}" viewBox="0 0 100 100" preserveAspectRatio="none" role="img" aria-label="近24小时热度走势${seen.length < safe.length ? '，部分时段缺少可比数据' : ''}"><defs><linearGradient id="aihot-spark-${id}" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="currentColor" stop-opacity=".20"/><stop offset="1" stop-color="currentColor" stop-opacity="0"/></linearGradient></defs>${runs.map(points => `${points.length > 1 ? `<path d="${curvePath(points)}L${f(points.at(-1)[0])} 100L${f(points[0][0])} 100Z" fill="url(#aihot-spark-${id})"/>` : ''}<path d="${curvePath(points)}" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linejoin="round" stroke-linecap="round" vector-effect="non-scaling-stroke"/>`).join('')}<path d="M${f(end[0])} ${f(end[1])}h0" stroke="currentColor" stroke-width="4.5" stroke-linecap="round" vector-effect="non-scaling-stroke"/></svg>`;
}
function delta(entry) {
  const trend = entry.trend;
  const hint = trend === 'unknown' ? '部分信源采集暂时落后，先不和6小时前比较' : '较6小时前';
  const label = trend === 'unknown' ? '暂不比较' : trend === 'new' || entry.trendPct === null ? '新上榜' : trend === 'flat' ? '持平' : Number.isFinite(entry.trendPct) ? `${trend === 'up' ? '↑' : '↓'} ${Math.abs(Math.round(entry.trendPct))}%` : '暂不比较';
  return `<span class="aihot-delta ${['up', 'down', 'new', 'unknown'].includes(trend) ? trend : 'flat'}" title="${hint}">${label}</span>`;
}
const badgeLabels = { surge: ['爆', '讨论快速增加'], new: ['新', '首报6小时内'], rising: ['发酵中', '讨论仍在增加'] };
const badges = entry => (Array.isArray(entry.badges) ? entry.badges : []).filter(id => badgeLabels[id]).map(id => `<span class="aihot-badge ${id}" title="${badgeLabels[id][1]}">${badgeLabels[id][0]}</span>`).join('');
function faces(entry, rank) {
  const people = list(entry.participants);
  const editorial = people.filter(p => p.kind === 'editorial'), signal = people.filter(p => p.kind !== 'editorial');
  const shown = editorial.slice(0, 5);
  const total = Number.isInteger(entry.participantCount) ? entry.participantCount : people.length;
  const group = (items, title) => items.length ? `<h4>${title}</h4><ul>${items.map(p => `<li>${image(p.iconUrl, '', 'aihot-avatar')}<span>${e(text(p.name))}</span></li>`).join('')}</ul>` : '';
  return `<details class="aihot-faces"><summary aria-label="${total}位参与者，查看名单" title="${e(people.map(p => p.name).join('、'))}">${shown.map(p => `<span class="aihot-face"><b>${e(text(p.name).slice(0, 1))}</b>${image(p.iconUrl, '', 'aihot-avatar')}</span>`).join('')}${total > shown.length ? `<span class="aihot-face-more">+${total - shown.length}</span>` : ''}</summary><div class="aihot-participants" role="region" aria-label="第${rank}名参与者名单">${group(editorial, '报道来源 · 精选组')}${group(signal, '讨论参与者 · 氛围组')}${total > people.length ? `<p>另外 ${total - people.length} 位参与者</p>` : ''}</div></details>`;
}
const storyTitle = entry => external(entry.story?.publicId ? `https://aihot.news/story/${encodeURIComponent(entry.story.publicId)}` : null, text(entry.story?.title), 'aihot-story-link');
const heat = entry => Number.isFinite(entry.heat) ? Math.round(entry.heat) : '—';
function voices(entry, long = false) {
  const names = (Array.isArray(entry.sourceNames) ? entry.sourceNames : []).slice(0, 2).map(text);
  return `<span class="aihot-voices">${long && names.length ? `<span>${e(names.join('、'))}${entry.sourceCount > names.length ? ` 等 ${e(entry.sourceCount)} 个来源` : ' 报道'}</span>` : `<span>${e(entry.sourceCount ?? '—')} 个来源</span>`}<i>·</i><span>${e(entry.participantCount ?? '—')} 位参与者</span></span>`;
}
function lead(entry) {
  const panel = !entry.cover && (Array.isArray(entry.spark) ? entry.spark : []).filter(Number.isFinite).length >= 3;
  const peak = Math.max(0, ...(Array.isArray(entry.spark) ? entry.spark : []).filter(Number.isFinite));
  const peakAt = Array.isArray(entry.spark) ? entry.spark.indexOf(peak) : -1;
  return `<article class="aihot-hot-lead aihot-hot-card"><div class="aihot-hot-card-top"><b class="aihot-rank rank-${entry.rank}">NO.${String(entry.rank).padStart(2, '0')}</b>${badges(entry)}${delta(entry)}</div><div class="aihot-hot-lead-main ${entry.cover || panel ? 'with-visual' : ''}"><div><h2>${storyTitle(entry)}</h2>${entry.summary ? `<p class="aihot-hot-summary">${e(entry.summary)}</p>` : ''}</div>${entry.cover ? image(entry.cover, '', 'aihot-hot-cover', true) : panel ? `<div class="aihot-heat-panel"><div><b>24 小时热度</b><span>峰值 ${Math.round(peak)} · ${peakAt === entry.spark.length - 1 ? '当前' : `${entry.spark.length - 1 - peakAt} 小时前`}</span></div>${sparkline(entry.spark, `lead${entry.rank}`, true)}<div><span>24 小时前</span><span>现在</span></div></div>` : ''}</div><div class="aihot-hot-lead-bottom"><div>${entry.latest ? `<p class="aihot-latest"><b>最新进展</b>${e(entry.latest)}</p>` : ''}<div class="aihot-voices-row">${faces(entry, entry.rank)}${voices(entry, true)}</div></div><div class="aihot-heat-block">${!panel ? sparkline(entry.spark, `mini${entry.rank}`) : ''}<div><strong>${heat(entry)}</strong><small>热度指数</small></div></div></div></article>`;
}
function runner(entry) {
  return `<article class="aihot-hot-runner aihot-hot-card"><div class="aihot-hot-card-top"><b class="aihot-rank rank-${entry.rank}">NO.${String(entry.rank).padStart(2, '0')}</b>${badges(entry)}${delta(entry)}</div><h2>${storyTitle(entry)}</h2>${entry.summary ? `<p class="aihot-hot-summary">${e(entry.summary)}</p>` : ''}<div class="aihot-hot-runner-bottom"><div>${faces(entry, entry.rank)}${voices(entry)}</div><div class="aihot-heat-block">${sparkline(entry.spark, `runner${entry.rank}`)}<strong>${heat(entry)}</strong></div></div></article>`;
}
function row(entry) {
  return `<li class="aihot-hot-row"><b class="aihot-rank rank-${entry.rank}" aria-label="热度排名第 ${entry.rank} 位">${String(entry.rank).padStart(2, '0')}</b><div><h3>${storyTitle(entry)}${badges(entry)}</h3>${entry.summary ? `<p class="aihot-hot-summary">${e(entry.summary)}</p>` : ''}<div class="aihot-row-mobile">${voices(entry)}</div></div>${faces(entry, entry.rank)}${sparkline(entry.spark, `row${entry.rank}`)}<div class="aihot-row-heat"><strong>${heat(entry)}</strong>${delta(entry)}</div></li>`;
}
export function renderHot(hot = {}) {
  const entries = list(hot.entries).filter(entry => Number.isInteger(entry.rank) && entry.rank > 0 && entry.rank <= 10), [first, ...rest] = entries;
  return `<div class="aihot-hot-page"><header class="aihot-hot-header"><div><span class="aihot-live">● 实时热度</span><h1>AI 热点榜</h1><p>过去 ${e(hot.windowHours ?? '—')} 小时，AI 圈讨论最多的 ${entries.length || 10} 件事</p></div><div><small>${e(timeLabel(hot.computedAt))} 更新 · 按讨论热度排序</small>${jump('aihot-hot-method', 'ⓘ 怎么算')}</div></header>${first ? `<section class="aihot-hot-podium" aria-label="热度前三">${lead(first)}${rest.slice(0, 2).map(runner).join('')}</section>${rest.length > 2 ? `<section class="aihot-hot-rest" aria-label="其余热点"><header><h2>继续看 <span>No.${String(rest[2].rank).padStart(2, '0')}–${String(rest.at(-1).rank).padStart(2, '0')}</span></h2><small>参与者 · 24 小时走势 · 热度指数</small></header><ol>${rest.slice(2).map(row).join('')}</ol></section>` : ''}` : '<div class="aihot-empty"><h2>暂时没有热点</h2><p>还没有足够多来源共同讨论的事件。</p></div>'}<details class="aihot-hot-method" id="aihot-hot-method"><summary>ⓘ 热度是怎么算的？<span>了解榜单 / 收起⌄</span></summary><div><p>热度来自参与同一事件的独立账号与机构，重复采集只算一次，并按24小时半衰期衰减。它衡量讨论活跃程度，不是报道质量评分。</p><p>榜单统计过去48小时。趋势只比较持续覆盖的同一组信源；它反映监测范围，不代表全网人数。缺少可比历史时，不展示趋势线。</p><p>信源名单只展示可公开阅读的报道来源；讨论参与者还包括只计入热度的账号与机构。同一机构的多个渠道可能合并计数，因此参与者不一定多于信源数。点击事件可查看各方报道与观点。</p><div class="aihot-badge-guide">${Object.entries(badgeLabels).map(([id, [label, hint]]) => `<span><b class="aihot-badge ${id}">${label}</b>${hint}</span>`).join('')}</div></div></details></div>`;
}
