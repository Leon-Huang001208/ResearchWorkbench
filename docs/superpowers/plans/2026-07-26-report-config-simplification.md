# 报告生产配置页精简 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让配置页正常时只显示“是否可生成”和本期必要设置，异常时只展示可直接处理的阻断待办；完整预检改为按需展开。

**Architecture:** 保持后端 `CompiledReportPlan`、`buildGenerationReadiness()` 和生成拦截语义不变。前端新增一个纯展示模型，把现有 `assetChecks`、`validationChecks`、`placeholderReadiness` 映射为 ready/blocked 摘要、前三项待办和既有完整详情。

**Tech Stack:** 原生 ES modules、HTML `<details>`、CSS、Python `pytest` 静态前端接线测试。

---

## 文件结构

- 修改 `app/web/templates/index.html:1861-1880`：提供摘要、待办与按需详情的语义容器。
- 修改 `app/web/static/js/templates.js:6621-6868`：构造状态模型、渲染两种状态，复用现有编辑跳转。
- 修改 `app/web/static/style.css:17149-17218`：添加紧凑摘要和待办卡样式，取消正常态固定滚动。
- 修改 `tests/unit/test_report_template_workbench_frontend.py:1028-1098`：覆盖 DOM、状态模型、详情和待办接线。

### Task 1: 先建立失败测试

**Files:**

- Modify: `tests/unit/test_report_template_workbench_frontend.py:1028-1098`
- Test: `tests/unit/test_report_template_workbench_frontend.py`

- [ ] **Step 1: 添加 HTML 契约测试**

在现有 preflight 测试后添加：

~~~python
def test_report_config_check_uses_collapsed_summary_and_on_demand_details():
    html = INDEX_HTML.read_text(encoding="utf-8")

    assert 'id="template-project-check-summary"' in html
    assert 'id="template-project-check-status"' in html
    assert 'id="template-project-check-actions"' in html
    assert 'id="template-validation-details"' in html
    start = html.index('id="template-project-check-details"')
    assert ' open' not in html[start:html.index('>', start)]
~~~

- [ ] **Step 2: 运行测试，确认失败**

Run:

~~~bash
/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/bin/python3 -m pytest tests/unit/test_report_template_workbench_frontend.py -q
~~~

Expected: FAIL，因为摘要、待办和内层详情容器不存在。

- [ ] **Step 3: 添加状态模型契约测试**

~~~python
def test_generation_preflight_uses_ready_summary_and_blocker_actions():
    source = TEMPLATES_JS.read_text(encoding="utf-8")
    css = STYLE_CSS.read_text(encoding="utf-8")

    assert "function buildPreflightDisplayModel(" in source
    assert "state: 'ready'" in source
    assert "state: 'blocked'" in source
    assert "function renderPreflightSummary(" in source
    assert "function renderPreflightActions(" in source
    assert "actions.slice(0, 3)" in source
    assert "function buildPreflightReviewGroups(" in source
    assert ".template-project-check-actions" in css
    assert ".template-validation-details" in css
~~~

- [ ] **Step 4: 再运行测试，确认失败**

Run the command from Step 2.

Expected: FAIL，缺少展示模型和样式选择器。

- [ ] **Step 5: 提交红灯测试**

~~~bash
git add tests/unit/test_report_template_workbench_frontend.py
git commit -m "test: define compact report config check behavior"
~~~

### Task 2: 建立收起的摘要与详情 DOM

**Files:**

- Modify: `app/web/templates/index.html:1861-1880`
- Test: `tests/unit/test_report_template_workbench_frontend.py:test_report_config_check_uses_collapsed_summary_and_on_demand_details`

- [ ] **Step 1: 替换默认打开的检查结构**

移除外层 `details` 的 `open` 属性和四条“待运行”静态校验行，保留 `template-generation-readiness-panel` 供事件委托使用：

~~~html
<details class="template-workbench-panel template-project-check-panel"
         id="template-project-check-details"
         data-preflight-state="loading">
    <summary>
        <span><i class="codicon codicon-checklist"></i> 生成检查</span>
        <small id="template-project-check-summary">正在检查</small>
        <strong id="template-project-check-status" class="badge">待加载</strong>
    </summary>
    <div class="template-project-check-body" id="template-generation-readiness-panel">
        <div id="template-validation-preview" class="template-project-check-section">
            <div id="template-project-check-actions"
                 class="template-project-check-actions" aria-live="polite"></div>
            <details id="template-validation-details" class="template-validation-details">
                <summary>查看检查详情</summary>
                <div id="template-validation-list" class="template-validation-list"></div>
            </details>
        </div>
    </div>
</details>
~~~

- [ ] **Step 2: 运行结构测试**

Run:

~~~bash
/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/bin/python3 -m pytest tests/unit/test_report_template_workbench_frontend.py::test_report_config_check_uses_collapsed_summary_and_on_demand_details -q
~~~

Expected: PASS。

- [ ] **Step 3: 提交 DOM 改动**

~~~bash
git add app/web/templates/index.html
git commit -m "feat: add compact report config check container"
~~~

### Task 3: 构造状态模型并复用现有编辑操作

**Files:**

- Modify: `app/web/static/js/templates.js:6621-6868`
- Test: `tests/unit/test_report_template_workbench_frontend.py:test_generation_preflight_uses_ready_summary_and_blocker_actions`

- [ ] **Step 1: 实现 `buildPreflightDisplayModel`**

放在 `buildPreflightReviewGroups()` 前；它接收 `readiness, checks, placeholderReadiness, context`，从 `compiledPlan?.placeholders` 统计 `evidence_required`，无 compiled plan 时回退为 `placeholderReadiness.length`。实现应等价于：

~~~js
const rawActions = [
    ...readiness.assetChecks.filter(item => !item.ok),
    ...checks.filter(item => !item.ok),
    ...placeholderReadiness.filter(item => !item.ok)
];
const actions = normalizeAndPrioritizePreflightActions(rawActions).slice(0, 3);
const state = actions.length ? 'blocked' : 'ready';
const summary = state === 'ready'
    ? mappedCount + ' 个占位符已配置 · ' + evidenceCount + ' 个正文段落可检索生成'
    : actions.length + ' 项待处理 · ' + mappedCount + ' 个占位符已配置';
return {
    state, summary, actions,
    detailGroups: buildPreflightReviewGroups(readiness, checks, placeholderReadiness, context)
};
~~~

实现 `normalizeAndPrioritizePreflightActions`：按 `placeholderName + action + actionTarget` 去重；缺 Word 映射、Prompt 或 Query 为优先级 10，模板资产为 20，Excel/表格/图表来源为 30，其余为 40；再按 `priority, label` 排序。每项规范化为 `label, detail, action, actionTarget, actionLabel, placeholderName, editorSection`。缺 action 时回退到 `open-advanced` 和 `template-advanced-maintenance`。

- [ ] **Step 2: 实现摘要和待办渲染函数**

新增 `renderPreflightSummary(model)` 与 `renderPreflightActions(model)`：

~~~js
function renderPreflightSummary(model) {
    const panel = document.getElementById('template-project-check-details');
    setText('template-project-check-summary', model.summary);
    setText(
        'template-project-check-status',
        model.state === 'ready' ? '可直接生成' : String(model.actions.length) + ' 项待处理'
    );
    if (panel) {
        panel.dataset.preflightState = model.state;
        if (model.state === 'blocked') panel.open = true;
    }
}
~~~

ready 时写入“全部检查通过。展开后可查看 Prompt、检索和输出详情。”；blocked 时渲染 `actions.slice(0, 3)`，每项同时包含主问题、影响说明、以及现有 `data-template-check-action` / target / placeholder 属性。所有动态文字经过 `esc()`。

- [ ] **Step 3: 改写 `renderTemplateValidationPreview()`**

保留 `buildGenerationReadiness` 与 `renderPlaceholderIssueQueue`，替换旧计数逻辑：

~~~js
const model = buildPreflightDisplayModel(readiness, checks, placeholderReadiness, {
    sections, placeholders, excelRows: readiness.excelRows
});
renderPreflightSummary(model);
renderPreflightActions(model);
list.innerHTML = model.detailGroups.map(renderPreflightReviewGroup).join('');
~~~

ready 时不强制打开外层检查；blocked 时自动打开，内层 `template-validation-details` 只由用户展开。移除旧 `template-validation-status` 写入，避免两套状态文案。

- [ ] **Step 4: 让生成拦截聚焦待办区**

在 `blockReportGenerationForPreflight()` 将：

~~~js
openProjectCheckPanel('template-validation-preview');
~~~

改为：

~~~js
openProjectCheckPanel('template-project-check-actions');
~~~

不得改变 `handleTemplateCheckAction()`，以继续支持定位占位符、上传与高级配置。

- [ ] **Step 5: 运行完整前端接线测试**

Run:

~~~bash
/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/bin/python3 -m pytest tests/unit/test_report_template_workbench_frontend.py -q
~~~

Expected: PASS；原有 Prompt/Evidence/输出详情测试继续通过。

- [ ] **Step 6: 提交行为改动**

~~~bash
git add app/web/static/js/templates.js tests/unit/test_report_template_workbench_frontend.py
git commit -m "feat: prioritize report config preflight actions"
~~~

### Task 4: 紧凑样式与验证

**Files:**

- Modify: `app/web/static/style.css:17149-17218`
- Verify: `tests/unit/test_report_template_workbench_frontend.py`

- [ ] **Step 1: 添加状态样式**

只在最终生效的配置左栏样式块新增以下选择器，避免修改会被后续规则覆盖的旧块：

~~~css
.template-project-check-actions { display: grid; gap: 8px; }
.template-preflight-ready-summary { padding: 10px 0; color: var(--apple-secondary); }
.template-preflight-action { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 10px; }
.template-preflight-action-detail { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.template-validation-details > summary { cursor: pointer; color: var(--apple-secondary); }
#template-project-check-details[data-preflight-state="ready"] .template-project-check-body {
    max-height: none; overflow: visible;
}
~~~

blocked 的前三项不出现滚动条；ready 默认仅显示 summary。打开外层后，显示一行就绪结论与内层“查看检查详情”；仅打开内层才显示原有三组与 Evidence 抽样。颜色使用既有 `--apple-*` 变量，并添加 light theme 及 `max-width: 1200px` 下按钮换行规则。

- [ ] **Step 2: 运行目标和完整单元测试**

Run:

~~~bash
/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/bin/python3 -m pytest tests/unit/test_report_template_workbench_frontend.py -q
/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/bin/python3 -m pytest tests/unit -q
~~~

Expected: 两条命令均以 exit code 0 完成。

- [ ] **Step 3: 浏览器验收**

可生成项目：检查默认收起，显示“可直接生成”和覆盖统计；内层详情展开后才出现 Prompt、Evidence、输出资产和抽样。缺 Prompt 或 Query 的草稿：检查自动打开、最多三项待办，点击进入正确配置；点击生成被拦截并聚焦待办区。

- [ ] **Step 4: 提交样式和验证修正**

~~~bash
git add app/web/static/style.css app/web/templates/index.html app/web/static/js/templates.js tests/unit/test_report_template_workbench_frontend.py
git commit -m "style: simplify report config check states"
~~~

只在本任务确有修正时提交；不要创建空提交。

## 计划自检

- 覆盖 ready 默认、blocked 待办、按需详情、回退、可访问容器和不改后端拦截语义。
- 顺序为 TDD：失败测试、DOM、行为、样式、全量验证。
- 每个改动都给出精确文件、函数、代码片段及命令。
