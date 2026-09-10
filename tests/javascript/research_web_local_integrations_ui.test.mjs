import assert from 'node:assert/strict';
import test from 'node:test';
import { readFile } from 'node:fs/promises';

import { createAPI, waitForLocalIntegrationProbe } from '../../app/research_web/ui/core.mjs';
import { createLocalIntegrationPollingGuard, renderLocalIntegrationConsole } from '../../app/research_web/ui/connections.mjs';
import { parseRoute } from '../../app/research_web/ui/core.mjs';
import { renderSettingsPage, settingsRefreshCatalogs } from '../../app/research_web/ui/settings.mjs';

const makeItem = (id, category, label, status, extra = {}) => ({
  id,
  category,
  label,
  discovery: status === '可用' ? '已发现' : '未发现',
  authorization: '无需授权',
  verification: status === '可用' ? '已验证' : '待验证',
  callable: status === '可用',
  status,
  message: `${label} 的明确说明`,
  detail: '不会把发现事实覆盖为可调用结论。',
  capabilities: [],
  actions: [],
  last_checked_at: '2026-09-10T00:00:00Z',
  last_verified_at: null,
  ...extra,
});

const localIntegrations = {
  platform: 'macos',
  service: { online: true, label: '本机服务在线' },
  summary: { available: 1, needs_attention: 4, total: 5 },
  categories: [
    { id: 'local_service', label: '本机服务', item_ids: ['research_web_service'] },
    { id: 'folders', label: '文件夹同步', item_ids: ['folder_sync'] },
    { id: 'office', label: 'Office 与金融插件', item_ids: ['excel_app', 'excel_automation_bridge'] },
    { id: 'browsers', label: '浏览器扩展', item_ids: [] },
    { id: 'mcp', label: '本地 MCP', item_ids: ['local_mcp'] },
  ],
  items: [
    makeItem('research_web_service', 'local_service', 'Research Web 本机服务', '可用'),
    makeItem('folder_sync', 'folders', '全局资料库文件夹同步', '待配置'),
    makeItem('excel_app', 'office', 'Microsoft Excel 应用', '待验证', { discovery: '已发现' }),
    makeItem('excel_automation_bridge', 'office', 'Excel 自动化桥', '待配置'),
    makeItem('local_mcp', 'mcp', '本地 MCP', '待授权', { authorization: '待授权' }),
  ],
};

test('local console shows only service and per-item truths without an overall callable verdict', () => {
  const html = renderLocalIntegrationConsole(localIntegrations);
  assert.match(html, /本机服务在线/);
  assert.match(html, /<strong>1<\/strong> 项可用/);
  assert.match(html, /<strong>4<\/strong> 项需处理/);
  for (const heading of ['发现', '授权', '验证', '可调用']) assert.match(html, new RegExp(`>${heading}<`));
  for (const category of ['本机服务', '文件夹同步', 'Office 与金融插件', '浏览器扩展', '本地 MCP']) assert.match(html, new RegExp(category));
  assert.match(html, /Microsoft Excel 应用[\s\S]*已发现[\s\S]*待验证[\s\S]*否/);
  assert.match(html, /Excel 自动化桥[\s\S]*待配置[\s\S]*未发现/);
  assert.doesNotMatch(html, /总体结论|本机工作流可用|local_cache/);
  assert.match(html, /<button[^>]*data-local-category-target="local-category-local_service"/);
  assert.doesNotMatch(html, /href="#local-category-/);
});

test('local console provides report automation as a separate workflow link', () => {
  const html = renderLocalIntegrationConsole(localIntegrations);
  assert.match(html, /报告自动化/);
  assert.match(html, /消费 Excel、Word、PowerPoint、Wind\/iFinD 数据能力/);
  assert.match(html, /href="#\/skills\?kind=workflow"/);
  assert.doesNotMatch(html, /检测项[^]*报告工作流/);
});

test('local console exposes busy, live-region and safe actions', () => {
  const actionModel = {
    ...localIntegrations,
    items: localIntegrations.items.map((item) => item.id === 'folder_sync'
      ? { ...item, actions: [{ id: 'configure', label: '配置 iFinD HTTP API', href: '#/settings/data?connection=ifind' }] }
      : item),
  };
  const html = renderLocalIntegrationConsole(actionModel, { busy: true });
  assert.match(html, /data-local-integrations-probe[^>]*disabled[^>]*aria-busy="true"[^>]*>检测中…/);
  assert.match(html, /class="sr-only" role="status" aria-live="polite" aria-atomic="true"/);
  assert.doesNotMatch(html, /data-local-integrations-console aria-live/);
  assert.match(html, /href="#\/settings\/data\?connection=ifind"/);

  const unsafe = renderLocalIntegrationConsole({
    ...actionModel,
    items: actionModel.items.map((item) => ({ ...item, actions: [{ id: 'bad', label: '坏链接', href: 'https://evil.test' }] })),
  });
  assert.doesNotMatch(unsafe, /evil\.test|坏链接/);
});

test('eligible Office rows expose explicit verification actions and per-target progress', () => {
  const expanded = {
    ...localIntegrations,
    items: [
      ...localIntegrations.items,
      makeItem('word_app', 'office', 'Microsoft Word 应用', '待验证', { discovery: '已发现', last_verified_at: '2026-09-10T01:00:00Z' }),
      makeItem('ifind_terminal', 'office', 'iFinD 专业终端', '不适用', {
        discovery: '不适用', authorization: '不适用', verification: '不适用',
        actions: [{ id: 'configure', label: '配置 iFinD HTTP API', href: '#/settings/data?connection=ifind' }],
      }),
    ],
    categories: localIntegrations.categories.map((category) => category.id === 'office'
      ? { ...category, item_ids: [...category.item_ids, 'word_app', 'ifind_terminal'] }
      : category),
  };
  const html = renderLocalIntegrationConsole(expanded, { verificationTarget: 'word' });
  assert.match(html, /role="status" aria-live="polite" aria-atomic="true">正在验证 Word，完成后将自动更新状态。/);
  assert.match(html, /data-local-integration-verify="excel"/);
  assert.match(html, /data-local-integration-verify="word"[^>]*disabled[^>]*aria-busy="true"[^>]*>验证中…/);
  assert.match(html, /最近验证：2026-09-10T01:00:00Z/);
  assert.doesNotMatch(html, /最近验证：2026-09-10T00:00:00Z/);
  assert.doesNotMatch(html, /data-local-integration-verify="ifind/);
  assert.match(html, /配置 iFinD HTTP API/);
});

test('local verification polling guard invalidates stale page and refresh work', () => {
  let localPageActive = true;
  const guard = createLocalIntegrationPollingGuard(() => localPageActive);
  const first = guard.begin();
  assert.equal(guard.isCurrent(first), true);

  const second = guard.begin();
  assert.equal(guard.isCurrent(first), false);
  assert.equal(guard.isCurrent(second), true);

  localPageActive = false;
  assert.equal(guard.isCurrent(second), false);
  localPageActive = true;
  guard.invalidate();
  assert.equal(guard.isCurrent(second), false);
});

test('settings local section loads the dedicated model while data keeps DataHub connections', () => {
  assert.deepEqual(settingsRefreshCatalogs('data'), ['connections']);
  assert.deepEqual(settingsRefreshCatalogs('local'), ['localIntegrations']);
  const html = renderSettingsPage({
    route: parseRoute('#/settings/local'),
    hash: '#/settings/local',
    localIntegrations,
    connections: { groups: [], sources: [] },
    busy: false,
    models: [],
    modelFailures: [],
  });
  assert.match(html, /data-settings-section="local"/);
  assert.match(html, /data-local-integrations-console/);
  assert.doesNotMatch(html, /data-connection-scope="local"|local_cache/);
  assert.match(html, /报告自动化[\s\S]*报告工作流消费/);
});

test('dedicated API uses idempotency and local probe polling validates responses', async () => {
  const calls = [];
  const api = createAPI({ fetcher: async (url, options = {}) => {
    calls.push([url, options]);
    return new Response(JSON.stringify({ id: 'probe-1', status: 'queued' }), { status: 202 });
  }, logger() {} });
  await api.localIntegrations();
  await api.probeLocalIntegrations('stable-local-key');
  await api.localIntegrationProbe('probe/one');
  assert.deepEqual(calls.map(([url]) => url), [
    '/api/research/local-integrations',
    '/api/research/local-integrations/probes',
    '/api/research/local-integrations/probes/probe%2Fone',
  ]);
  assert.equal(calls[1][1].headers['Idempotency-Key'], 'stable-local-key');

  const states = [{ status: 'queued' }, { status: 'checking' }, { status: 'completed', snapshot: localIntegrations }];
  const result = await waitForLocalIntegrationProbe(async () => states.shift(), 'probe-1', { delay: 0 });
  assert.equal(result.status, 'completed');
  await assert.rejects(waitForLocalIntegrationProbe(async () => ({}), 'probe-2', { delay: 0 }), /响应格式异常/);
});

test('dedicated API starts and polls allowlisted real verifications', async () => {
  const calls = [];
  const api = createAPI({ fetcher: async (url, options = {}) => {
    calls.push([url, options]);
    return new Response(JSON.stringify({ id: 'verify-1', target: 'excel', status: 'queued' }), { status: 202 });
  }, logger() {} });
  await api.verifyLocalIntegration('excel', 'stable-verification-key');
  await api.localIntegrationVerification('verify/one');
  assert.deepEqual(calls.map(([url]) => url), [
    '/api/research/local-integrations/verifications',
    '/api/research/local-integrations/verifications/verify%2Fone',
  ]);
  assert.equal(calls[0][1].headers['Idempotency-Key'], 'stable-verification-key');
  assert.equal(calls[0][1].body, JSON.stringify({ target: 'excel' }));
});

test('local-only CSS is compact, responsive and respects 44px targets', async () => {
  const css = await readFile(new URL('../../app/research_web/ui/appearance.css', import.meta.url), 'utf8');
  assert.match(css, /\.local-integrations-probe\s*\{[^}]*min-height:\s*44px/);
  assert.match(css, /\.local-category-nav button\s*\{[^}]*min-height:\s*44px/);
  assert.match(css, /@media \(max-width:\s*860px\)[^]*\.local-integration-row\s*\{[^}]*grid-template-columns:\s*1fr/);
  assert.doesNotMatch(css.match(/\.local-integration-console[^]*?(?=\n\.[a-z]|@media)/)?.[0] || '', /box-shadow/);
});

test('application controller no longer loads DataHub connections for the local page', async () => {
  const app = await readFile(new URL('../../app/research_web/ui/app.mjs', import.meta.url), 'utf8');
  assert.match(app, /localIntegrations:\s*\{\s*categories:/);
  assert.match(app, /api\.probeLocalIntegrations/);
  assert.match(app, /localIntegrationPollingGuard\.invalidate\(\)/);
  assert.match(app, /localIntegrationPollingGuard\.isCurrent\(verificationTicket\)/);
  assert.match(app, /return \{ status: 'cancelled' \}/);
  assert.match(app, /localCategoryTarget/);
  assert.match(app, /focus\(\{ preventScroll: true \}\)/);
  assert.match(app, /document\.scrollingElement/);
  assert.match(app, /scroller\.scrollTo\(\{ top: Math\.max\(0, top\), behavior \}\)/);
  assert.match(app, /prefers-reduced-motion: reduce/);
  assert.doesNotMatch(app, /scrollIntoView/);
  assert.doesNotMatch(app, /sourceId === 'local_cache'/);
});
