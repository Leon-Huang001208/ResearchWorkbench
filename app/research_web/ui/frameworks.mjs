import { escapeHTML as e } from './markdown.mjs';
import { renderDollar } from './frameworks/dollar.mjs';
import { renderGoldar } from './frameworks/goldar.mjs';

const frameworkMeta = {
  gold: {
    symbol: 'Au', domain: 'COMMODITY', name: '黄金研究框架',
    question: '黄金当前由哪组实际利率、美元、避险需求与实物资金力量共同定价？',
    chain: ['宏观状态', '定价驱动', '供需资金', '期权配置'],
  },
  dollar: {
    symbol: '$', domain: 'LIQUIDITY', name: '美元流动性框架',
    question: '美元流动性正在通过总量、价格、财政、融资管道与跨境渠道偏松还是偏紧？',
    chain: ['Q 总量', 'P 价格', 'g 财政', 'M 管道', 'X 跨境'],
  },
};

function frameworkCard(slug, catalog) {
  const meta = frameworkMeta[slug];
  const item = catalog?.items?.find((candidate) => candidate.slug === slug) || {};
  return `<a class="framework-card" href="#/frameworks/${slug}" data-framework-card="${slug}"><div class="framework-card-top"><span class="framework-symbol">${e(meta.symbol)}</span><span class="badge">V${e(item.version || '—')}</span></div><div><span class="eyebrow">${e(meta.domain)}</span><h2>${e(item.name || meta.name)}</h2><p>${e(item.question || meta.question)}</p></div><div class="framework-card-chain">${meta.chain.map((part) => `<span>${e(part)}</span>`).join('')}</div><footer><span>状态 <strong>${e(item.status || '等待服务')}</strong></span><span>覆盖 <strong class="mono">${item.coverage == null ? '—' : `${e(item.coverage)}%`}</strong></span><span>更新 <strong class="mono">${e(item.updated_at || '—')}</strong></span><i>→</i></footer></a>`;
}

function renderHub(catalog = null) {
  return `<section class="framework-hub"><header class="framework-hub-header"><div><span class="eyebrow">RESEARCH SYSTEMS</span><h1>研究框架</h1><p>把核心问题、因果链、支持与反证、数据缺口组织成可重复验证的研究工作区。</p></div><div class="framework-hub-count"><strong class="mono">02</strong><span>已注册框架</span></div></header><div class="framework-hub-guide"><strong>框架解释“为什么”</strong><span>个股、基金、债券、外汇和商品详情继续由「资产观察」负责；框架只引用结论所需的跨资产背景。</span><a href="#/workbench/assets">前往资产观察 →</a></div><div class="framework-card-grid">${frameworkCard('gold', catalog)}${frameworkCard('dollar', catalog)}</div></section>`;
}

export function renderFrameworks({ slug = null, anchor = 'overview', catalog = null, data = null, status = 'ready', error = '', bot = {} } = {}) {
  if (!slug) return renderHub(catalog);
  const renderer = { gold: renderGoldar, dollar: renderDollar }[slug];
  if (!renderer) return '<section class="framework-not-found"><span class="eyebrow">FRAMEWORK NOT FOUND</span><h1>研究框架不存在</h1><p>当前仅注册黄金与美元流动性框架。</p><a class="button" href="#/frameworks">返回研究框架</a></section>';
  if (status === 'loading' && !data) return `<section class="framework-loading" role="status"><span></span><strong>正在读取${e(frameworkMeta[slug].name)}…</strong></section>`;
  if (status === 'error' && !data) return `<section class="framework-not-found" role="alert"><span class="eyebrow">FRAMEWORK UNAVAILABLE</span><h1>框架数据暂时不可用</h1><p>${e(error || '请稍后刷新。')}</p><button class="button" type="button" data-framework-retry>重新读取</button></section>`;
  if (!data) return '<section class="framework-not-found" role="status"><h1>框架快照尚未生成</h1><p>服务端完成首次采集后再显示数据，不使用浏览器样例冒充实时结果。</p></section>';
  return `${status === 'error' ? `<div class="framework-data-warning" role="status">刷新失败，保留上一次已读取快照：${e(error)}</div>` : ''}${renderer(data, { anchor, bot })}`;
}
