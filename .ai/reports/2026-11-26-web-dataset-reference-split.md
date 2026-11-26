# app.mjs 事件处理拆分（第二步）

宿主为 Mac mini 本机 macOS，类型为 Research Web 前端可维护性改造。

Product-Progress: not-required — 本次只把数据集引用跳转移入独立模块，行为与界面均未改变。

<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"引用跳转仍由同一 click 监听器触发，只是实现移到同目录模块；部署拓扑、依赖方向、路由与渲染时序不变。","diagrams":[]} -->

## 问题

承接 #349。`app.mjs` 的 click 监听器 919 行含 298 个 if 分支，其中只有 8 处委托给 controller。第一步提取剪贴板动作后，继续按"依赖少、边界清晰"挑选下一刀。

## 实现

- 新增 `dataset-reference.mjs`：回答正文里的数据集引用（`data-doc-ref`）跳转。
  原内联逻辑需要同时改三处壳层状态、重绘、定位 `.context-panel .dataset-card`、
  计算滚动位置并做闪示。
- 依赖通过 `createDatasetReference({ openContext, render, root, schedule })` 注入：
  三处状态写入收敛为一个 `openContext({collapsed, open, tab})` 调用，
  模块不直接引用 `app.mjs` 的 `let` 变量。
- 同时把两个魔法值提为具名常量（闪示 2400ms、卡上方留白 12px、两个媒体查询）。

## 验证

真实浏览器（Chrome / 本机 loopback）：`dataset-reference.mjs` 以 200 加载，
`#app` 正常填充，28 个导航项可见，104 个模块全部成功，**0 个 404、控制台 0 错误**。

离线：新增 `research_web_dataset_reference` 6 项通过（含序号从 1 起、
越界与非法输入不动作、窄屏展开上下文、减少动效时改为瞬时滚动、滚动位置不为负）；
既有 `research_web_ui` + `research_web_appearance` + `research_web_asset_chart` +
`research_web_clipboard_actions` 共 140 项通过。`check_ui_tokens` 预算未变。

## 未验证与后续

`app.mjs` 3917 行（两步合计减少 6 行，不等于收益——收益在每处逻辑有了独立边界和测试）。
下一步目标为连接管理簇（约 140 行），但其依赖 8 个可变状态，需要先把
`localCategory`/`officeConsentConfirmation` 等状态收敛后再抽。
