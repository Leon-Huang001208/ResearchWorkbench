# 表单处理批量抽离（资产 + 自动化）

宿主为 Mac mini 本机 macOS，类型为 Research Web 前端可维护性改造。

Product-Progress: not-required — 本次只把表单提交处理移入独立模块，行为与界面均未改变。

<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"七个表单分支仍由同一 submit 监听器触发，实现移入两个同目录模块；部署、依赖方向、路由与渲染时序不变。","diagrams":[]} -->

## 问题

`app.mjs` 的 submit 监听器 434 行、26 个分支。其中七个表单共享同一形状：
读 FormData → 构 payload → 调 API → 刷新目录 → 提示。逐个内联导致同一套
忙碌标志与错误处理反复手写。

## 实现（一次两个模块）

**`asset-forms.mjs`** —— 资产工作台的四个表单：

| 表单 | 原行数 |
| --- | --- |
| `data-asset-observation` | 24 |
| `data-watchlist-item` | 14 |
| `data-asset-note` | 10 |
| `data-asset-alert` | 16 |

后三个收敛为同一个 `postAndRefresh` 形状；观测表单保留其完整生命周期
（取消前一次、乐观占位、轮询、历史启动、三种结束文案）。
Wind 的「不超过 60 个日历日」规则提为 `windRangeError` 纯函数，
日期不可解析时**失败关闭**而不是放行。

**`automation-forms.mjs`** —— 自动化侧三个表单：

| 表单 | 原行数 |
| --- | --- |
| `data-delivery-channel-form` | 23 |
| `data-automation-form` | 35 |
| `data-report-schedule-form` | 16 |

`buildSchedule`、`buildDeliveryChannel`、`automationTarget` 均为纯函数并导出，
可脱离 DOM 校验：once/weekly/monthly 的字段差异、SMTP 与 webhook 的载荷差异、
报告工作流与能力目标的输出格式来源差异。

`app.mjs` **3868 → 3780**（-88），七个分支合计 148 行降为 28 行。

## 验证

真实浏览器：`asset-forms.mjs` 与 `automation-forms.mjs` 均以 200 加载，
109 个模块全部成功，**0 个 404、控制台 0 错误**，`#app` 正常填充，28 个导航项可见。

离线：本次相关测试范围 **224 项全部通过**（新增 25 项 + 既有 199 项）。

## 一个必须说明的基线事实

全量 `tests/javascript/research_web_*.test.mjs` 在主工作区**基线本就有 11 项失败**，
本分支为 5 项。两者都属既有问题（与本批改动无关，涉及 Python 覆盖路径、
能力中心渲染、wheel 构建等），本次不处理也不隐瞒。判断依据是：同一条命令
在主工作区（未含本批改动）跑出更多失败，且本次改动的相关测试范围 224 项全绿。

## 未验证与后续

未对真实 Wind／知丘接口提交观测或自动化任务（会触发外部调用，需单独授权）。
submit 监听器仍有约 20 个分支，click 仍有约 25 个，按同一模式可继续收敛。
