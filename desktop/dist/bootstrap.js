const DEFAULT_BACKEND_URL = 'http://127.0.0.1:8765';
const MAX_ATTEMPTS = 90;
const RETRY_DELAY_MS = 1000;

const statusEl = document.getElementById('boot-status');
const retryButton = document.getElementById('retry-button');

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

function setStatus(message) {
    if (statusEl) statusEl.textContent = message;
}

async function isBackendReady(baseUrl) {
    try {
        const response = await fetch(`${baseUrl}/health`, {
            method: 'GET',
            cache: 'no-store',
        });
        return response.ok;
    } catch (_) {
        return false;
    }
}

async function waitForBackend() {
    const baseUrl = window.ALPHAFOUNDRY_BACKEND_URL || DEFAULT_BACKEND_URL;
    if (retryButton) retryButton.hidden = true;

    for (let attempt = 1; attempt <= MAX_ATTEMPTS; attempt += 1) {
        setStatus(`正在连接本地服务... (${attempt}/${MAX_ATTEMPTS})`);
        if (await isBackendReady(baseUrl)) {
            setStatus('服务已就绪，正在打开工作台...');
            window.location.replace(`${baseUrl}/`);
            return;
        }
        await sleep(RETRY_DELAY_MS);
    }

    setStatus(`本地服务暂未就绪。请确认后端已启动，或点击重试。目标地址：${baseUrl}（请通过 http://127.0.0.1:8765/ 访问）`);
    if (retryButton) retryButton.hidden = false;
}

if (retryButton) {
    retryButton.addEventListener('click', waitForBackend);
}

waitForBackend();
