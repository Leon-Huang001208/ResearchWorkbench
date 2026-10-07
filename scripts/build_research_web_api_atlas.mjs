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

function repositoryLink(map, file) {
  const repository=map.reading?.repository;
  safePath(file.replace(/\/$/,''));
  if(!repository) return `<code>${escapeHTML(file)}</code>`;
  if(repository.url!=='https://github.com/Leon-Huang001208/ResearchWorkbench' || !/^[a-f0-9]{40}$/.test(repository.revision)) throw new Error('invalid architecture repository identity');
  return `<a href="${repository.url}/${file.endsWith('/')?'tree':'blob'}/${repository.revision}/${file.split('/').map(encodeURIComponent).join('/')}" rel="noopener noreferrer">${escapeHTML(file)}</a>`;
}

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
    return `<section id="${escapeHTML(level.id)}"><h2>${escapeHTML(level.title)}</h2><div class="grid">${diagrams.map(diagram=>{
      if(!/^[a-z0-9-]+$/.test(diagram.id) || diagram.artifact!==`${ARTIFACT_ROOT}/${diagram.id}.html`) throw new Error('invalid diagram artifact');
      const graph=JSON.parse(fs.readFileSync(checkedFile(root,diagram.source),'utf8'));
      return `<a class="card" href="${diagram.id}.html"><span>${escapeHTML(diagram.id)}</span><h3>${escapeHTML(graph.meta?.title || diagram.id)}</h3><p>${escapeHTML(diagram.summary || '')}</p></a>`;
    }).join('')}</div></section>`;
  }).join('');
  const moduleEntries=map.reading ? map.reading.modules : map.groups.map(group=>({id:group.id,group:group.id,title:group.id}));
  if(!Array.isArray(moduleEntries) || !moduleEntries.length || new Set(moduleEntries.map(module=>module.id)).size!==moduleEntries.length || map.groups.some(group=>!moduleEntries.some(module=>module.group===group.id))) throw new Error('missing or duplicate reading module');
  const modules=moduleEntries.map(module=>{
    if(!/^[a-z0-9-]+$/.test(module.id)) throw new Error('invalid module ID');
    const group=map.groups.find(item=>item.id===module.group);
    if(!group) throw new Error('unknown reading group');
    if(module.category && !categories.includes(module.category)) throw new Error('unknown module API category');
    const links=(values)=>values.map(file=>{
      if(!fs.existsSync(checkedFile(root,file.replace(/\/$/,'')))) throw new Error('reading reference missing');
      return repositoryLink(map,file);
    }).join(' · ');
    const diagrams=(module.diagrams || group.diagrams).map(id=>{
      const diagram=map.diagrams.find(item=>item.id===id);
      if(!diagram) throw new Error('unknown module view');
      return `<a href="${escapeHTML(id)}.html">${escapeHTML(id)}</a>`;
    }).join(' · ');
    return `<article id="module-${module.id}" class="module"><h3>${escapeHTML(module.title)}</h3><p>${escapeHTML(module.summary || '')}</p><dl><dt>图与流程</dt><dd>${diagrams}</dd><dt>权威说明</dt><dd>${links(module.documents || group.documents)}</dd><dt>API</dt><dd><a href="api-atlas.html?category=${encodeURIComponent(module.category || '')}">${escapeHTML(module.category || '全部领域')}</a></dd></dl><details><summary>源码与测试位置</summary><dl><dt>主要源码</dt><dd>${links(module.sources || group.sources)}</dd><dt>主要测试</dt><dd>${links(module.tests || group.tests)}</dd></dl></details><a href="#top">返回阅读起点 ↑</a></article>`;
  }).join('');
  const index=`<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Research Web 当前架构</title><style>
  :root{color-scheme:light dark;--paper:#f5f7fb;--card:#fff;--ink:#182337;--muted:#607087;--line:#dce4ee;--blue:#205cf2}*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.65 system-ui,-apple-system,"PingFang SC",sans-serif}header{background:#071d34;color:#fff;padding:24px}main{max-width:1180px;margin:auto;padding:28px 24px}a{color:var(--blue);overflow-wrap:anywhere}a:focus-visible{outline:3px solid var(--blue);outline-offset:3px}h1{font-size:30px}p,dt{color:var(--muted)}nav{display:flex;flex-wrap:wrap;gap:16px}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}.card,.module{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:20px}.card{display:block;color:inherit;text-decoration:none}.card:hover{border-color:var(--blue)}.card h3{margin:8px 0}.module{margin:16px 0}dd{margin:0 0 12px;overflow-wrap:anywhere}code{overflow-wrap:anywhere}@media(max-width:650px){.grid{grid-template-columns:1fr}}@media(prefers-color-scheme:dark){:root{--paper:#0b1524;--card:#142238;--ink:#e5edf8;--muted:#a8bbd2;--line:#2d4058;--blue:#87acff}}</style></head><body><header>Research Workbench / Research Web / 当前架构</header><main id="top"><h1>从研究问题，到真实文件交付</h1><p>先理解产品边界，再看部署、子系统和关键流程，最后进入 API 与代码。旧量化、旧 API、桌面与 merged-platform 保留历史身份。</p><nav aria-label="阅读层次">${levels.map(level=>`<a href="#${escapeHTML(level.id)}">${escapeHTML(level.title)}</a>`).join('')}<a href="#modules">模块阅读入口</a></nav><p><a href="api-atlas.html">打开当前 API Atlas（${uniqueOperations} 个唯一接口 / ${apis.length} 项源码声明）</a></p><p>唯一接口按 Method + Path 去重；声明保留不同源码位置。首页与 Atlas 均收录完整清单，领域筛选仅改变当前可见条目。</p>${diagramCards}<section id="modules"><h2>模块阅读入口</h2><nav>${(map.reading?.modules || map.groups.map(g=>({id:g.id,title:g.id}))).map(m=>`<a href="#module-${escapeHTML(m.id)}">${escapeHTML(m.title)}</a>`).join('')}</nav>${modules}</section><footer><p>当前权威入口：${repositoryLink(map,map.canonicalEntry)}。仓库链接固定到被说明的源码提交 <code>${escapeHTML(map.reading?.repository?.revision || 'fixture')}</code>；生成物的最终交付提交另记于任务回执。真实模型、数据源与平台验收分别记录。</p></footer></main></body></html>`;
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
