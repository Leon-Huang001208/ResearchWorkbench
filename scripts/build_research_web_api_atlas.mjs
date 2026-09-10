#!/usr/bin/env node
/** Build the current Research Web API atlas from the checked architecture inventory. */
import fs from 'node:fs';
import path from 'node:path';

const root = path.resolve(process.argv[2] || process.cwd());
const mapPath = path.join(root, 'docs/architecture/research-web/architecture-map.json');
const outputPath = path.join(root, 'outputs/research-web-architecture/api-atlas.html');
const logPath = path.join(root, 'logs/research-api-atlas.jsonl');
const escapeHTML = value => String(value).replace(/[&<>"']/g, character => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[character]));

function category(api) {
  const route = api.path;
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

function build() {
  const map = JSON.parse(fs.readFileSync(mapPath, 'utf8'));
  if (!Array.isArray(map.apis) || !map.apis.length) throw new Error('architecture API inventory is empty');
  const apis = [...map.apis].sort((left, right) => category(left).localeCompare(category(right), 'zh-CN') || left.path.localeCompare(right.path) || left.method.localeCompare(right.method));
  const uniqueOperations = new Set(apis.map(api => `${api.method} ${api.path}`)).size;
  const methodCounts = Object.fromEntries(['GET','POST','PUT','PATCH','DELETE'].map(method => [method, apis.filter(api => api.method === method).length]));
  const categories = [...new Set(apis.map(category))];
  const cards = apis.map(api => `<article class="api" data-category="${escapeHTML(category(api))}" data-search="${escapeHTML(`${api.method} ${api.path} ${api.source}`.toLowerCase())}"><div class="head"><span class="method ${api.method.toLowerCase()}">${escapeHTML(api.method)}</span><code>${escapeHTML(api.path)}</code></div><div class="meta"><span>${escapeHTML(category(api))}</span><code>${escapeHTML(api.source)}</code></div></article>`).join('');
  const html = `<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Research Workbench · API Atlas</title><style>
:root{color-scheme:light dark;--paper:#f5f7fb;--surface:#fff;--ink:#182337;--muted:#66758b;--line:#dce4ee;--blue:#205cf2;--green:#16866b;--amber:#9a6800}*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:14px/1.55 system-ui,-apple-system,"PingFang SC",sans-serif}header{background:#071d34;color:#fff;padding:28px max(20px,calc((100vw - 1320px)/2))}header h1{margin:0;font-size:30px}header p{margin:5px 0 0;color:#b9c9dc}main{max-width:1320px;margin:auto;padding:24px}.metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:18px}.metric,.api{background:var(--surface);border:1px solid var(--line);border-radius:12px}.metric{padding:15px}.metric b{display:block;font-size:23px}.toolbar{display:flex;gap:10px;position:sticky;top:0;z-index:2;padding:12px 0;background:color-mix(in srgb,var(--paper) 92%,transparent)}input,select{border:1px solid var(--line);border-radius:9px;background:var(--surface);color:var(--ink);padding:10px 12px}input{flex:1}.list{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.api{padding:14px}.head{display:flex;align-items:flex-start;gap:9px}.head code{font-size:13px;overflow-wrap:anywhere}.method{font-size:11px;font-weight:800;padding:3px 6px;border-radius:5px;flex:none}.get{background:#e8f7f1;color:var(--green)}.post{background:#eaf0ff;color:var(--blue)}.put,.patch{background:#fff4d7;color:var(--amber)}.delete{background:#ffecea;color:#ad342d}.meta{display:flex;justify-content:space-between;gap:8px;margin-top:11px;color:var(--muted);font-size:12px}.meta code{overflow-wrap:anywhere;text-align:right}.empty{display:none;text-align:center;padding:48px;color:var(--muted)}@media(max-width:800px){.metrics{grid-template-columns:repeat(2,1fr)}.list{grid-template-columns:1fr}.toolbar{flex-wrap:wrap}.toolbar input{flex-basis:100%}}@media(prefers-color-scheme:dark){:root{--paper:#0b1524;--surface:#142238;--ink:#e5edf8;--muted:#a8bbd2;--line:#2d4058;--blue:#87acff}.get{background:#173e35}.post{background:#1d315d}.put,.patch{background:#49391d}.delete{background:#4a2527}}</style></head><body><header><h1>Research Web API Atlas</h1><p>由 architecture-map.json 生成 · 当前源码声明 · 不包含旧 /api/research-runs 链路</p></header><main><section class="metrics"><div class="metric"><span>唯一接口</span><b>${uniqueOperations}</b></div><div class="metric"><span>源码声明</span><b>${apis.length}</b></div><div class="metric"><span>GET / POST</span><b>${methodCounts.GET} / ${methodCounts.POST}</b></div><div class="metric"><span>领域分组</span><b>${categories.length}</b></div></section><div class="toolbar"><input id="search" type="search" aria-label="搜索接口" placeholder="搜索 Method、路径或源码"><select id="category" aria-label="筛选领域"><option value="">全部领域</option>${categories.map(value => `<option>${escapeHTML(value)}</option>`).join('')}</select></div><section class="list" aria-live="polite">${cards}</section><p class="empty">没有匹配的接口。</p></main><script>(()=>{const search=document.querySelector('#search'),select=document.querySelector('#category'),cards=[...document.querySelectorAll('.api')],empty=document.querySelector('.empty');function filter(){const query=search.value.trim().toLowerCase(),kind=select.value;let visible=0;for(const card of cards){const show=(!query||card.dataset.search.includes(query))&&(!kind||card.dataset.category===kind);card.hidden=!show;if(show)visible+=1}empty.style.display=visible?'none':'block'}search.addEventListener('input',filter);select.addEventListener('change',filter)})();</script></body></html>`;
  fs.mkdirSync(path.dirname(outputPath), {recursive:true});
  fs.writeFileSync(outputPath, html, {encoding:'utf8',mode:0o644});
  fs.mkdirSync(path.dirname(logPath), {recursive:true});
  fs.appendFileSync(logPath, `${JSON.stringify({timestamp:new Date().toISOString(),event:'research_api_atlas_built',apiDeclarationCount:apis.length,uniqueOperationCount:uniqueOperations,categoryCount:categories.length})}\n`, {encoding:'utf8',mode:0o600});
  process.stdout.write(`${JSON.stringify({ok:true,output:path.relative(root,outputPath),apiDeclarationCount:apis.length,uniqueOperationCount:uniqueOperations,categoryCount:categories.length})}\n`);
}

try { build(); }
catch (error) {
  process.stderr.write(`API Atlas build failed: ${error instanceof Error ? error.message : String(error)}\n`);
  process.exitCode = 1;
}
