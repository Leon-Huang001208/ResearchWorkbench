/* ============ 交互层：scrollytelling / 面板联动 / 钻取 / kill switch ============ */
const charts = {};   // 图表实例
let currentChapter = null;

/* ---------- 右侧数据面板 ---------- */
function renderPanel(key){
  const snap = PANEL_SNAPSHOTS[key];
  const el = document.getElementById('panel-metrics');
  document.getElementById('panel-era').textContent = snap.era;
  el.innerHTML = snap.metrics.map(m=>`
    <div class="metric">
      <div class="m-k">${m.k}</div>
      <div class="m-v">${m.v}</div>
      <div class="m-d">${m.d}</div>
      <svg class="m-spark" viewBox="0 0 100 24" preserveAspectRatio="none">${spark(m.s)}</svg>
    </div>`).join('');
}
function spark(arr){
  const mx=Math.max(...arr), mn=Math.min(...arr), rg=(mx-mn)||1;
  const pts=arr.map((v,i)=>`${(i/(arr.length-1)*100).toFixed(1)},${(22-(v-mn)/rg*20).toFixed(1)}`).join(' ');
  const up = arr[arr.length-1] >= arr[0];
  return `<polyline points="${pts}" fill="none" stroke="${up?'#2ecc71':'#e74c3c'}" stroke-width="1.6"/>`;
}

/* ---------- 中央舞台切换 ---------- */
function setStage(chartId){
  const stage = document.getElementById('stage-chart');
  const meta = CHARTS.find(c=>c.id===chartId);
  document.getElementById('stage-title').textContent = meta.title;
  document.getElementById('stage-sub').textContent = meta.sub;
  if (charts.__stage) { charts.__stage.dispose(); }
  stage.innerHTML='';
  charts.__stage = renderChart(chartId, stage);
}

/* ---------- 章节激活 ---------- */
function activateChapter(id){
  if (currentChapter === id) return;
  currentChapter = id;
  document.querySelectorAll('.chapter').forEach(c=>c.classList.toggle('active', c.dataset.id===id));
  const ch = CHAPTERS.find(c=>c.id===id);
  setStage(ch.stage);
  renderPanel(ch.panel);
  document.getElementById('progress-label').textContent =
    ch.kicker.replace('WINDOW ','W') + ' · ' + ch.title;
}

/* ---------- 生成章节 DOM ---------- */
function buildChapters(){
  const host = document.getElementById('chapters');
  host.innerHTML = CHAPTERS.map(ch=>`
    <section class="chapter" data-id="${ch.id}">
      <div class="ch-kicker">${ch.kicker}</div>
      <h2 class="ch-title">${ch.title}</h2>
      <p class="ch-lead">${ch.lead}</p>
      ${ch.body.map(p=>`<p class="ch-body">${p}</p>`).join('')}
      <div class="ch-points">
        ${ch.points.map(p=>`<div class="pt"><span class="pt-y">${p[0]}</span><span>${p[1]}</span></div>`).join('')}
      </div>
    </section>`).join('');
  const io = new IntersectionObserver(es=>{
    es.forEach(e=>{ if(e.isIntersecting) activateChapter(e.target.dataset.id); });
  },{rootMargin:'-42% 0px -42% 0px'});
  document.querySelectorAll('.chapter').forEach(c=>io.observe(c));
}

/* ---------- 图表总览（26 张） ---------- */
function buildGallery(){
  const host = document.getElementById('gallery-grid');
  host.innerHTML = CHARTS.map((c,i)=>`
    <div class="g-card" data-id="${c.id}">
      <div class="g-head">
        <span class="g-no">${String(i+1).padStart(2,'0')}</span>
        <div><div class="g-title">${c.title}</div><div class="g-sub">${c.sub}</div></div>
      </div>
      <div class="g-chart" id="g-${c.id}"></div>
      <div class="g-foot"><span class="g-src">来源：${c.src[0]} 等</span><span class="g-drill">点击钻取 ↗</span></div>
    </div>`).join('');
  CHARTS.forEach(c=>{
    charts['g-'+c.id] = renderChart(c.id, document.getElementById('g-'+c.id), {silent:true});
  });
  host.querySelectorAll('.g-card').forEach(card=>{
    card.addEventListener('click',()=>openDrill(card.dataset.id));
  });
}

/* ---------- 钻取弹窗 ---------- */
function openDrill(id){
  const meta = CHARTS.find(c=>c.id===id);
  const idx = CHARTS.indexOf(meta);
  document.getElementById('modal-title').textContent = String(idx+1).padStart(2,'0') + ' · ' + meta.title;
  document.getElementById('modal-sub').textContent = meta.sub;
  document.getElementById('modal-src').innerHTML =
    meta.src.map(s=>`<span class="src-tag">${s}</span>`).join('') +
    `<div class="src-note">${meta.note}</div>`;
  document.getElementById('modal').classList.add('open');
  const dom = document.getElementById('modal-chart');
  dom.innerHTML='';
  if (charts.__modal) charts.__modal.dispose();
  charts.__modal = echarts.init(dom);
  charts.__modal.setOption(builders[id]());
}
function closeDrill(){ document.getElementById('modal').classList.remove('open'); }

/* ---------- Kill switches ---------- */
let ksChart;
const KS_BASE = { x:['2026Q3','2026Q4','2027Q1','2027Q2','2027Q3','2027Q4','2028Q1','2028Q2'],
  base:[14,9,5,3,2,1,0,-1], cons:[14,6,0,-4,-8,-10,-12,-13], contr:[14,2,-8,-18,-28,-32,-30,-28] };
function buildKillSwitches(){
  const host = document.getElementById('ks-list');
  host.innerHTML = KILL_SWITCHES.map(k=>`
    <label class="ks">
      <input type="checkbox" id="${k.id}">
      <span class="ks-body">
        <span class="ks-name">${k.name}<i class="ks-ind"></i></span>
        <span class="ks-desc">${k.desc}</span>
        <span class="ks-meta">冲击：${k.impact} ｜ 情景迁移：${k.scen}</span>
      </span>
    </label>`).join('');
  ksChart = echarts.init(document.getElementById('ks-chart'));
  updateKs();
  KILL_SWITCHES.forEach(k=>document.getElementById(k.id).addEventListener('change',updateKs));
}
function updateKs(){
  const on = Object.fromEntries(KILL_SWITCHES.map(k=>[k.id,document.getElementById(k.id).checked]));
  // 冲击叠加模型：对 Base 路径逐季施加压力
  let stressed = KS_BASE.base.slice();
  if(on.ks1) stressed = stressed.map((v,i)=> v - [0,0,1,2,4,6,8,9][i]);        // capex+20% → 2027H2 起压价
  if(on.ks2) stressed = stressed.map((v,i)=> v + [1,1,1,1,0,0,0,0][i]);        // HBM4 良率低 → 短期更紧
  if(on.ks3) stressed = stressed.map((v,i)=> v - [2,4,7,10,12,14,15,16][i]);   // AI 需求下降
  if(on.ks4) stressed = stressed.map((v,i)=> v - [0,3,6,9,11,12,13,14][i]);    // 库存累积
  const anyOn = Object.values(on).some(Boolean);
  ksChart.setOption({
    tooltip:Object.assign({},TT,{trigger:'axis',valueFormatter:v=>(v>0?'+':'')+v+'%'}),
    legend:{textStyle:{color:C.dim,fontFamily:F},top:4},
    grid:{left:44,right:16,top:34,bottom:30},
    xAxis:AX({type:'category',data:KS_BASE.x}),
    yAxis:AX({type:'value',name:'DRAM 价格 QoQ %',nameTextStyle:{color:C.dim,fontFamily:F}}),
    series:[
      {name:'Base 路径',type:'line',data:KS_BASE.base,lineStyle:{color:C.green,width:2},itemStyle:{color:C.green},symbolSize:5},
      {name:'Conservative',type:'line',data:KS_BASE.cons,lineStyle:{color:C.amber,width:1.5,type:'dashed'},itemStyle:{color:C.amber},symbolSize:4},
      {name:'Contraction',type:'line',data:KS_BASE.contr,lineStyle:{color:C.red,width:1.5,type:'dashed'},itemStyle:{color:C.red},symbolSize:4},
      {name:'Kill-switch 压力测试',type:'line',data:stressed,symbolSize:7,
        lineStyle:{color:'#fff',width:3,type:anyOn?'solid':'dashed',opacity:anyOn?1:.25},
        itemStyle:{color:'#fff',opacity:anyOn?1:.25},areaStyle:anyOn?{opacity:.08}:undefined,
        markLine:{data:[{yAxis:0}],lineStyle:{color:C.line},label:{show:false}}}
    ]
  });
  const verdict = document.getElementById('ks-verdict');
  const min = Math.min(...stressed);
  verdict.innerHTML = !anyOn
    ? '未启用 kill switch — 显示三种情景的基准价格路径。勾选左侧开关进行压力测试。'
    : `压力测试结果：价格环比最低点 <b class="${min<0?'neg':'pos'}">${min>0?'+':''}${min}%</b>（${KS_BASE.x[stressed.indexOf(min)]}）— ${min<=-10?'触发 <b>Contraction</b> 情景。':min<0?'滑向 <b>Conservative</b> 情景。':'Base 情景仍然成立，但斜率受损。'}`;
}

/* ---------- 触发器表 ---------- */
function buildTriggers(){
  document.getElementById('trigger-body').innerHTML = TRIGGERS.map(t=>`
    <tr>
      <td class="t-no">${t.n}</td><td class="t-name">${t.name}</td><td>${t.th}</td>
      <td>${t.win}</td><td>${t.sig}</td>
      <td><span class="t-status ${t.cur.includes('未触发')?'ok':(t.cur.includes('观察')?'warn':'')}"></span>${t.cur}</td>
    </tr>`).join('');
}

/* ---------- 导航/杂项 ---------- */
function buildNav(){
  document.getElementById('nav-links').innerHTML =
    CHAPTERS.map((c,i)=>`<a href="#anchor-${c.id}" data-nav="${c.id}">${String(i+1).padStart(2,'0')} ${c.title.split(' ')[0].slice(0,10)}</a>`).join('') +
    `<a href="#gallery">图表库 26</a><a href="#killswitch">Kill Switch</a><a href="#triggers">触发器</a>`;
  document.getElementById('chapters').insertAdjacentHTML('afterbegin',
    CHAPTERS.map(c=>`<div id="anchor-${c.id}" class="anchor"></div>`).join(''));
}

/* ---------- resize ---------- */
window.addEventListener('resize', ()=>Object.values(charts).forEach(c=>c&&c.resize&&c.resize()));

document.addEventListener('DOMContentLoaded', ()=>{
  buildNav(); buildChapters(); buildGallery(); buildKillSwitches(); buildTriggers();
  renderPanel('ch1');
  activateChapter('ch1');
  // 首屏周期墙
  charts.__hero = renderChart('wallTimeline', document.getElementById('hero-chart'), {silent:true});
  document.getElementById('modal-close').addEventListener('click',closeDrill);
  document.getElementById('modal').addEventListener('click',e=>{ if(e.target.id==='modal') closeDrill(); });
  document.addEventListener('keydown',e=>{ if(e.key==='Escape') closeDrill(); });
  document.getElementById('year').textContent = new Date().getFullYear();
});
