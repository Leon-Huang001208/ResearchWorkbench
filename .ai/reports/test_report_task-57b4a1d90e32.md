# FinGPT / Claw DataHub：CJPY 接入交付证据

- 日期：2026-09-03；Harness：`task-57b4a1d90e32` / `sess-cb5914f0d6a74853`。
- 基线：`codex/merged-platform-v1`，`3c42117`；任务分支：`codex/datahub-cjpy`。
- 专用 worktree：`/Users/leon/Desktop/Projects/AlphaFoundry/.worktrees/datahub-cjpy`。
- 状态：功能实现及本地验收通过；原生 macOS / Windows CI 尚未执行，完整跨平台门禁未完成。
- 未合并、未发布。目标远端为公开仓库；推送任务分支并运行远端 CI 留作最终确认步骤。

## 实现范围

1. CJPY 0.5.2 的 17 类目录/数据接口，经 Adapter → Connector → 校验 → PostgreSQL 事实与完整快照入库。原始 gzip JSON、所有字段、索引元数据、SHA256 均保留。
2. `019_add_datahub.py` 在 018 后新增四表：快照、分页行、行情投影、任务批次。015–018 未修改；既有日线降级链及 `internal:asset_snapshot` 保留。
3. 股票/基金身份、上海业务时点、单位、缺失语义、分钟粒度、复权、乱序响应、隔离与重验证、幂等、批次重试和租约 fencing。旧日线未知复权语义不自动改写。
4. 手动同步复用 ScheduledJob，批次、事实、DomainEvent 和首页失效同事务提交。没有全市场历史自动回补。
5. `/api/datahub` 的来源、目录、分页事实、同步任务、健康、研究引用；能力中心真实 DataHub 页面。
6. 受信 `internal:data_catalog` / `internal:data_query` 及平台 MCP 调用同一 DataHubService。研究引用由服务端读回事实，限定 project/workspace/run；Artifact / Evidence 保留来源哈希、时点、单位和事实 ID。
7. 修复项目同名 mcp 包遮蔽已安装 SDK 的 stdio 入口；真实协议握手、发现、查询与写入拒绝已验证。
8. 架构追踪 CAP-DH-001、API-DH-001…008 及模块文档、API Atlas、Python 文件索引已更新。

## 环境与依赖

- 同一业务解释器：`/Users/leon/opt/anaconda3/bin/python`，Python 3.11；经用户授权由 CJPY 0.2.0 升级为 0.5.2，使用 `pip install --no-deps`。
- 项目可选依赖固定 `cjpy==0.5.2`；用户提供的 wheel、Apache-2.0 许可证及 manifest 在 `vendor/cjpy/`。
- wheel SHA256：`d8c6820a718ae5f79061b54815473dd3ecd3be73cd808634fbac5bc1c385bd94`。
- 已有 MCP SDK 1.27.2；未为此新增安装。Tauri 使用主项目已有 CLI，未安装 Node 依赖。
- 本机 PostgreSQL 18 + pgvector；样本库 `alphafoundry_datahub_test`、回归库 `alphafoundry_datahub_validation`、增量迁移库 `alphafoundry_datahub_upgrade` 分开。
- SDK token 沿用已有配置；未进入仓库、请求参数、事实库或报告。未迁移用户生产数据库。

## 实际验证

### 自动化与静态检查

| 验证 | 实际结果 | 本地日志 |
|---|---|---|
| DataHub、Adapter、研究 Workspace/Run/工具、Scheduler、事实契约及桌面回归 | 300 passed，5 warnings，27.52 秒 | `logs/datahub-acceptance-final.log` |
| 真实 MCP SDK stdio 客户端 | 1 passed，4.27 秒；握手、17 类目录、数据库查询、write 参数拒绝 | `logs/datahub-mcp-stdio.log` |
| 最后修改后的桌面契约及健康检查 helper | 56 passed，9.55 秒；与 300 项套件有重叠，不相加统计 | `logs/datahub-desktop-contracts-final.log` |
| 变更的 26 个 Python 文件 | Ruff / Black / isort 全通过 | `logs/datahub-targeted-checks-final.log` |
| 12 个相关 Python 源文件 mypy | Success，无类型错误 | `logs/datahub-mypy-delivery.log` |
| 蓝图、接口唯一性与引用追踪 | 8 passed | `logs/datahub-blueprint-final.log` |
| 3 个变更 JS 文件 | `node --check` 均退出 0 | 本次命令记录 |
| workflow YAML / 内嵌 Python | 解析及 Python AST 检查通过；未当作 CI 实跑 | 本次命令记录 |

主回归命令（`python` 指上述 Anaconda 解释器）：

```bash
DATAHUB_TEST_DATABASE_URL=postgresql+psycopg://leon@127.0.0.1/alphafoundry_datahub_validation \
python -m pytest tests/unit/test_datahub.py tests/unit/data_layer/adapters/test_cjpy_adapter.py \
  tests/unit/test_runtime_provider_service.py tests/unit/test_platform_scheduler_domains.py \
  tests/unit/test_alembic_migration_graph.py tests/unit/test_research_workspace_service.py \
  tests/unit/test_research_workspace_api.py tests/unit/test_research_run_service.py \
  tests/unit/test_research_runs_api.py tests/unit/test_desktop_shell_scaffold.py \
  tests/unit/test_scheduler_coordinator.py tests/unit/test_merged_platform_contracts.py \
  tests/unit/test_asset_observation_service.py -q --tb=short

DATAHUB_TEST_DATABASE_URL=postgresql+psycopg://leon@127.0.0.1/alphafoundry_datahub_test \
python -m pytest tests/unit/test_datahub_mcp.py -q
python -m pytest tests/unit/test_desktop_shell_scaffold.py tests/unit/test_check_sidecar_health.py -q --tb=short
node --test tests/javascript/merged_platform_blueprint.test.mjs
```

覆盖包括：17 类读回、额外字段/嵌套值、缺失不归零、未知身份与单位隔离、SH/SZ/BJ/OF 映射、分钟时刻、前后不复权隔离、历史未知复权保护、因子上海日期、旧响应不覆盖新事实、指数成分完整替换、隔离重验证、过期租约不能写入、部分失败只重试未完成批次、事实和事件事务回滚、响应大小分页、工具封闭白名单与写入拒绝。

全仓库 `ruff check .`、`black . --check`、`isort . --check-only` 也实际执行，未通过：当时分别报告 35 项问题、28 个格式文件、11 个 import 格式文件，主要来自基线；isort 的一项是忽略目录下的本任务预览脚本。没有把全仓库检查标为通过，也没有修改 015–018 等无关文件。最后对已触及的桌面测试文件修正一处既有引号格式；26 个交付 Python 文件最终均通过。原始日志：`logs/datahub-ruff-all.log`、`logs/datahub-black-all.log`、`logs/datahub-isort-all.log`。

### PostgreSQL 迁移

- 空白独立回归库从初始 revision 升至 019：通过，`logs/datahub-validation-migration.log`。
- 另建增量验证库，先升级 018 并写入旧 CJPY 日线（close=99、未知复权），再执行 `018 → 019`：只新增四张 DataHub 表，旧行内容保留。
- 同一验证库再执行 `019 → 018 → 019`：旧表集合与旧行情不变，回升通过。证据：`logs/datahub-incremental-migration.log`。
- 真实 PostgreSQL 回归使用回滚隔离；不会清空真实 CJPY 样本库。

### 真实 CJPY 样本

这部分是真实 SDK 请求与 PostgreSQL 读回，不是单元测试替身；列表数量不能解释为全市场历史数据覆盖。

| 数据集 | 成功获取 / 保存的样本 | 校验结果 |
|---|---:|---|
| universes / code_mappings / market_fields | 31 / 2 / 53 | 通过 |
| tables / table_fields / factors | 107 / 45 / 69 | 通过 |
| macro_tables / macro_indicators | 40 / 2510 | 通过 |
| stock_list | 5470 | 通过 |
| fund_list | 29930 | 修正 OF 身份映射后重同步，隔离 0 |
| codes | 5554 | 首次超时后重试成功；5449 可查询，105 身份未确认隔离 |
| index_constituents | 300 | 独立样本库缺少 IndexMaster，全部原样保存并隔离 |
| trading_days | 2 | 通过 |
| daily_quotes 日线 / 5 分钟 | 1 / 49 | 通过，分周期存储 |
| factor_data / table_data / macro_data | 1 / 1 / 2 | 修正无名 DataFrame 索引的字段误判后重试，隔离 0 |

原始运行与重试分别见 `logs/datahub-live-results.json`、`logs/datahub-live-recheck.json`、`logs/datahub-final-live.json`；原始 gzip 文件留在 `data/raw/cjpy/2026/09/03/`，不提交供应商数据。最后 codes 采集成功后的临时统计脚本因读取不存在的 `report.saved` 报错，事务已完成；后续独立数据库读回确认上述 5554/5449/105 数量。没有隐去这次统计脚本错误或最初隔离结果。

指数主数据缺失是样本库的实际限制；真实 PostgreSQL 测试中另有明确的指数主数据，已验证合法成分投影、修订替换及乱序保护。没有为使真实样本显示成功而编造身份。

### 网页、共享工具和证据链

- 最终预览：`http://127.0.0.1:8876/platform/?revision=datahub-delivery#/capabilities?tab=datahub`；绑定独立样本库，仅启动 DataHub 手动任务 Scheduler。
- 浏览器实际执行“目录 → 同步 → 入库记录 → 浏览 → 引用到研究”。真实目录任务 `job-4002e8ee345047abae8fed6eb590e56d` 返回 succeeded，保存 31 行，失败 0，attempt=1。
- 因子行 `000001.SZ / 2026-09-02 / 收盘价 11.91 CNY` 的事实 ID：`5c2acb8e3d80a7a7e0d15104572e6fe96bdac88f8108092c26524a55f99aa0d0:0`。
- 网页引用后实际生成 1 份可信研究 Artifact；来源 SHA256 `7f9ed72b3ea8d63ec668abc2c7ca77a1324f277385e0c41a32f3e88e26c7f783` 与事实一致。错误 Workspace 请求返回 422。证据：`logs/datahub-citation-verification.log`。
- MCP 查询同一事实 ID；写入参数被拒绝，见 `logs/datahub-mcp-proof-final.log` 及真实 stdio 测试。
- FinGPT / Claw 的相同工具输入返回一致事实；可信结果进入原 Run 的 Artifact / Evidence。未用外部 LLM 或 DSH 在线运行来替代契约测试。
- 最终页面交易日 D 周期实际读回两行；切换数据集清空旧结果并重置分页。截图 `logs/datahub-browser-final.jpg`；首次引用截图 `logs/datahub-browser-citation.jpg`。
- 查询中的旧业务日期保守显示 stale；未知、不可用或隔离数据未被包装为 fresh。合并产品壳其他原型页面仍有演示内容，不代表整个产品已上线。

### 原生 macOS

- 最终 arm64 PyInstaller sidecar 构建通过，约 585 秒：`logs/datahub-macos-build-exact.log`。正常构建参数相同，最后一次复核省略 `--clean`。
- 最终稳定产物 `/health` 明确断言 `persistence.status=ready`：通过，约 140 秒冷启动，`logs/datahub-macos-health-exact.log`。
- 独立数据目录、不可达数据库 `/health` 明确断言 `setup_required`：通过，约 104 秒，`logs/datahub-macos-health-setup.log`。helper 停止自己创建的进程并确认端口释放。
- `python scripts/desktop/prepare_tauri_sidecar.py` 后运行已有 Tauri CLI 的 `build --debug --bundles app`：通过，`logs/datahub-macos-tauri.log`。产物为 `src-tauri/target/debug/bundle/macos/AlphaFoundry.app`；已还原受版本控制的开发 shim，不提交打包二进制。
- 初次 60 秒检查超时；一次 180 秒检查遇到默认持久化 `.env` 覆盖测试数据库；另一次在最终构建替换二进制时遇到压缩流截断。随后使用稳定产物及任务专用权威配置，两种实际健康契约均通过。未更改用户桌面配置或系统安全设置。
- CI 已增加 CJPY wheel、DataHub 增量迁移及 PG 回归、独立权威 `.env`、两种明确健康断言和 180 秒冷启动上限；这些 workflow 修改尚未在远端 runner 实跑。
- 本轮原生健康检查使用 `ALPHAFOUNDRY_PREVIEW=1`，证明打包入口与数据库探针，不能证明正常启动下所有后台服务已启动；DataHub Scheduler 的证据来自真实网页手动任务与启动注册/重试测试。桌面 workflow 不包含 MCP stdio 测试，其证据来自本地独立测试。

### 独立审查

只读审查分轮覆盖事实/身份/复权/乱序/租约、查询与证据链，以及最后的 MCP stdio / CI 权威配置。已修复的具体问题均配套回归；最后一轮未发现有依据的阻断问题。审查没有替代真实运行，也没有把 preview 健康检查扩大解释为后台全服务验收。

## 剩余门禁与回滚

- **原生 Windows CI 与 macOS CI 尚未执行。** 本机 macOS 成功不能证明 Windows 支持。公开远端推送与 workflow dispatch 待确认；不触发 release workflow、不合并目标分支。
- 发布前的真实 Windows 安装级 smoke 不在本次发布范围内，仍是以后发版的必要条件。
- 本机环境以 Anaconda 全环境打包，sidecar 体积较大且冷启动慢；没有为此扩展到依赖裁剪。
- CJPY 已用当前账户实测；其余 13 个注册来源未逐一测试实时连通性。对历史数据使用保守 36 小时新鲜度规则，尚未为各类数据建立特定刷新日历。
- 回滚应用分支即可停止使用 DataHub；若回滚 019，会删除四张新增表，必须先备份。已归档原始文件、研究 Artifact 及对旧事实仓储的合法投影应按运维保留策略处理，迁移降级不会自动撤销这些历史事实。
- 安装包、真实样本、任务数据库、运行日志均留在本机；仓库交付仅含源代码、测试、文档、架构产物及已授权 SDK wheel/许可证。

## 最终完整性

文档同步、任务报告完整性与 `git diff --check` 均通过。结果分别在 `logs/datahub-doc-sync.log`、`logs/datahub-task-completion.log`、`logs/datahub-diff-check.log`。Harness 已记录本地回归 passed、任务 blocked / permission；最终 `harness-enforce.mjs` 退出 1，原因 `latest outcome is not completed/passed`，记录在 `logs/datahub-harness-enforce.log`。这是公开远端推送/跨平台 CI 尚未完成的真实验收状态，不能据本地测试宣称整体门禁通过。
