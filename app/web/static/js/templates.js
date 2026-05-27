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
    templates: []
};

let currentSelectedTemplate = null;
let currentSelectedFileType = null;
let isEditMode = false;
let draggedTemplateName = null;
let draggedElement = null;
let editingTemplateName = null;
let originalTemplates = [];

// ─── Template Page / List ──────────────────────────────────────
async function loadTemplatesPage() {
    try {
        await loadTemplatesList();
        initTemplateDropZone();
        await initTemplateSelects();
    } catch (e) {
        toast('加载模板页面失败: ' + e.message, 'error');
    }
}

async function loadTemplatesList() {
    try {
        const data = await apiCall('GET', '/api/templates/');
        currentTemplateState.templates = data.templates || [];
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

        return `
        <div class="${wrapperClasses.join(' ')}" data-template-name="${esc(templateName)}" data-index="${index}" ${isEditMode ? 'draggable="true" ondragstart="handleDragStart(event)" ondragover="handleDragOver(event)" ondrop="handleDrop(event)"' : ''}>
            <button class="iphone-delete-btn" onclick="event.stopPropagation(); deleteTemplate('${esc(templateName)}')"></button>
            <div class="iphone-app-icon ${fileType}" onclick="!isEditMode && selectTemplate('${esc(templateName)}', '${fileType}')">
                ${iconHtml}
            </div>
            <div class="iphone-app-name">${esc(templateName)}</div>
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
        const data = await apiCall('GET', '/api/templates/');
        const templates = data.templates || [];
        const template = templates.find(t => (t.template_name || t.name) === templateName);

        if (template) {
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
    clearPlaceholderData();
}

// ─── Upload Modal ──────────────────────────────────────────────
function openUploadModal() {
    document.getElementById('upload-template-modal').classList.remove('hidden');
    document.getElementById('template-name-input').value = '';
    document.getElementById('template-desc-input').value = '';
    document.getElementById('template-version-input').value = '1.0';
    document.getElementById('template-file-input').value = '';
    document.getElementById('selected-file-info').classList.add('hidden');
    document.getElementById('template-upload-status').innerHTML = '';
}

function closeUploadModal() {
    document.getElementById('upload-template-modal').classList.add('hidden');
}

// ─── Drag & Drop Reordering ────────────────────────────────────
function handleDragStart(event) {
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
        await apiCall('POST', '/api/templates/reorder', { template_names: newOrder });
        toast('模板顺序已更新', 'success');
    } catch (e) {
        toast('更新顺序失败: ' + e.message, 'error');
        await loadTemplates();
    }

    draggedTemplateName = null;
    draggedElement = null;
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
        await apiCall('POST', '/api/templates/reorder', { template_names: newOrder });

        toast('模板已保存', 'success');
        isEditMode = false;

        document.getElementById('btn-edit-templates').classList.remove('hidden');
        document.getElementById('btn-save-templates-order').classList.add('hidden');

        await loadTemplates();
    } catch (e) {
        toast('保存失败: ' + e.message, 'error');
    }
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
        try {
            const data = await apiCall('GET', `/api/templates/${encodeURIComponent(templateName)}/placeholders/${fileType}`);
            placeholders = data.placeholders || [];
        } catch (e) {
            placeholders = [];
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
    if (!file.name.match(/\.(pptx|docx)$/i)) {
        toast('请上传 .pptx 或 .docx 文件', 'error');
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
    const fileInput = document.getElementById('template-file-input');
    const nameInput = document.getElementById('template-name-input');
    const descInput = document.getElementById('template-desc-input');
    const versionInput = document.getElementById('template-version-input');
    const typeSelect = document.getElementById('template-type-select');
    const statusEl = document.getElementById('template-upload-status');

    const file = fileInput?.files?.[0];
    if (!file) {
        toast('请选择文件', 'error');
        return;
    }

    const name = nameInput?.value.trim() || file.name.replace(/\.(pptx|docx|xlsx)$/i, '');
    const description = descInput?.value.trim() || '';
    const version = versionInput?.value.trim() || '1.0';
    const fileType = typeSelect?.value || 'docx';

    let actualFileType = fileType;
    if (file.name.toLowerCase().endsWith('.pptx')) actualFileType = 'pptx';
    if (file.name.toLowerCase().endsWith('.xlsx')) actualFileType = 'excel';

    if (statusEl) {
        statusEl.innerHTML = '<div class="loading"><div class="spinner"></div><span>正在上传...</span></div>';
        statusEl.classList.remove('hidden');
    }

    const formData = new FormData();
    formData.append('file', file);
    formData.append('template_name', name);
    formData.append('file_type', actualFileType);
    formData.append('description', description);
    formData.append('version', version);

    try {
        const response = await fetch('/api/templates/upload', {
            method: 'POST',
            headers: { 'Authorization': 'Bearer dummy' },
            body: formData
        });

        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: 'Upload failed' }));
            throw new Error(error.detail || 'Upload failed');
        }

        const data = await response.json();
        toast('模板上传成功', 'success');
        await loadTemplatesList();
        await initTemplateSelects();
        switchTemplatesTab('configure');

        if (nameInput) nameInput.value = '';
        if (descInput) descInput.value = '';
        clearFileSelection();
    } catch (e) {
        toast('上传失败: ' + e.message, 'error');
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

        if (canonicalId) {
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

        currentTemplateState.renderedReportId = result.report_id;

        if (resultEl) {
            const downloadLink = document.getElementById('render-download-link');
            if (downloadLink && result.report_id) {
                downloadLink.href = `/api/templates/download/${encodeURIComponent(result.report_id)}`;
            }
            resultEl.innerHTML = `
                <div class="success-message">
                    <i class="codicon codicon-pass"></i>
                    <span>报告渲染成功！</span>
                </div>
                <a id="render-download-link" href="/api/templates/download/${encodeURIComponent(result.report_id)}"
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
    generateAiContent, generateAllAiFields, callLlmApi
};
