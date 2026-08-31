# 06 迁移、兼容与删除门禁

## 职责

迁移流程把 LSH 的可迁移主题数据与受限研究能力收敛到 AlphaFoundry，不做一次性大切换。旧 LSH 入口先由兼容适配器转发；只有功能等价、数据校验、回归、调用归零和归档证据齐全后才删除。等价迁移完成后，LSH 保持只读归档一个稳定版本。

## 数据归属

- AlphaFoundry PostgreSQL 最终拥有全部迁移后的 `theme_observation`、Workspace/Run 与个人观察数据。
- LSH CSV/SQLite/Flask 仅是迁移来源；source file hash、row identity、行级结果和原始归档路径必须保留。
- `lsh-capability-map.yaml` 记录 source、target、classification、data_migration、parity_test、call_count_zero、archive_path、status。
- 不迁入 LSH 的策略评分、YAML 交易规则、纸面订单、账户、模拟交易、`score_hint`、`driver-summary` 或旧策略范围。

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
```

默认必须是 dry-run；apply 需要显式参数。报告类型 `MigrationReport` 包含 `accepted/quarantined/rejected/duplicate`、文件/行数、缺失、冲突、单位、source hashes、目标 revision 与数据库写入计数。

兼容门禁 `LegacyCapabilityDecision` 返回 `allowed`、`missing_evidence`、`target`、`archive_path`。旧适配器响应带 deprecation 标识和 correlation ID；新前端只调用新领域 API。

## 主流程

1. 冻结 LSH source version 与文件哈希，分类为 data、runtime、UI、strategy/trading 或 discard。
2. 运行四段 Alembic：`015_add_platform_fact_core` → `016_add_theme_and_market_home` → `017_add_research_workspace_runtime` → `018_add_asset_observation`。
3. 对 LSH 主题文件运行 dry-run，审阅 accepted/quarantined/rejected、重复、单位和冲突。
4. 获得明确 apply 决策后写入新表；按 source hash + row identity 幂等，复核计数和抽样事实。
5. 新 API 与旧能力并行读，对相同 fixture/as_of 跑 parity；前端切到新 API，旧适配器持续计量调用。
6. 只有 `data_migration + parity_test + regression + call_count_zero + archive_path` 全绿，gate 才允许删除。
7. 删除后观察一个稳定版本；LSH 目录与数据导出只读归档，发现回归时恢复适配器而不是双写。

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
