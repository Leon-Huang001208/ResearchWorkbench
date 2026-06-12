# Weekly Report Generation Center Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert the report template detail page into a generation-first weekly report center while preserving the existing advanced template maintenance tools.

**Architecture:** Keep the current single-page frontend and existing `/api/report-projects` backend contract. Reorganize the template detail DOM so the primary surface is a generation center, then reuse the existing placeholder editor, YAML/Prompt source editor, Excel mapping, and validation functions inside a collapsed advanced maintenance section.

**Tech Stack:** FastAPI static HTML, vanilla JavaScript modules in `app/web/static/js/templates.js`, CSS in `app/web/static/style.css`, pytest static wiring tests.

---

## File Structure

- Modify `tests/unit/test_report_template_workbench_frontend.py`: add failing static contract tests for the new generation center and update the style expectations from the old full-height workbench to the new sectioned layout.
- Modify `app/web/templates/index.html`: replace the current “报告模板工作台” top-level workbench layout with a “周报生成中心” structure containing generation hero, status strip, recent output/check panels, and collapsed advanced maintenance.
- Modify `app/web/static/js/templates.js`: add generation readiness helpers and renderers, wire existing actions into the new DOM, and keep existing advanced editor functions alive.
- Modify `app/web/static/style.css`: add generation-center layout styles and responsive rules, while retaining existing advanced editor styles for the folded maintenance area.

## Task 1: Lock The New Frontend Contract In Tests

**Files:**
- Modify: `tests/unit/test_report_template_workbench_frontend.py`

- [ ] **Step 1: Add a failing HTML contract test**

Add this test after `test_template_detail_has_report_workbench_regions`:

```python
def test_template_detail_prioritizes_weekly_report_generation_center():
    html = INDEX_HTML.read_text(encoding="utf-8")

    assert 'id="template-generation-center"' in html
    assert "周报生成中心" in html
    assert "生成本周报告" in html
    assert 'id="template-generation-period"' in html
    assert 'id="template-generation-lookback"' in html
    assert 'id="template-generation-status-strip"' in html
    assert 'id="template-generation-step-data"' in html
    assert 'id="template-generation-step-content"' in html
    assert 'id="template-generation-step-output"' in html
    assert 'id="template-recent-generation-panel"' in html
    assert 'id="template-generation-readiness-panel"' in html
    assert 'id="template-advanced-maintenance"' in html
    assert "高级维护：模板、占位符、Prompt、YAML" in html
    assert "报告模板工作台" not in html
    assert "Word 占位符、Excel 底稿、Section 配置统一维护" not in html
```

- [ ] **Step 2: Add a failing JavaScript contract test**

Add this test after `test_templates_js_populates_report_workbench`:

```python
def test_templates_js_renders_generation_center_and_reuses_advanced_workbench():
    source = TEMPLATES_JS.read_text(encoding="utf-8")

    assert "renderReportGenerationCenter" in source
    assert "buildGenerationReadiness" in source
    assert "renderGenerationHero" in source
    assert "renderGenerationStatusStrip" in source
    assert "renderRecentGenerationPanel" in source
    assert "renderAdvancedMaintenance" in source
    assert "template-generation-period" in source
    assert "template-generation-lookback" in source
    assert "template-generation-status-strip" in source
    assert "template-recent-generation-panel" in source
    assert "template-generation-readiness-panel" in source
    assert "template-advanced-maintenance" in source
    assert "最近生成" in source
    assert "尚未生成" in source
```

- [ ] **Step 3: Add a failing CSS contract test**

Add this test near `test_report_template_workbench_styles_exist`:

```python
def test_weekly_report_generation_center_styles_exist():
    css = STYLE_CSS.read_text(encoding="utf-8")

    assert ".template-generation-center" in css
    assert ".template-generation-hero" in css
    assert ".template-generation-actions" in css
    assert ".template-generation-status-strip" in css
    assert ".template-generation-step" in css
    assert ".template-generation-panels" in css
    assert ".template-recent-generation-card" in css
    assert ".template-advanced-maintenance" in css
    assert ".template-advanced-maintenance[open]" in css
```

- [ ] **Step 4: Run the targeted test file and verify it fails**

Run:

```bash
/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/bin/python3 -m pytest tests/unit/test_report_template_workbench_frontend.py -q
```

Expected: FAIL on the three new tests because the HTML, JavaScript functions, and CSS classes do not exist yet.

## Task 2: Rebuild The Template Detail HTML Around Generation

**Files:**
- Modify: `app/web/templates/index.html:939-1030`
- Test: `tests/unit/test_report_template_workbench_frontend.py`

- [ ] **Step 1: Replace the workbench header and main-grid shell**

In `app/web/templates/index.html`, replace the `div` with `id="template-workbench-summary"` content from the existing workbench header through the closing `</div>` for `.template-workbench-main-grid` with this structure:

```html
                        <!-- Weekly Report Generation Center -->
                        <div class="template-generation-center" id="template-generation-center">
                            <section class="template-generation-hero">
                                <div class="template-generation-copy">
                                    <p class="eyebrow">周报生成中心</p>
                                    <h3 id="template-generation-title">生成本周报告</h3>
                                    <div class="template-generation-meta">
                                        <span id="template-generation-period">报告周期待加载</span>
                                        <span id="template-generation-lookback">证据检索 7 天</span>
                                        <span id="template-generation-placeholder-total">0 个占位符</span>
                                    </div>
                                </div>
                                <div class="template-generation-actions">
                                    <button id="btn-template-generate-report" class="btn-primary"><i class="codicon codicon-play"></i> 生成报告</button>
                                    <button id="btn-template-preview-report" class="btn-secondary" disabled><i class="codicon codicon-open-preview"></i> 预览最近版本</button>
                                    <a id="btn-template-download-report" class="btn-secondary disabled" href="#" aria-disabled="true"><i class="codicon codicon-cloud-download"></i> 下载文档</a>
                                </div>
                            </section>

                            <section class="template-generation-status-strip" id="template-generation-status-strip">
                                <div class="template-generation-step" id="template-generation-step-data">
                                    <span class="step-index">1</span>
                                    <div>
                                        <strong>数据就绪</strong>
                                        <small id="template-generation-data-summary">Word、Excel、配套数据待检查</small>
                                    </div>
                                </div>
                                <div class="template-generation-step" id="template-generation-step-content">
                                    <span class="step-index">2</span>
                                    <div>
                                        <strong>内容就绪</strong>
                                        <small id="template-generation-content-summary">段落和 Prompt 待检查</small>
                                    </div>
                                </div>
                                <div class="template-generation-step" id="template-generation-step-output">
                                    <span class="step-index">3</span>
                                    <div>
                                        <strong>输出就绪</strong>
                                        <small id="template-generation-output-summary">生成后可预览和下载</small>
                                    </div>
                                </div>
                            </section>

                            <section class="template-generation-panels">
                                <div class="template-workbench-panel" id="template-recent-generation-panel">
                                    <div class="panel-title-row">
                                        <h4>最近生成</h4>
                                        <span id="template-recent-generation-status" class="badge">尚未生成</span>
                                    </div>
                                    <div id="template-recent-generation-card" class="template-recent-generation-card">
                                        <div class="empty-state compact">生成报告后显示预览和下载入口</div>
                                    </div>
                                </div>

                                <details class="template-workbench-panel template-project-check-panel" id="template-project-check-details">
                                    <summary>
                                        <span><i class="codicon codicon-checklist"></i> 生成前检查</span>
                                        <small id="template-project-check-summary">素材、数据和生成规则</small>
                                        <strong id="template-project-check-status" class="badge">待加载</strong>
                                    </summary>
                                    <div class="template-project-check-body" id="template-generation-readiness-panel">
                                        <div class="template-project-check-section">
                                            <div class="panel-title-row compact">
                                                <h4>模板资产</h4>
                                                <span id="template-asset-status" class="badge">待加载</span>
                                            </div>
                                            <div id="template-asset-checklist" class="template-asset-checklist">
                                                <div class="asset-check-item"><i class="codicon codicon-file-code"></i><span>Word 模板</span><strong>未确认</strong></div>
                                                <div class="asset-check-item"><i class="codicon codicon-table"></i><span>主 Excel 底稿</span><strong>未确认</strong></div>
                                                <div class="asset-check-item"><i class="codicon codicon-settings-gear"></i><span>Section 配置</span><strong>未确认</strong></div>
                                            </div>
                                        </div>

                                        <div class="template-project-check-section">
                                            <div class="panel-title-row compact">
                                                <h4>Excel 底稿映射</h4>
                                                <span class="text-muted">数据槽 / 图表 / 表格</span>
                                            </div>
                                            <div id="template-excel-mapping" class="template-mapping-table">
                                                <div class="empty-state compact">绑定 Excel 后显示数据来源</div>
                                            </div>
                                        </div>

                                        <div class="template-project-check-section" id="template-validation-preview">
                                            <div class="panel-title-row compact">
                                                <h4>生成预检</h4>
                                                <span id="template-validation-status" class="badge">未运行</span>
                                            </div>
                                            <div id="template-validation-list" class="template-validation-list">
                                                <div class="validation-item pending"><i class="codicon codicon-circle-outline"></i><span>Word 占位符均有 section 映射</span></div>
                                                <div class="validation-item pending"><i class="codicon codicon-circle-outline"></i><span>AI 文本 section 已配置 prompt</span></div>
                                                <div class="validation-item pending"><i class="codicon codicon-circle-outline"></i><span>Excel 图表和表格已绑定来源</span></div>
                                                <div class="validation-item pending"><i class="codicon codicon-circle-outline"></i><span>数字、禁用词、投资建议规则已配置</span></div>
                                            </div>
                                        </div>
                                    </div>
                                </details>
                            </section>

                            <details class="template-advanced-maintenance" id="template-advanced-maintenance">
                                <summary>
                                    <span><i class="codicon codicon-tools"></i> 高级维护：模板、占位符、Prompt、YAML</span>
                                    <small>维护 Word 占位符、Section 配置、Prompt 模板和 Excel 映射</small>
                                </summary>
                                <div class="template-workbench-main-grid">
                                    <div class="template-workbench-left">
                                        <div class="template-workbench-panel">
                                            <div class="panel-title-row">
                                                <h4>选择占位符</h4>
                                                <span id="template-placeholder-count" class="text-muted">0 个</span>
                                            </div>
                                            <div id="template-placeholder-map" class="template-placeholder-map">
                                                <div class="empty-state compact">选择模板后显示占位符映射</div>
                                            </div>
                                        </div>
                                    </div>

                                    <div class="template-workbench-panel template-section-editor-panel" id="template-section-config-editor">
                                        <div class="panel-title-row">
                                            <h4 id="template-selected-placeholder-title">占位符配置详情</h4>
                                            <button id="btn-template-save-placeholder" class="btn-secondary" disabled><i class="codicon codicon-save"></i> 保存当前占位符</button>
                                        </div>
                                        <div id="template-placeholder-detail-form" class="template-placeholder-detail-form">
                                            <div class="empty-state compact">从左侧选择一个 Word 占位符后编辑配置</div>
                                        </div>
                                        <div class="panel-title-row template-source-fragment-title">
                                            <h4>当前片段源码</h4>
                                            <span id="template-source-kind-label" class="text-muted">YAML / Markdown Prompt</span>
                                        </div>
                                        <div class="template-source-switcher">
                                            <button id="btn-template-source-section" class="source-switch-btn active" type="button">当前 YAML</button>
                                            <button id="btn-template-source-prompt" class="source-switch-btn" type="button">Prompt 模板</button>
                                        </div>
                                        <div class="template-workbench-actions template-source-actions">
                                            <button id="btn-template-edit-source" class="btn-secondary"><i class="codicon codicon-edit"></i> 查看片段</button>
                                            <button id="btn-template-save-source" class="btn-secondary" disabled><i class="codicon codicon-save"></i> 保存当前片段</button>
                                        </div>
                                        <textarea id="template-source-editor" class="template-source-editor" spellcheck="false" readonly>选择模板后生成配置草稿...</textarea>
                                    </div>
                                </div>
                            </details>
                        </div>
```

- [ ] **Step 2: Run the targeted test file**

Run:

```bash
/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/bin/python3 -m pytest tests/unit/test_report_template_workbench_frontend.py -q
```

Expected: HTML contract test passes. JavaScript and CSS contract tests still fail.

## Task 3: Add Generation Center Rendering Helpers

**Files:**
- Modify: `app/web/static/js/templates.js`
- Test: `tests/unit/test_report_template_workbench_frontend.py`

- [ ] **Step 1: Change the detail renderer entry point**

In `loadTemplateDetails`, replace:

```javascript
            renderTemplateWorkbench(template);
```

with:

```javascript
            renderReportGenerationCenter(template);
```

- [ ] **Step 2: Add the generation center wrapper**

Insert this function immediately before the existing `renderTemplateWorkbench(template)` function:

```javascript
function renderReportGenerationCenter(template) {
    const project = template.report_project || null;
    const placeholders = getTemplateWorkbenchPlaceholders(template);
    const sections = getTemplateWorkbenchSections(template);
    const readiness = buildGenerationReadiness(template, sections, placeholders);

    renderGenerationHero(template, readiness);
    renderGenerationStatusStrip(readiness);
    renderRecentGenerationPanel(template);
    renderAdvancedMaintenance(template);
}
```

- [ ] **Step 3: Keep existing workbench logic as advanced maintenance**

Rename the existing function declaration:

```javascript
function renderTemplateWorkbench(template) {
```

to:

```javascript
function renderAdvancedMaintenance(template) {
```

Inside `saveSelectedPlaceholderConfig`, replace:

```javascript
        renderTemplateWorkbench(selectedTemplate || template);
```

with:

```javascript
        renderReportGenerationCenter(selectedTemplate || template);
```

- [ ] **Step 4: Add readiness and hero helpers**

Insert these functions after `renderReportGenerationCenter`:

```javascript
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
```

- [ ] **Step 5: Ensure generation completion refreshes the center**

In `renderReportProject`, after the successful result updates `currentTemplateState.renderedReportId`, add this refresh before rendering the success status:

```javascript
            await loadReportProjectsList();
            const refreshedProject = await findReportProjectForTemplate(currentSelectedTemplate);
            const selectedTemplate = getCurrentWorkbenchTemplate();
            if (selectedTemplate && refreshedProject) {
                selectedTemplate.report_project = refreshedProject;
                currentTemplateState.selectedReportProject = refreshedProject;
                renderReportGenerationCenter(selectedTemplate);
            }
```

- [ ] **Step 6: Run the targeted test file**

Run:

```bash
/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/bin/python3 -m pytest tests/unit/test_report_template_workbench_frontend.py -q
```

Expected: HTML and JavaScript contract tests pass. CSS contract test still fails.

## Task 4: Add Generation Center Styling

**Files:**
- Modify: `app/web/static/style.css`
- Test: `tests/unit/test_report_template_workbench_frontend.py`

- [ ] **Step 1: Add generation center CSS**

Add this CSS before the existing `.template-workbench` block:

```css
.template-generation-center {
    display: grid;
    gap: 1rem;
    margin-bottom: 1.5rem;
}

.template-generation-hero {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 1rem;
    padding: 1.25rem 1.5rem;
    border: 1px solid var(--border);
    border-radius: var(--radius);
    background: var(--bg-card);
    box-shadow: var(--shadow-sm);
}

.template-generation-copy h3 {
    margin: 0;
    font-size: 1.15rem;
    font-weight: 650;
    color: var(--text-primary);
}

.template-generation-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    margin-top: 0.75rem;
}

.template-generation-meta span {
    padding: 0.32rem 0.55rem;
    border: 1px solid var(--border);
    border-radius: 6px;
    background: var(--bg-secondary);
    color: var(--text-secondary);
    font-size: 0.78rem;
}

.template-generation-actions {
    display: flex;
    gap: 0.65rem;
    flex-wrap: wrap;
    justify-content: flex-end;
}

.template-generation-status-strip {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 0.75rem;
}

.template-generation-step {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr);
    gap: 0.7rem;
    min-height: 74px;
    padding: 0.9rem;
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    background: var(--bg-card);
}

.template-generation-step .step-index {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    border-radius: 50%;
    background: var(--bg-secondary);
    color: var(--text-secondary);
    font-weight: 700;
}

.template-generation-step strong,
.template-recent-generation-card strong {
    display: block;
    color: var(--text-primary);
}

.template-generation-step small,
.template-recent-generation-card small {
    display: block;
    margin-top: 0.22rem;
    color: var(--text-muted);
    line-height: 1.35;
}

.template-generation-step.ok .step-index {
    background: var(--success);
    color: white;
}

.template-generation-step.pending .step-index {
    background: var(--bg-secondary);
    color: var(--warning);
}

.template-generation-panels {
    display: grid;
    grid-template-columns: minmax(0, 1.05fr) minmax(360px, 0.95fr);
    gap: 1rem;
}

.template-recent-generation-card {
    display: grid;
    gap: 0.7rem;
    min-height: 132px;
    align-content: start;
}

.template-recent-generation-actions {
    display: flex;
    gap: 0.6rem;
    flex-wrap: wrap;
}

.template-advanced-maintenance {
    border: 1px solid var(--border);
    border-radius: var(--radius);
    background: var(--bg-card);
    box-shadow: var(--shadow-sm);
    overflow: hidden;
}

.template-advanced-maintenance > summary {
    display: flex;
    justify-content: space-between;
    gap: 1rem;
    padding: 0.9rem 1rem;
    cursor: pointer;
    list-style: none;
}

.template-advanced-maintenance > summary::-webkit-details-marker {
    display: none;
}

.template-advanced-maintenance > summary span {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    color: var(--text-primary);
    font-weight: 650;
}

.template-advanced-maintenance > summary small {
    color: var(--text-muted);
}

.template-advanced-maintenance[open] > summary {
    border-bottom: 1px solid var(--border);
}

.template-source-actions {
    margin-bottom: 0.75rem;
}
```

- [ ] **Step 2: Update responsive CSS**

Inside the existing `@media` block that already handles `.template-workbench-header` and `.template-workbench-main-grid`, add these selectors:

```css
    .template-generation-hero,
    .template-generation-actions {
        flex-direction: column;
        align-items: stretch;
    }

    .template-generation-status-strip,
    .template-generation-panels {
        grid-template-columns: 1fr;
    }
```

- [ ] **Step 3: Run the targeted test file**

Run:

```bash
/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/bin/python3 -m pytest tests/unit/test_report_template_workbench_frontend.py -q
```

Expected: PASS.

## Task 5: Browser And Regression Verification

**Files:**
- No source edits expected unless verification finds a layout issue.

- [ ] **Step 1: Run focused Python tests**

Run:

```bash
/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/bin/python3 -m pytest tests/unit/test_report_template_workbench_frontend.py tests/unit/test_report_projects_api.py -q
```

Expected: PASS. If `test_report_projects_api.py` fails from unrelated environment data, capture the failing test name and error before changing code.

- [ ] **Step 2: Start or reuse the local app server**

Run:

```bash
./scripts/start_all.sh
```

Expected: a local web UI is available. Use the port printed by the script. If the script reports an existing server, use that URL.

- [ ] **Step 3: Verify the page in the in-app browser**

Open the app URL in Browser, navigate to 模板管理, open “华安ETF周报”, and verify:

- The first visible card says “周报生成中心”.
- “生成报告” is the primary action.
- “数据就绪 / 内容就绪 / 输出就绪” appear before advanced maintenance.
- “高级维护：模板、占位符、Prompt、YAML” is collapsed by default.
- Expanding advanced maintenance shows the placeholder selector, current YAML/Prompt switcher, save current placeholder button, and source editor.
- There is no incoherent text overlap at the desktop viewport.

- [ ] **Step 4: Check git diff**

Run:

```bash
git diff -- app/web/templates/index.html app/web/static/js/templates.js app/web/static/style.css tests/unit/test_report_template_workbench_frontend.py
```

Expected: diff only contains generation-center UI, helper rendering code, CSS, and tests.

- [ ] **Step 5: Commit implementation**

Run:

```bash
git add app/web/templates/index.html app/web/static/js/templates.js app/web/static/style.css tests/unit/test_report_template_workbench_frontend.py
git commit -m "feat: prioritize weekly report generation center"
```

Expected: commit succeeds.

## Self-Review

- Spec coverage: the plan covers generation-first hero, lightweight status strip, recent generation/check panels, collapsed advanced maintenance, no backend API changes, preserved YAML/Prompt/Excel/placeholder maintenance, error states through existing rendering, and tests.
- Placeholder scan: the plan contains no unresolved placeholders or undefined work items.
- Type consistency: helper names are consistent across tests and implementation steps: `renderReportGenerationCenter`, `buildGenerationReadiness`, `renderGenerationHero`, `renderGenerationStatusStrip`, `renderRecentGenerationPanel`, and `renderAdvancedMaintenance`.
