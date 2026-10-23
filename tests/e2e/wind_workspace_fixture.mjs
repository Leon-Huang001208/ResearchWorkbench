/** Isolated snapshot-only browser fixture. It never contacts a supplier/model. */
import assert from 'node:assert/strict';
import http from 'node:http';
import path from 'node:path';
import { readFile, writeFile, appendFile, mkdir } from 'node:fs/promises';
import { createHash, randomUUID } from 'node:crypto';

const sourceFiles = ['index.html', 'app.mjs', 'core.mjs', 'asset-workspace.mjs', 'asset-workspace.css', 'asset-layout.css', 'asset-controller.mjs', 'asset-chart.mjs', 'asset-chips.mjs', 'asset-chip-panel.mjs', 'asset-chart.css', 'asset-indicators.mjs', 'asset-format.mjs', 'asset-projection.mjs', 'asset-search.mjs', 'asset-news.mjs', 'asset-navigation.mjs', 'styles.css', 'vendor/echarts-5.5.0.min.js', 'vendor/chart-4.4.7.umd.js'];
const clone = value => structuredClone(value);
const mime = { '.html': 'text/html', '.mjs': 'text/javascript', '.js': 'text/javascript', '.json': 'application/json', '.css': 'text/css', '.svg': 'image/svg+xml', '.png': 'image/png', '.woff2': 'font/woff2' };
// Preview-container restrictions only. Product files and their hashes stay intact.
const previewControls = `const restriction='隔离预览只回读冻结快照；研究提交、供应商刷新和业务写入已禁用。';
const forms='form[data-asset-observation],form[data-asset-note],form[data-asset-alert],form[data-asset-watchlist-create]';
const apply=()=>{const buttons=[...document.querySelectorAll('[data-workbench-handoff],[data-asset-block-refresh],[data-watchlist-item],[data-send],[data-submit]'),...[...document.querySelectorAll(forms)].flatMap(form=>[...form.querySelectorAll('button:not([type="button"]),input[type="submit"]')])];for(const button of buttons){button.disabled=true;button.title=restriction;button.setAttribute('aria-disabled','true');button.dataset.previewReadOnly='true';}};
new MutationObserver(apply).observe(document.documentElement,{childList:true,subtree:true});apply();document.addEventListener('submit',event=>{if(event.target.matches(forms)){event.preventDefault();event.stopImmediatePropagation();}},true);`;

export async function startWindFixture(project, output, { port = 0, proofPath = process.env.RWB_WIND_PROOF, partialProofPath = process.env.RWB_WIND_PARTIAL_PROOF } = {}) {
  await mkdir(output, { recursive: true });
  const ui = path.join(project, 'app/research_web/ui');
  const hashes = Object.fromEntries(await Promise.all(sourceFiles.map(async name => [name, createHash('sha256').update(await readFile(path.join(ui, name))).digest('hex')])));
  const proof = proofPath ? JSON.parse(await readFile(proofPath, 'utf8')) : null;
  const partialProof = partialProofPath ? JSON.parse(await readFile(partialProofPath, 'utf8')) : null;
  assert.ok(proof?.observations?.length && proof?.rowsByDataset, 'RWB_WIND_PROOF must contain actual exported observations and rowsByDataset');
  const versions = clone(proof.versions || proof.observations.map(observation => ({ asset: observation.asset, adjustment: observation.blocks.history.dataset.asset_history.adjustment, observation })));
  const rows = clone({ ...proof.rowsByDataset, ...(partialProof?.rowsByDataset || {}) });
  const current = new Map();
  for (const version of versions) {
    const existing = current.get(version.asset);
    if (!existing || version.adjustment === 'qfq') current.set(version.asset, clone(version.observation));
  }
  const state = { current, versions, partialVersions: clone(partialProof?.versions || []), partialProvenance: partialProof?.provenance, partialProofPath, usePartialForRecent: false, rows, reads: [], historyRequests: [], errors: [], jobs: new Map(), preferences: ['volume', 'macd'], preferenceWrites: [], proofPath, hashes, readDelay: 0, jobPolls: 0 };
  const publicObservation = observation => {
    const value = clone(observation);
    for (const block of Object.values(value.blocks || {})) if (block.dataset) block.dataset.limitations = [...(block.dataset.limitations || []), '冻结快照、非实时行情；隔离预览只回读已保存数据，不查询供应商或模型。'];
    return value;
  };
  const byId = id => [...current.values()].find(observation => observation.id === id);
  const finishJob = job => {
    const observation = byId(job.observation_id);
    const available = state.usePartialForRecent && job.scope === 'recent' ? state.partialVersions : versions;
    const version = available.find(item => item.asset === observation?.asset && item.adjustment === job.adjustment);
    assert.ok(version, 'No real frozen snapshot for requested adjustment');
    const next = clone(version.observation);
    next.id = observation.id;
    next.session_id = observation.session_id;
    current.set(next.asset, next);
    job.state = job.status = 'completed';
    job.progress = { chunks_completed: 1, chunks_total: 1, rows: next.blocks.history.dataset.row_count };
    job.current_dataset = clone(next.blocks.history.dataset);
    next.history_job = clone(job);
    return job;
  };
  const server = http.createServer(async (request, response) => {
    try {
      const url = new URL(request.url, 'http://127.0.0.1');
      state.reads.push({ method: request.method, path: url.pathname, search: url.search });
      const send = (data, status = 200, type = 'application/json') => { response.writeHead(status, { 'Content-Type': `${type}; charset=utf-8` }); response.end(typeof data === 'string' || Buffer.isBuffer(data) ? data : JSON.stringify(data)); };
      response.setHeader('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; object-src 'none'");
      response.setHeader('X-RWB-Isolated-Preview', 'Frozen snapshots only; no supplier/model calls');
      if (url.pathname === '/preview-controls.mjs') return send(previewControls, 200, 'text/javascript');
      if (url.pathname === '/favicon.ico') { response.writeHead(204); response.end(); return; }
      if (url.pathname.startsWith('/api/research/')) {
        const preferencesRoute = url.pathname === '/api/research/assets/chart-preferences';
        const blockLoadMatch = url.pathname.match(/^\/api\/research\/assets\/observations\/([^/]+)\/blocks\/([^/]+)\/load$/);
        const createObservation = request.method === 'POST' && url.pathname.endsWith('/assets/observations');
        const jobMatch = url.pathname.match(/^\/api\/research\/assets\/observations\/([^/]+)\/history-jobs(?:\/([^/]+))?(\/cancel)?$/);
        const simulatedWrite = request.method === 'PUT' && preferencesRoute || request.method === 'POST' && jobMatch && (!jobMatch[2] || jobMatch[3]) || request.method === 'POST' && blockLoadMatch || createObservation;
        if (request.method !== 'GET' && !simulatedWrite) return send({ code: 'isolated_preview_read_only', error: '隔离预览禁用研究提交、刷新供应商和持久业务写入。' }, 403);
        if (request.method === 'GET' && jobMatch?.[3]) return send({ code: 'method_not_allowed', error: '取消模拟任务须使用 POST。' }, 405);
        let body = '';
        if (['POST', 'PUT'].includes(request.method)) { for await (const chunk of request) body += chunk; body = body ? JSON.parse(body) : {}; }
        if (url.pathname.endsWith('/assets/search')) {
          const query = String(url.searchParams.get('q') || '').normalize('NFKC').trim().toLowerCase();
          const limit = Math.max(1, Math.min(50, Number(url.searchParams.get('limit')) || 20));
          const directory = proof.directory || [...current.values()].map(observation => ({ asset: observation.asset, code: observation.asset.split('.')[0], exchange: observation.asset.split('.')[1], asset_type: 'stock', name: (rows[observation.blocks.overview?.dataset?.dataset_id] || [])[0]?.name || observation.asset, pinyin_abbr: '' }));
          const scored = directory.map(item => ({ item, rank: item.code === query || item.asset.toLowerCase() === query ? 0 : item.name.includes(query) ? 1 : item.code.startsWith(query) ? 2 : item.pinyin_abbr?.startsWith(query) ? 3 : item.asset.toLowerCase().includes(query) || item.pinyin_abbr?.includes(query) ? 4 : 9 })).filter(value => value.rank < 9).sort((a, b) => a.rank - b.rank || a.item.asset.localeCompare(b.item.asset));
          return send({ status: 'ready', items: scored.slice(0, limit).map(value => value.item), total_count: directory.length, provider: 'frozen-directory', as_of: proof.directory_as_of, limitations: ['冻结目录；选择无快照证券时只提示缺口，不查询供应商。'] });
        }
        if (createObservation) {
          const observation = current.get(String(body.asset || '').toUpperCase());
          return observation ? send(publicObservation(observation), 202) : send({ detail: { code: 'preview_snapshot_missing', message: '隔离预览未保存该资产快照；不会查询供应商。' } }, 409);
        }
        if (blockLoadMatch) {
          const observation = byId(blockLoadMatch[1]);
          if (!observation) return send({ detail: { code: 'preview_snapshot_missing', message: '隔离预览没有这份观察快照。' } }, 404);
          if (!observation.blocks[blockLoadMatch[2]]) observation.blocks[blockLoadMatch[2]] = { status: 'unavailable', failure_code: 'preview_snapshot_missing', dataset: null };
          return send(publicObservation(observation), 202);
        }
        if (preferencesRoute) {
          if (request.method === 'PUT') {
            if (!Array.isArray(body.panels) || body.panels.length > 4 || new Set(body.panels).size !== body.panels.length || body.panels.some(id => !['volume', 'macd', 'kdj', 'rsi'].includes(id))) return send({ code: 'preview_preferences_invalid' }, 400);
            state.chipSettings = body.chip_settings ? clone(body.chip_settings) : state.chipSettings; state.preferences = [...body.panels]; state.preferenceWrites.push([...body.panels]);
          }
          return send({ panels: state.preferences, ...(state.chipSettings ? { chip_settings: state.chipSettings } : {}), revision: state.preferenceWrites.length });
        }
        if (jobMatch) {
          const [, oid, jid, cancel] = jobMatch;
          if (request.method === 'POST' && !jid) {
            assert.ok(request.headers['idempotency-key']);
            const observation = byId(oid); assert.ok(observation);
            state.historyRequests.push({ observation_id: oid, request_key: request.headers['idempotency-key'], ...clone(body) });
            const job = { id: randomUUID(), observation_id: oid, request_key: request.headers['idempotency-key'], state: 'running', status: 'running', scope: body.scope, adjustment: body.adjustment, retryable: true, progress: { chunks_completed: 0, chunks_total: 1, rows: 0 }, current_dataset: observation.blocks.history.dataset, polls: 0 };
            state.jobs.set(job.id, job); return send(job, 202);
          }
          if (jid) {
            const job = state.jobs.get(jid); assert.ok(job?.observation_id === oid);
            if (cancel) job.state = job.status = 'cancelled';
            else if (job.state === 'running' && ++job.polls >= 2) finishJob(job);
            state.jobPolls++; return send(job);
          }
          return send({ items: [...state.jobs.values()].filter(job => job.observation_id === oid) });
        }
        if (url.pathname.endsWith('/assets/observations')) return send({ items: [...current.values()].map(publicObservation) });
        const observationMatch = url.pathname.match(/\/assets\/observations\/([^/]+)$/);
        if (observationMatch) return send(publicObservation(byId(observationMatch[1])));
        const datasetMatch = url.pathname.match(/\/datasets\/([^/]+)\/rows$/);
        if (datasetMatch) {
          if (state.readDelay) await new Promise(resolve => setTimeout(resolve, state.readDelay));
          const items = rows[datasetMatch[1]]; assert.ok(Array.isArray(items), 'Unknown frozen dataset');
          const offset = Number(url.searchParams.get('offset') || 0); const limit = Number(url.searchParams.get('limit') || 100);
          return send({ items: items.slice(offset, offset + limit), offset, limit, total: items.length });
        }
        if (url.pathname.endsWith('/watchlists')) return send({ items: [{ id: 'preview-watchlist', name: '隔离快照', items: [...current.keys()].map(asset => ({ asset, asset_type: 'stock' })) }] });
        if (url.pathname.endsWith('/intel/news') || url.pathname.endsWith('/intel/announcements')) {
          const kind = url.pathname.endsWith('/announcements') ? 'announcements' : 'news';
          const frozen = proof.intel?.[url.searchParams.get('code')]?.[kind];
          if (frozen?.error) return send({ detail: { message: frozen.error } }, 503);
          return send(frozen?.items || []);
        }
        if (url.pathname.endsWith('/runtime')) return send({ connected: true, credential_configured: false, provider: 'snapshot-preview', model: null, mode: 'native', version: 'isolated-snapshot' });
        if (url.pathname.endsWith('/models')) return send({ groups: [], failures: [] });
        if (url.pathname.endsWith('/events')) return send('event: connected\ndata: {}\n\n', 200, 'text/event-stream');
        return send({ items: [] });
      }
      const relative = url.pathname === '/' ? 'index.html' : url.pathname.replace(/^\/static\//, '');
      const filename = path.resolve(ui, relative); assert.ok(filename.startsWith(ui + path.sep));
      let contents = await readFile(filename);
      if (relative === 'index.html') contents = contents.toString().replace('</head>', '<script type="module" src="/preview-controls.mjs"></script></head>').replace('<body>', '<body><div style="position:fixed;right:8px;bottom:4px;z-index:99999;pointer-events:none;font:11px sans-serif;color:#ad8134;background:var(--surface,#222);padding:3px 8px;border:1px solid #ad8134;border-radius:4px">隔离预览 · 冻结快照、非实时行情 · 不查询供应商或模型</div>');
      return send(contents, 200, mime[path.extname(filename)] || 'application/octet-stream');
    } catch (error) {
      state.errors.push({ type: error.name, message: error.message });
      await appendFile(path.join(output, 'server.jsonl'), JSON.stringify({ event: 'wind_fixture_failed', type: error.name, message: error.message }) + '\n');
      response.writeHead(500, { 'Content-Type': 'application/json' }); response.end(JSON.stringify({ error: 'wind_fixture_failed' }));
    }
  });
  await new Promise(resolve => server.listen(port, '127.0.0.1', resolve));
  const origin = `http://127.0.0.1:${server.address().port}`;
  await writeFile(path.join(output, 'fixture.json'), JSON.stringify({ origin, pid: process.pid, proofPath, partialProofPath, hashes, supplierCalls: 0, modelCalls: 0, productionWrites: 0 }, null, 2));
  return { state, origin, close: () => new Promise(resolve => server.close(resolve)), verifySourceUnchanged: async () => {
    for (const [file, hash] of Object.entries(hashes)) assert.equal(createHash('sha256').update(await readFile(path.join(ui, file))).digest('hex'), hash, `Source changed while browser acceptance ran: ${file}`);
    return hashes;
  } };
}
