import { escapeHTML as e } from './markdown.mjs';
import { goldFrameworkV0 } from './frameworks/fixtures/gold-v0.mjs';
import { renderGoldar } from './frameworks/goldar.mjs';

const fixtureSource = (name, asOf, proxy = false) => [{ name, url: '#', observed_at: asOf, unit: 'fixture', method: 'offline fixture', proxy }];
const fixtureGap = (label, index, severity = 'medium') => ({ id: `fixture-gap-${index}`, label, severity, next_check: '接入真实来源后更新' });

export function goldFallbackData() {
  const legacy = goldFrameworkV0;
  const { framework, snapshot: item } = legacy;
  const adaptBlock = (block, sourceName, proxy = false) => ({ ...block, as_of: block.as_of || item.meta.as_of, fetched_at: item.meta.fetched_at, sources: fixtureSource(sourceName, block.as_of || item.meta.as_of, proxy), gaps: (block.gaps || []).map((gap, index) => fixtureGap(typeof gap === 'string' ? gap : gap.label, index)) });
  return {
    framework: {
      slug: 'gold', name: framework.name, domain: 'commodity', version: '1.0.0', source_revision: framework.source_revision,
      question: framework.question, chain: framework.chain, counter_evidence: framework.counter_evidence,
      sections: framework.sections.map(([id, label]) => ({ id, label, question: `${label}的关键研究问题` })),
      method: '固定样例通过确定性因子、支持、反证和数据缺口形成研究状态。',
    },
    snapshot: {
      schema_version: 1, revision: '0'.repeat(64), as_of: item.meta.as_of, fetched_at: item.meta.fetched_at, status: item.meta.status, coverage: item.meta.coverage,
      market_context: adaptBlock({ ...item.market_context, change_percent: item.market_context.change, range_low: item.market_context.range[0], range_high: item.market_context.range[1], series: item.market_context.series.map((value, index) => ({ label: item.market_context.labels[index], value })) }, 'Illustrative gold series'),
      pricing_drivers: adaptBlock({ ...item.pricing_drivers, factors: item.pricing_drivers.factors.map(({ label, value }) => ({ label, value })), relationships: item.pricing_drivers.relationships.map(({ name, ...rest }) => ({ label: name, ...rest })) }, 'FRED fixture'),
      supply_demand: adaptBlock({ ...item.supply_demand, flows: item.supply_demand.flow_metrics }, 'Goldhub fixture'),
      cycle_macro: adaptBlock({ ...item.cycle_macro, policy_phase: '通胀后再平衡' }, 'Federal Reserve fixture'),
      options: adaptBlock({ ...item.options, strikes: item.options.strikes.map(({ tone, ...strike }) => ({ ...strike, side: tone === 'negative' ? 'pressure' : tone === 'positive' ? 'support' : 'neutral' })) }, 'GLD options fixture', true),
      research_state: item.research_state,
      allocation_context: adaptBlock({ ...item.allocation_context, diversification_note: '历史样例中黄金与股债相关性较低，关系会随制度切换。', drawdown_note: '黄金可缓和部分风险资产回撤，但流动性冲击初期也可能同步下跌。' }, 'Illustrative allocation study'),
      events: item.events,
      evidence: item.evidence.map((row) => ({ ...row, url: '#' })),
      gaps: item.meta.gaps.map((gap, index) => fixtureGap(gap, index, index === 0 ? 'high' : 'medium')),
    },
  };
}

function renderHub(catalog = null) {
  const fallback = goldFallbackData(); const gold = catalog?.items?.find((item) => item.slug === 'gold') || { ...fallback.framework, status: fallback.snapshot.status, coverage: fallback.snapshot.coverage, updated_at: fallback.snapshot.as_of };
  return `<section class="framework-hub"><header class="framework-hub-header"><div><span class="eyebrow">RESEARCH SYSTEMS</span><h1>研究框架</h1><p>把核心问题、因果链、支持与反证、数据缺口组织成可重复验证的研究工作区。</p></div><div class="framework-hub-count"><strong class="mono">01</strong><span>已注册框架</span></div></header><div class="framework-hub-guide"><strong>框架解释“为什么”</strong><span>个股、基金、债券、外汇和商品详情继续由「资产观察」负责；框架只引用结论所需的跨资产背景。</span><a href="#/workbench/assets">前往资产观察 →</a></div><div class="framework-card-grid"><a class="framework-card" href="#/frameworks/gold"><div class="framework-card-top"><span class="framework-symbol">Au</span><span class="badge">V${e(gold.version || '1.0.0')}</span></div><div><span class="eyebrow">COMMODITY</span><h2>${e(gold.name)}</h2><p>${e(gold.question)}</p></div><div class="framework-card-chain">${fallback.framework.chain.slice(0, 4).map((item) => `<span>${e(item)}</span>`).join('')}</div><footer><span>状态 <strong>${e(gold.status)}</strong></span><span>覆盖 <strong class="mono">${e(gold.coverage)}%</strong></span><span>更新 <strong class="mono">${e(gold.updated_at)}</strong></span><i>→</i></footer></a><article class="framework-card framework-card-placeholder"><div class="framework-card-top"><span class="framework-symbol muted">···</span></div><div><span class="eyebrow">PROGRESSIVE ABSTRACTION</span><h2>从真实重复项再抽象</h2><p>Dollar 与首个行业框架落地后，再提取通用章节组件；当前不预设统一大模板。</p></div></article></div></section>`;
}

export function renderFrameworks({ slug = null, anchor = 'overview', catalog = null, data = null, status = 'ready', error = '', bot = {} } = {}) {
  if (!slug) return renderHub(catalog);
  if (slug !== 'gold') return `<section class="framework-not-found"><span class="eyebrow">FRAMEWORK NOT FOUND</span><h1>研究框架不存在</h1><p>当前 V1 只注册 Goldar。</p><a class="button" href="#/frameworks">返回研究框架</a></section>`;
  if (status === 'loading') return '<section class="framework-loading" role="status"><span></span><strong>正在读取黄金研究框架…</strong></section>';
  if (status === 'error' && !data) return `<section class="framework-not-found" role="alert"><span class="eyebrow">FRAMEWORK UNAVAILABLE</span><h1>框架数据暂时不可用</h1><p>${e(error || '请稍后刷新。')}</p><button class="button" type="button" data-framework-retry>重新读取</button></section>`;
  return `${status === 'error' ? `<div class="framework-data-warning" role="status">实时数据读取失败，当前显示离线样例：${e(error)}</div>` : ''}${renderGoldar(data || goldFallbackData(), { anchor, bot })}`;
}
