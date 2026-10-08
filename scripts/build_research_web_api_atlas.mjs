#!/usr/bin/env node
/** Build the current Research Web API atlas from the checked architecture inventory. */
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const MAP_PATH = 'docs/architecture/research-web/architecture-map.json';
const ARTIFACT_ROOT = 'outputs/research-web-architecture';
const escapeHTML = value => String(value).replace(/[&<>"']/g, character => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[character]));

export function category(api) {
  const route = api.path;
  if (route.includes('/local-integrations')) return '本机集成';
  if (route.includes('/frameworks')) return '研究框架';
  if (route.includes('/integrations')) return '集成协调器';
  if (route.includes('/automations')) return '自动化';
  if (route.includes('/mcp/')) return 'MCP Registry';
  if (route.includes('/report-workflows') || route.includes('/report-runs')) return '报告 Workflow';
  if (route.includes('/assets/') || route.includes('/watchlists') || route.includes('/asset-')) return '资产观察';
  if (route.includes('/data/') || route.includes('/datasets') || route.includes('/handoffs') || route.includes('/artifacts')) return 'DataHub 与交接';
  if (route.includes('/capabilities') || route.includes('/skills') || route.includes('/tools') || route.includes('/workflows')) return '能力中心';
  if (route.includes('/operations')) return '运行与用量';
  if (route.includes('/documentation')) return '架构文档';
  if (route.includes('/report-projects')) return '历史报告兼容';
  return '研究会话与 Runtime';
}

function safePath(value) {
  if(typeof value!=='string' || !value || !/^[A-Za-z0-9_./-]+$/.test(value) || value.startsWith('/') || value.split('/').some(part=>part==='..' || part==='.' || !part)) throw new Error('unsafe repository path');
  return value;
}

function checkedFile(root, file) {
  let current=root;
  for(const part of safePath(file).split('/')) {
    current=path.join(current,part);
    try {
      if(fs.lstatSync(current).isSymbolicLink()) throw new Error('symlink in generated artifact path');
    } catch(error) {
      if(error.code!=='ENOENT') throw error;
    }
  }
  return current;
}

function repositoryLink(map, file, {compact=false} = {}) {
  const repository=map.reading?.repository;
  safePath(file.replace(/\/$/,''));
  if(!repository) return `<code>${escapeHTML(file)}</code>`;
  if(repository.url!=='https://github.com/Leon-Huang001208/ResearchWorkbench' || !/^[a-f0-9]{40}$/.test(repository.revision)) throw new Error('invalid architecture repository identity');
  return `<a href="${repository.url}/${file.endsWith('/')?'tree':'blob'}/${repository.revision}/${file.split('/').map(encodeURIComponent).join('/')}" rel="noopener noreferrer"${compact?` aria-label="${escapeHTML(file)}" title="${escapeHTML(file)}"`:''}>${escapeHTML(compact?path.posix.basename(file.replace(/\/$/,'')):file)}</a>`;
}

function readingBrand(root) {
  const asset=checkedFile(root,'app/research_web/ui/assets/brand/brand-mark.png');
  if(!fs.existsSync(asset)) {
    if(fs.existsSync(checkedFile(root,'app/research_web/ui/shell.mjs'))) throw new Error('product reading brand asset missing');
    return ''; // Non-product fixtures have no brand; never invent a substitute image.
  }
  const identity=fs.lstatSync(asset);
  if(!identity.isFile() || identity.size>128*1024) throw new Error('invalid reading brand asset');
  const bytes=fs.readFileSync(asset);
  if(!bytes.subarray(0,8).equals(Buffer.from([137,80,78,71,13,10,26,10]))) throw new Error('invalid reading brand PNG');
  return `<img src="data:image/png;base64,${bytes.toString('base64')}" alt="" width="108" height="120">`;
}

const READING_CSS = `
:root{color-scheme:light;--canvas:#fff;--surface:#fafaf9;--sidebar:#f5f5f3;--ink:#242424;--muted:#686860;--line:#e8e8e5;--blue:#086aa6;--selected:#e8e8e5;--focus:#74746b;--shadow:0 3px 16px #24242408;--action:#272725;--on-action:#fff;font-family:-apple-system,BlinkMacSystemFont,'PingFang SC','Segoe UI',sans-serif}
:root[data-theme=dark]{color-scheme:dark;--canvas:#1b1b19;--surface:#222220;--sidebar:#171715;--ink:#ecece7;--muted:#aaa99f;--line:#343430;--blue:#70b9e8;--selected:#30302c;--focus:#a4a496;--shadow:0 3px 16px #00000018;--action:#e8e8e2;--on-action:#1b1b19}
*{box-sizing:border-box}body{margin:0;background:var(--canvas);color:var(--ink);font-size:16px;line-height:1.65}button,input,select{font:inherit}a{color:var(--blue);text-underline-offset:4px}button,a,input,select{transition:background 150ms,color 150ms,border-color 150ms}a:focus-visible,button:focus-visible,input:focus-visible,select:focus-visible{outline:2px solid var(--focus);outline-offset:4px}p{text-wrap:pretty}section,article{scroll-margin-top:94px}
.shell{display:grid;grid-template-columns:248px minmax(0,1fr);min-height:100vh}.sidebar{height:100vh;position:sticky;top:0;background:var(--sidebar);border-right:1px solid var(--line);padding:32px 20px;display:flex;flex-direction:column}.brand{display:flex;align-items:center;gap:12px;color:var(--ink);font-size:16px;font-weight:650;text-decoration:none;line-height:1.2}.brand img{width:27px;height:30px;object-fit:contain}:root[data-theme=dark] .brand img{filter:brightness(0) invert(1)}.sidebar-label{margin:48px 12px 12px;font-size:13px;color:var(--muted)}.toc{display:grid;gap:4px}.toc a{display:flex;align-items:center;gap:12px;padding:10px 12px;border-radius:8px;color:var(--muted);font-size:14px;text-decoration:none}.toc a span{font:12px ui-monospace,SFMono-Regular,Menlo,monospace;opacity:.65}.toc a:hover,.toc a.active{color:var(--ink);background:var(--selected)}.sidebar-foot{margin-top:auto;padding:24px 12px 0;border-top:1px solid var(--line);font-size:13px;color:var(--muted)}.sidebar-foot a{display:block;margin-top:8px}
.workspace{min-width:0}.topbar{position:sticky;top:0;z-index:4;height:72px;display:flex;align-items:center;justify-content:space-between;gap:24px;padding:0 48px;background:var(--canvas);border-bottom:1px solid var(--line)}.crumb{color:var(--muted);font-size:14px}.crumb strong{color:var(--ink);font-weight:500}.search{display:flex;align-items:center;gap:12px;width:min(340px,44%);border:1px solid var(--line);border-radius:8px;background:var(--surface);padding:8px 12px}.search input{width:100%;border:0;outline:none;background:transparent;color:var(--ink);font-size:14px}.search kbd{white-space:nowrap;font-size:12px;color:var(--muted);border:1px solid var(--line);padding:0 5px;border-radius:4px}
main{max-width:1220px;margin:auto;padding:48px 48px 96px}.intro{padding-bottom:32px}.eyebrow{font:12px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace;color:var(--muted)}.intro h1{font-size:clamp(28px,3.2vw,40px);line-height:1.25;font-weight:600;letter-spacing:-.035em;margin:12px 0 16px}.intro p{color:var(--muted);max-width:720px;margin:0}.intro-actions{display:flex;gap:24px;align-items:center;margin-top:24px}.primary-link{display:inline-flex;align-items:center;gap:24px;padding:10px 16px;background:var(--action);color:var(--on-action);border-radius:8px;text-decoration:none;font-size:14px}.primary-link:hover{opacity:.85}.stat-line{font-size:13px;color:var(--muted)}.stat-line b{color:var(--ink);font-weight:550}
.reading-section{margin-top:32px}.section-heading{display:flex;align-items:baseline;justify-content:space-between;gap:16px;margin-bottom:16px}.section-heading h2{margin:0;font-size:21px;line-height:1.4;font-weight:600;letter-spacing:-.02em}.section-heading h2 span{font:13px ui-monospace,SFMono-Regular,Menlo,monospace;color:var(--muted);margin-right:14px}.section-count{font-size:12px;color:var(--muted)}.diagram-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.diagram{position:relative;display:flex;align-items:center;gap:20px;min-width:0;padding:20px 24px;border:1px solid var(--line);border-radius:12px;text-decoration:none;color:var(--ink);background:var(--surface)}.diagram:hover{border-color:var(--blue)}.entry-copy{min-width:0;flex:1}.diagram h3{font-size:17px;line-height:1.5;font-weight:600;margin:6px 0}.diagram p{font-size:14px;line-height:1.65;color:var(--muted);margin:0}.entry-arrow{color:var(--muted);font-size:20px}.preview-placeholder{display:none}.reading-section:has(.diagram-grid>.diagram:only-child) .diagram-grid{grid-template-columns:1fr}#overview .diagram{min-height:144px;padding:28px 32px;background:var(--sidebar)}#overview h3{font-size:24px}#overview .entry-arrow{font-size:28px}
#modules{margin-top:48px;border-top:1px solid var(--line);padding-top:32px}.module-list{border-top:1px solid var(--line)}.module-row{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:28px;padding:20px 0;border-bottom:1px solid var(--line)}.module-row h3{font-size:16px;margin:0 0 4px;font-weight:600}.module-row p{font-size:14px;color:var(--muted);margin:0;max-width:660px}.module-actions{display:flex;align-items:center;gap:20px;font-size:13px;white-space:nowrap}.empty{padding:40px 0;color:var(--muted)}[hidden]{display:none!important}.notes{border-top:1px solid var(--line);margin-top:48px;padding-top:24px;font-size:13px;color:var(--muted)}.notes p{margin:0 0 8px}.mobile-nav{display:none}
@media(max-width:1000px){.shell{grid-template-columns:220px minmax(0,1fr)}main{padding:32px}.topbar{padding:0 32px}.diagram-grid{grid-template-columns:1fr}.module-row{grid-template-columns:1fr;gap:12px}.module-actions{justify-content:flex-start}}
@media(prefers-reduced-motion:reduce){*{transition:none!important}}
:root{--control-line:#ddddd8}:root[data-theme=dark]{--control-line:#494942}
.topbar{height:auto;min-height:72px;padding-top:12px;padding-bottom:12px;flex-wrap:wrap}.page-tools{display:flex;align-items:center;gap:12px;flex-wrap:wrap}.page-tools label{font-size:13px;color:var(--muted);display:flex;align-items:center;gap:6px}.page-tools select{font-size:13px;padding:7px 8px;background:var(--surface);color:var(--ink);border:1px solid var(--control-line);border-radius:8px}.search{width:100%;margin-top:24px;max-width:640px}.search input:disabled,.page-tools select:disabled{opacity:.55;cursor:not-allowed}
.reading-hint{font-size:13px;color:var(--muted);margin-top:12px}.module-jump{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:20px}.module-jump a{font-size:13px;color:var(--muted);text-decoration:none;padding:5px 10px;border-radius:8px;background:var(--sidebar)}.module-jump a:hover{color:var(--ink);background:var(--selected)}
.module{padding:24px 0;border-bottom:1px solid var(--line)}.module h3{font-size:17px;margin:0 0 6px;font-weight:600}.module>p{font-size:14px;color:var(--muted);margin:0 0 16px}.module-resources{display:grid;grid-template-columns:minmax(0,1.1fr) minmax(0,1.5fr) minmax(0,1fr);gap:20px;margin:0}.module-resources div{min-width:0}dt{font-size:12px;color:var(--muted);margin-bottom:4px}dd{font-size:14px;margin:0;overflow-wrap:anywhere}.module details{margin-top:16px;font-size:14px}.module summary{cursor:pointer;color:var(--muted);padding:4px 0;width:fit-content}.module summary:hover{color:var(--ink)}.module details[open] summary{color:var(--ink);margin-bottom:12px}.source-list{margin:0;padding:16px 20px;background:var(--surface);border-radius:8px}.source-list dd{font:13px/1.8 ui-monospace,SFMono-Regular,Menlo,monospace;margin-bottom:12px}.source-list dd:last-child{margin-bottom:0}.notice{padding:16px;border:1px solid var(--line);border-radius:8px;font-size:14px}
:root[data-density=compact] .diagram-grid{grid-template-columns:1fr}:root[data-density=compact] .diagram{padding:14px 20px;min-height:0}:root[data-density=compact] #overview .diagram{padding:20px 24px}:root[data-density=compact] .diagram p{display:none}:root[data-density=compact] .reading-section{margin-top:24px}:root[data-density=compact] #overview h3{font-size:20px}:root[data-density=compact] .module{padding:16px 0}
@media(max-width:1000px){.page-tools{gap:8px}.module-resources{grid-template-columns:1fr 1fr}.module-resources div:last-child{grid-column:1/-1}}
@media(max-width:720px){.shell{display:block}.sidebar{display:none}.mobile-nav{display:block;margin-bottom:24px;padding:12px;background:var(--sidebar);border-radius:8px}.mobile-nav summary{font-size:14px}.mobile-nav nav{display:grid;padding-top:12px;gap:8px}.mobile-nav a{font-size:14px}.topbar{padding:16px 20px}.search{max-width:100%}main{padding:28px 20px 72px}.intro-actions{align-items:flex-start;flex-direction:column;gap:16px}.diagram,#overview .diagram{padding:20px}#overview h3{font-size:21px}.module-resources{grid-template-columns:1fr}.module-resources div:last-child{grid-column:auto}.crumb{width:100%}.module{padding:20px 0}.source-list{padding:14px}.page-tools{width:100%}}
@media(prefers-color-scheme:dark){:root:not([data-theme]){color-scheme:dark;--canvas:#1b1b19;--surface:#222220;--sidebar:#171715;--ink:#ecece7;--muted:#aaa99f;--line:#343430;--blue:#70b9e8;--selected:#30302c;--focus:#a4a496;--action:#e8e8e2;--on-action:#1b1b19;--control-line:#494942}:root:not([data-theme]) .brand img{filter:brightness(0) invert(1)}}
`;

const READING_SCRIPT = `
try {
  const root=document.documentElement;
  const search=document.getElementById('architecture-search');
  const theme=document.getElementById('architecture-theme');
  const density=document.getElementById('architecture-density');
  const status=document.getElementById('reading-status');
  const empty=document.getElementById('reading-empty');
  const entries=[...document.querySelectorAll('.reading-entry')];
  const sections=[...document.querySelectorAll('main > section')];
  const media=matchMedia('(prefers-color-scheme:dark)');
  function applyTheme(){root.dataset.theme=theme.value==='auto'?(media.matches?'dark':'light'):theme.value;}
  function applyDensity(){root.dataset.density=density.value;}
  for(const control of [search,theme,density])control.disabled=false;
  applyTheme();applyDensity();theme.addEventListener('change',applyTheme);density.addEventListener('change',applyDensity);
  media.addEventListener('change',applyTheme);
  function filter(){
    const term=search.value.trim().toLowerCase();let diagrams=0,modules=0;
    for(const entry of entries){entry.hidden=!entry.dataset.readingSearch.includes(term);if(!entry.hidden){if(entry.dataset.readingKind==='diagram')diagrams++;else modules++;}}
    for(const section of sections)section.hidden=!section.querySelector('.reading-entry:not([hidden])');
    empty.hidden=diagrams+modules!==0;
    status.textContent=term?'找到 '+diagrams+' 张图、'+modules+' 个模块':'可查找图名、模块职责、源码路径与 API 领域。';
  }
  search.addEventListener('input',filter);
  document.getElementById('reading-clear')?.addEventListener('click',()=>{search.value='';filter();search.focus();});
  document.addEventListener('keydown',event=>{if((event.metaKey||event.ctrlKey)&&event.key.toLowerCase()==='k'){event.preventDefault();search.focus();}});
  function revealHash(){
    let id;try{id=decodeURIComponent(location.hash.slice(1));}catch{return;}
    const target=document.getElementById(id);if(!target)return;
    if(target.closest?.('main > section')?.hidden || target.closest?.('.reading-entry')?.hidden || target.hidden){search.value='';filter();}
    if(target.tagName==='DETAILS')target.open=true;
  }
  window.addEventListener('hashchange',revealHash);filter();revealHash();
  if('IntersectionObserver' in window){
    const links=[...document.querySelectorAll('[data-reading-link]')];
    const observer=new IntersectionObserver(changes=>{
      for(const change of changes)if(change.isIntersecting){
        for(const link of links){const active=link.getAttribute('href')==='#'+change.target.id;link.classList.toggle('active',active);if(active)link.setAttribute('aria-current','location');else link.removeAttribute('aria-current');}
      }
    },{rootMargin:'-15% 0px -65% 0px'});
    for(const section of sections)observer.observe(section);
  }
} catch(error) {
  console.error('architecture_reading_initialization_failed',error);
  for(const id of ['architecture-search','architecture-theme','architecture-density']){const control=document.getElementById(id);if(control)control.disabled=true;}
  const message=document.getElementById('reading-error');if(message)message.hidden=false;
}
`;

export function renderArtifacts(root) {
  const map = JSON.parse(fs.readFileSync(checkedFile(root,MAP_PATH), 'utf8'));
  if(fs.existsSync(checkedFile(root,'app/research_web/documentation.py')) && !map.reading) throw new Error('product reading metadata is required');
  if (!Array.isArray(map.apis) || !map.apis.length) throw new Error('architecture API inventory is empty');
  for(const api of map.apis) {
    if(!['GET','POST','PUT','PATCH','DELETE','HEAD','OPTIONS'].includes(api.method) || typeof api.path!=='string' || !api.path.startsWith('/') || /[\x00-\x1f]/.test(api.path)) throw new Error('invalid API identity');
    safePath(api.source);
  }
  const compare=(a,b)=>a<b?-1:a>b?1:0;
  const apis = [...map.apis].sort((left, right) => compare(category(left),category(right)) || compare(left.path,right.path) || compare(left.method,right.method) || compare(left.source,right.source));
  const uniqueOperations = new Set(apis.map(api => `${api.method} ${api.path}`)).size;
  const methodCounts = Object.fromEntries(['GET','POST','PUT','PATCH','DELETE'].map(method => [method, apis.filter(api => api.method === method).length]));
  const categories = [...new Set(apis.map(category))];
  const cards = apis.map(api => `<article class="api" data-category="${escapeHTML(category(api))}" data-search="${escapeHTML(`${api.method} ${api.path} ${api.source}`.toLowerCase())}"><div class="head"><span class="method ${api.method.toLowerCase()}">${escapeHTML(api.method)}</span><code>${escapeHTML(api.path)}</code></div><div class="meta"><span>${escapeHTML(category(api))}</span>${repositoryLink(map,api.source)}</div></article>`).join('');
  const html = `<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Research Workbench · API Atlas</title><style>
:root{color-scheme:light dark;--paper:#f5f7fb;--surface:#fff;--ink:#182337;--muted:#66758b;--line:#dce4ee;--blue:#205cf2;--green:#16866b;--amber:#9a6800}*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:14px/1.55 system-ui,-apple-system,"PingFang SC",sans-serif}header{background:#071d34;color:#fff;padding:28px max(20px,calc((100vw - 1320px)/2))}header h1{margin:0;font-size:30px}header p{margin:5px 0 0;color:#b9c9dc}main{max-width:1320px;margin:auto;padding:24px}.metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:18px}.metric,.api{background:var(--surface);border:1px solid var(--line);border-radius:12px}.metric{padding:15px}.metric b{display:block;font-size:23px}.toolbar{display:flex;gap:10px;position:sticky;top:0;z-index:2;padding:12px 0;background:color-mix(in srgb,var(--paper) 92%,transparent)}input,select{border:1px solid var(--line);border-radius:9px;background:var(--surface);color:var(--ink);padding:10px 12px}input{flex:1}.list{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.api{padding:14px}.head{display:flex;align-items:flex-start;gap:9px}.head code{font-size:13px;overflow-wrap:anywhere}.method{font-size:11px;font-weight:800;padding:3px 6px;border-radius:5px;flex:none}.get{background:#e8f7f1;color:var(--green)}.post{background:#eaf0ff;color:var(--blue)}.put,.patch{background:#fff4d7;color:var(--amber)}.delete{background:#ffecea;color:#ad342d}.meta{display:flex;justify-content:space-between;gap:8px;margin-top:11px;color:var(--muted);font-size:12px}.meta code,.meta a{overflow-wrap:anywhere;min-width:0;text-align:right}.empty{display:none;text-align:center;padding:48px;color:var(--muted)}@media(max-width:800px){.metrics{grid-template-columns:repeat(2,1fr)}.list{grid-template-columns:1fr}.toolbar{flex-wrap:wrap}.toolbar input{flex-basis:100%}}@media(prefers-color-scheme:dark){:root{--paper:#0b1524;--surface:#142238;--ink:#e5edf8;--muted:#a8bbd2;--line:#2d4058;--blue:#87acff}.get{background:#173e35}.post{background:#1d315d}.put,.patch{background:#49391d}.delete{background:#4a2527}}</style></head><body><header><nav aria-label="面包屑"><a href="index.html" style="color:inherit">架构阅读起点</a> / API Atlas</nav><h1>Research Web API Atlas</h1><p>由 architecture-map.json 生成 · 当前源码声明 · 不包含旧 /api/research-runs 链路</p></header><main><section class="metrics"><div class="metric"><span>唯一接口</span><b>${uniqueOperations}</b></div><div class="metric"><span>源码声明</span><b>${apis.length}</b></div><div class="metric"><span>GET / POST 声明</span><b>${methodCounts.GET} / ${methodCounts.POST}</b></div><div class="metric"><span>领域分组</span><b>${categories.length}</b></div></section><div class="toolbar"><input id="search" type="search" aria-label="搜索接口" placeholder="搜索 Method、路径或源码"><select id="category" aria-label="筛选领域"><option value="">全部领域</option>${categories.map(value => `<option>${escapeHTML(value)}</option>`).join('')}</select></div><section class="list" aria-live="polite">${cards}</section><p class="empty">没有匹配的接口。</p></main><script>(()=>{const search=document.querySelector('#search'),select=document.querySelector('#category'),cards=[...document.querySelectorAll('.api')],empty=document.querySelector('.empty');const categoryParam=new URLSearchParams(location.search).get('category');if([...select.options].some(option=>option.value===categoryParam))select.value=categoryParam;function filter(){const query=search.value.trim().toLowerCase(),kind=select.value;let visible=0;for(const card of cards){const show=(!query||card.dataset.search.includes(query))&&(!kind||card.dataset.category===kind);card.hidden=!show;if(show)visible+=1}empty.style.display=visible?'none':'block'}search.addEventListener('input',filter);select.addEventListener('change',filter);filter()})();</script></body></html>`;
  const levels=map.reading?.levels || [{id:'details',title:'架构图目录'}];
  const levelIds=levels.map(level=>level.id);
  if(new Set(levelIds).size!==levelIds.length || levelIds.some(id=>!/^[-a-z0-9]+$/.test(id)) || map.diagrams.some(diagram=>!levelIds.includes(diagram.level || 'details'))) throw new Error('invalid or uncovered reading level');
  if(map.reading && !map.diagrams.some(diagram=>diagram.id==='00-system-overview' && diagram.level==='overview')) throw new Error('product overview missing from reading inventory');
  const diagramCards=levels.map(level=>{
    const diagrams=map.diagrams.filter(diagram=>(diagram.level || 'details')===level.id);
    return `<section id="${escapeHTML(level.id)}" class="reading-section"><div class="section-heading"><h2>${escapeHTML(level.title)}</h2><span class="section-count">${diagrams.length} 个视图</span></div><div class="grid diagram-grid">${diagrams.map(diagram=>{
      if(!/^[a-z0-9-]+$/.test(diagram.id) || diagram.artifact!==`${ARTIFACT_ROOT}/${diagram.id}.html`) throw new Error('invalid diagram artifact');
      const graph=JSON.parse(fs.readFileSync(checkedFile(root,diagram.source),'utf8'));
      return `<a class="card diagram reading-entry" href="${diagram.id}.html" data-reading-kind="diagram" data-reading-search="${escapeHTML(`${diagram.id} ${graph.meta?.title || ''} ${diagram.summary || ''}`.toLowerCase())}"><div class="entry-copy"><span class="eyebrow">${escapeHTML(diagram.id)}</span><h3>${escapeHTML(graph.meta?.title || diagram.id)}</h3><p>${escapeHTML(diagram.summary || '')}</p></div><span class="entry-arrow" aria-hidden="true">↗</span></a>`;
    }).join('')}</div></section>`;
  }).join('');
  const moduleEntries=map.reading ? map.reading.modules : map.groups.map(group=>({id:group.id,group:group.id,title:group.id}));
  if(!Array.isArray(moduleEntries) || !moduleEntries.length || new Set(moduleEntries.map(module=>module.id)).size!==moduleEntries.length || map.groups.some(group=>!moduleEntries.some(module=>module.group===group.id))) throw new Error('missing or duplicate reading module');
  const modules=moduleEntries.map(module=>{
    if(!/^[a-z0-9-]+$/.test(module.id)) throw new Error('invalid module ID');
    const group=map.groups.find(item=>item.id===module.group);
    if(!group) throw new Error('unknown reading group');
    if(module.category && !categories.includes(module.category)) throw new Error('unknown module API category');
    const links=(values,options={})=>values.map(file=>{
      if(!fs.existsSync(checkedFile(root,file.replace(/\/$/,'')))) throw new Error('reading reference missing');
      return repositoryLink(map,file,options);
    }).join(' · ');
    const diagrams=(module.diagrams || group.diagrams).map(id=>{
      const diagram=map.diagrams.find(item=>item.id===id);
      if(!diagram) throw new Error('unknown module view');
      return `<a href="${escapeHTML(id)}.html">${escapeHTML(id)}</a>`;
    }).join(' · ');
    const searchText=[module.id,module.title,module.summary || '',module.category || '',...(module.documents || group.documents),...(module.sources || group.sources),...(module.tests || group.tests)].join(' ').toLowerCase();
    return `<article id="module-${module.id}" class="module reading-entry" data-reading-kind="module" data-reading-search="${escapeHTML(searchText)}"><h3>${escapeHTML(module.title)}</h3><p>${escapeHTML(module.summary || '')}</p><dl class="module-resources"><div><dt>图与流程</dt><dd>${diagrams}</dd></div><div><dt>权威说明</dt><dd>${links(module.documents || group.documents,{compact:true})}</dd></div><div><dt>API</dt><dd><a href="api-atlas.html?category=${encodeURIComponent(module.category || '')}">${escapeHTML(module.category || '全部领域')}</a></dd></div></dl><details id="module-${module.id}-code"><summary>源码与测试位置</summary><dl class="source-list"><dt>主要源码</dt><dd>${links(module.sources || group.sources)}</dd><dt>主要测试</dt><dd>${links(module.tests || group.tests)}</dd></dl></details></article>`;
  }).join('');
  const nav=levels.map((level,index)=>`<a href="#${escapeHTML(level.id)}" data-reading-link><span>${String(index+1).padStart(2,'0')}</span>${escapeHTML(level.title)}</a>`).join('')+'<a href="#modules" data-reading-link><span>'+String(levels.length+1).padStart(2,'0')+'</span>模块阅读入口</a>';
  const index=`<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Research Web 当前架构</title><style>${READING_CSS}</style></head><body><div class="shell" id="top"><aside class="sidebar"><a class="brand" href="#top">${readingBrand(root)}<span>Research<br>Workbench</span></a><div class="sidebar-label">架构阅读目录</div><nav class="toc" aria-label="架构阅读目录">${nav}</nav><div class="sidebar-foot">先理解边界，再查看实现。<a href="api-atlas.html">打开 API Atlas ↗</a><a href="/">返回 Research Web</a></div></aside><div class="workspace"><header class="topbar"><div class="crumb">架构文档 / <strong>阅读起点</strong></div><div class="page-tools"><label>主题<select id="architecture-theme" disabled><option value="auto">跟随系统</option><option value="light">浅色</option><option value="dark">深色</option></select></label><label>阅读密度<select id="architecture-density" disabled><option value="comfortable">舒适</option><option value="compact">紧凑</option></select></label></div></header><main><details class="mobile-nav"><summary>阅读目录</summary><nav aria-label="移动阅读目录">${nav}</nav></details><div class="intro"><span class="eyebrow">Research Web · 当前架构</span><h1>从研究问题，到真实文件交付</h1><p>先理解产品边界，再看部署、子系统和关键流程，最后进入 API 与代码。旧量化、旧 API、桌面与 merged-platform 保留历史身份。</p><div class="intro-actions"><a class="primary-link" href="#${escapeHTML(levels[0].id)}">从总览开始 <span aria-hidden="true">↓</span></a><span class="stat-line"><b>${map.diagrams.length}</b> 张图 · <b>${moduleEntries.length}</b> 个模块 · <a href="api-atlas.html">${uniqueOperations} 个唯一接口 / ${apis.length} 项源码声明</a></span></div><label class="search"><input id="architecture-search" type="search" placeholder="查找图、模块、源码或 API 领域" aria-label="查找图与模块" disabled><kbd aria-hidden="true">⌘ K</kbd></label><p id="reading-status" class="reading-hint" role="status" aria-live="polite">可查找图名、模块职责、源码路径与 API 领域。</p><noscript><p class="notice">搜索与主题控件需要 JavaScript；图册、目录和全部模块链接仍可直接阅读。</p></noscript><p id="reading-error" class="notice" role="alert" hidden>交互初始化失败，可以继续使用图册与模块链接。</p></div>${diagramCards}<section id="modules" class="reading-section"><div class="section-heading"><h2>模块阅读入口</h2><span class="section-count">${moduleEntries.length} 个模块</span></div><nav class="module-jump" aria-label="模块目录">${moduleEntries.map(module=>`<a href="#module-${escapeHTML(module.id)}">${escapeHTML(module.title)}</a>`).join('')}</nav><div class="module-list">${modules}</div></section><div id="reading-empty" class="empty" hidden><p>没有找到匹配的图或模块，请换一个关键词。</p><button type="button" id="reading-clear">清除搜索</button></div><footer class="notes"><p>唯一接口按 Method + Path 去重；声明保留不同源码位置。首页与 Atlas 均收录完整清单，领域筛选仅改变当前可见条目。</p><p>当前权威入口：${repositoryLink(map,map.canonicalEntry)}。仓库链接固定到被说明的源码提交 <code>${escapeHTML(map.reading?.repository?.revision || 'fixture')}</code>；生成物的最终交付提交另记于任务回执。真实模型、数据源与平台验收分别记录。</p></footer></main></div></div><script>${READING_SCRIPT}</script></body></html>`;
  return {artifacts:{[`${ARTIFACT_ROOT}/api-atlas.html`]:html,[`${ARTIFACT_ROOT}/index.html`]:index},apiDeclarationCount:apis.length,uniqueOperationCount:uniqueOperations,categoryCount:categories.length};
}

export function checkGeneratedArtifacts(root) {
  const {artifacts}=renderArtifacts(root);
  return Object.entries(artifacts).flatMap(([file,content])=>{
    const resolved=checkedFile(root,file);
    return fs.existsSync(resolved) && fs.readFileSync(resolved,'utf8')===content ? [] : [{code:'generated_artifact_stale',path:file,message:'Missing or stale generated page; run node scripts/build_research_web_api_atlas.mjs'}];
  });
}

function main(args) {
  const check=args.includes('--check');
  const positional=args.filter(value=>value!=='--check');
  if(positional.length>1 || positional.some(value=>value.startsWith('--'))) throw new Error('usage: build_research_web_api_atlas.mjs [project] [--check]');
  const root=fs.realpathSync(path.resolve(positional[0] || process.cwd()));
  if(check) {
    const violations=checkGeneratedArtifacts(root);
    console.log(JSON.stringify({ok:!violations.length,violations}));
    if(violations.length) process.exitCode=1;
    return;
  }
  const {artifacts,...counts}=renderArtifacts(root);
  const outputPaths=Object.fromEntries(Object.keys(artifacts).map(file=>[file,checkedFile(root,file)]));
  const logPath=checkedFile(root,'logs/research-api-atlas.jsonl');
  for(const [file,content] of Object.entries(artifacts)) {
    const outputPath=outputPaths[file];
    fs.mkdirSync(path.dirname(outputPath),{recursive:true});
    fs.writeFileSync(outputPath,content,{encoding:'utf8',mode:0o644});
  }
  fs.mkdirSync(path.dirname(logPath),{recursive:true});
  fs.appendFileSync(logPath,JSON.stringify({timestamp:new Date().toISOString(),event:'research_api_atlas_built',...counts})+'\n',{encoding:'utf8',mode:0o600});
  console.log(JSON.stringify({ok:true,outputs:Object.keys(artifacts),...counts}));
}

if(process.argv[1] && path.resolve(process.argv[1])===fileURLToPath(import.meta.url)) {
  try {main(process.argv.slice(2));}
  catch(error) {console.error(`Architecture pages build failed: ${error.message}`);process.exitCode=1;}
}
