/* ============================================================
   Research Workbench — Templates Module
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
    activeSourceKind: 'section_config',
    lastReportGenerationResult: null,
    lastReportRunLog: null
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
    { key: 'check', label: '准备模板资产', icon: 'codicon-checklist' },
    { key: 'mapping', label: '读取底稿映射', icon: 'codicon-table' },
    { key: 'evidence', label: '检索证据与新闻', icon: 'codicon-search' },
    { key: 'generate', label: '生成段落内容', icon: 'codicon-symbol-keyword' },
    { key: 'write', label: '渲染 Word 文档', icon: 'codicon-file-code' },
    { key: 'refresh', label: '完成输出', icon: 'codicon-open-preview' }
];
const TEMPLATE_DETAIL_MODES = ['generation', 'config', 'preview', 'logs'];
const TEMPLATE_DETAIL_MODE_KEY = 'report-template-detail-mode';
const REPORT_UPLOAD_FILE_INPUTS = [
    'project-word-template-input',
    'project-excel-workbook-input',
    'project-section-config-input',
    'project-prompt-templates-input',
    'project-data-files-input'
];

// ─── Template Page / List ──────────────────────────────────────
async function loadTemplatesPage() {
    try {
        await loadReportProjectsList();
        await loadTemplatesList();
        initTemplateDropZone();
        initReportProjectUploadInputs();
        await initTemplateSelects();
    } catch (e) {
        toast('加载模板页面失败: ' + e.message, 'error');
    }
}

async function loadTemplatesList() {
    let templateData = { templates: [] };

    try {
        await loadReportProjectsList();
    } catch (e) {
        console.warn('Failed to load report projects before templates:', e);
    }

    try {
        templateData = await apiCall('GET', '/api/templates/');
    } catch (e) {
        console.warn('Failed to load legacy templates:', e);
    }

    try {
        currentTemplateState.templates = mergeTemplatesWithReportProjects(
            templateData.templates || [],
            currentTemplateState.reportProjects || []
        );
        renderTemplatesList(currentTemplateState.templates);
    } catch (e) {
        console.error('Failed to render templates:', e);
        const container = document.getElementById('templates-grid');
        if (container) {
            container.innerHTML = '<div style="grid-column: 1/-1; text-align: center; padding: 60px 20px; color: var(--text-secondary);">模板加载失败</div>';
        }
    }
}

async function loadTemplates() {
    return loadTemplatesList();
}

async function loadReportProjectsList() {
    try {
        const data = await apiCall('GET', '/api/report-projects/');
        currentTemplateState.reportProjects = data.projects || [];
        return currentTemplateState.reportProjects;
    } catch (e) {
        console.warn('Failed to load report projects:', e);
        currentTemplateState.reportProjects = [];
        return [];
    }
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
    const wordPlaceholders = project?.word_placeholders;
    if (Array.isArray(wordPlaceholders) && wordPlaceholders.length) {
        return wordPlaceholders.map(normalizePlaceholderName).filter(Boolean);
    }

    const rawPlaceholders = project?.section_config?.placeholders;
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
    const projectSections = project?.section_config?.sections;
    if (Array.isArray(projectSections) && projectSections.length) {
        return projectSections;
    }

    const rawPlaceholders = project?.section_config?.placeholders;
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
        await loadReportProjectsList();
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

function renderTemplatesList(templates) {
    const container = document.getElementById('templates-grid');
    if (!container) return;

    if (!templates.length) {
        container.innerHTML = '<div style="grid-column: 1/-1; text-align: center; padding: 60px 20px; color: var(--text-secondary);">暂无模板，点击下方"上传"按钮添加</div>';
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
            iconHtml = '<i class="codicon codicon-file-media" style="font-size: 60px;"></i>';
        } else if (fileType === 'excel') {
            iconHtml = '<i class="codicon codicon-table" style="font-size: 60px;"></i>';
        } else {
            iconHtml = '<i class="codicon codicon-file-code" style="font-size: 60px;"></i>';
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
    REPORT_UPLOAD_FILE_INPUTS.forEach(inputId => {
        const input = document.getElementById(inputId);
        if (input) input.value = '';
        updateReportProjectUploadFileLabel(inputId);
    });
    document.getElementById('template-upload-status').innerHTML = '';
}

function closeUploadModal() {
    document.getElementById('upload-template-modal').classList.add('hidden');
}

function initReportProjectUploadInputs() {
    REPORT_UPLOAD_FILE_INPUTS.forEach(inputId => {
        const input = document.getElementById(inputId);
        if (!input || input.dataset.boundUploadLabel === 'true') return;
        input.dataset.boundUploadLabel = 'true';
        input.addEventListener('change', () => updateReportProjectUploadFileLabel(inputId));
        updateReportProjectUploadFileLabel(inputId);
    });
}

function updateReportProjectUploadFileLabel(inputId) {
    const input = document.getElementById(inputId);
    const label = document.querySelector(`[data-file-label="${inputId}"]`);
    if (!label) return;
    const files = Array.from(input?.files || []);
    if (!files.length) {
        label.textContent = inputId === 'project-section-config-input' ? '自动生成' : '未选择';
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
        const projectPlaceholders = currentTemplateState.selectedReportProject?.word_placeholders;
        if (Array.isArray(projectPlaceholders) && projectPlaceholders.length) {
            // 使用项目包解析出的 Word 占位符，避免报告项目走旧模板 API。
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
    renderTemplatePreviewPanel(template);
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
    const excelRows = buildExcelMappingRows(template);
    const generatedReports = Array.isArray(template.report_project?.generated_reports)
        ? template.report_project.generated_reports
        : [];

    const readyAssets = assetChecks.filter(asset => asset.ok).length;
    const passedChecks = validationChecks.filter(check => check.ok).length;
    const pendingIssueCount = assetChecks.filter(asset => !asset.ok).length
        + validationChecks.filter(check => !check.ok).length;
    const dataOk = readyAssets === assetChecks.length && excelRows.length > 0;
    const contentOk = passedChecks === validationChecks.length;
    const outputOk = generatedReports.length > 0 || dataOk && contentOk;
    const warningCount = validationChecks.length - passedChecks;

    return {
        assetChecks,
        validationChecks,
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
        passedReadinessChecks: readyAssets + passedChecks,
        totalReadinessChecks: assetChecks.length + validationChecks.length,
        placeholderCount: placeholders.length || sections.length
    };
}

function renderGenerationHero(template, readiness) {
    const templateName = template.template_name || template.name || currentSelectedTemplate || '周报';
    const project = template.report_project || null;
    const titleEls = [
        document.getElementById('template-generation-title'),
        document.getElementById('template-config-title')
    ].filter(Boolean);
    const periodEls = [
        document.getElementById('template-generation-period'),
        document.getElementById('template-config-period')
    ].filter(Boolean);
    const lookbackEls = [
        document.getElementById('template-generation-lookback'),
        document.getElementById('template-config-lookback')
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
    const rangeText = `${generationOptions.start_date} 至 ${generationOptions.end_date}`;

    titleEls.forEach(el => { el.textContent = `${templateName} · 本周报告`; });
    periodEls.forEach(el => { el.textContent = `报告日期：${reportDateText}`; });
    lookbackEls.forEach(el => { el.textContent = `证据窗口：${rangeText}`; });
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
}

function renderGenerationStatusStrip(readiness) {
    renderProjectCheckSummary(readiness);
    const dataSummary = `素材 ${readiness.readyAssets}/${readiness.totalAssets} · 数据范围 ${readiness.excelRows.length}`;
    const contentSummary = `预检 ${readiness.passedChecks}/${readiness.totalChecks} · 警告 ${readiness.warningCount}`;
    const outputSummary = readiness.latestReport ? '最近版本可预览和下载' : '生成后可预览和下载';
    updateGenerationStep('template-generation-step-data', 'template-generation-data-summary', readiness.dataOk, dataSummary);
    updateGenerationStep('template-generation-step-content', 'template-generation-content-summary', readiness.contentOk, contentSummary);
    updateGenerationStep('template-generation-step-output', 'template-generation-output-summary', readiness.outputOk, outputSummary);
    setGenerationFlowState(readiness.latestReport ? 'refresh' : 'generate', readiness.latestReport ? '已完成' : '等待生成');
}

function renderProjectCheckSummary(readiness) {
    const summaryEl = document.getElementById('template-project-check-summary');
    const statusEl = document.getElementById('template-project-check-status');
    const pending = readiness.pendingIssueCount || 0;
    const passed = readiness.passedReadinessChecks || 0;
    const total = readiness.totalReadinessChecks || 0;

    if (summaryEl) {
        summaryEl.textContent = pending
            ? `${passed}/${total} 通过 · 点击查看待处理项`
            : `${total} 项通过 · 可直接生成`;
    }
    if (statusEl) {
        statusEl.textContent = pending ? `${pending} 项待处理` : '检查通过';
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

function setGenerationFlowState(activeKey = 'generate', label = '') {
    const activeIndex = Math.max(0, REPORT_GENERATION_STEPS.findIndex(step => step.key === activeKey));
    document.querySelectorAll('[data-generation-flow-step]').forEach((stepEl) => {
        const key = stepEl.dataset.generationFlowStep;
        const index = REPORT_GENERATION_STEPS.findIndex(step => step.key === key);
        const isDone = index >= 0 && index < activeIndex;
        const isActive = key === activeKey;
        stepEl.classList.toggle('done', isDone);
        stepEl.classList.toggle('active', isActive);
        stepEl.classList.toggle('pending', !isDone && !isActive);
        const statusEl = stepEl.querySelector('em');
        if (statusEl) {
            statusEl.textContent = isDone ? '完成' : (isActive ? '当前' : '等待');
        }
    });
    const progressLabel = document.getElementById('template-generation-progress-label');
    if (progressLabel) progressLabel.textContent = label || '生成流程';
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

function selectGeneratedReport(fileName, { openPreview = false } = {}) {
    currentTemplateState.selectedGeneratedReportFile = fileName || null;
    const template = getCurrentWorkbenchTemplate();
    if (!template) return;
    renderRecentGenerationPanel(template);
    renderTemplatePreviewPanel(template);
    renderTemplateLogPanel(template);
    if (openPreview) {
        setStoredTemplateDetailMode('preview');
        applyTemplateDetailMode('preview');
    }
}

function renderRecentGenerationPanel(template) {
    const project = template.report_project || null;
    const statusEl = document.getElementById('template-recent-generation-status');
    const card = document.getElementById('template-recent-generation-card');
    if (!card) return;

    const generatedReports = getGeneratedReports(project);
    const selectedReport = getSelectedGeneratedReport(project);
    const { previewUrl, downloadUrl } = getGeneratedReportUrls(project, selectedReport);
    const previewAction = document.querySelector('[data-template-report-action="preview"]');
    const folderAction = document.querySelector('[data-template-report-action="folder"]');
    const downloadAction = document.querySelector('[data-template-report-action="download"]');

    if (statusEl) {
        statusEl.textContent = generatedReports.length ? `${generatedReports.length} 个版本` : '尚未生成';
    }
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
            <div class="template-result-empty">
                <i class="codicon codicon-file"></i>
                <span>尚未生成。点击“生成报告”后，这里会显示历史版本。</span>
            </div>
        `;
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

function renderTemplatePreviewPanel(template) {
    const project = template.report_project || null;
    const selectedReport = getSelectedGeneratedReport(project);
    const frame = document.getElementById('template-report-preview-frame');
    const label = document.getElementById('template-preview-document-label');
    const status = document.getElementById('template-preview-file-status');
    const card = document.getElementById('template-preview-file-card');
    const { previewUrl } = getGeneratedReportUrls(project, selectedReport);

    if (label) label.textContent = selectedReport?.file_name || '尚未生成';
    if (status) status.textContent = selectedReport ? '已选择' : '尚未生成';
    if (frame) {
        if (previewUrl) {
            frame.src = previewUrl;
            frame.classList.remove('hidden');
        } else {
            frame.removeAttribute('src');
            frame.classList.add('hidden');
        }
    }
    if (!card) return;
    if (!selectedReport) {
        card.innerHTML = '<div class="empty-state compact">在生成记录中选择一个报告后预览。</div>';
        return;
    }
    card.innerHTML = `
        <div class="template-preview-file-row">
            <i class="codicon codicon-file-text"></i>
            <span>
                <strong>${esc(selectedReport.file_name || '生成文档')}</strong>
                <small>${esc(formatGeneratedAt(selectedReport.generated_at))}</small>
            </span>
        </div>
    `;
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
            toast('打开文件夹失败：当前后端还没加载新接口，请重启 Research Workbench', 'error');
            return;
        }
        toast('打开文件夹失败: ' + e.message, 'error');
    }
}

function renderReportGenerationProgressCard({ status = 'running', activeKey = 'check', message = '' } = {}) {
    const card = document.getElementById('template-recent-generation-card');
    const statusEl = document.getElementById('template-recent-generation-status');
    if (!card) return;

    const activeIndex = Math.max(0, REPORT_GENERATION_STEPS.findIndex(step => step.key === activeKey));
    const statusText = status === 'error' ? '生成失败' : '生成中';
    if (statusEl) statusEl.textContent = statusText;
    setGenerationFlowState(activeKey, statusText);
    setText('template-generation-current-step-summary', message || '正在生成报告');
    const liveLog = document.getElementById('template-generation-live-log');
    if (liveLog) {
        liveLog.innerHTML = `
            <div class="template-generation-live-log-row">
                <span>${esc(formatShortTime(new Date().toISOString()))}</span>
                <strong>${esc(message || '正在生成报告')}</strong>
                <em>${esc(statusText)}</em>
            </div>
        `;
    }

    card.innerHTML = `
        <div class="template-generation-progress" role="status" aria-live="polite">
            <div class="template-generation-progress-header">
                <i class="codicon codicon-loading spin"></i>
                <span>
                    <strong>${statusText}</strong>
                    <small>${esc(message || '正在准备生成本周报告')}</small>
                </span>
            </div>
            <div class="template-generation-progress-steps">
                ${REPORT_GENERATION_STEPS.map((step, index) => {
                    const stepState = index < activeIndex ? 'done' : (index === activeIndex ? 'active' : 'pending');
                    const icon = stepState === 'done' ? 'codicon-pass' : step.icon;
                    return `
                        <div class="template-generation-progress-step ${stepState}">
                            <i class="codicon ${icon}"></i>
                            <span>${esc(step.label)}</span>
                        </div>
                    `;
                }).join('')}
            </div>
        </div>
    `;
}

function renderReportGenerationFailure(error) {
    const card = document.getElementById('template-recent-generation-card');
    const statusEl = document.getElementById('template-recent-generation-status');
    if (!card) return;

    const message = error?.message || String(error || '未知错误');
    const hint = getReportGenerationErrorHint(message);
    const target = getReportGenerationErrorTarget(message);
    if (statusEl) statusEl.textContent = '生成失败';

    card.innerHTML = `
        <div class="template-generation-error-card" role="alert">
            <div class="template-generation-error-header">
                <i class="codicon codicon-error"></i>
                <span>
                    <strong>生成失败</strong>
                    <small>${esc(hint)}</small>
                </span>
            </div>
            <pre>${esc(message)}</pre>
            <div class="template-generation-error-actions">
                <button type="button" class="btn-secondary" id="btn-template-generation-open-config">
                    <i class="codicon codicon-tools"></i> 打开高级配置
                </button>
                <button type="button" class="btn-primary" id="btn-template-generation-retry">
                    <i class="codicon codicon-refresh"></i> 重试生成
                </button>
            </div>
        </div>
    `;
    const openConfigBtn = card.querySelector('#btn-template-generation-open-config');
    if (openConfigBtn) openConfigBtn.dataset.errorTarget = target;
    bindReportGenerationFeedbackActions();
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
    currentTemplateState.activeSourceKind = 'section_config';
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
    renderTemplatePlaceholderMap(placeholders, sections);
    renderTemplateExcelMapping(template, templateName);
    renderCommonGenerationRules(template);
    renderSelectedPlaceholderDetail(template);

    const sourceEditor = document.getElementById('template-source-editor');
    if (sourceEditor) {
        const draftKey = `report-template-source:${project?.slug || templateName}:project-v2`;
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

function getTemplateWorkbenchSource(template, sourceKind = 'section_config') {
    const project = template.report_project || null;
    if (sourceKind === 'prompt_templates') {
        const useLibraryDraft = shouldUsePromptTemplateLibraryDraft(template);
        return {
            content: useLibraryDraft
                ? buildPromptTemplateLibraryMarkdown(template)
                : (project?.prompt_templates_source || buildPromptTemplateLibraryMarkdown(template)),
            sourceKind: 'prompt_templates',
            label: useLibraryDraft ? 'Markdown Prompt（模板库草稿）' : 'Markdown Prompt'
        };
    }
    return {
        content: shouldUsePlaceholderMappingDraft(template)
            ? buildPlaceholderMappingConfigYaml(template)
            : (project?.section_config_source || buildPlaceholderMappingConfigYaml(template)),
        sourceKind: 'section_config',
        label: shouldUsePlaceholderMappingDraft(template)
            ? 'YAML 占位符映射（草稿）'
            : 'YAML 占位符映射'
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
    if (!sectionBtn || !promptBtn) return;
    const isFixedExcel = isSelectedFixedExcelPlaceholder(template);
    if (isFixedExcel && currentTemplateState.activeSourceKind === 'prompt_templates') {
        currentTemplateState.activeSourceKind = 'section_config';
    }
    sectionBtn.classList.toggle('active', currentTemplateState.activeSourceKind === 'section_config');
    promptBtn.classList.toggle('active', currentTemplateState.activeSourceKind === 'prompt_templates');
    promptBtn.disabled = isFixedExcel || !template.report_project?.prompt_templates_source;
}

function switchTemplateSourceKind(sourceKind) {
    const template = getCurrentWorkbenchTemplate();
    if (!template) return;
    if (sourceKind === 'prompt_templates' && isSelectedFixedExcelPlaceholder(template)) {
        return;
    }
    currentTemplateState.activeSourceKind = sourceKind;
    updateTemplateSourceSwitcher(template);
    renderSelectedSourceFragment(template);
    setTemplateSourceEditing(false);
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
    const projectSections = project?.section_config?.sections;
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
    return [
        {
            icon: 'codicon-file-code',
            label: 'Word 模板',
            ok: Boolean(project?.word_template_filename || template.has_docx),
            value: project?.word_template_filename || (template.has_docx ? '已绑定' : '缺失'),
            action: 'upload',
            actionTarget: 'project-word-template-input',
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
            ok: Boolean(project?.section_config_filename || sections.length > 0),
            value: project?.section_config_filename || (sections.length ? `${sections.length} 段` : '待配置'),
            action: 'upload',
            actionTarget: 'project-section-config-input',
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

function renderTemplatePlaceholderMap(placeholders, sections) {
    const countEl = document.getElementById('template-placeholder-count');
    const container = document.getElementById('template-placeholder-map');
    if (!container) return;

    const names = placeholders.length
        ? placeholders
        : sections.map(section => section.placeholder || section.key).filter(Boolean);

    if (countEl) countEl.textContent = `${names.length} 个`;

    if (!names.length) {
        container.innerHTML = '<div class="empty-state compact">当前配置里还没有占位符</div>';
        return;
    }

    const selectedName = normalizePlaceholderName(currentTemplateState.selectedPlaceholderName)
        || normalizePlaceholderName(names[0]);

    container.innerHTML = `
        <select id="template-placeholder-select" class="placeholder-select" aria-label="当前段落">
            ${names.map(name => {
                const normalizedName = normalizePlaceholderName(name);
                return `
                    <option value="${esc(normalizedName)}" ${normalizedName === selectedName ? 'selected' : ''}>
                        ${esc(normalizedName)}
                    </option>
                `;
            }).join('')}
        </select>
    `;

    bindPlaceholderMapRows();
}

function renderMappingSummary(mapping, section) {
    const title = getPlaceholderKindLabel(mapping, section);
    const details = [];
    if (isPromptPlaceholderType(mapping?.type || '', mapping || {})) details.push('生成规则已绑定');
    if (mapping?.source) details.push('Excel 来源已绑定');
    if (mapping?.value) details.push('静态文本已填写');
    const detailText = details.length ? details.join(' / ') : '等待配置';
    return `
        <span class="mapping-summary-title">${esc(title)}</span>
        <small>${esc(detailText)}</small>
    `;
}

function getPlaceholderKindLabel(mapping, section) {
    const type = mapping?.type || section?.type || '';
    if (type === 'excel_commodity_market_review') return 'Excel 固定市场回顾';
    if (isPromptPlaceholderType(type, mapping || {})) return 'AI 生成段落';
    if (type === 'excel_cell' || type === 'excel_range' || mapping?.source) return 'Excel 数据';
    if (type === 'static_text' || mapping?.value) return '固定文本';
    return '配置项';
}

function getStoredCommonDefaults(template) {
    const defaults = template?.report_project?.section_config?.defaults;
    const base = {
        generation_mode: 'evidence_grounded_generation',
        evidence_policy: 'strict',
        query_mode: usesEmbeddedPromptQueries(template?.report_project) ? 'retrieval_query_embedded' : 'query_source',
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
            embedding_model: '/Users/leon/Desktop/Projects/ResearchWorkbench/data/models/embeddings/bge-large-zh-v1.5',
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
            model: '/Users/leon/Desktop/Projects/ResearchWorkbench/data/models/rerankers/bge-reranker-large',
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
                <small>共用规则与生成检查</small>
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
                    <small>${esc(getFirstLine(generationConstraints))}</small>
                </span>
                <span class="template-common-summary-meta">
                    <i class="codicon codicon-chevron-down"></i>
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
                    <small>${esc(formatEvidenceScopeSummary(reportPeriod, retrieval))}</small>
                </span>
                <span class="template-common-summary-meta">
                    检索前筛选
                    <i class="codicon codicon-chevron-down"></i>
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

function getDefaultEvidenceStartDate(reportDate = getDefaultReportDate()) {
    const end = parseDateInput(reportDate) || parseDateInput(getDefaultReportDate());
    if (!end) return '';
    const start = new Date(end);
    start.setDate(start.getDate() - 6);
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
                    <small>${esc(retrieval.mode || 'hybrid')} · Top K ${esc(retrieval.top_k ?? 10)} · 候选 ${esc(candidateK)}/${esc(semanticCandidateK)}</small>
                </span>
                <span class="template-common-summary-meta">
                    权重 ${keywordWeightPercent}/${semanticWeightPercent}
                    <i class="codicon codicon-chevron-down"></i>
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
                        <input type="text" data-common-rule-field="retrieval.embedding_model" value="${esc(retrieval.embedding_model || '/Users/leon/Desktop/Projects/ResearchWorkbench/data/models/embeddings/bge-large-zh-v1.5')}">
                    </label>
                </div>
            </div>
        </details>
        <details class="template-common-rule-card template-common-summary-card" data-common-section="rerank" ${isCommonRuleSectionOpen('rerank') ? 'open' : ''}>
            <summary>
                <span class="template-common-summary-title">
                    <strong>证据重排</strong>
                    <small>${rerank.enabled !== false ? '已启用' : '未启用'}</small>
                </span>
                <span class="template-common-summary-meta">
                    候选 ${esc(rerankTopN)} · 阈值 ${esc(rerankMinScore)}
                    <i class="codicon codicon-chevron-down"></i>
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
                        <input type="text" data-common-rule-field="rerank.model" value="${esc(rerank.model || '/Users/leon/Desktop/Projects/ResearchWorkbench/data/models/rerankers/bge-reranker-large')}">
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

    document.querySelectorAll('#template-common-rules [data-common-rule-field]').forEach(input => {
        if (input.dataset.boundCommonRule) return;
        input.dataset.boundCommonRule = 'true';
        const update = () => {
            if (input.dataset.commonRuleField === 'report_period.report_date') {
                syncEvidenceRangeFromReportDate(input.value);
            }
            collectCommonDefaultsDraft(template);
            renderSelectedSourceFragment(template);
        };
        input.addEventListener('input', update);
        input.addEventListener('change', update);
    });
    document.querySelectorAll('#template-common-rules [data-common-source-type]').forEach(input => {
        if (input.dataset.boundCommonSourceType) return;
        input.dataset.boundCommonSourceType = 'true';
        input.addEventListener('change', () => {
            syncSourceTypeCheckboxes(input);
            collectCommonDefaultsDraft(template);
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

function syncSourceTypeCheckboxes(changedInput) {
    const allInput = document.querySelector('#template-common-rules [data-common-source-type="__all__"]');
    const sourceInputs = [...document.querySelectorAll('#template-common-rules [data-common-source-type]:not([data-common-source-type="__all__"])')];
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
    const startInput = document.querySelector('#template-common-rules [data-common-rule-field="report_period.start_date"]');
    const endInput = document.querySelector('#template-common-rules [data-common-rule-field="report_period.end_date"]');
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
        document.getElementById('template-common-rules')
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
        ...document.querySelectorAll('#template-common-rules [data-common-source-type]:checked')
    ]
        .map(input => input.value)
        .filter(Boolean);
    if (document.querySelector('#template-common-rules [data-common-source-type]')) {
        draft.retrieval.source_types = selectedSourceTypes;
    }

    currentTemplateState.commonDefaultsDraft = draft;
    return draft;
}

function getStoredPlaceholderMappings(template) {
    const raw = template?.report_project?.section_config?.placeholders;
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
        const type = stored.type || inferPlaceholderType(key);
        mappings.set(key, {
            title: inferPlaceholderTitle(key),
            type,
            prompt_template: type === 'prompt' ? resolvePromptTemplateName(key, project) : undefined,
            query_mode: type === 'prompt' && usesEmbeddedPromptQueries(project) ? 'retrieval_query_embedded' : undefined,
            query_source: type === 'prompt' && !usesEmbeddedPromptQueries(project) ? inferQuerySource(key, project) : undefined,
            ...stored
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
    const select = document.getElementById('template-placeholder-select');
    if (select && !select.dataset.bound) {
        select.dataset.bound = 'true';
        select.addEventListener('change', () => selectTemplatePlaceholder(select.value || ''));
    }
    document.querySelectorAll('#template-placeholder-map .placeholder-map-row').forEach(row => {
        if (row.dataset.bound) return;
        row.dataset.bound = 'true';
        row.addEventListener('click', () => selectTemplatePlaceholder(row.dataset.placeholderName || ''));
    });
}

function selectTemplatePlaceholder(name) {
    const normalizedName = normalizePlaceholderName(name);
    if (!normalizedName) return;
    currentTemplateState.selectedPlaceholderName = normalizedName;
    const template = getCurrentWorkbenchTemplate();
    if (!template) return;
    renderTemplatePlaceholderMap(
        getTemplateWorkbenchPlaceholders(template),
        getTemplateWorkbenchSections(template)
    );
    renderSelectedPlaceholderDetail(template);
    updateTemplateSourceSwitcher(template);
    updateTemplateSourceFromPlaceholderDraft(template);
}

function getSelectedPlaceholderMapping(template) {
    const name = normalizePlaceholderName(currentTemplateState.selectedPlaceholderName);
    if (!name) return null;
    const draft = currentTemplateState.placeholderMappingDrafts?.[name];
    if (draft) return draft;
    const mappings = getCurrentPlaceholderMappings(template);
    return mappings.get(name) || {
        title: inferPlaceholderTitle(name),
        type: inferPlaceholderType(name)
    };
}

function renderSelectedPlaceholderDetail(template) {
    const titleEl = document.getElementById('template-selected-placeholder-title');
    const formEl = document.getElementById('template-placeholder-detail-form');
    const advancedFormEl = document.getElementById('template-advanced-placeholder-form');
    const saveBtn = document.getElementById('btn-template-save-placeholder');
    const advancedBtn = document.getElementById('btn-template-advanced-config');
    if (!formEl) return;

    const name = normalizePlaceholderName(currentTemplateState.selectedPlaceholderName);
    const mapping = getSelectedPlaceholderMapping(template);
    if (!name || !mapping) {
        if (titleEl) titleEl.textContent = '占位符配置详情';
        formEl.innerHTML = '<div class="empty-state compact">选择一个段落后编辑配置</div>';
        if (advancedFormEl) advancedFormEl.innerHTML = '<div class="empty-state compact">选择段落后显示高级字段</div>';
        if (saveBtn) saveBtn.disabled = true;
        if (advancedBtn) advancedBtn.disabled = true;
        return;
    }

    if (titleEl) titleEl.textContent = `编辑：${name}`;
    if (saveBtn) saveBtn.disabled = false;
    if (advancedBtn) advancedBtn.disabled = false;

    const type = mapping.type || inferPlaceholderType(name);
    const isPromptLike = isPromptPlaceholderType(type, mapping);
    const promptParam = mapping.params?.param || inferPromptParam(name);
    const needsParam = isPromptLike && Boolean(promptParam);
    const usesQuerySource = isPromptLike && !usesEmbeddedPromptQueries(template.report_project);
    const selectedKeywordProfile = getSelectedKeywordProfileName(template, mapping, name);
    const keywordMode = inferKeywordMode(template, mapping, name);
    const retrievalKeywords = getKeywordEditorText(template, mapping, name, keywordMode, selectedKeywordProfile);
    const minNewsCount = mapping.min_news_count || '';
    const dataTemplate = getDataTemplateComponent(mapping).template || inferDefaultDataTemplate(name);
    const dataTemplateFields = getDataTemplateFields(mapping);
    const writingStructure = getLlmWritingComponent(mapping).writing_structure || mapping.writing_structure || inferDefaultWritingStructure(name);
    const writingStructureText = Array.isArray(writingStructure) ? writingStructure.join('\n') : '';
    const typeOptions = getEditablePlaceholderTypeOptions(type);
    updateTemplateConfigPlaceholderChips(type, mapping);

    formEl.innerHTML = buildSimplePlaceholderFieldsHtml({
        name,
        type,
        mapping,
        isPromptLike,
        retrievalKeywords,
        selectedKeywordProfile,
        keywordMode,
        minNewsCount,
        dataTemplate,
        dataTemplateFields,
        writingStructureText,
        template
    });

    if (advancedFormEl) {
        advancedFormEl.innerHTML = buildAdvancedPlaceholderFieldsHtml({
            name,
            type,
            mapping,
            isPromptLike,
            typeOptions,
            needsParam,
            usesQuerySource,
            promptParam,
            template
        });
    }

    bindPlaceholderDetailInputs(template);
}

function updateTemplateConfigPlaceholderChips(type, mapping = {}) {
    const typeEl = document.getElementById('template-config-placeholder-type');
    const sourceEl = document.getElementById('template-config-placeholder-source');
    const healthEl = document.getElementById('template-config-placeholder-health');
    const kind = getPlaceholderKindLabel(mapping, { type });
    const source = isPromptPlaceholderType(type, mapping)
        ? 'Prompt + Excel'
        : (mapping.source || mapping.data_source ? 'Excel 数据' : '模板配置');
    if (typeEl) typeEl.textContent = kind;
    if (sourceEl) sourceEl.textContent = source;
    if (healthEl) {
        healthEl.textContent = '可生成';
        healthEl.classList.add('ok');
    }
}

function buildSimplePlaceholderFieldsHtml({
    name,
    type,
    mapping,
    isPromptLike,
    retrievalKeywords,
    selectedKeywordProfile,
    keywordMode,
    minNewsCount,
    dataTemplate,
    dataTemplateFields,
    writingStructureText,
    template
}) {
    if (isPromptLike) {
        const profileOptions = buildKeywordProfileOptions(template, selectedKeywordProfile);
        const profileKeywords = getKeywordProfileKeywords(template, selectedKeywordProfile);
        const semanticQuery = getSemanticRetrievalQueryForPlaceholder(template, mapping, name);
        const profileHelp = selectedKeywordProfile && profileKeywords.length
            ? `当前预设包包含 ${profileKeywords.length} 个关键词。`
            : '当前没有匹配到已存在的预设包，可以切换为自定义关键词。';
        const keywordChipsHtml = profileKeywords.length
            ? profileKeywords.map(keyword => `<span class="template-keyword-chip">${esc(keyword)}</span>`).join('')
            : '<span class="template-keyword-empty">当前预设包没有关键词</span>';
        const dataFieldsHtml = type === 'composite_market_review'
            ? renderDataTemplateFieldsEditor(dataTemplateFields)
            : '';
        const writingStructureHtml = `
            <label class="${type === 'composite_market_review' ? 'template-config-secondary-field' : ''}">
                <span>${type === 'composite_market_review' ? '后续写作结构（一行一步）' : '写作结构（一行一步，可选）'}</span>
                <textarea data-placeholder-field="components.llm_writing.writing_structure" rows="5">${esc(writingStructureText)}</textarea>
            </label>
        `;
        return `
            <section class="template-config-form-section template-config-form-section-compact">
                <label>
                    <span>目标字数</span>
                    <input type="number" min="1" step="1" data-placeholder-field="target_words" value="${esc(mapping.target_words || inferDefaultTargetWords(name))}">
                </label>
                <label>
                    <span>最大字数</span>
                    <input type="number" min="1" step="1" data-placeholder-field="max_words" value="${esc(mapping.max_words || inferDefaultMaxWords(name))}">
                </label>
                <label>
                    <span>最少 evidence/news 条数</span>
                    <input type="number" min="1" step="1" data-placeholder-field="min_news_count" value="${esc(minNewsCount)}">
                </label>
            </section>
            ${type === 'composite_market_review' ? `
                <label>
                    <span>固定开头模板（Excel 数据填充）</span>
                    <textarea data-placeholder-field="components.data_template.template" rows="4">${esc(dataTemplate)}</textarea>
                </label>
            ` : ''}
            <section class="template-retrieval-panel template-config-form-section">
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
            ${dataFieldsHtml}
            ${writingStructureHtml}
            <section class="template-keyword-panel template-config-form-section">
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
        `;
    }

    if (type === 'excel_commodity_market_review') {
        const dataSource = mapping.data_source || {};
        const kind = dataSource.kind || (name.includes('原油') ? 'oil' : 'gold');
        return `
            <section class="template-fixed-excel-panel template-config-form-section">
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

    if (type === 'report_period') {
        const field = mapping.field || inferReportPeriodField(name);
        return `
            <section class="template-fixed-excel-panel template-report-period-panel template-config-form-section">
                <div>
                    <span>生成方式</span>
                    <strong>按共用参数里的报告日期/数据使用范围自动填充</strong>
                </div>
                <label>
                    <span>日期字段</span>
                    <select data-placeholder-field="field">
                        <option value="start_date" ${field === 'start_date' ? 'selected' : ''}>开始日期</option>
                        <option value="end_date" ${field === 'end_date' ? 'selected' : ''}>结束日期</option>
                    </select>
                </label>
            </section>
        `;
    }

    if (type === 'excel_cell' || type === 'excel_range') {
        return `
            <label>
                <span>Excel 来源 / 区域</span>
                <input type="text" data-placeholder-field="source" value="${esc(mapping.source || '')}">
            </label>
        `;
    }

    if (type === 'static_text') {
        return `
            <label>
                <span>静态文本</span>
                <textarea data-placeholder-field="value" rows="3">${esc(mapping.value || '')}</textarea>
            </label>
        `;
    }

    return '<div class="empty-state compact">当前占位符没有常用字段，可打开高级配置查看</div>';
}

function getSemanticRetrievalQueryForPlaceholder(template, mapping = {}, placeholderName = '') {
    if (String(mapping.prompt_retrieval_query || '').trim()) {
        return String(mapping.prompt_retrieval_query).trim();
    }
    if (String(mapping.query_mode || '').trim() === 'query_source' && mapping.query_source) {
        return `Query 来源：${mapping.query_source}`;
    }
    const promptName = mapping.prompt_template
        || resolvePromptTemplateName(placeholderName, template?.report_project);
    const promptSource = template?.report_project?.prompt_templates_source || '';
    const query = extractPromptTemplateLabel(promptSource, promptName, '检索 Query');
    if (query) return query;
    if (mapping.query_source) return `Query 来源：${mapping.query_source}`;
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

function getDataTemplateFields(mapping = {}) {
    const componentFields = getDataTemplateComponent(mapping).fields;
    const fields = componentFields && typeof componentFields === 'object'
        ? componentFields
        : {};
    return {
        ...getDefaultDataTemplateFields(mapping),
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
    const orderedFields = ['market_trend', 'index_performance', 'avg_turnover', 'turnover_trend'];
    return `
        <div class="template-data-fields-panel">
            <div class="template-data-fields-header">
                <strong>模板变量数据来源</strong>
                <span>固定开头里的 {...} 从这里取数或计算</span>
            </div>
            <div class="template-data-fields-grid">
                ${orderedFields.map(fieldKey => {
                    const field = fields[fieldKey] || {};
                    return `
                        <div class="template-data-field-row template-config-data-source-row">
                            <code class="template-config-token">{${esc(fieldKey)}}</code>
                            <label>
                                <span>Excel 文件</span>
                                <input type="text" data-placeholder-field="components.data_template.fields.${esc(fieldKey)}.workbook" value="${esc(field.workbook || '')}">
                            </label>
                            <label>
                                <span>Sheet</span>
                                <input type="text" data-placeholder-field="components.data_template.fields.${esc(fieldKey)}.sheet" value="${esc(field.sheet || '')}">
                            </label>
                            <label>
                                <span>单元格/区域</span>
                                <input type="text" data-placeholder-field="components.data_template.fields.${esc(fieldKey)}.ref" value="${esc(field.cell || field.range || '')}">
                            </label>
                            <label class="template-data-field-rule">
                                <span>取数/计算规则</span>
                                <textarea data-placeholder-field="components.data_template.fields.${esc(fieldKey)}.rule" rows="2">${esc(field.rule || '')}</textarea>
                            </label>
                        </div>
                    `;
                }).join('')}
            </div>
        </div>
    `;
}

function buildAdvancedPlaceholderFieldsHtml({
    name,
    type,
    mapping,
    isPromptLike,
    typeOptions,
    needsParam,
    usesQuerySource,
    promptParam,
    template
}) {
    return `
        <div class="template-advanced-help">
            这些字段决定当前 Word 占位符连接到哪种生成或取数流程。日常改周报文案时不用动，只有新增模板、改占位符类型或排查 YAML 映射时才需要。
        </div>
        <label>
            <span>标题</span>
            <input type="text" data-placeholder-field="title" value="${esc(mapping.title || inferPlaceholderTitle(name))}">
        </label>
        <label>
            <span>类型</span>
            <select data-placeholder-field="type">
                ${typeOptions.map(option => `
                    <option value="${option.value}" ${type === option.value ? 'selected' : ''}>${esc(option.label)}</option>
                `).join('')}
            </select>
        </label>
        ${isPromptLike ? `
            <label>
                <span>Prompt 模板</span>
                <input type="text" data-placeholder-field="prompt_template" value="${esc(mapping.prompt_template || resolvePromptTemplateName(name, template.report_project))}">
            </label>
	            <label>
	                <span>检索模式</span>
	                <select data-placeholder-field="query_mode">
	                    ${['retrieval_query_embedded', 'query_source'].map(option => `
	                        <option value="${option}" ${(mapping.query_mode || 'retrieval_query_embedded') === option ? 'selected' : ''}>${option}</option>
	                    `).join('')}
	                </select>
	            </label>
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
        ${(type === 'excel_cell' || type === 'excel_range') ? `
            <label>
                <span>Excel 来源 / 区域</span>
                <input type="text" data-placeholder-field="source" value="${esc(mapping.source || '')}">
            </label>
        ` : ''}
        ${type === 'static_text' ? `
            <label>
                <span>静态文本</span>
                <textarea data-placeholder-field="value" rows="3">${esc(mapping.value || '')}</textarea>
            </label>
        ` : ''}
    `;
}

function getEditablePlaceholderTypeOptions(currentType = '') {
    const primaryOptions = [
        { value: 'prompt', label: 'AI 生成段落' },
        { value: 'composite_market_review', label: 'Excel 固定开头 + AI 续写' },
        { value: 'report_period', label: '报告日期' }
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
        prompt: 'AI 生成段落',
        ai_text: 'AI 生成段落',
        composite_market_review: 'Excel 固定开头 + AI 续写',
        excel_commodity_market_review: 'Excel 固定市场回顾',
        report_period: '报告日期',
        excel_cell: 'Excel 单元格取值',
        excel_range: 'Excel 区域取值',
        static_text: '固定文本'
    };
    return labels[type] || type || '未设置';
}

function bindPlaceholderDetailInputs(template) {
    document.querySelectorAll('#template-placeholder-detail-form [data-placeholder-field], #template-advanced-placeholder-form [data-placeholder-field]').forEach(input => {
        if (input.dataset.boundPlaceholderField) return;
        input.dataset.boundPlaceholderField = 'true';
        input.addEventListener('input', () => updateTemplateSourceFromPlaceholderDraft(template));
        input.addEventListener('change', () => {
            updateTemplateSourceFromPlaceholderDraft(template);
            if ([
                'type',
                'retrieval.keyword_mode',
                'retrieval.keyword_profile_select'
            ].includes(input.dataset.placeholderField)) {
                renderSelectedPlaceholderDetail(template);
                renderSelectedSourceFragment(template);
            }
        });
    });
}

function collectSelectedPlaceholderDraft(template) {
    const name = normalizePlaceholderName(currentTemplateState.selectedPlaceholderName);
    if (!name) return null;

    const forms = [
        document.getElementById('template-placeholder-detail-form'),
        document.getElementById('template-advanced-placeholder-form')
    ].filter(Boolean);
    const existing = getSelectedPlaceholderMapping(template) || {};
    const draft = { ...existing };
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
        } else if (
            field === 'retrieval.keyword_mode'
            || field === 'retrieval.keyword_profile_select'
            || field === 'retrieval.custom_keywords'
        ) {
            return;
        } else if (field === 'prompt.retrieval_query') {
            draft.prompt_retrieval_query = value;
        } else if (field === 'retrieval.keyword_profile') {
            if ((draft.type || inferPlaceholderType(name)) === 'composite_market_review') {
                setLlmWritingRetrievalDraftField(draft, 'keyword_profile', value || null);
            } else if (value) {
                draft.retrieval = { ...(draft.retrieval || {}), keyword_profile: value };
            } else if (draft.retrieval) {
                delete draft.retrieval.keyword_profile;
                if (!Object.keys(draft.retrieval).length) delete draft.retrieval;
            }
        } else if (field === 'retrieval.keywords') {
            const keywords = splitDelimitedList(value);
            if ((draft.type || inferPlaceholderType(name)) === 'composite_market_review') {
                setLlmWritingRetrievalDraftField(draft, 'keywords', keywords);
            } else if (keywords.length) {
                draft.retrieval = { ...(draft.retrieval || {}), keywords };
            } else if (draft.retrieval) {
                delete draft.retrieval.keywords;
                if (!Object.keys(draft.retrieval).length) delete draft.retrieval;
            }
        } else if (field.startsWith('components.data_template.fields.')) {
            setDataTemplateFieldDraft(draft, field, value);
        } else if (field === 'components.data_template.template') {
            setComponentDraftField(draft, 'data_template', 'template', value);
        } else if (field === 'components.llm_writing.writing_structure') {
            const structure = splitLines(value);
            if ((draft.type || inferPlaceholderType(name)) === 'composite_market_review') {
                setComponentDraftField(draft, 'llm_writing', 'writing_structure', structure);
            } else if (structure.length) {
                draft.writing_structure = structure;
            } else {
                delete draft.writing_structure;
            }
        } else if (field.startsWith('data_source.')) {
            const key = field.split('.')[1];
            draft.data_source = { ...(draft.data_source || {}), [key]: value };
        } else if (field === 'target_words' || field === 'max_words' || field === 'min_news_count') {
            draft[field] = value === '' ? null : Number(value);
        } else if (field) {
            draft[field] = value;
        }
    }));
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
    draft.type = draft.type || inferPlaceholderType(name);
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
            ...getDataTemplateFields(draft)
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
    const isComposite = (draft.type || inferPlaceholderType(placeholderName)) === 'composite_market_review';
    const nextRetrieval = isComposite
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

    if (isComposite) {
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

    if (isSelectedFixedExcelPlaceholder(template) && currentTemplateState.activeSourceKind === 'prompt_templates') {
        currentTemplateState.activeSourceKind = 'section_config';
    }
    const source = getTemplateWorkbenchSource(template, currentTemplateState.activeSourceKind);
    const selectedName = normalizePlaceholderName(currentTemplateState.selectedPlaceholderName);
    const sourceKindLabel = document.getElementById('template-source-kind-label');

    sourceEditor.dataset.sourceKind = source.sourceKind;
    sourceEditor.dataset.placeholderName = selectedName;

    if (source.sourceKind === 'prompt_templates') {
        const promptName = getSelectedPromptTemplateName(template);
        sourceEditor.dataset.promptTemplateName = promptName;
        sourceEditor.value = getPromptTemplateFragment(source.content, promptName);
        if (sourceKindLabel) {
            sourceKindLabel.textContent = promptName
                ? `${source.label}：${promptName}`
                : source.label;
        }
        return;
    }

    sourceEditor.dataset.promptTemplateName = '';
    sourceEditor.value = buildSelectedPlaceholderYamlFragment(template, getEditablePlaceholderMappings(template));
    if (sourceKindLabel) {
        sourceKindLabel.textContent = selectedName
            ? `${source.label}：{{${selectedName}}}`
            : source.label;
    }
}

function buildUpdatedSectionConfigSource(template, mappings) {
    const projectSource = template.report_project?.section_config_source || '';
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
    if (sourceKind === 'section_config') {
        return buildUpdatedSectionConfigSource(template, getEditablePlaceholderMappings(template));
    }
    return editorValue;
}

function buildUpdatedPromptTemplatesSource(template, promptFragment) {
    const source = getTemplateWorkbenchSource(template, 'prompt_templates').content;
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
    const firstUnmappedPlaceholder = placeholders.find(placeholder =>
        !placeholderMappings.has(normalizePlaceholderName(placeholder))
    );
    const allPlaceholdersMapped = placeholders.length === 0
        || !firstUnmappedPlaceholder;
    const hasPromptMapping = [...placeholderMappings.values()].some(mapping => mapping.prompt_template);
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

function renderTemplateValidationPreview(template, sections, placeholders) {
    const statusEl = document.getElementById('template-validation-status');
    const list = document.getElementById('template-validation-list');
    if (!list) return;

    const checks = buildTemplateValidationChecks(template, sections, placeholders);
    const excelRows = buildExcelMappingRows(template);
    const mappedPlaceholders = placeholders.length || sections.length;
    const summaryRows = [
        {
            label: 'Word 占位符映射',
            value: checks[0]?.ok ? `${mappedPlaceholders}/${mappedPlaceholders}` : '待处理',
            ok: Boolean(checks[0]?.ok)
        },
        {
            label: 'Excel 数据来源',
            value: excelRows.length ? `${excelRows.length} 个` : '待绑定',
            ok: excelRows.length > 0
        },
        {
            label: 'Prompt 模板',
            value: checks[1]?.ok ? '已绑定' : '待绑定',
            ok: Boolean(checks[1]?.ok)
        },
        {
            label: '禁用词 / 投资建议',
            value: checks[3]?.ok ? '已配置' : '待配置',
            ok: Boolean(checks[3]?.ok)
        }
    ];

    list.innerHTML = summaryRows.map(row => `
        <div class="validation-item ${row.ok ? 'ok' : 'pending'}">
            <span>${esc(row.label)}</span>
            <strong>${esc(row.value)}</strong>
        </div>
    `).join('');

    if (statusEl) {
        const passed = checks.filter(check => check.ok).length;
        statusEl.textContent = `${passed}/${checks.length}`;
        statusEl.classList.toggle('warning', passed < checks.length);
    }
}

function buildTemplateConfigYaml(template) {
    if (template.report_project) return buildPlaceholderMappingConfigYaml(template);
    const name = template.template_name || template.name || currentSelectedTemplate || 'report_template';
    const project = template.report_project || null;
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
        `  word_template: ${project?.word_template_filename || (template.has_docx ? '已绑定' : '待上传')}`,
        `  excel_workbook: ${project?.excel_workbook_filename || (template.has_excel ? '已绑定' : '待上传')}`,
        `  section_config: ${project?.section_config_filename || '当前模板 YAML'}`,
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
    const existingMappings = mappingsOverride || getStoredPlaceholderMappings(template);
    const lines = [
        '# 填写方式：',
        '# - placeholders 下每一项对应 Word 模板里的一个 {{占位符}}。',
        usesEmbeddedPromptQueries(project)
            ? '# - type=prompt 时，系统直接使用 prompt_template 中内置的检索 Query 和写作规则。'
            : '# - type=prompt 时，系统会读取 query_source，再套用 prompt_template 生成正文。',
        usesEmbeddedPromptQueries(project)
            ? '# - prompt_template 写 Word 占位符对应的模板标题，例如：人工智能。'
            : '# - query_source 写法示例：data/industry.json#人工智能，表示取该 JSON 中“人工智能”的 QUERY。',
        '# - params 用来传给 Prompt 模板中的 {{param}} 等变量。',
        `name: ${name}`,
        `version: ${template.version || '1.0'}`,
        'description: Word 占位符到 Excel / Prompt / 静态文本的映射',
        buildDefaultsBlock(getEditableCommonDefaults(template)),
        'assets:',
        `  word_template: ${project?.word_template_filename || '待绑定'}`,
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
    lines.push(`    embedding_model: ${retrieval.embedding_model || '/Users/leon/Desktop/Projects/ResearchWorkbench/data/models/embeddings/bge-large-zh-v1.5'}`);
    const sourceTypes = Array.isArray(retrieval.source_types) ? retrieval.source_types : [];
    if (sourceTypes.length) {
        lines.push('    source_types:');
        sourceTypes.forEach(sourceType => lines.push(`      - ${sourceType}`));
    }
    lines.push('  rerank:');
    lines.push(`    enabled: ${rerank.enabled !== false}`);
    lines.push(`    provider: ${rerank.provider || 'bge-reranker'}`);
    lines.push(`    model: ${rerank.model || '/Users/leon/Desktop/Projects/ResearchWorkbench/data/models/rerankers/bge-reranker-large'}`);
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
            '    type: report_period',
            `    field: ${field}`
        ].join('\n');
    }
    const mapping = existingMappings.get(key) || {};
    const type = mapping.type || inferPlaceholderType(key);
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
    const type = mapping.type || inferPlaceholderType(key);
    const lines = [
        `  ${key}:`,
        `    title: ${mapping.title || inferPlaceholderTitle(key)}`,
        `    type: ${type}`
    ];

    if (type === 'excel_cell' || type === 'excel_range') {
        lines.push(`    source: ${mapping.source || ''}`);
    } else if (type === 'report_period') {
        lines.push(`    field: ${mapping.field || inferReportPeriodField(key)}`);
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
    } else if (isPromptPlaceholderType(type, mapping)) {
        lines.push(`    prompt_template: ${mapping.prompt_template || resolvePromptTemplateName(key, project)}`);
        if (!usesEmbeddedPromptQueries(project)) {
            lines.push(`    query_source: ${mapping.query_source || inferQuerySource(key, project)}`);
        } else {
            lines.push('    query_mode: retrieval_query_embedded');
        }
        lines.push(`    target_words: ${mapping.target_words || inferDefaultTargetWords(key)}`);
        lines.push(`    max_words: ${mapping.max_words || inferDefaultMaxWords(key)}`);
        if (mapping.min_news_count) lines.push(`    min_news_count: ${mapping.min_news_count}`);
        if (type === 'composite_market_review') {
            lines.push(...buildCompositeMarketReviewYamlLines(mapping, key));
        } else {
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
        const param = mapping.params?.param || inferPromptParam(key);
        if (param) {
            lines.push('    params:');
            lines.push(`      param: ${param}`);
        } else {
            lines.push('    params: {}');
        }
    } else {
        lines.push(`    value: ${mapping.value || ''}`);
    }
    return lines;
}

function buildCompositeMarketReviewYamlLines(mapping, key) {
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
    lines.push('      fields:');
    lines.push(...buildDataTemplateFieldsYamlLines(getDataTemplateFields(mapping), '        '));
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
    const orderedFields = ['market_trend', 'index_performance', 'avg_turnover', 'turnover_trend'];
    return orderedFields.flatMap(fieldKey => {
        const field = fields[fieldKey] || {};
        const lines = [`${indent}${fieldKey}:`];
        if (field.label) lines.push(`${indent}  label: ${field.label}`);
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
    if (isSystemDatePlaceholder(name)) return 'report_period';
    if (/^(start_date|end_date|data\d+)$/i.test(name)) return 'excel_cell';
    if (/^(content\d+|phrase\d+|sector\d+)$/i.test(name)) return 'prompt';
    if (/[\u4e00-\u9fff]/.test(name)) return 'prompt';
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
        '说明：这里是可复用写作模板，不是单个占位符的完整提示词。占位符在 section_config.yaml 里通过 prompt_template 选择下面的模板；检索 Query 用来先从数据库/新闻库取 evidence，再由写作规则生成正文。',
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
    const configSaveCommonBtn = document.getElementById('btn-template-config-save-common');
    const configSavePlaceholderBtn = document.getElementById('btn-template-config-save-placeholder');
    const configAdvancedBtn = document.getElementById('btn-template-config-advanced');
    const sourceEditor = document.getElementById('template-source-editor');
    const readinessPanel = document.getElementById('template-generation-readiness-panel');

    bindTemplateDetailModeTabs();

    if (readinessPanel && !readinessPanel.dataset.bound) {
        readinessPanel.dataset.bound = 'true';
        readinessPanel.addEventListener('click', event => {
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

    const sourceSectionBtn = document.getElementById('btn-template-source-section');
    const sourcePromptBtn = document.getElementById('btn-template-source-prompt');
    if (sourceSectionBtn && !sourceSectionBtn.dataset.bound) {
        sourceSectionBtn.dataset.bound = 'true';
        sourceSectionBtn.addEventListener('click', () => switchTemplateSourceKind('section_config'));
    }
    if (sourcePromptBtn && !sourcePromptBtn.dataset.bound) {
        sourcePromptBtn.dataset.bound = 'true';
        sourcePromptBtn.addEventListener('click', () => switchTemplateSourceKind('prompt_templates'));
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

    if (configSavePlaceholderBtn && !configSavePlaceholderBtn.dataset.bound) {
        configSavePlaceholderBtn.dataset.bound = 'true';
        configSavePlaceholderBtn.addEventListener('click', () => {
            const target = document.getElementById('btn-template-save-placeholder');
            if (target && !target.disabled) target.click();
        });
    }

    if (configSaveCommonBtn && !configSaveCommonBtn.dataset.bound) {
        configSaveCommonBtn.dataset.bound = 'true';
        configSaveCommonBtn.addEventListener('click', () => {
            const target = document.getElementById('btn-template-save-common-rules');
            if (target && !target.disabled) target.click();
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
            renderReportGenerationProgressCard({
                activeKey: 'check',
                message: '正在检查当前模板、占位符和本地草稿'
            });
            if (sourceEditor?.dataset.draftKey) {
                const template = getCurrentWorkbenchTemplate() || {};
                localStorage.setItem(
                    sourceEditor.dataset.draftKey,
                    buildSourceContentForSave(template, sourceEditor.dataset.sourceKind || 'local_draft', sourceEditor.value)
                );
            }

            generateBtn.disabled = true;
            const originalText = generateBtn.innerHTML;
            generateBtn.innerHTML = '<i class="codicon codicon-loading spin"></i> 生成中...';
            try {
                await renderReportFromTemplate({ inlineProgress: true });
                toast('报告生成完成', 'success');
            } catch (e) {
                renderReportGenerationFailure(e);
                toast('生成失败: ' + e.message, 'error');
            } finally {
                generateBtn.disabled = false;
                generateBtn.innerHTML = originalText;
            }
        });
    }
}

async function saveCurrentSectionConfig({
    button,
    savingHtml = '<i class="codicon codicon-loading spin"></i> 保存中...',
    successMessage = '配置已保存',
    localMessage = '配置草稿已保存到本地',
    errorPrefix = '保存配置失败'
} = {}) {
    const template = getCurrentWorkbenchTemplate();
    if (!template) {
        toast('请先选择模板', 'error');
        return;
    }
    updateTemplateSourceFromPlaceholderDraft(template);

    const sourceEditor = document.getElementById('template-source-editor');
    const mappings = getEditablePlaceholderMappings(template);
    const content = buildUpdatedSectionConfigSource(template, mappings);
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
                    source_kind: 'section_config',
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
            toast(successMessage, 'success');
        } else {
            localStorage.setItem(sourceEditor?.dataset.draftKey || 'report-template-source:draft', content);
            toast(localMessage, 'success');
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
    const wordInput = document.getElementById('project-word-template-input');
    const excelInput = document.getElementById('project-excel-workbook-input');
    const sectionInput = document.getElementById('project-section-config-input');
    const promptInput = document.getElementById('project-prompt-templates-input');
    const dataFilesInput = document.getElementById('project-data-files-input');
    const statusEl = document.getElementById('template-upload-status');

    const projectName = nameInput?.value.trim();
    const wordFile = wordInput?.files?.[0];
    const excelFile = excelInput?.files?.[0];
    const sectionFile = sectionInput?.files?.[0];

    if (!projectName) {
        toast('请输入报告项目名称', 'error');
        return;
    }
    if (!wordFile) {
        toast('请选择 Word 模板', 'error');
        return;
    }

    if (statusEl) {
        statusEl.innerHTML = '<div class="loading"><div class="spinner"></div><span>正在创建报告项目...</span></div>';
        statusEl.classList.remove('hidden');
    }

    const formData = new FormData();
    formData.append('project_name', projectName);
    formData.append('word_template', wordFile);
    if (excelFile) {
        formData.append('excel_workbook', excelFile);
    }
    if (sectionFile) {
        formData.append('section_config', sectionFile);
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
        await loadReportProjectsList();
        await loadTemplatesList();
        await initTemplateSelects();
        closeUploadModal();

        if (nameInput) nameInput.value = '';
        [wordInput, excelInput, sectionInput, promptInput, dataFilesInput].forEach(input => {
            if (input) input.value = '';
        });
        REPORT_UPLOAD_FILE_INPUTS.forEach(updateReportProjectUploadFileLabel);
    } catch (e) {
        toast('创建报告项目失败: ' + e.message, 'error');
    } finally {
        if (statusEl) statusEl.classList.add('hidden');
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
                activeKey: 'generate',
                message: '正在检索证据、调用模型并生成正文'
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
            const projects = await loadReportProjectsList();
            const refreshedProject = (projects || []).find(project => project.slug === renderedProjectSlug);
            const selectedTemplate = getCurrentWorkbenchTemplate();
            if (selectedTemplate && refreshedProject) {
                selectedTemplate.report_project = refreshedProject;
                currentTemplateState.selectedReportProject = refreshedProject;
                renderReportGenerationCenter(selectedTemplate);
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
        if (options.inlineProgress) throw e;
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

    return apiCall(
        'POST',
        `/api/report-projects/${encodeURIComponent(project.slug)}/render`,
        {
            placeholders: currentTemplateState.placeholderValues || {},
            report_date: generationOptions.report_date || null,
            start_date: generationOptions.start_date || null,
            end_date: generationOptions.end_date || null
        }
    );
}

function getReportProjectGenerationOptions() {
    const defaults = getEditableCommonDefaults(getCurrentWorkbenchTemplate() || {});
    const reportPeriod = defaults.report_period || {};
    const reportDate = String(reportPeriod.report_date || getDefaultReportDate()).trim();
    const startDate = String(reportPeriod.start_date || getDefaultEvidenceStartDate(reportDate)).trim();
    const endDate = String(reportPeriod.end_date || reportDate).trim();
    return {
        report_date: reportDate,
        start_date: startDate,
        end_date: endDate
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
