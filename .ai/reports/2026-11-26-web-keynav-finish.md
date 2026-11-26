# 列表键盘导航收尾

宿主为 Mac mini 本机 macOS，类型为 Research Web 前端可维护性改造。

Product-Progress: not-required — 本次只把剩余两处内联键盘逻辑改为调用共享工具，行为与界面均未改变。

<!-- architecture-review {"group":"workbench","structure":"unchanged","reason":"资产搜索下拉的键位导航改为调用共享纯函数，工作台的查询、数据与接口均未变化。","diagrams":[]} -->
<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"资产搜索下拉与发现抽屉的键位/焦点逻辑改为调用既有纯函数与工具，部署、依赖方向与渲染时序不变。","diagrams":[]} -->

## 实现

承接 #355。本次收尾两处：

- `asset-search.mjs`：搜索下拉的垂直键盘导航改为 `nextListIndex({axis:'vertical'})`。
  原实现与共享函数逐项等价（原式在 `items.length` 为 0 时提前返回，故不存在 -1 入口问题）。
- `app.mjs` 发现抽屉：手写的 Tab 焦点陷阱改为 `trapTabFocus`（4 行 → 2 行），
  与能力预览、MCP 对话框使用同一实现。

## 刻意未迁移

`app.mjs` 的 project 编辑器对话框用更窄的选择器（仅 `input`／`button`），
与共享工具的 `FOCUSABLE_SELECTOR` 不同；强行统一会改变可聚焦集合，属于行为变更，
不在本次范围。该处保持原样。

## 验证

真实浏览器：110 个模块全部成功，`asset-search.mjs` 正常加载，
**0 个 404、控制台 0 错误**，`#app` 正常填充，28 个导航项可见。

离线：`research_web_list_keynav`、`research_web_focus_trap`、`research_web_ui`
共 61 项通过；资产相关测试 274 项通过。

## 未验证

未在真实浏览器里逐键验证搜索下拉与发现抽屉的完整按键序列。
