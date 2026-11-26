# Office 自动验证同意：上下文收敛并抽离

宿主为 Mac mini 本机 macOS，类型为 Research Web 前端可维护性改造。

Product-Progress: not-required — 本次只把 Office 自动验证同意流程移入独立模块，行为与界面均未改变。

<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"流程仍由同一 click 监听器触发，实现移入同目录模块并复用既有 polling guard 与 consent queue；部署、依赖方向与渲染时序不变。","diagrams":[]} -->

## 问题

上一步刻意跳过了这个分支，因为 `officeAutoConsent` 一个分支就要 9 个协作者。
本次先做"上下文收敛"再做抽离：把 guard、queue、目录刷新、批次等待、成功/错误
提示、日志合并进一个工厂，点击处理只保留一次调用。

## 实现

- 新增 `office-auto-consent.mjs`，导出三个纯函数便于单测：
  `OFFICE_INTEGRATION_IDS`、`officeConsentTargets`、`officeConsentNeedsConfirm`，
  以及 `createOfficeAutoConsent({...})`。
- 复用 `connections.mjs` 里既有的 `createLocalIntegrationPollingGuard` 与
  `createOfficeConsentQueue`，没有新造轮子。
- `app.mjs` 中该分支由 58 行降为 8 行；目录只允许减少，`app.mjs` 3920 → 3886。
- **语义修正**：原参数 `enabled` 容易被读成"要启用"，实际含义是"当前已启用"，
  关闭才是需要二次确认的破坏性方向。抽离时改名为 `currentlyEnabled`，
  并把这一判断写进函数注释与测试名。

## 验证

真实浏览器：`office-auto-consent.mjs` 200 加载，106 个模块全部成功，
**0 个 404、控制台 0 错误**，`#app` 正常填充，28 个导航项可见。

离线：新增 10 项通过，覆盖目标解析（all/单个/未知）、仅在关闭时要求确认、
跨目标确认不串用、确认后逐项更新、开启时跳确认、未知 id 不触网、
拒绝时错误与日志稳定码、以及离开页面中途放弃且不报成功。
既有 153 项通过。`check_ui_tokens` 预算未变。

## 未验证与后续

未做真实 Office 插件的端到端同意流程（需本机 Excel/Word/PowerPoint 环境）。
`connectionRemove`、`integrationConsent`、`connectionProbe` 仍在监听器内，
它们共享目录刷新语义，可按同样方式继续收敛。
