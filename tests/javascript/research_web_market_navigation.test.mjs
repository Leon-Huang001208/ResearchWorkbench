import assert from 'node:assert/strict';
import test from 'node:test';
import { createAPI, parseRoute } from '../../app/research_web/ui/core.mjs';
import { renderPrimaryRail } from '../../app/research_web/ui/shell.mjs';

test('market is a first-level workspace before assets with canonical tab and board routing', () => {
  assert.deepEqual(parseRoute('#/market?view=sectors'), { page: 'market', sessionId: null, marketView: 'sectors', marketBoardId: null });
  assert.equal(parseRoute('#/market?view=quotes&board_id=BK0420').marketBoardId, 'BK0420');
  assert.equal(parseRoute('#/market?view=invalid&board_id=../../host').marketView, 'overview');
  assert.equal(parseRoute('#/market?board_id=../../host').marketBoardId, null);
  const html = renderPrimaryRail({ page: 'market' });
  assert.ok(html.indexOf('href="#/market"') < html.indexOf('href="#/assets"'));
  assert.match(html, /href="#\/market"[^>]*aria-current="page"/);
});

test('market requests use the existing same-origin authenticated API transport', async () => {
  const calls = [];
  const api = createAPI({ logger() {}, fetcher: async (url, options) => { calls.push({ url, options }); return { ok: true, status: 202, json: async () => ({ request_id: 'r' }) }; } });
  await api.request('/market/refresh', { method: 'POST', body: { sections: ['quotes'] }, userAction: true });
  assert.equal(calls[0].url, '/api/research/market/refresh');
  assert.equal(calls[0].options.credentials, 'same-origin');
  assert.equal(calls[0].options.headers['X-Research-User-Action'], '?1');
});
