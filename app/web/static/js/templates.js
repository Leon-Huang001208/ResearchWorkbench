/* ============================================================
   AlphaFoundry — Templates Module
   Template management, placeholder config, render, upload, DnD
   ============================================================ */

import { apiCall, toast, esc } from './core.js';

// ─── Module State ──────────────────────────────────────────────
let currentTemplateState = {
    selectedTemplate: null,
    selectedFileType: 'docx',
    discoveredPlaceholders: [],
    placeholderValues: {},
    placeholderMappingDrafts: {},
    keywordModeDrafts: {},
    commonDefaultsDraft: null,
    commonRuleOpenState: {},
    renderedReportId: null,
    templates: [],
    reportProjects: [],
    selectedReportProject: null,
    selectedGeneratedReportFile: null,
    configEditModal: null,
    placeholderPickerSyncTimer: null,
    lastReportGenerationResult: null,
    lastReportRunLog: null,
    templateListStatus: null,
    reportProjectIssues: []
};

let currentSelectedTemplate = null;
let currentSelectedFileType = null;
let isEditMode = false;
let draggedTemplateName = null;
let draggedElement = null;
let pointerDragState = null;
let editingTemplateName = null;
let originalTemplates = [];

const REPORT_GENERATION_STEPS = [
    { key: 'check', label: '准备模板', icon: 'codicon-checklist' },
    { key: 'mapping', label: '读取底稿', icon: 'codicon-table' },
    { key: 'evidence', label: '检索证据', icon: 'codicon-search' },
    { key: 'generate', label: '生成内容', icon: 'codicon-symbol-keyword' },
    { key: 'write', label: '渲染文档', icon: 'codicon-file-code' },
    { key: 'refresh', label: '完成输出', icon: 'codicon-open-preview' }
];
const TEMPLATE_DETAIL_MODES = ['generation', 'config', 'preview', 'logs'];
const TEMPLATE_DETAIL_MODE_KEY = 'report-template-detail-mode';
const REPORT_UPLOAD_FILE_INPUTS = [
    'project-word-template-input',
    'project-ppt-template-input',
    'project-excel-workbook-input',
    'project-report-config-input',
    'project-prompt-templates-input',
    'project-data-files-input'
];

// ─── Template Page / List ──────────────────────────────────────
async function loadTemplatesPage() {
    try {
        await loadTemplatesList();
        initTemplateDropZone();
        initReportProjectUploadInputs();
        initFullPreviewViewer();
        await initTemplateSelects();
    } catch (e) {
        toast('加载模板页面失败: ' + e.message, 'error');
    }
}

async function loadTemplatesList() {
    const [legacyResult, reportProjectsResult] = await Promise.allSettled([
        apiCall('GET', '/api/templates/'),
        apiCall('GET', '/api/report-projects/')
    ]);
    const legacyLoaded = legacyResult.status === 'fulfilled';
    const reportProjectsLoaded = reportProjectsResult.status === 'fulfilled';
    const templateData = legacyLoaded ? legacyResult.value : { templates: [] };
    const reportProjectsData = reportProjectsLoaded ? reportProjectsResult.value : { projects: [], issues: [] };

    if (!legacyLoaded) {
        console.warn('Failed to load legacy templates:', legacyResult.reason);
    }
    if (!reportProjectsLoaded) {
        console.warn('Failed to load report projects:', reportProjectsResult.reason);
    }

    try {
        currentTemplateState.reportProjects = reportProjectsData.projects || [];
        currentTemplateState.reportProjectIssues = reportProjectsData.issues || [];
        currentTemplateState.templates = mergeTemplatesWithReportProjects(
            templateData.templates || [],
            currentTemplateState.reportProjects
        );
        currentTemplateState.templateListStatus = buildTemplateListStatus({
            legacyLoaded,
            reportProjectsLoaded,
            reportProjectIssues: currentTemplateState.reportProjectIssues,
            templateCount: currentTemplateState.templates.length
        });
        renderTemplateListStatus(currentTemplateState.templateListStatus);
        renderTemplatesList(
            currentTemplateState.templates,
            currentTemplateState.templateListStatus.showEmptyState
        );
    } catch (e) {
        console.error('Failed to render templates:', e);
        const container = document.getElementById('templates-grid');
        if (container) {
            container.innerHTML = '<div style="grid-column: 1/-1; text-align: center; padding: 60px 20px; color: var(--text-secondary);">模板加载失败</div>';
        }
    }
}

function buildTemplateListStatus({ legacyLoaded, reportProjectsLoaded, reportProjectIssues, templateCount }) {
    if (!legacyLoaded && !reportProjectsLoaded) {
        return {
            kind: 'error',
            message: '两个模板来源均加载失败，请检查服务后重试。',
            showEmptyState: false
        };
    }
    if (!legacyLoaded) {
        return {
            kind: 'warning',
            message: '模板库加载失败，正在显示可用报告项目。',
            showEmptyState: false
        };
    }
    if (!reportProjectsLoaded) {
        return {
            kind: 'warning',
            message: '报告项目加载失败，正在显示可用模板库。',
            showEmptyState: false
        };
    }
    if (reportProjectIssues.length) {
        return {
            kind: 'warning',
            message: `发现 ${reportProjectIssues.length} 个报告项目扫描问题，缺失资产的项目未显示。`,
            showEmptyState: false
        };
    }
    return {
        kind: 'ready',
        message: '',
        showEmptyState: templateCount === 0
    };
}

function renderTemplateListStatus(status) {
    const container = document.getElementById('template-list-status');
    if (!container) return;

    if (!status || status.kind === 'ready') {
        container.className = 'template-list-status hidden';
        container.innerHTML = '';
        return;
    }

    container.className = `template-list-status is-${status.kind}`;
    container.innerHTML = `${esc(status.message)}<button type="button" onclick="loadTemplatesList()">重试</button>`;
}

async function loadTemplates() {
    return loadTemplatesList();
}

async function loadReportProjectsList() {
    const data = await apiCall('GET', '/api/report-projects/');
    currentTemplateState.reportProjects = data.projects || [];
    currentTemplateState.reportProjectIssues = data.issues || [];
    return currentTemplateState.reportProjects;
}

function mergeTemplatesWithReportProjects(templates, projects) {
    const merged = [...templates];
    const byName = new Map(merged.map(template => [template.template_name || template.name, template]));

    projects.forEach(project => {
        const templateName = project.name || project.slug;
        const existing = byName.get(templateName) || byName.get(`${templateName}模板`);
        const projectPlaceholders = buildPlaceholderNamesFromReportProject(project);
        const projectSections = buildSectionsFromReportProject(project);
        if (existing) {
            existing.template_name = templateName;
            existing.name = templateName;
            existing.description = project.description || existing.description || '报告项目包';
            existing.report_project = project;
            existing.has_docx = existing.has_docx || Boolean(project.word_template_filename);
            existing.has_pptx = existing.has_pptx || Boolean(project.ppt_template_filename);
            existing.has_excel = existing.has_excel || Boolean(project.excel_workbook_filename);
            existing.placeholders = projectPlaceholders.length ? projectPlaceholders : (existing.placeholders || []);
            existing.sections = projectSections.length ? projectSections : (existing.sections || []);
            return;
        }

        merged.push({
            template_name: templateName,
            name: templateName,
            description: project.description || '报告项目包',
            version: '1.0',
            has_docx: Boolean(project.word_template_filename),
            has_pptx: Boolean(project.ppt_template_filename),
            has_excel: Boolean(project.excel_workbook_filename),
            placeholders: projectPlaceholders,
            sections: projectSections,
            report_project: project,
            is_report_project_only: true
        });
    });

    return merged;
}

function buildPlaceholderNamesFromReportProject(project) {
    const pptPlaceholders = project?.ppt_placeholders;
    if (Array.isArray(pptPlaceholders) && pptPlaceholders.length) {
        return pptPlaceholders.map(normalizePlaceholderName).filter(Boolean);
    }
    const wordPlaceholders = project?.word_placeholders;
    if (Array.isArray(wordPlaceholders) && wordPlaceholders.length) {
        return wordPlaceholders.map(normalizePlaceholderName).filter(Boolean);
    }

    const rawPlaceholders = project?.report_config?.placeholders;
    if (Array.isArray(rawPlaceholders)) {
        return rawPlaceholders
            .map(item => normalizePlaceholderName(item?.name || item?.key || item?.placeholder))
            .filter(Boolean);
    }
    if (rawPlaceholders && typeof rawPlaceholders === 'object') {
        return Object.keys(rawPlaceholders).map(normalizePlaceholderName).filter(Boolean);
    }
    return [];
}

function buildSectionsFromReportProject(project) {
    const projectSections = project?.report_config?.sections;
    if (Array.isArray(projectSections) && projectSections.length) {
        return projectSections;
    }

    const rawPlaceholders = project?.report_config?.placeholders;
    if (Array.isArray(rawPlaceholders)) {
        return rawPlaceholders
            .map(item => ({
                name: normalizePlaceholderName(item?.name || item?.key || item?.placeholder),
                title: item?.title || item?.label || item?.name || item?.key || item?.placeholder,
                ...item
            }))
            .filter(item => item.name);
    }
    if (rawPlaceholders && typeof rawPlaceholders === 'object') {
        return Object.entries(rawPlaceholders).map(([name, config]) => ({
            name: normalizePlaceholderName(name),
            title: config?.title || name,
            ...(config || {})
        }));
    }
    return [];
}

async function findReportProjectForTemplate(templateName) {
    if (!currentTemplateState.reportProjects.length) {
        try {
            await loadReportProjectsList();
        } catch (e) {
            console.warn('Failed to load report projects for template details:', e);
            return null;
        }
    }

    const rawTemplateName = String(templateName || '');
    const normalizedTemplateName = rawTemplateName.replace(/模板$/, '');
    return currentTemplateState.reportProjects.find(project => {
        const projectName = project.name || project.slug || '';
        return projectName === normalizedTemplateName
            || normalizedTemplateName.includes(projectName)
            || projectName.includes(normalizedTemplateName)
            || (rawTemplateName.includes('创业板50') && projectName.includes('创业板50'));
    }) || null;
}

function renderTemplatesList(templates, showEmptyState = true) {
    const container = document.getElementById('templates-grid');
    if (!container) return;

    if (!templates.length) {
        container.innerHTML = showEmptyState
            ? '<div style="grid-column: 1/-1; text-align: center; padding: 60px 20px; color: var(--text-secondary);">暂无模板，点击下方"上传"按钮添加</div>'
            : '<div style="grid-column: 1/-1; text-align: center; padding: 60px 20px; color: var(--text-secondary);">模板来源暂时不可用，请重试。</div>';
        return;
    }

    container.innerHTML = templates.map((t, index) => {
        let fileType = 'docx';
        if (t.has_docx) fileType = 'docx';
        else if (t.has_pptx) fileType = 'pptx';
        else if (t.has_excel) fileType = 'excel';
        else if (t.type) fileType = t.type;

        const templateName = t.template_name || t.name;
        const version = t.version || '1.0';
        const description = t.description || '';
        const project = t.report_project || null;

        let iconHtml = '';
        if (fileType === 'pptx') {
            iconHtml = '<span class="iphone-app-letter">P</span>';
        } else if (fileType === 'excel') {
            iconHtml = '<span class="iphone-app-letter">X</span>';
        } else {
            iconHtml = '<span class="iphone-app-letter">W</span>';
        }

        const wrapperClasses = ['iphone-template-wrapper'];
        if (isEditMode) wrapperClasses.push('edit-mode');
        const clickAttr = isEditMode ? '' : `onclick="selectTemplate('${esc(templateName)}', '${fileType}')"`;

        return `
        <div class="${wrapperClasses.join(' ')}" data-template-name="${esc(templateName)}" data-index="${index}" ${clickAttr} ${isEditMode ? 'onpointerdown="handleTemplatePointerDown(event)"' : ''}>
            <button class="iphone-delete-btn" onclick="event.stopPropagation(); deleteTemplate('${esc(templateName)}')"></button>
            <div class="iphone-app-icon ${fileType}">
                ${iconHtml}
            </div>
            ${isEditMode ? `
                <input class="iphone-template-name-input"
                       value="${esc(templateName)}"
                       data-original-name="${esc(templateName)}"
                       data-project-slug="${esc(project?.slug || '')}"
                       draggable="false"
                       onclick="event.stopPropagation()"
                       ondragstart="event.preventDefault()"
                       onkeydown="handleTemplateNameKeydown(event)"
                       onblur="saveTemplateInlineName(this)" />
            ` : `<div class="iphone-app-name">${esc(templateName)}</div>`}
        </div>
    `}).join('');
}

// ─── Template Selection / Detail ───────────────────────────────
async function selectTemplate(templateName, fileType) {
    currentSelectedTemplate = templateName;
    currentSelectedFileType = fileType;
    currentTemplateState.selectedTemplate = templateName;
    currentTemplateState.selectedFileType = fileType;
    currentTemplateState.discoveredPlaceholders = [];
    currentTemplateState.placeholderValues = {};
    currentTemplateState.placeholderMappingDrafts = {};
    currentTemplateState.keywordModeDrafts = {};
    currentTemplateState.commonDefaultsDraft = null;
    currentTemplateState.renderedReportId = null;
    currentTemplateState.selectedReportProject = null;

    const cards = document.querySelectorAll('.iphone-template-wrapper');
    cards.forEach(c => c.classList.remove('selected'));
    const selected = document.querySelector(`.iphone-template-wrapper[data-template-name="${esc(templateName)}"]`);
    if (selected) selected.classList.add('selected');

    await loadTemplateDetails(templateName);

    document.getElementById('templates-list-view').classList.add('hidden');
    document.getElementById('template-detail-view').classList.remove('hidden');

    clearPlaceholderData();
    await loadTemplatePlaceholdersForRender(templateName, fileType);
}

async function loadTemplateDetails(templateName) {
    try {
        if (!currentTemplateState.templates.length) {
            await loadTemplatesList();
        }
        const templates = currentTemplateState.templates || [];
        const template = templates.find(t => (t.template_name || t.name) === templateName);

        if (template) {
            template.report_project = template.report_project || await findReportProjectForTemplate(templateName);
            currentTemplateState.selectedReportProject = template.report_project || null;

            const detailNameEl = document.getElementById('detail-template-name');
            const detailTitleEl = document.getElementById('detail-template-title');
            const detailDescriptionEl = document.getElementById('detail-template-description');
            if (detailNameEl) detailNameEl.textContent = template.template_name || template.name;
            if (detailTitleEl) detailTitleEl.textContent = template.template_name || template.name;
            if (detailDescriptionEl) detailDescriptionEl.textContent = template.description || '';

            document.getElementById('detail-has-docx')?.classList.toggle('hidden', !template.has_docx);
            document.getElementById('detail-has-pptx')?.classList.toggle('hidden', !template.has_pptx);
            document.getElementById('detail-has-excel')?.classList.toggle('hidden', !template.has_excel);

            const iconEl = document.getElementById('detail-template-icon');
            if (iconEl) {
                iconEl.className = 'template-icon-large';
                if (template.has_docx) iconEl.classList.add('docx');
                else if (template.has_pptx) iconEl.classList.add('pptx');
                else if (template.has_excel) iconEl.classList.add('excel');
                else iconEl.classList.add('default');
            }

            const downloadTemplateBtn = document.getElementById('btn-download-template');
            if (downloadTemplateBtn) downloadTemplateBtn.onclick = () => {
                downloadTemplateFile(templateName, currentSelectedFileType);
            };

            const deleteTemplateBtn = document.getElementById('btn-delete-template');
            if (deleteTemplateBtn) deleteTemplateBtn.onclick = () => {
                deleteTemplate(templateName);
            };

            renderReportGenerationCenter(template);
        }
    } catch (e) {
        console.error('Failed to load template details:', e);
        toast('加载模板详情失败: ' + e.message, 'error');
    }
}

function goBackToTemplates() {
    document.getElementById('template-detail-view').classList.add('hidden');
    document.getElementById('templates-list-view').classList.remove('hidden');
    currentSelectedTemplate = null;
    currentSelectedFileType = null;
    currentTemplateState.selectedReportProject = null;
    currentTemplateState.keywordModeDrafts = {};
    clearPlaceholderData();
}

// ─── Upload Modal ──────────────────────────────────────────────
function openUploadModal() {
    document.getElementById('upload-template-modal').classList.remove('hidden');
    document.getElementById('template-name-input').value = '';
    setReportProjectUploadType('word');
    REPORT_UPLOAD_FILE_INPUTS.forEach(inputId => {
        const input = document.getElementById(inputId);
        if (input) input.value = '';
        updateReportProjectUploadFileLabel(inputId);
    });
    updateReportProjectUploadType();
    document.getElementById('template-upload-status').innerHTML = '';
}

function closeUploadModal() {
    document.getElementById('upload-template-modal').classList.add('hidden');
}

function initReportProjectUploadInputs() {
    document.querySelectorAll('[data-project-type-option]').forEach(button => {
        if (button.dataset.boundUploadType === 'true') return;
        button.dataset.boundUploadType = 'true';
        button.addEventListener('click', () => {
            setReportProjectUploadType(button.dataset.projectTypeOption || 'word');
        });
    });
    REPORT_UPLOAD_FILE_INPUTS.forEach(inputId => {
        const input = document.getElementById(inputId);
        if (!input || input.dataset.boundUploadLabel === 'true') return;
        input.dataset.boundUploadLabel = 'true';
        input.addEventListener('change', () => updateReportProjectUploadFileLabel(inputId));
        updateReportProjectUploadFileLabel(inputId);
    });
    updateReportProjectUploadType();
}

function setReportProjectUploadType(projectType = 'word') {
    const normalizedType = projectType === 'ppt' ? 'ppt' : 'word';
    const valueInput = document.getElementById('project-type-select');
    if (valueInput) valueInput.value = normalizedType;
    document.querySelectorAll('[data-project-type-option]').forEach(button => {
        const active = button.dataset.projectTypeOption === normalizedType;
        button.classList.toggle('active', active);
        button.setAttribute('aria-checked', active ? 'true' : 'false');
    });
    updateReportProjectUploadType();
}

function updateReportProjectUploadType() {
    const projectType = document.getElementById('project-type-select')?.value || 'word';
    document.querySelectorAll('[data-upload-template-card]').forEach(card => {
        card.classList.toggle('hidden', card.dataset.uploadTemplateCard !== projectType);
    });
}

function updateReportProjectUploadFileLabel(inputId) {
    const input = document.getElementById(inputId);
    const label = document.querySelector(`[data-file-label="${inputId}"]`);
    if (!label) return;
    const files = Array.from(input?.files || []);
    if (!files.length) {
        label.textContent = inputId === 'project-report-config-input' ? '自动生成' : '未选择';
        label.classList.remove('has-file');
        return;
    }
    label.textContent = files.length === 1 ? files[0].name : `${files.length} 个文件`;
    label.classList.add('has-file');
}

// ─── Drag & Drop Reordering ────────────────────────────────────
function handleTemplatePointerDown(event) {
    if (!isEditMode || event.button !== 0) return;
    if (event.target.closest('.iphone-template-name-input, .iphone-delete-btn')) return;

    const card = event.target.closest('.iphone-template-wrapper');
    if (!card) return;

    const rect = card.getBoundingClientRect();
    pointerDragState = {
        card,
        templateName: card.dataset.templateName,
        pointerId: event.pointerId,
        startX: event.clientX,
        startY: event.clientY,
        offsetX: event.clientX - rect.left,
        offsetY: event.clientY - rect.top,
        rect,
        placeholder: null,
        hasMoved: false
    };

    card.setPointerCapture?.(event.pointerId);
    document.addEventListener('pointermove', handleTemplatePointerMove);
    document.addEventListener('pointerup', handleTemplatePointerUp);
    document.addEventListener('pointercancel', handleTemplatePointerCancel);
}

function handleTemplatePointerMove(event) {
    if (!pointerDragState || event.pointerId !== pointerDragState.pointerId) return;

    const dx = event.clientX - pointerDragState.startX;
    const dy = event.clientY - pointerDragState.startY;
    const distance = Math.sqrt(dx * dx + dy * dy);
    if (!pointerDragState.hasMoved && distance < 6) return;

    event.preventDefault();

    if (!pointerDragState.hasMoved) {
        startTemplatePointerDrag();
    }

    const { card, offsetX, offsetY } = pointerDragState;
    card.style.left = `${event.clientX - offsetX}px`;
    card.style.top = `${event.clientY - offsetY}px`;
    moveTemplateDragPlaceholder(event.clientX, event.clientY);
}

function startTemplatePointerDrag() {
    const { card, rect } = pointerDragState;
    const placeholder = document.createElement('div');
    placeholder.className = 'iphone-template-placeholder';
    placeholder.style.width = `${rect.width}px`;
    placeholder.style.height = `${rect.height}px`;

    card.parentNode.insertBefore(placeholder, card);
    card.classList.add('dragging');
    card.style.position = 'fixed';
    card.style.left = `${rect.left}px`;
    card.style.top = `${rect.top}px`;
    card.style.width = `${rect.width}px`;
    card.style.height = `${rect.height}px`;

    pointerDragState.placeholder = placeholder;
    pointerDragState.hasMoved = true;
    draggedTemplateName = pointerDragState.templateName;
    draggedElement = card;
}

function moveTemplateDragPlaceholder(clientX, clientY) {
    const container = document.getElementById('templates-grid');
    if (!container || !pointerDragState?.placeholder) return;

    const afterElement = getDragAfterElement(container, clientX, clientY);
    if (afterElement) {
        container.insertBefore(pointerDragState.placeholder, afterElement);
    } else {
        container.appendChild(pointerDragState.placeholder);
    }
}

async function handleTemplatePointerUp(event) {
    if (!pointerDragState || event.pointerId !== pointerDragState.pointerId) return;
    await finishTemplatePointerDrag();
}

async function handleTemplatePointerCancel(event) {
    if (!pointerDragState || event.pointerId !== pointerDragState.pointerId) return;
    await finishTemplatePointerDrag({ persist: false });
}

async function finishTemplatePointerDrag({ persist = true } = {}) {
    const state = pointerDragState;
    if (!state) return;

    cleanupTemplatePointerListeners();
    state.card.releasePointerCapture?.(state.pointerId);

    if (state.hasMoved && state.placeholder) {
        state.placeholder.parentNode.insertBefore(state.card, state.placeholder);
        state.placeholder.remove();
    }

    state.card.classList.remove('dragging');
    state.card.style.position = '';
    state.card.style.left = '';
    state.card.style.top = '';
    state.card.style.width = '';
    state.card.style.height = '';

    pointerDragState = null;
    draggedTemplateName = null;
    draggedElement = null;

    if (state.hasMoved && persist) {
        await persistCurrentTemplateOrder('模板顺序已更新');
    }
}

function cleanupTemplatePointerListeners() {
    document.removeEventListener('pointermove', handleTemplatePointerMove);
    document.removeEventListener('pointerup', handleTemplatePointerUp);
    document.removeEventListener('pointercancel', handleTemplatePointerCancel);
}

function handleDragStart(event) {
    if (event.target.closest('.iphone-template-name-input')) {
        event.preventDefault();
        return;
    }
    const card = event.target.closest('.iphone-template-wrapper');
    if (!card) return;
    draggedTemplateName = card.dataset.templateName;
    draggedElement = card;
    card.classList.add('dragging');

    const dragImage = new Image();
    dragImage.src = 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7';
    event.dataTransfer.setDragImage(dragImage, 0, 0);

    event.dataTransfer.effectAllowed = 'move';
    event.dataTransfer.setData('text/plain', draggedTemplateName);
}

function handleDragOver(event) {
    event.preventDefault();
    if (event.dataTransfer) {
        event.dataTransfer.dropEffect = 'move';
    }

    const container = document.getElementById('templates-grid');
    if (!draggedTemplateName || !draggedElement) return;

    const afterElement = getDragAfterElement(container, event.clientX, event.clientY);

    if (afterElement) {
        container.insertBefore(draggedElement, afterElement);
    } else {
        container.appendChild(draggedElement);
    }
}

function getDragAfterElement(container, x, y) {
    const draggableElements = [...container.querySelectorAll('.iphone-template-wrapper:not(.dragging)')];

    return draggableElements.reduce((closest, child) => {
        const box = child.getBoundingClientRect();
        const centerX = box.left + box.width / 2;
        const centerY = box.top + box.height / 2;

        const dx = x - centerX;
        const dy = y - centerY;
        const distance = Math.sqrt(dx * dx + dy * dy);

        const isAfter = y < centerY || (Math.abs(y - centerY) < box.height / 2 && x < centerX);

        if (isAfter && (closest.element === null || distance < closest.distance)) {
            return { distance: distance, element: child };
        } else {
            return closest;
        }
    }, { distance: Number.POSITIVE_INFINITY, element: null }).element;
}

async function handleDrop(event) {
    event.preventDefault();

    await persistCurrentTemplateOrder('模板顺序已更新');

    draggedTemplateName = null;
    draggedElement = null;
}

async function persistCurrentTemplateOrder(successMessage = '模板顺序已更新') {
    const container = document.getElementById('templates-grid');
    const cards = Array.from(container.querySelectorAll('.iphone-template-wrapper'));

    cards.forEach(card => {
        card.classList.remove('dragging');
    });

    if (!draggedTemplateName) return;

    const newOrder = cards.map(c => c.dataset.templateName);

    const templateMap = {};
    currentTemplateState.templates.forEach(t => {
        const name = t.template_name || t.name;
        templateMap[name] = t;
    });
    currentTemplateState.templates = newOrder.map(name => templateMap[name]);

    try {
        const reorderableNames = getReorderableTemplateNames(newOrder);
        if (reorderableNames.length) {
            await apiCall('POST', '/api/templates/reorder', { template_names: reorderableNames });
        }
        toast(successMessage, 'success');
    } catch (e) {
        toast('更新顺序失败: ' + e.message, 'error');
        await loadTemplates();
    }
}

function handleTemplateNameKeydown(event) {
    if (event.key === 'Enter') {
        event.preventDefault();
        event.target.blur();
    }
    if (event.key === 'Escape') {
        event.preventDefault();
        event.target.value = event.target.dataset.originalName || event.target.value;
        event.target.blur();
    }
}

async function saveTemplateInlineName(input) {
    const originalName = input.dataset.originalName || '';
    const newName = input.value.trim();
    const projectSlug = input.dataset.projectSlug || '';

    if (!newName) {
        input.value = originalName;
        toast('名称不能为空', 'error');
        return;
    }
    if (newName === originalName) return;

    input.disabled = true;
    try {
        if (projectSlug) {
            await apiCall('PATCH', `/api/report-projects/${encodeURIComponent(projectSlug)}`, {
                project_name: newName
            });
            try {
                await apiCall('PATCH', `/api/templates/${encodeURIComponent(originalName)}`, {
                    template_name: newName
                });
            } catch (templateError) {
                console.warn('Template metadata rename skipped:', templateError);
            }
        } else {
            await apiCall('PATCH', `/api/templates/${encodeURIComponent(originalName)}`, {
                template_name: newName
            });
        }

        toast('名称已更新', 'success');
        await loadTemplates();
        isEditMode = true;
        document.getElementById('btn-edit-templates')?.classList.add('hidden');
        document.getElementById('btn-save-templates-order')?.classList.remove('hidden');
        renderTemplatesList(currentTemplateState.templates || []);
    } catch (e) {
        input.value = originalName;
        toast('改名失败: ' + e.message, 'error');
    } finally {
        input.disabled = false;
    }
}

// ─── Edit Template Modal ───────────────────────────────────────
function openEditTemplateModal(templateName, description, version) {
    editingTemplateName = templateName;
    document.getElementById('edit-template-name').value = templateName;
    document.getElementById('edit-template-description').value = description || '';
    document.getElementById('edit-template-version').value = version || '1.0';
    document.getElementById('edit-template-modal').classList.remove('hidden');
}

function closeEditTemplateModal() {
    document.getElementById('edit-template-modal').classList.add('hidden');
    editingTemplateName = null;
}

async function saveTemplateEdit() {
    const newName = document.getElementById('edit-template-name').value.trim();
    const newDescription = document.getElementById('edit-template-description').value.trim();
    const newVersion = document.getElementById('edit-template-version').value.trim();

    if (!newName) {
        toast('模板名称不能为空', 'error');
        return;
    }

    try {
        await apiCall('PATCH', `/api/templates/${encodeURIComponent(editingTemplateName)}`, {
            template_name: newName,
            description: newDescription,
            version: newVersion
        });

        toast('模板已更新', 'success');
        closeEditTemplateModal();
        await loadTemplates();

        if (currentSelectedTemplate === editingTemplateName && newName !== editingTemplateName) {
            currentSelectedTemplate = newName;
            currentTemplateState.selectedTemplate = newName;
            await loadTemplateDetails(newName);
        }
    } catch (e) {
        toast('更新模板失败: ' + e.message, 'error');
    }
}

// ─── Edit Mode Toggle ──────────────────────────────────────────
function toggleEditMode() {
    isEditMode = !isEditMode;

    if (isEditMode) {
        originalTemplates = [...(currentTemplateState.templates || [])];
    }

    document.getElementById('btn-edit-templates').classList.toggle('hidden', isEditMode);
    document.getElementById('btn-save-templates-order').classList.toggle('hidden', !isEditMode);

    renderTemplatesList(currentTemplateState.templates || []);
}

async function saveTemplatesOrder() {
    const cards = document.querySelectorAll('.iphone-template-wrapper');
    const newOrder = Array.from(cards).map(card => card.dataset.templateName);

    try {
        const reorderableNames = getReorderableTemplateNames(newOrder);
        if (reorderableNames.length) {
            await apiCall('POST', '/api/templates/reorder', { template_names: reorderableNames });
        }

        toast('模板已保存', 'success');
        isEditMode = false;

        document.getElementById('btn-edit-templates').classList.remove('hidden');
        document.getElementById('btn-save-templates-order').classList.add('hidden');

        await loadTemplates();
    } catch (e) {
        toast('保存失败: ' + e.message, 'error');
    }
}

function getReorderableTemplateNames(templateNames) {
    const templateByName = new Map(
        (currentTemplateState.templates || []).map(template => [
            template.template_name || template.name,
            template
        ])
    );
    return templateNames.filter(name => !templateByName.get(name)?.is_report_project_only);
}

// ─── Placeholder Management ────────────────────────────────────
function clearPlaceholderData() {
    const container = document.getElementById('render-placeholders-container');
    if (container) container.innerHTML = '';
    const result = document.getElementById('render-result');
    if (result) result.classList.add('hidden');
}

async function initTemplateSelects() {
    try {
        const data = await apiCall('GET', '/api/templates/');
        const templates = data.templates || [];

        const configureSelect = document.getElementById('configure-template-select');
        const renderSelect = document.getElementById('render-template-select');

        const optionsHtml = '<option value="">选择模板...</option>' +
            templates.map(t => {
                const templateName = t.template_name || t.name;
                return `<option value="${esc(templateName)}">${esc(templateName)}</option>`;
            }).join('');

        if (configureSelect) configureSelect.innerHTML = optionsHtml;
        if (renderSelect) renderSelect.innerHTML = optionsHtml;
    } catch (e) {
        console.error('Failed to init template selects:', e);
    }
}

async function discoverPlaceholders() {
    let templateName = currentSelectedTemplate;
    let fileType = currentSelectedFileType || 'docx';

    if (!templateName) {
        const templateSelect = document.getElementById('configure-template-select');
        const typeSelect = document.getElementById('configure-type-select');
        templateName = templateSelect?.value;
        fileType = typeSelect?.value || 'docx';
    }

    if (!templateName) {
        toast('请先选择模板', 'error');
        return;
    }

    const loadingEl = document.getElementById('discover-loading');
    const placeholderList = document.getElementById('placeholder-list');
    const noPlaceholders = document.getElementById('no-placeholders');

    if (loadingEl) loadingEl.classList.remove('hidden');
    if (placeholderList) placeholderList.innerHTML = '';
    if (noPlaceholders) noPlaceholders.classList.add('hidden');

    try {
        const data = await apiCall('GET', `/api/templates/${encodeURIComponent(templateName)}/placeholders/${fileType}`);
        currentTemplateState.discoveredPlaceholders = data.placeholders || [];
        currentTemplateState.selectedTemplate = templateName;
        currentTemplateState.selectedFileType = fileType;
        renderPlaceholders(data.placeholders || []);
    } catch (e) {
        toast('发现占位符失败: ' + e.message, 'error');
    } finally {
        if (loadingEl) loadingEl.classList.add('hidden');
    }
}

function renderPlaceholders(placeholders) {
    const container = document.getElementById('placeholder-list');
    const noPlaceholders = document.getElementById('no-placeholders');

    if (!container) return;

    if (!placeholders.length) {
        if (noPlaceholders) noPlaceholders.classList.remove('hidden');
        container.innerHTML = '';
        return;
    }

    if (noPlaceholders) noPlaceholders.classList.add('hidden');

    if (!currentTemplateState.placeholderConfigs) {
        currentTemplateState.placeholderConfigs = {};
    }

    container.innerHTML = placeholders.map(ph => {
        const name = typeof ph === 'string' ? ph : (ph.name || ph);
        const config = currentTemplateState.placeholderConfigs[name] || {};
        const type = config.type || 'string';
        const description = config.description || '';
        const prompt = config.prompt || '';

        return `
        <div class="placeholder-item" data-placeholder-name="${esc(name)}">
            <div class="placeholder-item-header">
                <div class="placeholder-name">${esc(name)}</div>
                <select class="placeholder-type-select" onchange="updatePlaceholderConfig('${esc(name)}', 'type', this.value)">
                    <option value="string" ${type === 'string' ? 'selected' : ''}>字符串</option>
                    <option value="number" ${type === 'number' ? 'selected' : ''}>数字</option>
                    <option value="date" ${type === 'date' ? 'selected' : ''}>日期</option>
                    <option value="rich_text" ${type === 'rich_text' ? 'selected' : ''}>长文本/AI生成</option>
                </select>
            </div>
            <input type="text" class="placeholder-description-input" placeholder="占位符描述"
                   value="${esc(description)}"
                   onchange="updatePlaceholderConfig('${esc(name)}', 'description', this.value)" />
            <textarea class="placeholder-prompt-textarea" placeholder="AI生成提示词（仅rich_text类型时使用，描述需要生成的内容"
                      onchange="updatePlaceholderConfig('${esc(name)}', 'prompt', this.value)">${esc(prompt)}</textarea>
        </div>
    `}).join('');
}

function updatePlaceholderConfig(name, key, value) {
    if (!currentTemplateState.placeholderConfigs) {
        currentTemplateState.placeholderConfigs = {};
    }
    if (!currentTemplateState.placeholderConfigs[name]) {
        currentTemplateState.placeholderConfigs[name] = {};
    }
    currentTemplateState.placeholderConfigs[name][key] = value;
}

function updatePlaceholderValue(name, value) {
    currentTemplateState.placeholderValues[name] = value;
}

async function loadTemplatePlaceholdersForRender(templateName, fileType = 'docx') {
    const container = document.getElementById('render-placeholders-container');
    if (!container) return;

    container.innerHTML = '<div class="loading"><div class="spinner"></div><span>正在加载占位符配置...</span></div>';

    try {
        let placeholders = [];
        const projectPlaceholders = currentTemplateState.selectedReportProject?.ppt_placeholders
            || currentTemplateState.selectedReportProject?.word_placeholders;
        if (Array.isArray(projectPlaceholders) && projectPlaceholders.length) {
            // 使用项目包解析出的 Word 占位符；PPT 项目优先使用 PPT 占位符，避免报告项目走旧模板 API。
            placeholders = projectPlaceholders;
        } else {
            try {
                const data = await apiCall('GET', `/api/templates/${encodeURIComponent(templateName)}/placeholders/${fileType}`);
                placeholders = data.placeholders || [];
            } catch (e) {
                placeholders = [];
            }
        }

        let config = {};
        try {
            const configData = await apiCall('GET', `/api/templates/${encodeURIComponent(templateName)}/config`);
            config = configData.config || {};
            currentTemplateState.placeholderConfigs = config.placeholders || {};
        } catch (e) {
            // no config is fine
        }

        renderRenderPlaceholders(placeholders, currentTemplateState.placeholderConfigs || {});
    } catch (e) {
        container.innerHTML = `<div class="error-state">加载占位符失败: ${esc(e.message)}</div>`;
        toast('加载占位符失败: ' + e.message, 'error');
    }
}

function renderRenderPlaceholders(placeholders, configs = {}) {
    const container = document.getElementById('render-placeholders-container');
    if (!container) return;

    if (!placeholders.length) {
        container.innerHTML = '<div class="empty-state"><i class="codicon codicon-search"></i><p>该模板没有配置占位符</p></div>';
        return;
    }

    container.innerHTML = placeholders.map(ph => {
        const name = typeof ph === 'string' ? ph : (ph.name || ph);
        const config = configs[name] || {};
        const type = config.type || 'string';
        const existingValue = currentTemplateState.placeholderValues[name] || '';

        let inputHtml = '';
        if (type === 'rich_text') {
            inputHtml = `
                <textarea class="render-placeholder-textarea" placeholder="输入内容或点击右侧AI按钮生成"
                          data-placeholder-name="${esc(name)}"
                          onchange="updatePlaceholderValue('${esc(name)}', this.value)">${esc(existingValue)}</textarea>
                <button class="btn-ai-generate" onclick="generateAiContent('${esc(name)}')">
                    <i class="codicon codicon-hubot"></i>
                    AI生成
                </button>
            `;
        } else {
            inputHtml = `
                <input type="text" class="render-placeholder-input" placeholder="输入值"
                       value="${esc(existingValue)}"
                       data-placeholder-name="${esc(name)}"
                       onchange="updatePlaceholderValue('${esc(name)}', this.value)" />
            `;
        }

        return `
        <div class="render-placeholder-item">
            <div class="render-placeholder-header">
                <div class="render-placeholder-name">${esc(name)}</div>
                <div class="render-placeholder-type">${type === 'rich_text' ? 'AI生成文本' : type}</div>
            </div>
            ${inputHtml}
        </div>
        `}).join('');
}

// ─── Report Template Workbench ────────────────────────────────
function renderReportGenerationCenter(template) {
    const placeholders = getTemplateWorkbenchPlaceholders(template);
    const sections = getTemplateWorkbenchSections(template);
    const readiness = buildGenerationReadiness(template, sections, placeholders);

    renderGenerationHero(template, readiness);
    renderGenerationStatusStrip(readiness);
    renderGenerationStepContext(template, readiness);
    renderRecentGenerationPanel(template);
    loadPreviewManifest(template);
    renderTemplateLogPanel(template);
    renderAdvancedMaintenance(template);
    applyTemplateDetailMode(getStoredTemplateDetailMode());
}

function getStoredTemplateDetailMode() {
    try {
        const mode = localStorage.getItem(TEMPLATE_DETAIL_MODE_KEY);
        return TEMPLATE_DETAIL_MODES.includes(mode) ? mode : 'generation';
    } catch (e) {
        return 'generation';
    }
}

function setStoredTemplateDetailMode(mode) {
    try {
        localStorage.setItem(TEMPLATE_DETAIL_MODE_KEY, mode);
    } catch (e) {
        // Preference persistence is optional.
    }
}

function applyTemplateDetailMode(mode = 'both') {
    const normalizedMode = TEMPLATE_DETAIL_MODES.includes(mode) ? mode : 'generation';
    const generationPanel = document.getElementById('template-generation-overview');
    const configPanel = document.getElementById('template-advanced-maintenance');
    const previewPanel = document.getElementById('template-generation-preview-panel');
    const logPanel = document.getElementById('template-generation-log-panel');
    const showGeneration = normalizedMode === 'generation';
    const showConfig = normalizedMode === 'config';

    if (generationPanel) generationPanel.classList.toggle('hidden', !showGeneration);
    if (configPanel) {
        configPanel.classList.toggle('hidden', !showConfig);
        if (showConfig) configPanel.open = true;
    }
    if (previewPanel) previewPanel.classList.toggle('hidden', normalizedMode !== 'preview');
    if (logPanel) logPanel.classList.toggle('hidden', normalizedMode !== 'logs');

    document.querySelectorAll('[data-template-detail-mode]').forEach(button => {
        button.classList.toggle('active', button.dataset.templateDetailMode === normalizedMode);
    });
}

function bindTemplateDetailModeTabs() {
    document.querySelectorAll('[data-template-detail-mode]').forEach(button => {
        if (button.dataset.bound) return;
        button.dataset.bound = 'true';
        button.addEventListener('click', () => {
            const mode = button.dataset.templateDetailMode || 'both';
            setStoredTemplateDetailMode(mode);
            applyTemplateDetailMode(mode);
        });
    });
}

function buildGenerationReadiness(template, sections, placeholders) {
    const assetChecks = buildTemplateAssetChecks(template, sections);
    const validationChecks = buildTemplateValidationChecks(template, sections, placeholders);
    const compiledPlan = getCompiledReportPlan(template);
    const compiledPlanItems = buildCompiledPlanReadinessItems(compiledPlan);
    const placeholderReadiness = compiledPlanItems.length ? compiledPlanItems : buildPlaceholderReadinessItems(template, placeholders);
    const excelRows = buildExcelMappingRows(template);
    const generatedReports = Array.isArray(template.report_project?.generated_reports)
        ? template.report_project.generated_reports
        : [];

    const readyAssets = assetChecks.filter(asset => asset.ok).length;
    const passedChecks = validationChecks.filter(check => check.ok).length;
    const placeholderIssueCount = placeholderReadiness.filter(item => !item.ok).length;
    const pendingIssueCount = assetChecks.filter(asset => !asset.ok).length
        + validationChecks.filter(check => !check.ok).length
        + placeholderIssueCount;
    const dataOk = readyAssets === assetChecks.length && excelRows.length > 0;
    const contentOk = passedChecks === validationChecks.length && placeholderIssueCount === 0;
    const outputOk = generatedReports.length > 0 || dataOk && contentOk;
    const warningCount = validationChecks.length - passedChecks + placeholderIssueCount;

    return {
        assetChecks,
        validationChecks,
        placeholderReadiness: placeholderReadiness,
        compiledPlan,
        excelRows,
        generatedReports,
        latestReport: generatedReports[0] || null,
        dataOk,
        contentOk,
        outputOk,
        warningCount,
        pendingIssueCount,
        readyAssets,
        totalAssets: assetChecks.length,
        passedChecks,
        totalChecks: validationChecks.length,
        placeholderIssueCount,
        passedReadinessChecks: readyAssets + passedChecks + placeholderReadiness.filter(item => item.ok).length,
        totalReadinessChecks: assetChecks.length + validationChecks.length + placeholderReadiness.length,
        placeholderCount: placeholders.length || sections.length
    };
}

function getCompiledReportPlan(template) {
    const compiledPlan = template?.report_project?.compiled_plan;
    return compiledPlan && typeof compiledPlan === 'object' ? compiledPlan : null;
}

function buildCompiledPlanReadinessItems(compiledPlan) {
    const placeholders = Array.isArray(compiledPlan?.placeholders)
        ? compiledPlan.placeholders
        : [];
    return placeholders.map(item => {
        const warnings = Array.isArray(item.warnings) ? item.warnings : [];
        const ok = Boolean(
            item.deterministic
            || (item.prompt_found && item.retrieval_ready && !warnings.length)
        );
        const message = warnings[0]
            || (!item.prompt_found ? `缺少 Prompt 模板 ${item.prompt_template || item.title || ''}` : '')
            || (!item.retrieval_ready ? '缺少检索关键词或 Query' : '')
            || '后端计划检查未通过';
        return {
            placeholderName: normalizePlaceholderName(item.placeholder || item.title || ''),
            mapping: {
                type: item.output_type || 'paragraph',
                prompt_template: item.prompt_template || ''
            },
            ok,
            issue: ok ? null : {
                message: `后端计划：${message}`,
                editorSection: item.prompt_found ? 'query' : 'basic'
            },
            status: {
                ok,
                state: ok ? 'ready' : 'missing',
                label: ok ? '可生成' : '缺配置',
                detail: ok ? '后端计划检查通过' : message
            },
            editorSection: item.prompt_found ? 'query' : 'basic'
        };
    });
}

function getTemplateGenerationPreflight(template = getCurrentWorkbenchTemplate()) {
    const safeTemplate = template || {};
    const sections = getTemplateWorkbenchSections(safeTemplate);
    const placeholders = getTemplateWorkbenchPlaceholders(safeTemplate);
    const readiness = buildGenerationReadiness(safeTemplate, sections, placeholders);
    const issues = [
        ...readiness.assetChecks.filter(item => !item.ok),
        ...readiness.validationChecks.filter(item => !item.ok),
        ...readiness.placeholderReadiness.filter(item => !item.ok)
    ];
    return {
        ok: Boolean(template && readiness.dataOk && readiness.contentOk),
        template: safeTemplate,
        sections,
        placeholders,
        readiness,
        issues
    };
}

function blockReportGenerationForPreflight(preflight) {
    const template = preflight?.template || getCurrentWorkbenchTemplate() || {};
    renderTemplateValidationPreview(template, preflight.sections, preflight.placeholders);
    openProjectCheckPanel('template-project-check-actions');
    setGenerationFlowState('check', '生成预检未通过', '请先处理占位符配置问题');
    setText('template-generation-current-step-summary', '请先处理生成预检中的占位符配置问题');
    toggleFlowActions(false);
    toast('请先处理生成预检中的占位符配置问题', 'warning');
}

function renderGenerationHero(template, readiness) {
    const templateName = template.template_name || template.name || currentSelectedTemplate || '周报';
    const project = template.report_project || null;
    const titleEls = [
        document.getElementById('template-generation-title'),
        document.getElementById('template-config-title')
    ].filter(Boolean);
    const periodInputEls = [
        document.getElementById('template-generation-period-input'),
        document.getElementById('template-config-period-input')
    ].filter(Boolean);
    const lookbackInputEls = [
        document.getElementById('template-generation-lookback-input'),
        document.getElementById('template-config-lookback-input')
    ].filter(Boolean);
    const placeholderTotalEls = [
        document.getElementById('template-generation-placeholder-total'),
        document.getElementById('template-config-placeholder-total')
    ].filter(Boolean);
    const healthEls = [
        document.getElementById('template-generation-health'),
        document.getElementById('template-config-health')
    ].filter(Boolean);
    const actionHintEl = document.getElementById('template-generation-action-hint');

    const canGenerate = Boolean(readiness.dataOk && readiness.contentOk);
    const generationOptions = getReportProjectGenerationOptions();
    const reportDateText = generationOptions.report_date || getDefaultReportDate();
    const lookbackDays = generationOptions.lookback_days || 7;

    titleEls.forEach(el => { el.textContent = templateName; });
    periodInputEls.forEach(el => { el.value = reportDateText; });
    lookbackInputEls.forEach(el => { el.value = lookbackDays; });
    placeholderTotalEls.forEach(el => { el.textContent = `${readiness.placeholderCount} 个占位符`; });
    healthEls.forEach(healthEl => {
        healthEl.textContent = canGenerate ? '可生成' : '需检查';
        healthEl.classList.toggle('ok', canGenerate);
        healthEl.classList.toggle('pending', !canGenerate);
    });
    if (actionHintEl) {
        actionHintEl.textContent = canGenerate
            ? '资料和内容已就绪，生成后可预览和下载 Word'
            : `还有 ${readiness.pendingIssueCount || 1} 项需要处理，建议先打开生成前检查`;
    }

    if (project) ensureSelectedGeneratedReport(project);
    bindHeroMetaInputs();
}

let _heroMetaInputsBound = false;

function bindHeroMetaInputs() {
    if (_heroMetaInputsBound) return;
    _heroMetaInputsBound = true;

    const dateInputs = [
        document.getElementById('template-generation-period-input'),
        document.getElementById('template-config-period-input')
    ].filter(Boolean);
    const lookbackInputs = [
        document.getElementById('template-generation-lookback-input'),
        document.getElementById('template-config-lookback-input')
    ].filter(Boolean);

    if (!dateInputs.length && !lookbackInputs.length) {
        _heroMetaInputsBound = false;
        return;
    }

    const sync = () => {
        const template = getCurrentWorkbenchTemplate();
        if (!template) return;
        const defaults = getEditableCommonDefaults(template);

        const dateEl = dateInputs.find(el => document.contains(el));
        const lookbackEl = lookbackInputs.find(el => document.contains(el));

        const reportDate = dateEl?.value || getDefaultReportDate();
        const lookbackDays = Math.max(1, Math.min(90,
            Number(lookbackEl?.value) || 7
        ));
        const startDate = getDefaultEvidenceStartDate(reportDate, lookbackDays);
        const endDate = reportDate;

        // Sync values across both heroes
        dateInputs.forEach(el => { el.value = reportDate; });
        lookbackInputs.forEach(el => { el.value = lookbackDays; });

        currentTemplateState.commonDefaultsDraft = {
            ...defaults,
            report_period: {
                ...(defaults.report_period || {}),
                report_date: reportDate,
                start_date: startDate,
                end_date: endDate,
                lookback_days: lookbackDays
            }
        };
        refreshCommonConfigSurfaces(template);
        renderSelectedSourceFragment(template);
    };

    dateInputs.forEach(el => el.addEventListener('change', sync));
    lookbackInputs.forEach(el => el.addEventListener('change', sync));
}

function refreshGenerationHeroMeta(template = getCurrentWorkbenchTemplate()) {
    if (!template) return;
    const placeholders = getTemplateWorkbenchPlaceholders(template);
    const sections = getTemplateWorkbenchSections(template);
    renderGenerationHero(template, buildGenerationReadiness(template, sections, placeholders));
}

function renderGenerationStatusStrip(readiness) {
    renderProjectCheckSummary(readiness);
    const dataSummary = `素材 ${readiness.readyAssets}/${readiness.totalAssets} · 数据范围 ${readiness.excelRows.length}`;
    const contentSummary = `预检 ${readiness.passedChecks}/${readiness.totalChecks} · 警告 ${readiness.warningCount}`;
    const outputSummary = readiness.latestReport ? '最近版本可预览和下载' : '生成后可预览和下载';
    updateGenerationStep('template-generation-step-data', 'template-generation-data-summary', readiness.dataOk, dataSummary);
    updateGenerationStep('template-generation-step-content', 'template-generation-content-summary', readiness.contentOk, contentSummary);
    updateGenerationStep('template-generation-step-output', 'template-generation-output-summary', readiness.outputOk, outputSummary);
    setGenerationFlowState(readiness.latestReport ? 'refresh' : 'check', readiness.latestReport ? '已完成' : '等待生成');
}

function renderProjectCheckSummary(readiness) {
    const summaryEl = document.getElementById('template-project-check-summary');
    const statusEl = document.getElementById('template-project-check-status');
    const pending = readiness.pendingIssueCount || 0;
    const passed = readiness.passedReadinessChecks || 0;
    const total = readiness.totalReadinessChecks || 0;

    if (summaryEl) {
        summaryEl.textContent = pending
            ? `${passed}/${total} 项通过 · 点击查看待处理项`
            : `${total} 项通过 · 可直接生成`;
    }
    if (statusEl) {
        statusEl.textContent = pending ? `${pending} 项待处理` : '可直接生成';
        statusEl.classList.toggle('warning', pending > 0);
    }
}

function updateGenerationStep(stepId, summaryId, ok, summary) {
    const step = document.getElementById(stepId);
    const summaryEl = document.getElementById(summaryId);
    if (step) {
        step.classList.toggle('ok', Boolean(ok));
        step.classList.toggle('pending', !ok);
    }
    if (summaryEl) summaryEl.textContent = summary;
}

function setGenerationFlowState(activeKey = 'generate', label = '', detail = '') {
    const activeIndex = Math.max(0, REPORT_GENERATION_STEPS.findIndex(step => step.key === activeKey));
    document.querySelectorAll('[data-generation-flow-step]').forEach((stepEl) => {
        const key = stepEl.dataset.generationFlowStep;
        const index = REPORT_GENERATION_STEPS.findIndex(step => step.key === key);
        const isDone = index >= 0 && index < activeIndex;
        const isActive = key === activeKey;
        stepEl.classList.toggle('done', isDone);
        stepEl.classList.toggle('active', isActive);
        stepEl.classList.toggle('pending', !isDone && !isActive);
        // 移除之前的错误状态
        stepEl.classList.remove('error');
        const statusEl = stepEl.querySelector('em');
        if (statusEl) {
            if (isDone) {
                statusEl.textContent = '完成';
            } else if (isActive) {
                statusEl.textContent = detail || '当前';
            } else {
                statusEl.textContent = '等待';
            }
        }
    });
    const progressLabel = document.getElementById('template-generation-progress-label');
    if (progressLabel) progressLabel.textContent = label || '生成流程';
    syncFlowStepDescription(activeKey);
}

function syncFlowStepDescription(activeKey) {
    const msgEl = document.getElementById('template-generation-progress-message');
    if (!msgEl) return;
    const stepEl = document.querySelector(`[data-generation-flow-step="${activeKey}"]`);
    if (!stepEl) { msgEl.textContent = ''; return; }
    const smallEl = stepEl.querySelector('small');
    msgEl.textContent = smallEl ? smallEl.textContent : '';
}

function renderGenerationStepContext(template, readiness) {
    const placeholders = getTemplateWorkbenchPlaceholders(template);
    const selectedName = getSelectedPlaceholderName(template, placeholders);
    setText(
        'template-generation-current-step-summary',
        readiness.latestReport
            ? '最近版本可预览和下载'
            : (selectedName ? `下一步将生成：${inferPlaceholderTitle(selectedName)}` : '等待启动')
    );
}

function setText(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value == null ? '' : String(value);
}

function getSelectedPlaceholderName(template, placeholders = []) {
    if (currentTemplateState.selectedPlaceholderName) return currentTemplateState.selectedPlaceholderName;
    if (placeholders.length) return placeholders[0];
    const sections = getTemplateWorkbenchSections(template);
    return sections[0]?.placeholder || '';
}

function buildGenerationPromptSummary(template, selectedName, mapping) {
    if (!selectedName) return '选择占位符后展示当前段落使用的 Prompt、变量和写作约束。';
    const project = template.report_project || null;
    const promptTemplate = mapping.prompt_template || resolvePromptTemplateName(selectedName, project);
    const querySource = mapping.query_source || inferQuerySource(selectedName, project);
    const fixedPrefix = mapping.fixed_prefix || mapping.template || '';
    if (fixedPrefix) return fixedPrefix;
    return `${inferPlaceholderTitle(selectedName)} 使用 ${promptTemplate || '默认 Prompt'}，检索来源：${querySource || '模板内置'}。严格依据 evidence、Excel 变量和写作参数生成，不补充外部判断。`;
}

function renderGenerationLiveLog(readiness) {
    const log = document.getElementById('template-generation-live-log');
    if (!log) return;
    const rows = [
        ['准备', `模板资产 ${readiness.readyAssets}/${readiness.totalAssets}`, readiness.dataOk ? '完成' : '待检查'],
        ['映射', `Excel 数据范围 ${readiness.excelRows.length}`, readiness.excelRows.length ? '完成' : '等待'],
        ['预检', `内容检查 ${readiness.passedChecks}/${readiness.totalChecks}`, readiness.contentOk ? '完成' : '待处理'],
        ['输出', readiness.latestReport ? readiness.latestReport.file_name : '尚未生成', readiness.latestReport ? '可用' : '等待']
    ];
    log.innerHTML = rows.map(([time, message, status]) => `
        <div class="template-generation-live-log-row">
            <span>${esc(time)}</span>
            <strong>${esc(message)}</strong>
            <em>${esc(status)}</em>
        </div>
    `).join('');
}

function getGeneratedReports(project) {
    return Array.isArray(project?.generated_reports) ? project.generated_reports : [];
}

function ensureSelectedGeneratedReport(project) {
    const reports = getGeneratedReports(project);
    if (!reports.length) {
        currentTemplateState.selectedGeneratedReportFile = null;
        return null;
    }
    const selected = reports.find(report => report.file_name === currentTemplateState.selectedGeneratedReportFile);
    if (selected) return selected;
    currentTemplateState.selectedGeneratedReportFile = reports[0]?.file_name || null;
    return reports[0] || null;
}

function getSelectedGeneratedReport(project) {
    return ensureSelectedGeneratedReport(project);
}

function getGeneratedReportUrls(project, report) {
    if (!project?.slug || !report?.file_name) {
        return { previewUrl: '', downloadUrl: '' };
    }
    return {
        previewUrl: `/api/report-projects/${encodeURIComponent(project.slug)}/preview/${encodeURIComponent(report.file_name)}`,
        downloadUrl: `/api/report-projects/${encodeURIComponent(project.slug)}/download/${encodeURIComponent(report.file_name)}`
    };
}

function buildDeliveryCheckRows(runResult, runLog, latestReport, readiness) {
    const sections = Array.isArray(runLog?.generation?.sections)
        ? runLog.generation.sections
        : [];
    const generatedCount = runResult?.generated_placeholder_count
        ?? sections.length
        ?? 0;
    const hasGenerationMetrics = Boolean(runResult || sections.length);
    const missingCount = hasGenerationMetrics
        ? Math.max(0, (readiness?.placeholderCount || 0) - generatedCount)
        : 0;
    const evidenceTotal = runResult?.evidence_count
        ?? sections.reduce((total, section) => total + Number(section.evidence_count || 0), 0);
    // runResult.warnings 后端已合并 generation + section + chart + table 四类 warning，
    // 不再重复叠加 runLog.generation.warnings 和 sections[*].warnings 避免前端重复计数
    const warnings = [
        ...(runResult?.warnings || []),
    ];
    const emptyPlaceholderCount = runResult?.empty_placeholder_count
        ?? runLog?.output?.empty_placeholder_count
        ?? missingCount;
    const chartTableWarnings = warnings.filter(warning => /图表|表格|chart|table/i.test(String(warning)));
    return [
        {
            label: '生成段落',
            value: generatedCount ? `${generatedCount} 段` : (latestReport ? '已生成' : '待生成'),
            ok: Boolean(generatedCount || latestReport)
        },
        {
            label: '缺失段落',
            value: `${missingCount} 个`,
            ok: missingCount === 0
        },
        {
            label: 'Evidence 总数',
            value: `${evidenceTotal || 0} 条`,
            ok: evidenceTotal > 0 || !sections.length
        },
        {
            label: 'Warnings',
            value: `${warnings.length} 条`,
            ok: warnings.length === 0
        },
        {
            label: '空占位符',
            value: `${emptyPlaceholderCount || 0} 个`,
            ok: !emptyPlaceholderCount
        },
        {
            label: '图表/表格',
            value: chartTableWarnings.length ? `${chartTableWarnings.length} 条警告` : '未见阻断',
            ok: chartTableWarnings.length === 0
        }
    ];
}

function renderDeliveryCheckCard(runResult, runLog, latestReport, readiness) {
    if (!latestReport && !runResult) return '';
    const rows = buildDeliveryCheckRows(runResult, runLog, latestReport, readiness);
    const passed = rows.filter(row => row.ok).length;
    return `
        <div class="template-delivery-check-card">
            <div class="template-delivery-check-title">
                <span>交付检查</span>
                <strong>${passed}/${rows.length} 通过</strong>
            </div>
            <div class="template-delivery-check-grid">
                ${rows.map(row => `
                    <div class="template-delivery-check-item ${row.ok ? 'ok' : 'pending'}">
                        <span>${esc(row.label)}</span>
                        <strong>${esc(row.value)}</strong>
                    </div>
                `).join('')}
            </div>
        </div>
    `;
}

function selectGeneratedReport(fileName, { openPreview = false } = {}) {
    currentTemplateState.selectedGeneratedReportFile = fileName || null;
    const template = getCurrentWorkbenchTemplate();
    if (!template) return;
    renderRecentGenerationPanel(template);
    loadPreviewManifest(template);
    renderTemplateLogPanel(template);
    if (openPreview) {
        setStoredTemplateDetailMode('preview');
        applyTemplateDetailMode('preview');
    }
}

function renderRecentGenerationPanel(template) {
    const project = template.report_project || null;
    const placeholders = getTemplateWorkbenchPlaceholders(template);
    const sections = getTemplateWorkbenchSections(template);
    const readiness = buildGenerationReadiness(template, sections, placeholders);
    const card = document.getElementById('template-recent-generation-card');
    if (!card) return;

    const generatedReports = getGeneratedReports(project);
    const selectedReport = getSelectedGeneratedReport(project);
    const { previewUrl, downloadUrl } = getGeneratedReportUrls(project, selectedReport);
    const previewAction = document.querySelector('[data-template-report-action="preview"]');
    const folderAction = document.querySelector('[data-template-report-action="folder"]');
    const downloadAction = document.querySelector('[data-template-report-action="download"]');
    if (previewAction) {
        previewAction.disabled = !previewUrl;
        previewAction.onclick = previewUrl ? () => selectGeneratedReport(selectedReport.file_name, { openPreview: true }) : null;
    }
    if (folderAction) {
        folderAction.disabled = !project?.slug || !selectedReport;
        folderAction.onclick = project?.slug && selectedReport
            ? () => openReportProjectOutputFolder(project.slug, selectedReport.file_name)
            : null;
    }
    if (downloadAction) {
        downloadAction.href = downloadUrl || '#';
        downloadAction.classList.toggle('disabled', !downloadUrl);
        downloadAction.setAttribute('aria-disabled', downloadUrl ? 'false' : 'true');
    }

    if (!generatedReports.length) {
        card.innerHTML = `
            <div class=”template-result-empty”>
                <i class=”codicon codicon-file”></i>
                <span>尚未生成。点击”生成报告”后，这里会显示历史版本。</span>
            </div>
        `;
    }

    const deliveryCheck = renderDeliveryCheckCard(
        currentTemplateState.lastReportGenerationResult,
        currentTemplateState.lastReportRunLog,
        selectedReport,
        readiness
    );

    const deliveryPanel = document.getElementById('template-delivery-check-panel');
    if (deliveryPanel) {
        deliveryPanel.innerHTML = deliveryCheck || '';
    }

    if (!generatedReports.length) {
        return;
    }

    card.innerHTML = `
        <div class="template-generated-report-list" role="listbox" aria-label="生成报告历史">
            ${generatedReports.map((report, index) => {
                const selected = report.file_name === selectedReport?.file_name;
                return `
                    <button type="button"
                            class="template-generated-report-item ${selected ? 'selected' : ''}"
                            role="option"
                            aria-selected="${selected ? 'true' : 'false'}"
                            data-template-generated-report="${esc(report.file_name || '')}">
                        <i class="codicon codicon-file-text"></i>
                        <span>
                            <strong>${esc(report.file_name || '生成文档')}</strong>
                            <small>${esc(formatGeneratedAt(report.generated_at))}</small>
                        </span>
                        ${index === 0 ? '<em>最新</em>' : ''}
                    </button>
                `;
            }).join('')}
        </div>
    `;
    card.querySelectorAll('[data-template-generated-report]').forEach(button => {
        button.addEventListener('click', () => selectGeneratedReport(button.dataset.templateGeneratedReport));
    });
}

// ─── Full Preview Viewer (page-image based) ──────────────────

const FULL_PREVIEW_STORAGE_KEY = 'alpha-foundry-full-word-preview';
const FULL_PREVIEW_MIN_ZOOM = 0.18;
const FULL_PREVIEW_MAX_ZOOM = 1.8;
const FULL_PREVIEW_ZOOM_STEP = 0.08;

function _fullPreviewDom() {
    return {
        panel: document.querySelector('.word-preview-panel'),
        title: document.querySelector('[data-preview-title]'),
        file: document.querySelector('[data-preview-file]'),
        body: document.querySelector('.word-preview-body'),
        scroller: document.querySelector('[data-preview-scroller]'),
        stage: document.querySelector('[data-preview-stage]'),
        rail: document.querySelector('[data-preview-thumbnail-rail]'),
        empty: document.getElementById('word-preview-empty-state'),
        thumbToggle: document.querySelector('[data-preview-thumbnails-toggle]'),
        zoomOut: document.querySelector('[data-preview-zoom-out]'),
        zoomIn: document.querySelector('[data-preview-zoom-in]'),
        zoomInput: document.querySelector('[data-preview-zoom-input]'),
        fitWidth: document.querySelector('[data-preview-fit-width]'),
        fitPage: document.querySelector('[data-preview-fit-page]'),
        pageInput: document.querySelector('[data-preview-page-input]'),
        pageTotal: document.querySelector('[data-preview-page-total]'),
        pageRange: document.querySelector('[data-preview-page-range]'),
        layoutButtons: Array.from(document.querySelectorAll('[data-preview-layout]')),
    };
}

function _fullPreviewReadStorage() {
    try { return JSON.parse(localStorage.getItem(FULL_PREVIEW_STORAGE_KEY) || '{}'); } catch (e) { return {}; }
}

function _fullPreviewPersist(state) {
    try {
        localStorage.setItem(FULL_PREVIEW_STORAGE_KEY, JSON.stringify({
            zoom: state.zoom, layout: state.layout, thumbnails: state.thumbnails
        }));
    } catch (e) { /* optional */ }
}

function _fullPreviewClamp(value, min, max) { return Math.min(max, Math.max(min, value)); }

function _fullPreviewJoinUrl(base, src) {
    if (!base || /^([a-z]+:)?\/\//i.test(src) || src.startsWith('data:') || src.startsWith('/')) return src;
    return base.replace(/\/+$/, '') + '/' + src.replace(/^\.?\//, '');
}

function initFullPreviewViewer() {
    const dom = _fullPreviewDom();
    if (!dom.panel) return;

    const state = currentTemplateState._previewViewer || {
        manifest: null,
        pages: [],
        currentPage: 1,
        zoom: _fullPreviewClamp(Number(_fullPreviewReadStorage().zoom) || 0.44, FULL_PREVIEW_MIN_ZOOM, FULL_PREVIEW_MAX_ZOOM),
        layout: 'double',
        thumbnails: true,
        observer: null,
        scrollTimer: 0,
    };
    currentTemplateState._previewViewer = state;

    const saved = _fullPreviewReadStorage();
    if (saved.layout === 'single') state.layout = 'single';
    if (saved.thumbnails === false) state.thumbnails = false;

    // ── event wiring (once) ──

    dom.thumbToggle?.addEventListener('click', () => {
        state.thumbnails = !state.thumbnails;
        _fullPreviewApplyChrome(state, dom);
        _fullPreviewPersist(state);
        requestAnimationFrame(() => _fullPreviewFitMode(state, dom, 'width'));
    });

    dom.zoomOut?.addEventListener('click', () => _fullPreviewSetZoom(state, dom, state.zoom - FULL_PREVIEW_ZOOM_STEP));
    dom.zoomIn?.addEventListener('click', () => _fullPreviewSetZoom(state, dom, state.zoom + FULL_PREVIEW_ZOOM_STEP));
    dom.fitWidth?.addEventListener('click', () => _fullPreviewFitMode(state, dom, 'width'));
    dom.fitPage?.addEventListener('click', () => _fullPreviewFitMode(state, dom, 'page'));

    dom.zoomInput?.addEventListener('keydown', (e) => { if (e.key === 'Enter') _fullPreviewCommitZoom(state, dom); });
    dom.zoomInput?.addEventListener('blur', () => _fullPreviewCommitZoom(state, dom));

    dom.pageInput?.addEventListener('keydown', (e) => { if (e.key === 'Enter') _fullPreviewCommitPage(state, dom); });
    dom.pageInput?.addEventListener('blur', () => _fullPreviewCommitPage(state, dom));

    dom.layoutButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const next = btn.getAttribute('data-preview-layout');
            if (next && next !== state.layout) {
                state.layout = next;
                _fullPreviewPersist(state);
                _fullPreviewRender(state, dom);
                requestAnimationFrame(() => _fullPreviewScrollToPage(state, dom, state.currentPage, false));
            }
        });
    });

    dom.scroller?.addEventListener('scroll', () => {
        window.clearTimeout(state.scrollTimer);
        state.scrollTimer = window.setTimeout(() => _fullPreviewSyncFromScroll(state, dom), 40);
    }, { passive: true });

    dom.scroller?.addEventListener('wheel', (e) => {
        if (e.ctrlKey || e.metaKey) {
            e.preventDefault();
            _fullPreviewSetZoom(state, dom, state.zoom + (e.deltaY < 0 ? FULL_PREVIEW_ZOOM_STEP : -FULL_PREVIEW_ZOOM_STEP));
        }
    }, { passive: false });

    window.addEventListener('resize', _fullPreviewDebounce(() => _fullPreviewFitMode(state, dom, 'width'), 160));

    _fullPreviewApplyChrome(state, dom);
}

async function loadPreviewManifest(template) {
    const dom = _fullPreviewDom();
    const state = currentTemplateState._previewViewer;
    if (!dom.panel || !state) return;

    const project = template.report_project || null;
    const selectedReport = getSelectedGeneratedReport(project);

    if (!project?.slug || !selectedReport?.file_name) {
        dom.file.textContent = '未选择报告';
        dom.title.textContent = 'Word 预览';
        dom.stage.innerHTML = '<div class="empty-state">在生成记录中选择报告后，预览将在此处显示。</div>';
        dom.rail.innerHTML = '';
        dom.pageTotal.textContent = '0';
        dom.panel.classList.remove('has-preview');
        if (dom.empty) dom.empty.style.display = '';
        return;
    }

    const manifestUrl = `/api/report-projects/${encodeURIComponent(project.slug)}/preview-manifest/${encodeURIComponent(selectedReport.file_name)}`;

    try {
        const response = await fetch(manifestUrl, { cache: 'no-store' });
        if (!response.ok) throw new Error('manifest http ' + response.status);
        const manifest = await response.json();

        state.manifest = manifest;
        state.pages = (Array.isArray(manifest.pages) ? manifest.pages : []).map((page, index) => ({
            pageNumber: index + 1,
            label: page.label || '第 ' + (index + 1) + ' 页',
            src: page.src || '',
            width: Number(page.width) || 1224,
            height: Number(page.height) || 1584,
        }));

        const first = state.pages[0];
        if (first) {
            document.documentElement.style.setProperty('--wpv-page-width', first.width + 'px');
            document.documentElement.style.setProperty('--wpv-page-height', first.height + 'px');
        }

        dom.title.textContent = manifest.title || 'Word 预览';
        dom.file.textContent = manifest.fileName || selectedReport.file_name;
        dom.pageTotal.textContent = String(state.pages.length);

        dom.panel.classList.add('has-preview');
        if (dom.empty) dom.empty.style.display = 'none';

        _fullPreviewRender(state, dom);
        _fullPreviewFitMode(state, dom, 'width');
        _fullPreviewUpdateCurrentPage(state, dom, 1);
        dom.panel.classList.add('has-preview');
        if (dom.empty) dom.empty.style.display = 'none';
    } catch (error) {
        console.error('[word-preview] failed to load manifest', error);
        dom.stage.innerHTML = '<div class="error-state">预览资源加载失败，请检查报告是否已生成。</div>';
        dom.file.textContent = '加载失败';
        dom.rail.innerHTML = '';
        dom.pageTotal.textContent = '0';
        dom.panel.classList.add('has-preview');
        if (dom.empty) dom.empty.style.display = 'none';
    }
}

function _fullPreviewRender(state, dom) {
    _fullPreviewApplyChrome(state, dom);
    _fullPreviewRenderThumbnails(state, dom);
    _fullPreviewRenderPages(state, dom);
    _fullPreviewSetupLazyLoad(state, dom);
    _fullPreviewUpdateCurrentPage(state, dom, state.currentPage);
}

function _fullPreviewRenderThumbnails(state, dom) {
    if (!dom.rail) return;
    dom.rail.textContent = '';
    state.pages.forEach(page => {
        const btn = document.createElement('button');
        btn.className = 'thumbnail-card';
        btn.type = 'button';
        btn.dataset.thumbnailPage = String(page.pageNumber);
        const img = document.createElement('img');
        img.src = page.src;
        img.alt = page.label;
        img.loading = 'lazy';
        const label = document.createElement('span');
        label.textContent = String(page.pageNumber);
        btn.append(img, label);
        btn.addEventListener('click', () => _fullPreviewScrollToPage(state, dom, page.pageNumber, true));
        dom.rail.append(btn);
    });
}

function _fullPreviewRenderPages(state, dom) {
    if (!dom.stage) return;
    dom.stage.textContent = '';
    if (!state.pages.length) {
        dom.stage.innerHTML = '<div class="empty-state">暂无预览页</div>';
        return;
    }
    _fullPreviewGetSpreads(state).forEach(spread => {
        const row = document.createElement('div');
        row.className = 'page-spread';
        row.dataset.spreadStart = String(spread[0].pageNumber);
        spread.forEach(page => {
            const figure = document.createElement('figure');
            figure.className = 'page-sheet is-loading';
            figure.dataset.pageNumber = String(page.pageNumber);
            figure.style.setProperty('--wpv-page-width', page.width + 'px');
            figure.style.setProperty('--wpv-page-height', page.height + 'px');
            const img = document.createElement('img');
            img.dataset.src = page.src;
            img.alt = page.label;
            img.decoding = 'async';
            img.addEventListener('load', () => figure.classList.remove('is-loading'));
            img.addEventListener('error', () => { figure.classList.remove('is-loading'); figure.classList.add('is-error'); });
            figure.append(img);
            row.append(figure);
        });
        dom.stage.append(row);
    });
}

function _fullPreviewGetSpreads(state) {
    if (state.layout === 'single') return state.pages.map(p => [p]);
    const spreads = [];
    for (let i = 0; i < state.pages.length; i += 2) spreads.push(state.pages.slice(i, i + 2));
    return spreads;
}

function _fullPreviewSetupLazyLoad(state, dom) {
    if (state.observer) { state.observer.disconnect(); state.observer = null; }
    const images = Array.from(dom.stage.querySelectorAll('img[data-src]'));
    if (!('IntersectionObserver' in window)) { images.forEach(_fullPreviewLoadImage); return; }
    state.observer = new IntersectionObserver(entries => {
        entries.forEach(entry => { if (entry.isIntersecting) { _fullPreviewLoadImage(entry.target); state.observer.unobserve(entry.target); } });
    }, { root: dom.scroller, rootMargin: '900px 0px' });
    images.forEach(img => state.observer.observe(img));
}

function _fullPreviewLoadImage(img) {
    if (img.dataset.src) { img.src = img.dataset.src; img.removeAttribute('data-src'); }
}

function _fullPreviewSetZoom(state, dom, next) {
    state.zoom = _fullPreviewClamp(next, FULL_PREVIEW_MIN_ZOOM, FULL_PREVIEW_MAX_ZOOM);
    if (dom.fitWidth) dom.fitWidth.classList.remove('is-active');
    if (dom.fitPage) dom.fitPage.classList.remove('is-active');
    _fullPreviewApplyZoom(state, dom);
    _fullPreviewPersist(state);
}

function _fullPreviewApplyZoom(state, dom) {
    document.documentElement.style.setProperty('--wpv-zoom', String(state.zoom));
    if (dom.zoomInput) dom.zoomInput.value = Math.round(state.zoom * 100) + '%';
}

function _fullPreviewFitMode(state, dom, mode) {
    if (!state.pages.length) return;
    const first = state.pages[0];
    const gap = state.layout === 'double' ? 24 : 0;
    const pageCount = state.layout === 'double' ? 2 : 1;
    const spreadWidth = first.width * pageCount + gap;
    const spreadHeight = first.height;
    const widthZoom = (dom.scroller.clientWidth - 90) / spreadWidth;
    const heightZoom = (dom.scroller.clientHeight - 86) / spreadHeight;
    state.zoom = _fullPreviewClamp(mode === 'page' ? Math.min(widthZoom, heightZoom) : widthZoom, FULL_PREVIEW_MIN_ZOOM, FULL_PREVIEW_MAX_ZOOM);
    if (dom.fitWidth) dom.fitWidth.classList.toggle('is-active', mode === 'width');
    if (dom.fitPage) dom.fitPage.classList.toggle('is-active', mode === 'page');
    _fullPreviewApplyZoom(state, dom);
    _fullPreviewPersist(state);
}

function _fullPreviewCommitZoom(state, dom) {
    const raw = String(dom.zoomInput?.value || '').replace(/[^0-9.]/g, '');
    const value = Number(raw);
    if (Number.isFinite(value) && value > 0) {
        _fullPreviewSetZoom(state, dom, value / 100);
    } else {
        _fullPreviewApplyZoom(state, dom);
    }
}

function _fullPreviewCommitPage(state, dom) {
    const value = parseInt(dom.pageInput?.value, 10);
    if (Number.isFinite(value)) {
        _fullPreviewScrollToPage(state, dom, value, true);
    } else if (dom.pageInput) {
        dom.pageInput.value = String(state.currentPage);
    }
}

function _fullPreviewScrollToPage(state, dom, pageNumber, smooth) {
    const next = _fullPreviewClamp(Math.round(pageNumber), 1, Math.max(state.pages.length, 1));
    const target = dom.stage?.querySelector('[data-page-number="' + next + '"]');
    if (target && dom.scroller) {
        dom.scroller.scrollTo({
            top: Math.max(0, target.offsetTop - 24),
            left: Math.max(0, target.offsetLeft - 42),
            behavior: smooth ? 'smooth' : 'auto',
        });
    }
    _fullPreviewUpdateCurrentPage(state, dom, next);
}

function _fullPreviewSyncFromScroll(state, dom) {
    const sheets = Array.from(dom.stage?.querySelectorAll('[data-page-number]') || []);
    if (!sheets.length) return;
    const scrollerRect = dom.scroller.getBoundingClientRect();
    const targetY = scrollerRect.top + scrollerRect.height * 0.38;
    let best = sheets[0], bestDist = Infinity;
    sheets.forEach(sheet => {
        const rect = sheet.getBoundingClientRect();
        const dist = Math.abs(rect.top - targetY);
        if (dist < bestDist) { bestDist = dist; best = sheet; }
    });
    _fullPreviewUpdateCurrentPage(state, dom, Number(best.dataset.pageNumber));
}

function _fullPreviewUpdateCurrentPage(state, dom, pageNumber) {
    state.currentPage = _fullPreviewClamp(Math.round(pageNumber), 1, Math.max(state.pages.length, 1));
    if (dom.pageInput) dom.pageInput.value = String(state.currentPage);
    const rangeEnd = state.layout === 'double'
        ? Math.min(state.currentPage + (state.currentPage % 2 === 1 ? 1 : 0), state.pages.length)
        : state.currentPage;
    const rangeStart = state.layout === 'double' && state.currentPage % 2 === 0
        ? state.currentPage - 1
        : state.currentPage;
    if (dom.pageRange) dom.pageRange.textContent = rangeStart === rangeEnd ? String(rangeStart) : rangeStart + '-' + rangeEnd;
    dom.rail?.querySelectorAll('.thumbnail-card').forEach(thumb => {
        thumb.classList.toggle('is-current', Number(thumb.dataset.thumbnailPage) === state.currentPage);
    });
}

function _fullPreviewApplyChrome(state, dom) {
    if (dom.body) dom.body.classList.toggle('thumbnails-hidden', !state.thumbnails);
    if (dom.thumbToggle) dom.thumbToggle.classList.toggle('is-active', state.thumbnails);
    dom.layoutButtons.forEach(btn => {
        btn.classList.toggle('is-active', btn.getAttribute('data-preview-layout') === state.layout);
    });
    _fullPreviewApplyZoom(state, dom);
}

function _fullPreviewDebounce(fn, wait) {
    let timer = 0;
    return function () { window.clearTimeout(timer); timer = window.setTimeout(fn, wait); };
}

function renderTemplateLogPanel(template) {
    const project = template.report_project || null;
    const latest = getLatestGeneratedReport(project);
    const table = document.getElementById('template-generation-log-table');
    const context = document.getElementById('template-generation-log-context');
    const status = document.getElementById('template-log-status');
    const runResult = currentTemplateState.lastReportGenerationResult;
    const runLog = currentTemplateState.lastReportRunLog;
    const runLogUrl = runResult?.run_log_url || getRunLogUrlForReport(project, latest);

    if (status) status.textContent = runLogUrl ? '最近一次生成' : '暂无日志';
    if (table) {
        const rows = buildTemplateLogRows(runResult, runLog, latest);
        table.innerHTML = rows.length ? rows.map(row => `
            <div class="template-generation-log-row ${esc(row.level || 'info')}">
                <span class="mono">${esc(row.time || '--')}</span>
                <em>${esc(row.level || 'INFO')}</em>
                <strong>${esc(row.scope || 'report')}</strong>
                <span>${esc(row.message || '')}</span>
                <small>${esc(row.duration || '')}</small>
            </div>
        `).join('') : '<div class="empty-state compact">生成报告后显示运行日志、警告和耗时。</div>';
    }
    if (context) {
        context.innerHTML = `
            <div class="template-log-context-list">
                <div><span>项目</span><strong>${esc(project?.name || '未选择')}</strong></div>
                <div><span>输出文件</span><strong>${esc(latest?.file_name || runResult?.file_name || '尚未生成')}</strong></div>
                <div><span>日志地址</span><strong>${esc(runLogUrl || '暂无')}</strong></div>
                <div><span>结果</span><strong>${esc(runResult?.success ? '成功' : (latest ? '已生成' : '等待生成'))}</strong></div>
            </div>
            <div class="template-log-actions">
                ${runLogUrl ? `<a class="btn-secondary" href="${esc(runLogUrl)}" target="_blank">打开 JSON 日志</a>` : ''}
                ${project?.slug ? `<button type="button" class="btn-primary" data-template-log-open-folder>打开所在文件夹</button>` : ''}
            </div>
        `;
        const folderBtn = context.querySelector('[data-template-log-open-folder]');
        if (folderBtn && project?.slug) {
            folderBtn.addEventListener('click', () => openReportProjectOutputFolder(project.slug));
        }
    }
}

function getLatestGeneratedReport(project) {
    return Array.isArray(project?.generated_reports) ? project.generated_reports[0] || null : null;
}

function getRunLogUrlForReport(project, report) {
    if (!project?.slug || !report?.file_name) return '';
    const match = String(report.file_name).match(/^(\d{4}-\d{2}-\d{2}_\d{6})/);
    if (!match) return '';
    return `/api/report-projects/${encodeURIComponent(project.slug)}/runs/${encodeURIComponent(match[1])}.json`;
}

function buildTemplateLogRows(runResult, runLog, latest) {
    const rows = [];
    if (runResult) {
        rows.push(['DONE', 'output.save', `保存 ${runResult.file_name || '输出文档'}`, 'ok']);
        if (runResult.generated_placeholder_count != null) {
            rows.push(['INFO', 'placeholder', `生成占位符 ${runResult.generated_placeholder_count}`, '']);
        }
        if (runResult.evidence_count != null) {
            rows.push(['INFO', 'evidence', `使用证据 ${runResult.evidence_count} 条`, '']);
        }
        (runResult.warnings || []).slice(0, 4).forEach(warning => {
            rows.push(['WARN', 'guard', warning, '']);
        });
    } else if (runLog?.generation?.sections?.length) {
        runLog.generation.sections.slice(0, 8).forEach(section => {
            rows.push([
                section.warnings?.length ? 'WARN' : 'INFO',
                section.placeholder || 'section',
                `${section.title || section.placeholder || '段落'} · evidence ${section.evidence_count || 0}`,
                section.tokens_used ? `${section.tokens_used} tokens` : ''
            ]);
        });
    } else if (latest) {
        rows.push(['DONE', 'output.save', `最近生成 ${latest.file_name}`, '']);
    }
    return rows.map((row, index) => ({
        time: index === 0 ? formatShortTime(runResult?.generated_at || latest?.generated_at) : '',
        level: row[0],
        scope: row[1],
        message: row[2],
        duration: row[3]
    }));
}

function formatShortTime(value) {
    if (!value) return '--';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return '--';
    return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
}

async function openReportProjectOutputFolder(slug, fileName = '') {
    if (!slug) {
        toast('报告项目未绑定，无法打开所在文件夹', 'error');
        return;
    }
    try {
        const query = fileName ? `?file_name=${encodeURIComponent(fileName)}` : '';
        await apiCall('POST', `/api/report-projects/${encodeURIComponent(slug)}/open-folder${query}`);
        toast('已打开报告所在文件夹', 'success');
    } catch (e) {
        if (String(e.message || '').includes('Not Found')) {
            toast('打开文件夹失败：当前后端还没加载新接口，请重启 AlphaFoundry', 'error');
            return;
        }
        toast('打开文件夹失败: ' + e.message, 'error');
    }
}

function renderReportGenerationProgressCard({ status = 'running', activeKey = 'check', message = '' } = {}) {
    const statusText = status === 'error' ? '生成失败' : '生成中';
    const detail = message || '正在准备生成报告';
    setGenerationFlowState(activeKey, statusText, detail);
    toggleFlowActions(false);
}

function renderReportGenerationFailure(error) {
    const message = error?.message || String(error || '未知错误');
    const hint = getReportGenerationErrorHint(message);
    const target = getReportGenerationErrorTarget(message);

    // 在活跃步骤上显示错误状态
    const activeStepEl = document.querySelector('[data-generation-flow-step].active');
    if (activeStepEl) {
        activeStepEl.classList.add('error');
        const emEl = activeStepEl.querySelector('em');
        if (emEl) emEl.textContent = '失败';
        const smallEl = activeStepEl.querySelector('small');
        if (smallEl) smallEl.textContent = hint;
    }

    // 更新进度标签
    const progressLabel = document.getElementById('template-generation-progress-label');
    if (progressLabel) progressLabel.textContent = '生成失败';

    // 显示流程操作按钮（只显示"打开高级配置"）
    toggleFlowActions(true, 'error', target);

    // 将"生成报告"按钮替换为"重试生成"
    const generateBtn = document.getElementById('btn-template-generate-report');
    if (generateBtn) {
        generateBtn.disabled = false;
        generateBtn.innerHTML = '<i class="codicon codicon-refresh"></i> 重试生成';
    }
}

function bindReportGenerationFlowActions(errorTarget) {
    const openConfigBtn = document.getElementById('btn-template-flow-open-config');

    if (openConfigBtn) {
        const newBtn = openConfigBtn.cloneNode(true);
        openConfigBtn.parentNode.replaceChild(newBtn, openConfigBtn);
        newBtn.addEventListener('click', () => {
            openAdvancedMaintenance(errorTarget || '');
        });
    }
}

function toggleFlowActions(visible, mode, errorTarget) {
    const container = document.getElementById('template-generation-flow-actions');
    if (!container) return;

    if (!visible) {
        container.classList.add('hidden');
        return;
    }

    // 只在出错时显示"打开高级配置"按钮；重试按钮已移到"生成报告"按钮位置
    container.classList.remove('hidden');
    if (mode === 'error') {
        bindReportGenerationFlowActions(errorTarget);
    }
}

function getReportGenerationErrorHint(message) {
    if (/No model provider|PROVIDER_PROFILES|model provider|api key|provider/i.test(message)) {
        return '模型接口不可用，先检查 PROVIDER_PROFILES、API Key 或模型供应商配置。';
    }
    if (/template|Word|docx|placeholder/i.test(message)) {
        return 'Word 模板或占位符可能不匹配，打开高级配置检查占位符映射。';
    }
    if (/Excel|workbook|sheet|range/i.test(message)) {
        return 'Excel 底稿或数据区域可能不可读，检查工作簿、Sheet 和数据范围。';
    }
    if (/section|yaml|config/i.test(message)) {
        return 'Section/YAML 配置可能有缺项或格式问题，打开高级配置检查当前片段。';
    }
    return '保留错误信息后重试；如果连续失败，优先检查接口、模板和数据文件。';
}

function getReportGenerationErrorTarget(message) {
    if (/template|Word|docx|placeholder/i.test(message)) return 'template-placeholder-map';
    if (/Excel|workbook|sheet|range/i.test(message)) return 'template-excel-mapping';
    if (/section|yaml|config|PROVIDER_PROFILES|model provider|api key|provider/i.test(message)) return 'template-common-rules';
    return 'template-advanced-maintenance';
}

function bindReportGenerationFeedbackActions() {
    const openConfigBtn = document.getElementById('btn-template-generation-open-config');
    const retryBtn = document.getElementById('btn-template-generation-retry');
    if (openConfigBtn && !openConfigBtn.dataset.bound) {
        openConfigBtn.dataset.bound = 'true';
        openConfigBtn.addEventListener('click', () => openAdvancedMaintenance(openConfigBtn.dataset.errorTarget));
    }
    if (retryBtn && !retryBtn.dataset.bound) {
        retryBtn.dataset.bound = 'true';
        retryBtn.addEventListener('click', () => {
            const generateBtn = document.getElementById('btn-template-generate-report');
            if (generateBtn && !generateBtn.disabled) generateBtn.click();
        });
    }
}

function openAdvancedMaintenance(targetId = '') {
    setStoredTemplateDetailMode('config');
    applyTemplateDetailMode('config');
    const panel = document.getElementById('template-advanced-maintenance');
    if (!panel) return;
    panel.open = true;
    const target = targetId ? document.getElementById(targetId) : null;
    highlightWorkbenchTarget(target || panel);
}

function openProjectCheckPanel(targetId = '') {
    const panel = document.getElementById('template-project-check-details');
    if (panel) panel.open = true;
    const target = targetId ? document.getElementById(targetId) : null;
    highlightWorkbenchTarget(target || panel);
}

function highlightWorkbenchTarget(element) {
    if (!element) return;
    element.scrollIntoView({ behavior: 'smooth', block: 'center' });
    element.classList.remove('template-focus-highlight');
    void element.offsetWidth;
    element.classList.add('template-focus-highlight');
    window.setTimeout(() => element.classList.remove('template-focus-highlight'), 1800);
}

function formatGeneratedAt(value) {
    if (!value) return '生成时间未知';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);
    return date.toLocaleString('zh-CN', { hour12: false });
}

function renderAdvancedMaintenance(template) {
    const project = template.report_project || null;
    const placeholders = getTemplateWorkbenchPlaceholders(template);
    const sections = getTemplateWorkbenchSections(template);
    const templateName = template.template_name || template.name || currentSelectedTemplate || '未命名模板';
    const placeholderNames = placeholders.length
        ? placeholders
        : sections.map(section => section.placeholder || section.key).filter(Boolean);
    const selectedName = normalizePlaceholderName(currentTemplateState.selectedPlaceholderName);
    const firstPlaceholder = normalizePlaceholderName(placeholderNames[0] || '');
    currentTemplateState.selectedPlaceholderName = placeholderNames
        .map(normalizePlaceholderName)
        .includes(selectedName)
            ? selectedName
            : firstPlaceholder;

    renderTemplateAssetChecklist(template, sections);
    renderTemplatePlaceholderMap(template, placeholders, sections);
    renderTemplateExcelMapping(template, templateName);
    renderCommonGenerationRules(template);
    renderSelectedPlaceholderDetail(template);

    const sourceEditor = document.getElementById('template-source-editor');
    if (sourceEditor) {
        const draftKey = `report-template-source:${project?.slug || templateName}:unified`;
        sourceEditor.dataset.draftKey = draftKey;
        sourceEditor.readOnly = true;
        sourceEditor.classList.add('readonly');
    }

    updateTemplateSourceSwitcher(template);
    renderSelectedSourceFragment(template);
    setTemplateSourceEditing(false);

    renderTemplateValidationPreview(template, sections, placeholders);
    bindTemplateWorkbenchActions();
}

function getTemplateWorkbenchSource(template) {
    const project = template.report_project || null;
    return {
        content: shouldUsePlaceholderMappingDraft(template)
            ? buildPlaceholderMappingConfigYaml(template)
            : (project?.report_config_source || buildPlaceholderMappingConfigYaml(template)),
        sourceKind: 'report_config',
        label: shouldUsePlaceholderMappingDraft(template)
            ? '统一报告配置（草稿）'
            : '统一报告配置'
    };
}

function shouldUsePlaceholderMappingDraft(template) {
    const placeholders = getTemplateWorkbenchPlaceholders(template);
    if (!placeholders.length) return false;
    const mappings = getStoredPlaceholderMappings(template);
    if (mappings.size === 0) return true;
    return placeholders.some(placeholder => !mappings.has(normalizePlaceholderName(placeholder)));
}

function updateTemplateSourceSwitcher(template) {
    const sectionBtn = document.getElementById('btn-template-source-section');
    const promptBtn = document.getElementById('btn-template-source-prompt');
    const reportCfgBtn = document.getElementById('btn-template-source-report-config');
    if (sectionBtn) {
        sectionBtn.classList.remove('hidden');
        sectionBtn.classList.add('active');
    }
    if (promptBtn) promptBtn.classList.add('hidden');
    if (reportCfgBtn) reportCfgBtn.classList.add('hidden');
}

function isSelectedFixedExcelPlaceholder(template) {
    const mapping = getSelectedPlaceholderMapping(template) || {};
    const type = String(mapping.type || '').toLowerCase();
    return type === 'excel_commodity_market_review';
}

function getCurrentWorkbenchTemplate() {
    const selectedName = currentSelectedTemplate || currentTemplateState.selectedTemplate;
    return (currentTemplateState.templates || []).find(template =>
        (template.template_name || template.name) === selectedName
        || template.report_project?.slug === currentTemplateState.selectedReportProject?.slug
    ) || null;
}

function getTemplateWorkbenchSections(template) {
    const project = template.report_project || null;
    const projectSections = project?.report_config?.sections;
    if (Array.isArray(projectSections) && projectSections.length) {
        return projectSections;
    }
    const placeholderSections = buildSectionsFromReportProject(project);
    if (placeholderSections.length) {
        return placeholderSections;
    }
    return template.sections || [];
}

function getTemplateWorkbenchPlaceholders(template) {
    const project = template.report_project || null;
    const pptPlaceholders = project?.ppt_placeholders;
    if (Array.isArray(pptPlaceholders) && pptPlaceholders.length) {
        return pptPlaceholders;
    }
    const projectPlaceholders = project?.word_placeholders;
    if (Array.isArray(projectPlaceholders) && projectPlaceholders.length) {
        return projectPlaceholders;
    }
    const configPlaceholders = buildPlaceholderNamesFromReportProject(project);
    if (configPlaceholders.length) {
        return configPlaceholders;
    }
    return template.placeholders || [];
}

function buildTemplateAssetChecks(template, sections) {
    const project = template.report_project || null;
    const isPptProject = project?.project_type === 'ppt';
    const templateFilename = project?.template_filename
        || (isPptProject ? project?.ppt_template_filename : project?.word_template_filename);
    return [
        {
            icon: 'codicon-file-code',
            label: isPptProject ? 'PPT 模板' : 'Word 模板',
            ok: Boolean(templateFilename || template.has_docx),
            value: templateFilename || (template.has_docx ? '已绑定' : '缺失'),
            action: 'upload',
            actionTarget: isPptProject ? 'project-ppt-template-input' : 'project-word-template-input',
            actionLabel: '上传模板'
        },
        {
            icon: 'codicon-table',
            label: 'Excel 底稿',
            ok: Boolean(project?.excel_workbook_filename || template.has_excel),
            value: project?.excel_workbook_filename || (template.has_excel ? '已绑定' : '待绑定'),
            action: 'upload',
            actionTarget: 'project-excel-workbook-input',
            actionLabel: '上传 Excel'
        },
        {
            icon: 'codicon-settings-gear',
            label: 'Section 配置',
            ok: Boolean(project?.report_config_filename || sections.length > 0),
            value: project?.report_config_filename || (sections.length ? `${sections.length} 段` : '待配置'),
            action: 'upload',
            actionTarget: 'project-report-config-input',
            actionLabel: '上传配置'
        }
    ];
}

function renderTemplateAssetChecklist(template, sections) {
    const statusEl = document.getElementById('template-asset-status');
    const checklist = document.getElementById('template-asset-checklist');
    if (!checklist) return;

    const assets = buildTemplateAssetChecks(template, sections);

    checklist.innerHTML = assets.map(asset => `
        <div class="asset-check-item ${asset.ok ? 'ok' : 'missing'}">
            <i class="codicon ${asset.icon}"></i>
            <span>${esc(asset.label)}</span>
            <strong>${esc(asset.value)}</strong>
            ${asset.ok ? '' : `
                <button type="button"
                        class="template-check-action"
                        data-template-check-action="${esc(asset.action)}"
                        data-template-check-target="${esc(asset.actionTarget)}">
                    ${esc(asset.actionLabel)}
                </button>
            `}
        </div>
    `).join('');

    const readyCount = assets.filter(asset => asset.ok).length;
    if (statusEl) {
        statusEl.textContent = `${readyCount}/${assets.length} 就绪`;
        statusEl.classList.toggle('warning', readyCount < assets.length);
    }
}

function renderTemplatePlaceholderMap(template, placeholders, sections) {
    const countEl = document.getElementById('template-placeholder-count');
    const container = document.getElementById('template-placeholder-map');
    if (!container) return;

    const names = placeholders.length
        ? placeholders
        : sections.map(section => section.placeholder || section.key).filter(Boolean);

    if (countEl) countEl.textContent = `${names.length} 个`;

    if (!names.length) {
        currentTemplateState.selectedPlaceholderName = '';
        container.innerHTML = '<div class="empty-state compact">当前配置里还没有占位符</div>';
        return;
    }

    const normalizedNames = names.map(name => normalizePlaceholderName(name)).filter(Boolean);
    const currentName = normalizePlaceholderName(currentTemplateState.selectedPlaceholderName);
    const selectedName = normalizedNames.includes(currentName)
        ? currentName
        : normalizedNames[0];
    currentTemplateState.selectedPlaceholderName = selectedName;
    const groups = [
        { readiness: 'needs_attention', label: '需要处理', names: [] },
        { readiness: 'ready', label: '已完成', names: [] }
    ];
    normalizedNames.forEach(normalizedName => {
        const mapping = getEffectivePlaceholderMapping(template, normalizedName);
        const lifecycle = getPlaceholderLifecycleStatus(template, mapping, normalizedName);
        const group = lifecycle.state === 'ready' ? groups[1] : groups[0];
        group.names.push(normalizedName);
    });

    container.innerHTML = `
        <div class="placeholder-picker" data-open="false">
            <button
                id="template-placeholder-select"
                class="placeholder-select placeholder-select-button"
                type="button"
                value="${esc(selectedName)}"
                data-value="${esc(selectedName)}"
                aria-label="当前段落"
                aria-haspopup="listbox"
                aria-expanded="false"
            >
                <span class="placeholder-select-text">${esc(selectedName)}</span>
            </button>
            <div class="placeholder-select-menu" role="listbox" hidden>
                ${groups.filter(group => group.names.length).map(group => `
                    <div
                        class="template-placeholder-map-group"
                        data-placeholder-readiness="${esc(group.readiness)}"
                        role="group"
                        aria-label="${esc(group.label)}"
                    >
                        <div class="template-placeholder-map-group-label">${esc(group.label)}</div>
                        ${group.names.map(normalizedName => `
                            <button
                                class="placeholder-select-option"
                                type="button"
                                role="option"
                                data-placeholder-name="${esc(normalizedName)}"
                                aria-selected="${normalizedName === selectedName ? 'true' : 'false'}"
                            >
                                ${esc(normalizedName)}
                            </button>
                        `).join('')}
                    </div>
                `).join('')}
            </div>
        </div>
    `;

    bindPlaceholderMapRows();
    const picker = document.getElementById('template-placeholder-select');
    if (picker) {
        setPlaceholderPickerValue(selectedName);
        if (window.requestAnimationFrame) {
            window.requestAnimationFrame(reconcilePlaceholderPickerAndDetail);
        }
        window.setTimeout(reconcilePlaceholderPickerAndDetail, 50);
    }
}

function renderMappingSummary(mapping, section) {
    const title = getPlaceholderKindLabel(mapping, section);
    const details = [];
    if (isParagraphPlaceholderType(mapping?.type || '', mapping || {})) details.push('生成规则已绑定');
    if (mapping?.source) details.push(getPlaceholderSourceSummary(mapping));
    if (mapping?.value) details.push('固定文案已填写');
    const detailText = details.length ? details.join(' / ') : '等待配置';
    return `
        <span class="mapping-summary-title">${esc(title)}</span>
        <small>${esc(detailText)}</small>
    `;
}

function getPlaceholderSourceSummary(mapping = {}, placeholderName = '') {
    const type = getCanonicalPlaceholderType(mapping.type, mapping) || inferPlaceholderType(placeholderName);
    if (type === 'paragraph') {
        const mode = getParagraphMode(mapping.type || type, mapping, placeholderName);
        if (isDataTemplateParagraphMode(mapping.type || type, mode) && usesEvidenceParagraphMode(mapping.type || type, mode)) return 'Excel + Prompt';
        if (isDataTemplateParagraphMode(mapping.type || type, mode)) return 'Excel 数据模板';
        return mapping.prompt_template ? `Prompt：${mapping.prompt_template}` : 'Prompt / 证据';
    }
    if (type === 'field') {
        const sourceKind = getPlaceholderSourceKind(mapping.type || type, mapping, placeholderName);
        if (sourceKind === 'report_period') return '报告周期';
        if (sourceKind === 'excel_cell' || sourceKind === 'excel_range') return 'Excel 数据';
        return '手动值';
    }
    if (type === 'static_text') return mapping.value ? '已填写文案' : '待填写文案';
    if (type === 'table') return mapping.source?.kind || '表格来源';
    if (type === 'chart') return mapping.source?.kind || '图表来源';
    return '待配置';
}

function getPlaceholderConfigStatus(mapping = {}, placeholderName = '') {
    const type = getCanonicalPlaceholderType(mapping.type, mapping) || inferPlaceholderType(placeholderName);
    if (type === 'paragraph') {
        const mode = getParagraphMode(mapping.type || type, mapping, placeholderName);
        if (usesEvidenceParagraphMode(mapping.type || type, mode)) {
            return { ok: Boolean(mapping.prompt_template || mapping.prompt_retrieval_query), label: mapping.prompt_template || mapping.prompt_retrieval_query ? '已配置' : '待配置 Prompt' };
        }
        return { ok: Boolean(getDataTemplateComponent(mapping).template), label: getDataTemplateComponent(mapping).template ? '已配置' : '待配置模板' };
    }
    if (type === 'field') {
        const sourceKind = getPlaceholderSourceKind(mapping.type || type, mapping, placeholderName);
        if (sourceKind === 'report_period') return { ok: true, label: '已配置' };
        if (sourceKind === 'excel_cell' || sourceKind === 'excel_range') return { ok: Boolean(mapping.source), label: mapping.source ? '已配置' : '待配置来源' };
        return { ok: mapping.value !== undefined && mapping.value !== '', label: mapping.value ? '已配置' : '待填写' };
    }
    if (type === 'static_text') return { ok: Boolean(mapping.value), label: mapping.value ? '已配置' : '待填写' };
    if (type === 'table' || type === 'chart') return { ok: Boolean(mapping.source?.kind), label: mapping.source?.kind ? '已配置' : '待配置来源' };
    return { ok: false, label: '待配置' };
}

function getPlaceholderLifecycleStatus(template, mapping, placeholderName) {
    const issue = getPlaceholderReadinessIssue(mapping, placeholderName);
    if (issue) {
        return {
            state: 'missing',
            label: '缺配置',
            detail: issue.message,
            ok: false
        };
    }
    if (!isPlaceholderConfirmed(template, mapping, placeholderName)) {
        return {
            state: 'confirm',
            label: '需确认',
            detail: '系统已自动推断用途和来源，请确认后保存',
            ok: false
        };
    }
    return {
        state: 'ready',
        label: '可生成',
        detail: '配置完整',
        ok: true
    };
}

function isPlaceholderConfirmed(template, mapping = {}, placeholderName = '') {
    if (mapping.confirmed === true || mapping.confirmed === 'true') return true;
    const storedMappings = getStoredPlaceholderMappings(template);
    return storedMappings.has(normalizePlaceholderName(placeholderName));
}

function getTemplateWorkbenchPlaceholderNames(template) {
    const placeholders = getTemplateWorkbenchPlaceholders(template);
    const sections = getTemplateWorkbenchSections(template);
    return (placeholders.length
        ? placeholders
        : sections.map(section => section.placeholder || section.key).filter(Boolean)
    ).map(name => normalizePlaceholderName(name)).filter(Boolean);
}

function buildPlaceholderWizardState(template) {
    const names = getTemplateWorkbenchPlaceholderNames(template);
    const items = names.map(name => {
        const mapping = getEffectivePlaceholderMapping(template, name);
        const status = getPlaceholderLifecycleStatus(template, mapping, name);
        return { name, mapping, status };
    });
    const selectedName = normalizePlaceholderName(currentTemplateState.selectedPlaceholderName);
    const currentIndex = Math.max(0, items.findIndex(item => item.name === selectedName));
    const completedCount = items.filter(item => item.status.state === 'ready').length;
    const incompleteItems = items.filter(item => item.status.state !== 'ready');
    return {
        names,
        items,
        currentIndex,
        selectedName,
        completedCount,
        totalCount: items.length,
        incompleteItems
    };
}

function renderPlaceholderWizardControls(template) {
    const progressEl = document.getElementById('template-placeholder-wizard-progress');
    const progressBar = document.getElementById('template-placeholder-progress-bar');
    const prevBtn = document.getElementById('btn-template-prev-placeholder');
    const nextIncompleteBtn = document.getElementById('btn-template-next-incomplete-placeholder');
    const reviewPreflightBtn = document.getElementById('btn-template-review-preflight');
    const saveNextBtn = document.getElementById('btn-template-save-next-placeholder');
    const actionsEl = saveNextBtn?.closest('.template-placeholder-actions');
    const statusStripEl = document.querySelector('.template-placeholder-status-strip');
    if (!template) return;
    const state = buildPlaceholderWizardState(template);
    const hasIncomplete = state.incompleteItems.length > 0;
    const isComplete = state.totalCount > 0 && !hasIncomplete;
    if (progressEl) {
        progressEl.textContent = !state.totalCount
            ? '暂无待配置段落'
            : hasIncomplete
                ? `${state.completedCount} / ${state.totalCount} 已完成，还差 ${state.incompleteItems.length} 项`
                : `${state.completedCount} / ${state.totalCount} 已完成 · 全部段落已配置，可查看生成前检查`;
    }
    if (progressBar) {
        const percent = state.totalCount ? Math.round((state.completedCount / state.totalCount) * 100) : 0;
        progressBar.style.width = `${percent}%`;
    }
    if (actionsEl) {
        actionsEl.classList.toggle('has-incomplete', hasIncomplete);
        actionsEl.classList.toggle('is-complete', isComplete);
    }
    if (statusStripEl) {
        statusStripEl.classList.toggle('has-incomplete', hasIncomplete);
        statusStripEl.classList.toggle('is-complete', isComplete);
    }
    if (prevBtn) prevBtn.disabled = state.totalCount <= 1;
    if (nextIncompleteBtn) {
        nextIncompleteBtn.disabled = !hasIncomplete;
        nextIncompleteBtn.hidden = !hasIncomplete;
    }
    if (reviewPreflightBtn) {
        reviewPreflightBtn.hidden = !isComplete;
        reviewPreflightBtn.disabled = !isComplete;
    }
    if (saveNextBtn) {
        saveNextBtn.disabled = !state.totalCount || !hasIncomplete;
        saveNextBtn.hidden = !hasIncomplete;
    }
}

function selectAdjacentTemplatePlaceholder(direction, incompleteOnly = false) {
    const template = getCurrentWorkbenchTemplate();
    if (!template) return;
    const state = buildPlaceholderWizardState(template);
    if (!state.items.length) return;
    const pool = incompleteOnly ? state.incompleteItems : state.items;
    if (!pool.length) return;
    const currentName = normalizePlaceholderName(currentTemplateState.selectedPlaceholderName);
    const currentPoolIndex = pool.findIndex(item => item.name === currentName);
    const baseIndex = currentPoolIndex >= 0 ? currentPoolIndex : 0;
    const nextIndex = (baseIndex + direction + pool.length) % pool.length;
    selectTemplatePlaceholder(pool[nextIndex].name);
}

function selectFirstActionablePlaceholder(template) {
    const state = buildPlaceholderWizardState(template);
    const firstActionable = state.incompleteItems[0] || state.items[0];
    if (firstActionable) selectTemplatePlaceholder(firstActionable.name);
}

function markSelectedPlaceholderConfirmed(template) {
    const result = collectSelectedPlaceholderDraft(template);
    if (!result) return null;
    result.draft.confirmed = true;
    currentTemplateState.placeholderMappingDrafts[result.name] = result.draft;
    return result;
}

function getPlaceholderKindLabel(mapping, section) {
    const type = getCanonicalPlaceholderType(mapping?.type || section?.type || '', mapping || {});
    if (type === 'excel_commodity_market_review') return 'Excel 固定市场回顾';
    if (isParagraphPlaceholderType(type, mapping || {})) return '正文段落';
    if (type === 'field') return '短字段';
    if (type === 'static_text' || mapping?.value) return '固定文案';
    if (type === 'table') return '表格';
    if (type === 'chart') return '图表 / 图片';
    return '配置项';
}

function getCanonicalPlaceholderType(type = '', mapping = {}) {
    const normalized = String(type || '').trim();
    if (normalized) {
        if (['prompt', 'ai_text', 'composite_market_review'].includes(normalized)) return 'paragraph';
        if (['report_period', 'excel_cell', 'excel_range'].includes(normalized)) return 'field';
        if (normalized === 'config_text') return 'static_text';
        if (normalized === 'excel_chart') return 'chart';
        return normalized;
    }
    if (isParagraphMode(mapping?.mode)) return 'paragraph';
    return '';
}

function isParagraphMode(mode = '') {
    return [
        'data_template',
        'evidence_ai',
        'data_template_plus_evidence_ai',
        'data_ai',
        'rewrite'
    ].includes(String(mode || '').trim());
}

function getParagraphMode(type = '', mapping = {}, placeholderName = '') {
    const canonicalType = getCanonicalPlaceholderType(type, mapping);
    if (canonicalType !== 'paragraph') return '';
    if (isParagraphMode(mapping?.mode)) return mapping.mode;
    const normalized = String(type || '').trim();
    if (normalized === 'composite_market_review') return 'data_template_plus_evidence_ai';
    if (normalized === 'prompt' || normalized === 'ai_text') return 'evidence_ai';
    const hasDataTemplate = Boolean(getDataTemplateComponent(mapping).template)
        || Object.keys(getDataTemplateFields(mapping, { includeDefaults: false }) || {}).length > 0;
    const hasLlmWriting = Boolean(getLlmWritingComponent(mapping).writing_structure)
        || Boolean(getLlmWritingComponent(mapping).retrieval)
        || Boolean(mapping.prompt_template)
        || Boolean(mapping.retrieval);
    if (hasDataTemplate && hasLlmWriting) return 'data_template_plus_evidence_ai';
    if (hasDataTemplate) return 'data_template';
    if (/[\u4e00-\u9fff]/.test(normalizePlaceholderName(placeholderName))) return 'evidence_ai';
    return 'evidence_ai';
}

function getParagraphModeLabel(mode = '') {
    const labels = {
        data_template: '数据说明段落',
        evidence_ai: '根据材料撰写',
        data_template_plus_evidence_ai: '数据说明 + 材料续写',
        data_ai: '数据解读',
        rewrite: '草稿改写'
    };
    return labels[mode] || '根据材料撰写';
}

function isParagraphPlaceholderType(type = '', mapping = {}) {
    return getCanonicalPlaceholderType(type, mapping) === 'paragraph';
}

function isDataTemplateParagraphMode(type = '', mode = '') {
    const normalizedType = String(type || '').trim();
    const paragraphMode = isParagraphMode(mode) ? mode : getParagraphMode(normalizedType, { mode });
    return normalizedType === 'composite_market_review'
        || ['data_template', 'data_template_plus_evidence_ai'].includes(paragraphMode);
}

function usesEvidenceParagraphMode(type = '', mode = '') {
    const normalizedType = String(type || '').trim();
    const paragraphMode = isParagraphMode(mode) ? mode : getParagraphMode(normalizedType, { mode });
    return ['prompt', 'ai_text', 'composite_market_review'].includes(normalizedType)
        || ['evidence_ai', 'data_template_plus_evidence_ai', 'data_ai', 'rewrite'].includes(paragraphMode);
}

function shouldStoreParagraphRetrievalInLlmComponent(type = '', mode = '') {
    const paragraphMode = isParagraphMode(mode) ? mode : getParagraphMode(type, { mode });
    return String(type || '').trim() === 'composite_market_review'
        || paragraphMode === 'data_template_plus_evidence_ai';
}

function getPlaceholderSourceKind(type = '', mapping = {}, placeholderName = '') {
    const source = mapping?.source && typeof mapping.source === 'object' ? mapping.source : {};
    if (source.kind) return String(source.kind);
    const normalizedType = String(type || '').trim();
    if (normalizedType === 'report_period' || isSystemDatePlaceholder(placeholderName)) return 'report_period';
    if (normalizedType === 'excel_range') return 'excel_range';
    if (normalizedType === 'excel_cell' || mapping?.source) return 'excel_cell';
    return mapping?.value ? 'manual' : '';
}

function isReportPeriodFieldPlaceholder(type = '', mapping = {}, placeholderName = '') {
    return getCanonicalPlaceholderType(type, mapping) === 'field'
        && getPlaceholderSourceKind(type, mapping, placeholderName) === 'report_period';
}

function isExcelFieldPlaceholder(type = '', mapping = {}, placeholderName = '') {
    return getCanonicalPlaceholderType(type, mapping) === 'field'
        && ['excel_cell', 'excel_range'].includes(getPlaceholderSourceKind(type, mapping, placeholderName));
}

function getStoredCommonDefaults(template) {
    const project = template?.report_project;
    const defaults = project?.report_config?.defaults;
    const base = {
        generation_mode: 'evidence_grounded_generation',
        evidence_policy: 'strict',
        query_mode: usesEmbeddedPromptQueries(project) ? 'retrieval_query_embedded' : 'query_source',
        validators: {
            require_evidence_from_uploaded_material: true,
            forbid_external_facts: true,
            forbid_direct_investment_advice: true,
            forbidden_terms: ['保本', '稳赚', '收益保证', '明确买入', '目标价']
        },
        generation_constraints: [
            '严格依据上传材料、Excel 数据和 evidence，不添加外部知识或虚构数据',
            '不得使用 Wind 数据',
            '不得使用日度数据；如需描述市场表现，应使用周度或区间汇总数据',
            '使用数据或数值时必须说明来源；如数据来自已上传 Excel，可直接用于正文',
            '生成一段正文，不输出换行符',
            '不得输出标题、编号、项目符号或解释过程',
            '不得输出直接投资建议、收益承诺、目标价或买卖指令',
            '禁止出现这些词语：保本、稳赚、收益保证、明确买入、目标价',
            '禁止出现这些短语：根据文件、据报道、数据显示',
            '禁止提及与本段无关的指数名称、公司名称、证券机构、个股名称、ETF 名称',
            '如写作参数、固定模板或 Excel 数据明确要求引用指数名称，可以用于客观描述，不得展开投资评价',
            '如因说明数据出处必须引用机构名称，只能作为来源出现，不得展开评价',
            '可基于事实做一句审慎趋势判断，但必须直接由前文事实或数据支撑'
        ],
        hard_constraints: {
            no_wind_data: true,
            no_baidu_data: true,
            require_number_source: true,
            single_paragraph: true,
            forbidden_phrases: ['根据文件', '据报道', '数据显示'],
            forbidden_entity_categories: ['指数名称', '公司名称', '证券机构'],
            prompt_text: [
                '仅基于上传素材、Excel 数据和检索证据撰写，不使用 Wind 数据、百度数据或外部事实补充。',
                '涉及数字时必须说明来源，避免使用“根据文件”“据报道”“数据显示”等模板化表述。',
                '不要输出指数名称、公司名称、证券机构等实体清单式堆砌，不输出投资收益保证或直接买卖建议。',
                '除模板特别要求外，只输出一段正式周报正文，不换行。'
            ].join('\n')
        },
        retrieval: {
            mode: 'hybrid',
            top_k: 10,
            candidate_k: 40,
            semantic_candidate_k: 80,
            keyword_weight: 0.6,
            semantic_weight: 0.4,
            embedding_model: 'BAAI/bge-large-zh-v1.5',
            source_types: []
        },
        report_period: {
            report_date: getDefaultReportDate(),
            start_date: getDefaultEvidenceStartDate(),
            end_date: getDefaultReportDate()
        },
        rerank: {
            enabled: true,
            provider: 'bge-reranker',
            model: 'BAAI/bge-reranker-large',
            top_n: 30,
            min_score: 0.35
        }
    };
    if (!defaults || typeof defaults !== 'object') return base;
    return {
        ...base,
        ...defaults,
        validators: { ...base.validators, ...(defaults.validators || {}) },
        generation_constraints: Array.isArray(defaults.generation_constraints)
            ? defaults.generation_constraints
            : base.generation_constraints,
        hard_constraints: { ...base.hard_constraints, ...(defaults.hard_constraints || {}) },
        retrieval: { ...base.retrieval, ...(defaults.retrieval || {}) },
        report_period: { ...base.report_period, ...(defaults.report_period || {}) },
        rerank: { ...base.rerank, ...(defaults.rerank || {}) }
    };
}

function getEditableCommonDefaults(template) {
    return currentTemplateState.commonDefaultsDraft || getStoredCommonDefaults(template);
}

function renderCommonGenerationRules(template) {
    const container = document.getElementById('template-common-rules');
    if (!container) return;
    snapshotCommonRuleOpenState(container);

    const defaults = getEditableCommonDefaults(template);
    const retrieval = defaults.retrieval || {};
    const reportPeriod = defaults.report_period || {};
    const rerank = defaults.rerank || {};
    const generationConstraints = Array.isArray(defaults.generation_constraints)
        ? defaults.generation_constraints.join('\n')
        : '';

    container.innerHTML = `
        <div class="panel-title-row template-config-rail-header">
            <div>
                <h4>配置导航</h4>
            </div>
            <div class="template-common-title-actions">
                <button id="btn-template-save-common-rules" class="btn-secondary" type="button">
                    <i class="codicon codicon-save"></i> 保存共用参数
                </button>
            </div>
        </div>
        <details class="template-common-rule-card template-common-summary-card" data-common-section="generation_constraints" ${isCommonRuleSectionOpen('generation_constraints', true) ? 'open' : ''}>
            <summary>
                <span class="template-common-summary-title">
                    <strong>共用 Prompt 约束</strong>
                </span>
                <span class="template-common-summary-meta">
                    已保存
                </span>
            </summary>
            <div class="template-common-rule-editor">
                <textarea class="template-common-field wide" data-common-rule-field="generation_constraints" rows="12">${esc(generationConstraints)}</textarea>
            </div>
        </details>
        <div id="template-common-evidence-rules"></div>
        <div id="template-common-retrieval-rules"></div>
    `;

    renderCommonEvidenceRules(reportPeriod, retrieval);
    renderAdvancedCommonRules(template, retrieval, rerank);

    bindCommonRuleInputs(template);
}

function renderCommonEvidenceRules(reportPeriod = {}, retrieval = {}) {
    const container = document.getElementById('template-common-evidence-rules');
    if (!container) return;
    const sourceTypes = Array.isArray(retrieval.source_types) ? retrieval.source_types : [];
    const reportDate = reportPeriod.report_date || getDefaultReportDate();
    const startDate = reportPeriod.start_date || getDefaultEvidenceStartDate(reportDate);
    const endDate = reportPeriod.end_date || reportDate;
    container.innerHTML = `
        <details class="template-common-rule-card template-common-summary-card" data-common-section="evidence_scope" ${isCommonRuleSectionOpen('evidence_scope') ? 'open' : ''}>
            <summary>
                <span class="template-common-summary-title">
                    <strong>证据来源与时间</strong>
                </span>
                <span class="template-common-summary-meta">
                    有效
                </span>
            </summary>
            <div class="template-common-rule-editor">
                <div class="template-common-rules-grid template-retrieval-rules-grid">
                    <label class="template-common-field">
                        <span>报告日期</span>
                        <input type="date" data-common-rule-field="report_period.report_date" value="${esc(reportDate)}">
                    </label>
                    <label class="template-common-field">
                        <span>数据使用范围</span>
                        <div class="template-date-range-grid">
                            <input type="date" aria-label="数据开始日期" data-common-rule-field="report_period.start_date" value="${esc(startDate)}">
                            <input type="date" aria-label="数据结束日期" data-common-rule-field="report_period.end_date" value="${esc(endDate)}">
                        </div>
                    </label>
                    <label class="template-common-field wide">
                        <span>数据源使用筛选</span>
                        <div class="template-source-type-grid">
                            ${renderSourceTypeCheckboxes(sourceTypes)}
                        </div>
                    </label>
                </div>
            </div>
        </details>
    `;
}

function formatEvidenceScopeSummary(reportPeriod = {}, retrieval = {}) {
    const reportDate = reportPeriod.report_date || getDefaultReportDate();
    const startDate = reportPeriod.start_date || getDefaultEvidenceStartDate(reportDate);
    const endDate = reportPeriod.end_date || reportDate;
    const sourceTypes = Array.isArray(retrieval.source_types) && retrieval.source_types.length
        ? retrieval.source_types.join('、')
        : '全部来源';
    return `${startDate} 至 ${endDate} · ${sourceTypes}`;
}

function renderSourceTypeCheckboxes(selectedSourceTypes = []) {
    const selected = new Set(selectedSourceTypes);
    const allSelected = selected.size === 0;
    const options = [
        { value: '', label: '全部' },
        { value: 'cls', label: '财联社' },
        { value: 'cnstock', label: '中证网' },
        { value: 'zq', label: '券商研报' },
        { value: 'canonical_event', label: '结构化事件' }
    ];
    return options.map(option => `
        <label class="template-source-type-option">
            <input type="checkbox"
                   data-common-source-type="${esc(option.value || '__all__')}"
                   value="${esc(option.value)}"
                   ${option.value ? (selected.has(option.value) ? 'checked' : '') : (allSelected ? 'checked' : '')}>
            <span>${esc(option.label)}</span>
        </label>
    `).join('');
}

function getDefaultReportDate() {
    const now = new Date();
    const timezoneOffset = now.getTimezoneOffset() * 60000;
    return new Date(now.getTime() - timezoneOffset).toISOString().slice(0, 10);
}

function getDefaultEvidenceStartDate(reportDate = getDefaultReportDate(), lookbackDays = 7) {
    const end = parseDateInput(reportDate) || parseDateInput(getDefaultReportDate());
    if (!end) return '';
    const start = new Date(end);
    start.setDate(start.getDate() - Math.max(1, Number(lookbackDays) || 7) + 1);
    return formatDateInput(start);
}

function parseDateInput(value) {
    if (!value) return null;
    const date = new Date(`${value}T00:00:00`);
    return Number.isNaN(date.getTime()) ? null : date;
}

function formatDateInput(date) {
    const timezoneOffset = date.getTimezoneOffset() * 60000;
    return new Date(date.getTime() - timezoneOffset).toISOString().slice(0, 10);
}

function renderAdvancedCommonRules(template, retrieval = {}, rerank = {}) {
    const container = document.getElementById('template-common-retrieval-rules');
    if (!container) return;

    const candidateK = retrieval.candidate_k ?? retrieval.keyword_candidates ?? 40;
    const semanticCandidateK = retrieval.semantic_candidate_k ?? retrieval.semantic_candidates ?? 80;
    const rerankTopN = rerank.top_n ?? rerank.candidates ?? 30;
    const rerankMinScore = rerank.min_score ?? 0.35;
    const keywordWeightPercent = formatRulePercent(retrieval.keyword_weight ?? 0.6);
    const semanticWeightPercent = formatRulePercent(retrieval.semantic_weight ?? 0.4);

    container.innerHTML = `
        <details class="template-common-rule-card template-common-summary-card" data-common-section="retrieval" ${isCommonRuleSectionOpen('retrieval') ? 'open' : ''}>
            <summary>
                <span class="template-common-summary-title">
                    <strong>检索策略</strong>
                </span>
                <span class="template-common-summary-meta">
                    ${keywordWeightPercent}/${semanticWeightPercent}
                </span>
            </summary>
            <div class="template-common-rule-editor">
                <div class="template-common-rules-grid template-retrieval-rules-grid">
                    <label class="template-common-field">
                        <span>模式</span>
                        <select data-common-rule-field="retrieval.mode">
                            ${['hybrid', 'keyword', 'semantic'].map(option => `
                                <option value="${option}" ${(retrieval.mode || 'hybrid') === option ? 'selected' : ''}>${option}</option>
                            `).join('')}
                        </select>
                    </label>
                    <label class="template-common-field">
                        <span>Top K</span>
                        <input type="number" min="1" step="1" data-common-rule-field="retrieval.top_k" value="${esc(retrieval.top_k ?? 10)}">
                    </label>
                    <label class="template-common-field">
                        <span>候选数</span>
                        <input type="number" min="1" step="1" data-common-rule-field="retrieval.candidate_k" value="${esc(candidateK)}">
                    </label>
                    <label class="template-common-field">
                        <span>语义候选数</span>
                        <input type="number" min="1" step="1" data-common-rule-field="retrieval.semantic_candidate_k" value="${esc(semanticCandidateK)}">
                    </label>
                    <label class="template-common-field">
                        <span>关键词权重</span>
                        <input type="number" min="0" max="1" step="0.1" data-common-rule-field="retrieval.keyword_weight" value="${esc(retrieval.keyword_weight ?? 0.6)}">
                    </label>
                    <label class="template-common-field">
                        <span>语义权重</span>
                        <input type="number" min="0" max="1" step="0.1" data-common-rule-field="retrieval.semantic_weight" value="${esc(retrieval.semantic_weight ?? 0.4)}">
                    </label>
                    <label class="template-common-field">
                        <span>Embedding 模型</span>
                        <input type="text" data-common-rule-field="retrieval.embedding_model" value="${esc(retrieval.embedding_model || 'BAAI/bge-large-zh-v1.5')}">
                    </label>
                </div>
            </div>
        </details>
        <details class="template-common-rule-card template-common-summary-card" data-common-section="rerank" ${isCommonRuleSectionOpen('rerank') ? 'open' : ''}>
            <summary>
                <span class="template-common-summary-title">
                    <strong>证据重排</strong>
                </span>
                <span class="template-common-summary-meta">
                    ${rerank.enabled !== false ? '启用' : '关闭'}
                </span>
            </summary>
            <div class="template-common-rule-editor">
                <div class="template-rerank-editor">
                    <label class="template-common-rules-check template-rerank-toggle">
                        <input type="checkbox" data-common-rule-field="rerank.enabled" ${rerank.enabled !== false ? 'checked' : ''}>
                        <span>
                            <strong>启用证据重排</strong>
                            <small>先召回候选证据，再用本地 reranker 按相关性排序</small>
                        </span>
                    </label>
                    <label class="template-common-field">
                        <span>重排 Provider</span>
                        <input type="text" data-common-rule-field="rerank.provider" value="${esc(rerank.provider || 'bge-reranker')}">
                    </label>
                    <label class="template-common-field">
                        <span>Reranker 模型</span>
                        <input type="text" data-common-rule-field="rerank.model" value="${esc(rerank.model || 'BAAI/bge-reranker-large')}">
                    </label>
                    <label class="template-common-field">
                        <span>参与重排的候选证据数</span>
                        <input type="number" min="1" step="1" data-common-rule-field="rerank.top_n" value="${esc(rerankTopN)}">
                    </label>
                    <label class="template-common-field">
                        <span>最低相关分</span>
                        <input type="number" min="0" max="1" step="0.05" data-common-rule-field="rerank.min_score" value="${esc(rerankMinScore)}">
                    </label>
                </div>
            </div>
        </details>
    `;
}

function bindCommonRuleInputs(template) {
    document.querySelectorAll('#template-common-rules details[data-common-section]').forEach(details => {
        if (details.dataset.boundCommonOpenState) return;
        details.dataset.boundCommonOpenState = 'true';
        const summary = details.querySelector('summary');
        if (summary) {
            summary.addEventListener('click', event => {
                event.preventDefault();
                selectCommonRuleSection(details);
                openCommonRuleEditorModal(details.dataset.commonSection || '');
            });
        }
        details.addEventListener('toggle', () => {
            if (details.open) {
                document.querySelectorAll('#template-common-rules details[data-common-section]').forEach(other => {
                    if (other !== details) other.open = false;
                });
            }
            window.requestAnimationFrame(() => {
                const openDetails = document.querySelector('#template-common-rules details[data-common-section][open]');
                if (!openDetails) {
                    details.open = true;
                    return;
                }
                currentTemplateState.commonRuleOpenState = {};
                document.querySelectorAll('#template-common-rules details[data-common-section]').forEach(item => {
                    currentTemplateState.commonRuleOpenState[item.dataset.commonSection] = item.open;
                });
            });
        });
    });

    document.querySelectorAll('#template-common-rules [data-common-rule-field], #template-config-editor-modal-body [data-common-rule-field]').forEach(input => {
        if (input.dataset.boundCommonRule) return;
        input.dataset.boundCommonRule = 'true';
        const update = () => {
            if (input.dataset.commonRuleField === 'report_period.report_date') {
                syncEvidenceRangeFromReportDate(input.value);
            }
            collectCommonDefaultsDraft(template);
            refreshCommonConfigSurfaces(template);
            renderSelectedSourceFragment(template);
        };
        input.addEventListener('input', update);
        input.addEventListener('change', update);
    });
    document.querySelectorAll('#template-common-rules [data-common-source-type], #template-config-editor-modal-body [data-common-source-type]').forEach(input => {
        if (input.dataset.boundCommonSourceType) return;
        input.dataset.boundCommonSourceType = 'true';
        input.addEventListener('change', () => {
            syncSourceTypeCheckboxes(input);
            collectCommonDefaultsDraft(template);
            refreshCommonConfigSurfaces(template);
            renderSelectedSourceFragment(template);
        });
    });
    const saveCommonRulesBtn = document.getElementById('btn-template-save-common-rules');
    if (saveCommonRulesBtn && !saveCommonRulesBtn.dataset.bound) {
        saveCommonRulesBtn.dataset.bound = 'true';
        saveCommonRulesBtn.addEventListener('click', () => saveCurrentSectionConfig({
            button: saveCommonRulesBtn,
            savingHtml: '<i class="codicon codicon-loading spin"></i> 保存中...',
            successMessage: '共用参数已保存',
            localMessage: '共用参数草稿已保存到本地',
            errorPrefix: '保存共用参数失败'
        }));
    }
}

function refreshCommonConfigSurfaces(template = getCurrentWorkbenchTemplate()) {
    if (!template) return;
    refreshGenerationHeroMeta(template);

    const defaults = getEditableCommonDefaults(template);
    const reportPeriod = defaults.report_period || {};
    const retrieval = defaults.retrieval || {};
    const evidenceSummaryEl = document.querySelector(
        '#template-common-rules [data-common-section="evidence_scope"] .template-common-summary-title small'
    );
    if (evidenceSummaryEl) {
        evidenceSummaryEl.textContent = formatEvidenceScopeSummary(reportPeriod, retrieval);
    }

    renderSelectedPlaceholderDetail(template);
}

function setCommonRuleEditingSection(section = '') {
    document.querySelectorAll('#template-common-rules details[data-common-section]').forEach(item => {
        item.classList.toggle('is-editing', Boolean(section) && item.dataset.commonSection === section);
    });
}

function selectCommonRuleSection(details) {
    if (!details) return;
    document.querySelectorAll('#template-common-rules details[data-common-section]').forEach(other => {
        other.open = other === details;
        currentTemplateState.commonRuleOpenState = {
            ...(currentTemplateState.commonRuleOpenState || {}),
            [other.dataset.commonSection]: other === details
        };
    });
    setCommonRuleEditingSection(details.dataset.commonSection || '');
}

function getCommonRuleSectionLabels(section = '') {
    const labels = {
        generation_constraints: {
            title: '共用 Prompt 约束',
            subtitle: '控制所有段落共同遵守的写作边界和硬约束'
        },
        evidence_scope: {
            title: '证据来源与时间',
            subtitle: '设置报告日期、证据窗口和可使用的数据源'
        },
        retrieval: {
            title: '检索策略',
            subtitle: '设置召回模式、Top K、候选数和语义/关键词权重'
        },
        rerank: {
            title: '证据重排',
            subtitle: '设置 reranker、候选证据数和最低相关分'
        }
    };
    return labels[section] || {
        title: '共用配置',
        subtitle: '调整共用生成参数'
    };
}

function openCommonRuleEditorModal(section) {
    const details = [...document.querySelectorAll('#template-common-rules details[data-common-section]')]
        .find(item => item.dataset.commonSection === section);
    const editor = details?.querySelector('.template-common-rule-editor');
    if (!details || !editor) return;
    setCommonRuleEditingSection(section);
    const labels = getCommonRuleSectionLabels(section);
    openTemplateConfigEditorModal({
        title: labels.title,
        subtitle: labels.subtitle,
        contentNode: editor,
        action: 'common'
    });
    const template = getCurrentWorkbenchTemplate();
    if (template) bindCommonRuleInputs(template);
}

function syncSourceTypeCheckboxes(changedInput) {
    const scope = changedInput.closest('#template-config-editor-modal-body') || document.getElementById('template-common-rules') || document;
    const allInput = scope.querySelector('[data-common-source-type="__all__"]');
    const sourceInputs = [...scope.querySelectorAll('[data-common-source-type]:not([data-common-source-type="__all__"])')];
    if (changedInput.dataset.commonSourceType === '__all__' && changedInput.checked) {
        sourceInputs.forEach(input => {
            input.checked = false;
        });
        return;
    }
    if (changedInput.dataset.commonSourceType !== '__all__' && changedInput.checked && allInput) {
        allInput.checked = false;
    }
    if (allInput && !sourceInputs.some(input => input.checked)) {
        allInput.checked = true;
    }
}

function syncEvidenceRangeFromReportDate(reportDate) {
    const normalizedReportDate = reportDate || getDefaultReportDate();
    const scope = document.querySelector('#template-config-editor-modal-body [data-common-rule-field="report_period.report_date"]')
        ? document.getElementById('template-config-editor-modal-body')
        : document.getElementById('template-common-rules');
    const startInput = scope?.querySelector('[data-common-rule-field="report_period.start_date"]');
    const endInput = scope?.querySelector('[data-common-rule-field="report_period.end_date"]');
    if (startInput) startInput.value = getDefaultEvidenceStartDate(normalizedReportDate);
    if (endInput) endInput.value = normalizedReportDate;
}

function snapshotCommonRuleOpenState(root = document) {
    const detailsList = root.querySelectorAll?.('details[data-common-section]') || [];
    if (!detailsList.length) return;
    const nextState = { ...(currentTemplateState.commonRuleOpenState || {}) };
    detailsList.forEach(details => {
        nextState[details.dataset.commonSection] = details.open;
    });
    currentTemplateState.commonRuleOpenState = nextState;
}

function isCommonRuleSectionOpen(section, fallback = false) {
    const state = currentTemplateState.commonRuleOpenState || {};
    return Object.prototype.hasOwnProperty.call(state, section) ? Boolean(state[section]) : fallback;
}

function formatRulePercent(value) {
    const numberValue = Number(value);
    if (!Number.isFinite(numberValue)) return '0%';
    return `${Math.round(numberValue * 100)}%`;
}

function getFirstLine(value) {
    return String(value || '').split('\n').map(line => line.trim()).find(Boolean) || '未填写共用约束';
}

function getHardConstraintPromptText(hardConstraints = {}) {
    if (typeof hardConstraints.prompt_text === 'string' && hardConstraints.prompt_text.trim()) {
        return hardConstraints.prompt_text;
    }

    const lines = [];
    if (hardConstraints.no_wind_data !== false || hardConstraints.no_baidu_data !== false) {
        const blocked = [
            hardConstraints.no_wind_data !== false ? 'Wind 数据' : '',
            hardConstraints.no_baidu_data !== false ? '百度数据' : ''
        ].filter(Boolean).join('、');
        lines.push(`不使用${blocked}，仅基于上传素材、Excel 数据和检索证据撰写。`);
    }
    if (hardConstraints.require_number_source !== false) {
        lines.push('涉及数字时必须说明来源。');
    }
    if (Array.isArray(hardConstraints.forbidden_phrases) && hardConstraints.forbidden_phrases.length) {
        lines.push(`避免使用这些模板化表述：${hardConstraints.forbidden_phrases.join('、')}。`);
    }
    if (Array.isArray(hardConstraints.forbidden_entity_categories) && hardConstraints.forbidden_entity_categories.length) {
        lines.push(`不要输出这些实体类别的清单式堆砌：${hardConstraints.forbidden_entity_categories.join('、')}。`);
    }
    if (hardConstraints.single_paragraph !== false) {
        lines.push('除模板特别要求外，只输出一段正式周报正文，不换行。');
    }
    return lines.join('\n') || [
        '仅基于上传素材、Excel 数据和检索证据撰写，不使用外部事实补充。',
        '语言客观审慎，不输出投资收益保证或直接买卖建议。'
    ].join('\n');
}

function collectCommonDefaultsDraft(template) {
    const containers = [
        document.getElementById('template-common-rules'),
        document.getElementById('template-placeholder-detail-form'),
        document.getElementById('template-config-editor-modal-body')
    ].filter(Boolean);
    if (!containers.length) return getEditableCommonDefaults(template);

    const existing = getEditableCommonDefaults(template);
    const draft = {
        ...existing,
        validators: { ...(existing.validators || {}) },
        hard_constraints: { ...(existing.hard_constraints || {}) },
        generation_constraints: Array.isArray(existing.generation_constraints)
            ? [...existing.generation_constraints]
            : [],
        retrieval: { ...(existing.retrieval || {}) },
        report_period: { ...(existing.report_period || {}) },
        rerank: { ...(existing.rerank || {}) }
    };

    containers.forEach(container => container.querySelectorAll('[data-common-rule-field]').forEach(input => {
        const field = input.dataset.commonRuleField;
        if (!field) return;
        let value;
        if (input.type === 'checkbox') {
            value = input.checked;
        } else if (field === 'generation_constraints') {
            value = splitLines(input.value);
        } else if (field === 'validators.forbidden_terms'
            || field === 'hard_constraints.forbidden_phrases'
            || field === 'hard_constraints.forbidden_entity_categories'
            || field === 'retrieval.source_types') {
            value = splitDelimitedList(input.value);
        } else if (input.type === 'number') {
            value = input.value === '' ? null : Number(input.value);
        } else {
            value = input.value?.trim?.() || '';
        }

        const path = field.split('.');
        if (path.length === 2 && draft[path[0]] && typeof draft[path[0]] === 'object') {
            draft[path[0]][path[1]] = value;
        } else {
            draft[field] = value;
        }
    }));
    const selectedSourceTypes = [
        ...containers.flatMap(container => [...container.querySelectorAll('[data-common-source-type]:checked')])
    ]
        .map(input => input.value)
        .filter(Boolean);
    if (containers.some(container => container.querySelector('[data-common-source-type]'))) {
        draft.retrieval.source_types = selectedSourceTypes;
    }

    currentTemplateState.commonDefaultsDraft = draft;
    return draft;
}

function getStoredPlaceholderMappings(template) {
    const raw = template?.report_project?.report_config?.placeholders;
    const mappings = new Map();
    if (Array.isArray(raw)) {
        raw.forEach(item => {
            const key = normalizePlaceholderName(item?.name || item?.key || item?.placeholder);
            if (key) mappings.set(key, item);
        });
    } else if (raw && typeof raw === 'object') {
        Object.entries(raw).forEach(([key, value]) => {
            mappings.set(normalizePlaceholderName(key), value || {});
        });
    }
    return mappings;
}

function getPlaceholderMappings(template) {
    return getStoredPlaceholderMappings(template);
}

function getCurrentPlaceholderMappings(template) {
    const storedMappings = getStoredPlaceholderMappings(template);
    const placeholders = getTemplateWorkbenchPlaceholders(template);
    if (!placeholders.length) return storedMappings;

    const hasMissingPlaceholders = placeholders.some(placeholder =>
        !storedMappings.has(normalizePlaceholderName(placeholder))
    );
    if (!hasMissingPlaceholders && storedMappings.size) return storedMappings;

    return buildDraftPlaceholderMappings(template, storedMappings);
}

function buildDraftPlaceholderMappings(template, storedMappings = new Map()) {
    const project = template.report_project || null;
    const mappings = new Map(storedMappings);
    getTemplateWorkbenchPlaceholders(template).forEach(placeholder => {
        const key = normalizePlaceholderName(placeholder);
        if (!key) return;
        const stored = storedMappings.get(key) || {};
        const storedType = stored.type || '';
        const type = getCanonicalPlaceholderType(storedType, stored) || inferPlaceholderType(key);
        const paragraphMode = type === 'paragraph' ? getParagraphMode(storedType, stored, key) : undefined;
        const needsEvidenceDefaults = type === 'paragraph' && usesEvidenceParagraphMode(storedType, paragraphMode);
        mappings.set(key, {
            ...stored,
            title: inferPlaceholderTitle(key),
            type,
            mode: paragraphMode,
            prompt_template: needsEvidenceDefaults
                ? (stored.prompt_template || resolvePromptTemplateName(key, project))
                : undefined,
            query_mode: needsEvidenceDefaults && usesEmbeddedPromptQueries(project)
                ? (stored.query_mode || 'retrieval_query_embedded')
                : undefined,
            query_source: needsEvidenceDefaults && !usesEmbeddedPromptQueries(project)
                ? (stored.query_source || inferQuerySource(key, project))
                : undefined
        });
    });
    return mappings;
}

function isPlaceholderMappingConfigured(mapping) {
    return Boolean(
        mapping?.source
        || mapping?.value
        || mapping?.prompt_template
        || mapping?.query_source
    );
}

function normalizePlaceholderName(name) {
    return String(name || '').replace(/^\{\{\s*/, '').replace(/\s*\}\}$/, '').trim();
}

function bindPlaceholderMapRows() {
    const picker = document.getElementById('template-placeholder-select');
    if (picker && !picker.dataset.bound) {
        picker.dataset.bound = 'true';
        picker.addEventListener('click', event => {
            event.stopPropagation();
            togglePlaceholderPickerMenu();
        });
        picker.addEventListener('keydown', event => {
            if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                togglePlaceholderPickerMenu();
            }
            if (event.key === 'Escape') closePlaceholderPickerMenu();
        });
        startPlaceholderPickerSync();
    }
    document.querySelectorAll('#template-placeholder-map .placeholder-select-option').forEach(option => {
        if (option.dataset.bound) return;
        option.dataset.bound = 'true';
        option.addEventListener('click', event => {
            event.stopPropagation();
            selectTemplatePlaceholder(option.dataset.placeholderName || '');
            closePlaceholderPickerMenu();
        });
    });
    document.querySelectorAll('#template-placeholder-map .placeholder-map-row').forEach(row => {
        if (row.dataset.bound) return;
        row.dataset.bound = 'true';
        row.addEventListener('click', () => selectTemplatePlaceholder(row.dataset.placeholderName || ''));
    });
    if (!document.body.dataset.placeholderPickerCloseBound) {
        document.body.dataset.placeholderPickerCloseBound = 'true';
        document.addEventListener('click', closePlaceholderPickerMenu);
    }
}

function selectTemplatePlaceholder(name) {
    const normalizedName = normalizePlaceholderName(name);
    if (!normalizedName) return;
    currentTemplateState.selectedPlaceholderName = normalizedName;
    const template = getCurrentWorkbenchTemplate();
    if (!template) return;
    setPlaceholderPickerValue(normalizedName);
    renderSelectedPlaceholderDetail(template);
    updateTemplateSourceSwitcher(template);
    updateTemplateSourceFromPlaceholderDraft(template);
}

function getPlaceholderPickerValue() {
    const picker = document.getElementById('template-placeholder-select');
    return normalizePlaceholderName(picker?.dataset.value || picker?.value || '');
}

function setPlaceholderPickerValue(name) {
    const normalizedName = normalizePlaceholderName(name);
    const picker = document.getElementById('template-placeholder-select');
    if (picker) {
        picker.dataset.value = normalizedName;
        picker.value = normalizedName;
        const label = picker.querySelector('.placeholder-select-text');
        if (label) label.textContent = normalizedName;
    }
    document.querySelectorAll('#template-placeholder-map .placeholder-select-option').forEach(option => {
        const isSelected = normalizePlaceholderName(option.dataset.placeholderName || '') === normalizedName;
        option.setAttribute('aria-selected', isSelected ? 'true' : 'false');
    });
}

function togglePlaceholderPickerMenu() {
    const picker = document.getElementById('template-placeholder-select');
    const wrapper = picker?.closest('.placeholder-picker');
    const menu = wrapper?.querySelector('.placeholder-select-menu');
    if (!picker || !wrapper || !menu) return;
    const isOpen = wrapper.dataset.open === 'true';
    wrapper.dataset.open = isOpen ? 'false' : 'true';
    picker.setAttribute('aria-expanded', isOpen ? 'false' : 'true');
    menu.hidden = isOpen;
}

function closePlaceholderPickerMenu() {
    const picker = document.getElementById('template-placeholder-select');
    const wrapper = picker?.closest('.placeholder-picker');
    const menu = wrapper?.querySelector('.placeholder-select-menu');
    if (!picker || !wrapper || !menu) return;
    wrapper.dataset.open = 'false';
    picker.setAttribute('aria-expanded', 'false');
    menu.hidden = true;
}

function getEffectivePlaceholderMapping(template, placeholderName) {
    const name = normalizePlaceholderName(placeholderName);
    if (!name) return null;
    const draft = currentTemplateState.placeholderMappingDrafts?.[name];
    if (draft) return draft;
    const mappings = getCurrentPlaceholderMappings(template);
    return mappings.get(name) || {
        title: inferPlaceholderTitle(name),
        type: inferPlaceholderType(name)
    };
}

function getSelectedPlaceholderMapping(template) {
    return getEffectivePlaceholderMapping(template, currentTemplateState.selectedPlaceholderName);
}


function getRenderedPlaceholderSummaryName() {
    return normalizePlaceholderName(
        document.querySelector('#template-placeholder-detail-form .template-config-summary-head h4')?.textContent || ''
    );
}

function syncSelectedPlaceholderFromPicker() {
    const selectedName = getPlaceholderPickerValue();
    if (selectedName && selectedName !== normalizePlaceholderName(currentTemplateState.selectedPlaceholderName)) {
        currentTemplateState.selectedPlaceholderName = selectedName;
    }
    return normalizePlaceholderName(currentTemplateState.selectedPlaceholderName);
}

function reconcilePlaceholderPickerAndDetail() {
    const pickerName = getPlaceholderPickerValue();
    if (!pickerName) return;
    const stateName = normalizePlaceholderName(currentTemplateState.selectedPlaceholderName);
    const renderedName = getRenderedPlaceholderSummaryName();
    if (pickerName === stateName && (!renderedName || renderedName === pickerName)) return;
    currentTemplateState.selectedPlaceholderName = pickerName;
    const template = getCurrentWorkbenchTemplate();
    if (!template) return;
    renderSelectedPlaceholderDetail(template);
    updateTemplateSourceSwitcher(template);
    updateTemplateSourceFromPlaceholderDraft(template);
}

function startPlaceholderPickerSync() {
    if (currentTemplateState.placeholderPickerSyncTimer) return;
    currentTemplateState.placeholderPickerSyncTimer = window.setInterval(() => {
        const select = document.getElementById('template-placeholder-select');
        if (!select) return;
        reconcilePlaceholderPickerAndDetail();
    }, 250);
}

function renderPlaceholderSaveFeedback(message, tone = 'success') {
    const feedbackEl = document.getElementById('template-config-save-feedback');
    if (!feedbackEl) return;
    feedbackEl.textContent = message || '';
    feedbackEl.hidden = !message;
    feedbackEl.dataset.tone = tone;
}

function renderSelectedPlaceholderDetail(template) {
    const titleEl = document.getElementById('template-selected-placeholder-title');
    const formEl = document.getElementById('template-placeholder-detail-form');
    const advancedFormEl = document.getElementById('template-advanced-placeholder-form');
    const advancedSectionEl = advancedFormEl?.closest('.template-advanced-section');
    const advancedDrawerBodyEl = advancedFormEl?.closest('.template-advanced-drawer-body');
    const saveBtn = document.getElementById('btn-template-save-placeholder');
    const advancedBtn = document.getElementById('btn-template-advanced-config');
    if (!formEl) return;

    const name = syncSelectedPlaceholderFromPicker();
    const mapping = getSelectedPlaceholderMapping(template);
    if (!name || !mapping) {
        if (titleEl) titleEl.textContent = '占位符配置详情';
        formEl.innerHTML = '<div class="empty-state compact">选择一个段落后编辑配置</div>';
        if (advancedFormEl) advancedFormEl.innerHTML = '<div class="empty-state compact">选择段落后显示高级字段</div>';
        advancedSectionEl?.classList.add('hidden');
        advancedDrawerBodyEl?.classList.remove('source-only');
        if (saveBtn) saveBtn.disabled = true;
        if (advancedBtn) advancedBtn.disabled = true;
        return;
    }

    if (titleEl) titleEl.textContent = '';
    if (saveBtn) saveBtn.disabled = false;
    if (advancedBtn) advancedBtn.disabled = false;

    const storedType = mapping.type || '';
    const type = getCanonicalPlaceholderType(storedType, mapping) || inferPlaceholderType(name);
    const paragraphMode = getParagraphMode(storedType, mapping, name);
    const isPromptLike = usesEvidenceParagraphMode(storedType, paragraphMode);
    const promptParam = mapping.params?.param || inferPromptParam(name);
    const needsParam = isPromptLike && Boolean(promptParam);
    const usesQuerySource = isPromptLike && !usesEmbeddedPromptQueries(template.report_project);
    const selectedKeywordProfile = getSelectedKeywordProfileName(template, mapping, name);
    const keywordMode = inferKeywordMode(template, mapping, name);
    const retrievalKeywords = getKeywordEditorText(template, mapping, name, keywordMode, selectedKeywordProfile);
    const minNewsCount = mapping.min_news_count || '';
    const supportsDataTemplate = isDataTemplateParagraphMode(storedType, paragraphMode);
    const dataTemplate = supportsDataTemplate
        ? (getDataTemplateComponent(mapping).template || inferDefaultDataTemplate(name))
        : '';
    const dataTemplateFields = getDataTemplateFields(mapping, {
        includeDefaults: supportsDataTemplate
    });
    const writingStructure = getLlmWritingComponent(mapping).writing_structure || mapping.writing_structure || inferDefaultWritingStructure(name);
    const writingStructureText = Array.isArray(writingStructure) ? writingStructure.join('\n') : '';
    const rawSemanticQuery = getConfiguredSemanticRetrievalQueryForPlaceholder(template, mapping, name);
    const semanticQueryDisplay = getSemanticRetrievalQueryForPlaceholder(template, mapping, name);
    const typeOptions = getEditablePlaceholderTypeOptions(type);
    updateTemplateConfigPlaceholderChips(type, mapping, template, name);
    renderPlaceholderWizardControls(template);

    const editorHtml = buildSimplePlaceholderFieldsHtml({
        name,
        type,
        paragraphMode,
        mapping,
        isPromptLike,
        retrievalKeywords,
        selectedKeywordProfile,
        keywordMode,
        minNewsCount,
        dataTemplate,
        dataTemplateFields,
        writingStructureText,
        typeOptions,
        template
    });
    formEl.innerHTML = `
        <div id="template-placeholder-editor-source" class="template-inline-editor-source">
            ${editorHtml}
        </div>
        ${buildPlaceholderConfigSummaryHtml({
            name,
            type,
            paragraphMode,
            mapping,
            isPromptLike,
            selectedKeywordProfile,
            keywordMode,
            minNewsCount,
            dataTemplateFields,
            retrievalKeywords,
            rawSemanticQuery,
            semanticQueryDisplay,
            dataTemplate,
            writingStructureText,
            template
        })}
        <p id="template-config-save-feedback" class="template-config-save-feedback" role="status" aria-live="polite" hidden></p>
    `;

    if (advancedFormEl) {
        advancedFormEl.innerHTML = buildAdvancedPlaceholderFieldsHtml({
            name,
            type,
            paragraphMode,
            mapping,
            isPromptLike,
            typeOptions,
            needsParam,
            usesQuerySource,
            promptParam,
            template
        });
        const hasAdvancedFields = Boolean(advancedFormEl.querySelector('[data-placeholder-field]'));
        advancedSectionEl?.classList.toggle('hidden', !hasAdvancedFields);
        advancedDrawerBodyEl?.classList.toggle('source-only', !hasAdvancedFields);
    }

    bindPlaceholderDetailInputs(template);
    bindPlaceholderSummaryEditActions(template);
}

function bindPlaceholderSummaryEditActions(template) {
    document.querySelectorAll('#template-placeholder-detail-form [data-placeholder-edit-section]').forEach(item => {
        if (item.dataset.boundPlaceholderEditSection) return;
        item.dataset.boundPlaceholderEditSection = 'true';
        item.addEventListener('click', (e) => {
            // 编辑模式下点击表单元素不做任何事（让用户正常输入）
            if (item.classList.contains('is-editing')) {
                const tag = e.target.tagName;
                if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || tag === 'LABEL' || tag === 'OPTION') {
                    return;
                }
            }
            const section = item.dataset.placeholderEditSection || 'all';
            openPlaceholderConfigEditorModal(
                template,
                section,
                item.dataset.placeholderEditField || ''
            );
        });
    });
}


/* ── 统一 rendering 配置内联 badges（嵌入卡片内）── */
function buildRenderingBadges(mapping) {
    const parts = [];
    const rendering = mapping.rendering || {};
    if (Array.isArray(rendering.runs) && rendering.runs.length > 0) {
        const fontInfo = [rendering.default_font, rendering.default_size_pt ? `${rendering.default_size_pt}pt` : ''].filter(Boolean).join(' ') || '默认';
        parts.push(`<span class="template-config-enhancement-badge">📝 ${esc(fontInfo)} · ${rendering.runs.length} 个文本片段</span>`);
    }
    if (!parts.length) return '';
    return `<div class="template-config-enhancement-badges">${parts.join('')}</div>`;
}

function buildKeywordGroupsInlineBadges(groups) {
    if (!Array.isArray(groups) || !groups.length) return '';
    const badges = groups.slice(0, 3).map((g, i) => {
        const text = Array.isArray(g) ? g.slice(0, 4).join(', ') : String(g);
        const more = Array.isArray(g) && g.length > 4 ? ` +${g.length - 4}` : '';
        return `<span class="template-config-enhancement-badge">G${i + 1}: ${esc(text)}${more}</span>`;
    }).join('');
    const more = groups.length > 3 ? `<span class="template-config-enhancement-badge">+${groups.length - 3} 组</span>` : '';
    return `<div class="template-config-enhancement-badges">${badges}${more}</div>`;
}

/* ── 增强字段 textarea ↔ 结构化数据 互转 ── */
function formatRunsForTextarea(runs) {
    if (!Array.isArray(runs) || !runs.length) return '';
    return runs.map(r => {
        if (!r) return '';
        if (r.is_dynamic) return 'dynamic';
        const fields = ['static', r.bold ? 'bold' : '', r.font_size_pt || '', r.color_hex || '', r.text || ''];
        return fields.join('|');
    }).join('\n');
}

function formatKeywordGroupsForTextarea(groups) {
    if (!Array.isArray(groups) || !groups.length) return '';
    return groups.map(g => (Array.isArray(g) ? g.join(', ') : String(g))).join('\n');
}

function parseRunsTextarea(text) {
    if (!text || !text.trim()) return [];
    return text.split('\n').map(line => {
        const trimmed = line.trim();
        if (!trimmed) return null;
        if (trimmed === 'dynamic' || trimmed.startsWith('dynamic')) {
            return { is_dynamic: true };
        }
        const parts = trimmed.split('|');
        const style = parts[0] === 'static' ? parts[1] : parts[0];
        const isStatic = parts[0] === 'static';
        const boldIdx = isStatic ? 1 : 0;
        const fontSizeIdx = isStatic ? 2 : 1;
        const colorIdx = isStatic ? 3 : 2;
        const textIdx = isStatic ? 4 : 3;
        return {
            text: (parts[textIdx] || '').trim(),
            bold: (parts[boldIdx] || '').trim() === 'bold' || undefined,
            font_size_pt: parseFloat(parts[fontSizeIdx]) || undefined,
            color_hex: (parts[colorIdx] || '').trim() || undefined,
            is_dynamic: false
        };
    }).filter(Boolean);
}

function parseKeywordGroupsTextarea(text) {
    if (!text || !text.trim()) return [];
    return text.split('\n').map(line => {
        const trimmed = line.trim();
        if (!trimmed) return null;
        return trimmed.split(',').map(s => s.trim()).filter(Boolean);
    }).filter(Boolean);
}

function buildConfigCollapsibleSection({
    title,
    meta = '',
    editSection,
    body,
    open = false
}) {
    const editSectionAttribute = {
        keywords: 'data-placeholder-edit-section="keywords"',
        fixed_template: 'data-placeholder-edit-section="fixed_template"',
        data_fields: 'data-placeholder-edit-section="data_fields"',
        writing: 'data-placeholder-edit-section="writing"'
    }[editSection] || `data-placeholder-edit-section="${esc(editSection)}"`;
    return `
        <details class="template-config-collapsible-section"${open ? ' open' : ''}>
            <summary>
                <div class="template-config-readable-title">
                    <strong>${esc(title)}</strong>
                    <span>${esc(meta)}</span>
                </div>
                <button class="template-config-inline-action template-config-edit-trigger" type="button" ${editSectionAttribute}>编辑</button>
            </summary>
            <div class="template-config-collapsible-body">
                ${body || ''}
            </div>
        </details>
    `;
}

function buildPlaceholderConfigSummaryHtml({
    name,
    type,
    paragraphMode = '',
    mapping = {},
    isPromptLike,
    selectedKeywordProfile,
    keywordMode,
    minNewsCount,
    dataTemplateFields = {},
    retrievalKeywords = '',
    rawSemanticQuery = '',
    semanticQueryDisplay: providedSemanticQueryDisplay = '',
    dataTemplate = '',
    writingStructureText = '',
    template
}) {
    const effectiveMode = isParagraphPlaceholderType(type, mapping)
        ? (isParagraphMode(paragraphMode) ? paragraphMode : getParagraphMode(type, mapping, name))
        : '';
    const supportsDataTemplate = isDataTemplateParagraphMode(type, effectiveMode);
    const usesEvidence = usesEvidenceParagraphMode(type, effectiveMode);
    const dataFieldEntries = dataTemplateFields && typeof dataTemplateFields === 'object'
        ? Object.entries(dataTemplateFields)
        : [];
    rawSemanticQuery = String(rawSemanticQuery ?? '');
    const semanticQueryDisplay = String(providedSemanticQueryDisplay ?? '');
    const keywordList = splitLines(retrievalKeywords || '');
    const writingSteps = splitLines(writingStructureText);
    if (isReportPeriodFieldPlaceholder(mapping.type || type, mapping, name)) {
        const field = mapping.field || inferReportPeriodField(name);
        const defaults = getEditableCommonDefaults(template);
        const reportPeriod = defaults.report_period || {};
        const fieldLabel = field === 'start_date' ? '开始日期' : '结束日期';
        const fieldValue = field === 'start_date'
            ? (reportPeriod.start_date || getDefaultEvidenceStartDate(reportPeriod.report_date || getDefaultReportDate()))
            : (reportPeriod.end_date || reportPeriod.report_date || getDefaultReportDate());
        const facts = [
            { label: '字段类型', value: '报告日期' },
            { label: '映射字段', value: fieldLabel }
        ];
        return `
            <section class="template-config-summary-card template-config-readable-card">
                <div class="template-config-summary-head">
                    <div>
                        <h4>${esc(name)}</h4>
                    </div>
                </div>
                <div class="template-config-summary-grid template-config-basic-grid template-report-period-summary-grid">
                    ${facts.map(item => `
                        <div class="template-config-summary-item">
                            <span>${esc(item.label)}</span>
                            <strong>${esc(item.value)}</strong>
                        </div>
                    `).join('')}
                    <label class="template-config-summary-item template-config-report-date-field">
                        <span>${esc(fieldLabel)}</span>
                        <input type="date" data-common-rule-field="report_period.${esc(field)}" value="${esc(fieldValue)}">
                    </label>
                </div>
                <button class="template-config-readable-section template-config-edit-trigger" type="button" data-placeholder-edit-section="basic">
                    <div class="template-config-readable-title">
                        <strong>取值来源</strong>
                        <span>共用参数</span>
                    </div>
                    <p>由“证据来源与时间”里的报告日期和数据使用范围自动填充，不参与 AI 生成，也不需要额外生成参数。</p>
                </button>
            </section>
        `;
    }
    const facts = isParagraphPlaceholderType(type, mapping)
        ? [
            { label: '段落方式', value: getParagraphModeLabel(effectiveMode) },
            ...(usesEvidence ? [
                { label: '目标字数', value: mapping.target_words || inferDefaultTargetWords(name) },
                { label: '证据条数', value: minNewsCount || mapping.min_news_count || '默认' }
            ] : [
                { label: '数据变量', value: dataFieldEntries.length ? `${dataFieldEntries.length} 个` : '未配置' },
                { label: 'AI 生成', value: '不参与' }
            ])
        ]
        : [
            { label: '目标字数', value: mapping.target_words || inferDefaultTargetWords(name) },
            { label: '证据条数', value: minNewsCount || mapping.min_news_count || '默认' }
        ];
    const rendering = mapping.rendering || {};
    const hasRuns = Array.isArray(rendering.runs) && rendering.runs.length > 0;
    const queryNeedsAttention = usesEvidence && !rawSemanticQuery.trim();
    const keywordsNeedAttention = usesEvidence && !queryNeedsAttention && keywordList.length === 0;
    return `
        <section class="template-config-summary-card template-config-readable-card">
            <div class="template-config-summary-head">
                <div>
                    <h4>${esc(name)}</h4>
                </div>
            </div>
            <button class="template-config-summary-grid template-config-basic-grid template-config-edit-trigger" type="button" data-placeholder-edit-section="basic">
                ${facts.map(item => `
                    <div class="template-config-summary-item">
                        <span>${esc(item.label)}</span>
                        <strong>${esc(item.value)}</strong>
                    </div>
                `).join('')}
                ${hasRuns ? buildRenderingBadges(mapping) : ''}
            </button>
            ${usesEvidence ? `
                ${queryNeedsAttention ? `
                    <button class="template-config-next-action template-config-edit-trigger" type="button" data-placeholder-edit-section="query">
                        <span>下一步</span>
                        <strong>补充语义 Query，明确系统应召回哪些材料。</strong>
                    </button>
                ` : keywordsNeedAttention ? `
                    <button class="template-config-next-action template-config-edit-trigger" type="button" data-placeholder-edit-section="keywords">
                        <span>下一步</span>
                        <strong>选择关键词预设包，或添加自定义关键词。</strong>
                    </button>
                ` : ''}
                ${buildConfigCollapsibleSection({
                    title: '语义 Query',
                    meta: queryNeedsAttention ? '待补充 · 用于相关内容召回' : '用于相关内容召回',
                    editSection: 'query',
                    open: queryNeedsAttention,
                    body: `<p>${esc(semanticQueryDisplay.trim() || '未配置语义 Query')}</p>`
                })}
                ${buildConfigCollapsibleSection({
                    title: '关键词',
                    meta: `${keywordMode === 'profile' ? `预设包：${selectedKeywordProfile || '未选择'}` : '自定义'} · ${keywordList.length} 个`,
                    editSection: 'keywords',
                    body: `
                    <div class="template-config-keyword-cloud">
                        ${keywordList.length
                            ? keywordList.map(keyword => `<span>${esc(keyword)}</span>`).join('')
                            : '<em>暂无关键词</em>'}
                    </div>
                    `
                })}
            ` : ''}
            ${supportsDataTemplate && dataTemplate ? `
                ${buildConfigCollapsibleSection({
                    title: '固定开头模板',
                    meta: 'Excel 数据填充',
                    editSection: 'fixed_template',
                    body: `<p class="template-config-data-template-preview">${renderDataTemplatePreview(dataTemplate, dataTemplateFields)}</p>`
                })}
            ` : ''}
            ${dataFieldEntries.length ? `
                ${buildConfigCollapsibleSection({
                    title: '模板变量数据来源',
                    meta: `${dataFieldEntries.length} 个变量`,
                    editSection: 'data_fields',
                    body: `
                    <div class="template-config-data-overview">
                        ${dataFieldEntries.map(([fieldKey, field]) => `
                            <button class="template-config-data-overview-row template-config-edit-trigger" type="button" data-placeholder-edit-section="data_fields" data-placeholder-edit-field="${esc(fieldKey)}">
                                <span class="template-config-variable-chip" title="内部变量：${esc(fieldKey)}">${esc(getDataTemplateFieldDisplayLabel(fieldKey, field))}</span>
                                <span>${esc(field.workbook || '未设置文件')}</span>
                                <span>${esc(field.sheet || '未设置 Sheet')}</span>
                                <span>${esc(field.cell || field.range || '未设置区域')}</span>
                                <small>${esc(field.rule || '未设置取数规则')}</small>
                            </button>
                        `).join('')}
                    </div>
                    `
                })}
            ` : ''}
            ${usesEvidence ? `
                ${buildConfigCollapsibleSection({
                    title: '写作结构',
                    meta: writingSteps.length ? `${writingSteps.length} 步` : '未配置',
                    editSection: 'writing',
                    body: writingSteps.length ? `
                        <ol class="template-config-writing-steps">
                            ${writingSteps.map(step => `<li>${esc(step)}</li>`).join('')}
                        </ol>
                    ` : `
                        <p class="template-config-empty-note">未单独配置写作步骤，点击这里添加生成正文的结构和表达边界。</p>
                    `
                })}
            ` : ''}
        </section>
    `;
}

function getPlaceholderEditSectionLabels(section = '', fieldKey = '') {
    const labels = {
        basic: ['基础参数', '修改当前占位符的字数、证据条数等常用参数'],
        query: ['语义 Query', '修改用于召回相关内容的检索 Query'],
        keywords: ['关键词', '修改关键词来源、预设包或自定义关键词'],
        fixed_template: ['固定开头模板', '修改 Excel 数据填充的固定文案模板'],
        data_fields: [fieldKey ? `变量：${getDataTemplateFieldDisplayLabel(fieldKey)}` : '模板变量数据来源', '修改变量的 Excel 文件、Sheet、区域和计算规则'],
        writing: ['写作结构', '修改生成正文的步骤和表达边界'],
        all: ['编辑配置', '修改当前占位符的生成、检索、Excel 和关键词配置']
    };
    const [title, subtitle] = labels[section] || labels.all;
    return { title, subtitle };
}

function setPlaceholderEditingSection(section = '', fieldKey = '') {
    document.querySelectorAll('#template-placeholder-detail-form [data-placeholder-edit-section]').forEach(item => {
        item.classList.toggle('is-editing', Boolean(section)
            && item.dataset.placeholderEditSection === section
            && (!fieldKey || item.dataset.placeholderEditField === fieldKey));
    });
}

function setPlaceholderEditorVisibility(editor, section = 'all', fieldKey = '') {
    const activeSection = section || 'all';
    const children = Array.from(editor.children);
    const sectionChildren = children.filter(child => child.dataset.placeholderEditorSection);
    const shouldFilter = activeSection !== 'all' && sectionChildren.length > 0;
    children.forEach(child => {
        if (!shouldFilter) {
            child.hidden = false;
            return;
        }
        const childSections = String(child.dataset.placeholderEditorSection || '').split(/\s+/).filter(Boolean);
        child.hidden = !childSections.includes(activeSection);
    });
    editor.querySelectorAll('[data-placeholder-editor-field]').forEach(row => {
        row.hidden = activeSection === 'data_fields'
            && Boolean(fieldKey)
            && row.dataset.placeholderEditorField !== fieldKey;
    });
}

function openPlaceholderConfigEditorModal(template, section = 'all', fieldKey = '') {
    const editor = document.getElementById('template-placeholder-editor-source');
    const name = normalizePlaceholderName(currentTemplateState.selectedPlaceholderName);
    if (!editor || !name) return;
    const labels = getPlaceholderEditSectionLabels(section, fieldKey);
    editor.dataset.activeEditorSection = section || 'all';
    editor.dataset.activeEditorField = fieldKey || '';
    setPlaceholderEditingSection(section, fieldKey);
    setPlaceholderEditorVisibility(editor, section, fieldKey);
    openTemplateConfigEditorModal({
        title: name,
        subtitle: '',
        contentNode: editor,
        action: 'placeholder'
    });
    setPlaceholderEditorVisibility(editor, section, fieldKey);
    bindPlaceholderDetailInputs(template);
}

function updateTemplateConfigPlaceholderChips(type, mapping = {}, template = getCurrentWorkbenchTemplate(), placeholderName = '') {
    const typeEl = document.getElementById('template-config-placeholder-type');
    const sourceEl = document.getElementById('template-config-placeholder-source');
    const healthEl = document.getElementById('template-config-placeholder-health');
    const kind = getPlaceholderKindLabel(mapping, { type });
    const paragraphMode = isParagraphPlaceholderType(type, mapping)
        ? getParagraphMode(type, mapping)
        : '';
    const source = isParagraphPlaceholderType(type, mapping)
        ? (
            isDataTemplateParagraphMode(type, paragraphMode)
                ? (usesEvidenceParagraphMode(type, paragraphMode) ? 'Prompt + Excel' : 'Excel 数据')
                : 'Prompt + 证据'
        )
        : type === 'field'
            ? (
                isReportPeriodFieldPlaceholder(mapping.type || type, mapping)
                    ? '报告周期'
                    : isExcelFieldPlaceholder(mapping.type || type, mapping)
                        ? 'Excel 数据'
                        : '手动/配置'
            )
            : type === 'table'
                ? '表格管线'
                : type === 'chart'
                    ? '图表管线'
                    : (mapping.source || mapping.data_source ? 'Excel 数据' : '模板配置');
    if (typeEl) typeEl.textContent = kind;
    if (sourceEl) sourceEl.textContent = source;
    if (healthEl) {
        const lifecycle = getPlaceholderLifecycleStatus(template, mapping, placeholderName);
        healthEl.textContent = lifecycle.label;
        healthEl.title = lifecycle.detail;
        healthEl.classList.toggle('ok', lifecycle.state === 'ready');
        healthEl.classList.toggle('confirm', lifecycle.state === 'confirm');
        healthEl.classList.toggle('missing', lifecycle.state === 'missing');
    }
}

function buildSimplePlaceholderFieldsHtml({
    name,
    type,
    paragraphMode = '',
    mapping,
    isPromptLike,
    retrievalKeywords,
    selectedKeywordProfile,
    keywordMode,
    minNewsCount,
    dataTemplate,
    dataTemplateFields,
    writingStructureText,
    typeOptions = getEditablePlaceholderTypeOptions(type),
    template
}) {
    const typeSelectHtml = renderPlaceholderOutputShapeSelect(type, typeOptions);
    if (isParagraphPlaceholderType(type, mapping)) {
        const effectiveMode = isParagraphMode(paragraphMode)
            ? paragraphMode
            : getParagraphMode(type, mapping, name);
        const supportsDataTemplate = isDataTemplateParagraphMode(type, effectiveMode);
        const usesEvidence = usesEvidenceParagraphMode(type, effectiveMode);
        const profileOptions = buildKeywordProfileOptions(template, selectedKeywordProfile);
        const profileKeywords = getKeywordProfileKeywords(template, selectedKeywordProfile);
        const semanticQuery = getSemanticRetrievalQueryForPlaceholder(template, mapping, name);
        const profileHelp = selectedKeywordProfile && profileKeywords.length
            ? `当前预设包包含 ${profileKeywords.length} 个关键词。`
            : '当前没有匹配到已存在的预设包，可以切换为自定义关键词。';
        const keywordChipsHtml = profileKeywords.length
            ? profileKeywords.map(keyword => `<span class="template-keyword-chip">${esc(keyword)}</span>`).join('')
            : '<span class="template-keyword-empty">当前预设包没有关键词</span>';
        const dataFieldsHtml = supportsDataTemplate
            ? renderDataTemplateFieldsEditor(dataTemplateFields)
            : '';
        const writingStructureHtml = `
            <label class="${effectiveMode === 'data_template_plus_evidence_ai' ? 'template-config-secondary-field' : ''}" data-placeholder-editor-section="writing">
                <span>${effectiveMode === 'data_template_plus_evidence_ai' ? '后续写作结构（一行一步）' : '写作结构（一行一步，可选）'}</span>
                <textarea data-placeholder-field="components.llm_writing.writing_structure" rows="5">${esc(writingStructureText)}</textarea>
            </label>
        `;
        return `
            ${typeSelectHtml}
            <section class="template-config-form-section template-config-form-section-compact" data-placeholder-editor-section="basic">
                <label>
                    <span>段落写作方式</span>
                    <select data-placeholder-field="mode">
                        <option value="data_template" ${effectiveMode === 'data_template' ? 'selected' : ''}>数据说明段落</option>
                        <option value="evidence_ai" ${effectiveMode === 'evidence_ai' ? 'selected' : ''}>根据材料撰写</option>
                        <option value="data_template_plus_evidence_ai" ${effectiveMode === 'data_template_plus_evidence_ai' ? 'selected' : ''}>数据说明 + 材料续写</option>
                    </select>
                </label>
                ${usesEvidence ? `
                <label>
                    <span>目标字数</span>
                    <input type="number" min="1" step="1" data-placeholder-field="target_words" value="${esc(mapping.target_words || inferDefaultTargetWords(name))}">
                </label>
                <label>
                    <span>最少 evidence/news 条数</span>
                    <input type="number" min="1" step="1" data-placeholder-field="min_news_count" value="${esc(minNewsCount)}">
                </label>
                ` : ''}
            </section>
            ${supportsDataTemplate ? `
                <label data-placeholder-editor-section="fixed_template">
                    <span>固定开头模板（Excel 数据填充）</span>
                    <textarea data-placeholder-field="components.data_template.template" rows="4">${esc(dataTemplate)}</textarea>
                </label>
            ` : ''}
            ${usesEvidence ? `
            <section class="template-retrieval-panel template-config-form-section" data-placeholder-editor-section="query">
                <div class="template-retrieval-header">
                    <strong>检索设置</strong>
                    <span>Hybrid = 语义 Query + 关键词</span>
                </div>
                <label class="template-semantic-query-field">
                    <span>语义 Query（用于相关内容召回）</span>
                    <textarea rows="3" data-placeholder-field="prompt.retrieval_query">${esc(semanticQuery)}</textarea>
                    <small>保存当前占位符后，会同步写回 Prompt 模板中的“检索 Query”。</small>
                </label>
            </section>
            ` : ''}
            ${dataFieldsHtml}
            ${usesEvidence ? writingStructureHtml : ''}
            ${usesEvidence ? `
            <section class="template-keyword-panel template-config-form-section" data-placeholder-editor-section="keywords">
                <div class="template-keyword-source-row">
                    <label>
                        <span>关键词来源</span>
                        <select data-placeholder-field="retrieval.keyword_mode">
                            <option value="profile" ${keywordMode === 'profile' ? 'selected' : ''}>预设包</option>
                            <option value="custom" ${keywordMode === 'custom' ? 'selected' : ''}>自定义</option>
                        </select>
                    </label>
                    ${keywordMode === 'profile' ? `
                        <div class="template-keyword-summary">
                            <span>当前预设包</span>
                            <strong>${esc(selectedKeywordProfile || '未选择预设包')}</strong>
                            <small>${profileKeywords.length} 个关键词</small>
                        </div>
                    ` : `
                        <div class="template-keyword-summary">
                            <span>当前关键词</span>
                            <strong>自定义关键词</strong>
                            <small>${splitLines(retrievalKeywords).length} 个关键词</small>
                        </div>
                    `}
                </div>
                ${keywordMode === 'profile' ? `
                    <details class="template-keyword-details">
                        <summary>更换预设包 / 查看关键词</summary>
                        <label>
                            <span>选择预设包</span>
                            <select data-placeholder-field="retrieval.keyword_profile_select">
                                ${profileOptions}
                            </select>
                        </label>
                        <div class="template-keyword-preview">
                            ${keywordChipsHtml}
                        </div>
                        <small class="template-keyword-mode-help">${esc(profileHelp)}</small>
                    </details>
                ` : `
                    <label class="template-custom-keywords">
                        <span>自定义关键词（一行一个）</span>
                        <textarea data-placeholder-field="retrieval.custom_keywords" rows="4">${esc(retrievalKeywords)}</textarea>
                        <small class="template-keyword-mode-help">保存后将使用这组关键词，不再引用预设包。</small>
                    </label>
                `}
            </section>
            ` : ''}
        `;
    }

    if (type === 'excel_commodity_market_review') {
        const dataSource = mapping.data_source || {};
        const kind = dataSource.kind || (name.includes('原油') ? 'oil' : 'gold');
        return `
            ${typeSelectHtml}
            <section class="template-fixed-excel-panel template-config-form-section" data-placeholder-editor-section="basic">
                <div>
                    <span>生成方式</span>
                    <strong>读取 Excel 周报数据，直接生成固定市场回顾</strong>
                </div>
                <label>
                    <span>Excel 文件</span>
                    <input type="text" data-placeholder-field="data_source.workbook" value="${esc(dataSource.workbook || '周报数据.xlsx')}">
                </label>
                <label>
                    <span>Sheet</span>
                    <input type="text" data-placeholder-field="data_source.sheet" value="${esc(dataSource.sheet || (kind === 'oil' ? '石油' : '黄金'))}">
                </label>
                <input type="hidden" data-placeholder-field="data_source.kind" value="${esc(kind)}">
            </section>
        `;
    }

    if (type === 'field') {
        return `${typeSelectHtml}${renderFieldPlaceholderEditor({ name, type, mapping, template })}`;
    }

    if (type === 'static_text') {
        return `${typeSelectHtml}${renderStaticTextPlaceholderEditor(mapping)}`;
    }

    if (type === 'table' || type === 'chart') {
        return `${typeSelectHtml}${renderTableOrChartPlaceholderEditor(type, mapping)}`;
    }

    return `${typeSelectHtml}<div class="empty-state compact">当前占位符没有常用字段，可打开高级配置查看</div>`;
}

function renderPlaceholderOutputShapeSelect(type, typeOptions) {
    const descriptions = {
        paragraph: '写一段话',
        field: '日期、数字、单个值',
        static_text: '不生成，只替换文字',
        table: '插入 Excel 区域',
        chart: '插入图表或图片'
    };
    return `
        <section class="template-config-form-section placeholder-purpose-section" data-placeholder-editor-section="basic">
            <div class="placeholder-purpose-header">
                <span>这个占位符要替换成什么？</span>
            </div>
            <input type="hidden" data-placeholder-field="type" data-placeholder-output-shape-select="true" value="${esc(type)}">
            <div class="placeholder-purpose-grid">
                ${typeOptions.map(option => {
                    const selected = type === option.value;
                    return `
                        <button
                            type="button"
                            class="placeholder-purpose-card ${selected ? 'selected' : ''}"
                            data-placeholder-output-shape-option="${esc(option.value)}"
                            aria-pressed="${selected ? 'true' : 'false'}"
                        >
                            <strong>${esc(option.label)}</strong>
                            <small>${esc(descriptions[option.value] || '保留当前旧类型')}</small>
                        </button>
                    `;
                }).join('')}
            </div>
        </section>
    `;
}

function renderFieldPlaceholderEditor({ name, type, mapping, template }) {
    if (isReportPeriodFieldPlaceholder(mapping.type || type, mapping, name)) {
        const field = mapping.field || inferReportPeriodField(name);
        const defaults = getEditableCommonDefaults(template);
        const reportPeriod = defaults.report_period || {};
        const reportDate = reportPeriod.report_date || getDefaultReportDate();
        const startDate = reportPeriod.start_date || getDefaultEvidenceStartDate(reportDate);
        const endDate = reportPeriod.end_date || reportDate;
        const fieldLabel = field === 'start_date' ? '开始日期' : '结束日期';
        const fieldValue = field === 'start_date' ? startDate : endDate;
        return `
            <section class="template-fixed-excel-panel template-report-period-panel template-config-form-section" data-placeholder-editor-section="basic">
                <div>
                    <span>生成方式</span>
                    <strong>按共用参数里的报告日期/数据使用范围填充</strong>
                </div>
                <label>
                    <span>日期字段</span>
                    <select data-placeholder-field="field">
                        <option value="start_date" ${field === 'start_date' ? 'selected' : ''}>开始日期</option>
                        <option value="end_date" ${field === 'end_date' ? 'selected' : ''}>结束日期</option>
                    </select>
                </label>
                <label>
                    <span>${fieldLabel}</span>
                    <input type="date" data-common-rule-field="report_period.${esc(field)}" value="${esc(fieldValue)}">
                    <small>这里修改后会同步到“证据来源与时间”的共用参数。</small>
                </label>
            </section>
        `;
    }
    if (isExcelFieldPlaceholder(mapping.type || type, mapping, name)) {
        const source = mapping.source && typeof mapping.source === 'object' ? mapping.source : {};
        const sourceKind = source.kind || getPlaceholderSourceKind(mapping.type || type, mapping, name) || 'excel_cell';
        const sourceRef = source.ref || (typeof mapping.source === 'string' ? mapping.source : '');
        return `
            <section class="template-fixed-excel-panel template-config-form-section" data-placeholder-editor-section="basic">
                <label>
                    <span>来源类型</span>
                    <select data-placeholder-field="source.kind">
                        <option value="excel_cell" ${sourceKind === 'excel_cell' ? 'selected' : ''}>Excel 单元格</option>
                        <option value="excel_range" ${sourceKind === 'excel_range' ? 'selected' : ''}>Excel 区域</option>
                    </select>
                </label>
                <label>
                    <span>Excel 来源 / 区域</span>
                    <input type="text" data-placeholder-field="source.ref" value="${esc(sourceRef)}">
                </label>
            </section>
        `;
    }
    return `
        <label data-placeholder-editor-section="basic">
            <span>手动值</span>
            <input type="text" data-placeholder-field="value" value="${esc(mapping.value || '')}">
        </label>
    `;
}

function renderStaticTextPlaceholderEditor(mapping = {}) {
    return `
        <label data-placeholder-editor-section="basic">
            <span>固定文案</span>
            <textarea data-placeholder-field="value" rows="3">${esc(mapping.value || '')}</textarea>
        </label>
    `;
}

function renderTableOrChartPlaceholderEditor(type, mapping = {}) {
    return `
        <section class="template-fixed-excel-panel template-config-form-section" data-placeholder-editor-section="basic">
            <div>
                <span>生成方式</span>
                <strong>${type === 'table' ? '由表格管线插入 Word 表格' : '由图表管线插入图表或图片'}</strong>
            </div>
            <label>
                <span>来源类型</span>
                <input type="text" data-placeholder-field="source.kind" value="${esc(mapping.source?.kind || (type === 'table' ? 'excel_range' : 'excel_chart'))}">
            </label>
            <label>
                <span>插入方式</span>
                <input type="text" data-placeholder-field="insert.mode" value="${esc(mapping.insert?.mode || 'replace_placeholder')}">
            </label>
        </section>
    `;
}

function getConfiguredSemanticRetrievalQueryForPlaceholder(template, mapping = {}, placeholderName = '') {
    if (String(mapping.prompt_retrieval_query || '').trim()) {
        return String(mapping.prompt_retrieval_query).trim();
    }
    const queryMode = String(mapping.query_mode || mapping.queryMode || '').trim();
    const querySource = String(mapping.query_source || mapping.querySource || '').trim();
    if (querySource && (!queryMode || queryMode === 'query_source')) {
        return querySource;
    }
    const promptName = mapping.prompt_template
        || resolvePromptTemplateName(placeholderName, template?.report_project);
    const promptSource = template?.report_project?.prompt_templates_source || '';
    const query = extractPromptTemplateLabel(promptSource, promptName, '检索 Query');
    if (query) return query;
    return '';
}

function getSemanticRetrievalQueryForPlaceholder(template, mapping = {}, placeholderName = '') {
    if (String(mapping.prompt_retrieval_query || '').trim()) {
        return String(mapping.prompt_retrieval_query).trim();
    }
    const queryMode = String(mapping.query_mode || mapping.queryMode || '').trim();
    const querySource = String(mapping.query_source || mapping.querySource || '').trim();
    if (queryMode === 'query_source' && querySource) {
        return `Query 来源：${querySource}`;
    }
    const promptName = mapping.prompt_template
        || resolvePromptTemplateName(placeholderName, template?.report_project);
    const promptSource = template?.report_project?.prompt_templates_source || '';
    const query = extractPromptTemplateLabel(promptSource, promptName, '检索 Query');
    if (query) return query;
    if (querySource) return `Query 来源：${querySource}`;
    return promptName || normalizePlaceholderName(placeholderName) || '未配置语义 Query';
}

function extractPromptTemplateLabel(source, promptName, label) {
    if (!source || !promptName) return '';
    const block = getPromptTemplateBlock(source, promptName);
    if (!block) return '';
    const stripped = stripMarkdownCodeFence(block);
    const pattern = new RegExp(`${escapeRegExp(label)}\\s*[：:]\\s*([\\s\\S]*?)(?=\\n\\s*[^\\n：:]{1,24}\\s*[：:]|\\n\\s*##\\s+|$)`);
    const match = stripped.match(pattern);
    return match ? match[1].trim() : '';
}

function getPromptTemplateBlock(source, promptName) {
    const pattern = new RegExp(`(^|\\n)##\\s+${escapeRegExp(promptName)}\\s*\\n([\\s\\S]*?)(?=\\n##\\s+|$)`);
    const match = String(source || '').match(pattern);
    return match ? match[2].trim() : '';
}

function stripMarkdownCodeFence(value) {
    return String(value || '')
        .replace(/^```[a-zA-Z0-9_-]*\s*\n/, '')
        .replace(/\n```\s*$/, '')
        .trim();
}

function getDataTemplateFields(mapping = {}, { includeDefaults = true } = {}) {
    const component = getDataTemplateComponent(mapping);
    const hasExplicitFields = Object.prototype.hasOwnProperty.call(component, 'fields');
    const componentFields = component.fields;
    const fields = componentFields && typeof componentFields === 'object'
        ? componentFields
        : {};
    return {
        ...(includeDefaults && !hasExplicitFields ? getDefaultDataTemplateFields(mapping) : {}),
        ...fields
    };
}

function getDefaultDataTemplateFields(mapping = {}) {
    const dataSource = mapping.data_source || {};
    const workbook = dataSource.workbook || '周报数据.xlsx';
    const domesticSheet = dataSource.domestic_sheet || '国内';
    const turnoverSheet = dataSource.turnover_sheet || '市场成交';
    return {
        market_trend: {
            label: 'market_trend',
            workbook,
            sheet: domesticSheet,
            range: 'B2:C6',
            rule: '读取主要指数周内涨跌幅，正负都有为“分化趋势”，全涨为“普涨趋势”，全跌为“调整趋势”'
        },
        index_performance: {
            label: 'index_performance',
            workbook,
            sheet: domesticSheet,
            range: 'B2:C6',
            rule: '按顺序读取指数名称和周内涨跌幅，生成“沪深300涨0.86%”这类列表'
        },
        avg_turnover: {
            label: 'avg_turnover',
            workbook,
            sheet: turnoverSheet,
            cell: 'B2',
            rule: '读取本周日均成交额，并格式化为“x.xx万亿”'
        },
        turnover_trend: {
            label: 'turnover_trend',
            workbook,
            sheet: turnoverSheet,
            range: 'B2:C2',
            rule: '比较本周日均成交额和上周日均成交额，生成“回升/回落/持平”'
        }
    };
}

function renderDataTemplateFieldsEditor(fields = {}) {
    const fieldEntries = Object.entries(fields || {});
    return `
        <div class="template-data-fields-panel" data-placeholder-editor-section="data_fields">
            <div class="template-data-fields-header">
                <div>
                    <strong>模板变量数据来源</strong>
                    <span>可填写显示名称；未填写时，固定开头直接显示变量名</span>
                </div>
                <button class="template-data-field-add btn btn-secondary" type="button" data-template-data-field-add>
                    <span>+</span> 添加变量
                </button>
            </div>
            <div class="template-data-fields-grid">
                ${fieldEntries.length ? fieldEntries.map(([fieldKey, field]) => {
                    const refValue = field.cell || field.range || '';
                    return `
                        <div class="template-data-field-row template-config-data-source-row" data-placeholder-editor-field="${esc(fieldKey)}" data-template-data-field-row data-template-data-field-key="${esc(fieldKey)}">
                            <label class="template-data-field-key">
                                <span>变量名</span>
                                <input type="text" data-data-template-field-key value="${esc(fieldKey)}" spellcheck="false">
                            </label>
                            <label>
                                <span>显示名称（可选）</span>
                                <input type="text" data-data-template-field-prop="display_name" value="${esc(field.display_name || '')}" placeholder="例如：市场走势">
                            </label>
                            <label>
                                <span>Excel 文件</span>
                                <input type="text" data-data-template-field-prop="workbook" value="${esc(field.workbook || '')}">
                            </label>
                            <label>
                                <span>Sheet</span>
                                <input type="text" data-data-template-field-prop="sheet" value="${esc(field.sheet || '')}">
                            </label>
                            <label>
                                <span>单元格/区域</span>
                                <input type="text" data-data-template-field-prop="ref" value="${esc(refValue)}">
                            </label>
                            <label class="template-data-field-rule">
                                <span>取数/计算规则</span>
                                <textarea data-data-template-field-prop="rule" rows="2">${esc(field.rule || '')}</textarea>
                            </label>
                            <button class="template-data-field-delete" type="button" data-template-data-field-delete="${esc(fieldKey)}" aria-label="删除 ${esc(fieldKey)}">
                                删除
                            </button>
                        </div>
                    `;
                }).join('') : `
                    <div class="template-data-fields-empty">
                        暂无变量。点击“添加变量”，然后在固定开头模板中用 {变量名} 引用。
                    </div>
                `}
            </div>
        </div>
    `;
}

function getDataTemplateFieldDisplayLabel(fieldKey = '', field = {}) {
    const key = String(fieldKey || '').trim();
    const displayName = String(field?.display_name || '').trim();
    return displayName || key;
}

function renderDataTemplatePreview(template, fields) {
    const source = String(template || '');
    const dataFields = fields && typeof fields === 'object' ? fields : {};
    return source.split(/(\{[A-Za-z_][A-Za-z0-9_-]*\})/g).map(part => {
        const match = /^\{([A-Za-z_][A-Za-z0-9_-]*)\}$/.exec(part);
        if (!match) return esc(part);
        const fieldKey = match[1];
        if (!Object.prototype.hasOwnProperty.call(dataFields, fieldKey)) return esc(part);
        const label = getDataTemplateFieldDisplayLabel(fieldKey, dataFields[fieldKey]);
        return `<span class="template-config-variable-chip" title="内部变量：${esc(fieldKey)}">${esc(label)}</span>`;
    }).join('');
}

function buildAdvancedPlaceholderFieldsHtml({
    name,
    type,
    mapping,
    isPromptLike,
    needsParam,
    usesQuerySource,
    promptParam,
    template
}) {
    return `
        <div class="template-advanced-help">
            这里仅保留少数底层来源与参数。占位符类型和段落写作方式请在“基础参数”中设置。
        </div>
        ${isPromptLike ? `
            ${usesQuerySource ? `
                <label>
                    <span>Query 来源</span>
                    <input type="text" data-placeholder-field="query_source" value="${esc(mapping.query_source || inferQuerySource(name, template.report_project))}">
                </label>
            ` : ''}
            ${needsParam ? `
                <label>
                    <span>参数 param</span>
                    <input type="text" data-placeholder-field="params.param" value="${esc(promptParam)}">
                </label>
            ` : ''}
        ` : ''}
        ${isExcelFieldPlaceholder(mapping.type || type, mapping, name) ? `
            <label>
                <span>Excel 来源 / 区域</span>
                <input type="text" data-placeholder-field="source.ref" value="${esc(typeof mapping.source === 'string' ? mapping.source : (mapping.source?.ref || ''))}">
            </label>
        ` : ''}
        ${type === 'static_text' ? `
            <label>
                <span>固定文案</span>
                <textarea data-placeholder-field="value" rows="3">${esc(mapping.value || '')}</textarea>
            </label>
        ` : ''}
    `;
}

function getEditablePlaceholderTypeOptions(currentType = '') {
    const primaryOptions = [
        { value: 'paragraph', label: '正文段落' },
        { value: 'field', label: '短字段' },
        { value: 'static_text', label: '固定文案' },
        { value: 'table', label: '表格' },
        { value: 'chart', label: '图表 / 图片' }
    ];
    if (!currentType || primaryOptions.some(option => option.value === currentType)) {
        return primaryOptions;
    }
    return [
        {
            value: currentType,
            label: `当前旧类型：${getPlaceholderTypeLabel(currentType)}`
        },
        ...primaryOptions
    ];
}

function getPlaceholderTypeLabel(type = '') {
    const labels = {
        paragraph: '正文段落',
        prompt: '正文段落（旧：AI 生成段落）',
        ai_text: '正文段落（旧：AI 生成段落）',
        composite_market_review: '正文段落（旧：Excel 固定开头 + AI 续写）',
        excel_commodity_market_review: 'Excel 固定市场回顾',
        field: '短字段',
        report_period: '短字段（旧：报告日期）',
        excel_cell: '短字段（旧：Excel 单元格取值）',
        excel_range: '短字段（旧：Excel 区域取值）',
        static_text: '固定文案',
        config_text: '固定文案（旧：可配置文案）',
        table: '表格',
        chart: '图表 / 图片',
        excel_chart: '图表 / 图片（旧：Excel 图表）'
    };
    return labels[type] || type || '未设置';
}

function isPlaceholderConfigEditorModalOpen() {
    const modal = document.getElementById('template-config-editor-modal');
    return Boolean(
        modal
        && !modal.classList.contains('hidden')
        && currentTemplateState.configEditModal?.action === 'placeholder'
    );
}

function refreshKeywordProfilePreview(input, template) {
    const profileName = input.value || '';
    const keywords = getKeywordProfileKeywords(template, profileName);
    const panel = input.closest('.template-keyword-panel');
    const summary = panel?.querySelector('.template-keyword-summary');
    const preview = panel?.querySelector('.template-keyword-preview');
    const help = panel?.querySelector('.template-keyword-mode-help');

    if (summary) {
        summary.innerHTML = `
            <span>当前预设包</span>
            <strong>${esc(profileName || '未选择预设包')}</strong>
            <small>${keywords.length} 个关键词</small>
        `;
    }
    if (preview) {
        preview.innerHTML = keywords.length
            ? keywords.map(keyword => `<span class="template-keyword-chip">${esc(keyword)}</span>`).join('')
            : '<span class="template-keyword-empty">当前预设包没有关键词</span>';
    }
    if (help) {
        help.textContent = profileName && keywords.length
            ? `当前预设包包含 ${keywords.length} 个关键词。`
            : '当前没有匹配到已存在的预设包，可以切换为自定义关键词。';
    }
}

function normalizeDataTemplateFieldKey(value, fallback = 'variable') {
    const cleaned = String(value || '')
        .trim()
        .replace(/[{}]/g, '')
        .replace(/\s+/g, '_')
        .replace(/[^A-Za-z0-9_]/g, '_')
        .replace(/_+/g, '_')
        .replace(/^_+|_+$/g, '');
    const withPrefix = cleaned && /^[A-Za-z_]/.test(cleaned)
        ? cleaned
        : `${fallback}_${cleaned || ''}`;
    return (withPrefix || fallback).replace(/_+$/g, '') || fallback;
}

function getUniqueDataTemplateFieldKey(baseKey, fields = {}) {
    const normalizedBase = normalizeDataTemplateFieldKey(baseKey || 'new_variable', 'variable');
    if (!Object.prototype.hasOwnProperty.call(fields, normalizedBase)) return normalizedBase;
    let index = 2;
    let nextKey = `${normalizedBase}_${index}`;
    while (Object.prototype.hasOwnProperty.call(fields, nextKey)) {
        index += 1;
        nextKey = `${normalizedBase}_${index}`;
    }
    return nextKey;
}

function collectDataTemplateFieldsFromForms(forms = []) {
    const rows = forms.flatMap(formEl => Array.from(formEl.querySelectorAll('[data-template-data-field-row]')));
    if (!rows.length) return null;
    const fields = {};
    rows.forEach(row => {
        const previousKey = row.dataset.templateDataFieldKey || 'variable';
        const requestedKey = row.querySelector('[data-data-template-field-key]')?.value || previousKey;
        const fieldKey = getUniqueDataTemplateFieldKey(requestedKey, fields);
        const field = { label: fieldKey };
        row.querySelectorAll('[data-data-template-field-prop]').forEach(input => {
            const prop = input.dataset.dataTemplateFieldProp;
            const value = input.value?.trim?.() || '';
            if (!value) return;
            if (prop === 'ref') {
                if (value.includes(':')) field.range = value;
                else field.cell = value;
            } else if (prop) {
                field[prop] = value;
            }
        });
        fields[fieldKey] = field;
    });
    return fields;
}

function refreshDataTemplateFieldToken(input) {
    const row = input.closest('[data-template-data-field-row]');
    const token = row?.querySelector('.template-config-token');
    if (!token) return;
    token.textContent = `{${normalizeDataTemplateFieldKey(input.value || row.dataset.templateDataFieldKey || 'variable')}}`;
}

function refreshDataTemplateFieldsEditor(template, activeField = '') {
    const wasModalOpen = isPlaceholderConfigEditorModalOpen();
    if (wasModalOpen) closeTemplateConfigEditorModal();
    renderSelectedPlaceholderDetail(template);
    renderSelectedSourceFragment(template);
    if (wasModalOpen) {
        window.requestAnimationFrame(() => openPlaceholderConfigEditorModal(template, 'data_fields', activeField));
    }
}

function bindDataTemplateFieldInputs(template) {
    const forms = [
        document.getElementById('template-placeholder-detail-form'),
        document.getElementById('template-config-editor-modal-body')
    ].filter(Boolean);
    forms.forEach(formEl => {
        formEl.querySelectorAll('[data-data-template-field-key], [data-data-template-field-prop]').forEach(input => {
            if (input.dataset.boundDataTemplateField) return;
            input.dataset.boundDataTemplateField = 'true';
            input.addEventListener('input', () => {
                if (input.matches('[data-data-template-field-key]')) refreshDataTemplateFieldToken(input);
                updateTemplateSourceFromPlaceholderDraft(template);
            });
            input.addEventListener('change', () => updateTemplateSourceFromPlaceholderDraft(template));
        });
        formEl.querySelectorAll('[data-template-data-field-add]').forEach(button => {
            if (button.dataset.boundDataTemplateFieldAdd) return;
            button.dataset.boundDataTemplateFieldAdd = 'true';
            button.addEventListener('click', () => {
                const activeField = currentTemplateState.configEditModal?.contentNode?.dataset?.activeEditorField || '';
                const result = collectSelectedPlaceholderDraft(template);
                if (!result) return;
                const fields = {
                    ...getDataTemplateFields(result.draft, { includeDefaults: false })
                };
                const newKey = getUniqueDataTemplateFieldKey('new_variable', fields);
                fields[newKey] = {
                    label: newKey,
                    workbook: '周报数据.xlsx',
                    sheet: '',
                    cell: '',
                    rule: ''
                };
                setComponentDraftField(result.draft, 'data_template', 'fields', fields);
                currentTemplateState.placeholderMappingDrafts[result.name] = result.draft;
                refreshDataTemplateFieldsEditor(template, activeField ? newKey : '');
            });
        });
        formEl.querySelectorAll('[data-template-data-field-delete]').forEach(button => {
            if (button.dataset.boundDataTemplateFieldDelete) return;
            button.dataset.boundDataTemplateFieldDelete = 'true';
            button.addEventListener('click', () => {
                const row = button.closest('[data-template-data-field-row]');
                if (row) row.remove();
                const result = collectSelectedPlaceholderDraft(template);
                if (!result) return;
                const remainingFields = collectDataTemplateFieldsFromForms(forms) || {};
                setComponentDraftField(result.draft, 'data_template', 'fields', remainingFields);
                currentTemplateState.placeholderMappingDrafts[result.name] = result.draft;
                refreshDataTemplateFieldsEditor(template);
            });
        });
    });
}

function bindPlaceholderDetailInputs(template) {
    document.querySelectorAll('#template-placeholder-detail-form [data-common-rule-field]').forEach(input => {
        if (input.dataset.boundPlaceholderCommonRule) return;
        input.dataset.boundPlaceholderCommonRule = 'true';
        const update = () => {
            collectCommonDefaultsDraft(template);
            renderSelectedSourceFragment(template);
        };
        input.addEventListener('input', update);
        input.addEventListener('change', update);
    });
    document.querySelectorAll('#template-placeholder-detail-form [data-placeholder-field], #template-advanced-placeholder-form [data-placeholder-field], #template-config-editor-modal-body [data-placeholder-field]').forEach(input => {
        if (input.dataset.boundPlaceholderField) return;
        input.dataset.boundPlaceholderField = 'true';
        input.addEventListener('input', () => updateTemplateSourceFromPlaceholderDraft(template));
        input.addEventListener('change', () => {
            updateTemplateSourceFromPlaceholderDraft(template);
            const field = input.dataset.placeholderField;
            if (field === 'retrieval.keyword_profile_select' && isPlaceholderConfigEditorModalOpen()) {
                refreshKeywordProfilePreview(input, template);
                renderSelectedSourceFragment(template);
                return;
            }
            if (field === 'retrieval.keyword_mode' && isPlaceholderConfigEditorModalOpen()) {
                const activeSection = currentTemplateState.configEditModal?.contentNode?.dataset?.activeEditorSection || 'keywords';
                const activeField = currentTemplateState.configEditModal?.contentNode?.dataset?.activeEditorField || '';
                closeTemplateConfigEditorModal();
                window.requestAnimationFrame(() => openPlaceholderConfigEditorModal(template, activeSection, activeField));
                return;
            }
            if (field === 'type' && isPlaceholderConfigEditorModalOpen()) {
                const activeSection = currentTemplateState.configEditModal?.contentNode?.dataset?.activeEditorSection || 'basic';
                const activeField = currentTemplateState.configEditModal?.contentNode?.dataset?.activeEditorField || '';
                closeTemplateConfigEditorModal();
                window.requestAnimationFrame(() => openPlaceholderConfigEditorModal(template, activeSection, activeField));
                return;
            }
            if (field === 'mode' && isPlaceholderConfigEditorModalOpen()) {
                const draftName = normalizePlaceholderName(currentTemplateState.selectedPlaceholderName);
                if (draftName) {
                    currentTemplateState.placeholderMappingDrafts = currentTemplateState.placeholderMappingDrafts || {};
                    const prev = currentTemplateState.placeholderMappingDrafts[draftName] || getSelectedPlaceholderMapping(template) || {};
                    currentTemplateState.placeholderMappingDrafts[draftName] = { ...prev, mode: input.value };
                }
                const activeSection = currentTemplateState.configEditModal?.contentNode?.dataset?.activeEditorSection || 'basic';
                const activeField = currentTemplateState.configEditModal?.contentNode?.dataset?.activeEditorField || '';
                closeTemplateConfigEditorModal();
                window.requestAnimationFrame(() => openPlaceholderConfigEditorModal(template, activeSection, activeField));
                return;
            }
            if (field === 'type' || field === 'mode' || field === 'retrieval.keyword_mode' || field === 'retrieval.keyword_profile_select') {
                renderSelectedPlaceholderDetail(template);
                renderSelectedSourceFragment(template);
            }
        });
    });
    bindPlaceholderPurposeCards(template);
    bindDataTemplateFieldInputs(template);
}

function bindPlaceholderPurposeCards(template) {
    document.querySelectorAll('[data-placeholder-output-shape-option]').forEach(button => {
        if (button.dataset.boundPlaceholderPurposeCard) return;
        button.dataset.boundPlaceholderPurposeCard = 'true';
        button.addEventListener('click', () => {
            const section = button.closest('.placeholder-purpose-section');
            const input = section?.querySelector('[data-placeholder-output-shape-select="true"]');
            const value = button.dataset.placeholderOutputShapeOption || '';
            if (!input || !value || input.value === value) return;
            const oldCard = section.querySelector('[data-placeholder-output-shape-option].selected');
            const oldLabel = oldCard?.querySelector('strong')?.textContent || '当前类型';
            const newLabel = button.querySelector('strong')?.textContent || value;
            if (!confirm(`确定要将占位符类型从"${oldLabel}"切换为"${newLabel}"吗？\n\n已配置的内容不会丢失，切换回来可以恢复。`)) return;
            input.value = value;
            input.dispatchEvent(new Event('input', { bubbles: true }));
            const draftName = normalizePlaceholderName(currentTemplateState.selectedPlaceholderName);
            if (draftName) {
                currentTemplateState.placeholderMappingDrafts = currentTemplateState.placeholderMappingDrafts || {};
                const prev = currentTemplateState.placeholderMappingDrafts[draftName] || getSelectedPlaceholderMapping(template) || {};
                currentTemplateState.placeholderMappingDrafts[draftName] = { ...prev, type: getCanonicalPlaceholderType(value, prev) || value };
            }
            if (isPlaceholderConfigEditorModalOpen()) {
                const activeSection = currentTemplateState.configEditModal?.contentNode?.dataset?.activeEditorSection || 'basic';
                const activeField = currentTemplateState.configEditModal?.contentNode?.dataset?.activeEditorField || '';
                closeTemplateConfigEditorModal();
                window.requestAnimationFrame(() => openPlaceholderConfigEditorModal(template, activeSection, activeField));
            } else {
                input.dispatchEvent(new Event('change', { bubbles: true }));
            }
            section.querySelectorAll('[data-placeholder-output-shape-option]').forEach(optionButton => {
                const selected = optionButton === button;
                optionButton.classList.toggle('selected', selected);
                optionButton.setAttribute('aria-pressed', selected ? 'true' : 'false');
            });
            renderSelectedSourceFragment(template);
        });
    });
}

function collectSelectedPlaceholderDraft(template) {
    const name = normalizePlaceholderName(currentTemplateState.selectedPlaceholderName);
    if (!name) return null;

    const forms = [
        document.getElementById('template-placeholder-detail-form'),
        document.getElementById('template-advanced-placeholder-form'),
        document.getElementById('template-config-editor-modal-body')
    ].filter(Boolean);
    const existing = getSelectedPlaceholderMapping(template) || {};
    const draft = { ...existing };
    const dataTemplateFieldsDraft = collectDataTemplateFieldsFromForms(forms);
    const keywordModeInput = document.querySelector('[data-placeholder-field="retrieval.keyword_mode"]');
    const keywordProfileInput = document.querySelector('[data-placeholder-field="retrieval.keyword_profile_select"]');
    const customKeywordsInput = document.querySelector('[data-placeholder-field="retrieval.custom_keywords"]');
    forms.forEach(formEl => formEl.querySelectorAll('[data-placeholder-field]').forEach(input => {
        const field = input.dataset.placeholderField;
        const value = input.value?.trim?.() || '';
        if (field === 'params.param') {
            draft.params = value ? { ...(draft.params || {}), param: value } : {};
        } else if (field === 'field') {
            if (value) draft.field = value;
            else delete draft.field;
        } else if (field === 'type') {
            draft.type = getCanonicalPlaceholderType(value, draft) || value;
        } else if (field === 'mode') {
            if (isParagraphMode(value)) {
                draft.type = 'paragraph';
                draft.mode = value;
            } else {
                delete draft.mode;
            }
        } else if (
            field === 'retrieval.keyword_mode'
            || field === 'retrieval.keyword_profile_select'
            || field === 'retrieval.custom_keywords'
        ) {
            return;
        } else if (field === 'prompt.retrieval_query') {
            draft.prompt_retrieval_query = value;
        } else if (field === 'retrieval.keyword_profile') {
            const rawDraftType = draft.type || '';
            const draftType = getCanonicalPlaceholderType(rawDraftType, draft) || inferPlaceholderType(name);
            const draftMode = getParagraphMode(rawDraftType || draftType, draft, name);
            if (shouldStoreParagraphRetrievalInLlmComponent(draftType, draftMode)) {
                setLlmWritingRetrievalDraftField(draft, 'keyword_profile', value || null);
            } else if (value) {
                draft.retrieval = { ...(draft.retrieval || {}), keyword_profile: value };
            } else if (draft.retrieval) {
                delete draft.retrieval.keyword_profile;
                if (!Object.keys(draft.retrieval).length) delete draft.retrieval;
            }
        } else if (field === 'retrieval.keywords') {
            const keywords = splitDelimitedList(value);
            const rawDraftType = draft.type || '';
            const draftType = getCanonicalPlaceholderType(rawDraftType, draft) || inferPlaceholderType(name);
            const draftMode = getParagraphMode(rawDraftType || draftType, draft, name);
            if (shouldStoreParagraphRetrievalInLlmComponent(draftType, draftMode)) {
                setLlmWritingRetrievalDraftField(draft, 'keywords', keywords);
            } else if (keywords.length) {
                draft.retrieval = { ...(draft.retrieval || {}), keywords };
            } else if (draft.retrieval) {
                delete draft.retrieval.keywords;
                if (!Object.keys(draft.retrieval).length) delete draft.retrieval;
            }
        } else if (field.startsWith('components.data_template.fields.')) {
            return;
        } else if (field === 'components.data_template.template') {
            setComponentDraftField(draft, 'data_template', 'template', value);
        } else if (field === 'components.llm_writing.writing_structure') {
            const structure = splitLines(value);
            const rawDraftType = draft.type || '';
            const draftType = getCanonicalPlaceholderType(rawDraftType, draft) || inferPlaceholderType(name);
            const draftMode = getParagraphMode(rawDraftType || draftType, draft, name);
            if (shouldStoreParagraphRetrievalInLlmComponent(draftType, draftMode)) {
                setComponentDraftField(draft, 'llm_writing', 'writing_structure', structure);
            } else if (structure.length) {
                draft.writing_structure = structure;
            } else {
                delete draft.writing_structure;
            }
        } else if (field.startsWith('data_source.')) {
            const key = field.split('.')[1];
            draft.data_source = { ...(draft.data_source || {}), [key]: value };
        } else if (field.startsWith('source.')) {
            const key = field.split('.')[1];
            draft.source = { ...((draft.source && typeof draft.source === 'object') ? draft.source : {}), [key]: value };
        } else if (field.startsWith('insert.')) {
            const key = field.split('.')[1];
            draft.insert = { ...(draft.insert || {}), [key]: value };
        } else if (field === 'target_words' || field === 'max_words' || field === 'min_news_count') {
            draft[field] = value === '' ? null : Number(value);
        } else if (field) {
            draft[field] = value;
        }
    }));
    if (dataTemplateFieldsDraft) {
        setComponentDraftField(draft, 'data_template', 'fields', dataTemplateFieldsDraft);
    }
    if (keywordModeInput) {
        currentTemplateState.keywordModeDrafts = currentTemplateState.keywordModeDrafts || {};
        currentTemplateState.keywordModeDrafts[name] = keywordModeInput.value;
        applyKeywordModeDraft(
            template,
            draft,
            name,
            keywordModeInput.value,
            keywordProfileInput?.value || '',
            customKeywordsInput?.value || ''
        );
    }
    draft.title = draft.title || inferPlaceholderTitle(name);
    draft.type = getCanonicalPlaceholderType(draft.type, draft) || inferPlaceholderType(name);
    if (draft.type === 'paragraph') {
        draft.mode = isParagraphMode(draft.mode)
            ? draft.mode
            : getParagraphMode(draft.type, draft, name);
    }

    currentTemplateState.placeholderMappingDrafts = currentTemplateState.placeholderMappingDrafts || {};
    currentTemplateState.placeholderMappingDrafts[name] = draft;
    return { name, draft };
}

function getDataTemplateComponent(mapping = {}) {
    return getPlaceholderComponent(mapping, 'data_template');
}

function getLlmWritingComponent(mapping = {}) {
    return getPlaceholderComponent(mapping, 'llm_writing');
}

function getPlaceholderComponent(mapping = {}, componentType = '') {
    const components = Array.isArray(mapping.components) ? mapping.components : [];
    return components.find(component => component?.type === componentType) || {};
}

function setComponentDraftField(draft, componentType, field, value) {
    const components = Array.isArray(draft.components) ? [...draft.components] : [];
    let index = components.findIndex(component => component?.type === componentType);
    if (index < 0) {
        components.push({
            name: componentType === 'data_template' ? '市场表现与交易面' : '市场热点与趋势判断',
            type: componentType
        });
        index = components.length - 1;
    }
    const component = { ...(components[index] || {}), type: componentType };
    if (Array.isArray(value) ? value.length : Boolean(value)) {
        component[field] = value;
    } else {
        delete component[field];
    }
    components[index] = component;
    draft.components = components;
}

function setDataTemplateFieldDraft(draft, path, value) {
    const parts = path.split('.');
    const fieldKey = parts[3];
    const property = parts[4];
    if (!fieldKey || !property) return;

    const component = {
        ...getDataTemplateComponent(draft),
        fields: {
            ...getDataTemplateFields(draft, { includeDefaults: false })
        }
    };
    const field = { ...(component.fields[fieldKey] || {}) };
    const nextValue = String(value || '').trim();
    if (property === 'ref') {
        delete field.cell;
        delete field.range;
        if (nextValue) {
            if (nextValue.includes(':')) field.range = nextValue;
            else field.cell = nextValue;
        }
    } else if (nextValue) {
        field[property] = nextValue;
    } else {
        delete field[property];
    }
    field.label = field.label || fieldKey;
    component.fields[fieldKey] = field;
    setComponentDraftField(draft, 'data_template', 'fields', component.fields);
}

function setLlmWritingRetrievalDraftField(draft, field, value) {
    const components = Array.isArray(draft.components) ? [...draft.components] : [];
    let index = components.findIndex(component => component?.type === 'llm_writing');
    if (index < 0) {
        components.push({ name: '市场热点与趋势判断', type: 'llm_writing' });
        index = components.length - 1;
    }
    const component = { ...(components[index] || {}), type: 'llm_writing' };
    const retrieval = { ...(component.retrieval || {}) };
    if (Array.isArray(value) ? value.length : Boolean(value)) {
        retrieval[field] = value;
    } else {
        delete retrieval[field];
    }
    component.retrieval = retrieval;
    if (!Object.keys(retrieval).length) delete component.retrieval;
    components[index] = component;
    draft.components = components;
    if (draft.retrieval) {
        delete draft.retrieval[field];
        if (!Object.keys(draft.retrieval).length) delete draft.retrieval;
    }
}

function applyKeywordModeDraft(template, draft, placeholderName, mode, profileName, customKeywordsText) {
    const rawDraftType = draft.type || '';
    const draftType = getCanonicalPlaceholderType(rawDraftType, draft) || inferPlaceholderType(placeholderName);
    const paragraphMode = getParagraphMode(rawDraftType || draftType, draft, placeholderName);
    const storeInLlmComponent = shouldStoreParagraphRetrievalInLlmComponent(draftType, paragraphMode);
    const nextRetrieval = storeInLlmComponent
        ? { ...(getLlmWritingComponent(draft).retrieval || {}) }
        : { ...(draft.retrieval || {}) };

    if (mode === 'profile') {
        const selectedProfile = String(profileName || '').trim();
        if (selectedProfile) {
            nextRetrieval.keyword_profile = selectedProfile;
        } else {
            delete nextRetrieval.keyword_profile;
        }
        delete nextRetrieval.keywords;
        delete nextRetrieval.must_any;
        delete nextRetrieval.query_terms;
    } else {
        const keywords = splitLines(customKeywordsText);
        if (keywords.length) {
            nextRetrieval.keywords = keywords;
        } else {
            const seedProfile = nextRetrieval.keyword_profile || profileName;
            const profileKeywords = nextRetrieval.keyword_profile
                ? getKeywordProfileKeywords(template, seedProfile)
                : [];
            if (profileKeywords.length) {
                nextRetrieval.keywords = profileKeywords;
            } else {
                delete nextRetrieval.keywords;
            }
        }
        delete nextRetrieval.keyword_profile;
        delete nextRetrieval.keyword_profile_source;
        delete nextRetrieval.keyword_profile_needs_review;
    }

    if (storeInLlmComponent) {
        setLlmWritingRetrievalDraft(draft, nextRetrieval);
    } else if (Object.keys(nextRetrieval).length) {
        draft.retrieval = nextRetrieval;
    } else {
        delete draft.retrieval;
    }
}

function setLlmWritingRetrievalDraft(draft, retrieval) {
    const components = Array.isArray(draft.components) ? [...draft.components] : [];
    let index = components.findIndex(component => component?.type === 'llm_writing');
    if (index < 0) {
        components.push({ name: '市场热点与趋势判断', type: 'llm_writing' });
        index = components.length - 1;
    }
    const component = { ...(components[index] || {}), type: 'llm_writing' };
    if (retrieval && Object.keys(retrieval).length) {
        component.retrieval = retrieval;
    } else {
        delete component.retrieval;
    }
    components[index] = component;
    draft.components = components;
    delete draft.retrieval;
}

function getKeywordProfileCatalog(template) {
    const profiles = template?.report_project?.keyword_profiles || currentTemplateState.selectedReportProject?.keyword_profiles || {};
    return profiles && typeof profiles === 'object' ? profiles : {};
}

function getKeywordProfileNames(template) {
    return Object.keys(getKeywordProfileCatalog(template)).sort((a, b) => a.localeCompare(b, 'zh-Hans-CN'));
}

function getSelectedKeywordProfileName(template, mapping = {}, placeholderName = '') {
    const configured = mapping.retrieval?.keyword_profile
        || getLlmWritingComponent(mapping).retrieval?.keyword_profile
        || '';
    if (configured) return configured;
    const normalizedPlaceholder = normalizePlaceholderName(placeholderName);
    const names = getKeywordProfileNames(template);
    return names.includes(normalizedPlaceholder) ? normalizedPlaceholder : '';
}

function getKeywordProfileKeywords(template, profileName = '') {
    const profile = getKeywordProfileCatalog(template)?.[profileName];
    return Array.isArray(profile?.keywords) ? profile.keywords : [];
}

function inferKeywordMode(template, mapping = {}, placeholderName = '') {
    const normalizedPlaceholder = normalizePlaceholderName(placeholderName);
    const modeDraft = currentTemplateState.keywordModeDrafts?.[normalizedPlaceholder];
    if (modeDraft === 'profile' || modeDraft === 'custom') return modeDraft;

    const selectedProfile = getSelectedKeywordProfileName(template, mapping, placeholderName);
    if (selectedProfile && getKeywordProfileCatalog(template)?.[selectedProfile]) {
        return 'profile';
    }
    return getExplicitPlaceholderRetrievalKeywords(mapping).length ? 'custom' : 'profile';
}

function getKeywordEditorText(template, mapping = {}, placeholderName = '', keywordMode = 'profile', profileName = '') {
    if (keywordMode === 'profile') {
        return getKeywordProfileKeywords(template, profileName).join('\n');
    }
    const explicitKeywords = getExplicitPlaceholderRetrievalKeywords(mapping);
    if (explicitKeywords.length) return explicitKeywords.join('\n');
    const profileKeywords = getKeywordProfileKeywords(template, profileName);
    return (profileKeywords.length ? profileKeywords : inferPlaceholderKeywords(placeholderName)).join('\n');
}

function buildKeywordProfileOptions(template, selectedProfile = '') {
    const names = getKeywordProfileNames(template);
    const optionNames = selectedProfile && !names.includes(selectedProfile)
        ? [selectedProfile, ...names]
        : names;
    if (!optionNames.length) {
        return '<option value="">没有可用预设包</option>';
    }
    return optionNames.map(name => `
        <option value="${esc(name)}" ${selectedProfile === name ? 'selected' : ''}>${esc(name)}</option>
    `).join('');
}

function getPlaceholderRetrievalKeywords(mapping, placeholderName = '') {
    const retrieval = mapping?.retrieval || {};
    const componentRetrieval = getLlmWritingComponent(mapping)?.retrieval || {};
    const queryTerms = retrieval.query_terms || {};
    const keywords = retrieval.keywords
        || queryTerms.must_any
        || retrieval.must_any
        || componentRetrieval.keywords
        || [];
    if (Array.isArray(keywords) && keywords.length) return keywords;
    return inferPlaceholderKeywords(placeholderName);
}

function getExplicitPlaceholderRetrievalKeywords(mapping = {}) {
    const retrieval = mapping?.retrieval || {};
    const componentRetrieval = getLlmWritingComponent(mapping)?.retrieval || {};
    const queryTerms = retrieval.query_terms || componentRetrieval.query_terms || {};
    const keywords = retrieval.keywords
        || componentRetrieval.keywords
        || queryTerms.must_any
        || retrieval.must_any
        || componentRetrieval.must_any
        || [];
    return Array.isArray(keywords) ? keywords : [];
}

function splitLines(value) {
    return String(value || '')
        .split(/\n+/)
        .map(item => item.trim())
        .filter(Boolean);
}

function isPromptPlaceholderType(type, mapping = {}) {
    if (type === 'excel_commodity_market_review') return false;
    if (isParagraphPlaceholderType(type, mapping)) {
        return usesEvidenceParagraphMode(type, getParagraphMode(type, mapping));
    }
    return ['prompt', 'ai_text', 'composite_market_review'].includes(type)
        || Boolean(mapping.prompt_template)
        || Boolean(mapping.query_source)
        || Boolean(mapping.retrieval)
        || Boolean(mapping.components)
        || Boolean(mapping.target_words)
        || Boolean(mapping.max_words);
}

function splitDelimitedList(value) {
    return String(value || '')
        .split(/[\n,，、；;]+/)
        .map(item => item.trim())
        .filter(Boolean);
}

function inferPlaceholderKeywords(name) {
    const normalized = normalizePlaceholderName(name);
    const keywordMap = {
        'A股市场回顾': ['A股', '市场热点', '板块轮动', '成交额', '风格切换'],
        '中国宏观': ['货币政策', '财政政策', '宏观经济', '产业政策', '就业'],
        '人工智能': ['CPO', '算力', '人工智能', '大模型', '先进封装'],
        '电子': ['半导体', '芯片', '集成电路', '消费电子', '汽车电子'],
        '航天': ['商业航天', '卫星互联网', '火箭', '低空经济', '太空经济'],
        '电力设备新能源': ['光伏', '风电', '储能', '新能源车', '锂电池'],
        '消费': ['消费复苏', '促消费', '食品饮料', '服务消费', '零售'],
        '金融地产': ['货币政策', '信贷', '资本市场', '房地产政策', '银行'],
        '医药生物': ['创新药', '医疗器械', 'CRO', 'CDMO', '生物医药'],
        '海外市场': ['美联储', '欧洲央行', '日本央行', '利率', '汇率'],
        '美国': ['美联储', '美国经济', '美股', '美债', '美元'],
        '欧洲': ['欧洲央行', '欧元区', '德国', '法国', '欧股'],
        '日本': ['日本央行', '日元', '日本股市', '通胀', '利率'],
        '美国新闻': ['美联储', '美债', '美元', '美股', '关税'],
        '欧洲新闻': ['欧洲央行', '欧元', '欧债', '德国', '法国'],
        '港股科技': ['港股科技', '互联网平台', '半导体', '生物医药', '南向资金'],
        '港股央企红利': ['央企红利', '高股息', '港股通', '银行', '有色金属'],
        '黄金': ['黄金', '美联储', '实际利率', '避险', '央行购金'],
        '黄金市场回顾': ['黄金', '美联储', '实际利率', '避险', '央行购金'],
        '原油': ['原油', 'OPEC', '供需', '地缘风险', '库存'],
        '原油市场回顾': ['原油', 'OPEC', '供需', '地缘风险', '库存']
    };
    return keywordMap[normalized] || [];
}

function getEditablePlaceholderMappings(template) {
    const mappings = getCurrentPlaceholderMappings(template);
    Object.entries(currentTemplateState.placeholderMappingDrafts || {}).forEach(([name, draft]) => {
        if (draft) mappings.set(name, draft);
    });
    const selectedDraft = collectSelectedPlaceholderDraft(template);
    if (selectedDraft) {
        mappings.set(selectedDraft.name, selectedDraft.draft);
    }
    return mappings;
}

function updateTemplateSourceFromPlaceholderDraft(template) {
    renderSelectedSourceFragment(template);
}

function renderSelectedSourceFragment(template) {
    const sourceEditor = document.getElementById('template-source-editor');
    if (!sourceEditor) return;

    const source = getTemplateWorkbenchSource(template);
    const selectedName = normalizePlaceholderName(currentTemplateState.selectedPlaceholderName);
    const sourceKindLabel = document.getElementById('template-source-kind-label');

    sourceEditor.dataset.sourceKind = source.sourceKind;
    sourceEditor.dataset.placeholderName = selectedName;

    sourceEditor.dataset.promptTemplateName = '';
    sourceEditor.value = buildSelectedPlaceholderYamlFragment(template, getEditablePlaceholderMappings(template));
    if (sourceKindLabel) {
        sourceKindLabel.textContent = selectedName
            ? `${source.label}：{{${selectedName}}}`
            : source.label;
    }
}

function buildUpdatedReportConfigSource(template, mappings) {
    const projectSource = normalizeUnifiedReportConfigSource(
        template.report_project?.report_config_source || ''
    );
    const defaultsBlock = buildDefaultsBlock(collectCommonDefaultsDraft(template));
    const placeholdersBlock = buildPlaceholderMappingsBlock(template, mappings);
    if (!projectSource.trim()) {
        return buildPlaceholderMappingConfigYaml(template, mappings);
    }
    let updatedSource = projectSource;
    if (/(^|\n)defaults:\n/.test(updatedSource)) {
        updatedSource = updatedSource.replace(
            /(^|\n)defaults:\n[\s\S]*?(?=\n\S|\s*$)/,
            `$1${defaultsBlock}`
        );
    } else {
        updatedSource = insertTopLevelBlockBefore(updatedSource, defaultsBlock, ['charts:', 'placeholders:']);
    }
    if (/(^|\n)placeholders:\n/.test(updatedSource)) {
        return updatedSource.replace(
            /(^|\n)placeholders:\n[\s\S]*?(?=\n\S|\s*$)/,
            `$1${placeholdersBlock}`
        );
    }
    return `${updatedSource.trimEnd()}\n${placeholdersBlock}`;
}

function normalizeUnifiedReportConfigSource(source) {
    return removeTopLevelYamlBlock(String(source || ''), 'sections').trimEnd();
}

function removeTopLevelYamlBlock(source, key) {
    const pattern = new RegExp(`(^|\\n)${escapeRegExp(key)}:\\s*(?:\\n[\\s\\S]*?)?(?=\\n\\S|$)`, 'g');
    return source.replace(pattern, '$1');
}

function insertTopLevelBlockBefore(source, block, anchors) {
    const lines = String(source || '').split('\n');
    const anchorIndex = lines.findIndex(line => anchors.includes(line.trim()));
    if (anchorIndex < 0) return `${source.trimEnd()}\n${block}`;
    return [
        ...lines.slice(0, anchorIndex),
        block,
        ...lines.slice(anchorIndex)
    ].join('\n');
}

function buildSourceContentForSave(template, sourceKind, editorValue) {
    if (sourceKind === 'prompt_templates') {
        return buildUpdatedPromptTemplatesSource(template, editorValue);
    }
    return buildUpdatedReportConfigSource(template, getEditablePlaceholderMappings(template));
}

function buildUpdatedPromptTemplatesSource(template, promptFragment) {
    const source = shouldUsePromptTemplateLibraryDraft(template)
        ? buildPromptTemplateLibraryMarkdown(template)
        : (template.report_project?.prompt_templates_source || buildPromptTemplateLibraryMarkdown(template));
    const promptName = document.getElementById('template-source-editor')?.dataset.promptTemplateName
        || getSelectedPromptTemplateName(template);
    const fragment = String(promptFragment || '').trimEnd();
    if (!promptName || !fragment.trim()) return source;

    const normalizedFragment = fragment.startsWith('## ')
        ? fragment
        : `## ${promptName}\n${fragment}`;
    const blockPattern = new RegExp(`(^|\\n)##\\s+${escapeRegExp(promptName)}\\s*\\n[\\s\\S]*?(?=\\n##\\s+|$)`);
    if (blockPattern.test(source)) {
        return source.replace(blockPattern, `$1${normalizedFragment}\n`);
    }
    return `${source.trimEnd()}\n\n${normalizedFragment}\n`;
}

function buildUpdatedPromptTemplatesSourceFromQuery(template, mapping, placeholderName) {
    const query = String(mapping?.prompt_retrieval_query || '').trim();
    if (!query) return null;
    const promptName = mapping.prompt_template
        || resolvePromptTemplateName(placeholderName, template?.report_project);
    if (!promptName) return null;

    const source = template?.report_project?.prompt_templates_source || buildPromptTemplateLibraryMarkdown(template);
    const existingBlock = getPromptTemplateBlock(source, promptName);
    if (!existingBlock) {
        const fragment = [
            `## ${promptName}`,
            '',
            '```text',
            `检索 Query：${query}`,
            '',
            '写作要求：',
            '```'
        ].join('\n');
        return `${source.trimEnd()}\n\n${fragment}\n`;
    }

    const nextBlock = replacePromptTemplateLabel(existingBlock, '检索 Query', query);
    const blockPattern = new RegExp(`(^|\\n)##\\s+${escapeRegExp(promptName)}\\s*\\n[\\s\\S]*?(?=\\n##\\s+|$)`);
    return source.replace(blockPattern, (match, prefix = '') => `${prefix}## ${promptName}\n\n${nextBlock.trim()}\n`);
}

function replacePromptTemplateLabel(block, label, value) {
    const rawBlock = String(block || '').trim();
    const hasFence = /^```[a-zA-Z0-9_-]*\s*\n/.test(rawBlock);
    const body = stripMarkdownCodeFence(rawBlock);
    const pattern = new RegExp(`(${escapeRegExp(label)}\\s*[：:]\\s*)([\\s\\S]*?)(?=\\n\\s*[^\\n：:]{1,24}\\s*[：:]|$)`);
    const nextBody = pattern.test(body)
        ? body.replace(pattern, (match, prefix = '') => `${prefix}${value}`)
        : `${label}：${value}\n\n${body}`.trim();
    if (!hasFence) return nextBody;
    const fenceMatch = rawBlock.match(/^```([a-zA-Z0-9_-]*)/);
    const fenceLang = fenceMatch?.[1] || 'text';
    return `\`\`\`${fenceLang}\n${nextBody.trim()}\n\`\`\``;
}

function renderTemplateExcelMapping(template, templateName) {
    const container = document.getElementById('template-excel-mapping');
    if (!container) return;

    const rows = buildExcelMappingRows(template);

    if (!rows.length) {
        container.innerHTML = '<div class="empty-state compact">上传或绑定 Excel 底稿后配置数据槽</div>';
        return;
    }

    container.innerHTML = `
        <div class="mapping-row mapping-head"><span>数据槽</span><span>来源</span><span>用途</span></div>
        ${rows.map(row => `
            <div class="mapping-row">
                <span>${esc(row.slot)}</span>
                <code>${esc(row.source)}</code>
                <span>${esc(row.usage)}</span>
            </div>
        `).join('')}
    `;
}

function buildExcelMappingRows(template) {
    const project = template.report_project || null;
    const projectSheets = project?.excel_sheets;
    if (Array.isArray(projectSheets) && projectSheets.length) {
        return projectSheets.map(sheet => ({
            slot: sheet.name,
            source: `${sheet.name}!${sheet.dimension || '未识别范围'}`,
            usage: `${sheet.nonempty_count || 0} 个非空单元格`
        }));
    }
    if (!template.has_excel) return [];
    return [
        { slot: 'report_date', source: 'Excel!A1', usage: '标题日期' },
        { slot: 'summary_table', source: 'Excel!A1:F20', usage: '表格占位符' },
        { slot: 'chart_1', source: '第 1 个图表', usage: '图表占位符' }
    ];
}

function buildTemplateValidationChecks(template, sections, placeholders) {
    const placeholderMappings = getCurrentPlaceholderMappings(template);
    const effectivePlaceholderMappings = (placeholders || [])
        .map(placeholderName => normalizePlaceholderName(placeholderName))
        .filter(Boolean)
        .map(placeholderName => ({
            placeholderName,
            mapping: getEffectivePlaceholderMapping(template, placeholderName)
        }));
    const firstUnmappedPlaceholder = effectivePlaceholderMappings.find(({ placeholderName }) =>
        !placeholderMappings.has(placeholderName)
    )?.placeholderName;
    const allPlaceholdersMapped = placeholders.length === 0
        || !firstUnmappedPlaceholder;
    const hasPromptMapping = [...placeholderMappings.values()].some(mapping => mapping.prompt_template)
        || effectivePlaceholderMappings.some(({ mapping }) => mapping?.prompt_retrieval_query);
    const hasExcelMapping = buildExcelMappingRows(template).length > 0;
    const hasRuleConfig = sections.some(section =>
        section.evidence_policy
        || section.forbidden_terms?.length
        || section.investment_advice_policy
    ) || Boolean(template.report_project);

    return [
        {
            label: 'Word 占位符均有 section 映射',
            ok: allPlaceholdersMapped,
            action: 'open-advanced',
            actionTarget: 'template-placeholder-map',
            actionLabel: '配置占位符',
            placeholderName: firstUnmappedPlaceholder ? normalizePlaceholderName(firstUnmappedPlaceholder) : ''
        },
        {
            label: 'AI 文本 section 已配置 prompt',
            ok: hasPromptMapping || sections.some(section => section.prompt_template || section.required_facets?.length),
            action: 'open-advanced',
            actionTarget: 'template-placeholder-detail-form',
            actionLabel: '编辑 Prompt'
        },
        {
            label: 'Excel 图表和表格已绑定来源',
            ok: hasExcelMapping,
            action: 'focus-check',
            actionTarget: 'template-excel-mapping',
            actionLabel: '检查映射'
        },
        {
            label: '数字、禁用词、投资建议规则已配置',
            ok: hasRuleConfig,
            action: 'open-advanced',
            actionTarget: 'template-common-rules',
            actionLabel: '编辑规则'
        }
    ];
}

function buildPlaceholderReadinessItems(template, placeholders) {
    return (placeholders || [])
        .map(placeholderName => normalizePlaceholderName(placeholderName))
        .filter(Boolean)
        .map(placeholderName => {
            const mapping = getEffectivePlaceholderMapping(template, placeholderName);
            const readinessIssue = getPlaceholderReadinessIssue(mapping, placeholderName);
            const lifecycle = getPlaceholderLifecycleStatus(template, mapping, placeholderName);
            const issue = lifecycle.state === 'ready'
                ? null
                : lifecycle.state === 'missing'
                    ? readinessIssue
                : {
                    message: lifecycle.detail,
                    editorSection: lifecycle.state === 'confirm' ? 'basic' : 'basic'
                };
            return {
                placeholderName,
                mapping,
                ok: lifecycle.ok,
                issue,
                status: lifecycle,
                editorSection: issue?.editorSection || 'basic'
            };
        });
}

function getPlaceholderReadinessIssue(mapping, placeholderName) {
    const type = getCanonicalPlaceholderType(mapping.type, mapping) || inferPlaceholderType(placeholderName);
    if (type === 'paragraph') {
        const mode = getParagraphMode(mapping.type || type, mapping, placeholderName);
        if (usesEvidenceParagraphMode(mapping.type || type, mode)
            && !mapping.prompt_template
            && !mapping.prompt_retrieval_query) {
            return {
                message: '缺少 Prompt 模板或语义 Query',
                editorSection: 'query'
            };
        }
        if (isDataTemplateParagraphMode(mapping.type || type, mode)
            && !getDataTemplateComponent(mapping).template) {
            return {
                message: '缺少数据说明模板',
                editorSection: 'fixed_template'
            };
        }
        return null;
    }
    if (type === 'field') {
        const sourceKind = getPlaceholderSourceKind(mapping.type || type, mapping, placeholderName);
        if (sourceKind === 'report_period') return null;
        if ((sourceKind === 'excel_cell' || sourceKind === 'excel_range')
            && !(typeof mapping.source === 'string' ? mapping.source : mapping.source?.ref)) {
            return {
                message: '缺少 Excel 来源',
                editorSection: 'basic'
            };
        }
        if (!mapping.value && sourceKind !== 'excel_cell' && sourceKind !== 'excel_range') {
            return {
                message: '缺少短字段取值',
                editorSection: 'basic'
            };
        }
        return null;
    }
    if (type === 'static_text' && !mapping.value) {
        return {
            message: '缺少固定文案',
            editorSection: 'basic'
        };
    }
    if (type === 'table' && !mapping.source?.kind) {
        return {
            message: '缺少表格来源',
            editorSection: 'basic'
        };
    }
    if (type === 'chart' && !mapping.source?.kind) {
        return {
            message: '缺少图表来源',
            editorSection: 'basic'
        };
    }
    return null;
}

function buildPreflightDisplayModel(readiness, checks, placeholderReadiness, context) {
    const compiledPlaceholders = Array.isArray(readiness.compiledPlan?.placeholders)
        ? readiness.compiledPlan.placeholders
        : [];
    const evidenceCount = compiledPlaceholders.length
        ? compiledPlaceholders.filter(item => item.evidence_required).length
        : placeholderReadiness.length;
    const mappedCount = context.placeholders.length || context.sections.length;
    const rawActions = [
        ...readiness.assetChecks.filter(item => !item.ok),
        ...checks.filter(item => !item.ok),
        ...placeholderReadiness.filter(item => !item.ok)
    ];
    const actions = normalizeAndPrioritizePreflightActions(rawActions);
    const detailGroups = buildPreflightReviewGroups(
        readiness,
        checks,
        placeholderReadiness,
        context
    );

    if (!actions.length) {
        return {
            state: 'ready',
            summary: `${mappedCount} 个占位符已配置 · ${evidenceCount} 个正文段落可检索生成`,
            actions: [],
            detailGroups
        };
    }

    return {
        state: 'blocked',
        summary: `${actions.length} 项待处理 · ${mappedCount} 个占位符已配置`,
        actions,
        detailGroups
    };
}

function normalizeAndPrioritizePreflightActions(items) {
    const actionsByKey = new Map();
    items.forEach(item => {
        const action = item.action || 'open-advanced';
        const actionTarget = item.actionTarget || 'template-advanced-maintenance';
        const placeholderName = normalizePlaceholderName(item.placeholderName || '');
        const label = placeholderName ? `{{${placeholderName}}}` : (item.label || '生成配置');
        const detail = item.issue?.message || item.status?.detail || item.value || '需要补充配置';
        const normalized = {
            label,
            detail,
            action,
            actionTarget,
            actionLabel: item.actionLabel || '去处理',
            placeholderName,
            editorSection: item.editorSection || item.issue?.editorSection || 'basic',
            priority: getPreflightActionPriority(label, detail)
        };
        const key = `${placeholderName}|${action}|${actionTarget}|${label}`;
        const existing = actionsByKey.get(key);
        if (!existing || normalized.priority < existing.priority) {
            actionsByKey.set(key, normalized);
        }
    });

    return [...actionsByKey.values()].sort((left, right) =>
        left.priority - right.priority || left.label.localeCompare(right.label, 'zh-CN')
    );
}

function getPreflightActionPriority(label, detail) {
    const text = `${label} ${detail}`.toLowerCase();
    if (/prompt|query|检索关键词|占位符映射|word 占位符/.test(text)) return 10;
    if (/word 模板|ppt 模板|section 配置|模板缺失/.test(text)) return 20;
    if (/excel|表格|图表|数据来源/.test(text)) return 30;
    return 40;
}

function buildPreflightReviewGroups(readiness, checks, placeholderReadiness, context) {
    const compiledPlan = readiness.compiledPlan || null;
    const compiledPlaceholders = Array.isArray(compiledPlan?.placeholders)
        ? compiledPlan.placeholders
        : [];
    const evidencePlaceholders = compiledPlaceholders.filter(item => item.evidence_required);
    const deterministicPlaceholders = compiledPlaceholders.filter(item => item.deterministic === true);
    const missingPromptItems = compiledPlaceholders.filter(item =>
        item.evidence_required && item.prompt_found === false
    );
    const missingRetrievalItems = compiledPlaceholders.filter(item =>
        item.evidence_required && item.retrieval_ready === false
    );
    const planWarnings = Array.isArray(readiness.compiledPlan?.warnings)
        ? readiness.compiledPlan.warnings
        : [];
    const evidencePreviewRows = buildEvidencePreviewRows(readiness);
    const assetRows = (readiness.assetChecks || []).map(item => ({
        label: item.label || '模板资产',
        value: item.ok ? '已就绪' : '待处理',
        ok: Boolean(item.ok),
        action: item.action,
        actionTarget: item.actionTarget,
        actionLabel: item.actionLabel
    }));
    const mappedPlaceholders = context.placeholders.length || context.sections.length;

    return [
        {
            title: 'Prompt 覆盖',
            meta: missingPromptItems.length
                ? `${missingPromptItems.length} 个缺 Prompt`
                : `${evidencePlaceholders.length || placeholderReadiness.length} 个可写作`,
            rows: [
                {
                    label: 'Word 占位符映射',
                    value: checks[0]?.ok ? `${mappedPlaceholders}/${mappedPlaceholders}` : '待处理',
                    ok: Boolean(checks[0]?.ok),
                    action: checks[0]?.action,
                    actionTarget: checks[0]?.actionTarget,
                    actionLabel: checks[0]?.actionLabel,
                    placeholderName: checks[0]?.placeholderName
                },
                {
                    label: 'AI 文本 Prompt',
                    value: missingPromptItems.length ? `${missingPromptItems.length} 个待补` : '已覆盖',
                    ok: missingPromptItems.length === 0 && Boolean(checks[1]?.ok),
                    action: checks[1]?.action,
                    actionTarget: checks[1]?.actionTarget,
                    actionLabel: checks[1]?.actionLabel
                },
                {
                    label: '禁用词 / 投资建议',
                    value: checks[3]?.ok ? '已配置' : '待配置',
                    ok: Boolean(checks[3]?.ok),
                    action: checks[3]?.action,
                    actionTarget: checks[3]?.actionTarget,
                    actionLabel: checks[3]?.actionLabel
                },
                ...missingPromptItems.slice(0, 3).map(item => ({
                    label: `{{${item.placeholder}}}`,
                    value: `缺少 ${item.prompt_template || item.title || 'Prompt 模板'}`,
                    ok: false,
                    placeholderName: item.placeholder,
                    editorSection: 'basic',
                    action: 'focus-placeholder',
                    actionLabel: '定位'
                }))
            ]
        },
        {
            title: 'Evidence 覆盖',
            meta: missingRetrievalItems.length || planWarnings.length
                ? `${missingRetrievalItems.length + planWarnings.length} 项待处理`
                : `${evidencePlaceholders.length} 个检索段落`,
            rows: [
                {
                    label: '检索关键词 / Query',
                    value: missingRetrievalItems.length ? `${missingRetrievalItems.length} 个待补` : '已覆盖',
                    ok: missingRetrievalItems.length === 0,
                    action: 'open-advanced',
                    actionTarget: 'template-placeholder-detail-form',
                    actionLabel: '编辑检索'
                },
                ...missingRetrievalItems.slice(0, 4).map(item => ({
                    label: `{{${item.placeholder}}}`,
                    value: '缺少检索关键词或 Query',
                    ok: false,
                    placeholderName: item.placeholder,
                    editorSection: 'query',
                    action: 'focus-placeholder',
                    actionLabel: '定位'
                })),
                ...planWarnings.slice(0, 3).map(warning => ({
                    label: '后端计划',
                    value: warning,
                    ok: false
                })),
                ...evidencePreviewRows.slice(0, 4).map(row => ({
                    label: row.label,
                    value: row.value,
                    ok: row.ok,
                    kind: row.kind,
                    action: row.action,
                    actionTarget: row.actionTarget,
                    actionLabel: row.actionLabel,
                    placeholderName: row.placeholderName,
                    editorSection: row.editorSection,
                    detail: row.detail
                }))
            ]
        },
        {
            title: '输出资产',
            meta: readiness.latestReport ? '最近版本可用' : `${readiness.readyAssets}/${readiness.totalAssets} 项资产`,
            rows: [
                ...assetRows,
                {
                    label: 'Excel 数据来源',
                    value: context.excelRows.length ? `${context.excelRows.length} 个范围` : '待绑定',
                    ok: context.excelRows.length > 0,
                    action: checks[2]?.action,
                    actionTarget: checks[2]?.actionTarget,
                    actionLabel: checks[2]?.actionLabel
                },
                {
                    label: '确定性占位符',
                    value: deterministicPlaceholders.length ? `${deterministicPlaceholders.length} 个` : '无',
                    ok: true
                },
                {
                    label: '输出入口',
                    value: readiness.latestReport ? '可预览 / 下载' : '生成后可用',
                    ok: Boolean(readiness.outputOk)
                }
            ]
        }
    ];
}

function buildEvidencePreviewRows(readiness) {
    const runLogSamples = getRunLogEvidenceSamples(currentTemplateState.lastReportRunLog);
    if (runLogSamples.length) return runLogSamples;
    const compiledPlaceholders = Array.isArray(readiness.compiledPlan?.placeholders)
        ? readiness.compiledPlan.placeholders
        : [];
    return compiledPlaceholders
        .filter(item => item.evidence_required)
        .slice(0, 5)
        .map(item => {
            const keywords = item.retrieval_config?.must_any || [];
            const topK = item.retrieval_config?.top_k || 0;
            return {
                label: `Evidence 抽样 · ${item.title || item.placeholder}`,
                value: keywords.length
                    ? `关键词 ${keywords.slice(0, 4).join('、')} · Top K ${topK || '-'}`
                    : `检索 Query 来自 ${item.prompt_template || 'Prompt'}`,
                ok: item.retrieval_ready !== false,
                kind: 'template-evidence-sample',
                action: 'focus-placeholder',
                placeholderName: item.placeholder,
                editorSection: 'query',
                actionLabel: '调关键词'
            };
        });
}

function getRunLogEvidenceSamples(runLog) {
    const sections = Array.isArray(runLog?.generation?.sections)
        ? runLog.generation.sections
        : [];
    return sections.slice(0, 5).map(section => {
        const evidence = Array.isArray(section.evidence) ? section.evidence : [];
        const firstEvidence = evidence[0] || {};
        const matchedTerms = Array.isArray(firstEvidence.matched_terms)
            ? firstEvidence.matched_terms
            : [];
        return {
            label: `Evidence 抽样 · ${section.title || section.placeholder || '段落'}`,
            value: evidence.length
                ? `${firstEvidence.title || '证据'} · 命中 ${matchedTerms.slice(0, 4).join('、') || 'matched_terms'}`
                : '本段未检索到 evidence',
            ok: evidence.length > 0,
            kind: 'template-evidence-sample',
            action: evidence.length ? 'open-logs' : 'focus-placeholder',
            placeholderName: section.placeholder || '',
            editorSection: 'query',
            actionLabel: evidence.length ? '看日志' : '调关键词'
        };
    });
}

function renderPreflightReviewGroup(group) {
    const rows = (group.rows || []).filter(Boolean);
    return `
        <div class="template-preflight-group">
            <div class="template-preflight-group-title">
                <span>${esc(group.title || '')}</span>
                <strong>${esc(group.meta || '')}</strong>
            </div>
            ${rows.map(row => `
                <div class="validation-item ${row.ok ? 'ok' : 'pending'} ${esc(row.kind || '')}">
                    <span>
                        ${esc(row.label || '')}
                        ${row.value ? `<small>${esc(row.value)}</small>` : ''}
                    </span>
                    ${row.action ? `
                        <button
                            type="button"
                            class="template-check-action"
                            data-template-check-action="${esc(row.action)}"
                            data-template-check-target="${esc(row.actionTarget || '')}"
                            data-template-placeholder-name="${esc(row.placeholderName || '')}"
                            data-template-placeholder-editor-section="${esc(row.editorSection || 'basic')}"
                        >
                            ${esc(row.actionLabel || '处理')}
                        </button>
                    ` : `<strong>${esc(row.value || '')}</strong>`}
                </div>
            `).join('')}
        </div>
    `;
}

function renderPreflightSummary(model) {
    const panel = document.getElementById('template-project-check-details');
    const statusEl = document.getElementById('template-project-check-status');
    setText('template-project-check-summary', model.summary);
    if (statusEl) {
        statusEl.textContent = model.state === 'ready'
            ? '可直接生成'
            : `${model.actions.length} 项待处理`;
        statusEl.classList.toggle('warning', model.state === 'blocked');
    }
    if (panel) {
        panel.dataset.preflightState = model.state;
        if (model.state === 'blocked') panel.open = true;
    }
}

function renderPreflightActions(model) {
    const container = document.getElementById('template-project-check-actions');
    if (!container) return;
    if (model.state === 'ready') {
        container.innerHTML = `
            <div class="template-preflight-ready-summary">
                全部检查通过。展开后可查看 Prompt、检索和输出详情。
            </div>
        `;
        return;
    }

    container.innerHTML = model.actions.slice(0, 3).map(action => `
        <div class="template-preflight-action">
            <span>
                <strong>${esc(action.label)}</strong>
                <small class="template-preflight-action-detail">${esc(action.detail)}</small>
            </span>
            <button
                type="button"
                class="template-check-action"
                data-template-check-action="${esc(action.action)}"
                data-template-check-target="${esc(action.actionTarget)}"
                data-template-placeholder-name="${esc(action.placeholderName)}"
                data-template-placeholder-editor-section="${esc(action.editorSection)}"
            >${esc(action.actionLabel)}</button>
        </div>
    `).join('');
}

function renderTemplateValidationPreview(template, sections, placeholders) {
    const list = document.getElementById('template-validation-list');
    if (!list) return;

    const readiness = buildGenerationReadiness(template, sections, placeholders);
    const checks = readiness.validationChecks;
    const placeholderReadiness = readiness.placeholderReadiness;
    renderPlaceholderIssueQueue(template, placeholderReadiness);
    const excelRows = readiness.excelRows;
    const model = buildPreflightDisplayModel(readiness, checks, placeholderReadiness, {
        sections,
        placeholders,
        excelRows
    });
    renderPreflightSummary(model);
    renderPreflightActions(model);
    list.innerHTML = model.detailGroups.map(group => renderPreflightReviewGroup(group)).join('');
}

function renderPlaceholderIssueQueue(template, placeholderReadiness) {
    const countEl = document.getElementById('template-placeholder-issue-count');
    const listEl = document.getElementById('template-placeholder-issue-list');
    if (!listEl) return;
    const queueEl = listEl.closest('.placeholder-issue-queue');
    const issues = (placeholderReadiness || []).filter(item => !item.ok);
    if (countEl) countEl.textContent = `${issues.length}`;
    if (queueEl) queueEl.classList.toggle('is-empty', issues.length === 0);
    if (!issues.length) {
        listEl.innerHTML = '<div class="empty-state compact">暂无阻止生成的问题</div>';
        return;
    }
    listEl.innerHTML = issues.slice(0, 5).map(item => `
        <button
            type="button"
            class="placeholder-issue-queue-item"
            data-template-check-action="focus-placeholder"
            data-template-placeholder-name="${esc(item.placeholderName || '')}"
            data-template-placeholder-editor-section="${esc(item.editorSection || 'basic')}"
        >
            <span>{{${esc(item.placeholderName)}}}</span>
            <strong>${esc(item.issue?.message || item.status?.detail || '需要处理')}</strong>
        </button>
    `).join('') + (issues.length > 5 ? `
        <button
            type="button"
            class="placeholder-issue-queue-item more"
            data-template-check-action="focus-placeholder"
            data-template-placeholder-name="${esc(issues[5].placeholderName || '')}"
            data-template-placeholder-editor-section="${esc(issues[5].editorSection || 'basic')}"
        >
            <span>查看所有 ${issues.length} 个未完成</span>
            <strong>定位下一个</strong>
        </button>
    ` : '');
}

function buildTemplateConfigYaml(template) {
    if (template.report_project) return buildPlaceholderMappingConfigYaml(template);
    const name = template.template_name || template.name || currentSelectedTemplate || 'report_template';
    const project = template.report_project || null;
    const isPptProject = project?.project_type === 'ppt';
    const templateAssetKey = isPptProject ? 'ppt_template' : 'word_template';
    const templateAssetValue = project?.template_filename
        || (isPptProject ? project?.ppt_template_filename : project?.word_template_filename)
        || (template.has_docx ? '已绑定' : '待上传');
    const sections = getTemplateWorkbenchSections(template).length ? getTemplateWorkbenchSections(template) : [
        {
            key: 'main_viewpoint',
            title: '行情回顾及主要观点',
            target_words: 350,
            placeholder: 'main_viewpoint',
            required_facets: ['主要指数表现', '成交额', '市场主线']
        }
    ];

    const lines = [
        `name: ${name}`,
        `description: ${template.description || `${name} 模板配置`}`,
        `version: ${template.version || '1.0'}`,
        'assets:',
        `  project: ${project?.name || '待绑定项目包'}`,
        `  ${templateAssetKey}: ${templateAssetValue}`,
        `  excel_workbook: ${project?.excel_workbook_filename || (template.has_excel ? '已绑定' : '待上传')}`,
        `  report_config: ${project?.report_config_filename || '当前模板 YAML'}`,
        `  prompt_templates: ${project?.prompt_templates_filename || '未绑定'}`,
        `  output_dir: ${project?.output_dir || '待绑定 generated 目录'}`,
        '  data_sources:',
        ...(project?.data_source_files?.length
            ? project.data_source_files.map(file => `    - ${file}`)
            : ['    - 未绑定']),
        'sections:'
    ];

    sections.forEach(section => {
        lines.push(`  - id: ${section.key}`);
        lines.push(`    title: ${section.title || section.key}`);
        lines.push(`    placeholder: "{{${section.placeholder || section.key}}}"`);
        lines.push(`    type: ${section.placeholder?.includes('chart') ? 'excel_chart' : 'ai_text'}`);
        lines.push(`    max_words: ${section.target_words || 250}`);
        lines.push('    data_slots:');
        const facets = section.required_facets?.length ? section.required_facets : ['excel.range_or_rag_profile'];
        facets.forEach(facet => lines.push(`      - ${facet}`));
        lines.push('    prompt: |');
        lines.push(`      请围绕“${section.title || section.key}”撰写正式周报段落。`);
        lines.push('      使用给定数据，语言客观审慎，不输出投资收益保证。');
        lines.push('    validators:');
        lines.push(`      evidence_policy: ${section.evidence_policy || 'strict'}`);
        lines.push('      require_numbers_from_data: true');
        lines.push('      forbidden_terms:');
        const forbiddenTerms = section.forbidden_terms?.length
            ? section.forbidden_terms
            : ['保本', '稳赚', '收益保证', '明确买入', '目标价'];
        forbiddenTerms.forEach(term => lines.push(`        - ${term}`));
        lines.push(`      investment_advice_policy: ${section.investment_advice_policy || 'no_direct_recommendation'}`);
    });

    return lines.join('\n');
}

function buildPlaceholderMappingConfigYaml(template, mappingsOverride = null) {
    const name = template.template_name || template.name || currentSelectedTemplate || 'report_template';
    const project = template.report_project || null;
    const isPptProject = project?.project_type === 'ppt';
    const templateAssetKey = isPptProject ? 'ppt_template' : 'word_template';
    const templateAssetValue = project?.template_filename
        || (isPptProject ? project?.ppt_template_filename : project?.word_template_filename)
        || '待绑定';
    const existingMappings = mappingsOverride || getStoredPlaceholderMappings(template);
    const lines = [
        '# 填写方式：',
        `# - placeholders 下每一项对应 ${isPptProject ? 'PPT' : 'Word'} 模板里的一个 {{占位符}}。`,
        usesEmbeddedPromptQueries(project)
            ? '# - type=prompt 时，系统直接使用 prompt_template 中内置的检索 Query 和写作规则。'
            : '# - type=prompt 时，系统会读取 query_source，再套用 prompt_template 生成正文。',
        usesEmbeddedPromptQueries(project)
            ? '# - prompt_template 写 Word 占位符对应的模板标题，例如：人工智能。'
            : '# - query_source 写法示例：data/industry.json#人工智能，表示取该 JSON 中“人工智能”的 QUERY。',
        '# - params 用来传给 Prompt 模板中的 {{param}} 等变量。',
        `name: ${name}`,
        `version: ${template.version || '1.0'}`,
        `description: ${isPptProject ? 'PPT' : 'Word'} 占位符到 Excel / Prompt / 静态文本的映射`,
        buildDefaultsBlock(getEditableCommonDefaults(template)),
        'assets:',
        `  ${templateAssetKey}: ${templateAssetValue}`,
        `  excel_workbook: ${project?.excel_workbook_filename || '待绑定'}`,
        `  prompt_templates: ${project?.prompt_templates_filename || '未绑定'}`,
        buildPlaceholderMappingsBlock(template, existingMappings)
    ];

    return lines.join('\n');
}

function buildPlaceholderMappingsBlock(template, existingMappings) {
    const placeholders = getTemplateWorkbenchPlaceholders(template);
    const lines = ['placeholders:'];

    placeholders.forEach(placeholder => {
        const key = normalizePlaceholderName(placeholder);
        const mapping = existingMappings.get(key) || {};
        lines.push(...buildPlaceholderYamlEntry(template, key, mapping));
    });

    return lines.join('\n');
}

function buildDefaultsBlock(defaults) {
    const validators = defaults?.validators || {};
    const retrieval = defaults?.retrieval || {};
    const reportPeriod = defaults?.report_period || {};
    const rerank = defaults?.rerank || {};
    const forbiddenTerms = Array.isArray(validators.forbidden_terms)
        ? validators.forbidden_terms
        : ['保本', '稳赚', '收益保证', '明确买入', '目标价'];
    const generationConstraints = Array.isArray(defaults?.generation_constraints)
        ? defaults.generation_constraints
        : getStoredCommonDefaults({}).generation_constraints;
    const lines = [
        'defaults:',
        `  generation_mode: ${defaults?.generation_mode || 'evidence_grounded_generation'}`,
        `  evidence_policy: ${defaults?.evidence_policy || 'strict'}`,
        `  query_mode: ${defaults?.query_mode || 'retrieval_query_embedded'}`,
        '  validators:',
        `    require_evidence_from_uploaded_material: ${validators.require_evidence_from_uploaded_material !== false}`,
        `    forbid_external_facts: ${validators.forbid_external_facts !== false}`,
        `    forbid_direct_investment_advice: ${validators.forbid_direct_investment_advice !== false}`,
        '    forbidden_terms:'
    ];
    forbiddenTerms.forEach(term => lines.push(`      - ${term}`));
    lines.push('  generation_constraints:');
    generationConstraints.forEach(item => lines.push(`  - ${item}`));
    lines.push('  report_period:');
    const reportDate = reportPeriod.report_date || getDefaultReportDate();
    lines.push(`    report_date: ${reportDate}`);
    lines.push(`    start_date: ${reportPeriod.start_date || getDefaultEvidenceStartDate(reportDate)}`);
    lines.push(`    end_date: ${reportPeriod.end_date || reportDate}`);
    lines.push('  retrieval:');
    lines.push(`    mode: ${retrieval.mode || 'hybrid'}`);
    lines.push(`    top_k: ${retrieval.top_k ?? 10}`);
    lines.push(`    candidate_k: ${retrieval.candidate_k ?? retrieval.keyword_candidates ?? 40}`);
    lines.push(`    semantic_candidate_k: ${retrieval.semantic_candidate_k ?? retrieval.semantic_candidates ?? 80}`);
    lines.push(`    keyword_weight: ${retrieval.keyword_weight ?? 0.6}`);
    lines.push(`    semantic_weight: ${retrieval.semantic_weight ?? 0.4}`);
    lines.push(`    embedding_model: ${retrieval.embedding_model || 'BAAI/bge-large-zh-v1.5'}`);
    const sourceTypes = Array.isArray(retrieval.source_types) ? retrieval.source_types : [];
    if (sourceTypes.length) {
        lines.push('    source_types:');
        sourceTypes.forEach(sourceType => lines.push(`      - ${sourceType}`));
    }
    lines.push('  rerank:');
    lines.push(`    enabled: ${rerank.enabled !== false}`);
    lines.push(`    provider: ${rerank.provider || 'bge-reranker'}`);
    lines.push(`    model: ${rerank.model || 'BAAI/bge-reranker-large'}`);
    lines.push(`    top_n: ${rerank.top_n ?? rerank.candidates ?? 30}`);
    lines.push(`    min_score: ${rerank.min_score ?? 0.35}`);
    return lines.join('\n');
}

function buildSelectedPlaceholderYamlFragment(template, existingMappings) {
    const key = normalizePlaceholderName(currentTemplateState.selectedPlaceholderName);
    if (!key) return '# 从左侧选择一个 Word 占位符后显示对应 YAML 片段';
    if (isSystemDatePlaceholder(key)) {
        const field = inferReportPeriodField(key);
        return [
            'placeholders:',
            `  ${key}:`,
            `    title: ${inferPlaceholderTitle(key)}`,
            '    type: field',
            '    format: date',
            '    source:',
            '      kind: report_period',
            `      field: ${field}`
        ].join('\n');
    }
    const mapping = existingMappings.get(key) || {};
    const type = getCanonicalPlaceholderType(mapping.type, mapping) || inferPlaceholderType(key);
    if (type === 'excel_commodity_market_review') {
        return [
            '# 当前占位符片段',
            '# 固定 Excel 字段：只配置数据来源，不使用 Prompt、检索或大模型写作。',
            'placeholders:',
            ...buildPlaceholderYamlEntry(template, key, mapping)
        ].join('\n');
    }
    return [
        '# 当前占位符片段',
        '# 继承 defaults: 共用 Prompt 约束 / 检索配置 / Rerank / validators。',
        '# 下方只写当前占位符自己的覆盖项，例如 prompt_template、target_words、max_words、params。',
        'placeholders:',
        ...buildPlaceholderYamlEntry(template, key, mapping)
    ].join('\n');
}

function buildPlaceholderYamlEntry(template, key, mapping) {
    const project = template.report_project || null;
    const storedType = mapping.type || '';
    const type = getCanonicalPlaceholderType(storedType, mapping) || inferPlaceholderType(key);
    const paragraphMode = getParagraphMode(storedType, mapping, key);
    const lines = [
        `  ${key}:`,
        `    title: ${mapping.title || inferPlaceholderTitle(key)}`,
        `    type: ${type}`
    ];
    if (mapping.confirmed !== undefined) {
        lines.push(`    confirmed: ${mapping.confirmed === false ? 'false' : 'true'}`);
    }

    if (type === 'field') {
        const sourceKind = getPlaceholderSourceKind(storedType, mapping, key);
        if (sourceKind === 'report_period') {
            lines.push('    format: date');
            lines.push('    source:');
            lines.push('      kind: report_period');
            lines.push(`      field: ${mapping.field || mapping.source?.field || inferReportPeriodField(key)}`);
        } else if (sourceKind === 'excel_cell' || sourceKind === 'excel_range') {
            lines.push('    source:');
            lines.push(`      kind: ${sourceKind}`);
            lines.push(`      ref: ${typeof mapping.source === 'string' ? mapping.source : (mapping.source?.ref || '')}`);
        } else {
            lines.push('    source:');
            lines.push('      kind: manual');
            lines.push(`    value: ${mapping.value || ''}`);
        }
    } else if (type === 'excel_commodity_market_review') {
        const dataSource = mapping.data_source || {};
        const kind = dataSource.kind || (key.includes('原油') ? 'oil' : 'gold');
        lines.push('    data_source:');
        lines.push(`      kind: ${kind}`);
        lines.push(`      workbook: ${dataSource.workbook || '周报数据.xlsx'}`);
        lines.push(`      sheet: ${dataSource.sheet || (kind === 'oil' ? '石油' : '黄金')}`);
        if (mapping.params?.param) {
            lines.push('    params:');
            lines.push(`      param: ${mapping.params.param}`);
        } else {
            lines.push('    params: {}');
        }
    } else if (type === 'paragraph') {
        lines.push(`    mode: ${paragraphMode}`);
        if (usesEvidenceParagraphMode(storedType, paragraphMode)) {
            lines.push(`    prompt_template: ${mapping.prompt_template || resolvePromptTemplateName(key, project)}`);
            if (!usesEmbeddedPromptQueries(project)) {
                lines.push(`    query_source: ${mapping.query_source || inferQuerySource(key, project)}`);
            } else {
                lines.push('    query_mode: retrieval_query_embedded');
            }
            lines.push(`    target_words: ${mapping.target_words || inferDefaultTargetWords(key)}`);
            lines.push(`    max_words: ${mapping.max_words || inferDefaultMaxWords(key)}`);
            if (mapping.min_news_count) lines.push(`    min_news_count: ${mapping.min_news_count}`);
        }
        if (isDataTemplateParagraphMode(storedType, paragraphMode)) {
            lines.push(...buildCompositeMarketReviewYamlLines(mapping, key, {
                includeLlmWriting: usesEvidenceParagraphMode(storedType, paragraphMode)
            }));
        } else if (usesEvidenceParagraphMode(storedType, paragraphMode)) {
            const retrieval = mapping.retrieval || {};
            const keywords = getExplicitPlaceholderRetrievalKeywords(mapping);
            if (retrieval.keyword_profile || keywords.length) {
                lines.push('    retrieval:');
                if (retrieval.keyword_profile) lines.push(`      keyword_profile: ${retrieval.keyword_profile}`);
                if (keywords.length) {
                    lines.push('      keywords:');
                    keywords.forEach(keyword => lines.push(`      - ${keyword}`));
                }
            }
            const writingStructure = getLlmWritingComponent(mapping).writing_structure || mapping.writing_structure || [];
            if (Array.isArray(writingStructure) && writingStructure.length) {
                lines.push('    writing_structure:');
                writingStructure.forEach(item => lines.push(`    - ${item}`));
            }
        }
        if (usesEvidenceParagraphMode(storedType, paragraphMode)) {
            const param = mapping.params?.param || inferPromptParam(key);
            if (param) {
                lines.push('    params:');
                lines.push(`      param: ${param}`);
            } else {
                lines.push('    params: {}');
            }
        }
    } else if (type === 'table') {
        lines.push('    source:');
        lines.push(`      kind: ${mapping.source?.kind || 'excel_range'}`);
        if (mapping.source?.workbook) lines.push(`      workbook: ${mapping.source.workbook}`);
        if (mapping.source?.sheet) lines.push(`      sheet: ${mapping.source.sheet}`);
        if (mapping.source?.range) lines.push(`      range: ${mapping.source.range}`);
        lines.push('    insert:');
        lines.push(`      mode: ${mapping.insert?.mode || 'replace_placeholder'}`);
    } else if (type === 'chart') {
        lines.push('    source:');
        lines.push(`      kind: ${mapping.source?.kind || 'excel_chart'}`);
        if (mapping.source?.workbook) lines.push(`      workbook: ${mapping.source.workbook}`);
        if (mapping.source?.chart) lines.push(`      chart: ${mapping.source.chart}`);
        lines.push('    insert:');
        lines.push(`      mode: ${mapping.insert?.mode || 'replace_placeholder'}`);
    } else {
        lines.push(`    value: ${mapping.value || ''}`);
    }
    lines.push(...buildUnifiedRenderingYamlLines(mapping.rendering));
    return lines;
}

function buildUnifiedRenderingYamlLines(rendering) {
    if (!rendering || typeof rendering !== 'object') return [];
    const lines = ['    rendering:'];
    if (rendering.paragraph_style) lines.push(`      paragraph_style: ${rendering.paragraph_style}`);
    if (rendering.default_font) lines.push(`      default_font: ${rendering.default_font}`);
    if (rendering.default_size_pt !== undefined && rendering.default_size_pt !== null) {
        lines.push(`      default_size_pt: ${rendering.default_size_pt}`);
    }
    if (rendering.visible_if) lines.push(`      visible_if: ${rendering.visible_if}`);
    if (Array.isArray(rendering.runs) && rendering.runs.length) {
        lines.push('      runs:');
        rendering.runs.forEach(run => {
            lines.push('        -');
            Object.entries(run || {}).forEach(([key, value]) => {
                if (value !== undefined && value !== null && value !== '') {
                    lines.push(`          ${key}: ${typeof value === 'string' ? JSON.stringify(value) : value}`);
                }
            });
        });
    }
    if (rendering.chart_grid && typeof rendering.chart_grid === 'object') {
        lines.push('      chart_grid:');
        Object.entries(rendering.chart_grid).forEach(([key, value]) => {
            if (value !== undefined && value !== null) {
                lines.push(`        ${key}: ${typeof value === 'string' ? JSON.stringify(value) : JSON.stringify(value)}`);
            }
        });
    }
    return lines.length === 1 ? [] : lines;
}

function buildCompositeMarketReviewYamlLines(mapping, key, { includeLlmWriting = true } = {}) {
    const lines = [
        '    data_source:',
        '      workbook: 周报数据.xlsx',
        '      domestic_sheet: 国内',
        '      turnover_sheet: 市场成交',
        '    components:'
    ];
    const dataTemplate = getDataTemplateComponent(mapping).template || inferDefaultDataTemplate(key);
    lines.push('    - name: 市场表现与交易面');
    lines.push('      type: data_template');
    lines.push('      source: excel');
    lines.push(`      template: ${dataTemplate}`);
    const yamlDataFields = getDataTemplateFields(mapping);
    const dataTemplateFieldLines = buildDataTemplateFieldsYamlLines(yamlDataFields, '        ');
    if (dataTemplateFieldLines.length) {
        lines.push('      fields:');
        lines.push(...dataTemplateFieldLines);
    } else {
        lines.push('      fields: {}');
    }
    if (!includeLlmWriting) return lines;
    lines.push('    - name: 市场热点与趋势判断');
    lines.push('      type: llm_writing');
    const llmComponent = getLlmWritingComponent(mapping);
    const retrieval = llmComponent.retrieval || mapping.retrieval || {};
    const keywords = getExplicitPlaceholderRetrievalKeywords({ retrieval, components: [] });
    if (retrieval.keyword_profile || keywords.length) {
        lines.push('      retrieval:');
        if (retrieval.keyword_profile) lines.push(`        keyword_profile: ${retrieval.keyword_profile}`);
        if (keywords.length) {
            lines.push('        keywords:');
            keywords.forEach(keyword => lines.push(`        - ${keyword}`));
        }
    }
    const writingStructure = llmComponent.writing_structure || mapping.writing_structure || inferDefaultWritingStructure(key);
    if (Array.isArray(writingStructure) && writingStructure.length) {
        lines.push('      writing_structure:');
        writingStructure.forEach(item => lines.push(`      - ${item}`));
    }
    return lines;
}

function buildDataTemplateFieldsYamlLines(fields = {}, indent = '') {
    return Object.entries(fields || {}).flatMap(([fieldKey, field = {}]) => {
        const lines = [`${indent}${fieldKey}:`];
        lines.push(`${indent}  label: ${field.label || fieldKey}`);
        if (field.display_name) lines.push(`${indent}  display_name: ${field.display_name}`);
        if (field.workbook) lines.push(`${indent}  workbook: ${field.workbook}`);
        if (field.sheet) lines.push(`${indent}  sheet: ${field.sheet}`);
        if (field.cell) lines.push(`${indent}  cell: ${field.cell}`);
        if (field.range) lines.push(`${indent}  range: ${field.range}`);
        if (field.rule) lines.push(`${indent}  rule: ${field.rule}`);
        return lines;
    });
}

function getSelectedPromptTemplateName(template) {
    const name = normalizePlaceholderName(currentTemplateState.selectedPlaceholderName);
    if (!name) return '';
    const mapping = getSelectedPlaceholderMapping(template) || {};
    if (String(mapping.type || '').toLowerCase() === 'excel_commodity_market_review') return '';
    return mapping.prompt_template || resolvePromptTemplateName(name, template.report_project);
}

function getPromptTemplateFragment(source, promptName) {
    if (!promptName) return '从左侧选择一个占位符后显示对应 Prompt 模板';
    const pattern = new RegExp(`(^|\\n)##\\s+${escapeRegExp(promptName)}\\s*\\n([\\s\\S]*?)(?=\\n##\\s+|$)`);
    const match = String(source || '').match(pattern);
    if (match) {
        return `## ${promptName}\n${match[2].trimEnd()}`;
    }
    return [
        `## ${promptName}`,
        '',
        '# 未在 Prompt 模板库中找到当前模板，可在这里补充后保存。'
    ].join('\n');
}

function escapeRegExp(value) {
    return String(value || '').replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function inferPlaceholderType(name) {
    if (isSystemDatePlaceholder(name)) return 'field';
    if (/^(start_date|end_date|data\d+)$/i.test(name)) return 'field';
    if (/^(table|summary_table|.*_table)$/i.test(name)) return 'table';
    if (/^(chart|.*_chart|chart_\d+)$/i.test(name)) return 'chart';
    if (/^(content\d+|phrase\d+|sector\d+)$/i.test(name)) return 'paragraph';
    if (/[\u4e00-\u9fff]/.test(name)) return 'paragraph';
    return 'static_text';
}

function isSystemDatePlaceholder(name) {
    const normalized = normalizePlaceholderName(name);
    return ['开始日期', '结束日期', 'start_date', 'end_date'].includes(normalized);
}

function inferReportPeriodField(name) {
    const normalized = normalizePlaceholderName(name);
    return ['开始日期', 'start_date'].includes(normalized) ? 'start_date' : 'end_date';
}

function inferPlaceholderTitle(name) {
    const titles = {
        title: '报告标题',
        start_date: '开始日期',
        end_date: '结束日期'
    };
    return titles[name] || name;
}

function resolvePromptTemplateName(name, project = null) {
    const normalized = normalizePlaceholderName(name);
    if (usesEmbeddedPromptQueries(project) && /[\u4e00-\u9fff]/.test(normalized)) {
        return normalized;
    }
    const directMap = {
        'A股市场回顾': 'domestic_market',
        '中国宏观': 'domestic_macro',
        '港股科技': 'overseas_hk_tech',
        '港股央企红利': 'overseas_hk_dividend',
        '原油': 'commodity_market',
        '原油市场回顾': 'commodity_market',
        '黄金': 'commodity_market',
        '美国新闻': 'overseas_news',
        '欧洲新闻': 'overseas_news'
    };
    if (directMap[normalized]) return directMap[normalized];
    if (['美国', '欧洲', '日本', '海外市场'].includes(normalized)) return 'overseas_market';
    if (['人工智能', '医药生物', '消费', '金融地产', '电子', '航天', '电力设备新能源'].includes(normalized)) {
        return 'industry_review';
    }
    if (/^(content\d+|phrase\d+|sector\d+)$/i.test(normalized)) return 'section_paragraph';
    return 'section_paragraph';
}

function usesEmbeddedPromptQueries(project = null) {
    const projectName = project?.name || project?.slug || '';
    const sourceFiles = project?.data_source_files || [];
    const promptName = project?.prompt_templates_filename || '';
    return projectName.includes('华安ETF周报')
        || (promptName && sourceFiles.length === 0);
}

function inferQuerySource(name, project = null) {
    const normalized = normalizePlaceholderName(name);
    const sourceMap = {
        'A股市场回顾': 'data/domestic.json#市场',
        '中国宏观': 'data/domestic.json#宏观',
        '人工智能': 'data/industry.json#人工智能',
        '电子': 'data/industry.json#电子',
        '航天': 'data/industry.json#航天',
        '电力设备新能源': 'data/industry.json#电力设备新能源',
        '消费': 'data/industry.json#消费',
        '金融地产': 'data/industry.json#金融地产',
        '医药生物': 'data/industry.json#医药生物',
        '港股科技': 'data/overseas.json#港股科技',
        '港股央企红利': 'data/overseas.json#港股央企红利',
        '美国': 'data/overseas.json#美国',
        '欧洲': 'data/overseas.json#欧洲',
        '日本': 'data/overseas.json#日本',
        '美国新闻': 'data/overseas.json#美国新闻',
        '欧洲新闻': 'data/overseas.json#欧洲新闻',
        '海外市场': 'data/overseas.json#美国',
        '原油': 'data/commodity.json#石油',
        '原油市场回顾': 'data/commodity.json#石油',
        '黄金': 'data/commodity.json#黄金'
    };
    if (sourceMap[normalized]) return sourceMap[normalized];
    const firstDataSource = project?.data_source_files?.[0];
    return firstDataSource ? `data/${firstDataSource}#${normalized}` : '';
}

function inferPromptParam(name) {
    const normalized = normalizePlaceholderName(name);
    if (['人工智能', '医药生物', '消费', '金融地产', '电子', '航天', '电力设备新能源'].includes(normalized)) {
        return normalized;
    }
    if (['美国', '欧洲', '日本', '港股科技', '港股央企红利'].includes(normalized)) {
        return normalized;
    }
    if (['原油', '原油市场回顾'].includes(normalized)) return '原油';
    if (normalized === '黄金') return '黄金';
    return '';
}

function inferDefaultMaxWords(name) {
    const normalized = normalizePlaceholderName(name);
    if (normalized === 'A股市场回顾') return 320;
    if (['美国新闻', '欧洲新闻'].includes(normalized)) return 250;
    if (['原油', '原油市场回顾', '黄金', '黄金市场回顾'].includes(normalized)) return 300;
    if (['中国宏观', '美国', '欧洲', '日本', '海外市场', '港股科技', '港股央企红利'].includes(normalized)) return 350;
    if (['人工智能', '医药生物', '消费', '金融地产', '电子', '航天', '电力设备新能源'].includes(normalized)) return 400;
    return 300;
}

function inferDefaultTargetWords(name) {
    const normalized = normalizePlaceholderName(name);
    if (normalized === 'A股市场回顾') return 250;
    const maxWords = inferDefaultMaxWords(normalized);
    return Math.max(80, Math.round(maxWords * 0.7 / 10) * 10);
}

function inferDefaultDataTemplate(name) {
    const normalized = normalizePlaceholderName(name);
    if (normalized !== 'A股市场回顾') return '';
    return '本周A股市场整体呈现{market_trend}，主要指数表现不一：{index_performance}。交易面，A股市场本周日均成交额在{avg_turnover}左右，市场投资热情{turnover_trend}。';
}

function inferDefaultWritingStructure(name) {
    const normalized = normalizePlaceholderName(name);
    if (normalized !== 'A股市场回顾') return [];
    return [
        '接在固定开头之后，概括本周市场热点板块或概念，按材料中的重要性或出现频率排序',
        '描述板块轮动特征，包括反复活跃方向、阶段性活跃方向和相对低迷方向',
        '结合一个有明确 evidence 支撑的政策、产业或景气度变化，给出一句审慎趋势判断',
        '最后如需表达关注方向，应使用“后续可关注”“值得跟踪”等克制表述，不得构成直接投资建议'
    ];
}

function shouldUsePromptTemplateLibraryDraft(template) {
    const source = template.report_project?.prompt_templates_source || '';
    if (!source.trim()) return true;
    return source.includes('要求如下：') && !source.includes('# Prompt 模板库');
}

function buildPromptTemplateLibraryMarkdown(template) {
    const name = template.template_name || template.name || currentSelectedTemplate || 'report_template';
    return [
        '# Prompt 模板库',
        '',
        `适用项目：${name}`,
        '',
        '说明：这里是可复用写作模板，不是单个占位符的完整提示词。占位符在 report_config.yaml 里通过 prompt_template 选择下面的模板；检索 Query 用来先从数据库/新闻库取 evidence，再由写作规则生成正文。',
        '',
        '## domestic_market',
        '用于：A股市场回顾',
        '',
        '```text',
        '{{query}}',
        '基于上传材料概括本周 A 股市场热点与风格变化。只使用材料内事实和数据，避免指数点位预测、个股推荐和收益承诺。输出一段正式周报文字，控制在 100-150 字。',
        '```',
        '',
        '## domestic_macro',
        '用于：中国宏观',
        '',
        '```text',
        '{{query}}',
        '围绕宏观数据、货币政策、财政政策和产业政策提炼本周变化。结论必须由材料事实支撑，语言客观审慎，不使用“根据文件/数据显示”等引导语。输出一段 250-350 字。',
        '```',
        '',
        '## industry_review',
        '用于：人工智能、电子、医药生物、消费、金融地产、航天、电力设备新能源等行业段落',
        '',
        '```text',
        '{{query}}',
        '请撰写 {{param}} 行业周度点评，覆盖政策、供需、技术、价格或景气度变化。优先使用材料中的新闻和数据，避免外部知识、个股推荐和投资收益保证。输出一段 250-400 字。',
        '```',
        '',
        '## overseas_market',
        '用于：美国、欧洲、日本、海外市场',
        '',
        '```text',
        '{{query}}',
        '请概括 {{param}} 市场相关宏观、政策、利率、汇率、地缘或权益市场信息。只陈述材料内事实，并给出由事实支撑的审慎总结。输出一段 250-350 字。',
        '```',
        '',
        '## overseas_news',
        '用于：美国新闻、欧洲新闻',
        '',
        '```text',
        '{{query}}',
        '提炼影响当地权益、债券、汇率或风险偏好的核心新闻。保留事实链条，避免无依据推断。输出一段 150-250 字。',
        '```',
        '',
        '## overseas_hk_tech',
        '用于：港股科技',
        '',
        '```text',
        '{{query}}',
        '概括港股科技相关板块、政策、产业和上市公司动态。若提及个股，仅作为事实示例，不构成投资建议。输出一段 250-350 字。',
        '```',
        '',
        '## overseas_hk_dividend',
        '用于：港股央企红利',
        '',
        '```text',
        '{{query}}',
        '概括港股央企红利相关行业、政策、资金偏好和高股息资产变化。不得直接推荐买入或承诺收益。输出一段 250-350 字。',
        '```',
        '',
        '## commodity_market',
        '用于：原油、黄金',
        '',
        '```text',
        '{{query}}',
        '围绕 {{param}} 的供需、政策、美元/利率、地缘风险和资金面变化撰写周度点评。只使用材料内信息，输出一段 200-300 字。',
        '```',
        ''
    ].join('\n');
}

function setTemplateAdvancedDrawerOpen(open) {
    const drawer = document.getElementById('template-advanced-drawer');
    const backdrop = document.getElementById('template-advanced-drawer-backdrop');
    if (!drawer || !backdrop) return;
    drawer.classList.toggle('hidden', !open);
    backdrop.classList.toggle('hidden', !open);
    drawer.setAttribute('aria-hidden', open ? 'false' : 'true');
    if (open) {
        renderSelectedSourceFragment(getCurrentWorkbenchTemplate() || {});
    }
}

function restoreTemplateConfigEditorModalContent() {
    const modalState = currentTemplateState.configEditModal;
    if (!modalState?.contentNode || !modalState.parentNode) {
        currentTemplateState.configEditModal = null;
        return;
    }
    if (modalState.action === 'placeholder') {
        setPlaceholderEditorVisibility(modalState.contentNode, 'all');
    }
    if (modalState.parentNode.isConnected) {
        const nextSibling = modalState.nextSibling?.parentNode === modalState.parentNode
            ? modalState.nextSibling
            : null;
        modalState.parentNode.insertBefore(modalState.contentNode, nextSibling);
    } else {
        modalState.contentNode.remove();
    }
    currentTemplateState.configEditModal = null;
}

function openTemplateConfigEditorModal({
    title = '编辑配置',
    subtitle = '调整当前配置项',
    contentNode,
    action = ''
} = {}) {
    const modal = document.getElementById('template-config-editor-modal');
    const body = document.getElementById('template-config-editor-modal-body');
    const titleEl = document.getElementById('template-config-editor-modal-title');
    const subtitleEl = document.getElementById('template-config-editor-modal-subtitle');
    const saveBtn = document.getElementById('btn-template-config-editor-modal-save');
    if (!modal || !body || !contentNode) return;

    restoreTemplateConfigEditorModalContent();
    currentTemplateState.configEditModal = {
        contentNode,
        parentNode: contentNode.parentNode,
        nextSibling: contentNode.nextSibling,
        action
    };
    body.innerHTML = '';
    body.appendChild(contentNode);
    if (titleEl) titleEl.textContent = title;
    if (subtitleEl) subtitleEl.textContent = subtitle;
    if (saveBtn) {
        saveBtn.dataset.configModalAction = action;
        saveBtn.innerHTML = `<i class="codicon codicon-save"></i> ${action === 'common' ? '保存共用参数' : '保存配置'}`;
    }
    modal.dataset.configEditorSection = contentNode.dataset.activeEditorSection || '';
    modal.classList.remove('hidden');
    modal.setAttribute('aria-hidden', 'false');
    const closeBtn = document.getElementById('btn-template-config-editor-modal-close');
    window.requestAnimationFrame(() => closeBtn?.focus?.({ preventScroll: true }));
}

function closeTemplateConfigEditorModal() {
    const modal = document.getElementById('template-config-editor-modal');
    const action = currentTemplateState.configEditModal?.action || '';
    restoreTemplateConfigEditorModalContent();
    if (action === 'common') {
        setCommonRuleEditingSection('');
    } else if (action === 'placeholder') {
        setPlaceholderEditingSection('');
    }
    if (modal) {
        modal.classList.add('hidden');
        modal.setAttribute('aria-hidden', 'true');
        delete modal.dataset.configEditorSection;
    }
    const template = getCurrentWorkbenchTemplate();
    if (template) {
        if (action === 'common') {
            collectCommonDefaultsDraft(template);
            refreshCommonConfigSurfaces(template);
        }
        renderSelectedPlaceholderDetail(template);
        renderSelectedSourceFragment(template);
    }
}

function saveTemplateConfigEditorModal() {
    const action = currentTemplateState.configEditModal?.action || '';
    if (action === 'common') {
        const template = getCurrentWorkbenchTemplate();
        if (template) {
            collectCommonDefaultsDraft(template);
            refreshCommonConfigSurfaces(template);
        }
        document.getElementById('btn-template-save-common-rules')?.click();
        closeTemplateConfigEditorModal();
        return;
    }
    if (action === 'placeholder') {
        const template = getCurrentWorkbenchTemplate();
        if (template) collectSelectedPlaceholderDraft(template);
        document.getElementById('btn-template-save-placeholder')?.click();
        closeTemplateConfigEditorModal();
    }
}

function bindTemplateWorkbenchActions() {
    const editBtn = document.getElementById('btn-template-edit-source');
    const saveBtn = document.getElementById('btn-template-save-source');
    const savePlaceholderBtn = document.getElementById('btn-template-save-placeholder');
    const advancedConfigBtn = document.getElementById('btn-template-advanced-config');
    const closeAdvancedConfigBtn = document.getElementById('btn-template-close-advanced-config');
    const showRunLogBtn = document.getElementById('btn-template-show-run-log');
    const advancedConfigBackdrop = document.getElementById('template-advanced-drawer-backdrop');
    const dryRunBtn = document.getElementById('btn-template-dry-run');
    const generateBtn = document.getElementById('btn-template-generate-report');
    const configAdvancedBtn = document.getElementById('btn-template-config-advanced');
    const prevPlaceholderBtn = document.getElementById('btn-template-prev-placeholder');
    const nextIncompleteBtn = document.getElementById('btn-template-next-incomplete-placeholder');
    const reviewPreflightBtn = document.getElementById('btn-template-review-preflight');
    const savePlaceholderNextBtn = document.getElementById('btn-template-save-next-placeholder');
    const configModal = document.getElementById('template-config-editor-modal');
    const closeConfigModalBtn = document.getElementById('btn-template-config-editor-modal-close');
    const cancelConfigModalBtn = document.getElementById('btn-template-config-editor-modal-cancel');
    const saveConfigModalBtn = document.getElementById('btn-template-config-editor-modal-save');
    const sourceEditor = document.getElementById('template-source-editor');
    const readinessPanel = document.getElementById('template-generation-readiness-panel');
    const placeholderIssueList = document.getElementById('template-placeholder-issue-list');

    bindTemplateDetailModeTabs();

    if (readinessPanel && !readinessPanel.dataset.bound) {
        readinessPanel.dataset.bound = 'true';
        readinessPanel.addEventListener('click', event => {
            const actionBtn = event.target.closest('[data-template-check-action]');
            if (!actionBtn) return;
            handleTemplateCheckAction(actionBtn);
        });
    }

    if (placeholderIssueList && !placeholderIssueList.dataset.bound) {
        placeholderIssueList.dataset.bound = 'true';
        placeholderIssueList.addEventListener('click', event => {
            const actionBtn = event.target.closest('[data-template-check-action]');
            if (!actionBtn) return;
            handleTemplateCheckAction(actionBtn);
        });
    }

    if (editBtn && sourceEditor && !editBtn.dataset.bound) {
        editBtn.dataset.bound = 'true';
        editBtn.addEventListener('click', () => {
            setTemplateSourceEditing(true);
            sourceEditor.focus();
        });
    }

	    if (saveBtn && sourceEditor && !saveBtn.dataset.bound) {
        saveBtn.dataset.bound = 'true';
        saveBtn.addEventListener('click', async () => {
            const key = sourceEditor.dataset.draftKey || 'report-template-source:draft';
            const sourceKind = sourceEditor.dataset.sourceKind || 'local_draft';
            saveBtn.disabled = true;
            const originalText = saveBtn.innerHTML;
            saveBtn.innerHTML = '<i class="codicon codicon-loading spin"></i> 保存中...';
            try {
                const content = buildSourceContentForSave(
                    getCurrentWorkbenchTemplate() || {},
                    sourceKind,
                    sourceEditor.value
                );
                if (currentTemplateState.selectedReportProject && sourceKind !== 'local_draft') {
                    const project = currentTemplateState.selectedReportProject;
                    const updatedProject = await apiCall(
                        'PUT',
                        `/api/report-projects/${encodeURIComponent(project.slug)}/source`,
                        {
                            source_kind: sourceKind,
                            content
                        }
                    );
                    currentTemplateState.selectedReportProject = updatedProject;
                    const selectedTemplate = (currentTemplateState.templates || []).find(template =>
                        template.report_project?.slug === project.slug
                    );
                    if (selectedTemplate) {
                        selectedTemplate.report_project = updatedProject;
                    }
                    toast('配置已保存到项目文件', 'success');
                } else {
                    localStorage.setItem(key, content);
                    toast('配置草稿已保存到本地', 'success');
                }
                setTemplateSourceEditing(false);
                renderSelectedSourceFragment(getCurrentWorkbenchTemplate() || {});
            } catch (e) {
                saveBtn.disabled = false;
                toast('保存配置失败: ' + e.message, 'error');
            } finally {
                saveBtn.innerHTML = originalText;
            }
	        });
	    }

    if (advancedConfigBtn && !advancedConfigBtn.dataset.bound) {
        advancedConfigBtn.dataset.bound = 'true';
        advancedConfigBtn.addEventListener('click', () => setTemplateAdvancedDrawerOpen(true));
    }

    if (configAdvancedBtn && !configAdvancedBtn.dataset.bound) {
        configAdvancedBtn.dataset.bound = 'true';
        configAdvancedBtn.addEventListener('click', () => setTemplateAdvancedDrawerOpen(true));
    }

    if (closeAdvancedConfigBtn && !closeAdvancedConfigBtn.dataset.bound) {
        closeAdvancedConfigBtn.dataset.bound = 'true';
        closeAdvancedConfigBtn.addEventListener('click', () => setTemplateAdvancedDrawerOpen(false));
    }

    if (showRunLogBtn && !showRunLogBtn.dataset.bound) {
        showRunLogBtn.dataset.bound = 'true';
        showRunLogBtn.addEventListener('click', () => {
            setTemplateAdvancedDrawerOpen(false);
            setStoredTemplateDetailMode('logs');
            applyTemplateDetailMode('logs');
        });
    }

    if (advancedConfigBackdrop && !advancedConfigBackdrop.dataset.bound) {
        advancedConfigBackdrop.dataset.bound = 'true';
        advancedConfigBackdrop.addEventListener('click', () => setTemplateAdvancedDrawerOpen(false));
    }

	    if (savePlaceholderBtn && !savePlaceholderBtn.dataset.bound) {
	        savePlaceholderBtn.dataset.bound = 'true';
        savePlaceholderBtn.addEventListener('click', () => saveCurrentSectionConfig({
            button: savePlaceholderBtn,
            savingHtml: '<i class="codicon codicon-loading spin"></i> 保存中...',
            successMessage: '占位符配置已保存',
            localMessage: '占位符配置草稿已保存到本地',
            errorPrefix: '保存占位符失败'
        }));
    }

    if (savePlaceholderNextBtn && !savePlaceholderNextBtn.dataset.bound) {
        savePlaceholderNextBtn.dataset.bound = 'true';
        savePlaceholderNextBtn.addEventListener('click', () => saveCurrentSectionConfig({
            button: savePlaceholderNextBtn,
            savingHtml: '<i class="codicon codicon-loading spin"></i> 保存中...',
            successMessage: '占位符配置已保存，已跳到下一个未完成项',
            localMessage: '占位符配置草稿已保存，已跳到下一个未完成项',
            errorPrefix: '保存占位符失败',
            jumpToNextIncomplete: true
        }));
    }

    if (prevPlaceholderBtn && !prevPlaceholderBtn.dataset.bound) {
        prevPlaceholderBtn.dataset.bound = 'true';
        prevPlaceholderBtn.addEventListener('click', () => selectAdjacentTemplatePlaceholder(-1, false));
    }

    if (nextIncompleteBtn && !nextIncompleteBtn.dataset.bound) {
        nextIncompleteBtn.dataset.bound = 'true';
        nextIncompleteBtn.addEventListener('click', () => selectAdjacentTemplatePlaceholder(1, true));
    }

    if (reviewPreflightBtn && !reviewPreflightBtn.dataset.bound) {
        reviewPreflightBtn.dataset.bound = 'true';
        reviewPreflightBtn.addEventListener('click', () => openProjectCheckPanel('template-validation-preview'));
    }

    if (closeConfigModalBtn && !closeConfigModalBtn.dataset.bound) {
        closeConfigModalBtn.dataset.bound = 'true';
        closeConfigModalBtn.addEventListener('click', closeTemplateConfigEditorModal);
    }

    if (cancelConfigModalBtn && !cancelConfigModalBtn.dataset.bound) {
        cancelConfigModalBtn.dataset.bound = 'true';
        cancelConfigModalBtn.addEventListener('click', closeTemplateConfigEditorModal);
    }

    if (saveConfigModalBtn && !saveConfigModalBtn.dataset.bound) {
        saveConfigModalBtn.dataset.bound = 'true';
        saveConfigModalBtn.addEventListener('click', saveTemplateConfigEditorModal);
    }

    if (configModal && !configModal.dataset.boundBackdropClose) {
        configModal.dataset.boundBackdropClose = 'true';
        configModal.addEventListener('click', event => {
            if (event.target === configModal) closeTemplateConfigEditorModal();
        });
    }

    if (dryRunBtn && !dryRunBtn.dataset.bound) {
        dryRunBtn.dataset.bound = 'true';
        dryRunBtn.addEventListener('click', () => {
            const statusEl = document.getElementById('template-validation-status');
            if (statusEl) {
                statusEl.textContent = '已预检';
                statusEl.classList.remove('warning');
            }
            toast('已完成前端预检；真实生成校验下一版接入', 'info');
        });
    }

    if (generateBtn && !generateBtn.dataset.bound) {
        generateBtn.dataset.bound = 'true';
        generateBtn.addEventListener('click', async () => {
            const template = getCurrentWorkbenchTemplate() || {};
            renderReportGenerationProgressCard({
                activeKey: 'check',
                message: '正在检查当前模板、占位符和本地草稿'
            });
            if (sourceEditor?.dataset.draftKey) {
                localStorage.setItem(
                    sourceEditor.dataset.draftKey,
                    buildSourceContentForSave(template, sourceEditor.dataset.sourceKind || 'local_draft', sourceEditor.value)
                );
            }

            const preflight = getTemplateGenerationPreflight(template);
            if (!preflight.ok) {
                blockReportGenerationForPreflight(preflight);
                return;
            }

            generateBtn.disabled = true;
            generateBtn.innerHTML = '<i class="codicon codicon-loading spin"></i> 生成中...';
            try {
                await renderReportFromTemplate({ inlineProgress: true });
                setGenerationFlowState('refresh', '生成完成', '已完成');
                toggleFlowActions(false);
                generateBtn.innerHTML = '<i class="codicon codicon-play"></i> 生成报告';
                toast('报告生成完成', 'success');
            } catch (e) {
                renderReportGenerationFailure(e);
                toast('生成失败: ' + e.message, 'error');
            } finally {
                generateBtn.disabled = false;
            }
        });
    }
}

async function saveCurrentSectionConfig({
    button,
    savingHtml = '<i class="codicon codicon-loading spin"></i> 保存中...',
    successMessage = '配置已保存',
    localMessage = '配置草稿已保存到本地',
    errorPrefix = '保存配置失败',
    jumpToNextIncomplete = false
} = {}) {
    const template = getCurrentWorkbenchTemplate();
    if (!template) {
        toast('请先选择模板', 'error');
        return;
    }
    updateTemplateSourceFromPlaceholderDraft(template);
    markSelectedPlaceholderConfirmed(template);

    const sourceEditor = document.getElementById('template-source-editor');
    const mappings = getEditablePlaceholderMappings(template);
    const saveKind = 'report_config';
    const content = buildUpdatedReportConfigSource(template, mappings);
    const selectedName = normalizePlaceholderName(currentTemplateState.selectedPlaceholderName);
    const selectedMapping = selectedName ? mappings.get(selectedName) : null;
    const originalText = button?.innerHTML;
    if (button) {
        button.disabled = true;
        button.innerHTML = savingHtml;
    }

    try {
        if (currentTemplateState.selectedReportProject) {
            const project = currentTemplateState.selectedReportProject;
            let updatedProject = await apiCall(
                'PUT',
                `/api/report-projects/${encodeURIComponent(project.slug)}/source`,
                {
                    source_kind: saveKind,
                    content
                }
            );
            const promptTemplatesContent = buildUpdatedPromptTemplatesSourceFromQuery(
                { ...template, report_project: updatedProject },
                selectedMapping,
                selectedName
            );
            if (promptTemplatesContent) {
                updatedProject = await apiCall(
                    'PUT',
                    `/api/report-projects/${encodeURIComponent(project.slug)}/source`,
                    {
                        source_kind: 'prompt_templates',
                        content: promptTemplatesContent
                    }
                );
            }
            currentTemplateState.selectedReportProject = updatedProject;
            const selectedTemplate = (currentTemplateState.templates || []).find(item =>
                item.report_project?.slug === project.slug
            );
            if (selectedTemplate) selectedTemplate.report_project = updatedProject;
            renderAdvancedMaintenance(selectedTemplate || template);
            if (jumpToNextIncomplete) {
                selectAdjacentTemplatePlaceholder(1, true);
            }
            toast(successMessage, 'success');
        } else {
            localStorage.setItem(sourceEditor?.dataset.draftKey || 'report-template-source:draft', content);
            renderSelectedPlaceholderDetail(template);
            if (jumpToNextIncomplete) {
                selectAdjacentTemplatePlaceholder(1, true);
            }
            toast(localMessage, 'success');
        }
        if (!jumpToNextIncomplete) {
            renderPlaceholderSaveFeedback('已保存当前段落。');
        }
    } catch (e) {
        toast(`${errorPrefix}: ${e.message}`, 'error');
    } finally {
        if (button) {
            button.innerHTML = originalText;
            button.disabled = false;
        }
    }
}

function handleTemplateCheckAction(actionBtn) {
    const action = actionBtn.dataset.templateCheckAction;
    const target = actionBtn.dataset.templateCheckTarget || '';
    const placeholderName = normalizePlaceholderName(actionBtn.dataset.templatePlaceholderName || '');

    if (action === 'upload') {
        openUploadModalForField(target);
        return;
    }

    if (action === 'focus-check') {
        openProjectCheckPanel(target);
        return;
    }

    if (action === 'focus-placeholder') {
        const template = getCurrentWorkbenchTemplate();
        if (!template || !placeholderName) return;
        const item = {
            editorSection: actionBtn.dataset.templatePlaceholderEditorSection || 'basic'
        };
        setStoredTemplateDetailMode('config');
        applyTemplateDetailMode('config');
        selectTemplatePlaceholder(placeholderName);
        openPlaceholderConfigEditorModal(template, item.editorSection || 'basic');
        return;
    }

    if (action === 'open-logs') {
        setStoredTemplateDetailMode('logs');
        applyTemplateDetailMode('logs');
        highlightWorkbenchTarget(document.getElementById('template-generation-log-panel'));
        return;
    }

    if (action === 'open-advanced') {
        if (placeholderName) {
            const template = getCurrentWorkbenchTemplate();
            if (template) {
                currentTemplateState.selectedPlaceholderName = placeholderName;
                renderAdvancedMaintenance(template);
            }
        }
        openAdvancedMaintenance(target);
    }
}

function openUploadModalForField(fieldId) {
    openUploadModal();
    const template = getCurrentWorkbenchTemplate();
    const nameInput = document.getElementById('template-name-input');
    if (nameInput && template) {
        nameInput.value = template.report_project?.name || template.template_name || template.name || '';
    }
    const field = document.getElementById(fieldId);
    if (field) highlightWorkbenchTarget(field.closest('.form-field') || field);
    field?.focus();
}

function setTemplateSourceEditing(editing) {
    const sourceEditor = document.getElementById('template-source-editor');
    const editBtn = document.getElementById('btn-template-edit-source');
    const saveBtn = document.getElementById('btn-template-save-source');
    if (sourceEditor) {
        sourceEditor.readOnly = !editing;
        sourceEditor.classList.toggle('readonly', !editing);
        sourceEditor.classList.toggle('editing', editing);
    }
    if (editBtn) {
        editBtn.disabled = editing;
    }
    if (saveBtn) {
        saveBtn.disabled = !editing;
    }
}

// ─── Tab Switching ─────────────────────────────────────────────
function switchTemplatesTab(tabName) {
    const detailViewActive = !document.getElementById('template-detail-view').classList.contains('hidden');

    if (detailViewActive && (tabName === 'detail-configure' || tabName === 'detail-render')) {
        document.querySelectorAll('#template-detail-view .tab-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('#template-detail-view .tab-panel').forEach(p => p.classList.add('hidden'));
        document.querySelector(`#template-detail-view .tab-btn[data-tab="${tabName}"]`)?.classList.add('active');
        document.getElementById(`tab-${tabName}`)?.classList.remove('hidden');
    } else {
        document.querySelectorAll('#section-templates .tab-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('#section-templates .tab-panel').forEach(p => p.classList.add('hidden'));
        document.querySelector(`#section-templates .tab-btn[data-tab="${tabName}"]`)?.classList.add('active');
        document.getElementById(`tab-${tabName}`)?.classList.remove('hidden');
    }
}

// ─── Upload Drop Zone ──────────────────────────────────────────
function initTemplateDropZone() {
    const dropZone = document.getElementById('template-drop-zone');
    const fileInput = document.getElementById('template-file-input');

    if (!dropZone || !fileInput) return;

    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('dragover');
    });

    dropZone.addEventListener('dragleave', () => {
        dropZone.classList.remove('dragover');
    });

    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('dragover');
        const files = e.dataTransfer.files;
        if (files.length) {
            handleTemplateFileSelect(files[0]);
        }
    });

    dropZone.addEventListener('click', () => {
        fileInput.click();
    });

    fileInput.addEventListener('change', (e) => {
        if (e.target.files?.[0]) {
            handleTemplateFileSelect(e.target.files[0]);
        }
    });

    const chooseBtn = document.getElementById('btn-choose-file');
    if (chooseBtn) {
        chooseBtn.addEventListener('click', () => {
            fileInput.click();
        });
    }

    const clearBtn = document.getElementById('btn-clear-file');
    if (clearBtn) {
        clearBtn.addEventListener('click', () => {
            clearFileSelection();
        });
    }
}

async function handleTemplateFileSelect(file) {
    if (!file.name.match(/\.(pptx|docx|xlsx)$/i)) {
        toast('请上传 .pptx、.docx 或 .xlsx 文件', 'error');
        return;
    }

    const fileNameEl = document.getElementById('selected-file-name');
    const fileInfoEl = document.getElementById('selected-file-info');

    if (fileNameEl) fileNameEl.textContent = file.name;
    if (fileInfoEl) fileInfoEl.classList.remove('hidden');
}

function clearFileSelection() {
    const fileNameEl = document.getElementById('selected-file-name');
    const fileInfoEl = document.getElementById('selected-file-info');
    const fileInput = document.getElementById('template-file-input');

    if (fileNameEl) fileNameEl.textContent = '';
    if (fileInfoEl) fileInfoEl.classList.add('hidden');
    if (fileInput) fileInput.value = '';
}

// ─── Upload / Download / Delete ────────────────────────────────
async function uploadTemplate() {
    const nameInput = document.getElementById('template-name-input');
    const projectTypeSelect = document.getElementById('project-type-select');
    const wordInput = document.getElementById('project-word-template-input');
    const pptInput = document.getElementById('project-ppt-template-input');
    const excelInput = document.getElementById('project-excel-workbook-input');
    const reportConfigInput = document.getElementById('project-report-config-input');
    const promptInput = document.getElementById('project-prompt-templates-input');
    const dataFilesInput = document.getElementById('project-data-files-input');
    const statusEl = document.getElementById('template-upload-status');

    const projectName = nameInput?.value.trim();
    const projectType = projectTypeSelect?.value === 'ppt' ? 'ppt' : 'word';
    const wordFile = wordInput?.files?.[0];
    const pptFile = pptInput?.files?.[0];
    const excelFile = excelInput?.files?.[0];
    const reportConfigFile = reportConfigInput?.files?.[0];

    if (!projectName) {
        toast('请输入报告项目名称', 'error');
        return;
    }
    if (projectType === 'word' && !wordFile) {
        toast('请选择 Word 模板', 'error');
        return;
    }
    if (projectType === 'ppt' && !pptFile) {
        toast('请选择 PPT 模板', 'error');
        return;
    }

    if (statusEl) {
        statusEl.innerHTML = '<div class="loading"><div class="spinner"></div><span>正在创建报告项目...</span></div>';
        statusEl.classList.remove('hidden');
    }

    const formData = new FormData();
    formData.append('project_name', projectName);
    formData.append('project_type', projectType);
    if (projectType === 'ppt') {
        formData.append('ppt_template', pptFile);
    } else {
        formData.append('word_template', wordFile);
    }
    if (excelFile) {
        formData.append('excel_workbook', excelFile);
    }
    if (reportConfigFile) {
        formData.append('report_config', reportConfigFile);
    }
    if (promptInput?.files?.[0]) {
        formData.append('prompt_templates', promptInput.files[0]);
    }
    Array.from(dataFilesInput?.files || []).forEach(file => {
        formData.append('data_files', file);
    });

    try {
        const response = await fetch('/api/report-projects/upload', {
            method: 'POST',
            headers: { 'Authorization': 'Bearer dummy' },
            body: formData
        });

        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: 'Upload failed' }));
            throw new Error(error.detail || 'Upload failed');
        }

        const data = await response.json();
        toast('报告项目已创建', 'success');
        try {
            await loadReportProjectsList();
            await loadTemplatesList();
            await initTemplateSelects();
            await enterFirstPlaceholderConfigurationMode(data);
        } catch (e) {
            console.warn('Failed to refresh templates after report project creation:', e);
            toast('报告项目已创建，但模板列表刷新失败，请稍后重试。', 'warning');
        }
        closeUploadModal();

        if (nameInput) nameInput.value = '';
        [wordInput, pptInput, excelInput, sectionInput, promptInput, dataFilesInput].forEach(input => {
            if (input) input.value = '';
        });
        REPORT_UPLOAD_FILE_INPUTS.forEach(updateReportProjectUploadFileLabel);
    } catch (e) {
        toast('创建报告项目失败: ' + e.message, 'error');
    } finally {
        if (statusEl) statusEl.classList.add('hidden');
    }
}

async function enterFirstPlaceholderConfigurationMode(project) {
    const templateName = project?.project_name || project?.name || project?.template_name || '';
    if (!templateName) return;
    try {
        await selectTemplate(templateName, project?.project_type === 'ppt' ? 'pptx' : 'docx');
        const template = getCurrentWorkbenchTemplate();
        if (!template) return;
        setStoredTemplateDetailMode('config');
        applyTemplateDetailMode('config');
        selectFirstActionablePlaceholder(template);
        renderPlaceholderWizardControls(template);
        toast('首次配置：请逐个确认占位符用途和来源', 'info');
    } catch (e) {
        console.warn('Failed to enter first placeholder configuration mode', e);
    }
}

async function downloadTemplateFile(name, type) {
    try {
        window.open(`/api/templates/files/${encodeURIComponent(name)}/${type}`, '_blank');
    } catch (e) {
        toast('下载失败: ' + e.message, 'error');
    }
}

async function deleteTemplate(name) {
    if (!confirm(`确定要删除模板 "${name}" 吗？`)) return;

    try {
        await apiCall('DELETE', `/api/templates/${encodeURIComponent(name)}`);
        toast('模板已删除', 'success');
        await loadTemplatesList();
        await initTemplateSelects();

        if (currentTemplateState.selectedTemplate === name) {
            currentTemplateState.selectedTemplate = null;
        }
    } catch (e) {
        toast('删除失败: ' + e.message, 'error');
    }
}

// ─── YAML Config ───────────────────────────────────────────────
async function createYamlConfig() {
    const name = document.getElementById('template-name-input')?.value.trim();
    const description = document.getElementById('template-desc-input')?.value.trim();
    const yamlContent = prompt('请输入YAML配置:');

    if (!name) {
        toast('请输入模板名称', 'error');
        return;
    }

    if (!yamlContent) {
        toast('请输入YAML配置', 'error');
        return;
    }

    try {
        await apiCall('POST', '/api/templates/create-yaml', {
            name,
            description,
            yaml_content: yamlContent
        });
        toast('YAML配置创建成功', 'success');
        await loadTemplatesList();
        await initTemplateSelects();
    } catch (e) {
        toast('创建失败: ' + e.message, 'error');
    }
}

// ─── Render Report ─────────────────────────────────────────────
async function renderReportFromTemplate(options = {}) {
    const templateSelect = document.getElementById('render-template-select');
    const typeSelect = document.getElementById('render-type-select');
    const canonicalIdInput = document.getElementById('render-canonical-id');
    const reportTypeSelect = document.getElementById('render-report-type');

    const templateName = templateSelect?.value || currentTemplateState.selectedTemplate;
    const fileType = typeSelect?.value || currentTemplateState.selectedFileType || 'docx';
    const canonicalId = canonicalIdInput?.value.trim() || null;
    const reportType = reportTypeSelect?.value || 'full';

    if (!templateName) {
        const error = new Error('请先选择一个模板');
        if (options.inlineProgress) throw error;
        toast(error.message, 'error');
        return null;
    }

    const loadingEl = document.getElementById('render-loading');
    const resultEl = document.getElementById('render-result');

    if (loadingEl) loadingEl.classList.remove('hidden');
    if (resultEl) resultEl.classList.add('hidden');

    try {
        let result;
        if (options.inlineProgress) {
            renderReportGenerationProgressCard({
                activeKey: 'check',
                message: '已提交后台生成任务，等待后台调度引擎'
            });
        }

        if (!canonicalId && currentTemplateState.selectedReportProject) {
            result = await renderReportProject(currentTemplateState.selectedReportProject);
        } else if (canonicalId) {
            result = await apiCall('POST', '/api/templates/render-from-asset', {
                template_name: templateName,
                file_type: fileType,
                canonical_id: canonicalId,
                report_type: reportType,
                additional_placeholders: currentTemplateState.placeholderValues
            });
        } else {
            result = await apiCall('POST', '/api/templates/render', {
                template_name: templateName,
                file_type: fileType,
                placeholders: currentTemplateState.placeholderValues
            });
        }

        currentTemplateState.renderedReportId = result.report_id || result.file_name || null;
        if (result?.file_name) {
            currentTemplateState.selectedGeneratedReportFile = result.file_name;
        }
        if (result?.run_log_url) {
            currentTemplateState.lastReportGenerationResult = result;
            try {
                currentTemplateState.lastReportRunLog = await apiCall('GET', result.run_log_url);
            } catch (logError) {
                console.warn('Failed to load report generation run log', logError);
                currentTemplateState.lastReportRunLog = null;
            }
        }
        const renderedProjectSlug = currentTemplateState.selectedReportProject?.slug;
        if (renderedProjectSlug) {
            if (options.inlineProgress) {
                renderReportGenerationProgressCard({
                    activeKey: 'refresh',
                    message: '报告已写入 Word，正在刷新最近版本和预览入口'
                });
            }
            try {
                const projects = await loadReportProjectsList();
                const refreshedProject = (projects || []).find(project => project.slug === renderedProjectSlug);
                const selectedTemplate = getCurrentWorkbenchTemplate();
                if (selectedTemplate && refreshedProject) {
                    selectedTemplate.report_project = refreshedProject;
                    currentTemplateState.selectedReportProject = refreshedProject;
                    renderReportGenerationCenter(selectedTemplate);
                }
            } catch (refreshError) {
                console.warn('生成后刷新项目列表失败，报告已成功生成', refreshError);
            }
        }

        if (resultEl) {
            const downloadUrl = result.download_url
                || (result.report_id ? `/api/templates/download/${encodeURIComponent(result.report_id)}` : null);
            const previewUrl = result.preview_url || null;
            const downloadLink = document.getElementById('render-download-link');
            if (downloadLink && downloadUrl) {
                downloadLink.href = downloadUrl;
            }
            resultEl.innerHTML = `
                <div class="success-message">
                    <i class="codicon codicon-pass"></i>
                    <span>报告渲染成功！</span>
                </div>
                <div class="render-result-actions">
                    <a id="render-download-link" href="${esc(downloadUrl || '#')}"
                       class="btn-primary" target="_blank">下载报告</a>
                    ${previewUrl ? `<a href="${esc(previewUrl)}" class="btn-secondary" target="_blank">打开预览</a>` : ''}
                </div>
                ${previewUrl ? `
                    <div class="report-preview-shell">
                        <div class="report-preview-header">
                            <strong>Word 内容预览</strong>
                            <span>生成后自动刷新</span>
                        </div>
                        <div id="render-preview-content" class="report-preview-content">
                            <div class="loading compact"><div class="spinner"></div><span>正在加载预览...</span></div>
                        </div>
                    </div>
                ` : ''}
            `;
            resultEl.classList.remove('hidden');
            if (previewUrl) {
                await loadRenderedReportPreview(previewUrl);
            }
        }
        return result;
    } catch (e) {
        if (options.inlineProgress) {
            // 清除进度卡片，显示失败状态
            renderReportGenerationFailure(e);
            toast('渲染失败: ' + e.message, 'error');
            throw e;
        }
        toast('渲染失败: ' + e.message, 'error');
        return null;
    } finally {
        if (loadingEl) loadingEl.classList.add('hidden');
    }
}

async function loadRenderedReportPreview(previewUrl) {
    const container = document.getElementById('render-preview-content');
    if (!container) return;
    try {
        const response = await fetch(previewUrl, { credentials: 'same-origin' });
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        container.innerHTML = await response.text();
    } catch (error) {
        container.innerHTML = `<div class="empty-state compact">预览加载失败：${esc(error.message)}</div>`;
    }
}

async function renderReportProject(project) {
    if (!project?.slug) {
        throw new Error('报告项目未绑定');
    }
    const generationOptions = getReportProjectGenerationOptions();

    const job = await apiCall(
        'POST',
        `/api/report-projects/${encodeURIComponent(project.slug)}/render-jobs`,
        {
            placeholders: currentTemplateState.placeholderValues || {},
            report_date: generationOptions.report_date || null,
            start_date: generationOptions.start_date || null,
            end_date: generationOptions.end_date || null,
            lookback_days: generationOptions.lookback_days || 7
        }
    );
    return pollReportGenerationJob(job);
}

async function pollReportGenerationJob(initialJob) {
    const deadline = Date.now() + (40 * 60 * 1000);
    const jobId = initialJob?.job_id || 'unknown';
    const statusUrl = initialJob?.status_url;
    let job = initialJob;
    let consecutiveNetworkFailures = 0;

    if (!statusUrl) {
        throw new Error('后台生成任务缺少状态地址');
    }

    while (Date.now() < deadline) {
        updateReportGenerationJobProgress(job);
        if (job.status === 'completed') {
            if (!job.result) throw new Error('报告生成完成，但后端未返回文件信息');
            return job.result;
        }
        if (job.status === 'failed') {
            throw new Error(job.error || job.message || '报告生成失败');
        }

        await waitForReportGenerationPoll(1500);
        try {
            job = await apiCall('GET', statusUrl);
            consecutiveNetworkFailures = 0;
        } catch (error) {
            consecutiveNetworkFailures += 1;
            if (consecutiveNetworkFailures >= 3) {
                throw new Error(`生成进度连接连续失败：${error.message}（任务 ${jobId} 可能仍在后台运行）`);
            }
            await waitForReportGenerationPoll(1000 * consecutiveNetworkFailures);
        }
    }

    throw new Error(`等待生成结果超时（任务 ${jobId} 可能仍在后台运行）`);
}

let _evidenceStepEnteredAt = null;

function updateReportGenerationJobProgress(job) {
    const completed = Number(job?.completed_sections || 0);
    const total = Number(job?.total_sections || 0);
    const sectionProgress = total > 0 ? `（${completed}/${total} 个段落）` : '';
    const phase = job?.phase || '';

    let activeKey;
    if (phase === 'queued') {
        activeKey = 'check';
        _evidenceStepEnteredAt = null;
    } else if (phase === 'prepare') {
        activeKey = 'mapping';
        _evidenceStepEnteredAt = null;
    } else if (phase === 'generate') {
        if (_evidenceStepEnteredAt === null) {
            _evidenceStepEnteredAt = Date.now();
        }
        activeKey = (Date.now() - _evidenceStepEnteredAt < 4000)
            ? 'evidence'
            : 'generate';
    } else if (phase === 'render') {
        activeKey = 'write';
        _evidenceStepEnteredAt = null;
    } else if (phase === 'save' || job?.status === 'completed') {
        activeKey = 'refresh';
        _evidenceStepEnteredAt = null;
    } else {
        activeKey = 'generate';
    }

    renderReportGenerationProgressCard({
        activeKey,
        message: `${job?.message || '正在后台生成报告'}${sectionProgress}`
    });
}

function waitForReportGenerationPoll(milliseconds) {
    return new Promise(resolve => window.setTimeout(resolve, milliseconds));
}

function getReportProjectGenerationOptions() {
    const defaults = getEditableCommonDefaults(getCurrentWorkbenchTemplate() || {});
    const savedPeriod = defaults.report_period || {};
    const draftPeriod = currentTemplateState.commonDefaultsDraft?.report_period || {};
    const lookbackDays = Math.max(
        1,
        Math.min(90, Number(draftPeriod.lookback_days || savedPeriod.lookback_days || 7))
    );
    const reportDate = String(draftPeriod.report_date || getDefaultReportDate()).trim();
    const startDate = getDefaultEvidenceStartDate(reportDate, lookbackDays);
    const endDate = reportDate;
    const project = getCurrentWorkbenchTemplate()?.report_project;
    return {
        report_date: reportDate,
        start_date: startDate,
        end_date: endDate,
        lookback_days: lookbackDays,
        output_format: project?.project_type === 'ppt' ? 'pptx' : 'docx'
    };
}

async function downloadRenderedReport(reportId) {
    try {
        window.open(`/api/templates/download/${encodeURIComponent(reportId)}`, '_blank');
    } catch (e) {
        toast('下载失败: ' + e.message, 'error');
    }
}

// ─── Save / Export Placeholder Config ──────────────────────────
async function savePlaceholderConfig() {
    const templateName = document.getElementById('configure-template-select')?.value;
    const fileType = document.getElementById('configure-type-select')?.value || 'docx';

    if (!templateName) {
        toast('请先选择模板', 'error');
        return;
    }

    const config = {
        template_name: templateName,
        file_type: fileType,
        placeholders: currentTemplateState.placeholderConfigs || {}
    };

    try {
        await apiCall('POST', '/api/templates/config', config);
        toast('配置保存成功', 'success');
    } catch (e) {
        toast('保存配置失败: ' + e.message, 'error');
    }
}

async function exportYamlConfig() {
    const templateName = document.getElementById('configure-template-select')?.value;
    const fileType = document.getElementById('configure-type-select')?.value || 'docx';

    if (!templateName) {
        toast('请先选择模板', 'error');
        return;
    }

    const config = {
        name: templateName,
        description: `${templateName} 模板配置`,
        file_type: fileType,
        placeholders: currentTemplateState.placeholderConfigs || {}
    };

    const yaml = jsYaml.dump(config, { indent: 2 });

    const blob = new Blob([yaml], { type: 'application/x-yaml' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${templateName}_config.yaml`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    toast('YAML配置导出成功', 'success');
}

// ─── AI Content Generation ─────────────────────────────────────
async function generateAiContent(placeholderName) {
    const config = currentTemplateState.placeholderConfigs?.[placeholderName] || {};
    const prompt = config.prompt;

    if (!prompt) {
        toast('该占位符没有配置生成提示词，请先在配置页面设置', 'error');
        return;
    }

    const btn = document.querySelector(`.render-placeholder-item:has([data-placeholder-name="${esc(placeholderName)}"]) .btn-ai-generate`);
    const input = document.querySelector(`.render-placeholder-item [data-placeholder-name="${esc(placeholderName)}"]`);

    if (btn) {
        btn.classList.add('loading');
        btn.disabled = true;
        btn.innerHTML = '<i class="codicon codicon-loading spin"></i> 生成中...';
    }

    try {
        const fullPrompt = `
请根据以下要求生成内容：
${prompt}

要求：
1. 内容符合券商研报的专业风格
2. 语言流畅，逻辑清晰
3. 不需要多余的解释和说明
4. 直接返回生成的内容即可
        `.trim();

        const result = await callLlmApi(fullPrompt);

        if (input && result) {
            input.value = result;
            updatePlaceholderValue(placeholderName, result);
            toast('生成成功', 'success');
        }
    } catch (e) {
        toast('生成失败: ' + e.message, 'error');
    } finally {
        if (btn) {
            btn.classList.remove('loading');
            btn.disabled = false;
            btn.innerHTML = '<i class="codicon codicon-hubot"></i> AI生成';
        }
    }
}

async function generateAllAiFields() {
    const configs = currentTemplateState.placeholderConfigs || {};
    const aiPlaceholders = Object.entries(configs)
        .filter(([name, config]) => config.type === 'rich_text' && config.prompt)
        .map(([name]) => name);

    if (aiPlaceholders.length === 0) {
        toast('没有需要生成的AI字段，请先配置占位符类型为"长文本/AI生成"并设置提示词', 'info');
        return;
    }

    const confirmBtn = confirm(`确定要生成所有 ${aiPlaceholders.length} 个AI字段吗？这可能需要一点时间。`);
    if (!confirmBtn) return;

    const btn = document.getElementById('btn-generate-all-ai');
    if (btn) {
        btn.classList.add('loading');
        btn.disabled = true;
        btn.innerHTML = '<i class="codicon codicon-loading spin"></i> 生成中...';
    }

    let successCount = 0;
    let failCount = 0;

    try {
        for (const name of aiPlaceholders) {
            try {
                await generateAiContent(name);
                successCount++;
                await new Promise(resolve => setTimeout(resolve, 1000));
            } catch (e) {
                console.error(`生成 ${name} 失败:`, e);
                failCount++;
            }
        }

        toast(`批量生成完成：成功 ${successCount} 个，失败 ${failCount} 个`, successCount > 0 ? 'success' : 'error');
    } finally {
        if (btn) {
            btn.classList.remove('loading');
            btn.disabled = false;
            btn.innerHTML = '<i class="codicon codicon-hubot"></i> 生成所有AI字段';
        }
    }
}

async function callLlmApi(prompt) {
    try {
        const response = await apiCall('POST', '/api/llm/generate', {
            prompt: prompt,
            temperature: 0.7,
            max_tokens: 2000
        });

        return response.content || response.result || response.text || '';
    } catch (e) {
        throw new Error(`LLM调用失败: ${e.message}`);
    }
}

// ─── Exports ───────────────────────────────────────────────────
export {
    loadTemplatesPage, loadTemplatesList, loadTemplates,
    renderTemplatesList, selectTemplate, loadTemplateDetails, goBackToTemplates,
    openUploadModal, closeUploadModal,
    handleTemplatePointerDown,
    handleDragStart, handleDragOver, getDragAfterElement, handleDrop,
    openEditTemplateModal, closeEditTemplateModal, saveTemplateEdit,
    toggleEditMode, saveTemplatesOrder,
    clearPlaceholderData, initTemplateSelects, discoverPlaceholders,
    renderPlaceholders, updatePlaceholderConfig, updatePlaceholderValue,
    loadTemplatePlaceholdersForRender, renderRenderPlaceholders,
    switchTemplatesTab, initTemplateDropZone,
    handleTemplateFileSelect, clearFileSelection,
    uploadTemplate, downloadTemplateFile, deleteTemplate,
    createYamlConfig, renderReportFromTemplate, downloadRenderedReport,
    savePlaceholderConfig, exportYamlConfig,
    generateAiContent, generateAllAiFields, callLlmApi,
    handleTemplateNameKeydown, saveTemplateInlineName
};
