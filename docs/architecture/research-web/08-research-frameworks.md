# 研究框架

## 当前边界

研究框架是 Research Web 的解释层，不是第二个资产行情终端。`#/frameworks` 提供框架入口，`#/frameworks/gold` 提供黄金专用研究空间；资产观察继续负责个股、基金、债券、外汇和商品的行情与资产详情。

当前提交是 V0 视觉检查点，只使用 `app/research_web/ui/frameworks/fixtures/gold-v0.mjs` 中明确标注的固定样例。它不调用真实数据、不持久化快照，也不发布当前市场结论。用户确认信息架构、密度与图表方向后，才进入版本化静态定义、严格快照契约与采集器阶段。

## 前端职责

- `ui/frameworks.mjs`：Hub、框架注册入口与未知框架回退。
- `ui/frameworks/goldar.mjs`：黄金专属页面编排和七个章节。
- `ui/frameworks/charts/lieflat.mjs`：黄金专属 Lieflat SVG 适配层。
- `ui/frameworks/fixtures/gold-v0.mjs`：确定性 V0 数据，结构预演后续 `{framework, snapshot}` 契约。
- `ui/core.mjs`：安全解析框架 slug 与 `tab` 查询参数。

七个章节为总览、定价驱动、供需与资金、周期与宏观、持仓与期权、情景与配置、事件与证据。章节导航在内容滚动区吸顶，移动端允许页签和宽图表局部横向滚动，不允许页面级横向溢出。

## 研究与呈现协议

黄金页始终从核心问题出发，依次连接宏观状态、定价驱动、供需与资金、持仓与期权、情景与配置。研究状态只使用“偏强 / 中性 / 偏弱 / 待核验”；关键输入缺失、过期或口径冲突时必须降级为“待核验”。配置章节只呈现历史相关性、回撤、分散化和情景差异，不给出个人比例或订单。

V0 图表适配自 Lieflat 模板的编码原则：价格背景使用 Hairline Area，因子贡献使用 Rung Waterfall，供需结构使用 Paired Rungs，周期比较使用 Trend Lineage，期权压力使用 Tick Rows，相关性使用带显式数值的 Matrix Heat。所有图形使用现有 Codex tokens 与语义色，不加载外部字体、CDN、iframe 或 Goldar 品牌素材。

## 验证

`tests/javascript/research_web_frameworks_ui.test.mjs` 覆盖路由、七章节渲染、代理指标说明、自托管资源和禁止交易操作用语。`tests/e2e/research_web_goldar_v0.mjs` 在浅色和深色的 1440、1280、1024、768、390 像素视口检查页面溢出、44px 页签、图表局部滚动、键盘导航及 reduced-motion。
