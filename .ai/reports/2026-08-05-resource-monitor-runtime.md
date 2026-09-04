# 资源监控常驻运行时交付报告

**日期：** 2026-08-05
**状态：** 已实现，待集成

## 范围

- 新增 `ResourceMonitorRuntime`，使用单一 `threading.Thread`、`Event` 和 `time.monotonic()` 周期性采集资源快照。
- 每次周期创建一个数据库会话和 `MonitoringRepositoryImpl`，在该会话内调用 `ResourceHostHistoryService.record_if_due()` 与 `ResourceMonitorAlertService.evaluate()`。
- 运行时共享一个 `ResourceAlertState`，每次创建的告警服务都显式消费同一状态，因此压力和恢复连续计数不会在分钟周期之间重置。
- API 在数据库就绪且 `ensure_schema()` 完成后启动运行时；`RESEARCH_PREVIEW=1` 和桌面 `setup_required` 均不启动。关闭时先停止运行时，再停止现有数据调度器。

## 失败处理

- 采样、历史写入、告警评估和线程生命周期异常均只记录结构化 `error_type`，不将内部异常细节写入日志事件字段；告警评估降级为 warning。
- 历史或告警阶段失败不会阻止同周期另一个阶段执行，且后续周期继续执行。
- `start()` 幂等；`stop()` 发出停止信号并以可配置的有限超时等待活动线程退出。阻塞采样超时时记录 `RuntimeStopTimeout` warning 并返回受控失败值，使 API 继续关闭。

## 验证

| 命令 | 实际结果 |
| --- | --- |
| `python -m pytest tests/unit/test_resource_monitor_runtime.py tests/unit/test_resource_monitor_alert_service.py tests/unit/test_resource_host_history_service.py tests/unit/app/api/routes/test_setup_readiness.py -q` | 36 passed；FastAPI 既有 `on_event` 弃用警告 4 条 |
| `ruff check services/resource_monitor_runtime.py services/resource_monitor_alert_service.py app/api/main.py tests/unit/test_resource_monitor_runtime.py tests/unit/test_resource_monitor_alert_service.py tests/unit/app/api/routes/test_setup_readiness.py` | passed |
| `black --check services/resource_monitor_runtime.py services/resource_monitor_alert_service.py app/api/main.py tests/unit/test_resource_monitor_runtime.py tests/unit/test_resource_monitor_alert_service.py tests/unit/app/api/routes/test_setup_readiness.py` | passed |
| `isort --check-only services/resource_monitor_runtime.py services/resource_monitor_alert_service.py app/api/main.py tests/unit/test_resource_monitor_runtime.py tests/unit/test_resource_monitor_alert_service.py tests/unit/app/api/routes/test_setup_readiness.py` | passed |
| `python scripts/generate_py_file_index.py && python scripts/check_doc_sync.py` | generated index; documentation sync passed |
| `git diff --check` | passed |

## 风险

- 本地验证使用伪监控器、伪会话和伪仓储，未连接真实 PostgreSQL。
- 告警共享状态的具体消费逻辑由后续任务实现；本变更仅提供稳定的共享状态注入边界。
