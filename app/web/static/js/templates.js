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
    commonDefaultsDraft: null,
    renderedReportId: null,
    templates: [],
    reportProjects: [],
    selectedReportProject: null,
    activeSourceKind: 'section_config'
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
    currentTemplateState.placeholderMappingDrafts = {};
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
function renderReportGenerationCenter(template) {
    const placeholders = getTemplateWorkbenchPlaceholders(template);
    const sections = getTemplateWorkbenchSections(template);
    const readiness = buildGenerationReadiness(template, sections, placeholders);

    renderGenerationHero(template, readiness);
    renderGenerationStatusStrip(readiness);
    renderRecentGenerationPanel(template);
    renderAdvancedMaintenance(template);
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
        readyAssets,
        totalAssets: assetChecks.length,
        passedChecks,
        totalChecks: validationChecks.length,
        placeholderCount: placeholders.length || sections.length
    };
}

function renderGenerationHero(template, readiness) {
    const templateName = template.template_name || template.name || currentSelectedTemplate || '周报';
    const project = template.report_project || null;
    const titleEl = document.getElementById('template-generation-title');
    const periodEl = document.getElementById('template-generation-period');
    const lookbackEl = document.getElementById('template-generation-lookback');
    const placeholderTotalEl = document.getElementById('template-generation-placeholder-total');

    if (titleEl) titleEl.textContent = `${templateName} · 生成本周报告`;
    if (periodEl) periodEl.textContent = '报告周期：本周';
    if (lookbackEl) lookbackEl.textContent = '证据检索 7 天';
    if (placeholderTotalEl) placeholderTotalEl.textContent = `${readiness.placeholderCount} 个占位符`;

    const previewBtn = document.getElementById('btn-template-preview-report');
    const latestReport = readiness.latestReport;
    if (previewBtn) {
        const previewUrl = latestReport && project
            ? `/api/report-projects/${encodeURIComponent(project.slug)}/preview/${encodeURIComponent(latestReport.file_name)}`
            : '';
        previewBtn.disabled = !previewUrl;
        previewBtn.onclick = previewUrl ? () => window.open(previewUrl, '_blank') : null;
    }
}

function renderGenerationStatusStrip(readiness) {
    updateGenerationStep(
        'template-generation-step-data',
        'template-generation-data-summary',
        readiness.dataOk,
        `素材 ${readiness.readyAssets}/${readiness.totalAssets} · 数据范围 ${readiness.excelRows.length}`
    );
    updateGenerationStep(
        'template-generation-step-content',
        'template-generation-content-summary',
        readiness.contentOk,
        `预检 ${readiness.passedChecks}/${readiness.totalChecks} · 警告 ${readiness.warningCount}`
    );
    updateGenerationStep(
        'template-generation-step-output',
        'template-generation-output-summary',
        readiness.outputOk,
        readiness.latestReport ? '最近版本可预览和下载' : '生成后可预览和下载'
    );
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

function renderRecentGenerationPanel(template) {
    const project = template.report_project || null;
    const statusEl = document.getElementById('template-recent-generation-status');
    const card = document.getElementById('template-recent-generation-card');
    const downloadLink = document.getElementById('btn-template-download-report');
    if (!card) return;

    const generatedReports = Array.isArray(project?.generated_reports) ? project.generated_reports : [];
    const latest = generatedReports[0] || null;
    const downloadUrl = latest && project
        ? `/api/report-projects/${encodeURIComponent(project.slug)}/download/${encodeURIComponent(latest.file_name)}`
        : '';
    const previewUrl = latest && project
        ? `/api/report-projects/${encodeURIComponent(project.slug)}/preview/${encodeURIComponent(latest.file_name)}`
        : '';

    if (statusEl) statusEl.textContent = latest ? '可下载' : '尚未生成';
    if (downloadLink) {
        downloadLink.href = downloadUrl || '#';
        downloadLink.classList.toggle('disabled', !downloadUrl);
        downloadLink.setAttribute('aria-disabled', downloadUrl ? 'false' : 'true');
    }

    if (!latest) {
        card.innerHTML = '<div class="empty-state compact">尚未生成。点击“生成报告”后，这里会显示最近版本。</div>';
        return;
    }

    card.innerHTML = `
        <strong>${esc(latest.file_name || '最近生成文档')}</strong>
        <small>${esc(formatGeneratedAt(latest.generated_at))}</small>
        <div class="template-recent-generation-actions">
            ${previewUrl ? `<a class="btn-secondary" href="${esc(previewUrl)}" target="_blank">打开预览</a>` : ''}
            ${downloadUrl ? `<a class="btn-secondary" href="${esc(downloadUrl)}" target="_blank">下载 Word</a>` : ''}
        </div>
    `;
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
    sectionBtn.classList.toggle('active', currentTemplateState.activeSourceKind === 'section_config');
    promptBtn.classList.toggle('active', currentTemplateState.activeSourceKind === 'prompt_templates');
    promptBtn.disabled = !template.report_project?.prompt_templates_source;
}

function switchTemplateSourceKind(sourceKind) {
    const template = getCurrentWorkbenchTemplate();
    if (!template) return;
    currentTemplateState.activeSourceKind = sourceKind;
    updateTemplateSourceSwitcher(template);
    renderSelectedSourceFragment(template);
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

function buildTemplateAssetChecks(template, sections) {
    const project = template.report_project || null;
    return [
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

    const selectedName = normalizePlaceholderName(currentTemplateState.selectedPlaceholderName)
        || normalizePlaceholderName(names[0]);
    const selectedMapping = placeholderMappings.get(selectedName);
    const selectedSection = sectionByPlaceholder.get(selectedName)
        || sections.find(item => item.key === selectedName);
    const selectedStatus = selectedMapping
        ? (isPlaceholderMappingConfigured(selectedMapping) ? '已配置' : '待补参数')
        : (selectedSection ? '旧配置映射' : '未映射');

    container.innerHTML = `
        <label class="placeholder-select-label" for="template-placeholder-select">当前占位符</label>
        <select id="template-placeholder-select" class="placeholder-select">
            ${names.map(name => {
                const normalizedName = normalizePlaceholderName(name);
                return `
                    <option value="${esc(normalizedName)}" ${normalizedName === selectedName ? 'selected' : ''}>
                        {{${esc(normalizedName)}}}
                    </option>
                `;
            }).join('')}
        </select>
        <div class="placeholder-selected-card ${selectedStatus === '未映射' ? 'unmapped' : 'mapped'}">
            <code>{{${esc(selectedName)}}}</code>
            <div class="mapping-summary">${renderMappingSummary(selectedMapping, selectedSection, getCurrentWorkbenchTemplate() || {})}</div>
            <strong>${selectedStatus}</strong>
        </div>
    `;

    bindPlaceholderMapRows();
}

function renderMappingSummary(mapping, section, template = {}) {
    const project = template.report_project || null;
    const title = mapping?.title || section?.title || '待配置来源';
    const details = [];
    if (mapping?.prompt_template) details.push(`Prompt: ${mapping.prompt_template}`);
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
        hard_constraints: {
            no_wind_data: true,
            no_baidu_data: true,
            require_number_source: true,
            single_paragraph: true,
            forbidden_phrases: ['根据文件', '据报道', '数据显示'],
            forbidden_entity_categories: ['指数名称', '公司名称', '证券机构']
        },
        retrieval: {
            mode: 'hybrid',
            top_k: 8,
            keyword_candidates: 40,
            semantic_candidates: 80,
            keyword_weight: 0.7,
            semantic_weight: 0.3
        },
        rerank: {
            enabled: true,
            provider: 'deepseek',
            candidates: 16,
            min_score: 30
        }
    };
    if (!defaults || typeof defaults !== 'object') return base;
    return {
        ...base,
        ...defaults,
        validators: { ...base.validators, ...(defaults.validators || {}) },
        hard_constraints: { ...base.hard_constraints, ...(defaults.hard_constraints || {}) },
        retrieval: { ...base.retrieval, ...(defaults.retrieval || {}) },
        rerank: { ...base.rerank, ...(defaults.rerank || {}) }
    };
}

function getEditableCommonDefaults(template) {
    return currentTemplateState.commonDefaultsDraft || getStoredCommonDefaults(template);
}

function renderCommonGenerationRules(template) {
    const container = document.getElementById('template-common-rules');
    if (!container) return;

    const defaults = getEditableCommonDefaults(template);
    const validators = defaults.validators || {};
    const hardConstraints = defaults.hard_constraints || {};
    const retrieval = defaults.retrieval || {};
    const rerank = defaults.rerank || {};
    const forbiddenTerms = Array.isArray(validators.forbidden_terms)
        ? validators.forbidden_terms.join('\n')
        : '';
    const forbiddenPhrases = Array.isArray(hardConstraints.forbidden_phrases)
        ? hardConstraints.forbidden_phrases.join('\n')
        : '';
    const forbiddenEntityCategories = Array.isArray(hardConstraints.forbidden_entity_categories)
        ? hardConstraints.forbidden_entity_categories.join('\n')
        : '';

    container.innerHTML = `
        <div class="panel-title-row">
            <h4>共用参数</h4>
            <span class="text-muted">所有 prompt 占位符默认继承</span>
        </div>
        <div class="template-common-rule-card">
            <h5>硬性生成约束</h5>
            <div class="template-common-check-grid">
                <label><input type="checkbox" data-common-rule-field="hard_constraints.no_wind_data" ${hardConstraints.no_wind_data !== false ? 'checked' : ''}><span>不使用 Wind 数据</span></label>
                <label><input type="checkbox" data-common-rule-field="hard_constraints.no_baidu_data" ${hardConstraints.no_baidu_data !== false ? 'checked' : ''}><span>不使用百度数据</span></label>
                <label><input type="checkbox" data-common-rule-field="hard_constraints.require_number_source" ${hardConstraints.require_number_source !== false ? 'checked' : ''}><span>数字必须说明来源</span></label>
                <label><input type="checkbox" data-common-rule-field="hard_constraints.single_paragraph" ${hardConstraints.single_paragraph !== false ? 'checked' : ''}><span>只输出一段，不换行</span></label>
            </div>
            <label class="template-common-field wide">
                <span>禁用短语（逗号或换行分隔）</span>
                <textarea data-common-rule-field="hard_constraints.forbidden_phrases" rows="3">${esc(forbiddenPhrases)}</textarea>
            </label>
            <label class="template-common-field wide">
                <span>禁用实体类别（逗号或换行分隔）</span>
                <textarea data-common-rule-field="hard_constraints.forbidden_entity_categories" rows="3">${esc(forbiddenEntityCategories)}</textarea>
            </label>
        </div>
        <div class="template-common-rule-card">
            <h5>检索配置</h5>
            <div class="template-common-rules-grid">
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
                    <input type="number" min="1" step="1" data-common-rule-field="retrieval.top_k" value="${esc(retrieval.top_k ?? 8)}">
                </label>
                <label class="template-common-field">
                    <span>候选数</span>
                    <input type="number" min="1" step="1" data-common-rule-field="retrieval.keyword_candidates" value="${esc(retrieval.keyword_candidates ?? 40)}">
                </label>
                <label class="template-common-field">
                    <span>语义候选数</span>
                    <input type="number" min="1" step="1" data-common-rule-field="retrieval.semantic_candidates" value="${esc(retrieval.semantic_candidates ?? 80)}">
                </label>
                <label class="template-common-field">
                    <span>Keyword 权重</span>
                    <input type="number" min="0" max="1" step="0.1" data-common-rule-field="retrieval.keyword_weight" value="${esc(retrieval.keyword_weight ?? 0.7)}">
                </label>
                <label class="template-common-field">
                    <span>Semantic 权重</span>
                    <input type="number" min="0" max="1" step="0.1" data-common-rule-field="retrieval.semantic_weight" value="${esc(retrieval.semantic_weight ?? 0.3)}">
                </label>
            </div>
        </div>
        <div class="template-common-rule-card">
            <h5>Rerank</h5>
            <div class="template-common-rules-grid">
                <label class="template-common-rules-check">
                    <input type="checkbox" data-common-rule-field="rerank.enabled" ${rerank.enabled !== false ? 'checked' : ''}>
                    <span>启用 DeepSeek/LLM 重排</span>
                </label>
                <label class="template-common-field">
                    <span>重排候选数</span>
                    <input type="number" min="1" step="1" data-common-rule-field="rerank.candidates" value="${esc(rerank.candidates ?? 16)}">
                </label>
                <label class="template-common-field">
                    <span>最低分</span>
                    <input type="number" min="0" step="1" data-common-rule-field="rerank.min_score" value="${esc(rerank.min_score ?? 30)}">
                </label>
            </div>
        </div>
    `;

    container.querySelectorAll('[data-common-rule-field]').forEach(input => {
        const update = () => {
            collectCommonDefaultsDraft(template);
            renderSelectedSourceFragment(template);
        };
        input.addEventListener('input', update);
        input.addEventListener('change', update);
    });
}

function collectCommonDefaultsDraft(template) {
    const container = document.getElementById('template-common-rules');
    if (!container) return getEditableCommonDefaults(template);

    const existing = getEditableCommonDefaults(template);
    const draft = {
        ...existing,
        validators: { ...(existing.validators || {}) },
        hard_constraints: { ...(existing.hard_constraints || {}) },
        retrieval: { ...(existing.retrieval || {}) },
        rerank: { ...(existing.rerank || {}) }
    };

    container.querySelectorAll('[data-common-rule-field]').forEach(input => {
        const field = input.dataset.commonRuleField;
        if (!field) return;
        let value;
        if (input.type === 'checkbox') {
            value = input.checked;
        } else if (field === 'validators.forbidden_terms'
            || field === 'hard_constraints.forbidden_phrases'
            || field === 'hard_constraints.forbidden_entity_categories') {
            value = String(input.value || '')
                .split(/[\n,，]/)
                .map(item => item.trim())
                .filter(Boolean);
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
    });

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
    const saveBtn = document.getElementById('btn-template-save-placeholder');
    if (!formEl) return;

    const name = normalizePlaceholderName(currentTemplateState.selectedPlaceholderName);
    const mapping = getSelectedPlaceholderMapping(template);
    if (!name || !mapping) {
        if (titleEl) titleEl.textContent = '占位符配置详情';
        formEl.innerHTML = '<div class="empty-state compact">从左侧选择一个 Word 占位符后编辑配置</div>';
        if (saveBtn) saveBtn.disabled = true;
        return;
    }

    if (titleEl) titleEl.textContent = `{{${name}}} 配置`;
    if (saveBtn) saveBtn.disabled = false;

    const type = mapping.type || inferPlaceholderType(name);
    const promptParam = mapping.params?.param || inferPromptParam(name);
    const needsParam = type === 'prompt' && Boolean(promptParam);
    const usesQuerySource = type === 'prompt' && !usesEmbeddedPromptQueries(template.report_project);
    const retrievalKeywords = getPlaceholderRetrievalKeywords(mapping, name).join('\n');

    formEl.innerHTML = `
        <label>
            <span>标题</span>
            <input type="text" data-placeholder-field="title" value="${esc(mapping.title || inferPlaceholderTitle(name))}">
        </label>
        <label>
            <span>类型</span>
            <select data-placeholder-field="type">
                ${['prompt', 'excel_cell', 'excel_range', 'static_text'].map(option => `
                    <option value="${option}" ${type === option ? 'selected' : ''}>${option}</option>
                `).join('')}
            </select>
        </label>
        ${type === 'prompt' ? `
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
            <label>
                <span>目标字数</span>
                <input type="number" min="1" step="1" data-placeholder-field="max_words" value="${esc(mapping.max_words || mapping.target_words || inferDefaultMaxWords(name))}">
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
            <label>
                <span>检索关键词（当前占位符）</span>
                <textarea data-placeholder-field="retrieval.keywords" rows="3">${esc(retrievalKeywords)}</textarea>
            </label>
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

    formEl.querySelectorAll('[data-placeholder-field]').forEach(input => {
        input.addEventListener('input', () => updateTemplateSourceFromPlaceholderDraft(template));
        input.addEventListener('change', () => {
            updateTemplateSourceFromPlaceholderDraft(template);
            if (input.dataset.placeholderField === 'type') {
                renderSelectedPlaceholderDetail(template);
                renderSelectedSourceFragment(template);
            }
        });
    });
}

function collectSelectedPlaceholderDraft(template) {
    const name = normalizePlaceholderName(currentTemplateState.selectedPlaceholderName);
    if (!name) return null;

    const formEl = document.getElementById('template-placeholder-detail-form');
    const existing = getSelectedPlaceholderMapping(template) || {};
    const draft = { ...existing };
    formEl?.querySelectorAll('[data-placeholder-field]').forEach(input => {
        const field = input.dataset.placeholderField;
        const value = input.value?.trim?.() || '';
        if (field === 'params.param') {
            draft.params = value ? { ...(draft.params || {}), param: value } : {};
        } else if (field === 'retrieval.keywords') {
            const keywords = splitDelimitedList(value);
            if (keywords.length) {
                draft.retrieval = { ...(draft.retrieval || {}), keywords };
            } else if (draft.retrieval) {
                delete draft.retrieval.keywords;
                if (!Object.keys(draft.retrieval).length) delete draft.retrieval;
            }
        } else if (field) {
            draft[field] = value;
        }
    });
    draft.title = draft.title || inferPlaceholderTitle(name);
    draft.type = draft.type || inferPlaceholderType(name);
    currentTemplateState.placeholderMappingDrafts = currentTemplateState.placeholderMappingDrafts || {};
    currentTemplateState.placeholderMappingDrafts[name] = draft;
    return { name, draft };
}

function getPlaceholderRetrievalKeywords(mapping, placeholderName = '') {
    const retrieval = mapping?.retrieval || {};
    const queryTerms = retrieval.query_terms || {};
    const keywords = retrieval.keywords || queryTerms.must_any || retrieval.must_any || [];
    if (Array.isArray(keywords) && keywords.length) return keywords;
    return inferPlaceholderKeywords(placeholderName);
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
    const allPlaceholdersMapped = placeholders.length === 0
        || placeholders.every(placeholder => placeholderMappings.has(normalizePlaceholderName(placeholder)));
    const hasPromptMapping = [...placeholderMappings.values()].some(mapping => mapping.prompt_template);
    const hasRuleConfig = sections.some(section =>
        section.evidence_policy
        || section.forbidden_terms?.length
        || section.investment_advice_policy
    ) || Boolean(template.report_project);

    return [
        { label: 'Word 占位符均有 section 映射', ok: allPlaceholdersMapped },
        { label: 'AI 文本 section 已配置 prompt', ok: hasPromptMapping || sections.some(section => section.prompt_template || section.required_facets?.length) },
        { label: 'Excel 图表和表格已绑定来源', ok: template.has_excel || (template.template_name || '').includes('创业板50') },
        { label: '数字、禁用词、投资建议规则已配置', ok: hasRuleConfig }
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
    const placeholders = getTemplateWorkbenchPlaceholders(template)
        .filter(placeholder => !isSystemDatePlaceholder(placeholder));
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
    const hardConstraints = defaults?.hard_constraints || {};
    const retrieval = defaults?.retrieval || {};
    const rerank = defaults?.rerank || {};
    const forbiddenTerms = Array.isArray(validators.forbidden_terms)
        ? validators.forbidden_terms
        : ['保本', '稳赚', '收益保证', '明确买入', '目标价'];
    const forbiddenPhrases = Array.isArray(hardConstraints.forbidden_phrases)
        ? hardConstraints.forbidden_phrases
        : ['根据文件', '据报道', '数据显示'];
    const forbiddenEntityCategories = Array.isArray(hardConstraints.forbidden_entity_categories)
        ? hardConstraints.forbidden_entity_categories
        : ['指数名称', '公司名称', '证券机构'];
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
    lines.push('  hard_constraints:');
    lines.push(`    no_wind_data: ${hardConstraints.no_wind_data !== false}`);
    lines.push(`    no_baidu_data: ${hardConstraints.no_baidu_data !== false}`);
    lines.push(`    require_number_source: ${hardConstraints.require_number_source !== false}`);
    lines.push(`    single_paragraph: ${hardConstraints.single_paragraph !== false}`);
    lines.push('    forbidden_phrases:');
    forbiddenPhrases.forEach(term => lines.push(`      - ${term}`));
    lines.push('    forbidden_entity_categories:');
    forbiddenEntityCategories.forEach(term => lines.push(`      - ${term}`));
    lines.push('  retrieval:');
    lines.push(`    mode: ${retrieval.mode || 'hybrid'}`);
    lines.push(`    top_k: ${retrieval.top_k ?? 8}`);
    lines.push(`    keyword_candidates: ${retrieval.keyword_candidates ?? 40}`);
    lines.push(`    semantic_candidates: ${retrieval.semantic_candidates ?? 80}`);
    lines.push(`    keyword_weight: ${retrieval.keyword_weight ?? 0.7}`);
    lines.push(`    semantic_weight: ${retrieval.semantic_weight ?? 0.3}`);
    lines.push('  rerank:');
    lines.push(`    enabled: ${rerank.enabled !== false}`);
    lines.push(`    provider: ${rerank.provider || 'deepseek'}`);
    lines.push(`    candidates: ${rerank.candidates ?? 16}`);
    lines.push(`    min_score: ${rerank.min_score ?? 30}`);
    return lines.join('\n');
}

function buildSelectedPlaceholderYamlFragment(template, existingMappings) {
    const key = normalizePlaceholderName(currentTemplateState.selectedPlaceholderName);
    if (!key) return '# 从左侧选择一个 Word 占位符后显示对应 YAML 片段';
    if (isSystemDatePlaceholder(key)) {
        return [
            'placeholders:',
            `  ${key}:`,
            `    title: ${inferPlaceholderTitle(key)}`,
            '    type: static_text',
            '    value: 系统生成时自动填充'
        ].join('\n');
    }
    const mapping = existingMappings.get(key) || {};
    return [
        '# 当前占位符片段',
        '# 继承 defaults: 硬性生成约束 / 检索配置 / Rerank / validators。',
        '# 下方只写当前占位符自己的覆盖项，例如 prompt_template、max_words、params。',
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
    } else if (type === 'prompt') {
        lines.push(`    prompt_template: ${mapping.prompt_template || resolvePromptTemplateName(key, project)}`);
        if (!usesEmbeddedPromptQueries(project)) {
            lines.push(`    query_source: ${mapping.query_source || inferQuerySource(key, project)}`);
        } else {
            lines.push('    query_mode: retrieval_query_embedded');
        }
        lines.push(`    max_words: ${mapping.max_words || mapping.target_words || inferDefaultMaxWords(key)}`);
        const retrieval = mapping.retrieval || {};
        const keywords = getPlaceholderRetrievalKeywords(mapping, key);
        if (retrieval.keyword_profile || keywords.length) {
            lines.push('    retrieval:');
            if (retrieval.keyword_profile) lines.push(`      keyword_profile: ${retrieval.keyword_profile}`);
            if (keywords.length) {
                lines.push('      keywords:');
                keywords.forEach(keyword => lines.push(`        - ${keyword}`));
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

function getSelectedPromptTemplateName(template) {
    const name = normalizePlaceholderName(currentTemplateState.selectedPlaceholderName);
    if (!name) return '';
    const mapping = getSelectedPlaceholderMapping(template) || {};
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
    if (isSystemDatePlaceholder(name)) return 'static_text';
    if (/^(start_date|end_date|data\d+)$/i.test(name)) return 'excel_cell';
    if (/^(content\d+|phrase\d+|sector\d+)$/i.test(name)) return 'prompt';
    if (/[\u4e00-\u9fff]/.test(name)) return 'prompt';
    return 'static_text';
}

function isSystemDatePlaceholder(name) {
    const normalized = normalizePlaceholderName(name);
    return ['开始日期', '结束日期', 'start_date', 'end_date'].includes(normalized);
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
    if (normalized === 'A股市场回顾') return 150;
    if (['美国新闻', '欧洲新闻'].includes(normalized)) return 250;
    if (['原油', '原油市场回顾', '黄金', '黄金市场回顾'].includes(normalized)) return 300;
    if (['中国宏观', '美国', '欧洲', '日本', '海外市场', '港股科技', '港股央企红利'].includes(normalized)) return 350;
    if (['人工智能', '医药生物', '消费', '金融地产', '电子', '航天', '电力设备新能源'].includes(normalized)) return 400;
    return 300;
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

    if (savePlaceholderBtn && !savePlaceholderBtn.dataset.bound) {
        savePlaceholderBtn.dataset.bound = 'true';
        savePlaceholderBtn.addEventListener('click', async () => {
            const template = getCurrentWorkbenchTemplate();
            if (!template) {
                toast('请先选择模板', 'error');
                return;
            }
            updateTemplateSourceFromPlaceholderDraft(template);
            const sourceEditor = document.getElementById('template-source-editor');
            if (!sourceEditor) return;
            const content = buildUpdatedSectionConfigSource(template, getEditablePlaceholderMappings(template));

            savePlaceholderBtn.disabled = true;
            const originalText = savePlaceholderBtn.innerHTML;
            savePlaceholderBtn.innerHTML = '<i class="codicon codicon-loading spin"></i> 保存中...';
            try {
                if (currentTemplateState.selectedReportProject) {
                    const project = currentTemplateState.selectedReportProject;
                    const updatedProject = await apiCall(
                        'PUT',
                        `/api/report-projects/${encodeURIComponent(project.slug)}/source`,
                        {
                            source_kind: 'section_config',
                            content
                        }
                    );
                    currentTemplateState.selectedReportProject = updatedProject;
                    const selectedTemplate = (currentTemplateState.templates || []).find(item =>
                        item.report_project?.slug === project.slug
                    );
                    if (selectedTemplate) selectedTemplate.report_project = updatedProject;
                    renderAdvancedMaintenance(selectedTemplate || template);
                    toast('占位符配置已保存', 'success');
                } else {
                    localStorage.setItem(sourceEditor.dataset.draftKey || 'report-template-source:draft', content);
                    toast('占位符配置草稿已保存到本地', 'success');
                }
            } catch (e) {
                toast('保存占位符失败: ' + e.message, 'error');
            } finally {
                savePlaceholderBtn.innerHTML = originalText;
                savePlaceholderBtn.disabled = false;
            }
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
        const renderedProjectSlug = currentTemplateState.selectedReportProject?.slug;
        if (renderedProjectSlug) {
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
            `;
            resultEl.classList.remove('hidden');
            if (previewUrl) {
                await loadRenderedReportPreview(previewUrl);
            }
        }
    } catch (e) {
        toast('渲染失败: ' + e.message, 'error');
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
