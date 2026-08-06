# System Center Resource Monitor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将系统监控与系统配置收拢为一个“系统”入口，并改进资源监控的状态、异常密度和筛选器体验。

**Architecture:** 保留 `section-resource-monitor`、`section-config`、配置表单和 API；`app.js` 把唯一“系统”入口映射至两个既有区块。资源模块只替换状态和筛选控件，继续用既有事件 API 与安全 DOM 写入。

**Tech Stack:** 原生 HTML/CSS/ES Modules、FastAPI 既有接口、pytest 静态测试、Node 语法检查。

---

## 文件结构与边界

- `app/web/templates/index.html`：唯一侧栏入口、两个页内标签、筛选菜单 DOM；不修改配置字段。
- `app/web/static/js/app.js`：系统导航映射、配置初始化与监控轮询生命周期。
- `app/web/static/js/resource-monitor.js`：异常/不可用状态、状态与严重度菜单。
- `app/web/static/style.css`：标签、紧凑异常行、浮层与状态样式。
- `tests/unit/test_resource_monitor_frontend_static.py`：导航、菜单和无成功徽标契约。
- Web 文档与 `.ai/reports/2026-08-06-system-center-resource-monitor-ui.md`：术语与验证证据。

在独立 worktree `/Users/leon/Desktop/Projects/AlphaFoundry-worktrees/system-center-ui`、分支 `codex/system-center-ui` 实施，避免主工作区未提交配置改动。

### Task 1: 建立 worktree 与失败测试

**Files:**
- Create: `/Users/leon/Desktop/Projects/AlphaFoundry-worktrees/system-center-ui`
- Modify: `tests/unit/test_resource_monitor_frontend_static.py`

- [ ] **Step 1: 创建干净工作区**

```bash
git worktree add -b codex/system-center-ui \
  /Users/leon/Desktop/Projects/AlphaFoundry-worktrees/system-center-ui master
git -C /Users/leon/Desktop/Projects/AlphaFoundry-worktrees/system-center-ui status --short
```

Expected: 新 worktree 干净，主工作区的配置 WIP 不出现。

- [ ] **Step 2: 为尚不存在的 DOM/模块契约写断言**

在资源静态测试中加入：

```python
assert 'data-section="system"' in template
assert 'data-section="resource-monitor"' not in template
assert 'data-section="config"' not in template
assert 'data-system-tab="resource-monitor"' in template
assert 'data-system-tab="config"' in template
assert 'data-resource-filter-trigger="status"' in template
assert 'data-resource-filter-menu="severity"' in template
assert "function setSystemTab" in app_js
assert "function toggleResourceEventFilter" in source
assert ".resource-filter-menu" in style
assert ".resource-monitor-status[hidden]" in style
```

- [ ] **Step 3: 确认红灯**

Run: `python -m pytest tests/unit/test_resource_monitor_frontend_static.py -q`

Expected: FAIL，原因是新入口、标签和菜单尚未实现。

- [ ] **Step 4: 提交测试基线**

```bash
git add tests/unit/test_resource_monitor_frontend_static.py
git commit -m "test: define system center monitor contracts"
```

### Task 2: 实现单一入口与页内标签

**Files:**
- Modify: `app/web/templates/index.html:49,62,864,1346`
- Modify: `app/web/static/js/app.js:203-261,348-354`
- Test: `tests/unit/test_resource_monitor_frontend_static.py`

- [ ] **Step 1: 替换侧栏入口、添加两个同步的标签条**

将旧“系统监控”和“系统配置”按钮替换为：

```html
<button class="activity-btn" data-section="system" title="系统">
  <i class="codicon codicon-settings"></i><span>系统</span>
</button>
```

在资源区和配置区页首放入同一标签结构；资源区激活第一个，配置区激活第二个：

```html
<div class="system-center-tabs" role="tablist" aria-label="系统中心">
  <button type="button" role="tab" data-system-tab="resource-monitor"
          aria-controls="section-resource-monitor">资源与异常</button>
  <button type="button" role="tab" data-system-tab="config"
          aria-controls="section-config">系统配置</button>
</div>
```

资源区标题改为“系统中心”，副标题为“本机资源、异常与运行配置”。保留 `resource-monitor-status` 的 id/ARIA，初始添加 `hidden`，不得留有 `ok` 文本。

- [ ] **Step 2: 增加系统路由映射**

在 `app.js` 导航区加入：

```js
const SYSTEM_TABS = new Set(['resource-monitor', 'config']);

function systemTarget(section, requestedTab = null) {
    if (section !== 'system') return section;
    return SYSTEM_TABS.has(requestedTab) ? requestedTab : 'resource-monitor';
}

function setSystemTab(section) {
    document.querySelectorAll('[data-system-tab]').forEach(button => {
        const selected = button.dataset.systemTab === section;
        button.classList.toggle('active', selected);
        button.setAttribute('aria-selected', String(selected));
        button.tabIndex = selected ? 0 : -1;
    });
    localStorage.setItem('af-system-tab', section);
}
```

将 `navigateTo(section)` 改成 `navigateTo(section, options = {})`；用 `systemTarget(section, options.systemTab)` 得到真实 section，以它驱动区块激活、`startResourceMonitoring()`、`stopResourceMonitoring()` 与 `initConfigurationPage()`。侧栏只激活 `data-section="system"`，`af-active-section` 保存 `system`，并调用 `setSystemTab(targetSection)`。

把数据库配置事件改为：

```js
document.addEventListener('alphafoundry:open-database-configuration', () => {
    navigateTo('system', { systemTab: 'config' });
});
```

绑定标签 click：`navigateTo('system', { systemTab: button.dataset.systemTab })`。启动时将旧保存值 `resource-monitor`、`config` 迁移到 `system`，子标签只接受白名单值，默认资源标签。

- [ ] **Step 3: 验证绿灯并提交**

```bash
python -m pytest tests/unit/test_resource_monitor_frontend_static.py -q
node --check app/web/static/js/app.js
git add app/web/templates/index.html app/web/static/js/app.js tests/unit/test_resource_monitor_frontend_static.py
git commit -m "feat: unify system monitor and configuration navigation"
```

Expected: 测试通过，Node 无语法错误。

### Task 3: 实现有意义的状态、紧凑异常行与筛选浮层

**Files:**
- Modify: `app/web/templates/index.html:959-970`
- Modify: `app/web/static/js/resource-monitor.js:449-566,829-865`
- Modify: `app/web/static/style.css:13491-13517,13824-13888`
- Test: `tests/unit/test_resource_monitor_frontend_static.py`

- [ ] **Step 1: 用菜单按钮替换原生 select**

```html
<div class="resource-event-filters" aria-label="异常历史筛选">
  <div class="resource-filter">
    <button type="button" class="resource-filter-trigger" data-resource-filter-trigger="status"
            aria-haspopup="listbox" aria-expanded="false" aria-controls="resource-filter-menu-status">
      <span>状态</span><strong data-resource-filter-label="status">全部</strong>
      <i class="codicon codicon-chevron-down" aria-hidden="true"></i>
    </button>
    <div id="resource-filter-menu-status" class="resource-filter-menu"
         data-resource-filter-menu="status" role="listbox" hidden></div>
  </div>
  <div class="resource-filter">
    <button type="button" class="resource-filter-trigger" data-resource-filter-trigger="severity"
            aria-haspopup="listbox" aria-expanded="false" aria-controls="resource-filter-menu-severity">
      <span>严重度</span><strong data-resource-filter-label="severity">全部</strong>
      <i class="codicon codicon-chevron-down" aria-hidden="true"></i>
    </button>
    <div id="resource-filter-menu-severity" class="resource-filter-menu"
         data-resource-filter-menu="severity" role="listbox" hidden></div>
  </div>
</div>
```

- [ ] **Step 2: 写入菜单数据与操作函数**

在模块顶层定义：

```js
const RESOURCE_EVENT_FILTERS = {
    status: [['all', '全部'], ['open', '未确认'], ['acknowledged', '已确认'], ['resolved', '已解决']],
    severity: [['', '全部'], ['critical', '严重'], ['warning', '警告'], ['info', '信息']],
};
let resourceEventFilterState = { status: 'all', severity: '' };
let openResourceEventFilter = null;
```

实现 `toggleResourceEventFilter(kind)`、`closeResourceEventFilters()`、`renderResourceEventFilters()`：通过 `document.createElement('button')` 建立 `role="option"` 项；当前项设置 `aria-selected="true"` 并带 `codicon-check`。选择后更新 state/标签、关闭菜单、调用 `pollResourceEvents()`。在 `bindControls()` 绑定 trigger 和 document 外部点击；Escape 优先关闭菜单，再保留原进程详情关闭行为；`resourceEventFilters()` 直接返回 state。

- [ ] **Step 3: 只显示待处理或不可用状态**

```js
const pending = resourceEvents.filter(event => event.status !== 'resolved');
const unavailable = publicStatus(code) === 'unavailable';
if (!unavailable && pending.length === 0) {
    status.hidden = true;
    status.textContent = '';
    return;
}
status.hidden = false;
status.textContent = unavailable
    ? '采样暂不可用，保留上一帧数据'
    : pending.length + ' 个待处理异常';
```

在 `renderResourceEvents()` 结束时再次调用 `renderStatus(publicStatus(points.at(-1)?.status))`，让事件刷新同步提醒。普通 `ok`、`degraded` 不再产生可见文案。

- [ ] **Step 4: 实现紧凑行与完整状态样式**

根异常元素追加 `resource-event-row` 类。局部 CSS 必含：

```css
#section-resource-monitor .resource-monitor-status[hidden] { display: none; }
#section-resource-monitor .resource-filter { position: relative; }
#section-resource-monitor .resource-filter-trigger { display: inline-flex; align-items: center; gap: 7px; }
#section-resource-monitor .resource-filter-menu { position: absolute; z-index: 4; top: calc(100% + 6px); right: 0; min-width: 168px; }
#section-resource-monitor .resource-filter-option[aria-selected="true"] { color: var(--apple-accent, var(--accent)); }
```

为 trigger 的 default/hover/focus-visible/expanded、选项的 hover/selected、异常行的 default/hover/focus-visible、以及小于 900px 的单列回退定义样式；不得影响其它页面原生 `select`。

- [ ] **Step 5: 验证绿灯并提交**

```bash
python -m pytest tests/unit/test_resource_monitor_frontend_static.py -q
node --check app/web/static/js/resource-monitor.js
git add app/web/templates/index.html app/web/static/js/resource-monitor.js app/web/static/style.css tests/unit/test_resource_monitor_frontend_static.py
git commit -m "feat: refine system center monitor controls"
```

Expected: 测试通过，Node 无语法错误。

### Task 4: 文档、预览验收与整合

**Files:**
- Modify: `docs/modules/app_web.md`, `docs/REFERENCE.md`, `docs/FILE_GUIDE.md`, `docs/CHANGELOG.md`
- Create: `.ai/reports/2026-08-06-system-center-resource-monitor-ui.md`

- [ ] **Step 1: 更新文档和报告**

文档统一说明：侧栏唯一入口为“系统”、默认子标签为“资源与异常”、系统配置通过页内标签进入。报告记录无 `ok`、菜单键盘行为、测试证据和未验证 Windows 桌面端的限制。

- [ ] **Step 2: 运行完整相关验证**

```bash
python -m pytest \
  tests/unit/test_resource_monitor_service.py \
  tests/unit/test_resource_host_history_service.py \
  tests/unit/test_resource_monitor_runtime.py \
  tests/unit/test_resource_monitor_alert_service.py \
  tests/unit/app/api/routes/test_resource_monitoring.py \
  tests/unit/test_resource_monitor_frontend_static.py \
  tests/unit/test_configuration_frontend_static.py -q
node --check app/web/static/js/app.js
node --check app/web/static/js/resource-monitor.js
git diff --check
```

Expected: pytest、Node 与 diff 检查全部成功。

- [ ] **Step 3: 启动独立预览并验收**

Run: `npm run desktop:preview -- --port 8766 --use-stable-data`

验证唯一系统入口、资源默认标签、两个标签切换、正常无 `ok`、待处理数量、采样失败保留上一帧、两个筛选器的打开/选择/外部点击/Escape、紧凑异常行小屏回退。

- [ ] **Step 4: 提交文档，用户验收后合并**

```bash
git add docs/modules/app_web.md docs/REFERENCE.md docs/FILE_GUIDE.md docs/CHANGELOG.md \
  .ai/reports/2026-08-06-system-center-resource-monitor-ui.md
git commit -m "docs: record system center monitor UI"
git diff --check master...HEAD
git diff --stat master...HEAD
```

用户确认预览后执行：

```bash
git checkout master
git merge --no-ff codex/system-center-ui -m "merge: unify system center UI"
npm run desktop:restart
```

Expected: 主桌面健康检查成功。不得宣称 Windows 已验证；本计划只产生 macOS 本地证据。
