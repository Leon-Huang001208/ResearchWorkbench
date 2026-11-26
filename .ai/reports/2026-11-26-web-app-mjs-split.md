# app.mjs 事件处理拆分（第一步）

宿主为 Mac mini 本机 macOS，类型为 Research Web 前端可维护性改造（承接 #347/#348 的设计尺度）。

Product-Progress: not-required — 本次只把剪贴板动作从巨型事件监听器移入独立模块，行为与界面均未改变。

<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"复制动作只是从 app.mjs 的内联分支移入同目录模块，仍由同一 click 监听器调用；部署拓扑、模块依赖方向、路由与渲染时序都没有变化。","diagrams":[]} -->

## 问题

`app.mjs` 3923 行，是"加功能很累"的直接来源。按大括号深度实测，四个顶层事件监听器共占 1702 行：

| 监听器 | 行数 | if 分支 | 委托给 controller | 内联 return |
| --- | --- | --- | --- | --- |
| click | 919 | 298 | 8 | 97 |
| submit | 434 | 103 | 6 | 54 |
| keydown | 239 | 77 | 1 | 24 |
| change | 110 | 51 | 7 | 12 |

click 里 298 个分支只有 8 个委托出去，其余是内联逻辑。这就是新增一个按钮要改 919 行巨型函数的原因。

## 实现

本步只迁一个依赖最少、内聚明确的切片，用于确立可复用的拆分模式，不改其余分支：

- 新增 `clipboard-actions.mjs`：`copyAnswer` 与 `shareSession`。依赖通过
  `createClipboardActions({ getState, getCopied, setCopied, render, schedule, writeText })`
  注入，不直接引用 app.mjs 的闭包变量。
- `app.mjs` 在 `state` 定义之后实例化该 controller，click 监听器里两段内联逻辑
  改为一次调用，行为等价。
- 顺带修掉一个原有隐患：`copiedTransient` 的清除定时器现在会在触发时比对当前标记，
  旧的定时器不会误清后来设置的标记。

## 验证

真实浏览器（Chrome / 本机 loopback）：`clipboard-actions.mjs` 以 200 加载，
`#app` 正常填充，28 个导航项可见，**控制台 0 错误、0 个 404**，103 个模块全部成功。

离线：新增 `research_web_clipboard_actions` 6 项通过（含"旧定时器不得清除新标记"
与剪贴板被拒绝时的降级）；既有 `research_web_ui` + `research_web_appearance` +
`research_web_asset_chart` 134 项通过。`check_ui_tokens` 未见预算变化。

## 未验证与后续

`app.mjs` 仍 3919 行。下一步按同样模式继续切分 click 中的成组分支
（连接管理约 220 行、文档引用 53 行），每刀独立验证；submit/keydown/change
三个监听器在 click 收敛后再处理。全量重写仍不在计划内。
