import assert from 'node:assert/strict';
import test from 'node:test';
import { createController } from '../../app/research_web/ui/core.mjs';
import { readNavigationView, saveNavigationView } from '../../app/research_web/ui/conversation-navigation.mjs';

test('server accounts do not restore another accounts draft or navigation in the same browser', async () => {
  const values = new Map();
  const storage = { getItem: key => values.get(key), setItem: (key, value) => values.set(key, value), removeItem: key => values.delete(key) };
  const api = { detail: async id => ({ id, mode: 'claw', messages: [], status: 'idle' }) };
  const alice = '11111111-1111-4111-8111-111111111111';
  const bob = '22222222-2222-4222-8222-222222222222';
  const previous = globalThis.__RWB_USER_ID__;
  try {
    globalThis.__RWB_USER_ID__ = alice;
    const a = createController({ api, draftStorage: storage, logger() {} });
    await a.open({ page: 'claw', sessionId: null }); a.setDraft('private Alice draft');
    saveNavigationView('claw', { expanded: ['alice-project'] }, storage);
    globalThis.__RWB_USER_ID__ = bob;
    const b = createController({ api, draftStorage: storage, logger() {} });
    await b.open({ page: 'claw', sessionId: null });
    assert.equal(b.state.draft, '');
    assert.deepEqual(readNavigationView('claw', storage).expanded, []);
    globalThis.__RWB_USER_ID__ = alice;
    const restored = createController({ api, draftStorage: storage, logger() {} });
    await restored.open({ page: 'claw', sessionId: null });
    assert.equal(restored.state.draft, 'private Alice draft');
    assert.deepEqual(readNavigationView('claw', storage).expanded, ['alice-project']);
  } finally {
    if (previous === undefined) delete globalThis.__RWB_USER_ID__; else globalThis.__RWB_USER_ID__ = previous;
  }
});
