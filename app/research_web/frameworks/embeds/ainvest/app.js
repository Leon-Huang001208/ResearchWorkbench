/* AI 产业链雷达 前端 */
const $ = s => document.querySelector(s);
const APP_BASE = location.pathname.startsWith('/frameworks-embed/ainvest') ? '/frameworks-embed/ainvest' : (location.pathname.startsWith('/ainvest/') ? '/ainvest' : '');
const apiUrl = path => APP_BASE + (path.startsWith('/api/') ? path + '.json' : path);
let TAX = null, JUDG = {}, HYPE = { items: [], phases: [] }, CHAIN = { cols: [], edges: [] };
let selectedId = null;
const nodeCache = new Map();
let heatmapCache = null;
let rotationCache = null;
const parentOf = new Map();
const nodeById = new Map();

/* ---------- 主题 ---------- */
const THEME_NAMES = { auto: '自动', light: '浅色', dark: '深色' };
function applyTheme(t) {
  document.documentElement.dataset.theme = t;
  $('#btn-theme').textContent = '主题：' + THEME_NAMES[t];
  localStorage.setItem('acr-theme', t);
}
applyTheme(localStorage.getItem('acr-theme') || 'auto');
$('#btn-theme').addEventListener('click', () => {
  const order = ['auto', 'light', 'dark'];
  const cur = document.documentElement.dataset.theme;
  applyTheme(order[(order.indexOf(cur) + 1) % 3]);
  if (selectedId === '__overview') renderGartner(); // 重绘取新配色
});
$('#brand-home').addEventListener('click', () => showOverview());

/* ---------- 树索引 ---------- */
function indexTree(node, parent) {
  nodeById.set(node.id, node);
  if (parent) parentOf.set(node.id, parent.id);
  (node.children || []).forEach(c => indexTree(c, node));
}
function depthOf(id) { let d = 0, cur = id; while (parentOf.has(cur)) { cur = parentOf.get(cur); d++; } return d; }
function l2AncestorOf(id) { let cur = id; while (depthOf(cur) > 2) cur = parentOf.get(cur); return depthOf(cur) === 2 ? cur : id; }

/* ---------- 启动 ---------- */
async function boot() {
  const r = await fetch(apiUrl('/api/bootstrap'));
  const d = await r.json();
  TAX = d.taxonomy; JUDG = d.judgments || {}; HYPE = d.hype || HYPE; CHAIN = d.chain || CHAIN;
  indexTree(TAX, null);
  const nt = d.meta.newsUpdatedAt
    ? new Date(d.meta.newsUpdatedAt).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false })
    : '-';
  $('#meta-info').textContent = `资讯 ${d.meta.newsCount} 条 · 研报 ${d.meta.reportsCount} 篇 · 数据更新 ${nt}`;
  renderSidebar();
  showOverview();
}

function renderSidebar() {
  const navLabel = (icon, label) => `<span class="nav-label"><span class="nav-icon icon-${icon}" aria-hidden="true"></span><span>${label}</span></span>`;
  const l1Icons = { upstream: 'cpu', midstream: 'cloud', downstream: 'apps' };
  let html = `<div class="l2 overview" data-id="__overview">${navLabel('dashboard', '总览 · 热力图')}</div>` +
    `<div class="l2 overview" data-id="__phys">${navLabel('stack', '图解产业链')}</div>` +
    `<div class="l2 overview" data-id="__feed">${navLabel('news', '信息流')}</div>` +
    `<div class="l2 overview" data-id="__timeline">${navLabel('calendar', '时间线')}</div>` +
    `<div class="l2 overview" data-id="__industry">${navLabel('apps', '行业数据')}</div>` +
    `<div class="l2 overview" data-id="__macro">${navLabel('trending-up', '宏观研究')}</div>` +
    `<div class="l2 overview" data-id="__bubble">${navLabel('bolt', '泡沫监控')}</div>`;
  html += (TAX.children || []).map(l1 => {
    const items = (l1.children || []).map(l2 =>
      `<div class="l2" data-id="${l2.id}"><span>${l2.name}</span><span class="cnt">${countNodes(l2)}</span></div>`
    ).join('');
    return `<div class="l1">${navLabel(l1Icons[l1.id] || 'apps', l1.name)}</div>${items}`;
  }).join('');
  $('#sidebar').innerHTML = html;
  $('#sidebar').addEventListener('click', e => {
    const el = e.target.closest('.l2');
    if (!el) return;
    if (el.dataset.id === '__overview') showOverview();
    else if (el.dataset.id === '__phys') showPhys();
    else if (el.dataset.id === '__feed') showFeed();
    else if (el.dataset.id === '__timeline') showTimeline();
    else if (el.dataset.id === '__industry') showIndustry();
    else if (el.dataset.id === '__macro') showMacro();
    else if (el.dataset.id === '__bubble') showBubble();
    else select(el.dataset.id);
  });
}
function countNodes(node) { let n = 0; (function w(x) { n++; (x.children || []).forEach(w); })(node); return n; }
function setActive(id) { document.querySelectorAll('.l2').forEach(el => el.classList.toggle('active', el.dataset.id === id)); }

/* ---------- 视图切换 ---------- */
function showView(name) {
  $('#view-overview').style.display = name === 'overview' ? '' : 'none';
  $('#view-feed').style.display = name === 'feed' ? '' : 'none';
  $('#view-timeline').style.display = name === 'timeline' ? '' : 'none';
  $('#view-industry').style.display = name === 'industry' ? '' : 'none';
  $('#view-topic').style.display = name === 'topic' ? '' : 'none';
  $('#view-macro').style.display = name === 'macro' ? '' : 'none';
  $('#view-phys').style.display = name === 'phys' ? '' : 'none';
  $('#view-bubble').style.display = name === 'bubble' ? '' : 'none';
  $('#view-node').style.display = name === 'node' ? '' : 'none';
  document.querySelector('.layout').classList.toggle('topic-layout', name === 'topic');
}

/* ---------- 图解产业链 ---------- */
let physCache = null, physSceneId = null, physSelPart = null;
const physSvgCache = new Map();
function enhancePhysFlows(stage) {
  const svg = stage.querySelector('svg');
  if (!svg) return;
  const ns = 'http://www.w3.org/2000/svg';
  const flows = svg.querySelectorAll('path.ph-flow, path.ph-dash, path.ph-route, path.ph-lead, line.ph-lead, .ph-lead path, .ph-lead line, path[stroke-dasharray], line[stroke-dasharray]');
  flows.forEach((flow, i) => {
    if (flow.dataset.flowEnhanced) return;
    flow.dataset.flowEnhanced = '1';
    flow.classList.add('ph-route');
    flow.removeAttribute('stroke-dasharray');
    const d = flow.tagName.toLowerCase() === 'line'
      ? `M${flow.getAttribute('x1')} ${flow.getAttribute('y1')}L${flow.getAttribute('x2')} ${flow.getAttribute('y2')}`
      : flow.getAttribute('d');
    if (!d) return;
    let length = 160;
    try { length = flow.getTotalLength(); } catch { /* 绘图元素不支持长度时使用默认时长 */ }
    const dot = document.createElementNS(ns, 'circle');
    dot.setAttribute('class', 'ph-route-dot');
    dot.setAttribute('r', '2');
    dot.setAttribute('pointer-events', 'none');
    const motion = document.createElementNS(ns, 'animateMotion');
    motion.setAttribute('path', d);
    motion.setAttribute('dur', `${Math.max(1.8, Math.min(5.5, length / 72)).toFixed(1)}s`);
    motion.setAttribute('repeatCount', 'indefinite');
    motion.setAttribute('begin', `${-(i % 5) * 0.45}s`);
    const pulse = document.createElementNS(ns, 'animate');
    pulse.setAttribute('attributeName', 'opacity');
    pulse.setAttribute('values', '.3;1;.3');
    pulse.setAttribute('dur', motion.getAttribute('dur'));
    pulse.setAttribute('repeatCount', 'indefinite');
    dot.append(motion, pulse);
    flow.parentNode.append(dot);
  });
}
async function showPhys() {
  selectedId = '__phys';
  setActive('__phys');
  showView('phys');
  if (!physCache) {
    const r = await fetch(apiUrl('/api/physmap'));
    physCache = await r.json();
  }
  if (selectedId !== '__phys') return;
  renderPhysScene(physSceneId || physCache.rootScene);
}
async function fetchSceneSvg(file) {
  if (physSvgCache.has(file)) return physSvgCache.get(file);
  const r = await fetch(apiUrl('/' + file));
  const t = await r.text();
  physSvgCache.set(file, t);
  return t;
}
async function renderPhysScene(id) {
  const sc = physCache.scenes[id];
  if (!sc) return;
  physSceneId = id; physSelPart = null;
  renderPhysCrumbs();
  const stage = $('#ph-stage');
  const svgText = await fetchSceneSvg(sc.svg);
  if (physSceneId !== id || selectedId !== '__phys') return;
  stage.classList.add('ph-fade');
  stage.innerHTML = svgText;
  enhancePhysFlows(stage);
  stage.querySelectorAll('.ph-hot').forEach(g => {
    g.addEventListener('click', e => { e.stopPropagation(); onPhysPart(g); });
  });
  setTimeout(() => stage.classList.remove('ph-fade'), 30);
  renderPhysPanel(null);
}
function physChain(id) {
  const chain = [];
  let cur = id;
  while (cur) { chain.unshift(cur); cur = (physCache.scenes[cur] || {}).parent; }
  return chain;
}
function renderPhysCrumbs() {
  const chain = physChain(physSceneId);
  $('#ph-crumbs').innerHTML = chain.map((sid, i) => {
    const sc = physCache.scenes[sid];
    const cur = i === chain.length - 1;
    return `<span class="ph-crumb${cur ? ' cur' : ''}" data-scene="${sid}">${sc.crumb}</span>` + (cur ? '' : '<span class="ph-crumb-sep">›</span>');
  }).join('');
  document.querySelectorAll('#ph-crumbs .ph-crumb:not(.cur)').forEach(el => {
    el.addEventListener('click', () => renderPhysScene(el.dataset.scene));
  });
}
function onPhysPart(g) {
  const pid = g.dataset.part;
  const part = physCache.parts[pid];
  if (!part) return;
  if (part.drill) { physZoomInto(g, () => renderPhysScene(part.drill)); return; }
  physSelPart = pid;
  document.querySelectorAll('#ph-stage .ph-hot').forEach(el => el.classList.toggle('ph-sel', el.dataset.part === pid));
  renderPhysPanel(pid);
}
function physZoomInto(g, done) {
  const svg = document.querySelector('#ph-stage svg');
  if (!svg) return done();
  let bb;
  try { bb = g.getBBox(); } catch { return done(); }
  const vb = svg.viewBox.baseVal;
  const pad = Math.max(bb.width, bb.height) * 0.25 + 10;
  const to = { x: bb.x - pad, y: bb.y - pad, w: bb.width + pad * 2, h: bb.height + pad * 2 };
  const from = { x: vb.x, y: vb.y, w: vb.width, h: vb.height };
  const t0 = performance.now(), D = 340;
  let finished = false;
  const finish = () => { if (finished) return; finished = true; done(); };
  $('#ph-stage').classList.add('ph-fade');
  (function step() {
    const t = Math.min(1, (performance.now() - t0) / D), e = 1 - Math.pow(1 - t, 3);
    svg.setAttribute('viewBox', `${from.x + (to.x - from.x) * e} ${from.y + (to.y - from.y) * e} ${from.w + (to.w - from.w) * e} ${from.h + (to.h - from.h) * e}`);
    if (t < 1 && !finished) requestAnimationFrame(step); else finish();
  })();
  setTimeout(finish, D + 80); // rAF 被节流（后台标签页等）时兜底，保证导航完成
}
async function renderPhysPanel(pid) {
  const panel = $('#ph-panel');
  const sc = physCache.scenes[physSceneId];
  if (!pid) {
    const parts = Object.entries(physCache.parts).filter(([, p]) => p.sceneOf === physSceneId);
    panel.innerHTML = `<div class="ph-p-name">${sc.title}</div>
      <div class="ph-p-desc">${sc.desc || ''}</div>
      <div class="ph-p-sec">本层部件 · 点图中部件或下方名称</div>
      <div class="ph-p-parts">${parts.map(([id, p]) => `<span class="ph-p-chip${p.drill ? ' drill' : ''}" data-pid="${id}">${p.name}${p.drill ? ' ⊕' : ''}</span>`).join('')}</div>`;
    panel.querySelectorAll('.ph-p-chip').forEach(el => {
      el.addEventListener('click', () => {
        const g = document.querySelector(`#ph-stage .ph-hot[data-part="${el.dataset.pid}"]`);
        if (g) onPhysPart(g);
      });
    });
    return;
  }
  const part = physCache.parts[pid];
  let html = `<div class="ph-p-name">${part.name}</div><div class="ph-p-desc">${part.desc || ''}</div>`;
  if (part.materials && part.materials.length) {
    html += `<div class="ph-p-sec">${part.matTitle || '材料与矿产'}</div><div class="ph-mat">${part.materials.map(m =>
      `<div class="ph-mat-item">${m.m}${m.note ? `<span class="note">${m.note}</span>` : ''}</div>`).join('')}</div>`;
  }
  if (part.chain && physCache.scenes[part.chain]) {
    html += `<div><button class="ph-node-btn" id="ph-chain-btn">${part.chainLabel || '查看制造链 →'}</button></div>`;
  }
  html += '<div id="ph-node-block"></div>';
  panel.innerHTML = html;
  const chainBtn = $('#ph-chain-btn');
  if (chainBtn) chainBtn.addEventListener('click', () => renderPhysScene(part.chain));
  if (part.taxonomyId && nodeById.has(part.taxonomyId)) {
    const data = await fetchNode(part.taxonomyId);
    if (physSelPart !== pid || selectedId !== '__phys') return;
    const tks = (data.tickers || []).slice(0, 5);
    $('#ph-node-block').innerHTML = `<div class="ph-p-sec">对应赛道 · ${data.name}</div>` +
      tks.map(t => `<div class="ph-tk"><span>${t.n}</span><span class="${pctCls(t.pct)}">${fmtPct(t.pct)}</span></div>`).join('') +
      '<button class="ph-node-btn" id="ph-goto-node">进入环节页 · 标的研报资讯 →</button>';
    $('#ph-goto-node').addEventListener('click', () => select(part.taxonomyId));
  }
}

/* ---------- AI 泡沫监控 ---------- */
let bubbleCache = null;
const DIM_TAKEAWAY = {
  demand: '调用量和付费比例仍在增长，但模型能力进步速度、Token 日均使用量增速和 ARR 增速放缓；使用量加权 Token 支出环比 +32%，替代经济性仍受成本约束。',
  cashflow: '云收入同比 +44% 至 1166 亿美元，但资本开支同比 +87% 至 1815 亿美元；资本开支/经营性现金流升至 97%，自由现金流不足 50 亿美元，是当前最主要压力。',
  funding: '外部融资对扩张的作用上升，但融资仍处初期，负债、债券发行、信用利差和风险投资尚未显示投资主体全面泡沫化。',
  constraint: '就业端存在挤出压力，但数据中心建筑额仍同比增长 27%，社区、监管等约束暂不足以抵消 AI 对总投资的拉动。',
};
/* ---------- 宏观研究 ---------- */
let macroCache = null;
function macroFmt(v, unit) {
  if (v == null) return '-';
  if (unit === '人') return Math.round(v).toLocaleString('zh-CN');
  const abs = Math.abs(v);
  const n = abs >= 1000 ? v.toLocaleString('zh-CN', { maximumFractionDigits: 0 }) : v.toFixed(2).replace(/\.?0+$/, '') || '0';
  return `${n}${unit && unit !== '人' ? unit.replace(' YoY', '') : ''}`;
}
function macroChange(v, unit) {
  if (v == null) return '-';
  const sign = v > 0 ? '+' : '';
  if (unit === '人') return `${sign}${Math.round(v).toLocaleString('zh-CN')}`;
  return `${sign}${v.toFixed(2).replace(/\.?0+$/, '') || '0'}${unit === '%' || unit === 'ppt' || unit === '% YoY' ? (unit === '% YoY' ? 'ppt' : unit) : ''}`;
}
async function showMacro() {
  selectedId = '__macro';
  setActive('__macro');
  showView('macro');
  if (!macroCache || Date.now() - macroCache.t > 300_000) {
    const r = await fetch(apiUrl('/api/macro'));
    macroCache = { t: Date.now(), data: await r.json() };
  }
  if (selectedId !== '__macro') return;
  renderMacro(macroCache.data);
}
function renderMacro(d) {
  const meta = d._meta || {};
  $('#macro-updated').textContent = `数据更新 ${meta.updatedAt || ''}`;
  $('#macro-regime-label').textContent = (meta.regime && meta.regime.label) || '';
  $('#macro-regime-text').textContent = (meta.regime && meta.regime.text) || '';

  const KEY_IDS = ['ust10y', 'curve-10y2y', 'hy-oas', 'vix', 'cpi', 'core-pce'];
  const byId = new Map((d.indicators || []).map(i => [i.id, i]));
  $('#macro-strip').innerHTML = KEY_IDS.map(id => {
    const i = byId.get(id);
    if (!i) return '';
    return `<div class="idx"><div class="n">${esc(i.name)}</div><div class="p">${macroFmt(i.value, i.unit)}</div>` +
      `<div class="c ${pctCls(i.mom)}">${i.mom == null ? '' : macroChange(i.mom, i.unit) + ' 环比'}</div></div>`;
  }).join('');

  $('#macro-groups').innerHTML = (d.categories || []).map(cat => {
    const rows = (d.indicators || []).filter(i => i.cat === cat.id);
    const trs = rows.map(i => {
      const live = i.refreshedBy ? '<span class="bb-live">实时跟踪</span>' : '';
      return `<div class="bb-row">
        <div class="bb-name">${esc(i.name)}<span class="bb-meaning">${esc(i.meaning)}</span></div>
        <div class="bb-region">${esc(i.region || '-')}</div>
        <div class="bb-value">${macroFmt(i.value, i.unit)}</div>
        <div class="bb-mom">环比 ${macroChange(i.mom, i.unit)}</div>
        <div class="bb-yoy">同比 ${i.yoy == null ? '-' : macroChange(i.yoy, i.unit)}</div>
        <div class="bb-tr">${bubbleTrendIcon(i.trend)}</div>
        <div class="bb-src">${esc(i.source)}${live}</div>
      </div>`;
    }).join('');
    return `<div class="bb-dim-card bb-macro-cat">
      <div class="bb-dim-head"><span class="bb-dim-name">${esc(cat.name)}</span><span class="bb-dim-role">${rows.length} 项</span></div>
      <div class="bb-dim-desc">${esc(cat.desc)}</div>
      <div class="bb-dim-take">${esc(cat.aiNote || '')}</div>
      <div class="bb-group" style="border:none;margin-top:6px">${trs}</div>
    </div>`;
  }).join('');
}
async function showBubble() {
  selectedId = '__bubble';
  setActive('__bubble');
  showView('bubble');
  if (!bubbleCache || Date.now() - bubbleCache.t > 300_000) {
    const r = await fetch(apiUrl('/api/bubble'));
    bubbleCache = { t: Date.now(), data: await r.json() };
  }
  if (selectedId !== '__bubble') return;
  renderBubble(bubbleCache.data);
}
function bubbleTrendIcon(t) {
  if (t === 'up') return '<span class="bb-trend bb-up">▲</span>';
  if (t === 'down') return '<span class="bb-trend bb-down">▼</span>';
  return '<span class="bb-trend bb-flat">–</span>';
}
function bubbleFmt(v, unit) {
  if (v == null) return '-';
  const n = Math.abs(v) >= 100 ? v.toFixed(1) : v.toFixed(2).replace(/\.?0+$/, '') || '0';
  return `${n}${unit === '%' || unit === 'ppt' ? unit : ''}`;
}
function bubbleValue(i) {
  const value = i.displayValue != null ? esc(i.displayValue) : bubbleFmt(i.value, i.unit);
  const unit = i.displayUnit || (i.unit !== '%' && i.unit !== 'ppt' ? i.unit : '');
  return `${value}<span class="bb-unit">${unit ? esc(unit) : ''}</span>`;
}
function bubblePct(v) {
  if (v == null) return '-';
  const n = Math.abs(v) >= 100 ? v.toFixed(1) : v.toFixed(2).replace(/\.?0+$/, '') || '0';
  return `${v > 0 ? '+' : ''}${n}%`;
}
const BB_STOPS = [
  { p: 0, c: [59, 130, 246] }, { p: 25, c: [34, 193, 195] }, { p: 50, c: [92, 184, 92] },
  { p: 70, c: [224, 167, 43] }, { p: 100, c: [213, 69, 60] },
];
function bbColorAt(pct) {
  pct = Math.max(0, Math.min(100, pct));
  let a = BB_STOPS[0], b = BB_STOPS[BB_STOPS.length - 1];
  for (let i = 0; i < BB_STOPS.length - 1; i++) {
    if (pct >= BB_STOPS[i].p && pct <= BB_STOPS[i + 1].p) { a = BB_STOPS[i]; b = BB_STOPS[i + 1]; break; }
  }
  const t = b.p === a.p ? 0 : (pct - a.p) / (b.p - a.p);
  const rgb = a.c.map((v, i) => Math.round(v + (b.c[i] - v) * t));
  return `rgb(${rgb.join(',')})`;
}
function bbZone(score) {
  if (score < 20) return '冰点 · 极度悲观';
  if (score < 40) return '偏冷 · 验证不足';
  if (score < 60) return '温和 · 基本面追赶中';
  if (score < 80) return '偏热 · 需保持警惕';
  return '过热 · 泡沫信号强烈';
}
function bbArcPoint(cx, cy, r, t) {
  const rad = (180 - t * 180) * Math.PI / 180;
  return { x: cx + r * Math.cos(rad), y: cy - r * Math.sin(rad) };
}
function renderBubbleGauge(d) {
  const temp = (d._meta && d._meta.temperature) || {};
  const score = Math.max(0, Math.min(100, temp.score ?? 50));
  const cx = 130, cy = 118, r = 96, sw = 20;
  let arcPath = '';
  for (let i = 0; i <= 48; i++) {
    const p = bbArcPoint(cx, cy, r, i / 48);
    arcPath += (i === 0 ? 'M' : 'L') + `${p.x.toFixed(1)},${p.y.toFixed(1)} `;
  }
  const needleP = bbArcPoint(cx, cy, r - sw / 2 - 8, score / 100);
  const svg = $('#bb-gauge-svg');
  svg.innerHTML = `<defs><linearGradient id="bb-grad" x1="${cx - r}" y1="0" x2="${cx + r}" y2="0" gradientUnits="userSpaceOnUse">` +
    BB_STOPS.map(s => `<stop offset="${s.p}%" stop-color="rgb(${s.c.join(',')})"/>`).join('') +
    `</linearGradient></defs>` +
    `<path d="${arcPath.trim()}" fill="none" stroke="url(#bb-grad)" stroke-width="${sw}" stroke-linecap="round"/>` +
    `<line x1="${cx}" y1="${cy}" x2="${needleP.x.toFixed(1)}" y2="${needleP.y.toFixed(1)}" class="bb-needle"/>` +
    `<circle cx="${cx}" cy="${cy}" r="7" class="bb-hub"/>`;
  $('#bb-gauge-score').textContent = Math.round(score);
  $('#bb-gauge-score').style.color = bbColorAt(score);
  $('#bb-gauge-label').textContent = temp.label || bbZone(score);
  $('#bb-gauge-methodology').textContent = temp.methodology || '';

  $('#bb-gauge-breakdown').innerHTML = (d.dimensions || []).map(dim => {
    const w = Math.round((dim.tempWeight || 0) * 100);
    const s = dim.tempScore;
    const barW = s == null ? 0 : Math.round(s);
    const color = s == null ? 'var(--chip-bg)' : bbColorAt(s);
    return `<div class="bb-gb-row"><span class="bb-gb-name">${esc(dim.name)}</span>` +
      `<div class="bb-gb-bar"><div style="width:${barW}%;background:${color}"></div></div>` +
      `<span class="bb-gb-val">${s == null ? '-' : Math.round(s)} <span class="bb-gb-w">×${w}%</span></span></div>`;
  }).join('');
}
function renderBubble(d) {
  $('#bubble-asof').textContent = `研报基准日 ${d._meta.asOf} · 页面更新 ${d._meta.updatedAt}`;
  $('#bubble-verdict').textContent = d._meta.verdict || '';
  renderBubbleGauge(d);

  $('#bubble-dims').innerHTML = d.dimensions.map(dim => {
    const rows = d.indicators.filter(i => i.dim === dim.id);
    const chips = rows.slice(0, 4).map(i =>
      `<span class="bb-chip">${esc(i.meaning)}${i.region && i.region !== '-' ? `(${esc(i.region)})` : ''} ${bubbleTrendIcon(i.trend)}</span>`
    ).join('');
    return `<div class="bb-dim-card bb-${dim.direction}">
      <div class="bb-dim-head"><span class="bb-dim-name">${esc(dim.name)}</span><span class="bb-dim-role">${dim.direction === 'health' ? '过剩信号' : '压力信号'}</span></div>
      <div class="bb-dim-desc">${esc(dim.desc)}</div>
      <div class="bb-dim-take">${esc(DIM_TAKEAWAY[dim.id] || '')}</div>
      <div class="bb-dim-chips">${chips}</div>
    </div>`;
  }).join('');

  $('#bubble-table').innerHTML = d.dimensions.map(dim => {
    const rows = d.indicators.filter(i => i.dim === dim.id);
    const trs = rows.map(i => {
      const live = i.refreshedBy ? `<span class="bb-live" title="${esc(i.liveSource || '')}">实时跟踪</span>` : '';
      return `<div class="bb-row">
        <div class="bb-name">${esc(i.name)}<span class="bb-meaning">${esc(i.meaning)}</span></div>
        <div class="bb-region">${esc(i.region || '-')}</div>
        <div class="bb-value">${bubbleValue(i)}</div>
        <div class="bb-mom">环比 ${bubblePct(i.mom)}</div>
        <div class="bb-yoy">同比 ${bubblePct(i.yoy)}</div>
        <div class="bb-tr">${bubbleTrendIcon(i.trend)}</div>
        <div class="bb-src">${esc(i.source)}${live}</div>
      </div>`;
    }).join('');
    return `<div class="bb-group"><div class="bb-group-head">${esc(dim.name)} <span class="hint">${rows.length} 项</span></div>${trs}</div>`;
  }).join('');
}

/* ---------- 专题 ---------- */
let topicListCache = null;
async function fetchTopicList() {
  if (topicListCache && Date.now() - topicListCache.t < 300_000) return topicListCache.data;
  const r = await fetch(apiUrl('/api/topics'));
  const data = await r.json();
  topicListCache = { t: Date.now(), data };
  return data;
}
function renderTopicList(d) {
  focusRowData.topics = {
    head: '<div class="focus-head">专题</div>',
    empty: '<div class="empty">暂无专题</div>',
    rows: (d.topics || []).map(t =>
    `<div class="tp-item" data-topic="${t.id}"><span class="tp-tag">${esc(t.tag)}</span>` +
    `<div class="tp-title">${esc(t.title)}</div>` +
    `<div class="tp-meta-line"><span class="tp-date">${esc(t.date)}</span><span class="tp-summary">${esc(t.summary)}</span></div></div>`),
  };
  scheduleFocusBalance();
}
async function showTopic(id) {
  selectedId = '__topic';
  setActive('__overview');
  showView('topic');
  const r = await fetch(apiUrl(`/api/topic/${id}`));
  const d = await r.json();
  renderTopic(d);
  window.scrollTo({ top: 0, behavior: 'instant' });
}
function renderTopic(d) {
  $('#topic-tag').textContent = d.tag || '';
  $('#topic-date').textContent = d.date || '';
  $('#topic-title').textContent = d.title || '';
  $('#topic-summary').textContent = d.summary || '';

  $('#topic-narrative').innerHTML = (d.narrative || []).map(b =>
    `<div class="tn-block">${b.h ? `<h3>${esc(b.h)}</h3>` : ''}<p>${esc(b.p)}</p></div>`).join('');
  $('#topic-action').innerHTML = d.actionLink?.url
    ? `<a class="topic-action-link" href="${esc(d.actionLink.url)}" target="_blank" rel="noopener"><span>${esc(d.actionLink.label || '外部监控')}</span><span aria-hidden="true">↗</span></a>`
    : '';
  $('#topic-impact-body').innerHTML = `<div>${esc(d.impact || '')}</div>`;

  const badge = (sel, n) => $(sel).textContent = n ? `${n} 项` : '';

  // 标的（含未上市公司）
  badge('#badge-topic-tickers', (d.tickers || []).length + (d.firms || []).length);
  let tkHtml = MKT_GROUPS.map(([label, fn]) => {
    const list = (d.tickers || []).filter(t => fn(t.c));
    if (!list.length) return '';
    const rows = list.map(t => {
      const pct = t.pct == null ? '<span class="pct-flat">-</span>' : `<span class="${pctCls(t.pct)}">${fmtPct(t.pct)}</span>`;
      return `<div class="trow">${stockLink(t.c, `<span class="t-name">${esc(t.n)}</span><span class="t-code">${fmtCode(t.c)}</span>`)}` +
        `<span class="t-right"><span class="t-price">${t.price == null ? '-' : fmtPrice(t.price)}</span>${pct}</span></div>`;
    }).join('');
    return `<div class="mkt-head">${label} · ${list.length} 只</div>${rows}`;
  }).join('');
  if ((d.firms || []).length) {
    tkHtml += `<div class="mkt-head">未上市 · ${d.firms.length} 家</div>` + d.firms.map(f =>
      `<div class="trow"><span class="t-name">${esc(f.n)}</span><span class="t-code" style="text-align:right">${esc(f.note || '')}</span></div>`).join('');
  }
  $('#topic-tickers').innerHTML = tkHtml || '<div class="empty">暂无关联标的</div>';

  // 基金
  const funds = d.funds || [];
  badge('#badge-topic-funds', funds.length);
  const maxExpo = funds.length ? funds[0].expo : 1;
  $('#topic-funds').innerHTML = funds.length ? funds.map(f =>
    `<div class="frow"><div class="fr-top"><a class="fr-name q-link" href="${fundUrl(f.code)}" target="_blank" rel="noopener">${esc(f.name)}<span class="fr-code">${f.code}</span></a>` +
    `<span class="fr-expo">${f.expo.toFixed(1)}%</span></div>` +
    `<div class="expo-bar"><div style="width:${Math.min(100, f.expo / maxExpo * 100).toFixed(0)}%"></div></div>` +
    `<div class="fr-sub"><span class="chip">${esc(f.type)}</span><span>${esc(f.matched.join(' / '))}</span></div></div>`
  ).join('') : '<div class="empty">暂无关联基金</div>';

  // 业绩与 IPO
  const tl = d.timeline || { earnings: [], ipos: [] };
  badge('#badge-topic-tl', tl.earnings.length + tl.ipos.length);
  const eRow = e => {
    const [cls, label] = e.disclosed ? (BEAT_BADGE[e.beat] || ['b-inline', '已披露']) : ['b-pending', '未披露 · 预计'];
    return `<div class="tl-row">${tlDate(e.date)}<div class="tl-main"><div class="tl-head">${tlCo(e)}` +
      `<span class="tl-period">${esc(e.period)}</span><span class="badge ${cls}">${label}</span></div>` +
      `<div class="tl-text">${esc(e.text || '')}</div></div></div>`;
  };
  const pRow = p => `<div class="tl-row"><div class="tl-date">${esc(p.date)}</div><div class="tl-main">` +
    `<div class="tl-head">${tlCo(p)}<span class="tl-period">${esc(p.market)}</span><span class="badge b-status">${esc(p.status)}</span></div>` +
    `<div class="tl-text">${esc(ipoText(p))}</div></div></div>`;
  $('#topic-tl').innerHTML = [...tl.earnings.map(eRow), ...tl.ipos.map(pRow)].join('') || '<div class="empty">暂无关联业绩/IPO</div>';
  document.querySelectorAll('#topic-tl .tl-co[data-node]').forEach(el => el.addEventListener('click', () => select(el.dataset.node)));

  // 相关资讯：专题精选 newsRefs 优先，其后接自动匹配的资讯
  const refs = d.newsRefs || [];
  const autoNews = (d.news || []).filter(n => !refs.some(r => r.title === n.title));
  badge('#badge-topic-news', refs.length + autoNews.length);
  const newsRow = n => `<div class="item"><a class="i-title" href="${esc(n.url)}" target="_blank" rel="noopener">${esc(n.title)}</a>` +
    `<div class="i-meta"><span>${esc((n.publishedAt || '').slice(0, 10))}</span><span>${esc(n.source || '')}</span></div></div>`;
  $('#topic-news').innerHTML = [...refs.map(newsRow), ...autoNews.map(newsRow)].join('') || '<div class="empty">暂无相关资讯</div>';

  // 研报
  const reports = d.reports || [];
  badge('#badge-topic-reports', reports.length);
  $('#topic-reports').innerHTML = reports.length ? reports.map(r => {
    const stock = r.name ? `<span class="chip stock">${esc(r.name)}</span>` : '';
    const rating = r.rating && r.rating !== '暂无评级' ? `<span class="chip rating">${esc(r.rating)}</span>` : '';
    return `<div class="item"><a class="i-title" href="${esc(r.url)}" target="_blank" rel="noopener">${esc(r.title)}</a>` +
      `<div class="i-meta"><span>${r.date.slice(5)}</span><span>${esc(r.org)}</span>${stock}${rating}</div></div>`;
  }).join('') : '<div class="empty">暂无相关研报</div>';

}
$('#topic-back').addEventListener('click', showOverview);

/* ---------- 时间线视图 ---------- */
let tlCache = null;
const BEAT_BADGE = { beat: ['b-beat', '超预期'], miss: ['b-miss', '不及预期'], 'miss-current': ['b-miss', '目前来看不及预期'], inline: ['b-inline', '符合预期'], pending: ['b-pending', '已披露·待核验'] };
async function showTimeline() {
  selectedId = '__timeline';
  setActive('__timeline');
  showView('timeline');
  if (!tlCache || Date.now() - tlCache.t > 300_000) {
    const r = await fetch(apiUrl('/api/timeline'));
    tlCache = { t: Date.now(), data: await r.json() };
  }
  if (selectedId !== '__timeline') return;
  renderTimeline();
}
function tlDate(dstr) {
  const m = dstr.match(/^\d{4}-\d{2}-\d{2}$/);
  if (!m) return `<div class="tl-date">${esc(dstr)}</div>`;
  const d = new Date(dstr + 'T00:00:00');
  const dow = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'][d.getDay()];
  return `<div class="tl-date">${dstr.slice(5).replace('-', '/')}<span class="tl-dow">${dstr.slice(0, 4)} · ${dow}</span></div>`;
}
function tlCo(e) {
  const clickable = e.nodeId && nodeById.has(e.nodeId);
  return `<span class="tl-co${clickable ? '' : ' plain'}"${clickable ? ` data-node="${e.nodeId}"` : ''}>${esc(e.co)}</span>`;
}
function ipoText(p) { return [p.note, p.pricing].filter(Boolean).join(' · '); }
function renderTimeline() {
  const d = tlCache.data;
  $('#tl-date').textContent = (d._meta.updatedAt || '') + '';
  const today = new Date().toISOString().slice(0, 10);
  const rows = e => {
    const [cls, label] = e.disclosed ? (BEAT_BADGE[e.beat] || ['b-inline', '已披露']) : ['b-pending', '未披露 · 预计'];
    const pct = e.pct == null ? '' : `<span class="${pctCls(e.pct)}" style="font-size:11.5px">今日 ${fmtPct(e.pct)}</span>`;
    return `<div class="tl-row">${tlDate(e.date)}<div class="tl-main">` +
      `<div class="tl-head">${tlCo(e)}<span class="tl-period">${esc(e.period)}</span><span class="badge ${cls}">${label}</span>${pct}</div>` +
      `<div class="tl-text">${esc(e.text || '')}</div></div></div>`;
  };
  const upcoming = (d.earnings || []).filter(e => !e.disclosed).sort((a, b) => a.date.localeCompare(b.date));
  const past = (d.earnings || []).filter(e => e.disclosed).sort((a, b) => b.date.localeCompare(a.date));
  $('#tl-earnings').innerHTML =
    `<div class="tl-group">即将披露 · ${upcoming.length}</div>` + upcoming.map(rows).join('') +
    `<div class="tl-today"><span>今日 ${today}</span></div>` +
    `<div class="tl-group">近期已披露 · ${past.length}</div>` + past.map(rows).join('');
  $('#tl-ipos').innerHTML = (d.ipos || []).map(p =>
    `<div class="tl-row"><div class="tl-date">${esc(p.date)}</div><div class="tl-main">` +
    `<div class="tl-head">${tlCo(p)}<span class="tl-period">${esc(p.market)}</span><span class="badge b-status">${esc(p.status)}</span></div>` +
    `<div class="tl-text">${esc(ipoText(p))}</div></div></div>`
  ).join('');
  $('#tl-events').innerHTML = (d.events || []).length ? d.events.map(evDate2).join('') : '<div class="empty">暂无重大事件</div>';
  document.querySelectorAll('#view-timeline .tl-co[data-node]').forEach(el =>
    el.addEventListener('click', () => select(el.dataset.node)));
  renderCalendar();
}

/* ---------- 行业数据 ---------- */
let industryCache = null;
let industryScope = '全部';
let industryEvidence = '全部';
async function showIndustry() {
  selectedId = '__industry';
  setActive('__industry');
  showView('industry');
  if (!industryCache || Date.now() - industryCache.t > 300_000) {
    const r = await fetch(apiUrl('/api/industry-data'));
    industryCache = { t: Date.now(), data: await r.json() };
  }
  if (selectedId !== '__industry') return;
  renderIndustry();
}
function industryFilterGroup(el, values, selected, onSelect) {
  el.innerHTML = values.map(v => `<button class="${v === selected ? 'active' : ''}" data-value="${esc(v)}">${esc(v)}</button>`).join('');
  el.querySelectorAll('button').forEach(btn => btn.addEventListener('click', () => onSelect(btn.dataset.value)));
}
function renderIndustry() {
  const data = industryCache.data || {};
  const items = data.items || [];
  $('#industry-date').textContent = data._meta?.updatedAt || '-';
  const scopes = ['全部', ...new Set(items.map(i => i.scope))];
  const evidence = ['全部', '硬数据', '机构估算', '代理指标'];
  industryFilterGroup($('#industry-scope-filters'), scopes, industryScope, value => {
    industryScope = value; renderIndustry();
  });
  industryFilterGroup($('#industry-evidence-filters'), evidence, industryEvidence, value => {
    industryEvidence = value; renderIndustry();
  });
  const query = ($('#industry-search').value || '').trim().toLowerCase();
  const visible = items.filter(i =>
    (industryScope === '全部' || i.scope === industryScope) &&
    (industryEvidence === '全部' || i.evidence === industryEvidence) &&
    (!query || [i.stage, i.metric, i.value, i.change, i.source, i.scope].join(' ').toLowerCase().includes(query))
  ).sort((a, b) => (a.stageOrder - b.stageOrder) || a.metric.localeCompare(b.metric, 'zh-CN'));
  let lastStage = '';
  $('#industry-rows').innerHTML = visible.map(i => {
    const stage = i.stage === lastStage ? '' : i.stage;
    lastStage = i.stage;
    const evidenceCls = i.evidence === '硬数据' ? 'hard' : i.evidence === '机构估算' ? 'estimate' : 'proxy';
    return `<tr class="industry-row" data-id="${esc(i.id)}" tabindex="0" aria-expanded="false">` +
      `<td data-label="产业链位置"><span class="industry-stage">${esc(stage)}</span></td>` +
      `<td data-label="核心指标"><span class="industry-metric">${esc(i.metric)}</span><span class="industry-expand">查看口径</span></td>` +
      `<td data-label="最新数据"><strong>${esc(i.value)}</strong></td><td data-label="变化"><span class="industry-change">${esc(i.change)}${industryExpectation(i.expectation)}</span></td>` +
      `<td data-label="最新周期">${esc(i.period)}</td><td data-label="频率">${esc(i.frequency)}</td>` +
      `<td data-label="归属"><span class="industry-scope">${esc(i.scope)}</span></td>` +
      `<td data-label="数据性质"><span class="industry-evidence ${evidenceCls}">${esc(i.evidence)}</span></td></tr>` +
      `<tr class="industry-detail" data-detail="${esc(i.id)}"><td colspan="8"><div>` +
      `<span>${esc(i.note)}</span><a href="${esc(i.sourceUrl)}" target="_blank" rel="noopener">来源：${esc(i.source)} ↗</a>` +
      `</div></td></tr>`;
  }).join('') || '<tr><td colspan="8"><div class="empty">没有符合条件的数据</div></td></tr>';
  const toggle = row => {
    const detail = document.querySelector(`[data-detail="${row.dataset.id}"]`);
    const open = row.getAttribute('aria-expanded') !== 'true';
    row.setAttribute('aria-expanded', open ? 'true' : 'false');
    detail?.classList.toggle('open', open);
  };
  document.querySelectorAll('.industry-row').forEach(row => {
    row.addEventListener('click', () => toggle(row));
    row.addEventListener('keydown', e => {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggle(row); }
    });
  });
  $('#industry-method').textContent = [data._meta?.note, data._meta?.methodology].filter(Boolean).join(' ');
}
function industryExpectation(value) {
  const cls = value === '超预期' ? 'beat' : value === '不及预期' ? 'miss' : 'inline';
  return `<span class="industry-expectation ${cls}">${esc(value || '符合预期')}</span>`;
}
$('#industry-search').addEventListener('input', () => {
  if (selectedId === '__industry' && industryCache) renderIndustry();
});

/* ---------- 投资日历 ---------- */
let calYear = null, calMonthIdx = null;
function calBuildIndex(d) {
  const iso = /^\d{4}-\d{2}-\d{2}$/;
  const map = new Map();
  const add = (date, kind, label, nodeId) => {
    if (!iso.test(date)) return;
    if (!map.has(date)) map.set(date, []);
    map.get(date).push({ kind, label, nodeId });
  };
  (d.earnings || []).forEach(e => add(e.date, 'earn', e.co, e.nodeId));
  (d.ipos || []).forEach(p => add(p.date, 'ipo', p.co, p.nodeId));
  (d.events || []).forEach(e => add(e.date, 'event', e.title, e.nodeId));
  return map;
}
function renderCalendar() {
  const d = tlCache && tlCache.data;
  if (!d) return;
  const now = new Date();
  if (calYear == null) { calYear = now.getFullYear(); calMonthIdx = now.getMonth(); }
  const idx = calBuildIndex(d);
  const startDow = new Date(calYear, calMonthIdx, 1).getDay();
  const daysInMonth = new Date(calYear, calMonthIdx + 1, 0).getDate();
  const daysInPrevMonth = new Date(calYear, calMonthIdx, 0).getDate();
  const todayStr = now.toISOString().slice(0, 10);

  $('#cal-month-label').textContent = `${calYear} 年 ${calMonthIdx + 1} 月`;

  const totalCells = Math.ceil((startDow + daysInMonth) / 7) * 7;
  const dows = ['日', '一', '二', '三', '四', '五', '六'];
  let html = dows.map(x => `<div class="cal-dow">${x}</div>`).join('');
  for (let i = 0; i < totalCells; i++) {
    const offset = i - startDow + 1;
    if (offset < 1) { html += `<div class="cal-cell cal-out"><div class="cal-daynum">${daysInPrevMonth + offset}</div></div>`; continue; }
    if (offset > daysInMonth) { html += `<div class="cal-cell cal-out"><div class="cal-daynum">${offset - daysInMonth}</div></div>`; continue; }
    const mm = String(calMonthIdx + 1).padStart(2, '0'), dd = String(offset).padStart(2, '0');
    const dateStr = `${calYear}-${mm}-${dd}`;
    const items = idx.get(dateStr) || [];
    const shown = items.slice(0, 3), rest = items.length - shown.length;
    html += `<div class="cal-cell${dateStr === todayStr ? ' cal-today' : ''}"><div class="cal-daynum">${offset}</div>` +
      shown.map(it => {
        const clickable = it.nodeId && nodeById.has(it.nodeId);
        return `<div class="cal-item cal-${it.kind}${clickable ? ' cal-clickable' : ''}"${clickable ? ` data-node="${it.nodeId}"` : ''} title="${esc(it.label)}">${esc(it.label)}</div>`;
      }).join('') + (rest > 0 ? `<div class="cal-more">+${rest}</div>` : '') + `</div>`;
  }
  $('#cal-grid').innerHTML = html;
  document.querySelectorAll('#cal-grid .cal-clickable').forEach(el => el.addEventListener('click', () => select(el.dataset.node)));
}
$('#cal-prev').addEventListener('click', () => { calMonthIdx--; if (calMonthIdx < 0) { calMonthIdx = 11; calYear--; } renderCalendar(); });
$('#cal-next').addEventListener('click', () => { calMonthIdx++; if (calMonthIdx > 11) { calMonthIdx = 0; calYear++; } renderCalendar(); });
$('#cal-today').addEventListener('click', () => { calYear = null; renderCalendar(); });
function evDate2(e) {
  const iso = /^\d{4}-\d{2}-\d{2}$/;
  const dateHtml = iso.test(e.date)
    ? (() => {
      const d = new Date(e.date + 'T00:00:00');
      const dow = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'][d.getDay()];
      const range = e.dateEnd ? `–${e.dateEnd.slice(5).replace('-', '/')}` : '';
      return `<div class="tl-date">${e.date.slice(5).replace('-', '/')}${range}<span class="tl-dow">${e.date.slice(0, 4)} · ${dow}</span></div>`;
    })()
    : `<div class="tl-date">${esc(e.date)}</div>`;
  const clickable = e.nodeId && nodeById.has(e.nodeId);
  const titleHtml = `<span class="tl-co${clickable ? '' : ' plain'}"${clickable ? ` data-node="${e.nodeId}"` : ''}>${esc(e.title)}</span>`;
  return `<div class="tl-row">${dateHtml}<div class="tl-main">` +
    `<div class="tl-head">${titleHtml}<span class="ev-cat">${esc(e.category)}</span></div>` +
    `<div class="tl-text">${esc(e.note || '')}</div></div></div>`;
}

/* ---------- 信息流视图 ---------- */
let feedCache = null, feedCat = 'all';
const CAT_NAMES = { market: '市场', 'ai-models': '模型发布', 'ai-products': '产品发布', model: '模型发布', product: '产品发布', industry: '行业动态', paper: '论文研究', tip: '观点技巧', funding: '融资并购', policy: '政策监管', open: '开源', hardware: '硬件/产业' };
const CAT_ORDER = ['market', 'hardware', 'industry', 'ai-products', 'ai-models', 'tip', 'paper'];
async function showFeed() {
  selectedId = '__feed';
  setActive('__feed');
  showView('feed');
  if (!feedCache || Date.now() - feedCache.t > 300_000) {
    const r = await fetch(apiUrl('/api/feed'));
    feedCache = { t: Date.now(), data: await r.json() };
  }
  if (selectedId !== '__feed') return;
  renderFeed();
}
function renderFeed() {
  const d = feedCache.data;
  $('#feed-meta').textContent = `近 7 天 ${d.count} 条 · 来源 AI HOT + 同花顺快讯 · 标签=关联产业链环节`;
  const presentCats = new Set(d.items.map(i => i.category).filter(Boolean));
  const cats = [...CAT_ORDER.filter(c => presentCats.has(c)), ...[...presentCats].filter(c => !CAT_ORDER.includes(c))];
  $('#feed-cats').innerHTML = ['all', ...cats].map(c =>
    `<span class="fcat${feedCat === c ? ' active' : ''}" data-cat="${c}">${c === 'all' ? '全部' : (CAT_NAMES[c] || c)}</span>`).join('');
  document.querySelectorAll('.fcat').forEach(el => el.addEventListener('click', () => { feedCat = el.dataset.cat; renderFeed(); }));
  const items = d.items.filter(i => feedCat === 'all' || i.category === feedCat);
  $('#feed-list').innerHTML = items.map(n => {
    const t = n.publishedAt ? new Date(n.publishedAt).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false }) : '';
    const tags = (n.tags || []).map(tg => `<span class="ftag" data-node="${tg.id}">${esc(tg.n)}</span>`).join('');
    return `<div class="fitem"><a class="f-title" href="${esc(n.url)}" target="_blank" rel="noopener">${esc(n.title)}</a>` +
      (n.summary ? `<div class="f-sum">${esc(n.summary)}</div>` : '') +
      `<div class="f-meta"><span>${t}</span><span>${esc(n.source || '')}</span>` +
      (n.category ? `<span class="fcat-chip">${CAT_NAMES[n.category] || esc(n.category)}</span>` : '') + tags + `</div></div>`;
  }).join('') || '<div class="empty">该分类暂无条目</div>';
  document.querySelectorAll('.ftag').forEach(el => el.addEventListener('click', () => select(el.dataset.node)));
}

/* ---------- 总览视图 ---------- */
async function showOverview() {
  selectedId = '__overview';
  setActive('__overview');
  showView('overview');
  renderChainMap();
  renderGartner();
  renderSystemMap();
  renderRotationLoading();
  fetchRotation().then(d => { if (selectedId === '__overview') renderRotation(d); }).catch(() => { if (selectedId === '__overview') $('#rotation-chart').innerHTML = '<div class="empty">产业链轮动暂时无法取得行情数据</div>'; });
  fetchTopicList().then(td => { if (selectedId === '__overview') renderTopicList(td); });
  const d = await fetchHeatmap();
  if (selectedId !== '__overview') return;
  renderIndices(d.indices || []);
  renderFocus(d.focus || {});
  renderHeatmap(d.segments || []);
  const md = await fetchMapping();
  if (selectedId !== '__overview') return;
  renderMapping(md);
}
async function fetchRotation() {
  if (rotationCache && Date.now() - rotationCache.t < 900_000) return rotationCache.data;
  const r = await fetch(apiUrl('/api/rotation'));
  if (!r.ok) throw new Error(`rotation ${r.status}`);
  const data = await r.json();
  rotationCache = { t: Date.now(), data };
  return data;
}
function renderRotationLoading() {
  const el = $('#rotation-chart');
  if (el) el.innerHTML = '<div class="rotation-loading">正在加载产业链轮动…</div>';
}
function renderRotation(d) {
  const el = $('#rotation-chart');
  if (!el || !(d.labels || []).length || !(d.series || []).length) return;
  const labels = d.labels, series = d.series;
  const W = 1060;
  const box = el.getBoundingClientRect();
  const H = Math.max(360, box.width ? W * Math.max(box.height, 1) / box.width : 640);
  const left = 42, right = 30, top = 92, bottom = 38;
  const plotW = W - left - right, plotH = H - top - bottom;
  const all = series.flatMap(s => s.values).filter(Number.isFinite);
  const min = Math.min(...all), max = Math.max(...all), span = Math.max(1, max - min), yMin = Math.max(0, min - span * .08), yMax = max + span * .08;
  const x = i => left + (labels.length <= 1 ? 0 : i / (labels.length - 1)) * plotW;
  const y = v => top + (yMax - v) / (yMax - yMin) * plotH;
  const colors = ['#2563eb', '#1e3a8a', '#68758a', '#64748b', '#e5a5b3', '#a23a32', '#eab308', '#79b98c', '#6941a5'];
  const escText = value => esc(String(value));
  let out = `<svg class="rotation-svg" viewBox="0 0 ${W} ${H.toFixed(2)}" preserveAspectRatio="xMidYMid meet" role="img" aria-label="AI产业链轮动月线走势">`;
  out += `<text class="rotation-axis-label" x="${left}" y="18">归一化走势（${escText(d.start)} = 100）</text>`;
  const legendCols = 3, legendW = (W - left - right) / legendCols;
  series.forEach((s, i) => {
    const col = i % legendCols, row = Math.floor(i / legendCols), lx = left + col * legendW, ly = 42 + row * 18;
    out += `<line class="rotation-legend-line" x1="${lx}" y1="${ly - 4}" x2="${lx + 24}" y2="${ly - 4}" style="stroke:${colors[i % colors.length]}"/>`;
    out += `<text class="rotation-legend-text" data-series="${i}" x="${lx + 30}" y="${ly}">${escText(s.name)}（${escText(s.industry)}）</text>`;
  });
  for (let i = 0; i <= 4; i++) {
    const value = yMax - ((yMax - yMin) * i / 4), yy = y(value);
    out += `<line class="rotation-grid" x1="${left}" y1="${yy.toFixed(1)}" x2="${W - right}" y2="${yy.toFixed(1)}"/>`;
    out += `<text class="rotation-y-label" x="${left - 8}" y="${yy + 3}" text-anchor="end">${Math.round(value)}</text>`;
  }
  const labelStep = Math.max(1, Math.ceil(labels.length / 7));
  labels.forEach((label, i) => {
    if (i !== 0 && i !== labels.length - 1 && i % labelStep) return;
    const xx = x(i);
    out += `<line class="rotation-grid rotation-grid-v" x1="${xx.toFixed(1)}" y1="${top}" x2="${xx.toFixed(1)}" y2="${H - bottom}"/>`;
    out += `<text class="rotation-x-label" x="${xx.toFixed(1)}" y="${H - 13}" text-anchor="middle">${escText(label.slice(2))}</text>`;
  });
  out += `<line class="rotation-axis" x1="${left}" y1="${H - bottom}" x2="${W - right}" y2="${H - bottom}"/>`;
  series.forEach((s, i) => {
    const path = s.values.map((value, index) => `${index ? 'L' : 'M'} ${x(index).toFixed(1)} ${y(value).toFixed(1)}`).join(' ');
    out += `<path class="rotation-line" data-series="${i}" d="${path}" style="stroke:${colors[i % colors.length]}"/>`;
  });
  out += `<line class="rotation-crosshair" x1="${left}" y1="${top}" x2="${left}" y2="${H - bottom}"/>`;
  out += `<g class="rotation-hover" aria-hidden="true"><line class="rotation-hover-line" x1="${left}" y1="${top}" x2="${left}" y2="${H - bottom}"/><rect class="rotation-tooltip-box" x="${left + 8}" y="${top + 8}" width="232" height="${series.length * 16 + 26}" rx="5"/><text class="rotation-tooltip-date" x="${left + 18}" y="${top + 26}"></text>${series.map((s, i) => `<text class="rotation-tooltip-row" data-row="${i}" x="${left + 18}" y="${top + 44 + i * 16}" style="fill:${colors[i % colors.length]}"></text>`).join('')}</g>`;
  out += `<rect class="rotation-hit" x="${left}" y="${top}" width="${plotW}" height="${plotH}"/>`;
  out += '</svg>';
  el.innerHTML = out;
  const svg = el.querySelector('svg'), hit = svg.querySelector('.rotation-hit'), hover = svg.querySelector('.rotation-hover');
  const setHover = index => {
    const xx = x(index);
    hover.querySelector('.rotation-hover-line').setAttribute('x1', xx); hover.querySelector('.rotation-hover-line').setAttribute('x2', xx);
    hover.querySelector('.rotation-tooltip-date').textContent = labels[index];
    hover.querySelectorAll('.rotation-tooltip-row').forEach((row, i) => { row.textContent = `${series[i].name}  ${series[i].values[index].toFixed(1)}`; });
    hover.style.display = '';
  };
  const setSelection = (index, seriesIndex) => {
    svg.querySelectorAll('.rotation-line.is-selected, .rotation-legend-text.is-selected').forEach(node => node.classList.remove('is-selected'));
    svg.querySelector(`.rotation-line[data-series="${seriesIndex}"]`)?.classList.add('is-selected');
    svg.querySelector(`.rotation-legend-text[data-series="${seriesIndex}"]`)?.classList.add('is-selected');
  };
  const nearestSeries = (event, index) => {
    const rect = svg.getBoundingClientRect();
    const localY = (event.clientY - rect.top) / rect.height * H;
    return series.reduce((best, s, i) => {
      const distance = Math.abs(y(s.values[index]) - localY);
      return distance < best.distance ? { index: i, distance } : best;
    }, { index: 0, distance: Infinity }).index;
  };
  hit.addEventListener('pointermove', event => {
    const rect = svg.getBoundingClientRect(), localX = (event.clientX - rect.left) / rect.width * W;
    setHover(Math.max(0, Math.min(labels.length - 1, Math.round((localX - left) / plotW * (labels.length - 1)))));
  });
  hit.addEventListener('click', event => {
    const rect = svg.getBoundingClientRect(), localX = (event.clientX - rect.left) / rect.width * W;
    const index = Math.max(0, Math.min(labels.length - 1, Math.round((localX - left) / plotW * (labels.length - 1))));
    setSelection(index, nearestSeries(event, index));
  });
  hit.addEventListener('pointerleave', () => { hover.style.display = 'none'; });
  setHover(labels.length - 1);
  hover.style.display = 'none';
}
async function fetchHeatmap() {
  if (heatmapCache && Date.now() - heatmapCache.t < 60_000) return heatmapCache.data;
  const r = await fetch(apiUrl('/api/heatmap'));
  const data = await r.json();
  heatmapCache = { t: Date.now(), data };
  return data;
}
function renderIndices(list) {
  $('#idx-row').innerHTML = list.map(q =>
    `<div class="idx"><div class="n">${q.n}</div><div class="p">${q.price == null ? '-' : fmtPrice(q.price)}</div>` +
    `<div class="c ${pctCls(q.pct)}">${q.pct == null ? '-' : fmtPct(q.pct)}</div></div>`
  ).join('');
}
let mapCache = null;
async function fetchMapping() {
  if (mapCache && Date.now() - mapCache.t < 60_000) return mapCache.data;
  const r = await fetch(apiUrl('/api/mapping'));
  const data = await r.json();
  mapCache = { t: Date.now(), data };
  return data;
}
function renderMapping(d) {
  const maps = [...(d.maps || [])].sort((a, b) => Math.abs(b.score ?? 0) - Math.abs(a.score ?? 0));
  $('#map-list').innerHTML = maps.map(m => {
    const sig = m.score == null ? '<span class="sig-badge pct-flat">信号 -</span>'
      : `<span class="sig-badge ${pctCls(m.score)}">信号 ${fmtPct(m.score)}</span>`;
    const chips = m.signal.map(s =>
      stockLink(s.c, `<span><b>${esc(s.n)}</b> <span class="${pctCls(s.pct)}">${s.pct == null ? '-' : fmtPct(s.pct)}</span></span>`)
    ).join('');
    const tgts = m.targets.map(t =>
      `<span class="tgt-chip" data-node="${t.id}"><span>${esc(t.name)}</span>` +
      `<span class="${pctCls(t.avg)}">${t.avg == null ? '' : fmtPct(t.avg)}</span></span>`
    ).join('');
    const repSeen = new Set();
    const reps = m.targets.flatMap(t => t.reps.slice(0, 1))
      .filter(r => { if (repSeen.has(r.n)) return false; repSeen.add(r.n); return true; }).slice(0, 3)
      .map(r => stockLink(r.c, `${esc(r.n)} <span class="${pctCls(r.pct)}">${fmtPct(r.pct)}</span>`)).join(' · ');
    const funds = (m.funds || []).map(f =>
      `<a class="q-link" href="${fundUrl(f.code)}" target="_blank" rel="noopener" title="天天基金详情"><b>${esc(f.name)}</b> <span class="pct-flat">${f.expo.toFixed(1)}%</span></a>`
    ).join(' · ');
    return `<div class="map-row">` +
      `<div><div class="map-title">${esc(m.title)}${sig}</div><div class="map-chips">${chips}</div>` +
      `<div class="map-logic">${esc(m.logic)}</div></div>` +
      `<div class="map-arrow">→</div>` +
      `<div><div class="tgt-chips">${tgts}</div>${reps ? `<div class="tgt-reps">代表：${reps}</div>` : ''}` +
      `${funds ? `<div class="tgt-reps">基金：${funds}</div>` : ''}</div>` +
      `</div>`;
  }).join('') || '<div class="empty">暂无映射配置</div>';
  document.querySelectorAll('#map-list .tgt-chip').forEach(el =>
    el.addEventListener('click', () => select(el.dataset.node)));
}

/* 今日焦点三列：渲染全量候选行，再按最短列高度裁掉各列尾部，保证三列底边对齐。 */
let lastFocusData = null;
let focusBalanceRaf = 0;
let focusRowData = { topics: null, news: null, events: null };
function scheduleFocusBalance() {
  if (focusBalanceRaf) cancelAnimationFrame(focusBalanceRaf);
  focusBalanceRaf = requestAnimationFrame(() => { focusBalanceRaf = 0; balanceFocusGrid(); });
}
function focusColumnEl(kind) {
  return document.getElementById(kind === 'topics' ? 'focus-topics' : kind === 'news' ? 'focus-news' : 'focus-events');
}
function focusRowSelector(kind) {
  return kind === 'topics' ? '.tp-item' : kind === 'news' ? '.fn-item' : '.fe-row';
}
function renderFocusColumn(kind) {
  const data = focusRowData[kind];
  const el = focusColumnEl(kind);
  if (!el || !data) return [];
  el.innerHTML = data.head + (data.rows.length ? data.rows.join('') : data.empty);
  return [...el.children].filter(x => x.matches(focusRowSelector(kind)));
}
function balanceFocusGrid() {
  const grid = document.querySelector('.focus-grid-3');
  if (!grid || !lastFocusData) return;
  const kinds = ['topics', 'news', 'events'];
  if (kinds.some(k => !focusRowData[k])) return; // 专题列表异步到达后再统一配平
  const narrow = window.matchMedia('(max-width: 900px)').matches;
  if (narrow) {
    kinds.forEach(renderFocusColumn); // 单列视图展示全部内容
    return;
  }
  // 先全量渲染并实测每行高度（列宽固定，行高不随行数变化），
  // 目标高度取三列中最短者，再让每列保留不超过目标的最多行数。
  const full = kinds.map(k => ({ kind: k, heights: renderFocusColumn(k).map(el => el.getBoundingClientRect().height) }));
  if (full.some(c => !c.heights.length)) return; // 某列暂无内容时不配平，避免把其他列清空
  const totals = full.map(c => c.heights.reduce((a, b) => a + b, 0));
  const target = Math.min(...totals);
  let trimmed = false;
  kinds.forEach((k, i) => {
    const data = focusRowData[k];
    let acc = 0;
    let keep = data.rows.length;
    let bestDiff = Math.abs(target - acc);
    for (let j = 0; j < data.rows.length; j++) {
      acc += full[i].heights[j];
      const diff = Math.abs(target - acc);
      if (diff < bestDiff) { bestDiff = diff; keep = j + 1; }
    }
    data.keep = Math.min(keep, data.rows.length);
    if (keep < data.rows.length) trimmed = true;
  });
  if (!trimmed) return; // 三列本来就齐
  kinds.forEach(k => {
    const data = focusRowData[k];
    const el = focusColumnEl(k);
    el.innerHTML = data.head + (data.keep ? data.rows.slice(0, data.keep).join('') : data.empty);
  });
}
let focusResizeTimer = 0;
window.addEventListener('resize', () => {
  clearTimeout(focusResizeTimer);
  focusResizeTimer = setTimeout(() => { if (lastFocusData) balanceFocusGrid(); }, 180);
});

function renderFocus(f) {
  lastFocusData = f;
  const news = (f.newsAll && f.newsAll.length ? f.newsAll : f.news) || [];
  const focusTime = value => {
    if (!value || Number.isNaN(new Date(value).getTime())) return '';
    const parts = date => Object.fromEntries(new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).formatToParts(date).filter(x => x.type !== 'literal').map(x => [x.type, x.value]));
    const t = parts(new Date(value)), today = parts(new Date()), day = `${t.year}-${t.month}-${t.day}`, nowDay = `${today.year}-${today.month}-${today.day}`;
    const yesterday = new Date(Date.now() - 86400_000), y = parts(yesterday), yesterdayDay = `${y.year}-${y.month}-${y.day}`;
    const prefix = day === nowDay ? '今天' : day === yesterdayDay ? '昨天' : `${t.month}/${t.day}`;
    return `${prefix} ${t.hour}:${t.minute}`;
  };
  focusRowData.news = {
    head: '<div class="focus-head">今日要闻</div>',
    empty: '<div class="empty">近 24 小时暂无精选要闻</div>',
    rows: news.map(n => {
    const t = focusTime(n.publishedAt);
    return `<div class="fn-item"><a class="fn-title" href="${esc(n.url)}" target="_blank" rel="noopener">${esc(n.title)}</a>` +
      `<div class="fn-meta"><span>${t}</span><span>${esc(n.source || '')}</span></div></div>`;
    }),
  };

  const evRow = (e, dateStr, badgeHtml, note, extraCls = '') =>
    `<div class="fe-row${extraCls ? ` ${extraCls}` : ''}"><span class="fe-date">${esc(dateStr)}</span>` +
    `<span class="fe-co"${e.nodeId ? ` data-node="${e.nodeId}"` : ''}>${esc(e.co)}</span>` +
    badgeHtml + (note ? `<span class="fe-note">${esc(note)}</span>` : '') + `</div>`;
  // 事件栏候选：宏观数据最重要全部保留，其后重大事件、待披露、IPO；
  // 已披露业绩放最后，三列配平时先从这里压缩。
  const earningsAll = (f.earningsAll && f.earningsAll.length) ? f.earningsAll : [...(f.upcoming || []), ...(f.disclosed || [])];
  const evItems = [];
  (f.macroReleases || []).forEach(m => {
    const result = m.surprise || '已发布';
    const resultCls = result === '超预期' ? 'b-beat' : /不及预期|低于预期/.test(result) ? 'b-miss' : 'b-inline';
    evItems.push(evRow(
      { nodeId: null, co: m.title },
      m.date.slice(5).replace('-', '/'),
      `<span class="ev-cat">宏观数据</span><span class="badge ${resultCls}">${esc(result)}</span>`,
      `实际：${esc(m.actual || '-')} · 预期：${esc(m.expected || '无一致预期')}`,
      'fe-macro',
    ));
  });
  (f.events || []).forEach(e => {
    const dateStr = /^\d{4}-\d{2}-\d{2}$/.test(e.date) ? e.date.slice(5).replace('-', '/') : e.date;
    evItems.push(evRow({ ...e, co: e.title || e.co }, dateStr, `<span class="ev-cat">${esc(e.category)}</span>`, e.note || ''));
  });
  earningsAll.filter(e => !e.disclosed).forEach(e => {
    evItems.push(evRow(e, e.date.slice(5).replace('-', '/'), '<span class="badge b-pending">待披露</span>', e.period));
  });
  (f.ipos || []).forEach(p => {
    evItems.push(evRow(p, p.date.replace('（预计）', ''), `<span class="badge b-status">${esc(p.status)}</span>`, [p.market, p.pricing].filter(Boolean).join(' · ')));
  });
  earningsAll.filter(e => e.disclosed).forEach(e => {
    const [cls, label] = BEAT_BADGE[e.beat] || ['b-inline', '已披露'];
    evItems.push(evRow(e, e.date.slice(5).replace('-', '/'), `<span class="badge ${cls}">${label}</span>`, e.period));
  });
  focusRowData.events = {
    head: '<div class="focus-head">业绩、IPO、数据与重大事件</div>',
    empty: '<div class="empty">近期暂无事件</div>',
    rows: evItems,
  };
  scheduleFocusBalance();
}

function heatColor(pct) {
  if (pct == null || Math.abs(pct) < 0.005) return { bg: 'var(--chip-bg)', fg: 'var(--txt3)' };
  const a = 0.16 + Math.min(Math.abs(pct) / 6, 1) * 0.78;
  const rgb = pct > 0 ? '211,63,54' : '26,151,102';
  return { bg: `rgba(${rgb},${a.toFixed(2)})`, fg: a > 0.55 ? '#fff' : 'var(--txt)' };
}
function renderHeatmap(segments) {
  $('#hm-wrap').innerHTML = segments.map(s => {
    const valid = s.tickers.filter(t => t.pct != null);
    const avg = valid.length ? valid.reduce((x, t) => x + t.pct, 0) / valid.length : null;
    const ranked = [...s.tickers].sort((a, b) => Math.abs(b.pct ?? 0) - Math.abs(a.pct ?? 0));
    const top = [...ranked.filter(t => t.featured), ...ranked.filter(t => !t.featured)].slice(0, 9);
    const tiles = top.map(t => {
      const hc = heatColor(t.pct);
      return stockLink(t.c, `<div class="hm-tile" style="background:${hc.bg};color:${hc.fg}" title="${esc(t.n)} ${t.price ?? '-'} · 点击看K线">` +
        `<div class="n">${esc(t.n)}</div><div class="v">${t.pct == null ? '-' : fmtPct(t.pct)}</div></div>`);
    }).join('');
    return `<div class="hm-seg"><div class="hm-seg-head" data-id="${s.id}">` +
      `<span>${esc(s.name)} <span class="l1tag">${esc(s.l1.slice(0, 2))}</span></span>` +
      `<span class="${pctCls(avg)}">${avg == null ? '' : fmtPct(avg)}</span></div>` +
      `<div class="hm-tiles">${tiles}</div></div>`;
  }).join('');
  document.querySelectorAll('.hm-seg-head').forEach(el => el.addEventListener('click', () => select(el.dataset.id)));
}

/* ---------- 产业链图谱 ---------- */
function renderChainMap() {
  const svg = $('#chain-svg');
  if (!svg || !(CHAIN.cols || []).length) return;
  const COL_GAP2 = 30, ROW_H2 = 36, BOX_H2 = 26, TOP = 34, PAD2 = 10;
  const colW2 = CHAIN.cols.map(c => Math.max(...c.nodes.map(n => measure(n.n) - 8), 64));
  const colX2 = [PAD2];
  for (let i = 1; i < colW2.length; i++) colX2[i] = colX2[i - 1] + colW2[i - 1] + COL_GAP2;
  const pos = new Map();
  let maxRows = 0;
  CHAIN.cols.forEach((c, ci) => {
    maxRows = Math.max(maxRows, c.nodes.length);
    c.nodes.forEach((n, ri) => pos.set(n.id, { x: colX2[ci], y: TOP + ri * ROW_H2, w: colW2[ci], n: n.n }));
  });
  const W = colX2[colX2.length - 1] + colW2[colW2.length - 1] + PAD2;
  const H = TOP + maxRows * ROW_H2 + 4;
  let out = '';
  CHAIN.cols.forEach((c, ci) => {
    out += `<text class="cm-col-title" x="${colX2[ci] + colW2[ci] / 2}" y="18" text-anchor="middle">${esc(c.title)}</text>`;
  });
  (CHAIN.edges || []).forEach(([a, b]) => {
    const p = pos.get(a), q = pos.get(b);
    if (!p || !q) return;
    const x1 = p.x + p.w, y1 = p.y + BOX_H2 / 2, x2 = q.x, y2 = q.y + BOX_H2 / 2;
    const mx = (x1 + x2) / 2;
    out += `<path class="cm-edge" d="M ${x1} ${y1} C ${mx} ${y1} ${mx} ${y2} ${x2} ${y2}"/>`;
  });
  pos.forEach((p, id) => {
    out += `<g class="tnode" data-id="${id}"><rect x="${p.x}" y="${p.y}" width="${p.w}" height="${BOX_H2}" rx="6"/>` +
      `<text x="${p.x + p.w / 2}" y="${p.y + BOX_H2 / 2 + 4}" text-anchor="middle">${esc(p.n)}</text></g>`;
  });
  svg.setAttribute('width', W);
  svg.setAttribute('height', H);
  svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
  svg.innerHTML = out;
  svg.querySelectorAll('.tnode').forEach(g => g.addEventListener('click', () => select(g.dataset.id)));
}

/* ---------- AI 产业链系统（可下钻矢量图） ---------- */
async function renderSystemMap() {
  const el = $('#system-diagram');
  if (!el) return;
  try {
    const r = await fetch(apiUrl('/scenes/ai-system.svg?inline=1'));
    if (!r.ok) throw new Error(`system map ${r.status}`);
    const markup = await r.text();
    if (selectedId !== '__overview') return;
    el.innerHTML = markup;
    el.querySelectorAll('[data-node]').forEach(node => {
      node.classList.add('system-clickable');
      node.addEventListener('click', event => {
        event.stopPropagation();
        select(node.dataset.node);
      });
    });
  } catch {
    el.innerHTML = '<div class="empty">产业链系统图暂时无法加载</div>';
  }
}

/* ---------- Gartner 曲线 ---------- */
function renderGartner(layoutHeight = null) {
  const svg = $('#gartner-svg');
  if (!svg) return;
  const W = 1060;
  if (svg.__gartnerObserver) svg.__gartnerObserver.disconnect();
  const current = svg.getBoundingClientRect();
  const H = Math.max(340, Number(layoutHeight) || (current.width && current.height ? W * current.height / current.width : 340));
  const top = 20, plotBottom = H - 45;
  const y = value => top + ((value - 20) / (295 - 20)) * (plotBottom - top);
  const curve = `M 50 ${y(272)} C 150 ${y(268)} 200 ${y(62)} 288 ${y(62)} C 348 ${y(62)} 352 ${y(158)} 428 ${y(210)} C 462 ${y(232)} 484 ${y(237)} 516 ${y(232)} C 665 ${y(210)} 800 ${y(158)} 1015 ${y(130)}`;
  svg.setAttribute('width', W); svg.setAttribute('height', H.toFixed(2)); svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
  svg.setAttribute('preserveAspectRatio', 'xMidYMid meet');
  svg.innerHTML =
    `<line class="g-axis" x1="42" y1="${top}" x2="42" y2="${plotBottom}"/><line class="g-axis" x1="42" y1="${plotBottom}" x2="1030" y2="${plotBottom}"/>` +
    `<text class="g-axis-label" x="16" y="34" transform="rotate(-90 16 34)" text-anchor="end">期望值 / 市场关注度</text>` +
    `<text class="g-axis-label" x="1030" y="${plotBottom + 17}" text-anchor="end">时间 / 成熟度 →</text>` +
    `<path class="g-curve" d="${curve}"/>`;
  const path = svg.querySelector('.g-curve');
  const L = path.getTotalLength();
  const NS = 'http://www.w3.org/2000/svg';
  // 阶段分隔与标签
  const bounds = [0, 0.14, 0.38, 0.58, 0.82, 1];
  const bx = bounds.map(b => path.getPointAtLength(b * L).x);
  (HYPE.phases || []).forEach((ph, i) => {
    if (i > 0) {
      const ln = document.createElementNS(NS, 'line');
      ln.setAttribute('class', 'g-phase-line');
      ln.setAttribute('x1', bx[i]); ln.setAttribute('x2', bx[i]);
      ln.setAttribute('y1', top + 10); ln.setAttribute('y2', plotBottom);
      svg.appendChild(ln);
    }
    const tx = document.createElementNS(NS, 'text');
    tx.setAttribute('class', 'g-phase-label');
    tx.setAttribute('x', (bx[i] + bx[i + 1]) / 2); tx.setAttribute('y', plotBottom + 35);
    tx.setAttribute('text-anchor', 'middle');
    tx.textContent = ph;
    svg.appendChild(tx);
  });
  // 数据点
  (HYPE.items || []).forEach((it, i) => {
    const pt = path.getPointAtLength(Math.max(0, Math.min(1, it.pos)) * L);
    const ladder = [-16, 30, -40, 52];
    const off = ladder[i % 4];
    const above = off < 0;
    const leader = document.createElementNS(NS, 'line');
    leader.setAttribute('class', 'g-leader');
    leader.setAttribute('x1', pt.x); leader.setAttribute('y1', pt.y + (above ? -6 : 6));
    leader.setAttribute('x2', pt.x); leader.setAttribute('y2', pt.y + off + (above ? 4 : -10));
    svg.appendChild(leader);
    const dot = document.createElementNS(NS, 'circle');
    dot.setAttribute('class', 'g-dot');
    dot.setAttribute('cx', pt.x); dot.setAttribute('cy', pt.y); dot.setAttribute('r', 5);
    const label = document.createElementNS(NS, 'text');
    label.setAttribute('class', 'g-label');
    label.setAttribute('x', pt.x); label.setAttribute('y', pt.y + off);
    label.setAttribute('text-anchor', 'middle');
    label.textContent = it.n;
    const go = () => it.nodeId && nodeById.has(it.nodeId) && select(it.nodeId);
    dot.addEventListener('click', go);
    label.addEventListener('click', go);
    svg.appendChild(dot); svg.appendChild(label);
  });
  $('#hype-date').textContent = (HYPE._meta && HYPE._meta.updatedAt) || '';
  svg.dataset.layoutHeight = String(H);
  const sync = () => {
    const r = svg.getBoundingClientRect();
    if (!r.width || !r.height) return;
    const next = Math.max(340, W * r.height / r.width);
    if (Math.abs(next - Number(svg.dataset.layoutHeight)) > 1) renderGartner(next);
  };
  if (typeof ResizeObserver !== 'undefined') {
    svg.__gartnerObserver = new ResizeObserver(sync);
    svg.__gartnerObserver.observe(svg);
  }
  requestAnimationFrame(sync);
}

/* ---------- 节点视图 ---------- */
async function select(id) {
  if (!nodeById.has(id)) return;
  selectedId = id;
  showView('node');
  setActive(l2AncestorOf(id));
  renderTree(nodeById.get(l2AncestorOf(id)));
  renderBreadcrumbLoading(id);
  const data = await fetchNode(id);
  if (selectedId !== id) return;
  renderNode(data);
}
async function fetchNode(id) {
  const c = nodeCache.get(id);
  if (c && Date.now() - c.t < 60_000) return c.data;
  const r = await fetch(apiUrl(`/api/node/${id}`));
  const data = await r.json();
  nodeCache.set(id, { t: Date.now(), data });
  return data;
}
function renderBreadcrumbLoading(id) {
  const names = [];
  let cur = id;
  while (cur && cur !== 'root') { names.unshift(nodeById.get(cur).name); cur = parentOf.get(cur); }
  $('#breadcrumb').innerHTML = names.map(esc).join('<span class="sep">›</span>');
  $('#counts').textContent = '加载中…';
}

const MKT_GROUPS = [
  ['A股', c => c.startsWith('sh') || c.startsWith('sz')],
  ['港股', c => c.startsWith('hk')],
  ['美股', c => c.startsWith('us')],
];

function renderNode(d) {
  $('#breadcrumb').innerHTML = d.path.map(esc).join('<span class="sep">›</span>');
  $('#counts').textContent = `标的 ${d.counts.tickers} · 资讯 ${d.counts.news} · 研报 ${d.counts.reports}`;

  if (d.judgment) {
    const inherited = d.judgment.nodeId !== d.id ? `（继承自「${esc(d.judgment.nodeName)}」）` : '';
    $('#judgment').innerHTML =
      `<div class="j-head"><span class="j-title">趋势研判${inherited}</span>` +
      (d.judgment.score ? `<span class="j-score">景气度 ${d.judgment.score}</span>` : '') +
      `<span class="j-date">${(JUDG._meta && JUDG._meta.updatedAt) || ''} 更新</span></div>` +
      `<div>${esc(d.judgment.text)}</div>`;
  } else {
    $('#judgment').innerHTML = '<div class="j-head"><span class="j-title">趋势研判</span></div><div>暂无研判，待周度更新生成。</div>';
  }

  // 业绩与 IPO（该环节相关，无内容则隐藏）
  const tl = d.timeline || { earnings: [], ipos: [] };
  const tlSec = $('#node-timeline');
  if (tl.earnings.length + tl.ipos.length) {
    tlSec.style.display = '';
    const inherited = tl.from && tl.from.id !== d.id;
    $('#node-tl-hint').textContent = '该环节相关公司 · 未披露日期为预计' + (inherited ? ` · 继承自「${tl.from.name}」` : '');
    const pctMap = new Map(d.tickers.map(t => [t.c, t.pct]));
    const eRow = e => {
      const [cls, label] = e.disclosed ? (BEAT_BADGE[e.beat] || ['b-inline', '已披露']) : ['b-pending', '未披露 · 预计'];
      const p = e.ticker != null ? pctMap.get(e.ticker) : null;
      const pct = p == null ? '' : `<span class="${pctCls(p)}" style="font-size:11.5px">今日 ${fmtPct(p)}</span>`;
      return `<div class="tl-row">${tlDate(e.date)}<div class="tl-main">` +
        `<div class="tl-head">${tlCo(e)}<span class="tl-period">${esc(e.period)}</span><span class="badge ${cls}">${label}</span>${pct}</div>` +
        `<div class="tl-text">${esc(e.text || '')}</div></div></div>`;
    };
    const up = tl.earnings.filter(e => !e.disclosed).sort((a, b) => a.date.localeCompare(b.date));
    const past = tl.earnings.filter(e => e.disclosed).sort((a, b) => b.date.localeCompare(a.date));
    let html = '';
    if (tl.earnings.length) html += `<div class="tl-group">业绩 · ${tl.earnings.length}</div>` + [...up, ...past].map(eRow).join('');
    if (tl.ipos.length) html += `<div class="tl-group">IPO · ${tl.ipos.length}</div>` + tl.ipos.map(p =>
      `<div class="tl-row"><div class="tl-date">${esc(p.date)}</div><div class="tl-main">` +
      `<div class="tl-head">${tlCo(p)}<span class="tl-period">${esc(p.market)}</span><span class="badge b-status">${esc(p.status)}</span></div>` +
      `<div class="tl-text">${esc(ipoText(p))}</div></div></div>`).join('');
    $('#node-tl-body').innerHTML = html;
    document.querySelectorAll('#node-tl-body .tl-co[data-node]').forEach(el =>
      el.addEventListener('click', () => select(el.dataset.node)));
  } else {
    tlSec.style.display = 'none';
    $('#node-tl-body').innerHTML = '';
  }

  // 标的：按市场分组 + 未上市公司
  const firms = d.firms || [];
  $('#badge-tickers').textContent = d.counts.tickers ? `${d.counts.tickers} 只` : '';
  let tkHtml = MKT_GROUPS.map(([label, fn]) => {
    const list = d.tickers.filter(t => fn(t.c));
    if (!list.length) return '';
    const rows = list.map(t => {
      const pct = t.pct == null ? '<span class="pct-flat">-</span>'
        : `<span class="${pctCls(t.pct)}">${fmtPct(t.pct)}</span>`;
      return `<div class="trow">${stockLink(t.c, `<span class="t-name">${esc(t.n)}</span><span class="t-code">${fmtCode(t.c)}</span>`)}` +
        `<span class="t-right"><span class="t-price">${t.price == null ? '-' : fmtPrice(t.price)}</span>${pct}</span></div>`;
    }).join('');
    return `<div class="mkt-head">${label} · ${list.length} 只</div>${rows}`;
  }).join('');
  if (firms.length) {
    tkHtml += `<div class="mkt-head">未上市 · ${firms.length} 家</div>` + firms.map(f =>
      `<div class="trow"><span class="t-name">${esc(f.n)}</span>` +
      `<span class="t-code" style="text-align:right">${esc(f.note || '')}</span></div>`
    ).join('');
  }
  $('#panel-tickers').innerHTML = tkHtml || '<div class="empty">该环节暂未配置标的</div>';

  // 基金：按环节暴露排序（前十大持仓中属于该环节标的的净值占比合计）
  const funds = d.funds || [];
  $('#badge-funds').textContent = funds.length ? `${funds.length} 只` : '';
  const maxExpo = funds.length ? funds[0].expo : 1;
  $('#panel-funds').innerHTML = funds.length ? funds.map(f =>
    `<div class="frow"><div class="fr-top"><a class="fr-name q-link" href="${fundUrl(f.code)}" target="_blank" rel="noopener" title="天天基金详情">${esc(f.name)}<span class="fr-code">${f.code}</span></a>` +
    `<span class="fr-expo">${f.expo.toFixed(1)}%</span></div>` +
    `<div class="expo-bar"><div style="width:${Math.min(100, f.expo / maxExpo * 100).toFixed(0)}%"></div></div>` +
    `<div class="fr-sub"><span class="chip">${esc(f.type)}</span><span>${esc(f.matched.join(' / '))}</span></div></div>`
  ).join('') : '<div class="empty">暂无该环节暴露 ≥0.5% 的基金</div>';

  $('#badge-news').textContent = d.counts.news ? `${d.counts.news} 条` : '';
  $('#panel-news').innerHTML = d.news.length ? d.news.map(n => {
    const t = n.publishedAt ? new Date(n.publishedAt).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false }) : '';
    return `<div class="item"><a class="i-title" href="${esc(n.url)}" target="_blank" rel="noopener">${esc(n.title)}</a>` +
      `<div class="i-meta"><span>${t}</span><span>${esc(n.source || '')}</span></div></div>`;
  }).join('') : '<div class="empty">近 7 天暂无匹配资讯</div>';

  $('#badge-reports').textContent = d.counts.reports ? `${d.counts.reports} 篇` : '';
  $('#panel-reports').innerHTML = d.reports.length ? d.reports.map(r => {
    const stock = r.name ? `<span class="chip stock">${esc(r.name)}</span>` : '';
    const rating = r.rating && r.rating !== '暂无评级' ? `<span class="chip rating">${esc(r.rating)}</span>` : '';
    return `<div class="item"><a class="i-title" href="${esc(r.url)}" target="_blank" rel="noopener">${esc(r.title)}</a>` +
      `<div class="i-meta"><span>${r.date.slice(5)}</span><span>${esc(r.org)}</span>${stock}${rating}</div></div>`;
  }).join('') : '<div class="empty">近 7 天暂无匹配研报</div>';
}

/* ---------- SVG 树 ---------- */
const ROW_H = 40, BOX_H = 30, COL_GAP = 38, PAD = 14;
function measure(name) {
  let w = 0;
  for (const ch of name) w += ch.charCodeAt(0) > 255 ? 12.5 : 7.2;
  return Math.max(58, Math.ceil(w) + 22);
}
function renderTree(root) {
  const colW = [];
  (function scan(n, d) {
    colW[d] = Math.max(colW[d] || 0, measure(n.name));
    (n.children || []).forEach(c => scan(c, d + 1));
  })(root, 0);
  const colX = [PAD];
  for (let i = 1; i < colW.length; i++) colX[i] = colX[i - 1] + colW[i - 1] + COL_GAP;

  let leaf = 0;
  const pos = new Map();
  (function place(n, d) {
    let y;
    if (!n.children || n.children.length === 0) { y = PAD + leaf * ROW_H; leaf++; }
    else {
      const ys = n.children.map(c => place(c, d + 1));
      y = (Math.min(...ys) + Math.max(...ys)) / 2;
    }
    pos.set(n.id, { x: colX[d], y, w: measure(n.name) });
    return y;
  })(root, 0);

  const H = PAD * 2 + Math.max(leaf, 1) * ROW_H;
  const W = colX[colW.length - 1] + colW[colW.length - 1] + PAD;

  let links = '', nodes = '';
  (function draw(n) {
    const p = pos.get(n.id);
    (n.children || []).forEach(c => {
      const q = pos.get(c.id);
      links += `<line class="tlink" x1="${p.x + p.w}" y1="${p.y + BOX_H / 2}" x2="${q.x}" y2="${q.y + BOX_H / 2}"/>`;
      draw(c);
    });
    nodes += `<g class="tnode${n.id === selectedId ? ' selected' : ''}" data-id="${n.id}">` +
      `<rect x="${p.x}" y="${p.y}" width="${p.w}" height="${BOX_H}" rx="6"/>` +
      `<text x="${p.x + p.w / 2}" y="${p.y + BOX_H / 2 + 4}" text-anchor="middle">${esc(n.name)}</text></g>`;
  })(root);

  const svg = $('#tree-svg');
  svg.setAttribute('width', W);
  svg.setAttribute('height', H);
  svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
  svg.innerHTML = links + nodes;
  svg.querySelectorAll('.tnode').forEach(g => g.addEventListener('click', () => select(g.dataset.id)));
}

/* ---------- 外部行情页链接 ---------- */
const INDEX_CODES = new Set(['sh000001', 'sz399001', 'sz399006', 'usIXIC', 'usDJI', 'usINX', 'hkHSI', 'hkHSTECH']);
function stockUrl(c) {
  if (!c || INDEX_CODES.has(c)) return null;
  if (c.startsWith('us')) return `https://www.tradingview.com/chart/?symbol=${encodeURIComponent(c.slice(2))}`;
  if (c.startsWith('kr')) return `https://finance.naver.com/item/main.naver?code=${c.slice(2)}`;
  if (c.startsWith('jp')) return `https://www.tradingview.com/chart/?symbol=${encodeURIComponent('TSE:' + c.slice(2))}`;
  if (c.startsWith('tw')) return `https://www.tradingview.com/chart/?symbol=${encodeURIComponent('TWSE:' + c.slice(2))}`;
  if (c.startsWith('hk')) return `https://www.tradingview.com/chart/?symbol=${encodeURIComponent('HKEX:' + Number(c.slice(2)))}`;
  if (c.startsWith('sh') || c.startsWith('sz')) return `https://stockpage.10jqka.com.cn/${c.slice(2)}/`;
  return null;
}
function stockLink(c, inner) {
  const u = stockUrl(c);
  return u ? `<a class="q-link" href="${u}" target="_blank" rel="noopener" title="查看K线">${inner}</a>` : inner;
}
function fundUrl(code) { return `https://fund.eastmoney.com/${code}.html`; }

/* ---------- 工具 ---------- */
function fmtPrice(p) { return p >= 1000 ? p.toLocaleString('zh-CN', { maximumFractionDigits: 1 }) : p.toFixed(2); }
function fmtPct(p) { return (p > 0 ? '+' : '') + p.toFixed(2) + '%'; }
function pctCls(p) { return p == null ? 'pct-flat' : p > 0 ? 'pct-up' : p < 0 ? 'pct-down' : 'pct-flat'; }
function fmtCode(c) {
  if (c.startsWith('us')) return c.slice(2);
  if (c.startsWith('hk')) return c.slice(2) + '.HK';
  if (c.startsWith('kr')) return c.slice(2) + '.KS';
  if (c.startsWith('jp')) return c.slice(2) + '.JP';
  if (c.startsWith('tw')) return c.slice(2) + '.TW';
  return c.slice(2) + (c.startsWith('sh') ? '.SH' : '.SZ');
}
function esc(s) { return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }

$('#btn-refresh').addEventListener('click', () => {
  nodeCache.clear(); heatmapCache = null; rotationCache = null; feedCache = null; tlCache = null; mapCache = null; topicListCache = null; bubbleCache = null; macroCache = null; physCache = null; physSvgCache.clear();
  if (selectedId === '__overview' || selectedId === '__topic') showOverview();
  else if (selectedId === '__feed') showFeed();
  else if (selectedId === '__timeline') showTimeline();
  else if (selectedId === '__industry') showIndustry();
  else if (selectedId === '__macro') showMacro();
  else if (selectedId === '__phys') showPhys();
  else if (selectedId === '__bubble') showBubble();
  else if (selectedId) select(selectedId);
});

/* 今日焦点三列：事件委托，配平重建 DOM 后监听不丢。 */
document.querySelector('.focus-grid-3')?.addEventListener('click', e => {
  const tp = e.target.closest('.tp-item');
  if (tp) { showTopic(tp.dataset.topic); return; }
  const co = e.target.closest('.fe-co[data-node]');
  if (co) select(co.dataset.node);
});

boot();
