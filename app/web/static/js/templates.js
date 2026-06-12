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
    renderedReportId: null,
    templates: [],
    reportProjects: [],
    selectedReportProject: null,
    activeSourceKind: 'section_config',
    selectedPlaceholderName: null,
    fullSectionConfigSource: ''
};

let currentSelectedTemplate = null;
let currentSelectedFileType = null;
let isEditMode = false;
let draggedTemplateName = null;
let draggedElement = null;
let pointerDragState = null;
let editingTemplateName = null;
let originalTemplates = [];

// ─── Template Page / List ──────────────────────────────────────
async function loadTemplatesPage() {
    try {
        await loadReportProjectsList();
        await loadTemplatesList();
        initTemplateDropZone();
        await initTemplateSelects();
    } catch (e) {
        toast('加载模板页面失败: ' + e.message, 'error');
    }
}

async function loadTemplatesList() {
    try {
        await loadReportProjectsList();
        const data = await apiCall('GET', '/api/templates/');
        currentTemplateState.templates = mergeTemplatesWithReportProjects(
            data.templates || [],
            currentTemplateState.reportProjects || []
        );
        renderTemplatesList(currentTemplateState.templates);
    } catch (e) {
        console.error('Failed to load templates:', e);
        const container = document.getElementById('template-list');
        if (container) container.innerHTML = '<p class="empty-state">加载失败</p>';
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
        if (existing) {
            existing.report_project = project;
            existing.has_docx = existing.has_docx || Boolean(project.word_template_filename);
            existing.has_excel = existing.has_excel || Boolean(project.excel_workbook_filename);
            return;
        }

        merged.push({
            template_name: templateName,
            name: templateName,
            description: '报告项目包',
            version: '1.0',
            has_docx: Boolean(project.word_template_filename),
            has_excel: Boolean(project.excel_workbook_filename),
            placeholders: [],
            sections: [],
            report_project: project,
            is_report_project_only: true
        });
    });

    return merged;
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

            document.getElementById('detail-template-name').textContent = template.template_name || template.name;
            const templateVersionBadge = document.getElementById('detail-template-version');
            if (templateVersionBadge) templateVersionBadge.textContent = `v${template.version || '1.0'}`;

            const downloadTemplateButton = document.getElementById('btn-download-template');
            if (downloadTemplateButton) downloadTemplateButton.onclick = () => {
                downloadTemplateFile(templateName, currentSelectedFileType);
            };

            const deleteTemplateButton = document.getElementById('btn-delete-template');
            if (deleteTemplateButton) deleteTemplateButton.onclick = () => {
                deleteTemplate(templateName);
            };

            renderTemplateWorkbench(template);
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
    clearPlaceholderData();
}

// ─── Upload Modal ──────────────────────────────────────────────
function openUploadModal() {
    document.getElementById('upload-template-modal').classList.remove('hidden');
    document.getElementById('template-name-input').value = '';
    document.getElementById('project-word-template-input').value = '';
    document.getElementById('project-excel-workbook-input').value = '';
    document.getElementById('project-section-config-input').value = '';
    document.getElementById('project-prompt-templates-input').value = '';
    document.getElementById('project-data-files-input').value = '';
    document.getElementById('template-upload-status').innerHTML = '';
}

function closeUploadModal() {
    document.getElementById('upload-template-modal').classList.add('hidden');
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
function renderTemplateWorkbench(template) {
    const project = template.report_project || null;
    const placeholders = getTemplateWorkbenchPlaceholders(template);
    const sections = getTemplateWorkbenchSections(template);
    const templateName = template.template_name || template.name || currentSelectedTemplate || '未命名模板';
    currentTemplateState.activeSourceKind = 'section_config';
    currentTemplateState.fullSectionConfigSource = project?.section_config_source || buildPlaceholderMappingConfigYaml(template);
    const currentSelected = currentTemplateState.selectedPlaceholderName;
    const normalizedNames = placeholders.map(normalizePlaceholderName).filter(Boolean);
    if (!currentSelected || !normalizedNames.includes(normalizePlaceholderName(currentSelected))) {
        currentTemplateState.selectedPlaceholderName = normalizedNames[0] || null;
    }

    renderTemplateAssetChecklist(template, sections);
    renderTemplatePlaceholderMap(placeholders, sections);
    renderSelectedPlaceholderEditor(template);
    renderTemplateExcelMapping(template, templateName);

    const primaryDownloadLink = document.getElementById('btn-template-download-report');
    if (primaryDownloadLink) {
        primaryDownloadLink.href = '#';
        primaryDownloadLink.classList.add('disabled');
        primaryDownloadLink.setAttribute('aria-disabled', 'true');
    }

    const sourceEditor = document.getElementById('template-source-editor');
    if (sourceEditor) {
        const source = getTemplateWorkbenchSource(template, currentTemplateState.activeSourceKind);
        const draftKey = `report-template-source:${project?.slug || templateName}:project-v2`;
        sourceEditor.value = source.content || localStorage.getItem(draftKey) || buildSelectedPlaceholderYaml(template);
        sourceEditor.dataset.draftKey = draftKey;
        sourceEditor.dataset.sourceKind = source.sourceKind;
        sourceEditor.readOnly = true;
        sourceEditor.classList.add('readonly');
    }

    const sourceKindLabel = document.getElementById('template-source-kind-label');
    if (sourceKindLabel) {
        const source = getTemplateWorkbenchSource(template, currentTemplateState.activeSourceKind);
        sourceKindLabel.textContent = source.label;
    }

    updateTemplateSourceSwitcher(template);
    setTemplateSourceEditing(false);

    renderTemplateValidationPreview(template, sections, placeholders);
    updateTemplateProjectCheckStatus(template, sections, placeholders);
    bindTemplateWorkbenchActions();
}

function getTemplateWorkbenchSource(template, sourceKind = 'section_config') {
    const project = template.report_project || null;
    if (sourceKind === 'prompt_templates') {
        const promptFragment = buildSelectedPromptTemplateMarkdown(template);
        const useLibraryDraft = shouldUsePromptTemplateLibraryDraft(template);
        return {
            content: promptFragment || (useLibraryDraft
                ? buildPromptTemplateLibraryMarkdown(template)
                : (project?.prompt_templates_source || buildPromptTemplateLibraryMarkdown(template))),
            sourceKind: 'prompt_templates',
            label: promptFragment ? 'Markdown Prompt（当前占位符）' : (useLibraryDraft ? 'Markdown Prompt（模板库草稿）' : 'Markdown Prompt')
        };
    }
    return {
        content: buildSelectedPlaceholderYaml(template),
        sourceKind: 'section_config',
        label: 'YAML 当前占位符片段'
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
    sectionBtn.classList.toggle('active', currentTemplateState.activeSourceKind === 'section_config');
    promptBtn.classList.toggle('active', currentTemplateState.activeSourceKind === 'prompt_templates');
    promptBtn.disabled = !template.report_project?.prompt_templates_source;
}

function switchTemplateSourceKind(sourceKind) {
    const template = getCurrentWorkbenchTemplate();
    if (!template) return;
    currentTemplateState.activeSourceKind = sourceKind;
    const source = getTemplateWorkbenchSource(template, sourceKind);
    const sourceEditor = document.getElementById('template-source-editor');
    if (sourceEditor) {
        sourceEditor.value = source.content;
        sourceEditor.dataset.sourceKind = source.sourceKind;
    }
    const sourceKindLabel = document.getElementById('template-source-kind-label');
    if (sourceKindLabel) {
        sourceKindLabel.textContent = source.label;
    }
    updateTemplateSourceSwitcher(template);
    setTemplateSourceEditing(false);
}

function refreshSelectedPlaceholderSource(template = getCurrentWorkbenchTemplate()) {
    if (!template) return;
    const source = getTemplateWorkbenchSource(template, currentTemplateState.activeSourceKind);
    const sourceEditor = document.getElementById('template-source-editor');
    if (sourceEditor) {
        sourceEditor.value = source.content;
        sourceEditor.dataset.sourceKind = source.sourceKind;
    }
    const sourceKindLabel = document.getElementById('template-source-kind-label');
    if (sourceKindLabel) sourceKindLabel.textContent = source.label;
    updateTemplateSourceSwitcher(template);
    setTemplateSourceEditing(false);
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
    return template.sections || [];
}

function getTemplateWorkbenchPlaceholders(template) {
    const project = template.report_project || null;
    const projectPlaceholders = project?.word_placeholders;
    if (Array.isArray(projectPlaceholders) && projectPlaceholders.length) {
        return projectPlaceholders;
    }
    return template.placeholders || [];
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
            ${asset.detail ? `<small>${esc(asset.detail)}</small>` : ''}
        </div>
    `).join('');

    const readyCount = assets.filter(asset => asset.ok).length;
    if (statusEl) {
        statusEl.textContent = `${readyCount}/${assets.length} 就绪`;
        statusEl.classList.toggle('warning', readyCount < assets.length);
    }
}

function buildTemplateAssetChecks(template, sections) {
    const project = template.report_project || null;
    const dataAssets = Array.isArray(project?.data_assets) ? project.data_assets : [];
    const dataAssetSummary = dataAssets.length
        ? summarizeDataAssets(dataAssets)
        : (project?.data_source_files?.length ? project.data_source_files.join('、') : '未识别配套数据');
    return [
        {
            icon: 'codicon-file-code',
            label: 'Word 模板',
            ok: Boolean(project?.word_template_filename || template.has_docx),
            value: project?.word_template_filename || (template.has_docx ? '已绑定' : '缺失')
        },
        {
            icon: 'codicon-table',
            label: '主 Excel 底稿',
            ok: Boolean(project?.excel_workbook_filename || template.has_excel),
            value: project?.excel_workbook_filename || (template.has_excel ? '已绑定' : '待绑定')
        },
        {
            icon: 'codicon-files',
            label: '配套数据',
            ok: dataAssets.length > 0 || Boolean(project?.data_source_files?.length),
            value: dataAssets.length ? `${dataAssets.length} 个文件` : dataAssetSummary,
            detail: dataAssetSummary
        },
        {
            icon: 'codicon-settings-gear',
            label: 'Section 配置',
            ok: Boolean(project?.section_config_filename || sections.length > 0),
            value: project?.section_config_filename || (sections.length ? `${sections.length} 段` : '待配置')
        }
    ];
}

function updateTemplateProjectCheckStatus(template, sections, placeholders) {
    const details = document.getElementById('template-project-check-details');
    const statusEl = document.getElementById('template-project-check-status');
    const summaryEl = document.getElementById('template-project-check-summary');
    if (!details || !statusEl || !summaryEl) return;

    const assetChecks = buildTemplateAssetChecks(template, sections);
    const validationChecks = buildTemplateValidationChecks(template, sections, placeholders);
    const excelRows = buildExcelMappingRows(template);
    const readyAssets = assetChecks.filter(asset => asset.ok).length;
    const passedChecks = validationChecks.filter(check => check.ok).length;
    const assetsOk = readyAssets === assetChecks.length;
    const validationOk = passedChecks === validationChecks.length;
    const excelOk = excelRows.length > 0;
    const allOk = assetsOk && validationOk && excelOk;

    statusEl.textContent = allOk ? '检查通过' : '需处理';
    statusEl.classList.toggle('warning', !allOk);
    summaryEl.textContent = allOk
        ? `素材齐全 · ${excelRows.length} 个数据范围 · ${passedChecks}/${validationChecks.length} 预检`
        : `素材 ${readyAssets}/${assetChecks.length} · 数据 ${excelOk ? '可读' : '待检查'} · 预检 ${passedChecks}/${validationChecks.length}`;
    details.open = !allOk;
}

function summarizeDataAssets(dataAssets) {
    const importantKinds = ['primary_excel', 'chart_workbook', 'table_workbook', 'workbook', 'query_json'];
    const sortedAssets = [...dataAssets].sort((left, right) => {
        const leftRank = importantKinds.indexOf(left.kind);
        const rightRank = importantKinds.indexOf(right.kind);
        return (leftRank === -1 ? 99 : leftRank) - (rightRank === -1 ? 99 : rightRank)
            || String(left.file_name || '').localeCompare(String(right.file_name || ''), 'zh-CN');
    });
    const names = sortedAssets.slice(0, 6).map(asset => asset.file_name || asset.relative_path).filter(Boolean);
    const extraCount = Math.max(0, sortedAssets.length - names.length);
    return extraCount ? `${names.join('、')} 等 ${sortedAssets.length} 个` : names.join('、');
}

function renderTemplatePlaceholderMap(placeholders, sections) {
    const countEl = document.getElementById('template-placeholder-count');
    const container = document.getElementById('template-placeholder-map');
    if (!container) return;

    const placeholderMappings = getCurrentPlaceholderMappings(getCurrentWorkbenchTemplate() || {});
    const sectionByPlaceholder = new Map(
        sections
            .filter(section => section.placeholder)
            .map(section => [normalizePlaceholderName(section.placeholder), section])
    );
    const names = placeholders.length
        ? placeholders
        : sections.map(section => section.placeholder || section.key).filter(Boolean);

    if (countEl) countEl.textContent = `${names.length} 个`;

    if (!names.length) {
        container.innerHTML = '<div class="empty-state compact">当前配置里还没有占位符</div>';
        return;
    }

    const placeholderOptions = names.map(name => {
        const normalizedName = normalizePlaceholderName(name);
        const mapping = placeholderMappings.get(normalizedName);
        const section = sectionByPlaceholder.get(normalizedName)
            || sections.find(item => item.key === normalizedName);
        const status = mapping
            ? (isPlaceholderMappingConfigured(mapping) ? '已配置' : '待补参数')
            : (section ? '旧配置映射' : '未映射');
        return { normalizedName, mapping, section, status };
    });
    const selectedName = normalizePlaceholderName(currentTemplateState.selectedPlaceholderName)
        || placeholderOptions[0]?.normalizedName
        || '';
    const selectedOption = placeholderOptions.find(item => item.normalizedName === selectedName)
        || placeholderOptions[0];
    const selectedMapped = Boolean(selectedOption?.mapping || selectedOption?.section);

    container.innerHTML = `
        <label class="placeholder-select-shell">
            <span>当前占位符</span>
            <select id="template-placeholder-select">
                ${placeholderOptions.map(item => `
                    <option value="${esc(item.normalizedName)}" ${item.normalizedName === selectedOption.normalizedName ? 'selected' : ''}>
                        {{${esc(item.normalizedName)}}} · ${esc(item.status)}
                    </option>
                `).join('')}
            </select>
        </label>
        <div class="placeholder-map-current ${selectedMapped ? 'mapped' : 'unmapped'}">
            <code>{{${esc(selectedOption.normalizedName)}}}</code>
            <div class="mapping-summary">${renderMappingSummary(selectedOption.mapping, selectedOption.section, getCurrentWorkbenchTemplate() || {})}</div>
            <strong>${esc(selectedOption.status)}</strong>
        </div>
    `;

    const selector = container.querySelector('#template-placeholder-select');
    if (selector) {
        selector.addEventListener('change', () => selectWorkbenchPlaceholder(selector.value));
    }

    if (selectedOption && selectedOption.normalizedName !== normalizePlaceholderName(currentTemplateState.selectedPlaceholderName)) {
        currentTemplateState.selectedPlaceholderName = selectedOption.normalizedName;
    }
}

function selectWorkbenchPlaceholder(name) {
    const normalizedName = normalizePlaceholderName(name);
    if (!normalizedName) return;
    currentTemplateState.selectedPlaceholderName = normalizedName;
    const template = getCurrentWorkbenchTemplate();
    if (!template) return;
    renderTemplatePlaceholderMap(
        getTemplateWorkbenchPlaceholders(template),
        getTemplateWorkbenchSections(template)
    );
    renderSelectedPlaceholderEditor(template);
    refreshSelectedPlaceholderSource(template);
}

function renderMappingSummary(mapping, section, template = {}) {
    const project = template.report_project || null;
    const title = mapping?.title || section?.title || '待配置来源';
    const details = [];
    if (mapping?.type === 'report_period') {
        details.push(`报告周期: ${mapping.field === 'start_date' ? '本周周一' : '报告日'}`);
    }
    if (mapping?.type === 'composite_market_review') {
        details.push('Excel 数据句 + Prompt 热点归纳');
    }
    if (mapping?.query_source) {
        details.push(`Query: ${mapping.query_source}`);
    } else if (mapping?.prompt_template && usesEmbeddedPromptQueries(project)) {
        details.push('检索 Query: 模板内置');
    }
    if (mapping?.source) details.push(`Excel: ${mapping.source}`);
    if (mapping?.value) details.push('静态文本已填写');
    const detailText = details.length ? details.join(' / ') : '需要补 prompt_template 或检索 Query';
    return `
        <span class="mapping-summary-title">${esc(title)}</span>
        <small>${esc(detailText)}</small>
    `;
}

function renderSelectedPlaceholderEditor(template) {
    const container = document.getElementById('template-placeholder-detail-form');
    const titleEl = document.getElementById('template-selected-placeholder-title');
    const saveBtn = document.getElementById('btn-template-save-placeholder');
    if (!container) return;

    const selectedName = normalizePlaceholderName(currentTemplateState.selectedPlaceholderName);
    if (!selectedName) {
        container.innerHTML = '<div class="empty-state compact">从左侧选择一个 Word 占位符后编辑配置</div>';
        if (titleEl) titleEl.textContent = '占位符配置详情';
        if (saveBtn) saveBtn.disabled = true;
        return;
    }

    const mapping = getCurrentPlaceholderMappings(template).get(selectedName) || {};
    const type = mapping.type || inferPlaceholderType(selectedName);
    const retrieval = mapping.retrieval || {};
    const validators = mapping.validators || {};
    const queryTerms = retrieval.query_terms || {};
    const keywords = retrieval.keywords || queryTerms.must_any || retrieval.must_any || [];

    if (titleEl) titleEl.textContent = `{{${selectedName}}}`;
    if (saveBtn) saveBtn.disabled = false;

    container.innerHTML = `
        <div class="placeholder-detail-grid">
            <label class="placeholder-detail-field">
                <span>类型</span>
                <select id="placeholder-field-type">
                    ${['prompt', 'composite_market_review', 'report_period', 'static_text', 'excel_cell', 'excel_range'].map(option => `
                        <option value="${option}" ${type === option ? 'selected' : ''}>${option}</option>
                    `).join('')}
                </select>
            </label>
            <label class="placeholder-detail-field" data-visible-for="prompt composite_market_review">
                <span>目标字数</span>
                <input id="placeholder-field-target-words" type="number" min="20" step="10" value="${esc(String(mapping.target_words || ''))}" placeholder="例如 100">
            </label>
            <label class="placeholder-detail-field" data-visible-for="prompt composite_market_review">
                <span>最大字数</span>
                <input id="placeholder-field-max-words" type="number" min="20" step="10" value="${esc(String(mapping.max_words || mapping.target_words || '300'))}">
            </label>
            <label class="placeholder-detail-field" data-visible-for="prompt composite_market_review">
                <span>最少新闻条数</span>
                <input id="placeholder-field-min-news-count" type="number" min="0" step="1" value="${esc(String(mapping.min_news_count || validators.min_news_count || ''))}" placeholder="例如 5">
            </label>
            <label class="placeholder-detail-field" data-visible-for="report_period">
                <span>报告周期字段</span>
                <select id="placeholder-field-period-field">
                    <option value="">不适用</option>
                    <option value="start_date" ${mapping.field === 'start_date' ? 'selected' : ''}>开始日期</option>
                    <option value="end_date" ${mapping.field === 'end_date' ? 'selected' : ''}>结束日期</option>
                </select>
            </label>
            <label class="placeholder-detail-field" data-visible-for="static_text excel_cell excel_range">
                <span>静态值 / Excel 来源</span>
                <input id="placeholder-field-source" type="text" value="${esc(mapping.source || mapping.value || '')}" placeholder="Sheet!A1 或静态文本">
            </label>
        </div>

        <div class="placeholder-detail-section" data-visible-for="prompt composite_market_review">
            <div class="placeholder-detail-section-title">检索关键词</div>
            <label class="placeholder-detail-field wide">
                <span>关键词 Profile</span>
                <input id="placeholder-field-keyword-profile" type="text" value="${esc(retrieval.keyword_profile || '')}" placeholder="例如 电力设备新能源">
            </label>
            <label class="placeholder-detail-field wide">
                <span>检索关键词（逗号或换行分隔）</span>
                <textarea id="placeholder-field-keywords" rows="3">${esc(keywords.join('\n'))}</textarea>
            </label>
        </div>
    `;

    container.querySelectorAll('input, select, textarea').forEach(input => {
        input.addEventListener('input', () => updateSelectedPlaceholderDraft());
        input.addEventListener('change', () => updateSelectedPlaceholderDraft());
    });
    document.getElementById('placeholder-field-type')?.addEventListener('change', event => {
        updatePlaceholderFieldVisibility(String(event.target.value || ''));
    });
    updatePlaceholderFieldVisibility(type);
}

function updatePlaceholderFieldVisibility(type) {
    const normalizedType = String(type || '').trim();
    document.querySelectorAll('#template-placeholder-detail-form [data-visible-for]').forEach(element => {
        const visibleTypes = String(element.dataset.visibleFor || '').split(/\s+/).filter(Boolean);
        const shouldShow = visibleTypes.includes(normalizedType);
        element.classList.toggle('placeholder-detail-field-hidden', !shouldShow);
    });
}

function updateSelectedPlaceholderDraft() {
    const template = getCurrentWorkbenchTemplate();
    if (!template) return;
    refreshSelectedPlaceholderSource(template);
}

function collectSelectedPlaceholderConfig(template) {
    const selectedName = normalizePlaceholderName(currentTemplateState.selectedPlaceholderName);
    if (!selectedName) return null;
    const original = getCurrentPlaceholderMappings(template).get(selectedName) || {};
    const type = readFieldValue('placeholder-field-type') || original.type || inferPlaceholderType(selectedName);
    const config = {
        ...original,
        title: original.title || inferPlaceholderTitle(selectedName),
        type
    };

    const maxWords = readNumberFieldValue('placeholder-field-max-words');
    if (maxWords && type !== 'report_period') config.max_words = maxWords;
    else delete config.max_words;

    const targetWords = readNumberFieldValue('placeholder-field-target-words');
    if (targetWords && type !== 'report_period') config.target_words = targetWords;
    else delete config.target_words;

    const minNewsCount = readNumberFieldValue('placeholder-field-min-news-count');
    if (minNewsCount && type !== 'report_period') config.min_news_count = minNewsCount;
    else delete config.min_news_count;

    const promptTemplate = original.prompt_template || resolvePromptTemplateName(selectedName, template.report_project || null);
    if (['prompt', 'composite_market_review'].includes(type) && promptTemplate) {
        config.prompt_template = promptTemplate;
        if (hasReportDefaultQueryMode(template.report_project || null)) {
            delete config.query_mode;
        } else {
            config.query_mode = config.query_mode || 'retrieval_query_embedded';
        }
    }

    const periodField = readFieldValue('placeholder-field-period-field');
    if (type === 'report_period') {
        config.field = periodField || inferReportPeriodField(selectedName);
        delete config.max_words;
        delete config.target_words;
        delete config.min_news_count;
        delete config.prompt_template;
        delete config.retrieval;
        delete config.validators;
    }

    const sourceValue = readFieldValue('placeholder-field-source');
    if (['excel_cell', 'excel_range'].includes(type)) {
        config.source = sourceValue;
    } else if (type === 'static_text') {
        config.value = sourceValue;
    }

    if (['prompt', 'composite_market_review'].includes(type)) {
        delete config.validators;
        delete config.params;
        const keywords = splitListInput(readFieldValue('placeholder-field-keywords'));
        const keywordProfile = readFieldValue('placeholder-field-keyword-profile');
        const retrieval = {};
        if (keywordProfile) retrieval.keyword_profile = keywordProfile;
        if (keywords.length) {
            retrieval.keywords = keywords;
        }
        if (Object.keys(retrieval).length) config.retrieval = retrieval;
        else delete config.retrieval;
    }

    return config;
}

function readFieldValue(id) {
    const el = document.getElementById(id);
    return el ? String(el.value || '').trim() : '';
}

function readNumberFieldValue(id) {
    const value = readFieldValue(id);
    if (!value) return null;
    const parsed = Number.parseInt(value, 10);
    return Number.isFinite(parsed) ? parsed : null;
}

function readFloatFieldValue(id) {
    const value = readFieldValue(id);
    if (!value) return null;
    const parsed = Number.parseFloat(value);
    return Number.isFinite(parsed) ? parsed : null;
}

function splitListInput(value) {
    return String(value || '')
        .split(/[\n,，、；;]+/)
        .map(item => item.trim())
        .filter(Boolean);
}

function inferPromptParamsObject(name) {
    const param = inferPromptParam(name);
    return param ? { param } : {};
}

function buildSelectedPlaceholderYaml(template) {
    const selectedName = normalizePlaceholderName(currentTemplateState.selectedPlaceholderName);
    if (!selectedName) return '选择左侧占位符后显示当前 YAML 片段。';
    const config = collectSelectedPlaceholderConfig(template)
        || getCurrentPlaceholderMappings(template).get(selectedName)
        || {};
    return buildPlaceholderYamlBlock(selectedName, config).trimEnd();
}

function buildPlaceholderYamlBlock(key, config) {
    const lines = [`  ${key}:`];
    appendYamlValue(lines, 4, 'title', config.title || inferPlaceholderTitle(key));
    appendYamlValue(lines, 4, 'type', config.type || inferPlaceholderType(key));
    const orderedKeys = [
        'prompt_template',
        'query_mode',
        'target_words',
        'max_words',
        'min_news_count',
        'validators',
        'field',
        'source',
        'value',
        'retrieval',
        'data_source',
        'params'
    ];
    orderedKeys.forEach(name => {
        if (config[name] !== undefined && config[name] !== null && config[name] !== '') {
            appendYamlValue(lines, 4, name, config[name]);
        }
    });
    Object.keys(config).forEach(name => {
        if (['title', 'type', ...orderedKeys].includes(name)) return;
        if (config[name] !== undefined && config[name] !== null && config[name] !== '') {
            appendYamlValue(lines, 4, name, config[name]);
        }
    });
    return lines.join('\n') + '\n';
}

function appendYamlValue(lines, indent, key, value) {
    const prefix = ' '.repeat(indent);
    if (Array.isArray(value)) {
        lines.push(`${prefix}${key}:`);
        value.forEach(item => appendYamlListItem(lines, indent + 2, item));
        return;
    }
    if (value && typeof value === 'object') {
        lines.push(`${prefix}${key}:`);
        Object.entries(value).forEach(([childKey, childValue]) => {
            if (childValue === undefined || childValue === null || childValue === '') return;
            appendYamlValue(lines, indent + 2, childKey, childValue);
        });
        return;
    }
    lines.push(`${prefix}${key}: ${formatYamlScalar(value)}`);
}

function appendYamlListItem(lines, indent, value) {
    const prefix = ' '.repeat(indent);
    if (value && typeof value === 'object') {
        lines.push(`${prefix}-`);
        Object.entries(value).forEach(([childKey, childValue]) => {
            appendYamlValue(lines, indent + 2, childKey, childValue);
        });
    } else {
        lines.push(`${prefix}- ${formatYamlScalar(value)}`);
    }
}

function formatYamlScalar(value) {
    if (typeof value === 'boolean') return value ? 'true' : 'false';
    if (typeof value === 'number') return String(value);
    const text = String(value);
    if (!text) return "''";
    if (/[:#\n\r]|^\s|\s$|^(true|false|null|\d)/i.test(text)) {
        return JSON.stringify(text);
    }
    return text;
}

function replacePlaceholderYamlBlock(source, key, block) {
    const lines = String(source || '').split('\n');
    const placeholderIndex = lines.findIndex(line => /^placeholders:\s*$/.test(line));
    if (placeholderIndex === -1) {
        return `${String(source || '').trimEnd()}\n\nplaceholders:\n${block}`;
    }
    const keyPattern = new RegExp(`^  ${escapeRegExp(key)}:\\s*$`);
    const start = lines.findIndex((line, index) => index > placeholderIndex && keyPattern.test(line));
    if (start === -1) {
        const insertIndex = findPlaceholderSectionEnd(lines, placeholderIndex);
        lines.splice(insertIndex, 0, ...block.trimEnd().split('\n'));
        return lines.join('\n');
    }
    let end = start + 1;
    while (end < lines.length && !/^  [^ ].*:\s*$/.test(lines[end]) && !/^[A-Za-z_\u4e00-\u9fff][^:]*:\s*$/.test(lines[end])) {
        end += 1;
    }
    lines.splice(start, end - start, ...block.trimEnd().split('\n'));
    return lines.join('\n');
}

function findPlaceholderSectionEnd(lines, placeholderIndex) {
    let index = placeholderIndex + 1;
    while (index < lines.length) {
        if (/^[A-Za-z_\u4e00-\u9fff][^:]*:\s*$/.test(lines[index])) return index;
        index += 1;
    }
    return lines.length;
}

function escapeRegExp(text) {
    return String(text).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function getPromptTemplateBlock(template, promptTemplateName) {
    const source = template.report_project?.prompt_templates_source || '';
    if (!source || !promptTemplateName) return null;
    const escaped = escapeRegExp(promptTemplateName);
    const pattern = new RegExp(`(^|\\n)##\\s+${escaped}\\s*\\n([\\s\\S]*?)(?=\\n##\\s+|$)`);
    const match = source.match(pattern);
    if (!match) return null;
    const body = stripPromptCodeFence(match[2].trim());
    return {
        title: promptTemplateName,
        query: extractPromptLabel(body, '检索 Query'),
        requirements: extractPromptLabel(body, '写作要求')
            || extractPromptLabel(body, '写作格式')
            || body.slice(0, 180),
        raw: `## ${promptTemplateName}\n${body}`
    };
}

function stripPromptCodeFence(text) {
    return String(text || '')
        .replace(/^```[A-Za-z0-9_-]*\s*/m, '')
        .replace(/\s*```\s*$/m, '')
        .trim();
}

function extractPromptLabel(text, label) {
    const pattern = new RegExp(`${escapeRegExp(label)}\\s*[：:]\\s*([\\s\\S]*?)(?=\\n\\s*(?:检索 Query|写作要求|写作格式)\\s*[：:]|$)`);
    const match = text.match(pattern);
    return match ? match[1].trim() : '';
}

function buildSelectedPromptTemplateMarkdown(template) {
    const selectedName = normalizePlaceholderName(currentTemplateState.selectedPlaceholderName);
    if (!selectedName) return '';
    const mapping = getCurrentPlaceholderMappings(template).get(selectedName) || {};
    const promptTemplate = mapping.prompt_template
        || resolvePromptTemplateName(selectedName, template.report_project || null);
    const block = getPromptTemplateBlock(template, promptTemplate);
    return block?.raw || '';
}

async function saveSelectedPlaceholderConfig() {
    const template = getCurrentWorkbenchTemplate();
    const project = template?.report_project || currentTemplateState.selectedReportProject;
    const selectedName = normalizePlaceholderName(currentTemplateState.selectedPlaceholderName);
    if (!template || !project || !selectedName) {
        toast('请先选择报告项目和占位符', 'error');
        return;
    }
    const config = collectSelectedPlaceholderConfig(template);
    if (!config) return;
    const block = buildPlaceholderYamlBlock(selectedName, config);
    const source = currentTemplateState.fullSectionConfigSource
        || project.section_config_source
        || buildPlaceholderMappingConfigYaml(template);
    const nextSource = replacePlaceholderYamlBlock(source, selectedName, block);
    const saveBtn = document.getElementById('btn-template-save-placeholder');
    const originalText = saveBtn?.innerHTML;
    if (saveBtn) {
        saveBtn.disabled = true;
        saveBtn.innerHTML = '<i class="codicon codicon-loading spin"></i> 保存中...';
    }
    try {
        const updatedProject = await apiCall(
            'PUT',
            `/api/report-projects/${encodeURIComponent(project.slug)}/source`,
            {
                source_kind: 'section_config',
                content: nextSource
            }
        );
        currentTemplateState.selectedReportProject = updatedProject;
        currentTemplateState.fullSectionConfigSource = updatedProject.section_config_source || nextSource;
        const selectedTemplate = (currentTemplateState.templates || []).find(item =>
            item.report_project?.slug === project.slug
        );
        if (selectedTemplate) selectedTemplate.report_project = updatedProject;
        toast(`已保存 {{${selectedName}}} 配置`, 'success');
        renderTemplateWorkbench(selectedTemplate || template);
    } catch (e) {
        toast('保存当前占位符失败: ' + e.message, 'error');
    } finally {
        if (saveBtn) {
            saveBtn.disabled = false;
            saveBtn.innerHTML = originalText;
        }
    }
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
        const storedConfig = { ...stored };
        if (hasReportDefaultQueryMode(project)) delete storedConfig.query_mode;
        const type = stored.type || inferPlaceholderType(key);
        const usesPrompt = ['prompt', 'composite_market_review'].includes(type);
        const promptTemplate = usesPrompt ? resolvePromptTemplateName(key, project) : undefined;
        const keywordRetrieval = usesPrompt ? buildKeywordRetrievalDraft(key, project) : undefined;
        mappings.set(key, {
            title: inferPlaceholderTitle(key),
            type,
            prompt_template: promptTemplate,
            query_mode: usesPrompt && usesEmbeddedPromptQueries(project) && !hasReportDefaultQueryMode(project)
                ? 'retrieval_query_embedded'
                : undefined,
            query_source: usesPrompt && !usesEmbeddedPromptQueries(project) ? inferQuerySource(key, project) : undefined,
            retrieval: keywordRetrieval,
            ...storedConfig
        });
    });
    return mappings;
}

function buildKeywordRetrievalDraft(placeholderName, project = null) {
    const profile = resolveKeywordProfileForPlaceholder(placeholderName, project);
    const keywords = profile?.keywords?.length
        ? profile.keywords.slice(0, 24)
        : suggestFallbackKeywords(placeholderName, project).slice(0, 24);
    if (!keywords.length) return undefined;
    return {
        keyword_profile: profile?.name || undefined,
        keywords
    };
}

function resolveKeywordProfileForPlaceholder(placeholderName, project = null) {
    const profiles = project?.keyword_profiles || {};
    const normalized = normalizeKeywordProfileKey(placeholderName);
    if (!normalized) return null;
    const entries = Object.entries(profiles);
    for (const [name, profile] of entries) {
        const keys = [name, profile?.name, profile?.param].map(normalizeKeywordProfileKey).filter(Boolean);
        if (keys.includes(normalized)) return { name, ...(profile || {}) };
    }
    for (const [name, profile] of entries) {
        const keys = [name, profile?.name, profile?.param].map(normalizeKeywordProfileKey).filter(Boolean);
        if (keys.some(key => key && (normalized.includes(key) || key.includes(normalized)))) {
            return { name, ...(profile || {}) };
        }
    }
    if (normalized === '原油') {
        return resolveKeywordProfileForPlaceholder('石油', project);
    }
    if (normalized === '港股') {
        return resolveKeywordProfileForPlaceholder('香港', project);
    }
    return null;
}

function suggestFallbackKeywords(placeholderName, project = null) {
    const terms = [normalizePlaceholderName(placeholderName)];
    const promptName = resolvePromptTemplateName(placeholderName, project);
    const block = getPromptTemplateBlock({ report_project: project }, promptName);
    if (block?.query) terms.push(...block.query.match(/[\u4e00-\u9fffA-Za-z0-9]{2,}/g) || []);
    if (block?.requirements) terms.push(...block.requirements.match(/[\u4e00-\u9fffA-Za-z0-9]{2,}/g) || []);
    return [...new Set(terms.map(item => String(item || '').trim()).filter(item =>
        item && !['检索', 'Query', '写作', '要求', '格式', '本周', '最新', '动态'].includes(item)
    ))];
}

function normalizeKeywordProfileKey(value) {
    return normalizePlaceholderName(value)
        .replace(/[\s_\-（）()【】[\]：:]+/g, '')
        .toLowerCase();
}

function isPlaceholderMappingConfigured(mapping) {
    return Boolean(
        mapping?.source
        || mapping?.value
        || mapping?.prompt_template
        || mapping?.query_source
        || mapping?.type === 'report_period'
        || mapping?.type === 'composite_market_review'
    );
}

function normalizePlaceholderName(name) {
    return String(name || '').replace(/^\{\{\s*/, '').replace(/\s*\}\}$/, '').trim();
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

function renderTemplateValidationPreview(template, sections, placeholders) {
    const statusEl = document.getElementById('template-validation-status');
    const list = document.getElementById('template-validation-list');
    if (!list) return;

    const checks = buildTemplateValidationChecks(template, sections, placeholders);

    list.innerHTML = checks.map(check => `
        <div class="validation-item ${check.ok ? 'ok' : 'pending'}">
            <i class="codicon ${check.ok ? 'codicon-pass' : 'codicon-circle-outline'}"></i>
            <span>${esc(check.label)}</span>
        </div>
    `).join('');

    if (statusEl) {
        const passed = checks.filter(check => check.ok).length;
        statusEl.textContent = `${passed}/${checks.length}`;
        statusEl.classList.toggle('warning', passed < checks.length);
    }
}

function buildTemplateValidationChecks(template, sections, placeholders) {
    const placeholderMappings = getCurrentPlaceholderMappings(template);
    const allPlaceholdersMapped = placeholders.length === 0
        || placeholders.every(placeholder => placeholderMappings.has(normalizePlaceholderName(placeholder)));
    const hasPromptMapping = [...placeholderMappings.values()].some(mapping => mapping.prompt_template);
    const hasRuleConfig = sections.some(section =>
        section.evidence_policy
        || section.forbidden_terms?.length
        || section.investment_advice_policy
    ) || Boolean(template.report_project);
    const checks = [
        { label: 'Word 占位符均有 section 映射', ok: allPlaceholdersMapped },
        { label: 'AI 文本 section 已配置 prompt', ok: hasPromptMapping || sections.some(section => section.prompt_template || section.required_facets?.length) },
        { label: 'Excel 图表和表格已绑定来源', ok: template.has_excel || (template.template_name || '').includes('创业板50') },
        { label: '数字、禁用词、投资建议规则已配置', ok: hasRuleConfig }
    ];
    return checks;
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

function buildPlaceholderMappingConfigYaml(template) {
    const name = template.template_name || template.name || currentSelectedTemplate || 'report_template';
    const project = template.report_project || null;
    const placeholders = getTemplateWorkbenchPlaceholders(template);
    const existingMappings = getStoredPlaceholderMappings(template);
    const lines = [
        '# 填写方式：',
        '# - placeholders 下每一项对应 Word 模板里的一个 {{占位符}}。',
        usesEmbeddedPromptQueries(project)
            ? '# - type=prompt 时，系统直接使用 prompt_template 中内置的检索 Query 和写作规则。'
            : '# - type=prompt 时，系统会读取 query_source，再套用 prompt_template 生成正文。',
        usesEmbeddedPromptQueries(project)
            ? '# - prompt_template 写 Word 占位符对应的模板标题，例如：人工智能。'
            : '# - query_source 写法示例：data/industry.json#人工智能，表示取该 JSON 中“人工智能”的 QUERY。',
        '# - retrieval.keyword_profile 表示复用哪组关键词画像；retrieval.keywords 是本段实际检索关键词。',
        `name: ${name}`,
        `version: ${template.version || '1.0'}`,
        'description: Word 占位符到 Excel / Prompt / 静态文本的映射',
        'assets:',
        `  word_template: ${project?.word_template_filename || '待绑定'}`,
        `  excel_workbook: ${project?.excel_workbook_filename || '待绑定'}`,
        `  prompt_templates: ${project?.prompt_templates_filename || '未绑定'}`,
        'placeholders:'
    ];

    placeholders.forEach(placeholder => {
        const key = normalizePlaceholderName(placeholder);
        const mapping = existingMappings.get(key) || {};
        const type = mapping.type || inferPlaceholderType(key);
        lines.push(`  ${key}:`);
        lines.push(`    title: ${mapping.title || inferPlaceholderTitle(key)}`);
        lines.push(`    type: ${type}`);
        if (type === 'excel_cell' || type === 'excel_range') {
            lines.push(`    source: ${mapping.source || ''}`);
        } else if (type === 'report_period') {
            lines.push(`    field: ${mapping.field || inferReportPeriodField(key)}`);
        } else if (type === 'prompt') {
            lines.push(`    prompt_template: ${mapping.prompt_template || resolvePromptTemplateName(key, project)}`);
            if (!usesEmbeddedPromptQueries(project)) {
                lines.push(`    query_source: ${mapping.query_source || inferQuerySource(key, project)}`);
            } else if (!hasReportDefaultQueryMode(project)) {
                lines.push('    query_mode: retrieval_query_embedded');
            }
            const retrieval = mapping.retrieval || buildKeywordRetrievalDraft(key, project);
            if (retrieval?.keyword_profile || retrieval?.keywords?.length) {
                lines.push('    retrieval:');
                if (retrieval.keyword_profile) lines.push(`      keyword_profile: ${retrieval.keyword_profile}`);
                if (retrieval.keywords?.length) {
                    lines.push('      keywords:');
                    retrieval.keywords.forEach(keyword => lines.push(`        - ${keyword}`));
                }
            }
        } else {
            lines.push(`    value: ${mapping.value || ''}`);
        }
    });

    return lines.join('\n');
}

function inferPlaceholderType(name) {
    if (/^(start_date|end_date)$/i.test(name) || ['开始日期', '结束日期'].includes(name)) {
        return 'report_period';
    }
    if (/^data\d+$/i.test(name)) return 'excel_cell';
    if (/^(content\d+|phrase\d+|sector\d+)$/i.test(name)) return 'prompt';
    if (/[\u4e00-\u9fff]/.test(name)) return 'prompt';
    return 'static_text';
}

function inferPlaceholderTitle(name) {
    const titles = {
        title: '报告标题',
        start_date: '开始日期',
        end_date: '结束日期'
    };
    return titles[name] || name;
}

function inferReportPeriodField(name) {
    if (/^start_date$/i.test(name) || name === '开始日期') return 'start_date';
    if (/^end_date$/i.test(name) || name === '结束日期') return 'end_date';
    return 'end_date';
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

function hasReportDefaultQueryMode(project = null) {
    return Boolean(project?.section_config?.defaults?.query_mode);
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

function bindTemplateWorkbenchActions() {
    const editBtn = document.getElementById('btn-template-edit-source');
    const saveBtn = document.getElementById('btn-template-save-source');
    const savePlaceholderBtn = document.getElementById('btn-template-save-placeholder');
    const dryRunBtn = document.getElementById('btn-template-dry-run');
    const generateBtn = document.getElementById('btn-template-generate-report');
    const sourceEditor = document.getElementById('template-source-editor');

    if (editBtn && sourceEditor && !editBtn.dataset.bound) {
        editBtn.dataset.bound = 'true';
        editBtn.addEventListener('click', () => {
            if (sourceEditor.dataset.sourceKind === 'section_config') {
                toast('当前 YAML 片段用于对照，请在上方表单修改并保存当前占位符', 'info');
                return;
            }
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
            if (sourceEditor.dataset.sourceKind === 'section_config') {
                await saveSelectedPlaceholderConfig();
                setTemplateSourceEditing(false);
                return;
            }
            const key = sourceEditor.dataset.draftKey || 'report-template-source:draft';
            const sourceKind = sourceEditor.dataset.sourceKind || 'local_draft';
            saveBtn.disabled = true;
            const originalText = saveBtn.innerHTML;
            saveBtn.innerHTML = '<i class="codicon codicon-loading spin"></i> 保存中...';
            try {
                if (currentTemplateState.selectedReportProject && sourceKind !== 'local_draft') {
                    const project = currentTemplateState.selectedReportProject;
                    const updatedProject = await apiCall(
                        'PUT',
                        `/api/report-projects/${encodeURIComponent(project.slug)}/source`,
                        {
                            source_kind: sourceKind,
                            content: sourceEditor.value
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
                    localStorage.setItem(key, sourceEditor.value);
                    toast('配置草稿已保存到本地', 'success');
                }
                setTemplateSourceEditing(false);
            } catch (e) {
                saveBtn.disabled = false;
                toast('保存配置失败: ' + e.message, 'error');
            } finally {
                saveBtn.innerHTML = originalText;
            }
        });
    }

    if (savePlaceholderBtn && !savePlaceholderBtn.dataset.bound) {
        savePlaceholderBtn.dataset.bound = 'true';
        savePlaceholderBtn.addEventListener('click', saveSelectedPlaceholderConfig);
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
            if (sourceEditor?.dataset.draftKey) {
                localStorage.setItem(sourceEditor.dataset.draftKey, sourceEditor.value);
            }

            generateBtn.disabled = true;
            const originalText = generateBtn.innerHTML;
            generateBtn.innerHTML = '<i class="codicon codicon-loading spin"></i> 生成中...';
            try {
                await renderReportFromTemplate();
            } finally {
                generateBtn.disabled = false;
                generateBtn.innerHTML = originalText;
            }
        });
    }
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
    if (!wordFile || !excelFile || !sectionFile) {
        toast('请至少选择 Word 模板、Excel 底稿和 Section 配置', 'error');
        return;
    }

    if (statusEl) {
        statusEl.innerHTML = '<div class="loading"><div class="spinner"></div><span>正在创建报告项目...</span></div>';
        statusEl.classList.remove('hidden');
    }

    const formData = new FormData();
    formData.append('project_name', projectName);
    formData.append('word_template', wordFile);
    formData.append('excel_workbook', excelFile);
    formData.append('section_config', sectionFile);
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
        if (wordInput) wordInput.value = '';
        if (excelInput) excelInput.value = '';
        if (sectionInput) sectionInput.value = '';
        if (promptInput) promptInput.value = '';
        if (dataFilesInput) dataFilesInput.value = '';
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
async function renderReportFromTemplate() {
    const templateSelect = document.getElementById('render-template-select');
    const typeSelect = document.getElementById('render-type-select');
    const canonicalIdInput = document.getElementById('render-canonical-id');
    const reportTypeSelect = document.getElementById('render-report-type');

    const templateName = templateSelect?.value || currentTemplateState.selectedTemplate;
    const fileType = typeSelect?.value || currentTemplateState.selectedFileType || 'docx';
    const canonicalId = canonicalIdInput?.value.trim() || null;
    const reportType = reportTypeSelect?.value || 'full';

    if (!templateName) {
        toast('请先选择一个模板', 'error');
        return;
    }

    const loadingEl = document.getElementById('render-loading');
    const resultEl = document.getElementById('render-result');

    if (loadingEl) loadingEl.classList.remove('hidden');
    if (resultEl) resultEl.classList.add('hidden');

    try {
        let result;

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

        if (resultEl) {
            const downloadUrl = result.download_url
                || (result.report_id ? `/api/templates/download/${encodeURIComponent(result.report_id)}` : null);
            const previewUrl = result.preview_url || null;
            const runLogUrl = result.run_log_url || null;
            const downloadLink = document.getElementById('render-download-link');
            if (downloadLink && downloadUrl) {
                downloadLink.href = downloadUrl;
            }
            const primaryDownloadLink = document.getElementById('btn-template-download-report');
            if (primaryDownloadLink && downloadUrl) {
                primaryDownloadLink.href = downloadUrl;
                primaryDownloadLink.classList.remove('disabled');
                primaryDownloadLink.removeAttribute('aria-disabled');
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
                ${runLogUrl ? `
                    <div class="report-preview-shell evidence-debug-shell">
                        <div class="report-preview-header">
                            <strong>Evidence 检索调试</strong>
                            <span>Top K / 命中词 / 关键词分 / 语义分 / 融合分 / Rerank</span>
                        </div>
                        <div id="render-evidence-debug" class="report-preview-content">
                            <div class="loading compact"><div class="spinner"></div><span>正在加载 evidence...</span></div>
                        </div>
                    </div>
                ` : ''}
            `;
            resultEl.classList.remove('hidden');
            if (previewUrl) {
                await loadRenderedReportPreview(previewUrl);
            }
            if (runLogUrl) {
                await loadRenderedReportEvidence(runLogUrl);
            }
        }
    } catch (e) {
        toast('渲染失败: ' + e.message, 'error');
    } finally {
        if (loadingEl) loadingEl.classList.add('hidden');
    }
}

async function loadRenderedReportEvidence(runLogUrl) {
    const container = document.getElementById('render-evidence-debug');
    if (!container) return;
    try {
        const runLog = await apiCall('GET', runLogUrl);
        const sections = runLog?.generation?.sections || [];
        if (!sections.length) {
            container.innerHTML = '<div class="empty-state compact">暂无 generation 记录。</div>';
            return;
        }
        container.innerHTML = sections.map(section => {
            const evidence = section.evidence || [];
            const topItems = evidence.slice(0, 3).map(item => {
                const terms = item.matched_terms?.length
                    ? `<span class="muted">命中：${esc(item.matched_terms.join(' / '))}</span>`
                    : '<span class="muted">未记录命中词</span>';
                const scoreParts = [];
                if (item.retrieval_rank) scoreParts.push(`Rank ${item.retrieval_rank}`);
                if (item.retrieval_method) scoreParts.push(item.retrieval_method);
                if (item.keyword_score !== null && item.keyword_score !== undefined) {
                    scoreParts.push(`关键词 ${item.keyword_score}`);
                }
                if (item.semantic_score !== null && item.semantic_score !== undefined) {
                    scoreParts.push(`语义 ${Number(item.semantic_score).toFixed(3)}`);
                }
                if (item.retrieval_score !== null && item.retrieval_score !== undefined) {
                    scoreParts.push(`融合 ${Number(item.retrieval_score).toFixed(4)}`);
                }
                if (item.rerank_rank) scoreParts.push(`Rerank ${item.rerank_rank}`);
                if (item.rerank_score !== null && item.rerank_score !== undefined) {
                    scoreParts.push(`重排 ${item.rerank_score}`);
                }
                const score = scoreParts.length
                    ? `<span class="muted">${esc(scoreParts.join(' / '))}</span>`
                    : '';
                const reason = item.rerank_reason
                    ? `<div class="muted">重排理由：${esc(item.rerank_reason)}</div>`
                    : '';
                return `
                    <li>
                        <strong>${esc(item.title || '未命名 evidence')}</strong>
                        <div>${terms} ${score}</div>
                        ${reason}
                    </li>
                `;
            }).join('');
            const retrieval = section.retrieval_config || {};
            const mustAny = retrieval.must_any?.length
                ? `<div class="muted">关键词：${esc(retrieval.must_any.join(' / '))}</div>`
                : '';
            const retrievalSummary = retrieval.mode
                ? `<div class="muted">模式：${esc(retrieval.mode)} / ${esc(retrieval.fusion_method || 'keyword')} / keyword ${esc(String(retrieval.keyword_weight ?? '-'))} / semantic ${esc(String(retrieval.semantic_weight ?? '-'))}</div>`
                : '';
            const rerankSummary = retrieval.rerank_enabled
                ? `<div class="muted">Rerank：${esc(retrieval.rerank_provider || 'llm')} / Top ${esc(String(retrieval.rerank_top_n || '-'))} / 阈值 ${esc(String(retrieval.min_rerank_score ?? 0))}</div>`
                : '';
            return `
                <div class="evidence-debug-section">
                    <div class="evidence-debug-title">
                        <strong>${esc(section.placeholder || section.title || 'Section')}</strong>
                        <span>${evidence.length} 条 evidence</span>
                    </div>
                    ${retrievalSummary}
                    ${rerankSummary}
                    ${mustAny}
                    <ol>${topItems || '<li class="muted">没有进入最终 prompt 的 evidence</li>'}</ol>
                </div>
            `;
        }).join('');
    } catch (error) {
        container.innerHTML = `<div class="empty-state compact">Evidence 加载失败：${esc(error.message)}</div>`;
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

    return apiCall(
        'POST',
        `/api/report-projects/${encodeURIComponent(project.slug)}/render`,
        { placeholders: currentTemplateState.placeholderValues || {} }
    );
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
