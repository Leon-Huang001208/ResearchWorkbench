import { escapeHTML as e } from '../markdown.mjs';
import { dumbbellQueue, hairlineArea, hairlineLine, pairedRungs, plumbScatter, rungWaterfall } from './charts/lieflat.mjs';
import { anchorRail, blockSources, chapterHeading, evidenceList, frameworkBot, frameworkPanel, sourceNames } from './common.mjs';

const blocks = (snapshot) => [snapshot.quantity_q, snapshot.price_p, snapshot.fiscal_g, snapshot.plumbing_m, snapshot.cross_border_x];
const first = (series) => series?.points?.[0]?.value;
const last = (series) => series?.points?.at(-1)?.value;

function metricGrid(block) {
  return `<div class="framework-metric-grid">${block.metrics.map((item) => `<article><span>${e(item.label)}${item.proxy ? ' · 代理' : ''}</span><strong class="mono">${e(item.value)}</strong><small>${e(item.direction)} · ${e(item.interpretation)}</small></article>`).join('')}</div>${blockSources(block)}`;
}

function dimensionIntro(block) {
  const score = block.score == null ? '—' : `${block.score >= 0 ? '+' : ''}${block.score.toFixed(2)}`;
  return `<div class="framework-dimension-intro"><span class="framework-dimension-key mono">${e(block.key)}</span><div><strong>${e(block.label)}</strong><p>${e(block.summary)}</p></div><span class="mono">${score}</span></div>`;
}

function pairedFromSeries(series) {
  return series.filter((item) => Number.isFinite(first(item)) && Number.isFinite(last(item))).map((item) => ({ label: item.label, previous: first(item), current: last(item) }));
}

function scatterFromSeries(series) {
  const [xSeries, ySeries] = series;
  const length = Math.min(xSeries?.points?.length || 0, ySeries?.points?.length || 0);
  return Array.from({ length }, (_, index) => ({ label: xSeries.points[index].date, x: xSeries.points[index].value, y: ySeries.points[index].value }));
}

export function renderDollar({ framework, snapshot }, { anchor = 'overview', bot = {} } = {}) {
  const state = snapshot.research_state;
  const fixture = blocks(snapshot).some((item) => item.status === 'fixture');
  const dimensions = blocks(snapshot);
  const factors = dimensions.filter((item) => item.score != null).map((item) => ({ label: item.key, value: item.score }));
  const quantitySeries = snapshot.quantity_q.series.find((item) => item.label.includes('净流动性')) || snapshot.quantity_q.series[0];
  const plumbingSeries = snapshot.plumbing_m.series.find((item) => item.label.includes('SOFR')) || snapshot.plumbing_m.series[0];
  const plumbingPoints = plumbingSeries.points.slice(-30);
  const policyRows = pairedFromSeries(snapshot.price_p.series);
  const fiscalRows = pairedFromSeries(snapshot.fiscal_g.series);
  const crossBorderPoints = scatterFromSeries(snapshot.cross_border_x.series);
  const score = state.score == null ? '待核验' : `${state.score >= 0 ? '+' : ''}${state.score.toFixed(2)}`;
  const nav = anchorRail(framework, 'dollar', anchor, '美元流动性研究画布');
  const botView = frameworkBot(bot, snapshot.revision, '净流动性代理改善，为什么美元条件仍可能偏紧？');
  return `<article class="framework-detail dollar-framework" data-framework="dollar" data-framework-revision="${e(snapshot.revision)}">
    <header class="framework-hero"><div class="framework-hero-main"><a class="framework-back" href="#/frameworks">← 研究框架</a><div class="framework-title-line"><span class="framework-symbol" aria-hidden="true">$</span><div><span class="eyebrow">LIQUIDITY FRAMEWORK · V${e(framework.version)}</span><h1>${e(framework.name)}</h1></div></div><p class="framework-question">${e(framework.question)}</p><div class="framework-chain" aria-label="研究链路">${framework.chain.map((item, index) => `<span>${index ? '<i aria-hidden="true">→</i>' : ''}${e(item)}</span>`).join('')}</div></div><aside class="framework-hero-meta"><span class="badge">${fixture ? '固定样例' : '数据快照'}</span><strong>${e(snapshot.status)}</strong><dl><div><dt>观测</dt><dd class="mono">${e(snapshot.as_of)}</dd></div><div><dt>证据</dt><dd class="mono">${snapshot.evidence.length}</dd></div><div><dt>覆盖</dt><dd class="mono">${snapshot.coverage}%</dd></div></dl></aside></header>
    ${fixture ? '<div class="framework-fixture-notice" role="status"><strong>离线确定性样例</strong><span>首次采集尚未完成；页面明确保留样例标识，不将其伪装为实时数据。</span></div>' : ''}
    <div class="framework-canvas-layout">${nav}<main class="framework-canvas">
      <section class="framework-chapter" id="framework-overview" aria-labelledby="framework-overview-title">${chapterHeading('overview', 1, '总览', '先判断美元条件，再沿 Q-P-g-M-X 找到支撑、拖累和未解缺口。')}<div class="framework-summary-band"><div><span>当前研究状态</span><strong>${e(state.label)}</strong><small>已知小计 <b class="mono">${state.known_subtotal.toFixed(2)}</b> · 综合 <b class="mono">${e(score)}</b></small></div><dl><div><dt>主要支撑</dt><dd>${state.supports.map((item) => `<span>${e(item)}</span>`).join('')}</dd></div><div><dt>主要拖累</dt><dd>${state.drags.map((item) => `<span>${e(item)}</span>`).join('')}</dd></div></dl><aside><span>下一项验证</span><strong>${e(state.next_check)}</strong><button type="button" data-framework-gap="${e(snapshot.gaps[0]?.id || '')}">带着缺口提问 →</button></aside></div><div class="framework-overview-row">${frameworkPanel('五维力量如何合成', 'F9 Rung Waterfall · 缺失维度不补零', rungWaterfall(factors, 'Q-P-g-M-X 标准化模型', { title: '美元流动性五维贡献', conclusion: `已知小计 ${state.known_subtotal >= 0 ? '+' : ''}${state.known_subtotal.toFixed(2)}；可能区间 ${state.possible_low.toFixed(2)} 至 ${state.possible_high.toFixed(2)}` }))}${frameworkPanel('数据覆盖与缺口', '任一维度不可计算即保持待核验', `<div class="framework-coverage"><div class="framework-coverage-number"><strong class="mono">${snapshot.coverage}%</strong><span>当前覆盖</span></div><div class="framework-coverage-track" aria-label="数据覆盖率 ${snapshot.coverage}%"><i style="--coverage:${snapshot.coverage}%"></i></div><ul>${snapshot.gaps.map((item) => `<li><strong>${e(item.label)}</strong><span>${e(item.next_check)}</span></li>`).join('')}</ul></div>`)}</div></section>
      <section class="framework-chapter" id="framework-quantity" aria-labelledby="framework-quantity-title">${chapterHeading('quantity', 2, 'Q 总量水库', 'Fed 资产负债表、准备金和 ON RRP 的水位如何变化？')}${dimensionIntro(snapshot.quantity_q)}<div class="framework-two-column">${frameworkPanel('净流动性代理', 'F3 Hairline Area · 非会计恒等式', hairlineArea(quantitySeries.points, sourceNames(snapshot.quantity_q), { title: quantitySeries.label, conclusion: `最新 ${last(quantitySeries).toFixed(1)} ${e(quantitySeries.unit)}` }))}${frameworkPanel('水位读数', '总量与边际变化分开解释', metricGrid(snapshot.quantity_q))}</div></section>
      <section class="framework-chapter" id="framework-price" aria-labelledby="framework-price-title">${chapterHeading('price', 3, 'P 资金价格', '政策走廊、实际利率和期限结构是否放松融资约束？')}${dimensionIntro(snapshot.price_p)}<div class="framework-two-column">${frameworkPanel('政策路径变化', 'F12 Dumbbell Queue · 起点对最新', dumbbellQueue(policyRows, sourceNames(snapshot.price_p), { conclusion: '曲线节点的最新读数与观察起点并列' }))}${frameworkPanel('价格读数', '资金价格与总量信号可能背离', metricGrid(snapshot.price_p))}</div></section>
      <section class="framework-chapter" id="framework-fiscal" aria-labelledby="framework-fiscal-title">${chapterHeading('fiscal', 4, 'g 财政水流', 'TGA、发行与结算正在向市场注水还是抽水？')}${dimensionIntro(snapshot.fiscal_g)}<div class="framework-two-column">${frameworkPanel('TGA 与发行结算', 'F6 Paired Rungs · 起点对最新', pairedRungs(fiscalRows, sourceNames(snapshot.fiscal_g), { title: '财政水流变化', conclusion: 'TGA 与发行结算必须联合观察', legend: '淡档 = 起点 · 实档 = 最新 · 各序列保留原单位' }))}${frameworkPanel('财政读数', '日度 TGA 优先；WDTGAL 仅作回退代理', metricGrid(snapshot.fiscal_g))}</div></section>
      <section class="framework-chapter" id="framework-plumbing" aria-labelledby="framework-plumbing-title">${chapterHeading('plumbing', 5, 'M 融资管道', '隔夜资金、回购和交易商资产负债表是否出现摩擦？')}${dimensionIntro(snapshot.plumbing_m)}<div class="framework-two-column">${frameworkPanel('政策锚附近的摩擦', 'F2 Hairline Line · SOFR−IORB', hairlineLine(plumbingPoints.map((item) => ({ label: item.date, value: item.value })), sourceNames(snapshot.plumbing_m), { title: plumbingSeries.label, conclusion: `最新利差 ${last(plumbingSeries).toFixed(1)} ${e(plumbingSeries.unit)}` }))}${frameworkPanel('管道读数', '总量宽松不代表融资管道畅通', metricGrid(snapshot.plumbing_m))}</div></section>
      <section class="framework-chapter" id="framework-cross-border" aria-labelledby="framework-cross-border-title">${chapterHeading('cross-border', 6, 'X 跨境美元', '美元强弱、官方托管与全球美元融资是否同向？')}${dimensionIntro(snapshot.cross_border_x)}<div class="framework-two-column">${frameworkPanel('跨境关系', 'F8 Plumb Scatter · 同期观察', plumbScatter(crossBorderPoints, sourceNames(snapshot.cross_border_x), { conclusion: '广义美元走强时，海外美元压力需要更多直接证据确认' }))}${frameworkPanel('跨境读数', '跨币种基差缺失必须明示', metricGrid(snapshot.cross_border_x))}</div></section>
      <section class="framework-chapter" id="framework-evidence" aria-labelledby="framework-evidence-title">${chapterHeading('evidence', 7, '传导与证据', '把五维信号传导到黄金、风险资产与海外融资，并保留证据台账。')}<div class="framework-transmission">${snapshot.transmission.links.map((item) => `<article><span>${e(item.source)}</span><i aria-hidden="true">→</i><strong>${e(item.target)}</strong><em>${e(item.state)}</em><p>${e(item.explanation)}</p></article>`).join('')}</div><div class="framework-two-column">${frameworkPanel('证据台账', '直接、代理和缺口分列', evidenceList(snapshot.evidence))}${frameworkPanel('事件雷达', '事件是验证节点，不预设方向', `<ol class="framework-timeline">${snapshot.events.map((item) => `<li><time class="mono">${e(item.date)}</time><div><span>${e(item.type)}</span><strong>${e(item.title)}</strong><p>${e(item.impact)}</p></div><em>${e(item.status)}</em></li>`).join('')}</ol>`)}</div>${blockSources(snapshot.transmission)}<details class="framework-method-details"><summary>方法、来源版本与边界</summary><p>${e(framework.method)}</p><p>“WALCL − TGA − ON RRP”仅称净流动性代理；框架版本 <span class="mono">${e(framework.version)}</span> · 方法参考 <a href="https://github.com/yuxudong-morefun/dollar/tree/${e(framework.source_revision)}" target="_blank" rel="noreferrer">${e(framework.source_revision.slice(0, 10))}</a>。</p></details></section>
    </main>${bot?.open ? botView : ''}</div>${bot?.open ? '' : botView}
  </article>`;
}
