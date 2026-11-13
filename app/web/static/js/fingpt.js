import { apiCall, esc, toast } from './core.js';

let initialized = false;
let expectedOrigin = null;
let hostAvailable = false;
let frameReady = false;
let frameReadyWaiter = null;

export async function initFinGPT() {
    if (!initialized) bindEvents();
    initialized = true;
    if (await refreshHealth()) await refreshGovernance();
}

function bindEvents() {
    document.getElementById('btn-fingpt-retry')?.addEventListener('click', refreshHealth);
    document.querySelectorAll('[data-fingpt-preset]').forEach(button => {
        button.addEventListener('click', () => launchPreset(button.dataset.fingptPreset, button));
    });
    window.addEventListener('message', event => {
        if (event.origin !== expectedOrigin || !event.data) return;
        if (event.data.type === 'alphafoundry.fingpt.ready') {
            frameReady = true;
            frameReadyWaiter?.resolve();
            frameReadyWaiter = null;
            return;
        }
        if (event.data.type !== 'alphafoundry.fingpt.launch-result') return;
        if (event.data.ok) toast('任务已在 FinGPT 会话中启动。', 'success');
        else toast('DSH 未能消费启动任务，请重新创建。', 'error');
        refreshGovernance();
    });
}

async function refreshHealth() {
    const state = document.getElementById('fingpt-runtime-state');
    const frame = document.getElementById('fingpt-dsh-frame');
    const diagnostic = document.getElementById('fingpt-host-unavailable');
    const link = document.querySelector('[data-open-research-qa]');
    const panels = [...document.querySelector('.fingpt-page').children].filter(panel => panel !== link.parentElement);
    link.hidden = true;
    link.removeAttribute('href');
    try {
        const result = await apiCall('GET', '/api/v2/fingpt/health');
        if (result.retired === true) {
            const url = result.research_web_url;
            if (typeof url !== 'string' || !/^https:\/\/[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.tail[a-z0-9]+\.ts\.net(?::443)?\/#\/qa$/.test(url)) {
                throw new Error('invalid_fingpt_replacement');
            }
            hostAvailable = false;
            expectedOrigin = null;
            frameReady = false;
            frame.hidden = true;
            frame.removeAttribute('src');
            for (const panel of panels) panel.hidden = true;
            link.href = url;
            link.hidden = false;
            return false;
        }
        for (const panel of panels) panel.hidden = false;
        hostAvailable = result.available === true;
        expectedOrigin = result.embed_origin || null;
        state.textContent = hostAvailable ? 'DSH Host 已连接 · 对话正文由 DSH 保存' : 'DSH Host 未连接';
        state.classList.toggle('ready', hostAvailable);
        if (hostAvailable && result.embed_url && expectedOrigin) {
            if (frame.src !== result.embed_url) {
                frameReady = false;
                frame.src = result.embed_url;
            }
            frame.hidden = false; diagnostic.hidden = true;
            frame.contentWindow?.postMessage({ type: 'alphafoundry.fingpt.ping' }, expectedOrigin);
        } else {
            frameReady = false; frame.hidden = true; diagnostic.hidden = false;
            document.getElementById('fingpt-diagnostic-copy').textContent = result.diagnostic || '请启动本机 DSH Host 后重试。';
        }
        return true;
    } catch (error) {
        hostAvailable = false; expectedOrigin = null; frameReady = false;
        frame.hidden = true; frame.removeAttribute('src'); diagnostic.hidden = false;
        for (const panel of panels) panel.hidden = !panel.contains(diagnostic);
        state.textContent = '无法检查 FinGPT 状态';
        document.getElementById('fingpt-diagnostic-copy').textContent = 'FinGPT 状态暂不可核验，请重新检查。';
        return false;
    }
}

async function launchPreset(presetId, button) {
    button.disabled = true;
    try {
        const task = await apiCall('POST', '/api/v2/fingpt/tasks', { preset_id: presetId });
        if (presetId === 'daily-market-commentary') {
            toast('正在执行每日市场点评 Workflow…', 'info');
            await apiCall('POST', `/api/v2/fingpt/tasks/${encodeURIComponent(task.task_id)}/execute`, {});
            toast('每日市场点评已完成；产物已归档到 AlphaFoundry。', 'success');
        } else {
            if (!hostAvailable || !expectedOrigin) throw new Error('DSH Host 未就绪');
            const frame = document.getElementById('fingpt-dsh-frame');
            await waitForFrameReady(frame);
            frame.contentWindow?.postMessage({ type: 'alphafoundry.fingpt.launch', launchId: task.launch_id }, expectedOrigin);
            toast('已向 FinGPT 发送一次性启动任务。', 'info');
        }
        await refreshGovernance();
    } catch (error) {
        toast(error?.message || '任务启动失败。', 'error');
    } finally { button.disabled = false; }
}

function waitForFrameReady(frame) {
    if (frameReady) return Promise.resolve();
    frame.contentWindow?.postMessage({ type: 'alphafoundry.fingpt.ping' }, expectedOrigin);
    return new Promise((resolve, reject) => {
        const timeout = window.setTimeout(() => {
            if (frameReadyWaiter?.resolve === resolve) frameReadyWaiter = null;
            reject(new Error('DSH 对话页面尚未就绪，请稍后重试。'));
        }, 3000);
        frameReadyWaiter = {
            resolve: () => {
                window.clearTimeout(timeout);
                resolve();
            },
        };
    });
}

async function refreshGovernance() {
    try {
        const [tasks, sessions] = await Promise.all([apiCall('GET', '/api/v2/fingpt/tasks'), apiCall('GET', '/api/v2/fingpt/sessions')]);
        renderRows('fingpt-task-list', tasks.tasks || [], row => `<div class="fingpt-row"><strong>${esc(row.title)}</strong><span>${esc(row.status)}</span></div>`);
        renderRows('fingpt-session-list', sessions.sessions || [], row => `<div class="fingpt-row"><strong>${esc(row.title || row.dsh_session_id)}</strong><span>${esc(row.status)}</span></div>`);
    } catch (error) { console.warn('[fingpt] governance refresh failed', { errorType: error?.name || 'UnknownError' }); }
}

function renderRows(id, rows, render) {
    const element = document.getElementById(id);
    if (!element) return;
    element.innerHTML = rows.length ? rows.map(render).join('') : '<p>尚无记录。</p>';
}
