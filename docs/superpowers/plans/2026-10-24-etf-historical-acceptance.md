# Huaan ETF Historical Acceptance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development to implement this plan task by task.

**Goal:** 用原Report Workflow完成明确标注、永不正式定稿的历史周报全流程验收。

**Architecture:** 在Host持久Run和冻结要求中记录可信用途，沿现有DataHub → Wind Excel → DSH → Host投影/质量/文件链传递；普通正式路径不变。历史注记先于文件哈希并由绑定阶段重验，不增加引擎或依赖。

**Tech Stack:** 现有Python/FastAPI/DSH、原Word模板与openpyxl、原前端模块、现存pytest及静态检查工具。

---

## 1. 运行身份与数据门（同一实现者负责依赖闭包）

- [ ] 阅读AGENTS、架构、开发图和周报模块；复现首次Run的原始历史阻断与次级错误。
- [ ] 在report_workflow_routes/runtime及相关测试先添加专用历史验收创建、owner、去重、恢复/重试用途保持反例，确认红灯。
- [ ] Host创建并冻结用途；原普通API默认正式，不接受模型/快照覆盖。字段命名跟随现有实现风格。
- [ ] 在Provider、DataHub、weekly_data/quality及底稿重放所有调用点传可信验收模式；真实时间和historical_recheck保留。
- [ ] 正式门保持原拒绝结果；先呈现历史采集主因，不能让空经济日历错误掩盖它。
- [ ] 执行数据与运行合同测试，修复到通过；不实际调用厂商或模型。

## 2. Host派生文件与不可正式定稿

- [ ] 只读探索精确canonical → stage projection → trusted renderer → bind → quality → finalize调用点。
- [ ] 先写Word/HTML标签移除与用途篡改反例、普通渲染无标签回归及正式稿/日程不升级反例。
- [ ] 通过可信渲染入口确定性插入历史标签/期间/真实采集说明，先于最终文件哈希；绑定阶段读回核对。
- [ ] 历史用途作为独立非正式终态，不更新上一正式稿，不满足manual finalized门；保留一次有界修订。
- [ ] 原模板/章节/表格/图表/页眉页脚结构与当前正式路径回归保持。

## 3. 产品入口、文档、评审与发布

- [ ] 原周报详情添加明确的历史验收入口和状态文案，原正式/历史区分及定时关闭可见；必要JS合同测试。
- [ ] 同步周报数据/生产、架构模块、接口、安装/安全/平台及README复核；新测试只加原CI步骤，不加job/依赖/timeout。
- [ ] 执行相关Python/JS、ruff/black/isort/mypy、索引、文档/架构/约束和完整Router，保留失败证据。
- [ ] 独立规格审查后独立代码质量审查，按最终SHA/tree重新绑定。
- [ ] 按受管Git安全入口提交、发布PR、核对公开仓库额度及原三CI、正常合并；部署仍单独授权。

## 4. 真实验收（源码交付不替代）

- [ ] 核对实际常驻版本/源码/owner与原数据保全；复用适用已部署版本，不回退后续合格版本。
- [ ] 通过原API创建一次历史验收Run，保留真实取数、冻结和失败/修订证据；结果未知不重复模型。
- [ ] 数字/引用/正文/文件门全部记录，确证不finalized且不改正式稿/日程。
- [ ] 原Word逐页、表格图表、页眉页脚、标签、重开与下载文件哈希检查；三周期与正式实时验收保持待验。
- [ ] 归档恢复校验后按本任务归属安全收尾；原数据、日志、未知与其他任务资源保护。
