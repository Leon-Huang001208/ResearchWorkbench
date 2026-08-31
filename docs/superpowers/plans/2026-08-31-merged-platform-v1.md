# AlphaFoundry × LSH Merged Platform V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 AlphaFoundry 与 LSH 的可迁移能力收敛为一个 PostgreSQL 事实源、一个 FastAPI 业务内核、四个边界清晰的产品模块，以及可选的 DSH Runtime 侧车。

**Architecture:** 保持现有模块化单体和 Tauri + Python sidecar 交付形态。新增共享事实契约、主题观测、研究工作区、观察列表与提醒等领域对象；现有 Research Run、资产、指数、ETF、基金、Evidence 与 Connector 作为底座复用。DSH 只实现 `RuntimeProvider`，不得直接读写数据库。

**Tech Stack:** Python 3.11+、Pydantic v2、FastAPI、SQLAlchemy 2、PostgreSQL + pgvector、Alembic、APScheduler、SSE、pytest、Tauri 2、Archify。

---

## 交付与依赖顺序

任务必须按顺序执行。Task 1–2 固化架构和共享内核；Task 3–6 分别交付可测试的软件纵切；Task 7 处理迁移；Task 8 做总集成和交付。

### Task 1: 架构包与九张图

**Files:**
- Create: `docs/architecture/merged-platform/README.md`
- Create: `docs/architecture/merged-platform/00-system-overview.md`
- Create: `docs/architecture/merged-platform/01-shared-contracts.md`
- Create: `docs/architecture/merged-platform/02-fingpt-claw.md`
- Create: `docs/architecture/merged-platform/03-market-home.md`
- Create: `docs/architecture/merged-platform/04-theme-research-packs.md`
- Create: `docs/architecture/merged-platform/05-asset-observation.md`
- Create: `docs/architecture/merged-platform/06-migration-rollout.md`
- Create: `docs/architecture/merged-platform/diagrams/*.json`
- Create: `outputs/merged-platform-architecture/*.html`
- Modify: `docs/ARCHITECTURE.md`
- Modify: `docs/FILE_GUIDE.md`
- Modify: `docs/CHANGELOG.md`

- [ ] **Step 1: 写七份架构正文与索引**

每份正文必须固定：职责、拥有的数据、禁止依赖、公共接口、主流程、失败语义、状态机、可观测性、测试与验收。`README.md` 必须给出模块依赖顺序和实现导航。

- [ ] **Step 2: 编写九份 Archify JSON**

分别使用 `architecture`、`sequence`、`dataflow`、`lifecycle` 表达系统部署、模块依赖、核心 ER、研究请求、Research Run、首页数据流、Pack 生命周期、资产提醒和迁移门禁。每份图不超过 12 个主节点，中文标签，`meta.quality_profile` 为 `showcase`。

- [ ] **Step 3: 验证并交付每张图**

Run for every candidate:

```bash
node /Users/leon/.codex/skills/archify/bin/archify.mjs validate <type> <json> --quality showcase --json
node /Users/leon/.codex/skills/archify/bin/archify.mjs deliver <type> <json> <html> --quality showcase --json
node /Users/leon/.codex/skills/archify/bin/archify.mjs visual-check <html> --json
```

Expected: 9/9 showcase checks, 0 composition errors, 0 warnings；四个视口无横纵溢出。人工检查最小和最大尺寸的明暗截图。

- [ ] **Step 4: 文档自检**

Run:

```bash
rg -n "TODO|TBD|FIXME|待定" docs/architecture/merged-platform
rg -n "research_workspace|theme_observation|watchlist|market_home_snapshot" docs/architecture/merged-platform
```

Expected: 第一条无输出；第二条能在数据归属、API 和迁移章节定位每个对象。

- [ ] **Step 5: Commit**

```bash
git add docs/architecture/merged-platform docs/ARCHITECTURE.md docs/FILE_GUIDE.md docs/CHANGELOG.md outputs/merged-platform-architecture
git commit -m "docs: define merged platform architecture"
```

### Task 2: 共享契约、持久化模型与迁移

**Files:**
- Create: `core/contracts/platform_shared.py`
- Create: `core/contracts/theme_research.py`
- Create: `core/contracts/research_workspace.py`
- Create: `core/contracts/asset_observation.py`
- Create: `core/contracts/market_home.py`
- Modify: `core/contracts/research.py`
- Modify: `data_layer/repositories/models.py`
- Create: `storage/migrations/versions/015_add_merged_platform_core.py`
- Test: `tests/unit/test_merged_platform_contracts.py`
- Test: `tests/unit/test_merged_platform_migration.py`

- [ ] **Step 1: 写失败的契约测试**

```python
def test_observation_requires_source_and_time_context():
    with pytest.raises(ValidationError):
        ObservationEnvelope(
            observation_id="obs-1",
            subject_ref="asset:1",
            metric_key="close",
            observed_at=NOW,
            available_at=NOW,
            freshness_status=FreshnessStatus.FRESH,
        )


def test_skill_rejects_unbounded_tools():
    with pytest.raises(ValidationError):
        SkillManifest(
            skill_key="unsafe",
            name="unsafe",
            version="1.0.0",
            prompt_template="x",
            allowed_tools=["shell"],
        )
```

同时覆盖：时间顺序、数值单位、四类资产、Pack 生命周期、Research Session 模式、Agent 限额、提醒操作符和缺失值语义。

- [ ] **Step 2: 运行测试确认失败**

```bash
python -m pytest tests/unit/test_merged_platform_contracts.py -q
```

Expected: FAIL because the new contract modules do not exist.

- [ ] **Step 3: 实现聚焦的 Pydantic 契约**

`platform_shared.py` 定义 `AssetRef`、`AssetIdentifier`、`SourceRef`、`ObservationEnvelope`、`FreshnessStatus`、`DomainEvent`、`ScheduledJob`；其他文件只定义对应领域对象。使用 `model_validator` 强制 `available_at >= observed_at`、numeric value 必须带 unit、stale/unavailable 不得伪装 fresh。

- [ ] **Step 4: 写失败的迁移测试**

```python
def test_merged_platform_migration_creates_expected_tables():
    source = MIGRATION.read_text(encoding="utf-8")
    for table in EXPECTED_TABLES:
        assert f'"{table}"' in source
```

`EXPECTED_TABLES` 必须覆盖计划中的 18 张新表；同时断言迁移不会创建第二张 `research_run`、股票、指数、ETF 或基金事实表。

- [ ] **Step 5: 实现 SQLAlchemy 模型与 Alembic 迁移**

表拥有明确的唯一键、外键、时间索引和 JSONB 负载。所有跨来源身份放 `asset_identifier`；主题事实只进入 `theme_observation`；Research Note 引用现有 run/claim；Watchlist Item 只引用 canonical asset ID。

- [ ] **Step 6: 验证**

```bash
python -m pytest tests/unit/test_merged_platform_contracts.py tests/unit/test_merged_platform_migration.py tests/unit/test_alembic_migration_graph.py -q
python -m ruff check core/contracts data_layer/repositories/models.py storage/migrations/versions/015_add_merged_platform_core.py tests/unit/test_merged_platform_contracts.py tests/unit/test_merged_platform_migration.py
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add core/contracts data_layer/repositories/models.py storage/migrations/versions/015_add_merged_platform_core.py tests/unit/test_merged_platform_contracts.py tests/unit/test_merged_platform_migration.py
git commit -m "feat: add merged platform shared contracts"
```

### Task 3: 资产观察纵切

**Files:**
- Create: `data_layer/repositories/asset_observation_repository.py`
- Create: `services/asset_observation_service.py`
- Create: `services/alert_evaluation_service.py`
- Create: `app/api/routes/asset_observation.py`
- Modify: `app/api/main.py`
- Test: `tests/unit/test_asset_observation_service.py`
- Test: `tests/unit/test_asset_observation_api.py`

- [ ] **Step 1: 写身份、Watchlist、同类比较和提醒失败测试**

```python
def test_stale_fact_never_triggers_alert(service, stale_observation):
    result = service.evaluate(RULE, stale_observation)
    assert result.status == "skipped_data_stale"
    assert result.notification_id is None


def test_alert_fires_only_on_false_to_true_transition(service):
    first = service.evaluate(RULE, fresh_value(101))
    duplicate = service.evaluate(RULE, fresh_value(102))
    assert first.status == "triggered"
    assert duplicate.status == "deduplicated"
```

API 测试覆盖四类资产详情、peer-set 元数据、多列表、代码变更保留 Item、提醒确认和 resolved。

- [ ] **Step 2: 运行确认失败**

```bash
python -m pytest tests/unit/test_asset_observation_service.py tests/unit/test_asset_observation_api.py -q
```

- [ ] **Step 3: 实现 Repository 和 Service**

Repository 只操作本模块表以及现有结构化资产表；Service 组合 `AssetSnapshotEnvelope`，不复制资产事实。默认 peer 规则分别使用行业、指数类别、跟踪指数/主题、基金分类/基准。

- [ ] **Step 4: 实现 API**

提供 `/api/asset-observation/assets`、`/watchlists`、`/alert-rules`、`/alert-events`；所有 route 保持薄层并把异常映射为 400/404/409。写操作记录结构化日志。

- [ ] **Step 5: 验证与 Commit**

```bash
python -m pytest tests/unit/test_asset_observation_service.py tests/unit/test_asset_observation_api.py tests/unit/test_asset_analysis_service.py tests/unit/test_funds_api.py -q
python -m ruff check services/asset_observation_service.py services/alert_evaluation_service.py data_layer/repositories/asset_observation_repository.py app/api/routes/asset_observation.py tests/unit/test_asset_observation_service.py tests/unit/test_asset_observation_api.py
git add core/contracts/asset_observation.py data_layer/repositories/asset_observation_repository.py services/asset_observation_service.py services/alert_evaluation_service.py app/api/routes/asset_observation.py app/api/main.py tests/unit/test_asset_observation_service.py tests/unit/test_asset_observation_api.py
git commit -m "feat: add asset observation and alerts"
```

### Task 4: 全市场首页纵切

**Files:**
- Create: `data_layer/repositories/market_home_repository.py`
- Create: `services/market_home_service.py`
- Create: `app/api/routes/market_home.py`
- Test: `tests/unit/test_market_home_service.py`
- Test: `tests/unit/test_market_home_api.py`

- [ ] **Step 1: 写透明排名、快照和降级失败测试**

```python
def test_mainline_rank_exposes_versioned_components(service):
    ranked = service.rank_mainlines(SAMPLE_SECTORS)
    assert ranked.formula_version == "mainline-v1"
    assert ranked.leading[0].components.model_dump() == {
        "return_percentile": 1.0,
        "turnover_change_percentile": 1.0,
        "breadth_percentile": 1.0,
        "event_density_percentile": 1.0,
    }


def test_history_never_rebuilds_from_live_data(service, repository):
    service.get_snapshot(date(2026, 8, 28), "close")
    repository.assert_live_provider_not_called()
```

- [ ] **Step 2: 实现排序与快照服务**

`mainline-v1` 权重固定为 return 0.35、turnover change 0.30、breadth 0.25、event density 0.10；返回 components、sample_size 和 formula_version。区块独立计算 freshness，单区块失败不得使整页 500。

- [ ] **Step 3: 实现 API 与 SSE 失效事件**

提供 `/api/market-home/live`、`/snapshots/{trading_day}`、`/events` 和 drill-down。SSE 仅发送 section key、as_of 和 event ID。

- [ ] **Step 4: 验证与 Commit**

```bash
python -m pytest tests/unit/test_market_home_service.py tests/unit/test_market_home_api.py tests/unit/test_dashboard.py tests/unit/core/services/test_system_event_bus.py -q
python -m ruff check services/market_home_service.py data_layer/repositories/market_home_repository.py app/api/routes/market_home.py tests/unit/test_market_home_service.py tests/unit/test_market_home_api.py
git add core/contracts/market_home.py data_layer/repositories/market_home_repository.py services/market_home_service.py app/api/routes/market_home.py app/api/main.py tests/unit/test_market_home_service.py tests/unit/test_market_home_api.py
git commit -m "feat: add factual market home snapshots"
```

### Task 5: Research Pack、黄金纵切与 LSH 数据迁移

**Files:**
- Create: `theme_packs/gold/manifest.yaml`
- Create: `theme_packs/aerospace/manifest.yaml`
- Create: `theme_packs/photovoltaic/manifest.yaml`
- Create: `theme_packs/ai_infrastructure/manifest.yaml`
- Create: `services/theme_pack_registry.py`
- Create: `services/theme_observation_service.py`
- Create: `data_layer/repositories/theme_repository.py`
- Create: `app/api/routes/themes.py`
- Create: `scripts/migrate_lsh_theme_data.py`
- Test: `tests/unit/test_theme_pack_registry.py`
- Test: `tests/unit/test_lsh_theme_migration.py`
- Test: `tests/unit/test_themes_api.py`

- [ ] **Step 1: 写 Manifest 安全边界和迁移失败测试**

```python
def test_pack_plugin_cannot_declare_network_or_database_permissions(registry, tmp_path):
    manifest = write_manifest(tmp_path, plugin_permissions=["network"])
    with pytest.raises(ValueError, match="forbidden permission"):
        registry.load(manifest)


def test_migration_is_idempotent_and_preserves_source_hash(migrator, csv_file):
    first = migrator.scan(csv_file)
    second = migrator.scan(csv_file)
    assert first.source_hash == second.source_hash
    assert second.duplicate_count == first.accepted_count
```

- [ ] **Step 2: 实现 Registry、Observation 和六类读模型查询**

Manifest 必须验证 key/version/kind、边界、产业链、dataset schema、KPI 单位/频率/来源、新鲜度、资产暴露和模板。插件只允许 normalize/validate/derive。

- [ ] **Step 3: 实现四个 Manifest 与黄金纵切**

黄金声明价格、供需、ETF 持仓/流量、SGE、央行储备和宏观数据集；其余三个 Pack 声明 LSH 已存在的可迁移数据集，不迁 `score_hint` 或 `driver-summary`。

- [ ] **Step 4: 实现 dry-run 迁移器**

CLI 默认 `--dry-run`，输出 accepted/quarantined/rejected、缺失、重复、冲突、单位和哈希。只有显式 `--apply` 才通过 Repository 写入；重复 source_hash + row identity 幂等跳过。

- [ ] **Step 5: 实现主题 API**

提供 `/api/themes`、`/{key}/snapshot`、`/kpis`、`/value-chain`、`/events`、`/assets`、`/health` 和创建预填 Workspace 的请求模型。

- [ ] **Step 6: 验证与 Commit**

```bash
python -m pytest tests/unit/test_theme_pack_registry.py tests/unit/test_lsh_theme_migration.py tests/unit/test_themes_api.py -q
python scripts/migrate_lsh_theme_data.py --source /Users/leon/Desktop/LSH_Project/manual_data/skills --dry-run --output /tmp/lsh-theme-migration-report.json
python -m ruff check services/theme_pack_registry.py services/theme_observation_service.py data_layer/repositories/theme_repository.py app/api/routes/themes.py scripts/migrate_lsh_theme_data.py tests/unit/test_theme_pack_registry.py tests/unit/test_lsh_theme_migration.py tests/unit/test_themes_api.py
git add theme_packs services/theme_pack_registry.py services/theme_observation_service.py data_layer/repositories/theme_repository.py app/api/routes/themes.py app/api/main.py scripts/migrate_lsh_theme_data.py tests/unit/test_theme_pack_registry.py tests/unit/test_lsh_theme_migration.py tests/unit/test_themes_api.py
git commit -m "feat: add theme research packs"
```

### Task 6: FinGPT、Claw 与统一调度

**Files:**
- Create: `data_layer/repositories/research_workspace_repository.py`
- Create: `services/research_workspace_service.py`
- Create: `services/runtime_provider_service.py`
- Create: `services/agent_team_service.py`
- Create: `services/scheduler_coordinator.py`
- Create: `app/api/routes/research_workspaces.py`
- Create: `app/api/routes/research_runtime.py`
- Modify: `services/research_run_service.py`
- Modify: `app/api/routes/research_runs.py`
- Test: `tests/unit/test_research_workspace_service.py`
- Test: `tests/unit/test_runtime_provider_service.py`
- Test: `tests/unit/test_agent_team_service.py`
- Test: `tests/unit/test_scheduler_coordinator.py`
- Test: `tests/unit/test_research_workspace_api.py`

- [ ] **Step 1: 写项目隔离、回退、Skill 权限和调度失败测试**

```python
def test_workspace_memory_never_crosses_projects(service):
    service.pin_note(WORKSPACE_A, NOTE_A)
    assert NOTE_A.note_id not in service.build_memory_context(WORKSPACE_B).note_ids


def test_claw_does_not_semantically_fallback(router):
    with pytest.raises(RuntimeBlockedError) as exc:
        router.route(mode="claw", required_capabilities={"agent_team"})
    assert exc.value.code == "blocked_runtime"


def test_schedule_coalesces_missed_runs(coordinator):
    coordinator.record_missed(SCHEDULE_ID, count=3)
    assert coordinator.pending_runs(SCHEDULE_ID) == 1
```

- [ ] **Step 2: 实现 Workspace/Session/Message/Note**

临时 Session 可原子升级到 Workspace；完整 Run 自动关联并归档；置顶 Note 创建新 revision，旧 revision 不覆盖。所有查询必须带 workspace scope。

- [ ] **Step 3: 实现 Runtime Router 与 Skill/Team 安全验证**

FinGPT 允许 DSH→LangGraph 回退；Claw 缺 agent_team 能力时阻断。Skill 工具只能来自内部 allowlist、附件、受控网页和注册 MCP。Supervisor 通过 Blackboard 下发任务，并受步骤、并发、token/费用和 deadline 限制。

- [ ] **Step 4: 实现 Scheduler Coordinator**

使用 `scheduled_job` 的 owner、lease_expires_at 和 idempotency_key 获取租约；默认 single-flight，missed runs coalesce latest。现有数据调度器先通过适配层注册，不立即删除。

- [ ] **Step 5: 实现 API 与 SSE**

注册 workspaces、sessions/messages、runtime-providers、skills、agent-teams、agent-schedules；Run SSE 发送状态和阶段，不发送秘密或完整大对象。冲突幂等键返回已有资源。

- [ ] **Step 6: 验证与 Commit**

```bash
python -m pytest tests/unit/test_research_workspace_service.py tests/unit/test_runtime_provider_service.py tests/unit/test_agent_team_service.py tests/unit/test_scheduler_coordinator.py tests/unit/test_research_workspace_api.py tests/unit/test_research_run_service.py tests/unit/test_research_runs_api.py -q
python -m ruff check services/research_workspace_service.py services/runtime_provider_service.py services/agent_team_service.py services/scheduler_coordinator.py data_layer/repositories/research_workspace_repository.py app/api/routes/research_workspaces.py app/api/routes/research_runtime.py tests/unit/test_research_workspace_service.py tests/unit/test_runtime_provider_service.py tests/unit/test_agent_team_service.py tests/unit/test_scheduler_coordinator.py tests/unit/test_research_workspace_api.py
git add core/contracts/research_workspace.py core/contracts/research.py data_layer/repositories/research_workspace_repository.py services/research_workspace_service.py services/runtime_provider_service.py services/agent_team_service.py services/scheduler_coordinator.py services/research_run_service.py app/api/routes/research_workspaces.py app/api/routes/research_runtime.py app/api/routes/research_runs.py app/api/main.py tests/unit/test_research_workspace_service.py tests/unit/test_runtime_provider_service.py tests/unit/test_agent_team_service.py tests/unit/test_scheduler_coordinator.py tests/unit/test_research_workspace_api.py
git commit -m "feat: add FinGPT and Claw research runtime"
```

### Task 7: 兼容适配、删除门禁与前端交互契约

**Files:**
- Create: `services/legacy_capability_gate.py`
- Create: `docs/architecture/merged-platform/lsh-capability-map.yaml`
- Modify: `app/web/static/js/dashboard.js`
- Modify: `app/web/static/js/asset.js`
- Modify: `app/web/static/js/research-workbench.js`
- Modify: `app/web/static/js/industry.js`
- Test: `tests/unit/test_legacy_capability_gate.py`
- Test: `tests/unit/test_merged_platform_frontend_contract.py`

- [ ] **Step 1: 写删除门禁和前端契约失败测试**

```python
def test_duplicate_capability_cannot_be_removed_without_parity(gate):
    decision = gate.evaluate("lsh.flask.skill_snapshot")
    assert decision.allowed is False
    assert "parity_test" in decision.missing_evidence
```

前端静态契约测试断言四个入口只调用新领域 API，事实页面不存在 AI 自动摘要，研究输出不写事实接口。

- [ ] **Step 2: 实现 capability map 和 gate**

每项 LSH 能力记录 source、target、classification、data_migration、parity_test、call_count_zero、archive_path 和 status。只有全部门禁满足才能从 deprecated 转 removed。

- [ ] **Step 3: 改造现有页面交互契约**

不做视觉重设计；只把首页、资产、行业和研究工作台的数据调用、状态、空值和错误反馈切换到新 API。保留旧 API adapter 直到调用量归零。

- [ ] **Step 4: 验证与 Commit**

```bash
python -m pytest tests/unit/test_legacy_capability_gate.py tests/unit/test_merged_platform_frontend_contract.py tests/unit/test_research_workbench_frontend.py tests/unit/test_dashboard_wiring.py -q
git add services/legacy_capability_gate.py docs/architecture/merged-platform/lsh-capability-map.yaml app/web/static/js/dashboard.js app/web/static/js/asset.js app/web/static/js/research-workbench.js app/web/static/js/industry.js tests/unit/test_legacy_capability_gate.py tests/unit/test_merged_platform_frontend_contract.py
git commit -m "refactor: route workbench through merged platform APIs"
```

### Task 8: 文档同步、总验证与交付

**Files:**
- Modify: `docs/modules/app_api.md`
- Modify: `docs/modules/core_contracts.md`
- Modify: `docs/modules/core_services.md`
- Modify: `docs/REFERENCE.md`
- Modify: `docs/FILE_GUIDE.md`
- Modify: `docs/CHANGELOG.md`
- Create: `.ai/reports/2026-08-31-merged-platform-v1.md`

- [ ] **Step 1: 同步文档与任务报告**

报告必须区分已实现、仅有契约、未验证平台项和 LSH 冻结能力；记录真实命令和结果，不宣称未运行的 Windows 或安装验证。

- [ ] **Step 2: 跑完整相关测试**

```bash
python -m pytest tests/unit/test_merged_platform_contracts.py tests/unit/test_merged_platform_migration.py tests/unit/test_asset_observation_service.py tests/unit/test_asset_observation_api.py tests/unit/test_market_home_service.py tests/unit/test_market_home_api.py tests/unit/test_theme_pack_registry.py tests/unit/test_lsh_theme_migration.py tests/unit/test_themes_api.py tests/unit/test_research_workspace_service.py tests/unit/test_runtime_provider_service.py tests/unit/test_agent_team_service.py tests/unit/test_scheduler_coordinator.py tests/unit/test_research_workspace_api.py tests/unit/test_legacy_capability_gate.py tests/unit/test_merged_platform_frontend_contract.py -q
python -m ruff check core/contracts services data_layer/repositories app/api/routes scripts/migrate_lsh_theme_data.py tests/unit
python -m black --check core/contracts services data_layer/repositories app/api/routes scripts/migrate_lsh_theme_data.py tests/unit
python -m isort --check-only core/contracts services data_layer/repositories app/api/routes scripts/migrate_lsh_theme_data.py tests/unit
```

Expected: all targeted tests and static checks PASS.

- [ ] **Step 3: 跑回归与导入检查**

```bash
python -m pytest tests/unit/test_research_run_service.py tests/unit/test_research_runs_api.py tests/unit/test_asset_analysis_service.py tests/unit/test_funds_api.py tests/unit/test_dashboard.py tests/unit/core/services/test_system_event_bus.py tests/unit/test_alembic_migration_graph.py -q
python scripts/migrate_lsh_theme_data.py --source /Users/leon/Desktop/LSH_Project/manual_data/skills --dry-run --output /tmp/lsh-theme-migration-report.json
```

Expected: PASS；迁移报告含 accepted/quarantined/rejected 和 source hashes，数据库无写入。

- [ ] **Step 4: 记录未在本机完成的平台验证**

原生 Windows/macOS CI 的 sidecar、Tauri、PostgreSQL/pgvector ready/setup-required，以及真实 Windows 安装冒烟必须列为发布门禁；本地检查不能代替这些证据。

- [ ] **Step 5: 最终 Commit**

```bash
git add docs .ai/reports/2026-08-31-merged-platform-v1.md
git commit -m "docs: record merged platform delivery evidence"
```

## 自检映射

- 架构包与九图：Task 1。
- 共享类型和 18 张新表：Task 2。
- 资产观察、提醒、系统通知契约：Task 3、Task 7。
- 首页事实、透明主线与快照：Task 4。
- 四个 Pack、黄金纵切和 LSH dry-run：Task 5。
- FinGPT、Claw、白名单 MCP、Supervisor、日程：Task 6。
- 兼容、删除门禁和只读归档：Task 7–8。
- 测试、性能与跨平台门禁：Task 8。

本计划不包含策略、因子评分、模拟交易、报告中心或运维体系重构。
