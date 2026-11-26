# 列表键盘导航去重

宿主为 Mac mini 本机 macOS，类型为 Research Web 前端可维护性改造。

Product-Progress: not-required — 本次只把重复的键盘导航算法合并为一个模块，行为与界面均未改变。

<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"三个模块的 Tab 键导航改为调用同一纯函数；部署、依赖方向、路由与渲染时序不变。","diagrams":[]} -->
<!-- architecture-review {"group":"capabilities","structure":"unchanged","reason":"能力类型与 MCP 子视图的键位导航改为共用 list-keynav 纯函数，各自原有的边缘语义与调用方均未变化。","diagrams":[]} -->
<!-- architecture-review {"group":"automations","structure":"unchanged","reason":"能力目录的键位导航实现改为调用共享纯函数，自动化目录数据、调度与执行链均未变化。","diagrams":[]} -->

## 扫描结果

按「剥掉标识符与字面量后的结构骨架」扫描 111 个 `.mjs`：

- 完全逐字重复的 5 行窗口：**0 组**
- 结构重复的行（≥3 次、跨文件）：**2 种**，实为同一个算法的两种写法

定位到 **6 处**同一规则——「Home/End 跳到两端，方向键步进并回卷」：

| 位置 | 用途 |
| --- | --- |
| `app.mjs` ×3 | 场景选择、组合输入、连接分组 tablist |
| `asset-search.mjs` | 搜索下拉 |
| `capabilities.mjs` | 能力类型 tab |
| `capability-workspace.mjs` | 能力工作台类型 tab |
| `mcp-marketplace.mjs` | MCP 子视图 tab |

## 一个真实的不一致

其中两处用 `Math.max(0, indexOf(...))` 把未知值钉在 0，另一些没有。
在 `ArrowLeft` 且当前值未知时，这个差异决定跳到**首个**还是**末尾**。
合并时保留了各自的原语义（`capabilities` 与 `capability-workspace` 保留 `Math.max`），
并用测试把这一行为固定下来——**合并的是实现，不是行为**。

## 实现

- 新增 `list-keynav.mjs`：`LIST_NAV_KEYS`、`nextListIndex`、`listNavTarget`。
- `nextListIndex` 是纯函数，支持水平/垂直轴、以及「无选中项时从哪一端进入」。
- 统一了 3 个导出函数（`capabilityTabKey`、`capabilityWorkspaceKindKey`、
  `mcpMarketplaceTabKey`）；`app.mjs` 与 `asset-search.mjs` 的内联写法本次未动。

## 验证

真实浏览器：`list-keynav.mjs` 以 200 加载，110 个模块全部成功，
**0 个 404、控制台 0 错误**，`#app` 正常填充，28 个导航项可见。

离线：新增 9 项通过（Home/End、双向回卷、垂直轴、无选中项时从两端进入、
空列表、非导航键、以及未知 kind 的原始边缘行为）；相关测试范围 **233 项全部通过**。

## 未验证与后续

`app.mjs` 与 `asset-search.mjs` 里的 4 处仍是内联写法。它们语义略有差异
（`app.mjs` 的第二处带 `current < 0` 的显式分支），需要逐处比对后再迁移，
不在本次范围内。
