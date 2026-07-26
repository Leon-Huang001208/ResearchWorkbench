# System Configuration UI Refinement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不改变配置保存和测试语义的前提下，精修系统配置首页及六个编辑弹窗的布局、状态表达和操作层级。

**Architecture:** 首页继续由 `configurationSnapshot`、数据库 readiness 与会话内 `connectionStateBySection` 驱动，但将两块横幅收敛为一个进度概览并提供纯前端状态筛选。模态框继续由 `renderModalForm` 生成字段和由既有保存/测试流程处理数据；HTML 只补充语义挂点，CSS 负责一致的紧凑版式与响应式降级。

**Tech Stack:** HTML 模板、原生 ES modules、CSS、pytest 静态契约测试、Node.js 语法检查。

---

### Task 1: 定义首页与弹窗的可回归 UI 契约

**Files:**
- Modify: `tests/unit/test_configuration_frontend_static.py`
- Modify: `docs/modules/app_web.md`

- [ ] **Step 1: 写入失败的首页与弹窗静态契约测试**

在 `test_configuration_frontend_static.py` 新增两个测试；测试只检查公开 DOM 挂点和源代码语义，不能导出或断言秘密值：

```python
def test_configuration_refinement_uses_compact_progress_and_explicit_refresh_semantics():
    template = CONFIGURATION_TEMPLATE.read_text(encoding="utf-8")
    source = CONFIGURATION_JS.read_text(encoding="utf-8")

    assert 'data-config-progress-completed' in template
    assert 'data-config-progress-missing' in template
    assert 'data-config-connection-summary' in template
    assert 'data-config-status-filter' in template
    assert 'data-config-onboarding' not in template
    assert '刷新状态' in template
    assert '不测试连接' in template
    assert 'renderConfigurationCardVisibility' in source
    assert 'connectionStateBySection.clear()' in source


def test_configuration_refinement_keeps_modal_actions_and_empty_collection_hooks():
    template = CONFIGURATION_TEMPLATE.read_text(encoding="utf-8")
    source = CONFIGURATION_JS.read_text(encoding="utf-8")

    assert 'data-config-test-help' in template
    assert '保存更改' in template
    assert 'config-empty-collection' in source
    assert 'config-field-grid config-field-grid--compact' in source
    assert 'aria-describedby' in source
```

在 `docs/modules/app_web.md` 追加一条模块说明：首页的“刷新状态”不测试连接、不保存配置；连接测试在弹窗内执行，锁定字段和秘密值安全约束不变。

- [ ] **Step 2: 运行测试，确认它在实现前失败**

Run: `pytest --noconftest tests/unit/test_configuration_frontend_static.py -q`

Expected: FAIL，缺少新的首页挂点、刷新说明和集合空状态类名；既有安全测试仍可通过。

- [ ] **Step 3: 保持测试为展示层契约**

不要为测试新增接口、模拟秘密值或改变后端服务。所有新断言必须只读取 `index.html`、`configuration.js`、`configuration.css` 和模块文档。

- [ ] **Step 4: 提交测试与文档契约**

```bash
git add tests/unit/test_configuration_frontend_static.py docs/modules/app_web.md
git commit -m "test(config): specify refined configuration UI"
```

### Task 2: 收敛首页为紧凑进度概览与模块网格

**Files:**
- Modify: `app/web/templates/index.html:1231-1364`
- Modify: `app/web/static/js/configuration.js:743-825, 1248-1280, 1312-1408`
- Modify: `app/web/static/configuration.css`

- [ ] **Step 1: 替换首页横幅 DOM，保留所有卡片 data 属性**

删除 `data-config-onboarding` 区块，以一个 `data-config-health-summary` 区块承载三项内容：完成进度、待处理数量、连接状态。保留 `data-config-card`、`data-card-badge`、`data-card-summary` 和 `data-config-card-action`，因为现有键盘和点击绑定依赖它们。

首页概览使用如下结构；计数和文案由 JavaScript 填充：

```html
<section class="config-health-summary" data-config-health-summary aria-label="配置概览" aria-live="polite">
  <div class="config-progress-overview">
    <span>配置进度</span>
    <strong><span data-config-progress-completed>--</span> / 6 项已完成</strong>
    <div class="config-progress-track" aria-hidden="true"><span data-config-progress-bar></span></div>
  </div>
  <div class="config-summary-stat config-summary-stat--attention">
    <span>需要处理</span><strong data-config-progress-missing>--</strong><em>项待配置</em>
  </div>
  <button class="config-connection-summary" data-config-connection-summary type="button">
    <span>连接状态</span><strong data-config-connection-label>正在读取…</strong><small data-config-health-detail></small>
  </button>
</section>
<div class="config-modules-header">
  <div><h3>配置模块</h3><p>选择一个模块查看或修改配置</p></div>
  <label class="config-status-filter">状态筛选
    <select data-config-status-filter><option value="all">全部模块</option><option value="attention">需要处理</option><option value="ready">已就绪</option></select>
  </label>
</div>
```

将 `#config-refresh` 文案改为 `刷新状态`，添加 `title="重新读取配置状态，不测试连接或保存配置"` 和可见的 `config-refresh-help` 辅助文字。删除首次配置按钮及其 DOM 查询。

- [ ] **Step 2: 在 `renderConfigurationHealth` 中渲染新概览**

以已有 `getConfigurationHealth(snapshot)` 为唯一计数来源。将完成数、待办数、连接标签和进度条写入新节点；不要将会话验证结果持久化。

```js
const total = Object.keys(snapshot?.readiness || {}).length || ONBOARDING_SECTIONS.length;
const completed = health.readyCount;
const missing = health.missingCount;
summary.querySelector('[data-config-progress-completed]').textContent = completed;
summary.querySelector('[data-config-progress-missing]').textContent = missing;
summary.querySelector('[data-config-progress-bar]').style.width = `${Math.round((completed / total) * 100)}%`;
summary.querySelector('[data-config-connection-label]').textContent = health.errorCount
    ? `${health.errorCount} 项连接异常`
    : health.verifiedCount ? `${health.verifiedCount} 项本次已验证` : '暂无异常';
```

删除 `renderConfigurationHealth` 对 `data-config-onboarding` 的读取，删除 `openNextIncompleteConfiguration` 和 onboarding click listener。连接状态按钮仅负责让用户看到已有 detail 文案，不发起新连接请求。

- [ ] **Step 3: 实现纯前端状态筛选，不改接口与卡片操作**

在 `renderSummaryCards` 完成徽章 class 更新后调用以下函数；`attention` 显示 `missing` 或 `error`，`ready` 显示 `ready`、`verified` 或数据库的 `ready`，其余隐藏。筛选不修改 snapshot、保存 payload 或卡片的 `role`/`tabindex`。

```js
function renderConfigurationCardVisibility(filter = document.querySelector('[data-config-status-filter]')?.value || 'all') {
    document.querySelectorAll('[data-config-card]').forEach(card => {
        const state = card.querySelector('[data-card-badge]')?.classList;
        const attention = state?.contains('missing') || state?.contains('error');
        const ready = state?.contains('ready') || state?.contains('verified');
        card.hidden = filter === 'attention' ? !attention : filter === 'ready' ? !ready : false;
    });
}
```

在 `bindConfigurationEvents` 给 `[data-config-status-filter]` 绑定 `change` 事件。刷新后清空 `connectionStateBySection` 后重新加载配置，确保 `刷新状态` 的名称与实际行为一致。

- [ ] **Step 4: 为首页添加精炼深色样式与断点**

在 `configuration.css` 末尾加入覆盖样式而不是修改无关工作台 CSS：

```css
.configuration-page { max-width: 1280px; margin-inline: auto; }
.config-health-summary { grid-template-columns: minmax(220px, 1.25fr) repeat(2, minmax(150px, .7fr)); }
.config-cards-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
.config-summary-card { min-height: 178px; border-radius: 10px; }
.config-card-surface { align-items: flex-start; flex-direction: row; padding: 16px; gap: 12px; }
.config-card-icon { width: 32px; height: 32px; border-radius: 8px; box-shadow: none; font-size: 16px; }
@media (max-width: 980px) { .config-cards-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 640px) { .config-health-summary, .config-cards-grid { grid-template-columns: 1fr; } }
```

移除或覆盖卡片的发光伪元素与 80px 图标表现；保留清晰的 `:hover`、`:focus-visible` 和状态文字。

- [ ] **Step 5: 运行首页静态测试与 JavaScript 语法检查**

Run: `pytest --noconftest tests/unit/test_configuration_frontend_static.py -q && node --check app/web/static/js/configuration.js`

Expected: PASS，且 Node 无语法输出。

- [ ] **Step 6: 提交首页精修**

```bash
git add app/web/templates/index.html app/web/static/js/configuration.js app/web/static/configuration.css tests/unit/test_configuration_frontend_static.py
git commit -m "feat(config): refine configuration overview"
```

### Task 3: 统一六个配置弹窗的表单布局、空状态和操作层级

**Files:**
- Modify: `app/web/templates/index.html:1366-1389`
- Modify: `app/web/static/js/configuration.js:1411-1553, 1628-1723`
- Modify: `app/web/static/configuration.css`
- Modify: `tests/unit/test_configuration_frontend_static.py`

- [ ] **Step 1: 在模态框模板中加入测试行为说明挂点**

把页脚的 status、锁定提示与操作按钮保留原有 ID；在测试按钮前增加仅在 `testable` 分区显示的说明节点：

```html
<span id="config-edit-modal-status" class="config-modal-status" aria-live="polite"></span>
<span id="config-edit-modal-lock-note" class="config-modal-lock-note" hidden>…</span>
<span id="config-edit-modal-test-help" data-config-test-help class="config-modal-test-help">
  测试连接不会保存当前更改
</span>
<button id="btn-config-edit-modal-cancel" class="btn-secondary config-modal-cancel" type="button">取消</button>
<button id="btn-config-edit-modal-test" class="btn-secondary" type="button">…测试连接</button>
<button id="btn-config-edit-modal-save" class="btn-primary" type="button">…保存更改</button>
```

- [ ] **Step 2: 在 `renderModalForm` 为空账号/Key 池渲染解释性空状态**

为 `values.accounts` 为空的知丘、iFinD、联网搜索分支在新增按钮后追加 `config-empty-collection`，不要渲染只含列标题的空列表：

```js
function createEmptyCollectionState(copy) {
    return `<div class="config-empty-collection" role="status">
        <i class="codicon codicon-info" aria-hidden="true"></i><span>${copy}</span>
    </div>`;
}
```

只将此 HTML 用于固定的内部说明字符串；账号名称、Key、密码或 API 返回数据必须继续通过 DOM API 创建，不能插入到 `innerHTML`。

为联网搜索、知丘调度、iFinD 连接等短字段网格添加 `config-field-grid--compact`；由 CSS 在宽屏分别为两列或三列，窄屏折叠为一列。数据库 URL、密钥输入和高级配置保持单列或现有安全布局。

- [ ] **Step 3: 在 `openConfigModal` 维持测试/锁定的行为边界**

根据 `SECTION_META[section].testable` 设置测试按钮和 `data-config-test-help` 的 `hidden`，不改变 `modalTestSection`、`modalSaveSection`、`collectSection` 或环境锁 payload 过滤：

```js
const testable = Boolean(meta.testable);
testBtn.hidden = !testable;
document.querySelector('[data-config-test-help]').hidden = !testable;
```

测试按钮仍使用当前填写的表单 payload 调用既有测试接口，保存按钮仍使用既有保存路径；环境锁 footer `setModalLockNote` 必须继续与 `aria-describedby` 一起工作。

- [ ] **Step 4: 用覆盖样式收紧模态框，而不修改全局 modal**

在 `configuration.css` 添加配置页面专属规则：

```css
.config-edit-modal-content { width: min(820px, calc(100vw - 48px)); max-height: min(760px, calc(100vh - 48px)); border-radius: 12px; }
.config-edit-modal-content .modal-header { padding: 16px 20px 14px; }
.config-modal-header-icon { width: 38px; height: 38px; border-radius: 9px; box-shadow: none; }
.config-edit-modal-body { padding: 18px 20px; }
.config-edit-modal-body .config-panel { padding: 0; border: 0; background: transparent; box-shadow: none; }
.config-field-grid--compact { grid-template-columns: repeat(3, minmax(0, 1fr)); }
.config-empty-collection { margin-top: 12px; padding: 14px; border: 1px dashed var(--border-primary); border-radius: 8px; color: var(--text-secondary); }
.config-edit-modal-content .modal-footer { padding: 12px 20px; }
@media (max-width: 720px) { .config-field-grid--compact { grid-template-columns: 1fr; } }
```

使用现有 `data-modal-color` 变量作为 4px 顶部色线和局部按钮/焦点色；去掉粗左色条、大面积渐变和圆形按钮，不能覆盖 `:focus-visible`。

- [ ] **Step 5: 扩展静态测试并通过它**

在 Task 1 的 modal 测试中补充：测试说明会随 `meta.testable` 隐藏；空状态使用固定说明并且不包含 `key_value`、`password_value`、`api_key?.value` 等秘密回填路径。运行：

```bash
pytest --noconftest tests/unit/test_configuration_frontend_static.py -q
node --check app/web/static/js/configuration.js
git diff --check
```

Expected: PASS，无空格错误。

- [ ] **Step 6: 提交弹窗精修**

```bash
git add app/web/templates/index.html app/web/static/js/configuration.js app/web/static/configuration.css tests/unit/test_configuration_frontend_static.py
git commit -m "feat(config): refine configuration modals"
```

### Task 4: 进行浏览器与回归验证并更新交付文档

**Files:**
- Modify: `docs/modules/app_web.md`
- Test: `tests/unit/test_configuration_frontend_static.py`

- [ ] **Step 1: 运行完整目标回归集**

Run:

```bash
pytest tests/unit/test_configuration_service.py tests/unit/test_configuration_frontend_static.py -q
node --check app/web/static/js/configuration.js
git diff --check
```

Expected: 全部通过。若服务端测试因本机依赖缺失而无法收集，记录具体模块名；不安装 Python 包，除非先获得用户同意。

- [ ] **Step 2: 在可用浏览器/桌面开发环境执行视觉冒烟测试**

依次检查：

1. 首页在宽屏是三列、约 980px 时两列、窄屏单列；筛选只隐藏卡片，不破坏点击与键盘 Enter/Space 打开。
2. `刷新状态` 显示“不测试连接或保存配置”的帮助，刷新后本次连接测试标签清除。
3. 打开联网搜索空 Key 池，确认新增入口、空状态、2 列选择字段、3 列短数字字段和固定 footer。
4. 打开至少一个已有配置分区，确认秘密值不回填、锁定说明仍关联禁用字段、测试不会保存、保存仍刷新卡片。
5. 在 200% 缩放或窄屏下，footer 按钮和关闭按钮可访问且无横向溢出。

- [ ] **Step 3: 更新文档为真实验证状态**

在 `docs/modules/app_web.md` 记录最终用户可见布局：紧凑进度概览、`刷新状态`语义、卡片断点、弹窗空状态和测试不保存说明。只记录实际完成的浏览器验证；不能声明 Windows 桌面端已验证，除非原生 Windows CI 与安装级冒烟测试实际完成。

- [ ] **Step 4: 提交验证与文档**

```bash
git add docs/modules/app_web.md tests/unit/test_configuration_frontend_static.py
git commit -m "docs(config): verify refined configuration UI"
```

## Plan self-review

- **Spec coverage:** Task 2 覆盖紧凑概览、刷新语义、三列/两列/单列卡片和筛选；Task 3 覆盖六个弹窗的标题、字段网格、空状态、固定 footer、锁定与测试语义；Task 4 覆盖安全、可访问性、响应式和真实验证记录。
- **Safety boundaries:** 计划不改 `ConfigurationService`、保存 API、秘密值回填限制、锁定 payload 过滤或测试接口；所有新 `innerHTML` 仅接受固定内部说明字符串。
- **Consistency:** 数据属性、函数名和 CSS class 在测试、DOM、渲染和样式任务中一致：`data-config-progress-*`、`data-config-status-filter`、`renderConfigurationCardVisibility`、`config-field-grid--compact`、`config-empty-collection`。
