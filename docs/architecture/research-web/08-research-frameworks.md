# 研究框架

## 产品边界

研究框架是 Research Web 的解释层，不是第二个资产行情终端。`#/frameworks` 提供框架入口，`#/frameworks/gold` 提供黄金专用研究画布；资产观察继续负责个股、基金、债券、外汇和商品的行情与资产详情。黄金框架中的美债、美元、基金和商品只作为定价驱动或组合背景。

黄金 V1 使用一张连续研究画布，而不是七个相互割裂的页面。总览、定价驱动、供需与资金、周期与宏观、持仓与期权、情景与配置、事件与证据是同页语义锚点；旧 `?tab=` 深链仍映射到对应锚点。桌面 Bot 是画布右侧的吸顶解释面板，移动端为全页底部面板。

## 版本化专用包

`app/research_web/frameworks/base.py` 只定义薄的跨框架协议：框架元数据、章节、来源、缺口和区块新鲜度。黄金的因果链、反证条件、字段、状态门、样例和存储全部留在 `frameworks/goldar/`：

- `definition.py`：不可变方法版本与来源修订 `758ae3848d`。
- `contracts.py`：严格、禁止额外字段的黄金专用快照。
- `seed.py`：可复现的离线初始快照及内容 revision。
- `store.py`：大小限制、路径链接拒绝、revision 校验、原子写入和旧 V0 快照保留迁移。
- `service.py` / `routes.py`：框架目录、快照读取以及绑定精确 revision 的页面会话。

后续调整黄金逻辑时新增方法版本并配套迁移和回归，不原地改变历史版本语义。Dollar 或行业框架应新建自己的定义、契约、采集转换和 renderer；只有至少两个真实框架出现相同概念后，才把重复内容提升到 `base.py` 或前端共用组件。

## API 与研究状态

- `GET /api/research/frameworks` 返回框架元数据和可用状态。
- `GET /api/research/frameworks/{slug}/data` 返回 `{framework, snapshot}`。
- `POST .../sessions` 创建只解释当前快照的 DSH 会话。
- `POST .../messages` 在原解释会话继续提问。
- `POST .../verify` 仅在用户显式触发后，新建只读深度验证会话。

所有 Bot 请求都携带并复核 `snapshot_revision`。数据更新后旧会话返回 `framework_snapshot_changed`，不得把新旧证据混在同一结论中。默认 `framework-explain` 预设没有工具，只能解释服务器提供的框架上下文；`framework-verify` 通过 `framework-research` Skill 使用当前 Runtime 实际暴露的只读检索与公共数据工具。两种模式都不能写快照、改评分或输出交易指令。

研究状态只使用“偏强 / 中性 / 偏弱 / 待核验”。关键区块缺失、过期或存在高严重度缺口时，严格契约强制降级为“待核验”。当前 seed 是离线确定性证据，不宣称是实时行情；未来采集器必须按区块独立保留最后成功值，单一来源失败不得清空整份快照。

## Lieflat 图表协议

页面只保留四张承担明确比较任务的图：F2 Hairline Line（价格背景）、F9 Rung Waterfall（驱动贡献）、F6 Paired Rungs（需求同比）、F5 Tick Rows（期权压力）。周期、配置、事件和证据使用紧凑表格、带标签文本或 disclosure，不为了装饰继续增加图表。

每张图只有一个结论、一个标题、一组来源与一条编码说明；数字使用等宽样式，颜色只表达正负、风险和缺口语义。SVG 提供 title/description，不加载外部字体、CDN、iframe 或品牌素材。移动端允许图表容器局部横向滚动，但页面本身不得横向溢出。

## 验证

`tests/research_web/test_frameworks.py` 覆盖严格契约、精确快照绑定、双 DSH 预设、旧快照迁移、符号链接拒绝和生命周期幂等。`tests/javascript/research_web_frameworks_ui.test.mjs` 覆盖连续画布、七锚点、四张图、状态与安全用语。`tests/e2e/research_web_goldar_v0.mjs` 保留兼容文件名，在浅色和深色的 1440、1280、1024、768、390 像素视口检查页面溢出、44px 锚点、键盘导航、Bot 响应式形态及 reduced-motion；制品写入 `outputs/goldar-v1/`。
