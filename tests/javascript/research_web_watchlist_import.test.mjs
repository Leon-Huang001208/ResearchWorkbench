import assert from 'node:assert/strict';
import test from 'node:test';
import { createAPI } from '../../app/research_web/ui/core.mjs';
import { createAssetWorkspaceController } from '../../app/research_web/ui/asset-controller.mjs';
import { renderAssetWorkspace } from '../../app/research_web/ui/asset-workspace.mjs';
import { createWatchlistImportController, encodeWatchlistFile, renderWatchlistImportResults } from '../../app/research_web/ui/watchlist-import.mjs';

const text = 'asset,asset_type,name\r\n000001.SZ,stock,同名😀\r\n';
const file = () => new File(['\ufeff' + text], '自选.csv');
const frozen = () => ({ import_id: 'import-id', preview_digest: 'a'.repeat(64), expires_at: 1999999999, can_confirm: true, catalog_status: 'ready', rows: [{ row_number: 1, line_number: 2, input: { asset: '000001', asset_type: 'stock', name: '<img src=x onerror=alert(1)>' }, status: 'needs_selection', proposed_action: 'blocked', selected: null, candidates: [{ asset: '000001.SZ', name: '同名' }] }] });
const make = (overrides = {}) => {
  const calls = []; let serial = 0;
  const controller = createWatchlistImportController({ api: {
    previewWatchlistImport: async (id, body) => { calls.push({ id, body }); return frozen(); },
    confirmWatchlistImport: async (id, importId, body, key) => { calls.push({ id, importId, body, key }); return { status: 'committed', added_count: 1, skipped_count: 0 }; },
    ...overrides,
  }, makeKey: () => `key-${++serial}` });
  return { controller, calls };
};

test('raw byte hash and base64 retain BOM, CRLF, leading zero and emoji', async () => {
  const result = await encodeWatchlistFile(file());
  const raw = Buffer.from(result.file_base64, 'base64');
  assert.equal(raw.toString(), '\ufeff' + text);
  const expected = await crypto.subtle.digest('SHA-256', raw);
  assert.equal(result.file_sha256, Buffer.from(expected).toString('hex'));
  await assert.rejects(encodeWatchlistFile(new File([], 'empty.csv')), /非空/);
  await assert.rejects(encodeWatchlistFile({ size: 1024 * 1024 + 1 }), /1 MiB/);
});

test('explicit preview, change, refreeze and confirm preserve file and full decisions', async () => {
  const { controller: c, calls } = make();
  c.target('list-id'); await c.file(file()); await c.preview();
  const input = c.state.file;
  c.choose(1, '000001.SZ'); c.skip(2, true);
  assert.ok(c.state.dirty); await c.confirm(); assert.equal(calls.length, 1);
  await c.preview(); assert.deepEqual(calls[1].body.selections, { 1: '000001.SZ' }); assert.deepEqual(calls[1].body.skipped_rows, [2]);
  await c.confirm(); assert.equal(calls.length, 3); assert.equal(c.state.receipt.added_count, 1);
  assert.equal(c.state.file, input); assert.equal(c.state.filename, '自选.csv');
  await c.confirm(); assert.equal(calls.length, 3);
});

test('unknown response retries reuse exact confirmation key; conflict retains input and requires refreeze', async () => {
  const keys = []; let count = 0;
  const { controller: c } = make({ confirmWatchlistImport: async (_id, _importId, _body, key) => { keys.push(key); if (++count === 1) throw new Error('response lost'); throw Object.assign(new Error('changed'), { code: 'watchlist_import_target_changed', status: 409 }); } });
  c.target('list-id'); await c.file(file()); await c.preview();
  await c.confirm(); assert.match(c.state.error, /确认结果尚未核实/); assert.equal(c.state.dirty, false);
  await c.confirm(); assert.deepEqual(keys, ['key-1', 'key-1']); assert.ok(c.state.dirty); assert.ok(c.state.file); assert.match(c.state.error, /列表已变化/);
  await c.confirm(); assert.equal(keys.length, 2);
});

test('preview rejection, forbidden and unavailable catalog keep file and clear confirm ability', async () => {
  const { controller: c } = make({ previewWatchlistImport: async () => { throw Object.assign(new Error('denied'), { status: 403 }); } });
  c.target('list-id'); await c.file(file()); const original = c.state.file; await c.preview();
  assert.equal(c.state.file, original); assert.ok(c.state.dirty); assert.match(c.state.error, /无权限/);
  const state = { ...c.state, preview: { ...frozen(), can_confirm: false, catalog_status: 'unavailable', catalog_failure: 'asset_directory_cache_unavailable' } };
  assert.match(renderWatchlistImportResults(state), /本地目录不可用/);
});

test('account change ignores delayed results and cannot confirm previous user draft', async () => {
  let account = 'a'; let resolve;
  const c = createWatchlistImportController({ account: () => account, api: { previewWatchlistImport: () => new Promise(r => { resolve = r; }) } });
  c.target('list-id'); await c.file(file()); const pending = c.preview(); account = 'b'; resolve(frozen()); await pending;
  assert.equal(c.state.preview, null); await c.confirm();
});

test('render escapes private row text, displays every skip and candidate truncation', () => {
  const p = frozen(); p.rows[0].candidates_truncated = true; p.rows[0].candidate_count = 60;
  p.rows.push({ ...p.rows[0], row_number: 2, status: 'skipped', proposed_action: 'skip_explicit', candidates: [] });
  const html = renderWatchlistImportResults({ preview: p, selections: {}, skips: [2], dirty: true });
  assert.doesNotMatch(html, /<img/); assert.match(html, /&lt;img/); assert.match(html, /本人指定/); assert.match(html, /共 60 个候选/); assert.match(html, /data-wi-skip="2" checked/);
});

test('original list renderer exposes real import element with bounded list metadata and unchanged links', () => {
  const html = renderAssetWorkspace({ watchlists: [{ id: 'list-id', name: '<自选>', items: [{ asset: '000001.SZ', asset_type: 'stock', name: '原项' }] }] });
  assert.match(html, /rwb-watchlist-import data-lists=/); assert.match(html, /data-asset-watchlist-create/); assert.match(html, /data-watchlist-item/); assert.match(html, /000001.SZ/); assert.doesNotMatch(html, /<自选>/);
});

test('API uses original account prefix and strict payload with stable idempotency header', async () => {
  const calls = [];
  const api = createAPI({ fetcher: async (url, options) => { calls.push({ url, options }); return { ok: true, status: 200, json: async () => ({}) }; }, logger: () => {} });
  await api.previewWatchlistImport('list-id', { schema_version: 1 });
  await api.confirmWatchlistImport('list-id', 'import-id', { confirmed: true }, 'stable-confirm-key');
  assert.equal(calls[0].url, '/api/research/watchlists/list-id/imports/preview');
  assert.equal(calls[1].url, '/api/research/watchlists/list-id/imports/import-id/confirm');
  assert.equal(calls[1].options.headers['Idempotency-Key'], 'stable-confirm-key');
  assert.equal(calls[1].options.credentials, 'same-origin');
});

test('successful import event rereads only original lists and preserves observations and chart state', async () => {
  const previous = globalThis.document;
  const events = new EventTarget(); globalThis.document = events;
  let reads = 0; let changes = 0;
  try {
    const controller = createAssetWorkspaceController({ api: { watchlists: async () => { reads++; return { items: [{ id: 'original', items: [{ asset: '000001.SZ' }] }] }; } }, onChange: () => { changes++; } });
    controller.state.observation = { id: 'retained' }; controller.state.rows = { history: [{ close: 10 }] };
    events.dispatchEvent(new CustomEvent('rwb-watchlist-import-committed', { detail: { account: 'single-user', receipt: {} } }));
    await new Promise(resolve => setTimeout(resolve, 0));
    assert.equal(reads, 1); assert.equal(changes, 1); assert.equal(controller.state.watchlists[0].id, 'original'); assert.equal(controller.state.observation.id, 'retained'); assert.equal(controller.state.rows.history[0].close, 10);
  } finally { globalThis.document = previous; }
});

test('known CSV errors are actionable Chinese and unknown errors never echo backend details', async () => {
  let count = 0;
  const { controller: c } = make({ previewWatchlistImport: async () => {
    throw Object.assign(new Error('/Users/private/credentials leaked detail'), { code: ++count === 1 ? 'watchlist_import_formula_rejected' : 'unknown_internal_failure' });
  } });
  c.target('list-id'); await c.file(file()); await c.preview();
  assert.match(c.state.error, /公式型字段/); assert.doesNotMatch(c.state.error, /watchlist_import_|Users/);
  await c.preview(); assert.match(c.state.error, /文件与选择已保留/); assert.doesNotMatch(c.state.error, /Users|credentials|internal/);
});
