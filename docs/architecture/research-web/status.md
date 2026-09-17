# Research Web 架构状态

本页只保留当前边界和未闭合项；逐任务实现与验证记录位于 `.ai/reports/`，此前累计评审已归档到 [`docs/archive/reviews/`](../../archive/reviews/)。

## 当前

- 当前产品入口：`app.research_web.main:app`。
- 唯一研究引擎：项目专属 DSH Runtime。
- 当前产品阶段：Web-only。
- DataHub 目录：15 项能力、22 个登记来源；真实可调用取决于配置、授权、探测、适配和当前健康。
- 研究框架：Gold 与 Dollar 使用独立快照、方法版本、采集和 renderer，共享受限生命周期协议。
- 文档拓扑：本目录是唯一详细架构入口；`architecture-map.json` 是源码、文档、测试、接口和图证据的机器真源。

## 待验证或环境相关

- 专业数据源和本机集成只在对应环境完成真实授权、探测和调用后才能标记可用。
- Web-only 的原生 Windows CI 不等于真实 Windows 浏览器或桌面安装级验收。
- 历史报告 Workflow、外部数据和模型结果的旧验收不能自动证明当前版本仍通过；需要按任务重新验证。

## 变更记录

每次影响 Research Web 源码或文档门禁的任务，在本次变更的 `.ai/reports/*.md` 中加入 `architecture-review` 标记。架构检查只读取本次 changed set 内的任务报告，不再要求向一个永久增长的 review record 追加内容。
