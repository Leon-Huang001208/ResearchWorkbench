import { escapeHTML as e } from '../../markdown.mjs';

const finite = (value) => Number.isFinite(Number(value));
const jitter = (seed, salt = 1) => {
  const value = Math.sin(seed * 12.9898 + salt * 78.233) * 43758.5453;
  return value - Math.floor(value);
};

function chartFailure(name) {
  console.warn('[ResearchWeb] framework_chart_invalid', { chart: name, status: 'invalid_data' });
  return `<div class="framework-chart-error" role="status">${e(name)}暂时无法显示。</div>`;
}

function shell({ id, title, conclusion, source, body, legend }) {
  return `<figure class="lieflat-chart" data-lieflat-basics="${e(id)}">
    <header><div><span class="eyebrow">LIEFLAT BASICS · ${e(id)}</span><h3>${e(title)}</h3></div><strong>${e(conclusion)}</strong></header>
    <svg viewBox="0 0 400 326" role="img" aria-labelledby="${e(id)}-title ${e(id)}-desc">
      <title id="${e(id)}-title">${e(title)}</title><desc id="${e(id)}-desc">${e(conclusion)}；图中提供完整数值标签。</desc>${body}
    </svg>
    <figcaption><span>${e(legend)}</span><span>来源：${e(source)}</span></figcaption>
  </figure>`;
}

export function hairlineLine(points = [], source = '固定样例') {
  if (points.length < 2 || points.length > 30 || points.some((item) => !item?.label || !finite(item.value))) return chartFailure('价格背景');
  const values = points.map((item) => Number(item.value));
  const min = Math.min(...values); const max = Math.max(...values); const span = max - min || 1;
  const x = (index) => 30 + index * (340 / Math.max(1, points.length - 1));
  const base = 262; const map = (value) => 238 - ((value - min) / span) * 160;
  const peaks = [];
  for (const index of [...values.keys()].sort((a, b) => values[b] - values[a])) {
    if (peaks.every((other) => Math.abs(other - index) >= 3)) peaks.push(index);
    if (peaks.length === 2) break;
  }
  const floor = points.map((_, index) => `<line class="lf-grid lf-reveal" style="--delay:${index * 12}ms" x1="${x(index)}" y1="${base}" x2="${x(index)}" y2="${base - 7}"/>`).join('');
  const dots = points.map((item, index) => {
    const peak = peaks.includes(index); const weekend = index % 7 >= 5;
    return `<g class="lf-reveal" style="--delay:${180 + index * 24}ms"><circle class="lf-dot ${weekend ? 'hollow' : ''}" cx="${x(index)}" cy="${map(item.value)}" r="${peak ? 4.2 : 2.1}"><title>${e(item.label)} · ${Number(item.value).toFixed(1)}</title></circle>${peak ? `<text class="lf-number" x="${x(index)}" y="${map(item.value) - 12}" text-anchor="middle">${Number(item.value).toFixed(0)}</text>` : ''}</g>`;
  }).join('');
  const labels = [0, Math.floor((points.length - 1) / 2), points.length - 1].map((index) => `<text class="lf-label" x="${x(index)}" y="282" text-anchor="middle">${e(points[index].label)}</text>`).join('');
  const path = points.map((item, index) => `${x(index)} ${map(item.value)}`).join(' L ');
  return shell({ id: 'F2', title: '价格背景', conclusion: `样例价格接近区间上沿 ${max.toFixed(0)}`, source, legend: '一圆点 = 一期 · 空心点仅用于区分节律', body: `${floor}<line class="lf-grid" x1="24" y1="${base}" x2="376" y2="${base}"/><path class="lf-ink lf-draw" pathLength="1" d="M${path}"/>${dots}${labels}` });
}

export function rungWaterfall(factors = [], source = '固定样例模型') {
  if (!factors.length || factors.length > 6 || factors.some((item) => !item?.label || !finite(item.value))) return chartFailure('因子贡献');
  const unit = 0.05; const x0 = (index) => 54 + index * (292 / Math.max(1, factors.length - 1)); const base = 252;
  let level = 0;
  const rows = factors.map((item) => {
    const value = Number(item.value); const from = level; level += value; return { ...item, value, from, to: level };
  });
  const min = Math.min(0, ...rows.flatMap((item) => [item.from, item.to])); const max = Math.max(0, ...rows.flatMap((item) => [item.from, item.to])); const span = max - min || 1;
  const y = (value) => 230 - ((value - min) / span) * 155;
  const body = rows.map((item, index) => {
    const count = Math.max(1, Math.round(Math.abs(item.value) / unit)); const low = Math.min(item.from, item.to); const high = Math.max(item.from, item.to); const rungStep = (y(low) - y(high)) / count;
    const rungs = Array.from({ length: count }, (_, rung) => {
      const yy = y(low) - rung * rungStep; const half = 9 + jitter(rung + 1, index + 2) * 4;
      return `<line class="lf-rung ${item.value < 0 ? 'negative' : ''} lf-reveal" style="--delay:${index * 90 + rung * 12}ms" x1="${x0(index) - half}" y1="${yy}" x2="${x0(index) + half}" y2="${yy}"/>`;
    }).join('');
    const connector = index < rows.length - 1 ? `<line class="lf-handoff" x1="${x0(index) + 14}" y1="${y(item.to)}" x2="${x0(index + 1) - 14}" y2="${y(item.to)}"/>` : '';
    return `${rungs}${connector}<text class="lf-number ${item.value < 0 ? 'muted' : ''}" x="${x0(index)}" y="${Math.min(y(low), y(high)) - 9}" text-anchor="middle">${item.value > 0 ? '+' : '−'}${Math.abs(item.value).toFixed(2)}</text><text class="lf-label" x="${x0(index)}" y="276" text-anchor="middle">${e(item.label)}</text>`;
  }).join('');
  return shell({ id: 'F9', title: '驱动力拆解', conclusion: `合计贡献 ${level >= 0 ? '+' : ''}${level.toFixed(2)}，美元构成主要拖累`, source, legend: '实档增加 · 虚档减少 · 一档 = 0.05', body: `<line class="lf-grid" x1="28" y1="256" x2="372" y2="256"/>${body}` });
}

export function pairedRungs(categories = [], source = 'Goldhub 固定样例') {
  if (!categories.length || categories.length > 6 || categories.some((item) => !item?.label || !finite(item.current) || !finite(item.previous))) return chartFailure('需求结构');
  const max = Math.max(...categories.flatMap((item) => [Number(item.current), Number(item.previous)]));
  const unit = Math.max(1, Math.ceil(max / 28 / 5) * 5); const step = 5.8; const base = 258; const x0 = (index) => 54 + index * (292 / Math.max(1, categories.length - 1));
  const body = categories.map((item, index) => {
    const previous = Math.max(1, Math.round(Number(item.previous) / unit)); const current = Math.max(1, Math.round(Number(item.current) / unit));
    const rungs = (count, xx, faint, salt) => Array.from({ length: count }, (_, rung) => {
      const yy = base - rung * step; const half = 8.8 + jitter(rung + 1, salt) * 2.4;
      return `<line class="lf-rung ${faint ? 'previous' : ''} lf-reveal" style="--delay:${index * 70 + rung * 8}ms" x1="${xx - half}" y1="${yy}" x2="${xx + half}" y2="${yy}"/>`;
    }).join('');
    return `${rungs(previous, x0(index) - 13, true, index + 2)}${rungs(current, x0(index) + 13, false, index + 7)}<text class="lf-number muted" x="${x0(index) - 13}" y="${base - (previous - 1) * step - 9}" text-anchor="middle">${Number(item.previous).toFixed(0)}</text><text class="lf-number" x="${x0(index) + 13}" y="${base - (current - 1) * step - 9}" text-anchor="middle">${Number(item.current).toFixed(0)}</text><text class="lf-label" x="${x0(index)}" y="278" text-anchor="middle">${e(item.label)}</text>`;
  }).join('');
  return shell({ id: 'F6', title: '需求结构', conclusion: '投资与央行需求抵消珠宝需求回落', source, legend: `淡档 = 同期 · 实档 = 本期 · 一档约 ${unit} 吨`, body: `<line class="lf-grid" x1="28" y1="262" x2="372" y2="262"/>${body}` });
}

export function tickRows(strikes = [], source = 'GLD 期权固定代理') {
  if (!strikes.length || strikes.length > 8 || strikes.some((item) => !item?.label || !finite(item.value))) return chartFailure('期权压力');
  const max = Math.max(...strikes.map((item) => Number(item.value))); const unit = Math.max(1, Math.ceil(max / 30 / 5) * 5); const x0 = 112; const width = 215;
  const body = strikes.map((item, index) => {
    const value = Number(item.value); const count = Math.max(1, Math.round(value / unit)); const y = 54 + index * 43; const pitch = width / Math.max(30, count);
    const ticks = Array.from({ length: count }, (_, tick) => {
      const xx = x0 + tick * pitch + pitch / 2; const height = 9 + jitter(tick + 1, index + 2) * 6;
      return `<line class="lf-tick ${e(item.side || 'neutral')} lf-reveal" style="--delay:${index * 60 + tick * 10}ms" x1="${xx}" y1="${y + 9}" x2="${xx}" y2="${y + 9 - height}"/>${tick % 5 === 4 ? `<circle class="lf-marker" cx="${xx}" cy="${y + 13}" r="1"/>` : ''}`;
    }).join('');
    return `<text class="lf-label" x="100" y="${y + 3}" text-anchor="end">${e(item.label)}</text><line class="lf-grid" x1="${x0}" y1="${y + 9}" x2="${x0 + width}" y2="${y + 9}"/>${ticks}<text class="lf-number" x="${x0 + width + 12}" y="${y + 4}">${value.toFixed(0)}k</text>`;
  }).join('');
  return shell({ id: 'F5', title: 'GLD 期权压力', conclusion: '235 执行价的代理压力最集中', source, legend: `一竖线约 ${unit}k · 圆点标记每第五格`, body });
}
