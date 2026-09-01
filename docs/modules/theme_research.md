# Theme Research Packs

## 边界

主题研究模块只拥有版本化 `theme_pack` Manifest 和统一 `theme_observation` 事实。六类产品视图（snapshot、KPI、value chain、events、assets、health）均由查询时投影生成，不新增平行事实表。主题入口只生成 `WorkspacePrefillRequest`，不写研究结论，也不把模型输出写回事实区。

首批声明包位于 `resources/research_packs/`：黄金、航天航空、光伏、AI 基础设施/光模块。创业板 50 只以 `index:399673.SZ` 的 `market_proxy` 暴露关系出现在光伏和 AI Pack，不继承 LSH 策略范围。

## Manifest 与生命周期

每份 Manifest 固定声明：key/kind/version/兼容版本、主题边界、dataset 字段 schema、row identity、时间/主体/指标/数值/单位映射、来源优先级/来源等级、新鲜度、KPI 精确 metric、产业链、事件类型、资产暴露、研究模板、可信内置插件 ID，以及可选的首页失效区块。Manifest 及嵌套对象禁止额外字段；所有必填集合非空，key 唯一，dataset/evidence/rationale 引用必须闭合。identity、dimension、observed/available time、subject 和 metric 等直接索引的结构字段必须在 schema 中声明为 required；optional 字段不能被提升为结构键，从而在摄入前消除缺列 `KeyError`。

生命周期只允许：

```text
discovered → validated → enabled ↔ degraded
                    ↘ disabled ←
```

`sync_manifests()` 可幂等执行。生命周期由数据库状态权威控制，重读文件不会把 degraded/disabled 重置成 discovered；Repository 自行对 Manifest canonicalize/hash，调用方不能提供或复用旧 hash 绕过不可变性。同一 `pack_key/version` 的相同内容可幂等保存，内容不同则拒绝为不可变版本冲突，升级必须发布新 version。状态写入只接受 `PackLifecycle`，并在 Repository 内再次验证合法转换；任意字符串和逆向/跳级转换不会触碰 DB row。最终更新使用 `WHERE pack_key/version/status=<expected>` 的 CAS；竞争事务改变 expected status 后 rowcount 为 0，后写事务拒绝而不能覆盖 disabled 等终态。必要 dataset 缺失或超时使 enabled Pack 进入 degraded；数据恢复后回到 enabled。disabled 只读保留。

## 插件安全边界

插件不是任意 Python/Shell 扩展。Manifest 只能引用代码库中固定、带版本的 `builtin.*.vN` ID，operation 只允许 `normalize|validate|derive` 且必须与内置定义一致。Registry 不接受外部 Python source 或运行时 callable 注册，因此 `getattr/__import__`、`importlib`、闭包/容器携带 `os` 等路径均不能进入执行面；输入与输出仍必须进行无 NaN 的 JSON round-trip。首批四个 Pack 的 `plugins` 为空，不加载任何外部插件代码。

## 摄入语义

`ThemeResearchService.ingest_file()` 默认 dry-run；只有 `apply=True` 才写入。每个文件保存 SHA-256 source hash；identity/dimension fields 先按字段类型完整规范化，再与精确 metric 生成稳定语义 identity。数值和数量不得参与 identity。源数据缺少完整业务主键、但同维度允许多条合法事实时，Manifest 可显式声明 `source_row_discriminator: row_number`；海关 Pack 用 period/flow/region/partner/HS/source-file 加不可变源文件内行号形成可解释 `dimension_key`，并写入 `subject_ref`。因此 4,979 条源行完整形成 9,958 个 observation，snapshot 同样保留 9,958 个事实；同一维度/行号的值修订会成为 conflict 而不是新 identity。长表一行生成一个 observation；宽表按 `observation_fields` 为每个有值字段生成独立 observation。跨 source hash 的相同 identity 只有在规范化 payload、时间、来源、值和单位语义相等时才返回 duplicate；同 identity 的不可解释不同值或 payload 进入 quarantine，既不覆盖旧事实也不误报 duplicate。

行结果严格区分：

- accepted：契约完整；显式 apply 时写入 `theme_observation`。
- quarantined：时间、来源或字段语义无法可靠解析；不写事实。
- rejected：缺单位或命中禁止内容；不写事实。
- duplicate：已存在或同一文件内重复；不重复写入。

每行的 source name、freshness 与 verification 由该行或 Manifest 显式映射决定；source tier 只接受 Manifest 对精确 source name 的固定映射，既不按名字 token 猜测，也不从来源优先级继承高等级。快照先在查询时间可用的事实中按 `dataset+subject+metric` 选择最大 fact `as_of`，相同事实期再选较新 publication；snapshot 与 health 均以同一选中事实集合和 dataset SLA 计算 freshness/coverage。snapshot facts、KPI observations 和 events 返回不落库的 effective observation：source-reported fresh 超过 dataset SLA 后投影为 stale，并增加 `dataset_sla_stale`，而数据库原始 observation 仍保持 source freshness。报告包括 accepted/quarantined/rejected/duplicate/applied、source hash、行级安全错误码和 `IngestionCheckpoint`。断点必须携带相同 source hash 和运行 mode；dry-run checkpoint 不能用于 apply，避免跳过尚未写入的行。`--resume-from` 从同 mode 既有报告恢复逐文件 checkpoint；`--apply` 仅在数据库 commit 成功后原子写报告，commit 失败会 rollback 且不留下成功报告。`catalysts.csv`（含 `score_hint`）、`driver-summary.csv`、策略 YAML、订单和评分字段固定拒绝；apply 只保存聚合拒绝统计，不保存禁止行内容。

apply 在 PostgreSQL 事务内使用 dataset namespace 与 semantic identity 的 `pg_advisory_xact_lock` 串行化检查和写入，避免不同 source hash 并发绕过 `SELECT → INSERT` 冲突判定。SQLite 测试/本地兼容路径先显式开启 Session transaction，再获取进程内 dataset 锁并持有到外层 commit/rollback；未知 Pack 在取锁前由 Registry 拒绝，避免异常前无事务导致锁泄漏。SQLite 路径不承诺跨进程一致性。

声明 `market_home_section: global_context|market_mainlines` 的 dataset 在 apply 时通过统一 helper 写 `market_home.section_invalidated` outbox。observation、摄入报告和 outbox 使用同一 Session/事务，只 flush 不自行 commit；外层 rollback 会同时撤销事实与失效事件。未声明参与首页投影的主题数据不发送首页失效。

## API

```text
GET  /api/themes
GET  /api/themes/{key}/snapshot
GET  /api/themes/{key}/kpis
GET  /api/themes/{key}/value-chain
GET  /api/themes/{key}/events
GET  /api/themes/{key}/assets
GET  /api/themes/{key}/health
POST /api/themes/{key}/research-workspaces
```

不存在的 Pack 返回 404；没有可追溯 observation 的事实快照返回 404；请求错误返回 400；异常细节不会泄漏到响应。所有 repository 写入依赖请求级事务，不在模块内自行 commit。

## 验证范围

单元测试覆盖四份 Manifest、不可变版本/数据库权威生命周期、可信插件 ID/三类逃逸、宽表拆分、规范化 identity/payload 幂等、真实冲突 quarantine、SQLite 并发提交、来源/时效/SLA/verification、快照事实期选择与跨读模型 coverage、默认 dry-run、显式 apply、mode-safe 断点恢复、commit 失败、首页 outbox 同事务回滚、六类读模型、研究预填和 API 错误映射。`scripts/migrate_lsh_theme_data.py` 提供默认 dry-run、显式 `--apply`、`--source`、`--output` 与 `--resume-from`；dry-run 使用内存数据库，不连接或写入目标数据库。真实 LSH dry-run 覆盖三个已知主题目录下的 28 个顶层 CSV（包括未映射和禁止迁移的数据，以 rejected 报告保留审计结果）；运行报告与未验证项见 `.ai/reports/2026-09-01-merged-platform-theme-research.md`。
