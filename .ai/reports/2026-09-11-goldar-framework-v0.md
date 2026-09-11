# Goldar 研究框架 V0 视觉检查点

## 交付范围

本检查点完成 Web-only 的 Framework Hub、Goldar 专属路由、七章节页面骨架和固定 fixture 图表。当前没有新增 Python、数据源、持久化或 API；所有数值均在页面上标记为演示数据，不代表当前市场。

## 设计校准

- 模式：扩展现有 Research Web，不重做主导航、主题或技术栈。
- 视觉：Codex-native 的安静研究工作台；高数据墨水、少阴影、有限圆角、等宽数字。
- 密度：桌面并列两个分析模块，移动端单列；主画布无横向溢出，宽图表局部滚动。
- 边界：研究框架解释驱动与证据；资产观察继续承载行情和资产详情。

## Lieflat 候选审计

| 研究结论 | 采用模板 | 核心编码保留 | 放弃候选与原因 |
| --- | --- | --- | --- |
| 紧凑价格背景 | F3 Hairline Area | 每期细竖线、单一路径、峰值注记 | 完整 K 线会重复资产终端 |
| 因子贡献 | F9 Rung Waterfall | 正负基线、离散刻度、精确值 | 普通堆叠条弱化正负方向 |
| 供需结构 | F6 Paired Rungs | 本期/同期成对比较、吨数标签 | 饼图不利于跨期比较 |
| Fed 周期 | L11 Trend Lineage | 多周期同构路径与节点 | 单线图无法比较周期谱系 |
| 期权压力 | F5 Tick Rows | 执行价行、离散压力格、精确值 | 面积图会暗示连续密度 |
| 相关性 | G20 Matrix Heat | 二维矩阵、显式相关系数 | L4/L9/F10 不能诚实表达有符号矩阵 |

图表适配只复用 Lieflat 的编码和几何思路，颜色、字体、间距、容器和交互使用现有 Research Web tokens；未复制参考项目 CSS、页面代码或品牌资产。

## 已执行验证

- `node --test tests/javascript/research_web_frameworks_ui.test.mjs`：5/5 通过。
- `node --test tests/javascript/research_web*.test.mjs`：261 通过、1 项按既有条件跳过、0 失败；隔离 worktree 使用未提交的本地 `.venv` 链接复用项目环境。
- `node tests/e2e/research_web_goldar_v0.mjs`：浅/深色共 10 个主题视口组合通过；视口为 1440×900、1280×720、1024×768、768×1024、390×844。
- 浏览器页签键盘切换 6 项通过；reduced-motion 下章节动画关闭。
- 浏览器运行时错误 0，console error 0，页面级和主画布横向溢出 0。
- `node --check`（三个新增模块）和 `git diff --check` 通过。

截图与机器可读结果位于 `outputs/goldar-v0/`。本报告只证明 V0 视觉骨架，不证明后续 API、采集器、真实数据、快照迁移或运行时行为。

## 下一阶段（等待视觉确认）

确认后实现版本化 `framework` 定义、Goldar 专用 `snapshot` 严格契约、两层 API、分区容错存储、采集调度、旧临时快照迁移、真实来源只读冒烟，以及计划中的 Python/JavaScript/浏览器/架构全量验证。
