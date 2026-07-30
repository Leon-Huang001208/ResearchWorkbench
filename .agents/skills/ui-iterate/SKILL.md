---
name: ui-iterate
description: Use when refining an existing app/web component's visual or interaction states without changing its public API
---

# UI Iteration

在已有组件上做一项可验证的局部 UI 改动；不把视觉调整扩展为重设计。

## 先建立边界

1. 阅读根目录 `AGENTS.md`、`docs/frontend/FRONTEND_WORKFLOW.md` 与 `docs/frontend/COMPONENT_RULES.md`。
2. 找到现有组件、调用点、selector 与状态样式的来源；先复用已有约定，不能凭猜测新增平行实现。
3. 列出并冻结外部可见的输入与 DOM 表面：属性、参数、`data-*`、事件、ARIA、selector 和外部样式契约。除非获得明确授权，不得破坏这些契约。

## 状态矩阵与最小实现

在编辑前写出本次相关状态及优先级。Button 至少逐项考虑：default、hover、disabled、loading、danger，以及它们会相互覆盖的组合。说明每项的视觉、可交互性与语义预期。

只修改实现该矩阵所必需的组件、样式和测试。不要借机替换组件库、重命名公开接口、重排无关样式或重构相邻组件。

## 验证与交付

- 运行与改动相符的已有测试；若有目标浏览器和可用环境，实际检查相关状态，而不是只描述应当如何检查。
- 在交付中逐项列出状态：`已验证（证据）` 或 `未验证（原因）`。浏览器不可用、组合状态未覆盖或无视觉基线，都必须明确写为未验证。
- 同时报告：修改文件、保留的外部可见契约、实际运行命令和结果、最小 diff 的边界与遗留风险。

## 防错检查

“样式很小所以无需浏览器证据”、“加载态默认没问题”或“顺手统一其他按钮”都是扩大范围或遗漏验证的信号。回到状态矩阵，只交付已证明的项目。
