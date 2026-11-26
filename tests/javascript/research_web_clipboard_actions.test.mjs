import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createClipboardActions } from '../../app/research_web/ui/clipboard-actions.mjs';

function harness({ messages = [], fail = false } = {}) {
  const state = { detail: { messages }, error: '' };
  let copied = '';
  let renders = 0;
  const timers = [];
  const written = [];
  const actions = createClipboardActions({
    getState: () => state,
    getCopied: () => copied,
    setCopied: value => { copied = value; },
    render: () => { renders += 1; },
    schedule: (fn, ms) => { timers.push([fn, ms]); },
    writeText: async text => {
      if (fail) throw new Error('denied');
      written.push(text);
    },
  });
  return {
    actions, state, written, timers,
    get copied() { return copied; },
    get renders() { return renders; },
    flush() { while (timers.length) timers.shift()[0](); },
  };
}

test('copyAnswer writes the message body and flashes a marker', async () => {
  const h = harness({ messages: [{ id: 'm1', text: 'hello' }] });
  assert.equal(await h.actions.copyAnswer('m1'), true);
  assert.deepEqual(h.written, ['hello']);
  assert.equal(h.copied, 'answer:m1');
  assert.equal(h.renders, 1);
});

test('the flash clears itself after the transient window', async () => {
  const h = harness({ messages: [{ id: 'm1', text: 'hello' }] });
  await h.actions.copyAnswer('m1');
  assert.equal(h.timers.at(-1)[1], 1600);
  h.flush();
  assert.equal(h.copied, '');
  assert.equal(h.renders, 2);
});

test('a newer marker is not cleared by an older timer', async () => {
  const h = harness({ messages: [{ id: 'm1', text: 'one' }, { id: 'm2', text: 'two' }] });
  await h.actions.copyAnswer('m1');
  const [firstTimer] = h.timers;
  await h.actions.copyAnswer('m2');
  firstTimer[0]();                 // stale timer fires
  assert.equal(h.copied, 'answer:m2', 'stale timer must not clear the current marker');
});

test('unknown message ids do nothing', async () => {
  const h = harness({ messages: [] });
  assert.equal(await h.actions.copyAnswer('missing'), false);
  assert.equal(h.renders, 0);
  assert.equal(h.written.length, 0);
});

test('clipboard denial reports a manual-copy error instead of throwing', async () => {
  const h = harness({ messages: [{ id: 'm1', text: 'x' }], fail: true });
  assert.equal(await h.actions.copyAnswer('m1'), false);
  assert.match(h.state.error, /手动/);
  assert.equal(h.renders, 1);
});

test('shareSession copies the current URL', async () => {
  const h = harness();
  const original = globalThis.location;
  globalThis.location = { href: 'https://example.test/#/thread' };
  try {
    assert.equal(await h.actions.shareSession(), true);
    assert.deepEqual(h.written, ['https://example.test/#/thread']);
    assert.equal(h.copied, 'share');
  } finally {
    globalThis.location = original;
  }
});
