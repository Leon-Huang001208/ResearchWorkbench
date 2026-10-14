import { escapeHTML as e } from '../markdown.mjs';

const value = v => v == null ? '—' : typeof v === 'number' ? v.toLocaleString('zh-CN', { maximumFractionDigits: 3 }) : e(v);
function sourceLink(url, label) {
  return /^https?:\/\//i.test(url || '') ? `<a href="${e(url)}" target="_blank" rel="noreferrer">${e(label)}</a>` : e(label);
}
function gaps(rows = []) {
  return rows.map(g => `<p class="core-gap"><strong>${e(g.label)}</strong> · ${e(g.severity)}<br>${e(g.next_check)}</p>`).join('');
}
function sources(block) {
  return `<footer>观测 ${e(block.as_of || '—')} · 取得 ${e(block.fetched_at || '—')} · 检查 ${e(block.checked_at || block.fetched_at || '—')}<br>${(block.sources || []).map(s => typeof s === 'string' ? e(s) : `${sourceLink(s.url, s.name)} · ${e(s.unit)} · ${e(s.observed_at)} · ${e(s.method)}${s.proxy ? ' · 代理' : ''}`).join('<br>') || '暂无来源'}${block.failure_code ? `<br>采集失败 ${e(block.failure_code)}` : ''}${gaps(block.gaps)}</footer>`;
}
function chart(points, label, unit = '') {
  const rows = (points || []).map((p, i) => ({ y: typeof p === 'number' ? p : p.value, label: p.date || p.label || i })).filter(p => Number.isFinite(p.y));
  if (!rows.length) return '<p class="empty-data">暂无可用序列</p>';
  const low = Math.min(...rows.map(p => p.y)), high = Math.max(...rows.map(p => p.y));
  const line = rows.map((p, i) => `${40 + i * 540 / Math.max(rows.length - 1, 1)},${135 - (p.y - low) * 110 / (high - low || 1)}`).join(' ');
  return `<svg viewBox="0 0 600 160" role="img" aria-label="${e(label)} · ${e(unit)}"><title>${e(label)} · ${e(unit)}</title><desc>最低 ${value(low)}，最高 ${value(high)}；横轴按观测日期排列</desc><text x="2" y="20" fill="currentColor" font-size="10">${value(high)}</text><text x="2" y="145" fill="currentColor" font-size="10">${value(low)}</text><polyline points="${line}" fill="none" stroke="currentColor" stroke-width="2"/></svg><div class="series-range">${e(rows[0].label)} — ${e(rows.at(-1).label)} · 最新 ${value(rows.at(-1).y)} ${e(unit)}</div>`;
}
const blocks = {
  gold: [['market_context','价格背景'],['pricing_drivers','定价驱动'],['supply_demand','供需与资金'],['cycle_macro','周期与宏观'],['options','持仓与期权'],['allocation_context','情景与配置']],
  dollar: [['quantity_q','Q 总量水库'],['price_p','P 资金价格'],['fiscal_g','g 财政水流'],['plumbing_m','M 融资管道'],['cross_border_x','X 跨境美元'],['transmission','传导']],
};
function table(headers, rows) {
  return `<div class="core-table"><table><thead><tr>${headers.map(h => `<th>${e(h)}</th>`).join('')}</tr></thead><tbody>${rows.map(row => `<tr>${row.map(c => `<td>${value(c)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
}
function allocationConnected(block) {
  if (['fixture', 'missing'].includes(block.status) || !block.sources?.length) return false;
  return block.sources.every(source => {
    try {
      const url = new URL(source.url);
      return ['http:', 'https:'].includes(url.protocol) && Boolean(url.hostname) && url.hostname !== 'invalid' && !url.hostname.endsWith('.invalid') && !/fixture/i.test(source.method || '');
    } catch (error) {
      console.warn('gold_allocation_source_invalid', error.name);
      return false;
    }
  });
}
function panel(key, title, b) {
  if (!b) return `<section class="core-card"><h2>${e(title)}</h2><p>尚未接入</p></section>`;
  if (key === 'allocation_context' && !allocationConnected(b)) return `<section id="allocation_context" class="core-card"><header><h2>${e(title)}</h2><span>尚未接入</span></header><p>缺少带来源、观测窗口与计算口径的配置研究数据。</p>${gaps(b.gaps)}</section>`;
  const metrics = b.metrics || b.relationships || b.flows || b.positioning || [];
  const series = Array.isArray(b.series) && b.series[0]?.points ? b.series : b.series ? [{ label: title, unit: b.sources?.[0]?.unit || '', points: b.series }] : [];
  const maxStrike = Math.max(...(b.strikes || []).map(s => s.value), 1);
  return `<section id="${e(key)}" class="core-card"><header><h2>${e(title)}</h2><span>${e(b.status || '待核验')} · ${e(b.as_of || '—')}</span></header>
    ${b.score !== undefined ? `<div class="dimension-score">原生维度得分 ${value(b.score)}</div>` : ''}
    ${b.price !== undefined ? `<strong class="price">${value(b.price)}</strong><p>变化 ${value(b.change_percent)}% · 区间 ${value(b.range_low)}–${value(b.range_high)}</p>` : ''}
    <p>${e(b.summary || '')}</p>
    ${series.map(s => `<h3>${e(s.label || title)}${s.unit ? ` · ${e(s.unit)}` : ''}</h3>${chart(s.points, s.label || title, s.unit || '')}`).join('')}
    <div class="metric-grid">${metrics.map(m => `<div><span>${e(m.label || m.name)}</span><strong>${value(m.value)}</strong><small>${e(m.direction || '')}${m.proxy ? ' · 代理' : ''}<br>${e(m.interpretation || m.note || '')}</small></div>`).join('')}</div>
    ${(b.factors || []).map(f => `<div class="factor"><span>${e(f.label)}</span><meter min="-1" max="1" value="${Number.isFinite(f.value) ? f.value : 0}"></meter><b>${value(f.value)}</b></div><p class="factor-detail">原始值 ${e(f.raw_value || '—')} · 原生因子得分 ${value(f.score)} · 权重 ${value(f.weight)}%${f.monitor_only ? ' · 仅监控' : ''}</p>`).join('')}
    ${b.categories ? table(['需求（来源单位）','本期','前期'], b.categories.map(c => [c.label,c.current,c.previous])) : ''}
    ${b.policy_phase ? `<h3>政策阶段</h3><p>${e(b.policy_phase)}</p>` : ''}
    ${(b.regimes || []).map(r => `<div class="core-regime"><strong>${e(r.label)}</strong> · ${e(r.fit)}<p>${e(r.reason)}</p></div>`).join('')}
    ${(b.strikes || []).map(s => `<div class="strike"><span>${e(s.label)} · ${e(s.side)}</span><meter min="0" max="${maxStrike}" value="${s.value}"></meter><strong>${value(s.value)}</strong></div>`).join('')}
    ${b.diversification_note ? `<p>${e(b.diversification_note)}</p><p>${e(b.drawdown_note)}</p>` : ''}
    ${b.scenarios ? table(['情景','黄金','股票','债券','说明'], b.scenarios.map(s => [s.label,s.gold,s.equities,s.bonds,s.note])) : ''}
    ${b.correlations ? `<h3>相关性矩阵</h3>${table(['资产','关联资产','相关系数'], b.correlations.map(c => [c.row,c.column,c.value]))}` : ''}
    ${(b.links || []).map(l => `<p>${e(l.source)} → ${e(l.target)} · ${e(l.state)}<br>${e(l.explanation)}</p>`).join('')}
    ${sources(b)}
  </section>`;
}
export function renderEmbedDashboard({ framework: f, snapshot: s }) {
  const r = s.research_state;
  return `<div class="core-shell ${e(f.slug)}"><aside class="core-nav"><h1>${f.slug === 'gold' ? 'GOLDAR' : 'DOLLAR'}<small>${e(f.name)}</small></h1><a href="#overview">研究总览</a>${blocks[f.slug].map(([k,t]) => `<a href="#${k}">${e(t)}</a>`).join('')}<a href="#evidence">证据与缺口</a><a href="#unsupported">扩展模块</a></aside><main class="core-main">
    <header class="core-header"><div><small>RESEARCH OBSERVATORY · NATIVE SNAPSHOT</small><h1>${e(f.name)}</h1><p>${e(f.question || '')}</p><p>${(f.chain || []).map(e).join(' → ')}</p></div><span>${e(s.as_of)}<br>快照 ${e(s.revision.slice(0,8))}<br>取得 ${e(s.fetched_at || '—')}</span></header>
    <section id="overview" class="core-summary"><div><span>当前研究状态</span><h2>${e(r.label)}</h2><strong>原生得分 ${value(r.score)}</strong>${r.known_subtotal != null ? `<p>已知小计 ${value(r.known_subtotal)} · 区间 ${value(r.possible_low)} 至 ${value(r.possible_high)}</p>` : ''}<p>覆盖 ${value(s.coverage)}% · 置信度 ${value(r.confidence)}%</p>${r.model_weights ? `<p>模型权重 ${Object.entries(r.model_weights).map(([k,v]) => `${e(k)} ${value(v)}%`).join(' · ')}</p>` : ''}</div><div><h3>主要支撑</h3>${(r.supports || []).map(t=>`<p>${e(t)}</p>`).join('')}<h3>主要拖累</h3>${(r.drags || []).map(t=>`<p>${e(t)}</p>`).join('')}</div><div><h3>下一项验证</h3><p>${e(r.next_check)}</p><h3>反证条件</h3>${(f.counter_evidence || []).map(t => `<p>${e(t)}</p>`).join('')}</div></section>
    <div class="core-grid">${blocks[f.slug].map(([k,t]) => panel(k,t,s[k])).join('')}</div>
    <section id="evidence" class="core-card"><h2>证据与缺口</h2>${gaps(s.gaps)}${(s.evidence || []).map(a=>`<p>${e(a.date)} · ${sourceLink(a.url,a.source)} · ${e(a.observation)}<br>${e(a.use)} · ${e(a.quality)}</p>`).join('')}<h3>事件雷达</h3>${(s.events || []).map(a => `<p>${e(a.date)} · ${e(a.type)} · <strong>${e(a.title)}</strong> · ${e(a.status)}<br>${e(a.impact)}</p>`).join('')}<details><summary>方法版本与边界</summary><p>${e(f.method || '')}</p><p>版本 ${e(f.version || '')} · 方法修订 ${e(f.source_revision || '')}</p></details></section>
    <section id="unsupported" class="core-card"><h2>扩展模块</h2><p>回测 · 量化策略 · 模型拟合：尚未接入</p></section>
  </main></div>`;
}
