import { apiCall, esc, toast } from './core.js';

let initialized = false;
let templates = [];
let selectedTemplateKey = null;
let currentRun = null;
let currentWorkspace = null;
let currentSession = null;
let pendingPrefill = null;
const LOCAL_PROJECT_ID = 'local';
const RESEARCH_CONTEXT_KEY = 'research-web.context.v1';

export function initResearchWorkbench() {
    if (initialized) return;
    initialized = true;
    restoreResearchContext();
    const form = document.getElementById('research-run-form');
    const dateInput = document.getElementById('research-as-of');
    if (!form || !dateInput) return;

    dateInput.value = new Date().toISOString().slice(0, 10);
    form.addEventListener('submit', submitResearchRun);
    form.addEventListener('input', updateSubmitState);
    document.getElementById('research-subject-type')?.addEventListener('change', () => {
        syncRecommendedTemplate();
        updateSubmitState();
    });
    document.getElementById('research-template-list')?.addEventListener('click', handleTemplateClick);
    document.getElementById('research-template-list')?.addEventListener('keydown', handleTemplateKeydown);
    document.getElementById('research-run-history')?.addEventListener('click', handleHistoryClick);
    document.getElementById('research-run-outputs')?.addEventListener('click', handleOutputClick);
    document.getElementById('research-run-outputs')?.addEventListener('submit', handleEvidenceSubmit);
    document.getElementById('research-history-refresh')?.addEventListener('click', loadRunHistory);

    Promise.all([loadTemplates(), loadRunHistory()]).catch(error => {
        console.error('[research-center] initialization failed', {
            errorType: error?.name || 'UnknownError',
        });
    });
}

export function openResearchCenter(prefill = {}) {
    initResearchWorkbench();
    pendingPrefill = { ...prefill };
    applyPrefill(pendingPrefill);
}

async function loadTemplates() {
    const notice = document.getElementById('research-template-notice');
    try {
        templates = await apiCall('GET', '/api/research-templates');
        renderTemplates();
        if (pendingPrefill) applyPrefill(pendingPrefill);
        else syncRecommendedTemplate();
        updateSubmitState();
    } catch (error) {
        console.error('[research-center] template catalog load failed', {
            errorType: error?.name || 'UnknownError',
        });
        if (notice) {
            notice.className = 'research-template-notice is-warning';
            notice.textContent = '研究模板目录暂时不可用，请检查后端状态。';
        }
        throw error;
    }
}

function renderTemplates() {
    const container = document.getElementById('research-template-list');
    if (!container) return;
    container.innerHTML = templates.map(template => {
        const selected = template.template_key === selectedTemplateKey;
        return `
            <button type="button"
                    class="research-template-card ${selected ? 'is-selected' : ''}"
                    role="option"
                    aria-selected="${selected}"
                    aria-disabled="${!template.available}"
                    data-template-key="${esc(template.template_key)}">
                <small>${template.available ? 'AVAILABLE' : 'PLANNED'}</small>
                <strong>${esc(template.name)}</strong>
                <span>${esc(template.description)}</span>
            </button>`;
    }).join('');
}

function handleTemplateClick(event) {
    const card = event.target.closest('[data-template-key]');
    if (!card) return;
    selectTemplate(card.dataset.templateKey);
}

function handleTemplateKeydown(event) {
    if (!['Enter', ' '].includes(event.key)) return;
    const card = event.target.closest('[data-template-key]');
    if (!card) return;
    event.preventDefault();
    selectTemplate(card.dataset.templateKey);
}

function selectTemplate(templateKey) {
    const template = templates.find(item => item.template_key === templateKey);
    if (!template) return;
    selectedTemplateKey = templateKey;
    renderTemplates();
    updateTemplateNotice(template);
    updateSubmitState();
}

function syncRecommendedTemplate() {
    if (!templates.length) return;
    const subjectType = document.getElementById('research-subject-type')?.value || 'security';
    const selected = templates.find(item => item.template_key === selectedTemplateKey);
    if (selected?.supported_subject_types?.includes(subjectType)) {
        updateTemplateNotice(selected);
        return;
    }
    const recommended = templates.find(item => item.supported_subject_types?.includes(subjectType));
    selectedTemplateKey = recommended?.template_key || null;
    renderTemplates();
    updateTemplateNotice(recommended);
}

function updateTemplateNotice(template) {
    const notice = document.getElementById('research-template-notice');
    const label = document.getElementById('research-template-selection');
    if (label) label.textContent = template?.name || '尚未选择模板';
    if (!notice) return;
    if (!template) {
        notice.className = 'research-template-notice is-warning';
        notice.textContent = '当前对象类型没有匹配的研究模板。';
    } else if (!template.available) {
        notice.className = 'research-template-notice is-warning';
        notice.textContent = `${template.name}尚在规划中，当前不能创建 Research Run。`;
    } else {
        notice.className = 'research-template-notice';
        notice.textContent = `将使用“${template.name}”执行，并应用其证据覆盖与质量门禁。`;
    }
}

function updateSubmitState() {
    const button = document.getElementById('research-run-submit');
    if (!button || button.getAttribute('aria-busy') === 'true') return;
    const template = templates.find(item => item.template_key === selectedTemplateKey);
    const subjectType = document.getElementById('research-subject-type')?.value;
    const subjectId = document.getElementById('research-subject-id')?.value.trim();
    const question = document.getElementById('research-question')?.value.trim();
    const asOf = document.getElementById('research-as-of')?.value;
    button.disabled = !(
        template?.available
        && template.supported_subject_types?.includes(subjectType)
        && subjectId
        && question
        && asOf
    );
}

function applyPrefill(prefill) {
    const fieldMap = {
        'research-subject-type': prefill.subject_type,
        'research-subject-id': prefill.subject_id,
        'research-subject-name': prefill.display_name,
        'research-as-of': prefill.as_of,
        'research-question': prefill.question,
    };
    Object.entries(fieldMap).forEach(([id, value]) => {
        const input = document.getElementById(id);
        if (input && value) input.value = value;
    });
    if (prefill.template_key) selectedTemplateKey = prefill.template_key;
    syncRecommendedTemplate();
    updateSubmitState();
    document.getElementById('research-question')?.focus();
}

async function submitResearchRun(event) {
    event.preventDefault();
    const button = document.getElementById('research-run-submit');
    const status = document.getElementById('research-run-status');
    const outputs = document.getElementById('research-run-outputs');
    const template = templates.find(item => item.template_key === selectedTemplateKey);
    if (!button || !status || !outputs || !template?.available) return;

    setSubmitLoading(true);
    status.textContent = '正在创建并执行研究…';
    outputs.innerHTML = '<div class="empty-state">正在按研究图执行：规划 → 证据 → 质检 → 产物。</div>';
    try {
        const attachments = (document.getElementById('research-attachments')?.value || '')
            .split(',')
            .map(item => item.trim())
            .filter(Boolean);
        const date = document.getElementById('research-as-of')?.value;
        const subjectId = document.getElementById('research-subject-id')?.value.trim();
        const question = document.getElementById('research-question')?.value.trim();
        await ensureResearchContext({
            title: document.getElementById('research-subject-name')?.value.trim() || subjectId,
            question,
        });
        const createKey = globalThis.crypto?.randomUUID?.() || `run-${Date.now()}`;
        const binding = await apiCall(
            'POST',
            `/api/research-sessions/${encodeURIComponent(currentSession.session_id)}/runs`,
            {
                project_id: LOCAL_PROJECT_ID,
                workspace_id: currentWorkspace.workspace_id,
                run: {
                    template_key: template.template_key,
                    subject: {
                        subject_type: document.getElementById('research-subject-type')?.value,
                        subject_id: subjectId,
                        display_name: document.getElementById('research-subject-name')?.value.trim() || subjectId,
                    },
                    as_of: `${date}T00:00:00Z`,
                    question,
                    attachment_refs: attachments,
                    mode: 'fingpt',
                    skill_keys: [],
                },
            },
            { headers: { 'Idempotency-Key': createKey } }
        );
        const executeKey = globalThis.crypto?.randomUUID?.() || `execute-${Date.now()}`;
        const run = await apiCall(
            'POST',
            `/api/research-sessions/${encodeURIComponent(currentSession.session_id)}/runs/${encodeURIComponent(binding.run.run_id)}/execute`,
            {
                project_id: LOCAL_PROJECT_ID,
                workspace_id: currentWorkspace.workspace_id,
            },
            { headers: { 'Idempotency-Key': executeKey } }
        );
        currentRun = run;
        const result = await apiCall(
            'GET',
            `/api/research-runs/${encodeURIComponent(run.run_id)}/outputs`,
            null,
            { headers: researchScopeHeaders() }
        );
        renderResearchOutputs(result);
        setRunStatus(run.status);
        await loadRunHistory();
        toast(run.status === 'completed' ? '研究任务已完成' : '研究任务已阻塞', run.status === 'completed' ? 'success' : 'warning');
    } catch (error) {
        console.error('[research-center] research execution failed', {
            errorType: error?.name || 'UnknownError',
        });
        status.textContent = '研究任务失败';
        outputs.innerHTML = `<div class="error-state-inline">${esc(error.message || '研究任务执行失败。')}</div>`;
        toast('研究任务执行失败', 'error');
    } finally {
        currentSession = null;
        persistResearchContext();
        setSubmitLoading(false);
    }
}

async function ensureResearchContext({ title, question }) {
    if (!currentWorkspace) {
        const key = globalThis.crypto?.randomUUID?.() || `workspace-${Date.now()}`;
        currentWorkspace = await apiCall('POST', '/api/research-workspaces', {
            project_id: LOCAL_PROJECT_ID,
            title: title || '研究工作区',
        }, { headers: { 'Idempotency-Key': key } });
    }
    const key = globalThis.crypto?.randomUUID?.() || `session-${Date.now()}`;
    currentSession = await apiCall('POST', '/api/research-sessions', {
        mode: 'workspace',
        workspace_id: currentWorkspace.workspace_id,
        project_id: LOCAL_PROJECT_ID,
    }, { headers: { 'Idempotency-Key': key } });
    persistResearchContext();
    const messageKey = globalThis.crypto?.randomUUID?.() || `message-${Date.now()}`;
    await apiCall(
        'POST',
        `/api/research-sessions/${encodeURIComponent(currentSession.session_id)}/messages`,
        { role: 'user', content: question },
        { headers: { 'Idempotency-Key': messageKey, ...researchScopeHeaders() } }
    );
}

function researchScopeHeaders() {
    if (!currentWorkspace?.workspace_id) return {};
    return {
        'X-Project-ID': LOCAL_PROJECT_ID,
        'X-Workspace-ID': currentWorkspace.workspace_id,
    };
}

function persistResearchContext() {
    try {
        localStorage.setItem(RESEARCH_CONTEXT_KEY, JSON.stringify({
            project_id: LOCAL_PROJECT_ID,
            workspace: currentWorkspace,
            session: currentSession,
        }));
    } catch (error) {
        console.warn('[research-center] context persistence failed', {
            errorType: error?.name || 'UnknownError',
        });
    }
}

function restoreResearchContext() {
    try {
        const saved = JSON.parse(localStorage.getItem(RESEARCH_CONTEXT_KEY) || 'null');
        if (saved?.project_id !== LOCAL_PROJECT_ID) return;
        if (saved.workspace?.workspace_id) currentWorkspace = saved.workspace;
        currentSession = null;
    } catch (error) {
        console.warn('[research-center] context restore failed', {
            errorType: error?.name || 'UnknownError',
        });
        currentWorkspace = null;
        currentSession = null;
    }
}

function setSubmitLoading(loading) {
    const button = document.getElementById('research-run-submit');
    if (!button) return;
    button.setAttribute('aria-busy', String(loading));
    button.innerHTML = loading
        ? '<i class="codicon codicon-loading codicon-modifier-spin"></i> 正在执行'
        : '<i class="codicon codicon-play"></i> 创建并执行研究';
    if (loading) button.disabled = true;
    else updateSubmitState();
}

function setRunStatus(statusValue) {
    const status = document.getElementById('research-run-status');
    if (!status) return;
    const labels = {
        completed: '研究已完成',
        blocked: '研究已阻塞：需要补证或解决冲突',
        draft: '研究草稿',
        failed: '研究执行失败',
    };
    status.textContent = labels[statusValue] || `研究状态：${statusValue}`;
}

async function loadRunHistory() {
    const container = document.getElementById('research-run-history');
    if (!container) return;
    if (!currentWorkspace?.workspace_id) {
        container.innerHTML = '<div class="empty-state">创建研究工作区后显示历史任务。</div>';
        return;
    }
    try {
        const runs = await apiCall(
            'GET',
            '/api/research-runs',
            null,
            { headers: researchScopeHeaders() }
        );
        if (!runs.length) {
            container.innerHTML = '<div class="empty-state">还没有研究任务。</div>';
            return;
        }
        container.innerHTML = runs.map(run => `
            <button type="button" class="research-history-item" data-run-id="${esc(run.run_id)}">
                <strong>${esc(run.subject?.display_name || run.target_id)}</strong>
                <span>${esc(templateName(run.template_key))} · ${esc(run.as_of.slice(0, 10))}</span>
                <small class="is-${esc(run.status)}">${esc(run.status)}</small>
            </button>`).join('');
    } catch (error) {
        console.warn('[research-center] recent runs load failed', {
            errorType: error?.name || 'UnknownError',
        });
        container.innerHTML = '<div class="error-state-inline">无法读取最近研究任务。</div>';
    }
}

async function handleHistoryClick(event) {
    const item = event.target.closest('[data-run-id]');
    if (!item) return;
    const runId = item.dataset.runId;
    try {
        currentRun = await apiCall(
            'GET',
            `/api/research-runs/${encodeURIComponent(runId)}`,
            null,
            { headers: researchScopeHeaders() }
        );
        const result = await apiCall(
            'GET',
            `/api/research-runs/${encodeURIComponent(runId)}/outputs`,
            null,
            { headers: researchScopeHeaders() }
        );
        renderResearchOutputs(result);
        setRunStatus(currentRun.status);
    } catch (error) {
        console.error('[research-center] research run load failed', {
            runId,
            errorType: error?.name || 'UnknownError',
        });
        toast('无法打开研究任务', 'error');
    }
}

function renderResearchOutputs(result) {
    const outputs = document.getElementById('research-run-outputs');
    if (!outputs) return;
    const gateRows = (result.quality_gates || []).map(gate => `
        <li class="research-gate ${gate.passed ? 'is-passed' : 'is-blocked'}">
            <strong>${gate.passed ? '通过' : '阻塞'} · ${esc(gate.gate_key)}</strong><span>${esc(gate.message)}</span>
        </li>`).join('') || '<li class="empty-state">等待质量门禁执行。</li>';
    const claimRows = (result.claims || []).map(claim => `
        <li><strong>${esc(claim.category)}</strong><span>${esc(claim.text)}</span><small>${esc((claim.evidence_refs || []).join(', '))}</small></li>`).join('') || '<li class="empty-state">尚无可发布观点。</li>';
    const card = result.decision_card;
    const downloads = result.status === 'completed'
        ? `<div class="research-downloads">
            <button class="btn-secondary" type="button" data-download="markdown">下载 Markdown</button>
            <button class="btn-secondary" type="button" data-download="word">下载 Word</button>
        </div>`
        : '';
    const decisionCard = card ? `
        <section class="dashboard-card research-output-card">
            <div class="card-header"><h3><i class="codicon codicon-target"></i> 决策卡</h3><span>置信度 ${(card.confidence * 100).toFixed(0)}%</span></div>
            <p>${esc(card.conclusion)}</p>
            <div class="research-output-columns"><div><strong>核心驱动</strong><ul>${list(card.core_drivers)}</ul></div><div><strong>风险</strong><ul>${list(card.risks)}</ul></div></div>
        </section>` : '';
    const report = result.report_markdown ? `<pre class="research-report-preview">${esc(result.report_markdown)}</pre>` : '<div class="empty-state">报告尚未发布，先处理阻塞的质量门禁。</div>';
    const toolbar = currentRun?.subject?.subject_type && ['security', 'etf', 'index'].includes(currentRun.subject.subject_type)
        ? '<div class="research-output-toolbar"><button class="btn-secondary" type="button" data-action="back-to-asset"><i class="codicon codicon-arrow-left"></i> 返回资产观察</button></div>'
        : '';
    const evidenceForm = result.status === 'blocked' ? renderEvidenceForm() : '';
    outputs.innerHTML = `
        ${toolbar}
        <div class="research-output-grid">
            <section class="dashboard-card research-output-card"><div class="card-header"><h3><i class="codicon codicon-checklist"></i> 质量门禁</h3></div><ul class="research-gate-list">${gateRows}</ul>${evidenceForm}</section>
            <section class="dashboard-card research-output-card"><div class="card-header"><h3><i class="codicon codicon-link"></i> 观点与证据</h3></div><ul class="research-claim-list">${claimRows}</ul></section>
        </div>
        ${decisionCard}
        <section class="dashboard-card research-output-card"><div class="card-header"><h3><i class="codicon codicon-markdown"></i> 报告预览</h3>${downloads}</div>${report}</section>`;
}

function renderEvidenceForm() {
    const template = templates.find(item => item.template_key === currentRun?.template_key);
    const kinds = template?.evidence_kinds || [];
    return `
        <form class="research-evidence-form" data-research-evidence-form>
            <strong>补充一条证据并恢复</strong>
            <div class="form-grid">
                <div class="form-field"><label>证据分类</label><select name="evidence_kind" required>${kinds.map(kind => `<option value="${esc(kind)}">${esc(kind)}</option>`).join('')}</select></div>
                <div class="form-field"><label>来源层级</label><select name="source_tier"><option value="official">官方</option><option value="licensed">授权</option><option value="public">公开</option><option value="user">用户材料</option></select></div>
                <div class="form-field"><label>来源名称</label><input name="source_name" required placeholder="公司公告"></div>
                <div class="form-field"><label>精确来源锚点</label><input name="source_ref" required placeholder="annual-report-p87"></div>
                <div class="form-field research-form-wide"><label>证据摘要</label><input name="summary" required></div>
                <div class="form-field research-form-wide"><label>支持的研究观点</label><input name="claim_text" required></div>
            </div>
            <div class="research-run-actions"><button class="btn-primary" type="submit">补证并恢复运行</button></div>
        </form>`;
}

async function handleEvidenceSubmit(event) {
    const form = event.target.closest('[data-research-evidence-form]');
    if (!form || !currentRun) return;
    event.preventDefault();
    const button = form.querySelector('button[type="submit"]');
    const data = new FormData(form);
    button.disabled = true;
    try {
        const evidenceId = globalThis.crypto?.randomUUID?.() || `${Date.now()}`;
        await apiCall(
            'POST',
            `/api/research-runs/${encodeURIComponent(currentRun.run_id)}/evidence`,
            {
                evidence_id: `user-${evidenceId}`,
                evidence_kind: data.get('evidence_kind'),
                source_tier: data.get('source_tier'),
                source_name: data.get('source_name'),
                source_ref: data.get('source_ref'),
                summary: data.get('summary'),
                claim_text: data.get('claim_text'),
            },
            { headers: researchScopeHeaders() }
        );
        const resumeKey = globalThis.crypto?.randomUUID?.() || `resume-${Date.now()}`;
        currentRun = await apiCall(
            'POST',
            `/api/research-runs/${encodeURIComponent(currentRun.run_id)}/resume`,
            null,
            { headers: { 'Idempotency-Key': resumeKey, ...researchScopeHeaders() } }
        );
        const result = await apiCall(
            'GET',
            `/api/research-runs/${encodeURIComponent(currentRun.run_id)}/outputs`,
            null,
            { headers: researchScopeHeaders() }
        );
        renderResearchOutputs(result);
        setRunStatus(currentRun.status);
        await loadRunHistory();
        toast(currentRun.status === 'completed' ? '补证完成，报告已发布' : '证据已保存，仍有门禁需要处理', currentRun.status === 'completed' ? 'success' : 'warning');
    } catch (error) {
        console.error('[research-center] evidence resume failed', {
            runId: currentRun.run_id,
            errorType: error?.name || 'UnknownError',
        });
        toast(error.message || '补证恢复失败', 'error');
        button.disabled = false;
    }
}

async function handleOutputClick(event) {
    const action = event.target.closest('[data-action]')?.dataset.action;
    if (action === 'back-to-asset') window.navigateTo?.('asset-analysis');
    const download = event.target.closest('[data-download]')?.dataset.download;
    if (download && currentRun) {
        try {
            await downloadResearchArtifact(currentRun.run_id, download);
        } catch (error) {
            console.error('[research-center] artifact download failed', {
                runId: currentRun.run_id,
                artifactType: download,
                errorType: error?.name || 'UnknownError',
            });
            toast('研究产物下载失败', 'error');
        }
    }
}

async function downloadResearchArtifact(runId, artifactType) {
    const response = await fetch(
        `/api/research-runs/${encodeURIComponent(runId)}/downloads/${encodeURIComponent(artifactType)}`,
        { headers: researchScopeHeaders() }
    );
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const blobUrl = URL.createObjectURL(await response.blob());
    const link = document.createElement('a');
    link.href = blobUrl;
    link.download = `${runId}.${artifactType === 'word' ? 'docx' : 'md'}`;
    link.click();
    URL.revokeObjectURL(blobUrl);
}

function templateName(templateKey) {
    return templates.find(item => item.template_key === templateKey)?.name || templateKey;
}

function list(items) {
    return (items || []).map(item => `<li>${esc(item)}</li>`).join('') || '<li>—</li>';
}
