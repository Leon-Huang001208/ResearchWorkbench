import { escapeHTML as e } from './markdown.mjs';
import { goldFrameworkV0 } from './frameworks/fixtures/gold-v0.mjs';
import { renderGoldar } from './frameworks/goldar.mjs';

function renderHub() {
  const { framework, snapshot } = goldFrameworkV0;
  return `<section class="framework-hub">
    <header class="framework-hub-header"><div><span class="eyebrow">RESEARCH SYSTEMS</span><h1>研究框架</h1><p>把核心问题、因果链、支持与反证、数据缺口组织成可重复验证的研究工作区。</p></div><div class="framework-hub-count"><strong class="mono">01</strong><span>已注册框架</span></div></header>
    <div class="framework-hub-guide" aria-label="研究框架与资产观察边界"><strong>框架解释“为什么”</strong><span>黄金、美债、美元等行情与资产详情继续由「资产观察」负责；框架只引用解释结论所需的背景。</span><a href="#/workbench/assets">前往资产观察 →</a></div>
    <div class="framework-card-grid">
      <a class="framework-card" href="#/frameworks/gold">
        <div class="framework-card-top"><span class="framework-symbol" aria-hidden="true">Au</span><span class="badge">V0 · 固定样例</span></div>
        <div><span class="eyebrow">COMMODITY</span><h2>${e(framework.name)}</h2><p>${e(framework.question)}</p></div>
        <div class="framework-card-chain">${framework.chain.slice(0, 4).map(item => `<span>${e(item)}</span>`).join('')}</div>
        <footer><span>状态 <strong>${e(snapshot.meta.status)}</strong></span><span>覆盖 <strong class="mono">${snapshot.meta.coverage}%</strong></span><span>更新 <strong class="mono">${e(snapshot.meta.as_of)}</strong></span><i aria-hidden="true">→</i></footer>
      </a>
      <article class="framework-card framework-card-placeholder" aria-label="后续框架占位"><div class="framework-card-top"><span class="framework-symbol muted" aria-hidden="true">···</span></div><div><span class="eyebrow">PROGRESSIVE ABSTRACTION</span><h2>从真实重复项再抽象</h2><p>Dollar 与首个行业框架落地后，再提取通用章节组件；当前不预设统一大模板。</p></div></article>
    </div>
  </section>`;
}

export function renderFrameworks({ slug = null, tab = 'overview' } = {}) {
  if (!slug) return renderHub();
  if (slug === 'gold') return renderGoldar(tab);
  console.warn('[ResearchWeb] framework_route_not_found', { status: 'not_found' });
  return `<section class="framework-not-found"><span class="eyebrow">FRAMEWORK NOT FOUND</span><h1>研究框架不存在</h1><p>当前 V1 只注册 Goldar。</p><a class="button" href="#/frameworks">返回研究框架</a></section>`;
}
