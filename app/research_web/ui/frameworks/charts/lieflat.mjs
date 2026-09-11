import { escapeHTML as e } from '../../markdown.mjs';

function chartFailure(name) {
  console.warn('[ResearchWeb] framework_chart_invalid', { chart: name, status: 'invalid_fixture' });
  return `<div class="framework-chart-error" role="status">${e(name)}暂时无法显示。</div>`;
}

function finite(value) {
  return Number.isFinite(Number(value));
}

function chartShell({ name, caption, source, body, viewBox = '0 0 520 260' }) {
  return `<figure class="lieflat-chart"><svg viewBox="${viewBox}" role="img" aria-labelledby="${e(name)}-title ${e(name)}-desc"><title id="${e(name)}-title">${e(caption)}</title><desc id="${e(name)}-desc">${e(caption)}；图中同时提供数值标签。</desc>${body}</svg><figcaption><span>${e(caption)}</span><span>来源：${e(source)}</span></figcaption></figure>`;
}

export function hairlineArea(series = [], labels = []) {
  if (series.length < 2 || series.some(value => !finite(value))) return chartFailure('价格背景');
  const width = 480; const height = 176; const left = 24; const top = 24;
  const min = Math.min(...series); const max = Math.max(...series); const span = max - min || 1;
  const points = series.map((value, index) => ({
    x: left + (index / (series.length - 1)) * width,
    y: top + height - ((Number(value) - min) / span) * height,
    value: Number(value),
    label: labels[index] || `第 ${index + 1} 期`,
  }));
  const line = points.map(({ x, y }) => `${x.toFixed(1)},${y.toFixed(1)}`).join(' ');
  const hairlines = points.map(({ x, y, value, label }) => `<line class="chart-hairline" x1="${x}" y1="${top + height}" x2="${x}" y2="${y}"><title>${e(label)}：${value.toFixed(1)}</title></line>`).join('');
  const peak = points.reduce((best, point) => point.value > best.value ? point : best, points[0]);
  return chartShell({
    name: 'gold-price-background', caption: '黄金价格背景 · 固定样例', source: 'V0 fixture',
    body: `<line class="chart-axis" x1="${left}" y1="${top + height}" x2="${left + width}" y2="${top + height}"/>${hairlines}<polyline class="chart-line" points="${line}"/><circle class="chart-point" cx="${peak.x}" cy="${peak.y}" r="3"/><text class="chart-label chart-label-strong" x="${Math.min(peak.x, 448)}" y="${Math.max(16, peak.y - 10)}">高点 ${peak.value.toFixed(1)}</text><text class="chart-label" x="${left}" y="232">${e(points[0].label)}</text><text class="chart-label chart-label-end" x="${left + width}" y="232">${e(points.at(-1).label)}</text>`,
  });
}

export function rungWaterfall(factors = []) {
  if (!factors.length || factors.some(item => !item?.label || !finite(item.value))) return chartFailure('因子贡献');
  const max = Math.max(...factors.map(item => Math.abs(Number(item.value))), 0.01);
  const rows = factors.map((item, index) => {
    const value = Number(item.value); const y = 40 + index * 42; const length = Math.abs(value) / max * 154;
    const x = value >= 0 ? 270 : 270 - length;
    const ticks = Math.max(1, Math.round(Math.abs(value) / 0.05));
    return `<g><text class="chart-label" x="20" y="${y + 5}">${e(item.label)}</text><line class="chart-axis" x1="106" y1="${y}" x2="434" y2="${y}"/><line class="chart-rung ${e(item.tone || 'neutral')}" x1="${x}" y1="${y}" x2="${value >= 0 ? 270 + length : 270}" y2="${y}"/><g class="chart-rung-ticks">${Array.from({ length: ticks }, (_, tick) => { const tx = value >= 0 ? 270 + (tick + 1) / ticks * length : 270 - (tick + 1) / ticks * length; return `<line x1="${tx}" y1="${y - 5}" x2="${tx}" y2="${y + 5}"/>`; }).join('')}</g><text class="chart-value ${e(item.tone || 'neutral')}" x="${value >= 0 ? 446 : 94}" y="${y + 5}" text-anchor="${value >= 0 ? 'start' : 'end'}">${value > 0 ? '+' : ''}${value.toFixed(2)}</text></g>`;
  }).join('');
  return chartShell({ name: 'gold-factor-waterfall', caption: '量化因子贡献 · 每格 0.05', source: 'V0 fixture model', body: `<line class="chart-zero" x1="270" y1="18" x2="270" y2="230"/>${rows}` });
}

export function pairedRungs(categories = []) {
  if (!categories.length || categories.some(item => !finite(item.current) || !finite(item.previous))) return chartFailure('供需结构');
  const max = Math.max(...categories.flatMap(item => [Number(item.current), Number(item.previous)]), 1);
  const rows = categories.map((item, index) => {
    const y = 42 + index * 49; const current = Number(item.current); const previous = Number(item.previous);
    const currentWidth = current / max * 268; const previousWidth = previous / max * 268;
    return `<g><text class="chart-label" x="20" y="${y + 7}">${e(item.label)}</text><line class="chart-rung previous" x1="108" y1="${y - 6}" x2="${108 + previousWidth}" y2="${y - 6}"/><line class="chart-rung positive" x1="108" y1="${y + 8}" x2="${108 + currentWidth}" y2="${y + 8}"/><text class="chart-value" x="${Math.max(118 + currentWidth, 405)}" y="${y + 12}">${current} t</text></g>`;
  }).join('');
  return chartShell({ name: 'gold-demand-rungs', caption: '需求结构 · 本期与上年同期', source: 'Goldhub fixture', body: `<text class="chart-legend" x="336" y="18">— 本期</text><text class="chart-legend muted" x="422" y="18">— 同期</text>${rows}` });
}

export function trendLineage(cycles = []) {
  if (!cycles.length || cycles.some(item => !Array.isArray(item.points) || item.points.length < 2 || item.points.some(value => !finite(value)))) return chartFailure('周期谱系');
  const rows = cycles.map((item, row) => {
    const yBase = 48 + row * 49; const points = item.points.map((value, index) => `${156 + index * 74},${yBase + 16 - Number(value) * 24}`).join(' ');
    return `<g><text class="chart-value" x="20" y="${yBase}">${e(item.period)}</text><text class="chart-label" x="20" y="${yBase + 16}">${e(item.label)}</text><polyline class="chart-line lineage" points="${points}"/>${item.points.map((value, index) => `<circle class="chart-point" cx="${156 + index * 74}" cy="${yBase + 16 - Number(value) * 24}" r="2.5"/>`).join('')}</g>`;
  }).join('');
  return chartShell({ name: 'gold-cycle-lineage', caption: 'Fed 宽松周期中的黄金路径', source: 'V0 fixture study', body: rows });
}

export function tickRows(strikes = []) {
  if (!strikes.length || strikes.some(item => !finite(item.value))) return chartFailure('期权压力');
  const max = Math.max(...strikes.map(item => Number(item.value)), 1);
  const rows = strikes.map((item, index) => {
    const y = 38 + index * 42; const count = Math.max(1, Math.round(Number(item.value) / max * 18));
    return `<g><text class="chart-label" x="20" y="${y + 5}">${e(item.label)}</text><g class="chart-ticks ${e(item.tone || 'neutral')}">${Array.from({ length: count }, (_, tick) => `<line x1="${132 + tick * 15}" y1="${y - 7}" x2="${132 + tick * 15}" y2="${y + 7}"/>`).join('')}</g><text class="chart-value" x="432" y="${y + 5}">${Number(item.value).toFixed(0)}k</text></g>`;
  }).join('');
  return chartShell({ name: 'gold-option-pressure', caption: 'GLD 执行价未平仓压力 · 每格约 5k', source: 'GLD options fixture', body: rows });
}

export function matrixHeat(labels = [], matrix = []) {
  if (!labels.length || matrix.length !== labels.length || matrix.some(row => !Array.isArray(row) || row.length !== labels.length || row.some(value => !finite(value)))) return chartFailure('相关性矩阵');
  const size = 54; const startX = 162; const startY = 42;
  const cells = matrix.flatMap((row, y) => row.map((raw, x) => {
    const value = Number(raw); const tone = value > 0.15 ? 'positive' : value < -0.15 ? 'negative' : 'neutral';
    const strength = Math.max(1, Math.min(4, Math.ceil(Math.abs(value) * 4)));
    return `<g><rect class="matrix-cell ${tone} strength-${strength}" x="${startX + x * size}" y="${startY + y * 36}" width="48" height="30" rx="2"><title>${e(labels[y])} 与 ${e(labels[x])}：${value.toFixed(2)}</title></rect><text class="matrix-value" x="${startX + x * size + 24}" y="${startY + y * 36 + 20}">${value.toFixed(2)}</text></g>`;
  })).join('');
  const columnLabels = labels.map((label, index) => `<text class="chart-label matrix-column" x="${startX + index * size + 24}" y="28">${e(label)}</text>`).join('');
  const rowLabels = labels.map((label, index) => `<text class="chart-label" x="150" y="${startY + index * 36 + 20}" text-anchor="end">${e(label)}</text>`).join('');
  return chartShell({ name: 'gold-correlation-matrix', caption: '资产月度收益相关性', source: 'V0 fixture, 2016–2026', body: `${columnLabels}${rowLabels}${cells}` });
}
