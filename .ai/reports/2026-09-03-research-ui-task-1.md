# Research Web UI Task 1

详见同任务报告：`.superpowers/sdd/2026-09-03-research-ui-capabilities/task-1-report.md`。

本次仅实现 `app/research_web/ui/` 产品壳、输入与详情面板布局，新增可测试的 `shell.mjs`、`composer.mjs` 和 `research_web_ui_layout.test.mjs`；保持既有 DSH 控制器/API，不启动服务或模型。

验证：完整 `DSH_SOURCE_ROOT=/Users/leon/Developer/deepseek-harness node --test tests/javascript/research_web*.test.mjs` 38/38 通过，四个改动模块 `node --check` 通过，`git diff --check` 通过。浏览器视觉与响应式实际验收未运行。
