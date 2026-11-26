# app.mjs 事件处理拆分（第三步）

宿主为 Mac mini 本机 macOS，类型为 Research Web 前端可维护性改造。

Product-Progress: not-required — 本次只把本地集成筛选与同意取消移入独立模块，行为与界面均未改变。

<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"两个分支仍由同一 click 监听器触发，实现移到同目录模块；部署、依赖方向、路由与渲染时序不变。","diagrams":[]} -->

## 背景与取舍

连接管理簇原计划一次抽出，但实测 `officeAutoConsent` 依赖 9 个对象
（目录、API、轮询 guard、队列、状态、重绘、成功提示、日志、等待器），
把 9 个参数塞进工厂函数只会把复杂度换个地方藏。

因此本步只抽其中两个**纯 UI 簿记**分支，它们依赖少且边界干净：

| 分支 | 原行数 | 实际职责 |
| --- | --- | --- |
| `localCategoryTarget` | 5 | 改分类、重绘、把焦点还给按下的 chip |
| `officeAutoCancel` | 5 | 清空待确认目标、重绘、把焦点还给触发行 |

## 实现

- 新增 `local-integration-filter.mjs`：`selectCategory` 与 `cancelConsent`。
  依赖通过 `createLocalIntegrationFilter({ setCategory, getConsentTarget, setConsentTarget, render, root })` 注入。
- 分类前缀 `local-category-` 提为具名常量。
- `CSS.escape` 增加降级：DOM 有就用，没有则转义引号与反斜杠，
  避免在无 DOM 环境下直接抛 `ReferenceError`。

## 验证

真实浏览器：`local-integration-filter.mjs` 200 加载，105 个模块全部成功，
**0 个 404、控制台 0 错误**，浏览器内 `CSS.escape` 可用。

离线：新增 7 项通过（含前缀剥离、焦点使用原始值、缺失焦点目标不抛错、
无待确认时取消仍安全）；既有 146 项通过。`check_ui_tokens` 预算未变。

## 未验证与后续

`app.mjs` 3920 行。`officeAutoConsent`、`connectionRemove`、`integrationConsent`
等分支仍内联；它们共享轮询 guard 与目录刷新语义，需要先把这些收敛为
一个连接管理上下文对象后再整体抽出，否则只是把参数列表搬家。
