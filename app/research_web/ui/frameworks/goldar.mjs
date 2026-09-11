import { escapeHTML as e } from '../markdown.mjs';
import { goldFrameworkV0 } from './fixtures/gold-v0.mjs';
import { hairlineArea, matrixHeat, pairedRungs, rungWaterfall, tickRows, trendLineage } from './charts/lieflat.mjs';

const { framework, snapshot } = goldFrameworkV0;

function metric(label, value, note = '') {
  return `<div class="framework-metric"><span>${e(label)}</span><strong class="mono">${e(value)}</strong>${note ? `<small>${e(note)}</small>` : ''}</div>`;
}

function sourceStrip(section) {
  return `<footer class="framework-source-strip"><span>观测 ${e(section.as_of || snapshot.meta.as_of)}</span><span>状态 ${e(section.status || 'fixture')}</span><span>${e((section.sources || []).join(' · ') || 'V0 fixture')}</span>${section.gaps?.length ? `<span class="framework-gap">缺口 ${e(section.gaps.length)}</span>` : ''}</footer>`;
}

function panel(title, subtitle, content, extraClass = '') {
  return `<section class="framework-panel ${extraClass}"><header><div><h2>${e(title)}</h2>${subtitle ? `<p>${e(subtitle)}</p>` : ''}</div></header>${content}</section>`;
}

function overview() {
  const state = snapshot.research_state;
  const market = snapshot.market_context;
  return `<div class="framework-overview-grid">
    ${panel('研究状态', '结论会随证据完整性降级', `<div class="framework-state-block"><div class="framework-state-dial"><span>当前状态</span><strong>${e(state.label)}</strong><small>置信度 <span class="mono">${state.confidence}%</span></small></div><dl class="framework-state-list"><div><dt>支撑</dt><dd>${state.supports.map(item => `<span>${e(item)}</span>`).join('')}</dd></div><div><dt>拖累</dt><dd>${state.drags.map(item => `<span>${e(item)}</span>`).join('')}</dd></div></dl></div><div class="framework-next-check"><span>下一项验证</span><strong>${e(state.next_check)}</strong></div>`, 'framework-state-panel')}
    ${panel('价格背景', '只提供框架判断所需的紧凑上下文', `<div class="framework-price-line"><strong class="mono">${market.price.toLocaleString('en-US', { minimumFractionDigits: 1 })}</strong><span class="positive mono">+${market.change.toFixed(1)}%</span><small>样例区间 ${market.range[0]}–${market.range[1]}</small></div>${hairlineArea(market.series, market.labels)}`)}
    ${panel('驱动力拆解', '贡献值是演示模型输出，不代表实时判断', rungWaterfall(snapshot.pricing_drivers.factors), 'framework-span-2')}
    ${panel('数据覆盖', '缺失、过期或口径冲突都会阻止确定状态', `<div class="framework-coverage"><div class="framework-coverage-number"><strong class="mono">${snapshot.meta.coverage}%</strong><span>样例覆盖率</span></div><div class="framework-coverage-track" aria-label="样例数据覆盖率 ${snapshot.meta.coverage}%"><i style="--coverage:${snapshot.meta.coverage}%"></i></div><ul>${snapshot.meta.gaps.map(item => `<li>${e(item)}</li>`).join('')}</ul></div>`, 'framework-span-2')}
  </div>`;
}

function drivers() {
  const section = snapshot.pricing_drivers;
  return `<div class="framework-two-column">${panel('因子贡献', '实际利率、美元、通胀、波动与资金流', rungWaterfall(section.factors))}${panel('宏观关系读数', '方向、水平与解释分开呈现', `<div class="framework-fact-table" role="table" aria-label="黄金宏观关系读数"><div class="framework-fact-head" role="row"><span>驱动</span><span>读数</span><span>方向</span><span>解释</span></div>${section.relationships.map(item => `<div class="framework-fact-row" role="row"><strong>${e(item.name)}</strong><span class="mono">${e(item.value)}</span><span>${e(item.direction)}</span><span>${e(item.interpretation)}</span></div>`).join('')}</div>${sourceStrip(section)}`)}</div>`;
}

function supply() {
  const section = snapshot.supply_demand;
  return `<div class="framework-two-column">${panel('黄金需求结构', '吨；本期与上年同期', pairedRungs(section.categories))}${panel('资金与结构读数', 'ETF、央行与期现结构', `<div class="framework-kpi-list">${section.flow_metrics.map(item => `<article><span>${e(item.label)}</span><strong class="mono">${e(item.value)}</strong><small>${e(item.note)}</small></article>`).join('')}</div>${sourceStrip(section)}`)}</div>`;
}

function cycle() {
  const section = snapshot.cycle_macro;
  return `<div class="framework-two-column">${panel('Fed 周期谱系', '比较不同宽松阶段的相对路径', trendLineage(section.cycles))}${panel('宏观情景映射', '先判断增长与通胀，再解释黄金', `<div class="framework-regime-list">${section.regimes.map(item => `<article><div><strong>${e(item.label)}</strong><span class="framework-fit">${e(item.fit)}</span></div><p>${e(item.reason)}</p></article>`).join('')}</div>${sourceStrip(section)}`)}</div>`;
}

function positioning() {
  const section = snapshot.options;
  return `<div class="framework-two-column">${panel('持仓与波动', '区分趋势确认、拥挤与保护需求', `<div class="framework-kpi-list compact">${section.positioning.map(item => `<article><span>${e(item.label)}</span><strong class="mono">${e(item.value)}</strong><small>${e(item.note)}</small></article>`).join('')}</div><div class="framework-proxy-note"><strong>代理指标</strong><span>场外期权不可见，GLD 结构只用于观察压力分布。</span></div>${sourceStrip(section)}`)}${panel('期权压力分布', '未平仓量集中不等同于价格预测', tickRows(section.strikes))}</div>`;
}

function allocation() {
  const section = snapshot.allocation_context;
  return `<div class="framework-two-column">${panel('相关性矩阵', '黄金仅作为组合背景，不提供个人仓位', matrixHeat(section.labels, section.matrix))}${panel('情景差异', '符号表达历史方向关系，不构成操作建议', `<div class="framework-scenario-table"><div class="framework-scenario-head"><span>情景</span><span>黄金</span><span>美股</span><span>美债</span></div>${section.scenarios.map(item => `<article><strong>${e(item.label)}</strong><span class="mono">${e(item.gold)}</span><span class="mono">${e(item.equities)}</span><span class="mono">${e(item.bonds)}</span><p>${e(item.note)}</p></article>`).join('')}</div>${sourceStrip(section)}`)}</div>`;
}

function evidence() {
  return `<div class="framework-two-column evidence-layout">${panel('事件雷达', '事件是待验证节点，不预设方向', `<ol class="framework-timeline">${snapshot.events.map(item => `<li><time class="mono">${e(item.date)}</time><div><span class="framework-event-type">${e(item.type)}</span><strong>${e(item.title)}</strong><p>${e(item.impact)}</p></div><span class="framework-event-status">${e(item.status)}</span></li>`).join('')}</ol>`)}${panel('证据台账', '每条观察保留时间、用途与质量标签', `<div class="framework-evidence-list">${snapshot.evidence.map(item => `<article><time class="mono">${e(item.date)}</time><div><strong>${e(item.observation)}</strong><p>${e(item.source)} · ${e(item.use)}</p></div><span>${e(item.quality)}</span></article>`).join('')}</div>`)}</div>`;
}

const renderSection = { overview, drivers, supply, cycle, positioning, allocation, evidence };

export function renderGoldar(tab = 'overview') {
  const activeTab = renderSection[tab] ? tab : 'overview';
  return `<article class="framework-detail" data-framework="gold">
    <header class="framework-hero">
      <div class="framework-hero-main"><a class="framework-back" href="#/frameworks">← 研究框架</a><div class="framework-title-line"><span class="framework-symbol" aria-hidden="true">Au</span><div><span class="eyebrow">COMMODITY FRAMEWORK · V0</span><h1>${e(framework.name)}</h1></div></div><p class="framework-question">${e(framework.question)}</p><div class="framework-chain" aria-label="研究链路">${framework.chain.map((item, index) => `<span>${index ? '<i aria-hidden="true">→</i>' : ''}${e(item)}</span>`).join('')}</div></div>
      <aside class="framework-hero-meta"><span class="badge">固定样例</span><strong>${e(snapshot.meta.status)}</strong><dl><div><dt>观测</dt><dd class="mono">${e(snapshot.meta.as_of)}</dd></div><div><dt>来源</dt><dd class="mono">${snapshot.meta.source_count}</dd></div><div><dt>覆盖</dt><dd class="mono">${snapshot.meta.coverage}%</dd></div></dl></aside>
    </header>
    <div class="framework-fixture-notice" role="status"><strong>V0 视觉检查点</strong><span>本页全部数值均为固定演示数据，不代表当前市场；用于确认信息架构、密度和图表语言。</span></div>
    <nav class="framework-tabs" aria-label="黄金研究章节">${framework.sections.map(([id, label]) => `<a href="#/frameworks/gold${id === 'overview' ? '' : `?tab=${id}`}" class="${id === activeTab ? 'active' : ''}" ${id === activeTab ? 'aria-current="page"' : ''}>${e(label)}</a>`).join('')}</nav>
    <div class="framework-section" id="framework-${e(activeTab)}">${renderSection[activeTab]()}</div>
    <footer class="framework-method"><span>方法版本 ${e(framework.version)}</span><span>功能参考 <a href="https://github.com/yuxudong-morefun/goldar/tree/${e(framework.source_revision)}" target="_blank" rel="noreferrer">${e(framework.source_revision)}</a></span><span>后续：确认 V0 后接入版本化定义、快照契约与真实来源</span></footer>
  </article>`;
}
