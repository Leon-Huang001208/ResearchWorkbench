import assert from 'node:assert/strict';
import test from 'node:test';

import {
  buildConfigurationPayload,
  renderConnectionCenter,
  selectedConnectionId,
} from '../../app/research_web/ui/connections.mjs';

const ids = [
  'wind', 'tinysoft', 'ifind', 'tushare', 'mysql',
  'tavily', 'bing', 'zhiqiu_reports', 'zhiqiu_wechat', 'zhiqiu_transcript',
  'akshare', 'baostock', 'yahoo', 'chinastock', 'csindex', 'szse', 'cninfo',
  'cls', 'cnstock_flash', 'cnstock_news', 'eastmoney_fund', 'local_cache',
];

const groups = [
  { id: 'professional', label: '专业数据源', source_ids: ids.slice(0, 5) },
  { id: 'api', label: 'API 数据源', source_ids: ids.slice(5, 10) },
  { id: 'public', label: '公开来源', source_ids: ids.slice(10, 21) },
  { id: 'local', label: '本机集成', source_ids: ids.slice(21) },
];

const sources = ids.map((id) => ({
  id,
  name: ({ wind: 'Wind', ifind: 'iFinD', mysql: '用户 MySQL 数据库', local_cache: 'Excel 与本机工作流' })[id] || id,
  group: groups.find((group) => group.source_ids.includes(id))?.id,
  auth_type: ['wind', 'local_cache'].includes(id) ? 'local' : id === 'mysql' ? 'account' : 'none',
  configured: id === 'mysql',
  secret_configured: id === 'mysql',
  probed: id === 'mysql',
  probe_status: id === 'mysql' ? 'healthy' : 'untested',
  integration_completed: ['mysql', 'cls', 'eastmoney_fund'].includes(id),
  callable: id === 'mysql',
  configuration_supported: ['mysql', 'wind', 'ifind', 'tinysoft', 'tushare', 'tavily', 'bing', 'zhiqiu_reports'].includes(id),
  description: `${id} 说明`,
  actions: ['probe'],
}));

const model = {
  groups,
  sources,
  platform: {
    os: 'darwin',
    excel_automation: { status: 'available', label: 'Excel 自动化' },
    wind_excel: { status: 'not_logged_in', label: 'Wind 插件' },
    ifind_excel: { status: 'not_installed', label: 'iFinD 插件' },
    report_workflow: { status: 'unverified', label: '报告工作流' },
  },
  migration: { available: true, targets: ['tushare'], conflicts: [] },
};

test('connection center renders all 22 sources in grouped compact navigation', () => {
  const html = renderConnectionCenter({ connections: model, selectedId: 'mysql', configuration: { configured: true, secret_configured: true, label: '因子库', host: 'db.internal', port: 3306, user: 'reader', charset: 'gbk', tls_mode: 'required_no_verify' } });
  assert.equal((html.match(/data-connection-select=/g) || []).length, 22);
  for (const label of ['专业数据源', 'API 数据源', '公开来源', '本机集成']) assert.match(html, new RegExp(label));
  for (const label of ['已配置', '已检测', '已适配', '可调用']) assert.match(html, new RegExp(label));
  assert.match(html, /id="connection-config-mysql"/);
  assert.doesNotMatch(html, /本轮仅说明后续适配方向/);
});

test('Wind detail is session based and does not render username or password fields', () => {
  const html = renderConnectionCenter({ connections: model, selectedId: 'wind', configuration: { preferred_adapter: 'auto' } });
  assert.match(html, /本机已登录会话/);
  assert.match(html, /client_api/);
  assert.match(html, /excel/);
  assert.doesNotMatch(html, /name="(?:username|password)"/);
  assert.match(html, /检测到组件不等于可调用/);
});

test('iFinD and token source details expose real configuration without secret values', () => {
  const ifind = renderConnectionCenter({ connections: model, selectedId: 'ifind', configuration: { configured: true, secret_configured: true, accounts: [{ id: 'primary', username: 'licensed-user', secret_configured: true }], backend: 'http_api', base_url: 'https://example.test' } });
  assert.match(ifind, /账号池/);
  assert.match(ifind, /python_sdk/);
  assert.match(ifind, /http_api/);
  assert.match(ifind, /type="password"/);
  assert.doesNotMatch(ifind, /actual-secret/);

  const token = renderConnectionCenter({ connections: model, selectedId: 'tushare', configuration: { configured: true, secret_configured: true } });
  assert.match(token, /API Token/);
  assert.match(token, /留空保留/);
});

test('unadapted and no-auth sources show diagnostics without a fake form', () => {
  const html = renderConnectionCenter({ connections: model, selectedId: 'cnstock_news', configuration: null });
  assert.match(html, /尚未适配/);
  assert.doesNotMatch(html, /<form/);
  assert.match(html, /检测/);
});

test('platform integration detail reports each verified layer independently', () => {
  const html = renderConnectionCenter({ connections: model, selectedId: 'local_cache', configuration: null });
  for (const label of ['Excel 自动化', 'Wind 插件', 'iFinD 插件', '报告工作流']) assert.match(html, new RegExp(label));
  assert.match(html, /未登录/);
  assert.match(html, /未安装/);
  assert.match(html, /未验证/);
});

test('configuration payloads are strict per source and never retain empty secrets', () => {
  const mysql = buildConfigurationPayload('mysql', new Map([
    ['label', ' 因子库 '], ['host', ' db.test '], ['port', '3306'], ['user', ' reader '],
    ['password', ''], ['charset', 'gbk'], ['tls_mode', 'required_no_verify'],
  ]));
  assert.deepEqual(mysql, { label: '因子库', host: 'db.test', port: 3306, user: 'reader', charset: 'gbk', tls_mode: 'required_no_verify' });
  const token = buildConfigurationPayload('tushare', new Map([['token', ' once ']]));
  assert.deepEqual(token, { token: 'once' });
  const zhiqiu = buildConfigurationPayload('zhiqiu_reports', new Map([['accounts.0.id', 'team'], ['accounts.0.username', 'reader'], ['accounts.0.password', 'one-shot']]));
  assert.deepEqual(zhiqiu, { accounts: [{ id: 'team', username: 'reader', password: 'one-shot' }] });
  assert.throws(() => buildConfigurationPayload('cnstock_news', new Map()), /不支持配置/);
});

test('settings deep link accepts only known safe source identifiers', () => {
  assert.equal(selectedConnectionId('#/settings?connection=ifind', sources), 'ifind');
  assert.equal(selectedConnectionId('#/settings?connection=../../runtime', sources), 'wind');
  assert.equal(selectedConnectionId('#/settings', sources), 'wind');
  assert.equal(selectedConnectionId('#/settings/data?connection=mysql', sources, 'data'), 'mysql');
  assert.equal(selectedConnectionId('#/settings/local?connection=mysql', sources, 'local'), 'local_cache');
  assert.equal(selectedConnectionId('#/settings/local?connection=local_cache', sources, 'local'), 'local_cache');
});

test('connection center separates remote data sources from local integrations', () => {
  const data = renderConnectionCenter({ connections: model, selectedId: 'wind', configuration: {}, scope: 'data' });
  assert.match(data, /data-connection-scope="data"/);
  assert.match(data, /data-connection-select="wind"/);
  assert.doesNotMatch(data, /data-connection-select="local_cache"/);
  assert.match(data, /data-migration-review/);

  const local = renderConnectionCenter({ connections: model, selectedId: 'local_cache', configuration: null, scope: 'local' });
  assert.match(local, /data-connection-scope="local"/);
  assert.match(local, /data-connection-select="local_cache"/);
  assert.doesNotMatch(local, /data-connection-select="wind"|data-migration-review/);
});

test('legacy migration requires source selection and an explicit second confirmation', () => {
  const html = renderConnectionCenter({ connections: model, selectedId: 'tushare', configuration: {}, migrationOpen: true });
  assert.match(html, /data-migration-confirm/);
  assert.match(html, /name="source_ids"/);
  assert.match(html, /name="confirm" required/);
  assert.match(html, /不读取或展示秘密值/);
});
