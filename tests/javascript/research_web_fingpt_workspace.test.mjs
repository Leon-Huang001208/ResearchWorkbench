import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';
import { nativeFinGPT, renderFinGPT, paintFinGPTShell } from '../../app/research_web/ui/fingpt-workspace.mjs';

test('native FinGPT is enabled only by server identity configuration', () => {
  delete globalThis.__RWB_FINGPT_WORKSPACE__;
  assert.equal(nativeFinGPT(), false);
  globalThis.__RWB_FINGPT_WORKSPACE__ = true;
  assert.equal(nativeFinGPT(), true);
  assert.match(renderFinGPT(), /data-fingpt-workspace/);
  assert.doesNotMatch(renderFinGPT(), /data-qa-app|prompt/);
  delete globalThis.__RWB_FINGPT_WORKSPACE__;
});

test('ordinary shell rendering is unchanged', () => {
  const root = { innerHTML: '', querySelector: () => null };
  paintFinGPTShell(root, '<main>Claw</main>', false);
  assert.equal(root.innerHTML, '<main>Claw</main>');
});

test('native entry clears only authentication state before using original OIDC', () => {
  const source = readFileSync(new URL('../../integrations/weknora/rwb-fingpt.mjs', import.meta.url), 'utf8');
  assert.match(source, /\/api\/v1\/auth\/oidc\/start/);
  assert.doesNotMatch(source, /localStorage\.clear\(|setItem\(|password|client_secret/);
});

test('unbound identity points to the actual knowledge settings route', async () => {
  const { mountFinGPT } = await import('../../app/research_web/ui/fingpt-workspace.mjs');
  const previous = globalThis.document;
  let link;
  globalThis.document = { createElement: () => ({}) };
  const slot = { textContent: '', append: value => { link = value; } };
  try {
    await mountFinGPT({ querySelector: () => slot }, async () => ({ ok: false, status: 409 }));
    assert.match(slot.textContent, /绑定/);
    assert.equal(link.href, '#/settings/data');
  } finally { globalThis.document = previous; }
});

test('new conversations enter native workspace while scoped financial handoffs keep their session', async () => {
  const { isNativeFinGPTEntry, fingptReplacement } = await import('../../app/research_web/ui/qa-navigation.mjs');
  assert.equal(isNativeFinGPTEntry({ page: 'fingpt' }, true), true);
  assert.equal(isNativeFinGPTEntry({ page: 'qa' }, true), true);
  assert.equal(isNativeFinGPTEntry({ page: 'qa', sessionId: 'frozen-financial-task' }, true), false);
  assert.equal(isNativeFinGPTEntry({ page: 'fingpt', sessionId: 'frozen-financial-task' }, true), false);
  assert.equal(isNativeFinGPTEntry({ page: 'claw' }, true), false);
  assert.equal(fingptReplacement({ mode: 'fingpt', execution_engine: 'alphadesk' }, 'frozen-financial-task'), '#/qa?session=frozen-financial-task');
});
