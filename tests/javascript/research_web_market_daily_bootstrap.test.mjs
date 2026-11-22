import assert from 'node:assert/strict';
import test from 'node:test';
import { createMarketDailyBootstrap } from '../../app/research_web/ui/market-daily-bootstrap.mjs';

const event = (group, action) => ({ preventDefault() {}, target: { closest: () => ({ dataset: { marketDailyGroup: group, marketDailyAction: action } }) } });
const storage = () => { const m = new Map(); return { setItem: (k,v) => m.set(k,v), getItem: k => m.get(k) ?? null, removeItem: k => m.delete(k) }; };
const result = { status: 'partial', items: [{ source: 'fed_fomc', label: '美联储', status: 'completed', records: 4 }, { source: 'bls_cpi', status: 'failed', error: '<script>alert(1)</script>' }] };

test('one-time imports require a deliberate preflight then explicit same-origin write', async () => {
  const calls = [];
  const job = createMarketDailyBootstrap({ api: { async request(path, opts) { calls.push({path, opts}); return result; } }, storage: storage(), getIdentity: () => 'account-a', makeKey: () => 'batch-key-123' });
  assert.match(job.render(), /预检/);
  assert.equal(calls.length, 0);
  await job.handleClick(event('events', 'execute'));
  assert.equal(calls.length, 0);
  await job.handleClick(event('events', 'preview'));
  assert.deepEqual(calls.map(c => c.path), ['/events/initial-batch/preview']);
  assert.match(job.render(), /美联储/);
  assert.doesNotMatch(job.render(), /<script>/);
  await job.handleClick(event('events', 'execute'));
  assert.deepEqual(calls.map(c => c.path), ['/events/initial-batch/preview','/events/initial-batch']);
  assert.ok(calls.every(c => c.opts.userAction && c.opts.method === 'POST'));
  assert.deepEqual(calls[1].opts.body,{idempotency_key:'batch-key-123'});
  await job.handleClick(event('events', 'execute'));
  assert.equal(calls.length, 2);
});

test('an unknown execution can only be explicitly reconciled with the same key', async () => {
  const keys = [];
  const job = createMarketDailyBootstrap({ api: { async request(path, {body}) { if (path.endsWith('/preview')) return result; keys.push(body.idempotency_key); if (keys.length === 1) throw new Error('lost response'); return result; } }, storage: storage(), getIdentity: () => 'a', makeKey: () => 'unknown-key-123' });
  await job.handleClick(event('scores','preview'));
  await job.handleClick(event('scores','execute'));
  assert.match(job.render(), /结果未知/);
  await job.handleClick(event('scores','preview'));
  assert.deepEqual(keys,['unknown-key-123']);
  await job.handleClick(event('scores','execute'));
  assert.deepEqual(keys,['unknown-key-123','unknown-key-123']);
});

test('a late preview from another account does not unlock execution or display its records', async () => {
  let finish; let owner = 'a'; let n = 0;
  const job = createMarketDailyBootstrap({ api: { request() { n++; return new Promise(resolve => {finish=resolve;}); } }, getIdentity: () => owner });
  const pending = job.handleClick(event('events','preview'));
  owner = 'b'; job.dispose(); finish(result); await pending;
  assert.doesNotMatch(job.render(), /美联储/);
  await job.handleClick(event('events','execute'));
  assert.equal(n,1);
});

test('a persisted interruption preserves its rows but allows a new explicit attempt', async () => {
  let n = 0;
  const keys = [];
  const job = createMarketDailyBootstrap({ api: { async request(path, {body}) { if (path.endsWith('/preview')) return result; keys.push(body.idempotency_key); return keys.length === 1 ? {...result, status:'interrupted'} : result; } }, storage: storage(), makeKey: () => `batch-key-${++n}` });
  await job.handleClick(event('events','preview'));
  await job.handleClick(event('events','execute'));
  assert.match(job.render(), /已中断/);
  assert.match(job.render(), /美联储/);
  await job.handleClick(event('events','preview'));
  await job.handleClick(event('events','execute'));
  assert.deepEqual(keys,['batch-key-1','batch-key-2']);
});

test('reload restores only the same account and operation’s unresolved key', async () => {
  const keys = [], browser = storage();
  const api = { async request(path, {body}) { if (path.endsWith('/preview')) return result; keys.push(body.idempotency_key); if (keys.length === 1) throw new Error('lost response'); return result; } };
  const before = createMarketDailyBootstrap({api, storage:browser, getIdentity:() => 'a', makeKey:() => 'saved-key-123'});
  await before.handleClick(event('events','preview'));
  await before.handleClick(event('events','execute'));
  const other = createMarketDailyBootstrap({api, storage:browser, getIdentity:() => 'b'});
  assert.doesNotMatch(other.render(), /结果未知/);
  const after = createMarketDailyBootstrap({api, storage:browser, getIdentity:() => 'a', makeKey:() => 'wrong-key-456'});
  assert.match(after.render(), /结果未知/);
  await after.handleClick(event('scores','execute'));
  await after.handleClick(event('events','execute'));
  assert.deepEqual(keys,['saved-key-123','saved-key-123']);
  assert.doesNotMatch(createMarketDailyBootstrap({api, storage:browser, getIdentity:() => 'a'}).render(), /结果未知/);
});
