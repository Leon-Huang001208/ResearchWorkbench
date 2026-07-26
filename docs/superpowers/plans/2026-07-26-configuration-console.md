# 系统配置控制台 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不扩展配置 API 的前提下，让系统配置页提供可操作的就绪总览、首次配置引导和本次会话内的连接测试状态。

**Architecture:** HTML 只提供稳定的总览、引导和卡片动作挂点；`configuration.js` 从既有脱敏快照计算界面状态，并在既有测试请求返回后维护内存级连接状态；CSS 以现有卡片变量和响应式网格实现紧凑操作台样式。后端接口保持不变。

**Tech Stack:** Jinja2 HTML、原生 ES modules、CSS、Pytest 静态回归检查、Node `--check`。

---

### Task 1: 建立前端控制台回归契约

**Files:**
- Modify: `tests/unit/test_configuration_frontend_static.py`
- Test: `tests/unit/test_configuration_frontend_static.py`

- [x] **Step 1: 写入会失败的静态断言**

在 `tests/unit/test_configuration_frontend_static.py` 新增 `test_configuration_console_keeps_health_overview_and_session_test_state`，读取 `index.html` 和 `configuration.js`，断言以下字符串存在：`data-config-health-summary`、`data-config-onboarding`、`data-config-card-action`、`connectionStateBySection`、`已验证`、`连接异常`。

- [x] **Step 2: 运行测试确认失败**

Run: `/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/bin/python3 -m pytest --noconftest tests/unit/test_configuration_frontend_static.py -v`

Expected: 新增测试失败，错误指出总览或会话状态标记尚未出现。

### Task 2: 渲染健康总览、引导和卡片主动作

**Files:**
- Modify: `app/web/templates/index.html`
- Modify: `app/web/static/js/configuration.js`
- Modify: `app/web/static/style.css`
- Test: `tests/unit/test_configuration_frontend_static.py`

- [x] **Step 1: 在页面头部插入稳定挂点**

在 `#section-config` 的 `.configuration-header` 内添加 `data-config-health-summary`，在卡片网格前添加 `data-config-onboarding`；每张卡片页脚加入 `data-config-card-action`，并保留 `data-config-card` 的键盘和点击入口。

- [x] **Step 2: 在 JavaScript 中增加纯前端状态渲染**

声明 `const connectionStateBySection = new Map()`。新增 `getConfigurationHealth(snapshot)`、`renderConfigurationHealth(snapshot)` 和 `openNextIncompleteConfiguration()`：前者以既有 `snapshot.readiness` 计算已就绪/待配置数量；总览展示本次会话内 `verified` 与 `error` 数量；引导从 `llm`、`database`、`zhiqiu`、`ifind`、`web_search` 中寻找首个未就绪分区并调用既有 `openConfigModal(section)`。在 `renderSnapshot` 与 `renderSummaryCards` 中调用渲染逻辑。

- [x] **Step 3: 在连接测试完成后写入会话状态**

在 `testSection(section)` 成功返回时记录 `verified` 或 `error`，在异常路径记录 `error`；随后重新渲染总览和卡片。刷新快照前清空该 Map，保证状态不会跨页面加载声称仍有效。

- [x] **Step 4: 为总览、引导和卡片动作添加紧凑样式**

新增 `.config-health-summary`、`.config-onboarding`、`.config-onboarding-step`、`.config-card-action`、`.verified` 与 `.error` 规则；卡片 hover 仅提高明度和边框，不改变 `transform`，并提供 `:focus-visible` 状态与窄屏单列布局。

- [x] **Step 5: 运行测试确认通过**

Run: `/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/bin/python3 -m pytest --noconftest tests/unit/test_configuration_frontend_static.py -v`

Expected: 4 个测试通过，且 Node 语法检查通过。

### Task 3: 更新前端模块文档与变更记录

**Files:**
- Modify: `docs/modules/app_web.md`
- Modify: `docs/CHANGELOG.md`

- [x] **Step 1: 记录配置控制台行为**

在 `docs/modules/app_web.md` 的配置模块说明中加入：总览与首次引导只读取脱敏快照；连接验证状态是会话内状态，刷新后清除；卡片动作仍复用既有编辑模态框。

- [x] **Step 2: 记录用户可见变更**

在 `docs/CHANGELOG.md` 的未发布条目中记录系统配置页新增健康总览、继续配置入口、卡片动作文字与会话级连接验证状态。

- [x] **Step 3: 复验受影响前端契约**

Run: `/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/bin/python3 -m pytest --noconftest tests/unit/test_configuration_frontend_static.py -v && node --check app/web/static/js/configuration.js`

Expected: 命令退出码为 0。
