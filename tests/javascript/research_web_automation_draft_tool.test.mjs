import test from 'node:test';
import assert from 'node:assert/strict';
import { apply } from '../../app/research_web/runtime/research-tools.mjs';

test('native schedule tool proposes only; no create/enable or caller paths', async () => {
  const tools = new Map(); const calls = [];
  const ctx = { tools: { register: tool => tools.set(tool.name, tool) }, logger: { info() {}, warn() {} } };
  apply(ctx, { python: '/python', runnerPath: '/runner', researchRoot: '/research' }, undefined,
    async () => ({ admitted: true }), async (_ctx, _exec, _config, args) => { calls.push(args); return { id: 'draft-one', status: 'proposed' }; });
  const tool = tools.get('rwb_prepare_automation');
  assert.ok(tool);
  const args = { name: '每日研究', target_kind: 'skill', target_id: 'company-research', target_version: 1, input_template: '研究公司', schedule: { kind: 'daily', timezone: 'Asia/Shanghai', hour: 9, minute: 0 } };
  const result = await tool.execute(args, { signal: new AbortController().signal });
  assert.equal(JSON.parse(result.result_json).status, 'proposed');
  assert.equal(calls.length, 1);
  await assert.rejects(() => tool.execute({ ...args, enabled: true }, { signal: new AbortController().signal }), /draft_arguments_invalid/);
  await assert.rejects(() => tool.execute({ ...args, cwd: '/secret' }, { signal: new AbortController().signal }), /draft_arguments_invalid/);
  assert.equal(calls.length, 1);
});
