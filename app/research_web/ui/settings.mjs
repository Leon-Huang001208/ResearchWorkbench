import { escapeHTML as e } from './markdown.mjs';
import { modelOptions } from './views.mjs';
import { renderAppearancePicker } from './shell.mjs';
import { renderConnectionCenter, renderLocalIntegrationConsole, selectedConnectionId } from './connections.mjs';

export const settingsSections = Object.freeze([
  { id: 'general', label: '通用', eyebrow: 'GENERAL', description: '管理仅影响当前浏览器的显示偏好。' },
  { id: 'model', label: '模型服务', eyebrow: 'MODEL SERVICE', description: '配置 Research Runtime 使用的模型服务。', refreshable: true },
  { id: 'data', label: '数据源', eyebrow: 'DATA CONNECTIONS', description: '管理专业数据源、API 数据源与公开来源。', refreshable: true },
  { id: 'local', label: '本机集成', eyebrow: 'LOCAL INTEGRATIONS', description: '诊断当前服务设备上的本机服务、文件夹、Office、浏览器与 MCP 能力。', refreshable: true },
  { id: 'docs', label: '架构文档', eyebrow: 'DOCUMENTATION', description: '只读查看当前架构与实现说明。' },
]);

const sectionIds = new Set(settingsSections.map((section) => section.id));

export function resolveSettingsSection(route = {}, sources = []) {
  const requested = sectionIds.has(route.settingsSection) ? route.settingsSection : 'general';
  if (!route.legacySettingsConnection || !route.connectionId) return requested;
  const source = sources.find((item) => item?.id === route.connectionId);
  return source?.group === 'local' ? 'local' : 'data';
}

export function settingsConnectionId(hash, sources, section) {
  if (!['data', 'local'].includes(section)) return '';
  return selectedConnectionId(hash, sources, section === 'local' ? 'local' : 'data');
}

export function settingsRefreshCatalogs(section) {
  if (section === 'model') return ['runtime', 'models'];
  if (section === 'data') return ['connections', 'integrations'];
  if (section === 'local') return ['localIntegrations', 'tabbit', 'integrations'];
  return [];
}

function renderSettingsNavigation(activeSection) {
  return `<nav class="settings-navigation" aria-label="设置分类"><span class="settings-navigation-label">设置</span>${settingsSections.map((section) => `<a href="#/settings/${section.id}" class="settings-navigation-link ${section.id === activeSection ? 'active' : ''}" ${section.id === activeSection ? 'aria-current="page"' : ''}>${e(section.label)}</a>`).join('')}</nav>`;
}

function renderSettingsHeader(section) {
  const refreshLabel = ['data', 'local'].includes(section.id) ? '重新检测全部' : '刷新状态';
  return `<header class="settings-page-header"><div><p class="eyebrow">${e(section.eyebrow)}</p><h1>${e(section.label)}</h1><p class="muted">${e(section.description)}</p></div>${section.refreshable ? `<button class="button" type="button" data-refresh>${refreshLabel}</button>` : ''}</header>`;
}

function renderModelSettings({ runtime, models, runtimeLabel, busy, modelFailures }) {
  const supported = (models || []).filter((group) => group.id === 'deepseek-official' || group.provider === 'deepseek-official');
  const disabled = busy || !runtime?.owned_runtime ? 'disabled' : '';
  const test = runtime?.last_model_test;
  const known = (value, yes, no) => value === true ? yes : value === false ? no : '未知，请刷新状态';
  const testLabel = !runtime || !Object.hasOwn(runtime, 'last_model_test') ? '无法读取' : !test ? '尚未测试' : test.status === 'passed' ? '已收到最终文本' : `失败：${test.code || 'model_generation_failed'}`;
  return `<section class="settings-card model-settings"><div class="section-heading"><div><p class="eyebrow">模型服务</p><h2>DSH 与模型配置</h2></div><span class="badge ${runtime?.connected ? 'live' : 'danger'}">${e(runtimeLabel)}</span></div>
    <dl class="runtime-details"><div><dt>Runtime 服务</dt><dd>${known(runtime?.health_check_passed, '可达', '不可达')}</dd></div><div><dt>配置已保存</dt><dd>${known(runtime?.configuration_saved, '是', '否（默认值）')}</dd></div><div><dt>Runtime 已应用</dt><dd>${known(runtime?.runtime_applied, '新会话默认模型', '待新会话应用或连接确认')}</dd></div><div><dt>凭据已配置</dt><dd>${known(runtime?.credential_configured, '是', '否')}</dd></div><div><dt>最近真实推理</dt><dd>${e(testLabel)}</dd></div><div><dt>版本</dt><dd>${e(runtime?.version || '未提供')}</dd></div><div><dt>管理方式</dt><dd>${runtime?.owned_runtime ? '由 Research Workbench 管理' : '外部或未确认运行时'}</dd></div></dl>${runtime?.configuration_uncertain ? '<div class="notice warning" role="status">凭据提交结果未知；请在设置页重新录入或明确清除，后续模型请求暂时阻断。</div>' : ''}
    <form id="settings-form" autocomplete="off"><label for="settings-model">受支持模型</label><select id="settings-model" ${disabled}>${modelOptions(supported, runtime?.model)}</select><div class="form-grid"><label>Provider<input id="provider" name="provider" readonly value="deepseek-official"></label><label>模型 ID<input id="model-id" name="model" required autocomplete="off" value="${e(runtime?.model || 'deepseek-v4-flash')}" placeholder="固定 Runtime 目录内的模型 ID"></label></div><label for="api-key">API Key <span class="muted">（可选，仅替换时填写）</span></label><input id="api-key" name="api_key" type="password" autocomplete="new-password" spellcheck="false" placeholder="留空则保留现有凭据"><p class="muted small">仅发送给专属 DSH 的凭据后端；提交即清空，不回填。保存只影响新会话模型；已有会话保留选模。任何任务运行时拒绝保存或清除。</p><button class="button primary" type="submit" ${disabled}>保存模型配置</button></form>
    <div class="button-row"><button class="button" type="button" data-model-clear ${disabled || !runtime?.model ? 'disabled' : ''}>清除模型凭据</button><button class="button" type="button" data-model-test ${disabled}>测试真实生成</button></div><p class="muted small">测试显式调用当前模型，含前置检查与取消等待，单次最长 93 秒，会消耗少量模型额度并保留测试会话；服务可达与保存成功不代表推理成功。工具调用在用户显式发起的最小研究中单独验证。</p></section>${modelFailures.length ? '<div class="notice warning" role="status">模型目录未完整加载；保存时由固定 Runtime 支持目录校验。</div>' : ''}`;
}

function renderGeneralSettings() {
  return `<section class="settings-card appearance-settings"><h2>外观</h2><p class="muted">选择浅色、深色，或跟随系统。仅保存在此浏览器，不影响研究任务。</p>${renderAppearancePicker()}</section>`;
}

function renderDocumentationSettings() {
  return '<section class="settings-card"><h2>架构与实现文档</h2><p class="muted">只读查看当前架构图；检查回执不替代实现与人工验收。</p><a class="button" href="/api/research/documentation/index.html" target="_blank" rel="noopener noreferrer">打开架构文档 ↗</a></section>';
}

function renderTabbitSettings(tabbit, busy) {
  const labels = {
    ready: '已就绪', disabled: '已关闭', launcher_missing: '缺少 CLI', browser_offline: '浏览器离线',
    unsupported_version: '版本过低', instance_selection_required: '请选择实例', error: '诊断失败',
  };
  const state = tabbit?.status || 'error';
  const instances = Array.isArray(tabbit?.instances) ? tabbit.instances : [];
  const selected = tabbit?.selected_instance || tabbit?.instance_id || '';
  const saved = tabbit?.saved_config || { browser_enabled: tabbit?.browser_enabled !== false, web_fetch_enabled: tabbit?.web_fetch_enabled === true };
  const applied = tabbit?.applied_config || saved;
  const switchLabel = (value) => value ? '开启' : '关闭';
  const configTruth = `<div class="tabbit-config-truth"><p><strong>已保存配置</strong> · 浏览器自动化：${switchLabel(saved.browser_enabled)} · web_fetch：${switchLabel(saved.web_fetch_enabled)}</p><p><strong>Runtime 已应用</strong> · 浏览器自动化：${switchLabel(applied.browser_enabled)} · web_fetch：${switchLabel(applied.web_fetch_enabled)}</p></div>`;
  const instanceSelect = instances.length > 1 ? `<label>运行实例<select name="instance_id" required><option value="">请选择实例</option>${instances.map((item) => `<option value="${e(item.id)}" ${selected === item.id ? 'selected' : ''}>${e(item.name || item.id)} · ${item.online ? '在线' : '离线'} · ${e(item.id)}</option>`).join('')}</select></label>` : `<input type="hidden" name="instance_id" value="${e(selected)}">`;
  return `<section class="settings-card tabbit-settings"><div class="section-heading"><div><p class="eyebrow">浏览器自动化</p><h2>Tabbit CLI</h2></div><span class="badge ${state === 'ready' ? 'live' : 'danger'}">${e(labels[state] || labels.error)}</span></div><p class="muted">dsh-tabbit ${e(tabbit?.plugin_version || '0.3.4')} · 浏览器 ${e(tabbit?.browser_version || '未检测到')} · 在线实例 ${e(tabbit?.online_instances ?? 0)}</p>${configTruth}${tabbit?.restart_required ? '<div class="notice warning" role="status">配置已保存，需在研究任务空闲后重启 Runtime 才会应用。</div>' : ''}<form id="tabbit-settings-form"><label class="switch-row"><span><strong>浏览器自动化</strong><small>允许 Agent 按任务使用 tabbit_browser；默认开启。</small></span><input type="checkbox" name="browser_enabled" ${saved.browser_enabled ? 'checked' : ''}></label><label class="switch-row"><span><strong>Tabbit 接管 web_fetch</strong><small>使用真实浏览器登录态获取网页；默认关闭，开启时浏览器自动化必须同时开启。</small></span><input type="checkbox" name="web_fetch_enabled" ${saved.web_fetch_enabled ? 'checked' : ''}></label>${instanceSelect}<div class="button-row"><button class="button primary" type="submit" ${busy ? 'disabled' : ''}>保存 Tabbit 配置</button><button class="button" type="button" data-tabbit-refresh ${busy ? 'disabled' : ''}>刷新诊断</button></div></form><p class="small muted">Research Workbench 不会下载或升级 Tabbit。缺少 CLI、浏览器离线或版本低于 1.9.0 时，请按 <a href="https://github.com/Tabbit-Browser/dsh-tabbit#readme" target="_blank" rel="noopener noreferrer">官方安装说明 ↗</a> 手动处理并重启 Tabbit。</p><p class="small muted">只读调用依赖调用方的 <code>read_only: true</code> 声明，并非对 Playwright 代码的静态证明；写操作会逐次请求原生审批。</p></section>`;
}

function renderSettingsBody(options) {
  const { section, runtime, tabbit, models, runtimeLabel, busy, modelFailures, connections, integrations, localIntegrations, localVerificationTarget, selectedConfiguration, migrationOpen, connectionDetailOpen, hash } = options;
  if (section === 'model') return renderModelSettings({ runtime, models, runtimeLabel, busy, modelFailures });
  if (section === 'local') {
    const localSummary = (integrations?.items || []).filter((item) => item?.scope === 'local').reduce((summary, item) => {
      summary[item.bucket] = (summary[item.bucket] || 0) + 1;
      return summary;
    }, { available: 0, checking: 0, user_action: 0, system_fault: 0, not_delivered: 0 });
    return `${renderTabbitSettings(tabbit, busy)}${renderLocalIntegrationConsole(localIntegrations, { busy, verificationTarget: localVerificationTarget, integrationSummary: localSummary })}`;
  }
  if (section === 'data') {
    return renderConnectionCenter({
      connections,
      selectedId: settingsConnectionId(hash, connections?.sources || [], section),
      configuration: selectedConfiguration,
      migrationOpen,
      detailOpen: connectionDetailOpen,
      scope: 'data',
      busy,
    });
  }
  if (section === 'docs') return renderDocumentationSettings();
  return renderGeneralSettings();
}

export function renderSettingsPage(options = {}) {
  const sources = Array.isArray(options.connections?.sources) ? options.connections.sources : [];
  const section = resolveSettingsSection(options.route, sources);
  const definition = settingsSections.find((item) => item.id === section) || settingsSections[0];
  return `<div class="settings-layout">${renderSettingsNavigation(section)}<section class="settings-page" data-settings-section="${e(section)}">${renderSettingsHeader(definition)}${renderSettingsBody({ ...options, section })}</section></div>`;
}
