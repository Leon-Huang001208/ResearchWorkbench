# Theme Research Packs

## 边界

主题研究模块只拥有版本化 `theme_pack` Manifest 和统一 `theme_observation` 事实。六类产品视图（snapshot、KPI、value chain、events、assets、health）均由查询时投影生成，不新增平行事实表。主题入口只生成 `WorkspacePrefillRequest`，不写研究结论，也不把模型输出写回事实区。

首批声明包位于 `resources/research_packs/`：黄金、航天航空、光伏、AI 基础设施/光模块。创业板 50 只以 `index:399673.SZ` 的 `market_proxy` 暴露关系出现在光伏和 AI Pack，不继承 LSH 策略范围。

## Manifest 与生命周期

每份 Manifest 固定声明：key/kind/version/兼容版本、主题边界、dataset 字段 schema、row identity、时间/主体/指标/数值/单位映射、来源优先级、新鲜度、KPI、产业链、事件类型、资产暴露、研究模板与插件权限。

生命周期只允许：

```text
discovered → validated → enabled ↔ degraded
                    ↘ disabled ←
```

`sync_manifests()` 可幂等执行。必要 dataset 缺失或超时使 enabled Pack 进入 degraded；数据恢复后回到 enabled。disabled 只读保留。

## 插件安全边界

插件不是任意 Python/Shell 扩展。Registry 只允许 `normalize`、`validate`、`derive` 三种已注册纯函数。注册前和每次运行前都会检查 callable 指纹与危险名称；静态检查拒绝网络、SQLAlchemy/数据库、模型网关、Shell、`open`、`pathlib`、动态导入等能力。输入与输出必须能进行无 NaN 的 JSON round-trip，因此文件句柄、Session、HTTP client、模型对象等能力对象不能注入。首批四个 Pack 不加载任何外部插件代码。

## 摄入语义

`ThemeResearchService.ingest_file()` 默认 dry-run；只有 `apply=True` 才写入。每个文件保存 SHA-256 source hash，每行使用 Manifest identity fields 生成稳定 row identity hash。唯一键为 `pack_key + dataset_key + row_identity + source_hash`，同文件重复和重复 apply 都返回 duplicate。

行结果严格区分：

- accepted：契约完整；显式 apply 时写入 `theme_observation`。
- quarantined：时间、来源或字段语义无法可靠解析；不写事实。
- rejected：缺单位或命中禁止内容；不写事实。
- duplicate：已存在或同一文件内重复；不重复写入。

报告包括 accepted/quarantined/rejected/duplicate/applied、source hash、行级安全错误码和 `IngestionCheckpoint`。断点必须携带同一个 source hash，避免文件变化后错误续跑。`catalysts.csv`（含 `score_hint`）、`driver-summary.csv`、策略 YAML、订单和评分字段固定拒绝；apply 只保存聚合拒绝统计，不保存禁止行内容。

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

单元测试覆盖四份 Manifest、生命周期、插件静态/运行时边界、dry-run、显式 apply、幂等、同文件重复、断点 source hash、隔离/拒绝、六类读模型、研究预填和 API 错误映射。`scripts/migrate_lsh_theme_data.py` 提供默认 dry-run、显式 `--apply`、`--source` 与 `--output`；dry-run 使用内存数据库，不连接或写入目标数据库。真实 LSH dry-run 覆盖三个已知主题目录下的 28 个顶层 CSV（包括未映射和禁止迁移的数据，以 rejected 报告保留审计结果）；运行报告与未验证项见 `.ai/reports/2026-09-01-merged-platform-theme-research.md`。
