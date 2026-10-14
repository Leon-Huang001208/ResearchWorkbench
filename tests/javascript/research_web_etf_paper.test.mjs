import assert from 'node:assert/strict';
import test from 'node:test';
import { parseRoute, createAPI } from '../../app/research_web/ui/core.mjs';
import { renderEtfPaper } from '../../app/research_web/ui/etf-paper.mjs';

test('ETF route displays real admission blocked without fabricated values or auto execution', () => {
  assert.equal(parseRoute('#/workbench/etf-paper').section, 'etf-paper');
  const html = renderEtfPaper({ readiness: { gaps: ['<script>untrusted</script>'] } });
  assert.match(html, /真实链路：BLOCKED/);
  assert.match(html, /尚无模拟结果/);
  assert.match(html, /&lt;script&gt;/);
  assert.doesNotMatch(html, /<script>|onclick=|已成交|value="10000"/);
});

test('paper POST carries explicit action and idempotency key; HTTP errors propagate', async () => {
  const calls = [];
  const api = createAPI({ fetcher: async (url, options) => {
    calls.push({ url, options });
    return { ok: false, status: 409, json: async () => ({ error: { code: 'idempotency_conflict', message: '重复键冲突' } }) };
  }, logger: () => {} });
  await assert.rejects(() => api.etfReplay({ fixture: true }, 'fixture-key'), /重复键冲突/);
  assert.equal(calls.length, 1);
  assert.equal(calls[0].options.headers['X-Research-User-Action'], '?1');
  assert.equal(calls[0].options.headers['Idempotency-Key'], 'fixture-key');
  assert.equal(calls[0].url, '/api/research/portfolio-decisions/runs');
});
