# 整机容量分钟历史交付报告

**日期：** 2026-08-05
**状态：** 已实现，待集成

## 范围

- 新增 `ResourceHostHistoryService`，将整机容量的白名单字段保存到既有 `HealthMetrics.extra`。
- 每个 UTC 分钟使用带稳定 UUIDv5 后缀的确定性 `resource-host-<utc-minute>-<uuid>` 主键保存最多一条 `host_capacity`；仓储会先按类型过滤再限制查询，公开查询最多返回 1500 个按时间升序的安全公开点。
- 条件写入在 savepoint 内处理唯一冲突，不污染外层事务；其他持久化异常记录安全 warning 后返回受控失败值。
- 在写入时按 1500 条一批循环清理所有超过 24 小时的同类记录；资源事件及其他监控指标不会被删除。
- 为 `MonitoringRepositoryImpl` 增加按非空 ID 精确删除指标的能力，不创建表或迁移。

## 隐私与失败处理

- 只保存七个 `host` 字段和四个 `alpha` 字段；内部进程、PID、命令及其他快照键会丢弃。
- 缺少或错误的 `host` 输入会记录结构化 `error_type` 并跳过持久化。
- 仓储或查询异常同样仅记录 `error_type`，并以受控的失败值返回。
- 受控失败路径使用 warning，避免把可降级的采样与查询问题升级为错误级别告警。

## 验证

| 命令 | 实际结果 |
| --- | --- |
| `python -m pytest tests/unit/test_resource_host_history_service.py tests/unit/test_monitoring.py -q` | 55 passed |
| `ruff check services/resource_host_history_service.py data_layer/repositories/monitoring_repository.py tests/unit/test_resource_host_history_service.py` | passed |
| `black --check services/resource_host_history_service.py data_layer/repositories/monitoring_repository.py tests/unit/test_resource_host_history_service.py` | passed |
| `isort --check-only services/resource_host_history_service.py data_layer/repositories/monitoring_repository.py tests/unit/test_resource_host_history_service.py` | passed |
| `git diff --check` | passed |

## 风险

- 变更尚未接入运行时采样、API、UI 或告警流程，符合本任务边界；接入方需显式创建并调用该服务。
- 验证使用本地单元测试与模拟仓储，未连接实际 PostgreSQL。
