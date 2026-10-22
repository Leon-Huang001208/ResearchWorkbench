# 基金 NAV 原生研究仓捕获（2026-10-22）

宿主 macOS；任务类型为 Web 功能开发。隔离 worktree：`ResearchWorkbench-worktrees/datahub-fund-snapshots-20261022`，实现基线 `346fe44`（PR188 依赖）。本报告不代表远端 CI、常驻部署、Windows/Linux、正式回测或全历史验收。未提交、未 push、未开 PR。

<!-- architecture-review {"group":"datahub","structure":"unchanged","reason":"仅收窄既有原生快照的NAV缺口准入条件；沿默认Host/Broker/MarketStore原件与修订路径，不新增HTTP、schema、节点或执行引擎，既有04图拓扑保持。","diagrams":[]} -->

## 范围与合同

仅在既有 `SnapshotSeries.ingest` 接受一个封闭例外：实际 scope/result provider 均为 `eastmoney_fund`，`fund_data` 的 `nav` 或 `fund_nav`，日期差 0–30 天（最多31个日历日），`status=complete`、`pagination_complete is True`，且所有 missing 都属于 `adjusted_total_return`、`benchmark_timeseries`、`verified_currency`。仍保留缺口、限制、原字段和不可变原件；不把未知币种、基准或累计净值认证为总回报。读取继续明示 `quality_accepted=False`、`formal_backtest_eligible=False`。

其他来源/dataset、缺 provider、未知缺字段、无界/宽区间、日期错误/倒序、snapshot/empty/partial、缺原件和历史 as_of 写入继续拒绝或不入仓。无新 HTTP、schema、依赖、引擎或部署节点。

## 实际验证

解释器为既有 `/Users/leon/Desktop/Projects/ResearchWorkbench-worktrees/datahub-warehouse-20261022/.venv-tests/bin/python`，没有安装依赖。

- RED：`python -m pytest --confcutdir=tests/research_web tests/research_web/test_research_snapshot_store.py -q -k 'bounded_nav or nav_exception'`：修复前 2 failed / 10 passed，两个合法 NAV 捕获均因旧 completeness 检查拒绝。日志 `logs/fund-nav-snapshots/red.log`。
- 离线闭包：`python -m pytest --confcutdir=tests/research_web tests/research_web/test_research_snapshot_store.py tests/research_web/test_research_warehouse_management.py tests/research_web/test_datahub_warehouse.py tests/research_web/test_market_store_live_postgres.py -q`：45 passed、19 skipped、12 subtests passed；19个 live PostgreSQL 测试未设置 opt-in，SKIPPED 不是数据库通过。日志 `logs/fund-nav-snapshots/offline.log`。
- 默认 `ResearchService` 自行构造 `ResearchWarehouse` 与 `StorageRunner`，保留实际 Broker。离线测试仅用内存 backend 和 HTTP transport fixture，第一次查询写仓；第二个不同 call_id 通过仓返回2行，供应商调用数始终1（第二次调用硬拒绝）。实际 catalog 禁用撤权、来源配置 revision 变更，以及已绑定 warehouse profile 被禁用均失败关闭；无模型调用。
- 四个修改 Python 文件的 `python -m ruff check ...`、`python -m black ... --check`、`python -m isort ... --check-only` 均通过；最初 Ruff SIM117 / Black 排版失败已修复并复验。

## 真实有界验收与清理

根任务复核隔离后授权继续既定有界验收。实际命令：`RWB_MARKET_STORE_LIVE_PG=1 RWB_MARKET_STORE_LIVE_DATA=1 /Users/leon/Desktop/Projects/ResearchWorkbench-worktrees/datahub-warehouse-20261022/.venv-tests/bin/python -m pytest --confcutdir=tests/research_web tests/research_web/test_market_store_live_postgres.py -q -s -k default_host_bounded_eastmoney_nav_capture_and_restart`。结果 **1 passed、18 deselected**，3.58秒，日志 `logs/fund-nav-snapshots/live-nav.log`。

新增 opt-in `LivePostgresTests.test_default_host_bounded_eastmoney_nav_capture_and_restart` 使用现有自有 tempfile PostgreSQL fixture，真实取得 `510050`、`2025-01-02..2025-01-03` 的2行 NAV。默认 Host/API 创建仓配置并初始化，实际 Broker 走既有东财 Provider；首次写入、第二个 call_id 数据库命中、仅自有 PG 重启后再次命中均通过。供应商 fetch 始终仅1次（后续调用硬拒绝），固定 as_of 的冻结原件字节、rows、fields 和 missing 在重启前后相等。`quality_accepted=False`、`formal_backtest_eligible=False`、`historical_point_in_time=False`；模型调用0。

Host 构造前显式注入内存 MCP/delivery credential backend，DataHub 默认 credential backend 也替换为同一内存后端；同时为 SystemKeyringBackend 的 get/set/delete 设置 fail-closed 哨兵，并断言三者均未调用。keyring 原始 get/set/delete 同时被内存实现覆盖。没有读取或修改实际 Keychain、既有5432、业务数据库、外置盘或常驻服务。fixture 结束打印 `owned_pgdata_removed=true owned_pg_stopped=true tcp_disabled=true fsync=on`，自有临时数据库和目录已回收。

候选 Router、独立评审、完整性检查和远端门由根任务继续；真实单样本不是全历史或正式回测验收。

## 测试隔离事故（保留真实风险）

首次默认 Host 测试只替换了 `keyring.get_password`，未替换 set/delete。构造 `ResearchService` 时 `_build_mcp_runtime` → `_persistent_mcp_key` → `SystemKeyringBackend.set_password` → `keyring.set_password` 返回后，第二次 mocked get 仍为 None，报 `mcp_runtime_key_race`。非秘密身份为 service `ResearchWorkbench.MCPRuntime`、account `confirmation-signing-v1`。这是固定全局 MCP 签名项，无法证明该项为临时测试独占；可能覆盖同名既有签名 key。不读取实际 key 值、不删除、不声称恢复。初次 Store 在 `TemporaryDirectory` 内，但该 service/account 不含 Store 根；日志未保留临时根，后续 host.log 被再次运行覆盖。

已向根任务立即报告并暂停真实验收。随后测试在任何 `ResearchService` 构造前同时将 get/set/delete 全部替换为内存字典，离线闭包通过。根任务只读归因确认该固定项用于 ConfirmationTokenManager，默认票据5分钟、最大10分钟；本次调用路径没有变更 installation integrity、vendor 或 model 项。既有同名 key 的先前状态仍不能证明；本补丁没有修复/删除该项、读取秘密或重启服务。根任务复核新增 live 测试隔离并要求增加上述显式内存后端和真实后端哨兵后，才继续自有 PG 有界验收。

## 交接文件

- `app/research_web/datahub/research_snapshot_store.py`：封闭 NAV 捕获条件。
- `tests/research_web/test_research_snapshot_store.py`：成功保留语义缺口及边界拒绝。
- `tests/research_web/test_research_warehouse_management.py`：默认 Host/Broker 离线生命周期与当前授权。
- `tests/research_web/test_market_store_live_postgres.py`：已通过的有界免费 NAV + 自有 PG 重启验收。
- `docs/research-web-vendor-snapshots.md`：同合同。

真实东财两日与自有 PG 通过不认证币种、基准、总回报、完整历史或正式回测。部署、全历史、生产连接和付费/模型任务不在此子任务范围。


## 根任务复核补充

PR188已合并为88ef3817680ac822e2d7c819db845de4b7275173，后续本切片不重复其变更。独立复审另发现仅mock keyring不足以隔离RESEARCH_CREDENTIAL_HOME文件后端；默认离线Host和live NAV测试现均显式注入DataHub、MCP registry/runtime、delivery内存后端，并对SystemKeyring三方法及PrivateFileCredentialBackend构造设失败关闭哨兵且assert_not_called。修复后39项及12subtests通过，真实两日ownedPG重验1项2.88秒通过并停止清理；两轮独立Python评审均PASS。无新增依赖、已有服务变更或外盘操作。
