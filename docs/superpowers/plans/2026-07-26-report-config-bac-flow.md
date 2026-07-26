# 报告配置 B-A-C 流程 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 依次让当前段落编辑、段落选择和配置完成后的生成交接更明确。

**Architecture:** 复用 `templates.js` 已有占位符完成度、选择器、保存和预检状态。B 在 `renderSelectedPlaceholderDetail` 与保存回调中补状态消息；A 在 `template-placeholder-map` 渲染中增加状态分组；C 在已有进度条和“下一个未完成”按钮上切换行动语义，不新增 API 或页面骨架。

**Tech Stack:** Vanilla JavaScript、CSS、Pytest 静态前端测试。

---

### Task 1: B — 当前段落的下一步与保存反馈

**Files:**
- Modify: `app/web/static/js/templates.js:3906-4800,8752-8840`
- Modify: `app/web/static/style.css`
- Test: `tests/unit/test_report_template_workbench_frontend.py`

- [ ] **Step 1: 写失败测试**

```python
def test_report_config_exposes_current_action_and_save_feedback():
    source = TEMPLATES_JS.read_text(encoding="utf-8")
    assert 'id="template-config-save-feedback"' in source
    assert 'renderPlaceholderSaveFeedback' in source
    assert 'data-placeholder-edit-section="query"' in source
```

- [ ] **Step 2: 运行测试确认失败**

Run: `/Users/leon/opt/anaconda3/bin/python3 -m pytest tests/unit/test_report_template_workbench_frontend.py -q`

Expected: 新断言失败。

- [ ] **Step 3: 实现最小状态消息**

在 `renderSelectedPlaceholderDetail` 的摘要容器附近插入 `#template-config-save-feedback`；新增 `renderPlaceholderSaveFeedback(message, tone = 'success')`，只更新该元素的文本、hidden 和 `data-tone`。在 `savePlaceholderConfig` 成功后调用：

```javascript
renderPlaceholderSaveFeedback('已保存当前段落。', 'success');
```

保留既有 toast、保存和“保存并下一个”逻辑；点击已有 `.template-config-next-action` 仍由既有编辑触发器打开对应编辑区。

- [ ] **Step 4: 添加反馈样式并验证**

添加 `.template-config-save-feedback[data-tone="success"]` 与窄屏规则；不得修改左右栏网格。运行定向 pytest、Node 语法检查和 `git diff --check`。

- [ ] **Step 5: 提交**

```bash
git add app/web/static/js/templates.js app/web/static/style.css tests/unit/test_report_template_workbench_frontend.py
git commit -m "feat: clarify current report config action"
```

### Task 2: A — 按状态分组段落选择

**Files:**
- Modify: `app/web/static/js/templates.js:2555-2760,3622-3680`
- Modify: `app/web/static/style.css`
- Test: `tests/unit/test_report_template_workbench_frontend.py`

- [ ] **Step 1: 写失败测试**

```python
def test_report_config_groups_placeholder_choices_by_readiness():
    source = TEMPLATES_JS.read_text(encoding="utf-8")
    assert 'template-placeholder-map-group' in source
    assert '需要处理' in source
    assert '已完成' in source
    assert 'data-placeholder-readiness' in source
```

- [ ] **Step 2: 运行测试确认失败**

Run: `/Users/leon/opt/anaconda3/bin/python3 -m pytest tests/unit/test_report_template_workbench_frontend.py -q`

Expected: 新断言失败。

- [ ] **Step 3: 用已有 readiness 分组渲染选项**

在渲染 `#template-placeholder-map` 的函数中依据现有 `placeholderReadiness` 将选项分为 `needs_attention` 和 `ready`。每组输出：

```html
<div class="template-placeholder-map-group" data-placeholder-readiness="needs_attention">
  <span class="template-placeholder-map-group-label">需要处理</span>
  <!-- existing placeholder-select-option buttons -->
</div>
```

按钮保留 `data-placeholder-name`、原点击事件和可读标题；状态文本仅使用已有 lifecycle/readiness 标签，不展示内部变量名。

- [ ] **Step 4: 添加紧凑分组样式并验证**

添加组标题、状态色和窄屏样式，不更改现有选择事件。运行定向 pytest、Node 语法检查、差异检查。

- [ ] **Step 5: 提交**

```bash
git add app/web/static/js/templates.js app/web/static/style.css tests/unit/test_report_template_workbench_frontend.py
git commit -m "feat: group report sections by readiness"
```

### Task 3: C — 完成配置后的检查与生成交接

**Files:**
- Modify: `app/web/static/js/templates.js:2739-2760,7050-7130,7817-7850`
- Modify: `app/web/templates/index.html`
- Modify: `app/web/static/style.css`
- Test: `tests/unit/test_report_template_workbench_frontend.py`

- [ ] **Step 1: 写失败测试**

```python
def test_report_config_completion_cta_switches_from_next_item_to_preflight():
    html = INDEX_HTML.read_text(encoding="utf-8")
    source = TEMPLATES_JS.read_text(encoding="utf-8")
    assert 'id="btn-template-review-preflight"' in html
    assert '查看生成前检查' in source
    assert 'openProjectCheckPanel' in source
```

- [ ] **Step 2: 运行测试确认失败**

Run: `/Users/leon/opt/anaconda3/bin/python3 -m pytest tests/unit/test_report_template_workbench_frontend.py -q`

Expected: 新断言失败。

- [ ] **Step 3: 实现完成状态切换**

新增 `#btn-template-review-preflight`，默认 hidden。更新现有完成度刷新函数：存在未完成项时保留 `#btn-template-next-incomplete-placeholder`；全部完成时隐藏它、显示“查看生成前检查”。点击新按钮调用：

```javascript
openProjectCheckPanel('template-validation-preview');
```

进度文字在未完成时包含“还差 n 项”；完成时显示“全部段落已配置，可查看生成前检查”。不直接触发生成。

- [ ] **Step 4: 添加 CTA 样式并验证**

为完成 CTA 使用既有主按钮样式和窄屏规则。运行定向 pytest、Node 语法检查、差异检查。

- [ ] **Step 5: 提交**

```bash
git add app/web/templates/index.html app/web/static/js/templates.js app/web/static/style.css tests/unit/test_report_template_workbench_frontend.py
git commit -m "feat: guide report config completion to preflight"
```

### Task 4: 全量相关回归

- [ ] **Step 1: 运行报告配置及分支相关测试**

```bash
/Users/leon/opt/anaconda3/bin/python3 -m pytest \
  tests/unit/test_report_template_workbench_frontend.py \
  tests/unit/test_alembic_migration_graph.py \
  tests/unit/core/services/test_crawl_scheduler.py -q
/Users/leon/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node --check app/web/static/js/templates.js
git diff --check
```

Expected: all commands exit 0.

- [ ] **Step 2: 运行完整单元套件**

Run: `/Users/leon/opt/anaconda3/bin/python3 -m pytest tests/unit -q`

Expected: 报告配置相关用例通过；已知范围外基线失败单独记录。

