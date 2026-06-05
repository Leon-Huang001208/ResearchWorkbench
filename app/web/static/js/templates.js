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
    selectedReportProject: null
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
            document.getElementById('detail-template-title').textContent = template.template_name || template.name;
            document.getElementById('detail-template-description').textContent = template.description || '';
            document.getElementById('detail-template-version').textContent = `v${template.version || '1.0'}`;

            document.getElementById('detail-has-docx').classList.toggle('hidden', !template.has_docx);
            document.getElementById('detail-has-pptx').classList.toggle('hidden', !template.has_pptx);
            document.getElementById('detail-has-excel').classList.toggle('hidden', !template.has_excel);

            const iconEl = document.getElementById('detail-template-icon');
            iconEl.className = 'template-icon-large';
            if (template.has_docx) iconEl.classList.add('docx');
            else if (template.has_pptx) iconEl.classList.add('pptx');
            else if (template.has_excel) iconEl.classList.add('excel');
            else iconEl.classList.add('default');

            document.getElementById('btn-download-template').onclick = () => {
                downloadTemplateFile(templateName, currentSelectedFileType);
            };

            document.getElementById('btn-delete-template').onclick = () => {
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

    renderTemplateAssetChecklist(template, sections);
    renderTemplatePlaceholderMap(placeholders, sections);
    renderTemplateExcelMapping(template, templateName);

    const primaryDownloadLink = document.getElementById('btn-template-download-report');
    if (primaryDownloadLink) {
        primaryDownloadLink.href = '#';
        primaryDownloadLink.classList.add('disabled');
        primaryDownloadLink.setAttribute('aria-disabled', 'true');
    }

    const sourceEditor = document.getElementById('template-source-editor');
    if (sourceEditor) {
        const projectSource = project?.section_config_source || '';
        const draftKey = `report-template-source:${project?.slug || templateName}:project-v2`;
        sourceEditor.value = projectSource || localStorage.getItem(draftKey) || buildTemplateConfigYaml(template);
        sourceEditor.dataset.draftKey = draftKey;
    }

    renderTemplateValidationPreview(template, sections, placeholders);
    bindTemplateWorkbenchActions();
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

    const project = template.report_project || null;
    const assets = [
        {
            icon: 'codicon-file-code',
            label: 'Word 模板',
            ok: Boolean(project?.word_template_filename || template.has_docx),
            value: project?.word_template_filename || (template.has_docx ? '已绑定' : '缺失')
        },
        {
            icon: 'codicon-table',
            label: 'Excel 底稿',
            ok: Boolean(project?.excel_workbook_filename || template.has_excel),
            value: project?.excel_workbook_filename || (template.has_excel ? '已绑定' : '待绑定')
        },
        {
            icon: 'codicon-settings-gear',
            label: 'Section 配置',
            ok: Boolean(project?.section_config_filename || sections.length > 0),
            value: project?.section_config_filename || (sections.length ? `${sections.length} 段` : '待配置')
        }
    ];

    checklist.innerHTML = assets.map(asset => `
        <div class="asset-check-item ${asset.ok ? 'ok' : 'missing'}">
            <i class="codicon ${asset.icon}"></i>
            <span>${esc(asset.label)}</span>
            <strong>${esc(asset.value)}</strong>
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

    container.innerHTML = names.slice(0, 8).map(name => {
        const normalizedName = normalizePlaceholderName(name);
        const section = sectionByPlaceholder.get(normalizedName)
            || sections.find(item => item.key === normalizedName);
        const status = section ? '已映射' : '未映射';
        return `
            <div class="placeholder-map-row ${section ? 'mapped' : 'unmapped'}">
                <code>{{${esc(normalizedName)}}}</code>
                <span>${esc(section?.title || '待指定 Section')}</span>
                <strong>${status}</strong>
            </div>
        `;
    }).join('');
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

    const hasRuleConfig = sections.some(section =>
        section.evidence_policy
        || section.forbidden_terms?.length
        || section.investment_advice_policy
    ) || Boolean(template.report_project);
    const checks = [
        { label: 'Word 占位符均有 section 映射', ok: placeholders.length === 0 || sections.length > 0 },
        { label: 'AI 文本 section 已配置 prompt', ok: sections.some(section => section.prompt_template || section.required_facets?.length) },
        { label: 'Excel 图表和表格已绑定来源', ok: template.has_excel || (template.template_name || '').includes('创业板50') },
        { label: '数字、禁用词、投资建议规则已配置', ok: hasRuleConfig }
    ];

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

function buildTemplateConfigYaml(template) {
    if (template.report_project?.section_config_source) {
        return template.report_project.section_config_source;
    }
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

function bindTemplateWorkbenchActions() {
    const saveBtn = document.getElementById('btn-template-save-source');
    const dryRunBtn = document.getElementById('btn-template-dry-run');
    const generateBtn = document.getElementById('btn-template-generate-report');
    const sourceEditor = document.getElementById('template-source-editor');

    if (saveBtn && sourceEditor && !saveBtn.dataset.bound) {
        saveBtn.dataset.bound = 'true';
        saveBtn.addEventListener('click', () => {
            const key = sourceEditor.dataset.draftKey || 'report-template-source:draft';
            localStorage.setItem(key, sourceEditor.value);
            toast('配置草稿已保存到本地', 'success');
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
                <a id="render-download-link" href="${esc(downloadUrl || '#')}"
                   class="btn-primary" target="_blank">下载报告</a>
            `;
            resultEl.classList.remove('hidden');
        }
    } catch (e) {
        toast('渲染失败: ' + e.message, 'error');
    } finally {
        if (loadingEl) loadingEl.classList.add('hidden');
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
