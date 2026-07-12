import { apiCall } from './core.js?v=20260712config2';

const rowOriginalNames = new WeakMap();

function element(tag, className = '', text = '') {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text) node.textContent = text;
    return node;
}

function labeledControl(labelText, control, hint = '') {
    const label = element('label', 'config-dynamic-field');
    label.append(element('span', '', labelText), control);
    if (hint) label.append(element('small', 'config-secret-state', hint));
    return label;
}

function input(type, value, ariaLabel) {
    const control = document.createElement('input');
    control.type = type;
    control.value = value ?? '';
    control.setAttribute('aria-label', ariaLabel);
    return control;
}

function select(options, value, ariaLabel) {
    const control = document.createElement('select');
    control.setAttribute('aria-label', ariaLabel);
    options.forEach(([optionValue, label]) => {
        const option = element('option', '', label);
        option.value = optionValue;
        control.append(option);
    });
    control.value = value;
    return control;
}

function removeButton(label) {
    const button = element('button', 'config-remove-row', '删除');
    button.type = 'button';
    button.setAttribute('aria-label', label);
    button.addEventListener('click', () => button.closest('.config-dynamic-row')?.remove());
    return button;
}

function secretHint(secret) {
    if (!secret?.configured) return '未配置';
    return '已配置';
}

function createProviderRow(provider = {}) {
    const row = element('div', 'config-dynamic-row config-provider-row');
    rowOriginalNames.set(row, provider.original_name || '');
    const name = input('text', provider.name, 'Provider 名称');
    name.dataset.field = 'name';
    const protocol = select([
        ['openai_compatible', 'OpenAI 兼容'],
        ['anthropic', 'Anthropic'],
        ['local', '本地模型'],
    ], provider.protocol || 'openai_compatible', 'Provider 协议');
    protocol.dataset.field = 'protocol';
    const baseUrl = input('url', provider.base_url, 'Provider Base URL');
    baseUrl.dataset.field = 'base_url';
    const apiKey = input('password', '', 'Provider API Token');
    apiKey.autocomplete = 'new-password';
    apiKey.placeholder = '留空保留';
    apiKey.dataset.field = 'api_key';
    const clearLabel = element('label', 'config-checkbox config-clear-secret');
    const clear = input('checkbox', '', '显式清除 Provider Token');
    clear.dataset.field = 'clear_api_key';
    clearLabel.append(clear, document.createTextNode('显式清除 Token'));
    row.append(
        labeledControl('名称', name),
        labeledControl('协议', protocol),
        labeledControl('Base URL', baseUrl),
        labeledControl('API Token', apiKey, secretHint(provider.api_key)),
        clearLabel,
        removeButton(`删除 Provider ${provider.name || '新行'}`),
    );
    return row;
}

function createTaskRouteRow(route = {}) {
    const row = element('div', 'config-dynamic-row config-route-row');
    const task = input('text', route.task, '任务名称');
    task.dataset.field = 'task';
    const provider = input('text', route.provider, '任务 Provider');
    provider.dataset.field = 'provider';
    const model = input('text', route.model, '任务模型');
    model.dataset.field = 'model';
    row.append(
        labeledControl('任务', task),
        labeledControl('Provider', provider),
        labeledControl('模型', model),
        removeButton(`删除任务路由 ${route.task || '新行'}`),
    );
    return row;
}

function createZhiqiuAccountRow(account = {}) {
    const row = element('div', 'config-dynamic-row config-zhiqiu-row');
    rowOriginalNames.set(row, account.original_name || '');
    const name = input('text', account.name, '知秋账号名称');
    name.dataset.field = 'name';
    const username = input('text', account.username, '知秋用户名');
    username.autocomplete = 'username';
    username.dataset.field = 'username';
    const password = input('password', '', '知秋密码');
    password.autocomplete = 'new-password';
    password.placeholder = '留空保留';
    password.dataset.field = 'password';
    const clearLabel = element('label', 'config-checkbox config-clear-secret');
    const clear = input('checkbox', '', '显式清除知秋密码');
    clear.dataset.field = 'clear_password';
    clearLabel.append(clear, document.createTextNode('显式清除密码'));
    row.append(
        labeledControl('名称', name),
        labeledControl('用户名', username),
        labeledControl('密码', password, secretHint(account.password)),
        clearLabel,
        removeButton(`删除知秋账号 ${account.name || '新行'}`),
    );
    return row;
}

function renderProviders(providers) {
    const list = document.getElementById('config-provider-list');
    if (!list) return;
    list.replaceChildren(...providers.map(createProviderRow));
}

function renderTaskRoutes(routes) {
    const list = document.getElementById('config-task-route-list');
    if (!list) return;
    list.replaceChildren(...routes.map(createTaskRouteRow));
}

function renderZhiqiuAccounts(accounts) {
    const list = document.getElementById('config-zhiqiu-account-list');
    if (!list) return;
    list.replaceChildren(...accounts.map(createZhiqiuAccountRow));
}

function setFormValues(form, values, fields) {
    fields.forEach(field => {
        const control = form?.elements.namedItem(field);
        if (!control) return;
        if (control.type === 'checkbox') control.checked = Boolean(values[field]);
        else control.value = values[field] ?? '';
    });
}

function setSecretState(selector, secret) {
    const node = document.querySelector(selector);
    if (node) node.textContent = secretHint(secret);
}

function renderReadiness(snapshot) {
    const overall = document.querySelector('[data-readiness="overall"]');
    if (overall) {
        const ready = snapshot.ready_count === snapshot.total_count;
        overall.classList.toggle('ready', ready);
        overall.classList.toggle('missing', !ready);
        overall.querySelector('strong').textContent = `${snapshot.ready_count} / ${snapshot.total_count}`;
        overall.querySelector('small').textContent = ready ? '全部配置就绪' : '仍有配置待补齐';
    }
    ['llm', 'zhiqiu', 'ifind', 'database'].forEach(section => {
        const ready = Boolean(snapshot.readiness?.[section]);
        const card = document.querySelector(`[data-readiness="${section}"]`);
        if (card) {
            card.classList.toggle('ready', ready);
            card.classList.toggle('missing', !ready);
            card.querySelector('strong').textContent = ready ? '已就绪' : '待配置';
        }
        setSectionStatus(section, ready ? '已就绪' : '待配置', ready ? 'ready' : 'missing');
    });
    setSectionStatus('advanced', snapshot.readiness?.advanced ? '已就绪' : '待配置', snapshot.readiness?.advanced ? 'ready' : 'missing');
}

function renderSnapshot(snapshot) {
    renderReadiness(snapshot);
    renderProviders(snapshot.sections.llm.providers || []);
    renderTaskRoutes(snapshot.sections.llm.task_routes || []);
    renderZhiqiuAccounts(snapshot.sections.zhiqiu.accounts || []);

    setFormValues(document.getElementById('config-zhiqiu-form'), snapshot.sections.zhiqiu, [
        'enabled', 'rotation_strategy', 'max_retries', 'retry_delay', 'lease_timeout', 'max_consecutive_failures',
    ]);
    setFormValues(document.getElementById('config-ifind-form'), snapshot.sections.ifind, [
        'username', 'backend', 'http_base_url',
    ]);
    setFormValues(document.getElementById('config-advanced-form'), snapshot.sections.advanced, [
        'log_level', 'log_dir', 'llm_max_workers', 'llm_max_retries', 'chunk_size', 'chunk_overlap', 'long_text_threshold',
    ]);
    document.querySelectorAll('.configuration-page input[type="password"]').forEach(control => { control.value = ''; });
    document.querySelectorAll('.configuration-page .config-clear-secret input').forEach(control => { control.checked = false; });
    setSecretState('[data-secret-state="ifind-password"]', snapshot.sections.ifind.password);
    setSecretState('[data-secret-state="database-url"]', snapshot.sections.database.database_url);
}

function setSectionStatus(section, message, state = '') {
    const node = document.querySelector(`[data-config-status="${section}"]`);
    if (!node) return;
    node.textContent = message;
    node.className = `config-status ${state}`.trim();
}

function showPageMessage(message, state = '') {
    const node = document.getElementById('config-page-message');
    if (!node) return;
    node.replaceChildren(document.createTextNode(message));
    node.className = `config-page-message ${state}`.trim();
}

function formatValidationPath(loc) {
    return Array.isArray(loc) && loc.length ? loc.join('.') : 'section';
}

function showPageError(error, fallback) {
    const node = document.getElementById('config-page-message');
    if (!node) return;
    const details = Array.isArray(error?.details) ? error.details : [];
    if (!details.length) {
        showPageMessage(safeErrorMessage(error, fallback), 'error');
        return;
    }
    const title = element('strong', '', '字段校验失败');
    const list = element('ul', 'config-field-errors');
    details.forEach(detail => {
        const path = formatValidationPath(detail.loc);
        list.append(element('li', '', `${path}: ${detail.msg || '输入值未通过校验'}`));
    });
    node.replaceChildren(title, list);
    node.className = 'config-page-message error';
}

function safeErrorMessage(error, fallback) {
    if (error instanceof Error && typeof error.message === 'string' && error.message.length <= 240 && !error.message.includes('[object Object]')) {
        return error.message;
    }
    return fallback;
}

async function loadConfiguration() {
    showPageMessage('正在读取配置…');
    try {
        const snapshot = await apiCall('GET', '/api/config');
        renderSnapshot(snapshot);
        showPageMessage('配置已刷新', 'ready');
    } catch (error) {
        showPageError(error, '配置读取失败，请稍后重试');
    }
}

function rowValue(row, field) {
    const control = row.querySelector(`[data-field="${field}"]`);
    return control?.type === 'checkbox' ? control.checked : (control?.value ?? '').trim();
}

function collectLlm() {
    const providers = [...document.querySelectorAll('.config-provider-row')].map(row => ({
        original_name: rowOriginalNames.get(row) || undefined,
        name: rowValue(row, 'name'),
        protocol: rowValue(row, 'protocol'),
        base_url: rowValue(row, 'base_url'),
        api_key: rowValue(row, 'api_key'),
        clear_api_key: rowValue(row, 'clear_api_key'),
    }));
    const task_routes = [...document.querySelectorAll('.config-route-row')].map(row => ({
        task: rowValue(row, 'task'),
        provider: rowValue(row, 'provider'),
        model: rowValue(row, 'model'),
    }));
    return { providers, task_routes };
}

function collectZhiqiu() {
    const form = document.getElementById('config-zhiqiu-form');
    const accounts = [...document.querySelectorAll('.config-zhiqiu-row')].map(row => ({
        original_name: rowOriginalNames.get(row) || undefined,
        name: rowValue(row, 'name'),
        username: rowValue(row, 'username'),
        password: rowValue(row, 'password'),
        clear_password: rowValue(row, 'clear_password'),
    }));
    return {
        accounts,
        enabled: form.elements.enabled.checked,
        rotation_strategy: form.elements.rotation_strategy.value,
        max_retries: Number(form.elements.max_retries.value),
        retry_delay: Number(form.elements.retry_delay.value),
        lease_timeout: Number(form.elements.lease_timeout.value),
        max_consecutive_failures: Number(form.elements.max_consecutive_failures.value),
    };
}

function collectIfind() {
    const form = document.getElementById('config-ifind-form');
    return {
        username: form.elements.username.value.trim(),
        password: form.elements.password.value,
        clear_password: form.elements.clear_password.checked,
        backend: form.elements.backend.value,
        http_base_url: form.elements.http_base_url.value.trim(),
    };
}

function collectDatabase() {
    const databaseUrl = document.getElementById('config-database-form').elements.database_url.value;
    if (!databaseUrl) throw new Error('请输入新的数据库连接地址');
    return { database_url: databaseUrl };
}

function collectAdvanced() {
    const form = document.getElementById('config-advanced-form');
    return {
        log_level: form.elements.log_level.value,
        log_dir: form.elements.log_dir.value.trim(),
        llm_max_workers: Number(form.elements.llm_max_workers.value),
        llm_max_retries: Number(form.elements.llm_max_retries.value),
        chunk_size: Number(form.elements.chunk_size.value),
        chunk_overlap: Number(form.elements.chunk_overlap.value),
        long_text_threshold: Number(form.elements.long_text_threshold.value),
    };
}

function collectSection(section) {
    const collectors = { llm: collectLlm, zhiqiu: collectZhiqiu, ifind: collectIfind, database: collectDatabase, advanced: collectAdvanced };
    return collectors[section]();
}

async function saveSection(section) {
    setSectionStatus(section, '保存中…');
    try {
        const payload = collectSection(section);
        const result = await apiCall('PUT', `/api/config/${section}`, payload);
        await loadConfiguration();
        setSectionStatus(section, result.message, result.restart_required ? 'restart' : 'ready');
        showPageMessage(result.message, result.restart_required ? 'restart' : 'ready');
    } catch (error) {
        const message = safeErrorMessage(error, '保存失败，请检查输入字段');
        const firstPath = Array.isArray(error?.details) && error.details.length
            ? formatValidationPath(error.details[0].loc)
            : '';
        setSectionStatus(section, firstPath ? `字段校验失败：${firstPath}` : message, 'error');
        showPageError(error, '保存失败，请检查输入字段');
    }
}

async function testSection(section) {
    setSectionStatus(section, '验证中…');
    try {
        const result = await apiCall('POST', `/api/config/${section}/test`, collectSection(section));
        setSectionStatus(section, result.message, result.success ? 'ready' : 'error');
        showPageMessage(result.message, result.success ? 'ready' : 'error');
    } catch (error) {
        const message = safeErrorMessage(error, '连接验证失败，请检查配置');
        const firstPath = Array.isArray(error?.details) && error.details.length
            ? formatValidationPath(error.details[0].loc)
            : '';
        setSectionStatus(section, firstPath ? `字段校验失败：${firstPath}` : message, 'error');
        showPageError(error, '连接验证失败，请检查配置');
    }
}

function bindConfigurationEvents() {
    const page = document.getElementById('section-config');
    if (!page || page.dataset.bound === 'true') return;
    page.dataset.bound = 'true';
    page.querySelector('[data-add-provider]')?.addEventListener('click', () => {
        document.getElementById('config-provider-list')?.append(createProviderRow());
    });
    page.querySelector('[data-add-task-route]')?.addEventListener('click', () => {
        document.getElementById('config-task-route-list')?.append(createTaskRouteRow());
    });
    page.querySelector('[data-add-zhiqiu-account]')?.addEventListener('click', () => {
        document.getElementById('config-zhiqiu-account-list')?.append(createZhiqiuAccountRow());
    });
    page.querySelectorAll('[data-config-form]').forEach(form => {
        form.addEventListener('submit', event => {
            event.preventDefault();
            saveSection(form.dataset.configForm);
        });
    });
    page.querySelectorAll('[data-config-test]').forEach(button => {
        button.addEventListener('click', () => testSection(button.dataset.configTest));
    });
    document.getElementById('config-refresh')?.addEventListener('click', loadConfiguration);
}

export async function initConfigurationPage() {
    if (!document.getElementById('section-config')) return;
    bindConfigurationEvents();
    await loadConfiguration();
}

export { renderProviders, renderTaskRoutes, renderZhiqiuAccounts };
