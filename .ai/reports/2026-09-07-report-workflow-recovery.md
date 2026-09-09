# Report Workflow 完整落地与断电恢复验收记录

## 当前结论

- 目标分支：`codex/web-consolidation`。
- 项目 Web `8088` 与专属 DSH `3081` 已通过 `rwb web status` 和 HTTP 健康检查；默认模型为 `deepseek-v4-flash`，凭据已配置。
- 华安 ETF 周报、创业板 50 周报、华安 ETF 投资风向标与 AI 周报已在 Claw 和能力中心使用真实报告 Workflow 目录展示。AI 周报继续为 `needs_attention`。
- 资产观察已作为独立主导航页面恢复，包含独立行情/财务/事件/公告/资料状态、自选、笔记、提醒和 FinGPT/Claw 快照交接。
- 投资风向标 v3 已完成真实 Claw 运行、双子 Agent、确定性 PPTX 组装和重开验收。华安 ETF 周报仍为 `delivery_incomplete`，创业板 50 的 iFinD 公式刷新仍未通过，因此尚未满足合并、推送和清理门禁。

## 已实现

1. `rwb` 使用仓库自举路径启动，不依赖 hidden worktree 的 editable `.pth`；项目停止/重启逻辑只管理 `8088/3081`。
2. 报告 Workflow 使用不可变版本和独立 Run 副本；创业板 50 的误标 Wind 文件保留为 `legacy_mislabeled`，不进入刷新步骤。
3. Wind/iFinD 公式检测覆盖短公式、`EDB`、`S_INFO_*`、`S_WQ_*`、`THS_*` 和 `thsiFinD`。
4. Excel 刷新、底稿提取、模板检查、图表、DOCX/PPTX 组装与交付检查以受控 Tool 边界实现；Claw 只负责研究与结构化 Payload。
5. 华安真实运行 `d3c6b827e2f2442980335ae2cbfc170e` 刷新两份 Wind 底稿，生成共享快照 SHA-256 `9e15975b2460d92d2ce024cd2fedc4e08ed7b0a3e1401bf346d6322d91548b60`，并由两个真实子 Agent 共用。
6. 该运行生成可重开的 DOCX、HTML、XLSX；文件有效但正文区块不完整，系统按设计保留有效文件并拒绝标记完整交付或启用日程。
7. 报告 Payload 的 `blocks`、`date_blocks`、`table_blocks`、`chart_blocks` 等家族统一投影；显式 `missing` 高于解释文字，缺失说明不能冒充已交付正文。
8. 架构主入口固定为十张图，并新增报告运行序列与 Excel 数据流；API Atlas 区分 113 个唯一操作与 115 项源码声明。
9. PPTX 渲染支持跨多个 `<a:t>` 文本片段的占位符替换；交付验证会按段落重组文本并拒绝残留占位符，不能再以“文件可打开且有文字”误判通过。
10. Report Workflow 无论 Claw 是否提前生成 Office 文件，都必须使用结构化 `report_payload.json` 经受审查渲染器重新投影；投影未完成时进入 `delivery_incomplete`。迁移报告的新不可变版本统一要求至少两个真实子 Agent。
11. 投资风向标 v3 运行 `d7e47d9d680647dc878fd42f243dc74b` 使用共享快照 `0b273259b72f163c692fe91ddc6be6b243751252173edee2a75a99ca8a9391f8`；两个真实子 Agent 分别消耗 12,822 和 11,407 tokens。最终 PPTX 为 1,323,374 bytes、SHA-256 `76a6c4e12ef7fb3bd30636dfa7e001dce883dc988273e5e90d569d1b9f1e69f7`，ZIP 完整且无残留占位符。

## 验证证据

- Python Research Web：`424 passed, 3 skipped`，仅有一个 AnyIO 弃用警告。
- JavaScript：`171 passed, 1 skipped`；跳过项需要固定 DSH 源码条件，不是失败。
- 报告投影专项：`4 passed`，包含“显式 missing 即使有解释文字也不能通过”的回归。
- 最新报告渲染、交付、Workflow 集成与迁移专项：`110 passed`；新增跨文本片段 PPTX、强制确定性投影和最低子 Agent 数回归。
- 浏览器布局：5 个视口 × FinGPT/Claw/能力中心，共 15 组检查通过；没有模型调用或写操作。
- 断电恢复后的布局回归先复现了旧统一侧栏 ARIA 名称导致的测试失败；测试已改为匹配 FinGPT/Claw 当前独立侧栏契约，并重新完成 15 组检查。
- 架构文档浏览器验收：十图入口、API Atlas 计数/搜索、沙箱导航、主题和节点详情均通过。
- Archify 最终图：showcase 9/9、零错误、零警告，四视口无溢出并完成人工截图复核。
- Ruff、Node syntax、`git diff --check`、架构一致性和文档同步检查均通过。
- 服务核对：`8088`、`3081` 健康；OpenAPI 为 113 个唯一操作。

## 真实验收阻塞项

1. 华安 Workflow 的已刷新底稿不包含足够新闻、宏观与行业证据；真实模型 Payload 明确列出缺失区块。不得用模型猜测或旧静态内容填满。
2. 2026-09-07 最新主动探测中，Wind 在 180 秒上限内未稳定完成并返回 `provider_timeout`；iFinD 在 146 秒后返回 `formula_error`。创业板 50 不能宣称通过，也不能使用旧缓存替代。
3. 由于两项真实阻塞仍存在，周报日程保持关闭；`master` 合并、GitHub 推送、worktree/旧目录清理均未执行。
