import assert from 'node:assert/strict';
import test from 'node:test';

import { parseRoute } from '../../app/research_web/ui/core.mjs';
import {
  renderSettingsPage,
  resolveSettingsSection,
  settingsConnectionId,
  settingsRefreshCatalogs,
  settingsSections,
} from '../../app/research_web/ui/settings.mjs';

const groups = [
  { id: 'professional', label: '专业数据源', source_ids: ['wind', 'mysql'] },
  { id: 'api', label: 'API 数据源', source_ids: ['tavily'] },
  { id: 'public', label: '公开来源', source_ids: ['cls'] },
  { id: 'local', label: '本机集成', source_ids: ['local_cache'] },
];

const sources = [
  { id: 'wind', name: 'Wind', group: 'professional', auth_type: 'local', integration_completed: true, actions: ['probe'] },
  { id: 'mysql', name: 'MySQL', group: 'professional', auth_type: 'account', configuration_supported: true, actions: ['probe'] },
  { id: 'tavily', name: 'Tavily', group: 'api', auth_type: 'api_key', configuration_supported: true, actions: ['probe'] },
  { id: 'cls', name: '财联社', group: 'public', auth_type: 'none', integration_completed: true, actions: ['probe'] },
  { id: 'local_cache', name: 'Excel 与本机工作流', group: 'local', auth_type: 'local', integration_completed: true, actions: ['probe'] },
];

const connections = {
  groups,
  sources,
  platform: {
    excel_automation: { status: 'available', label: 'Excel 自动化' },
    wind_excel: { status: 'unverified', label: 'Wind 插件' },
    ifind_excel: { status: 'unverified', label: 'iFinD 插件' },
    report_workflow: { status: 'unverified', label: '报告工作流' },
  },
  migration: { available: true, targets: ['tavily'], conflicts: [] },
};

const baseOptions = {
  runtime: { connected: true, provider: 'openai', model: 'gpt', version: '1', owned_runtime: true },
  models: [{ id: 'gpt', provider: 'openai' }],
  runtimeLabel: 'DSH 已连接',
  busy: false,
  modelFailures: [],
  connections,
  selectedConfiguration: {},
  migrationOpen: false,
};

test('settings hash contract covers five canonical sections and safe fallbacks', () => {
  assert.deepEqual(parseRoute('#/settings'), { page: 'settings', sessionId: null, settingsSection: 'general' });
  for (const section of settingsSections) {
    assert.deepEqual(parseRoute(`#/settings/${section.id}`), { page: 'settings', sessionId: null, settingsSection: section.id });
  }
  assert.deepEqual(parseRoute('#/settings/unknown'), { page: 'settings', sessionId: null, settingsSection: 'general', settingsSectionFallback: true });
  assert.deepEqual(parseRoute('#/settings/data/extra'), { page: 'settings', sessionId: null, settingsSection: 'general', settingsSectionFallback: true });
  assert.deepEqual(parseRoute('#/settings/%2e%2e?connection=%3Ctoken%3E'), { page: 'settings', sessionId: null, settingsSection: 'general', settingsSectionFallback: true });
});

test('legacy connection links select the compatible data or local section', () => {
  const remote = parseRoute('#/settings?connection=mysql');
  const local = parseRoute('#/settings?connection=local_cache');
  assert.equal(resolveSettingsSection(remote, sources), 'data');
  assert.equal(resolveSettingsSection(local, sources), 'local');
  assert.equal(settingsConnectionId('#/settings?connection=mysql', sources, 'data'), 'mysql');
  assert.equal(settingsConnectionId('#/settings?connection=local_cache', sources, 'local'), 'local_cache');
});

test('settings renders exactly one active body and marks one category current', () => {
  const signatures = {
    general: 'appearance-picker',
    model: 'id="settings-form"',
    data: 'data-connection-scope="data"',
    local: 'data-connection-scope="local"',
    docs: '/api/research/documentation/index.html',
  };
  for (const section of Object.keys(signatures)) {
    const html = renderSettingsPage({ ...baseOptions, route: parseRoute(`#/settings/${section}`), hash: `#/settings/${section}` });
    assert.equal((html.match(/aria-current="page"/g) || []).length, 1, section);
    assert.match(html, new RegExp(`data-settings-section="${section}"`));
    assert.match(html, new RegExp(signatures[section]));
    for (const [other, signature] of Object.entries(signatures)) {
      if (other !== section) assert.doesNotMatch(html, new RegExp(signature), `${section} must not render ${other}`);
    }
  }
});

test('only live settings sections render scoped refresh controls', () => {
  assert.deepEqual(settingsRefreshCatalogs('model'), ['runtime', 'models']);
  assert.deepEqual(settingsRefreshCatalogs('data'), ['connections']);
  assert.deepEqual(settingsRefreshCatalogs('local'), ['connections']);
  assert.deepEqual(settingsRefreshCatalogs('general'), []);
  assert.deepEqual(settingsRefreshCatalogs('docs'), []);
  for (const section of ['model', 'data', 'local']) {
    const html = renderSettingsPage({ ...baseOptions, route: parseRoute(`#/settings/${section}`), hash: `#/settings/${section}` });
    assert.match(html, /data-refresh/);
  }
  for (const section of ['general', 'docs']) {
    const html = renderSettingsPage({ ...baseOptions, route: parseRoute(`#/settings/${section}`), hash: `#/settings/${section}` });
    assert.doesNotMatch(html, /data-refresh/);
  }
});

test('data and local pages never mix source groups', () => {
  const data = renderSettingsPage({ ...baseOptions, route: parseRoute('#/settings/data'), hash: '#/settings/data?connection=wind' });
  assert.match(data, /data-connection-select="wind"/);
  assert.doesNotMatch(data, /data-connection-select="local_cache"/);

  const local = renderSettingsPage({ ...baseOptions, route: parseRoute('#/settings/local'), hash: '#/settings/local?connection=local_cache' });
  assert.match(local, /data-connection-select="local_cache"/);
  assert.doesNotMatch(local, /data-connection-select="wind"/);
});

test('settings navigation and responsive CSS keep desktop rail and 44px mobile tabs', async () => {
  const { readFile } = await import('node:fs/promises');
  const css = await readFile(new URL('../../app/research_web/ui/appearance.css', import.meta.url), 'utf8');
  assert.match(css, /\.settings-layout\s*\{[^}]*grid-template-columns:\s*200px minmax\(0, 1fr\)/);
  assert.match(css, /@media \(max-width:\s*760px\)[\s\S]*?\.settings-navigation\s*\{[^}]*display:\s*flex/);
  assert.match(css, /\.settings-navigation-link\s*\{[^}]*min-height:\s*44px/);
  assert.match(css, /@media \(prefers-reduced-motion:\s*reduce\)/);
});
