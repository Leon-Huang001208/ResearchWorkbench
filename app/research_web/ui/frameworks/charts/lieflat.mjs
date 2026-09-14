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

export function hairlineLine(points = [], source = '固定样例', options = {}) {
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
  return shell({ id: 'F2', title: options.title || '价格背景', conclusion: options.conclusion || `最新值 ${values.at(-1).toFixed(1)}，区间上沿 ${max.toFixed(1)}`, source, legend: options.legend || '一圆点 = 一期 · 空心点仅用于区分节律', body: `${floor}<line class="lf-grid" x1="24" y1="${base}" x2="376" y2="${base}"/><path class="lf-ink lf-draw" pathLength="1" d="M${path}"/>${dots}${labels}` });
}

export function rungWaterfall(factors = [], source = '固定样例模型', options = {}) {
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
  return shell({ id: 'F9', title: options.title || '驱动力拆解', conclusion: options.conclusion || `已知贡献合计 ${level >= 0 ? '+' : ''}${level.toFixed(2)}`, source, legend: options.legend || '实档增加 · 虚档减少 · 一档 = 0.05', body: `<line class="lf-grid" x1="28" y1="256" x2="372" y2="256"/>${body}` });
}

export function pairedRungs(categories = [], source = 'Goldhub 固定样例', options = {}) {
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
  return shell({ id: 'F6', title: options.title || '需求结构', conclusion: options.conclusion || '本期与前期变化需要结合来源口径解释', source, legend: options.legend || `淡档 = 前期 · 实档 = 本期 · 一档约 ${unit}`, body: `<line class="lf-grid" x1="28" y1="262" x2="372" y2="262"/>${body}` });
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

export function hairlineArea(points = [], source = '暂无来源', options = {}) {
  if (points.length < 2 || points.length > 60 || points.some((item) => !item?.date || !finite(item.value))) return chartFailure(options.title || '净流动性');
  const values = points.map((item) => Number(item.value));
  const min = Math.min(...values); const max = Math.max(...values); const span = max - min || 1;
  const x = (index) => 30 + index * (340 / Math.max(1, points.length - 1));
  const y = (value) => 236 - ((value - min) / span) * 160;
  const path = points.map((item, index) => `${x(index)} ${y(item.value)}`).join(' L ');
  const area = `M${path} L ${x(points.length - 1)} 258 L ${x(0)} 258 Z`;
  const labels = [0, Math.floor((points.length - 1) / 2), points.length - 1].map((index) => `<text class="lf-label" x="${x(index)}" y="280" text-anchor="middle">${e(points[index].date)}</text>`).join('');
  return shell({ id: 'F3', title: options.title || '净流动性代理', conclusion: options.conclusion || `最新 ${values.at(-1).toFixed(1)}，较起点 ${values.at(-1) >= values[0] ? '上升' : '下降'}`, source, legend: options.legend || '浅色面积仅编码相对水位，不代表会计恒等式', body: `<path class="lf-area lf-reveal" d="${area}"/><path class="lf-ink lf-draw" pathLength="1" d="M${path}"/><circle class="lf-dot" cx="${x(points.length - 1)}" cy="${y(values.at(-1))}" r="3.5"/><text class="lf-number" x="${x(points.length - 1)}" y="${y(values.at(-1)) - 12}" text-anchor="end">${values.at(-1).toFixed(1)}</text>${labels}` });
}

export function dumbbellQueue(rows = [], source = '暂无来源', options = {}) {
  if (!rows.length || rows.length > 6 || rows.some((item) => !item?.label || !finite(item.current) || !finite(item.previous))) return chartFailure(options.title || '政策路径');
  const values = rows.flatMap((item) => [Number(item.current), Number(item.previous)]);
  const min = Math.min(...values); const max = Math.max(...values); const span = max - min || 1;
  const x = (value) => 112 + ((value - min) / span) * 218;
  const body = rows.map((item, index) => {
    const y = 70 + index * 62; const current = Number(item.current); const previous = Number(item.previous);
    return `<text class="lf-label" x="98" y="${y + 3}" text-anchor="end">${e(item.label)}</text><line class="lf-grid" x1="${x(previous)}" y1="${y}" x2="${x(current)}" y2="${y}"/><circle class="lf-dot hollow" cx="${x(previous)}" cy="${y}" r="5"/><circle class="lf-dot" cx="${x(current)}" cy="${y}" r="5"/><text class="lf-number muted" x="${x(previous)}" y="${y - 13}" text-anchor="middle">${previous.toFixed(2)}</text><text class="lf-number" x="${x(current)}" y="${y + 22}" text-anchor="middle">${current.toFixed(2)}</text>`;
  }).join('');
  return shell({ id: 'F12', title: options.title || '政策路径变化', conclusion: options.conclusion || '实心点为最新，空心点为起始观察', source, legend: options.legend || '空心 = 前期 · 实心 = 最新', body });
}

export function plumbScatter(points = [], source = '暂无来源', options = {}) {
  if (points.length < 2 || points.length > 60 || points.some((item) => !finite(item.x) || !finite(item.y))) return chartFailure(options.title || '跨境关系');
  const xs = points.map((item) => Number(item.x)); const ys = points.map((item) => Number(item.y));
  const xmin = Math.min(...xs); const xmax = Math.max(...xs); const ymin = Math.min(...ys); const ymax = Math.max(...ys);
  const x = (value) => 48 + ((value - xmin) / (xmax - xmin || 1)) * 300;
  const y = (value) => 252 - ((value - ymin) / (ymax - ymin || 1)) * 178;
  const marks = points.map((item, index) => `<g class="lf-reveal" style="--delay:${index * 35}ms"><line class="lf-plumb" x1="${x(item.x)}" y1="${y(item.y)}" x2="${x(item.x)}" y2="262"/><circle class="lf-dot ${index === points.length - 1 ? '' : 'hollow'}" cx="${x(item.x)}" cy="${y(item.y)}" r="${index === points.length - 1 ? 4 : 2.6}"><title>${e(item.label || String(index + 1))} · ${Number(item.x).toFixed(2)}, ${Number(item.y).toFixed(2)}</title></circle></g>`).join('');
  return shell({ id: 'F8', title: options.title || '跨境美元关系', conclusion: options.conclusion || '广义美元与官方托管关系需要持续核验', source, legend: options.legend || '横轴 = 广义美元 · 纵轴 = 外国官方托管', body: `<line class="lf-grid" x1="42" y1="262" x2="360" y2="262"/>${marks}<text class="lf-label" x="48" y="282">${xmin.toFixed(1)}</text><text class="lf-label" x="348" y="282" text-anchor="end">${xmax.toFixed(1)}</text>` });
}

export function matrixArc(cells = [], source = '暂无来源', options = {}) {
  if (cells.length < 4 || cells.length > 36 || cells.some((item) => !item?.row || !item?.column || !finite(item.value))) return chartFailure(options.title || '相关性矩阵');
  const labels = [...new Set(cells.flatMap((item) => [item.row, item.column]))];
  if (labels.length > 6) return chartFailure(options.title || '相关性矩阵');
  const size = 43; const originX = 104; const originY = 50;
  const lookup = new Map(cells.map((item) => [`${item.row}\0${item.column}`, Number(item.value)]));
  const headers = labels.map((label, index) => `<text class="lf-label" x="${originX + index * size + size / 2}" y="34" text-anchor="middle">${e(label)}</text><text class="lf-label" x="92" y="${originY + index * size + 27}" text-anchor="end">${e(label)}</text>`).join('');
  const body = labels.flatMap((row, rowIndex) => labels.map((column, columnIndex) => {
    const value = lookup.get(`${row}\0${column}`) ?? lookup.get(`${column}\0${row}`) ?? (row === column ? 1 : 0);
    const strength = Math.max(1, Math.ceil(Math.abs(value) * 4));
    return `<rect class="matrix-cell ${value >= 0 ? 'positive' : 'negative'} strength-${strength}" x="${originX + columnIndex * size}" y="${originY + rowIndex * size}" width="${size - 3}" height="${size - 3}" rx="2"/><text class="matrix-value" x="${originX + columnIndex * size + (size - 3) / 2}" y="${originY + rowIndex * size + 24}">${value.toFixed(2)}</text>`;
  })).join('');
  return shell({ id: 'L4', title: options.title || '相关性矩阵', conclusion: options.conclusion || '颜色仅表示正负方向，数字保留完整系数', source, legend: options.legend || '绿 = 正相关 · 红 = 负相关 · 深度 = 绝对值', body: `${headers}${body}` });
}
