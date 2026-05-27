/* ============================================================
   AlphaFoundry — Core Utilities
   ============================================================ */

// ─── API ────────────────────────────────────────────────────
const API_BASE = '';

export async function apiCall(method, url, body = null) {
    const opts = {
        method,
        headers: { 'Content-Type': 'application/json' },
    };
    if (body) opts.body = JSON.stringify(body);
    const resp = await fetch(`${API_BASE}${url}`, opts);
    if (!resp.ok) {
        const err = await resp.json().catch(() => ({ detail: resp.statusText }));
        throw new Error(err.error || err.detail || `HTTP ${resp.status}`);
    }
    return resp.json();
}

// ─── Toast ──────────────────────────────────────────────────
export function toast(msg, type = 'info') {
    const el = document.getElementById('toast');
    if (!el) return;
    el.textContent = msg;
    el.className = `toast toast-${type}`;
    setTimeout(() => el.classList.add('hidden'), 3500);
}

// ─── HTML Escape ────────────────────────────────────────────
export function esc(s) {
    if (!s) return '';
    const d = document.createElement('div');
    d.textContent = String(s);
    return d.innerHTML;
}

// ─── Loading & Error States ─────────────────────────────────
export function showLoading(container) {
    if (!container) return;
    // Remove existing error state
    const existingError = container.querySelector('.error-state');
    if (existingError) existingError.classList.add('hidden');
    // Show loading spinner
    const spinner = container.querySelector('.loading-spinner');
    if (spinner) spinner.classList.remove('hidden');
}

export function hideLoading(container) {
    if (!container) return;
    const spinner = container.querySelector('.loading-spinner');
    if (spinner) spinner.classList.add('hidden');
}

export function showError(container, message) {
    if (!container) return;
    const errorEl = container.querySelector('.error-state');
    if (!errorEl) return;
    const msgEl = errorEl.querySelector('.error-msg');
    if (msgEl) msgEl.textContent = message;
    errorEl.classList.remove('hidden');
    hideLoading(container);
}

export function clearStatus(container) {
    if (!container) return;
    hideLoading(container);
    const errorEl = container.querySelector('.error-state');
    if (errorEl) errorEl.classList.add('hidden');
}

// ─── Chart Utilities ────────────────────────────────────────
export function getChartColors() {
    const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    return {
        grid: isDark ? 'rgba(148,163,184,.15)' : 'rgba(0,0,0,.06)',
        text: isDark ? '#94a3b8' : '#64748b',
        blue: '#3182ce',
        orange: '#ed8936',
        green: '#38a169',
        red: '#e53e3e',
        purple: '#805ad5',
        colors: ['#3182ce','#ed8936','#38a169','#e53e3e','#805ad5','#d69e2e','#319795','#b83280'],
    };
}

export function applyChartDefaults() {
    const c = getChartColors();
    if (typeof Chart !== 'undefined') {
        Chart.defaults.color = c.text;
        Chart.defaults.borderColor = c.grid;
    }
}

// ─── Format Helpers ─────────────────────────────────────────
export function fmtVolume(vol) {
    if (vol === undefined || vol === null) return '--';
    if (vol >= 100000000) return `${(vol / 100000000).toFixed(2)}亿股`;
    if (vol >= 10000) return `${(vol / 10000).toFixed(2)}万股`;
    return `${vol.toFixed(0)}股`;
}

export function fmtAmount(amt) {
    if (amt === undefined || amt === null) return '--';
    if (amt >= 100000000) return `${(amt / 100000000).toFixed(2)}亿`;
    if (amt >= 10000) return `${(amt / 10000).toFixed(2)}万`;
    return `${amt.toFixed(0)}`;
}

export function fmtMarketCap(cap) {
    if (cap === undefined || cap === null) return '--';
    if (cap >= 1000000000000) return `${(cap / 1000000000000).toFixed(2)}万亿`;
    if (cap >= 100000000) return `${(cap / 100000000).toFixed(2)}亿`;
    return `${cap.toFixed(0)}`;
}

export function fmtRevenue(rev) {
    if (rev === undefined || rev === null) return '--';
    if (rev >= 100000000) return `${(rev / 100000000).toFixed(2)}亿`;
    if (rev >= 10000) return `${(rev / 10000).toFixed(2)}万`;
    return `${rev.toFixed(0)}`;
}

export function fmtNetProfit(profit) {
    if (profit === undefined || profit === null) return '--';
    if (profit >= 100000000) return `${(profit / 100000000).toFixed(2)}亿`;
    if (profit >= 10000) return `${(profit / 10000).toFixed(2)}万`;
    return `${profit.toFixed(0)}`;
}

// ─── Loading Container HTML ─────────────────────────────────
export const LOADING_HTML = `
    <div class="loading-spinner hidden">
        <div class="spinner"></div>
        <span data-i18n="common.loading">加载中...</span>
    </div>
    <div class="error-state hidden">
        <span class="error-icon">!</span>
        <span class="error-msg"></span>
        <button class="retry-btn" data-i18n="common.retry">重试</button>
    </div>
`;
