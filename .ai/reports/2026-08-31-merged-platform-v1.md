# Research Workbench × LSH 合并平台 V1 交付报告

## 范围与边界

本任务按 `docs/architecture/merged-platform/` 实施四个纵切：FinGPT/Claw、facts-only 市场首页、Research Pack、资产观察，并保留模块化单体 + 可选本地 DSH 侧车。PostgreSQL + pgvector 仍是唯一权威存储；事实区、研究区和个人观察区隔离；没有实施策略、因子评分、模拟交易、报告中心或运维体系重构。

LSH 的策略、交易和基金审批能力保持冻结归档。旧 Flask、SQLite、静态 Dashboard 和平行运行模型只有在真实 apply、parity、回归、零调用、归档路径和稳定观察期全部通过后才允许停止/删除；本任务没有绕过该门禁执行破坏性删除。

## 已实施

- 七份专题架构正文、索引、九张正式 Archify 图源/HTML，以及详细 API/状态/追踪补充图。
- 五个共享契约模块、20 张 additive ORM 表和 Alembic 015–018；继续复用既有 Research Run 与资产事实表。
- 四类资产统一身份/详情/peer set、Watchlist、Alert 状态机、持久站内 Notification 与官方 Tauri 系统通知桥。
- 首页五区 live 投影、透明 `mainline-v1`、不可变 close snapshot、durable invalidation SSE，以及权威 writer 同事务 outbox 和持久收盘调度器。
- 黄金、航天、光伏、AI 基础设施四个 Research Pack、统一 Observation、六类读模型、严格 Manifest/内置插件边界和 LSH dry-run/apply/resume 迁移器。
- Workspace/Session/Message/Note、Runtime Router、声明式 Skill、Supervisor Agent Team、Agent Schedule、持久租约/fencing 与有序 Research Run SSE。
- 现有首页、资产、主题和研究工作台通过 additive 新 API 适配；删除门禁由 `LegacyCapabilityGate` fail-closed 控制。

## 已执行证据

- 架构：九份正式 Archify JSON/HTML 均通过 showcase validation 和四视口检查；详细蓝图另覆盖 8 张共享图和 30 张领域图。
- 合并平台总聚焦：共享契约、迁移、资产、首页、四个 Pack、Workspace/Session/Run、Skill、Runtime Router、Agent Team/Schedule、统一调度、前端契约和删除门禁共 `351 passed, 5 warnings in 23.06s`。
- Research Pack：独立复核通过；Pack 聚焦 `145 passed`。真实 LSH dry-run 的两次报告在 totals、28 个 source hash 和 28 个 checkpoint 上完全一致。
- Research Runtime：经过生产工具接线、预算、唯一归属、动态 Supervisor、heartbeat、reservation takeover、stale terminal fencing 和 ACK 丢失重放多轮攻击性复核，最终独立结论 PASS；扩展回归 `172 passed`，Agent Schedule 最终 `7 passed`。
- PostgreSQL：本机 PostgreSQL 18.3 + pgvector 0.8.5 从空库完整执行 `001 → 018`；确认 head 018、六类核心表及 `uq_research_session_run_id`。烟测、`SKIP LOCKED`、租约接管/fencing 和 Workspace 幂等隔离共 `3 passed`。
- 浏览器：独立 Chrome/Playwright 脚本验证 8 个路由、4 个视口、5 条完整旅程、10 张截图、10 种显式状态和 stale alert guard，结果 `prototype_e2e_pass`；FinGPT 输入问题保持验证通过且浏览器 console error 为 0。
- JavaScript/桌面本地：蓝图、产品原型和 Tauri 通知桥 `20 passed`；相关 JS `node --check` 通过；macOS `cargo check` 通过。
- 格式与静态检查：本次变更 45 个 Python 文件的 Black/isort 通过；Ruff 对变更文件通过，`models.py` 仅忽略该历史文件已有的 `RUF012/UP017` 债务。仓库全量 Ruff 仍有 8,367 个既有问题，不属于本合并范围。
- 本地契约性能基线（FastAPI TestClient + 确定性 stub，40 次，不等同生产负载）：market-home live P95 0.888ms、SSE 首状态 P95 1.022ms、资产 P95 0.891ms、主题 P95 44.99ms、提醒评估 P95 0.985ms，均低于计划门槛。
- 仓库全量 pytest 尝试在三个既有可选依赖处被收集阻断：`Crypto`、Python `playwright` 和 `fake_useragent`。未为无关连接器污染共享虚拟环境；上述 351 项合并平台测试和 Node Playwright 验收不依赖这些包。

## 数据迁移证据

真实源目录为 `/Users/leon/Desktop/LSH_Project/manual_data/skills`。最终两次执行均保持 dry-run，未连接或写入目标数据库：

- files scanned：28
- accepted：14,575
- quarantined：0
- rejected：16
- duplicate：0
- applied：0
- source hashes：28，两个报告完全一致
- checkpoints：28，两个报告完全一致，且均为 dry-run mode

拒绝记录保留行级审计；没有把缺单位、禁止字段或未映射来源写入事实区。

## 未验证与发布门禁

- 本地 PostgreSQL 已验证迁移和核心并发语义，但未执行生产迁移、长时多进程 soak、生产数据量查询压测或灾备演练。
- 未连接真实 DSH 产品侧车或真实白名单 MCP；只验证了 localhost adapter、回调关联和受控 handler。未进行长时 SSE/并发客户端负载测试。
- 未执行真实 LSH apply，因此不能满足 LSH 停止/删除门禁。
- macOS 本地 `cargo check` 不能证明 Windows。原生 macOS/Windows CI 仍须构建各自 Python sidecar、Tauri 安装包并验证 PostgreSQL ready/setup-required；发布前还必须在真实 Windows 设备完成安装、升级、卸载、主窗口、sidecar、日志以及通知权限烟测。
- 本实现位于隔离分支 `codex/merged-platform-v1`，尚未合并到用户当前的脏工作区，也未发布。

## 最终状态

本地实现与架构实施门禁完成，可进入合并评审。发布门禁仍明确保留：真实 LSH apply/parity/零调用/稳定观察期、真实 DSH/MCP、原生 Windows CI 和真实 Windows 安装级冒烟未完成，因此没有停止或删除 LSH，也不宣称 Windows/生产已验证。
