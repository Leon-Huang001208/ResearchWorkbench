import test from 'node:test';
import assert from 'node:assert/strict';
import { modelOptions } from '../../app/research_web/ui/views.mjs';

test('local gateway offers six providers and preserves the selected model', () => {
  const html = modelOptions([{ provider: 'openai-compatible', models: [{ id: 'deepseek/deepseek-flash' }] }], 'mimo/mimo-v2.6-pro', 'http://127.0.0.1:10100/v1');
  for (const name of ['GLM 5.3', 'Qwen 3.8 Max', 'Kimi K3', 'DeepSeek Flash', 'MiniMax M3', 'MiMo 2.6 Pro']) assert.ok(html.includes(name));
  assert.match(html, /selected>MiMo 2\.6 Pro/);
  assert.equal((html.match(/deepseek\/deepseek-flash/g) || []).length, 1);
});

test('unrelated compatible endpoints and official models keep their catalog', () => {
  for (const provider of ['openai-compatible', 'deepseek-official']) {
    const html = modelOptions([{ provider, models: [{ id: 'other-model', name: 'Other' }] }]);
    assert.ok(html.includes('Other'));
    assert.ok(!html.includes('Kimi K3'));
  }
});

 test('matching model IDs do not expand a remote, missing, or non-gateway endpoint', () => {
  for (const endpoint of ['', 'https://vendor.example/v1', 'http://127.0.0.1:11434/v1', 'http://127.0.0.1:10100/other', 'http://localhost.evil:10100/v1', 'not a url', 'http://user@127.0.0.1:10100/v1', 'http://127.0.0.1:10100/v1?proxy=vendor']) {
    const html = modelOptions([{ provider: 'openai-compatible', models: [{ id: 'deepseek/deepseek-flash' }] }], '', endpoint);
    assert.ok(!html.includes('Kimi K3'), endpoint);
  }
});
 test('loopback aliases support the configured gateway only', () => {
  for (const endpoint of ['http://localhost:10100/v1', 'http://[::1]:10100/v1/']) {
    const html = modelOptions([{ provider: 'openai-compatible', models: [{ id: 'deepseek/deepseek-flash' }] }], '', endpoint);
    assert.ok(html.includes('Kimi K3'));
  }
});

test('composer and settings forward the active connection endpoint', async () => {
  const { renderComposer } = await import('../../app/research_web/ui/composer.mjs');
  const { renderSettingsPage } = await import('../../app/research_web/ui/settings.mjs');
  const groups = [{ provider: 'openai-compatible', models: [{ id: 'deepseek/deepseek-flash' }] }];
  for (const [endpoint, expands] of [['http://127.0.0.1:10100/v1', true], ['https://vendor.example/v1', false]]) {
    const composer = renderComposer({ page: 'fingpt', models: groups, modelEndpoint: endpoint });
    const settings = renderSettingsPage({ route: { settingsSection: 'model' }, models: groups, runtime: { owned_runtime: true, provider: 'openai-compatible', connection: { base_url: endpoint } }, modelFailures: [] });
    assert.equal(composer.includes('Kimi K3'), expands);
    assert.equal(settings.includes('Kimi K3'), expands);
  }
});
