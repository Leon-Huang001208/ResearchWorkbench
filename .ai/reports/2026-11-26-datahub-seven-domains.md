# DataHub WeKnora 七域目录结构

<!-- architecture-review {"group":"inbound-mcp-readonly","structure":"unchanged","reason":"七域只作为现有入站 MCP 业务工具的目录骨架，复用原 OAuth、Host、DataHub 查询、status 分页和快照链；不新增服务、执行器、数据库、HTTP 路由或权限范围。","diagrams":[]} -->

宿主：macOS arm64 Mac mini；任务类型：Web 后端功能重构；本平台范围为本地 Python/HTTP 合同、
既有仓库门与 macOS 安装。Windows/Linux 产品验收为 NOT_RUN。
任务：`datahub-seven-domains-20261126`；基线：`4a080a03`，开发中已合并 `origin/master` `069b5dd7`。

## 变更

- 新增 `mcp_facade/domains.py`，把 stock_data、fund_data、index_data、bond_data、
  financial_docs、economic_data、analytics_data 定义为有序、不可变的域对象，显式列出工具清单
  与 available/reserved 状态；bond_data、analytics_data 保留为空工具域。
- `task_contracts.py` 保留 `TASKS` 的历史 4 元组解包接口，但域由 `domains.py` 派生而不是重复存储；
  导入时校验已注册工具恰好归属一个域、域内工具均存在、无重复或孤儿归属。
- `tools/list` 为每个业务工具附 `_meta.rwb.business` 域标记，并在结果级
  `_meta.rwb.business_domains` 提供按七域分组的目录；`rwb_datahub_catalog` 增加同样分组。
  原有 9 个工具名、输入 schema、scope 过滤、错误码、提交和 status 返回保持不变。
- 新增空工具的 financial_docs 域保持 available 以承接后续已验证的新闻/公告工具；
  reserved 域不注册占位工具。公共 search_assets、get_trading_calendar 显式归入 stock_data，
  不另造第八个“shared”金融域。

## 范围外观察

- `datahub/planning.py` 仍只对 `market_bars` 提供仓库规划；其余业务工具没有同等增量补齐。
  本任务按用户要求未改动。
- 原始设计的 search_news、search_announcements、query_user_table 仍未注册；
  `docs/plans/2026-11-24-weknora-datahub-skill-layer.md` 保留为目标设计，不作为已交付事实。

## 验证

- 项目共享测试环境完整入站 MCP 合同（8 个 `test_mcp_facade_*` 与本文件）：
  163 passed，7 subtests passed，真实耗时 101.69 秒。
- HTTP 合同覆盖业务工具七域分组、旧 read scope 不暴露业务目录、catalog 分组；
  `test_documentation.py` 与 `test_documentation_center.py` 另 36 passed。
- `ruff check`、`black --check`、`isort --check-only` 通过；
  `check_documentation_governance`、`generate_py_file_index --check`、
  `check_research_architecture --base origin/master` 通过；
  Actions 与架构 Node 合同 202 passed（另有文档治理合同已单独通过）。
- `scripts/mcp_datahub_ci.py` 将 domains/server/task_contracts/tools 作为业务工具入口纳入
  原 MCP/DataHub lane；资产三项桥接仍要求 contracts/task_contracts/asset_workspace 同时变化。

Product-Progress: not-required — 本次只把既有后端 MCP 工具目录重构为七域结构，用户界面与产品可见功能未变化。

