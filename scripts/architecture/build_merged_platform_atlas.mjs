import { mkdir, readFile, readdir, rename, rm, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const schemaVersion = 'merged-platform-blueprint-v1';
const factEnvelopeFields = [
  'as_of',
  'observed_at',
  'available_at',
  'source_refs',
  'freshness_status',
  'quality_flags',
];

const requiredInterfaceFields = [
  'id',
  'domain',
  'method',
  'path',
  'request_model',
  'response_model',
  'response_kind',
  'success_statuses',
  'errors',
  'idempotency',
  'service_id',
  'read_data_owner_ids',
  'write_data_owner_ids',
  'event_ids',
  'security',
  'fact_envelope_fields',
];

const escapeHtml = (value) =>
  String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');

const unique = (values) => new Set(values).size === values.length;

const log = (level, phase, details = {}) => {
  process.stdout.write(
    `${JSON.stringify({
      at: new Date().toISOString(),
      level,
      phase,
      ...details,
    })}\n`,
  );
};

export async function loadAllCatalogs(catalogDir) {
  const load = async (name) => {
    const inputPath = path.join(catalogDir, name);
    try {
      return JSON.parse(await readFile(inputPath, 'utf8'));
    } catch (error) {
      const wrapped = new Error(
        `catalog-read failed for ${inputPath}: ${error.message}`,
        { cause: error },
      );
      wrapped.phase = 'catalog-read';
      wrapped.inputPath = inputPath;
      throw wrapped;
    }
  };

  const [capabilities, atlas, traceability] = await Promise.all([
    load('capabilities.json'),
    load('api-atlas.json'),
    load('traceability.json'),
  ]);
  return { capabilities, atlas, traceability };
}

export function validateCatalogs({ capabilities, atlas, traceability }) {
  const errors = [];
  for (const [name, catalog] of Object.entries({
    capabilities,
    atlas,
    traceability,
  })) {
    if (catalog?.schema_version !== schemaVersion) {
      errors.push(`${name}: unsupported schema_version`);
    }
  }

  const capabilitiesList = capabilities?.capabilities ?? [];
  const pages = capabilities?.pages ?? [];
  const interfaces = atlas?.interfaces ?? [];
  const services = traceability?.services ?? [];
  const dataOwners = traceability?.data_owners ?? [];
  const events = traceability?.events ?? [];
  const traces = traceability?.traces ?? [];
  const allIds = [
    ...capabilitiesList,
    ...pages,
    ...interfaces,
    ...services,
    ...dataOwners,
    ...events,
  ].map((item) => item.id);
  if (!unique(allIds)) errors.push('catalog identifiers must be globally unique');

  const pageIds = new Set(pages.map((item) => item.id));
  const apiIds = new Set(interfaces.map((item) => item.id));
  const serviceIds = new Set(services.map((item) => item.id));
  const dataOwnerIds = new Set(dataOwners.map((item) => item.id));
  const eventIds = new Set(events.map((item) => item.id));
  const capabilityIds = new Set(capabilitiesList.map((item) => item.id));
  const traceByCapability = new Map(
    traces.map((item) => [item.capability_id, item]),
  );

  for (const capability of capabilitiesList) {
    const trace = traceByCapability.get(capability.id);
    if (!trace) {
      errors.push(`${capability.id}: missing implementation trace`);
      continue;
    }
    if (capability.decision === 'remove') {
      if (!trace.replacement_capability_ids?.length) {
        errors.push(`${capability.id}: removed capability needs a replacement`);
      }
      for (const replacementId of trace.replacement_capability_ids ?? []) {
        if (!capabilityIds.has(replacementId)) {
          errors.push(`${capability.id}: unknown replacement ${replacementId}`);
        }
      }
    } else if (!trace.local_interaction && !trace.api_ids?.length) {
      errors.push(`${capability.id}: active capability has no API trace`);
    }
  }

  for (const trace of traces) {
    for (const [key, values, known] of [
      ['page', trace.page_ids, pageIds],
      ['API', trace.api_ids, apiIds],
      ['service', trace.service_ids, serviceIds],
      ['data owner', trace.data_owner_ids, dataOwnerIds],
      ['event', trace.event_ids, eventIds],
    ]) {
      for (const id of values ?? []) {
        if (!known.has(id)) errors.push(`${trace.capability_id}: unknown ${key} ${id}`);
      }
    }
  }

  const endpointKeys = interfaces.map((item) => `${item.method} ${item.path}`);
  if (!unique(endpointKeys)) errors.push('method/path pairs must be unique');
  for (const api of interfaces) {
    for (const field of requiredInterfaceFields) {
      if (!(field in api)) errors.push(`${api.id}: missing ${field}`);
    }
    if (!serviceIds.has(api.service_id)) {
      errors.push(`${api.id}: unknown service ${api.service_id}`);
    }
    for (const ownerId of [
      ...(api.read_data_owner_ids ?? []),
      ...(api.write_data_owner_ids ?? []),
    ]) {
      if (!dataOwnerIds.has(ownerId)) {
        errors.push(`${api.id}: unknown data owner ${ownerId}`);
      }
    }
    for (const eventId of api.event_ids ?? []) {
      if (!eventIds.has(eventId)) errors.push(`${api.id}: unknown event ${eventId}`);
    }
    if (api.method !== 'GET' && api.idempotency?.required !== true) {
      errors.push(`${api.id}: write API must require idempotency`);
    }
    if (
      api.response_kind === 'fact' &&
      JSON.stringify(api.fact_envelope_fields) !== JSON.stringify(factEnvelopeFields)
    ) {
      errors.push(`${api.id}: invalid fact envelope`);
    }
    if (api.response_kind === 'event-stream') {
      for (const field of [
        'last_event_id',
        'heartbeat_seconds',
        'reconnect_delay_ms',
        'terminal_events',
        'replay_boundary',
      ]) {
        if (!(field in (api.sse ?? {}))) errors.push(`${api.id}: missing SSE ${field}`);
      }
    }
  }
  return errors;
}

const renderTag = (text, kind = '') =>
  `<span class="tag ${escapeHtml(kind)}">${escapeHtml(text)}</span>`;

export function renderApiAtlas({ capabilities, atlas, traceability }) {
  const traceByApi = new Map();
  for (const trace of traceability.traces) {
    for (const apiId of trace.api_ids ?? []) {
      const current = traceByApi.get(apiId) ?? [];
      current.push(trace.capability_id);
      traceByApi.set(apiId, current);
    }
  }
  const domains = [...new Set(atlas.interfaces.map((item) => item.domain))].sort();
  const methods = [...new Set(atlas.interfaces.map((item) => item.method))].sort();
  const cards = atlas.interfaces
    .map((api) => {
      const capabilitiesForApi = traceByApi.get(api.id) ?? [];
      const owners = [...api.read_data_owner_ids, ...api.write_data_owner_ids];
      return `<article class="api-card" id="${escapeHtml(api.id)}" data-domain="${escapeHtml(api.domain)}" data-method="${escapeHtml(api.method)}" data-search="${escapeHtml(`${api.id} ${api.path} ${api.request_model} ${api.response_model}`.toLowerCase())}">
  <div class="api-head"><span class="method method-${api.method.toLowerCase()}">${escapeHtml(api.method)}</span><code>${escapeHtml(api.path)}</code><a href="#${escapeHtml(api.id)}">${escapeHtml(api.id)}</a></div>
  <div class="api-grid">
    <dl><dt>请求</dt><dd>${escapeHtml(api.request_model)}</dd><dt>响应</dt><dd>${escapeHtml(api.response_model)} · ${escapeHtml(api.response_kind)}</dd><dt>成功</dt><dd>${api.success_statuses.map(escapeHtml).join(', ')}</dd></dl>
    <dl><dt>Owner</dt><dd>${escapeHtml(api.service_id)}</dd><dt>数据</dt><dd>${owners.length ? owners.map((id) => renderTag(id)).join('') : '只读/无写入'}</dd><dt>幂等</dt><dd>${escapeHtml(api.idempotency.mode)}</dd></dl>
  </div>
  <div class="trace-row">${capabilitiesForApi.map((id) => `<a class="tag trace" href="#cap-${escapeHtml(id)}">${escapeHtml(id)}</a>`).join('')}${api.event_ids.map((id) => renderTag(id, 'event')).join('')}</div>
  <details><summary>错误、安全与完整契约</summary><pre>${escapeHtml(JSON.stringify({ errors: api.errors, security: api.security, fact_envelope_fields: api.fact_envelope_fields, sse: api.sse ?? null }, null, 2))}</pre></details>
</article>`;
    })
    .join('\n');
  const capabilityIndex = capabilities.capabilities
    .map(
      (capability) =>
        `<span id="cap-${escapeHtml(capability.id)}" class="capability ${escapeHtml(capability.decision)}">${escapeHtml(capability.id)} · ${escapeHtml(capability.name)} · ${escapeHtml(capability.decision)}</span>`,
    )
    .join('');
  const embedded = JSON.stringify({ capabilities, atlas, traceability }).replaceAll(
    '<',
    '\\u003c',
  );
  return `<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>AlphaFoundry API Atlas</title>
<style>
:root{--navy:#061b2e;--blue:#2864dc;--gold:#c99737;--ink:#19212f;--muted:#69758a;--line:#dce3ee;--canvas:#f5f7fb;--surface:#fff;--green:#16866b;--red:#d94b45}*{box-sizing:border-box}body{margin:0;background:var(--canvas);color:var(--ink);font:14px/1.5 Inter,ui-sans-serif,system-ui,-apple-system,"PingFang SC",sans-serif}.top{background:var(--navy);color:#fff;padding:28px clamp(20px,4vw,64px)}.top h1{margin:0 0 6px;font-size:clamp(24px,3vw,38px)}.top p{margin:0;color:#b9c8db}.shell{max-width:1500px;margin:auto;padding:24px}.summary{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin-top:-42px}.metric{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:18px;box-shadow:0 8px 24px #061b2e12}.metric b{display:block;font-size:26px}.toolbar{position:sticky;top:0;z-index:4;display:flex;gap:10px;align-items:center;margin:20px 0;padding:12px;background:#f5f7fbeb;backdrop-filter:blur(12px)}select,input{border:1px solid var(--line);border-radius:9px;background:#fff;padding:10px 12px;color:var(--ink)}input{flex:1}.capabilities{display:flex;gap:6px;flex-wrap:wrap;margin:16px 0}.capability,.tag{display:inline-flex;border-radius:999px;background:#edf3ff;color:#2355ad;padding:3px 8px;margin:2px;font-size:12px}.capability.remove{background:#fff0ee;color:#a63e37}.capability.merge{background:#edf8f4;color:#116c55}.api-list{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.api-card{background:#fff;border:1px solid var(--line);border-radius:14px;padding:16px;scroll-margin-top:90px}.api-head{display:flex;gap:10px;align-items:center;flex-wrap:wrap}.api-head code{font-size:14px;word-break:break-all}.api-head a{margin-left:auto;color:var(--blue);text-decoration:none}.method{font-weight:800;border-radius:6px;padding:4px 7px}.method-get{background:#e9f7f2;color:var(--green)}.method-post{background:#edf3ff;color:var(--blue)}.method-patch{background:#fff6dc;color:#8a650f}.method-delete{background:#fff0ee;color:var(--red)}.api-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin:14px 0}.api-grid dl{margin:0}.api-grid dt{color:var(--muted);font-size:12px}.api-grid dd{margin:0 0 8px}.trace-row{border-top:1px solid var(--line);padding-top:10px}.tag.event{background:#fff6dc;color:#7b5b12}.tag.trace{text-decoration:none}details{margin-top:10px}summary{cursor:pointer;color:var(--blue)}pre{white-space:pre-wrap;overflow:auto;background:#0d2236;color:#d9e6f5;border-radius:8px;padding:12px;font-size:11px}.empty{display:none;padding:48px;text-align:center;color:var(--muted)}@media(max-width:900px){.summary{grid-template-columns:repeat(2,1fr)}.api-list{grid-template-columns:1fr}}@media(max-width:560px){.shell{padding:14px}.summary{grid-template-columns:1fr;margin-top:-24px}.toolbar{flex-wrap:wrap}.toolbar input{flex-basis:100%}.api-grid{grid-template-columns:1fr}}
</style></head><body>
<header class="top"><h1>AlphaFoundry × LSH API Atlas</h1><p>从产品能力追踪到 HTTP/SSE、Service、数据 Owner、事件和异常语义。</p></header>
<main class="shell"><section class="summary"><div class="metric"><b>${capabilities.capabilities.length}</b>产品能力</div><div class="metric"><b>${capabilities.pages.length}</b>核心页面</div><div class="metric"><b>${atlas.interfaces.length}</b>接口方法</div><div class="metric"><b>${traceability.events.length}</b>领域事件</div></section>
<section class="toolbar" aria-label="接口筛选"><select data-filter="domain" aria-label="领域"><option value="">全部领域</option>${domains.map((domain) => `<option>${escapeHtml(domain)}</option>`).join('')}</select><select data-filter="method" aria-label="方法"><option value="">全部方法</option>${methods.map((method) => `<option>${escapeHtml(method)}</option>`).join('')}</select><input type="search" data-filter="search" placeholder="搜索 API、路径或模型" aria-label="搜索接口"></section>
<section class="capabilities" aria-label="能力索引">${capabilityIndex}</section><section class="api-list">${cards}</section><p class="empty">没有符合筛选条件的接口。</p></main>
<script type="application/json" id="atlas-data">${embedded}</script><script>
const domain=document.querySelector('[data-filter="domain"]');const method=document.querySelector('[data-filter="method"]');const search=document.querySelector('[data-filter="search"]');const cards=[...document.querySelectorAll('.api-card')];const empty=document.querySelector('.empty');function filter(){const q=search.value.trim().toLowerCase();let count=0;for(const card of cards){const show=(!domain.value||card.dataset.domain===domain.value)&&(!method.value||card.dataset.method===method.value)&&(!q||card.dataset.search.includes(q));card.hidden=!show;if(show)count+=1}empty.style.display=count?'none':'block'}for(const control of [domain,method,search])control.addEventListener('input',filter);
</script></body></html>`;
}

export function renderBlueprintIndex({ diagramGroups = [], atlasPath = 'api-atlas.html' }) {
  const groups = diagramGroups.length
    ? diagramGroups
        .map(
          (group) =>
            `<section><h2>${escapeHtml(group.name)}</h2><div class="links">${group.items.map((item) => `<a href="${escapeHtml(item.href)}">${escapeHtml(item.label)}</a>`).join('')}</div></section>`,
        )
        .join('')
    : '<section><h2>详细图</h2><p>图源将在后续架构任务中生成并自动加入本索引。</p></section>';
  return `<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>AlphaFoundry 详细蓝图</title><style>body{margin:0;background:#f5f7fb;color:#19212f;font:15px/1.6 system-ui,-apple-system,"PingFang SC",sans-serif}header{padding:44px clamp(20px,6vw,80px);background:#061b2e;color:white}main{max-width:1200px;margin:auto;padding:28px}.hero{display:block;background:#2864dc;color:white;text-decoration:none;padding:22px;border-radius:14px;font-size:20px;font-weight:700}.links{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:10px}.links a{background:white;border:1px solid #dce3ee;border-radius:10px;padding:14px;color:#2355ad;text-decoration:none}</style></head><body><header><h1>AlphaFoundry × LSH 详细实施蓝图</h1><p>产品功能、接口、服务、数据与状态的双向追踪入口。</p></header><main><a class="hero" href="${escapeHtml(atlasPath)}">打开 API Atlas</a>${groups}</main></body></html>`;
}

async function atomicWrite(outputPath, content) {
  const temporaryPath = `${outputPath}.${process.pid}.${Date.now()}.tmp`;
  try {
    await writeFile(temporaryPath, content, 'utf8');
    await rename(temporaryPath, outputPath);
  } catch (error) {
    await rm(temporaryPath, { force: true });
    throw new Error(`atomic-write failed for ${outputPath}: ${error.message}`, {
      cause: error,
    });
  }
}

async function discoverDiagramGroups(outputDir) {
  const diagramDir = path.join(outputDir, 'diagrams');
  let names = [];
  try {
    names = (await readdir(diagramDir)).filter((name) => name.endsWith('.html'));
  } catch (error) {
    if (error.code !== 'ENOENT') throw error;
  }
  const groupNames = [
    ['Shared', /^A/],
    ['Market', /^D01/],
    ['Theme', /^D02/],
    ['Asset', /^D03/],
    ['FinGPT', /^D04/],
    ['Claw', /^D05/],
    ['Platform Core', /^D06/],
  ];
  return groupNames
    .map(([name, pattern]) => ({
      name,
      items: names
        .filter((fileName) => pattern.test(fileName))
        .sort()
        .map((fileName) => ({
          label: fileName.replace(/\.html$/, ''),
          href: `diagrams/${fileName}`,
        })),
    }))
    .filter((group) => group.items.length);
}

function parseArgs(argv) {
  const result = {};
  for (let index = 0; index < argv.length; index += 2) {
    const key = argv[index];
    const value = argv[index + 1];
    if (!key?.startsWith('--') || !value) {
      throw new Error(`invalid CLI arguments near ${key ?? '<end>'}`);
    }
    result[key.slice(2)] = value;
  }
  if (!result['catalog-dir'] || !result['output-dir']) {
    throw new Error('required arguments: --catalog-dir and --output-dir');
  }
  return result;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const catalogDir = path.resolve(args['catalog-dir']);
  const outputDir = path.resolve(args['output-dir']);
  log('info', 'catalog-read', { catalog_dir: catalogDir });
  const catalogs = await loadAllCatalogs(catalogDir);
  const errors = validateCatalogs(catalogs);
  if (errors.length) {
    for (const message of errors) log('error', 'catalog-validate', { message });
    throw new Error(`catalog validation failed with ${errors.length} error(s)`);
  }
  await mkdir(outputDir, { recursive: true });
  const diagramGroups = await discoverDiagramGroups(outputDir);
  await atomicWrite(path.join(outputDir, 'api-atlas.html'), renderApiAtlas(catalogs));
  await atomicWrite(
    path.join(outputDir, 'index.html'),
    renderBlueprintIndex({ diagramGroups, atlasPath: 'api-atlas.html' }),
  );
  log('info', 'build-complete', {
    capabilities: catalogs.capabilities.capabilities.length,
    pages: catalogs.capabilities.pages.length,
    apis: catalogs.atlas.interfaces.length,
    traces: catalogs.traceability.traces.length,
    output_dir: outputDir,
  });
}

const isMain = process.argv[1]
  ? pathToFileURL(path.resolve(process.argv[1])).href === import.meta.url
  : false;
if (isMain) {
  main().catch((error) => {
    log('error', error.phase ?? 'build', {
      input_path: error.inputPath ?? null,
      message: error.message,
      cause: error.cause?.message ?? null,
    });
    process.exitCode = 1;
  });
}
