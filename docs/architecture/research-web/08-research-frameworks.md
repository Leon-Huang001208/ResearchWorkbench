# 研究框架

## 产品边界

研究框架是 Research Web 的解释层，不是第二个资产行情终端。`#/frameworks` 固定列出黄金与美元流动性，`#/frameworks/gold` 和 `#/frameworks/dollar` 分别提供专用研究画布；资产观察继续负责个股、基金、债券、外汇和商品的行情与资产详情。框架引用的美债、美元、基金和商品只作为因果驱动、传导或组合背景。

两个框架都使用一张连续研究画布，而不是七个相互割裂的页面。Gold 的七个语义锚点保持不变；Dollar 按“总览 → Q 总量水库 → P 资金价格 → g 财政水流 → M 融资管道 → X 跨境美元 → 传导与证据”排列。`?tab=` 深链映射到同页锚点。桌面 Bot 是画布右侧的吸顶解释面板，移动端为全页底部面板。

## 版本化专用包

`app/research_web/frameworks/base.py` 只定义薄的跨框架协议：框架元数据、章节、来源、缺口和区块新鲜度。`registry.py` 固定注册框架，`storage.py` 负责严格有界的原子快照，`scheduler.py` 只创建一个幂等的 `AsyncIOScheduler`。Gold 与 Dollar 分别拥有 definition、contract、collector、score/context 和前端 renderer，不把 Q-P-g-M-X 或黄金字段提升成通用 schema。

黄金的因果链、反证条件、字段、状态门、样例和采集全部留在 `frameworks/goldar/`：

- `definition.py`：不可变方法版本与来源修订 `758ae3848dc32adf2b361fdd070f98cbc75ce496`。
- `contracts.py`：严格、禁止额外字段的黄金专用快照。
- `seed.py`：可复现的离线初始快照及内容 revision。
- `store.py`：使用共享存储协议并把 Gold v1 原件备份为 `snapshot.legacy-v1.json` 后迁移到 v2。
- `collector.py`：WGC/SPDR 黄金价格与持仓、FRED 宏观、Goldhub 供需/ETF、Cboe GLD 期权和 CFTC 年度 ZIP。

`frameworks/dollar/` 使用方法修订 `2c210b45577905c0e8ec5f9c061e7069a6cb3b96` 和 DollarSnapshot v1。核心读取 FRED、纽约联储、FiscalData 与 TreasuryDirect Upcoming Auctions；日度财政失败时保留 WDTGAL 周频代理并标明代理属性。“WALCL − TGA − ON RRP”只称净流动性代理，不描述成会计恒等式。五维平均值大于 `0.15` 为偏松、小于 `-0.15` 为偏紧；任一维度不可计算或存在高严重度缺口时强制待核验，同时保留已知小计和可能区间。

后续调整框架逻辑时，先改框架自己的 definition/contract/collector/context/renderer，新增方法版本并配套迁移和回归，不原地改变历史版本语义。只有至少两个真实框架出现同一生命周期或展示概念后，才把重复内容提升到公共协议或 `ui/frameworks/common.mjs`。

## API 与研究状态

- `GET /api/research/frameworks` 返回框架元数据和可用状态。
- `GET /api/research/frameworks/{slug}/data` 返回 `{framework, snapshot}`。
- `POST .../sessions` 创建只解释当前快照的 DSH 会话。
- `POST .../messages` 在原解释会话继续提问。
- `POST .../verify` 仅在用户显式触发后，新建只读深度验证会话。

所有 Bot 请求都携带并复核 `snapshot_revision`。数据更新后旧会话返回 `framework_snapshot_changed`，不得把新旧证据混在同一结论中。默认 `framework-explain` 预设没有工具，只能解释服务器提供的框架上下文；`framework-verify` 通过 `framework-research` Skill 使用当前 Runtime 实际暴露的只读检索与公共数据工具。两种模式都不能写快照、改评分或输出交易指令。

Gold 研究状态只使用“偏强 / 中性 / 偏弱 / 待核验”，Dollar 使用“偏松 / 中性 / 偏紧 / 待核验”。关键区块缺失、过期或存在高严重度缺口时，严格契约强制降级。seed 只用于离线测试和首次尚无真实快照的服务端状态；生产浏览器在 API 失败时不加载 fixture。采集器按区块保留最后成功值，并记录 `checked_at` 与 `failure_code`；GET 请求只读本地快照，不触发外网。

## Lieflat 图表协议

Gold 使用 F2（价格背景）、F9（四维贡献）、F6（需求同比）、F5（期权压力）和 L4（相关性矩阵）。Dollar 使用 F9（五维贡献）、F3（净流动性代理）、F12（政策路径变化）、F6（TGA/发行）、F2（SOFR−IORB）和 F8（跨境关系）；单页模板不重复且不超过六张。周期、事件和证据继续使用紧凑表格或 disclosure。

每张图只有一个结论、一个标题、一组来源与一条编码说明；数字使用等宽样式，颜色只表达正负、风险和缺口语义。SVG 提供 title/description，不加载外部字体、CDN、iframe 或品牌素材。移动端允许图表容器局部横向滚动，但页面本身不得横向溢出。

## 验证

`tests/research_web/test_frameworks.py` 覆盖两框架目录、严格契约、精确快照绑定、跨框架拒绝、迁移和生命周期；`test_framework_collectors.py` 覆盖转换、门限、CFTC 幂等与最后成功值。`test_workbench_operations.py` 覆盖全局 Artifacts 忽略软删除会话、显式查询仍返回 410、恢复后重新出现。JavaScript 测试覆盖两个连续画布、图表、无浏览器 fixture、状态与安全用语。浏览器验收覆盖浅/深色、1440/1024/768/390、键盘锚点、Bot、横向溢出和 reduced-motion。
