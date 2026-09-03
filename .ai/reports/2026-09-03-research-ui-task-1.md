# Research Web UI Task 1

详见同任务报告：`.superpowers/sdd/2026-09-03-research-ui-capabilities/task-1-report.md`。

本次仅实现 `app/research_web/ui/` 产品壳、输入与详情面板布局，新增可测试的 `shell.mjs`、`composer.mjs` 和 `research_web_ui_layout.test.mjs`；保持既有 DSH 控制器/API，不启动服务或模型。

验证：完整 `DSH_SOURCE_ROOT=/Users/leon/Developer/deepseek-harness node --test tests/javascript/research_web*.test.mjs` 38/38 通过，四个改动模块 `node --check` 通过，`git diff --check` 通过。浏览器视觉与响应式实际验收未运行。

Round 1 审查修复：独立深色主导航 rail 与可折叠浅色二级会话栏；窄屏二级抽屉；Claw 会话/当前工作区（仅当前 `detail` 资料与文件）切换；单独 `/` 列全部启用 Skill；运行任务从完整会话目录筛选。新增四项 RED/GREEN 回归用例；完整 JS 回归 42/42 通过、四个 UI 模块语法检查和 `git diff --check` 通过。浏览器宽度与真实模型验收仍由主控制器执行。

Round 2 审查修复：桌面折叠的二级栏在窄屏作为打开抽屉时不再带 `aria-hidden`；Claw“当前工作区”现在切换主画布，复用既有资料卡、安全固定下载、文件下载和隔离预览，“会话”切回聊天。新增两项 RED/GREEN 回归；不新增接口或存储，草稿保持由控制器管理。完整 JS 回归 44/44、四个 UI 模块语法检查及 `git diff --check` 均通过。
