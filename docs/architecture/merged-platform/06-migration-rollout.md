# 06 迁移、兼容与删除门禁

## 职责

迁移流程把 LSH 的可迁移主题数据与受限研究能力收敛到 AlphaFoundry，不做一次性大切换。旧 LSH 入口先由兼容适配器转发；只有功能等价、数据校验、回归、调用归零和归档证据齐全后才删除。等价迁移完成后，LSH 保持只读归档一个稳定版本。

## 数据归属

- AlphaFoundry PostgreSQL 最终拥有全部迁移后的 `theme_observation`、Workspace/Run 与个人观察数据。
- LSH CSV/SQLite/Flask 仅是迁移来源；source file hash、row identity、行级结果和原始归档路径必须保留。
- `lsh-capability-map.yaml` 记录 source、target、classification、data_migration、parity_test、call_count_zero、archive_path、status。
- 策略、交易和基金审批能力冻结为只读归档，不作为重复能力删除；其策略评分、YAML 交易规则、纸面订单、账户、模拟交易、`score_hint`、`driver-summary` 不迁入新事实模型。

## 禁止依赖

- 不双写 AlphaFoundry 与 LSH，不让 DSH/Vibe/Flask 继续成为事实源。
- 不在校验前 apply，不因导入失败覆盖有效目标记录，不删除唯一数据副本。
- 不用静态代码搜索代替运行时零调用证据，不用 UI 相似代替 API/数据等价测试。
- 不把 archive 当备份；归档前必须有可恢复的数据导出、哈希和版本标签。
- 不在本 Task 添加 Python/Tauri 依赖、发布、执行破坏性删除或外部协调。

## 公共 API 与类型

迁移器接口：

```text
scripts/migrate_lsh_theme_data.py --source <path> --dry-run --output <report.json>
scripts/migrate_lsh_theme_data.py --source <path> --apply --output <report.json>
scripts/migrate_lsh_theme_data.py --source <path> --dry-run --resume-from <prior-report.json> --output <report.json>
```

默认必须是 dry-run；apply 需要显式参数。报告类型 `MigrationReport` 包含 `accepted/quarantined/rejected/duplicate`、文件/行数、缺失、冲突、单位、source hashes、逐文件 checkpoint、运行 mode、目标 revision 与数据库写入计数。恢复报告必须与同一 source root/source hash/mode 匹配；dry-run checkpoint 禁止用于 apply 跳行。apply 只有在数据库 commit 成功后才原子发布报告，commit 失败 rollback 且不生成成功报告。

兼容门禁 `LegacyCapabilityDecision` 返回 `allowed`、`missing_evidence`、`target`、`archive_path`。旧适配器响应带 deprecation 标识和 correlation ID；新前端只调用新领域 API。

## 主流程

1. 冻结 LSH source version 与文件哈希，分类为 data、runtime、UI、strategy/trading 或 discard。
2. 运行四段 Alembic：`015_add_platform_fact_core` → `016_add_theme_and_market_home` → `017_add_research_workspace_runtime` → `018_add_asset_observation`。
3. 对 LSH 主题文件运行 dry-run，审阅 accepted/quarantined/rejected、重复、单位和冲突。
4. 获得明确 apply 决策后写入新表；按规范化业务 dimension/source-row discriminator（禁止值/数量参与 identity）+ 完整规范化 payload 判定 duplicate/不可解释冲突，source hash 保留审计。dimension 同时进入 subject_ref/read-model key，防止投影隐式折叠。PostgreSQL 使用事务级 advisory lock 串行化并发 semantic identity；复核计数和抽样事实。
5. 新 API 与旧能力并行读，对相同 fixture/as_of 跑 parity；前端切到新 API，旧适配器持续计量调用。
6. `data_migration + parity_test + regression + call_count_zero + archive_path` 全绿后停止 LSH，把目录与数据导出设为只读归档，并观察一个稳定版本；观察期发现回归时恢复适配器而不是双写。
7. 稳定观察期完成且所有证据持续有效后，gate 才允许删除重复 Flask、SQLite、静态 Dashboard 和平行运行模型；策略、交易和基金审批不进入删除集合。删除后继续回归监测。

## 状态与失败

- Capability：`inventory → mapped → adapted → parity_verified → deprecated → zero_call_observed → archived → removed`。
- Data row：`scanned → accepted|quarantined|rejected|duplicate`；accepted 只有 apply 后变为 `applied`。
- 任一门禁失败返回 `blocked` 并列出证据，不推进删除。
- 迁移事务失败回滚该批；恢复从幂等键继续。schema migration 失败停在当前 revision，不能标记完成。
- 稳定版本观察期发现回归进入 `rollback_adapter`，保留新库已验证事实并暂停删除，不向旧库双写。

## 可观测性

日志记录 `capability_key`、`source_version`、`source_hash`、`migration_revision`、`row_outcome`、`parity_case`、`legacy_call_count`、`gate_status` 和 `archive_version`。指标覆盖每类行结果、迁移吞吐/回滚、parity 差异、旧 API 调用、适配器错误、删除门禁阻断与观察期回归。

## 测试与验收

- Alembic 图测试确认 014→015→016→017→018 单线 upgrade/downgrade，20 张表准确且无重复事实表。
- 迁移器 fixture 测试覆盖真实 LSH CSV header、禁止文件、哈希幂等、quarantine 和默认无写入。
- 每项 capability 必须有 target API、数据迁移证据、parity 测试、相关回归、连续稳定观察窗口的零调用和可读 archive path。
- 前端静态契约断言首页、资产、行业、研究只调用新领域 API；研究输出不写事实 API。
- 归档验收记录 commit/tag、schema/version、文件哈希、恢复说明和只读权限。
- 桌面相关迁移仍需原生 macOS/Windows CI；发布前真实 Windows 安装级烟测不能由本地验证替代。
- PostgreSQL 集成测试必须覆盖迁移、幂等摄入、快照、任务租约、项目隔离和通知持久化。
- API/SSE 测试必须覆盖分页、断线重连、取消、恢复、Provider 故障和部分数据降级。
- 浏览器验收必须覆盖首页、资产观察、主题研究、FinGPT/Claw 四条完整旅程。
- 安全测试必须证明 DSH 无数据库权限，Skill/MCP 未授权调用被拒绝，项目记忆互相隔离。
- 性能门槛固定为缓存首页 P95≤500ms、资产/主题详情 P95≤1s、SSE 首状态≤1s、提醒评估延迟≤60s。

## V1 实施记录

- `services/legacy_capability_gate.py` 已实现 fail-closed 删除判断；清单缺失、字段不全、未知 capability 或未达到 `archived` 状态都不会获得删除许可。
- `lsh-capability-map.yaml` 采用 JSON-compatible YAML，避免为清单读取新增运行时依赖；当前真实证据均按未完成记录，因此没有任何 LSH 重复能力获准删除。
- `strategy_trading` 与 `fund_approval` 固定为 `freeze_read_only`，门禁始终返回 `retain_read_only`。
- 首页、资产观察、主题产业链和研究入口的现有前端已接入新领域 API；这只是兼容期适配，不代表 LSH 已达到零调用、只读归档或可删除状态。
