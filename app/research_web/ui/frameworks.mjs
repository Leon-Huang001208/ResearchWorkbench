import { escapeHTML as e } from './markdown.mjs';
import { renderEmbedded } from './frameworks/embedded.mjs';

const frameworkMeta = {
  gold: {
    symbol: 'Au', domain: 'COMMODITY', name: '黄金研究框架',
    question: '黄金当前由哪组实际利率、美元、避险需求与实物资金力量共同定价？',
    chain: ['宏观状态', '定价驱动', '供需资金', '期权配置'],
  },
  dollar: {
    symbol: '$', domain: 'LIQUIDITY', name: '美元流动性研究框架',
    question: '美元流动性当前由总量、资金价格、财政水流、融资管道与跨境需求中的哪一环主导？',
    chain: ['Q 总量', 'P 价格', 'g 财政', 'M 管道', 'X 跨境'],
  },
  'ai-economy': {
    symbol: 'AI', domain: 'INDUSTRY', name: 'AI如何改变经济与市场',
    question: 'AI 如何从算力、模型、应用到宏观经济与市场定价逐层传导？',
    chain: ['算力', '模型', '应用', '经济', '市场'],
  },
  'bond-framework': {
    symbol: '债', domain: 'MACRO', name: '债市分析框架',
    question: '当前债市由基本面、政策面、资金面和供需面中的哪些力量主导？',
    chain: ['基本面', '政策面', '资金面', '供需面'],
  },
  elnino: {
    symbol: 'EN', domain: 'MACRO', name: '厄尔尼诺',
    question: '厄尔尼诺/拉尼娜周期如何影响农产品、能源与全球资产定价？',
    chain: ['周期', '气候', '农业', '能源', '资产'],
  },
  'fund-track-selection': {
    symbol: '基', domain: 'STRATEGY', name: '如何通过赛道选基金',
    question: '如何用赛道视角筛选、比较和跟踪主题基金？',
    chain: ['赛道定义', '基金筛选', '业绩比较', '跟踪调仓'],
  },
  'memory-chips-60': {
    symbol: '存', domain: 'INDUSTRY', name: '存储芯片60年',
    question: '存储芯片60年产业周期与技术变迁如何影响当前投资？',
    chain: ['历史', '周期', '技术', '竞争', '投资'],
  },
  'inference-chips-42': {
    symbol: '推', domain: 'INDUSTRY', name: '推理芯片42年',
    question: '推理芯片42年演进如何塑造 AI 算力竞争格局？',
    chain: ['历史', '架构', '生态', '竞争', '投资'],
  },
  'model-hardware-chain': {
    symbol: '硬', domain: 'INDUSTRY', name: '模型如何催化硬件产业链',
    question: '大模型迭代如何沿硬件产业链传导需求与供给？',
    chain: ['模型', '算力', '网络', '存储', '制造'],
  },
  'gold-cycle': {
    symbol: 'Au+', domain: 'COMMODITY', name: '黄金大周期研究框架',
    question: '黄金在大周期中由哪些长期力量定价？',
    chain: ['货币', '实际利率', '央行', '地缘', '周期'],
  },
  ainvest: {
    symbol: 'AI+', domain: 'INDUSTRY', name: 'AInvest AI产业链雷达',
    question: 'AI 产业链各环节的热度、映射、业绩与实物拆解如何变化？',
    chain: ['热力图', '产业链', '焦点', '实物拆解', '宏观'],
  },
};

export function frameworkName(slug) {
  return frameworkMeta[slug]?.name || '框架详情';
}

function frameworkCard(slug, catalog) {
  const meta = frameworkMeta[slug];
  const item = catalog?.items?.find((candidate) => candidate.slug === slug) || {};
  return `<a class="framework-card" href="#/frameworks/${slug}" data-framework-card="${slug}"><div class="framework-card-top"><span class="framework-symbol">${e(meta.symbol)}</span><span class="badge">V${e(item.version || '—')}</span></div><div class="framework-card-body"><span class="eyebrow">${e(meta.domain)}</span><h2>${e(item.name || meta.name)}</h2><p>${e(item.question || meta.question)}</p></div><div class="framework-card-chain">${meta.chain.map((part) => `<span>${e(part)}</span>`).join('')}</div><footer><span>状态 <strong>${e(item.status || '等待服务')}</strong></span><span>覆盖 <strong class="mono">${item.coverage == null ? '—' : `${e(item.coverage)}%`}</strong></span><span>更新 <strong class="mono">${e(item.updated_at || '—')}</strong></span><i>→</i></footer></a>`;
}

export function renderFrameworks({ slug = null, catalog = null, data = null, status = 'ready', error = '', bot = {} } = {}) {
  if (!slug) {
    const count = catalog?.items?.length || Object.keys(frameworkMeta).length;
    const slugs = Object.keys(frameworkMeta);
    return `<section class="framework-hub"><header class="framework-hub-header"><div><span class="eyebrow">RESEARCH SYSTEMS</span><h1>研究框架</h1><p>把核心问题、因果链、支持与反证、数据缺口组织成可重复验证的研究工作区。</p></div><div class="framework-hub-count"><strong class="mono">${String(count).padStart(2, '0')}</strong><span>已注册框架</span></div></header><div class="framework-card-grid">${slugs.map((s) => frameworkCard(s, catalog)).join('')}</div></section>`;
  }
  const meta = frameworkMeta[slug];
  if (!meta) {
    return '<section class="framework-not-found"><span class="eyebrow">FRAMEWORK NOT FOUND</span><h1>研究框架不存在</h1><p>当前注册的研究框架未包含该标识。</p><a class="button" href="#/frameworks">返回研究框架</a></section>';
  }
  if (status === 'loading' && !data) return `<section class="framework-loading" role="status"><span></span><strong>正在读取${e(meta.name)}…</strong></section>`;
  if (status === 'error' && !data) return `<section class="framework-not-found" role="alert"><span class="eyebrow">FRAMEWORK UNAVAILABLE</span><h1>框架数据暂时不可用</h1><p>${e(error || '请稍后刷新。')}</p><button class="button" type="button" data-framework-retry>重新读取</button></section>`;
  if (!data) return '<section class="framework-not-found" role="status"><h1>框架快照尚未生成</h1><p>服务端完成首次采集后再显示数据，不使用浏览器样例冒充实时结果。</p></section>';
  if (data.framework?.slug !== slug) return `<section class="framework-loading" role="status"><span></span><strong>正在读取${e(meta.name)}…</strong></section>`;
  return `${status === 'error' ? `<div class="framework-bot-error" role="alert">刷新失败，保留上次快照：${e(error)}</div>` : ''}${renderEmbedded(data, { bot })}`;
}

