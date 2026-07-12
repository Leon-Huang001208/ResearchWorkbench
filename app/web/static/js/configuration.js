import { apiCall } from './core.js?v=20260712config2';

const rowOriginalNames = new WeakMap();
const dirtySections = new Set();
const sectionEditGenerations = new Map();
let configurationInitialized = false;
let configurationReady = false;
let configurationSnapshot = null;
let loadAbortController = null;

export function configurationRequestOptions(options = {}) {
    const csrfToken = globalThis.document
        ?.querySelector('meta[name="alphafoundry-config-token"]')
        ?.content || '';
    return {
        ...options,
        headers: {
            ...(options.headers || {}),
            'X-AlphaFoundry-Config-Token': csrfToken,
        },
    };
}

async function configurationApiCall(method, url, body = null, options = {}) {
    return apiCall(method, url, body, configurationRequestOptions(options));
}

export function createGenerationTracker() {
    let generation = 0;
    return {
        next() {
            generation += 1;
            return generation;
        },
        isLatest(token) {
            return token === generation;
        },
        invalidate() {
            generation += 1;
            return generation;
        },
    };
}

export function createReadinessGate() {
    let ready = false;
    return {
        run(action) {
            if (!ready) return false;
            action();
            return true;
        },
        markReady() {
            ready = true;
        },
        markLoadFailed() {
            return ready;
        },
        isReady() {
            return ready;
        },
    };
}

export function createRequestCoordinator({ onFirstBegin = () => {}, onLastFinish = () => {} } = {}) {
    const active = new Map();
    const generations = new Map();
    let activeCount = 0;
    return {
        begin(section) {
            if (active.has(section)) return null;
            const token = (generations.get(section) || 0) + 1;
            generations.set(section, token);
            active.set(section, token);
            activeCount += 1;
            if (activeCount === 1) onFirstBegin();
            return token;
        },
        isLatest(section, token) {
            return active.get(section) === token && generations.get(section) === token;
        },
        finish(section, token) {
            if (active.get(section) !== token) return;
            active.delete(section);
            activeCount = Math.max(0, activeCount - 1);
            if (activeCount === 0) onLastFinish();
        },
        hasActive() {
            return activeCount > 0;
        },
    };
}

export function normalizeSecretState(value, clear, changedControl) {
    if (changedControl === 'input' && value) {
        return { value, clear: false, disabled: false };
    }
    if (changedControl === 'clear' && clear) {
        return { value: '', clear: true, disabled: true };
    }
    return { value, clear: Boolean(clear), disabled: Boolean(clear) };
}

export function safeConfigurationError(error) {
    const statusMessages = {
        400: '配置无效，请检查输入',
        409: '操作冲突，请稍后重试',
        422: '字段校验失败',
        500: '配置保存失败',
    };
    if (error?.code === 'secret_conflict') {
        return { message: '秘密值与清除选项不能同时提交', details: [] };
    }
    const status = Number(error?.status);
    const details = status === 422 && Array.isArray(error?.details)
        ? error.details.map(detail => ({
            path: formatValidationPath(detail.loc),
            msg: typeof detail.msg === 'string' ? detail.msg.slice(0, 240) : '输入值未通过校验',
        }))
        : [];
    return {
        message: statusMessages[status] || '请求失败，请稍后重试',
        details,
    };
}

const loadGeneration = createGenerationTracker();
const requestCoordinator = createRequestCoordinator({
    onFirstBegin: () => {
        loadAbortController?.abort();
        loadAbortController = null;
        loadGeneration.invalidate();
        setRefreshDisabled(true);
        syncMutationControls();
    },
    onLastFinish: () => {
        setRefreshDisabled(false);
        syncMutationControls();
    },
});

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

function toggleSecretVisibility(secretInput, button) {
    const reveal = secretInput.type === 'password';
    secretInput.type = reveal ? 'text' : 'password';
    button.textContent = reveal ? '隐藏' : '显示';
    button.setAttribute('aria-label', `${reveal ? '隐藏' : '显示'}${secretInput.getAttribute('aria-label') || '敏感值'}`);
}

async function copySecretValue(secretInput) {
    if (!secretInput.value) {
        showPageMessage('没有可复制的已保存值', 'error');
        return;
    }
    try {
        await navigator.clipboard.writeText(secretInput.value);
        showPageMessage('已复制到剪贴板', 'ready');
    } catch {
        showPageMessage('复制失败，请手动选择复制', 'error');
    }
}

function createSecretControl(secretInput) {
    const control = element('span', 'config-secret-control');
    const toggle = element('button', 'config-secret-action', '显示');
    const copy = element('button', 'config-secret-action', '复制');
    toggle.type = 'button';
    copy.type = 'button';
    toggle.setAttribute('data-secret-toggle', '');
    copy.setAttribute('data-secret-copy', '');
    toggle.setAttribute('aria-label', `显示${secretInput.getAttribute('aria-label') || '敏感值'}`);
    copy.setAttribute('aria-label', `复制${secretInput.getAttribute('aria-label') || '敏感值'}`);
    toggle.addEventListener('click', () => toggleSecretVisibility(secretInput, toggle));
    copy.addEventListener('click', () => copySecretValue(secretInput));
    control.append(secretInput, toggle, copy);
    return control;
}

function bindSecretActions(scope) {
    scope?.querySelectorAll?.('[data-secret-toggle]').forEach(button => {
        if (button.dataset.bound === 'true') return;
        button.dataset.bound = 'true';
        const secretInput = button.closest('.config-secret-control')?.querySelector('input');
        if (secretInput) button.addEventListener('click', () => toggleSecretVisibility(secretInput, button));
    });
    scope?.querySelectorAll?.('[data-secret-copy]').forEach(button => {
        if (button.dataset.bound === 'true') return;
        button.dataset.bound = 'true';
        const secretInput = button.closest('.config-secret-control')?.querySelector('input');
        if (secretInput) button.addEventListener('click', () => copySecretValue(secretInput));
    });
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
    button.disabled = !configurationReady || requestCoordinator.hasActive();
    button.setAttribute('aria-label', label);
    button.addEventListener('click', () => {
        const row = button.closest('.config-dynamic-row');
        if (row) markSectionDirty(row);
        row?.remove();
    });
    return button;
}

function secretHint(secret) {
    if (!secret?.configured) return '未配置';
    return '已配置';
}

function applySecretState(secretInput, clearInput, changedControl) {
    const state = normalizeSecretState(secretInput.value, clearInput.checked, changedControl);
    secretInput.value = state.value;
    secretInput.disabled = state.disabled;
    clearInput.checked = state.clear;
}

function bindSecretPair(secretInput, clearInput) {
    if (!secretInput || !clearInput) return;
    secretInput.addEventListener('input', () => applySecretState(secretInput, clearInput, 'input'));
    clearInput.addEventListener('change', () => applySecretState(secretInput, clearInput, 'clear'));
    applySecretState(secretInput, clearInput, 'initial');
}

function collectSecretPair(secretInput, clearInput) {
    if (secretInput.value && clearInput.checked) {
        const error = new Error('secret conflict');
        error.code = 'secret_conflict';
        throw error;
    }
    return { value: secretInput.value, clear: clearInput.checked };
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
    const apiKey = input('password', provider.api_key?.value || '', 'Provider API Token');
    apiKey.autocomplete = 'new-password';
    apiKey.placeholder = '未配置';
    apiKey.dataset.field = 'api_key';
    const clearLabel = element('label', 'config-checkbox config-clear-secret');
    const clear = input('checkbox', '', '显式清除 Provider Token');
    clear.dataset.field = 'clear_api_key';
    bindSecretPair(apiKey, clear);
    clearLabel.append(clear, document.createTextNode('清除'));
    const actions = element('div', 'config-row-actions');
    actions.append(clearLabel, removeButton(`删除 Provider ${provider.name || '新行'}`));
    row.append(
        labeledControl('名称', name),
        labeledControl('协议', protocol),
        labeledControl('Base URL', baseUrl),
        labeledControl('API Token', createSecretControl(apiKey), secretHint(provider.api_key)),
        actions,
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
    const password = input('password', account.password?.value || '', '知秋密码');
    password.autocomplete = 'new-password';
    password.placeholder = '未配置';
    password.dataset.field = 'password';
    const clearLabel = element('label', 'config-checkbox config-clear-secret');
    const clear = input('checkbox', '', '显式清除知秋密码');
    clear.dataset.field = 'clear_password';
    bindSecretPair(password, clear);
    clearLabel.append(clear, document.createTextNode('清除'));
    const actions = element('div', 'config-row-actions');
    actions.append(clearLabel, removeButton(`删除知秋账号 ${account.name || '新行'}`));
    row.append(
        labeledControl('名称', name),
        labeledControl('用户名', username),
        labeledControl('密码', createSecretControl(password), secretHint(account.password)),
        actions,
    );
    return row;
}

function createIfindAccountRow(account = {}) {
    const row = element('div', 'config-dynamic-row config-ifind-row');
    rowOriginalNames.set(row, account.original_name || '');
    const name = input('text', account.name, 'iFinD 账号名称');
    name.dataset.field = 'name';
    const username = input('text', account.username, 'iFinD 用户名');
    username.autocomplete = 'username';
    username.dataset.field = 'username';
    const password = input('password', account.password?.value || '', 'iFinD 密码');
    password.autocomplete = 'new-password';
    password.placeholder = '未配置';
    password.dataset.field = 'password';
    const clearLabel = element('label', 'config-checkbox config-clear-secret');
    const clear = input('checkbox', '', '显式清除 iFinD 密码');
    clear.dataset.field = 'clear_password';
    bindSecretPair(password, clear);
    clearLabel.append(clear, document.createTextNode('清除'));
    const actions = element('div', 'config-row-actions');
    actions.append(clearLabel, removeButton(`删除 iFinD 账号 ${account.name || '新行'}`));
    row.append(
        labeledControl('名称', name),
        labeledControl('用户名', username),
        labeledControl('密码', createSecretControl(password), secretHint(account.password)),
        actions,
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

function renderIfindAccounts(accounts) {
    const list = document.getElementById('config-ifind-account-list');
    if (!list) return;
    list.replaceChildren(...accounts.map(createIfindAccountRow));
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
    configurationSnapshot = snapshot;
    renderReadiness(snapshot);
    Object.entries(snapshot.sections).forEach(([section, values]) => {
        if (!dirtySections.has(section)) renderSection(section, values);
    });
}

function renderSection(section, values) {
    if (section === 'llm') {
        renderProviders(values.providers || []);
        renderTaskRoutes(values.task_routes || []);
    } else if (section === 'zhiqiu') {
        renderZhiqiuAccounts(values.accounts || []);
        setFormValues(document.getElementById('config-zhiqiu-form'), values, [
            'enabled', 'rotation_strategy', 'max_retries', 'retry_delay', 'lease_timeout', 'max_consecutive_failures',
        ]);
    } else if (section === 'ifind') {
        renderIfindAccounts(values.accounts || []);
        setFormValues(document.getElementById('config-ifind-form'), values, ['backend', 'http_base_url']);
    } else if (section === 'database') {
        setSecretState('[data-secret-state="database-url"]', values.database_url);
        const form = document.getElementById('config-database-form');
        if (form) form.elements.database_url.value = values.database_url?.value || '';
    } else if (section === 'advanced') {
        setFormValues(document.getElementById('config-advanced-form'), values, [
            'log_level', 'log_dir', 'llm_max_workers', 'llm_max_retries', 'chunk_size', 'chunk_overlap', 'long_text_threshold',
        ]);
    }
    dirtySections.delete(section);
}

function deriveSectionReadiness(section, values) {
    if (section === 'llm') return (values.providers || []).some(item => item.protocol === 'local' || item.api_key?.configured);
    if (section === 'zhiqiu') return (values.accounts || []).some(item => item.password?.configured);
    if (section === 'ifind') return (values.accounts || []).some(item => item.username && item.password?.configured);
    if (section === 'database') return Boolean(values.database_url?.configured);
    return true;
}

function applySectionResponse(section, values, renderValues = true) {
    if (renderValues) {
        renderSection(section, values);
    } else {
        updateOriginalNameMappings(section, values);
    }
    if (configurationSnapshot) {
        configurationSnapshot.sections[section] = values;
        configurationSnapshot.readiness[section] = deriveSectionReadiness(section, values);
        configurationSnapshot.ready_count = Object.values(configurationSnapshot.readiness).filter(Boolean).length;
        renderReadiness(configurationSnapshot);
    }
}

function updateOriginalNameMappings(section, values) {
    if (section === 'llm') {
        document.querySelectorAll('.config-provider-row').forEach((row, index) => {
            const provider = values.providers?.[index];
            if (provider) rowOriginalNames.set(row, provider.original_name || provider.name || '');
        });
    } else if (section === 'zhiqiu') {
        document.querySelectorAll('.config-zhiqiu-row').forEach((row, index) => {
            const account = values.accounts?.[index];
            if (account) rowOriginalNames.set(row, account.original_name || account.name || '');
        });
    } else if (section === 'ifind') {
        document.querySelectorAll('.config-ifind-row').forEach((row, index) => {
            const account = values.accounts?.[index];
            if (account) rowOriginalNames.set(row, account.original_name || account.name || '');
        });
    }
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

function showPageError(error) {
    const node = document.getElementById('config-page-message');
    if (!node) return;
    const safe = safeConfigurationError(error);
    if (!safe.details.length) {
        showPageMessage(safe.message, 'error');
        return;
    }
    const title = element('strong', '', safe.message);
    const list = element('ul', 'config-field-errors');
    safe.details.forEach(detail => {
        list.append(element('li', '', `${detail.path}: ${detail.msg}`));
    });
    node.replaceChildren(title, list);
    node.className = 'config-page-message error';
}

async function loadConfiguration({ discardDirty = false } = {}) {
    if (requestCoordinator.hasActive()) {
        showPageMessage('配置保存或验证进行中，请稍后刷新', 'error');
        return false;
    }
    const token = loadGeneration.next();
    loadAbortController?.abort();
    const controller = new AbortController();
    loadAbortController = controller;
    showPageMessage('');
    try {
        const snapshot = await configurationApiCall('GET', '/api/config', null, { signal: controller.signal });
        if (!loadGeneration.isLatest(token)) return;
        if (discardDirty) dirtySections.clear();
        renderSnapshot(snapshot);
        configurationReady = true;
        syncMutationControls();
        showPageMessage('');
        return true;
    } catch (error) {
        if (error?.name === 'AbortError' || !loadGeneration.isLatest(token)) return;
        if (!configurationSnapshot) {
            configurationReady = false;
            syncMutationControls();
        }
        showPageError(error);
    } finally {
        if (loadGeneration.isLatest(token)) loadAbortController = null;
    }
}

function rowValue(row, field) {
    const control = row.querySelector(`[data-field="${field}"]`);
    return control?.type === 'checkbox' ? control.checked : (control?.value ?? '').trim();
}

function collectLlm() {
    const providers = [...document.querySelectorAll('.config-provider-row')].map(row => {
        const secret = collectSecretPair(
            row.querySelector('[data-field="api_key"]'),
            row.querySelector('[data-field="clear_api_key"]'),
        );
        return {
            original_name: rowOriginalNames.get(row) || undefined,
            name: rowValue(row, 'name'),
            protocol: rowValue(row, 'protocol'),
            base_url: rowValue(row, 'base_url'),
            api_key: secret.value,
            clear_api_key: secret.clear,
        };
    });
    const task_routes = [...document.querySelectorAll('.config-route-row')].map(row => ({
        task: rowValue(row, 'task'),
        provider: rowValue(row, 'provider'),
        model: rowValue(row, 'model'),
    }));
    return { providers, task_routes };
}

function collectZhiqiu() {
    const form = document.getElementById('config-zhiqiu-form');
    const accounts = [...document.querySelectorAll('.config-zhiqiu-row')].map(row => {
        const secret = collectSecretPair(
            row.querySelector('[data-field="password"]'),
            row.querySelector('[data-field="clear_password"]'),
        );
        return {
            original_name: rowOriginalNames.get(row) || undefined,
            name: rowValue(row, 'name'),
            username: rowValue(row, 'username'),
            password: secret.value,
            clear_password: secret.clear,
        };
    });
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
    const accounts = [...document.querySelectorAll('.config-ifind-row')].map(row => {
        const secret = collectSecretPair(
            row.querySelector('[data-field="password"]'),
            row.querySelector('[data-field="clear_password"]'),
        );
        return {
            original_name: rowOriginalNames.get(row) || undefined,
            name: rowValue(row, 'name'),
            username: rowValue(row, 'username'),
            password: secret.value,
            clear_password: secret.clear,
        };
    });
    return {
        accounts,
        backend: form.elements.backend.value,
        http_base_url: form.elements.http_base_url.value.trim(),
    };
}

function collectDatabase() {
    const databaseUrl = document.getElementById('config-database-form').elements.database_url.value;
    if (!databaseUrl) {
        const error = new Error('invalid configuration');
        error.status = 400;
        throw error;
    }
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

function setSectionBusy(section, busy) {
    const form = document.querySelector(`[data-config-form="${section}"]`);
    form?.querySelectorAll('button').forEach(button => { button.disabled = busy; });
}

function setRefreshDisabled(disabled) {
    const button = document.getElementById('config-refresh');
    if (button) button.disabled = disabled;
}

function syncMutationControls() {
    const page = document.getElementById('section-config');
    if (!page) return;
    const disabled = !configurationReady || requestCoordinator.hasActive();
    page.querySelectorAll(
        '[data-config-save], [data-add-provider], [data-add-task-route], [data-add-zhiqiu-account], [data-add-ifind-account], .config-remove-row',
    ).forEach(button => { button.disabled = disabled; });
}

async function saveSection(section) {
    if (!configurationReady) {
        showPageMessage('配置尚未加载完成，暂时无法保存或验证', 'error');
        return;
    }
    const token = requestCoordinator.begin(section);
    if (token === null) return;
    const submittedEditGeneration = sectionEditGenerations.get(section) || 0;
    setSectionBusy(section, true);
    setSectionStatus(section, '保存中…');
    try {
        const payload = collectSection(section);
        const result = await configurationApiCall('PUT', `/api/config/${section}`, payload);
        if (!requestCoordinator.isLatest(section, token)) return;
        const editedWhileSaving = (sectionEditGenerations.get(section) || 0) !== submittedEditGeneration;
        applySectionResponse(section, result.section, !editedWhileSaving);
        const message = result.restart_required ? '重启后生效' : '配置已生效';
        setSectionStatus(section, message, result.restart_required ? 'restart' : 'ready');
        showPageMessage(message, result.restart_required ? 'restart' : 'ready');
    } catch (error) {
        if (!requestCoordinator.isLatest(section, token)) return;
        const safe = safeConfigurationError(error);
        const firstPath = safe.details[0]?.path || '';
        setSectionStatus(section, firstPath ? `字段校验失败：${firstPath}` : safe.message, 'error');
        showPageError(error);
    } finally {
        const latest = requestCoordinator.isLatest(section, token);
        requestCoordinator.finish(section, token);
        if (latest) setSectionBusy(section, !configurationReady || requestCoordinator.hasActive());
    }
}

async function testSection(section) {
    if (!configurationReady) {
        showPageMessage('配置尚未加载完成，暂时无法保存或验证', 'error');
        return;
    }
    const token = requestCoordinator.begin(section);
    if (token === null) return;
    setSectionBusy(section, true);
    setSectionStatus(section, '验证中…');
    try {
        const result = await configurationApiCall('POST', `/api/config/${section}/test`, collectSection(section));
        if (!requestCoordinator.isLatest(section, token)) return;
        const message = result.success ? '连接验证成功' : '连接验证失败';
        setSectionStatus(section, message, result.success ? 'ready' : 'error');
        showPageMessage(message, result.success ? 'ready' : 'error');
    } catch (error) {
        if (!requestCoordinator.isLatest(section, token)) return;
        const safe = safeConfigurationError(error);
        const firstPath = safe.details[0]?.path || '';
        setSectionStatus(section, firstPath ? `字段校验失败：${firstPath}` : safe.message, 'error');
        showPageError(error);
    } finally {
        const latest = requestCoordinator.isLatest(section, token);
        requestCoordinator.finish(section, token);
        if (latest) setSectionBusy(section, !configurationReady || requestCoordinator.hasActive());
    }
}

function markSectionDirty(target) {
    const form = target.closest?.('[data-config-form]');
    const section = form?.dataset.configForm;
    if (!section) return;
    dirtySections.add(section);
    sectionEditGenerations.set(section, (sectionEditGenerations.get(section) || 0) + 1);
}

async function refreshConfiguration() {
    if (requestCoordinator.hasActive()) {
        showPageMessage('配置保存或验证进行中，请稍后刷新', 'error');
        return;
    }
    if (dirtySections.size && !window.confirm('刷新会丢弃尚未保存的修改，是否继续？')) return;
    await loadConfiguration({ discardDirty: true });
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
    page.querySelector('[data-add-ifind-account]')?.addEventListener('click', () => {
        document.getElementById('config-ifind-account-list')?.append(createIfindAccountRow());
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
    bindSecretActions(page);
    page.addEventListener('input', event => markSectionDirty(event.target));
    page.addEventListener('change', event => markSectionDirty(event.target));
    page.addEventListener('click', event => {
        if (event.target.closest?.('[data-add-provider], [data-add-task-route], [data-add-zhiqiu-account], [data-add-ifind-account], .config-remove-row')) {
            markSectionDirty(event.target);
        }
    });
    syncMutationControls();
}

export async function initConfigurationPage() {
    if (!document.getElementById('section-config')) return;
    bindConfigurationEvents();
    if (configurationInitialized) return;
    configurationInitialized = true;
    await loadConfiguration();
}

export { renderProviders, renderTaskRoutes, renderZhiqiuAccounts, renderIfindAccounts };
