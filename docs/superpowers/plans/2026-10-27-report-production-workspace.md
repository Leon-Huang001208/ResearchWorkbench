# 独立报告生产工作区实施记录

> 执行方式：主会话按已批准计划实施；独立评审只读，不并行修改维护任务。

**Goal:** 报告项目独立主导航，管理已有四个项目，每期交付复用原 Host 与唯一 DSH。

**Architecture:** UI 新目录和深链接投影原 report-workflows/report-runs API；生产状态属于所选 Run。配置及历史复用现有渲染区块，原能力中心与 Claw 入口改为业务路由。无 schema、依赖、数据库或引擎变更。

**Tech Stack:** 原生 JavaScript ES modules、现有 CSS 主题、Node test runner、原 FastAPI API。

## 已批准的设计

- 主导航 Claw 后新增报告生产；首页是真实项目目录，无创建向导。
- 项目有生产与交付、模板与配置、历史记录三栏；关联 Claw 会话不复制。
- 保留旧 Run、未知受理、版本、来源和用途。invalid/invalidated 文件不提供下载链接。
- 本期数据、内容、文件与定稿独立显示，不把依赖就绪当数据通过。
- 仅原主管理员范围展示；后台权限仍独立执行。Excel 定时继续禁用。

## 实施与验证顺序

1. 在 `tests/javascript/research_web_reports_workspace.test.mjs` 先覆盖路由、权限、筛选、旧运行选择与无效文件，再实现 `ui/report-workspace.mjs`。
2. `core.mjs` 增加 reports 路由并取消旧 reports→skills 别名；`shell.mjs` 增加受约束导航。
3. `app.mjs` 带页代次读取和事件接线，重复提交立即拒绝；自动轮询只 GET 可见且有活动 Run 的生产页，离开即清计时器。
4. 配置/历史复用 `report-workflows.mjs`；新 CSS 与原明暗主题一致、窄屏重排；原 Mac Bootstrap 验证两项静态安装字节。
5. 运行 `RWB_TEST_PYTHON=<既有任务解释器> node --test tests/javascript/*.test.mjs`、完整 changed-set Router、文档/架构/完整性门；隔离浏览器检查四项目、三标签、筛选、刷新、失效文件与未知运行。
6. 最终独评、受管提交/PR/原三 CI 和同候选 Mac 安装通过后合并；实际常驻升级与完整历史周报仍由唯一维护任务在资格闭合后执行。

## v0 与来源

用户于2026-10-27要求继续完成，确认已展示的目录和华安工作台结构。只读参考 AlphaFoundry `templates.js` 的生成优先/维护分栏及桌面源列表设计，不复制其执行引擎。v0 外部证据保存在任务验证目录，真实产品预览使用全新独立 Host、无 Native、内存凭据及只读元数据快照，禁止供应商/Office/模型及非GET操作。
