/* Desktop first-run database setup guidance. */

import { configurationRequestOptions, openDatabaseConfiguration } from './configuration.js?v=20260727modalhierarchy1';

let setupWizardBound = false;
let setupWizardRestoreFocus = null;
let setupWizardInitializationPromise = null;
let setupWizardHandoffPending = false;

function setupWizardElements() {
    return {
        overlay: document.getElementById('setup-wizard'),
        message: document.getElementById('setup-wizard-message'),
        remediation: document.getElementById('setup-wizard-remediation'),
        openDatabase: document.getElementById('setup-wizard-open-database'),
        skip: document.getElementById('setup-wizard-skip'),
    };
}

function safeMessage(value, fallback) {
    return typeof value === 'string' && value.trim() ? value.trim() : fallback;
}

function rememberSetupWizardFocus() {
    const activeElement = document.activeElement;
    if (activeElement && typeof activeElement.focus === 'function') {
        setupWizardRestoreFocus = activeElement;
    }
}

function restoreSetupWizardFocus() {
    const focusTarget = setupWizardRestoreFocus;
    setupWizardRestoreFocus = null;
    if (focusTarget?.isConnected !== false && typeof focusTarget?.focus === 'function') {
        focusTarget.focus();
        return;
    }
    document.body?.focus?.();
}

function discardSetupWizardRestoreFocus() {
    setupWizardRestoreFocus = null;
}

export function getSetupWizardFocusableControls(overlay) {
    if (!overlay || overlay.classList.contains('hidden') || overlay.getAttribute('aria-hidden') !== 'false') {
        return [];
    }
    return [...overlay.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])')]
        .filter(control => !control.disabled && !control.hidden && control.getAttribute('aria-hidden') !== 'true')
        .filter(control => {
            const style = globalThis.getComputedStyle?.(control);
            return !style || (style.display !== 'none' && style.visibility !== 'hidden');
        });
}

export function cycleSetupWizardFocus(event, controls, activeElement) {
    if (event.key !== 'Tab' || !controls.length) return false;
    const first = controls[0];
    const last = controls[controls.length - 1];
    if (!controls.includes(activeElement)) {
        event.preventDefault();
        (event.shiftKey ? last : first).focus();
        return true;
    }
    if (event.shiftKey && activeElement !== first) return false;
    if (!event.shiftKey && activeElement !== last) return false;
    event.preventDefault();
    (event.shiftKey ? last : first).focus();
    return true;
}

function hideSetupWizard({ restoreFocus = true } = {}) {
    const { overlay } = setupWizardElements();
    if (!overlay || overlay.classList.contains('hidden')) return;
    overlay.classList.add('hidden');
    overlay.setAttribute('aria-hidden', 'true');
    if (restoreFocus) restoreSetupWizardFocus();
}

function renderSetupWizard(readiness) {
    const { overlay, message, remediation, openDatabase } = setupWizardElements();
    if (!overlay || !message || !remediation) return;

    message.textContent = safeMessage(readiness?.database?.message, '数据库尚未就绪，请完成数据库配置。');
    const steps = Array.isArray(readiness?.database?.remediation) ? readiness.database.remediation : [];
    remediation.replaceChildren(...steps.slice(0, 8).map(step => {
        const item = document.createElement('li');
        item.textContent = safeMessage(step, '请检查数据库配置后重试。');
        return item;
    }));
    if (overlay.classList.contains('hidden')) rememberSetupWizardFocus();
    overlay.classList.remove('hidden');
    overlay.setAttribute('aria-hidden', 'false');
    openDatabase?.focus();
}

async function fetchSetupReadiness() {
    try {
        const response = await fetch('/api/setup/readiness', configurationRequestOptions({ cache: 'no-store' }));
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return await response.json();
    } catch (error) {
        console.warn('[setup-wizard] readiness request failed', {
            errorType: error?.name || 'UnknownError',
        });
        return null;
    }
}

function bindSetupWizardEvents() {
    if (setupWizardBound) return;
    const { openDatabase, skip } = setupWizardElements();
    if (!openDatabase || !skip) return;
    setupWizardBound = true;
    openDatabase.addEventListener('click', async () => {
        if (setupWizardHandoffPending) return;
        setupWizardHandoffPending = true;
        const { overlay } = setupWizardElements();
        openDatabase.disabled = true;
        overlay?.setAttribute('aria-busy', 'true');
        try {
            await openDatabaseConfiguration();
            hideSetupWizard({ restoreFocus: false });
            discardSetupWizardRestoreFocus();
        } catch (error) {
            console.error('[setup-wizard] database configuration action failed', {
                errorType: error?.name || 'UnknownError',
            });
            renderSetupWizard({ database: { message: '无法打开数据库配置，请稍后重试。' } });
        } finally {
            setupWizardHandoffPending = false;
            openDatabase.disabled = false;
            overlay?.removeAttribute('aria-busy');
        }
    });
    skip.addEventListener('click', () => {
        if (setupWizardHandoffPending) return;
        hideSetupWizard();
    });
    document.addEventListener('keydown', event => {
        const { overlay } = setupWizardElements();
        const controls = getSetupWizardFocusableControls(overlay);
        cycleSetupWizardFocus(event, controls, document.activeElement);
    }, true);
}

export async function initSetupWizard() {
    if (setupWizardInitializationPromise) return setupWizardInitializationPromise;
    setupWizardInitializationPromise = (async () => {
        bindSetupWizardEvents();
        const readiness = await fetchSetupReadiness();
        if (readiness?.runtime_status === 'setup_required') {
            renderSetupWizard(readiness);
            return true;
        }
        hideSetupWizard();
        return false;
    })();
    try {
        return await setupWizardInitializationPromise;
    } finally {
        setupWizardInitializationPromise = null;
    }
}
