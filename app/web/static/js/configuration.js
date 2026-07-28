let _configToken = null;

async function fetchConfigToken() {
    try {
        const resp = await fetch('/api/config/token', { cache: 'no-store' });
        if (!resp.ok) return;
        const data = await resp.json();
        if (typeof data.token === 'string' && data.token.length > 0) {
            _configToken = data.token;
        }
    } catch (e) {
        // 静默失败，降级到 meta 标签
        console.warn('[config] fetchConfigToken failed, falling back to meta token', e);
    }
}

const rowOriginalNames = new WeakMap();
const dirtySections = new Set();
const sectionEditGenerations = new Map();
let configurationInitialized = false;
let configurationReady = false;
let configurationSnapshot = null;
let loadAbortController = null;
let initialLoadRetryCount = 0;
let dynamicLockMessageSequence = 0;
const connectionStateBySection = new Map();
const ONBOARDING_SECTIONS = ['llm', 'database', 'zhiqiu', 'ifind', 'web_search'];
let databaseRuntimeReadiness = null;
let configurationInitializationPromise = null;
const LOCKED_FIELD_MESSAGE = '此项由当前启动配置管理，不能在这里修改。';
const LOCKED_COLLECTION_MESSAGE = '该组由当前启动配置管理，不能在这里修改。';
const STATIC_LOCK_FIELD_KEYS = {
    advanced: {
        log_level: 'LOG_LEVEL',
        log_dir: 'LOG_DIR',
        llm_max_workers: 'LLM_EXTRACT_MAX_WORKERS',
        llm_max_retries: 'LLM_EXTRACT_MAX_RETRIES',
        chunk_size: 'LLM_EXTRACT_CHUNK_SIZE',
        chunk_overlap: 'LLM_EXTRACT_CHUNK_OVERLAP',
        long_text_threshold: 'LLM_EXTRACT_LONG_TEXT_THRESHOLD',
    },
    database: { database_url: 'DATABASE_URL' },
    web_search: {
        provider: 'WEB_SEARCH_PROVIDER',
        rotation_strategy: 'WEB_SEARCH_KEY_ROTATION',
        quota_limit: 'WEB_SEARCH_KEY_QUOTA_LIMIT',
        max_results: 'WEB_SEARCH_MAX_RESULTS',
        timeout: 'WEB_SEARCH_TIMEOUT',
    },
};
const COLLECTION_LOCK_KEYS = {
    zhiqiu: ['ZQ_ACCOUNTS_JSON', 'ZQ_ACCOUNTS'],
    ifind: ['IFIND_ACCOUNTS_JSON', 'IFIND_USERNAME', 'IFIND_PASSWORD'],
    web_search: ['WEB_SEARCH_API_KEYS', 'TAVILY_API_KEY', 'BING_API_KEY'],
};

export function isEnvironmentLocked(key, environmentLockedFields = configurationSnapshot?.environment_locked_fields || []) {
    return environmentLockedFields.includes(key);
}

export function filterEnvironmentLockedPayload(
    section,
    payload,
    environmentLockedFields = configurationSnapshot?.environment_locked_fields || [],
) {
    const filteredPayload = { ...payload };
    Object.entries(STATIC_LOCK_FIELD_KEYS[section] || {}).forEach(([field, key]) => {
        if (isEnvironmentLocked(key, environmentLockedFields)) delete filteredPayload[field];
    });
    if (COLLECTION_LOCK_KEYS[section]?.some(key => isEnvironmentLocked(key, environmentLockedFields))) {
        delete filteredPayload.accounts;
    }
    return filteredPayload;
}

export function configurationRequestOptions(options = {}) {
    const metaToken = globalThis.document
        ?.querySelector('meta[name="alphafoundry-config-token"]')
        ?.content || '';
    const csrfToken = _configToken || metaToken;
    return {
        ...options,
        headers: {
            ...(options.headers || {}),
            'X-AlphaFoundry-Config-Token': csrfToken,
        },
    };
}

// 配置面专属错误：携带 HTTP status 与后端返回的结构化字段，
// 供 safeConfigurationError 按 status 给出针对性文案（403/400/409/422/500）。
class ConfigurationApiError extends Error {
    constructor(message, { status = 0, code = null, details = null } = {}) {
        super(message);
        this.name = 'ConfigurationApiError';
        this.status = status;
        this.code = code;
        this.details = details;
    }
}

async function configurationApiCall(method, url, body = null, options = {}) {
    const csrfOpts = configurationRequestOptions(options);
    const opts = {
        method,
        signal: options.signal,
        ...csrfOpts,
        headers: {
            'Content-Type': 'application/json',
            ...(csrfOpts.headers || {}),
            ...(options.headers || {}),
        },
    };
    if (body) opts.body = JSON.stringify(body);
    let resp;
    try {
        resp = await fetch(url, opts);
    } catch (e) {
        if (e?.name === 'AbortError') throw e;
        throw new ConfigurationApiError('网络请求失败，请检查本地服务是否运行', {});
    }
    if (!resp.ok) {
        const payload = await resp.json().catch(() => ({ detail: resp.statusText }));
        const detail = payload?.detail ?? payload?.error ?? payload?.message ?? resp.statusText;
        throw new ConfigurationApiError(
            typeof detail === 'string' ? detail : `HTTP ${resp.status}`,
            {
                status: resp.status,
                code: payload?.code ?? null,
                details: Array.isArray(detail) ? detail : (Array.isArray(payload?.details) ? payload.details : null),
            },
        );
    }
    return resp.json();
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
        403: '会话已失效或访问来源不被信任，请通过 http://127.0.0.1:8765/ 打开后重试',
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
        syncMutationControls();
    },
    onLastFinish: () => {
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

function createSecretControl(secretInput, secret = {}) {
    const control = element('span', 'config-secret-control');
    const configured = Boolean(secret?.configured);
    const secretLabel = secretInput.getAttribute('aria-label') || '敏感值';
    const replace = element('button', 'config-secret-action', configured ? '替换密钥' : '设置密钥');
    const clear = element('button', 'config-secret-action', '清空密钥');

    secretInput.value = '';
    secretInput.disabled = configured;
    secretInput.dataset.secretClear = 'false';
    secretInput.dataset.secretConfigured = String(configured);
    replace.type = 'button';
    clear.type = 'button';
    clear.disabled = !configured;
    replace.setAttribute('data-secret-replace', '');
    clear.setAttribute('data-secret-clear', '');
    replace.setAttribute('aria-label', `${configured ? '替换' : '设置'}${secretLabel}`);
    clear.setAttribute('aria-label', `清空${secretLabel}`);
    replace.addEventListener('click', () => {
        secretInput.disabled = false;
        secretInput.dataset.secretClear = 'false';
        clear.disabled = false;
        markSecretControlDirty(secretInput);
        secretInput.focus();
    });
    clear.addEventListener('click', () => {
        secretInput.value = '';
        secretInput.disabled = true;
        secretInput.dataset.secretClear = 'true';
        clear.disabled = false;
        markSecretControlDirty(secretInput);
    });
    secretInput.addEventListener('input', () => {
        if (!secretInput.value) return;
        secretInput.dataset.secretClear = 'false';
        clear.disabled = false;
    });
    control.append(secretInput, replace, clear);
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
    const button = element('button', 'config-remove-row', '移除');
    button.type = 'button';
    button.disabled = !configurationReady || requestCoordinator.hasActive();
    button.setAttribute('aria-label', label);
    button.addEventListener('click', () => {
        const row = button.closest('.config-dynamic-row');
        const form = row?.closest('[data-config-form]');
        const section = form?.dataset.configForm;
        if (row) markSectionDirty(form || row);
        row?.remove();
        restoreEmptyCollectionState(form, section);
    });
    return button;
}

function secretHint(secret) {
    if (!secret?.configured) return '未配置';
    return '已配置';
}

function collectSecretPair(secretInput) {
    if (!secretInput) return { value: null, clear: false };
    const value = secretInput.value;
    const clear = secretInput.dataset.secretClear === 'true';
    return { value: clear || value === '' ? null : value, clear };
}

function markSecretControlDirty(secretInput) {
    const form = secretInput.closest('[data-config-form]');
    if (!form) return;
    markSectionDirty(form);
    modalDirty = true;
    syncModalButtons();
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
    apiKey.placeholder = '未配置';
    apiKey.dataset.field = 'api_key';
    const actions = element('div', 'config-row-actions');
    actions.append(removeButton(`移除 Provider ${provider.name || '新行'}`));
    row.append(
        labeledControl('名称', name),
        labeledControl('协议', protocol),
        labeledControl('Base URL', baseUrl),
        labeledControl('API Token', createSecretControl(apiKey, provider.api_key), secretHint(provider.api_key)),
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
    const actions = element('div', 'config-row-actions');
    actions.append(removeButton(`移除任务路由 ${route.task || '新行'}`));
    row.append(
        labeledControl('任务', task),
        labeledControl('Provider', provider),
        labeledControl('模型', model),
        actions,
    );
    return row;
}

function createZhiqiuAccountRow(account = {}) {
    const row = element('div', 'config-dynamic-row config-zhiqiu-row');
    rowOriginalNames.set(row, account.original_name || '');
    const name = input('text', account.name, '知丘账号名称');
    name.dataset.field = 'name';
    const username = input('text', account.username, '知丘用户名');
    username.autocomplete = 'username';
    username.dataset.field = 'username';
    const password = input('password', '', '知丘密码');
    password.autocomplete = 'new-password';
    password.placeholder = '未配置';
    password.dataset.field = 'password';
    const actions = element('div', 'config-row-actions');
    actions.append(removeButton(`移除知丘账号 ${account.name || '新行'}`));
    row.append(
        labeledControl('名称', name),
        labeledControl('用户名', username),
        labeledControl('密码', createSecretControl(password, account.password), secretHint(account.password)),
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
    const password = input('password', '', 'iFinD 密码');
    password.autocomplete = 'new-password';
    password.placeholder = '未配置';
    password.dataset.field = 'password';
    const actions = element('div', 'config-row-actions');
    actions.append(removeButton(`移除 iFinD 账号 ${account.name || '新行'}`));
    row.append(
        labeledControl('名称', name),
        labeledControl('用户名', username),
        labeledControl('密码', createSecretControl(password, account.password), secretHint(account.password)),
        actions,
    );
    return row;
}

function renderProviders(providers) {
    const list = document.getElementById('config-provider-list');
    if (!list) return;
    list.replaceChildren(...providers.map(createProviderRow));
    applyProviderRowLocks();
}

function renderTaskRoutes(routes) {
    const list = document.getElementById('config-task-route-list');
    if (!list) return;
    list.replaceChildren(...routes.map(createTaskRouteRow));
    applyTaskRouteLocks();
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

function createWebSearchKeyRow(account = {}) {
    const row = element('div', 'config-dynamic-row config-web_search-row');
    rowOriginalNames.set(row, account.original_name || '');
    const name = input('text', account.name, 'Key 名称');
    name.dataset.field = 'name';
    const key = input('password', '', 'API Key');
    key.autocomplete = 'new-password';
    key.placeholder = 'tvly-... 或 bing-key...';
    key.dataset.field = 'key';
    const hint = secretHint(account.key);
    const stateBadge = element('span', 'config-secret-state' + (hint === '已配置' ? ' configured' : ''), hint);
    stateBadge.dataset.field = 'state';
    const actions = element('div', 'config-row-actions');
    actions.append(removeButton(`移除 Key ${account.name || '新行'}`));
    row.append(
        labeledControl('名称', name),
        labeledControl('Key', createSecretControl(key, account.key)),
        stateBadge,
        actions,
    );
    return row;
}

function renderWebSearchKeys(accounts) {
    const list = document.getElementById('config-web_search-key-list');
    if (!list) return;
    list.replaceChildren(...accounts.map(createWebSearchKeyRow));
}

function createEmptyCollectionState(section) {
    const messages = {
        zhiqiu: '尚未添加账号。新增账号后，可在此管理轮询与重试策略。',
        ifind: '尚未添加账号。新增账号后，可在此配置 iFinD 连接方式。',
        web_search: '尚未添加 API Key。新增 Key 后，可在此配置搜索参数。',
    };
    const message = messages[section];
    if (!message) return null;
    const state = element('p', 'config-empty-collection', message);
    state.setAttribute('role', 'status');
    return state;
}

function renderEmptyCollectionState(form, section, accounts) {
    if ((accounts || []).length || form.querySelector('.config-empty-collection')) return;
    const collection = {
        zhiqiu: { listId: 'config-zhiqiu-account-list' },
        ifind: { listId: 'config-ifind-account-list' },
        web_search: { listId: 'config-web_search-key-list' },
    }[section];
    const list = collection && form.querySelector(`#${collection.listId}`);
    const state = createEmptyCollectionState(section);
    if (list && state) list.append(state);
}

function removeEmptyCollectionState(form) {
    form.querySelector('.config-empty-collection')?.remove();
}

function restoreEmptyCollectionState(form, section) {
    if (!form || !section || form.querySelector('.config-empty-collection')) return;
    const collection = {
        zhiqiu: { listId: 'config-zhiqiu-account-list', rowSelector: '.config-zhiqiu-row' },
        ifind: { listId: 'config-ifind-account-list', rowSelector: '.config-ifind-row' },
        web_search: { listId: 'config-web_search-key-list', rowSelector: '.config-web_search-row' },
    }[section];
    const list = collection && form.querySelector(`#${collection.listId}`);
    if (list && !list.querySelector(collection.rowSelector)) {
        renderEmptyCollectionState(form, section, []);
    }
}

function syncEmptyCollectionState(section, accounts) {
    const form = document.getElementById(`config-${section}-form`);
    if (!form) return;
    removeEmptyCollectionState(form);
    renderEmptyCollectionState(form, section, accounts);
}

function addControlDescription(control, messageId) {
    if (!control || !messageId) return;
    const describedBy = new Set((control.getAttribute('aria-describedby') || '').split(/\s+/).filter(Boolean));
    describedBy.add(messageId);
    control.setAttribute('aria-describedby', [...describedBy].join(' '));
}

function removeControlDescription(control, messageId) {
    if (!control || !messageId) return;
    const describedBy = new Set((control.getAttribute('aria-describedby') || '').split(/\s+/).filter(Boolean));
    describedBy.delete(messageId);
    if (describedBy.size) control.setAttribute('aria-describedby', [...describedBy].join(' '));
    else control.removeAttribute('aria-describedby');
}

function lockControl(control, message = null) {
    if (!control) return false;
    const changed = !control.disabled;
    control.disabled = true;
    control.closest('.config-secret-control')?.querySelectorAll('[data-secret-replace], [data-secret-clear]').forEach(button => {
        button.disabled = true;
    });
    control.closest('label')?.classList.add('environment-locked');
    addControlDescription(control, message?.id);
    return changed;
}

function createDynamicLockMessage(row) {
    const existingMessage = row.querySelector('.config-dynamic-lock-message');
    if (existingMessage) return existingMessage;
    const message = element('p', 'config-dynamic-lock-message', LOCKED_COLLECTION_MESSAGE);
    message.id = `config-dynamic-lock-message-${++dynamicLockMessageSequence}`;
    row.prepend(message);
    return message;
}

function setDynamicRowLocked(row, lockedControls) {
    const businessControls = [...row.querySelectorAll('[data-field]')];
    const lockedControlSet = new Set(lockedControls);
    const fullyLocked = businessControls.length > 0
        && businessControls.every(control => lockedControlSet.has(control) && control.disabled);
    const existingMessage = row.querySelector('.config-dynamic-lock-message');

    if (!fullyLocked) {
        delete row.dataset.configLocked;
        row.classList.remove('config-dynamic-row-locked');
        businessControls.forEach(control => removeControlDescription(control, existingMessage?.id));
        existingMessage?.remove();
        return false;
    }

    row.dataset.configLocked = 'true';
    row.classList.add('config-dynamic-row-locked');
    row.querySelectorAll('.config-remove-row').forEach(button => { button.disabled = true; });
    const message = createDynamicLockMessage(row);
    businessControls.forEach(control => addControlDescription(control, message.id));
    setModalLockNote(true);
    return true;
}

function showCollectionLockMessage(button) {
    const header = button?.closest('.config-subsection-header');
    if (!header) return;
    const existingMessage = header.querySelector('.config-collection-lock-message');
    const message = existingMessage || element('p', 'config-collection-lock-message', LOCKED_COLLECTION_MESSAGE);
    if (!message.id) message.id = `config-collection-lock-message-${++dynamicLockMessageSequence}`;
    if (!existingMessage) header.querySelector('h4')?.insertAdjacentElement('afterend', message);
}

function applyProviderRowLocks() {
    const lockedFields = configurationSnapshot?.environment_locked_fields || [];
    const providerFieldSuffixes = {
        name: 'NAME',
        protocol: 'PROTOCOL',
        base_url: 'BASE_URL',
        api_key: 'API_KEY',
    };
    document.querySelectorAll('.config-provider-row').forEach((row, rowIndex) => {
        const index = rowIndex + 1;
        const prefix = `LLM_PROVIDER_${index}_`;
        const lockedControls = [];
        Object.entries(providerFieldSuffixes).forEach(([field, suffix]) => {
            const control = row.querySelector(`[data-field="${field}"]`);
            const locked = isEnvironmentLocked(`${prefix}${suffix}`, lockedFields);
            if (locked) {
                lockControl(control);
                if (control?.disabled) lockedControls.push(control);
            }
        });
        setDynamicRowLocked(row, lockedControls);
    });
}

function applyTaskRouteLocks() {
    const lockedFields = configurationSnapshot?.environment_locked_fields || [];
    document.querySelectorAll('.config-route-row').forEach(row => {
        const task = rowValue(row, 'task');
        const providerControl = row.querySelector('[data-field="provider"]');
        const modelControl = row.querySelector('[data-field="model"]');
        const providerLocked = task && isEnvironmentLocked(`TASK_${task.toUpperCase()}_PROVIDER`, lockedFields);
        const modelLocked = task && isEnvironmentLocked(`TASK_${task.toUpperCase()}_MODEL`, lockedFields);
        const lockedControls = [];

        if (providerLocked) {
            lockControl(providerControl);
            if (providerControl?.disabled) lockedControls.push(providerControl);
        }
        if (modelLocked) {
            lockControl(modelControl);
            if (modelControl?.disabled) lockedControls.push(modelControl);
        }
        setDynamicRowLocked(row, lockedControls);
    });
}

function applyCollectionLock(form, section, { addButton, rowSelector }) {
    const keys = COLLECTION_LOCK_KEYS[section] || [];
    const lockedFields = configurationSnapshot?.environment_locked_fields || [];
    const locked = keys.some(key => isEnvironmentLocked(key, lockedFields));
    if (!locked) return;

    const button = form.querySelector(addButton);
    showCollectionLockMessage(button);
    const header = button?.closest('.config-subsection-header');
    const message = header?.querySelector('.config-collection-lock-message');
    setModalLockNote(true);
    if (button) button.disabled = true;
    form.querySelectorAll(rowSelector).forEach(row => {
        row.querySelectorAll('input[data-field], select[data-field], textarea[data-field]').forEach(control => lockControl(control, message));
        row.querySelectorAll('.config-remove-row').forEach(removeButton => { removeButton.disabled = true; });
    });
}

function applyCollectionLocks(form, section) {
    const configs = {
        zhiqiu: { addButton: '[data-add-zhiqiu-account]', rowSelector: '.config-zhiqiu-row' },
        ifind: { addButton: '[data-add-ifind-account]', rowSelector: '.config-ifind-row' },
        web_search: { addButton: '[data-add-web_search-key]', rowSelector: '.config-web_search-row' },
    };
    if (configs[section]) applyCollectionLock(form, section, configs[section]);
}

function setFormValues(form, values, fields) {
    fields.forEach(field => {
        const control = form?.elements.namedItem(field);
        if (!control) return;
        if (control.type === 'checkbox') control.checked = Boolean(values[field]);
        else control.value = values[field] ?? '';
    });
}

function databaseSecretPresentation(secret, locked = false) {
    if (!secret?.configured) {
        return { state: 'missing', label: '未配置', summary: '尚未设置连接地址' };
    }
    return {
        state: 'configured',
        label: locked ? '由启动配置管理' : '已配置',
        summary: typeof secret.masked_value === 'string' && secret.masked_value.trim()
            ? secret.masked_value.trim()
            : '连接地址已安全保存',
    };
}

function setSecretState(selector, secret) {
    const node = document.querySelector(selector);
    if (!node) return;
    const hint = secretHint(secret);
    node.textContent = hint;
    node.classList.toggle('configured', hint === '已配置');
}

function databaseReadinessPresentation() {
    const readiness = databaseRuntimeReadiness;
    const databaseReady = readiness?.database?.ready === true;
    if (databaseReady && readiness?.runtime_status === 'ready') {
        return { label: '数据库已验证', state: 'ready' };
    }
    if (databaseReady && (readiness?.restart_required || readiness?.runtime_status === 'setup_required')) {
        return { label: '数据库待重启', state: 'restart' };
    }
    return { label: '数据库未就绪', state: 'missing' };
}

function renderDatabaseRuntimeReadiness() {
    const presentation = databaseReadinessPresentation();
    setSectionStatus('database', presentation.label, presentation.state);
    const card = document.querySelector('[data-config-card="database"]');
    const badge = card?.querySelector('[data-card-badge="database"]');
    const summary = card?.querySelector('[data-card-summary="database"]');
    if (badge) {
        badge.textContent = presentation.label;
        badge.className = `config-card-badge ${presentation.state}`;
    }
    if (summary) summary.textContent = presentation.label;
}

async function refreshDatabaseRuntimeReadiness() {
    try {
        const readiness = await configurationApiCall('GET', '/api/setup/readiness');
        if (!readiness || typeof readiness.runtime_status !== 'string') {
            throw new ConfigurationApiError('invalid setup readiness response');
        }
        databaseRuntimeReadiness = readiness;
    } catch (error) {
        databaseRuntimeReadiness = null;
        console.warn('[config] database readiness refresh failed', {
            errorType: error?.name || 'UnknownError',
        });
    }
    renderDatabaseRuntimeReadiness();
    renderSummaryCards();
    if (configurationSnapshot) {
        renderConfigurationHealth(configurationSnapshot);
    }
    return databaseRuntimeReadiness;
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
    ['llm', 'zhiqiu', 'ifind'].forEach(section => {
        const ready = Boolean(snapshot.readiness?.[section]);
        const card = document.querySelector(`[data-readiness="${section}"]`);
        if (card) {
            card.classList.toggle('ready', ready);
            card.classList.toggle('missing', !ready);
            card.querySelector('strong').textContent = ready ? '已就绪' : '待配置';
        }
        setSectionStatus(section, ready ? '已就绪' : '待配置', ready ? 'ready' : 'missing');
    });
    renderDatabaseRuntimeReadiness();
    setSectionStatus('advanced', snapshot.readiness?.advanced ? '已就绪' : '待配置', snapshot.readiness?.advanced ? 'ready' : 'missing');
}

function getConfigurationHealth(snapshot) {
    const readiness = snapshot?.readiness || {};
    const entries = Object.entries(readiness);
    const readyCount = entries.filter(([section, ready]) => (
        section === 'database'
            ? databaseReadinessPresentation().state === 'ready'
            : Boolean(ready)
    )).length;
    const connectionStates = [...connectionStateBySection.values()];
    return {
        readyCount,
        missingCount: Math.max(0, entries.length - readyCount),
        verifiedCount: connectionStates.filter(state => state === 'verified').length,
        errorCount: connectionStates.filter(state => state === 'error').length,
    };
}

const CAPABILITY_PRESENTATIONS = {
    available: {
        state: 'ready',
        label: '可用',
        detail: '当前环境已检测到此能力。',
        remediation: '无需操作。',
    },
    not_detected: {
        state: 'missing',
        label: '未检测到',
        detail: '当前环境未检测到此能力。',
        remediation: '请安装或启动所需组件后重新检测。',
    },
    not_applicable: {
        state: 'missing',
        label: '不适用',
        detail: '此能力不适用于当前运行环境。',
        remediation: '无需配置此能力。',
    },
    unknown: {
        state: 'error',
        label: '未知',
        detail: '暂时无法确定此能力的状态。',
        remediation: '请刷新检测；若仍未知，请查看应用日志。',
    },
};

function getUnknownCapabilityPresentation() {
    const presentation = CAPABILITY_PRESENTATIONS.unknown;
    return {
        ...presentation,
        remediation: [presentation.remediation],
    };
}

export function getCapabilityPresentation(capability = {}) {
    if (!capability || typeof capability !== 'object' || Array.isArray(capability)) {
        return getUnknownCapabilityPresentation();
    }
    const status = capability.status;
    if (typeof status !== 'string' || !Object.hasOwn(CAPABILITY_PRESENTATIONS, status)) {
        return getUnknownCapabilityPresentation();
    }

    const presentation = CAPABILITY_PRESENTATIONS[status];
    const detail = typeof capability.detail === 'string' && capability.detail.trim()
        ? capability.detail.trim()
        : presentation.detail;
    const remediation = Array.isArray(capability.remediation)
        ? capability.remediation.filter(item => typeof item === 'string' && item.trim()).map(item => item.trim())
        : [];
    return {
        ...presentation,
        detail,
        remediation: remediation.length ? remediation : [presentation.remediation],
    };
}

function getEnvironmentCatalogLabel(catalog, capabilityKey) {
    const sections = Array.isArray(catalog?.sections) ? catalog.sections : [];
    const matchedSection = sections.find(section => section?.key === capabilityKey);
    return typeof matchedSection?.label === 'string' && matchedSection.label.trim()
        ? matchedSection.label.trim()
        : '';
}

export function getEnvironmentDisplayValue(value, labels = {}) {
    if (typeof value !== 'string' || !value.trim()) return '未提供';
    if (labels && typeof labels === 'object' && Object.hasOwn(labels, value)) {
        return labels[value];
    }
    return value.trim();
}

function appendEnvironmentPath(paths, label, key) {
    const item = document.createElement('div');
    const name = document.createElement('dt');
    const value = document.createElement('dd');
    const path = paths && typeof paths[key] === 'string' ? paths[key].trim() : '';
    name.textContent = label;
    value.textContent = path || '后端未提供此路径';
    item.append(name, value);
    return item;
}

export function renderEnvironmentDiagnostics(snapshot) {
    const diagnostics = document.querySelector('[data-config-environment-diagnostics]');
    if (!diagnostics) return;

    const environment = snapshot && snapshot.environment;
    if (!environment || typeof environment !== 'object') {
        diagnostics.hidden = true;
        return;
    }

    const summaryTitle = diagnostics.querySelector('[data-config-environment-summary-title]');
    const summaryDetail = diagnostics.querySelector('[data-config-environment-summary-detail]');
    const pathsNode = diagnostics.querySelector('[data-config-environment-paths]');
    const capabilitiesNode = diagnostics.querySelector('[data-config-environment-capabilities]');
    const platform = getEnvironmentDisplayValue(environment.platform, {
        macos: 'macOS',
        windows: 'Windows',
        linux: 'Linux',
        unknown: '未知',
    });
    const architecture = getEnvironmentDisplayValue(environment.architecture);
    const runtimeMode = getEnvironmentDisplayValue(environment.runtime_mode, {
        desktop: '桌面端',
        server: '服务端',
        unknown: '未知',
    });

    summaryTitle?.replaceChildren(`当前环境：${platform} / ${architecture} / ${runtimeMode}`);
    summaryDetail?.replaceChildren(`平台：${platform} · 架构：${architecture} · 运行模式：${runtimeMode}`);

    if (pathsNode) {
        pathsNode.replaceChildren(
            appendEnvironmentPath(environment.paths, '配置路径', 'config'),
            appendEnvironmentPath(environment.paths, '数据路径', 'data'),
            appendEnvironmentPath(environment.paths, '日志路径', 'logs'),
        );
    }

    if (capabilitiesNode) {
        const capabilities = Array.isArray(environment.capabilities) ? environment.capabilities : [];
        const capabilityItems = capabilities.map(capability => {
            const presentation = getCapabilityPresentation(capability);
            const item = document.createElement('li');
            const header = document.createElement('div');
            const name = document.createElement('strong');
            const status = document.createElement('span');
            const detail = document.createElement('p');
            const remediation = document.createElement('p');
            const label = typeof capability?.label === 'string' && capability.label.trim()
                ? capability.label.trim()
                : getEnvironmentCatalogLabel(snapshot.catalog, capability?.key) || '未命名能力';

            item.classList.add('config-environment-diagnostics-capability', presentation.state);
            header.className = 'config-environment-diagnostics-capability-header';
            status.className = 'config-environment-diagnostics-capability-status';
            detail.className = 'config-environment-diagnostics-capability-detail';
            remediation.className = 'config-environment-diagnostics-capability-remediation';
            name.textContent = label;
            status.textContent = `状态：${presentation.label}`;
            detail.textContent = presentation.detail;
            remediation.textContent = `建议：${presentation.remediation.join('；')}`;
            header.append(name, status);
            item.append(header, detail, remediation);
            return item;
        });
        if (!capabilityItems.length) {
            const empty = document.createElement('li');
            empty.className = 'config-environment-diagnostics-empty';
            empty.textContent = '后端未提供本机能力检测结果。';
            capabilityItems.push(empty);
        }
        capabilitiesNode.replaceChildren(...capabilityItems);
    }

    diagnostics.hidden = false;
}

function renderConfigurationHealth(snapshot) {
    const health = getConfigurationHealth(snapshot);
    const summary = document.querySelector('[data-config-health-summary]');
    const readiness = snapshot?.readiness || {};
    const total = Object.keys(readiness).length || ONBOARDING_SECTIONS.length;
    const completed = health.readyCount;
    const missing = Math.max(0, total - completed);
    const percent = total ? Math.round((completed / total) * 100) : 0;

    if (!summary) return;
    summary.classList.toggle('ready', missing === 0 && health.errorCount === 0);
    summary.classList.toggle('has-error', health.errorCount > 0);
    const completedNode = summary.querySelector('[data-config-progress-completed]');
    if (completedNode) completedNode.textContent = completed;
    const totalNode = summary.querySelector('[data-config-progress-total]');
    if (totalNode) totalNode.textContent = total;
    const progressBar = summary.querySelector('[data-config-progress-bar]');
    if (progressBar) {
        progressBar.style.width = `${percent}%`;
        progressBar.parentElement?.setAttribute('aria-valuenow', String(percent));
    }
}

function renderSnapshot(snapshot) {
    configurationSnapshot = snapshot;
    renderReadiness(snapshot);
    Object.entries(snapshot.sections).forEach(([section, values]) => {
        if (!dirtySections.has(section)) renderSection(section, values);
    });
    renderSummaryCards();
    renderConfigurationHealth(snapshot);
    renderEnvironmentDiagnostics(snapshot);
}

function renderSection(section, values) {
    if (section === 'llm') {
        renderProviders(values.providers || []);
        renderTaskRoutes(values.task_routes || []);
    } else if (section === 'zhiqiu') {
        renderZhiqiuAccounts(values.accounts || []);
        syncEmptyCollectionState('zhiqiu', values.accounts || []);
        setFormValues(document.getElementById('config-zhiqiu-form'), values, [
            'enabled', 'rotation_strategy', 'max_retries', 'retry_delay', 'lease_timeout', 'max_consecutive_failures',
        ]);
    } else if (section === 'ifind') {
        renderIfindAccounts(values.accounts || []);
        syncEmptyCollectionState('ifind', values.accounts || []);
        setFormValues(document.getElementById('config-ifind-form'), values, ['backend', 'http_base_url']);
    } else if (section === 'database') {
        setSecretState('[data-secret-state="database-url"]', values.database_url);
        const form = document.getElementById('config-database-form');
        if (form) form.elements.database_url.value = '';
    } else if (section === 'advanced') {
        setFormValues(document.getElementById('config-advanced-form'), values, [
            'log_level', 'log_dir', 'llm_max_workers', 'llm_max_retries', 'chunk_size', 'chunk_overlap', 'long_text_threshold',
        ]);
    } else if (section === 'web_search') {
        renderWebSearchKeys(values.accounts || []);
        syncEmptyCollectionState('web_search', values.accounts || []);
        setFormValues(document.getElementById('config-web_search-form'), values, [
            'provider', 'rotation_strategy', 'quota_limit', 'max_results', 'timeout',
        ]);
    }
    dirtySections.delete(section);
}

function deriveSectionReadiness(section, values) {
    if (section === 'llm') return (values.providers || []).some(item => item.protocol === 'local' || item.api_key?.configured);
    if (section === 'zhiqiu') return (values.accounts || []).some(item => item.password?.configured);
    if (section === 'ifind') return (values.accounts || []).some(item => item.username && item.password?.configured);
    if (section === 'database') return databaseRuntimeReadiness?.database?.ready === true
        && databaseRuntimeReadiness.runtime_status === 'ready';
    if (section === 'web_search') return (values.accounts || []).some(item => item.key?.configured);
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
        if (section !== 'database') {
            configurationSnapshot.readiness[section] = deriveSectionReadiness(section, values);
        }
        configurationSnapshot.ready_count = Object.values(configurationSnapshot.readiness).filter(Boolean).length;
        connectionStateBySection.delete(section);
        renderReadiness(configurationSnapshot);
    }
    renderSummaryCards();
    renderConfigurationHealth(configurationSnapshot);
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
    // 如果该 section 的模态框打开，写入模态框状态栏
    const modalStatus = document.getElementById('config-edit-modal-status');
    if (modalStatus && currentModalSection === section) {
        modalStatus.textContent = message;
        modalStatus.className = `config-modal-status ${state}`.trim();
        return;
    }
    // 否则写入页面内联状态
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

function showPageError(error, showRetry = false) {
    const node = document.getElementById('config-page-message');
    if (!node) return;
    const safe = safeConfigurationError(error);
    if (!safe.details.length) {
        if (showRetry) {
            const msg = document.createElement('span');
            msg.textContent = safe.message;
            const btn = document.createElement('button');
            btn.className = 'btn-primary';
            btn.style.cssText = 'margin-left:12px;min-height:28px;padding:0 14px;font-size:12px;border-radius:14px;';
            btn.textContent = '重试';
            btn.addEventListener('click', () => {
                initialLoadRetryCount = 0;
                showPageMessage('');
                loadConfiguration();
            });
            node.replaceChildren(msg, btn);
            node.className = 'config-page-message error';
        } else {
            showPageMessage(safe.message, 'error');
        }
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
        connectionStateBySection.clear();
        renderSnapshot(snapshot);
        configurationReady = true;
        initialLoadRetryCount = 0;
        syncMutationControls();
        showPageMessage('');
        return true;
    } catch (error) {
        if (error?.name === 'AbortError' || !loadGeneration.isLatest(token)) return;
        // 403 自愈：后端在 fetchConfigToken 之后、本请求之前重启过，导致 token 过期。
        // 刷新一次 token 再重试，仍失败才落到错误提示。仅对初始加载生效一次。
        if (error?.status === 403 && !configurationSnapshot && initialLoadRetryCount === 0) {
            initialLoadRetryCount += 1;
            showPageMessage('会话已失效，正在重新加载…', 'info');
            window.setTimeout(async () => {
                if (loadGeneration.isLatest(token) && !configurationSnapshot && !requestCoordinator.hasActive()) {
                    await fetchConfigToken();
                    loadConfiguration();
                }
            }, 200);
            return;
        }
        if (!configurationSnapshot) {
            configurationReady = false;
            syncMutationControls();
            if (initialLoadRetryCount < 5) {
                initialLoadRetryCount += 1;
                window.setTimeout(() => {
                    if (!configurationSnapshot && !requestCoordinator.hasActive()) loadConfiguration();
                }, 1000);
            } else {
                // 所有重试耗尽，显示含重试按钮的错误消息
                // 移除骨架屏 data-loading 属性，恢复卡片可点击状态
                const grid = document.querySelector('.config-cards-grid');
                if (grid) grid.removeAttribute('data-loading');
                showPageError(error, true);
                return;
            }
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

function focusFirstCollectionField(row) {
    row?.querySelector('input[data-field]:not(:disabled), select[data-field]:not(:disabled), textarea[data-field]:not(:disabled)')?.focus();
}

function collectLlm() {
    const providers = [...document.querySelectorAll('.config-provider-row')].map(row => {
        const secret = collectSecretPair(row.querySelector('[data-field="api_key"]'));
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
        const secret = collectSecretPair(row.querySelector('[data-field="password"]'));
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
        const secret = collectSecretPair(row.querySelector('[data-field="password"]'));
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

function collectWebSearch() {
    const form = document.getElementById('config-web_search-form');
    const accounts = [...document.querySelectorAll('.config-web_search-row')].map(row => {
        const secret = collectSecretPair(row.querySelector('[data-field="key"]'));
        return {
            original_name: rowOriginalNames.get(row) || undefined,
            name: rowValue(row, 'name'),
            key: secret.value,
            clear_key: secret.clear,
        };
    });
    return {
        accounts,
        provider: form.elements.provider.value,
        rotation_strategy: form.elements.rotation_strategy.value,
        quota_limit: Number(form.elements.quota_limit.value),
        max_results: Number(form.elements.max_results.value),
        timeout: Number(form.elements.timeout.value),
    };
}

function collectDatabase() {
    const databaseUrl = document.getElementById('config-database-form').elements.database_url.value;
    if (!databaseUrl && !isEnvironmentLocked(STATIC_LOCK_FIELD_KEYS.database.database_url)) {
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
    const collectors = { llm: collectLlm, zhiqiu: collectZhiqiu, ifind: collectIfind, database: collectDatabase, advanced: collectAdvanced, web_search: collectWebSearch };
    return filterEnvironmentLockedPayload(section, collectors[section]());
}

function setSectionBusy(section, busy) {
    const form = document.querySelector(`[data-config-form="${section}"]`);
    form?.querySelectorAll('button').forEach(button => { button.disabled = busy; });
}

function syncMutationControls() {
    const page = document.getElementById('section-config');
    if (!page) return;
    const disabled = !configurationReady || requestCoordinator.hasActive();
    page.querySelectorAll(
        '[data-config-save], [data-add-provider], [data-add-task-route], [data-add-zhiqiu-account], [data-add-ifind-account], [data-add-web_search-key], .config-remove-row',
    ).forEach(button => { button.disabled = disabled; });
}

async function saveSection(section) {
    if (!configurationReady) {
        showPageMessage('配置尚未加载完成，暂时无法保存或验证', 'error');
        return false;
    }
    const token = requestCoordinator.begin(section);
    if (token === null) return false;
    const submittedEditGeneration = sectionEditGenerations.get(section) || 0;
    setSectionBusy(section, true);
    setSectionStatus(section, '保存中…');
    const saveBtn = document.querySelector(`[data-config-form="${section}"] [data-config-save]`);
    saveBtn?.setAttribute('data-saving', '');
    try {
        const payload = collectSection(section);
        const result = await configurationApiCall('PUT', `/api/config/${section}`, payload);
        if (!requestCoordinator.isLatest(section, token)) return false;
        const editedWhileSaving = (sectionEditGenerations.get(section) || 0) !== submittedEditGeneration;
        applySectionResponse(section, result.section, !editedWhileSaving);
        if (section === 'database') await refreshDatabaseRuntimeReadiness();
        const message = result.restart_required ? '重启后生效' : '配置已生效';
        setSectionStatus(section, message, result.restart_required ? 'restart' : 'ready');
        showPageMessage(message, result.restart_required ? 'restart' : 'ready');
        saveBtn?.removeAttribute('data-saving');
        saveBtn?.setAttribute('data-save-success', '');
        setTimeout(() => saveBtn?.removeAttribute('data-save-success'), 1800);
        return !editedWhileSaving;
    } catch (error) {
        if (!requestCoordinator.isLatest(section, token)) return false;
        const safe = safeConfigurationError(error);
        const firstPath = safe.details[0]?.path || '';
        setSectionStatus(section, firstPath ? `字段校验失败：${firstPath}` : safe.message, 'error');
        showPageError(error);
        saveBtn?.removeAttribute('data-saving');
        saveBtn?.setAttribute('data-save-error', '');
        setTimeout(() => saveBtn?.removeAttribute('data-save-error'), 2200);
        return false;
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
        if (section === 'database') await refreshDatabaseRuntimeReadiness();
        const message = result.success ? '连接验证成功' : '连接验证失败';
        connectionStateBySection.set(section, result.success ? 'verified' : 'error');
        console.info('[config] connection test completed', { section, success: Boolean(result.success) });
        setSectionStatus(section, message, result.success ? 'ready' : 'error');
        showPageMessage(message, result.success ? 'ready' : 'error');
        renderSummaryCards();
        renderConfigurationHealth(configurationSnapshot);
    } catch (error) {
        if (!requestCoordinator.isLatest(section, token)) return;
        connectionStateBySection.set(section, 'error');
        console.warn('[config] connection test failed', { section, status: error?.status || 0 });
        const safe = safeConfigurationError(error);
        const firstPath = safe.details[0]?.path || '';
        setSectionStatus(section, firstPath ? `字段校验失败：${firstPath}` : safe.message, 'error');
        showPageError(error);
        renderSummaryCards();
        renderConfigurationHealth(configurationSnapshot);
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

function bindConfigurationEvents() {
    const page = document.getElementById('section-config');
    if (!page || page.dataset.bound === 'true') return;
    page.dataset.bound = 'true';

    // 卡片点击 → 打开模态框
    page.querySelectorAll('[data-config-card]').forEach(card => {
        card.addEventListener('click', () => {
            const section = card.dataset.configCard;
            openConfigModal(section);
        });
        card.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                openConfigModal(card.dataset.configCard);
            }
        });
    });

    syncMutationControls();
}

export async function initConfigurationPage() {
    if (!document.getElementById('section-config')) return;
    bindConfigurationEvents();
    initConfigModal();
    if (configurationInitialized && configurationSnapshot) return;
    if (configurationInitializationPromise) return configurationInitializationPromise;
    if (configurationInitialized && !configurationSnapshot) {
        // 上次加载失败，重置重试计数以允许重新加载
        initialLoadRetryCount = 0;
    }
    configurationInitializationPromise = (async () => {
        configurationInitialized = true;

        // 显示加载骨架屏
        const grid = document.querySelector('.config-cards-grid');
        if (grid) grid.setAttribute('data-loading', '');

        await fetchConfigToken();
        await loadConfiguration();
        await refreshDatabaseRuntimeReadiness();

        // 加载完成后移除骨架屏（renderSnapshot -> renderSummaryCards 中也会处理）
        if (grid) grid.removeAttribute('data-loading');
    })();
    try {
        await configurationInitializationPromise;
    } finally {
        configurationInitializationPromise = null;
    }
}

// ── 模态框状态 ───────────────────────────────────────────
let currentModalSection = null;
let modalDirty = false;

const SECTION_META = {
    llm:        { title: '大模型服务',       subtitle: '配置模型服务和任务路由',              icon: 'robot',          testable: true,  color: 'violet' },
    zhiqiu:     { title: '知丘账号池',       subtitle: '配置知丘账号和调度策略',              icon: 'account',        testable: true,  color: 'cyan' },
    ifind:      { title: 'iFinD 账号池',     subtitle: '配置 iFinD 账号和连接方式',           icon: 'database',       testable: true,  color: 'blue' },
    web_search: { title: '联网搜索 API Key 池', subtitle: '配置搜索 API Key 和搜索参数',       icon: 'search',         testable: true,  color: 'amber' },
    database:   { title: '数据库',           subtitle: '配置数据库连接地址',                  icon: 'server',         testable: true,  color: 'emerald' },
    advanced:   { title: '高级配置',          subtitle: '日志、并发、重试与分块参数',           icon: 'settings-gear',  testable: false, color: 'slate' },
};

// ── 摘要卡片 ───────────────────────────────────────────
export function renderSummaryCards() {
    if (!configurationSnapshot) return;

    const summaries = {
        llm: () => {
            const providers = configurationSnapshot.sections.llm?.providers || [];
            const routes = configurationSnapshot.sections.llm?.task_routes || [];
            return `${providers.length} 个服务, ${routes.length} 条路由`;
        },
        zhiqiu: () => {
            const count = (configurationSnapshot.sections.zhiqiu?.accounts || []).length;
            const strategy = configurationSnapshot.sections.zhiqiu?.rotation_strategy || '--';
            return `${count} 个账号 · ${strategy === 'round_robin' ? '轮询' : strategy === 'random' ? '随机' : strategy === 'least_used' ? '最少使用' : strategy}`;
        },
        ifind: () => {
            const count = (configurationSnapshot.sections.ifind?.accounts || []).length;
            const backend = configurationSnapshot.sections.ifind?.backend || '--';
            return `${count} 个账号 · 后端: ${backend === 'auto' ? '自动' : backend}`;
        },
        web_search: () => {
            const count = (configurationSnapshot.sections.web_search?.accounts || []).length;
            return `${count} 个 Key`;
        },
        database: () => {
            return databaseReadinessPresentation().label;
        },
        advanced: () => {
            const adv = configurationSnapshot.sections.advanced || {};
            return `日志级别: ${adv.log_level || '--'}, 并发: ${adv.llm_max_workers || '--'}`;
        },
    };

    Object.entries(summaries).forEach(([section, fn]) => {
        const card = document.querySelector(`[data-config-card="${section}"]`);
        const el = card?.querySelector(`[data-card-summary="${section}"]`);
        if (el) el.textContent = fn();

        // 设置卡片专属颜色
        const meta = SECTION_META[section];
        if (card && meta?.color) {
            card.setAttribute('data-card-color', meta.color);
        }

        const badge = document.querySelector(`[data-card-badge="${section}"]`);
        if (badge) {
            if (section === 'database') {
                const presentation = databaseReadinessPresentation();
                badge.textContent = presentation.label;
                badge.className = `config-card-badge ${presentation.state}`;
            } else {
                const ready = configurationSnapshot.readiness?.[section];
                const connectionState = connectionStateBySection.get(section);
                const label = connectionState === 'verified'
                    ? '连接已验证'
                    : connectionState === 'error'
                        ? '连接异常'
                        : ready ? '已就绪' : '待配置';
                const state = connectionState === 'verified'
                    ? 'verified'
                    : connectionState === 'error'
                        ? 'error'
                        : ready ? 'ready' : 'missing';
                badge.textContent = label;
                badge.className = `config-card-badge ${state}`;
            }
        }

        const action = document.querySelector(`[data-config-card-action="${section}"]`);
        if (action) {
            const connectionState = connectionStateBySection.get(section);
            action.textContent = connectionState === 'error'
                ? '修复配置'
                : configurationSnapshot.readiness?.[section] ? '管理配置' : '去配置';
        }
    });

    // 移除加载骨架屏状态
    const grid = document.querySelector('.config-cards-grid');
    if (grid) grid.removeAttribute('data-loading');
}

// ── 模态框渲染 ──────────────────────────────────────────
function renderModalForm(section, values) {
    const body = document.getElementById('config-edit-modal-body');
    body.innerHTML = '';

    const form = document.createElement('form');
    form.id = `config-${section}-form`;
    form.dataset.configForm = section;
    form.className = 'config-panel';

    switch (section) {
        case 'llm':
            form.innerHTML = `
                <div class="config-tab-list" role="tablist" aria-label="大模型配置">
                    <button type="button" role="tab" data-config-tab="providers" id="config-tab-providers" aria-controls="config-tab-panel-providers" aria-selected="true" tabindex="0" class="is-active">模型服务</button>
                    <button type="button" role="tab" data-config-tab="routes" id="config-tab-routes" aria-controls="config-tab-panel-routes" aria-selected="false" tabindex="-1">任务模型路由</button>
                </div>
                <section role="tabpanel" data-config-tab-panel="providers" id="config-tab-panel-providers" aria-labelledby="config-tab-providers" class="is-active">
                    <div class="config-subsection-header"><h4><i class="codicon codicon-server"></i>模型服务</h4><button type="button" class="secondary-btn" data-add-provider>新增服务</button></div>
                    <div class="config-collection-table config-provider-table"><div class="config-row-labels config-provider-labels" aria-hidden="true"><span>服务名称</span><span>接口协议</span><span>服务地址</span><span>API 密钥</span><span>操作</span></div><div id="config-provider-list" class="config-dynamic-list"></div></div>
                </section>
                <section role="tabpanel" data-config-tab-panel="routes" id="config-tab-panel-routes" aria-labelledby="config-tab-routes" class="hidden" hidden>
                    <div class="config-subsection-header"><h4><i class="codicon codicon-symbol-ruler"></i>任务模型路由</h4><button type="button" class="secondary-btn" data-add-task-route>新增路由</button></div>
                    <div class="config-collection-table config-route-table"><div class="config-row-labels config-route-labels" aria-hidden="true"><span>任务类型</span><span>模型服务</span><span>模型名称</span><span>操作</span></div><div id="config-task-route-list" class="config-dynamic-list"></div></div>
                </section>`;
            break;
        case 'zhiqiu':
            form.innerHTML = `
                <div class="config-subsection-header"><h4><i class="codicon codicon-account"></i>账号池</h4><button type="button" class="secondary-btn" data-add-zhiqiu-account>新增账号</button></div>
                <div class="config-collection-table config-zhiqiu-table"><div class="config-row-labels config-zhiqiu-labels" aria-hidden="true"><span>名称</span><span>用户名</span><span>密码</span><span>操作</span></div><div id="config-zhiqiu-account-list" class="config-dynamic-list"></div></div>
                <div class="config-settings-header"><h4><i class="codicon codicon-settings"></i>调度设置</h4></div>
                <div class="config-field-grid config-field-grid--compact">
                    <label class="config-checkbox"><input type="checkbox" name="enabled">启用账号轮询</label>
                    <label><span>轮询策略</span><select name="rotation_strategy"><option value="round_robin">轮询</option><option value="random">随机</option><option value="least_used">最少使用</option></select></label>
                    <label><span>最大重试次数</span><input type="number" name="max_retries" min="0" max="20"></label>
                    <label><span>重试间隔（秒）</span><input type="number" name="retry_delay" min="0" max="3600"></label>
                    <label><span>租约超时（秒）</span><input type="number" name="lease_timeout" min="1" max="86400"></label>
                    <label><span>连续失败阈值</span><input type="number" name="max_consecutive_failures" min="1" max="1000"></label>
                </div>`;
            break;
        case 'ifind':
            form.innerHTML = `
                <div class="config-subsection-header"><h4><i class="codicon codicon-organization"></i>账号</h4><button type="button" class="secondary-btn" data-add-ifind-account>新增账号</button></div>
                <div class="config-collection-table config-ifind-table"><div class="config-row-labels config-ifind-labels" aria-hidden="true"><span>名称</span><span>用户名</span><span>密码</span><span>操作</span></div><div id="config-ifind-account-list" class="config-dynamic-list"></div></div>
                <div class="config-settings-header"><h4><i class="codicon codicon-plug"></i>连接设置</h4></div>
                <div class="config-field-grid config-field-grid--compact config-settings-grid">
                    <label><span>后端类型</span><select name="backend"><option value="auto">自动</option><option value="python_sdk">Python SDK</option><option value="http_api">HTTP API</option></select></label>
                    <label><span>HTTP Base URL</span><input type="url" name="http_base_url" placeholder="https://quantapi.10jqka.com.cn"></label>
                </div>
                `;
            break;
        case 'web_search':
            form.innerHTML = `
                <div class="config-subsection-header"><h4><i class="codicon codicon-key"></i>Key 池</h4><button type="button" class="secondary-btn" data-add-web_search-key>新增 Key</button></div>
                <div class="config-collection-table config-web-search-table"><div class="config-row-labels config-web_search-labels" aria-hidden="true"><span>名称</span><span>API Key</span><span>状态</span><span>操作</span></div><div id="config-web_search-key-list" class="config-dynamic-list"></div></div>
                <div class="config-settings-header"><h4><i class="codicon codicon-search"></i>搜索设置</h4></div>
                <div class="config-field-grid config-field-grid--compact">
                    <label><span>搜索 Provider</span><select name="provider"><option value="tavily">Tavily</option><option value="bing">Bing</option></select></label>
                    <label><span>轮询策略</span><select name="rotation_strategy"><option value="round_robin">轮询</option><option value="random">随机</option><option value="least_used">最少使用</option></select></label>
                    <label><span>月度配额</span><input type="number" name="quota_limit" min="1" max="100000" placeholder="1000"></label>
                    <label><span>每次最大结果</span><input type="number" name="max_results" min="1" max="20" placeholder="5"></label>
                    <label><span>请求超时（秒）</span><input type="number" name="timeout" min="1" max="120" placeholder="15"></label>
                </div>`;
            break;
        case 'database':
            form.innerHTML = `
                <section class="config-database-current" data-database-current aria-label="当前数据库连接"><span>当前连接</span><strong data-database-summary>正在读取安全摘要…</strong><small data-secret-state="database-url">未配置</small></section>
                <label class="config-field-wide config-database-replacement"><span>替换连接地址</span><input type="password" name="database_url" autocomplete="new-password" placeholder="输入新的连接地址"><small>保存后重启桌面端，新地址才会生效。</small></label>`;
            break;
        case 'advanced':
            form.innerHTML = `
                <div class="config-field-grid">
                    <label><span>日志级别</span><select name="log_level"><option>DEBUG</option><option>INFO</option><option>WARNING</option><option>ERROR</option><option>CRITICAL</option></select></label>
                    <label><span>日志目录</span><input type="text" name="log_dir"></label>
                    <label><span>LLM 并发数</span><input type="number" name="llm_max_workers" min="1" max="128"></label>
                    <label><span>LLM 重试次数</span><input type="number" name="llm_max_retries" min="0" max="20"></label>
                    <label><span>分块大小</span><input type="number" name="chunk_size" min="256" max="100000"></label>
                    <label><span>分块重叠</span><input type="number" name="chunk_overlap" min="0" max="50000"></label>
                    <label><span>长文本阈值</span><input type="number" name="long_text_threshold" min="1" max="100000"></label>
                </div>`;
            break;
    }

    body.appendChild(form);
    applyEnvironmentLocks(form, section);

    // 用现有 render 函数填充数据
    if (section === 'llm') {
        renderProviders(values.providers || []);
        renderTaskRoutes(values.task_routes || []);
    } else if (section === 'zhiqiu') {
        renderZhiqiuAccounts(values.accounts || []);
        renderEmptyCollectionState(form, section, values.accounts);
        setFormValues(form, values, ['enabled', 'rotation_strategy', 'max_retries', 'retry_delay', 'lease_timeout', 'max_consecutive_failures']);
    } else if (section === 'ifind') {
        renderIfindAccounts(values.accounts || []);
        renderEmptyCollectionState(form, section, values.accounts);
        setFormValues(form, values, ['backend', 'http_base_url']);
    } else if (section === 'web_search') {
        renderWebSearchKeys(values.accounts || []);
        renderEmptyCollectionState(form, section, values.accounts);
        setFormValues(form, values, ['provider', 'rotation_strategy', 'quota_limit', 'max_results', 'timeout']);
    } else if (section === 'database') {
        const databaseInput = form.elements.database_url;
        const locked = Boolean(databaseInput?.disabled);
        const presentation = databaseSecretPresentation(values.database_url, locked);
        const summary = form.querySelector('[data-database-summary]');
        if (summary) summary.textContent = presentation.summary;
        const state = form.querySelector('[data-secret-state="database-url"]');
        if (state) {
            state.textContent = presentation.label;
            state.classList.toggle('configured', presentation.state === 'configured');
        }
        if (form.elements.database_url) form.elements.database_url.value = '';
    } else if (section === 'advanced') {
        setFormValues(form, values, ['log_level', 'log_dir', 'llm_max_workers', 'llm_max_retries', 'chunk_size', 'chunk_overlap', 'long_text_threshold']);
    }

    if (section === 'llm') {
        applyProviderRowLocks();
        applyTaskRouteLocks();
    }
    applyCollectionLocks(form, section);

    // 绑定事件
    bindModalFormEvents(form, section);
}

function setEnvironmentLockState(control, { section, field, locked, suppressInlineMessage = false }) {
    const label = control.closest('label');
    if (!label) return false;

    const messageId = `config-lock-message-${section}-${field}`;
    const existingMessage = label.querySelector('[data-config-lock-message]');
    const describedBy = new Set((control.getAttribute('aria-describedby') || '').split(/\s+/).filter(Boolean));

    control.disabled = locked;
    label.classList.toggle('environment-locked', locked);

    if (!locked) {
        delete label.dataset.environmentLocked;
        existingMessage?.remove();
        describedBy.delete(messageId);
        if (describedBy.size) control.setAttribute('aria-describedby', [...describedBy].join(' '));
        else control.removeAttribute('aria-describedby');
        return false;
    }

    label.dataset.environmentLocked = 'true';
    if (suppressInlineMessage) {
        existingMessage?.remove();
        describedBy.delete(messageId);
        if (describedBy.size) control.setAttribute('aria-describedby', [...describedBy].join(' '));
        else control.removeAttribute('aria-describedby');
        return true;
    }
    const message = existingMessage || document.createElement('small');
    message.className = 'config-lock-message';
    message.dataset.configLockMessage = '';
    message.id = messageId;
    message.textContent = LOCKED_FIELD_MESSAGE;
    if (!existingMessage) label.appendChild(message);
    describedBy.add(messageId);
    control.setAttribute('aria-describedby', [...describedBy].join(' '));
    return true;
}

function setModalLockNote(visible) {
    const note = document.getElementById('config-edit-modal-lock-note');
    if (note) note.hidden = !visible;
}

function applyEnvironmentLocks(form, section) {
    const lockedFields = configurationSnapshot?.environment_locked_fields || [];
    const fieldKeys = STATIC_LOCK_FIELD_KEYS[section] || {};
    let hasStaticLock = false;
    Object.entries(fieldKeys).forEach(([field, key]) => {
        const control = form.elements[field];
        if (!control) return;
        hasStaticLock = setEnvironmentLockState(control, {
            section,
            field,
            locked: isEnvironmentLocked(key, lockedFields),
            suppressInlineMessage: section === 'database' && field === 'database_url',
        }) || hasStaticLock;
    });
    setModalLockNote(hasStaticLock);
}

function selectConfigurationTab(form, selectedTab) {
    const tabs = [...form.querySelectorAll('[data-config-tab]')];
    tabs.forEach(button => {
        const selected = button.dataset.configTab === selectedTab;
        button.setAttribute('aria-selected', String(selected));
        button.classList.toggle('is-active', selected);
        button.tabIndex = selected ? 0 : -1;
    });
    form.querySelectorAll('[data-config-tab-panel]').forEach(panel => {
        const selected = panel.dataset.configTabPanel === selectedTab;
        panel.classList.toggle('is-active', selected);
        panel.classList.toggle('hidden', !selected);
        panel.hidden = !selected;
    });
}

function bindModalFormEvents(form, section) {
    const tabs = [...form.querySelectorAll('[data-config-tab]')];
    tabs.forEach((tab, index) => {
        tab.tabIndex = tab.getAttribute('aria-selected') === 'true' ? 0 : -1;
        tab.addEventListener('click', () => {
            selectConfigurationTab(form, tab.dataset.configTab);
        });
        tab.addEventListener('keydown', event => {
            let nextIndex = index;
            if (event.key === 'ArrowLeft') nextIndex = (index - 1 + tabs.length) % tabs.length;
            else if (event.key === 'ArrowRight') nextIndex = (index + 1) % tabs.length;
            else if (event.key === 'Home') nextIndex = 0;
            else if (event.key === 'End') nextIndex = tabs.length - 1;
            else return;
            event.preventDefault();
            selectConfigurationTab(form, tabs[nextIndex].dataset.configTab);
            tabs[nextIndex].focus();
        });
    });

    // 新增加行按钮
    form.querySelector('[data-add-provider]')?.addEventListener('click', () => {
        const row = createProviderRow();
        document.getElementById('config-provider-list')?.append(row);
        focusFirstCollectionField(row);
        applyProviderRowLocks();
        markSectionDirty(form);
        modalDirty = true;
        syncModalButtons();
    });
    form.querySelector('[data-add-task-route]')?.addEventListener('click', () => {
        const row = createTaskRouteRow();
        document.getElementById('config-task-route-list')?.append(row);
        focusFirstCollectionField(row);
        applyTaskRouteLocks();
        markSectionDirty(form);
        modalDirty = true;
        syncModalButtons();
    });
    form.querySelector('[data-add-zhiqiu-account]')?.addEventListener('click', () => {
        const row = createZhiqiuAccountRow();
        document.getElementById('config-zhiqiu-account-list')?.append(row);
        focusFirstCollectionField(row);
        removeEmptyCollectionState(form);
        applyCollectionLocks(form, section);
        markSectionDirty(form);
        modalDirty = true;
        syncModalButtons();
    });
    form.querySelector('[data-add-ifind-account]')?.addEventListener('click', () => {
        const row = createIfindAccountRow();
        document.getElementById('config-ifind-account-list')?.append(row);
        focusFirstCollectionField(row);
        removeEmptyCollectionState(form);
        applyCollectionLocks(form, section);
        markSectionDirty(form);
        modalDirty = true;
        syncModalButtons();
    });
    form.querySelector('[data-add-web_search-key]')?.addEventListener('click', () => {
        const row = createWebSearchKeyRow();
        document.getElementById('config-web_search-key-list')?.append(row);
        focusFirstCollectionField(row);
        removeEmptyCollectionState(form);
        applyCollectionLocks(form, section);
        markSectionDirty(form);
        modalDirty = true;
        syncModalButtons();
    });

    // 脏数据追踪
    form.addEventListener('input', () => { modalDirty = true; markSectionDirty(form); syncModalButtons(); });
    form.addEventListener('change', () => { modalDirty = true; markSectionDirty(form); syncModalButtons(); });
    form.addEventListener('click', (e) => {
        if (e.target.closest('.config-remove-row')) {
            markSectionDirty(form);
            modalDirty = true;
            syncModalButtons();
        }
    });
}

// ── 模态框打开 / 关闭 ──────────────────────────────────
function openConfigModal(section) {
    if (!configurationSnapshot) {
        showPageMessage('配置数据加载中，请稍候...', 'loading');
        return;
    }
    currentModalSection = section;
    modalDirty = false;
    setModalLockNote(false);
    const modal = document.getElementById('config-edit-modal');

    const values = configurationSnapshot.sections[section];
    const meta = SECTION_META[section];

    document.getElementById('config-edit-modal-title').textContent = meta.title;
    document.getElementById('config-edit-modal-subtitle').textContent = meta.subtitle;

    // 渲染 section 专属图标
    const iconEl = document.getElementById('config-edit-modal-icon');
    if (iconEl && meta.icon) {
        iconEl.innerHTML = `<i class="codicon codicon-${meta.icon}"></i>`;
    }

    const content = document.querySelector('.config-edit-modal-content');
    content.setAttribute('data-modal-section', section);
    if (meta.color) content.setAttribute('data-modal-color', meta.color);

    renderModalForm(section, values);

    const testable = Boolean(meta.testable);
    const testBtn = document.getElementById('btn-config-edit-modal-test');
    testBtn.hidden = !testable;
    const testHelp = modal?.querySelector('[data-config-test-help]');
    if (testHelp) testHelp.hidden = !testable;

    const statusEl = document.getElementById('config-edit-modal-status');
    statusEl.textContent = '';
    statusEl.className = 'config-modal-status';

    // 同步保存按钮状态
    syncModalButtons();

    document.getElementById('config-edit-modal').classList.remove('hidden');
    document.getElementById('config-edit-modal').setAttribute('aria-hidden', 'false');
}

function closeConfigModal() {
    if (modalDirty || (currentModalSection && dirtySections.has(currentModalSection))) {
        if (!window.confirm('有未保存的更改，确定关闭？')) return;
    }

    document.getElementById('config-edit-modal').classList.add('hidden');
    document.getElementById('config-edit-modal').setAttribute('aria-hidden', 'true');
    document.getElementById('config-edit-modal-body').innerHTML = '';
    // 清除 modal content 上的 data 属性，防止 CSS 变量残留
    const content = document.querySelector('.config-edit-modal-content');
    if (content) {
        content.removeAttribute('data-modal-color');
        content.removeAttribute('data-modal-section');
    }
    if (currentModalSection) dirtySections.delete(currentModalSection);
    currentModalSection = null;
    modalDirty = false;
}

function syncModalButtons() {
    const disabled = !configurationReady || requestCoordinator.hasActive();
    const saveDisabled = disabled || !modalDirty;
    const saveBtn = document.getElementById('btn-config-edit-modal-save');
    const testBtn = document.getElementById('btn-config-edit-modal-test');
    if (saveBtn) saveBtn.disabled = saveDisabled;
    if (testBtn) testBtn.disabled = disabled;
}

async function modalSaveSection() {
    if (!currentModalSection) return;
    const statusEl = document.getElementById('config-edit-modal-status');
    statusEl.textContent = '保存中…';
    statusEl.className = 'config-modal-status';
    try {
        const saved = await saveSection(currentModalSection);
        if (saved) {
            modalDirty = false;
        }
        syncModalButtons();
        // saveSection 内部会调用 setSectionStatus，模态框版本会更新 statusEl
    } catch (e) {
        // saveSection 已处理错误显示
    }
}

async function modalTestSection() {
    if (!currentModalSection) return;
    const statusEl = document.getElementById('config-edit-modal-status');
    statusEl.textContent = '验证中…';
    statusEl.className = 'config-modal-status';
    try {
        await testSection(currentModalSection);
    } catch (e) {
        // testSection 已处理错误显示
    }
}

function initConfigModal() {
    const modal = document.getElementById('config-edit-modal');
    if (!modal || modal.dataset.modalBound === 'true') return;
    modal.dataset.modalBound = 'true';

    document.getElementById('btn-config-edit-modal-close')?.addEventListener('click', closeConfigModal);
    document.getElementById('btn-config-edit-modal-cancel')?.addEventListener('click', closeConfigModal);
    document.getElementById('btn-config-edit-modal-save')?.addEventListener('click', modalSaveSection);
    document.getElementById('btn-config-edit-modal-test')?.addEventListener('click', modalTestSection);

    // Backdrop 关闭
    modal.addEventListener('click', (e) => {
        if (e.target === modal) closeConfigModal();
    });

    // Escape 关闭
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && currentModalSection && !document.getElementById('config-edit-modal')?.classList.contains('hidden')) {
            closeConfigModal();
        }
    });
}

export async function openDatabaseConfiguration() {
    try {
        document.dispatchEvent(new CustomEvent('alphafoundry:open-database-configuration'));
        await initConfigurationPage();
        openConfigModal('database');
        const modal = document.getElementById('config-edit-modal');
        const modalCloseButton = document.getElementById('btn-config-edit-modal-close');
        if (!modal || !modalCloseButton || modal.classList.contains('hidden')) {
            throw new Error('database configuration modal is unavailable');
        }
        modalCloseButton.focus();
    } catch (error) {
        console.error('[config] unable to open database configuration', {
            errorType: error?.name || 'UnknownError',
        });
        showPageMessage('无法打开数据库配置，请稍后重试', 'error');
        throw error;
    }
}

export { initConfigModal, openConfigModal, closeConfigModal };
export { renderProviders, renderTaskRoutes, renderZhiqiuAccounts, renderIfindAccounts };
