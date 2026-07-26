# 报告配置工作台降噪 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不改变报告配置工作台左右布局和现有编辑能力的前提下，默认只呈现当前段落的关键配置与下一步。

**Architecture:** `buildPlaceholderConfigSummaryHtml` 继续是右侧段落摘要的唯一渲染入口。它将把低频内容包装为原生 `details` 摘要区，保留原有 `data-placeholder-edit-section` 编辑触发器；生成检查继续使用既有预检模型，只将通过状态保持在紧凑摘要中。CSS 仅增加这套摘要区的布局、折叠和响应式样式。

**Tech Stack:** 原生 HTML、JavaScript、CSS、Pytest 静态前端测试。

---

### Task 1: 为默认折叠层级建立前端回归测试

**Files:**

- Modify: `tests/unit/test_report_template_workbench_frontend.py`
- Modify: `app/web/static/js/templates.js:buildPlaceholderConfigSummaryHtml`

- [ ] **Step 1: 写失败测试，明确常用区与低频区的 DOM 合同**

```python
def test_report_config_summary_collapses_low_frequency_sections():
    source = TEMPLATES_JS.read_text(encoding="utf-8")

    assert 'class="template-config-collapsible-section"' in source
    assert 'data-placeholder-edit-section="keywords"' in source
    assert 'data-placeholder-edit-section="fixed_template"' in source
    assert 'data-placeholder-edit-section="data_fields"' in source
    assert 'data-placeholder-edit-section="writing"' in source
```

- [ ] **Step 2: 运行测试确认当前实现不满足折叠合同**

Run: `/Users/leon/opt/anaconda3/bin/python3 -m pytest tests/unit/test_report_template_workbench_frontend.py -q`

Expected: 新增断言失败，因为低频配置仍以内联完整内容渲染。

- [ ] **Step 3: 在 `buildPlaceholderConfigSummaryHtml` 中增加统一的折叠摘要辅助函数**

```javascript
function buildConfigCollapsibleSection({ title, meta, editSection, body, open = false }) {
    return `<details class="template-config-collapsible-section" ${open ? 'open' : ''}>
        <summary><span><strong>${esc(title)}</strong><small>${esc(meta)}</small></span>
            <i class="codicon codicon-chevron-down" aria-hidden="true"></i></summary>
        <div class="template-config-collapsible-body">${body}
            <button class="template-config-inline-action template-config-edit-trigger"
                type="button" data-placeholder-edit-section="${esc(editSection)}">编辑</button>
        </div>
    </details>`;
}
```

- [ ] **Step 4: 重新运行前端测试，确认合同通过**

Run: `/Users/leon/opt/anaconda3/bin/python3 -m pytest tests/unit/test_report_template_workbench_frontend.py -q`

Expected: PASS。

- [ ] **Step 5: 提交测试与摘要结构**

```bash
git add tests/unit/test_report_template_workbench_frontend.py app/web/static/js/templates.js
git commit -m "feat: collapse low-frequency report config sections"
```

### Task 2: 将右侧段落摘要改为“当前动作优先”

**Files:**

- Modify: `app/web/static/js/templates.js:buildPlaceholderConfigSummaryHtml`
- Test: `tests/unit/test_report_template_workbench_frontend.py`

- [ ] **Step 1: 写失败测试，要求 Query 在缺失时成为默认展开项**

```python
def test_report_config_summary_prioritizes_missing_query():
    source = TEMPLATES_JS.read_text(encoding="utf-8")

    assert 'const queryNeedsAttention = usesEvidence && !semanticQuery.trim();' in source
    assert 'open: queryNeedsAttention' in source
    assert 'template-config-next-action' in source
```

- [ ] **Step 2: 运行测试确认问题优先状态尚未实现**

Run: `/Users/leon/opt/anaconda3/bin/python3 -m pytest tests/unit/test_report_template_workbench_frontend.py -q`

Expected: FAIL，尚未根据 Query 是否缺失选择展开项。

- [ ] **Step 3: 用明确的完成度计算替换同时展开的内容区**

```javascript
const queryNeedsAttention = usesEvidence && !semanticQuery.trim();
const nextAction = queryNeedsAttention
    ? '补充语义 Query，明确系统应召回哪些材料。'
    : keywordList.length === 0 && usesEvidence
        ? '选择关键词预设包，或添加自定义关键词。'
        : '';
```

Use `buildConfigCollapsibleSection` for keywords, fixed template, data fields, and writing. Keep the basic fact grid visible; keep Query visible as its own concise card and attach its existing edit trigger. Do not remove any `data-placeholder-edit-section` values used by `openPlaceholderConfigEditorModal`.

- [ ] **Step 4: 运行测试确认问题优先和可达编辑入口都通过**

Run: `/Users/leon/opt/anaconda3/bin/python3 -m pytest tests/unit/test_report_template_workbench_frontend.py -q`

Expected: PASS。

- [ ] **Step 5: 提交当前动作优先逻辑**

```bash
git add app/web/static/js/templates.js tests/unit/test_report_template_workbench_frontend.py
git commit -m "feat: prioritize current report config action"
```

### Task 3: 为可折叠摘要补充样式，并保持检查区紧凑

**Files:**

- Modify: `app/web/static/style.css`
- Modify: `tests/unit/test_report_template_workbench_frontend.py`

- [ ] **Step 1: 写失败测试，要求折叠区与下一步提示拥有独立样式钩子**

```python
def test_report_config_summary_has_compact_collapsible_styles():
    css = STYLE_CSS.read_text(encoding="utf-8")

    assert '.template-config-collapsible-section' in css
    assert '.template-config-collapsible-section > summary' in css
    assert '.template-config-next-action' in css
```

- [ ] **Step 2: 运行测试确认样式钩子不存在**

Run: `/Users/leon/opt/anaconda3/bin/python3 -m pytest tests/unit/test_report_template_workbench_frontend.py -q`

Expected: FAIL。

- [ ] **Step 3: 添加紧凑摘要样式和窄屏回退**

```css
.template-config-collapsible-section { border: 1px solid var(--border-color); border-radius: 10px; }
.template-config-collapsible-section > summary { display: flex; justify-content: space-between; align-items: center; min-height: 52px; padding: 0 14px; cursor: pointer; }
.template-config-next-action { margin: 14px 0; padding: 10px 12px; border-left: 3px solid var(--apple-accent); }
```

Add a mobile rule that lets the summary header wrap and keeps the edit action usable. Do not change `.template-config-grid` column definitions or move `#template-project-check-details` out of the left rail.

- [ ] **Step 4: 运行前端测试、语法检查与样式差异检查**

Run:

```bash
/Users/leon/opt/anaconda3/bin/python3 -m pytest tests/unit/test_report_template_workbench_frontend.py -q
/Users/leon/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node --check app/web/static/js/templates.js
git diff --check
```

Expected: all commands exit 0.

- [ ] **Step 5: 提交视觉降噪样式**

```bash
git add app/web/static/style.css tests/unit/test_report_template_workbench_frontend.py
git commit -m "style: reduce report config workspace noise"
```

### Task 4: 进行相关回归并记录范围外失败

**Files:**

- Verify: `tests/unit/test_report_template_workbench_frontend.py`
- Verify: `tests/unit/test_alembic_migration_graph.py`
- Verify: `tests/unit/core/services/test_crawl_scheduler.py`

- [ ] **Step 1: 运行本分支相关回归测试**

Run:

```bash
/Users/leon/opt/anaconda3/bin/python3 -m pytest \
  tests/unit/test_report_template_workbench_frontend.py \
  tests/unit/test_alembic_migration_graph.py \
  tests/unit/core/services/test_crawl_scheduler.py -q
```

Expected: PASS。

- [ ] **Step 2: 运行完整单元套件并区分本次回归与既有基线失败**

Run: `/Users/leon/opt/anaconda3/bin/python3 -m pytest tests/unit -q`

Expected: 本次涉及的报告配置文件没有失败；若仍存在已知行业图资源、干跑数据库、宏观敏感度或治理日志失败，记录为范围外基线。

- [ ] **Step 3: 检查提交前工作区**

Run: `git status --short && git log --oneline -6`

Expected: 仅包含本计划产生的提交，不包含测试生成文件。

