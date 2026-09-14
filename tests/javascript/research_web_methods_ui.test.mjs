import test from 'node:test';
import assert from 'node:assert/strict';

import { renderCapabilityPreviewDialog, renderCapabilityWorkspace, capabilityWorkspaceKindKey } from '../../app/research_web/ui/capability-workspace.mjs';
import { renderComposer, methodSelectionState } from '../../app/research_web/ui/composer.mjs';
import { createController } from '../../app/research_web/ui/core.mjs';

const method = (id, name = id) => ({ id, kind: 'method', name, description: `${name}说明`, category: '推理方法', builtin: true, enabled: true, version: 1, metadata: { scenarios: ['复杂研究'], inputs: [{ name: 'question', label: '研究问题', type: 'text', required: true }], default_formats: [], required_tools: [], dependencies: [] }, method_spec: { version: '1.0.0' } });
const session = () => ({ id: 's1', status: 'idle', messages: [], files: [], activities: [], approvals: [], questions: [] });

test('method is a separate read-only capability tab with ten versioned entries', () => {
  const methods = Array.from({ length: 10 }, (_, index) => method(`method-${index}`, `方法${index}`));
  const html = renderCapabilityWorkspace({ capabilities: methods, kind: 'method' });
  assert.match(html, /id="capability-kind-method"/);
  assert.match(html, /方法能力库/);
  assert.doesNotMatch(html, /data-cap-create|data-cap-import/);
  assert.equal((html.match(/data-use-method=/g) || []).length, 10);
  assert.deepEqual(capabilityWorkspaceKindKey('End', 'skill'), { handled: true, kind: 'data' });
});

test('composer exposes method sources, max-three state and selected chips', () => {
  const methods = [method('fact-checking', '事实核查'), method('first-principles', '第一性原理')];
  const html = renderComposer({ methods, methodIds: ['fact-checking'], methodPickerOpen: true });
  assert.match(html, /方法 1\/3/);
  assert.match(html, /class="capability-picker method-picker" open/);
  assert.match(html, /事实核查.*用户选择/s);
  assert.match(html, /data-method-id="first-principles"/);
  assert.deepEqual(methodSelectionState(['a', 'b', 'c'], 'd'), { accepted: false, reason: '最多选择三个方法' });
});

test('method preview shows linked business capabilities without making methods editable', () => {
  const selected = method('fact-checking', '事实核查');
  const skill = { id: 'company-research', kind: 'skill', name: '公司研究', metadata: { method_policy: { required: ['fact-checking'] } } };
  const html = renderCapabilityPreviewDialog({ detail: selected, capabilities: [selected, skill] });
  assert.match(html, /公司研究（必需）/);
  assert.doesNotMatch(html, /data-cap-manage/);
});

test('controller preserves method ids in drafts and retries', async () => {
  const bodies = [];
  const controller = createController({ api: { detail: async () => session(), message: async (_id, body) => { bodies.push(body); throw new Error('retry'); } }, makeID: () => 'method-key' });
  await controller.open({ page: 'fingpt', sessionId: 's1' });
  controller.setMethods(['fact-checking', 'first-principles']);
  controller.setDraft('研究问题');
  await controller.open({ page: 'history', sessionId: null });
  await controller.open({ page: 'fingpt', sessionId: 's1' });
  await controller.send();
  assert.deepEqual(bodies[0].method_ids, ['fact-checking', 'first-principles']);
});
