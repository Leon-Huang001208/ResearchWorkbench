# OpenBB DataHub Provider 接入

macOS arm64，功能开发。OpenBB 5.0.0 及 217 个依赖安装在
`/Users/leon/Developer/openbb/.venv`（`openbb[routers]`，`openbb-build` 已执行），
RWB Web 环境未新增依赖。

接入只开放 `external_data/equity_daily`：`args.params.symbol`、`provider`
（`nasdaq`/`cboe`/`tmx`）与 `args.query.start_date`/`end_date`。Host 不导入 SDK，
每次调用由 `RWB_OPENBB_PYTHON` 指向的解释器运行固定 `public_worker openbb` 子进程，
最小环境、临时 HOME、30 秒上限，父进程校验固定 Result schema。未配置解释器时
`blocked_dependency`；binding 仍登记，固定来源请求明确不可用，不换源。

真实链路（本机）：`DataHub.query` → `snapshot`、4 行、`data_success=true`、
执行健康 `success`，AAPL 2026-11-20 至 11-25，provider=nasdaq。默认 `cboe`
匿名返回 HTTP 403；`tmx` 同样失败。单位、币种、PIT、历史修订未认证；
OpenBB 是第三方转发，不是原始来源。`purpose=backtest`、`as_of`、
`required_semantics` 拒绝，也未进入研究仓 `PUBLIC_NUMERIC` 白名单。

已验证：`test_datahub_openbb.py` 9 项、DataHub catalog/connection/外部源/清单相关
回归、`verification_policy` 与 `actions_quota_governance` 148 项 JS。
`ruff`、`black --check`、`isort --check-only`、`mypy` 通过。
未执行：GitHub CI、真实 Windows/Linux、常驻服务部署、OpenBB 其他 provider 或数据集。

Product-Progress: not-required — 本次仅新增可选 DataHub 来源和开发文档，用户可见进度尚未确认发布。

<!-- architecture-review {"group":"datahub","structure":"unchanged","reason":"新增一个首类 SDK 来源及固定 external_data 数据集，沿用既有 Broker→Provider→会话快照边界，无新增服务、数据库、路由或仓库拓扑；只在既有 provider dispatch、catalog、probe 与 worker_activity 上增加封闭分支。","diagrams":[]} -->
<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"只把新增 Provider、worker 与测试登记进既有 mcp_datahub_only 路径闭包和 verification-policy 的 inbound-mcp 文件清单，复用原 runner、job、权限与平台门，不改 CI 拓扑。","diagrams":[]} -->
