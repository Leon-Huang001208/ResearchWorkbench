import { test } from 'node:test';
import assert from 'node:assert/strict';
import { waitForHandler, type JobOutput } from '../src/queue.ts';

test('an uncooperative handler cannot hold the worker loop or publish a late commit', async () => {
  const stop = new AbortController();
  let resolveLate!: (output: JobOutput) => void;
  const pending = waitForHandler(async () => new Promise<JobOutput>(resolve => { resolveLate = resolve; }), stop.signal);
  await Promise.resolve();
  stop.abort();
  await assert.rejects(pending, /hot_handler_cancelled/);
  let committed = false;
  resolveLate({ result: {}, commit: async () => { committed = true; } });
  await Promise.resolve();
  assert.equal(committed, false);
});
