# Merged Platform Task 5 — Theme Research Packs

## 实施范围

- 新增四个声明式 Research Pack：gold、aerospace、photovoltaic、ai_infrastructure。
- 扩展主题契约：dataset schema/mapping、六类读模型、工作区预填、摄入报告与断点。
- 新增 Registry、Repository、Service 和 `/api/themes` 路由，并在 FastAPI 主应用最小接入。
- 实现 Manifest 生命周期、静态/运行时插件能力门、统一 ThemeObservation、dry-run/显式 apply、source hash、row identity 幂等、accepted/quarantined/rejected/duplicate 和断点恢复。
- 明确拒绝 LSH `score_hint` catalysts、`driver-summary`、策略、订单及评分字段；创业板 50 仅作为光伏/AI 的 index market proxy。
- 独立审查后收紧为可信内置插件 ID；Manifest 及嵌套对象 `extra=forbid`、非空/唯一/引用闭合；宽表拆分 observation，按完整规范化 identity/payload 区分 duplicate 与 conflict quarantine。
- 修正来源 tier、freshness/SLA coverage、verification、`as_of/available_at`、snapshot subject key、KPI 精确 metric，以及数据库权威 lifecycle/content hash。
- Theme apply 与 `market_home.section_invalidated` outbox 使用同一事务；仅 Manifest 显式声明的 `global_context|market_mainlines` dataset 触发。
- CLI 新增 `--resume-from`；显式 apply 仅在 commit 成功后写报告，commit 失败 rollback 且无成功报告。
- 复审后补齐 source-row discriminator 无损海关展开、checkpoint mode 隔离、不可变 Manifest version、最大 fact `as_of` 快照、snapshot/health 一致 coverage，以及 PostgreSQL advisory transaction lock/SQLite 事务期兼容锁。
- Repository 现自行 canonicalize/hash Manifest，并以枚举和转换表保护 lifecycle；调用方旧 hash、任意状态字符串和非法逆向转换均无法改写 DB。
- 海关 dimension 由 period/flow/region/partner/HS/source-file/源行号组成，数值不参与 identity；真实 SQLite apply 验证 accepted=persisted=snapshot=9,958，KPI 金额点 4,979。

## TDD 证据

首次 RED：

```text
python -m pytest tests/unit/test_theme_pack_registry.py tests/unit/test_theme_research_service.py tests/unit/test_theme_research_api.py -q
结果：3 个 collection error，分别缺少 Registry、Repository 与 API route（符合新能力尚未实现的预期）。
```

随后为同文件重复、可选 CSV 字段、JSON-like 插件输入、分组数字/日期、断点 source hash、拒绝统计持久化和幂等 manifest sync 分别增加失败测试并观察预期失败，再实现最小修复。

独立审查修复的首次聚焦 RED：

```text
python -m pytest tests/unit/test_theme_pack_registry.py tests/unit/test_theme_research_service.py tests/unit/test_lsh_theme_migration.py -q
结果：19 failed, 28 passed。失败覆盖任意 callable 三类逃逸、Manifest 严格校验、真实 identity 冲突、宽表拆分、行级来源/时效/verification、DB lifecycle、resume 与 commit 失败。
```

随后继续以 RED→GREEN 补充：`12`/`12.0` 持久化语义等价、规范化日期 identity、随时间变化的派生 freshness 不影响相同 source payload 幂等、dataset SLA coverage、数据库拥有 lifecycle 的内容哈希、Manifest 显式首页区块与 observation/outbox 同事务 rollback，以及 source payload 不能自行授权首页 invalidation。

第二轮复审修复首先观察到以下 RED：海关同维度合法多行被误 quarantine、名称含 `official` 的攻击来源被提权、首页重复 apply 在空 accepted 集合执行 `max()`、dry-run checkpoint 可错误跳过 apply、同 Pack version 被覆盖、旧事实晚发布覆盖新事实期、snapshot/health coverage 不一致、嵌套 AssetRef/KPI/rationale 引用泄漏，以及两个 SQLite 并发 source hash 均 accepted。实现后对应聚焦回归 `5 passed`；完整 Task 5 聚焦回归见下方最终验证。

第三轮复审首先以直接 Repository 攻击观察到旧 content hash 可覆盖同 version Manifest、任意字符串可写坏 lifecycle；另复现 persisted 9,958 facts 被 snapshot 折叠为 2，以及 SQLite 在无活跃事务时取锁后 rollback 无法释放。对应测试全部先 RED；修复后 Repository 攻击 4 项相关测试与 projection/锁 4 项相关测试均 GREEN。

第四轮复审先复现 optional `source_url` 可被提升为 identity/subject 并在 CSV 缺列时 `KeyError`、SLA 过期事实只在 snapshot 顶层 stale 而 facts/KPI/events 仍 fresh，以及 lifecycle ORM UPDATE 只按主键、无 expected-status CAS。Manifest 结构字段 required 校验、三类 effective observation 投影和 CAS SQL/竞争终态注入测试均先 RED 后 GREEN；真实 PostgreSQL 并发仍列为未验证项。

## 已执行验证

```text
python -m pytest tests/unit/test_theme_pack_registry.py tests/unit/test_theme_research_service.py tests/unit/test_theme_research_api.py -q
阶段结果：23 passed（增加后续边界测试前的中间 GREEN）。
```

真实 LSH dry-run 使用新增 CLI 与内存 SQLite；未连接或写入目标数据库：

```text
python scripts/migrate_lsh_theme_data.py \
  --source /Users/leon/Desktop/LSH_Project/manual_data/skills \
  --dry-run \
  --output /tmp/lsh-theme-migration-report-reviewed.json

source: /Users/leon/Desktop/LSH_Project/manual_data/skills
files scanned: 28
accepted: 14575
quarantined: 0
rejected: 16
duplicate: 0
applied: 0
source hashes: 28
checkpoints: 28
checkpoint modes: dry-run only
```

计数变化是预期的契约修正，不是源文件变化。官方海关文件的 4,979 条源行在相同业务维度下允许多条不同金额/数量；Manifest 用非值业务维度、source file 和不可变源文件内行号形成显式 dimension，金额/数量不参与 identity。每行的 value/quantity 两个 metric 共形成 9,958 个 accepted observation、0 quarantine，没有用审计记录替代事实，也不会在 snapshot 中折叠。`ai-token-usage.csv` 的 `other` 聚合排名是合法来源语义，按 string 保留 total_tokens/rank 两个 observation，因此该文件也为 0 quarantine。16 条 rejected 包括两份含 `score_hint` 的 catalysts（4+4）、`driver-summary`（1）、两条数值缺单位的 macro rows（2），以及未映射的非 official optical-module customs 文件（5），均保留行级拒绝审计而不写事实。每个文件均生成 SHA-256 source hash 与带 `mode=dry-run` checkpoint；真实运行严格为 dry-run，未连接或写入目标数据库。

最终验证：

```text
python -m pytest \
  tests/unit/test_theme_pack_registry.py \
  tests/unit/test_theme_research_service.py \
  tests/unit/test_theme_research_api.py \
  tests/unit/test_lsh_theme_migration.py \
  tests/unit/test_merged_platform_contracts.py \
  tests/unit/test_merged_platform_migration.py -q
结果：145 passed

python -m ruff check <12 个 Task 5/共享契约 Python 文件>
结果：All checks passed

python -m black --check <12 个 Task 5/共享契约 Python 文件>
结果：12 files would be left unchanged

python -m isort --check-only <12 个 Task 5/共享契约 Python 文件>
结果：通过

python -m mypy <7 个 Task 5 source/CLI 文件>
结果：Success: no issues found in 7 source files
```

## 未验证项

- 未在真实 PostgreSQL + pgvector 实例执行 apply 或查询性能验证；SQLite 单元集成不能替代生产数据库验证。
- 未执行 LSH 数据 apply；真实扫描严格保持 dry-run，无数据库写入。
- LSH 中没有可映射的黄金 CSV；黄金纵切使用契约 fixture 完成 apply、幂等与六类投影验证，生产黄金数据仍需 Connector/迁移源。
- 本任务不修改桌面端，不涉及 Windows 安装包；也未宣称 Windows 验证。
